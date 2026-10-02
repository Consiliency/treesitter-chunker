"""Observable compatibility results and local grammar selection."""

from dataclasses import asdict
import subprocess
import sys
import time
from pathlib import Path

import pytest

from chunker import get_parser
from chunker.grammar_management.compatibility import (
    CompatibilityChecker,
    CompatibilityDatabase,
    CompatibilityLevel,
    SelectionCriterion,
    SmartSelector,
    TestResult as GrammarTestResult,
)
from chunker.grammar_management.core import GrammarManager, load_compiled_grammar


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    ("language", "fixture"),
    [
        ("python", "tests/fixtures/boundary_ir/repos/python/app/service.py"),
        ("javascript", "tests/fixtures/boundary_ir/repos/javascript/service.js"),
    ],
)
def test_supported_fixture_parsers_accept_real_source(
    language: str, fixture: str
) -> None:
    source = (ROOT / fixture).read_bytes()
    tree = get_parser(language).parse(source)
    assert not tree.root_node.has_error


def test_compatibility_reason_score_selection_and_history(
    tmp_path: Path, monkeypatch
) -> None:
    if sys.platform != "linux":
        pytest.skip("The checked-in grammar builds as a Linux shared library")

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    source = (
        ROOT / "packages/baml-grammar/tests/fixtures/declarations.baml"
    ).read_text(encoding="utf-8")
    user_dir = tmp_path / "user"
    package_dir = tmp_path / "package"
    user_dir.mkdir()
    package_dir.mkdir()
    (user_dir / "libbaml.so").touch()
    package_library = package_dir / "libbaml.so"
    grammar_src = ROOT / "packages/baml-grammar/src"
    subprocess.run(
        [
            "cc",
            "-shared",
            "-fPIC",
            "-O2",
            "-I",
            str(grammar_src),
            str(grammar_src / "parser.c"),
            "-o",
            str(package_library),
        ],
        check=True,
        capture_output=True,
    )
    assert (
        not load_compiled_grammar(package_library, "baml")
        .parse(source.encode("utf-8"))
        .root_node.has_error
    )

    manager = GrammarManager(
        user_dir=user_dir,
        package_dir=package_dir,
        cache_dir=tmp_path / "cache",
    )
    database = CompatibilityDatabase(tmp_path / "history.db")
    checker = CompatibilityChecker(manager, database)
    incompatible = checker.check_compatibility("baml", code_samples=[source])
    assert incompatible.level == CompatibilityLevel.INCOMPATIBLE
    assert incompatible.score == 0.0
    assert any("empty" in issue.lower() for issue in incompatible.issues)
    recorded = database.get_compatibility_result("baml", "unknown")
    assert recorded is not None
    history = asdict(recorded)

    compatible = checker.check_compatibility(
        "baml", code_samples=[source], grammar_path=package_library
    )
    assert compatible.level in {
        CompatibilityLevel.COMPATIBLE,
        CompatibilityLevel.DEGRADED,
    }
    assert compatible.score > incompatible.score
    assert compatible.test_results is not None
    assert compatible.test_results["successful_samples"] == 1

    selected = SmartSelector(manager, checker, database).select_best_grammar(
        "baml", criteria_weights={SelectionCriterion.COMPATIBILITY: 1.0}
    )
    assert selected is not None
    assert selected.grammar_path == package_library
    assert selected.compatibility_score > 0.0
    preserved = database.get_compatibility_result("baml", "unknown")
    assert preserved is not None
    assert asdict(preserved) == history


def test_performance_trends_filter_language_age_and_preserve_order(
    tmp_path: Path,
) -> None:
    parsed = {}
    for language, fixture in (
        ("python", "tests/fixtures/boundary_ir/repos/python/app/service.py"),
        ("javascript", "tests/fixtures/boundary_ir/repos/javascript/service.js"),
    ):
        source = (ROOT / fixture).read_bytes()
        tree = get_parser(language).parse(source)
        assert not tree.root_node.has_error
        parsed[language] = {"root_type": tree.root_node.type, "bytes": len(source)}

    database = CompatibilityDatabase(tmp_path / "trends.db")
    now = time.time()
    for language, age_days, throughput, memory_delta in (
        ("python", 2, 10.0, 8.0),
        ("javascript", 1.5, 100.0, 99.0),
        ("python", 1, 20.0, 4.0),
        ("python", 45, 200.0, 80.0),
    ):
        database.store_test_result(
            GrammarTestResult(
                language=language,
                grammar_version="pinned",
                test_type="parse",
                success=True,
                duration=0.1,
                sample_results=[parsed[language]],
                performance_metrics={
                    "avg_throughput_lines_per_sec": throughput,
                    "memory_delta_mb": memory_delta,
                },
                timestamp=now - age_days * 24 * 60 * 60,
            )
        )

    assert database.get_performance_trends("python", days=30) == {
        "language": "python",
        "days_analyzed": 30,
        "data_points": 2,
        "throughput": {"average": 15.0, "median": 15.0, "trend": "improving"},
        "memory": {"average_delta": 6.0, "median_delta": 6.0, "trend": "improving"},
    }

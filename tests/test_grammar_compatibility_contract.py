"""Observable compatibility results and local grammar selection."""

from dataclasses import asdict
import importlib.util
import shutil
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
    CompatibilityResult,
    GrammarTester,
    SelectionCriterion,
    SmartSelector,
    TestResult as GrammarTestResult,
)
from chunker.grammar_management.core import (
    GrammarManager,
    GrammarValidator,
    load_compiled_grammar,
)


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


def test_error_pattern_analysis_counts_real_python_parse_failures(
    tmp_path: Path, monkeypatch
) -> None:
    valid = (ROOT / "tests/fixtures/boundary_ir/repos/python/app/service.py").read_text(
        encoding="utf-8"
    )
    samples = [valid, valid + "\ndef broken(\n", valid + "\nclass Broken(:\n"]
    parser = get_parser("python")
    assert not parser.parse(samples[0].encode()).root_node.has_error
    assert all(
        parser.parse(sample.encode()).root_node.has_error for sample in samples[1:]
    )

    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    manager = GrammarManager(
        user_dir=tmp_path / "user",
        package_dir=tmp_path / "package",
        cache_dir=tmp_path / "cache",
    )
    tester = GrammarTester(manager, GrammarValidator(tmp_path / "validation"))
    analysis = tester.analyze_error_patterns("python", samples)

    assert analysis["language"] == "python"
    assert analysis["total_samples"] == 3
    assert analysis["successful_parses"] == 1
    assert analysis["failed_parses"] == 2
    assert analysis["failure_rate"] == pytest.approx(2 / 3)
    assert analysis["error_patterns"] == {"syntax_error": 2}
    assert analysis["common_errors"] == [("syntax_error", 2)]
    assert not home.exists()


def test_comprehensive_syntax_result_follows_real_parse_outcome(
    tmp_path: Path, monkeypatch
) -> None:
    source = (
        ROOT / "tests/fixtures/boundary_ir/repos/python/app/service.py"
    ).read_text(encoding="utf-8")
    malformed = source + "\ndef broken(\n"
    parser = get_parser("python")
    assert not parser.parse(source.encode()).root_node.has_error
    assert parser.parse(malformed.encode()).root_node.has_error

    native_spec = importlib.util.find_spec("tree_sitter_language_pack._native")
    assert native_spec is not None and native_spec.origin is not None
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    user_dir = tmp_path / "user"
    user_dir.mkdir()
    shutil.copyfile(native_spec.origin, user_dir / "libpython.so")
    manager = GrammarManager(
        user_dir=user_dir,
        package_dir=tmp_path / "package",
        cache_dir=tmp_path / "cache",
    )
    tester = GrammarTester(manager, GrammarValidator(tmp_path / "validation"))

    tester.test_suites["python"] = [source]
    accepted = tester.run_comprehensive_test("python", ["syntax"])
    assert accepted.success is True
    assert accepted.sample_results[0]["success"] is True
    assert accepted.sample_results[0]["samples_tested"] == 1
    assert accepted.sample_results[0]["errors"] == []

    tester.test_suites["python"] = [source, malformed]
    rejected = tester.run_comprehensive_test("python", ["syntax"])
    assert rejected.success is False
    assert rejected.sample_results[0]["success"] is False
    assert rejected.sample_results[0]["samples_tested"] == 2
    assert rejected.sample_results[0]["errors"] == [
        "Sample 2: Syntax error in parse tree"
    ]
    assert not home.exists()


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
        ("python", 1, 20.0, 4.0),
        ("javascript", 1.5, 100.0, 99.0),
        ("python", 2, 10.0, 8.0),
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


def test_database_stats_count_persisted_parse_records_and_date_span(
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

    database_path = tmp_path / "stats.db"
    database = CompatibilityDatabase(database_path)
    now = time.time()
    oldest = now - 3 * 24 * 60 * 60
    newest = now - 24 * 60 * 60
    for language, timestamp in (("python", oldest), ("javascript", newest)):
        database.store_compatibility_result(
            CompatibilityResult(
                language=language,
                grammar_version="pinned",
                language_version=None,
                level=CompatibilityLevel.COMPATIBLE,
                score=1.0,
                test_results={"parsed": parsed[language]},
                timestamp=timestamp,
            )
        )
    database.store_test_result(
        GrammarTestResult(
            language="python",
            grammar_version="pinned",
            test_type="parse",
            success=True,
            duration=0.1,
            sample_results=[parsed["python"]],
            timestamp=now,
        )
    )

    stats = CompatibilityDatabase(database_path).get_database_stats()
    assert stats["compatibility_results"] == 2
    assert stats["test_results"] == 1
    assert stats["grammar_metadata"] == 0
    assert stats["database_size_mb"] > 0
    assert stats["oldest_record"] == oldest
    assert stats["newest_record"] == newest
    assert stats["data_span_days"] == pytest.approx(2)

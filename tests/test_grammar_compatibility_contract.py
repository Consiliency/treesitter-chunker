"""Observable compatibility results and local grammar selection."""

from dataclasses import asdict
import subprocess
import sys
from pathlib import Path

import pytest

from chunker import get_parser
from chunker.grammar_management.compatibility import (
    CompatibilityChecker,
    CompatibilityDatabase,
    CompatibilityLevel,
    SelectionCriterion,
    SmartSelector,
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

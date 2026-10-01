"""Selection checks each local grammar artifact on the pinned runtime."""

import subprocess
import sys
from pathlib import Path

import pytest

from chunker.grammar_management.compatibility import (
    CompatibilityChecker,
    CompatibilityDatabase,
    CompatibilityLevel,
    SelectionCriterion,
    SmartSelector,
)
from chunker.grammar_management.core import GrammarManager, load_compiled_grammar


FIXTURE = (
    Path(__file__).parent.parent
    / "packages/baml-grammar/tests/fixtures/declarations.baml"
)


def test_selector_prefers_compatible_candidate_and_keeps_canonical_history(
    tmp_path: Path, monkeypatch
) -> None:
    if sys.platform != "linux":
        pytest.skip("Local shared-library build is Linux-only")

    source = FIXTURE.read_text(encoding="utf-8")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))

    user_dir = tmp_path / "user"
    package_dir = tmp_path / "package"
    user_dir.mkdir()
    package_dir.mkdir()
    user_library = user_dir / "libbaml.so"
    user_library.touch()
    package_library = package_dir / "libbaml.so"
    grammar_src = Path(__file__).parent.parent / "packages/baml-grammar/src"
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
    tree = load_compiled_grammar(package_library, "baml").parse(source.encode("utf-8"))
    assert tree.root_node.type == "source_file"
    assert not tree.root_node.has_error

    manager = GrammarManager(
        user_dir=user_dir,
        package_dir=package_dir,
        cache_dir=tmp_path / "grammar-cache",
    )
    database = CompatibilityDatabase(tmp_path / "compat.db")
    checker = CompatibilityChecker(manager, database)

    canonical = checker.check_compatibility("baml", code_samples=[source])
    assert canonical.level == CompatibilityLevel.INCOMPATIBLE
    assert canonical.score == 0.0
    assert database.get_compatibility_result("baml", "unknown") is not None

    candidate = checker.check_compatibility(
        "baml", code_samples=[source], grammar_path=package_library
    )
    assert candidate.level != CompatibilityLevel.INCOMPATIBLE
    assert candidate.score > 0.0
    assert candidate.test_results is not None
    assert candidate.test_results["success_rate"] == 1.0
    assert (
        database.get_compatibility_result("baml", "unknown").level
        == CompatibilityLevel.INCOMPATIBLE
    )

    selected = SmartSelector(manager, checker, database).select_best_grammar(
        "baml", criteria_weights={SelectionCriterion.COMPATIBILITY: 1.0}
    )
    assert selected is not None
    assert selected.grammar_path == package_library
    assert selected.compatibility_score > 0.0

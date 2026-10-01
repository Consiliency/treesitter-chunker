"""Selection checks each local grammar artifact on the pinned runtime."""

import shutil
from pathlib import Path

import pytest
from tree_sitter_language_pack import cache_dir as pack_cache_dir

from chunker import get_parser
from chunker.grammar_management.compatibility import (
    CompatibilityChecker,
    CompatibilityDatabase,
    CompatibilityLevel,
    SelectionCriterion,
    SmartSelector,
)
from chunker.grammar_management.core import GrammarManager


FIXTURE = Path(__file__).parent / "fixtures/boundary_ir/repos/python/app/service.py"


def test_selector_prefers_compatible_candidate_and_keeps_canonical_history(
    tmp_path: Path, monkeypatch
) -> None:
    source = FIXTURE.read_text(encoding="utf-8")
    tree = get_parser("python").parse(source.encode("utf-8"))
    assert tree.root_node.type == "module"
    assert not tree.root_node.has_error

    native_library = Path(pack_cache_dir()) / "libtree_sitter_python.so"
    if not native_library.exists():
        pytest.skip("Pinned pack does not expose a Linux grammar library")

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))

    user_dir = tmp_path / "user"
    package_dir = tmp_path / "package"
    user_dir.mkdir()
    package_dir.mkdir()
    user_library = user_dir / "libpython.so"
    user_library.touch()
    package_library = package_dir / "libpython.so"
    shutil.copyfile(native_library, package_library)

    manager = GrammarManager(
        user_dir=user_dir,
        package_dir=package_dir,
        cache_dir=tmp_path / "grammar-cache",
    )
    database = CompatibilityDatabase(tmp_path / "compat.db")
    checker = CompatibilityChecker(manager, database)

    canonical = checker.check_compatibility("python", code_samples=[source])
    assert canonical.level == CompatibilityLevel.INCOMPATIBLE
    assert canonical.score == 0.0
    assert database.get_compatibility_result("python", "unknown") is not None

    candidate = checker.check_compatibility(
        "python", code_samples=[source], grammar_path=package_library
    )
    assert candidate.level == CompatibilityLevel.COMPATIBLE
    assert candidate.score > 0.0
    assert candidate.test_results is not None
    assert candidate.test_results["success_rate"] == 1.0
    assert (
        database.get_compatibility_result("python", "unknown").level
        == CompatibilityLevel.INCOMPATIBLE
    )

    selected = SmartSelector(manager, checker, database).select_best_grammar(
        "python", criteria_weights={SelectionCriterion.COMPATIBILITY: 1.0}
    )
    assert selected is not None
    assert selected.grammar_path == package_library
    assert selected.compatibility_score > 0.0

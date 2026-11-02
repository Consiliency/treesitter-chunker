"""Each local grammar candidate carries its own install record (treesitter-chunker#134).

The installer keeps one record per language and the record names the artifact
it describes (``install_path``). Selection must attribute that version and
metadata to that artifact only, and group candidates only when they share a
known version. Named mutations: ``M134-shared-record`` (give every artifact
the language's record, the old behavior), ``M134-group-unknown`` (group
``unknown`` versions together), ``M134-plain-equality`` (compare the paths
with ``==``), ``M134-fallback-false`` (no resolved-path fallback for a missing
record path) and ``M134-valueerror-escapes`` (a corrupt record path hides every
candidate).
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import pytest

from chunker.grammar_management.compatibility import (
    CompatibilityChecker,
    SelectionCriterion,
    SmartSelector,
)
from chunker.grammar_management.core import (
    GrammarManager,
    GrammarPriority,
    InstallationInfo,
    load_compiled_grammar,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "packages/baml-grammar/tests/fixtures/declarations.baml"
GRAMMAR_SRC = ROOT / "packages/baml-grammar/src"

pytestmark = pytest.mark.skipif(
    sys.platform != "linux",
    reason="The checked-in BAML grammar builds as a Linux shared library",
)


def _build(library: Path) -> None:
    subprocess.run(
        [
            "cc",
            "-shared",
            "-fPIC",
            "-O2",
            "-I",
            str(GRAMMAR_SRC),
            str(GRAMMAR_SRC / "parser.c"),
            "-o",
            str(library),
        ],
        check=True,
        capture_output=True,
    )
    source = FIXTURE.read_bytes()
    tree = load_compiled_grammar(library, "baml").parse(source)
    assert tree.root_node.type == "source_file"
    assert not tree.root_node.has_error


@pytest.fixture
def artifacts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Real USER and PACKAGE BAML artifacts in an isolated grammar manager."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    user_dir = tmp_path / "user"
    package_dir = tmp_path / "package"
    user_dir.mkdir()
    package_dir.mkdir()
    user_library = user_dir / "libbaml.so"
    package_library = package_dir / "libbaml.so"
    _build(user_library)
    _build(package_library)
    manager = GrammarManager(
        user_dir=user_dir, package_dir=package_dir, cache_dir=tmp_path / "cache"
    )
    selector = SmartSelector(manager, CompatibilityChecker(manager))
    return manager, selector, user_library, package_library


def _record(
    manager: GrammarManager, path: Path, version: str, parse_time: float
) -> dict:
    metadata = {
        "performance": {"parse_time": parse_time},
        "query_support": True,
        "source": str(path),
    }
    manager._installer._save_installation_info(
        "baml",
        InstallationInfo(
            version=version,
            install_date=time.time(),
            install_path=path,
            source_url="https://example.invalid/tree-sitter-baml",
            priority=GrammarPriority.USER,
            metadata=metadata,
        ),
    )
    return metadata


def _by_priority(selector: SmartSelector) -> dict[GrammarPriority, object]:
    candidates = selector._discover_candidates("baml")
    assert len(candidates) == 2
    return {candidate.priority: candidate for candidate in candidates}


@pytest.mark.parametrize("owner", [GrammarPriority.USER, GrammarPriority.PACKAGE])
def test_install_record_describes_only_its_own_artifact(artifacts, owner) -> None:
    manager, selector, user_library, package_library = artifacts
    owned = user_library if owner is GrammarPriority.USER else package_library
    metadata = _record(manager, owned, "0.2.0", 0.05)

    candidates = _by_priority(selector)
    recorded = candidates[owner]
    other = candidates[
        (
            GrammarPriority.PACKAGE
            if owner is GrammarPriority.USER
            else GrammarPriority.USER
        )
    ]
    assert recorded.grammar_path == owned
    assert recorded.version == "0.2.0"
    assert recorded.metadata == metadata
    assert other.grammar_path != owned
    assert other.version == "unknown"
    assert other.metadata == {}

    # Scores follow each artifact's own metadata.
    assert selector._score_performance(recorded) == 1.0
    assert selector._score_performance(other) == 0.5
    assert selector._score_features(recorded) == 0.25
    assert selector._score_features(other) == 0.0

    # Different versions are not a conflict: both survive.
    resolved = selector._resolve_conflicts(list(candidates.values()))
    assert {c.grammar_path for c in resolved} == {user_library, package_library}


def test_record_for_another_path_attaches_to_no_candidate(artifacts, tmp_path) -> None:
    manager, selector, user_library, package_library = artifacts
    _record(manager, tmp_path / "elsewhere" / "libbaml.so", "0.3.0", 0.05)
    candidates = _by_priority(selector)
    assert all(c.version == "unknown" for c in candidates.values())
    assert all(c.metadata == {} for c in candidates.values())


def test_unknown_versions_are_not_grouped_as_conflicts(artifacts) -> None:
    _manager, selector, user_library, package_library = artifacts
    candidates = selector._discover_candidates("baml")
    assert [c.version for c in candidates] == ["unknown", "unknown"]
    resolved = selector._resolve_conflicts(candidates)
    assert {c.grammar_path for c in resolved} == {user_library, package_library}


def test_true_same_version_conflict_still_groups(artifacts) -> None:
    _manager, selector, user_library, package_library = artifacts
    candidates = selector._discover_candidates("baml")
    for candidate in candidates:
        candidate.version = "0.2.0"
        candidate.overall_score = 0.5
    resolved = selector._resolve_conflicts(candidates)
    # Equal scores: the source priority breaks the tie.
    assert [c.grammar_path for c in resolved] == [user_library]


def test_selection_returns_a_real_attributed_artifact(artifacts) -> None:
    manager, selector, user_library, _package_library = artifacts
    _record(manager, user_library, "0.2.0", 0.05)
    selected = selector.select_best_grammar(
        "baml", criteria_weights={SelectionCriterion.PERFORMANCE: 1.0}
    )
    assert selected is not None
    assert selected.grammar_path == user_library
    assert selected.version == "0.2.0"
    assert selected.performance_score == 1.0


@pytest.mark.parametrize(
    "spelling",
    ["dot-dot", "symlinked-dir", "missing-segment"],
)
def test_record_path_spellings_name_the_same_artifact(
    artifacts, tmp_path, spelling
) -> None:
    """The record attaches by file identity, not by path text."""
    manager, selector, user_library, package_library = artifacts
    user_dir = user_library.parent
    if spelling == "dot-dot":
        recorded = user_dir / ".." / user_dir.name / user_library.name
    elif spelling == "symlinked-dir":
        link = tmp_path / "linked-user"
        link.symlink_to(user_dir, target_is_directory=True)
        recorded = link / user_library.name
    else:
        # The record's path does not exist as written ("gone" is missing),
        # so only the resolved-location fallback can match it.
        recorded = user_dir / "gone" / ".." / user_library.name
        assert not recorded.exists()
    assert recorded != user_library
    _record(manager, recorded, "0.2.0", 0.05)
    candidates = _by_priority(selector)
    assert candidates[GrammarPriority.USER].version == "0.2.0"
    assert candidates[GrammarPriority.PACKAGE].version == "unknown"


def test_corrupt_record_path_attaches_to_no_candidate(artifacts) -> None:
    manager, selector, user_library, package_library = artifacts
    _record(manager, Path(str(user_library) + "\x00corrupt"), "0.2.0", 0.05)
    candidates = _by_priority(selector)
    assert {c.grammar_path for c in candidates.values()} == {
        user_library,
        package_library,
    }
    assert all(c.version == "unknown" for c in candidates.values())

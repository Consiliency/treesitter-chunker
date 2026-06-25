"""Smoke-tier coverage gate across the entire tree-sitter-language-pack.

This complements -- does not duplicate -- the deep golden determinism gate
(``tests/test_boundary_ir_golden_snapshots.py`` + ``test_boundary_ir_determinism``),
which holds 12 languages to byte-level goldens. This gate is the *comprehensive*
tier: every pack language must keep loading under the pin, and the per-language
coverage classification must match the committed
``docs/language-coverage.json`` oracle.

Why diff-against-committed rather than hand-written asserts: the committed JSON
is both the published coverage report *and* the test oracle, so they can never
drift apart. The diff catches regressions in BOTH directions -- a language that
stops loading (the C#/ABI-15 class) AND a language that newly gains or loses an
extraction surface. ``scripts/regenerate_language_coverage.py`` is the one
sanctioned way to update the oracle; an unintended change shows up as a JSON
diff in review.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.boundary_ir_conformance import assert_grammar_runtime_pins
from tests.language_smoke import (
    EMPTY,
    EXTRACTION_GAP,
    LOAD_ONLY,
    LOADS,
    RICH,
    SPARSE,
    compute_coverage,
    load_language,
    pack_languages,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
COVERAGE_JSON = REPO_ROOT / "docs" / "language-coverage.json"


def _committed_coverage() -> dict:
    return json.loads(COVERAGE_JSON.read_text(encoding="utf-8"))


def test_grammar_runtime_pins_held() -> None:
    """Fail closed if the ABI-paired stack drifted off-pin before anything else."""
    assert_grammar_runtime_pins()


def test_pack_pinned_exactly_at_committed_version() -> None:
    """Guard the diff-against-committed oracle against pack patch float.

    The committed coverage JSON's per-language ``node_count`` / ``kinds`` are
    baked against the EXACT pack version the report was generated on. The
    pyproject range (``>=0.9,<1.0``) and ``assert_grammar_runtime_pins`` would
    both stay green on a future ``0.9.x`` whose grammars shifted, turning the
    coverage diff red with a confusing message. Assert the exact committed pack
    version here so any float fails loudly with a clear cause: regenerate the
    oracle on the new pin, or hold the pack.
    """
    from importlib import metadata

    committed_pack = _committed_coverage()["pins"]["tree_sitter_language_pack"]
    expected = committed_pack.lstrip("=")
    installed = metadata.version("tree-sitter-language-pack")
    assert installed == expected, (
        f"tree-sitter-language-pack=={installed} but the committed coverage "
        f"oracle was baked against {expected}. The coverage JSON's per-language "
        "node_count/kinds are version-exact; a different 0.9.x can shift them. "
        "Regenerate via scripts/regenerate_language_coverage.py on the new pin "
        "(and review the diff), or hold the pack at the committed version."
    )


def test_coverage_report_is_committed() -> None:
    """The published coverage report must exist (it is the test oracle)."""
    assert COVERAGE_JSON.exists(), (
        "docs/language-coverage.json is missing. Run "
        "scripts/regenerate_language_coverage.py on the pinned stack."
    )


@pytest.mark.parametrize("language", pack_languages())
def test_every_pack_language_loads(language: str) -> None:
    """Comprehensive LOAD smoke: every pack grammar loads + parses under the pin.

    This is the forward-drift tripwire: a future ABI break that silently breaks
    a language (the C#/ABI-15 failure mode) turns this RED instead of passing
    silently.
    """
    status, error = load_language(language)
    assert status == LOADS, f"{language} failed to load under the pinned stack: {error}"


def test_coverage_matches_committed_oracle() -> None:
    """Live sweep must match the committed coverage JSON (drift both directions).

    A language that stops loading, or one that newly gains/loses an extraction
    surface, changes the live computation and fails this diff. Regenerate the
    oracle deliberately via scripts/regenerate_language_coverage.py and review
    the JSON diff in the PR.
    """
    committed = _committed_coverage()
    live = compute_coverage()

    # Normalize the volatile pins block exactly as the regenerate script does, so
    # a patch bump inside the pinned range does not fail the gate.
    live["pins"] = {
        "tree_sitter": ">=0.25,<0.26",
        "tree_sitter_language_pack": "==0.9.0",
    }

    assert live["summary"] == committed["summary"], (
        "Coverage summary drifted from the committed oracle. "
        "Regenerate via scripts/regenerate_language_coverage.py and review."
    )
    assert live["languages"] == committed["languages"], (
        "Per-language coverage drifted from the committed oracle. "
        "Regenerate via scripts/regenerate_language_coverage.py and review the diff."
    )


def test_extraction_sampled_languages_nonempty() -> None:
    """Every RICH/SPARSE language must keep emitting >= 1 boundary kind.

    These are the languages with a curated valid sample and a real boundary
    surface; them going EMPTY is a regression (ABI drift / the C#-class silent
    break). EMPTY / EXTRACTION_GAP / LOAD_ONLY languages are intentionally NOT
    asserted non-empty here -- asserting a boundary surface that does not exist
    today would be asserting a feature, not guarding a regression; the
    diff-against-committed oracle already tracks those.
    """
    committed = _committed_coverage()["languages"]
    sampled = {
        name: rec
        for name, rec in committed.items()
        if rec["extraction"] in (RICH, SPARSE)
    }
    assert sampled, "expected at least one extraction-verified language"
    for name, rec in sorted(sampled.items()):
        assert rec["node_count"] >= 1, f"{name} unexpectedly emits zero nodes"
        assert rec["kinds"], f"{name} unexpectedly emits zero kinds"


def test_taxonomy_buckets_are_disjoint_and_total() -> None:
    """Sanity: every language carries exactly one extraction classification."""
    committed = _committed_coverage()
    valid = {RICH, SPARSE, EMPTY, EXTRACTION_GAP, LOAD_ONLY}
    for name, rec in committed["languages"].items():
        assert rec["extraction"] in valid, f"{name} has unknown class {rec}"

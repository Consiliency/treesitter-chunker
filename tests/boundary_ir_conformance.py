"""Shared Boundary IR conformance helpers."""

from __future__ import annotations

from copy import deepcopy
from importlib import metadata
from pathlib import Path
from typing import Any

import pytest

from chunker.boundary import dumps_boundary_ir, extract_boundary_ir
from chunker.boundary.types import METRIC_KEYS, TIMING_KEYS, TOP_LEVEL_KEYS
from chunker._internal.pack_pin import resolve_pack_pin
from chunker.parser import list_languages

P0_BOUNDARY_LANGUAGES = ("python", "javascript", "typescript", "go")

# The full set of languages the determinism gate holds to a committed golden +
# non-empty-extraction guarantee. P0 is the richer semantic-parity contract
# (manifest.json); this superset is the byte-level / grammar-health contract.
#
# csharp is TURNKEY as of the tree_sitter 0.25 runtime bump: the language-pack
# 0.9.0 C# grammar is ABI-15, which the old 0.24 runtime rejected (silently
# emitting {} / zero boundaries). The 0.25 runtime loads ABI 13-15, so C# now
# extracts rich nodes out of the box with no grammar pin / uv override. The
# canonical key is ``csharp`` (NOT ``c_sharp`` -- that alias yields zero nodes);
# see EXTENSION_MAP in chunker/auto.py (.cs -> csharp).
SUPPORTED_BOUNDARY_LANGUAGES = (
    "python",
    "javascript",
    "typescript",
    "go",
    "java",
    "cpp",
    "c",
    "ruby",
    "kotlin",
    "swift",
    "php",
    "csharp",
)

FIXTURE_ROOT = Path("tests/fixtures/boundary_ir/repos")
GOLDEN_ROOT = Path("tests/fixtures/boundary_ir/golden")
GOLDEN_TOOL_VERSION = "<tool-version>"

# Pinned grammar/runtime ranges. These MUST mirror pyproject.toml's dependency
# pins. tree_sitter and tree-sitter-language-pack are ABI-paired, but the
# coupling is asymmetric: the 0.25 runtime is ABI-additive (loads ABI 13-15, so
# bumping the runtime under a HELD pack is byte-stable), whereas bumping the PACK
# floats its pre-compiled grammars -- pack >=1.x ships a newer Python grammar
# that changes docstring node handling and silently drops the ``docstring:``
# line from semantic_text. That pack-float is the real cause of the historically
# observed "docstring drop", NOT the runtime bump. The assertion below fails
# closed if an unintended transitive bump moves either dist outside its range, so
# pack stays pinned at 0.9.x and the IR stays byte-stable.
PINNED_TREE_SITTER = (("0.25", "0.26"), "tree_sitter")
PINNED_LANGUAGE_PACK = (resolve_pack_pin(), "tree-sitter-language-pack")

FILE_KEYS = (
    "id",
    "path",
    "language",
    "content_hash",
    "parser",
    "status",
    "diagnostics",
)
NODE_KEYS = (
    "id",
    "identity",
    "definition_id",
    "node_id",
    "symbol_id",
    "file_id",
    "path",
    "language",
    "kind",
    "symbol",
    "qualified_name",
    "semantic_path",
    "signature",
    "span",
    "parent",
    "relationships",
    "metadata",
    "provenance",
)
EDGE_KEYS = (
    "id",
    "source",
    "target",
    "type",
    "resolution",
    "reference",
    "candidates",
    "location",
    "provenance",
    "metadata",
)
DIAGNOSTIC_KEYS = (
    "id",
    "severity",
    "code",
    "message",
    "path",
    "location",
    "stage",
    "details",
)
RUN_KEYS = (
    "tool",
    "tool_version",
    "root",
    "created_at",
    "canonical",
    "options",
    "timings",
)
RUN_OPTION_KEYS = (
    "include_retrieval_metadata",
    "language",
    "resolution_mode",
    "fail_fast",
    "include_timings",
)
SOURCE_KEYS = ("kind", "path")
SPAN_KEYS = ("byte_end", "byte_start", "end_line", "start_line")
LOCATION_KEYS = ("byte_end", "byte_start", "end_line", "start_line")


def fixture_path(language: str) -> Path:
    """Return the repo-relative fixture root for a supported language."""
    if language not in SUPPORTED_BOUNDARY_LANGUAGES:
        msg = f"Unsupported Boundary IR language: {language}"
        raise ValueError(msg)
    return FIXTURE_ROOT / language


def grammar_available(language: str) -> bool:
    """Return whether the local tree-sitter grammar is available."""
    return language in list_languages()


def skip_if_grammar_unavailable(language: str) -> None:
    """Skip the current test when an optional local grammar is unavailable."""
    if not grammar_available(language):
        pytest.skip(f"{language} grammar is not available")


def extract_fixture_ir(language: str) -> dict[str, Any]:
    """Extract canonical Boundary IR from a supported fixture repository.

    The determinism gate must NOT silently skip a supported language when its
    grammar is missing -- a missing grammar is exactly the drift we want to fail
    loudly on. So this calls extraction directly. ``skip_if_grammar_unavailable``
    remains available for non-gate tests that opt into skipping.
    """
    return extract_boundary_ir(fixture_path(language), language)


def assert_extraction_nonempty(language: str) -> None:
    """Fail loudly if a supported language extracts zero boundary nodes.

    Guards the silent-``{}`` case: a grammar can be "available" yet emit nothing
    (the C#/ABI-15 failure mode), which dict/golden equality alone would not
    catch if the golden were also empty. Requiring >= 1 node makes a broken or
    ABI-mismatched grammar a hard CI failure instead of a silent gap.
    """
    ir = extract_fixture_ir(language)
    assert len(ir["nodes"]) >= 1, (
        f"{language} extracted zero boundary nodes from its fixture repo; "
        "the grammar is missing, ABI-mismatched, or emitting an empty IR. "
        "This is the silent-empty failure mode the determinism gate exists to "
        "catch -- investigate the grammar/runtime pairing, do not relax the gate."
    )


def _version_in_range(version: str, low: str, high: str) -> bool:
    """Return whether ``low <= version < high`` using PEP 440 ordering."""
    from packaging.version import Version

    return Version(low) <= Version(version) < Version(high)


def assert_grammar_runtime_pins() -> None:
    """Fail closed if the installed grammar/runtime versions drift off-pin.

    Reads the *installed* distribution versions and checks each against the
    range pinned in pyproject.toml. An unintended transitive bump (e.g. the
    language-pack drifting 0.9 -> 1.x, which floats a newer Python grammar that
    drops docstrings from semantic_text) trips this guard rather than silently
    corrupting the IR.
    """
    for (low, high), dist in (PINNED_TREE_SITTER, PINNED_LANGUAGE_PACK):
        installed = metadata.version(dist)
        assert _version_in_range(installed, low, high), (
            f"{dist}=={installed} is outside the pinned range >={low},<{high}. "
            "An unintended transitive bump tripped the determinism gate. "
            "tree_sitter and tree-sitter-language-pack are ABI-paired; mixing "
            "versions silently breaks Boundary IR extraction. Re-pin in "
            "pyproject.toml deliberately and regenerate goldens, or roll back "
            "the bump -- do not weaken this assertion."
        )


def fixture_boundary_json_bytes(language: str) -> bytes:
    """Return canonical Boundary IR JSON bytes for a P0 fixture repository."""
    return dumps_boundary_ir(extract_fixture_ir(language)).encode("utf-8")


def normalize_ir_for_golden(ir: dict[str, Any]) -> dict[str, Any]:
    """Normalize only the tool version for checked golden snapshots."""
    normalized = deepcopy(ir)
    normalized["run"]["tool_version"] = GOLDEN_TOOL_VERSION
    return normalized


def _assert_keys(record: dict[str, Any], keys: tuple[str, ...], label: str) -> None:
    assert set(record) == set(keys), f"{label} keys changed: {sorted(record)}"


def assert_required_fields(ir: dict[str, Any]) -> None:
    """Assert that a Boundary IR document has every frozen required field."""
    _assert_keys(ir, TOP_LEVEL_KEYS, "top-level")
    _assert_keys(ir["source"], SOURCE_KEYS, "source")
    _assert_keys(ir["metrics"], METRIC_KEYS, "metrics")
    _assert_keys(ir["run"], RUN_KEYS, "run")
    _assert_keys(ir["run"]["options"], RUN_OPTION_KEYS, "run options")
    _assert_keys(ir["run"]["timings"], TIMING_KEYS, "run timings")

    for file_record in ir["files"]:
        _assert_keys(file_record, FILE_KEYS, "file")

    for node in ir["nodes"]:
        _assert_keys(node, NODE_KEYS, "node")
        _assert_keys(node["span"], SPAN_KEYS, "node span")

    for edge in ir["edges"]:
        _assert_keys(edge, EDGE_KEYS, "edge")
        _assert_keys(edge["location"], LOCATION_KEYS, "edge location")

    for diagnostic in ir["diagnostics"]:
        _assert_keys(diagnostic, DIAGNOSTIC_KEYS, "diagnostic")

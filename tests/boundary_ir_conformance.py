"""Shared Boundary IR conformance helpers."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from chunker.boundary import dumps_boundary_ir, extract_boundary_ir
from chunker.boundary.types import METRIC_KEYS, TIMING_KEYS, TOP_LEVEL_KEYS
from chunker.parser import list_languages

P0_BOUNDARY_LANGUAGES = ("python", "javascript", "typescript", "go")
FIXTURE_ROOT = Path("tests/fixtures/boundary_ir/repos")
GOLDEN_ROOT = Path("tests/fixtures/boundary_ir/golden")
GOLDEN_TOOL_VERSION = "<tool-version>"

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
    """Return the repo-relative fixture root for a P0 language."""
    if language not in P0_BOUNDARY_LANGUAGES:
        msg = f"Unsupported P0 Boundary IR language: {language}"
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
    """Extract canonical Boundary IR from a P0 fixture repository."""
    if language == "go":
        skip_if_grammar_unavailable(language)
    return extract_boundary_ir(fixture_path(language), language)


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

"""Lightweight Boundary IR types and constants."""

from __future__ import annotations

from typing import Any, Literal, TypeAlias

from chunker.types import (
    RESOLUTION_MODES,
    RESOLUTION_STATUSES,
    ResolutionMode,
    ResolutionStatus,
)

BoundaryIR: TypeAlias = dict[str, Any]
BoundaryRecord: TypeAlias = dict[str, Any]
SemanticEdgeSource: TypeAlias = Literal["semantic"]

BOUNDARY_IR_SCHEMA_VERSION = "1.0"
BOUNDARY_IR_SEMANTIC_SCHEMA_VERSION = "1.1"
SEMANTIC_RESOLVER_API_VERSION = "1.0"
BOUNDARY_CACHE_VERSION = "1"
BOUNDARY_CACHE_KEY_PREFIX = "boundary:v1:"
BOUNDARY_CACHE_KEY_FIELDS = (
    "path",
    "content_hash",
    "language",
    "grammar_version",
    "tool_version",
    "schema_version",
    "resolution_mode",
    "fail_fast",
    "include_retrieval_metadata",
)
BOUNDARY_CACHE_EXCLUDED_OPTION_FIELDS = (
    "created_at",
    "canonical",
    "include_timings",
    "incremental",
    "cache_dir",
    "force_rebuild",
)
SEMANTIC_EDGE_SOURCES: tuple[SemanticEdgeSource, ...] = ("semantic",)

TOP_LEVEL_KEYS = (
    "schema_version",
    "source",
    "files",
    "nodes",
    "edges",
    "diagnostics",
    "metrics",
    "run",
)

METRIC_KEYS = (
    "files_total",
    "files_processed",
    "files_parsed",
    "files_skipped",
    "files_failed",
    "nodes_total",
    "edges_total",
    "diagnostics_total",
    "resolved_edges",
    "ambiguous_edges",
    "unresolved_edges",
    "parse_failures",
    "metadata_failures",
    "graph_failures",
    "serialization_failures",
    "failure_buckets",
)

TIMING_KEYS = (
    "parse_ms",
    "metadata_normalization_ms",
    "graph_assembly_ms",
    "resolution_ms",
    "serialization_ms",
    "total_ms",
)

DIAGNOSTIC_STAGES = (
    "discovery",
    "parse",
    "metadata",
    "graph",
    "resolution",
    "semantic",
    "serialization",
)

DIAGNOSTIC_SEVERITIES = ("info", "warning", "error")

FILE_STATUSES = ("parsed", "skipped", "error")

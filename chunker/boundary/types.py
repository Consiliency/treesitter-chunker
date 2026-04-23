"""Lightweight Boundary IR types and constants."""

from __future__ import annotations

from typing import Any, Literal, TypeAlias

BoundaryIR: TypeAlias = dict[str, Any]
BoundaryRecord: TypeAlias = dict[str, Any]
ResolutionStatus: TypeAlias = Literal["resolved", "ambiguous", "unresolved"]
ResolutionMode: TypeAlias = Literal["strict", "permissive"]

BOUNDARY_IR_SCHEMA_VERSION = "1.0"
RESOLUTION_STATUSES: tuple[ResolutionStatus, ...] = (
    "resolved",
    "ambiguous",
    "unresolved",
)
RESOLUTION_MODES: tuple[ResolutionMode, ...] = ("strict", "permissive")

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
    "serialization",
)

DIAGNOSTIC_SEVERITIES = ("info", "warning", "error")

FILE_STATUSES = ("parsed", "skipped", "error")

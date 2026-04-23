"""Adapter from current extraction outputs to Boundary IR."""

from __future__ import annotations

import hashlib
import json
import time
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

from chunker.auto import ZeroConfigAPI
from chunker.core import chunk_file
from chunker.symbol_graph import collect_source_files, extract_symbol_graph
from chunker.types import CodeChunk, compute_definition_id, compute_file_id

from .identity import select_node_identity
from .serialization import canonicalize_boundary_ir
from .types import (
    BOUNDARY_IR_SCHEMA_VERSION,
    RESOLUTION_MODES,
    TIMING_KEYS,
    ResolutionMode,
)

try:
    TOOL_VERSION = version("treesitter-chunker")
except PackageNotFoundError:  # pragma: no cover - source tree without install metadata
    TOOL_VERSION = None


def _display_path(file_path: Path, root: Path) -> str:
    base = root if root.is_dir() else root.parent
    try:
        return str(file_path.relative_to(base))
    except ValueError:
        return str(file_path)


def _module_name(display_path: str) -> str:
    path = Path(display_path)
    parts = list(path.parts)
    if parts:
        parts[-1] = Path(parts[-1]).stem
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts) if parts else path.stem


def _detect_language(file_path: Path, fallback: str | None) -> str | None:
    if fallback:
        return fallback.lower()
    return ZeroConfigAPI.EXTENSION_MAP.get(file_path.suffix.lower())


def _content_hash(file_path: Path) -> str:
    return "sha1:" + hashlib.sha1(file_path.read_bytes()).hexdigest()


def _stable_hash(*values: object) -> str:
    seed = "|".join(str(value) for value in values)
    return hashlib.sha1(seed.encode("utf-8")).hexdigest()


def _stable_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _stable_value(value[key]) for key in sorted(value)}
    if isinstance(value, list | tuple | set):
        values = [_stable_value(item) for item in value]
        if all(isinstance(item, str) for item in values):
            return sorted(dict.fromkeys(values))
        return values
    if isinstance(value, str | int | float | bool) or value is None:
        return value
    return str(value)


def _span(chunk: CodeChunk) -> dict[str, int]:
    return {
        "byte_end": chunk.byte_end,
        "byte_start": chunk.byte_start,
        "end_line": chunk.end_line,
        "start_line": chunk.start_line,
    }


def _boundary_kind(chunk: CodeChunk, metadata: dict[str, Any]) -> str:
    if metadata.get("type_kind"):
        return str(metadata["type_kind"])
    if chunk.language == "go" and metadata.get("kind") == "type":
        content = chunk.content or ""
        if " struct " in f" {content} " or content.lstrip().startswith("struct"):
            return "struct"
        if " interface " in f" {content} " or content.lstrip().startswith("interface"):
            return "interface"
    return str(metadata.get("kind") or chunk.node_type)


def _ensure_definition_id(chunk: CodeChunk, display_path: str) -> None:
    if chunk.definition_id or not chunk.qualified_route:
        return
    chunk.definition_id = compute_definition_id(
        display_path,
        chunk.language,
        chunk.qualified_route,
    )


def _node_record(
    chunk: CodeChunk,
    display_path: str,
    file_id: str,
    module_name: str,
) -> dict[str, Any]:
    _ensure_definition_id(chunk, display_path)
    identity = select_node_identity(chunk, module_name)
    metadata = chunk.metadata or {}
    return {
        "id": identity["value"],
        "identity": identity,
        "definition_id": chunk.definition_id or None,
        "node_id": chunk.node_id or None,
        "symbol_id": chunk.symbol_id,
        "file_id": file_id,
        "path": display_path,
        "language": chunk.language,
        "kind": _boundary_kind(chunk, metadata),
        "symbol": metadata.get("symbol"),
        "qualified_name": metadata.get("qualified_name"),
        "semantic_path": metadata.get("semantic_path"),
        "signature": metadata.get("signature_text") or metadata.get("signature"),
        "span": _span(chunk),
        "parent": chunk.parent_chunk_id,
        "relationships": [],
        "metadata": _stable_value(
            {
                "dependencies": metadata.get("dependencies", []),
                "exports": metadata.get("exports", []),
                "imports": metadata.get("imports", []),
                "parent_symbol": metadata.get("parent_symbol"),
                "semantic_text": metadata.get("semantic_text"),
            }
        ),
        "provenance": {
            "extractor": "chunk_file",
            "metadata": "retrieval",
        },
    }


def _add_symbol_indexes(
    indexes: dict[str, str],
    chunk: CodeChunk,
    node: dict[str, Any],
    module_name: str,
) -> None:
    node_id = str(node["id"])
    for value in (
        chunk.definition_id,
        chunk.node_id,
        chunk.symbol_id,
        node.get("definition_id"),
        node.get("node_id"),
        node.get("symbol_id"),
    ):
        if value:
            indexes[str(value)] = node_id
    qualified_name = node.get("qualified_name")
    symbol = node.get("symbol")
    if qualified_name:
        indexes[f"{module_name}:{qualified_name}"] = node_id
        indexes[str(qualified_name)] = node_id
    if symbol:
        indexes[f"{module_name}:{symbol}"] = node_id
        indexes[str(symbol)] = node_id


def _edge_record(
    relationship: dict[str, Any],
    symbol_indexes: dict[str, str],
    resolution_mode: ResolutionMode,
) -> dict[str, Any]:
    source_ref = str(relationship.get("from") or "")
    reference = str(relationship.get("reference") or relationship.get("to") or "")
    target_ref = str(relationship.get("to") or reference)
    source = symbol_indexes.get(source_ref, source_ref)
    is_internal = bool(relationship.get("is_internal"))
    resolution = str(relationship.get("resolution") or "")
    if resolution not in {"resolved", "ambiguous", "unresolved"}:
        resolution = "resolved" if is_internal else "unresolved"
    if resolution == "resolved":
        target = symbol_indexes.get(target_ref, target_ref)
    else:
        target = reference
    raw_candidates = relationship.get("candidates")
    if isinstance(raw_candidates, list):
        candidates = sorted(
            dict.fromkeys(
                symbol_indexes.get(str(candidate), str(candidate))
                for candidate in raw_candidates
                if str(candidate)
            )
        )
    else:
        candidates = [target] if resolution == "resolved" and target else []
    relationship_type = str(relationship.get("type") or "reference")
    line = relationship.get("line")
    location = {
        "byte_end": None,
        "byte_start": None,
        "end_line": line if isinstance(line, int) else None,
        "start_line": line if isinstance(line, int) else None,
    }
    edge_id = (
        "edge:"
        + _stable_hash(
            source,
            target,
            relationship_type,
            reference,
            line,
            relationship.get("file") or "",
        )[:16]
    )
    provenance = {
        "resolver": "extract_symbol_graph",
        "source": "syntax",
        "resolution_mode": resolution_mode,
    }
    if resolution_mode == "strict":
        provenance["enforcement_grade"] = "strict"
    return {
        "id": edge_id,
        "source": source,
        "target": target,
        "type": relationship_type,
        "resolution": resolution,
        "reference": reference,
        "candidates": candidates,
        "location": location,
        "provenance": provenance,
        "metadata": {
            "file": relationship.get("file"),
            "is_internal": is_internal,
        },
    }


def _diagnostic(
    message: str,
    *,
    stage: str,
    code: str,
    path: str | None = None,
    location: dict[str, Any] | None = None,
    details: dict[str, Any] | None = None,
    severity: str = "error",
) -> dict[str, Any]:
    stable_details = _stable_value(details or {})
    stable_location = _stable_value(location)
    seed = json.dumps(
        {
            "stage": stage,
            "code": code,
            "path": path,
            "location": stable_location,
            "message": message,
            "details": stable_details,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return {
        "id": f"diagnostic:{_stable_hash(seed)[:16]}",
        "severity": severity,
        "code": code,
        "message": message,
        "path": path,
        "location": stable_location,
        "stage": stage,
        "details": stable_details,
    }


def _timings(include_timings: bool, spans: dict[str, float]) -> dict[str, float | None]:
    if not include_timings:
        return dict.fromkeys(TIMING_KEYS)
    return {key: round(max(0.0, spans.get(key, 0.0)), 3) for key in TIMING_KEYS}


def _add_duration(spans: dict[str, float], key: str, started_at: float) -> None:
    spans[key] = spans.get(key, 0.0) + (time.perf_counter() - started_at) * 1000


def _failure_buckets(diagnostics: list[dict[str, Any]]) -> dict[str, int]:
    buckets: dict[str, int] = {}
    for diagnostic in diagnostics:
        code = str(diagnostic.get("code") or "")
        if code:
            buckets[code] = buckets.get(code, 0) + 1
    return {key: buckets[key] for key in sorted(buckets)}


def extract_boundary_ir(
    path: str | Path,
    language: str | None = None,
    *,
    canonical: bool = True,
    created_at: str | None = None,
    resolution_mode: ResolutionMode = "strict",
    fail_fast: bool = False,
    include_timings: bool = False,
) -> dict[str, Any]:
    """Extract Boundary IR for a source file or repository."""
    if resolution_mode not in RESOLUTION_MODES:
        msg = f"Unsupported resolution_mode: {resolution_mode}"
        raise ValueError(msg)
    total_started_at = time.perf_counter()
    timing_spans: dict[str, float] = {}
    root = Path(path)
    started_at = time.perf_counter()
    files = collect_source_files(root, language)
    _add_duration(timing_spans, "parse_ms", started_at)
    started_at = time.perf_counter()
    graph = extract_symbol_graph(
        root,
        language,
        resolution_mode=resolution_mode,
        fail_fast=fail_fast,
    )
    _add_duration(timing_spans, "graph_assembly_ms", started_at)
    file_records: list[dict[str, Any]] = []
    node_records: list[dict[str, Any]] = []
    edge_records: list[dict[str, Any]] = []
    diagnostics = [
        _diagnostic(
            str(message),
            stage="graph",
            code="boundary.graph_error",
            details={"source": "extract_symbol_graph"},
        )
        for message in graph.get("errors", [])
    ]
    symbol_indexes: dict[str, str] = {}
    parse_failures = 0
    metadata_failures = 0
    serialization_failures = 0

    for file_path in files:
        display_path = _display_path(file_path, root)
        detected_language = _detect_language(file_path, language)
        file_id = compute_file_id(display_path)
        file_diagnostics: list[str] = []
        status = "parsed"
        chunks: list[CodeChunk] = []
        if detected_language:
            try:
                started_at = time.perf_counter()
                chunks = chunk_file(
                    file_path,
                    detected_language,
                    extract_metadata=True,
                    include_retrieval_metadata=True,
                )
                _add_duration(timing_spans, "parse_ms", started_at)
            except Exception as exc:  # pragma: no cover - parser dependent
                _add_duration(timing_spans, "parse_ms", started_at)
                if fail_fast:
                    raise
                parse_failures += 1
                status = "error"
                diagnostic = _diagnostic(
                    str(exc),
                    stage="parse",
                    code="boundary.parse_error",
                    path=display_path,
                    details={"exception": type(exc).__name__},
                )
                diagnostics.append(diagnostic)
                file_diagnostics.append(str(diagnostic["id"]))
        else:
            status = "skipped"

        module = _module_name(display_path)
        for chunk in chunks:
            try:
                started_at = time.perf_counter()
                node = _node_record(chunk, display_path, file_id, module)
                _add_duration(
                    timing_spans,
                    "metadata_normalization_ms",
                    started_at,
                )
                node_records.append(node)
                _add_symbol_indexes(symbol_indexes, chunk, node, module)
            except Exception as exc:  # pragma: no cover - defensive normalization
                _add_duration(
                    timing_spans,
                    "metadata_normalization_ms",
                    started_at,
                )
                if fail_fast:
                    raise
                metadata_failures += 1
                status = "error"
                diagnostic = _diagnostic(
                    str(exc),
                    stage="metadata",
                    code="boundary.metadata_error",
                    path=display_path,
                    location=_span(chunk),
                    details={"exception": type(exc).__name__},
                )
                diagnostics.append(diagnostic)
                file_diagnostics.append(str(diagnostic["id"]))

        file_records.append(
            {
                "id": file_id,
                "path": display_path,
                "language": detected_language,
                "content_hash": _content_hash(file_path),
                "parser": (
                    f"tree-sitter-{detected_language}" if detected_language else None
                ),
                "status": status,
                "diagnostics": sorted(dict.fromkeys(file_diagnostics)),
            }
        )

    seen_edges: set[str] = set()
    relationships_by_source: dict[str, list[str]] = {}
    started_at = time.perf_counter()
    for relationship in graph.get("relationships", []):
        edge = _edge_record(relationship, symbol_indexes, resolution_mode)
        if edge["id"] in seen_edges:
            continue
        seen_edges.add(edge["id"])
        edge_records.append(edge)
        relationships_by_source.setdefault(str(edge["source"]), []).append(
            str(edge["id"])
        )
    _add_duration(timing_spans, "resolution_ms", started_at)

    for node in node_records:
        node["relationships"] = sorted(
            dict.fromkeys(relationships_by_source.get(str(node["id"]), []))
        )

    resolved_edges = sum(1 for edge in edge_records if edge["resolution"] == "resolved")
    ambiguous_edges = sum(
        1 for edge in edge_records if edge["resolution"] == "ambiguous"
    )
    unresolved_edges = sum(
        1 for edge in edge_records if edge["resolution"] == "unresolved"
    )
    graph_failures = len(graph.get("errors", []))
    failure_buckets = _failure_buckets(diagnostics)
    ir: dict[str, Any] = {
        "schema_version": BOUNDARY_IR_SCHEMA_VERSION,
        "source": {
            "kind": "file" if root.is_file() else "repository",
            "path": str(root),
        },
        "files": file_records,
        "nodes": node_records,
        "edges": edge_records,
        "diagnostics": diagnostics,
        "metrics": {
            "files_total": len(file_records),
            "files_processed": len(file_records),
            "files_parsed": sum(
                1 for item in file_records if item["status"] == "parsed"
            ),
            "files_skipped": sum(
                1 for item in file_records if item["status"] == "skipped"
            ),
            "files_failed": sum(
                1 for item in file_records if item["status"] == "error"
            ),
            "nodes_total": len(node_records),
            "edges_total": len(edge_records),
            "diagnostics_total": len(diagnostics),
            "resolved_edges": resolved_edges,
            "ambiguous_edges": ambiguous_edges,
            "unresolved_edges": unresolved_edges,
            "parse_failures": parse_failures,
            "metadata_failures": metadata_failures,
            "graph_failures": graph_failures,
            "serialization_failures": serialization_failures,
            "failure_buckets": failure_buckets,
        },
        "run": {
            "tool": "treesitter-chunker",
            "tool_version": TOOL_VERSION,
            "root": str(root),
            "created_at": created_at,
            "canonical": canonical,
            "options": {
                "include_retrieval_metadata": True,
                "language": language,
                "resolution_mode": resolution_mode,
                "fail_fast": fail_fast,
                "include_timings": include_timings,
            },
            "timings": {},
        },
    }
    timing_spans["total_ms"] = (time.perf_counter() - total_started_at) * 1000
    started_at = time.perf_counter()
    if canonical:
        try:
            ir["run"]["timings"] = _timings(include_timings, timing_spans)
            canonical_ir = canonicalize_boundary_ir(ir)
            _add_duration(timing_spans, "serialization_ms", started_at)
            timing_spans["total_ms"] = (time.perf_counter() - total_started_at) * 1000
            canonical_ir["run"]["timings"] = _timings(include_timings, timing_spans)
            return canonicalize_boundary_ir(canonical_ir)
        except Exception:
            if fail_fast:
                raise
            serialization_failures += 1
            ir["metrics"]["serialization_failures"] = serialization_failures
            diagnostic = _diagnostic(
                "Boundary IR serialization failed",
                stage="serialization",
                code="boundary.serialization_error",
                details={},
            )
            ir["diagnostics"].append(diagnostic)
            ir["metrics"]["diagnostics_total"] = len(ir["diagnostics"])
            ir["metrics"]["failure_buckets"] = _failure_buckets(ir["diagnostics"])
            ir["run"]["timings"] = _timings(include_timings, timing_spans)
            return ir
    _add_duration(timing_spans, "serialization_ms", started_at)
    timing_spans["total_ms"] = (time.perf_counter() - total_started_at) * 1000
    ir["run"]["timings"] = _timings(include_timings, timing_spans)
    return ir

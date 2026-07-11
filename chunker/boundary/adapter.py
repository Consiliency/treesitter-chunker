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
from chunker.symbol_graph import (
    assemble_symbol_graph,
    collect_source_files,
    extract_symbol_facts_for_file,
    extract_symbol_graph,
)
from chunker.types import CodeChunk, compute_definition_id, compute_file_id

from .cache import (
    BoundaryCacheRecord,
    build_boundary_cache_key,
    load_cache_index,
    load_cache_record,
    prune_cache_record,
    save_cache_index,
    save_cache_record,
)
from .identity import select_node_identity
from .impact import (
    compute_impacted_paths,
    detect_changed_paths,
    normalize_boundary_path,
)
from .serialization import canonicalize_boundary_ir
from .semantic import SemanticEdge, SemanticResolver, SemanticResolverContext
from .types import (
    BOUNDARY_CACHE_KEY_FIELDS,
    BOUNDARY_CACHE_KEY_PREFIX,
    BOUNDARY_IR_SCHEMA_VERSION,
    BOUNDARY_IR_SEMANTIC_SCHEMA_VERSION,
    RESOLUTION_MODES,
    SEMANTIC_RESOLVER_API_VERSION,
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
    if isinstance(value, set):
        # A set is genuinely order-insensitive AND has no source order to
        # preserve, so it is the one collection we must order deterministically
        # here. Stringify-sort to give canon a stable insertion order.
        return sorted(_stable_value(item) for item in value)
    if isinstance(value, list | tuple):
        # canon S4: list/tuple order is preserved ALWAYS. NEVER content-sniff
        # all-string lists into sorted(dict.fromkeys(...)) -- that destroyed
        # order-significant fields (imports) and silently de-duplicated (BUG-1).
        # Order-insensitive fields are sorted at construction / in the serializer.
        return [_stable_value(item) for item in value]
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
    # Always (re)compute from the canonical repo-relative display_path (BUG-3):
    # the chunk may already carry a definition_id computed from a different
    # (e.g. absolute) path, so do NOT early-return when it is already set.
    if not chunk.qualified_route:
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


def _grammar_version(language: str | None) -> str | None:
    if not language:
        return None
    return f"tree-sitter-{language}"


def _cache_dir_for(root: Path, cache_dir: str | Path | None) -> Path:
    if cache_dir is not None:
        return Path(cache_dir)
    digest = hashlib.sha256(str(root.resolve()).encode("utf-8")).hexdigest()[:16]
    return Path.home() / ".cache" / "treesitter-chunker" / "boundary" / digest


def _cache_key_payload(
    *,
    display_path: str,
    content_hash: str,
    language: str | None,
    resolution_mode: ResolutionMode,
    fail_fast: bool,
    semantic_resolvers: tuple[SemanticResolver, ...] | None = None,
    semantic_min_confidence: float = 0.0,
) -> dict[str, Any]:
    semantic_requested = semantic_resolvers is not None
    return {
        "path": normalize_boundary_path(display_path),
        "content_hash": content_hash,
        "language": language,
        "grammar_version": _grammar_version(language),
        "tool_version": TOOL_VERSION,
        "schema_version": (
            BOUNDARY_IR_SEMANTIC_SCHEMA_VERSION
            if semantic_requested
            else BOUNDARY_IR_SCHEMA_VERSION
        ),
        "resolution_mode": resolution_mode,
        "fail_fast": fail_fast,
        "include_retrieval_metadata": True,
        "semantic_schema_version": (
            BOUNDARY_IR_SEMANTIC_SCHEMA_VERSION if semantic_requested else None
        ),
        "semantic_resolvers": (
            _semantic_resolver_fingerprints(semantic_resolvers)
            if semantic_requested
            else None
        ),
        "semantic_min_confidence": (
            semantic_min_confidence if semantic_requested else None
        ),
    }


def _build_boundary_cache_key(payload: dict[str, Any]) -> str:
    if payload.get("semantic_schema_version") is None:
        return build_boundary_cache_key(payload)
    key_payload = {field: payload.get(field) for field in BOUNDARY_CACHE_KEY_FIELDS}
    key_payload.update(
        {
            "semantic_min_confidence": payload.get("semantic_min_confidence"),
            "semantic_resolvers": payload.get("semantic_resolvers"),
            "semantic_schema_version": payload.get("semantic_schema_version"),
        }
    )
    encoded = json.dumps(
        key_payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return BOUNDARY_CACHE_KEY_PREFIX + hashlib.sha256(encoded).hexdigest()


def _validate_semantic_min_confidence(value: float) -> None:
    if value < 0.0 or value > 1.0:
        msg = "semantic_min_confidence must be in [0.0, 1.0]"
        raise ValueError(msg)


def _semantic_resolver_fingerprints(
    semantic_resolvers: tuple[SemanticResolver, ...] | None,
) -> tuple[dict[str, Any], ...]:
    if semantic_resolvers is None:
        return ()
    fingerprints = []
    for resolver in semantic_resolvers:
        fingerprints.append(
            {
                "resolver_id": str(getattr(resolver, "resolver_id", "")),
                "resolver_version": str(getattr(resolver, "resolver_version", "")),
                "resolver_api_version": SEMANTIC_RESOLVER_API_VERSION,
                "supported_languages": sorted(
                    str(language)
                    for language in tuple(getattr(resolver, "supported_languages", ()))
                ),
            }
        )
    return tuple(
        sorted(
            fingerprints,
            key=lambda item: (item["resolver_id"], item["resolver_version"]),
        )
    )


def _ordered_semantic_resolvers(
    semantic_resolvers: tuple[SemanticResolver, ...] | None,
) -> tuple[SemanticResolver, ...]:
    if semantic_resolvers is None:
        return ()
    return tuple(
        sorted(
            semantic_resolvers,
            key=lambda resolver: (
                str(getattr(resolver, "resolver_id", "")),
                str(getattr(resolver, "resolver_version", "")),
            ),
        )
    )


def _semantic_context(
    *,
    root: Path,
    language: str | None,
    resolution_mode: ResolutionMode,
    file_records: list[dict[str, Any]],
    node_records: list[dict[str, Any]],
    edge_records: list[dict[str, Any]],
    diagnostics: list[dict[str, Any]],
) -> SemanticResolverContext:
    return SemanticResolverContext(
        root=root,
        language=language,
        resolution_mode=resolution_mode,
        files=tuple(_stable_value(record) for record in file_records),
        nodes=tuple(_stable_value(record) for record in node_records),
        edges=tuple(_stable_value(record) for record in edge_records),
        diagnostics=tuple(_stable_value(record) for record in diagnostics),
    )


def _semantic_edge_record(edge: SemanticEdge) -> dict[str, Any]:
    target = edge.target_node_id or edge.reference
    edge_id = (
        "edge:"
        + _stable_hash(
            "semantic",
            edge.resolver_id,
            edge.source_node_id,
            target,
            edge.relationship_type,
            edge.reference,
        )[:16]
    )
    location = edge.location or {}
    return {
        "id": edge_id,
        "source": edge.source_node_id,
        "target": target,
        "type": edge.relationship_type,
        "resolution": edge.resolution,
        "reference": edge.reference,
        "candidates": list(edge.candidates),
        "location": {
            "byte_end": location.get("byte_end"),
            "byte_start": location.get("byte_start"),
            "end_line": location.get("end_line"),
            "start_line": location.get("start_line"),
        },
        "provenance": {
            "confidence": edge.confidence,
            "resolver": edge.resolver_id,
            "resolver_api_version": SEMANTIC_RESOLVER_API_VERSION,
            "resolver_version": edge.resolver_version,
            "source": "semantic",
        },
        "metadata": _stable_value(edge.metadata),
    }


def _merge_semantic_edges(
    *,
    root: Path,
    language: str | None,
    resolution_mode: ResolutionMode,
    fail_fast: bool,
    semantic_resolvers: tuple[SemanticResolver, ...] | None,
    semantic_min_confidence: float,
    file_records: list[dict[str, Any]],
    node_records: list[dict[str, Any]],
    edge_records: list[dict[str, Any]],
    diagnostics: list[dict[str, Any]],
    relationships_by_source: dict[str, list[str]],
) -> None:
    if semantic_resolvers is None:
        return
    context = _semantic_context(
        root=root,
        language=language,
        resolution_mode=resolution_mode,
        file_records=file_records,
        node_records=node_records,
        edge_records=edge_records,
        diagnostics=diagnostics,
    )
    semantic_by_key: dict[tuple[str, str, str, str, str], dict[str, Any]] = {}
    for resolver in _ordered_semantic_resolvers(semantic_resolvers):
        resolver_id = str(getattr(resolver, "resolver_id", ""))
        resolver_version = str(getattr(resolver, "resolver_version", ""))
        supported = tuple(
            str(item) for item in getattr(resolver, "supported_languages", ())
        )
        if language and supported and language not in supported:
            continue
        try:
            semantic_edges = resolver.enrich(context)
            for semantic_edge in semantic_edges:
                if semantic_edge.confidence < semantic_min_confidence:
                    continue
                edge = _semantic_edge_record(semantic_edge)
                key = (
                    resolver_id,
                    str(edge["source"]),
                    str(edge["target"]),
                    str(edge["type"]),
                    str(edge["reference"]),
                )
                existing = semantic_by_key.get(key)
                if (
                    existing is None
                    or edge["provenance"]["confidence"]
                    > existing["provenance"]["confidence"]
                ):
                    semantic_by_key[key] = edge
        except Exception as exc:
            if fail_fast:
                raise
            diagnostics.append(
                _diagnostic(
                    f"Semantic resolver {resolver_id} failed: {exc}",
                    stage="semantic",
                    code="boundary.semantic_resolver_error",
                    details={
                        "exception": type(exc).__name__,
                        "resolver": resolver_id,
                        "resolver_version": resolver_version,
                    },
                )
            )
    for edge in sorted(
        semantic_by_key.values(),
        key=lambda item: (
            item["source"],
            item["target"],
            item["type"],
            item["reference"],
            item["provenance"]["resolver"],
            item["id"],
        ),
    ):
        edge_records.append(edge)
        relationships_by_source.setdefault(str(edge["source"]), []).append(
            str(edge["id"])
        )


def _dependency_summary(
    symbol_facts: dict[str, Any],
    node_records: list[dict[str, Any]],
) -> dict[str, Any]:
    references: set[str] = set()
    for chunk_record in symbol_facts.get("chunk_records", []):
        for key in ("imports", "dependencies", "calls"):
            for value in chunk_record.get(key, []):
                if isinstance(value, dict):
                    references.update(str(item) for item in value.values() if item)
                elif value:
                    references.add(str(value))
    exports: set[str] = set()
    for node in node_records:
        for key in ("symbol", "qualified_name"):
            value = node.get(key)
            if value:
                exports.add(str(value))
    return {
        "exports": sorted(exports),
        "module": symbol_facts.get("module"),
        "references": sorted(references),
        "relationship_endpoints": [],
    }


def _extract_file_cache_record(
    file_path: Path,
    root: Path,
    language: str | None,
    *,
    resolution_mode: ResolutionMode,
    fail_fast: bool,
    cache_key: str,
    key_payload: dict[str, Any],
    timing_spans: dict[str, float],
) -> tuple[BoundaryCacheRecord, int, int]:
    display_path = normalize_boundary_path(_display_path(file_path, root))
    detected_language = _detect_language(file_path, language)
    file_id = compute_file_id(display_path)
    file_diagnostics: list[str] = []
    diagnostics: list[dict[str, Any]] = []
    status = "parsed"
    chunks: list[CodeChunk] = []
    parse_failures = 0
    metadata_failures = 0
    symbol_facts = extract_symbol_facts_for_file(
        file_path,
        root,
        language,
        fail_fast=fail_fast,
    )
    if detected_language:
        try:
            started_at = time.perf_counter()
            chunks = chunk_file(
                file_path,
                detected_language,
                extract_metadata=True,
                include_retrieval_metadata=True,
                identity_path=display_path,
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
    node_records: list[dict[str, Any]] = []
    symbol_indexes: dict[str, str] = {}
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

    file_record = {
        "id": file_id,
        "path": display_path,
        "language": detected_language,
        "content_hash": key_payload["content_hash"],
        "parser": f"tree-sitter-{detected_language}" if detected_language else None,
        "status": status,
        "diagnostics": sorted(dict.fromkeys(file_diagnostics)),
    }
    record = BoundaryCacheRecord(
        path=display_path,
        content_hash=str(key_payload["content_hash"]),
        cache_key=cache_key,
        key_payload=key_payload,
        file_record=file_record,
        node_records=node_records,
        symbol_facts=symbol_facts,
        diagnostics=diagnostics,
        dependency_summary=_dependency_summary(symbol_facts, node_records),
    )
    return record, parse_failures, metadata_failures


def _node_symbol_indexes(node_records: list[dict[str, Any]]) -> dict[str, str]:
    indexes: dict[str, str] = {}
    for node in node_records:
        node_id = str(node["id"])
        for key in (
            "definition_id",
            "node_id",
            "symbol_id",
            "qualified_name",
            "symbol",
        ):
            value = node.get(key)
            if value:
                indexes[str(value)] = node_id
        module_name = _module_name(str(node.get("path") or ""))
        for key in ("qualified_name", "symbol"):
            value = node.get(key)
            if value:
                indexes[f"{module_name}:{value}"] = node_id
    return indexes


def _assemble_boundary_ir(
    *,
    root: Path,
    language: str | None,
    canonical: bool,
    created_at: str | None,
    resolution_mode: ResolutionMode,
    fail_fast: bool,
    include_timings: bool,
    file_records: list[dict[str, Any]],
    node_records: list[dict[str, Any]],
    symbol_facts: list[dict[str, Any]],
    diagnostics: list[dict[str, Any]],
    parse_failures: int,
    metadata_failures: int,
    semantic_resolvers: tuple[SemanticResolver, ...] | None,
    semantic_min_confidence: float,
    timing_spans: dict[str, float],
    total_started_at: float,
) -> dict[str, Any]:
    started_at = time.perf_counter()
    graph = assemble_symbol_graph(
        symbol_facts,
        total_files=len(file_records),
        no_source_error=(
            f"No source files found in {root}" if not file_records else None
        ),
        resolution_mode=resolution_mode,
    )
    _add_duration(timing_spans, "graph_assembly_ms", started_at)
    diagnostics.extend(
        _diagnostic(
            str(message),
            stage="graph",
            code="boundary.graph_error",
            details={"source": "extract_symbol_graph"},
        )
        for message in graph.get("errors", [])
    )
    parse_failures = sum(
        1
        for diagnostic in diagnostics
        if diagnostic.get("code") == "boundary.parse_error"
    )
    metadata_failures = sum(
        1
        for diagnostic in diagnostics
        if diagnostic.get("code") == "boundary.metadata_error"
    )
    symbol_indexes = _node_symbol_indexes(node_records)
    edge_records: list[dict[str, Any]] = []
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
    _merge_semantic_edges(
        root=root,
        language=language,
        resolution_mode=resolution_mode,
        fail_fast=fail_fast,
        semantic_resolvers=semantic_resolvers,
        semantic_min_confidence=semantic_min_confidence,
        file_records=file_records,
        node_records=node_records,
        edge_records=edge_records,
        diagnostics=diagnostics,
        relationships_by_source=relationships_by_source,
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
    semantic_requested = semantic_resolvers is not None
    run_options = {
        "include_retrieval_metadata": True,
        "language": language,
        "resolution_mode": resolution_mode,
        "fail_fast": fail_fast,
        "include_timings": include_timings,
    }
    if semantic_requested:
        run_options["semantic_min_confidence"] = semantic_min_confidence
        run_options["semantic_resolvers"] = list(
            _semantic_resolver_fingerprints(semantic_resolvers)
        )
    ir: dict[str, Any] = {
        "schema_version": (
            BOUNDARY_IR_SEMANTIC_SCHEMA_VERSION
            if semantic_requested
            else BOUNDARY_IR_SCHEMA_VERSION
        ),
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
            "serialization_failures": 0,
            "failure_buckets": _failure_buckets(diagnostics),
        },
        "run": {
            "tool": "treesitter-chunker",
            "tool_version": TOOL_VERSION,
            "root": str(root),
            "created_at": created_at,
            "canonical": canonical,
            "options": run_options,
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
            ir["metrics"]["serialization_failures"] = 1
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


def extract_boundary_ir(
    path: str | Path,
    language: str | None = None,
    *,
    canonical: bool = True,
    created_at: str | None = None,
    resolution_mode: ResolutionMode = "strict",
    fail_fast: bool = False,
    include_timings: bool = False,
    incremental: bool = False,
    cache_dir: str | Path | None = None,
    force_rebuild: bool = False,
    semantic_resolvers: tuple[SemanticResolver, ...] | None = None,
    semantic_min_confidence: float = 0.0,
) -> dict[str, Any]:
    """Extract Boundary IR for a source file or repository."""
    if resolution_mode not in RESOLUTION_MODES:
        msg = f"Unsupported resolution_mode: {resolution_mode}"
        raise ValueError(msg)
    _validate_semantic_min_confidence(semantic_min_confidence)
    semantic_resolvers = (
        None if semantic_resolvers is None else tuple(semantic_resolvers)
    )
    total_started_at = time.perf_counter()
    timing_spans: dict[str, float] = {}
    root = Path(path)
    if incremental:
        return _extract_boundary_ir_incremental(
            root,
            language,
            canonical=canonical,
            created_at=created_at,
            resolution_mode=resolution_mode,
            fail_fast=fail_fast,
            include_timings=include_timings,
            cache_dir=cache_dir,
            force_rebuild=force_rebuild,
            semantic_resolvers=semantic_resolvers,
            semantic_min_confidence=semantic_min_confidence,
            timing_spans=timing_spans,
            total_started_at=total_started_at,
        )
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
        # BUG-4: normalize on the cold path too, so cold and incremental funnel
        # every path through the same total normalization before any ID.
        display_path = normalize_boundary_path(_display_path(file_path, root))
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
                    identity_path=display_path,
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
    _merge_semantic_edges(
        root=root,
        language=language,
        resolution_mode=resolution_mode,
        fail_fast=fail_fast,
        semantic_resolvers=semantic_resolvers,
        semantic_min_confidence=semantic_min_confidence,
        file_records=file_records,
        node_records=node_records,
        edge_records=edge_records,
        diagnostics=diagnostics,
        relationships_by_source=relationships_by_source,
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
    semantic_requested = semantic_resolvers is not None
    run_options = {
        "include_retrieval_metadata": True,
        "language": language,
        "resolution_mode": resolution_mode,
        "fail_fast": fail_fast,
        "include_timings": include_timings,
    }
    if semantic_requested:
        run_options["semantic_min_confidence"] = semantic_min_confidence
        run_options["semantic_resolvers"] = list(
            _semantic_resolver_fingerprints(semantic_resolvers)
        )
    ir: dict[str, Any] = {
        "schema_version": (
            BOUNDARY_IR_SEMANTIC_SCHEMA_VERSION
            if semantic_requested
            else BOUNDARY_IR_SCHEMA_VERSION
        ),
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
            "options": run_options,
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


def _extract_boundary_ir_incremental(
    root: Path,
    language: str | None,
    *,
    canonical: bool,
    created_at: str | None,
    resolution_mode: ResolutionMode,
    fail_fast: bool,
    include_timings: bool,
    cache_dir: str | Path | None,
    force_rebuild: bool,
    semantic_resolvers: tuple[SemanticResolver, ...] | None,
    semantic_min_confidence: float,
    timing_spans: dict[str, float],
    total_started_at: float,
) -> dict[str, Any]:
    started_at = time.perf_counter()
    files = collect_source_files(root, language)
    _add_duration(timing_spans, "parse_ms", started_at)
    cache_root = _cache_dir_for(root, cache_dir)
    index = load_cache_index(cache_root)
    current_payloads: dict[str, dict[str, Any]] = {}
    current_keys: dict[str, str] = {}
    current_hashes: dict[str, str] = {}
    invalid_paths: set[str] = set()
    cached_records: dict[str, BoundaryCacheRecord] = {}

    for file_path in files:
        display_path = normalize_boundary_path(_display_path(file_path, root))
        detected_language = _detect_language(file_path, language)
        content_hash = _content_hash(file_path)
        payload = _cache_key_payload(
            display_path=display_path,
            content_hash=content_hash,
            language=detected_language,
            resolution_mode=resolution_mode,
            fail_fast=fail_fast,
            semantic_resolvers=semantic_resolvers,
            semantic_min_confidence=semantic_min_confidence,
        )
        cache_key = _build_boundary_cache_key(payload)
        current_payloads[display_path] = payload
        current_keys[display_path] = cache_key
        current_hashes[display_path] = content_hash
        previous_key = index.records.get(display_path)
        if previous_key == cache_key and not force_rebuild:
            record = load_cache_record(cache_root, cache_key)
            if record is None:
                invalid_paths.add(display_path)
            else:
                cached_records[display_path] = record
        else:
            invalid_paths.add(display_path)

    changed_paths, deleted_paths = detect_changed_paths(
        current_hashes,
        index,
        invalid_paths=invalid_paths,
        force_rebuild=force_rebuild,
    )
    for deleted_path in deleted_paths:
        old_key = index.records.pop(deleted_path, None)
        index.content_hashes.pop(deleted_path, None)
        if old_key:
            prune_cache_record(cache_root, old_key)

    recomputed: dict[str, BoundaryCacheRecord] = {}
    current_summaries: dict[str, dict[str, Any]] = {}
    parse_failures = 0
    metadata_failures = 0
    path_by_display = {
        normalize_boundary_path(_display_path(file_path, root)): file_path
        for file_path in files
    }
    for display_path in changed_paths:
        file_path = path_by_display.get(display_path)
        if file_path is None:
            continue
        record, parse_count, metadata_count = _extract_file_cache_record(
            file_path,
            root,
            language,
            resolution_mode=resolution_mode,
            fail_fast=fail_fast,
            cache_key=current_keys[display_path],
            key_payload=current_payloads[display_path],
            timing_spans=timing_spans,
        )
        recomputed[display_path] = record
        current_summaries[display_path] = record.dependency_summary
        parse_failures += parse_count
        metadata_failures += metadata_count

    impact_records = {**cached_records, **recomputed}
    impacted_paths = compute_impacted_paths(
        changed_paths,
        deleted_paths,
        impact_records,
        current_summaries=current_summaries,
    )
    for display_path in impacted_paths:
        if display_path in recomputed:
            continue
        file_path = path_by_display.get(display_path)
        if file_path is None:
            continue
        record, parse_count, metadata_count = _extract_file_cache_record(
            file_path,
            root,
            language,
            resolution_mode=resolution_mode,
            fail_fast=fail_fast,
            cache_key=current_keys[display_path],
            key_payload=current_payloads[display_path],
            timing_spans=timing_spans,
        )
        recomputed[display_path] = record
        parse_failures += parse_count
        metadata_failures += metadata_count

    records: list[BoundaryCacheRecord] = []
    for display_path in sorted(path_by_display):
        record = recomputed.get(display_path) or cached_records.get(display_path)
        if record is None:
            file_path = path_by_display[display_path]
            record, parse_count, metadata_count = _extract_file_cache_record(
                file_path,
                root,
                language,
                resolution_mode=resolution_mode,
                fail_fast=fail_fast,
                cache_key=current_keys[display_path],
                key_payload=current_payloads[display_path],
                timing_spans=timing_spans,
            )
            recomputed[display_path] = record
            parse_failures += parse_count
            metadata_failures += metadata_count
        records.append(record)

    for display_path, record in recomputed.items():
        save_cache_record(cache_root, record)
        index.records[display_path] = record.cache_key
        index.content_hashes[display_path] = record.content_hash
    save_cache_index(cache_root, index)

    return _assemble_boundary_ir(
        root=root,
        language=language,
        canonical=canonical,
        created_at=created_at,
        resolution_mode=resolution_mode,
        fail_fast=fail_fast,
        include_timings=include_timings,
        file_records=[record.file_record for record in records],
        node_records=[node for record in records for node in record.node_records],
        symbol_facts=[record.symbol_facts for record in records],
        diagnostics=[
            diagnostic for record in records for diagnostic in record.diagnostics
        ],
        parse_failures=parse_failures,
        metadata_failures=metadata_failures,
        semantic_resolvers=semantic_resolvers,
        semantic_min_confidence=semantic_min_confidence,
        timing_spans=timing_spans,
        total_started_at=total_started_at,
    )

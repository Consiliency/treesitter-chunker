"""Shared symbol graph extraction built on enriched chunk metadata."""

from __future__ import annotations

import hashlib
import re
from bisect import bisect_left
from collections import defaultdict
from fnmatch import fnmatchcase
from heapq import heappop, heappush
from pathlib import Path
from typing import Any

from .auto import ZeroConfigAPI
from ._internal.registry import baml_companion_available
from .core import chunk_file
from .types import RESOLUTION_MODES, ResolutionMode, ResolutionStatus

SKIP_PARTS = {
    "__pycache__",
    ".git",
    ".venv",
    "venv",
    "node_modules",
    ".tox",
    ".pytest_cache",
    "build",
    "dist",
    ".eggs",
    "archive",
}

CLASS_KINDS = {"class", "interface", "struct", "enum", "trait", "type"}
FUNCTION_KINDS = {"function", "method", "constructor"}
SYMBOL_KINDS = CLASS_KINDS | FUNCTION_KINDS | {"module"}
_IMPORT_KEYWORDS = {
    "import",
    "from",
    "as",
    "require",
    "package",
    "using",
    "namespace",
    "static",
    "new",
}


def _candidate_extensions(language: str | None) -> set[str]:
    extension_map = ZeroConfigAPI.EXTENSION_MAP
    if language is None:
        extensions = set(extension_map)
        if not baml_companion_available():
            extensions.discard(".baml")
        return extensions
    normalized = language.lower()
    return {ext for ext, lang in extension_map.items() if lang == normalized}


def _should_skip_path(path: Path) -> bool:
    return any(part in SKIP_PARTS for part in path.parts)


def collect_source_files(path: str | Path, language: str | None = None) -> list[Path]:
    """Collect source files for a given path/language selection."""
    root = Path(path)
    if not root.exists():
        return []

    extensions = _candidate_extensions(language)
    if root.is_file():
        if language is None or root.suffix.lower() in extensions:
            return [root]
        return []

    files = [
        file_path
        for file_path in root.rglob("*")
        if file_path.is_file()
        and not _should_skip_path(file_path)
        and file_path.suffix.lower() in extensions
    ]
    return sorted(files)


def _detect_language(
    file_path: Path, fallback_language: str | None = None
) -> str | None:
    if fallback_language:
        return fallback_language.lower()
    if file_path.suffix.lower() == ".baml" and not baml_companion_available():
        return None
    return ZeroConfigAPI.EXTENSION_MAP.get(file_path.suffix.lower())


def _module_name(file_path: Path, root: Path) -> str:
    try:
        rel_path = file_path.relative_to(root if root.is_dir() else root.parent)
    except ValueError:
        rel_path = file_path
    parts = list(rel_path.parts)
    if parts and parts[-1].count("."):
        parts[-1] = parts[-1].rsplit(".", maxsplit=1)[0]
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts) if parts else file_path.stem


def _display_file(file_path: Path, root: Path) -> str:
    from .boundary.impact import normalize_boundary_path

    try:
        display_file = str(
            file_path.relative_to(root if root.is_dir() else root.parent)
        )
    except ValueError:
        display_file = str(file_path)
    return normalize_boundary_path(display_file)


def _normalize_reference(value: object) -> str | None:
    if isinstance(value, dict):
        for key in ("qualified_name", "symbol", "name", "module", "path"):
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
        return None
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _reference_candidates(reference: str) -> list[str]:
    tokens = [
        token for token in re.findall(r"[A-Za-z_][A-Za-z0-9_\.]*", reference) if token
    ]
    candidates: list[str] = []
    for token in tokens:
        lowered = token.lower()
        if lowered in _IMPORT_KEYWORDS:
            continue
        candidates.append(token)
        if "." in token:
            candidates.extend(part for part in token.split(".") if part)
    candidates.append(reference)
    seen = set()
    ordered = []
    for candidate in candidates:
        if candidate not in seen:
            seen.add(candidate)
            ordered.append(candidate)
    return ordered


def _build_resolution_indexes(
    symbol_lookup: dict[str, dict[str, Any]],
) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    by_qualified: defaultdict[str, set[str]] = defaultdict(set)
    by_name: defaultdict[str, set[str]] = defaultdict(set)
    for symbol_id, symbol in symbol_lookup.items():
        qualified_name = symbol.get("qualified_name")
        if qualified_name:
            by_qualified[str(qualified_name)].add(symbol_id)
        name = symbol.get("name")
        if name:
            by_name[str(name)].add(symbol_id)
    return dict(by_qualified), dict(by_name)


def _resolve_reference_candidates(
    reference: str,
    by_qualified: dict[str, set[str]],
    by_name: dict[str, set[str]],
) -> list[str]:
    for candidate in _reference_candidates(reference):
        if candidate in by_qualified:
            return sorted(by_qualified[candidate])
    candidates: set[str] = set()
    for candidate in _reference_candidates(reference):
        candidates.update(by_name.get(candidate, set()))
    return sorted(candidates)


def _resolution_status(candidates: list[str]) -> ResolutionStatus:
    if len(candidates) == 1:
        return "resolved"
    if candidates:
        return "ambiguous"
    return "unresolved"


def _resolve_call_reference_candidates(
    reference: str,
    by_qualified: dict[str, set[str]],
    by_name: dict[str, set[str]],
) -> list[str]:
    """Do not infer a callee from tokens inside arbitrary source expressions.

    Call references are verbatim source slices, unlike normalized import names.
    Only simple identifier/member-chain syntax uses the existing permissive
    resolver. Comments, computed members and other complex expressions remain
    unresolved raw observations; their incidental identifiers are not callees.
    This is a conservative syntax guard, not scope-aware name resolution.
    """
    if not re.fullmatch(
        r"[A-Za-z_][A-Za-z0-9_]*(?:\s*(?:\?\.|\.|::)\s*[A-Za-z_][A-Za-z0-9_]*)*",
        reference.strip(),
    ):
        return []
    return _resolve_reference_candidates(reference, by_qualified, by_name)


def _import_record(import_text: str, line: int) -> dict[str, Any]:
    names = [
        candidate
        for candidate in _reference_candidates(import_text)
        if "." not in candidate
    ]
    return {
        "module": import_text,
        "names": names,
        "alias": "",
        "line": line,
        "is_from_import": import_text.lstrip().startswith("from "),
    }


def _call_site_id(
    caller: str,
    file_name: str,
    call_byte_start: int,
    call_byte_end: int,
    callee_byte_start: int,
    callee_byte_end: int,
    reference: str,
) -> str:
    seed = "|".join(
        str(value)
        for value in (
            caller,
            file_name,
            call_byte_start,
            call_byte_end,
            callee_byte_start,
            callee_byte_end,
            reference,
            "calls",
        )
    )
    return "call:" + hashlib.sha1(seed.encode("utf-8")).hexdigest()


def _line_bounds(newline_offsets: list[int], start: int, end: int) -> tuple[int, int]:
    start_line = bisect_left(newline_offsets, start) + 1
    final_byte = max(start, end - 1)
    end_line = bisect_left(newline_offsets, final_byte) + 1
    return start_line, end_line


def _call_facts_for_chunks(
    chunks: list[Any],
    owners: list[dict[str, Any]],
    source: bytes,
    display_file: str,
) -> list[dict[str, Any]]:
    observations: list[dict[str, Any]] = []
    for order, chunk in enumerate(chunks):
        metadata = chunk.metadata or {}
        spans = metadata.get("call_spans", [])
        if not isinstance(spans, list):
            continue
        for span in spans:
            if not isinstance(span, dict):
                continue
            call_start = span.get("start")
            call_end = span.get("end")
            callee_start = span.get("callee_start")
            callee_end = span.get("callee_end")
            if not (
                isinstance(call_start, int)
                and isinstance(call_end, int)
                and isinstance(callee_start, int)
                and isinstance(callee_end, int)
            ):
                continue
            if not (
                0 <= call_start < call_end <= len(source)
                and call_start <= callee_start < callee_end <= call_end
            ):
                continue
            reference = source[callee_start:callee_end].decode("utf-8")
            observations.append(
                {
                    "call_start": call_start,
                    "call_end": call_end,
                    "callee_start": callee_start,
                    "callee_end": callee_end,
                    "reference": reference,
                    "call_kind": str(span.get("type") or "call"),
                    "order": order,
                    "chunk_start": chunk.byte_start,
                    "chunk_end": chunk.byte_end,
                    "node_type": chunk.node_type,
                }
            )

    decorated_owner_index = sorted(
        (
            owner
            for owner in owners
            if owner["parent_context"] == "decorated_definition"
        ),
        key=lambda item: (item["byte_start"], item["order"]),
    )
    decorated_owner_starts = [owner["byte_start"] for owner in decorated_owner_index]
    decorated_owners: dict[tuple[Any, ...], dict[str, Any]] = {}
    for observation in observations:
        if observation["node_type"] == "decorated_definition":
            decorated_index = bisect_left(
                decorated_owner_starts, observation["chunk_start"]
            )
            wrapper_owner = None
            while (
                decorated_index < len(decorated_owner_index)
                and decorated_owner_index[decorated_index]["byte_start"]
                <= observation["chunk_end"]
            ):
                candidate = decorated_owner_index[decorated_index]
                if candidate["byte_end"] <= observation["chunk_end"]:
                    wrapper_owner = candidate
                    break
                decorated_index += 1
            if wrapper_owner is not None:
                site_key = (
                    display_file,
                    observation["call_start"],
                    observation["call_end"],
                    observation["callee_start"],
                    observation["callee_end"],
                    observation["reference"],
                )
                if not (
                    wrapper_owner["byte_start"] <= observation["call_start"]
                    and observation["call_end"] <= wrapper_owner["byte_end"]
                ):
                    decorated_owners[site_key] = wrapper_owner

    owners_by_start = sorted(
        owners, key=lambda item: (item["byte_start"], item["order"])
    )
    owner_heap: list[tuple[tuple[int, int, int], int, dict[str, Any]]] = []
    owner_index = 0
    observation_owners: dict[int, dict[str, Any]] = {}
    for observation in sorted(
        observations,
        key=lambda item: (
            item["call_start"],
            item["call_end"],
            item["callee_start"],
            item["callee_end"],
            item["reference"],
            item["order"],
        ),
    ):
        while (
            owner_index < len(owners_by_start)
            and owners_by_start[owner_index]["byte_start"] <= observation["call_start"]
        ):
            candidate = owners_by_start[owner_index]
            owner_rank = (
                0 if candidate["kind"] in FUNCTION_KINDS else 1,
                candidate["byte_end"] - candidate["byte_start"],
                candidate["order"],
            )
            heappush(owner_heap, (owner_rank, candidate["order"], candidate))
            owner_index += 1

        deferred = []
        while owner_heap:
            candidate = owner_heap[0][2]
            if candidate["byte_end"] < observation["call_start"]:
                heappop(owner_heap)
                continue
            if candidate["byte_end"] < observation["call_end"]:
                deferred.append(heappop(owner_heap))
                continue
            observation_owners[id(observation)] = candidate
            break
        for entry in deferred:
            heappush(owner_heap, entry)

    selected: dict[tuple[Any, ...], tuple[tuple[Any, ...], dict[str, Any]]] = {}
    for observation in observations:
        site_key = (
            display_file,
            observation["call_start"],
            observation["call_end"],
            observation["callee_start"],
            observation["callee_end"],
            observation["reference"],
        )
        owner = decorated_owners.get(site_key)
        if owner is not None:
            pass
        elif id(observation) in observation_owners:
            owner = observation_owners[id(observation)]
        else:
            continue

        key = (
            owner["id"],
            display_file,
            observation["call_start"],
            observation["call_end"],
            observation["callee_start"],
            observation["callee_end"],
            observation["reference"],
        )
        selection_rank = (owner["order"], observation["order"])
        current = selected.get(key)
        if current is None or selection_rank < current[0]:
            selected[key] = (selection_rank, {**observation, "owner": owner})

    newline_offsets = [match.start() for match in re.finditer(b"\n", source)]
    call_facts = []
    for _, observation in sorted(
        selected.values(),
        key=lambda item: (
            item[1]["call_start"],
            item[1]["call_end"],
            item[1]["callee_start"],
            item[0],
        ),
    ):
        owner = observation["owner"]
        start_line, end_line = _line_bounds(
            newline_offsets, observation["call_start"], observation["call_end"]
        )
        fact_id = _call_site_id(
            owner["id"],
            display_file,
            observation["call_start"],
            observation["call_end"],
            observation["callee_start"],
            observation["callee_end"],
            observation["reference"],
        )
        call_facts.append(
            {
                "id": fact_id,
                "from": owner["id"],
                "file": display_file,
                "type": "calls",
                "reference": observation["reference"],
                "location": {
                    "byte_start": observation["call_start"],
                    "byte_end": observation["call_end"],
                    "start_line": start_line,
                    "end_line": end_line,
                },
                "callee_byte_start": observation["callee_start"],
                "callee_byte_end": observation["callee_end"],
                "call_kind": observation["call_kind"],
            }
        )
    return call_facts


def extract_symbol_facts_for_file(
    file_path: Path,
    root: Path,
    language: str | None = None,
    *,
    fail_fast: bool = False,
) -> dict[str, Any]:
    """Extract deterministic per-file symbol facts used by graph assembly."""
    detected_language = _detect_language(file_path, language)
    display_file = _display_file(file_path, root)
    module_name = _module_name(file_path, root)
    facts: dict[str, Any] = {
        "path": display_file,
        "display_file": display_file,
        "module": module_name,
        "language": detected_language,
        "symbol_lookup": {},
        "import_strings": [],
        "imports": [],
        "chunk_records": [],
        "call_facts": [],
        "errors": [],
    }
    if not detected_language:
        return facts
    try:
        chunks = chunk_file(
            file_path,
            detected_language,
            extract_metadata=True,
            include_retrieval_metadata=True,
            identity_path=display_file,
        )
    except Exception as exc:  # pragma: no cover - defensive around parser failures
        if fail_fast:
            raise
        facts["errors"].append(f"Error extracting symbols from {file_path}: {exc}")
        return facts

    source = file_path.read_bytes().decode("utf-8", errors="replace").encode("utf-8")
    symbol_lookup: dict[str, dict[str, Any]] = {}
    fact_import_strings: list[str] = []
    imports_output: list[dict[str, Any]] = []
    chunk_records: list[dict[str, Any]] = []
    owners: list[dict[str, Any]] = []
    identity_occurrences: defaultdict[str, int] = defaultdict(int)
    for order, chunk in enumerate(chunks):
        metadata = chunk.metadata or {}
        identity_base = str(chunk.definition_id or chunk.node_id)
        occurrence = identity_occurrences[identity_base]
        identity_occurrences[identity_base] += 1
        symbol_id = (
            identity_base if occurrence == 0 else f"{identity_base}#{occurrence}"
        )
        fact_import_strings.extend(
            str(value) for value in metadata.get("imports", []) if str(value)
        )
        symbol = metadata.get("symbol")
        kind = metadata.get("kind")
        if not symbol or not kind or kind not in SYMBOL_KINDS:
            continue
        qualified_name = metadata.get("qualified_name")
        symbol_record = {
            "name": str(symbol),
            "kind": str(kind),
            "file": display_file,
            "line": chunk.start_line,
            "end_line": chunk.end_line,
            "module": module_name,
            "parent_class": str(metadata.get("parent_symbol") or ""),
            "qualified_name": qualified_name,
            "signature": metadata.get("signature_text"),
            "semantic_path": metadata.get("semantic_path"),
            "language": detected_language,
            "definition_id": chunk.definition_id or None,
            "node_id": chunk.node_id or None,
        }
        symbol_lookup[symbol_id] = symbol_record
        owners.append(
            {
                "id": symbol_id,
                "kind": str(kind),
                "byte_start": chunk.byte_start,
                "byte_end": chunk.byte_end,
                "order": order,
                "parent_context": chunk.parent_context,
            }
        )
        import_strings = [
            str(value) for value in metadata.get("imports", []) if str(value)
        ]
        imports_output.extend(
            _import_record(import_text, chunk.start_line)
            for import_text in import_strings
        )
        chunk_records.append(
            {
                "context": {
                    "id": symbol_id,
                    "line": chunk.start_line,
                    "file": display_file,
                },
                "imports": import_strings,
                "dependencies": [
                    str(value)
                    for value in metadata.get("dependencies", [])
                    if str(value)
                ],
                "calls": (
                    list(metadata.get("calls", []))
                    if isinstance(metadata.get("calls"), list)
                    else []
                ),
            }
        )
    facts["symbol_lookup"] = symbol_lookup
    facts["import_strings"] = sorted(dict.fromkeys(fact_import_strings))
    facts["imports"] = imports_output
    facts["chunk_records"] = chunk_records
    facts["call_facts"] = _call_facts_for_chunks(chunks, owners, source, display_file)
    return facts


def assemble_symbol_graph(
    facts: list[dict[str, Any]],
    *,
    total_files: int | None = None,
    no_source_error: str | None = None,
    resolution_mode: ResolutionMode = "permissive",
) -> dict[str, Any]:
    """Assemble public symbol graph output from per-file facts."""
    if resolution_mode not in RESOLUTION_MODES:
        msg = f"Unsupported resolution_mode: {resolution_mode}"
        raise ValueError(msg)
    if total_files == 0 and no_source_error:
        return {
            "symbols": {"classes": [], "functions": [], "imports": []},
            "relationships": [],
            "call_facts": [],
            "metadata": {
                "files_processed": 0,
                "total_classes": 0,
                "total_functions": 0,
                "total_imports": 0,
                "total_relationships": 0,
                "errors": [no_source_error],
            },
            "symbol_lookup": {},
            "errors": [no_source_error],
        }

    symbol_lookup: dict[str, dict[str, Any]] = {}
    imports_output: list[dict[str, Any]] = []
    chunk_records: list[dict[str, Any]] = []
    call_facts: list[dict[str, Any]] = []
    errors: list[str] = []
    for file_facts in facts:
        symbol_lookup.update(file_facts.get("symbol_lookup", {}))
        imports_output.extend(file_facts.get("imports", []))
        chunk_records.extend(file_facts.get("chunk_records", []))
        call_facts.extend(file_facts.get("call_facts", []))
        errors.extend(str(error) for error in file_facts.get("errors", []))

    by_qualified, by_name = _build_resolution_indexes(symbol_lookup)
    relationships: list[dict[str, Any]] = []
    seen_relationships: set[tuple[str, str, str, str]] = set()

    for chunk_record in chunk_records:
        relationship_context = chunk_record["context"]
        from_id = relationship_context["id"]
        line = relationship_context["line"]
        file_name = relationship_context["file"]
        for relationship_type, values in (
            ("imports", chunk_record.get("imports", [])),
            ("dependencies", chunk_record.get("dependencies", [])),
        ):
            for value in values:
                reference = _normalize_reference(value)
                if not reference:
                    continue
                candidates = _resolve_reference_candidates(
                    reference, by_qualified, by_name
                )
                resolution = _resolution_status(candidates)
                to_id = candidates[0] if resolution == "resolved" else reference
                if to_id == from_id:
                    continue
                dedupe_key = (from_id, to_id, relationship_type, reference)
                if dedupe_key in seen_relationships:
                    continue
                seen_relationships.add(dedupe_key)
                relationships.append(
                    {
                        "from": from_id,
                        "to": to_id,
                        "type": relationship_type,
                        "line": line,
                        "file": file_name,
                        "is_internal": resolution == "resolved",
                        "reference": reference,
                        "resolution": resolution,
                        "candidates": candidates,
                        "resolution_mode": resolution_mode,
                        "provenance": {
                            "resolver": "extract_symbol_graph",
                            "source": "syntax",
                        },
                    }
                )

    call_facts = sorted(
        call_facts,
        key=lambda fact: (
            str(fact.get("file") or ""),
            int(fact.get("location", {}).get("byte_start", 0)),
            int(fact.get("location", {}).get("byte_end", 0)),
            str(fact.get("id") or ""),
        ),
    )
    seen_call_sites: set[str] = set()
    for fact in call_facts:
        call_site_id = str(fact["id"])
        if call_site_id in seen_call_sites:
            continue
        seen_call_sites.add(call_site_id)
        from_id = str(fact["from"])
        reference = str(fact["reference"])
        candidates = _resolve_call_reference_candidates(
            reference, by_qualified, by_name
        )
        resolution = _resolution_status(candidates)
        to_id = candidates[0] if resolution == "resolved" else reference
        relationships.append(
            {
                "from": from_id,
                "to": to_id,
                "type": "calls",
                "line": fact["location"]["start_line"],
                "file": fact["file"],
                "is_internal": resolution == "resolved",
                "reference": reference,
                "resolution": resolution,
                "candidates": candidates,
                "resolution_mode": resolution_mode,
                "provenance": {
                    "resolver": "extract_symbol_graph",
                    "source": "syntax",
                },
                "call_site_id": call_site_id,
                "location": fact["location"],
                "callee_byte_start": fact["callee_byte_start"],
                "callee_byte_end": fact["callee_byte_end"],
                "call_kind": fact["call_kind"],
            }
        )

    class_symbols = [
        symbol for symbol in symbol_lookup.values() if symbol["kind"] in CLASS_KINDS
    ]
    function_symbols = [
        symbol for symbol in symbol_lookup.values() if symbol["kind"] in FUNCTION_KINDS
    ]
    total = len(facts) if total_files is None else total_files
    metadata = {
        "files_processed": total - len(errors),
        "total_classes": len(class_symbols),
        "total_functions": len(function_symbols),
        "total_imports": len(imports_output),
        "total_relationships": len(relationships),
        "errors": errors,
    }
    return {
        "symbols": {
            "classes": class_symbols,
            "functions": function_symbols,
            "imports": imports_output,
        },
        "relationships": relationships,
        "call_facts": call_facts,
        "metadata": metadata,
        "symbol_lookup": symbol_lookup,
        "errors": errors,
    }


def extract_symbol_graph(
    path: str | Path,
    language: str | None = None,
    resolution_mode: ResolutionMode = "permissive",
    fail_fast: bool = False,
) -> dict[str, Any]:
    """Extract a language-agnostic symbol graph from chunk metadata."""
    if resolution_mode not in RESOLUTION_MODES:
        msg = f"Unsupported resolution_mode: {resolution_mode}"
        raise ValueError(msg)
    root = Path(path)
    files = collect_source_files(root, language)
    if not files:
        return {
            "symbols": {"classes": [], "functions": [], "imports": []},
            "relationships": [],
            "call_facts": [],
            "metadata": {
                "files_processed": 0,
                "total_classes": 0,
                "total_functions": 0,
                "total_imports": 0,
                "total_relationships": 0,
                "errors": [f"No source files found in {root}"],
            },
            "symbol_lookup": {},
            "errors": [f"No source files found in {root}"],
        }

    facts = [
        extract_symbol_facts_for_file(
            file_path,
            root,
            language,
            fail_fast=fail_fast,
        )
        for file_path in files
    ]
    return assemble_symbol_graph(
        facts,
        total_files=len(files),
        resolution_mode=resolution_mode,
    )


def find_symbols(
    path: str | Path, pattern: str, kind: str | None = None
) -> list[dict[str, Any]]:
    """Find symbols matching a glob-style pattern."""
    graph = extract_symbol_graph(path)
    matches = []
    for symbol_id, symbol in graph["symbol_lookup"].items():
        if kind and symbol.get("kind") != kind:
            continue
        name = str(symbol.get("name") or "")
        qualified_name = str(symbol.get("qualified_name") or "")
        if fnmatchcase(name, pattern) or (
            qualified_name and fnmatchcase(qualified_name, pattern)
        ):
            matches.append({"id": symbol_id, **symbol})
    matches.sort(
        key=lambda symbol: (
            symbol.get("file", ""),
            symbol.get("line", 0),
            symbol.get("name", ""),
        )
    )
    return matches

"""Shared symbol graph extraction built on enriched chunk metadata."""

from __future__ import annotations

import re
from collections import defaultdict
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Any, Literal

from .auto import ZeroConfigAPI
from .core import chunk_file

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
ResolutionMode = Literal["strict", "permissive"]
ResolutionStatus = Literal["resolved", "ambiguous", "unresolved"]
RESOLUTION_MODES = ("strict", "permissive")


def _candidate_extensions(language: str | None) -> set[str]:
    extension_map = ZeroConfigAPI.EXTENSION_MAP
    if language is None:
        return set(extension_map)
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
    try:
        return str(file_path.relative_to(root if root.is_dir() else root.parent))
    except ValueError:
        return str(file_path)


def _symbol_id(
    module_name: str, qualified_name: str | None, symbol: str | None, fallback: str
) -> str:
    if module_name and qualified_name:
        return f"{module_name}:{qualified_name}"
    if module_name and symbol:
        return f"{module_name}:{symbol}"
    return fallback


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

    symbol_lookup: dict[str, dict[str, Any]] = {}
    chunk_records: list[
        tuple[dict[str, Any], list[str], list[str], list[dict[str, Any]]]
    ] = []
    imports_output: list[dict[str, Any]] = []
    errors: list[str] = []

    for file_path in files:
        detected_language = _detect_language(file_path, language)
        if not detected_language:
            continue
        module_name = _module_name(file_path, root)
        display_file = _display_file(file_path, root)
        try:
            chunks = chunk_file(
                file_path,
                detected_language,
                extract_metadata=True,
                include_retrieval_metadata=True,
            )
        except Exception as exc:  # pragma: no cover - defensive around parser failures
            if fail_fast:
                raise
            errors.append(f"Error extracting symbols from {file_path}: {exc}")
            continue

        for chunk in chunks:
            metadata = chunk.metadata or {}
            symbol = metadata.get("symbol")
            kind = metadata.get("kind")
            if not symbol or not kind or kind not in SYMBOL_KINDS:
                continue
            qualified_name = metadata.get("qualified_name")
            symbol_id = _symbol_id(
                module_name,
                str(qualified_name) if qualified_name else None,
                str(symbol),
                chunk.definition_id or chunk.node_id,
            )
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
            }
            symbol_lookup[symbol_id] = symbol_record
            import_strings = [
                str(value) for value in metadata.get("imports", []) if str(value)
            ]
            imports_output.extend(
                _import_record(import_text, chunk.start_line)
                for import_text in import_strings
            )
            chunk_records.append(
                (
                    {
                        "id": symbol_id,
                        "line": chunk.start_line,
                        "file": display_file,
                    },
                    import_strings,
                    [
                        str(value)
                        for value in metadata.get("dependencies", [])
                        if str(value)
                    ],
                    (
                        list(metadata.get("calls", []))
                        if isinstance(metadata.get("calls"), list)
                        else []
                    ),
                )
            )

    by_qualified, by_name = _build_resolution_indexes(symbol_lookup)
    relationships: list[dict[str, Any]] = []
    seen_relationships: set[tuple[str, str, str]] = set()

    for relationship_context, imports, dependencies, calls in chunk_records:
        from_id = relationship_context["id"]
        line = relationship_context["line"]
        file_name = relationship_context["file"]
        for relationship_type, values in (
            ("imports", imports),
            ("dependencies", dependencies),
            ("calls", calls),
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
                dedupe_key = (from_id, to_id, relationship_type)
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

    class_symbols = [
        symbol for symbol in symbol_lookup.values() if symbol["kind"] in CLASS_KINDS
    ]
    function_symbols = [
        symbol for symbol in symbol_lookup.values() if symbol["kind"] in FUNCTION_KINDS
    ]
    metadata = {
        "files_processed": len(files) - len(errors),
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
        "metadata": metadata,
        "symbol_lookup": symbol_lookup,
        "errors": errors,
    }


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

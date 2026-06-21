"""Canonical Boundary IR JSON serialization."""

from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from chunker.boundary import _canon

# Fields excluded from the parity hash view (BUG-2 / canon S5 + locator).
# These are volatile / provenance data (wall-clock, absolute paths, tool build,
# timings) that MUST NOT enter hashed content -- otherwise the same logical code
# hashes differently across machines, checkouts, and runs (false negatives).
_PARITY_EXCLUDED_RUN_FIELDS = ("root", "created_at", "tool_version", "timings")
# canon profile for Boundary-IR semantic content (the meaning-bearing structure).
_PARITY_DIGEST_PROFILE = "semantic-content"


def _location_start_line(record: dict[str, Any]) -> int:
    location = record.get("location")
    if isinstance(location, dict):
        value = location.get("start_line")
        if isinstance(value, int):
            return value
    return -1


def _span_start_line(record: dict[str, Any]) -> int:
    span = record.get("span")
    if isinstance(span, dict):
        value = span.get("start_line")
        if isinstance(value, int):
            return value
    return -1


def _canonicalize_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _canonicalize_value(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        # canon rule (SPEC.md S4): array insertion order is preserved ALWAYS.
        # The serializer never content-sniff-sorts lists -- reordering a list is a
        # different logical value, so an order-significant field (params, imports,
        # ...) MUST hash differently when reordered (BUG-1). The only authorized
        # reorders are the explicit, field-keyed set-semantic sorts applied below
        # in canonicalize_boundary_ir() (top-level files/nodes/edges/diagnostics,
        # plus candidates / relationships / failure_buckets / file diagnostics).
        return [_canonicalize_value(item) for item in value]
    return value


def canonicalize_boundary_ir(ir: dict[str, Any]) -> dict[str, Any]:
    """Return a canonicalized copy of a Boundary IR dictionary."""
    canonical = _canonicalize_value(deepcopy(ir))
    if not isinstance(canonical, dict):
        msg = "Boundary IR must be a dictionary"
        raise TypeError(msg)

    canonical["files"] = sorted(
        canonical.get("files", []),
        key=lambda item: (item.get("path") or "", item.get("id") or ""),
    )
    canonical["nodes"] = sorted(
        canonical.get("nodes", []),
        key=lambda item: (
            item.get("id") or "",
            item.get("path") or "",
            _span_start_line(item),
        ),
    )
    canonical["edges"] = sorted(
        canonical.get("edges", []),
        key=lambda item: (
            item.get("source") or "",
            item.get("target") or "",
            item.get("type") or "",
            item.get("id") or "",
        ),
    )
    canonical["diagnostics"] = sorted(
        canonical.get("diagnostics", []),
        key=lambda item: (
            item.get("path") or "",
            _location_start_line(item),
            item.get("code") or "",
            item.get("id") or "",
        ),
    )

    # Explicit, field-keyed set-semantic sorts (canon S4: only schema-declared
    # order-insensitive lists may be ordered, and that ordering is the caller's,
    # done before/at canonicalization -- NOT a content-sniff over arbitrary
    # string lists). These are the only authorized array reorders besides the
    # top-level files/nodes/edges/diagnostics sorts above. Every other list
    # (params, imports, ...) preserves insertion order via _canonicalize_value.
    for edge in canonical.get("edges", []):
        if isinstance(edge, dict) and isinstance(edge.get("candidates"), list):
            edge["candidates"] = sorted(edge["candidates"])
    for node in canonical.get("nodes", []):
        if isinstance(node, dict) and isinstance(node.get("relationships"), list):
            node["relationships"] = sorted(node["relationships"])
    for file_record in canonical.get("files", []):
        if isinstance(file_record, dict) and isinstance(
            file_record.get("diagnostics"), list
        ):
            file_record["diagnostics"] = sorted(file_record["diagnostics"])
    return canonical


def dumps_boundary_ir(ir: dict[str, Any], *, pretty: bool = False) -> str:
    """Serialize Boundary IR as UTF-8-compatible JSON text with one newline."""
    canonical = canonicalize_boundary_ir(ir)
    if pretty:
        return json.dumps(canonical, indent=2, sort_keys=True) + "\n"
    return json.dumps(canonical, separators=(",", ":"), sort_keys=True) + "\n"


def _strip_parity_volatile(canonical: dict[str, Any]) -> dict[str, Any]:
    """Drop volatile/provenance fields that must not enter the parity hash (BUG-2).

    Excludes the absolute ``source.path`` and the volatile ``run`` fields
    (root, created_at, tool_version, timings). The fields stay in the full
    emitted document (``dumps_boundary_ir``) for humans/debuggers -- only the
    parity view drops them.
    """
    source = canonical.get("source")
    if isinstance(source, dict):
        source.pop("path", None)
    run = canonical.get("run")
    if isinstance(run, dict):
        for field in _PARITY_EXCLUDED_RUN_FIELDS:
            run.pop(field, None)
    return canonical


def _floats_to_strings(value: Any) -> Any:
    """Recursively convert every float to its string repr (canon S6).

    canon rejects ALL real numbers (cross-language float formatting is the single
    largest source of byte-divergence), so any float in the IR -- semantic-edge
    ``confidence``, ``run.options.semantic_min_confidence``, or any future field
    -- is pre-represented as a string before canon sees it. The conversion is
    generic (never a hand-enumerated field list) and deterministic: within a
    field the type is stable, so this can never itself cause divergence.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, dict):
        return {key: _floats_to_strings(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_floats_to_strings(item) for item in value]
    return value


def canonicalize_for_parity(ir: dict[str, Any]) -> dict[str, Any]:
    """Return the parity-hashable view of a Boundary IR (BUG-2).

    Pipeline: canonicalize (apply the top-level + set-semantic sorts) -> strip
    volatile fields (source.path, run.{root,created_at,tool_version,timings}) ->
    pre-represent floats as strings. The result is a canon-compatible value: feed
    it to ``canonicalize_for_parity_bytes`` / ``parity_digest`` for the actual
    hash. This is the first-class API ``spec`` and other canon consumers call so
    they never hand-strip volatile fields.
    """
    canonical = canonicalize_boundary_ir(ir)
    canonical = _strip_parity_volatile(canonical)
    return _floats_to_strings(canonical)


def canonicalize_for_parity_bytes(ir: dict[str, Any]) -> bytes:
    """canon canonical UTF-8 bytes of the parity view (cross-tool byte-identity).

    Routes the parity view through the vendored canon serializer so the bytes are
    byte-identical to every other canon consumer (spec, greenfield, codegraph-de)
    -- not merely self-consistent JSON.
    """
    return _canon.canonical_bytes(canonicalize_for_parity(ir))


def parity_digest(ir: dict[str, Any]) -> str:
    """Lowercase-hex SHA-256 canon digest of the Boundary IR parity view (BUG-2)."""
    return _canon.digest(canonicalize_for_parity(ir), _PARITY_DIGEST_PROFILE)

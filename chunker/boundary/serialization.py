"""Canonical Boundary IR JSON serialization."""

from __future__ import annotations

import json
from copy import deepcopy
from typing import Any


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
        canonical = [_canonicalize_value(item) for item in value]
        if all(isinstance(item, str) for item in canonical):
            return sorted(canonical)
        return canonical
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
    return canonical


def dumps_boundary_ir(ir: dict[str, Any], *, pretty: bool = False) -> str:
    """Serialize Boundary IR as UTF-8-compatible JSON text with one newline."""
    canonical = canonicalize_boundary_ir(ir)
    if pretty:
        return json.dumps(canonical, indent=2, sort_keys=True) + "\n"
    return json.dumps(canonical, separators=(",", ":"), sort_keys=True) + "\n"

"""Persistent cache records for incremental Boundary IR extraction."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .types import (
    BOUNDARY_CACHE_KEY_FIELDS,
    BOUNDARY_CACHE_KEY_PREFIX,
    BOUNDARY_CACHE_VERSION,
    BOUNDARY_IR_SCHEMA_VERSION,
)


def build_boundary_cache_key(payload: dict[str, Any]) -> str:
    """Build a deterministic Boundary IR cache key from frozen fields."""
    key_payload = {field: payload.get(field) for field in BOUNDARY_CACHE_KEY_FIELDS}
    encoded = json.dumps(
        key_payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return BOUNDARY_CACHE_KEY_PREFIX + hashlib.sha256(encoded).hexdigest()


def _record_filename(cache_key: str) -> str:
    return cache_key.replace(":", "_") + ".json"


@dataclass
class BoundaryCacheRecord:
    path: str
    content_hash: str
    cache_key: str
    key_payload: dict[str, Any]
    file_record: dict[str, Any]
    node_records: list[dict[str, Any]]
    symbol_facts: dict[str, Any]
    diagnostics: list[dict[str, Any]]
    dependency_summary: dict[str, Any]
    schema_version: str = BOUNDARY_IR_SCHEMA_VERSION
    cache_version: str = BOUNDARY_CACHE_VERSION

    def to_json(self) -> dict[str, Any]:
        return {
            "cache_key": self.cache_key,
            "cache_version": self.cache_version,
            "content_hash": self.content_hash,
            "dependency_summary": self.dependency_summary,
            "diagnostics": self.diagnostics,
            "file_record": self.file_record,
            "key_payload": self.key_payload,
            "node_records": self.node_records,
            "path": self.path,
            "schema_version": self.schema_version,
            "symbol_facts": self.symbol_facts,
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "BoundaryCacheRecord":
        if data.get("cache_version") != BOUNDARY_CACHE_VERSION:
            msg = "Boundary cache record version mismatch"
            raise ValueError(msg)
        if data.get("schema_version") != BOUNDARY_IR_SCHEMA_VERSION:
            msg = "Boundary cache record schema mismatch"
            raise ValueError(msg)
        required = (
            "path",
            "content_hash",
            "cache_key",
            "key_payload",
            "file_record",
            "node_records",
            "symbol_facts",
            "diagnostics",
            "dependency_summary",
        )
        missing = [key for key in required if key not in data]
        if missing:
            msg = f"Boundary cache record missing fields: {', '.join(missing)}"
            raise ValueError(msg)
        return cls(
            path=str(data["path"]),
            content_hash=str(data["content_hash"]),
            cache_key=str(data["cache_key"]),
            key_payload=dict(data["key_payload"]),
            file_record=dict(data["file_record"]),
            node_records=list(data["node_records"]),
            symbol_facts=dict(data["symbol_facts"]),
            diagnostics=list(data["diagnostics"]),
            dependency_summary=dict(data["dependency_summary"]),
            schema_version=str(data["schema_version"]),
            cache_version=str(data["cache_version"]),
        )


@dataclass
class BoundaryCacheIndex:
    records: dict[str, str] = field(default_factory=dict)
    content_hashes: dict[str, str] = field(default_factory=dict)
    cache_version: str = BOUNDARY_CACHE_VERSION
    schema_version: str = BOUNDARY_IR_SCHEMA_VERSION

    def to_json(self) -> dict[str, Any]:
        return {
            "cache_version": self.cache_version,
            "content_hashes": self.content_hashes,
            "records": self.records,
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "BoundaryCacheIndex":
        if data.get("cache_version") != BOUNDARY_CACHE_VERSION:
            return cls()
        if data.get("schema_version") != BOUNDARY_IR_SCHEMA_VERSION:
            return cls()
        return cls(
            records={str(k): str(v) for k, v in dict(data.get("records", {})).items()},
            content_hashes={
                str(k): str(v) for k, v in dict(data.get("content_hashes", {})).items()
            },
        )


def load_cache_index(cache_dir: Path) -> BoundaryCacheIndex:
    try:
        data = json.loads((cache_dir / "index.json").read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return BoundaryCacheIndex()
        return BoundaryCacheIndex.from_json(data)
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return BoundaryCacheIndex()


def save_cache_index(cache_dir: Path, index: BoundaryCacheIndex) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    _atomic_write_json(cache_dir / "index.json", index.to_json())


def load_cache_record(cache_dir: Path, cache_key: str) -> BoundaryCacheRecord | None:
    try:
        data = json.loads(
            (cache_dir / _record_filename(cache_key)).read_text(encoding="utf-8")
        )
        if not isinstance(data, dict):
            return None
        record = BoundaryCacheRecord.from_json(data)
        if record.cache_key != cache_key:
            return None
        return record
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return None


def save_cache_record(cache_dir: Path, record: BoundaryCacheRecord) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    _atomic_write_json(cache_dir / _record_filename(record.cache_key), record.to_json())


def prune_cache_record(cache_dir: Path, cache_key: str) -> None:
    try:
        (cache_dir / _record_filename(cache_key)).unlink()
    except FileNotFoundError:
        pass


def _atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    tmp_path = path.with_name(path.name + ".tmp")
    tmp_path.write_text(
        json.dumps(data, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    tmp_path.replace(path)

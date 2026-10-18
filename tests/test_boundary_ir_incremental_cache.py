import json
from pathlib import Path

from chunker.boundary.cache import (
    BoundaryCacheIndex,
    BoundaryCacheRecord,
    build_boundary_cache_key,
    load_cache_index,
    load_cache_record,
    save_cache_index,
    save_cache_record,
)
from chunker.boundary.types import BOUNDARY_IR_SCHEMA_VERSION


def _payload(**overrides):
    payload = {
        "path": "app.py",
        "content_hash": "sha1:abc",
        "language": "python",
        "grammar_version": "tree-sitter-python",
        "tool_version": "1",
        "schema_version": "1.0",
        "resolution_mode": "strict",
        "fail_fast": False,
        "include_retrieval_metadata": True,
        "created_at": "ignored",
    }
    payload.update(overrides)
    return payload


def _record(cache_key: str) -> BoundaryCacheRecord:
    return BoundaryCacheRecord(
        path="app.py",
        content_hash="sha1:abc",
        cache_key=cache_key,
        key_payload=_payload(),
        file_record={"path": "app.py", "content_hash": "sha1:abc"},
        node_records=[{"id": "node:1"}],
        symbol_facts={"path": "app.py", "chunk_records": []},
        diagnostics=[],
        dependency_summary={"exports": ["build"], "references": []},
    )


def test_cache_key_is_stable_and_changes_for_included_fields():
    first = build_boundary_cache_key(_payload())
    reordered = build_boundary_cache_key(dict(reversed(list(_payload().items()))))

    assert first == reordered
    assert first.startswith("boundary:v2:")
    assert first != build_boundary_cache_key(_payload(content_hash="sha1:def"))


def test_excluded_option_fields_do_not_change_cache_key():
    baseline = build_boundary_cache_key(_payload())

    assert baseline == build_boundary_cache_key(
        _payload(
            created_at="later",
            canonical=False,
            include_timings=True,
            incremental=True,
            cache_dir="/tmp/cache",
            force_rebuild=True,
        )
    )


def test_cache_record_and_index_round_trip_as_utf8_json(tmp_path: Path):
    cache_key = build_boundary_cache_key(_payload())
    record = _record(cache_key)
    index = BoundaryCacheIndex(
        records={"app.py": cache_key}, content_hashes={"app.py": "sha1:abc"}
    )

    save_cache_record(tmp_path, record)
    save_cache_index(tmp_path, index)

    assert load_cache_record(tmp_path, cache_key) == record
    assert load_cache_index(tmp_path) == index
    assert json.loads((tmp_path / "index.json").read_text(encoding="utf-8"))[
        "records"
    ] == {"app.py": cache_key}


def test_malformed_cache_records_are_misses(tmp_path: Path):
    cache_key = build_boundary_cache_key(_payload())
    (tmp_path / cache_key.replace(":", "_")).with_suffix(".json").write_text(
        "{not json",
        encoding="utf-8",
    )

    assert load_cache_record(tmp_path, cache_key) is None
    assert load_cache_index(tmp_path) == BoundaryCacheIndex()


def test_496_anchor_same_schema_v1_cache_is_a_miss(tmp_path: Path):
    cache_key = "boundary:v1:" + "0" * 64
    record = _record(cache_key).to_json()
    record["key_payload"]["schema_version"] = BOUNDARY_IR_SCHEMA_VERSION
    record["cache_version"] = "1"
    record["schema_version"] = BOUNDARY_IR_SCHEMA_VERSION
    (tmp_path / cache_key.replace(":", "_")).with_suffix(".json").write_text(
        json.dumps(record),
        encoding="utf-8",
    )
    (tmp_path / "index.json").write_text(
        json.dumps(
            {
                "cache_version": "1",
                "schema_version": BOUNDARY_IR_SCHEMA_VERSION,
                "records": {"app.py": cache_key},
                "content_hashes": {"app.py": "sha1:abc"},
            }
        ),
        encoding="utf-8",
    )

    assert load_cache_record(tmp_path, cache_key) is None
    assert load_cache_index(tmp_path) == BoundaryCacheIndex()

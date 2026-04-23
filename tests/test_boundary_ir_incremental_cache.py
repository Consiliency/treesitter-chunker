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
    assert first.startswith("boundary:v1:")
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

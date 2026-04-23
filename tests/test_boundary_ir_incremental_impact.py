from chunker.boundary.cache import BoundaryCacheIndex, BoundaryCacheRecord
from chunker.boundary.impact import compute_impacted_paths, detect_changed_paths


def _record(path: str, *, exports=(), references=(), endpoints=()):
    return BoundaryCacheRecord(
        path=path,
        content_hash=f"sha1:{path}",
        cache_key=f"boundary:v1:{path}",
        key_payload={},
        file_record={"path": path},
        node_records=[],
        symbol_facts={},
        diagnostics=[],
        dependency_summary={
            "exports": list(exports),
            "module": path.removesuffix(".py"),
            "references": list(references),
            "relationship_endpoints": list(endpoints),
        },
    )


def test_no_change_warm_run_has_empty_recompute_set():
    index = BoundaryCacheIndex(
        records={"a.py": "key"},
        content_hashes={"a.py": "sha1:a"},
    )

    changed, deleted = detect_changed_paths({"a.py": "sha1:a"}, index)

    assert changed == []
    assert deleted == []


def test_added_deleted_and_changed_paths_are_sorted():
    index = BoundaryCacheIndex(
        records={"a.py": "key-a", "z.py": "key-z"},
        content_hashes={"a.py": "old", "z.py": "sha1:z"},
    )

    changed, deleted = detect_changed_paths(
        {"a.py": "new", "b.py": "sha1:b"},
        index,
        invalid_paths={"b.py"},
    )

    assert changed == ["a.py", "b.py"]
    assert deleted == ["z.py"]


def test_reverse_references_pull_impacted_neighbors():
    records = {
        "helper.py": _record("helper.py", exports=["Helper"]),
        "service.py": _record("service.py", references=["Helper"]),
        "unrelated.py": _record("unrelated.py", references=["Other"]),
    }

    impacted = compute_impacted_paths(["helper.py"], [], records)

    assert impacted == ["helper.py", "service.py"]

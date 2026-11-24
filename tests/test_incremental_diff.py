import subprocess
import sys
import tracemalloc
from dataclasses import asdict, replace
from pathlib import Path

import pytest

from chunker import chunk_text
from chunker.incremental import DefaultIncrementalProcessor, SimpleIncrementalIndex
from chunker.interfaces.incremental import ChangeType, ChunkChange, ChunkDiff
from chunker.types import CodeChunk


def test_move_attribution_uses_source_order_for_ambiguous_candidates():
    old = chunk_text(
        "def foo():\n    return 1\n\ndef bar():\n    return 1\n",
        "python",
        file_path="a.py",
    )
    source = "\n" * 5 + "def baz():\n    return 1\n"
    new = chunk_text(source, "python", file_path="a.py")
    processor = DefaultIncrementalProcessor()
    for ordered in (old, list(reversed(old))):
        pairs = processor.detect_moved_chunks(ordered, new)
        assert [(a.chunk_id, b.chunk_id) for a, b in pairs] == [
            (old[0].chunk_id, new[0].chunk_id)
        ]
        diff = processor.compute_diff(ordered, source, "python")
        assert [
            (change.old_chunk.chunk_id, change.new_chunk.chunk_id)
            for change in diff.changes
            if change.change_type == ChangeType.MOVED
        ] == [(old[0].chunk_id, new[0].chunk_id)]
        assert [asdict(c) for c in processor.update_chunks(ordered, diff)] == [
            asdict(c) for c in new
        ]


def _chunk(
    content: str, *, definition_id: str, file_path: str = "src/example.py"
) -> CodeChunk:
    return CodeChunk(
        language="python",
        file_path=file_path,
        node_type="function_definition",
        start_line=1,
        end_line=2,
        byte_start=0,
        byte_end=len(content.encode("utf-8")),
        parent_context="",
        content=content,
        qualified_route=["function_definition:example"],
        definition_id=definition_id,
    )


def test_content_diff_reparses_with_path_and_definition_identity(monkeypatch):
    old = _chunk("def example():\n    return 1\n", definition_id="definition")
    seen = {}

    def reparse(content, language, file_path):
        seen.update(content=content, language=language, file_path=file_path)
        return [_chunk(content, definition_id="definition", file_path=file_path)]

    monkeypatch.setattr("chunker.incremental.chunk_text", reparse)
    diff = DefaultIncrementalProcessor().compute_diff(
        [old],
        "def example():\n    return 2\n",
        "python",
    )

    assert seen["file_path"] == "src/example.py"
    assert diff.summary["modified"] == 1
    assert diff.summary["added"] == diff.summary["deleted"] == 0
    assert diff.changes[0].change_type is ChangeType.MODIFIED


def test_overload_diff_preserves_every_definition():
    source = "class A { int foo(int a) { return 1; } int foo(String a) { return 2; } int foo(int a, int b) { return 3; } }"
    old = chunk_text(source, "java", file_path="A.java")
    new = chunk_text(source.replace("return 2", "return 4"), "java", file_path="A.java")
    processor = DefaultIncrementalProcessor()
    processor.store_chunks("A.java", old)
    diff = processor.compute_diff("A.java", new)
    assert len(old) == len(new) == 4
    assert sum(diff.summary[k] for k in ("added", "modified", "unchanged")) == len(new)
    assert [asdict(c) for c in processor.update_chunks(old, diff)] == [
        asdict(c) for c in new
    ]
    content_diff = processor.compute_diff(
        old, source.replace("return 2", "return 4"), "java"
    )
    assert [asdict(c) for c in processor.update_chunks(old, content_diff)] == [
        asdict(c) for c in new
    ]


def test_update_body_edit_removes_previous_occurrence():
    old = chunk_text("def f():\n    return 1\n", "python", file_path="a.py")
    new = chunk_text("def f():\n    return 2\n", "python", file_path="a.py")
    processor = DefaultIncrementalProcessor()
    processor.store_chunks("a.py", old)
    updated = processor.update_chunks(old, processor.compute_diff("a.py", new))
    assert [c.chunk_id for c in updated] == [c.chunk_id for c in new]


def test_update_refreshes_unchanged_chunk_positions():
    source = "def f():\n    return 1\n\ndef g():\n    return 2\n"
    old = chunk_text(source, "python", file_path="a.py")
    new = chunk_text(
        source.replace("return 1", "return 10000"), "python", file_path="a.py"
    )
    processor = DefaultIncrementalProcessor()
    processor.store_chunks("a.py", old)
    diff = processor.compute_diff("a.py", new)
    assert diff.summary["unchanged"] == 1
    updated = processor.update_chunks(old, diff)
    assert [c.chunk_id for c in updated] == [c.chunk_id for c in new]
    assert [c.byte_start for c in updated] == [c.byte_start for c in new]


def test_multiline_overload_deletion_and_relocation_reconstructs_new_file():
    old_source = (
        "class A {\n"
        "  int foo(int a) { return 1; }\n"
        "  int foo(long a) { return 1; }\n"
        "}\n"
    )
    new_source = "class A {\n\n\n  int foo(int a) { return 1; }\n}\n"
    old = chunk_text(old_source, "java", file_path="A.java")
    new = chunk_text(new_source, "java", file_path="A.java")
    processor = DefaultIncrementalProcessor()
    for previous in (old, list(reversed(old))):
        diff = processor.compute_diff(previous, new_source, "java")
        updated = processor.update_chunks(previous, diff)
        assert len(updated) == len(new) == 2
        assert [asdict(c) for c in updated] == [asdict(c) for c in new]
        assert diff.summary["moved"] == 0
        assert sum(
            diff.summary[k] for k in ("added", "modified", "moved", "unchanged")
        ) == len(new)
        assert sum(
            diff.summary[k] for k in ("deleted", "modified", "moved", "unchanged")
        ) == len(old)


def test_move_detection_never_reuses_a_target():
    old = chunk_text(
        "def foo():\n    return 1\n\ndef bar():\n    return 1\n",
        "python",
        file_path="a.py",
    )
    new = chunk_text("\n\n\n\n\ndef baz():\n    return 1\n", "python", file_path="a.py")
    matches = DefaultIncrementalProcessor.detect_moved_chunks(old, new)
    assert len(matches) == 1
    assert len({after.chunk_id for _, after in matches}) == len(matches)


def test_duplicate_python_definition_reduction_and_relocation():
    body = "def f():\n    return 1\n"
    old = chunk_text(body + "\n" + body, "python", file_path="a.py")
    new_source = "\n" + body
    expected = chunk_text(new_source, "python", file_path="a.py")
    processor = DefaultIncrementalProcessor()
    diff = processor.compute_diff(old, new_source, "python")
    assert [asdict(c) for c in processor.update_chunks(old, diff)] == [
        asdict(c) for c in expected
    ]
    assert diff.summary["moved"] == 0
    assert diff.summary["deleted"] == 2
    assert diff.summary["added"] == 1


def test_move_detection_preserves_complete_collision_context():
    body = "def f():\n    return 1\n"
    old = chunk_text(body + "\n" + body, "python", file_path="a.py")
    new_source = body + "\n\n" + body
    expected = chunk_text(new_source, "python", file_path="a.py")
    processor = DefaultIncrementalProcessor()
    diff = processor.compute_diff(old, new_source, "python")
    assert diff.summary["unchanged"] == 1
    assert diff.summary["moved"] == 0
    assert diff.summary["added"] == diff.summary["deleted"] == 1
    assert [asdict(c) for c in processor.update_chunks(old, diff)] == [
        asdict(c) for c in expected
    ]


def test_unchanged_method_refreshes_parent_identity_and_stored_state():
    source = "class A { int f() { return 1; } int x = 1; }"
    old = [
        c
        for c in chunk_text(source, "java", file_path="A.java")
        if c.node_type == "method_declaration"
    ]
    expected = [
        c
        for c in chunk_text(
            source.replace("x = 1", "x = 2"), "java", file_path="A.java"
        )
        if c.node_type == "method_declaration"
    ]
    assert old[0].chunk_id == expected[0].chunk_id
    assert old[0].parent_chunk_id != expected[0].parent_chunk_id
    processor = DefaultIncrementalProcessor()
    processor.store_chunks("A.java", old)
    diff = processor.compute_diff("A.java", expected)
    assert diff.changes == []
    fields = [asdict(c) for c in expected]
    assert [asdict(c) for c in diff.unchanged_chunks] == fields
    assert [asdict(c) for c in processor.update_chunks(old, diff)] == fields
    assert [asdict(c) for c in processor.file_chunks["A.java"]] == fields


def _rebuilt(chunks):
    index = SimpleIncrementalIndex()
    for chunk in chunks:
        index.update_chunk(None, chunk)
    return index


@pytest.mark.parametrize("api", ["list", "content", "stored_content"])
@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_index_tracks_successive_source_shifts(api, newline):
    path = "a.py"
    body = newline.join(("def f():", "    return 1", ""))
    other = chunk_text(body, "python", file_path="other.py")
    old = chunk_text(body, "python", file_path=path)
    index = _rebuilt(old + other)
    processor = DefaultIncrementalProcessor()
    processor.store_chunks(path, old)
    for shift in (1, 2, 2):
        source = newline * shift + body
        new = chunk_text(source, "python", file_path=path)
        if api == "list":
            diff = processor.compute_diff(path, new)
            assert diff.added == diff.removed == diff.modified == []
        elif api == "content":
            diff = processor.compute_diff(old, source, "python")
        else:
            diff = processor.compute_diff(path, source, "python")
            processor.store_chunks(path, new)
        assert diff.summary["unchanged"] == 1
        assert diff.summary["modified"] == 0
        assert diff.changes == []
        assert [c.chunk_id for c in diff.unchanged_chunks] == [new[0].chunk_id]
        changed = old[0].chunk_id != new[0].chunk_id
        pairs = [(old[0].chunk_id, new[0].chunk_id)] if changed else []
        assert [(a.chunk_id, b.chunk_id) for a, b in diff.occurrence_updates] == pairs
        assert index.get_update_cost(diff) == len(pairs) / 2
        before = len(index.update_log)
        index.batch_update(diff)
        events = index.update_log[before:]
        assert [(e["old_id"], e["new_id"]) for e in events] == pairs
        assert all(e["action"] == "update" for e in events)
        fresh = _rebuilt(new + other)
        assert index.index == fresh.index
        assert sorted(index.search("DEF F")) == sorted(fresh.search("DEF F"))
        assert len(index.search("DEF F")) == 2
        assert index.index[new[0].chunk_id]["line_range"] == (1 + shift, 2 + shift)
        if shift == 1 and newline == "\n":
            assert old[0].start_line == 1
            assert old[0].chunk_id == "dfb9527c729f936e770bbf5bdc5df5fdd092ea67"
            assert new[0].chunk_id == "4cecc8b4404968a6014ba21cc90f1a5497c7fcd0"
        old = new


@pytest.mark.parametrize(
    ("old_prefix", "new_prefix", "same_id"),
    [("  ", "\n\n", True), ("#a\n", "#ab\n", False)],
)
def test_index_tracks_independent_byte_and_line_shifts(old_prefix, new_prefix, same_id):
    body = "def f():\n    return 1\n"
    old = chunk_text(old_prefix + body, "python", file_path="a.py")
    new = chunk_text(new_prefix + body, "python", file_path="a.py")
    assert (old[0].chunk_id == new[0].chunk_id) == same_id
    assert (old[0].start_line != new[0].start_line) == same_id
    diff = DefaultIncrementalProcessor().compute_diff(old, new_prefix + body, "python")
    index = _rebuilt(old)
    index.batch_update(diff)
    assert len(diff.occurrence_updates) == 1
    assert index.index == _rebuilt(new).index


@pytest.mark.parametrize(
    ("field", "value", "affected"),
    [
        ("start_line", 2, True),
        ("end_line", 3, True),
        ("file_path", "other.py", True),
        ("node_type", "other_type", True),
        ("parent_chunk_id", "parent", False),
        ("metadata", {"key": "value"}, False),
    ],
)
def test_same_id_payload_updates(field, value, affected):
    (old,) = chunk_text("def f():\n    return 1", "python", file_path="a.py")
    new = replace(old, **{field: value})
    processor = DefaultIncrementalProcessor()
    processor.store_chunks("a.py", [old])
    diff = processor.compute_diff("a.py", [new])
    index = _rebuilt([old])
    assert diff.unchanged_chunks[0] is new
    assert diff.changes == []
    assert index.get_update_cost(diff) == int(affected)
    index.batch_update(diff)
    assert len(index.update_log) == 1 + int(affected)
    assert index.index == {
        old.chunk_id: {
            "content": "def f():\n    return 1",
            "file_path": value if field == "file_path" else "a.py",
            "node_type": value if field == "node_type" else "function_definition",
            "line_range": (
                value if field == "start_line" else 1,
                value if field == "end_line" else 2,
            ),
        }
    }


@pytest.mark.parametrize("reverse", [False, True])
def test_index_handles_one_sided_duplicate_routes(reverse):
    body = "def f():\n    return 1\n"
    previous, current = body + "\n" + body, "\n" + body
    if reverse:
        previous, current = current, previous
    old = chunk_text(previous, "python", file_path="a.py")
    new = chunk_text(current, "python", file_path="a.py")
    diff = DefaultIncrementalProcessor().compute_diff(old, current, "python")
    assert diff.summary["added"] == len(new)
    assert diff.summary["deleted"] == len(old)
    assert diff.summary["moved"] == 0
    assert diff.occurrence_updates == []
    index = _rebuilt(old)
    index.batch_update(diff)
    assert index.index == _rebuilt(new).index
    assert len(index.search("def f")) == len(new)


def test_index_applies_mixed_edits_and_refreshes():
    old_source = "def gone(): pass\n\ndef edit(): return 1\n\ndef same(): return 3"
    source = "class Added: pass\n\ndef edit(): return 12\n\ndef same(): return 3"
    old = chunk_text(old_source, "python", file_path="a.py")
    new = chunk_text(source, "python", file_path="a.py")
    diff = DefaultIncrementalProcessor().compute_diff(old, source, "python")
    assert [diff.summary[k] for k in ("added", "deleted", "modified", "unchanged")] == [
        1
    ] * 4
    assert len(diff.occurrence_updates) == 1
    index = _rebuilt(old)
    index.batch_update(diff)
    assert index.index == _rebuilt(new).index
    assert len(index.update_log) == len(old) + 4


def test_batch_retires_all_old_ids_before_publishing():
    old = _chunk("first", definition_id="first")
    other = _chunk("second", definition_id="second")
    edited = replace(old, chunk_id=other.chunk_id, content="changed")
    shifted = replace(other, chunk_id=old.chunk_id, start_line=2)
    change = ChunkChange(edited.chunk_id, ChangeType.MODIFIED, old, edited, [], 1.0)
    diff = ChunkDiff(
        [change], [], [], [(old, edited)], [shifted], {}, [(other, shifted)]
    )
    index = _rebuilt([old, other])
    index.batch_update(diff)
    assert index.index == _rebuilt([edited, shifted]).index
    assert [e["action"] for e in index.update_log] == ["add", "add", "update", "update"]


@pytest.mark.parametrize(
    "regions",
    [[], [(2, 2)], [(5, 3)], [(6, 7), (3, 5), (3, 5), (4, 4), (9, 9), (3, 1)]],
)
def test_merge_matches_bounded_line_set_oracle(regions):
    base = _chunk("body", definition_id="one")
    full = [
        replace(
            base,
            chunk_id=f"{path}-{start}-{end}",
            file_path=path,
            start_line=start,
            end_line=end,
        )
        for path in ("b.py", "a.py")
        for start in range(1, 11)
        for end in range(1, 11)
    ]
    incremental = [replace(full[0]), replace(full[0])]
    changed = {line for a, b in regions for line in range(a, b + 1)}
    supplied = {c.chunk_id for c in incremental}
    retained = [
        c
        for c in full
        if c.chunk_id not in supplied
        and changed.isdisjoint(range(c.start_line, c.end_line + 1))
    ]
    expected = sorted(incremental + retained, key=lambda c: (c.file_path, c.start_line))
    actual = DefaultIncrementalProcessor.merge_incremental_results(
        full, incremental, regions
    )
    assert list(map(id, actual)) == list(map(id, expected))


def _measure_merge_peak():
    merge = DefaultIncrementalProcessor.merge_incremental_results
    for region_end, chunk_end in ((100, 200100), (100000, 200100), (100, 300000)):
        chunk = replace(
            _chunk("body", definition_id="one"), start_line=200001, end_line=chunk_end
        )
        full, incremental, regions = [chunk], [], [(1, region_end)]
        tracemalloc.start()
        try:
            result = merge(full, incremental, regions)
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        assert len(result) == 1 and result[0] is chunk
        assert peak < 512 * 1024, (region_end, chunk_end, peak)


def test_merge_allocation_is_independent_of_both_span_lengths():
    # Keep fixtures, parser imports and pytest's allocations outside each measurement.
    subprocess.run(
        [
            sys.executable,
            "-c",
            "import runpy, sys; runpy.run_path(sys.argv[1])['_measure_merge_peak']()",
            str(Path(__file__).resolve()),
        ],
        check=True,
    )

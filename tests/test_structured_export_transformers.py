"""Registration and composition through the public structured export entry points."""

import json
import sqlite3
from contextlib import closing
from dataclasses import asdict
from types import SimpleNamespace

import pytest

from chunker.exceptions import ChunkerError
from chunker.export import (
    SQLiteExporter,
    StructuredExportOrchestrator,
    StructuredJSONExporter,
    StructuredJSONLExporter,
)
from chunker.interfaces.export import (
    ChunkRelationship,
    ExportFormat,
    ExportMetadata,
    RelationshipType,
)
from chunker.types import CodeChunk


def chunk(key):
    return CodeChunk(
        language="python",
        file_path="src/π.py",
        node_type="function_definition",
        start_line=1,
        end_line=2,
        byte_start=3,
        byte_end=13,
        parent_context="",
        content=f"{key}\r\n",
        chunk_id=key,
        parent_chunk_id="one" if key == "two" else None,
        qualified_route=["function:" + key],
        metadata={"original": [1]},
    )


def edge(target="two"):
    return ChunkRelationship("one", target, RelationshipType.CALLS, {"original": [1]})


def pipeline(writer, fmt=ExportFormat.JSON):
    export = StructuredExportOrchestrator()
    export.register_exporter(fmt, writer)
    return export


def dispatch(export, chunks, edges, path, streaming):
    if streaming:
        export.export_streaming(iter(chunks), iter(edges), path)
    else:
        export.export(chunks, edges, path)


@pytest.mark.parametrize("streaming", [False, True])
@pytest.mark.parametrize("fmt", ["json", "jsonl", "parquet", "sqlite"])
def test_serialized_payload(tmp_path, streaming, fmt):
    if fmt == "parquet":
        pq = pytest.importorskip("pyarrow.parquet")
        from chunker.export.formats.parquet import StructuredParquetExporter

        writer = StructuredParquetExporter()
        writer.set_batch_size(1)
    else:
        writer = {
            "json": StructuredJSONExporter,
            "jsonl": StructuredJSONLExporter,
            "sqlite": SQLiteExporter,
        }[fmt]()
    export = pipeline(writer, ExportFormat(fmt))
    export.add_filter(
        SimpleNamespace(
            should_include_chunk=lambda c: c.chunk_id != "drop",
            should_include_relationship=lambda r: r.target_chunk_id != "rejected",
        )
    )
    calls = []

    class First:
        def transform_chunk(self, c):
            calls.append(("A", c.chunk_id))
            return {"content": f"[{c.content}]", "metadata": {"stage": [1]}}

        def transform_relationship(self, r):
            calls.append(("A", r.target_chunk_id))
            return {
                "relationship_type": "uses",
                "metadata": {**r.metadata, "stage": [1]},
            }

    class Second:
        def transform_chunk(self, c):
            calls.append(("B", c.chunk_id))
            return {"content": f"{c.content}:{c.metadata['stage'][0]}"}

        def transform_relationship(self, r):
            calls.append(("B", r.target_chunk_id))
            assert r.relationship_type is RelationshipType.USES
            return {"relationship_type": RelationshipType.REFERENCES}

    export.add_transformer(First())
    export.add_transformer(Second())
    path = tmp_path / f"data-{streaming}.{fmt}"
    edges = [edge(), edge("rejected")]
    if fmt == "json":
        edges.append(edge("drop"))
    dispatch(
        export, [chunk("one"), chunk("drop"), chunk("two")], edges, path, streaming
    )
    if fmt == "sqlite":
        with closing(sqlite3.connect(path)) as db:
            rows = db.execute(
                """SELECT a.content, b.content, r.relationship_type
                FROM relationships r JOIN chunks a ON r.source_chunk_id=a.chunk_id
                JOIN chunks b ON r.target_chunk_id=b.chunk_id"""
            ).fetchall()
        assert rows == [("[one\r\n]:1", "[two\r\n]:1", "references")]
    else:
        if fmt == "json":
            data = json.loads(path.read_text(encoding="utf-8"))
            chunks, rels = data["chunks"], data["relationships"]
            assert [c["metadata"] for c in chunks] == [{"stage": [1]}] * 2
            assert [r["target_chunk_id"] for r in rels] == ["two", "drop"]
        elif fmt == "jsonl":
            lines = list(map(json.loads, path.read_text(encoding="utf-8").splitlines()))
            assert [r["type"] for r in lines] == [
                "metadata",
                "chunk",
                "chunk",
                "relationship",
            ]
            chunks, rels = [r["data"] for r in lines[1:3]], [lines[3]["data"]]
        else:

            def read_sidecar(kind):
                with pq.ParquetFile(tmp_path / f"{path.stem}_{kind}.parquet") as file:
                    return file.read(use_threads=False).to_pylist()

            chunks, rels = read_sidecar("chunks"), read_sidecar("relationships")
            rels[0]["metadata"] = json.loads(rels[0]["metadata"])
        assert [c["content"] for c in chunks] == ["[one\r\n]:1", "[two\r\n]:1"]
        assert [c["chunk_id"] for c in chunks] == ["one", "two"]
        assert chunks[1]["parent_chunk_id"] == "one"
        for c in chunks:
            assert (
                c["file_path"],
                c["byte_start"],
                c["byte_end"],
                c["start_line"],
                c["end_line"],
            ) == ("src/π.py", 3, 13, 1, 2)
            if fmt != "json":
                assert "metadata" not in c
        assert rels[0] == {
            "source_chunk_id": "one",
            "target_chunk_id": "two",
            "relationship_type": "references",
            "metadata": {"original": [1], "stage": [1]},
        }
    expected = [
        ("A", "one"),
        ("B", "one"),
        ("A", "two"),
        ("B", "two"),
        ("A", "two"),
        ("B", "two"),
    ]
    if fmt == "json":
        expected += [("A", "drop"), ("B", "drop")]
    assert calls == expected


class Capture:
    def export(self, chunks, edges, output, metadata):
        assert isinstance(chunks, list)
        assert isinstance(edges, list)
        self.chunks, self.edges, self.metadata = chunks, edges, metadata

    def export_streaming(self, chunks, edges, output):
        assert iter(chunks) is chunks
        assert iter(edges) is edges
        self.chunks, self.edges = list(chunks), list(edges)


@pytest.mark.parametrize("streaming", [False, True])
def test_no_hooks_preserve_records_and_metadata(tmp_path, streaming):
    writer = Capture()
    export = pipeline(writer)
    c, r = chunk("one"), edge()
    chunks, edges = [c], [r]
    fixed = ExportMetadata(ExportFormat.JSON, "custom", "now", [], 12, 10, {})
    path = tmp_path / "out.json"
    if streaming:
        dispatch(export, chunks, edges, path, True)
    else:
        export.export(chunks, edges, path, fixed)
        assert (
            writer.chunks is chunks
            and writer.edges is edges
            and writer.metadata is fixed
        )
        json_writer = StructuredJSONExporter()
        pipeline(json_writer).export(chunks, edges, path, fixed)
        direct = tmp_path / "direct.json"
        json_writer.export(chunks, edges, direct, fixed)
        assert path.read_bytes() == direct.read_bytes()
    assert writer.chunks[0] is c and writer.edges[0] is r


@pytest.mark.parametrize("streaming", [False, True])
@pytest.mark.parametrize("populated", [False, True])
def test_empty_or_filtered_records_skip_hooks(tmp_path, streaming, populated):
    writer = Capture()
    export = pipeline(writer)
    export.add_transformer(object())
    export.add_filter(
        SimpleNamespace(
            should_include_chunk=lambda c: False,
            should_include_relationship=lambda r: False,
        )
    )
    dispatch(
        export,
        [chunk("x")] if populated else [],
        [edge()] if populated else [],
        tmp_path / "empty.json",
        streaming,
    )
    assert writer.chunks == writer.edges == []


def test_detached_patch_and_duplicate_stages(tmp_path):
    writer = Capture()
    export = pipeline(writer)
    shared = {"tags": []}

    class Stage:
        def transform_chunk(self, c):
            assert isinstance(c, CodeChunk)
            shared["tags"][:] = [c.content]
            c.qualified_route.clear()
            c.metadata["original"].append("omitted")
            return {
                "metadata": {"original": [], "shared": shared},
                "content": c.content + "!",
            }

        def transform_relationship(self, r):
            assert isinstance(r, ChunkRelationship)
            return {**asdict(r), "metadata": None}

    def full(c):
        return asdict(c)

    export.add_transformer(
        SimpleNamespace(transform_chunk=full, transform_relationship=lambda r: {})
    )
    stage = Stage()
    export.add_transformer(stage)
    export.add_transformer(stage)
    first, last, original_edge = chunk("one"), chunk("two"), edge()
    first.chunk_id = ""
    export.export([first, last], [original_edge], tmp_path / "out.json")
    shared["tags"].clear()
    assert [c.content for c in writer.chunks] == ["one\r\n!!", "two\r\n!!"]
    assert [c.metadata for c in writer.chunks] == [
        {"original": [], "shared": {"tags": ["one\r\n!"]}},
        {"original": [], "shared": {"tags": ["two\r\n!"]}},
    ]
    assert writer.chunks[0].chunk_id == ""
    assert writer.chunks[0].qualified_route == first.qualified_route == ["function:one"]
    assert (
        first.metadata == last.metadata == original_edge.metadata == {"original": [1]}
    )
    assert writer.edges[0].metadata is None
    assert first.content == "one\r\n"


def test_batch_snapshot_before_filters(tmp_path):
    writer = Capture()
    export = pipeline(writer)
    a = SimpleNamespace(transform_chunk=lambda c: {"content": c.content + "A"})
    b = SimpleNamespace(transform_chunk=lambda c: {"content": c.content + "B"})
    export.add_transformer(a)

    def include(c):
        export.add_transformer(b)
        return True

    export.add_filter(SimpleNamespace(should_include_chunk=include))
    for count, suffix in [(1, "A"), (2, "AB")]:
        export.export([chunk("one")], [], tmp_path / "snapshot.json")
        assert writer.chunks[0].content == "one\r\n" + suffix
        meta = writer.metadata
        assert (
            meta.version,
            meta.chunk_count,
            meta.relationship_count,
            meta.source_files,
        ) == ("1.0", 1, 0, ["src/π.py"])
        assert meta.options == {"filters": 1, "transformers": count, "batch_size": 1000}


def test_stream_pulls_only_requested_records(tmp_path):
    pulls = []
    export = StructuredExportOrchestrator()

    def source(label, value):
        pulls.append(label)
        yield value
        pytest.fail("read past requested record")

    def consume(chunks, edges, output):
        assert pulls == []
        assert next(edges).relationship_type is RelationshipType.USES
        export.add_transformer(
            SimpleNamespace(transform_chunk=lambda c: {"content": "next"})
        )
        assert next(chunks).content == "first"

    export.register_exporter(
        ExportFormat.JSON, SimpleNamespace(export_streaming=consume)
    )
    export.add_transformer(
        SimpleNamespace(
            transform_chunk=lambda c: {"content": "first"},
            transform_relationship=lambda r: {"relationship_type": "uses"},
        )
    )
    path = tmp_path / "lazy.json"
    export.export_streaming(source("chunk", chunk("one")), source("edge", edge()), path)
    assert pulls == ["edge", "chunk"]
    writer = Capture()
    export.register_exporter(ExportFormat.JSON, writer)
    export.export_streaming(iter([chunk("one")]), iter([]), path)
    assert writer.chunks[0].content == "next"


@pytest.mark.parametrize(
    ("is_edge", "patch", "field"),
    [
        (False, None, "patch"),
        (False, [], "patch"),
        (False, chunk("bad"), "patch"),
        (False, {0: 1}, "field name"),
        (False, {"byte_size": 1}, "byte_size"),
        (False, {"metadata": None}, "metadata"),
        (False, {"metadata": {1: 0}}, "metadata"),
        (False, {"content": b"x"}, "content"),
        (False, {"chunk_id": "other"}, "chunk_id"),
        (False, {"file_path": "other"}, "file_path"),
        (False, {"qualified_route": []}, "qualified_route"),
        (False, {"byte_end": 99}, "byte_end"),
        (False, {"start_line": True}, "start_line"),
        (True, {"source_chunk_id": "two", "target_chunk_id": "one"}, "source_chunk_id"),
        (True, {"target_chunk_id": "one"}, "target_chunk_id"),
        (True, {"relationship_type": "invalid"}, "relationship_type"),
        (True, {"relationship_type": "CALLS"}, "relationship_type"),
        (True, {"relationship_type": 1}, "relationship_type"),
        (True, {"metadata": {1: 2}}, "metadata"),
    ],
)
def test_bad_patch_stops_before_batch_write(tmp_path, is_edge, patch, field):
    class Invalid:
        def transform_chunk(self, c):
            c.metadata.clear()
            return patch

        def transform_relationship(self, r):
            r.metadata.clear()
            return patch

    export = pipeline(StructuredJSONExporter())
    export.add_transformer(
        SimpleNamespace(
            transform_chunk=lambda c: {}, transform_relationship=lambda r: {}
        )
    )
    export.add_transformer(Invalid())
    export.add_transformer(object())
    path = tmp_path / "seed.json"
    path.write_bytes(b"seed\r\n")
    c, r = chunk("one"), edge()
    with pytest.raises(ChunkerError) as info:
        export.export([] if is_edge else [c], [r] if is_edge else [], path)
    message = str(info.value)
    assert all(
        part in message
        for part in (
            "2",
            "Invalid",
            field,
            "one",
            "relationship" if is_edge else "chunk",
        )
    )
    if is_edge:
        assert "two" in message
    assert c.metadata == r.metadata == {"original": [1]}
    assert path.read_bytes() == b"seed\r\n"


def test_chunk_only_hook_and_late_edge_failure(tmp_path):
    export = pipeline(StructuredJSONExporter())
    export.add_transformer(SimpleNamespace(transform_chunk=lambda c: {"content": ""}))
    path = tmp_path / "out.json"
    export.export([chunk("one")], [], path)
    assert json.loads(path.read_text(encoding="utf-8"))["chunks"][0]["content"] == ""
    before = path.read_bytes()
    with pytest.raises(ChunkerError, match="relationship.*one.*two") as error:
        export.export([chunk("one")], [edge()], path)
    assert isinstance(error.value.__cause__, AttributeError)
    assert path.read_bytes() == before


def test_jsonl_partial_output_is_closed(tmp_path):
    failure = RuntimeError("private metadata")
    seen = []

    def transform(c):
        seen.append(c.chunk_id)
        if c.chunk_id == "two":
            raise failure
        return {"content": "completed"}

    export = pipeline(StructuredJSONLExporter(), ExportFormat.JSONL)
    export.add_transformer(SimpleNamespace(transform_chunk=lambda c: {}))
    export.add_transformer(SimpleNamespace(transform_chunk=transform))
    path = tmp_path / "partial.jsonl"
    with pytest.raises(ChunkerError, match="2.*SimpleNamespace.*chunk.*two") as error:
        export.export_streaming(map(chunk, ["one", "two", "three"]), iter([]), path)
    assert error.value.__cause__ is failure
    assert "private metadata" not in str(error.value)
    assert seen == ["one", "two"]
    lines = (
        path.rename(tmp_path / "closed.jsonl").read_text(encoding="utf-8").splitlines()
    )
    header, record = map(json.loads, lines)
    assert header["type"] == "metadata"
    assert (record["type"], record["data"]["chunk_id"], record["data"]["content"]) == (
        "chunk",
        "one",
        "completed",
    )


@pytest.mark.parametrize("in_patch", [False, True])
def test_copy_failure(tmp_path, in_patch):
    failure = TypeError("private value")

    class Uncopyable:
        def __deepcopy__(self, memo):
            raise failure

    export = pipeline(Capture())
    c = chunk("one")
    bad = {"private": Uncopyable()}
    if not in_patch:
        c.metadata = bad
    export.add_transformer(SimpleNamespace(transform_chunk=lambda c: {"metadata": bad}))
    with pytest.raises(ChunkerError, match="1.*SimpleNamespace.*chunk.*one") as error:
        export.export([c], [], tmp_path / "copy.json")
    assert error.value.__cause__ is failure
    if in_patch:
        assert "metadata" in str(error.value)


@pytest.mark.parametrize("streaming", [False, True])
@pytest.mark.parametrize("source", ["writer", "filter", "process-control"])
def test_external_exceptions_propagate(tmp_path, streaming, source):
    failure = (
        KeyboardInterrupt() if source == "process-control" else LookupError(source)
    )

    def fail(*args):
        raise failure

    writer = (
        SimpleNamespace(export=fail, export_streaming=fail)
        if source == "writer"
        else Capture()
    )
    export = pipeline(writer)
    export.add_transformer(
        SimpleNamespace(
            transform_chunk=fail if source == "process-control" else lambda c: {}
        )
    )
    if source == "filter":
        export.add_filter(SimpleNamespace(should_include_chunk=fail))
    with pytest.raises(type(failure)) as error:
        dispatch(export, [chunk("one")], [], tmp_path / "test.json", streaming)
    assert error.value is failure


def test_input_iterator_exception(tmp_path):
    failure = LookupError("iterator")

    def source():
        yield chunk("one")
        raise failure

    export = pipeline(Capture())
    export.add_transformer(SimpleNamespace(transform_chunk=lambda c: {}))
    with pytest.raises(LookupError) as error:
        export.export_streaming(source(), iter([]), tmp_path / "test.json")
    assert error.value is failure


def test_no_hooks_batch_json_accepts_dictionary_records(tmp_path):
    records = [{"file_path": "legacy.py", "content": "first"}, {"content": "second"}]
    edges = [{"source_chunk_id": "legacy", "target_chunk_id": "external"}]
    path = tmp_path / "legacy.json"
    pipeline(StructuredJSONExporter()).export(records, edges, path)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["chunks"] == records
    assert data["relationships"] == edges
    assert set(data["metadata"]["source_files"]) == {"legacy.py", ""}

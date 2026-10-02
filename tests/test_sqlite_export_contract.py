"""SQLite export preserves parsed chunks and directed relationships."""

import json
import sqlite3
from pathlib import Path

import pytest

from chunker import chunk_file
from chunker.export.formats.database import SQLiteExporter
from chunker.interfaces.export import ChunkRelationship, RelationshipType


FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "tests/fixtures/boundary_ir/repos/python/app/service.py"
)


@pytest.mark.parametrize("streaming", [False, True])
def test_sqlite_export_round_trips_parsed_chunks_and_relationship(
    tmp_path: Path, streaming: bool
) -> None:
    chunks = chunk_file(FIXTURE, "python")
    assert len(chunks) >= 2
    parent, child = chunks[:2]
    assert parent.chunk_id and child.chunk_id and parent.chunk_id != child.chunk_id
    relationship = ChunkRelationship(
        source_chunk_id=parent.chunk_id,
        target_chunk_id=child.chunk_id,
        relationship_type=RelationshipType.HAS_METHOD,
        metadata={"fixture": "service.py"},
    )
    output = tmp_path / "chunks.sqlite"
    exporter = SQLiteExporter()
    if streaming:
        exporter.set_batch_size(1)
        exporter.export_streaming(iter(chunks), iter([relationship]), output)
    else:
        exporter.export(chunks, [relationship], output)

    with sqlite3.connect(output) as connection:
        stored_chunks = connection.execute(
            "SELECT chunk_id, language, file_path, node_type, content FROM chunks"
        ).fetchall()
        stored_relationships = connection.execute(
            "SELECT source_chunk_id, target_chunk_id, relationship_type, metadata "
            "FROM relationships"
        ).fetchall()

    assert {row[0] for row in stored_chunks} == {chunk.chunk_id for chunk in chunks}
    assert {row[1] for row in stored_chunks} == {"python"}
    assert {row[2] for row in stored_chunks} == {str(FIXTURE)}
    assert {row[3] for row in stored_chunks} == {chunk.node_type for chunk in chunks}
    assert {row[4] for row in stored_chunks} == {chunk.content for chunk in chunks}
    assert len(stored_relationships) == 1
    source, target, relationship_type, metadata = stored_relationships[0]
    assert (source, target, relationship_type) == (
        parent.chunk_id,
        child.chunk_id,
        RelationshipType.HAS_METHOD.value,
    )
    assert json.loads(metadata) == {"fixture": "service.py"}

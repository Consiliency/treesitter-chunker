"""Tests for JSONL export functionality."""

import gzip
import json
from io import StringIO
from pathlib import Path

import pytest

from chunker.chunker import CodeChunk
from chunker.export import JSONLExporter, SchemaType


@pytest.fixture
def sample_chunks():
    """Create sample chunks with relationships."""
    chunks = [
        CodeChunk(
            language="python",
            file_path="test.py",
            node_type="class_definition",
            start_line=1,
            end_line=10,
            byte_start=0,
            byte_end=200,
            parent_context="",
            content="class TestClass:\n    pass",
            chunk_id="chunk1",
            parent_chunk_id=None,
        ),
        CodeChunk(
            language="python",
            file_path="test.py",
            node_type="method_definition",
            start_line=3,
            end_line=5,
            byte_start=50,
            byte_end=100,
            parent_context="class_definition",
            content="def method(self):\n        pass",
            chunk_id="chunk2",
            parent_chunk_id="chunk1",
        ),
    ]
    return chunks


def test_jsonl_export_flat_schema(sample_chunks):
    """Test JSONL export with flat schema."""
    exporter = JSONLExporter(SchemaType.FLAT)
    output = StringIO()

    exporter.export(sample_chunks, output)

    lines = output.getvalue().strip().split("\n")
    assert len(lines) == 2

    # Parse each line
    chunk1 = json.loads(lines[0])
    chunk2 = json.loads(lines[1])

    assert chunk1["chunk_id"] == "chunk1"
    assert chunk2["parent_chunk_id"] == "chunk1"


def test_jsonl_export_full_schema(sample_chunks):
    """Test JSONL export with full schema."""
    exporter = JSONLExporter(SchemaType.FULL)
    output = StringIO()

    exporter.export(sample_chunks, output)

    lines = output.getvalue().strip().split("\n")
    assert len(lines) == 4  # metadata + 2 chunks + relationships

    # Parse each line
    metadata = json.loads(lines[0])
    chunk1 = json.loads(lines[1])
    json.loads(lines[2])
    relationships = json.loads(lines[3])

    assert metadata["type"] == "metadata"
    assert metadata["data"]["total_chunks"] == 2

    assert chunk1["type"] == "chunk"
    assert chunk1["data"]["chunk_id"] == "chunk1"

    assert relationships["type"] == "relationships"
    assert len(relationships["data"]["parent_child"]) == 1


def test_jsonl_export_to_file(sample_chunks, tmp_path):
    """Test JSONL export to file."""
    exporter = JSONLExporter(SchemaType.FLAT)
    output_path = tmp_path / "output.jsonl"

    exporter.export(sample_chunks, output_path)

    assert output_path.exists()
    with Path(output_path).open("r") as f:
        lines = f.readlines()

    assert len(lines) == 2
    chunk1 = json.loads(lines[0])
    assert chunk1["chunk_id"] == "chunk1"


def test_jsonl_export_compressed(sample_chunks, tmp_path):
    """Test JSONL export with compression."""
    exporter = JSONLExporter(SchemaType.FLAT)
    output_path = tmp_path / "output.jsonl"

    exporter.export(sample_chunks, output_path, compress=True)

    compressed_path = Path(f"{output_path}.gz")
    assert compressed_path.exists()

    with gzip.Path(compressed_path).open("rt") as f:
        lines = f.readlines()

    assert len(lines) == 2
    chunk1 = json.loads(lines[0])
    assert chunk1["chunk_id"] == "chunk1"


def test_jsonl_stream_export(sample_chunks, tmp_path):
    """Test JSONL streaming export."""
    exporter = JSONLExporter(SchemaType.FLAT)
    output_path = tmp_path / "output.jsonl"

    # Generator function
    def chunk_generator():
        yield from sample_chunks

    exporter.stream_export(chunk_generator(), output_path)

    assert output_path.exists()
    with Path(output_path).open("r") as f:
        lines = f.readlines()

    assert len(lines) == 2
    chunk1 = json.loads(lines[0])
    assert chunk1["chunk_id"] == "chunk1"


def test_jsonl_stream_export_compressed(sample_chunks, tmp_path):
    """Test JSONL streaming export with compression."""
    exporter = JSONLExporter(SchemaType.FLAT)
    output_path = tmp_path / "output.jsonl"

    # Generator function
    def chunk_generator():
        yield from sample_chunks

    exporter.stream_export(chunk_generator(), output_path, compress=True)

    compressed_path = Path(f"{output_path}.gz")
    assert compressed_path.exists()

    with gzip.Path(compressed_path).open("rt") as f:
        lines = f.readlines()

    assert len(lines) == 2
    chunk1 = json.loads(lines[0])
    assert chunk1["chunk_id"] == "chunk1"


def test_jsonl_minimal_schema(sample_chunks):
    """Test JSONL export with minimal schema."""
    exporter = JSONLExporter(SchemaType.MINIMAL)
    output = StringIO()

    exporter.export(sample_chunks, output)

    lines = output.getvalue().strip().split("\n")
    assert len(lines) == 2

    chunk1 = json.loads(lines[0])
    assert "id" in chunk1
    assert "type" in chunk1
    assert "content" in chunk1
    assert "chunk_id" not in chunk1  # Minimal schema

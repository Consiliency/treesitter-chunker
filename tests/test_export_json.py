"""Tests for JSON export functionality."""

import gzip
import json
from pathlib import Path

import pytest

from chunker.export import JSONExporter, SchemaType
from chunker.types import CodeChunk


@pytest.fixture()
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


def test_json_export_flat_schema(sample_chunks):
    """Test JSON export with flat schema."""
    exporter = JSONExporter(SchemaType.FLAT)
    result = exporter.export_to_string(sample_chunks)
    data = json.loads(result)

    assert isinstance(data, list)
    assert len(data) == 2
    assert data[0]["chunk_id"] == "chunk1"
    assert data[1]["parent_chunk_id"] == "chunk1"


def test_json_export_nested_schema(sample_chunks):
    """Test JSON export with nested schema."""
    exporter = JSONExporter(SchemaType.NESTED)
    result = exporter.export_to_string(sample_chunks)
    data = json.loads(result)

    assert isinstance(data, list)
    assert len(data) == 1  # Only root chunk
    assert data[0]["chunk_id"] == "chunk1"
    assert len(data[0]["children"]) == 1
    assert data[0]["children"][0]["chunk_id"] == "chunk2"


def test_json_export_minimal_schema(sample_chunks):
    """Test JSON export with minimal schema."""
    exporter = JSONExporter(SchemaType.MINIMAL)
    result = exporter.export_to_string(sample_chunks)
    data = json.loads(result)

    assert isinstance(data, list)
    assert len(data) == 2
    assert "id" in data[0]
    assert "type" in data[0]
    assert "content" in data[0]
    assert "chunk_id" not in data[0]  # Minimal schema


def test_json_export_full_schema(sample_chunks):
    """Test JSON export with full schema."""
    exporter = JSONExporter(SchemaType.FULL)
    result = exporter.export_to_string(sample_chunks)
    data = json.loads(result)

    assert isinstance(data, dict)
    assert "metadata" in data
    assert "chunks" in data
    assert "relationships" in data

    assert data["metadata"]["total_chunks"] == 2
    assert len(data["chunks"]) == 2
    assert len(data["relationships"]["parent_child"]) == 1


def test_json_export_to_file(sample_chunks, tmp_path):
    """Test JSON export to file."""
    exporter = JSONExporter(SchemaType.FLAT)
    output_path = tmp_path / "output.json"

    exporter.export(sample_chunks, output_path)

    assert output_path.exists()
    with Path(output_path).open(
        "r",
        encoding="utf-8",
    ) as f:
        data = json.load(f)
    assert len(data) == 2


def test_json_export_compressed(sample_chunks, tmp_path):
    """Test JSON export with compression."""
    exporter = JSONExporter(SchemaType.FLAT)
    output_path = tmp_path / "output.json"

    exporter.export(sample_chunks, output_path, compress=True)

    compressed_path = Path(f"{output_path}.gz")
    assert compressed_path.exists()

    with gzip.open(compressed_path, "rt") as f:
        data = json.load(f)
    assert len(data) == 2


def test_json_export_custom_indent(sample_chunks):
    """Test JSON export with custom indentation."""
    exporter = JSONExporter(SchemaType.FLAT)

    # No indent
    result_compact = exporter.export_to_string(sample_chunks, indent=None)
    assert "\n" not in result_compact.strip()

    # With indent
    result_pretty = exporter.export_to_string(sample_chunks, indent=4)
    assert "\n" in result_pretty
    assert "    " in result_pretty  # 4 spaces

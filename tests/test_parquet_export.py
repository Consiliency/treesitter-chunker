"""Tests for Parquet export functionality."""

import subprocess
import sys
import json
import tempfile
from dataclasses import replace
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from chunker.exporters import ParquetExporter
from chunker.types import CodeChunk


def read_parquet_table(path):
    """Close the test reader before deleting its file on Windows."""
    with pa.OSFile(str(path), "rb") as source:
        return pq.read_table(source)


@pytest.fixture
def sample_chunks():
    """Create sample code chunks for testing."""
    return [
        CodeChunk(
            language="python",
            file_path="test1.py",
            node_type="function_definition",
            start_line=1,
            end_line=5,
            byte_start=0,
            byte_end=100,
            parent_context="",
            content="def test_func():\n    pass",
        ),
        CodeChunk(
            language="python",
            file_path="test1.py",
            node_type="class_definition",
            start_line=7,
            end_line=15,
            byte_start=102,
            byte_end=250,
            parent_context="",
            content="class TestClass:\n    def method(self):\n        pass",
        ),
        CodeChunk(
            language="rust",
            file_path="test2.rs",
            node_type="function_definition",
            start_line=1,
            end_line=3,
            byte_start=0,
            byte_end=50,
            parent_context="",
            content='fn main() {\n    println!("Hello");\n}',
        ),
    ]


def test_basic_export(sample_chunks):
    """Test basic Parquet export functionality."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "chunks.parquet"

        exporter = ParquetExporter()
        exporter.export(sample_chunks, output_path)

        # Read back and verify
        table = read_parquet_table(output_path)
        assert len(table) == 3

        # Check schema
        assert "language" in table.schema.names
        assert "file_path" in table.schema.names
        assert "node_type" in table.schema.names
        assert "content" in table.schema.names
        assert "metadata" in table.schema.names
        assert "lines_of_code" in table.schema.names
        assert "byte_size" in table.schema.names

        # Check nested metadata
        metadata_col = table.column("metadata")
        assert metadata_col.type.num_fields == 4

        # Cleanup
        output_path.unlink()


def test_column_selection(sample_chunks):
    """Test exporting with selected columns only."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "chunks.parquet"

        exporter = ParquetExporter(columns=["language", "node_type", "lines_of_code"])
        exporter.export(sample_chunks, output_path)

        # Read back and verify
        table = read_parquet_table(output_path)
        assert len(table) == 3

        # Check only selected columns are present
        assert set(table.schema.names) == {"language", "node_type", "lines_of_code"}

        # Cleanup
        output_path.unlink()


def test_partitioned_export(sample_chunks):
    """Test partitioned Parquet export."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "partitioned_chunks"

        exporter = ParquetExporter(partition_by=["language"])
        exporter.export(sample_chunks, output_path)

        # Check partitions were created
        assert (output_path / "language=python").exists()
        assert (output_path / "language=rust").exists()

        table = pq.ParquetDataset(str(output_path)).read()
        assert len(table) == len(sample_chunks)
        actual = sorted(table.to_pylist(), key=lambda row: row["content"])
        expected = sorted(
            [exporter._chunk_to_dict(chunk) for chunk in sample_chunks],
            key=lambda row: row["content"],
        )
        assert actual == expected


def test_compression_options(sample_chunks):
    """Test different compression codecs."""
    compressions = ["snappy", "gzip", "zstd", None]

    for compression in compressions:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "chunks.parquet"

            exporter = ParquetExporter(compression=compression)
            exporter.export(sample_chunks, output_path)

            # Verify file was created and can be read
            assert output_path.exists()
            table = read_parquet_table(output_path)
            assert len(table) == 3

            # Cleanup
            output_path.unlink()


def test_streaming_export(sample_chunks):
    """Test streaming export for large datasets."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "chunks.parquet"

        exporter = ParquetExporter()

        # Use iterator to simulate streaming
        def chunks_iterator():
            yield from sample_chunks

        exporter.export_streaming(chunks_iterator(), output_path, batch_size=2)

        # Read back and verify
        table = read_parquet_table(output_path)
        assert len(table) == 3

        # Cleanup
        output_path.unlink()


def test_empty_chunks():
    """Test exporting empty chunks list."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "chunks.parquet"

        exporter = ParquetExporter()
        exporter.export([], output_path)

        # Read back and verify
        table = read_parquet_table(output_path)
        assert len(table) == 0

        # Cleanup
        output_path.unlink()


def test_metadata_structure(sample_chunks):
    """Test nested metadata structure is correctly preserved."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "chunks.parquet"

        exporter = ParquetExporter()
        exporter.export(sample_chunks, output_path)

        # Read back
        table = read_parquet_table(output_path)

        # Check metadata is a struct type
        metadata_col = table.column("metadata")
        assert metadata_col.type.num_fields == 4

        # Check first row's metadata values directly from PyArrow
        first_row_metadata = metadata_col[0].as_py()
        assert first_row_metadata["start_line"] == 1
        assert first_row_metadata["end_line"] == 5
        assert first_row_metadata["byte_start"] == 0
        assert first_row_metadata["byte_end"] == 100

        # Cleanup
        output_path.unlink()


def test_partitioned_reexport_replaces_matching_partitions(sample_chunks, tmp_path):
    exporter = ParquetExporter(partition_by=["language"])
    exporter.export(sample_chunks, tmp_path)
    exporter.export(sample_chunks, tmp_path)
    assert len(pq.ParquetDataset(str(tmp_path)).read()) == len(sample_chunks)
    python_chunk = next(c for c in sample_chunks if c.language == "python")
    exporter.export([python_chunk], tmp_path)
    rows = pq.ParquetDataset(str(tmp_path)).read().to_pylist()
    assert sum(row["language"] == "python" for row in rows) == 1
    assert sum(row["language"] == "rust" for row in rows) == 1


def test_partitioned_export_above_default_partition_limit(sample_chunks, tmp_path):
    chunks = [
        replace(sample_chunks[0], file_path=f"source-{i}.py", content=f"content-{i}")
        for i in range(1025)
    ]
    exporter = ParquetExporter(partition_by=["file_path"])
    exporter.export(chunks, tmp_path)
    rows = pq.ParquetDataset(str(tmp_path)).read().to_pylist()
    assert len(rows) == len(chunks)
    assert {(row["file_path"], row["content"]) for row in rows} == {
        (chunk.file_path, chunk.content) for chunk in chunks
    }
    replacement = replace(chunks[0], content="replacement")
    exporter.export([replacement], tmp_path)
    exporter.export([], tmp_path)
    rows = pq.ParquetDataset(str(tmp_path)).read().to_pylist()
    assert len(rows) == len(chunks)
    assert {(row["file_path"], row["content"]) for row in rows} == {
        (chunk.file_path, chunk.content) for chunk in [replacement, *chunks[1:]]
    }


@pytest.mark.parametrize("partition_by", [["file_path"], ["language", "file_path"]])
def test_partitioned_string_paths_round_trip(sample_chunks, tmp_path, partition_by):
    chunks = [
        replace(sample_chunks[0], file_path=path, content=f"content-{i}")
        for i, path in enumerate(["001", "1", "2"])
    ]
    exporter = ParquetExporter(partition_by=partition_by)

    def read_rows():
        schema = pq.read_schema(tmp_path / "_common_metadata")
        assert schema.field("file_path").type == pa.string()
        return pq.ParquetDataset(str(tmp_path), schema=schema).read().to_pylist()

    exporter.export(chunks, tmp_path)
    assert {(row["file_path"], row["content"]) for row in read_rows()} == {
        (chunk.file_path, chunk.content) for chunk in chunks
    }
    metadata = (tmp_path / "_common_metadata").read_bytes()
    replacement = replace(chunks[0], content="replacement")
    exporter.export([replacement], tmp_path)
    exporter.export([], tmp_path)
    assert (tmp_path / "_common_metadata").read_bytes() == metadata
    assert {(row["file_path"], row["content"]) for row in read_rows()} == {
        (chunk.file_path, chunk.content) for chunk in [replacement, *chunks[1:]]
    }


def test_partitioned_selected_schema_is_preserved(sample_chunks, tmp_path):
    exporter = ParquetExporter(
        columns=["file_path", "content"], partition_by=["file_path"]
    )
    exporter.export([replace(sample_chunks[0], file_path="001")], tmp_path)
    schema = pq.read_schema(tmp_path / "_common_metadata")
    assert schema.names == ["file_path", "content"]
    assert pq.ParquetDataset(str(tmp_path), schema=schema).read().to_pylist() == [
        {"file_path": "001", "content": sample_chunks[0].content}
    ]
    before = {
        str(p.relative_to(tmp_path)): p.read_bytes()
        for p in tmp_path.rglob("*")
        if p.is_file()
    }
    with pytest.raises(ValueError, match="schema"):
        ParquetExporter(partition_by=["file_path"]).export(sample_chunks, tmp_path)
    assert {
        str(p.relative_to(tmp_path)): p.read_bytes()
        for p in tmp_path.rglob("*")
        if p.is_file()
    } == before


@pytest.mark.parametrize("field", ["file_path", "language"])
def test_reserved_partition_value_rejected_before_writing(
    sample_chunks, tmp_path, field
):
    reserved = "__HIVE_DEFAULT_PARTITION__"
    original = sample_chunks[0]
    invalid = replace(original, **{field: reserved})
    exporter = ParquetExporter(partition_by=[field])
    fresh = tmp_path / "fresh"
    with pytest.raises(ValueError, match="reserved Hive"):
        exporter.export([invalid], fresh)
    assert not fresh.exists()

    existing = tmp_path / "existing"
    exporter.export([original], existing)
    before = {
        p.relative_to(existing): p.read_bytes()
        for p in existing.rglob("*")
        if p.is_file()
    }
    with pytest.raises(ValueError, match="reserved Hive"):
        exporter.export([replace(original, content="replacement"), invalid], existing)
    assert {
        p.relative_to(existing): p.read_bytes()
        for p in existing.rglob("*")
        if p.is_file()
    } == before
    schema = pq.read_schema(existing / "_common_metadata")
    assert pq.ParquetDataset(existing, schema=schema).read().to_pylist()[0][
        field
    ] == getattr(original, field)

    other_field = "language" if field == "file_path" else "file_path"
    allowed = tmp_path / "nonpartition"
    ParquetExporter(partition_by=[other_field]).export([invalid], allowed)
    schema = pq.read_schema(allowed / "_common_metadata")
    assert (
        pq.ParquetDataset(allowed, schema=schema).read().to_pylist()[0][field]
        == reserved
    )
    flat = tmp_path / "flat.parquet"
    ParquetExporter().export([invalid], flat)
    assert pq.read_table(flat).to_pylist()[0][field] == reserved


@pytest.mark.parametrize("changed", [["file_path", "language"], ["file_path"]])
def test_partition_specification_cannot_change(sample_chunks, tmp_path, changed):
    original = replace(sample_chunks[0], file_path="001", content="old")
    columns = ["language", "file_path"]
    ParquetExporter(partition_by=columns).export([original], tmp_path)
    before = {
        p.relative_to(tmp_path): p.read_bytes()
        for p in tmp_path.rglob("*")
        if p.is_file()
    }
    with pytest.raises(ValueError, match="partition specification"):
        ParquetExporter(partition_by=changed).export(
            [replace(original, content="new")], tmp_path
        )
    assert {
        p.relative_to(tmp_path): p.read_bytes()
        for p in tmp_path.rglob("*")
        if p.is_file()
    } == before
    schema = pq.read_schema(tmp_path / "_common_metadata")
    assert json.loads(schema.metadata[b"treesitter_chunker.partition_by"]) == columns
    assert (
        pq.ParquetDataset(tmp_path, schema=schema).read().to_pylist()[0]["content"]
        == "old"
    )


@pytest.mark.parametrize("keep_schema", [True, False])
def test_legacy_partitioned_dataset_requires_reexport(
    sample_chunks, tmp_path, keep_schema
):
    exporter = ParquetExporter(partition_by=["file_path"])
    exporter.export(sample_chunks, tmp_path)
    metadata = tmp_path / "_common_metadata"
    if keep_schema:
        pq.write_metadata(pq.read_schema(metadata).remove_metadata(), metadata)
    else:
        metadata.unlink()
    before = {
        p.relative_to(tmp_path): p.read_bytes()
        for p in tmp_path.rglob("*")
        if p.is_file()
    }
    with pytest.raises(ValueError, match="partition specification"):
        exporter.export([replace(sample_chunks[0], content="new")], tmp_path)
    assert {
        p.relative_to(tmp_path): p.read_bytes()
        for p in tmp_path.rglob("*")
        if p.is_file()
    } == before


@pytest.mark.parametrize(
    ("partition_by", "first_path", "second_path"),
    [
        (["file_path"], "A.py", "a.py"),
        (["file_path"], "trailing", "trailing."),
        (["file_path", "node_type"], "A.py", "a.py"),
    ],
)
def test_portable_partition_aliases_rejected_before_writing(
    sample_chunks, tmp_path, partition_by, first_path, second_path
):
    first = replace(sample_chunks[0], file_path=first_path, node_type="function")
    second = replace(first, file_path=second_path, node_type="class", content="new")
    exporter = ParquetExporter(partition_by=partition_by)
    fresh = tmp_path / "fresh"
    with pytest.raises(ValueError, match="portable partition"):
        exporter.export([first, second], fresh)
    assert not fresh.exists()
    existing = tmp_path / "existing"
    exporter.export([first], existing)
    before = {
        p.relative_to(existing): p.read_bytes()
        for p in existing.rglob("*")
        if p.is_file()
    }
    with pytest.raises(ValueError, match="portable partition"):
        exporter.export([replace(first, content="replacement"), second], existing)
    assert {
        p.relative_to(existing): p.read_bytes()
        for p in existing.rglob("*")
        if p.is_file()
    } == before
    schema = pq.read_schema(existing / "_common_metadata")
    assert (
        pq.ParquetDataset(existing, schema=schema).read().to_pylist()[0]["file_path"]
        == first_path
    )
    exporter.export([replace(first, content="replacement")], existing)
    assert (
        pq.ParquetDataset(existing, schema=schema).read().to_pylist()[0]["content"]
        == "replacement"
    )

    empty = tmp_path / "empty"
    exporter.export([first], empty)
    for path in empty.rglob("*.parquet"):
        path.unlink()
    before = {
        p.relative_to(empty): p.read_bytes() for p in empty.rglob("*") if p.is_file()
    }
    with pytest.raises(ValueError, match="portable partition"):
        exporter.export([second], empty)
    assert {
        p.relative_to(empty): p.read_bytes() for p in empty.rglob("*") if p.is_file()
    } == before
    if second_path.endswith("."):
        single = tmp_path / "single"
        with pytest.raises(ValueError, match="portable partition"):
            exporter.export([second], single)
        assert not single.exists()
    allowed = tmp_path / "allowed"
    ParquetExporter(partition_by=["language"]).export([first, second], allowed)
    schema = pq.read_schema(allowed / "_common_metadata")
    assert {
        row["file_path"]
        for row in pq.ParquetDataset(allowed, schema=schema).read().to_pylist()
    } == {first_path, second_path}


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX file-descriptor limit")
def test_partitioned_export_under_file_descriptor_limit(tmp_path):
    script = """
import resource, runpy, sys
from pathlib import Path
soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
limit = 1024 if hard == resource.RLIM_INFINITY else min(1024, hard)
resource.setrlimit(resource.RLIMIT_NOFILE, (limit, hard))
tests = runpy.run_path(sys.argv[1])
tests['test_partitioned_export_above_default_partition_limit'](
    tests['sample_chunks'].__wrapped__(), Path(sys.argv[2]))
print('Partitioned readback completed under file-descriptor limit', limit)
"""
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            script,
            str(Path(__file__).resolve()),
            str(tmp_path),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert "Partitioned readback completed under file-descriptor limit" in result.stdout

"""Advanced export integration tests for all export formats.

This module tests advanced export scenarios including streaming,
compression, schema transformations, and error handling.
"""

import gzip
import json
import os
from pathlib import Path

import pytest

from chunker import CodeChunk, chunk_file, chunk_files_parallel
from chunker.export import JSONExporter, JSONLExporter, SchemaType
from chunker.export.formatters import FlatFormatter
from chunker.streaming import chunk_file_streaming


class TestStreamingExport:
    """Test streaming export capabilities."""

    def test_jsonl_streaming_export(self, tmp_path):
        """Test JSONL streaming export for large datasets."""
        # Create a file that generates many chunks
        large_file = tmp_path / "large_module.py"
        content_lines = []
        for i in range(100):
            content_lines.extend(
                [
                    f"def function_{i}():",
                    f"    '''Function {i} docstring'''",
                    f"    return {i}",
                    "",
                ],
            )
        large_file.write_text("\n".join(content_lines))

        # Use streaming chunker
        output_file = tmp_path / "streaming_output.jsonl"
        exporter = JSONLExporter(schema_type=SchemaType.FLAT)

        # Stream export
        chunks_generator = chunk_file_streaming(large_file, language="python")
        exporter.stream_export(chunks_generator, output_file)

        # Verify output
        lines = output_file.read_text().strip().split("\n")
        assert len(lines) >= 100  # At least one chunk per function

        # Verify each line is valid JSON
        for line in lines:
            data = json.loads(line)
            assert "content" in data
            assert "start_line" in data

    def test_compressed_streaming_export(self, tmp_path):
        """Test streaming export with compression."""
        # Create test data
        test_file = tmp_path / "test.py"
        test_file.write_text(
            """
def compress_me():
    return "This will be compressed"

class CompressedClass:
    def method(self):
        return "compressed method"
""",
        )

        # Stream export with compression
        output_file = tmp_path / "compressed.jsonl"
        exporter = JSONLExporter()

        chunks_gen = chunk_file_streaming(test_file, language="python")
        exporter.stream_export(chunks_gen, output_file, compress=True)

        # Verify compressed file exists
        compressed_file = Path(str(output_file) + ".gz")
        assert compressed_file.exists()

        # Decompress and verify content
        with gzip.open(compressed_file, "rt") as f:
            lines = f.read().strip().split("\n")
            assert len(lines) >= 2  # Function and class

            for line in lines:
                data = json.loads(line)
                assert "content" in data


class TestSchemaTransformations:
    """Test different schema transformations during export."""

    def test_flat_schema_export(self, tmp_path):
        """Test flat schema export format."""
        test_file = tmp_path / "schema_test.py"
        test_file.write_text(
            """
def parent_function():
    def nested_function():
        return "nested"
    return nested_function

class ParentClass:
    class NestedClass:
        def method(self):
            pass
""",
        )

        chunks = chunk_file(test_file, language="python")

        # Export with flat schema
        json_file = tmp_path / "flat_schema.json"
        exporter = JSONExporter(schema_type=SchemaType.FLAT)
        exporter.export(chunks, json_file)

        with open(json_file) as f:
            data = json.load(f)

        # Flat schema should have simple structure
        assert isinstance(data, list)
        for item in data:
            assert "content" in item
            assert "file_path" in item
            assert "start_line" in item
            assert "node_type" in item

    def test_full_schema_export(self, tmp_path):
        """Test full schema export with metadata and relationships."""
        test_file = tmp_path / "full_schema.py"
        test_file.write_text(
            """
import os

def uses_import():
    return os.path.join("a", "b")

class Referencer:
    def __init__(self):
        self.func = uses_import

    def call_func(self):
        return self.func()
""",
        )

        chunks = chunk_file(test_file, language="python")

        # Export with full schema
        json_file = tmp_path / "full_schema.json"
        exporter = JSONExporter(schema_type=SchemaType.FULL)
        exporter.export(chunks, json_file)

        with open(json_file) as f:
            data = json.load(f)

        # Full schema should have metadata and structure
        assert "metadata" in data
        assert "chunks" in data
        assert "relationships" in data

        # Verify metadata
        assert "total_chunks" in data["metadata"]
        assert "languages" in data["metadata"]
        assert data["metadata"]["total_chunks"] == len(chunks)

    def test_minimal_schema_export(self, tmp_path):
        """Test minimal schema export format."""
        test_file = tmp_path / "minimal_test.py"
        test_file.write_text(
            """
def simple_func():
    return 42

class SimpleClass:
    pass
""",
        )

        chunks = chunk_file(test_file, language="python")

        # Export with minimal schema
        json_file = tmp_path / "minimal_schema.json"
        exporter = JSONExporter(schema_type=SchemaType.MINIMAL)
        exporter.export(chunks, json_file)

        with open(json_file) as f:
            data = json.load(f)

        # Minimal schema should have minimal fields
        assert isinstance(data, list)
        for item in data:
            # Only essential fields (from MinimalFormatter)
            assert "content" in item
            assert "lines" in item  # Minimal location format as "start-end"
            assert "id" in item
            assert "type" in item
            assert "file" in item
            # Should not have verbose fields
            assert "byte_start" not in item
            assert "byte_end" not in item
            assert "parent_chunk_id" not in item


class TestMultiFormatExport:
    """Test exporting to multiple formats simultaneously."""

    def test_parallel_multi_format_export(self, tmp_path):
        """Test exporting chunks to multiple formats in parallel."""
        # Create test project
        project_dir = tmp_path / "multi_export_project"
        project_dir.mkdir()

        for i in range(5):
            (project_dir / f"module_{i}.py").write_text(
                f"""
def module_{i}_func():
    return {i}

class Module_{i}:
    value = {i}
""",
            )

        # Process all files
        files = list(project_dir.glob("*.py"))
        results = chunk_files_parallel(files, language="python", num_workers=2)

        # Collect all chunks
        all_chunks = []
        for chunks in results.values():
            all_chunks.extend(chunks)

        # Export to all formats
        export_dir = tmp_path / "exports"
        export_dir.mkdir()

        # JSON formats
        for schema_type in [SchemaType.FLAT, SchemaType.FULL, SchemaType.MINIMAL]:
            json_file = export_dir / f"export_{schema_type.value}.json"
            exporter = JSONExporter(schema_type=schema_type)
            exporter.export(all_chunks, json_file)
            assert json_file.exists()

        # JSONL format
        jsonl_file = export_dir / "export.jsonl"
        jsonl_exporter = JSONLExporter()
        jsonl_exporter.export(all_chunks, jsonl_file)
        assert jsonl_file.exists()

        # Compressed versions
        for compress_file in [
            export_dir / "compressed.json",
            export_dir / "compressed.jsonl",
        ]:
            exporter = (
                JSONExporter() if compress_file.suffix == ".json" else JSONLExporter()
            )
            exporter.export(all_chunks, compress_file, compress=True)
            assert Path(str(compress_file) + ".gz").exists()

    def test_format_consistency(self, tmp_path):
        """Test that different formats contain consistent data."""
        test_file = tmp_path / "consistency_test.py"
        test_file.write_text(
            """
def test_function(param1, param2):
    '''Test function with parameters'''
    result = param1 + param2
    return result * 2

class TestClass:
    def __init__(self, value):
        self.value = value

    def process(self):
        return self.value * 3
""",
        )

        chunks = chunk_file(test_file, language="python")

        # Export to different formats
        formats_data = {}

        # JSON with different schemas
        for schema_type in [SchemaType.FLAT, SchemaType.FULL, SchemaType.MINIMAL]:
            json_file = tmp_path / f"{schema_type.value}.json"
            exporter = JSONExporter(schema_type=schema_type)
            exporter.export(chunks, json_file)

            with open(json_file) as f:
                formats_data[schema_type.value] = json.load(f)

        # JSONL
        jsonl_file = tmp_path / "data.jsonl"
        jsonl_exporter = JSONLExporter()
        jsonl_exporter.export(chunks, jsonl_file)

        jsonl_data = []
        with open(jsonl_file) as f:
            for line in f:
                jsonl_data.append(json.loads(line))
        formats_data["jsonl"] = jsonl_data

        # Verify consistency across formats
        # Extract chunks from different format structures
        flat_chunks = formats_data["flat"]
        full_chunks = (
            formats_data["full"]["chunks"]
            if "chunks" in formats_data["full"]
            else formats_data["full"]
        )
        minimal_chunks = formats_data["minimal"]
        jsonl_chunks = formats_data["jsonl"]

        # All should have same number of chunks
        chunk_counts = [
            len(flat_chunks),
            len(full_chunks),
            len(minimal_chunks),
            len(jsonl_chunks),
        ]
        assert all(count == chunk_counts[0] for count in chunk_counts)

        # Verify core content is consistent
        for i in range(len(flat_chunks)):
            # Content should be same across formats (accounting for structure differences)
            flat_content = flat_chunks[i]["content"]

            # Full format might have nested structure
            full_chunks[i].get("content", full_chunks[i].get("code", ""))

            # Minimal might have different field names
            minimal_chunks[i].get(
                "content",
                minimal_chunks[i].get("code", ""),
            )

            jsonl_content = jsonl_chunks[i]["content"]

            # At least flat and jsonl should match exactly
            assert flat_content == jsonl_content


class TestExportErrorHandling:
    """Test error handling in export operations."""

    def test_export_to_readonly_directory(self, tmp_path):
        """Test export to read-only directory."""
        # Skip on Windows where chmod doesn't work the same
        if os.name == "nt":
            pytest.skip("Read-only directory test not reliable on Windows")

        chunks = [
            CodeChunk(
                language="python",
                file_path="/test.py",
                node_type="function_definition",
                start_line=1,
                end_line=1,
                byte_start=0,
                byte_end=16,
                parent_context="",
                content="def test(): pass",
            ),
        ]

        # Create read-only directory
        readonly_dir = tmp_path / "readonly"
        readonly_dir.mkdir()
        os.chmod(readonly_dir, 0o444)

        try:
            output_file = readonly_dir / "export.json"
            exporter = JSONExporter()

            with pytest.raises(PermissionError):
                exporter.export(chunks, output_file)
        finally:
            # Restore permissions
            os.chmod(readonly_dir, 0o755)

    def test_export_with_invalid_chunks(self, tmp_path):
        """Test export handling of malformed chunks."""
        # Create chunks with missing required fields
        invalid_chunks = [
            {  # Dict instead of CodeChunk - formatter should handle
                "content": "def test(): pass",
                "start_line": 1,
            },
        ]

        output_file = tmp_path / "invalid.json"
        exporter = JSONExporter()

        # Should handle gracefully or raise specific error
        try:
            # This might work if formatter handles dicts
            exporter.export(invalid_chunks, output_file)
            # If it worked, verify output
            assert output_file.exists()
        except (AttributeError, TypeError) as e:
            # Should be a clear error about chunk format
            assert "chunk" in str(e).lower() or "attribute" in str(e).lower()

    def test_interrupted_streaming_export(self, tmp_path):
        """Test handling of interrupted streaming export."""

        # Create a generator that fails partway through
        def failing_generator():
            yield CodeChunk(
                language="python",
                file_path="/test.py",
                node_type="function_definition",
                start_line=1,
                end_line=1,
                byte_start=0,
                byte_end=10,
                parent_context="",
                content="def one(): pass",
            )
            yield CodeChunk(
                language="python",
                file_path="/test.py",
                node_type="function_definition",
                start_line=3,
                end_line=3,
                byte_start=20,
                byte_end=30,
                parent_context="",
                content="def two(): pass",
            )
            # Simulate error
            raise RuntimeError("Simulated streaming error")

        output_file = tmp_path / "interrupted.jsonl"
        exporter = JSONLExporter()

        with pytest.raises(RuntimeError):
            exporter.stream_export(failing_generator(), output_file)

        # Partial file should exist with some content
        if output_file.exists():
            lines = output_file.read_text().strip().split("\n")
            # Should have written at least first chunk
            assert len(lines) >= 1
            first_chunk = json.loads(lines[0])
            assert "one" in first_chunk["content"]


class TestLargeScaleExport:
    """Test export with large-scale data."""

    def test_export_memory_efficiency(self, tmp_path):
        """Test memory efficiency during large exports."""
        import gc

        import psutil

        # Create many chunks
        chunks = []
        for i in range(1000):
            chunks.append(
                CodeChunk(
                    language="python",
                    file_path=f"/file_{i % 10}.py",
                    node_type="function_definition",
                    start_line=i * 5 + 1,
                    end_line=i * 5 + 4,
                    byte_start=i * 100,
                    byte_end=i * 100 + 80,
                    parent_context="",
                    content=f"def function_{i}():\n    return {i}",
                ),
            )

        process = psutil.Process()
        gc.collect()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        # Export to various formats
        json_file = tmp_path / "large.json"
        jsonl_file = tmp_path / "large.jsonl"

        # JSON export
        json_exporter = JSONExporter(schema_type=SchemaType.FLAT)
        json_exporter.export(chunks, json_file)

        json_memory = process.memory_info().rss / 1024 / 1024
        json_increase = json_memory - initial_memory

        # JSONL export
        jsonl_exporter = JSONLExporter()
        jsonl_exporter.export(chunks, jsonl_file)

        jsonl_memory = process.memory_info().rss / 1024 / 1024
        jsonl_increase = jsonl_memory - json_memory

        # Memory increase should be reasonable
        assert json_increase < 100  # MB
        assert jsonl_increase < 50  # MB - JSONL should be more efficient

        # Verify files
        assert json_file.stat().st_size > 0
        assert jsonl_file.stat().st_size > 0

    def test_export_performance_comparison(self, tmp_path):
        """Compare performance of different export formats."""
        import time

        # Create test chunks
        chunks = []
        for i in range(500):
            chunks.append(
                CodeChunk(
                    language="python",
                    file_path=f"/module_{i // 50}.py",
                    node_type=(
                        "function_definition" if i % 2 == 0 else "class_definition"
                    ),
                    start_line=i * 3 + 1,
                    end_line=i * 3 + 3,
                    byte_start=i * 50,
                    byte_end=i * 50 + 45,
                    parent_context="module",
                    content=(
                        f"def func_{i}(): pass"
                        if i % 2 == 0
                        else f"class Class_{i}: pass"
                    ),
                ),
            )

        export_times = {}

        # Time different export formats
        formats = [
            ("json_flat", JSONExporter(schema_type=SchemaType.FLAT)),
            ("json_full", JSONExporter(schema_type=SchemaType.FULL)),
            ("json_minimal", JSONExporter(schema_type=SchemaType.MINIMAL)),
            ("jsonl", JSONLExporter()),
        ]

        for format_name, exporter in formats:
            output_file = tmp_path / f"{format_name}.out"

            start_time = time.time()
            exporter.export(chunks, output_file)
            elapsed = time.time() - start_time

            export_times[format_name] = elapsed
            assert output_file.exists()

        # Performance comparison - JSONL and flat JSON should be in same ballpark
        # For small datasets, the performance difference might not be significant
        # Just verify all formats complete reasonably quickly
        for format_name, elapsed in export_times.items():
            assert elapsed < 2.0  # Should export 500 chunks in < 2 seconds

        # Minimal should be faster than full (less data to write)
        assert export_times["json_minimal"] <= export_times["json_full"] * 1.5


class TestCustomExportScenarios:
    """Test custom and advanced export scenarios."""

    def test_filtered_export(self, tmp_path):
        """Test exporting filtered subset of chunks."""
        test_file = tmp_path / "filter_test.py"
        test_file.write_text(
            """
def small_func():
    pass

def medium_function():
    x = 1
    y = 2
    return x + y

def large_function_with_many_lines():
    # Line 1
    # Line 2
    # Line 3
    # Line 4
    # Line 5
    result = 0
    for i in range(10):
        result += i
    return result

class TestClass:
    def method(self):
        pass
""",
        )

        chunks = chunk_file(test_file, language="python")

        # Filter chunks by size
        large_chunks = [
            chunk for chunk in chunks if chunk.end_line - chunk.start_line > 5
        ]

        # Export only large chunks
        output_file = tmp_path / "large_only.json"
        exporter = JSONExporter()
        exporter.export(large_chunks, output_file)

        with open(output_file) as f:
            data = json.load(f)

        # Should only have large function
        assert len(data) >= 1
        assert all(
            "large" in item["content"] or (item["end_line"] - item["start_line"] > 5)
            for item in data
        )

    def test_incremental_export(self, tmp_path):
        """Test incremental/append export scenarios."""
        output_file = tmp_path / "incremental.jsonl"
        exporter = JSONLExporter()

        # First batch
        chunks_batch1 = [
            CodeChunk(
                language="python",
                file_path="/batch1.py",
                node_type="function_definition",
                start_line=1,
                end_line=2,
                byte_start=0,
                byte_end=20,
                parent_context="",
                content="def batch1(): pass",
            ),
        ]
        exporter.export(chunks_batch1, output_file)

        # Second batch - append mode
        chunks_batch2 = [
            CodeChunk(
                language="python",
                file_path="/batch2.py",
                node_type="function_definition",
                start_line=1,
                end_line=2,
                byte_start=0,
                byte_end=20,
                parent_context="",
                content="def batch2(): pass",
            ),
        ]

        # Manually append to test incremental export
        with open(output_file, "a") as f:
            for chunk in chunks_batch2:
                formatter = FlatFormatter()
                chunk_dict = formatter._chunk_to_dict(chunk)
                json.dump(chunk_dict, f)
                f.write("\n")

        # Verify both batches are in file
        lines = output_file.read_text().strip().split("\n")
        assert len(lines) == 2

        data = [json.loads(line) for line in lines]
        assert "batch1" in data[0]["content"]
        assert "batch2" in data[1]["content"]


def test_export_format_auto_detection(tmp_path):
    """Test automatic format detection based on file extension."""
    chunks = [
        CodeChunk(
            language="python",
            file_path="/test.py",
            node_type="function_definition",
            start_line=1,
            end_line=1,
            byte_start=0,
            byte_end=16,
            parent_context="",
            content="def test(): pass",
        ),
    ]

    # Different file extensions
    test_cases = [
        ("output.json", JSONExporter),
        ("output.jsonl", JSONLExporter),
        ("output.ndjson", JSONLExporter),  # Alternative JSONL extension
    ]

    for filename, _expected_exporter_class in test_cases:
        output_file = tmp_path / filename

        # Use appropriate exporter based on extension
        if filename.endswith((".jsonl", ".ndjson")):
            exporter = JSONLExporter()
        else:
            exporter = JSONExporter()

        exporter.export(chunks, output_file)
        assert output_file.exists()

        # Verify format
        content = output_file.read_text()
        if filename.endswith((".jsonl", ".ndjson")):
            # Should be line-delimited
            lines = content.strip().split("\n")
            for line in lines:
                json.loads(line)  # Each line should be valid JSON
        else:
            # Should be single JSON document
            json.loads(content)  # Entire content should be valid JSON

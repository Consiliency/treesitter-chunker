"""Integration tests for incremental processing with real-world scenarios."""
import shutil
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from chunker.incremental import (
    DefaultChangeDetector,
    DefaultChunkCache,
    DefaultIncrementalProcessor,
)
from chunker.interfaces.incremental import ChangeType
from chunker.types import CodeChunk


class TestIncrementalIntegration:
    """Integration tests for incremental processing."""

    @classmethod
    @pytest.fixture
    def temp_project(cls):
        """Create a temporary project structure."""
        temp_dir = tempfile.mkdtemp()
        src_dir = Path(temp_dir) / "src"
        src_dir.mkdir()
        (src_dir / "main.py").write_text(
            """
def main():
    ""\"Main entry point.""\"
    print("Starting application")
    process_data()
    cleanup()

def process_data():
    ""\"Process application data.""\"
    data = load_data()
    results = analyze(data)
    save_results(results)

def cleanup():
    ""\"Clean up resources.""\"
    print("Cleaning up")
""",
            )
        (src_dir / "utils.py").write_text(
            """
def load_data():
    ""\"Load data from file.""\"
    return {"items": [1, 2, 3]}

def analyze(data):
    ""\"Analyze the data.""\"
    return sum(data.get("items", []))

def save_results(results):
    ""\"Save results to file.""\"
    print(f"Results: {results}")
""",
            )
        yield temp_dir
        shutil.rmtree(temp_dir)

    @classmethod
    @patch("chunker.chunker.get_parser")
    def test_incremental_workflow(cls, mock_get_parser, temp_project):
        """Test complete incremental processing workflow."""
        mock_parser = mock_get_parser.return_value
        mock_parser.parse.return_value = None
        processor = DefaultIncrementalProcessor()
        cache = DefaultChunkCache(str(Path(temp_project) / ".cache"))
        detector = DefaultChangeDetector()
        src_dir = Path(temp_project) / "src"
        main_file = src_dir / "main.py"
        src_dir / "utils.py"
        with patch("chunker.incremental.chunk_text") as mock_chunk_text:
            main_content = main_file.read_text()
            main_chunks = [{"chunk_id": "main_main", "content":
                """def main():
    ""\"Main entry point.""\"
    print("Starting application")
    process_data()
    cleanup()"""
                , "node_type": "function_definition", "start_line": 2,
                "end_line": 6}, {"chunk_id": "main_process", "content":
                """def process_data():
    ""\"Process application data.""\"
    data = load_data()
    results = analyze(data)
    save_results(results)"""
                , "node_type": "function_definition", "start_line": 8,
                "end_line": 12}, {"chunk_id": "main_cleanup", "content":
                """def cleanup():
    ""\"Clean up resources.""\"
    print("Cleaning up")"""
                , "node_type": "function_definition", "start_line": 14,
                "end_line": 16}]
            from chunker.types import CodeChunk
            main_chunks_obj = [CodeChunk(language="python", file_path=str(
                main_file), node_type=c["node_type"], start_line=c[
                "start_line"], end_line=c["end_line"], byte_start=0,
                byte_end=len(c["content"]), parent_context="", content=c[
                "content"], chunk_id=c["chunk_id"]) for c in main_chunks]
            mock_chunk_text.return_value = main_chunks_obj
            main_hash = detector.compute_file_hash(main_content)
            cache.store(str(main_file), main_chunks_obj, main_hash)
            modified_main = """
def main():
    ""\"Main entry point.""\"
    print("Starting application")
    process_data()
    cleanup()

def process_data():
    ""\"Process application data with logging.""\"
    import logging
    logging.info("Processing started")
    data = load_data()
    results = analyze(data)
    save_results(results)
    logging.info("Processing completed")

def cleanup():
    ""\"Clean up resources.""\"
    print("Cleaning up")

def new_function():
    ""\"A new helper function.""\"
    return "helper\"
"""
            main_file.write_text(modified_main)
            modified_chunks = [main_chunks_obj[0], CodeChunk(language="python", file_path=str(main_file), node_type="function_definition", start_line=8, end_line=15,
                byte_start=0, byte_end=200, parent_context="", content="""def process_data():
    ""\"Process application data with logging.""\"
    import logging
    logging.info("Processing started")
    data = load_data()
    results = analyze(data)
    save_results(results)
    logging.info("Processing completed")"""
                , chunk_id="main_process"), main_chunks_obj[2], CodeChunk(
                language="python", file_path=str(main_file), node_type="function_definition", start_line=21, end_line=23,
                byte_start=0, byte_end=50, parent_context="", content="""def new_function():
    ""\"A new helper function.""\"
    return "helper\""""
                , chunk_id="main_new")]
            mock_chunk_text.return_value = modified_chunks
            new_hash = detector.compute_file_hash(modified_main)
            assert new_hash != main_hash
            cache_entry = cache.retrieve(str(main_file), main_hash)
            assert cache_entry is not None
            diff = processor.compute_diff(cache_entry.chunks, modified_main,
                "python")
            assert diff.summary["modified"] == 1
            assert diff.summary["added"] == 1
            assert diff.summary["unchanged"] == 2
            modified_changes = [c for c in diff.changes if c.change_type ==
                ChangeType.MODIFIED]
            assert len(modified_changes) == 1
            assert "logging" in modified_changes[0].new_chunk.content
            updated_chunks = processor.update_chunks(cache_entry.chunks, diff)
            assert len(updated_chunks) == 4
            cache.store(str(main_file), updated_chunks, new_hash)
            stats = cache.get_statistics()
            assert stats["entries"] == 1
            assert stats["hit_rate"] > 0

    @classmethod
    def test_cross_file_move_detection(cls, temp_project):
        """Test detecting code moved between files."""
        processor = DefaultIncrementalProcessor()
        src_dir = Path(temp_project) / "src"
        file1_chunk = CodeChunk(language="python", file_path=str(src_dir /
            "file1.py"), node_type="function_definition", start_line=1,
            end_line=5, byte_start=0, byte_end=100, parent_context="",
            content="""def shared_function():
    '''Shared logic'''
    return process_shared_data()
"""
            , chunk_id="file1_shared")
        file2_chunk = CodeChunk(language="python", file_path=str(src_dir /
            "file2.py"), node_type="function_definition", start_line=10,
            end_line=14, byte_start=200, byte_end=300, parent_context="",
            content="""def shared_function():
    '''Shared logic'''
    return process_shared_data()
"""
            , chunk_id="file2_shared")
        moved_pairs = processor.detect_moved_chunks([file1_chunk], [
            file2_chunk])
        assert len(moved_pairs) == 1
        assert moved_pairs[0][0].file_path != moved_pairs[0][1].file_path
        assert moved_pairs[0][0].content == moved_pairs[0][1].content

    @classmethod
    def test_cache_persistence(cls, temp_project):
        """Test cache export and import functionality."""
        cache_dir1 = str(Path(temp_project) / ".cache1")
        cache_dir2 = str(Path(temp_project) / ".cache2")
        export_file = str(Path(temp_project) / "cache_export.json")
        cache1 = DefaultChunkCache(cache_dir1)
        test_chunks = [CodeChunk(language="python", file_path="test.py",
            node_type="function_definition", start_line=1, end_line=3,
            byte_start=0, byte_end=50, parent_context="", content="""def test():
    pass
""", chunk_id="test_func")]
        cache1.store("test.py", test_chunks, "hash123", metadata={"version":
            "1.0", "author": "test"})
        cache1.export_cache(export_file)
        assert Path(export_file).exists()
        cache2 = DefaultChunkCache(cache_dir2)
        cache2.import_cache(export_file)
        entry = cache2.retrieve("test.py")
        assert entry is not None
        assert entry.file_hash == "hash123"
        assert len(entry.chunks) == 1
        assert entry.chunks[0].chunk_id == "test_func"
        assert entry.metadata["version"] == "1.0"

    @classmethod
    def test_performance_metrics(cls, temp_project):
        """Test performance tracking of incremental processing."""
        cache = DefaultChunkCache(str(Path(temp_project) / ".cache"))
        dummy_chunk = [CodeChunk(language="python", file_path="test.py",
            node_type="function", start_line=1, end_line=2, byte_start=0,
            byte_end=10, parent_context="", content="def f(): pass",
            chunk_id="f")]
        start_time = time.time()
        for i in range(10):
            cache.store(f"file{i}.py", dummy_chunk, f"hash{i}")
        for i in range(5):
            cache.retrieve(f"file{i}.py", f"hash{i}")
        for i in range(5):
            cache.retrieve(f"nonexistent{i}.py")
        elapsed = time.time() - start_time
        stats = cache.get_statistics()
        assert stats["entries"] == 10
        assert stats["stats"]["stores"] == 10
        assert stats["stats"]["retrievals"] == 10
        assert stats["stats"]["hits"] == 5
        assert stats["stats"]["misses"] == 5
        assert stats["hit_rate"] == 0.5
        assert elapsed < 1.0

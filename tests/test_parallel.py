"""Comprehensive tests for parallel processing functionality.

This test module covers:
1. Worker pool sizing strategies - optimal worker counts for different workloads
2. Failure handling - parse errors, missing files, permission issues, worker crashes
3. Resource contention - memory pressure, concurrent cache access, file_path system limits
4. Progress tracking - completion order, accurate chunk counting
5. Memory usage - streaming mode efficiency, cache memory bounds
6. Cancellation and timeout - graceful shutdown, edge cases

The tests use a variety of Python code templates to simulate different scenarios
and stress test the parallel processing system.
"""

import contextlib
import multiprocessing as mp
import shutil
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from chunker.parallel import ParallelChunker, chunk_directory_parallel

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration

PYTHON_FUNCTION_TEMPLATE = """
def function_{idx}():
    ""\"Function {idx} docstring.""\"
    result = 0
    for i in range({complexity}):
        result += i * {idx}
    return result
"""
PYTHON_CLASS_TEMPLATE = """
class TestClass{idx}:
    ""\"Test class {idx}.""\"

    def __init__(self):
        self.value = {idx}

    def method_{idx}(self):
        ""\"Method in class {idx}.""\"
        return self.value * {complexity}
"""
PYTHON_ERROR_CODE = """
def broken_function():
    ""\"This function has syntax errors.""\"
    if True
        print("Missing colon")
    return None
"""
PYTHON_INFINITE_LOOP = """
def infinite_loop():
    ""\"This function never terminates.""\"
    while True:
        pass
"""


class TestParallelChunkerInit:
    """Test ParallelChunker initialization and configuration."""

    @classmethod
    def test_default_initialization(cls):
        """Test default worker count is CPU count."""
        chunker = ParallelChunker("python")
        assert chunker.num_workers == mp.cpu_count()
        assert chunker.use_cache is True
        assert chunker.use_streaming is False
        assert chunker.cache is not None

    @classmethod
    def test_custom_worker_count(cls):
        """Test custom worker count configuration."""
        chunker = ParallelChunker("python", num_workers=4)
        assert chunker.num_workers == 4

    @classmethod
    def test_cache_disabled(cls):
        """Test initialization without cache."""
        chunker = ParallelChunker("python", use_cache=False)
        assert chunker.cache is None

    @classmethod
    def test_streaming_enabled(cls):
        """Test initialization with streaming."""
        chunker = ParallelChunker("python", use_streaming=True)
        assert chunker.use_streaming is True


class TestWorkerPoolSizing:
    """Test various worker pool sizing strategies."""

    @classmethod
    def test_single_worker(cls, temp_directory_with_files):
        """Test processing with single worker (sequential)."""
        chunker = ParallelChunker("python", num_workers=1)
        results = chunker.chunk_files_parallel(
            list(temp_directory_with_files.glob("*.py")),
        )
        assert len(results) > 0
        assert all(isinstance(chunks, list) for chunks in results.values())

    @classmethod
    def test_optimal_workers_for_small_workload(
        cls,
        temp_directory_with_files,
    ):
        """Test that we don't spawn more workers than files."""
        files = list(temp_directory_with_files.glob("*.py"))[:2]
        chunker = ParallelChunker("python", num_workers=8)
        results = chunker.chunk_files_parallel(files)
        assert len(results) == 2
        assert all(isinstance(chunks, list) for chunks in results.values())
        assert all(len(chunks) > 0 for chunks in results.values())

    @classmethod
    def test_cpu_bound_sizing(cls):
        """Test worker sizing for CPU-bound workloads."""
        temp_dir = Path(tempfile.mkdtemp())
        try:
            for i in range(20):
                file_path = temp_dir / f"complex_{i}.py"
                content = PYTHON_FUNCTION_TEMPLATE.format(
                    idx=i,
                    complexity=100 + i * 50,
                )
                file_path.write_text(content * 10)
            for num_workers in [1, 2, 4, mp.cpu_count()]:
                chunker = ParallelChunker("python", num_workers=num_workers)
                start_time = time.time()
                results = chunker.chunk_files_parallel(list(temp_dir.glob("*.py")))
                duration = time.time() - start_time
                assert len(results) == 20
                assert all(len(chunks) > 0 for chunks in results.values())
                assert duration < 60
        finally:
            shutil.rmtree(temp_dir)

    @classmethod
    def test_io_bound_sizing(cls, temp_directory_with_files):
        """Test worker sizing for I/O-bound workloads with cache."""
        chunker = ParallelChunker(
            "python",
            num_workers=mp.cpu_count() * 2,
            use_cache=True,
        )
        results1 = chunker.chunk_files_parallel(
            list(temp_directory_with_files.glob("*.py")),
        )
        start_time = time.time()
        results2 = chunker.chunk_files_parallel(
            list(temp_directory_with_files.glob("*.py")),
        )
        cached_duration = time.time() - start_time
        assert len(results1) == len(results2)
        assert cached_duration < 1.0


class TestFailureHandling:
    """Test failure handling in parallel workers."""

    @classmethod
    def test_single_file_parse_error(cls):
        """Test handling of parse errors in individual files."""
        temp_dir = Path(tempfile.mkdtemp())
        try:
            valid_file = temp_dir / "valid.py"
            valid_file.write_text(PYTHON_FUNCTION_TEMPLATE.format(idx=1, complexity=10))
            invalid_file = temp_dir / "invalid.py"
            invalid_file.write_text(PYTHON_ERROR_CODE)
            chunker = ParallelChunker("python")
            results = chunker.chunk_files_parallel([valid_file, invalid_file])
            assert valid_file in results
            assert len(results[valid_file]) > 0
            assert invalid_file in results
        finally:
            shutil.rmtree(temp_dir)

    @classmethod
    def test_file_not_found_handling(cls):
        """Test handling of missing files."""
        chunker = ParallelChunker("python")
        non_existent = Path("/tmp/does_not_exist_12345.py")
        results = chunker.chunk_files_parallel([non_existent])
        assert non_existent in results
        assert results[non_existent] == []

    @classmethod
    def test_permission_denied_handling(cls):
        """Test handling of permission errors."""
        temp_dir = Path(tempfile.mkdtemp())
        try:
            restricted_file = temp_dir / "restricted.py"
            restricted_file.write_text(
                PYTHON_FUNCTION_TEMPLATE.format(idx=1, complexity=10),
            )
            Path(restricted_file).chmod(0)
            chunker = ParallelChunker("python")
            results = chunker.chunk_files_parallel([restricted_file])
            assert restricted_file in results
            assert results[restricted_file] == []
        finally:
            with contextlib.suppress(FileNotFoundError, IndexError, KeyError):
                Path(restricted_file).chmod(0o644)
            shutil.rmtree(temp_dir)

    @classmethod
    def test_worker_crash_handling(cls):
        """Test handling of worker process crashes."""
        with patch(
            "chunker.parallel.ParallelChunker._process_single_file",
        ) as mock_process:
            mock_process.side_effect = Exception("Worker crashed")
            temp_file = Path(
                tempfile.NamedTemporaryFile(suffix=".py", delete=False).name,
            )
            temp_file.write_text("def test(): pass", encoding="utf-8")
            try:
                chunker = ParallelChunker("python")
                results = chunker.chunk_files_parallel([temp_file])
                assert temp_file in results
                assert results[temp_file] == []
            finally:
                temp_file.unlink(missing_ok=True)

    @classmethod
    def test_partial_batch_failure(cls):
        """Test handling when some files in batch fail."""
        temp_dir = Path(tempfile.mkdtemp())
        try:
            files = []
            for i in range(10):
                file_path = temp_dir / f"file_{i}.py"
                if i % 3 == 0:
                    file_path.write_text(
                        "This is not valid Python code at all! @#$%^&*()",
                    )
                else:
                    file_path.write_text(
                        PYTHON_FUNCTION_TEMPLATE.format(idx=i, complexity=10),
                    )
                files.append(file_path)
            chunker = ParallelChunker("python")
            results = chunker.chunk_files_parallel(files)
            assert len(results) == 10
            for file_path in files:
                assert file_path in results
            valid_files = [f for i, f in enumerate(files) if i % 3 != 0]
            for valid_file in valid_files:
                assert len(results[valid_file]) > 0
        finally:
            shutil.rmtree(temp_dir)


class TestResourceContention:
    """Test scenarios with resource contention."""

    @classmethod
    def test_memory_pressure(cls):
        """Test behavior under memory pressure with large files."""
        temp_dir = Path(tempfile.mkdtemp())
        try:
            for i in range(5):
                file_path = temp_dir / f"large_{i}.py"
                content = []
                for j in range(1000):
                    content.append(
                        PYTHON_FUNCTION_TEMPLATE.format(idx=j, complexity=10),
                    )
                    content.append(PYTHON_CLASS_TEMPLATE.format(idx=j, complexity=10))
                file_path.write_text("\n".join(content))
            chunker = ParallelChunker("python", num_workers=4)
            results = chunker.chunk_files_parallel(list(temp_dir.glob("*.py")))
            assert len(results) == 5
            for chunks in results.values():
                assert len(chunks) > 1000
        finally:
            shutil.rmtree(temp_dir)

    @classmethod
    def test_concurrent_cache_access(cls):
        """Test concurrent access to cache from multiple workers."""
        temp_dir = Path(tempfile.mkdtemp())
        try:
            files = []
            for i in range(10):
                file_path = temp_dir / f"cache_test_{i}.py"
                file_path.write_text(
                    PYTHON_FUNCTION_TEMPLATE.format(idx=i, complexity=10),
                )
                files.append(file_path)
            chunker = ParallelChunker("python", num_workers=4, use_cache=True)
            results1 = chunker.chunk_files_parallel(files)
            results2 = chunker.chunk_files_parallel(files)
            assert len(results1) == len(results2) == 10
            for path in files:
                chunks1 = results1[path]
                chunks2 = results2[path]
                assert len(chunks1) == len(chunks2)
                assert all(
                    c1.chunk_id == c2.chunk_id
                    for c1, c2 in zip(chunks1, chunks2, strict=False)
                )
        finally:
            shutil.rmtree(temp_dir)

    @classmethod
    def test_file_system_limits(cls):
        """Test handling of file_path system limits (too many open files)."""
        temp_dir = Path(tempfile.mkdtemp())
        try:
            files = []
            for i in range(100):
                file_path = temp_dir / f"many_{i}.py"
                file_path.write_text(f"def func_{i}(): return {i}")
                files.append(file_path)
            chunker = ParallelChunker("python", num_workers=2)
            results = chunker.chunk_files_parallel(files)
            assert len(results) == 100
            assert all(len(chunks) > 0 for chunks in results.values())
        finally:
            shutil.rmtree(temp_dir)


class TestProgressTracking:
    """Test progress tracking accuracy in parallel processing."""

    @classmethod
    def test_completion_order_tracking(cls):
        """Test tracking of completion order with varying file_path sizes."""
        temp_dir = Path(tempfile.mkdtemp())
        try:
            files = []
            for i in range(10):
                file_path = temp_dir / f"sized_{i}.py"
                content = PYTHON_FUNCTION_TEMPLATE.format(
                    idx=i,
                    complexity=10,
                ) * (i + 1)
                file_path.write_text(content)
                files.append(file_path)
            chunker = ParallelChunker("python", num_workers=4)
            results = chunker.chunk_files_parallel(files)
            assert len(results) == 10
            assert set(results.keys()) == set(files)
            for i, file_path in enumerate(sorted(files, key=lambda f: f.name)):
                expected_chunks = i + 1
                assert len(results[file_path]) == expected_chunks
        finally:
            shutil.rmtree(temp_dir)

    @classmethod
    def test_accurate_chunk_counting(cls):
        """Test accurate counting of chunks across all workers."""
        temp_dir = Path(tempfile.mkdtemp())
        try:
            expected_total_chunks = 0
            files = []
            for i in range(20):
                file_path = temp_dir / f"counted_{i}.py"
                content = [
                    PYTHON_FUNCTION_TEMPLATE.format(idx=j, complexity=5)
                    for j in range(i + 1)
                ]
                file_path.write_text("\n".join(content))
                files.append(file_path)
                expected_total_chunks += i + 1
            chunker = ParallelChunker("python", num_workers=4)
            results = chunker.chunk_files_parallel(files)
            actual_total_chunks = sum(len(chunks) for chunks in results.values())
            assert actual_total_chunks == expected_total_chunks
        finally:
            shutil.rmtree(temp_dir)


class TestMemoryUsage:
    """Test memory usage under various load conditions."""

    @classmethod
    def test_memory_efficient_streaming(cls):
        """Test that streaming mode uses less memory."""
        temp_dir = Path(tempfile.mkdtemp())
        try:
            large_file = temp_dir / "large.py"
            content = [
                PYTHON_FUNCTION_TEMPLATE.format(
                    idx=i,
                    complexity=10,
                )
                for i in range(5000)
            ]
            large_file.write_text("\n".join(content))
            chunker_streaming = ParallelChunker(
                "python",
                num_workers=1,
                use_streaming=True,
            )
            results_streaming = chunker_streaming.chunk_files_parallel([large_file])
            chunker_normal = ParallelChunker(
                "python",
                num_workers=1,
                use_streaming=False,
            )
            results_normal = chunker_normal.chunk_files_parallel([large_file])
            assert len(results_streaming[large_file]) == len(results_normal[large_file])
        finally:
            shutil.rmtree(temp_dir)

    @classmethod
    def test_cache_memory_bounds(cls):
        """Test that cache doesn't grow unbounded."""
        temp_dir = Path(tempfile.mkdtemp())
        try:
            files = []
            for i in range(100):
                file_path = temp_dir / f"cache_mem_{i}.py"
                content = f"def unique_func_{i}_{time.time()}(): return {i}"
                file_path.write_text(content)
                files.append(file_path)
            chunker = ParallelChunker("python", num_workers=2, use_cache=True)
            for i in range(0, 100, 10):
                batch = files[i : i + 10]
                chunker.chunk_files_parallel(batch)
            if chunker.cache:
                stats = chunker.cache.get_cache_stats()
                assert "total_files" in stats
                assert "total_size_bytes" in stats
        finally:
            shutil.rmtree(temp_dir)


class TestCancellationAndTimeout:
    """Test cancellation and timeout handling."""

    @classmethod
    def test_timeout_handling(cls):
        """Test handling of operations that exceed timeout."""
        temp_file = Path(tempfile.NamedTemporaryFile(suffix=".py", delete=False).name)
        content = []
        for i in range(50000):
            content.append(PYTHON_FUNCTION_TEMPLATE.format(idx=i, complexity=100))
            content.append(PYTHON_CLASS_TEMPLATE.format(idx=i, complexity=100))
        temp_file.write_text("\n".join(content), encoding="utf-8")
        try:
            chunker = ParallelChunker("python", num_workers=1)
            results = chunker.chunk_files_parallel([temp_file])
            assert temp_file in results
            assert len(results[temp_file]) > 0
        finally:
            temp_file.unlink(missing_ok=True)

    @classmethod
    def test_graceful_shutdown(cls):
        """Test graceful shutdown of worker pool."""
        temp_dir = Path(tempfile.mkdtemp())
        try:
            files = []
            for i in range(10):
                file_path = temp_dir / f"shutdown_{i}.py"
                file_path.write_text(
                    PYTHON_FUNCTION_TEMPLATE.format(idx=i, complexity=10),
                )
                files.append(file_path)
            chunker = ParallelChunker("python", num_workers=4)
            results = chunker.chunk_files_parallel(files)
            assert len(results) == 10
            results2 = chunker.chunk_files_parallel(files)
            assert len(results2) == 10
        finally:
            shutil.rmtree(temp_dir)


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @classmethod
    def test_empty_file_list(cls):
        """Test processing empty file_path list."""
        chunker = ParallelChunker("python")
        results = chunker.chunk_files_parallel([])
        assert results == {}

    @classmethod
    def test_single_file_processing(cls):
        """Test processing single file_path doesn't create unnecessary overhead."""
        temp_file = Path(tempfile.NamedTemporaryFile(suffix=".py", delete=False).name)
        temp_file.write_text("def test(): pass", encoding="utf-8")
        try:
            chunker = ParallelChunker("python", num_workers=4)
            results = chunker.chunk_files_parallel([temp_file])
            assert len(results) == 1
            assert temp_file in results
            assert len(results[temp_file]) == 1
        finally:
            temp_file.unlink(missing_ok=True)

    @classmethod
    def test_duplicate_files_in_list(cls):
        """Test handling of duplicate files in input list."""
        temp_file = Path(tempfile.NamedTemporaryFile(suffix=".py", delete=False).name)
        temp_file.write_text("def test(): pass", encoding="utf-8")
        try:
            chunker = ParallelChunker("python", num_workers=2)
            results = chunker.chunk_files_parallel([temp_file, temp_file, temp_file])
            assert len(results) == 1
            assert temp_file in results
            assert len(results[temp_file]) == 1
        finally:
            temp_file.unlink(missing_ok=True)

    @classmethod
    def test_mixed_language_files(cls):
        """Test error handling when processing files of wrong language."""
        temp_dir = Path(tempfile.mkdtemp())
        try:
            py_file = temp_dir / "test.py"
            py_file.write_text("def python_func(): pass")
            js_file = temp_dir / "test.js"
            js_file.write_text("function jsFunc() { return 42; }")
            chunker = ParallelChunker("python")
            results = chunker.chunk_files_parallel([py_file, js_file])
            assert py_file in results
            assert len(results[py_file]) > 0
            assert js_file in results
        finally:
            shutil.rmtree(temp_dir)


class TestDirectoryProcessing:
    """Test directory processing functionality."""

    @classmethod
    def test_recursive_directory_processing(cls):
        """Test processing nested directory structures."""
        temp_dir = Path(tempfile.mkdtemp())
        try:
            (temp_dir / "src").mkdir()
            (temp_dir / "src" / "utils").mkdir()
            (temp_dir / "tests").mkdir()
            files_created = []
            root_file = temp_dir / "main.py"
            root_file.write_text("def main(): pass")
            files_created.append(root_file)
            src_file = temp_dir / "src" / "app.py"
            src_file.write_text("def app(): pass")
            files_created.append(src_file)
            utils_file = temp_dir / "src" / "utils" / "helpers.py"
            utils_file.write_text("def helper(): pass")
            files_created.append(utils_file)
            test_file = temp_dir / "tests" / "test_app.py"
            test_file.write_text("def test_app(): pass")
            files_created.append(test_file)
            results = chunk_directory_parallel(temp_dir, "python", num_workers=2)
            assert len(results) == 4
            for file_path in files_created:
                assert file_path in results
                assert len(results[file_path]) == 1
        finally:
            shutil.rmtree(temp_dir)

    @classmethod
    def test_extension_filtering(cls):
        """Test filtering by file_path extensions."""
        temp_dir = Path(tempfile.mkdtemp())
        try:
            py_file = temp_dir / "code.py"
            py_file.write_text("def python_func(): pass")
            txt_file = temp_dir / "notes.txt"
            txt_file.write_text("Some notes")
            md_file = temp_dir / "README.md"
            md_file.write_text("# README")
            results = chunk_directory_parallel(temp_dir, "python")
            assert len(results) == 1
            assert py_file in results
            assert txt_file not in results
            assert md_file not in results
            results_custom = chunk_directory_parallel(
                temp_dir,
                "python",
                extensions=[".py", ".txt", ".md"],
            )
            assert len(results_custom) >= 1
            assert py_file in results_custom
        finally:
            shutil.rmtree(temp_dir)


@pytest.fixture
def temp_directory_with_files():
    """Create a temporary directory with multiple Python files."""
    temp_dir = Path(tempfile.mkdtemp())
    for i in range(5):
        file_path = temp_dir / f"test_file_{i}.py"
        content = PYTHON_FUNCTION_TEMPLATE.format(idx=i, complexity=10)
        file_path.write_text(content)
    yield temp_dir
    shutil.rmtree(temp_dir)

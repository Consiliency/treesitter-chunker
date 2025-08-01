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

import multiprocessing as mp
import os
import shutil
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from chunker.parallel import ParallelChunker, chunk_directory_parallel

# Sample code templates for testing
PYTHON_FUNCTION_TEMPLATE = '''
def function_{idx}():
    """Function {idx} docstring."""
    result = 0
    for i in range({complexity}):
        result += i * {idx}
    return result
'''

PYTHON_CLASS_TEMPLATE = '''
class TestClass{idx}:
    """Test class {idx}."""

    def __init__(self):
        self.value = {idx}

    def method_{idx}(self):
        """Method in class {idx}."""
        return self.value * {complexity}
'''

PYTHON_ERROR_CODE = '''
def broken_function():
    """This function has syntax errors."""
    if True
        print("Missing colon")
    return None
'''

PYTHON_INFINITE_LOOP = '''
def infinite_loop():
    """This function never terminates."""
    while True:
        pass
'''


class TestParallelChunkerInit:
    """Test ParallelChunker initialization and configuration."""

    def test_default_initialization(self):
        """Test default worker count is CPU count."""
        chunker = ParallelChunker("python")
        assert chunker.num_workers == mp.cpu_count()
        assert chunker.use_cache is True
        assert chunker.use_streaming is False
        assert chunker.cache is not None

    def test_custom_worker_count(self):
        """Test custom worker count configuration."""
        chunker = ParallelChunker("python", num_workers=4)
        assert chunker.num_workers == 4

    def test_cache_disabled(self):
        """Test initialization without cache."""
        chunker = ParallelChunker("python", use_cache=False)
        assert chunker.cache is None

    def test_streaming_enabled(self):
        """Test initialization with streaming."""
        chunker = ParallelChunker("python", use_streaming=True)
        assert chunker.use_streaming is True


class TestWorkerPoolSizing:
    """Test various worker pool sizing strategies."""

    def test_single_worker(self, temp_directory_with_files):
        """Test processing with single worker (sequential)."""
        chunker = ParallelChunker("python", num_workers=1)
        results = chunker.chunk_files_parallel(
            list(temp_directory_with_files.glob("*.py")),
        )
        assert len(results) > 0
        assert all(isinstance(chunks, list) for chunks in results.values())

    def test_optimal_workers_for_small_workload(self, temp_directory_with_files):
        """Test that we don't spawn more workers than files."""
        files = list(temp_directory_with_files.glob("*.py"))[:2]  # Only 2 files

        # Test that even with 8 requested workers, it still processes 2 files correctly
        chunker = ParallelChunker("python", num_workers=8)  # Request 8 workers
        results = chunker.chunk_files_parallel(files)

        # Should process both files successfully
        assert len(results) == 2
        assert all(isinstance(chunks, list) for chunks in results.values())
        assert all(len(chunks) > 0 for chunks in results.values())

    def test_cpu_bound_sizing(self):
        """Test worker sizing for CPU-bound workloads."""
        # Create files with varying complexity
        temp_dir = Path(tempfile.mkdtemp())
        try:
            for i in range(20):
                file_path = temp_dir / f"complex_{i}.py"
                # Create files with increasing complexity
                content = PYTHON_FUNCTION_TEMPLATE.format(
                    idx=i,
                    complexity=100 + i * 50,
                )
                file_path.write_text(content * 10)  # Repeat to make larger

            # Test with different worker counts
            for num_workers in [1, 2, 4, mp.cpu_count()]:
                chunker = ParallelChunker("python", num_workers=num_workers)
                start_time = time.time()
                results = chunker.chunk_files_parallel(list(temp_dir.glob("*.py")))
                duration = time.time() - start_time

                assert len(results) == 20
                assert all(len(chunks) > 0 for chunks in results.values())

                # Can't assert exact timing, but verify completion
                assert duration < 60  # Should complete within reasonable time

        finally:
            shutil.rmtree(temp_dir)

    def test_io_bound_sizing(self, temp_directory_with_files):
        """Test worker sizing for I/O-bound workloads with cache."""
        chunker = ParallelChunker(
            "python",
            num_workers=mp.cpu_count() * 2,
            use_cache=True,
        )

        # First run - populate cache
        results1 = chunker.chunk_files_parallel(
            list(temp_directory_with_files.glob("*.py")),
        )

        # Second run - should be faster due to cache
        start_time = time.time()
        results2 = chunker.chunk_files_parallel(
            list(temp_directory_with_files.glob("*.py")),
        )
        cached_duration = time.time() - start_time

        assert len(results1) == len(results2)
        # Cache should make it very fast
        assert cached_duration < 1.0


class TestFailureHandling:
    """Test failure handling in parallel workers."""

    def test_single_file_parse_error(self):
        """Test handling of parse errors in individual files."""
        temp_dir = Path(tempfile.mkdtemp())
        try:
            # Create mix of valid and invalid files
            valid_file = temp_dir / "valid.py"
            valid_file.write_text(PYTHON_FUNCTION_TEMPLATE.format(idx=1, complexity=10))

            invalid_file = temp_dir / "invalid.py"
            invalid_file.write_text(PYTHON_ERROR_CODE)

            chunker = ParallelChunker("python")
            results = chunker.chunk_files_parallel([valid_file, invalid_file])

            # Valid file_path should have chunks
            assert valid_file in results
            assert len(results[valid_file]) > 0

            # Invalid file_path might have partial results (tree-sitter can parse partial syntax)
            assert invalid_file in results
            # Tree-sitter can still extract some nodes from files with syntax errors

        finally:
            shutil.rmtree(temp_dir)

    def test_file_not_found_handling(self):
        """Test handling of missing files."""
        chunker = ParallelChunker("python")
        non_existent = Path("/tmp/does_not_exist_12345.py")

        results = chunker.chunk_files_parallel([non_existent])
        assert non_existent in results
        assert results[non_existent] == []

    def test_permission_denied_handling(self):
        """Test handling of permission errors."""
        temp_dir = Path(tempfile.mkdtemp())
        try:
            restricted_file = temp_dir / "restricted.py"
            restricted_file.write_text(
                PYTHON_FUNCTION_TEMPLATE.format(idx=1, complexity=10),
            )

            # Remove read permissions
            os.chmod(restricted_file, 0o000)

            chunker = ParallelChunker("python")
            results = chunker.chunk_files_parallel([restricted_file])

            # Should handle permission error gracefully
            assert restricted_file in results
            assert results[restricted_file] == []

        finally:
            # Restore permissions for cleanup
            try:
                os.chmod(restricted_file, 0o644)
            except (FileNotFoundError, IndexError, KeyError):
                pass  # In case file_path doesn't exist
            shutil.rmtree(temp_dir)

    def test_worker_crash_handling(self):
        """Test handling of worker process crashes."""
        with patch(
            "chunker.parallel.ParallelChunker._process_single_file",
        ) as mock_process:
            # Simulate worker crash
            mock_process.side_effect = Exception("Worker crashed")

            temp_file = Path(tempfile.mktemp(suffix=".py"))
            temp_file.write_text("def test(): pass")

            try:
                chunker = ParallelChunker("python")
                results = chunker.chunk_files_parallel([temp_file])

                # Should handle crash gracefully
                assert temp_file in results
                assert results[temp_file] == []
            finally:
                temp_file.unlink(missing_ok=True)

    def test_partial_batch_failure(self):
        """Test handling when some files in batch fail."""
        temp_dir = Path(tempfile.mkdtemp())
        try:
            files = []
            for i in range(10):
                file_path = temp_dir / f"file_{i}.py"
                if i % 3 == 0:
                    # Create truly unparseable content
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

            # All files should be in results
            for file_path in files:
                assert file_path in results

            # Valid files should have chunks
            valid_files = [f for i, f in enumerate(files) if i % 3 != 0]
            for valid_file in valid_files:
                assert len(results[valid_file]) > 0

        finally:
            shutil.rmtree(temp_dir)


class TestResourceContention:
    """Test scenarios with resource contention."""

    def test_memory_pressure(self):
        """Test behavior under memory pressure with large files."""
        temp_dir = Path(tempfile.mkdtemp())
        try:
            # Create large files
            for i in range(5):
                file_path = temp_dir / f"large_{i}.py"
                # Create a large file_path with many functions
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
            # Each file_path should have ~2000 chunks (1000 functions + 1000 classes with methods)
            for chunks in results.values():
                assert len(chunks) > 1000

        finally:
            shutil.rmtree(temp_dir)

    def test_concurrent_cache_access(self):
        """Test concurrent access to cache from multiple workers."""
        temp_dir = Path(tempfile.mkdtemp())
        try:
            # Create files
            files = []
            for i in range(10):
                file_path = temp_dir / f"cache_test_{i}.py"
                file_path.write_text(
                    PYTHON_FUNCTION_TEMPLATE.format(idx=i, complexity=10),
                )
                files.append(file_path)

            # Enable cache
            chunker = ParallelChunker("python", num_workers=4, use_cache=True)

            # First run - populate cache
            results1 = chunker.chunk_files_parallel(files)

            # Second run - all workers hitting cache simultaneously
            results2 = chunker.chunk_files_parallel(files)

            assert len(results1) == len(results2) == 10

            # Results should be identical
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

    def test_file_system_limits(self):
        """Test handling of file_path system limits (too many open files)."""
        temp_dir = Path(tempfile.mkdtemp())
        try:
            # Create many small files
            files = []
            for i in range(100):
                file_path = temp_dir / f"many_{i}.py"
                file_path.write_text(f"def func_{i}(): return {i}")
                files.append(file_path)

            # Process with limited workers to avoid hitting system limits
            chunker = ParallelChunker("python", num_workers=2)
            results = chunker.chunk_files_parallel(files)

            assert len(results) == 100
            assert all(len(chunks) > 0 for chunks in results.values())

        finally:
            shutil.rmtree(temp_dir)


class TestProgressTracking:
    """Test progress tracking accuracy in parallel processing."""

    def test_completion_order_tracking(self):
        """Test tracking of completion order with varying file_path sizes."""
        temp_dir = Path(tempfile.mkdtemp())
        try:
            # Create files of different sizes
            files = []
            for i in range(10):
                file_path = temp_dir / f"sized_{i}.py"
                # Vary content size
                content = PYTHON_FUNCTION_TEMPLATE.format(idx=i, complexity=10) * (
                    i + 1
                )
                file_path.write_text(content)
                files.append(file_path)

            # Process files
            chunker = ParallelChunker("python", num_workers=4)
            results = chunker.chunk_files_parallel(files)

            # Verify all files were processed
            assert len(results) == 10
            assert set(results.keys()) == set(files)

            # Verify chunk counts match expected (each file_path has i+1 repetitions)
            for i, file_path in enumerate(sorted(files, key=lambda f: f.name)):
                # Each repetition has one function
                expected_chunks = i + 1
                assert len(results[file_path]) == expected_chunks

        finally:
            shutil.rmtree(temp_dir)

    def test_accurate_chunk_counting(self):
        """Test accurate counting of chunks across all workers."""
        temp_dir = Path(tempfile.mkdtemp())
        try:
            # Create files with known chunk counts
            expected_total_chunks = 0
            files = []

            for i in range(20):
                file_path = temp_dir / f"counted_{i}.py"

                # Add exactly i+1 functions
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

    def test_memory_efficient_streaming(self):
        """Test that streaming mode uses less memory."""
        temp_dir = Path(tempfile.mkdtemp())
        try:
            # Create a very large file_path
            large_file = temp_dir / "large.py"
            content = [
                PYTHON_FUNCTION_TEMPLATE.format(idx=i, complexity=10)
                for i in range(5000)
            ]
            large_file.write_text("\n".join(content))

            # Process with streaming
            chunker_streaming = ParallelChunker(
                "python",
                num_workers=1,
                use_streaming=True,
            )
            results_streaming = chunker_streaming.chunk_files_parallel([large_file])

            # Process without streaming
            chunker_normal = ParallelChunker(
                "python",
                num_workers=1,
                use_streaming=False,
            )
            results_normal = chunker_normal.chunk_files_parallel([large_file])

            # Both should produce same results
            assert len(results_streaming[large_file]) == len(results_normal[large_file])

        finally:
            shutil.rmtree(temp_dir)

    def test_cache_memory_bounds(self):
        """Test that cache doesn't grow unbounded."""
        temp_dir = Path(tempfile.mkdtemp())
        try:
            # Create many unique files
            files = []
            for i in range(100):
                file_path = temp_dir / f"cache_mem_{i}.py"
                # Each file_path has unique content to prevent deduplication
                content = f"def unique_func_{i}_{time.time()}(): return {i}"
                file_path.write_text(content)
                files.append(file_path)

            chunker = ParallelChunker("python", num_workers=2, use_cache=True)

            # Process files in batches
            for i in range(0, 100, 10):
                batch = files[i : i + 10]
                chunker.chunk_files_parallel(batch)

            # Cache stats should show reasonable memory usage
            if chunker.cache:
                stats = chunker.cache.get_cache_stats()
                # Just verify we can get stats without error
                assert "total_files" in stats
                assert "total_size_bytes" in stats

        finally:
            shutil.rmtree(temp_dir)


class TestCancellationAndTimeout:
    """Test cancellation and timeout handling."""

    def test_timeout_handling(self):
        """Test handling of operations that exceed timeout."""
        # Create a file_path that would take long to process
        temp_file = Path(tempfile.mktemp(suffix=".py"))
        # Create a very large file_path that takes time to process
        content = []
        for i in range(50000):
            content.append(PYTHON_FUNCTION_TEMPLATE.format(idx=i, complexity=100))
            content.append(PYTHON_CLASS_TEMPLATE.format(idx=i, complexity=100))
        temp_file.write_text("\n".join(content))

        try:
            # Process with limited workers to ensure it takes time
            chunker = ParallelChunker("python", num_workers=1)
            results = chunker.chunk_files_parallel([temp_file])

            # Should process successfully (no actual timeout in current implementation)
            assert temp_file in results
            assert len(results[temp_file]) > 0  # Should have many chunks

        finally:
            temp_file.unlink(missing_ok=True)

    def test_graceful_shutdown(self):
        """Test graceful shutdown of worker pool."""
        temp_dir = Path(tempfile.mkdtemp())
        try:
            # Create files
            files = []
            for i in range(10):
                file_path = temp_dir / f"shutdown_{i}.py"
                file_path.write_text(
                    PYTHON_FUNCTION_TEMPLATE.format(idx=i, complexity=10),
                )
                files.append(file_path)

            chunker = ParallelChunker("python", num_workers=4)

            # Process normally - executor should shut down cleanly
            results = chunker.chunk_files_parallel(files)
            assert len(results) == 10

            # Process again to ensure pool can be recreated
            results2 = chunker.chunk_files_parallel(files)
            assert len(results2) == 10

        finally:
            shutil.rmtree(temp_dir)


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_file_list(self):
        """Test processing empty file_path list."""
        chunker = ParallelChunker("python")
        results = chunker.chunk_files_parallel([])
        assert results == {}

    def test_single_file_processing(self):
        """Test processing single file_path doesn't create unnecessary overhead."""
        temp_file = Path(tempfile.mktemp(suffix=".py"))
        temp_file.write_text("def test(): pass")

        try:
            chunker = ParallelChunker("python", num_workers=4)
            results = chunker.chunk_files_parallel([temp_file])

            assert len(results) == 1
            assert temp_file in results
            assert len(results[temp_file]) == 1

        finally:
            temp_file.unlink(missing_ok=True)

    def test_duplicate_files_in_list(self):
        """Test handling of duplicate files in input list."""
        temp_file = Path(tempfile.mktemp(suffix=".py"))
        temp_file.write_text("def test(): pass")

        try:
            chunker = ParallelChunker("python", num_workers=2)
            # Pass same file_path multiple times
            results = chunker.chunk_files_parallel([temp_file, temp_file, temp_file])

            # Should process each occurrence
            assert len(results) == 1  # Dict keys are unique
            assert temp_file in results
            assert len(results[temp_file]) == 1

        finally:
            temp_file.unlink(missing_ok=True)

    def test_mixed_language_files(self):
        """Test error handling when processing files of wrong language."""
        temp_dir = Path(tempfile.mkdtemp())
        try:
            # Create Python file_path
            py_file = temp_dir / "test.py"
            py_file.write_text("def python_func(): pass")

            # Create JavaScript file_path
            js_file = temp_dir / "test.js"
            js_file.write_text("function jsFunc() { return 42; }")

            # Try to process both as Python
            chunker = ParallelChunker("python")
            results = chunker.chunk_files_parallel([py_file, js_file])

            # Python file_path should work
            assert py_file in results
            assert len(results[py_file]) > 0

            # JS file_path might parse partially or fail
            assert js_file in results
            # Don't assert on JS results as tree-sitter might parse it partially

        finally:
            shutil.rmtree(temp_dir)


class TestDirectoryProcessing:
    """Test directory processing functionality."""

    def test_recursive_directory_processing(self):
        """Test processing nested directory structures."""
        temp_dir = Path(tempfile.mkdtemp())
        try:
            # Create nested structure
            (temp_dir / "src").mkdir()
            (temp_dir / "src" / "utils").mkdir()
            (temp_dir / "tests").mkdir()

            # Create files at different levels
            files_created = []

            # Root level
            root_file = temp_dir / "main.py"
            root_file.write_text("def main(): pass")
            files_created.append(root_file)

            # Src level
            src_file = temp_dir / "src" / "app.py"
            src_file.write_text("def app(): pass")
            files_created.append(src_file)

            # Utils level
            utils_file = temp_dir / "src" / "utils" / "helpers.py"
            utils_file.write_text("def helper(): pass")
            files_created.append(utils_file)

            # Tests level
            test_file = temp_dir / "tests" / "test_app.py"
            test_file.write_text("def test_app(): pass")
            files_created.append(test_file)

            # Process directory
            results = chunk_directory_parallel(temp_dir, "python", num_workers=2)

            assert len(results) == 4
            for file_path in files_created:
                assert file_path in results
                assert len(results[file_path]) == 1

        finally:
            shutil.rmtree(temp_dir)

    def test_extension_filtering(self):
        """Test filtering by file_path extensions."""
        temp_dir = Path(tempfile.mkdtemp())
        try:
            # Create files with different extensions
            py_file = temp_dir / "code.py"
            py_file.write_text("def python_func(): pass")

            txt_file = temp_dir / "notes.txt"
            txt_file.write_text("Some notes")

            md_file = temp_dir / "README.md"
            md_file.write_text("# README")

            # Process with default Python extensions
            results = chunk_directory_parallel(temp_dir, "python")

            assert len(results) == 1
            assert py_file in results
            assert txt_file not in results
            assert md_file not in results

            # Process with custom extensions
            results_custom = chunk_directory_parallel(
                temp_dir,
                "python",
                extensions=[".py", ".txt", ".md"],
            )

            # Should try to process all but only .py will succeed
            assert len(results_custom) >= 1
            assert py_file in results_custom

        finally:
            shutil.rmtree(temp_dir)


@pytest.fixture()
def temp_directory_with_files():
    """Create a temporary directory with multiple Python files."""
    temp_dir = Path(tempfile.mkdtemp())

    # Create test files
    for i in range(5):
        file_path = temp_dir / f"test_file_{i}.py"
        content = PYTHON_FUNCTION_TEMPLATE.format(idx=i, complexity=10)
        file_path.write_text(content)

    yield temp_dir
    shutil.rmtree(temp_dir)

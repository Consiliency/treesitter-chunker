"""Comprehensive tests for the ASTCache caching system."""

import shutil
import sqlite3
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from chunker import chunk_file
from chunker.cache import ASTCache
from chunker.streaming import get_file_metadata
from chunker.types import CodeChunk

# Sample code for testing
SAMPLE_PYTHON_CODE = '''
def calculate_sum(a, b):
    """Calculate the sum of two numbers."""
    return a + b

class MathOperations:
    """A class for basic math operations."""

    def multiply(self, x, y):
        """Multiply two numbers."""
        return x * y

    def divide(self, x, y):
        """Divide x by y."""
        if y == 0:
            raise ValueError("Cannot divide by zero")
        return x / y

def main():
    """Main function."""
    ops = MathOperations()
    result = ops.multiply(4, 5)
    print(f"4 * 5 = {result}")
'''

SAMPLE_JAVASCRIPT_CODE = """
function greet(name) {
    return `Hello, ${name}!`;
}

class Person {
    constructor(name, age) {
        this.name = name;
        this.age = age;
    }

    introduce() {
        return `My name is ${this.name} and I'm ${this.age} years old.`;
    }
}

const main = () => {
    const person = new Person("Alice", 30);
    console.log(person.introduce());
};
"""


@pytest.fixture()
def temp_cache_dir():
    """Create a temporary cache directory."""
    cache_dir = Path(tempfile.mkdtemp()) / "cache"
    yield cache_dir
    if cache_dir.parent.exists():
        shutil.rmtree(cache_dir.parent)


@pytest.fixture()
def cache(temp_cache_dir):
    """Create a cache instance with temporary directory."""
    return ASTCache(cache_dir=temp_cache_dir)


@pytest.fixture()
def temp_python_file():
    """Create a temporary Python file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(SAMPLE_PYTHON_CODE)
        temp_path = Path(f.name)
    yield temp_path
    temp_path.unlink()


@pytest.fixture()
def temp_js_file():
    """Create a temporary JavaScript file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".js", delete=False) as f:
        f.write(SAMPLE_JAVASCRIPT_CODE)
        temp_path = Path(f.name)
    yield temp_path
    temp_path.unlink()


@pytest.fixture()
def sample_chunks():
    """Create sample code chunks for testing."""
    return [
        CodeChunk(
            language="python",
            file_path="/test/file1.py",
            node_type="function_definition",
            start_line=1,
            end_line=3,
            byte_start=0,
            byte_end=50,
            parent_context="",
            content="def test():\n    pass",
            chunk_id="chunk1",
        ),
        CodeChunk(
            language="python",
            file_path="/test/file1.py",
            node_type="class_definition",
            start_line=5,
            end_line=10,
            byte_start=52,
            byte_end=150,
            parent_context="",
            content="class TestClass:\n    pass",
            chunk_id="chunk2",
        ),
    ]


class TestCacheBasics:
    """Test basic cache operations."""

    def test_cache_initialization(self, temp_cache_dir):
        """Test cache initialization creates proper directory structure."""
        cache = ASTCache(cache_dir=temp_cache_dir)

        assert temp_cache_dir.exists()
        assert (temp_cache_dir / "ast_cache.db").exists()

        # Verify database schema
        with sqlite3.connect(cache.db_path) as conn:
            cursor = conn.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name='file_cache'",
            )
            schema = cursor.fetchone()[0]
            assert "file_path" in schema
            assert "file_hash" in schema
            assert "chunks_data" in schema

    def test_cache_and_retrieve_chunks(self, cache, temp_python_file):
        """Test basic cache and retrieve operations."""
        chunks = chunk_file(temp_python_file, "python")

        # Cache the chunks
        cache.cache_chunks(temp_python_file, "python", chunks)

        # Retrieve from cache
        cached_chunks = cache.get_cached_chunks(temp_python_file, "python")

        assert cached_chunks is not None
        assert len(cached_chunks) == len(chunks)
        assert all(
            c1.chunk_id == c2.chunk_id
            for c1, c2 in zip(chunks, cached_chunks, strict=False)
        )
        assert all(
            c1.content == c2.content
            for c1, c2 in zip(chunks, cached_chunks, strict=False)
        )

    def test_cache_miss_on_file_change(self, cache, temp_python_file):
        """Test cache miss when file is modified."""
        chunks = chunk_file(temp_python_file, "python")
        cache.cache_chunks(temp_python_file, "python", chunks)

        # Verify cache hit
        assert cache.get_cached_chunks(temp_python_file, "python") is not None

        # Modify file
        time.sleep(0.01)  # Ensure mtime changes
        with open(temp_python_file, "a") as f:
            f.write("\n# Modified")

        # Should get cache miss
        assert cache.get_cached_chunks(temp_python_file, "python") is None

    def test_cache_multiple_languages(self, cache, temp_python_file):
        """Test caching same file with different languages."""
        py_chunks = [
            CodeChunk(
                language="python",
                file_path=str(temp_python_file),
                node_type="function",
                start_line=1,
                end_line=3,
                byte_start=0,
                byte_end=50,
                parent_context="",
                content="def test(): pass",
                chunk_id="py1",
            ),
        ]

        # Pretend it's also valid JavaScript
        js_chunks = [
            CodeChunk(
                language="javascript",
                file_path=str(temp_python_file),
                node_type="function",
                start_line=1,
                end_line=3,
                byte_start=0,
                byte_end=50,
                parent_context="",
                content="function test() {}",
                chunk_id="js1",
            ),
        ]

        cache.cache_chunks(temp_python_file, "python", py_chunks)
        cache.cache_chunks(temp_python_file, "javascript", js_chunks)

        # Both should be cached independently
        cached_py = cache.get_cached_chunks(temp_python_file, "python")
        cached_js = cache.get_cached_chunks(temp_python_file, "javascript")

        assert len(cached_py) == 1
        assert cached_py[0].chunk_id == "py1"
        assert len(cached_js) == 1
        assert cached_js[0].chunk_id == "js1"


class TestCacheInvalidation:
    """Test cache invalidation strategies."""

    def test_invalidate_specific_file(self, cache, temp_python_file, temp_js_file):
        """Test invalidating cache for specific file."""
        py_chunks = chunk_file(temp_python_file, "python")
        js_chunks = chunk_file(temp_js_file, "javascript")

        cache.cache_chunks(temp_python_file, "python", py_chunks)
        cache.cache_chunks(temp_js_file, "javascript", js_chunks)

        # Invalidate only Python file
        cache.invalidate_cache(temp_python_file)

        assert cache.get_cached_chunks(temp_python_file, "python") is None
        assert cache.get_cached_chunks(temp_js_file, "javascript") is not None

    def test_invalidate_all_cache(self, cache, temp_python_file, temp_js_file):
        """Test invalidating entire cache."""
        cache.cache_chunks(
            temp_python_file,
            "python",
            chunk_file(temp_python_file, "python"),
        )
        cache.cache_chunks(
            temp_js_file,
            "javascript",
            chunk_file(temp_js_file, "javascript"),
        )

        # Invalidate all
        cache.invalidate_cache()

        assert cache.get_cached_chunks(temp_python_file, "python") is None
        assert cache.get_cached_chunks(temp_js_file, "javascript") is None

        # Stats should show empty cache
        stats = cache.get_cache_stats()
        assert stats["total_files"] == 0


class TestCacheConcurrency:
    """Test thread-safe cache operations."""

    def test_concurrent_cache_reads(self, cache, temp_python_file):
        """Test multiple threads reading from cache simultaneously."""
        chunks = chunk_file(temp_python_file, "python")
        cache.cache_chunks(temp_python_file, "python", chunks)

        results = []

        def read_cache():
            cached = cache.get_cached_chunks(temp_python_file, "python")
            results.append(len(cached) if cached else 0)

        # Launch multiple threads
        threads = []
        for _ in range(10):
            t = threading.Thread(target=read_cache)
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # All threads should get same result
        assert all(r == len(chunks) for r in results)

    def test_concurrent_cache_writes(self, cache, temp_cache_dir):
        """Test multiple threads writing to cache simultaneously."""

        def write_cache(file_num):
            file_path = temp_cache_dir / f"test_{file_num}.py"
            file_path.write_text(SAMPLE_PYTHON_CODE)

            chunks = chunk_file(file_path, "python")
            cache.cache_chunks(file_path, "python", chunks)

            # Verify write succeeded
            cached = cache.get_cached_chunks(file_path, "python")
            assert cached is not None
            assert len(cached) == len(chunks)

        # Launch multiple threads
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(write_cache, i) for i in range(10)]
            for future in futures:
                future.result()  # Wait and check for exceptions

        # Verify all files were cached
        stats = cache.get_cache_stats()
        assert stats["total_files"] == 10

    def test_concurrent_mixed_operations(self, cache, temp_python_file):
        """Test concurrent reads, writes, and invalidations."""
        initial_chunks = chunk_file(temp_python_file, "python")
        cache.cache_chunks(temp_python_file, "python", initial_chunks)

        operations_completed = {"reads": 0, "writes": 0, "invalidates": 0}
        lock = threading.Lock()

        def mixed_operations(op_type):
            if op_type == "read":
                cache.get_cached_chunks(temp_python_file, "python")
                with lock:
                    operations_completed["reads"] += 1
            elif op_type == "write":
                cache.cache_chunks(temp_python_file, "python", initial_chunks)
                with lock:
                    operations_completed["writes"] += 1
            else:  # invalidate
                cache.invalidate_cache(temp_python_file)
                with lock:
                    operations_completed["invalidates"] += 1

        # Mix of operations
        operations = ["read"] * 10 + ["write"] * 5 + ["invalidate"] * 2

        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(mixed_operations, op) for op in operations]
            for future in futures:
                future.result()

        assert operations_completed["reads"] == 10
        assert operations_completed["writes"] == 5
        assert operations_completed["invalidates"] == 2


class TestCacheCorruptionRecovery:
    """Test cache recovery from corruption scenarios."""

    def test_recover_from_corrupted_database(self, cache, temp_python_file):
        """Test recovery when database file is corrupted."""
        chunks = chunk_file(temp_python_file, "python")
        cache.cache_chunks(temp_python_file, "python", chunks)

        # Corrupt the database
        with open(cache.db_path, "wb") as f:
            f.write(b"corrupted data")

        # Should handle gracefully - reinitialize database
        new_cache = ASTCache(cache_dir=cache.db_path.parent)

        # Cache should be empty but functional
        assert new_cache.get_cached_chunks(temp_python_file, "python") is None

        # Should be able to cache again
        new_cache.cache_chunks(temp_python_file, "python", chunks)
        assert new_cache.get_cached_chunks(temp_python_file, "python") is not None

    def test_recover_from_corrupted_pickle_data(self, cache, temp_python_file):
        """Test recovery when pickled chunk data is corrupted."""
        chunk_file(temp_python_file, "python")
        metadata = get_file_metadata(temp_python_file)

        # Insert corrupted pickle data directly
        with cache._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO file_cache
                (file_path, file_hash, file_size, mtime, language, chunks_data)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (
                    str(temp_python_file),
                    metadata.hash,
                    metadata.size,
                    metadata.mtime,
                    "python",
                    b"corrupted pickle data",
                ),
            )

        # Should return None on corrupted data
        result = cache.get_cached_chunks(temp_python_file, "python")
        assert result is None

    def test_handle_missing_file(self, cache):
        """Test handling when cached file no longer exists."""
        non_existent = Path("/tmp/non_existent_file.py")

        # Should return None gracefully
        result = cache.get_cached_chunks(non_existent, "python")
        assert result is None


class TestCachePerformance:
    """Test cache performance characteristics."""

    def test_cache_size_limits(self, cache, temp_cache_dir):
        """Test behavior with large number of cached files."""
        # Create many files
        for i in range(100):
            file_path = temp_cache_dir / f"file_{i}.py"
            file_path.write_text(SAMPLE_PYTHON_CODE)
            chunks = chunk_file(file_path, "python")
            cache.cache_chunks(file_path, "python", chunks)

        stats = cache.get_cache_stats()
        assert stats["total_files"] == 100
        assert stats["cache_db_size"] > 0

    def test_large_file_caching(self, cache, temp_cache_dir):
        """Test caching very large files."""
        # Create a large file with many functions
        large_code = ""
        for i in range(1000):
            large_code += f"\ndef function_{i}():\n    return {i}\n\n"

        large_file = temp_cache_dir / "large_file.py"
        large_file.write_text(large_code)

        # Chunk and cache
        start_time = time.time()
        chunks = chunk_file(large_file, "python")
        cache.cache_chunks(large_file, "python", chunks)
        cache_time = time.time() - start_time

        # Retrieve from cache
        start_time = time.time()
        cached_chunks = cache.get_cached_chunks(large_file, "python")
        retrieve_time = time.time() - start_time

        assert len(cached_chunks) == 1000
        assert retrieve_time < cache_time  # Cache should be faster than parsing

    @pytest.mark.parametrize("num_workers", [1, 2, 4])
    def test_parallel_performance(self, cache, temp_cache_dir, num_workers):
        """Test parallel caching performance with different worker counts."""
        # Create test files
        files = []
        for i in range(20):
            file_path = temp_cache_dir / f"parallel_{i}.py"
            file_path.write_text(SAMPLE_PYTHON_CODE)
            files.append(file_path)

        def process_file(file_path):
            chunks = chunk_file(file_path, "python")
            cache.cache_chunks(file_path, "python", chunks)
            return len(chunks)

        start_time = time.time()
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            results = list(executor.map(process_file, files))
        elapsed = time.time() - start_time

        assert all(r > 0 for r in results)
        assert cache.get_cache_stats()["total_files"] == 20

        # Record time for performance comparison
        print(f"\nWorkers: {num_workers}, Time: {elapsed:.2f}s")


class TestCacheEviction:
    """Test cache eviction strategies."""

    def test_manual_eviction_by_age(self, cache, temp_cache_dir):
        """Test evicting old cache entries."""
        # Create files with different ages
        old_file = temp_cache_dir / "old.py"
        new_file = temp_cache_dir / "new.py"

        old_file.write_text(SAMPLE_PYTHON_CODE)
        new_file.write_text(SAMPLE_PYTHON_CODE)

        # Cache old file
        cache.cache_chunks(old_file, "python", chunk_file(old_file, "python"))

        # Simulate time passing by modifying database directly
        with cache._get_connection() as conn:
            conn.execute(
                """
                UPDATE file_cache
                SET created_at = datetime('now', '-7 days')
                WHERE file_path = ?
            """,
                (str(old_file),),
            )

        # Cache new file
        cache.cache_chunks(new_file, "python", chunk_file(new_file, "python"))

        # Implement manual age-based eviction
        with cache._get_connection() as conn:
            conn.execute(
                """
                DELETE FROM file_cache
                WHERE created_at < datetime('now', '-1 day')
            """,
            )

        # Old file should be evicted
        assert cache.get_cached_chunks(old_file, "python") is None
        assert cache.get_cached_chunks(new_file, "python") is not None


class TestMemoryVsDiskCache:
    """Compare memory-based vs disk-based caching strategies."""

    def test_memory_cache_simulation(self, temp_python_file):
        """Simulate in-memory cache for comparison."""
        memory_cache = {}

        # Cache in memory
        chunks = chunk_file(temp_python_file, "python")
        key = (str(temp_python_file), "python")
        metadata = get_file_metadata(temp_python_file)
        memory_cache[key] = (metadata, chunks)

        # Retrieve from memory
        cached_meta, cached_chunks = memory_cache.get(key, (None, None))
        current_meta = get_file_metadata(temp_python_file)

        if cached_meta and cached_meta.hash == current_meta.hash:
            assert len(cached_chunks) == len(chunks)
        else:
            raise AssertionError("Cache should hit")

    def test_hybrid_cache_pattern(self, cache, temp_python_file):
        """Test hybrid caching with memory layer over disk cache."""
        # Simple LRU memory cache
        from collections import OrderedDict

        class HybridCache:
            def __init__(self, disk_cache, max_memory_items=10):
                self.disk_cache = disk_cache
                self.memory_cache = OrderedDict()
                self.max_items = max_memory_items

            def get(self, path, language):
                key = (str(path), language)

                # Check memory first
                if key in self.memory_cache:
                    self.memory_cache.move_to_end(key)
                    return self.memory_cache[key]

                # Fall back to disk
                chunks = self.disk_cache.get_cached_chunks(path, language)
                if chunks:
                    self._add_to_memory(key, chunks)
                return chunks

            def _add_to_memory(self, key, chunks):
                self.memory_cache[key] = chunks
                if len(self.memory_cache) > self.max_items:
                    self.memory_cache.popitem(last=False)

        hybrid = HybridCache(cache, max_memory_items=2)

        # First access - from disk
        chunks = chunk_file(temp_python_file, "python")
        cache.cache_chunks(temp_python_file, "python", chunks)

        result1 = hybrid.get(temp_python_file, "python")
        assert result1 is not None

        # Second access - should be from memory
        result2 = hybrid.get(temp_python_file, "python")
        assert result2 is result1  # Same object reference


class TestCacheIntegration:
    """Integration tests with real-world scenarios."""

    def test_cache_with_git_operations(self, cache, temp_cache_dir):
        """Test cache behavior with git-like file modifications."""
        repo_dir = temp_cache_dir / "repo"
        repo_dir.mkdir()

        # Create initial file
        file_path = repo_dir / "module.py"
        file_path.write_text(SAMPLE_PYTHON_CODE)

        # Initial cache
        chunks_v1 = chunk_file(file_path, "python")
        cache.cache_chunks(file_path, "python", chunks_v1)

        # Simulate git checkout (file content changes)
        time.sleep(0.01)
        modified_code = SAMPLE_PYTHON_CODE.replace("calculate_sum", "compute_sum")
        file_path.write_text(modified_code)

        # Cache should miss due to content change
        assert cache.get_cached_chunks(file_path, "python") is None

        # Re-cache new version
        chunks_v2 = chunk_file(file_path, "python")
        cache.cache_chunks(file_path, "python", chunks_v2)

        # Should hit on unchanged file
        assert cache.get_cached_chunks(file_path, "python") is not None

    def test_cache_with_symbolic_links(self, cache, temp_cache_dir):
        """Test cache behavior with symbolic links."""
        # Create actual file
        actual_file = temp_cache_dir / "actual.py"
        actual_file.write_text(SAMPLE_PYTHON_CODE)

        # Create symlink
        symlink = temp_cache_dir / "link.py"
        symlink.symlink_to(actual_file)

        # Cache via symlink
        chunks = chunk_file(symlink, "python")
        cache.cache_chunks(symlink, "python", chunks)

        # Should be able to retrieve via symlink
        cached = cache.get_cached_chunks(symlink, "python")
        assert cached is not None
        assert len(cached) == len(chunks)

        # Modifying actual file should invalidate cache
        time.sleep(0.01)
        with open(actual_file, "a") as f:
            f.write("\n# Modified")

        assert cache.get_cached_chunks(symlink, "python") is None


class TestCacheErrorHandling:
    """Test error handling in cache operations."""

    def test_handle_permission_errors(self, temp_cache_dir):
        """Test handling of permission errors."""
        # Create cache with restricted permissions
        restricted_dir = temp_cache_dir / "restricted"
        restricted_dir.mkdir(parents=True, exist_ok=True)

        cache = ASTCache(cache_dir=restricted_dir)

        # Make directory read-only
        restricted_dir.chmod(0o444)

        try:
            # Should handle permission errors gracefully
            test_file = Path("/tmp/test.py")
            test_file.write_text(SAMPLE_PYTHON_CODE)

            chunks = chunk_file(test_file, "python")

            # This might fail on some systems, so we just ensure no crash
            try:
                cache.cache_chunks(test_file, "python", chunks)
            except (OSError, sqlite3.OperationalError):
                pass  # Expected on some systems

        finally:
            # Restore permissions for cleanup
            restricted_dir.chmod(0o755)

    def test_handle_disk_full(self, cache, temp_python_file, monkeypatch):
        """Test handling disk full scenarios."""
        chunks = chunk_file(temp_python_file, "python")

        # Mock disk full error by creating a wrapper connection
        class MockConnection:
            def __init__(self, real_conn):
                self.real_conn = real_conn

            def execute(self, sql, *args):
                if "INSERT" in sql:
                    raise sqlite3.OperationalError("disk full")
                return self.real_conn.execute(sql, *args)

            def commit(self):
                return self.real_conn.commit()

            def close(self):
                return self.real_conn.close()

        def mock_get_connection():
            real_conn = sqlite3.connect(cache.db_path)
            mock_conn = MockConnection(real_conn)

            from contextlib import contextmanager

            @contextmanager
            def connection_context():
                try:
                    yield mock_conn
                    mock_conn.commit()
                finally:
                    mock_conn.close()

            return connection_context()

        monkeypatch.setattr(cache, "_get_connection", mock_get_connection)

        # Should handle disk full gracefully
        with pytest.raises(sqlite3.OperationalError):
            cache.cache_chunks(temp_python_file, "python", chunks)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

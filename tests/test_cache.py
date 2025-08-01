"""Comprehensive tests for the ASTCache caching system."""
import shutil
import sqlite3
import tempfile
import threading
import time
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path

import pytest
from chunker.cache import ASTCache

from chunker import chunk_file
from chunker.streaming import get_file_metadata
from chunker.types import CodeChunk

SAMPLE_PYTHON_CODE = """
def calculate_sum(a, b):
    ""\"Calculate the sum of two numbers.""\"
    return a + b

class MathOperations:
    ""\"A class for basic math operations.""\"

    def multiply(self, x, y):
        ""\"Multiply two numbers.""\"
        return x * y

    def divide(self, x, y):
        ""\"Divide x by y.""\"
        if y == 0:
            raise ValueError("Cannot divide by zero")
        return x / y

def main():
    ""\"Main function.""\"
    ops = MathOperations()
    result = ops.multiply(4, 5)
    print(f"4 * 5 = {result}")
"""
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


@pytest.fixture
def temp_cache_dir():
    """Create a temporary cache directory."""
    cache_dir = Path(tempfile.mkdtemp()) / "cache"
    yield cache_dir
    if cache_dir.parent.exists():
        shutil.rmtree(cache_dir.parent)


@pytest.fixture
def cache(temp_cache_dir):
    """Create a cache instance with temporary directory."""
    return ASTCache(cache_dir=temp_cache_dir)


@pytest.fixture
def temp_python_file():
    """Create a temporary Python file."""
    with tempfile.NamedTemporaryFile(encoding="utf-8", mode="w", suffix=".py", delete=False) as f:
        f.write(SAMPLE_PYTHON_CODE)
        temp_path = Path(f.name)
    yield temp_path
    temp_path.unlink()


@pytest.fixture
def temp_js_file():
    """Create a temporary JavaScript file."""
    with tempfile.NamedTemporaryFile(encoding="utf-8", mode="w", suffix=".js", delete=False) as f:
        f.write(SAMPLE_JAVASCRIPT_CODE)
        temp_path = Path(f.name)
    yield temp_path
    temp_path.unlink()


@pytest.fixture
def sample_chunks():
    """Create sample code chunks for testing."""
    return [CodeChunk(language="python", file_path="/test/file1.py",
        node_type="function_definition", start_line=1, end_line=3,
        byte_start=0, byte_end=50, parent_context="", content="""def test():
    pass""", chunk_id="chunk1"), CodeChunk(language="python", file_path="/test/file1.py", node_type="class_definition",
        start_line=5, end_line=10, byte_start=52, byte_end=150,
        parent_context="", content="""class TestClass:
    pass""",
        chunk_id="chunk2")]


class TestCacheBasics:
    """Test basic cache operations."""

    @classmethod
    def test_cache_initialization(cls, temp_cache_dir):
        """Test cache initialization creates proper directory structure."""
        cache = ASTCache(cache_dir=temp_cache_dir)
        assert temp_cache_dir.exists()
        assert (temp_cache_dir / "ast_cache.db").exists()
        with sqlite3.connect(cache.db_path) as conn:
            cursor = conn.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name='file_cache'",
                )
            schema = cursor.fetchone()[0]
            assert "file_path" in schema
            assert "file_hash" in schema
            assert "chunks_data" in schema

    @staticmethod
    def test_cache_and_retrieve_chunks(cache, temp_python_file):
        """Test basic cache and retrieve operations."""
        chunks = chunk_file(temp_python_file, "python")
        cache.cache_chunks(temp_python_file, "python", chunks)
        cached_chunks = cache.get_cached_chunks(temp_python_file, "python")
        assert cached_chunks is not None
        assert len(cached_chunks) == len(chunks)
        assert all(c1.chunk_id == c2.chunk_id for c1, c2 in zip(chunks,
            cached_chunks, strict=False))
        assert all(c1.content == c2.content for c1, c2 in zip(chunks,
            cached_chunks, strict=False))

    @classmethod
    def test_cache_miss_on_file_change(cls, cache, temp_python_file):
        """Test cache miss when file is modified."""
        chunks = chunk_file(temp_python_file, "python")
        cache.cache_chunks(temp_python_file, "python", chunks)
        assert cache.get_cached_chunks(temp_python_file, "python") is not None
        time.sleep(0.01)
        with Path(temp_python_file).open("a", encoding="utf-8") as f:
            f.write("\n# Modified")
        assert cache.get_cached_chunks(temp_python_file, "python") is None

    @classmethod
    def test_cache_multiple_languages(cls, cache, temp_python_file):
        """Test caching same file with different languages."""
        py_chunks = [CodeChunk(language="python", file_path=str(
            temp_python_file), node_type="function", start_line=1, end_line=3, byte_start=0, byte_end=50, parent_context="", content="def test(): pass", chunk_id="py1")]
        js_chunks = [CodeChunk(language="javascript", file_path=str(
            temp_python_file), node_type="function", start_line=1, end_line=3, byte_start=0, byte_end=50, parent_context="", content="function test() {}", chunk_id="js1")]
        cache.cache_chunks(temp_python_file, "python", py_chunks)
        cache.cache_chunks(temp_python_file, "javascript", js_chunks)
        cached_py = cache.get_cached_chunks(temp_python_file, "python")
        cached_js = cache.get_cached_chunks(temp_python_file, "javascript")
        assert len(cached_py) == 1
        assert cached_py[0].chunk_id == "py1"
        assert len(cached_js) == 1
        assert cached_js[0].chunk_id == "js1"


class TestCacheInvalidation:
    """Test cache invalidation strategies."""

    @staticmethod
    def test_invalidate_specific_file(cache, temp_python_file, temp_js_file):
        """Test invalidating cache for specific file."""
        py_chunks = chunk_file(temp_python_file, "python")
        js_chunks = chunk_file(temp_js_file, "javascript")
        cache.cache_chunks(temp_python_file, "python", py_chunks)
        cache.cache_chunks(temp_js_file, "javascript", js_chunks)
        cache.invalidate_cache(temp_python_file)
        assert cache.get_cached_chunks(temp_python_file, "python") is None
        assert cache.get_cached_chunks(temp_js_file, "javascript") is not None

    @staticmethod
    def test_invalidate_all_cache(cache, temp_python_file, temp_js_file):
        """Test invalidating entire cache."""
        cache.cache_chunks(temp_python_file, "python", chunk_file(
            temp_python_file, "python"))
        cache.cache_chunks(temp_js_file, "javascript", chunk_file(
            temp_js_file, "javascript"))
        cache.invalidate_cache()
        assert cache.get_cached_chunks(temp_python_file, "python") is None
        assert cache.get_cached_chunks(temp_js_file, "javascript") is None
        stats = cache.get_cache_stats()
        assert stats["total_files"] == 0


class TestCacheConcurrency:
    """Test thread-safe cache operations."""

    @staticmethod
    def test_concurrent_cache_reads(cache, temp_python_file):
        """Test multiple threads reading from cache simultaneously."""
        chunks = chunk_file(temp_python_file, "python")
        cache.cache_chunks(temp_python_file, "python", chunks)
        results = []

        def read_cache():
            cached = cache.get_cached_chunks(temp_python_file, "python")
            results.append(len(cached) if cached else 0)
        threads = []
        for _ in range(10):
            t = threading.Thread(target=read_cache)
            threads.append(t)
            t.start()
        for t in threads:
            t.join()
        assert all(r == len(chunks) for r in results)

    @classmethod
    def test_concurrent_cache_writes(cls, cache, temp_cache_dir):
        """Test multiple threads writing to cache simultaneously."""

        def write_cache(file_num):
            file_path = temp_cache_dir / f"test_{file_num}.py"
            file_path.write_text(SAMPLE_PYTHON_CODE)
            chunks = chunk_file(file_path, "python")
            cache.cache_chunks(file_path, "python", chunks)
            cached = cache.get_cached_chunks(file_path, "python")
            assert cached is not None
            assert len(cached) == len(chunks)
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(write_cache, i) for i in range(10)]
            for future in futures:
                future.result()
        stats = cache.get_cache_stats()
        assert stats["total_files"] == 10

    @classmethod
    def test_concurrent_mixed_operations(cls, cache, temp_python_file):
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
            else:
                cache.invalidate_cache(temp_python_file)
                with lock:
                    operations_completed["invalidates"] += 1
        operations = ["read"] * 10 + ["write"] * 5 + ["invalidate"] * 2
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(mixed_operations, op) for op in
                operations]
            for future in futures:
                future.result()
        assert operations_completed["reads"] == 10
        assert operations_completed["writes"] == 5
        assert operations_completed["invalidates"] == 2


class TestCacheCorruptionRecovery:
    """Test cache recovery from corruption scenarios."""

    @classmethod
    def test_recover_from_corrupted_database(cls, cache, temp_python_file):
        """Test recovery when database file is corrupted."""
        chunks = chunk_file(temp_python_file, "python")
        cache.cache_chunks(temp_python_file, "python", chunks)
        with Path(cache.db_path).open("wb") as f:
            f.write(b"corrupted data")
        new_cache = ASTCache(cache_dir=cache.db_path.parent)
        assert new_cache.get_cached_chunks(temp_python_file, "python") is None
        new_cache.cache_chunks(temp_python_file, "python", chunks)
        assert new_cache.get_cached_chunks(temp_python_file, "python",
            ) is not None

    @staticmethod
    def test_recover_from_corrupted_pickle_data(cache, temp_python_file):
        """Test recovery when pickled chunk data is corrupted."""
        chunk_file(temp_python_file, "python")
        metadata = get_file_metadata(temp_python_file)
        with cache._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO file_cache
                (file_path, file_hash, file_size, mtime, language, chunks_data)
                VALUES (?, ?, ?, ?, ?, ?)
            """
                , (str(temp_python_file), metadata.hash, metadata.size,
                metadata.mtime, "python", b"corrupted pickle data"))
        result = cache.get_cached_chunks(temp_python_file, "python")
        assert result is None

    @classmethod
    def test_handle_missing_file(cls, cache):
        """Test handling when cached file no longer exists."""
        non_existent = Path("/tmp/non_existent_file.py")
        result = cache.get_cached_chunks(non_existent, "python")
        assert result is None


class TestCachePerformance:
    """Test cache performance characteristics."""

    @staticmethod
    def test_cache_size_limits(cache, temp_cache_dir):
        """Test behavior with large number of cached files."""
        for i in range(100):
            file_path = temp_cache_dir / f"file_{i}.py"
            file_path.write_text(SAMPLE_PYTHON_CODE)
            chunks = chunk_file(file_path, "python")
            cache.cache_chunks(file_path, "python", chunks)
        stats = cache.get_cache_stats()
        assert stats["total_files"] == 100
        assert stats["cache_db_size"] > 0

    @staticmethod
    def test_large_file_caching(cache, temp_cache_dir):
        """Test caching very large files."""
        large_code = ""
        for i in range(1000):
            large_code += f"\ndef function_{i}():\n    return {i}\n\n"
        large_file = temp_cache_dir / "large_file.py"
        large_file.write_text(large_code)
        start_time = time.time()
        chunks = chunk_file(large_file, "python")
        cache.cache_chunks(large_file, "python", chunks)
        cache_time = time.time() - start_time
        start_time = time.time()
        cached_chunks = cache.get_cached_chunks(large_file, "python")
        retrieve_time = time.time() - start_time
        assert len(cached_chunks) == 1000
        assert retrieve_time < cache_time

    @classmethod
    @pytest.mark.parametrize("num_workers", [1, 2, 4])
    def test_parallel_performance(cls, cache, temp_cache_dir, num_workers):
        """Test parallel caching performance with different worker counts."""
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
        print(f"\nWorkers: {num_workers}, Time: {elapsed:.2f}s")


class TestCacheEviction:
    """Test cache eviction strategies."""

    @staticmethod
    def test_manual_eviction_by_age(cache, temp_cache_dir):
        """Test evicting old cache entries."""
        old_file = temp_cache_dir / "old.py"
        new_file = temp_cache_dir / "new.py"
        old_file.write_text(SAMPLE_PYTHON_CODE)
        new_file.write_text(SAMPLE_PYTHON_CODE)
        cache.cache_chunks(old_file, "python", chunk_file(old_file, "python"))
        with cache._get_connection() as conn:
            conn.execute(
                """
                UPDATE file_cache
                SET created_at = datetime('now', '-7 days')
                WHERE file_path = ?
            """
                , (str(old_file),))
        cache.cache_chunks(new_file, "python", chunk_file(new_file, "python"))
        with cache._get_connection() as conn:
            conn.execute(
                """
                DELETE FROM file_cache
                WHERE created_at < datetime('now', '-1 day')
            """,
                )
        assert cache.get_cached_chunks(old_file, "python") is None
        assert cache.get_cached_chunks(new_file, "python") is not None


class TestMemoryVsDiskCache:
    """Compare memory-based vs disk-based caching strategies."""

    @classmethod
    def test_memory_cache_simulation(cls, temp_python_file):
        """Simulate in-memory cache for comparison."""
        memory_cache = {}
        chunks = chunk_file(temp_python_file, "python")
        key = str(temp_python_file), "python"
        metadata = get_file_metadata(temp_python_file)
        memory_cache[key] = metadata, chunks
        cached_meta, cached_chunks = memory_cache.get(key, (None, None))
        current_meta = get_file_metadata(temp_python_file)
        if cached_meta and cached_meta.hash == current_meta.hash:
            assert len(cached_chunks) == len(chunks)
        else:
            raise AssertionError("Cache should hit")

    @staticmethod
    def test_hybrid_cache_pattern(cache, temp_python_file):
        """Test hybrid caching with memory layer over disk cache."""

        class HybridCache:

            def __init__(self, disk_cache, max_memory_items=10):
                self.disk_cache = disk_cache
                self.memory_cache = OrderedDict()
                self.max_items = max_memory_items

            def get(self, path, language):
                key = str(path), language
                if key in self.memory_cache:
                    self.memory_cache.move_to_end(key)
                    return self.memory_cache[key]
                chunks = self.disk_cache.get_cached_chunks(path, language)
                if chunks:
                    self._add_to_memory(key, chunks)
                return chunks

            def _add_to_memory(self, key, chunks):
                self.memory_cache[key] = chunks
                if len(self.memory_cache) > self.max_items:
                    self.memory_cache.popitem(last=False)
        hybrid = HybridCache(cache, max_memory_items=2)
        chunks = chunk_file(temp_python_file, "python")
        cache.cache_chunks(temp_python_file, "python", chunks)
        result1 = hybrid.get(temp_python_file, "python")
        assert result1 is not None
        result2 = hybrid.get(temp_python_file, "python")
        assert result2 is result1


class TestCacheIntegration:
    """Integration tests with real-world scenarios."""

    @staticmethod
    def test_cache_with_git_operations(cache, temp_cache_dir):
        """Test cache behavior with git-like file modifications."""
        repo_dir = temp_cache_dir / "repo"
        repo_dir.mkdir()
        file_path = repo_dir / "module.py"
        file_path.write_text(SAMPLE_PYTHON_CODE)
        chunks_v1 = chunk_file(file_path, "python")
        cache.cache_chunks(file_path, "python", chunks_v1)
        time.sleep(0.01)
        modified_code = SAMPLE_PYTHON_CODE.replace("calculate_sum",
            "compute_sum")
        file_path.write_text(modified_code)
        assert cache.get_cached_chunks(file_path, "python") is None
        chunks_v2 = chunk_file(file_path, "python")
        cache.cache_chunks(file_path, "python", chunks_v2)
        assert cache.get_cached_chunks(file_path, "python") is not None

    @classmethod
    def test_cache_with_symbolic_links(cls, cache, temp_cache_dir):
        """Test cache behavior with symbolic links."""
        actual_file = temp_cache_dir / "actual.py"
        actual_file.write_text(SAMPLE_PYTHON_CODE)
        symlink = temp_cache_dir / "link.py"
        symlink.symlink_to(actual_file)
        chunks = chunk_file(symlink, "python")
        cache.cache_chunks(symlink, "python", chunks)
        cached = cache.get_cached_chunks(symlink, "python")
        assert cached is not None
        assert len(cached) == len(chunks)
        time.sleep(0.01)
        with Path(actual_file).open("a", encoding="utf-8") as f:
            f.write("\n# Modified")
        assert cache.get_cached_chunks(symlink, "python") is None


class TestCacheErrorHandling:
    """Test error handling in cache operations."""

    @classmethod
    def test_handle_permission_errors(cls, temp_cache_dir):
        """Test handling of permission errors."""
        restricted_dir = temp_cache_dir / "restricted"
        restricted_dir.mkdir(parents=True, exist_ok=True)
        cache = ASTCache(cache_dir=restricted_dir)
        restricted_dir.chmod(292)
        try:
            test_file = Path("/tmp/test.py")
            test_file.write_text(SAMPLE_PYTHON_CODE, encoding="utf-8")
            chunks = chunk_file(test_file, "python")
            try:
                cache.cache_chunks(test_file, "python", chunks)
            except (OSError, sqlite3.OperationalError):
                pass
        finally:
            restricted_dir.chmod(493)

    @staticmethod
    def test_handle_disk_full(cache, temp_python_file, monkeypatch):
        """Test handling disk full scenarios."""
        chunks = chunk_file(temp_python_file, "python")

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

            @contextmanager
            def connection_context():
                try:
                    yield mock_conn
                    mock_conn.commit()
                finally:
                    mock_conn.close()
            return connection_context()
        monkeypatch.setattr(cache, "_get_connection", mock_get_connection)
        with pytest.raises(sqlite3.OperationalError):
            cache.cache_chunks(temp_python_file, "python", chunks)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

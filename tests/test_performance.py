import shutil
import tempfile
from pathlib import Path

import pytest

from chunker import chunk_file, chunk_file_streaming, chunk_files_parallel
from chunker.cache import ASTCache

# Sample Python code for testing
SAMPLE_PYTHON_CODE = '''
def hello_world():
    """A simple hello world function."""
    print("Hello, World!")

class Calculator:
    """A simple calculator class."""

    def add(self, a, b):
        """Add two numbers."""
        return a + b

    def subtract(self, a, b):
        """Subtract b from a."""
        return a - b

def main():
    calc = Calculator()
    result = calc.add(5, 3)
    print(f"5 + 3 = {result}")
    hello_world()

if __name__ == "__main__":
    main()
'''


@pytest.fixture
def temp_python_file():
    """Create a temporary Python file for testing."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(SAMPLE_PYTHON_CODE)
        temp_path = Path(f.name)
    yield temp_path
    temp_path.unlink()


@pytest.fixture
def temp_directory_with_files():
    """Create a temporary directory with multiple Python files."""
    temp_dir = Path(tempfile.mkdtemp())

    # Create multiple test files
    for i in range(5):
        file_path = temp_dir / f"test_file_{i}.py"
        file_path.write_text(SAMPLE_PYTHON_CODE)

    yield temp_dir
    shutil.rmtree(temp_dir)


def test_basic_chunking(temp_python_file):
    """Test basic file chunking."""
    chunks = chunk_file(temp_python_file, "python")

    assert len(chunks) == 5  # hello_world, Calculator, add, subtract, main
    assert all(c.language == "python" for c in chunks)
    assert any(c.node_type == "function_definition" for c in chunks)
    assert any(c.node_type == "class_definition" for c in chunks)


def test_streaming_chunking(temp_python_file):
    """Test streaming file chunking."""
    chunks = list(chunk_file_streaming(temp_python_file, "python"))

    assert len(chunks) == 5
    assert all(c.language == "python" for c in chunks)

    # Compare with basic chunking
    basic_chunks = chunk_file(temp_python_file, "python")
    assert len(chunks) == len(basic_chunks)


def test_cached_chunking(temp_python_file):
    """Test chunking with caching."""
    cache = ASTCache()

    # Clear any existing cache
    cache.invalidate_cache(temp_python_file)

    # First run - chunk normally and cache manually
    chunks1 = chunk_file(temp_python_file, "python")
    assert len(chunks1) == 5

    # Manually cache the chunks
    cache.cache_chunks(temp_python_file, "python", chunks1)

    # Retrieve from cache
    cached_chunks = cache.get_cached_chunks(temp_python_file, "python")
    assert cached_chunks is not None
    assert len(cached_chunks) == 5

    # Verify cached chunks match original
    assert [c.chunk_id for c in chunks1] == [c.chunk_id for c in cached_chunks]


def test_parallel_chunking(temp_directory_with_files):
    """Test parallel file processing."""
    files = list(temp_directory_with_files.glob("*.py"))

    results = chunk_files_parallel(files, "python", num_workers=2)

    assert len(results) == 5  # 5 files
    for chunks in results.values():
        assert len(chunks) == 5  # Each file has 5 chunks


def test_cache_invalidation(temp_python_file):
    """Test cache invalidation."""
    cache = ASTCache()

    # Chunk the file and cache manually
    chunks = chunk_file(temp_python_file, "python")
    cache.cache_chunks(temp_python_file, "python", chunks)
    assert cache.get_cached_chunks(temp_python_file, "python") is not None

    # Invalidate cache
    cache.invalidate_cache(temp_python_file)
    assert cache.get_cached_chunks(temp_python_file, "python") is None


def test_cache_stats():
    """Test cache statistics."""
    cache = ASTCache()
    stats = cache.get_cache_stats()

    assert "total_files" in stats
    assert "total_size_bytes" in stats
    assert "cache_db_size" in stats
    assert isinstance(stats["total_files"], int)
    assert isinstance(stats["total_size_bytes"], int)

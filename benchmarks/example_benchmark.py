#!/usr/bin/env python3
"""
Example benchmark demonstrating all performance features.
"""
import shutil
import tempfile
import time
from pathlib import Path

from chunker import (
    ASTCache,
    chunk_directory_parallel,
    chunk_file,
    chunk_file_streaming,
    chunk_files_parallel,
)


def create_test_files(num_files: int = 10) -> Path:
    """Create a temporary directory with test Python files."""
    temp_dir = Path(tempfile.mkdtemp())

    # Sample code with multiple functions and classes
    sample_code = '''
def fibonacci(n):
    """Calculate fibonacci number."""
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)

class DataProcessor:
    """Process data with various methods."""

    def __init__(self, data):
        self.data = data

    def clean_data(self):
        """Clean the data."""
        return [x.strip() for x in self.data if x]

    def transform_data(self):
        """Transform the data."""
        return [x.upper() for x in self.clean_data()]

    def analyze_data(self):
        """Analyze the data."""
        cleaned = self.clean_data()
        return {
            "count": len(cleaned),
            "unique": len(set(cleaned)),
            "longest": max(len(x) for x in cleaned) if cleaned else 0
        }

def process_file(filename):
    """Process a file_path."""
    with open(filename, 'r') as f:
        data = f.readlines()
    processor = DataProcessor(data)
    return processor.analyze_data()

class Calculator:
    """Simple calculator class."""

    @staticmethod
    def add(a, b):
        return a + b

    @staticmethod
    def multiply(a, b):
        return a * b

    def power(self, base, exp):
        """Calculate power."""
        result = 1
        for _ in range(exp):
            result *= base
        return result
'''

    # Create test files
    for i in range(num_files):
        file_path = temp_dir / f"test_module_{i}.py"
        file_path.write_text(sample_code)

    return temp_dir


def demo_basic_chunking():
    """Demonstrate basic chunking."""
    print("\n1. Basic Chunking Demo")
    print("-" * 40)

    temp_dir = create_test_files(1)
    test_file = next(iter(temp_dir.glob("*.py")))

    start = time.time()
    chunks = chunk_file(test_file, "python")
    duration = time.time() - start

    print(f"File: {test_file.name}")
    print(f"Chunks found: {len(chunks)}")
    print(f"Time taken: {duration:.3f}s")

    for chunk in chunks[:3]:  # Show first 3 chunks
        print(f"  - {chunk.node_type}: lines {chunk.start_line}-{chunk.end_line}")

    shutil.rmtree(temp_dir)


def demo_streaming_chunking():
    """Demonstrate streaming chunking."""
    print("\n2. Streaming Chunking Demo")
    print("-" * 40)

    temp_dir = create_test_files(1)
    test_file = next(iter(temp_dir.glob("*.py")))

    start = time.time()
    chunks = list(chunk_file_streaming(test_file, "python"))
    duration = time.time() - start

    print(f"File: {test_file.name}")
    print(f"Chunks streamed: {len(chunks)}")
    print(f"Time taken: {duration:.3f}s")
    print("(Memory efficient for large files)")

    shutil.rmtree(temp_dir)


def demo_cached_chunking():
    """Demonstrate cached chunking."""
    print("\n3. Cached Chunking Demo")
    print("-" * 40)

    temp_dir = create_test_files(1)
    test_file = next(iter(temp_dir.glob("*.py")))

    # Clear cache
    cache = ASTCache()
    cache.invalidate_cache(test_file)

    # First run (cold cache)
    start = time.time()
    chunks1 = chunk_file(test_file, "python", use_cache=True)
    cold_duration = time.time() - start

    # Second run (warm cache)
    start = time.time()
    chunk_file(test_file, "python", use_cache=True)
    warm_duration = time.time() - start

    print(f"File: {test_file.name}")
    print(f"Chunks: {len(chunks1)}")
    print(f"Cold cache: {cold_duration:.3f}s")
    print(f"Warm cache: {warm_duration:.3f}s")
    print(f"Speedup: {cold_duration/warm_duration:.2f}x")

    # Show cache stats
    stats = cache.get_cache_stats()
    print(f"Cache stats: {stats['total_files']} files cached")

    shutil.rmtree(temp_dir)


def demo_parallel_processing():
    """Demonstrate parallel processing."""
    print("\n4. Parallel Processing Demo")
    print("-" * 40)

    temp_dir = create_test_files(20)
    files = list(temp_dir.glob("*.py"))

    # Sequential processing
    start = time.time()
    sequential_results = {}
    for file_path in files:
        sequential_results[file_path] = chunk_file(file_path, "python")
    seq_duration = time.time() - start

    # Parallel processing
    start = time.time()
    parallel_results = chunk_files_parallel(files, "python", num_workers=4)
    par_duration = time.time() - start

    print(f"Files processed: {len(files)}")
    print(f"Sequential time: {seq_duration:.3f}s")
    print(f"Parallel time (4 workers): {par_duration:.3f}s")
    print(f"Speedup: {seq_duration/par_duration:.2f}x")

    total_chunks = sum(len(chunks) for chunks in parallel_results.values())
    print(f"Total chunks extracted: {total_chunks}")

    shutil.rmtree(temp_dir)


def demo_directory_processing():
    """Demonstrate directory-level parallel processing."""
    print("\n5. Directory Processing Demo")
    print("-" * 40)

    temp_dir = create_test_files(10)

    # Create subdirectories
    subdir = temp_dir / "submodule"
    subdir.mkdir()
    for i in range(5):
        (subdir / f"sub_module_{i}.py").write_text("def sub_func(): pass")

    start = time.time()
    results = chunk_directory_parallel(
        temp_dir,
        "python",
        num_workers=4,
        use_cache=True,
        use_streaming=True,
    )
    duration = time.time() - start

    print(f"Directory: {temp_dir.name}")
    print(f"Files found: {len(results)}")
    print(f"Time taken: {duration:.3f}s")
    print("Features used: parallel + streaming + caching")

    total_chunks = sum(len(chunks) for chunks in results.values())
    print(f"Total chunks: {total_chunks}")

    shutil.rmtree(temp_dir)


def main():
    """Run all demos."""
    print("=" * 60)
    print("Tree-sitter Chunker Performance Features Demo")
    print("=" * 60)

    demo_basic_chunking()
    demo_streaming_chunking()
    demo_cached_chunking()
    demo_parallel_processing()
    demo_directory_processing()

    print("\n" + "=" * 60)
    print("Demo completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()

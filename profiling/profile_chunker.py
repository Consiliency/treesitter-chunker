"""Profiling tools for the Tree-sitter chunker."""

import cProfile
import io
import pstats
import shutil
import tempfile
import time
from collections.abc import Callable
from pathlib import Path

from chunker.chunker import chunk_file
from chunker.performance.enhanced_chunker import EnhancedChunker
from chunker.performance.optimization.batch import BatchProcessor


def profile_function(func: Callable, *args, **kwargs) -> tuple:
    """Profile a function and return results.

    Args:
        func: Function to profile
        *args: Positional arguments for func
        **kwargs: Keyword arguments for func

    Returns:
        Tuple of (result, profile_stats)
    """
    profiler = cProfile.Profile()

    profiler.enable()
    result = func(*args, **kwargs)
    profiler.disable()

    # Get statistics
    s = io.StringIO()
    ps = pstats.Stats(profiler, stream=s).sort_stats("cumulative")
    ps.print_stats()

    return result, s.getvalue()


def create_test_file(size: str = "medium") -> Path:
    """Create a test file for profiling.

    Args:
        size: 'small', 'medium', or 'large'

    Returns:
        Path to test file
    """
    temp_file = tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False)

    if size == "small":
        content = """
def test_function():
    return 42

class TestClass:
    def method(self):
        return "test"
"""
    elif size == "medium":
        functions = []
        for i in range(50):
            functions.append(
                f'''
def function_{i}(x, y):
    """Function {i}."""
    result = x + y
    for j in range(10):
        result += j
    return result
''',
            )
        content = "\n".join(functions)
    else:  # large
        functions = []
        for i in range(200):
            functions.append(
                f'''
def complex_function_{i}(data, options=None):
    """Complex function {i} with multiple operations."""
    if options is None:
        options = {{}}
    
    result = 0
    for item in data:
        if isinstance(item, int):
            result += item
        elif isinstance(item, list):
            result += sum(item)
    
    # Some nested logic
    if result > 100:
        for i in range(result):
            if i % 2 == 0:
                result -= 1
    
    return result
''',
            )
        content = "\n".join(functions)

    temp_file.write(content)
    temp_file.close()

    return Path(temp_file.name)


def profile_basic_chunking():
    """Profile basic chunking operation."""
    print("\nProfiling basic chunking")
    print("=" * 70)

    test_file = create_test_file("large")

    try:
        # Profile standard chunker
        print("\n1. Standard chunker:")
        _, stats = profile_function(chunk_file, test_file, "python")

        # Show top functions
        print("\nTop 20 time-consuming functions:")
        lines = stats.split("\n")
        for i, line in enumerate(lines):
            if i < 25 and line.strip():  # Header + top 20
                print(line)

        # Profile enhanced chunker
        print("\n\n2. Enhanced chunker (cold cache):")
        chunker = EnhancedChunker()
        _, stats = profile_function(chunker.chunk_file, test_file, "python")

        # Show top functions
        print("\nTop 20 time-consuming functions:")
        lines = stats.split("\n")
        for i, line in enumerate(lines):
            if i < 25 and line.strip():
                print(line)

        # Profile with warm cache
        print("\n\n3. Enhanced chunker (warm cache):")
        _, stats = profile_function(chunker.chunk_file, test_file, "python")

        print("\nTop 10 functions (should show cache hits):")
        lines = stats.split("\n")
        for i, line in enumerate(lines):
            if i < 15 and line.strip():
                print(line)

    finally:
        test_file.unlink()


def profile_batch_processing():
    """Profile batch processing operations."""
    print("\nProfiling batch processing")
    print("=" * 70)

    # Create test directory
    temp_dir = Path(tempfile.mkdtemp())

    try:
        # Create test files
        files = []
        for i in range(20):
            file_path = temp_dir / f"test_{i}.py"
            content = f"""
def function_{i}():
    return {i}

class Class_{i}:
    def method(self):
        return {i} * 2
"""
            file_path.write_text(content)
            files.append(file_path)

        # Profile batch processing
        processor = BatchProcessor(max_workers=4)

        for file_path in files:
            processor.add_file(str(file_path))

        print("\n1. Parallel batch processing:")
        _, stats = profile_function(
            processor.process_batch,
            batch_size=20,
            parallel=True,
        )

        # Show relevant functions
        print("\nKey functions:")
        lines = stats.split("\n")
        relevant_keywords = [
            "process_batch",
            "process_file",
            "chunk",
            "parse",
            "thread",
        ]

        for line in lines:
            for keyword in relevant_keywords:
                if keyword in line.lower():
                    print(line)
                    break

    finally:
        shutil.rmtree(temp_dir)


def profile_memory_usage():
    """Profile memory usage patterns."""
    print("\nProfiling memory usage")
    print("=" * 70)

    try:
        import tracemalloc
    except ImportError:
        print("tracemalloc not available in this Python version")
        return

    test_file = create_test_file("large")

    try:
        # Profile standard chunker
        print("\n1. Standard chunker memory usage:")
        tracemalloc.start()

        chunks = chunk_file(test_file, "python")

        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        print(f"   Current memory: {current / 1024 / 1024:.2f} MB")
        print(f"   Peak memory: {peak / 1024 / 1024:.2f} MB")
        print(f"   Chunks generated: {len(chunks)}")

        # Profile enhanced chunker
        print("\n2. Enhanced chunker memory usage:")
        chunker = EnhancedChunker()

        tracemalloc.start()

        # First run (cold cache)
        chunks = chunker.chunk_file(test_file, "python")

        current1, peak1 = tracemalloc.get_traced_memory()

        # Second run (warm cache)
        chunks = chunker.chunk_file(test_file, "python")

        current2, peak2 = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        print("   After first run:")
        print(f"     Current memory: {current1 / 1024 / 1024:.2f} MB")
        print(f"     Peak memory: {peak1 / 1024 / 1024:.2f} MB")
        print("   After second run (cached):")
        print(f"     Current memory: {current2 / 1024 / 1024:.2f} MB")
        print(f"     Peak memory: {peak2 / 1024 / 1024:.2f} MB")

        # Show cache stats
        stats = chunker.get_stats()
        cache_memory = stats["cache"]["total_memory_bytes"]
        print(f"   Cache memory usage: {cache_memory / 1024 / 1024:.2f} MB")

    finally:
        test_file.unlink()


def profile_incremental_parsing():
    """Profile incremental parsing performance."""
    print("\nProfiling incremental parsing")
    print("=" * 70)

    test_file = create_test_file("large")

    try:
        chunker = EnhancedChunker(enable_incremental=True)

        # Initial parse
        print("\n1. Initial parse:")
        _, stats = profile_function(chunker.chunk_file, test_file, "python")

        # Make a small change
        content = test_file.read_text()
        new_content = content.replace(
            "def complex_function_50",
            "def modified_function_50",
        )
        test_file.write_text(new_content)

        # Profile incremental parse
        print("\n2. Incremental parse after small change:")
        _, stats = profile_function(chunker.chunk_file_incremental, test_file, "python")

        # Show functions related to incremental parsing
        print("\nIncremental parsing functions:")
        lines = stats.split("\n")
        incremental_keywords = [
            "incremental",
            "detect_changes",
            "parse_incremental",
            "update_chunks",
        ]

        for line in lines:
            for keyword in incremental_keywords:
                if keyword in line:
                    print(line)
                    break

    finally:
        test_file.unlink()


def generate_performance_report():
    """Generate a comprehensive performance report."""
    print("\nGenerating Performance Report")
    print("=" * 70)

    test_file = create_test_file("medium")

    try:
        # Initialize components
        chunker = EnhancedChunker()

        # Warm up
        chunker.warm_up(["python", "javascript"])

        # Run multiple iterations
        iterations = 10
        times = []

        print(f"\n1. Running {iterations} iterations...")

        for i in range(iterations):
            # Clear cache every 3 iterations to test both scenarios
            if i % 3 == 0:
                chunker.clear_caches()

            start = time.perf_counter()
            chunks = chunker.chunk_file(test_file, "python")
            elapsed = time.perf_counter() - start
            times.append(elapsed)

            print(f"   Iteration {i+1}: {elapsed*1000:.2f}ms")

        # Calculate statistics
        avg_time = sum(times) / len(times)
        min_time = min(times)
        max_time = max(times)

        print("\n2. Performance Summary:")
        print(f"   Average: {avg_time*1000:.2f}ms")
        print(f"   Min: {min_time*1000:.2f}ms")
        print(f"   Max: {max_time*1000:.2f}ms")

        # Get final statistics
        stats = chunker.get_stats()

        print("\n3. Cache Performance:")
        cache_stats = stats["cache"]
        print(f"   Hit rate: {cache_stats['overall_hit_rate']:.2%}")
        print(f"   Total hits: {cache_stats['total_hits']}")
        print(f"   Total misses: {cache_stats['total_misses']}")

        print("\n4. Pool Statistics:")
        pool_stats = stats["pool"]
        for resource_type, resource_stats in pool_stats.items():
            if resource_stats["acquired"] > 0:
                reuse_rate = resource_stats["acquired"] / resource_stats["created"]
                print(f"   {resource_type}:")
                print(f"     Reuse rate: {reuse_rate:.2f}x")
                print(f"     Currently pooled: {resource_stats['pooled']}")

        print("\n5. Performance Metrics:")
        metrics = stats["metrics"]
        for metric_name, metric_stats in sorted(metrics.items()):
            if metric_stats["count"] > 0:
                print(f"   {metric_name}:")
                print(f"     Mean: {metric_stats['mean']:.2f}")
                print(f"     Count: {metric_stats['count']}")

    finally:
        test_file.unlink()


if __name__ == "__main__":
    # Run all profiling
    profile_basic_chunking()
    profile_batch_processing()
    profile_memory_usage()
    profile_incremental_parsing()
    generate_performance_report()

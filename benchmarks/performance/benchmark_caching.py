"""Benchmarks for caching performance."""

import time
import tempfile
import shutil
from pathlib import Path
from typing import List, Tuple
import statistics

from chunker.performance.cache.manager import CacheManager
from chunker.performance.enhanced_chunker import EnhancedChunker
from chunker.chunker import chunk_file


def create_test_files(num_files: int = 100) -> Tuple[Path, List[Path]]:
    """Create test Python files for benchmarking.
    
    Args:
        num_files: Number of files to create
        
    Returns:
        Tuple of (temp_dir, list of file paths)
    """
    temp_dir = Path(tempfile.mkdtemp())
    files = []
    
    for i in range(num_files):
        file_path = temp_dir / f"test_file_{i}.py"
        
        # Create a Python file with some functions
        content = f'''
"""Test file {i} for benchmarking."""

def function_one_{i}(x, y):
    """Add two numbers."""
    return x + y

def function_two_{i}(items):
    """Process a list of items."""
    result = []
    for item in items:
        if item > 0:
            result.append(item * 2)
    return result

class TestClass_{i}:
    """A test class."""
    
    def __init__(self, name):
        self.name = name
        self.value = 0
    
    def method_one(self, x):
        """Increment value by x."""
        self.value += x
        return self.value
    
    def method_two(self):
        """Get current value."""
        return self.value

def function_three_{i}(data):
    """Complex function with nested logic."""
    if isinstance(data, list):
        return [x * 2 for x in data if x > 0]
    elif isinstance(data, dict):
        return {{k: v * 2 for k, v in data.items() if v > 0}}
    else:
        return data * 2
'''
        
        file_path.write_text(content)
        files.append(file_path)
    
    return temp_dir, files


def benchmark_cache_performance(num_files: int = 50, iterations: int = 3):
    """Benchmark caching performance.
    
    Args:
        num_files: Number of files to test
        iterations: Number of iterations for each test
    """
    print(f"\nBenchmarking cache performance with {num_files} files, {iterations} iterations")
    print("=" * 70)
    
    # Create test files
    temp_dir, files = create_test_files(num_files)
    
    try:
        # Test 1: Baseline (no caching)
        print("\n1. Baseline (no caching):")
        baseline_times = []
        
        for i in range(iterations):
            start = time.perf_counter()
            
            for file_path in files:
                chunks = chunk_file(file_path, "python")
            
            elapsed = time.perf_counter() - start
            baseline_times.append(elapsed)
            print(f"   Iteration {i+1}: {elapsed:.3f}s")
        
        baseline_avg = statistics.mean(baseline_times)
        print(f"   Average: {baseline_avg:.3f}s")
        
        # Test 2: With caching (cold start)
        print("\n2. With caching (cold start):")
        chunker = EnhancedChunker()
        
        cold_start = time.perf_counter()
        for file_path in files:
            chunks = chunker.chunk_file(file_path, "python")
        cold_elapsed = time.perf_counter() - cold_start
        print(f"   Cold start: {cold_elapsed:.3f}s")
        
        # Test 3: With caching (warm cache)
        print("\n3. With caching (warm cache):")
        warm_times = []
        
        for i in range(iterations):
            start = time.perf_counter()
            
            for file_path in files:
                chunks = chunker.chunk_file(file_path, "python")
            
            elapsed = time.perf_counter() - start
            warm_times.append(elapsed)
            print(f"   Iteration {i+1}: {elapsed:.3f}s")
        
        warm_avg = statistics.mean(warm_times)
        print(f"   Average: {warm_avg:.3f}s")
        
        # Print cache statistics
        stats = chunker.get_stats()
        cache_stats = stats['cache']
        print("\n4. Cache Statistics:")
        print(f"   Total cache size: {cache_stats['total_size']}")
        print(f"   Cache hit rate: {cache_stats['overall_hit_rate']:.2%}")
        print(f"   Memory usage: {cache_stats['total_memory_bytes'] / 1024 / 1024:.2f} MB")
        
        # Performance improvement
        speedup = baseline_avg / warm_avg
        print(f"\n5. Performance Summary:")
        print(f"   Baseline: {baseline_avg:.3f}s")
        print(f"   With cache: {warm_avg:.3f}s")
        print(f"   Speedup: {speedup:.2f}x")
        print(f"   Time saved: {baseline_avg - warm_avg:.3f}s ({(1 - warm_avg/baseline_avg) * 100:.1f}%)")
        
    finally:
        # Cleanup
        shutil.rmtree(temp_dir)


def benchmark_cache_invalidation(num_files: int = 20):
    """Benchmark cache invalidation strategies."""
    print(f"\nBenchmarking cache invalidation with {num_files} files")
    print("=" * 70)
    
    # Create test files
    temp_dir, files = create_test_files(num_files)
    
    try:
        chunker = EnhancedChunker()
        
        # Populate cache
        print("\n1. Populating cache...")
        for file_path in files:
            chunker.chunk_file(file_path, "python")
        
        initial_stats = chunker.get_stats()['cache']
        print(f"   Initial cache size: {initial_stats['total_size']}")
        
        # Test single file invalidation
        print("\n2. Single file invalidation:")
        start = time.perf_counter()
        chunker.invalidate_file(files[0])
        elapsed = time.perf_counter() - start
        print(f"   Time: {elapsed*1000:.3f}ms")
        
        # Test pattern invalidation
        print("\n3. Pattern invalidation (ast:*test_file_1*.py:*):")
        cache = chunker._cache
        
        # Re-populate
        for file_path in files[:10]:
            chunker.chunk_file(file_path, "python")
        
        start = time.perf_counter()
        count = cache.invalidate_pattern("ast:*test_file_1*.py:*")
        elapsed = time.perf_counter() - start
        print(f"   Invalidated {count} entries in {elapsed*1000:.3f}ms")
        
        # Test full cache clear
        print("\n4. Full cache clear:")
        start = time.perf_counter()
        cache.clear()
        elapsed = time.perf_counter() - start
        print(f"   Time: {elapsed*1000:.3f}ms")
        
    finally:
        # Cleanup
        shutil.rmtree(temp_dir)


def benchmark_cache_memory():
    """Benchmark memory usage of caches."""
    print("\nBenchmarking cache memory usage")
    print("=" * 70)
    
    cache = CacheManager(
        ast_size=1000,
        chunk_size=5000,
        query_size=1000,
        metadata_size=1000
    )
    
    # Test different data sizes
    test_sizes = [100, 1000, 10000]
    
    for size in test_sizes:
        print(f"\n{size} byte values:")
        
        # Fill cache with data
        test_data = b'x' * size
        num_entries = 1000
        
        start_mem = cache.memory_usage()
        
        for i in range(num_entries):
            cache.put(f"test:{i}", test_data)
        
        end_mem = cache.memory_usage()
        
        print(f"   Entries: {num_entries}")
        print(f"   Memory used: {(end_mem - start_mem) / 1024 / 1024:.2f} MB")
        print(f"   Per entry: {(end_mem - start_mem) / num_entries / 1024:.2f} KB")
        
        cache.clear()


if __name__ == "__main__":
    # Run benchmarks
    benchmark_cache_performance(num_files=50, iterations=3)
    benchmark_cache_invalidation(num_files=20)
    benchmark_cache_memory()
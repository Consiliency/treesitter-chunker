"""Demonstration of performance optimization features."""

import tempfile
import time
from pathlib import Path

from chunker.performance.enhanced_chunker import EnhancedChunker
from chunker.performance.optimization.batch import BatchProcessor
from chunker.performance.optimization.memory_pool import MemoryPool
from chunker.performance.optimization.monitor import PerformanceMonitor


def demo_basic_caching():
    """Demonstrate basic caching functionality."""
    print("\n=== Basic Caching Demo ===")

    # Create enhanced chunker
    chunker = EnhancedChunker()

    # Parse a file (cold cache)
    test_file = Path(__file__)

    print(f"\nParsing {test_file.name} with cold cache...")
    start = time.perf_counter()
    chunks1 = chunker.chunk_file(test_file, "python")
    cold_time = time.perf_counter() - start
    print(f"Cold cache: {cold_time * 1000:.2f}ms, {len(chunks1)} chunks")

    # Parse again (warm cache)
    print(f"\nParsing {test_file.name} with warm cache...")
    start = time.perf_counter()
    chunks2 = chunker.chunk_file(test_file, "python")
    warm_time = time.perf_counter() - start
    print(f"Warm cache: {warm_time * 1000:.2f}ms, {len(chunks2)} chunks")

    # Show speedup
    speedup = cold_time / warm_time
    print(f"\nSpeedup: {speedup:.2f}x")

    # Display cache statistics
    stats = chunker.get_stats()
    cache_stats = stats["cache"]
    print("\nCache statistics:")
    print(f"  Hit rate: {cache_stats['overall_hit_rate']:.2%}")
    print(f"  Total size: {cache_stats['total_size']} entries")
    print(f"  Memory usage: {cache_stats['total_memory_bytes'] / 1024:.2f} KB")


def demo_incremental_parsing():
    """Demonstrate incremental parsing."""
    print("\n\n=== Incremental Parsing Demo ===")

    # Create a test file
    test_content = '''
def function_one():
    """First function."""
    return 1

def function_two():
    """Second function."""
    return 2

class TestClass:
    """Test class."""

    def method(self):
        return 3
'''

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(test_content)
        test_file = Path(f.name)

    try:
        chunker = EnhancedChunker(enable_incremental=True)

        # Initial parse
        print("\nInitial parse...")
        chunks1 = chunker.chunk_file(test_file, "python")
        print(f"Found {len(chunks1)} chunks")

        # Make a small change
        new_content = test_content.replace("return 1", "return 100")
        test_file.write_text(new_content)

        # Incremental parse
        print("\nIncremental parse after small change...")
        start = time.perf_counter()
        chunker.chunk_file_incremental(test_file, "python")
        incr_time = time.perf_counter() - start
        print(f"Incremental parse: {incr_time * 1000:.2f}ms")

        # Compare with full reparse
        chunker.invalidate_file(test_file)  # Clear cache
        start = time.perf_counter()
        chunker.chunk_file(test_file, "python", force_reparse=True)
        full_time = time.perf_counter() - start
        print(f"Full reparse: {full_time * 1000:.2f}ms")

        if incr_time < full_time:
            print(f"\nIncremental parsing was {full_time / incr_time:.2f}x faster!")

    finally:
        test_file.unlink()


def demo_batch_processing():
    """Demonstrate batch processing."""
    print("\n\n=== Batch Processing Demo ===")

    # Find Python files in current directory
    current_dir = Path(__file__).parent
    py_files = list(current_dir.glob("*.py"))[:5]  # Limit to 5 files

    if not py_files:
        print("No Python files found in current directory")
        return

    print(f"\nFound {len(py_files)} Python files to process")

    # Create batch processor with monitoring
    monitor = PerformanceMonitor()
    processor = BatchProcessor(
        performance_monitor=monitor,
        max_workers=2,
    )

    # Add files with size-based priority
    for file_path in py_files:
        size = file_path.stat().st_size
        processor.add_file(str(file_path), priority=size)
        print(f"  Added {file_path.name} (priority: {size})")

    # Process batch
    print("\nProcessing batch...")
    start = time.perf_counter()
    results = processor.process_batch(batch_size=len(py_files), parallel=True)
    elapsed = time.perf_counter() - start

    # Show results
    total_chunks = sum(len(chunks) for chunks in results.values())
    print(f"\nProcessed {len(results)} files in {elapsed:.2f}s")
    print(f"Total chunks: {total_chunks}")
    print(f"Files/second: {len(results) / elapsed:.1f}")

    # Show performance metrics
    print("\nPerformance metrics:")
    metrics = monitor.get_metrics()
    for name, stats in sorted(metrics.items()):
        if stats["count"] > 0:
            print(f"  {name}: {stats['mean']:.2f} (avg of {stats['count']})")


def demo_memory_pooling():
    """Demonstrate memory pooling benefits."""
    print("\n\n=== Memory Pooling Demo ===")

    pool = MemoryPool(max_pool_size=5)

    # Warm up pool
    print("\nWarming up parser pool...")
    pool.warm_up("parser:python", 3)

    # Acquire and release parsers
    print("\nAcquiring and releasing parsers...")
    parsers_used = []

    for i in range(5):
        parser = pool.acquire_parser("python")
        parsers_used.append(parser)
        print(f"  Acquired parser {i + 1}")

    # Release them back
    for i, parser in enumerate(parsers_used):
        pool.release_parser(parser, "python")
        print(f"  Released parser {i + 1}")

    # Show pool statistics
    stats = pool.get_stats()
    if "parser:python" in stats:
        p_stats = stats["parser:python"]
        print("\nPool statistics:")
        print(f"  Created: {p_stats['created']} parsers")
        print(f"  Acquired: {p_stats['acquired']} times")
        print(f"  Released: {p_stats['released']} times")
        print(f"  Currently pooled: {p_stats['pooled']}")

        reuse_rate = (
            p_stats["acquired"] / p_stats["created"] if p_stats["created"] > 0 else 0
        )
        print(f"  Reuse rate: {reuse_rate:.2f}x")


def demo_performance_monitoring():
    """Demonstrate performance monitoring."""
    print("\n\n=== Performance Monitoring Demo ===")

    monitor = PerformanceMonitor()

    # Time various operations
    operations = [
        ("fast_operation", 0.01),
        ("medium_operation", 0.05),
        ("slow_operation", 0.1),
    ]

    print("\nTiming operations...")
    for op_name, sleep_time in operations:
        with monitor.measure(op_name):
            time.sleep(sleep_time)  # Simulate work
            print(f"  Executed {op_name}")

    # Record some metrics
    print("\nRecording metrics...")
    for i in range(10):
        monitor.record_metric("file_size", 1000 + i * 500)
        monitor.record_metric("chunk_count", 5 + i)

    # Display summary
    print("\n" + monitor.get_summary())


def main():
    """Run all demonstrations."""
    print("Tree-sitter Chunker Performance Optimization Demo")
    print("=" * 50)

    demos = [
        demo_basic_caching,
        demo_incremental_parsing,
        demo_batch_processing,
        demo_memory_pooling,
        demo_performance_monitoring,
    ]

    for demo in demos:
        try:
            demo()
        except (TypeError, ValueError) as e:
            print(f"\nError in {demo.__name__}: {e}")

    print("\n\nDemo complete!")


if __name__ == "__main__":
    main()

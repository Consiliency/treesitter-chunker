"""Example demonstrating Garbage Collection tuning for performance optimization."""

import gc
import time

from chunker import (
    gc_disabled,
    get_memory_optimizer,
    optimized_gc,
    tune_gc_for_batch,
    tune_gc_for_streaming,
)


def example_batch_processing():
    """Example: GC tuning for batch processing."""
    print("=== Batch Processing GC Tuning ===")

    # Get original thresholds
    original = gc.get_threshold()
    print(f"Original GC thresholds: {original}")

    # Tune for batch processing
    tune_gc_for_batch(1000)
    print(f"Batch processing thresholds: {gc.get_threshold()}")

    # Process batch data
    batch_data = [{"id": i, "data": list(range(100))} for i in range(1000)]

    start = time.perf_counter()
    results = [sum(item["data"]) for item in batch_data]
    elapsed = time.perf_counter() - start

    print(f"Processed {len(batch_data)} items in {elapsed:.3f}s")

    # Restore original
    gc.set_threshold(*original)


def example_streaming_processing():
    """Example: GC tuning for streaming."""
    print("\n=== Streaming GC Tuning ===")

    original = gc.get_threshold()

    # Tune for streaming
    tune_gc_for_streaming()
    print(f"Streaming thresholds: {gc.get_threshold()}")

    # Simulate streaming processing
    stream_count = 0
    for i in range(10000):
        # Process stream item
        {"item": i, "value": i * 2}
        stream_count += 1

        # GC will run more frequently for gen0

    print(f"Processed {stream_count} stream items")

    gc.set_threshold(*original)


def example_context_manager():
    """Example: Using GC optimization context managers."""
    print("\n=== Context Manager Examples ===")

    # Example 1: Optimize for batch task
    with optimized_gc("batch"):
        print("Processing batch with optimized GC...")
        # Batch processing here
        data = [i**2 for i in range(10000)]
        print(f"Processed {len(data)} items")

    # Example 2: Disable GC for critical section
    print("\nCritical section with GC disabled:")
    with gc_disabled():
        print(f"GC enabled: {gc.isenabled()}")
        # Critical performance section
        critical_data = [list(range(100)) for _i in range(1000)]

    print(f"GC enabled after context: {gc.isenabled()}")


def example_object_pooling():
    """Example: Using object pools to reduce allocation overhead."""
    print("\n=== Object Pooling Example ===")

    # Get memory optimizer
    optimizer = get_memory_optimizer()

    # Create object pool for dictionaries
    pool = optimizer.create_object_pool(
        dict,
        dict,
        max_size=50,
    )

    # Use pooled objects
    objects_used = []

    # Acquire objects from pool
    for i in range(10):
        obj = pool.acquire()
        obj["id"] = i
        obj["data"] = list(range(10))
        objects_used.append(obj)

    # Get pool stats
    stats = pool.get_stats()
    print("Pool stats after acquisition:")
    print(f"  Created: {stats['created']}")
    print(f"  In use: {stats['in_use']}")

    # Release objects back to pool
    for obj in objects_used:
        pool.release(obj)

    # Acquire again - should reuse
    obj = pool.acquire()
    stats = pool.get_stats()
    print("\nPool stats after release and reacquire:")
    print(f"  Reused: {stats['reused']}")
    print(f"  Reuse rate: {stats['reuse_rate']:.1%}")


def example_memory_monitoring():
    """Example: Monitor memory usage."""
    print("\n=== Memory Monitoring Example ===")

    optimizer = get_memory_optimizer()

    # Create some data
    large_data = [list(range(1000)) for _ in range(1000)]

    # Get memory usage
    usage = optimizer.get_memory_usage()

    print("Memory usage statistics:")
    print(f"  RSS: {usage['rss'] / 1024 / 1024:.1f} MB")
    print(f"  VMS: {usage['vms'] / 1024 / 1024:.1f} MB")
    print(f"  Available: {usage['available'] / 1024 / 1024 / 1024:.1f} GB")

    # Clean up
    del large_data
    gc.collect()


def example_memory_efficient_batch():
    """Example: Process large dataset in memory-efficient batches."""
    print("\n=== Memory-Efficient Batch Processing ===")

    optimizer = get_memory_optimizer()

    # Large dataset
    large_dataset = list(range(10000))

    # Process in batches
    total_sum = 0
    batch_count = 0

    for batch in optimizer.memory_efficient_batch(large_dataset, batch_size=1000):
        batch_count += 1
        # Process batch
        batch_sum = sum(x**2 for x in batch)
        total_sum += batch_sum
        print(f"  Processed batch {batch_count}: {len(batch)} items")

    print(f"Total sum: {total_sum}")
    print(f"Processed {batch_count} batches")


if __name__ == "__main__":
    # Run examples
    example_batch_processing()
    example_streaming_processing()
    example_context_manager()
    example_object_pooling()

    try:
        example_memory_monitoring()
    except ImportError:
        print("\n(Memory monitoring requires psutil - skipping)")

    example_memory_efficient_batch()

    print("\n✅ All GC tuning examples completed!")

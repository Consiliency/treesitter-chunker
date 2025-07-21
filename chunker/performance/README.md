# Performance Module

The performance module provides comprehensive optimizations for Tree-sitter parsing and chunking operations, designed to handle large codebases efficiently.

## Features

### 1. Multi-Level Caching

The caching system provides multiple levels of caching for different data types:

- **AST Cache**: Stores parsed Abstract Syntax Trees
- **Chunk Cache**: Stores generated code chunks
- **Query Cache**: Stores query results
- **Metadata Cache**: Stores file metadata

```python
from chunker.performance.cache.manager import CacheManager

# Initialize cache manager
cache = CacheManager(
    ast_size=100,      # Max AST entries
    chunk_size=1000,   # Max chunk entries
    query_size=500,    # Max query entries
    metadata_size=500  # Max metadata entries
)

# Cache operations
cache.cache_ast(file_path, source_hash, ast, language, parse_time_ms)
cached_ast = cache.get_cached_ast(file_path, source_hash)

# Invalidate file caches
cache.invalidate_file(file_path)
```

### 2. Incremental Parsing

Leverages Tree-sitter's incremental parsing capabilities to efficiently handle file changes:

```python
from chunker.performance.optimization.incremental import IncrementalParser

parser = IncrementalParser()

# Detect changes between versions
changes = parser.detect_changes(old_source, new_source)

# Parse incrementally
new_tree = parser.parse_incremental(old_tree, new_source, changes)

# Update chunks based on changes
new_chunks = parser.update_chunks(old_chunks, old_tree, new_tree, changes)
```

### 3. Memory Pooling

Reuses expensive objects like parsers to reduce allocation overhead:

```python
from chunker.performance.optimization.memory_pool import MemoryPool

pool = MemoryPool(max_pool_size=50)

# Acquire and release parsers
parser = pool.acquire_parser("python")
# Use parser...
pool.release_parser(parser, "python")

# Warm up pool
pool.warm_up("parser:python", count=5)
```

### 4. Performance Monitoring

Tracks and reports performance metrics:

```python
from chunker.performance.optimization.monitor import PerformanceMonitor

monitor = PerformanceMonitor()

# Time operations
with monitor.measure('parse_file'):
    # Perform operation
    pass

# Record custom metrics
monitor.record_metric('file_size', 1024)

# Get statistics
stats = monitor.get_metrics()
print(monitor.get_summary())
```

### 5. Batch Processing

Efficiently processes multiple files with priority support:

```python
from chunker.performance.optimization.batch import BatchProcessor

processor = BatchProcessor(max_workers=4)

# Add files with priority
processor.add_file("important.py", priority=10)
processor.add_file("normal.py", priority=5)

# Process batch
results = processor.process_batch(batch_size=20, parallel=True)

# Process entire directory
results = processor.process_directory("/path/to/code", pattern="**/*.py")
```

## Enhanced Chunker

The `EnhancedChunker` combines all optimizations:

```python
from chunker.performance.enhanced_chunker import EnhancedChunker

# Initialize with all optimizations
chunker = EnhancedChunker(
    enable_incremental=True
)

# Warm up for expected languages
chunker.warm_up(['python', 'javascript'])

# Parse with caching
chunks = chunker.chunk_file("file.py", "python")

# Parse incrementally after changes
chunks = chunker.chunk_file_incremental("file.py", "python")

# Get performance statistics
stats = chunker.get_stats()
```

## Performance Benchmarks

Run benchmarks to measure performance improvements:

```bash
# Cache performance
python benchmarks/performance/benchmark_caching.py

# Incremental parsing
python benchmarks/performance/benchmark_incremental.py

# Batch processing
python benchmarks/performance/benchmark_batch.py
```

## Profiling Tools

Profile the chunker to identify bottlenecks:

```bash
# Run profiling suite
python profiling/profile_chunker.py
```

## Configuration Tips

1. **Cache Sizes**: Adjust based on available memory and codebase size
2. **Pool Sizes**: Set based on concurrent processing needs
3. **Batch Sizes**: Balance between memory usage and parallelism
4. **TTL Settings**: Configure based on file change frequency

## Thread Safety

All components are designed to be thread-safe for concurrent usage:
- Caches use thread-safe data structures
- Memory pools use locking for resource management
- Performance monitors aggregate metrics safely

## Memory Considerations

- Cache memory usage can be monitored via `cache.memory_usage()`
- Implement cache eviction policies for long-running processes
- Use `cache.evict_expired()` to clean up expired entries
- Clear caches periodically with `cache.clear()` if needed
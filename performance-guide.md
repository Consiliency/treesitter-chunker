# Performance Guide

This guide provides comprehensive strategies and best practices for optimizing Tree-sitter Chunker performance. Learn how to leverage caching, parallel processing, and streaming to handle codebases of any size efficiently.

## Table of Contents

1. [Performance Overview](#performance-overview)
2. [AST Caching](#ast-caching)
3. [Parallel Processing](#parallel-processing)
4. [Streaming Large Files](#streaming-large-files)
5. [Memory Management](#memory-management)
6. [Benchmarking](#benchmarking)
7. [Configuration Tuning](#configuration-tuning)
8. [Common Bottlenecks](#common-bottlenecks)
9. [Performance Monitoring](#performance-monitoring)
10. [Best Practices](#best-practices)

## Performance Overview

Tree-sitter Chunker is designed for high performance with several key optimizations:

- **AST Caching**: Up to 11.9x speedup for repeated file processing
- **Parser Pooling**: Efficient reuse of parser instances
- **Parallel Processing**: Near-linear speedup with CPU cores
- **Streaming Support**: Process files larger than available memory
- **Lazy Loading**: Languages loaded only when needed

### Performance Metrics

| Operation | Performance | Notes |
|-----------|------------|-------|
| Parser Creation | ~10-50ms | One-time cost per language |
| File Parsing | O(n) with file size | ~1MB/s typical |
| Cached Parse | ~0.1ms | 11.9x speedup |
| Chunk Extraction | O(n) with AST nodes | Linear traversal |
| Memory Usage | ~10x source size | For AST storage |

## AST Caching

The AST cache dramatically improves performance when processing files multiple times.

### Basic Usage

```python
from chunker import chunk_file, ASTCache

# Caching is enabled by default
chunks1 = chunk_file("large_file.py", "python")  # Parses file
chunks2 = chunk_file("large_file.py", "python")  # Uses cache (11.9x faster)
```

### Cache Configuration

```python
from chunker import ASTCache

# Create cache with custom size
cache = ASTCache(max_size=500)  # Cache up to 500 ASTs

# Monitor cache performance
stats = cache.get_stats()
print(f"Hit rate: {stats['hit_rate']:.2%}")
print(f"Hits: {stats['hits']}, Misses: {stats['misses']}")
print(f"Current size: {stats['size']}/{stats['max_size']}")

# Clear cache when needed
cache.clear()
```

### Cache Key Strategy

The cache uses a composite key based on:
- File path (absolute)
- File modification time
- File size
- Language

This ensures cache invalidation when files change.

### Advanced Caching

```python
from chunker import ASTCache
from pathlib import Path
import time

class SmartChunker:
    def __init__(self, cache_size=200):
        self.cache = ASTCache(max_size=cache_size)
        
    def process_with_cache_warmup(self, files, language):
        """Warm up cache for frequently accessed files."""
        # Pre-process popular files
        popular_files = self.identify_popular_files(files)
        for file in popular_files[:self.cache.max_size]:
            chunk_file(file, language)  # Warm cache
        
        # Process all files
        results = {}
        for file in files:
            results[file] = chunk_file(file, language)
        
        return results
    
    def monitor_cache_efficiency(self):
        """Monitor and report cache efficiency."""
        stats = self.cache.get_stats()
        if stats['hit_rate'] < 0.5 and stats['size'] == stats['max_size']:
            print("Consider increasing cache size for better performance")
        return stats
```

## Parallel Processing

Leverage multiple CPU cores for processing many files simultaneously.

### Basic Parallel Processing

```python
from chunker import chunk_files_parallel

# Process multiple files in parallel
files = ["file1.py", "file2.py", "file3.py", "file4.py"]
results = chunk_files_parallel(
    files,
    "python",
    max_workers=4,  # Use 4 CPU cores
    show_progress=True
)

# Results is a dict mapping file paths to chunks
for file_path, chunks in results.items():
    print(f"{file_path}: {len(chunks)} chunks")
```

### Directory Processing

```python
from chunker import chunk_directory_parallel

# Process entire directory tree
results = chunk_directory_parallel(
    "src/",
    "python",
    pattern="**/*.py",  # Glob pattern
    max_workers=8,
    show_progress=True
)

print(f"Processed {len(results)} files")
```

### Custom Parallel Implementation

```python
from concurrent.futures import ProcessPoolExecutor, as_completed
from chunker import chunk_file
import multiprocessing as mp

def process_large_codebase(directory, language):
    """Custom parallel processing with fine control."""
    from pathlib import Path
    
    # Find all files
    files = list(Path(directory).rglob(f"*.{language[:2]}"))
    
    # Determine optimal worker count
    cpu_count = mp.cpu_count()
    worker_count = min(cpu_count, len(files), 32)  # Cap at 32
    
    results = {}
    failed = []
    
    # Process with progress tracking
    with ProcessPoolExecutor(max_workers=worker_count) as executor:
        # Submit all tasks
        future_to_file = {
            executor.submit(chunk_file, str(f), language): f 
            for f in files
        }
        
        # Process completed tasks
        for future in as_completed(future_to_file):
            file = future_to_file[future]
            try:
                chunks = future.result(timeout=30)
                results[str(file)] = chunks
            except Exception as e:
                print(f"Failed to process {file}: {e}")
                failed.append(file)
    
    return results, failed

# Use it
results, failed = process_large_codebase("large_project/", "python")
print(f"Processed: {len(results)}, Failed: {len(failed)}")
```

### Parallel Processing Best Practices

1. **Worker Count**: Use `min(cpu_count, file_count)` workers
2. **Batch Size**: Group small files to reduce overhead
3. **Memory Limits**: Monitor memory usage with many workers
4. **Error Handling**: Isolate failures to individual files

## Streaming Large Files

For files too large to fit in memory, use streaming processing.

### Basic Streaming

```python
from chunker import chunk_file_streaming

# Process a very large file
for chunk in chunk_file_streaming("huge_codebase.py", "python"):
    # Each chunk is yielded as it's found
    print(f"Found {chunk.node_type} at lines {chunk.start_line}-{chunk.end_line}")
    
    # Process immediately without storing all chunks
    if chunk.node_type == "function_definition":
        analyze_function(chunk)
```

### Streaming with Batching

```python
from chunker import chunk_file_streaming
from itertools import islice

def process_in_batches(file_path, language, batch_size=100):
    """Process chunks in batches to balance memory and efficiency."""
    stream = chunk_file_streaming(file_path, language)
    
    while True:
        # Get next batch
        batch = list(islice(stream, batch_size))
        if not batch:
            break
            
        # Process batch
        process_batch(batch)
        
        # Optional: Clear memory between batches
        import gc
        gc.collect()

def process_batch(chunks):
    """Process a batch of chunks."""
    # Example: Save to database
    records = [chunk_to_record(chunk) for chunk in chunks]
    db.insert_many(records)
```

### Custom Streaming Implementation

```python
from chunker import StreamingChunker
import mmap

class MemoryEfficientChunker:
    def __init__(self, language):
        self.chunker = StreamingChunker(language)
    
    def process_huge_file(self, file_path):
        """Process files of any size efficiently."""
        with open(file_path, 'rb') as f:
            # Use memory mapping for efficient access
            with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mmapped:
                # Process in chunks
                chunk_size = 1024 * 1024  # 1MB chunks
                offset = 0
                
                while offset < len(mmapped):
                    # Read chunk
                    end = min(offset + chunk_size, len(mmapped))
                    data = mmapped[offset:end]
                    
                    # Process chunk
                    for code_chunk in self.chunker.process_bytes(data, offset):
                        yield code_chunk
                    
                    offset = end
```

## Memory Management

Optimize memory usage for large-scale processing.

### Memory Profiling

```python
import psutil
import os
from chunker import chunk_file

def profile_memory_usage(file_path, language):
    """Profile memory usage during chunking."""
    process = psutil.Process(os.getpid())
    
    # Baseline memory
    baseline = process.memory_info().rss / 1024 / 1024  # MB
    
    # Process file
    chunks = chunk_file(file_path, language)
    
    # Peak memory
    peak = process.memory_info().rss / 1024 / 1024  # MB
    
    print(f"Memory usage: {peak - baseline:.1f} MB")
    print(f"Memory per chunk: {(peak - baseline) / len(chunks):.2f} MB")
    
    return chunks
```

### Memory Optimization Strategies

```python
from chunker import chunk_files_parallel, ASTCache
import gc

class MemoryOptimizedProcessor:
    def __init__(self):
        # Smaller cache for memory-constrained environments
        self.cache = ASTCache(max_size=50)
    
    def process_with_memory_limit(self, files, language, memory_limit_mb=1000):
        """Process files while staying within memory limit."""
        import resource
        
        # Set memory limit (Unix only)
        if hasattr(resource, 'RLIMIT_AS'):
            resource.setrlimit(
                resource.RLIMIT_AS,
                (memory_limit_mb * 1024 * 1024, -1)
            )
        
        # Process in smaller batches
        batch_size = max(1, memory_limit_mb // 100)  # Rough estimate
        results = {}
        
        for i in range(0, len(files), batch_size):
            batch = files[i:i + batch_size]
            batch_results = chunk_files_parallel(batch, language, max_workers=2)
            results.update(batch_results)
            
            # Force garbage collection between batches
            gc.collect()
            
            # Clear cache if memory pressure
            if self.get_memory_usage() > memory_limit_mb * 0.8:
                self.cache.clear()
        
        return results
    
    def get_memory_usage(self):
        """Get current memory usage in MB."""
        import psutil
        process = psutil.Process(os.getpid())
        return process.memory_info().rss / 1024 / 1024
```

## Benchmarking

Measure and compare performance across different scenarios.

### Basic Benchmarking

```python
import time
from chunker import chunk_file, chunk_files_parallel

def benchmark_single_vs_parallel(files, language):
    """Compare single-threaded vs parallel processing."""
    
    # Single-threaded
    start = time.time()
    results_single = {}
    for file in files:
        results_single[file] = chunk_file(file, language)
    single_time = time.time() - start
    
    # Clear cache for fair comparison
    from chunker import clear_cache
    clear_cache()
    
    # Parallel
    start = time.time()
    results_parallel = chunk_files_parallel(files, language)
    parallel_time = time.time() - start
    
    print(f"Single-threaded: {single_time:.2f}s")
    print(f"Parallel: {parallel_time:.2f}s")
    print(f"Speedup: {single_time / parallel_time:.2f}x")
    
    return results_parallel
```

### Comprehensive Benchmark Suite

```python
import time
import statistics
from pathlib import Path
from chunker import chunk_file, ASTCache, chunk_file_streaming

class ChunkerBenchmark:
    def __init__(self):
        self.results = {}
    
    def benchmark_cache_performance(self, file_path, language, iterations=10):
        """Benchmark cache hit performance."""
        times_cold = []
        times_hot = []
        
        for i in range(iterations):
            # Cold cache
            cache = ASTCache()
            cache.clear()
            
            start = time.perf_counter()
            chunk_file(file_path, language)
            times_cold.append(time.perf_counter() - start)
            
            # Hot cache
            start = time.perf_counter()
            chunk_file(file_path, language)
            times_hot.append(time.perf_counter() - start)
        
        cold_avg = statistics.mean(times_cold)
        hot_avg = statistics.mean(times_hot)
        
        self.results['cache'] = {
            'cold_avg': cold_avg,
            'hot_avg': hot_avg,
            'speedup': cold_avg / hot_avg,
            'cold_stdev': statistics.stdev(times_cold),
            'hot_stdev': statistics.stdev(times_hot)
        }
        
        print(f"Cache Performance:")
        print(f"  Cold: {cold_avg*1000:.1f}ms ± {statistics.stdev(times_cold)*1000:.1f}ms")
        print(f"  Hot:  {hot_avg*1000:.1f}ms ± {statistics.stdev(times_hot)*1000:.1f}ms")
        print(f"  Speedup: {cold_avg / hot_avg:.1f}x")
    
    def benchmark_file_sizes(self, language):
        """Benchmark performance across different file sizes."""
        # Create test files of different sizes
        test_sizes = [100, 1000, 10000, 100000]  # lines
        
        for size in test_sizes:
            content = self.generate_test_file(size, language)
            file_path = f"test_{size}.{language[:2]}"
            
            with open(file_path, 'w') as f:
                f.write(content)
            
            start = time.perf_counter()
            chunks = chunk_file(file_path, language)
            elapsed = time.perf_counter() - start
            
            print(f"{size} lines: {elapsed*1000:.1f}ms, {len(chunks)} chunks")
            print(f"  Rate: {size/elapsed:.0f} lines/sec")
            
            Path(file_path).unlink()  # Clean up
    
    def generate_test_file(self, lines, language):
        """Generate test file with specified number of lines."""
        if language == "python":
            template = """def function_{i}(x, y):
    \"\"\"Function {i} docstring.\"\"\"
    result = x + y + {i}
    return result

"""
            functions = lines // 5  # Each function is ~5 lines
            return '\n'.join(template.format(i=i) for i in range(functions))
        
        # Add other languages as needed
        return '\n' * lines
```

## Configuration Tuning

Optimize configuration for your specific use case.

### Cache Size Tuning

```python
from chunker import ASTCache
import psutil

def determine_optimal_cache_size():
    """Determine optimal cache size based on available memory."""
    # Get available memory
    available_mb = psutil.virtual_memory().available / 1024 / 1024
    
    # Use 10% of available memory for cache (rough estimate)
    # Assume average AST size of 1MB
    optimal_size = int(available_mb * 0.1)
    
    # Apply reasonable bounds
    optimal_size = max(50, min(optimal_size, 1000))
    
    print(f"Recommended cache size: {optimal_size} entries")
    return optimal_size

# Use it
cache = ASTCache(max_size=determine_optimal_cache_size())
```

### Worker Count Optimization

```python
import multiprocessing as mp
from chunker import chunk_files_parallel

def determine_optimal_workers(file_count):
    """Determine optimal number of workers."""
    cpu_count = mp.cpu_count()
    
    # Rules of thumb:
    # - Don't exceed CPU count
    # - Don't create more workers than files
    # - Account for memory constraints
    # - Leave some CPUs for system
    
    if file_count < 10:
        return min(file_count, 2)
    elif file_count < 100:
        return min(file_count, cpu_count // 2)
    else:
        return min(32, cpu_count - 1)  # Leave one CPU free

# Use it
files = ["file1.py", "file2.py", ...]  # Your files
optimal_workers = determine_optimal_workers(len(files))
results = chunk_files_parallel(files, "python", max_workers=optimal_workers)
```

### Configuration File Optimization

```toml
# chunker.config.toml - Optimized for large codebases

# Performance settings
[performance]
cache_size = 500  # Increase for frequently accessed files
parser_pool_size = 10  # Number of parsers per language
parallel_workers = 8  # Adjust based on CPU count

# Memory management
[memory]
max_file_size_mb = 50  # Stream files larger than this
streaming_chunk_size = 1048576  # 1MB chunks for streaming
gc_threshold = 100  # Run GC after processing N files

# Language-specific optimizations
[languages.python]
enabled = true
# Only chunk what you need
chunk_types = ["function_definition", "class_definition"]
min_chunk_size = 5  # Skip tiny functions
max_chunk_size = 500  # Split huge functions

[languages.javascript]
enabled = true
# Include only important constructs
chunk_types = ["function_declaration", "class_declaration", "arrow_function"]
# Skip minified files
exclude_patterns = ["*.min.js", "*bundle.js"]
```

## Common Bottlenecks

### 1. Parser Creation Overhead

**Problem**: Creating parsers is expensive (~10-50ms each).

**Solution**: Reuse parsers with pooling.

```python
from chunker import get_parser, return_parser

# Bad: Creating new parser each time
def process_files_slow(files, language):
    results = []
    for file in files:
        parser = get_parser(language)  # Expensive!
        # ... use parser ...
    return results

# Good: Reuse parser
def process_files_fast(files, language):
    parser = get_parser(language)  # Create once
    try:
        results = []
        for file in files:
            # ... use same parser ...
            results.append(result)
        return results
    finally:
        return_parser(language, parser)  # Return for reuse
```

### 2. Memory Exhaustion

**Problem**: Processing too many large files at once.

**Solution**: Use streaming and batching.

```python
# Bad: Load everything into memory
def process_all_at_once(directory, language):
    all_chunks = []
    for file in Path(directory).rglob("*.py"):
        chunks = chunk_file(file, language)
        all_chunks.extend(chunks)  # Memory grows unbounded!
    return all_chunks

# Good: Process and release
def process_incrementally(directory, language):
    for file in Path(directory).rglob("*.py"):
        chunks = chunk_file(file, language)
        yield from chunks  # Yield immediately
        # Chunks are garbage collected after use
```

### 3. Cache Thrashing

**Problem**: Cache constantly evicting useful entries.

**Solution**: Increase cache size or implement smarter eviction.

```python
from chunker import ASTCache

class SmartCache(ASTCache):
    def __init__(self, max_size=100):
        super().__init__(max_size)
        self.access_counts = {}
    
    def get(self, file_path, language):
        result = super().get(file_path, language)
        if result:
            # Track access frequency
            key = (str(file_path), language)
            self.access_counts[key] = self.access_counts.get(key, 0) + 1
        return result
    
    def evict_least_frequently_used(self):
        """Evict based on access frequency instead of recency."""
        if len(self.cache) >= self.max_size:
            # Find least frequently used
            lfu_key = min(self.access_counts.items(), key=lambda x: x[1])[0]
            del self.cache[lfu_key]
            del self.access_counts[lfu_key]
```

## Performance Monitoring

### Real-time Monitoring

```python
import time
import psutil
import threading
from chunker import chunk_files_parallel

class PerformanceMonitor:
    def __init__(self):
        self.running = False
        self.stats = {
            'files_processed': 0,
            'chunks_extracted': 0,
            'processing_time': 0,
            'peak_memory_mb': 0,
            'cpu_percent': []
        }
    
    def start_monitoring(self):
        """Start background monitoring thread."""
        self.running = True
        self.monitor_thread = threading.Thread(target=self._monitor)
        self.monitor_thread.start()
    
    def stop_monitoring(self):
        """Stop monitoring and return stats."""
        self.running = False
        self.monitor_thread.join()
        return self.stats
    
    def _monitor(self):
        """Background monitoring loop."""
        process = psutil.Process()
        
        while self.running:
            # CPU usage
            cpu = process.cpu_percent(interval=0.1)
            self.stats['cpu_percent'].append(cpu)
            
            # Memory usage
            memory_mb = process.memory_info().rss / 1024 / 1024
            self.stats['peak_memory_mb'] = max(
                self.stats['peak_memory_mb'], 
                memory_mb
            )
            
            time.sleep(0.1)
    
    def process_with_monitoring(self, files, language):
        """Process files while monitoring performance."""
        self.start_monitoring()
        start_time = time.time()
        
        try:
            results = chunk_files_parallel(files, language)
            
            # Update stats
            self.stats['files_processed'] = len(results)
            self.stats['chunks_extracted'] = sum(
                len(chunks) for chunks in results.values()
            )
            self.stats['processing_time'] = time.time() - start_time
            
            return results
        finally:
            stats = self.stop_monitoring()
            self.print_report(stats)
    
    def print_report(self, stats):
        """Print performance report."""
        print("\nPerformance Report:")
        print(f"Files processed: {stats['files_processed']}")
        print(f"Chunks extracted: {stats['chunks_extracted']}")
        print(f"Processing time: {stats['processing_time']:.2f}s")
        print(f"Peak memory: {stats['peak_memory_mb']:.1f} MB")
        
        if stats['cpu_percent']:
            avg_cpu = sum(stats['cpu_percent']) / len(stats['cpu_percent'])
            print(f"Average CPU: {avg_cpu:.1f}%")
        
        if stats['processing_time'] > 0:
            rate = stats['files_processed'] / stats['processing_time']
            print(f"Processing rate: {rate:.1f} files/sec")
```

### Logging Performance Metrics

```python
import logging
from functools import wraps
from chunker import chunk_file

# Configure performance logger
perf_logger = logging.getLogger('chunker.performance')
perf_logger.setLevel(logging.INFO)

def log_performance(func):
    """Decorator to log function performance."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed = time.perf_counter() - start
        
        perf_logger.info(
            f"{func.__name__} completed in {elapsed:.3f}s"
        )
        return result
    return wrapper

# Use it
@log_performance
def process_codebase(directory, language):
    # Your processing logic
    pass
```

## Best Practices

### 1. Profile Before Optimizing

Always measure before optimizing:

```python
import cProfile
import pstats

def profile_chunking(file_path, language):
    """Profile chunking performance."""
    profiler = cProfile.Profile()
    profiler.enable()
    
    # Run the code
    chunks = chunk_file(file_path, language)
    
    profiler.disable()
    
    # Print stats
    stats = pstats.Stats(profiler)
    stats.sort_stats('cumulative')
    stats.print_stats(10)  # Top 10 functions
    
    return chunks
```

### 2. Choose the Right Tool

- **Small files (<1MB)**: Use `chunk_file()`
- **Many files**: Use `chunk_files_parallel()`
- **Large files (>10MB)**: Use `chunk_file_streaming()`
- **Entire codebases**: Use `chunk_directory_parallel()`

### 3. Optimize for Your Use Case

```python
# For CI/CD - Speed matters most
config = {
    'max_workers': mp.cpu_count(),
    'cache_size': 1000,
    'show_progress': False
}

# For development - Memory efficiency matters
config = {
    'max_workers': 2,
    'cache_size': 100,
    'streaming_threshold': 5 * 1024 * 1024  # 5MB
}

# For analysis - Completeness matters
config = {
    'max_workers': 4,
    'timeout': None,  # No timeout
    'ignore_errors': False
}
```

### 4. Monitor and Adjust

Continuously monitor and adjust based on real-world usage:

```python
from chunker import ASTCache

# Periodic cache effectiveness check
def check_cache_effectiveness():
    cache = ASTCache()
    stats = cache.get_stats()
    
    if stats['hit_rate'] < 0.3:
        print("Low cache hit rate - consider:")
        print("- Increasing cache size")
        print("- Pre-warming cache with common files")
        print("- Checking if files are being modified")
    
    if stats['size'] == stats['max_size'] and stats['misses'] > stats['hits']:
        print("Cache is full but ineffective - increase size")
```

### 5. Error Recovery

Build resilient systems that handle failures gracefully:

```python
def robust_processing(files, language, max_retries=3):
    """Process files with retry logic and error handling."""
    results = {}
    failed = []
    
    for file in files:
        for attempt in range(max_retries):
            try:
                chunks = chunk_file(file, language)
                results[file] = chunks
                break
            except Exception as e:
                if attempt == max_retries - 1:
                    print(f"Failed to process {file} after {max_retries} attempts: {e}")
                    failed.append((file, str(e)))
                else:
                    time.sleep(0.1 * (attempt + 1))  # Exponential backoff
    
    return results, failed
```

## See Also

- [API Reference](api-reference.md) - Complete API documentation
- [User Guide](user-guide.md) - General usage guide
- [Export Formats](export-formats.md) - Output format optimization
- [Configuration](configuration.md) - Performance-related settings
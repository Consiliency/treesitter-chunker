"""Benchmarks for batch processing performance."""

import time
import tempfile
import shutil
from pathlib import Path
from typing import List, Tuple
import statistics
from concurrent.futures import ProcessPoolExecutor

from chunker.performance.optimization.batch import BatchProcessor
from chunker.performance.optimization.memory_pool import MemoryPool
from chunker.performance.optimization.monitor import PerformanceMonitor
from chunker.chunker import chunk_file


def create_test_repository(num_files: int = 100, files_per_dir: int = 10) -> Path:
    """Create a test repository structure.
    
    Args:
        num_files: Total number of files
        files_per_dir: Files per directory
        
    Returns:
        Path to repository root
    """
    temp_dir = Path(tempfile.mkdtemp())
    
    # Create directory structure
    num_dirs = (num_files + files_per_dir - 1) // files_per_dir
    
    file_count = 0
    for dir_idx in range(num_dirs):
        dir_path = temp_dir / f"module_{dir_idx}"
        dir_path.mkdir()
        
        # Create __init__.py
        (dir_path / "__init__.py").write_text(f'"""Module {dir_idx}."""')
        
        # Create Python files
        for file_idx in range(min(files_per_dir, num_files - file_count)):
            file_path = dir_path / f"file_{file_idx}.py"
            
            # Vary file sizes
            if file_idx % 3 == 0:
                # Small file
                content = f'''
def small_function_{file_idx}():
    """A small function."""
    return {file_idx}
'''
            elif file_idx % 3 == 1:
                # Medium file
                content = f'''
"""Module with several functions."""

def function_one_{file_idx}(x, y):
    return x + y

def function_two_{file_idx}(items):
    return [x * 2 for x in items]

class MyClass_{file_idx}:
    def __init__(self):
        self.value = {file_idx}
    
    def method(self):
        return self.value * 2
'''
            else:
                # Larger file
                functions = []
                for i in range(10):
                    functions.append(f'''
def function_{i}_{file_idx}(param):
    """Function {i} in file {file_idx}."""
    result = param * {i}
    for j in range(10):
        result += j
    return result
''')
                content = '\n'.join(functions)
            
            file_path.write_text(content)
            file_count += 1
    
    # Create some JavaScript files too
    js_dir = temp_dir / "javascript"
    js_dir.mkdir()
    
    for i in range(min(10, num_files // 10)):
        js_file = js_dir / f"script_{i}.js"
        js_content = f'''
function jsFunction{i}(x, y) {{
    return x + y;
}}

class JsClass{i} {{
    constructor() {{
        this.value = {i};
    }}
    
    method() {{
        return this.value * 2;
    }}
}}

const arrow{i} = (x) => x * 2;
'''
        js_file.write_text(js_content)
    
    return temp_dir


def benchmark_batch_vs_sequential(num_files: int = 100):
    """Compare batch processing vs sequential processing."""
    print(f"\nBenchmarking batch vs sequential processing ({num_files} files)")
    print("=" * 70)
    
    repo_path = create_test_repository(num_files)
    
    try:
        # Get all Python files
        py_files = list(repo_path.rglob("*.py"))
        print(f"Found {len(py_files)} Python files")
        
        # Test 1: Sequential processing (baseline)
        print("\n1. Sequential processing:")
        start = time.perf_counter()
        
        sequential_results = {}
        for file_path in py_files:
            chunks = chunk_file(file_path, "python")
            sequential_results[str(file_path)] = chunks
        
        sequential_time = time.perf_counter() - start
        total_chunks = sum(len(chunks) for chunks in sequential_results.values())
        print(f"   Time: {sequential_time:.3f}s")
        print(f"   Total chunks: {total_chunks}")
        print(f"   Chunks/second: {total_chunks / sequential_time:.1f}")
        
        # Test 2: Batch processing (parallel)
        print("\n2. Batch processing (parallel):")
        processor = BatchProcessor(max_workers=4)
        
        # Add all files
        for file_path in py_files:
            processor.add_file(str(file_path))
        
        start = time.perf_counter()
        batch_results = processor.process_batch(batch_size=len(py_files), parallel=True)
        batch_time = time.perf_counter() - start
        
        total_chunks = sum(len(chunks) for chunks in batch_results.values())
        print(f"   Time: {batch_time:.3f}s")
        print(f"   Total chunks: {total_chunks}")
        print(f"   Chunks/second: {total_chunks / batch_time:.1f}")
        print(f"   Speedup: {sequential_time / batch_time:.2f}x")
        
        # Test 3: Batch processing with different batch sizes
        print("\n3. Batch size comparison:")
        batch_sizes = [10, 20, 50, 100]
        
        for batch_size in batch_sizes:
            if batch_size > len(py_files):
                continue
                
            processor = BatchProcessor(max_workers=4)
            for file_path in py_files:
                processor.add_file(str(file_path))
            
            start = time.perf_counter()
            results = {}
            
            while processor.pending_count() > 0:
                batch_results = processor.process_batch(batch_size=batch_size, parallel=True)
                results.update(batch_results)
            
            elapsed = time.perf_counter() - start
            print(f"   Batch size {batch_size}: {elapsed:.3f}s")
        
    finally:
        # Cleanup
        shutil.rmtree(repo_path)


def benchmark_memory_pool_efficiency():
    """Benchmark memory pool efficiency."""
    print("\nBenchmarking memory pool efficiency")
    print("=" * 70)
    
    repo_path = create_test_repository(50)
    
    try:
        py_files = list(repo_path.rglob("*.py"))[:20]  # Use subset
        
        # Test 1: Without memory pool
        print("\n1. Without memory pool:")
        processor1 = BatchProcessor(memory_pool=None, max_workers=1)
        
        for file_path in py_files:
            processor1.add_file(str(file_path))
        
        start = time.perf_counter()
        results1 = processor1.process_batch(batch_size=len(py_files), parallel=False)
        time1 = time.perf_counter() - start
        print(f"   Time: {time1:.3f}s")
        
        # Test 2: With memory pool
        print("\n2. With memory pool:")
        pool = MemoryPool(max_pool_size=10)
        pool.warm_up('parser:python', 5)  # Pre-create parsers
        
        processor2 = BatchProcessor(memory_pool=pool, max_workers=1)
        
        for file_path in py_files:
            processor2.add_file(str(file_path))
        
        start = time.perf_counter()
        results2 = processor2.process_batch(batch_size=len(py_files), parallel=False)
        time2 = time.perf_counter() - start
        print(f"   Time: {time2:.3f}s")
        print(f"   Speedup: {time1 / time2:.2f}x")
        
        # Show pool statistics
        pool_stats = pool.get_stats()
        print("\n3. Pool statistics:")
        for resource_type, stats in pool_stats.items():
            print(f"   {resource_type}:")
            print(f"     Created: {stats['created']}")
            print(f"     Acquired: {stats['acquired']}")
            print(f"     Released: {stats['released']}")
            print(f"     Pooled: {stats['pooled']}")
        
    finally:
        # Cleanup
        shutil.rmtree(repo_path)


def benchmark_priority_processing():
    """Benchmark priority-based file processing."""
    print("\nBenchmarking priority-based processing")
    print("=" * 70)
    
    repo_path = create_test_repository(50)
    
    try:
        py_files = list(repo_path.rglob("*.py"))
        
        # Create processor with monitoring
        monitor = PerformanceMonitor()
        processor = BatchProcessor(performance_monitor=monitor, max_workers=2)
        
        # Add files with different priorities
        # Higher priority for larger files
        for file_path in py_files:
            file_size = file_path.stat().st_size
            priority = file_size  # Larger files get higher priority
            processor.add_file(str(file_path), priority)
        
        print(f"\n1. Processing {len(py_files)} files with size-based priority")
        
        # Process in batches and track order
        processed_order = []
        batch_num = 0
        
        while processor.pending_count() > 0:
            batch_num += 1
            print(f"\n   Batch {batch_num}:")
            
            start = time.perf_counter()
            results = processor.process_batch(batch_size=10, parallel=True)
            elapsed = time.perf_counter() - start
            
            # Track processing order
            for file_path in results.keys():
                size = Path(file_path).stat().st_size
                processed_order.append((file_path, size))
            
            print(f"     Files: {len(results)}")
            print(f"     Time: {elapsed:.3f}s")
            print(f"     Avg file size: {sum(Path(f).stat().st_size for f in results) / len(results):.0f} bytes")
        
        # Verify priority ordering (first files should be larger)
        first_10_avg = sum(size for _, size in processed_order[:10]) / 10
        last_10_avg = sum(size for _, size in processed_order[-10:]) / 10
        
        print(f"\n2. Priority verification:")
        print(f"   First 10 files avg size: {first_10_avg:.0f} bytes")
        print(f"   Last 10 files avg size: {last_10_avg:.0f} bytes")
        print(f"   Priority working: {'✓' if first_10_avg > last_10_avg else '✗'}")
        
        # Show performance metrics
        print("\n3. Performance metrics:")
        metrics = monitor.get_metrics()
        
        if 'batch.file_size' in metrics:
            print(f"   Files processed: {metrics['batch.file_size']['count']}")
            print(f"   Avg file size: {metrics['batch.file_size']['mean']:.0f} bytes")
        
        if 'batch.chunk_count' in metrics:
            print(f"   Avg chunks per file: {metrics['batch.chunk_count']['mean']:.1f}")
        
    finally:
        # Cleanup
        shutil.rmtree(repo_path)


def benchmark_directory_processing():
    """Benchmark processing entire directories."""
    print("\nBenchmarking directory processing")
    print("=" * 70)
    
    repo_path = create_test_repository(100)
    
    try:
        processor = BatchProcessor(max_workers=4)
        
        # Test different patterns
        patterns = [
            ("All Python files", "**/*.py"),
            ("Top-level only", "*.py"),
            ("Specific module", "module_0/*.py")
        ]
        
        for desc, pattern in patterns:
            processor.clear_queue()
            processor.reset_processed()
            
            print(f"\n{desc} ({pattern}):")
            
            start = time.perf_counter()
            results = processor.process_directory(
                str(repo_path),
                pattern=pattern,
                recursive=True
            )
            elapsed = time.perf_counter() - start
            
            total_chunks = sum(len(chunks) for chunks in results.values())
            print(f"   Files: {len(results)}")
            print(f"   Chunks: {total_chunks}")
            print(f"   Time: {elapsed:.3f}s")
            print(f"   Files/second: {len(results) / elapsed:.1f}")
        
    finally:
        # Cleanup
        shutil.rmtree(repo_path)


if __name__ == "__main__":
    # Run benchmarks
    benchmark_batch_vs_sequential(num_files=100)
    benchmark_memory_pool_efficiency()
    benchmark_priority_processing()
    benchmark_directory_processing()
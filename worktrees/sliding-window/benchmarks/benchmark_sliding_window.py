"""Performance benchmarks for sliding window implementation."""

import time
import random
import string
from pathlib import Path
import tempfile
import statistics

from chunker.sliding_window import (
    DefaultSlidingWindowEngine,
    WindowConfig,
    WindowUnit,
    OverlapStrategy
)


def generate_text(size_mb: float) -> str:
    """Generate random text of specified size in MB."""
    size_bytes = int(size_mb * 1024 * 1024)
    
    # Mix of different content types
    words = ['the', 'quick', 'brown', 'fox', 'jumps', 'over', 'lazy', 'dog',
             'lorem', 'ipsum', 'dolor', 'sit', 'amet', 'consectetur', 'adipiscing']
    
    text_parts = []
    current_size = 0
    
    while current_size < size_bytes:
        # Randomly choose content type
        content_type = random.choice(['paragraph', 'short', 'code', 'list'])
        
        if content_type == 'paragraph':
            # Generate paragraph
            para = ' '.join(random.choice(words) for _ in range(50))
            para += '.\n\n'
            text_parts.append(para)
            current_size += len(para)
        
        elif content_type == 'short':
            # Short lines
            line = ' '.join(random.choice(words) for _ in range(5))
            line += '.\n'
            text_parts.append(line)
            current_size += len(line)
        
        elif content_type == 'code':
            # Code-like content
            code = f"def function_{random.randint(1, 100)}():\n"
            code += f"    return {random.randint(1, 100)}\n\n"
            text_parts.append(code)
            current_size += len(code)
        
        else:  # list
            # List items
            item = f"- {' '.join(random.choice(words) for _ in range(10))}\n"
            text_parts.append(item)
            current_size += len(item)
    
    return ''.join(text_parts)


def benchmark_window_generation(text: str, config: WindowConfig, name: str) -> dict:
    """Benchmark window generation performance."""
    engine = DefaultSlidingWindowEngine(config)
    
    # Warmup
    list(engine.process_text(text[:1000]))
    
    # Actual benchmark
    times = []
    window_counts = []
    
    for _ in range(3):  # 3 runs
        start = time.perf_counter()
        windows = list(engine.process_text(text))
        end = time.perf_counter()
        
        times.append(end - start)
        window_counts.append(len(windows))
    
    return {
        'name': name,
        'avg_time': statistics.mean(times),
        'min_time': min(times),
        'max_time': max(times),
        'window_count': window_counts[0],
        'throughput_mb_per_sec': len(text) / (1024 * 1024) / statistics.mean(times)
    }


def benchmark_file_processing(file_path: str, config: WindowConfig, name: str) -> dict:
    """Benchmark file processing performance."""
    engine = DefaultSlidingWindowEngine(config)
    
    times = []
    window_counts = []
    
    for _ in range(3):
        start = time.perf_counter()
        windows = list(engine.process_file(file_path))
        end = time.perf_counter()
        
        times.append(end - start)
        window_counts.append(len(windows))
    
    file_size_mb = Path(file_path).stat().st_size / (1024 * 1024)
    
    return {
        'name': name,
        'file_size_mb': file_size_mb,
        'avg_time': statistics.mean(times),
        'min_time': min(times),
        'max_time': max(times),
        'window_count': window_counts[0],
        'throughput_mb_per_sec': file_size_mb / statistics.mean(times)
    }


def benchmark_navigation(text: str, config: WindowConfig) -> dict:
    """Benchmark navigation operations."""
    from chunker.sliding_window import DefaultWindowNavigator
    
    engine = DefaultSlidingWindowEngine(config)
    navigator = DefaultWindowNavigator(engine, text)
    
    results = {}
    
    # Benchmark forward navigation
    start = time.perf_counter()
    count = 0
    while navigator.has_next():
        navigator.next_window()
        count += 1
    end = time.perf_counter()
    results['forward_navigation_time'] = end - start
    results['windows_navigated'] = count
    
    # Reset and benchmark jumping
    navigator.reset()
    jump_positions = [i * 10 for i in range(min(10, navigator.total_windows // 10))]
    
    start = time.perf_counter()
    for pos in jump_positions:
        navigator.jump_to_window(pos)
    end = time.perf_counter()
    results['jump_time'] = end - start
    results['jumps_performed'] = len(jump_positions)
    
    # Benchmark search
    search_terms = ['the', 'function', 'lorem']
    start = time.perf_counter()
    total_found = 0
    for term in search_terms:
        found = navigator.find_windows_containing(term)
        total_found += len(found)
    end = time.perf_counter()
    results['search_time'] = end - start
    results['total_matches'] = total_found
    
    return results


def run_benchmarks():
    """Run all benchmarks."""
    print("=== Sliding Window Performance Benchmarks ===\n")
    
    # Generate test data
    print("Generating test data...")
    small_text = generate_text(0.1)  # 100KB
    medium_text = generate_text(1.0)  # 1MB
    large_text = generate_text(5.0)  # 5MB
    
    print(f"Small text: {len(small_text) / 1024:.1f} KB")
    print(f"Medium text: {len(medium_text) / (1024 * 1024):.1f} MB")
    print(f"Large text: {len(large_text) / (1024 * 1024):.1f} MB")
    print()
    
    # Benchmark 1: Different window sizes
    print("Benchmark 1: Window Size Impact")
    print("-" * 50)
    
    window_sizes = [100, 500, 1000, 5000]
    for size in window_sizes:
        config = WindowConfig(size=size, unit=WindowUnit.CHARACTERS)
        result = benchmark_window_generation(medium_text, config, f"{size} chars")
        print(f"Window size {size}:")
        print(f"  Windows: {result['window_count']}")
        print(f"  Time: {result['avg_time']:.3f}s")
        print(f"  Throughput: {result['throughput_mb_per_sec']:.1f} MB/s")
    print()
    
    # Benchmark 2: Different overlap strategies
    print("Benchmark 2: Overlap Strategy Impact")
    print("-" * 50)
    
    overlap_configs = [
        (WindowConfig(size=1000, overlap=0), "No overlap"),
        (WindowConfig(size=1000, overlap=100, overlap_strategy=OverlapStrategy.FIXED), "Fixed 100"),
        (WindowConfig(size=1000, overlap=10, overlap_strategy=OverlapStrategy.PERCENTAGE), "10% overlap"),
        (WindowConfig(size=1000, overlap_strategy=OverlapStrategy.SEMANTIC), "Semantic overlap"),
    ]
    
    for config, name in overlap_configs:
        result = benchmark_window_generation(medium_text, config, name)
        print(f"{name}:")
        print(f"  Windows: {result['window_count']}")
        print(f"  Time: {result['avg_time']:.3f}s")
        print(f"  Throughput: {result['throughput_mb_per_sec']:.1f} MB/s")
    print()
    
    # Benchmark 3: Different units
    print("Benchmark 3: Unit Type Impact")
    print("-" * 50)
    
    unit_configs = [
        (WindowConfig(size=1000, unit=WindowUnit.CHARACTERS), "Characters"),
        (WindowConfig(size=50, unit=WindowUnit.LINES), "Lines"),
        (WindowConfig(size=1000, unit=WindowUnit.BYTES), "Bytes"),
    ]
    
    for config, name in unit_configs:
        result = benchmark_window_generation(medium_text, config, name)
        print(f"{name}:")
        print(f"  Windows: {result['window_count']}")
        print(f"  Time: {result['avg_time']:.3f}s")
        print(f"  Throughput: {result['throughput_mb_per_sec']:.1f} MB/s")
    print()
    
    # Benchmark 4: Boundary preservation
    print("Benchmark 4: Boundary Preservation Impact")
    print("-" * 50)
    
    boundary_configs = [
        (WindowConfig(size=1000, preserve_boundaries=False), "No preservation"),
        (WindowConfig(size=1000, preserve_boundaries=True), "With preservation"),
    ]
    
    for config, name in boundary_configs:
        result = benchmark_window_generation(medium_text, config, name)
        print(f"{name}:")
        print(f"  Time: {result['avg_time']:.3f}s")
        print(f"  Throughput: {result['throughput_mb_per_sec']:.1f} MB/s")
    print()
    
    # Benchmark 5: File processing
    print("Benchmark 5: File Processing (Streaming)")
    print("-" * 50)
    
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
        f.write(large_text)
        temp_path = f.name
    
    try:
        config = WindowConfig(size=5000)
        result = benchmark_file_processing(temp_path, config, "5MB file streaming")
        print(f"File size: {result['file_size_mb']:.1f} MB")
        print(f"Windows: {result['window_count']}")
        print(f"Time: {result['avg_time']:.3f}s")
        print(f"Throughput: {result['throughput_mb_per_sec']:.1f} MB/s")
    finally:
        Path(temp_path).unlink()
    print()
    
    # Benchmark 6: Navigation
    print("Benchmark 6: Navigation Performance")
    print("-" * 50)
    
    config = WindowConfig(size=1000)
    nav_results = benchmark_navigation(medium_text, config)
    
    print(f"Forward navigation:")
    print(f"  Windows: {nav_results['windows_navigated']}")
    print(f"  Time: {nav_results['forward_navigation_time']:.3f}s")
    print(f"  Speed: {nav_results['windows_navigated'] / nav_results['forward_navigation_time']:.0f} windows/s")
    
    print(f"Jump operations:")
    print(f"  Jumps: {nav_results['jumps_performed']}")
    print(f"  Time: {nav_results['jump_time']:.3f}s")
    
    print(f"Search operations:")
    print(f"  Matches: {nav_results['total_matches']}")
    print(f"  Time: {nav_results['search_time']:.3f}s")
    print()
    
    # Benchmark 7: Scalability
    print("Benchmark 7: Scalability")
    print("-" * 50)
    
    config = WindowConfig(size=1000, overlap=100)
    
    for text, name in [(small_text, "Small"), (medium_text, "Medium"), (large_text, "Large")]:
        result = benchmark_window_generation(text, config, name)
        print(f"{name} ({len(text) / (1024 * 1024):.1f} MB):")
        print(f"  Windows: {result['window_count']}")
        print(f"  Time: {result['avg_time']:.3f}s")
        print(f"  Throughput: {result['throughput_mb_per_sec']:.1f} MB/s")
    
    print("\n=== Benchmark Complete ===")


if __name__ == "__main__":
    run_benchmarks()
from __future__ import annotations
import time
import statistics
from pathlib import Path
from typing import List, Dict, Any, Callable
from dataclasses import dataclass, field
import json
from datetime import datetime

from chunker import chunk_file
from chunker.streaming import chunk_file_streaming
from chunker.parallel import chunk_files_parallel
from chunker.cache import ASTCache

@dataclass
class BenchmarkResult:
    """Store results from a single benchmark run."""
    name: str
    duration: float
    memory_used: int = 0
    chunks_processed: int = 0
    files_processed: int = 0
    cache_hits: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class BenchmarkSuite:
    """Collection of benchmark results."""
    name: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    results: List[BenchmarkResult] = field(default_factory=list)
    
    def add_result(self, result: BenchmarkResult):
        self.results.append(result)
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary statistics for all benchmarks."""
        if not self.results:
            return {}
        
        durations = [r.duration for r in self.results]
        return {
            "suite_name": self.name,
            "timestamp": self.timestamp,
            "total_benchmarks": len(self.results),
            "total_duration": sum(durations),
            "avg_duration": statistics.mean(durations),
            "min_duration": min(durations),
            "max_duration": max(durations),
            "std_dev": statistics.stdev(durations) if len(durations) > 1 else 0,
            "total_chunks": sum(r.chunks_processed for r in self.results),
            "total_files": sum(r.files_processed for r in self.results),
        }
    
    def to_json(self) -> str:
        """Export results as JSON."""
        data = {
            "suite": self.get_summary(),
            "results": [
                {
                    "name": r.name,
                    "duration": r.duration,
                    "memory_used": r.memory_used,
                    "chunks_processed": r.chunks_processed,
                    "files_processed": r.files_processed,
                    "cache_hits": r.cache_hits,
                    "metadata": r.metadata,
                }
                for r in self.results
            ]
        }
        return json.dumps(data, indent=2)

class PerformanceBenchmark:
    """Run performance benchmarks for different chunking strategies."""
    
    def __init__(self, test_files: List[Path], language: str):
        self.test_files = test_files
        self.language = language
        self.cache = ASTCache()
    
    def _measure_time(self, func: Callable, *args, **kwargs) -> tuple[float, Any]:
        """Measure execution time of a function."""
        start = time.perf_counter()
        result = func(*args, **kwargs)
        duration = time.perf_counter() - start
        return duration, result
    
    def benchmark_basic_chunking(self) -> BenchmarkResult:
        """Benchmark basic chunking without optimizations."""
        total_chunks = 0
        duration = 0
        
        for file_path in self.test_files:
            file_duration, chunks = self._measure_time(
                chunk_file, file_path, self.language, use_cache=False
            )
            duration += file_duration
            total_chunks += len(chunks)
        
        return BenchmarkResult(
            name="Basic Chunking",
            duration=duration,
            chunks_processed=total_chunks,
            files_processed=len(self.test_files),
            metadata={"method": "sequential", "cache": False, "streaming": False}
        )
    
    def benchmark_streaming_chunking(self) -> BenchmarkResult:
        """Benchmark streaming chunking."""
        total_chunks = 0
        duration = 0
        
        for file_path in self.test_files:
            file_duration, chunks = self._measure_time(
                lambda: list(chunk_file_streaming(file_path, self.language))
            )
            duration += file_duration
            total_chunks += len(chunks)
        
        return BenchmarkResult(
            name="Streaming Chunking",
            duration=duration,
            chunks_processed=total_chunks,
            files_processed=len(self.test_files),
            metadata={"method": "streaming", "cache": False, "streaming": True}
        )
    
    def benchmark_cached_chunking(self) -> BenchmarkResult:
        """Benchmark chunking with cache (cold and warm)."""
        # Clear cache first
        for file in self.test_files:
            self.cache.invalidate_cache(file)
        
        # Cold cache run
        cold_duration = 0
        total_chunks = 0
        for file_path in self.test_files:
            file_duration, chunks = self._measure_time(
                chunk_file, file_path, self.language, use_cache=True
            )
            cold_duration += file_duration
            total_chunks += len(chunks)
        
        # Warm cache run
        cache_hits = 0
        warm_duration = 0
        for file_path in self.test_files:
            file_duration, chunks = self._measure_time(
                chunk_file, file_path, self.language, use_cache=True
            )
            warm_duration += file_duration
            if self.cache.get_cached_chunks(file_path, self.language) is not None:
                cache_hits += 1
        
        return BenchmarkResult(
            name="Cached Chunking",
            duration=warm_duration,
            chunks_processed=total_chunks,
            files_processed=len(self.test_files),
            cache_hits=cache_hits,
            metadata={
                "method": "cached",
                "cache": True,
                "streaming": False,
                "cold_cache_duration": cold_duration,
                "warm_cache_duration": warm_duration,
                "speedup": cold_duration / warm_duration if warm_duration > 0 else 0
            }
        )
    
    def benchmark_parallel_chunking(self, num_workers: int = 4) -> BenchmarkResult:
        """Benchmark parallel chunking."""
        duration, results = self._measure_time(
            chunk_files_parallel,
            self.test_files,
            self.language,
            num_workers=num_workers,
            use_cache=False,
            use_streaming=False
        )
        
        total_chunks = sum(len(chunks) for chunks in results.values())
        
        return BenchmarkResult(
            name=f"Parallel Chunking ({num_workers} workers)",
            duration=duration,
            chunks_processed=total_chunks,
            files_processed=len(results),
            metadata={
                "method": "parallel",
                "cache": False,
                "streaming": False,
                "num_workers": num_workers
            }
        )
    
    def benchmark_parallel_streaming(self, num_workers: int = 4) -> BenchmarkResult:
        """Benchmark parallel chunking with streaming."""
        duration, results = self._measure_time(
            chunk_files_parallel,
            self.test_files,
            self.language,
            num_workers=num_workers,
            use_cache=False,
            use_streaming=True
        )
        
        total_chunks = sum(len(chunks) for chunks in results.values())
        
        return BenchmarkResult(
            name=f"Parallel Streaming ({num_workers} workers)",
            duration=duration,
            chunks_processed=total_chunks,
            files_processed=len(results),
            metadata={
                "method": "parallel",
                "cache": False,
                "streaming": True,
                "num_workers": num_workers
            }
        )
    
    def run_all_benchmarks(self) -> BenchmarkSuite:
        """Run all benchmarks and return results."""
        suite = BenchmarkSuite(name="Chunker Performance Benchmarks")
        
        print("Running benchmarks...")
        
        # Basic chunking
        print("  - Basic chunking...")
        suite.add_result(self.benchmark_basic_chunking())
        
        # Streaming
        print("  - Streaming chunking...")
        suite.add_result(self.benchmark_streaming_chunking())
        
        # Cached
        print("  - Cached chunking...")
        suite.add_result(self.benchmark_cached_chunking())
        
        # Parallel
        for workers in [2, 4, 8]:
            print(f"  - Parallel chunking ({workers} workers)...")
            suite.add_result(self.benchmark_parallel_chunking(workers))
        
        # Parallel streaming
        print("  - Parallel streaming (4 workers)...")
        suite.add_result(self.benchmark_parallel_streaming(4))
        
        return suite


def run_benchmarks(directory: Path, language: str, 
                  extensions: List[str] = None) -> BenchmarkSuite:
    """Run benchmarks on all files in a directory."""
    if extensions is None:
        ext_map = {
            "python": [".py"],
            "rust": [".rs"],
            "javascript": [".js"],
            "c": [".c", ".h"],
            "cpp": [".cpp", ".hpp"],
        }
        extensions = ext_map.get(language, [".py"])
    
    # Find test files
    test_files = []
    for ext in extensions:
        test_files.extend(directory.rglob(f"*{ext}"))
    
    if not test_files:
        raise ValueError(f"No files found with extensions {extensions} in {directory}")
    
    print(f"Found {len(test_files)} files to benchmark")
    
    benchmark = PerformanceBenchmark(test_files[:20], language)  # Limit to 20 files for quick benchmarks
    return benchmark.run_all_benchmarks()
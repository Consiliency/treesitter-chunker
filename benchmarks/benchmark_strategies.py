"""Benchmark different chunking strategies."""

import time
import statistics
from pathlib import Path
from typing import Dict, List, Any

from chunker.parser import get_parser
from chunker.strategies import (
    SemanticChunker,
    HierarchicalChunker,
    AdaptiveChunker,
    CompositeChunker
)
from chunker.config import get_profile, ChunkingProfile


def benchmark_strategy(strategy, ast, source, file_path, language, runs=5):
    """Benchmark a single strategy."""
    times = []
    chunk_counts = []
    
    for _ in range(runs):
        start = time.time()
        chunks = strategy.chunk(ast, source, file_path, language)
        end = time.time()
        
        times.append(end - start)
        chunk_counts.append(len(chunks))
    
    return {
        'mean_time': statistics.mean(times),
        'std_time': statistics.stdev(times) if len(times) > 1 else 0,
        'min_time': min(times),
        'max_time': max(times),
        'mean_chunks': statistics.mean(chunk_counts),
        'total_runs': runs
    }


def analyze_chunk_quality(chunks: List[Any]) -> Dict[str, Any]:
    """Analyze the quality of chunks produced."""
    if not chunks:
        return {
            'count': 0,
            'avg_size': 0,
            'size_variance': 0,
            'metadata_completeness': 0
        }
    
    sizes = [c.end_line - c.start_line + 1 for c in chunks]
    
    metadata_scores = []
    for chunk in chunks:
        score = 0
        if hasattr(chunk, 'metadata') and chunk.metadata:
            score = len(chunk.metadata) / 10  # Normalize to 0-1
        metadata_scores.append(min(1.0, score))
    
    return {
        'count': len(chunks),
        'avg_size': statistics.mean(sizes),
        'size_variance': statistics.variance(sizes) if len(sizes) > 1 else 0,
        'min_size': min(sizes),
        'max_size': max(sizes),
        'metadata_completeness': statistics.mean(metadata_scores)
    }


def run_benchmarks():
    """Run benchmarks on different strategies."""
    # Sample code for benchmarking
    test_file = Path(__file__).parent.parent / "examples" / "example.py"
    
    if not test_file.exists():
        # Use inline sample if file doesn't exist
        sample_code = '''
# Sample code for benchmarking
import os
import sys
from typing import List, Dict, Optional

class BenchmarkClass:
    def __init__(self, config: Dict):
        self.config = config
        self.data = []
    
    def process(self, items: List[str]) -> List[Dict]:
        results = []
        for item in items:
            if self.validate(item):
                results.append(self.transform(item))
        return results
    
    def validate(self, item: str) -> bool:
        return len(item) > 0 and item.isalnum()
    
    def transform(self, item: str) -> Dict:
        return {
            'original': item,
            'processed': item.upper(),
            'length': len(item)
        }

def complex_function(data: List[int], threshold: int = 10) -> Dict[str, Any]:
    """Complex function with multiple branches."""
    results = {'positive': [], 'negative': [], 'zero': []}
    
    for value in data:
        if value > threshold:
            results['positive'].append(value * 2)
        elif value < -threshold:
            results['negative'].append(abs(value))
        elif value == 0:
            results['zero'].append(0)
        else:
            # Small values
            if value > 0:
                results['positive'].append(value)
            else:
                results['negative'].append(value)
    
    return results
'''
        source = sample_code.encode()
        file_path = "benchmark_sample.py"
    else:
        source = test_file.read_bytes()
        file_path = str(test_file)
    
    # Parse the code
    language = "python"
    parser = get_parser(language)
    tree = parser.parse(source)
    
    # Initialize strategies
    strategies = {
        'Semantic': SemanticChunker(),
        'Hierarchical': HierarchicalChunker(),
        'Adaptive': AdaptiveChunker(),
        'Composite': CompositeChunker()
    }
    
    # Run benchmarks
    print("=== Chunking Strategy Benchmarks ===\n")
    print(f"File: {file_path}")
    print(f"Size: {len(source)} bytes, {len(source.decode().splitlines())} lines\n")
    
    results = {}
    
    for name, strategy in strategies.items():
        print(f"\nBenchmarking {name} Chunker...")
        
        # Run benchmark
        perf = benchmark_strategy(strategy, tree.root_node, source, file_path, language)
        
        # Get one set of chunks for quality analysis
        chunks = strategy.chunk(tree.root_node, source, file_path, language)
        quality = analyze_chunk_quality(chunks)
        
        results[name] = {
            'performance': perf,
            'quality': quality
        }
        
        # Print results
        print(f"  Performance:")
        print(f"    Mean time: {perf['mean_time']*1000:.2f}ms (±{perf['std_time']*1000:.2f}ms)")
        print(f"    Range: {perf['min_time']*1000:.2f}ms - {perf['max_time']*1000:.2f}ms")
        print(f"  Chunks:")
        print(f"    Count: {quality['count']}")
        print(f"    Avg size: {quality['avg_size']:.1f} lines")
        print(f"    Size range: {quality['min_size']} - {quality['max_size']} lines")
        print(f"    Metadata completeness: {quality['metadata_completeness']:.0%}")
    
    # Compare strategies
    print("\n=== Strategy Comparison ===\n")
    
    # Speed comparison
    print("Speed Ranking (fastest to slowest):")
    speed_ranking = sorted(results.items(), key=lambda x: x[1]['performance']['mean_time'])
    for i, (name, data) in enumerate(speed_ranking, 1):
        time_ms = data['performance']['mean_time'] * 1000
        print(f"  {i}. {name}: {time_ms:.2f}ms")
    
    # Chunk granularity comparison
    print("\nChunk Granularity (most to least chunks):")
    chunk_ranking = sorted(results.items(), key=lambda x: x[1]['quality']['count'], reverse=True)
    for i, (name, data) in enumerate(chunk_ranking, 1):
        count = data['quality']['count']
        avg_size = data['quality']['avg_size']
        print(f"  {i}. {name}: {count} chunks (avg {avg_size:.1f} lines)")
    
    # Test with profiles
    print("\n=== Profile-based Chunking ===\n")
    
    profiles_to_test = ['documentation', 'code_review', 'embedding_generation']
    
    for profile_name in profiles_to_test:
        profile = get_profile(profile_name)
        if profile:
            print(f"\nProfile: {profile_name}")
            print(f"Description: {profile.description}")
            
            # Create composite chunker with profile config
            chunker = CompositeChunker()
            chunker.configure(profile.config.composite)
            
            # Benchmark
            start = time.time()
            chunks = chunker.chunk(tree.root_node, source, file_path, language)
            elapsed = time.time() - start
            
            quality = analyze_chunk_quality(chunks)
            
            print(f"  Time: {elapsed*1000:.2f}ms")
            print(f"  Chunks: {quality['count']} (avg {quality['avg_size']:.1f} lines)")
            print(f"  Use cases: {', '.join(profile.use_cases[:2])}")


if __name__ == "__main__":
    run_benchmarks()
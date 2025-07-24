"""Example of chunk optimization for different use cases."""

from chunker import ChunkOptimizer, OptimizationConfig, OptimizationStrategy, chunk_file


def demonstrate_optimization():
    """Demonstrate chunk optimization features."""

    # 1. Get initial chunks from a file
    print("1. Getting initial chunks from a Python file...")
    chunks = chunk_file("examples/sample_code.py", language="python")
    print(f"   Original chunks: {len(chunks)}")

    # 2. Create optimizer with default config
    optimizer = ChunkOptimizer()

    # 3. Optimize for different LLM models
    print("\n2. Optimizing for GPT-4 (8k context)...")
    optimized_gpt4, metrics_gpt4 = optimizer.optimize_for_llm(
        chunks,
        model="gpt-4",
        max_tokens=2000,  # Leave room for prompts
        strategy=OptimizationStrategy.BALANCED,
    )
    print(f"   Optimized chunks: {metrics_gpt4.optimized_count}")
    print(f"   Average tokens: {metrics_gpt4.avg_tokens_after:.1f}")
    print(f"   Coherence score: {metrics_gpt4.coherence_score:.2f}")
    print(f"   Token efficiency: {metrics_gpt4.token_efficiency:.2%}")

    # 4. Optimize for Claude (100k context)
    print("\n3. Optimizing for Claude (100k context)...")
    optimized_claude, metrics_claude = optimizer.optimize_for_llm(
        chunks,
        model="claude",
        max_tokens=8000,  # Can use larger chunks
        strategy=OptimizationStrategy.AGGRESSIVE,
    )
    print(f"   Optimized chunks: {metrics_claude.optimized_count}")
    print(f"   Average tokens: {metrics_claude.avg_tokens_after:.1f}")

    # 5. Optimize for embeddings
    print("\n4. Optimizing for embeddings...")
    embedding_chunks = optimizer.optimize_for_embedding(
        chunks,
        embedding_model="text-embedding-ada-002",
        max_tokens=512,
    )
    print(f"   Embedding chunks: {len(embedding_chunks)}")

    # 6. Custom configuration
    print("\n5. Using custom configuration...")
    config = OptimizationConfig()
    config.min_chunk_tokens = 100
    config.max_chunk_tokens = 1500
    config.target_chunk_tokens = 750
    config.merge_threshold = 0.8

    custom_optimizer = ChunkOptimizer(config)

    # Rebalance chunks for uniform sizing
    rebalanced = custom_optimizer.rebalance_chunks(
        chunks,
        target_tokens=750,
        variance=0.2,
    )
    print(f"   Rebalanced chunks: {len(rebalanced)}")

    # 7. Preserve structure strategy
    print("\n6. Using PRESERVE_STRUCTURE strategy...")
    preserved, metrics_preserved = optimizer.optimize_for_llm(
        chunks,
        model="gpt-4",
        max_tokens=1000,
        strategy=OptimizationStrategy.PRESERVE_STRUCTURE,
    )
    print(f"   Preserved chunks: {metrics_preserved.optimized_count}")
    print(
        f"   Structure maintained: {metrics_preserved.optimized_count == len(chunks)}",
    )

    # 8. Show chunk boundaries analysis
    print("\n7. Analyzing chunk boundaries...")
    from chunker import ChunkBoundaryAnalyzer

    analyzer = ChunkBoundaryAnalyzer()

    # Find merge suggestions
    merge_suggestions = analyzer.suggest_merge_points(chunks[:5])  # First 5 chunks
    print(f"   Merge suggestions: {len(merge_suggestions)}")
    for i, (idx1, idx2, score) in enumerate(merge_suggestions[:3]):
        print(f"   - Merge chunks {idx1} and {idx2} (score: {score:.2f})")


def create_sample_code():
    """Create a sample code file for demonstration."""
    sample_code = '''"""Sample Python module for chunk optimization demo."""

import os
import sys
from typing import List, Dict, Optional


class DataProcessor:
    """Processes data with various methods."""
    
    def __init__(self, config: Dict[str, any]):
        self.config = config
        self.data = []
        self.results = {}
    
    def load_data(self, filepath: str) -> bool:
        """Load data from file."""
        try:
            with open(filepath, 'r') as f:
                self.data = f.readlines()
            return True
        except Exception as e:
            print(f"Error loading data: {e}")
            return False
    
    def process_batch(self, batch_size: int = 100) -> List[Dict]:
        """Process data in batches."""
        results = []
        for i in range(0, len(self.data), batch_size):
            batch = self.data[i:i + batch_size]
            processed = self._process_single_batch(batch)
            results.extend(processed)
        return results
    
    def _process_single_batch(self, batch: List[str]) -> List[Dict]:
        """Process a single batch of data."""
        processed = []
        for item in batch:
            # Complex processing logic here
            result = {
                'original': item,
                'processed': item.strip().upper(),
                'length': len(item)
            }
            processed.append(result)
        return processed
    
    def save_results(self, output_path: str) -> bool:
        """Save processing results."""
        try:
            with open(output_path, 'w') as f:
                for result in self.results:
                    f.write(str(result) + '\\n')
            return True
        except Exception as e:
            print(f"Error saving results: {e}")
            return False


def analyze_text(text: str) -> Dict[str, int]:
    """Analyze text and return statistics."""
    words = text.split()
    lines = text.split('\\n')
    
    stats = {
        'characters': len(text),
        'words': len(words),
        'lines': len(lines),
        'avg_word_length': sum(len(w) for w in words) / len(words) if words else 0
    }
    
    return stats


def main():
    """Main entry point."""
    processor = DataProcessor({'debug': True})
    
    if processor.load_data('input.txt'):
        results = processor.process_batch(50)
        processor.results = results
        processor.save_results('output.txt')
        
        # Analyze results
        for result in results[:10]:
            stats = analyze_text(result['processed'])
            print(f"Stats: {stats}")


if __name__ == '__main__':
    main()
'''

    with open("examples/sample_code.py", "w") as f:
        f.write(sample_code)
    print("Created examples/sample_code.py")


if __name__ == "__main__":
    # Create sample file if it doesn't exist
    import os

    if not os.path.exists("examples/sample_code.py"):
        os.makedirs("examples", exist_ok=True)
        create_sample_code()

    demonstrate_optimization()

# Chunk Optimization

The chunk optimization feature allows you to adapt code chunks to specific use cases and model constraints, ensuring chunks fit within token limits while maintaining semantic coherence.

## Overview

The optimization module provides:

- **ChunkOptimizer**: Main class for optimizing chunks
- **ChunkBoundaryAnalyzer**: Analyzes code to find optimal split/merge points
- **Multiple optimization strategies**: AGGRESSIVE, BALANCED, CONSERVATIVE, PRESERVE_STRUCTURE
- **Model-specific optimization**: Optimize for different LLMs and embedding models
- **Token-aware processing**: Uses tiktoken for accurate token counting

## Usage

### Basic Optimization

```python
from chunker import chunk_file, ChunkOptimizer, OptimizationStrategy

# Get initial chunks
chunks = chunk_file("example.py", language="python")

# Create optimizer
optimizer = ChunkOptimizer()

# Optimize for GPT-4
optimized_chunks, metrics = optimizer.optimize_for_llm(
    chunks,
    model="gpt-4",
    max_tokens=2000,
    strategy=OptimizationStrategy.BALANCED
)

print(f"Original chunks: {metrics.original_count}")
print(f"Optimized chunks: {metrics.optimized_count}")
print(f"Average tokens: {metrics.avg_tokens_after:.1f}")
print(f"Coherence score: {metrics.coherence_score:.2f}")
```

### Optimization Strategies

1. **AGGRESSIVE**: Maximizes merging and splitting to fit token limits
2. **BALANCED**: Smart merging/splitting while preserving code structure
3. **CONSERVATIVE**: Minimal changes, only splits oversized chunks
4. **PRESERVE_STRUCTURE**: Maintains original structure, splits only when necessary

### Specific Operations

#### Merge Small Chunks

```python
# Merge chunks smaller than 100 tokens
merged = optimizer.merge_small_chunks(chunks, min_tokens=100)
```

#### Split Large Chunks

```python
# Split chunks larger than 1000 tokens
split = optimizer.split_large_chunks(chunks, max_tokens=1000)
```

#### Rebalance Chunks

```python
# Create uniformly sized chunks around 500 tokens (±20%)
balanced = optimizer.rebalance_chunks(
    chunks, 
    target_tokens=500,
    variance=0.2
)
```

#### Optimize for Embeddings

```python
# Optimize for embedding models (typically smaller token limits)
embedding_chunks = optimizer.optimize_for_embedding(
    chunks,
    embedding_model="text-embedding-ada-002",
    max_tokens=512
)
```

## Configuration

```python
from chunker import OptimizationConfig

config = OptimizationConfig()
config.min_chunk_tokens = 100
config.max_chunk_tokens = 2000
config.target_chunk_tokens = 750
config.merge_threshold = 0.8

optimizer = ChunkOptimizer(config)
```

## Boundary Analysis

The ChunkBoundaryAnalyzer finds natural split points in code:

```python
from chunker import ChunkBoundaryAnalyzer

analyzer = ChunkBoundaryAnalyzer()

# Find natural boundaries
boundaries = analyzer.find_natural_boundaries(code_content, "python")

# Score a specific boundary
score = analyzer.score_boundary(code_content, position, "python")

# Get merge suggestions
suggestions = analyzer.suggest_merge_points(chunks)
```

## Supported Models

The optimizer includes token limits for:
- GPT-4 (8k, 32k, turbo variants)
- GPT-3.5-turbo
- Claude (100k, 200k contexts)
- LLaMA variants
- Embedding models (ada-002, etc.)

## Integration with Phase 9

The optimization feature integrates with Phase 9's token counting:
- Uses TiktokenCounter for accurate token measurements
- Supports multiple tokenizer models
- Handles token-based splitting intelligently

## Performance Considerations

- Optimization operations are computationally lightweight
- Token counting is cached for efficiency
- Boundary analysis uses regex patterns optimized for each language
- Merge/split operations preserve chunk metadata and relationships
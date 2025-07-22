# Smart Context Provider

The Smart Context Provider is a Phase 10 feature that intelligently selects related code chunks to provide optimal context for LLM processing. It analyzes semantic meaning, dependencies, usage patterns, and structural relationships to build comprehensive context.

## Overview

The Smart Context Provider helps LLMs better understand code by providing relevant context beyond just the immediate chunk being processed. It uses multiple analysis techniques to identify and rank related code based on:

- **Semantic Similarity**: Code with similar functionality or purpose
- **Dependencies**: Code that the current chunk depends on (imports, function calls, etc.)
- **Usages**: Code that uses or references the current chunk
- **Structural Relationships**: Parent classes, sibling methods, nested functions, etc.

## Key Components

### SmartContextProvider

The main interface that provides four types of context extraction:

```python
from chunker import TreeSitterSmartContextProvider, CodeChunk

provider = TreeSitterSmartContextProvider()

# Get semantically similar code
context_str, metadata = provider.get_semantic_context(chunk, max_tokens=2000)

# Get dependencies
dependencies = provider.get_dependency_context(chunk, all_chunks)

# Get usages
usages = provider.get_usage_context(chunk, all_chunks)

# Get structural relations
structural = provider.get_structural_context(chunk, all_chunks)
```

### Context Strategies

Strategies for selecting the most relevant context within token limits:

```python
from chunker import RelevanceContextStrategy, HybridContextStrategy

# Relevance-based selection (prioritizes highest scores)
relevance_strategy = RelevanceContextStrategy()
selected = relevance_strategy.select_context(chunk, candidates, max_tokens=1000)

# Hybrid selection (balances different context types)
hybrid_strategy = HybridContextStrategy(weights={
    'dependency': 0.4,
    'semantic': 0.3,
    'usage': 0.2,
    'structural': 0.1
})
selected = hybrid_strategy.select_context(chunk, candidates, max_tokens=1000)
```

### Context Cache

Caching system for expensive context computations:

```python
from chunker import InMemoryContextCache

# Create cache with 1-hour TTL
cache = InMemoryContextCache(ttl=3600)

# Use with provider
provider = TreeSitterSmartContextProvider(cache=cache)

# Manual cache operations
cache.set(chunk_id, 'dependency', context_data)
cached = cache.get(chunk_id, 'dependency')
cache.invalidate({chunk_id})  # Invalidate specific chunks
cache.invalidate()  # Clear all
```

## Usage Examples

### Basic Context Extraction

```python
from chunker import chunk_file, TreeSitterSmartContextProvider

# Get chunks from a file
chunks = chunk_file("app.py", "python")

# Create provider
provider = TreeSitterSmartContextProvider()

# Analyze a specific chunk
target_chunk = chunks[0]

# Get semantic context
context, metadata = provider.get_semantic_context(target_chunk)
print(f"Semantic context (relevance: {metadata.relevance_score:.2f}):")
print(context)

# Get all dependencies
deps = provider.get_dependency_context(target_chunk, chunks)
for dep_chunk, dep_meta in deps:
    print(f"Depends on: {dep_chunk.node_type} ({dep_meta.relevance_score:.2f})")
```

### Building Comprehensive Context

```python
# Collect all types of context
dependencies = provider.get_dependency_context(chunk, chunks)
usages = provider.get_usage_context(chunk, chunks)
structural = provider.get_structural_context(chunk, chunks)

# Combine all candidates
all_candidates = dependencies + usages + structural

# Use strategy to select within token budget
strategy = RelevanceContextStrategy()
selected_chunks = strategy.select_context(chunk, all_candidates, max_tokens=2000)

# Build context string
context_parts = [chunk.content for chunk in selected_chunks]
full_context = "\n\n".join(context_parts)
```

### Custom Context Strategy

```python
from chunker import ContextStrategy, ContextMetadata
from typing import List, Tuple

class CustomStrategy(ContextStrategy):
    def select_context(self, chunk: CodeChunk, 
                      candidates: List[Tuple[CodeChunk, ContextMetadata]], 
                      max_tokens: int) -> List[CodeChunk]:
        # Custom selection logic
        # For example, prioritize dependencies and nearby code
        selected = []
        tokens_used = 0
        
        # First add all direct dependencies
        for cand_chunk, metadata in candidates:
            if metadata.relationship_type == 'dependency' and metadata.relevance_score > 0.8:
                selected.append(cand_chunk)
                tokens_used += metadata.token_count
                
        # Then add nearby structural relations
        for cand_chunk, metadata in candidates:
            if metadata.relationship_type == 'structural' and metadata.distance < 50:
                if tokens_used + metadata.token_count <= max_tokens:
                    selected.append(cand_chunk)
                    tokens_used += metadata.token_count
                    
        return selected
    
    def rank_candidates(self, chunk: CodeChunk, 
                       candidates: List[Tuple[CodeChunk, ContextMetadata]]) -> List[Tuple[CodeChunk, float]]:
        # Custom ranking logic
        ranked = []
        for cand_chunk, metadata in candidates:
            score = metadata.relevance_score
            
            # Boost dependencies
            if metadata.relationship_type == 'dependency':
                score *= 1.5
                
            # Penalize distant code
            if metadata.distance > 100:
                score *= 0.5
                
            ranked.append((cand_chunk, score))
            
        return sorted(ranked, key=lambda x: x[1], reverse=True)
```

## Integration with LLM Processing

```python
def process_with_context(chunk: CodeChunk, all_chunks: List[CodeChunk], 
                        llm_client, max_context_tokens: int = 2000):
    """Process a chunk with smart context."""
    provider = TreeSitterSmartContextProvider()
    strategy = HybridContextStrategy()
    
    # Gather all context
    deps = provider.get_dependency_context(chunk, all_chunks)
    usages = provider.get_usage_context(chunk, all_chunks)
    structural = provider.get_structural_context(chunk, all_chunks)
    
    # Select most relevant
    all_candidates = deps + usages + structural
    selected = strategy.select_context(chunk, all_candidates, max_context_tokens)
    
    # Build prompt with context
    context_str = "\n\n".join([
        f"# {c.node_type} from {c.file_path} (lines {c.start_line}-{c.end_line}):\n{c.content}"
        for c in selected
    ])
    
    prompt = f"""Given the following context:

{context_str}

Analyze this code chunk:

{chunk.content}

[Your analysis request here]"""
    
    # Send to LLM
    response = llm_client.complete(prompt)
    return response
```

## Performance Considerations

1. **Use Caching**: The provider supports caching to avoid recomputing context for the same chunks
2. **Batch Processing**: When processing multiple chunks, gather all chunks first then analyze
3. **Token Budgets**: Set reasonable token limits to avoid overwhelming the LLM
4. **Strategy Selection**: Use `RelevanceStrategy` for speed, `HybridStrategy` for comprehensiveness

## Metadata Structure

Each context relationship includes metadata:

```python
@dataclass
class ContextMetadata:
    relevance_score: float      # 0.0 to 1.0
    relationship_type: str      # 'dependency', 'usage', 'semantic', 'structural'
    distance: int              # Line distance or file distance
    token_count: int           # Estimated tokens in the chunk
```

## Best Practices

1. **Cache Context**: Use caching for repeated analysis of the same codebase
2. **Balance Context Types**: Use hybrid strategy for comprehensive understanding
3. **Monitor Token Usage**: Track token counts to stay within LLM limits
4. **Prioritize Relevance**: Focus on high-relevance chunks for better results
5. **Update Cache**: Invalidate cache when code changes
# Advanced Query System

The Advanced Query System provides sophisticated code search and retrieval capabilities, including natural language queries, semantic search, and similarity matching.

## Overview

The query system consists of three main components:

1. **NaturalLanguageQueryEngine** - Handles various query types and search operations
2. **AdvancedQueryIndex** - Provides fast indexed search with multiple index types
3. **SmartQueryOptimizer** - Improves queries through typo correction and synonym expansion

## Features

### Query Types

- **Natural Language**: Search using plain English queries like "find error handling code"
- **Structured**: Use field-based queries like `type:function language:python`
- **Regex**: Search with regular expressions
- **AST Pattern**: Match specific AST node patterns

### Search Capabilities

- **Semantic Search**: Understands programming concepts and intent
- **Similarity Matching**: Find chunks similar to a reference chunk
- **Multi-criteria Filtering**: Filter by language, node type, size, and metadata
- **Relevance Scoring**: Results ranked by relevance score

### Performance Features

- **Indexed Search**: Fast retrieval using inverted indices
- **Embedding-based Search**: Semantic similarity using vector embeddings
- **Query Optimization**: Automatic typo correction and synonym expansion
- **Incremental Updates**: Add/remove chunks without rebuilding entire index

## Usage Examples

### Basic Natural Language Search

```python
from chunker import NaturalLanguageQueryEngine, QueryType

engine = NaturalLanguageQueryEngine()

# Search for authentication code
results = engine.search(
    "find authentication functions",
    chunks,
    QueryType.NATURAL_LANGUAGE,
    limit=10
)

for result in results:
    print(f"{result.chunk.file_path}:{result.chunk.start_line}")
    print(f"Score: {result.score:.2f}")
    print(f"Matched intents: {result.metadata['matched_intents']}")
```

### Structured Queries

```python
# Find Python test functions
results = engine.search(
    "type:function_definition language:python test",
    chunks,
    QueryType.STRUCTURED
)

# Find class definitions in specific files
results = engine.search(
    "type:class_definition file:auth",
    chunks,
    QueryType.STRUCTURED
)
```

### Building and Using an Index

```python
from chunker import AdvancedQueryIndex

# Create and build index
index = AdvancedQueryIndex()
index.build_index(chunks)

# Query the index
results = index.query("database connection", limit=20)

# Get index statistics
stats = index.get_statistics()
print(f"Indexed {stats['total_chunks']} chunks")
print(f"Unique terms: {stats['unique_terms']}")
```

### Query Optimization

```python
from chunker import SmartQueryOptimizer

optimizer = SmartQueryOptimizer()

# Optimize queries with typos
query = "find fucntion with retrun statement"
optimized = optimizer.optimize_query(query, QueryType.NATURAL_LANGUAGE)
# Result: "find function with return statement"

# Get query suggestions
suggestions = optimizer.suggest_queries("test", chunks)
# Returns: ["test_authentication", "test_login", "test functions", ...]
```

### Filtering Chunks

```python
# Filter by multiple criteria
filtered = engine.filter(
    chunks,
    languages=["python", "javascript"],
    node_types=["function_definition", "method_definition"],
    min_lines=5,
    max_lines=50
)

# Filter by metadata
filtered = engine.filter(
    chunks,
    metadata_filters={
        "complexity": {"min": 5, "max": 20},
        "has_docstring": True
    }
)
```

### Similarity Search

```python
# Find chunks similar to a reference
reference_chunk = chunks[0]
similar = engine.find_similar(
    reference_chunk,
    chunks,
    threshold=0.7,  # Minimum similarity score
    limit=10
)

for result in similar:
    print(f"Similar chunk: {result.chunk.file_path}")
    print(f"Similarity: {result.score:.2f}")
    print(f"Factors: {result.metadata['similarity_factors']}")
```

## Natural Language Query Examples

The system understands various natural language patterns:

- **Error Handling**: "find error handling", "exception handling code", "try-catch blocks"
- **Authentication**: "authentication functions", "login methods", "user auth"
- **Database**: "database queries", "SQL operations", "db connections"
- **Testing**: "test functions", "unit tests", "test cases"
- **Configuration**: "config classes", "settings", "environment setup"
- **Logging**: "logging code", "debug statements", "log functions"
- **Security**: "security checks", "encryption", "password handling"
- **Validation**: "input validation", "data verification", "format checking"

## Structured Query Syntax

Structured queries support field:value pairs with keywords:

```
type:function_definition language:python error handling
```

Supported fields:
- `type`: Node type (function_definition, class_definition, etc.)
- `language`: Programming language
- `file`: File path pattern (supports wildcards)
- Custom metadata fields

## Performance Considerations

### Index Size

The index size depends on:
- Number of chunks
- Average chunk size
- Unique terms in content
- Embedding dimensions (128D by default)

### Query Performance

- Natural language queries: ~10-50ms for 1000 chunks
- Structured queries: ~5-20ms for 1000 chunks
- Regex queries: ~20-100ms depending on pattern complexity
- Index building: ~100ms per 1000 chunks

### Memory Usage

Approximate memory usage:
- Base index: ~1KB per chunk
- Text index: ~2-5KB per chunk
- Embeddings: ~1KB per chunk (128 floats)

## Advanced Features

### Custom Query Intents

Extend the query engine with custom intents:

```python
engine.query_patterns["custom_intent"] = [
    re.compile(r"\bcustom\s+pattern\b", re.I),
    re.compile(r"\bspecial\s+code\b", re.I),
]

engine.code_patterns["custom_intent"] = [
    re.compile(r"@CustomAnnotation"),
    re.compile(r"CUSTOM_MARKER"),
]
```

### Embedding Customization

The system uses a simplified embedding approach by default. For production use, consider integrating with:
- Sentence transformers
- OpenAI embeddings
- Custom trained models

### Query Pipeline

The query processing pipeline:
1. Query parsing and intent extraction
2. Query optimization (typo correction, synonyms)
3. Candidate retrieval from indices
4. Scoring and ranking
5. Result filtering and limiting

## Best Practices

1. **Build indices for large codebases**: Use `AdvancedQueryIndex` for codebases with >1000 chunks
2. **Optimize queries**: Always use `SmartQueryOptimizer` for user-provided queries
3. **Cache results**: Cache frequent queries to improve response time
4. **Update incrementally**: Use `add_chunk`/`remove_chunk` for real-time updates
5. **Monitor performance**: Track query times and index statistics

## Integration with Other Features

The query system integrates well with:
- **Smart Context**: Use query results as context for code generation
- **Semantic Analysis**: Combine with relationship analysis for better results
- **Metadata Extraction**: Query by extracted metadata fields
- **Hierarchical Chunking**: Search within specific hierarchy levels
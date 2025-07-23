# Token Limit Handling

The treesitter-chunker now includes built-in support for respecting token limits when chunking code. This is essential when preparing code for LLMs that have specific context window limitations.

## Quick Start

```python
from chunker import chunk_file_with_token_limit

# Chunk a file ensuring no chunk exceeds 1000 tokens
chunks = chunk_file_with_token_limit(
    "example.py", 
    language="python", 
    max_tokens=1000,
    model="gpt-4"
)

for chunk in chunks:
    print(f"{chunk.node_type}: {chunk.metadata['token_count']} tokens")
```

## Features

### 1. Token-Aware Chunking

The chunker automatically adds token count information to each chunk's metadata:

```python
from chunker import chunk_file

chunks = chunk_file("example.py", "python")
for chunk in chunks:
    # Token info is automatically added
    print(f"Tokens: {chunk.metadata.get('token_count', 'N/A')}")
```

### 2. Automatic Chunk Splitting

When a chunk exceeds the specified token limit, it's automatically split while preserving code structure:

```python
# Large functions/classes are split intelligently
chunks = chunk_file_with_token_limit("large_file.py", "python", max_tokens=500)
```

### 3. Multiple Tokenizer Models

Support for different LLM tokenizers:

```python
# GPT-4 (default)
chunks = chunk_file_with_token_limit("file.py", "python", max_tokens=1000, model="gpt-4")

# Claude
chunks = chunk_file_with_token_limit("file.py", "python", max_tokens=1000, model="claude")

# GPT-3.5
chunks = chunk_file_with_token_limit("file.py", "python", max_tokens=1000, model="gpt-3.5-turbo")
```

## API Reference

### Functions

#### `chunk_text_with_token_limit()`

```python
def chunk_text_with_token_limit(
    text: str, 
    language: str, 
    max_tokens: int, 
    file_path: str = "", 
    model: str = "gpt-4",
    extract_metadata: bool = True
) -> list[CodeChunk]
```

Chunks text ensuring no chunk exceeds the token limit.

#### `chunk_file_with_token_limit()`

```python
def chunk_file_with_token_limit(
    path: str | Path, 
    language: str, 
    max_tokens: int,
    model: str = "gpt-4", 
    extract_metadata: bool = True
) -> list[CodeChunk]
```

Chunks a file ensuring no chunk exceeds the token limit.

#### `count_chunk_tokens()`

```python
def count_chunk_tokens(chunk: CodeChunk, model: str = "gpt-4") -> int
```

Counts tokens in an existing chunk.

### Classes

#### `TreeSitterTokenAwareChunker`

For advanced use cases, you can use the token-aware chunker directly:

```python
from chunker import TreeSitterTokenAwareChunker

chunker = TreeSitterTokenAwareChunker()

# Add token info to existing chunks
chunks_with_tokens = chunker.add_token_info(chunks, model="gpt-4")

# Chunk with token limits
limited_chunks = chunker.chunk_with_token_limit(
    "file.py", "python", max_tokens=1000
)
```

## Chunk Metadata

When using token-aware chunking, chunks include additional metadata:

```python
{
    "token_count": 156,           # Number of tokens in the chunk
    "tokenizer_model": "gpt-4",   # Model used for tokenization
    "chars_per_token": 4.2,       # Average characters per token
    "is_split": True,             # Whether chunk was split from larger chunk
    "split_index": 1,             # Index if split (1, 2, 3...)
    "original_chunk_id": "abc123" # ID of original chunk before splitting
}
```

## Splitting Strategies

### Class Splitting

Classes are intelligently split by methods when they exceed token limits:

```python
class LargeClass:
    def __init__(self):
        # ...
    
    def method1(self):
        # ...
    
    def method2(self):
        # ...
```

If this class exceeds the token limit, it will be split into:
- Chunk 1: Class header + `__init__` + `method1`
- Chunk 2: Class header + `method2`

### Function Splitting

Large functions are split by logical line groups while preserving context:

```python
def large_function():
    # Setup code
    # ...
    
    # Main logic
    # ...
    
    # Cleanup
    # ...
```

## Best Practices

1. **Choose Appropriate Limits**: Consider the LLM's context window and leave room for prompts:
   ```python
   # For GPT-4 (8k context), leave room for prompts
   chunks = chunk_file_with_token_limit("file.py", "python", max_tokens=6000)
   ```

2. **Model-Specific Tokenization**: Use the same model for tokenization as you'll use for processing:
   ```python
   # If using Claude for processing
   chunks = chunk_file_with_token_limit("file.py", "python", 
                                       max_tokens=5000, model="claude")
   ```

3. **Preserve Metadata**: Token-aware chunking preserves all metadata extraction:
   ```python
   chunks = chunk_file_with_token_limit("file.py", "python", 
                                       max_tokens=1000, extract_metadata=True)
   # Chunks still include signatures, docstrings, complexity metrics, etc.
   ```

## Integration with Fallback Strategies

Token limits work seamlessly with the fallback chunking system. When tree-sitter chunks are too large, the sliding window fallback can be used:

```python
from chunker.fallback import SlidingWindowFallback

fallback = SlidingWindowFallback()
# Automatically uses sliding window for files that can't be parsed
# or produce chunks exceeding token limits
```

## Performance Considerations

- Token counting is cached per encoding type
- Splitting only occurs when necessary
- Original chunk structure is preserved when possible
- Metadata extraction happens before splitting for efficiency
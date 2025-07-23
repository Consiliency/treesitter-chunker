# Intelligent Fallback System

The IntelligentFallbackChunker provides smart, automatic selection between tree-sitter parsing and sliding window chunking based on file characteristics, language support, and token limits.

## Overview

The intelligent fallback system automatically chooses the best chunking method by analyzing:
- Tree-sitter language support availability
- Parse success/failure
- Token limits and chunk sizes
- File type and content characteristics
- Specialized processor availability

## Quick Start

```python
from chunker import IntelligentFallbackChunker

# Create with token limit
fallback = IntelligentFallbackChunker(
    token_limit=1000,  # Max tokens per chunk
    model="gpt-4"      # Tokenizer model
)

# Chunk any file - it will automatically choose the best method
chunks = fallback.chunk_text(content, "example.py")

# Each chunk includes decision metadata
for chunk in chunks:
    print(f"Method: {chunk.metadata['chunking_decision']}")
    print(f"Reason: {chunk.metadata['chunking_reason']}")
```

## Decision Logic

### 1. Tree-sitter (Primary)

Used when:
- Language is supported by tree-sitter
- Parsing succeeds
- All chunks fit within token limits

```python
# Automatically uses tree-sitter for supported languages
chunks = fallback.chunk_text(python_code, "script.py")
# Decision: TREE_SITTER
```

### 2. Tree-sitter with Splitting

Used when:
- Language is supported by tree-sitter
- Parsing succeeds
- Some chunks exceed token limits

```python
# Large functions/classes are automatically split
fallback = IntelligentFallbackChunker(token_limit=500)
chunks = fallback.chunk_text(large_class, "module.py")
# Decision: TREE_SITTER_WITH_SPLIT
```

### 3. Specialized Processor

Used when:
- File type has a specialized processor (markdown, logs, config)
- File is not a code file

```python
# Automatically uses markdown processor
chunks = fallback.chunk_text(markdown_content, "README.md")
# Decision: SPECIALIZED_PROCESSOR
```

### 4. Sliding Window (Fallback)

Used when:
- No tree-sitter support for language
- Parse fails or produces no chunks
- Unknown file type

```python
# Falls back to sliding window for unknown types
chunks = fallback.chunk_text(text, "data.xyz")
# Decision: SLIDING_WINDOW
```

## Features

### Automatic Language Detection

```python
# Extension-based detection
fallback.chunk_text(content, "script.py")    # Detects Python
fallback.chunk_text(content, "app.js")       # Detects JavaScript

# Shebang detection
content = "#!/usr/bin/env python3\n..."
fallback.chunk_text(content, "script")       # Detects Python from shebang
```

### Token Limit Enforcement

```python
# Set token limit for LLM compatibility
fallback = IntelligentFallbackChunker(
    token_limit=4000,      # GPT-4 safe limit
    model="gpt-4"          # Use correct tokenizer
)

# Large chunks are automatically split
chunks = fallback.chunk_text(large_file, "big.py")
# All chunks guaranteed <= 4000 tokens
```

### Decision Transparency

```python
# Get detailed decision information
info = fallback.get_decision_info("file.py", content)

print(info['decision'])           # e.g., "tree_sitter_with_split"
print(info['reason'])             # e.g., "Tree-sitter with splitting (largest chunk: 1234 tokens)"
print(info['metrics'])            # Detailed analysis metrics
```

## Configuration

### Basic Configuration

```python
# Default configuration
fallback = IntelligentFallbackChunker()

# With token limits
fallback = IntelligentFallbackChunker(
    token_limit=1000,
    model="claude"
)

# With sliding window config
fallback = IntelligentFallbackChunker(
    sliding_window_config={
        'window_size': 2000,
        'overlap': 200
    }
)
```

### Supported Languages

The system automatically detects these languages:

```python
# Common languages
.py    → python
.js    → javascript
.ts    → typescript
.java  → java
.cpp   → cpp
.rs    → rust
.go    → go
.rb    → ruby
.php   → php
.cs    → csharp
# ... and many more
```

## Decision Metrics

The system analyzes multiple metrics:

```python
metrics = {
    'has_tree_sitter_support': True,    # Language supported?
    'parse_success': True,              # Parse succeeded?
    'largest_chunk_tokens': 1234,       # Biggest chunk size
    'average_chunk_tokens': 567,        # Average size
    'total_tokens': 5678,               # Total tokens
    'is_code_file': True,               # Code vs text?
    'token_limit_exceeded': False,      # Any oversized chunks?
}
```

## Examples

### Multi-Language Project

```python
fallback = IntelligentFallbackChunker(token_limit=1000)

# Automatically handles different file types
for file_path in project_files:
    with open(file_path) as f:
        content = f.read()
    
    chunks = fallback.chunk_text(content, file_path)
    
    # Each file uses optimal method
    print(f"{file_path}: {chunks[0].metadata['chunking_decision']}")
```

### LLM Processing Pipeline

```python
# Configure for specific LLM
fallback = IntelligentFallbackChunker(
    token_limit=3500,      # Leave room for prompts
    model="gpt-3.5-turbo"
)

# Process repository
for file_path in repo.get_files():
    chunks = fallback.chunk_text(
        repo.read_file(file_path), 
        file_path
    )
    
    # All chunks fit in context window
    for chunk in chunks:
        response = llm.process(chunk.content)
```

### Fallback Handling

```python
# System gracefully handles edge cases
fallback = IntelligentFallbackChunker()

# Empty file - uses sliding window
chunks = fallback.chunk_text("", "empty.py")

# Binary file - detects and handles
chunks = fallback.chunk_text(binary_content, "image.png")

# Corrupted code - falls back gracefully
chunks = fallback.chunk_text(corrupted, "broken.py")
```

## Integration with Phase 11 Components

The intelligent fallback integrates with all Phase 11 processors:

```python
# Automatically uses specialized processors
chunks = fallback.chunk_text(markdown, "README.md")    # MarkdownProcessor
chunks = fallback.chunk_text(logs, "app.log")          # LogProcessor
chunks = fallback.chunk_text(config, "config.yaml")    # ConfigProcessor

# Falls back to sliding window when needed
chunks = fallback.chunk_text(text, "notes.txt")        # SlidingWindowEngine
```

## Best Practices

1. **Set Appropriate Token Limits**
   ```python
   # Account for prompt overhead
   fallback = IntelligentFallbackChunker(
       token_limit=6000  # For 8k context window
   )
   ```

2. **Use Correct Tokenizer Model**
   ```python
   # Match tokenizer to LLM
   fallback = IntelligentFallbackChunker(
       model="claude"  # For Claude models
   )
   ```

3. **Handle Decision Metadata**
   ```python
   chunks = fallback.chunk_text(content, file_path)
   
   # Log decisions for debugging
   for chunk in chunks:
       logger.info(f"Chunked with {chunk.metadata['chunking_decision']}")
   ```

4. **Monitor Performance**
   ```python
   # Check decision distribution
   decisions = {}
   for chunk in all_chunks:
       decision = chunk.metadata['chunking_decision']
       decisions[decision] = decisions.get(decision, 0) + 1
   
   print("Chunking methods used:", decisions)
   ```

## Limitations

- Language detection is heuristic-based
- Token counting requires the tiktoken library
- Specialized processors must be available in the environment
- Binary files are detected but not chunked
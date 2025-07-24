# Zero-Configuration API

The Zero-Config API provides the simplest way to use treesitter-chunker with automatic language detection, grammar management, and intelligent fallbacks.

## Overview

The `ZeroConfigAPI` class provides a high-level interface that:
- Automatically detects programming languages from file extensions and content
- Downloads and sets up tree-sitter grammars as needed
- Falls back to intelligent text chunking when tree-sitter is unavailable
- Supports batch operations and preloading for offline use

## Basic Usage

```python
from chunker import ZeroConfigAPI
from chunker.contracts.registry_stub import UniversalRegistryStub

# Create API instance with a registry
registry = UniversalRegistryStub()  # Or use real UniversalLanguageRegistry
api = ZeroConfigAPI(registry)

# Chunk a file - language is auto-detected
result = api.auto_chunk_file("example.py")

# Access chunks
for chunk in result.chunks:
    print(f"Type: {chunk['type']}, Lines: {chunk['start_line']}-{chunk['end_line']}")
    print(chunk['content'])
```

## Key Features

### 1. Automatic Language Detection

```python
# Detects Python from .py extension
language = api.detect_language("script.py")  # Returns "python"

# Detects from shebang
language = api.detect_language("script")  # Checks #!/usr/bin/env python

# Special file names
language = api.detect_language("Makefile")  # Returns "makefile"
language = api.detect_language("Dockerfile")  # Returns "dockerfile"
```

### 2. Zero-Configuration File Chunking

```python
# Automatically detects language and chunks appropriately
result = api.auto_chunk_file("main.go")

# Check if grammar was downloaded
if result.grammar_downloaded:
    print("Grammar was automatically downloaded")

# Check if fallback was used
if result.fallback_used:
    print("Used text-based chunking (tree-sitter unavailable)")
```

### 3. Direct Text Chunking

```python
# Chunk text content directly
code = """
def hello(name):
    return f"Hello, {name}!"
"""

result = api.chunk_text(code, "python")
```

### 4. Token-Limited Chunking

```python
# Limit chunks to specific token count
result = api.auto_chunk_file("large_file.py", token_limit=1000)
```

### 5. Language Preloading

```python
# Preload multiple languages for offline use
languages = ["python", "javascript", "go", "rust"]
results = api.preload_languages(languages)

for lang, success in results.items():
    print(f"{lang}: {'✓' if success else '✗'}")
```

### 6. Ensure Language Availability

```python
# Ensure a specific language is ready
if api.ensure_language("java"):
    print("Java is ready to use")
    
# Ensure specific version
if api.ensure_language("python", "0.20.0"):
    print("Python 0.20.0 is ready")
```

### 7. Get Language-Specific Chunker

```python
# Get a configured chunker for a specific language
chunker = api.get_chunker_for_language("rust")

# Use it directly
chunks = chunker.chunk_file("main.rs")
```

### 8. List Supported Extensions

```python
# Get all supported file extensions
extensions = api.list_supported_extensions()

# Example output:
# {
#     "python": [".py"],
#     "javascript": [".js", ".jsx"],
#     "typescript": [".ts", ".tsx"],
#     ...
# }
```

## Result Structure

The `AutoChunkResult` object contains:

```python
@dataclass
class AutoChunkResult:
    chunks: list[dict[str, Any]]  # List of chunk dictionaries
    language: str                  # Detected or specified language
    grammar_downloaded: bool       # Whether grammar was downloaded
    fallback_used: bool           # Whether fallback chunking was used
    metadata: dict[str, Any]      # Additional metadata
```

Each chunk dictionary contains:
- `content`: The actual code/text content
- `type`: Node type (e.g., "function_definition", "class", "text")
- `start_line`: Starting line number
- `end_line`: Ending line number
- `metadata`: Optional additional metadata

## Error Handling

```python
try:
    result = api.auto_chunk_file("nonexistent.py")
except ValueError as e:
    print(f"Error: {e}")  # File not found

# Invalid language handling
success = api.ensure_language("not-a-real-language")
assert success is False
```

## Integration with Registry

The Zero-Config API works with any implementation of `UniversalRegistryContract`:

```python
from chunker.contracts.registry_contract import UniversalRegistryContract

class MyCustomRegistry(UniversalRegistryContract):
    # Implement required methods
    pass

api = ZeroConfigAPI(MyCustomRegistry())
```

## Advanced Usage

### Custom Language Override

```python
# Force specific language detection
result = api.auto_chunk_file("script.txt", language="python")
```

### Fallback Behavior

When tree-sitter is unavailable, the API automatically falls back to intelligent text chunking:

```python
# If grammar download fails or language unsupported
result = api.auto_chunk_file("data.csv")
assert result.fallback_used is True
assert result.language == "unknown"  # Or detected type
```

### Batch Processing

```python
import os

# Process all Python files in a directory
for root, dirs, files in os.walk("src"):
    for file in files:
        if file.endswith(".py"):
            path = os.path.join(root, file)
            result = api.auto_chunk_file(path)
            print(f"Processed {path}: {len(result.chunks)} chunks")
```

## Best Practices

1. **Preload for Production**: Use `preload_languages()` to ensure grammars are available before processing
2. **Check Results**: Always check `fallback_used` to know if tree-sitter chunking was successful
3. **Handle Unknown Languages**: Implement fallback logic for files with unknown languages
4. **Cache Registry**: Use a persistent registry implementation to avoid re-downloading grammars

## Example: Complete Workflow

```python
from chunker import ZeroConfigAPI
from chunker.contracts.registry_stub import UniversalRegistryStub

# Initialize
registry = UniversalRegistryStub()
api = ZeroConfigAPI(registry)

# Preload common languages
languages = ["python", "javascript", "typescript", "go"]
preload_results = api.preload_languages(languages)
print(f"Preloaded: {sum(preload_results.values())} of {len(languages)} languages")

# Process a mixed codebase
def process_file(file_path):
    try:
        result = api.auto_chunk_file(file_path)
        
        print(f"\nFile: {file_path}")
        print(f"Language: {result.language}")
        print(f"Chunks: {len(result.chunks)}")
        print(f"Grammar downloaded: {result.grammar_downloaded}")
        print(f"Fallback used: {result.fallback_used}")
        
        # Process chunks
        for i, chunk in enumerate(result.chunks):
            print(f"  Chunk {i+1}: {chunk['type']} (lines {chunk['start_line']}-{chunk['end_line']})")
            
    except Exception as e:
        print(f"Error processing {file_path}: {e}")

# Process various file types
process_file("main.py")
process_file("app.js")
process_file("server.go")
process_file("README.md")
process_file("Makefile")
```

## Performance Considerations

1. **Grammar Download**: First use of a language may be slower due to grammar download
2. **Caching**: The registry should cache parsers for better performance
3. **Parallel Processing**: Consider using parallel processing for large codebases
4. **Memory Usage**: Large files may consume significant memory during parsing

## Troubleshooting

### Grammar Download Failures
- Check internet connection
- Verify language name is correct
- Check if grammar is available in tree-sitter ecosystem

### Fallback Warnings
- Normal for non-code files (markdown, config files)
- Check file extension mapping if unexpected
- Verify tree-sitter installation

### Performance Issues
- Preload languages before batch processing
- Use token limits for very large files
- Consider chunking strategy configuration
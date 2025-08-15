# Tree-sitter Chunker User Guide

## Table of Contents

1. [Introduction](#introduction)
2. [Installation](#installation)
3. [Core Concepts](#core-concepts)
4. [Basic Usage](#basic-usage)
5. [Supported Languages](#supported-languages)
6. [Working with Chunks](#working-with-chunks)
7. [Advanced Features](#advanced-features)
8. [Integration Patterns](#integration-patterns)
9. [Performance Best Practices](#performance-best-practices)
10. [Configuration](#configuration)
11. [Troubleshooting](#troubleshooting)

## Introduction

Tree-sitter Chunker is a powerful library for semantically chunking source code using Tree-sitter parsers. It provides intelligent code splitting that understands syntax and structure, making it ideal for code analysis, documentation generation, and AI/LLM applications.

### Key Features

- **Dynamic Language Discovery**: Automatically discovers available languages from compiled grammars
- **Efficient Parser Management**: LRU caching and pooling for optimal performance
- **Thread-Safe Operation**: Designed for concurrent processing
- **Rich Error Handling**: Comprehensive exception hierarchy with recovery suggestions
- **Semantic Understanding**: Extracts meaningful code units (functions, classes, methods)
- **Context Preservation**: Maintains parent-child relationships for nested structures

### When to Use Tree-sitter Chunker

Tree-sitter Chunker is ideal for:

- **Code Embedding Generation**: Create embeddings for semantic code search
- **LLM Context Windows**: Split code intelligently for language model processing
- **Documentation Generation**: Extract functions and classes with metadata
- **Code Analysis**: Analyze code structure, complexity, and patterns
- **Code Navigation**: Build code maps and understand project structure
- **Refactoring Tools**: Identify and process code units programmatically

## Installation

### Prerequisites

- Python 3.8 or higher
- ~~uv package manager (recommended) or pip~~ **pip is sufficient for PyPI installation**
- ~~C compiler (for building tree-sitter grammars)~~ **No longer required for basic usage!**
- ~~Git (for fetching grammar repositories)~~ **No longer required for basic usage!**

### Install from PyPI (Recommended)

The easiest way to get started is to install the pre-built package from PyPI:

```bash
# Install the latest stable version
pip install treesitter-chunker

# With visualization tools (requires graphviz)
pip install "treesitter-chunker[viz]"

# With all optional dependencies
pip install "treesitter-chunker[all]"
```

**Note**: Prebuilt wheels include compiled Tree-sitter grammars for common languages (Python, JavaScript, Rust, C, C++), so no local compilation is required!

### Development Installation

If you want to contribute or need the latest development version:

```bash
# Clone the repository
git clone https://github.com/Consiliency/treesitter-chunker.git
cd treesitter-chunker

# Install in development mode
uv pip install -e ".[dev]"

# Install py-tree-sitter with ABI 15 support
uv pip install git+https://github.com/tree-sitter/py-tree-sitter.git

# Build language grammars (only needed for development)
python scripts/fetch_grammars.py
python scripts/build_lib.py
```

### Verify Installation

```python
from chunker.parser import list_languages, get_language_info

# Check available languages
languages = list_languages()
print(f"Available languages: {languages}")

# Get language details
info = get_language_info("python")
print(f"Python ABI version: {info.version}")
print(f"Node types: {info.node_types_count}")
```

## Core Concepts

### Languages and Grammars

Tree-sitter uses grammar files to understand language syntax. Each language has:
- A grammar definition that describes syntax rules
- A parser that builds Abstract Syntax Trees (AST)
- Node types that represent different code constructs

### Code Chunks

A chunk is a semantic unit of code with:
- **Content**: The actual source code
- **Metadata**: Location, type, and context information
- **Relationships**: Parent-child relationships for nested structures

### Parser Management

The library uses several optimization strategies:
- **Caching**: Recently used parsers are kept in memory
- **Pooling**: Multiple parsers per language for concurrent use
- **Lazy Loading**: Languages are loaded only when needed

## Basic Usage

### Command Line Interface

```bash
# Basic chunking
python cli/main.py chunk example.py -l python

# Output as JSON
python cli/main.py chunk src/main.rs -l rust --json

# Process JavaScript file
python cli/main.py chunk app.js -l javascript
```

### Python API - Simple

```python
from chunker.chunker import chunk_file

# Chunk a Python file
chunks = chunk_file("example.py", "python")

# Process chunks
for chunk in chunks:
    print(f"{chunk.node_type} at lines {chunk.start_line}-{chunk.end_line}")
    if chunk.parent_context:
        print(f"  Parent: {chunk.parent_context}")
    print(f"  Preview: {chunk.content.split(chr(10))[0]}...")
```

### Python API - Advanced

```python
from chunker.parser import get_parser, return_parser
from chunker.exceptions import LanguageNotFoundError

# Manual parser management for better control
try:
    parser = get_parser("python")
    
    with open("example.py", "rb") as f:
        tree = parser.parse(f.read())
    
    # Process the AST
    root = tree.root_node
    print(f"Root type: {root.type}")
    print(f"Children: {root.child_count}")
    
finally:
    # Return parser for reuse
    return_parser("python", parser)
```

## Supported Languages

### Python
```python
# Extracted node types:
# - function_definition (functions)
# - class_definition (classes)
# - method_definition (methods within classes)

class Calculator:  # class_definition
    def add(self, a, b):  # method_definition
        return a + b
    
def main():  # function_definition
    calc = Calculator()
```

### JavaScript
```javascript
// Extracted node types:
// - function_declaration
// - class_declaration
// - method_definition
// - arrow_function

class Component {  // class_declaration
    render() {  // method_definition
        return null;
    }
}

const handler = () => {  // arrow_function
    console.log("clicked");
};
```

### Rust
```rust
// Extracted node types:
// - function_item
// - impl_item
// - struct_item
// - trait_item

struct Data {  // struct_item
    value: i32,
}

impl Data {  // impl_item
    fn new() -> Self {  // function_item
        Data { value: 0 }
    }
}
```

### C/C++
```cpp
// C extracts: function_definition
// C++ adds: class_specifier, method_declaration

class Widget {  // class_specifier (C++ only)
public:
    void update();  // method_declaration
};

int process_data(int* data) {  // function_definition
    return data[0];
}
```

## Working with Chunks

### Understanding CodeChunk

```python
from chunker.chunker import CodeChunk

# Example chunk structure
chunk = CodeChunk(
    language="python",
    file_path="/path/to/file.py",
    node_type="function_definition",
    start_line=10,
    end_line=15,
    byte_start=234,
    byte_end=456,
    parent_context="class:Calculator",
    content="def add(self, a, b):\n    return a + b"
)

# Access properties
print(f"Function spans {chunk.end_line - chunk.start_line + 1} lines")
print(f"Belongs to: {chunk.parent_context}")
print(f"Size: {chunk.byte_end - chunk.byte_start} bytes")
```

### Filtering and Grouping

```python
from collections import defaultdict

chunks = chunk_file("project.py", "python")

# Group by type
by_type = defaultdict(list)
for chunk in chunks:
    by_type[chunk.node_type].append(chunk)

print(f"Functions: {len(by_type['function_definition'])}")
print(f"Classes: {len(by_type['class_definition'])}")
print(f"Methods: {len(by_type['method_definition'])}")

# Find large functions
large_functions = [
    c for c in chunks 
    if c.node_type == "function_definition" 
    and (c.end_line - c.start_line) > 50
]

# Get methods of a specific class
class_methods = [
    c for c in chunks 
    if c.parent_context == "class:MyClass"
]
```

### Analyzing Code Structure

```python
def analyze_file_structure(file_path, language):
    """Analyze the structure of a code file."""
    chunks = chunk_file(file_path, language)
    
    # Build hierarchy
    top_level = [c for c in chunks if not c.parent_context]
    nested = [c for c in chunks if c.parent_context]
    
    print(f"File: {file_path}")
    print(f"Total chunks: {len(chunks)}")
    print(f"Top-level: {len(top_level)}")
    print(f"Nested: {len(nested)}")
    
    # Complexity metrics
    sizes = [(c.end_line - c.start_line + 1) for c in chunks]
    if sizes:
        print(f"Average size: {sum(sizes) / len(sizes):.1f} lines")
        print(f"Largest: {max(sizes)} lines")
        print(f"Smallest: {min(sizes)} lines")
    
    return chunks
```

## Advanced Features

### Working with the Language Registry

```python
from chunker.registry import LanguageRegistry
from pathlib import Path

# Access the registry directly
registry = LanguageRegistry(Path("build/my-languages.so"))

# Discover all languages
languages = registry.discover_languages()
for name, metadata in languages.items():
    print(f"{name}:")
    print(f"  Version: {metadata.version}")
    print(f"  Node types: {metadata.node_types_count}")
    print(f"  Has scanner: {metadata.has_scanner}")

# Check specific language
if registry.has_language("python"):
    lang = registry.get_language("python")
    # Use with tree-sitter parser
```

### Custom Parser Configuration

```python
from chunker.parser import get_parser
from chunker.factory import ParserConfig

# Configure parser with timeout
config = ParserConfig(
    timeout_ms=5000,  # 5 second timeout
    included_ranges=[(0, 1000), (2000, 3000)]  # Parse only specific byte ranges
)

parser = get_parser("python", config)
# Parser will only parse specified ranges and timeout after 5s
```

### Concurrent Processing

```python
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

def process_directory(directory, language, max_workers=4):
    """Process all files in directory concurrently."""
    files = list(Path(directory).rglob(f"*.{language[:2]}"))
    
    def process_file(file_path):
        try:
            return chunk_file(file_path, language)
        except Exception as e:
            print(f"Error in {file_path}: {e}")
            return []
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all files
        futures = {executor.submit(process_file, f): f for f in files}
        
        # Collect results
        all_chunks = []
        for future in futures:
            chunks = future.result()
            all_chunks.extend(chunks)
    
    return all_chunks

# Process entire codebase
chunks = process_directory("src", "python", max_workers=8)
```

### Cache Management

```python
from chunker.parser import clear_cache, _factory

# Monitor cache performance
def process_with_stats(files, language):
    # Clear cache for fresh start
    clear_cache()
    
    # Process files
    for file in files:
        chunk_file(file, language)
    
    # Get statistics
    stats = _factory.get_stats()
    print(f"Cache Performance:")
    print(f"  Hits: {stats['cache_hits']}")
    print(f"  Misses: {stats['cache_misses']}")
    print(f"  Hit rate: {stats['hit_rate']:.2%}")
    print(f"  Current cache size: {stats['cache_size']}")
    
    return stats
```

## Integration Patterns

### Integration with Embedding Systems

```python
from chunker.chunker import chunk_file
import numpy as np

def create_code_embeddings(file_path, language, embedding_model):
    """Generate embeddings for code chunks."""
    chunks = chunk_file(file_path, language)
    
    embeddings = []
    for chunk in chunks:
        # Prepare text for embedding
        context = f"File: {chunk.file_path}\n"
        context += f"Type: {chunk.node_type}\n"
        if chunk.parent_context:
            context += f"Parent: {chunk.parent_context}\n"
        context += f"Lines: {chunk.start_line}-{chunk.end_line}\n\n"
        context += chunk.content
        
        # Generate embedding (example with sentence-transformers)
        embedding = embedding_model.encode(context)
        
        embeddings.append({
            "chunk_id": f"{chunk.file_path}:{chunk.start_line}",
            "metadata": {
                "type": chunk.node_type,
                "parent": chunk.parent_context,
                "lines": (chunk.start_line, chunk.end_line)
            },
            "embedding": embedding,
            "content": chunk.content
        })
    
    return embeddings

# Search function
def semantic_search(query, embeddings, embedding_model, top_k=5):
    """Search for relevant code chunks."""
    query_embedding = embedding_model.encode(query)
    
    # Calculate similarities
    similarities = []
    for item in embeddings:
        similarity = np.dot(query_embedding, item["embedding"])
        similarities.append((similarity, item))
    
    # Return top results
    similarities.sort(key=lambda x: x[0], reverse=True)
    return [item for _, item in similarities[:top_k]]
```

### Documentation Generation

```python
import ast
from chunker.chunker import chunk_file

def extract_docstrings(project_path, output_file):
    """Extract all docstrings from Python project."""
    from pathlib import Path
    
    documentation = []
    
    for py_file in Path(project_path).rglob("*.py"):
        chunks = chunk_file(py_file, "python")
        
        for chunk in chunks:
            if chunk.node_type in ["function_definition", "class_definition"]:
                try:
                    # Parse chunk to extract docstring
                    tree = ast.parse(chunk.content)
                    if tree.body:
                        node = tree.body[0]
                        docstring = ast.get_docstring(node)
                        
                        if docstring:
                            documentation.append({
                                "type": chunk.node_type,
                                "name": node.name,
                                "file": str(py_file),
                                "line": chunk.start_line,
                                "docstring": docstring,
                                "signature": chunk.content.split('\n')[0]
                            })
                except:
                    continue
    
    # Generate markdown documentation
    with open(output_file, "w") as f:
        f.write("# API Documentation\n\n")
        
        # Group by file
        by_file = {}
        for doc in documentation:
            by_file.setdefault(doc["file"], []).append(doc)
        
        for file, docs in sorted(by_file.items()):
            f.write(f"## {file}\n\n")
            for doc in docs:
                f.write(f"### {doc['name']}\n")
                f.write(f"*{doc['type']} at line {doc['line']}*\n\n")
                f.write(f"```python\n{doc['signature']}\n```\n\n")
                f.write(f"{doc['docstring']}\n\n")
```

### Code Quality Analysis

```python
from chunker.chunker import chunk_file
import re

def analyze_code_quality(file_path, language):
    """Analyze code quality metrics."""
    chunks = chunk_file(file_path, language)
    
    issues = []
    
    for chunk in chunks:
        # Check function length
        lines = chunk.end_line - chunk.start_line + 1
        if chunk.node_type == "function_definition" and lines > 50:
            issues.append({
                "type": "long_function",
                "severity": "warning" if lines < 100 else "error",
                "location": f"{chunk.file_path}:{chunk.start_line}",
                "message": f"Function is {lines} lines long (recommended: <50)",
                "chunk": chunk
            })
        
        # Check complexity (simple heuristic based on nesting)
        max_indent = 0
        for line in chunk.content.split('\n'):
            if line.strip():
                indent = len(line) - len(line.lstrip())
                max_indent = max(max_indent, indent)
        
        if max_indent > 20:  # 5 levels of nesting (4 spaces each)
            issues.append({
                "type": "high_complexity",
                "severity": "warning",
                "location": f"{chunk.file_path}:{chunk.start_line}",
                "message": f"High nesting level detected",
                "chunk": chunk
            })
        
        # Check naming conventions (Python example)
        if language == "python" and chunk.node_type == "function_definition":
            # Extract function name
            match = re.match(r'def\s+(\w+)', chunk.content)
            if match:
                func_name = match.group(1)
                if not re.match(r'^[a-z_][a-z0-9_]*$', func_name):
                    issues.append({
                        "type": "naming_convention",
                        "severity": "info",
                        "location": f"{chunk.file_path}:{chunk.start_line}",
                        "message": f"Function '{func_name}' doesn't follow snake_case",
                        "chunk": chunk
                    })
    
    return issues

# Generate report
def generate_quality_report(directory, language):
    """Generate code quality report for directory."""
    from pathlib import Path
    
    all_issues = []
    for file in Path(directory).rglob(f"*.{language[:2]}"):
        issues = analyze_code_quality(file, language)
        all_issues.extend(issues)
    
    # Summary
    by_type = {}
    by_severity = {}
    for issue in all_issues:
        by_type[issue["type"]] = by_type.get(issue["type"], 0) + 1
        by_severity[issue["severity"]] = by_severity.get(issue["severity"], 0) + 1
    
    print("Code Quality Report")
    print("=" * 50)
    print(f"Total issues: {len(all_issues)}")
    print("\nBy type:")
    for type, count in by_type.items():
        print(f"  {type}: {count}")
    print("\nBy severity:")
    for severity, count in by_severity.items():
        print(f"  {severity}: {count}")
    
    return all_issues
```

## Plugin System

### Using Built-in Plugins

Tree-sitter Chunker comes with built-in plugins for Python, JavaScript, Rust, C, and C++:

```python
from chunker.plugin_manager import get_plugin_manager

# Load built-in plugins
manager = get_plugin_manager()
manager.load_built_in_plugins()

# List available plugins
print(manager.list_plugins())
# Output: ['python', 'javascript', 'rust', 'c', 'cpp']

# Chunk files using plugins
chunks = chunk_file("example.py", "python")
```

### Plugin Configuration

Configure plugins through configuration files or programmatically:

```python
from chunker.chunker_config import ChunkerConfig
from chunker.plugin_manager import PluginConfig

# Load configuration from file
config = ChunkerConfig("chunker.config.toml")

# Or configure programmatically
config = ChunkerConfig()
config.set_plugin_config("python", PluginConfig(
    enabled=True,
    chunk_types={"function_definition", "class_definition"},
    min_chunk_size=5,
    max_chunk_size=300,
    custom_options={
        "include_docstrings": True,
        "skip_private": False
    }
))
```

### Loading Custom Plugins

```python
from pathlib import Path
from chunker.plugin_manager import get_plugin_manager

# Load plugins from a directory
manager = get_plugin_manager()
manager.load_plugin_directory(Path("~/.chunker/plugins"))

# Or register a plugin class directly
from my_plugin import SwiftPlugin
manager.register_plugin(SwiftPlugin)
```

## Performance Features

### AST Caching

The AST cache provides up to 11.9x speedup for repeated file processing:

```python
from chunker.core import chunk_file
from chunker.cache import ASTCache

# Caching is enabled by default
chunks1 = chunk_file("large_file.py", "python")  # First run: parses
chunks2 = chunk_file("large_file.py", "python")  # Second run: uses cache (11.9x faster)

# Monitor cache performance
cache = ASTCache(max_size=200)
stats = cache.get_stats()
print(f"Cache hit rate: {stats['hit_rate']:.2%}")
print(f"Cache size: {stats['size']}/{stats['max_size']}")
```

### Parallel File Processing

Process multiple files concurrently for maximum performance:

```python
from chunker.parallel import chunk_files_parallel, chunk_directory_parallel

# Process specific files
files = ["src/main.py", "src/utils.py", "src/models.py"]
results = chunk_files_parallel(
    files, 
    "python", 
    max_workers=8,
    show_progress=True
)

# Process entire directory
results = chunk_directory_parallel(
    "src/",
    "python",
    pattern="**/*.py",
    max_workers=8
)

for file_path, chunks in results.items():
    print(f"{file_path}: {len(chunks)} chunks")
```

### Streaming Large Files

For very large files, use streaming to avoid loading everything into memory:

```python
from chunker.streaming import chunk_file_streaming

# Process a huge file incrementally
for chunk in chunk_file_streaming("massive_codebase.py", "python"):
    # Process each chunk as it's found
    print(f"Found {chunk.node_type} at lines {chunk.start_line}-{chunk.end_line}")
    # Save to database, send to API, etc.
    process_chunk(chunk)
```

### Performance Tips

1. **Enable Caching**: Always use caching for files that are processed multiple times
2. **Use Parallel Processing**: Take advantage of multiple CPU cores
3. **Stream Large Files**: Use streaming for files over 10MB
4. **Configure Cache Size**: Adjust based on available memory
5. **Batch Operations**: Process files in batches rather than one at a time

## Export Formats

### JSON Export

Export chunks to JSON with different schema types:

```python
from chunker.core import chunk_file
from chunker.export.json_export import JSONExporter
from chunker.export.formatters import SchemaType

# Get chunks
chunks = chunk_file("example.py", "python")

# Export with flat schema (default)
exporter = JSONExporter(schema_type=SchemaType.FLAT)
exporter.export(chunks, "output.json", indent=2)

# Export with nested schema (preserves hierarchy)
exporter = JSONExporter(schema_type=SchemaType.NESTED)
exporter.export(chunks, "output_nested.json")

# Export with compression
exporter.export(chunks, "output.json.gz", compress=True)
```

### JSONL Export

JSON Lines format is ideal for streaming and large datasets:

```python
from chunker.export.json_export import JSONLExporter

# Export to JSONL
exporter = JSONLExporter()
exporter.export(chunks, "output.jsonl")

# Stream export for large datasets
from chunker.streaming import chunk_file_streaming

def chunk_generator():
    for chunk in chunk_file_streaming("huge_file.py", "python"):
        yield chunk

exporter.export_streaming(chunk_generator(), "large_output.jsonl")
```

### Parquet Export

Parquet format is excellent for analytics and data science workflows:

```python
from chunker.exporters import ParquetExporter

# Basic export
exporter = ParquetExporter()
exporter.export(chunks, "output.parquet")

# Export with custom columns and compression
exporter = ParquetExporter(
    columns=["language", "file_path", "node_type", "content", "start_line", "end_line"],
    compression="snappy"  # Options: snappy, gzip, brotli, lz4, zstd
)
exporter.export(chunks, "output.parquet")

# Export with partitioning for large datasets
exporter.export_partitioned(
    chunks,
    "output_dir/",
    partition_cols=["language", "node_type"]
)

# Stream export for memory efficiency
from chunker.parallel import chunk_directory_parallel

def process_directory(directory):
    results = chunk_directory_parallel(directory, "python")
    for file_path, file_chunks in results.items():
        for chunk in file_chunks:
            yield chunk

exporter.export_streaming(
    process_directory("large_codebase/"),
    "streaming_output.parquet",
    batch_size=1000
)
```

### Export Format Comparison

| Format | Best For | Compression | Streaming | Schema Support |
|--------|----------|-------------|-----------|----------------|
| JSON | Human-readable, small datasets | Optional | No | Flexible |
| JSONL | Streaming, logs, APIs | Optional | Yes | Per-line |
| Parquet | Analytics, big data | Built-in | Yes | Typed |

### Custom Export Example

```python
# Export chunks with filtering and transformation
from chunker.parallel import chunk_directory_parallel
from chunker.exporters import ParquetExporter

# Process a project
results = chunk_directory_parallel("myproject/", "python")

# Filter and transform chunks
processed_chunks = []
for file_path, chunks in results.items():
    for chunk in chunks:
        # Only export functions and classes
        if chunk.node_type in ["function_definition", "class_definition"]:
            # Add custom metadata
            chunk.metadata = {
                "project": "myproject",
                "version": "1.0.0",
                "extracted_at": datetime.now().isoformat()
            }
            processed_chunks.append(chunk)

# Export to Parquet with partitioning
exporter = ParquetExporter(compression="zstd")
exporter.export_partitioned(
    processed_chunks,
    "exports/myproject/",
    partition_cols=["node_type"]
)
```

## Performance Best Practices

### 1. Reuse Parsers

```python
# Good - parser reused automatically
for file in files:
    chunks = chunk_file(file, "python")

# Also good - manual control
parser = get_parser("python")
try:
    for file in files:
        # Use same parser for multiple files
        with open(file, 'rb') as f:
            tree = parser.parse(f.read())
finally:
    return_parser("python", parser)
```

### 2. Process in Parallel

```python
from concurrent.futures import ThreadPoolExecutor

# Process multiple files concurrently
with ThreadPoolExecutor(max_workers=8) as executor:
    futures = [executor.submit(chunk_file, f, "python") for f in files]
    results = [f.result() for f in futures]
```

### 3. Configure Cache Size

```python
import os

# Set via environment variables
os.environ['CHUNKER_CACHE_SIZE'] = '20'
os.environ['CHUNKER_POOL_SIZE'] = '10'

# Or configure factory directly
from chunker.factory import ParserFactory
from chunker.registry import LanguageRegistry

registry = LanguageRegistry(Path("build/my-languages.so"))
factory = ParserFactory(registry, cache_size=20, pool_size=10)
```

### 4. Handle Large Files

```python
def chunk_large_file(file_path, language, max_size_mb=10):
    """Handle large files efficiently."""
    from pathlib import Path
    
    file_size = Path(file_path).stat().st_size / (1024 * 1024)
    
    if file_size > max_size_mb:
        # Process in chunks using included_ranges
        from chunker.factory import ParserConfig
        
        chunk_size = int(max_size_mb * 1024 * 1024)
        ranges = []
        
        with open(file_path, 'rb') as f:
            data = f.read()
            for i in range(0, len(data), chunk_size):
                ranges.append((i, min(i + chunk_size, len(data))))
        
        all_chunks = []
        for start, end in ranges:
            config = ParserConfig(included_ranges=[(start, end)])
            parser = get_parser(language, config)
            # Process range...
            
        return all_chunks
    else:
        return chunk_file(file_path, language)
```

## Configuration

### Environment Variables

```bash
# Set logging level
export CHUNKER_LOG_LEVEL=DEBUG

# Configure cache sizes
export CHUNKER_CACHE_SIZE=20
export CHUNKER_POOL_SIZE=10

# Run with custom configuration
python cli/main.py chunk file.py -l python
```

### Programmatic Configuration

```python
import logging
from chunker.factory import ParserConfig

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Configure parser
config = ParserConfig(
    timeout_ms=10000,  # 10 second timeout
    logger=logging.getLogger("parser")
)
```

## Troubleshooting

### Common Issues and Solutions

#### Language Not Found

```python
from chunker.parser import list_languages
from chunker.exceptions import LanguageNotFoundError

try:
    chunks = chunk_file("file.xyz", "xyz")
except LanguageNotFoundError as e:
    print(f"Error: {e}")
    available = list_languages()
    print(f"Available languages: {', '.join(available)}")
    # Suggestion: Check if language is compiled into .so file
```

#### Library Not Found

```bash
# Error: LibraryNotFoundError: Shared library not found: build/my-languages.so

# Solution: Build the library
python scripts/fetch_grammars.py
python scripts/build_lib.py
```

#### Parser Version Mismatch

```bash
# Error: Language 'python' ABI version 14 doesn't match parser version 13

# Solution: Update py-tree-sitter
uv pip install git+https://github.com/tree-sitter/py-tree-sitter.git
```

#### Empty Results

```python
# Debug why no chunks are returned
import logging
logging.basicConfig(level=logging.DEBUG)

chunks = chunk_file("file.py", "python")
if not chunks:
    # Check if file has supported node types
    parser = get_parser("python")
    with open("file.py", "rb") as f:
        tree = parser.parse(f.read())
    
    # Inspect AST
    def print_tree(node, indent=0):
        print("  " * indent + node.type)
        for child in node.children:
            print_tree(child, indent + 1)
    
    print_tree(tree.root_node)
```

### Debug Information

```python
from chunker.parser import _factory, _registry

# Check loaded languages
print("Loaded languages:", _registry.list_languages())

# Check cache statistics
stats = _factory.get_stats()
print("Cache stats:", stats)

# Enable detailed logging
import logging
logging.getLogger("chunker").setLevel(logging.DEBUG)
```

### Getting Help

When reporting issues:

1. **Version Information**:
   ```python
   import sys
   import tree_sitter
   print(f"Python: {sys.version}")
   print(f"Tree-sitter: {tree_sitter.__version__}")
   ```

2. **Minimal Example**:
   ```python
   from chunker.chunker import chunk_file
   chunks = chunk_file("problem_file.py", "python")
   ```

3. **Error Traceback**: Include the full error message

4. **Environment**: OS, Python version, installation method

## See Also

- [API Reference](api-reference.md) - Complete API documentation
- [Plugin Development](plugin-development.md) - Creating custom language plugins
- [Configuration](configuration.md) - Configuration file reference
- [Performance Guide](performance-guide.md) - Optimization strategies
- [Export Formats](export-formats.md) - Detailed export documentation
- [Getting Started](getting-started.md) - Quick start tutorial  
- [Architecture](architecture.md) - System design details
- [Cookbook](cookbook.md) - Practical recipes and examples
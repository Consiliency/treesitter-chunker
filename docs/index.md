# Tree-sitter Chunker Documentation

Welcome to the Tree-sitter Chunker documentation! Tree-sitter Chunker is a powerful Python library for semantically chunking source code using Tree-sitter parsers. It intelligently splits code into meaningful units like functions, classes, and methods, making it perfect for code analysis, embeddings, and documentation generation.

## Quick Links

- **[Getting Started](getting-started.md)** - Installation and your first chunking project
- **[API Reference](api-reference.md)** - Complete API documentation with all 27 exported APIs
- **[User Guide](user-guide.md)** - Comprehensive usage guide with plugins and performance
- **[Plugin Development](plugin-development.md)** - Create custom language plugins
- **[Configuration](configuration.md)** - Configuration files and options
- **[Performance Guide](performance-guide.md)** - Optimization strategies and benchmarking
- **[Export Formats](export-formats.md)** - JSON, JSONL, and Parquet export options
- **[Cookbook](cookbook.md)** - Practical recipes and examples
- **[Architecture](architecture.md)** - System design and internals

### Phase 11: Text Processing
- **[Intelligent Fallback](intelligent_fallback.md)** - Automatic chunking method selection
- **[Token Limits](token_limits.md)** - LLM-aware token limit handling
- **[Markdown Processor](markdown_processor.md)** - Markdown document chunking
- **[Config Processor](config_processor.md)** - Configuration file chunking
- **[Log Processor](log_processor.md)** - Log file analysis and chunking

### Phase 12: Graph & Database Export
- **[Phase 12 Export](phase12_export.md)** - GraphML, Neo4j, DOT, SQLite, PostgreSQL exports
- **[GraphML Export](graphml_export.md)** - Detailed GraphML export documentation

## What is Tree-sitter Chunker?

Tree-sitter Chunker leverages the power of Tree-sitter parsers to understand code structure and extract semantic chunks. Unlike simple line-based splitting, it:

- ✨ **Understands Code Structure** - Extracts functions, classes, methods based on AST
- 🚀 **High Performance** - Efficient parser caching and pooling
- 🔧 **Language Agnostic** - Supports Python, JavaScript, Rust, C, C++
- 🧩 **Extensible** - Easy to add new languages and chunk types
- 🔒 **Thread Safe** - Designed for concurrent processing
- 📦 **Zero Config** - Works out of the box with sensible defaults

## Quick Example

```python
from chunker.chunker import chunk_file

# Chunk a Python file
chunks = chunk_file("example.py", "python")

# Process results
for chunk in chunks:
    print(f"{chunk.node_type} at lines {chunk.start_line}-{chunk.end_line}")
    print(f"  {chunk.content.split(chr(10))[0]}...")
```

## Features

### 🎯 Semantic Chunking
Extract meaningful code units:
- Functions and methods
- Classes and structures
- Nested contexts preserved
- Accurate line and byte positions
- Support for 5 languages with plugin architecture

### 🏎️ Performance Optimized
Built for speed and efficiency:
- **AST Caching**: 11.9x speedup for repeated files
- **Parallel Processing**: Process directories with multiple workers
- **Streaming Support**: Handle files larger than memory
- **LRU Parser Caching**: Efficient parser reuse
- **Thread-Safe Operations**: Safe concurrent processing

### 🛠️ Developer Friendly
Simple API with powerful capabilities:
- **Plugin System**: Easy language extensibility
- **Multiple Export Formats**: JSON, JSONL, Parquet
- **Rich Configuration**: TOML/YAML/JSON config files
- **Comprehensive CLI**: Batch processing, filtering, progress tracking
- **Detailed Documentation**: API reference, guides, and examples

### 🌐 Multi-Language Support
Built-in support for:
- Python (with decorators, async functions)
- JavaScript (including JSX, TypeScript)
- Rust (impl blocks, traits, macros)
- C (functions, structs, preprocessor)
- C++ (classes, templates, namespaces)

## Installation

```bash
# Using uv (recommended)
uv pip install -e ".[dev]"

# Install py-tree-sitter with ABI 15 support
uv pip install git+https://github.com/tree-sitter/py-tree-sitter.git

# Build language grammars
python scripts/fetch_grammars.py
python scripts/build_lib.py
```

## Use Cases

### 📊 Code Embeddings
Generate embeddings for semantic code search:
```python
chunks = chunk_file("module.py", "python")
embeddings = [generate_embedding(chunk.content) for chunk in chunks]
```

### 📝 Documentation Generation
Extract functions with docstrings:
```python
for chunk in chunks:
    if chunk.node_type == "function_definition":
        # Extract and process docstring
        generate_docs(chunk)
```

### 🔍 Code Analysis
Analyze code structure and complexity:
```python
functions = [c for c in chunks if "function" in c.node_type]
large_functions = [f for f in functions if f.end_line - f.start_line > 50]
```

### 🤖 AI/ML Applications
Prepare code for language models:
```python
# Create training data
for chunk in chunks:
    context = f"{chunk.node_type} in {chunk.parent_context or 'module'}"
    training_data.append({"code": chunk.content, "context": context})
```

## Documentation Overview

### For New Users

1. Start with **[Getting Started](getting-started.md)** to install and run your first example
2. Follow the tutorial to build practical tools
3. Check the **[Quick Reference Card](getting-started.md#quick-reference-card)**

### For Developers

1. Read the **[User Guide](user-guide.md)** for comprehensive coverage
2. Explore the **[API Reference](api-reference.md)** for detailed function documentation
3. Check the **[Cookbook](cookbook.md)** for ready-to-use solutions

### For Contributors

1. Study the **[Architecture](architecture.md)** document
2. Understand the plugin system and extension points
3. Review the troubleshooting guide

## Common Tasks

### List Available Languages
```python
from chunker.parser import list_languages
print(list_languages())
# Output: ['c', 'cpp', 'javascript', 'python', 'rust']
```

### Get Language Information
```python
from chunker.parser import get_language_info
info = get_language_info("python")
print(f"ABI Version: {info.version}")
print(f"Node types: {info.node_types_count}")
```

### Handle Errors Gracefully
```python
from chunker.exceptions import LanguageNotFoundError, LibraryNotFoundError

try:
    chunks = chunk_file("file.xyz", "xyz")
except LanguageNotFoundError as e:
    print(f"Language not supported: {e}")
except LibraryNotFoundError:
    print("Run: python scripts/build_lib.py")
```

### Process Multiple Files
```python
from concurrent.futures import ThreadPoolExecutor

def process_files(file_list, language):
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = executor.map(lambda f: chunk_file(f, language), file_list)
        return list(results)
```

## New Features

### 🔌 Plugin Architecture
- Dynamic plugin discovery and loading
- Abstract base class for custom languages
- Configuration management per plugin
- Built-in plugins for all supported languages

### ⚡ Performance Enhancements
- **AST Caching**: 11.9x speedup with intelligent caching
- **Parallel Processing**: `chunk_files_parallel()` and `chunk_directory_parallel()`
- **Streaming API**: `chunk_file_streaming()` for huge files
- **Configurable Workers**: Optimize for your CPU count

### 📤 Export Formats
- **JSON Export**: Flat, nested, or relational schemas
- **JSONL Export**: Streaming-friendly line-delimited JSON
- **Parquet Export**: Columnar format with compression and partitioning
- **Compression Support**: Gzip, Snappy, Brotli, LZ4, Zstd

### 🎛️ Advanced Configuration
- **Config Files**: Support for .chunkerrc, TOML, YAML, JSON
- **Language Settings**: Per-language chunk types and rules
- **Plugin Options**: Custom options for each language
- **Environment Variables**: System-wide configuration

### 🖥️ Enhanced CLI
- **Batch Processing**: Process entire directories
- **File Filtering**: Include/exclude patterns
- **Chunk Filtering**: By type and size
- **Progress Tracking**: Rich progress bars with ETA
- **Multiple Output Formats**: Table, JSON, JSONL

## Performance Tips

1. **Enable Caching**: Use ASTCache for 11.9x speedup on repeated files
2. **Parallel Processing**: Use `chunk_files_parallel()` for multiple files
3. **Stream Large Files**: Use `chunk_file_streaming()` for files >10MB
4. **Optimize Workers**: Set `max_workers` based on CPU count
5. **Choose Right Export**: Parquet for analytics, JSONL for streaming

## Community

### Getting Help

- Check the **[Troubleshooting Guide](user-guide.md#troubleshooting)**
- Review **[Common Issues](architecture.md#troubleshooting-guide)**
- Enable debug logging for detailed information

### Contributing

We welcome contributions! Areas of interest:

- Adding new language support
- Performance optimizations
- Documentation improvements
- Bug fixes and tests

### What's Next

Many features from the [ROADMAP.md](specs/ROADMAP.md) are now implemented:

- ✅ **Plugin System**: Complete with 5 built-in language plugins
- ✅ **Language Configuration**: Flexible framework with inheritance
- ✅ **Parallel Processing**: Full support with progress tracking
- ✅ **Streaming API**: Memory-efficient processing for large files
- ✅ **Export Formats**: JSON, JSONL, and Parquet with compression
- ✅ **Advanced CLI**: Batch processing, filtering, and configuration
- ✅ **AST Caching**: 11.9x performance improvement
- ✅ **Phase 9 Features**: Token counting, hierarchy, metadata, semantic merging, custom rules
- ✅ **Phase 10 Features**: Smart context, advanced queries, optimization, multi-language support
- ✅ **Phase 11 Features**: Text processing, intelligent fallback, token limits
- ✅ **Phase 12 Features**: Graph exports (GraphML, Neo4j, DOT) and database exports (SQLite, PostgreSQL)

Upcoming features (Phase 13):
- Pre-commit hooks and linting setup
- CI/CD pipeline automation
- AST visualization tools
- PyPI publishing and Docker support
- Platform-specific packages

## License

Tree-sitter Chunker is open source software. See the LICENSE file for details.

## Acknowledgments

Built on top of the excellent [Tree-sitter](https://tree-sitter.github.io/) parsing library.

---

*Happy chunking!* 🚀
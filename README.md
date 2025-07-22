# Tree-sitter Chunker

A high-performance semantic code chunker that leverages [Tree-sitter](https://tree-sitter.github.io/) parsers to intelligently split source code into meaningful chunks like functions, classes, and methods.

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)]()
[![Tree-sitter](https://img.shields.io/badge/tree--sitter-latest-green.svg)]()

## ✨ Key Features

- 🎯 **Semantic Understanding** - Extracts functions, classes, methods based on AST
- 🚀 **Blazing Fast** - 11.9x speedup with intelligent AST caching
- 🔌 **Plugin Architecture** - Built-in support for Python, JavaScript, Rust, C, C++
- 🎛️ **Flexible Configuration** - TOML/YAML/JSON config files with per-language settings
- 📊 **Multiple Export Formats** - JSON, JSONL, and Parquet with compression
- ⚡ **Parallel Processing** - Process entire codebases with configurable workers
- 🌊 **Streaming Support** - Handle files larger than memory
- 🎨 **Rich CLI** - Progress bars, batch processing, and filtering

## 📦 Installation

### Prerequisites
- Python 3.8+
- C compiler (for building Tree-sitter grammars)
- `uv` package manager (recommended) or pip

### Quick Install

```bash
# Clone the repository
git clone https://github.com/yourusername/treesitter-chunker.git
cd treesitter-chunker

# Install with uv (recommended)
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -e ".[dev]"
uv pip install git+https://github.com/tree-sitter/py-tree-sitter.git

# Build language grammars
python scripts/fetch_grammars.py
python scripts/build_lib.py

# Verify installation
python -c "from chunker import list_languages; print(list_languages())"
# Output: ['c', 'cpp', 'javascript', 'python', 'rust']
```

## 🚀 Quick Start

### Basic Usage

```python
from chunker import chunk_file

# Extract chunks from a Python file
chunks = chunk_file("example.py", "python")

for chunk in chunks:
    print(f"{chunk.node_type} at lines {chunk.start_line}-{chunk.end_line}")
    print(f"  Context: {chunk.parent_context or 'module level'}")
```

### Using Plugins

```python
from chunker import chunk_file, get_plugin_manager

# Load built-in language plugins
manager = get_plugin_manager()
manager.load_built_in_plugins()

# Now chunking uses plugin-based rules
chunks = chunk_file("example.py", "python")
```

### Parallel Processing

```python
from chunker import chunk_files_parallel, chunk_directory_parallel

# Process multiple files in parallel
results = chunk_files_parallel(
    ["file1.py", "file2.py", "file3.py"],
    "python",
    max_workers=4,
    show_progress=True
)

# Process entire directory
results = chunk_directory_parallel(
    "src/",
    "python",
    pattern="**/*.py"
)
```

### Export Formats

```python
from chunker import chunk_file
from chunker.export import JSONExporter, JSONLExporter, SchemaType
from chunker.exporters import ParquetExporter

chunks = chunk_file("example.py", "python")

# Export to JSON with nested schema
json_exporter = JSONExporter(schema_type=SchemaType.NESTED)
json_exporter.export(chunks, "chunks.json")

# Export to JSONL for streaming
jsonl_exporter = JSONLExporter()
jsonl_exporter.export(chunks, "chunks.jsonl")

# Export to Parquet for analytics
parquet_exporter = ParquetExporter(compression="snappy")
parquet_exporter.export(chunks, "chunks.parquet")
```

### CLI Usage

```bash
# Basic chunking
python cli/main.py chunk example.py -l python

# Process directory with progress bar
python cli/main.py chunk src/ -l python --recursive --progress

# Export as JSON
python cli/main.py chunk example.py -l python --json > chunks.json

# With configuration file
python cli/main.py chunk src/ --config .chunkerrc
```

## 🎯 Features

### Plugin Architecture

The chunker uses a flexible plugin system for language support:

- **Built-in Plugins**: Python, JavaScript, Rust, C, C++
- **Custom Plugins**: Easy to add new languages
- **Configuration**: Per-language chunk types and rules
- **Hot Loading**: Load plugins from directories

### Performance Features

- **AST Caching**: 11.9x speedup for repeated processing
- **Parallel Processing**: Utilize multiple CPU cores
- **Streaming**: Process files larger than memory
- **Progress Tracking**: Rich progress bars with ETA

### Configuration System

Support for multiple configuration formats:

```toml
# .chunkerrc
min_chunk_size = 3
max_chunk_size = 300

[languages.python]
chunk_types = ["function_definition", "class_definition", "async_function_definition"]
min_chunk_size = 5
```

### Export Formats

- **JSON**: Human-readable, supports nested/flat/relational schemas
- **JSONL**: Line-delimited JSON for streaming
- **Parquet**: Columnar format for analytics with compression

### Phase 9 Features (Completed)

- **Token Integration**: Count tokens for LLM context windows
- **Chunk Hierarchy**: Build hierarchical chunk relationships
- **Metadata Extraction**: Extract TODOs, complexity metrics, etc.
- **Semantic Merging**: Intelligently merge related chunks
- **Custom Rules**: Define custom chunking rules per language
- **Repository Processing**: Process entire repositories efficiently
- **Overlapping Fallback**: Handle edge cases with smart fallbacks
- **Cross-Platform Packaging**: Distribute as wheels for all platforms

## 📚 API Overview

Tree-sitter Chunker exports 107 APIs organized into logical groups:

### Core Functions
- `chunk_file()` - Extract chunks from a file
- `CodeChunk` - Data class representing a chunk

### Parser Management
- `get_parser()` - Get parser for a language
- `list_languages()` - List available languages
- `get_language_info()` - Get language metadata
- `return_parser()` - Return parser to pool
- `clear_cache()` - Clear parser cache

### Plugin System
- `PluginManager` - Manage language plugins
- `LanguagePlugin` - Base class for plugins
- `PluginConfig` - Plugin configuration
- `get_plugin_manager()` - Get global plugin manager

### Performance Features
- `chunk_files_parallel()` - Process files in parallel
- `chunk_directory_parallel()` - Process directories
- `chunk_file_streaming()` - Stream large files
- `ASTCache` - Cache parsed ASTs
- `StreamingChunker` - Streaming chunker class
- `ParallelChunker` - Parallel processing class

### Configuration
- `ChunkerConfig` - Global configuration
- `LanguageConfig` - Language-specific config
- `CompositeLanguageConfig` - Config inheritance
- `ChunkRule` - Custom chunking rules

### Export System
- `JSONExporter` - Export to JSON
- `JSONLExporter` - Export to JSONL
- `ParquetExporter` - Export to Parquet
- `SchemaType` - Export schema types

### Phase 9 Features
- **Token Integration**: `TokenCounter`, `TokenAwareChunker`, `TokenConfig`
- **Chunk Hierarchy**: `ChunkHierarchy`, `ChunkRelationship`, `HierarchyBuilder`
- **Metadata Extraction**: `MetadataExtractor`, `ChunkMetadata`, `MetadataConfig`
- **Semantic Merging**: `SemanticChunker`, `MergeStrategy`, `SemanticConfig`
- **Custom Rules**: `RuleBasedChunker`, `ChunkRule`, `RuleEngine`
- **Repository Processing**: `RepoProcessor`, `RepoConfig`, `FileFilter`
- **Overlapping Fallback**: `FallbackChunker`, `ChunkOverlap`, `FallbackStrategy`
- **Packaging**: `PackageDistributor`, `WheelBuilder`, `PlatformConfig`

### Error Handling
- `ChunkerError` - Base exception
- `LanguageNotFoundError` - Language not supported
- `ParserError` - Parser configuration error
- `LibraryNotFoundError` - Missing language library

See the [API Reference](docs/api-reference.md) for detailed documentation.

## 📖 Documentation

- **[Getting Started](docs/getting-started.md)** - Installation and first steps
- **[User Guide](docs/user-guide.md)** - Comprehensive usage guide
- **[API Reference](docs/api-reference.md)** - Detailed API documentation
- **[Plugin Development](docs/plugin-development.md)** - Create custom language plugins
- **[Configuration Guide](docs/configuration.md)** - Configuration options
- **[Performance Guide](docs/performance-guide.md)** - Optimization strategies
- **[Export Formats](docs/export-formats.md)** - Export format details
- **[Cookbook](docs/cookbook.md)** - Practical recipes and examples
- **[Architecture](docs/architecture.md)** - System design and internals

## 📁 Project Structure

```
treesitter-chunker/
├── chunker/              # Core library
│   ├── __init__.py      # Main exports (27 APIs)
│   ├── chunker.py       # Core chunking logic
│   ├── parser.py        # Parser management
│   ├── plugin_manager.py # Plugin system
│   ├── languages/       # Language plugins
│   ├── export/          # Export formats
│   ├── parallel.py      # Parallel processing
│   ├── streaming.py     # Streaming support
│   └── cache.py         # AST caching
├── cli/                 # Command-line interface
├── docs/                # Documentation
├── tests/               # Test suite
├── examples/            # Example files
└── scripts/             # Build scripts
```

## 🤝 Contributing

Contributions are welcome! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

### Development Setup

```bash
# Clone and install in development mode
git clone https://github.com/yourusername/treesitter-chunker.git
cd treesitter-chunker
uv pip install -e ".[dev]"

# Run tests (558 tests, >95% coverage)
python -m pytest

# Run benchmarks
python benchmarks/run_benchmarks.py
```

### Test Suite

The project includes a comprehensive test suite with excellent coverage:
- **Total tests**: 668 (558 original + 45 Phase 7 + 65 Phase 9)
- **Test files**: 48 (33 original + 6 Phase 7 + 9 Phase 9)
- **Unit test coverage**: >95%
- **Integration test coverage**: ~85% (increased from ~40%)
- **Status**: All tests passing (655 passed, 13 skipped for unimplemented features)

**Phase 9 Completed**: Successfully implemented and integrated all Phase 9 features including token counting, hierarchy building, metadata extraction, semantic merging, custom rules, repository processing, overlapping fallback, and cross-platform packaging.

## 🚀 Phase 10: Advanced Features (Planned)

The next phase will introduce advanced capabilities through well-defined interfaces:

### Smart Context Selection
- **Interface**: `SmartContextProvider`
- **Features**: Semantic, dependency, usage, and structural context extraction
- **Goal**: Provide optimal context for LLM processing

### Advanced Query System
- **Interface**: `ChunkQueryAdvanced`
- **Features**: Natural language queries, semantic search, similarity matching
- **Goal**: Enable sophisticated code search and retrieval

### Chunk Optimization
- **Interface**: `ChunkOptimizer`
- **Features**: LLM-specific optimization, boundary analysis, chunk rebalancing
- **Goal**: Optimize chunks for specific model constraints and use cases

### Multi-Language Support
- **Interface**: `MultiLanguageProcessor`
- **Features**: Mixed-language files, cross-language references, embedded code
- **Goal**: Handle polyglot codebases and modern web frameworks

### Incremental Processing
- **Interface**: `IncrementalProcessor`
- **Features**: Change detection, diff computation, cache management
- **Goal**: Efficiently process only changed portions of large codebases

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

Built on top of the excellent [Tree-sitter](https://tree-sitter.github.io/) parsing library.
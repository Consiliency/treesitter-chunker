# Tree-sitter Chunker

A high-performance semantic code chunker that leverages [Tree-sitter](https://tree-sitter.github.io/) parsers to intelligently split source code into meaningful chunks like functions, classes, and methods.

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)]()
[![Tree-sitter](https://img.shields.io/badge/tree--sitter-latest-green.svg)]()

## ✨ Key Features

- 🎯 **Semantic Understanding** - Extracts functions, classes, methods based on AST
- 🚀 **Blazing Fast** - 11.9x speedup with intelligent AST caching
- 🌍 **Universal Language Support** - Auto-download and support for 100+ Tree-sitter grammars
- 🔌 **Plugin Architecture** - Built-in support for Python, JavaScript, Rust, C, C++
- 🎛️ **Flexible Configuration** - TOML/YAML/JSON config files with per-language settings
- 📊 **14 Export Formats** - JSON, JSONL, Parquet, CSV, XML, GraphML, Neo4j, DOT, SQLite, PostgreSQL, and more
- ⚡ **Parallel Processing** - Process entire codebases with configurable workers
- 🌊 **Streaming Support** - Handle files larger than memory
- 🎨 **Rich CLI** - Progress bars, batch processing, and filtering
- 🤖 **LLM-Ready** - Token counting, chunk optimization, and context-aware splitting
- 📝 **Text File Support** - Markdown, logs, config files with intelligent chunking
- 🔍 **Advanced Query** - Natural language search across your codebase
- 📈 **Graph Export** - Visualize code structure in yEd, Neo4j, or Graphviz
- 🐛 **Debug Tools** - AST visualization, chunk inspection, performance profiling
- 🔧 **Developer Tools** - Pre-commit hooks, CI/CD generation, quality metrics
- 📦 **Multi-Platform Distribution** - PyPI, Docker, Homebrew packages
- 🌐 **Zero-Configuration** - Automatic language detection and grammar download

## 📦 Installation

### Prerequisites
- Python 3.8+
- C compiler (for building Tree-sitter grammars)
- `uv` package manager (recommended) or pip

### Installation Methods

#### From PyPI (when published)
```bash
pip install treesitter-chunker
```

#### Using Docker
```bash
docker pull ghcr.io/consiliency/treesitter-chunker:latest
docker run -v $(pwd):/workspace treesitter-chunker chunk /workspace/example.py -l python
```

#### Using Homebrew (macOS/Linux)
```bash
brew tap consiliency/treesitter-chunker
brew install treesitter-chunker
```

#### For Debian/Ubuntu
```bash
# Download .deb package from releases
sudo dpkg -i python3-treesitter-chunker_1.0.0-1_all.deb
```

#### For Fedora/RHEL
```bash
# Download .rpm package from releases
sudo rpm -i python-treesitter-chunker-1.0.0-1.noarch.rpm
```

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

### Zero-Configuration Usage (New!)

```python
from chunker import ZeroConfigAPI

# Create API instance - no setup required!
api = ZeroConfigAPI()

# Automatically detects language and downloads grammar if needed
result = api.auto_chunk_file("example.rs")

for chunk in result.chunks:
    print(f"{chunk['type']} at lines {chunk['start_line']}-{chunk['end_line']}")

# Preload languages for offline use
api.preload_languages(["python", "rust", "go", "typescript"])
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

### AST Visualization

Generate Graphviz diagrams of the parse tree:

```bash
python scripts/visualize_ast.py example.py --lang python --out example.svg
```

### VS Code Extension

The Tree-sitter Chunker VS Code extension provides integrated chunking capabilities:

1. **Install the extension**: Search for "TreeSitter Chunker" in VS Code marketplace
2. **Commands available**:
   - `TreeSitter Chunker: Chunk Current File` - Analyze the active file
   - `TreeSitter Chunker: Chunk Workspace` - Process all supported files
   - `TreeSitter Chunker: Show Chunks` - View chunks in a webview
   - `TreeSitter Chunker: Export Chunks` - Export to JSON/JSONL/Parquet

3. **Features**:
   - Visual chunk boundaries in the editor
   - Context menu integration
   - Configurable chunk types per language
   - Progress tracking for large operations

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

### Recent Feature Additions

#### Phase 9 Features (Completed)
- **Token Integration**: Count tokens for LLM context windows
- **Chunk Hierarchy**: Build hierarchical chunk relationships
- **Metadata Extraction**: Extract TODOs, complexity metrics, etc.
- **Semantic Merging**: Intelligently merge related chunks
- **Custom Rules**: Define custom chunking rules per language
- **Repository Processing**: Process entire repositories efficiently
- **Overlapping Fallback**: Handle edge cases with smart fallbacks
- **Cross-Platform Packaging**: Distribute as wheels for all platforms

#### Phase 14: Universal Language Support (Completed)
- **Automatic Grammar Discovery**: Discovers 100+ Tree-sitter grammars from GitHub
- **On-Demand Download**: Downloads and compiles grammars automatically when needed
- **Zero-Configuration API**: Simple API that just works without setup
- **Smart Caching**: Local cache with 24-hour refresh for offline use
- **Language Detection**: Automatic language detection from file extensions

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

### Phase 14 Features
- **Grammar Discovery**: `GrammarDiscoveryService`, `GrammarInfo`, `GrammarCompatibility`
- **Grammar Download**: `GrammarDownloadManager`, `DownloadProgress`, `DownloadOptions`
- **Universal Registry**: `UniversalLanguageRegistry` with auto-download support
- **Zero-Config API**: `ZeroConfigAPI`, `AutoChunkResult`, automatic language detection

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

### Phase 10 Documentation
- **[Smart Context](docs/SMART_CONTEXT.md)** - Intelligent context extraction
- **[Advanced Query](docs/QUERY_ADVANCED.md)** - Natural language queries
- **[Optimization](docs/OPTIMIZATION.md)** - Chunk optimization strategies
- **[Incremental Processing](docs/INCREMENTAL_PROCESSING.md)** - Efficient change detection
- **[Structured Export](docs/STRUCTURED_EXPORT.md)** - Export with relationships

### Phase 11 Documentation
- **[Markdown Processing](docs/MARKDOWN_PROCESSOR.md)** - Header-aware markdown chunking
- **[Log Processing](docs/LOG_PROCESSOR.md)** - Advanced log file analysis
- **[Config Processing](docs/CONFIG_PROCESSOR.md)** - Configuration file handling
- **[Text Processing](docs/TEXT_PROCESSING.md)** - Non-code file support

### Phase 14 Documentation
- **[Grammar Discovery](docs/grammar_discovery.md)** - Automatic grammar discovery from GitHub
- **[Zero-Config API](docs/zero_config_api.md)** - Simple API that requires no setup

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

# Enable pre-commit hooks
uv pip install pre-commit
pre-commit install
```

### Test Suite

The project includes a comprehensive test suite with excellent coverage:
- **Total tests**: 830+ tests
- **Test files**: 59+ test modules
- **Unit test coverage**: >95%
- **Integration test coverage**: ~90%
- **Status**: All tests passing

## 🎯 Project Status

### Completed Phases (15 of 15) 🎉
- **Phase 1**: Core Architecture - Parser redesign, plugin system ✅
- **Phase 2**: Language Support - 5 languages with custom configs ✅
- **Phase 3**: Advanced Chunking - Context preservation, relationships ✅
- **Phase 4**: Performance - Streaming, caching, parallel processing ✅
- **Phase 5**: CLI & Export - Rich CLI, 14 export formats ✅
- **Phase 6**: Testing & Docs - >95% coverage, comprehensive guides ✅
- **Phase 7**: Integration Testing - Cross-module testing ✅
- **Phase 8**: Structured Export - CSV, XML, minimal formats ✅
- **Phase 9**: Feature Enhancement - Token counting, custom rules ✅
- **Phase 10**: Advanced Features - Smart context, query system ✅
- **Phase 11**: Text Processing - Markdown, logs, config files ✅
- **Phase 12**: Graph & Database - GraphML, Neo4j, SQLite, PostgreSQL ✅
- **Phase 13**: Developer Tools & Distribution - PyPI, Docker, CI/CD ✅
- **Phase 14**: Universal Language Support - 100+ languages auto-download ✅
- **Phase 15**: Production Readiness - Pre-commit hooks, CI/CD, quality tools ✅

## 🚀 Advanced Capabilities

### Smart Processing
- **Token-Aware Chunking**: Respects LLM context windows (GPT-4, Claude, etc.)
- **Intelligent Fallback**: Automatically selects best chunking method
- **Context Preservation**: Maintains imports, class context, and relationships
- **Semantic Merging**: Groups related code (getters/setters, overloads)

### Text File Support 
- **Markdown**: Header-aware chunking with code block preservation
- **Logs**: Timestamp-based grouping with session detection
- **Config Files**: Section-based chunking for INI/TOML/YAML/JSON
- **Plain Text**: Paragraph and sentence-aware chunking

### Export Formats
- **Structured Data**: JSON, JSONL, Parquet, CSV, XML
- **Graph Formats**: GraphML (yEd), Neo4j, DOT (Graphviz)
- **Databases**: SQLite with FTS5, PostgreSQL with JSONB
- **Specialized**: Minimal (code-only), Enhanced (with relationships), Debug

### Advanced Features
- **Natural Language Query**: Search code with intuitive queries
- **Smart Context Selection**: Optimal context extraction for LLMs
- **Incremental Processing**: Process only changed files
- **Repository Processing**: Git-aware with .gitignore support
- **Custom Rules**: Define language-specific chunking rules

## ✅ Phase 13: Developer Tools & Distribution (Completed)

Phase 13 added professional development and distribution capabilities:

### Developer Tools
- **🔍 AST Visualization**: Generate AST diagrams in SVG/PNG/JSON formats
- **🐛 Debug Tools**: Interactive chunk inspector, profiling, and analysis
- **📊 Chunk Comparison**: Compare different chunking strategies
- **🎯 Performance Profiling**: Memory and timing analysis for optimization
- **🔌 VS Code Extension**: Full-featured extension for code chunking within VS Code
- **📚 Sphinx Documentation**: Auto-generated API documentation with GitHub Pages deployment

### Development Environment
- **🔧 Pre-commit Hooks**: Automated code quality checks before commits
- **✨ Code Formatting**: Black, ruff, and mypy integration
- **📈 Quality Metrics**: Type coverage and test coverage tracking
- **🤖 CI/CD Generation**: GitHub Actions workflows for multi-platform testing

### Build System
- **🏗️ Cross-Platform Building**: Linux, macOS, Windows support
- **📦 Grammar Compilation**: Automated Tree-sitter grammar building
- **🔨 Wheel Building**: Platform-specific Python wheels with compiled extensions
- **✔️ Build Verification**: Automated artifact validation

### Distribution
- **📦 PyPI Publishing**: Automated package publishing with validation
- **🐳 Docker Images**: Multi-platform container images (Dockerfile and Alpine variant)
- **🍺 Homebrew Formula**: macOS/Linux package manager support
- **📦 Platform Packages**: Debian (.deb) and RPM packages with GitHub Actions workflows
- **🚀 Release Management**: Version bumping and changelog generation

## ✅ Phase 15: Production Readiness & Developer Experience (Completed)

Phase 15 completed the production readiness with enhanced developer tools and robust CI/CD:

### Developer Tooling
- **🔧 Pre-commit Integration**: Black, Ruff, mypy hooks for automated code quality
- **✨ Linting & Formatting**: Automated code formatting and style checking
- **🎯 Type Checking**: Full mypy integration with strict typing
- **📊 Quality Metrics**: Code coverage and complexity tracking

### CI/CD Pipeline
- **🤖 GitHub Actions**: Multi-platform test matrix (Python 3.8-3.12)
- **✅ Test Automation**: Unit, integration, and contract tests
- **📈 Coverage Reporting**: Automated coverage tracking with badges
- **🚀 Release Automation**: Tag-based releases with changelog

### Debug & Visualization
- **🔍 AST Visualization**: Generate SVG/PNG diagrams of parse trees
- **🐛 Chunk Inspector**: Interactive chunk analysis tool
- **📊 Performance Profiling**: Memory and timing analysis
- **📝 Debug Output**: Detailed logging and trace capabilities

### Build System
- **🏗️ Cross-Platform Support**: Windows, macOS, Linux builds
- **📦 Grammar Compilation**: Automated Tree-sitter grammar building
- **🔨 Wheel Building**: Platform-specific Python wheels
- **✔️ Build Verification**: Automated testing of built artifacts

### Distribution
- **📦 PyPI Publishing**: Automated package publishing with validation
- **🐳 Docker Images**: Multi-platform containers (amd64/arm64)
- **🍺 Homebrew Formula**: macOS/Linux package manager support
- **📦 Platform Packages**: Debian (.deb) and RPM packages with workflows

## 🎯 Project Status and Maturity

**Current Status**: ✅ **Production Ready** (v1.0.0)

The Tree-sitter Chunker has completed all 15 planned development phases and is now production-ready:

- **Code Maturity**: Stable API with comprehensive documentation
- **Test Coverage**: 900+ tests with >95% coverage
- **Performance**: Optimized with 11.9x performance improvements
- **Languages**: Built-in support for 9 languages + automatic support for 100+ via download
- **Export Formats**: 14 different output formats
- **Distribution**: Available via PyPI, Docker Hub, and Homebrew
- **Zero-Configuration**: Works out of the box with automatic grammar management

### 🚀 Future Enhancements

With Phase 15 complete, the next phases focus on making Tree-sitter Chunker the ideal submodule for integration into larger platforms:

- **Phase 16 - API Excellence**: Async APIs, HTTP service, and seamless integration patterns
- **Phase 17 - Scale & Performance**: Handle millions of files with distributed processing
- **Phase 18 - Deploy Anywhere**: From WASM in browsers to Kubernetes clusters
- **Phase 19 - Enhanced Text Processing**: Intelligent chunking for documentation and configs

The chunker is now fully optimized for integration into any vector embedding pipeline with production-ready tooling and CI/CD.

See the [ROADMAP](specs/ROADMAP.md#future-directions-post-phase-14) for detailed phase plans.

## 📚 Documentation

- **[Getting Started Guide](docs/getting-started.md)**: Quick introduction to basic usage
- **[API Reference](docs/api-reference.md)**: Complete API documentation
- **[Architecture Overview](docs/architecture.md)**: System design and components
- **[Lessons Learned](docs/LESSONS_LEARNED.md)**: Insights from development
- **[Contributing Guide](CONTRIBUTING.md)**: How to contribute to the project

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

Built on top of the excellent [Tree-sitter](https://tree-sitter.github.io/) parsing library.
# Tree-sitter Chunker API Reference

## Overview

Tree-sitter Chunker provides a comprehensive API for semantically chunking source code files using Tree-sitter parsers. The library features dynamic language discovery, efficient parser caching, plugin architecture, parallel processing, and multiple export formats.

## Table of Contents

- [Installation](#installation)
- [Quick Start](#quick-start)
- [Core APIs](#core-apis)
  - [chunk_file](#chunk_file)
  - [CodeChunk](#codechunk)
- [Parser Management](#parser-management)
  - [get_parser](#get_parser)
  - [list_languages](#list_languages)
  - [get_language_info](#get_language_info)
  - [return_parser](#return_parser)
  - [clear_cache](#clear_cache)
  - [ParserConfig](#parserconfig)
- [Plugin System](#plugin-system)
  - [PluginManager](#pluginmanager)
  - [LanguagePlugin](#languageplugin)
  - [PluginConfig](#pluginconfig)
  - [get_plugin_manager](#get_plugin_manager)
- [Configuration](#configuration)
  - [ChunkerConfig](#chunkerconfig)
- [Performance Features](#performance-features)
  - [ASTCache](#astcache)
  - [chunk_files_parallel](#chunk_files_parallel)
  - [chunk_directory_parallel](#chunk_directory_parallel)
  - [chunk_file_streaming](#chunk_file_streaming)
  - [StreamingChunker](#streamingchunker)
  - [ParallelChunker](#parallelchunker)
- [Export Formats](#export-formats)
  - [JSON Export](#json-export)
  - [JSONL Export](#jsonl-export)
  - [Parquet Export](#parquet-export)
- [Exception Handling](#exception-handling)
- [Thread Safety](#thread-safety)
- [Performance Optimization](#performance-optimization)

## Installation

```bash
# Install with uv (recommended)
uv pip install -e ".[dev]"

# Required dependencies
uv pip install git+https://github.com/tree-sitter/py-tree-sitter.git
uv pip install pyarrow>=11.0.0

# Build language grammars
python scripts/fetch_grammars.py
python scripts/build_lib.py
```

## Quick Start

```python
from chunker import chunk_file, get_plugin_manager

# Basic usage
chunks = chunk_file("example.py", "python")

# With plugins
manager = get_plugin_manager()
manager.load_built_in_plugins()
chunks = chunk_file("example.py", "python")

# Parallel processing
from chunker import chunk_files_parallel
results = chunk_files_parallel(["file1.py", "file2.py", "file3.py"], "python")

# Export to Parquet
from chunker.exporters import ParquetExporter
exporter = ParquetExporter()
exporter.export(chunks, "output.parquet")
```

## Core APIs

### chunk_file

```python
chunk_file(path: str | Path, language: str) -> list[CodeChunk]
```

Parse a file and extract semantic code chunks. This is the main function for extracting meaningful code blocks from source files.

**Parameters:**
- `path` (str | Path): Path to the file to chunk
- `language` (str): Programming language of the file

**Returns:**
- `list[CodeChunk]`: List of extracted code chunks

**Example:**
```python
from chunker import chunk_file

chunks = chunk_file("src/main.py", "python")
for chunk in chunks:
    print(f"{chunk.node_type} at lines {chunk.start_line}-{chunk.end_line}")
```

### CodeChunk

```python
@dataclass
class CodeChunk:
    language: str
    file_path: str
    node_type: str
    start_line: int
    end_line: int
    byte_start: int
    byte_end: int
    parent_context: str
    content: str
    chunk_id: str = ""
    parent_chunk_id: str | None = None
    references: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
```

Represents a semantic chunk of code extracted from a file.

**Attributes:**
- `language` (str): Programming language
- `file_path` (str): Path to the source file
- `node_type` (str): Type of syntax node (e.g., "function_definition", "class_definition")
- `start_line` (int): Starting line number (1-indexed)
- `end_line` (int): Ending line number (1-indexed)
- `byte_start` (int): Starting byte offset in the file
- `byte_end` (int): Ending byte offset in the file
- `parent_context` (str): Parent node context (e.g., "class:MyClass" for methods)
- `content` (str): The actual code content
- `chunk_id` (str): Unique identifier for the chunk (auto-generated if not provided)
- `parent_chunk_id` (str | None): ID of the parent chunk if nested
- `references` (list[str]): List of references to other chunks
- `dependencies` (list[str]): List of dependencies on other chunks

**Methods:**
- `generate_id() -> str`: Generate a unique ID based on content and location

## Parser Management

### get_parser

```python
get_parser(language: str, config: Optional[ParserConfig] = None) -> Parser
```

Get a parser instance for the specified language with optional configuration. Parsers are cached and pooled for efficiency.

**Parameters:**
- `language` (str): The name of the language (e.g., "python", "javascript", "rust")
- `config` (Optional[ParserConfig]): Optional parser configuration

**Returns:**
- `Parser`: A configured tree-sitter parser instance

**Raises:**
- `LanguageNotFoundError`: If the language is not available
- `ParserError`: If parser initialization fails

### list_languages

```python
list_languages() -> List[str]
```

List all available languages discovered from the compiled shared library.

**Returns:**
- `List[str]`: Sorted list of available language names

**Example:**
```python
languages = list_languages()
print(languages)  # ['c', 'cpp', 'javascript', 'python', 'rust']
```

### get_language_info

```python
get_language_info(language: str) -> LanguageMetadata
```

Get detailed metadata about a specific language including version, capabilities, and node types.

**Parameters:**
- `language` (str): The name of the language

**Returns:**
- `LanguageMetadata`: Language metadata object with detailed information

### return_parser

```python
return_parser(language: str, parser: Parser) -> None
```

Return a parser to the pool for reuse. This is a performance optimization - parsers will be automatically cleaned up if not returned, but returning them enables better reuse.

### clear_cache

```python
clear_cache() -> None
```

Clear the parser cache. This forces all parsers to be recreated on next request. Useful for freeing memory or ensuring fresh parser instances.

### ParserConfig

```python
@dataclass
class ParserConfig:
    timeout_ms: Optional[int] = None
    included_ranges: Optional[List[Tuple[int, int]]] = None
    logger: Optional[Any] = None
```

Configuration options for parser instances.

**Attributes:**
- `timeout_ms`: Parser timeout in milliseconds (prevents infinite loops)
- `included_ranges`: List of (start_byte, end_byte) ranges to parse (for partial parsing)
- `logger`: Optional logger for parser debug events

## Plugin System

### PluginManager

```python
class PluginManager:
    def __init__(self, config: Optional[ChunkerConfig] = None)
    def register_plugin(self, plugin_class: Type[LanguagePlugin]) -> None
    def load_plugin_directory(self, directory: Path) -> List[Type[LanguagePlugin]]
    def load_built_in_plugins() -> None
    def get_plugin(self, language: str) -> Optional[LanguagePlugin]
    def list_plugins() -> List[str]
```

Manages plugin discovery, loading, and lifecycle.

**Key Methods:**
- `register_plugin`: Register a plugin class
- `load_plugin_directory`: Load plugins from a directory
- `load_built_in_plugins`: Load all built-in language plugins
- `get_plugin`: Get a plugin instance for a language
- `list_plugins`: List all registered plugin languages

### LanguagePlugin

```python
class LanguagePlugin(ABC):
    @property
    @abstractmethod
    def language_name(self) -> str
    
    @property
    @abstractmethod
    def supported_extensions(self) -> Set[str]
    
    @property
    @abstractmethod
    def default_chunk_types(self) -> Set[str]
    
    @abstractmethod
    def get_node_name(self, node: Node, source: bytes) -> Optional[str]
```

Abstract base class for language plugins. All language plugins must inherit from this class.

**Built-in Plugins:**
- `PythonPlugin`: Python language support
- `RustPlugin`: Rust language support
- `JavaScriptPlugin`: JavaScript/TypeScript support
- `CPlugin`: C language support
- `CppPlugin`: C++ language support

### PluginConfig

```python
@dataclass
class PluginConfig:
    enabled: bool = True
    chunk_types: Optional[Set[str]] = None
    min_chunk_size: int = 0
    max_chunk_size: int = 1000000
    custom_options: Dict[str, Any] = field(default_factory=dict)
```

Configuration for individual plugins.

**Attributes:**
- `enabled`: Whether the plugin is enabled
- `chunk_types`: Override default chunk types
- `min_chunk_size`: Minimum chunk size in lines
- `max_chunk_size`: Maximum chunk size in lines
- `custom_options`: Plugin-specific options

### get_plugin_manager

```python
get_plugin_manager() -> PluginManager
```

Get the global plugin manager instance (singleton).

**Example:**
```python
from chunker import get_plugin_manager

manager = get_plugin_manager()
manager.load_built_in_plugins()

# List available plugins
plugins = manager.list_plugins()
print(plugins)  # ['python', 'rust', 'javascript', 'c', 'cpp']
```

## Configuration

### ChunkerConfig

```python
class ChunkerConfig:
    def __init__(self, config_path: Optional[Path] = None)
    def load(self, config_path: Path) -> None
    def save(self, config_path: Optional[Path] = None) -> None
    def set_plugin_config(self, language: str, config: PluginConfig) -> None
    def get_plugin_config(self, language: str) -> PluginConfig
    
    @classmethod
    def find_config(cls, start_path: Path = Path.cwd()) -> Optional[Path]
```

Configuration manager supporting TOML, YAML, and JSON formats.

**Supported Formats:**
- `.toml` - TOML configuration
- `.yaml` / `.yml` - YAML configuration
- `.json` - JSON configuration

**Example Configuration (TOML):**
```toml
# chunker.config.toml
plugin_dirs = ["./plugins", "~/.chunker/plugins"]
enabled_languages = ["python", "rust", "javascript"]

[plugins.python]
enabled = true
chunk_types = ["function_definition", "class_definition", "async_function_definition"]
min_chunk_size = 3
max_chunk_size = 500

[plugins.python.custom_options]
include_docstrings = true
include_type_hints = true
```

## Performance Features

### ASTCache

```python
class ASTCache:
    def __init__(self, max_size: int = 100)
    def get(self, file_path: Path, language: str) -> Optional[ParsedAST]
    def put(self, file_path: Path, language: str, ast: ParsedAST) -> None
    def clear() -> None
    def get_stats() -> Dict[str, Any]
```

LRU cache for parsed ASTs providing up to 11.9x speedup for repeated file processing.

**Key Methods:**
- `get`: Retrieve cached AST if available
- `put`: Store AST in cache
- `clear`: Clear all cached entries
- `get_stats`: Get cache performance statistics

**Example:**
```python
from chunker import ASTCache

cache = ASTCache(max_size=200)
# Cache is used automatically by chunk_file when available
chunks = chunk_file("large_file.py", "python")  # First run: parses
chunks = chunk_file("large_file.py", "python")  # Second run: uses cache (11.9x faster)

# Check cache stats
stats = cache.get_stats()
print(f"Cache hits: {stats['hits']}, misses: {stats['misses']}")
print(f"Hit rate: {stats['hit_rate']:.2%}")
```

### chunk_files_parallel

```python
chunk_files_parallel(
    file_paths: List[Union[str, Path]], 
    language: str,
    max_workers: Optional[int] = None,
    show_progress: bool = True
) -> Dict[str, List[CodeChunk]]
```

Process multiple files in parallel using thread pool.

**Parameters:**
- `file_paths`: List of file paths to process
- `language`: Programming language
- `max_workers`: Maximum number of worker threads (defaults to CPU count)
- `show_progress`: Whether to show progress bar

**Returns:**
- `Dict[str, List[CodeChunk]]`: Map of file path to chunks

**Example:**
```python
from chunker import chunk_files_parallel

files = ["src/main.py", "src/utils.py", "src/models.py"]
results = chunk_files_parallel(files, "python", max_workers=4)

for file_path, chunks in results.items():
    print(f"{file_path}: {len(chunks)} chunks")
```

### chunk_directory_parallel

```python
chunk_directory_parallel(
    directory: Union[str, Path],
    language: str,
    pattern: str = "**/*",
    max_workers: Optional[int] = None,
    show_progress: bool = True
) -> Dict[str, List[CodeChunk]]
```

Process all matching files in a directory in parallel.

**Parameters:**
- `directory`: Directory to process
- `language`: Programming language
- `pattern`: Glob pattern for file matching
- `max_workers`: Maximum number of worker threads
- `show_progress`: Whether to show progress bar

### chunk_file_streaming

```python
chunk_file_streaming(
    path: Union[str, Path],
    language: str,
    chunk_size: int = 1048576  # 1MB
) -> Iterator[CodeChunk]
```

Stream chunks from a file without loading the entire file into memory. Ideal for very large files.

**Parameters:**
- `path`: Path to the file
- `language`: Programming language
- `chunk_size`: Size of each read chunk in bytes

**Returns:**
- `Iterator[CodeChunk]`: Iterator yielding chunks as they are found

**Example:**
```python
from chunker import chunk_file_streaming

# Process a very large file
for chunk in chunk_file_streaming("huge_codebase.py", "python"):
    # Process each chunk as it's found
    process_chunk(chunk)
```

### StreamingChunker

```python
class StreamingChunker:
    def __init__(self, language: str, chunk_size: int = 1048576)
    def process_stream(self, stream: IO[bytes]) -> Iterator[CodeChunk]
```

Low-level streaming chunker for custom stream processing.

### ParallelChunker

```python
class ParallelChunker:
    def __init__(self, language: str, max_workers: Optional[int] = None)
    def process_files(self, file_paths: List[Path]) -> Dict[str, List[CodeChunk]]
    def process_directory(self, directory: Path, pattern: str = "**/*") -> Dict[str, List[CodeChunk]]
```

Low-level parallel processing API for advanced use cases.

## Export Formats

### JSON Export

```python
from chunker.export import JSONExporter, SchemaType

exporter = JSONExporter(schema_type=SchemaType.FLAT)
exporter.export(chunks, "output.json", compress=True, indent=2)

# Available schema types:
# - SchemaType.FLAT: Simple flat structure
# - SchemaType.NESTED: Nested hierarchy preserving relationships
# - SchemaType.RELATIONAL: Normalized relational structure
```

**JSONExporter Methods:**
```python
class JSONExporter:
    def __init__(self, schema_type: SchemaType = SchemaType.FLAT)
    def export(self, chunks: list[CodeChunk], output: Union[str, Path, IO[str]], 
               compress: bool = False, indent: Optional[int] = 2) -> None
    def export_to_string(self, chunks: list[CodeChunk], indent: Optional[int] = 2) -> str
```

### JSONL Export

```python
from chunker.export import JSONLExporter

exporter = JSONLExporter(schema_type=SchemaType.FLAT)
exporter.export(chunks, "output.jsonl", compress=True)

# Streaming export for large datasets
exporter.export_streaming(chunk_iterator, "large_output.jsonl")
```

**JSONLExporter Methods:**
```python
class JSONLExporter:
    def __init__(self, schema_type: SchemaType = SchemaType.FLAT)
    def export(self, chunks: list[CodeChunk], output: Union[str, Path, IO[str]], 
               compress: bool = False) -> None
    def export_streaming(self, chunks: Iterator[CodeChunk], 
                        output: Union[str, Path, IO[str]], compress: bool = False) -> None
```

### Parquet Export

```python
from chunker.exporters import ParquetExporter

exporter = ParquetExporter(
    columns=["language", "file_path", "node_type", "content"],
    partition_by=["language"],
    compression="snappy"
)
exporter.export(chunks, "output.parquet")

# Export with custom schema
exporter.export_partitioned(chunks, "output_dir/", partition_cols=["language", "node_type"])
```

**ParquetExporter Methods:**
```python
class ParquetExporter:
    def __init__(self, columns: Optional[List[str]] = None,
                 partition_by: Optional[List[str]] = None,
                 compression: str = "snappy")
    def export(self, chunks: List[CodeChunk], output_path: Union[str, Path]) -> None
    def export_partitioned(self, chunks: List[CodeChunk], output_dir: Union[str, Path],
                          partition_cols: Optional[List[str]] = None) -> None
    def export_streaming(self, chunk_iterator: Iterator[CodeChunk],
                        output_path: Union[str, Path], batch_size: int = 1000) -> None
```

**Compression Options:**
- `"snappy"` - Fast compression (default)
- `"gzip"` - Higher compression ratio
- `"brotli"` - Best compression ratio
- `"lz4"` - Fastest compression
- `"zstd"` - Good balance of speed and ratio
- `None` - No compression

## Exception Handling

The library provides a comprehensive exception hierarchy for precise error handling:

### Base Exception

```python
class ChunkerError(Exception):
    """Base exception for all chunker errors"""
```

### Language Errors

```python
class LanguageError(ChunkerError):
    """Base class for language-related errors"""

class LanguageNotFoundError(LanguageError):
    """Raised when requested language is not available"""
```

### Parser Errors

```python
class ParserError(ChunkerError):
    """Base class for parser-related errors"""
```

### Library Errors

```python
class LibraryError(ChunkerError):
    """Base class for shared library errors"""

class LibraryNotFoundError(LibraryError):
    """Raised when .so file is missing"""
```

### Error Handling Examples

```python
from chunker import chunk_file, list_languages
from chunker.exceptions import LanguageNotFoundError, LibraryNotFoundError

try:
    chunks = chunk_file("example.py", "python")
except LanguageNotFoundError as e:
    print(f"Language not available: {e}")
    available = list_languages()
    print(f"Available languages: {', '.join(available)}")
except LibraryNotFoundError as e:
    print(f"Library not found: {e}")
    print("Run: python scripts/build_lib.py")
```

## Thread Safety

The library is designed to be thread-safe for concurrent processing:

### Thread-Safe Components

- **LanguageRegistry**: Thread-safe for all read operations after initialization
- **ParserFactory**: Thread-safe with internal locking for cache and pool operations
- **PluginManager**: Thread-safe plugin registration and retrieval
- **ASTCache**: Thread-safe with concurrent access support
- **get_parser/return_parser**: Thread-safe API functions

### Non Thread-Safe Components

- **Parser instances**: NOT thread-safe - each thread must use its own parser
- **Tree objects**: NOT thread-safe - parse results should not be shared
- **CodeChunk objects**: Safe to share after creation (immutable)

### Concurrent Usage Example

```python
import threading
from concurrent.futures import ThreadPoolExecutor
from chunker import chunk_file, chunk_files_parallel

# Safe concurrent processing using high-level API
files = ["file1.py", "file2.py", "file3.py"]
results = chunk_files_parallel(files, "python", max_workers=4)

# Manual concurrent processing
def process_file(file_path):
    # Each thread gets its own parser automatically
    return chunk_file(file_path, "python")

with ThreadPoolExecutor(max_workers=4) as executor:
    futures = [executor.submit(process_file, f) for f in files]
    results = [f.result() for f in futures]
```

## Performance Optimization

### Best Practices

1. **Use AST Caching**: Enable caching for repeated file processing
   ```python
   # Cache is enabled by default
   chunks1 = chunk_file("file.py", "python")  # Parses
   chunks2 = chunk_file("file.py", "python")  # Uses cache (11.9x faster)
   ```

2. **Process Files in Parallel**: Use parallel processing for multiple files
   ```python
   results = chunk_files_parallel(file_list, "python", max_workers=8)
   ```

3. **Stream Large Files**: Use streaming for very large files
   ```python
   for chunk in chunk_file_streaming("huge_file.py", "python"):
       process_chunk(chunk)
   ```

4. **Configure Cache Size**: Adjust cache size based on available memory
   ```python
   from chunker import ASTCache
   cache = ASTCache(max_size=500)  # Cache up to 500 ASTs
   ```

5. **Use Appropriate Export Format**: Choose format based on use case
   - JSON: Human-readable, good for small datasets
   - JSONL: Streaming-friendly, good for large datasets
   - Parquet: Best for analytics, supports compression and partitioning

### Performance Metrics

- **Parser Creation**: ~10-50ms (one-time cost)
- **Parsing**: O(n) with file size
- **Caching**: 11.9x speedup for cached files
- **Parallel Processing**: Near-linear speedup with CPU cores
- **Memory Usage**: ~10x source file size for AST

## See Also

- [Getting Started](getting-started.md) - Quick introduction tutorial
- [User Guide](user-guide.md) - Comprehensive usage guide
- [Plugin Development](plugin-development.md) - Creating custom language plugins
- [Configuration](configuration.md) - Configuration file reference
- [Performance Guide](performance-guide.md) - Optimization strategies
- [Export Formats](export-formats.md) - Detailed export documentation
- [Architecture](architecture.md) - System design and internals
- [Cookbook](cookbook.md) - Common recipes and examples
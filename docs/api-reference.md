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
# Install from PyPI (recommended)
pip install treesitter-chunker

# With visualization tools (requires graphviz)
pip install "treesitter-chunker[viz]"

# With all optional dependencies
pip install "treesitter-chunker[all]"
```

The main wheel is pure Python. The pinned grammar pack loads native parsers,
which may be downloaded on first use; prefetch for offline operation. See
[packaging](packaging.md) for platform requirements.

### Development Installation

If you want to contribute or need the latest development version:

```bash
# Clone the repository
git clone https://github.com/Consiliency/treesitter-chunker.git
cd treesitter-chunker

# Install the locked project environment
uv sync --locked --all-extras
```

## Quick Start

Run this with a real `example.py` fixture. All process-worker setup and exports
are under the main guard so spawn/forkserver workers do not repeat them.

```python
from pathlib import Path
from chunker import chunk_file
from chunker.plugin_manager import get_plugin_manager
from chunker.parallel import chunk_files_parallel
from chunker.exporters import ParquetExporter

if __name__ == "__main__":
    chunks = chunk_file("example.py", "python")

    # Explicit plugin path; core chunk_file does not use registered plugins
    manager = get_plugin_manager()
    plugin_chunks = manager.chunk_file(Path("example.py"), "python")

    results = chunk_files_parallel(
        ["example.py"], "python", num_workers=2, use_cache=False
    )
    ParquetExporter().export(chunks, "output.parquet")
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
from chunker.core import chunk_file

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

Get a parser instance for the specified language with optional configuration. Default parsers are owned by the calling thread; configured calls create fresh, uncached parsers.

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

List registered parser languages. Parser availability and verified semantic
extraction are separate; see [language coverage](language-coverage.md).

**Returns:**
- `List[str]`: Sorted list of available language names

**Example:**
```python
languages = list_languages()
print(languages)  # Availability depends on the installed grammars
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

Compatibility no-op for thread-owned parsers. Use `acquire_parser()` as a
context manager when a parser must return to the shared idle pool. See
[parser concurrency](performance-guide/parser-concurrency.md).

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
    included_ranges: Optional[List[tree_sitter.Range]] = None
    logger: Optional[Any] = None
```

Configuration options for parser instances.

Invalid or unsupported configuration raises `ParserConfigError` before factory
language lookup, including requests for unavailable languages. Omit unsupported
options when requesting on-demand grammar acquisition.

**Attributes:**
- `timeout_ms`: Applied only on runtimes exposing the legacy timeout API.
  Any explicit value, including zero, raises `ParserConfigError` on the pinned
  0.26 runtime. Omit this option there; no parse deadline is provided.
- `included_ranges`: List of Tree-sitter `Range` objects for partial parsing
- `logger`: Any non-`None` value raises `ParserConfigError`. Configure Python
  application logging separately; this field does not attach a parser logger.

## Plugin System

### PluginManager

```python
from pathlib import Path
from chunker import PluginManager, PluginConfig

manager = PluginManager()
manager.load_builtin_plugins()
print(manager.registry.list_languages())
chunks = manager.chunk_file(
    Path("example.py"), "python", config=PluginConfig(min_chunk_size=1)
)
```

`load_plugins_from_directory(Path(...))` discovers and registers plugins from
a directory. Register a class explicitly with `manager.registry.register(cls)`.
`get_plugin(language, config=None)` returns a plugin instance. The constructor
takes no configuration object; pass a `PluginConfig` to the consuming method.

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
    min_chunk_size: int = 1
    max_chunk_size: int | None = None
    custom_options: Dict[str, Any] = field(default_factory=dict)
```

Configuration for individual plugins.

**Attributes:**
- `enabled`: Application selection flag; the manager does not enforce it
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
from chunker.plugin_manager import get_plugin_manager

manager = get_plugin_manager()  # Built-ins are already loaded

# List available plugins
plugins = manager.registry.list_languages()
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

For file schemas, discovery and actual consumers, see
[Configuration](configuration.md). CLI `.chunkerrc` settings and
`ChunkerConfig` plugin settings are separate interfaces.

## Performance Features

### ASTCache

`from chunker import ASTCache` exposes a SQLite cache of **chunk lists**:

```python
from pathlib import Path
from chunker import ASTCache, chunk_file

path = Path("example.py").resolve()
cache = ASTCache(Path(".cache/chunks"))
chunks = cache.get_cached_chunks(path, "python")
if chunks is None:
    chunks = chunk_file(path, "python")
    cache.cache_chunks(path, "python", chunks)
print(cache.get_cache_stats())
```

`get_cache_stats()` returns `total_files`, `total_size_bytes` and `cache_db_size`.
`invalidate_cache(path)` removes a file; `invalidate_cache()` removes all entries.
There is no `max_size`, `get_stats()` or LRU/TTL policy. Direct `chunk_file()`
does not use this cache automatically. See [performance](performance-guide.md)
for invalidation limits.

Parallel helpers default to `use_cache=True` and share
`~/.cache/treesitter-chunker/ast_cache.db`; no directory override is exposed.
Disable with `use_cache=False` unless you manage invalidation when parser pins
or extraction mode/options change.

### chunk_files_parallel

Import from `chunker.parallel`. Returns `dict[Path, list[CodeChunk]]` using a
**process pool**, with `num_workers`, `use_cache` and `use_streaming` options:

```python
from chunker.parallel import chunk_files_parallel

if __name__ == "__main__":
    results = chunk_files_parallel(
        ["example.py"], "python", num_workers=2, use_cache=False
    )
    for path, chunks in results.items():
        print(path, len(chunks))
```

### chunk_directory_parallel

Import from `chunker.parallel`, or use its alias `chunker.chunk_directory`.
Accepts `extensions=[".py"]`, `num_workers`, `use_cache` and `use_streaming`.
It recurses through the directory; it does not accept `pattern` or `show_progress`.

### chunk_file_streaming

Import from `chunker` or `chunker.streaming`. Takes `path`, `language` and
`include_retrieval_metadata=False`; yields `CodeChunk` objects. It memory-maps
source and parses a whole tree, then yields chunks lazily. It does not accept a
read-buffer `chunk_size`. See [performance](performance-guide.md) for language
parity limitations.

### StreamingChunker

Import from `chunker.streaming`. Construct with `StreamingChunker(language)`;
call `chunk_file_streaming(Path(...))`. There is no `process_stream()` method.

### ParallelChunker

Import from `chunker.parallel`. Construct with `language`, `num_workers`,
`use_cache`, `use_streaming` and optional `timeout_seconds`. Methods are
`chunk_files_parallel(list[Path])` and
`chunk_directory_parallel(Path, extensions=None)`. A timeout bounds result
collection; it does not guarantee termination of an already running worker.

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
exporter.stream_export(chunk_iterator, "large_output.jsonl")
```

**JSONLExporter Methods:**
```python
class JSONLExporter:
    def __init__(self, schema_type: SchemaType = SchemaType.FLAT)
    def export(self, chunks: list[CodeChunk], output: Union[str, Path, IO[str]], 
               compress: bool = False) -> None
    def stream_export(self, chunks: Iterator[CodeChunk],
                        output: Union[str, Path, IO[str]], compress: bool = False) -> None
```

### Parquet Export

Use a dedicated directory for partitioned datasets, not a file with a suffix.
Re-exporting into an existing dataset with a different partition specification
raises an error; use a fresh directory.

```python
from chunker.exporters import ParquetExporter

exporter = ParquetExporter(
    columns=["language", "file_path", "node_type", "content"],
    partition_by=["language"],
    compression="snappy"
)
exporter.export(chunks, "partitioned_output/")

# Export with custom schema
ParquetExporter(partition_by=["language", "node_type"]).export(chunks, "output_dir/")
```

**ParquetExporter Methods:**
```python
class ParquetExporter:
    def __init__(self, columns: Optional[List[str]] = None,
                 partition_by: Optional[List[str]] = None,
                 compression: str = "snappy")
    def export(self, chunks: List[CodeChunk], output_path: Union[str, Path]) -> None
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
from chunker.core import chunk_file
from chunker.parser import list_languages
from chunker.exceptions import LanguageNotFoundError, LibraryNotFoundError

try:
    chunks = chunk_file("example.py", "python")
except LanguageNotFoundError as e:
    print(f"Language not available: {e}")
    available = list_languages()
    print(f"Available languages: {', '.join(available)}")
except LibraryNotFoundError as e:
    print(f"Library not found: {e}")
    print("Check the locked parser stack and grammar availability")
```

## Thread Safety

`get_parser()` owns its mutable parser per thread; do not pass it to another
thread. `acquire_parser()` provides an exclusive lease. See
[parser concurrency](performance-guide/parser-concurrency.md). Treat plugin
registration as initialization; do not assume arbitrary shared plugin mutation
is synchronized. The SQLite chunk cache opens a separate connection per operation.

## Performance Optimization

See [Performance Guide](performance-guide.md) for explicit caching, process-pool
examples, streaming limits and reproducible measurement. No fixed speedup or
near-linear scaling is guaranteed.

## See Also

- [Getting Started](getting-started.md) - Quick introduction tutorial
- [User Guide](user-guide.md) - Comprehensive usage guide
- [Plugin Development](plugin-development.md) - Creating custom language plugins
- [Configuration](configuration.md) - Configuration file reference
- [Performance Guide](performance-guide.md) - Optimization strategies
- [Export Formats](export-formats.md) - Detailed export documentation
- [Architecture](architecture.md) - System design and internals
- [Cookbook](cookbook.md) - Common recipes and examples

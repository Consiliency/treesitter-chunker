# Plugin Architecture Documentation

## Overview

The treesitter-chunker plugin architecture provides a flexible and extensible system for adding support for new programming languages. The architecture consists of several key components:

1. **Abstract Base Plugin Class** - Defines the interface all language plugins must implement
2. **Plugin Manager** - Handles plugin discovery, loading, and lifecycle management
3. **Plugin Registry** - Maintains a registry of available plugins and their configurations
4. **Configuration System** - Supports TOML/YAML configuration files for customizing plugin behavior

## Architecture Components

### 1. LanguagePlugin Base Class (`chunker/languages/base.py`)

The abstract base class that all language plugins must inherit from. Key methods and properties:

```python
class LanguagePlugin(ABC):
    @property
    @abstractmethod
    def language_name(self) -> str:
        """Return the language identifier (e.g., 'python', 'rust')."""
        
    @property
    @abstractmethod
    def supported_extensions(self) -> Set[str]:
        """Return set of file extensions this plugin handles."""
        
    @property
    @abstractmethod
    def default_chunk_types(self) -> Set[str]:
        """Return default set of node types to chunk."""
        
    @abstractmethod
    def get_node_name(self, node: Node, source: bytes) -> Optional[str]:
        """Extract a human-readable name from a node."""
```

### 2. Plugin Manager (`chunker/plugin_manager.py`)

Manages plugin discovery and loading:

- **Dynamic Discovery**: Automatically discovers plugin classes from Python files
- **Directory Support**: Can load plugins from multiple directories
- **Built-in Plugins**: Automatically loads plugins from the `chunker/languages` directory
- **Lazy Loading**: Plugins are only instantiated when needed

### 3. Plugin Registry

Maintains the registry of available plugins:

- Maps language names to plugin classes
- Maps file extensions to languages
- Manages plugin instances with caching
- Supports custom configurations per plugin instance

### 4. Configuration System (`chunker/config.py`)

Flexible configuration management:

- **Multiple Formats**: Supports TOML, YAML, and JSON
- **Hierarchical Configuration**: Global defaults with per-language overrides
- **Auto-discovery**: Searches for config files up the directory tree
- **Custom Options**: Plugins can define their own configuration options

## Creating a New Language Plugin

To create a plugin for a new language:

1. **Create a new Python file** in `chunker/languages/` or a custom plugin directory:

```python
from typing import Set, Optional
from tree_sitter import Node
from .base import LanguagePlugin
from ..chunker import CodeChunk

class MyLanguagePlugin(LanguagePlugin):
    @property
    def language_name(self) -> str:
        return "mylang"
    
    @property
    def supported_extensions(self) -> Set[str]:
        return {".ml", ".mli"}
    
    @property
    def default_chunk_types(self) -> Set[str]:
        return {"function", "class", "module"}
    
    def get_node_name(self, node: Node, source: bytes) -> Optional[str]:
        # Extract name from AST node
        for child in node.children:
            if child.type == "identifier":
                return source[child.start_byte:child.end_byte].decode('utf-8')
        return None
```

2. **Optional: Override processing methods** for custom behavior:

```python
def process_node(self, node: Node, source: bytes, 
                 file_path: str, parent_context: Optional[str] = None) -> Optional[CodeChunk]:
    # Custom node processing logic
    
def get_context_for_children(self, node: Node, chunk: CodeChunk) -> str:
    # Build context string for nested definitions
    
def should_include_chunk(self, chunk: CodeChunk) -> bool:
    # Custom filtering logic
```

## Configuration

### Configuration File Structure

**YAML Example** (`chunker.config.yaml`):
```yaml
chunker:
  plugin_dirs:
    - ./custom_plugins
    - ~/.chunker/plugins
  enabled_languages:
    - python
    - rust
    - javascript
  default_plugin_config:
    min_chunk_size: 3
    max_chunk_size: 500

languages:
  python:
    enabled: true
    chunk_types:
      - function_definition
      - class_definition
    include_docstrings: true  # custom option
```

**TOML Example** (`chunker.config.toml`):
```toml
[chunker]
plugin_dirs = ["./custom_plugins", "~/.chunker/plugins"]
enabled_languages = ["python", "rust", "javascript"]

[chunker.default_plugin_config]
min_chunk_size = 3
max_chunk_size = 500

[languages.python]
enabled = true
chunk_types = ["function_definition", "class_definition"]
include_docstrings = true
```

### Configuration Options

#### Global Options:
- `plugin_dirs`: List of directories to search for plugins
- `enabled_languages`: List of languages to enable (if not specified, all are enabled)
- `default_plugin_config`: Default configuration for all plugins

#### Plugin Configuration:
- `enabled`: Whether the plugin is active
- `chunk_types`: Override default node types to chunk
- `min_chunk_size`: Minimum lines for a chunk
- `max_chunk_size`: Maximum lines for a chunk
- Custom options specific to each plugin

## Usage

### Basic Usage

```python
from chunker import get_plugin_manager

# Get the global plugin manager
manager = get_plugin_manager()

# Chunk a file
chunks = manager.chunk_file("example.py")
for chunk in chunks:
    print(f"{chunk.node_type} at lines {chunk.start_line}-{chunk.end_line}")
```

### With Custom Configuration

```python
from chunker import PluginManager, ChunkerConfig, PluginConfig

# Load configuration from file
config = ChunkerConfig.find_config()
if config:
    config.load(config)

# Or create configuration programmatically
manager = PluginManager()
plugin_config = PluginConfig(
    chunk_types={"function_definition", "class_definition"},
    min_chunk_size=5,
    max_chunk_size=100
)

# Get plugin with custom config
plugin = manager.get_plugin("python", plugin_config)
chunks = plugin.chunk_file("example.py")
```

### Loading Custom Plugins

```python
from pathlib import Path
from chunker import get_plugin_manager

manager = get_plugin_manager()

# Load plugins from a custom directory
custom_dir = Path("./my_plugins")
loaded = manager.load_plugins_from_directory(custom_dir)
print(f"Loaded {loaded} plugins from {custom_dir}")

# Now use the newly loaded plugins
chunks = manager.chunk_file("example.mylang")
```

## Built-in Plugins

### Python Plugin
- Extensions: `.py`, `.pyi`
- Default chunks: `function_definition`, `async_function_definition`, `class_definition`, `decorated_definition`
- Custom options: `include_docstrings`

### Rust Plugin
- Extensions: `.rs`
- Default chunks: `function_item`, `impl_item`, `struct_item`, `enum_item`, `trait_item`, etc.
- Custom options: `include_tests`

### JavaScript Plugin
- Extensions: `.js`, `.jsx`, `.mjs`, `.cjs`, `.ts`, `.tsx`
- Default chunks: `function_declaration`, `function_expression`, `arrow_function`, `class_declaration`, etc.
- Custom options: `include_jsx`

## Advanced Features

### Plugin Discovery

The plugin manager automatically discovers plugins by:
1. Scanning Python files in plugin directories
2. Finding all classes that inherit from `LanguagePlugin`
3. Registering them automatically

### Parser Integration

Each plugin gets a tree-sitter parser instance:
- Parsers are created lazily when needed
- The parser language must match the plugin's `language_name`
- Parsers are cached for efficiency

### Context Building

Plugins can build hierarchical context for nested definitions:
- Parent context is passed to child nodes
- Useful for showing "class.method" or "module.function" relationships
- Customizable per language

## Testing

Run the test suite to verify plugin functionality:

```bash
pytest tests/test_plugin_system.py -v
```

## Installation

1. Install dependencies:
```bash
pip install -e .
```

2. Build tree-sitter grammars:
```bash
python scripts/fetch_grammars.py
```

3. Create a configuration file (optional):
```bash
cp examples/chunker.config.yaml .
```

## Handling Ambiguous File Extensions

Some file extensions are used by multiple languages. The plugin system handles these intelligently:

### .h Files (C/C++)

The `.h` extension is commonly used by both C and C++ projects. The plugin system handles this ambiguity through:

1. **Automatic Detection**: The system examines file content for C++ features like:
   - Classes and namespaces
   - Templates
   - C++ keywords (virtual, override, final)
   - STL includes
   - Scope resolution operators (::)

2. **Fallback Behavior**: If detection fails or is uncertain, defaults to C

3. **Manual Override**: You can always specify the language explicitly

Example usage:
```python
# Automatic detection based on content
chunks = manager.chunk_file("example.h")  # Detects C++ features or defaults to C

# Explicit language specification
chunks = manager.chunk_file("example.h", language="cpp")  # Force C++
chunks = manager.chunk_file("example.h", language="c")    # Force C
```

### Extension Sharing

When multiple plugins claim the same extension:
- The system logs an informational message (not a warning)
- The last registered plugin takes precedence for basic extension mapping
- Content-based detection provides intelligent handling for ambiguous files
- Users can always override with explicit language specification

## Troubleshooting

### Plugin Not Found
- Check that the plugin file is in a configured plugin directory
- Ensure the plugin class inherits from `LanguagePlugin`
- Verify the language name matches the parser name

### Configuration Not Loading
- Check file format matches extension (.yaml, .toml, .json)
- Verify YAML/TOML syntax is correct
- Use `ChunkerConfig.find_config()` to locate config files

### Parser Errors
- Ensure tree-sitter grammars are built
- Verify language name matches available parsers
- Check that parser language matches plugin `language_name`

### Ambiguous File Extensions
- Check logs for detection results
- Use explicit language parameter if detection is incorrect
- Ensure file has sufficient content for detection
- Consider file-specific configuration overrides
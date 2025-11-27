# Internal API Reference

⚠️ **Warning**: The APIs documented here are internal implementation details and are not part of the public API. They may change without notice between versions. Use at your own risk.

## Internal Modules

The following modules have been moved to `chunker._internal` as they are implementation details:

- `registry` - Language registry for discovering and loading tree-sitter languages
- `factory` - Parser factory for creating and managing parser instances
- `cache` - AST caching implementation (note: `ASTCache` is still exported publicly)
- `gc_tuning` - Garbage collection optimization utilities
- `vfs` - Virtual file system implementations
- `file_utils` - File metadata and hashing utilities

## Migration Guide

If you were previously using these internal modules directly:

```python
# Old way (no longer supported)
from chunker.registry import LanguageRegistry
from chunker.factory import ParserFactory, ParserConfig

# New way (not recommended - internal use only)
from chunker._internal.registry import LanguageRegistry
from chunker._internal.factory import ParserFactory, ParserConfig
```

**Recommended approach**: Use the public API instead:

```python
# Public API - stable and supported
from chunker import chunk_file, chunk_text, list_languages
from chunker.parser import get_parser, get_language_info
```

## Why This Change?

Moving these modules to `_internal` helps:

1. **Clarify the public API** - Users know which APIs are stable
2. **Enable internal refactoring** - We can improve internals without breaking changes
3. **Reduce API surface** - Simpler, cleaner public interface
4. **Better encapsulation** - Implementation details are hidden

## Advanced Use Cases

If you need advanced functionality that was previously available through these modules, please:

1. Check if the public API already provides what you need
2. Open an issue describing your use case
3. Consider contributing a PR to expose the functionality properly

## Internal Module Documentation

### Registry Module

The registry module discovers available languages from compiled tree-sitter libraries:

```python
# Internal use only!
from chunker._internal.registry import LanguageRegistry
registry = LanguageRegistry(library_path)
languages = registry.list_languages()
```

### Factory Module

The factory creates and manages parser instances with pooling:

```python
# Internal use only!
from chunker._internal.factory import ParserFactory, ParserConfig
config = ParserConfig(timeout_ms=1000)
factory = ParserFactory(registry)
parser = factory.get_parser("python", config)
```

### Cache Module

The cache module provides AST caching with SQLite:

```python
# Public API available!
from chunker import ASTCache  # This is still public
cache = ASTCache(cache_dir="./cache")
```

Remember: These internal APIs may change or be removed in any version without notice!

## Utility Modules

The following utility modules in `chunker/utils/` provide shared functionality used throughout the codebase. While not part of the public API, they are stable and may be useful for plugin developers.

### Text Utilities (`chunker/utils/text.py`)

Provides safe text encoding/decoding functions with graceful error handling:

```python
from chunker.utils.text import safe_decode_bytes, safe_decode, safe_encode

# Decode bytes to string with replacement for invalid UTF-8
text = safe_decode_bytes(b"hello\xff\xfeworld")  # Returns "hello��world"

# Decode that handles None and str passthrough
text = safe_decode(some_value)  # Works with bytes, str, or None

# Encode string to bytes with replacement for unencodable chars
data = safe_encode("hello")  # Returns b"hello"
```

**Functions:**
- `safe_decode_bytes(data: bytes, errors: str = "replace") -> str`: Decode bytes with fallback
- `safe_decode(data: bytes | str | None, encoding: str = "utf-8", errors: str = "replace") -> str`: Universal decode
- `safe_encode(text: str | None, encoding: str = "utf-8", errors: str = "replace") -> bytes`: Safe encode

### JSON Utilities (`chunker/utils/json.py`)

Provides JSON loading with clear error reporting via `ConfigurationError`:

```python
from chunker.utils.json import load_json_file, load_json_string, safe_json_loads
from chunker.exceptions import ConfigurationError

# Load JSON file with detailed error reporting
try:
    data = load_json_file("config.json")
except ConfigurationError as e:
    print(f"Error: {e}")  # Includes file path, line, column

# Parse JSON string
data = load_json_string('{"key": "value"}', source="config")

# Parse with fallback default
data = safe_json_loads(maybe_json, default={"fallback": True})
```

**Functions:**
- `load_json_file(path: Path | str) -> dict[str, Any]`: Load JSON with detailed errors
- `load_json_string(content: str, source: str = "<string>") -> dict[str, Any]`: Parse JSON string
- `safe_json_loads(content: str, default: dict | None = None) -> dict[str, Any]`: Parse with fallback
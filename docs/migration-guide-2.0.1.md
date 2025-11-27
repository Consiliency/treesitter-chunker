# Migration Guide: v2.0.0 → v2.0.1

This guide covers the changes in treesitter-chunker v2.0.1 and how to update your code if needed.

## Overview

Version 2.0.1 is a **non-breaking patch release** focused on internal consistency and robustness improvements. **No code changes are required** to upgrade from v2.0.0.

### What Changed

| Area | Change | Impact |
|------|--------|--------|
| UTF-8 Handling | Centralized safe decoding in language plugins | Internal only |
| JSON Loading | Consistent error handling for config files | Better error messages |
| Error Messages | `ConfigurationError` now includes line/column info | Improved debugging |
| API Surface | No changes | ✅ Fully compatible |

## Upgrade Steps

### 1. Update Your Dependency

```bash
# Using pip
pip install --upgrade treesitter-chunker==2.0.1

# Using uv
uv pip install treesitter-chunker==2.0.1

# Using poetry
poetry update treesitter-chunker

# In requirements.txt
treesitter-chunker>=2.0.1,<3.0.0
```

### 2. Verify the Upgrade

```python
import chunker
print(chunker.__version__)  # Should print "2.0.1"
```

That's it! Your existing code should work without any modifications.

---

## What's New (Optional Improvements)

While no changes are required, v2.0.1 introduces some utilities you may find useful:

### Improved JSON Error Messages

If you load JSON configuration files, errors now include precise location information:

```python
# Before (v2.0.0) - generic error
# JSONDecodeError: Expecting property name enclosed in double quotes

# After (v2.0.1) - detailed error with location
# ConfigurationError: Invalid JSON in config.json: Expecting property name
#                     enclosed in double quotes (line 15, column 3)
```

### New Utility Functions (For Plugin Developers)

If you're developing language plugins or extensions, these utilities are now available:

#### Safe Text Decoding

```python
from chunker.utils.text import safe_decode_bytes, safe_decode

# Handle potentially malformed UTF-8 in source files
text = safe_decode_bytes(raw_bytes)  # Replaces invalid sequences with �

# Handle mixed bytes/str input
text = safe_decode(value)  # Works with bytes, str, or None
```

#### Safe JSON Loading

```python
from chunker.utils.json import load_json_file, safe_json_loads
from chunker.exceptions import ConfigurationError

# Load JSON with detailed error reporting
try:
    config = load_json_file("config.json")
except ConfigurationError as e:
    print(f"Config error: {e}")  # Includes file, line, column

# Parse JSON with fallback default
data = safe_json_loads(maybe_json_string, default={})
```

---

## API Compatibility Reference

### Unchanged Public APIs

All public APIs remain exactly the same:

```python
# Core chunking - unchanged
from chunker import chunk_file, chunk_text, chunk_directory
chunks = chunk_file("example.py", "python")

# CodeChunk dataclass - unchanged
from chunker import CodeChunk
# All fields: language, file_path, node_type, start_line, end_line,
#             byte_start, byte_end, parent_context, content, chunk_id,
#             parent_chunk_id, references, dependencies, metadata

# Parser management - unchanged
from chunker import get_parser, list_languages, get_language_info

# Incremental processing - unchanged
from chunker import DefaultIncrementalProcessor, DefaultChangeDetector

# Repo processing - unchanged
from chunker.repo import RepoProcessorImpl, GitAwareProcessorImpl
```

### HTTP API Endpoints (Unchanged)

If you use the HTTP API, all endpoints remain the same:

| Endpoint | Method | Status |
|----------|--------|--------|
| `/chunk/text` | POST | ✅ Unchanged |
| `/chunk/file` | POST | ✅ Unchanged |
| `/export/postgres` | POST | ✅ Unchanged |
| `/graph/xref` | POST | ✅ Unchanged |
| `/graph/cut` | POST | ✅ Unchanged |
| `/nearest-tests` | POST | ✅ Unchanged |

---

## Handling ConfigurationError

If you catch JSON-related exceptions, note that invalid JSON in config files now raises `ConfigurationError` instead of `json.JSONDecodeError`:

```python
# If you were catching JSONDecodeError specifically for config files:
from chunker.exceptions import ConfigurationError

try:
    # Loading chunker config, strategy config, or custom grammar repos
    config = load_strategy_config("strategy.json")
except ConfigurationError as e:
    # Now includes: file path, error message, line number, column number
    print(f"Configuration error: {e}")
except FileNotFoundError:
    print("Config file not found")
```

**Note:** Direct `json.load()` calls in your own code are unaffected. This change only applies to chunker's internal config loading functions.

---

## Affected Language Plugins

The following language plugins were updated internally to use centralized UTF-8 handling. If you've extended any of these, your extensions should still work:

- Clojure (`chunker/languages/clojure.py`)
- C# (`chunker/languages/cs_plugin.py`)
- Elixir (`chunker/languages/elixir.py`)
- Go (`chunker/languages/go.py`)
- Haskell (`chunker/languages/haskell.py`)
- Java (`chunker/languages/java_plugin.py`)
- Python (`chunker/languages/python.py`)
- Scala (`chunker/languages/scala.py`)
- SQL (`chunker/languages/sql.py`)
- Vue (`chunker/languages/vue.py`)
- Zig (`chunker/languages/zig.py`)

**If you've subclassed these plugins:** Your code should continue to work. The internal change is that `source[start:end].decode("utf-8")` patterns were replaced with `safe_decode_bytes(source[start:end])`, which handles malformed UTF-8 gracefully instead of raising `UnicodeDecodeError`.

---

## Testing Your Upgrade

Run your existing test suite after upgrading:

```bash
# Run your tests
pytest

# Quick smoke test
python -c "
from chunker import chunk_file, chunk_text, __version__
print(f'Version: {__version__}')
chunks = chunk_text('def hello(): pass', 'python')
print(f'Chunks: {len(chunks)}')
print('✅ Upgrade successful!')
"
```

---

## Rollback Instructions

If you encounter any issues (unlikely for this patch release):

```bash
# Rollback to v2.0.0
pip install treesitter-chunker==2.0.0
```

---

## Questions or Issues?

- **GitHub Issues:** https://github.com/Consiliency/treesitter-chunker/issues
- **Changelog:** See [CHANGELOG.md](../CHANGELOG.md) for full release notes

---

## Summary

| Question | Answer |
|----------|--------|
| Do I need to change my code? | **No** |
| Are there breaking changes? | **No** |
| Should I upgrade? | **Yes** - better error messages and robustness |
| Is it safe to upgrade? | **Yes** - all tests pass, APIs unchanged |

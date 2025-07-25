# Grammar Download Manager - Phase 14

## Overview

The Grammar Download Manager is responsible for downloading, compiling, and managing tree-sitter grammar files. It provides a robust system for fetching grammars from GitHub repositories, compiling them into shared libraries, and managing a local cache.

## Features

- **Automatic Grammar Download**: Downloads grammar repositories from GitHub
- **Compilation Support**: Compiles grammar sources into `.so` shared libraries
- **Cache Management**: Maintains a local cache with version tracking
- **Progress Tracking**: Provides progress callbacks during downloads
- **Cross-Platform**: Works on Linux, macOS, and Windows
- **ABI Compatibility**: Detects and validates tree-sitter ABI versions

## Implementation

The main implementation is in `chunker/grammar/download.py` which provides the `GrammarDownloadManager` class that implements the `GrammarDownloadContract`.

### Key Components

1. **Download System**
   - Downloads grammar archives from GitHub
   - Supports both master/main branches and tagged versions
   - Provides progress tracking via callbacks

2. **Compilation Engine**
   - Compiles C/C++ grammar sources
   - Handles scanner files (scanner.c, scanner.cc)
   - Platform-specific compilation flags

3. **Cache Management**
   - Default location: `~/.cache/treesitter-chunker/grammars/`
   - Metadata tracking in JSON format
   - Version-aware caching
   - Cleanup utilities

4. **Validation**
   - Validates compiled `.so` files
   - Checks for expected symbols
   - ABI compatibility verification

## Usage Example

```python
from chunker.grammar.download import GrammarDownloadManager

# Create manager
manager = GrammarDownloadManager()

# Download and compile a grammar
success, path = manager.download_and_compile("python", "v0.20.0")
if success:
    print(f"Grammar compiled to: {path}")

# Check if grammar is cached
if manager.is_grammar_cached("python"):
    print("Python grammar is already available")

# Download with progress tracking
def progress_callback(progress):
    print(f"Downloaded {progress.percent_complete:.1f}%")

grammar_path = manager.download_grammar(
    "javascript", 
    progress_callback=progress_callback
)

# Compile separately
result = manager.compile_grammar(grammar_path, output_dir)
if result.success:
    print(f"Compiled to: {result.output_path}")
    print(f"ABI version: {result.abi_version}")

# Clean old grammars
removed = manager.clean_cache(keep_recent=5)
print(f"Removed {removed} old grammars")
```

## Supported Languages

The manager includes built-in support for:

- Python, JavaScript, TypeScript
- Rust, Go, Java, C, C++
- Ruby, PHP, Bash
- HTML, CSS, JSON
- YAML, TOML, Markdown
- SQL, Kotlin, Swift

Additional languages can be added by updating the `GRAMMAR_REPOS` dictionary.

## Cache Structure

```
~/.cache/treesitter-chunker/grammars/
├── metadata.json          # Cache metadata
├── python-master/         # Downloaded grammar source
│   ├── grammar.js
│   └── src/
│       ├── parser.c
│       └── scanner.c
├── python.so              # Compiled library
├── javascript-v0.20.0/
├── javascript.so
└── ...
```

## Testing

The implementation includes comprehensive unit tests in `tests/test_grammar_download.py`:

```bash
# Run unit tests
python -m pytest tests/test_grammar_download.py -xvs

# Run integration tests
python -m pytest tests/test_phase14_integration.py::TestDiscoveryDownloadIntegration -xvs
```

## Error Handling

- Network errors during download
- Missing build tools (cc/gcc)
- Invalid grammar sources
- Compilation failures
- ABI incompatibilities
- Disk space issues

## Future Enhancements

- Parallel downloads for multiple grammars
- Grammar dependency resolution
- Pre-compiled binary distribution
- Grammar version compatibility matrix
- Automatic grammar updates

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build and Development Commands

### Environment Setup
```bash
# The project uses uv as the package and environment manager
uv venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows

# Install dependencies
uv pip install -e ".[dev]"

# Install py-tree-sitter from GitHub for ABI 15 support (if needed)
uv pip install git+https://github.com/tree-sitter/py-tree-sitter.git
```

- Always use UV as the Python package and environment manager

### Building Tree-sitter Grammars
```bash
# 1. Fetch grammar repositories (required once)
python scripts/fetch_grammars.py

# 2. Compile grammars into shared library
python scripts/build_lib.py
```

### Running Tests
```bash
# Run all tests
python -m pytest

# Run specific test file
python -m pytest tests/test_parser.py

# Run with verbose output
python -m pytest -xvs

# Run specific test
python -m pytest tests/test_parser.py::TestParserAPI::test_get_parser_basic
```

### CLI Usage
```bash
# Basic usage
python cli/main.py chunk examples/example.py -l python

# Output as JSON
python cli/main.py chunk examples/example.py -l python --json
```

## High-Level Architecture

### Core Components

1. **Parser Module (`chunker/parser.py`)**
   - Provides the main API: `get_parser()`, `list_languages()`, `get_language_info()`
   - Maintains singleton instances of `LanguageRegistry` and `ParserFactory`
   - Handles lazy initialization of the compiled language library

2. **Language Registry (`chunker/registry.py`)**
   - Dynamically discovers available languages from compiled .so file
   - Uses ctypes to load language functions (e.g., `tree_sitter_python()`)
   - Manages language metadata and compatibility checking
   - Note: Language constructor shows expected deprecation warning when loading from .so

3. **Parser Factory (`chunker/factory.py`)**
   - Creates and manages parser instances with LRU caching
   - Provides thread-safe parser pooling for concurrent usage
   - Supports parser configuration (timeout, included ranges)

4. **Chunker (`chunker/chunker.py`)**
   - Implements the actual code chunking logic
   - Currently focuses on function/class/method nodes (MVP)
   - Uses tree-sitter AST traversal to identify chunks

5. **Exception Hierarchy (`chunker/exceptions.py`)**
   - Base `ChunkerError` with specific exceptions for different failure modes
   - Provides helpful error messages with recovery suggestions

### Key Design Decisions

1. **Dynamic Language Discovery**: Instead of hardcoding language support, the system dynamically discovers available languages from the compiled .so file at runtime.

2. **Parser Pooling**: Parsers are expensive to create, so the factory maintains both an LRU cache and per-language pools for efficient reuse.

3. **Version Compatibility**: The system gracefully handles ABI version mismatches between grammars and py-tree-sitter, with clear error messages.

4. **Thread Safety**: All core components are designed to be thread-safe for concurrent processing.

### Language Support

Currently supports: Python, JavaScript, C, C++, Rust

All languages must be compiled into `build/my-languages.so` using the build script.

### Important Notes

- **py-tree-sitter Version**: The project requires py-tree-sitter with ABI 15 support. If you encounter version compatibility errors, install from GitHub instead of PyPI.

- **Deprecation Warning**: When loading languages from .so files, you'll see "int argument support is deprecated" warnings. This is expected and doesn't affect functionality.

- **Grammar Compilation**: Always run `scripts/fetch_grammars.py` followed by `scripts/build_lib.py` after cloning or when adding new languages.

- **User Input Weighting**: Never assume I am right without doing your own research and thinking first.

- **Code Improvement Strategy**: Never create new similarly named new versions of files or functions to improve or correct them. Instead, revise the existing files and functions using the same name.
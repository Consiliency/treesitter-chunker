# Contributor Guide for treesitter-chunker

## Project Overview
This is a Python library for chunking code using tree-sitter. The project provides intelligent code chunking capabilities with fallback mechanisms for various programming languages.

## Dev Environment Tips
- Use `uv` as the package and environment manager (not pip or poetry)
- Run `source .venv/bin/activate` to activate the virtual environment
- Use `python scripts/fetch_grammars.py` followed by `python scripts/build_lib.py` to set up tree-sitter grammars
- The project requires py-tree-sitter with ABI 15 support - install from GitHub if you encounter version issues

## Project Structure
- `chunker/` - Main library code
  - `parser.py` - Main API entry point
  - `registry.py` - Language registry for dynamic discovery
  - `factory.py` - Parser factory with caching
  - `chunker.py` - Core chunking logic
  - `token/` - Token-based chunking module
  - `fallback/` - Intelligent fallback system
- `tests/` - Test suite
- `scripts/` - Build and setup scripts
- `cli/` - Command-line interface

## Testing Instructions
- Run all tests: `python -m pytest`
- Run specific test file: `python -m pytest tests/test_parser.py`
- Run with verbose output: `python -m pytest -xvs`
- Run specific test: `python -m pytest tests/test_parser.py::TestParserAPI::test_get_parser_basic`
- Tests must pass before merging any changes

## Code Quality Checks
- Run linter: `ruff check .`
- Run formatter: `black .`
- Run type checker: `pyright`
- Sort imports: `isort .`

## Working with the Code
- Always edit existing functions rather than creating new ones with similar names
- Follow existing code conventions and patterns
- Use the existing exception hierarchy in `chunker/exceptions.py`
- Maintain thread safety in core components
- Never commit secrets or API keys

## Language Support
Currently supports: Python, JavaScript, C, C++, Rust
All languages must be compiled into `build/my-languages.so`

## Common Tasks
1. **Adding a new language**: 
   - Add grammar to `scripts/fetch_grammars.py`
   - Run fetch and build scripts
   - Test with CLI

2. **Modifying chunking logic**:
   - Main logic is in `chunker/chunker.py`
   - Token-based chunking in `chunker/token/chunker.py`
   - Fallback system in `chunker/fallback/`

3. **Running the CLI**:
   ```bash
   python cli/main.py chunk examples/example.py -l python
   python cli/main.py chunk examples/example.py -l python --json
   ```

## Important Notes
- Deprecation warnings about "int argument support" when loading languages are expected
- Always run fetch_grammars.py and build_lib.py after cloning
- Parser instances are cached and pooled for performance
- The system dynamically discovers languages from the compiled .so file

## PR Instructions
- Title format: `[component] Brief description`
- Include tests for any new functionality
- Ensure all tests pass
- Update documentation if changing public APIs
- Reference any related issues
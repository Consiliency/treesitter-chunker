# Tree-sitter Chunker Troubleshooting Guide

## Common Issues and Solutions

### Installation Issues

#### ABI Version Mismatch
**Error**: `RuntimeError: Cannot create language version 15, expected 13-14`

**Solution**: Install py-tree-sitter from GitHub to get ABI 15 support:
```bash
uv pip install git+https://github.com/tree-sitter/py-tree-sitter.git
```

#### Grammar Compilation Failed
**Error**: `Failed to compile grammars`

**Solution**:
1. Ensure you have a C compiler installed (gcc/clang)
2. Run the build scripts in order:
   ```bash
   python scripts/fetch_grammars.py
   python scripts/build_lib.py
   ```

### Import Errors

#### Module Import Errors
**Error**: `ImportError: cannot import name 'chunk_file' from 'chunker'`

**Solution**: Use the correct module path:
```python
# Old (incorrect)
from chunker import chunk_file

# New (correct)
from chunker.core import chunk_file
```

Common import corrections:
- `from chunker.core import chunk_file`
- `from chunker.parallel import chunk_files_parallel`
- `from chunker.streaming import chunk_file_streaming`
- `from chunker.plugin_manager import get_plugin_manager`
- `from chunker.cache import ASTCache`
- `from chunker.export.json_export import JSONExporter, JSONLExporter`
- `from chunker.export.formatters import SchemaType`

#### Circular Import Errors
**Error**: `ImportError: cannot import name '_walk' from partially initialized module`

**Solution**: This has been fixed in the latest version. Ensure you're using the latest code where circular dependencies have been resolved by moving shared functions to `chunker.core`.

### Runtime Issues

#### No Chunks Returned
**Problem**: `chunk_file()` returns empty list

**Possible causes**:
1. **File too small**: Default `min_chunk_size` is 3 lines. Adjust if needed:
   ```python
   from chunker.chunker_config import ChunkerConfig
   config = ChunkerConfig(min_chunk_size=1)
   ```

2. **Language not supported**: Check available languages:
   ```python
   from chunker.parser import list_languages
   print(list_languages())
   ```

3. **File excluded by pattern**: When using batch processing, files with "test" in the name are excluded by default:
   ```bash
   python cli/main.py batch src/ --exclude "*.tmp" --include "*.py"
   ```

#### Parser Not Available
**Error**: `LanguageNotFoundError: Language 'xyz' not found`

**Solution**:
1. Check if language is supported:
   ```python
   from chunker.parser import list_languages
   print(list_languages())
   ```

2. For universal language support, use ZeroConfigAPI:
   ```python
   from chunker.auto import ZeroConfigAPI
   api = ZeroConfigAPI()
   result = api.auto_chunk_file("file.xyz")  # Auto-downloads grammar if available
   ```

### CLI Issues

#### JSON Parse Errors in Tests
**Error**: `json.decoder.JSONDecodeError: Invalid control character`

**Solution**: This can occur when test output contains ANSI escape codes. The latest version includes fallback parsing to handle this.

#### Batch Command Not Finding Files
**Problem**: No files processed when running batch command

**Common issues**:
1. Default exclude pattern filters out test files
2. Wrong file extension pattern
3. Incorrect path

**Solution**:
```bash
# Override default excludes
python cli/main.py batch src/ --exclude "" --include "*.py"

# Be explicit about patterns
python cli/main.py batch src/ --pattern "**/*.py"
```

### Performance Issues

#### Slow Processing
**Problem**: Chunking takes too long

**Solutions**:
1. Enable caching:
   ```python
   from chunker.cache import ASTCache
   cache = ASTCache()
   ```

2. Use parallel processing:
   ```python
   from chunker.parallel import chunk_files_parallel
   results = chunk_files_parallel(files, "python", max_workers=4)
   ```

3. Use streaming for large files:
   ```python
   from chunker.streaming import chunk_file_streaming
   chunks = list(chunk_file_streaming("large_file.py", "python"))
   ```

### Export Issues

#### Memory Issues with Large Exports
**Problem**: Out of memory when exporting large datasets

**Solution**: Use streaming export:
```python
from chunker.export.json_export import JSONLExporter
from chunker.streaming import chunk_file_streaming

exporter = JSONLExporter()
exporter.stream_export(
    chunk_file_streaming("large_file.py", "python"),
    "output.jsonl"
)
```

### Testing Issues

#### Skipped Tests
**Notice**: Some tests are skipped with "ABI version mismatch"

**Explanation**: This is expected when grammars were compiled with different ABI versions. The skip markers prevent false failures. To run these tests, recompile grammars with matching ABI version.

#### Coverage Module Issues
**Error**: Circular import errors from coverage module

**Solution**: Run tests without coverage:
```bash
python -m pytest -p no:cov
```

### Language-Specific Issues

#### Language Plugin Not Found
**Error**: `Plugin for language 'xyz' not found`

**Solution**:
1. Load built-in plugins:
   ```python
   from chunker.plugin_manager import get_plugin_manager
   manager = get_plugin_manager()
   manager.load_built_in_plugins()
   ```

2. Check available plugins:
   ```python
   print(manager.list_plugins())
   ```

### Getting Help

If you encounter issues not covered here:

1. Check the [GitHub Issues](https://github.com/anthropics/claude-code/issues)
2. Review the [API Reference](api-reference.md)
3. See the [User Guide](user-guide.md) for detailed examples
4. File a new issue with:
   - Python version
   - Tree-sitter chunker version
   - Minimal code to reproduce
   - Full error traceback
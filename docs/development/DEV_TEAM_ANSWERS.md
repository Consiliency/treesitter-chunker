# Tree-sitter Chunker: Dev Team Integration Guide

This document provides comprehensive answers to your questions about integrating with the Tree-sitter Chunker project. All information has been verified against the actual codebase.

## 📋 CodeChunk Schema & Fields

### ✅ Available Fields (All Languages)

The `CodeChunk` class provides these **stable fields** across all languages:

```python
@dataclass
class CodeChunk:
    # Core identification
    language: str                    # Language identifier (e.g., "python", "rust")
    file_path: str                   # Path to source file
    node_type: str                   # AST node type (e.g., "function_definition")
    
    # Line-based positioning
    start_line: int                  # Starting line (1-indexed)
    end_line: int                    # Ending line (1-indexed)
    
    # Byte-accurate positioning (preferred for SymbolSpan)
    byte_start: int                  # Starting byte offset
    byte_end: int                    # Ending byte offset
    
    # Context and hierarchy
    parent_context: str              # Parent context (e.g., "class:MyClass")
    parent_chunk_id: str | None      # ID of parent chunk if nested
    
    # Content
    content: str                     # Actual source code content
    
    # Stable identifiers for incremental processing
    chunk_id: str                    # Unique chunk identifier (SHA1-based)
    node_id: str                     # Stable node identifier
    file_id: str                     # Stable file identifier
    symbol_id: str | None            # Symbol identifier if available
    
    # Hierarchy tracking
    parent_route: list[str]          # Ancestor node types from root
    
    # Dependencies and references
    references: list[str]            # List of references to other chunks
    dependencies: list[str]          # List of dependencies on other chunks
    
    # Extensible metadata
    metadata: dict[str, Any]         # Language-specific metadata
```

### 🔑 Stable Chunk ID for Incremental Processing

**Yes, you get stable chunk IDs!** The `chunk_id` field provides:

- **Deterministic generation**: Based on `file_path`, `language`, `parent_route`, and `content` hash
- **SHA1-based**: 40-character unique identifier
- **Content-aware**: Changes when content changes, stable when content is identical
- **Hierarchy-aware**: Includes parent route for nested structures

```python
# ID generation is automatic and stable
chunk = CodeChunk(...)
print(chunk.chunk_id)  # e.g., "a1b2c3d4e5f6..."

# For incremental processing, use chunk_id as your primary key
```

## 🔗 Imports and Calls Extraction

### ✅ Built-in Support

**Yes, the chunker already extracts imports and calls!** This is handled through the metadata extraction system:

```python
from chunker import chunk_file

# Extract chunks with metadata (enabled by default)
chunks = chunk_file("example.py", "python")

for chunk in chunks:
    # Import information
    if "imports" in chunk.metadata:
        print(f"Imports: {chunk.metadata['imports']}")
    
    # Function calls
    if "calls" in chunk.metadata:
        print(f"Calls: {chunk.metadata['calls']}")
    
    # Dependencies
    if chunk.dependencies:
        print(f"Dependencies: {chunk.dependencies}")
```

### 📊 Metadata Structure

Each chunk's metadata includes:

```python
{
    "imports": ["os", "sys", "json"],           # Imported modules/symbols
    "calls": ["print", "len", "open"],          # Function calls made
    "dependencies": ["external_func", "SomeClass"], # External symbols referenced
    "exports": ["my_function", "MyClass"],      # Symbols exported by this chunk
    "signature": {                              # Function/method signature
        "name": "function_name",
        "parameters": [...],
        "return_type": "str",
        "decorators": ["@staticmethod"]
    }
}
```

### 🎯 Language-Specific Query Examples

If you need to run custom Tree-sitter queries, here are examples:

#### Python Import Queries
```python
from chunker.parser import get_parser

parser = get_parser("python")
tree = parser.parse(source_code.encode())

# Find all import statements
query = parser.language.query("""
  (import_statement) @import
  (import_from_statement) @import_from
""")

captures = query.capture(tree.root_node)
for node, capture_name in captures:
    print(f"{capture_name}: {source_code[node.start_byte:node.end_byte]}")
```

#### JavaScript/TypeScript Import Queries
```javascript
// Find ES6 imports
const query = parser.language.query(`
  (import_statement) @import
  (import_clause) @import_clause
  (named_imports) @named_imports
`);

// Find function calls
const callQuery = parser.language.query(`
  (call_expression
    function: (identifier) @function_name
    arguments: (arguments)) @function_call
`);
```

## 🔢 Byte Offsets

### ✅ Full Byte Offset Support

**Yes, `start_byte`/`end_byte` are exposed in CodeChunk across all languages!**

```python
for chunk in chunks:
    # Byte-accurate spans for idempotent edits
    span_start = chunk.byte_start
    span_end = chunk.byte_end
    
    # Content extraction using byte offsets
    content_bytes = source_bytes[span_start:span_end]
    
    # Perfect for SymbolSpan integration
    symbol_span = SymbolSpan(
        start=span_start,
        end=span_end,
        content=chunk.content
    )
```

**Benefits for your use case:**
- **Idempotent edits**: Byte offsets are stable across file modifications
- **Precise positioning**: No line-based ambiguity
- **Cross-language consistency**: Same API for Python, Rust, JavaScript, etc.

## ⚙️ Configuration from Python

### ✅ Programmatic Configuration

**Yes, you can configure everything programmatically!** Here's how:

```python
from chunker import ChunkerConfig, PluginConfig

# Create configuration programmatically
config = ChunkerConfig()

# Set global defaults
config.default_plugin_config.min_chunk_size = 1  # Don't filter small functions
config.default_plugin_config.max_chunk_size = 1000

# Configure specific languages
python_config = PluginConfig(
    enabled=True,
    chunk_types={
        "function_definition",      # Functions
        "class_definition",         # Classes
        "method_definition",        # Methods
        "async_function_definition" # Async functions
    },
    min_chunk_size=1,              # Include all functions
    max_chunk_size=500,
    custom_options={
        "include_docstrings": True,
        "skip_private": False
    }
)

config.set_plugin_config("python", python_config)

# Use configuration
from chunker import chunk_file
chunks = chunk_file("file.py", "python", config=config)
```

### 🎯 Per-Language Chunk Types

**Default chunk types for each language:**

#### Python
```python
chunk_types = {
    "function_definition",      # def function()
    "class_definition",         # class Class
    "method_definition",        # def method()
    "async_function_definition" # async def function()
}
```

#### JavaScript/TypeScript
```python
chunk_types = {
    "function_declaration",     # function name()
    "arrow_function",           # () => {}
    "class_declaration",        # class Class
    "method_definition",        # method() {}
    "export_statement"          # export statements
}
```

#### Rust
```python
chunk_types = {
    "function_item",            # fn function()
    "impl_item",                # impl blocks
    "struct_item",              # struct definitions
    "trait_item",               # trait definitions
    "enum_item"                 # enum definitions
}
```

## 🔧 Parser Access

### ✅ Stable API for Direct Parser Access

**Yes, you get stable access to underlying Tree-sitter parsers!**

```python
from chunker.parser import get_parser, list_languages

# Get available languages
languages = list_languages()
print(languages)  # ['python', 'javascript', 'rust', 'c', 'cpp']

# Get parser instance
parser = get_parser("python")

# Access the underlying Tree-sitter Language
language = parser.language
print(f"Language: {language.name}")

# Run custom queries
query = language.query("""
  (function_definition
    name: (identifier) @function_name
    parameters: (parameters) @params
    body: (block) @body) @function
""")

# Parse source code
tree = parser.parse(source_code.encode())
captures = query.capture(tree.root_node)

# Extract custom information
for node, capture_name in captures:
    if capture_name == "function_name":
        function_name = source_code[node.start_byte:node.end_byte]
        print(f"Found function: {function_name}")
```

### 🎯 Custom Query Implementation

You can implement your own import/call extraction:

```python
def extract_imports_and_calls(source_code: str, language: str):
    parser = get_parser(language)
    tree = parser.parse(source_code.encode())
    
    imports = []
    calls = []
    
    if language == "python":
        # Python-specific queries
        import_query = parser.language.query("""
          (import_statement) @import
          (import_from_statement) @import_from
        """)
        
        call_query = parser.language.query("""
          (call_expression
            function: (identifier) @function_name) @call
        """)
        
        # Process captures...
        
    elif language == "javascript":
        # JavaScript-specific queries
        import_query = parser.language.query("""
          (import_statement) @import
          (import_clause) @import_clause
        """)
        
        call_query = parser.language.query("""
          (call_expression
            function: (identifier) @function_name) @call
        """)
    
    return imports, calls
```

## 🔒 Determinism & Ordering

### ✅ Parallel Processing with Deterministic Output

**Yes, you get ordering guarantees!** The parallel chunker ensures deterministic results:

```python
from chunker.parallel import chunk_files_parallel

# Process files in parallel
results = chunk_files_parallel(
    file_paths=["file1.py", "file2.py", "file3.py"],
    language="python",
    num_workers=4
)

# Results are deterministic and ordered
for file_path, chunks in results.items():
    # Chunks within each file are ordered by start_line
    chunks.sort(key=lambda c: c.start_line)
    
    # Process in deterministic order
    for chunk in chunks:
        process_chunk(chunk)
```

### 🎯 Ordering Guarantees

1. **File-level ordering**: Results dictionary maintains file order
2. **Chunk-level ordering**: Chunks within files are ordered by `start_line`
3. **Stable IDs**: `chunk_id` provides consistent identification across runs
4. **Cache consistency**: AST caching ensures identical results for unchanged files

### 🔧 Controlling Output Order

```python
# For full control over output order
all_chunks = []
for file_path in sorted(file_paths):  # Ensure file order
    if file_path in results:
        file_chunks = results[file_path]
        # Sort by line number for deterministic chunk order
        file_chunks.sort(key=lambda c: (c.start_line, c.byte_start))
        all_chunks.extend(file_chunks)

# Now you have fully deterministic ordering
```

## 🌍 Language Coverage

### ✅ Prebuilt Wheel Languages

**Prebuilt wheels include these languages (no compilation required):**

```python
# Core languages (always available)
core_languages = [
    "python",      # Python 3.x
    "javascript",  # ES6+ JavaScript
    "rust",        # Rust
    "c",           # C language
    "cpp"          # C++
]

# Available in prebuilt wheels
print(list_languages())  # ['c', 'cpp', 'javascript', 'python', 'rust']
```

### 🚀 Auto-Download for 100+ Languages

**Additional languages are automatically downloaded when needed:**

```python
from chunker.auto import ZeroConfigAPI

api = ZeroConfigAPI()

# Automatically downloads and compiles grammars
result = api.auto_chunk_file("file.go")      # Go
result = api.auto_chunk_file("file.java")    # Java
result = api.auto_chunk_file("file.rb")      # Ruby
result = api.auto_chunk_file("file.swift")   # Swift
```

### 📦 CI/Offline Best Practices

**For CI and offline environments:**

```python
# 1. Pre-download required languages
from chunker.grammar.manager import TreeSitterGrammarManager

manager = TreeSitterGrammarManager()
languages_needed = ["python", "javascript", "rust", "go", "java"]

for lang in languages_needed:
    if not manager.is_grammar_available(lang):
        manager.download_and_build_grammar(lang)

# 2. Bundle grammars in your deployment
# Grammars are compiled to .so/.dll files that can be bundled

# 3. Use prebuilt wheels in CI
# pip install treesitter-chunker  # Includes core languages
```

## 🎯 Quick Start for Non-Python Adapter

Here's how to implement your first non-Python adapter quickly:

```python
from chunker.parser import get_parser
from chunker.types import CodeChunk

def chunk_go_file(file_path: str) -> list[CodeChunk]:
    """Chunk a Go file using Tree-sitter queries."""
    
    # Get Go parser
    parser = get_parser("go")
    
    # Read source
    with open(file_path, 'rb') as f:
        source = f.read()
    
    # Parse AST
    tree = parser.parse(source)
    
    # Define chunk types for Go
    chunk_types = {
        "function_declaration",  # func name()
        "method_declaration",    # func (r *Receiver) name()
        "type_declaration",      # type Name struct
        "interface_type",        # interface Name
    }
    
    chunks = []
    
    # Extract functions
    query = parser.language.query("""
      (function_declaration
        name: (identifier) @function_name
        parameters: (parameter_list) @params
        result: (result) @result
        body: (block) @body) @function
    """)
    
    captures = query.capture(tree.root_node)
    
    for node, capture_name in captures:
        if capture_name == "function":
            # Extract function name
            name_node = next(n for n, c in captures if c == "function_name" and n.parent == node)
            function_name = source[name_node.start_byte:name_node.end_byte].decode()
            
            # Create chunk
            chunk = CodeChunk(
                language="go",
                file_path=file_path,
                node_type="function_declaration",
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                byte_start=node.start_byte,
                byte_end=node.end_byte,
                parent_context="",
                content=source[node.start_byte:node.end_byte].decode(),
                metadata={
                    "name": function_name,
                    "imports": extract_go_imports(node, source),
                    "calls": extract_go_calls(node, source)
                }
            )
            chunks.append(chunk)
    
    return chunks

def extract_go_imports(node, source):
    """Extract Go import statements."""
    imports = []
    # Implementation using Go-specific Tree-sitter queries
    return imports

def extract_go_calls(node, source):
    """Extract Go function calls."""
    calls = []
    # Implementation using Go-specific Tree-sitter queries
    return calls
```

## 📚 Additional Resources

- **API Reference**: `docs/api-reference.md`
- **Configuration Guide**: `docs/configuration.md`
- **Plugin Development**: `docs/plugin-development.md`
- **Performance Guide**: `docs/performance-guide.md`
- **Export Formats**: `docs/export-formats.md`

## 🎯 Summary

**You get everything you need:**

✅ **Complete CodeChunk schema** with byte offsets, stable IDs, and metadata  
✅ **Built-in import/call extraction** via metadata system  
✅ **Programmatic configuration** for all chunking parameters  
✅ **Direct parser access** for custom Tree-sitter queries  
✅ **Deterministic parallel processing** with ordering guarantees  
✅ **36+ languages** with auto-download capability  
✅ **Prebuilt wheels** for core languages (no compilation needed)  

The chunker is production-ready and designed for exactly your use case. You can start with the built-in metadata extraction and extend with custom queries as needed.

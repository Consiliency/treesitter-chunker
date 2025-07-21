# Tree-sitter Debug Tools Examples

This directory contains examples demonstrating the Tree-sitter debug and visualization tools.

## Quick Start

### 1. Interactive REPL

Start the debug REPL for interactive exploration:

```bash
python -m cli.main debug repl --lang python
```

In the REPL, you can:
- Load files: `load examples/example.py`
- Debug queries: `query (function_definition) @func`
- Analyze chunks: `chunk`
- Explore AST: `explore`

### 2. AST Visualization

Visualize the AST of a source file:

```bash
# Show as tree in terminal
python -m cli.main debug ast examples/example.py --lang python

# Generate graph (requires graphviz)
python -m cli.main debug ast examples/example.py --format graph --output ast.svg

# Show with chunk boundaries
python -m cli.main debug ast examples/example.py --chunks

# Highlight specific node types
python -m cli.main debug ast examples/example.py --highlight function_definition,class_definition
```

### 3. Query Debugging

Debug Tree-sitter queries:

```bash
# Debug a simple query
python -m cli.main debug query "(function_definition) @func" --file examples/example.py --lang python

# Show AST to help write queries
python -m cli.main debug query "(identifier) @id" --code "x = 42" --lang python --ast

# Test on inline code
python -m cli.main debug query "(call) @call" --code "print('hello')" --lang python
```

### 4. Chunk Analysis

Analyze and debug chunking decisions:

```bash
# Analyze chunking
python -m cli.main debug chunks examples/example.py --lang python

# Visualize chunk boundaries
python -m cli.main debug chunks examples/example.py --visualize

# Check for size violations
python -m cli.main debug chunks examples/example.py --min-size 5 --max-size 50

# Show side-by-side comparison
python -m cli.main debug chunks examples/example.py --visualize --side-by-side
```

### 5. Interactive Node Explorer

Explore AST nodes interactively:

```bash
python -m cli.main debug explore --file examples/example.py --lang python
```

Commands in explorer:
- `child 0` - Navigate to first child
- `parent` - Go to parent node
- `info` - Show detailed node information
- `tree` - Show subtree structure
- `find function_definition` - Find nodes of type
- `bookmark main` - Bookmark current node
- `help` - Show all commands

### 6. Parse Validation

Validate parsing and find errors:

```bash
python -m cli.main debug validate examples/example.py --lang python
```

## Common Query Patterns

### Python

```scheme
; Functions
(function_definition name: (identifier) @func)

; Classes
(class_definition name: (identifier) @class)

; Method calls
(attribute 
  object: (identifier) @obj
  attribute: (identifier) @method)

; Imports
[
  (import_statement)
  (import_from_statement)
] @import

; Decorators
(decorator (identifier) @decorator)
```

### JavaScript

```scheme
; Functions
[
  (function_declaration)
  (function_expression)
  (arrow_function)
] @function

; Variables
(variable_declarator
  name: (identifier) @var)

; JSX elements
(jsx_element
  open_tag: (jsx_opening_element
    name: (identifier) @component))
```

### Rust

```scheme
; Functions
(function_item name: (identifier) @func)

; Structs
(struct_item name: (type_identifier) @struct)

; Impl blocks
(impl_item type: (type_identifier) @type)

; Macros
(macro_invocation
  macro: (identifier) @macro)
```

## Python API Examples

See `debug_workflow_example.py` for examples using the Python API:

```python
from chunker.debug import (
    ASTVisualizer,
    QueryDebugger,
    ChunkDebugger,
    explore_ast
)

# Visualize AST
visualizer = ASTVisualizer("python")
visualizer.visualize_file("example.py", output_format="tree")

# Debug queries
debugger = QueryDebugger("python")
matches = debugger.debug_query(
    "(function_definition) @func",
    source_code
)

# Analyze chunks
chunk_debugger = ChunkDebugger("python")
analysis = chunk_debugger.analyze_file("example.py")

# Interactive exploration
explore_ast(source_code, "python")
```

## Tips

1. **Writing Queries**: Use the AST visualizer first to understand node structure
2. **Debugging Chunks**: Use `--visualize` to see boundaries overlaid on code
3. **Performance**: For large files, use `--max-depth` to limit AST visualization
4. **Graphviz**: Install with `apt-get install graphviz` or `brew install graphviz`

## Troubleshooting

- **No matches found**: Check node types with AST visualizer
- **Query syntax error**: Ensure proper parentheses and capture syntax
- **Graph generation fails**: Install graphviz system package
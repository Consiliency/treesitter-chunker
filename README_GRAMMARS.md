# More Grammars Support

This worktree implements extended language support for the Tree-sitter chunker, including grammar management capabilities.

## New Languages Added

- **Go** - Full support for functions, methods, types, interfaces, and constants
- **Ruby** - Support for classes, modules, methods, DSL blocks, and attr_* declarations  
- **Java** - Support for classes, interfaces, enums, methods, fields, and annotations

## Grammar Management

The grammar module provides a complete workflow for managing Tree-sitter grammars:

### Core Components

1. **GrammarManager** - Manages grammar lifecycle (add, fetch, build, remove)
2. **GrammarBuilder** - Compiles grammar sources into shared libraries
3. **GrammarRepository** - Registry of known Tree-sitter grammars
4. **GrammarValidator** - Validates grammar compatibility and correctness

### Usage

```python
from chunker.grammar import TreeSitterGrammarManager, get_grammar_repository

# Get repository instance
repo = get_grammar_repository()

# Search for grammars
results = repo.search("javascript")

# Get grammar by file extension
grammar = repo.get_grammar_by_extension(".py")

# Create manager
manager = TreeSitterGrammarManager()

# Add a grammar
manager.add_grammar("go", "https://github.com/tree-sitter/tree-sitter-go.git")

# Fetch source code
manager.fetch_grammar("go")

# Build grammar
manager.build_grammar("go")

# Validate it works
is_valid, error = manager.validate_grammar("go")
```

### CLI Tool

Use the provided script to manage grammars:

```bash
# List all available grammars
python examples/manage_grammars.py list

# Search for grammars
python examples/manage_grammars.py search rust

# Add and build grammars
python examples/manage_grammars.py add python go ruby java
python examples/manage_grammars.py fetch python go ruby java
python examples/manage_grammars.py build python go ruby java

# Check status
python examples/manage_grammars.py status

# Check file support
python examples/manage_grammars.py check example.go
```

## Language Configurations

Each new language includes:

### Go
- Functions and methods (with receiver types)
- Type declarations (structs, interfaces)
- Constants and variables
- Package-level context

### Ruby
- Methods (instance, class, singleton)
- Classes and modules
- DSL blocks (RSpec, Rails, Rake)
- Attribute accessors

### Java  
- Classes, interfaces, enums
- Methods and constructors
- Fields and static blocks
- Annotations support
- Inner and nested classes

## Testing

Run language-specific tests:

```bash
# Test new language support
pytest tests/test_go_language.py
pytest tests/test_ruby_language.py
pytest tests/test_java_language.py

# Test grammar management
pytest tests/unit/grammar/
pytest tests/integration/grammar/
```

## Extending Language Support

To add a new language:

1. Add grammar info to `KNOWN_GRAMMARS` in `repository.py`
2. Create language plugin in `chunker/languages/<language>_plugin.py`
3. Register configuration with `language_config_registry`
4. Add tests in `tests/test_<language>_language.py`

Example plugin structure:

```python
from .plugin_base import LanguagePlugin
from .base import LanguageConfig, ChunkRule, language_config_registry

class NewLanguagePlugin(LanguagePlugin):
    @property
    def language_name(self) -> str:
        return "newlang"
    
    def get_chunk_node_types(self) -> Set[str]:
        return {"function", "class", "module"}
    
    # ... implement other methods

# Register configuration
newlang_config = LanguageConfig(
    name="newlang",
    file_extensions=[".nl"],
    chunk_rules=[...],
    scope_node_types=[...]
)
language_config_registry.register(newlang_config)
```

## Integration with Main System

The grammar management integrates with the existing chunker:

```python
from chunker.parser import get_parser
from chunker.chunker import CodeChunker

# After building a grammar, use it normally
parser = get_parser("go")
tree = parser.parse(code.encode())

chunker = CodeChunker()
chunks = chunker.chunk(tree, code.encode(), "main.go")
```

## Known Grammar Sources

The system includes 25+ known grammars including:
- All major programming languages (Python, JS, Java, C/C++, Go, Rust, Ruby, etc.)
- Web technologies (HTML, CSS, TypeScript)
- Data formats (JSON, YAML, TOML)
- Scripting languages (Bash, Lua)
- Mobile languages (Swift, Kotlin)
- Functional languages (Haskell, Scala)

## Future Enhancements

- Automatic grammar updates
- Grammar version management
- Custom grammar development tools
- Language-specific chunking optimizations
- Grammar compatibility matrix
# Metadata Extraction

The metadata extraction feature enriches code chunks with detailed information about functions, methods, and classes, including signatures, complexity metrics, documentation, and dependencies.

## Overview

When enabled, the chunker automatically extracts the following metadata for each chunk:

- **Function/Method Signatures**: Parameter names, types, default values, return types
- **Complexity Metrics**: Cyclomatic and cognitive complexity, nesting depth, lines of code
- **Documentation**: Docstrings, JSDoc comments, and other documentation
- **Dependencies**: External symbols referenced by the chunk
- **Imports/Exports**: Module dependencies and exported symbols

## Usage

### Basic Usage

```python
from chunker.chunker import chunk_text

# Extract chunks with metadata (default)
chunks = chunk_text(code, 'python')

# Access metadata
for chunk in chunks:
    print(f"Function: {chunk.metadata['signature']['name']}")
    print(f"Complexity: {chunk.metadata['complexity']['cyclomatic']}")
    print(f"Docstring: {chunk.metadata['docstring']}")
```

### Disabling Metadata Extraction

```python
# Disable metadata extraction for performance
chunks = chunk_text(code, 'python', extract_metadata=False)
```

## Metadata Structure

Each chunk's metadata dictionary contains:

```python
{
    'signature': {
        'name': 'function_name',
        'parameters': [
            {'name': 'param1', 'type': 'str', 'default': None},
            {'name': 'param2', 'type': 'int', 'default': '0'}
        ],
        'return_type': 'bool',
        'decorators': ['staticmethod', 'lru_cache'],
        'modifiers': ['async', 'staticmethod']
    },
    'complexity': {
        'cyclomatic': 5,
        'cognitive': 8,
        'nesting_depth': 3,
        'lines_of_code': 25,
        'logical_lines': 18
    },
    'docstring': 'Function documentation...',
    'dependencies': ['external_func', 'SomeClass'],
    'imports': ['import os', 'from typing import List'],
    'exports': ['exported_function', 'ExportedClass']
}
```

## Supported Languages

Currently, metadata extraction is supported for:

- **Python**: Full support including type annotations, decorators, async/await
- **JavaScript**: Functions, arrow functions, async, generators, JSDoc
- **TypeScript**: All JavaScript features plus interfaces, type annotations
- **JSX/TSX**: Same as JavaScript/TypeScript

## Language-Specific Features

### Python

- Type annotations from function signatures
- Decorators and their parameters
- Async function detection
- Docstring extraction (Google, NumPy, and Sphinx styles)
- Special method modifiers (staticmethod, classmethod)

### JavaScript/TypeScript

- JSDoc comment parsing
- Arrow function support
- Async/await and generator detection
- TypeScript type annotations
- Interface method signatures
- Method modifiers (static, private, protected)

## Complexity Metrics

### Cyclomatic Complexity

Measures the number of linearly independent paths through the code:
- Base complexity: 1
- +1 for each: if, while, for, case, catch, and, or
- Higher values indicate more complex control flow

### Cognitive Complexity

Measures how difficult code is to understand:
- Considers nesting levels
- Penalizes deeply nested conditions
- Accounts for logical operators and recursion

### Example

```python
def example(items):         # Cyclomatic: 1 (base)
    for item in items:      # Cyclomatic: 2, Cognitive: 1
        if item > 0:        # Cyclomatic: 3, Cognitive: 3 (nesting penalty)
            process(item)
```

## Performance Considerations

Metadata extraction adds overhead to the chunking process. For large codebases where metadata is not needed, disable it:

```python
# Faster chunking without metadata
chunks = chunk_file('large_file.py', 'python', extract_metadata=False)
```

## Extending Metadata Extraction

To add support for a new language:

1. Create a new extractor class inheriting from `BaseMetadataExtractor`
2. Create a complexity analyzer inheriting from `BaseComplexityAnalyzer`
3. Register them in `MetadataExtractorFactory`

Example:

```python
from chunker.metadata.extractor import BaseMetadataExtractor

class RubyMetadataExtractor(BaseMetadataExtractor):
    def extract_signature(self, node, source):
        # Implement Ruby-specific signature extraction
        pass
```

## API Reference

### MetadataExtractorFactory

```python
# Create extractors for a language
extractor = MetadataExtractorFactory.create_extractor('python')
analyzer = MetadataExtractorFactory.create_analyzer('python')

# Check language support
if MetadataExtractorFactory.is_supported('ruby'):
    # Extract metadata for Ruby
    pass
```

### Chunk Methods

```python
chunk = chunks[0]

# Access metadata
signature = chunk.metadata.get('signature', {})
complexity = chunk.metadata.get('complexity', {})

# Dependencies are also stored in the chunk
deps = chunk.dependencies  # List of dependency names
```
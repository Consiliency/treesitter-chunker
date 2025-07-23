# Specialized Processors Module

This module contains specialized processors for handling different file types that require custom chunking logic beyond basic tree-sitter parsing.

## Overview

The processors module provides a framework for implementing file-type-specific chunking strategies. Each processor understands the unique structure and semantics of its target format.

## Available Processors

### MarkdownProcessor

The `MarkdownProcessor` handles Markdown files with intelligent structure-aware chunking.

**Features:**
- Header-based section detection
- Atomic element preservation (code blocks, tables)
- Smart boundary detection
- Context-preserving overlap
- Support for CommonMark and GFM

**Usage:**
```python
from chunker.processors.markdown import MarkdownProcessor
from chunker.processors import ProcessorConfig

# Configure processor
config = ProcessorConfig(
    max_chunk_size=1500,  # Maximum tokens per chunk
    min_chunk_size=100,   # Minimum tokens per chunk
    overlap_size=100,     # Overlap between chunks
    preserve_structure=True  # Preserve document structure
)

# Create processor
processor = MarkdownProcessor(config)

# Process content
chunks = processor.process(markdown_content, "document.md")
```

## Architecture

### Base Classes

#### SpecializedProcessor

Abstract base class for all specialized processors.

**Required Methods:**
- `can_process(file_path, content)`: Check if processor can handle content
- `process(content, file_path)`: Process content into chunks
- `extract_structure(content)`: Extract structural information
- `find_boundaries(content)`: Find natural chunk boundaries

#### ProcessorConfig

Configuration dataclass for processors.

**Fields:**
- `max_chunk_size`: Maximum tokens per chunk (default: 1500)
- `min_chunk_size`: Minimum tokens per chunk (default: 100)
- `overlap_size`: Overlap tokens between chunks (default: 100)
- `preserve_structure`: Preserve document structure (default: True)

### Integration Points

#### SlidingWindowEngine

Interface for sliding window text processing (implementation in sliding-window worktree).

```python
engine = SlidingWindowEngine(window_size=1000, overlap=100)
positions = engine.process_text(text, boundaries)
```

## Implementing a New Processor

To create a new specialized processor:

1. **Extend SpecializedProcessor:**
```python
from . import SpecializedProcessor, ProcessorConfig
from ..types import CodeChunk

class MyProcessor(SpecializedProcessor):
    def __init__(self, config=None):
        super().__init__(config)
        # Initialize processor-specific attributes
```

2. **Implement Required Methods:**
```python
def can_process(self, file_path: str, content: str) -> bool:
    # Check file extension or content patterns
    return file_path.endswith('.myext')
    
def extract_structure(self, content: str) -> Dict[str, Any]:
    # Parse and extract structural elements
    return {
        'elements': [],
        'metadata': {}
    }
    
def find_boundaries(self, content: str) -> List[Tuple[int, int, str]]:
    # Identify natural chunk boundaries
    return [(start, end, boundary_type), ...]
    
def process(self, content: str, file_path: str) -> List[CodeChunk]:
    # Main processing logic
    structure = self.extract_structure(content)
    boundaries = self.find_boundaries(content)
    return self._create_chunks(content, boundaries, file_path)
```

3. **Handle Special Cases:**
- Atomic elements that shouldn't be split
- Nested structures requiring special handling
- Format-specific validation rules

## Best Practices

### 1. Structure Preservation
Always identify and preserve atomic elements:
```python
ATOMIC_ELEMENTS = {'code_block', 'table', 'diagram'}

def is_atomic(self, element_type: str) -> bool:
    return element_type in self.ATOMIC_ELEMENTS
```

### 2. Boundary Detection
Use natural document boundaries:
```python
def find_boundaries(self, content: str):
    # Headers, sections, paragraphs
    # Don't split in middle of sentences
    # Respect document hierarchy
```

### 3. Context Maintenance
Apply intelligent overlap:
```python
def apply_overlap(self, chunks: List[CodeChunk]) -> List[CodeChunk]:
    # Add context from previous chunk
    # Mark overlap in metadata
    # Avoid duplicating atomic elements
```

### 4. Validation
Validate chunk quality:
```python
def validate_chunk(self, chunk: CodeChunk) -> bool:
    # Check minimum size
    # Verify structural integrity
    # Ensure atomic elements are complete
```

## Testing

Each processor should have comprehensive tests:

```python
class TestMyProcessor:
    def test_can_process(self):
        # Test file type detection
        
    def test_extract_structure(self):
        # Test structure extraction
        
    def test_atomic_preservation(self):
        # Ensure atomic elements aren't split
        
    def test_boundary_detection(self):
        # Test boundary identification
        
    def test_edge_cases(self):
        # Empty files, malformed content, etc.
```

## Future Processors

Planned processors for future phases:

- **ReSTProcessor**: reStructuredText documents
- **LaTeXProcessor**: LaTeX documents  
- **AsciiDocProcessor**: AsciiDoc format
- **HTMLProcessor**: HTML with structure preservation
- **JSONProcessor**: Large JSON files with schema awareness
- **XMLProcessor**: XML with DTD/schema validation

## Performance Considerations

1. **Lazy Processing**: Extract structure on-demand
2. **Efficient Parsing**: Use compiled regex patterns
3. **Memory Management**: Stream large files
4. **Caching**: Reuse extracted structures

## Integration with Tree-Sitter

Specialized processors complement tree-sitter parsing:

```python
# Markdown with embedded code
content = """
# Example

```python
def hello():
    print("Hello")
```
"""

# Markdown processor handles structure
markdown_processor = MarkdownProcessor()
chunks = markdown_processor.process(content, "example.md")

# Code blocks can be further processed with tree-sitter
for chunk in chunks:
    if chunk.chunk_type == 'code_block':
        language = chunk.metadata.get('language')
        # Use tree-sitter for code analysis
```

## Error Handling

Processors should handle errors gracefully:

```python
try:
    chunks = processor.process(content, file_path)
except ProcessorError as e:
    logger.error(f"Processing failed: {e}")
    # Fall back to simple chunking
    chunks = fallback_chunker.process(content)
```

## Contributing

When adding new processors:

1. Follow the established patterns
2. Add comprehensive tests
3. Document special handling rules
4. Consider performance implications
5. Ensure compatibility with existing interfaces
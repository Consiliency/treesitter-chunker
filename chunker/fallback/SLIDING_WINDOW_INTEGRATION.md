# Sliding Window Fallback Integration

## Overview

The Sliding Window Fallback system provides a unified framework for processing text files that cannot be parsed by Tree-sitter. It integrates various text processors (sliding window, markdown, log, config) with automatic processor selection based on file type and content.

## Architecture

### Core Components

1. **SlidingWindowFallback**: Main class extending the base FallbackChunker
2. **ProcessorRegistry**: Manages processor registration and lookup
3. **TextProcessor**: Base class for all text processors
4. **ProcessorChain**: Enables hybrid processing with multiple processors
5. **ProcessorInfo**: Metadata about registered processors

### Processor Types

- `SLIDING_WINDOW`: Generic sliding window processing
- `MARKDOWN`: Markdown-specific processing
- `LOG`: Log file processing
- `CONFIG`: Configuration file processing
- `GENERIC`: Generic text processing
- `CUSTOM`: User-defined processors

## Processor Selection Algorithm

The processor selection follows a priority-based algorithm:

1. **File Type Detection**
   - Detect file type using FileTypeDetector
   - Map file type to potential processors

2. **Extension Matching**
   - Check file extension against processor capabilities
   - Add matching processors to candidate list

3. **Priority Sorting**
   - Sort candidates by priority (higher = preferred)
   - Filter out disabled processors

4. **Capability Check**
   - For each candidate, call `can_process()`
   - Use first processor that returns True

5. **Fallback**
   - If no processor matches, use generic line-based chunking
   - Emit warning about fallback usage

### Selection Flow

```
File Input
    ↓
File Type Detection ←→ Extension Check
    ↓                      ↓
Processor Candidates (union)
    ↓
Filter by Enabled Status
    ↓
Sort by Priority
    ↓
For each processor:
    can_process() ?
        Yes → Use processor
        No → Try next
    ↓
No matches → Generic fallback
```

## Configuration

### ChunkerConfig Integration

The system integrates with ChunkerConfig for processor configuration:

```yaml
processors:
  markdown_processor:
    enabled: true
    priority: 100
    config:
      max_header_level: 3
      include_code_blocks: true
  
  log_processor:
    enabled: true
    priority: 90
    config:
      time_window: 300
      group_by_severity: true

chunker:
  plugin_dirs:
    - ./custom_processors
    - ~/.chunker/processors
```

### Processor Configuration

Each processor can have custom configuration:

```python
processor_config = {
    'window_size': 1000,
    'overlap': 100,
    'preserve_words': True
}
```

## Custom Processor Development

### Creating a Custom Processor

```python
from chunker.fallback import TextProcessor, ProcessorInfo, ProcessorType
from chunker.types import CodeChunk

class MyCustomProcessor(TextProcessor):
    """Custom processor for specific file format."""
    
    def can_process(self, content: str, file_path: str) -> bool:
        """Check if this processor can handle the content."""
        return file_path.endswith('.myformat') or 'MAGIC_STRING' in content
    
    def process(self, content: str, file_path: str) -> List[CodeChunk]:
        """Process content into chunks."""
        chunks = []
        # Custom processing logic
        return chunks
```

### Registering Custom Processors

1. **Runtime Registration**:
```python
fallback.register_custom_processor(
    name="my_processor",
    processor_class=MyCustomProcessor,
    file_types={FileType.TEXT},
    extensions={'.myformat'},
    priority=150
)
```

2. **Plugin Directory**:
   - Place processor in plugin directory
   - Name file as `*_processor.py`
   - Include `processor_info()` static method

3. **Configuration**:
   - Add to `processors` section in config
   - Set enabled status and priority

## Processor Chaining

For complex files with mixed content:

```python
# Create processor chain
chain = fallback.create_processor_chain([
    'markdown_processor',
    'code_block_processor',
    'sql_processor'
])

# Process mixed content
chunks = chain.process(content, file_path)
```

## Performance Optimization

### Processor Caching

- Processors are instantiated once and cached
- Reduces overhead for repeated processing
- Cache cleared when processor is unregistered

### Priority-Based Selection

- Higher priority processors checked first
- Avoids unnecessary capability checks
- Custom processors can override built-ins

### Lazy Loading

- Processors loaded only when needed
- Plugin directories scanned on demand
- Minimal startup overhead

## API Reference

### SlidingWindowFallback

```python
class SlidingWindowFallback(FallbackChunker):
    def chunk_text(self, content: str, file_path: str, language: Optional[str] = None) -> List[CodeChunk]
    def register_custom_processor(self, name: str, processor_class: Type[TextProcessor], ...)
    def enable_processor(self, name: str) -> None
    def disable_processor(self, name: str) -> None
    def get_processor_info(self, file_path: str) -> Dict[str, Any]
    def create_processor_chain(self, processor_names: List[str]) -> Optional[ProcessorChain]
```

### TextProcessor

```python
class TextProcessor(ABC):
    @abstractmethod
    def can_process(self, content: str, file_path: str) -> bool
    
    @abstractmethod
    def process(self, content: str, file_path: str) -> List[CodeChunk]
    
    def get_metadata(self) -> Dict[str, Any]
```

### ProcessorRegistry

```python
class ProcessorRegistry:
    def register(self, processor_info: ProcessorInfo) -> None
    def unregister(self, name: str) -> None
    def get_processor(self, name: str) -> Optional[TextProcessor]
    def find_processors(self, file_path: str, file_type: Optional[FileType] = None) -> List[str]
    def list_processors(self) -> List[ProcessorInfo]
```

## Best Practices

1. **Processor Priority**
   - Built-in: 40-60
   - Enhanced built-in: 80-100
   - Custom/specialized: 120-200

2. **File Type Support**
   - Be specific with file types
   - Include common extensions
   - Use content detection as fallback

3. **Error Handling**
   - Processors should not raise exceptions
   - Return empty list if processing fails
   - Log errors for debugging

4. **Performance**
   - Avoid expensive operations in `can_process()`
   - Cache compiled regexes
   - Process incrementally for large files

5. **Chunk Quality**
   - Preserve semantic boundaries
   - Include appropriate context
   - Set accurate line/byte positions

## Integration with Main Chunker

The SlidingWindowFallback integrates seamlessly with the main chunker:

1. Tree-sitter attempts parsing
2. On failure, fallback system activated
3. SlidingWindowFallback selects processor
4. Chunks returned with processor metadata
5. Warning emitted about fallback usage

This ensures consistent behavior while providing flexibility for unsupported file types.
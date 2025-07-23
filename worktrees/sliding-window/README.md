# Sliding Window Engine

This is the core sliding window implementation for the treesitter-chunker project (Phase 11).

## Overview

The sliding window engine provides efficient text processing capabilities by dividing large texts into overlapping or non-overlapping windows. It supports multiple units of measurement, dynamic sizing, and both in-memory and streaming processing modes.

## Features

- **Multiple Units**: Process text by characters, lines, tokens, or bytes
- **Flexible Overlap**: Fixed, percentage-based, or semantic overlap strategies  
- **Dynamic Sizing**: Automatically adjust window sizes based on content density
- **Streaming Support**: Efficiently process large files without loading everything into memory
- **Boundary Preservation**: Align windows to natural boundaries (words, sentences, paragraphs)
- **Thread-Safe**: Safe for concurrent processing
- **Navigation**: Built-in navigator for traversing windows

## Installation

This module is part of the treesitter-chunker project. Install the main project and the sliding window module will be available.

## Quick Start

```python
from chunker.sliding_window import (
    DefaultSlidingWindowEngine,
    WindowConfig,
    WindowUnit,
    OverlapStrategy
)

# Basic configuration
config = WindowConfig(
    size=1000,  # 1000 characters per window
    unit=WindowUnit.CHARACTERS,
    overlap=100,  # 100 character overlap
    overlap_strategy=OverlapStrategy.FIXED
)

# Create engine
engine = DefaultSlidingWindowEngine(config)

# Process text
text = "Your long text here..."
for window in engine.process_text(text):
    print(f"Window {window.position.window_index}: {window.content[:50]}...")
```

## Configuration Options

### WindowConfig Parameters

- `size`: Target size of each window
- `unit`: Unit of measurement (CHARACTERS, LINES, TOKENS, BYTES)
- `overlap`: Amount of overlap between windows
- `overlap_strategy`: How overlap is calculated (FIXED, PERCENTAGE, SEMANTIC)
- `min_window_size`: Minimum allowed window size (for dynamic adjustment)
- `max_window_size`: Maximum allowed window size (for dynamic adjustment)
- `preserve_boundaries`: Try to align windows to natural boundaries
- `trim_whitespace`: Remove leading/trailing whitespace from windows

## Advanced Usage

### Line-Based Processing

```python
config = WindowConfig(
    size=50,  # 50 lines per window
    unit=WindowUnit.LINES,
    overlap=5,  # 5 line overlap
    preserve_boundaries=True
)
```

### Percentage Overlap

```python
config = WindowConfig(
    size=1000,
    overlap=20,  # 20% overlap
    overlap_strategy=OverlapStrategy.PERCENTAGE
)
```

### Dynamic Window Adjustment

```python
config = WindowConfig(
    size=1000,
    min_window_size=500,
    max_window_size=2000
)
# Windows will automatically adjust size based on content density
```

### File Processing

```python
# Automatically uses streaming for large files
for window in engine.process_file("large_document.txt"):
    process_window(window)
```

### Window Navigation

```python
from chunker.sliding_window import DefaultWindowNavigator

navigator = DefaultWindowNavigator(engine, text)

# Navigate through windows
while navigator.has_next():
    window = navigator.next_window()
    
# Jump to specific window
window = navigator.jump_to_window(10)

# Find windows containing text
indices = navigator.find_windows_containing("search term")
```

## Utility Functions

```python
from chunker.sliding_window.utils import (
    calculate_window_statistics,
    optimize_window_config,
    find_natural_boundaries
)

# Get statistics about windows
stats = calculate_window_statistics(windows)

# Optimize configuration for target window count
config = optimize_window_config(text, target_windows=10)

# Find natural boundaries in text
boundaries = find_natural_boundaries(text, preferred_size=1000)
```

## Performance Considerations

- **Memory Usage**: Streaming mode uses ~1MB buffer regardless of file size
- **Processing Speed**: Linear time complexity O(n) for window generation
- **Thread Safety**: Safe for concurrent use with minimal lock contention

## Integration with Tree-sitter Chunker

This sliding window engine integrates with the main chunker to provide:
- Text-based chunking as an alternative to AST-based chunking
- Hybrid chunking combining both approaches
- Token-aware windowing using the token counter

## Testing

Run tests with:
```bash
pytest tests/test_sliding_window.py -v
```

## Examples

See `examples/sliding_window_demo.py` for comprehensive usage examples including:
- Basic sliding window usage
- Line-based processing
- Dynamic adjustment
- File processing
- Navigation patterns
- Utility functions

## Algorithm Details

For detailed information about the sliding window algorithm implementation, see [docs/sliding_window_algorithm.md](docs/sliding_window_algorithm.md).
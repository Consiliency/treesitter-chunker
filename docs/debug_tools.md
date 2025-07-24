# Debug Tools Documentation

The Debug Tools component provides visualization and inspection capabilities for the TreeSitter Chunker, helping developers understand how code is parsed and chunked.

## Overview

The debug tools consist of two main components:

1. **DebugVisualization**: Provides AST visualization, chunk inspection, profiling, and debug mode chunking
2. **ChunkComparison**: Compares different chunking strategies to help choose the best approach

## Installation

The debug tools are included as part of the TreeSitter Chunker package. To use visualization features, you may need to install graphviz:

```bash
# Install graphviz (optional, for graph visualizations)
pip install graphviz

# On Ubuntu/Debian
sudo apt-get install graphviz

# On macOS
brew install graphviz
```

## Usage

### AST Visualization

Visualize the Abstract Syntax Tree of your code in different formats:

```python
from chunker.debug.tools import DebugVisualization

debug = DebugVisualization()

# Visualize as SVG (requires graphviz)
svg_output = debug.visualize_ast("example.py", "python", "svg")

# Visualize as JSON (no dependencies)
json_output = debug.visualize_ast("example.py", "python", "json")

# Get DOT format for further processing
dot_output = debug.visualize_ast("example.py", "python", "dot")
```

### Chunk Inspection

Inspect detailed information about specific chunks:

```python
# First, get chunks from your file
from chunker import chunk_file

chunks = chunk_file("example.py", "python")
chunk_id = chunks[0].chunk_id

# Inspect the chunk
info = debug.inspect_chunk("example.py", chunk_id, include_context=True)

# info contains:
# - id, type, start_line, end_line
# - content: the actual code
# - metadata: extracted metadata
# - relationships: parent, children, siblings
# - context: surrounding code
```

### Performance Profiling

Profile the chunking process to understand performance characteristics:

```python
metrics = debug.profile_chunking("large_file.py", "python")

print(f"Total time: {metrics['total_time']:.3f}s")
print(f"Memory peak: {metrics['memory_peak'] / 1024 / 1024:.1f}MB")
print(f"Chunks created: {metrics['chunk_count']}")
print(f"Average chunk size: {metrics['statistics']['average_chunk_size']:.1f} lines")

# Phase breakdown
for phase, time in metrics['phases'].items():
    print(f"  {phase}: {time:.3f}s")
```

### Debug Mode Chunking

Run chunking with detailed trace information:

```python
# Basic debug mode
trace = debug.debug_mode_chunking("example.py", "python")

print(f"Visited {trace['node_visits']} nodes")
print(f"Created {trace['chunks_created']} chunks")

# With breakpoints
trace = debug.debug_mode_chunking(
    "example.py", 
    "python",
    breakpoints=["function_definition", "class_definition"]
)

# Find breakpoint hits
for step in trace['steps']:
    if step.get('breakpoint'):
        print(f"Breakpoint at {step['node_type']} on line {step['start_line']}")
```

### Strategy Comparison

Compare different chunking strategies:

```python
from chunker.debug.tools import ChunkComparison

comparison = ChunkComparison()

result = comparison.compare_strategies(
    "example.py",
    "python",
    ["default", "token_aware", "semantic"]
)

# View results for each strategy
for strategy, metrics in result['strategies'].items():
    if 'error' not in metrics:
        print(f"{strategy}: {metrics['chunk_count']} chunks, "
              f"avg {metrics['average_lines']:.1f} lines")

# Check overlap between strategies
for overlap_key, overlap in result['overlaps'].items():
    print(f"{overlap_key}: {overlap['similarity']:.1%} similar")
```

## Available Strategies

The comparison tool supports these strategies:

- `default`: Standard tree-sitter based chunking
- `adaptive`: Adapts chunk size based on complexity
- `composite`: Combines multiple strategies
- `hierarchical`: Preserves code hierarchy
- `semantic`: Groups semantically related code
- `token_aware`: Respects token limits
- `fallback`: For files without tree-sitter support

## Output Formats

### Visualization Formats

- **SVG**: Scalable vector graphics (requires graphviz)
- **PNG**: Raster image (requires graphviz)
- **DOT**: Graphviz source format
- **JSON**: Structured data format

### Chunk Inspection Fields

- `id`: Unique chunk identifier
- `type`: Node type (function, class, etc.)
- `start_line`, `end_line`: Line boundaries
- `content`: Actual code content
- `metadata`: Language-specific metadata
- `relationships`: Parent/child/sibling relationships
- `context`: Surrounding code context

### Profiling Metrics

- `total_time`: Total processing time
- `memory_peak`: Peak memory usage
- `memory_current`: Current memory usage
- `chunk_count`: Number of chunks created
- `phases`: Time breakdown by phase
  - `parsing`: Tree-sitter parsing
  - `chunking`: Chunk extraction
  - `metadata`: Metadata extraction
- `statistics`: Additional statistics
  - `file_size`: File size in bytes
  - `total_lines`: Total line count
  - `average_chunk_size`: Average lines per chunk
  - `min_chunk_size`, `max_chunk_size`: Size range

## Examples

### Debugging Chunking Issues

```python
# When chunks are too large or small
trace = debug.debug_mode_chunking("problematic.py", "python")

# Analyze decision points
for decision in trace['decision_points']:
    print(f"Line {decision['line']}: {decision['decision']} - {decision['reason']}")
```

### Comparing Token-Aware Strategies

```python
# Compare token limits
result = comparison.compare_strategies(
    "large_file.py",
    "python", 
    ["default", "token_aware"]
)

# Find chunks that differ
for diff in result['differences']:
    print(f"{diff['strategy']} has unique chunk: {diff['unique_chunk']}")
```

### Visualizing with Chunks Highlighted

The visualizer automatically highlights chunks in the AST when they're available, making it easy to see chunk boundaries.

## Error Handling

All debug tools include proper error handling:

- `FileNotFoundError`: File doesn't exist
- `ValueError`: Invalid parameters (format, chunk ID, strategy)
- Language detection based on file extension

## Performance Considerations

- AST visualization can be memory-intensive for large files
- Profiling adds minimal overhead
- Strategy comparison runs each strategy sequentially
- Debug mode captures detailed traces which may impact performance

## Integration with CI/CD

The debug tools can be integrated into CI/CD pipelines for chunk analysis:

```python
# In CI script
metrics = debug.profile_chunking("src/main.py", "python")

# Fail if chunks are too large
if metrics['statistics']['max_chunk_size'] > 500:
    raise ValueError("Chunks too large for LLM context")

# Compare strategies for optimization
result = comparison.compare_strategies(
    "src/main.py", 
    "python",
    ["default", "token_aware"]
)

if result['strategies']['token_aware']['chunk_count'] < 
   result['strategies']['default']['chunk_count'] * 0.5:
    print("Consider using token_aware strategy")
```
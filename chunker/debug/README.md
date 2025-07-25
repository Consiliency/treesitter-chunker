# Debug & Visualization Tools

This component provides comprehensive debugging and visualization capabilities for the tree-sitter chunker.

## Overview

The Debug & Visualization Tools component implements two main contracts:
- **DebugVisualizationContract**: AST visualization, chunk inspection, performance profiling, and debug mode chunking
- **ChunkComparisonContract**: Strategy comparison and analysis

## Features

### AST Visualization
Generate visual representations of Abstract Syntax Trees in multiple formats:
- **JSON**: Structured JSON representation of the AST
- **DOT**: Graphviz DOT format for graph visualization
- **SVG/PNG**: Rendered visualizations (requires Graphviz)
- **Text**: Text-based representation (JSON format)

### Chunk Inspection
Detailed analysis of individual chunks:
- Chunk metadata and boundaries
- Relationships (parent, children, siblings)
- Context information (surrounding code)
- Language-specific details

### Performance Profiling
Profile chunking operations to identify bottlenecks:
- Timing metrics for each phase (parsing, chunking, metadata)
- Memory usage statistics
- File and chunk statistics
- Detailed performance breakdown

### Debug Mode Chunking
Step-by-step trace of the chunking process:
- Node visitation trace
- Decision points and rule applications
- Breakpoint support for specific node types
- Detailed debugging information

### Strategy Comparison
Compare different chunking strategies:
- Side-by-side metrics comparison
- Overlap analysis between strategies
- Difference detection
- Support for multiple strategy types:
  - default
  - adaptive
  - composite
  - hierarchical
  - semantic
  - token_aware
  - fallback

## Usage

### AST Visualization

```python
from chunker.debug import DebugVisualizationImpl

visualizer = DebugVisualizationImpl()

# Generate JSON representation
json_ast = visualizer.visualize_ast("example.py", "python", "json")

# Generate SVG visualization
svg_ast = visualizer.visualize_ast("example.py", "python", "svg")

# Generate DOT format
dot_ast = visualizer.visualize_ast("example.py", "python", "dot")
```

### Chunk Inspection

```python
# Inspect a specific chunk
chunk_info = visualizer.inspect_chunk(
    "example.py",
    "chunk_id_123",
    include_context=True
)

print(f"Chunk type: {chunk_info['type']}")
print(f"Lines: {chunk_info['start_line']}-{chunk_info['end_line']}")
print(f"Parent: {chunk_info['relationships']['parent']}")
```

### Performance Profiling

```python
# Profile chunking performance
profile = visualizer.profile_chunking("large_file.py", "python")

print(f"Total time: {profile['total_time']:.3f}s")
print(f"Memory peak: {profile['memory_peak'] / 1024 / 1024:.1f}MB")
print(f"Chunks created: {profile['chunk_count']}")
```

### Debug Mode

```python
# Run with breakpoints
trace = visualizer.debug_mode_chunking(
    "example.py",
    "python",
    breakpoints=["function_definition", "class_definition"]
)

print(f"Nodes visited: {trace['node_visits']}")
print(f"Chunks created: {trace['chunks_created']}")
```

### Strategy Comparison

```python
from chunker.debug import ChunkComparisonImpl

comparator = ChunkComparisonImpl()

# Compare different strategies
result = comparator.compare_strategies(
    "example.py",
    "python",
    ["default", "adaptive", "token_aware"]
)

for strategy, metrics in result['strategies'].items():
    print(f"{strategy}: {metrics['chunk_count']} chunks")
```

## Implementation Details

The component is structured as follows:

- **chunker/debug/visualization_impl.py**: Implementation of DebugVisualizationContract
- **chunker/debug/comparison.py**: Implementation of ChunkComparisonContract
- **chunker/debug/tools/**: Core implementation modules
  - **visualization.py**: AST visualization and profiling logic
  - **comparison.py**: Strategy comparison logic
- **chunker/debug/visualization/**: Visualization utilities
  - **ast_visualizer.py**: AST rendering and formatting
  - **chunk_visualizer.py**: Chunk boundary visualization
- **chunker/debug/interactive/**: Interactive debugging tools
  - **chunk_debugger.py**: Interactive chunk debugging
  - **node_explorer.py**: AST node exploration
  - **query_debugger.py**: Query debugging utilities
  - **repl.py**: Interactive REPL for debugging

## Dependencies

- **tree-sitter**: For AST parsing
- **graphviz** (optional): For SVG/PNG visualization
- **rich**: For console output formatting
- **tracemalloc**: For memory profiling

## Testing

The component includes comprehensive tests:
- Unit tests: `tests/test_debug_contract_impl.py`
- Integration tests: `tests/test_debug_tools_integration.py`
- Contract compliance: `tests/test_phase15_contract_compliance.py`

Run tests with:
```bash
python -m pytest tests/test_debug_contract_impl.py -xvs
python -m pytest tests/test_debug_tools_integration.py -xvs
```

## Performance Considerations

- AST visualization can be memory-intensive for large files
- Use `max_depth` parameter to limit visualization depth
- Profile results include memory usage to help identify issues
- Strategy comparison runs multiple chunking passes, so it's slower on large files

## Future Enhancements

- Real-time visualization updates
- Interactive debugging UI
- Export visualizations to more formats
- Performance comparison over time
- Integration with IDE plugins
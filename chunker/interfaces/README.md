# Tree-sitter Chunker Interfaces

This package contains the interface definitions for Phase 8 parallel development. All implementations in separate worktrees should inherit from these interfaces to ensure compatibility.

## Interface Overview

### Core Interfaces (`base.py`)

- **ChunkingStrategy**: Base interface for all chunking approaches
  - `can_handle()`: Check if strategy can handle a file
  - `chunk()`: Perform chunking on AST
  - `configure()`: Apply configuration

- **ASTProcessor**: Base for AST traversal and processing
  - `process_node()`: Process individual nodes
  - `should_process_children()`: Control traversal
  - `traverse()`: Template method for tree walking

- **ChunkFilter**: Filter chunks after extraction
- **ChunkMerger**: Merge related chunks

### Query Support (`query.py`)

- **QueryEngine**: Parse and execute Tree-sitter queries
  - `parse_query()`: Parse query strings
  - `execute_query()`: Run queries on AST
  - `validate_query()`: Check query syntax

- **QueryBasedChunker**: Chunking using Tree-sitter queries
  - `set_query()`: Set the chunking query
  - `merge_query_results()`: Convert matches to chunks

- **Query**, **QueryMatch**: Data structures for query results

### Context Extraction (`context.py`)

- **ContextExtractor**: Extract context from AST
  - `extract_imports()`: Find import statements
  - `extract_dependencies()`: Find dependencies
  - `build_context_prefix()`: Create context string

- **SymbolResolver**: Resolve symbol references
- **ScopeAnalyzer**: Analyze scope relationships
- **ContextFilter**: Filter relevant context

### Performance (`performance.py`)

- **CacheManager**: Manage various caches
  - `get()`, `put()`: Basic cache operations
  - `invalidate_pattern()`: Pattern-based invalidation
  - `get_stats()`: Cache statistics

- **IncrementalParser**: Support incremental parsing
  - `parse_incremental()`: Parse based on changes
  - `detect_changes()`: Find changed ranges

- **MemoryPool**: Reuse expensive objects
- **PerformanceMonitor**: Track performance metrics

### Export (`export.py`)

- **StructuredExporter**: Export with relationships
  - `export()`: Export chunks and relationships
  - `export_streaming()`: Stream large datasets

- **RelationshipTracker**: Track chunk relationships
- **GraphExporter**: Specialized graph format export
- **DatabaseExporter**: Database format export

### Grammar Management (`grammar.py`)

- **GrammarManager**: Manage Tree-sitter grammars
  - `add_grammar()`: Add new grammar
  - `fetch_grammar()`: Download grammar source
  - `build_grammar()`: Compile grammar

- **GrammarBuilder**: Build grammars from source
- **GrammarRepository**: Repository of known grammars
- **GrammarValidator**: Validate grammar compatibility

### Fallback Support (`fallback.py`)

**Important**: These are last-resort interfaces for files without Tree-sitter support.

- **FallbackChunker**: Non-AST chunking
  - `chunk_by_lines()`: Line-based chunking
  - `chunk_by_delimiter()`: Delimiter-based
  - `emit_warning()`: Warn about fallback usage

- **LogChunker**: Specialized for log files
- **MarkdownChunker**: Markdown without Tree-sitter

### Debugging (`debug.py`)

- **ASTVisualizer**: Visualize ASTs
  - `visualize()`: Create visual representation
  - `visualize_with_chunks()`: Show chunk boundaries

- **QueryDebugger**: Debug Tree-sitter queries
- **ChunkDebugger**: Debug chunking behavior
- **NodeExplorer**: Interactive AST exploration

## Implementation Guidelines

### 1. Inherit from Interfaces

```python
from chunker.interfaces import ChunkingStrategy
from chunker.types import CodeChunk

class MyChunker(ChunkingStrategy):
    def can_handle(self, file_path: str, language: str) -> bool:
        return language in ['python', 'javascript']
    
    def chunk(self, ast: Node, source: bytes, file_path: str, language: str) -> List[CodeChunk]:
        # Implementation
        pass
```

### 2. Use Stub Implementations for Testing

```python
from chunker.interfaces.stubs import QueryEngineStub

def test_my_feature():
    query_engine = QueryEngineStub()
    # Test your code that depends on QueryEngine
```

### 3. Follow Interface Contracts

Each interface method has specific contracts documented in docstrings. Follow these carefully to ensure compatibility.

### 4. Coordinate on Shared Data Structures

Use the common data structures defined in the interfaces:
- `CodeChunk` from `chunker.types`
- `QueryMatch`, `ContextItem`, etc. from interface modules

## Worktree Assignments

| Worktree | Primary Interfaces | Key Responsibilities |
|----------|-------------------|---------------------|
| query-support | QueryEngine, Query | Tree-sitter query implementation |
| more-grammars | GrammarManager | Add language grammars |
| smart-context | ContextExtractor | AST-based context extraction |
| treesitter-enhanced | ChunkingStrategy | Advanced chunking features |
| ast-performance | CacheManager, IncrementalParser | Performance optimization |
| structured-export | StructuredExporter | Export with relationships |
| treesitter-debug | ASTVisualizer, QueryDebugger | Debugging tools |
| minimal-fallback | FallbackChunker | Last-resort chunking |

## Testing

1. Write unit tests against interfaces using stubs
2. Create integration tests that verify interface contracts
3. Test error handling and edge cases
4. Verify thread safety where applicable

## Merge Preparation

Before merging your worktree:
1. Ensure all interface methods are implemented
2. Add comprehensive tests
3. Document any deviations or extensions
4. Verify no coupling to other worktree implementations

## Questions?

If you need clarification on any interface:
1. Check the docstrings in the interface files
2. Look at the stub implementations for examples
3. Coordinate through the main repository issues
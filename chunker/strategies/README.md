# Enhanced Chunking Strategies

This directory contains advanced chunking strategies that go beyond basic function/class extraction. Each strategy uses Tree-sitter's full AST capabilities to create intelligent, semantically-aware chunks.

## Available Strategies

### 1. SemanticChunker
Uses AST semantics for intelligent chunk boundaries based on code meaning and relationships.

**Features:**
- Analyzes semantic roles (initialization, validation, computation, I/O, etc.)
- Groups semantically related code
- Considers coupling and dependencies
- Splits complex functions intelligently
- Preserves semantic cohesion

**Best for:**
- Creating meaningful code segments for documentation
- Grouping related functionality
- Understanding code organization

### 2. HierarchicalChunker
Preserves nested structure relationships and creates a hierarchy of chunks.

**Features:**
- Maintains parent-child relationships
- Supports tree-based navigation
- Configurable granularity (fine, balanced, coarse)
- Preserves structural context
- Optimizes chunk hierarchy

**Best for:**
- Code navigation systems
- Maintaining structural context
- Understanding code organization
- IDE-like features

### 3. AdaptiveChunker
Dynamically adjusts chunk size based on code complexity and other metrics.

**Features:**
- Smaller chunks for complex code
- Larger chunks for simple, cohesive code
- Considers complexity, coupling, and density
- Balances chunk sizes
- Respects natural boundaries

**Best for:**
- LLM context windows
- Optimizing for processing constraints
- Handling varied codebases

### 4. CompositeChunker
Combines multiple strategies using configurable fusion methods.

**Features:**
- Runs multiple strategies in parallel
- Fusion methods: union, intersection, consensus, weighted
- Handles overlapping chunks
- Quality-based filtering
- Strategy weighting

**Best for:**
- Production systems needing robustness
- Combining strengths of different approaches
- Customizable chunking pipelines

## Usage Examples

### Basic Usage

```python
from chunker.strategies import SemanticChunker
from chunker.parser import get_parser

# Parse your code
parser = get_parser("python")
tree = parser.parse(source_code.encode())

# Create and configure chunker
chunker = SemanticChunker()
chunker.configure({
    'merge_related': True,
    'complexity_threshold': 15.0
})

# Get chunks
chunks = chunker.chunk(tree.root_node, source_code.encode(), "file.py", "python")
```

### Using Profiles

```python
from chunker.strategies import CompositeChunker
from chunker.config import get_profile

# Load a predefined profile
profile = get_profile('code_review')

# Create chunker with profile
chunker = CompositeChunker()
chunker.configure(profile.config.composite)

# Chunk your code
chunks = chunker.chunk(tree.root_node, source_code.encode(), "file.py", "python")
```

### Custom Configuration

```python
from chunker.config import StrategyConfig

# Create custom configuration
config = StrategyConfig(
    min_chunk_size=20,
    max_chunk_size=150,
    semantic={
        'complexity_threshold': 12.0,
        'merge_related': True
    },
    adaptive={
        'base_chunk_size': 40,
        'adaptive_aggressiveness': 0.75
    }
)

# Apply to a strategy
chunker = AdaptiveChunker()
chunker.configure(config.get_strategy_config('adaptive'))
```

## Configuration Options

### Common Options
- `min_chunk_size`: Minimum chunk size in lines
- `max_chunk_size`: Maximum chunk size in lines

### Strategy-Specific Options

See each strategy's class documentation for detailed configuration options.

## Analysis Tools

The strategies use advanced AST analysis tools:

- **ComplexityAnalyzer**: Calculates cyclomatic and cognitive complexity
- **CouplingAnalyzer**: Analyzes dependencies and relationships
- **SemanticAnalyzer**: Understands code semantics and patterns

## Performance Considerations

- SemanticChunker: Higher overhead due to deep analysis
- HierarchicalChunker: Efficient for navigation-focused use cases
- AdaptiveChunker: Good balance of quality and performance
- CompositeChunker: Overhead depends on enabled strategies

## Extending Strategies

All strategies implement the `ChunkingStrategy` interface:

```python
from chunker.interfaces.base import ChunkingStrategy

class CustomChunker(ChunkingStrategy):
    def can_handle(self, file_path: str, language: str) -> bool:
        # Return True if this strategy can handle the file
        pass
    
    def chunk(self, ast: Node, source: bytes, file_path: str, language: str) -> List[CodeChunk]:
        # Implement chunking logic
        pass
    
    def configure(self, config: Dict[str, Any]) -> None:
        # Handle configuration updates
        pass
```
# Worktree Development Guide

This guide helps developers working in Phase 8 worktrees implement features against the common interfaces while avoiding merge conflicts.

## Getting Started

### 1. Set Up Your Worktree

After your worktree is created:

```bash
cd ../treesitter-chunker-worktrees/[your-worktree]
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"
uv pip install git+https://github.com/tree-sitter/py-tree-sitter.git

# Build grammars
python scripts/fetch_grammars.py
python scripts/build_lib.py
```

### 2. Understand Your Interfaces

Your primary interfaces are in `chunker/interfaces/`. Start by reading:
- The specific interface files you'll implement
- The README.md in the interfaces directory
- The docstrings for each method

### 3. Create Your Implementation Module

Create your implementation in the appropriate location:
- Query support → `chunker/query/`
- Context extraction → `chunker/context/`
- Performance → `chunker/performance/`
- etc.

## Development Workflow

### Step 1: Import Interfaces

```python
from chunker.interfaces import YourInterface
from chunker.interfaces.stubs import DependencyStub
```

### Step 2: Create Initial Implementation

```python
class YourImplementation(YourInterface):
    """Implementation of YourInterface for specific feature."""
    
    def __init__(self):
        # Use stubs for dependencies from other worktrees
        self.dependency = DependencyStub()
    
    def interface_method(self, *args, **kwargs):
        # Implement according to interface contract
        pass
```

### Step 3: Write Tests First

```python
import pytest
from chunker.interfaces.stubs import YourInterfaceStub

def test_interface_contract():
    """Test that implementation follows interface contract."""
    impl = YourImplementation()
    
    # Test each interface method
    result = impl.interface_method(test_input)
    assert result meets interface contract
```

### Step 4: Implement Incrementally

1. Start with the simplest interface method
2. Get tests passing
3. Move to next method
4. Refactor as needed

## Interface Implementation Checklist

- [ ] All abstract methods implemented
- [ ] Method signatures match interface exactly
- [ ] Return types match interface specification
- [ ] Exceptions match interface documentation
- [ ] Thread safety considered (if applicable)
- [ ] Performance characteristics documented

## Common Patterns

### Using Stubs for Dependencies

When your implementation needs something from another worktree:

```python
from chunker.interfaces.stubs import QueryEngineStub

class MyFeature:
    def __init__(self, query_engine=None):
        self.query_engine = query_engine or QueryEngineStub()
```

### Extending Interfaces

If you need additional functionality:

```python
class ExtendedInterface(BaseInterface):
    """Extended interface with additional methods."""
    
    # Original interface methods...
    
    def additional_method(self):
        """Document why this is needed."""
        pass
```

Document extensions clearly for merge coordination.

### Configuration Handling

Use consistent configuration patterns:

```python
from chunker.config import ChunkerConfig

class MyImplementation(MyInterface):
    def configure(self, config: Dict[str, Any]) -> None:
        # Validate configuration
        self._validate_config(config)
        
        # Apply configuration
        self.option1 = config.get('option1', default_value)
```

## Testing Guidelines

### Unit Tests

Test your implementation in isolation:

```python
def test_implementation_behavior():
    impl = YourImplementation()
    # Test specific behavior
    
def test_interface_compliance():
    impl = YourImplementation()
    # Verify interface contract
```

### Integration Tests

Create integration tests using stubs:

```python
def test_integration_with_stub():
    impl = YourImplementation()
    stub = DependencyStub()
    
    # Test interaction
    result = impl.process_with_dependency(stub)
    assert result is valid
```

### Performance Tests

If your feature affects performance:

```python
def test_performance_characteristics():
    impl = YourImplementation()
    
    start = time.time()
    for _ in range(1000):
        impl.performance_critical_method()
    duration = time.time() - start
    
    assert duration < acceptable_threshold
```

## Coordination Points

### Shared Data Structures

Always use the common types:
- `CodeChunk` from `chunker.types`
- Interface-defined types (QueryMatch, ContextItem, etc.)

### Error Handling

Follow the project's error hierarchy:
```python
from chunker.exceptions import ChunkerError

class YourFeatureError(ChunkerError):
    """Specific error for your feature."""
    pass
```

### Logging

Use consistent logging:
```python
import logging

logger = logging.getLogger(__name__)

class YourImplementation:
    def method(self):
        logger.debug("Processing started")
        try:
            # Implementation
            logger.info("Processing completed")
        except Exception as e:
            logger.error(f"Processing failed: {e}")
            raise
```

## Pre-Merge Checklist

Before creating a PR from your worktree:

- [ ] All interface methods implemented
- [ ] All tests passing
- [ ] Documentation complete
- [ ] No dependencies on other worktree implementations
- [ ] Code follows project style guide
- [ ] Performance impact documented
- [ ] Breaking changes documented (if any)

## Merge Conflict Prevention

### DO:
- Implement only your assigned interfaces
- Use stubs for external dependencies
- Add new files rather than modifying existing ones
- Document any necessary changes to shared files

### DON'T:
- Modify interfaces after starting implementation
- Change shared data structures
- Import from other worktrees
- Modify another feature's code

## Communication

### When to Communicate

Reach out when you:
- Need to extend an interface
- Find an issue with an interface definition
- Need functionality from another worktree
- Want to change shared code

### How to Communicate

1. Create an issue in the main repository
2. Tag relevant worktree owners
3. Propose solution with minimal impact
4. Wait for consensus before proceeding

## Troubleshooting

### Import Errors

If you get import errors:
1. Ensure you're importing from `chunker.interfaces`
2. Check that you've installed in development mode: `pip install -e .`
3. Verify the main branch has been pulled recently

### Stub Limitations

If a stub doesn't provide enough functionality:
1. Create a local mock for testing
2. Document what additional stub methods are needed
3. Create an issue for stub enhancement

### Interface Mismatches

If the interface doesn't match your needs:
1. First try to work within the interface
2. Document the limitation
3. Propose interface enhancement for next phase

## Example: Query Support Implementation

Here's a simplified example:

```python
# chunker/query/engine.py
from chunker.interfaces import QueryEngine, Query
from tree_sitter import Parser

class TreeSitterQueryEngine(QueryEngine):
    """Tree-sitter query engine implementation."""
    
    def __init__(self):
        self._parser_cache = {}
    
    def parse_query(self, query_string: str, language: str) -> Query:
        """Parse a Tree-sitter query string."""
        # Implementation details...
        return TreeSitterQuery(parsed_query)
    
    def execute_query(self, ast: Node, query: Query) -> List[QueryMatch]:
        """Execute query on AST."""
        # Implementation details...
        return matches
    
    def validate_query(self, query_string: str, language: str) -> Tuple[bool, Optional[str]]:
        """Validate query syntax."""
        try:
            self.parse_query(query_string, language)
            return True, None
        except QuerySyntaxError as e:
            return False, str(e)
```

Remember: The goal is parallel development without conflicts. When in doubt, communicate!
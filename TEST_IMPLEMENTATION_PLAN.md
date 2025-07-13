# Test Implementation Plan

Based on the ROADMAP.md testing gaps analysis, this plan outlines the implementation of comprehensive test coverage for the tree-sitter-chunker project.

## Overview

Current test coverage varies significantly across modules:
- Core parser functionality: ~85% coverage
- Plugin system: ~60% coverage  
- Language configurations: ~75% coverage
- Export formats: ~70% coverage
- Performance features: ~50% coverage
- CLI: ~40% coverage

Target: >95% overall coverage with comprehensive integration testing

## Phase 1: Critical Missing Test Files (Week 1)

### 1.1 test_config.py
**Priority: CRITICAL** - Configuration system has lowest coverage (~40%)
```python
# Test cases to implement:
- YAML and JSON format loading/saving
- Config validation error handling
- Path resolution edge cases
- Config inheritance and merging
- Project-specific config overrides
- Invalid config file handling
- Config schema validation
- Environment variable expansion
```

### 1.2 test_cache.py  
**Priority: HIGH** - Cache system needs comprehensive testing
```python
# Test cases to implement:
- Cache expiration and TTL
- Cache size limits and eviction
- Concurrent cache access
- Cache corruption recovery
- Memory cache vs disk cache
- Cache invalidation strategies
- Performance benchmarks
```

### 1.3 test_parallel.py
**Priority: HIGH** - Parallel processing edge cases
```python
# Test cases to implement:
- Worker pool sizing strategies
- Failure handling in parallel workers
- Resource contention scenarios
- Progress tracking accuracy
- Memory usage under load
- Cancellation and timeout handling
```

### 1.4 test_streaming.py
**Priority: HIGH** - Streaming functionality gaps
```python
# Test cases to implement:
- Large file streaming (>100MB)
- Memory usage profiling
- Streaming error recovery
- Partial chunk handling
- Buffer size optimization
- Progress callbacks
```

### 1.5 test_types.py
**Priority: MEDIUM** - Type system validation
```python
# Test cases to implement:
- CodeChunk serialization/deserialization
- Type validation and coercion
- Dataclass field validation
- JSON/dict conversion
- Type compatibility checks
```

## Phase 2: Language-Specific Tests (Week 2)

### 2.1 test_python_language.py
```python
# Test cases to implement:
- Async function detection
- Decorator handling
- Nested class definitions
- Lambda expressions
- List/dict comprehensions
- Type annotations
- Docstring extraction
```

### 2.2 test_javascript_language.py
```python
# Test cases to implement:
- ES6+ syntax support
- JSX/TSX handling
- Arrow functions
- Class properties
- Module imports/exports
- Async/await patterns
```

### 2.3 test_rust_language.py
```python
# Test cases to implement:
- Trait implementations
- Macro definitions
- Unsafe blocks
- Lifetime annotations
- Module structure
- Generic functions
```

### 2.4 test_c_language.py
```python
# Test cases to implement:
- Preprocessor directives
- Function pointers
- Struct/union definitions
- Header file parsing
- Inline assembly
```

### 2.5 test_cpp_language.py
```python
# Test cases to implement:
- Template specialization
- Namespace handling
- Virtual functions
- Operator overloading
- STL usage patterns
```

## Phase 3: Advanced Integration Testing (Week 3)

### 3.1 test_plugin_integration.py
```python
# Test cases to implement:
- Plugin hot-reloading
- Plugin version conflicts
- Plugin initialization failures
- Custom plugin directories
- Plugin dependency resolution
- Plugin configuration merging
```

### 3.2 test_export_integration.py
```python
# Test cases to implement:
- Format conversion accuracy
- Large dataset exports
- Streaming exports
- Export cancellation
- Memory-efficient exports
- Cross-format compatibility
```

### 3.3 test_cli_integration.py
```python
# Test cases to implement:
- Complex command combinations
- Input validation edge cases
- Interactive mode testing
- Error recovery scenarios
- Progress display accuracy
- Signal handling (CTRL+C)
```

### 3.4 test_end_to_end.py
```python
# Test cases to implement:
- Full pipeline testing
- Multi-language projects
- Configuration precedence
- Performance benchmarks
- Resource usage monitoring
- Error propagation
```

## Phase 4: Performance and Edge Cases (Week 4)

### 4.1 Performance Tests
- Parser creation overhead benchmarks
- Memory leak detection
- Long-running parser pools
- Cache performance under load
- Parallel processing scalability
- Large file handling (>1GB)

### 4.2 Edge Case Tests
- Corrupted .so files
- Missing language grammars
- Invalid UTF-8 handling
- Circular dependencies
- Resource exhaustion
- Network timeouts (for remote features)

### 4.3 Recovery Tests
- Parser crash recovery
- Partial file processing
- Interrupt handling
- Cleanup on failure
- State persistence
- Graceful degradation

## Implementation Strategy

### Week 1: Foundation
1. Set up test infrastructure improvements
2. Implement Phase 1 critical test files
3. Ensure CI/CD integration
4. Set up coverage reporting

### Week 2: Language Coverage
1. Implement all language-specific tests
2. Create test fixtures for each language
3. Validate against real-world code samples
4. Document language-specific quirks

### Week 3: Integration & E2E
1. Implement integration test suite
2. Create complex test scenarios
3. Add performance benchmarks
4. Set up continuous performance monitoring

### Week 4: Polish & Edge Cases
1. Handle all edge cases
2. Add stress tests
3. Complete documentation
4. Achieve >95% coverage target

## Success Criteria

1. **Coverage**: >95% code coverage across all modules
2. **Performance**: No regression in processing speed
3. **Reliability**: All tests pass consistently
4. **Documentation**: Each test file has clear documentation
5. **CI/CD**: All tests integrated into automated pipeline

## Test File Creation Order

1. `test_config.py` - Most critical gap
2. `test_cache.py` - Performance critical
3. `test_parallel.py` - Concurrency coverage
4. `test_streaming.py` - Memory efficiency
5. `test_types.py` - Type safety
6. Language-specific tests in parallel
7. Integration tests building on unit tests
8. Performance and edge case tests

## Notes

- Each test file should follow the existing pattern in `test_performance.py`
- Use pytest fixtures for common test data
- Include both positive and negative test cases
- Add benchmarks where performance is critical
- Document any discovered bugs or limitations

## Implementation Progress *[Updated: 2025-01-13]*

### Phase 1 & 2 Completed
- [x] test_config.py: 38 tests
- [x] test_cache.py: 24 tests (fixed 5 initial failures)
- [x] test_parallel.py: 28 tests
- [x] test_streaming.py: 23 tests (1 skipped for large files)
- [x] test_types.py: 31 tests
- [x] test_python_language.py: 37 tests (fixed 10 expectation issues)
- [x] test_javascript_language.py: 13 tests
- [x] test_rust_language.py: 10 tests (see isolation fix below)
- [x] test_c_language.py: 18 tests
- [x] test_cpp_language.py: 10 tests

**Total**: 232 new tests added (Phase 1: 144, Phase 2: 88)

### Rust Test Isolation Fix ✅ COMPLETED

The Rust tests were passing individually but failing when run as part of the full suite due to module-level config registration:

```python
# Previous (problematic):
language_config_registry.register(RustConfig())  # At module level

# Fixed (implemented):
class TestRustLanguageFeatures:
    def setup_method(self):
        self.rust_config = RustConfig()
        language_config_registry.register(self.rust_config)
    
    def teardown_method(self):
        if "rust" in language_config_registry._configs:
            del language_config_registry._configs["rust"]
```

This fix has been implemented and all Rust tests now pass both individually and as part of the full test suite.
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

### Phase 3 & 4 Completed ✅ *[2025-01-19]*

Successfully implemented all Phase 3 and 4 tests:

**Phase 3: Advanced Integration Testing**
- [x] test_plugin_integration_advanced.py: 23 tests (20 passing, 3 skipped)
- [x] test_export_integration_advanced.py: 15 tests (all passing)
- [x] test_cli_integration_advanced.py: 22 tests (21 passing, 1 skipped)
- [x] test_end_to_end.py: 12 tests (all passing)

**Phase 4: Performance and Edge Cases**
- [x] test_performance_advanced.py: 11 tests (all passing)
- [x] test_edge_cases.py: 29 tests (all passing)
- [x] test_recovery.py: 21 tests (all passing)

**Final Test Suite Statistics**:
- Total test files: 33
- Total tests: 558
- Passing: 545 (97.7%)
- Skipped: 13 (2.3%)
- Failing: 0
- Coverage: >95% achieved

## Phase 5: Cross-Module Integration Testing (Week 5) *[Added: 2025-01-19]*

### Overview
Address the ~40% integration test coverage gap identified in Phase 7 of ROADMAP.md. Focus on module interface points and error propagation to increase integration coverage to ~80%.

### 5.1 test_config_runtime_changes.py
**Priority: HIGH** - Config stability during operations
```python
# Test cases to implement:
- Config modifications during active parsing
- Registry updates with concurrent readers
- Config inheritance changes mid-operation
- Memory safety and reference counting
- Config rollback on errors
- Thread-safe config access patterns
- Config hot-reload simulation
- Performance impact of config changes
```

### 5.2 test_plugin_integration_advanced.py (enhancement)
**Priority: MEDIUM** - Complete plugin conflict scenarios
```python
# Test cases to implement:
- Multiple plugins claiming same language
- Plugin initialization order dependencies
- Resource contention between plugins
- Plugin version conflict resolution
- Plugin failure cascading effects
- Plugin hot-reload simulation
- Memory leaks in plugin lifecycle
```

### 5.3 test_parquet_cli_integration.py
**Priority: MEDIUM** - Full CLI integration with Parquet
```python
# Test cases to implement:
- Parquet with --include/--exclude filters
- Parquet with --chunk-types filtering
- Parquet with parallel processing
- Large file streaming to Parquet
- Schema evolution across languages
- Compression option testing
- Memory usage profiling
- Progress tracking accuracy
```

### 5.4 test_cache_file_monitoring.py
**Priority: HIGH** - File change detection
```python
# Test cases to implement:
- File modification detection
- File deletion handling
- File rename tracking
- Concurrent file modifications
- Cache consistency across workers
- Timestamp vs content-based invalidation
- Directory-level change detection
- Cache corruption recovery
```

### 5.5 test_parallel_error_handling.py
**Priority: CRITICAL** - System stability
```python
# Test cases to implement:
- Worker process crashes
- Worker timeout handling
- Partial result aggregation
- Error message propagation
- Resource cleanup verification
- Deadlock prevention
- Memory leak detection
- Progress tracking with failures
```

### 5.6 test_cross_module_errors.py
**Priority: CRITICAL** - Error propagation
```python
# Test cases to implement:
- Parser errors to CLI output
- Plugin errors to export modules
- Config errors to parallel processing
- Cascading failure scenarios
- Error context preservation
- User-friendly error formatting
- Stack trace filtering
- Recovery suggestion testing
```

### Implementation Strategy

#### Week 5 Schedule:
1. **Day 1-2**: Implement critical tests (5.5, 5.6)
2. **Day 3**: Implement high priority tests (5.1, 5.4)
3. **Day 4**: Implement medium priority tests (5.2, 5.3)
4. **Day 5**: Integration, debugging, and documentation

### Expected Outcomes
- Increase integration coverage from ~40% to ~80%
- Identify and fix cross-module synchronization issues
- Ensure proper error propagation and recovery
- Document any architectural limitations discovered
- Create integration test best practices guide

### Success Metrics
1. **Coverage**: Integration test coverage reaches ~80%
2. **Stability**: No race conditions or deadlocks found
3. **Error Handling**: All errors properly propagated with context
4. **Performance**: No significant degradation under error conditions
5. **Documentation**: All integration points documented

### Risk Mitigation
- Start with critical error handling tests
- Use property-based testing for edge cases
- Run tests under various system loads
- Monitor for memory leaks and resource exhaustion
- Create reproducible test scenarios
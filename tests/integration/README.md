# Integration Test Framework

This directory contains the shared interfaces and utilities for cross-module integration testing across multiple phases (7-15).

## Overview

The integration test framework ensures consistent testing across multiple parallel worktrees by providing:
- Common interface definitions with full implementations
- Shared error and event formats  
- Comprehensive reusable test fixtures
- Thread-safe coordination utilities
- Performance monitoring tools

## Interfaces

### ErrorPropagationMixin
Tracks error propagation across module boundaries:
- `capture_cross_module_error()` - Capture errors with full context including traceback and call stack
- `verify_error_context()` - Verify errors contain expected information
- Automatically extracts traceback and call stack information
- Thread-safe for concurrent error tracking

### ConfigChangeObserver
Monitors configuration changes during runtime:
- `on_config_change()` - Record configuration change events with timestamp
- `get_affected_modules()` - Determine impact of changes based on configuration mappings
- `register_observer()` - Register callbacks for configuration changes
- `get_change_log()` - Retrieve all configuration changes
- Maintains mapping of config keys to affected modules

### ResourceTracker
Ensures proper resource lifecycle management:
- `track_resource()` - Register resource allocation with timestamp
- `release_resource()` - Mark resources as released with cleanup time
- `verify_cleanup()` - Check for resource leaks by module
- `get_resource_state()` - Query individual resource status
- `get_all_resources()` - Filter resources by module or state

## Standard Formats

### Error Context Format
```python
{
    'source_module': str,      # Origin module (e.g., 'chunker.parallel')
    'target_module': str,      # Destination module (e.g., 'cli.main')
    'operation': str,          # Operation/class that failed
    'original_error': Exception,
    'error_type': str,         # Type name of exception
    'error_message': str,      # String representation
    'timestamp': float,        # When error occurred
    'context_data': {
        'traceback': List[str],  # Full traceback
        'call_stack': List[str]  # Call stack frames
    }
}
```

### Config Change Event Format
```python
{
    'config_path': str,        # Configuration key (e.g., 'parser_timeout')
    'old_value': Any,          # Previous value
    'new_value': Any,          # New value
    'affected_modules': List[str],  # Modules impacted
    'timestamp': float         # When change occurred
}
```

### Resource Tracking Format
```python
{
    'resource_id': str,        # Unique identifier
    'resource_type': str,      # 'process', 'file_handle', 'lock', etc.
    'owner_module': str,       # Module that owns it
    'created_at': float,       # Creation timestamp
    'state': str,              # 'active', 'released', 'leaked'
    'metadata': dict,          # Resource-specific data
    'released_at': float       # Release timestamp (if released)
}
```

## Available Fixtures

### Basic Fixtures
- `temp_workspace` - Temporary directory with standard subdirs (src/, tests/, cache/, output/)
- `sample_code_files` - Sample code in Python, JavaScript, Rust, and C

### Error Tracking
- `error_tracking_context` - Context manager for tracking errors with handlers
  - Captures uncaught exceptions automatically
  - Supports registering error handlers by module
  - Thread-safe error chain tracking

### Configuration Management
- `config_change_tracker` - Tracks configuration changes with observers
  - Automatic change logging
  - Observer pattern for change notifications

### Resource Management
- `resource_monitor` - Monitors resource allocation and cleanup
  - Helper method `assert_no_leaks()` for testing
  - Tracks resources by module and state

### Testing Utilities
- `parallel_test_environment` - Manages processes/threads for parallel tests
  - Creates tracked workers (processes and threads)
  - Shared synchronization primitives (locks, queues, events)
  - Automatic cleanup on exit

- `mock_parser_factory` - Controllable mock parser for failure testing
  - Configure failures: always fail, fail on Nth call, timeout
  - Tracks parse count and simulates syntax trees

- `test_file_generator` - Generate test files with specific patterns
  - Create large files with repeated patterns
  - Generate files with specific error types (syntax, unicode, binary)
  - Automatic cleanup of generated files

- `async_test_runner` - Runner for async test scenarios
  - Run single or parallel async operations
  - Timeout support for async operations
  - Automatic task cleanup

### Performance and Concurrency
- `thread_safe_counter` - Thread-safe counter for concurrent operations
- `performance_monitor` - Track operation timings and statistics
  - Context manager for timing blocks
  - Statistical analysis (min, max, average)

## Usage Examples

### Error Propagation Testing
```python
from tests.integration.interfaces import ErrorPropagationMixin

class TestCrossModuleErrors(ErrorPropagationMixin):
    def test_error_propagation(self):
        # Simulate error
        error = ValueError("Parser timeout")
        
        # Capture with full context
        context = self.capture_cross_module_error(
            source_module='chunker.parser',
            target_module='cli.main',
            error=error
        )
        
        # Verify context
        self.verify_error_context(context, {
            'source_module': 'chunker.parser',
            'error_type': 'ValueError'
        })
        
        # Check traceback was captured
        assert 'traceback' in context['context_data']
```

### Resource Tracking
```python
def test_resource_cleanup(resource_monitor):
    # Track resource allocation
    resource_monitor.track_resource(
        module='chunker.parallel',
        resource_type='process',
        resource_id='worker_12345'
    )
    
    # Simulate work...
    
    # Release resource
    resource_monitor.release_resource('worker_12345')
    
    # Verify cleanup
    resource_monitor.assert_no_leaks('chunker.parallel')
```

### Parallel Testing
```python
def test_concurrent_operations(parallel_test_environment):
    with parallel_test_environment as env:
        # Create synchronized workers
        lock = env.create_shared_lock('data_lock')
        queue = env.create_queue('results')
        
        def worker_func(worker_id):
            with lock:
                # Critical section
                queue.put(f"Result from {worker_id}")
        
        # Launch workers
        workers = []
        for i in range(4):
            w = env.create_worker_process(worker_func, args=(i,))
            w.start()
            workers.append(w)
        
        # Collect results
        results = []
        for _ in range(4):
            results.append(queue.get(timeout=5))
        
        # Cleanup happens automatically
```

### Mock Parser Testing
```python
def test_parser_failures(mock_parser_factory):
    # Configure parser to fail on 3rd call
    mock_parser_factory.configure_failure(
        'python', 
        fail_type='nth_call', 
        n=3
    )
    
    parser = mock_parser_factory.get_parser('python')
    
    # First two calls succeed
    parser.parse(b"def test(): pass")
    parser.parse(b"class Foo: pass")
    
    # Third call fails
    with pytest.raises(RuntimeError):
        parser.parse(b"import sys")
```

## Best Practices

1. **Thread Safety** - All interfaces are thread-safe; use them in concurrent tests
2. **Resource Tracking** - Always track resources that need cleanup
3. **Error Context** - Capture full context including tracebacks for debugging
4. **Configuration Changes** - Use observers to react to config changes
5. **Performance Monitoring** - Track timing for performance-sensitive operations
6. **Cleanup** - Use context managers and fixtures for automatic cleanup
7. **Mock Control** - Use mock factories to simulate specific failure scenarios

## Integration Test Implementation

When implementing integration tests:

1. Import required interfaces and fixtures
2. Use standard formats for consistency
3. Track all resources that need cleanup
4. Capture errors with full context
5. Use performance monitoring for timing-sensitive tests
6. Leverage parallel test environment for concurrency tests
7. Always verify cleanup in teardown

## Testing the Framework

Run the integration test framework tests:
```bash
pytest tests/integration/test_interfaces.py -v
pytest tests/integration/test_fixtures.py -v
```

## Coordination Between Worktrees

1. This coordinator worktree implements all interfaces first
2. Other worktrees pull these changes before starting
3. All worktrees use the same error/event formats
4. Resource tracking is consistent across all tests
5. Performance metrics use the same monitoring tools

This ensures maximum consistency and code reuse across the Phase 7 integration testing effort.
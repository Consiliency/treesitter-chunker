# Integration Test Framework

This directory contains the shared interfaces and utilities for Phase 7 cross-module integration testing.

## Overview

The integration test framework ensures consistent testing across multiple parallel worktrees by providing:
- Common interface definitions
- Shared error and event formats  
- Reusable test fixtures
- Coordination utilities

## Interfaces

### ErrorPropagationMixin
Tracks error propagation across module boundaries:
- `capture_cross_module_error()` - Capture errors with full context
- `verify_error_context()` - Verify errors contain expected information

### ConfigChangeObserver
Monitors configuration changes during runtime:
- `on_config_change()` - Record configuration change events
- `get_affected_modules()` - Determine impact of changes

### ResourceTracker
Ensures proper resource lifecycle management:
- `track_resource()` - Register resource allocation
- `release_resource()` - Mark resources as released
- `verify_cleanup()` - Check for resource leaks

## Standard Formats

### Error Context Format
```python
{
    'source_module': str,      # Origin module
    'target_module': str,      # Destination module  
    'operation': str,          # Operation that failed
    'original_error': Exception,
    'error_type': str,
    'error_message': str,
    'timestamp': float,
    'context_data': dict       # Additional context
}
```

### Config Change Event Format
```python
{
    'config_path': str,        # Configuration key
    'old_value': Any,          # Previous value
    'new_value': Any,          # New value
    'affected_modules': List[str],
    'timestamp': float
}
```

### Resource Tracking Format
```python
{
    'resource_id': str,        # Unique identifier
    'resource_type': str,      # Type of resource
    'owner_module': str,       # Module that owns it
    'created_at': float,
    'state': str,              # 'active' or 'released'
    'metadata': dict           # Resource-specific data
}
```

## Usage Example

```python
from tests.integration.interfaces import (
    ErrorPropagationMixin, 
    ConfigChangeObserver,
    ResourceTracker
)

class TestCrossModuleErrors(ErrorPropagationMixin):
    def test_error_propagation(self):
        # Simulate error
        error = ValueError("Test error")
        
        # Capture with context
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
```

## Best Practices

1. **Always use standard formats** - Ensures consistency across tests
2. **Track all resources** - Use ResourceTracker for anything that needs cleanup
3. **Capture full context** - Include as much debugging info as possible
4. **Thread safety** - All interfaces are designed to be thread-safe
5. **Clean up in teardown** - Always verify resource cleanup

## Integration Test Files

The following test files use these interfaces:
- `test_parallel_error_handling.py` - Worker crashes and error propagation
- `test_cross_module_errors.py` - Error flow across modules
- `test_config_runtime_changes.py` - Configuration change handling
- `test_cache_file_monitoring.py` - File change detection
- `test_parquet_cli_integration.py` - CLI export integration
- `test_plugin_integration_advanced.py` - Plugin lifecycle management

## Implementation Status

This framework will be fully implemented by the integration coordinator worktree.
Other worktrees should pull the coordinator changes before starting their work.
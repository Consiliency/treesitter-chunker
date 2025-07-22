# Phase 7 Integration Testing - Parallel Worktree Commands

## Prerequisites

Before starting, ensure you're in the main repository with a clean working tree:

```bash
cd /home/jenner/code/treesitter-chunker
git status  # Should show "nothing to commit, working tree clean"

# Verify skeleton interfaces exist
ls -la tests/integration/
cat tests/integration/interfaces.py
```

## Terminal 1: Integration Coordinator (MUST START FIRST)

```bash
# Create the coordinator worktree
git worktree add ../treesitter-chunker-worktrees/integration-coordinator -b feature/integration-coordinator

# Navigate to the worktree
cd ../treesitter-chunker-worktrees/integration-coordinator

# Set up the environment
source .venv/bin/activate
uv pip install -e ".[dev]"
python scripts/fetch_grammars.py
python scripts/build_lib.py

# Verify skeleton files exist
ls -la tests/integration/

# Launch Claude Code with the FULL coordinator implementation prompt
claude "Implement the complete integration test coordinator for Phase 7. You have skeleton files in tests/integration/ that need full implementation.

IMPLEMENT these complete interfaces in tests/integration/interfaces.py:

```python
import time
from typing import Any, Dict, List, Optional

class ErrorPropagationMixin:
    '''Mixin for tracking error propagation across module boundaries.'''
    
    def capture_cross_module_error(self, source_module: str, target_module: str, 
                                   error: Exception) -> Dict[str, Any]:
        '''Capture error with full context.'''
        return {
            'source_module': source_module,
            'target_module': target_module,
            'operation': self.__class__.__name__,
            'original_error': error,
            'error_type': type(error).__name__,
            'error_message': str(error),
            'timestamp': time.time(),
            'context_data': {
                'traceback': self._get_traceback(error),
                'call_stack': self._get_call_stack()
            }
        }
    
    def verify_error_context(self, error: Dict[str, Any], 
                            expected_context: Dict[str, Any]) -> None:
        '''Verify error has expected context.'''
        for key, value in expected_context.items():
            assert key in error, f'Missing context key: {key}'
            if key != 'timestamp':  # Don't check exact timestamp
                assert error[key] == value, f'Context mismatch for {key}: {error[key]} != {value}'
    
    def _get_traceback(self, error: Exception) -> List[str]:
        '''Extract traceback information.'''
        import traceback
        return traceback.format_exception(type(error), error, error.__traceback__)
    
    def _get_call_stack(self) -> List[str]:
        '''Get current call stack.'''
        import inspect
        return [f'{frame.filename}:{frame.lineno} in {frame.function}' 
                for frame in inspect.stack()[2:]]  # Skip this method and caller

class ConfigChangeObserver:
    '''Observer for configuration changes during runtime.'''
    
    def __init__(self):
        self._observers = []
        self._change_log = []
        self._module_config_map = {
            'chunk_types': ['chunker', 'languages'],
            'parser_timeout': ['parser', 'factory'],
            'cache_dir': ['cache', 'streaming'],
            'num_workers': ['parallel'],
            'plugin_dirs': ['plugin_manager'],
        }
        
    def on_config_change(self, config_key: str, old_value: Any, 
                        new_value: Any) -> Dict[str, Any]:
        '''Record config change event.'''
        event = {
            'config_path': config_key,
            'old_value': old_value,
            'new_value': new_value,
            'affected_modules': self.get_affected_modules(config_key),
            'timestamp': time.time()
        }
        self._change_log.append(event)
        self._notify_observers(event)
        return event
    
    def get_affected_modules(self, config_key: str) -> List[str]:
        '''Determine which modules are affected by config change.'''
        # Check direct mappings
        if config_key in self._module_config_map:
            return self._module_config_map[config_key]
        
        # Check nested keys (e.g., 'languages.python.chunk_types')
        for key, modules in self._module_config_map.items():
            if key in config_key:
                return modules
        
        # Default: all modules potentially affected
        return ['parser', 'chunker', 'cache', 'parallel', 'plugin_manager']
    
    def register_observer(self, callback):
        '''Register callback for config changes.'''
        self._observers.append(callback)
    
    def _notify_observers(self, event: Dict[str, Any]):
        '''Notify all registered observers.'''
        for observer in self._observers:
            observer(event)
    
    def get_change_log(self) -> List[Dict[str, Any]]:
        '''Get all recorded changes.'''
        return self._change_log.copy()

class ResourceTracker:
    '''Track resource allocation and cleanup across modules.'''
    
    def __init__(self):
        self._resources = {}
        self._allocation_order = []
        
    def track_resource(self, module: str, resource_type: str, 
                      resource_id: str) -> Dict[str, Any]:
        '''Track a new resource allocation.'''
        resource = {
            'resource_id': resource_id,
            'resource_type': resource_type,
            'owner_module': module,
            'created_at': time.time(),
            'state': 'active',
            'metadata': {}
        }
        self._resources[resource_id] = resource
        self._allocation_order.append(resource_id)
        return resource
    
    def release_resource(self, resource_id: str) -> None:
        '''Mark resource as released.'''
        if resource_id in self._resources:
            self._resources[resource_id]['state'] = 'released'
            self._resources[resource_id]['released_at'] = time.time()
    
    def verify_cleanup(self, module: str) -> List[Dict[str, Any]]:
        '''Verify all resources for module are cleaned up.'''
        leaked = []
        for resource in self._resources.values():
            if resource['owner_module'] == module and resource['state'] == 'active':
                leaked.append(resource)
        return leaked
    
    def get_resource_state(self, resource_id: str) -> Optional[Dict[str, Any]]:
        '''Get current state of a resource.'''
        return self._resources.get(resource_id)
    
    def get_all_resources(self, module: Optional[str] = None, 
                         state: Optional[str] = None) -> List[Dict[str, Any]]:
        '''Get resources filtered by module and/or state.'''
        resources = list(self._resources.values())
        if module:
            resources = [r for r in resources if r['owner_module'] == module]
        if state:
            resources = [r for r in resources if r['state'] == state]
        return resources
```

ALSO IMPLEMENT comprehensive fixtures in tests/integration/fixtures.py including:
- error_tracking_context: Context manager using ErrorPropagationMixin
- config_change_tracker: Fixture using ConfigChangeObserver  
- resource_monitor: Fixture using ResourceTracker
- parallel_test_environment: Setup for parallel tests with proper isolation
- mock_parser_factory: Mock parser with controllable failures
- test_file_generator: Generate test files with specific patterns
- async_test_runner: Runner for async test scenarios

Create tests/integration/README.md documenting:
- How to use each interface
- Expected error/event formats
- Integration test best practices
- Examples of cross-module testing

Ensure all implementations are thread-safe and can handle concurrent access.

After implementing, run:
pytest tests/integration/ -v
git add tests/integration/
git commit -m 'Implement integration test coordinator interfaces'
git push origin feature/integration-coordinator"
```

## Terminal 2: Parallel Error Handling (CRITICAL - Start after Coordinator pushes)

```bash
# Create the worktree
git worktree add ../treesitter-chunker-worktrees/parallel-errors -b feature/test-parallel-errors

# Navigate to the worktree
cd ../treesitter-chunker-worktrees/parallel-errors

# Set up the environment
source .venv/bin/activate
uv pip install -e ".[dev]"
python scripts/fetch_grammars.py
python scripts/build_lib.py

# IMPORTANT: Pull coordinator changes first
git fetch origin
git pull origin feature/integration-coordinator

# Verify interfaces are available
python -c "from tests.integration.interfaces import ErrorPropagationMixin, ResourceTracker; print('✓ Interfaces loaded')"

# Launch Claude Code
claude "Implement test_parallel_error_handling.py for Phase 7 integration testing.

You have access to these interfaces from tests.integration.interfaces:
- ErrorPropagationMixin: For tracking error propagation
- ResourceTracker: For verifying resource cleanup

Use this ERROR CONTEXT FORMAT for all error tracking:
```python
{
    'source_module': str,      # e.g., 'chunker.parallel.ParallelChunker'
    'target_module': str,      # e.g., 'cli.main'
    'operation': str,          # e.g., 'chunk_files_parallel'
    'original_error': Exception,
    'error_type': str,         # e.g., 'WorkerCrashError'
    'error_message': str,
    'timestamp': float,
    'context_data': {
        'traceback': List[str],
        'call_stack': List[str],
        'worker_id': Optional[int],
        'file_being_processed': Optional[str]
    }
}
```

Use this RESOURCE FORMAT for tracking:
```python
{
    'resource_id': str,        # e.g., 'worker_process_12345'
    'resource_type': str,      # 'process', 'file_handle', 'lock', 'memory_buffer'
    'owner_module': str,       # e.g., 'chunker.parallel'
    'created_at': float,
    'state': str,              # 'active', 'released', 'leaked'
    'metadata': {
        'pid': Optional[int],
        'memory_usage': Optional[int],
        'file_path': Optional[str]
    }
}
```

IMPLEMENT these test scenarios:

1. test_worker_process_crash_recovery():
   - Simulate worker crash during file processing
   - Verify error propagates with full context
   - Check partial results are handled
   - Ensure crashed worker resources are cleaned up

2. test_worker_timeout_handling():
   - Create worker that hangs indefinitely
   - Verify timeout triggers correctly
   - Check error context includes timeout details
   - Ensure timed-out worker is terminated

3. test_partial_results_on_failure():
   - Process 10 files, make 3rd and 7th fail
   - Verify successful results are preserved
   - Check failed files have proper error context
   - Ensure overall operation completes

4. test_resource_cleanup_after_errors():
   - Track all resources before operation
   - Trigger various error scenarios
   - Verify all resources are released
   - Check for file handle/lock leaks

5. test_deadlock_prevention():
   - Create scenario prone to deadlock
   - Verify deadlock detection/prevention
   - Check timeout breaks deadlock
   - Ensure clean recovery

6. test_memory_leak_detection():
   - Run operation in loop with errors
   - Track memory usage over iterations
   - Verify no memory accumulation
   - Check process count stays stable

7. test_progress_tracking_with_failures():
   - Start operation with progress tracking
   - Introduce failures at various points
   - Verify progress accurately reflects state
   - Check progress callbacks handle errors

8. test_error_aggregation_strategies():
   - Test different error aggregation modes
   - Verify 'fail_fast' vs 'collect_all' behavior
   - Check error summaries are accurate
   - Ensure context preserved in aggregation

Use fixtures from tests.integration.fixtures for setup.
Mock multiprocessing.Process to control failures.
Test with both ProcessPoolExecutor and custom process management.

Run with: pytest tests/test_parallel_error_handling.py -v"
```

## Terminal 3: Cross-Module Errors (CRITICAL - Start after Coordinator pushes)

```bash
# Create the worktree
git worktree add ../treesitter-chunker-worktrees/cross-module-errors -b feature/test-cross-module-errors

# Navigate to the worktree
cd ../treesitter-chunker-worktrees/cross-module-errors

# Set up the environment
source .venv/bin/activate
uv pip install -e ".[dev]"
python scripts/fetch_grammars.py
python scripts/build_lib.py

# Pull coordinator changes
git fetch origin
git pull origin feature/integration-coordinator

# Verify interfaces
python -c "from tests.integration.interfaces import ErrorPropagationMixin; print('✓ Interfaces loaded')"

# Launch Claude Code
claude "Implement test_cross_module_errors.py for Phase 7 integration testing.

You have ErrorPropagationMixin from tests.integration.interfaces.

CRITICAL: Coordinate error formats with parallel-errors worktree:
```python
ERROR_CONTEXT = {
    'source_module': str,
    'target_module': str,
    'operation': str,
    'original_error': Exception,
    'error_type': str,
    'error_message': str,
    'timestamp': float,
    'context_data': dict
}
```

IMPLEMENT these cross-module error propagation tests:

1. test_parser_error_to_cli():
   - Trigger parser.ParserError
   - Trace through chunker to CLI
   - Verify user sees friendly message
   - Check stack trace is filtered appropriately

2. test_plugin_error_to_export():
   - Create plugin that fails during chunking
   - Verify error reaches export module
   - Check export handles gracefully
   - Ensure partial export is valid

3. test_config_error_to_parallel():
   - Introduce invalid config during parallel operation
   - Verify workers handle config errors
   - Check error aggregation works
   - Ensure no zombie processes

4. test_cascading_failure_scenario():
   - Create error that triggers chain reaction
   - Cache error → Parser error → CLI error
   - Verify each module adds context
   - Check final error is comprehensible

5. test_error_context_preservation():
   - Pass error through 5+ module boundaries
   - Verify no context is lost
   - Check context accumulation
   - Ensure performance isn't degraded

6. test_user_friendly_formatting():
   - Test various error types
   - Verify technical details are hidden
   - Check suggestions are provided
   - Ensure formatting is consistent

7. test_stack_trace_filtering():
   - Generate errors with deep stacks
   - Verify internal frames are filtered
   - Check user code frames are preserved
   - Ensure debugging info available with --debug

8. test_recovery_suggestion_generation():
   - Test each error type
   - Verify appropriate suggestions
   - Check suggestions are actionable
   - Ensure no security info leaked

Mock modules to control error generation.
Test both sync and async error paths.
Verify logging at each boundary.

Run with: pytest tests/test_cross_module_errors.py -v"
```

## Terminal 4: Config Runtime Changes (HIGH - Start after Coordinator pushes)

```bash
# Create the worktree
git worktree add ../treesitter-chunker-worktrees/config-runtime -b feature/test-config-runtime

# Navigate to the worktree
cd ../treesitter-chunker-worktrees/config-runtime

# Set up the environment
source .venv/bin/activate
uv pip install -e ".[dev]"
python scripts/fetch_grammars.py
python scripts/build_lib.py

# Pull coordinator changes
git fetch origin
git pull origin feature/integration-coordinator

# Verify interfaces
python -c "from tests.integration.interfaces import ConfigChangeObserver; print('✓ Interfaces loaded')"

# Launch Claude Code
claude "Implement test_config_runtime_changes.py for Phase 7 integration testing.

You have ConfigChangeObserver from tests.integration.interfaces.

Use this CONFIG CHANGE EVENT FORMAT:
```python
{
    'config_path': str,         # e.g., 'languages.python.chunk_types'
    'old_value': Any,
    'new_value': Any,
    'affected_modules': List[str],
    'timestamp': float
}
```

IMPLEMENT these runtime config change tests:

1. test_config_change_during_parsing():
   - Start parsing large file
   - Change chunk_types mid-parse
   - Verify parser completes with old config
   - Check new parse uses new config

2. test_registry_concurrent_updates():
   - Launch 10 threads reading config
   - Launch 5 threads updating config
   - Verify no corruption or deadlock
   - Check all threads see consistent state

3. test_config_inheritance_changes():
   - Modify parent config during operation
   - Verify child configs update correctly
   - Check no operations fail
   - Ensure inheritance chain intact

4. test_memory_safety_verification():
   - Track all config references
   - Change config values
   - Verify no dangling references
   - Check reference counting correct

5. test_config_rollback_on_error():
   - Make config change that causes error
   - Verify automatic rollback
   - Check system returns to stable state
   - Ensure rollback is logged

6. test_thread_safe_access_patterns():
   - Test various access patterns
   - Read-heavy vs write-heavy loads
   - Verify performance characteristics
   - Check no race conditions

7. test_hot_reload_simulation():
   - Simulate config file change on disk
   - Verify detection and reload
   - Check no active operations fail
   - Ensure smooth transition

8. test_performance_impact_measurement():
   - Baseline performance without changes
   - Measure impact of frequent changes
   - Verify acceptable degradation
   - Check optimization opportunities

Use fixtures from tests.integration.fixtures.
Mock file system for hot reload tests.
Test with real parser operations.

Run with: pytest tests/test_config_runtime_changes.py -v"
```

## Terminal 5: Cache File Monitoring (HIGH - Start after Coordinator pushes)

```bash
# Create the worktree
git worktree add ../treesitter-chunker-worktrees/cache-monitoring -b feature/test-cache-monitoring

# Navigate to the worktree
cd ../treesitter-chunker-worktrees/cache-monitoring

# Set up the environment
source .venv/bin/activate
uv pip install -e ".[dev]"
python scripts/fetch_grammars.py
python scripts/build_lib.py

# Pull coordinator changes
git fetch origin
git pull origin feature/integration-coordinator

# Verify interfaces
python -c "from tests.integration.interfaces import ResourceTracker; print('✓ Interfaces loaded')"

# Launch Claude Code
claude "Implement test_cache_file_monitoring.py for Phase 7 integration testing.

You have ResourceTracker from tests.integration.interfaces.

COORDINATE with parallel-errors worktree on resource tracking:
```python
RESOURCE_FORMAT = {
    'resource_id': str,
    'resource_type': str,    # Use 'cache_entry', 'file_watcher', 'db_connection'
    'owner_module': str,     # 'chunker.cache'
    'created_at': float,
    'state': str,
    'metadata': dict
}
```

IMPLEMENT these cache monitoring tests:

1. test_file_modification_detection():
   - Cache file, then modify it
   - Verify modification detected
   - Check cache invalidation
   - Ensure new content cached

2. test_file_deletion_handling():
   - Cache file, then delete it
   - Verify graceful handling
   - Check cache entry removed
   - Ensure no crashes on access

3. test_file_rename_tracking():
   - Cache file, then rename it
   - Test both tracking and non-tracking modes
   - Verify appropriate behavior
   - Check resource cleanup

4. test_concurrent_file_modifications():
   - Multiple processes modify same file
   - Verify cache consistency
   - Check no corruption
   - Ensure proper locking

5. test_cache_consistency_across_workers():
   - Parallel workers sharing cache
   - Modify files during processing
   - Verify all workers see updates
   - Check synchronization works

6. test_content_vs_timestamp_invalidation():
   - Test timestamp-based invalidation
   - Test content-hash invalidation
   - Compare performance
   - Verify accuracy

7. test_directory_level_changes():
   - Monitor directory for changes
   - Add/remove files
   - Verify batch invalidation
   - Check performance impact

8. test_cache_corruption_recovery():
   - Corrupt cache database
   - Verify detection and recovery
   - Check no data loss
   - Ensure automatic rebuild

Track all cache resources with ResourceTracker.
Test with both SQLite and memory caches.
Simulate real file system events.

Run with: pytest tests/test_cache_file_monitoring.py -v"
```

## Terminal 6: Parquet CLI Integration (MEDIUM - Start after Coordinator pushes)

```bash
# Create the worktree
git worktree add ../treesitter-chunker-worktrees/parquet-cli -b feature/test-parquet-cli

# Navigate to the worktree
cd ../treesitter-chunker-worktrees/parquet-cli

# Set up the environment
source .venv/bin/activate
uv pip install -e ".[dev]"
python scripts/fetch_grammars.py
python scripts/build_lib.py

# Pull coordinator changes
git fetch origin
git pull origin feature/integration-coordinator

# Launch Claude Code
claude "Implement test_parquet_cli_integration.py for Phase 7 integration testing.

Use fixtures from tests.integration.fixtures.

IMPLEMENT these Parquet CLI integration tests:

1. test_parquet_with_include_exclude_filters():
   - Test --include '*.py' --exclude '*test*'
   - Verify correct file selection
   - Check Parquet schema includes file metadata
   - Ensure filters work with patterns

2. test_parquet_with_chunk_type_filtering():
   - Test --chunk-types 'function,class'
   - Verify only specified types exported
   - Check schema adapts to chunk types
   - Ensure consistent column structure

3. test_parquet_with_parallel_processing():
   - Test -j 4 with Parquet export
   - Verify thread-safe writing
   - Check no data corruption
   - Ensure proper ordering

4. test_large_file_streaming_to_parquet():
   - Generate 100MB+ file
   - Test streaming export
   - Monitor memory usage
   - Verify complete export

5. test_schema_evolution_across_languages():
   - Export Python, JS, Rust files
   - Verify schema handles all languages
   - Check nullable columns
   - Ensure backward compatibility

6. test_compression_options():
   - Test snappy, gzip, brotli
   - Compare file sizes
   - Measure performance impact
   - Verify decompression works

7. test_memory_usage_profiling():
   - Export large dataset
   - Track memory throughout
   - Verify streaming limits memory
   - Check for memory leaks

8. test_progress_tracking_accuracy():
   - Export with --progress
   - Verify accurate completion %
   - Check ETA calculations
   - Ensure updates are smooth

Test full CLI integration, not just exporter.
Use CliRunner for command testing.
Verify Parquet files with pyarrow.

Run with: pytest tests/test_parquet_cli_integration.py -v"
```

## Terminal 7: Plugin Enhancement (MEDIUM - Start after Coordinator pushes)

```bash
# Create the worktree
git worktree add ../treesitter-chunker-worktrees/plugin-enhance -b feature/test-plugin-enhance

# Navigate to the worktree
cd ../treesitter-chunker-worktrees/plugin-enhance

# Set up the environment
source .venv/bin/activate
uv pip install -e ".[dev]"
python scripts/fetch_grammars.py
python scripts/build_lib.py

# Pull coordinator changes
git fetch origin
git pull origin feature/integration-coordinator

# Verify interfaces
python -c "from tests.integration.interfaces import ResourceTracker; print('✓ Interfaces loaded')"

# Launch Claude Code
claude "Enhance test_plugin_integration_advanced.py by implementing the 4 skipped tests.

You have ResourceTracker from tests.integration.interfaces for resource tracking.

REMOVE @pytest.mark.skip decorators and IMPLEMENT:

1. test_plugin_conflict_resolution():
   - Create 2 plugins for Python with different versions
   - Verify warning is logged
   - Check higher version wins
   - Ensure clean override
   - Track plugin resources with ResourceTracker

2. test_plugin_hot_reloading():
   - Load plugin from directory
   - Modify plugin file on disk
   - Trigger reload without restart
   - Verify new version active
   - Check old resources cleaned up

3. test_plugin_version_conflicts():
   - Create plugins with dependency conflicts
   - Test version resolution strategies
   - Verify compatible set chosen
   - Check error on unresolvable conflicts

4. test_plugin_config_hot_reload():
   - Load plugin with config file
   - Modify config while plugin active
   - Verify config reloaded
   - Check no operations disrupted
   - Ensure config validation runs

Also ADD these resource-focused tests:

5. test_plugin_resource_contention():
   - Multiple plugins compete for parser
   - Verify fair resource allocation
   - Check no starvation
   - Track with ResourceTracker

6. test_plugin_initialization_order():
   - Plugins with dependencies
   - Verify correct init order
   - Check circular dependency detection
   - Ensure clean failure

Use ResourceTracker to verify:
- All plugin resources tracked
- Proper cleanup on unload
- No resource leaks
- Thread-safe access

Run with: pytest tests/test_plugin_integration_advanced.py::TestPluginLifecycle -v"
```

## Daily Synchronization Commands

Run these in each worktree before starting work:

```bash
# Update from main
git fetch origin
git pull origin main --rebase

# Update from coordinator (for dependent worktrees)
git fetch origin
git pull origin feature/integration-coordinator

# Verify interfaces still work
python -c "from tests.integration import *; print('✓ All interfaces available')"

# Run your tests
pytest tests/test_*.py -v

# Push changes
git add -A
git commit -m "Implement [specific feature]"
git push origin HEAD
```

## Progress Monitoring

From the main repository:

```bash
# Check all worktrees
git worktree list

# Check test count
find ../treesitter-chunker-worktrees -name "test_*.py" -exec grep -c "def test_" {} \; | awk '{sum+=$1} END {print "Total tests: " sum}'

# Check coverage
cd ../treesitter-chunker-worktrees/[worktree-name]
python -m pytest tests/test_*.py --cov=chunker --cov-report=html
```

## Final Integration (Day 5)

```bash
# 1. Ensure all worktrees pushed
cd /home/jenner/code/treesitter-chunker
git fetch --all

# 2. Merge in order
git checkout main
git merge feature/integration-coordinator
git merge feature/test-parallel-errors feature/test-cross-module-errors
git merge feature/test-config-runtime feature/test-cache-monitoring  
git merge feature/test-parquet-cli feature/test-plugin-enhance

# 3. Run full integration suite
python -m pytest tests/integration/ tests/test_*integration*.py -v

# 4. Clean up worktrees
git worktree list | grep -v main | awk '{print $1}' | xargs -I {} git worktree remove {}
```

## Success Checklist

- [ ] Coordinator interfaces implemented first
- [ ] All worktrees pull coordinator changes
- [ ] Error formats consistent between parallel/cross-module
- [ ] Resource tracking consistent across all tests
- [ ] No import errors from integration interfaces
- [ ] All 42 tests implemented and passing
- [ ] Integration coverage reaches 80%

This setup ensures maximum parallelization while maintaining consistency through shared interfaces.
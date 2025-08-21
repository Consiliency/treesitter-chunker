# Performance Core Framework

This module provides the foundational infrastructure for all performance optimization components in Phase 3 of the treesitter-chunker project.

## Overview

The performance core framework offers comprehensive performance monitoring, analysis, and optimization capabilities for the treesitter-chunker system. It provides real-time metrics collection, bottleneck detection, optimization strategies, and budget management.

## Key Features

### 1. Performance Metrics Collection
- **Real-time metrics**: CPU, memory, I/O, and network performance tracking
- **Cross-platform support**: Works with or without psutil for maximum compatibility
- **Historical data**: Store and analyze performance trends over time
- **Contextual metadata**: Rich context information for each metric

### 2. Performance Analysis & Optimization
- **Bottleneck detection**: Automatically identify performance issues
- **Optimization strategies**: Built-in and extensible optimization algorithms
- **Validation**: Verify that optimizations actually improve performance
- **Baseline tracking**: Compare performance against historical baselines

### 3. Budget Management
- **Performance budgets**: Set limits for key performance metrics
- **Violation detection**: Real-time monitoring of budget compliance
- **Alerting**: Configurable alerts when budgets are exceeded
- **Reporting**: Comprehensive budget utilization reports

### 4. Developer Utilities
- **Performance decorators**: Easy function timing and memory profiling
- **Benchmarking tools**: Statistical function performance analysis
- **Context managers**: Measure code block performance
- **Memory optimization**: Tools for efficient memory allocation

## Core Classes

### PerformanceMetric
Represents a single performance measurement with comprehensive metadata:
- Value, unit, timestamp, category, severity
- Contextual information and custom metadata
- Serialization support for persistence

### PerformanceProfile
Complete performance snapshot for a system component:
- Collection of related metrics
- Optimization recommendations
- Baseline comparison data
- Profile timing information

### PerformanceManager
Central orchestration and management:
- System-wide metrics collection
- Performance analysis and bottleneck detection
- Optimization application and validation
- Continuous monitoring capabilities

### MetricsCollector
Real-time performance data collection:
- CPU, memory, I/O metrics
- Configurable collection intervals
- Historical data storage
- Thread-safe operations

### OptimizationEngine
Core optimization algorithms and strategies:
- Built-in optimization strategies (GC, memory, CPU affinity)
- Extensible strategy registration
- Optimization validation
- Performance impact tracking

### PerformanceBudget
Budget management and enforcement:
- Configurable performance limits
- Real-time violation detection
- Utilization reporting
- Budget health monitoring

### PerformanceUtils
Common utilities and helpers:
- Execution timing decorators
- Memory profiling decorators
- Function benchmarking
- Memory allocation optimization

## Usage Examples

### Basic System Monitoring
```python
from chunker.performance.core import PerformanceManager

# Create manager
manager = PerformanceManager()

# Collect system metrics
profile = manager.collect_system_metrics()
print(f"Collected {len(profile.metrics)} metrics")
print(f"Optimization potential: {profile.optimization_potential}%")
```

### Performance Analysis and Optimization
```python
# Analyze performance
analysis = manager.analyze_performance()
print(f"System health: {analysis['overall_health']}")

# Apply optimizations if needed
if analysis['overall_health'] != 'good':
    result = manager.optimize_system()
    print(f"Applied {len(result['optimizations_applied'])} optimizations")
```

### Budget Management
```python
from chunker.performance.core import PerformanceBudget

# Set performance budgets
budget = PerformanceBudget()
budget.set_budget_limit('cpu_percent', 80.0)
budget.set_budget_limit('memory_percent', 85.0)

# Check for violations
violation = budget.check_budget_violation('cpu_percent', 90.0)
if violation:
    print("CPU budget exceeded!")
```

### Function Performance Monitoring
```python
from chunker.performance.core import PerformanceUtils

@PerformanceUtils.measure_execution_time
@PerformanceUtils.profile_memory_usage
def expensive_function():
    # Your code here
    return result

# Get performance statistics
stats = PerformanceUtils.get_function_performance_stats(expensive_function)
print(f"Average execution time: {stats['timing_stats']['avg_ms']:.2f}ms")
```

### Continuous Monitoring
```python
# Start continuous monitoring
manager = PerformanceManager(enable_continuous_monitoring=True)

# Let it run...
time.sleep(60)

# Get performance history
history = manager.get_performance_history()
print(f"Collected {len(history)} performance profiles")

# Stop monitoring
manager.stop_monitoring()
```

### Function Benchmarking
```python
def my_function(n):
    return sum(range(n))

# Benchmark with statistical analysis
results = PerformanceUtils.benchmark_function(my_function, iterations=1000, n=10000)
print(f"Average: {results['timing']['avg_ms']:.3f}ms")
print(f"Min: {results['timing']['min_ms']:.3f}ms")
print(f"Max: {results['timing']['max_ms']:.3f}ms")
```

## Advanced Features

### Custom Optimization Strategies
```python
def custom_optimization(optimization_config):
    # Your optimization logic
    return success_status

# Register custom strategy
engine = OptimizationEngine()
engine.register_optimization_strategy('my_optimization', custom_optimization)
```

### Budget Configuration Export/Import
```python
# Export budget configuration
config = budget.export_budget_config()

# Import to another system
new_budget = PerformanceBudget()
new_budget.import_budget_config(config)
```

### Performance Context Managers
```python
# Measure code block performance
context = PerformanceUtils.create_performance_context_manager("data_processing")
with context:
    # Your code here
    process_large_dataset()
```

## Configuration

### Default Budget Limits
- CPU usage: 80%
- Memory usage: 85%
- Swap usage: 50%
- Load average (1 min): 2.0
- Response time: 1000ms
- Memory growth rate: 100MB/min

### Collection Intervals
- Default metrics collection: 1.0 second
- Continuous monitoring: 10.0 seconds
- History retention: 1000 metrics per type

## Dependencies

### Required
- Python 3.10+
- Standard library modules: `time`, `threading`, `gc`, `tracemalloc`, `resource`

### Optional
- `psutil`: Enhanced system metrics collection (automatically detected)

## Thread Safety

All components are designed to be thread-safe:
- Thread-local storage for metrics
- Proper locking mechanisms
- Daemon threads for background operations
- Graceful shutdown handling

## Error Handling

The framework implements comprehensive error handling:
- Graceful degradation when psutil is unavailable
- Platform-specific feature detection
- Robust exception handling in monitoring loops
- Detailed logging for debugging

## Performance Considerations

The framework is designed to minimize its own performance impact:
- Lazy initialization of expensive resources
- Efficient data structures for metrics storage
- Optional continuous monitoring
- Configurable collection intervals
- Memory-bounded history retention

## Testing

Comprehensive test suite with 95%+ coverage:
- Unit tests for all classes and methods
- Integration tests for end-to-end workflows
- Mock-based testing for system dependencies
- Performance regression tests

## Future Extensions

The core framework is designed to support future Phase 3 components:
- Advanced optimization algorithms
- Machine learning-based performance prediction
- Distributed performance monitoring
- Custom metric types and collectors
- Performance visualization tools

## Example Demo

See `examples/performance_framework_demo.py` for a comprehensive demonstration of all framework capabilities.
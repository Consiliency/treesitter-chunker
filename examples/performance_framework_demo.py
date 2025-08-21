#!/usr/bin/env python3
"""
Performance Framework Demo

Demonstrates the capabilities of the Phase 3 performance core framework
including metrics collection, optimization, and budget management.
"""

import logging
import time

from chunker.performance.core import (
    MetricsCollector,
    OptimizationEngine,
    PerformanceBudget,
    PerformanceManager,
    PerformanceMetric,
    PerformanceUtils,
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def demo_basic_metrics_collection():
    """Demonstrate basic metrics collection."""
    logger.info("=== Basic Metrics Collection Demo ===")

    # Create performance manager
    manager = PerformanceManager(enable_continuous_monitoring=False)

    # Collect system metrics
    profile = manager.collect_system_metrics()

    logger.info(f"Collected {len(profile.metrics)} metrics")
    logger.info(f"Profile time: {profile.profile_time:.3f}s")
    logger.info(f"Optimization potential: {profile.optimization_potential:.1f}%")

    # Show some example metrics
    cpu_metrics = profile.get_metrics_by_category("cpu")
    memory_metrics = profile.get_metrics_by_category("memory")

    logger.info(f"CPU metrics: {len(cpu_metrics)}")
    logger.info(f"Memory metrics: {len(memory_metrics)}")

    # Show critical metrics if any
    critical_metrics = profile.get_critical_metrics()
    if critical_metrics:
        logger.warning(f"Found {len(critical_metrics)} critical metrics:")
        for metric in critical_metrics[:3]:  # Show first 3
            logger.warning(f"  {metric.name}: {metric.value} {metric.unit}")
    else:
        logger.info("No critical metrics found - system healthy")


def demo_performance_analysis():
    """Demonstrate performance analysis and optimization."""
    logger.info("=== Performance Analysis Demo ===")

    manager = PerformanceManager(enable_continuous_monitoring=False)

    # Analyze current performance
    analysis = manager.analyze_performance()

    logger.info(f"Overall health: {analysis['overall_health']}")
    logger.info(f"Optimization potential: {analysis['optimization_potential']:.1f}%")

    if analysis["bottlenecks"]:
        logger.warning("Detected bottlenecks:")
        for bottleneck in analysis["bottlenecks"][:3]:  # Show first 3
            logger.warning(f"  - {bottleneck}")

    # Apply optimizations if needed
    if analysis["overall_health"] != "good":
        logger.info("Applying system optimizations...")
        optimization_result = manager.optimize_system()

        if optimization_result["status"] == "success":
            logger.info(
                f"Applied {len(optimization_result['optimizations_applied'])} optimizations",
            )
            logger.info(f"Improvement: {optimization_result['improvement']:.1f}%")
        else:
            logger.error(f"Optimization failed: {optimization_result['message']}")


def demo_budget_management():
    """Demonstrate performance budget management."""
    logger.info("=== Budget Management Demo ===")

    budget = PerformanceBudget()

    # Set some custom budget limits
    budget.set_budget_limit("cpu_percent", 75.0)
    budget.set_budget_limit("memory_percent", 80.0)
    budget.set_budget_limit("response_time_ms", 500.0)

    # Simulate checking metrics against budget
    test_metrics = [
        ("cpu_percent", 65.0),  # Within budget
        ("memory_percent", 85.0),  # Over budget
        ("response_time_ms", 300.0),  # Within budget
    ]

    for metric_name, value in test_metrics:
        violation = budget.check_budget_violation(metric_name, value)
        if violation:
            logger.warning(f"Budget violation: {metric_name} = {value} exceeds limit")
        else:
            logger.info(f"Budget OK: {metric_name} = {value}")

    # Show budget status
    status = budget.get_budget_status()
    logger.info(f"Budget health: {status['budget_health']}")
    logger.info(f"Metrics in violation: {status['metrics_in_violation']}")

    # Show utilization
    utilization = budget.get_budget_utilization()
    logger.info("Budget utilization:")
    for metric, percent in utilization.items():
        logger.info(f"  {metric}: {percent:.1f}%")


@PerformanceUtils.measure_execution_time
@PerformanceUtils.profile_memory_usage
def expensive_function():
    """A function that simulates expensive work."""
    # Simulate CPU-intensive work
    total = 0
    for i in range(100000):
        total += i**2

    # Simulate memory allocation
    large_list = [str(i) * 100 for i in range(1000)]

    time.sleep(0.1)  # Simulate I/O wait

    return total, len(large_list)


def demo_performance_decorators():
    """Demonstrate performance measurement decorators."""
    logger.info("=== Performance Decorators Demo ===")

    # Run function multiple times
    logger.info("Running expensive function 5 times...")
    results = []
    for i in range(5):
        result = expensive_function()
        results.append(result)

    # Get performance statistics
    stats = PerformanceUtils.get_function_performance_stats(expensive_function)

    logger.info(f"Function: {stats['function_name']}")

    if stats.get("timing_stats"):
        timing = stats["timing_stats"]
        logger.info("Timing stats:")
        logger.info(f"  Executions: {timing['count']}")
        logger.info(f"  Average: {timing['avg_ms']:.2f}ms")
        logger.info(f"  Min: {timing['min_ms']:.2f}ms")
        logger.info(f"  Max: {timing['max_ms']:.2f}ms")

    if stats.get("memory_stats"):
        memory = stats["memory_stats"]
        logger.info("Memory stats:")
        logger.info(f"  Measurements: {memory['count']}")
        logger.info(f"  Average change: {memory['avg_bytes']} bytes")


def demo_benchmarking():
    """Demonstrate function benchmarking."""
    logger.info("=== Function Benchmarking Demo ===")

    def simple_function(n):
        return sum(range(n))

    # Benchmark the function
    logger.info("Benchmarking simple function with 1000 iterations...")
    benchmark_results = PerformanceUtils.benchmark_function(
        simple_function,
        iterations=1000,
        n=1000,
    )

    logger.info(f"Function: {benchmark_results['function_name']}")
    logger.info(f"Iterations: {benchmark_results['iterations']}")
    logger.info(f"Errors: {benchmark_results['errors']}")

    timing = benchmark_results["timing"]
    logger.info("Timing results:")
    logger.info(f"  Average: {timing['avg_ms']:.3f}ms")
    logger.info(f"  Min: {timing['min_ms']:.3f}ms")
    logger.info(f"  Max: {timing['max_ms']:.3f}ms")
    logger.info(f"  Median: {timing['median_ms']:.3f}ms")


def demo_continuous_monitoring():
    """Demonstrate continuous performance monitoring."""
    logger.info("=== Continuous Monitoring Demo ===")

    # Start continuous monitoring
    manager = PerformanceManager(enable_continuous_monitoring=True)

    logger.info("Starting continuous monitoring for 10 seconds...")

    # Let it monitor for a short time
    time.sleep(10)

    # Get performance history
    history = manager.get_performance_history()
    logger.info(f"Collected {len(history)} performance profiles during monitoring")

    # Stop monitoring
    manager.stop_monitoring()

    if history:
        latest_profile = history[-1]
        logger.info(f"Latest profile has {len(latest_profile.metrics)} metrics")

        # Show trend if we have multiple profiles
        if len(history) >= 2:
            first_potential = history[0].optimization_potential
            latest_potential = latest_profile.optimization_potential
            trend = latest_potential - first_potential

            if abs(trend) > 1:
                direction = "increased" if trend > 0 else "decreased"
                logger.info(f"Optimization potential {direction} by {abs(trend):.1f}%")
            else:
                logger.info("Optimization potential remained stable")


def main():
    """Run all performance framework demos."""
    logger.info("Starting Performance Framework Demo")
    logger.info("=" * 50)

    try:
        # Run all demo functions
        demo_basic_metrics_collection()
        print()

        demo_performance_analysis()
        print()

        demo_budget_management()
        print()

        demo_performance_decorators()
        print()

        demo_benchmarking()
        print()

        demo_continuous_monitoring()
        print()

        logger.info("Performance Framework Demo completed successfully!")

    except KeyboardInterrupt:
        logger.info("Demo interrupted by user")
    except Exception as e:
        logger.error(f"Demo failed with error: {e}")
        raise


if __name__ == "__main__":
    main()

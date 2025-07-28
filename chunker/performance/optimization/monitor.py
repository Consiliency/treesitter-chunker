"""Performance monitoring implementation."""

import logging
import statistics
import time
from collections import defaultdict
from dataclasses import dataclass
from threading import RLock

from chunker.interfaces.performance import (
    PerformanceMonitor as PerformanceMonitorInterface,
)

logger = logging.getLogger(__name__)


@dataclass
class TimingInfo:
    """Information about a timed operation."""

    operation_id: str
    operation_name: str
    start_time: float
    end_time: float | None = None
    duration_ms: float | None = None


class PerformanceMonitor(PerformanceMonitorInterface):
    """Monitor and track performance metrics for the chunker.

    This implementation provides:
    - Operation timing with hierarchical tracking
    - Metric recording with statistics
    - Thread-safe operation
    - Automatic metric aggregation
    """

    def __init__(self):
        """Initialize performance monitor."""
        self._operations: dict[str, TimingInfo] = {}
        self._completed_operations: list[TimingInfo] = []
        self._metrics: dict[str, list[float]] = defaultdict(list)
        self._lock = RLock()
        self._operation_counter = 0

        logger.info("Initialized PerformanceMonitor")

    def start_operation(self, operation_name: str) -> str:
        """Start timing an operation.

        Args:
            operation_name: Name of the operation

        Returns:
            Operation ID for tracking
        """
        with self._lock:
            self._operation_counter += 1
            operation_id = (
                f"{operation_name}_{self._operation_counter}_{int(time.time() * 1000)}"
            )

            timing_info = TimingInfo(
                operation_id=operation_id,
                operation_name=operation_name,
                start_time=time.perf_counter(),
            )

            self._operations[operation_id] = timing_info
            logger.debug(f"Started operation: {operation_name} (ID: {operation_id})")

            return operation_id

    def end_operation(self, operation_id: str) -> float:
        """End timing an operation.

        Args:
            operation_id: ID from start_operation

        Returns:
            Duration in milliseconds
        """
        with self._lock:
            if operation_id not in self._operations:
                logger.warning(f"Unknown operation ID: {operation_id}")
                return 0.0

            timing_info = self._operations[operation_id]
            timing_info.end_time = time.perf_counter()
            timing_info.duration_ms = (
                timing_info.end_time - timing_info.start_time
            ) * 1000

            # Move to completed
            self._completed_operations.append(timing_info)
            del self._operations[operation_id]

            # Record as metric
            self.record_metric(
                f"operation.{timing_info.operation_name}",
                timing_info.duration_ms,
            )

            logger.debug(
                f"Ended operation: {timing_info.operation_name} "
                f"(Duration: {timing_info.duration_ms:.2f}ms)",
            )

            return timing_info.duration_ms

    def record_metric(self, metric_name: str, value: float) -> None:
        """Record a performance metric.

        Args:
            metric_name: Name of the metric
            value: Metric value
        """
        with self._lock:
            self._metrics[metric_name].append(value)

            # Keep only last 1000 values per metric to prevent memory issues
            if len(self._metrics[metric_name]) > 1000:
                self._metrics[metric_name] = self._metrics[metric_name][-1000:]

    def get_metrics(self) -> dict[str, dict[str, float]]:
        """Get all recorded metrics with statistics.

        Returns:
            Dictionary of metrics with statistics
        """
        with self._lock:
            result = {}

            for metric_name, values in self._metrics.items():
                if not values:
                    continue

                # Calculate statistics
                result[metric_name] = {
                    "count": len(values),
                    "mean": statistics.mean(values),
                    "median": statistics.median(values),
                    "min": min(values),
                    "max": max(values),
                    "sum": sum(values),
                }

                # Add standard deviation if we have enough values
                if len(values) > 1:
                    result[metric_name]["std_dev"] = statistics.stdev(values)
                else:
                    result[metric_name]["std_dev"] = 0.0

                # Add percentiles for larger datasets
                if len(values) >= 10:
                    sorted_values = sorted(values)
                    result[metric_name]["p50"] = sorted_values[len(sorted_values) // 2]
                    result[metric_name]["p90"] = sorted_values[
                        int(len(sorted_values) * 0.9)
                    ]
                    result[metric_name]["p95"] = sorted_values[
                        int(len(sorted_values) * 0.95)
                    ]
                    result[metric_name]["p99"] = sorted_values[
                        int(len(sorted_values) * 0.99)
                    ]

            # Add operation summaries
            operation_durations = defaultdict(list)
            for op in self._completed_operations:
                if op.duration_ms is not None:
                    operation_durations[op.operation_name].append(op.duration_ms)

            for op_name, durations in operation_durations.items():
                if f"operation.{op_name}" not in result and durations:
                    result[f"operation.{op_name}"] = {
                        "count": len(durations),
                        "mean": statistics.mean(durations),
                        "median": statistics.median(durations),
                        "min": min(durations),
                        "max": max(durations),
                        "sum": sum(durations),
                    }

            return result

    def reset(self) -> None:
        """Reset all metrics."""
        with self._lock:
            self._operations.clear()
            self._completed_operations.clear()
            self._metrics.clear()
            self._operation_counter = 0
            logger.info("Reset all performance metrics")

    # Convenience methods for common operations

    def measure(self, operation_name: str):
        """Context manager for measuring operations.

        Usage:
            with monitor.measure('parse_file'):
                # Do operation
                pass
        """
        return TimingContext(self, operation_name)

    def get_summary(self) -> str:
        """Get a human-readable summary of performance metrics.

        Returns:
            Formatted summary string
        """
        metrics = self.get_metrics()

        if not metrics:
            return "No metrics recorded yet."

        lines = ["Performance Summary:", "-" * 50]

        for metric_name, stats in sorted(metrics.items()):
            lines.append(f"\n{metric_name}:")
            lines.append(f"  Count: {stats['count']:,}")
            lines.append(f"  Mean: {stats['mean']:.2f}")
            lines.append(f"  Median: {stats['median']:.2f}")
            lines.append(f"  Min: {stats['min']:.2f}")
            lines.append(f"  Max: {stats['max']:.2f}")

            if "std_dev" in stats:
                lines.append(f"  Std Dev: {stats['std_dev']:.2f}")

            if "p90" in stats:
                lines.append(f"  P90: {stats['p90']:.2f}")
                lines.append(f"  P95: {stats['p95']:.2f}")
                lines.append(f"  P99: {stats['p99']:.2f}")

        return "\n".join(lines)

    def log_summary(self) -> None:
        """Log performance summary at INFO level."""
        logger.info(self.get_summary())


class TimingContext:
    """Context manager for timing operations."""

    def __init__(self, monitor: PerformanceMonitor, operation_name: str):
        self.monitor = monitor
        self.operation_name = operation_name
        self.operation_id = None

    def __enter__(self):
        self.operation_id = self.monitor.start_operation(self.operation_name)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.operation_id:
            self.monitor.end_operation(self.operation_id)

# chunker/performance/core/performance_framework.py

import functools
import gc
import json
import logging
import os
import resource
import sys
import threading
import time
import tracemalloc
import weakref
from abc import ABC, abstractmethod
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, Tuple, Union

# Conditional imports
try:
    import psutil

    HAS_PSUTIL = True
except ImportError:
    psutil = None
    HAS_PSUTIL = False

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetric:
    """Represents a performance metric with comprehensive data."""

    name: str
    value: float
    unit: str
    timestamp: datetime
    context: dict[str, Any]
    category: str  # 'cpu', 'memory', 'io', 'network', 'custom'
    severity: str  # 'normal', 'warning', 'critical'
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert metric to dictionary for serialization."""
        return {
            "name": self.name,
            "value": self.value,
            "unit": self.unit,
            "timestamp": self.timestamp.isoformat(),
            "context": self.context,
            "category": self.category,
            "severity": self.severity,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PerformanceMetric":
        """Create metric from dictionary."""
        data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        return cls(**data)

    def is_within_threshold(self, threshold: float) -> bool:
        """Check if metric value is within threshold."""
        return self.value <= threshold

    def get_severity_level(self) -> int:
        """Get numeric severity level for comparison."""
        severity_levels = {"normal": 0, "warning": 1, "critical": 2}
        return severity_levels.get(self.severity, 0)


@dataclass
class PerformanceProfile:
    """Comprehensive performance profile for a system component."""

    component_name: str
    metrics: list[PerformanceMetric]
    profile_time: float
    optimization_potential: float
    recommendations: list[str]
    baseline_comparison: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)

    def get_metrics_by_category(self, category: str) -> list[PerformanceMetric]:
        """Get all metrics for a specific category."""
        return [m for m in self.metrics if m.category == category]

    def get_critical_metrics(self) -> list[PerformanceMetric]:
        """Get all critical severity metrics."""
        return [m for m in self.metrics if m.severity == "critical"]

    def get_average_metric_value(self, metric_name: str) -> float | None:
        """Get average value for a specific metric name."""
        values = [m.value for m in self.metrics if m.name == metric_name]
        return sum(values) / len(values) if values else None

    def to_dict(self) -> dict[str, Any]:
        """Convert profile to dictionary for serialization."""
        return {
            "component_name": self.component_name,
            "metrics": [m.to_dict() for m in self.metrics],
            "profile_time": self.profile_time,
            "optimization_potential": self.optimization_potential,
            "recommendations": self.recommendations,
            "baseline_comparison": self.baseline_comparison,
            "created_at": self.created_at.isoformat(),
        }


class PerformanceManager:
    """Central performance orchestration and management."""

    def __init__(self, enable_continuous_monitoring: bool = False):
        """Initialize the performance manager."""
        self.metrics_collector = MetricsCollector()
        self.optimization_engine = OptimizationEngine()
        self.performance_budget = PerformanceBudget()
        self.logger = logging.getLogger(f"{__name__}.PerformanceManager")
        self.enable_continuous_monitoring = enable_continuous_monitoring
        self._monitoring_thread: threading.Thread | None = None
        self._stop_monitoring = threading.Event()
        self._performance_profiles: dict[str, PerformanceProfile] = {}
        self._lock = threading.RLock()

        if enable_continuous_monitoring:
            self.start_monitoring()

    def start_monitoring(self) -> None:
        """Start continuous performance monitoring."""
        if self._monitoring_thread and self._monitoring_thread.is_alive():
            self.logger.warning("Monitoring already running")
            return

        self._stop_monitoring.clear()
        self._monitoring_thread = threading.Thread(
            target=self._monitoring_loop,
            daemon=True,
            name="PerformanceMonitor",
        )
        self._monitoring_thread.start()
        self.logger.info("Started continuous performance monitoring")

    def stop_monitoring(self) -> None:
        """Stop continuous performance monitoring."""
        if self._monitoring_thread:
            self._stop_monitoring.set()
            self._monitoring_thread.join(timeout=5.0)
            self.logger.info("Stopped continuous performance monitoring")

    def _monitoring_loop(self) -> None:
        """Main monitoring loop."""
        while not self._stop_monitoring.is_set():
            try:
                profile = self.collect_system_metrics()
                with self._lock:
                    self._performance_profiles[
                        f"system_{datetime.now().isoformat()}"
                    ] = profile

                # Check for budget violations
                critical_metrics = profile.get_critical_metrics()
                if critical_metrics:
                    self.logger.warning(
                        f"Found {len(critical_metrics)} critical metrics",
                    )

            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {e}")

            self._stop_monitoring.wait(10.0)  # Monitor every 10 seconds

    def collect_system_metrics(self) -> PerformanceProfile:
        """Collect comprehensive system performance metrics."""
        start_time = time.time()
        metrics = []

        try:
            # Collect CPU metrics
            cpu_metrics = self.metrics_collector.collect_cpu_metrics()
            for name, value in cpu_metrics.items():
                severity = (
                    "critical" if value > 90 else "warning" if value > 70 else "normal"
                )
                metrics.append(
                    PerformanceMetric(
                        name=name,
                        value=value,
                        unit="%",
                        timestamp=datetime.now(),
                        context={"source": "system"},
                        category="cpu",
                        severity=severity,
                        metadata={
                            "collection_method": "psutil" if HAS_PSUTIL else "basic",
                        },
                    ),
                )

            # Collect memory metrics
            memory_metrics = self.metrics_collector.collect_memory_metrics()
            for name, value in memory_metrics.items():
                unit = "bytes" if "bytes" in name else "%"
                severity = (
                    "critical"
                    if value > 90 and unit == "%"
                    else "warning" if value > 70 and unit == "%" else "normal"
                )
                metrics.append(
                    PerformanceMetric(
                        name=name,
                        value=value,
                        unit=unit,
                        timestamp=datetime.now(),
                        context={"source": "system"},
                        category="memory",
                        severity=severity,
                        metadata={
                            "collection_method": "psutil" if HAS_PSUTIL else "basic",
                        },
                    ),
                )

            # Collect I/O metrics
            io_metrics = self.metrics_collector.collect_io_metrics()
            for name, value in io_metrics.items():
                metrics.append(
                    PerformanceMetric(
                        name=name,
                        value=value,
                        unit="bytes/s" if "rate" in name else "bytes",
                        timestamp=datetime.now(),
                        context={"source": "system"},
                        category="io",
                        severity="normal",
                        metadata={
                            "collection_method": "psutil" if HAS_PSUTIL else "basic",
                        },
                    ),
                )

        except Exception as e:
            self.logger.error(f"Error collecting system metrics: {e}")

        profile_time = time.time() - start_time

        # Calculate optimization potential
        optimization_potential = self._calculate_optimization_potential(metrics)

        # Generate recommendations
        recommendations = self._generate_recommendations(metrics)

        return PerformanceProfile(
            component_name="system",
            metrics=metrics,
            profile_time=profile_time,
            optimization_potential=optimization_potential,
            recommendations=recommendations,
        )

    def _calculate_optimization_potential(
        self,
        metrics: list[PerformanceMetric],
    ) -> float:
        """Calculate optimization potential based on metrics."""
        if not metrics:
            return 0.0

        critical_count = sum(1 for m in metrics if m.severity == "critical")
        warning_count = sum(1 for m in metrics if m.severity == "warning")
        total_count = len(metrics)

        # Higher potential if more critical/warning metrics
        potential = (critical_count * 0.8 + warning_count * 0.4) / total_count
        return min(potential * 100, 100.0)  # Cap at 100%

    def _generate_recommendations(self, metrics: list[PerformanceMetric]) -> list[str]:
        """Generate optimization recommendations based on metrics."""
        recommendations = []

        critical_metrics = [m for m in metrics if m.severity == "critical"]
        warning_metrics = [m for m in metrics if m.severity == "warning"]

        if critical_metrics:
            cpu_critical = [m for m in critical_metrics if m.category == "cpu"]
            memory_critical = [m for m in critical_metrics if m.category == "memory"]

            if cpu_critical:
                recommendations.append(
                    "High CPU usage detected - consider optimizing algorithms or adding caching",
                )
            if memory_critical:
                recommendations.append(
                    "High memory usage detected - consider memory profiling and optimization",
                )

        if warning_metrics:
            recommendations.append(
                "Monitor system resources closely - some metrics are approaching critical levels",
            )

        if not recommendations:
            recommendations.append("System performance is within normal parameters")

        return recommendations

    def analyze_performance(self) -> dict[str, Any]:
        """Analyze current performance and identify bottlenecks."""
        try:
            current_profile = self.collect_system_metrics()

            analysis = {
                "timestamp": datetime.now().isoformat(),
                "overall_health": "good",
                "bottlenecks": [],
                "recommendations": current_profile.recommendations,
                "optimization_potential": current_profile.optimization_potential,
                "metrics_summary": {
                    "total_metrics": len(current_profile.metrics),
                    "critical_metrics": len(current_profile.get_critical_metrics()),
                    "warning_metrics": len(
                        [m for m in current_profile.metrics if m.severity == "warning"],
                    ),
                },
            }

            # Determine overall health
            critical_count = analysis["metrics_summary"]["critical_metrics"]
            warning_count = analysis["metrics_summary"]["warning_metrics"]

            if critical_count > 0:
                analysis["overall_health"] = "critical"
            elif warning_count > 2:
                analysis["overall_health"] = "warning"

            # Identify bottlenecks
            bottlenecks = self.optimization_engine.detect_bottlenecks(current_profile)
            analysis["bottlenecks"] = bottlenecks

            self.logger.info(
                f"Performance analysis complete: {analysis['overall_health']} health",
            )
            return analysis

        except Exception as e:
            self.logger.error(f"Error analyzing performance: {e}")
            return {
                "timestamp": datetime.now().isoformat(),
                "overall_health": "unknown",
                "error": str(e),
                "bottlenecks": [],
                "recommendations": [
                    "Unable to analyze performance - check system resources",
                ],
            }

    def optimize_system(self) -> dict[str, Any]:
        """Execute system-wide performance optimization."""
        try:
            # Analyze current state
            analysis = self.analyze_performance()

            if analysis["overall_health"] == "good":
                return {
                    "status": "success",
                    "message": "System already optimized",
                    "optimizations_applied": [],
                    "improvement": 0.0,
                }

            # Generate optimizations
            current_profile = self.collect_system_metrics()
            bottlenecks = analysis.get("bottlenecks", [])
            optimizations = self.optimization_engine.generate_optimizations(bottlenecks)

            applied_optimizations = []
            for optimization in optimizations:
                try:
                    if self.optimization_engine.apply_optimization(optimization):
                        applied_optimizations.append(optimization)
                except Exception as e:
                    self.logger.warning(
                        f"Failed to apply optimization {optimization.get('name', 'unknown')}: {e}",
                    )

            # Measure improvement
            time.sleep(1)  # Allow system to settle
            new_profile = self.collect_system_metrics()
            improvement = max(
                0.0,
                current_profile.optimization_potential
                - new_profile.optimization_potential,
            )

            return {
                "status": "success",
                "message": f"Applied {len(applied_optimizations)} optimizations",
                "optimizations_applied": applied_optimizations,
                "improvement": improvement,
                "before_potential": current_profile.optimization_potential,
                "after_potential": new_profile.optimization_potential,
            }

        except Exception as e:
            self.logger.error(f"Error optimizing system: {e}")
            return {
                "status": "error",
                "message": str(e),
                "optimizations_applied": [],
                "improvement": 0.0,
            }

    def validate_optimizations(self) -> dict[str, Any]:
        """Validate that optimizations improved performance."""
        try:
            # Get recent profiles for comparison
            with self._lock:
                recent_profiles = list(self._performance_profiles.values())[
                    -10:
                ]  # Last 10 profiles

            if len(recent_profiles) < 2:
                return {
                    "status": "insufficient_data",
                    "message": "Need at least 2 profiles for validation",
                    "validation_passed": False,
                }

            # Compare latest with previous
            latest_profile = recent_profiles[-1]
            previous_profile = recent_profiles[-2]

            # Check for improvement in optimization potential
            potential_improvement = (
                previous_profile.optimization_potential
                - latest_profile.optimization_potential
            )

            # Check for reduction in critical metrics
            critical_before = len(previous_profile.get_critical_metrics())
            critical_after = len(latest_profile.get_critical_metrics())
            critical_improvement = critical_before - critical_after

            validation_passed = potential_improvement > 0 or critical_improvement > 0

            return {
                "status": "success",
                "validation_passed": validation_passed,
                "potential_improvement": potential_improvement,
                "critical_metrics_reduction": critical_improvement,
                "message": (
                    "Optimizations validated successfully"
                    if validation_passed
                    else "No significant improvement detected"
                ),
                "comparison_details": {
                    "before": {
                        "optimization_potential": previous_profile.optimization_potential,
                        "critical_metrics": critical_before,
                    },
                    "after": {
                        "optimization_potential": latest_profile.optimization_potential,
                        "critical_metrics": critical_after,
                    },
                },
            }

        except Exception as e:
            self.logger.error(f"Error validating optimizations: {e}")
            return {"status": "error", "message": str(e), "validation_passed": False}

    def get_performance_history(self) -> list[PerformanceProfile]:
        """Get performance history."""
        with self._lock:
            return list(self._performance_profiles.values())

    def clear_performance_history(self) -> None:
        """Clear performance history."""
        with self._lock:
            self._performance_profiles.clear()

    def __del__(self) -> None:
        """Cleanup on destruction."""
        try:
            self.stop_monitoring()
            self.metrics_collector.stop_collection()
        except Exception:
            pass  # Ignore cleanup errors


class MetricsCollector:
    """Real-time performance metrics collection and storage."""

    def __init__(self):
        """Initialize the metrics collector."""
        self.metrics_store: dict[str, list[PerformanceMetric]] = {}
        self.collection_thread: threading.Thread | None = None
        self.is_collecting = False
        self._stop_event = threading.Event()
        self._lock = threading.RLock()
        self.logger = logging.getLogger(f"{__name__}.MetricsCollector")

        # Initialize tracemalloc for memory tracking
        try:
            tracemalloc.start()
        except Exception as e:
            self.logger.warning(f"Could not start tracemalloc: {e}")

    def start_collection(self, interval: float = 1.0) -> None:
        """Start continuous metrics collection."""
        if self.is_collecting:
            self.logger.warning("Metrics collection already running")
            return

        self.is_collecting = True
        self._stop_event.clear()
        self.collection_thread = threading.Thread(
            target=self._collection_loop,
            args=(interval,),
            daemon=True,
            name="MetricsCollector",
        )
        self.collection_thread.start()
        self.logger.info(f"Started metrics collection with {interval}s interval")

    def stop_collection(self) -> None:
        """Stop metrics collection."""
        if not self.is_collecting:
            return

        self.is_collecting = False
        self._stop_event.set()

        if self.collection_thread:
            self.collection_thread.join(timeout=5.0)

        self.logger.info("Stopped metrics collection")

    def _collection_loop(self, interval: float) -> None:
        """Main collection loop."""
        while self.is_collecting and not self._stop_event.is_set():
            try:
                # Collect all metric types
                cpu_metrics = self.collect_cpu_metrics()
                memory_metrics = self.collect_memory_metrics()
                io_metrics = self.collect_io_metrics()

                # Store metrics
                timestamp = datetime.now()
                with self._lock:
                    for name, value in {
                        **cpu_metrics,
                        **memory_metrics,
                        **io_metrics,
                    }.items():
                        metric = PerformanceMetric(
                            name=name,
                            value=value,
                            unit=self._get_metric_unit(name),
                            timestamp=timestamp,
                            context={"collection_type": "continuous"},
                            category=self._get_metric_category(name),
                            severity=self._get_metric_severity(name, value),
                            metadata={"interval": interval},
                        )

                        if name not in self.metrics_store:
                            self.metrics_store[name] = []
                        self.metrics_store[name].append(metric)

                        # Keep only last 1000 metrics per type
                        if len(self.metrics_store[name]) > 1000:
                            self.metrics_store[name] = self.metrics_store[name][-1000:]

            except Exception as e:
                self.logger.error(f"Error in collection loop: {e}")

            self._stop_event.wait(interval)

    def _get_metric_unit(self, name: str) -> str:
        """Get appropriate unit for metric."""
        if "percent" in name or "%" in name:
            return "%"
        if "bytes" in name or "memory" in name:
            return "bytes"
        if "rate" in name:
            return "bytes/s"
        if "count" in name:
            return "count"
        return "value"

    def _get_metric_category(self, name: str) -> str:
        """Get category for metric."""
        if "cpu" in name.lower():
            return "cpu"
        if "memory" in name.lower() or "mem" in name.lower():
            return "memory"
        if "io" in name.lower() or "disk" in name.lower():
            return "io"
        if "network" in name.lower() or "net" in name.lower():
            return "network"
        return "custom"

    def _get_metric_severity(self, name: str, value: float) -> str:
        """Determine metric severity based on value."""
        category = self._get_metric_category(name)
        unit = self._get_metric_unit(name)

        if unit == "%":
            if value > 90:
                return "critical"
            if value > 70:
                return "warning"
        elif category == "memory" and unit == "bytes":
            # For absolute memory values, need more context
            if value > 8 * 1024 * 1024 * 1024:  # 8GB
                return "warning"

        return "normal"

    def collect_cpu_metrics(self) -> dict[str, Any]:
        """Collect CPU performance metrics."""
        metrics = {}

        try:
            if HAS_PSUTIL:
                # Get CPU percentage
                cpu_percent = psutil.cpu_percent(interval=0.1)
                metrics["cpu_percent"] = cpu_percent

                # Get per-CPU percentages
                cpu_percents = psutil.cpu_percent(percpu=True, interval=0.1)
                for i, percent in enumerate(cpu_percents):
                    metrics[f"cpu_core_{i}_percent"] = percent

                # Get CPU frequency
                try:
                    cpu_freq = psutil.cpu_freq()
                    if cpu_freq:
                        metrics["cpu_freq_current"] = cpu_freq.current
                        metrics["cpu_freq_min"] = cpu_freq.min
                        metrics["cpu_freq_max"] = cpu_freq.max
                except (AttributeError, OSError):
                    pass

                # Get load average (Unix only)
                try:
                    load_avg = psutil.getloadavg()
                    metrics["load_avg_1min"] = load_avg[0]
                    metrics["load_avg_5min"] = load_avg[1]
                    metrics["load_avg_15min"] = load_avg[2]
                except (AttributeError, OSError):
                    pass

            else:
                # Fallback: basic CPU monitoring using resource module
                try:
                    # Get process CPU time
                    cpu_time = resource.getrusage(resource.RUSAGE_SELF)
                    metrics["process_cpu_time"] = cpu_time.ru_utime + cpu_time.ru_stime

                    # Estimate CPU usage (basic approximation)
                    if hasattr(self, "_last_cpu_time"):
                        time_delta = time.time() - self._last_cpu_check
                        cpu_delta = metrics["process_cpu_time"] - self._last_cpu_time
                        if time_delta > 0:
                            metrics["cpu_percent_estimate"] = (
                                cpu_delta / time_delta
                            ) * 100

                    self._last_cpu_time = metrics["process_cpu_time"]
                    self._last_cpu_check = time.time()

                except Exception:
                    metrics["cpu_percent_estimate"] = 0.0

        except Exception as e:
            self.logger.error(f"Error collecting CPU metrics: {e}")
            metrics["cpu_collection_error"] = str(e)

        return metrics

    def collect_memory_metrics(self) -> dict[str, Any]:
        """Collect memory performance metrics."""
        metrics = {}

        try:
            if HAS_PSUTIL:
                # Virtual memory
                vmem = psutil.virtual_memory()
                metrics["memory_total"] = vmem.total
                metrics["memory_available"] = vmem.available
                metrics["memory_used"] = vmem.used
                metrics["memory_percent"] = vmem.percent
                metrics["memory_free"] = vmem.free

                # Swap memory
                swap = psutil.swap_memory()
                metrics["swap_total"] = swap.total
                metrics["swap_used"] = swap.used
                metrics["swap_free"] = swap.free
                metrics["swap_percent"] = swap.percent

                # Process memory
                process = psutil.Process()
                pmem = process.memory_info()
                metrics["process_memory_rss"] = pmem.rss
                metrics["process_memory_vms"] = pmem.vms
                metrics["process_memory_percent"] = process.memory_percent()

            else:
                # Fallback: basic memory monitoring
                try:
                    mem_usage = resource.getrusage(resource.RUSAGE_SELF)
                    metrics["process_memory_peak"] = (
                        mem_usage.ru_maxrss * 1024
                    )  # Convert to bytes

                    # Use tracemalloc if available
                    if tracemalloc.is_tracing():
                        current, peak = tracemalloc.get_traced_memory()
                        metrics["tracemalloc_current"] = current
                        metrics["tracemalloc_peak"] = peak

                except Exception:
                    pass

        except Exception as e:
            self.logger.error(f"Error collecting memory metrics: {e}")
            metrics["memory_collection_error"] = str(e)

        return metrics

    def collect_io_metrics(self) -> dict[str, Any]:
        """Collect I/O performance metrics."""
        metrics = {}

        try:
            if HAS_PSUTIL:
                # Disk I/O
                disk_io = psutil.disk_io_counters()
                if disk_io:
                    metrics["disk_read_bytes"] = disk_io.read_bytes
                    metrics["disk_write_bytes"] = disk_io.write_bytes
                    metrics["disk_read_count"] = disk_io.read_count
                    metrics["disk_write_count"] = disk_io.write_count
                    metrics["disk_read_time"] = disk_io.read_time
                    metrics["disk_write_time"] = disk_io.write_time

                # Network I/O
                try:
                    net_io = psutil.net_io_counters()
                    if net_io:
                        metrics["network_bytes_sent"] = net_io.bytes_sent
                        metrics["network_bytes_recv"] = net_io.bytes_recv
                        metrics["network_packets_sent"] = net_io.packets_sent
                        metrics["network_packets_recv"] = net_io.packets_recv
                        metrics["network_errin"] = net_io.errin
                        metrics["network_errout"] = net_io.errout
                        metrics["network_dropin"] = net_io.dropin
                        metrics["network_dropout"] = net_io.dropout
                except Exception:
                    pass  # Network stats may not be available

                # Process I/O
                try:
                    process = psutil.Process()
                    pio = process.io_counters()
                    metrics["process_read_bytes"] = pio.read_bytes
                    metrics["process_write_bytes"] = pio.write_bytes
                    metrics["process_read_count"] = pio.read_count
                    metrics["process_write_count"] = pio.write_count
                except Exception:
                    pass  # May not be available on all platforms

            else:
                # Fallback: basic I/O monitoring
                try:
                    io_stats = resource.getrusage(resource.RUSAGE_SELF)
                    metrics["process_block_input"] = io_stats.ru_inblock
                    metrics["process_block_output"] = io_stats.ru_oublock
                    metrics["process_voluntary_switches"] = io_stats.ru_nvcsw
                    metrics["process_involuntary_switches"] = io_stats.ru_nivcsw
                except Exception:
                    pass

        except Exception as e:
            self.logger.error(f"Error collecting I/O metrics: {e}")
            metrics["io_collection_error"] = str(e)

        return metrics

    def get_metric_history(
        self,
        metric_name: str,
        limit: int = 100,
    ) -> list[PerformanceMetric]:
        """Get historical data for a specific metric."""
        with self._lock:
            return self.metrics_store.get(metric_name, [])[-limit:]

    def get_all_metrics(self) -> dict[str, list[PerformanceMetric]]:
        """Get all stored metrics."""
        with self._lock:
            return self.metrics_store.copy()

    def clear_metrics(self) -> None:
        """Clear all stored metrics."""
        with self._lock:
            self.metrics_store.clear()


class OptimizationEngine:
    """Core optimization algorithms and strategies."""

    def __init__(self):
        """Initialize the optimization engine."""
        self.optimization_strategies: dict[str, Callable] = {}
        self.performance_baseline: dict[str, Any] = {}
        self.logger = logging.getLogger(f"{__name__}.OptimizationEngine")
        self._optimization_history: list[dict[str, Any]] = []

        # Register built-in optimization strategies
        self._register_builtin_strategies()

    def _register_builtin_strategies(self) -> None:
        """Register built-in optimization strategies."""
        self.optimization_strategies.update(
            {
                "gc_optimization": self._optimize_garbage_collection,
                "memory_optimization": self._optimize_memory_usage,
                "cpu_affinity": self._optimize_cpu_affinity,
                "thread_optimization": self._optimize_threading,
            },
        )

    def detect_bottlenecks(self, profile: PerformanceProfile) -> list[str]:
        """Detect performance bottlenecks in the system."""
        bottlenecks = []

        try:
            # Analyze critical metrics
            critical_metrics = profile.get_critical_metrics()
            for metric in critical_metrics:
                if metric.category == "cpu" and metric.value > 90:
                    bottlenecks.append(
                        f"High CPU usage: {metric.name} at {metric.value}%",
                    )
                elif (
                    metric.category == "memory"
                    and metric.unit == "%"
                    and metric.value > 90
                ):
                    bottlenecks.append(
                        f"High memory usage: {metric.name} at {metric.value}%",
                    )
                elif metric.category == "io":
                    bottlenecks.append(f"I/O bottleneck: {metric.name}")

            # Look for patterns in metrics
            cpu_metrics = profile.get_metrics_by_category("cpu")
            memory_metrics = profile.get_metrics_by_category("memory")

            # Check for sustained high CPU usage
            high_cpu_count = sum(1 for m in cpu_metrics if m.value > 70)
            if (
                high_cpu_count > len(cpu_metrics) * 0.7
            ):  # More than 70% of CPU metrics are high
                bottlenecks.append("Sustained high CPU usage across multiple cores")

            # Check for memory pressure
            high_memory_count = sum(
                1 for m in memory_metrics if m.unit == "%" and m.value > 70
            )
            if high_memory_count > 0:
                bottlenecks.append("Memory pressure detected")

            # Check optimization potential
            if profile.optimization_potential > 50:
                bottlenecks.append(
                    "High optimization potential - system can be significantly improved",
                )

            self.logger.info(f"Detected {len(bottlenecks)} bottlenecks")

        except Exception as e:
            self.logger.error(f"Error detecting bottlenecks: {e}")
            bottlenecks.append("Error analyzing system - manual inspection recommended")

        return bottlenecks

    def generate_optimizations(self, bottlenecks: list[str]) -> list[dict[str, Any]]:
        """Generate optimization strategies for detected bottlenecks."""
        optimizations = []

        try:
            for bottleneck in bottlenecks:
                bottleneck_lower = bottleneck.lower()

                if "cpu" in bottleneck_lower:
                    optimizations.extend(
                        [
                            {
                                "name": "gc_optimization",
                                "description": "Optimize garbage collection to reduce CPU overhead",
                                "strategy": "gc_optimization",
                                "priority": "high",
                                "estimated_impact": 0.15,
                            },
                            {
                                "name": "cpu_affinity",
                                "description": "Optimize CPU affinity for better performance",
                                "strategy": "cpu_affinity",
                                "priority": "medium",
                                "estimated_impact": 0.10,
                            },
                        ],
                    )

                if "memory" in bottleneck_lower:
                    optimizations.append(
                        {
                            "name": "memory_optimization",
                            "description": "Optimize memory usage patterns",
                            "strategy": "memory_optimization",
                            "priority": "high",
                            "estimated_impact": 0.20,
                        },
                    )

                if (
                    "sustained" in bottleneck_lower
                    or "high optimization potential" in bottleneck_lower
                ):
                    optimizations.append(
                        {
                            "name": "thread_optimization",
                            "description": "Optimize threading and concurrency",
                            "strategy": "thread_optimization",
                            "priority": "medium",
                            "estimated_impact": 0.12,
                        },
                    )

            # Remove duplicates based on strategy name
            seen_strategies = set()
            unique_optimizations = []
            for opt in optimizations:
                if opt["strategy"] not in seen_strategies:
                    unique_optimizations.append(opt)
                    seen_strategies.add(opt["strategy"])

            # Sort by priority and estimated impact
            priority_order = {"high": 3, "medium": 2, "low": 1}
            unique_optimizations.sort(
                key=lambda x: (
                    priority_order.get(x["priority"], 0),
                    x["estimated_impact"],
                ),
                reverse=True,
            )

            self.logger.info(
                f"Generated {len(unique_optimizations)} optimization strategies",
            )

        except Exception as e:
            self.logger.error(f"Error generating optimizations: {e}")

        return unique_optimizations

    def apply_optimization(self, optimization: dict[str, Any]) -> bool:
        """Apply a specific optimization strategy."""
        try:
            strategy_name = optimization.get("strategy")
            if not strategy_name or strategy_name not in self.optimization_strategies:
                self.logger.warning(f"Unknown optimization strategy: {strategy_name}")
                return False

            strategy_func = self.optimization_strategies[strategy_name]

            self.logger.info(
                f"Applying optimization: {optimization.get('name', strategy_name)}",
            )

            # Record optimization attempt
            optimization_record = {
                "timestamp": datetime.now().isoformat(),
                "optimization": optimization,
                "status": "attempting",
            }

            # Apply the optimization
            result = strategy_func(optimization)

            optimization_record["status"] = "success" if result else "failed"
            optimization_record["result"] = result

            self._optimization_history.append(optimization_record)

            if result:
                self.logger.info(f"Successfully applied optimization: {strategy_name}")
            else:
                self.logger.warning(f"Failed to apply optimization: {strategy_name}")

            return result

        except Exception as e:
            self.logger.error(
                f"Error applying optimization {optimization.get('name', 'unknown')}: {e}",
            )
            return False

    def validate_optimization(self, optimization: dict[str, Any]) -> bool:
        """Validate that an optimization improved performance."""
        try:
            # Simple validation - check if optimization was recorded as successful
            strategy_name = optimization.get("strategy")

            # Look for recent successful applications of this strategy
            recent_optimizations = [
                opt
                for opt in self._optimization_history[-10:]  # Last 10 optimizations
                if opt["optimization"].get("strategy") == strategy_name
                and opt["status"] == "success"
            ]

            return len(recent_optimizations) > 0

        except Exception as e:
            self.logger.error(f"Error validating optimization: {e}")
            return False

    def _optimize_garbage_collection(self, optimization: dict[str, Any]) -> bool:
        """Optimize garbage collection settings."""
        try:
            # Get current GC thresholds
            old_thresholds = gc.get_threshold()

            # Adjust GC thresholds for better performance
            # Increase thresholds to reduce GC frequency but allow more objects
            new_thresholds = (
                int(old_thresholds[0] * 1.5),  # Generation 0
                int(old_thresholds[1] * 1.3),  # Generation 1
                int(old_thresholds[2] * 1.2),  # Generation 2
            )

            gc.set_threshold(*new_thresholds)

            # Force a collection to clean up
            collected = gc.collect()

            self.logger.info(
                f"GC optimization: collected {collected} objects, new thresholds: {new_thresholds}",
            )
            return True

        except Exception as e:
            self.logger.error(f"Error optimizing garbage collection: {e}")
            return False

    def _optimize_memory_usage(self, optimization: dict[str, Any]) -> bool:
        """Optimize memory usage patterns."""
        try:
            # Force garbage collection
            collected = gc.collect()

            # Enable GC debugging for better tracking
            if not gc.get_debug():
                gc.set_debug(gc.DEBUG_STATS)

            self.logger.info(
                f"Memory optimization: collected {collected} objects, enabled GC debugging",
            )
            return True

        except Exception as e:
            self.logger.error(f"Error optimizing memory usage: {e}")
            return False

    def _optimize_cpu_affinity(self, optimization: dict[str, Any]) -> bool:
        """Optimize CPU affinity for performance."""
        try:
            if not HAS_PSUTIL:
                self.logger.info(
                    "CPU affinity optimization skipped - psutil not available",
                )
                return False

            process = psutil.Process()

            # Get current CPU affinity
            try:
                current_affinity = process.cpu_affinity()
                cpu_count = psutil.cpu_count()

                # If process is using all CPUs, try to optimize
                if len(current_affinity) == cpu_count and cpu_count > 2:
                    # Use fewer cores for better cache locality
                    new_affinity = list(range(min(4, cpu_count)))  # Use up to 4 cores
                    process.cpu_affinity(new_affinity)

                    self.logger.info(
                        f"CPU affinity optimization: changed from {current_affinity} to {new_affinity}",
                    )
                    return True
                self.logger.info(
                    "CPU affinity already optimized or insufficient cores",
                )
                return True

            except (AttributeError, OSError) as e:
                self.logger.info(f"CPU affinity optimization not supported: {e}")
                return False

        except Exception as e:
            self.logger.error(f"Error optimizing CPU affinity: {e}")
            return False

    def _optimize_threading(self, optimization: dict[str, Any]) -> bool:
        """Optimize threading and concurrency."""
        try:
            # Set thread stack size for better memory usage
            try:
                current_stack_size = threading.stack_size()
                if current_stack_size == 0:  # Default stack size
                    # Set smaller stack size to save memory
                    new_stack_size = 512 * 1024  # 512KB
                    threading.stack_size(new_stack_size)
                    self.logger.info(
                        f"Thread optimization: set stack size to {new_stack_size} bytes",
                    )
                    return True
                self.logger.info(
                    f"Thread stack size already set: {current_stack_size}",
                )
                return True

            except Exception as e:
                self.logger.info(f"Thread stack size optimization not supported: {e}")
                return False

        except Exception as e:
            self.logger.error(f"Error optimizing threading: {e}")
            return False

    def register_optimization_strategy(
        self,
        name: str,
        strategy_func: Callable,
    ) -> None:
        """Register a custom optimization strategy."""
        self.optimization_strategies[name] = strategy_func
        self.logger.info(f"Registered optimization strategy: {name}")

    def get_optimization_history(self) -> list[dict[str, Any]]:
        """Get history of applied optimizations."""
        return self._optimization_history.copy()


class PerformanceBudget:
    """Performance budget management and enforcement."""

    def __init__(self):
        """Initialize the performance budget."""
        self.budget_limits: dict[str, float] = {}
        self.current_usage: dict[str, float] = {}
        self.violations: list[dict[str, Any]] = []
        self.logger = logging.getLogger(f"{__name__}.PerformanceBudget")
        self._lock = threading.RLock()

        # Set default budget limits
        self._set_default_limits()

    def _set_default_limits(self) -> None:
        """Set sensible default budget limits."""
        self.budget_limits.update(
            {
                "cpu_percent": 80.0,
                "memory_percent": 85.0,
                "swap_percent": 50.0,
                "load_avg_1min": 2.0,
                "response_time_ms": 1000.0,
                "memory_growth_rate_mb_per_min": 100.0,
            },
        )

    def set_budget_limit(self, metric: str, limit: float) -> None:
        """Set a budget limit for a specific metric."""
        with self._lock:
            old_limit = self.budget_limits.get(metric)
            self.budget_limits[metric] = limit

            self.logger.info(
                f"Budget limit for '{metric}' changed from {old_limit} to {limit}",
            )

    def check_budget_violation(self, metric: str, value: float) -> bool:
        """Check if a metric value violates budget limits."""
        with self._lock:
            limit = self.budget_limits.get(metric)
            if limit is None:
                return False  # No limit set for this metric

            self.current_usage[metric] = value

            if value > limit:
                violation = {
                    "timestamp": datetime.now().isoformat(),
                    "metric": metric,
                    "value": value,
                    "limit": limit,
                    "violation_amount": value - limit,
                    "violation_percent": ((value - limit) / limit) * 100,
                }

                self.violations.append(violation)

                # Keep only last 100 violations
                if len(self.violations) > 100:
                    self.violations = self.violations[-100:]

                self.logger.warning(
                    f"Budget violation: {metric} = {value} exceeds limit of {limit}",
                )
                return True

            return False

    def get_budget_status(self) -> dict[str, Any]:
        """Get current budget status and violations."""
        with self._lock:
            total_metrics = len(self.budget_limits)
            violated_metrics = len(
                set(v["metric"] for v in self.violations[-10:]),
            )  # Last 10 violations

            status = {
                "timestamp": datetime.now().isoformat(),
                "total_metrics_monitored": total_metrics,
                "metrics_in_violation": violated_metrics,
                "budget_health": (
                    "good"
                    if violated_metrics == 0
                    else "warning" if violated_metrics <= 2 else "critical"
                ),
                "current_usage": self.current_usage.copy(),
                "budget_limits": self.budget_limits.copy(),
                "recent_violations": self.violations[-10:],  # Last 10 violations
                "violation_summary": {},
            }

            # Summarize violations by metric
            for violation in self.violations[-50:]:  # Last 50 violations
                metric = violation["metric"]
                if metric not in status["violation_summary"]:
                    status["violation_summary"][metric] = {
                        "count": 0,
                        "max_violation": 0,
                        "avg_violation": 0,
                        "total_violation": 0,
                    }

                summary = status["violation_summary"][metric]
                summary["count"] += 1
                summary["max_violation"] = max(
                    summary["max_violation"],
                    violation["violation_amount"],
                )
                summary["total_violation"] += violation["violation_amount"]

            # Calculate averages
            for metric_summary in status["violation_summary"].values():
                if metric_summary["count"] > 0:
                    metric_summary["avg_violation"] = (
                        metric_summary["total_violation"] / metric_summary["count"]
                    )

            return status

    def get_budget_utilization(self) -> dict[str, float]:
        """Get current budget utilization as percentage."""
        with self._lock:
            utilization = {}
            for metric, limit in self.budget_limits.items():
                current = self.current_usage.get(metric, 0.0)
                utilization[metric] = (current / limit) * 100 if limit > 0 else 0.0

            return utilization

    def clear_violations(self) -> None:
        """Clear violation history."""
        with self._lock:
            self.violations.clear()
            self.logger.info("Cleared budget violation history")

    def export_budget_config(self) -> dict[str, Any]:
        """Export budget configuration for persistence."""
        with self._lock:
            return {
                "budget_limits": self.budget_limits.copy(),
                "exported_at": datetime.now().isoformat(),
            }

    def import_budget_config(self, config: dict[str, Any]) -> None:
        """Import budget configuration."""
        with self._lock:
            if "budget_limits" in config:
                self.budget_limits.update(config["budget_limits"])
                self.logger.info(
                    f"Imported budget configuration with {len(config['budget_limits'])} limits",
                )


class PerformanceUtils:
    """Common performance utilities and helpers."""

    @staticmethod
    def measure_execution_time(func: Callable) -> Callable:
        """Decorator to measure function execution time."""

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            start_time = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                end_time = time.perf_counter()
                execution_time = (
                    end_time - start_time
                ) * 1000  # Convert to milliseconds

                logger.debug(f"{func.__name__} executed in {execution_time:.2f}ms")

                # Store timing in wrapper attribute for inspection
                if not hasattr(wrapper, "_performance_timings"):
                    wrapper._performance_timings = []
                wrapper._performance_timings.append(execution_time)

                # Keep only last 100 timings
                if len(wrapper._performance_timings) > 100:
                    wrapper._performance_timings = wrapper._performance_timings[-100:]

        return wrapper

    @staticmethod
    def profile_memory_usage(func: Callable) -> Callable:
        """Decorator to profile memory usage of functions."""

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Start memory tracking
            gc.collect()  # Clean up before measurement

            if tracemalloc.is_tracing():
                snapshot_before = tracemalloc.take_snapshot()

            try:
                result = func(*args, **kwargs)
                return result
            finally:
                if tracemalloc.is_tracing():
                    snapshot_after = tracemalloc.take_snapshot()

                    # Calculate memory difference
                    top_stats = snapshot_after.compare_to(snapshot_before, "lineno")
                    total_diff = sum(stat.size_diff for stat in top_stats)

                    logger.debug(f"{func.__name__} memory change: {total_diff} bytes")

                    # Store memory usage in wrapper attribute
                    if not hasattr(wrapper, "_memory_usage"):
                        wrapper._memory_usage = []
                    wrapper._memory_usage.append(total_diff)

                    # Keep only last 100 measurements
                    if len(wrapper._memory_usage) > 100:
                        wrapper._memory_usage = wrapper._memory_usage[-100:]

        return wrapper

    @staticmethod
    def optimize_memory_allocation(size: int) -> int:
        """Optimize memory allocation size."""
        # Round up to nearest power of 2 for better memory alignment
        if size <= 0:
            return 1

        # For small sizes, use exact size
        if size <= 1024:
            return size

        # For larger sizes, round to next power of 2
        power = 1
        while power < size:
            power <<= 1

        return power

    @staticmethod
    def cpu_affinity_optimization() -> None:
        """Optimize CPU affinity for performance."""
        if not HAS_PSUTIL:
            logger.info("CPU affinity optimization skipped - psutil not available")
            return

        try:
            process = psutil.Process()
            cpu_count = psutil.cpu_count()
            current_affinity = process.cpu_affinity()

            # If using all CPUs and we have many cores, optimize for cache locality
            if len(current_affinity) == cpu_count and cpu_count > 4:
                # Use half the cores for better cache performance
                optimal_cores = list(range(cpu_count // 2))
                process.cpu_affinity(optimal_cores)
                logger.info(
                    f"Optimized CPU affinity: {current_affinity} -> {optimal_cores}",
                )

        except Exception as e:
            logger.debug(f"CPU affinity optimization failed: {e}")

    @staticmethod
    def get_function_performance_stats(func: Callable) -> dict[str, Any]:
        """Get performance statistics for a decorated function."""
        stats = {
            "function_name": getattr(func, "__name__", "unknown"),
            "timing_stats": {},
            "memory_stats": {},
        }

        # Get timing statistics
        if hasattr(func, "_performance_timings"):
            timings = func._performance_timings
            if timings:
                stats["timing_stats"] = {
                    "count": len(timings),
                    "min_ms": min(timings),
                    "max_ms": max(timings),
                    "avg_ms": sum(timings) / len(timings),
                    "total_ms": sum(timings),
                }

        # Get memory statistics
        if hasattr(func, "_memory_usage"):
            memory_usage = func._memory_usage
            if memory_usage:
                stats["memory_stats"] = {
                    "count": len(memory_usage),
                    "min_bytes": min(memory_usage),
                    "max_bytes": max(memory_usage),
                    "avg_bytes": sum(memory_usage) / len(memory_usage),
                    "total_bytes": sum(memory_usage),
                }

        return stats

    @staticmethod
    def clear_function_performance_data(func: Callable) -> None:
        """Clear performance data for a decorated function."""
        if hasattr(func, "_performance_timings"):
            func._performance_timings.clear()
        if hasattr(func, "_memory_usage"):
            func._memory_usage.clear()

    @staticmethod
    def create_performance_context_manager(name: str):
        """Create a context manager for measuring performance of code blocks."""

        class PerformanceContext:
            def __init__(self, context_name: str):
                self.name = context_name
                self.start_time = 0.0
                self.start_memory = 0

            def __enter__(self):
                self.start_time = time.perf_counter()
                if tracemalloc.is_tracing():
                    self.start_memory = tracemalloc.get_traced_memory()[0]
                return self

            def __exit__(self, exc_type, exc_val, exc_tb):
                end_time = time.perf_counter()
                execution_time = (end_time - self.start_time) * 1000

                memory_diff = 0
                if tracemalloc.is_tracing():
                    end_memory = tracemalloc.get_traced_memory()[0]
                    memory_diff = end_memory - self.start_memory

                logger.debug(
                    f"{self.name} block executed in {execution_time:.2f}ms, memory change: {memory_diff} bytes",
                )

        return PerformanceContext(name)

    @staticmethod
    def benchmark_function(
        func: Callable,
        iterations: int = 1000,
        *args: Any,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Benchmark a function with multiple iterations."""
        timings = []
        memory_usage = []
        errors = 0

        # Warm up
        try:
            func(*args, **kwargs)
        except Exception:
            pass

        for _ in range(iterations):
            gc.collect()

            if tracemalloc.is_tracing():
                mem_before = tracemalloc.get_traced_memory()[0]

            start_time = time.perf_counter()

            try:
                func(*args, **kwargs)
                end_time = time.perf_counter()
                timings.append((end_time - start_time) * 1000)

                if tracemalloc.is_tracing():
                    mem_after = tracemalloc.get_traced_memory()[0]
                    memory_usage.append(mem_after - mem_before)

            except Exception:
                errors += 1

        if not timings:
            return {"error": "No successful executions"}

        return {
            "function_name": func.__name__,
            "iterations": len(timings),
            "errors": errors,
            "timing": {
                "min_ms": min(timings),
                "max_ms": max(timings),
                "avg_ms": sum(timings) / len(timings),
                "median_ms": sorted(timings)[len(timings) // 2],
                "total_ms": sum(timings),
            },
            "memory": (
                {
                    "measurements": len(memory_usage),
                    "min_bytes": min(memory_usage) if memory_usage else 0,
                    "max_bytes": max(memory_usage) if memory_usage else 0,
                    "avg_bytes": (
                        sum(memory_usage) / len(memory_usage) if memory_usage else 0
                    ),
                    "total_bytes": sum(memory_usage) if memory_usage else 0,
                }
                if memory_usage
                else None
            ),
        }

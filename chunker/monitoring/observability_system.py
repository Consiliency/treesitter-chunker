# chunker/monitoring/observability_system.py

"""
Comprehensive monitoring and observability system for the treesitter-chunker.

This module provides real-time metrics collection, distributed tracing support,
log aggregation, custom dashboards, and alert integration.
"""

import functools
import gc
import json
import logging
import os
import queue
import resource
import sys
import threading
import time
import traceback
import tracemalloc
import uuid
import weakref
from abc import ABC, abstractmethod
from collections import defaultdict, deque
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

# Conditional imports
try:
    import psutil

    HAS_PSUTIL = True
except ImportError:
    psutil = None
    HAS_PSUTIL = False

try:
    import prometheus_client

    HAS_PROMETHEUS = True
except ImportError:
    prometheus_client = None
    HAS_PROMETHEUS = False

try:
    import structlog

    HAS_STRUCTLOG = True
except ImportError:
    structlog = None
    HAS_STRUCTLOG = False

# Import from performance framework
try:
    from ..performance.core.performance_framework import (
        PerformanceManager,
        PerformanceMetric,
    )

    HAS_PERFORMANCE_FRAMEWORK = True
except ImportError:
    HAS_PERFORMANCE_FRAMEWORK = False

logger = logging.getLogger(__name__)


@dataclass
class TraceSpan:
    """Represents a distributed trace span."""

    span_id: str
    trace_id: str
    parent_span_id: str | None
    operation_name: str
    start_time: datetime
    end_time: datetime | None = None
    duration_ms: float | None = None
    tags: dict[str, Any] = field(default_factory=dict)
    logs: list[dict[str, Any]] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)
    baggage: dict[str, str] = field(default_factory=dict)
    finished: bool = False

    def finish(self, end_time: datetime | None = None) -> None:
        """Finish the span."""
        if self.finished:
            return

        self.end_time = end_time or datetime.now()
        if self.start_time:
            delta = self.end_time - self.start_time
            self.duration_ms = delta.total_seconds() * 1000
        self.finished = True

    def set_tag(self, key: str, value: Any) -> None:
        """Set a tag on the span."""
        self.tags[key] = value

    def log(self, message: str, level: str = "info", **kwargs) -> None:
        """Add a log entry to the span."""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "level": level,
            "message": message,
            **kwargs,
        }
        self.logs.append(log_entry)

    def set_baggage(self, key: str, value: str) -> None:
        """Set baggage item (propagated to child spans)."""
        self.baggage[key] = value

    def to_dict(self) -> dict[str, Any]:
        """Convert span to dictionary for serialization."""
        return {
            "span_id": self.span_id,
            "trace_id": self.trace_id,
            "parent_span_id": self.parent_span_id,
            "operation_name": self.operation_name,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_ms": self.duration_ms,
            "tags": self.tags,
            "logs": self.logs,
            "context": self.context,
            "baggage": self.baggage,
            "finished": self.finished,
        }


@dataclass
class MetricDataPoint:
    """Represents a single metric data point."""

    metric_name: str
    value: float
    timestamp: datetime
    labels: dict[str, str] = field(default_factory=dict)
    metric_type: str = "gauge"  # gauge, counter, histogram, summary
    unit: str = ""
    help_text: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "metric_name": self.metric_name,
            "value": self.value,
            "timestamp": self.timestamp.isoformat(),
            "labels": self.labels,
            "metric_type": self.metric_type,
            "unit": self.unit,
            "help_text": self.help_text,
        }


@dataclass
class LogEntry:
    """Structured log entry."""

    timestamp: datetime
    level: str
    message: str
    logger_name: str
    module: str
    function: str
    line_number: int
    trace_id: str | None = None
    span_id: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)
    exception: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "level": self.level,
            "message": self.message,
            "logger_name": self.logger_name,
            "module": self.module,
            "function": self.function,
            "line_number": self.line_number,
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "extra": self.extra,
            "exception": self.exception,
        }


@dataclass
class Alert:
    """Represents a monitoring alert."""

    alert_id: str
    metric_name: str
    condition: str
    threshold: float
    current_value: float
    severity: str  # info, warning, critical
    title: str
    description: str
    timestamp: datetime
    resolved: bool = False
    resolved_at: datetime | None = None

    def resolve(self) -> None:
        """Mark alert as resolved."""
        self.resolved = True
        self.resolved_at = datetime.now()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "alert_id": self.alert_id,
            "metric_name": self.metric_name,
            "condition": self.condition,
            "threshold": self.threshold,
            "current_value": self.current_value,
            "severity": self.severity,
            "title": self.title,
            "description": self.description,
            "timestamp": self.timestamp.isoformat(),
            "resolved": self.resolved,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
        }


class MetricsCollector:
    """Advanced metrics collection with system, application, and business metrics."""

    def __init__(self, collection_interval: float = 5.0):
        """Initialize the metrics collector."""
        self.collection_interval = collection_interval
        self.metrics_store: dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self.custom_metrics: dict[str, Callable] = {}
        self.is_collecting = False
        self.collection_thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._lock = threading.RLock()
        self.logger = logging.getLogger(f"{__name__}.MetricsCollector")

        # Prometheus integration if available
        self.prometheus_metrics: dict[str, Any] = {}
        if HAS_PROMETHEUS:
            self._setup_prometheus_metrics()

        # Performance framework integration
        self.performance_manager: PerformanceManager | None = None
        if HAS_PERFORMANCE_FRAMEWORK:
            try:
                self.performance_manager = PerformanceManager(
                    enable_continuous_monitoring=False,
                )
            except Exception as e:
                self.logger.warning(f"Failed to initialize performance manager: {e}")

    def _setup_prometheus_metrics(self) -> None:
        """Setup Prometheus metrics."""
        if not HAS_PROMETHEUS:
            return

        try:
            # System metrics
            self.prometheus_metrics.update(
                {
                    "cpu_usage": prometheus_client.Gauge(
                        "chunker_cpu_usage_percent",
                        "CPU usage percentage",
                    ),
                    "memory_usage": prometheus_client.Gauge(
                        "chunker_memory_usage_bytes",
                        "Memory usage in bytes",
                    ),
                    "memory_percent": prometheus_client.Gauge(
                        "chunker_memory_usage_percent",
                        "Memory usage percentage",
                    ),
                    "disk_io_read": prometheus_client.Counter(
                        "chunker_disk_read_bytes_total",
                        "Total disk read bytes",
                    ),
                    "disk_io_write": prometheus_client.Counter(
                        "chunker_disk_write_bytes_total",
                        "Total disk write bytes",
                    ),
                    "network_io_sent": prometheus_client.Counter(
                        "chunker_network_sent_bytes_total",
                        "Total network bytes sent",
                    ),
                    "network_io_recv": prometheus_client.Counter(
                        "chunker_network_recv_bytes_total",
                        "Total network bytes received",
                    ),
                    # Application metrics
                    "chunks_processed": prometheus_client.Counter(
                        "chunker_chunks_processed_total",
                        "Total chunks processed",
                    ),
                    "chunk_processing_time": prometheus_client.Histogram(
                        "chunker_chunk_processing_seconds",
                        "Chunk processing time in seconds",
                    ),
                    "active_chunking_operations": prometheus_client.Gauge(
                        "chunker_active_operations",
                        "Number of active chunking operations",
                    ),
                    "error_count": prometheus_client.Counter(
                        "chunker_errors_total",
                        "Total errors",
                        ["error_type"],
                    ),
                    "cache_hits": prometheus_client.Counter(
                        "chunker_cache_hits_total",
                        "Total cache hits",
                    ),
                    "cache_misses": prometheus_client.Counter(
                        "chunker_cache_misses_total",
                        "Total cache misses",
                    ),
                    # Business metrics
                    "files_processed": prometheus_client.Counter(
                        "chunker_files_processed_total",
                        "Total files processed",
                        ["language"],
                    ),
                    "success_rate": prometheus_client.Gauge(
                        "chunker_success_rate",
                        "Processing success rate",
                    ),
                    "average_chunk_size": prometheus_client.Gauge(
                        "chunker_avg_chunk_size_bytes",
                        "Average chunk size in bytes",
                    ),
                    "throughput": prometheus_client.Gauge(
                        "chunker_throughput_chunks_per_second",
                        "Processing throughput",
                    ),
                },
            )
        except Exception as e:
            self.logger.error(f"Failed to setup Prometheus metrics: {e}")

    def start_collection(self) -> None:
        """Start continuous metrics collection."""
        if self.is_collecting:
            self.logger.warning("Metrics collection already running")
            return

        self.is_collecting = True
        self._stop_event.clear()
        self.collection_thread = threading.Thread(
            target=self._collection_loop,
            daemon=True,
            name="MetricsCollector",
        )
        self.collection_thread.start()
        self.logger.info(
            f"Started metrics collection with {self.collection_interval}s interval",
        )

    def stop_collection(self) -> None:
        """Stop metrics collection."""
        if not self.is_collecting:
            return

        self.is_collecting = False
        self._stop_event.set()

        if self.collection_thread:
            self.collection_thread.join(timeout=5.0)

        self.logger.info("Stopped metrics collection")

    def _collection_loop(self) -> None:
        """Main collection loop."""
        while self.is_collecting and not self._stop_event.is_set():
            try:
                # Collect all metric types
                self._collect_system_metrics()
                self._collect_application_metrics()
                self._collect_business_metrics()
                self._collect_custom_metrics()

            except Exception as e:
                self.logger.error(f"Error in metrics collection loop: {e}")

            self._stop_event.wait(self.collection_interval)

    def _collect_system_metrics(self) -> None:
        """Collect system performance metrics."""
        timestamp = datetime.now()

        try:
            if HAS_PSUTIL:
                # CPU metrics
                cpu_percent = psutil.cpu_percent(interval=0.1)
                self._store_metric("cpu_usage_percent", cpu_percent, timestamp)

                # Memory metrics
                memory = psutil.virtual_memory()
                self._store_metric("memory_usage_bytes", memory.used, timestamp)
                self._store_metric("memory_usage_percent", memory.percent, timestamp)
                self._store_metric(
                    "memory_available_bytes",
                    memory.available,
                    timestamp,
                )

                # Disk I/O
                disk_io = psutil.disk_io_counters()
                if disk_io:
                    self._store_metric("disk_read_bytes", disk_io.read_bytes, timestamp)
                    self._store_metric(
                        "disk_write_bytes",
                        disk_io.write_bytes,
                        timestamp,
                    )
                    self._store_metric("disk_read_count", disk_io.read_count, timestamp)
                    self._store_metric(
                        "disk_write_count",
                        disk_io.write_count,
                        timestamp,
                    )

                # Network I/O
                try:
                    net_io = psutil.net_io_counters()
                    if net_io:
                        self._store_metric(
                            "network_bytes_sent",
                            net_io.bytes_sent,
                            timestamp,
                        )
                        self._store_metric(
                            "network_bytes_recv",
                            net_io.bytes_recv,
                            timestamp,
                        )
                        self._store_metric(
                            "network_packets_sent",
                            net_io.packets_sent,
                            timestamp,
                        )
                        self._store_metric(
                            "network_packets_recv",
                            net_io.packets_recv,
                            timestamp,
                        )
                except Exception:
                    pass  # Network stats may not be available

                # Update Prometheus metrics
                if HAS_PROMETHEUS and self.prometheus_metrics:
                    self.prometheus_metrics.get("cpu_usage", lambda: None).set(
                        cpu_percent,
                    )
                    self.prometheus_metrics.get("memory_usage", lambda: None).set(
                        memory.used,
                    )
                    self.prometheus_metrics.get("memory_percent", lambda: None).set(
                        memory.percent,
                    )

                    if disk_io:
                        # Prometheus counters need to be incremented, not set
                        current_read = getattr(self, "_last_disk_read", 0)
                        current_write = getattr(self, "_last_disk_write", 0)
                        if current_read < disk_io.read_bytes:
                            self.prometheus_metrics.get(
                                "disk_io_read",
                                lambda: None,
                            ).inc(disk_io.read_bytes - current_read)
                        if current_write < disk_io.write_bytes:
                            self.prometheus_metrics.get(
                                "disk_io_write",
                                lambda: None,
                            ).inc(disk_io.write_bytes - current_write)
                        self._last_disk_read = disk_io.read_bytes
                        self._last_disk_write = disk_io.write_bytes

                    if net_io:
                        current_sent = getattr(self, "_last_net_sent", 0)
                        current_recv = getattr(self, "_last_net_recv", 0)
                        if current_sent < net_io.bytes_sent:
                            self.prometheus_metrics.get(
                                "network_io_sent",
                                lambda: None,
                            ).inc(net_io.bytes_sent - current_sent)
                        if current_recv < net_io.bytes_recv:
                            self.prometheus_metrics.get(
                                "network_io_recv",
                                lambda: None,
                            ).inc(net_io.bytes_recv - current_recv)
                        self._last_net_sent = net_io.bytes_sent
                        self._last_net_recv = net_io.bytes_recv

            else:
                # Fallback metrics without psutil
                try:
                    rusage = resource.getrusage(resource.RUSAGE_SELF)
                    self._store_metric(
                        "process_cpu_time",
                        rusage.ru_utime + rusage.ru_stime,
                        timestamp,
                    )
                    self._store_metric(
                        "process_max_memory",
                        rusage.ru_maxrss * 1024,
                        timestamp,
                    )  # Convert to bytes

                    if tracemalloc.is_tracing():
                        current, peak = tracemalloc.get_traced_memory()
                        self._store_metric("tracemalloc_current", current, timestamp)
                        self._store_metric("tracemalloc_peak", peak, timestamp)
                except Exception:
                    pass

        except Exception as e:
            self.logger.error(f"Error collecting system metrics: {e}")

    def _collect_application_metrics(self) -> None:
        """Collect application-specific metrics."""
        timestamp = datetime.now()

        try:
            # Get GC statistics
            gc_stats = gc.get_stats()
            for i, stats in enumerate(gc_stats):
                self._store_metric(
                    f"gc_generation_{i}_collections",
                    stats.get("collections", 0),
                    timestamp,
                )
                self._store_metric(
                    f"gc_generation_{i}_collected",
                    stats.get("collected", 0),
                    timestamp,
                )
                self._store_metric(
                    f"gc_generation_{i}_uncollectable",
                    stats.get("uncollectable", 0),
                    timestamp,
                )

            # Thread count
            thread_count = threading.active_count()
            self._store_metric("active_threads", thread_count, timestamp)

            # Performance framework integration
            if self.performance_manager:
                try:
                    profile = self.performance_manager.collect_system_metrics()
                    self._store_metric(
                        "optimization_potential",
                        profile.optimization_potential,
                        timestamp,
                    )
                    self._store_metric(
                        "profile_collection_time_ms",
                        profile.profile_time * 1000,
                        timestamp,
                    )

                    # Store critical metrics count
                    critical_count = len(profile.get_critical_metrics())
                    self._store_metric(
                        "critical_metrics_count",
                        critical_count,
                        timestamp,
                    )

                except Exception as e:
                    self.logger.debug(
                        f"Performance framework metrics collection failed: {e}",
                    )

        except Exception as e:
            self.logger.error(f"Error collecting application metrics: {e}")

    def _collect_business_metrics(self) -> None:
        """Collect business-specific metrics."""
        timestamp = datetime.now()

        try:
            # These would be updated by the chunker components
            # For now, we'll track what we can observe

            # Calculate success rate from recent operations
            success_rate = self._calculate_success_rate()
            if success_rate is not None:
                self._store_metric("success_rate", success_rate, timestamp)

                if HAS_PROMETHEUS and "success_rate" in self.prometheus_metrics:
                    self.prometheus_metrics["success_rate"].set(success_rate)

            # Calculate throughput from recent chunk processing
            throughput = self._calculate_throughput()
            if throughput is not None:
                self._store_metric(
                    "throughput_chunks_per_second",
                    throughput,
                    timestamp,
                )

                if HAS_PROMETHEUS and "throughput" in self.prometheus_metrics:
                    self.prometheus_metrics["throughput"].set(throughput)

        except Exception as e:
            self.logger.error(f"Error collecting business metrics: {e}")

    def _collect_custom_metrics(self) -> None:
        """Collect custom registered metrics."""
        timestamp = datetime.now()

        for metric_name, metric_func in self.custom_metrics.items():
            try:
                value = metric_func()
                if value is not None:
                    self._store_metric(metric_name, value, timestamp)
            except Exception as e:
                self.logger.error(
                    f"Error collecting custom metric '{metric_name}': {e}",
                )

    def _store_metric(
        self,
        metric_name: str,
        value: float,
        timestamp: datetime,
    ) -> None:
        """Store a metric data point."""
        with self._lock:
            data_point = MetricDataPoint(
                metric_name=metric_name,
                value=value,
                timestamp=timestamp,
            )
            self.metrics_store[metric_name].append(data_point)

    def _calculate_success_rate(self) -> float | None:
        """Calculate recent success rate from error metrics."""
        try:
            with self._lock:
                error_metrics = self.metrics_store.get("error_count", deque())
                success_metrics = self.metrics_store.get("chunks_processed", deque())

                if not success_metrics:
                    return None

                # Look at recent data (last 10 minutes)
                cutoff_time = datetime.now() - timedelta(minutes=10)
                recent_errors = sum(
                    1 for dp in error_metrics if dp.timestamp > cutoff_time
                )
                recent_successes = sum(
                    1 for dp in success_metrics if dp.timestamp > cutoff_time
                )

                total_operations = recent_errors + recent_successes
                if total_operations == 0:
                    return None

                return (recent_successes / total_operations) * 100
        except Exception:
            return None

    def _calculate_throughput(self) -> float | None:
        """Calculate recent throughput."""
        try:
            with self._lock:
                chunk_metrics = self.metrics_store.get("chunks_processed", deque())

                if len(chunk_metrics) < 2:
                    return None

                # Calculate throughput over last 5 minutes
                cutoff_time = datetime.now() - timedelta(minutes=5)
                recent_chunks = [
                    dp for dp in chunk_metrics if dp.timestamp > cutoff_time
                ]

                if len(recent_chunks) < 2:
                    return None

                time_span = (
                    recent_chunks[-1].timestamp - recent_chunks[0].timestamp
                ).total_seconds()
                if time_span <= 0:
                    return None

                return len(recent_chunks) / time_span
        except Exception:
            return None

    def register_custom_metric(
        self,
        metric_name: str,
        metric_func: Callable[[], float],
    ) -> None:
        """Register a custom metric function."""
        self.custom_metrics[metric_name] = metric_func
        self.logger.info(f"Registered custom metric: {metric_name}")

    def unregister_custom_metric(self, metric_name: str) -> None:
        """Unregister a custom metric."""
        if metric_name in self.custom_metrics:
            del self.custom_metrics[metric_name]
            self.logger.info(f"Unregistered custom metric: {metric_name}")

    def record_business_metric(
        self,
        metric_name: str,
        value: float,
        labels: dict[str, str] | None = None,
    ) -> None:
        """Record a business metric value."""
        timestamp = datetime.now()

        with self._lock:
            data_point = MetricDataPoint(
                metric_name=metric_name,
                value=value,
                timestamp=timestamp,
                labels=labels or {},
            )
            self.metrics_store[metric_name].append(data_point)

        # Update Prometheus metric if available
        if HAS_PROMETHEUS and metric_name in self.prometheus_metrics:
            try:
                prometheus_metric = self.prometheus_metrics[metric_name]
                if hasattr(prometheus_metric, "labels") and labels:
                    prometheus_metric.labels(**labels).set(value)
                elif hasattr(prometheus_metric, "inc"):
                    prometheus_metric.inc(value)
                elif hasattr(prometheus_metric, "set"):
                    prometheus_metric.set(value)
                elif hasattr(prometheus_metric, "observe"):
                    prometheus_metric.observe(value)
            except Exception as e:
                self.logger.debug(
                    f"Failed to update Prometheus metric {metric_name}: {e}",
                )

    def get_metric_history(
        self,
        metric_name: str,
        duration_minutes: int = 60,
    ) -> list[MetricDataPoint]:
        """Get metric history for the specified duration."""
        cutoff_time = datetime.now() - timedelta(minutes=duration_minutes)

        with self._lock:
            metrics = self.metrics_store.get(metric_name, deque())
            return [dp for dp in metrics if dp.timestamp > cutoff_time]

    def get_metric_summary(
        self,
        metric_name: str,
        duration_minutes: int = 60,
    ) -> dict[str, Any]:
        """Get statistical summary of a metric."""
        history = self.get_metric_history(metric_name, duration_minutes)

        if not history:
            return {"error": "No data available"}

        values = [dp.value for dp in history]

        return {
            "metric_name": metric_name,
            "count": len(values),
            "min": min(values),
            "max": max(values),
            "avg": sum(values) / len(values),
            "latest": values[-1] if values else None,
            "duration_minutes": duration_minutes,
            "first_timestamp": history[0].timestamp.isoformat(),
            "last_timestamp": history[-1].timestamp.isoformat(),
        }

    def get_all_metrics_summary(self) -> dict[str, dict[str, Any]]:
        """Get summary of all collected metrics."""
        with self._lock:
            summaries = {}
            for metric_name in self.metrics_store.keys():
                summaries[metric_name] = self.get_metric_summary(metric_name, 60)
            return summaries

    def clear_metrics(self, metric_name: str | None = None) -> None:
        """Clear metrics data."""
        with self._lock:
            if metric_name:
                if metric_name in self.metrics_store:
                    self.metrics_store[metric_name].clear()
                    self.logger.info(f"Cleared metrics for: {metric_name}")
            else:
                self.metrics_store.clear()
                self.logger.info("Cleared all metrics")


class TracingManager:
    """Distributed tracing support with span management and context propagation."""

    def __init__(
        self,
        service_name: str = "treesitter-chunker",
        sampling_rate: float = 1.0,
    ):
        """Initialize the tracing manager."""
        self.service_name = service_name
        self.sampling_rate = max(0.0, min(1.0, sampling_rate))
        self.active_spans: dict[str, TraceSpan] = {}
        self.completed_traces: dict[str, list[TraceSpan]] = {}
        self.context_storage = threading.local()
        self._lock = threading.RLock()
        self.logger = logging.getLogger(f"{__name__}.TracingManager")

        # Trace sampling
        self.trace_id_counter = 0
        self.span_id_counter = 0

    def _should_sample(self) -> bool:
        """Determine if trace should be sampled."""
        import random

        return random.random() < self.sampling_rate

    def _generate_trace_id(self) -> str:
        """Generate a unique trace ID."""
        return f"trace_{uuid.uuid4().hex[:16]}"

    def _generate_span_id(self) -> str:
        """Generate a unique span ID."""
        return f"span_{uuid.uuid4().hex[:8]}"

    def start_trace(self, operation_name: str, **kwargs) -> TraceSpan:
        """Start a new distributed trace."""
        if not self._should_sample():
            # Return a no-op span
            return self._create_noop_span(operation_name)

        trace_id = self._generate_trace_id()
        span_id = self._generate_span_id()

        span = TraceSpan(
            span_id=span_id,
            trace_id=trace_id,
            parent_span_id=None,
            operation_name=operation_name,
            start_time=datetime.now(),
            tags={"service.name": self.service_name, "span.kind": "server", **kwargs},
        )

        with self._lock:
            self.active_spans[span_id] = span

        # Set as current span in context
        self._set_current_span(span)

        self.logger.debug(
            f"Started trace: {trace_id}, span: {span_id}, operation: {operation_name}",
        )
        return span

    def start_span(
        self,
        operation_name: str,
        parent_span: TraceSpan | None = None,
        **kwargs,
    ) -> TraceSpan:
        """Start a new span within an existing trace."""
        # Get parent span from context if not provided
        if parent_span is None:
            parent_span = self._get_current_span()

        if parent_span is None or not self._should_sample():
            return self._create_noop_span(operation_name)

        span_id = self._generate_span_id()

        span = TraceSpan(
            span_id=span_id,
            trace_id=parent_span.trace_id,
            parent_span_id=parent_span.span_id,
            operation_name=operation_name,
            start_time=datetime.now(),
            tags={"service.name": self.service_name, "span.kind": "internal", **kwargs},
            baggage=parent_span.baggage.copy(),  # Inherit baggage
        )

        with self._lock:
            self.active_spans[span_id] = span

        self.logger.debug(
            f"Started span: {span_id}, parent: {parent_span.span_id}, operation: {operation_name}",
        )
        return span

    def finish_span(self, span: TraceSpan, **kwargs) -> None:
        """Finish a span and move it to completed traces."""
        if span is None or span.finished:
            return

        span.finish()

        # Add any final tags
        for key, value in kwargs.items():
            span.set_tag(key, value)

        with self._lock:
            # Remove from active spans
            if span.span_id in self.active_spans:
                del self.active_spans[span.span_id]

            # Add to completed traces
            if span.trace_id not in self.completed_traces:
                self.completed_traces[span.trace_id] = []
            self.completed_traces[span.trace_id].append(span)

            # Cleanup old traces (keep only last 1000 traces)
            if len(self.completed_traces) > 1000:
                oldest_traces = sorted(self.completed_traces.keys())[:100]
                for trace_id in oldest_traces:
                    del self.completed_traces[trace_id]

        self.logger.debug(
            f"Finished span: {span.span_id}, duration: {span.duration_ms}ms",
        )

    def _create_noop_span(self, operation_name: str) -> TraceSpan:
        """Create a no-op span for non-sampled traces."""
        return TraceSpan(
            span_id="noop",
            trace_id="noop",
            parent_span_id=None,
            operation_name=operation_name,
            start_time=datetime.now(),
            finished=True,
        )

    def _set_current_span(self, span: TraceSpan) -> None:
        """Set current span in thread-local context."""
        if not hasattr(self.context_storage, "span_stack"):
            self.context_storage.span_stack = []
        self.context_storage.span_stack.append(span)

    def _get_current_span(self) -> TraceSpan | None:
        """Get current span from thread-local context."""
        if not hasattr(self.context_storage, "span_stack"):
            return None
        if not self.context_storage.span_stack:
            return None
        return self.context_storage.span_stack[-1]

    def _pop_current_span(self) -> TraceSpan | None:
        """Pop current span from context stack."""
        if not hasattr(self.context_storage, "span_stack"):
            return None
        if not self.context_storage.span_stack:
            return None
        return self.context_storage.span_stack.pop()

    @contextmanager
    def trace(self, operation_name: str, **kwargs):
        """Context manager for automatic span lifecycle management."""
        span = self.start_span(operation_name, **kwargs)
        self._set_current_span(span)

        try:
            yield span
        except Exception as e:
            span.set_tag("error", True)
            span.set_tag("error.type", type(e).__name__)
            span.set_tag("error.message", str(e))
            span.log(f"Exception occurred: {e}", level="error")
            raise
        finally:
            self._pop_current_span()
            self.finish_span(span)

    def inject_context(self, span: TraceSpan, carrier: dict[str, str]) -> None:
        """Inject trace context into carrier (for propagation)."""
        if span and span.trace_id != "noop":
            carrier["x-trace-id"] = span.trace_id
            carrier["x-span-id"] = span.span_id

            # Inject baggage
            for key, value in span.baggage.items():
                carrier[f"x-baggage-{key}"] = value

    def extract_context(self, carrier: dict[str, str]) -> TraceSpan | None:
        """Extract trace context from carrier."""
        trace_id = carrier.get("x-trace-id")
        parent_span_id = carrier.get("x-span-id")

        if not trace_id or not parent_span_id:
            return None

        # Create a span context for continuing the trace
        span = TraceSpan(
            span_id=parent_span_id,
            trace_id=trace_id,
            parent_span_id=None,
            operation_name="extracted_context",
            start_time=datetime.now(),
            finished=True,  # This is just a context holder
        )

        # Extract baggage
        for key, value in carrier.items():
            if key.startswith("x-baggage-"):
                baggage_key = key[10:]  # Remove 'x-baggage-' prefix
                span.baggage[baggage_key] = value

        return span

    def get_trace(self, trace_id: str) -> list[TraceSpan]:
        """Get all spans for a trace."""
        with self._lock:
            return self.completed_traces.get(trace_id, [])

    def get_active_spans(self) -> list[TraceSpan]:
        """Get all currently active spans."""
        with self._lock:
            return list(self.active_spans.values())

    def get_trace_summary(self, trace_id: str) -> dict[str, Any]:
        """Get summary of a trace."""
        spans = self.get_trace(trace_id)

        if not spans:
            return {"error": "Trace not found"}

        # Calculate trace statistics
        start_time = min(span.start_time for span in spans if span.start_time)
        end_time = max(span.end_time for span in spans if span.end_time)
        total_duration = (
            (end_time - start_time).total_seconds() * 1000
            if end_time and start_time
            else 0
        )

        return {
            "trace_id": trace_id,
            "span_count": len(spans),
            "total_duration_ms": total_duration,
            "start_time": start_time.isoformat() if start_time else None,
            "end_time": end_time.isoformat() if end_time else None,
            "root_operation": next(
                (s.operation_name for s in spans if s.parent_span_id is None),
                "unknown",
            ),
            "service_name": self.service_name,
            "has_errors": any(span.tags.get("error", False) for span in spans),
        }

    def search_traces(
        self,
        operation_name: str | None = None,
        service_name: str | None = None,
        min_duration_ms: float | None = None,
        max_duration_ms: float | None = None,
        has_errors: bool | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Search traces based on criteria."""
        results = []

        with self._lock:
            for trace_id in list(self.completed_traces.keys())[:limit]:
                trace_summary = self.get_trace_summary(trace_id)

                if trace_summary.get("error"):
                    continue

                # Apply filters
                if operation_name and operation_name not in trace_summary.get(
                    "root_operation",
                    "",
                ):
                    continue

                if service_name and service_name != trace_summary.get("service_name"):
                    continue

                duration = trace_summary.get("total_duration_ms", 0)
                if min_duration_ms and duration < min_duration_ms:
                    continue

                if max_duration_ms and duration > max_duration_ms:
                    continue

                if has_errors is not None and has_errors != trace_summary.get(
                    "has_errors",
                    False,
                ):
                    continue

                results.append(trace_summary)

        return results

    def clear_traces(self, before_timestamp: datetime | None = None) -> int:
        """Clear completed traces, optionally before a timestamp."""
        cleared_count = 0

        with self._lock:
            if before_timestamp is None:
                cleared_count = len(self.completed_traces)
                self.completed_traces.clear()
            else:
                traces_to_remove = []
                for trace_id, spans in self.completed_traces.items():
                    if any(
                        span.start_time and span.start_time < before_timestamp
                        for span in spans
                    ):
                        traces_to_remove.append(trace_id)

                for trace_id in traces_to_remove:
                    del self.completed_traces[trace_id]
                    cleared_count += 1

        self.logger.info(f"Cleared {cleared_count} traces")
        return cleared_count


class LogAggregator:
    """Centralized log collection with parsing, enrichment, and correlation."""

    def __init__(self, max_logs: int = 10000):
        """Initialize the log aggregator."""
        self.max_logs = max_logs
        self.logs: deque = deque(maxlen=max_logs)
        self.log_handlers: list[logging.Handler] = []
        self.enrichment_functions: list[Callable] = []
        self.alert_rules: list[dict[str, Any]] = []
        self.alerts: deque = deque(maxlen=1000)
        self._lock = threading.RLock()
        self.logger = logging.getLogger(f"{__name__}.LogAggregator")

        # Setup structured logging if available
        if HAS_STRUCTLOG:
            self._setup_structlog()
        else:
            self._setup_standard_logging()

    def _setup_structlog(self) -> None:
        """Setup structured logging with structlog."""
        try:
            structlog.configure(
                processors=[
                    structlog.stdlib.filter_by_level,
                    structlog.stdlib.add_logger_name,
                    structlog.stdlib.add_log_level,
                    structlog.stdlib.PositionalArgumentsFormatter(),
                    structlog.processors.TimeStamper(fmt="iso"),
                    structlog.processors.StackInfoRenderer(),
                    structlog.processors.format_exc_info,
                    self._structlog_processor,
                ],
                context_class=dict,
                logger_factory=structlog.stdlib.LoggerFactory(),
                wrapper_class=structlog.stdlib.BoundLogger,
                cache_logger_on_first_use=True,
            )
            self.logger.info("Configured structured logging with structlog")
        except Exception as e:
            self.logger.error(f"Failed to configure structlog: {e}")
            self._setup_standard_logging()

    def _setup_standard_logging(self) -> None:
        """Setup standard logging integration."""
        # Create custom handler that feeds into our aggregator
        handler = LogAggregatorHandler(self)
        handler.setLevel(logging.DEBUG)

        # Add to root logger
        root_logger = logging.getLogger()
        root_logger.addHandler(handler)
        self.log_handlers.append(handler)

        self.logger.info("Configured standard logging integration")

    def _structlog_processor(self, logger, method_name, event_dict):
        """Structlog processor to feed logs into aggregator."""
        try:
            # Extract information from structlog event
            log_entry = LogEntry(
                timestamp=datetime.now(),
                level=event_dict.get("level", "INFO"),
                message=event_dict.get("event", ""),
                logger_name=logger.name,
                module=event_dict.get("module", ""),
                function=event_dict.get("function", ""),
                line_number=event_dict.get("lineno", 0),
                extra=event_dict,
            )

            self._process_log_entry(log_entry)
        except Exception as e:
            # Don't let log processing break the application
            self.logger.debug("Error in structlog processor: %s", e)

        return event_dict

    def _process_log_entry(self, log_entry: LogEntry) -> None:
        """Process and store a log entry."""
        try:
            # Apply enrichment functions
            for enrichment_func in self.enrichment_functions:
                try:
                    enrichment_func(log_entry)
                except Exception as e:
                    self.logger.debug(f"Enrichment function failed: {e}")

            # Store log entry
            with self._lock:
                self.logs.append(log_entry)

            # Check alert rules
            self._check_alert_rules(log_entry)

        except Exception as e:
            # Don't let log processing break the application
            self.logger.debug("Error processing log entry: %s", e)

    def add_enrichment_function(self, func: Callable[[LogEntry], None]) -> None:
        """Add a log enrichment function."""
        self.enrichment_functions.append(func)
        self.logger.info(f"Added log enrichment function: {func.__name__}")

    def add_alert_rule(self, rule: dict[str, Any]) -> None:
        """Add a log-based alert rule."""
        required_fields = ["name", "condition", "severity"]
        if not all(field in rule for field in required_fields):
            raise ValueError(f"Alert rule must contain: {required_fields}")

        self.alert_rules.append(rule)
        self.logger.info(f"Added alert rule: {rule['name']}")

    def _check_alert_rules(self, log_entry: LogEntry) -> None:
        """Check log entry against alert rules."""
        for rule in self.alert_rules:
            try:
                if self._evaluate_alert_condition(log_entry, rule["condition"]):
                    alert = Alert(
                        alert_id=str(uuid.uuid4()),
                        metric_name="log_alert",
                        condition=rule["condition"],
                        threshold=0,  # N/A for log alerts
                        current_value=1,  # Alert triggered
                        severity=rule["severity"],
                        title=rule["name"],
                        description=f"Log alert triggered: {rule.get('description', rule['name'])}",
                        timestamp=datetime.now(),
                    )

                    with self._lock:
                        self.alerts.append(alert)

                    self.logger.warning(f"Log alert triggered: {rule['name']}")

            except Exception as e:
                self.logger.debug(f"Error evaluating alert rule {rule['name']}: {e}")

    def _evaluate_alert_condition(self, log_entry: LogEntry, condition: str) -> bool:
        """Evaluate an alert condition against a log entry."""
        try:
            # Simple condition evaluation
            condition_lower = condition.lower()

            if "level" in condition_lower:
                if "error" in condition_lower and log_entry.level.upper() == "ERROR":
                    return True
                if (
                    "warning" in condition_lower
                    and log_entry.level.upper() == "WARNING"
                ):
                    return True
                if (
                    "critical" in condition_lower
                    and log_entry.level.upper() == "CRITICAL"
                ):
                    return True

            if "message" in condition_lower:
                message_lower = log_entry.message.lower()
                # Extract quoted strings from condition
                import re

                quoted_strings = re.findall(r'"([^"]*)"', condition)
                for quoted_string in quoted_strings:
                    if quoted_string.lower() in message_lower:
                        return True

            if "exception" in condition_lower and log_entry.exception:
                return True

            return False

        except Exception:
            return False

    def search_logs(
        self,
        level: str | None = None,
        logger_name: str | None = None,
        message_contains: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        trace_id: str | None = None,
        limit: int = 100,
    ) -> list[LogEntry]:
        """Search logs based on criteria."""
        results = []

        with self._lock:
            logs_to_search = list(self.logs)[-limit * 10 :]  # Search in larger subset

        for log_entry in reversed(logs_to_search):  # Most recent first
            if len(results) >= limit:
                break

            # Apply filters
            if level and log_entry.level.upper() != level.upper():
                continue

            if logger_name and logger_name not in log_entry.logger_name:
                continue

            if (
                message_contains
                and message_contains.lower() not in log_entry.message.lower()
            ):
                continue

            if start_time and log_entry.timestamp < start_time:
                continue

            if end_time and log_entry.timestamp > end_time:
                continue

            if trace_id and log_entry.trace_id != trace_id:
                continue

            results.append(log_entry)

        return results

    def get_log_statistics(self, duration_minutes: int = 60) -> dict[str, Any]:
        """Get log statistics for the specified duration."""
        cutoff_time = datetime.now() - timedelta(minutes=duration_minutes)

        with self._lock:
            recent_logs = [log for log in self.logs if log.timestamp > cutoff_time]

        if not recent_logs:
            return {"error": "No logs in specified duration"}

        # Count by level
        level_counts = defaultdict(int)
        logger_counts = defaultdict(int)

        for log in recent_logs:
            level_counts[log.level.upper()] += 1
            logger_counts[log.logger_name] += 1

        return {
            "duration_minutes": duration_minutes,
            "total_logs": len(recent_logs),
            "logs_per_minute": len(recent_logs) / duration_minutes,
            "level_distribution": dict(level_counts),
            "top_loggers": dict(
                sorted(logger_counts.items(), key=lambda x: x[1], reverse=True)[:10],
            ),
            "first_log_time": (
                recent_logs[0].timestamp.isoformat() if recent_logs else None
            ),
            "last_log_time": (
                recent_logs[-1].timestamp.isoformat() if recent_logs else None
            ),
        }

    def correlate_with_traces(self, trace_id: str) -> list[LogEntry]:
        """Get all logs correlated with a specific trace."""
        return self.search_logs(trace_id=trace_id, limit=1000)

    def get_alerts(
        self,
        severity: str | None = None,
        resolved: bool | None = None,
    ) -> list[Alert]:
        """Get alerts based on criteria."""
        with self._lock:
            alerts = list(self.alerts)

        filtered_alerts = []
        for alert in alerts:
            if severity and alert.severity != severity:
                continue
            if resolved is not None and alert.resolved != resolved:
                continue
            filtered_alerts.append(alert)

        return filtered_alerts

    def resolve_alert(self, alert_id: str) -> bool:
        """Resolve an alert."""
        with self._lock:
            for alert in self.alerts:
                if alert.alert_id == alert_id:
                    alert.resolve()
                    self.logger.info(f"Resolved alert: {alert_id}")
                    return True
        return False

    def clear_logs(self, before_timestamp: datetime | None = None) -> int:
        """Clear logs, optionally before a timestamp."""
        cleared_count = 0

        with self._lock:
            if before_timestamp is None:
                cleared_count = len(self.logs)
                self.logs.clear()
            else:
                # Can't efficiently remove from middle of deque, so recreate
                remaining_logs = deque(
                    (log for log in self.logs if log.timestamp >= before_timestamp),
                    maxlen=self.max_logs,
                )
                cleared_count = len(self.logs) - len(remaining_logs)
                self.logs = remaining_logs

        self.logger.info(f"Cleared {cleared_count} logs")
        return cleared_count


class LogAggregatorHandler(logging.Handler):
    """Custom logging handler that feeds into LogAggregator."""

    def __init__(self, aggregator: LogAggregator):
        super().__init__()
        self.aggregator = aggregator

    def emit(self, record: logging.LogRecord) -> None:
        """Process a log record."""
        try:
            # Extract trace context if available
            trace_id = getattr(record, "trace_id", None)
            span_id = getattr(record, "span_id", None)

            log_entry = LogEntry(
                timestamp=datetime.fromtimestamp(record.created),
                level=record.levelname,
                message=record.getMessage(),
                logger_name=record.name,
                module=record.module,
                function=record.funcName,
                line_number=record.lineno,
                trace_id=trace_id,
                span_id=span_id,
                extra=getattr(record, "__dict__", {}),
                exception=self.format(record) if record.exc_info else None,
            )

            self.aggregator._process_log_entry(log_entry)

        except Exception:
            # Don't let logging break the application
            pass


class DashboardGenerator:
    """Real-time dashboard creation with metric visualization and export capabilities."""

    def __init__(self):
        """Initialize the dashboard generator."""
        self.dashboards: dict[str, dict[str, Any]] = {}
        self.widget_types = {
            "line_chart": self._create_line_chart,
            "bar_chart": self._create_bar_chart,
            "gauge": self._create_gauge,
            "counter": self._create_counter,
            "table": self._create_table,
            "heatmap": self._create_heatmap,
            "pie_chart": self._create_pie_chart,
        }
        self.logger = logging.getLogger(f"{__name__}.DashboardGenerator")

    def create_dashboard(
        self,
        dashboard_id: str,
        title: str,
        description: str = "",
        refresh_interval: int = 30,
    ) -> dict[str, Any]:
        """Create a new dashboard."""
        dashboard = {
            "id": dashboard_id,
            "title": title,
            "description": description,
            "refresh_interval": refresh_interval,
            "created_at": datetime.now().isoformat(),
            "widgets": [],
            "layout": {"rows": [], "columns": 12},
        }

        self.dashboards[dashboard_id] = dashboard
        self.logger.info(f"Created dashboard: {dashboard_id}")
        return dashboard

    def add_widget(
        self,
        dashboard_id: str,
        widget_id: str,
        widget_type: str,
        title: str,
        config: dict[str, Any],
        position: dict[str, int] | None = None,
    ) -> bool:
        """Add a widget to a dashboard."""
        if dashboard_id not in self.dashboards:
            self.logger.error(f"Dashboard not found: {dashboard_id}")
            return False

        if widget_type not in self.widget_types:
            self.logger.error(f"Unknown widget type: {widget_type}")
            return False

        widget = {
            "id": widget_id,
            "type": widget_type,
            "title": title,
            "config": config,
            "position": position or {"x": 0, "y": 0, "width": 6, "height": 4},
            "created_at": datetime.now().isoformat(),
        }

        self.dashboards[dashboard_id]["widgets"].append(widget)
        self.logger.info(f"Added widget {widget_id} to dashboard {dashboard_id}")
        return True

    def generate_dashboard_data(
        self,
        dashboard_id: str,
        metrics_collector: MetricsCollector,
        duration_minutes: int = 60,
    ) -> dict[str, Any]:
        """Generate real-time data for a dashboard."""
        if dashboard_id not in self.dashboards:
            return {"error": "Dashboard not found"}

        dashboard = self.dashboards[dashboard_id].copy()
        dashboard_data = {
            "dashboard": dashboard,
            "generated_at": datetime.now().isoformat(),
            "data_duration_minutes": duration_minutes,
            "widgets_data": {},
        }

        # Generate data for each widget
        for widget in dashboard["widgets"]:
            try:
                widget_data = self._generate_widget_data(
                    widget,
                    metrics_collector,
                    duration_minutes,
                )
                dashboard_data["widgets_data"][widget["id"]] = widget_data
            except Exception as e:
                self.logger.error(
                    f"Error generating data for widget {widget['id']}: {e}",
                )
                dashboard_data["widgets_data"][widget["id"]] = {"error": str(e)}

        return dashboard_data

    def _generate_widget_data(
        self,
        widget: dict[str, Any],
        metrics_collector: MetricsCollector,
        duration_minutes: int,
    ) -> dict[str, Any]:
        """Generate data for a specific widget."""
        widget_type = widget["type"]
        config = widget["config"]

        if widget_type not in self.widget_types:
            return {"error": f"Unknown widget type: {widget_type}"}

        # Call the appropriate widget generator
        generator_func = self.widget_types[widget_type]
        return generator_func(config, metrics_collector, duration_minutes)

    def _create_line_chart(
        self,
        config: dict[str, Any],
        metrics_collector: MetricsCollector,
        duration_minutes: int,
    ) -> dict[str, Any]:
        """Create line chart data."""
        metric_names = config.get("metrics", [])
        if not metric_names:
            return {"error": "No metrics specified for line chart"}

        chart_data = {
            "type": "line_chart",
            "series": [],
            "x_axis": {"type": "datetime", "title": "Time"},
            "y_axis": {"title": config.get("y_axis_title", "Value")},
        }

        for metric_name in metric_names:
            history = metrics_collector.get_metric_history(
                metric_name,
                duration_minutes,
            )
            if history:
                series_data = {
                    "name": metric_name,
                    "data": [
                        {"x": dp.timestamp.isoformat(), "y": dp.value} for dp in history
                    ],
                }
                chart_data["series"].append(series_data)

        return chart_data

    def _create_bar_chart(
        self,
        config: dict[str, Any],
        metrics_collector: MetricsCollector,
        duration_minutes: int,
    ) -> dict[str, Any]:
        """Create bar chart data."""
        metric_names = config.get("metrics", [])
        if not metric_names:
            return {"error": "No metrics specified for bar chart"}

        chart_data = {
            "type": "bar_chart",
            "categories": [],
            "series": [{"name": "Current Value", "data": []}],
        }

        for metric_name in metric_names:
            history = metrics_collector.get_metric_history(
                metric_name,
                duration_minutes,
            )
            if history:
                chart_data["categories"].append(metric_name)
                chart_data["series"][0]["data"].append(history[-1].value)

        return chart_data

    def _create_gauge(
        self,
        config: dict[str, Any],
        metrics_collector: MetricsCollector,
        duration_minutes: int,
    ) -> dict[str, Any]:
        """Create gauge data."""
        metric_name = config.get("metric")
        if not metric_name:
            return {"error": "No metric specified for gauge"}

        history = metrics_collector.get_metric_history(metric_name, duration_minutes)
        if not history:
            return {"error": "No data available for metric"}

        current_value = history[-1].value
        min_value = config.get("min_value", 0)
        max_value = config.get("max_value", 100)

        # Define threshold bands
        thresholds = config.get(
            "thresholds",
            [
                {"value": max_value * 0.8, "color": "yellow"},
                {"value": max_value * 0.9, "color": "red"},
            ],
        )

        return {
            "type": "gauge",
            "value": current_value,
            "min": min_value,
            "max": max_value,
            "thresholds": thresholds,
            "unit": config.get("unit", ""),
            "title": config.get("title", metric_name),
        }

    def _create_counter(
        self,
        config: dict[str, Any],
        metrics_collector: MetricsCollector,
        duration_minutes: int,
    ) -> dict[str, Any]:
        """Create counter data."""
        metric_name = config.get("metric")
        if not metric_name:
            return {"error": "No metric specified for counter"}

        history = metrics_collector.get_metric_history(metric_name, duration_minutes)
        if not history:
            return {"error": "No data available for metric"}

        current_value = history[-1].value

        # Calculate change from previous period
        previous_period_minutes = config.get("comparison_period", 60)
        previous_cutoff = datetime.now() - timedelta(minutes=previous_period_minutes)
        previous_values = [dp.value for dp in history if dp.timestamp < previous_cutoff]

        change = 0
        change_percent = 0
        if previous_values:
            previous_value = previous_values[-1]
            change = current_value - previous_value
            if previous_value != 0:
                change_percent = (change / previous_value) * 100

        return {
            "type": "counter",
            "value": current_value,
            "change": change,
            "change_percent": change_percent,
            "unit": config.get("unit", ""),
            "title": config.get("title", metric_name),
            "trend": "up" if change > 0 else "down" if change < 0 else "stable",
        }

    def _create_table(
        self,
        config: dict[str, Any],
        metrics_collector: MetricsCollector,
        duration_minutes: int,
    ) -> dict[str, Any]:
        """Create table data."""
        metric_names = config.get("metrics", [])
        if not metric_names:
            return {"error": "No metrics specified for table"}

        table_data = {
            "type": "table",
            "columns": ["Metric", "Current Value", "Min", "Max", "Average"],
            "rows": [],
        }

        for metric_name in metric_names:
            summary = metrics_collector.get_metric_summary(
                metric_name,
                duration_minutes,
            )
            if "error" not in summary:
                row = [
                    metric_name,
                    (
                        f"{summary['latest']:.2f}"
                        if summary["latest"] is not None
                        else "N/A"
                    ),
                    f"{summary['min']:.2f}",
                    f"{summary['max']:.2f}",
                    f"{summary['avg']:.2f}",
                ]
                table_data["rows"].append(row)

        return table_data

    def _create_heatmap(
        self,
        config: dict[str, Any],
        metrics_collector: MetricsCollector,
        duration_minutes: int,
    ) -> dict[str, Any]:
        """Create heatmap data."""
        metric_name = config.get("metric")
        if not metric_name:
            return {"error": "No metric specified for heatmap"}

        history = metrics_collector.get_metric_history(metric_name, duration_minutes)
        if not history:
            return {"error": "No data available for metric"}

        # Group data by time periods
        time_buckets = config.get("time_buckets", 24)  # Default 24 buckets
        bucket_size = duration_minutes / time_buckets

        heatmap_data = []
        for i in range(time_buckets):
            bucket_start = datetime.now() - timedelta(
                minutes=duration_minutes - (i * bucket_size),
            )
            bucket_end = bucket_start + timedelta(minutes=bucket_size)

            bucket_values = [
                dp.value for dp in history if bucket_start <= dp.timestamp < bucket_end
            ]

            avg_value = sum(bucket_values) / len(bucket_values) if bucket_values else 0
            heatmap_data.append(
                {"x": i, "y": 0, "value": avg_value},  # Single row heatmap
            )

        return {
            "type": "heatmap",
            "data": heatmap_data,
            "x_labels": [
                f"T-{int((time_buckets - i - 1) * bucket_size)}m"
                for i in range(time_buckets)
            ],
            "y_labels": [metric_name],
            "title": config.get("title", f"{metric_name} Heatmap"),
        }

    def _create_pie_chart(
        self,
        config: dict[str, Any],
        metrics_collector: MetricsCollector,
        duration_minutes: int,
    ) -> dict[str, Any]:
        """Create pie chart data."""
        metric_names = config.get("metrics", [])
        if not metric_names:
            return {"error": "No metrics specified for pie chart"}

        pie_data = {"type": "pie_chart", "series": []}

        total_value = 0
        metric_values = {}

        for metric_name in metric_names:
            history = metrics_collector.get_metric_history(
                metric_name,
                duration_minutes,
            )
            if history:
                value = history[-1].value
                metric_values[metric_name] = value
                total_value += value

        # Convert to percentages
        for metric_name, value in metric_values.items():
            percentage = (value / total_value * 100) if total_value > 0 else 0
            pie_data["series"].append(
                {"name": metric_name, "value": value, "percentage": percentage},
            )

        return pie_data

    def export_dashboard(self, dashboard_id: str, format_type: str = "json") -> str:
        """Export dashboard configuration."""
        if dashboard_id not in self.dashboards:
            raise ValueError(f"Dashboard not found: {dashboard_id}")

        dashboard = self.dashboards[dashboard_id]

        if format_type == "json":
            return json.dumps(dashboard, indent=2, default=str)
        if format_type == "yaml":
            try:
                import yaml

                return yaml.dump(dashboard, default_flow_style=False)
            except ImportError:
                raise ValueError("PyYAML required for YAML export")
        else:
            raise ValueError(f"Unsupported export format: {format_type}")

    def import_dashboard(self, dashboard_config: str, format_type: str = "json") -> str:
        """Import dashboard configuration."""
        try:
            if format_type == "json":
                dashboard = json.loads(dashboard_config)
            elif format_type == "yaml":
                import yaml

                dashboard = yaml.safe_load(dashboard_config)
            else:
                raise ValueError(f"Unsupported import format: {format_type}")

            dashboard_id = dashboard.get("id", str(uuid.uuid4()))
            self.dashboards[dashboard_id] = dashboard

            self.logger.info(f"Imported dashboard: {dashboard_id}")
            return dashboard_id

        except Exception as e:
            self.logger.error(f"Failed to import dashboard: {e}")
            raise

    def list_dashboards(self) -> list[dict[str, Any]]:
        """List all dashboards."""
        return [
            {
                "id": dashboard_id,
                "title": dashboard["title"],
                "description": dashboard["description"],
                "widget_count": len(dashboard["widgets"]),
                "created_at": dashboard["created_at"],
            }
            for dashboard_id, dashboard in self.dashboards.items()
        ]

    def delete_dashboard(self, dashboard_id: str) -> bool:
        """Delete a dashboard."""
        if dashboard_id in self.dashboards:
            del self.dashboards[dashboard_id]
            self.logger.info(f"Deleted dashboard: {dashboard_id}")
            return True
        return False


class MonitoringSystem:
    """Central monitoring orchestration system integrating all observability components."""

    def __init__(
        self,
        service_name: str = "treesitter-chunker",
        metrics_interval: float = 5.0,
        trace_sampling_rate: float = 1.0,
        max_logs: int = 10000,
    ):
        """Initialize the comprehensive monitoring system."""
        self.service_name = service_name
        self.logger = logging.getLogger(f"{__name__}.MonitoringSystem")

        # Initialize components
        self.metrics_collector = MetricsCollector(collection_interval=metrics_interval)
        self.tracing_manager = TracingManager(
            service_name=service_name,
            sampling_rate=trace_sampling_rate,
        )
        self.log_aggregator = LogAggregator(max_logs=max_logs)
        self.dashboard_generator = DashboardGenerator()

        # Alert management
        self.alert_rules: list[dict[str, Any]] = []
        self.active_alerts: dict[str, Alert] = {}
        self.alert_callbacks: list[Callable[[Alert], None]] = []

        # Integration with performance framework
        self.performance_manager: PerformanceManager | None = None
        if HAS_PERFORMANCE_FRAMEWORK:
            try:
                self.performance_manager = PerformanceManager(
                    enable_continuous_monitoring=True,
                )
            except Exception as e:
                self.logger.warning(f"Failed to initialize performance manager: {e}")

        # System state
        self.is_running = False
        self.monitoring_thread: threading.Thread | None = None
        self._stop_event = threading.Event()

        # Setup default dashboards
        self._setup_default_dashboards()

        # Setup default log enrichment
        self._setup_log_enrichment()

        # Setup default alert rules
        self._setup_default_alerts()

        self.logger.info(f"Initialized monitoring system for service: {service_name}")

    def start(self) -> None:
        """Start the monitoring system."""
        if self.is_running:
            self.logger.warning("Monitoring system already running")
            return

        try:
            # Start all components
            self.metrics_collector.start_collection()

            # Start monitoring loop
            self.is_running = True
            self._stop_event.clear()
            self.monitoring_thread = threading.Thread(
                target=self._monitoring_loop,
                daemon=True,
                name="MonitoringSystem",
            )
            self.monitoring_thread.start()

            self.logger.info("Started monitoring system")

        except Exception as e:
            self.logger.error(f"Failed to start monitoring system: {e}")
            self.stop()
            raise

    def stop(self) -> None:
        """Stop the monitoring system."""
        if not self.is_running:
            return

        try:
            self.is_running = False
            self._stop_event.set()

            # Stop components
            self.metrics_collector.stop_collection()

            if self.monitoring_thread:
                self.monitoring_thread.join(timeout=5.0)

            if self.performance_manager:
                self.performance_manager.stop_monitoring()

            self.logger.info("Stopped monitoring system")

        except Exception as e:
            self.logger.error(f"Error stopping monitoring system: {e}")

    def _monitoring_loop(self) -> None:
        """Main monitoring loop for alerts and system health."""
        while self.is_running and not self._stop_event.is_set():
            try:
                # Check metric-based alerts
                self._check_metric_alerts()

                # Perform health checks
                self._perform_health_checks()

                # Cleanup old data
                self._cleanup_old_data()

            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {e}")

            self._stop_event.wait(30.0)  # Check every 30 seconds

    def _check_metric_alerts(self) -> None:
        """Check metric-based alert rules."""
        for rule in self.alert_rules:
            try:
                if rule.get("type") != "metric":
                    continue

                metric_name = rule["metric"]
                condition = rule["condition"]
                threshold = rule["threshold"]

                # Get recent metric data
                recent_data = self.metrics_collector.get_metric_history(metric_name, 5)
                if not recent_data:
                    continue

                current_value = recent_data[-1].value

                # Evaluate condition
                alert_triggered = False
                if (
                    (condition == "greater_than" and current_value > threshold)
                    or (condition == "less_than" and current_value < threshold)
                    or (condition == "equals" and current_value == threshold)
                ):
                    alert_triggered = True

                alert_id = f"{rule['name']}_{metric_name}"

                if alert_triggered:
                    if alert_id not in self.active_alerts:
                        # Create new alert
                        alert = Alert(
                            alert_id=alert_id,
                            metric_name=metric_name,
                            condition=f"{condition} {threshold}",
                            threshold=threshold,
                            current_value=current_value,
                            severity=rule["severity"],
                            title=rule["name"],
                            description=rule.get(
                                "description",
                                f"{metric_name} {condition} {threshold}",
                            ),
                            timestamp=datetime.now(),
                        )

                        self.active_alerts[alert_id] = alert

                        # Trigger alert callbacks
                        for callback in self.alert_callbacks:
                            try:
                                callback(alert)
                            except Exception as e:
                                self.logger.error(f"Alert callback failed: {e}")

                        self.logger.warning(f"Alert triggered: {alert.title}")
                elif (
                    alert_id in self.active_alerts
                    and not self.active_alerts[alert_id].resolved
                ):
                    self.active_alerts[alert_id].resolve()
                    self.logger.info(f"Alert resolved: {alert_id}")

            except Exception as e:
                self.logger.error(
                    f"Error checking alert rule {rule.get('name', 'unknown')}: {e}",
                )

    def _perform_health_checks(self) -> None:
        """Perform system health checks."""
        try:
            # Check if metrics collection is healthy
            recent_metrics = self.metrics_collector.get_metric_history(
                "cpu_usage_percent",
                5,
            )
            if not recent_metrics:
                self.logger.warning(
                    "No recent CPU metrics - metrics collection may be unhealthy",
                )

            # Check log aggregation health
            recent_logs = self.log_aggregator.search_logs(limit=10)
            if len(recent_logs) < 5:
                self.logger.debug("Low log volume detected")

            # Check for memory leaks in monitoring system
            if HAS_PSUTIL:
                process = psutil.Process()
                memory_percent = process.memory_percent()
                if memory_percent > 10:  # Monitoring system using more than 10% memory
                    self.logger.warning(
                        f"High memory usage in monitoring system: {memory_percent:.2f}%",
                    )

        except Exception as e:
            self.logger.error(f"Error in health checks: {e}")

    def _cleanup_old_data(self) -> None:
        """Clean up old monitoring data."""
        try:
            # Clean up old traces (older than 24 hours)
            cutoff_time = datetime.now() - timedelta(hours=24)
            self.tracing_manager.clear_traces(cutoff_time)

            # Clean up old logs (older than 24 hours)
            self.log_aggregator.clear_logs(cutoff_time)

        except Exception as e:
            self.logger.error(f"Error in data cleanup: {e}")

    def _setup_default_dashboards(self) -> None:
        """Setup default monitoring dashboards."""
        try:
            # System Overview Dashboard
            self.dashboard_generator.create_dashboard(
                "system_overview",
                "System Overview",
                "High-level system metrics and performance indicators",
            )

            # Add system metrics widgets
            self.dashboard_generator.add_widget(
                "system_overview",
                "cpu_usage_chart",
                "line_chart",
                "CPU Usage",
                {"metrics": ["cpu_usage_percent"], "y_axis_title": "Percentage"},
                {"x": 0, "y": 0, "width": 6, "height": 4},
            )

            self.dashboard_generator.add_widget(
                "system_overview",
                "memory_usage_chart",
                "line_chart",
                "Memory Usage",
                {"metrics": ["memory_usage_percent"], "y_axis_title": "Percentage"},
                {"x": 6, "y": 0, "width": 6, "height": 4},
            )

            self.dashboard_generator.add_widget(
                "system_overview",
                "metrics_table",
                "table",
                "Current Metrics",
                {
                    "metrics": [
                        "cpu_usage_percent",
                        "memory_usage_percent",
                        "active_threads",
                    ],
                },
                {"x": 0, "y": 4, "width": 12, "height": 4},
            )

            # Application Performance Dashboard
            self.dashboard_generator.create_dashboard(
                "application_performance",
                "Application Performance",
                "Application-specific metrics and performance data",
            )

            # Add application widgets
            self.dashboard_generator.add_widget(
                "application_performance",
                "chunks_processed_counter",
                "counter",
                "Chunks Processed",
                {"metric": "chunks_processed", "unit": "chunks"},
                {"x": 0, "y": 0, "width": 3, "height": 3},
            )

            self.dashboard_generator.add_widget(
                "application_performance",
                "success_rate_gauge",
                "gauge",
                "Success Rate",
                {
                    "metric": "success_rate",
                    "min_value": 0,
                    "max_value": 100,
                    "unit": "%",
                },
                {"x": 3, "y": 0, "width": 3, "height": 3},
            )

            self.dashboard_generator.add_widget(
                "application_performance",
                "throughput_gauge",
                "gauge",
                "Throughput",
                {
                    "metric": "throughput_chunks_per_second",
                    "min_value": 0,
                    "max_value": 100,
                    "unit": "chunks/s",
                },
                {"x": 6, "y": 0, "width": 3, "height": 3},
            )

            self.dashboard_generator.add_widget(
                "application_performance",
                "error_count_counter",
                "counter",
                "Error Count",
                {"metric": "error_count", "unit": "errors"},
                {"x": 9, "y": 0, "width": 3, "height": 3},
            )

        except Exception as e:
            self.logger.error(f"Failed to setup default dashboards: {e}")

    def _setup_log_enrichment(self) -> None:
        """Setup default log enrichment functions."""

        def add_trace_context(log_entry: LogEntry) -> None:
            """Add trace context to log entries."""
            current_span = self.tracing_manager._get_current_span()
            if current_span and current_span.trace_id != "noop":
                log_entry.trace_id = current_span.trace_id
                log_entry.span_id = current_span.span_id

        def add_system_context(log_entry: LogEntry) -> None:
            """Add system context to log entries."""
            log_entry.extra["service_name"] = self.service_name
            log_entry.extra["hostname"] = (
                os.uname().nodename if hasattr(os, "uname") else "unknown"
            )
            log_entry.extra["pid"] = os.getpid()

        self.log_aggregator.add_enrichment_function(add_trace_context)
        self.log_aggregator.add_enrichment_function(add_system_context)

    def _setup_default_alerts(self) -> None:
        """Setup default alert rules."""
        default_rules = [
            {
                "name": "High CPU Usage",
                "type": "metric",
                "metric": "cpu_usage_percent",
                "condition": "greater_than",
                "threshold": 80.0,
                "severity": "warning",
                "description": "CPU usage is above 80%",
            },
            {
                "name": "Critical CPU Usage",
                "type": "metric",
                "metric": "cpu_usage_percent",
                "condition": "greater_than",
                "threshold": 95.0,
                "severity": "critical",
                "description": "CPU usage is above 95%",
            },
            {
                "name": "High Memory Usage",
                "type": "metric",
                "metric": "memory_usage_percent",
                "condition": "greater_than",
                "threshold": 85.0,
                "severity": "warning",
                "description": "Memory usage is above 85%",
            },
            {
                "name": "Critical Memory Usage",
                "type": "metric",
                "metric": "memory_usage_percent",
                "condition": "greater_than",
                "threshold": 95.0,
                "severity": "critical",
                "description": "Memory usage is above 95%",
            },
        ]

        for rule in default_rules:
            self.add_alert_rule(rule)

        # Setup default log alert rules
        log_alert_rules = [
            {
                "name": "Error Log Alert",
                "condition": "level error",
                "severity": "warning",
                "description": "Error level log detected",
            },
            {
                "name": "Exception Alert",
                "condition": "exception",
                "severity": "critical",
                "description": "Exception in log detected",
            },
        ]

        for rule in log_alert_rules:
            self.log_aggregator.add_alert_rule(rule)

    # Public API methods

    @contextmanager
    def trace_operation(self, operation_name: str, **kwargs):
        """Context manager for tracing operations."""
        with self.tracing_manager.trace(operation_name, **kwargs) as span:
            yield span

    def record_metric(
        self,
        metric_name: str,
        value: float,
        labels: dict[str, str] | None = None,
    ) -> None:
        """Record a business/application metric."""
        self.metrics_collector.record_business_metric(metric_name, value, labels)

    def add_alert_rule(self, rule: dict[str, Any]) -> None:
        """Add a new alert rule."""
        self.alert_rules.append(rule)
        self.logger.info(f"Added alert rule: {rule.get('name', 'unnamed')}")

    def add_alert_callback(self, callback: Callable[[Alert], None]) -> None:
        """Add an alert callback function."""
        self.alert_callbacks.append(callback)
        self.logger.info("Added alert callback")

    def get_system_health(self) -> dict[str, Any]:
        """Get comprehensive system health status."""
        return {
            "timestamp": datetime.now().isoformat(),
            "service_name": self.service_name,
            "monitoring_status": "healthy" if self.is_running else "stopped",
            "components": {
                "metrics_collector": {
                    "status": (
                        "running" if self.metrics_collector.is_collecting else "stopped"
                    ),
                    "metrics_count": len(self.metrics_collector.metrics_store),
                    "last_collection": (
                        "active" if self.metrics_collector.is_collecting else "inactive"
                    ),
                },
                "tracing_manager": {
                    "active_spans": len(self.tracing_manager.get_active_spans()),
                    "completed_traces": len(self.tracing_manager.completed_traces),
                    "sampling_rate": self.tracing_manager.sampling_rate,
                },
                "log_aggregator": {
                    "log_count": len(self.log_aggregator.logs),
                    "active_alerts": len(
                        [a for a in self.log_aggregator.get_alerts() if not a.resolved],
                    ),
                    "alert_rules": len(self.log_aggregator.alert_rules),
                },
                "dashboard_generator": {
                    "dashboard_count": len(self.dashboard_generator.dashboards),
                },
            },
            "active_alerts": len(
                [a for a in self.active_alerts.values() if not a.resolved],
            ),
            "performance_integration": self.performance_manager is not None,
        }

    def get_metrics_summary(self, duration_minutes: int = 60) -> dict[str, Any]:
        """Get summary of all metrics."""
        return self.metrics_collector.get_all_metrics_summary()

    def search_logs(self, **kwargs) -> list[LogEntry]:
        """Search logs with various criteria."""
        return self.log_aggregator.search_logs(**kwargs)

    def get_dashboard_data(
        self,
        dashboard_id: str,
        duration_minutes: int = 60,
    ) -> dict[str, Any]:
        """Get real-time dashboard data."""
        return self.dashboard_generator.generate_dashboard_data(
            dashboard_id,
            self.metrics_collector,
            duration_minutes,
        )

    def export_monitoring_config(self) -> dict[str, Any]:
        """Export complete monitoring configuration."""
        return {
            "service_name": self.service_name,
            "alert_rules": self.alert_rules,
            "dashboards": self.dashboard_generator.dashboards,
            "metrics_interval": self.metrics_collector.collection_interval,
            "trace_sampling_rate": self.tracing_manager.sampling_rate,
            "exported_at": datetime.now().isoformat(),
        }

    def import_monitoring_config(self, config: dict[str, Any]) -> None:
        """Import monitoring configuration."""
        try:
            if "alert_rules" in config:
                self.alert_rules.extend(config["alert_rules"])

            if "dashboards" in config:
                self.dashboard_generator.dashboards.update(config["dashboards"])

            self.logger.info("Imported monitoring configuration")

        except Exception as e:
            self.logger.error(f"Failed to import monitoring config: {e}")
            raise

    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()

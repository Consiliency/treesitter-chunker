"""Comprehensive unit tests for performance core framework."""

import gc
import json
import threading
import time
import tracemalloc
from datetime import datetime, timedelta
from unittest.mock import MagicMock, Mock, patch

import pytest

from chunker.performance.core import (
    MetricsCollector,
    OptimizationEngine,
    PerformanceBudget,
    PerformanceManager,
    PerformanceMetric,
    PerformanceProfile,
    PerformanceUtils,
)


class TestPerformanceMetric:
    """Test PerformanceMetric class."""

    def test_metric_creation(self):
        """Test basic metric creation."""
        timestamp = datetime.now()
        metric = PerformanceMetric(
            name="cpu_usage",
            value=75.5,
            unit="%",
            timestamp=timestamp,
            context={"source": "system"},
            category="cpu",
            severity="warning",
            metadata={"collection_method": "psutil"},
        )

        assert metric.name == "cpu_usage"
        assert metric.value == 75.5
        assert metric.unit == "%"
        assert metric.timestamp == timestamp
        assert metric.context == {"source": "system"}
        assert metric.category == "cpu"
        assert metric.severity == "warning"
        assert metric.metadata == {"collection_method": "psutil"}

    def test_to_dict(self):
        """Test metric serialization to dict."""
        timestamp = datetime.now()
        metric = PerformanceMetric(
            name="memory_usage",
            value=85.0,
            unit="%",
            timestamp=timestamp,
            context={"source": "test"},
            category="memory",
            severity="critical",
        )

        data = metric.to_dict()

        assert data["name"] == "memory_usage"
        assert data["value"] == 85.0
        assert data["timestamp"] == timestamp.isoformat()
        assert data["severity"] == "critical"

    def test_from_dict(self):
        """Test metric deserialization from dict."""
        timestamp = datetime.now()
        data = {
            "name": "io_rate",
            "value": 1024.0,
            "unit": "MB/s",
            "timestamp": timestamp.isoformat(),
            "context": {"source": "disk"},
            "category": "io",
            "severity": "normal",
            "metadata": {},
        }

        metric = PerformanceMetric.from_dict(data)

        assert metric.name == "io_rate"
        assert metric.value == 1024.0
        assert metric.timestamp == timestamp

    def test_is_within_threshold(self):
        """Test threshold checking."""
        metric = PerformanceMetric(
            name="cpu_usage",
            value=75.0,
            unit="%",
            timestamp=datetime.now(),
            context={},
            category="cpu",
            severity="normal",
        )

        assert metric.is_within_threshold(80.0)
        assert not metric.is_within_threshold(70.0)

    def test_get_severity_level(self):
        """Test severity level conversion."""
        metric_normal = PerformanceMetric(
            name="test",
            value=50.0,
            unit="%",
            timestamp=datetime.now(),
            context={},
            category="cpu",
            severity="normal",
        )
        metric_warning = PerformanceMetric(
            name="test",
            value=75.0,
            unit="%",
            timestamp=datetime.now(),
            context={},
            category="cpu",
            severity="warning",
        )
        metric_critical = PerformanceMetric(
            name="test",
            value=95.0,
            unit="%",
            timestamp=datetime.now(),
            context={},
            category="cpu",
            severity="critical",
        )

        assert metric_normal.get_severity_level() == 0
        assert metric_warning.get_severity_level() == 1
        assert metric_critical.get_severity_level() == 2


class TestPerformanceProfile:
    """Test PerformanceProfile class."""

    def test_profile_creation(self):
        """Test basic profile creation."""
        metrics = [
            PerformanceMetric(
                name="cpu_usage",
                value=50.0,
                unit="%",
                timestamp=datetime.now(),
                context={},
                category="cpu",
                severity="normal",
            ),
        ]

        profile = PerformanceProfile(
            component_name="test_component",
            metrics=metrics,
            profile_time=0.5,
            optimization_potential=25.0,
            recommendations=["Optimize algorithm"],
        )

        assert profile.component_name == "test_component"
        assert len(profile.metrics) == 1
        assert profile.optimization_potential == 25.0

    def test_get_metrics_by_category(self):
        """Test filtering metrics by category."""
        metrics = [
            PerformanceMetric(
                name="cpu_usage",
                value=50.0,
                unit="%",
                timestamp=datetime.now(),
                context={},
                category="cpu",
                severity="normal",
            ),
            PerformanceMetric(
                name="memory_usage",
                value=75.0,
                unit="%",
                timestamp=datetime.now(),
                context={},
                category="memory",
                severity="warning",
            ),
            PerformanceMetric(
                name="cpu_cores",
                value=4.0,
                unit="count",
                timestamp=datetime.now(),
                context={},
                category="cpu",
                severity="normal",
            ),
        ]

        profile = PerformanceProfile(
            component_name="test",
            metrics=metrics,
            profile_time=1.0,
            optimization_potential=10.0,
            recommendations=[],
        )

        cpu_metrics = profile.get_metrics_by_category("cpu")
        assert len(cpu_metrics) == 2

        memory_metrics = profile.get_metrics_by_category("memory")
        assert len(memory_metrics) == 1

    def test_get_critical_metrics(self):
        """Test filtering critical metrics."""
        metrics = [
            PerformanceMetric(
                name="cpu_usage",
                value=50.0,
                unit="%",
                timestamp=datetime.now(),
                context={},
                category="cpu",
                severity="normal",
            ),
            PerformanceMetric(
                name="memory_usage",
                value=95.0,
                unit="%",
                timestamp=datetime.now(),
                context={},
                category="memory",
                severity="critical",
            ),
        ]

        profile = PerformanceProfile(
            component_name="test",
            metrics=metrics,
            profile_time=1.0,
            optimization_potential=50.0,
            recommendations=[],
        )

        critical_metrics = profile.get_critical_metrics()
        assert len(critical_metrics) == 1
        assert critical_metrics[0].severity == "critical"

    def test_get_average_metric_value(self):
        """Test calculating average metric values."""
        metrics = [
            PerformanceMetric(
                name="cpu_usage",
                value=50.0,
                unit="%",
                timestamp=datetime.now(),
                context={},
                category="cpu",
                severity="normal",
            ),
            PerformanceMetric(
                name="cpu_usage",
                value=70.0,
                unit="%",
                timestamp=datetime.now(),
                context={},
                category="cpu",
                severity="normal",
            ),
            PerformanceMetric(
                name="memory_usage",
                value=80.0,
                unit="%",
                timestamp=datetime.now(),
                context={},
                category="memory",
                severity="normal",
            ),
        ]

        profile = PerformanceProfile(
            component_name="test",
            metrics=metrics,
            profile_time=1.0,
            optimization_potential=10.0,
            recommendations=[],
        )

        avg_cpu = profile.get_average_metric_value("cpu_usage")
        assert avg_cpu == 60.0

        avg_nonexistent = profile.get_average_metric_value("nonexistent")
        assert avg_nonexistent is None

    def test_to_dict(self):
        """Test profile serialization."""
        timestamp = datetime.now()
        metrics = [
            PerformanceMetric(
                name="test",
                value=50.0,
                unit="%",
                timestamp=timestamp,
                context={},
                category="cpu",
                severity="normal",
            ),
        ]

        profile = PerformanceProfile(
            component_name="test",
            metrics=metrics,
            profile_time=1.0,
            optimization_potential=25.0,
            recommendations=["test"],
            created_at=timestamp,
        )

        data = profile.to_dict()

        assert data["component_name"] == "test"
        assert len(data["metrics"]) == 1
        assert data["profile_time"] == 1.0
        assert data["created_at"] == timestamp.isoformat()


class TestMetricsCollector:
    """Test MetricsCollector class."""

    def test_collector_initialization(self):
        """Test collector initialization."""
        collector = MetricsCollector()

        assert collector.metrics_store == {}
        assert not collector.is_collecting
        assert collector.collection_thread is None

    def test_start_stop_collection(self):
        """Test starting and stopping collection."""
        collector = MetricsCollector()

        collector.start_collection(interval=0.1)
        assert collector.is_collecting
        assert collector.collection_thread is not None

        time.sleep(0.2)  # Let it collect once

        collector.stop_collection()
        assert not collector.is_collecting

    @patch("chunker.performance.core.performance_framework.psutil")
    def test_collect_cpu_metrics_with_psutil(self, mock_psutil):
        """Test CPU metrics collection with psutil."""
        # Mock psutil functions
        mock_psutil.cpu_percent.side_effect = [50.0, [25.0, 75.0]]
        mock_cpu_freq = Mock()
        mock_cpu_freq.current = 2400.0
        mock_cpu_freq.min = 1200.0
        mock_cpu_freq.max = 3200.0
        mock_psutil.cpu_freq.return_value = mock_cpu_freq
        mock_psutil.getloadavg.return_value = [1.0, 1.5, 2.0]

        collector = MetricsCollector()
        metrics = collector.collect_cpu_metrics()

        assert "cpu_percent" in metrics
        assert "cpu_core_0_percent" in metrics
        assert "cpu_freq_current" in metrics
        assert "load_avg_1min" in metrics

    def test_collect_cpu_metrics_fallback(self):
        """Test CPU metrics collection fallback without psutil."""
        with patch("chunker.performance.core.performance_framework.HAS_PSUTIL", False):
            collector = MetricsCollector()
            metrics = collector.collect_cpu_metrics()

            # Should have fallback metrics
            assert "process_cpu_time" in metrics

    @patch("chunker.performance.core.performance_framework.psutil")
    def test_collect_memory_metrics_with_psutil(self, mock_psutil):
        """Test memory metrics collection with psutil."""
        # Mock virtual memory
        mock_vmem = Mock()
        mock_vmem.total = 8 * 1024 * 1024 * 1024  # 8GB
        mock_vmem.available = 4 * 1024 * 1024 * 1024  # 4GB
        mock_vmem.used = 4 * 1024 * 1024 * 1024  # 4GB
        mock_vmem.percent = 50.0
        mock_vmem.free = 4 * 1024 * 1024 * 1024  # 4GB
        mock_psutil.virtual_memory.return_value = mock_vmem

        # Mock swap memory
        mock_swap = Mock()
        mock_swap.total = 2 * 1024 * 1024 * 1024  # 2GB
        mock_swap.used = 1 * 1024 * 1024 * 1024  # 1GB
        mock_swap.free = 1 * 1024 * 1024 * 1024  # 1GB
        mock_swap.percent = 50.0
        mock_psutil.swap_memory.return_value = mock_swap

        # Mock process memory
        mock_process = Mock()
        mock_pmem = Mock()
        mock_pmem.rss = 100 * 1024 * 1024  # 100MB
        mock_pmem.vms = 200 * 1024 * 1024  # 200MB
        mock_process.memory_info.return_value = mock_pmem
        mock_process.memory_percent.return_value = 1.25
        mock_psutil.Process.return_value = mock_process

        collector = MetricsCollector()
        metrics = collector.collect_memory_metrics()

        assert "memory_total" in metrics
        assert "memory_percent" in metrics
        assert "swap_percent" in metrics
        assert "process_memory_rss" in metrics

    def test_collect_memory_metrics_fallback(self):
        """Test memory metrics collection fallback."""
        with patch("chunker.performance.core.performance_framework.HAS_PSUTIL", False):
            collector = MetricsCollector()
            metrics = collector.collect_memory_metrics()

            # Should have some fallback metrics
            assert "process_memory_peak" in metrics

    @patch("chunker.performance.core.performance_framework.psutil")
    def test_collect_io_metrics_with_psutil(self, mock_psutil):
        """Test I/O metrics collection with psutil."""
        # Mock disk I/O
        mock_disk_io = Mock()
        mock_disk_io.read_bytes = 1024 * 1024
        mock_disk_io.write_bytes = 2048 * 1024
        mock_disk_io.read_count = 100
        mock_disk_io.write_count = 200
        mock_disk_io.read_time = 1000
        mock_disk_io.write_time = 2000
        mock_psutil.disk_io_counters.return_value = mock_disk_io

        # Mock network I/O
        mock_net_io = Mock()
        mock_net_io.bytes_sent = 5 * 1024 * 1024
        mock_net_io.bytes_recv = 10 * 1024 * 1024
        mock_net_io.packets_sent = 1000
        mock_net_io.packets_recv = 2000
        mock_net_io.errin = 0
        mock_net_io.errout = 0
        mock_net_io.dropin = 0
        mock_net_io.dropout = 0
        mock_psutil.net_io_counters.return_value = mock_net_io

        collector = MetricsCollector()
        metrics = collector.collect_io_metrics()

        assert "disk_read_bytes" in metrics
        assert "disk_write_bytes" in metrics
        assert "network_bytes_sent" in metrics
        assert "network_bytes_recv" in metrics

    def test_metric_history_management(self):
        """Test metric history storage and retrieval."""
        collector = MetricsCollector()

        # Add some mock metrics
        timestamp = datetime.now()
        metric = PerformanceMetric(
            name="test_metric",
            value=50.0,
            unit="%",
            timestamp=timestamp,
            context={},
            category="test",
            severity="normal",
        )

        collector.metrics_store["test_metric"] = [metric]

        history = collector.get_metric_history("test_metric")
        assert len(history) == 1
        assert history[0].name == "test_metric"

        # Test non-existent metric
        empty_history = collector.get_metric_history("nonexistent")
        assert empty_history == []

    def test_clear_metrics(self):
        """Test clearing all metrics."""
        collector = MetricsCollector()

        # Add some metrics
        timestamp = datetime.now()
        metric = PerformanceMetric(
            name="test_metric",
            value=50.0,
            unit="%",
            timestamp=timestamp,
            context={},
            category="test",
            severity="normal",
        )

        collector.metrics_store["test_metric"] = [metric]

        collector.clear_metrics()
        assert collector.metrics_store == {}


class TestOptimizationEngine:
    """Test OptimizationEngine class."""

    def test_engine_initialization(self):
        """Test engine initialization."""
        engine = OptimizationEngine()

        assert engine.optimization_strategies != {}
        assert engine.performance_baseline == {}
        assert "gc_optimization" in engine.optimization_strategies
        assert "memory_optimization" in engine.optimization_strategies

    def test_detect_bottlenecks(self):
        """Test bottleneck detection."""
        engine = OptimizationEngine()

        # Create profile with bottlenecks
        metrics = [
            PerformanceMetric(
                name="cpu_usage",
                value=95.0,
                unit="%",
                timestamp=datetime.now(),
                context={},
                category="cpu",
                severity="critical",
            ),
            PerformanceMetric(
                name="memory_usage",
                value=92.0,
                unit="%",
                timestamp=datetime.now(),
                context={},
                category="memory",
                severity="critical",
            ),
        ]

        profile = PerformanceProfile(
            component_name="test",
            metrics=metrics,
            profile_time=1.0,
            optimization_potential=80.0,
            recommendations=[],
        )

        bottlenecks = engine.detect_bottlenecks(profile)

        assert len(bottlenecks) > 0
        assert any("cpu" in b.lower() for b in bottlenecks)
        assert any("memory" in b.lower() for b in bottlenecks)

    def test_generate_optimizations(self):
        """Test optimization generation."""
        engine = OptimizationEngine()

        bottlenecks = [
            "High CPU usage: cpu_percent at 95.0%",
            "High memory usage: memory_percent at 92.0%",
        ]

        optimizations = engine.generate_optimizations(bottlenecks)

        assert len(optimizations) > 0
        assert any(opt["strategy"] == "gc_optimization" for opt in optimizations)
        assert any(opt["strategy"] == "memory_optimization" for opt in optimizations)

        # Check optimization structure
        opt = optimizations[0]
        assert "name" in opt
        assert "description" in opt
        assert "strategy" in opt
        assert "priority" in opt
        assert "estimated_impact" in opt

    def test_apply_optimization(self):
        """Test applying optimizations."""
        engine = OptimizationEngine()

        optimization = {
            "name": "test_gc_optimization",
            "strategy": "gc_optimization",
            "description": "Test GC optimization",
        }

        result = engine.apply_optimization(optimization)

        # Should succeed (GC optimization should work)
        assert result

        # Check that optimization was recorded
        history = engine.get_optimization_history()
        assert len(history) > 0
        assert history[-1]["optimization"]["name"] == "test_gc_optimization"

    def test_validate_optimization(self):
        """Test optimization validation."""
        engine = OptimizationEngine()

        # Apply an optimization first
        optimization = {"name": "test_optimization", "strategy": "gc_optimization"}

        engine.apply_optimization(optimization)

        # Validate should return True since we just applied it
        result = engine.validate_optimization(optimization)
        assert result

    def test_register_custom_strategy(self):
        """Test registering custom optimization strategy."""
        engine = OptimizationEngine()

        def custom_strategy(optimization):
            return True

        engine.register_optimization_strategy("custom_test", custom_strategy)

        assert "custom_test" in engine.optimization_strategies

        # Test applying custom strategy
        optimization = {"name": "test_custom", "strategy": "custom_test"}

        result = engine.apply_optimization(optimization)
        assert result

    def test_builtin_gc_optimization(self):
        """Test built-in GC optimization."""
        engine = OptimizationEngine()

        old_thresholds = gc.get_threshold()

        optimization = {"strategy": "gc_optimization"}
        result = engine._optimize_garbage_collection(optimization)

        assert result

        new_thresholds = gc.get_threshold()

        # Thresholds should have changed
        assert new_thresholds != old_thresholds

    def test_builtin_memory_optimization(self):
        """Test built-in memory optimization."""
        engine = OptimizationEngine()

        optimization = {"strategy": "memory_optimization"}
        result = engine._optimize_memory_usage(optimization)

        assert result

    @patch("chunker.performance.core.performance_framework.psutil")
    def test_builtin_cpu_affinity_optimization(self, mock_psutil):
        """Test built-in CPU affinity optimization."""
        engine = OptimizationEngine()

        # Mock process with many CPUs
        mock_process = Mock()
        mock_process.cpu_affinity.return_value = [0, 1, 2, 3, 4, 5, 6, 7]
        mock_psutil.Process.return_value = mock_process
        mock_psutil.cpu_count.return_value = 8

        optimization = {"strategy": "cpu_affinity"}
        result = engine._optimize_cpu_affinity(optimization)

        assert result
        # Should have called cpu_affinity to set new affinity
        mock_process.cpu_affinity.assert_called()

    def test_builtin_threading_optimization(self):
        """Test built-in threading optimization."""
        engine = OptimizationEngine()

        optimization = {"strategy": "thread_optimization"}
        result = engine._optimize_threading(optimization)

        # Result depends on platform support, but should not raise exception
        assert isinstance(result, bool)


class TestPerformanceBudget:
    """Test PerformanceBudget class."""

    def test_budget_initialization(self):
        """Test budget initialization with defaults."""
        budget = PerformanceBudget()

        assert budget.budget_limits != {}
        assert "cpu_percent" in budget.budget_limits
        assert "memory_percent" in budget.budget_limits
        assert budget.current_usage == {}
        assert budget.violations == []

    def test_set_budget_limit(self):
        """Test setting budget limits."""
        budget = PerformanceBudget()

        budget.set_budget_limit("cpu_percent", 75.0)

        assert budget.budget_limits["cpu_percent"] == 75.0

    def test_check_budget_violation(self):
        """Test budget violation detection."""
        budget = PerformanceBudget()

        budget.set_budget_limit("cpu_percent", 80.0)

        # No violation
        violation = budget.check_budget_violation("cpu_percent", 75.0)
        assert not violation

        # Violation
        violation = budget.check_budget_violation("cpu_percent", 85.0)
        assert violation

        # Check violation was recorded
        assert len(budget.violations) == 1
        assert budget.violations[0]["metric"] == "cpu_percent"
        assert budget.violations[0]["value"] == 85.0

    def test_get_budget_status(self):
        """Test budget status reporting."""
        budget = PerformanceBudget()

        budget.set_budget_limit("cpu_percent", 80.0)
        budget.check_budget_violation("cpu_percent", 85.0)

        status = budget.get_budget_status()

        assert "timestamp" in status
        assert "total_metrics_monitored" in status
        assert "metrics_in_violation" in status
        assert "budget_health" in status
        assert "current_usage" in status
        assert "budget_limits" in status
        assert "recent_violations" in status

        assert status["budget_health"] in ["good", "warning", "critical"]

    def test_get_budget_utilization(self):
        """Test budget utilization calculation."""
        budget = PerformanceBudget()

        budget.set_budget_limit("cpu_percent", 80.0)
        budget.current_usage["cpu_percent"] = 60.0

        utilization = budget.get_budget_utilization()

        assert "cpu_percent" in utilization
        assert utilization["cpu_percent"] == 75.0  # 60/80 * 100

    def test_clear_violations(self):
        """Test clearing violation history."""
        budget = PerformanceBudget()

        budget.set_budget_limit("cpu_percent", 80.0)
        budget.check_budget_violation("cpu_percent", 85.0)

        assert len(budget.violations) == 1

        budget.clear_violations()

        assert len(budget.violations) == 0

    def test_export_import_config(self):
        """Test budget configuration export/import."""
        budget = PerformanceBudget()

        budget.set_budget_limit("cpu_percent", 75.0)
        budget.set_budget_limit("memory_percent", 90.0)

        config = budget.export_budget_config()

        assert "budget_limits" in config
        assert "exported_at" in config
        assert config["budget_limits"]["cpu_percent"] == 75.0

        # Test import
        new_budget = PerformanceBudget()
        new_budget.import_budget_config(config)

        assert new_budget.budget_limits["cpu_percent"] == 75.0
        assert new_budget.budget_limits["memory_percent"] == 90.0


class TestPerformanceUtils:
    """Test PerformanceUtils class."""

    def test_measure_execution_time(self):
        """Test execution time measurement decorator."""

        @PerformanceUtils.measure_execution_time
        def test_function():
            time.sleep(0.01)  # Sleep 10ms
            return "result"

        result = test_function()

        assert result == "result"
        assert hasattr(test_function, "_performance_timings")
        assert len(test_function._performance_timings) == 1
        assert (
            test_function._performance_timings[0] >= 8
        )  # At least 8ms (allowing for variation)

    def test_profile_memory_usage(self):
        """Test memory usage profiling decorator."""
        if not tracemalloc.is_tracing():
            tracemalloc.start()

        @PerformanceUtils.profile_memory_usage
        def test_function():
            # Allocate some memory
            data = [i for i in range(1000)]
            return data

        result = test_function()

        assert len(result) == 1000

        if hasattr(test_function, "_memory_usage"):
            assert len(test_function._memory_usage) >= 1

    def test_optimize_memory_allocation(self):
        """Test memory allocation optimization."""
        # Test small sizes
        assert PerformanceUtils.optimize_memory_allocation(512) == 512

        # Test larger sizes (should round to power of 2)
        assert PerformanceUtils.optimize_memory_allocation(1500) == 2048
        assert PerformanceUtils.optimize_memory_allocation(3000) == 4096

        # Test edge cases
        assert PerformanceUtils.optimize_memory_allocation(0) == 1
        assert PerformanceUtils.optimize_memory_allocation(-1) == 1

    @patch("chunker.performance.core.performance_framework.psutil")
    def test_cpu_affinity_optimization(self, mock_psutil):
        """Test CPU affinity optimization."""
        mock_process = Mock()
        mock_process.cpu_affinity.return_value = [0, 1, 2, 3, 4, 5, 6, 7]
        mock_psutil.Process.return_value = mock_process
        mock_psutil.cpu_count.return_value = 8

        PerformanceUtils.cpu_affinity_optimization()

        # Should have attempted to set CPU affinity
        mock_process.cpu_affinity.assert_called()

    def test_get_function_performance_stats(self):
        """Test getting function performance statistics."""

        @PerformanceUtils.measure_execution_time
        def test_function():
            time.sleep(0.01)

        # Call function multiple times
        test_function()
        test_function()
        test_function()

        stats = PerformanceUtils.get_function_performance_stats(test_function)

        assert stats["function_name"] == "test_function"
        assert "timing_stats" in stats

        if "count" in stats["timing_stats"]:
            assert stats["timing_stats"]["count"] == 3
            assert "min_ms" in stats["timing_stats"]
            assert "max_ms" in stats["timing_stats"]
            assert "avg_ms" in stats["timing_stats"]

    def test_clear_function_performance_data(self):
        """Test clearing function performance data."""

        @PerformanceUtils.measure_execution_time
        def test_function():
            pass

        test_function()

        assert hasattr(test_function, "_performance_timings")
        assert len(test_function._performance_timings) > 0

        PerformanceUtils.clear_function_performance_data(test_function)

        assert len(test_function._performance_timings) == 0

    def test_create_performance_context_manager(self):
        """Test performance context manager."""
        context_manager = PerformanceUtils.create_performance_context_manager(
            "test_block",
        )

        with context_manager:
            time.sleep(0.01)  # Do some work

        # Should complete without error
        assert True

    def test_benchmark_function(self):
        """Test function benchmarking."""

        def test_function(x, y):
            return x + y

        results = PerformanceUtils.benchmark_function(
            test_function,
            iterations=10,
            x=5,
            y=3,
        )

        assert "function_name" in results
        assert "iterations" in results
        assert "timing" in results
        assert results["function_name"] == "test_function"
        assert results["iterations"] == 10

        timing = results["timing"]
        assert "min_ms" in timing
        assert "max_ms" in timing
        assert "avg_ms" in timing


class TestPerformanceManager:
    """Test PerformanceManager class."""

    def test_manager_initialization(self):
        """Test manager initialization."""
        manager = PerformanceManager(enable_continuous_monitoring=False)

        assert manager.metrics_collector is not None
        assert manager.optimization_engine is not None
        assert manager.performance_budget is not None
        assert not manager.enable_continuous_monitoring

    def test_collect_system_metrics(self):
        """Test system metrics collection."""
        manager = PerformanceManager(enable_continuous_monitoring=False)

        profile = manager.collect_system_metrics()

        assert isinstance(profile, PerformanceProfile)
        assert profile.component_name == "system"
        assert len(profile.metrics) > 0
        assert profile.profile_time >= 0
        assert isinstance(profile.optimization_potential, float)
        assert isinstance(profile.recommendations, list)

    def test_analyze_performance(self):
        """Test performance analysis."""
        manager = PerformanceManager(enable_continuous_monitoring=False)

        analysis = manager.analyze_performance()

        assert "timestamp" in analysis
        assert "overall_health" in analysis
        assert "bottlenecks" in analysis
        assert "recommendations" in analysis
        assert "optimization_potential" in analysis
        assert "metrics_summary" in analysis

        assert analysis["overall_health"] in ["good", "warning", "critical", "unknown"]

    def test_optimize_system(self):
        """Test system optimization."""
        manager = PerformanceManager(enable_continuous_monitoring=False)

        result = manager.optimize_system()

        assert "status" in result
        assert "message" in result
        assert "optimizations_applied" in result
        assert "improvement" in result

        assert result["status"] in ["success", "error"]

    def test_validate_optimizations(self):
        """Test optimization validation."""
        manager = PerformanceManager(enable_continuous_monitoring=False)

        # Need at least 2 profiles for validation
        manager.collect_system_metrics()  # First profile
        time.sleep(0.1)
        manager.collect_system_metrics()  # Second profile

        result = manager.validate_optimizations()

        assert "status" in result
        assert "validation_passed" in result

        if result["status"] == "success":
            assert "potential_improvement" in result
            assert "critical_metrics_reduction" in result
            assert "comparison_details" in result

    def test_start_stop_monitoring(self):
        """Test starting and stopping continuous monitoring."""
        manager = PerformanceManager(enable_continuous_monitoring=False)

        manager.start_monitoring()
        assert manager._monitoring_thread is not None
        assert manager._monitoring_thread.is_alive()

        time.sleep(0.1)  # Let it run briefly

        manager.stop_monitoring()
        # Thread should stop within timeout
        time.sleep(0.1)

    def test_performance_history(self):
        """Test performance history management."""
        manager = PerformanceManager(enable_continuous_monitoring=False)

        # Collect some profiles
        profile1 = manager.collect_system_metrics()
        profile2 = manager.collect_system_metrics()

        # Note: profiles are only stored during continuous monitoring
        # So history might be empty here, which is expected behavior
        history = manager.get_performance_history()
        assert isinstance(history, list)

        # Test clearing history
        manager.clear_performance_history()
        empty_history = manager.get_performance_history()
        assert len(empty_history) == 0


class TestIntegration:
    """Integration tests for the performance framework."""

    def test_end_to_end_performance_monitoring(self):
        """Test complete performance monitoring workflow."""
        # Initialize components
        manager = PerformanceManager(enable_continuous_monitoring=False)

        # Collect baseline metrics
        baseline_profile = manager.collect_system_metrics()
        assert baseline_profile is not None

        # Analyze performance
        analysis = manager.analyze_performance()
        assert "overall_health" in analysis

        # Apply optimizations if needed
        if analysis["overall_health"] != "good":
            optimization_result = manager.optimize_system()
            assert optimization_result["status"] == "success"

            # Validate optimizations
            validation_result = manager.validate_optimizations()
            # May not have enough data for validation in test
            assert validation_result["status"] in ["success", "insufficient_data"]

    def test_metrics_collection_and_budget_enforcement(self):
        """Test metrics collection with budget enforcement."""
        collector = MetricsCollector()
        budget = PerformanceBudget()

        # Set strict budget limits
        budget.set_budget_limit("cpu_percent", 50.0)
        budget.set_budget_limit("memory_percent", 60.0)

        # Collect metrics
        cpu_metrics = collector.collect_cpu_metrics()
        memory_metrics = collector.collect_memory_metrics()

        # Check against budget
        for name, value in {**cpu_metrics, **memory_metrics}.items():
            if name in budget.budget_limits:
                budget.check_budget_violation(name, value)

        # Get budget status
        status = budget.get_budget_status()
        assert status["budget_health"] in ["good", "warning", "critical"]

    def test_optimization_workflow(self):
        """Test complete optimization workflow."""
        engine = OptimizationEngine()

        # Create a profile with performance issues
        problematic_metrics = [
            PerformanceMetric(
                name="cpu_usage",
                value=95.0,
                unit="%",
                timestamp=datetime.now(),
                context={},
                category="cpu",
                severity="critical",
            ),
            PerformanceMetric(
                name="memory_usage",
                value=88.0,
                unit="%",
                timestamp=datetime.now(),
                context={},
                category="memory",
                severity="warning",
            ),
        ]

        profile = PerformanceProfile(
            component_name="test_system",
            metrics=problematic_metrics,
            profile_time=1.5,
            optimization_potential=75.0,
            recommendations=[],
        )

        # Detect bottlenecks
        bottlenecks = engine.detect_bottlenecks(profile)
        assert len(bottlenecks) > 0

        # Generate optimizations
        optimizations = engine.generate_optimizations(bottlenecks)
        assert len(optimizations) > 0

        # Apply optimizations
        applied_count = 0
        for optimization in optimizations[:2]:  # Apply first 2
            if engine.apply_optimization(optimization):
                applied_count += 1

        assert applied_count > 0

        # Validate optimizations
        for optimization in optimizations[:applied_count]:
            assert engine.validate_optimization(optimization)

    def test_performance_utils_integration(self):
        """Test performance utilities integration."""

        @PerformanceUtils.measure_execution_time
        @PerformanceUtils.profile_memory_usage
        def intensive_function():
            # Simulate intensive work
            data = []
            for i in range(10000):
                data.append(str(i) * 10)
            return len(data)

        # Run the function
        result = intensive_function()
        assert result == 10000

        # Check performance data
        stats = PerformanceUtils.get_function_performance_stats(intensive_function)
        assert "timing_stats" in stats

        # Benchmark the function
        benchmark_results = PerformanceUtils.benchmark_function(
            intensive_function,
            iterations=5,
        )

        assert benchmark_results["iterations"] == 5
        assert "timing" in benchmark_results
        assert benchmark_results["timing"]["min_ms"] > 0


# Fixtures for testing
@pytest.fixture()
def sample_metric():
    """Create a sample performance metric for testing."""
    return PerformanceMetric(
        name="test_metric",
        value=75.0,
        unit="%",
        timestamp=datetime.now(),
        context={"source": "test"},
        category="cpu",
        severity="normal",
    )


@pytest.fixture()
def sample_profile():
    """Create a sample performance profile for testing."""
    metrics = [
        PerformanceMetric(
            name="cpu_usage",
            value=50.0,
            unit="%",
            timestamp=datetime.now(),
            context={},
            category="cpu",
            severity="normal",
        ),
        PerformanceMetric(
            name="memory_usage",
            value=65.0,
            unit="%",
            timestamp=datetime.now(),
            context={},
            category="memory",
            severity="warning",
        ),
    ]

    return PerformanceProfile(
        component_name="test_component",
        metrics=metrics,
        profile_time=1.0,
        optimization_potential=30.0,
        recommendations=["Monitor memory usage"],
    )


if __name__ == "__main__":
    pytest.main([__file__])

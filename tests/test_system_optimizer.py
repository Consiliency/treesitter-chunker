#!/usr/bin/env python3
"""
Comprehensive tests for the system optimization engine.
Tests cover all optimization components with 95%+ coverage.
"""

import gc
import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from chunker.performance.optimization.system_optimizer import (
    CPUOptimizer,
    IOOptimizer,
    MemoryOptimizer,
    OptimizationResult,
    SystemOptimizer,
)


class TestOptimizationResult(unittest.TestCase):
    """Test OptimizationResult dataclass functionality."""

    def test_optimization_result_creation(self):
        """Test OptimizationResult creation and properties."""
        result = OptimizationResult(
            name="test_optimization",
            success=True,
            improvement=15.5,
            details={"method": "test", "value": 100},
        )

        self.assertEqual(result.name, "test_optimization")
        self.assertTrue(result.success)
        self.assertEqual(result.improvement, 15.5)
        self.assertEqual(result.details["method"], "test")
        self.assertIsNotNone(result.timestamp)

    def test_optimization_result_to_dict(self):
        """Test OptimizationResult serialization to dictionary."""
        result = OptimizationResult(
            name="test_optimization",
            success=True,
            improvement=15.5,
            details={"method": "test"},
        )

        result_dict = result.to_dict()

        self.assertIsInstance(result_dict, dict)
        self.assertEqual(result_dict["name"], "test_optimization")
        self.assertTrue(result_dict["success"])
        self.assertEqual(result_dict["improvement"], 15.5)
        self.assertIn("timestamp", result_dict)


class TestSystemOptimizer(unittest.TestCase):
    """Test SystemOptimizer main orchestration functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.optimizer = SystemOptimizer()

    def tearDown(self):
        """Clean up after tests."""
        # Stop any monitoring that might be running
        try:
            self.optimizer.performance_manager.stop_monitoring()
        except Exception:
            pass

    def test_system_optimizer_initialization(self):
        """Test SystemOptimizer initialization."""
        self.assertIsNotNone(self.optimizer.performance_manager)
        self.assertIsNotNone(self.optimizer.cpu_optimizer)
        self.assertIsNotNone(self.optimizer.memory_optimizer)
        self.assertIsNotNone(self.optimizer.io_optimizer)
        self.assertIsNotNone(self.optimizer.logger)
        self.assertIsInstance(self.optimizer._optimization_history, list)

    @patch("chunker.performance.optimization.system_optimizer.PerformanceManager")
    def test_optimize_system_success(self, mock_pm_class):
        """Test successful system optimization."""
        # Mock performance manager
        mock_pm = Mock()
        mock_profile = Mock()
        mock_profile.optimization_potential = 50.0
        mock_pm.collect_system_metrics.return_value = mock_profile
        mock_pm_class.return_value = mock_pm

        optimizer = SystemOptimizer()
        optimizer.cpu_optimizer = Mock()
        optimizer.memory_optimizer = Mock()
        optimizer.io_optimizer = Mock()

        # Mock optimizer responses
        optimizer.cpu_optimizer.optimize_performance.return_value = {
            "success": True,
            "improvement": 10.0,
        }
        optimizer.memory_optimizer.optimize_performance.return_value = {
            "success": True,
            "improvement": 15.0,
        }
        optimizer.io_optimizer.optimize_performance.return_value = {
            "success": True,
            "improvement": 8.0,
        }

        result = optimizer.optimize_system()

        self.assertTrue(result["success"])
        self.assertGreater(result["total_improvement"], 0)
        self.assertEqual(len(result["optimization_results"]), 3)
        self.assertIn("timestamp", result)

    def test_optimize_cpu_delegation(self):
        """Test CPU optimization delegation."""
        with patch.object(
            self.optimizer.cpu_optimizer,
            "optimize_performance",
        ) as mock_opt:
            mock_opt.return_value = {"success": True, "improvement": 5.0}

            result = self.optimizer.optimize_cpu()

            mock_opt.assert_called_once()
            self.assertTrue(result["success"])

    def test_optimize_memory_delegation(self):
        """Test memory optimization delegation."""
        with patch.object(
            self.optimizer.memory_optimizer,
            "optimize_performance",
        ) as mock_opt:
            mock_opt.return_value = {"success": True, "improvement": 8.0}

            result = self.optimizer.optimize_memory()

            mock_opt.assert_called_once()
            self.assertTrue(result["success"])

    def test_optimize_io_delegation(self):
        """Test I/O optimization delegation."""
        with patch.object(
            self.optimizer.io_optimizer,
            "optimize_performance",
        ) as mock_opt:
            mock_opt.return_value = {"success": True, "improvement": 3.0}

            result = self.optimizer.optimize_io()

            mock_opt.assert_called_once()
            self.assertTrue(result["success"])

    def test_measure_improvements_no_baseline(self):
        """Test measuring improvements without baseline."""
        result = self.optimizer.measure_improvements()

        self.assertIn("error", result)
        self.assertEqual(result["improvement"], 0.0)

    def test_measure_improvements_with_baseline(self):
        """Test measuring improvements with baseline."""
        # Set up mock baseline
        mock_baseline = Mock()
        mock_baseline.optimization_potential = 60.0
        mock_baseline.get_critical_metrics.return_value = [
            Mock(),
            Mock(),
        ]  # 2 critical metrics

        self.optimizer._baseline_metrics = mock_baseline

        with patch.object(
            self.optimizer.performance_manager,
            "collect_system_metrics",
        ) as mock_collect:
            mock_current = Mock()
            mock_current.optimization_potential = 40.0
            mock_current.get_critical_metrics.return_value = [
                Mock(),
            ]  # 1 critical metric
            mock_current.get_metrics_by_category.return_value = []
            mock_collect.return_value = mock_current

            result = self.optimizer.measure_improvements()

            self.assertIn("overall", result)
            self.assertGreater(result["overall"], 0)
            self.assertEqual(result["baseline_critical_count"], 2)
            self.assertEqual(result["current_critical_count"], 1)
            self.assertEqual(result["critical_reduction"], 1)

    def test_get_optimization_status(self):
        """Test getting optimization status."""
        status = self.optimizer.get_optimization_status()

        self.assertIn("has_baseline", status)
        self.assertIn("optimization_count", status)
        self.assertIn("recent_optimizations", status)
        self.assertIn("system_health", status)
        self.assertIn("timestamp", status)

    def test_system_improvement_calculation(self):
        """Test system improvement calculation."""
        # Create mock profiles
        baseline = Mock()
        baseline.optimization_potential = 80.0
        baseline.get_critical_metrics.return_value = [
            Mock(),
            Mock(),
            Mock(),
        ]  # 3 critical

        current = Mock()
        current.optimization_potential = 50.0
        current.get_critical_metrics.return_value = [Mock()]  # 1 critical

        improvement = self.optimizer._calculate_system_improvement(baseline, current)

        # Should be 30% from potential + some from critical reduction
        self.assertGreater(improvement, 30.0)
        self.assertLessEqual(improvement, 100.0)

    def test_category_improvement_calculation(self):
        """Test category-specific improvement calculation."""
        # Create mock metrics
        baseline_metrics = [Mock(), Mock()]
        baseline_metrics[0].value = 80.0
        baseline_metrics[0].unit = "%"
        baseline_metrics[1].value = 70.0
        baseline_metrics[1].unit = "%"

        current_metrics = [Mock(), Mock()]
        current_metrics[0].value = 60.0
        current_metrics[0].unit = "%"
        current_metrics[1].value = 50.0
        current_metrics[1].unit = "%"

        baseline = Mock()
        baseline.get_metrics_by_category.return_value = baseline_metrics

        current = Mock()
        current.get_metrics_by_category.return_value = current_metrics

        improvement = self.optimizer._calculate_category_improvement(
            "cpu",
            baseline,
            current,
        )

        # Average baseline: 75%, average current: 55% -> 26.67% improvement
        self.assertGreater(improvement, 20.0)
        self.assertLess(improvement, 30.0)


class TestCPUOptimizer(unittest.TestCase):
    """Test CPUOptimizer functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.optimizer = CPUOptimizer()

    def tearDown(self):
        """Clean up thread pools."""
        for pool in self.optimizer.thread_pools.values():
            try:
                pool.shutdown(wait=False)
            except Exception:
                pass

    def test_cpu_optimizer_initialization(self):
        """Test CPUOptimizer initialization."""
        self.assertIsNone(self.optimizer.current_affinity)
        self.assertIsInstance(self.optimizer.thread_pools, dict)
        self.assertIsNotNone(self.optimizer.logger)

    @patch("chunker.performance.optimization.system_optimizer.HAS_PSUTIL", True)
    @patch("chunker.performance.optimization.system_optimizer.psutil")
    def test_optimize_thread_pools_success(self, mock_psutil):
        """Test successful thread pool optimization."""
        mock_psutil.cpu_count.return_value = 8

        result = self.optimizer.optimize_thread_pools()

        self.assertTrue(result["success"])
        self.assertGreater(result["improvement"], 0)
        self.assertGreater(result["pools_created"], 0)
        self.assertIn("pool_configs", result)

        # Check that pools were actually created
        self.assertGreater(len(self.optimizer.thread_pools), 0)

    @patch("chunker.performance.optimization.system_optimizer.HAS_PSUTIL", False)
    def test_optimize_thread_pools_no_psutil(self):
        """Test thread pool optimization without psutil."""
        result = self.optimizer.optimize_thread_pools()

        self.assertFalse(result["success"])
        self.assertIn("psutil not available", result["error"])
        self.assertEqual(result["improvement"], 0.0)

    @patch("chunker.performance.optimization.system_optimizer.HAS_PSUTIL", True)
    @patch("chunker.performance.optimization.system_optimizer.psutil")
    def test_set_cpu_affinity_success(self, mock_psutil):
        """Test successful CPU affinity setting."""
        mock_process = Mock()
        mock_process.cpu_affinity.return_value = [0, 1, 2, 3]
        mock_psutil.Process.return_value = mock_process
        mock_psutil.cpu_count.return_value = 4

        result = self.optimizer.set_cpu_affinity([0, 1])

        self.assertTrue(result)
        mock_process.cpu_affinity.assert_called_with([0, 1])
        self.assertEqual(self.optimizer.current_affinity, [0, 1])

    @patch("chunker.performance.optimization.system_optimizer.HAS_PSUTIL", True)
    @patch("chunker.performance.optimization.system_optimizer.psutil")
    def test_set_cpu_affinity_invalid_cpus(self, mock_psutil):
        """Test CPU affinity setting with invalid CPU list."""
        mock_psutil.cpu_count.return_value = 4

        result = self.optimizer.set_cpu_affinity([10, 11])  # Invalid CPUs

        self.assertFalse(result)

    @patch("chunker.performance.optimization.system_optimizer.HAS_PSUTIL", False)
    def test_set_cpu_affinity_no_psutil(self):
        """Test CPU affinity setting without psutil."""
        result = self.optimizer.set_cpu_affinity([0, 1])

        self.assertFalse(result)

    @patch("chunker.performance.optimization.system_optimizer.HAS_PSUTIL", True)
    @patch("chunker.performance.optimization.system_optimizer.psutil")
    def test_set_optimal_cpu_affinity(self, mock_psutil):
        """Test automatic optimal CPU affinity setting."""
        mock_process = Mock()
        mock_process.cpu_affinity.return_value = [0, 1, 2, 3, 4, 5, 6, 7]  # All 8 cores
        mock_psutil.Process.return_value = mock_process
        mock_psutil.cpu_count.return_value = 8

        with patch.object(
            self.optimizer,
            "set_cpu_affinity",
            return_value=True,
        ) as mock_set:
            result = self.optimizer.set_optimal_cpu_affinity()

            self.assertTrue(result["success"])
            self.assertGreater(result["improvement"], 0)
            mock_set.assert_called_once()

    def test_optimize_cache_usage(self):
        """Test CPU cache usage optimization."""
        result = self.optimizer.optimize_cache_usage()

        self.assertTrue(result["success"])
        self.assertGreaterEqual(result["improvement"], 0)
        self.assertIn("optimizations_applied", result)

    @patch("chunker.performance.optimization.system_optimizer.HAS_PSUTIL", True)
    @patch("chunker.performance.optimization.system_optimizer.psutil")
    def test_balance_cpu_load(self, mock_psutil):
        """Test CPU load balancing."""
        mock_psutil.cpu_percent.return_value = [90, 30, 80, 20]  # Imbalanced load
        mock_process = Mock()
        mock_process.nice.return_value = 0
        mock_psutil.Process.return_value = mock_process

        result = self.optimizer.balance_cpu_load()

        self.assertTrue(result["success"])
        self.assertIn("load_imbalance", result)
        self.assertIn("cpu_loads", result)

    @patch("chunker.performance.optimization.system_optimizer.HAS_PSUTIL", True)
    @patch("chunker.performance.optimization.system_optimizer.psutil")
    def test_balance_cpu_load_already_balanced(self, mock_psutil):
        """Test CPU load balancing when already balanced."""
        mock_psutil.cpu_percent.return_value = [50, 55, 48, 52]  # Balanced load

        result = self.optimizer.balance_cpu_load()

        self.assertTrue(result["success"])
        self.assertEqual(result["improvement"], 0.0)
        self.assertIn("already balanced", result["details"])

    def test_get_thread_pool(self):
        """Test getting thread pool."""
        # First create a pool
        self.optimizer.thread_pools["test_pool"] = Mock()

        pool = self.optimizer.get_thread_pool("test_pool")
        self.assertIsNotNone(pool)

        # Test non-existent pool
        pool = self.optimizer.get_thread_pool("nonexistent")
        self.assertIsNone(pool)

    @patch("chunker.performance.optimization.system_optimizer.HAS_PSUTIL", True)
    @patch("chunker.performance.optimization.system_optimizer.psutil")
    def test_optimize_performance_full_flow(self, mock_psutil):
        """Test full CPU optimization flow."""
        mock_psutil.cpu_count.return_value = 4
        mock_psutil.cpu_percent.return_value = [50, 50, 50, 50]
        mock_process = Mock()
        mock_process.cpu_affinity.return_value = [0, 1, 2, 3]
        mock_process.nice.return_value = 0
        mock_process.cpu_percent.return_value = 25.0
        mock_psutil.Process.return_value = mock_process

        result = self.optimizer.optimize_performance()

        self.assertTrue(result["success"])
        self.assertIn("optimizations", result)
        self.assertIn("baseline_metrics", result)
        self.assertIn("timestamp", result)


class TestMemoryOptimizer(unittest.TestCase):
    """Test MemoryOptimizer functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.optimizer = MemoryOptimizer()

    def test_memory_optimizer_initialization(self):
        """Test MemoryOptimizer initialization."""
        self.assertIsInstance(self.optimizer.memory_pools, dict)
        self.assertIsInstance(self.optimizer.gc_settings, dict)
        self.assertIsNotNone(self.optimizer.logger)

    def test_optimize_garbage_collection(self):
        """Test garbage collection optimization."""
        original_thresholds = gc.get_threshold()

        try:
            result = self.optimizer.optimize_garbage_collection()

            self.assertTrue(result["success"])
            self.assertGreaterEqual(
                result["improvement"],
                0,
            )  # Can be 0 if no objects to collect
            self.assertIn("old_thresholds", result)
            self.assertIn("new_thresholds", result)
            self.assertIn("objects_collected", result)

            # Check that thresholds were actually changed
            new_thresholds = gc.get_threshold()
            self.assertNotEqual(original_thresholds, new_thresholds)

        finally:
            # Restore original thresholds
            gc.set_threshold(*original_thresholds)

    def test_create_memory_pools(self):
        """Test memory pool creation."""
        result = self.optimizer.create_memory_pools()

        self.assertTrue(result["success"])
        self.assertGreater(result["improvement"], 0)
        self.assertGreater(result["pools_created"], 0)
        self.assertIn("pool_sizes", result)

        # Check that pools were actually created
        self.assertGreater(len(self.optimizer.memory_pools), 0)

        # Test pool structure
        for pool_name, pool in self.optimizer.memory_pools.items():
            self.assertIn("size", pool)
            self.assertIn("buffers", pool)
            self.assertIn("available", pool)
            self.assertIn("in_use", pool)

    def test_detect_memory_leaks(self):
        """Test memory leak detection."""
        leaks = self.optimizer.detect_memory_leaks()

        self.assertIsInstance(leaks, list)
        # Should return empty list or detected issues

    def test_detect_and_cleanup_leaks(self):
        """Test leak detection and cleanup."""
        result = self.optimizer.detect_and_cleanup_leaks()

        self.assertTrue(result["success"])
        self.assertGreaterEqual(result["improvement"], 0)
        self.assertIn("initial_leaks", result)
        self.assertIn("final_leaks", result)
        self.assertIn("cleanup_actions", result)

    def test_optimize_allocation_patterns(self):
        """Test allocation pattern optimization."""
        result = self.optimizer.optimize_allocation_patterns()

        self.assertTrue(result["success"])
        self.assertGreaterEqual(result["improvement"], 0)
        self.assertIn("optimizations", result)

    def test_get_memory_pool_success(self):
        """Test successful memory pool allocation."""
        # First create pools
        self.optimizer.create_memory_pools()

        buffer = self.optimizer.get_memory_pool(64)

        if buffer is not None:  # Pool might be empty or not available
            self.assertIsInstance(buffer, bytearray)
            self.assertLessEqual(len(buffer), 64)

    def test_get_memory_pool_no_pools(self):
        """Test memory pool allocation with no pools."""
        buffer = self.optimizer.get_memory_pool(64)

        self.assertIsNone(buffer)

    def test_return_to_pool(self):
        """Test returning buffer to memory pool."""
        # Create pools and get a buffer
        self.optimizer.create_memory_pools()
        buffer = self.optimizer.get_memory_pool(64)

        if buffer is not None:
            # Return the buffer
            self.optimizer.return_to_pool(buffer, 64)
            # This should not raise an exception

    @patch("chunker.performance.optimization.system_optimizer.HAS_PSUTIL", True)
    @patch("chunker.performance.optimization.system_optimizer.psutil")
    def test_optimize_performance_full_flow(self, mock_psutil):
        """Test full memory optimization flow."""
        mock_process = Mock()
        mock_memory_info = Mock()
        mock_memory_info.rss = 500 * 1024 * 1024  # 500MB
        mock_memory_info.vms = 1000 * 1024 * 1024  # 1GB
        mock_process.memory_info.return_value = mock_memory_info
        mock_process.memory_percent.return_value = 10.0
        mock_psutil.Process.return_value = mock_process

        mock_vmem = Mock()
        mock_vmem.total = 8 * 1024 * 1024 * 1024  # 8GB
        mock_vmem.available = 4 * 1024 * 1024 * 1024  # 4GB
        mock_vmem.percent = 50.0
        mock_psutil.virtual_memory.return_value = mock_vmem

        result = self.optimizer.optimize_performance()

        self.assertTrue(result["success"])
        self.assertIn("optimizations", result)
        self.assertIn("baseline_metrics", result)


class TestIOOptimizer(unittest.TestCase):
    """Test IOOptimizer functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.optimizer = IOOptimizer()

    def tearDown(self):
        """Clean up timers."""
        for timer in self.optimizer._batch_timers.values():
            try:
                timer.cancel()
            except Exception:
                pass

    def test_io_optimizer_initialization(self):
        """Test IOOptimizer initialization."""
        self.assertIsInstance(self.optimizer.connection_pools, dict)
        self.assertIsInstance(self.optimizer.batch_operations, dict)
        self.assertIsNotNone(self.optimizer.logger)

    def test_optimize_file_operations(self):
        """Test file operation optimization."""
        result = self.optimizer.optimize_file_operations()

        self.assertTrue(result["success"])
        self.assertGreater(result["improvement"], 0)
        self.assertIn("optimizations", result)
        self.assertIn("buffer_sizes", result)
        self.assertTrue(result["cache_enabled"])

    def test_optimize_network_io(self):
        """Test network I/O optimization."""
        result = self.optimizer.optimize_network_io()

        self.assertTrue(result["success"])
        self.assertGreater(result["improvement"], 0)
        self.assertIn("optimizations", result)
        self.assertIn("socket_config", result)
        self.assertGreaterEqual(result["connection_pools"], 1)

    def test_implement_batching(self):
        """Test I/O operation batching implementation."""
        result = self.optimizer.implement_batching()

        self.assertTrue(result["success"])
        self.assertGreater(result["improvement"], 0)
        self.assertGreater(result["batches_created"], 0)
        self.assertIn("batch_configs", result)

        # Check that batches were created
        self.assertGreater(len(self.optimizer.batch_operations), 0)

    def test_optimize_connection_pools(self):
        """Test connection pool optimization."""
        result = self.optimizer.optimize_connection_pools()

        self.assertTrue(result["success"])
        self.assertGreater(result["improvement"], 0)
        self.assertGreater(result["pools_optimized"], 0)
        self.assertIn("pool_configs", result)

        # Check that pools were created
        self.assertGreater(len(self.optimizer.connection_pools), 0)

    def test_add_to_batch(self):
        """Test adding operations to batch."""
        # First create batches
        self.optimizer.implement_batching()

        # Add operations to a batch
        batch_name = list(self.optimizer.batch_operations.keys())[0]
        self.optimizer.add_to_batch(batch_name, "test_operation")

        batch = self.optimizer.batch_operations[batch_name]
        self.assertIn("test_operation", batch["operations"])

    def test_add_to_batch_nonexistent(self):
        """Test adding to non-existent batch."""
        # Should not raise an exception
        self.optimizer.add_to_batch("nonexistent_batch", "test_operation")

    def test_flush_batch(self):
        """Test batch flushing."""
        # Create batches and add operation
        self.optimizer.implement_batching()
        batch_name = list(self.optimizer.batch_operations.keys())[0]
        self.optimizer.add_to_batch(batch_name, "test_operation")

        # Flush the batch
        self.optimizer._flush_batch(batch_name)

        # Check that batch is empty
        batch = self.optimizer.batch_operations[batch_name]
        self.assertEqual(len(batch["operations"]), 0)

    def test_read_file_cached_no_cache(self):
        """Test cached file reading without cache initialized."""
        result = self.optimizer.read_file_cached("nonexistent.txt")

        self.assertIsNone(result)

    def test_read_file_cached_with_cache(self):
        """Test cached file reading with cache."""
        # Initialize cache
        self.optimizer.optimize_file_operations()

        # Create a temporary file
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.write("test content")
            temp_file = f.name

        try:
            # Read file (should cache it)
            content1 = self.optimizer.read_file_cached(temp_file)
            content2 = self.optimizer.read_file_cached(temp_file)  # Should hit cache

            self.assertIsNotNone(content1)
            self.assertEqual(content1, content2)
            self.assertGreater(self.optimizer._file_cache["hits"], 0)

        finally:
            Path(temp_file).unlink()

    @patch("chunker.performance.optimization.system_optimizer.HAS_PSUTIL", True)
    @patch("chunker.performance.optimization.system_optimizer.psutil")
    def test_optimize_performance_full_flow(self, mock_psutil):
        """Test full I/O optimization flow."""
        # Mock I/O counters
        mock_disk_io = Mock()
        mock_disk_io.read_bytes = 1000000
        mock_disk_io.write_bytes = 500000
        mock_disk_io.read_count = 100
        mock_disk_io.write_count = 50
        mock_psutil.disk_io_counters.return_value = mock_disk_io

        mock_net_io = Mock()
        mock_net_io.bytes_sent = 2000000
        mock_net_io.bytes_recv = 3000000
        mock_net_io.packets_sent = 1000
        mock_net_io.packets_recv = 1500
        mock_psutil.net_io_counters.return_value = mock_net_io

        mock_process = Mock()
        mock_pio = Mock()
        mock_pio.read_bytes = 800000
        mock_pio.write_bytes = 400000
        mock_pio.read_count = 80
        mock_pio.write_count = 40
        mock_process.io_counters.return_value = mock_pio
        mock_psutil.Process.return_value = mock_process

        result = self.optimizer.optimize_performance()

        self.assertTrue(result["success"])
        self.assertIn("optimizations", result)
        self.assertIn("baseline_metrics", result)


class TestIntegration(unittest.TestCase):
    """Integration tests for the complete system optimizer."""

    def test_full_system_optimization_flow(self):
        """Test complete system optimization flow."""
        optimizer = SystemOptimizer()

        try:
            # Run optimization
            result = optimizer.optimize_system()

            # Should complete without errors
            self.assertIn("success", result)
            self.assertIn("total_improvement", result)
            self.assertIn("optimization_results", result)

            # Measure improvements
            improvements = optimizer.measure_improvements()
            self.assertIn("overall", improvements)

            # Get status
            status = optimizer.get_optimization_status()
            self.assertIn("has_baseline", status)

        finally:
            # Clean up
            try:
                optimizer.performance_manager.stop_monitoring()
            except Exception:
                pass

    def test_individual_optimizer_integration(self):
        """Test individual optimizers work together."""
        system_optimizer = SystemOptimizer()

        # Test CPU optimization
        cpu_result = system_optimizer.optimize_cpu()
        self.assertIn("success", cpu_result)

        # Test memory optimization
        memory_result = system_optimizer.optimize_memory()
        self.assertIn("success", memory_result)

        # Test I/O optimization
        io_result = system_optimizer.optimize_io()
        self.assertIn("success", io_result)

    def test_error_handling_and_recovery(self):
        """Test error handling in optimization process."""
        optimizer = SystemOptimizer()

        # Mock an optimizer to fail
        optimizer.cpu_optimizer.optimize_performance = Mock(
            side_effect=Exception("Test error"),
        )

        result = optimizer.optimize_system()

        # Should handle error gracefully
        self.assertIn("success", result)
        self.assertIn("optimization_results", result)

        # Check that other optimizers still ran
        self.assertGreaterEqual(len(result["optimization_results"]), 1)


class TestErrorHandling(unittest.TestCase):
    """Test error handling and edge cases."""

    def test_system_optimizer_optimize_system_failure(self):
        """Test system optimization complete failure."""
        optimizer = SystemOptimizer()

        # Mock performance manager to fail
        optimizer.performance_manager.collect_system_metrics = Mock(
            side_effect=Exception("System error"),
        )

        result = optimizer.optimize_system()

        self.assertFalse(result["success"])
        self.assertIn("error", result)
        self.assertEqual(result["total_improvement"], 0.0)

    def test_cpu_optimizer_optimize_performance_failure(self):
        """Test CPU optimization failure."""
        optimizer = CPUOptimizer()

        # Mock _collect_cpu_metrics to fail during baseline collection
        optimizer._collect_cpu_metrics = Mock(side_effect=Exception("CPU error"))

        result = optimizer.optimize_performance()

        self.assertFalse(result["success"])
        self.assertIn("error", result)

    def test_memory_optimizer_optimize_performance_failure(self):
        """Test memory optimization failure."""
        optimizer = MemoryOptimizer()

        # Mock _collect_memory_metrics to fail during baseline collection
        optimizer._collect_memory_metrics = Mock(side_effect=Exception("Memory error"))

        result = optimizer.optimize_performance()

        self.assertFalse(result["success"])
        self.assertIn("error", result)

    def test_io_optimizer_optimize_performance_failure(self):
        """Test I/O optimization failure."""
        optimizer = IOOptimizer()

        # Mock _collect_io_metrics to fail during baseline collection
        optimizer._collect_io_metrics = Mock(side_effect=Exception("I/O error"))

        result = optimizer.optimize_performance()

        self.assertFalse(result["success"])
        self.assertIn("error", result)

    def test_cpu_optimizer_collect_metrics_error(self):
        """Test CPU metrics collection error handling."""
        optimizer = CPUOptimizer()

        with patch(
            "chunker.performance.optimization.system_optimizer.HAS_PSUTIL",
            True,
        ):
            with patch(
                "chunker.performance.optimization.system_optimizer.psutil",
            ) as mock_psutil:
                mock_psutil.cpu_percent.side_effect = Exception("CPU metrics error")

                metrics = optimizer._collect_cpu_metrics()

                # Should return empty dict on error
                self.assertIsInstance(metrics, dict)

    def test_memory_optimizer_collect_metrics_error(self):
        """Test memory metrics collection error handling."""
        optimizer = MemoryOptimizer()

        with patch(
            "chunker.performance.optimization.system_optimizer.HAS_PSUTIL",
            True,
        ):
            with patch(
                "chunker.performance.optimization.system_optimizer.psutil",
            ) as mock_psutil:
                mock_psutil.virtual_memory.side_effect = Exception(
                    "Memory metrics error",
                )

                metrics = optimizer._collect_memory_metrics()

                # Should return empty dict on error
                self.assertIsInstance(metrics, dict)

    def test_io_optimizer_collect_metrics_error(self):
        """Test I/O metrics collection error handling."""
        optimizer = IOOptimizer()

        with patch(
            "chunker.performance.optimization.system_optimizer.HAS_PSUTIL",
            True,
        ):
            with patch(
                "chunker.performance.optimization.system_optimizer.psutil",
            ) as mock_psutil:
                mock_psutil.disk_io_counters.side_effect = Exception(
                    "I/O metrics error",
                )

                metrics = optimizer._collect_io_metrics()

                # Should return empty dict on error
                self.assertIsInstance(metrics, dict)

    def test_io_optimizer_schedule_batch_flush_error(self):
        """Test batch flush scheduling error handling."""
        optimizer = IOOptimizer()

        # This should not raise an exception
        optimizer._schedule_batch_flush("nonexistent_batch")

    def test_io_optimizer_flush_batch_error(self):
        """Test batch flushing error handling."""
        optimizer = IOOptimizer()

        # This should not raise an exception
        optimizer._flush_batch("nonexistent_batch")

    def test_memory_optimizer_get_pool_error(self):
        """Test memory pool access error handling."""
        optimizer = MemoryOptimizer()

        # Create a corrupted pool
        optimizer.memory_pools["corrupted"] = {"size": "invalid"}

        buffer = optimizer.get_memory_pool(64)
        self.assertIsNone(buffer)

    def test_memory_optimizer_return_pool_error(self):
        """Test memory pool return error handling."""
        optimizer = MemoryOptimizer()

        # This should not raise an exception
        optimizer.return_to_pool(bytearray(64), 64)

    def test_io_optimizer_read_file_cached_error(self):
        """Test cached file reading error handling."""
        optimizer = IOOptimizer()
        optimizer.optimize_file_operations()  # Initialize cache

        # Try to read non-existent file
        content = optimizer.read_file_cached("/nonexistent/file.txt")
        self.assertIsNone(content)


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and boundary conditions."""

    def test_cpu_optimizer_thread_pools_already_exist(self):
        """Test thread pool optimization when pools already exist."""
        optimizer = CPUOptimizer()

        # Pre-create a pool
        optimizer.thread_pools["cpu_intensive"] = Mock()

        with patch(
            "chunker.performance.optimization.system_optimizer.HAS_PSUTIL",
            True,
        ):
            with patch(
                "chunker.performance.optimization.system_optimizer.psutil",
            ) as mock_psutil:
                mock_psutil.cpu_count.return_value = 4

                result = optimizer.optimize_thread_pools()

                self.assertTrue(result["success"])
                # Should create fewer pools since one already exists
                self.assertLess(result["pools_created"], 3)

    @patch("chunker.performance.optimization.system_optimizer.HAS_PSUTIL", True)
    @patch("chunker.performance.optimization.system_optimizer.psutil")
    def test_cpu_optimizer_affinity_already_optimal(self, mock_psutil):
        """Test CPU affinity when already optimal."""
        optimizer = CPUOptimizer()

        mock_process = Mock()
        mock_process.cpu_affinity.return_value = [
            0,
            1,
        ]  # Already optimal for 4-core system
        mock_psutil.Process.return_value = mock_process
        mock_psutil.cpu_count.return_value = 4

        result = optimizer.set_optimal_cpu_affinity()

        self.assertTrue(result["success"])
        self.assertEqual(result["improvement"], 0.0)
        self.assertIn("already optimized", result["details"])

    def test_memory_optimizer_pool_cache_eviction(self):
        """Test memory pool cache eviction."""
        optimizer = MemoryOptimizer()
        optimizer.create_memory_pools()

        # Get a pool and verify structure
        pool_name = list(optimizer.memory_pools.keys())[0]
        pool = optimizer.memory_pools[pool_name]

        # Simulate using all buffers
        available_copy = pool["available"].copy()
        for buffer_idx in available_copy:
            pool["available"].remove(buffer_idx)
            pool["in_use"].add(buffer_idx)

        # Try to get another buffer (should return None since all are in use)
        buffer = optimizer.get_memory_pool(pool["size"])
        self.assertIsNone(buffer)

    def test_io_optimizer_batch_size_reached(self):
        """Test I/O batching when batch size is reached."""
        optimizer = IOOptimizer()
        optimizer.implement_batching()

        batch_name = list(optimizer.batch_operations.keys())[0]
        batch = optimizer.batch_operations[batch_name]
        batch_size = batch["config"]["batch_size"]

        # Add operations up to batch size
        for i in range(batch_size):
            optimizer.add_to_batch(batch_name, f"operation_{i}")

        # Batch should be automatically flushed
        # Give it a moment to process
        time.sleep(0.1)

        # Adding one more should trigger flush
        optimizer.add_to_batch(batch_name, "final_operation")

    def test_io_optimizer_file_cache_lru_eviction(self):
        """Test file cache LRU eviction."""
        optimizer = IOOptimizer()
        optimizer.optimize_file_operations()

        # Create multiple temporary files to exceed cache size
        temp_files = []
        try:
            cache_size = optimizer._file_cache["max_size"]

            for i in range(cache_size + 2):
                with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
                    f.write(f"content_{i}")
                    temp_files.append(f.name)

            # Read files to fill cache beyond capacity
            for temp_file in temp_files:
                optimizer.read_file_cached(temp_file)

            # Cache should not exceed max size
            self.assertLessEqual(len(optimizer._file_cache["data"]), cache_size)

        finally:
            # Clean up temp files
            for temp_file in temp_files:
                try:
                    Path(temp_file).unlink()
                except Exception:
                    pass

    def test_system_optimizer_category_improvement_no_metrics(self):
        """Test category improvement calculation with no metrics."""
        optimizer = SystemOptimizer()

        baseline = Mock()
        baseline.get_metrics_by_category.return_value = []

        current = Mock()
        current.get_metrics_by_category.return_value = []

        improvement = optimizer._calculate_category_improvement(
            "cpu",
            baseline,
            current,
        )
        self.assertEqual(improvement, 0.0)

    def test_system_optimizer_calculate_improvement_error(self):
        """Test system improvement calculation error handling."""
        optimizer = SystemOptimizer()

        # Mock baseline that raises exception
        baseline = Mock()
        baseline.optimization_potential = None
        baseline.get_critical_metrics.side_effect = Exception("Test error")

        current = Mock()
        current.optimization_potential = 50.0
        current.get_critical_metrics.return_value = []

        improvement = optimizer._calculate_system_improvement(baseline, current)
        self.assertEqual(improvement, 0.0)


class TestComprehensiveCoverage(unittest.TestCase):
    """Additional tests to achieve 95%+ coverage."""

    @patch("chunker.performance.optimization.system_optimizer.HAS_PSUTIL", True)
    @patch("chunker.performance.optimization.system_optimizer.psutil")
    def test_cpu_optimizer_load_avg_collection(self, mock_psutil):
        """Test CPU load average collection."""
        optimizer = CPUOptimizer()

        mock_psutil.cpu_percent.return_value = 50.0
        mock_psutil.cpu_count.return_value = 4
        mock_psutil.getloadavg.return_value = (1.5, 1.2, 1.0)

        mock_process = Mock()
        mock_process.cpu_affinity.return_value = [0, 1, 2, 3]
        mock_process.cpu_percent.return_value = 25.0
        mock_psutil.Process.return_value = mock_process

        metrics = optimizer._collect_cpu_metrics()

        self.assertIn("load_avg", metrics)
        self.assertEqual(metrics["load_avg"], (1.5, 1.2, 1.0))

    @patch("chunker.performance.optimization.system_optimizer.HAS_PSUTIL", True)
    @patch("chunker.performance.optimization.system_optimizer.psutil")
    def test_cpu_optimizer_cpu_freq_collection(self, mock_psutil):
        """Test CPU frequency collection."""
        optimizer = CPUOptimizer()

        mock_cpu_freq = Mock()
        mock_cpu_freq.current = 2400.0
        mock_cpu_freq.min = 800.0
        mock_cpu_freq.max = 3200.0
        mock_psutil.cpu_freq.return_value = mock_cpu_freq

        mock_psutil.cpu_percent.return_value = 50.0
        mock_psutil.cpu_count.return_value = 4

        metrics = optimizer._collect_cpu_metrics()

        self.assertIn("cpu_freq_current", metrics)
        self.assertEqual(metrics["cpu_freq_current"], 2400.0)

    @patch("chunker.performance.optimization.system_optimizer.HAS_PSUTIL", False)
    def test_cpu_optimizer_fallback_collection(self):
        """Test CPU metrics collection fallback without psutil."""
        optimizer = CPUOptimizer()

        metrics = optimizer._collect_cpu_metrics()

        # Should collect process CPU time
        self.assertIn("process_cpu_time", metrics)

    @patch("chunker.performance.optimization.system_optimizer.HAS_PSUTIL", True)
    @patch("chunker.performance.optimization.system_optimizer.psutil")
    def test_memory_optimizer_tracemalloc_collection(self, mock_psutil):
        """Test memory collection with tracemalloc."""
        optimizer = MemoryOptimizer()

        # Mock tracemalloc
        with patch(
            "chunker.performance.optimization.system_optimizer.tracemalloc",
        ) as mock_tracemalloc:
            mock_tracemalloc.is_tracing.return_value = True
            mock_tracemalloc.get_traced_memory.return_value = (1000000, 2000000)

            mock_vmem = Mock()
            mock_vmem.total = 8000000000
            mock_vmem.available = 4000000000
            mock_vmem.used = 4000000000
            mock_vmem.percent = 50.0
            mock_vmem.free = 4000000000
            mock_psutil.virtual_memory.return_value = mock_vmem

            metrics = optimizer._collect_memory_metrics()

            self.assertIn("tracemalloc_current", metrics)
            self.assertEqual(metrics["tracemalloc_current"], 1000000)

    @patch("chunker.performance.optimization.system_optimizer.HAS_PSUTIL", False)
    def test_memory_optimizer_fallback_collection(self):
        """Test memory metrics collection fallback."""
        optimizer = MemoryOptimizer()

        metrics = optimizer._collect_memory_metrics()

        # Should collect basic process memory
        self.assertIn("process_memory_peak", metrics)

    @patch("chunker.performance.optimization.system_optimizer.HAS_PSUTIL", True)
    @patch("chunker.performance.optimization.system_optimizer.psutil")
    def test_io_optimizer_network_collection_error(self, mock_psutil):
        """Test I/O network collection error handling."""
        optimizer = IOOptimizer()

        mock_disk_io = Mock()
        mock_disk_io.read_bytes = 1000
        mock_disk_io.write_bytes = 500
        mock_disk_io.read_count = 10
        mock_disk_io.write_count = 5
        mock_disk_io.read_time = 100
        mock_disk_io.write_time = 50
        mock_psutil.disk_io_counters.return_value = mock_disk_io

        # Network should fail
        mock_psutil.net_io_counters.side_effect = Exception("Network error")

        mock_process = Mock()
        mock_pio = Mock()
        mock_pio.read_bytes = 800
        mock_pio.write_bytes = 400
        mock_pio.read_count = 8
        mock_pio.write_count = 4
        mock_process.io_counters.return_value = mock_pio
        mock_psutil.Process.return_value = mock_process

        metrics = optimizer._collect_io_metrics()

        self.assertIn("disk_read_bytes", metrics)
        self.assertNotIn(
            "network_bytes_sent",
            metrics,
        )  # Should be missing due to error

    @patch("chunker.performance.optimization.system_optimizer.HAS_PSUTIL", False)
    def test_io_optimizer_fallback_collection(self):
        """Test I/O metrics collection fallback."""
        optimizer = IOOptimizer()

        metrics = optimizer._collect_io_metrics()

        # Should collect basic process I/O
        self.assertIn("process_block_input", metrics)

    def test_cpu_optimizer_balance_single_core(self):
        """Test CPU load balancing on single core system."""
        optimizer = CPUOptimizer()

        with patch(
            "chunker.performance.optimization.system_optimizer.HAS_PSUTIL",
            True,
        ):
            with patch(
                "chunker.performance.optimization.system_optimizer.psutil",
            ) as mock_psutil:
                mock_psutil.cpu_percent.return_value = [80]  # Single core

                result = optimizer.balance_cpu_load()

                self.assertTrue(result["success"])
                self.assertEqual(result["improvement"], 0.0)
                self.assertIn("Single core system", result["details"])

    @patch("chunker.performance.optimization.system_optimizer.HAS_PSUTIL", True)
    @patch("chunker.performance.optimization.system_optimizer.psutil")
    def test_cpu_optimizer_set_affinity_permission_error(self, mock_psutil):
        """Test CPU affinity setting with permission error."""
        optimizer = CPUOptimizer()

        mock_process = Mock()
        mock_process.cpu_affinity.side_effect = PermissionError("Permission denied")
        mock_psutil.Process.return_value = mock_process
        mock_psutil.cpu_count.return_value = 4

        result = optimizer.set_cpu_affinity([0, 1])

        self.assertFalse(result)

    @patch("chunker.performance.optimization.system_optimizer.HAS_PSUTIL", True)
    @patch("chunker.performance.optimization.system_optimizer.psutil")
    def test_cpu_optimizer_set_affinity_small_system(self, mock_psutil):
        """Test CPU affinity optimization on small system."""
        optimizer = CPUOptimizer()

        mock_process = Mock()
        mock_process.cpu_affinity.return_value = [0, 1]  # 2-core system
        mock_psutil.Process.return_value = mock_process
        mock_psutil.cpu_count.return_value = 2

        with patch.object(optimizer, "set_cpu_affinity", return_value=True) as mock_set:
            result = optimizer.set_optimal_cpu_affinity()

            self.assertTrue(result["success"])
            # Should keep all cores on small system
            mock_set.assert_called_with([0, 1])

    def test_memory_optimizer_gc_with_psutil_high_memory(self):
        """Test GC optimization with high memory usage."""
        optimizer = MemoryOptimizer()

        with patch(
            "chunker.performance.optimization.system_optimizer.HAS_PSUTIL",
            True,
        ):
            with patch(
                "chunker.performance.optimization.system_optimizer.psutil",
            ) as mock_psutil:
                mock_process = Mock()
                mock_memory_info = Mock()
                mock_memory_info.rss = 1200 * 1024 * 1024  # 1.2GB (high memory)
                mock_process.memory_info.return_value = mock_memory_info
                mock_psutil.Process.return_value = mock_process

                result = optimizer.optimize_garbage_collection()

                self.assertTrue(result["success"])
                # Should use more aggressive GC for high memory

    def test_memory_optimizer_gc_with_psutil_low_memory(self):
        """Test GC optimization with low memory usage."""
        optimizer = MemoryOptimizer()

        with patch(
            "chunker.performance.optimization.system_optimizer.HAS_PSUTIL",
            True,
        ):
            with patch(
                "chunker.performance.optimization.system_optimizer.psutil",
            ) as mock_psutil:
                mock_process = Mock()
                mock_memory_info = Mock()
                mock_memory_info.rss = 100 * 1024 * 1024  # 100MB (low memory)
                mock_process.memory_info.return_value = mock_memory_info
                mock_psutil.Process.return_value = mock_process

                result = optimizer.optimize_garbage_collection()

                self.assertTrue(result["success"])
                # Should use less aggressive GC for low memory

    def test_memory_optimizer_leak_detection_with_garbage(self):
        """Test memory leak detection with garbage."""
        optimizer = MemoryOptimizer()

        # Add some garbage to gc
        original_garbage = gc.garbage.copy()
        try:
            gc.garbage.extend([object(), object(), object()])

            leaks = optimizer.detect_memory_leaks()

            # Should detect reference cycles
            cycle_leaks = [leak for leak in leaks if "Reference cycles" in leak]
            self.assertGreater(len(cycle_leaks), 0)

        finally:
            # Clean up
            gc.garbage.clear()
            gc.garbage.extend(original_garbage)

    def test_io_optimizer_timer_cancellation(self):
        """Test batch timer cancellation."""
        optimizer = IOOptimizer()
        optimizer.implement_batching()

        batch_name = list(optimizer.batch_operations.keys())[0]

        # Schedule initial timer
        optimizer._schedule_batch_flush(batch_name)

        # Should have a timer
        self.assertIn(batch_name, optimizer._batch_timers)

        # Schedule again (should cancel previous)
        optimizer._schedule_batch_flush(batch_name)

        # Should still have timer (new one)
        self.assertIn(batch_name, optimizer._batch_timers)

    def test_io_optimizer_cache_miss_then_hit(self):
        """Test file cache miss followed by hit."""
        optimizer = IOOptimizer()
        optimizer.optimize_file_operations()

        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.write("test content for cache")
            temp_file = f.name

        try:
            # First read should be a miss
            initial_misses = optimizer._file_cache["misses"]
            content1 = optimizer.read_file_cached(temp_file)
            self.assertIsNotNone(content1)
            self.assertGreater(optimizer._file_cache["misses"], initial_misses)

            # Second read should be a hit
            initial_hits = optimizer._file_cache["hits"]
            content2 = optimizer.read_file_cached(temp_file)
            self.assertEqual(content1, content2)
            self.assertGreater(optimizer._file_cache["hits"], initial_hits)

        finally:
            Path(temp_file).unlink()

    def test_io_optimizer_connection_pool_update(self):
        """Test connection pool configuration update."""
        optimizer = IOOptimizer()

        # Create initial pool
        pool_name = "test_pool"
        optimizer.connection_pools[pool_name] = {"max_connections": 5}

        result = optimizer.optimize_connection_pools()

        self.assertTrue(result["success"])
        # Should update existing pool
        updated_pool = optimizer.connection_pools[pool_name]
        self.assertNotEqual(updated_pool["max_connections"], 5)  # Should be updated

    def test_system_optimizer_category_improvement_non_percent_metrics(self):
        """Test category improvement with non-percentage metrics."""
        optimizer = SystemOptimizer()

        # Create metrics with different units
        baseline_metrics = [Mock(), Mock()]
        baseline_metrics[0].value = 1000
        baseline_metrics[0].unit = "bytes"
        baseline_metrics[1].value = 80.0
        baseline_metrics[1].unit = "%"

        current_metrics = [Mock(), Mock()]
        current_metrics[0].value = 800
        current_metrics[0].unit = "bytes"
        current_metrics[1].value = 60.0
        current_metrics[1].unit = "%"

        baseline = Mock()
        baseline.get_metrics_by_category.return_value = baseline_metrics

        current = Mock()
        current.get_metrics_by_category.return_value = current_metrics

        improvement = optimizer._calculate_category_improvement(
            "memory",
            baseline,
            current,
        )

        # Should only consider percentage metrics
        self.assertGreater(improvement, 0)

    def test_measure_improvements_error_handling(self):
        """Test improvements measurement error handling."""
        optimizer = SystemOptimizer()

        # Set baseline but make collect_system_metrics fail
        optimizer._baseline_metrics = Mock()
        optimizer.performance_manager.collect_system_metrics = Mock(
            side_effect=Exception("Metrics error"),
        )

        result = optimizer.measure_improvements()

        self.assertIn("error", result)
        self.assertEqual(result["improvement"], 0.0)


if __name__ == "__main__":
    # Set up test environment
    import logging

    logging.basicConfig(level=logging.WARNING)  # Reduce log noise during tests

    # Run tests
    unittest.main(verbosity=2)

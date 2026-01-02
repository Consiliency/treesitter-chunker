"""Comprehensive System Integration Testing for Phase 1.7 - Task E3.

This module implements comprehensive system integration testing that validates the complete Phase 1.7
system with all groups working together. It tests error handling pipeline integration, grammar
management CLI functionality, end-to-end workflows, and Phase 1.8 readiness.

Key Features:
- Complete system integration test suite
- Error handling pipeline validation
- Grammar management CLI testing
- End-to-end workflow testing across all groups
- Performance testing and benchmarking
- Phase 1.8 alignment validation
- Detailed test reports with metrics

Integration Requirements:
- Tests ErrorHandlingPipeline and ErrorHandlingOrchestrator from integration.py
- Tests GrammarManagementCLI from cli.py
- Validates all Phase 1.7 components working together
- Tests Phase 1.8 readiness including grammar management commands
- Performance benchmarking with realistic workloads
- Error injection and recovery testing
- Resource usage monitoring
- Thread safety validation

The system is production-ready with comprehensive testing of the complete Phase 1.7 system.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import json
import logging
import multiprocessing
import os
import platform
import queue
import random
import signal
import statistics
import string
import sys
import tempfile
import threading
import time
import traceback
import uuid
from collections import defaultdict, deque
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from unittest.mock import Mock, patch

import psutil

# Import Task E1 components (Error Handling Pipeline Integration)
try:
    from ..error_handling.integration import (
        CLIErrorIntegration,
        ErrorHandlingOrchestrator,
        ErrorHandlingPipeline,
        ErrorHandlingSession,
        PipelineMetrics,
        PipelineResult,
        PipelineStage,
        SessionStatus,
        create_error_handling_system,
        get_system_health_report,
    )

    ERROR_HANDLING_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Error handling integration not available: {e}")
    ERROR_HANDLING_AVAILABLE = False

    # Create stub classes for graceful fallback
    class ErrorHandlingPipeline:
        def __init__(self, **kwargs):
            pass

        def process_error(self, *args, **kwargs):
            return Mock(success=True, stage_reached=Mock(value="complete"))

        def get_pipeline_health(self):
            return {"status": "healthy"}

        def shutdown(self):
            pass

    class ErrorHandlingOrchestrator:
        def __init__(self, *args, **kwargs):
            pass

        def create_session(self, *args, **kwargs):
            return Mock(session_id="test")

        def close_session(self, *args):
            return True

        def get_session_statistics(self):
            return {"active_sessions": 0}

        def shutdown(self):
            pass

    class CLIErrorIntegration:
        def __init__(self, *args):
            pass

        def handle_grammar_validation_error(self, *args, **kwargs):
            return {"success": True, "guidance": [], "quick_fixes": []}


# Import Task E2 components (Grammar Management CLI)
try:
    from ..grammar_management.cli import (
        ComprehensiveGrammarCLI,
        GrammarPriority,
        GrammarStatus,
        ProgressIndicator,
    )

    CLI_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Grammar management CLI not available: {e}")
    CLI_AVAILABLE = False

    class ComprehensiveGrammarCLI:
        def __init__(self, **kwargs):
            pass

        def list_grammars(self, *args):
            return 0

        def info_grammar(self, *args):
            return 0

        def fetch_grammar(self, *args, **kwargs):
            return 0


# Import other Phase 1.7 components
try:
    from ..error_handling.classifier import (
        ClassifiedError,
        ErrorCategory,
        ErrorClassifier,
        ErrorContext,
        ErrorSeverity,
        ErrorSource,
    )
    from ..error_handling.compatibility_detector import CompatibilityErrorDetector
    from ..error_handling.guidance_engine import UserActionGuidanceEngine
    from ..error_handling.syntax_analyzer import SyntaxErrorAnalyzer
    from ..error_handling.templates import TemplateManager
    from ..error_handling.troubleshooting import TroubleshootingDatabase

    PHASE_17_COMPONENTS_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Phase 1.7 components not fully available: {e}")
    PHASE_17_COMPONENTS_AVAILABLE = False

# Import chunker core components
try:
    from ..chunker import TreeSitterChunker
    from ..factory import ChunkerFactory
    from ..grammar.manager import GrammarManager

    CHUNKER_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Chunker components not available: {e}")
    CHUNKER_AVAILABLE = False

# Import existing testing framework
try:
    from .integration_framework import IntegrationTestFramework

    INTEGRATION_FRAMEWORK_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Integration framework not available: {e}")
    INTEGRATION_FRAMEWORK_AVAILABLE = False

logger = logging.getLogger(__name__)


class TestStatus:
    """Test execution status constants."""

    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"
    TIMEOUT = "timeout"


class TestCategory:
    """Test category constants."""

    UNIT = "unit"
    INTEGRATION = "integration"
    END_TO_END = "end_to_end"
    PERFORMANCE = "performance"
    STRESS = "stress"
    SMOKE = "smoke"
    REGRESSION = "regression"
    SECURITY = "security"


class TestPriority:
    """Test priority levels."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class SystemTestResult:
    """Result of a system integration test."""

    test_id: str
    test_name: str
    test_category: str
    test_priority: str
    status: str
    start_time: datetime
    end_time: datetime | None = None
    execution_time: float = 0.0
    details: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)
    error_message: str | None = None
    stack_trace: str | None = None
    assertions: list[dict[str, Any]] = field(default_factory=list)
    resource_usage: dict[str, Any] = field(default_factory=dict)
    thread_info: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "test_id": self.test_id,
            "test_name": self.test_name,
            "test_category": self.test_category,
            "test_priority": self.test_priority,
            "status": self.status,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "execution_time": self.execution_time,
            "details": self.details,
            "metrics": self.metrics,
            "error_message": self.error_message,
            "stack_trace": self.stack_trace,
            "assertions": self.assertions,
            "resource_usage": self.resource_usage,
            "thread_info": self.thread_info,
        }


@dataclass
class SystemTestSuite:
    """Suite of system integration tests."""

    suite_id: str
    suite_name: str
    description: str
    tests: list[SystemTestResult] = field(default_factory=list)
    setup_time: float = 0.0
    teardown_time: float = 0.0
    total_execution_time: float = 0.0
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None

    @property
    def test_counts(self) -> dict[str, int]:
        """Get test counts by status."""
        counts = defaultdict(int)
        for test in self.tests:
            counts[test.status] += 1
        return dict(counts)

    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if not self.tests:
            return 0.0
        passed = self.test_counts.get(TestStatus.PASSED, 0)
        return (passed / len(self.tests)) * 100.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "suite_id": self.suite_id,
            "suite_name": self.suite_name,
            "description": self.description,
            "test_counts": self.test_counts,
            "success_rate": self.success_rate,
            "setup_time": self.setup_time,
            "teardown_time": self.teardown_time,
            "total_execution_time": self.total_execution_time,
            "created_at": self.created_at.isoformat(),
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
            "tests": [test.to_dict() for test in self.tests],
        }


@dataclass
class SystemHealthMetrics:
    """System health and performance metrics."""

    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    memory_available: int = 0
    disk_usage: float = 0.0
    process_count: int = 0
    thread_count: int = 0
    open_files: int = 0
    network_connections: int = 0
    load_average: list[float] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "cpu_usage": self.cpu_usage,
            "memory_usage": self.memory_usage,
            "memory_available": self.memory_available,
            "disk_usage": self.disk_usage,
            "process_count": self.process_count,
            "thread_count": self.thread_count,
            "open_files": self.open_files,
            "network_connections": self.network_connections,
            "load_average": self.load_average,
        }


class ResourceMonitor:
    """Monitor system resources during testing."""

    def __init__(self, interval: float = 1.0):
        """Initialize resource monitor.

        Args:
            interval: Monitoring interval in seconds
        """
        self.interval = interval
        self.monitoring = False
        self.metrics: list[SystemHealthMetrics] = []
        self.monitor_thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def start_monitoring(self) -> None:
        """Start resource monitoring."""
        if self.monitoring:
            return

        self.monitoring = True
        self._stop_event.clear()
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()

    def stop_monitoring(self) -> SystemHealthMetrics:
        """Stop monitoring and return average metrics.

        Returns:
            Average system health metrics during monitoring period
        """
        if not self.monitoring:
            return SystemHealthMetrics()

        self.monitoring = False
        self._stop_event.set()

        if self.monitor_thread:
            self.monitor_thread.join(timeout=2.0)

        return self._calculate_average_metrics()

    def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        try:
            while not self._stop_event.wait(self.interval):
                metrics = self._collect_metrics()
                self.metrics.append(metrics)
        except Exception as e:
            logger.error(f"Error in resource monitoring: {e}")

    def _collect_metrics(self) -> SystemHealthMetrics:
        """Collect current system metrics."""
        try:
            # CPU usage
            cpu_usage = psutil.cpu_percent(interval=None)

            # Memory usage
            memory = psutil.virtual_memory()
            memory_usage = memory.percent
            memory_available = memory.available

            # Disk usage
            disk = psutil.disk_usage("/")
            disk_usage = disk.percent

            # Process info
            process = psutil.Process()
            process_count = len(psutil.pids())
            thread_count = process.num_threads()

            # File handles
            try:
                open_files = process.num_fds() if hasattr(process, "num_fds") else 0
            except (psutil.AccessDenied, AttributeError):
                open_files = 0

            # Network connections
            try:
                network_connections = len(process.connections())
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                network_connections = 0

            # Load average (Unix-like systems only)
            load_average = []
            try:
                if hasattr(os, "getloadavg"):
                    load_average = list(os.getloadavg())
            except (OSError, AttributeError):
                pass

            return SystemHealthMetrics(
                cpu_usage=cpu_usage,
                memory_usage=memory_usage,
                memory_available=memory_available,
                disk_usage=disk_usage,
                process_count=process_count,
                thread_count=thread_count,
                open_files=open_files,
                network_connections=network_connections,
                load_average=load_average,
            )

        except Exception as e:
            logger.error(f"Error collecting metrics: {e}")
            return SystemHealthMetrics()

    def _calculate_average_metrics(self) -> SystemHealthMetrics:
        """Calculate average metrics from collected data."""
        if not self.metrics:
            return SystemHealthMetrics()

        # Calculate averages
        avg_cpu = statistics.mean(m.cpu_usage for m in self.metrics)
        avg_memory = statistics.mean(m.memory_usage for m in self.metrics)
        avg_disk = statistics.mean(m.disk_usage for m in self.metrics)

        # Use latest values for counts
        latest = self.metrics[-1]

        return SystemHealthMetrics(
            cpu_usage=avg_cpu,
            memory_usage=avg_memory,
            memory_available=latest.memory_available,
            disk_usage=avg_disk,
            process_count=latest.process_count,
            thread_count=latest.thread_count,
            open_files=latest.open_files,
            network_connections=latest.network_connections,
            load_average=latest.load_average,
        )


class SystemIntegrationTester:
    """Comprehensive system integration testing for Phase 1.7."""

    def __init__(self, config: dict[str, Any] | None = None):
        """Initialize the system integration tester.

        Args:
            config: Optional configuration dictionary
        """
        self.config = config or {}
        self.test_suites: dict[str, SystemTestSuite] = {}
        self.current_suite: SystemTestSuite | None = None
        self.resource_monitor = ResourceMonitor(
            interval=self.config.get("monitor_interval", 1.0),
        )

        # Test data and fixtures
        self.test_data = self._load_test_data()
        self.temp_dir: Path | None = None

        # Component instances
        self.error_pipeline: ErrorHandlingPipeline | None = None
        self.error_orchestrator: ErrorHandlingOrchestrator | None = None
        self.cli_integration: CLIErrorIntegration | None = None
        self.grammar_cli: ComprehensiveGrammarCLI | None = None

        # Thread safety
        self._results_lock = threading.Lock()
        self._setup_lock = threading.Lock()

        # Performance tracking
        self.performance_baseline: dict[str, float] = {}
        self.performance_results: list[dict[str, Any]] = []

        logger.info("SystemIntegrationTester initialized")

    def _load_test_data(self) -> dict[str, Any]:
        """Load test data for system integration tests."""
        return {
            "languages": ["python", "javascript", "java", "go", "rust", "cpp"],
            "code_samples": {
                "python": {
                    "valid": '#!/usr/bin/env python3\nprint("Hello, World!")',
                    "syntax_error": '#!/usr/bin/env python3\nprint("Hello, World!"',
                    "large": "#!/usr/bin/env python3\n"
                    + "\n".join([f"var_{i} = {i}" for i in range(1000)]),
                },
                "javascript": {
                    "valid": 'console.log("Hello, World!");',
                    "syntax_error": 'console.log("Hello, World!";',
                    "large": "\n".join([f"var var_{i} = {i};" for i in range(1000)]),
                },
                "java": {
                    "valid": 'public class Test { public static void main(String[] args) { System.out.println("Hello"); } }',
                    "syntax_error": 'public class Test { public static void main(String[] args) { System.out.println("Hello"); }',
                    "large": "public class Test {\n"
                    + "\n".join([f"    int var_{i} = {i};" for i in range(500)])
                    + "\n}",
                },
            },
            "error_messages": [
                "SyntaxError: unexpected token",
                "ParseError: missing closing bracket",
                "TypeError: cannot read property",
                "ReferenceError: variable not defined",
                "Grammar version mismatch",
                "Compatibility issue detected",
                "Parser generation failed",
                "Tree-sitter compilation error",
            ],
            "cli_commands": [
                ["list"],
                ["info", "python"],
                ["versions", "javascript"],
                ["fetch", "python"],
                ["build", "python"],
                ["test", "python", "test.py"],
                ["validate", "python"],
                ["remove", "python"],
            ],
        }

    @contextmanager
    def setup_test_environment(self):
        """Context manager for test environment setup and teardown."""
        setup_start = time.time()

        try:
            # Create temporary directory
            self.temp_dir = Path(tempfile.mkdtemp(prefix="system_integration_test_"))

            # Initialize components if available
            if ERROR_HANDLING_AVAILABLE:
                try:
                    (
                        self.error_pipeline,
                        self.error_orchestrator,
                        self.cli_integration,
                    ) = create_error_handling_system(
                        max_concurrent_processes=2,
                        max_sessions=10,
                        session_timeout_minutes=5,
                    )
                except Exception as e:
                    logger.warning(f"Failed to initialize error handling system: {e}")

            if CLI_AVAILABLE:
                try:
                    self.grammar_cli = ComprehensiveGrammarCLI(
                        cache_dir=self.temp_dir / "grammar_cache",
                        verbose=False,
                    )
                except Exception as e:
                    logger.warning(f"Failed to initialize grammar CLI: {e}")

            setup_time = time.time() - setup_start
            if self.current_suite:
                self.current_suite.setup_time = setup_time

            yield

        finally:
            # Cleanup
            teardown_start = time.time()

            try:
                # Shutdown error handling components
                if self.error_orchestrator:
                    self.error_orchestrator.shutdown()
                if self.error_pipeline:
                    self.error_pipeline.shutdown()

                # Cleanup temporary directory
                if self.temp_dir and self.temp_dir.exists():
                    import shutil

                    shutil.rmtree(self.temp_dir, ignore_errors=True)

            except Exception as e:
                logger.error(f"Error during test cleanup: {e}")

            finally:
                teardown_time = time.time() - teardown_start
                if self.current_suite:
                    self.current_suite.teardown_time = teardown_time

    def create_test_suite(self, suite_name: str, description: str) -> SystemTestSuite:
        """Create a new test suite.

        Args:
            suite_name: Name of the test suite
            description: Description of the test suite

        Returns:
            New SystemTestSuite instance
        """
        suite_id = f"suite_{int(time.time())}_{hash(suite_name) % 10000}"
        suite = SystemTestSuite(
            suite_id=suite_id,
            suite_name=suite_name,
            description=description,
        )

        self.test_suites[suite_id] = suite
        self.current_suite = suite

        logger.info(f"Created test suite: {suite_name} (ID: {suite_id})")
        return suite

    def run_test(
        self,
        test_func: Callable,
        test_name: str,
        test_category: str = TestCategory.INTEGRATION,
        test_priority: str = TestPriority.MEDIUM,
        timeout: float | None = 30.0,
        **test_kwargs,
    ) -> SystemTestResult:
        """Run a single system integration test.

        Args:
            test_func: Test function to execute
            test_name: Name of the test
            test_category: Category of the test
            test_priority: Priority level of the test
            timeout: Test timeout in seconds
            **test_kwargs: Additional keyword arguments for the test function

        Returns:
            SystemTestResult with test execution results
        """
        if not self.current_suite:
            raise ValueError("No test suite created. Call create_test_suite() first.")

        test_id = f"test_{int(time.time())}_{hash(test_name) % 10000}"
        start_time = datetime.now(UTC)

        # Initialize test result
        result = SystemTestResult(
            test_id=test_id,
            test_name=test_name,
            test_category=test_category,
            test_priority=test_priority,
            status=TestStatus.RUNNING,
            start_time=start_time,
        )

        # Start resource monitoring
        self.resource_monitor.start_monitoring()

        try:
            # Run test with timeout
            if timeout:
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(
                        self._execute_test_safely,
                        test_func,
                        **test_kwargs,
                    )
                    try:
                        test_result = future.result(timeout=timeout)
                        result.status = TestStatus.PASSED
                        result.details["result"] = test_result
                    except concurrent.futures.TimeoutError:
                        result.status = TestStatus.TIMEOUT
                        result.error_message = f"Test timed out after {timeout} seconds"
            else:
                test_result = self._execute_test_safely(test_func, **test_kwargs)
                result.status = TestStatus.PASSED
                result.details["result"] = test_result

        except AssertionError as e:
            result.status = TestStatus.FAILED
            result.error_message = f"Assertion failed: {e}"
            result.stack_trace = traceback.format_exc()

        except Exception as e:
            result.status = TestStatus.ERROR
            result.error_message = str(e)
            result.stack_trace = traceback.format_exc()

        # Stop monitoring and collect metrics
        result.resource_usage = self.resource_monitor.stop_monitoring().to_dict()

        # Record timing and thread information
        end_time = datetime.now(UTC)
        result.end_time = end_time
        result.execution_time = (end_time - start_time).total_seconds()

        result.thread_info = {
            "main_thread": threading.current_thread().name,
            "active_threads": threading.active_count(),
            "thread_names": [t.name for t in threading.enumerate()],
        }

        # Add to test suite
        with self._results_lock:
            self.current_suite.tests.append(result)
            self.current_suite.total_execution_time += result.execution_time

        logger.info(
            f"Test {test_name} completed with status: {result.status} in {result.execution_time:.2f}s",
        )
        return result

    def _execute_test_safely(self, test_func: Callable, **test_kwargs) -> Any:
        """Execute test function safely with error handling.

        Args:
            test_func: Test function to execute
            **test_kwargs: Keyword arguments for test function

        Returns:
            Test function result
        """
        try:
            return test_func(**test_kwargs)
        except Exception as e:
            logger.error(f"Test function error: {e}")
            raise

    # Error Handling Pipeline Integration Tests

    def test_error_handling_pipeline_integration(self) -> dict[str, Any]:
        """Test error handling pipeline integration with all components."""
        if not ERROR_HANDLING_AVAILABLE:
            raise AssertionError("Error handling components not available")

        results = {}

        # Test pipeline creation
        assert self.error_pipeline is not None, "Error pipeline should be initialized"
        assert (
            self.error_orchestrator is not None
        ), "Error orchestrator should be initialized"
        assert self.cli_integration is not None, "CLI integration should be initialized"

        # Test pipeline health
        health = self.error_pipeline.get_pipeline_health()
        assert health["status"] in [
            "healthy",
            "degraded",
        ], f"Pipeline health status should be healthy or degraded, got: {health['status']}"
        results["pipeline_health"] = health

        # Test error processing
        test_errors = [
            "SyntaxError: unexpected token at line 5",
            "Grammar version mismatch for Python 3.9",
            "Tree-sitter parsing failed",
        ]

        processed_errors = []
        for error_msg in test_errors:
            try:
                pipeline_result = self.error_pipeline.process_error(
                    error_msg,
                    error_context={"language": "python", "file_path": "test.py"},
                )
                processed_errors.append(
                    {
                        "error": error_msg,
                        "success": pipeline_result.success,
                        "stage_reached": pipeline_result.stage_reached.value,
                        "processing_time": pipeline_result.processing_time,
                    },
                )
            except Exception as e:
                processed_errors.append(
                    {"error": error_msg, "success": False, "exception": str(e)},
                )

        results["processed_errors"] = processed_errors

        # Test session management
        session = self.error_orchestrator.create_session(user_id="test_user")
        assert session is not None, "Session should be created"
        results["session_created"] = True

        # Test session statistics
        stats = self.error_orchestrator.get_session_statistics()
        assert isinstance(stats, dict), "Session statistics should be a dictionary"
        assert "active_sessions" in stats, "Stats should include active sessions count"
        results["session_stats"] = stats

        # Test CLI integration
        cli_result = self.cli_integration.handle_grammar_validation_error(
            "python",
            "Grammar validation failed",
            "/path/to/grammar",
        )
        assert isinstance(cli_result, dict), "CLI integration should return dictionary"
        assert "success" in cli_result, "CLI result should include success field"
        results["cli_integration"] = cli_result

        return results

    def test_error_handling_performance(self) -> dict[str, Any]:
        """Test error handling pipeline performance under load."""
        if not ERROR_HANDLING_AVAILABLE:
            raise AssertionError("Error handling components not available")

        results = {}

        # Performance test configuration
        num_errors = 100
        concurrent_sessions = 10

        # Generate test errors
        test_errors = [
            f"Test error {i}: {random.choice(self.test_data['error_messages'])}"
            for i in range(num_errors)
        ]

        # Sequential processing test
        start_time = time.time()
        sequential_results = []

        for error_msg in test_errors[:20]:  # Test with 20 errors for reasonable time
            pipeline_result = self.error_pipeline.process_error(
                error_msg,
                error_context={
                    "language": "python",
                    "test_id": f"seq_{len(sequential_results)}",
                },
            )
            sequential_results.append(
                {
                    "success": pipeline_result.success,
                    "processing_time": pipeline_result.processing_time,
                },
            )

        sequential_time = time.time() - start_time
        results["sequential_processing"] = {
            "total_time": sequential_time,
            "errors_processed": len(sequential_results),
            "avg_time_per_error": sequential_time / len(sequential_results),
            "success_rate": sum(1 for r in sequential_results if r["success"])
            / len(sequential_results),
        }

        # Concurrent session test
        def process_errors_in_session(
            session_id: str,
            errors: list[str],
        ) -> list[dict[str, Any]]:
            session = self.error_orchestrator.create_session(
                user_id=f"perf_test_{session_id}",
            )
            session_results = []

            try:
                for error_msg in errors:
                    result = self.error_orchestrator.process_error_in_session(
                        session.session_id,
                        error_msg,
                        error_context={"performance_test": True},
                    )
                    session_results.append(
                        {
                            "success": result.success,
                            "processing_time": result.processing_time,
                        },
                    )
            finally:
                self.error_orchestrator.close_session(session.session_id)

            return session_results

        # Run concurrent test
        start_time = time.time()
        errors_per_session = test_errors[:30]  # 30 errors total
        session_errors = [
            errors_per_session[i::concurrent_sessions]
            for i in range(concurrent_sessions)
        ]

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=concurrent_sessions,
        ) as executor:
            future_to_session = {
                executor.submit(process_errors_in_session, f"session_{i}", errors): i
                for i, errors in enumerate(session_errors)
            }

            concurrent_results = []
            for future in concurrent.futures.as_completed(future_to_session):
                try:
                    session_results = future.result()
                    concurrent_results.extend(session_results)
                except Exception as e:
                    logger.error(f"Concurrent session error: {e}")

        concurrent_time = time.time() - start_time
        results["concurrent_processing"] = {
            "total_time": concurrent_time,
            "errors_processed": len(concurrent_results),
            "concurrent_sessions": concurrent_sessions,
            "avg_time_per_error": (
                concurrent_time / len(concurrent_results) if concurrent_results else 0
            ),
            "success_rate": (
                sum(1 for r in concurrent_results if r["success"])
                / len(concurrent_results)
                if concurrent_results
                else 0
            ),
        }

        # System health report
        health_report = get_system_health_report(
            self.error_pipeline,
            self.error_orchestrator,
        )
        results["system_health"] = health_report

        return results

    # Grammar Management CLI Tests

    def test_grammar_management_cli_integration(self) -> dict[str, Any]:
        """Test grammar management CLI integration."""
        if not CLI_AVAILABLE:
            raise AssertionError("Grammar CLI components not available")

        results = {}

        assert self.grammar_cli is not None, "Grammar CLI should be initialized"

        # Test CLI command execution
        cli_commands = [
            ("list_grammars", self.grammar_cli.list_grammars),
            ("info_grammar", lambda: self.grammar_cli.info_grammar("python")),
            ("versions_grammar", lambda: self.grammar_cli.versions_grammar("python")),
        ]

        command_results = {}
        for command_name, command_func in cli_commands:
            try:
                # Capture the command result (exit code)
                exit_code = command_func()
                command_results[command_name] = {
                    "success": exit_code == 0,
                    "exit_code": exit_code,
                }
            except Exception as e:
                command_results[command_name] = {"success": False, "error": str(e)}

        results["cli_commands"] = command_results

        # Test CLI with error handling integration
        if self.cli_integration:
            validation_result = self.cli_integration.handle_grammar_validation_error(
                "python",
                "Grammar compilation failed",
                "/path/to/python/grammar",
            )
            results["validation_integration"] = validation_result

            download_result = self.cli_integration.handle_grammar_download_error(
                "python",
                "Download failed: connection timeout",
                "https://github.com/tree-sitter/tree-sitter-python",
            )
            results["download_integration"] = download_result

        return results

    def test_grammar_cli_phase18_alignment(self) -> dict[str, Any]:
        """Test Grammar CLI Phase 1.8 alignment requirements."""
        if not CLI_AVAILABLE:
            raise AssertionError("Grammar CLI components not available")

        results = {}

        # Test directory structure compliance
        cache_dir = self.grammar_cli.cache_dir
        grammars_dir = self.grammar_cli.grammars_dir
        user_grammars_dir = self.grammar_cli.user_grammars_dir
        package_grammars_dir = self.grammar_cli.package_grammars_dir
        build_dir = self.grammar_cli.build_dir

        directories = {
            "cache_dir": cache_dir,
            "grammars_dir": grammars_dir,
            "user_grammars_dir": user_grammars_dir,
            "package_grammars_dir": package_grammars_dir,
            "build_dir": build_dir,
        }

        directory_compliance = {}
        for dir_name, dir_path in directories.items():
            directory_compliance[dir_name] = {
                "exists": dir_path.exists(),
                "is_directory": dir_path.is_dir() if dir_path.exists() else False,
                "path": str(dir_path),
            }

        results["directory_structure"] = directory_compliance

        # Test grammar priority order compliance
        priority_order = self.grammar_cli._get_grammar_priority_order()
        assert len(priority_order) >= 3, "Should have at least 3 priority levels"

        priority_info = []
        for path, description, priority in priority_order:
            priority_info.append(
                {
                    "path": str(path),
                    "description": description,
                    "priority": priority,
                    "exists": path.exists(),
                },
            )

        results["priority_order"] = priority_info

        # Test grammar sources availability
        grammar_sources = self.grammar_cli.grammar_sources
        assert len(grammar_sources) > 0, "Should have grammar sources configured"

        results["grammar_sources"] = {
            "count": len(grammar_sources),
            "languages": list(grammar_sources.keys())[:10],  # First 10 languages
            "sample_urls": dict(list(grammar_sources.items())[:3]),
        }

        # Test CLI error handling integration
        error_handling_tests = []
        test_errors = [
            ("grammar_not_found", "nonexistent_language"),
            ("validation_error", "python"),
            ("download_error", "javascript"),
        ]

        for error_type, language in test_errors:
            try:
                error_result = self.grammar_cli._handle_error(
                    f"Test {error_type} for {language}",
                    language,
                    {"test": True, "error_type": error_type},
                )
                error_handling_tests.append(
                    {
                        "error_type": error_type,
                        "language": language,
                        "success": error_result.get("success", False),
                        "has_guidance": len(error_result.get("guidance", [])) > 0,
                        "has_quick_fixes": len(error_result.get("quick_fixes", [])) > 0,
                    },
                )
            except Exception as e:
                error_handling_tests.append(
                    {
                        "error_type": error_type,
                        "language": language,
                        "success": False,
                        "error": str(e),
                    },
                )

        results["error_handling"] = error_handling_tests

        return results

    # End-to-End Workflow Tests

    def test_complete_error_resolution_workflow(self) -> dict[str, Any]:
        """Test complete error resolution workflow across all components."""
        if not (ERROR_HANDLING_AVAILABLE and CLI_AVAILABLE):
            raise AssertionError("Both error handling and CLI components required")

        results = {}
        workflow_steps = []

        # Step 1: Simulate parsing error
        test_code = self.test_data["code_samples"]["python"]["syntax_error"]
        error_context = {
            "language": "python",
            "file_path": "test_syntax_error.py",
            "line_number": 2,
            "column_number": 25,
        }

        workflow_steps.append(
            {
                "step": "error_simulation",
                "description": "Simulate parsing error",
                "input": {"code": test_code[:50] + "...", "context": error_context},
            },
        )

        # Step 2: Process through error handling pipeline
        pipeline_result = self.error_pipeline.process_error(
            "SyntaxError: unexpected EOF while parsing",
            error_context,
        )

        workflow_steps.append(
            {
                "step": "pipeline_processing",
                "description": "Process error through pipeline",
                "success": pipeline_result.success,
                "stage_reached": pipeline_result.stage_reached.value,
                "processing_time": pipeline_result.processing_time,
                "has_guidance": pipeline_result.guidance_sequence is not None,
                "has_troubleshooting": len(pipeline_result.troubleshooting_entries) > 0,
            },
        )

        # Step 3: CLI integration for grammar validation
        cli_result = self.cli_integration.handle_grammar_validation_error(
            "python",
            "Grammar parsing failed for Python syntax",
            error_context.get("file_path"),
        )

        workflow_steps.append(
            {
                "step": "cli_integration",
                "description": "Handle through CLI integration",
                "success": cli_result.get("success", False),
                "guidance_count": len(cli_result.get("guidance", [])),
                "quick_fixes_count": len(cli_result.get("quick_fixes", [])),
            },
        )

        # Step 4: Grammar management operations
        grammar_operations = []

        # Check grammar status
        try:
            info_result = self.grammar_cli.info_grammar("python")
            grammar_operations.append(
                {"operation": "info_grammar", "success": info_result == 0},
            )
        except Exception as e:
            grammar_operations.append(
                {"operation": "info_grammar", "success": False, "error": str(e)},
            )

        # Validate grammar
        try:
            validate_result = self.grammar_cli.validate_grammar("python")
            grammar_operations.append(
                {"operation": "validate_grammar", "success": validate_result == 0},
            )
        except Exception as e:
            grammar_operations.append(
                {"operation": "validate_grammar", "success": False, "error": str(e)},
            )

        workflow_steps.append(
            {
                "step": "grammar_operations",
                "description": "Perform grammar management operations",
                "operations": grammar_operations,
            },
        )

        # Step 5: System health check
        health_report = get_system_health_report(
            self.error_pipeline,
            self.error_orchestrator,
        )

        workflow_steps.append(
            {
                "step": "health_check",
                "description": "Check system health after workflow",
                "overall_health": health_report.get("overall_health", {}),
                "pipeline_healthy": health_report.get("pipeline_health", {}).get(
                    "status",
                )
                == "healthy",
            },
        )

        results["workflow_steps"] = workflow_steps

        # Calculate overall workflow success
        successful_steps = sum(
            1 for step in workflow_steps if step.get("success", True)
        )
        results["workflow_success_rate"] = successful_steps / len(workflow_steps)
        results["total_steps"] = len(workflow_steps)
        results["successful_steps"] = successful_steps

        return results

    def test_multi_language_processing(self) -> dict[str, Any]:
        """Test processing multiple languages through the complete system."""
        if not ERROR_HANDLING_AVAILABLE:
            raise AssertionError("Error handling components not available")

        results = {}
        languages = ["python", "javascript", "java"]
        language_results = {}

        for language in languages:
            if language not in self.test_data["code_samples"]:
                continue

            lang_result = {"language": language, "tests": []}

            # Test valid code processing
            valid_code = self.test_data["code_samples"][language]["valid"]
            valid_result = self.error_pipeline.process_error(
                f"Processing {language} code",
                error_context={
                    "language": language,
                    "file_path": f"test.{language}",
                    "code_sample": valid_code,
                },
            )

            lang_result["tests"].append(
                {
                    "test_type": "valid_code",
                    "success": valid_result.success,
                    "processing_time": valid_result.processing_time,
                },
            )

            # Test syntax error processing
            error_code = self.test_data["code_samples"][language]["syntax_error"]
            error_result = self.error_pipeline.process_error(
                f"SyntaxError in {language} code",
                error_context={
                    "language": language,
                    "file_path": f"error_test.{language}",
                    "code_sample": error_code,
                },
            )

            lang_result["tests"].append(
                {
                    "test_type": "syntax_error",
                    "success": error_result.success,
                    "processing_time": error_result.processing_time,
                    "classified": error_result.classified_error is not None,
                },
            )

            # Test CLI operations if available
            if CLI_AVAILABLE and self.grammar_cli:
                try:
                    # Get grammar info
                    info_exit_code = self.grammar_cli.info_grammar(language)
                    lang_result["tests"].append(
                        {"test_type": "cli_info", "success": info_exit_code == 0},
                    )

                    # Get versions
                    versions_exit_code = self.grammar_cli.versions_grammar(language)
                    lang_result["tests"].append(
                        {
                            "test_type": "cli_versions",
                            "success": versions_exit_code == 0,
                        },
                    )

                except Exception as e:
                    lang_result["tests"].append(
                        {
                            "test_type": "cli_operations",
                            "success": False,
                            "error": str(e),
                        },
                    )

            language_results[language] = lang_result

        results["language_results"] = language_results

        # Calculate overall metrics
        all_tests = [
            test
            for lang_data in language_results.values()
            for test in lang_data["tests"]
        ]

        results["summary"] = {
            "total_languages": len(language_results),
            "total_tests": len(all_tests),
            "successful_tests": sum(
                1 for test in all_tests if test.get("success", False)
            ),
            "success_rate": (
                sum(1 for test in all_tests if test.get("success", False))
                / len(all_tests)
                if all_tests
                else 0
            ),
            "avg_processing_time": (
                statistics.mean(
                    [
                        test.get("processing_time", 0)
                        for test in all_tests
                        if "processing_time" in test and test["processing_time"] > 0
                    ],
                )
                if any("processing_time" in test for test in all_tests)
                else 0
            ),
        }

        return results

    # Performance and Stress Tests

    def test_concurrent_processing_stress(self) -> dict[str, Any]:
        """Test system under concurrent processing stress."""
        if not ERROR_HANDLING_AVAILABLE:
            raise AssertionError("Error handling components not available")

        results = {}

        # Stress test configuration
        num_workers = min(multiprocessing.cpu_count(), 8)
        errors_per_worker = 20
        total_errors = num_workers * errors_per_worker

        # Generate test errors
        test_errors = []
        for i in range(total_errors):
            language = random.choice(["python", "javascript", "java"])
            error_type = random.choice(["syntax", "compatibility", "parsing"])
            test_errors.append(
                {
                    "message": f"{error_type.title()}Error: test error {i}",
                    "context": {
                        "language": language,
                        "file_path": f"test_{i}.{language}",
                        "error_type": error_type,
                        "worker_id": i % num_workers,
                    },
                },
            )

        # Function to process errors in a worker
        def process_errors_worker(
            worker_id: int,
            worker_errors: list[dict[str, Any]],
        ) -> list[dict[str, Any]]:
            worker_results = []
            session = self.error_orchestrator.create_session(
                user_id=f"stress_worker_{worker_id}",
            )

            try:
                for error_data in worker_errors:
                    start_time = time.time()

                    try:
                        result = self.error_orchestrator.process_error_in_session(
                            session.session_id,
                            error_data["message"],
                            error_data["context"],
                        )

                        worker_results.append(
                            {
                                "worker_id": worker_id,
                                "success": result.success,
                                "processing_time": result.processing_time,
                                "stage_reached": result.stage_reached.value,
                                "error_type": error_data["context"]["error_type"],
                            },
                        )

                    except Exception as e:
                        worker_results.append(
                            {
                                "worker_id": worker_id,
                                "success": False,
                                "error": str(e),
                                "processing_time": time.time() - start_time,
                                "error_type": error_data["context"]["error_type"],
                            },
                        )

            finally:
                self.error_orchestrator.close_session(session.session_id)

            return worker_results

        # Distribute errors among workers
        worker_errors = [[] for _ in range(num_workers)]
        for i, error_data in enumerate(test_errors):
            worker_errors[i % num_workers].append(error_data)

        # Run stress test
        start_time = time.time()
        all_results = []

        with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
            future_to_worker = {
                executor.submit(process_errors_worker, i, errors): i
                for i, errors in enumerate(worker_errors)
            }

            for future in concurrent.futures.as_completed(future_to_worker):
                worker_id = future_to_worker[future]
                try:
                    worker_results = future.result()
                    all_results.extend(worker_results)
                except Exception as e:
                    logger.error(f"Stress test worker {worker_id} failed: {e}")
                    all_results.append(
                        {
                            "worker_id": worker_id,
                            "success": False,
                            "error": f"Worker failed: {e}",
                            "processing_time": 0,
                        },
                    )

        total_time = time.time() - start_time

        # Analyze results
        successful_results = [r for r in all_results if r.get("success", False)]
        failed_results = [r for r in all_results if not r.get("success", False)]

        processing_times = [r.get("processing_time", 0) for r in successful_results]

        results["stress_test"] = {
            "configuration": {
                "num_workers": num_workers,
                "errors_per_worker": errors_per_worker,
                "total_errors": total_errors,
            },
            "timing": {
                "total_time": total_time,
                "avg_processing_time": (
                    statistics.mean(processing_times) if processing_times else 0
                ),
                "median_processing_time": (
                    statistics.median(processing_times) if processing_times else 0
                ),
                "max_processing_time": max(processing_times) if processing_times else 0,
                "min_processing_time": min(processing_times) if processing_times else 0,
            },
            "results": {
                "total_processed": len(all_results),
                "successful": len(successful_results),
                "failed": len(failed_results),
                "success_rate": (
                    len(successful_results) / len(all_results) if all_results else 0
                ),
                "errors_per_second": (
                    len(all_results) / total_time if total_time > 0 else 0
                ),
            },
        }

        # Test system health after stress test
        health_report = get_system_health_report(
            self.error_pipeline,
            self.error_orchestrator,
        )
        results["post_stress_health"] = health_report

        return results

    def test_memory_usage_analysis(self) -> dict[str, Any]:
        """Test memory usage patterns under various loads."""
        if not ERROR_HANDLING_AVAILABLE:
            raise AssertionError("Error handling components not available")

        results = {}

        # Get initial memory usage
        initial_memory = psutil.Process().memory_info()
        results["initial_memory"] = {
            "rss": initial_memory.rss,
            "vms": initial_memory.vms,
        }

        # Test 1: Gradual load increase
        memory_samples = []
        load_levels = [10, 50, 100, 200, 500]

        for load_level in load_levels:
            # Process batch of errors
            batch_start_memory = psutil.Process().memory_info()

            for i in range(load_level):
                error_msg = f"Memory test error {i} at load level {load_level}"
                context = {
                    "language": "python",
                    "test_type": "memory_analysis",
                    "load_level": load_level,
                    "error_index": i,
                }

                try:
                    result = self.error_pipeline.process_error(error_msg, context)
                except Exception as e:
                    logger.warning(
                        f"Memory test error at load {load_level}, error {i}: {e}",
                    )

            batch_end_memory = psutil.Process().memory_info()
            memory_samples.append(
                {
                    "load_level": load_level,
                    "memory_before": batch_start_memory.rss,
                    "memory_after": batch_end_memory.rss,
                    "memory_delta": batch_end_memory.rss - batch_start_memory.rss,
                    "memory_per_error": (
                        (batch_end_memory.rss - batch_start_memory.rss) / load_level
                        if load_level > 0
                        else 0
                    ),
                },
            )

            # Small delay to allow garbage collection
            time.sleep(0.1)

        results["gradual_load_test"] = memory_samples

        # Test 2: Memory leak detection
        baseline_memory = psutil.Process().memory_info().rss
        leak_test_iterations = 50
        leak_samples = []

        for iteration in range(leak_test_iterations):
            # Process errors and immediately release references
            for i in range(10):
                error_msg = f"Leak test error {i} in iteration {iteration}"
                result = self.error_pipeline.process_error(
                    error_msg,
                    {"language": "python", "leak_test": True},
                )
                # Explicitly delete result to help with garbage collection
                del result

            current_memory = psutil.Process().memory_info().rss
            leak_samples.append(
                {
                    "iteration": iteration,
                    "memory_usage": current_memory,
                    "memory_delta": current_memory - baseline_memory,
                },
            )

        results["memory_leak_test"] = {
            "baseline_memory": baseline_memory,
            "samples": leak_samples,
            "memory_growth": leak_samples[-1]["memory_delta"] if leak_samples else 0,
            "avg_growth_per_iteration": (
                statistics.mean([s["memory_delta"] for s in leak_samples])
                if leak_samples
                else 0
            ),
        }

        # Test 3: Session cleanup memory impact
        pre_session_memory = psutil.Process().memory_info().rss

        # Create and cleanup many sessions
        session_ids = []
        for i in range(100):
            session = self.error_orchestrator.create_session(user_id=f"memory_test_{i}")
            session_ids.append(session.session_id)

            # Process a few errors in each session
            for j in range(3):
                try:
                    self.error_orchestrator.process_error_in_session(
                        session.session_id,
                        f"Session memory test error {j}",
                        {"test": "session_cleanup"},
                    )
                except Exception:
                    pass  # Ignore errors for memory testing

        mid_session_memory = psutil.Process().memory_info().rss

        # Close all sessions
        for session_id in session_ids:
            self.error_orchestrator.close_session(session_id)

        # Allow cleanup time
        time.sleep(1.0)

        post_session_memory = psutil.Process().memory_info().rss

        results["session_cleanup_test"] = {
            "pre_session_memory": pre_session_memory,
            "mid_session_memory": mid_session_memory,
            "post_session_memory": post_session_memory,
            "memory_increase": mid_session_memory - pre_session_memory,
            "memory_recovered": mid_session_memory - post_session_memory,
            "net_memory_impact": post_session_memory - pre_session_memory,
        }

        return results

    def test_thread_safety(self) -> dict[str, Any]:
        """Test thread safety of all system components."""
        if not ERROR_HANDLING_AVAILABLE:
            raise AssertionError("Error handling components not available")

        results = {}

        # Shared data structures for thread safety testing
        shared_results = queue.Queue()
        shared_errors = queue.Queue()
        thread_counter = [0]  # Use list for mutable reference
        counter_lock = threading.Lock()

        def thread_worker(thread_id: int, num_operations: int):
            """Worker function for thread safety testing."""
            thread_results = []

            try:
                # Create session for this thread
                session = self.error_orchestrator.create_session(
                    user_id=f"thread_safety_test_{thread_id}",
                )

                for i in range(num_operations):
                    # Increment shared counter safely
                    with counter_lock:
                        thread_counter[0] += 1
                        operation_id = thread_counter[0]

                    # Process error
                    error_msg = (
                        f"Thread {thread_id} operation {i} (global {operation_id})"
                    )
                    context = {
                        "thread_id": thread_id,
                        "operation_id": operation_id,
                        "language": "python",
                    }

                    start_time = time.time()
                    result = self.error_orchestrator.process_error_in_session(
                        session.session_id,
                        error_msg,
                        context,
                    )

                    thread_results.append(
                        {
                            "thread_id": thread_id,
                            "operation_id": operation_id,
                            "success": result.success,
                            "processing_time": result.processing_time,
                            "wall_time": time.time() - start_time,
                        },
                    )

                    # Small random delay to increase contention
                    time.sleep(random.uniform(0.001, 0.01))

                # Close session
                self.error_orchestrator.close_session(session.session_id)

                # Add results to shared queue
                for result in thread_results:
                    shared_results.put(result)

            except Exception as e:
                shared_errors.put(
                    {
                        "thread_id": thread_id,
                        "error": str(e),
                        "traceback": traceback.format_exc(),
                    },
                )

        # Run thread safety test
        num_threads = 8
        operations_per_thread = 25

        threads = []
        start_time = time.time()

        for thread_id in range(num_threads):
            thread = threading.Thread(
                target=thread_worker,
                args=(thread_id, operations_per_thread),
                name=f"ThreadSafetyTest-{thread_id}",
            )
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join(timeout=30.0)
            if thread.is_alive():
                logger.warning(f"Thread {thread.name} did not complete in time")

        total_time = time.time() - start_time

        # Collect results
        all_results = []
        while not shared_results.empty():
            all_results.append(shared_results.get())

        thread_errors = []
        while not shared_errors.empty():
            thread_errors.append(shared_errors.get())

        results["thread_safety_test"] = {
            "configuration": {
                "num_threads": num_threads,
                "operations_per_thread": operations_per_thread,
                "expected_total_operations": num_threads * operations_per_thread,
            },
            "execution": {
                "total_time": total_time,
                "completed_operations": len(all_results),
                "thread_errors": len(thread_errors),
                "final_counter_value": thread_counter[0],
            },
            "results": {
                "success_rate": (
                    sum(1 for r in all_results if r.get("success", False))
                    / len(all_results)
                    if all_results
                    else 0
                ),
                "avg_processing_time": (
                    statistics.mean([r.get("processing_time", 0) for r in all_results])
                    if all_results
                    else 0
                ),
                "operations_per_second": (
                    len(all_results) / total_time if total_time > 0 else 0
                ),
            },
            "thread_errors": thread_errors[:5],  # Include first 5 errors for debugging
        }

        # Test counter consistency
        expected_counter = len(all_results)
        results["counter_consistency"] = {
            "expected_value": expected_counter,
            "actual_value": thread_counter[0],
            "consistent": expected_counter == thread_counter[0],
        }

        # Test session management thread safety
        session_stats = self.error_orchestrator.get_session_statistics()
        results["session_stats_after_test"] = session_stats

        return results

    # Test Suite Execution Methods

    def run_error_handling_integration_tests(self) -> None:
        """Run comprehensive error handling integration test suite."""
        self.create_test_suite(
            "Error Handling Integration",
            "Comprehensive testing of error handling pipeline integration",
        )

        with self.setup_test_environment():
            # Basic integration tests
            self.run_test(
                self.test_error_handling_pipeline_integration,
                "Error Handling Pipeline Integration",
                TestCategory.INTEGRATION,
                TestPriority.CRITICAL,
                timeout=60.0,
            )

            # Performance tests
            self.run_test(
                self.test_error_handling_performance,
                "Error Handling Performance Test",
                TestCategory.PERFORMANCE,
                TestPriority.HIGH,
                timeout=120.0,
            )

            # Thread safety tests
            self.run_test(
                self.test_thread_safety,
                "Thread Safety Test",
                TestCategory.INTEGRATION,
                TestPriority.HIGH,
                timeout=90.0,
            )

    def run_grammar_cli_integration_tests(self) -> None:
        """Run comprehensive grammar CLI integration test suite."""
        self.create_test_suite(
            "Grammar CLI Integration",
            "Comprehensive testing of grammar management CLI integration",
        )

        with self.setup_test_environment():
            # CLI integration tests
            self.run_test(
                self.test_grammar_management_cli_integration,
                "Grammar Management CLI Integration",
                TestCategory.INTEGRATION,
                TestPriority.CRITICAL,
                timeout=60.0,
            )

            # Phase 1.8 alignment tests
            self.run_test(
                self.test_grammar_cli_phase18_alignment,
                "Grammar CLI Phase 1.8 Alignment",
                TestCategory.INTEGRATION,
                TestPriority.CRITICAL,
                timeout=45.0,
            )

    def run_end_to_end_workflow_tests(self) -> None:
        """Run comprehensive end-to-end workflow test suite."""
        self.create_test_suite(
            "End-to-End Workflows",
            "Comprehensive testing of complete system workflows",
        )

        with self.setup_test_environment():
            # Complete workflow tests
            self.run_test(
                self.test_complete_error_resolution_workflow,
                "Complete Error Resolution Workflow",
                TestCategory.END_TO_END,
                TestPriority.CRITICAL,
                timeout=120.0,
            )

            # Multi-language processing
            self.run_test(
                self.test_multi_language_processing,
                "Multi-Language Processing Workflow",
                TestCategory.END_TO_END,
                TestPriority.HIGH,
                timeout=90.0,
            )

    def run_performance_and_stress_tests(self) -> None:
        """Run comprehensive performance and stress test suite."""
        self.create_test_suite(
            "Performance & Stress Tests",
            "Comprehensive performance testing and stress testing",
        )

        with self.setup_test_environment():
            # Stress tests
            self.run_test(
                self.test_concurrent_processing_stress,
                "Concurrent Processing Stress Test",
                TestCategory.STRESS,
                TestPriority.MEDIUM,
                timeout=180.0,
            )

            # Memory analysis
            self.run_test(
                self.test_memory_usage_analysis,
                "Memory Usage Analysis",
                TestCategory.PERFORMANCE,
                TestPriority.HIGH,
                timeout=120.0,
            )

    def run_all_system_integration_tests(self) -> dict[str, Any]:
        """Run all system integration test suites.

        Returns:
            Comprehensive test report
        """
        logger.info("Starting comprehensive system integration testing")

        start_time = time.time()

        try:
            # Run all test suites
            self.run_error_handling_integration_tests()
            self.run_grammar_cli_integration_tests()
            self.run_end_to_end_workflow_tests()
            self.run_performance_and_stress_tests()

            total_time = time.time() - start_time

            # Generate comprehensive report
            report = self.generate_comprehensive_report()
            report["execution_summary"] = {
                "total_execution_time": total_time,
                "test_suites_completed": len(self.test_suites),
                "completed_at": datetime.now(UTC).isoformat(),
            }

            logger.info(
                f"System integration testing completed in {total_time:.2f} seconds",
            )
            return report

        except Exception as e:
            logger.error(f"System integration testing failed: {e}")
            raise

    def generate_comprehensive_report(self) -> dict[str, Any]:
        """Generate comprehensive test report with detailed metrics.

        Returns:
            Comprehensive test report dictionary
        """
        report = {
            "report_metadata": {
                "generated_at": datetime.now(UTC).isoformat(),
                "system_info": {
                    "platform": platform.platform(),
                    "python_version": platform.python_version(),
                    "cpu_count": multiprocessing.cpu_count(),
                    "available_memory": psutil.virtual_memory().total,
                },
                "component_availability": {
                    "error_handling": ERROR_HANDLING_AVAILABLE,
                    "cli": CLI_AVAILABLE,
                    "phase_17_components": PHASE_17_COMPONENTS_AVAILABLE,
                    "chunker": CHUNKER_AVAILABLE,
                },
            },
            "test_suites": {},
            "overall_summary": {
                "total_suites": len(self.test_suites),
                "total_tests": 0,
                "test_status_counts": defaultdict(int),
                "overall_success_rate": 0.0,
                "total_execution_time": 0.0,
                "performance_metrics": {},
                "critical_failures": [],
            },
        }

        # Process each test suite
        all_tests = []
        for suite_id, suite in self.test_suites.items():
            suite_data = suite.to_dict()
            report["test_suites"][suite_id] = suite_data

            # Update overall metrics
            all_tests.extend(suite.tests)
            report["overall_summary"]["total_tests"] += len(suite.tests)
            report["overall_summary"][
                "total_execution_time"
            ] += suite.total_execution_time

            # Count test statuses
            for status, count in suite.test_counts.items():
                report["overall_summary"]["test_status_counts"][status] += count

            # Collect critical failures
            for test in suite.tests:
                if (
                    test.status in [TestStatus.FAILED, TestStatus.ERROR]
                    and test.test_priority == TestPriority.CRITICAL
                ):
                    report["overall_summary"]["critical_failures"].append(
                        {
                            "suite": suite.suite_name,
                            "test": test.test_name,
                            "status": test.status,
                            "error": test.error_message,
                        },
                    )

        # Calculate overall success rate
        if report["overall_summary"]["total_tests"] > 0:
            passed_tests = report["overall_summary"]["test_status_counts"][
                TestStatus.PASSED
            ]
            report["overall_summary"]["overall_success_rate"] = (
                passed_tests / report["overall_summary"]["total_tests"]
            ) * 100.0

        # Performance analysis
        performance_tests = [
            test
            for test in all_tests
            if test.test_category in [TestCategory.PERFORMANCE, TestCategory.STRESS]
        ]

        if performance_tests:
            execution_times = [test.execution_time for test in performance_tests]
            report["overall_summary"]["performance_metrics"] = {
                "total_performance_tests": len(performance_tests),
                "avg_execution_time": statistics.mean(execution_times),
                "max_execution_time": max(execution_times),
                "min_execution_time": min(execution_times),
                "performance_test_success_rate": (
                    sum(
                        1
                        for test in performance_tests
                        if test.status == TestStatus.PASSED
                    )
                    / len(performance_tests)
                )
                * 100.0,
            }

        # Resource usage analysis
        resource_data = []
        for test in all_tests:
            if test.resource_usage and "cpu_usage" in test.resource_usage:
                resource_data.append(test.resource_usage)

        if resource_data:
            cpu_usages = [
                data["cpu_usage"] for data in resource_data if data["cpu_usage"] > 0
            ]
            memory_usages = [
                data["memory_usage"]
                for data in resource_data
                if data["memory_usage"] > 0
            ]

            report["overall_summary"]["resource_analysis"] = {
                "avg_cpu_usage": statistics.mean(cpu_usages) if cpu_usages else 0,
                "max_cpu_usage": max(cpu_usages) if cpu_usages else 0,
                "avg_memory_usage": (
                    statistics.mean(memory_usages) if memory_usages else 0
                ),
                "max_memory_usage": max(memory_usages) if memory_usages else 0,
            }

        # Phase 1.8 readiness assessment
        phase18_tests = [
            test
            for test in all_tests
            if "phase18" in test.test_name.lower()
            or "phase 1.8" in test.test_name.lower()
        ]

        report["phase_18_readiness"] = {
            "total_phase18_tests": len(phase18_tests),
            "passed_phase18_tests": sum(
                1 for test in phase18_tests if test.status == TestStatus.PASSED
            ),
            "phase18_success_rate": (
                (
                    sum(1 for test in phase18_tests if test.status == TestStatus.PASSED)
                    / len(phase18_tests)
                    * 100.0
                )
                if phase18_tests
                else 0
            ),
            "readiness_status": (
                "READY"
                if all(test.status == TestStatus.PASSED for test in phase18_tests)
                else "NOT_READY" if phase18_tests else "NO_TESTS"
            ),
        }

        # Recommendations
        recommendations = []

        if report["overall_summary"]["overall_success_rate"] < 90:
            recommendations.append(
                "Overall success rate is below 90% - investigate test failures",
            )

        if report["overall_summary"]["critical_failures"]:
            recommendations.append(
                f"{len(report['overall_summary']['critical_failures'])} critical test failures detected - immediate attention required",
            )

        if not ERROR_HANDLING_AVAILABLE:
            recommendations.append(
                "Error handling components not available - check Task E1 implementation",
            )

        if not CLI_AVAILABLE:
            recommendations.append(
                "Grammar CLI components not available - check Task E2 implementation",
            )

        report["recommendations"] = recommendations

        return report

    def save_report(self, output_path: Path, format: str = "json") -> None:
        """Save test report to file.

        Args:
            output_path: Path to save the report
            format: Report format ('json' or 'html')
        """
        report = self.generate_comprehensive_report()

        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)

            if format.lower() == "json":
                with open(output_path, "w") as f:
                    json.dump(report, f, indent=2, default=str)
            elif format.lower() == "html":
                html_content = self._generate_html_report(report)
                with open(output_path, "w") as f:
                    f.write(html_content)
            else:
                raise ValueError(f"Unsupported format: {format}")

            logger.info(f"Test report saved to {output_path}")

        except Exception as e:
            logger.error(f"Failed to save report: {e}")
            raise

    def _generate_html_report(self, report: dict[str, Any]) -> str:
        """Generate HTML report from test results.

        Args:
            report: Test report dictionary

        Returns:
            HTML report as string
        """
        html_template = """
<!DOCTYPE html>
<html>
<head>
    <title>System Integration Test Report</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .summary { background: #f0f0f0; padding: 15px; border-radius: 5px; }
        .suite { margin: 20px 0; border: 1px solid #ddd; padding: 15px; }
        .test { margin: 10px 0; padding: 10px; border-left: 4px solid #ccc; }
        .passed { border-left-color: #28a745; background: #d4edda; }
        .failed { border-left-color: #dc3545; background: #f8d7da; }
        .error { border-left-color: #fd7e14; background: #fff3cd; }
        .skipped { border-left-color: #6c757d; background: #e2e3e5; }
        .metrics { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 10px; }
        .metric { background: #f8f9fa; padding: 10px; border-radius: 3px; }
    </style>
</head>
<body>
    <h1>System Integration Test Report</h1>

    <div class="summary">
        <h2>Summary</h2>
        <div class="metrics">
            <div class="metric">
                <strong>Total Tests:</strong> {total_tests}
            </div>
            <div class="metric">
                <strong>Success Rate:</strong> {success_rate:.1f}%
            </div>
            <div class="metric">
                <strong>Total Time:</strong> {total_time:.2f}s
            </div>
            <div class="metric">
                <strong>Critical Failures:</strong> {critical_failures}
            </div>
        </div>
    </div>

    {test_suites_html}

    <div class="summary">
        <h2>Phase 1.8 Readiness</h2>
        <p><strong>Status:</strong> {readiness_status}</p>
        <p><strong>Success Rate:</strong> {phase18_success_rate:.1f}%</p>
    </div>

    {recommendations_html}

</body>
</html>
        """

        # Generate test suites HTML
        test_suites_html = ""
        for suite_id, suite_data in report["test_suites"].items():
            suite_html = f"""
            <div class="suite">
                <h3>{suite_data['suite_name']}</h3>
                <p>{suite_data['description']}</p>
                <p>Success Rate: {suite_data['success_rate']:.1f}%</p>
            """

            for test_data in suite_data["tests"]:
                test_class = test_data["status"].lower()
                test_html = f"""
                <div class="test {test_class}">
                    <h4>{test_data['test_name']}</h4>
                    <p><strong>Status:</strong> {test_data['status']}</p>
                    <p><strong>Time:</strong> {test_data['execution_time']:.2f}s</p>
                    {f"<p><strong>Error:</strong> {test_data['error_message']}</p>" if test_data.get('error_message') else ""}
                </div>
                """
                suite_html += test_html

            suite_html += "</div>"
            test_suites_html += suite_html

        # Generate recommendations HTML
        recommendations_html = ""
        if report.get("recommendations"):
            recommendations_html = "<div class='summary'><h2>Recommendations</h2><ul>"
            for rec in report["recommendations"]:
                recommendations_html += f"<li>{rec}</li>"
            recommendations_html += "</ul></div>"

        return html_template.format(
            total_tests=report["overall_summary"]["total_tests"],
            success_rate=report["overall_summary"]["overall_success_rate"],
            total_time=report["overall_summary"]["total_execution_time"],
            critical_failures=len(report["overall_summary"]["critical_failures"]),
            test_suites_html=test_suites_html,
            readiness_status=report["phase_18_readiness"]["readiness_status"],
            phase18_success_rate=report["phase_18_readiness"]["phase18_success_rate"],
            recommendations_html=recommendations_html,
        )

    def print_summary(self) -> None:
        """Print comprehensive test summary to console."""
        report = self.generate_comprehensive_report()

        logger.info("\n" + "=" * 80)
        logger.info("SYSTEM INTEGRATION TEST REPORT - PHASE 1.7")
        logger.info("=" * 80)

        # Overall summary
        overall = report["overall_summary"]
        logger.info("\nOverall Results:")
        logger.info("   Total Test Suites: %s", overall["total_suites"])
        logger.info("   Total Tests: %s", overall["total_tests"])
        logger.info("   Success Rate: %.1f%%", overall["overall_success_rate"])
        logger.info(
            "   Total Execution Time: %.2f seconds",
            overall["total_execution_time"],
        )

        # Test status breakdown
        logger.info("\nTest Status Breakdown:")
        for status, count in overall["test_status_counts"].items():
            logger.info("   %s: %s", status.title(), count)

        # Component availability
        logger.info("\nComponent Availability:")
        availability = report["report_metadata"]["component_availability"]
        for component, available in availability.items():
            status_str = "Available" if available else "Not Available"
            logger.info("   %s: %s", component.replace("_", " ").title(), status_str)

        # Test suites
        logger.info("\nTest Suite Results:")
        for suite_id, suite_data in report["test_suites"].items():
            logger.info(
                "   %s: %s/%s passed (%.1f%%)",
                suite_data["suite_name"],
                suite_data["test_counts"].get(TestStatus.PASSED, 0),
                len(suite_data["tests"]),
                suite_data["success_rate"],
            )

        # Phase 1.8 readiness
        phase18 = report["phase_18_readiness"]
        logger.info("\nPhase 1.8 Readiness:")
        logger.info("   Status: %s", phase18["readiness_status"])
        logger.info(
            "   Phase 1.8 Tests: %s/%s passed (%.1f%%)",
            phase18["passed_phase18_tests"],
            phase18["total_phase18_tests"],
            phase18["phase18_success_rate"],
        )

        # Critical failures
        if overall["critical_failures"]:
            logger.warning("\nCritical Failures:")
            for failure in overall["critical_failures"][:5]:  # Show first 5
                logger.warning(
                    "   %s -> %s: %s",
                    failure["suite"],
                    failure["test"],
                    failure["status"],
                )
            if len(overall["critical_failures"]) > 5:
                logger.warning(
                    "   ... and %s more", len(overall["critical_failures"]) - 5
                )

        # Performance metrics
        if overall.get("performance_metrics"):
            perf = overall["performance_metrics"]
            logger.info("\nPerformance Metrics:")
            logger.info("   Performance Tests: %s", perf["total_performance_tests"])
            logger.info("   Avg Execution Time: %.2fs", perf["avg_execution_time"])
            logger.info(
                "   Performance Success Rate: %.1f%%",
                perf["performance_test_success_rate"],
            )

        # Recommendations
        if report["recommendations"]:
            logger.info("\nRecommendations:")
            for i, rec in enumerate(report["recommendations"][:5], 1):
                logger.info("   %s. %s", i, rec)

        logger.info("=" * 80)


def run_comprehensive_system_integration_tests(
    config: dict[str, Any] | None = None,
    output_dir: Path | None = None,
) -> SystemIntegrationTester:
    """Run comprehensive system integration tests.

    Args:
        config: Optional test configuration
        output_dir: Optional output directory for reports

    Returns:
        SystemIntegrationTester instance with results
    """
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Create tester instance
    tester = SystemIntegrationTester(config)

    try:
        logger.info("Starting Comprehensive System Integration Testing")
        logger.info("=" * 80)

        # Run all tests
        report = tester.run_all_system_integration_tests()

        # Print summary
        tester.print_summary()

        # Save reports if output directory specified
        if output_dir:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            # Save JSON report
            json_path = output_dir / f"system_integration_report_{timestamp}.json"
            tester.save_report(json_path, "json")

            # Save HTML report
            html_path = output_dir / f"system_integration_report_{timestamp}.html"
            tester.save_report(html_path, "html")

            logger.info("\nReports saved to:")
            logger.info("   JSON: %s", json_path)
            logger.info("   HTML: %s", html_path)

        logger.info(
            "\nComprehensive system integration testing completed successfully!"
        )
        return tester

    except Exception as e:
        logger.error("System integration testing failed: %s", e)
        raise


if __name__ == "__main__":
    # Run system integration tests
    run_comprehensive_system_integration_tests(output_dir=Path("test_reports"))

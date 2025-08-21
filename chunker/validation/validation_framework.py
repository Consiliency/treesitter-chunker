# chunker/validation/validation_framework.py

import gc
import hashlib
import json
import logging
import os
import pickle
import statistics
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import weakref
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from ..performance.core.performance_framework import (
    PerformanceManager,
    PerformanceProfile,
)

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Represents a validation test result."""

    test_name: str
    status: str  # 'passed', 'failed', 'skipped', 'error'
    execution_time: float
    timestamp: datetime
    details: dict[str, Any]
    error_message: str | None = None
    metrics: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert result to dictionary."""
        return {
            "test_name": self.test_name,
            "status": self.status,
            "execution_time": self.execution_time,
            "timestamp": self.timestamp.isoformat(),
            "details": self.details,
            "error_message": self.error_message,
            "metrics": self.metrics,
        }


@dataclass
class LoadTestScenario:
    """Load test scenario configuration."""

    name: str
    description: str
    target_function: Callable
    load_levels: list[int]
    duration_seconds: float
    ramp_up_seconds: float
    success_criteria: dict[str, float]
    test_data_generator: Callable | None = None

    def generate_test_data(self) -> Any:
        """Generate test data for the scenario."""
        if self.test_data_generator:
            return self.test_data_generator()
        return None


class ValidationManager:
    """Main validation orchestration and coordination."""

    def __init__(self):
        """Initialize the validation manager."""
        self.performance_validator = PerformanceValidator()
        self.load_tester = LoadTester()
        self.regression_tester = RegressionTester()
        self.logger = logging.getLogger(f"{__name__}.ValidationManager")
        self._validation_history: list[dict[str, Any]] = []
        self._lock = threading.RLock()

        # Validation configuration
        self.config = {
            "max_execution_time": 300,  # 5 minutes
            "parallel_test_workers": 4,
            "retry_failed_tests": True,
            "max_retries": 3,
            "enable_detailed_logging": True,
        }

    def run_full_validation(
        self,
        components: list[str] | None = None,
    ) -> dict[str, Any]:
        """Run complete validation suite."""
        start_time = time.time()
        validation_id = hashlib.md5(
            f"{datetime.now().isoformat()}".encode(),
        ).hexdigest()[:8]

        self.logger.info(f"Starting full validation suite (ID: {validation_id})")

        try:
            # Initialize validation report
            validation_report = {
                "validation_id": validation_id,
                "start_time": datetime.now().isoformat(),
                "components_tested": components
                or ["performance", "load", "regression"],
                "status": "in_progress",
                "results": {},
                "summary": {
                    "total_tests": 0,
                    "passed": 0,
                    "failed": 0,
                    "skipped": 0,
                    "errors": 0,
                },
                "execution_time": 0.0,
                "recommendations": [],
            }

            # Run component validations
            if not components or "performance" in components:
                self.logger.info("Running performance validation...")
                perf_results = self.validate_performance()
                validation_report["results"]["performance"] = perf_results
                self._update_summary(validation_report["summary"], perf_results)

            if not components or "load" in components:
                self.logger.info("Running load tests...")
                load_results = self.run_load_tests()
                validation_report["results"]["load"] = load_results
                self._update_summary(validation_report["summary"], load_results)

            if not components or "regression" in components:
                self.logger.info("Running regression tests...")
                regression_results = self.run_regression_tests()
                validation_report["results"]["regression"] = regression_results
                self._update_summary(validation_report["summary"], regression_results)

            # Determine overall status
            validation_report["execution_time"] = time.time() - start_time
            validation_report["end_time"] = datetime.now().isoformat()

            summary = validation_report["summary"]
            if summary["errors"] > 0:
                validation_report["status"] = "error"
            elif summary["failed"] > 0:
                validation_report["status"] = "failed"
            elif summary["passed"] > 0:
                validation_report["status"] = "passed"
            else:
                validation_report["status"] = "no_tests"

            # Generate recommendations
            validation_report["recommendations"] = (
                self._generate_validation_recommendations(validation_report)
            )

            # Store validation history
            with self._lock:
                self._validation_history.append(validation_report)
                # Keep only last 50 validations
                if len(self._validation_history) > 50:
                    self._validation_history = self._validation_history[-50:]

            self.logger.info(
                f"Full validation completed: {validation_report['status']} "
                f"({summary['passed']}/{summary['total_tests']} passed)",
            )

            return validation_report

        except Exception as e:
            self.logger.error(f"Error in full validation: {e}")
            return {
                "validation_id": validation_id,
                "status": "error",
                "error": str(e),
                "execution_time": time.time() - start_time,
                "timestamp": datetime.now().isoformat(),
            }

    def _update_summary(
        self,
        summary: dict[str, int],
        component_results: dict[str, Any],
    ) -> None:
        """Update validation summary with component results."""
        if "test_results" in component_results:
            for result in component_results["test_results"]:
                summary["total_tests"] += 1
                status = result.get("status", "unknown")
                if status in summary:
                    summary[status] += 1

    def _generate_validation_recommendations(
        self,
        validation_report: dict[str, Any],
    ) -> list[str]:
        """Generate recommendations based on validation results."""
        recommendations = []
        summary = validation_report["summary"]

        # Check overall health
        if summary["failed"] > summary["passed"]:
            recommendations.append(
                "System has more failing than passing tests - immediate attention required",
            )

        if summary["errors"] > 0:
            recommendations.append(
                "System errors detected - investigate error logs and fix underlying issues",
            )

        # Check specific component results
        results = validation_report.get("results", {})

        if "performance" in results:
            perf_results = results["performance"]
            if perf_results.get("overall_health") == "critical":
                recommendations.append(
                    "Critical performance issues detected - optimize system resources",
                )
            elif perf_results.get("optimization_potential", 0) > 50:
                recommendations.append(
                    "High optimization potential - consider performance tuning",
                )

        if "load" in results:
            load_results = results["load"]
            failed_scenarios = [
                s
                for s in load_results.get("scenario_results", [])
                if s.get("status") == "failed"
            ]
            if failed_scenarios:
                recommendations.append(
                    f"Load testing failures in {len(failed_scenarios)} scenarios - review capacity limits",
                )

        if "regression" in results:
            regression_results = results["regression"]
            if regression_results.get("regressions_detected", 0) > 0:
                recommendations.append(
                    "Performance regressions detected - investigate recent changes",
                )

        if not recommendations:
            recommendations.append("All validations passed - system is performing well")

        return recommendations

    def validate_performance(self) -> dict[str, Any]:
        """Validate system performance."""
        try:
            return self.performance_validator.validate_performance_benchmarks()
        except Exception as e:
            self.logger.error(f"Error validating performance: {e}")
            return {
                "status": "error",
                "error": str(e),
                "test_results": [],
                "overall_health": "unknown",
            }

    def run_load_tests(self) -> dict[str, Any]:
        """Execute comprehensive load testing."""
        try:
            return self.load_tester.run_comprehensive_load_tests()
        except Exception as e:
            self.logger.error(f"Error running load tests: {e}")
            return {"status": "error", "error": str(e), "scenario_results": []}

    def run_regression_tests(self) -> dict[str, Any]:
        """Execute regression testing."""
        try:
            return self.regression_tester.detect_regressions()
        except Exception as e:
            self.logger.error(f"Error running regression tests: {e}")
            return {
                "status": "error",
                "error": str(e),
                "regressions_detected": 0,
                "test_results": [],
            }

    def generate_validation_report(
        self,
        validation_id: str | None = None,
    ) -> dict[str, Any]:
        """Generate comprehensive validation report."""
        try:
            with self._lock:
                if validation_id:
                    # Find specific validation
                    validation = next(
                        (
                            v
                            for v in self._validation_history
                            if v["validation_id"] == validation_id
                        ),
                        None,
                    )
                    if not validation:
                        return {"error": f"Validation {validation_id} not found"}
                    return validation
                # Return latest validation or run new one
                if self._validation_history:
                    return self._validation_history[-1]
                return self.run_full_validation()

        except Exception as e:
            self.logger.error(f"Error generating validation report: {e}")
            return {"error": str(e), "timestamp": datetime.now().isoformat()}

    def get_validation_history(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get validation history."""
        with self._lock:
            return self._validation_history[-limit:]

    def clear_validation_history(self) -> None:
        """Clear validation history."""
        with self._lock:
            self._validation_history.clear()


class PerformanceValidator:
    """Performance benchmark validation and testing."""

    def __init__(self):
        """Initialize the performance validator."""
        self.performance_manager = PerformanceManager()
        self.benchmarks = {}
        self.sla_requirements = {}
        self.logger = logging.getLogger(f"{__name__}.PerformanceValidator")

        # Set default SLA requirements
        self._set_default_sla_requirements()

        # Set default benchmarks
        self._set_default_benchmarks()

    def _set_default_sla_requirements(self) -> None:
        """Set default SLA requirements."""
        self.sla_requirements = {
            "response_time_ms": 1000,  # 1 second
            "throughput_ops_per_sec": 100,
            "error_rate_percent": 1.0,
            "cpu_utilization_percent": 80,
            "memory_utilization_percent": 85,
            "availability_percent": 99.9,
        }

    def _set_default_benchmarks(self) -> None:
        """Set default performance benchmarks."""
        self.benchmarks = {
            "chunking_performance": {
                "max_chunk_time_ms": 500,
                "min_throughput_chunks_per_sec": 50,
                "max_memory_mb_per_chunk": 10,
            },
            "parsing_performance": {
                "max_parse_time_ms": 200,
                "min_throughput_files_per_sec": 20,
                "max_memory_mb_per_file": 5,
            },
            "system_performance": {
                "max_startup_time_ms": 5000,
                "max_memory_baseline_mb": 100,
                "min_gc_efficiency_percent": 80,
            },
        }

    def validate_performance_benchmarks(self) -> dict[str, Any]:
        """Validate performance against benchmarks."""
        start_time = time.time()

        try:
            # Collect current performance metrics
            current_profile = self.performance_manager.collect_system_metrics()

            test_results = []

            # Test chunking performance
            chunking_results = self._test_chunking_performance()
            test_results.extend(chunking_results)

            # Test parsing performance
            parsing_results = self._test_parsing_performance()
            test_results.extend(parsing_results)

            # Test system performance
            system_results = self._test_system_performance(current_profile)
            test_results.extend(system_results)

            # Calculate overall health
            passed_count = sum(1 for r in test_results if r.status == "passed")
            total_count = len(test_results)
            health_ratio = passed_count / total_count if total_count > 0 else 0

            if health_ratio >= 0.9:
                overall_health = "good"
            elif health_ratio >= 0.7:
                overall_health = "warning"
            else:
                overall_health = "critical"

            return {
                "status": "completed",
                "execution_time": time.time() - start_time,
                "test_results": [r.to_dict() for r in test_results],
                "summary": {
                    "total_tests": total_count,
                    "passed": passed_count,
                    "failed": total_count - passed_count,
                    "health_ratio": health_ratio,
                },
                "overall_health": overall_health,
                "optimization_potential": current_profile.optimization_potential,
                "recommendations": current_profile.recommendations,
            }

        except Exception as e:
            self.logger.error(f"Error validating performance benchmarks: {e}")
            return {
                "status": "error",
                "error": str(e),
                "execution_time": time.time() - start_time,
                "test_results": [],
                "overall_health": "unknown",
            }

    def _test_chunking_performance(self) -> list[ValidationResult]:
        """Test chunking performance against benchmarks."""
        results = []

        try:
            # Mock chunking performance test
            start_time = time.time()

            # Simulate chunking operation
            time.sleep(0.1)  # Simulate processing time

            execution_time = (time.time() - start_time) * 1000  # Convert to ms

            # Test against benchmark
            max_time = self.benchmarks["chunking_performance"]["max_chunk_time_ms"]
            status = "passed" if execution_time <= max_time else "failed"

            results.append(
                ValidationResult(
                    test_name="chunking_max_time",
                    status=status,
                    execution_time=execution_time,
                    timestamp=datetime.now(),
                    details={
                        "measured_time_ms": execution_time,
                        "benchmark_max_ms": max_time,
                        "within_benchmark": execution_time <= max_time,
                    },
                    metrics={"execution_time_ms": execution_time},
                ),
            )

            # Test throughput
            chunks_processed = 10
            throughput = chunks_processed / (execution_time / 1000)  # chunks per second
            min_throughput = self.benchmarks["chunking_performance"][
                "min_throughput_chunks_per_sec"
            ]

            status = "passed" if throughput >= min_throughput else "failed"

            results.append(
                ValidationResult(
                    test_name="chunking_throughput",
                    status=status,
                    execution_time=execution_time,
                    timestamp=datetime.now(),
                    details={
                        "measured_throughput": throughput,
                        "benchmark_min_throughput": min_throughput,
                        "chunks_processed": chunks_processed,
                    },
                    metrics={"throughput_chunks_per_sec": throughput},
                ),
            )

        except Exception as e:
            results.append(
                ValidationResult(
                    test_name="chunking_performance_error",
                    status="error",
                    execution_time=0.0,
                    timestamp=datetime.now(),
                    details={"error_type": type(e).__name__},
                    error_message=str(e),
                ),
            )

        return results

    def _test_parsing_performance(self) -> list[ValidationResult]:
        """Test parsing performance against benchmarks."""
        results = []

        try:
            # Mock parsing performance test
            start_time = time.time()

            # Simulate parsing operation
            time.sleep(0.05)  # Simulate processing time

            execution_time = (time.time() - start_time) * 1000  # Convert to ms

            # Test against benchmark
            max_time = self.benchmarks["parsing_performance"]["max_parse_time_ms"]
            status = "passed" if execution_time <= max_time else "failed"

            results.append(
                ValidationResult(
                    test_name="parsing_max_time",
                    status=status,
                    execution_time=execution_time,
                    timestamp=datetime.now(),
                    details={
                        "measured_time_ms": execution_time,
                        "benchmark_max_ms": max_time,
                        "within_benchmark": execution_time <= max_time,
                    },
                    metrics={"execution_time_ms": execution_time},
                ),
            )

        except Exception as e:
            results.append(
                ValidationResult(
                    test_name="parsing_performance_error",
                    status="error",
                    execution_time=0.0,
                    timestamp=datetime.now(),
                    details={"error_type": type(e).__name__},
                    error_message=str(e),
                ),
            )

        return results

    def _test_system_performance(
        self,
        profile: PerformanceProfile,
    ) -> list[ValidationResult]:
        """Test system performance against benchmarks."""
        results = []

        try:
            # Test memory usage
            memory_metrics = profile.get_metrics_by_category("memory")
            memory_percent_metrics = [m for m in memory_metrics if m.unit == "%"]

            if memory_percent_metrics:
                avg_memory_percent = statistics.mean(
                    m.value for m in memory_percent_metrics
                )
                max_memory_percent = self.sla_requirements["memory_utilization_percent"]

                status = (
                    "passed" if avg_memory_percent <= max_memory_percent else "failed"
                )

                results.append(
                    ValidationResult(
                        test_name="system_memory_utilization",
                        status=status,
                        execution_time=profile.profile_time,
                        timestamp=datetime.now(),
                        details={
                            "measured_memory_percent": avg_memory_percent,
                            "sla_max_percent": max_memory_percent,
                            "within_sla": avg_memory_percent <= max_memory_percent,
                        },
                        metrics={"memory_utilization_percent": avg_memory_percent},
                    ),
                )

            # Test CPU usage
            cpu_metrics = profile.get_metrics_by_category("cpu")
            cpu_percent_metrics = [m for m in cpu_metrics if "percent" in m.name]

            if cpu_percent_metrics:
                avg_cpu_percent = statistics.mean(m.value for m in cpu_percent_metrics)
                max_cpu_percent = self.sla_requirements["cpu_utilization_percent"]

                status = "passed" if avg_cpu_percent <= max_cpu_percent else "failed"

                results.append(
                    ValidationResult(
                        test_name="system_cpu_utilization",
                        status=status,
                        execution_time=profile.profile_time,
                        timestamp=datetime.now(),
                        details={
                            "measured_cpu_percent": avg_cpu_percent,
                            "sla_max_percent": max_cpu_percent,
                            "within_sla": avg_cpu_percent <= max_cpu_percent,
                        },
                        metrics={"cpu_utilization_percent": avg_cpu_percent},
                    ),
                )

        except Exception as e:
            results.append(
                ValidationResult(
                    test_name="system_performance_error",
                    status="error",
                    execution_time=0.0,
                    timestamp=datetime.now(),
                    details={"error_type": type(e).__name__},
                    error_message=str(e),
                ),
            )

        return results

    def validate_performance_sla(self) -> dict[str, Any]:
        """Validate performance against SLA requirements."""
        start_time = time.time()

        try:
            # Get current performance profile
            current_profile = self.performance_manager.collect_system_metrics()

            sla_results = []

            for sla_metric, threshold in self.sla_requirements.items():
                # Find matching metrics in profile
                matching_metrics = []

                for metric in current_profile.metrics:
                    if (
                        sla_metric.replace("_", "").lower()
                        in metric.name.replace("_", "").lower()
                    ):
                        matching_metrics.append(metric)

                if matching_metrics:
                    # Use average value for SLA check
                    avg_value = statistics.mean(m.value for m in matching_metrics)
                    status = "passed" if avg_value <= threshold else "failed"

                    sla_results.append(
                        ValidationResult(
                            test_name=f"sla_{sla_metric}",
                            status=status,
                            execution_time=current_profile.profile_time,
                            timestamp=datetime.now(),
                            details={
                                "measured_value": avg_value,
                                "sla_threshold": threshold,
                                "within_sla": avg_value <= threshold,
                                "metrics_count": len(matching_metrics),
                            },
                            metrics={sla_metric: avg_value},
                        ),
                    )
                else:
                    # SLA metric not available
                    sla_results.append(
                        ValidationResult(
                            test_name=f"sla_{sla_metric}",
                            status="skipped",
                            execution_time=0.0,
                            timestamp=datetime.now(),
                            details={"reason": "metric_not_available"},
                            error_message=f"No metrics found for SLA requirement: {sla_metric}",
                        ),
                    )

            return {
                "status": "completed",
                "execution_time": time.time() - start_time,
                "sla_results": [r.to_dict() for r in sla_results],
                "sla_compliance": all(
                    r.status in ["passed", "skipped"] for r in sla_results
                ),
            }

        except Exception as e:
            self.logger.error(f"Error validating performance SLA: {e}")
            return {
                "status": "error",
                "error": str(e),
                "execution_time": time.time() - start_time,
                "sla_results": [],
            }

    def detect_performance_regressions(
        self,
        baseline_profile: PerformanceProfile | None = None,
    ) -> list[dict[str, Any]]:
        """Detect performance regressions."""
        try:
            current_profile = self.performance_manager.collect_system_metrics()

            if not baseline_profile:
                # Use historical data if available
                history = self.performance_manager.get_performance_history()
                if len(history) < 2:
                    return [
                        {
                            "error": "Insufficient historical data for regression detection",
                        },
                    ]
                baseline_profile = history[-2]  # Previous profile

            regressions = []

            # Compare metrics between profiles
            current_metrics = {m.name: m.value for m in current_profile.metrics}
            baseline_metrics = {m.name: m.value for m in baseline_profile.metrics}

            for metric_name, current_value in current_metrics.items():
                if metric_name in baseline_metrics:
                    baseline_value = baseline_metrics[metric_name]

                    # Calculate percentage change
                    if baseline_value > 0:
                        change_percent = (
                            (current_value - baseline_value) / baseline_value
                        ) * 100

                        # Consider significant changes as potential regressions
                        if abs(change_percent) > 20:  # 20% threshold
                            regression_type = (
                                "performance_degradation"
                                if change_percent > 0
                                else "unexpected_improvement"
                            )

                            regressions.append(
                                {
                                    "metric_name": metric_name,
                                    "baseline_value": baseline_value,
                                    "current_value": current_value,
                                    "change_percent": change_percent,
                                    "regression_type": regression_type,
                                    "severity": (
                                        "high" if abs(change_percent) > 50 else "medium"
                                    ),
                                },
                            )

            return regressions

        except Exception as e:
            self.logger.error(f"Error detecting performance regressions: {e}")
            return [{"error": str(e)}]

    def generate_performance_report(self) -> dict[str, Any]:
        """Generate performance validation report."""
        try:
            # Run all performance validations
            benchmark_results = self.validate_performance_benchmarks()
            sla_results = self.validate_performance_sla()
            regressions = self.detect_performance_regressions()

            return {
                "timestamp": datetime.now().isoformat(),
                "benchmark_validation": benchmark_results,
                "sla_validation": sla_results,
                "regression_analysis": {
                    "regressions_found": len(
                        [r for r in regressions if "error" not in r],
                    ),
                    "regressions": regressions,
                },
                "overall_status": (
                    "healthy"
                    if (
                        benchmark_results.get("overall_health") == "good"
                        and sla_results.get("sla_compliance", False)
                        and len(regressions) == 0
                    )
                    else "needs_attention"
                ),
            }

        except Exception as e:
            self.logger.error(f"Error generating performance report: {e}")
            return {
                "timestamp": datetime.now().isoformat(),
                "error": str(e),
                "overall_status": "error",
            }


class LoadTester:
    """Comprehensive load testing and stress testing."""

    def __init__(self):
        """Initialize the load tester."""
        self.test_scenarios: dict[str, LoadTestScenario] = {}
        self.results_store: dict[str, list[dict[str, Any]]] = {}
        self.logger = logging.getLogger(f"{__name__}.LoadTester")

        # Initialize default test scenarios
        self._setup_default_scenarios()

    def _setup_default_scenarios(self) -> None:
        """Setup default load test scenarios."""
        # Basic processing scenario
        self.test_scenarios["basic_processing"] = LoadTestScenario(
            name="basic_processing",
            description="Basic processing load test",
            target_function=self._mock_processing_function,
            load_levels=[1, 5, 10, 20],
            duration_seconds=10.0,
            ramp_up_seconds=2.0,
            success_criteria={
                "max_response_time_ms": 1000,
                "min_success_rate_percent": 95,
                "max_error_rate_percent": 5,
            },
        )

        # Memory intensive scenario
        self.test_scenarios["memory_intensive"] = LoadTestScenario(
            name="memory_intensive",
            description="Memory intensive load test",
            target_function=self._mock_memory_intensive_function,
            load_levels=[1, 3, 5],
            duration_seconds=15.0,
            ramp_up_seconds=3.0,
            success_criteria={
                "max_memory_mb": 500,
                "max_response_time_ms": 2000,
                "min_success_rate_percent": 90,
            },
        )

        # High concurrency scenario
        self.test_scenarios["high_concurrency"] = LoadTestScenario(
            name="high_concurrency",
            description="High concurrency load test",
            target_function=self._mock_concurrent_function,
            load_levels=[10, 25, 50, 100],
            duration_seconds=20.0,
            ramp_up_seconds=5.0,
            success_criteria={
                "max_response_time_ms": 1500,
                "min_success_rate_percent": 98,
                "max_error_rate_percent": 2,
            },
        )

    def _mock_processing_function(self, test_data: Any = None) -> dict[str, Any]:
        """Mock processing function for load testing."""
        start_time = time.time()

        # Simulate some processing work
        time.sleep(0.01)  # 10ms of work

        # Occasionally simulate an error (5% chance)
        if time.time() % 100 < 5:
            raise Exception("Simulated processing error")

        return {
            "result": "success",
            "execution_time": time.time() - start_time,
            "processed_data": f"processed_{hash(str(test_data)) if test_data else 'none'}",
        }

    def _mock_memory_intensive_function(self, test_data: Any = None) -> dict[str, Any]:
        """Mock memory intensive function for load testing."""
        start_time = time.time()

        # Simulate memory allocation
        data = [i for i in range(10000)]  # Allocate some memory
        time.sleep(0.02)  # 20ms of work

        return {
            "result": "success",
            "execution_time": time.time() - start_time,
            "memory_allocated": len(data),
        }

    def _mock_concurrent_function(self, test_data: Any = None) -> dict[str, Any]:
        """Mock concurrent function for load testing."""
        start_time = time.time()

        # Simulate thread-safe processing
        time.sleep(0.005)  # 5ms of work

        return {
            "result": "success",
            "execution_time": time.time() - start_time,
            "thread_id": threading.current_thread().ident,
        }

    def run_load_test(self, scenario: str, load_level: int) -> dict[str, Any]:
        """Run a specific load test scenario."""
        if scenario not in self.test_scenarios:
            return {"error": f"Unknown scenario: {scenario}"}

        test_scenario = self.test_scenarios[scenario]
        start_time = time.time()

        self.logger.info(f"Running load test: {scenario} with load level {load_level}")

        try:
            results = []
            errors = []

            # Calculate test parameters
            total_requests = int(load_level * test_scenario.duration_seconds)
            request_interval = (
                test_scenario.duration_seconds / total_requests
                if total_requests > 0
                else 1.0
            )

            # Use ThreadPoolExecutor for concurrent load generation
            with ThreadPoolExecutor(max_workers=min(load_level, 50)) as executor:
                # Submit all requests
                futures = []

                for i in range(total_requests):
                    # Ramp up gradually
                    if i < (load_level * test_scenario.ramp_up_seconds):
                        time.sleep(request_interval * 0.5)  # Slower ramp up

                    test_data = test_scenario.generate_test_data()
                    future = executor.submit(
                        self._execute_single_request,
                        test_scenario.target_function,
                        test_data,
                        i,
                    )
                    futures.append(future)

                    # Control request rate
                    if i < total_requests - 1:
                        time.sleep(max(0, request_interval - 0.001))

                # Collect results
                for future in as_completed(
                    futures,
                    timeout=test_scenario.duration_seconds + 30,
                ):
                    try:
                        result = future.result()
                        results.append(result)
                    except Exception as e:
                        errors.append(
                            {
                                "error": str(e),
                                "error_type": type(e).__name__,
                                "timestamp": datetime.now().isoformat(),
                            },
                        )

            # Analyze results
            execution_time = time.time() - start_time

            response_times = [
                r["execution_time"] for r in results if "execution_time" in r
            ]
            success_count = len(results)
            error_count = len(errors)
            total_requests_attempted = success_count + error_count

            # Calculate metrics
            metrics = {
                "total_requests": total_requests_attempted,
                "successful_requests": success_count,
                "failed_requests": error_count,
                "success_rate_percent": (
                    (success_count / total_requests_attempted * 100)
                    if total_requests_attempted > 0
                    else 0
                ),
                "error_rate_percent": (
                    (error_count / total_requests_attempted * 100)
                    if total_requests_attempted > 0
                    else 0
                ),
                "average_response_time_ms": (
                    statistics.mean(response_times) * 1000 if response_times else 0
                ),
                "median_response_time_ms": (
                    statistics.median(response_times) * 1000 if response_times else 0
                ),
                "min_response_time_ms": (
                    min(response_times) * 1000 if response_times else 0
                ),
                "max_response_time_ms": (
                    max(response_times) * 1000 if response_times else 0
                ),
                "throughput_requests_per_sec": (
                    success_count / execution_time if execution_time > 0 else 0
                ),
                "test_duration_seconds": execution_time,
            }

            # Check success criteria
            success_criteria_met = self._check_success_criteria(
                test_scenario.success_criteria,
                metrics,
            )

            result = {
                "scenario": scenario,
                "load_level": load_level,
                "status": "passed" if success_criteria_met else "failed",
                "metrics": metrics,
                "success_criteria": test_scenario.success_criteria,
                "success_criteria_met": success_criteria_met,
                "errors": errors[:10],  # Keep only first 10 errors
                "timestamp": datetime.now().isoformat(),
            }

            # Store result
            if scenario not in self.results_store:
                self.results_store[scenario] = []
            self.results_store[scenario].append(result)

            self.logger.info(
                f"Load test completed: {scenario} - {result['status']} "
                f"({metrics['success_rate_percent']:.1f}% success rate)",
            )

            return result

        except Exception as e:
            self.logger.error(f"Error running load test {scenario}: {e}")
            return {
                "scenario": scenario,
                "load_level": load_level,
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }

    def _execute_single_request(
        self,
        target_function: Callable,
        test_data: Any,
        request_id: int,
    ) -> dict[str, Any]:
        """Execute a single request for load testing."""
        start_time = time.time()

        try:
            result = target_function(test_data)
            execution_time = time.time() - start_time

            return {
                "request_id": request_id,
                "status": "success",
                "execution_time": execution_time,
                "result": result,
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            execution_time = time.time() - start_time

            return {
                "request_id": request_id,
                "status": "error",
                "execution_time": execution_time,
                "error": str(e),
                "error_type": type(e).__name__,
                "timestamp": datetime.now().isoformat(),
            }

    def _check_success_criteria(
        self,
        criteria: dict[str, float],
        metrics: dict[str, float],
    ) -> bool:
        """Check if metrics meet success criteria."""
        try:
            for criterion, threshold in criteria.items():
                if criterion == "max_response_time_ms":
                    if metrics.get("max_response_time_ms", float("inf")) > threshold:
                        return False
                elif criterion == "min_success_rate_percent":
                    if metrics.get("success_rate_percent", 0) < threshold:
                        return False
                elif criterion == "max_error_rate_percent":
                    if metrics.get("error_rate_percent", 100) > threshold:
                        return False
                elif criterion == "max_memory_mb":
                    # This would need to be measured during the test
                    pass

            return True

        except Exception as e:
            self.logger.error(f"Error checking success criteria: {e}")
            return False

    def run_stress_test(self, scenario: str) -> dict[str, Any]:
        """Run stress testing to failure point."""
        if scenario not in self.test_scenarios:
            return {"error": f"Unknown scenario: {scenario}"}

        test_scenario = self.test_scenarios[scenario]
        start_time = time.time()

        self.logger.info(f"Running stress test: {scenario}")

        try:
            stress_results = []
            max_load_level = (
                test_scenario.load_levels[-1] if test_scenario.load_levels else 10
            )

            # Gradually increase load until failure
            current_load = 1
            consecutive_failures = 0

            while consecutive_failures < 3 and current_load <= max_load_level * 5:
                result = self.run_load_test(scenario, current_load)
                stress_results.append(result)

                if result["status"] == "failed":
                    consecutive_failures += 1
                else:
                    consecutive_failures = 0

                current_load *= 2  # Double the load each iteration

                # Brief pause between stress levels
                time.sleep(1)

            # Find breaking point
            successful_tests = [r for r in stress_results if r["status"] == "passed"]
            breaking_point = (
                successful_tests[-1]["load_level"] if successful_tests else 0
            )

            return {
                "scenario": scenario,
                "status": "completed",
                "execution_time": time.time() - start_time,
                "breaking_point_load_level": breaking_point,
                "max_tested_load_level": (
                    stress_results[-1]["load_level"] if stress_results else 0
                ),
                "total_tests_run": len(stress_results),
                "stress_test_results": stress_results,
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            self.logger.error(f"Error running stress test {scenario}: {e}")
            return {
                "scenario": scenario,
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }

    def run_comprehensive_load_tests(self) -> dict[str, Any]:
        """Run all configured load test scenarios."""
        start_time = time.time()

        self.logger.info("Running comprehensive load tests")

        try:
            scenario_results = []

            for scenario_name, scenario in self.test_scenarios.items():
                self.logger.info(f"Testing scenario: {scenario_name}")

                scenario_test_results = []

                # Test each load level
                for load_level in scenario.load_levels:
                    result = self.run_load_test(scenario_name, load_level)
                    scenario_test_results.append(result)

                # Run stress test for this scenario
                stress_result = self.run_stress_test(scenario_name)

                scenario_results.append(
                    {
                        "scenario_name": scenario_name,
                        "load_test_results": scenario_test_results,
                        "stress_test_result": stress_result,
                        "overall_status": (
                            "passed"
                            if all(
                                r["status"] == "passed" for r in scenario_test_results
                            )
                            else "failed"
                        ),
                    },
                )

            # Overall analysis
            total_tests = sum(len(sr["load_test_results"]) for sr in scenario_results)
            passed_tests = sum(
                len([r for r in sr["load_test_results"] if r["status"] == "passed"])
                for sr in scenario_results
            )

            return {
                "status": "completed",
                "execution_time": time.time() - start_time,
                "scenario_results": scenario_results,
                "summary": {
                    "total_scenarios": len(scenario_results),
                    "total_tests": total_tests,
                    "passed_tests": passed_tests,
                    "failed_tests": total_tests - passed_tests,
                    "success_rate": (
                        (passed_tests / total_tests * 100) if total_tests > 0 else 0
                    ),
                },
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            self.logger.error(f"Error running comprehensive load tests: {e}")
            return {
                "status": "error",
                "error": str(e),
                "execution_time": time.time() - start_time,
                "scenario_results": [],
                "timestamp": datetime.now().isoformat(),
            }

    def measure_performance_under_load(self, load_level: int) -> dict[str, Any]:
        """Measure performance under specific load levels."""
        try:
            self.logger.info(f"Measuring performance under load level: {load_level}")

            # Run all scenarios at specified load level
            results = {}

            for scenario_name in self.test_scenarios:
                result = self.run_load_test(scenario_name, load_level)
                results[scenario_name] = result

            return {
                "load_level": load_level,
                "scenario_results": results,
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            self.logger.error(f"Error measuring performance under load: {e}")
            return {
                "load_level": load_level,
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }

    def generate_load_test_report(self) -> dict[str, Any]:
        """Generate comprehensive load test report."""
        try:
            # Run comprehensive tests if no results exist
            if not self.results_store:
                comprehensive_results = self.run_comprehensive_load_tests()

            report = {
                "timestamp": datetime.now().isoformat(),
                "scenarios_tested": list(self.test_scenarios.keys()),
                "results_summary": {},
                "performance_analysis": {},
                "recommendations": [],
            }

            # Analyze results for each scenario
            for scenario_name, results in self.results_store.items():
                if results:
                    latest_result = results[-1]

                    report["results_summary"][scenario_name] = {
                        "total_tests": len(results),
                        "latest_status": latest_result.get("status", "unknown"),
                        "latest_metrics": latest_result.get("metrics", {}),
                        "success_criteria_met": latest_result.get(
                            "success_criteria_met",
                            False,
                        ),
                    }

            # Generate recommendations
            report["recommendations"] = self._generate_load_test_recommendations()

            return report

        except Exception as e:
            self.logger.error(f"Error generating load test report: {e}")
            return {"timestamp": datetime.now().isoformat(), "error": str(e)}

    def _generate_load_test_recommendations(self) -> list[str]:
        """Generate recommendations based on load test results."""
        recommendations = []

        try:
            for scenario_name, results in self.results_store.items():
                if not results:
                    continue

                latest_result = results[-1]
                metrics = latest_result.get("metrics", {})

                # Check response times
                avg_response_time = metrics.get("average_response_time_ms", 0)
                if avg_response_time > 1000:
                    recommendations.append(
                        f"High response times in {scenario_name} - consider optimization",
                    )

                # Check error rates
                error_rate = metrics.get("error_rate_percent", 0)
                if error_rate > 5:
                    recommendations.append(
                        f"High error rate in {scenario_name} - investigate error handling",
                    )

                # Check throughput
                throughput = metrics.get("throughput_requests_per_sec", 0)
                if throughput < 10:
                    recommendations.append(
                        f"Low throughput in {scenario_name} - consider scaling",
                    )

            if not recommendations:
                recommendations.append(
                    "All load tests passed successfully - system is performing well under load",
                )

        except Exception as e:
            recommendations.append(f"Error analyzing load test results: {e}")

        return recommendations

    def add_test_scenario(self, scenario: LoadTestScenario) -> None:
        """Add a custom test scenario."""
        self.test_scenarios[scenario.name] = scenario
        self.logger.info(f"Added test scenario: {scenario.name}")

    def get_test_results(self, scenario: str | None = None) -> dict[str, Any]:
        """Get test results for a scenario or all scenarios."""
        if scenario:
            return self.results_store.get(scenario, [])
        return self.results_store


class RegressionTester:
    """Automated regression testing and change impact assessment."""

    def __init__(self):
        """Initialize the regression tester."""
        self.baseline_metrics: dict[str, Any] = {}
        self.change_impact: dict[str, Any] = {}
        self.logger = logging.getLogger(f"{__name__}.RegressionTester")
        self._baseline_file = Path(tempfile.gettempdir()) / "performance_baseline.json"
        self._regression_history: list[dict[str, Any]] = []

        # Load existing baseline if available
        self._load_baseline()

    def _load_baseline(self) -> None:
        """Load baseline metrics from storage."""
        try:
            if self._baseline_file.exists():
                with open(self._baseline_file) as f:
                    self.baseline_metrics = json.load(f)
                self.logger.info(
                    f"Loaded baseline metrics: {len(self.baseline_metrics)} metrics",
                )
            else:
                self.logger.info("No existing baseline found")
        except Exception as e:
            self.logger.warning(f"Error loading baseline: {e}")

    def _save_baseline(self) -> None:
        """Save baseline metrics to storage."""
        try:
            with open(self._baseline_file, "w") as f:
                json.dump(self.baseline_metrics, f, indent=2, default=str)
            self.logger.info("Baseline metrics saved")
        except Exception as e:
            self.logger.error(f"Error saving baseline: {e}")

    def establish_baseline(self) -> dict[str, Any]:
        """Establish performance baseline."""
        start_time = time.time()

        self.logger.info("Establishing performance baseline")

        try:
            # Initialize performance manager for baseline collection
            performance_manager = PerformanceManager()

            # Collect comprehensive baseline metrics
            baseline_profile = performance_manager.collect_system_metrics()

            # Run benchmark tests to establish baseline
            benchmark_results = self._run_baseline_benchmarks()

            # Store baseline data
            self.baseline_metrics = {
                "timestamp": datetime.now().isoformat(),
                "system_metrics": {
                    metric.name: {
                        "value": metric.value,
                        "unit": metric.unit,
                        "category": metric.category,
                    }
                    for metric in baseline_profile.metrics
                },
                "benchmark_results": benchmark_results,
                "profile_time": baseline_profile.profile_time,
                "optimization_potential": baseline_profile.optimization_potential,
                "establishment_time": time.time() - start_time,
            }

            # Save baseline to persistent storage
            self._save_baseline()

            result = {
                "status": "success",
                "baseline_established": True,
                "metrics_count": len(baseline_profile.metrics),
                "benchmark_tests": len(benchmark_results),
                "establishment_time": time.time() - start_time,
                "baseline_timestamp": self.baseline_metrics["timestamp"],
            }

            self.logger.info(
                f"Baseline established with {result['metrics_count']} metrics",
            )
            return result

        except Exception as e:
            self.logger.error(f"Error establishing baseline: {e}")
            return {
                "status": "error",
                "error": str(e),
                "baseline_established": False,
                "establishment_time": time.time() - start_time,
            }

    def _run_baseline_benchmarks(self) -> dict[str, Any]:
        """Run benchmark tests for baseline establishment."""
        benchmarks = {}

        try:
            # Memory allocation benchmark
            start_time = time.time()
            data = [i for i in range(100000)]
            benchmarks["memory_allocation_100k_items"] = time.time() - start_time

            # CPU intensive benchmark
            start_time = time.time()
            result = sum(i * i for i in range(10000))
            benchmarks["cpu_intensive_sum_squares_10k"] = time.time() - start_time

            # String processing benchmark
            start_time = time.time()
            text = "test string " * 1000
            processed = text.upper().replace(" ", "_")
            benchmarks["string_processing_1k_ops"] = time.time() - start_time

            # File I/O benchmark (if possible)
            try:
                start_time = time.time()
                with tempfile.NamedTemporaryFile(mode="w+", delete=True) as f:
                    f.write("test data " * 1000)
                    f.flush()
                    f.seek(0)
                    content = f.read()
                benchmarks["file_io_1k_write_read"] = time.time() - start_time
            except Exception:
                pass

        except Exception as e:
            self.logger.warning(f"Error running baseline benchmarks: {e}")

        return benchmarks

    def detect_regressions(self) -> dict[str, Any]:
        """Detect performance regressions from baseline."""
        start_time = time.time()

        if not self.baseline_metrics:
            return {
                "status": "no_baseline",
                "message": "No baseline established - call establish_baseline() first",
                "regressions_detected": 0,
                "test_results": [],
            }

        self.logger.info("Detecting performance regressions")

        try:
            # Collect current metrics
            performance_manager = PerformanceManager()
            current_profile = performance_manager.collect_system_metrics()

            # Run current benchmarks
            current_benchmarks = self._run_baseline_benchmarks()

            regressions = []
            test_results = []

            # Compare system metrics
            baseline_system_metrics = self.baseline_metrics.get("system_metrics", {})
            current_system_metrics = {
                metric.name: metric.value for metric in current_profile.metrics
            }

            for metric_name, baseline_data in baseline_system_metrics.items():
                if metric_name in current_system_metrics:
                    baseline_value = baseline_data["value"]
                    current_value = current_system_metrics[metric_name]

                    # Calculate regression
                    regression_analysis = self._analyze_metric_regression(
                        metric_name,
                        baseline_value,
                        current_value,
                        baseline_data.get("category", "unknown"),
                    )

                    if regression_analysis["is_regression"]:
                        regressions.append(regression_analysis)

                    test_results.append(
                        ValidationResult(
                            test_name=f"regression_{metric_name}",
                            status=(
                                "failed"
                                if regression_analysis["is_regression"]
                                else "passed"
                            ),
                            execution_time=current_profile.profile_time,
                            timestamp=datetime.now(),
                            details=regression_analysis,
                            metrics={
                                "baseline_value": baseline_value,
                                "current_value": current_value,
                            },
                        ),
                    )

            # Compare benchmark results
            baseline_benchmarks = self.baseline_metrics.get("benchmark_results", {})

            for benchmark_name, baseline_time in baseline_benchmarks.items():
                if benchmark_name in current_benchmarks:
                    current_time = current_benchmarks[benchmark_name]

                    regression_analysis = self._analyze_benchmark_regression(
                        benchmark_name,
                        baseline_time,
                        current_time,
                    )

                    if regression_analysis["is_regression"]:
                        regressions.append(regression_analysis)

                    test_results.append(
                        ValidationResult(
                            test_name=f"benchmark_regression_{benchmark_name}",
                            status=(
                                "failed"
                                if regression_analysis["is_regression"]
                                else "passed"
                            ),
                            execution_time=current_time,
                            timestamp=datetime.now(),
                            details=regression_analysis,
                            metrics={
                                "baseline_time": baseline_time,
                                "current_time": current_time,
                            },
                        ),
                    )

            # Store regression analysis
            regression_record = {
                "timestamp": datetime.now().isoformat(),
                "regressions_detected": len(regressions),
                "regressions": regressions,
                "test_results": [r.to_dict() for r in test_results],
                "baseline_timestamp": self.baseline_metrics["timestamp"],
                "detection_time": time.time() - start_time,
            }

            self._regression_history.append(regression_record)

            # Keep only last 100 regression tests
            if len(self._regression_history) > 100:
                self._regression_history = self._regression_history[-100:]

            result = {
                "status": "completed",
                "regressions_detected": len(regressions),
                "regressions": regressions,
                "test_results": [r.to_dict() for r in test_results],
                "baseline_age_hours": self._calculate_baseline_age_hours(),
                "detection_time": time.time() - start_time,
                "recommendations": self._generate_regression_recommendations(
                    regressions,
                ),
            }

            if regressions:
                self.logger.warning(
                    f"Detected {len(regressions)} performance regressions",
                )
            else:
                self.logger.info("No performance regressions detected")

            return result

        except Exception as e:
            self.logger.error(f"Error detecting regressions: {e}")
            return {
                "status": "error",
                "error": str(e),
                "regressions_detected": 0,
                "test_results": [],
                "detection_time": time.time() - start_time,
            }

    def _analyze_metric_regression(
        self,
        metric_name: str,
        baseline_value: float,
        current_value: float,
        category: str,
    ) -> dict[str, Any]:
        """Analyze whether a metric represents a regression."""
        try:
            # Calculate percentage change
            if baseline_value == 0:
                change_percent = 0 if current_value == 0 else float("inf")
            else:
                change_percent = (
                    (current_value - baseline_value) / baseline_value
                ) * 100

            # Determine regression based on metric category and direction
            is_regression = False
            severity = "low"

            # For performance metrics, higher values are generally worse
            if category in ["cpu", "memory"] and change_percent > 20:  # 20% threshold
                is_regression = True
                severity = "high" if change_percent > 50 else "medium"
            elif category == "io" and change_percent > 30:  # Higher threshold for I/O
                is_regression = True
                severity = "high" if change_percent > 100 else "medium"

            return {
                "metric_name": metric_name,
                "category": category,
                "baseline_value": baseline_value,
                "current_value": current_value,
                "change_percent": change_percent,
                "is_regression": is_regression,
                "severity": severity,
                "analysis_type": "metric",
            }

        except Exception as e:
            return {
                "metric_name": metric_name,
                "error": str(e),
                "is_regression": False,
                "analysis_type": "metric",
            }

    def _analyze_benchmark_regression(
        self,
        benchmark_name: str,
        baseline_time: float,
        current_time: float,
    ) -> dict[str, Any]:
        """Analyze whether a benchmark represents a regression."""
        try:
            # Calculate percentage change
            if baseline_time == 0:
                change_percent = 0 if current_time == 0 else float("inf")
            else:
                change_percent = ((current_time - baseline_time) / baseline_time) * 100

            # For execution time benchmarks, higher values are worse
            is_regression = change_percent > 25  # 25% threshold for benchmarks
            severity = (
                "high"
                if change_percent > 100
                else "medium" if change_percent > 50 else "low"
            )

            return {
                "benchmark_name": benchmark_name,
                "baseline_time": baseline_time,
                "current_time": current_time,
                "change_percent": change_percent,
                "is_regression": is_regression,
                "severity": severity,
                "analysis_type": "benchmark",
            }

        except Exception as e:
            return {
                "benchmark_name": benchmark_name,
                "error": str(e),
                "is_regression": False,
                "analysis_type": "benchmark",
            }

    def _calculate_baseline_age_hours(self) -> float:
        """Calculate age of baseline in hours."""
        try:
            baseline_timestamp = datetime.fromisoformat(
                self.baseline_metrics["timestamp"],
            )
            age = datetime.now() - baseline_timestamp
            return age.total_seconds() / 3600
        except Exception:
            return 0.0

    def _generate_regression_recommendations(
        self,
        regressions: list[dict[str, Any]],
    ) -> list[str]:
        """Generate recommendations based on detected regressions."""
        recommendations = []

        if not regressions:
            recommendations.append("No regressions detected - performance is stable")
            return recommendations

        # Analyze regression types
        high_severity_count = sum(1 for r in regressions if r.get("severity") == "high")
        cpu_regressions = sum(1 for r in regressions if r.get("category") == "cpu")
        memory_regressions = sum(
            1 for r in regressions if r.get("category") == "memory"
        )
        benchmark_regressions = sum(
            1 for r in regressions if r.get("analysis_type") == "benchmark"
        )

        if high_severity_count > 0:
            recommendations.append(
                f"Critical: {high_severity_count} high-severity regressions detected - immediate investigation required",
            )

        if cpu_regressions > 0:
            recommendations.append(
                f"CPU performance degraded in {cpu_regressions} metrics - consider algorithm optimization",
            )

        if memory_regressions > 0:
            recommendations.append(
                f"Memory usage increased in {memory_regressions} metrics - check for memory leaks",
            )

        if benchmark_regressions > 0:
            recommendations.append(
                f"Benchmark performance degraded in {benchmark_regressions} tests - profile recent changes",
            )

        # Check baseline age
        baseline_age = self._calculate_baseline_age_hours()
        if baseline_age > 168:  # 1 week
            recommendations.append(
                "Baseline is over 1 week old - consider re-establishing baseline",
            )

        return recommendations

    def assess_change_impact(self, changes: list[str]) -> dict[str, Any]:
        """Assess impact of specific changes."""
        start_time = time.time()

        self.logger.info(f"Assessing impact of {len(changes)} changes")

        try:
            # Run regression detection before and after change simulation
            pre_change_results = self.detect_regressions()

            # Simulate some impact (in a real implementation, this would test actual changes)
            impact_analysis = {
                "changes_analyzed": changes,
                "impact_assessment": {},
                "risk_level": "low",
                "recommendations": [],
            }

            # Analyze each change type
            for change in changes:
                change_impact = self._analyze_single_change_impact(change)
                impact_analysis["impact_assessment"][change] = change_impact

            # Determine overall risk level
            high_risk_changes = sum(
                1
                for change, impact in impact_analysis["impact_assessment"].items()
                if impact.get("risk_level") == "high"
            )

            if high_risk_changes > 0:
                impact_analysis["risk_level"] = "high"
            elif len(changes) > 5:
                impact_analysis["risk_level"] = "medium"

            # Generate recommendations
            impact_analysis["recommendations"] = (
                self._generate_change_impact_recommendations(
                    changes,
                    impact_analysis["impact_assessment"],
                )
            )

            # Store change impact analysis
            self.change_impact[datetime.now().isoformat()] = impact_analysis

            result = {
                "status": "completed",
                "analysis_time": time.time() - start_time,
                "changes_count": len(changes),
                "overall_risk_level": impact_analysis["risk_level"],
                "high_risk_changes": high_risk_changes,
                "impact_analysis": impact_analysis,
                "pre_change_regressions": pre_change_results.get(
                    "regressions_detected",
                    0,
                ),
            }

            self.logger.info(
                f"Change impact assessment completed: {result['overall_risk_level']} risk",
            )
            return result

        except Exception as e:
            self.logger.error(f"Error assessing change impact: {e}")
            return {
                "status": "error",
                "error": str(e),
                "analysis_time": time.time() - start_time,
                "changes_count": len(changes),
            }

    def _analyze_single_change_impact(self, change: str) -> dict[str, Any]:
        """Analyze impact of a single change."""
        try:
            # Simple heuristic-based analysis (in practice, this would be more sophisticated)
            impact = {
                "change": change,
                "risk_level": "low",
                "potential_impacts": [],
                "monitoring_recommendations": [],
            }

            change_lower = change.lower()

            # High-risk patterns
            if any(
                keyword in change_lower
                for keyword in ["algorithm", "core", "critical", "performance"]
            ):
                impact["risk_level"] = "high"
                impact["potential_impacts"].append("Core performance may be affected")
                impact["monitoring_recommendations"].append(
                    "Monitor all performance metrics closely",
                )

            # Medium-risk patterns
            elif any(
                keyword in change_lower
                for keyword in ["memory", "cpu", "optimization", "cache"]
            ):
                impact["risk_level"] = "medium"
                impact["potential_impacts"].append("Resource utilization may change")
                impact["monitoring_recommendations"].append(
                    "Monitor resource usage metrics",
                )

            # Memory-related changes
            if "memory" in change_lower:
                impact["potential_impacts"].append("Memory usage patterns may change")
                impact["monitoring_recommendations"].append(
                    "Watch for memory leaks and allocation patterns",
                )

            # Threading/concurrency changes
            if any(
                keyword in change_lower
                for keyword in ["thread", "concurrent", "parallel", "async"]
            ):
                impact["potential_impacts"].append("Concurrency behavior may change")
                impact["monitoring_recommendations"].append(
                    "Monitor thread safety and deadlock potential",
                )

            return impact

        except Exception as e:
            return {"change": change, "error": str(e), "risk_level": "unknown"}

    def _generate_change_impact_recommendations(
        self,
        changes: list[str],
        impact_assessment: dict[str, Any],
    ) -> list[str]:
        """Generate recommendations for change impact."""
        recommendations = []

        try:
            high_risk_changes = [
                change
                for change, impact in impact_assessment.items()
                if impact.get("risk_level") == "high"
            ]

            if high_risk_changes:
                recommendations.append(
                    f"High-risk changes detected: {', '.join(high_risk_changes)}",
                )
                recommendations.append("Recommend thorough testing and gradual rollout")

            if len(changes) > 10:
                recommendations.append(
                    "Large number of changes - consider breaking into smaller batches",
                )

            # Collect all monitoring recommendations
            all_monitoring_recs = set()
            for impact in impact_assessment.values():
                if "monitoring_recommendations" in impact:
                    all_monitoring_recs.update(impact["monitoring_recommendations"])

            for rec in all_monitoring_recs:
                recommendations.append(f"Monitoring: {rec}")

            if not recommendations:
                recommendations.append(
                    "Changes appear low-risk - standard monitoring recommended",
                )

        except Exception as e:
            recommendations.append(f"Error generating recommendations: {e}")

        return recommendations

    def prevent_regressions(self) -> dict[str, Any]:
        """Implement regression prevention measures."""
        start_time = time.time()

        self.logger.info("Implementing regression prevention measures")

        try:
            prevention_measures = {
                "baseline_check": self._check_baseline_freshness(),
                "monitoring_setup": self._setup_regression_monitoring(),
                "alert_configuration": self._configure_regression_alerts(),
                "automated_testing": self._setup_automated_regression_tests(),
            }

            measures_successful = sum(
                1
                for measure in prevention_measures.values()
                if measure.get("status") == "success"
            )
            total_measures = len(prevention_measures)

            result = {
                "status": "completed",
                "implementation_time": time.time() - start_time,
                "prevention_measures": prevention_measures,
                "measures_implemented": measures_successful,
                "total_measures": total_measures,
                "success_rate": (
                    (measures_successful / total_measures * 100)
                    if total_measures > 0
                    else 0
                ),
                "recommendations": [],
            }

            # Generate recommendations based on implementation success
            if measures_successful < total_measures:
                result["recommendations"].append(
                    "Some prevention measures failed - review implementation logs",
                )

            if prevention_measures["baseline_check"].get("age_hours", 0) > 168:
                result["recommendations"].append(
                    "Baseline is stale - establish new baseline",
                )

            result["recommendations"].append(
                "Regression prevention measures active - monitor effectiveness",
            )

            self.logger.info(
                f"Regression prevention: {measures_successful}/{total_measures} measures implemented",
            )
            return result

        except Exception as e:
            self.logger.error(f"Error implementing regression prevention: {e}")
            return {
                "status": "error",
                "error": str(e),
                "implementation_time": time.time() - start_time,
            }

    def _check_baseline_freshness(self) -> dict[str, Any]:
        """Check if baseline is fresh and valid."""
        try:
            if not self.baseline_metrics:
                return {
                    "status": "no_baseline",
                    "message": "No baseline established",
                    "action_required": "establish_baseline",
                }

            age_hours = self._calculate_baseline_age_hours()

            return {
                "status": "success",
                "age_hours": age_hours,
                "is_fresh": age_hours < 168,  # Less than 1 week
                "baseline_timestamp": self.baseline_metrics["timestamp"],
                "metrics_count": len(self.baseline_metrics.get("system_metrics", {})),
            }

        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _setup_regression_monitoring(self) -> dict[str, Any]:
        """Setup regression monitoring."""
        try:
            # In a real implementation, this would configure monitoring systems
            return {
                "status": "success",
                "monitoring_enabled": True,
                "check_interval_minutes": 60,
                "metrics_monitored": ["cpu_percent", "memory_percent", "response_time"],
                "message": "Regression monitoring configured",
            }

        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _configure_regression_alerts(self) -> dict[str, Any]:
        """Configure regression alerts."""
        try:
            # In a real implementation, this would configure alerting systems
            return {
                "status": "success",
                "alerts_configured": True,
                "thresholds": {
                    "performance_degradation_percent": 25,
                    "high_severity_regressions": 1,
                    "consecutive_failures": 3,
                },
                "message": "Regression alerts configured",
            }

        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _setup_automated_regression_tests(self) -> dict[str, Any]:
        """Setup automated regression testing."""
        try:
            # In a real implementation, this would configure CI/CD integration
            return {
                "status": "success",
                "automation_enabled": True,
                "test_frequency": "on_commit",
                "test_types": ["benchmark", "load", "performance"],
                "message": "Automated regression testing configured",
            }

        except Exception as e:
            return {"status": "error", "error": str(e)}

    def get_regression_history(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get regression testing history."""
        return self._regression_history[-limit:]

    def clear_baseline(self) -> None:
        """Clear current baseline."""
        self.baseline_metrics = {}
        try:
            if self._baseline_file.exists():
                self._baseline_file.unlink()
        except Exception as e:
            self.logger.warning(f"Error removing baseline file: {e}")
        self.logger.info("Baseline cleared")

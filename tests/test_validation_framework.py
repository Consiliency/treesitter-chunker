# tests/test_validation_framework.py

import json
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from chunker.validation.validation_framework import (
    LoadTester,
    LoadTestScenario,
    PerformanceValidator,
    RegressionTester,
    ValidationManager,
    ValidationResult,
)


class TestValidationResult:
    """Test ValidationResult class."""

    def test_validation_result_creation(self):
        """Test creating a validation result."""
        result = ValidationResult(
            test_name="test_performance",
            status="passed",
            execution_time=1.5,
            timestamp=datetime.now(),
            details={"metric": "value"},
            metrics={"time": 1.5},
        )

        assert result.test_name == "test_performance"
        assert result.status == "passed"
        assert result.execution_time == 1.5
        assert result.details == {"metric": "value"}
        assert result.metrics == {"time": 1.5}

    def test_validation_result_to_dict(self):
        """Test converting validation result to dictionary."""
        timestamp = datetime.now()
        result = ValidationResult(
            test_name="test_performance",
            status="passed",
            execution_time=1.5,
            timestamp=timestamp,
            details={"metric": "value"},
        )

        result_dict = result.to_dict()

        assert result_dict["test_name"] == "test_performance"
        assert result_dict["status"] == "passed"
        assert result_dict["execution_time"] == 1.5
        assert result_dict["timestamp"] == timestamp.isoformat()
        assert result_dict["details"] == {"metric": "value"}


class TestLoadTestScenario:
    """Test LoadTestScenario class."""

    def test_load_test_scenario_creation(self):
        """Test creating a load test scenario."""

        def mock_function():
            return "test"

        def mock_generator():
            return "test_data"

        scenario = LoadTestScenario(
            name="test_scenario",
            description="Test scenario",
            target_function=mock_function,
            load_levels=[1, 5, 10],
            duration_seconds=10.0,
            ramp_up_seconds=2.0,
            success_criteria={"max_response_time_ms": 1000},
            test_data_generator=mock_generator,
        )

        assert scenario.name == "test_scenario"
        assert scenario.description == "Test scenario"
        assert scenario.target_function == mock_function
        assert scenario.load_levels == [1, 5, 10]
        assert scenario.duration_seconds == 10.0
        assert scenario.ramp_up_seconds == 2.0
        assert scenario.success_criteria == {"max_response_time_ms": 1000}

    def test_generate_test_data(self):
        """Test generating test data."""

        def mock_generator():
            return "generated_data"

        scenario = LoadTestScenario(
            name="test",
            description="Test",
            target_function=lambda: None,
            load_levels=[1],
            duration_seconds=1.0,
            ramp_up_seconds=0.0,
            success_criteria={},
            test_data_generator=mock_generator,
        )

        data = scenario.generate_test_data()
        assert data == "generated_data"

    def test_generate_test_data_no_generator(self):
        """Test generating test data with no generator."""
        scenario = LoadTestScenario(
            name="test",
            description="Test",
            target_function=lambda: None,
            load_levels=[1],
            duration_seconds=1.0,
            ramp_up_seconds=0.0,
            success_criteria={},
        )

        data = scenario.generate_test_data()
        assert data is None


class TestValidationManager:
    """Test ValidationManager class."""

    def setup_method(self):
        """Setup test fixtures."""
        self.validation_manager = ValidationManager()

    def test_validation_manager_initialization(self):
        """Test validation manager initialization."""
        assert self.validation_manager.performance_validator is not None
        assert self.validation_manager.load_tester is not None
        assert self.validation_manager.regression_tester is not None
        assert hasattr(self.validation_manager, "config")
        assert isinstance(self.validation_manager._validation_history, list)

    @patch(
        "chunker.validation.validation_framework.PerformanceValidator.validate_performance_benchmarks",
    )
    def test_validate_performance(self, mock_validate):
        """Test performance validation."""
        mock_validate.return_value = {
            "status": "completed",
            "test_results": [],
            "overall_health": "good",
        }

        result = self.validation_manager.validate_performance()

        assert result["status"] == "completed"
        assert result["overall_health"] == "good"
        mock_validate.assert_called_once()

    @patch(
        "chunker.validation.validation_framework.LoadTester.run_comprehensive_load_tests",
    )
    def test_run_load_tests(self, mock_load_tests):
        """Test load testing."""
        mock_load_tests.return_value = {"status": "completed", "scenario_results": []}

        result = self.validation_manager.run_load_tests()

        assert result["status"] == "completed"
        mock_load_tests.assert_called_once()

    @patch(
        "chunker.validation.validation_framework.RegressionTester.detect_regressions",
    )
    def test_run_regression_tests(self, mock_regression):
        """Test regression testing."""
        mock_regression.return_value = {
            "status": "completed",
            "regressions_detected": 0,
            "test_results": [],
        }

        result = self.validation_manager.run_regression_tests()

        assert result["status"] == "completed"
        assert result["regressions_detected"] == 0
        mock_regression.assert_called_once()

    def test_run_full_validation(self):
        """Test full validation suite."""
        with (
            patch.object(self.validation_manager, "validate_performance") as mock_perf,
            patch.object(self.validation_manager, "run_load_tests") as mock_load,
            patch.object(
                self.validation_manager,
                "run_regression_tests",
            ) as mock_regression,
        ):

            mock_perf.return_value = {"test_results": [{"status": "passed"}]}
            mock_load.return_value = {"test_results": [{"status": "passed"}]}
            mock_regression.return_value = {"test_results": [{"status": "passed"}]}

            result = self.validation_manager.run_full_validation()

            assert "validation_id" in result
            assert result["status"] == "passed"
            assert "results" in result
            assert "performance" in result["results"]
            assert "load" in result["results"]
            assert "regression" in result["results"]
            assert result["summary"]["total_tests"] == 3
            assert result["summary"]["passed"] == 3

    def test_run_full_validation_specific_components(self):
        """Test full validation with specific components."""
        with patch.object(self.validation_manager, "validate_performance") as mock_perf:
            mock_perf.return_value = {"test_results": [{"status": "passed"}]}

            result = self.validation_manager.run_full_validation(
                components=["performance"],
            )

            assert "performance" in result["results"]
            assert "load" not in result["results"]
            assert "regression" not in result["results"]

    def test_generate_validation_recommendations(self):
        """Test validation recommendation generation."""
        validation_report = {
            "summary": {"passed": 5, "failed": 2, "errors": 1},
            "results": {
                "performance": {"overall_health": "critical"},
                "load": {"scenario_results": [{"status": "failed"}]},
                "regression": {"regressions_detected": 2},
            },
        }

        recommendations = self.validation_manager._generate_validation_recommendations(
            validation_report,
        )

        assert len(recommendations) > 0
        assert any("errors detected" in rec for rec in recommendations)
        assert any("performance issues" in rec for rec in recommendations)

    def test_get_validation_history(self):
        """Test getting validation history."""
        # Add some mock history
        self.validation_manager._validation_history = [
            {"validation_id": "1", "timestamp": "2023-01-01T00:00:00"},
            {"validation_id": "2", "timestamp": "2023-01-02T00:00:00"},
            {"validation_id": "3", "timestamp": "2023-01-03T00:00:00"},
        ]

        history = self.validation_manager.get_validation_history(limit=2)

        assert len(history) == 2
        assert history[0]["validation_id"] == "2"
        assert history[1]["validation_id"] == "3"

    def test_clear_validation_history(self):
        """Test clearing validation history."""
        self.validation_manager._validation_history = ["test1", "test2"]

        self.validation_manager.clear_validation_history()

        assert len(self.validation_manager._validation_history) == 0


class TestPerformanceValidator:
    """Test PerformanceValidator class."""

    def setup_method(self):
        """Setup test fixtures."""
        with patch("chunker.validation.validation_framework.PerformanceManager"):
            self.validator = PerformanceValidator()

    def test_performance_validator_initialization(self):
        """Test performance validator initialization."""
        assert hasattr(self.validator, "benchmarks")
        assert hasattr(self.validator, "sla_requirements")
        assert "response_time_ms" in self.validator.sla_requirements
        assert "chunking_performance" in self.validator.benchmarks

    @patch("chunker.validation.validation_framework.PerformanceManager")
    def test_validate_performance_benchmarks(self, mock_manager_class):
        """Test performance benchmark validation."""
        mock_manager = Mock()
        mock_profile = Mock()
        mock_profile.optimization_potential = 25.0
        mock_profile.recommendations = ["Test recommendation"]
        mock_profile.get_critical_metrics.return_value = []
        mock_profile.get_metrics_by_category.return_value = []
        mock_profile.profile_time = 0.1

        mock_manager.collect_system_metrics.return_value = mock_profile
        mock_manager_class.return_value = mock_manager

        validator = PerformanceValidator()

        with (
            patch.object(validator, "_test_chunking_performance") as mock_chunking,
            patch.object(validator, "_test_parsing_performance") as mock_parsing,
            patch.object(validator, "_test_system_performance") as mock_system,
        ):

            mock_chunking.return_value = [
                ValidationResult(
                    test_name="test_chunking",
                    status="passed",
                    execution_time=0.1,
                    timestamp=datetime.now(),
                    details={},
                ),
            ]
            mock_parsing.return_value = [
                ValidationResult(
                    test_name="test_parsing",
                    status="passed",
                    execution_time=0.05,
                    timestamp=datetime.now(),
                    details={},
                ),
            ]
            mock_system.return_value = [
                ValidationResult(
                    test_name="test_system",
                    status="passed",
                    execution_time=0.1,
                    timestamp=datetime.now(),
                    details={},
                ),
            ]

            result = validator.validate_performance_benchmarks()

            assert result["status"] == "completed"
            assert result["overall_health"] == "good"
            assert result["summary"]["total_tests"] == 3
            assert result["summary"]["passed"] == 3

    def test_test_chunking_performance(self):
        """Test chunking performance testing."""
        results = self.validator._test_chunking_performance()

        assert len(results) >= 1
        assert all(isinstance(r, ValidationResult) for r in results)
        assert any(r.test_name == "chunking_max_time" for r in results)

    def test_test_parsing_performance(self):
        """Test parsing performance testing."""
        results = self.validator._test_parsing_performance()

        assert len(results) >= 1
        assert all(isinstance(r, ValidationResult) for r in results)
        assert any(r.test_name == "parsing_max_time" for r in results)

    def test_validate_performance_sla(self):
        """Test SLA validation."""
        with patch.object(
            self.validator.performance_manager,
            "collect_system_metrics",
        ) as mock_collect:
            mock_profile = Mock()
            mock_metric = Mock()
            mock_metric.name = "cpu_percent"
            mock_metric.value = 50.0
            mock_profile.metrics = [mock_metric]
            mock_profile.profile_time = 0.1

            mock_collect.return_value = mock_profile

            result = self.validator.validate_performance_sla()

            assert result["status"] == "completed"
            assert "sla_results" in result

    def test_detect_performance_regressions(self):
        """Test performance regression detection."""
        # Mock baseline profile
        baseline_profile = Mock()
        baseline_metric = Mock()
        baseline_metric.name = "cpu_percent"
        baseline_metric.value = 50.0
        baseline_profile.metrics = [baseline_metric]

        with patch.object(
            self.validator.performance_manager,
            "collect_system_metrics",
        ) as mock_collect:
            current_profile = Mock()
            current_metric = Mock()
            current_metric.name = "cpu_percent"
            current_metric.value = 80.0  # 60% increase - should trigger regression
            current_profile.metrics = [current_metric]

            mock_collect.return_value = current_profile

            regressions = self.validator.detect_performance_regressions(
                baseline_profile,
            )

            assert len(regressions) == 1
            assert regressions[0]["metric_name"] == "cpu_percent"
            assert regressions[0]["change_percent"] == 60.0

    def test_generate_performance_report(self):
        """Test performance report generation."""
        with (
            patch.object(
                self.validator,
                "validate_performance_benchmarks",
            ) as mock_bench,
            patch.object(self.validator, "validate_performance_sla") as mock_sla,
            patch.object(
                self.validator,
                "detect_performance_regressions",
            ) as mock_regression,
        ):

            mock_bench.return_value = {"overall_health": "good"}
            mock_sla.return_value = {"sla_compliance": True}
            mock_regression.return_value = []

            report = self.validator.generate_performance_report()

            assert "timestamp" in report
            assert "benchmark_validation" in report
            assert "sla_validation" in report
            assert "regression_analysis" in report
            assert report["overall_status"] == "healthy"


class TestLoadTester:
    """Test LoadTester class."""

    def setup_method(self):
        """Setup test fixtures."""
        self.load_tester = LoadTester()

    def test_load_tester_initialization(self):
        """Test load tester initialization."""
        assert len(self.load_tester.test_scenarios) > 0
        assert "basic_processing" in self.load_tester.test_scenarios
        assert "memory_intensive" in self.load_tester.test_scenarios
        assert "high_concurrency" in self.load_tester.test_scenarios

    def test_mock_processing_function(self):
        """Test mock processing function."""
        result = self.load_tester._mock_processing_function()

        assert result["result"] == "success"
        assert "execution_time" in result
        assert "processed_data" in result

    def test_mock_memory_intensive_function(self):
        """Test mock memory intensive function."""
        result = self.load_tester._mock_memory_intensive_function()

        assert result["result"] == "success"
        assert "execution_time" in result
        assert "memory_allocated" in result

    def test_mock_concurrent_function(self):
        """Test mock concurrent function."""
        result = self.load_tester._mock_concurrent_function()

        assert result["result"] == "success"
        assert "execution_time" in result
        assert "thread_id" in result

    def test_run_load_test(self):
        """Test running a load test."""
        result = self.load_tester.run_load_test("basic_processing", 1)

        assert result["scenario"] == "basic_processing"
        assert result["load_level"] == 1
        assert result["status"] in ["passed", "failed"]
        assert "metrics" in result
        assert "timestamp" in result

    def test_run_load_test_unknown_scenario(self):
        """Test running load test with unknown scenario."""
        result = self.load_tester.run_load_test("unknown_scenario", 1)

        assert "error" in result
        assert "Unknown scenario" in result["error"]

    def test_execute_single_request(self):
        """Test executing single request."""

        def test_function(data):
            return {"result": "test_success"}

        result = self.load_tester._execute_single_request(test_function, None, 1)

        assert result["request_id"] == 1
        assert result["status"] == "success"
        assert "execution_time" in result
        assert result["result"]["result"] == "test_success"

    def test_execute_single_request_with_error(self):
        """Test executing single request that raises error."""

        def failing_function(data):
            raise ValueError("Test error")

        result = self.load_tester._execute_single_request(failing_function, None, 1)

        assert result["request_id"] == 1
        assert result["status"] == "error"
        assert result["error"] == "Test error"
        assert result["error_type"] == "ValueError"

    def test_check_success_criteria(self):
        """Test checking success criteria."""
        criteria = {
            "max_response_time_ms": 1000,
            "min_success_rate_percent": 95,
            "max_error_rate_percent": 5,
        }

        metrics = {
            "max_response_time_ms": 500,
            "success_rate_percent": 98,
            "error_rate_percent": 2,
        }

        result = self.load_tester._check_success_criteria(criteria, metrics)
        assert result is True

        # Test failing criteria
        metrics["max_response_time_ms"] = 1500
        result = self.load_tester._check_success_criteria(criteria, metrics)
        assert result is False

    def test_run_stress_test(self):
        """Test running stress test."""
        # Use a quick scenario for testing
        self.load_tester.test_scenarios["test_quick"] = LoadTestScenario(
            name="test_quick",
            description="Quick test",
            target_function=lambda: {"result": "success"},
            load_levels=[1, 2],
            duration_seconds=0.1,
            ramp_up_seconds=0.0,
            success_criteria={"max_response_time_ms": 1000},
        )

        result = self.load_tester.run_stress_test("test_quick")

        assert result["scenario"] == "test_quick"
        assert result["status"] == "completed"
        assert "breaking_point_load_level" in result
        assert "stress_test_results" in result

    def test_run_comprehensive_load_tests(self):
        """Test running comprehensive load tests."""
        # Modify scenarios to be very quick for testing
        for scenario in self.load_tester.test_scenarios.values():
            scenario.duration_seconds = 0.1
            scenario.load_levels = [1]

        result = self.load_tester.run_comprehensive_load_tests()

        assert result["status"] == "completed"
        assert "scenario_results" in result
        assert "summary" in result
        assert len(result["scenario_results"]) > 0

    def test_measure_performance_under_load(self):
        """Test measuring performance under load."""
        # Modify scenarios to be very quick for testing
        for scenario in self.load_tester.test_scenarios.values():
            scenario.duration_seconds = 0.1

        result = self.load_tester.measure_performance_under_load(1)

        assert result["load_level"] == 1
        assert "scenario_results" in result
        assert len(result["scenario_results"]) > 0

    def test_add_test_scenario(self):
        """Test adding custom test scenario."""
        scenario = LoadTestScenario(
            name="custom_test",
            description="Custom test scenario",
            target_function=lambda: {"result": "success"},
            load_levels=[1, 5],
            duration_seconds=1.0,
            ramp_up_seconds=0.0,
            success_criteria={},
        )

        self.load_tester.add_test_scenario(scenario)

        assert "custom_test" in self.load_tester.test_scenarios
        assert self.load_tester.test_scenarios["custom_test"] == scenario

    def test_get_test_results(self):
        """Test getting test results."""
        # Add some mock results
        self.load_tester.results_store["test_scenario"] = [
            {"test": "result1"},
            {"test": "result2"},
        ]

        # Test getting specific scenario results
        results = self.load_tester.get_test_results("test_scenario")
        assert len(results) == 2
        assert results[0]["test"] == "result1"

        # Test getting all results
        all_results = self.load_tester.get_test_results()
        assert "test_scenario" in all_results

    def test_generate_load_test_recommendations(self):
        """Test generating load test recommendations."""
        # Add mock results with high response times
        self.load_tester.results_store["test_scenario"] = [
            {
                "metrics": {
                    "average_response_time_ms": 1500,
                    "error_rate_percent": 8,
                    "throughput_requests_per_sec": 5,
                },
            },
        ]

        recommendations = self.load_tester._generate_load_test_recommendations()

        assert len(recommendations) > 0
        assert any("High response times" in rec for rec in recommendations)
        assert any("High error rate" in rec for rec in recommendations)
        assert any("Low throughput" in rec for rec in recommendations)


class TestRegressionTester:
    """Test RegressionTester class."""

    def setup_method(self):
        """Setup test fixtures."""
        self.regression_tester = RegressionTester()

    def test_regression_tester_initialization(self):
        """Test regression tester initialization."""
        assert hasattr(self.regression_tester, "baseline_metrics")
        assert hasattr(self.regression_tester, "change_impact")
        assert hasattr(self.regression_tester, "_baseline_file")
        assert hasattr(self.regression_tester, "_regression_history")

    def test_run_baseline_benchmarks(self):
        """Test running baseline benchmarks."""
        benchmarks = self.regression_tester._run_baseline_benchmarks()

        assert len(benchmarks) > 0
        assert "memory_allocation_100k_items" in benchmarks
        assert "cpu_intensive_sum_squares_10k" in benchmarks
        assert "string_processing_1k_ops" in benchmarks
        assert all(isinstance(v, (int, float)) for v in benchmarks.values())

    @patch("chunker.validation.validation_framework.PerformanceManager")
    def test_establish_baseline(self, mock_manager_class):
        """Test establishing performance baseline."""
        mock_manager = Mock()
        mock_profile = Mock()
        mock_metric = Mock()
        mock_metric.name = "test_metric"
        mock_metric.value = 50.0
        mock_metric.unit = "%"
        mock_metric.category = "cpu"
        mock_profile.metrics = [mock_metric]
        mock_profile.profile_time = 0.1
        mock_profile.optimization_potential = 25.0

        mock_manager.collect_system_metrics.return_value = mock_profile
        mock_manager_class.return_value = mock_manager

        result = self.regression_tester.establish_baseline()

        assert result["status"] == "success"
        assert result["baseline_established"] is True
        assert result["metrics_count"] == 1
        assert "baseline_timestamp" in result

        # Check that baseline was stored
        assert len(self.regression_tester.baseline_metrics) > 0
        assert "system_metrics" in self.regression_tester.baseline_metrics

    def test_detect_regressions_no_baseline(self):
        """Test regression detection without baseline."""
        self.regression_tester.baseline_metrics = {}

        result = self.regression_tester.detect_regressions()

        assert result["status"] == "no_baseline"
        assert result["regressions_detected"] == 0

    @patch("chunker.validation.validation_framework.PerformanceManager")
    def test_detect_regressions_with_baseline(self, mock_manager_class):
        """Test regression detection with baseline."""
        # Setup baseline
        self.regression_tester.baseline_metrics = {
            "timestamp": datetime.now().isoformat(),
            "system_metrics": {
                "cpu_percent": {"value": 50.0, "unit": "%", "category": "cpu"},
            },
            "benchmark_results": {"test_benchmark": 0.1},
        }

        # Setup current metrics (with regression)
        mock_manager = Mock()
        mock_profile = Mock()
        mock_metric = Mock()
        mock_metric.name = "cpu_percent"
        mock_metric.value = 90.0  # 80% increase
        mock_profile.metrics = [mock_metric]
        mock_profile.profile_time = 0.1

        mock_manager.collect_system_metrics.return_value = mock_profile
        mock_manager_class.return_value = mock_manager

        with patch.object(
            self.regression_tester,
            "_run_baseline_benchmarks",
        ) as mock_benchmarks:
            mock_benchmarks.return_value = {"test_benchmark": 0.15}  # 50% increase

            result = self.regression_tester.detect_regressions()

            assert result["status"] == "completed"
            assert result["regressions_detected"] > 0
            assert len(result["regressions"]) > 0

    def test_analyze_metric_regression(self):
        """Test analyzing metric regression."""
        analysis = self.regression_tester._analyze_metric_regression(
            "cpu_percent",
            50.0,
            80.0,
            "cpu",
        )

        assert analysis["metric_name"] == "cpu_percent"
        assert analysis["baseline_value"] == 50.0
        assert analysis["current_value"] == 80.0
        assert analysis["change_percent"] == 60.0
        assert analysis["is_regression"] is True
        assert analysis["severity"] == "high"

    def test_analyze_benchmark_regression(self):
        """Test analyzing benchmark regression."""
        analysis = self.regression_tester._analyze_benchmark_regression(
            "test_benchmark",
            0.1,
            0.15,
        )

        assert analysis["benchmark_name"] == "test_benchmark"
        assert analysis["baseline_time"] == 0.1
        assert analysis["current_time"] == 0.15
        assert (
            abs(analysis["change_percent"] - 50.0) < 0.001
        )  # Allow for floating point precision
        assert analysis["is_regression"] is True
        assert (
            analysis["severity"] == "low"
        )  # 50% is exactly the boundary, so it's 'low'

        # Test medium severity (> 50%)
        analysis_medium = self.regression_tester._analyze_benchmark_regression(
            "test_benchmark",
            0.1,
            0.16,
        )
        assert analysis_medium["severity"] == "medium"

        # Test high severity (> 100%)
        analysis_high = self.regression_tester._analyze_benchmark_regression(
            "test_benchmark",
            0.1,
            0.25,
        )
        assert analysis_high["severity"] == "high"

    def test_assess_change_impact(self):
        """Test assessing change impact."""
        changes = [
            "algorithm optimization",
            "memory management update",
            "ui improvement",
        ]

        result = self.regression_tester.assess_change_impact(changes)

        assert result["status"] == "completed"
        assert result["changes_count"] == 3
        assert "overall_risk_level" in result
        assert "impact_analysis" in result
        assert len(result["impact_analysis"]["changes_analyzed"]) == 3

    def test_analyze_single_change_impact(self):
        """Test analyzing single change impact."""
        # High risk change
        impact = self.regression_tester._analyze_single_change_impact(
            "core algorithm rewrite",
        )
        assert impact["risk_level"] == "high"
        assert len(impact["potential_impacts"]) > 0

        # Medium risk change
        impact = self.regression_tester._analyze_single_change_impact(
            "memory optimization",
        )
        assert impact["risk_level"] == "medium"

        # Low risk change
        impact = self.regression_tester._analyze_single_change_impact("ui color update")
        assert impact["risk_level"] == "low"

    def test_prevent_regressions(self):
        """Test implementing regression prevention."""
        result = self.regression_tester.prevent_regressions()

        assert result["status"] == "completed"
        assert "prevention_measures" in result
        assert "measures_implemented" in result
        assert "success_rate" in result
        assert len(result["recommendations"]) > 0

    def test_baseline_file_operations(self):
        """Test baseline file save/load operations."""
        # Create temporary baseline
        original_baseline = {
            "timestamp": datetime.now().isoformat(),
            "system_metrics": {"test_metric": {"value": 100}},
            "benchmark_results": {"test_bench": 0.5},
        }

        # Test saving
        self.regression_tester.baseline_metrics = original_baseline
        self.regression_tester._save_baseline()

        # Test loading
        self.regression_tester.baseline_metrics = {}
        self.regression_tester._load_baseline()

        assert self.regression_tester.baseline_metrics == original_baseline

    def test_calculate_baseline_age_hours(self):
        """Test calculating baseline age."""
        # Recent baseline
        recent_time = datetime.now() - timedelta(hours=2)
        self.regression_tester.baseline_metrics = {"timestamp": recent_time.isoformat()}

        age = self.regression_tester._calculate_baseline_age_hours()
        assert 1.5 < age < 2.5  # Should be around 2 hours

    def test_generate_regression_recommendations(self):
        """Test generating regression recommendations."""
        regressions = [
            {"severity": "high", "category": "cpu", "analysis_type": "metric"},
            {"severity": "medium", "category": "memory", "analysis_type": "benchmark"},
        ]

        recommendations = self.regression_tester._generate_regression_recommendations(
            regressions,
        )

        assert len(recommendations) > 0
        assert any("high-severity regressions" in rec for rec in recommendations)
        assert any("CPU performance" in rec for rec in recommendations)
        assert any("Memory usage" in rec for rec in recommendations)

    def test_get_regression_history(self):
        """Test getting regression history."""
        # Add mock history
        self.regression_tester._regression_history = [
            {"test": "regression1"},
            {"test": "regression2"},
            {"test": "regression3"},
        ]

        history = self.regression_tester.get_regression_history(limit=2)

        assert len(history) == 2
        assert history[0]["test"] == "regression2"
        assert history[1]["test"] == "regression3"

    def test_clear_baseline(self):
        """Test clearing baseline."""
        self.regression_tester.baseline_metrics = {"test": "data"}

        self.regression_tester.clear_baseline()

        assert len(self.regression_tester.baseline_metrics) == 0


class TestValidationFrameworkIntegration:
    """Integration tests for validation framework."""

    def test_full_validation_integration(self):
        """Test full validation integration."""
        validation_manager = ValidationManager()

        # Run a minimal validation (with quick settings)
        for scenario in validation_manager.load_tester.test_scenarios.values():
            scenario.duration_seconds = 0.1
            scenario.load_levels = [1]

        result = validation_manager.run_full_validation()

        assert "validation_id" in result
        assert result["status"] in ["passed", "failed", "error"]
        assert "results" in result
        assert "summary" in result
        assert "recommendations" in result

    def test_performance_and_regression_integration(self):
        """Test integration between performance validation and regression testing."""
        performance_validator = PerformanceValidator()
        regression_tester = RegressionTester()

        # Establish baseline
        baseline_result = regression_tester.establish_baseline()
        assert baseline_result["status"] == "success"

        # Run performance validation
        with patch("chunker.validation.validation_framework.PerformanceManager"):
            perf_result = performance_validator.validate_performance_benchmarks()
            assert perf_result["status"] == "completed"

        # Check for regressions
        regression_result = regression_tester.detect_regressions()
        assert regression_result["status"] in ["completed", "no_baseline"]

    def test_load_testing_and_performance_integration(self):
        """Test integration between load testing and performance validation."""
        load_tester = LoadTester()
        performance_validator = PerformanceValidator()

        # Configure quick load test
        for scenario in load_tester.test_scenarios.values():
            scenario.duration_seconds = 0.1
            scenario.load_levels = [1]

        # Run load test
        load_result = load_tester.run_load_test("basic_processing", 1)
        assert load_result["status"] in ["passed", "failed"]

        # Validate performance during load
        with patch("chunker.validation.validation_framework.PerformanceManager"):
            perf_result = performance_validator.validate_performance_benchmarks()
            assert perf_result["status"] == "completed"

    def test_validation_error_handling(self):
        """Test error handling in validation framework."""
        validation_manager = ValidationManager()

        # Test with mocked failures
        with patch.object(
            validation_manager,
            "validate_performance",
            side_effect=Exception("Performance error"),
        ):
            result = validation_manager.run_full_validation(components=["performance"])

            assert result["status"] == "error"
            assert "error" in result


if __name__ == "__main__":
    pytest.main([__file__])

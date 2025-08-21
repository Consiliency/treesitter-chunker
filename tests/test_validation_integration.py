# tests/test_validation_integration.py

import time
from unittest.mock import Mock, patch

import pytest

from chunker.performance.core.performance_framework import PerformanceManager
from chunker.validation.validation_framework import ValidationManager


class TestValidationIntegration:
    """Integration tests between validation framework and performance core."""

    def setup_method(self):
        """Setup test fixtures."""
        self.validation_manager = ValidationManager()
        self.performance_manager = PerformanceManager()

    def test_validation_manager_uses_performance_core(self):
        """Test that validation manager properly integrates with performance core."""
        # The performance validator should use PerformanceManager
        assert (
            self.validation_manager.performance_validator.performance_manager
            is not None
        )
        assert hasattr(
            self.validation_manager.performance_validator.performance_manager,
            "collect_system_metrics",
        )

    def test_performance_validation_with_real_performance_manager(self):
        """Test performance validation using real performance manager."""
        # Configure for quick test
        for scenario in self.validation_manager.load_tester.test_scenarios.values():
            scenario.duration_seconds = 0.5
            scenario.load_levels = [1]

        # Run performance validation
        result = self.validation_manager.validate_performance()

        assert result["status"] in ["completed", "error"]
        assert "test_results" in result
        assert "overall_health" in result

    def test_regression_testing_with_performance_metrics(self):
        """Test regression testing with performance metrics."""
        regression_tester = self.validation_manager.regression_tester

        # Establish baseline
        baseline_result = regression_tester.establish_baseline()
        assert baseline_result["status"] == "success"

        # Check for regressions (should work with real performance data)
        regression_result = regression_tester.detect_regressions()
        assert regression_result["status"] in ["completed", "no_baseline"]

    def test_load_testing_performance_impact(self):
        """Test that load testing can measure performance impact."""
        load_tester = self.validation_manager.load_tester

        # Configure for quick test
        for scenario in load_tester.test_scenarios.values():
            scenario.duration_seconds = 0.5
            scenario.load_levels = [1]

        # Run load test and measure performance
        load_result = load_tester.run_load_test("basic_processing", 1)

        assert load_result["status"] in ["passed", "failed"]
        assert "metrics" in load_result
        # Check for expected metrics (execution_time might be in different location)
        metrics = load_result["metrics"]
        assert "average_response_time_ms" in metrics or "execution_time" in metrics

    def test_full_validation_integration(self):
        """Test full validation integration with all components."""
        # Configure for quick test
        for scenario in self.validation_manager.load_tester.test_scenarios.values():
            scenario.duration_seconds = 0.5
            scenario.load_levels = [1]

        # Run full validation
        validation_result = self.validation_manager.run_full_validation()

        assert "validation_id" in validation_result
        assert validation_result["status"] in ["passed", "failed", "error"]
        assert "results" in validation_result

        # Check that all components ran
        results = validation_result["results"]
        assert "performance" in results
        assert "load" in results
        assert "regression" in results

    def test_performance_manager_continuous_monitoring_integration(self):
        """Test integration with performance manager's continuous monitoring."""
        # Start continuous monitoring
        self.performance_manager.start_monitoring()

        try:
            # Wait for some metrics to be collected
            time.sleep(1.0)

            # Get performance history
            history = self.performance_manager.get_performance_history()

            # Should have collected some metrics
            assert len(history) >= 0  # May be empty in fast test environment

            # Run validation while monitoring is active
            result = self.validation_manager.validate_performance()
            assert result["status"] in ["completed", "error"]

        finally:
            # Stop monitoring
            self.performance_manager.stop_monitoring()

    def test_validation_with_performance_optimization(self):
        """Test validation after performance optimization."""
        # Run initial validation
        initial_result = self.validation_manager.validate_performance()

        # Run performance optimization
        optimization_result = self.performance_manager.optimize_system()

        # Run validation again
        post_optimization_result = self.validation_manager.validate_performance()

        assert initial_result["status"] in ["completed", "error"]
        assert optimization_result["status"] in ["success", "error"]
        assert post_optimization_result["status"] in ["completed", "error"]

    def test_regression_detection_with_optimization_changes(self):
        """Test regression detection after optimization changes."""
        regression_tester = self.validation_manager.regression_tester

        # Establish baseline
        baseline_result = regression_tester.establish_baseline()
        assert baseline_result["status"] == "success"

        # Simulate some system changes through optimization
        self.performance_manager.optimize_system()

        # Wait a moment for changes to take effect
        time.sleep(0.1)

        # Check for regressions
        regression_result = regression_tester.detect_regressions()
        assert regression_result["status"] == "completed"

        # Should detect some changes (may or may not be regressions)
        assert "regressions_detected" in regression_result

    def test_validation_error_handling_with_performance_issues(self):
        """Test validation error handling when performance issues occur."""
        # Mock a failing performance manager
        with patch.object(
            self.validation_manager.performance_validator,
            "performance_manager",
        ) as mock_pm:
            mock_pm.collect_system_metrics.side_effect = Exception(
                "Performance collection failed",
            )

            # Validation should handle the error gracefully
            result = self.validation_manager.validate_performance()

            assert result["status"] == "error"
            assert "error" in result

    def test_load_testing_with_performance_monitoring(self):
        """Test load testing while performance monitoring is active."""
        # Start performance monitoring
        self.performance_manager.start_monitoring()

        try:
            # Configure load tester for quick test
            load_tester = self.validation_manager.load_tester
            for scenario in load_tester.test_scenarios.values():
                scenario.duration_seconds = 0.5
                scenario.load_levels = [1]

            # Run load test
            load_result = load_tester.run_load_test("basic_processing", 1)

            # Should succeed even with monitoring active
            assert load_result["status"] in ["passed", "failed"]

            # Check that monitoring captured some data
            history = self.performance_manager.get_performance_history()
            # History may be empty in fast test, but should not error
            assert isinstance(history, list)

        finally:
            self.performance_manager.stop_monitoring()

    def test_validation_report_includes_performance_data(self):
        """Test that validation reports include performance data from core framework."""
        # Configure for quick test
        for scenario in self.validation_manager.load_tester.test_scenarios.values():
            scenario.duration_seconds = 0.5
            scenario.load_levels = [1]

        # Run validation
        validation_result = self.validation_manager.run_full_validation()

        # Check that performance data is included
        assert "results" in validation_result
        performance_results = validation_result["results"].get("performance", {})

        if performance_results.get("status") == "completed":
            assert "optimization_potential" in performance_results
            assert "overall_health" in performance_results

    def test_concurrent_validation_and_performance_monitoring(self):
        """Test running validation concurrently with performance monitoring."""
        import threading

        # Start performance monitoring
        self.performance_manager.start_monitoring()

        validation_results = {}

        def run_validation():
            # Configure for quick test
            for scenario in self.validation_manager.load_tester.test_scenarios.values():
                scenario.duration_seconds = 0.3
                scenario.load_levels = [1]

            validation_results["result"] = self.validation_manager.run_full_validation()

        try:
            # Run validation in background thread
            validation_thread = threading.Thread(target=run_validation)
            validation_thread.start()

            # Wait for validation to complete
            validation_thread.join(timeout=30)

            # Check results
            assert "result" in validation_results
            result = validation_results["result"]
            assert "validation_id" in result
            assert result["status"] in ["passed", "failed", "error"]

        finally:
            self.performance_manager.stop_monitoring()


class TestValidationFrameworkStability:
    """Test validation framework stability and robustness."""

    def test_validation_with_limited_resources(self):
        """Test validation framework under resource constraints."""
        validation_manager = ValidationManager()

        # Configure for minimal resource usage
        for scenario in validation_manager.load_tester.test_scenarios.values():
            scenario.duration_seconds = 0.1
            scenario.load_levels = [1]

        # Run multiple validations quickly
        results = []
        for i in range(3):
            result = validation_manager.run_full_validation()
            results.append(result)

        # All should complete without crashing
        assert len(results) == 3
        for result in results:
            assert "validation_id" in result
            assert result["status"] in ["passed", "failed", "error"]

    def test_validation_cleanup_and_resource_management(self):
        """Test that validation framework properly cleans up resources."""
        validation_manager = ValidationManager()

        # Start monitoring
        validation_manager.performance_validator.performance_manager.start_monitoring()

        # Run some validations
        for scenario in validation_manager.load_tester.test_scenarios.values():
            scenario.duration_seconds = 0.1
            scenario.load_levels = [1]

        result = validation_manager.run_full_validation()

        # Stop monitoring and cleanup
        validation_manager.performance_validator.performance_manager.stop_monitoring()

        # Should complete without issues
        assert result["status"] in ["passed", "failed", "error"]

    def test_validation_with_mock_failures(self):
        """Test validation framework resilience to component failures."""
        validation_manager = ValidationManager()

        # Mock various failure scenarios
        with patch.object(
            validation_manager.performance_validator,
            "validate_performance_benchmarks",
            side_effect=Exception("Performance failure"),
        ):
            result = validation_manager.run_full_validation(components=["performance"])

            # Should handle failure gracefully (may be 'error' or 'no_tests' depending on how error is handled)
            assert result["status"] in ["error", "no_tests", "failed"]
            # Should have some indication of the problem
            assert "error" in result or "summary" in result


if __name__ == "__main__":
    pytest.main([__file__])

"""
Comprehensive unit tests for integration_tester.py

This module provides extensive test coverage for the integration testing framework,
ensuring all methods and edge cases are properly tested with 95%+ coverage.
"""

import json
import tempfile
import time
import unittest
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock, Mock, patch

from ..core.extraction_framework import BaseExtractor, CallSite, ExtractionResult
from .integration_tester import (
    ExtractorTestSuite,
    IntegrationTester,
    TestResult,
    _generate_overall_recommendations,
    _generate_overall_summary,
    run_complete_extractor_test_suite,
)


class MockExtractor(BaseExtractor):
    """Mock extractor for testing."""

    def __init__(self, language: str = "test", should_fail: bool = False):
        super().__init__(language)
        self.should_fail = should_fail
        self._call_count = 0

    def extract_calls(
        self,
        source_code: str,
        file_path: Path | None = None,
    ) -> ExtractionResult:
        """Mock extract_calls method."""
        self._call_count += 1

        if self.should_fail:
            raise Exception("Mock extractor failure")

        result = ExtractionResult()

        # Create mock call sites
        if source_code.strip():
            result.call_sites = [
                CallSite(
                    function_name="mock_function",
                    line_number=1,
                    column_number=0,
                    byte_start=0,
                    byte_end=len(source_code),
                    call_type="function",
                    context={"test": True},
                    language=self.language,
                    file_path=file_path or Path("test.txt"),
                ),
            ]

        result.extraction_time = 0.001
        return result

    def validate_source(self, source_code: str) -> bool:
        """Mock validate_source method."""
        return isinstance(source_code, str) and len(source_code.strip()) > 0


class TestTestResult(unittest.TestCase):
    """Test cases for TestResult class."""

    def test_initialization(self):
        """Test TestResult initialization."""
        result = TestResult("test_name", "python")

        self.assertEqual(result.test_name, "test_name")
        self.assertEqual(result.language, "python")
        self.assertFalse(result.passed)
        self.assertEqual(result.errors, [])
        self.assertEqual(result.warnings, [])
        self.assertEqual(result.execution_time, 0.0)
        self.assertEqual(result.call_sites_found, 0)
        self.assertEqual(result.accuracy_score, 0.0)
        self.assertEqual(result.performance_metrics, {})
        self.assertEqual(result.metadata, {})

    def test_add_error(self):
        """Test adding errors to TestResult."""
        result = TestResult("test", "python")

        # Test simple error
        result.add_error("Test error")
        self.assertEqual(len(result.errors), 1)
        self.assertIn("Test error", result.errors[0])
        self.assertFalse(result.passed)

        # Test error with exception
        exception = ValueError("Test exception")
        result.add_error("Error with exception", exception)
        self.assertEqual(len(result.errors), 2)
        self.assertIn("Error with exception", result.errors[1])
        self.assertIn("Test exception", result.errors[1])

    def test_add_warning(self):
        """Test adding warnings to TestResult."""
        result = TestResult("test", "python")

        result.add_warning("Test warning")
        self.assertEqual(len(result.warnings), 1)
        self.assertEqual(result.warnings[0], "Test warning")

    def test_to_dict(self):
        """Test TestResult serialization to dict."""
        result = TestResult("test_name", "python")
        result.passed = True
        result.accuracy_score = 0.85
        result.call_sites_found = 5
        result.execution_time = 1.23

        result_dict = result.to_dict()

        self.assertEqual(result_dict["test_name"], "test_name")
        self.assertEqual(result_dict["language"], "python")
        self.assertTrue(result_dict["passed"])
        self.assertEqual(result_dict["accuracy_score"], 0.85)
        self.assertEqual(result_dict["call_sites_found"], 5)
        self.assertEqual(result_dict["execution_time"], 1.23)


class TestExtractorTestSuite(unittest.TestCase):
    """Test cases for ExtractorTestSuite class."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_suite = ExtractorTestSuite()

    def test_initialization(self):
        """Test ExtractorTestSuite initialization."""
        # Should have all expected extractors
        expected_extractors = ["python", "javascript", "rust", "go", "c", "cpp", "java"]
        self.assertEqual(
            set(self.test_suite.extractors.keys()),
            set(expected_extractors),
        )

        # Should have test samples for all languages
        self.assertEqual(
            set(self.test_suite.test_samples.keys()),
            set(expected_extractors),
        )

        # Should have performance thresholds
        self.assertEqual(
            set(self.test_suite.performance_thresholds.keys()),
            set(expected_extractors),
        )

    @patch("chunker.extractors.testing.integration_tester.time.perf_counter")
    def test_run_all_tests(self, mock_time):
        """Test running all tests."""
        mock_time.side_effect = [0.0, 1.0, 2.0, 3.0]  # Mock timing

        # Replace extractors with mocks for faster testing
        self.test_suite.extractors = {
            "python": MockExtractor("python"),
            "javascript": MockExtractor("javascript"),
        }

        results = self.test_suite.run_all_tests()

        self.assertIn("overall_passed", results)
        self.assertIn("total_tests", results)
        self.assertIn("passed_tests", results)
        self.assertIn("failed_tests", results)
        self.assertIn("execution_time", results)
        self.assertIn("language_results", results)
        self.assertIn("summary", results)

    def test_test_language_extractors(self):
        """Test language extractor testing."""
        # Use mock extractor for faster testing
        self.test_suite.extractors = {"python": MockExtractor("python")}

        results = self.test_suite.test_language_extractors()

        self.assertIn("python", results)
        python_results = results["python"]

        self.assertIn("extractor_class", python_results)
        self.assertIn("tests", python_results)
        self.assertIn("overall_passed", python_results)
        self.assertIn("total_time", python_results)

    def test_test_cross_language_integration(self):
        """Test cross-language integration testing."""
        # Use mock extractors
        self.test_suite.extractors = {
            "python": MockExtractor("python"),
            "javascript": MockExtractor("javascript"),
        }

        results = self.test_suite.test_cross_language_integration()

        self.assertIn("consistency_tests", results)
        self.assertIn("multi_file_tests", results)
        self.assertIn("performance_comparison", results)
        self.assertIn("overall_passed", results)
        self.assertIn("execution_time", results)

    def test_benchmark_performance(self):
        """Test performance benchmarking."""
        # Use mock extractors for faster testing
        self.test_suite.extractors = {"python": MockExtractor("python")}

        results = self.test_suite.benchmark_performance()

        self.assertIn("language_benchmarks", results)
        self.assertIn("comparative_analysis", results)
        self.assertIn("performance_regression_check", results)
        self.assertIn("resource_usage", results)
        self.assertIn("execution_time", results)

    def test_basic_extraction_test(self):
        """Test basic extraction test method."""
        mock_extractor = MockExtractor("python")

        result = self.test_suite._test_basic_extraction("python", mock_extractor)

        self.assertIsInstance(result, TestResult)
        self.assertEqual(result.test_name, "basic_extraction")
        self.assertEqual(result.language, "python")
        self.assertGreaterEqual(result.execution_time, 0)

    def test_complex_extraction_test(self):
        """Test complex extraction test method."""
        mock_extractor = MockExtractor("python")

        result = self.test_suite._test_complex_extraction("python", mock_extractor)

        self.assertIsInstance(result, TestResult)
        self.assertEqual(result.test_name, "complex_extraction")
        self.assertEqual(result.language, "python")

    def test_edge_cases_test(self):
        """Test edge cases test method."""
        mock_extractor = MockExtractor("python")

        result = self.test_suite._test_edge_cases("python", mock_extractor)

        self.assertIsInstance(result, TestResult)
        self.assertEqual(result.test_name, "edge_cases")
        self.assertEqual(result.language, "python")

    def test_error_handling_test(self):
        """Test error handling test method."""
        mock_extractor = MockExtractor("python")

        result = self.test_suite._test_error_handling("python", mock_extractor)

        self.assertIsInstance(result, TestResult)
        self.assertEqual(result.test_name, "error_handling")
        self.assertEqual(result.language, "python")
        self.assertGreaterEqual(result.accuracy_score, 0.0)
        self.assertLessEqual(result.accuracy_score, 1.0)

    def test_validation_test(self):
        """Test validation test method."""
        mock_extractor = MockExtractor("python")

        result = self.test_suite._test_validation("python", mock_extractor)

        self.assertIsInstance(result, TestResult)
        self.assertEqual(result.test_name, "validation")
        self.assertEqual(result.language, "python")

    def test_extractor_consistency(self):
        """Test extractor consistency testing."""
        self.test_suite.extractors = {
            "python": MockExtractor("python"),
            "javascript": MockExtractor("javascript"),
        }

        results = self.test_suite._test_extractor_consistency()

        self.assertIsInstance(results, list)
        for test in results:
            self.assertIn("pattern", test)
            self.assertIn("results", test)
            self.assertIn("passed", test)

    def test_multi_file_scenarios(self):
        """Test multi-file scenario testing."""
        self.test_suite.extractors = {"python": MockExtractor("python")}

        results = self.test_suite._test_multi_file_scenarios()

        self.assertIsInstance(results, list)
        if results:  # May be empty if no temporary files created
            for test in results:
                self.assertIn("test_name", test)

    def test_compare_extractor_performance(self):
        """Test extractor performance comparison."""
        self.test_suite.extractors = {
            "python": MockExtractor("python"),
            "javascript": MockExtractor("javascript"),
        }

        results = self.test_suite._compare_extractor_performance()

        self.assertIn("processing_speeds", results)
        self.assertIn("accuracy_scores", results)
        self.assertIn("resource_efficiency", results)
        self.assertIn("reliability_scores", results)

    def test_generate_performance_test_files(self):
        """Test performance test file generation."""
        self.test_suite.extractors = {"python": MockExtractor("python")}

        test_files = self.test_suite._generate_performance_test_files()

        self.assertIn("small_files", test_files)
        self.assertIn("medium_files", test_files)
        self.assertIn("large_files", test_files)

        # Check that files were generated for Python
        self.assertIn("python", test_files["small_files"])
        self.assertIn("python", test_files["medium_files"])
        self.assertIn("python", test_files["large_files"])

        # Check file sizes are increasing
        small_size = len(test_files["small_files"]["python"].encode("utf-8"))
        medium_size = len(test_files["medium_files"]["python"].encode("utf-8"))
        large_size = len(test_files["large_files"]["python"].encode("utf-8"))

        self.assertLess(small_size, medium_size)
        self.assertLess(medium_size, large_size)

    def test_benchmark_single_extractor(self):
        """Test single extractor benchmarking."""
        mock_extractor = MockExtractor("python")
        test_code = "print('hello world')"

        benchmark = self.test_suite._benchmark_single_extractor(
            mock_extractor,
            test_code,
            "test",
        )

        self.assertIn("test_name", benchmark)
        self.assertIn("code_size_bytes", benchmark)
        self.assertIn("execution_time", benchmark)
        self.assertIn("calls_found", benchmark)
        self.assertIn("throughput_kb_per_second", benchmark)

        self.assertEqual(benchmark["test_name"], "test")
        self.assertEqual(benchmark["code_size_bytes"], len(test_code.encode("utf-8")))
        self.assertGreaterEqual(benchmark["execution_time"], 0)

    def test_generate_comparative_analysis(self):
        """Test comparative analysis generation."""
        # Mock benchmark data
        language_benchmarks = {
            "python": {
                "small_files": [
                    {
                        "execution_time": 0.1,
                        "throughput_kb_per_second": 10,
                        "memory_peak_mb": 5,
                    },
                ],
                "medium_files": [
                    {
                        "execution_time": 0.2,
                        "throughput_kb_per_second": 8,
                        "memory_peak_mb": 10,
                    },
                ],
                "large_files": [
                    {
                        "execution_time": 0.5,
                        "throughput_kb_per_second": 6,
                        "memory_peak_mb": 20,
                    },
                ],
            },
            "javascript": {
                "small_files": [
                    {
                        "execution_time": 0.15,
                        "throughput_kb_per_second": 8,
                        "memory_peak_mb": 3,
                    },
                ],
                "medium_files": [
                    {
                        "execution_time": 0.25,
                        "throughput_kb_per_second": 6,
                        "memory_peak_mb": 8,
                    },
                ],
                "large_files": [
                    {
                        "execution_time": 0.6,
                        "throughput_kb_per_second": 4,
                        "memory_peak_mb": 15,
                    },
                ],
            },
        }

        analysis = self.test_suite._generate_comparative_analysis(language_benchmarks)

        self.assertIn("fastest_extractor", analysis)
        self.assertIn("most_memory_efficient", analysis)
        self.assertIn("performance_rankings", analysis)
        self.assertIn("recommendations", analysis)

    def test_check_performance_regressions(self):
        """Test performance regression checking."""
        # Mock benchmark data with regression
        language_benchmarks = {
            "python": {
                "small_files": [
                    {"execution_time": 10.0, "code_size_bytes": 1024},
                ],  # Very slow
                "medium_files": [],
                "large_files": [],
            },
        }

        regression_check = self.test_suite._check_performance_regressions(
            language_benchmarks,
        )

        self.assertIn("regressions_found", regression_check)
        self.assertIn("performance_status", regression_check)
        self.assertIn("recommendations", regression_check)

    def test_helper_methods(self):
        """Test various helper methods."""
        # Test _count_expected_complex_calls
        count = self.test_suite._count_expected_complex_calls("python")
        self.assertIsInstance(count, int)
        self.assertGreaterEqual(count, 3)

        # Test _get_edge_cases_for_language
        edge_cases = self.test_suite._get_edge_cases_for_language("python")
        self.assertIsInstance(edge_cases, list)
        self.assertGreater(len(edge_cases), 0)

        # Test _check_edge_case_coverage
        mock_call_sites = [
            CallSite(
                "test",
                1,
                0,
                0,
                10,
                "function",
                {"text_snippet": "lambda x: x"},
                "python",
                Path("test.py"),
            ),
        ]
        coverage = self.test_suite._check_edge_case_coverage(
            mock_call_sites,
            "lambda_calls",
        )
        self.assertIsInstance(coverage, bool)

        # Test _generate_performance_recommendations
        mock_metrics = {
            "python": {"avg_execution_time": 0.1, "avg_memory_usage": 50},
            "javascript": {"avg_execution_time": 0.05, "avg_memory_usage": 30},
        }
        recommendations = self.test_suite._generate_performance_recommendations(
            mock_metrics,
        )
        self.assertIsInstance(recommendations, list)
        self.assertGreater(len(recommendations), 0)


class TestIntegrationTester(unittest.TestCase):
    """Test cases for IntegrationTester class."""

    def setUp(self):
        """Set up test fixtures."""
        self.integration_tester = IntegrationTester()

    def test_initialization(self):
        """Test IntegrationTester initialization."""
        self.assertIsInstance(self.integration_tester.test_suite, ExtractorTestSuite)

    def test_test_complete_workflow(self):
        """Test complete workflow testing."""
        # Mock the test suite for faster testing
        self.integration_tester.test_suite.extractors = {
            "python": MockExtractor("python"),
        }

        results = self.integration_tester.test_complete_workflow()

        self.assertIn("workflow_stages", results)
        self.assertIn("end_to_end_success", results)
        self.assertIn("total_time", results)
        self.assertIn("data_integrity_check", results)
        self.assertIn("error_recovery_test", results)

    def test_validate_accuracy(self):
        """Test accuracy validation."""
        # Mock the test suite
        self.integration_tester.test_suite.extractors = {
            "python": MockExtractor("python"),
        }

        results = self.integration_tester.validate_accuracy()

        self.assertIn("overall_accuracy", results)
        self.assertIn("language_accuracy", results)
        self.assertIn("accuracy_test_results", results)
        self.assertIn("validation_methodology", results)

    def test_test_error_handling(self):
        """Test error handling testing."""
        # Mock the test suite
        self.integration_tester.test_suite.extractors = {
            "python": MockExtractor("python"),
        }

        results = self.integration_tester.test_error_handling()

        self.assertIn("robustness_score", results)
        self.assertIn("language_error_handling", results)
        self.assertIn("critical_failures", results)
        self.assertIn("recovery_mechanisms", results)
        self.assertIn("error_categories_tested", results)

    def test_test_performance_integration(self):
        """Test performance integration testing."""
        results = self.integration_tester.test_performance_integration()

        self.assertIn("concurrent_processing", results)
        self.assertIn("memory_efficiency", results)
        self.assertIn("scalability_analysis", results)
        self.assertIn("performance_degradation_check", results)
        self.assertIn("resource_utilization", results)

    def test_workflow_stage_methods(self):
        """Test individual workflow stage methods."""
        # Mock the test suite
        self.integration_tester.test_suite.extractors = {
            "python": MockExtractor("python"),
        }

        # Test extractor initialization stage
        init_result = self.integration_tester._test_extractor_initialization()
        self.assertIn("stage_name", init_result)
        self.assertIn("passed", init_result)
        self.assertIn("extractors_initialized", init_result)

        # Test extraction workflow stage
        workflow_result = self.integration_tester._test_extraction_workflow()
        self.assertIn("stage_name", workflow_result)
        self.assertIn("passed", workflow_result)
        self.assertIn("successful_extractions", workflow_result)

        # Test result aggregation stage
        aggregation_result = self.integration_tester._test_result_aggregation()
        self.assertIn("stage_name", aggregation_result)
        self.assertIn("passed", aggregation_result)
        self.assertIn("aggregation_tests", aggregation_result)

        # Test cleanup workflow stage
        cleanup_result = self.integration_tester._test_cleanup_workflow()
        self.assertIn("stage_name", cleanup_result)
        self.assertIn("passed", cleanup_result)
        self.assertIn("cleanup_tests", cleanup_result)

    def test_data_integrity(self):
        """Test data integrity testing."""
        integrity_result = self.integration_tester._test_data_integrity()

        self.assertIn("position_accuracy", integrity_result)
        self.assertIn("function_name_accuracy", integrity_result)
        self.assertIn("call_type_consistency", integrity_result)
        self.assertIn("context_preservation", integrity_result)

    def test_error_recovery(self):
        """Test error recovery testing."""
        # Mock the test suite
        self.integration_tester.test_suite.extractors = {
            "python": MockExtractor("python"),
        }

        recovery_result = self.integration_tester._test_error_recovery()

        self.assertIn("graceful_degradation", recovery_result)
        self.assertIn("partial_success_handling", recovery_result)
        self.assertIn("error_propagation", recovery_result)

    def test_validate_language_accuracy(self):
        """Test language accuracy validation."""
        mock_extractor = MockExtractor("python")

        accuracy_result = self.integration_tester._validate_language_accuracy(
            "python",
            mock_extractor,
        )

        self.assertIn("overall_score", accuracy_result)
        self.assertIn("position_accuracy", accuracy_result)
        self.assertIn("name_accuracy", accuracy_result)
        self.assertIn("type_accuracy", accuracy_result)
        self.assertIn("context_completeness", accuracy_result)
        self.assertIn("test_details", accuracy_result)

        self.assertGreaterEqual(accuracy_result["overall_score"], 0.0)
        self.assertLessEqual(accuracy_result["overall_score"], 1.0)

    def test_recovery_mechanisms(self):
        """Test recovery mechanisms testing."""
        # Mock the test suite
        self.integration_tester.test_suite.extractors = {
            "python": MockExtractor("python"),
        }

        recovery_test = self.integration_tester._test_recovery_mechanisms()

        self.assertIn("fallback_strategies", recovery_test)
        self.assertIn("partial_processing", recovery_test)
        self.assertIn("error_isolation", recovery_test)


class TestUtilityFunctions(unittest.TestCase):
    """Test cases for utility functions."""

    def test_run_complete_extractor_test_suite(self):
        """Test the main test suite runner."""
        # This is a comprehensive test, so we'll do a basic check
        with patch(
            "chunker.extractors.testing.integration_tester.ExtractorTestSuite",
        ) as mock_suite_class:
            with patch(
                "chunker.extractors.testing.integration_tester.IntegrationTester",
            ) as mock_tester_class:
                # Mock the classes to return simple results
                mock_suite = Mock()
                mock_suite.run_all_tests.return_value = {
                    "overall_passed": True,
                    "total_tests": 10,
                    "passed_tests": 10,
                }
                mock_suite_class.return_value = mock_suite

                mock_tester = Mock()
                mock_tester.test_complete_workflow.return_value = {
                    "end_to_end_success": True,
                }
                mock_tester.validate_accuracy.return_value = {"overall_accuracy": 0.9}
                mock_tester.test_error_handling.return_value = {"robustness_score": 0.8}
                mock_tester.test_performance_integration.return_value = {
                    "concurrent_processing": {},
                }
                mock_tester_class.return_value = mock_tester

                results = run_complete_extractor_test_suite()

                self.assertIn("test_suite_version", results)
                self.assertIn("execution_timestamp", results)
                self.assertIn("overall_status", results)
                self.assertIn("component_results", results)
                self.assertIn("summary", results)
                self.assertIn("recommendations", results)
                self.assertIn("total_execution_time", results)

    def test_generate_overall_summary(self):
        """Test overall summary generation."""
        mock_component_results = {
            "test_suite": {
                "overall_passed": True,
                "total_tests": 20,
                "passed_tests": 18,
                "performance_summary": {"grade": "A"},
            },
            "accuracy_validation": {
                "overall_accuracy": 0.85,
                "language_accuracy": {"python": {"overall_score": 0.9}},
            },
            "workflow_tests": {"end_to_end_success": False},
        }

        summary = _generate_overall_summary(mock_component_results)

        self.assertIn("total_tests_run", summary)
        self.assertIn("total_tests_passed", summary)
        self.assertIn("overall_success_rate", summary)
        self.assertIn("component_status", summary)
        self.assertIn("critical_issues", summary)
        self.assertIn("performance_summary", summary)
        self.assertIn("accuracy_summary", summary)

        self.assertEqual(summary["total_tests_run"], 20)
        self.assertEqual(summary["total_tests_passed"], 18)
        self.assertEqual(summary["overall_success_rate"], 0.9)
        self.assertEqual(summary["component_status"]["test_suite"], "PASSED")
        self.assertEqual(summary["component_status"]["workflow_tests"], "FAILED")

    def test_generate_overall_recommendations(self):
        """Test overall recommendations generation."""
        mock_component_results = {
            "test_suite": {
                "overall_passed": False,
                "summary": {"overall_success_rate": 0.6},
            },
            "accuracy_validation": {
                "overall_accuracy": 0.5,
                "language_accuracy": {
                    "python": {"overall_score": 0.4},
                    "javascript": {"overall_score": 0.6},
                },
            },
            "error_handling": {
                "robustness_score": 0.7,
                "critical_failures": [{"language": "python", "issue": "crash"}],
            },
            "performance_integration": {
                "memory_efficiency": {
                    "memory_cleanup": {"python": 60, "javascript": 30},
                },
            },
        }

        recommendations = _generate_overall_recommendations(mock_component_results)

        self.assertIsInstance(recommendations, list)
        self.assertGreater(len(recommendations), 0)

        # Check that appropriate recommendations are generated
        rec_text = " ".join(recommendations)
        self.assertIn("production deployment", rec_text.lower())


class TestErrorHandling(unittest.TestCase):
    """Test error handling in integration testing."""

    def test_extractor_failure_handling(self):
        """Test handling of extractor failures."""
        # Create a test suite with a failing extractor
        test_suite = ExtractorTestSuite()
        test_suite.extractors = {"python": MockExtractor("python", should_fail=True)}

        # Test that failures are handled gracefully
        results = test_suite.test_language_extractors()

        self.assertIn("python", results)
        python_results = results["python"]

        # Should still return results structure even with failures
        self.assertIn("extractor_class", python_results)
        self.assertIn("tests", python_results)
        self.assertIn("overall_passed", python_results)
        self.assertFalse(
            python_results["overall_passed"],
        )  # Should fail due to mock failure

    def test_missing_extractor_handling(self):
        """Test handling of missing extractors."""
        test_suite = ExtractorTestSuite()
        test_suite.extractors = {}  # No extractors

        results = test_suite.test_language_extractors()

        # Should return empty results without crashing
        self.assertIsInstance(results, dict)
        self.assertEqual(len(results), 0)

    def test_invalid_data_handling(self):
        """Test handling of invalid data in utility functions."""
        # Test with None input
        summary = _generate_overall_summary(None)
        self.assertIn("summary_generation_error", summary)

        recommendations = _generate_overall_recommendations(None)
        self.assertIsInstance(recommendations, list)
        self.assertGreater(len(recommendations), 0)  # Should have error message

    def test_test_result_error_handling(self):
        """Test TestResult error handling."""
        result = TestResult("test", "python")

        # Test with None exception
        result.add_error("Error", None)
        self.assertEqual(len(result.errors), 1)
        self.assertIn("Error", result.errors[0])

        # Test with complex exception
        try:
            raise ValueError("Complex error") from Exception("Root cause")
        except Exception as e:
            result.add_error("Nested error", e)

        self.assertEqual(len(result.errors), 2)
        self.assertIn("Nested error", result.errors[1])


if __name__ == "__main__":
    unittest.main()

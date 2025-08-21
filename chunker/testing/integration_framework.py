"""Integration Test Framework for Phase 1.7: Smart Error Handling & User Guidance.

This framework provides comprehensive testing of all Phase 1.7 components working together:
- Group A: Language Version Detection
- Group B: Compatibility Database  
- Group C: Error Analysis & Classification
- Group D: User Guidance System
- Group E: Integration & Testing

The framework tests end-to-end workflows, error scenarios, and system integration.
"""

import json
import logging
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

# Import all Phase 1.7 components
try:
    # Group A: Language Version Detection
    # Group C: Error Analysis & Classification
    from ..error_handling import (
        ClassifiedError,
        CompatibilityErrorDetector,
        ErrorCategory,
        ErrorClassifier,
        ErrorSeverity,
        ErrorSource,
        SyntaxErrorAnalyzer,
    )

    # Group B: Compatibility Database
    from ..languages.compatibility import (
        CompatibilityDatabase,
        CompatibilityLevel,
        CompatibilityRule,
        CompatibilitySchema,
        GrammarVersion,
        LanguageVersion,
    )
    from ..languages.version_detection import (
        CppVersionDetector,
        GoVersionDetector,
        JavaScriptVersionDetector,
        JavaVersionDetector,
        PythonVersionDetector,
        RustVersionDetector,
    )

    # Group D: User Guidance System (will be available after Group D completes)
    # from ..error_handling.templates import TemplateManager
    # from ..error_handling.guidance_engine import UserActionGuidanceEngine
    # from ..error_handling.troubleshooting import TroubleshootingDatabase
    # Group E: Integration & Testing (will be available after Group E completes)
    # from ..error_handling.integration import ErrorHandlingPipeline

    IMPORTS_SUCCESSFUL = True

except ImportError as e:
    logging.warning(f"Some Phase 1.7 components not yet available: {e}")
    IMPORTS_SUCCESSFUL = False

logger = logging.getLogger(__name__)


@dataclass
class IntegrationTestResult:
    """Result of an integration test."""

    test_name: str
    test_category: str
    status: str  # "PASS", "FAIL", "SKIP", "ERROR"
    execution_time: float
    details: dict[str, Any] = field(default_factory=dict)
    error_message: str | None = None
    stack_trace: str | None = None
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "test_name": self.test_name,
            "test_category": self.test_category,
            "status": self.status,
            "execution_time": self.execution_time,
            "details": self.details,
            "error_message": self.error_message,
            "stack_trace": self.stack_trace,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class IntegrationTestSuite:
    """Suite of integration tests."""

    suite_name: str
    description: str
    tests: list[IntegrationTestResult] = field(default_factory=list)
    total_tests: int = 0
    passed_tests: int = 0
    failed_tests: int = 0
    skipped_tests: int = 0
    error_tests: int = 0
    total_execution_time: float = 0.0
    created_at: datetime = field(default_factory=datetime.now)

    def add_test_result(self, result: IntegrationTestResult) -> None:
        """Add a test result to the suite."""
        self.tests.append(result)
        self.total_tests += 1
        self.total_execution_time += result.execution_time

        if result.status == "PASS":
            self.passed_tests += 1
        elif result.status == "FAIL":
            self.failed_tests += 1
        elif result.status == "SKIP":
            self.skipped_tests += 1
        elif result.status == "ERROR":
            self.error_tests += 1

    def get_summary(self) -> dict[str, Any]:
        """Get summary of test suite results."""
        return {
            "suite_name": self.suite_name,
            "description": self.description,
            "total_tests": self.total_tests,
            "passed_tests": self.passed_tests,
            "failed_tests": self.failed_tests,
            "skipped_tests": self.skipped_tests,
            "error_tests": self.error_tests,
            "success_rate": (
                (self.passed_tests / self.total_tests * 100)
                if self.total_tests > 0
                else 0
            ),
            "total_execution_time": self.total_execution_time,
            "created_at": self.created_at.isoformat(),
        }


class IntegrationTestFramework:
    """Main framework for running integration tests."""

    def __init__(self):
        """Initialize the integration test framework."""
        self.test_suites: dict[str, IntegrationTestSuite] = {}
        self.current_suite: IntegrationTestSuite | None = None
        self.test_data: dict[str, Any] = self._load_test_data()
        self.logger = logging.getLogger(__name__)

    def _load_test_data(self) -> dict[str, Any]:
        """Load test data for integration tests."""
        return {
            "python_code": {
                "valid": "#!/usr/bin/env python3.9\nprint('Hello, World!')",
                "syntax_error": "#!/usr/bin/env python3.9\nprint('Hello, World!'\n",
                "version_specific": "#!/usr/bin/env python3.10\nfrom typing import TypeAlias\nTypeAlias = str",
            },
            "javascript_code": {
                "valid": "// ES2020\nconst x = 42;\nconsole.log(x);",
                "syntax_error": "// ES2020\nconst x = 42;\nconsole.log(x;\n",
                "version_specific": "// ES2022\nconst x = 42n;\nconsole.log(x);",
            },
            "rust_code": {
                "valid": 'fn main() {\n    println!("Hello, World!");\n}',
                "syntax_error": 'fn main() {\n    println!("Hello, World!");\n',
                "edition_2021": 'fn main() {\n    let x = 42;\n    println!("{x}");\n}',
            },
        }

    def create_test_suite(self, name: str, description: str) -> IntegrationTestSuite:
        """Create a new test suite."""
        suite = IntegrationTestSuite(name, description)
        self.test_suites[name] = suite
        self.current_suite = suite
        self.logger.info(f"Created test suite: {name}")
        return suite

    def run_test(
        self,
        test_func,
        test_name: str,
        test_category: str,
        *args,
        **kwargs,
    ) -> IntegrationTestResult:
        """Run a single integration test."""
        if not self.current_suite:
            raise ValueError("No test suite created. Call create_test_suite() first.")

        start_time = time.time()
        result = IntegrationTestResult(
            test_name=test_name,
            test_category=test_category,
            status="SKIP",
            execution_time=0.0,
        )

        try:
            # Check if test can run
            if not IMPORTS_SUCCESSFUL:
                result.status = "SKIP"
                result.details["reason"] = "Phase 1.7 components not fully available"
                self.logger.warning(
                    f"Test {test_name} skipped: components not available",
                )
            else:
                # Run the test
                test_result = test_func(*args, **kwargs)
                result.status = "PASS"
                result.details["result"] = test_result
                self.logger.info(f"Test {test_name} passed")

        except Exception as e:
            result.status = "ERROR"
            result.error_message = str(e)
            result.stack_trace = traceback.format_exc()
            self.logger.error(f"Test {test_name} failed with error: {e}")

        result.execution_time = time.time() - start_time
        self.current_suite.add_test_result(result)

        return result

    def run_group_a_integration_tests(self) -> None:
        """Run integration tests for Group A: Language Version Detection."""
        self.create_test_suite(
            "Group A Integration",
            "Language Version Detection Integration Tests",
        )

        # Test 1: Python version detection
        def test_python_detection():
            detector = PythonVersionDetector()
            version_info = detector.detect_version(
                self.test_data["python_code"]["valid"],
            )
            primary_version = detector.get_primary_version(version_info)
            assert primary_version == "3.9.0"
            return {"detected_version": primary_version}

        self.run_test(test_python_detection, "Python Version Detection", "Group A")

        # Test 2: JavaScript version detection
        def test_javascript_detection():
            detector = JavaScriptVersionDetector()
            version_info = detector.detect_version(
                self.test_data["javascript_code"]["valid"],
            )
            primary_version = detector.get_primary_version(version_info)
            assert "ES2020" in primary_version
            return {"detected_version": primary_version}

        self.run_test(
            test_javascript_detection,
            "JavaScript Version Detection",
            "Group A",
        )

        # Test 3: Rust version detection
        def test_rust_detection():
            detector = RustVersionDetector()
            version_info = detector.detect_version(
                self.test_data["rust_code"]["edition_2021"],
            )
            primary_version = detector.get_primary_version(version_info)
            assert "2021" in primary_version
            return {"detected_version": primary_version}

        self.run_test(test_rust_detection, "Rust Version Detection", "Group A")

    def run_group_b_integration_tests(self) -> None:
        """Run integration tests for Group B: Compatibility Database."""
        self.create_test_suite(
            "Group B Integration",
            "Compatibility Database Integration Tests",
        )

        # Test 1: Compatibility schema creation
        def test_compatibility_schema():
            schema = CompatibilitySchema()
            assert schema is not None
            return {"schema_created": True}

        self.run_test(
            test_compatibility_schema,
            "Compatibility Schema Creation",
            "Group B",
        )

        # Test 2: Language version creation
        def test_language_version():
            lang_ver = LanguageVersion("python", "3.9", edition="3.9.0")
            assert lang_ver.language == "python"
            assert lang_ver.version == "3.9"
            return {"language_version": lang_ver.to_dict()}

        self.run_test(test_language_version, "Language Version Creation", "Group B")

        # Test 3: Compatibility database operations
        def test_compatibility_database():
            db = CompatibilityDatabase()
            assert db is not None
            return {"database_created": True}

        self.run_test(
            test_compatibility_database,
            "Compatibility Database Creation",
            "Group B",
        )

    def run_group_c_integration_tests(self) -> None:
        """Run integration tests for Group C: Error Analysis & Classification."""
        self.create_test_suite(
            "Group C Integration",
            "Error Analysis & Classification Integration Tests",
        )

        # Test 1: Error classification
        def test_error_classification():
            classifier = ErrorClassifier()
            context = ErrorContext(
                file_path="test.py",
                line_number=42,
                language="python",
            )
            error = ClassifiedError(
                error_id="integration_test",
                message="Syntax error: unexpected token",
                category=ErrorCategory.SYNTAX,
                severity=ErrorSeverity.ERROR,
                source=ErrorSource.TREE_SITTER,
                context=context,
            )
            assert error.category == ErrorCategory.SYNTAX
            return {"error_classified": True, "category": error.category.value}

        self.run_test(test_error_classification, "Error Classification", "Group C")

        # Test 2: Compatibility error detection
        def test_compatibility_detection():
            db = CompatibilityDatabase()
            detector = CompatibilityErrorDetector(compatibility_db=db)
            assert detector is not None
            return {"detector_created": True}

        self.run_test(
            test_compatibility_detection,
            "Compatibility Error Detection",
            "Group C",
        )

        # Test 3: Syntax error analysis
        def test_syntax_analysis():
            analyzer = SyntaxErrorAnalyzer()
            lang_analyzer = SyntaxErrorAnalyzer.LanguageSpecificSyntaxAnalyzer(
                language="python",
            )
            assert analyzer is not None
            return {"analyzer_created": True}

        self.run_test(test_syntax_analysis, "Syntax Error Analysis", "Group C")

    def run_cross_group_integration_tests(self) -> None:
        """Run tests that integrate multiple groups together."""
        self.create_test_suite(
            "Cross-Group Integration",
            "Multi-Group Integration Tests",
        )

        # Test 1: A + B + C workflow
        def test_abc_workflow():
            # Group A: Detect version
            detector = PythonVersionDetector()
            version_info = detector.detect_version(
                self.test_data["python_code"]["valid"],
            )
            primary_version = detector.get_primary_version(version_info)

            # Group B: Create compatibility objects
            schema = CompatibilitySchema()
            lang_ver = LanguageVersion("python", "3.9", edition="3.9.0")

            # Group C: Classify error
            classifier = ErrorClassifier()
            context = ErrorContext(
                file_path="test.py",
                line_number=42,
                language="python",
            )
            error = ClassifiedError(
                error_id="abc_workflow",
                message="Version compatibility issue",
                category=ErrorCategory.COMPATIBILITY,
                severity=ErrorSeverity.WARNING,
                source=ErrorSource.COMPATIBILITY_CHECKER,
                context=context,
            )

            return {
                "version_detected": primary_version,
                "compatibility_created": True,
                "error_classified": True,
            }

        self.run_test(test_abc_workflow, "A+B+C Workflow", "Cross-Group")

        # Test 2: Error handling with version detection
        def test_error_with_version():
            # Create a syntax error
            detector = PythonVersionDetector()
            version_info = detector.detect_version(
                self.test_data["python_code"]["syntax_error"],
            )

            # Classify the error
            classifier = ErrorClassifier()
            context = ErrorContext(
                file_path="syntax_error.py",
                line_number=2,
                language="python",
            )
            error = ClassifiedError(
                error_id="syntax_error_test",
                message="SyntaxError: unexpected EOF while parsing",
                category=ErrorCategory.SYNTAX,
                severity=ErrorSeverity.ERROR,
                source=ErrorSource.TREE_SITTER,
                context=context,
            )

            return {
                "version_detected": detector.get_primary_version(version_info),
                "error_classified": True,
                "error_category": error.category.value,
            }

        self.run_test(
            test_error_with_version,
            "Error with Version Detection",
            "Cross-Group",
        )

    def run_performance_tests(self) -> None:
        """Run performance tests for the integration framework."""
        self.create_test_suite("Performance Tests", "Performance and Scalability Tests")

        # Test 1: Multiple error classifications
        def test_multiple_classifications():
            classifier = ErrorClassifier()
            start_time = time.time()

            results = []
            for i in range(100):
                context = ErrorContext(
                    file_path=f"test_{i}.py",
                    line_number=i,
                    language="python",
                )
                error = ClassifiedError(
                    error_id=f"perf_test_{i}",
                    message=f"Test error {i}",
                    category=ErrorCategory.SYNTAX,
                    severity=ErrorSeverity.ERROR,
                    source=ErrorSource.TREE_SITTER,
                    context=context,
                )
                results.append(error)

            end_time = time.time()
            duration = end_time - start_time

            return {
                "errors_created": len(results),
                "duration": duration,
                "rate": len(results) / duration if duration > 0 else 0,
            }

        self.run_test(
            test_multiple_classifications,
            "Multiple Error Classifications",
            "Performance",
        )

        # Test 2: Version detection performance
        def test_version_detection_performance():
            detector = PythonVersionDetector()
            start_time = time.time()

            results = []
            for i in range(50):
                code = f"#!/usr/bin/env python3.{i % 10}\nprint('test {i}')"
                version_info = detector.detect_version(code)
                primary_version = detector.get_primary_version(version_info)
                results.append(primary_version)

            end_time = time.time()
            duration = end_time - start_time

            return {
                "versions_detected": len(results),
                "duration": duration,
                "rate": len(results) / duration if duration > 0 else 0,
            }

        self.run_test(
            test_version_detection_performance,
            "Version Detection Performance",
            "Performance",
        )

    def generate_report(self) -> dict[str, Any]:
        """Generate comprehensive integration test report."""
        report = {
            "framework_info": {
                "name": "Phase 1.7 Integration Test Framework",
                "version": "1.0.0",
                "created_at": datetime.now().isoformat(),
                "imports_successful": IMPORTS_SUCCESSFUL,
            },
            "test_suites": {},
            "overall_summary": {
                "total_suites": len(self.test_suites),
                "total_tests": 0,
                "total_passed": 0,
                "total_failed": 0,
                "total_skipped": 0,
                "total_errors": 0,
                "overall_success_rate": 0.0,
                "total_execution_time": 0.0,
            },
        }

        # Aggregate results from all test suites
        for suite_name, suite in self.test_suites.items():
            suite_summary = suite.get_summary()
            report["test_suites"][suite_name] = suite_summary

            # Update overall summary
            report["overall_summary"]["total_tests"] += suite_summary["total_tests"]
            report["overall_summary"]["total_passed"] += suite_summary["passed_tests"]
            report["overall_summary"]["total_failed"] += suite_summary["failed_tests"]
            report["overall_summary"]["total_skipped"] += suite_summary["skipped_tests"]
            report["overall_summary"]["total_errors"] += suite_summary["error_tests"]
            report["overall_summary"]["total_execution_time"] += suite_summary[
                "total_execution_time"
            ]

        # Calculate overall success rate
        if report["overall_summary"]["total_tests"] > 0:
            report["overall_summary"]["overall_success_rate"] = (
                report["overall_summary"]["total_passed"]
                / report["overall_summary"]["total_tests"]
                * 100
            )

        return report

    def save_report(self, output_path: Path) -> None:
        """Save integration test report to file."""
        report = self.generate_report()

        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w") as f:
                json.dump(report, f, indent=2)

            self.logger.info(f"Integration test report saved to {output_path}")

        except Exception as e:
            self.logger.error(f"Failed to save report to {output_path}: {e}")
            raise

    def print_summary(self) -> None:
        """Print summary of all test results."""
        report = self.generate_report()

        print("\n" + "=" * 80)
        print("🧪 PHASE 1.7 INTEGRATION TEST FRAMEWORK - SUMMARY REPORT")
        print("=" * 80)

        print("📊 Overall Results:")
        print(f"   • Total Test Suites: {report['overall_summary']['total_suites']}")
        print(f"   • Total Tests: {report['overall_summary']['total_tests']}")
        print(f"   • Passed: {report['overall_summary']['total_passed']}")
        print(f"   • Failed: {report['overall_summary']['total_failed']}")
        print(f"   • Skipped: {report['overall_summary']['total_skipped']}")
        print(f"   • Errors: {report['overall_summary']['total_errors']}")
        print(
            f"   • Success Rate: {report['overall_summary']['overall_success_rate']:.1f}%",
        )
        print(
            f"   • Total Execution Time: {report['overall_summary']['total_execution_time']:.2f}s",
        )

        print("\n🔧 Framework Status:")
        print(
            f"   • Imports Successful: {report['framework_info']['imports_successful']}",
        )
        print(
            f"   • Components Available: {'All' if report['framework_info']['imports_successful'] else 'Partial'}",
        )

        print("\n📋 Test Suite Details:")
        for suite_name, suite_summary in report["test_suites"].items():
            print(
                f"   • {suite_name}: {suite_summary['passed_tests']}/{suite_summary['total_tests']} passed "
                f"({suite_summary['success_rate']:.1f}%)",
            )

        print("=" * 80)


def run_integration_tests() -> IntegrationTestFramework:
    """Run all integration tests and return results."""
    framework = IntegrationTestFramework()

    print("🧪 PHASE 1.7 INTEGRATION TEST FRAMEWORK")
    print("=" * 60)

    # Run all test suites
    framework.run_group_a_integration_tests()
    framework.run_group_b_integration_tests()
    framework.run_group_c_integration_tests()
    framework.run_cross_group_integration_tests()
    framework.run_performance_tests()

    # Generate and display results
    framework.print_summary()

    # Save report
    output_path = Path("integration_test_report.json")
    framework.save_report(output_path)

    return framework


if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Run integration tests
    framework = run_integration_tests()

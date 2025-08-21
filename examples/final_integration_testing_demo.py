#!/usr/bin/env python3
"""Demonstration of the Final Integration Testing System for treesitter-chunker.

This example shows how to use the comprehensive final integration testing system
that validates the complete Phase 1.9 system with all components working together.

The final integration testing system provides:
- Complete system integration testing across all Phase 1.9 components
- Performance optimization validation in real scenarios
- User experience workflow testing
- Production readiness assessment
- Cross-component interaction validation
- Stress testing under high load and failure conditions
- Scenario-based testing for complete user workflows
- Comprehensive test coverage reporting
"""

import asyncio
import logging
import sys
import time
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def setup_logging():
    """Setup logging for the demo."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("final_integration_testing_demo.log"),
        ],
    )


def demonstrate_basic_integration_testing():
    """Demonstrate basic integration testing functionality."""
    print("\n" + "=" * 60)
    print("BASIC INTEGRATION TESTING DEMONSTRATION")
    print("=" * 60)

    try:
        from chunker.integration.final_integration_tests import (
            FinalIntegrationTester,
            TestCategory,
            TestSeverity,
            run_final_integration_tests,
        )

        print("✓ Final integration testing system imported successfully")

        # Configuration for the integration tester
        config = {
            "max_workers": 4,
            "test_timeout": 120,
            "enable_performance_monitoring": True,
            "detailed_reporting": True,
        }

        print(f"✓ Configuration: {config}")

        # Run basic integration tests
        print("\n--- Running Basic Integration Tests ---")

        with FinalIntegrationTester(config) as tester:
            print(
                f"✓ Integration tester initialized with session ID: {tester.session_id}",
            )

            # Check component availability
            availability = tester._component_availability
            available_components = [
                name for name, avail in availability.items() if avail
            ]
            unavailable_components = [
                name for name, avail in availability.items() if not avail
            ]

            print(f"✓ Available components: {available_components}")
            if unavailable_components:
                print(f"⚠ Unavailable components: {unavailable_components}")

            # Run integration tests for available components
            categories_to_test = [TestCategory.SYSTEM_INTEGRATION]
            if availability.get("performance_optimizer", False):
                categories_to_test.append(TestCategory.PERFORMANCE)
            if availability.get("production_validator", False):
                categories_to_test.append(TestCategory.PRODUCTION_READINESS)

            print(f"✓ Testing categories: {[cat.value for cat in categories_to_test]}")

            # Execute tests
            report = tester.run_all_tests(categories=categories_to_test, parallel=True)

            # Display results
            print("\n--- Test Results ---")
            print(f"Total Tests: {report.total_tests}")
            print(f"Passed: {report.passed_tests}")
            print(f"Failed: {report.failed_tests}")
            print(f"Skipped: {report.skipped_tests}")
            print(f"Success Rate: {report.success_rate:.1f}%")
            print(f"Execution Time: {report.total_execution_time:.2f}s")
            print(f"Session ID: {report.test_session_id}")

            if report.is_passing:
                print("✅ All critical tests passed!")
            else:
                print("❌ Some critical tests failed!")
                for result in report.results:
                    if (
                        result.status.value == "failed"
                        and result.severity == TestSeverity.CRITICAL
                    ):
                        print(
                            f"  - CRITICAL FAILURE: {result.test_name}: {result.error_message}",
                        )

            # Show recommendations
            if report.recommendations:
                print("\n--- Recommendations ---")
                for i, rec in enumerate(report.recommendations, 1):
                    print(f"{i}. {rec}")

            return report

    except ImportError as e:
        print(f"❌ Failed to import final integration testing: {e}")
        return None
    except Exception as e:
        print(f"❌ Error during basic integration testing: {e}")
        import traceback

        traceback.print_exc()
        return None


def demonstrate_stress_testing():
    """Demonstrate stress testing capabilities."""
    print("\n" + "=" * 60)
    print("STRESS TESTING DEMONSTRATION")
    print("=" * 60)

    try:
        from chunker.integration.final_integration_tests import (
            FinalIntegrationTester,
            StressTestConfig,
            run_stress_tests,
        )

        # Configure stress testing
        stress_config = StressTestConfig(
            duration_seconds=10,  # Short duration for demo
            concurrent_operations=5,
            max_memory_mb=512,
            max_cpu_percent=70.0,
            failure_injection_rate=0.05,  # 5% failure rate
            operation_types=["parse", "chunk", "validate"],
        )

        print("✓ Stress test configuration created:")
        print(f"  - Duration: {stress_config.duration_seconds}s")
        print(f"  - Concurrent operations: {stress_config.concurrent_operations}")
        print(f"  - Max memory: {stress_config.max_memory_mb}MB")
        print(f"  - Max CPU: {stress_config.max_cpu_percent}%")
        print(
            f"  - Failure injection rate: {stress_config.failure_injection_rate * 100}%",
        )
        print(f"  - Operation types: {stress_config.operation_types}")

        print("\n--- Running Stress Tests ---")

        with FinalIntegrationTester() as tester:
            report = tester.run_stress_tests(stress_config)

            print("\n--- Stress Test Results ---")
            print(f"Total Tests: {report.total_tests}")
            print(f"Passed: {report.passed_tests}")
            print(f"Failed: {report.failed_tests}")
            print(f"Success Rate: {report.success_rate:.1f}%")

            # Find stress test specific results
            stress_results = [
                r for r in report.results if r.category.value == "stress_test"
            ]
            for result in stress_results:
                if "operations_completed" in result.metrics:
                    ops = result.metrics["operations_completed"]
                    failures = result.metrics.get("failures", 0)
                    ops_per_sec = result.metrics.get("operations_per_second", 0)
                    memory_mb = result.metrics.get("memory_increase_mb", 0)

                    print(f"  - Operations completed: {ops}")
                    print(f"  - Failures: {failures}")
                    print(f"  - Operations/second: {ops_per_sec:.1f}")
                    print(f"  - Memory increase: {memory_mb:.1f}MB")

            return report

    except ImportError as e:
        print(f"❌ Failed to import stress testing: {e}")
        return None
    except Exception as e:
        print(f"❌ Error during stress testing: {e}")
        import traceback

        traceback.print_exc()
        return None


def demonstrate_scenario_testing():
    """Demonstrate scenario-based testing."""
    print("\n" + "=" * 60)
    print("SCENARIO TESTING DEMONSTRATION")
    print("=" * 60)

    try:
        from chunker.integration.final_integration_tests import (
            FinalIntegrationTester,
            ScenarioTestConfig,
            create_comprehensive_test_scenarios,
        )

        # Create comprehensive test scenarios
        scenarios = create_comprehensive_test_scenarios()

        print(f"✓ Created {len(scenarios)} comprehensive test scenarios:")
        for i, scenario in enumerate(scenarios, 1):
            print(f"  {i}. {scenario.user_type}: {len(scenario.workflow_steps)} steps")

        # Create a custom scenario for demonstration
        demo_scenario = ScenarioTestConfig(
            user_type="demo_user",
            workflow_steps=[
                "system_initialization",
                "basic_operation",
                "result_validation",
                "cleanup",
            ],
            expected_outcomes={
                "initialization_success": True,
                "operation_completed": True,
                "results_validated": True,
            },
            timeout_per_step=15,
            allow_failures=False,
        )

        print(f"\n✓ Demo scenario created: {demo_scenario.user_type}")
        print(f"  - Workflow steps: {demo_scenario.workflow_steps}")
        print(f"  - Expected outcomes: {demo_scenario.expected_outcomes}")

        print("\n--- Running Scenario Tests ---")

        with FinalIntegrationTester() as tester:
            # Run just the demo scenario
            report = tester.run_scenario_tests([demo_scenario])

            print("\n--- Scenario Test Results ---")
            print(f"Total Tests: {report.total_tests}")
            print(f"Passed: {report.passed_tests}")
            print(f"Failed: {report.failed_tests}")
            print(f"Success Rate: {report.success_rate:.1f}%")

            # Show scenario-specific results
            scenario_results = [
                r for r in report.results if r.category.value == "scenario_test"
            ]
            for result in scenario_results:
                print(f"  - Scenario: {result.test_name}")
                print(f"  - Status: {result.status.value}")
                print(f"  - Execution time: {result.execution_time:.2f}s")
                if result.error_message:
                    print(f"  - Error: {result.error_message}")

            return report

    except ImportError as e:
        print(f"❌ Failed to import scenario testing: {e}")
        return None
    except Exception as e:
        print(f"❌ Error during scenario testing: {e}")
        import traceback

        traceback.print_exc()
        return None


def demonstrate_test_coverage_analysis():
    """Demonstrate test coverage analysis."""
    print("\n" + "=" * 60)
    print("TEST COVERAGE ANALYSIS DEMONSTRATION")
    print("=" * 60)

    try:
        from chunker.integration.final_integration_tests import (
            FinalIntegrationTester,
            get_integration_test_coverage,
        )

        print("✓ Analyzing test coverage across integration points...")

        with FinalIntegrationTester() as tester:
            coverage = tester.get_test_coverage()

            print("\n--- Component Coverage ---")
            for component, coverage_pct in coverage.get(
                "component_coverage",
                {},
            ).items():
                print(f"  - {component}: {coverage_pct:.1f}%")

            print("\n--- Integration Points Coverage ---")
            for integration, coverage_pct in coverage.get(
                "integration_points",
                {},
            ).items():
                print(f"  - {integration}: {coverage_pct:.1f}%")

            print("\n--- Critical Paths Coverage ---")
            for path, coverage_pct in coverage.get("critical_paths", {}).items():
                print(f"  - {path}: {coverage_pct:.1f}%")

            print("\n--- Performance Coverage ---")
            for scenario, coverage_pct in coverage.get(
                "performance_coverage",
                {},
            ).items():
                print(f"  - {scenario}: {coverage_pct:.1f}%")

            print("\n--- Error Scenarios Coverage ---")
            for scenario, coverage_pct in coverage.get("error_scenarios", {}).items():
                print(f"  - {scenario}: {coverage_pct:.1f}%")

            # Calculate overall coverage
            all_coverages = []
            for category_coverage in coverage.values():
                if isinstance(category_coverage, dict):
                    all_coverages.extend(category_coverage.values())

            if all_coverages:
                overall_coverage = sum(all_coverages) / len(all_coverages)
                print(f"\n✓ Overall Test Coverage: {overall_coverage:.1f}%")

            return coverage

    except ImportError as e:
        print(f"❌ Failed to import coverage analysis: {e}")
        return None
    except Exception as e:
        print(f"❌ Error during coverage analysis: {e}")
        import traceback

        traceback.print_exc()
        return None


def demonstrate_production_ready_testing():
    """Demonstrate production-ready testing workflow."""
    print("\n" + "=" * 60)
    print("PRODUCTION-READY TESTING WORKFLOW")
    print("=" * 60)

    try:
        from chunker.integration.final_integration_tests import (
            TestCategory,
            run_final_integration_tests,
        )

        print("✓ Running comprehensive production-ready test suite...")

        # Configuration for production-ready testing
        config = {
            "max_workers": 6,
            "test_timeout": 300,  # 5 minutes
            "enable_performance_monitoring": True,
            "detailed_reporting": True,
            "production_mode": True,
        }

        print(f"✓ Production configuration: {config}")

        # Run all available tests
        print("\n--- Executing Full Test Suite ---")
        report = run_final_integration_tests(config)

        print("\n--- Production Readiness Report ---")
        print(f"Session ID: {report.test_session_id}")
        print(f"Test Duration: {report.total_execution_time:.2f}s")
        print(f"Total Tests: {report.total_tests}")
        print(f"Passed: {report.passed_tests}")
        print(f"Failed: {report.failed_tests}")
        print(f"Skipped: {report.skipped_tests}")
        print(f"Error: {report.error_tests}")
        print(f"Timeout: {report.timeout_tests}")
        print(f"Success Rate: {report.success_rate:.1f}%")

        # Production readiness assessment
        if report.is_passing:
            print("\n🎉 PRODUCTION READY! All critical tests passed.")
        else:
            print("\n⚠️  NOT PRODUCTION READY! Critical issues found:")
            critical_failures = [
                r
                for r in report.results
                if r.severity.value == "critical" and r.status.value == "failed"
            ]
            for failure in critical_failures:
                print(f"  - {failure.test_name}: {failure.error_message}")

        # Performance metrics
        perf = report.performance_metrics
        print("\n--- Performance Metrics ---")
        print(
            f"Average test execution time: {perf.get('avg_test_execution_time', 0):.3f}s",
        )
        print(
            f"Maximum test execution time: {perf.get('max_test_execution_time', 0):.3f}s",
        )
        print(f"Total memory usage: {perf.get('total_memory_usage', 0):.1f}MB")
        print(f"CPU usage: {perf.get('cpu_usage_percent', 0):.1f}%")

        # System information
        sys_info = report.system_info
        print("\n--- System Information ---")
        print(f"Platform: {sys_info.get('platform', 'Unknown')}")
        print(f"Python version: {sys_info.get('python_version', 'Unknown')}")
        print(f"CPU count: {sys_info.get('cpu_count', 'Unknown')}")
        print(f"Total memory: {sys_info.get('memory_total_gb', 0):.1f}GB")

        # Component availability
        components = sys_info.get("component_availability", {})
        available = [name for name, avail in components.items() if avail]
        unavailable = [name for name, avail in components.items() if not avail]
        print(f"Available components: {available}")
        if unavailable:
            print(f"Unavailable components: {unavailable}")

        # Recommendations
        if report.recommendations:
            print("\n--- Recommendations ---")
            for i, rec in enumerate(report.recommendations, 1):
                print(f"{i}. {rec}")

        return report

    except ImportError as e:
        print(f"❌ Failed to import production testing: {e}")
        return None
    except Exception as e:
        print(f"❌ Error during production testing: {e}")
        import traceback

        traceback.print_exc()
        return None


def main():
    """Main demonstration function."""
    print("Final Integration Testing System Demonstration")
    print("=" * 60)
    print("This demo showcases the comprehensive final integration testing")
    print("system for treesitter-chunker Phase 1.9 implementation.")
    print("=" * 60)

    setup_logging()

    # Run all demonstrations
    demonstrations = [
        demonstrate_basic_integration_testing,
        demonstrate_stress_testing,
        demonstrate_scenario_testing,
        demonstrate_test_coverage_analysis,
        demonstrate_production_ready_testing,
    ]

    results = {}

    for demo_func in demonstrations:
        print(f"\n⏳ Starting {demo_func.__name__}...")
        start_time = time.time()

        try:
            result = demo_func()
            execution_time = time.time() - start_time
            results[demo_func.__name__] = {
                "success": result is not None,
                "result": result,
                "execution_time": execution_time,
            }
            print(f"✅ {demo_func.__name__} completed in {execution_time:.2f}s")
        except Exception as e:
            execution_time = time.time() - start_time
            results[demo_func.__name__] = {
                "success": False,
                "error": str(e),
                "execution_time": execution_time,
            }
            print(f"❌ {demo_func.__name__} failed in {execution_time:.2f}s: {e}")

    # Summary
    print("\n" + "=" * 60)
    print("DEMONSTRATION SUMMARY")
    print("=" * 60)

    successful_demos = [name for name, result in results.items() if result["success"]]
    failed_demos = [name for name, result in results.items() if not result["success"]]

    print(f"Successful demonstrations: {len(successful_demos)}")
    print(f"Failed demonstrations: {len(failed_demos)}")

    if successful_demos:
        print("\n✅ Successful:")
        for demo in successful_demos:
            exec_time = results[demo]["execution_time"]
            print(f"  - {demo}: {exec_time:.2f}s")

    if failed_demos:
        print("\n❌ Failed:")
        for demo in failed_demos:
            exec_time = results[demo]["execution_time"]
            error = results[demo].get("error", "Unknown error")
            print(f"  - {demo}: {error} ({exec_time:.2f}s)")

    total_time = sum(result["execution_time"] for result in results.values())
    print(f"\nTotal demonstration time: {total_time:.2f}s")

    if len(successful_demos) == len(demonstrations):
        print("\n🎉 All demonstrations completed successfully!")
        print("The Final Integration Testing System is fully functional.")
    else:
        print("\n⚠️  Some demonstrations failed. Check the output above for details.")

    print("\n💡 See 'final_integration_testing_demo.log' for detailed logs.")


if __name__ == "__main__":
    main()

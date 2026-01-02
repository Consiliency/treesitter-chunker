#!/usr/bin/env python3
"""
Demonstration of the comprehensive validation framework for treesitter-chunker.

This demo shows how to use the validation framework for:
1. Performance validation and benchmarking
2. Load testing and stress testing
3. Regression detection and prevention
4. Full system validation

The validation framework ensures system quality and performance standards.
"""

import sys
import time
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from chunker.validation.validation_framework import (
    LoadTester,
    LoadTestScenario,
    PerformanceValidator,
    RegressionTester,
    ValidationManager,
)


def demo_validation_manager():
    """Demonstrate the ValidationManager orchestration capabilities."""
    print("\n" + "=" * 60)
    print("VALIDATION MANAGER DEMO")
    print("=" * 60)

    # Initialize validation manager
    validation_manager = ValidationManager()

    print("🔍 Running full validation suite...")

    # Configure load tester for quick demo
    for scenario in validation_manager.load_tester.test_scenarios.values():
        scenario.duration_seconds = 1.0  # Quick demo
        scenario.load_levels = [1, 2]  # Minimal load levels

    # Run full validation
    start_time = time.time()
    validation_result = validation_manager.run_full_validation()
    execution_time = time.time() - start_time

    print(f"✅ Validation completed in {execution_time:.2f} seconds")
    print(f"📊 Validation ID: {validation_result['validation_id']}")
    print(f"🎯 Overall Status: {validation_result['status']}")

    # Display summary
    summary = validation_result["summary"]
    print("\n📈 Test Summary:")
    print(f"   Total Tests: {summary['total_tests']}")
    print(f"   Passed: {summary['passed']}")
    print(f"   Failed: {summary['failed']}")
    print(f"   Errors: {summary['errors']}")

    # Display recommendations
    print("\n💡 Recommendations:")
    for i, rec in enumerate(validation_result["recommendations"], 1):
        print(f"   {i}. {rec}")

    return validation_result


def demo_performance_validator():
    """Demonstrate performance validation capabilities."""
    print("\n" + "=" * 60)
    print("PERFORMANCE VALIDATOR DEMO")
    print("=" * 60)

    # Initialize performance validator
    performance_validator = PerformanceValidator()

    print("🔧 Running performance benchmark validation...")

    # Run performance benchmarks
    benchmark_result = performance_validator.validate_performance_benchmarks()

    print(f"✅ Benchmark validation: {benchmark_result['status']}")
    print(f"🏥 Overall health: {benchmark_result['overall_health']}")
    print(
        f"📊 Optimization potential: {benchmark_result['optimization_potential']:.1f}%",
    )

    # Display test results
    test_results = benchmark_result["test_results"]
    print("\n🧪 Individual Test Results:")
    for result in test_results:
        status_icon = "✅" if result["status"] == "passed" else "❌"
        print(f"   {status_icon} {result['test_name']}: {result['status']}")
        if "execution_time" in result:
            print(f"      ⏱️  Execution time: {result['execution_time']:.3f}ms")

    print("🔍 Running SLA validation...")

    # Run SLA validation
    sla_result = performance_validator.validate_performance_sla()

    print(f"✅ SLA validation: {sla_result['status']}")
    print(f"📋 SLA compliance: {sla_result.get('sla_compliance', 'Unknown')}")

    # Generate performance report
    print("📄 Generating comprehensive performance report...")
    report = performance_validator.generate_performance_report()

    print(f"📊 Overall performance status: {report['overall_status']}")

    return benchmark_result, sla_result, report


def demo_load_tester():
    """Demonstrate load testing capabilities."""
    print("\n" + "=" * 60)
    print("LOAD TESTER DEMO")
    print("=" * 60)

    # Initialize load tester
    load_tester = LoadTester()

    # Configure for quick demo
    for scenario in load_tester.test_scenarios.values():
        scenario.duration_seconds = 2.0  # Quick demo
        scenario.load_levels = [1, 3]  # Minimal load levels

    print("🚀 Running individual load test...")

    # Run a single load test
    load_result = load_tester.run_load_test("basic_processing", 2)

    print(f"✅ Load test: {load_result['status']}")
    print(f"📊 Scenario: {load_result['scenario']}")
    print(f"🎯 Load level: {load_result['load_level']}")

    metrics = load_result["metrics"]
    print("\n📈 Performance Metrics:")
    print(f"   Success rate: {metrics['success_rate_percent']:.1f}%")
    print(f"   Average response time: {metrics['average_response_time_ms']:.2f}ms")
    print(f"   Throughput: {metrics['throughput_requests_per_sec']:.1f} req/s")
    print(f"   Total requests: {metrics['total_requests']}")

    print("\n🔥 Running stress test...")

    # Run stress test
    stress_result = load_tester.run_stress_test("basic_processing")

    print(f"✅ Stress test: {stress_result['status']}")
    print(
        f"💪 Breaking point: {stress_result['breaking_point_load_level']} concurrent requests",
    )
    print(f"🔬 Tests run: {stress_result['total_tests_run']}")

    # Add custom test scenario
    print("\n🎛️  Adding custom test scenario...")

    def custom_test_function(data=None):
        """Custom test function for demo."""
        time.sleep(0.01)  # Simulate 10ms work
        return {"result": "custom_success", "data_processed": bool(data)}

    custom_scenario = LoadTestScenario(
        name="custom_demo",
        description="Custom demo scenario",
        target_function=custom_test_function,
        load_levels=[1, 2],
        duration_seconds=1.0,
        ramp_up_seconds=0.1,
        success_criteria={"max_response_time_ms": 100, "min_success_rate_percent": 95},
        test_data_generator=lambda: "demo_data",
    )

    load_tester.add_test_scenario(custom_scenario)

    # Test custom scenario
    custom_result = load_tester.run_load_test("custom_demo", 1)
    print(f"✅ Custom scenario test: {custom_result['status']}")

    return load_result, stress_result, custom_result


def demo_regression_tester():
    """Demonstrate regression testing capabilities."""
    print("\n" + "=" * 60)
    print("REGRESSION TESTER DEMO")
    print("=" * 60)

    # Initialize regression tester
    regression_tester = RegressionTester()

    print("📏 Establishing performance baseline...")

    # Establish baseline
    baseline_result = regression_tester.establish_baseline()

    print(f"✅ Baseline establishment: {baseline_result['status']}")
    print(f"📊 Metrics captured: {baseline_result['metrics_count']}")
    print(f"🧪 Benchmark tests: {baseline_result['benchmark_tests']}")

    # Wait a moment to ensure different timestamp
    time.sleep(0.1)

    print("\n🔍 Detecting performance regressions...")

    # Detect regressions
    regression_result = regression_tester.detect_regressions()

    print(f"✅ Regression detection: {regression_result['status']}")
    print(f"⚠️  Regressions detected: {regression_result['regressions_detected']}")

    if regression_result["regressions"]:
        print("\n🚨 Regression Details:")
        for regression in regression_result["regressions"]:
            print(
                f"   • {regression.get('metric_name', regression.get('benchmark_name', 'Unknown'))}",
            )
            print(f"     Change: {regression['change_percent']:.1f}%")
            print(f"     Severity: {regression['severity']}")

    print("\n📊 Assessing change impact...")

    # Assess change impact
    test_changes = [
        "memory optimization update",
        "algorithm performance improvement",
        "ui color scheme change",
    ]

    change_impact = regression_tester.assess_change_impact(test_changes)

    print(f"✅ Change impact assessment: {change_impact['status']}")
    print(f"🎯 Overall risk level: {change_impact['overall_risk_level']}")
    print(f"⚠️  High-risk changes: {change_impact['high_risk_changes']}")

    print("\n🛡️  Implementing regression prevention...")

    # Implement regression prevention
    prevention_result = regression_tester.prevent_regressions()

    print(f"✅ Prevention implementation: {prevention_result['status']}")
    print(
        f"🔧 Measures implemented: {prevention_result['measures_implemented']}/{prevention_result['total_measures']}",
    )
    print(f"📈 Success rate: {prevention_result['success_rate']:.1f}%")

    return baseline_result, regression_result, change_impact, prevention_result


def demo_integration_workflow():
    """Demonstrate a complete validation workflow."""
    print("\n" + "=" * 60)
    print("INTEGRATION WORKFLOW DEMO")
    print("=" * 60)

    print("🔄 Running complete validation workflow...")

    # Initialize all components
    validation_manager = ValidationManager()

    # Configure for quick demo
    for scenario in validation_manager.load_tester.test_scenarios.values():
        scenario.duration_seconds = 1.0
        scenario.load_levels = [1, 2]

    # Step 1: Establish baseline for future comparisons
    print("\n1️⃣  Establishing performance baseline...")
    baseline = validation_manager.regression_tester.establish_baseline()
    print(f"   ✅ Baseline: {baseline['status']}")

    # Step 2: Run performance validation
    print("\n2️⃣  Validating current performance...")
    performance = validation_manager.validate_performance()
    print(f"   ✅ Performance: {performance['status']}")

    # Step 3: Execute load tests
    print("\n3️⃣  Executing load tests...")
    load_tests = validation_manager.run_load_tests()
    print(f"   ✅ Load tests: {load_tests['status']}")

    # Step 4: Check for regressions
    print("\n4️⃣  Checking for regressions...")
    regressions = validation_manager.run_regression_tests()
    print(f"   ✅ Regressions: {regressions['status']}")

    # Step 5: Generate comprehensive report
    print("\n5️⃣  Generating validation report...")
    report = validation_manager.generate_validation_report()

    print("\n📋 Final Validation Report:")
    print(f"   Status: {report['status']}")
    if "summary" in report:
        summary = report["summary"]
        print(f"   Tests: {summary['passed']}/{summary['total_tests']} passed")

    print("\n💡 Final Recommendations:")
    for rec in report.get(
        "recommendations",
        ["System validation completed successfully"],
    ):
        print(f"   • {rec}")

    return report


def main():
    """Run the complete validation framework demonstration."""
    print("🚀 TREESITTER-CHUNKER VALIDATION FRAMEWORK DEMO")
    print("🔍 Comprehensive system validation and testing capabilities")

    try:
        # Demo each component
        validation_result = demo_validation_manager()
        performance_results = demo_performance_validator()
        load_results = demo_load_tester()
        regression_results = demo_regression_tester()

        # Demo integration workflow
        integration_result = demo_integration_workflow()

        print("\n" + "=" * 60)
        print("DEMO COMPLETED SUCCESSFULLY! 🎉")
        print("=" * 60)

        print("\n✅ All validation framework components demonstrated:")
        print("   🎯 ValidationManager - Orchestration and coordination")
        print("   📊 PerformanceValidator - Benchmark and SLA validation")
        print("   🚀 LoadTester - Load and stress testing")
        print("   🔍 RegressionTester - Regression detection and prevention")
        print("   🔄 Integration workflow - Complete validation pipeline")

        print("\n🏆 The validation framework provides:")
        print("   • Comprehensive performance monitoring")
        print("   • Automated load and stress testing")
        print("   • Regression detection and prevention")
        print("   • Quality assurance and system validation")
        print("   • Production-ready testing capabilities")

    except Exception as e:
        print(f"\n❌ Demo failed with error: {e}")
        import traceback

        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())

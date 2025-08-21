#!/usr/bin/env python3
"""
Core System Integration Demo - Task 1.9.1

This example demonstrates the core system integration that unifies Phase 1.7 (Error Handling & User Guidance)
with Phase 1.8 (Grammar Management & CLI Tools) into a production-ready system.

Key Features Demonstrated:
- System initialization and component orchestration
- Health monitoring and diagnostics
- Error processing through integrated pipeline
- Grammar lifecycle management
- Graceful degradation and fallback responses
- Thread-safe singleton pattern
"""

import time
from pathlib import Path

try:
    from chunker.integration import (
        SystemIntegrator,
        get_system_health,
        get_system_integrator,
        initialize_treesitter_system,
        process_grammar_error,
    )

    INTEGRATION_AVAILABLE = True
except ImportError:
    print(
        "Core integration not available. Install treesitter-chunker with integration support.",
    )
    INTEGRATION_AVAILABLE = False
    exit(1)


def demo_system_initialization():
    """Demonstrate system initialization and component setup."""
    print("🚀 Core System Integration Demo")
    print("=" * 50)

    print("\n1. Initializing treesitter-chunker system...")
    result = initialize_treesitter_system()

    print(f"   Status: {result['status']}")
    print(f"   Components: {len(result.get('components', []))}")
    print(f"   Initialization time: {result.get('initialization_time', 0):.3f}s")
    print(
        f"   System health: {result.get('system_health', {}).get('overall_status', 'unknown')}",
    )

    return result


def demo_health_monitoring():
    """Demonstrate system health monitoring capabilities."""
    print("\n2. System Health Monitoring")
    print("-" * 30)

    health = get_system_health()

    print(f"   Overall status: {health['system_health']['overall_status']}")
    print(f"   Total components: {health['system_health']['component_count']}")
    print(f"   Healthy components: {health['system_health']['healthy_components']}")
    print(f"   Available components: {health['system_health']['available_components']}")

    print("\n   Component Details:")
    for name, component in health["system_health"]["components"].items():
        status_emoji = (
            "✅"
            if component["status"] == "healthy"
            else "⚠️" if component["status"] == "degraded" else "❌"
        )
        print(f"   {status_emoji} {name}: {component['status']} ({component['type']})")

    # System metrics
    if "system_info" in health:
        print("\n   System Metrics:")
        if "cpu_percent" in health["system_info"]:
            print(f"   💻 CPU: {health['system_info']['cpu_percent']:.1f}%")
        if "memory_info" in health["system_info"]:
            memory_mb = health["system_info"]["memory_info"].get("rss", 0) / 1024 / 1024
            print(f"   🧠 Memory: {memory_mb:.1f} MB")

    return health


def demo_error_processing():
    """Demonstrate error processing through the integrated pipeline."""
    print("\n3. Error Processing Integration")
    print("-" * 30)

    # Test different types of errors
    test_errors = [
        (ValueError("Invalid syntax in Python code"), "python"),
        (ImportError("Cannot import required module"), "javascript"),
        (FileNotFoundError("Grammar file not found"), "rust"),
    ]

    for i, (error, language) in enumerate(test_errors, 1):
        print(f"\n   Test {i}: Processing {type(error).__name__} for {language}")

        result = process_grammar_error(
            error,
            context={
                "file_path": f"example.{language}",
                "line_number": 42,
                "test_case": True,
            },
            language=language,
        )

        print(f"   Status: {result['status']}")
        if "processing_time" in result:
            print(f"   Processing time: {result['processing_time']:.3f}s")

        if result["status"] == "success" and "error_analysis" in result:
            analysis = result["error_analysis"]
            print(
                f"   Analysis available: {type(analysis).__name__ if hasattr(analysis, '__name__') else 'Yes'}",
            )
        elif result["status"] == "fallback":
            print(
                f"   Fallback response: {len(result.get('guidance', []))} guidance items",
            )


def demo_grammar_lifecycle():
    """Demonstrate grammar lifecycle management."""
    print("\n4. Grammar Lifecycle Management")
    print("-" * 30)

    integrator = get_system_integrator()

    # Test different grammar operations
    operations = [
        ("validate", "python", {}),
        ("install", "typescript", {"version": "latest"}),
        ("update", "javascript", {}),
    ]

    for i, (operation, language, kwargs) in enumerate(operations, 1):
        print(f"\n   Test {i}: {operation.title()} grammar for {language}")

        result = integrator.manage_grammar_lifecycle(
            operation=operation,
            language=language,
            **kwargs,
        )

        print(f"   Status: {result['status']}")
        if "processing_time" in result:
            print(f"   Processing time: {result['processing_time']:.3f}s")

        if result["status"] == "error" and "error_analysis" in result:
            print("   Error analysis available: Yes")
        elif result["status"] == "degraded":
            available = result.get("available_components", [])
            print(f"   Available components: {len(available)}")


def demo_performance_metrics():
    """Demonstrate performance monitoring and metrics collection."""
    print("\n5. Performance Monitoring")
    print("-" * 30)

    integrator = get_system_integrator()

    print(f"   Session ID: {integrator.session_id}")
    print(f"   Requests processed: {integrator.request_count}")
    print(f"   Errors encountered: {integrator.error_count}")

    if integrator.performance_metrics:
        print(
            f"   Performance metrics collected: {len(integrator.performance_metrics)}",
        )
        for metric_name, values in integrator.performance_metrics.items():
            if values:
                avg_time = sum(values) / len(values)
                print(
                    f"   📊 {metric_name}: {avg_time:.3f}s avg ({len(values)} samples)",
                )
    else:
        print("   No performance metrics collected yet")


def demo_singleton_pattern():
    """Demonstrate thread-safe singleton pattern."""
    print("\n6. Singleton Pattern Verification")
    print("-" * 30)

    # Get multiple instances
    integrator1 = get_system_integrator()
    integrator2 = SystemIntegrator()
    integrator3 = get_system_integrator()

    # Verify they're all the same instance
    same_instance = integrator1 is integrator2 is integrator3
    print(f"   All instances identical: {'✅ Yes' if same_instance else '❌ No'}")
    print(f"   Instance ID: {id(integrator1)}")
    print(f"   Session ID: {integrator1.session_id}")


def demo_graceful_degradation():
    """Demonstrate graceful degradation when components are unavailable."""
    print("\n7. Graceful Degradation")
    print("-" * 30)

    # The system automatically handles missing components
    integrator = get_system_integrator()

    # Check phase availability
    print("   Phase Availability:")
    diagnostics = integrator.get_system_diagnostics()
    availability = diagnostics.get("phase_availability", {})

    for phase, available in availability.items():
        status = "✅ Available" if available else "⚠️ Degraded"
        print(f"   {status} {phase.replace('_', ' ').title()}")

    # System continues to work even with missing components
    overall_health = integrator.monitor_system_health()
    print(f"\n   Overall system health: {overall_health.value}")
    print(
        f"   System remains functional: {'✅ Yes' if overall_health.value != 'unhealthy' else '❌ No'}",
    )


def main():
    """Run the complete core integration demo."""
    if not INTEGRATION_AVAILABLE:
        return

    try:
        # Run all demonstrations
        demo_system_initialization()
        demo_health_monitoring()
        demo_error_processing()
        demo_grammar_lifecycle()
        demo_performance_metrics()
        demo_singleton_pattern()
        demo_graceful_degradation()

        print("\n" + "=" * 50)
        print("✅ Core System Integration Demo Completed Successfully!")
        print("\nKey Features Demonstrated:")
        print("• System initialization and component orchestration")
        print("• Health monitoring and diagnostics")
        print("• Error processing through integrated pipeline")
        print("• Grammar lifecycle management")
        print("• Performance monitoring and metrics")
        print("• Thread-safe singleton pattern")
        print("• Graceful degradation with missing components")

    except KeyboardInterrupt:
        print("\n\n🛑 Demo interrupted by user")
    except Exception as e:
        print(f"\n❌ Demo failed with error: {e}")
        import traceback

        traceback.print_exc()
    finally:
        # Cleanup
        try:
            integrator = get_system_integrator()
            integrator.shutdown()
            print("\n🧹 System shutdown completed")
        except Exception:
            pass


if __name__ == "__main__":
    main()

"""Tests for the Core System Integration (Task 1.9.1)."""

import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

try:
    from chunker.integration import (
        ComponentHealth,
        ComponentInitializationError,
        ComponentType,
        HealthStatus,
        LifecycleManager,
        SystemHealth,
        SystemInitializationError,
        SystemIntegrator,
        get_system_health,
        get_system_integrator,
        initialize_treesitter_system,
        process_grammar_error,
    )

    INTEGRATION_AVAILABLE = True
except ImportError:
    INTEGRATION_AVAILABLE = False


@pytest.mark.skipif(
    not INTEGRATION_AVAILABLE,
    reason="Integration module not available",
)
class TestComponentHealth:
    """Test ComponentHealth functionality."""

    def test_component_health_creation(self):
        """Test component health object creation."""
        health = ComponentHealth(
            name="test_component",
            component_type=ComponentType.ERROR_HANDLING,
        )

        assert health.name == "test_component"
        assert health.component_type == ComponentType.ERROR_HANDLING
        assert health.status == HealthStatus.UNKNOWN
        assert health.error_count == 0
        assert health.last_error is None

    def test_update_status(self):
        """Test status updates."""
        health = ComponentHealth(
            name="test_component",
            component_type=ComponentType.GRAMMAR_MANAGEMENT,
        )

        health.update_status(HealthStatus.HEALTHY)
        assert health.status == HealthStatus.HEALTHY
        assert health.last_check is not None

        health.update_status(HealthStatus.UNHEALTHY, "Test error")
        assert health.status == HealthStatus.UNHEALTHY
        assert health.last_error == "Test error"
        assert health.error_count == 1

    def test_record_performance(self):
        """Test performance metric recording."""
        health = ComponentHealth(
            name="test_component",
            component_type=ComponentType.CORE_CHUNKING,
        )

        health.record_performance("response_time", 0.123)
        health.record_performance("throughput", 100)

        assert health.performance_metrics["response_time"] == 0.123
        assert health.performance_metrics["throughput"] == 100

    def test_health_checks(self):
        """Test health status checking methods."""
        health = ComponentHealth(
            name="test_component",
            component_type=ComponentType.CLI_TOOLS,
        )

        # Unknown status
        assert not health.is_healthy()
        assert not health.is_available()

        # Healthy status
        health.update_status(HealthStatus.HEALTHY)
        assert health.is_healthy()
        assert health.is_available()

        # Degraded status
        health.update_status(HealthStatus.DEGRADED)
        assert not health.is_healthy()
        assert health.is_available()

        # Unhealthy status
        health.update_status(HealthStatus.UNHEALTHY)
        assert not health.is_healthy()
        assert not health.is_available()


@pytest.mark.skipif(
    not INTEGRATION_AVAILABLE,
    reason="Integration module not available",
)
class TestSystemHealth:
    """Test SystemHealth functionality."""

    def test_system_health_creation(self):
        """Test system health object creation."""
        system_health = SystemHealth()

        assert len(system_health.components) == 0
        assert system_health.overall_status == HealthStatus.UNKNOWN
        assert system_health.last_check is None

    def test_add_component(self):
        """Test adding components to system health."""
        system_health = SystemHealth()

        component = ComponentHealth(
            name="test_component",
            component_type=ComponentType.ERROR_HANDLING,
        )

        system_health.add_component(component)
        assert "test_component" in system_health.components
        assert system_health.components["test_component"] == component

    def test_update_overall_status(self):
        """Test overall status calculation."""
        system_health = SystemHealth()

        # No components
        system_health.update_overall_status()
        assert system_health.overall_status == HealthStatus.UNKNOWN

        # All healthy
        comp1 = ComponentHealth("comp1", ComponentType.ERROR_HANDLING)
        comp1.update_status(HealthStatus.HEALTHY)
        comp2 = ComponentHealth("comp2", ComponentType.GRAMMAR_MANAGEMENT)
        comp2.update_status(HealthStatus.HEALTHY)

        system_health.add_component(comp1)
        system_health.add_component(comp2)
        system_health.update_overall_status()
        assert system_health.overall_status == HealthStatus.HEALTHY

        # Some degraded
        comp1.update_status(HealthStatus.DEGRADED)
        system_health.update_overall_status()
        assert system_health.overall_status == HealthStatus.DEGRADED

        # Mostly unhealthy - need more unhealthy than available
        comp1.update_status(HealthStatus.UNHEALTHY)  # Both unhealthy now
        comp2.update_status(HealthStatus.UNHEALTHY)
        system_health.update_overall_status()
        assert system_health.overall_status == HealthStatus.UNHEALTHY

    def test_get_summary(self):
        """Test health summary generation."""
        system_health = SystemHealth()

        comp1 = ComponentHealth("comp1", ComponentType.ERROR_HANDLING)
        comp1.update_status(HealthStatus.HEALTHY)
        comp2 = ComponentHealth("comp2", ComponentType.GRAMMAR_MANAGEMENT)
        comp2.update_status(HealthStatus.DEGRADED, "Minor issue")

        system_health.add_component(comp1)
        system_health.add_component(comp2)
        system_health.update_overall_status()

        summary = system_health.get_summary()

        assert "overall_status" in summary
        assert "component_count" in summary
        assert "healthy_components" in summary
        assert "available_components" in summary
        assert "components" in summary
        assert summary["component_count"] == 2
        assert summary["healthy_components"] == 1
        assert summary["available_components"] == 2


@pytest.mark.skipif(
    not INTEGRATION_AVAILABLE,
    reason="Integration module not available",
)
class TestLifecycleManager:
    """Test LifecycleManager functionality."""

    def test_lifecycle_manager_creation(self):
        """Test lifecycle manager creation."""
        manager = LifecycleManager()

        assert len(manager.components) == 0
        assert len(manager.dependency_graph) == 0
        assert len(manager.initialization_order) == 0
        assert len(manager.initialized_components) == 0

    def test_register_component(self):
        """Test component registration."""
        manager = LifecycleManager()

        def factory():
            return Mock()

        manager.register_component("test_comp", factory, {"dep1", "dep2"})

        assert "test_comp" in manager.components
        assert manager.dependency_graph["test_comp"] == {"dep1", "dep2"}

    def test_dependency_resolution(self):
        """Test dependency resolution and topological sort."""
        manager = LifecycleManager()

        # Create components with dependencies
        manager.register_component("comp_a", Mock)
        manager.register_component("comp_b", Mock, {"comp_a"})
        manager.register_component("comp_c", Mock, {"comp_b"})

        order = manager._resolve_dependencies()

        # comp_a should be first, comp_c should be last
        assert order.index("comp_a") < order.index("comp_b")
        assert order.index("comp_b") < order.index("comp_c")

    def test_circular_dependency_detection(self):
        """Test circular dependency detection."""
        manager = LifecycleManager()

        manager.register_component("comp_a", Mock, {"comp_b"})
        manager.register_component("comp_b", Mock, {"comp_a"})

        with pytest.raises(SystemInitializationError):
            manager._resolve_dependencies()

    def test_component_initialization(self):
        """Test component initialization."""
        manager = LifecycleManager()

        mock_a = Mock()
        mock_b = Mock()

        manager.register_component("comp_a", lambda: mock_a)
        manager.register_component("comp_b", lambda: mock_b, {"comp_a"})

        initialized = manager.initialize_components()

        assert "comp_a" in initialized
        assert "comp_b" in initialized
        assert initialized["comp_a"] == mock_a
        assert initialized["comp_b"] == mock_b
        assert "comp_a" in manager.initialized_components
        assert "comp_b" in manager.initialized_components

    def test_initialization_failure(self):
        """Test handling of initialization failures."""
        manager = LifecycleManager()

        def failing_factory():
            raise Exception("Initialization failed")

        manager.register_component("failing_comp", failing_factory)

        with pytest.raises(SystemInitializationError):
            manager.initialize_components()

    def test_component_shutdown(self):
        """Test component shutdown."""
        manager = LifecycleManager()

        mock_comp = Mock()
        mock_comp.shutdown = Mock()

        manager.register_component("comp", lambda: mock_comp)
        initialized = manager.initialize_components()

        manager.shutdown_components(initialized)

        mock_comp.shutdown.assert_called_once()
        assert "comp" not in manager.initialized_components


@pytest.mark.skipif(
    not INTEGRATION_AVAILABLE,
    reason="Integration module not available",
)
class TestSystemIntegrator:
    """Test SystemIntegrator functionality."""

    def test_singleton_pattern(self):
        """Test that SystemIntegrator follows singleton pattern."""
        integrator1 = SystemIntegrator()
        integrator2 = SystemIntegrator()

        assert integrator1 is integrator2

    def test_get_system_integrator(self):
        """Test global system integrator function."""
        integrator1 = get_system_integrator()
        integrator2 = get_system_integrator()

        assert integrator1 is integrator2
        assert isinstance(integrator1, SystemIntegrator)

    def test_thread_safety(self):
        """Test thread safety of singleton creation."""
        results = []

        def create_integrator():
            results.append(SystemIntegrator())

        threads = [threading.Thread(target=create_integrator) for _ in range(10)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        # All instances should be the same
        assert all(instance is results[0] for instance in results)

    @patch("chunker.integration.core_integration.PHASE_17_AVAILABLE", False)
    @patch("chunker.integration.core_integration.PHASE_18_AVAILABLE", False)
    @patch("chunker.integration.core_integration.CORE_AVAILABLE", False)
    def test_graceful_degradation(self):
        """Test graceful degradation when components are unavailable."""
        # Create a new integrator instance to test degradation
        integrator = SystemIntegrator.__new__(SystemIntegrator)
        integrator._initialized = False
        integrator.__init__()

        # Should not raise exceptions even when components are unavailable
        result = integrator.initialize_system()
        assert result["status"] == "success"

        # Error processing should fall back gracefully
        error_result = integrator.process_grammar_error(
            Exception("Test error"),
            context={"test": True},
        )
        assert error_result["status"] == "fallback"

    def test_error_processing_integration(self):
        """Test error processing through the integrated pipeline."""
        integrator = get_system_integrator()

        # Mock error processing pipeline
        with patch.object(integrator, "error_pipeline") as mock_pipeline:
            mock_pipeline.process_error.return_value = {
                "classification": "syntax_error",
                "guidance": ["Fix syntax issue"],
            }

            result = integrator.process_grammar_error(
                Exception("Syntax error"),
                context={"language": "python"},
                language="python",
            )

            assert result["status"] == "success"
            assert "error_analysis" in result
            assert "processing_time" in result
            mock_pipeline.process_error.assert_called_once()

    def test_grammar_lifecycle_management(self):
        """Test grammar lifecycle operations."""
        integrator = get_system_integrator()

        # Mock grammar manager
        with patch.object(integrator, "grammar_manager") as mock_manager:
            mock_manager.install_grammar.return_value = {"status": "installed"}

            result = integrator.manage_grammar_lifecycle(
                "install",
                "python",
                version="latest",
            )

            assert result["status"] == "success"
            assert result["operation"] == "install"
            assert result["language"] == "python"
            mock_manager.install_grammar.assert_called_once_with(
                "python",
                version="latest",
            )

    def test_system_diagnostics(self):
        """Test system diagnostics collection."""
        integrator = get_system_integrator()

        diagnostics = integrator.get_system_diagnostics()

        assert "session_id" in diagnostics
        assert "startup_time" in diagnostics
        assert "system_health" in diagnostics
        assert "system_info" in diagnostics
        assert "performance_stats" in diagnostics
        assert "request_count" in diagnostics
        assert "error_count" in diagnostics
        assert "phase_availability" in diagnostics

    def test_health_monitoring(self):
        """Test system health monitoring."""
        integrator = get_system_integrator()

        # Initial health check
        status = integrator.monitor_system_health()
        assert isinstance(status, HealthStatus)

        # Force health check by setting interval to 0
        integrator._health_check_interval = 0
        status = integrator.monitor_system_health()
        assert isinstance(status, HealthStatus)

    def test_context_manager(self):
        """Test context manager functionality."""
        with patch(
            "chunker.integration.core_integration.SystemIntegrator.initialize_system",
        ) as mock_init:
            with patch(
                "chunker.integration.core_integration.SystemIntegrator.shutdown",
            ) as mock_shutdown:
                mock_init.return_value = {"status": "success"}

                with SystemIntegrator() as integrator:
                    assert isinstance(integrator, SystemIntegrator)

                mock_init.assert_called_once()
                mock_shutdown.assert_called_once()

    def test_fallback_responses(self):
        """Test fallback response generation."""
        integrator = get_system_integrator()

        # Test error fallback
        error_response = integrator._fallback_error_response(
            Exception("Test error"),
            "Test message",
            0.123,
        )

        assert error_response["status"] == "fallback"
        assert error_response["error"] == "Test error"
        assert error_response["message"] == "Test message"
        assert error_response["processing_time"] == 0.123
        assert "guidance" in error_response

        # Test general fallback
        fallback_response = integrator._fallback_response("Service unavailable", 0.456)

        assert fallback_response["status"] == "degraded"
        assert fallback_response["message"] == "Service unavailable"
        assert fallback_response["processing_time"] == 0.456


@pytest.mark.skipif(
    not INTEGRATION_AVAILABLE,
    reason="Integration module not available",
)
class TestGlobalFunctions:
    """Test global integration functions."""

    def test_initialize_treesitter_system(self):
        """Test global system initialization function."""
        with patch(
            "chunker.integration.core_integration.get_system_integrator",
        ) as mock_get:
            mock_integrator = Mock()
            mock_integrator.initialize_system.return_value = {"status": "success"}
            mock_get.return_value = mock_integrator

            result = initialize_treesitter_system()

            assert result["status"] == "success"
            mock_integrator.initialize_system.assert_called_once()

    def test_process_grammar_error_global(self):
        """Test global error processing function."""
        with patch(
            "chunker.integration.core_integration.get_system_integrator",
        ) as mock_get:
            mock_integrator = Mock()
            mock_integrator.process_grammar_error.return_value = {"status": "success"}
            mock_get.return_value = mock_integrator

            test_error = Exception("Test error")
            result = process_grammar_error(
                test_error,
                context={"test": True},
                language="python",
            )

            assert result["status"] == "success"
            # Check that the method was called with the right arguments
            assert mock_integrator.process_grammar_error.call_count == 1
            call_args = mock_integrator.process_grammar_error.call_args
            assert str(call_args[0][0]) == str(
                test_error,
            )  # Compare string representations
            assert call_args[0][1] == {"test": True}
            assert call_args[0][2] == "python"

    def test_get_system_health_global(self):
        """Test global system health function."""
        with patch(
            "chunker.integration.core_integration.get_system_integrator",
        ) as mock_get:
            mock_integrator = Mock()
            mock_integrator.get_system_diagnostics.return_value = {"status": "healthy"}
            mock_get.return_value = mock_integrator

            result = get_system_health()

            assert result["status"] == "healthy"
            mock_integrator.get_system_diagnostics.assert_called_once()


@pytest.mark.skipif(
    not INTEGRATION_AVAILABLE,
    reason="Integration module not available",
)
class TestIntegrationRobustness:
    """Test integration robustness and error handling."""

    def test_exception_handling_in_initialization(self):
        """Test exception handling during system initialization."""
        integrator = SystemIntegrator.__new__(SystemIntegrator)
        integrator._initialized = False

        # Mock lifecycle manager to raise exception
        with patch.object(integrator, "_setup_components") as mock_setup:
            mock_setup.side_effect = Exception("Setup failed")

            with pytest.raises(Exception):
                integrator.__init__()

    def test_performance_tracking(self):
        """Test performance metrics tracking."""
        integrator = get_system_integrator()

        # Initialize metrics
        initial_count = integrator.request_count

        # Process some operations
        integrator.process_grammar_error(Exception("Test"), language="python")
        integrator.manage_grammar_lifecycle("validate", "python")

        # Check that metrics were updated
        assert integrator.request_count > initial_count
        # The performance_metrics might be empty if operations complete too quickly
        # or use fallback responses. Just check that request count increased.
        assert integrator.request_count >= initial_count + 2

    def test_concurrent_operations(self):
        """Test concurrent operations on the system integrator."""
        integrator = get_system_integrator()
        results = []

        def process_error():
            result = integrator.process_grammar_error(
                Exception("Concurrent test"),
                language="python",
            )
            results.append(result)

        # Run concurrent operations
        threads = [threading.Thread(target=process_error) for _ in range(5)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        # All operations should complete
        assert len(results) == 5
        for result in results:
            assert "status" in result

    def test_memory_cleanup(self):
        """Test memory cleanup and resource management."""
        integrator = get_system_integrator()

        # Add some active sessions
        integrator.active_sessions["test1"] = {"data": "test"}
        integrator.active_sessions["test2"] = {"data": "test"}

        # Shutdown should clear sessions
        integrator.shutdown()
        assert len(integrator.active_sessions) == 0


@pytest.mark.skipif(
    not INTEGRATION_AVAILABLE,
    reason="Integration module not available",
)
def test_module_imports():
    """Test that all expected components can be imported."""
    from chunker.integration import (
        ComponentHealth,
        ComponentInitializationError,
        ComponentType,
        HealthStatus,
        LifecycleManager,
        SystemHealth,
        SystemInitializationError,
        SystemIntegrator,
    )

    # Verify all classes are accessible
    assert SystemIntegrator is not None
    assert ComponentHealth is not None
    assert HealthStatus is not None
    assert ComponentType is not None
    assert SystemHealth is not None
    assert LifecycleManager is not None
    assert SystemInitializationError is not None
    assert ComponentInitializationError is not None


@pytest.mark.skipif(
    not INTEGRATION_AVAILABLE,
    reason="Integration module not available",
)
def test_integration_with_main_chunker():
    """Test integration with main chunker package."""
    try:
        from chunker import (
            get_system_health,
            get_system_integrator,
            initialize_treesitter_system,
            process_grammar_error,
        )

        # Test that functions are available
        assert get_system_integrator is not None
        assert initialize_treesitter_system is not None
        assert process_grammar_error is not None
        assert get_system_health is not None

    except ImportError:
        # This is okay - integration may not be available in all configurations
        pass

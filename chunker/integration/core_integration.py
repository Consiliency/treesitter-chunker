"""Core System Integration for treesitter-chunker - Task 1.9.1.

This module implements the core system integration that unifies Phase 1.7 (Error Handling & User Guidance)
with Phase 1.8 (Grammar Management & CLI Tools) into a production-ready system.

Key Features:
- SystemIntegrator: Thread-safe singleton providing unified entry point
- Component orchestration with proper dependency management
- Health monitoring and diagnostics for all system components
- Graceful degradation when components are unavailable
- Lifecycle management for component initialization and shutdown
- Production-ready error handling and logging

The system integrates:
- Phase 1.7: Error handling pipeline, classification, compatibility detection, syntax analysis, user guidance
- Phase 1.8: Grammar management, CLI tools, registry, installation, validation

Design Principles:
- Thread-safe operations with proper locking
- Graceful degradation when components fail
- Comprehensive health monitoring
- Clear separation of concerns
- Production-ready error handling
"""

from __future__ import annotations

import logging
import os
import sys
import threading
import time
import traceback
import uuid
import weakref
from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import psutil

# Import Phase 1.7 Error Handling components with graceful fallback
try:
    from chunker.error_handling import (
        ClassifiedError,
        ErrorCategory,
        ErrorHandlingOrchestrator,
        ErrorHandlingPipeline,
        ErrorSeverity,
        TroubleshootingDatabase,
        UserActionGuidanceEngine,
    )

    PHASE_17_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Phase 1.7 components not available: {e}")
    PHASE_17_AVAILABLE = False
    ErrorHandlingPipeline = None
    ErrorHandlingOrchestrator = None
    ClassifiedError = None
    ErrorCategory = None
    ErrorSeverity = None
    UserActionGuidanceEngine = None
    TroubleshootingDatabase = None

# Import Phase 1.8 Grammar Management components with graceful fallback
try:
    from chunker.grammar_management import (
        ComprehensiveGrammarCLI,
        GrammarInstaller,
        GrammarManager,
        GrammarRegistry,
        GrammarStatus,
        GrammarValidator,
    )

    PHASE_18_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Phase 1.8 components not available: {e}")
    PHASE_18_AVAILABLE = False
    ComprehensiveGrammarCLI = None
    GrammarManager = None
    GrammarRegistry = None
    GrammarInstaller = None
    GrammarValidator = None
    GrammarStatus = None

# Import core chunking components
try:
    from chunker.core import chunk_file, chunk_text
    from chunker.parser import get_parser
    from chunker.token.chunker import TreeSitterTokenAwareChunker

    CORE_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Core chunking components not available: {e}")
    CORE_AVAILABLE = False
    chunk_file = None
    chunk_text = None
    get_parser = None
    TreeSitterTokenAwareChunker = None


class HealthStatus(Enum):
    """Health status enumeration for system components."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"
    INITIALIZING = "initializing"
    SHUTDOWN = "shutdown"


class ComponentType(Enum):
    """Type classification for system components."""

    ERROR_HANDLING = "error_handling"
    GRAMMAR_MANAGEMENT = "grammar_management"
    CORE_CHUNKING = "core_chunking"
    CLI_TOOLS = "cli_tools"
    EXTERNAL_DEPENDENCY = "external_dependency"


@dataclass
class ComponentHealth:
    """Health information for a system component."""

    name: str
    component_type: ComponentType
    status: HealthStatus = HealthStatus.UNKNOWN
    last_check: datetime | None = None
    error_count: int = 0
    last_error: str | None = None
    performance_metrics: dict[str, Any] = field(default_factory=dict)
    dependencies: set[str] = field(default_factory=set)
    metadata: dict[str, Any] = field(default_factory=dict)

    def update_status(self, status: HealthStatus, error: str | None = None) -> None:
        """Update component health status."""
        self.status = status
        self.last_check = datetime.now(UTC)
        if error:
            self.last_error = error
            self.error_count += 1

    def record_performance(self, metric_name: str, value: Any) -> None:
        """Record a performance metric."""
        self.performance_metrics[metric_name] = value

    def is_healthy(self) -> bool:
        """Check if component is healthy."""
        return self.status == HealthStatus.HEALTHY

    def is_available(self) -> bool:
        """Check if component is available for use."""
        return self.status in {HealthStatus.HEALTHY, HealthStatus.DEGRADED}


@dataclass
class SystemHealth:
    """Overall system health information."""

    components: dict[str, ComponentHealth] = field(default_factory=dict)
    overall_status: HealthStatus = HealthStatus.UNKNOWN
    last_check: datetime | None = None
    system_metrics: dict[str, Any] = field(default_factory=dict)

    def add_component(self, component: ComponentHealth) -> None:
        """Add a component to system health tracking."""
        self.components[component.name] = component

    def update_overall_status(self) -> None:
        """Update overall system status based on components."""
        if not self.components:
            self.overall_status = HealthStatus.UNKNOWN
            return

        healthy_count = sum(1 for c in self.components.values() if c.is_healthy())
        available_count = sum(1 for c in self.components.values() if c.is_available())
        total_count = len(self.components)

        if healthy_count == total_count:
            self.overall_status = HealthStatus.HEALTHY
        elif available_count >= total_count * 0.5:  # At least 50% available
            self.overall_status = HealthStatus.DEGRADED
        else:
            self.overall_status = HealthStatus.UNHEALTHY

        self.last_check = datetime.now(UTC)

    def get_summary(self) -> dict[str, Any]:
        """Get a summary of system health."""
        return {
            "overall_status": self.overall_status.value,
            "last_check": self.last_check.isoformat() if self.last_check else None,
            "component_count": len(self.components),
            "healthy_components": sum(
                1 for c in self.components.values() if c.is_healthy()
            ),
            "available_components": sum(
                1 for c in self.components.values() if c.is_available()
            ),
            "system_metrics": self.system_metrics,
            "components": {
                name: {
                    "status": comp.status.value,
                    "type": comp.component_type.value,
                    "error_count": comp.error_count,
                    "last_error": comp.last_error,
                }
                for name, comp in self.components.items()
            },
        }


class SystemInitializationError(Exception):
    """Raised when system initialization fails."""


class ComponentInitializationError(Exception):
    """Raised when component initialization fails."""


class SystemDegradationError(Exception):
    """Raised when system enters degraded state."""


class LifecycleManager:
    """Manages component lifecycle and dependencies."""

    def __init__(self):
        self.components: dict[str, Any] = {}
        self.dependency_graph: dict[str, set[str]] = defaultdict(set)
        self.initialization_order: list[str] = []
        self.initialized_components: set[str] = set()
        self.logger = logging.getLogger(__name__ + ".LifecycleManager")

    def register_component(
        self,
        name: str,
        component_factory: Callable[[], Any],
        dependencies: set[str] | None = None,
    ) -> None:
        """Register a component with its factory and dependencies."""
        self.components[name] = component_factory
        if dependencies:
            self.dependency_graph[name] = dependencies
        self.logger.debug(
            f"Registered component: {name} with dependencies: {dependencies}",
        )

    def _resolve_dependencies(self) -> list[str]:
        """Resolve component dependencies and return initialization order."""
        # Topological sort to determine initialization order
        visited = set()
        temp_visited = set()
        order = []

        def visit(component: str):
            if component in temp_visited:
                raise SystemInitializationError(
                    f"Circular dependency detected involving {component}",
                )
            if component in visited:
                return

            temp_visited.add(component)
            for dependency in self.dependency_graph.get(component, set()):
                if dependency in self.components:
                    visit(dependency)

            temp_visited.remove(component)
            visited.add(component)
            order.append(component)

        for component in self.components:
            if component not in visited:
                visit(component)

        return order

    def initialize_components(self) -> dict[str, Any]:
        """Initialize all components in dependency order."""
        try:
            self.initialization_order = self._resolve_dependencies()
            initialized = {}

            for component_name in self.initialization_order:
                try:
                    self.logger.info(f"Initializing component: {component_name}")
                    component_factory = self.components[component_name]
                    component_instance = component_factory()
                    initialized[component_name] = component_instance
                    self.initialized_components.add(component_name)
                    self.logger.info(
                        f"Successfully initialized component: {component_name}",
                    )
                except Exception as e:
                    self.logger.error(
                        f"Failed to initialize component {component_name}: {e}",
                    )
                    raise ComponentInitializationError(
                        f"Failed to initialize {component_name}: {e}",
                    )

            return initialized

        except Exception as e:
            self.logger.error(f"Component initialization failed: {e}")
            raise SystemInitializationError(f"System initialization failed: {e}")

    def shutdown_components(self, components: dict[str, Any]) -> None:
        """Shutdown components in reverse order."""
        # Shutdown in reverse order
        for component_name in reversed(self.initialization_order):
            if component_name in components:
                try:
                    component = components[component_name]
                    if hasattr(component, "shutdown"):
                        self.logger.info(f"Shutting down component: {component_name}")
                        component.shutdown()
                    self.initialized_components.discard(component_name)
                except Exception as e:
                    self.logger.error(
                        f"Error shutting down component {component_name}: {e}",
                    )


class SystemIntegrator:
    """
    Thread-safe singleton providing unified entry point for the complete grammar management system.

    This class orchestrates all Phase 1.7 and Phase 1.8 components, manages their lifecycle,
    provides health monitoring, and ensures graceful degradation when components are unavailable.
    """

    _instance = None
    _lock = threading.RLock()
    _initialized = False

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
            return cls._instance

    def __init__(self):
        if self._initialized:
            return

        with self._lock:
            if self._initialized:
                return

            self.logger = logging.getLogger(__name__ + ".SystemIntegrator")
            self.session_id = str(uuid.uuid4())
            self.startup_time = datetime.now(UTC)

            # Core system components
            self.lifecycle_manager = LifecycleManager()
            self.system_health = SystemHealth()
            self.active_sessions: dict[str, Any] = {}

            # Component instances (initialized lazily)
            self.error_pipeline: Any | None = None
            self.error_orchestrator: Any | None = None
            self.grammar_cli: Any | None = None
            self.grammar_manager: Any | None = None
            self.grammar_registry: Any | None = None
            self.token_aware_chunker: Any | None = None

            # Health monitoring
            self._health_check_interval = 30  # seconds
            self._last_health_check = None
            self._health_lock = threading.Lock()

            # Performance tracking
            self.performance_metrics: dict[str, deque] = defaultdict(
                lambda: deque(maxlen=100),
            )
            self.request_count = 0
            self.error_count = 0

            self._setup_components()
            self._initialized = True

    def _setup_components(self) -> None:
        """Setup component registrations with the lifecycle manager."""

        # Phase 1.7 Error Handling Components
        if PHASE_17_AVAILABLE:
            self.lifecycle_manager.register_component(
                "error_pipeline",
                lambda: ErrorHandlingPipeline() if ErrorHandlingPipeline else None,
                dependencies=set(),
            )

            self.lifecycle_manager.register_component(
                "error_orchestrator",
                lambda: None,  # Will be created after pipeline initialization
                dependencies={"error_pipeline"},
            )

        # Phase 1.8 Grammar Management Components
        if PHASE_18_AVAILABLE:
            self.lifecycle_manager.register_component(
                "grammar_registry",
                lambda: GrammarRegistry() if GrammarRegistry else None,
                dependencies=set(),
            )

            self.lifecycle_manager.register_component(
                "grammar_manager",
                lambda: GrammarManager() if GrammarManager else None,
                dependencies={"grammar_registry"},
            )

            self.lifecycle_manager.register_component(
                "grammar_cli",
                lambda: ComprehensiveGrammarCLI() if ComprehensiveGrammarCLI else None,
                dependencies={"grammar_manager", "error_pipeline"},
            )

        # Core Chunking Components
        if CORE_AVAILABLE:
            self.lifecycle_manager.register_component(
                "token_aware_chunker",
                lambda: (
                    TreeSitterTokenAwareChunker()
                    if TreeSitterTokenAwareChunker
                    else None
                ),
                dependencies={"grammar_manager"} if PHASE_18_AVAILABLE else set(),
            )

        # Initialize component health tracking
        self._initialize_health_tracking()

    def _initialize_health_tracking(self) -> None:
        """Initialize health tracking for all components."""
        component_configs = [
            ("error_pipeline", ComponentType.ERROR_HANDLING),
            ("error_orchestrator", ComponentType.ERROR_HANDLING),
            ("grammar_registry", ComponentType.GRAMMAR_MANAGEMENT),
            ("grammar_manager", ComponentType.GRAMMAR_MANAGEMENT),
            ("grammar_cli", ComponentType.CLI_TOOLS),
            ("token_aware_chunker", ComponentType.CORE_CHUNKING),
        ]

        for name, comp_type in component_configs:
            health = ComponentHealth(
                name=name,
                component_type=comp_type,
                status=HealthStatus.INITIALIZING,
            )
            self.system_health.add_component(health)

    def initialize_system(self) -> dict[str, Any]:
        """
        Bootstrap all components with proper dependency order.

        Returns:
            Dict containing status and initialized components
        """
        self.logger.info("Initializing treesitter-chunker system...")
        start_time = time.time()

        try:
            # Initialize components through lifecycle manager
            initialized_components = self.lifecycle_manager.initialize_components()

            # Store component references
            self.error_pipeline = initialized_components.get("error_pipeline")

            # Create error orchestrator manually if pipeline is available
            if self.error_pipeline and ErrorHandlingOrchestrator:
                try:
                    self.error_orchestrator = ErrorHandlingOrchestrator(
                        self.error_pipeline,
                    )
                    initialized_components["error_orchestrator"] = (
                        self.error_orchestrator
                    )
                except Exception as e:
                    self.logger.warning(
                        f"Failed to create ErrorHandlingOrchestrator: {e}",
                    )
                    self.error_orchestrator = None
            else:
                self.error_orchestrator = None

            self.grammar_cli = initialized_components.get("grammar_cli")
            self.grammar_manager = initialized_components.get("grammar_manager")
            self.grammar_registry = initialized_components.get("grammar_registry")
            self.token_aware_chunker = initialized_components.get("token_aware_chunker")

            # Update component health status
            for name, component in initialized_components.items():
                if name in self.system_health.components:
                    if component is not None:
                        self.system_health.components[name].update_status(
                            HealthStatus.HEALTHY,
                        )
                    else:
                        self.system_health.components[name].update_status(
                            HealthStatus.UNHEALTHY,
                            "Component not available",
                        )

            # Update overall system health
            self.system_health.update_overall_status()

            initialization_time = time.time() - start_time
            self.performance_metrics["initialization_time"].append(initialization_time)

            self.logger.info(
                f"System initialization completed in {initialization_time:.2f}s. "
                f"Status: {self.system_health.overall_status.value}",
            )

            return {
                "status": "success",
                "initialization_time": initialization_time,
                "system_health": self.system_health.get_summary(),
                "components": list(initialized_components.keys()),
                "session_id": self.session_id,
            }

        except Exception as e:
            self.error_count += 1
            self.logger.error(f"System initialization failed: {e}")

            # Update component statuses to reflect failure
            for component in self.system_health.components.values():
                if component.status == HealthStatus.INITIALIZING:
                    component.update_status(HealthStatus.UNHEALTHY, str(e))

            self.system_health.update_overall_status()

            raise SystemInitializationError(f"System initialization failed: {e}")

    def process_grammar_error(
        self,
        error: Exception,
        context: dict[str, Any] | None = None,
        language: str | None = None,
        grammar_path: Path | None = None,
    ) -> dict[str, Any]:
        """
        Process grammar-related errors through the integrated error handling pipeline.

        Args:
            error: The exception that occurred
            context: Additional context information
            language: Programming language context
            grammar_path: Path to grammar file if applicable

        Returns:
            Dict containing processed error information and guidance
        """
        self.request_count += 1
        start_time = time.time()

        try:
            if not self.error_pipeline:
                return self._fallback_error_response(
                    error,
                    "Error handling pipeline not available",
                )

            # Enhance context with system information
            enhanced_context = {
                "session_id": self.session_id,
                "timestamp": datetime.now(UTC).isoformat(),
                "language": language,
                "grammar_path": str(grammar_path) if grammar_path else None,
                "system_health": self.system_health.overall_status.value,
                **(context or {}),
            }

            # Process through error handling pipeline
            result = self.error_pipeline.process_error(
                error=error,
                context=enhanced_context,
            )

            processing_time = time.time() - start_time
            self.performance_metrics["error_processing_time"].append(processing_time)

            self.logger.debug(f"Processed grammar error in {processing_time:.3f}s")

            return {
                "status": "success",
                "processing_time": processing_time,
                "error_analysis": result,
                "session_id": self.session_id,
            }

        except Exception as e:
            self.error_count += 1
            processing_time = time.time() - start_time
            self.logger.error(f"Error processing failed: {e}")

            return self._fallback_error_response(
                error,
                f"Error processing failed: {e}",
                processing_time,
            )

    def manage_grammar_lifecycle(
        self,
        operation: str,
        language: str,
        **kwargs,
    ) -> dict[str, Any]:
        """
        Manage grammar lifecycle operations (install, update, remove, validate).

        Args:
            operation: Operation to perform (install, update, remove, validate)
            language: Target language
            **kwargs: Additional operation parameters

        Returns:
            Dict containing operation results
        """
        self.request_count += 1
        start_time = time.time()

        try:
            if not self.grammar_manager:
                return self._fallback_response(
                    f"Grammar management not available for operation: {operation}",
                )

            # Delegate to grammar manager based on operation
            if operation == "install":
                result = self.grammar_manager.install_grammar(language, **kwargs)
            elif operation == "update":
                result = self.grammar_manager.update_grammar(language, **kwargs)
            elif operation == "remove":
                result = self.grammar_manager.remove_grammar(language, **kwargs)
            elif operation == "validate":
                result = self.grammar_manager.validate_grammar(language, **kwargs)
            else:
                raise ValueError(f"Unknown operation: {operation}")

            processing_time = time.time() - start_time
            self.performance_metrics["grammar_operation_time"].append(processing_time)

            self.logger.info(
                f"Grammar {operation} for {language} completed in {processing_time:.3f}s",
            )

            return {
                "status": "success",
                "operation": operation,
                "language": language,
                "processing_time": processing_time,
                "result": result,
                "session_id": self.session_id,
            }

        except Exception as e:
            self.error_count += 1
            processing_time = time.time() - start_time
            self.logger.error(f"Grammar {operation} failed for {language}: {e}")

            # Process error through error handling if available
            if self.error_pipeline:
                try:
                    error_result = self.process_grammar_error(
                        e,
                        context={
                            "operation": operation,
                            "language": language,
                            "parameters": kwargs,
                        },
                        language=language,
                    )
                    return {
                        "status": "error",
                        "operation": operation,
                        "language": language,
                        "processing_time": processing_time,
                        "error": str(e),
                        "error_analysis": error_result.get("error_analysis"),
                        "session_id": self.session_id,
                    }
                except Exception:
                    pass  # Fall through to fallback

            return self._fallback_response(
                f"Grammar {operation} failed for {language}: {e}",
                processing_time,
            )

    def get_system_diagnostics(self) -> dict[str, Any]:
        """
        Retrieve comprehensive system diagnostics and health information.

        Returns:
            Dict containing system diagnostics
        """
        self._update_health_metrics()

        try:
            # Collect system metrics
            process = psutil.Process()
            system_info = {
                "cpu_percent": process.cpu_percent(),
                "memory_info": process.memory_info()._asdict(),
                "num_threads": process.num_threads(),
                "uptime": (datetime.now(UTC) - self.startup_time).total_seconds(),
            }
        except Exception:
            system_info = {"error": "Unable to collect system metrics"}

        # Performance statistics
        perf_stats = {}
        for metric_name, values in self.performance_metrics.items():
            if values:
                perf_stats[metric_name] = {
                    "count": len(values),
                    "avg": sum(values) / len(values),
                    "min": min(values),
                    "max": max(values),
                    "recent": list(values)[-10:],  # Last 10 values
                }

        return {
            "session_id": self.session_id,
            "startup_time": self.startup_time.isoformat(),
            "system_health": self.system_health.get_summary(),
            "system_info": system_info,
            "performance_stats": perf_stats,
            "request_count": self.request_count,
            "error_count": self.error_count,
            "active_sessions": len(self.active_sessions),
            "phase_availability": {
                "phase_17_error_handling": PHASE_17_AVAILABLE,
                "phase_18_grammar_management": PHASE_18_AVAILABLE,
                "core_chunking": CORE_AVAILABLE,
            },
        }

    def monitor_system_health(self) -> HealthStatus:
        """
        Monitor overall system health and perform health checks.

        Returns:
            Current system health status
        """
        with self._health_lock:
            now = datetime.now(UTC)

            # Perform health check if enough time has passed
            if (
                self._last_health_check is None
                or (now - self._last_health_check).total_seconds()
                >= self._health_check_interval
            ):

                self._perform_health_checks()
                self._last_health_check = now

            return self.system_health.overall_status

    def _perform_health_checks(self) -> None:
        """Perform health checks on all components."""
        for component_name, component_health in self.system_health.components.items():
            try:
                # Get component instance
                component = getattr(self, component_name.replace("-", "_"), None)

                if component is None:
                    component_health.update_status(
                        HealthStatus.UNHEALTHY,
                        "Component not initialized",
                    )
                    continue

                # Perform component-specific health check
                if hasattr(component, "health_check"):
                    health_result = component.health_check()
                    if health_result:
                        component_health.update_status(HealthStatus.HEALTHY)
                    else:
                        component_health.update_status(HealthStatus.DEGRADED)
                else:
                    # Basic availability check
                    component_health.update_status(HealthStatus.HEALTHY)

            except Exception as e:
                component_health.update_status(HealthStatus.UNHEALTHY, str(e))

        # Update overall system status
        self.system_health.update_overall_status()

    def _update_health_metrics(self) -> None:
        """Update system health metrics."""
        try:
            # Update system-level metrics
            process = psutil.Process()
            self.system_health.system_metrics.update(
                {
                    "cpu_percent": process.cpu_percent(),
                    "memory_usage_mb": process.memory_info().rss / 1024 / 1024,
                    "num_threads": process.num_threads(),
                    "request_count": self.request_count,
                    "error_count": self.error_count,
                    "error_rate": self.error_count / max(self.request_count, 1),
                },
            )
        except Exception as e:
            self.logger.warning(f"Failed to update health metrics: {e}")

    def _fallback_error_response(
        self,
        error: Exception,
        message: str,
        processing_time: float | None = None,
    ) -> dict[str, Any]:
        """Generate fallback error response when error processing fails."""
        return {
            "status": "fallback",
            "error": str(error),
            "error_type": type(error).__name__,
            "message": message,
            "processing_time": processing_time,
            "guidance": [
                "Error processing system is currently unavailable",
                "Check system logs for more detailed information",
                "Contact support if the issue persists",
            ],
            "session_id": self.session_id,
        }

    def _fallback_response(
        self,
        message: str,
        processing_time: float | None = None,
    ) -> dict[str, Any]:
        """Generate fallback response when components are unavailable."""
        return {
            "status": "degraded",
            "message": message,
            "processing_time": processing_time,
            "session_id": self.session_id,
            "available_components": [
                name
                for name, health in self.system_health.components.items()
                if health.is_available()
            ],
        }

    def shutdown(self) -> None:
        """Gracefully shutdown the system integrator."""
        self.logger.info("Shutting down SystemIntegrator...")

        try:
            # Shutdown components through lifecycle manager
            components = {
                "error_pipeline": self.error_pipeline,
                "error_orchestrator": self.error_orchestrator,
                "grammar_cli": self.grammar_cli,
                "grammar_manager": self.grammar_manager,
                "grammar_registry": self.grammar_registry,
                "token_aware_chunker": self.token_aware_chunker,
            }

            self.lifecycle_manager.shutdown_components(components)

            # Clear active sessions
            self.active_sessions.clear()

            # Update component statuses
            for component in self.system_health.components.values():
                component.update_status(HealthStatus.SHUTDOWN)

            self.logger.info("SystemIntegrator shutdown completed")

        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}")

    def __enter__(self):
        """Context manager entry."""
        self.initialize_system()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.shutdown()


# Global system integrator instance
_system_integrator = None
_integrator_lock = threading.Lock()


def get_system_integrator() -> SystemIntegrator:
    """
    Get the global system integrator instance.

    Returns:
        SystemIntegrator instance
    """
    global _system_integrator

    with _integrator_lock:
        if _system_integrator is None:
            _system_integrator = SystemIntegrator()
        return _system_integrator


def initialize_treesitter_system() -> dict[str, Any]:
    """
    Initialize the complete treesitter-chunker system.

    Returns:
        System initialization results
    """
    integrator = get_system_integrator()
    return integrator.initialize_system()


def process_grammar_error(
    error: Exception,
    context: dict[str, Any] | None = None,
    language: str | None = None,
) -> dict[str, Any]:
    """
    Process a grammar error through the integrated system.

    Args:
        error: The exception that occurred
        context: Additional context information
        language: Programming language context

    Returns:
        Processed error information
    """
    integrator = get_system_integrator()
    return integrator.process_grammar_error(error, context, language)


def get_system_health() -> dict[str, Any]:
    """
    Get current system health information.

    Returns:
        System health diagnostics
    """
    integrator = get_system_integrator()
    return integrator.get_system_diagnostics()

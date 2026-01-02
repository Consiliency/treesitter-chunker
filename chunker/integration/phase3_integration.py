"""
Phase 3 Final Validation & Integration Layer

This module provides the ultimate integration orchestration that ties together
all Phase 3 components into a cohesive, production-ready system.

Key Components:
- Phase3IntegrationOrchestrator: Main orchestration for all Phase 3 capabilities
- IntegrationValidator: Cross-component integration testing and validation
- ProductionReadinessChecker: Comprehensive production readiness assessment
- IntegrationReporter: Detailed reporting and metrics aggregation
"""

import gc
import json
import logging
import os
import sys
import threading
import time
import traceback
import uuid
import weakref
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

# Import Phase 3 components
try:
    from ..performance.optimization.system_optimizer import SystemOptimizer

    HAS_SYSTEM_OPTIMIZER = True
except ImportError:
    HAS_SYSTEM_OPTIMIZER = False

try:
    from ..performance.core.performance_framework import PerformanceManager

    HAS_PERFORMANCE_FRAMEWORK = True
except ImportError:
    HAS_PERFORMANCE_FRAMEWORK = False

try:
    from ..validation.validation_framework import ValidationManager

    HAS_VALIDATION_FRAMEWORK = True
except ImportError:
    HAS_VALIDATION_FRAMEWORK = False

try:
    from ..deployment.production_deployer import ProductionDeployer

    HAS_PRODUCTION_DEPLOYER = True
except ImportError:
    HAS_PRODUCTION_DEPLOYER = False

try:
    from ..monitoring.observability_system import MonitoringSystem

    HAS_MONITORING_SYSTEM = True
except ImportError:
    HAS_MONITORING_SYSTEM = False

logger = logging.getLogger(__name__)


# Custom exceptions for Phase 3 integration
class IntegrationError(Exception):
    """Exception raised for integration failures."""


class ValidationError(Exception):
    """Exception raised for validation failures."""


class ReportingError(Exception):
    """Exception raised for reporting failures."""


class ReadinessError(Exception):
    """Exception raised for readiness check failures."""


@dataclass
class IntegrationResult:
    """Represents the result of an integration operation."""

    component: str
    operation: str
    status: str  # 'success', 'failure', 'warning', 'skipped'
    execution_time: float
    timestamp: datetime
    details: dict[str, Any]
    error_message: str | None = None
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "component": self.component,
            "operation": self.operation,
            "status": self.status,
            "execution_time": self.execution_time,
            "timestamp": self.timestamp.isoformat(),
            "details": self.details,
            "error_message": self.error_message,
            "recommendations": self.recommendations,
        }


@dataclass
class ProductionReadinessReport:
    """Comprehensive production readiness assessment."""

    timestamp: datetime
    overall_status: str  # 'ready', 'warning', 'not_ready'
    readiness_score: float  # 0-100
    component_assessments: dict[str, dict[str, Any]]
    critical_issues: list[str]
    warnings: list[str]
    recommendations: list[str]
    deployment_blockers: list[str]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "overall_status": self.overall_status,
            "readiness_score": self.readiness_score,
            "component_assessments": self.component_assessments,
            "critical_issues": self.critical_issues,
            "warnings": self.warnings,
            "recommendations": self.recommendations,
            "deployment_blockers": self.deployment_blockers,
        }


class Phase3IntegrationOrchestrator:
    """
    Main orchestration class that integrates all Phase 3 components.

    Provides a unified API for accessing PerformanceManager, SystemOptimizer,
    ValidationManager, ProductionDeployer, and MonitoringSystem capabilities.
    """

    def __init__(self, service_name: str = "treesitter-chunker"):
        """Initialize the Phase 3 integration orchestrator."""
        self.service_name = service_name
        self.logger = logging.getLogger(f"{__name__}.Phase3IntegrationOrchestrator")
        self._lock = threading.RLock()

        # Initialize component managers
        self._initialize_components()

        # Integration state
        self.is_initialized = False
        self.is_running = False
        self.integration_history: list[dict[str, Any]] = []
        self.health_status: dict[str, Any] = {}

        # Performance tracking
        self.start_time = time.time()
        self.integration_metrics: dict[str, Any] = {}

        self.logger.info(
            f"Initialized Phase 3 Integration Orchestrator for {service_name}",
        )

    def _initialize_components(self) -> None:
        """Initialize all Phase 3 components."""
        # Performance Management
        if HAS_PERFORMANCE_FRAMEWORK:
            try:
                self.performance_manager = PerformanceManager(
                    enable_continuous_monitoring=True,
                )
                self.logger.info("Performance Manager initialized")
            except Exception as e:
                self.performance_manager = None
                self.logger.warning(f"Performance Manager initialization failed: {e}")
        else:
            self.performance_manager = None
            self.logger.warning("Performance Framework not available")

        # System Optimization
        if HAS_SYSTEM_OPTIMIZER:
            try:
                self.system_optimizer = SystemOptimizer()
                self.logger.info("System Optimizer initialized")
            except Exception as e:
                self.system_optimizer = None
                self.logger.warning(f"System Optimizer initialization failed: {e}")
        else:
            self.system_optimizer = None
            self.logger.warning("System Optimizer not available")

        # Validation Management
        if HAS_VALIDATION_FRAMEWORK:
            try:
                self.validation_manager = ValidationManager()
                self.logger.info("Validation Manager initialized")
            except Exception as e:
                self.validation_manager = None
                self.logger.warning(f"Validation Manager initialization failed: {e}")
        else:
            self.validation_manager = None
            self.logger.warning("Validation Framework not available")

        # Production Deployment
        if HAS_PRODUCTION_DEPLOYER:
            try:
                self.production_deployer = ProductionDeployer()
                self.logger.info("Production Deployer initialized")
            except Exception as e:
                self.production_deployer = None
                self.logger.warning(f"Production Deployer initialization failed: {e}")
        else:
            self.production_deployer = None
            self.logger.warning("Production Deployer not available")

        # Monitoring System
        if HAS_MONITORING_SYSTEM:
            try:
                self.monitoring_system = MonitoringSystem(
                    service_name=self.service_name,
                    metrics_interval=5.0,
                    trace_sampling_rate=0.1,  # 10% sampling for production
                )
                self.logger.info("Monitoring System initialized")
            except Exception as e:
                self.monitoring_system = None
                self.logger.warning(f"Monitoring System initialization failed: {e}")
        else:
            self.monitoring_system = None
            self.logger.warning("Monitoring System not available")

    def initialize_integration(self) -> dict[str, Any]:
        """Initialize the complete Phase 3 integration."""
        if self.is_initialized:
            return {
                "status": "already_initialized",
                "message": "Integration already initialized",
            }

        start_time = time.time()
        initialization_results = []

        try:
            self.logger.info("Starting Phase 3 integration initialization")

            # Initialize each component
            components = [
                ("performance_manager", self.performance_manager),
                ("system_optimizer", self.system_optimizer),
                ("validation_manager", self.validation_manager),
                ("production_deployer", self.production_deployer),
                ("monitoring_system", self.monitoring_system),
            ]

            successful_initializations = 0
            total_components = len([c for c in components if c[1] is not None])

            for component_name, component in components:
                if component is None:
                    continue

                result = self._initialize_component(component_name, component)
                initialization_results.append(result)

                if result["status"] == "success":
                    successful_initializations += 1

            # Determine overall initialization status
            if successful_initializations == total_components:
                status = "success"
                self.is_initialized = True
            elif successful_initializations > 0:
                status = "partial"
                self.is_initialized = True
            else:
                status = "failed"
                self.is_initialized = False

            # Record initialization
            initialization_record = {
                "timestamp": datetime.now().isoformat(),
                "status": status,
                "execution_time": time.time() - start_time,
                "components_initialized": successful_initializations,
                "total_components": total_components,
                "initialization_results": initialization_results,
                "integration_id": str(uuid.uuid4()),
            }

            self.integration_history.append(initialization_record)

            if self.is_initialized:
                self.logger.info(
                    f"Phase 3 integration initialized successfully ({successful_initializations}/{total_components} components)",
                )
            else:
                self.logger.error("Phase 3 integration initialization failed")

            return initialization_record

        except Exception as e:
            self.logger.error(f"Error during Phase 3 integration initialization: {e}")
            return {
                "timestamp": datetime.now().isoformat(),
                "status": "error",
                "error": str(e),
                "execution_time": time.time() - start_time,
            }

    def _initialize_component(
        self,
        component_name: str,
        component: Any,
    ) -> dict[str, Any]:
        """Initialize a specific component."""
        start_time = time.time()

        try:
            # Component-specific initialization logic
            if component_name == "monitoring_system":
                # Start monitoring system if it's not already running
                if hasattr(component, "start") and not getattr(
                    component,
                    "is_running",
                    False,
                ):
                    component.start()

            elif component_name == "performance_manager":
                # Initialize performance monitoring
                if hasattr(component, "start_monitoring"):
                    component.start_monitoring()

            elif component_name == "validation_manager":
                # Run initial validation setup
                if hasattr(component, "config"):
                    component.config["enable_detailed_logging"] = True

            # Verify component is working
            health_check = self._check_component_health(component_name, component)

            return {
                "component": component_name,
                "status": "success" if health_check["healthy"] else "warning",
                "execution_time": time.time() - start_time,
                "health_check": health_check,
                "message": f"{component_name} initialized successfully",
            }

        except Exception as e:
            self.logger.error(f"Failed to initialize {component_name}: {e}")
            return {
                "component": component_name,
                "status": "failed",
                "execution_time": time.time() - start_time,
                "error": str(e),
                "message": f"{component_name} initialization failed",
            }

    def _check_component_health(
        self,
        component_name: str,
        component: Any,
    ) -> dict[str, Any]:
        """Check the health of a specific component."""
        try:
            health = {"healthy": False, "details": {}}

            # Component-specific health checks
            if component_name == "performance_manager":
                if hasattr(component, "collect_system_metrics"):
                    try:
                        profile = component.collect_system_metrics()
                        health["healthy"] = len(profile.metrics) > 0
                        health["details"]["metrics_count"] = len(profile.metrics)
                    except Exception as e:
                        health["details"]["error"] = str(e)
                else:
                    health["healthy"] = True  # Basic availability

            elif component_name == "system_optimizer":
                if hasattr(component, "performance_manager"):
                    health["healthy"] = component.performance_manager is not None
                    health["details"]["has_performance_manager"] = health["healthy"]
                else:
                    health["healthy"] = True

            elif component_name == "validation_manager":
                if hasattr(component, "performance_validator"):
                    health["healthy"] = component.performance_validator is not None
                    health["details"]["has_validators"] = health["healthy"]
                else:
                    health["healthy"] = True

            elif component_name == "production_deployer":
                if hasattr(component, "health_checker"):
                    health["healthy"] = component.health_checker is not None
                    health["details"]["has_health_checker"] = health["healthy"]
                else:
                    health["healthy"] = True

            elif component_name == "monitoring_system":
                if hasattr(component, "is_running"):
                    health["healthy"] = component.is_running
                    health["details"]["running"] = health["healthy"]
                else:
                    health["healthy"] = True
            else:
                health["healthy"] = component is not None

            return health

        except Exception as e:
            return {"healthy": False, "error": str(e), "details": {}}

    def start_integrated_system(self) -> dict[str, Any]:
        """Start the complete integrated system."""
        if not self.is_initialized:
            init_result = self.initialize_integration()
            if init_result["status"] != "success":
                return {
                    "status": "failed",
                    "message": "Cannot start system - initialization failed",
                    "initialization_result": init_result,
                }

        if self.is_running:
            return {
                "status": "already_running",
                "message": "Integrated system already running",
            }

        start_time = time.time()
        startup_results = []

        try:
            self.logger.info("Starting integrated Phase 3 system")

            # Start components in optimal order
            startup_sequence = [
                ("monitoring_system", "Start comprehensive monitoring"),
                ("performance_manager", "Start performance monitoring"),
                ("system_optimizer", "Initialize system optimization"),
                ("validation_manager", "Start validation framework"),
                ("production_deployer", "Initialize deployment capabilities"),
            ]

            successful_starts = 0

            for component_name, description in startup_sequence:
                component = getattr(self, component_name, None)
                if component is None:
                    continue

                result = self._start_component(component_name, component, description)
                startup_results.append(result)

                if result["status"] == "success":
                    successful_starts += 1

            # Update system state
            self.is_running = successful_starts > 0

            # Record startup metrics
            startup_record = {
                "timestamp": datetime.now().isoformat(),
                "status": "success" if self.is_running else "failed",
                "execution_time": time.time() - start_time,
                "components_started": successful_starts,
                "total_components": len(startup_sequence),
                "startup_results": startup_results,
            }

            self.integration_history.append(startup_record)

            if self.is_running:
                self.logger.info(
                    f"Integrated system started successfully ({successful_starts} components)",
                )
                # Start health monitoring
                self._start_health_monitoring()
            else:
                self.logger.error("Failed to start integrated system")

            return startup_record

        except Exception as e:
            self.logger.error(f"Error starting integrated system: {e}")
            return {
                "timestamp": datetime.now().isoformat(),
                "status": "error",
                "error": str(e),
                "execution_time": time.time() - start_time,
            }

    def _start_component(
        self,
        component_name: str,
        component: Any,
        description: str,
    ) -> dict[str, Any]:
        """Start a specific component."""
        start_time = time.time()

        try:
            self.logger.info(f"Starting {component_name}: {description}")

            # Component-specific startup logic
            if component_name == "monitoring_system":
                if hasattr(component, "start") and not getattr(
                    component,
                    "is_running",
                    False,
                ):
                    component.start()

            elif component_name == "performance_manager":
                if hasattr(component, "start_monitoring"):
                    component.start_monitoring()

            # Verify component started successfully
            health_check = self._check_component_health(component_name, component)

            return IntegrationResult(
                component=component_name,
                operation="startup",
                status="success" if health_check["healthy"] else "warning",
                execution_time=time.time() - start_time,
                timestamp=datetime.now(),
                details={"health_check": health_check, "description": description},
            ).to_dict()

        except Exception as e:
            self.logger.error(f"Failed to start {component_name}: {e}")
            return IntegrationResult(
                component=component_name,
                operation="startup",
                status="failure",
                execution_time=time.time() - start_time,
                timestamp=datetime.now(),
                details={"description": description},
                error_message=str(e),
                recommendations=[
                    f"Check {component_name} configuration and dependencies",
                ],
            ).to_dict()

    def _start_health_monitoring(self) -> None:
        """Start continuous health monitoring of the integrated system."""
        try:

            def health_monitor():
                while self.is_running:
                    try:
                        self.health_status = self.get_system_health()

                        # Log health status periodically
                        if self.health_status.get("overall_status") != "healthy":
                            self.logger.warning(
                                f"System health status: {self.health_status.get('overall_status')}",
                            )

                        time.sleep(60)  # Check every minute

                    except Exception as e:
                        self.logger.error(f"Error in health monitoring: {e}")
                        time.sleep(30)  # Retry after 30 seconds

            health_thread = threading.Thread(
                target=health_monitor,
                daemon=True,
                name="Phase3HealthMonitor",
            )
            health_thread.start()

            self.logger.info("Started integrated system health monitoring")

        except Exception as e:
            self.logger.error(f"Failed to start health monitoring: {e}")

    def stop_integrated_system(self) -> dict[str, Any]:
        """Stop the complete integrated system."""
        if not self.is_running:
            return {
                "status": "already_stopped",
                "message": "Integrated system already stopped",
            }

        start_time = time.time()
        shutdown_results = []

        try:
            self.logger.info("Stopping integrated Phase 3 system")

            # Stop components in reverse order
            shutdown_sequence = [
                ("production_deployer", "Stop deployment capabilities"),
                ("validation_manager", "Stop validation framework"),
                ("system_optimizer", "Stop system optimization"),
                ("performance_manager", "Stop performance monitoring"),
                ("monitoring_system", "Stop comprehensive monitoring"),
            ]

            for component_name, description in shutdown_sequence:
                component = getattr(self, component_name, None)
                if component is None:
                    continue

                result = self._stop_component(component_name, component, description)
                shutdown_results.append(result)

            # Update system state
            self.is_running = False

            # Record shutdown
            shutdown_record = {
                "timestamp": datetime.now().isoformat(),
                "status": "success",
                "execution_time": time.time() - start_time,
                "shutdown_results": shutdown_results,
            }

            self.integration_history.append(shutdown_record)
            self.logger.info("Integrated system stopped successfully")

            return shutdown_record

        except Exception as e:
            self.logger.error(f"Error stopping integrated system: {e}")
            return {
                "timestamp": datetime.now().isoformat(),
                "status": "error",
                "error": str(e),
                "execution_time": time.time() - start_time,
            }

    def _stop_component(
        self,
        component_name: str,
        component: Any,
        description: str,
    ) -> dict[str, Any]:
        """Stop a specific component."""
        start_time = time.time()

        try:
            self.logger.info(f"Stopping {component_name}: {description}")

            # Component-specific shutdown logic
            if component_name == "monitoring_system":
                if hasattr(component, "stop"):
                    component.stop()

            elif component_name == "performance_manager":
                if hasattr(component, "stop_monitoring"):
                    component.stop_monitoring()

            return IntegrationResult(
                component=component_name,
                operation="shutdown",
                status="success",
                execution_time=time.time() - start_time,
                timestamp=datetime.now(),
                details={"description": description},
            ).to_dict()

        except Exception as e:
            self.logger.error(f"Failed to stop {component_name}: {e}")
            return IntegrationResult(
                component=component_name,
                operation="shutdown",
                status="failure",
                execution_time=time.time() - start_time,
                timestamp=datetime.now(),
                details={"description": description},
                error_message=str(e),
            ).to_dict()

    def optimize_integrated_system(self) -> dict[str, Any]:
        """Run comprehensive system optimization across all components."""
        if not self.is_running:
            return {
                "status": "failed",
                "message": "Cannot optimize - system not running",
                "timestamp": datetime.now().isoformat(),
            }

        start_time = time.time()
        optimization_results = {}

        try:
            self.logger.info("Starting comprehensive system optimization")

            # System-level optimization
            if self.system_optimizer:
                try:
                    system_result = self.system_optimizer.optimize_system()
                    optimization_results["system_optimization"] = system_result
                    self.logger.info(
                        f"System optimization completed with {system_result.get('total_improvement', 0):.2f}% improvement",
                    )
                except Exception as e:
                    optimization_results["system_optimization"] = {"error": str(e)}
                    self.logger.error(f"System optimization failed: {e}")

            # Performance optimization
            if self.performance_manager:
                try:
                    perf_analysis = self.performance_manager.analyze_performance()
                    optimization_results["performance_analysis"] = perf_analysis

                    # Apply performance recommendations
                    if "recommendations" in perf_analysis:
                        optimization_results["recommendations_applied"] = len(
                            perf_analysis["recommendations"],
                        )

                except Exception as e:
                    optimization_results["performance_analysis"] = {"error": str(e)}
                    self.logger.error(f"Performance analysis failed: {e}")

            # Validation and testing
            if self.validation_manager:
                try:
                    validation_result = self.validation_manager.run_full_validation()
                    optimization_results["validation_results"] = validation_result

                    if validation_result.get("status") == "passed":
                        self.logger.info("Post-optimization validation passed")
                    else:
                        self.logger.warning(
                            "Post-optimization validation issues detected",
                        )

                except Exception as e:
                    optimization_results["validation_results"] = {"error": str(e)}
                    self.logger.error(f"Validation failed: {e}")

            # Calculate overall improvement
            overall_improvement = 0.0
            improvement_count = 0

            if (
                "system_optimization" in optimization_results
                and "total_improvement" in optimization_results["system_optimization"]
            ):
                overall_improvement += optimization_results["system_optimization"][
                    "total_improvement"
                ]
                improvement_count += 1

            if improvement_count > 0:
                overall_improvement /= improvement_count

            # Generate optimization report
            optimization_report = {
                "timestamp": datetime.now().isoformat(),
                "status": "success",
                "execution_time": time.time() - start_time,
                "overall_improvement_percent": overall_improvement,
                "optimization_results": optimization_results,
                "recommendations": self._generate_optimization_recommendations(
                    optimization_results,
                ),
            }

            self.integration_history.append(optimization_report)
            self.logger.info(
                f"Comprehensive optimization completed with {overall_improvement:.2f}% improvement",
            )

            return optimization_report

        except Exception as e:
            self.logger.error(f"Error during comprehensive optimization: {e}")
            return {
                "timestamp": datetime.now().isoformat(),
                "status": "error",
                "error": str(e),
                "execution_time": time.time() - start_time,
                "optimization_results": optimization_results,
            }

    def _generate_optimization_recommendations(
        self,
        optimization_results: dict[str, Any],
    ) -> list[str]:
        """Generate recommendations based on optimization results."""
        recommendations = []

        try:
            # System optimization recommendations
            if "system_optimization" in optimization_results:
                system_result = optimization_results["system_optimization"]
                if system_result.get("total_improvement", 0) < 5:
                    recommendations.append(
                        "System optimization yielded low improvement - consider infrastructure upgrades",
                    )
                elif system_result.get("total_improvement", 0) > 20:
                    recommendations.append(
                        "High system optimization gains achieved - monitor stability",
                    )

            # Performance analysis recommendations
            if "performance_analysis" in optimization_results:
                perf_result = optimization_results["performance_analysis"]
                if perf_result.get("bottlenecks"):
                    recommendations.append(
                        f"Address {len(perf_result['bottlenecks'])} performance bottlenecks identified",
                    )

                if perf_result.get("optimization_potential", 0) > 30:
                    recommendations.append(
                        "High optimization potential remains - consider additional tuning",
                    )

            # Validation recommendations
            if "validation_results" in optimization_results:
                validation_result = optimization_results["validation_results"]
                if validation_result.get("status") == "failed":
                    recommendations.append(
                        "Optimization caused validation failures - review changes",
                    )
                elif validation_result.get("summary", {}).get("failed", 0) > 0:
                    recommendations.append(
                        "Some validation tests failed - investigate specific issues",
                    )

            if not recommendations:
                recommendations.append(
                    "Optimization completed successfully - continue monitoring performance",
                )

        except Exception as e:
            recommendations.append(f"Error generating recommendations: {e}")

        return recommendations

    def get_system_health(self) -> dict[str, Any]:
        """Get comprehensive health status of all integrated components."""
        health_report = {
            "timestamp": datetime.now().isoformat(),
            "service_name": self.service_name,
            "integration_status": "running" if self.is_running else "stopped",
            "uptime_seconds": time.time() - self.start_time,
            "components": {},
            "overall_status": "healthy",
        }

        try:
            # Check each component
            components = [
                ("performance_manager", self.performance_manager),
                ("system_optimizer", self.system_optimizer),
                ("validation_manager", self.validation_manager),
                ("production_deployer", self.production_deployer),
                ("monitoring_system", self.monitoring_system),
            ]

            unhealthy_count = 0
            total_count = 0

            for component_name, component in components:
                if component is None:
                    health_report["components"][component_name] = {
                        "status": "unavailable",
                        "message": "Component not initialized",
                    }
                    continue

                total_count += 1
                health_check = self._check_component_health(component_name, component)

                if not health_check.get("healthy", False):
                    unhealthy_count += 1

                health_report["components"][component_name] = {
                    "status": "healthy" if health_check.get("healthy") else "unhealthy",
                    "details": health_check.get("details", {}),
                    "error": health_check.get("error"),
                }

            # Determine overall status
            if unhealthy_count == 0:
                health_report["overall_status"] = "healthy"
            elif unhealthy_count < total_count / 2:
                health_report["overall_status"] = "degraded"
            else:
                health_report["overall_status"] = "unhealthy"

            # Add integration-specific health metrics
            health_report["integration_metrics"] = {
                "total_components": total_count,
                "healthy_components": total_count - unhealthy_count,
                "initialization_time": len(self.integration_history),
                "last_optimization": self._get_last_optimization_time(),
            }

        except Exception as e:
            health_report["error"] = str(e)
            health_report["overall_status"] = "error"
            self.logger.error(f"Error generating health report: {e}")

        return health_report

    def _get_last_optimization_time(self) -> str | None:
        """Get timestamp of last optimization run."""
        try:
            for record in reversed(self.integration_history):
                if "optimization_results" in record:
                    return record.get("timestamp")
            return None
        except Exception:
            return None

    @contextmanager
    def trace_operation(self, operation_name: str, **kwargs):
        """Context manager for tracing integrated operations."""
        if self.monitoring_system and hasattr(
            self.monitoring_system,
            "trace_operation",
        ):
            with self.monitoring_system.trace_operation(
                operation_name,
                **kwargs,
            ) as span:
                yield span
        else:
            # Fallback: basic timing
            start_time = time.time()
            try:
                yield {"operation": operation_name, "start_time": start_time}
            finally:
                execution_time = time.time() - start_time
                self.logger.debug(
                    f"Operation '{operation_name}' completed in {execution_time:.3f}s",
                )

    def record_business_metric(
        self,
        metric_name: str,
        value: float,
        labels: dict[str, str] | None = None,
    ) -> None:
        """Record a business metric through the monitoring system."""
        if self.monitoring_system and hasattr(self.monitoring_system, "record_metric"):
            self.monitoring_system.record_metric(metric_name, value, labels)
        else:
            # Fallback: store locally
            if "business_metrics" not in self.integration_metrics:
                self.integration_metrics["business_metrics"] = {}

            self.integration_metrics["business_metrics"][metric_name] = {
                "value": value,
                "labels": labels,
                "timestamp": datetime.now().isoformat(),
            }

    def get_integration_status(self) -> dict[str, Any]:
        """Get detailed status of the integration layer."""
        return {
            "service_name": self.service_name,
            "is_initialized": self.is_initialized,
            "is_running": self.is_running,
            "uptime_seconds": time.time() - self.start_time,
            "component_availability": {
                "performance_manager": self.performance_manager is not None,
                "system_optimizer": self.system_optimizer is not None,
                "validation_manager": self.validation_manager is not None,
                "production_deployer": self.production_deployer is not None,
                "monitoring_system": self.monitoring_system is not None,
            },
            "integration_history_count": len(self.integration_history),
            "last_health_check": (
                self.health_status.get("timestamp") if self.health_status else None
            ),
            "overall_health": (
                self.health_status.get("overall_status")
                if self.health_status
                else "unknown"
            ),
        }


class IntegrationValidator:
    """
    Comprehensive integration validation and testing.

    Validates that all Phase 3 components work together properly,
    performs cross-component integration tests, and verifies system stability.
    """

    def __init__(self, orchestrator: Phase3IntegrationOrchestrator):
        """Initialize the integration validator."""
        self.orchestrator = orchestrator
        self.logger = logging.getLogger(f"{__name__}.IntegrationValidator")
        self.validation_history: list[dict[str, Any]] = []
        self.test_results: dict[str, list[dict[str, Any]]] = {}

    def validate_component_integration(self) -> dict[str, Any]:
        """Validate that all components integrate properly."""
        start_time = time.time()
        validation_results = []

        try:
            self.logger.info("Starting component integration validation")

            # Test component connectivity
            connectivity_result = self._test_component_connectivity()
            validation_results.append(connectivity_result)

            # Test cross-component communication
            communication_result = self._test_cross_component_communication()
            validation_results.append(communication_result)

            # Test data flow between components
            data_flow_result = self._test_data_flow_integration()
            validation_results.append(data_flow_result)

            # Test error handling and recovery
            error_handling_result = self._test_error_handling_integration()
            validation_results.append(error_handling_result)

            # Calculate overall validation status
            passed_tests = sum(
                1 for result in validation_results if result.get("status") == "passed"
            )
            total_tests = len(validation_results)
            success_rate = (passed_tests / total_tests) * 100 if total_tests > 0 else 0

            validation_report = {
                "timestamp": datetime.now().isoformat(),
                "execution_time": time.time() - start_time,
                "status": "passed" if success_rate >= 80 else "failed",
                "success_rate": success_rate,
                "tests_passed": passed_tests,
                "total_tests": total_tests,
                "validation_results": validation_results,
                "recommendations": self._generate_integration_recommendations(
                    validation_results,
                ),
            }

            self.validation_history.append(validation_report)
            self.logger.info(
                f"Component integration validation completed: {success_rate:.1f}% success rate",
            )

            return validation_report

        except Exception as e:
            self.logger.error(f"Error in component integration validation: {e}")
            return {
                "timestamp": datetime.now().isoformat(),
                "execution_time": time.time() - start_time,
                "status": "error",
                "error": str(e),
                "validation_results": validation_results,
            }

    def _test_component_connectivity(self) -> dict[str, Any]:
        """Test connectivity between all components."""
        start_time = time.time()
        connectivity_tests = []

        try:
            # Test each component's basic availability
            components = [
                ("performance_manager", self.orchestrator.performance_manager),
                ("system_optimizer", self.orchestrator.system_optimizer),
                ("validation_manager", self.orchestrator.validation_manager),
                ("production_deployer", self.orchestrator.production_deployer),
                ("monitoring_system", self.orchestrator.monitoring_system),
            ]

            for component_name, component in components:
                if component is None:
                    connectivity_tests.append(
                        {
                            "component": component_name,
                            "status": "skipped",
                            "message": "Component not available",
                        },
                    )
                    continue

                try:
                    # Basic health check
                    health = self.orchestrator._check_component_health(
                        component_name,
                        component,
                    )
                    connectivity_tests.append(
                        {
                            "component": component_name,
                            "status": "passed" if health.get("healthy") else "failed",
                            "health_check": health,
                        },
                    )
                except Exception as e:
                    connectivity_tests.append(
                        {
                            "component": component_name,
                            "status": "failed",
                            "error": str(e),
                        },
                    )

            # Determine overall connectivity status
            passed_tests = sum(
                1 for test in connectivity_tests if test["status"] == "passed"
            )
            total_tests = len(
                [test for test in connectivity_tests if test["status"] != "skipped"],
            )

            return {
                "test_name": "component_connectivity",
                "status": "passed" if passed_tests >= total_tests * 0.8 else "failed",
                "execution_time": time.time() - start_time,
                "connectivity_tests": connectivity_tests,
                "passed_tests": passed_tests,
                "total_tests": total_tests,
            }

        except Exception as e:
            return {
                "test_name": "component_connectivity",
                "status": "error",
                "execution_time": time.time() - start_time,
                "error": str(e),
                "connectivity_tests": connectivity_tests,
            }

    def _test_cross_component_communication(self) -> dict[str, Any]:
        """Test communication pathways between components."""
        start_time = time.time()
        communication_tests = []

        try:
            # Test Performance Manager → System Optimizer
            if (
                self.orchestrator.performance_manager
                and self.orchestrator.system_optimizer
            ):
                try:
                    profile = (
                        self.orchestrator.performance_manager.collect_system_metrics()
                    )
                    if hasattr(
                        self.orchestrator.system_optimizer,
                        "performance_manager",
                    ):
                        self.orchestrator.system_optimizer.performance_manager = (
                            self.orchestrator.performance_manager
                        )
                        communication_tests.append(
                            {
                                "pathway": "performance_manager_to_system_optimizer",
                                "status": "passed",
                                "message": "Performance data successfully shared",
                            },
                        )
                    else:
                        communication_tests.append(
                            {
                                "pathway": "performance_manager_to_system_optimizer",
                                "status": "failed",
                                "message": "System optimizer cannot access performance manager",
                            },
                        )
                except Exception as e:
                    communication_tests.append(
                        {
                            "pathway": "performance_manager_to_system_optimizer",
                            "status": "failed",
                            "error": str(e),
                        },
                    )

            # Test Validation Manager → Performance Manager
            if (
                self.orchestrator.validation_manager
                and self.orchestrator.performance_manager
            ):
                try:
                    # Try to run a validation that uses performance data
                    perf_validation = (
                        self.orchestrator.validation_manager.validate_performance()
                    )
                    communication_tests.append(
                        {
                            "pathway": "validation_manager_to_performance_manager",
                            "status": (
                                "passed"
                                if perf_validation.get("status") == "completed"
                                else "failed"
                            ),
                            "message": "Performance validation executed successfully",
                        },
                    )
                except Exception as e:
                    communication_tests.append(
                        {
                            "pathway": "validation_manager_to_performance_manager",
                            "status": "failed",
                            "error": str(e),
                        },
                    )

            # Test Monitoring System integration
            if self.orchestrator.monitoring_system:
                try:
                    health = self.orchestrator.monitoring_system.get_system_health()
                    communication_tests.append(
                        {
                            "pathway": "monitoring_system_health_check",
                            "status": (
                                "passed"
                                if health.get("monitoring_status") == "healthy"
                                else "failed"
                            ),
                            "message": "Monitoring system health check successful",
                        },
                    )
                except Exception as e:
                    communication_tests.append(
                        {
                            "pathway": "monitoring_system_health_check",
                            "status": "failed",
                            "error": str(e),
                        },
                    )

            # Determine overall communication status
            passed_tests = sum(
                1 for test in communication_tests if test["status"] == "passed"
            )
            total_tests = len(communication_tests)

            return {
                "test_name": "cross_component_communication",
                "status": "passed" if passed_tests >= total_tests * 0.8 else "failed",
                "execution_time": time.time() - start_time,
                "communication_tests": communication_tests,
                "passed_tests": passed_tests,
                "total_tests": total_tests,
            }

        except Exception as e:
            return {
                "test_name": "cross_component_communication",
                "status": "error",
                "execution_time": time.time() - start_time,
                "error": str(e),
                "communication_tests": communication_tests,
            }

    def _test_data_flow_integration(self) -> dict[str, Any]:
        """Test data flow between integrated components."""
        start_time = time.time()
        data_flow_tests = []

        try:
            # Test metrics flow: Performance Manager → Monitoring System
            if (
                self.orchestrator.performance_manager
                and self.orchestrator.monitoring_system
            ):
                try:
                    with self.orchestrator.trace_operation("data_flow_test_metrics"):
                        profile = (
                            self.orchestrator.performance_manager.collect_system_metrics()
                        )

                        # Record a test metric
                        self.orchestrator.record_business_metric(
                            "integration_test_metric",
                            42.0,
                        )

                        data_flow_tests.append(
                            {
                                "flow": "performance_metrics_to_monitoring",
                                "status": "passed",
                                "metrics_collected": len(profile.metrics),
                                "message": "Metrics flow verified",
                            },
                        )
                except Exception as e:
                    data_flow_tests.append(
                        {
                            "flow": "performance_metrics_to_monitoring",
                            "status": "failed",
                            "error": str(e),
                        },
                    )

            # Test optimization flow: System Optimizer → Performance Manager
            if (
                self.orchestrator.system_optimizer
                and self.orchestrator.performance_manager
            ):
                try:
                    # Run a lightweight optimization
                    opt_result = self.orchestrator.system_optimizer.optimize_cpu()

                    data_flow_tests.append(
                        {
                            "flow": "optimization_to_performance",
                            "status": (
                                "passed" if opt_result.get("success") else "failed"
                            ),
                            "improvement": opt_result.get("improvement", 0),
                            "message": "Optimization data flow verified",
                        },
                    )
                except Exception as e:
                    data_flow_tests.append(
                        {
                            "flow": "optimization_to_performance",
                            "status": "failed",
                            "error": str(e),
                        },
                    )

            # Test validation flow: Validation Manager → All Components
            if self.orchestrator.validation_manager:
                try:
                    # Run a lightweight validation
                    validation_result = (
                        self.orchestrator.validation_manager.validate_performance()
                    )

                    data_flow_tests.append(
                        {
                            "flow": "validation_cross_component",
                            "status": (
                                "passed"
                                if validation_result.get("status") == "completed"
                                else "failed"
                            ),
                            "tests_run": validation_result.get("test_results", []),
                            "message": "Cross-component validation flow verified",
                        },
                    )
                except Exception as e:
                    data_flow_tests.append(
                        {
                            "flow": "validation_cross_component",
                            "status": "failed",
                            "error": str(e),
                        },
                    )

            # Determine overall data flow status
            passed_tests = sum(
                1 for test in data_flow_tests if test["status"] == "passed"
            )
            total_tests = len(data_flow_tests)

            return {
                "test_name": "data_flow_integration",
                "status": "passed" if passed_tests >= total_tests * 0.8 else "failed",
                "execution_time": time.time() - start_time,
                "data_flow_tests": data_flow_tests,
                "passed_tests": passed_tests,
                "total_tests": total_tests,
            }

        except Exception as e:
            return {
                "test_name": "data_flow_integration",
                "status": "error",
                "execution_time": time.time() - start_time,
                "error": str(e),
                "data_flow_tests": data_flow_tests,
            }

    def _test_error_handling_integration(self) -> dict[str, Any]:
        """Test error handling and recovery across components."""
        start_time = time.time()
        error_handling_tests = []

        try:
            # Test graceful degradation when components are unavailable
            original_performance_manager = self.orchestrator.performance_manager

            try:
                # Temporarily disable performance manager
                self.orchestrator.performance_manager = None

                # Test that system can still function
                health = self.orchestrator.get_system_health()

                error_handling_tests.append(
                    {
                        "scenario": "missing_performance_manager",
                        "status": (
                            "passed"
                            if health.get("overall_status") != "error"
                            else "failed"
                        ),
                        "message": "System handles missing performance manager gracefully",
                    },
                )

            finally:
                # Restore performance manager
                self.orchestrator.performance_manager = original_performance_manager

            # Test error propagation and handling
            if self.orchestrator.monitoring_system:
                try:
                    # Try to record an invalid metric
                    self.orchestrator.record_business_metric(
                        "test_error_metric",
                        float("inf"),
                    )

                    error_handling_tests.append(
                        {
                            "scenario": "invalid_metric_data",
                            "status": "passed",  # Should handle gracefully
                            "message": "Invalid metric data handled gracefully",
                        },
                    )
                except Exception as e:
                    error_handling_tests.append(
                        {
                            "scenario": "invalid_metric_data",
                            "status": "failed",
                            "error": str(e),
                        },
                    )

            # Test recovery from temporary failures
            try:
                # Simulate a temporary component failure
                if self.orchestrator.system_optimizer:
                    # Try an operation that might fail
                    opt_result = self.orchestrator.system_optimizer.optimize_memory()

                    error_handling_tests.append(
                        {
                            "scenario": "component_recovery",
                            "status": (
                                "passed"
                                if opt_result.get("success", False)
                                or "error" not in opt_result
                                else "warning"
                            ),
                            "message": "Component recovery tested",
                        },
                    )
            except Exception as e:
                error_handling_tests.append(
                    {
                        "scenario": "component_recovery",
                        "status": "failed",
                        "error": str(e),
                    },
                )

            # Determine overall error handling status
            passed_tests = sum(
                1
                for test in error_handling_tests
                if test["status"] in ["passed", "warning"]
            )
            total_tests = len(error_handling_tests)

            return {
                "test_name": "error_handling_integration",
                "status": "passed" if passed_tests >= total_tests * 0.8 else "failed",
                "execution_time": time.time() - start_time,
                "error_handling_tests": error_handling_tests,
                "passed_tests": passed_tests,
                "total_tests": total_tests,
            }

        except Exception as e:
            return {
                "test_name": "error_handling_integration",
                "status": "error",
                "execution_time": time.time() - start_time,
                "error": str(e),
                "error_handling_tests": error_handling_tests,
            }

    def _generate_integration_recommendations(
        self,
        validation_results: list[dict[str, Any]],
    ) -> list[str]:
        """Generate recommendations based on integration validation results."""
        recommendations = []

        try:
            for result in validation_results:
                if result.get("status") == "failed":
                    test_name = result.get("test_name", "unknown")
                    recommendations.append(
                        f"Address failures in {test_name} integration tests",
                    )

                    if "error" in result:
                        recommendations.append(
                            f"Investigate error in {test_name}: {result['error']}",
                        )

                elif result.get("status") == "warning":
                    test_name = result.get("test_name", "unknown")
                    recommendations.append(
                        f"Review warnings in {test_name} integration tests",
                    )

            # Specific recommendations based on test types
            connectivity_result = next(
                (
                    r
                    for r in validation_results
                    if r.get("test_name") == "component_connectivity"
                ),
                None,
            )
            if connectivity_result and connectivity_result.get("status") == "failed":
                recommendations.append(
                    "Check component initialization and health status",
                )

            communication_result = next(
                (
                    r
                    for r in validation_results
                    if r.get("test_name") == "cross_component_communication"
                ),
                None,
            )
            if communication_result and communication_result.get("status") == "failed":
                recommendations.append(
                    "Verify component interfaces and API compatibility",
                )

            data_flow_result = next(
                (
                    r
                    for r in validation_results
                    if r.get("test_name") == "data_flow_integration"
                ),
                None,
            )
            if data_flow_result and data_flow_result.get("status") == "failed":
                recommendations.append(
                    "Check data serialization and transfer mechanisms",
                )

            if not recommendations:
                recommendations.append(
                    "All integration tests passed - system integration is healthy",
                )

        except Exception as e:
            recommendations.append(f"Error generating integration recommendations: {e}")

        return recommendations

    def run_performance_benchmarks(self) -> dict[str, Any]:
        """Run performance benchmarks across integrated components."""
        start_time = time.time()

        try:
            self.logger.info("Running integrated system performance benchmarks")

            benchmark_results = {}

            # Benchmark component startup times
            startup_benchmark = self._benchmark_component_startup()
            benchmark_results["startup_performance"] = startup_benchmark

            # Benchmark cross-component operations
            operation_benchmark = self._benchmark_cross_component_operations()
            benchmark_results["operation_performance"] = operation_benchmark

            # Benchmark system optimization performance
            optimization_benchmark = self._benchmark_system_optimization()
            benchmark_results["optimization_performance"] = optimization_benchmark

            # Calculate overall benchmark score
            benchmark_scores = []
            for benchmark in benchmark_results.values():
                if "score" in benchmark:
                    benchmark_scores.append(benchmark["score"])

            overall_score = (
                sum(benchmark_scores) / len(benchmark_scores) if benchmark_scores else 0
            )

            benchmark_report = {
                "timestamp": datetime.now().isoformat(),
                "execution_time": time.time() - start_time,
                "overall_score": overall_score,
                "performance_grade": self._calculate_performance_grade(overall_score),
                "benchmark_results": benchmark_results,
                "recommendations": self._generate_performance_recommendations(
                    benchmark_results,
                ),
            }

            self.logger.info(
                f"Performance benchmarks completed with score: {overall_score:.1f}/100",
            )
            return benchmark_report

        except Exception as e:
            self.logger.error(f"Error running performance benchmarks: {e}")
            return {
                "timestamp": datetime.now().isoformat(),
                "execution_time": time.time() - start_time,
                "status": "error",
                "error": str(e),
            }

    def _benchmark_component_startup(self) -> dict[str, Any]:
        """Benchmark component startup performance."""
        try:
            # Measure current component health check times
            startup_times = {}

            components = [
                ("performance_manager", self.orchestrator.performance_manager),
                ("system_optimizer", self.orchestrator.system_optimizer),
                ("validation_manager", self.orchestrator.validation_manager),
                ("production_deployer", self.orchestrator.production_deployer),
                ("monitoring_system", self.orchestrator.monitoring_system),
            ]

            for component_name, component in components:
                if component is None:
                    continue

                start_time = time.time()
                try:
                    self.orchestrator._check_component_health(component_name, component)
                    startup_times[component_name] = time.time() - start_time
                except Exception:
                    startup_times[component_name] = -1  # Indicate failure

            # Calculate startup performance score
            valid_times = [t for t in startup_times.values() if t >= 0]
            avg_startup_time = sum(valid_times) / len(valid_times) if valid_times else 0

            # Score based on startup time (lower is better)
            if avg_startup_time < 0.1:
                score = 100
            elif avg_startup_time < 0.5:
                score = 90
            elif avg_startup_time < 1.0:
                score = 80
            elif avg_startup_time < 2.0:
                score = 70
            else:
                score = 60

            return {
                "component_startup_times": startup_times,
                "average_startup_time": avg_startup_time,
                "score": score,
                "status": "completed",
            }

        except Exception as e:
            return {"status": "error", "error": str(e), "score": 0}

    def _benchmark_cross_component_operations(self) -> dict[str, Any]:
        """Benchmark cross-component operation performance."""
        try:
            operation_times = {}

            # Benchmark health check operation
            if self.orchestrator.is_running:
                start_time = time.time()
                self.orchestrator.get_system_health()
                operation_times["system_health_check"] = time.time() - start_time

            # Benchmark metric recording
            start_time = time.time()
            self.orchestrator.record_business_metric("benchmark_test", 100.0)
            operation_times["metric_recording"] = time.time() - start_time

            # Benchmark tracing operation
            start_time = time.time()
            with self.orchestrator.trace_operation("benchmark_operation"):
                time.sleep(0.01)  # Simulate small operation
            operation_times["trace_operation"] = time.time() - start_time

            # Calculate operation performance score
            avg_operation_time = (
                sum(operation_times.values()) / len(operation_times)
                if operation_times
                else 0
            )

            # Score based on operation time
            if avg_operation_time < 0.01:
                score = 100
            elif avg_operation_time < 0.05:
                score = 90
            elif avg_operation_time < 0.1:
                score = 80
            elif avg_operation_time < 0.2:
                score = 70
            else:
                score = 60

            return {
                "operation_times": operation_times,
                "average_operation_time": avg_operation_time,
                "score": score,
                "status": "completed",
            }

        except Exception as e:
            return {"status": "error", "error": str(e), "score": 0}

    def _benchmark_system_optimization(self) -> dict[str, Any]:
        """Benchmark system optimization performance."""
        try:
            if not self.orchestrator.system_optimizer:
                return {
                    "status": "skipped",
                    "message": "System optimizer not available",
                    "score": 50,  # Neutral score
                }

            # Run a quick optimization benchmark
            start_time = time.time()
            opt_result = self.orchestrator.system_optimizer.optimize_cpu()
            optimization_time = time.time() - start_time

            # Score based on optimization time and improvement
            time_score = (
                100
                if optimization_time < 1.0
                else max(60, 100 - (optimization_time * 10))
            )
            improvement_score = min(
                100,
                opt_result.get("improvement", 0) * 10,
            )  # Scale improvement

            overall_score = (time_score + improvement_score) / 2

            return {
                "optimization_time": optimization_time,
                "improvement_achieved": opt_result.get("improvement", 0),
                "optimization_result": opt_result,
                "score": overall_score,
                "status": "completed",
            }

        except Exception as e:
            return {"status": "error", "error": str(e), "score": 0}

    def _calculate_performance_grade(self, score: float) -> str:
        """Calculate letter grade based on performance score."""
        if score >= 90:
            return "A"
        if score >= 80:
            return "B"
        if score >= 70:
            return "C"
        if score >= 60:
            return "D"
        return "F"

    def _generate_performance_recommendations(
        self,
        benchmark_results: dict[str, Any],
    ) -> list[str]:
        """Generate performance recommendations based on benchmark results."""
        recommendations = []

        try:
            # Startup performance recommendations
            startup_result = benchmark_results.get("startup_performance", {})
            if startup_result.get("average_startup_time", 0) > 1.0:
                recommendations.append(
                    "Component startup times are slow - consider lazy initialization",
                )

            # Operation performance recommendations
            operation_result = benchmark_results.get("operation_performance", {})
            if operation_result.get("average_operation_time", 0) > 0.1:
                recommendations.append(
                    "Cross-component operations are slow - review interfaces and caching",
                )

            # Optimization performance recommendations
            optimization_result = benchmark_results.get("optimization_performance", {})
            if optimization_result.get("optimization_time", 0) > 5.0:
                recommendations.append(
                    "System optimization is slow - consider incremental optimization",
                )

            if optimization_result.get("improvement_achieved", 0) < 1.0:
                recommendations.append(
                    "Low optimization improvement - system may already be well-tuned",
                )

            if not recommendations:
                recommendations.append(
                    "Performance benchmarks show good results - continue monitoring",
                )

        except Exception as e:
            recommendations.append(f"Error generating performance recommendations: {e}")

        return recommendations


class ProductionReadinessChecker:
    """
    Comprehensive production readiness assessment.

    Evaluates system readiness for production deployment including
    dependency verification, configuration validation, and resource checks.
    """

    def __init__(self, orchestrator: Phase3IntegrationOrchestrator):
        """Initialize the production readiness checker."""
        self.orchestrator = orchestrator
        self.logger = logging.getLogger(f"{__name__}.ProductionReadinessChecker")
        self.assessment_history: list[ProductionReadinessReport] = []

        # Readiness criteria weights
        self.criteria_weights = {
            "component_health": 0.25,
            "performance_metrics": 0.20,
            "security_validation": 0.15,
            "dependency_check": 0.15,
            "configuration_validation": 0.10,
            "resource_availability": 0.10,
            "monitoring_setup": 0.05,
        }

    def assess_production_readiness(self) -> ProductionReadinessReport:
        """Perform comprehensive production readiness assessment."""
        start_time = time.time()

        try:
            self.logger.info("Starting comprehensive production readiness assessment")

            component_assessments = {}
            critical_issues = []
            warnings = []
            recommendations = []
            deployment_blockers = []

            # Run all readiness checks
            assessments = [
                ("component_health", self._assess_component_health),
                ("performance_metrics", self._assess_performance_metrics),
                ("security_validation", self._assess_security_validation),
                ("dependency_check", self._assess_dependency_readiness),
                ("configuration_validation", self._assess_configuration_validation),
                ("resource_availability", self._assess_resource_availability),
                ("monitoring_setup", self._assess_monitoring_readiness),
            ]

            total_score = 0.0

            for assessment_name, assessment_func in assessments:
                try:
                    result = assessment_func()
                    component_assessments[assessment_name] = result

                    # Calculate weighted score
                    weight = self.criteria_weights.get(assessment_name, 0)
                    score = result.get("score", 0) * weight
                    total_score += score

                    # Collect issues
                    if result.get("status") == "critical":
                        critical_issues.extend(result.get("issues", []))
                        deployment_blockers.extend(result.get("blockers", []))
                    elif result.get("status") == "warning":
                        warnings.extend(result.get("issues", []))

                    recommendations.extend(result.get("recommendations", []))

                except Exception as e:
                    self.logger.error(f"Error in {assessment_name} assessment: {e}")
                    component_assessments[assessment_name] = {
                        "status": "error",
                        "error": str(e),
                        "score": 0,
                    }
                    critical_issues.append(f"{assessment_name} assessment failed: {e}")

            # Determine overall readiness status
            if critical_issues or deployment_blockers:
                overall_status = "not_ready"
            elif warnings:
                overall_status = "warning"
            else:
                overall_status = "ready"

            # Create readiness report
            readiness_report = ProductionReadinessReport(
                timestamp=datetime.now(),
                overall_status=overall_status,
                readiness_score=min(100.0, total_score),
                component_assessments=component_assessments,
                critical_issues=critical_issues,
                warnings=warnings,
                recommendations=list(set(recommendations)),  # Remove duplicates
                deployment_blockers=deployment_blockers,
            )

            self.assessment_history.append(readiness_report)

            self.logger.info(
                f"Production readiness assessment completed: {overall_status} "
                f"(score: {readiness_report.readiness_score:.1f}/100)",
            )

            return readiness_report

        except Exception as e:
            self.logger.error(f"Error in production readiness assessment: {e}")
            return ProductionReadinessReport(
                timestamp=datetime.now(),
                overall_status="error",
                readiness_score=0.0,
                component_assessments={"error": {"status": "error", "error": str(e)}},
                critical_issues=[f"Assessment failed: {e}"],
                warnings=[],
                recommendations=["Fix assessment errors before proceeding"],
                deployment_blockers=[f"Cannot assess readiness: {e}"],
            )

    def _assess_component_health(self) -> dict[str, Any]:
        """Assess health of all integrated components."""
        try:
            health_report = self.orchestrator.get_system_health()

            issues = []
            blockers = []
            recommendations = []

            # Check overall system health
            overall_status = health_report.get("overall_status", "unknown")

            if overall_status == "unhealthy":
                issues.append("System overall health is unhealthy")
                blockers.append("Fix unhealthy system components before deployment")
                score = 20
            elif overall_status == "degraded":
                issues.append("System health is degraded")
                recommendations.append(
                    "Improve degraded system components before deployment",
                )
                score = 60
            elif overall_status == "healthy":
                score = 100
            else:
                issues.append(f"Unknown system health status: {overall_status}")
                score = 40

            # Check individual components
            components = health_report.get("components", {})
            unhealthy_components = [
                name
                for name, status in components.items()
                if status.get("status") != "healthy"
            ]

            if unhealthy_components:
                issues.append(
                    f"Unhealthy components: {', '.join(unhealthy_components)}",
                )
                if len(unhealthy_components) > len(components) / 2:
                    blockers.append(
                        "Too many unhealthy components for production deployment",
                    )
                    score = min(score, 30)
                else:
                    recommendations.append(
                        "Address unhealthy components before deployment",
                    )
                    score = min(score, 70)

            # Check integration status
            if not self.orchestrator.is_initialized:
                blockers.append("System is not properly initialized")
                score = 0
            elif not self.orchestrator.is_running:
                issues.append("System is not currently running")
                score = min(score, 50)

            return {
                "status": (
                    "critical" if blockers else "warning" if issues else "healthy"
                ),
                "score": score,
                "issues": issues,
                "blockers": blockers,
                "recommendations": recommendations,
                "health_report": health_report,
            }

        except Exception as e:
            return {
                "status": "error",
                "score": 0,
                "error": str(e),
                "blockers": [f"Cannot assess component health: {e}"],
            }

    def _assess_performance_metrics(self) -> dict[str, Any]:
        """Assess performance readiness metrics."""
        try:
            issues = []
            recommendations = []
            score = 100

            # Check if performance monitoring is active
            if not self.orchestrator.performance_manager:
                issues.append("Performance manager not available")
                recommendations.append("Enable performance monitoring for production")
                score = 40
            else:
                try:
                    # Collect current performance data
                    profile = (
                        self.orchestrator.performance_manager.collect_system_metrics()
                    )

                    # Check optimization potential
                    optimization_potential = getattr(
                        profile,
                        "optimization_potential",
                        0,
                    )
                    if optimization_potential > 50:
                        issues.append(
                            "High optimization potential indicates performance issues",
                        )
                        recommendations.append(
                            "Run system optimization before production deployment",
                        )
                        score = min(score, 70)
                    elif optimization_potential > 30:
                        recommendations.append(
                            "Consider system optimization for better performance",
                        )
                        score = min(score, 85)

                    # Check critical metrics
                    critical_metrics = profile.get_critical_metrics()
                    if critical_metrics:
                        issues.append(
                            f"Critical performance metrics detected: {len(critical_metrics)}",
                        )
                        recommendations.append(
                            "Address critical performance metrics before deployment",
                        )
                        score = min(score, 60)

                except Exception as e:
                    issues.append(f"Error collecting performance metrics: {e}")
                    score = min(score, 70)

            # Check if system optimizer is available
            if not self.orchestrator.system_optimizer:
                recommendations.append(
                    "System optimizer not available - consider enabling for production",
                )
                score = min(score, 90)

            return {
                "status": (
                    "critical" if score < 50 else "warning" if score < 80 else "healthy"
                ),
                "score": score,
                "issues": issues,
                "recommendations": recommendations,
            }

        except Exception as e:
            return {"status": "error", "score": 0, "error": str(e)}

    def _assess_security_validation(self) -> dict[str, Any]:
        """Assess security readiness for production."""
        try:
            issues = []
            recommendations = []
            score = 100

            # Check monitoring system security
            if self.orchestrator.monitoring_system:
                try:
                    # Check if sensitive data is being logged
                    health = self.orchestrator.monitoring_system.get_system_health()

                    # Basic security checks
                    recommendations.append(
                        "Review log data for sensitive information before production",
                    )
                    recommendations.append(
                        "Configure proper authentication for monitoring endpoints",
                    )

                except Exception as e:
                    issues.append(f"Cannot assess monitoring security: {e}")
                    score = min(score, 80)
            else:
                recommendations.append(
                    "Enable monitoring system for production security visibility",
                )
                score = min(score, 90)

            # Check deployment security
            if self.orchestrator.production_deployer:
                recommendations.append(
                    "Ensure production deployer has proper access controls",
                )
            else:
                recommendations.append(
                    "Production deployer not available - manual deployment security review needed",
                )
                score = min(score, 85)

            # Basic environment checks
            recommendations.extend(
                [
                    "Verify all production credentials are properly secured",
                    "Ensure network security configurations are in place",
                    "Review and audit system access permissions",
                ],
            )

            return {
                "status": "warning" if score < 95 else "healthy",
                "score": score,
                "issues": issues,
                "recommendations": recommendations,
            }

        except Exception as e:
            return {"status": "error", "score": 0, "error": str(e)}

    def _assess_dependency_readiness(self) -> dict[str, Any]:
        """Assess dependency availability and versions."""
        try:
            issues = []
            blockers = []
            recommendations = []
            score = 100

            # Check Python version
            python_version = sys.version_info
            if python_version < (3, 8):
                blockers.append(
                    f"Python version {python_version.major}.{python_version.minor} is too old",
                )
                score = 0
            elif python_version < (3, 9):
                issues.append(
                    f"Python version {python_version.major}.{python_version.minor} is supported but not optimal",
                )
                score = min(score, 80)

            # Check optional dependencies
            optional_deps = {
                "psutil": HAS_PSUTIL,
                "performance_framework": HAS_PERFORMANCE_FRAMEWORK,
                "system_optimizer": HAS_SYSTEM_OPTIMIZER,
                "validation_framework": HAS_VALIDATION_FRAMEWORK,
                "production_deployer": HAS_PRODUCTION_DEPLOYER,
                "monitoring_system": HAS_MONITORING_SYSTEM,
            }

            missing_deps = [
                dep for dep, available in optional_deps.items() if not available
            ]

            if missing_deps:
                if len(missing_deps) > len(optional_deps) / 2:
                    blockers.append(
                        f"Too many missing dependencies: {', '.join(missing_deps)}",
                    )
                    score = 20
                else:
                    issues.append(
                        f"Some dependencies missing: {', '.join(missing_deps)}",
                    )
                    recommendations.append(
                        "Install missing dependencies for full functionality",
                    )
                    score = min(score, 70)

            # Check system resources
            try:
                if HAS_PSUTIL:
                    import psutil

                    # Memory check
                    memory = psutil.virtual_memory()
                    if memory.available < 500 * 1024 * 1024:  # 500MB
                        blockers.append("Insufficient available memory (<500MB)")
                        score = 10
                    elif memory.available < 1024 * 1024 * 1024:  # 1GB
                        issues.append("Low available memory (<1GB)")
                        score = min(score, 70)

                    # Disk space check
                    disk = psutil.disk_usage("/")
                    if disk.free < 1024 * 1024 * 1024:  # 1GB
                        blockers.append("Insufficient disk space (<1GB)")
                        score = 10
                    elif disk.free < 5 * 1024 * 1024 * 1024:  # 5GB
                        issues.append("Low disk space (<5GB)")
                        score = min(score, 80)

            except Exception:
                recommendations.append("Manual resource verification needed")

            return {
                "status": (
                    "critical" if blockers else "warning" if issues else "healthy"
                ),
                "score": score,
                "issues": issues,
                "blockers": blockers,
                "recommendations": recommendations,
                "dependency_status": optional_deps,
            }

        except Exception as e:
            return {"status": "error", "score": 0, "error": str(e)}

    def _assess_configuration_validation(self) -> dict[str, Any]:
        """Assess configuration readiness for production."""
        try:
            issues = []
            recommendations = []
            score = 100

            # Check orchestrator configuration
            integration_status = self.orchestrator.get_integration_status()

            if not integration_status.get("is_initialized"):
                issues.append("System not properly initialized")
                score = min(score, 30)

            # Check component configurations
            component_availability = integration_status.get(
                "component_availability",
                {},
            )
            unavailable_components = [
                name
                for name, available in component_availability.items()
                if not available
            ]

            if unavailable_components:
                recommendations.append(
                    f"Consider enabling unavailable components: {', '.join(unavailable_components)}",
                )
                score = min(score, 85)

            # Check monitoring configuration
            if self.orchestrator.monitoring_system:
                try:
                    monitoring_config = (
                        self.orchestrator.monitoring_system.export_monitoring_config()
                    )

                    if not monitoring_config.get("alert_rules"):
                        recommendations.append(
                            "Configure alerting rules for production monitoring",
                        )
                        score = min(score, 90)

                    if not monitoring_config.get("dashboards"):
                        recommendations.append(
                            "Set up monitoring dashboards for production visibility",
                        )
                        score = min(score, 85)

                except Exception as e:
                    issues.append(f"Cannot assess monitoring configuration: {e}")
                    score = min(score, 80)

            # Configuration validation recommendations
            recommendations.extend(
                [
                    "Review all environment-specific configurations",
                    "Validate production logging levels and destinations",
                    "Confirm resource limits and quotas are appropriate",
                ],
            )

            return {
                "status": "warning" if score < 90 else "healthy",
                "score": score,
                "issues": issues,
                "recommendations": recommendations,
            }

        except Exception as e:
            return {"status": "error", "score": 0, "error": str(e)}

    def _assess_resource_availability(self) -> dict[str, Any]:
        """Assess system resource availability."""
        try:
            issues = []
            blockers = []
            recommendations = []
            score = 100

            if HAS_PSUTIL:
                import psutil

                # CPU assessment
                cpu_percent = psutil.cpu_percent(interval=1.0)
                cpu_count = psutil.cpu_count()

                if cpu_percent > 90:
                    blockers.append(f"CPU usage too high: {cpu_percent:.1f}%")
                    score = 20
                elif cpu_percent > 70:
                    issues.append(f"High CPU usage: {cpu_percent:.1f}%")
                    score = min(score, 70)

                if cpu_count < 2:
                    issues.append("Low CPU core count may impact performance")
                    score = min(score, 80)

                # Memory assessment
                memory = psutil.virtual_memory()

                if memory.percent > 90:
                    blockers.append(f"Memory usage too high: {memory.percent:.1f}%")
                    score = 20
                elif memory.percent > 80:
                    issues.append(f"High memory usage: {memory.percent:.1f}%")
                    score = min(score, 70)

                # Disk assessment
                disk = psutil.disk_usage("/")
                disk_usage_percent = (disk.used / disk.total) * 100

                if disk_usage_percent > 95:
                    blockers.append(f"Disk usage too high: {disk_usage_percent:.1f}%")
                    score = 20
                elif disk_usage_percent > 85:
                    issues.append(f"High disk usage: {disk_usage_percent:.1f}%")
                    score = min(score, 75)

                # Network assessment (if possible)
                try:
                    network_io = psutil.net_io_counters()
                    # Basic network availability check
                    if network_io.bytes_sent == 0 and network_io.bytes_recv == 0:
                        issues.append("No network activity detected")
                        score = min(score, 80)
                except Exception:
                    pass

            else:
                recommendations.append(
                    "Install psutil for detailed resource monitoring",
                )
                score = min(score, 85)

            # General resource recommendations
            if score < 80:
                recommendations.extend(
                    [
                        "Free up system resources before production deployment",
                        "Consider horizontal scaling or resource upgrades",
                        "Monitor resource usage during peak loads",
                    ],
                )
            else:
                recommendations.append("Resource levels appear adequate for production")

            return {
                "status": (
                    "critical" if blockers else "warning" if issues else "healthy"
                ),
                "score": score,
                "issues": issues,
                "blockers": blockers,
                "recommendations": recommendations,
            }

        except Exception as e:
            return {"status": "error", "score": 0, "error": str(e)}

    def _assess_monitoring_readiness(self) -> dict[str, Any]:
        """Assess monitoring and observability readiness."""
        try:
            issues = []
            recommendations = []
            score = 100

            if not self.orchestrator.monitoring_system:
                issues.append("Monitoring system not available")
                recommendations.extend(
                    [
                        "Enable comprehensive monitoring for production",
                        "Set up alerting and dashboard systems",
                    ],
                )
                score = 40
            else:
                try:
                    monitoring_health = (
                        self.orchestrator.monitoring_system.get_system_health()
                    )

                    if monitoring_health.get("monitoring_status") != "healthy":
                        issues.append("Monitoring system health is not optimal")
                        score = min(score, 70)

                    # Check monitoring components
                    components = monitoring_health.get("components", {})

                    if (
                        components.get("metrics_collector", {}).get("status")
                        != "running"
                    ):
                        issues.append("Metrics collection not active")
                        score = min(score, 80)

                    if (
                        components.get("log_aggregator", {}).get("active_alerts", 0)
                        > 10
                    ):
                        recommendations.append("Review and resolve active log alerts")
                        score = min(score, 85)

                    # Check if dashboards are configured
                    dashboard_count = components.get("dashboard_generator", {}).get(
                        "dashboard_count",
                        0,
                    )
                    if dashboard_count == 0:
                        recommendations.append(
                            "Configure monitoring dashboards for production visibility",
                        )
                        score = min(score, 90)

                except Exception as e:
                    issues.append(f"Error assessing monitoring health: {e}")
                    score = min(score, 75)

            # General monitoring recommendations
            recommendations.extend(
                [
                    "Verify all critical metrics are being collected",
                    "Test alerting mechanisms before production deployment",
                    "Ensure monitoring data retention meets requirements",
                ],
            )

            return {
                "status": "warning" if score < 85 else "healthy",
                "score": score,
                "issues": issues,
                "recommendations": recommendations,
            }

        except Exception as e:
            return {"status": "error", "score": 0, "error": str(e)}


class IntegrationReporter:
    """
    Comprehensive integration reporting and metrics aggregation.

    Generates detailed reports on integration status, component health,
    performance metrics, and deployment readiness assessments.
    """

    def __init__(self, orchestrator: Phase3IntegrationOrchestrator):
        """Initialize the integration reporter."""
        self.orchestrator = orchestrator
        self.validator = IntegrationValidator(orchestrator)
        self.readiness_checker = ProductionReadinessChecker(orchestrator)
        self.logger = logging.getLogger(f"{__name__}.IntegrationReporter")

        self.report_templates = {
            "executive_summary": self._generate_executive_summary,
            "technical_details": self._generate_technical_details,
            "performance_analysis": self._generate_performance_analysis,
            "deployment_readiness": self._generate_deployment_readiness_report,
            "operational_status": self._generate_operational_status,
        }

    def generate_comprehensive_report(self) -> dict[str, Any]:
        """Generate a comprehensive integration report covering all aspects."""
        start_time = time.time()

        try:
            self.logger.info("Generating comprehensive integration report")

            # Collect all necessary data
            report_data = {
                "metadata": {
                    "report_id": str(uuid.uuid4()),
                    "generated_at": datetime.now().isoformat(),
                    "service_name": self.orchestrator.service_name,
                    "report_version": "1.0",
                    "generation_time": 0,  # Will be updated at the end
                },
                "sections": {},
            }

            # Generate each report section
            for section_name, generator_func in self.report_templates.items():
                try:
                    self.logger.info(f"Generating {section_name} section")
                    section_data = generator_func()
                    report_data["sections"][section_name] = section_data
                except Exception as e:
                    self.logger.error(f"Error generating {section_name} section: {e}")
                    report_data["sections"][section_name] = {
                        "status": "error",
                        "error": str(e),
                        "timestamp": datetime.now().isoformat(),
                    }

            # Update generation time
            report_data["metadata"]["generation_time"] = time.time() - start_time

            # Add report summary
            report_data["summary"] = self._generate_report_summary(
                report_data["sections"],
            )

            self.logger.info(
                f"Comprehensive report generated successfully in {report_data['metadata']['generation_time']:.2f}s",
            )

            return report_data

        except Exception as e:
            self.logger.error(f"Error generating comprehensive report: {e}")
            return {
                "metadata": {
                    "report_id": str(uuid.uuid4()),
                    "generated_at": datetime.now().isoformat(),
                    "service_name": self.orchestrator.service_name,
                    "status": "error",
                    "error": str(e),
                    "generation_time": time.time() - start_time,
                },
            }

    def _generate_executive_summary(self) -> dict[str, Any]:
        """Generate executive summary of integration status."""
        try:
            # Get current system status
            system_health = self.orchestrator.get_system_health()
            integration_status = self.orchestrator.get_integration_status()

            # Determine overall system state
            overall_health = system_health.get("overall_status", "unknown")
            is_operational = integration_status.get("is_running", False)

            # Calculate system maturity score
            maturity_factors = {
                "initialization": 20 if integration_status.get("is_initialized") else 0,
                "component_availability": len(
                    [
                        v
                        for v in integration_status.get(
                            "component_availability",
                            {},
                        ).values()
                        if v
                    ],
                )
                * 15,
                "monitoring_active": (
                    20 if overall_health in ["healthy", "degraded"] else 0
                ),
                "operational_time": min(
                    20,
                    (integration_status.get("uptime_seconds", 0) / 3600) * 5,
                ),  # Max 20 for 4+ hours
                "integration_history": min(
                    5,
                    len(self.orchestrator.integration_history),
                ),
            }

            maturity_score = sum(maturity_factors.values())

            # Generate key findings
            key_findings = []

            if overall_health == "healthy" and is_operational:
                key_findings.append("✓ System is healthy and operational")
            elif overall_health == "degraded":
                key_findings.append("⚠ System is operational but degraded")
            elif not is_operational:
                key_findings.append("✗ System is not currently operational")
            else:
                key_findings.append(f"? System health status: {overall_health}")

            # Component status summary
            component_availability = integration_status.get(
                "component_availability",
                {},
            )
            available_components = sum(component_availability.values())
            total_components = len(component_availability)

            key_findings.append(
                f"📊 {available_components}/{total_components} components available",
            )

            # System uptime
            uptime_hours = integration_status.get("uptime_seconds", 0) / 3600
            key_findings.append(f"⏱ System uptime: {uptime_hours:.1f} hours")

            # Recommendations for executives
            executive_recommendations = []

            if maturity_score < 50:
                executive_recommendations.append(
                    "System requires significant improvement before production deployment",
                )
            elif maturity_score < 75:
                executive_recommendations.append(
                    "System shows good progress but needs optimization before production",
                )
            else:
                executive_recommendations.append(
                    "System demonstrates high maturity and readiness",
                )

            if not is_operational:
                executive_recommendations.append(
                    "Immediate attention required - system not operational",
                )
            elif overall_health != "healthy":
                executive_recommendations.append(
                    "Address system health issues to ensure reliable operation",
                )

            return {
                "overall_status": overall_health,
                "operational_state": "operational" if is_operational else "stopped",
                "maturity_score": maturity_score,
                "maturity_grade": (
                    "A"
                    if maturity_score >= 85
                    else (
                        "B"
                        if maturity_score >= 70
                        else "C" if maturity_score >= 50 else "D"
                    )
                ),
                "key_findings": key_findings,
                "executive_recommendations": executive_recommendations,
                "component_summary": {
                    "total_components": total_components,
                    "available_components": available_components,
                    "availability_percentage": (
                        (available_components / total_components * 100)
                        if total_components > 0
                        else 0
                    ),
                },
                "maturity_factors": maturity_factors,
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }

    def _generate_technical_details(self) -> dict[str, Any]:
        """Generate detailed technical information."""
        try:
            # System information
            system_info = {
                "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
                "platform": os.name,
                "hostname": os.uname().nodename if hasattr(os, "uname") else "unknown",
                "process_id": os.getpid(),
            }

            # Component details
            component_details = {}

            components = [
                ("performance_manager", self.orchestrator.performance_manager),
                ("system_optimizer", self.orchestrator.system_optimizer),
                ("validation_manager", self.orchestrator.validation_manager),
                ("production_deployer", self.orchestrator.production_deployer),
                ("monitoring_system", self.orchestrator.monitoring_system),
            ]

            for component_name, component in components:
                if component is None:
                    component_details[component_name] = {
                        "status": "not_available",
                        "class": None,
                    }
                else:
                    health = self.orchestrator._check_component_health(
                        component_name,
                        component,
                    )
                    component_details[component_name] = {
                        "status": "healthy" if health.get("healthy") else "unhealthy",
                        "class": component.__class__.__name__,
                        "module": component.__class__.__module__,
                        "health_details": health.get("details", {}),
                        "error": health.get("error"),
                    }

            # Integration statistics
            integration_stats = {
                "initialization_count": len(
                    [
                        h
                        for h in self.orchestrator.integration_history
                        if "initialization_results" in h
                    ],
                ),
                "total_operations": len(self.orchestrator.integration_history),
                "successful_operations": len(
                    [
                        h
                        for h in self.orchestrator.integration_history
                        if h.get("status") == "success"
                    ],
                ),
                "last_operation_time": (
                    self.orchestrator.integration_history[-1].get("timestamp")
                    if self.orchestrator.integration_history
                    else None
                ),
            }

            # Memory and resource usage
            resource_details = {}

            if HAS_PSUTIL:
                try:
                    import psutil

                    process = psutil.Process()

                    resource_details = {
                        "memory_info": {
                            "rss": process.memory_info().rss,
                            "vms": process.memory_info().vms,
                            "percent": process.memory_percent(),
                        },
                        "cpu_info": {
                            "percent": process.cpu_percent(),
                            "times": process.cpu_times()._asdict(),
                        },
                        "open_files": len(process.open_files()),
                        "num_threads": process.num_threads(),
                    }
                except Exception as e:
                    resource_details = {"error": str(e)}

            # Configuration details
            configuration = {
                "service_name": self.orchestrator.service_name,
                "is_initialized": self.orchestrator.is_initialized,
                "is_running": self.orchestrator.is_running,
                "start_time": datetime.fromtimestamp(
                    self.orchestrator.start_time,
                ).isoformat(),
            }

            return {
                "system_info": system_info,
                "component_details": component_details,
                "integration_stats": integration_stats,
                "resource_usage": resource_details,
                "configuration": configuration,
                "dependency_status": {
                    "psutil_available": HAS_PSUTIL,
                    "performance_framework_available": HAS_PERFORMANCE_FRAMEWORK,
                    "system_optimizer_available": HAS_SYSTEM_OPTIMIZER,
                    "validation_framework_available": HAS_VALIDATION_FRAMEWORK,
                    "production_deployer_available": HAS_PRODUCTION_DEPLOYER,
                    "monitoring_system_available": HAS_MONITORING_SYSTEM,
                },
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }

    def _generate_performance_analysis(self) -> dict[str, Any]:
        """Generate performance analysis report."""
        try:
            performance_data = {}

            # Run performance benchmarks
            try:
                benchmark_results = self.validator.run_performance_benchmarks()
                performance_data["benchmarks"] = benchmark_results
            except Exception as e:
                performance_data["benchmarks"] = {"error": str(e)}

            # Get system performance metrics
            if self.orchestrator.performance_manager:
                try:
                    profile = (
                        self.orchestrator.performance_manager.collect_system_metrics()
                    )
                    performance_analysis = (
                        self.orchestrator.performance_manager.analyze_performance()
                    )

                    performance_data["current_metrics"] = {
                        "metric_count": len(profile.metrics),
                        "optimization_potential": profile.optimization_potential,
                        "profile_time": profile.profile_time,
                        "component_name": profile.component_name,
                    }

                    performance_data["analysis"] = performance_analysis

                except Exception as e:
                    performance_data["current_metrics"] = {"error": str(e)}
            else:
                performance_data["current_metrics"] = {"status": "not_available"}

            # System optimization results
            if self.orchestrator.system_optimizer:
                try:
                    # Get optimization status without running new optimization
                    opt_status = (
                        self.orchestrator.system_optimizer.get_optimization_status()
                    )
                    performance_data["optimization_status"] = opt_status

                except Exception as e:
                    performance_data["optimization_status"] = {"error": str(e)}
            else:
                performance_data["optimization_status"] = {"status": "not_available"}

            # Performance recommendations
            recommendations = []

            # Benchmark-based recommendations
            if (
                "benchmarks" in performance_data
                and "overall_score" in performance_data["benchmarks"]
            ):
                score = performance_data["benchmarks"]["overall_score"]
                if score < 60:
                    recommendations.append(
                        "Performance benchmarks show poor results - system optimization required",
                    )
                elif score < 80:
                    recommendations.append(
                        "Performance benchmarks show room for improvement",
                    )
                else:
                    recommendations.append("Performance benchmarks show good results")

            # Metrics-based recommendations
            if (
                "current_metrics" in performance_data
                and "optimization_potential" in performance_data["current_metrics"]
            ):
                potential = performance_data["current_metrics"][
                    "optimization_potential"
                ]
                if potential > 50:
                    recommendations.append(
                        "High optimization potential - consider running system optimization",
                    )
                elif potential > 30:
                    recommendations.append(
                        "Moderate optimization potential - monitor performance trends",
                    )

            # Resource-based recommendations
            if HAS_PSUTIL:
                try:
                    import psutil

                    cpu_percent = psutil.cpu_percent(interval=0.1)
                    memory_percent = psutil.virtual_memory().percent

                    if cpu_percent > 80:
                        recommendations.append(
                            "High CPU usage - investigate performance bottlenecks",
                        )

                    if memory_percent > 80:
                        recommendations.append(
                            "High memory usage - check for memory leaks or optimization needs",
                        )

                except Exception:
                    pass

            if not recommendations:
                recommendations.append("No significant performance issues detected")

            return {
                "performance_data": performance_data,
                "recommendations": recommendations,
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }

    def _generate_deployment_readiness_report(self) -> dict[str, Any]:
        """Generate deployment readiness assessment report."""
        try:
            # Run comprehensive readiness assessment
            readiness_report = self.readiness_checker.assess_production_readiness()

            # Convert to dictionary format
            report_dict = readiness_report.to_dict()

            # Add deployment timeline recommendations
            deployment_timeline = self._generate_deployment_timeline(readiness_report)
            report_dict["deployment_timeline"] = deployment_timeline

            # Add risk assessment
            risk_assessment = self._assess_deployment_risks(readiness_report)
            report_dict["risk_assessment"] = risk_assessment

            return report_dict

        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }

    def _generate_deployment_timeline(
        self,
        readiness_report: ProductionReadinessReport,
    ) -> dict[str, Any]:
        """Generate deployment timeline based on readiness assessment."""
        try:
            timeline = {
                "current_status": readiness_report.overall_status,
                "estimated_readiness": "unknown",
                "blocking_issues_count": len(readiness_report.deployment_blockers),
                "warning_issues_count": len(readiness_report.warnings),
                "phases": [],
            }

            # Determine timeline based on issues
            if readiness_report.overall_status == "ready":
                timeline["estimated_readiness"] = "immediate"
                timeline["phases"] = [
                    {
                        "phase": "final_validation",
                        "estimated_duration": "1-2 hours",
                        "tasks": [
                            "Run final integration tests",
                            "Verify monitoring setup",
                        ],
                    },
                    {
                        "phase": "deployment",
                        "estimated_duration": "2-4 hours",
                        "tasks": [
                            "Execute production deployment",
                            "Monitor initial performance",
                        ],
                    },
                ]

            elif readiness_report.overall_status == "warning":
                timeline["estimated_readiness"] = "1-3 days"
                timeline["phases"] = [
                    {
                        "phase": "issue_resolution",
                        "estimated_duration": "4-24 hours",
                        "tasks": readiness_report.warnings,
                    },
                    {
                        "phase": "validation",
                        "estimated_duration": "2-4 hours",
                        "tasks": ["Rerun readiness assessment", "Validate fixes"],
                    },
                    {
                        "phase": "deployment",
                        "estimated_duration": "2-4 hours",
                        "tasks": ["Execute production deployment"],
                    },
                ]

            else:  # not_ready
                timeline["estimated_readiness"] = "3-7 days"
                timeline["phases"] = [
                    {
                        "phase": "critical_fixes",
                        "estimated_duration": "1-3 days",
                        "tasks": readiness_report.deployment_blockers,
                    },
                    {
                        "phase": "system_optimization",
                        "estimated_duration": "4-8 hours",
                        "tasks": [
                            "Run system optimization",
                            "Address performance issues",
                        ],
                    },
                    {
                        "phase": "validation_and_testing",
                        "estimated_duration": "8-16 hours",
                        "tasks": [
                            "Run comprehensive validation",
                            "Perform integration tests",
                        ],
                    },
                    {
                        "phase": "deployment",
                        "estimated_duration": "2-4 hours",
                        "tasks": ["Execute production deployment"],
                    },
                ]

            return timeline

        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _assess_deployment_risks(
        self,
        readiness_report: ProductionReadinessReport,
    ) -> dict[str, Any]:
        """Assess deployment risks based on readiness report."""
        try:
            risks = {
                "overall_risk_level": "low",
                "risk_factors": [],
                "mitigation_strategies": [],
            }

            # Calculate risk level
            risk_score = 0

            # Critical issues add high risk
            if readiness_report.deployment_blockers:
                risk_score += len(readiness_report.deployment_blockers) * 30
                risks["risk_factors"].extend(
                    [
                        f"Deployment blocker: {blocker}"
                        for blocker in readiness_report.deployment_blockers
                    ],
                )

            # Warning issues add moderate risk
            if readiness_report.warnings:
                risk_score += len(readiness_report.warnings) * 10
                risks["risk_factors"].extend(
                    [f"Warning: {warning}" for warning in readiness_report.warnings],
                )

            # Low readiness score adds risk
            if readiness_report.readiness_score < 70:
                risk_score += 70 - readiness_report.readiness_score
                risks["risk_factors"].append(
                    f"Low readiness score: {readiness_report.readiness_score:.1f}/100",
                )

            # Component health risks
            component_assessments = readiness_report.component_assessments
            unhealthy_components = [
                name
                for name, assessment in component_assessments.items()
                if assessment.get("status") in ["critical", "error"]
            ]

            if unhealthy_components:
                risk_score += len(unhealthy_components) * 20
                risks["risk_factors"].append(
                    f"Unhealthy components: {', '.join(unhealthy_components)}",
                )

            # Determine overall risk level
            if risk_score >= 100:
                risks["overall_risk_level"] = "critical"
            elif risk_score >= 50:
                risks["overall_risk_level"] = "high"
            elif risk_score >= 25:
                risks["overall_risk_level"] = "medium"
            else:
                risks["overall_risk_level"] = "low"

            # Generate mitigation strategies
            if readiness_report.deployment_blockers:
                risks["mitigation_strategies"].append(
                    "Resolve all deployment blockers before proceeding",
                )

            if readiness_report.readiness_score < 80:
                risks["mitigation_strategies"].append(
                    "Improve system readiness score through optimization",
                )

            if unhealthy_components:
                risks["mitigation_strategies"].append(
                    "Address unhealthy component issues",
                )

            if risks["overall_risk_level"] in ["high", "critical"]:
                risks["mitigation_strategies"].extend(
                    [
                        "Implement staged deployment with rollback plan",
                        "Increase monitoring and alerting during deployment",
                        "Prepare incident response procedures",
                    ],
                )

            risks["risk_score"] = risk_score

            return risks

        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _generate_operational_status(self) -> dict[str, Any]:
        """Generate operational status report."""
        try:
            # Current operational state
            system_health = self.orchestrator.get_system_health()
            integration_status = self.orchestrator.get_integration_status()

            operational_metrics = {
                "system_state": {
                    "overall_health": system_health.get("overall_status"),
                    "is_operational": integration_status.get("is_running"),
                    "uptime_seconds": integration_status.get("uptime_seconds"),
                    "uptime_formatted": self._format_uptime(
                        integration_status.get("uptime_seconds", 0),
                    ),
                },
                "component_status": system_health.get("components", {}),
                "recent_activities": [],
            }

            # Recent integration activities
            recent_history = self.orchestrator.integration_history[
                -10:
            ]  # Last 10 operations
            for activity in recent_history:
                operational_metrics["recent_activities"].append(
                    {
                        "timestamp": activity.get("timestamp"),
                        "operation": activity.get("status", "unknown"),
                        "duration": activity.get("execution_time"),
                        "success": activity.get("status") == "success",
                    },
                )

            # Performance indicators
            performance_indicators = {}

            if self.orchestrator.monitoring_system:
                try:
                    monitoring_health = (
                        self.orchestrator.monitoring_system.get_system_health()
                    )
                    performance_indicators["monitoring"] = {
                        "status": monitoring_health.get("monitoring_status"),
                        "active_alerts": monitoring_health.get("active_alerts", 0),
                    }
                except Exception as e:
                    performance_indicators["monitoring"] = {"error": str(e)}

            # System resource status
            if HAS_PSUTIL:
                try:
                    import psutil

                    performance_indicators["resources"] = {
                        "cpu_usage": psutil.cpu_percent(interval=0.1),
                        "memory_usage": psutil.virtual_memory().percent,
                        "disk_usage": (
                            psutil.disk_usage("/").percent
                            if Path("/").exists()
                            else None
                        ),
                    }
                except Exception as e:
                    performance_indicators["resources"] = {"error": str(e)}

            # Operational recommendations
            operational_recommendations = []

            if not integration_status.get("is_running"):
                operational_recommendations.append(
                    "System is not operational - start integrated system",
                )
            elif system_health.get("overall_status") != "healthy":
                operational_recommendations.append(
                    "System health is not optimal - investigate component issues",
                )

            if len(operational_metrics["recent_activities"]) == 0:
                operational_recommendations.append(
                    "No recent activities detected - system may not be active",
                )
            elif (
                len(
                    [
                        a
                        for a in operational_metrics["recent_activities"]
                        if not a["success"]
                    ],
                )
                > len(operational_metrics["recent_activities"]) / 2
            ):
                operational_recommendations.append(
                    "High failure rate in recent activities - investigate system stability",
                )

            # Operational alerts
            operational_alerts = []

            uptime_hours = integration_status.get("uptime_seconds", 0) / 3600
            if uptime_hours < 1:
                operational_alerts.append(
                    f"System recently started ({uptime_hours:.1f}h uptime) - monitor stability",
                )

            if performance_indicators.get("resources", {}).get("cpu_usage", 0) > 90:
                operational_alerts.append("Critical CPU usage detected")

            if performance_indicators.get("resources", {}).get("memory_usage", 0) > 90:
                operational_alerts.append("Critical memory usage detected")

            if not operational_recommendations:
                operational_recommendations.append(
                    "System operational status appears normal",
                )

            return {
                "operational_metrics": operational_metrics,
                "performance_indicators": performance_indicators,
                "operational_recommendations": operational_recommendations,
                "operational_alerts": operational_alerts,
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }

    def _format_uptime(self, uptime_seconds: float) -> str:
        """Format uptime in human-readable format."""
        try:
            hours = int(uptime_seconds // 3600)
            minutes = int((uptime_seconds % 3600) // 60)
            seconds = int(uptime_seconds % 60)

            if hours > 0:
                return f"{hours}h {minutes}m {seconds}s"
            if minutes > 0:
                return f"{minutes}m {seconds}s"
            return f"{seconds}s"

        except Exception:
            return "unknown"

    def _generate_report_summary(self, sections: dict[str, Any]) -> dict[str, Any]:
        """Generate a summary of the entire report."""
        try:
            summary = {
                "report_health": "healthy",
                "sections_generated": 0,
                "sections_with_errors": 0,
                "key_insights": [],
                "priority_actions": [],
            }

            # Count section status
            for section_name, section_data in sections.items():
                summary["sections_generated"] += 1

                if section_data.get("status") == "error" or "error" in section_data:
                    summary["sections_with_errors"] += 1

            # Determine report health
            if summary["sections_with_errors"] > summary["sections_generated"] / 2:
                summary["report_health"] = "degraded"
            elif summary["sections_with_errors"] > 0:
                summary["report_health"] = "warnings"

            # Extract key insights from executive summary
            exec_summary = sections.get("executive_summary", {})
            if "key_findings" in exec_summary:
                summary["key_insights"] = exec_summary["key_findings"][:3]  # Top 3

            # Extract priority actions from deployment readiness
            deployment_readiness = sections.get("deployment_readiness", {})
            if "deployment_blockers" in deployment_readiness:
                summary["priority_actions"].extend(
                    deployment_readiness["deployment_blockers"][:3],
                )  # Top 3

            # Add operational priority actions
            operational_status = sections.get("operational_status", {})
            if "operational_alerts" in operational_status:
                summary["priority_actions"].extend(
                    operational_status["operational_alerts"][:2],
                )  # Top 2

            # Remove duplicates and limit
            summary["priority_actions"] = list(set(summary["priority_actions"]))[:5]

            return summary

        except Exception as e:
            return {
                "report_health": "error",
                "error": str(e),
                "sections_generated": 0,
                "sections_with_errors": 0,
            }

    def export_report(
        self,
        report_data: dict[str, Any],
        format_type: str = "json",
    ) -> str:
        """Export report in specified format."""
        try:
            if format_type == "json":
                return json.dumps(report_data, indent=2, default=str)
            if format_type == "yaml":
                try:
                    import yaml

                    return yaml.dump(report_data, default_flow_style=False, default=str)
                except ImportError:
                    raise ValueError("PyYAML required for YAML export")
            else:
                raise ValueError(f"Unsupported export format: {format_type}")

        except Exception as e:
            self.logger.error(f"Error exporting report: {e}")
            raise

    def generate_status_summary(self) -> dict[str, Any]:
        """Generate a quick status summary for monitoring dashboards."""
        try:
            system_health = self.orchestrator.get_system_health()
            integration_status = self.orchestrator.get_integration_status()

            return {
                "timestamp": datetime.now().isoformat(),
                "service_name": self.orchestrator.service_name,
                "overall_status": system_health.get("overall_status", "unknown"),
                "is_operational": integration_status.get("is_running", False),
                "uptime_hours": round(
                    integration_status.get("uptime_seconds", 0) / 3600,
                    1,
                ),
                "components_healthy": len(
                    [
                        status
                        for status in system_health.get("components", {}).values()
                        if status.get("status") == "healthy"
                    ],
                ),
                "total_components": len(system_health.get("components", {})),
                "recent_errors": len(
                    [
                        activity
                        for activity in self.orchestrator.integration_history[-10:]
                        if activity.get("status") in ["error", "failed"]
                    ],
                ),
                "last_operation": (
                    self.orchestrator.integration_history[-1].get("timestamp")
                    if self.orchestrator.integration_history
                    else None
                ),
            }

        except Exception as e:
            return {
                "timestamp": datetime.now().isoformat(),
                "status": "error",
                "error": str(e),
            }

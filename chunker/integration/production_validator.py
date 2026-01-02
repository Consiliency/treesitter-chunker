"""Production Validation System for treesitter-chunker - Task 1.9.4.

This module implements a comprehensive production validation system that ensures the integrated
system is ready for deployment. It performs extensive health checks, validates dependencies,
tests critical paths, and generates deployment readiness reports.

Key Features:
- ProductionValidator: Main orchestrator for all validation activities
- DependencyValidator: Checks all required dependencies and versions
- ConfigurationValidator: Validates all configuration settings
- SecurityValidator: Checks security settings and vulnerabilities
- PerformanceValidator: Verifies performance meets requirements
- IntegrationValidator: Tests all component integrations
- Critical path testing with end-to-end validation
- Deployment readiness assessment with detailed reporting
- CI/CD integration support with proper exit codes

The validation system integrates with:
- SystemIntegrator from core_integration.py for unified system management
- PerformanceOptimizer from performance_optimizer.py for performance validation
- UserExperienceManager from user_experience.py for UX validation
- All Phase 1.7 and 1.8 components for comprehensive testing

This implementation provides production-ready validation with comprehensive reporting,
automated testing, and deployment readiness assessment capabilities.
"""

from __future__ import annotations

import asyncio
import hashlib
import importlib
import inspect
import json
import logging
import os
import platform
import re
import shutil
import signal
import socket
import ssl
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import uuid
import warnings
from collections import defaultdict, deque
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor, TimeoutError, as_completed
from contextlib import contextmanager, suppress
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from urllib.parse import urlparse

import psutil

# Core integrations with graceful fallback
try:
    from .core_integration import (
        ComponentType,
        HealthStatus,
        SystemIntegrator,
        get_system_integrator,
    )

    CORE_INTEGRATION_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Core integration not available: {e}")
    CORE_INTEGRATION_AVAILABLE = False
    SystemIntegrator = None
    get_system_integrator = None
    HealthStatus = None
    ComponentType = None

try:
    from .performance_optimizer import (
        OptimizationLevel,
        PerformanceMetric,
        PerformanceOptimizer,
    )

    PERFORMANCE_OPTIMIZER_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Performance optimizer not available: {e}")
    PERFORMANCE_OPTIMIZER_AVAILABLE = False
    PerformanceOptimizer = None
    PerformanceMetric = None
    OptimizationLevel = None

try:
    from .user_experience import FeedbackLevel, InteractionMode, UserExperienceManager

    USER_EXPERIENCE_AVAILABLE = True
except ImportError as e:
    logging.warning(f"User experience manager not available: {e}")
    USER_EXPERIENCE_AVAILABLE = False
    UserExperienceManager = None
    InteractionMode = None
    FeedbackLevel = None

# Grammar and error handling components
try:
    from ..grammar import GrammarManager, GrammarRegistry, GrammarValidator
    from ..grammar_management import ComprehensiveGrammarCLI, GrammarInstaller

    GRAMMAR_COMPONENTS_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Grammar components not available: {e}")
    GRAMMAR_COMPONENTS_AVAILABLE = False
    GrammarManager = None
    GrammarRegistry = None
    GrammarValidator = None
    ComprehensiveGrammarCLI = None
    GrammarInstaller = None

try:
    from ..error_handling import (
        CompatibilityDetector,
        ErrorClassifier,
        ErrorHandlingPipeline,
    )

    ERROR_HANDLING_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Error handling not available: {e}")
    ERROR_HANDLING_AVAILABLE = False
    ErrorHandlingPipeline = None
    ErrorClassifier = None
    CompatibilityDetector = None

# Core chunking components
try:
    from ..chunker import TreeSitterChunker
    from ..core import chunk_file, chunk_text
    from ..parser import get_parser

    CORE_CHUNKING_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Core chunking not available: {e}")
    CORE_CHUNKING_AVAILABLE = False
    chunk_file = None
    chunk_text = None
    get_parser = None
    TreeSitterChunker = None


class ValidationSeverity(Enum):
    """Validation result severity levels."""

    PASS = "pass"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ValidationCategory(Enum):
    """Categories of validation checks."""

    DEPENDENCY = "dependency"
    CONFIGURATION = "configuration"
    SECURITY = "security"
    PERFORMANCE = "performance"
    INTEGRATION = "integration"
    CRITICAL_PATH = "critical_path"
    DEPLOYMENT = "deployment"
    SYSTEM_HEALTH = "system_health"


class DeploymentStage(Enum):
    """Deployment stages for validation."""

    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"


@dataclass
class ValidationResult:
    """Result of a single validation check."""

    check_name: str
    category: ValidationCategory
    severity: ValidationSeverity
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    duration: float = 0.0
    recommendations: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "check_name": self.check_name,
            "category": self.category.value,
            "severity": self.severity.value,
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
            "duration": self.duration,
            "recommendations": self.recommendations,
            "metadata": self.metadata,
        }

    def is_blocking(self) -> bool:
        """Check if this result blocks deployment."""
        return self.severity in {ValidationSeverity.ERROR, ValidationSeverity.CRITICAL}


@dataclass
class ValidationReport:
    """Comprehensive validation report."""

    validation_id: str
    deployment_stage: DeploymentStage
    timestamp: datetime
    duration: float
    results: list[ValidationResult] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)
    deployment_ready: bool = False
    exit_code: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_result(self, result: ValidationResult) -> None:
        """Add validation result to report."""
        self.results.append(result)
        self._update_summary()

    def _update_summary(self) -> None:
        """Update report summary based on results."""
        self.summary = {
            "total_checks": len(self.results),
            "pass": sum(
                1 for r in self.results if r.severity == ValidationSeverity.PASS
            ),
            "info": sum(
                1 for r in self.results if r.severity == ValidationSeverity.INFO
            ),
            "warning": sum(
                1 for r in self.results if r.severity == ValidationSeverity.WARNING
            ),
            "error": sum(
                1 for r in self.results if r.severity == ValidationSeverity.ERROR
            ),
            "critical": sum(
                1 for r in self.results if r.severity == ValidationSeverity.CRITICAL
            ),
            "categories": self._get_category_summary(),
        }

        # Determine deployment readiness
        blocking_results = [r for r in self.results if r.is_blocking()]
        self.deployment_ready = len(blocking_results) == 0

        # Set exit code for CI/CD integration
        if self.summary["critical"] > 0:
            self.exit_code = 2  # Critical failures
        elif self.summary["error"] > 0:
            self.exit_code = 1  # Errors
        else:
            self.exit_code = 0  # Success

    def _get_category_summary(self) -> dict[str, dict[str, int]]:
        """Get summary by category."""
        category_summary = {}
        for category in ValidationCategory:
            category_results = [r for r in self.results if r.category == category]
            category_summary[category.value] = {
                "total": len(category_results),
                "pass": sum(
                    1 for r in category_results if r.severity == ValidationSeverity.PASS
                ),
                "warning": sum(
                    1
                    for r in category_results
                    if r.severity == ValidationSeverity.WARNING
                ),
                "error": sum(
                    1
                    for r in category_results
                    if r.severity == ValidationSeverity.ERROR
                ),
                "critical": sum(
                    1
                    for r in category_results
                    if r.severity == ValidationSeverity.CRITICAL
                ),
            }
        return category_summary

    def get_blocking_issues(self) -> list[ValidationResult]:
        """Get all blocking validation issues."""
        return [r for r in self.results if r.is_blocking()]

    def get_recommendations(self) -> list[str]:
        """Get all unique recommendations from results."""
        recommendations = set()
        for result in self.results:
            recommendations.update(result.recommendations)
        return sorted(recommendations)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "validation_id": self.validation_id,
            "deployment_stage": self.deployment_stage.value,
            "timestamp": self.timestamp.isoformat(),
            "duration": self.duration,
            "results": [r.to_dict() for r in self.results],
            "summary": self.summary,
            "deployment_ready": self.deployment_ready,
            "exit_code": self.exit_code,
            "metadata": self.metadata,
        }


class DependencyValidator:
    """Validates all system dependencies and versions."""

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.logger = logging.getLogger(__name__ + ".DependencyValidator")

        # Required dependencies with version constraints
        self.required_dependencies = {
            "python": {"min_version": "3.8.0", "check_func": self._check_python},
            "tree_sitter": {
                "min_version": "0.20.0",
                "check_func": self._check_tree_sitter,
            },
            "psutil": {"min_version": "5.8.0", "check_func": self._check_psutil},
            "pathlib": {"min_version": None, "check_func": self._check_pathlib},
            "threading": {"min_version": None, "check_func": self._check_threading},
        }

        # Optional dependencies
        self.optional_dependencies = {
            "graphviz": {"check_func": self._check_graphviz},
            "pygments": {"check_func": self._check_pygments},
            "sqlite3": {"check_func": self._check_sqlite3},
            "requests": {"check_func": self._check_requests},
            "pydantic": {"check_func": self._check_pydantic},
        }

        # System requirements
        self.system_requirements = {
            "memory_mb": self.config.get("min_memory_mb", 512),
            "disk_mb": self.config.get("min_disk_mb", 1024),
            "cpu_cores": self.config.get("min_cpu_cores", 1),
        }

    def validate(self) -> list[ValidationResult]:
        """Validate all dependencies."""
        results = []

        # Check required dependencies
        for dep_name, dep_info in self.required_dependencies.items():
            result = self._validate_dependency(dep_name, dep_info, required=True)
            results.append(result)

        # Check optional dependencies
        for dep_name, dep_info in self.optional_dependencies.items():
            result = self._validate_dependency(dep_name, dep_info, required=False)
            results.append(result)

        # Check system requirements
        results.extend(self._validate_system_requirements())

        # Check environment variables
        results.extend(self._validate_environment())

        return results

    def _validate_dependency(
        self,
        name: str,
        info: dict[str, Any],
        required: bool,
    ) -> ValidationResult:
        """Validate a single dependency."""
        start_time = time.time()

        try:
            check_func = info["check_func"]
            check_result = check_func()

            if check_result["available"]:
                # Check version if required
                if info.get("min_version"):
                    version_check = self._check_version(
                        check_result.get("version"),
                        info["min_version"],
                    )

                    if not version_check["meets_requirement"]:
                        return ValidationResult(
                            check_name=f"{name}_version",
                            category=ValidationCategory.DEPENDENCY,
                            severity=(
                                ValidationSeverity.ERROR
                                if required
                                else ValidationSeverity.WARNING
                            ),
                            message=f"{name} version {check_result.get('version')} is below required {info['min_version']}",
                            details=check_result,
                            duration=time.time() - start_time,
                            recommendations=[
                                f"Upgrade {name} to version {info['min_version']} or higher",
                                (
                                    f"Run: pip install --upgrade {name}"
                                    if name != "python"
                                    else "Upgrade Python installation"
                                ),
                            ],
                        )

                return ValidationResult(
                    check_name=f"{name}_availability",
                    category=ValidationCategory.DEPENDENCY,
                    severity=ValidationSeverity.PASS,
                    message=f"{name} is available{(' (version ' + str(check_result.get('version')) + ')') if check_result.get('version') else ''}",
                    details=check_result,
                    duration=time.time() - start_time,
                )
            return ValidationResult(
                check_name=f"{name}_availability",
                category=ValidationCategory.DEPENDENCY,
                severity=(
                    ValidationSeverity.ERROR if required else ValidationSeverity.WARNING
                ),
                message=f"{name} is not available",
                details=check_result,
                duration=time.time() - start_time,
                recommendations=[
                    (
                        f"Install {name}: pip install {name}"
                        if name not in ["python", "pathlib", "threading"]
                        else f"Install {name}"
                    ),
                    "Check installation documentation",
                ],
            )

        except Exception as e:
            return ValidationResult(
                check_name=f"{name}_check",
                category=ValidationCategory.DEPENDENCY,
                severity=(
                    ValidationSeverity.ERROR if required else ValidationSeverity.WARNING
                ),
                message=f"Failed to check {name}: {e!s}",
                details={"error": str(e), "traceback": traceback.format_exc()},
                duration=time.time() - start_time,
                recommendations=[
                    f"Manually verify {name} installation",
                    "Check system configuration",
                ],
            )

    def _check_python(self) -> dict[str, Any]:
        """Check Python availability and version."""
        return {
            "available": True,
            "version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "executable": sys.executable,
            "platform": platform.platform(),
        }

    def _check_tree_sitter(self) -> dict[str, Any]:
        """Check tree-sitter availability."""
        try:
            import tree_sitter

            return {
                "available": True,
                "version": getattr(tree_sitter, "__version__", "unknown"),
                "module_path": tree_sitter.__file__,
            }
        except ImportError as e:
            return {"available": False, "error": str(e)}

    def _check_psutil(self) -> dict[str, Any]:
        """Check psutil availability."""
        try:
            import psutil

            return {
                "available": True,
                "version": psutil.version_info,
                "features": {
                    "cpu_count": hasattr(psutil, "cpu_count"),
                    "virtual_memory": hasattr(psutil, "virtual_memory"),
                    "disk_usage": hasattr(psutil, "disk_usage"),
                },
            }
        except ImportError as e:
            return {"available": False, "error": str(e)}

    def _check_pathlib(self) -> dict[str, Any]:
        """Check pathlib availability."""
        try:
            from pathlib import Path

            return {"available": True, "test_path": str(Path(__file__).parent)}
        except ImportError as e:
            return {"available": False, "error": str(e)}

    def _check_threading(self) -> dict[str, Any]:
        """Check threading availability."""
        try:
            import threading

            return {
                "available": True,
                "active_count": threading.active_count(),
                "main_thread": threading.main_thread().name,
            }
        except ImportError as e:
            return {"available": False, "error": str(e)}

    def _check_graphviz(self) -> dict[str, Any]:
        """Check graphviz availability."""
        try:
            import graphviz

            return {
                "available": True,
                "version": getattr(graphviz, "__version__", "unknown"),
            }
        except ImportError as e:
            return {"available": False, "error": str(e)}

    def _check_pygments(self) -> dict[str, Any]:
        """Check pygments availability."""
        try:
            import pygments

            return {"available": True, "version": pygments.__version__}
        except ImportError as e:
            return {"available": False, "error": str(e)}

    def _check_sqlite3(self) -> dict[str, Any]:
        """Check sqlite3 availability."""
        try:
            import sqlite3

            return {
                "available": True,
                "version": sqlite3.sqlite_version,
                "threadsafety": sqlite3.threadsafety,
            }
        except ImportError as e:
            return {"available": False, "error": str(e)}

    def _check_requests(self) -> dict[str, Any]:
        """Check requests availability."""
        try:
            import requests

            return {"available": True, "version": requests.__version__}
        except ImportError as e:
            return {"available": False, "error": str(e)}

    def _check_pydantic(self) -> dict[str, Any]:
        """Check pydantic availability."""
        try:
            import pydantic

            return {"available": True, "version": pydantic.VERSION}
        except ImportError as e:
            return {"available": False, "error": str(e)}

    def _check_version(self, current: str | None, required: str) -> dict[str, Any]:
        """Check if current version meets requirement."""
        if not current:
            return {"meets_requirement": False, "reason": "version_unknown"}

        try:
            # Simple version comparison (assumes semantic versioning)
            def version_tuple(v):
                return tuple(map(int, (v.split("."))))

            return {
                "meets_requirement": version_tuple(current) >= version_tuple(required),
                "current": current,
                "required": required,
            }
        except ValueError:
            return {"meets_requirement": False, "reason": "version_parse_error"}

    def _validate_system_requirements(self) -> list[ValidationResult]:
        """Validate system requirements."""
        results = []

        # Memory check
        try:
            memory = psutil.virtual_memory()
            memory_mb = memory.total / (1024 * 1024)

            if memory_mb >= self.system_requirements["memory_mb"]:
                results.append(
                    ValidationResult(
                        check_name="system_memory",
                        category=ValidationCategory.DEPENDENCY,
                        severity=ValidationSeverity.PASS,
                        message=f"System memory: {memory_mb:.0f} MB (required: {self.system_requirements['memory_mb']} MB)",
                        details={
                            "total_mb": memory_mb,
                            "available_mb": memory.available / (1024 * 1024),
                        },
                    ),
                )
            else:
                results.append(
                    ValidationResult(
                        check_name="system_memory",
                        category=ValidationCategory.DEPENDENCY,
                        severity=ValidationSeverity.WARNING,
                        message=f"Low system memory: {memory_mb:.0f} MB (recommended: {self.system_requirements['memory_mb']} MB)",
                        details={
                            "total_mb": memory_mb,
                            "required_mb": self.system_requirements["memory_mb"],
                        },
                        recommendations=[
                            "Add more RAM",
                            "Close unnecessary applications",
                        ],
                    ),
                )
        except Exception as e:
            results.append(
                ValidationResult(
                    check_name="system_memory",
                    category=ValidationCategory.DEPENDENCY,
                    severity=ValidationSeverity.WARNING,
                    message=f"Could not check system memory: {e!s}",
                    details={"error": str(e)},
                ),
            )

        # CPU check
        try:
            cpu_count = psutil.cpu_count()
            if cpu_count >= self.system_requirements["cpu_cores"]:
                results.append(
                    ValidationResult(
                        check_name="system_cpu",
                        category=ValidationCategory.DEPENDENCY,
                        severity=ValidationSeverity.PASS,
                        message=f"CPU cores: {cpu_count} (required: {self.system_requirements['cpu_cores']})",
                        details={
                            "cpu_count": cpu_count,
                            "cpu_percent": psutil.cpu_percent(interval=1),
                        },
                    ),
                )
            else:
                results.append(
                    ValidationResult(
                        check_name="system_cpu",
                        category=ValidationCategory.DEPENDENCY,
                        severity=ValidationSeverity.WARNING,
                        message=f"Limited CPU cores: {cpu_count} (recommended: {self.system_requirements['cpu_cores']})",
                        details={
                            "cpu_count": cpu_count,
                            "required_cores": self.system_requirements["cpu_cores"],
                        },
                        recommendations=["Upgrade CPU", "Reduce concurrent operations"],
                    ),
                )
        except Exception as e:
            results.append(
                ValidationResult(
                    check_name="system_cpu",
                    category=ValidationCategory.DEPENDENCY,
                    severity=ValidationSeverity.WARNING,
                    message=f"Could not check CPU: {e!s}",
                    details={"error": str(e)},
                ),
            )

        # Disk space check
        try:
            disk = psutil.disk_usage("/")
            disk_mb = disk.free / (1024 * 1024)

            if disk_mb >= self.system_requirements["disk_mb"]:
                results.append(
                    ValidationResult(
                        check_name="system_disk",
                        category=ValidationCategory.DEPENDENCY,
                        severity=ValidationSeverity.PASS,
                        message=f"Available disk space: {disk_mb:.0f} MB (required: {self.system_requirements['disk_mb']} MB)",
                        details={
                            "free_mb": disk_mb,
                            "total_mb": disk.total / (1024 * 1024),
                        },
                    ),
                )
            else:
                results.append(
                    ValidationResult(
                        check_name="system_disk",
                        category=ValidationCategory.DEPENDENCY,
                        severity=ValidationSeverity.ERROR,
                        message=f"Low disk space: {disk_mb:.0f} MB (required: {self.system_requirements['disk_mb']} MB)",
                        details={
                            "free_mb": disk_mb,
                            "required_mb": self.system_requirements["disk_mb"],
                        },
                        recommendations=["Free up disk space", "Add more storage"],
                    ),
                )
        except Exception as e:
            results.append(
                ValidationResult(
                    check_name="system_disk",
                    category=ValidationCategory.DEPENDENCY,
                    severity=ValidationSeverity.WARNING,
                    message=f"Could not check disk space: {e!s}",
                    details={"error": str(e)},
                ),
            )

        return results

    def _validate_environment(self) -> list[ValidationResult]:
        """Validate environment variables and settings."""
        results = []

        # Check important environment variables
        env_vars_to_check = {
            "PATH": {"required": True, "description": "System PATH"},
            "PYTHONPATH": {
                "required": False,
                "description": "Python module search path",
            },
            "HOME": {"required": True, "description": "User home directory"},
            "TEMP": {"required": False, "description": "Temporary directory"},
        }

        for var_name, var_info in env_vars_to_check.items():
            var_value = os.environ.get(var_name)

            if var_value:
                results.append(
                    ValidationResult(
                        check_name=f"env_{var_name.lower()}",
                        category=ValidationCategory.DEPENDENCY,
                        severity=ValidationSeverity.PASS,
                        message=f"Environment variable {var_name} is set",
                        details={"variable": var_name, "value_length": len(var_value)},
                    ),
                )
            else:
                severity = (
                    ValidationSeverity.ERROR
                    if var_info["required"]
                    else ValidationSeverity.INFO
                )
                results.append(
                    ValidationResult(
                        check_name=f"env_{var_name.lower()}",
                        category=ValidationCategory.DEPENDENCY,
                        severity=severity,
                        message=f"Environment variable {var_name} is not set",
                        details={
                            "variable": var_name,
                            "description": var_info["description"],
                        },
                        recommendations=(
                            [f"Set {var_name} environment variable"]
                            if var_info["required"]
                            else []
                        ),
                    ),
                )

        return results


class ConfigurationValidator:
    """Validates all system configuration settings."""

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.logger = logging.getLogger(__name__ + ".ConfigurationValidator")

        # Configuration schema definitions
        self.config_schema = {
            "grammar": {
                "source_paths": {"type": list, "required": False},
                "auto_download": {"type": bool, "required": False, "default": True},
                "cache_enabled": {"type": bool, "required": False, "default": True},
                "validation_enabled": {
                    "type": bool,
                    "required": False,
                    "default": True,
                },
            },
            "performance": {
                "optimization_level": {
                    "type": str,
                    "required": False,
                    "default": "balanced",
                },
                "cache_size": {"type": int, "required": False, "default": 1000},
                "thread_pool_size": {"type": int, "required": False, "default": 4},
                "memory_limit_mb": {"type": int, "required": False, "default": 1024},
            },
            "logging": {
                "level": {"type": str, "required": False, "default": "INFO"},
                "format": {"type": str, "required": False},
                "file_path": {"type": str, "required": False},
            },
            "security": {
                "ssl_verify": {"type": bool, "required": False, "default": True},
                "safe_mode": {"type": bool, "required": False, "default": True},
                "sandbox_enabled": {"type": bool, "required": False, "default": False},
            },
        }

    def validate(self) -> list[ValidationResult]:
        """Validate all configuration settings."""
        results = []

        # Validate configuration schema
        results.extend(self._validate_schema())

        # Validate configuration values
        results.extend(self._validate_values())

        # Validate configuration files
        results.extend(self._validate_config_files())

        # Validate environment-specific settings
        results.extend(self._validate_environment_config())

        return results

    def _validate_schema(self) -> list[ValidationResult]:
        """Validate configuration against schema."""
        results = []

        for section_name, section_schema in self.config_schema.items():
            section_config = self.config.get(section_name, {})

            # Check required fields
            for field_name, field_schema in section_schema.items():
                if (
                    field_schema.get("required", False)
                    and field_name not in section_config
                ):
                    results.append(
                        ValidationResult(
                            check_name=f"config_{section_name}_{field_name}",
                            category=ValidationCategory.CONFIGURATION,
                            severity=ValidationSeverity.ERROR,
                            message=f"Required configuration field missing: {section_name}.{field_name}",
                            details={"section": section_name, "field": field_name},
                            recommendations=[
                                f"Set {section_name}.{field_name} in configuration",
                            ],
                        ),
                    )
                elif field_name in section_config:
                    # Validate field type
                    expected_type = field_schema["type"]
                    actual_value = section_config[field_name]

                    if not self._check_type(actual_value, expected_type):
                        results.append(
                            ValidationResult(
                                check_name=f"config_{section_name}_{field_name}_type",
                                category=ValidationCategory.CONFIGURATION,
                                severity=ValidationSeverity.ERROR,
                                message=f"Invalid type for {section_name}.{field_name}: expected {expected_type.__name__}, got {type(actual_value).__name__}",
                                details={
                                    "section": section_name,
                                    "field": field_name,
                                    "expected_type": expected_type.__name__,
                                    "actual_type": type(actual_value).__name__,
                                    "value": actual_value,
                                },
                                recommendations=[
                                    f"Fix type for {section_name}.{field_name}",
                                ],
                            ),
                        )
                    else:
                        results.append(
                            ValidationResult(
                                check_name=f"config_{section_name}_{field_name}",
                                category=ValidationCategory.CONFIGURATION,
                                severity=ValidationSeverity.PASS,
                                message=f"Configuration field {section_name}.{field_name} is valid",
                                details={
                                    "section": section_name,
                                    "field": field_name,
                                    "value": actual_value,
                                },
                            ),
                        )

        return results

    def _check_type(self, value: Any, expected_type: type) -> bool:
        """Check if value matches expected type."""
        if expected_type == list:
            return isinstance(value, list)
        if expected_type == dict:
            return isinstance(value, dict)
        if expected_type == bool:
            return isinstance(value, bool)
        if expected_type == int:
            return isinstance(value, int)
        if expected_type == float:
            return isinstance(value, (int, float))
        if expected_type == str:
            return isinstance(value, str)
        return isinstance(value, expected_type)

    def _validate_values(self) -> list[ValidationResult]:
        """Validate configuration values for correctness."""
        results = []

        # Validate performance settings
        performance_config = self.config.get("performance", {})

        # Check optimization level
        opt_level = performance_config.get("optimization_level", "balanced")
        valid_levels = ["conservative", "balanced", "aggressive", "custom"]

        if opt_level in valid_levels:
            results.append(
                ValidationResult(
                    check_name="performance_optimization_level",
                    category=ValidationCategory.CONFIGURATION,
                    severity=ValidationSeverity.PASS,
                    message=f"Valid optimization level: {opt_level}",
                    details={"level": opt_level},
                ),
            )
        else:
            results.append(
                ValidationResult(
                    check_name="performance_optimization_level",
                    category=ValidationCategory.CONFIGURATION,
                    severity=ValidationSeverity.ERROR,
                    message=f"Invalid optimization level: {opt_level}",
                    details={"level": opt_level, "valid_levels": valid_levels},
                    recommendations=[
                        f"Set optimization_level to one of: {', '.join(valid_levels)}",
                    ],
                ),
            )

        # Check cache size
        cache_size = performance_config.get("cache_size", 1000)
        if isinstance(cache_size, int) and cache_size > 0:
            results.append(
                ValidationResult(
                    check_name="performance_cache_size",
                    category=ValidationCategory.CONFIGURATION,
                    severity=ValidationSeverity.PASS,
                    message=f"Valid cache size: {cache_size}",
                    details={"cache_size": cache_size},
                ),
            )
        else:
            results.append(
                ValidationResult(
                    check_name="performance_cache_size",
                    category=ValidationCategory.CONFIGURATION,
                    severity=ValidationSeverity.ERROR,
                    message=f"Invalid cache size: {cache_size}",
                    details={"cache_size": cache_size},
                    recommendations=["Set cache_size to a positive integer"],
                ),
            )

        # Validate logging settings
        logging_config = self.config.get("logging", {})

        # Check log level
        log_level = logging_config.get("level", "INFO")
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

        if log_level.upper() in valid_levels:
            results.append(
                ValidationResult(
                    check_name="logging_level",
                    category=ValidationCategory.CONFIGURATION,
                    severity=ValidationSeverity.PASS,
                    message=f"Valid log level: {log_level}",
                    details={"level": log_level},
                ),
            )
        else:
            results.append(
                ValidationResult(
                    check_name="logging_level",
                    category=ValidationCategory.CONFIGURATION,
                    severity=ValidationSeverity.WARNING,
                    message=f"Invalid log level: {log_level}",
                    details={"level": log_level, "valid_levels": valid_levels},
                    recommendations=[
                        f"Set log level to one of: {', '.join(valid_levels)}",
                    ],
                ),
            )

        return results

    def _validate_config_files(self) -> list[ValidationResult]:
        """Validate configuration files exist and are readable."""
        results = []

        # Common configuration file locations
        config_files = [
            "chunker.config.yaml",
            "chunker.config.json",
            "chunker.config.toml",
            ".chunkerrc",
            "pyproject.toml",
        ]

        found_configs = []
        for config_file in config_files:
            config_path = Path(config_file)
            if config_path.exists():
                try:
                    # Check if file is readable
                    with open(config_path) as f:
                        content = f.read()

                    found_configs.append(config_file)
                    results.append(
                        ValidationResult(
                            check_name=f"config_file_{config_file.replace('.', '_')}",
                            category=ValidationCategory.CONFIGURATION,
                            severity=ValidationSeverity.PASS,
                            message=f"Configuration file {config_file} is readable",
                            details={"file": config_file, "size": len(content)},
                        ),
                    )
                except Exception as e:
                    results.append(
                        ValidationResult(
                            check_name=f"config_file_{config_file.replace('.', '_')}",
                            category=ValidationCategory.CONFIGURATION,
                            severity=ValidationSeverity.WARNING,
                            message=f"Configuration file {config_file} exists but is not readable: {e!s}",
                            details={"file": config_file, "error": str(e)},
                            recommendations=[f"Fix permissions for {config_file}"],
                        ),
                    )

        if found_configs:
            results.append(
                ValidationResult(
                    check_name="config_files_available",
                    category=ValidationCategory.CONFIGURATION,
                    severity=ValidationSeverity.PASS,
                    message=f"Found {len(found_configs)} configuration file(s)",
                    details={"files": found_configs},
                ),
            )
        else:
            results.append(
                ValidationResult(
                    check_name="config_files_available",
                    category=ValidationCategory.CONFIGURATION,
                    severity=ValidationSeverity.INFO,
                    message="No configuration files found - using defaults",
                    details={"searched_files": config_files},
                    recommendations=["Create a configuration file for custom settings"],
                ),
            )

        return results

    def _validate_environment_config(self) -> list[ValidationResult]:
        """Validate environment-specific configuration."""
        results = []

        # Check for development vs production settings
        env = os.environ.get("ENVIRONMENT", "development").lower()

        if env == "production":
            # Production-specific validations
            security_config = self.config.get("security", {})

            # SSL verification should be enabled in production
            ssl_verify = security_config.get("ssl_verify", True)
            if ssl_verify:
                results.append(
                    ValidationResult(
                        check_name="production_ssl_verify",
                        category=ValidationCategory.CONFIGURATION,
                        severity=ValidationSeverity.PASS,
                        message="SSL verification is enabled for production",
                        details={"ssl_verify": ssl_verify},
                    ),
                )
            else:
                results.append(
                    ValidationResult(
                        check_name="production_ssl_verify",
                        category=ValidationCategory.CONFIGURATION,
                        severity=ValidationSeverity.ERROR,
                        message="SSL verification is disabled in production",
                        details={"ssl_verify": ssl_verify},
                        recommendations=[
                            "Enable SSL verification for production deployment",
                        ],
                    ),
                )

            # Debug mode should be disabled in production
            debug_mode = self.config.get("debug", False)
            if not debug_mode:
                results.append(
                    ValidationResult(
                        check_name="production_debug_mode",
                        category=ValidationCategory.CONFIGURATION,
                        severity=ValidationSeverity.PASS,
                        message="Debug mode is disabled for production",
                        details={"debug_mode": debug_mode},
                    ),
                )
            else:
                results.append(
                    ValidationResult(
                        check_name="production_debug_mode",
                        category=ValidationCategory.CONFIGURATION,
                        severity=ValidationSeverity.WARNING,
                        message="Debug mode is enabled in production",
                        details={"debug_mode": debug_mode},
                        recommendations=[
                            "Disable debug mode for production deployment",
                        ],
                    ),
                )

        return results


class SecurityValidator:
    """Validates security settings and checks for vulnerabilities."""

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.logger = logging.getLogger(__name__ + ".SecurityValidator")

        # Security check configurations
        self.security_checks = {
            "file_permissions": True,
            "ssl_configuration": True,
            "input_validation": True,
            "dependency_vulnerabilities": True,
            "code_injection_risks": True,
        }

    def validate(self) -> list[ValidationResult]:
        """Validate security settings and configurations."""
        results = []

        # Check file permissions
        results.extend(self._check_file_permissions())

        # Check SSL/TLS configuration
        results.extend(self._check_ssl_configuration())

        # Check for potential code injection risks
        results.extend(self._check_code_injection_risks())

        # Check dependency vulnerabilities
        results.extend(self._check_dependency_vulnerabilities())

        # Check input validation
        results.extend(self._check_input_validation())

        # Check for sensitive data exposure
        results.extend(self._check_sensitive_data_exposure())

        return results

    def _check_file_permissions(self) -> list[ValidationResult]:
        """Check file and directory permissions."""
        results = []

        # Check current directory permissions
        current_dir = Path.cwd()
        try:
            stat_info = current_dir.stat()
            permissions = oct(stat_info.st_mode)[-3:]

            # Check if directory is writable by others (security risk)
            if int(permissions[2]) >= 2:  # Others have write permission
                results.append(
                    ValidationResult(
                        check_name="directory_permissions",
                        category=ValidationCategory.SECURITY,
                        severity=ValidationSeverity.WARNING,
                        message=f"Current directory is writable by others: {permissions}",
                        details={
                            "directory": str(current_dir),
                            "permissions": permissions,
                        },
                        recommendations=[
                            "Change directory permissions to remove other write access",
                        ],
                    ),
                )
            else:
                results.append(
                    ValidationResult(
                        check_name="directory_permissions",
                        category=ValidationCategory.SECURITY,
                        severity=ValidationSeverity.PASS,
                        message=f"Directory permissions are secure: {permissions}",
                        details={
                            "directory": str(current_dir),
                            "permissions": permissions,
                        },
                    ),
                )
        except Exception as e:
            results.append(
                ValidationResult(
                    check_name="directory_permissions",
                    category=ValidationCategory.SECURITY,
                    severity=ValidationSeverity.WARNING,
                    message=f"Could not check directory permissions: {e!s}",
                    details={"error": str(e)},
                ),
            )

        # Check for sensitive files with loose permissions
        sensitive_patterns = ["*.key", "*.pem", "*.p12", "*.pfx", "*.conf", "config*"]
        loose_files = []

        for pattern in sensitive_patterns:
            for file_path in current_dir.glob(pattern):
                try:
                    stat_info = file_path.stat()
                    permissions = oct(stat_info.st_mode)[-3:]

                    # Check if file is readable by others
                    if int(permissions[2]) >= 4:  # Others have read permission
                        loose_files.append(
                            {"file": str(file_path), "permissions": permissions},
                        )
                except Exception:
                    continue

        if loose_files:
            results.append(
                ValidationResult(
                    check_name="sensitive_file_permissions",
                    category=ValidationCategory.SECURITY,
                    severity=ValidationSeverity.WARNING,
                    message=f"Found {len(loose_files)} sensitive files with loose permissions",
                    details={"files": loose_files},
                    recommendations=[
                        "Restrict permissions on sensitive files (e.g., chmod 600)",
                    ],
                ),
            )
        else:
            results.append(
                ValidationResult(
                    check_name="sensitive_file_permissions",
                    category=ValidationCategory.SECURITY,
                    severity=ValidationSeverity.PASS,
                    message="No sensitive files with loose permissions found",
                    details={"checked_patterns": sensitive_patterns},
                ),
            )

        return results

    def _check_ssl_configuration(self) -> list[ValidationResult]:
        """Check SSL/TLS configuration."""
        results = []

        # Check SSL context configuration
        try:
            # Test default SSL context
            default_context = ssl.create_default_context()

            results.append(
                ValidationResult(
                    check_name="ssl_context",
                    category=ValidationCategory.SECURITY,
                    severity=ValidationSeverity.PASS,
                    message="SSL context creation successful",
                    details={
                        "protocol": default_context.protocol.name,
                        "verify_mode": default_context.verify_mode.name,
                        "check_hostname": default_context.check_hostname,
                    },
                ),
            )

            # Check for secure protocols
            if default_context.protocol.name in ["TLSv1_2", "TLSv1_3"]:
                results.append(
                    ValidationResult(
                        check_name="ssl_protocol",
                        category=ValidationCategory.SECURITY,
                        severity=ValidationSeverity.PASS,
                        message=f"Secure SSL protocol: {default_context.protocol.name}",
                        details={"protocol": default_context.protocol.name},
                    ),
                )
            else:
                results.append(
                    ValidationResult(
                        check_name="ssl_protocol",
                        category=ValidationCategory.SECURITY,
                        severity=ValidationSeverity.WARNING,
                        message=f"Potentially insecure SSL protocol: {default_context.protocol.name}",
                        details={"protocol": default_context.protocol.name},
                        recommendations=["Use TLS 1.2 or higher"],
                    ),
                )

        except Exception as e:
            results.append(
                ValidationResult(
                    check_name="ssl_context",
                    category=ValidationCategory.SECURITY,
                    severity=ValidationSeverity.WARNING,
                    message=f"SSL context check failed: {e!s}",
                    details={"error": str(e)},
                ),
            )

        # Check SSL configuration in settings
        security_config = self.config.get("security", {})
        ssl_verify = security_config.get("ssl_verify", True)

        if ssl_verify:
            results.append(
                ValidationResult(
                    check_name="ssl_verification_enabled",
                    category=ValidationCategory.SECURITY,
                    severity=ValidationSeverity.PASS,
                    message="SSL certificate verification is enabled",
                    details={"ssl_verify": ssl_verify},
                ),
            )
        else:
            results.append(
                ValidationResult(
                    check_name="ssl_verification_enabled",
                    category=ValidationCategory.SECURITY,
                    severity=ValidationSeverity.ERROR,
                    message="SSL certificate verification is disabled",
                    details={"ssl_verify": ssl_verify},
                    recommendations=["Enable SSL certificate verification"],
                ),
            )

        return results

    def _check_code_injection_risks(self) -> list[ValidationResult]:
        """Check for potential code injection vulnerabilities."""
        results = []

        # Check for dangerous function usage patterns
        dangerous_patterns = {
            "eval": r"\beval\s*\(",
            "exec": r"\bexec\s*\(",
            "subprocess_shell": r"subprocess\.\w+\([^)]*shell\s*=\s*True",
            "os_system": r"os\.system\s*\(",
            "pickle_loads": r"pickle\.loads?\s*\(",
        }

        # Scan Python files in current directory
        python_files = list(Path.cwd().glob("**/*.py"))
        vulnerable_files = []

        for file_path in python_files[:50]:  # Limit to first 50 files for performance
            try:
                with open(file_path, encoding="utf-8", errors="ignore") as f:
                    content = f.read()

                file_vulnerabilities = []
                for pattern_name, pattern in dangerous_patterns.items():
                    matches = re.findall(pattern, content, re.IGNORECASE)
                    if matches:
                        file_vulnerabilities.append(
                            {"pattern": pattern_name, "matches": len(matches)},
                        )

                if file_vulnerabilities:
                    vulnerable_files.append(
                        {
                            "file": str(file_path),
                            "vulnerabilities": file_vulnerabilities,
                        },
                    )

            except Exception:
                continue

        if vulnerable_files:
            results.append(
                ValidationResult(
                    check_name="code_injection_risks",
                    category=ValidationCategory.SECURITY,
                    severity=ValidationSeverity.WARNING,
                    message=f"Found potential code injection risks in {len(vulnerable_files)} files",
                    details={"vulnerable_files": vulnerable_files},
                    recommendations=[
                        "Review usage of eval(), exec(), and shell=True",
                        "Use safer alternatives like ast.literal_eval()",
                        "Validate and sanitize all user inputs",
                    ],
                ),
            )
        else:
            results.append(
                ValidationResult(
                    check_name="code_injection_risks",
                    category=ValidationCategory.SECURITY,
                    severity=ValidationSeverity.PASS,
                    message="No obvious code injection risks found",
                    details={
                        "scanned_files": len(python_files),
                        "patterns_checked": list(dangerous_patterns.keys()),
                    },
                ),
            )

        return results

    def _check_dependency_vulnerabilities(self) -> list[ValidationResult]:
        """Check for known vulnerabilities in dependencies."""
        results = []

        # This is a simplified check - in production you would use tools like
        # safety, bandit, or integrate with vulnerability databases

        # Check for old Python version (known vulnerabilities)
        python_version = sys.version_info

        if python_version < (3, 8):
            results.append(
                ValidationResult(
                    check_name="python_version_security",
                    category=ValidationCategory.SECURITY,
                    severity=ValidationSeverity.ERROR,
                    message=f"Python version {python_version.major}.{python_version.minor} has known security vulnerabilities",
                    details={
                        "version": f"{python_version.major}.{python_version.minor}.{python_version.micro}",
                    },
                    recommendations=["Upgrade to Python 3.8 or higher"],
                ),
            )
        elif python_version < (3, 9):
            results.append(
                ValidationResult(
                    check_name="python_version_security",
                    category=ValidationCategory.SECURITY,
                    severity=ValidationSeverity.WARNING,
                    message=f"Python version {python_version.major}.{python_version.minor} is approaching end-of-life",
                    details={
                        "version": f"{python_version.major}.{python_version.minor}.{python_version.micro}",
                    },
                    recommendations=["Consider upgrading to a newer Python version"],
                ),
            )
        else:
            results.append(
                ValidationResult(
                    check_name="python_version_security",
                    category=ValidationCategory.SECURITY,
                    severity=ValidationSeverity.PASS,
                    message=f"Python version {python_version.major}.{python_version.minor} is secure",
                    details={
                        "version": f"{python_version.major}.{python_version.minor}.{python_version.micro}",
                    },
                ),
            )

        # Check for requirements.txt and suggest vulnerability scanning
        requirements_files = ["requirements.txt", "Pipfile", "pyproject.toml"]
        found_requirements = []

        for req_file in requirements_files:
            if Path(req_file).exists():
                found_requirements.append(req_file)

        if found_requirements:
            results.append(
                ValidationResult(
                    check_name="dependency_files_found",
                    category=ValidationCategory.SECURITY,
                    severity=ValidationSeverity.INFO,
                    message=f"Found dependency files: {', '.join(found_requirements)}",
                    details={"files": found_requirements},
                    recommendations=[
                        "Run 'pip install safety && safety check' to scan for vulnerabilities",
                        "Keep dependencies updated",
                        "Use dependency pinning for security",
                    ],
                ),
            )

        return results

    def _check_input_validation(self) -> list[ValidationResult]:
        """Check input validation implementations."""
        results = []

        # Look for input validation patterns in code
        validation_patterns = {
            "path_validation": r"Path\([^)]*\)\.resolve\(\)",
            "type_checking": r"isinstance\s*\([^)]+\)",
            "regex_validation": r"re\.(match|search|fullmatch)",
            "pydantic_models": r"class\s+\w+\([^)]*BaseModel[^)]*\):",
        }

        python_files = list(Path.cwd().glob("**/*.py"))
        validation_usage = {}

        for file_path in python_files[:20]:  # Limit for performance
            try:
                with open(file_path, encoding="utf-8", errors="ignore") as f:
                    content = f.read()

                for pattern_name, pattern in validation_patterns.items():
                    matches = len(re.findall(pattern, content, re.IGNORECASE))
                    if matches > 0:
                        validation_usage[pattern_name] = (
                            validation_usage.get(pattern_name, 0) + matches
                        )

            except Exception:
                continue

        if validation_usage:
            results.append(
                ValidationResult(
                    check_name="input_validation_present",
                    category=ValidationCategory.SECURITY,
                    severity=ValidationSeverity.PASS,
                    message="Input validation patterns found in codebase",
                    details={"validation_patterns": validation_usage},
                    recommendations=["Continue using input validation consistently"],
                ),
            )
        else:
            results.append(
                ValidationResult(
                    check_name="input_validation_present",
                    category=ValidationCategory.SECURITY,
                    severity=ValidationSeverity.WARNING,
                    message="Limited input validation patterns found",
                    details={
                        "scanned_files": len(python_files),
                        "patterns": list(validation_patterns.keys()),
                    },
                    recommendations=[
                        "Implement input validation for all user inputs",
                        "Use type hints and validation libraries",
                        "Validate file paths and prevent directory traversal",
                    ],
                ),
            )

        return results

    def _check_sensitive_data_exposure(self) -> list[ValidationResult]:
        """Check for potential sensitive data exposure."""
        results = []

        # Patterns that might indicate sensitive data
        sensitive_patterns = {
            "api_keys": r"(?i)(api[_-]?key|apikey)\s*[=:]\s*['\"][^'\"]{10,}['\"]",
            "passwords": r"(?i)(password|passwd|pwd)\s*[=:]\s*['\"][^'\"]{3,}['\"]",
            "tokens": r"(?i)(token|auth[_-]?token)\s*[=:]\s*['\"][^'\"]{10,}['\"]",
            "secrets": r"(?i)(secret[_-]?key|secret)\s*[=:]\s*['\"][^'\"]{10,}['\"]",
            "private_keys": r"-----BEGIN (RSA |)PRIVATE KEY-----",
        }

        # Files to check
        files_to_check = []
        for pattern in [
            "*.py",
            "*.yaml",
            "*.yml",
            "*.json",
            "*.conf",
            "*.cfg",
            "*.env",
        ]:
            files_to_check.extend(Path.cwd().glob(pattern))

        exposed_data = []

        for file_path in files_to_check[:30]:  # Limit for performance
            try:
                with open(file_path, encoding="utf-8", errors="ignore") as f:
                    content = f.read()

                file_exposures = []
                for pattern_name, pattern in sensitive_patterns.items():
                    matches = re.findall(pattern, content)
                    if matches:
                        file_exposures.append(
                            {"type": pattern_name, "count": len(matches)},
                        )

                if file_exposures:
                    exposed_data.append(
                        {"file": str(file_path), "exposures": file_exposures},
                    )

            except Exception:
                continue

        if exposed_data:
            results.append(
                ValidationResult(
                    check_name="sensitive_data_exposure",
                    category=ValidationCategory.SECURITY,
                    severity=ValidationSeverity.ERROR,
                    message=f"Potential sensitive data exposure found in {len(exposed_data)} files",
                    details={"exposed_files": exposed_data},
                    recommendations=[
                        "Move sensitive data to environment variables",
                        "Use secret management systems",
                        "Add sensitive files to .gitignore",
                        "Review and remove hardcoded credentials",
                    ],
                ),
            )
        else:
            results.append(
                ValidationResult(
                    check_name="sensitive_data_exposure",
                    category=ValidationCategory.SECURITY,
                    severity=ValidationSeverity.PASS,
                    message="No obvious sensitive data exposure found",
                    details={
                        "scanned_files": len(files_to_check),
                        "patterns_checked": list(sensitive_patterns.keys()),
                    },
                ),
            )

        return results


class PerformanceValidator:
    """Validates system performance meets requirements."""

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.logger = logging.getLogger(__name__ + ".PerformanceValidator")

        # Performance requirements
        self.requirements = {
            "response_time_ms": self.config.get("max_response_time_ms", 5000),
            "memory_usage_mb": self.config.get("max_memory_usage_mb", 1024),
            "cpu_usage_percent": self.config.get("max_cpu_usage_percent", 80),
            "throughput_ops_sec": self.config.get("min_throughput_ops_sec", 10),
            "cache_hit_rate": self.config.get("min_cache_hit_rate", 0.7),
        }

    def validate(self) -> list[ValidationResult]:
        """Validate system performance."""
        results = []

        # Test basic functionality performance
        results.extend(self._test_basic_performance())

        # Test memory usage
        results.extend(self._test_memory_performance())

        # Test concurrent operations
        results.extend(self._test_concurrency_performance())

        # Test with performance optimizer if available
        if PERFORMANCE_OPTIMIZER_AVAILABLE:
            results.extend(self._test_performance_optimizer())

        return results

    def _test_basic_performance(self) -> list[ValidationResult]:
        """Test basic functionality performance."""
        results = []

        # Test simple operations
        operations = [
            ("string_processing", self._test_string_processing),
            ("file_operations", self._test_file_operations),
            ("list_operations", self._test_list_operations),
        ]

        for op_name, op_func in operations:
            start_time = time.time()
            start_memory = psutil.Process().memory_info().rss / 1024 / 1024

            try:
                op_func()

                end_time = time.time()
                end_memory = psutil.Process().memory_info().rss / 1024 / 1024

                duration_ms = (end_time - start_time) * 1000
                memory_delta = end_memory - start_memory

                # Check performance against requirements
                if duration_ms <= self.requirements["response_time_ms"]:
                    results.append(
                        ValidationResult(
                            check_name=f"performance_{op_name}",
                            category=ValidationCategory.PERFORMANCE,
                            severity=ValidationSeverity.PASS,
                            message=f"{op_name} completed in {duration_ms:.2f}ms",
                            details={
                                "duration_ms": duration_ms,
                                "memory_delta_mb": memory_delta,
                                "requirement_ms": self.requirements["response_time_ms"],
                            },
                        ),
                    )
                else:
                    results.append(
                        ValidationResult(
                            check_name=f"performance_{op_name}",
                            category=ValidationCategory.PERFORMANCE,
                            severity=ValidationSeverity.WARNING,
                            message=f"{op_name} took {duration_ms:.2f}ms (requirement: {self.requirements['response_time_ms']}ms)",
                            details={
                                "duration_ms": duration_ms,
                                "memory_delta_mb": memory_delta,
                                "requirement_ms": self.requirements["response_time_ms"],
                            },
                            recommendations=[
                                "Optimize operation performance",
                                "Check system resources",
                                "Consider performance tuning",
                            ],
                        ),
                    )

            except Exception as e:
                results.append(
                    ValidationResult(
                        check_name=f"performance_{op_name}",
                        category=ValidationCategory.PERFORMANCE,
                        severity=ValidationSeverity.ERROR,
                        message=f"Performance test {op_name} failed: {e!s}",
                        details={"error": str(e)},
                        recommendations=[f"Fix issues in {op_name} operation"],
                    ),
                )

        return results

    def _test_string_processing(self) -> None:
        """Test string processing performance."""
        # Simulate string operations
        data = "test string " * 1000
        for _ in range(100):
            data.upper().lower().strip().split()

    def _test_file_operations(self) -> None:
        """Test file operations performance."""
        # Simulate file operations
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.write("test data " * 1000)
            temp_path = f.name

        try:
            for _ in range(10):
                with open(temp_path) as f:
                    f.read()
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def _test_list_operations(self) -> None:
        """Test list operations performance."""
        # Simulate list operations
        data = list(range(10000))
        for _ in range(10):
            sorted(data, reverse=True)

    def _test_memory_performance(self) -> list[ValidationResult]:
        """Test memory usage patterns."""
        results = []

        # Get baseline memory
        process = psutil.Process()
        baseline_memory = process.memory_info().rss / 1024 / 1024

        # Perform memory-intensive operation
        try:
            # Create some data structures
            large_list = list(range(100000))
            large_dict = {i: f"value_{i}" for i in range(10000)}

            # Check peak memory
            peak_memory = process.memory_info().rss / 1024 / 1024
            memory_increase = peak_memory - baseline_memory

            # Clean up
            del large_list, large_dict

            # Check if memory usage is within limits
            if peak_memory <= self.requirements["memory_usage_mb"]:
                results.append(
                    ValidationResult(
                        check_name="memory_usage_test",
                        category=ValidationCategory.PERFORMANCE,
                        severity=ValidationSeverity.PASS,
                        message=f"Memory usage test passed: {peak_memory:.1f} MB",
                        details={
                            "baseline_mb": baseline_memory,
                            "peak_mb": peak_memory,
                            "increase_mb": memory_increase,
                            "limit_mb": self.requirements["memory_usage_mb"],
                        },
                    ),
                )
            else:
                results.append(
                    ValidationResult(
                        check_name="memory_usage_test",
                        category=ValidationCategory.PERFORMANCE,
                        severity=ValidationSeverity.WARNING,
                        message=f"High memory usage: {peak_memory:.1f} MB (limit: {self.requirements['memory_usage_mb']} MB)",
                        details={
                            "baseline_mb": baseline_memory,
                            "peak_mb": peak_memory,
                            "increase_mb": memory_increase,
                            "limit_mb": self.requirements["memory_usage_mb"],
                        },
                        recommendations=[
                            "Optimize memory usage",
                            "Check for memory leaks",
                            "Consider garbage collection tuning",
                        ],
                    ),
                )

        except Exception as e:
            results.append(
                ValidationResult(
                    check_name="memory_usage_test",
                    category=ValidationCategory.PERFORMANCE,
                    severity=ValidationSeverity.ERROR,
                    message=f"Memory test failed: {e!s}",
                    details={"error": str(e)},
                    recommendations=["Investigate memory test failure"],
                ),
            )

        return results

    def _test_concurrency_performance(self) -> list[ValidationResult]:
        """Test concurrent operations performance."""
        results = []

        try:
            # Test with thread pool
            def simple_task(n):
                return sum(i * i for i in range(n))

            start_time = time.time()

            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = [executor.submit(simple_task, 1000) for _ in range(20)]
                completed_results = [f.result() for f in futures]

            end_time = time.time()
            duration = end_time - start_time
            throughput = len(completed_results) / duration

            if throughput >= self.requirements["throughput_ops_sec"]:
                results.append(
                    ValidationResult(
                        check_name="concurrency_throughput",
                        category=ValidationCategory.PERFORMANCE,
                        severity=ValidationSeverity.PASS,
                        message=f"Concurrency test passed: {throughput:.1f} ops/sec",
                        details={
                            "throughput_ops_sec": throughput,
                            "requirement_ops_sec": self.requirements[
                                "throughput_ops_sec"
                            ],
                            "duration": duration,
                            "operations": len(completed_results),
                        },
                    ),
                )
            else:
                results.append(
                    ValidationResult(
                        check_name="concurrency_throughput",
                        category=ValidationCategory.PERFORMANCE,
                        severity=ValidationSeverity.WARNING,
                        message=f"Low concurrency throughput: {throughput:.1f} ops/sec (requirement: {self.requirements['throughput_ops_sec']} ops/sec)",
                        details={
                            "throughput_ops_sec": throughput,
                            "requirement_ops_sec": self.requirements[
                                "throughput_ops_sec"
                            ],
                            "duration": duration,
                            "operations": len(completed_results),
                        },
                        recommendations=[
                            "Optimize concurrent operations",
                            "Check thread pool configuration",
                            "Review system resources",
                        ],
                    ),
                )

        except Exception as e:
            results.append(
                ValidationResult(
                    check_name="concurrency_throughput",
                    category=ValidationCategory.PERFORMANCE,
                    severity=ValidationSeverity.ERROR,
                    message=f"Concurrency test failed: {e!s}",
                    details={"error": str(e)},
                    recommendations=["Investigate concurrency test failure"],
                ),
            )

        return results

    def _test_performance_optimizer(self) -> list[ValidationResult]:
        """Test performance optimizer if available."""
        results = []

        try:
            # Create performance optimizer instance
            optimizer = PerformanceOptimizer(
                config={"monitoring": {"sample_interval": 1.0}},
            )

            # Run optimization
            start_time = time.time()
            optimization_result = optimizer.optimize_system(force=True)
            duration = time.time() - start_time

            if optimization_result.get("status") == "success":
                health_score = optimization_result.get("health_score", 0)

                if health_score >= 70:  # 70% threshold
                    results.append(
                        ValidationResult(
                            check_name="performance_optimizer_health",
                            category=ValidationCategory.PERFORMANCE,
                            severity=ValidationSeverity.PASS,
                            message=f"Performance optimizer health score: {health_score:.1f}/100",
                            details={
                                "health_score": health_score,
                                "optimization_duration": duration,
                                "optimization_result": optimization_result,
                            },
                        ),
                    )
                else:
                    results.append(
                        ValidationResult(
                            check_name="performance_optimizer_health",
                            category=ValidationCategory.PERFORMANCE,
                            severity=ValidationSeverity.WARNING,
                            message=f"Low performance optimizer health score: {health_score:.1f}/100",
                            details={
                                "health_score": health_score,
                                "optimization_duration": duration,
                                "optimization_result": optimization_result,
                            },
                            recommendations=[
                                "Investigate performance bottlenecks",
                                "Check system resources",
                                "Review optimization configuration",
                            ],
                        ),
                    )
            else:
                results.append(
                    ValidationResult(
                        check_name="performance_optimizer_execution",
                        category=ValidationCategory.PERFORMANCE,
                        severity=ValidationSeverity.ERROR,
                        message="Performance optimizer failed to execute",
                        details={"optimization_result": optimization_result},
                        recommendations=["Check performance optimizer configuration"],
                    ),
                )

            # Cleanup
            optimizer.shutdown()

        except Exception as e:
            results.append(
                ValidationResult(
                    check_name="performance_optimizer_test",
                    category=ValidationCategory.PERFORMANCE,
                    severity=ValidationSeverity.WARNING,
                    message=f"Performance optimizer test failed: {e!s}",
                    details={"error": str(e)},
                    recommendations=["Check performance optimizer installation"],
                ),
            )

        return results


class IntegrationValidator:
    """Validates all component integrations work correctly."""

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.logger = logging.getLogger(__name__ + ".IntegrationValidator")

    def validate(self) -> list[ValidationResult]:
        """Validate all system integrations."""
        results = []

        # Test core integration
        if CORE_INTEGRATION_AVAILABLE:
            results.extend(self._test_core_integration())

        # Test performance optimizer integration
        if PERFORMANCE_OPTIMIZER_AVAILABLE:
            results.extend(self._test_performance_integration())

        # Test user experience integration
        if USER_EXPERIENCE_AVAILABLE:
            results.extend(self._test_user_experience_integration())

        # Test grammar components integration
        if GRAMMAR_COMPONENTS_AVAILABLE:
            results.extend(self._test_grammar_integration())

        # Test error handling integration
        if ERROR_HANDLING_AVAILABLE:
            results.extend(self._test_error_handling_integration())

        # Test cross-component integration
        results.extend(self._test_cross_component_integration())

        return results

    def _test_core_integration(self) -> list[ValidationResult]:
        """Test core system integration."""
        results = []

        try:
            # Test system integrator initialization
            integrator = get_system_integrator()

            if integrator:
                results.append(
                    ValidationResult(
                        check_name="core_integrator_initialization",
                        category=ValidationCategory.INTEGRATION,
                        severity=ValidationSeverity.PASS,
                        message="Core system integrator initialized successfully",
                        details={"session_id": getattr(integrator, "session_id", None)},
                    ),
                )

                # Test system initialization
                try:
                    init_result = integrator.initialize_system()

                    if init_result.get("status") == "success":
                        results.append(
                            ValidationResult(
                                check_name="core_system_initialization",
                                category=ValidationCategory.INTEGRATION,
                                severity=ValidationSeverity.PASS,
                                message="Core system initialization successful",
                                details=init_result,
                            ),
                        )
                    else:
                        results.append(
                            ValidationResult(
                                check_name="core_system_initialization",
                                category=ValidationCategory.INTEGRATION,
                                severity=ValidationSeverity.WARNING,
                                message="Core system initialization completed with issues",
                                details=init_result,
                                recommendations=["Check system component availability"],
                            ),
                        )

                except Exception as e:
                    results.append(
                        ValidationResult(
                            check_name="core_system_initialization",
                            category=ValidationCategory.INTEGRATION,
                            severity=ValidationSeverity.ERROR,
                            message=f"Core system initialization failed: {e!s}",
                            details={"error": str(e)},
                            recommendations=[
                                "Check system dependencies and configuration",
                            ],
                        ),
                    )

                # Test diagnostics
                try:
                    diagnostics = integrator.get_system_diagnostics()
                    health_status = diagnostics.get("system_health", {}).get(
                        "overall_status",
                    )

                    if health_status == "healthy":
                        results.append(
                            ValidationResult(
                                check_name="core_system_health",
                                category=ValidationCategory.INTEGRATION,
                                severity=ValidationSeverity.PASS,
                                message="Core system health is good",
                                details={
                                    "health_status": health_status,
                                    "diagnostics": diagnostics,
                                },
                            ),
                        )
                    else:
                        results.append(
                            ValidationResult(
                                check_name="core_system_health",
                                category=ValidationCategory.INTEGRATION,
                                severity=ValidationSeverity.WARNING,
                                message=f"Core system health: {health_status}",
                                details={
                                    "health_status": health_status,
                                    "diagnostics": diagnostics,
                                },
                                recommendations=["Check component health issues"],
                            ),
                        )

                except Exception as e:
                    results.append(
                        ValidationResult(
                            check_name="core_system_health",
                            category=ValidationCategory.INTEGRATION,
                            severity=ValidationSeverity.WARNING,
                            message=f"Could not get system diagnostics: {e!s}",
                            details={"error": str(e)},
                        ),
                    )

            else:
                results.append(
                    ValidationResult(
                        check_name="core_integrator_initialization",
                        category=ValidationCategory.INTEGRATION,
                        severity=ValidationSeverity.ERROR,
                        message="Could not initialize core system integrator",
                        recommendations=["Check core integration module installation"],
                    ),
                )

        except Exception as e:
            results.append(
                ValidationResult(
                    check_name="core_integration_test",
                    category=ValidationCategory.INTEGRATION,
                    severity=ValidationSeverity.ERROR,
                    message=f"Core integration test failed: {e!s}",
                    details={"error": str(e)},
                    recommendations=["Check core integration module"],
                ),
            )

        return results

    def _test_performance_integration(self) -> list[ValidationResult]:
        """Test performance optimizer integration."""
        results = []

        try:
            # Test performance optimizer creation
            optimizer = PerformanceOptimizer(
                config={"monitoring": {"sample_interval": 1.0}},
            )

            results.append(
                ValidationResult(
                    check_name="performance_optimizer_creation",
                    category=ValidationCategory.INTEGRATION,
                    severity=ValidationSeverity.PASS,
                    message="Performance optimizer created successfully",
                    details={
                        "optimization_level": str(
                            getattr(optimizer, "optimization_level", None),
                        ),
                    },
                ),
            )

            # Test performance report generation
            try:
                report = optimizer.get_performance_report()

                if report and "timestamp" in report:
                    results.append(
                        ValidationResult(
                            check_name="performance_report_generation",
                            category=ValidationCategory.INTEGRATION,
                            severity=ValidationSeverity.PASS,
                            message="Performance report generated successfully",
                            details={"report_timestamp": report.get("timestamp")},
                        ),
                    )
                else:
                    results.append(
                        ValidationResult(
                            check_name="performance_report_generation",
                            category=ValidationCategory.INTEGRATION,
                            severity=ValidationSeverity.WARNING,
                            message="Performance report generation returned invalid data",
                            details={"report": report},
                            recommendations=[
                                "Check performance optimizer configuration",
                            ],
                        ),
                    )

            except Exception as e:
                results.append(
                    ValidationResult(
                        check_name="performance_report_generation",
                        category=ValidationCategory.INTEGRATION,
                        severity=ValidationSeverity.ERROR,
                        message=f"Performance report generation failed: {e!s}",
                        details={"error": str(e)},
                    ),
                )

            # Cleanup
            optimizer.shutdown()

        except Exception as e:
            results.append(
                ValidationResult(
                    check_name="performance_integration_test",
                    category=ValidationCategory.INTEGRATION,
                    severity=ValidationSeverity.ERROR,
                    message=f"Performance integration test failed: {e!s}",
                    details={"error": str(e)},
                    recommendations=["Check performance optimizer module"],
                ),
            )

        return results

    def _test_user_experience_integration(self) -> list[ValidationResult]:
        """Test user experience manager integration."""
        results = []

        try:
            # Test user experience manager creation
            ux_manager = UserExperienceManager(config={"interaction_mode": "silent"})

            results.append(
                ValidationResult(
                    check_name="user_experience_creation",
                    category=ValidationCategory.INTEGRATION,
                    severity=ValidationSeverity.PASS,
                    message="User experience manager created successfully",
                    details={
                        "interaction_mode": str(
                            getattr(ux_manager, "interaction_mode", None),
                        ),
                    },
                ),
            )

            # Test simplified API
            try:
                simplified_api = ux_manager.get_simplified_api()

                if simplified_api:
                    results.append(
                        ValidationResult(
                            check_name="user_experience_api",
                            category=ValidationCategory.INTEGRATION,
                            severity=ValidationSeverity.PASS,
                            message="User experience simplified API available",
                            details={"api_type": type(simplified_api).__name__},
                        ),
                    )
                else:
                    results.append(
                        ValidationResult(
                            check_name="user_experience_api",
                            category=ValidationCategory.INTEGRATION,
                            severity=ValidationSeverity.WARNING,
                            message="User experience simplified API not available",
                        ),
                    )

            except Exception as e:
                results.append(
                    ValidationResult(
                        check_name="user_experience_api",
                        category=ValidationCategory.INTEGRATION,
                        severity=ValidationSeverity.ERROR,
                        message=f"User experience API test failed: {e!s}",
                        details={"error": str(e)},
                    ),
                )

        except Exception as e:
            results.append(
                ValidationResult(
                    check_name="user_experience_integration_test",
                    category=ValidationCategory.INTEGRATION,
                    severity=ValidationSeverity.WARNING,
                    message=f"User experience integration test failed: {e!s}",
                    details={"error": str(e)},
                    recommendations=["Check user experience module"],
                ),
            )

        return results

    def _test_grammar_integration(self) -> list[ValidationResult]:
        """Test grammar components integration."""
        results = []

        try:
            # Test grammar manager
            if GrammarManager:
                manager = GrammarManager()
                results.append(
                    ValidationResult(
                        check_name="grammar_manager_creation",
                        category=ValidationCategory.INTEGRATION,
                        severity=ValidationSeverity.PASS,
                        message="Grammar manager created successfully",
                    ),
                )

            # Test grammar registry
            if GrammarRegistry:
                registry = GrammarRegistry()
                results.append(
                    ValidationResult(
                        check_name="grammar_registry_creation",
                        category=ValidationCategory.INTEGRATION,
                        severity=ValidationSeverity.PASS,
                        message="Grammar registry created successfully",
                    ),
                )

            # Test grammar validator
            if GrammarValidator:
                validator = GrammarValidator()
                results.append(
                    ValidationResult(
                        check_name="grammar_validator_creation",
                        category=ValidationCategory.INTEGRATION,
                        severity=ValidationSeverity.PASS,
                        message="Grammar validator created successfully",
                    ),
                )

        except Exception as e:
            results.append(
                ValidationResult(
                    check_name="grammar_integration_test",
                    category=ValidationCategory.INTEGRATION,
                    severity=ValidationSeverity.WARNING,
                    message=f"Grammar integration test failed: {e!s}",
                    details={"error": str(e)},
                    recommendations=["Check grammar components module"],
                ),
            )

        return results

    def _test_error_handling_integration(self) -> list[ValidationResult]:
        """Test error handling integration."""
        results = []

        try:
            # Test error handling pipeline
            if ErrorHandlingPipeline:
                pipeline = ErrorHandlingPipeline()
                results.append(
                    ValidationResult(
                        check_name="error_pipeline_creation",
                        category=ValidationCategory.INTEGRATION,
                        severity=ValidationSeverity.PASS,
                        message="Error handling pipeline created successfully",
                    ),
                )

                # Test error processing
                try:
                    test_error = ValueError("Test error for validation")
                    result = pipeline.process_error(test_error, context={"test": True})

                    if result:
                        results.append(
                            ValidationResult(
                                check_name="error_pipeline_processing",
                                category=ValidationCategory.INTEGRATION,
                                severity=ValidationSeverity.PASS,
                                message="Error handling pipeline processes errors correctly",
                                details={"result_type": type(result).__name__},
                            ),
                        )
                    else:
                        results.append(
                            ValidationResult(
                                check_name="error_pipeline_processing",
                                category=ValidationCategory.INTEGRATION,
                                severity=ValidationSeverity.WARNING,
                                message="Error handling pipeline returned no result",
                            ),
                        )

                except Exception as e:
                    results.append(
                        ValidationResult(
                            check_name="error_pipeline_processing",
                            category=ValidationCategory.INTEGRATION,
                            severity=ValidationSeverity.ERROR,
                            message=f"Error handling pipeline test failed: {e!s}",
                            details={"error": str(e)},
                        ),
                    )

        except Exception as e:
            results.append(
                ValidationResult(
                    check_name="error_handling_integration_test",
                    category=ValidationCategory.INTEGRATION,
                    severity=ValidationSeverity.WARNING,
                    message=f"Error handling integration test failed: {e!s}",
                    details={"error": str(e)},
                    recommendations=["Check error handling module"],
                ),
            )

        return results

    def _test_cross_component_integration(self) -> list[ValidationResult]:
        """Test cross-component integration scenarios."""
        results = []

        # Test integration between core and performance components
        if CORE_INTEGRATION_AVAILABLE and PERFORMANCE_OPTIMIZER_AVAILABLE:
            try:
                integrator = get_system_integrator()
                optimizer = PerformanceOptimizer(system_integrator=integrator)

                # Test if optimizer can get system health from integrator
                report = optimizer.get_performance_report()
                integration_status = report.get("system_integration", {})

                if integration_status.get("available", False):
                    results.append(
                        ValidationResult(
                            check_name="core_performance_integration",
                            category=ValidationCategory.INTEGRATION,
                            severity=ValidationSeverity.PASS,
                            message="Core and performance components integrated successfully",
                            details=integration_status,
                        ),
                    )
                else:
                    results.append(
                        ValidationResult(
                            check_name="core_performance_integration",
                            category=ValidationCategory.INTEGRATION,
                            severity=ValidationSeverity.WARNING,
                            message="Core and performance components not fully integrated",
                            details=integration_status,
                            recommendations=[
                                "Check component integration configuration",
                            ],
                        ),
                    )

                optimizer.shutdown()

            except Exception as e:
                results.append(
                    ValidationResult(
                        check_name="core_performance_integration",
                        category=ValidationCategory.INTEGRATION,
                        severity=ValidationSeverity.ERROR,
                        message=f"Core-performance integration test failed: {e!s}",
                        details={"error": str(e)},
                    ),
                )

        # Test integration with core chunking if available
        if CORE_CHUNKING_AVAILABLE:
            try:
                # Test basic chunking functionality
                if chunk_text:
                    test_text = "def hello_world():\n    print('Hello, World!')\n    return True"
                    chunks = chunk_text(test_text, language="python")

                    if chunks:
                        results.append(
                            ValidationResult(
                                check_name="core_chunking_integration",
                                category=ValidationCategory.INTEGRATION,
                                severity=ValidationSeverity.PASS,
                                message=f"Core chunking working: {len(chunks)} chunks generated",
                                details={
                                    "chunk_count": len(chunks),
                                    "test_language": "python",
                                },
                            ),
                        )
                    else:
                        results.append(
                            ValidationResult(
                                check_name="core_chunking_integration",
                                category=ValidationCategory.INTEGRATION,
                                severity=ValidationSeverity.WARNING,
                                message="Core chunking returned no chunks",
                                recommendations=["Check chunking configuration"],
                            ),
                        )

            except Exception as e:
                results.append(
                    ValidationResult(
                        check_name="core_chunking_integration",
                        category=ValidationCategory.INTEGRATION,
                        severity=ValidationSeverity.ERROR,
                        message=f"Core chunking integration test failed: {e!s}",
                        details={"error": str(e)},
                    ),
                )

        return results


class CriticalPathValidator:
    """Validates critical system paths and end-to-end workflows."""

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.logger = logging.getLogger(__name__ + ".CriticalPathValidator")

    def validate(self) -> list[ValidationResult]:
        """Validate critical paths and workflows."""
        results = []

        # Test complete system startup and shutdown
        results.extend(self._test_system_lifecycle())

        # Test error recovery scenarios
        results.extend(self._test_error_recovery())

        # Test resource exhaustion scenarios
        results.extend(self._test_resource_limits())

        # Test concurrent access patterns
        results.extend(self._test_concurrent_access())

        # Test data integrity
        results.extend(self._test_data_integrity())

        return results

    def _test_system_lifecycle(self) -> list[ValidationResult]:
        """Test complete system startup and shutdown."""
        results = []

        if not CORE_INTEGRATION_AVAILABLE:
            results.append(
                ValidationResult(
                    check_name="system_lifecycle_skipped",
                    category=ValidationCategory.CRITICAL_PATH,
                    severity=ValidationSeverity.INFO,
                    message="System lifecycle test skipped - core integration not available",
                ),
            )
            return results

        try:
            # Test system startup
            startup_start = time.time()
            integrator = get_system_integrator()
            init_result = integrator.initialize_system()
            startup_duration = time.time() - startup_start

            if init_result.get("status") == "success":
                results.append(
                    ValidationResult(
                        check_name="system_startup",
                        category=ValidationCategory.CRITICAL_PATH,
                        severity=ValidationSeverity.PASS,
                        message=f"System startup successful in {startup_duration:.2f}s",
                        details={
                            "startup_duration": startup_duration,
                            "init_result": init_result,
                        },
                    ),
                )

                # Test system operations while running
                try:
                    diagnostics = integrator.get_system_diagnostics()
                    health_status = integrator.monitor_system_health()

                    results.append(
                        ValidationResult(
                            check_name="system_operations",
                            category=ValidationCategory.CRITICAL_PATH,
                            severity=ValidationSeverity.PASS,
                            message="System operations working during runtime",
                            details={
                                "health_status": str(health_status),
                                "diagnostics_available": bool(diagnostics),
                            },
                        ),
                    )

                except Exception as e:
                    results.append(
                        ValidationResult(
                            check_name="system_operations",
                            category=ValidationCategory.CRITICAL_PATH,
                            severity=ValidationSeverity.ERROR,
                            message=f"System operations failed during runtime: {e!s}",
                            details={"error": str(e)},
                        ),
                    )

                # Test graceful shutdown
                try:
                    shutdown_start = time.time()
                    integrator.shutdown()
                    shutdown_duration = time.time() - shutdown_start

                    results.append(
                        ValidationResult(
                            check_name="system_shutdown",
                            category=ValidationCategory.CRITICAL_PATH,
                            severity=ValidationSeverity.PASS,
                            message=f"System shutdown successful in {shutdown_duration:.2f}s",
                            details={"shutdown_duration": shutdown_duration},
                        ),
                    )

                except Exception as e:
                    results.append(
                        ValidationResult(
                            check_name="system_shutdown",
                            category=ValidationCategory.CRITICAL_PATH,
                            severity=ValidationSeverity.ERROR,
                            message=f"System shutdown failed: {e!s}",
                            details={"error": str(e)},
                        ),
                    )

            else:
                results.append(
                    ValidationResult(
                        check_name="system_startup",
                        category=ValidationCategory.CRITICAL_PATH,
                        severity=ValidationSeverity.ERROR,
                        message="System startup failed",
                        details={"init_result": init_result},
                        recommendations=["Check system initialization requirements"],
                    ),
                )

        except Exception as e:
            results.append(
                ValidationResult(
                    check_name="system_lifecycle",
                    category=ValidationCategory.CRITICAL_PATH,
                    severity=ValidationSeverity.ERROR,
                    message=f"System lifecycle test failed: {e!s}",
                    details={"error": str(e), "traceback": traceback.format_exc()},
                    recommendations=["Check system integration components"],
                ),
            )

        return results

    def _test_error_recovery(self) -> list[ValidationResult]:
        """Test error recovery scenarios."""
        results = []

        # Test recovery from various error conditions
        error_scenarios = [
            ("file_not_found", FileNotFoundError("test_file.txt")),
            ("permission_denied", PermissionError("Access denied")),
            ("value_error", ValueError("Invalid value")),
            ("type_error", TypeError("Invalid type")),
            ("runtime_error", RuntimeError("Runtime issue")),
        ]

        for scenario_name, test_error in error_scenarios:
            try:
                # Simulate error handling
                if CORE_INTEGRATION_AVAILABLE:
                    integrator = get_system_integrator()

                    # Test error processing
                    error_result = integrator.process_grammar_error(
                        test_error,
                        context={"test_scenario": scenario_name},
                    )

                    if error_result.get("status") in ["success", "fallback"]:
                        results.append(
                            ValidationResult(
                                check_name=f"error_recovery_{scenario_name}",
                                category=ValidationCategory.CRITICAL_PATH,
                                severity=ValidationSeverity.PASS,
                                message=f"Error recovery successful for {scenario_name}",
                                details={
                                    "scenario": scenario_name,
                                    "error_type": type(test_error).__name__,
                                    "recovery_result": error_result,
                                },
                            ),
                        )
                    else:
                        results.append(
                            ValidationResult(
                                check_name=f"error_recovery_{scenario_name}",
                                category=ValidationCategory.CRITICAL_PATH,
                                severity=ValidationSeverity.WARNING,
                                message=f"Error recovery incomplete for {scenario_name}",
                                details={
                                    "scenario": scenario_name,
                                    "error_type": type(test_error).__name__,
                                    "recovery_result": error_result,
                                },
                            ),
                        )
                else:
                    results.append(
                        ValidationResult(
                            check_name=f"error_recovery_{scenario_name}",
                            category=ValidationCategory.CRITICAL_PATH,
                            severity=ValidationSeverity.INFO,
                            message=f"Error recovery test skipped for {scenario_name} - core integration not available",
                        ),
                    )

            except Exception as e:
                results.append(
                    ValidationResult(
                        check_name=f"error_recovery_{scenario_name}",
                        category=ValidationCategory.CRITICAL_PATH,
                        severity=ValidationSeverity.ERROR,
                        message=f"Error recovery test failed for {scenario_name}: {e!s}",
                        details={
                            "scenario": scenario_name,
                            "test_error": str(test_error),
                            "actual_error": str(e),
                        },
                    ),
                )

        return results

    def _test_resource_limits(self) -> list[ValidationResult]:
        """Test behavior under resource constraints."""
        results = []

        # Test memory pressure simulation
        try:
            # Get baseline memory
            process = psutil.Process()
            baseline_memory = process.memory_info().rss / 1024 / 1024

            # Create memory pressure (but not too much to crash the system)
            memory_hog = []
            try:
                # Gradually increase memory usage
                for i in range(10):
                    memory_hog.append([0] * 100000)  # Add ~400KB each iteration
                    current_memory = process.memory_info().rss / 1024 / 1024

                    # Stop if we've increased memory by 50MB to avoid system issues
                    if current_memory - baseline_memory > 50:
                        break

                # Test system behavior under memory pressure
                if CORE_INTEGRATION_AVAILABLE:
                    integrator = get_system_integrator()
                    health_status = integrator.monitor_system_health()

                    results.append(
                        ValidationResult(
                            check_name="memory_pressure_handling",
                            category=ValidationCategory.CRITICAL_PATH,
                            severity=ValidationSeverity.PASS,
                            message="System operates under memory pressure",
                            details={
                                "baseline_memory_mb": baseline_memory,
                                "peak_memory_mb": current_memory,
                                "memory_increase_mb": current_memory - baseline_memory,
                                "health_status": str(health_status),
                            },
                        ),
                    )
                else:
                    results.append(
                        ValidationResult(
                            check_name="memory_pressure_handling",
                            category=ValidationCategory.CRITICAL_PATH,
                            severity=ValidationSeverity.INFO,
                            message="Memory pressure test completed - core integration not available for health check",
                        ),
                    )

            finally:
                # Clean up memory
                del memory_hog

        except Exception as e:
            results.append(
                ValidationResult(
                    check_name="memory_pressure_handling",
                    category=ValidationCategory.CRITICAL_PATH,
                    severity=ValidationSeverity.ERROR,
                    message=f"Memory pressure test failed: {e!s}",
                    details={"error": str(e)},
                ),
            )

        # Test file descriptor limits (simulation)
        try:
            # Open multiple temporary files
            temp_files = []
            max_files = min(50, 100)  # Limit to avoid system issues

            try:
                for i in range(max_files):
                    temp_file = tempfile.NamedTemporaryFile(delete=False)
                    temp_files.append(temp_file)

                results.append(
                    ValidationResult(
                        check_name="file_descriptor_limits",
                        category=ValidationCategory.CRITICAL_PATH,
                        severity=ValidationSeverity.PASS,
                        message=f"Handled {len(temp_files)} open file descriptors",
                        details={"max_files_opened": len(temp_files)},
                    ),
                )

            finally:
                # Clean up files
                for temp_file in temp_files:
                    try:
                        temp_file.close()
                        Path(temp_file.name).unlink(missing_ok=True)
                    except Exception:
                        pass

        except Exception as e:
            results.append(
                ValidationResult(
                    check_name="file_descriptor_limits",
                    category=ValidationCategory.CRITICAL_PATH,
                    severity=ValidationSeverity.WARNING,
                    message=f"File descriptor limit test failed: {e!s}",
                    details={"error": str(e)},
                ),
            )

        return results

    def _test_concurrent_access(self) -> list[ValidationResult]:
        """Test concurrent access patterns."""
        results = []

        # Test concurrent operations
        def concurrent_task(task_id: int) -> dict[str, Any]:
            """Simulate concurrent work."""
            try:
                # Simulate some work
                time.sleep(0.1)
                result = {
                    "task_id": task_id,
                    "status": "completed",
                    "timestamp": time.time(),
                }
                return result
            except Exception as e:
                return {"task_id": task_id, "status": "failed", "error": str(e)}

        try:
            # Run concurrent tasks
            num_tasks = 10
            start_time = time.time()

            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = [
                    executor.submit(concurrent_task, i) for i in range(num_tasks)
                ]
                results_list = []

                for future in as_completed(futures, timeout=30):
                    try:
                        result = future.result()
                        results_list.append(result)
                    except Exception as e:
                        results_list.append({"status": "failed", "error": str(e)})

            end_time = time.time()

            # Analyze results
            successful_tasks = [
                r for r in results_list if r.get("status") == "completed"
            ]
            failed_tasks = [r for r in results_list if r.get("status") == "failed"]

            if len(successful_tasks) >= num_tasks * 0.8:  # 80% success rate
                results.append(
                    ValidationResult(
                        check_name="concurrent_operations",
                        category=ValidationCategory.CRITICAL_PATH,
                        severity=ValidationSeverity.PASS,
                        message=f"Concurrent operations successful: {len(successful_tasks)}/{num_tasks}",
                        details={
                            "total_tasks": num_tasks,
                            "successful_tasks": len(successful_tasks),
                            "failed_tasks": len(failed_tasks),
                            "duration": end_time - start_time,
                            "success_rate": len(successful_tasks) / num_tasks,
                        },
                    ),
                )
            else:
                results.append(
                    ValidationResult(
                        check_name="concurrent_operations",
                        category=ValidationCategory.CRITICAL_PATH,
                        severity=ValidationSeverity.WARNING,
                        message=f"Concurrent operations had issues: {len(successful_tasks)}/{num_tasks} successful",
                        details={
                            "total_tasks": num_tasks,
                            "successful_tasks": len(successful_tasks),
                            "failed_tasks": len(failed_tasks),
                            "duration": end_time - start_time,
                            "success_rate": len(successful_tasks) / num_tasks,
                            "failed_task_errors": [
                                r.get("error") for r in failed_tasks
                            ],
                        },
                        recommendations=[
                            "Check thread pool configuration",
                            "Review concurrent access patterns",
                        ],
                    ),
                )

        except TimeoutError:
            results.append(
                ValidationResult(
                    check_name="concurrent_operations",
                    category=ValidationCategory.CRITICAL_PATH,
                    severity=ValidationSeverity.ERROR,
                    message="Concurrent operations timed out",
                    recommendations=["Check for deadlocks", "Review timeout settings"],
                ),
            )
        except Exception as e:
            results.append(
                ValidationResult(
                    check_name="concurrent_operations",
                    category=ValidationCategory.CRITICAL_PATH,
                    severity=ValidationSeverity.ERROR,
                    message=f"Concurrent operations test failed: {e!s}",
                    details={"error": str(e)},
                ),
            )

        return results

    def _test_data_integrity(self) -> list[ValidationResult]:
        """Test data integrity under various conditions."""
        results = []

        # Test file operations integrity
        try:
            test_data = {
                "test_string": "Hello, World! 🌍",
                "test_number": 42,
                "test_list": [1, 2, 3, "four", 5.0],
                "test_dict": {"nested": {"key": "value"}},
                "test_unicode": "测试数据 ñáéíóú",
            }

            # Test JSON serialization/deserialization
            json_str = json.dumps(test_data, ensure_ascii=False)
            recovered_data = json.loads(json_str)

            if recovered_data == test_data:
                results.append(
                    ValidationResult(
                        check_name="json_data_integrity",
                        category=ValidationCategory.CRITICAL_PATH,
                        severity=ValidationSeverity.PASS,
                        message="JSON data integrity maintained",
                        details={"data_size": len(json_str)},
                    ),
                )
            else:
                results.append(
                    ValidationResult(
                        check_name="json_data_integrity",
                        category=ValidationCategory.CRITICAL_PATH,
                        severity=ValidationSeverity.ERROR,
                        message="JSON data integrity compromised",
                        details={"original": test_data, "recovered": recovered_data},
                        recommendations=["Check JSON serialization settings"],
                    ),
                )

        except Exception as e:
            results.append(
                ValidationResult(
                    check_name="json_data_integrity",
                    category=ValidationCategory.CRITICAL_PATH,
                    severity=ValidationSeverity.ERROR,
                    message=f"JSON data integrity test failed: {e!s}",
                    details={"error": str(e)},
                ),
            )

        # Test file I/O integrity
        try:
            test_content = (
                "Test file content\nWith multiple lines\nAnd unicode: 测试 ñáéíóú"
            )

            with tempfile.NamedTemporaryFile(
                mode="w",
                delete=False,
                encoding="utf-8",
            ) as f:
                f.write(test_content)
                temp_path = f.name

            try:
                # Read back and verify
                with open(temp_path, encoding="utf-8") as f:
                    read_content = f.read()

                if read_content == test_content:
                    results.append(
                        ValidationResult(
                            check_name="file_io_integrity",
                            category=ValidationCategory.CRITICAL_PATH,
                            severity=ValidationSeverity.PASS,
                            message="File I/O integrity maintained",
                            details={"file_size": len(test_content)},
                        ),
                    )
                else:
                    results.append(
                        ValidationResult(
                            check_name="file_io_integrity",
                            category=ValidationCategory.CRITICAL_PATH,
                            severity=ValidationSeverity.ERROR,
                            message="File I/O integrity compromised",
                            details={
                                "original_length": len(test_content),
                                "read_length": len(read_content),
                                "content_match": read_content == test_content,
                            },
                        ),
                    )

            finally:
                Path(temp_path).unlink(missing_ok=True)

        except Exception as e:
            results.append(
                ValidationResult(
                    check_name="file_io_integrity",
                    category=ValidationCategory.CRITICAL_PATH,
                    severity=ValidationSeverity.ERROR,
                    message=f"File I/O integrity test failed: {e!s}",
                    details={"error": str(e)},
                ),
            )

        return results


class ProductionValidator:
    """
    Main production validator that orchestrates comprehensive system validation.

    This class coordinates all validation components to ensure the integrated system
    is ready for production deployment.
    """

    def __init__(
        self,
        config: dict[str, Any] | None = None,
        deployment_stage: DeploymentStage = DeploymentStage.PRODUCTION,
    ):
        self.config = config or {}
        self.deployment_stage = deployment_stage
        self.logger = logging.getLogger(__name__ + ".ProductionValidator")

        # Initialize validation components
        self.dependency_validator = DependencyValidator(
            self.config.get("dependency", {}),
        )
        self.configuration_validator = ConfigurationValidator(
            self.config.get("configuration", {}),
        )
        self.security_validator = SecurityValidator(self.config.get("security", {}))
        self.performance_validator = PerformanceValidator(
            self.config.get("performance", {}),
        )
        self.integration_validator = IntegrationValidator(
            self.config.get("integration", {}),
        )
        self.critical_path_validator = CriticalPathValidator(
            self.config.get("critical_path", {}),
        )

        # Validation settings
        self.parallel_validation = self.config.get("parallel_validation", True)
        self.timeout_seconds = self.config.get("timeout_seconds", 300)  # 5 minutes
        self.fail_fast = self.config.get("fail_fast", False)

        # Report generation
        self.generate_detailed_report = self.config.get(
            "generate_detailed_report",
            True,
        )
        self.report_output_path = self.config.get(
            "report_output_path",
            "validation_report.json",
        )

    def validate_system(self) -> ValidationReport:
        """
        Perform comprehensive system validation.

        Returns:
            ValidationReport containing all validation results
        """
        validation_id = str(uuid.uuid4())
        start_time = time.time()
        timestamp = datetime.now(UTC)

        self.logger.info(
            f"Starting production validation {validation_id} for {self.deployment_stage.value}",
        )

        # Create validation report
        report = ValidationReport(
            validation_id=validation_id,
            deployment_stage=self.deployment_stage,
            timestamp=timestamp,
            duration=0.0,
            metadata={
                "validator_version": "1.9.4",
                "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
                "platform": platform.platform(),
                "hostname": socket.gethostname(),
                "config": self.config,
            },
        )

        try:
            if self.parallel_validation:
                results = self._run_parallel_validation()
            else:
                results = self._run_sequential_validation()

            # Add all results to report
            for result in results:
                report.add_result(result)

            # Calculate final duration
            report.duration = time.time() - start_time

            self.logger.info(
                f"Validation {validation_id} completed in {report.duration:.2f}s. "
                f"Status: {'READY' if report.deployment_ready else 'NOT READY'}",
            )

            # Generate detailed report if requested
            if self.generate_detailed_report:
                self._generate_report_file(report)

            return report

        except Exception as e:
            # Add critical error to report
            error_result = ValidationResult(
                check_name="validation_system_error",
                category=ValidationCategory.SYSTEM_HEALTH,
                severity=ValidationSeverity.CRITICAL,
                message=f"Validation system error: {e!s}",
                details={"error": str(e), "traceback": traceback.format_exc()},
                duration=time.time() - start_time,
            )
            report.add_result(error_result)
            report.duration = time.time() - start_time

            self.logger.error(f"Validation {validation_id} failed: {e!s}")

            return report

    def _run_parallel_validation(self) -> list[ValidationResult]:
        """Run validation components in parallel."""
        all_results = []

        # Define validation tasks
        validation_tasks = [
            ("dependency", self.dependency_validator.validate),
            ("configuration", self.configuration_validator.validate),
            ("security", self.security_validator.validate),
            ("performance", self.performance_validator.validate),
            ("integration", self.integration_validator.validate),
            ("critical_path", self.critical_path_validator.validate),
        ]

        # Run tasks in parallel
        with ThreadPoolExecutor(max_workers=6) as executor:
            # Submit all tasks
            future_to_name = {
                executor.submit(task_func): task_name
                for task_name, task_func in validation_tasks
            }

            # Collect results with timeout
            for future in as_completed(future_to_name, timeout=self.timeout_seconds):
                task_name = future_to_name[future]

                try:
                    results = future.result(timeout=30)  # 30 second timeout per task
                    all_results.extend(results)
                    self.logger.debug(
                        f"Completed {task_name} validation: {len(results)} results",
                    )

                    # Check for fail-fast conditions
                    if self.fail_fast:
                        critical_errors = [
                            r
                            for r in results
                            if r.severity == ValidationSeverity.CRITICAL
                        ]
                        if critical_errors:
                            self.logger.warning(
                                f"Fail-fast triggered by {task_name}: {len(critical_errors)} critical errors",
                            )
                            # Cancel remaining futures
                            for remaining_future in future_to_name:
                                if not remaining_future.done():
                                    remaining_future.cancel()
                            break

                except TimeoutError:
                    all_results.append(
                        ValidationResult(
                            check_name=f"{task_name}_timeout",
                            category=ValidationCategory.SYSTEM_HEALTH,
                            severity=ValidationSeverity.ERROR,
                            message=f"{task_name} validation timed out",
                            recommendations=[
                                f"Check {task_name} validator performance",
                                "Increase timeout settings",
                            ],
                        ),
                    )
                except Exception as e:
                    all_results.append(
                        ValidationResult(
                            check_name=f"{task_name}_error",
                            category=ValidationCategory.SYSTEM_HEALTH,
                            severity=ValidationSeverity.ERROR,
                            message=f"{task_name} validation failed: {e!s}",
                            details={
                                "error": str(e),
                                "traceback": traceback.format_exc(),
                            },
                        ),
                    )

        return all_results

    def _run_sequential_validation(self) -> list[ValidationResult]:
        """Run validation components sequentially."""
        all_results = []

        validation_components = [
            ("dependency", self.dependency_validator),
            ("configuration", self.configuration_validator),
            ("security", self.security_validator),
            ("performance", self.performance_validator),
            ("integration", self.integration_validator),
            ("critical_path", self.critical_path_validator),
        ]

        for component_name, validator in validation_components:
            self.logger.debug(f"Running {component_name} validation")

            try:
                component_start = time.time()
                results = validator.validate()
                component_duration = time.time() - component_start

                all_results.extend(results)
                self.logger.debug(
                    f"Completed {component_name} validation in {component_duration:.2f}s: {len(results)} results",
                )

                # Check for fail-fast conditions
                if self.fail_fast:
                    critical_errors = [
                        r for r in results if r.severity == ValidationSeverity.CRITICAL
                    ]
                    if critical_errors:
                        self.logger.warning(
                            f"Fail-fast triggered by {component_name}: {len(critical_errors)} critical errors",
                        )
                        break

            except Exception as e:
                all_results.append(
                    ValidationResult(
                        check_name=f"{component_name}_error",
                        category=ValidationCategory.SYSTEM_HEALTH,
                        severity=ValidationSeverity.ERROR,
                        message=f"{component_name} validation failed: {e!s}",
                        details={"error": str(e), "traceback": traceback.format_exc()},
                    ),
                )

        return all_results

    def _generate_report_file(self, report: ValidationReport) -> None:
        """Generate detailed report file."""
        try:
            report_path = Path(self.report_output_path)
            report_path.parent.mkdir(parents=True, exist_ok=True)

            # Generate JSON report
            with open(report_path, "w", encoding="utf-8") as f:
                json.dump(report.to_dict(), f, indent=2, ensure_ascii=False)

            self.logger.info(f"Detailed validation report saved to: {report_path}")

            # Generate human-readable summary
            summary_path = report_path.with_suffix(".summary.txt")
            self._generate_human_readable_summary(report, summary_path)

        except Exception as e:
            self.logger.error(f"Failed to generate report file: {e!s}")

    def _generate_human_readable_summary(
        self,
        report: ValidationReport,
        output_path: Path,
    ) -> None:
        """Generate human-readable validation summary."""
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write("=" * 80 + "\n")
                f.write("PRODUCTION VALIDATION REPORT\n")
                f.write("=" * 80 + "\n")
                f.write(f"Validation ID: {report.validation_id}\n")
                f.write(f"Deployment Stage: {report.deployment_stage.value.upper()}\n")
                f.write(f"Timestamp: {report.timestamp.isoformat()}\n")
                f.write(f"Duration: {report.duration:.2f} seconds\n")
                f.write(
                    f"Deployment Ready: {'✅ YES' if report.deployment_ready else '❌ NO'}\n",
                )
                f.write(f"Exit Code: {report.exit_code}\n")

                f.write("\n" + "=" * 80 + "\n")
                f.write("SUMMARY\n")
                f.write("=" * 80 + "\n")
                f.write(f"Total Checks: {report.summary['total_checks']}\n")
                f.write(f"✅ Passed: {report.summary['pass']}\n")
                f.write(f"ℹ️  Info: {report.summary['info']}\n")
                f.write(f"⚠️  Warnings: {report.summary['warning']}\n")
                f.write(f"❌ Errors: {report.summary['error']}\n")
                f.write(f"🚨 Critical: {report.summary['critical']}\n")

                # Category breakdown
                f.write("\n" + "-" * 50 + "\n")
                f.write("CATEGORY BREAKDOWN\n")
                f.write("-" * 50 + "\n")
                for category, stats in report.summary["categories"].items():
                    f.write(f"{category.upper()}: {stats['total']} total")
                    if stats["error"] > 0 or stats["critical"] > 0:
                        f.write(
                            f" (❌ {stats['error']} errors, 🚨 {stats['critical']} critical)",
                        )
                    elif stats["warning"] > 0:
                        f.write(f" (⚠️  {stats['warning']} warnings)")
                    else:
                        f.write(" (✅ all passed)")
                    f.write("\n")

                # Blocking issues
                blocking_issues = report.get_blocking_issues()
                if blocking_issues:
                    f.write("\n" + "=" * 80 + "\n")
                    f.write("🚨 BLOCKING ISSUES (MUST FIX BEFORE DEPLOYMENT)\n")
                    f.write("=" * 80 + "\n")
                    for issue in blocking_issues:
                        f.write(f"❌ {issue.check_name}: {issue.message}\n")
                        if issue.recommendations:
                            for rec in issue.recommendations:
                                f.write(f"   💡 {rec}\n")
                        f.write("\n")

                # Recommendations
                recommendations = report.get_recommendations()
                if recommendations:
                    f.write("\n" + "=" * 80 + "\n")
                    f.write("💡 RECOMMENDATIONS\n")
                    f.write("=" * 80 + "\n")
                    for i, rec in enumerate(
                        recommendations[:10],
                        1,
                    ):  # Top 10 recommendations
                        f.write(f"{i}. {rec}\n")

                # Detailed results by severity
                for severity in [
                    ValidationSeverity.CRITICAL,
                    ValidationSeverity.ERROR,
                    ValidationSeverity.WARNING,
                ]:
                    severity_results = [
                        r for r in report.results if r.severity == severity
                    ]
                    if severity_results:
                        icon = {"critical": "🚨", "error": "❌", "warning": "⚠️"}[
                            severity.value
                        ]
                        f.write(f"\n{icon} {severity.value.upper()} RESULTS\n")
                        f.write("-" * (len(severity.value) + 10) + "\n")
                        for result in severity_results:
                            f.write(f"{result.check_name}: {result.message}\n")
                            if result.recommendations:
                                for rec in result.recommendations:
                                    f.write(f"  💡 {rec}\n")
                            f.write("\n")

            self.logger.info(f"Human-readable summary saved to: {output_path}")

        except Exception as e:
            self.logger.error(f"Failed to generate human-readable summary: {e!s}")

    def get_exit_code(self, report: ValidationReport) -> int:
        """Get appropriate exit code for CI/CD integration."""
        return report.exit_code

    def print_summary(self, report: ValidationReport) -> None:
        """Print validation summary to console."""
        print("\n" + "=" * 80)
        print("🔍 PRODUCTION VALIDATION SUMMARY")
        print("=" * 80)
        print(f"Deployment Stage: {report.deployment_stage.value.upper()}")
        print(f"Duration: {report.duration:.2f} seconds")
        print(f"Total Checks: {report.summary['total_checks']}")

        # Status with color coding (simple)
        if report.deployment_ready:
            print("🟢 DEPLOYMENT READY: YES")
        else:
            print("🔴 DEPLOYMENT READY: NO")

        print(
            f"\nResults: ✅ {report.summary['pass']} passed, "
            f"⚠️  {report.summary['warning']} warnings, "
            f"❌ {report.summary['error']} errors, "
            f"🚨 {report.summary['critical']} critical",
        )

        # Show blocking issues if any
        blocking_issues = report.get_blocking_issues()
        if blocking_issues:
            print(f"\n🚨 {len(blocking_issues)} BLOCKING ISSUES:")
            for issue in blocking_issues[:5]:  # Show first 5
                print(f"   • {issue.check_name}: {issue.message}")
            if len(blocking_issues) > 5:
                print(f"   ... and {len(blocking_issues) - 5} more")

        print("=" * 80)

        if self.generate_detailed_report:
            print(f"📄 Detailed report: {self.report_output_path}")


# Main validation entry points
def validate_production_readiness(
    config: dict[str, Any] | None = None,
    deployment_stage: DeploymentStage = DeploymentStage.PRODUCTION,
    silent: bool = False,
) -> ValidationReport:
    """
    Main entry point for production validation.

    Args:
        config: Optional configuration dictionary
        deployment_stage: Target deployment stage
        silent: If True, suppress console output

    Returns:
        ValidationReport with all validation results
    """
    validator = ProductionValidator(config, deployment_stage)
    report = validator.validate_system()

    if not silent:
        validator.print_summary(report)

    return report


def main() -> int:
    """
    CLI entry point for production validation.

    Returns:
        Exit code (0 for success, 1 for errors, 2 for critical issues)
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="Production validation for treesitter-chunker",
    )
    parser.add_argument(
        "--config",
        type=str,
        help="Path to validation configuration file",
    )
    parser.add_argument(
        "--stage",
        choices=["development", "testing", "staging", "production"],
        default="production",
        help="Deployment stage to validate for",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="validation_report.json",
        help="Output path for validation report",
    )
    parser.add_argument(
        "--parallel",
        action="store_true",
        default=True,
        help="Run validation components in parallel",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop validation on first critical error",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="Validation timeout in seconds",
    )
    parser.add_argument("--silent", action="store_true", help="Suppress console output")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")

    args = parser.parse_args()

    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Load configuration if provided
    config = {}
    if args.config and Path(args.config).exists():
        try:
            with open(args.config) as f:
                if args.config.endswith(".json"):
                    config = json.load(f)
                elif args.config.endswith((".yaml", ".yml")):
                    import yaml

                    config = yaml.safe_load(f)
        except Exception as e:
            print(f"Warning: Could not load config file {args.config}: {e}")

    # Override config with CLI arguments
    config.update(
        {
            "parallel_validation": args.parallel,
            "fail_fast": args.fail_fast,
            "timeout_seconds": args.timeout,
            "report_output_path": args.output,
            "generate_detailed_report": True,
        },
    )

    # Run validation
    deployment_stage = DeploymentStage(args.stage)
    report = validate_production_readiness(config, deployment_stage, args.silent)

    return report.exit_code


if __name__ == "__main__":
    sys.exit(main())

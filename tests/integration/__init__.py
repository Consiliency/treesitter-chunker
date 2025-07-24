"""Integration test interfaces for cross-module testing.

This package provides shared interfaces and utilities for Phase 7 integration tests.
All integration tests should use these interfaces to ensure consistency across
parallel worktree development.
"""

from .coordinator import IntegrationCoordinator, TestResult, TestScenario
from .fixtures import *
from .interfaces import ConfigChangeObserver, ErrorPropagationMixin, ResourceTracker

__all__ = [
    "ConfigChangeObserver",
    "ErrorPropagationMixin",
    "IntegrationCoordinator",
    "ResourceTracker",
    "TestResult",
    "TestScenario",
]

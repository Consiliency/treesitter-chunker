"""Integration test interfaces for cross-module testing.

This package provides shared interfaces and utilities for Phase 7 integration tests.
All integration tests should use these interfaces to ensure consistency across
parallel worktree development.
"""

from .interfaces import (
    ErrorPropagationMixin,
    ConfigChangeObserver,
    ResourceTracker,
)
from .fixtures import *

__all__ = [
    'ErrorPropagationMixin',
    'ConfigChangeObserver', 
    'ResourceTracker',
]
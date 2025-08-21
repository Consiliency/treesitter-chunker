"""Performance core framework module.

This module provides the foundational infrastructure for all performance
optimization components in Phase 3 of the treesitter-chunker project.

Classes:
    PerformanceMetric: Represents a performance metric with comprehensive data
    PerformanceProfile: Comprehensive performance profile for a system component
    PerformanceManager: Central performance orchestration and management
    MetricsCollector: Real-time performance metrics collection and storage
    OptimizationEngine: Core optimization algorithms and strategies
    PerformanceBudget: Performance budget management and enforcement
    PerformanceUtils: Common performance utilities and helpers
"""

from .performance_framework import (
    MetricsCollector,
    OptimizationEngine,
    PerformanceBudget,
    PerformanceManager,
    PerformanceMetric,
    PerformanceProfile,
    PerformanceUtils,
)

__all__ = [
    "MetricsCollector",
    "OptimizationEngine",
    "PerformanceBudget",
    "PerformanceManager",
    "PerformanceMetric",
    "PerformanceProfile",
    "PerformanceUtils",
]

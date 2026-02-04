"""Hierarchical clustering module for code symbol analysis.

This module provides C4-style architecture inference from codebases
using the Leiden community detection algorithm.
"""

from .engine import ClusteringEngine
from .hierarchy import ClusterNode, HierarchyBuilder
from .metrics import ClusterMetrics, MetricsCalculator
from .weights import EdgeWeightCalculator, EdgeWeightConfig

__all__ = [
    "ClusteringEngine",
    "HierarchyBuilder",
    "ClusterNode",
    "ClusterMetrics",
    "MetricsCalculator",
    "EdgeWeightConfig",
    "EdgeWeightCalculator",
]

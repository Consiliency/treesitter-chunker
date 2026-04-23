"""Boundary IR public API."""

from .adapter import extract_boundary_ir
from .identity import select_node_identity
from .serialization import dumps_boundary_ir
from .semantic import SemanticEdge, SemanticResolver, SemanticResolverContext
from .types import (
    BOUNDARY_CACHE_EXCLUDED_OPTION_FIELDS,
    BOUNDARY_CACHE_KEY_FIELDS,
    BOUNDARY_CACHE_KEY_PREFIX,
    BOUNDARY_CACHE_VERSION,
    BOUNDARY_IR_SCHEMA_VERSION,
    BOUNDARY_IR_SEMANTIC_SCHEMA_VERSION,
    DIAGNOSTIC_SEVERITIES,
    DIAGNOSTIC_STAGES,
    FILE_STATUSES,
    METRIC_KEYS,
    RESOLUTION_MODES,
    RESOLUTION_STATUSES,
    SEMANTIC_EDGE_SOURCES,
    SEMANTIC_RESOLVER_API_VERSION,
    TIMING_KEYS,
    ResolutionMode,
    ResolutionStatus,
    SemanticEdgeSource,
)

__all__ = [
    "BOUNDARY_IR_SCHEMA_VERSION",
    "BOUNDARY_IR_SEMANTIC_SCHEMA_VERSION",
    "BOUNDARY_CACHE_EXCLUDED_OPTION_FIELDS",
    "BOUNDARY_CACHE_KEY_FIELDS",
    "BOUNDARY_CACHE_KEY_PREFIX",
    "BOUNDARY_CACHE_VERSION",
    "DIAGNOSTIC_SEVERITIES",
    "DIAGNOSTIC_STAGES",
    "FILE_STATUSES",
    "METRIC_KEYS",
    "RESOLUTION_MODES",
    "RESOLUTION_STATUSES",
    "ResolutionMode",
    "ResolutionStatus",
    "SEMANTIC_EDGE_SOURCES",
    "SEMANTIC_RESOLVER_API_VERSION",
    "SemanticEdge",
    "SemanticEdgeSource",
    "SemanticResolver",
    "SemanticResolverContext",
    "TIMING_KEYS",
    "dumps_boundary_ir",
    "extract_boundary_ir",
    "select_node_identity",
]

"""Boundary IR public API."""

from .adapter import extract_boundary_ir
from .identity import select_node_identity
from .serialization import dumps_boundary_ir
from .types import (
    BOUNDARY_IR_SCHEMA_VERSION,
    DIAGNOSTIC_SEVERITIES,
    DIAGNOSTIC_STAGES,
    FILE_STATUSES,
    METRIC_KEYS,
    RESOLUTION_MODES,
    RESOLUTION_STATUSES,
    TIMING_KEYS,
    ResolutionMode,
    ResolutionStatus,
)

__all__ = [
    "BOUNDARY_IR_SCHEMA_VERSION",
    "DIAGNOSTIC_SEVERITIES",
    "DIAGNOSTIC_STAGES",
    "FILE_STATUSES",
    "METRIC_KEYS",
    "RESOLUTION_MODES",
    "RESOLUTION_STATUSES",
    "ResolutionMode",
    "ResolutionStatus",
    "TIMING_KEYS",
    "dumps_boundary_ir",
    "extract_boundary_ir",
    "select_node_identity",
]

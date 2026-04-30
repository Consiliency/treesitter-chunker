from typing import get_args

from chunker.boundary import (
    RESOLUTION_MODES,
    RESOLUTION_STATUSES,
    ResolutionMode,
    ResolutionStatus,
)
from chunker.boundary.types import METRIC_KEYS
from chunker.symbol_graph import (
    RESOLUTION_MODES as SYMBOL_GRAPH_RESOLUTION_MODES,
    ResolutionMode as SymbolGraphResolutionMode,
    ResolutionStatus as SymbolGraphResolutionStatus,
)


def test_resolution_status_values_are_exact_and_exported():
    assert get_args(ResolutionStatus) == ("resolved", "ambiguous", "unresolved")
    assert get_args(ResolutionStatus) == RESOLUTION_STATUSES


def test_resolution_mode_values_are_exact_and_exported():
    assert get_args(ResolutionMode) == ("strict", "permissive")
    assert get_args(ResolutionMode) == RESOLUTION_MODES


def test_symbol_graph_resolution_vocabulary_reuses_shared_values():
    assert get_args(SymbolGraphResolutionStatus) == RESOLUTION_STATUSES
    assert get_args(SymbolGraphResolutionMode) == RESOLUTION_MODES
    assert SYMBOL_GRAPH_RESOLUTION_MODES == RESOLUTION_MODES


def test_resolution_counter_names_are_in_metric_keys():
    assert {
        "resolved_edges",
        "ambiguous_edges",
        "unresolved_edges",
    }.issubset(METRIC_KEYS)

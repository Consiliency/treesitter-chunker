from typing import get_args

from chunker.boundary import (
    RESOLUTION_MODES,
    RESOLUTION_STATUSES,
    ResolutionMode,
    ResolutionStatus,
)
from chunker.boundary.types import METRIC_KEYS


def test_resolution_status_values_are_exact_and_exported():
    assert get_args(ResolutionStatus) == ("resolved", "ambiguous", "unresolved")
    assert get_args(ResolutionStatus) == RESOLUTION_STATUSES


def test_resolution_mode_values_are_exact_and_exported():
    assert get_args(ResolutionMode) == ("strict", "permissive")
    assert get_args(ResolutionMode) == RESOLUTION_MODES


def test_resolution_counter_names_are_in_metric_keys():
    assert {
        "resolved_edges",
        "ambiguous_edges",
        "unresolved_edges",
    }.issubset(METRIC_KEYS)

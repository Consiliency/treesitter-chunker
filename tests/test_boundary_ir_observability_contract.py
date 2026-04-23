import inspect

from chunker.boundary import (
    DIAGNOSTIC_SEVERITIES,
    DIAGNOSTIC_STAGES,
    FILE_STATUSES,
    METRIC_KEYS,
    TIMING_KEYS,
    extract_boundary_ir,
)


def test_observability_constants_are_frozen():
    assert TIMING_KEYS == (
        "parse_ms",
        "metadata_normalization_ms",
        "graph_assembly_ms",
        "resolution_ms",
        "serialization_ms",
        "total_ms",
    )
    assert DIAGNOSTIC_STAGES == (
        "discovery",
        "parse",
        "metadata",
        "graph",
        "resolution",
        "serialization",
    )
    assert DIAGNOSTIC_SEVERITIES == ("info", "warning", "error")
    assert FILE_STATUSES == ("parsed", "skipped", "error")
    assert set(METRIC_KEYS) >= {
        "files_processed",
        "files_failed",
        "parse_failures",
        "metadata_failures",
        "graph_failures",
        "serialization_failures",
        "failure_buckets",
    }


def test_extract_boundary_ir_observability_signature_defaults():
    signature = inspect.signature(extract_boundary_ir)

    fail_fast = signature.parameters["fail_fast"]
    include_timings = signature.parameters["include_timings"]

    assert fail_fast.kind is inspect.Parameter.KEYWORD_ONLY
    assert fail_fast.default is False
    assert include_timings.kind is inspect.Parameter.KEYWORD_ONLY
    assert include_timings.default is False

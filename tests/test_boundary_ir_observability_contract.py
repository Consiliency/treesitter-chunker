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
        "semantic",
        "serialization",
    )
    assert DIAGNOSTIC_SEVERITIES == ("info", "warning", "error")
    assert FILE_STATUSES == ("parsed", "skipped", "error")
    assert METRIC_KEYS == (
        "files_total",
        "files_processed",
        "files_parsed",
        "files_skipped",
        "files_failed",
        "nodes_total",
        "edges_total",
        "diagnostics_total",
        "resolved_edges",
        "ambiguous_edges",
        "unresolved_edges",
        "parse_failures",
        "metadata_failures",
        "graph_failures",
        "serialization_failures",
        "failure_buckets",
    )


def test_extract_boundary_ir_observability_signature_defaults():
    signature = inspect.signature(extract_boundary_ir)

    fail_fast = signature.parameters["fail_fast"]
    include_timings = signature.parameters["include_timings"]

    assert fail_fast.kind is inspect.Parameter.KEYWORD_ONLY
    assert fail_fast.default is False
    assert include_timings.kind is inspect.Parameter.KEYWORD_ONLY
    assert include_timings.default is False


def test_base_run_options_stay_frozen_without_semantic_extensions(tmp_path):
    (tmp_path / "app.py").write_text(
        "def greet():\n    return 'hi'\n", encoding="utf-8"
    )

    ir = extract_boundary_ir(tmp_path, "python")

    assert ir["run"]["options"] == {
        "include_retrieval_metadata": True,
        "language": "python",
        "resolution_mode": "strict",
        "fail_fast": False,
        "include_timings": False,
    }

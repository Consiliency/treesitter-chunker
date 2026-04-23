from pathlib import Path

from chunker.boundary import TIMING_KEYS, extract_boundary_ir


def test_default_timings_are_present_and_null(tmp_path: Path):
    (tmp_path / "app.py").write_text(
        "def greet():\n    return 'hi'\n", encoding="utf-8"
    )

    ir = extract_boundary_ir(tmp_path, "python")

    assert set(ir["run"]["timings"]) == set(TIMING_KEYS)
    assert all(value is None for value in ir["run"]["timings"].values())
    assert ir["run"]["options"]["include_timings"] is False


def test_include_timings_emits_nonnegative_numbers(tmp_path: Path):
    (tmp_path / "app.py").write_text(
        "def greet():\n    return 'hi'\n", encoding="utf-8"
    )

    ir = extract_boundary_ir(tmp_path, "python", include_timings=True)

    assert ir["run"]["options"]["include_timings"] is True
    assert set(ir["run"]["timings"]) == set(TIMING_KEYS)
    assert all(
        isinstance(value, int | float) and value >= 0
        for value in ir["run"]["timings"].values()
    )


def test_observability_metrics_match_output_counts(tmp_path: Path):
    (tmp_path / "app.py").write_text(
        "def helper():\n    return 'hi'\n\ndef greet():\n    return helper()\n",
        encoding="utf-8",
    )

    ir = extract_boundary_ir(tmp_path, "python")
    metrics = ir["metrics"]

    assert metrics["files_processed"] == len(ir["files"])
    assert metrics["files_failed"] == 0
    assert metrics["parse_failures"] == 0
    assert metrics["metadata_failures"] == 0
    assert metrics["graph_failures"] == 0
    assert metrics["serialization_failures"] == 0
    assert metrics["failure_buckets"] == {}
    assert metrics["nodes_total"] == len(ir["nodes"])
    assert metrics["edges_total"] == len(ir["edges"])
    assert metrics["diagnostics_total"] == len(ir["diagnostics"])

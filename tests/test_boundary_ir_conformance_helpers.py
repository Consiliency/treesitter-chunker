from copy import deepcopy
from pathlib import Path

from tests.boundary_ir_conformance import (
    DIAGNOSTIC_KEYS,
    FIXTURE_ROOT,
    GOLDEN_ROOT,
    P0_BOUNDARY_LANGUAGES,
    assert_required_fields,
    fixture_path,
    normalize_ir_for_golden,
)


def test_p0_boundary_languages_are_exact():
    assert P0_BOUNDARY_LANGUAGES == ("python", "javascript", "typescript", "go")


def test_fixture_paths_are_repo_relative():
    assert Path("tests/fixtures/boundary_ir/repos") == FIXTURE_ROOT
    assert Path("tests/fixtures/boundary_ir/golden") == GOLDEN_ROOT
    for language in P0_BOUNDARY_LANGUAGES:
        path = fixture_path(language)
        assert not path.is_absolute()
        assert path == FIXTURE_ROOT / language


def test_normalize_ir_for_golden_changes_only_tool_version():
    ir = {
        "run": {
            "tool_version": "1.2.3",
            "created_at": None,
            "options": {"resolution_mode": "strict"},
        },
        "files": [{"path": "service.py"}],
    }
    original = deepcopy(ir)

    normalized = normalize_ir_for_golden(ir)

    assert ir == original
    assert normalized["run"]["tool_version"] == "<tool-version>"
    normalized["run"]["tool_version"] = "1.2.3"
    assert normalized == original


def test_assert_required_fields_accepts_diagnostic_record_shape():
    diagnostic = dict.fromkeys(DIAGNOSTIC_KEYS)
    diagnostic.update(
        {
            "id": "diagnostic:example",
            "severity": "error",
            "code": "boundary.example",
            "message": "example",
            "path": None,
            "location": None,
            "stage": "graph",
            "details": {},
        }
    )
    ir = {
        "schema_version": "1.0",
        "source": {"kind": "repository", "path": "tests/fixtures/example"},
        "files": [],
        "nodes": [],
        "edges": [],
        "diagnostics": [diagnostic],
        "metrics": {
            "files_total": 0,
            "files_processed": 0,
            "files_parsed": 0,
            "files_skipped": 0,
            "files_failed": 0,
            "nodes_total": 0,
            "edges_total": 0,
            "diagnostics_total": 1,
            "resolved_edges": 0,
            "ambiguous_edges": 0,
            "unresolved_edges": 0,
            "parse_failures": 0,
            "metadata_failures": 0,
            "graph_failures": 0,
            "serialization_failures": 0,
            "failure_buckets": {},
        },
        "run": {
            "tool": "treesitter-chunker",
            "tool_version": None,
            "root": "tests/fixtures/example",
            "created_at": None,
            "canonical": True,
            "options": {
                "include_retrieval_metadata": True,
                "language": "python",
                "resolution_mode": "strict",
                "fail_fast": False,
                "include_timings": True,
            },
            "timings": {
                "parse_ms": 0.0,
                "metadata_normalization_ms": 0.0,
                "graph_assembly_ms": 0.0,
                "resolution_ms": 0.0,
                "serialization_ms": 0.0,
                "total_ms": 0.0,
            },
        },
    }

    assert_required_fields(ir)

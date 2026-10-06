"""Validate emitted Boundary IR against the published JSON Schema.

The schema (``chunker/boundary/boundary_ir.schema.json``) is the machine-readable
contract ``spec`` and other consumers use to detect drift. These tests keep it
honest: the schema MUST validate the real emitter output (a freshly extracted IR
and the committed golden snapshots), not a hand-guessed shape. If the emitter
changes the document shape, either the change is intentional and the schema is
updated in the same commit, or this test fails and catches the drift.
"""

from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path

import jsonschema
import pytest

from chunker.boundary import extract_boundary_ir
from tests.boundary_ir_conformance import (
    GOLDEN_ROOT,
    P0_BOUNDARY_LANGUAGES,
    fixture_path,
)

SCHEMA_PATH = (
    Path(__file__).resolve().parent.parent
    / "chunker"
    / "boundary"
    / "boundary_ir.schema.json"
)


def _load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _validator() -> jsonschema.Draft202012Validator:
    schema = _load_schema()
    jsonschema.Draft202012Validator.check_schema(schema)
    return jsonschema.Draft202012Validator(schema)


def test_schema_is_a_valid_json_schema() -> None:
    """The published schema is itself a well-formed Draft 2020-12 schema."""
    schema = _load_schema()
    jsonschema.Draft202012Validator.check_schema(schema)
    assert schema["$schema"].endswith("2020-12/schema")


@pytest.mark.parametrize("language", P0_BOUNDARY_LANGUAGES)
def test_golden_snapshot_matches_schema(language: str) -> None:
    """Every committed golden snapshot validates against the schema."""
    golden_path = GOLDEN_ROOT / f"{language}.json"
    assert golden_path.exists(), f"Missing golden snapshot for {language}"
    data = json.loads(golden_path.read_text(encoding="utf-8"))
    errors = sorted(_validator().iter_errors(data), key=lambda e: list(e.path))
    assert not errors, "\n".join(f"{list(e.path)}: {e.message}" for e in errors[:10])


@pytest.mark.parametrize("language", P0_BOUNDARY_LANGUAGES)
def test_freshly_emitted_ir_matches_schema(language: str) -> None:
    """The live emitter output validates against the schema (no drift)."""
    ir = extract_boundary_ir(fixture_path(language), language, canonical=True)
    errors = sorted(_validator().iter_errors(ir), key=lambda e: list(e.path))
    assert not errors, "\n".join(f"{list(e.path)}: {e.message}" for e in errors[:10])


def test_emitted_ir_with_timings_matches_schema() -> None:
    """Populated run.timings (include_timings=True) still validates."""
    ir = extract_boundary_ir(
        fixture_path("python"),
        "python",
        canonical=True,
        include_timings=True,
    )
    errors = sorted(_validator().iter_errors(ir), key=lambda e: list(e.path))
    assert not errors, "\n".join(f"{list(e.path)}: {e.message}" for e in errors[:10])


@pytest.fixture
def actual_boundary_records(tmp_path: Path) -> tuple[dict, dict]:
    parsed = extract_boundary_ir(fixture_path("python"), "python", canonical=True)
    assert parsed["nodes"] and parsed["files"][0]["status"] == "parsed"
    unmapped = tmp_path / "service.unmapped"
    unmapped.write_bytes((fixture_path("python") / "app/service.py").read_bytes())
    skipped = extract_boundary_ir(unmapped, canonical=True)
    return parsed, skipped


def test_actual_skipped_unknown_metadata_matches_schema(
    actual_boundary_records: tuple[dict, dict],
) -> None:
    parsed, skipped = actual_boundary_records
    _validator().validate(parsed)
    assert skipped["files"][0]["status"] == "skipped"
    assert skipped["files"][0]["language"] is None
    assert skipped["files"][0]["parser"] is None
    assert skipped["nodes"] == []
    assert skipped["metrics"]["parse_failures"] == 0
    _validator().validate(skipped)


@pytest.mark.parametrize("status", ["parsed", "error"])
@pytest.mark.parametrize("field", ["language", "parser"])
def test_parsed_and_error_metadata_reject_null(
    actual_boundary_records: tuple[dict, dict], status: str, field: str
) -> None:
    invalid = deepcopy(actual_boundary_records[0])
    invalid["files"][0]["status"] = status
    invalid["files"][0][field] = None
    errors = list(_validator().iter_errors(invalid))
    assert any(list(error.path) == ["files", 0, field] for error in errors)


@pytest.mark.parametrize("field", ["language", "parser"])
def test_skipped_metadata_rejects_arbitrary_types(
    actual_boundary_records: tuple[dict, dict], field: str
) -> None:
    invalid = deepcopy(actual_boundary_records[1])
    invalid["files"][0][field] = 42
    errors = list(_validator().iter_errors(invalid))
    assert any(list(error.path) == ["files", 0, field] for error in errors)


def test_actual_syntax_and_semantic_versions_match_schema() -> None:
    syntax = extract_boundary_ir(fixture_path("python"), "python", canonical=True)
    semantic = extract_boundary_ir(
        fixture_path("python"), "python", canonical=True, semantic_resolvers=()
    )
    assert syntax["nodes"] and semantic["nodes"]
    assert syntax["schema_version"] == "2.0"
    assert semantic["schema_version"] == "2.1"
    _validator().validate(syntax)
    _validator().validate(semantic)


def test_guide_baseline_example_matches_published_schema() -> None:
    guide = (SCHEMA_PATH.parents[2] / "docs/interface-boundary-spec.md").read_text(
        encoding="utf-8"
    )
    match = re.search(r"## Minimal Baseline Example.*?```json\n(.*?)\n```", guide, re.S)
    assert match is not None
    _validator().validate(json.loads(match.group(1)))

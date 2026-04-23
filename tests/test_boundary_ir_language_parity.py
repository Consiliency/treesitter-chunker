import json
from pathlib import Path

import pytest

from tests.boundary_ir_conformance import P0_BOUNDARY_LANGUAGES, extract_fixture_ir

MANIFEST_PATH = Path("tests/fixtures/boundary_ir/manifest.json")


def _manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _node_values(ir: dict, field: str) -> set[str]:
    return {str(node[field]) for node in ir["nodes"] if node.get(field)}


def _metadata_values(ir: dict, field: str) -> set[str]:
    values = set()
    for node in ir["nodes"]:
        metadata = node.get("metadata") or {}
        values.update(str(value) for value in metadata.get(field, []) if str(value))
    return values


def _edge_values(ir: dict, edge_type: str) -> set[str]:
    return {
        str(edge["reference"])
        for edge in ir["edges"]
        if edge["type"] == edge_type and edge.get("reference")
    }


@pytest.mark.parametrize("language", P0_BOUNDARY_LANGUAGES)
def test_language_parity_matches_manifest(language: str):
    manifest = _manifest()[language]
    ir = extract_fixture_ir(language)

    kinds = _node_values(ir, "kind")
    qualified_names = _node_values(ir, "qualified_name")
    signatures = _node_values(ir, "signature")
    imports = _metadata_values(ir, "imports")
    dependencies = _metadata_values(ir, "dependencies")
    calls = _edge_values(ir, "calls")
    statuses = {str(edge["resolution"]) for edge in ir["edges"]}

    assert set(manifest["expected_kinds"]) <= kinds
    assert set(manifest["expected_qualified_names"]) <= qualified_names
    assert all(
        any(expected in signature for signature in signatures)
        for expected in manifest["expected_signatures"]
    )
    assert set(manifest["expected_dependencies"]) <= dependencies
    assert set(manifest["expected_calls"]) <= calls
    assert set(manifest["expected_resolution_statuses"]) <= statuses

    expected_imports = manifest["expected_import_fragments"]
    if expected_imports:
        assert all(
            any(fragment in import_text for import_text in imports)
            for fragment in expected_imports
        )
    else:
        assert manifest.get("expected_import_limitation"), (
            f"{language} has no import metadata expectations and no documented "
            "syntax-only limitation"
        )


@pytest.mark.parametrize("language", P0_BOUNDARY_LANGUAGES)
def test_strict_ambiguous_and_unresolved_edges_preserve_reference_targets(
    language: str,
):
    manifest = _manifest()[language]
    ir = extract_fixture_ir(language)

    for reference in manifest["strict_reference_targets"]:
        matches = [
            edge
            for edge in ir["edges"]
            if edge["reference"] == reference
            and edge["resolution"] in {"ambiguous", "unresolved"}
        ]
        assert matches, f"{language} did not emit strict edge for {reference}"
        for edge in matches:
            assert edge["target"] == reference

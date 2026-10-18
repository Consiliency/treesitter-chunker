from pathlib import Path
from textwrap import dedent

import pytest

from chunker.symbol_graph import (
    assemble_symbol_graph,
    extract_symbol_facts_for_file,
    extract_symbol_graph,
)


def _calls_to(result: dict, reference: str) -> list[dict]:
    return [
        rel
        for rel in result["relationships"]
        if rel["type"] == "calls" and rel["reference"] == reference
    ]


def test_unqualified_duplicate_call_is_ambiguous_with_sorted_candidates(
    tmp_path: Path,
):
    (tmp_path / "alpha.py").write_text(
        "def helper():\n    return 'alpha'\n",
        encoding="utf-8",
    )
    (tmp_path / "beta.py").write_text(
        "def helper():\n    return 'beta'\n",
        encoding="utf-8",
    )
    (tmp_path / "service.py").write_text(
        "def use_helper():\n    return helper()\n",
        encoding="utf-8",
    )

    result = extract_symbol_graph(tmp_path, "python")
    relationships = _calls_to(result, "helper")

    assert len(relationships) == 1
    relationship = relationships[0]
    assert relationship["resolution"] == "ambiguous"
    assert relationship["to"] == "helper"
    assert relationship["is_internal"] is False
    assert relationship["candidates"] == sorted(relationship["candidates"])
    assert len(relationship["candidates"]) == 2
    assert relationship["resolution_mode"] == "permissive"
    assert relationship["provenance"]["source"] == "syntax"


def test_missing_call_is_unresolved_and_preserves_reference(tmp_path: Path):
    (tmp_path / "service.py").write_text(
        "def use_missing():\n    return missing_call()\n",
        encoding="utf-8",
    )

    result = extract_symbol_graph(tmp_path, "python", resolution_mode="strict")
    relationships = _calls_to(result, "missing_call")

    assert len(relationships) == 1
    relationship = relationships[0]
    assert relationship["resolution"] == "unresolved"
    assert relationship["to"] == "missing_call"
    assert relationship["is_internal"] is False
    assert relationship["candidates"] == []
    assert relationship["resolution_mode"] == "strict"


def test_unique_call_remains_resolved_and_legacy_internal(tmp_path: Path):
    source = dedent(
        """\
        def helper():
            return 'ok'

        def use_helper():
            return helper()
        """
    )
    (tmp_path / "service.py").write_text(source, encoding="utf-8")

    result = extract_symbol_graph(tmp_path, "python")
    relationships = _calls_to(result, "helper")

    assert len(relationships) == 1
    relationship = relationships[0]
    assert relationship["resolution"] == "resolved"
    assert relationship["to"] != "helper"
    assert relationship["is_internal"] is True
    assert relationship["candidates"] == [relationship["to"]]


@pytest.mark.parametrize(
    ("language", "extension"), [("javascript", "js"), ("typescript", "ts")]
)
@pytest.mark.parametrize("mode", ["strict", "permissive"])
@pytest.mark.parametrize("reverse", [False, True])
def test_distinct_call_references_share_target_without_collapsing(
    tmp_path: Path, language, extension, mode, reverse
):
    references = ["target", "ns.target", "other.target"]
    if reverse:
        references.reverse()
    raw_calls = references + [references[0]]
    source = tmp_path / f"service.{extension}"
    source.write_text(
        "export function target() { return 1; }\n"
        "export function caller() { "
        + " ".join(f"{reference}();" for reference in raw_calls)
        + " }\n",
        encoding="utf-8",
    )
    facts = extract_symbol_facts_for_file(source, source, language, fail_fast=True)
    caller_id = next(
        symbol_id
        for symbol_id, symbol in facts["symbol_lookup"].items()
        if symbol["name"] == "caller"
    )
    target_id = next(
        symbol_id
        for symbol_id, symbol in facts["symbol_lookup"].items()
        if symbol["name"] == "target"
    )
    caller = next(
        record
        for record in facts["chunk_records"]
        if record["context"]["id"] == caller_id
    )
    assert facts["errors"] == []
    assert caller["calls"] == raw_calls

    result = extract_symbol_graph(
        source, language, resolution_mode=mode, fail_fast=True
    )
    calls = [rel for rel in result["relationships"] if rel["type"] == "calls"]

    assert [
        rel["reference"] for rel in calls
    ] == raw_calls, "distinct call sites were collapsed"
    assert result["errors"] == []
    assert result["metadata"]["total_functions"] == 2
    assert (
        result["metadata"]["total_relationships"] == len(result["relationships"]) == 7
    )
    for rel in calls:
        assert rel["from"] == caller_id
        assert rel["to"] == target_id
        assert rel["type"] == "calls"
        assert rel["line"] == 2
        assert rel["file"] == source.name
        assert rel["is_internal"] is True
        assert rel["resolution"] == "resolved"
        assert rel["candidates"] == [target_id]
        assert rel["resolution_mode"] == mode
        assert rel["provenance"] == {
            "resolver": "extract_symbol_graph",
            "source": "syntax",
        }
        assert rel["call_site_id"].startswith("call:")
        assert rel["location"]["byte_start"] < rel["location"]["byte_end"]


@pytest.mark.parametrize(
    ("language", "extension"), [("javascript", "js"), ("typescript", "ts")]
)
@pytest.mark.parametrize("mode", ["strict", "permissive"])
def test_normalized_reference_duplicates_and_relationship_types(
    tmp_path: Path, language, extension, mode
):
    source = tmp_path / f"service.{extension}"
    source.write_text(
        "export function target() { return 1; }\n"
        "export function caller() { target(); }\n",
        encoding="utf-8",
    )
    facts = extract_symbol_facts_for_file(source, source, language, fail_fast=True)
    caller_id = next(
        symbol_id
        for symbol_id, symbol in facts["symbol_lookup"].items()
        if symbol["name"] == "caller"
    )
    target_id = next(
        symbol_id
        for symbol_id, symbol in facts["symbol_lookup"].items()
        if symbol["name"] == "target"
    )
    caller = next(
        record
        for record in facts["chunk_records"]
        if record["context"]["id"] == caller_id
    )
    assert caller["calls"] == ["target"]
    for relationship_type in ("imports", "dependencies"):
        caller[relationship_type] = [
            "target",
            " target ",
            {"qualified_name": "target"},
            "ns.target",
            {"symbol": " ns.target "},
            "other.target",
        ]

    result = assemble_symbol_graph([facts], resolution_mode=mode)
    pairs = [(rel["type"], rel["reference"]) for rel in result["relationships"]]

    assert pairs == [
        (relationship_type, reference)
        for relationship_type in ("imports", "dependencies")
        for reference in ("target", "ns.target", "other.target")
    ] + [("calls", "target")], "distinct normalized references were collapsed"
    assert result["metadata"]["total_relationships"] == 7
    assert all(rel["from"] == caller_id for rel in result["relationships"])
    assert all(rel["to"] == target_id for rel in result["relationships"])

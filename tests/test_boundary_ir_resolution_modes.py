from pathlib import Path

import pytest

from chunker.boundary import dumps_boundary_ir, extract_boundary_ir
from chunker.boundary.cache import load_cache_index, load_cache_record


def _edge_for(ir: dict, reference: str, edge_type: str = "calls") -> dict:
    matches = [
        edge
        for edge in ir["edges"]
        if edge["reference"] == reference and edge["type"] == edge_type
    ]
    assert len(matches) == 1
    return matches[0]


def test_strict_boundary_ir_ambiguous_edge_uses_reference_target(
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

    ir = extract_boundary_ir(tmp_path, "python")
    edge = _edge_for(ir, "helper")

    assert edge["resolution"] == "ambiguous"
    assert edge["target"] == "helper"
    assert edge["candidates"] == sorted(edge["candidates"])
    assert len(edge["candidates"]) == 2
    assert ir["metrics"]["ambiguous_edges"] == sum(
        1 for item in ir["edges"] if item["resolution"] == "ambiguous"
    )
    assert edge["provenance"]["resolution_mode"] == "strict"
    assert edge["provenance"]["enforcement_grade"] == "strict"


def test_strict_boundary_ir_unresolved_edge_uses_reference_target(
    tmp_path: Path,
):
    (tmp_path / "service.py").write_text(
        "def use_missing():\n    return missing_call()\n",
        encoding="utf-8",
    )

    ir = extract_boundary_ir(tmp_path, "python", resolution_mode="strict")
    edge = _edge_for(ir, "missing_call")

    assert edge["resolution"] == "unresolved"
    assert edge["target"] == "missing_call"
    assert edge["candidates"] == []
    assert ir["metrics"]["unresolved_edges"] == sum(
        1 for item in ir["edges"] if item["resolution"] == "unresolved"
    )


def test_permissive_boundary_ir_records_mode_without_enforcement_grade(
    tmp_path: Path,
):
    (tmp_path / "service.py").write_text(
        "def use_missing():\n    return missing_call()\n",
        encoding="utf-8",
    )

    ir = extract_boundary_ir(tmp_path, "python", resolution_mode="permissive")
    edge = _edge_for(ir, "missing_call")

    assert ir["run"]["options"]["resolution_mode"] == "permissive"
    assert edge["target"] == "missing_call"
    assert edge["provenance"]["resolution_mode"] == "permissive"
    assert "enforcement_grade" not in edge["provenance"]


@pytest.mark.parametrize(
    ("language", "extension"), [("javascript", "js"), ("typescript", "ts")]
)
@pytest.mark.parametrize("mode", ["strict", "permissive"])
@pytest.mark.parametrize("reverse", [False, True])
def test_distinct_call_references_survive_fresh_cold_and_warm_boundary_ir(
    tmp_path: Path, monkeypatch, language, extension, mode, reverse
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
    cache_dir = tmp_path / "cache"
    fresh = extract_boundary_ir(
        source, language, resolution_mode=mode, canonical=True, fail_fast=True
    )
    cold = extract_boundary_ir(
        source,
        language,
        resolution_mode=mode,
        canonical=True,
        fail_fast=True,
        incremental=True,
        cache_dir=cache_dir,
    )
    index = load_cache_index(cache_dir)
    record = load_cache_record(cache_dir, index.records[source.name])
    assert record is not None
    caller_id = next(
        node["id"] for node in record.node_records if node["symbol"] == "caller"
    )
    caller_facts = next(
        chunk
        for chunk in record.symbol_facts["chunk_records"]
        if chunk["context"]["id"] == caller_id
    )
    assert caller_facts["calls"] == raw_calls

    from chunker.boundary import adapter

    def unexpected_recomputation(*args, **kwargs):
        pytest.fail("warm extraction must reuse the persisted raw symbol facts")

    monkeypatch.setattr(adapter, "_extract_file_cache_record", unexpected_recomputation)
    warm = extract_boundary_ir(
        source,
        language,
        resolution_mode=mode,
        canonical=True,
        fail_fast=True,
        incremental=True,
        cache_dir=cache_dir,
    )

    assert (
        dumps_boundary_ir(fresh) == dumps_boundary_ir(cold) == dumps_boundary_ir(warm)
    )
    calls = [edge for edge in warm["edges"] if edge["type"] == "calls"]
    assert sorted(edge["reference"] for edge in calls) == sorted(
        references
    ), "distinct normalized references were collapsed"
    assert len({edge["id"] for edge in calls}) == 3
    assert warm["diagnostics"] == []
    assert warm["metrics"]["edges_total"] == len(warm["edges"]) == 6
    caller = next(node for node in warm["nodes"] if node["symbol"] == "caller")
    target = next(node for node in warm["nodes"] if node["symbol"] == "target")
    assert caller["relationships"] == sorted(edge["id"] for edge in warm["edges"])
    for edge in calls:
        assert edge["source"] == caller["id"]
        assert edge["target"] == target["id"]
        assert edge["candidates"] == [target["id"]]
        assert edge["resolution"] == "resolved"
        assert edge["metadata"] == {"file": source.name, "is_internal": True}
        assert edge["location"] == {
            "byte_start": None,
            "byte_end": None,
            "start_line": 2,
            "end_line": 2,
        }
        assert edge["provenance"]["resolution_mode"] == mode
        if mode == "strict":
            assert edge["provenance"]["enforcement_grade"] == "strict"
        else:
            assert "enforcement_grade" not in edge["provenance"]

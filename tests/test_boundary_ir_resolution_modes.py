from pathlib import Path

from chunker.boundary import extract_boundary_ir


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

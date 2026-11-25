"""Independent declaration oracles for treesitter-chunker#685."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from chunker.boundary import extract_boundary_ir
from chunker.symbol_graph import (
    assemble_symbol_graph,
    collect_source_files,
    extract_symbol_facts_for_file,
    extract_symbol_graph,
)
from tests import call_resolution_harness as harness


@pytest.mark.parametrize(
    ("ext", "source", "decoys"),
    [
        ("js", "function outer(){\n const helper = () => 2;\n return helper(); }", 0),
        (
            "ts",
            "function outer(){\n const helper = function(){return 2};\n return helper(); }",
            2,
        ),
        (
            "tsx",
            "class K { run(){\n return helper();\n function helper(){return 2} } }",
            1,
        ),
        ("py", "def outer():\n class helper: pass\n return helper()", 1),
        (
            "py",
            "def outer():\n async def helper(): return 2\n def inner(): return helper()\n return inner()",
            2,
        ),
    ],
)
def test_nested_target(tmp_path: Path, ext: str, source: str, decoys: int) -> None:
    path = tmp_path / f"outer.{ext}"
    comment = "# café" if ext == "py" else "// café"
    path.write_bytes((comment + "\n" + source + "\n").replace("\n", "\r\n").encode())
    for i in range(decoys):
        (tmp_path / f"decoy{i}.{ext}").write_text(
            "def helper(): return 0" if ext == "py" else "function helper(){return 0}",
            encoding="utf-8",
        )
    off = extract_symbol_graph(tmp_path)
    on = extract_symbol_graph(tmp_path, call_resolution="imports")
    before, edge = [
        next(
            e
            for e in g["relationships"]
            if e.get("reference") == "helper" and e["type"] == "calls"
        )
        for g in (off, on)
    ]
    assert len(before["candidates"]) == decoys
    line = 4 if ext == "tsx" else 3
    (target,) = [
        k
        for k, v in on["symbol_lookup"].items()
        if v["file"] == path.name and v["line"] == line
    ]
    assert edge["to"] == target and edge["candidates"] == [target]
    assert edge["call_site_id"] == before["call_site_id"]
    assert edge["provenance"]["call_rules"] == ["t2.nested_local"]
    assert not harness.symbol_graph_violations(off, on, "imports")
    facts = [
        extract_symbol_facts_for_file(f, tmp_path, call_resolution="imports")
        for f in collect_source_files(tmp_path)
    ]
    warm = assemble_symbol_graph(
        json.loads(json.dumps(facts)), total_files=len(facts), call_resolution="imports"
    )
    assert warm["relationships"] == on["relationships"]
    bir_off = extract_boundary_ir(tmp_path)
    bir = extract_boundary_ir(tmp_path, call_resolution="imports")
    changed = next(e for e in bir["edges"] if e["id"] == edge["call_site_id"])
    assert changed["target"] == target
    assert not harness.boundary_violations(bir_off, bir, "imports")
    cache = tmp_path / ".cache"
    for _ in range(2):
        cached = extract_boundary_ir(
            tmp_path, incremental=True, cache_dir=cache, call_resolution="imports"
        )
        assert cached["edges"] == bir["edges"]


@pytest.mark.parametrize(
    ("ext", "body"),
    [
        ("js", "helper(); const helper=()=>2;"),
        ("py", "def inner(): return helper()\n inner()\n def helper(): pass"),
        ("js", "const helper=()=>2; function inner(){helper()}"),
        ("ts", "let helper=()=>2; helper();"),
        ("js", "function helper(){} function helper(){} helper();"),
        ("js", "function helper(){} helper=other; helper();"),
        ("js", "function helper(){} {const helper=other; helper()}"),
        ("py", "helper()\n def helper(): pass"),
        ("py", "if flag:\n  def helper(): pass\n helper()"),
        ("py", "def helper(): pass\n del helper\n helper()"),
        ("py", "def helper(): pass\n def helper(): pass\n helper()"),
        (
            "py",
            "def helper(): pass\n def inner():\n  nonlocal helper\n  helper = other\n helper()",
        ),
        ("py", "def helper(): pass\n def inner():\n  global helper\n  helper()"),
        ("py", "def helper(): pass\n def inner(helper):\n  helper()"),
        ("py", "def inner(): return helper()\n def helper(): pass"),
    ],
)
def test_withhold(tmp_path: Path, ext: str, body: str) -> None:
    source = (
        "def helper(): pass\ndef outer():\n " + body
        if ext == "py"
        else "function helper(){}\nfunction outer(){" + body + "}"
    )
    (tmp_path / f"use.{ext}").write_text(source, encoding="utf-8")
    before, after = [
        next(
            e
            for e in extract_symbol_graph(tmp_path, call_resolution=mode)[
                "relationships"
            ]
            if e.get("reference") == "helper" and e["type"] == "calls"
        )
        for mode in ("name", "imports")
    ]
    assert after == before


def test_two_nested_bindings_of_same_name(tmp_path: Path) -> None:
    # The same-name top-level and second nested definition are both decoys.
    (tmp_path / "use.py").write_text(
        "def helper(): return 0\n"
        "def first():\n def helper(): return 1\n return helper()\n"
        "def second():\n def helper(): return 2\n return helper()\n",
        encoding="utf-8",
    )
    graph = extract_symbol_graph(tmp_path, call_resolution="imports")
    calls = [
        edge for edge in graph["relationships"] if edge.get("reference") == "helper"
    ]
    assert len(calls) == 2
    assert {
        (edge["line"], graph["symbol_lookup"][edge["to"]]["line"]) for edge in calls
    } == {(4, 3), (7, 6)}
    off = extract_symbol_graph(tmp_path)
    calls[0]["provenance"]["call_rules"] = ["t1.lexical"]
    assert harness.failed_checks(
        harness.symbol_graph_violations(off, graph, "imports")
    ) == {3}

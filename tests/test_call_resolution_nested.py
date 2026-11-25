"""Independent declaration oracles for treesitter-chunker#685."""

from __future__ import annotations

import json
import runpy
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
        (
            "py",
            "def helper(): pass\n def eval(value): return value\n"
            " def annotated(x: eval('1')): return x\n return helper()",
        ),
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
    _assert_helper_fallback(tmp_path)


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


@pytest.mark.parametrize(
    "source",
    [
        b'def helper(): return "global"\n'
        b"def outer():\n"
        b'    def helper(): return "first"\n'
        b"    def middle():\n"
        b"        try: pass\n"
        b"        except ValueError, helper: pass\n"
        b"        def update():\n"
        b"            nonlocal helper\n"
        b'            def helper(): return "second"\n'
        b"        update()\n"
        b"    middle()\n"
        b"    return helper()\n",
        b'def helper(*args): return "global"\n'
        b"def outer():\n"
        b'    def helper(*args): return "first"\n'
        b"    def update():\n"
        b"        nonlocal helper\n"
        b"        try: raise ValueError\n"
        b"        except ValueError, (helper := LookupError): pass\n"
        b"    update()\n"
        b'    return str(helper("second"))\n',
        b"# coding: unicode_escape\n"
        b'def helper(): return "global"\n'
        b"def outer():\n"
        b'    def helper(): return "first"\n'
        rb'    # next declaration\n    def helper(): return "second"'
        b"\n"
        b"    return helper()\n",
    ],
    ids=[
        "nonlocal-across-exception-list",
        "walrus-in-exception-list",
        "escaped-newline-in-comment",
    ],
)
def test_python_uncertain_owner(tmp_path: Path, source: bytes) -> None:
    path = tmp_path / "use.py"
    path.write_bytes(source)
    namespace = runpy.run_path(str(path))
    assert namespace["outer"]() == "second"
    _assert_helper_fallback(tmp_path)


def _helper_edge(path: Path, mode: str) -> dict:
    graph = extract_symbol_graph(path, call_resolution=mode)
    (edge,) = [
        e
        for e in graph["relationships"]
        if e["type"] == "calls" and e.get("reference") == "helper"
    ]
    return edge


def _assert_helper_fallback(path: Path) -> None:
    assert _helper_edge(path, "imports") == _helper_edge(path, "name")


def test_shorthand_arguments_write_withholds(tmp_path: Path) -> None:
    """Sloppy ``{ arguments }`` exposes the mapped parameter that the nested
    declaration shares, so a write through it can replace ``helper``."""
    (tmp_path / "use.js").write_text(
        'function helper() { return "global" }\n'
        'function other() { return "second" }\n'
        "function outer(helper) {\n"
        '  function helper() { return "first" }\n'
        "  const box = { arguments }\n"
        "  box.arguments[0] = other\n"
        "  return helper()\n"
        "}\n"
        "console.log(outer(null))\n",
        encoding="utf-8",
    )
    _assert_helper_fallback(tmp_path)


@pytest.mark.parametrize(
    ("ext", "callee"),
    [
        ("js", "(/* direct */ eval)"),
        ("js", "(eval /* direct */)"),
        ("js", "((/* a */ (eval /* b */)))"),
        ("js", "(<!-- direct in a script\neval)"),
        ("js", "(0, eval)"),
        ("ts", "(eval<string>)"),
        ("tsx", "((/* direct */ eval<string>))"),
    ],
)
def test_eval_operand(tmp_path: Path, ext: str, callee: str) -> None:
    declarations = (
        "" if ext == "js" else "declare function eval<T>(source: string): unknown;\n"
    )
    (tmp_path / f"use.{ext}").write_text(
        f'{declarations}function helper() {{ return "global" }}\n'
        'function other() { return "second" }\n'
        "function outer() {\n"
        '  function helper() { return "first" }\n'
        f'  {callee}("helper = other")\n'
        "  return helper()\n"
        "}\n",
        encoding="utf-8",
    )
    if callee == "(0, eval)":
        # A comma expression discards the Reference: indirect eval runs in
        # the global environment and cannot assign the function's local helper.
        assert _helper_edge(tmp_path, "imports")["provenance"]["call_rules"] == [
            "t2.nested_local"
        ]
    else:
        _assert_helper_fallback(tmp_path)

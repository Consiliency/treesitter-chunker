"""Runtime-independent oracles for targets outside the name candidate set."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from chunker.boundary import extract_boundary_ir
from chunker.call_resolution import engine
from chunker.symbol_graph import extract_symbol_graph
from tests import call_resolution_harness as harness


def _write(root: Path, files: dict[str, str]) -> None:
    for name, source in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(source.encode("utf-8"))


def _site(edges: list[dict[str, Any]], reference: str = "alias") -> dict[str, Any]:
    (edge,) = [e for e in edges if e["type"] == "calls" and e["reference"] == reference]
    return edge


def _assert_target(edge: dict[str, Any], target: str) -> None:
    assert edge["to"] == target and edge["candidates"] == [target]


@pytest.mark.parametrize("language", ["js", "ts"])
@pytest.mark.parametrize("decoys", [0, 1, 2])
@pytest.mark.parametrize("mode", ["strict", "permissive"])
def test_proven_alias(tmp_path: Path, language: str, decoys: int, mode: str) -> None:
    definition = "export function exp(){ return 1; }"
    use = f"import {{exp as alias}} from './svc.{language}';\nexport function run(){{ return alias(); }}"
    _write(
        tmp_path,
        {
            f"svc.{language}": definition,
            f"use.{language}": "// café\r\n" + use.replace("\n", "\r\n"),
            **{
                f"decoy{i}.{language}": definition.replace("exp()", "alias()")
                for i in range(decoys)
            },
        },
    )
    off = extract_symbol_graph(tmp_path, resolution_mode=mode)
    on = extract_symbol_graph(tmp_path, resolution_mode=mode, call_resolution="imports")
    before, edge = (_site(graph["relationships"]) for graph in (off, on))
    assert len(before["candidates"]) == decoys
    assert edge["call_site_id"] == before["call_site_id"]
    (target,) = [
        key
        for key, s in on["symbol_lookup"].items()
        if s["file"] == f"svc.{language}" and s["name"] == "exp" and s["line"] == 1
    ]
    _assert_target(edge, target)
    assert edge["resolution"] == "resolved" and edge["is_internal"]
    assert edge["provenance"]["call_rules"] == ["t2.import_alias"]
    assert not harness.symbol_graph_violations(off, on, "imports")
    structural = extract_symbol_graph(
        tmp_path, resolution_mode=mode, call_resolution="structural"
    )
    assert _site(structural["relationships"]) == before
    bir_off = extract_boundary_ir(tmp_path, resolution_mode=mode)
    bir_on = extract_boundary_ir(
        tmp_path, resolution_mode=mode, call_resolution="imports"
    )
    bir = _site(bir_on["edges"])
    assert bir["id"] == before["call_site_id"]
    assert bir["resolution"] == "resolved" and bir["candidates"] == [bir["target"]]
    assert bir["provenance"]["call_rules"] == ["t2.import_alias"]
    assert not harness.boundary_violations(bir_off, bir_on, "imports")


JS_USE = (
    "import {exp as alias} from './svc.js';\nexport function run(){ return alias(); }"
)
JS_SVC = "export function exp(){ return 1; }"


@pytest.mark.parametrize("mode", ["name", "structural", "imports"])
@pytest.mark.parametrize(
    "escaped", [False, True], ids=["plain", "builtin-delattr-exception"]
)
def test_python_renamed_import_preserves_name_edge(
    tmp_path: Path, escaped: bool, mode: str
) -> None:
    files = {
        "m.py": "def x(): return 'intended'\n",
        "use.py": "from m import x as y\ndef run(): return y()\n",
    }
    if escaped:
        files.update(
            {
                "entry.py": "import writer\nimport use\nprint(use.run())\n",
                "writer.py": (
                    "import m\ndef earlier(): return 'earlier'\n"
                    "try:\n    delattr(m, 'missing')\n"
                    "except AttributeError as e:\n    e.obj.x = earlier\n"
                ),
            }
        )
    _write(tmp_path, files)
    for extract, field in (
        (extract_symbol_graph, "relationships"),
        (extract_boundary_ir, "edges"),
    ):
        before = _site(extract(tmp_path)[field], "y")
        assert before["resolution"] == "unresolved" and before["candidates"] == []
        assert _site(extract(tmp_path, call_resolution=mode)[field], "y") == before


@pytest.mark.parametrize(
    "use",
    [
        "import alias from './svc.js';",
        "import * as alias from './svc.js';",
        "import type {exp as alias} from './svc.js';",
        "import {exp as alias} from 'external';",
        "import {exp as alias} from './missing.js';",
    ],
)
def test_other_import_forms_do_not_substitute(tmp_path: Path, use: str) -> None:
    _write(
        tmp_path,
        {
            "svc.js": "export default function exp(){}\nexport {exp};",
            "use.ts": use + "\nexport function run(){ return alias(); }",
        },
    )
    calls = extract_symbol_graph(tmp_path, call_resolution="imports")["relationships"]
    assert _site(calls)["resolution"] == "unresolved"


def test_warm_alias_rechecks_writer(tmp_path: Path) -> None:
    root = tmp_path / "tree"
    _write(root, {"svc.js": JS_SVC, "use.js": JS_USE})
    ids = set()
    for writer, expected in [
        ("", "resolved"),
        ("require(dynamicName);", "unresolved"),
        ("", "resolved"),
    ]:
        _write(root, {"writer.js": writer})
        warm = extract_boundary_ir(
            root,
            call_resolution="imports",
            incremental=True,
            cache_dir=tmp_path / "cache",
        )
        cold = extract_boundary_ir(root, call_resolution="imports")
        edge = _site(warm["edges"])
        assert edge == _site(cold["edges"])
        assert edge["resolution"] == expected
        assert ("call_rules" in edge["provenance"]) == (expected == "resolved")
        ids.add(edge["id"])
    assert len(ids) == 1


def test_substitution_cannot_claim_another_real_export(tmp_path: Path) -> None:
    _write(tmp_path, {"use.js": JS_USE, "svc.js": JS_SVC, "other.js": JS_SVC})
    graph = extract_symbol_graph(tmp_path, call_resolution="imports")
    edge = _site(graph["relationships"])
    exports = {
        s["file"]: k for k, s in graph["symbol_lookup"].items() if s["name"] == "exp"
    }
    _assert_target(edge, exports["svc.js"])
    forged = dict(edge, to=exports["other.js"], candidates=[exports["other.js"]])
    with pytest.raises(AssertionError):
        _assert_target(forged, exports["svc.js"])


def test_alias_rule_cannot_label_ordinary_narrowing(tmp_path: Path) -> None:
    _write(
        tmp_path,
        {
            "use.js": JS_USE.replace("exp as alias", "exp").replace("alias()", "exp()"),
            "svc.js": JS_SVC,
            "other.js": JS_SVC,
        },
    )
    before = extract_symbol_graph(tmp_path)
    after = extract_symbol_graph(tmp_path, call_resolution="imports")
    edge = next(e for e in after["relationships"] if e["type"] == "calls")
    assert edge["provenance"]["call_rules"] == ["t2.import"]
    edge["provenance"]["call_rules"] = ["t2.import_alias"]
    assert harness.failed_checks(
        harness.symbol_graph_violations(before, after, "imports")
    ) == {3}


def test_alias_records_export_group_rule(tmp_path: Path) -> None:
    _write(
        tmp_path,
        {
            "svc.ts": "export function exp(a: string): number;\nexport function exp(a: any){ return 1; }",
            "use.ts": "import {exp as alias} from './svc';\nexport function run(){ return alias('x'); }",
        },
    )
    graph = extract_symbol_graph(tmp_path, call_resolution="imports")
    edge = _site(graph["relationships"])
    symbol = graph["symbol_lookup"][edge["to"]]
    assert symbol["file"] == "svc.ts" and symbol["line"] == 2
    assert edge["provenance"]["call_rules"] == ["t2.import_alias", "t1.ts_overload"]


def test_multiple_proven_declarations_cannot_substitute() -> None:
    before = ("decoy",)
    assert engine._substitute(
        before, frozenset({"first", "second"}), ("t2.import_alias",)
    ) == (before, ())

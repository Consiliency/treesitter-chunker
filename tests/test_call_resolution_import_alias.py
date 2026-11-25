"""Runtime-independent oracles for targets outside the name candidate set."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from chunker.boundary import extract_boundary_ir
from chunker.symbol_graph import extract_symbol_graph
from tests import call_resolution_harness as harness


def _write(root: Path, files: dict[str, str]) -> None:
    for name, source in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(source.encode("utf-8"))


def _site(edges: list[dict[str, Any]]) -> dict[str, Any]:
    (edge,) = [e for e in edges if e["type"] == "calls" and e["reference"] == "alias"]
    return edge


def _assert_target(edge: dict[str, Any], target: str) -> None:
    assert edge["to"] == target and edge["candidates"] == [target]


@pytest.mark.parametrize("language", ["py", "js", "ts"])
@pytest.mark.parametrize("decoys", [0, 1, 2])
@pytest.mark.parametrize("mode", ["strict", "permissive"])
def test_proven_alias(tmp_path: Path, language: str, decoys: int, mode: str) -> None:
    python = language == "py"
    definition = (
        "def exp():\n    return 1" if python else "export function exp(){ return 1; }"
    )
    use = (
        "from svc import exp as alias\ndef run():\n    return alias()"
        if python
        else f"import {{exp as alias}} from './svc.{language}';\nexport function run(){{ return alias(); }}"
    )
    _write(
        tmp_path,
        {
            f"svc.{language}": definition,
            f"use.{language}": ("# café\r\n" if python else "// café\r\n")
            + use.replace("\n", "\r\n"),
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


USE = "from svc import exp as alias\ndef run():\n    return alias()\n"
SVC = "def exp():\n    return 1\n"


@pytest.mark.parametrize(
    "files",
    [
        {
            "svc.py": SVC.replace("exp", "__exp") + SVC.replace("exp", "_K__exp"),
            "use.py": "class K:\n    def run(self):\n        from svc import __exp as alias\n        return alias()\n",
        },
        {
            "__svc.py": SVC,
            "_K__svc.py": SVC,
            "use.py": "class K:\n    def run(self):\n        from __svc import exp as alias\n        return alias()\n",
        },
        {
            "svc.py": SVC,
            "runner/svc.py": SVC,
            "runner/sub/use.py": USE,
            "runner/main.py": "from sub.use import run\nrun()\n",
        },
        {
            "svc.py": SVC,
            "use.py": "import writer\n" + USE,
            "writer.py": "class K:\n    def write(self):\n        import svc as __target\n        _K__target.exp = len\nK().write()\n",
        },
        {
            "svc.py": SVC,
            "bridge.py": "from svc import exp as exposed\n",
            "use.py": "from bridge import exposed as alias\ndef run():\n    return alias()",
            "writer.py": "class K:\n    def write(self):\n        import bridge as __target\n        _K__target.exposed = len\nK().write()",
        },
        {
            "pkg/svc.py": SVC,
            "pkg/use.py": USE.replace("from svc", "from .svc"),
            "pkg/__init__.py": "",
            "pkg/main.py": "import writer\n",
            "pkg/writer.py": "import svc\nsvc.exp = len",
        },
        {
            "svc.py": SVC,
            "other.py": SVC,
            "use.py": "if flag:\n    from svc import exp as alias\nelse:\n    from other import exp as alias\ndef run():\n    return alias()",
        },
        {
            "svc.py": "def __getattr__(name): return len\n" + SVC,
            "use.py": USE,
        },
        {
            "svc.py": SVC + "import writer\ndef later(): pass\n",
            "writer.py": "import svc\ntry: svc.later()\nexcept AttributeError as exc: exc.obj.exp = len",
            "use.py": USE,
        },
        {"svc.py": SVC + SVC, "use.py": USE},
        {
            "svc.py": "def earlier(): return 'earlier'\ndef __getattr__(name): return earlier\nimport use\n"
            + SVC,
            "use.py": USE,
            "entry.py": "import svc\nimport use\nprint(use.run())",
        },
        {
            "svc.py": SVC,
            "use.py": USE,
            "writer.py": "import svc\ndef earlier(): return 'earlier'\ntry: svc.bogus\nexcept AttributeError as exc: getattr(exc,'ob'+'j').exp=earlier",
            "entry.py": "import writer\nimport use\nprint(use.run())",
        },
        {"svc.py": SVC, "use.py": USE, "other.py": "import svc\nsvc.exp = len\n"},
        {
            "svc.py": SVC,
            "use.py": USE,
            "w.py": "from importlib.util import module_from_spec\nexec('x', module_from_spec(spec).__dict__)",
        },
        {"svc.py": SVC, "use.py": USE.replace("run()", "run(alias)")},
        {"svc.py": SVC, "use.py": USE.replace("from svc", "from absent")},
        {"svc.py": SVC + "exp = len\n", "use.py": USE},
        *[
            {
                "svc.py": SVC,
                "use.py": USE,
                "w.py": "import svc\ndef get():\n    return svc\n" + op,
            }
            for op in (
                "setattr(get(), 'exp', len)",
                "x = get() + other",
                "holder = [get()]\nuse(holder)",
                "(get(),).index(other)",
            )
        ],
    ],
)
def test_unsafe_alias_stays_unresolved(tmp_path: Path, files: dict[str, str]) -> None:
    _write(tmp_path, files)
    before = _site(extract_symbol_graph(tmp_path)["relationships"])
    assert before["resolution"] == "unresolved"
    assert (
        _site(
            extract_symbol_graph(tmp_path, call_resolution="imports")["relationships"]
        )
        == before
    )


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
    _write(root, {"svc.py": SVC, "use.py": USE})
    ids = set()
    for writer, expected in [
        ("", "resolved"),
        ("import svc\nsvc.exp = len", "unresolved"),
        ("", "resolved"),
    ]:
        _write(root, {"writer.py": writer})
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
    _write(tmp_path, {"use.py": USE, "svc.py": SVC, "other.py": SVC})
    graph = extract_symbol_graph(tmp_path, call_resolution="imports")
    edge = _site(graph["relationships"])
    exports = {
        s["file"]: k for k, s in graph["symbol_lookup"].items() if s["name"] == "exp"
    }
    _assert_target(edge, exports["svc.py"])
    forged = dict(edge, to=exports["other.py"], candidates=[exports["other.py"]])
    with pytest.raises(AssertionError):
        _assert_target(forged, exports["svc.py"])


def test_alias_rule_cannot_label_ordinary_narrowing(tmp_path: Path) -> None:
    _write(
        tmp_path,
        {
            "use.py": USE.replace("exp as alias", "exp").replace("alias()", "exp()"),
            "svc.py": SVC,
            "other.py": SVC,
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

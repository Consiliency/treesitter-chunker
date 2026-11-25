"""Runtime-independent oracles for targets outside the name candidate set."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from chunker.boundary import extract_boundary_ir
from chunker.call_resolution import engine
from chunker.symbol_graph import (
    assemble_symbol_graph,
    collect_source_files,
    extract_symbol_facts_for_file,
    extract_symbol_graph,
    module_layout,
)
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
@pytest.mark.parametrize("decoys", [0, 1, 2])
@pytest.mark.parametrize(
    "escaped", [False, True], ids=["plain", "builtin-delattr-exception"]
)
def test_python_renamed_import_preserves_name_edge(
    tmp_path: Path, escaped: bool, mode: str, decoys: int
) -> None:
    files = {
        "m.py": "def x(): return 'intended'\n",
        "use.py": "from m import x as y\ndef run(): return y()\n",
    }
    files.update({f"decoy{i}.py": "def y(): pass\n" for i in range(decoys)})
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
        assert len(before["candidates"]) == decoys
        assert before["resolution"] == ("unresolved", "resolved", "ambiguous")[decoys]
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


@pytest.mark.parametrize("reexport", [False, True])
def test_url_trimmed_specifier_cannot_substitute(
    tmp_path: Path, reexport: bool
) -> None:
    # Node trims the space and loads svc.js. A literal path lookup may find
    # svc.js .js. Both filenames are portable and both are in the graph.
    files = {"svc.js": JS_SVC, "svc.js .js": JS_SVC.replace("return 1", "return 2")}
    if reexport:
        files["use.js"] = JS_USE.replace("svc.js", "bridge.js")
        files["bridge.js"] = "export {exp} from './svc.js ';"
    else:
        files["use.js"] = JS_USE.replace("svc.js", "svc.js ")
    _write(tmp_path, files)
    graph = extract_symbol_graph(tmp_path, call_resolution="imports")
    assert _site(graph["relationships"])["resolution"] == "unresolved"


@pytest.mark.parametrize(
    "specifier", ["./sv\tc.js", "./sv\nc.js", "./sv\rc.js", "./svc.js\x01", " ./svc.js"]
)
def test_noisy_writer_path_vetoes_alias(tmp_path: Path, specifier: str) -> None:
    _write(
        tmp_path,
        {
            "svc.js": JS_SVC,
            "use.js": JS_USE,
            "writer.js": f"import {json.dumps(specifier)};",
        },
    )
    graph = extract_symbol_graph(tmp_path, call_resolution="imports")
    assert _site(graph["relationships"])["resolution"] == "unresolved"


@pytest.mark.parametrize("boundary", [False, True])
def test_identity_checks_reject_python_substitution(
    tmp_path: Path, boundary: bool
) -> None:
    _write(
        tmp_path,
        {
            "m.py": "def x(): pass",
            "use.py": "from m import x as y\ndef run(): return y()",
        },
    )
    extract = extract_boundary_ir if boundary else extract_symbol_graph
    off = extract(tmp_path)
    on = extract(tmp_path, call_resolution="imports")
    if boundary:
        edge = _site(on["edges"], "y")
        (target,) = [node["id"] for node in on["nodes"] if node["symbol"] == "x"]
        edge["target"] = target
        edge["metadata"]["is_internal"] = True
        on["metrics"]["unresolved_edges"] -= 1
        on["metrics"]["resolved_edges"] += 1
    else:
        edge = _site(on["relationships"], "y")
        (target,) = [
            k for k, symbol in on["symbol_lookup"].items() if symbol["name"] == "x"
        ]
        edge.update(to=target, is_internal=True)
    edge.update(resolution="resolved", candidates=[target])
    edge["provenance"].update(call_resolution="imports", call_rules=["t2.import_alias"])
    compare = (
        harness.boundary_violations if boundary else harness.symbol_graph_violations
    )
    assert harness.failed_checks(compare(off, on, "imports")) == (
        {7} if boundary else {3}
    )


@pytest.mark.parametrize("boundary", [False, True])
def test_alias_validators_reject_python_target(tmp_path: Path, boundary: bool) -> None:
    _write(
        tmp_path,
        {"use.js": JS_USE, "svc.js": JS_SVC, "other.py": "def unrelated(): pass"},
    )
    extract = extract_boundary_ir if boundary else extract_symbol_graph
    off = extract(tmp_path)
    on = extract(tmp_path, call_resolution="imports")
    if boundary:
        edge = _site(on["edges"])
        (target,) = [n["id"] for n in on["nodes"] if n["symbol"] == "unrelated"]
        edge.update(target=target, candidates=[target])
        violations = harness.boundary_violations(off, on, "imports")
    else:
        edge = _site(on["relationships"])
        (target,) = [
            k for k, s in on["symbol_lookup"].items() if s["name"] == "unrelated"
        ]
        edge.update(to=target, candidates=[target])
        violations = harness.symbol_graph_violations(off, on, "imports")
    assert harness.failed_checks(violations) == ({7} if boundary else {3})


@pytest.mark.parametrize("mode", ["strict", "permissive"])
@pytest.mark.parametrize("construct", [True, False], ids=["new-alias", "bare-alias"])
def test_class_decorator_replaces_alias_target(
    tmp_path: Path, mode: str, construct: bool
) -> None:
    if construct:
        service = (
            "class Replacement { constructor() { console.log('replacement') } }\n"
            "function replace(_value: Function) { return Replacement }\n"
            "@replace\nexport class Service { constructor() { console.log('original') } }"
        )
        use = "import {Service as alias} from './svc.js'; export function run() { return new alias() }\nrun()"
    else:
        service = (
            "function replace(value: typeof Service) { return function Actual() { return 'replacement' } as unknown as typeof Service }\n"
            "@replace export class Service {}"
        )
        use = "import {Service as alias} from './svc'; export function run() { return alias() }\nconsole.log(run())"
    _write(tmp_path, {"svc.ts": service, ("use.ts" if construct else "use.js"): use})
    for extract, field in (
        (extract_symbol_graph, "relationships"),
        (extract_boundary_ir, "edges"),
    ):
        off = _site(extract(tmp_path, resolution_mode=mode)[field])
        assert off["resolution"] == "unresolved"
        on = extract(tmp_path, resolution_mode=mode, call_resolution="imports")
        assert _site(on[field]) == off


def test_legacy_constructor_parameter_can_replace_alias_target(tmp_path: Path) -> None:
    _write(
        tmp_path,
        {
            "svc.ts": (
                "class Replacement { constructor() { console.log('replacement') } }\n"
                "(Reflect as any).decorate = (decorators: Function[], value: Function) => Replacement;\n"
                "function p(_target: any, _key: any, _index: number) {}\n"
                "export class Service { constructor(@p x = 0) { console.log('original') } }"
            ),
            "use.ts": "import {Service as alias} from './svc.js'; export function run(){return new alias()} run();",
        },
    )
    graph = extract_symbol_graph(tmp_path, call_resolution="imports")
    assert _site(graph["relationships"]) == _site(
        extract_symbol_graph(tmp_path)["relationships"]
    )


@pytest.mark.parametrize(
    ("declaration", "exported", "decorated"),
    [
        ("export class Service {}", "Service", False),
        ("export class Service { @d m(){} }", "Service", True),
        ("export class Service { method(@d x: number){} }", "Service", True),
        ("export class Service { constructor(@d x: number){} }", "Service", True),
        ('export class Service { "constructor"(@d x: number){} }', "Service", True),
        ("export class Service { @d field = 1 }", "Service", True),
        ("export class Service { @d accessor value = 1 }", "Service", True),
        ("@d export class Service {}", "Service", True),
        ("export @d class Service {}", "Service", True),
        ("@d class Service {} export {Service}", "Service", True),
        ("export default class Service {}", "default", False),
        ("@d export default class Service {}", "default", True),
        ("export default @d class Service {}", "default", True),
        ("@d export abstract class Service {}", "Service", True),
    ],
)
def test_class_alias_through_reexport(
    tmp_path: Path, declaration: str, exported: str, decorated: bool
) -> None:
    _write(
        tmp_path,
        {
            "svc.ts": "function d(...args: any[]) {}\n" + declaration,
            "bridge.ts": f"export {{{exported} as Public}} from './svc.js';",
            "use.ts": "import {Public as alias} from './bridge.js'; export function run(){return new alias()}",
        },
    )
    graph = extract_symbol_graph(tmp_path, call_resolution="imports")
    edge = _site(graph["relationships"])
    if decorated:
        assert edge == _site(extract_symbol_graph(tmp_path)["relationships"])
    else:
        (target,) = [
            k
            for k, s in graph["symbol_lookup"].items()
            if s["file"] == "svc.ts" and s["name"] == "Service"
        ]
        _assert_target(edge, target)
        assert edge["provenance"]["call_rules"] == ["t2.import_alias"]


@pytest.mark.parametrize("suffix", ["js", "tsx"])
def test_incremental_class_decorator_invalidates_target(
    tmp_path: Path, suffix: str
) -> None:
    root = tmp_path / "src"
    _write(
        root,
        {
            "use.ts": "import {Service as alias} from './svc.js'; export function run(){return new alias()}"
        },
    )
    for prefix in ("", "@d ", ""):
        _write(
            root,
            {
                f"svc.{suffix}": f"function d(x){{return x}}\n{prefix}export class Service {{}}"
            },
        )
        cached = extract_boundary_ir(
            root,
            call_resolution="imports",
            incremental=True,
            cache_dir=tmp_path / "cache",
        )
        edge = _site(cached["edges"])
        assert edge == _site(
            extract_boundary_ir(root, call_resolution="imports")["edges"]
        )
        assert edge["resolution"] == ("unresolved" if prefix else "resolved")


@pytest.mark.parametrize("forwarded", [False, True])
def test_decorated_namespace_call_replaces_other_export(
    tmp_path: Path, forwarded: bool
) -> None:
    _write(
        tmp_path,
        {
            "svc.ts": (
                "function other() { return 'replacement' }\n"
                "function swap(cls: typeof Install) {\n"
                "  return function(this: any) { this.exp = other } as unknown as typeof Install\n"
                "}\n@swap export class Install {}\n"
                "export function exp() { return 'original' }"
            ),
            "use.ts": (
                "import * as svc from './svc.js';\n"
                "import {exp as alias} from './svc.js';\n"
                "export function run() { (svc.Install as unknown as () => void)(); return alias(); }\n"
                "console.log(run());"
            ),
        },
    )
    if forwarded:
        installer, export = (
            (tmp_path / "svc.ts").read_text().split("export function exp")
        )
        _write(
            tmp_path,
            {
                "install.ts": installer,
                "svc.ts": "export {Install} from './install.js';\nexport function exp"
                + export,
            },
        )
    _assert_alias_withheld(tmp_path)


def _assert_alias_withheld(root: Path) -> None:
    for extract, field in (
        (extract_symbol_graph, "relationships"),
        (extract_boundary_ir, "edges"),
    ):
        before = _site(extract(root)[field])
        assert before["resolution"] == "unresolved"
        assert _site(extract(root, call_resolution="imports")[field]) == before


@pytest.mark.parametrize(
    "bridge",
    [
        "export {exp} from './svc.js';",
        "export * from './svc.js';",
        "import {exp} from './svc.js'; export {exp};",
    ],
)
def test_decorator_in_intermediate_module(tmp_path: Path, bridge: str) -> None:
    _write(
        tmp_path,
        {
            "use.ts": JS_USE.replace("./svc.js", "./bridge.js"),
            "bridge.ts": "function d(...args: any[]) {}\nclass Unrelated { @d field = 1 }\n"
            + bridge,
            "svc.ts": JS_SVC,
        },
    )
    _assert_alias_withheld(tmp_path)


@pytest.mark.parametrize("importer", ["js", "ts"])
@pytest.mark.parametrize("sibling", ["ts", "tsx", "mts", "cts", "d.ts"])
@pytest.mark.parametrize("through_bridge", [False, True])
def test_literal_and_typescript_siblings(
    tmp_path: Path, importer: str, sibling: str, through_bridge: bool
) -> None:
    files = {
        f"use.{importer}": JS_USE + "\nconsole.log(run());",
        "svc.js": "export function exp(){return 'javascript'}",
        f"svc.{sibling}": (
            "export declare function exp(): string;"
            if sibling == "d.ts"
            else "export function exp(){return 'typescript'}"
        ),
    }
    if through_bridge:
        files[f"use.{importer}"] = files[f"use.{importer}"].replace(
            "./svc.js", "./bridge.js"
        )
        files["bridge.js"] = "export {exp} from './svc.js';"
    _write(tmp_path, files)
    _assert_alias_withheld(tmp_path)


@pytest.mark.parametrize("suffix", ["js", "ts"])
def test_explicit_js_specifier_lone_source(tmp_path: Path, suffix: str) -> None:
    _write(tmp_path, {"use.js": JS_USE, f"svc.{suffix}": JS_SVC})
    graph = extract_symbol_graph(tmp_path, call_resolution="imports")
    edge = _site(graph["relationships"])
    assert edge["provenance"]["call_rules"] == ["t2.import_alias"]
    assert graph["symbol_lookup"][edge["to"]]["file"] == f"svc.{suffix}"


@pytest.mark.parametrize(("runtime", "source"), [("mjs", "mts"), ("cjs", "cts")])
def test_uncollected_module_variants(tmp_path: Path, runtime: str, source: str) -> None:
    _write(
        tmp_path,
        {
            "use.js": JS_USE.replace("./svc.js", f"./svc.{runtime}"),
            f"svc.{runtime}": JS_SVC,
            f"svc.{source}": JS_SVC,
        },
    )
    _assert_alias_withheld(tmp_path)


def test_cached_alias_rechecks_unparsed_sibling(tmp_path: Path) -> None:
    root = tmp_path / "src"
    _write(root, {"use.js": JS_USE, "svc.js": JS_SVC})

    def cached_edge() -> dict[str, Any]:
        return _site(
            extract_boundary_ir(
                root,
                language="javascript",
                call_resolution="imports",
                incremental=True,
                cache_dir=tmp_path / "cache",
            )["edges"]
        )

    assert cached_edge()["resolution"] == "resolved"
    _write(root, {"svc.mts": JS_SVC})
    assert cached_edge()["resolution"] == "unresolved"
    (root / "svc.mts").unlink()
    assert cached_edge()["resolution"] == "resolved"


def test_downlevel_class_field_writes_namespace_receiver(tmp_path: Path) -> None:
    _write(
        tmp_path,
        {
            "svc.ts": (
                "function other(){return 'replacement'}\n"
                "export class Install {exp = other}\n"
                "export function exp(){return 'original'}"
            ),
            "use.ts": (
                "import * as svc from './svc.js';\n"
                "import {exp as alias} from './svc.js';\n"
                "export function run(){ (svc.Install as unknown as () => void)(); return alias(); }\n"
                "console.log(run());"
            ),
        },
    )
    _assert_alias_withheld(tmp_path)


def test_filtered_facts_need_layout_for_alias_substitution(tmp_path: Path) -> None:
    _write(tmp_path, {"use.js": JS_USE, "svc.js": JS_SVC})
    facts = [
        extract_symbol_facts_for_file(
            path, tmp_path, "javascript", call_resolution="imports"
        )
        for path in collect_source_files(tmp_path, "javascript")
    ]
    options = {"language_filter": "javascript", "call_resolution": "imports"}

    def assembled(**layout: Any) -> dict[str, Any]:
        return _site(assemble_symbol_graph(facts, **options, **layout)["relationships"])

    assert assembled()["resolution"] == "unresolved"
    assert assembled(variant_paths=module_layout(tmp_path)[1])["provenance"][
        "call_rules"
    ] == ["t2.import_alias"]
    _write(tmp_path, {"svc.ts": JS_SVC})
    assert assembled()["resolution"] == "unresolved"
    assert (
        assembled(variant_paths=module_layout(tmp_path)[1])["resolution"]
        == "unresolved"
    )


def test_jsx_implicit_namespace_call(tmp_path: Path) -> None:
    _write(
        tmp_path,
        {
            "svc.ts": "export function exp(){return 'original'}\nfunction other(){return 'replacement'}\n"
            "export function createElement(this:any,...args:any[]){this.exp=other}",
            "use.tsx": "import * as React from './svc.js';\nimport {exp as alias} from './svc.js';\n"
            "export function run(){ <div/>; return alias(); }\nconsole.log(run());",
        },
    )
    _assert_alias_withheld(tmp_path)


def test_commonjs_emit_calls_shadowed_require(tmp_path: Path) -> None:
    _write(
        tmp_path,
        {
            "svc.js": JS_SVC,
            "use.js": "function require(){return {exp(){return 'replacement'}}}\n"
            + JS_USE
            + "\nconsole.log(run());",
        },
    )
    _assert_alias_withheld(tmp_path)


def test_downlevel_helper_overwrites_hoisted_export(tmp_path: Path) -> None:
    _write(
        tmp_path,
        {
            "svc.ts": "export function __assign(...args:any[]):any{return 'original'}\n"
            "export const demote=(a:any)=>({...a});",
            "bridge.ts": "export {__assign as exp} from './svc.js';",
            "use.ts": "import {exp as alias} from './bridge.js';\n"
            "export function run(){return alias({}, {val:'generated'}).val}\nconsole.log(run());",
        },
    )
    _assert_alias_withheld(tmp_path)


def test_jsx_factory_can_receive_exports(tmp_path: Path) -> None:
    _write(
        tmp_path,
        {
            "svc.tsx": "/** @jsx exports.install */\ndeclare const exports:any;\n"
            "function other(){return 'replacement'}\n"
            "export function exp(){return 'original'}\n"
            "export function install(this:any, ...args:any[]){this.exp=other}\n"
            "export function go(){<div/>}",
            "use.js": "import {exp as alias, go} from './svc.js';\n"
            "export function run(){go();return alias()}\nconsole.log(run());",
        },
    )
    _assert_alias_withheld(tmp_path)


def test_modified_commonjs_emit_intrinsic(tmp_path: Path) -> None:
    _write(
        tmp_path,
        {
            "svc.js": JS_SVC,
            "use.js": (
                "const def = Object.defineProperty;\n"
                "Object.defineProperty = function(o,k,d){\n"
                " if(k==='__esModule') def(o,'exp',{get(){return ()=> 'replacement'},set(){}});\n"
                " return def(o,k,d);\n};\n" + JS_USE + "\nconsole.log(run());"
            ),
        },
    )
    _assert_alias_withheld(tmp_path)


def test_single_file_self_import_lacks_sibling_inventory(tmp_path: Path) -> None:
    _write(
        tmp_path,
        {
            "svc.js": JS_USE + "\n" + JS_SVC,
            "svc.ts": "export function exp(){return 'other'}",
        },
    )
    _assert_alias_withheld(tmp_path / "svc.js")


@pytest.mark.parametrize("bridge", [False, True], ids=["direct", "reexport"])
@pytest.mark.parametrize(
    ("specifier", "target", "competitor"),
    [
        ("svc", "svc.js", "svc"),
        ("svc.jsx", "svc.jsx/index.ts", "svc.ts"),
        ("svc.js", "svc.js/index.ts", "svc.jsx"),
        ("theme.css", "theme.css.ts", "theme.d.css.ts"),
        ("svc.js", "svc.ts", "svc.js.mjs"),
        ("svc.js", "svc.ts", "svc.jsx/index.mjs"),
        ("svc", "svc.ts", "svc/package.json"),
        ("svc", "svc.ts", "svc.json"),
    ],
)
def test_competing_disk_lookup(
    tmp_path: Path, specifier: str, target: str, competitor: str, bridge: bool
) -> None:
    files = {
        "package.json": '{"type":"module"}',
        "use.ts": JS_USE.replace("svc.js", "bridge.ts" if bridge else specifier),
        target: JS_SVC,
        competitor: (
            '{"main":"../other.js"}'
            if competitor.endswith(".json")
            else (
                "export declare function exp(): string;"
                if competitor.endswith(".d.css.ts")
                else JS_SVC
            )
        ),
        "other.js": JS_SVC,
    }
    if bridge:
        files["bridge.ts"] = f"export {{exp}} from './{specifier}';"
    if specifier == "svc" and competitor == "svc":
        files["use.js"] = files.pop("use.ts")
    _write(tmp_path, files)
    _assert_alias_withheld(tmp_path)


def test_lone_directory_index(tmp_path: Path) -> None:
    _write(
        tmp_path,
        {"use.ts": JS_USE.replace("./svc.js", "./svc"), "svc/index.ts": JS_SVC},
    )
    graph = extract_symbol_graph(tmp_path, call_resolution="imports")
    edge = _site(graph["relationships"])
    assert edge["provenance"]["call_rules"] == ["t2.import_alias"]
    assert graph["symbol_lookup"][edge["to"]]["file"] == "svc/index.ts"


@pytest.mark.parametrize(
    ("option", "value"),
    [
        ("moduleSuffixes", [".test", ""]),
        ("paths", {}),
        ("baseUrl", "."),
        ("rootDirs", ["a", "b"]),
        ("customConditions", ["dev"]),
        ("allowArbitraryExtensions", True),
        ("moduleResolution", "bundler"),
    ],
)
@pytest.mark.parametrize(
    "location",
    [
        "project/tsconfig.json",
        "project/nested/jsconfig.json",
        "tsconfig.json",
        "project/build/tsconfig.json",
    ],
)
def test_unmodeled_lookup_config(
    tmp_path: Path, option: str, value: Any, location: str
) -> None:
    _write(
        tmp_path,
        {
            "project/use.ts": JS_USE,
            "project/svc.ts": JS_SVC,
            "project/svc.test.ts": JS_SVC,
            location: json.dumps({"compilerOptions": {option: value}}),
        },
    )
    _assert_alias_withheld(tmp_path / "project")


@pytest.mark.parametrize(
    "location",
    ["global.d.ts", "types.ts", "types.mts", "node_modules/@types/svc/index.d.ts"],
)
@pytest.mark.parametrize("language", [None, "javascript"])
def test_ambient_module_can_supply_export(
    tmp_path: Path, location: str, language: str | None
) -> None:
    _write(
        tmp_path,
        {
            "use.js": JS_USE,
            "svc.js": JS_SVC,
            location: 'declare module "*.js" { export function exp(): "ambient"; }',
            "tsconfig.json": '{"compilerOptions":{"module":"commonjs","moduleResolution":"node","strict":true}}',
        },
    )
    for extract, field in (
        (extract_symbol_graph, "relationships"),
        (extract_boundary_ir, "edges"),
    ):
        before = _site(extract(tmp_path, language=language)[field])
        assert before["resolution"] == "unresolved"
        assert (
            _site(
                extract(tmp_path, call_resolution="imports", language=language)[field]
            )
            == before
        )


def test_checker_prefers_ambient_declaration_after_disk_lookup(tmp_path: Path) -> None:
    _write(
        tmp_path,
        {
            "use.ts": JS_USE + "\nconst proof: 'ambient' = run();",
            "svc.js": JS_SVC,
            "global.d.ts": 'declare module "*.js" { export function exp(): "ambient"; }',
            "tsconfig.json": '{"compilerOptions":{"module":"commonjs","moduleResolution":"node","strict":true,"noEmit":true},"files":["use.ts","global.d.ts"]}',
        },
    )
    _assert_alias_withheld(tmp_path)


@pytest.mark.parametrize(
    "config",
    [
        {"files": ["../global.d.ts"]},
        {"compilerOptions": {"typeRoots": ["../types"]}},
        {"compilerOptions": {"module": "NodeNext"}},
    ],
)
def test_external_or_implicit_project_lookup(
    tmp_path: Path, config: dict[str, Any]
) -> None:
    _write(
        tmp_path,
        {"use.ts": JS_USE, "svc.js": JS_SVC, "tsconfig.json": json.dumps(config)},
    )
    _assert_alias_withheld(tmp_path)

"""Tier 2 call resolution for TS/JS, ``call_resolution="imports"`` (#682 PR 5).

Plan ``plans/detailed-scoped-call-resolution-682.md`` sections 9.1-9.3, 9.7
and 9.8. The committed fixtures' expected tables are asserted in
``test_call_resolution_engine.py``; this module covers each rule on trees the
tests write, because a committed tree would change the off-mode baseline
(11.2):

- exact decoding of string specifiers and quoted names (owner rule: decode
  per ECMAScript or fail closed);
- module resolution (relative only, TypeScript's candidate order, O-1 (a):
  more than one existing variant gives ``ambiguous-extension``);
- the export table, re-export hops, star exports and their failures;
- namespace imports (``ns.f()``) and every way ``ns`` may escape or be
  written;
- CommonJS reach: a module whose exports object CommonJS code may write,
  or another file may write through ``require``, ``import()`` or a namespace
  import, never resolves.

Each positive is unchanged in ``structural`` mode, where an import proves
nothing (6.3). Each near-miss keeps its off-mode edge exactly.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from chunker.call_resolution import engine, modules
from chunker.call_resolution.facts import (
    KNOWN_NONE_REASONS,
    valid_module_bindings,
    valid_scope_facts,
)
from chunker.call_resolution.js_strings import decode_js_string
from chunker.symbol_graph import (
    SKIP_PARTS,
    assemble_symbol_graph,
    collect_source_files,
    extract_symbol_facts_for_file,
    extract_symbol_graph,
)

MODE = "imports"
SVC = "export function t() { return 1; }\n"
USE = "import { t } from './svc';\nexport function u() { return t(); }\n"
# Two more definitions of ``t``, so today's candidate set has two or more
# members whichever file defines ``t``.
OTHERS = {
    "other.ts": "export function t() { return 2; }\n",
    "more.ts": "export function t() { return 3; }\n",
}


def _write(root: Path, files: dict[str, str]) -> Path:
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return root


def _label(outcome: Any) -> str | None:
    if outcome is None:
        return None
    if outcome["outcome"] == "none":
        return f"none({outcome['reason']})"
    return str(outcome["outcome"])


def _run(
    root: Path, file: str, reference: str, language: str | None = None
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], str | None]:
    """``(off edge, structural edge, imports edge, imports outcome label)``."""
    facts = [
        extract_symbol_facts_for_file(path, root, language, call_resolution=MODE)
        for path in collect_source_files(root, language)
    ]
    for item in facts:
        assert valid_scope_facts(item["scope_facts"], item["language"])
    graph = assemble_symbol_graph(
        facts, total_files=len(facts), call_resolution=MODE, language_filter=language
    )
    context = engine.build_run_context(
        facts, graph["symbol_lookup"], MODE, language_filter=language
    )
    off = extract_symbol_graph(root, language)
    structural = extract_symbol_graph(root, language, call_resolution="structural")
    on = extract_symbol_graph(root, language, call_resolution=MODE)
    assert on == graph

    def pick(document: dict[str, Any]) -> dict[str, Any]:
        (edge,) = [
            edge
            for edge in document["relationships"]
            if edge["type"] == "calls"
            and edge["file"] == file
            and edge["reference"] == reference
        ]
        return edge

    off_edge = pick(off)
    decision = engine.decide(context, off_edge)
    label = _label(decision.outcome) if decision.eligible else None
    return off_edge, pick(structural), pick(on), label


def _resolved_file(graph_edge: dict[str, Any], root: Path) -> str:
    graph = extract_symbol_graph(root, call_resolution=MODE)
    return str(graph["symbol_lookup"][graph_edge["to"]]["file"])


# ---------------------------------------------------------------------------
# Positives: each resolves in ``imports`` mode and is unchanged in
# ``structural`` mode. ``(files, (file, reference), target file, rules)``.

POSITIVES: dict[str, tuple[dict[str, str], tuple[str, str], str, list[str]]] = {
    "named": ({"svc.ts": SVC, "use.ts": USE}, ("use.ts", "t"), "svc.ts", []),
    "export-clause": (
        {"svc.ts": "function t() { return 1; }\nexport { t };\n", "use.ts": USE},
        ("use.ts", "t"),
        "svc.ts",
        [],
    ),
    "default-declaration": (
        {
            "svc.ts": "export default function t() { return 1; }\n",
            "use.ts": "import t from './svc';\nexport function u() { return t(); }\n",
        },
        ("use.ts", "t"),
        "svc.ts",
        [],
    ),
    "default-identifier-parenthesized": (
        {
            "svc.ts": "function t() { return 1; }\nexport default (t);\n",
            "use.ts": "import t from './svc';\nexport function u() { return t(); }\n",
        },
        ("use.ts", "t"),
        "svc.ts",
        [],
    ),
    "export-as-default": (
        {
            "svc.ts": "function t() { return 1; }\nexport { t as default };\n",
            "use.ts": (
                "import { default as t } from './svc';\n"
                "export function u() { return t(); }\n"
            ),
        },
        ("use.ts", "t"),
        "svc.ts",
        [],
    ),
    "quoted-import-name": (
        {
            "svc.ts": SVC,
            "use.ts": (
                "import { 't' as t } from './svc';\n"
                "export function u() { return t(); }\n"
            ),
        },
        ("use.ts", "t"),
        "svc.ts",
        [],
    ),
    "quoted-export-unicode-escape": (
        {
            "svc.ts": 'function t() { return 1; }\nexport { t as "\\u0074" };\n',
            "use.ts": USE,
        },
        ("use.ts", "t"),
        "svc.ts",
        [],
    ),
    "quoted-export-code-point-escape": (
        {
            "svc.ts": "function t() { return 1; }\nexport { t as '\\u{74}' };\n",
            "use.ts": USE,
        },
        ("use.ts", "t"),
        "svc.ts",
        [],
    ),
    "specifier-hex-escape": (
        {
            "svc.ts": SVC,
            "use.ts": (
                'import { t } from "./\\x73vc";\n'
                "export function u() { return t(); }\n"
            ),
        },
        ("use.ts", "t"),
        "svc.ts",
        [],
    ),
    "specifier-line-continuation": (
        {
            "svc.ts": SVC,
            "use.ts": (
                "import { t } from './s\\\nvc';\n"
                "export function u() { return t(); }\n"
            ),
        },
        ("use.ts", "t"),
        "svc.ts",
        [],
    ),
    "overload-set": (
        {
            "svc.ts": (
                "export function t(a: string): number;\n"
                "export function t(a: any) { return 1; }\n"
            ),
            "use.ts": USE,
        },
        ("use.ts", "t"),
        "svc.ts",
        ["t1.ts_overload"],
    ),
    "const-arrow": (
        {"svc.ts": "export const t = () => 1;\n", "use.ts": USE},
        ("use.ts", "t"),
        "svc.ts",
        [],
    ),
    "import-reexported": (
        {
            "svc.ts": SVC,
            "index.ts": "import { t } from './svc';\nexport { t };\n",
            "use.ts": USE.replace("./svc", "./index"),
        },
        ("use.ts", "t"),
        "svc.ts",
        [],
    ),
    "reexport-default-as-name": (
        {
            "svc.ts": "export default function t() { return 1; }\n",
            "index.ts": "export { default as t } from './svc';\n",
            "use.ts": USE.replace("./svc", "./index"),
        },
        ("use.ts", "t"),
        "svc.ts",
        [],
    ),
    "nested-stars": (
        {
            "svc.ts": SVC,
            "mid.ts": "export * from './svc';\n",
            "index.ts": "export * from './mid';\n",
            "use.ts": USE.replace("./svc", "./index"),
        },
        ("use.ts", "t"),
        "svc.ts",
        [],
    ),
    "explicit-export-beats-star": (
        {
            "svc.ts": SVC,
            "a.ts": "export function t() { return 4; }\n",
            "index.ts": "export * from './a';\nexport { t } from './svc';\n",
            "use.ts": USE.replace("./svc", "./index"),
        },
        ("use.ts", "t"),
        "svc.ts",
        [],
    ),
    "namespace-call": (
        {
            "svc.ts": SVC,
            "use.ts": (
                "import * as ns from './svc';\n"
                "export function u() { return ns.t(); }\n"
            ),
        },
        ("use.ts", "ns.t"),
        "svc.ts",
        [],
    ),
    "namespace-allow-listed-reads": (
        {
            "svc.ts": SVC,
            "use.ts": (
                "import * as ns from './svc';\n"
                "const g = ns.t;\n"
                "let k: typeof ns;\n"
                "console.log(ns.t, [ns.t], { a: ns.t }, (ns).t.name, !ns.t);\n"
                "export function u() { return ns.t(); }\n"
            ),
        },
        ("use.ts", "ns.t"),
        "svc.ts",
        [],
    ),
    "namespace-shadowed-write-is-another-binding": (
        {
            "svc.ts": SVC,
            "use.ts": (
                "import * as ns from './svc';\n"
                "function w(ns: any) { ns.t = 1; }\n"
                "export function u() { return ns.t(); }\n"
            ),
        },
        ("use.ts", "ns.t"),
        "svc.ts",
        [],
    ),
    "js-importer-explicit-extension": (
        {
            "svc.js": SVC,
            "svc.ts": "export function t() { return 5; }\n",
            "use.js": USE.replace("./svc", "./svc.js"),
        },
        ("use.js", "t"),
        "svc.js",
        [],
    ),
    "tsx-target": (
        {"svc.tsx": SVC, "use.ts": USE},
        ("use.ts", "t"),
        "svc.tsx",
        [],
    ),
    "directory-index": (
        {"lib/index.ts": SVC, "use.ts": USE.replace("./svc", "./lib")},
        ("use.ts", "t"),
        "lib/index.ts",
        [],
    ),
    "parent-directory": (
        {"svc.ts": SVC, "sub/use.ts": USE.replace("./svc", "../svc")},
        ("sub/use.ts", "t"),
        "svc.ts",
        [],
    ),
    "class-new": (
        {
            "svc.ts": "export class K {}\n",
            "other.ts": "export class K {}\n",
            "more.ts": "export class K {}\n",
            "use.ts": "import { K } from './svc';\nexport function u() { return new K(); }\n",
        },
        ("use.ts", "K"),
        "svc.ts",
        [],
    ),
    "inert-suffix-siblings": (
        {
            "svc.ts": SVC,
            "svc.test.ts": "import { t } from './svc';\nt();\n",
            "svc.stories.tsx": "export {};\n",
            "use.ts": USE,
        },
        ("use.ts", "t"),
        "svc.ts",
        [],
    ),
    "unrelated-require-of-another-module": (
        {
            "svc.ts": SVC,
            "use.ts": USE,
            "x.js": "const fs = require('fs');\nconst o = require('./other');\n",
        },
        ("use.ts", "t"),
        "svc.ts",
        [],
    ),
}


@pytest.mark.parametrize("case", sorted(POSITIVES))
def test_tier2_positives_resolve_end_to_end(tmp_path: Path, case: str) -> None:
    files, (file, reference), target, group_rules = POSITIVES[case]
    root = _write(tmp_path, {**OTHERS, **files})
    off, structural, on, label = _run(root, file, reference)
    assert off["resolution"] == "ambiguous", case
    # Tier 1 and Tier 2 never compete; structural mode proves no import.
    assert structural == off, case
    assert on["resolution"] == "resolved", (case, label)
    assert _resolved_file(on, root) == target, case
    binding_rule = "t2.namespace" if "." in reference else "t2.import"
    assert on["provenance"]["call_rules"] == [binding_rule, *group_rules], case
    assert on["provenance"]["call_resolution"] == MODE
    assert label == "import"


# ---------------------------------------------------------------------------
# Near-misses: each keeps its off-mode edge, with the recorded reason.
# ``(files, (file, reference), reason, language filter)``.

NEAR_MISSES: dict[str, tuple[dict[str, str], tuple[str, str], str, str | None]] = {
    # Live bindings and export forms (9.3).
    "live-let-binding": (
        {"svc.ts": "export let t = () => 1;\n", "use.ts": USE},
        ("use.ts", "t"),
        "expression-bound",
        None,
    ),
    "exporter-reassigns": (
        {"svc.ts": SVC + "t = () => 9;\n", "use.ts": USE},
        ("use.ts", "t"),
        "reassigned",
        None,
    ),
    "exporter-setter": (
        {
            "svc.ts": SVC + "export function set(v: any) { t = v; }\n",
            "use.ts": USE,
        },
        ("use.ts", "t"),
        "reassigned",
        None,
    ),
    "default-expression": (
        {
            "svc.ts": SVC + "export default (function t() { return 1; });\n",
            "use.ts": "import t from './svc';\nexport function u() { return t(); }\n",
        },
        ("use.ts", "t"),
        "expression-bound",
        None,
    ),
    "duplicate-export-name": (
        {
            "svc.ts": (
                "function t() { return 1; }\nfunction s() { return 2; }\n"
                "export { t };\nexport { s as t };\n"
            ),
            "use.ts": USE,
        },
        ("use.ts", "t"),
        "mixed-bindings",
        None,
    ),
    "type-only-export": (
        {"svc.ts": "function t() { return 1; }\nexport type { t };\n", "use.ts": USE},
        ("use.ts", "t"),
        "type-only",
        None,
    ),
    "ambient-export": (
        {"svc.ts": "export declare function t(): number;\n", "use.ts": USE},
        ("use.ts", "t"),
        "ambient",
        None,
    ),
    # Re-exports and stars.
    "star-with-unresolvable-source": (
        {
            "svc.ts": SVC,
            "index.ts": "export * from 'lodash';\nexport * from './svc';\n",
            "use.ts": USE.replace("./svc", "./index"),
        },
        ("use.ts", "t"),
        "external-module",
        None,
    ),
    "star-with-commonjs-source": (
        {
            "svc.ts": SVC,
            "cjs.js": "exports.t = function () {};\n",
            "index.ts": "export * from './cjs';\nexport * from './svc';\n",
            "use.ts": USE.replace("./svc", "./index"),
        },
        ("use.ts", "t"),
        "commonjs",
        None,
    ),
    "star-never-exports-default": (
        {
            "svc.ts": "export default function t() { return 1; }\n",
            "index.ts": "export * from './svc';\n",
            "use.ts": "import t from './index';\nexport function u() { return t(); }\n",
        },
        ("use.ts", "t"),
        "export-not-found",
        None,
    ),
    "star-cycle": (
        {
            "a.ts": "export * from './b';\n",
            "b.ts": "export * from './a';\n",
            "use.ts": USE.replace("./svc", "./a"),
        },
        ("use.ts", "t"),
        "cycle",
        None,
    ),
    "star-hop-limit": (
        {
            "svc.ts": SVC,
            "s1.ts": "export * from './s2';\n",
            "s2.ts": "export * from './s3';\n",
            "s3.ts": "export * from './s4';\n",
            "s4.ts": "export * from './svc';\n",
            "use.ts": USE.replace("./svc", "./s1"),
        },
        ("use.ts", "t"),
        "hop-limit",
        None,
    ),
    "reexport-type-only": (
        {
            "svc.ts": SVC,
            "index.ts": "export type { t } from './svc';\n",
            "use.ts": USE.replace("./svc", "./index"),
        },
        ("use.ts", "t"),
        "type-only",
        None,
    ),
    "reexport-missing-module": (
        {
            "svc.ts": SVC,
            "index.ts": "export { t } from './nope';\n",
            "use.ts": USE.replace("./svc", "./index"),
        },
        ("use.ts", "t"),
        "module-not-found",
        None,
    ),
    "reexport-dts-target": (
        {
            "lib.d.ts": "export declare function t(): number;\n",
            "index.ts": "export { t } from './lib';\n",
            "use.ts": USE.replace("./svc", "./index"),
        },
        ("use.ts", "t"),
        "dts-target",
        None,
    ),
    # Namespace imports: escapes and writes anywhere in the run (CommonJS
    # emit shares a mutable exports object).
    "namespace-member-write-elsewhere": (
        {
            "svc.ts": SVC,
            "use.ts": USE,
            "x.ts": "import * as ns from './svc';\nns.t = () => 0;\n",
        },
        ("use.ts", "t"),
        "commonjs",
        None,
    ),
    "namespace-passed-on": (
        {
            "svc.ts": SVC,
            "use.ts": USE,
            "x.ts": "import * as ns from './svc';\nObject.assign(ns, {});\n",
        },
        ("use.ts", "t"),
        "commonjs",
        None,
    ),
    "namespace-shorthand-escape": (
        {
            "svc.ts": SVC,
            "use.ts": USE,
            "x.ts": "import * as ns from './svc';\nexport const o = { ns };\n",
        },
        ("use.ts", "t"),
        "commonjs",
        None,
    ),
    "namespace-reexported": (
        {
            "svc.ts": SVC,
            "use.ts": USE,
            "x.ts": "import * as ns from './svc';\nexport { ns };\n",
        },
        ("use.ts", "t"),
        "commonjs",
        None,
    ),
    "namespace-delete": (
        {
            "svc.ts": SVC,
            "use.ts": USE,
            "x.ts": "import * as ns from './svc';\ndelete (ns as any).t;\n",
        },
        ("use.ts", "t"),
        "commonjs",
        None,
    ),
    "namespace-destructuring-write": (
        {
            "svc.ts": SVC,
            "use.ts": USE,
            "x.ts": "import * as ns from './svc';\n[ns.t] = [() => 0];\n",
        },
        ("use.ts", "t"),
        "commonjs",
        None,
    ),
    "namespace-wrapped-write": (
        {
            "svc.ts": SVC,
            "use.ts": USE,
            "x.ts": "import * as ns from './svc';\n((ns as any)).t = 0;\n",
        },
        ("use.ts", "t"),
        "commonjs",
        None,
    ),
    "namespace-computed-write": (
        {
            "svc.ts": SVC,
            "use.ts": USE,
            "x.ts": "import * as ns from './svc';\n(ns as any)['t'] = 0;\n",
        },
        ("use.ts", "t"),
        "commonjs",
        None,
    ),
    "namespace-write-in-own-file": (
        {
            "svc.ts": SVC,
            "use.ts": (
                "import * as ns from './svc';\n"
                "(ns as any).t = () => 0;\n"
                "export function u() { return ns.t(); }\n"
            ),
        },
        ("use.ts", "ns.t"),
        "commonjs",
        None,
    ),
    "export-star-as-escapes": (
        {
            "svc.ts": SVC,
            "use.ts": USE,
            "x.ts": "export * as ns from './svc';\n",
        },
        ("use.ts", "t"),
        "commonjs",
        None,
    ),
    # CommonJS reach from other files.
    "require-of-target": (
        {
            "svc.ts": SVC,
            "use.ts": USE,
            "x.js": "require('./svc').t = function () {};\n",
        },
        ("use.ts", "t"),
        "commonjs",
        None,
    ),
    "require-with-js-extension": (
        {
            "svc.ts": SVC,
            "use.ts": USE,
            "x.js": "const m = require('./svc.js');\nm.t = 1;\n",
        },
        ("use.ts", "t"),
        "commonjs",
        None,
    ),
    "require-non-literal": (
        {"svc.ts": SVC, "use.ts": USE, "x.js": "require(name).t = 1;\n"},
        ("use.ts", "t"),
        "run-tainted:dynamic-loader",
        None,
    ),
    "require-alias": (
        {
            "svc.ts": SVC,
            "use.ts": USE,
            "x.js": "const r = require;\nr('./svc').t = 1;\n",
        },
        ("use.ts", "t"),
        "run-tainted:dynamic-loader",
        None,
    ),
    "require-cache": (
        {
            "svc.ts": SVC,
            "use.ts": USE,
            "x.js": "Object.values(require.cache)[0].exports.t = 1;\n",
        },
        ("use.ts", "t"),
        "run-tainted:dynamic-loader",
        None,
    ),
    "dynamic-import-of-target": (
        {
            "svc.ts": SVC,
            "use.ts": USE,
            "x.ts": "export const p = import('./svc');\n",
        },
        ("use.ts", "t"),
        "commonjs",
        None,
    ),
    "dynamic-import-non-literal": (
        {
            "svc.ts": SVC,
            "use.ts": USE,
            "x.ts": "export const p = import(name);\n",
        },
        ("use.ts", "t"),
        "run-tainted:dynamic-loader",
        None,
    ),
    "import-equals-require": (
        {
            "svc.ts": SVC,
            "use.ts": USE,
            "x.ts": "import m = require('./svc');\nexport const k = m;\n",
        },
        ("use.ts", "t"),
        "commonjs",
        None,
    ),
    "module-children": (
        {
            "svc.ts": SVC,
            "use.ts": USE,
            "x.js": "module.children[0].exports.t = 1;\n",
        },
        ("use.ts", "t"),
        "run-tainted:module-object",
        None,
    ),
    "create-require": (
        {
            "svc.ts": SVC,
            "use.ts": USE,
            "x.ts": (
                "import { createRequire } from 'node:module';\n"
                "createRequire(import.meta.url)('./svc').t = 1;\n"
            ),
        },
        ("use.ts", "t"),
        "run-tainted:module-system",
        None,
    ),
    "main-module": (
        {
            "svc.ts": SVC,
            "use.ts": USE,
            "x.js": "process['mainModule'].require('./svc').t = 1;\n",
        },
        ("use.ts", "t"),
        "run-tainted:module-system",
        None,
    ),
    "code-evaluator": (
        {"svc.ts": SVC, "use.ts": USE, "x.js": "eval(source);\n"},
        ("use.ts", "t"),
        "run-tainted:evaluator",
        None,
    ),
    # E5-3: a file the parser cannot read is scanned as text.
    "unparsed-file-relative-literal-taints": (
        {
            "svc.ts": SVC,
            "use.ts": USE,
            "x.js": "require('./svc').t = 1;\nfunction (\n",
        },
        ("use.ts", "t"),
        "commonjs",
        None,
    ),
    "unparsed-file-trigger-spelling": (
        {"svc.ts": SVC, "use.ts": USE, "x.js": "createRequire;\nfunction (\n"},
        ("use.ts", "t"),
        "run-tainted:module-system",
        None,
    ),
    "unparsed-file-escaped-trigger-spelling": (
        {"svc.ts": SVC, "use.ts": USE, "x.js": "\\u0065val(s);\nfunction (\n"},
        ("use.ts", "t"),
        "run-tainted:evaluator",
        None,
    ),
    # CommonJS in the target module itself.
    "target-module-exports": (
        {"svc.ts": SVC + "module.exports.t = () => 0;\n", "use.ts": USE},
        ("use.ts", "t"),
        "commonjs",
        None,
    ),
    "target-exports": (
        {"svc.ts": SVC + "exports.t = () => 0;\n", "use.ts": USE},
        ("use.ts", "t"),
        "commonjs",
        None,
    ),
    "target-top-level-this": (
        {"svc.ts": SVC + "this.t = () => 0;\n", "use.ts": USE},
        ("use.ts", "t"),
        "commonjs",
        None,
    ),
    "target-top-level-arguments": (
        {"svc.ts": SVC + "arguments[0].t = () => 0;\n", "use.ts": USE},
        ("use.ts", "t"),
        "commonjs",
        None,
    ),
    "target-export-equals": (
        {"svc.ts": "function t() { return 1; }\nexport = t;\n", "use.ts": USE},
        ("use.ts", "t"),
        "commonjs",
        None,
    ),
    "target-script": (
        {"svc.js": "function t() { return 1; }\n", "use.ts": USE},
        ("use.ts", "t"),
        "commonjs",
        None,
    ),
    # Specifiers and quoted names that do not decode exactly, or that
    # toolchains read differently (9.2).
    "import-attributes": (
        {
            "svc.ts": SVC,
            "use.ts": (
                "import { t } from './svc' with { type: 'json' };\n"
                "export function u() { return t(); }\n"
            ),
        },
        ("use.ts", "t"),
        "unknown-variant",
        None,
    ),
    "specifier-legacy-octal": (
        {
            "svc.ts": SVC,
            "use.ts": (
                "import { t } from './\\163vc';\nexport function u() { return t(); }\n"
            ),
        },
        ("use.ts", "t"),
        "unmapped",
        None,
    ),
    "import-name-lone-surrogate": (
        {
            "svc.ts": SVC,
            "use.ts": (
                "import { '\\uD800' as t } from './svc';\n"
                "export function u() { return t(); }\n"
            ),
        },
        ("use.ts", "t"),
        "unmapped",
        None,
    ),
    "export-name-lone-surrogate": (
        {
            "svc.ts": SVC + "export { t as '\\uD800' };\n",
            "use.ts": USE,
        },
        ("use.ts", "t"),
        "export-not-found",
        None,
    ),
    "export-name-escape-is-not-raw-text": (
        {
            "svc.ts": "function t() { return 1; }\nexport { t as '\\x75' };\n",
            "use.ts": USE,
        },
        ("use.ts", "t"),
        "export-not-found",
        None,
    ),
    "specifier-case-fold": (
        {"svc.ts": SVC, "use.ts": USE.replace("./svc", "./SVC")},
        ("use.ts", "t"),
        "unknown-variant",
        None,
    ),
    "specifier-query": (
        {"svc.ts": SVC, "use.ts": USE.replace("./svc", "./svc?raw")},
        ("use.ts", "t"),
        "unknown-variant",
        None,
    ),
    "specifier-percent": (
        {"svc.ts": SVC, "use.ts": USE.replace("./svc", "./%73vc")},
        ("use.ts", "t"),
        "unknown-variant",
        None,
    ),
    "specifier-empty-segment": (
        {"svc.ts": SVC, "use.ts": USE.replace("./svc", ".//svc")},
        ("use.ts", "t"),
        "unknown-variant",
        None,
    ),
    "specifier-trailing-slash": (
        {"lib/index.ts": SVC, "use.ts": USE.replace("./svc", "./lib/")},
        ("use.ts", "t"),
        "unknown-variant",
        None,
    ),
    "specifier-outside-root": (
        {"svc.ts": SVC, "use.ts": USE.replace("./svc", "../svc")},
        ("use.ts", "t"),
        "outside-root",
        None,
    ),
    "specifier-absolute": (
        {"svc.ts": SVC, "use.ts": USE.replace("./svc", "/svc")},
        ("use.ts", "t"),
        "external-module",
        None,
    ),
    "specifier-node-scheme": (
        {"svc.ts": SVC, "use.ts": USE.replace("./svc", "node:svc")},
        ("use.ts", "t"),
        "external-module",
        None,
    ),
    "index-candidate-in-skipped-directory": (
        {"build.ts": SVC, "use.ts": USE.replace("./svc", "./build")},
        ("use.ts", "t"),
        "unknown-variant",
        None,
    ),
    "directory-named-like-the-js-file": (
        {
            "svc.ts": SVC,
            "svc.js/index.ts": "export function t() { return 6; }\n",
            "use.ts": USE.replace("./svc", "./svc.js"),
        },
        ("use.ts", "t"),
        "ambiguous-extension",
        None,
    ),
    "platform-suffix-sibling": (
        {
            "svc.ts": SVC,
            "svc.ios.ts": "export function t() { return 7; }\n",
            "use.ts": USE,
        },
        ("use.ts", "t"),
        "ambiguous-extension",
        None,
    ),
    "platform-suffix-index-sibling": (
        {
            "lib/index.ts": SVC,
            "lib/index.native.js": "export function t() { return 7; }\n",
            "use.ts": USE.replace("./svc", "./lib"),
        },
        ("use.ts", "t"),
        "ambiguous-extension",
        None,
    ),
    "specifier-uppercase-extension": (
        {"svc.ts": SVC, "use.ts": USE.replace("./svc", "./svc.JS")},
        ("use.ts", "t"),
        "unknown-variant",
        None,
    ),
    "directory-with-package-json": (
        {
            "lib/index.ts": SVC,
            "lib/package.json": '{"main": "./other.js"}\n',
            "use.ts": USE.replace("./svc", "./lib"),
        },
        ("use.ts", "t"),
        "unknown-variant",
        None,
    ),
    "javascript-filter-leaves-ts-uncollected": (
        {
            "svc.js": SVC,
            "use.js": USE,
            "other.js": "export function t() { return 2; }\n",
            "more.js": "export function t() { return 3; }\n",
        },
        ("use.js", "t"),
        "unknown-variant",
        "javascript",
    ),
    # Importer side.
    "importer-reassigns-the-import": (
        {
            "svc.ts": SVC,
            "use.ts": USE + "export function w() { (t as any) = 1; }\n",
        },
        ("use.ts", "t"),
        "reassigned",
        None,
    ),
}


@pytest.mark.parametrize("case", sorted(NEAR_MISSES))
def test_tier2_near_misses_keep_their_off_mode_edge(tmp_path: Path, case: str) -> None:
    files, (file, reference), reason, language = NEAR_MISSES[case]
    root = _write(tmp_path, {**OTHERS, **files})
    off, structural, on, label = _run(root, file, reference, language)
    assert off["resolution"] == "ambiguous", case
    assert len(off["candidates"]) >= 2, case
    assert structural == off, case
    assert on == off, (case, label)
    assert label == f"none({reason})", case
    assert reason in KNOWN_NONE_REASONS


# Member calls other than ``ns.f()`` on a namespace import stay untouched.
INELIGIBLE_MEMBER_CALLS = {
    "longer-chain": (
        "import * as ns from './svc';\nexport function u() { return ns.t.call(0); }\n",
        "ns.t.call",
    ),
    "named-import-member": (
        "import { t } from './svc';\nexport function u() { return t.call(0); }\n",
        "t.call",
    ),
}


@pytest.mark.parametrize("case", sorted(INELIGIBLE_MEMBER_CALLS))
def test_other_member_calls_are_not_eligible(tmp_path: Path, case: str) -> None:
    use, reference = INELIGIBLE_MEMBER_CALLS[case]
    root = _write(
        tmp_path,
        {
            "svc.ts": SVC + "export function call() { return 1; }\n",
            "other.ts": "export function call() { return 2; }\nexport function t() { return 5; }\n",
            # A candidate of another family: were the call eligible, the
            # family filter would narrow it.
            "p.py": "def call():\n    return 3\n\n\ndef t():\n    return 4\n",
            "use.ts": use,
        },
    )
    graph_off = extract_symbol_graph(root)
    graph_on = extract_symbol_graph(root, call_resolution=MODE)
    assert graph_on["relationships"] == graph_off["relationships"]
    assert any(
        edge["reference"] == reference for edge in graph_off["relationships"]
    ), case


def test_optional_namespace_call_fails_closed(tmp_path: Path) -> None:
    """``ns?.t()`` carries no member in the facts, so the reference and the
    tree disagree and the edge fails closed."""
    root = _write(
        tmp_path,
        {
            **OTHERS,
            "svc.ts": SVC,
            "use.ts": (
                "import * as ns from './svc';\n"
                "export function u() { return ns?.t(); }\n"
            ),
        },
    )
    off = extract_symbol_graph(root)
    on = extract_symbol_graph(root, call_resolution=MODE)
    assert on["relationships"] == off["relationships"]


# ---------------------------------------------------------------------------
# Units


DECODED = {
    "'abc'": "abc",
    '"a\\"b"': 'a"b',
    "'\\x41\\u0042\\u{43}'": "ABC",
    "'\\u{1F600}'": "\U0001f600",
    "'\\uD83D\\uDE00'": "\U0001f600",
    "'a\\\nb'": "ab",
    "'a\\\r\nb'": "ab",
    "'a\\ b'": "ab",
    "'\\0'": "\0",
    "'\\q'": "q",
    "'\\b\\f\\n\\r\\t\\v'": "\b\f\n\r\t\v",
    "'a b'": "a b",
}
UNDECODED = [
    "'\\1'",
    "'\\01'",
    "'\\8'",
    "'\\x4'",
    "'\\u12'",
    "'\\u{110000}'",
    "'\\u{}'",
    "'\\uD800'",
    "'\\uDC00x'",
    "'a\nb'",
    "'abc\"",
    "abc",
    "'a'b'",
]


@pytest.mark.parametrize("raw", sorted(DECODED))
def test_string_literals_decode_exactly(raw: str) -> None:
    assert decode_js_string(raw) == DECODED[raw]


@pytest.mark.parametrize("raw", UNDECODED)
def test_string_literals_that_do_not_decode_fail_closed(raw: str) -> None:
    assert decode_js_string(raw) is None


def test_copied_collection_constants_match_the_collector() -> None:
    from chunker.auto import ZeroConfigAPI

    assert modules.SKIPPED_DIRECTORIES == SKIP_PARTS
    for extension, language in modules.JS_EXTENSION_LANGUAGES.items():
        assert ZeroConfigAPI.EXTENSION_MAP[extension] == language
    js_family = {
        extension
        for extension, language in ZeroConfigAPI.EXTENSION_MAP.items()
        if language in ("javascript", "typescript", "tsx")
    }
    assert js_family == set(modules.JS_EXTENSION_LANGUAGES)


CANDIDATES = {
    ("./p.js", "typescript"): ("p.ts", "p.tsx", "p.d.ts", "p.js"),
    ("./p.jsx", "typescript"): ("p.tsx", "p.d.ts", "p.jsx"),
    ("./p.ts", "typescript"): ("p.ts",),
    ("./p.d.ts", "typescript"): ("p.d.ts",),
    ("./p.js", "javascript"): ("p.js",),
    ("./p", "javascript"): (
        "p.ts",
        "p.tsx",
        "p.d.ts",
        "p.js",
        "p.jsx",
        "p/index.ts",
        "p/index.tsx",
        "p/index.d.ts",
        "p/index.js",
        "p/index.jsx",
    ),
}


@pytest.mark.parametrize(("specifier", "language"), sorted(CANDIDATES))
def test_candidate_lists_follow_typescript_order(specifier: str, language: str) -> None:
    candidates, reason = modules.candidate_list(specifier, "use.ts", language)
    assert reason is None
    expected = CANDIDATES[(specifier, language)]
    assert candidates[: len(expected)] == expected
    if specifier.endswith((".js", ".jsx")) and language == "typescript":
        # The directory of that name, which TypeScript tries after the file.
        assert set(candidates[len(expected) :]) == {
            f"{specifier[2:]}/index{ext}"
            for ext in (".ts", ".tsx", ".d.ts", ".js", ".jsx")
        }
    else:
        assert len(candidates) == len(expected)


@pytest.mark.parametrize(
    ("specifier", "reason"),
    [
        ("lodash", "external-module"),
        ("#internal", "external-module"),
        ("node:fs", "external-module"),
        ("https://x/y.js", "external-module"),
        ("../x", "outside-root"),
        ("./a/../../x", "unknown-variant"),
        ("../../x", "outside-root"),
        ("./x.mjs", "unknown-variant"),
        ("./x.cts", "unknown-variant"),
        ("./x\\y", "unknown-variant"),
        ("./x#y", "unknown-variant"),
    ],
)
def test_specifiers_that_never_resolve(specifier: str, reason: str) -> None:
    assert modules.candidate_list(specifier, "use.ts", "typescript")[1] == reason


def test_namespace_binding_called_directly_is_non_callable() -> None:
    run = modules.ModuleRun(modules.ModuleIndex.build(["svc.ts"], None), {})
    binding = {"source": "./svc", "name": "*", "form": "namespace"}
    assert modules.resolve_import(run, "use.ts", "typescript", binding, None) == {
        "outcome": "none",
        "reason": "non-callable",
    }
    named = {"source": "./svc", "name": "t", "form": "named"}
    assert modules.resolve_import(run, "use.ts", "typescript", named, "t") == {
        "outcome": "none",
        "reason": "export-not-found",
    }


def test_member_must_match_the_tree() -> None:
    """A dotted reference whose member the facts do not record fails closed."""
    outcome = {
        "outcome": "import",
        "binding": {"source": "./svc", "name": "*", "form": "namespace"},
    }
    file_context = engine.FileContext(
        language="typescript", supported=True, bindings={}, declarations={}
    )
    context = engine.RunContext(
        mode=MODE,
        files={},
        symbol_lookup={},
        modules=modules.ModuleRun(modules.ModuleIndex.build([], None), {}),
    )
    proven, final, rules = engine.proof(
        outcome, MODE, file_context, {}, context=context, member="t"
    )
    assert (proven, final, rules) == (
        frozenset(),
        {"outcome": "none", "reason": "export-not-found"},
        (),
    )


@pytest.mark.parametrize(
    "bindings",
    [
        {},
        {"stars": [], "commonjs": False, "opaque": False, "taints": []},
        {
            "stars": [],
            "commonjs": False,
            "opaque": False,
            "symlink": False,
            "taints": [],
            "ns_uses": [],
            "shutoff": ["no-such-cause"],
        },
        {
            "stars": [],
            "commonjs": False,
            "opaque": False,
            "symlink": False,
            "taints": [],
            "ns_uses": [["./svc", "t", "write"]],
            "shutoff": [],
        },
        {
            "stars": [1],
            "commonjs": False,
            "opaque": False,
            "taints": [],
            "taint_all": False,
        },
        {
            "stars": [],
            "commonjs": 0,
            "opaque": False,
            "taints": [],
            "taint_all": False,
        },
    ],
)
def test_malformed_module_bindings_are_rejected(bindings: dict[str, Any]) -> None:
    assert not valid_module_bindings(bindings)


def test_malformed_tier2_facts_are_a_safe_miss(tmp_path: Path) -> None:
    root = _write(tmp_path, {"svc.ts": SVC})
    facts = extract_symbol_facts_for_file(root / "svc.ts", root, call_resolution=MODE)
    scope = facts["scope_facts"]
    assert valid_scope_facts(scope, "typescript")
    for broken in (
        {**scope, "exports": {"t": {"kind": "local"}}},
        {**scope, "exports": {"t": {"kind": "none", "reason": "no-such-reason"}}},
        {**scope, "exports": {"t": {"kind": "reexport", "source": 1, "name": "t"}}},
        {**scope, "module_bindings": {}},
    ):
        assert not valid_scope_facts(broken, "typescript")


def test_export_table_of_a_module(tmp_path: Path) -> None:
    root = _write(
        tmp_path,
        {
            "m.ts": (
                "export function a() {}\n"
                "function b() {}\n"
                "export { b as 'b-b', b as default };\n"
                "export interface a {}\n"
                "export interface I {}\n"
                "export * from './s';\n"
                "export { x as y } from './r';\n"
                "export * as ns from './n';\n"
                "export as namespace UMD;\n"
            ),
        },
    )
    facts = extract_symbol_facts_for_file(root / "m.ts", root, call_resolution=MODE)
    scope = facts["scope_facts"]
    exports = scope["exports"]
    assert sorted(exports) == ["I", "a", "b-b", "default", "ns", "y"]
    assert exports["a"]["kind"] == "local"
    assert exports["a"]["outcome"]["outcome"] == "local"
    assert exports["I"] == {"kind": "none", "reason": "type-only"}
    assert exports["ns"] == {"kind": "none", "reason": "namespace-export"}
    assert exports["y"] == {"kind": "reexport", "source": "./r", "name": "x"}
    assert exports["a"]["this"] is False
    assert scope["module_bindings"] == {
        "stars": ["./s"],
        "commonjs": False,
        "opaque": False,
        "symlink": False,
        "taints": ["./n"],
        "imports": ["./n", "./r", "./s"],
        "ns_uses": [],
        "shutoff": [],
    }


def test_unknown_export_statement_makes_the_module_opaque(tmp_path: Path) -> None:
    """An export statement outside the closed list fails every lookup in its
    module closed (``export { "a" }`` without ``from`` is not valid JS)."""
    root = _write(tmp_path, {"m.ts": "function t() {}\nexport { 'a' };\n"})
    facts = extract_symbol_facts_for_file(root / "m.ts", root, call_resolution=MODE)
    assert facts["scope_facts"]["module_bindings"]["opaque"] is True


def test_tier2_in_boundary_ir_incremental_runs(tmp_path: Path) -> None:
    """Cold and warm incremental runs agree, and editing the target module
    re-runs the resolution (rules run at assembly, 4.4)."""
    from chunker.boundary import extract_boundary_ir

    root = _write(tmp_path / "tree", {**OTHERS, "svc.ts": SVC, "use.ts": USE})
    cache_dir = tmp_path / "cache"

    def run(**kwargs: Any) -> dict[str, Any]:
        return extract_boundary_ir(root, call_resolution=MODE, **kwargs)

    def use_edge(document: dict[str, Any]) -> dict[str, Any]:
        (edge,) = [
            edge
            for edge in document["edges"]
            if edge["type"] == "calls"
            and edge["reference"] == "t"
            and edge["file"] == "use.ts"
        ]
        return edge

    cold = run()
    assert use_edge(cold)["resolution"] == "resolved"
    assert use_edge(cold)["provenance"]["call_rules"] == ["t2.import"]
    incremental = run(incremental=True, cache_dir=cache_dir)
    warm = run(incremental=True, cache_dir=cache_dir)
    assert incremental == cold
    assert warm == cold
    (root / "svc.ts").write_text(SVC + "t = () => 9;\n", encoding="utf-8")
    edited = run(incremental=True, cache_dir=cache_dir)
    assert use_edge(edited)["resolution"] == "ambiguous"
    assert edited == run()


# ---------------------------------------------------------------------------
# PR 5 fold 1 (the president's rulings E5-1..E5-5 on #703). Each case is a
# panel repro or a write form of one, on trees the tests write (11.2).

NS_USE = "import * as ns from './svc';\nexport function u() { return ns.t(); }\n"
FOLD1_NEAR_MISSES: dict[
    str, tuple[dict[str, str], tuple[str, str], str, str | None]
] = {
    # E5-1, A1: a write to an import binding is ``svc_1.t = …`` under
    # CommonJS emit, so it taints the exporting module, in any file.
    "import-write-cast": (
        {
            "svc.ts": SVC,
            "use.ts": USE,
            "evil.ts": (
                "import { t } from './svc';\n"
                "export function w() { (t as any) = () => 9; }\n"
            ),
        },
        ("use.ts", "t"),
        "commonjs",
        None,
    ),
    "import-write-js": (
        {
            "svc.ts": SVC,
            "use.ts": USE,
            "evil.js": "import { t } from './svc';\nexport function w() { t = 9; }\n",
        },
        ("use.ts", "t"),
        "commonjs",
        None,
    ),
    "import-write-default": (
        {
            "svc.ts": SVC + "export default function d() { return 4; }\n",
            "use.ts": USE,
            "evil.js": "import d from './svc';\nexport function w() { d = 9; }\n",
        },
        ("use.ts", "t"),
        "commonjs",
        None,
    ),
    "import-write-compound": (
        {
            "svc.ts": SVC,
            "use.ts": USE,
            "evil.js": "import { t } from './svc';\nexport function w() { t += 1; }\n",
        },
        ("use.ts", "t"),
        "commonjs",
        None,
    ),
    "import-write-logical": (
        {
            "svc.ts": SVC,
            "use.ts": USE,
            "evil.js": "import { t } from './svc';\nexport function w() { t ||= 1; }\n",
        },
        ("use.ts", "t"),
        "commonjs",
        None,
    ),
    "import-write-update": (
        {
            "svc.ts": SVC,
            "use.ts": USE,
            "evil.js": "import { t } from './svc';\nexport function w() { t++; }\n",
        },
        ("use.ts", "t"),
        "commonjs",
        None,
    ),
    "import-write-destructuring": (
        {
            "svc.ts": SVC,
            "use.ts": USE,
            "evil.js": (
                "import { t } from './svc';\n"
                "export function w(o) { ({ t } = o); [t] = [o]; }\n"
            ),
        },
        ("use.ts", "t"),
        "commonjs",
        None,
    ),
    "import-write-for-of": (
        {
            "svc.ts": SVC,
            "use.ts": USE,
            "evil.js": (
                "import { t } from './svc';\n"
                "export function w(xs) { for (t of xs) {} }\n"
            ),
        },
        ("use.ts", "t"),
        "commonjs",
        None,
    ),
    # E5-1, A2/B-5: ``ns.f()`` passes the exports object as ``this``.
    "namespace-call-of-this-function": (
        {
            "svc.ts": SVC + "export function reset(this: any) { this.t = () => 9; }\n",
            "use.ts": USE,
            "mut.ts": "import * as ns from './svc';\nexport function m() { ns.reset(); }\n",
        },
        ("use.ts", "t"),
        "commonjs",
        None,
    ),
    "namespace-call-this-in-nested-arrow": (
        {
            "svc.ts": SVC
            + "export function reset(this: any) { [1].map(() => this); }\n",
            "use.ts": USE,
            "mut.ts": "import * as ns from './svc';\nexport function m() { (ns.reset)(); }\n",
        },
        ("use.ts", "t"),
        "commonjs",
        None,
    ),
    "namespace-call-this-through-reexport": (
        {
            "impl.ts": "export function reset(this: any) { this.t = () => 9; }\n",
            "svc.ts": SVC + "export { reset } from './impl';\n",
            "use.ts": USE,
            "mut.ts": "import * as ns from './svc';\nexport function m() { ns.reset(); }\n",
        },
        ("use.ts", "t"),
        "commonjs",
        None,
    ),
    "namespace-define-getter": (
        {
            "svc.ts": SVC,
            "use.ts": USE,
            "mut.js": (
                "import * as ns from './svc';\n"
                "export function m() { ns.__defineGetter__('t', () => 0); }\n"
            ),
        },
        ("use.ts", "t"),
        "commonjs",
        None,
    ),
    "namespace-proto-read": (
        {
            "svc.ts": SVC,
            "use.ts": USE,
            "mut.ts": "import * as ns from './svc';\nexport const p = ns.__proto__;\n",
        },
        ("use.ts", "t"),
        "commonjs",
        None,
    ),
    "namespace-unknown-member-read": (
        {
            "svc.ts": SVC,
            "use.ts": USE,
            "mut.ts": "import * as ns from './svc';\nexport const p = (ns as any).missing;\n",
        },
        ("use.ts", "t"),
        "commonjs",
        None,
    ),
    "namespace-augmented-member-write": (
        {
            "svc.ts": SVC,
            "use.ts": USE,
            "mut.js": "import * as ns from './svc';\nns.t += 1;\n",
        },
        ("use.ts", "t"),
        "commonjs",
        None,
    ),
    "namespace-logical-member-write": (
        {
            "svc.ts": SVC,
            "use.ts": USE,
            "mut.js": "import * as ns from './svc';\nns.t &&= 1;\n",
        },
        ("use.ts", "t"),
        "commonjs",
        None,
    ),
    "namespace-binding-write": (
        {
            "svc.ts": SVC,
            "use.ts": USE,
            "mut.js": "import * as ns from './svc';\nexport function m() { ns = 1; }\n",
        },
        ("use.ts", "t"),
        "commonjs",
        None,
    ),
    # E5-1, B-4: module-level ``this`` wherever a top-level evaluation
    # reaches it.
    "module-this-in-computed-key": (
        {
            "svc.ts": SVC
            + "export const o = { [((this as any).t = () => 9, 'k')]() {} };\n",
            "use.ts": USE,
        },
        ("use.ts", "t"),
        "commonjs",
        None,
    ),
    "module-this-in-class-computed-key": (
        {
            "svc.js": SVC + "export class K { [(this.t = 0, 'k')]() {} }\n",
            "use.ts": USE,
        },
        ("use.ts", "t"),
        "commonjs",
        None,
    ),
    "module-this-in-field-computed-key": (
        {
            "svc.js": SVC + "export class K { [(this.t = 0, 'k')] = 1; }\n",
            "use.ts": USE,
        },
        ("use.ts", "t"),
        "commonjs",
        None,
    ),
    "module-this-in-extends": (
        {
            "svc.js": SVC + "export class K extends (this.t = 0, Object) {}\n",
            "use.ts": USE,
        },
        ("use.ts", "t"),
        "commonjs",
        None,
    ),
    "module-this-in-arrow-default": (
        {
            "svc.js": SVC + "((a = (this.t = 0)) => a)();\n",
            "use.ts": USE,
        },
        ("use.ts", "t"),
        "commonjs",
        None,
    ),
    # E5-3: each run-wide cause gives its own reason.
    "timer-string": (
        {"svc.ts": SVC, "use.ts": USE, "x.js": "setTimeout('code', 1);\n"},
        ("use.ts", "t"),
        "run-tainted:evaluator",
        None,
    ),
    "timer-free-name": (
        {"svc.ts": SVC, "use.ts": USE, "x.js": "setTimeout(handler, 1);\n"},
        ("use.ts", "t"),
        "run-tainted:evaluator",
        None,
    ),
    "function-constructor-route": (
        {"svc.ts": SVC, "use.ts": USE, "x.js": "(() => 0).constructor('s')();\n"},
        ("use.ts", "t"),
        "run-tainted:evaluator",
        None,
    ),
    "require-of-module": (
        {"svc.ts": SVC, "use.ts": USE, "x.js": "const m = require('module');\n"},
        ("use.ts", "t"),
        "run-tainted:module-system",
        None,
    ),
    "dynamic-import-of-node-module": (
        {
            "svc.ts": SVC,
            "use.ts": USE,
            "x.ts": "export const p = import('node:module');\n",
        },
        ("use.ts", "t"),
        "run-tainted:module-system",
        None,
    ),
    "import-from-module": (
        {
            "svc.ts": SVC,
            "use.ts": USE,
            "x.ts": "import m from 'module';\nexport const k = m;\n",
        },
        ("use.ts", "t"),
        "run-tainted:module-system",
        None,
    ),
    "undecodable-import-specifier": (
        {
            "svc.ts": SVC,
            "use.ts": USE,
            "x.ts": "import k from './\\8';\nexport const j = k;\n",
        },
        ("use.ts", "t"),
        "run-tainted:module-system",
        None,
    ),
    "get-builtin-module-identifier": (
        {"svc.ts": SVC, "use.ts": USE, "x.js": "getBuiltinModule('fs');\n"},
        ("use.ts", "t"),
        "run-tainted:module-system",
        None,
    ),
    "main-module-identifier": (
        {"svc.ts": SVC, "use.ts": USE, "x.js": "export const m = mainModule;\n"},
        ("use.ts", "t"),
        "run-tainted:module-system",
        None,
    ),
    "create-require-identifier": (
        {"svc.ts": SVC, "use.ts": USE, "x.js": "export const r = createRequire;\n"},
        ("use.ts", "t"),
        "run-tainted:module-system",
        None,
    ),
    "module-system-name-in-template": (
        {"svc.ts": SVC, "use.ts": USE, "x.js": "export const k = `main\\x4dodule`;\n"},
        ("use.ts", "t"),
        "run-tainted:module-system",
        None,
    ),
    "module-system-name-legacy-octal": (
        {"svc.ts": SVC, "use.ts": USE, "x.js": "const k = 'mainM\\157dule';\n"},
        ("use.ts", "t"),
        "run-tainted:module-system",
        None,
    ),
    "bun-import-meta-require": (
        {
            "svc.ts": SVC,
            "use.ts": USE,
            "x.ts": "export const m = import.meta.require('./other');\n",
        },
        ("use.ts", "t"),
        "run-tainted:dynamic-loader",
        None,
    ),
    "module-object-other-than-exports": (
        {"svc.ts": SVC, "use.ts": USE, "x.js": "module.require('./svc');\n"},
        ("use.ts", "t"),
        "run-tainted:module-object",
        None,
    ),
    "require-main-require": (
        {"svc.ts": SVC, "use.ts": USE, "x.js": "require.main.require(name);\n"},
        ("use.ts", "t"),
        "run-tainted:dynamic-loader",
        None,
    ),
    "module-handed-on": (
        {"svc.ts": SVC, "use.ts": USE, "x.js": "register(module);\n"},
        ("use.ts", "t"),
        "run-tainted:module-object",
        None,
    ),
    # E5-4: a taint whose specifier the resolver rejects still taints.
    "rejected-taint-trailing-slash": (
        {
            "lib/index.ts": SVC,
            "use.ts": USE.replace("./svc", "./lib"),
            "mut.ts": (
                "import * as ns from './lib/';\n"
                "export function m() { (ns as any).t = 0; }\n"
            ),
        },
        ("use.ts", "t"),
        "commonjs",
        None,
    ),
    "rejected-taint-dot": (
        {
            "lib/index.ts": SVC,
            "use.ts": USE.replace("./svc", "./lib"),
            "lib/mut.ts": (
                "import * as ns from '.';\nexport function m() { (ns as any).t = 0; }\n"
            ),
        },
        ("use.ts", "t"),
        "commonjs",
        None,
    ),
    "rejected-taint-query": (
        {"svc.ts": SVC, "use.ts": USE, "x.js": "require('./svc?x').t = 0;\n"},
        ("use.ts", "t"),
        "commonjs",
        None,
    ),
    "rejected-taint-hash": (
        {"svc.ts": SVC, "use.ts": USE, "x.js": "require('./svc#x').t = 0;\n"},
        ("use.ts", "t"),
        "commonjs",
        None,
    ),
    "rejected-taint-case": (
        {"svc.ts": SVC, "use.ts": USE, "x.js": "require('./SVC.JS').t = 0;\n"},
        ("use.ts", "t"),
        "commonjs",
        None,
    ),
    "rejected-taint-percent": (
        {"svc.ts": SVC, "use.ts": USE, "x.js": "require('./%73vc').t = 0;\n"},
        ("use.ts", "t"),
        "commonjs",
        None,
    ),
    "rejected-taint-backslash": (
        {"svc.ts": SVC, "use.ts": USE, "x.js": "require('.\\\\svc').t = 0;\n"},
        ("use.ts", "t"),
        "commonjs",
        None,
    ),
    "rejected-taint-dot-segment": (
        {"svc.ts": SVC, "use.ts": USE, "sub/x.js": "require('./../svc').t = 0;\n"},
        ("use.ts", "t"),
        "commonjs",
        None,
    ),
    "rejected-taint-outside-root": (
        {"svc.ts": SVC, "use.ts": USE, "x.js": "require('../elsewhere/svc').t = 0;\n"},
        ("use.ts", "t"),
        "run-tainted:unresolvable-writer",
        None,
    ),
    "template-require-taints": (
        {"svc.ts": SVC, "use.ts": USE, "x.js": "require(`./svc`).t = 0;\n"},
        ("use.ts", "t"),
        "commonjs",
        None,
    ),
    # E5-5: cheap fail-closed rules.
    "dot-segment-directory": (
        {
            "lib.ts": SVC,
            "lib/other.ts": "export function t() { return 8; }\n",
            "use.ts": USE.replace("./svc", "./lib/."),
        },
        ("use.ts", "t"),
        "unknown-variant",
        None,
    ),
    "dotdot-segment-directory": (
        {
            "pkg.ts": SVC,
            "pkg/x/a.ts": "export {};\n",
            "use.ts": USE.replace("./svc", "./pkg/x/.."),
        },
        ("use.ts", "t"),
        "unknown-variant",
        None,
    ),
    "bare-dot": (
        {"index.ts": SVC, "use.ts": USE.replace("./svc", ".")},
        ("use.ts", "t"),
        "unknown-variant",
        None,
    ),
    "bare-dotdot": (
        {"index.ts": SVC, "sub/use.ts": USE.replace("./svc", "..")},
        ("sub/use.ts", "t"),
        "unknown-variant",
        None,
    ),
    "exact-file-of-another-extension": (
        {
            "svc.css": ".t { color: red; }\n",
            "svc.css.ts": SVC,
            "use.ts": USE.replace("./svc", "./svc.css"),
        },
        ("use.ts", "t"),
        "unknown-variant",
        None,
    ),
    "non-inert-sibling-segment": (
        {
            "svc.ts": SVC,
            "svc.foo.ts": "export function t() { return 7; }\n",
            "use.ts": USE,
        },
        ("use.ts", "t"),
        "ambiguous-extension",
        None,
    ),
    "attributes-on-a-reexport-hop": (
        {
            "svc.ts": SVC,
            "index.ts": "import { t } from './svc' with { type: 'json' };\nexport { t };\n",
            "use.ts": USE.replace("./svc", "./index"),
        },
        ("use.ts", "t"),
        "unknown-variant",
        None,
    ),
    "attributes-on-export-from": (
        {
            "svc.ts": SVC,
            "index.ts": "export { t } from './svc' with { type: 'json' };\n",
            "use.ts": USE.replace("./svc", "./index"),
        },
        ("use.ts", "t"),
        "export-not-found",
        None,
    ),
    "declare-global-export-makes-the-module-opaque": (
        {
            "svc.ts": SVC + "export declare global { function q(): void }\n",
            "use.ts": USE,
        },
        ("use.ts", "t"),
        "export-not-found",
        None,
    ),
}

FOLD1_POSITIVES: dict[str, tuple[dict[str, str], tuple[str, str], str, list[str]]] = {
    "write-to-a-shadowing-local-is-not-an-import-write": (
        {
            "svc.ts": SVC,
            "use.ts": USE,
            "w.js": "import { t } from './svc';\nexport function w(t) { t = 1; }\n",
        },
        ("use.ts", "t"),
        "svc.ts",
        [],
    ),
    "namespace-call-of-this-free-function": (
        {"svc.ts": SVC, "use.ts": NS_USE},
        ("use.ts", "ns.t"),
        "svc.ts",
        [],
    ),
    "this-inside-functions-and-class-members-is-not-module-level": (
        {
            "svc.ts": SVC
            + "export function f(this: any) { return this; }\n"
            + "export class K { a = this; static { this.b = 1; } m() { return this; } }\n",
            "use.ts": USE,
        },
        ("use.ts", "t"),
        "svc.ts",
        [],
    ),
    "local-module-and-require-names": (
        {
            "svc.ts": SVC,
            "use.ts": USE,
            "x.ts": (
                "export function plan(module: string) { return module.length; }\n"
                "export function load(require: any, n: string) { return require(n); }\n"
                "export function e(exports: any) { exports.x = 1; }\n"
                "export function g() { const createRequire = 1; return createRequire; }\n"
            ),
        },
        ("use.ts", "t"),
        "svc.ts",
        [],
    ),
    "sleep-idiom-and-global-object-reads": (
        {
            "svc.ts": SVC,
            "use.ts": USE,
            "x.ts": (
                "export const sleep = (ms: number) =>\n"
                "  new Promise((r) => setTimeout(r, ms));\n"
                "export const w = typeof window !== 'undefined' ? window : undefined;\n"
                "export const g = globalThis;\n"
            ),
        },
        ("use.ts", "t"),
        "svc.ts",
        [],
    ),
    "type-position-import-is-erased": (
        {
            "svc.ts": SVC,
            "use.ts": USE,
            "x.ts": "export let a: typeof import('./svc');\n",
        },
        ("use.ts", "t"),
        "svc.ts",
        [],
    ),
    "namespace-extends-and-jsx-reads": (
        {
            "svc.tsx": SVC
            + "export class Base {}\nexport function Comp() { return null; }\n",
            "use.tsx": (
                "import * as ns from './svc';\n"
                "export class C extends ns.Base {}\n"
                "export const e = <ns.Comp />;\n"
                "export const f = <ns.Comp></ns.Comp>;\n"
                "export function u() { return ns.t(); }\n"
            ),
            "other.tsx": "export function t() { return 2; }\n",
        },
        ("use.tsx", "ns.t"),
        "svc.tsx",
        [],
    ),
    "inert-commonjs-idioms": (
        {
            "svc.ts": SVC,
            "use.ts": USE,
            "x.js": (
                "if (require.main === module) { main(); }\n"
                "const here = require.resolve('./other');\n"
                "const cjs = typeof require !== 'undefined' && typeof module;\n"
            ),
        },
        ("use.ts", "t"),
        "svc.ts",
        [],
    ),
    "saved-and-restored-timer": (
        {
            "svc.ts": SVC,
            "use.ts": USE,
            "x.ts": (
                "const saved = globalThis.setInterval;\n"
                "(globalThis as any).setInterval = (fn: () => unknown) => 0;\n"
                "globalThis.setInterval = saved;\n"
            ),
        },
        ("use.ts", "t"),
        "svc.ts",
        [],
    ),
    "unparsed-file-without-triggers-or-literals": (
        {"svc.ts": SVC, "use.ts": USE, "x.js": "function (\n"},
        ("use.ts", "t"),
        "svc.ts",
        [],
    ),
}


@pytest.mark.parametrize("case", sorted(FOLD1_NEAR_MISSES))
def test_fold1_near_misses_keep_their_off_mode_edge(tmp_path: Path, case: str) -> None:
    files, (file, reference), reason, language = FOLD1_NEAR_MISSES[case]
    root = _write(tmp_path, {**OTHERS, **files})
    off, structural, on, label = _run(root, file, reference, language)
    assert off["resolution"] == "ambiguous", case
    assert structural == off, case
    assert on == off, (case, label)
    assert label == f"none({reason})", case
    assert reason in KNOWN_NONE_REASONS


@pytest.mark.parametrize("case", sorted(FOLD1_POSITIVES))
def test_fold1_positives_resolve_end_to_end(tmp_path: Path, case: str) -> None:
    files, (file, reference), target, group_rules = FOLD1_POSITIVES[case]
    root = _write(tmp_path, {**OTHERS, **files})
    off, structural, on, label = _run(root, file, reference)
    assert off["resolution"] == "ambiguous", case
    assert structural == off, case
    assert on["resolution"] == "resolved", (case, label)
    assert _resolved_file(on, root) == target, case
    binding_rule = "t2.namespace" if "." in reference else "t2.import"
    assert on["provenance"]["call_rules"] == [binding_rule, *group_rules], case


def test_inert_sibling_segments_are_a_closed_list() -> None:
    """Q1 (keep, all panels): the allow-list is closed; any other segment,
    a platform name or not, fails closed."""
    assert (
        frozenset(
            {
                "test",
                "spec",
                "stories",
                "story",
                "bench",
                "d",
                "types",
                "styles",
                "mock",
                "mocks",
                "fixture",
                "fixtures",
                "e2e",
                "config",
            }
        )
        == modules.INERT_SUFFIXES
    )


def _symlink_or_skip(link: Path, target: str) -> None:
    """A relative symlink; the target uses the OS separator (Windows does
    not follow ``/`` in a symlink target)."""
    try:
        link.symlink_to(target)
    except (OSError, NotImplementedError):
        pytest.skip("symbolic links are not available")
    if not link.exists():
        pytest.skip("the symbolic link does not resolve on this host")


@pytest.mark.parametrize("which", ["importer", "target", "writer"])
def test_symlinked_files_fail_closed(tmp_path: Path, which: str) -> None:
    """E5-5 (A4): Node resolves a symlinked file's imports from its real
    path, tsc from the link; a symlinked importer, target or writer fails
    closed."""
    files = {**OTHERS, "real/svc.ts": SVC, "real/use.ts": USE, "real/x.js": "1;\n"}
    root = _write(tmp_path, files)
    if which == "importer":
        _symlink_or_skip(root / "use.ts", str(Path("real") / "use.ts"))
        (root / "svc.ts").write_text(SVC, encoding="utf-8")
        file, reason = "use.ts", "unknown-variant"
    elif which == "target":
        _symlink_or_skip(root / "real" / "lib.ts", "svc.ts")
        (root / "real" / "use.ts").write_text(
            USE.replace("./svc", "./lib"), encoding="utf-8"
        )
        file, reason = "real/use.ts", "unknown-variant"
    else:
        (root / "real" / "w").mkdir()
        (root / "real" / "w" / "x.js").write_text(
            "require('./svc').t = 0;\n", encoding="utf-8"
        )
        _symlink_or_skip(root / "real" / "y.js", str(Path("w") / "x.js"))
        file, reason = "real/use.ts", "run-tainted:unresolvable-writer"
    off, structural, on, label = _run(root, file, "t")
    assert off["resolution"] == "ambiguous"
    assert on == off
    assert label == f"none({reason})"


def test_unparsed_file_without_text_shuts_off_the_run() -> None:
    """A JS/TS file with no scope facts to read (``module_bindings`` empty)
    is an unknown writer: ``run-tainted:unparsed-file``."""
    facts = [
        {
            "path": "x.js",
            "scope_facts": {
                "language": "javascript",
                "supported": False,
                "module_bindings": {},
            },
        }
    ]
    run = modules.build_module_run(facts, None)
    assert modules.run_tainted_reason(run) == "run-tainted:unparsed-file"


def test_the_shutoff_is_logged(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    root = _write(
        tmp_path, {**OTHERS, "svc.ts": SVC, "use.ts": USE, "x.js": "eval(s);\n"}
    )
    with caplog.at_level("INFO", logger="chunker.call_resolution.modules"):
        extract_symbol_graph(root, call_resolution=MODE)
    assert any(
        "Tier 2 is off for this run (evaluator in x.js, production)"
        in record.getMessage()
        for record in caplog.records
    )


def test_text_scan_of_an_unparsed_file() -> None:
    from chunker.call_resolution.js_modules import text_module_bindings

    scanned = text_module_bindings(
        b"import x from './a';\nrequire(\"../b/c\");\nsetTimeout(r, 1);\nf(\n"
    )
    assert scanned["taints"] == ["../b/c", "./a"]
    assert scanned["shutoff"] == []
    assert scanned["opaque"] is True
    assert text_module_bindings(b"setTimeout('x');\n")["shutoff"] == [
        "evaluator",
        "unparsed-file",
    ]
    assert text_module_bindings(b"require(name)\n")["shutoff"] == [
        "dynamic-loader",
        "unparsed-file",
    ]


def test_symlinked_files_change_the_on_mode_cache_key() -> None:
    from chunker.boundary import adapter

    common = {
        "display_path": "a.ts",
        "content_hash": "0" * 64,
        "language": "typescript",
        "resolution_mode": "permissive",
        "fail_fast": False,
    }
    plain = adapter._cache_key_payload(**common, call_resolution=MODE)
    linked = adapter._cache_key_payload(**common, call_resolution=MODE, symlink=True)
    off = adapter._cache_key_payload(**common, symlink=True)
    assert "call_resolution_symlink" not in plain
    assert linked["call_resolution_symlink"] is True
    assert "call_resolution_symlink" not in off
    assert adapter._build_boundary_cache_key(plain) != (
        adapter._build_boundary_cache_key(linked)
    )


# ---------------------------------------------------------------------------
# PR 5 fold 2: owner decision O-2 ("scope by caller"). Causes and taints that
# originate in test files apply only to callers in test files; a test file a
# production file reaches is production.

TEST_USE = "import { t } from './svc';\nexport function v() { return t(); }\n"
O2_TEST_CAUSES = {
    "create-require": (
        "x.test.ts",
        "import { createRequire } from 'node:module';\nexport const r = createRequire;\n",
        "none(run-tainted:module-system)",
    ),
    "non-literal-import": (
        "x.test.ts",
        "export const p = (n: string) => import(n);\n",
        "none(run-tainted:dynamic-loader)",
    ),
    "constructor-route": (
        "__tests__/x.ts",
        "export const k = (() => 0).constructor('s');\n",
        "none(run-tainted:evaluator)",
    ),
    "import-binding-write": (
        "evil.test.js",
        "import { t } from './svc';\nexport function w() { t = 9; }\n",
        "none(commonjs)",
    ),
    "jest-spy-on-namespace": (
        "svc.spec.ts",
        "import * as ns from './svc';\njest.spyOn(ns, 't');\n",
        "none(commonjs)",
    ),
    "rejected-specifier-taint": (
        "test/x.js",
        "require('../SVC.JS').t = 0;\n",
        "none(commonjs)",
    ),
}


def _edge_label(
    root: Path, file: str
) -> tuple[dict[str, Any], dict[str, Any], str | None]:
    off, _, on, label = _run(root, file, "t")
    return off, on, label


@pytest.mark.parametrize("case", sorted(O2_TEST_CAUSES))
def test_test_file_causes_are_scoped_to_test_callers(tmp_path: Path, case: str) -> None:
    """O-2 (a), (b): a cause or taint in a test file leaves a production
    caller's edge resolved and fails a test caller's edge closed."""
    name, text, reason = O2_TEST_CAUSES[case]
    root = _write(
        tmp_path,
        {**OTHERS, "svc.ts": SVC, "use.ts": USE, "use.test.ts": TEST_USE, name: text},
    )
    off, on, label = _edge_label(root, "use.ts")
    assert off["resolution"] == "ambiguous"
    assert on["resolution"] == "resolved", (case, label)
    off, on, label = _edge_label(root, "use.test.ts")
    assert on == off, case
    assert label == reason, case


def test_production_causes_stay_run_wide(tmp_path: Path) -> None:
    """O-2 (f): a cause in a production file fails every caller closed."""
    root = _write(
        tmp_path,
        {
            **OTHERS,
            "svc.ts": SVC,
            "use.ts": USE,
            "use.test.ts": TEST_USE,
            "x.ts": "export const r = (n: string) => import(n);\n",
        },
    )
    for file in ("use.ts", "use.test.ts"):
        off, on, label = _edge_label(root, file)
        assert on == off, file
        assert label == "none(run-tainted:dynamic-loader)", file


def test_a_test_file_production_reaches_is_promoted(tmp_path: Path) -> None:
    """O-2 (c): a production file imports ``tests/helper.ts``, which holds a
    run-wide cause, so production edges fail closed too."""
    root = _write(
        tmp_path,
        {
            **OTHERS,
            "svc.ts": SVC,
            "use.ts": USE
            + "import { h } from './tests/helper';\nexport const k = h;\n",
            "tests/helper.ts": "export const h = 1;\neval('0');\n",
        },
    )
    off, on, label = _edge_label(root, "use.ts")
    assert on == off
    assert label == "none(run-tainted:evaluator)"


@pytest.mark.parametrize("link", ["import", "require", "reexport", "rejected"])
def test_promotion_is_transitive(tmp_path: Path, link: str) -> None:
    """O-2 (d): production -> ``tests/a.ts`` -> ``tests/b.ts`` (two hops,
    through each kind of edge) promotes ``b``, whose cause is run-wide."""
    second = {
        "import": "import './b';\n",
        "require": "require('./b');\n",
        "reexport": "export * from './b';\n",
        "rejected": "require('./B.JS?x');\n",
    }[link]
    root = _write(
        tmp_path,
        {
            **OTHERS,
            "svc.ts": SVC,
            "use.ts": USE + "import './tests/a';\n",
            "tests/a.js": second,
            "tests/b.js": "export const b = 1;\nconst r = require;\n",
        },
    )
    off, on, label = _edge_label(root, "use.ts")
    assert on == off, link
    assert label == "none(run-tainted:dynamic-loader)", link


def test_an_unreached_test_helper_stays_test_scoped(tmp_path: Path) -> None:
    """The control for promotion: the same helper, imported only by a test
    file, leaves production edges resolved."""
    root = _write(
        tmp_path,
        {
            **OTHERS,
            "svc.ts": SVC,
            "use.ts": USE,
            "use.test.ts": TEST_USE + "import './tests/helper';\n",
            "tests/helper.ts": "export const h = 1;\neval('0');\n",
        },
    )
    off, on, label = _edge_label(root, "use.ts")
    assert on["resolution"] == "resolved"
    off, on, label = _edge_label(root, "use.test.ts")
    assert label == "none(run-tainted:evaluator)"


TEST_PATHS = [
    "svc.test.ts",
    "svc.spec.tsx",
    "a/svc.test.d.ts",
    "__tests__/svc.ts",
    "a/__mocks__/svc.js",
    "test/svc.ts",
    "a/tests/b/svc.ts",
]
NOT_TEST_PATHS = [
    "contest.ts",
    "testing/svc.ts",
    "latest.ts",
    "my.tests.ts",
    "Test/svc.ts",
    "test.ts",
    "spec.ts",
    "svc.Test.ts",
    "e2e/svc.ts",
    "a/testdata/svc.ts",
]


@pytest.mark.parametrize("path", TEST_PATHS)
def test_test_classifier_entries(path: str) -> None:
    """O-2 (e): every entry of the closed classifier."""
    assert modules.is_test_path(path)


@pytest.mark.parametrize("path", NOT_TEST_PATHS)
def test_test_classifier_near_misses(path: str) -> None:
    assert not modules.is_test_path(path)


def test_test_classifier_is_closed() -> None:
    assert frozenset({"test", "spec"}) == modules.TEST_NAME_SEGMENTS
    assert (
        frozenset({"__tests__", "__mocks__", "test", "tests"})
        == modules.TEST_DIRECTORIES
    )


def test_the_shutoff_log_names_its_scope(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    root = _write(
        tmp_path,
        {**OTHERS, "svc.ts": SVC, "use.ts": USE, "x.test.js": "eval(s);\n"},
    )
    with caplog.at_level("INFO", logger="chunker.call_resolution.modules"):
        extract_symbol_graph(root, call_resolution=MODE)
    assert any(
        "Tier 2 is off for callers in test files (evaluator in x.test.js, "
        "test-scoped)" in record.getMessage()
        for record in caplog.records
    )


def test_an_uncomputable_production_edge_promotes_every_test_file(
    tmp_path: Path,
) -> None:
    """A production specifier whose target cannot be computed (it leaves the
    root) may name any file, so every test file becomes production."""
    root = _write(
        tmp_path,
        {
            **OTHERS,
            "svc.ts": SVC,
            "use.ts": USE + "import '../outside/x';\n",
            "x.test.js": "eval(s);\n",
        },
    )
    off, on, label = _edge_label(root, "use.ts")
    assert on == off
    assert label == "none(run-tainted:evaluator)"


# ---------------------------------------------------------------------------
# PR 5 fold 3: closed allow-lists for three run-wide causes. Runtime trace
# (node v24.22.3, plan Appendix B fold 3): ``builtinModules`` and
# ``isBuiltin`` are pure lookups; a literal ``r('./x')`` from
# ``createRequire`` returns the module's exports and writes nothing;
# ``x.constructor.name``, ``===``, ``instanceof`` and ``typeof`` never call
# the constructor. Everything outside each list keeps its run-wide effect.

FOLD3_SAFE = {
    "inert-module-imports": (
        "import { builtinModules, isBuiltin } from 'node:module';\n"
        "export const b = builtinModules.includes('fs') && isBuiltin('fs');\n"
        "console.log(builtinModules);\n"
    ),
    "type-only-module-import": "import type { Module } from 'module';\nexport let m: Module;\n",
    "create-require-literal-calls": (
        "import { createRequire } from 'node:module';\n"
        "const r = createRequire(import.meta.url);\n"
        "export const o = r('./other');\n"
        "export const p = r.resolve('./more');\n"
        "export const q = r(`lodash`);\n"
    ),
    "create-require-aliased": (
        "import { createRequire as cr } from 'module';\n"
        "export function load() { const req = cr(__filename); return req('./other'); }\n"
    ),
    "constructor-name-and-comparisons": (
        "export function kind(x: any, K: any) {\n"
        "  return [x.constructor.name, x.constructor === K, x.constructor != K,\n"
        "    x instanceof x.constructor, typeof x.constructor];\n"
        "}\n"
    ),
}


@pytest.mark.parametrize("case", sorted(FOLD3_SAFE))
def test_fold3_safe_uses_leave_the_run_on(tmp_path: Path, case: str) -> None:
    root = _write(
        tmp_path, {**OTHERS, "svc.ts": SVC, "use.ts": USE, "x.ts": FOLD3_SAFE[case]}
    )
    off, structural, on, label = _run(root, "use.ts", "t")
    assert off["resolution"] == "ambiguous"
    assert on["resolution"] == "resolved", (case, label)
    facts = extract_symbol_facts_for_file(root / "x.ts", root, call_resolution=MODE)
    assert facts["scope_facts"]["module_bindings"]["shutoff"] == [], case


CR = "import { createRequire } from 'node:module';\n"
FOLD3_UNSAFE = {
    # Item 1: anything but the inert names (createRequire under item 2).
    "module-namespace-import": (
        "import * as m from 'node:module';\nexport const k = m;\n",
        "module-system",
    ),
    "module-Module": (
        "import { Module } from 'node:module';\nexport const k = Module;\n",
        "module-system",
    ),
    "module-_load": (
        "import { _load } from 'module';\nexport const k = _load;\n",
        "module-system",
    ),
    "module-register": (
        "import { register } from 'node:module';\nregister('./x');\n",
        "module-system",
    ),
    "module-sync-builtin-esm-exports": (
        "import { syncBuiltinESMExports } from 'node:module';\nsyncBuiltinESMExports();\n",
        "module-system",
    ),
    "module-mixed-inert-and-other": (
        "import { isBuiltin, Module } from 'node:module';\nexport const k = [isBuiltin, Module];\n",
        "module-system",
    ),
    "module-inert-name-written": (
        "import { isBuiltin } from 'node:module';\nisBuiltin = () => true;\n",
        "module-system",
    ),
    "module-reexport": (
        "export { builtinModules } from 'node:module';\n",
        "module-system",
    ),
    "module-import-attributes": (
        "import { isBuiltin } from 'node:module' with { type: 'js' };\nisBuiltin('x');\n",
        "module-system",
    ),
    # Item 2: createRequire only as ``const r = createRequire(…)`` with
    # literal calls and ``r.resolve(<literal>)``.
    "create-require-non-literal-call": (
        CR
        + "const r = createRequire(import.meta.url);\nexport const f = (n: string) => r(n);\n",
        "module-system",
    ),
    "create-require-cache": (
        CR + "const r = createRequire(import.meta.url);\nexport const c = r.cache;\n",
        "module-system",
    ),
    "create-require-main": (
        CR + "const r = createRequire(import.meta.url);\nexport const m = r.main;\n",
        "module-system",
    ),
    "create-require-passed-on": (
        CR + "const r = createRequire(import.meta.url);\nconsole.log(r);\n",
        "module-system",
    ),
    "create-require-resolve-non-literal": (
        CR
        + "const r = createRequire(import.meta.url);\nexport const f = (n: string) => r.resolve(n);\n",
        "module-system",
    ),
    "create-require-let": (
        CR + "let r = createRequire(import.meta.url);\nr('./other');\n",
        "module-system",
    ),
    "create-require-var": (
        CR + "var r = createRequire(import.meta.url);\nr('./other');\n",
        "module-system",
    ),
    "create-require-immediate-call": (
        CR + "createRequire(import.meta.url)('./other');\n",
        "module-system",
    ),
    "create-require-aliased-value": (
        CR + "const r = createRequire(import.meta.url), q = r;\nq('./other');\n",
        "module-system",
    ),
    "create-require-of-module": (
        CR + "const r = createRequire(import.meta.url);\nr('module');\n",
        "module-system",
    ),
    # Item 3: ``.constructor`` outside the closed positions.
    "constructor-argument": (
        "export const k = (x: any) => expect(x.constructor);\n",
        "evaluator",
    ),
    "constructor-assigned": (
        "export const k = (x: any) => { const C = x.constructor; return C; };\n",
        "evaluator",
    ),
    "constructor-returned": (
        "export function k(x: any) { return x.constructor; }\n",
        "evaluator",
    ),
    "constructor-element": (
        "export const k = (x: any) => [x.constructor];\n",
        "evaluator",
    ),
    "constructor-spread": (
        "export const k = (x: any) => ({ ...x.constructor });\n",
        "evaluator",
    ),
    "constructor-computed-key": (
        "export const k = (x: any, o: any) => o[x.constructor];\n",
        "evaluator",
    ),
    "constructor-prototype-read": (
        "export const k = (x: any) => x.constructor.prototype;\n",
        "evaluator",
    ),
    "constructor-computed-name-read": (
        "export const k = (x: any) => x.constructor['name'];\n",
        "evaluator",
    ),
    "constructor-negated": (
        "export const k = (x: any) => !x.constructor;\n",
        "evaluator",
    ),
    "constructor-logical-or": (
        "export const k = (x: any, F: any) => new (x.constructor || F)();\n",
        "evaluator",
    ),
    "create-require-duplicate-binding": (
        CR + "var createRequire = (u: any) => 0;\n"
        "const r = createRequire(1);\nr('./other');\n",
        "module-system",
    ),
    "constructor-called": (
        "export const k = (x: any) => x.constructor('s');\n",
        "evaluator",
    ),
}


@pytest.mark.parametrize("case", sorted(FOLD3_UNSAFE))
def test_fold3_unsafe_uses_stay_run_wide(tmp_path: Path, case: str) -> None:
    text, cause = FOLD3_UNSAFE[case]
    root = _write(tmp_path, {**OTHERS, "svc.ts": SVC, "use.ts": USE, "x.ts": text})
    off, structural, on, label = _run(root, "use.ts", "t")
    assert on == off, case
    assert label == f"none(run-tainted:{cause})", case


def test_fold3_create_require_literal_calls_taint_their_target(tmp_path: Path) -> None:
    """A literal ``r('./x')`` taints its target like ``require``, with the
    lenient normalization for rejected specifiers (E5-4)."""
    for specifier in ("./svc", "./SVC.JS"):
        root = _write(
            tmp_path / specifier.strip("./").lower(),
            {
                **OTHERS,
                "svc.ts": SVC,
                "use.ts": USE,
                "x.ts": CR
                + f"const r = createRequire(import.meta.url);\nr('{specifier}').t = 0;\n",
            },
        )
        off, structural, on, label = _run(root, "use.ts", "t")
        assert on == off, specifier
        assert label == "none(commonjs)", specifier


def test_fold3_allow_lists_are_closed() -> None:
    from chunker.call_resolution import js_modules, js_scope

    assert frozenset({"builtinModules", "isBuiltin"}) == js_modules.INERT_MODULE_EXPORTS
    assert (
        frozenset({"===", "!==", "==", "!=", "instanceof"})
        == js_scope._SAFE_CONSTRUCTOR_OPERATORS
    )

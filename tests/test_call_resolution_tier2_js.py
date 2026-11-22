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
        "commonjs",
        None,
    ),
    "require-alias": (
        {
            "svc.ts": SVC,
            "use.ts": USE,
            "x.js": "const r = require;\nr('./svc').t = 1;\n",
        },
        ("use.ts", "t"),
        "commonjs",
        None,
    ),
    "require-cache": (
        {
            "svc.ts": SVC,
            "use.ts": USE,
            "x.js": "Object.values(require.cache)[0].exports.t = 1;\n",
        },
        ("use.ts", "t"),
        "commonjs",
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
        "commonjs",
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
        "commonjs",
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
        "commonjs",
        None,
    ),
    "main-module": (
        {
            "svc.ts": SVC,
            "use.ts": USE,
            "x.js": "process['mainModule'].require('./svc').t = 1;\n",
        },
        ("use.ts", "t"),
        "commonjs",
        None,
    ),
    "code-evaluator": (
        {"svc.ts": SVC, "use.ts": USE, "x.js": "eval(source);\n"},
        ("use.ts", "t"),
        "commonjs",
        None,
    ),
    "unsupported-js-file": (
        {"svc.ts": SVC, "use.ts": USE, "x.js": "function (\n"},
        ("use.ts", "t"),
        "commonjs",
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
        ("./a/../../x", "outside-root"),
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
    assert scope["module_bindings"] == {
        "stars": ["./s"],
        "commonjs": False,
        "opaque": False,
        "taints": ["./n"],
        "taint_all": False,
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

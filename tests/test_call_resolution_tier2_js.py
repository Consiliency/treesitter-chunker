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
from chunker.call_resolution.js_strings import decode_js_string, decode_jsx_text
from chunker.symbol_graph import (
    SKIP_PARTS,
    assemble_symbol_graph,
    collect_source_files,
    extract_symbol_facts_for_file,
    extract_symbol_graph,
    has_directory_symlink,
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
    links = has_directory_symlink(root)
    graph = assemble_symbol_graph(
        facts,
        total_files=len(facts),
        call_resolution=MODE,
        language_filter=language,
        directory_symlinks=links,
    )
    context = engine.build_run_context(
        facts,
        graph["symbol_lookup"],
        MODE,
        language_filter=language,
        directory_symlinks=links,
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
    # E5-7: a file the parser cannot read is a run-wide cause.
    "unparsed-file-relative-literal-taints": (
        {
            "svc.ts": SVC,
            "use.ts": USE,
            "x.js": "require('./svc').t = 1;\nfunction (\n",
        },
        ("use.ts", "t"),
        "run-tainted:unparsed-file",
        None,
    ),
    "unparsed-file-trigger-spelling": (
        {"svc.ts": SVC, "use.ts": USE, "x.js": "createRequire;\nfunction (\n"},
        ("use.ts", "t"),
        "run-tainted:unparsed-file",
        None,
    ),
    "unparsed-file-escaped-trigger-spelling": (
        {"svc.ts": SVC, "use.ts": USE, "x.js": "\\u0065val(s);\nfunction (\n"},
        ("use.ts", "t"),
        "run-tainted:unparsed-file",
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
        "run-tainted:dynamic-loader",
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
        "uncomputable": False,
        "filename_taints": [],
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
        "run-tainted:unparsed-file",
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
            + "export class K { a = this; m() { return this; } }\n",
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


# ---------------------------------------------------------------------------
# PR 5 fold 4 (the president's review at ec86f20c, P5-1..P5-3, item 4).

# P5-1 repro 1 (``president/rt-createrequire-base``): Node resolves
# ``r('./svc')`` from the createRequire base (``lib/``), not the importer.
RT_CREATEREQUIRE_BASE = {
    "app.ts": (
        "import { createRequire } from 'node:module';\n"
        "import * as path from 'node:path';\n"
        "const r = createRequire(path.join(__dirname, 'lib', 'x.js'));\n"
        "export function patch() { r('./svc').t = () => \"evil\"; }\n"
    ),
    "lib/svc.ts": 'export function t() { return "lib/svc.t"; }\n',
    "other.ts": 'export function t() { return "other.t"; }\n',
    "use.ts": (
        "import { t } from './lib/svc';\n"
        "import { patch } from './app';\n"
        "export function u() { return t(); }\n"
        'console.log("before:", u()); patch(); console.log("after :", u());\n'
    ),
}
# P5-1 repro 2 (``president/rt-o2-createrequire``): production runs a test
# file through a createRequire base under ``tests/``.
RT_O2_CREATEREQUIRE = {
    "app.ts": (
        "import { createRequire } from 'node:module';\n"
        "import * as path from 'node:path';\n"
        "const r = createRequire(path.join(__dirname, 'tests', 'x.js'));\n"
        "export function boot() { r('./setup'); }\n"
    ),
    "other.ts": 'export function t() { return "other.t"; }\n',
    "svc.ts": 'export function t() { return "svc.t"; }\n',
    "tests/setup.ts": "import * as ns from '../svc';\n(ns as any).t = () => \"evil\";\n",
    "use.ts": (
        "import { t } from './svc';\n"
        "import { boot } from './app';\n"
        "export function u() { return t(); }\n"
        'console.log("before:", u()); boot(); console.log("after :", u());\n'
    ),
}


@pytest.mark.parametrize(
    "tree", [RT_CREATEREQUIRE_BASE, RT_O2_CREATEREQUIRE], ids=["base", "o2"]
)
def test_p5_1_president_repros_fail_closed(
    tmp_path: Path, tree: dict[str, str]
) -> None:
    root = _write(tmp_path, tree)
    off, _, on, label = _run(root, "use.ts", "t")
    assert off["resolution"] == "ambiguous"
    assert on == off
    assert label == "none(run-tainted:unresolvable-writer)"


P5_1_BASES = {
    "dirname": "createRequire(__dirname)",
    "import-meta-dirname": "createRequire(import.meta.dirname)",
    "url-of-directory": "createRequire(new URL('./lib/', import.meta.url))",
    "path-to-file-url": "createRequire(pathToFileURL(__filename))",
    "variable": "createRequire(base)",
    "path-join": "createRequire(path.join(here, 'x.js'))",
}


@pytest.mark.parametrize("case", sorted(P5_1_BASES))
def test_p5_1_other_bases_make_targets_uncomputable(tmp_path: Path, case: str) -> None:
    text = CR + f"const r = {P5_1_BASES[case]};\nexport const k = r('./other');\n"
    root = _write(tmp_path, {**OTHERS, "svc.ts": SVC, "use.ts": USE, "x.ts": text})
    off, _, on, label = _run(root, "use.ts", "t")
    assert on == off, case
    assert label == "none(run-tainted:unresolvable-writer)", case


def test_p5_1_shadowed_filename_is_not_the_file(tmp_path: Path) -> None:
    text = (
        CR + "export function f(__filename: string) {\n"
        "  const r = createRequire(__filename);\n  return r('./other');\n}\n"
    )
    root = _write(tmp_path, {**OTHERS, "svc.ts": SVC, "use.ts": USE, "x.ts": text})
    off, _, on, label = _run(root, "use.ts", "t")
    assert on == off
    assert label == "none(run-tainted:unresolvable-writer)"


@pytest.mark.parametrize(
    "base", ["import.meta.url", "import.meta.filename", "__filename"]
)
def test_p5_1_own_file_bases_taint_exactly(tmp_path: Path, base: str) -> None:
    """The three own-file bases keep fold 3: a literal ``r('./svc')`` taints
    ``./svc`` (``commonjs``); ``r('./other')`` leaves ``use.ts`` resolved."""
    for target, resolved in (("./svc", False), ("./other", True)):
        text = CR + f"const r = createRequire({base});\nr('{target}').t = 0;\n"
        root = _write(
            tmp_path / f"{target[2:]}-{base.replace('.', '-')}",
            {**OTHERS, "svc.ts": SVC, "use.ts": USE, "x.ts": text},
        )
        off, _, on, label = _run(root, "use.ts", "t")
        if resolved:
            assert on["resolution"] == "resolved", (base, label)
        else:
            assert on == off, base
            assert label == "none(commonjs)", base


# P5-2 (``president/rt-o2-dirlink``): ``helpers -> tests``.
RT_O2_DIRLINK = {
    "app.ts": "import './helpers/w';\n",
    "other.ts": "export function t() { return 'o'; }\n",
    "svc.ts": "export function t() { return 'svc.t'; }\n",
    "tests/w.ts": (
        "import * as ns from '../svc';\n(ns as any).t = () => 'evil';\n"
        "export const k = 1;\n"
    ),
    "use.ts": (
        "import { t } from './svc';\nimport './app';\n"
        "export function u() { return t(); }\nconsole.log(u());\n"
    ),
}


def test_p5_2_directory_symlink_promotes_every_test_file(tmp_path: Path) -> None:
    root = _write(tmp_path, RT_O2_DIRLINK)
    _symlink_or_skip(root / "helpers", "tests")
    assert has_directory_symlink(root)
    off, _, on, label = _run(root, "use.ts", "t")
    assert on == off
    assert label == "none(commonjs)"


def test_p5_2_without_directory_symlinks_o2_scoping_holds(tmp_path: Path) -> None:
    """The control: the same tree with no link keeps O-2 scoping (the test
    writer is unreached, so production stays resolved)."""
    root = _write(tmp_path, {**RT_O2_DIRLINK, "app.ts": "export {};\n"})
    assert not has_directory_symlink(root)
    _, _, on, label = _run(root, "use.ts", "t")
    assert on["resolution"] == "resolved", label


def test_p5_2_unknown_directory_symlinks_promote(tmp_path: Path) -> None:
    """An assembly that does not say (``directory_symlinks=None``) treats
    every test file as production."""
    root = _write(
        tmp_path,
        {**OTHERS, "svc.ts": SVC, "use.ts": USE, "x.test.js": "eval(s);\n"},
    )
    facts = [
        extract_symbol_facts_for_file(path, root, call_resolution=MODE)
        for path in collect_source_files(root)
    ]
    run = modules.build_module_run(facts, None, None)
    assert run.test_scope == frozenset()
    assert modules.build_module_run(facts, None, False).test_scope == {"x.test.js"}


# P5-3: test-framework module mocks.
MOCK_CALLS = {
    "jest.mock": ("jest.mock('../svc');\n", ""),
    "jest.doMock": ("jest.doMock('../svc', () => ({}));\n", ""),
    "jest.unstable_mockModule": (
        "jest.unstable_mockModule('../svc', () => ({}));\n",
        "",
    ),
    "jest.setMock": ("jest.setMock('../svc', {});\n", ""),
    "vi.mock": ("vi.mock('../svc');\n", "import { vi } from 'vitest';\n"),
    "vi.doMock": ("vi.doMock('../svc');\n", "import { vi } from 'vitest';\n"),
    "jest-from-globals": (
        "jest.mock('../svc');\n",
        "import { jest } from '@jest/globals';\n",
    ),
    "aliased-vi": ("v.mock('../svc');\n", "import { vi as v } from 'vitest';\n"),
}


@pytest.mark.parametrize("case", sorted(MOCK_CALLS))
def test_p5_3_module_mocks_taint_for_test_callers(tmp_path: Path, case: str) -> None:
    call, header = MOCK_CALLS[case]
    root = _write(
        tmp_path,
        {
            **OTHERS,
            "svc.ts": SVC,
            "use.ts": USE,
            "tests/a.test.ts": header
            + "import { t } from '../svc';\n"
            + call
            + "export function check() { return t(); }\n",
        },
    )
    off, _, on, label = _run(root, "tests/a.test.ts", "t")
    assert on == off, case
    assert label == "none(commonjs)", case
    _, _, on, label = _run(root, "use.ts", "t")
    assert on["resolution"] == "resolved", (case, label)


@pytest.mark.parametrize(
    ("call", "reason"),
    [
        ("jest.mock(name);\n", "none(run-tainted:unresolvable-writer)"),
        ("jest.mock('lodash');\n", "import"),
        ("const jest = { mock(x: string) {} };\njest.mock('../svc');\n", "import"),
    ],
    ids=["non-literal", "bare-package", "shadowed-jest"],
)
def test_p5_3_mock_near_misses(tmp_path: Path, call: str, reason: str) -> None:
    root = _write(
        tmp_path,
        {
            **OTHERS,
            "svc.ts": SVC,
            "use.ts": USE,
            "tests/a.test.ts": "import { t } from '../svc';\n"
            + call
            + "export function check() { return t(); }\n",
        },
    )
    _, _, on, label = _run(root, "tests/a.test.ts", "t")
    assert label == reason
    assert (on["resolution"] == "resolved") is (reason == "import")
    _, _, on, _ = _run(root, "use.ts", "t")
    assert on["resolution"] == "resolved"


# Item 4: production edges whose targets cannot be computed promote every
# test file; a test file's cause then reaches production callers.
UNCOMPUTABLE_PRODUCTION = {
    "package-imports": "import k from '#setup';\nexport const j = k;\n",
    "import-meta-glob": "export const m = import.meta.glob('./tests/*.ts');\n",
    "import-meta-glob-eager": "export const m = import.meta.globEager('./x/*.ts');\n",
    "absolute-path": "import '/abs/setup.js';\n",
    "drive-letter": "import 'C:/abs/setup.js';\n",
    "file-url": "import 'file:///abs/setup.js';\n",
}


@pytest.mark.parametrize("case", sorted(UNCOMPUTABLE_PRODUCTION))
def test_uncomputable_production_targets_promote_every_test_file(
    tmp_path: Path, case: str
) -> None:
    root = _write(
        tmp_path,
        {
            **OTHERS,
            "svc.ts": SVC,
            "use.ts": USE,
            "app.ts": UNCOMPUTABLE_PRODUCTION[case],
            "x.test.js": "eval(s);\n",
        },
    )
    off, _, on, label = _run(root, "use.ts", "t")
    assert on == off, case
    assert label == "none(run-tainted:evaluator)", case


def test_uncomputable_writer_specifiers(tmp_path: Path) -> None:
    """A write through ``require('#x')`` or an absolute path cannot be
    located: ``unresolvable-writer``."""
    for name, text in (
        ("hash", "require('#x').t = 0;\n"),
        ("abs", "require('/x').t = 0;\n"),
    ):
        root = _write(
            tmp_path / name, {**OTHERS, "svc.ts": SVC, "use.ts": USE, "x.js": text}
        )
        off, _, on, label = _run(root, "use.ts", "t")
        assert on == off, name
        assert label == "none(run-tainted:unresolvable-writer)", name


# ---------------------------------------------------------------------------
# PR 5 fold 5 (the president's re-check at 3344e9db, P5-13, P5-14, P5-16,
# P5-18). Trees after ``president/rt-p13-*``: ``use.ts`` imports ``t`` from
# ``./lib/svc`` and calls the writer.

LIB_TREE = {
    "lib/svc.ts": 'export function t() { return "lib/svc.t"; }\n',
    "other.ts": 'export function t() { return "other.t"; }\n',
    "use.ts": (
        "import { t } from './lib/svc';\nimport { patch } from './app';\n"
        "export function u() { return t(); }\n"
    ),
}
PATCH = "export function patch() { r('./lib/svc').t = () => 'evil'; }\n"
P5_13_NEAR_MISSES = {
    "var-filename": (
        {
            "app.ts": CR + "import * as path from 'node:path';\n"
            "var __filename = path.join(__dirname, 'lib', 'x.js');\n"
            "const r = createRequire(__filename);\n" + PATCH
        },
        "none(run-tainted:unresolvable-writer)",
    ),
    "assign-filename": (
        {
            "app.ts": CR
            + "__filename = 'elsewhere/x.js';\nconst r = createRequire(__filename);\n"
            + PATCH
        },
        "none(run-tainted:unresolvable-writer)",
    ),
    "commonjs-assign-filename": (
        {
            "app.ts": CR
            + "__filename = 'elsewhere/x.js';\nconst r = createRequire(__filename);\n"
            + PATCH
            + "exports.k = 1;\n"
        },
        "none(run-tainted:unresolvable-writer)",
    ),
    "filename-written-late": (
        {
            "app.ts": CR + "const r = createRequire(__filename);\n"
            "function f() { __filename = 'elsewhere/x.js'; }\nf();\n" + PATCH
        },
        "none(run-tainted:unresolvable-writer)",
    ),
    "filename-destructured": (
        {
            "app.ts": CR + "const r = createRequire(__filename);\n"
            "export function f(o: any) { ({ __filename } = o); }\n" + PATCH
        },
        "none(run-tainted:unresolvable-writer)",
    ),
    "import-filename": (
        {
            "paths.ts": "export const f = 'lib/x.js';\n",
            "app.ts": CR + "import { f as __filename } from './paths';\n"
            "const r = createRequire(__filename);\n" + PATCH,
        },
        "none(run-tainted:unresolvable-writer)",
    ),
    "const-filename": (
        {
            "app.ts": CR
            + "const __filename = 'lib/x.js';\nconst r = createRequire(__filename);\n"
            + PATCH
        },
        "none(run-tainted:unresolvable-writer)",
    ),
    "meta-write": (
        {
            "app.ts": CR
            + "(import.meta as any).url = new URL('../lib/x.js', import.meta.url).href;\n"
            "const r = createRequire(import.meta.url);\n" + PATCH
        },
        "none(run-tainted:unresolvable-writer)",
    ),
    "meta-destructured-write": (
        {
            "app.ts": CR
            + "export function g(o: any) { ({ u: (import.meta as any).url } = o); }\n"
            "const r = createRequire(import.meta.filename);\n" + PATCH
        },
        "none(run-tainted:unresolvable-writer)",
    ),
    "global-filename-writer": (
        {
            "app.ts": CR + "const r = createRequire(__filename);\n" + PATCH,
            "setg.ts": "export {};\n(globalThis as any).__filename = 'lib/x.js';\n",
        },
        "none(run-tainted:unresolvable-writer)",
    ),
    "script-var-filename-writer": (
        {
            "app.ts": CR + "const r = createRequire(__filename);\n" + PATCH,
            "setg.js": "var __filename = 'lib/x.js';\n",
        },
        "none(run-tainted:unresolvable-writer)",
    ),
    "global-object-escape-writer": (
        {
            "app.ts": CR + "const r = createRequire(__filename);\n" + PATCH,
            "setg.ts": "export const g: any = globalThis;\n",
        },
        "none(run-tainted:unresolvable-writer)",
    ),
}


@pytest.mark.parametrize("case", sorted(P5_13_NEAR_MISSES))
def test_p5_13_bases_that_may_name_another_file(tmp_path: Path, case: str) -> None:
    files, reason = P5_13_NEAR_MISSES[case]
    root = _write(tmp_path, {**LIB_TREE, **files})
    off, _, on, label = _run(root, "use.ts", "t")
    assert off["resolution"] == "ambiguous"
    assert on == off, case
    assert label == reason, case


def test_p5_13_unwritten_import_meta_url_taints_exactly(tmp_path: Path) -> None:
    root = _write(
        tmp_path,
        {
            **LIB_TREE,
            "app.ts": CR + "const r = createRequire(import.meta.url);\n" + PATCH,
        },
    )
    off, _, on, label = _run(root, "use.ts", "t")
    assert on == off
    assert label == "none(commonjs)"


@pytest.mark.parametrize("writer", [False, True], ids=["no-writer", "global-writer"])
def test_p5_13_commonjs_free_filename_taints_exactly(
    tmp_path: Path, writer: bool
) -> None:
    """P5-20: CommonJS hints in the file do not bypass the run-wide writer
    check. With no writer the base taints ``./lib/svc`` exactly; with a
    global ``__filename`` writer it fails closed."""
    files = {
        "app.ts": CR
        + "const r = createRequire(__filename);\n"
        + PATCH
        + "exports.k = 1;\n"
    }
    if writer:
        files["setg.ts"] = "export {};\n(globalThis as any).__filename = 'x.js';\n"
    root = _write(tmp_path, {**LIB_TREE, **files})
    facts = extract_symbol_facts_for_file(root / "app.ts", root, call_resolution=MODE)
    bindings = facts["scope_facts"]["module_bindings"]
    assert bindings["commonjs"] is True
    assert bindings["filename_taints"] == ["./lib/svc"]
    assert "./lib/svc" not in bindings["taints"]
    off, _, on, label = _run(root, "use.ts", "t")
    assert on == off
    expected = "none(run-tainted:unresolvable-writer)" if writer else "none(commonjs)"
    assert label == expected


# P5-20 repros (``president/f5/cjsmis-*``): a CommonJS hint in an ES module.
CJSMIS = {
    "lib/svc.ts": 'export function t() { return "lib/svc.t"; }\n',
    "other.ts": 'export function t() { return "other.t"; }\n',
    "setg.ts": (
        "import * as path from 'node:path';\n"
        "(globalThis as any).__filename = path.join(__dirname, 'lib', 'x.js');\n"
    ),
    "use.ts": (
        "import { t } from './lib/svc';\nimport './setg';\n"
        "import { patch } from './esm/app.js';\n"
        "export function u() { return t(); }\n"
    ),
    "esm/package.json": '{"type":"module"}\n',
}


@pytest.mark.parametrize(
    "hint",
    ["void this;\n", 'if (typeof exports === "object") { console.log("cjs"); }\n'],
    ids=["this", "typeof-exports"],
)
def test_p5_20_commonjs_hints_do_not_bypass_the_writer_check(
    tmp_path: Path, hint: str
) -> None:
    app = (
        "import { createRequire } from 'node:module';\n"
        + hint
        + "const r = createRequire(__filename);\n"
        "export function patch() { r('./svc').t = () => \"evil\"; }\n"
    )
    root = _write(tmp_path, {**CJSMIS, "esm/app.js": app})
    off, _, on, label = _run(root, "use.ts", "t")
    assert off["resolution"] == "ambiguous"
    assert on == off
    assert label == "none(run-tainted:unresolvable-writer)"


def test_p5_13_esm_free_filename_taints_without_writers(tmp_path: Path) -> None:
    """The ES-module case: no run file writes a global ``__filename``, so the
    conditional taint applies."""
    root = _write(
        tmp_path,
        {**LIB_TREE, "app.ts": CR + "const r = createRequire(__filename);\n" + PATCH},
    )
    facts = extract_symbol_facts_for_file(root / "app.ts", root, call_resolution=MODE)
    assert facts["scope_facts"]["module_bindings"]["filename_taints"] == ["./lib/svc"]
    off, _, on, label = _run(root, "use.ts", "t")
    assert on == off
    assert label == "none(commonjs)"


# P5-14: a production specifier through a skipped directory.
SKIPDIR_TREE = {
    "other.ts": "export function t() { return 'o'; }\n",
    "svc.ts": "export function t() { return 'svc.t'; }\n",
    "tests/w.ts": "import * as ns from '../svc';\n(ns as any).t = () => 'evil';\n",
    "use.ts": (
        "import { t } from './svc';\nimport './app';\n"
        "export function u() { return t(); }\n"
    ),
}


@pytest.mark.parametrize("skipped", ["build", "node_modules"])
def test_p5_14_specifier_through_a_skipped_directory(
    tmp_path: Path, skipped: str
) -> None:
    root = _write(
        tmp_path, {**SKIPDIR_TREE, "app.ts": f"import './{skipped}/helpers/w';\n"}
    )
    (root / skipped).mkdir()
    _symlink_or_skip(root / skipped / "helpers", str(Path("..") / "tests"))
    assert not has_directory_symlink(root)
    off, _, on, label = _run(root, "use.ts", "t")
    assert on == off, skipped
    assert label == "none(commonjs)", skipped


def test_p5_14_control_gen_link_fails_closed_through_the_flag(tmp_path: Path) -> None:
    root = _write(tmp_path, {**SKIPDIR_TREE, "app.ts": "import './gen/helpers/w';\n"})
    (root / "gen").mkdir()
    _symlink_or_skip(root / "gen" / "helpers", str(Path("..") / "tests"))
    assert has_directory_symlink(root)
    off, _, on, label = _run(root, "use.ts", "t")
    assert on == off
    assert label == "none(commonjs)"


def test_p5_14_write_through_a_skipped_directory_is_unresolvable(
    tmp_path: Path,
) -> None:
    root = _write(
        tmp_path,
        {
            **OTHERS,
            "svc.ts": SVC,
            "use.ts": USE,
            "x.js": "require('./dist/a').t = 0;\n",
        },
    )
    off, _, on, label = _run(root, "use.ts", "t")
    assert on == off
    assert label == "none(run-tainted:unresolvable-writer)"


@pytest.mark.parametrize(
    "specifier",
    ["FILE:///abs/tests/w.js", "File:///abs/w.js", "data:text/javascript,import 'x'"],
)
def test_p5_18_schemes_are_case_insensitive_and_data_is_uncomputable(
    tmp_path: Path, specifier: str
) -> None:
    root = _write(
        tmp_path,
        {
            **OTHERS,
            "svc.ts": SVC,
            "use.ts": USE,
            "app.ts": f'import "{specifier}";\n',
            "x.test.js": "eval(s);\n",
        },
    )
    off, _, on, label = _run(root, "use.ts", "t")
    assert on == off, specifier
    assert label == "none(run-tainted:evaluator)", specifier
    assert (
        modules.lenient_targets(modules.ModuleIndex.build([], None), specifier, "x.js")
        is None
    )


def test_p5_16_directory_junctions_count_as_links(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A Windows directory junction is not a symlink to ``is_symlink()``;
    ``has_directory_symlink`` also asks ``is_junction()``."""
    root = _write(tmp_path, {"a/x.ts": "export {};\n", "b/y.ts": "export {};\n"})
    assert not has_directory_symlink(root)
    original = Path.is_junction
    monkeypatch.setattr(
        Path, "is_junction", lambda self: self.name == "b" or original(self)
    )
    assert has_directory_symlink(root)


@pytest.mark.parametrize(
    "spelling", ["Build", "NODE_MODULES", "Dist", "build.", "build "]
)
def test_p5_21_skipped_directories_match_case_and_win32_forms(
    tmp_path: Path, spelling: str
) -> None:
    """P5-21: ``./Build/…``, ``./NODE_MODULES/…``, ``./Dist/…``,
    ``./build./…`` and ``./build /…`` reach a skipped directory on a
    case-insensitive or Win32 file system, so they are uncomputable."""
    index = modules.ModuleIndex.build(["use.ts"], None)
    specifier = f"./{spelling}/helpers/w"
    assert modules.lenient_targets(index, specifier, "use.ts") is None
    root = _write(
        tmp_path,
        {
            **OTHERS,
            "svc.ts": SVC,
            "use.ts": USE,
            "x.js": f"require('{specifier}').t = 0;\n",
        },
    )
    off, _, on, label = _run(root, "use.ts", "t")
    assert on == off, spelling
    assert label == "none(run-tainted:unresolvable-writer)", spelling


@pytest.mark.parametrize(
    "specifier",
    [
        " file:///abs/w.js",
        "\tfile:///abs/w.js",
        "fi\tle:///abs/w.js",
        "file:\n///abs/w.js",
    ],
)
def test_url_whitespace_is_stripped_before_the_scheme(specifier: str) -> None:
    """WHATWG URL parsing strips C0 controls and spaces at the ends and
    removes every tab, LF and CR, so these are ``file:`` URLs."""
    index = modules.ModuleIndex.build(["use.ts"], None)
    assert modules.lenient_targets(index, specifier, "use.ts") is None


# ---------------------------------------------------------------------------
# PR 5 fold 7 (the president's re-check at ae5f53a5, P5-27, P5-32).

O2_CR = {
    "other.ts": 'export function t() { return "other.t"; }\n',
    "svc.ts": 'export function t() { return "svc.t"; }\n',
    "tests/w.ts": "require('../svc').t = () => \"evil\";\n",
    "use.ts": (
        "import { t } from './svc';\nimport './app';\n"
        "export function u() { return t(); }\n"
    ),
}


@pytest.mark.parametrize(
    "hint", ["void this;\n", ""], ids=["o2-cr-this", "o2-cr-plain"]
)
def test_p5_27_filename_base_targets_promote(tmp_path: Path, hint: str) -> None:
    """``createRequire(__filename)`` literal targets are O-2 edges: production
    ``app.ts`` loads ``tests/w.ts``, which is promoted, so its write reaches
    production callers."""
    app = (
        "import { createRequire } from 'node:module';\n"
        + hint
        + "const r = createRequire(__filename);\nr('./tests/w');\n"
    )
    root = _write(tmp_path, {**O2_CR, "app.ts": app})
    off, _, on, label = _run(root, "use.ts", "t")
    assert off["resolution"] == "ambiguous"
    assert on == off
    assert label == "none(commonjs)"


# The taint-source audit (fold 7): every way a production file can name a
# file feeds the O-2 promotion graph, so production loading ``tests/w.ts``
# through any of them makes its write reach production callers.
PROMOTING_SOURCES = {
    "static-import": "import './tests/w';\n",
    "export-from": "export { k } from './tests/w';\n",
    "export-star": "export * from './tests/w';\n",
    "export-star-as": "export * as ns from './tests/w';\n",
    "literal-require": "require('./tests/w');\n",
    "template-require": "require(`./tests/w`);\n",
    "literal-dynamic-import": "export const p = import('./tests/w');\n",
    "import-equals-require": "import w = require('./tests/w');\nexport const k = w;\n",
    "rejected-specifier": "require('./tests/W.JS?x');\n",
    "create-require-meta": CR
    + "const r = createRequire(import.meta.url);\nr('./tests/w');\n",
    "create-require-filename": CR
    + "const r = createRequire(__filename);\nr('./tests/w');\n",
    "module-mock": "jest.mock('./tests/w');\n",
    "named-import": "import { k } from './tests/w';\nexport const j = k;\n",
    "namespace-import": "import * as w from './tests/w';\nexport const j = w.k;\n",
}


@pytest.mark.parametrize("source", sorted(PROMOTING_SOURCES))
def test_every_file_naming_source_promotes(tmp_path: Path, source: str) -> None:
    root = _write(
        tmp_path,
        {
            **O2_CR,
            "tests/w.ts": "require('../svc').t = () => 'evil';\nexport const k = 1;\n",
            "app.ts": PROMOTING_SOURCES[source],
        },
    )
    off, _, on, label = _run(root, "use.ts", "t")
    assert on == off, source
    assert label == "none(commonjs)", source


@pytest.mark.parametrize(
    "segment",
    [
        "BUILD~1",
        "node_m~1",
        "dist~12.abc",
        "build::$INDEX_ALLOCATION",
        "a:b",
        "bu\u0131ld",
    ],
)
def test_p5_32_short_names_and_streams_are_uncomputable(
    tmp_path: Path, segment: str
) -> None:
    """P5-32: an 8.3 short name may alias any directory (``BUILD~1`` for
    ``build``), and a segment with ``:`` may be an NTFS stream, so both are
    uncomputable."""
    index = modules.ModuleIndex.build(["use.ts"], None)
    specifier = f"./{segment}/helpers/w"
    assert modules.lenient_targets(index, specifier, "use.ts") is None
    root = _write(
        tmp_path,
        {
            **OTHERS,
            "svc.ts": SVC,
            "use.ts": USE,
            "x.js": f"require('{specifier}').t = 0;\n",
        },
    )
    off, _, on, label = _run(root, "use.ts", "t")
    assert on == off, segment
    assert label == "none(run-tainted:unresolvable-writer)", segment


def test_p5_32_ordinary_segments_stay_computable() -> None:
    index = modules.ModuleIndex.build(["lib/w.ts", "my~lib/w.ts"], None)
    assert modules.lenient_targets(index, "./lib/w", "use.ts") == ("lib/w.ts",)
    assert modules.lenient_targets(index, "./my~lib/w", "use.ts") == ("my~lib/w.ts",)


# ---------------------------------------------------------------------------
# PR 5 fold 9 (executive ruling E5-7): no text scan. Every JS/TS file that
# tree-sitter cannot parse cleanly is a run-wide ``unparsed-file`` cause,
# scoped by O-2. ``function (`` makes each file unparseable.

BROKEN = "\nfunction (\n"
# The Codex repros on 6d0aadd0 and the president's P5-40..P5-43/P5-45
# escapes from the removed text scan.
UNPARSED_ESCAPES = {
    "codex-concatenation": "const m = require('./' + 'svc'); m.t = () => 2;",
    "codex-escaped-relative": "require('\\./svc').t = () => 2;",
    "p5-40-regex-after-paren": "if (c) /'/.test(s);\nrequire(name).t = 1;",
    "p5-41-typeof-chain": "typeof require(name).t;",
    "p5-42-unicode-space": "\u3000require(name).t = 1;",
    "p5-43-html-comment": "<!-- x\nrequire(name).t = 1;",
    "p5-45-hash-import": "import k from '#svc';\nk.t = 1;",
}


def _unparsed_tree(location: str, text: str) -> dict[str, str]:
    return {
        **OTHERS,
        "svc.ts": SVC,
        "use.ts": USE,
        "use.test.ts": TEST_USE,
        location: text + BROKEN,
    }


@pytest.mark.parametrize("case", sorted(UNPARSED_ESCAPES))
def test_e5_7_unparsed_production_files_are_run_wide(tmp_path: Path, case: str) -> None:
    """(a) An unparsed production file fails every caller closed."""
    root = _write(tmp_path, _unparsed_tree("x.js", UNPARSED_ESCAPES[case]))
    facts = extract_symbol_facts_for_file(root / "x.js", root, call_resolution=MODE)
    assert facts["scope_facts"]["supported"] is False, case
    assert facts["scope_facts"]["module_bindings"] == {}, case
    for caller in ("use.ts", "use.test.ts"):
        off, _, on, label = _run(root, caller, "t")
        assert on == off, (case, caller)
        assert label == "none(run-tainted:unparsed-file)", (case, caller)


@pytest.mark.parametrize("case", sorted(UNPARSED_ESCAPES))
def test_e5_7_unparsed_test_files_are_test_scoped(tmp_path: Path, case: str) -> None:
    """(b) The same file under ``tests/`` affects only test callers."""
    root = _write(tmp_path, _unparsed_tree("tests/x.js", UNPARSED_ESCAPES[case]))
    _, _, on, label = _run(root, "use.ts", "t")
    assert on["resolution"] == "resolved", (case, label)
    off, _, on, label = _run(root, "use.test.ts", "t")
    assert on == off, case
    assert label == "none(run-tainted:unparsed-file)", case


@pytest.mark.parametrize(
    "link",
    ["import './tests/x';\n", "require('./tests/x');\n"],
    ids=["import", "require"],
)
def test_e5_7_a_reached_unparsed_test_file_is_promoted(
    tmp_path: Path, link: str
) -> None:
    """(c) A production file reaching an unparsed ``tests/`` file promotes
    it, so its cause is run-wide (promotion uses the parsed file's edge)."""
    tree = _unparsed_tree("tests/x.js", "const k = 1;")
    tree["app.ts"] = link
    root = _write(tmp_path, tree)
    off, _, on, label = _run(root, "use.ts", "t")
    assert on == off
    assert label == "none(run-tainted:unparsed-file)"


def test_e5_7_clean_parsed_files_are_unaffected(tmp_path: Path) -> None:
    """(d) The same content without the parse error leaves production
    resolved (``require('./other')`` taints only ``./other``)."""
    root = _write(
        tmp_path,
        {**OTHERS, "svc.ts": SVC, "use.ts": USE, "x.js": "require('./other');\n"},
    )
    facts = extract_symbol_facts_for_file(root / "x.js", root, call_resolution=MODE)
    assert facts["scope_facts"]["supported"] is True
    _, _, on, label = _run(root, "use.ts", "t")
    assert on["resolution"] == "resolved", label


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        (
            "arguments[1]('./s' + 'vc').t = () => 2;\n",
            "none(run-tainted:dynamic-loader)",
        ),
        ("const a = arguments;\na[1](name);\n", "none(run-tainted:dynamic-loader)"),
        ("f(arguments);\n", "none(run-tainted:dynamic-loader)"),
    ],
    ids=["president-repro", "alias", "passed-on"],
)
def test_p5_44_module_level_arguments(tmp_path: Path, text: str, reason: str) -> None:
    """P5-44: at module level the CommonJS wrapper's ``arguments`` holds
    ``require``; any use but ``typeof`` or an equality operand is a
    ``dynamic-loader`` cause."""
    root = _write(tmp_path, {**OTHERS, "svc.ts": SVC, "use.ts": USE, "x.js": text})
    facts = extract_symbol_facts_for_file(root / "x.js", root, call_resolution=MODE)
    assert facts["scope_facts"]["supported"] is True
    off, _, on, label = _run(root, "use.ts", "t")
    assert on == off
    assert label == reason


@pytest.mark.parametrize(
    "text",
    [
        "export function f() { return arguments[0]; }\n",
        "export const k = typeof arguments;\n",
        "export const j = (x: unknown) => x === arguments;\n",
    ],
    ids=["function-own-arguments", "typeof", "equality"],
)
def test_p5_44_controls(tmp_path: Path, text: str) -> None:
    root = _write(tmp_path, {**OTHERS, "svc.ts": SVC, "use.ts": USE, "x.ts": text})
    _, _, on, label = _run(root, "use.ts", "t")
    assert on["resolution"] == "resolved", label


# Each snippet isolates a syntax trigger in a file unrelated to the import.
@pytest.mark.parametrize(
    "text",
    [
        "function inspect() { return inspect.caller; }",
        "function inspect() { return arguments.callee.caller; }",
        "function inspect(fn) { return fn?.['caller']; }",
        r"function inspect(fn) { return fn[`c\u0061ller`]; }",
        "function inspect(fn) { return Reflect.get(fn, 'caller'); }",
        "Object.getOwnPropertyDescriptor(Function.prototype, 'caller');",
        "function inspect(fn) { const {caller: frame} = fn; return frame; }",
        "function inspect(fn) { const {caller} = fn; return caller; }",
        "function inspect(frame) { return frame.getFunction(); }",
        "function inspect(frame) { return frame['getFunction'](); }",
        r"function inspect(frame) { return frame[`get\u0046unction`](); }",
        r"const key = `get\u0046unction`;",
        "Error.prepareStackTrace = (error, frames) => frames;",
        r"globalThis.Error[`prepare\u0053tackTrace`] = (_, frames) => frames;",
        "Error.prepareStackTrace = (_, frames) => frames; Error.captureStackTrace({});",
        "{ const Error = {}; } Error.prepareStackTrace = (error, frames) => frames;",
        "function f(Error) {} Error.prepareStackTrace = (error, frames) => frames;",
    ],
    ids=[
        "caller",
        "callee-caller",
        "computed-caller",
        "cooked-caller",
        "reflect-get",
        "descriptor",
        "destructure",
        "shorthand-destructure",
        "get-function",
        "computed-get-function",
        "cooked-get-function",
        "constant-get-function",
        "prepare-stack-trace",
        "computed-prepare-stack-trace",
        "capture-with-hook",
        "sibling-block-error-shadow",
        "sibling-function-error-shadow",
    ],
)
def test_718_stack_introspection(tmp_path: Path, text: str) -> None:
    root = _write(tmp_path, {**OTHERS, "svc.ts": SVC, "use.ts": USE, "x.js": text})
    facts = extract_symbol_facts_for_file(root / "x.js", root, call_resolution=MODE)
    assert "module-system" in facts["scope_facts"]["module_bindings"]["shutoff"]
    off, structural, on, label = _run(root, "use.ts", "t")
    assert on == structural == off
    # A computed escape or Function reference may already report evaluator.
    assert label in {"none(run-tainted:module-system)", "none(run-tainted:evaluator)"}


@pytest.mark.parametrize(
    "text",
    [
        "const labels = {name: 'caller-name', other: `myGetFunction`};",
        "function inspect(Error) { Error.prepareStackTrace = () => ''; }",
        "function f(globalThis) { globalThis.Error.prepareStackTrace = (e, s) => s; }",
        "const foo = {}; foo.Error.prepareStackTrace = (e, s) => s;",
        "Error.captureStackTrace({});",
    ],
)
def test_718_stack_introspection_controls(tmp_path: Path, text: str) -> None:
    root = _write(tmp_path, {**OTHERS, "svc.ts": SVC, "use.ts": USE, "x.js": text})
    _, _, on, label = _run(root, "use.ts", "t")
    assert on["resolution"] == "resolved", label


@pytest.mark.parametrize(
    "text",
    [
        pytest.param(
            "const k = 'caller';\n"
            "function g() { return g[k].arguments[1]; }\n"
            "g()('./svc').t = () => 'EVIL';\n",
            id="C03-const-key",
        ),
        pytest.param(
            "function g() { const k = Object.getOwnPropertyNames(g).find(n => n === 'caller'); return g[k].arguments[1]; }\n"
            "g()('./svc').t = () => 'EVIL';\n",
            id="C05-filter-names",
        ),
        pytest.param(
            "const get = Reflect.get;\n"
            "function g() { return get(g, 'caller').arguments[1]; }\n"
            "g()('./svc').t = () => 'EVIL';\n",
            id="C07-reflect-get-alias",
        ),
        pytest.param(
            "function g() { return Reflect.get.call(null, g, 'caller').arguments[1]; }\n"
            "g()('./svc').t = () => 'EVIL';\n",
            id="C08-reflect-get-call",
        ),
        pytest.param(
            "function g() { return Reflect.getOwnPropertyDescriptor(g, 'caller').value.arguments[1]; }\n"
            "g()('./svc').t = () => 'EVIL';\n",
            id="C10-reflect-gopd",
        ),
        pytest.param(
            "function g() { for (const n of Object.getOwnPropertyNames(g)) { switch (n) { case 'caller': return g[n].arguments[1]; } } }\n"
            "g()('./svc').t = () => 'EVIL';\n",
            id="C13-switch-case",
        ),
        pytest.param(
            "function g(k = 'caller') { return g[k].arguments[1]; }\n"
            "g()('./svc').t = () => 'EVIL';\n",
            id="C16-default-param",
        ),
        pytest.param(
            "function g() { return ['caller'].map(k => g[k])[0].arguments[1]; }\n"
            "g()('./svc').t = () => 'EVIL';\n",
            id="C17-array-map",
        ),
        pytest.param(
            "const k = 'caller';\n"
            "function g() { const { [k]: c } = g; return c.arguments[1]; }\n"
            "g()('./svc').t = () => 'EVIL';\n",
            id="C18-destructure-computed-var",
        ),
        pytest.param(
            "const o = { k: 'caller' };\n"
            "function g() { return g[o.k].arguments[1]; }\n"
            "g()('./svc').t = () => 'EVIL';\n",
            id="C21-object-literal-value",
        ),
        pytest.param("const labels = {caller: 'caller'};", id="object-labels"),
        pytest.param(r"const key = `c\u0061ller`;", id="cooked-template"),
        pytest.param(r"const key = 'c\141ller';", id="cooked-sloppy-string"),
    ],
)
def test_718_constant_stack_keys(tmp_path: Path, text: str) -> None:
    root = _write(tmp_path, {**OTHERS, "svc.ts": SVC, "use.ts": USE, "x.js": text})
    off, structural, on, label = _run(root, "use.ts", "t")
    assert on == structural == off
    assert label == "none(run-tainted:module-system)"


@pytest.mark.parametrize(
    ("filename", "text"),
    [
        pytest.param(
            "x.ts",
            "enum K { caller }\n"
            "function g(): any { return (g as any)[K[0]].arguments[1]; }\n"
            "(g() as any)('./svc').t = () => 'EVIL';\n",
            id="E03-enum-reverse-index",
        ),
        pytest.param(
            "x.js",
            "const o = { caller: 1 };\n"
            "function g() { return g[Object.keys(o)[0]].arguments[1]; }\n"
            "g()('./svc').t = () => 'EVIL';\n",
            id="H10-obj-key-keys",
        ),
        pytest.param(
            "x.js",
            "const o = { caller() {} };\n"
            "function g() { return g[Object.keys(o)[0]].arguments[1]; }\n"
            "g()('./svc').t = () => 'EVIL';\n",
            id="H11-obj-method-keys",
        ),
        pytest.param(
            "x.js",
            "const caller = 1;\n"
            "function g() { return g[Object.keys({ caller })[0]].arguments[1]; }\n"
            "g()('./svc').t = () => 'EVIL';\n",
            id="H12-obj-shorthand-keys",
        ),
        pytest.param(
            "x.js",
            "class A { caller() {} }\n"
            "function g() { return g[Object.getOwnPropertyNames(A.prototype)[1]].arguments[1]; }\n"
            "g()('./svc').t = () => 'EVIL';\n",
            id="H13-class-method-names",
        ),
        pytest.param(
            "x.js",
            "function caller() {}\n"
            "function g() { return g[caller.name].arguments[1]; }\n"
            "g()('./svc').t = () => 'EVIL';\n",
            id="H14-fn-name",
        ),
        pytest.param(
            "x.js",
            "const E = Error; E.prepareStackTrace = (e, s) => s; const fr = new Error().stack; E.prepareStackTrace = undefined;\n"
            "const o = { getFunction: 1 };\n"
            "fr[0][Object.keys(o)[0]]().arguments[1]('./svc').t = () => 'EVIL';\n",
            id="H15-getFunction-obj-key",
        ),
        pytest.param(
            "x.js",
            "class A { static caller = 1 }\n"
            "function g() { return g[Object.keys(A)[0]].arguments[1]; }\n"
            "g()('./svc').t = () => 'EVIL';\n",
            id="H16-class-static-field-keys",
        ),
        pytest.param(
            "x.js",
            "const E = Error; E.prepareStackTrace = (e, s) => s; const fr = new Error().stack; E.prepareStackTrace = undefined;\n"
            "const getFunction = 0;\n"
            "fr[0][Object.keys({ getFunction })[0]]().arguments[1]('./svc').t = () => 'EVIL';\n",
            id="H17-var-name-shorthand-getFunction",
        ),
        pytest.param(
            "x.js",
            "function g() { return g[/caller/.source].arguments[1]; }\n"
            "g()('./svc').t = () => 'EVIL';\n",
            id="H20-regex-source",
        ),
        pytest.param(
            "x.js",
            "function g() { const k = Object.getOwnPropertyNames(g).find(n => /^caller$/.test(n)); return g[k].arguments[1]; }\n"
            "g()('./svc').t = () => 'EVIL';\n",
            id="H21-regex-filter",
        ),
        pytest.param(
            "x.js",
            "const E = Error; E.prepareStackTrace = (e, s) => s; const fr = new Error().stack; E.prepareStackTrace = undefined;\n"
            "const P = Object.getPrototypeOf(fr[0]); const m = Object.getOwnPropertyNames(P).find(n => /^getFunction$/.test(n));\n"
            "fr[0][m]().arguments[1]('./svc').t = () => 'EVIL';\n",
            id="H22-regex-filter-getFunction",
        ),
        pytest.param("x.ts", "class caller {}", id="class-name"),
        pytest.param("x.js", "caller();", id="free-name"),
        pytest.param(
            "x.js",
            "{ let caller = 0; } caller();",
            id="sibling-variable-does-not-exempt",
        ),
        pytest.param(
            "x.js", "let other = 0; export { other as caller };", id="export-name"
        ),
        pytest.param(
            "x.js", "const caller = 0; export { caller };", id="export-shorthand"
        ),
        pytest.param(
            "x.js",
            "const caller = 0; export * as caller from './svc';",
            id="export-namespace",
        ),
        pytest.param(
            "x.ts",
            "class C { constructor(readonly caller: number) {} }",
            id="parameter-property",
        ),
        pytest.param(
            "x.tsx", "const caller = 0; const x = <caller />;", id="jsx-intrinsic"
        ),
        pytest.param("x.ts", "type caller = number;", id="type-name"),
        pytest.param("x.js", "const key = `caller${suffix}`;", id="template-part"),
        # R-718-3: lexical bindings are no longer exempt (the r2 controls).
        pytest.param(
            "x.js",
            "function inspect(caller, getFunction) { return caller(getFunction); }",
            id="parameters",
        ),
        pytest.param(
            "x.js",
            "let caller; var getFunction; caller = getFunction;",
            id="let-var-assign",
        ),
        pytest.param("x.js", "const caller = () => 1; caller();", id="const-arrow"),
        # The shorthand node is the only token spelling the name.
        pytest.param("x.js", "const { caller } = fn;", id="shorthand-pattern-only"),
        pytest.param("x.js", "const o = { caller };", id="shorthand-expression-only"),
        pytest.param(
            "x.js", "const { key: caller } = obj; caller();", id="pattern-value"
        ),
        pytest.param(
            "x.js", "for (let caller of items) { caller(); }", id="for-of-let"
        ),
        pytest.param(
            "x.js", "try {} catch (caller) { caller(); }", id="catch-parameter"
        ),
        pytest.param(
            "x.js",
            "const caller = 1; export { caller as other };",
            id="export-alias-source",
        ),
    ],
)
def test_718_stack_name_tokens(tmp_path: Path, filename: str, text: str) -> None:
    root = _write(tmp_path, {**OTHERS, "svc.ts": SVC, "use.ts": USE, filename: text})
    off, structural, on, label = _run(root, "use.ts", "t")
    assert on == structural == off
    assert label == "none(run-tainted:module-system)"


_R3_T = "g()('./svc').t = () => 'EVIL';\n"
_R3_TS_T = "(g() as any)('./svc').t = () => 'EVIL';\n"
_R3_GF = (
    "const E = Error; E.prepareStackTrace = (e, s) => s; "
    "const fr = new Error().stack; E.prepareStackTrace = undefined;\n"
)
_R3_KEYS = (
    "function g() { return g[Object.keys(require('./k'))[0]].arguments[1]; }\n" + _R3_T
)


def _r3_g(expr: str) -> str:
    return f"function g() {{ return g[{expr}].arguments[1]; }}\n" + _R3_T


# R-718-3 (B-4): a binding's name reaches runtime through NamedEvaluation
# (``.name``) or an export key. Each case prints EVIL on node v24 (the r3
# re-check, ``node3.log``).
@pytest.mark.parametrize(
    "files",
    [
        pytest.param(
            {"x.js": "const caller = function () {};\n" + _r3_g("caller.name")},
            id="B01-const-fnexpr-name",
        ),
        pytest.param(
            {"x.js": "let caller = () => {};\n" + _r3_g("caller.name")},
            id="B02-let-arrow-name",
        ),
        pytest.param(
            {"x.js": "var caller = () => {};\n" + _r3_g("caller.name")},
            id="B03-var-arrow-name",
        ),
        pytest.param(
            {"x.js": "const caller = class {};\n" + _r3_g("caller.name")},
            id="B04-const-classexpr-name",
        ),
        pytest.param(
            {
                "x.js": "function h(caller = () => {}) { return caller.name; }\n"
                + _r3_g("h()")
            },
            id="B05-default-param-arrow",
        ),
        pytest.param(
            {"x.js": "const [caller = () => {}] = [];\n" + _r3_g("caller.name")},
            id="B07-array-destructure-default",
        ),
        pytest.param(
            {"x.js": "let caller; caller = () => {};\n" + _r3_g("caller.name")},
            id="B08-assign-later-arrow",
        ),
        pytest.param(
            {
                "x.js": _R3_GF + "const getFunction = () => {};\n"
                "fr[0][getFunction.name]().arguments[1]('./svc').t = () => 'EVIL';\n"
            },
            id="B09-getFunction-const-arrow",
        ),
        pytest.param(
            {
                "x.js": "function h(caller = class {}) { return caller.name; }\n"
                + _r3_g("h()")
            },
            id="B10-param-default-classexpr",
        ),
        pytest.param(
            {"x.js": "const caller = async function () {};\n" + _r3_g("caller.name")},
            id="B12-const-async-fn",
        ),
        pytest.param(
            {"x.js": "const caller = function* () {};\n" + _r3_g("caller.name")},
            id="B13-const-generator",
        ),
        pytest.param(
            {"x.js": "let caller; caller ??= () => {};\n" + _r3_g("caller.name")},
            id="B14-logical-assign",
        ),
        pytest.param(
            {"x.js": "const caller = (function () {});\n" + _r3_g("caller.name")},
            id="B15-paren-fnexpr",
        ),
        pytest.param(
            {"x.js": _R3_KEYS, "k.ts": "export const caller = 1;\n"},
            id="B33-ts-export-const",
        ),
        pytest.param(
            {"x.js": _R3_KEYS, "k.ts": "export const caller = () => {};\n"},
            id="B34-ts-export-const-arrow",
        ),
        pytest.param(
            {"x.js": _R3_KEYS, "k.ts": "export let caller = 1;\n"},
            id="B36-ts-export-let",
        ),
        pytest.param(
            {
                "x.ts": "namespace N { export const caller = 1; }\n"
                "function g() { return (g as any)[Object.keys(N)[0]].arguments[1]; }\n"
                + _R3_TS_T
            },
            id="N01-ts-namespace-export",
        ),
        pytest.param(
            {
                "x.ts": "const caller = (() => {}) as any;\n"
                "function g() { return (g as any)[caller.name].arguments[1]; }\n"
                + _R3_TS_T
            },
            id="N02-ts-as-arrow-name",
        ),
        pytest.param(
            {
                "x.js": "function h(caller) { caller = () => {}; return caller.name; }\n"
                + _r3_g("h()")
            },
            id="N03-param-reassign-arrow",
        ),
    ],
)
def test_718_r3_named_bindings(tmp_path: Path, files: dict[str, str]) -> None:
    root = _write(tmp_path, {**OTHERS, "svc.ts": SVC, "use.ts": USE, **files})
    off, structural, on, label = _run(root, "use.ts", "t")
    assert on == structural == off
    assert label == "none(run-tainted:module-system)"


_R3_PRAGMA_TEXT = "/** @jsx h */\nfunction h(t, p, ...c) { return c[0]; }\n"
_R3_PRAGMA_ATTR = "/** @jsx h */\nfunction h(t, p) { return p.a; }\n"


# R-718-3 (B-5): JSX text and attribute strings decode HTML character
# references. J01 and J02 print EVIL on node v24 (classic-runtime emit).
@pytest.mark.parametrize(
    ("filename", "text"),
    [
        pytest.param("x.jsx", _R3_PRAGMA_TEXT + _r3_g("<i>caller</i>"), id="J01"),
        pytest.param(
            "x.jsx", _R3_PRAGMA_ATTR + _r3_g('<i a="call&#101;r" />'), id="J02"
        ),
        pytest.param("x.jsx", "const x = <i>call&#x65;r</i>;", id="text-hex"),
        pytest.param("x.jsx", "const x = <i>call&#X65;r</i>;", id="text-hex-upper"),
        pytest.param("x.jsx", "const x = <i>&#99;aller</i>;", id="text-decimal"),
        pytest.param("x.jsx", "const x = <i>&#00099;aller</i>;", id="text-zero-padded"),
        pytest.param("x.tsx", "const x = <i>get&#70;unction</i>;", id="text-tsx"),
        pytest.param(
            "x.jsx", "const x = <i>Who is the caller?</i>;", id="text-substring"
        ),
        pytest.param("x.jsx", "const x = <><b /> getFunction </>;", id="text-fragment"),
        pytest.param(
            "x.jsx", "const x = <i>&lt;mainModule&gt;</i>;", id="text-module-system"
        ),
        pytest.param(
            "x.jsx", "const x = <i a='call&#x65;r' />;", id="attr-single-quote-hex"
        ),
        pytest.param(
            "x.tsx", 'const x = <i a="&#103;etFunction" />;', id="attr-tsx-decimal"
        ),
        pytest.param(
            "x.jsx", 'const x = <i a="c&#97;ll&#x65;r" />;', id="attr-two-references"
        ),
    ],
)
def test_718_r3_jsx_strings(tmp_path: Path, filename: str, text: str) -> None:
    root = _write(tmp_path, {**OTHERS, "svc.ts": SVC, "use.ts": USE, filename: text})
    facts = extract_symbol_facts_for_file(root / filename, root, call_resolution=MODE)
    assert "module-system" in facts["scope_facts"]["module_bindings"]["shutoff"]
    off, structural, on, label = _run(root, "use.ts", "t")
    assert on == structural == off
    assert label == "none(run-tainted:module-system)"


@pytest.mark.parametrize(
    ("raw", "values"),
    [
        ("call&#101;r", ("caller", "caller")),
        ("call&#x65;r", ("caller", "caller")),
        ("&#0000099;aller", ("caller", "caller")),
        ("it&apos;s &amp; &lt;", ("it's & <", "it's & <")),
        # html.unescape also decodes a reference with no ``;`` and HTML5
        # names; the JSX spec keeps both literal. Either value is matched.
        ("call&#101r", ("call&#101r", "caller")),
        ("&period;", ("&period;", ".")),
        ("&#x110000;", ("&#x110000;", "\ufffd")),
        ("c\x61ller", ("c\x61ller", "c\x61ller")),
    ],
)
def test_718_r3_decode_jsx_text(raw: str, values: tuple[str, str]) -> None:
    assert decode_jsx_text(raw) == values


@pytest.mark.parametrize(
    ("filename", "text"),
    [
        pytest.param("x.jsx", "const x = <i>call er</i>;", id="text-split"),
        pytest.param("x.jsx", "const x = <i>call\ner</i>;", id="text-line-split"),
        # A backslash is literal in JSX: no JS escape decodes.
        pytest.param("x.jsx", 'const x = <i a="call\\x65r" />;', id="attr-js-escape"),
        pytest.param("x.jsx", 'const x = <i a="callers-list" />;', id="attr-not-exact"),
        pytest.param("x.tsx", 'const x = <i a="call&amp;er">ok</i>;', id="attr-amp"),
    ],
)
def test_718_r3_jsx_controls(tmp_path: Path, filename: str, text: str) -> None:
    root = _write(tmp_path, {**OTHERS, "svc.ts": SVC, "use.ts": USE, filename: text})
    _, _, on, label = _run(root, "use.ts", "t")
    assert on["resolution"] == "resolved", label


@pytest.mark.parametrize(
    "text",
    [
        pytest.param(
            "function g() { with (g) { return caller.arguments[1]; } }\n"
            "g()('./svc').t = () => 'EVIL';\n",
            id="C12-with",
        ),
        pytest.param(
            "function g(caller) { with (g) { return caller.arguments[1]; } }\n"
            "g()('./svc').t = () => 'EVIL';\n",
            id="C22-with-shadows-local-caller",
        ),
        pytest.param(
            "function g(Reflect) { with (globalThis) { return Reflect.get(g, 'caller').arguments[1]; } }\n"
            "g()('./svc').t = () => 'EVIL';\n",
            id="C23-with-globalThis-Reflect",
        ),
        pytest.param(
            "function g(Object) { with (globalThis) { return Object.getOwnPropertyDescriptor(g, 'caller').value.arguments[1]; } }\n"
            "g()('./svc').t = () => 'EVIL';\n",
            id="C24-with-globalThis-Object-gopd",
        ),
        pytest.param(
            "const E = Error; E.prepareStackTrace = (e, s) => s; const fr = new Error().stack; E.prepareStackTrace = undefined;\n"
            "with (fr[0]) { getFunction().arguments[1]('./svc').t = () => 'EVIL'; }\n",
            id="S08-with-getFunction-ident",
        ),
        pytest.param(
            "const mainModule = 0;\n"
            "with (process) { mainModule.require('./svc').t = () => 'EVIL'; }\n",
            id="P01-with-process-mainModule",
        ),
    ],
)
def test_718_with_statement(tmp_path: Path, text: str) -> None:
    root = _write(tmp_path, {**OTHERS, "svc.ts": SVC, "use.ts": USE, "x.js": text})
    facts = extract_symbol_facts_for_file(root / "x.js", root, call_resolution=MODE)
    assert "dynamic-scope" in facts["scope_facts"]["module_bindings"]["shutoff"]
    off, structural, on, label = _run(root, "use.ts", "t")
    assert on == structural == off
    assert label in {
        "none(run-tainted:dynamic-scope)",
        "none(run-tainted:module-system)",
    }


@pytest.mark.parametrize(
    "text",
    [
        "interface F { caller: unknown }",
        "interface F { ['caller']: unknown }",
        "type F = { getFunction(): void };",
        "type F = 'getFunction';",
    ],
)
def test_718_type_space_tokens(tmp_path: Path, text: str) -> None:
    root = _write(tmp_path, {**OTHERS, "svc.ts": SVC, "use.ts": USE, "x.ts": text})
    off, structural, on, label = _run(root, "use.ts", "t")
    assert on == structural == off
    assert label == "none(run-tainted:module-system)"


@pytest.mark.parametrize("promoted", [False, True])
@pytest.mark.parametrize(
    ("text", "cause"),
    [
        ("function inspect(frame) { return frame.getFunction(); }", "module-system"),
        ("const key = 'caller';", "module-system"),
        ("function inspect(object) { with (object) {} }", "dynamic-scope"),
    ],
)
def test_718_stack_introspection_test_scope(
    tmp_path: Path, promoted: bool, text: str, cause: str
) -> None:
    files = {
        **OTHERS,
        "svc.ts": SVC,
        "use.ts": USE,
        "tests/use.test.ts": USE.replace("./svc", "../svc"),
        "tests/frames.js": text,
    }
    if promoted:
        files["app.ts"] = "import './tests/frames';"
    root = _write(tmp_path, files)
    _, _, test_edge, test_label = _run(root, "tests/use.test.ts", "t")
    assert test_edge["resolution"] == "ambiguous"
    assert test_label == f"none(run-tainted:{cause})"
    _, _, prod_edge, prod_label = _run(root, "use.ts", "t")
    if promoted:
        assert prod_edge["resolution"] == "ambiguous"
        assert prod_label == test_label
    else:
        assert prod_edge["resolution"] == "resolved", prod_label


def test_p5_41_parsed_typeof_require_chain_is_a_loader(tmp_path: Path) -> None:
    """The parsed path never exempts ``typeof require(...)…``."""
    root = _write(
        tmp_path,
        {**OTHERS, "svc.ts": SVC, "use.ts": USE, "x.js": "typeof require(name).t;\n"},
    )
    off, _, on, label = _run(root, "use.ts", "t")
    assert on == off
    assert label == "none(run-tainted:dynamic-loader)"


def test_p5_37_short_name_after_trailing_dot_or_space() -> None:
    """P5-37: Win32 strips a trailing dot or space before the 8.3 match."""
    index = modules.ModuleIndex.build(["use.ts"], None)
    for segment in ("BUILD~1.", "BUILD~1 ", "node_m~1. "):
        assert modules.lenient_targets(index, f"./{segment}/w", "use.ts") is None


# ---------------------------------------------------------------------------
# PR 5 fold 10 (the president's re-check at 9bcd20c1, P5-47..P5-49). Files
# are written as bytes so line terminators are exact on every OS.


def _write_bytes(root: Path, files: dict[str, bytes]) -> Path:
    for name, data in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return root


WRITE = b"require('./svc').t = () => 2;\n"
P5_47_UNPARSED = {
    "hashbang-cr.js": b"#!/usr/bin/env node\r" + WRITE,
    "hashbang-ls.js": "#!/usr/bin/env node ".encode() + WRITE,
    "hashbang-ps.js": "#!/usr/bin/env node ".encode() + WRITE,
    "hashbang-cr.ts": b"#!/usr/bin/env node\rObject.assign(require('./svc'), { t: () => 2 });\n",
    "hashbang-cr-esm.ts": (
        b"#!/usr/bin/env node\rimport * as ns from './svc';\n"
        b"Object.assign(ns, { t: () => 2 });\n"
    ),
    "html-open-cr.js": b"<!-- c\r" + WRITE,
    "html-close-cr.js": b"var x = 1\n--> c\r" + WRITE,
    "html-open.ts": b"var y = 2;\n<!--y, require('./svc').t = () => 2;\n",
}


@pytest.mark.parametrize("name", sorted(P5_47_UNPARSED))
def test_p5_47_misread_line_terminators_are_unparsed(tmp_path: Path, name: str) -> None:
    root = _write(tmp_path, {**OTHERS, "svc.ts": SVC, "use.ts": USE})
    _write_bytes(root, {name: P5_47_UNPARSED[name]})
    facts = extract_symbol_facts_for_file(root / name, root, call_resolution=MODE)
    assert facts["scope_facts"]["supported"] is False, name
    off, _, on, label = _run(root, "use.ts", "t")
    assert on == off, name
    assert label == "none(run-tainted:unparsed-file)", name


def test_p5_47_crlf_files_stay_parsed(tmp_path: Path) -> None:
    root = _write(tmp_path, {**OTHERS, "svc.ts": SVC, "use.ts": USE})
    _write_bytes(
        root, {"x.js": b"#!/usr/bin/env node\r\nrequire('./other');\r\n// c\r\n"}
    )
    facts = extract_symbol_facts_for_file(root / "x.js", root, call_resolution=MODE)
    assert facts["scope_facts"]["supported"] is True
    _, _, on, label = _run(root, "use.ts", "t")
    assert on["resolution"] == "resolved", label


P5_48_REPROS = {
    "var": "var arguments;\narguments[1]('./s' + 'vc').t = () => 2;\n",
    "var-self": "var arguments = arguments;\narguments[1]('./s' + 'vc').t = () => 2;\n",
    "hoisted-var": "arguments[1]('./s' + 'vc').t = () => 2;\nvar arguments;\n",
    "function-then-var": (
        "function f() {}\nvar arguments;\n"
        "const r = arguments[1]; r('./s' + 'vc').t = () => 2;\n"
    ),
    "function-declaration": "function arguments() {}\nexport const k = 1;\n",
}


@pytest.mark.parametrize("case", sorted(P5_48_REPROS))
def test_p5_48_module_scope_arguments_declarations(tmp_path: Path, case: str) -> None:
    root = _write(
        tmp_path, {**OTHERS, "svc.ts": SVC, "use.ts": USE, "x.js": P5_48_REPROS[case]}
    )
    off, _, on, label = _run(root, "use.ts", "t")
    assert on == off, case
    assert label == "none(run-tainted:dynamic-loader)", case


def test_p5_48_function_local_arguments_declaration_is_unaffected(
    tmp_path: Path,
) -> None:
    root = _write(
        tmp_path,
        {
            **OTHERS,
            "svc.ts": SVC,
            "use.ts": USE,
            "x.js": "export function f() { var arguments; return arguments; }\n",
        },
    )
    _, _, on, label = _run(root, "use.ts", "t")
    assert on["resolution"] == "resolved", label


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        (
            "class C { static r = (arguments as any)[1]; }\n"
            "(C as any).r('./s' + 'vc').t = () => 2;\n",
            "none(run-tainted:dynamic-loader)",
        ),
        (
            "class C { static { (arguments as any)[1]('./s' + 'vc').t = () => 2; } }\n",
            "none(run-tainted:dynamic-loader)",
        ),
        (
            "class C { static { require('./svc').t = () => 2; } }\n",
            "none(commonjs)",
        ),
    ],
    ids=["static-field-arguments", "static-block-arguments", "static-block-require"],
)
def test_p5_49_static_members_are_module_level(
    tmp_path: Path, text: str, reason: str
) -> None:
    root = _write(tmp_path, {**OTHERS, "svc.ts": SVC, "use.ts": USE, "x.ts": text})
    off, _, on, label = _run(root, "use.ts", "t")
    assert on == off
    assert label == reason


def test_p5_49_static_field_this_makes_the_module_commonjs(tmp_path: Path) -> None:
    root = _write(
        tmp_path,
        {
            **OTHERS,
            "svc.ts": SVC + "export class K { static s = (this as any).t = 0; }\n",
            "use.ts": USE,
        },
    )
    off, _, on, label = _run(root, "use.ts", "t")
    assert on == off
    assert label == "none(commonjs)"


def test_p5_49_instance_members_stay_unaffected(tmp_path: Path) -> None:
    root = _write(
        tmp_path,
        {
            **OTHERS,
            "svc.ts": SVC
            + "export class K { a = this; m() { return arguments[0]; } }\n",
            "use.ts": USE,
            "x.ts": "export class J { b = 1; m() { return arguments[0]; } }\n",
        },
    )
    _, _, on, label = _run(root, "use.ts", "t")
    assert on["resolution"] == "resolved", label


# ---------------------------------------------------------------------------
# PR 5 fold 11 (the president's re-check at cc3c2d3d, P5-50): Annex B
# HTML-like comments that tree-sitter reads as code in JavaScript.

P5_50_UNPARSED = {
    "mlc-tpl.js": b"var x = 1;\nx /* c\n*/ --> `\n" + WRITE + b"//`;\n",
    "mlc-blk.js": b"var x = 1;\nx /* c\n*/ --> /*\n" + WRITE + b"//*/ 0;\n",
    "mid-open-tpl.js": b"var x = 1, y = 2;\nx <!--y, `\n" + WRITE + b"//`;\n",
    "mid-open-blk.js": b"var x = 1, y = 2;\nx <!--y, /*\n" + WRITE + b"//*/ 0;\n",
    "mlc-tpl-str.js": b"var x = 1;\nx /* c\n*/ --> `\n" + WRITE + b"//` + '';\n",
    "mlc-shadow-tpl.js": (
        b"var x = 1;\nx /* c\n*/ --> 0; var r = require('./other'); `\n"
        + WRITE
        + b"//`;\n"
    ),
    # Controls already unparsed: the comment starts the line.
    "mlc-tpl-nox.js": b"/* c\n*/ --> `\n" + WRITE + b"//`;\n",
    "mlc-tpl-ws.js": b"var x = 1;\nx\n  /* c\n*/ --> `\n" + WRITE + b"//`;\n",
}


@pytest.mark.parametrize("name", sorted(P5_50_UNPARSED))
def test_p5_50_hidden_html_comments_are_unparsed(tmp_path: Path, name: str) -> None:
    root = _write(tmp_path, {**OTHERS, "svc.ts": SVC, "use.ts": USE})
    _write_bytes(root, {name: P5_50_UNPARSED[name]})
    facts = extract_symbol_facts_for_file(root / name, root, call_resolution=MODE)
    assert facts["scope_facts"]["supported"] is False, name
    off, _, on, label = _run(root, "use.ts", "t")
    assert on == off, name
    assert label == "none(run-tainted:unparsed-file)", name


P5_50_PARSED = {
    # No line break inside the comment: V8 also reads ``x-- > `...` ``.
    "mlc-tpl-ctl-lf.js": b"var x = 1;\nx /* c */ --> `\n" + WRITE + b"//`;\n",
    # HTML text outside code: strings, templates, regexes. (tree-sitter
    # already reports an error for ``<!--`` or ``-->`` in JSX.)
    "string.js": b"var s = '<!-- -->';\nvar u = \"-->\";\n",
    "template.js": b"var s = `\n--> ${1} <!--`;\nvar t = `<!-- ${'-->'} -->`;\n",
    "regex.js": b"var r = /<!--/, q = /-->/;\n",
    # ``-->`` after code on its line is ``x-- >``.
    "decrement.js": b"var i = 3;\nwhile (i-->0) {}\n",
    # TypeScript has no HTML-like comments, and tsc agrees with tree-sitter.
    "mid-open.ts": b"var x = 1, y = 2;\nx <!--y, `\n" + WRITE + b"//`;\n",
    "mid-open.tsx": b"var x = 1, y = 2;\nx <!--y, `\n" + WRITE + b"//`;\n",
    "mlc-tpl.ts": b"var x = 1;\nx /* c\n*/ --> `\n" + WRITE + b"//`;\n",
}


@pytest.mark.parametrize("name", sorted(P5_50_PARSED))
def test_p5_50_html_text_outside_code_stays_parsed(tmp_path: Path, name: str) -> None:
    root = _write(tmp_path, {**OTHERS, "svc.ts": SVC, "use.ts": USE})
    _write_bytes(root, {name: P5_50_PARSED[name]})
    facts = extract_symbol_facts_for_file(root / name, root, call_resolution=MODE)
    assert facts["scope_facts"]["supported"] is True, name
    _, _, on, label = _run(root, "use.ts", "t")
    assert on["resolution"] == "resolved", (name, label)


def test_p5_50_substitution_in_a_template_is_code(tmp_path: Path) -> None:
    root = _write(tmp_path, {**OTHERS, "svc.ts": SVC, "use.ts": USE})
    _write_bytes(root, {"x.js": b"var a = 1, b = 2;\nvar s = `${a <!--b}`;\n"})
    facts = extract_symbol_facts_for_file(root / "x.js", root, call_resolution=MODE)
    assert facts["scope_facts"]["supported"] is False

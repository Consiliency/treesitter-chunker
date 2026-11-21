"""Tier 1 JavaScript/TypeScript scope analysis (treesitter-chunker#682, PR 2-3).

Plan ``plans/detailed-scoped-call-resolution-682.md`` sections 7.2, 7.4, 7.5
and 7.6. The expected tables (``test_call_resolution_engine.py``) pin every
fixture call end to end; this module adds:

- analyzer unit cases on short sources, one per rule of 7.2 that the
  fixtures do not isolate;
- the #688 notes for this head: N-1 (proofs name the symbol-carrying
  declaration, never the ``export_statement``), note 1 (a namespace merged
  with a function is dropped before the proof), and B7 (``declare enum``
  gives ``non-callable``);
- the allow-list contract: every handled kind has a handler;
- PR 3: script globals (implicit globals,
  global-object writes and their fail-closed wildcard), TS namespace merging
  and inherited ambient status, with end-to-end trees the tests write.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from chunker.call_resolution import allowlist, js_scope
from chunker.parser import get_parser
from chunker.symbol_graph import extract_symbol_graph
from tests import call_resolution_harness as harness

MODE = "structural"
CALL_NODES = {"call_expression": "function", "new_expression": "constructor"}


def _callees(node: Any, source: bytes, text: str) -> list[Any]:
    found = []
    stack = [node]
    while stack:
        current = stack.pop()
        field = CALL_NODES.get(current.type)
        callee = current.child_by_field_name(field) if field else None
        if callee is not None and source[callee.start_byte : callee.end_byte] == (
            text.encode()
        ):
            found.append(callee)
        stack.extend(reversed(current.children))
    return sorted(found, key=lambda item: item.start_byte)


def outcome(
    source: str, callee: str, language: str = "typescript", occurrence: int = 0
) -> dict[str, Any]:
    """The analyzer's outcome for the ``occurrence``-th call of ``callee``."""
    data = source.encode()
    root = get_parser(language).parse(data).root_node
    assert not root.has_error, source
    node = _callees(root, data, callee)[occurrence]
    span = {"callee_byte_start": node.start_byte, "callee_byte_end": node.end_byte}
    bindings = js_scope.analyze(root, data, language, [span])["bindings"]
    return bindings[f"{node.start_byte}:{node.end_byte}"]


def reason(source: str, callee: str, **kwargs: Any) -> str:
    result = outcome(source, callee, **kwargs)
    assert result["outcome"] == "none", result
    return str(result["reason"])


def proof_text(source: str, callee: str, **kwargs: Any) -> list[str]:
    result = outcome(source, callee, **kwargs)
    assert result["outcome"] == "local", result
    data = source.encode()
    return [data[start:end].decode() for _, start, end in result["proof"]]


def _js_proof(
    source: str, callee: str = "d", **kwargs: Any
) -> tuple[list[str], list[str]]:
    """JavaScript proof text and group rules for one call."""
    result = outcome(source, callee, language="javascript", **kwargs)
    assert result["outcome"] == "local", result
    data = source.encode()
    proof = [data[start:end].decode() for _, start, end in result["proof"]]
    return proof, result["rules"]


# ---------------------------------------------------------------------------
# Scope chain (7.2)

MODULE = "export {};\n"


def test_class_static_block_is_its_own_var_scope() -> None:
    source = MODULE + "function t() {}\nclass K { static { var t = 1; t(); } }"
    assert reason(source, "t") == "local-variable"


def test_class_body_binds_no_bare_names() -> None:
    source = MODULE + "function t() {}\nclass K { t() {} m() { return t(); } }"
    assert proof_text(source, "t") == ["function t() {}"]


def test_class_field_initializer_looks_up_outside_the_class() -> None:
    source = MODULE + "function t() { return 1; }\nclass K { x = t(); }"
    assert proof_text(source, "t") == ["function t() { return 1; }"]


def test_parameter_scope_skips_the_function_body() -> None:
    # The default value cannot see the body's own ``t``.
    source = MODULE + "function t() {}\nfunction f(x = t()) { function t() {} }"
    assert proof_text(source, "t") == ["function t() {}"]


def test_implicit_arguments_is_a_parameter_except_in_arrows() -> None:
    source = MODULE + "function arguments() {}\nfunction f() { return arguments(); }"
    assert reason(source, "arguments") == "parameter"
    arrow = MODULE + "function arguments() {}\nconst f = () => arguments();"
    assert proof_text(arrow, "arguments") == ["function arguments() {}"]


def test_named_generator_expression_binds_its_own_name() -> None:
    source = MODULE + "function g() {}\nconst x = function* g() { g(); };"
    assert reason(source, "g") == "self-binding"


def test_tdz_let_binds_across_its_whole_block() -> None:
    source = MODULE + "function t() {}\nfunction g() { { t(); let t = 1; } }"
    assert reason(source, "t") == "local-variable"


def test_for_switch_and_catch_scopes() -> None:
    loop = MODULE + "function i() {}\nfunction g() { for (let i = 0; ; ) { i(); } }"
    assert reason(loop, "i") == "local-variable"
    cases = (
        MODULE + "function z() {}\nfunction g(x) { switch (x) { case 1: let z; z(); } }"
    )
    assert reason(cases, "z") == "local-variable"
    catch = MODULE + "function e() {}\nfunction g() { try {} catch ({ e }) { e(); } }"
    assert reason(catch, "e") == "local-variable"
    var_loop = MODULE + "function v() {}\nfunction g(o) { for (var v in o) {} v(); }"
    assert reason(var_loop, "v") == "local-variable"


def test_const_function_binding_forms() -> None:
    single = MODULE + "const f = function () {};\nf();"
    assert proof_text(single, "f") == ["function () {}"]
    several = MODULE + "const f = () => 1, g = 2;\nf();"
    assert reason(several, "f") == "expression-bound"
    let_bound = MODULE + "let f = () => 1;\nf();"
    assert reason(let_bound, "f") == "expression-bound"
    generator = MODULE + "const f = function* () {};\nf();"
    assert reason(generator, "f") == "expression-bound"


def test_block_function_gives_none_inside_and_outside_its_block() -> None:
    source = MODULE + "function g() { { function d() {} d(); } return d(); }"
    assert reason(source, "d", occurrence=0) == "block-function"
    assert reason(source, "d", occurrence=1) == "block-function"
    unbraced = "function g(x) { if (x) function d() {} return d(); }"
    assert reason(unbraced, "d", language="javascript") == "block-function"


REASSIGNMENTS = [
    "t = other;",
    "t += 1;",
    "t++;",
    "[t] = [other];",
    "({ t } = { t: other });",
    # Wrapped targets (#689 panel A1, Codex P2): parentheses and TS wrappers.
    "(t)++;",
    "--(t);",
    "++(t);",
    "(t as any) = other;",
    "(<any>t) = other;",
    "(t satisfies any) = other;",
    "t! = other;",
    "t!++;",
    "(t as any) ||= other;",
    "(t as any) += 1;",
    "[t!] = [other];",
    "({ x: t! } = { x: other });",
    "for ((t as any) of [other]) {}",
    "[{ y: [t] }] = [{ y: [other] }];",
]


@pytest.mark.parametrize("write", REASSIGNMENTS)
def test_reassignment_forms(write: str) -> None:
    source = (
        MODULE
        + f"function t() {{}}\nfunction other() {{}}\nfunction g() {{ {write} return t(); }}"
    )
    assert reason(source, "t") == "reassigned"


@pytest.mark.parametrize(
    "write", ["t.x = 1;", "t.x++;", "t[0] = 1;", "(t as any).x = 1;", "t!.x += 1;"]
)
def test_property_writes_are_not_reassignments(write: str) -> None:
    source = MODULE + f"function t() {{}}\nfunction g() {{ {write} return t(); }}"
    assert proof_text(source, "t") == ["function t() {}"]


def test_reassignment_in_a_nested_function_unless_shadowed() -> None:
    nested = (
        MODULE + "function t() {}\nfunction g() { function h() { t = 1; } return t(); }"
    )
    assert reason(nested, "t") == "reassigned"
    shadowed = (
        MODULE
        + "function t() {}\nfunction g() { function h() { let t; t = 1; } return t(); }"
    )
    assert proof_text(shadowed, "t") == ["function t() {}"]


@pytest.mark.parametrize(
    "site",
    [
        # A direct eval anywhere can assign every binding visible from its
        # site, so every scope out to ``program`` is dynamic (#689 panel A3).
        "eval('x');",
        "function f(s) { eval(s); }",
        "const f = (s) => eval(s);",
        "class K { static { eval('t = 1'); } }",
        "function f() { function t() {} eval('x'); }",
        # Wrapped callees are still direct eval (Codex P2).
        "(eval)('t = 1');",
        "function f(s) { eval!(s); }",
        "function f(s) { (eval as any)(s); }",
        "function f(s) { (<any>eval)(s); }",
    ],
)
def test_direct_eval_makes_every_enclosing_scope_dynamic(site: str) -> None:
    source = MODULE + f"function t() {{}}\n{site}\nfunction g() {{ return t(); }}"
    assert reason(source, "t") == "dynamic-scope"


def test_eval_does_not_reach_unrelated_inner_scopes() -> None:
    source = MODULE + "eval('x');\nfunction g() { function t() {} return t(); }"
    # g's own body binds ``t`` before the lookup reaches the dynamic program.
    assert proof_text(source, "t") == ["function t() {}"]
    indirect = MODULE + "function t() {}\n(0, eval)('x');\nfunction g() { return t(); }"
    assert proof_text(indirect, "t") == ["function t() {}"]


def test_with_fails_closed() -> None:
    with_body = "function t() {}\nfunction w(o) { with (o) { t(); } }"
    assert reason(with_body, "t", language="javascript") == "dynamic-scope"


@pytest.mark.parametrize(
    "member",
    [
        # Computed method and property names are evaluated (#689 panel A2).
        "class K { [(t = 1, 'm')]() {} }",
        "const o = { [(t = 1, 'm')]() {} };",
        "class K { get [(t = 1, 'm')]() { return 1; } }",
        "const o = { [(t = 1, 'm')]: 1 };",
        "class K { [(t = 1, 'm')] = 1; }",
    ],
)
def test_writes_in_computed_names_are_seen(member: str) -> None:
    source = MODULE + f"function t() {{}}\n{member}\nfunction g() {{ return t(); }}"
    assert reason(source, "t") == "reassigned"


def test_eval_in_a_computed_name_is_seen() -> None:
    source = (
        MODULE
        + "function t() {}\nclass K { [eval('t = 1')]() {} }\nfunction g() { return t(); }"
    )
    assert reason(source, "t") == "dynamic-scope"


@pytest.mark.parametrize(
    ("member", "expected"),
    [
        ("class K { [((t: any) => t())(x)]() {} }", "parameter"),
        ("class K { [(() => { const t = 1; return t(); })()]() {} }", "local-variable"),
        ("class K { [(function t() { return t(); })()]() {} }", "self-binding"),
    ],
)
def test_lookups_inside_computed_names(member: str, expected: str) -> None:
    source = MODULE + f"function t() {{}}\nconst x = 1;\n{member}"
    assert reason(source, "t") == expected


def test_member_callees_look_up_their_head() -> None:
    source = (
        MODULE + "function g(m) { return m.t(); }\nclass K { n() { return this.m(); } }"
    )
    assert reason(source, "m.t") == "parameter"
    assert reason(source, "this.m") == "unbound"


def test_export_default_function_binds_its_name() -> None:
    source = (
        "export default function t() { return 1; }\nexport function g() { return t(); }"
    )
    assert proof_text(source, "t") == ["function t() { return 1; }"]


def test_unbound_name() -> None:
    assert reason(MODULE + "function g() { return nowhere(); }", "nowhere") == "unbound"


# ---------------------------------------------------------------------------
# Imports, TS forms and interim deferrals


def test_value_imports_are_import_outcomes() -> None:
    source = (
        "import d, { a as b } from './m';\nimport * as ns from './n';\n"
        "export function g() { return d() + b() + ns.f(); }"
    )
    assert outcome(source, "d") == {
        "outcome": "import",
        "binding": {"source": "./m", "name": "default", "form": "default"},
    }
    assert outcome(source, "b")["binding"] == {
        "source": "./m",
        "name": "a",
        "form": "named",
    }
    assert outcome(source, "ns.f")["binding"] == {
        "source": "./n",
        "name": "*",
        "form": "namespace",
    }


def test_type_only_imports() -> None:
    inline = "import { type t } from './m';\nexport function g() { return t(); }"
    assert reason(inline, "t") == "type-only"
    mixed = "import type { t } from './m';\nfunction t() {}\nexport function g() { return t(); }"
    assert proof_text(mixed, "t") == ["function t() {}"]


def test_import_alias_and_import_require_are_non_symbol() -> None:
    alias = "namespace N { export function f() {} }\nimport t = N.f;\nexport function g() { return t(); }"
    assert reason(alias, "t") == "local-variable"
    require = "import t = require('./eq');\nexport function g() { return t(); }"
    assert reason(require, "t") == "local-variable"


def test_using_declarations() -> None:
    js = "function u() {}\nexport function g() { using u = f(); u(); }"
    assert reason(js, "u", language="javascript") == "local-variable"
    # The pinned TypeScript grammar parses ``using`` as an assignment: fail closed.
    ts = "function u() {}\nexport function g() { { using u = f(); u(); } }"
    assert reason(ts, "u") == "unmapped"


def test_mixed_ambient_groups_fail_closed() -> None:
    """#689 panel C2: any ambient member gives ``none(ambient)``."""
    for source in (
        "declare function g(): void;\nfunction g() {}\ng();",
        "function g() {}\ndeclare function g(): void;\ng();",
        "declare function g(): void;\nfunction g(x: number): void;\nfunction g(x?: number) {}\ng();",
    ):
        assert reason(MODULE + source, "g") == "ambient", source
    module_block = "declare module 'm' { function g(): void; }\nfunction g() {}\ng();"
    assert proof_text(MODULE + module_block, "g") == ["function g() {}"]


def test_overload_shape_requires_signatures_then_a_function_body() -> None:
    """#689 panel A4: otherwise every member is proved and nothing resolves."""
    body_first = (
        "export function f(x: any): any { return x; }\nexport function f(x: string): string;\n"
        "export function g() { return f(1); }"
    )
    result = outcome(body_first, "f")
    assert (result["rules"], len(result["proof"])) == ([], 2)
    const_body = "function f(x: string): string;\nconst f = (x: any) => x;\nexport function g() { return f(1); }"
    result = outcome(const_body, "f")
    assert (result["rules"], len(result["proof"])) == ([], 2)


def test_overload_rules() -> None:
    contiguous = (
        "export function f(x: string): string;\nexport function f(x: number): number;\n"
        "export function f(x: any): any { return x; }\nexport function g() { return f(1); }"
    )
    result = outcome(contiguous, "f")
    assert result["rules"] == ["t1.ts_overload"]
    assert len(result["proof"]) == 1
    split = (
        "export function f(x: string): string;\nexport function h() {}\n"
        "export function f(x: any): any { return x; }\nexport function g() { return f(1); }"
    )
    result = outcome(split, "f")
    assert result["rules"] == []
    assert len(result["proof"]) == 2
    two_bodies = (
        "export function f(x: string): string;\nexport function f() { return 1; }\n"
        "export function f() { return 2; }\nexport function g() { return f(); }"
    )
    assert proof_text(two_bodies, "f") == [
        "function f() { return 1; }",
        "function f() { return 2; }",
    ]
    # JavaScript has no signatures; duplicates at a module top level are a group.
    js = "export function f() {}\nfunction f() {}\nexport function g() { f(); }"
    assert len(outcome(js, "f", language="javascript")["proof"]) == 2


def test_script_goal_and_namespace_lookups_follow_r1() -> None:
    """PR 3 replaces the PR 2 deferrals; R-1(i) still orders the reasons."""
    script = "function t() {}\nfunction g() { return t(); }"
    # A script top level proves, and names the global for the engine's
    # cross-file script-global check (7.2).
    result = outcome(script, "t", language="javascript")
    assert result["outcome"] == "local"
    assert result["global"] == "t"
    # R-1(i): an outcome that proves nothing reports its own reason.
    script_param = "function g(t) { return t(); }"
    assert reason(script_param, "t", language="javascript") == "parameter"
    # A single namespace declaration in a module proves, inside or outside.
    namespace = (
        MODULE + "function t() {}\nnamespace N { export function g() { return t(); } }"
    )
    assert proof_text(namespace, "t") == ["function t() {}"]
    inside = (
        MODULE + "namespace N { function t() {} export function g() { return t(); } }"
    )
    assert proof_text(inside, "t") == ["function t() {}"]
    inside_param = MODULE + "namespace N { export function g(t) { return t(); } }"
    assert reason(inside_param, "t") == "parameter"
    unbound = MODULE + "namespace N { export function g() { return nowhere(); } }"
    assert reason(unbound, "nowhere") == "unbound"


# ---------------------------------------------------------------------------
# Script globals (7.2; PR 3)


def script_globals(source: str, language: str = "javascript") -> list[str]:
    data = source.encode()
    root = get_parser(language).parse(data).root_node
    assert not root.has_error, source
    return js_scope.analyze(root, data, language, [])["script_globals"]


def test_script_globals_of_a_script() -> None:
    source = (
        "var a = 1; let b = 2; const c = 3; class K {} function f() {}\n"
        "if (x) { var v = 1; let blockLocal = 2; function bf() {} }\n"
        "function g() { implicit = 1; var local = 2; local = 3; inner++; }\n"
        "for (loopGlobal in o) {}\n"
    )
    assert script_globals(source) == [
        "K",
        "a",
        "b",
        "bf",
        "c",
        "f",
        "g",
        "implicit",
        "inner",
        "loopGlobal",
        "v",
    ]
    ts = "namespace N {}\nenum E { A }\ndeclare function amb(): void;\nimport t = N.f;"
    assert script_globals(ts, "typescript") == ["E", "N", "amb", "t"]


def test_script_globals_of_a_module() -> None:
    """A module's own top level is not global; global-object writes are."""
    source = (
        "export function f() {}\nlet b = 2;\nfunction g() { implicit = 1; }\n"
        "window.w = 1;\nglobalThis['gt'] = 2;\nself.s += 1;\nglobal.n++;\n"
        "window.top.chain = 3;\n[window.pattern] = xs;\nfor (window.loop of xs) {}\n"
        "delete window.deleted;\n"
        "this.notGlobal = 1;\nfunction h() { this.alsoNot = 1; }\n"
    )
    assert script_globals(source) == [
        "chain",
        "deleted",
        "gt",
        "loop",
        "n",
        "pattern",
        "s",
        "w",
    ]
    declare_global = (
        "export {};\ndeclare global { function dg(): void; var dv: number; }"
    )
    assert script_globals(declare_global, "typescript") == ["dg", "dv"]


GLOBAL_WILDCARD_FORMS = {
    "computed-key": "globalThis[k] = f;",
    "template-key": "window[`d`] = f;",
    "escaped-string-key": "window['\\x64'] = f;",
    "computed-read": "window[k]();",
    "argument": "Object.assign(window, { d: f });",
    "alias": "const g = globalThis; g.d = f;",
    "shorthand": "register({ window });",
    "conditional": "const root = typeof self !== 'undefined' ? self : this;",
    "chain-alias": "const w = window.window;",
    "eval-property": "window.eval(s);",
    "eval": "(0, eval)(s);",
    "function-constructor": "new Function(s)();",
    "exec-script": "execScript(s);",
    "string-timer": "setTimeout('d = f', 1);",
    "string-timer-member": "window.setInterval('d = f' + x, 1);",
    "top-level-this": "(function (root) { root.d = f; })(this);",
    "function-this": "function init() { var self = this; self.d = f; }",
    "object-method-this": "const o = { m() { return this; } };",
}


@pytest.mark.parametrize("form", sorted(GLOBAL_WILDCARD_FORMS))
def test_global_object_uses_fail_closed_with_a_wildcard(form: str) -> None:
    source = GLOBAL_WILDCARD_FORMS[form]
    assert js_scope.GLOBAL_WILDCARD in script_globals(source), source
    # The same file's own top level is then reassigned for every name.
    script = "function d() {}\nfunction g() { return d(); }\n" + source
    assert reason(script, "d", language="javascript") == "reassigned", source


def test_inert_global_object_uses_are_not_wildcards() -> None:
    for source in (
        "if (typeof window !== 'undefined') {}",
        "if ('fetch' in window) {}",
        "if (self === window) {}",
        "window.addEventListener('load', f);",
        "const t = window.setTimeout(f, 1);",
        "setTimeout(f, 1);",
        "function f(window) { return window; }",
        "export class K { m() { return this; } x = this; static { this.y = 1; } }",
        "function f() { return () => 1; }",
    ):
        assert js_scope.GLOBAL_WILDCARD not in script_globals(source), source
    module_this = "export function f() { var self = this; return self; }"
    assert js_scope.GLOBAL_WILDCARD not in script_globals(module_this)


GLOBAL_WRITE_FORMS = {
    "window": "window.d = other;",
    "globalThis-string": "globalThis['d'] = other;",
    "self-update": "self.d++;",
    "global-compound": "global.d ??= other;",
    "chain": "window.self.d = other;",
    "parenthesized": "(window).d = other;",
    # A script's top-level ``var``/``declare var`` of an alias is the global
    # object's own property.
    "script-var-alias": "var self;\nself.d = other;",
    "pattern": "({ a: window.d } = o);",
    "for-of": "for (window.d of xs) {}",
    "delete": "delete window.d;",
    "nested-function": "function h() { window.d = other; }",
    "top-level-this": "this.d = other;",
    "sloppy-function-this": "function h() { this.d = other; }",
    "object-method-this": "const o = { m() { this.d = other; } };",
    "arrow-in-function-this": "function h() { return () => { this.d = other; }; }",
}


@pytest.mark.parametrize("form", sorted(GLOBAL_WRITE_FORMS))
def test_global_writes_reassign_a_script_top_level(form: str) -> None:
    source = (
        "function d() {}\nfunction other() {}\nfunction g() { return d(); }\n"
        + GLOBAL_WRITE_FORMS[form]
    )
    assert reason(source, "d", language="javascript") == "reassigned", source
    assert "d" in script_globals(source)


def test_global_writes_leave_other_bindings_alone() -> None:
    # In a module, the top level is not the global object.
    module = (
        "export function d() {}\nwindow.d = 1;\nexport function g() { return d(); }"
    )
    assert _js_proof(module) == (["function d() {}"], [])
    # Class code is strict: ``this`` is never the global object there.
    strict = (
        "function d() {}\nclass K { m() { this.d = 1; function f() { this.d = 2; } } }\n"
        "function g() { return d(); }"
    )
    assert outcome(strict, "d", language="javascript")["outcome"] == "local"
    # A function-local binding is not the global.
    local = "function g() { function d() {} window.d = 1; return d(); }"
    assert _js_proof(local) == (["function d() {}"], [])
    # A locally bound ``window`` is not the global object.
    shadowed = "function d() {}\nfunction g(window) { window.d = 1; return d(); }"
    assert outcome(shadowed, "d", language="javascript")["outcome"] == "local"


def test_arguments_alias_reassigns_shared_parameter_names() -> None:
    """Sloppy ``arguments[0] = x`` writes a parameter binding, which a body
    function of the same name shares: fail closed when ``arguments`` occurs."""
    base = "export function g(d) { function d() {} %s return d(); }"
    for extra in ("arguments[0] = 1;", "h(arguments);", "(() => arguments)();"):
        assert reason(base % extra, "d", language="javascript") == "reassigned", extra
    assert outcome(base % "", "d", language="javascript")["outcome"] == "local"
    other = "export function g(x) { function d() {} arguments[0] = 1; return d(); }"
    assert outcome(other, "d", language="javascript")["outcome"] == "local"


# ---------------------------------------------------------------------------
# TS namespace merging and inherited ambient status (7.2; PR 3)

MERGED_NAMESPACES = {
    "two-declarations": (
        "namespace N { export function t() { return 1; } }\n"
        "namespace N { export function g() { return t(); } }"
    ),
    "declare-and-body": (
        "declare namespace N { function t(): void; }\n"
        "namespace N { export function g() { return t(); } }"
    ),
    "exported-and-plain": (
        "export namespace N { }\nnamespace N { export function g() { return t(); } }"
    ),
    "enum-merge": "enum N { A }\nnamespace N { export function g() { return t(); } }",
    "dotted": "namespace A.N { export function g() { return t(); } }",
    "dotted-sibling": (
        "namespace A { export namespace N { export function g() { return t(); } } }\n"
        "namespace A.B { }"
    ),
    "declare-module": "declare module 'm' { export function g(): void; function t(): void; }",
    "declare-global": "declare global { function t(): void; }",
    "nested-merged-parent": (
        "namespace O { export namespace N { export function g() { return t(); } } }\n"
        "namespace O { export function t() { return 2; } }"
    ),
}


@pytest.mark.parametrize("case", sorted(MERGED_NAMESPACES))
def test_lookups_through_a_merged_namespace(case: str) -> None:
    source = MODULE + "export function t() { return 1; }\n" + MERGED_NAMESPACES[case]
    data = source.encode()
    root = get_parser("typescript").parse(data).root_node
    assert not root.has_error
    calls = _callees(root, data, "t")
    if not calls:
        # Bodies with only declarations have no call; the scope is merged.
        assert case in ("declare-module", "declare-global")
        return
    for index in range(len(calls)):
        assert reason(source, "t", occurrence=index) == "namespace-merged", case


def test_namespaces_in_a_script_are_merged() -> None:
    source = "function t() {}\nnamespace N { export function g() { return t(); } }"
    assert reason(source, "t") == "namespace-merged"
    unbound = "namespace N { export function g() { return nowhere(); } }"
    assert reason(unbound, "nowhere") == "namespace-merged"


def test_namespace_merged_follows_r1() -> None:
    """The binding's own reason wins; ``namespace-merged`` only replaces a
    proof (and an unbound name, which another declaration may bind)."""
    pair = "namespace N { }\n"
    param = MODULE + pair + "namespace N { export function g(t) { return t(); } }"
    assert reason(param, "t") == "parameter"
    reassigned = (
        MODULE
        + "function t() {}\n"
        + pair
        + "namespace N { export function g() { t = 1; return t(); } }"
    )
    assert reason(reassigned, "t") == "reassigned"


def test_a_namespace_function_beside_the_namespace_is_not_a_merge() -> None:
    source = (
        MODULE + "function N() {}\nfunction t() {}\n"
        "namespace N { export function g() { return t(); } }"
    )
    assert proof_text(source, "t") == ["function t() {}"]


def test_exported_namespace_variables_are_expression_bound() -> None:
    """tsc rewrites uses of an exported namespace variable to a property of
    the namespace object, which other code can reassign."""
    source = (
        MODULE
        + "namespace N { export const t = () => 1; export function g() { return t(); } }"
    )
    assert reason(source, "t") == "expression-bound"
    local = (
        MODULE
        + "namespace N { const t = () => 1; export function g() { return t(); } }"
    )
    assert proof_text(local, "t") == ["() => 1"]


AMBIENT_BLOCKS = {
    # Ambient status is inherited from enclosing ``declare`` blocks; it is
    # the binding's own reason, so it wins over ``namespace-merged`` (R-1).
    "namespace-function": "declare namespace N { function t() {} function g() { return t(); } }",
    "namespace-class": "declare namespace N { class t {} function g() { return new t(); } }",
    "nested-namespace": (
        "declare namespace O { namespace N { function t() {} function g() { return t(); } } }"
    ),
    "module": "declare module 'm' { function t() {} function g() { return t(); } }",
    "global": "declare global { function t() {} function g() { return t(); } }",
}


@pytest.mark.parametrize("case", sorted(AMBIENT_BLOCKS))
def test_ambient_status_is_inherited(case: str) -> None:
    assert reason(MODULE + AMBIENT_BLOCKS[case], "t") == "ambient"


# ---------------------------------------------------------------------------
# PR 3 end to end, on trees the tests write (a committed tree would change
# the off-mode baseline, 11.2)


def _edges(root: Path) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """``(off, on)`` call edges, paired by ``call_site_id``."""
    off = extract_symbol_graph(root)
    on = extract_symbol_graph(root, call_resolution=MODE)
    on_by_site = {
        edge["call_site_id"]: edge
        for edge in on["relationships"]
        if edge["type"] == "calls"
    }
    return [
        (edge, on_by_site[edge["call_site_id"]])
        for edge in off["relationships"]
        if edge["type"] == "calls"
    ]


def _edge(
    pairs: list[tuple[dict[str, Any], dict[str, Any]]], file: str, reference: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    (pair,) = [
        pair
        for pair in pairs
        if pair[0]["file"] == file and pair[0]["reference"] == reference
    ]
    return pair


SCRIPT = "function d() { return 1; }\nfunction g() { return d(); }\n"
OTHER_SCRIPT_GLOBALS = {
    # Each second file makes ``d`` a script global elsewhere in the run.
    "let": "let d = () => 3;\n",
    "const": "const d = () => 3;\n",
    "class": "class d {}\n",
    "var": "var d;\n",
    "implicit": "function init() { d = function () { return 3; }; }\n",
    "nested-implicit": "function init() { return () => { d ||= other; }; }\n",
    "window-module": "export function d() {}\nwindow.d = function () {};\n",
    "globalThis-string": "export {};\nglobalThis['d'] = 1;\n",
    "self": "export {};\nself.d = 1;\n",
    "computed-key": "export {};\nglobalThis[name] = 1;\n",
    "escape": "export {};\nObject.assign(window, { d: 1 });\n",
    "indirect-eval": "export {};\n(0, eval)(s);\n",
    "sloppy-this": "function init() { this.d = 1; }\n",
    "declare-global": "export {};\ndeclare global { function d(): void; }\n",
    "unsupported": "function d() { return 3; }\nfunction (\n",
}


@pytest.mark.parametrize("form", sorted(OTHER_SCRIPT_GLOBALS))
def test_script_global_end_to_end(tmp_path: Path, form: str) -> None:
    """A script top level narrows only when no other file may declare the
    name as a global (7.2): k.js's own ``d`` stays ambiguous next to these."""
    extension = ".ts" if form == "declare-global" else ".js"
    root = _write(
        tmp_path,
        {
            "k.js": SCRIPT,
            "b" + extension: OTHER_SCRIPT_GLOBALS[form],
            # A third definition, so C0 keeps two or more candidates even
            # when the second file declares no symbol ``d``.
            "c.js": "export function d() { return 4; }\n",
        },
    )
    off, on = _edge(_edges(root), "k.js", "d")
    assert off["resolution"] == "ambiguous"
    assert on == off


COMPANIONS = {
    # No script globals: a module (whose ``window.other`` names another
    # global) and a Python file.
    "c.js": "export function d() { return 4; }\nexport let x = 1;\n",
    "m.ts": "export {};\nfunction d() { return 5; }\nwindow.other = 1;\n",
    "p.py": "def d():\n    return 6\n",
}


def _resolved_line(root: Path, rules: list[str]) -> int:
    off, on = _edge(_edges(root), "k.js", "d")
    assert off["resolution"] == "ambiguous"
    assert on["resolution"] == "resolved"
    assert on["provenance"]["call_rules"] == rules
    assert on["to"] in off["candidates"]
    graph = extract_symbol_graph(root, call_resolution=MODE)
    target = graph["symbol_lookup"][on["to"]]
    assert target["file"] == "k.js"
    return int(target["line"])


def test_script_global_controls_end_to_end(tmp_path: Path) -> None:
    """Module files and Python files declare no script globals, so a script
    top level resolves next to them."""
    root = _write(tmp_path, {"k.js": SCRIPT, **COMPANIONS})
    assert _resolved_line(root, ["t1.lexical"]) == 1


def test_namespace_merging_end_to_end(tmp_path: Path) -> None:
    root = _write(
        tmp_path,
        {
            "a.ts": (
                "export function t() { return 1; }\n"
                "export namespace N { export function g() { return t(); } }\n"
                "namespace N { }\n"
            ),
            "b.ts": (
                "export function t() { return 2; }\n"
                "export namespace M { export function g() { return t(); } }\n"
            ),
            "c.ts": "export function t() { return 3; }\n",
        },
    )
    pairs = _edges(root)
    off, on = _edge(pairs, "a.ts", "t")
    assert off["resolution"] == "ambiguous"
    assert on == off
    # A single declaration in a module is not merged: it resolves.
    off, on = _edge(pairs, "b.ts", "t")
    assert on["resolution"] == "resolved"
    assert on["provenance"]["call_rules"] == ["t1.lexical"]


def test_inherited_ambient_end_to_end(tmp_path: Path) -> None:
    root = _write(
        tmp_path,
        {
            "a.ts": (
                "export {};\n"
                "declare namespace N { class t {} function g() { return new t(); } }\n"
            ),
            # Nested only: a top-level ``t`` would be C0 on its own (6.2).
            "b.ts": "export namespace M { export class t {} }\n",
        },
    )
    off, on = _edge(_edges(root), "a.ts", "t")
    assert off["resolution"] == "ambiguous"
    assert on == off


ENUM_CASES = {
    # B-1 (president's #689 ruling): enum members shadow outer names inside
    # the enum body, so every lookup reaching it fails closed.
    "member": "export enum E { t = 1, B = t() }",
    "const": "export const enum E { t = 1, B = t() }",
    "declare": "declare enum E { t = 1, B = t() }",
    "string-member": "enum E { 't' = 1, B = t() }",
    "computed-member": "enum E { ['t'] = 1, B = t() }",
    "merged": "enum E { t = 1 }\nenum E { B = t() }",
    "non-member": "enum E { a = 1, B = t() }",
    "in-function": "export function g() { enum E { t = 1, B = t() } }",
    "nested-arrow": "enum E { t = 1, B = (() => t())() }",
}


@pytest.mark.parametrize("case", sorted(ENUM_CASES))
def test_lookups_inside_an_enum_body_fail_closed(case: str) -> None:
    source = MODULE + "export function t() { return 1; }\n" + ENUM_CASES[case]
    assert reason(source, "t") == "enum-scope"


def test_enum_scope_keeps_inner_bindings_and_outer_lookups() -> None:
    # A binding inside the initializer is found before the enum body.
    inner = (
        MODULE + "function t() {}\nenum E { B = ((t: () => number) => t())(() => 1) }"
    )
    assert reason(inner, "t") == "parameter"
    # Positive control: outside the enum, ``t`` still proves the function.
    outside = MODULE + "export function t() { return 1; }\nenum E { t = 1 }\nt();"
    assert proof_text(outside, "t") == ["function t() { return 1; }"]
    after = (
        MODULE
        + "export function t() { return 1; }\nenum E { t = 1, B = 2 }\n"
        + "export function g() { return t(); }"
    )
    assert proof_text(after, "t") == ["function t() { return 1; }"]


def test_group_rule_order_b7() -> None:
    """Non-callable kinds drop first; then ambient beats bodyless (7.4, R-1)."""
    assert reason(MODULE + "declare enum E { A }\nE();", "E") == "non-callable"
    assert reason(MODULE + "enum E { A }\nE();", "E") == "non-callable"
    merged = MODULE + "declare function g(): void;\ndeclare namespace g { }\ng();"
    assert reason(merged, "g") == "ambient"
    assert reason(MODULE + "declare function g(): void;\ng();", "g") == "ambient"
    assert reason(MODULE + "function g(): void;\ng();", "g") == "bodyless"
    namespace_function = MODULE + "function NS() {}\nnamespace NS { }\nNS();"
    assert proof_text(namespace_function, "NS") == ["function NS() {}"]


# ---------------------------------------------------------------------------
# Fail closed (5.3, 5.4, 7.5)


def test_nested_blocks_raise_recursion_error() -> None:
    """Deep nesting of any construct fails closed, not only arrays (C3)."""
    depth = 400
    data = ("function g() { " + "{ " * depth + "g();" + " }" * depth + " }").encode()
    root = get_parser("javascript").parse(data).root_node
    assert not root.has_error
    with pytest.raises(RecursionError):
        js_scope.analyze(root, data, "javascript", [])


def test_depth_cap_raises_recursion_error() -> None:
    depth = js_scope.MAX_DEPTH + 10
    data = ("const x = " + "[" * depth + "]" * depth + ";").encode()
    root = get_parser("javascript").parse(data).root_node
    with pytest.raises(RecursionError):
        js_scope.analyze(root, data, "javascript", [])


def test_a_callee_span_with_no_node_has_no_entry() -> None:
    data = b"function t() {}\nt();"
    root = get_parser("javascript").parse(data).root_node
    facts = [{"callee_byte_start": 0, "callee_byte_end": 3}]
    assert js_scope.analyze(root, data, "javascript", facts)["bindings"] == {}


def test_a_fail_closed_kind_poisons_only_its_scopes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delitem(allowlist.ALLOWLIST["typescript"], "labeled_statement")
    source = (
        MODULE
        + "function t() {}\nfunction g() { l: for (;;) {} return t(); }\nfunction h() { return t(); }"
    )
    assert reason(source, "t", occurrence=0) == "unmapped"
    assert proof_text(source, "t", occurrence=1) == ["function t() {}"]


HANDLED_BY_PARENT = {
    # Opened as a scope by its enum_declaration.
    "enum_body",
    # Bound by the declaration, parameter list or import that contains them;
    # the pass itself only descends into them.
    "array_pattern",
    "assignment_pattern",
    "object_assignment_pattern",
    "object_pattern",
    "pair_pattern",
    "rest_pattern",
    "shorthand_property_identifier_pattern",
    "formal_parameters",
    "required_parameter",
    "optional_parameter",
    "variable_declarator",
    "import_clause",
    "import_specifier",
    "named_imports",
    "namespace_import",
    "import_require_clause",
    # Opens a scope only through its parent.
    "program",
    # Checked on the lookup chain.
    "with_statement",
}


@pytest.mark.parametrize("language", ["javascript", "typescript", "tsx"])
def test_every_handled_kind_has_a_handler(language: str) -> None:
    handled = {
        kind
        for kind, entry in allowlist.ALLOWLIST[language].items()
        if entry.classification == allowlist.HANDLED
    }
    root = get_parser(language).parse(b"").root_node
    handlers = set(js_scope._Analysis(root, b"", language).handlers)
    assert handled - handlers - HANDLED_BY_PARENT == set()


def test_plan_named_kinds_are_classified() -> None:
    """Plan 7.5 names these forms explicitly."""
    assert allowlist.classify("typescript", "import_alias").classification == (
        allowlist.HANDLED
    )
    for language in ("javascript", "typescript", "tsx"):
        assert allowlist.classify(language, "for_in_statement").classification == (
            allowlist.HANDLED
        )
        assert allowlist.classify(language, "labeled_statement").classification == (
            allowlist.IGNORED
        )
    assert allowlist.classify("javascript", "using_declaration").classification == (
        allowlist.HANDLED
    )
    for language in ("typescript", "tsx"):
        assert "using_declaration" not in allowlist.named_node_kinds(language)


# ---------------------------------------------------------------------------
# #688 notes and fixture-wide proof checks


def test_fixture_proofs_name_symbol_declarations() -> None:
    """N-1: every proof declaration joins to exactly one symbol of its file.

    Exported definitions yield an ``export_statement`` chunk and the inner
    declaration's chunk; proofs name the inner one, so no fixture proof is
    ``unmapped`` and none names an ``export_statement``.
    """
    proofs = 0
    for _, item in harness.fixture_scope_facts():
        scope_facts = item["scope_facts"]
        symbols = [tuple(entry[:3]) for entry in scope_facts["symbols"]]
        for result in scope_facts["bindings"].values():
            if result["outcome"] != "local":
                continue
            for declaration in result["proof"]:
                proofs += 1
                assert declaration[0] != "export_statement", item["path"]
                assert symbols.count(tuple(declaration)) == 1, (
                    item["path"],
                    declaration,
                )
    assert proofs >= 30


def _write(root: Path, files: dict[str, str]) -> Path:
    for name, text in files.items():
        (root / name).write_text(text, encoding="utf-8")
    return root


def _calls(graph: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        f"{edge['file']}:{edge['reference']}": edge
        for edge in graph["relationships"]
        if edge["type"] == "calls"
    }


def test_b7_declare_enum_is_non_callable_end_to_end(tmp_path: Path) -> None:
    """B7: ``declare enum E {}`` then ``E()`` stays unchanged (plan 7.4).

    The tree is written here: a committed tree would change the off-mode
    baseline, which is never regenerated for a product change (11.2).
    """
    root = _write(
        tmp_path,
        {
            "a.ts": "declare enum E { A }\nexport function f() { return E(); }\n",
            "b.ts": "export function E() { return 1; }\n",
            "c.ts": (
                "declare function g(): void;\ndeclare namespace g { const x: number; }\n"
                "export function h() { return g(); }\n"
            ),
            "d.ts": "export function g() { return 2; }\n",
        },
    )
    off = _calls(extract_symbol_graph(root))
    on = _calls(extract_symbol_graph(root, call_resolution=MODE))
    assert off["a.ts:E"]["resolution"] == "ambiguous"
    assert len(off["a.ts:E"]["candidates"]) == 2
    # non-callable proves nothing and the one callable survivor is unproven.
    assert on["a.ts:E"] == off["a.ts:E"]
    # The ambient group proves nothing; only the kind filter narrows (to 2).
    assert len(off["c.ts:g"]["candidates"]) == 3
    assert on["c.ts:g"]["resolution"] == "ambiguous"
    assert on["c.ts:g"]["provenance"]["call_rules"] == ["t1.kind"]
    assert len(on["c.ts:g"]["candidates"]) == 2


def test_b7_outcomes_in_the_scope_facts(tmp_path: Path) -> None:
    from chunker.symbol_graph import extract_symbol_facts_for_file

    root = _write(
        tmp_path,
        {
            "a.ts": "declare enum E { A }\nexport function f() { return E(); }\n",
            "c.ts": (
                "declare function g(): void;\ndeclare namespace g { const x: number; }\n"
                "export function h() { return g(); }\n"
            ),
        },
    )
    reasons = {}
    for name in ("a.ts", "c.ts"):
        facts = extract_symbol_facts_for_file(
            root / name, root, None, call_resolution=MODE
        )
        (result,) = facts["scope_facts"]["bindings"].values()
        reasons[name] = result
    assert reasons == {
        "a.ts": {"outcome": "none", "reason": "non-callable"},
        "c.ts": {"outcome": "none", "reason": "ambient"},
    }


def test_using_near_miss_end_to_end(tmp_path: Path) -> None:
    """#689 panel B3: TS ``using``/``await using`` fail closed; on equals off.

    Written by the test, like the B7 trees: a committed tree would change the
    off-mode baseline (plan 10.6, 11.2).
    """
    root = _write(
        tmp_path,
        {
            "a.ts": (
                "function u() { return 1; }\n"
                "export function g() { using u = f(); return u(); }\n"
                "export async function h() { await using u = f(); return u(); }\n"
            ),
            "b.ts": "export function u() { return 2; }\n",
        },
    )
    off = extract_symbol_graph(root)
    on = extract_symbol_graph(root, call_resolution=MODE)
    calls = [
        edge
        for edge in off["relationships"]
        if edge["type"] == "calls" and edge["reference"] == "u"
    ]
    assert len(calls) == 2
    assert all(edge["resolution"] == "ambiguous" for edge in calls)
    assert on["relationships"] == off["relationships"]


def test_member_call_on_a_local_function_is_unchanged(tmp_path: Path) -> None:
    """#689 panel A5: ``m.m()`` is never eligible, even when ``m`` is proven."""
    root = _write(
        tmp_path,
        {
            "a.ts": "function m() { return 1; }\nexport function g() { return m.m(); }\n",
            "b.ts": "export function m() { return 2; }\n",
        },
    )
    off = _calls(extract_symbol_graph(root))
    on = _calls(extract_symbol_graph(root, call_resolution=MODE))
    assert off["a.ts:m.m"]["resolution"] == "ambiguous"
    assert on["a.ts:m.m"] == off["a.ts:m.m"]


def test_wrapped_reassignment_end_to_end(tmp_path: Path) -> None:
    """#689 panel A1: ``(t as any) = other`` keeps the edge as off."""
    root = _write(
        tmp_path,
        {
            "a.ts": (
                "export function t() { return 1; }\nfunction other() { return 3; }\n"
                "export function g() { (t as any) = other; return t(); }\n"
                "export function h(o: any) { o.t = 1; return t(); }\n"
            ),
            "b.ts": "export function t() { return 2; }\n",
        },
    )
    off = extract_symbol_graph(root)
    on = extract_symbol_graph(root, call_resolution=MODE)
    edges = {
        (edge["file"], edge["line"]): (off_edge, edge)
        for off_edge, edge in zip(off["relationships"], on["relationships"])
        if edge["type"] == "calls" and edge["reference"] == "t"
    }
    off_g, on_g = edges[("a.ts", 3)]
    assert off_g["resolution"] == "ambiguous"
    assert on_g == off_g
    # A file-wide fail-closed write: h's call reaches the same binding.
    off_h, on_h = edges[("a.ts", 4)]
    assert on_h == off_h


def test_enum_scope_end_to_end(tmp_path: Path) -> None:
    """B-1: calls in enum initializers keep their off-mode edge.

    Written by the test, like the B7 and ``using`` trees: a committed tree
    would change the off-mode baseline (plan 10.6, 11.2).
    """
    root = _write(
        tmp_path,
        {
            "a.ts": (
                "export function t() { return 1; }\n"
                "export enum E { t = 1, B = t() }\n"
                "export const enum C { 't' = 1, B = t() }\n"
                "enum M { t = 1 }\nenum M { B = t() }\n"
                "export function g() { enum L { a = 1, B = t() } return t(); }\n"
            ),
            "b.ts": "export function t() { return 2; }\n",
        },
    )
    off = extract_symbol_graph(root)
    on = extract_symbol_graph(root, call_resolution=MODE)
    on_by_site = {
        edge["call_site_id"]: edge
        for edge in on["relationships"]
        if edge["type"] == "calls"
    }
    # Pair by call_site_id, which is identical on and off.
    pairs = [
        (off_edge, on_by_site[off_edge["call_site_id"]])
        for off_edge in off["relationships"]
        if off_edge["type"] == "calls" and off_edge["reference"] == "t"
    ]
    assert sorted({on_edge["line"] for _, on_edge in pairs}) == [2, 3, 5, 6]
    for off_edge, on_edge in pairs:
        if on_edge["line"] in (2, 3, 5):
            assert off_edge["resolution"] == "ambiguous", on_edge["line"]
            assert on_edge == off_edge, on_edge["line"]
    # Line 6 has two calls: the enum initializer stays as off, and the
    # ``return t()`` outside the enum resolves to a.ts's own ``t``.
    line6 = [(a, b) for a, b in pairs if b["line"] == 6]
    assert len(line6) == 2
    (inside_off, inside_on), (outside_off, outside_on) = sorted(
        line6, key=lambda pair: pair[1]["callee_byte_start"]
    )
    assert inside_on == inside_off
    assert outside_off["resolution"] == "ambiguous"
    assert outside_on["resolution"] == "resolved"
    assert outside_on["provenance"]["call_rules"] == ["t1.lexical"]
    assert on["symbol_lookup"][outside_on["to"]]["file"] == "a.ts"


# ---------------------------------------------------------------------------
# Escaped names fail closed (Codex review of #689, comment 4649197239)

# ``\\u0074`` in these sources is the six characters of a Unicode escape for
# ``t``. Each form, in a.ts, sits beside a call ``t()`` that a.ts's own
# ``function t`` could otherwise prove.
ESCAPED_FORMS = {
    # The three Codex shapes: each resolved wrongly before.
    "parameter": "export function g(\\u0074: () => number) { return t(); }",
    "write": (
        "function other() { return 3; }\n"
        "export function g() { \\u0074 = other; return t(); }"
    ),
    "eval": "export function g(s: string) { \\u0065val(s); return t(); }",
    # More escape forms.
    "destructuring": "export function g(o: any) { const { \\u0074 } = o; return t(); }",
    "brace-form": "export function g(\\u{74}: () => number) { return t(); }",
    "declaration": "function \\u0074x() { return 4; }\nexport function g() { return t(); }",
    "property": "export function g(o: any) { o.\\u0074(); return t(); }",
}
BUG_FORMS = ("parameter", "write", "eval", "destructuring", "brace-form")


@pytest.mark.parametrize("form", sorted(ESCAPED_FORMS))
def test_escaped_names_make_the_analyzer_refuse(form: str) -> None:
    data = ("export function t() { return 1; }\n" + ESCAPED_FORMS[form]).encode()
    root = get_parser("typescript").parse(data).root_node
    assert not root.has_error
    assert js_scope.escaped_name(root, data) is not None
    with pytest.raises(js_scope.EscapedIdentifierError):
        js_scope.analyze(root, data, "typescript", [])


def test_backslashes_in_text_are_not_escaped_names() -> None:
    """Strings, templates, regexes, comments and JSX text keep the file."""
    source = (
        'export function t() { return "a\\nb" + `c\\t${1}` + /\\d+/.source; }\n'
        "// a \\u0074 comment\n/* \\u0074 */\n"
        "export const e = <div title='x\\ny'>a \\u0074 b</div>;\n"
        "export function g() { return t(); }\n"
    )
    data = source.encode()
    root = get_parser("tsx").parse(data).root_node
    assert not root.has_error
    assert js_scope.escaped_name(root, data) is None
    assert proof_text(source, "t", language="tsx") == [
        'function t() { return "a\\nb" + `c\\t${1}` + /\\d+/.source; }'
    ]


@pytest.mark.parametrize("form", sorted(ESCAPED_FORMS))
def test_escaped_names_end_to_end(tmp_path: Path, form: str) -> None:
    """The file is unsupported and keeps its off-mode edges; c.ts resolves."""
    from chunker.symbol_graph import extract_symbol_facts_for_file

    root = _write(
        tmp_path,
        {
            "a.ts": "export function t() { return 1; }\n" + ESCAPED_FORMS[form] + "\n",
            "b.ts": "export function t() { return 2; }\n",
            "c.ts": (
                "export function t() { return 3; }\n"
                "export function h() { return t(); }\n"
            ),
        },
    )
    facts = extract_symbol_facts_for_file(
        root / "a.ts", root, None, call_resolution=MODE
    )
    assert facts["scope_facts"]["supported"] is False
    assert facts["errors"] == []
    off = extract_symbol_graph(root)
    on = extract_symbol_graph(root, call_resolution=MODE)
    on_by_site = {
        edge["call_site_id"]: edge
        for edge in on["relationships"]
        if edge["type"] == "calls"
    }
    a_calls = [
        edge
        for edge in off["relationships"]
        if edge["type"] == "calls" and edge["file"] == "a.ts"
    ]
    assert any(
        edge["reference"] == "t" and edge["resolution"] == "ambiguous"
        for edge in a_calls
    )
    for edge in a_calls:
        assert on_by_site[edge["call_site_id"]] == edge
    # Control: the escape-free file in the same run still resolves.
    (control,) = (
        edge
        for edge in on["relationships"]
        if edge["type"] == "calls" and edge["file"] == "c.ts"
    )
    assert control["resolution"] == "resolved"
    assert control["provenance"]["call_rules"] == ["t1.lexical"]
    assert on["symbol_lookup"][control["to"]]["file"] == "c.ts"

"""Tier 1 JavaScript/TypeScript scope analysis (treesitter-chunker#682, PR 2).

Plan ``plans/detailed-scoped-call-resolution-682.md`` sections 7.2, 7.4, 7.5
and 7.6. The expected tables (``test_call_resolution_engine.py``) pin every
fixture call end to end; this module adds:

- analyzer unit cases on short sources, one per rule of 7.2 that the
  fixtures do not isolate;
- the #688 notes for this head: N-1 (proofs name the symbol-carrying
  declaration, never the ``export_statement``), note 1 (a namespace merged
  with a function is dropped before the proof), and B7 (``declare enum``
  gives ``non-callable``);
- the allow-list contract: every handled kind has a handler.
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


@pytest.mark.parametrize(
    "write",
    ["t = other;", "t += 1;", "t++;", "[t] = [other];", "({ t } = { t: other });"],
)
def test_reassignment_forms(write: str) -> None:
    source = (
        MODULE
        + f"function t() {{}}\nfunction other() {{}}\nfunction g() {{ {write} return t(); }}"
    )
    assert reason(source, "t") == "reassigned"


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


def test_eval_and_with_fail_closed() -> None:
    top_eval = MODULE + "function t() {}\neval('x');\nfunction g() { return t(); }"
    assert reason(top_eval, "t") == "dynamic-scope"
    inner_eval = (
        MODULE
        + "function t() {}\nfunction g() { function t() {} eval('x'); }\nfunction h() { return t(); }"
    )
    assert proof_text(inner_eval, "t") == ["function t() {}"]
    with_body = "function t() {}\nfunction w(o) { with (o) { t(); } }"
    assert reason(with_body, "t", language="javascript") == "dynamic-scope"


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


def test_script_goal_and_namespace_deferrals_follow_r1() -> None:
    script = "function t() {}\nfunction g() { return t(); }"
    assert reason(script, "t", language="javascript") == "script-goal-deferred"
    # R-1(i): an outcome that proves nothing reports its own reason.
    script_param = "function g(t) { return t(); }"
    assert reason(script_param, "t", language="javascript") == "parameter"
    namespace = (
        MODULE + "function t() {}\nnamespace N { export function g() { return t(); } }"
    )
    assert reason(namespace, "t") == "namespace-deferred"
    inside = (
        MODULE + "namespace N { function t() {} export function g() { return t(); } }"
    )
    assert reason(inside, "t") == "namespace-deferred"
    inside_param = MODULE + "namespace N { export function g(t) { return t(); } }"
    assert reason(inside_param, "t") == "parameter"


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

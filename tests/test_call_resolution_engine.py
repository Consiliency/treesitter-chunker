"""The call-resolution engine, expected tables and fact pins (#682).

Covers plan ``plans/detailed-scoped-call-resolution-682.md``:

- section 6.3, the binding-proof algorithm, and 7.1, ``t1.kind`` and
  ``t1.family``, as engine unit tests;
- section 5.4, the fail-closed join (``unmapped``, ``no-binding-fact``);
- section 10.1, the per-mode fields of ``expected/<tree>.json`` that this
  head asserts, and section 10.6, traceability for the rules and reasons live
  at this head;
- section 4.6, the pinned per-family scope-fact digests.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from chunker.call_resolution import engine
from chunker.call_resolution.facts import (
    CALL_RESOLUTION_FACT_VERSIONS,
    KNOWN_NONE_REASONS,
    valid_scope_facts,
)
from chunker.symbol_graph import (
    assemble_symbol_graph,
    collect_source_files,
    extract_symbol_facts_for_file,
    module_layout,
)
from tests import call_resolution_harness as harness

capture = harness.load_capture()
RUNS = capture.discover_runs()
TREES = sorted({run.tree for run in RUNS})
EXPECTED = capture.FIXTURES / "expected"
MODE = "structural"

# The plan PR this head implements (section 13.1). Expected-table rows of a
# later PR that record an expectation for this head carry ``interim``.
HEAD_PR = 6
# Rules and reasons this head produces, each with a case in the expected
# tables (10.6). Each later PR adds its own. ``stub`` left the vocabulary
# when the Python analyzer landed (PR 4); ``unmapped`` and ``no-binding-fact``
# are covered by the named tests below.
LIVE_RULES = {"t1.kind", "t1.family", "t1.lexical", "t1.ts_overload", "t1.js_hoist"}
# PR 5: Tier 2 for TS/JS, and PR 6: Tier 2 for Python, asserted in
# ``imports`` mode.
IMPORTS_MODE = "imports"
LIVE_IMPORTS_RULES = {"t2.import", "t2.namespace"}
LIVE_IMPORTS_REASONS = {
    "external-module",
    "module-not-found",
    "unknown-variant",
    "ambiguous-extension",
    "dts-target",
    "export-not-found",
    "star-conflict",
    "namespace-export",
    "commonjs",
    "hop-limit",
    "cycle",
    "local-variable",
    # PR 6 (Python, 9.5-9.8).
    "conditional",
    "outside-root",
    "script-dir-shadow",
    "attr-submodule-conflict",
}
LIVE_REASONS = {
    "unbound",
    "parameter",
    "local-variable",
    "expression-bound",
    "self-binding",
    "reassigned",
    "block-function",
    "mixed-bindings",
    "dynamic-scope",
    "ambient",
    "bodyless",
    "non-callable",
    "type-only",
    "script-global",
    "namespace-merged",
    # PR 4: Python.
    "conditional",
    "class-scope-bound",
    "star-import",
}
# Named generated-coverage tests (plan 10.6, R-3) that exist at this head.
NAMED_FAILURE_MODE_TESTS = (
    "test_no_binding_fact_dropped_entry_js",
    "test_no_binding_fact_dropped_entry_py",
    "test_unsupported_syntax_error",
    "test_unsupported_recursion_error",
    "test_unsupported_analyzer_exception",
    "test_unmapped_injected_missing_declaration",
    "test_unmapped_missing_symbol",
    "test_unmapped_unclassified_node",
    "test_unsupported_deep_nesting_js",
    # PR 4: the Python analyzer's named tests (plan 10.6).
    "test_unmapped_duplicate_key",
    "test_unsupported_deep_nesting",
)
# Named end-to-end near-misses on trees the test writes, because a committed
# tree would change the off-mode baseline (plan 10.6, 11.2): B7 and ``using``.
NAMED_TIER1_JS_TESTS = (
    "test_b7_declare_enum_is_non_callable_end_to_end",
    "test_b7_outcomes_in_the_scope_facts",
    "test_using_near_miss_end_to_end",
    "test_wrapped_reassignment_end_to_end",
    "test_member_call_on_a_local_function_is_unchanged",
    "test_enum_scope_end_to_end",
    "test_escaped_names_end_to_end",
    # PR 3: hoisting, script globals, namespace merging, inherited ambient.
    "test_script_global_end_to_end",
    "test_script_global_controls_end_to_end",
    "test_js_hoist_end_to_end",
    "test_js_hoist_near_misses_end_to_end",
    "test_namespace_merging_end_to_end",
    "test_inherited_ambient_end_to_end",
    # #691 panel fold.
    "test_panel_691_cases_keep_their_off_mode_edge",
    "test_misparsed_blocks_make_the_file_unsupported",
)
# Live reasons no committed fixture produces, each covered by a named test on
# a tree the test writes (the president's #689 ruling, B-1).
TEST_WRITTEN_REASONS = {
    "enum-scope": "test_enum_scope_end_to_end",
    # PR 4 (#695 panel A3): no committed fixture shadows a builtin.
    "builtin-shadow": "test_builtin_shadow_end_to_end",
}
# Named tests the plan assigns to later heads (panel C2). Each moved to the
# live list when its analyzer landed; none is left.
DEFERRED_FAILURE_MODE_TESTS: dict[str, str] = {}
# Named Python end-to-end tests on trees the test writes, because a committed
# tree would change the off-mode baseline (plan 10.6, 11.2).
NAMED_TIER1_PY_TESTS = (
    "test_decorated_definitions_keep_their_off_mode_edge",
    "test_non_ascii_identifiers_make_the_file_unsupported",
    "test_dynamic_binding_forms_keep_their_off_mode_edge",
    "test_write_forms_keep_their_off_mode_edge",
    "test_python_positives_end_to_end",
    # The #695 panel fold.
    "test_panel_695_cases_keep_their_off_mode_edge",
    "test_natural_unmapped_forms_keep_their_off_mode_edge",
    "test_line_continuation_target_end_to_end",
    "test_builtin_shadow_end_to_end",
    # The president's #695 ruling (B-1 to B-6).
    "test_ruling_695_cases_keep_their_off_mode_edge",
    "test_whitespace_differential_has_no_silent_misparse",
    # The president's re-check (N-1 to N-3): the general self-reference rule.
    "test_recheck_695_cases_keep_their_off_mode_edge",
    # The re-check at f7f0b0bd (N-4 to N-6) and the R-5 family.
    "test_fold4_695_cases_keep_their_off_mode_edge",
    # The re-check at 06f5dc32 (N-7): names from tokens.
    "test_fold5_695_cases_keep_their_off_mode_edge",
    # Codex 4654363963: mangled names from class code.
    "test_codex_4654363963_end_to_end",
    # The re-check at 13c38360 (I-3): mangled sys/__main__ aliases.
    "test_fold7_695_cases_keep_their_off_mode_edge",
    # The re-check at eae66582 (J-3): __main__ via class attributes and
    # from-imports.
    "test_fold8_695_cases_keep_their_off_mode_edge",
    # The re-check at f2b38014 (K-3): "__main__" constant strings.
    "test_fold9_695_cases_keep_their_off_mode_edge",
    # The re-check at 3b2d8fae (L-2): the narrowed __main__ guard.
    "test_fold10_695_cases_keep_their_off_mode_edge",
    # The re-check at 8006c72c (M-2): the positive allow-list.
    "test_fold11_695_cases_keep_their_off_mode_edge",
    # Codex 4655078224: closure cells and code objects.
    "test_codex_4655078224_closure_rebinding_end_to_end",
    # The re-check at 606c689f (O-3): code objects from dis/monitoring and
    # builtins reached as an attribute.
    "test_fold13_695_cases_keep_their_off_mode_edge",
    # The re-check at 8fd7c1a2 (P-2/P-3): the builtins module by name, the
    # profiler's code objects and inspect's frame-locals helpers.
    "test_fold14_695_cases_keep_their_off_mode_edge",
    # The re-check at 14e8f044 (Q-2/Q-3): calls in annotations, and more
    # code-object, live-locals and annotationlib routes.
    "test_fold15_695_cases_keep_their_off_mode_edge",
    # The re-check at a6734480 (S-2/S-3): class-body ``type`` values and
    # ``__annotate_func__``.
    "test_fold16_695_cases_keep_their_off_mode_edge",
    # Codex 4656123247: callees and receivers classified after unwrapping
    # parentheses.
    "test_fold17_695_parenthesized_callees_keep_their_off_mode_edge",
    # Fold 18: writer aliases, namespace mutators, operator writers, |=.
    "test_fold18_695_writer_aliases_keep_their_off_mode_edge",
    # Fold 19 (E-19): computed writes closed at the write site.
    "test_fold19_695_computed_writes_keep_their_off_mode_edge",
    # Fold 20: receiver-based patchers (pytest-mock, any X.patch.object).
    "test_fold20_695_receiver_patchers_keep_their_off_mode_edge",
    # Fold 21 (E-20): namespace aliases as attributes, mock aliases,
    # resolver mentions.
    "test_fold21_695_writes_and_triggers_keep_their_off_mode_edge",
    # Fold 22: one alias/readback/escape mechanism for every sensitive kind.
    "test_fold22_695_president_probes_keep_their_off_mode_edge",
    "test_fold22_695_cross_kind_matrix_fails_closed",
    # Fold 23 (E-21): the closed allow-list of sensitive-value uses.
    "test_fold23_695_president_probes_keep_their_off_mode_edge",
    "test_fold23_695_allow_list_is_closed",
    "test_fold24_695_president_probes_keep_their_off_mode_edge",
    "test_fold24_695_import_bindings_are_aliases",
    "test_fold24_695_namespace_iteration_fails_closed",
    "test_fold25_695_shadowed_allowlist_callees_keep_their_off_mode_edge",
    "test_fold25_695_verified_callees_still_resolve",
    "test_fold26_695_rebound_operator_members_keep_their_off_mode_edge",
    "test_fold26_695_unrelated_writes_keep_the_entry",
    "test_fold27_695_namespace_views_keep_their_off_mode_edge",
    "test_fold27_695_unreachable_results_still_resolve",
    "test_fold28_695_open_class_callees_keep_their_off_mode_edge",
    "test_fold28_695_class_nested_scopes_still_resolve",
    "test_fold28_695_plain_scopes_still_resolve",
)
# Expected rows per plan PR (10.1): a row that loses its finalization fails
# the pin (#695 panel B7).
EXPECTED_ROWS_PER_PR = {1: 55, 2: 55, 3: 6, 4: 43}
# Rows with an ``imports`` field, per plan PR (PR 5: Tier 2 for TS/JS; PR 6:
# Tier 2 for Python).
EXPECTED_IMPORTS_ROWS_PER_PR = {5: 31, 6: 18}
# Grammars per analyzer family, for the allow-list review rule.
FAMILY_GRAMMARS = {"js": ("javascript", "typescript", "tsx"), "python": ("python",)}


# ---------------------------------------------------------------------------
# Engine unit tests (6.3, 7.1)


def _symbol(
    language: str, kind: str = "function", file: str = "x.ts"
) -> dict[str, Any]:
    return {"language": language, "kind": kind, "file": file}


SYMBOLS = {
    "ts_fn_a": _symbol("typescript"),
    "ts_fn_b": _symbol("typescript"),
    "tsx_fn": _symbol("tsx"),
    "js_fn": _symbol("javascript"),
    "ts_iface": _symbol("typescript", "interface"),
    "ts_type": _symbol("typescript", "type"),
    "ts_enum": _symbol("typescript", "enum"),
    "ts_ns": _symbol("typescript", "module"),
    "py_fn": _symbol("python"),
    "py_class": _symbol("python", "class"),
    "go_fn": _symbol("go"),
    "rs_struct": _symbol("rust", "struct"),
    "other_file_fn": _symbol("typescript", file="other.ts"),
}


def _narrow(
    candidates: list[str],
    proven: set[str] | None = None,
    family: str = "js",
    binding_rules: tuple[str, ...] = ("t1.lexical",),
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    return engine.narrow(
        sorted(candidates),
        frozenset(proven or ()),
        binding_rules,
        family,
        SYMBOLS,
    )


def test_kind_filter_narrows_to_two_or_more() -> None:
    after, rules = _narrow(["ts_fn_a", "ts_fn_b", "ts_type", "ts_enum"])
    assert after == ("ts_fn_a", "ts_fn_b")
    assert rules == ("t1.kind",)


def test_family_filter_narrows_to_two_or_more() -> None:
    after, rules = _narrow(["ts_fn_a", "js_fn", "py_fn", "go_fn"])
    assert after == ("js_fn", "ts_fn_a")
    assert rules == ("t1.family",)


def test_filters_apply_together_in_family_then_kind_order() -> None:
    after, rules = _narrow(["ts_fn_a", "tsx_fn", "ts_iface", "py_fn"])
    assert after == ("ts_fn_a", "tsx_fn")
    assert rules == ("t1.family", "t1.kind")


@pytest.mark.parametrize(
    "candidates",
    [
        ["ts_fn_a", "ts_iface"],  # ts-param-kind: survivor unproven
        ["ts_fn_a", "ts_enum"],  # ts-enum-shadow
        ["py_fn", "js_fn"],  # py-builtin-family, from a Python caller
    ],
)
def test_a_filter_alone_never_resolves(candidates: list[str]) -> None:
    family = "python" if "py_fn" in candidates else "js"
    assert _narrow(candidates, family=family) == (tuple(sorted(candidates)), ())


def test_a_step_that_would_empty_the_set_is_skipped() -> None:
    assert _narrow(["py_fn", "go_fn"], family="js") == (("go_fn", "py_fn"), ())
    assert _narrow(["ts_iface", "ts_type"]) == (("ts_iface", "ts_type"), ())


def test_binding_intersects_and_resolves_when_one_remains() -> None:
    after, rules = _narrow(
        ["ts_fn_a", "ts_fn_b"],
        proven={"ts_fn_a"},
        binding_rules=("t1.lexical", "t1.ts_overload"),
    )
    assert after == ("ts_fn_a",)
    assert rules == ("t1.lexical", "t1.ts_overload")


def test_binding_group_of_two_stays_ambiguous() -> None:
    after, rules = _narrow(
        ["ts_fn_a", "ts_fn_b", "js_fn"], proven={"ts_fn_a", "ts_fn_b"}
    )
    assert after == ("ts_fn_a", "ts_fn_b")
    assert rules == ("t1.lexical",)


def test_a_proof_outside_c0_never_resolves_but_filters_may_narrow() -> None:
    # R-2: the binding step has no effect; the filters still narrow to two.
    after, rules = _narrow(
        ["ts_fn_a", "ts_fn_b", "ts_type"], proven={"nested_not_in_c0"}
    )
    assert after == ("ts_fn_a", "ts_fn_b")
    assert rules == ("t1.kind",)


def test_proof_equal_to_c0_changes_nothing() -> None:
    assert _narrow(
        ["py_fn", "py_class"], proven={"py_fn", "py_class"}, family="python"
    ) == (
        ("py_class", "py_fn"),
        (),
    )


def _file(
    bindings: dict[str, Any],
    symbols: list[list[Any]] | None = None,
    language: str = "typescript",
    supported: bool = True,
) -> engine.FileContext:
    context = engine.build_run_context(
        [
            {
                "path": "x.ts",
                "scope_facts": {
                    "language": language,
                    "supported": supported,
                    "bindings": bindings,
                    "symbols": symbols or [],
                },
            }
        ],
        SYMBOLS,
        MODE,
    )
    return context.files["x.ts"]


def test_join_maps_a_declaration_to_its_symbol() -> None:
    file_context = _file({}, [["function_declaration", 0, 9, "ts_fn_a"]])
    outcome = {
        "outcome": "local",
        "proof": [["function_declaration", 0, 9]],
        "rules": [],
    }
    proven, joined, rules = engine.proof(outcome, MODE, file_context, SYMBOLS)
    assert proven == {"ts_fn_a"}
    assert joined == outcome
    assert rules == ("t1.lexical",)


@pytest.mark.parametrize(
    "symbols",
    [
        [],  # no symbol at that key
        [
            ["function_declaration", 0, 9, "ts_fn_a"],
            ["function_declaration", 0, 9, "ts_fn_b"],
        ],  # a duplicate key
        [["function_declaration", 0, 9, "dropped_symbol"]],  # no symbol record
    ],
)
def test_join_fails_closed_as_unmapped(symbols: list[list[Any]]) -> None:
    outcome = {
        "outcome": "local",
        "proof": [["function_declaration", 0, 9]],
        "rules": [],
    }
    proven, joined, rules = engine.proof(outcome, MODE, _file({}, symbols), SYMBOLS)
    assert proven == frozenset()
    assert joined == {"outcome": "none", "reason": "unmapped"}
    assert rules == ()


def test_join_fails_closed_for_a_symbol_of_another_file() -> None:
    outcome = {
        "outcome": "local",
        "proof": [["function_declaration", 0, 9]],
        "rules": [],
    }
    symbols = [["function_declaration", 0, 9, "other_file_fn"]]
    proven, joined, _ = engine.proof(outcome, MODE, _file({}, symbols), SYMBOLS)
    assert proven == frozenset()
    assert joined == {"outcome": "none", "reason": "unmapped"}


@pytest.mark.parametrize(
    ("proof_symbols", "language"),
    [
        (["ts_enum"], "typescript"),  # probe (a): ts-enum-shadow, P = {enum E}
        (["ts_fn_a", "ts_iface"], "typescript"),  # probe (b): P holds an interface
        (["py_fn"], "typescript"),  # a cross-family proof
    ],
)
def test_a_non_callable_or_cross_family_proof_fails_closed(
    proof_symbols: list[str], language: str
) -> None:
    """The engine enforces the binding-proof invariant itself (panel B2)."""
    symbols = [
        ["function_declaration", index * 10, index * 10 + 9, symbol_id]
        for index, symbol_id in enumerate(proof_symbols)
    ]
    file_symbols = {
        symbol_id: {**SYMBOLS[symbol_id], "file": "x.ts"} for symbol_id in SYMBOLS
    }
    outcome = {
        "outcome": "local",
        "proof": [entry[:3] for entry in symbols],
        "rules": [],
    }
    proven, joined, rules = engine.proof(
        outcome, MODE, _file({}, symbols, language=language), file_symbols
    )
    assert (proven, joined, rules) == (
        frozenset(),
        {"outcome": "none", "reason": "non-callable"},
        (),
    )


def test_ts_enum_shadow_probe_does_not_resolve_end_to_end() -> None:
    """Probe (a): C0 = {local enum E, other-file function E}, P = {enum E}."""
    context = engine.build_run_context(
        [
            {
                "path": "x.ts",
                "scope_facts": {
                    "language": "typescript",
                    "supported": True,
                    "bindings": {
                        "3:4": {
                            "outcome": "local",
                            "proof": [["enum_declaration", 0, 9]],
                            "rules": [],
                        }
                    },
                    "symbols": [["enum_declaration", 0, 9, "ts_enum"]],
                },
            }
        ],
        SYMBOLS,
        MODE,
    )
    relationship = _relationship(candidates=["other_file_fn", "ts_enum"])
    decision = engine.decide(context, relationship)
    assert decision.outcome == {"outcome": "none", "reason": "non-callable"}
    assert not decision.changed


def test_a_filter_cannot_resolve_without_a_binding_rule() -> None:
    """Probe (b): P covers C0 including an interface; t1.kind alone never resolves."""
    candidates = ["ts_fn_a", "ts_iface"]
    assert _narrow(candidates, proven=set(candidates)) == (tuple(candidates), ())


def test_a_candidate_without_a_symbol_record_leaves_the_edge_unchanged() -> None:
    candidates = ["missing_symbol", "ts_fn_a", "ts_type", "ts_fn_b"]
    assert _narrow(candidates) == (tuple(sorted(candidates)), ())


def test_missing_binding_is_no_binding_fact() -> None:
    assert engine.proof(None, MODE, _file({}), SYMBOLS) == (
        frozenset(),
        {"outcome": "none", "reason": "no-binding-fact"},
        (),
    )


def test_an_import_outcome_proves_nothing_in_structural_mode() -> None:
    outcome = {"outcome": "import", "binding": {"module": "./m", "name": "t"}}
    assert engine.proof(outcome, MODE, _file({}), SYMBOLS) == (
        frozenset(),
        outcome,
        (),
    )


def _relationship(**overrides: Any) -> dict[str, Any]:
    relationship = {
        "type": "calls",
        "file": "x.ts",
        "reference": "t",
        "resolution": "ambiguous",
        "candidates": ["ts_fn_a", "ts_fn_b", "ts_type"],
        "call_site_id": "call:" + "1" * 40,
        "callee_byte_start": 3,
        "callee_byte_end": 4,
        "to": "t",
        "is_internal": False,
        "provenance": {"resolver": "extract_symbol_graph", "source": "syntax"},
    }
    relationship.update(overrides)
    return relationship


def _context(language: str = "typescript", supported: bool = True) -> engine.RunContext:
    return engine.build_run_context(
        [
            {
                "path": "x.ts",
                "scope_facts": {
                    "language": language,
                    "supported": supported,
                    "bindings": {"3:4": {"outcome": "none", "reason": "unbound"}},
                    "symbols": [],
                },
            }
        ],
        SYMBOLS,
        MODE,
    )


def _globals_context(
    others: list[tuple[str, str | None, bool, list[str]]],
) -> engine.RunContext:
    """A run of ``k.js`` (a script) plus ``(path, language, supported,
    script_globals)`` for every other file."""
    files = [("k.js", "javascript", True, ["d", "g"]), *others]
    return engine.build_run_context(
        [
            {
                "path": path,
                "scope_facts": {
                    "language": language,
                    "supported": supported,
                    "bindings": {},
                    "symbols": [],
                    "script_globals": names,
                },
            }
            for path, language, supported, names in files
        ],
        SYMBOLS,
        MODE,
    )


SCRIPT_LOCAL = {
    "outcome": "local",
    "proof": [["function_declaration", 0, 5]],
    "rules": [],
    "global": "d",
}


@pytest.mark.parametrize(
    ("others", "conflict"),
    [
        ([], False),
        ([("s.js", "javascript", True, ["e"])], False),
        ([("s.js", "javascript", True, ["d"])], True),
        ([("s.ts", "typescript", True, ["d"])], True),
        ([("s.tsx", "tsx", True, ["*"])], True),
        # An unsupported JS/TS file's globals are unknown (fail closed).
        ([("s.js", "javascript", False, [])], True),
        # Other families never share JS globals.
        ([("s.py", "python", False, []), ("s.go", "go", False, [])], False),
        # A file that can carry inline scripts may declare any global (B5).
        ([("index.html", "html", False, [])], True),
        ([("page.php", "php", False, [])], True),
        ([("feed.xml", "xml", False, [])], True),
        # Markdown and reStructuredText run nothing themselves: a page a site
        # generator renders from them is outside the run (R9; #691 ruling).
        ([("README.md", "markdown", False, []), ("doc.rst", "rst", False, [])], False),
        ([("doc.rst", "restructuredtext", False, [])], False),
    ],
)
def test_script_global_check(
    others: list[tuple[str, str | None, bool, list[str]]], conflict: bool
) -> None:
    """7.2: a script top-level proof stands only if no other file of the
    run may declare the name as a global."""
    context = _globals_context(others)
    result = engine.script_global_outcome(context, context.files["k.js"], SCRIPT_LOCAL)
    expected = {"outcome": "none", "reason": "script-global"}
    assert result == (expected if conflict else SCRIPT_LOCAL)


def test_script_global_check_ignores_other_outcomes() -> None:
    context = _globals_context([("s.js", "javascript", True, ["d"])])
    file_context = context.files["k.js"]
    # The caller's own globals never conflict, and only a ``local`` outcome
    # that carries ``global`` is checked.
    assert (
        engine.script_global_outcome(_globals_context([]), file_context, SCRIPT_LOCAL)
        == SCRIPT_LOCAL
    )
    module_local = {key: SCRIPT_LOCAL[key] for key in ("outcome", "proof", "rules")}
    for value in (
        module_local,
        {"outcome": "none", "reason": "parameter"},
        {"outcome": "import", "binding": {}},
        None,
    ):
        assert engine.script_global_outcome(context, file_context, value) == value


def test_decide_narrows_an_eligible_edge_and_rewrites_it() -> None:
    relationship = _relationship()
    decisions = engine.narrow_relationships([relationship], _context())
    decision = decisions[relationship["call_site_id"]]
    assert decision.eligible and decision.changed
    assert decision.outcome == {"outcome": "none", "reason": "unbound"}
    assert relationship["candidates"] == ["ts_fn_a", "ts_fn_b"]
    assert relationship["resolution"] == "ambiguous"
    assert relationship["to"] == "t"
    assert relationship["is_internal"] is False
    assert relationship["provenance"] == {
        "resolver": "extract_symbol_graph",
        "source": "syntax",
        "call_resolution": MODE,
        "call_rules": ["t1.kind"],
    }


@pytest.mark.parametrize(
    ("context", "overrides"),
    [
        (_context(language="go"), {}),
        (_context(supported=False), {}),
        (_context(), {"reference": "obj.t"}),
        (_context(), {"reference": "this.t"}),
        (_context(), {"resolution": "resolved", "candidates": ["ts_fn_a"]}),
        (_context(), {"resolution": "unresolved", "candidates": []}),
        (_context(), {"file": "other.ts"}),
        (_context(), {"type": "dependencies"}),
    ],
)
def test_ineligible_edges_are_untouched(
    context: engine.RunContext, overrides: dict[str, Any]
) -> None:
    relationship = _relationship(**overrides)
    before = json.loads(json.dumps(relationship))
    engine.narrow_relationships([relationship], context)
    assert relationship == before


def test_name_mode_does_nothing() -> None:
    context = engine.build_run_context([], SYMBOLS, "name")
    relationship = _relationship()
    assert engine.narrow_relationships([relationship], context) == {}
    assert relationship == _relationship()


def test_rule_and_reason_vocabularies() -> None:
    assert set(engine.KNOWN_RULE_IDS) == {
        "t1.lexical",
        "t1.kind",
        "t1.family",
        "t1.ts_overload",
        "t1.js_hoist",
        "t2.import",
        "t2.import_alias",
        "t2.nested_local",
        "t2.namespace",
    }
    assert {
        "t1.lexical",
        "t2.import",
        "t2.import_alias",
        "t2.nested_local",
        "t2.namespace",
    } == engine.BINDING_RULE_IDS
    assert {
        "interface",
        "type",
        "enum",
        "module",
        "struct",
        "trait",
    } == engine.NON_CALLABLE_KINDS
    assert {"unmapped", "no-binding-fact", "unbound"} <= KNOWN_NONE_REASONS
    assert "run-tainted:dynamic-scope" in KNOWN_NONE_REASONS
    # Interim reasons leave the vocabulary once replaced (stub at PR 4).
    assert not {"stub", "script-goal-deferred", "namespace-deferred"} & (
        KNOWN_NONE_REASONS
    )
    assert CALL_RESOLUTION_FACT_VERSIONS == {"js": "28", "python": "45"}
    assert [engine.language_family(name) for name in ("tsx", "javascript", "go")] == [
        "js",
        "js",
        "go",
    ]


# ---------------------------------------------------------------------------
# Expected tables at this head (10.1)


def _table(tree: str) -> dict[str, Any]:
    return json.loads((EXPECTED / f"{tree}.json").read_text(encoding="utf-8"))


def _outcome_label(outcome: dict[str, Any] | None) -> str | None:
    if outcome is None:
        return None
    if outcome["outcome"] == "none":
        return f"none({outcome['reason']})"
    return str(outcome["outcome"])


def _on_mode(run: Any) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    facts = [
        extract_symbol_facts_for_file(
            file_path, run.path, run.language, call_resolution=MODE
        )
        for file_path in collect_source_files(run.path, run.language)
    ]
    graph = assemble_symbol_graph(
        facts,
        total_files=len(facts),
        call_resolution=MODE,
        language_filter=run.language,
    )
    return facts, graph


@pytest.mark.parametrize("tree", TREES)
def test_expected_tables_hold_at_this_head(tree: str) -> None:
    """Rows with a ``structural`` field match it; every other row is unchanged.

    At this head both analyzers are real.
    """
    table = _table(tree)
    for run in (run for run in RUNS if run.tree == tree):
        facts, graph = _on_mode(run)
        scope = {item["path"]: item["scope_facts"] for item in facts}
        # The recorded outcome is the lookup outcome after the engine's
        # cross-file script-global check (7.2).
        context = engine.build_run_context(facts, graph["symbol_lookup"], MODE)
        for item in facts:
            assert valid_scope_facts(item["scope_facts"], item["language"])
        symbols = graph["symbol_lookup"]
        edges = [edge for edge in graph["relationships"] if edge["type"] == "calls"]
        records = table["runs"][run.label]["calls"]
        assert [edge["call_site_id"] for edge in edges] == [
            record["call_site_id"] for record in records
        ]
        for edge, record in zip(edges, records, strict=True):
            label = (
                f"{run.run_id} {record['file']}:{record['line']} {record['reference']}"
            )
            facts_for_file = scope[edge["file"]]
            outcome = engine.script_global_outcome(
                context,
                context.files[edge["file"]],
                facts_for_file["bindings"].get(
                    f"{edge['callee_byte_start']}:{edge['callee_byte_end']}"
                ),
            )
            actual = {
                "outcome": _outcome_label(outcome),
                "resolution": edge["resolution"],
                "candidates": [
                    f"{symbols[c]['file']}:{symbols[c]['line']}:{symbols[c]['qualified_name']}"
                    for c in edge["candidates"]
                ],
                "rules": edge["provenance"].get("call_rules", []),
            }
            expected = record.get(MODE)
            if expected is None:
                assert edge["resolution"] == record["today"]["resolution"], label
                assert edge["candidates"] == record["today"]["candidate_ids"], label
                assert "call_rules" not in edge["provenance"], label
                assert edge["resolution"] != "resolved" or (
                    record["today"]["resolution"] == "resolved"
                ), label
                continue
            assert {key: expected[key] for key in actual} == actual, label
            if "candidate_ids" in expected:
                # Labels cannot tell two symbols on one line apart.
                assert expected["candidate_ids"] == edge["candidates"], label
            assert isinstance(record.get("pr"), int), label


def _imports_mode(run: Any) -> tuple[list[dict[str, Any]], dict[str, Any], Any]:
    facts = [
        extract_symbol_facts_for_file(
            file_path, run.path, run.language, call_resolution=IMPORTS_MODE
        )
        for file_path in collect_source_files(run.path, run.language)
    ]
    off_facts = [
        {key: value for key, value in item.items() if key != "scope_facts"}
        for item in facts
    ]
    off = assemble_symbol_graph(
        off_facts, total_files=len(facts), language_filter=run.language
    )
    links, variants = module_layout(run.path)
    graph = assemble_symbol_graph(
        facts,
        total_files=len(facts),
        call_resolution=IMPORTS_MODE,
        language_filter=run.language,
        directory_symlinks=links,
        variant_paths=variants,
    )
    context = engine.build_run_context(
        facts,
        graph["symbol_lookup"],
        IMPORTS_MODE,
        language_filter=run.language,
        directory_symlinks=links,
        variant_paths=variants,
    )
    return off["relationships"], graph, context


@pytest.mark.parametrize("tree", TREES)
def test_expected_imports_tables_hold_at_this_head(tree: str) -> None:
    """``imports`` mode (Tier 1 + Tier 2, PR 5): a row's ``imports`` field,
    else its ``structural`` field (``= structural``), else unchanged.

    The recorded outcome is the engine's decision outcome: for an import
    binding, ``import`` when it proves a target, otherwise the Tier 2
    ``none`` reason (9.8).
    """
    table = _table(tree)
    for run in (run for run in RUNS if run.tree == tree):
        off_relationships, graph, context = _imports_mode(run)
        symbols = graph["symbol_lookup"]
        edges = [edge for edge in graph["relationships"] if edge["type"] == "calls"]
        off_edges = [edge for edge in off_relationships if edge["type"] == "calls"]
        records = table["runs"][run.label]["calls"]
        assert [edge["call_site_id"] for edge in edges] == [
            record["call_site_id"] for record in records
        ]
        for edge, off_edge, record in zip(edges, off_edges, records, strict=True):
            label = (
                f"{run.run_id} {record['file']}:{record['line']} {record['reference']}"
            )
            file_context = context.files[edge["file"]]
            raw = engine.script_global_outcome(
                context,
                file_context,
                file_context.bindings.get(
                    f"{edge['callee_byte_start']}:{edge['callee_byte_end']}"
                ),
            )
            decision = engine.decide(context, off_edge)
            outcome = (
                decision.outcome
                if decision.eligible and decision.outcome is not None
                else raw
            )
            if outcome is not None and outcome.get("outcome") == "local":
                outcome = {"outcome": "local"}
            actual = {
                "outcome": _outcome_label(outcome),
                "resolution": edge["resolution"],
                "candidates": [
                    f"{symbols[c]['file']}:{symbols[c]['line']}:{symbols[c]['qualified_name']}"
                    for c in edge["candidates"]
                ],
                "rules": edge["provenance"].get("call_rules", []),
            }
            expected = record.get(IMPORTS_MODE) or record.get(MODE)
            if expected is None:
                assert edge["resolution"] == record["today"]["resolution"], label
                assert edge["candidates"] == record["today"]["candidate_ids"], label
                assert "call_rules" not in edge["provenance"], label
                continue
            assert {key: expected[key] for key in actual} == actual, label
            if "candidate_ids" in expected:
                assert expected["candidate_ids"] == edge["candidates"], label
            if IMPORTS_MODE in record and "t2.nested_local" not in actual["rules"]:
                assert record["pr"] in (5, 6), label


def test_expected_imports_rows_per_pr_are_pinned() -> None:
    counts: dict[int, int] = {}
    rules: set[str] = set()
    reasons: set[str] = set()
    nested_trees: list[str] = []
    for tree in TREES:
        for run in _table(tree)["runs"].values():
            for record in run["calls"]:
                expected = record.get(IMPORTS_MODE)
                if expected is None:
                    continue
                assert set(expected) <= {
                    "outcome",
                    "resolution",
                    "candidates",
                    "candidate_ids",
                    "rules",
                }, tree
                assert set(expected["rules"]) <= set(engine.KNOWN_RULE_IDS), tree
                rules.update(expected["rules"])
                if expected["outcome"].startswith("none("):
                    reasons.add(expected["outcome"][5:-1])
                if expected["rules"] == ["t2.nested_local"]:
                    nested_trees.append(tree)
                    assert MODE in record, tree
                else:
                    counts[record["pr"]] = counts.get(record["pr"], 0) + 1
                    assert MODE not in record, tree
    assert sorted(nested_trees) == ["py-closure", "py-closure-2", "ts-nested-scope"]
    assert counts == EXPECTED_IMPORTS_ROWS_PER_PR
    # Traceability (10.6) for the Tier 2 rules and reasons live at this head.
    assert rules >= LIVE_IMPORTS_RULES
    assert reasons >= LIVE_IMPORTS_REASONS
    assert reasons <= KNOWN_NONE_REASONS


def test_expected_rows_per_pr_are_pinned() -> None:
    counts: dict[int, int] = {}
    for tree in TREES:
        for run in _table(tree)["runs"].values():
            for record in run["calls"]:
                if record.get(MODE) is not None:
                    counts[record["pr"]] = counts.get(record["pr"], 0) + 1
    assert counts == EXPECTED_ROWS_PER_PR


def test_expected_records_use_the_known_vocabulary() -> None:
    allowed_keys = {
        "outcome",
        "resolution",
        "candidates",
        "candidate_ids",
        "rules",
        "interim",
    }
    for tree in TREES:
        for run in _table(tree)["runs"].values():
            for record in run["calls"]:
                expected = record.get(MODE)
                if expected is None:
                    assert "pr" not in record or record["pr"] > 1, tree
                    continue
                assert set(expected) <= allowed_keys, tree
                assert set(expected["rules"]) <= set(engine.KNOWN_RULE_IDS), tree
                outcome = expected["outcome"]
                assert (
                    outcome is None
                    or outcome in {"local", "import"}
                    or (
                        outcome.startswith("none(")
                        and outcome[5:-1] in KNOWN_NONE_REASONS
                    )
                ), tree
                assert 1 <= record["pr"] <= 6, tree
                assert bool(expected.get("interim")) is (record["pr"] > HEAD_PR), tree


def test_live_rules_and_reasons_have_cases() -> None:
    """Traceability (10.6) for the rules and reasons live at this head."""
    rules: set[str] = set()
    reasons: set[str] = set()
    for tree in TREES:
        for run in _table(tree)["runs"].values():
            for record in run["calls"]:
                expected = record.get(MODE)
                if expected is None:
                    continue
                rules.update(expected["rules"])
                outcome = expected["outcome"] or ""
                if outcome.startswith("none("):
                    reasons.add(outcome[5:-1])
    assert rules >= LIVE_RULES
    assert reasons >= LIVE_REASONS
    from tests import test_call_resolution_failure_modes as failure_modes

    for name in NAMED_FAILURE_MODE_TESTS:
        assert callable(getattr(failure_modes, name, None)), name
    from tests import test_call_resolution_tier1_js as tier1_js

    for name in NAMED_TIER1_JS_TESTS:
        assert callable(getattr(tier1_js, name, None)), name
    from tests import test_call_resolution_tier1_py as tier1_py

    for name in NAMED_TIER1_PY_TESTS:
        assert callable(getattr(tier1_py, name, None)), name
    # Every reason the analyzers emit on the fixtures is a live reason; the
    # two the engine itself produces are covered by the named tests.
    emitted = {
        str(outcome["reason"])
        for _, item in harness.fixture_scope_facts()
        for outcome in item["scope_facts"]["bindings"].values()
        if outcome["outcome"] == "none"
    }
    covered = LIVE_REASONS | set(TEST_WRITTEN_REASONS)
    assert emitted <= covered | {"unmapped", "no-binding-fact"}, sorted(
        emitted - covered
    )
    assert set(TEST_WRITTEN_REASONS) <= KNOWN_NONE_REASONS
    assert set(TEST_WRITTEN_REASONS.values()) <= set(NAMED_TIER1_JS_TESTS) | set(
        NAMED_TIER1_PY_TESTS
    )
    assert not set(NAMED_FAILURE_MODE_TESTS) & set(DEFERRED_FAILURE_MODE_TESTS)
    assert set(DEFERRED_FAILURE_MODE_TESTS.values()) <= {"PR 2", "PR 4"}
    for name in DEFERRED_FAILURE_MODE_TESTS:
        assert (
            getattr(failure_modes, name, None) is None
        ), f"{name} exists: move it to NAMED_FAILURE_MODE_TESTS"


def test_proving_families_have_reviewed_allowlists() -> None:
    """A family whose analyzer proves anything has reviewed grammars (7.5).

    Both analyzers emit real outcomes, so javascript, typescript, tsx and
    python must be classified in full (the Python review landed with its
    analyzer, PR 4).
    """
    from chunker.call_resolution.allowlist import REVIEWED_LANGUAGES

    assert set(FAMILY_GRAMMARS) == set(CALL_RESOLUTION_FACT_VERSIONS)
    proving: set[str] = set()
    for _, item in harness.fixture_scope_facts():
        family = engine.language_family(item["language"])
        if item["scope_facts"]["bindings"]:
            assert family is not None
            proving.add(family)
    assert {"js", "python"} <= proving
    for family in sorted(proving):
        missing = set(FAMILY_GRAMMARS[family]) - REVIEWED_LANGUAGES
        assert not missing, f"{family} proves bindings; review {sorted(missing)}"


# ---------------------------------------------------------------------------
# Scope-fact digests (4.6)


def _version_key(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in str(version).split("."))


def test_fact_versions_never_go_down_from_main() -> None:
    """A version is never reused: each family's version is at least the one
    pinned in the committed digests (#691 panel B3)."""
    pinned = json.loads(harness.SCOPE_FACTS_DIGESTS.read_text(encoding="utf-8"))
    for family, version in CALL_RESOLUTION_FACT_VERSIONS.items():
        assert _version_key(version) >= _version_key(pinned[family]["version"])


def digest_problems(
    pinned: dict[str, Any], current: dict[str, Any]
) -> list[tuple[str, str]]:
    """``(kind, message)`` problems between pinned and current digests.

    ``unbumped`` is the hard rule: a file present on both sides whose facts
    changed while its family's version did not. Every other difference
    (families, versions, files added or removed) is ``regenerate``.
    """
    problems: list[tuple[str, str]] = []
    if sorted(pinned) != sorted(current):
        problems.append(("regenerate", "families differ"))
    for family in sorted(set(pinned) & set(current)):
        old, new = pinned[family], current[family]
        shared = set(old["files"]) & set(new["files"])
        changed = sorted(
            key for key in shared if old["files"][key] != new["files"][key]
        )
        if changed and old["version"] == new["version"]:
            problems.append(
                (
                    "unbumped",
                    f"{family} facts changed without a version bump: {changed[:5]}",
                )
            )
        if _version_key(new["version"]) < _version_key(old["version"]):
            # A version number is never reused, so it never goes down: a
            # revert takes a new, higher version (#691 panel B3).
            problems.append(
                (
                    "downgrade",
                    f"{family} version went down: {old['version']} -> {new['version']}",
                )
            )
        if old["version"] != new["version"] or set(old["files"]) != set(new["files"]):
            problems.append(("regenerate", f"{family} digests are stale"))
        if not new["files"]:
            problems.append(("regenerate", f"{family} has no fixture files"))
    return problems


def test_scope_fact_digests_are_pinned_per_family() -> None:
    """A family's facts change only together with its fact version.

    Regenerate with
    ``python -m tests.call_resolution_harness --write-scope-fact-digests``
    after bumping the family's version in ``CALL_RESOLUTION_FACT_VERSIONS``,
    or after adding or removing fixture files.
    """
    pinned = json.loads(harness.SCOPE_FACTS_DIGESTS.read_text(encoding="utf-8"))
    assert digest_problems(pinned, harness.scope_fact_digests()) == []


def test_digest_rule_applies_only_to_shared_files() -> None:
    pinned = {"js": {"version": "1", "files": {"a": "1", "b": "2"}}}

    def current(version: str, files: dict[str, str]) -> dict[str, Any]:
        return {"js": {"version": version, "files": files}}

    def kinds(value: dict[str, Any]) -> set[str]:
        return {kind for kind, _ in digest_problems(pinned, value)}

    assert kinds(current("1", {"a": "1", "b": "2"})) == set()
    assert kinds(current("1", {"a": "1", "b": "X"})) == {"unbumped"}
    assert kinds(current("2", {"a": "1", "b": "X"})) == {"regenerate"}
    assert kinds(current("1", {"a": "1", "b": "2", "c": "3"})) == {"regenerate"}
    assert kinds(current("1", {"a": "1"})) == {"regenerate"}
    assert kinds(current("0", {"a": "1", "b": "2"})) == {"downgrade", "regenerate"}

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
)
from tests import call_resolution_harness as harness

capture = harness.load_capture()
RUNS = capture.discover_runs()
TREES = sorted({run.tree for run in RUNS})
EXPECTED = capture.FIXTURES / "expected"
MODE = "structural"

# Rules and reasons this head produces. Each later PR adds its own.
LIVE_RULES = {"t1.kind", "t1.family"}
LIVE_REASONS = {"stub"}
# Named generated-coverage tests (plan 10.6, R-3) that exist at this head.
NAMED_FAILURE_MODE_TESTS = (
    "test_no_binding_fact_dropped_entry_js",
    "test_no_binding_fact_dropped_entry_py",
    "test_unsupported_syntax_error",
    "test_unsupported_recursion_error",
    "test_unsupported_analyzer_exception",
)


# ---------------------------------------------------------------------------
# Engine unit tests (6.3, 7.1)


def _symbol(language: str, kind: str = "function") -> dict[str, Any]:
    return {"language": language, "kind": kind}


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
                    "bindings": {"3:4": {"outcome": "none", "reason": "stub"}},
                    "symbols": [],
                },
            }
        ],
        SYMBOLS,
        MODE,
    )


def test_decide_narrows_an_eligible_edge_and_rewrites_it() -> None:
    relationship = _relationship()
    decisions = engine.narrow_relationships([relationship], _context())
    decision = decisions[relationship["call_site_id"]]
    assert decision.eligible and decision.changed
    assert decision.outcome == {"outcome": "none", "reason": "stub"}
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
        "t2.namespace",
    }
    assert {"t1.lexical", "t2.import", "t2.namespace"} == engine.BINDING_RULE_IDS
    assert {
        "interface",
        "type",
        "enum",
        "module",
        "struct",
        "trait",
    } == engine.NON_CALLABLE_KINDS
    assert {"stub", "unmapped", "no-binding-fact", "unbound"} <= KNOWN_NONE_REASONS
    assert CALL_RESOLUTION_FACT_VERSIONS == {"js": "1", "python": "1"}
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

    At this head the analyzers are stubs, so every call in a supported file
    has the outcome ``none(stub)`` and nothing resolves.
    """
    table = _table(tree)
    for run in (run for run in RUNS if run.tree == tree):
        facts, graph = _on_mode(run)
        scope = {item["path"]: item["scope_facts"] for item in facts}
        for item in facts:
            assert valid_scope_facts(item["scope_facts"], item["language"])
            for outcome in item["scope_facts"]["bindings"].values():
                assert outcome == {"outcome": "none", "reason": "stub"}
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
            outcome = facts_for_file["bindings"].get(
                f"{edge['callee_byte_start']}:{edge['callee_byte_end']}"
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
            assert isinstance(record.get("pr"), int), label


def test_expected_records_use_the_known_vocabulary() -> None:
    allowed_keys = {"outcome", "resolution", "candidates", "rules", "interim"}
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
                if record["pr"] > 1:
                    assert expected.get("interim"), tree


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


# ---------------------------------------------------------------------------
# Scope-fact digests (4.6)


def test_scope_fact_digests_are_pinned_per_family() -> None:
    """A family's facts change only together with its fact version.

    Regenerate with
    ``python -m tests.call_resolution_harness --write-scope-fact-digests``
    after bumping the family's version in ``CALL_RESOLUTION_FACT_VERSIONS``.
    """
    pinned = json.loads(harness.SCOPE_FACTS_DIGESTS.read_text(encoding="utf-8"))
    current = harness.scope_fact_digests()
    assert sorted(pinned) == sorted(current)
    for family, entry in current.items():
        if pinned[family]["files"] != entry["files"]:
            assert (
                pinned[family]["version"] != entry["version"]
            ), f"{family} scope facts changed without a fact-version bump"
            pytest.fail(f"{family} fact version bumped; regenerate the digests")
        assert (
            pinned[family]["version"] == entry["version"]
        ), f"{family} fact version changed; regenerate the digests"
        assert entry["files"], family

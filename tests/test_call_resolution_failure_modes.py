"""Failure modes of opt-in call resolution (treesitter-chunker#682).

Plan sections 5.3 and 5.4, and the named generated-coverage tests of section
10.6 (R-3) that this head can run:

- **Synthetic facts.** Start from a committed tree's real facts, apply one
  mutation, run the real ``assemble_symbol_graph``, and assert the recorded
  reason and that the edge equals its off-mode form. The ``unmapped`` tests
  need an analyzer that proves bindings: the JS/TS ones are here, and the
  Python duplicate-key test lands with the Python analyzer.
- **Unsupported files.** Run ``extract_symbol_graph`` on a temporary copy of
  a committed tree with one change, and assert ``supported: false`` for the
  file and that on equals off. Nothing is added to errors or diagnostics, and
  nothing is raised, even with ``fail_fast``.
"""

from __future__ import annotations

import copy
import shutil
from pathlib import Path
from typing import Any

import pytest

from chunker.boundary import extract_boundary_ir
from chunker.call_resolution import engine, facts
from chunker.symbol_graph import (
    assemble_symbol_graph,
    collect_source_files,
    extract_symbol_facts_for_file,
    extract_symbol_graph,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "call_resolution"
MODE = "structural"


def _facts(root: Path, **kwargs: Any) -> list[dict[str, Any]]:
    return [
        extract_symbol_facts_for_file(
            file_path, root, None, call_resolution=MODE, **kwargs
        )
        for file_path in collect_source_files(root)
    ]


def _call(
    graph: dict[str, Any], file: str, line: int, reference: str
) -> dict[str, Any]:
    (edge,) = (
        edge
        for edge in graph["relationships"]
        if edge["type"] == "calls"
        and edge["file"] == file
        and edge["line"] == line
        and edge["reference"] == reference
    )
    return edge


def _drop_binding(
    file_facts: list[dict[str, Any]], file: str, line: int, reference: str
) -> tuple[dict[str, Any], dict[str, Any], engine.Decision]:
    """Drop one call's binding entry; return (off edge, on edge, decision)."""
    off_graph = assemble_symbol_graph(copy.deepcopy(file_facts))
    off_edge = _call(off_graph, file, line, reference)
    (target,) = (item for item in file_facts if item["path"] == file)
    key = f"{off_edge['callee_byte_start']}:{off_edge['callee_byte_end']}"
    assert key in target["scope_facts"]["bindings"]
    del target["scope_facts"]["bindings"][key]
    on_graph = assemble_symbol_graph(file_facts, call_resolution=MODE)
    context = engine.build_run_context(file_facts, on_graph["symbol_lookup"], MODE)
    return (
        off_edge,
        _call(on_graph, file, line, reference),
        engine.decide(context, off_edge),
    )


def test_no_binding_fact_dropped_entry_js() -> None:
    off_edge, on_edge, decision = _drop_binding(
        _facts(FIXTURES / "authored" / "ts-class-body"), "svc.ts", 4, "t"
    )
    assert decision.eligible
    assert decision.outcome == {"outcome": "none", "reason": "no-binding-fact"}
    assert on_edge == off_edge


def test_no_binding_fact_dropped_entry_py() -> None:
    off_edge, on_edge, decision = _drop_binding(
        _facts(FIXTURES / "authored" / "py-class-scope-2"), "a.py", 10, "helper"
    )
    assert decision.eligible
    assert decision.outcome == {"outcome": "none", "reason": "no-binding-fact"}
    assert on_edge == off_edge


def test_no_binding_fact_does_not_block_the_filters() -> None:
    """A missing binding proves nothing, so only the filters can narrow."""
    off_edge, on_edge, decision = _drop_binding(
        _facts(FIXTURES / "authored" / "ts-kind-filter"), "x.ts", 1, "t"
    )
    assert decision.outcome == {"outcome": "none", "reason": "no-binding-fact"}
    assert on_edge["resolution"] == "ambiguous"
    assert len(on_edge["candidates"]) == 2
    assert set(on_edge["candidates"]) < set(off_edge["candidates"])
    assert on_edge["provenance"]["call_rules"] == ["t1.kind"]


def test_unmapped_injected_missing_declaration() -> None:
    """A proof whose declaration maps to no symbol fails closed (5.4).

    Injects a ``local`` binding pointing at a declaration span no chunk has
    into real ts-kind-filter facts, then runs the real assembly. The proof
    is dropped (``none(unmapped)``), so only the kind filter narrows and
    nothing resolves.
    """
    file_facts = _facts(FIXTURES / "authored" / "ts-kind-filter")
    off_edge = _call(assemble_symbol_graph(copy.deepcopy(file_facts)), "x.ts", 1, "t")
    (target,) = (item for item in file_facts if item["path"] == "x.ts")
    key = f"{off_edge['callee_byte_start']}:{off_edge['callee_byte_end']}"
    target["scope_facts"]["bindings"][key] = {
        "outcome": "local",
        "proof": [["function_declaration", 9000, 9001]],
        "rules": [],
    }
    assert facts.valid_scope_facts(target["scope_facts"], target["language"])
    on_graph = assemble_symbol_graph(file_facts, call_resolution=MODE)
    on_edge = _call(on_graph, "x.ts", 1, "t")
    context = engine.build_run_context(file_facts, on_graph["symbol_lookup"], MODE)
    decision = engine.decide(context, off_edge)
    assert decision.outcome == {"outcome": "none", "reason": "unmapped"}
    assert decision.proven == frozenset()
    assert on_edge["resolution"] == "ambiguous"
    assert len(on_edge["candidates"]) == 2
    assert on_edge["provenance"]["call_rules"] == ["t1.kind"]


def _decision(
    file_facts: list[dict[str, Any]], file: str, line: int, reference: str
) -> tuple[dict[str, Any], dict[str, Any], engine.Decision]:
    """``(off edge, on edge, decision)`` for one call of mutated facts."""
    off_edge = _call(
        assemble_symbol_graph(copy.deepcopy(file_facts)), file, line, reference
    )
    on_graph = assemble_symbol_graph(file_facts, call_resolution=MODE)
    context = engine.build_run_context(file_facts, on_graph["symbol_lookup"], MODE)
    return (
        off_edge,
        _call(on_graph, file, line, reference),
        engine.decide(context, off_edge),
    )


def test_unmapped_missing_symbol() -> None:
    """A proof whose declaration has no symbol entry fails closed (5.4).

    tsx-local ``a.tsx:2 App -> Foo`` resolves to ``a.tsx:1 Foo`` unmutated.
    Dropping that symbol's join entry leaves the analyzer's proof with no
    symbol, so the outcome is ``none(unmapped)`` and the edge stays as off.
    """
    file_facts = _facts(FIXTURES / "authored" / "tsx-local")
    off_edge, on_edge, decision = _decision(
        copy.deepcopy(file_facts), "a.tsx", 2, "Foo"
    )
    assert decision.outcome["outcome"] == "local"
    assert on_edge["resolution"] == "resolved"
    (target,) = (item for item in file_facts if item["path"] == "a.tsx")
    ((node_type, start, end),) = decision.outcome["proof"]
    entries = target["scope_facts"]["symbols"]
    kept = [entry for entry in entries if entry[:3] != [node_type, start, end]]
    assert len(kept) == len(entries) - 1
    target["scope_facts"]["symbols"] = kept
    assert facts.valid_scope_facts(target["scope_facts"], target["language"])
    off_edge, on_edge, decision = _decision(file_facts, "a.tsx", 2, "Foo")
    assert decision.eligible
    assert decision.outcome == {"outcome": "none", "reason": "unmapped"}
    assert decision.proven == frozenset()
    assert on_edge == off_edge


def test_unmapped_unclassified_node(monkeypatch: pytest.MonkeyPatch) -> None:
    """An unclassified declaration kind fails closed as ``unmapped`` (7.5).

    ts-nested-only ``a.ts:3 outer -> t`` resolves to ``outer.t`` with the
    full allow-list. With ``function_declaration`` removed from the
    TypeScript list, the kind is unclassified, the analyzer fails closed and
    the edge stays as off.
    """
    from chunker.call_resolution import allowlist

    root = FIXTURES / "authored" / "ts-nested-only"
    _, on_edge, decision = _decision(_facts(root), "a.ts", 3, "t")
    assert decision.outcome["outcome"] == "local"
    assert on_edge["resolution"] == "resolved"
    monkeypatch.delitem(allowlist.ALLOWLIST["typescript"], "function_declaration")
    assert (
        allowlist.classify("typescript", "function_declaration").classification
        == allowlist.FAIL_CLOSED
    )
    off_edge, on_edge, decision = _decision(_facts(root), "a.ts", 3, "t")
    assert decision.eligible
    assert decision.outcome == {"outcome": "none", "reason": "unmapped"}
    assert on_edge == off_edge


def test_a_malformed_symbol_span_is_skipped_not_fatal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A zero-width symbol chunk is left out of ``symbols`` (panel A6)."""
    import chunker.symbol_graph as symbol_graph_module

    original = symbol_graph_module.chunk_file

    def zero_width(*args: Any, **kwargs: Any) -> Any:
        chunks = original(*args, **kwargs)
        for chunk in chunks:
            if (chunk.metadata or {}).get("symbol"):
                chunk.byte_end = chunk.byte_start
                break
        return chunks

    monkeypatch.setattr(symbol_graph_module, "chunk_file", zero_width)
    root = FIXTURES / "authored" / "ts-kind-filter"
    file_facts = _facts(root)
    for item in file_facts:
        assert facts.valid_scope_facts(item["scope_facts"], item["language"])
    # The wrapper zeroes one symbol chunk per file; each is left out.
    for item in file_facts:
        assert len(item["scope_facts"]["symbols"]) == len(item["symbol_lookup"]) - 1
    graph = assemble_symbol_graph(file_facts, call_resolution=MODE)
    assert graph["metadata"]["call_resolution"] == MODE
    assert not facts.valid_symbol_entry(["function_declaration", 5, 5, "id"])
    assert not facts.valid_symbol_entry(["", 0, 5, "id"])
    assert facts.valid_symbol_entry(["function_declaration", 0, 5, "id"])


# ---------------------------------------------------------------------------
# Unsupported files (5.3)


def _copy(tmp_path: Path, tree: str) -> Path:
    root = tmp_path / tree.rsplit("/", 1)[-1]
    shutil.copytree(FIXTURES / tree, root)
    return root


def _append(path: Path, text: bytes) -> None:
    path.write_bytes(path.read_bytes() + text)


def _assert_unsupported_and_on_equals_off(
    root: Path, file: str, *, fail_fast: bool = False
) -> None:
    (target,) = (
        item for item in _facts(root, fail_fast=fail_fast) if item["path"] == file
    )
    assert target["scope_facts"]["supported"] is False
    assert target["scope_facts"]["bindings"] == {}
    assert facts.valid_scope_facts(target["scope_facts"], target["language"])
    assert target["errors"] == []
    off = extract_symbol_graph(root, fail_fast=fail_fast)
    on = extract_symbol_graph(root, fail_fast=fail_fast, call_resolution=MODE)
    assert on["relationships"] == off["relationships"]
    assert on["errors"] == off["errors"]
    boundary_off = extract_boundary_ir(root, fail_fast=fail_fast)
    boundary_on = extract_boundary_ir(root, fail_fast=fail_fast, call_resolution=MODE)
    assert boundary_on["edges"] == boundary_off["edges"]
    assert boundary_on["diagnostics"] == boundary_off["diagnostics"]


def test_unsupported_syntax_error(tmp_path: Path) -> None:
    root = _copy(tmp_path, "authored/ts-class-body")
    _append(root / "svc.ts", b"\nexport function broken( {\n")
    _assert_unsupported_and_on_equals_off(root, "svc.ts")


def test_unsupported_recursion_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``RecursionError`` in the analyzer gives ``supported: false``.

    Injected here, because the Python stub does not recurse. The plan's
    deeply nested Python source case (``test_unsupported_deep_nesting``)
    lands with the Python analyzer; the JS one is
    ``test_unsupported_deep_nesting_js``.
    """

    def deep(*args: object) -> dict[str, Any]:
        raise RecursionError("maximum recursion depth exceeded")

    monkeypatch.setitem(facts._ANALYZERS, "python", deep)
    root = _copy(tmp_path, "authored/py-class-scope-2")
    _assert_unsupported_and_on_equals_off(root, "a.py", fail_fast=True)


def test_unsupported_deep_nesting_js(tmp_path: Path) -> None:
    """A deeply nested JS/TS expression makes the analyzer give up (5.3).

    The nesting stays under the chunker's own depth cap, so the chunker
    still emits the file's symbols and calls; the analyzer's recursion hits
    its cap and raises ``RecursionError``, which gives ``supported: false``.
    """
    from chunker.call_resolution import js_scope

    depth = js_scope.MAX_DEPTH + 100
    root = _copy(tmp_path, "authored/ts-class-body")
    _append(
        root / "svc.ts",
        b"\nexport const deep = " + b"[" * depth + b"]" * depth + b";\n",
    )
    (target,) = (item for item in _facts(root) if item["path"] == "svc.ts")
    assert target["symbol_lookup"], "the chunker must still emit the symbols"
    assert target["call_facts"]
    _assert_unsupported_and_on_equals_off(root, "svc.ts", fail_fast=True)


def test_unsupported_deep_blocks_js(tmp_path: Path) -> None:
    """Deeply nested blocks, not only arrays, make the analyzer give up (C3)."""
    depth = 400
    root = _copy(tmp_path, "authored/ts-class-body")
    _append(
        root / "svc.ts",
        b"\nexport function deep() { "
        + b"{ " * depth
        + b"t();"
        + b" }" * depth
        + b" }\n",
    )
    (target,) = (item for item in _facts(root) if item["path"] == "svc.ts")
    assert target["symbol_lookup"], "the chunker must still emit the symbols"
    _assert_unsupported_and_on_equals_off(root, "svc.ts", fail_fast=True)


def test_unsupported_analyzer_exception(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(*args: object) -> dict[str, Any]:
        raise RuntimeError("injected analyzer failure")

    monkeypatch.setitem(facts._ANALYZERS, "js", broken)
    root = _copy(tmp_path, "greenfield-r1/r9-ts")
    _assert_unsupported_and_on_equals_off(root, "web/svc.ts", fail_fast=True)
    _assert_unsupported_and_on_equals_off(root, "web/svc.tsx", fail_fast=True)


def test_unsupported_parser_initialization_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import chunker.parser

    def no_parser(language: str, config: object = None) -> object:
        raise RuntimeError(f"no parser for {language}")

    monkeypatch.setattr(chunker.parser, "get_parser", no_parser)
    root = _copy(tmp_path, "authored/ts-kind-filter")
    _assert_unsupported_and_on_equals_off(root, "x.ts", fail_fast=True)


MALFORMED_OUTPUTS = {
    "unknown-outcome": {"goal": "module", "bindings": {"1:2": {"outcome": "guess"}}},
    "not-a-dict": ["goal", "module"],
    "mixed-script-globals": {"goal": "module", "script_globals": ["a", 1]},
    "bindings-not-a-mapping": {"goal": "module", "bindings": 5},
    "unhashable-reason": {
        "goal": "module",
        "bindings": {"1:2": {"outcome": "none", "reason": ["stub"]}},
    },
    "unhashable-script-global": {"goal": "module", "script_globals": [["a"]]},
    "unhashable-outcome-kind": {"goal": "module", "bindings": {"1:2": {"outcome": []}}},
}


@pytest.mark.parametrize("shape", sorted(MALFORMED_OUTPUTS))
def test_unsupported_malformed_analyzer_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, shape: str
) -> None:
    """Malformed analyzer output fails closed and never raises (5.3)."""

    def malformed(*args: object) -> Any:
        return MALFORMED_OUTPUTS[shape]

    monkeypatch.setitem(facts._ANALYZERS, "js", malformed)
    root = _copy(tmp_path, "authored/ts-kind-filter")
    _assert_unsupported_and_on_equals_off(root, "x.ts", fail_fast=True)


@pytest.mark.parametrize("failure", ["syntax", "exception"])
def test_an_unsupported_caller_never_narrows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    """ts-kind-filter narrows on a supported caller, never on an unsupported one."""
    root = _copy(tmp_path, "authored/ts-kind-filter")
    supported = extract_symbol_graph(root, call_resolution=MODE)
    assert _call(supported, "x.ts", 1, "t")["provenance"]["call_rules"] == ["t1.kind"]
    if failure == "syntax":
        _append(root / "x.ts", b"\nconst = ;\n")
    else:

        def broken(*args: object) -> dict[str, Any]:
            raise ValueError("injected")

        monkeypatch.setitem(facts._ANALYZERS, "js", broken)
    _assert_unsupported_and_on_equals_off(root, "x.ts")

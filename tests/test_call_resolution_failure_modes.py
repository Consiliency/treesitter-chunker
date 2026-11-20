"""Failure modes of opt-in call resolution (treesitter-chunker#682).

Plan sections 5.3 and 5.4, and the named generated-coverage tests of section
10.6 (R-3) that this head can run:

- **Synthetic facts.** Start from a committed tree's real facts, apply one
  mutation, run the real ``assemble_symbol_graph``, and assert the recorded
  reason and that the edge equals its off-mode form. The ``unmapped`` tests
  need analyzers that prove bindings, so they land with them.
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

    Injected here, because the stub analyzers do not recurse. The plan's
    deeply nested source case (``test_unsupported_deep_nesting``) lands with
    the Python analyzer.
    """

    def deep(*args: object) -> dict[str, Any]:
        raise RecursionError("maximum recursion depth exceeded")

    monkeypatch.setitem(facts._ANALYZERS, "python", deep)
    root = _copy(tmp_path, "authored/py-class-scope-2")
    _assert_unsupported_and_on_equals_off(root, "a.py", fail_fast=True)


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


def test_unsupported_malformed_analyzer_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def malformed(*args: object) -> dict[str, Any]:
        return {"goal": "module", "bindings": {"1:2": {"outcome": "guess"}}}

    monkeypatch.setitem(facts._ANALYZERS, "js", malformed)
    root = _copy(tmp_path, "authored/ts-kind-filter")
    _assert_unsupported_and_on_equals_off(root, "x.ts")


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

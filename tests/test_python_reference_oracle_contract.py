"""Python definition, reference and scope lookup against the shared oracles.

Each test consumes one issue's fixture contract from
``tests/fixtures/references/python`` (IF-0-REFS-1) and parses it with the real
pinned parser.
"""

from __future__ import annotations

from pathlib import Path

from chunker.context.factory import ContextFactory
from chunker.parser import get_parser
from tests.reference_oracle import reference_case

ISSUE_274 = "treesitter-chunker#274"
ISSUE_294 = "treesitter-chunker#294"
ISSUE_278 = "treesitter-chunker#278"


def _point(node) -> tuple[int, int] | None:
    return None if node is None else tuple(node.start_point)


def test_274_module_and_nested_definitions_match_oracle() -> None:
    case = reference_case("python", "module_definitions")
    assert not case.root.has_error
    mismatches = []
    for entry in case.entries("definitions", ISSUE_274):
        resolver = ContextFactory.create_symbol_resolver("python")
        found = resolver.find_symbol_definition(
            entry["name"], case.scope(entry["scope"]), case.root
        )
        expected = case.node(entry) if entry["expect"] == "found" else None
        if found != expected:
            mismatches.append(
                (
                    entry["name"],
                    entry["scope"],
                    entry["expect"],
                    found.type if found else None,
                    _point(found),
                )
            )
    assert mismatches == []


def test_274_issue_reproduction_finds_service_declarations() -> None:
    fixture = Path(__file__).parent / "fixtures/boundary_ir/repos/python/app/service.py"
    root = get_parser("python").parse(fixture.read_bytes()).root_node
    assert not root.has_error
    resolver = ContextFactory.create_symbol_resolver("python")
    renderer = resolver.find_symbol_definition("Renderer", root, root)
    report = resolver.find_symbol_definition("render_report", root, root)
    assert renderer is not None and renderer.type == "class_definition"
    assert report is not None and report.type == "function_definition"
    assert resolver.find_symbol_definition("cleaned", root, root) is None
    assert resolver.find_symbol_definition("render", root, root) is None


def test_294_binding_targets_are_not_references_and_uses_are() -> None:
    case = reference_case("python", "binding_targets")
    assert not case.root.has_error
    extracted = {
        (name, tuple(node.start_point))
        for name, node in ContextFactory.create_context_extractor(
            "python"
        )._find_references_in_node(case.root, case.source)
    }
    mismatches = []
    for entry in case.entries("occurrences", ISSUE_294):
        node = case.occurrence(entry)
        point = tuple(node.start_point)
        resolved = {
            tuple(reference.start_point)
            for reference in ContextFactory.create_symbol_resolver(
                "python"
            ).find_symbol_references(entry["name"], case.root)
        }
        expected = entry["role"] == "use"
        observed = (point in resolved, (entry["name"], point) in extracted)
        if observed != (expected, expected):
            mismatches.append((entry["name"], point, entry["role"], observed))
    assert mismatches == []


def test_278_walrus_and_default_scopes_match_oracle() -> None:
    case = reference_case("python", "assignment_expression_scope")
    assert not case.root.has_error
    mismatches = []
    for entry in case.entries("visible", ISSUE_278):
        visible = ContextFactory.create_scope_analyzer("python").get_visible_symbols(
            case.scope(entry["scope"]), case.root
        )
        missing = sorted(set(entry["includes"]) - visible)
        leaked = sorted(set(entry["excludes"]) & visible)
        if missing or leaked:
            mismatches.append((entry["scope"], "missing", missing, "leaked", leaked))
    for entry in case.entries("enclosing", ISSUE_278):
        enclosing = ContextFactory.create_scope_analyzer("python").get_enclosing_scope(
            case.node(entry)
        )
        if enclosing != case.scope(entry["scope"]):
            mismatches.append(
                (
                    entry["node_type"],
                    (entry["row"], entry["column"]),
                    "expected",
                    entry["scope"],
                    "got",
                    enclosing.type if enclosing else None,
                    _point(enclosing),
                )
            )
    assert mismatches == []

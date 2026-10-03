"""Visible JavaScript names from real nested scopes."""

from pathlib import Path

from chunker import get_parser
from chunker.context.factory import ContextFactory


FIXTURE = Path(__file__).parent / "fixtures/boundary_ir/repos/javascript/service.js"
BOUNDARIES = Path(__file__).parent / "fixtures/context/javascript_scope_boundaries.js"


def test_javascript_scope_reports_local_definitions_without_leaking_children() -> None:
    source = FIXTURE.read_bytes()
    tree = get_parser("javascript").parse(source)
    assert tree.root_node.type == "program"
    assert not tree.root_node.has_error

    declarations = {}
    pending = [tree.root_node]
    while pending:
        node = pending.pop()
        if node.type in {"class_declaration", "function_declaration"}:
            name = node.child_by_field_name("name")
            assert name is not None
            declarations[name.text.decode("utf-8")] = node
        pending.extend(node.children)
    assert {"Renderer", "run"} <= declarations.keys()

    analyzer = ContextFactory.create_scope_analyzer("javascript")
    module_names = analyzer.get_visible_symbols(tree.root_node, tree.root_node)
    assert {"formatName", "Renderer", "run"} <= module_names
    assert {"render", "cleaned", "duplicate"}.isdisjoint(module_names)

    class_names = analyzer.get_visible_symbols(declarations["Renderer"], tree.root_node)
    assert {"formatName", "Renderer", "run", "render"} <= class_names

    run_body = declarations["run"].child_by_field_name("body")
    assert run_body is not None
    function_names = analyzer.get_visible_symbols(run_body, tree.root_node)
    assert {"formatName", "Renderer", "run", "cleaned", "duplicate"} <= function_names


def test_javascript_scope_keeps_block_and_object_method_names_contained() -> None:
    tree = get_parser("javascript").parse(BOUNDARIES.read_bytes())
    root = tree.root_node
    assert root.type == "program"
    assert not root.has_error

    analyzer = ContextFactory.create_scope_analyzer("javascript")
    module_names = analyzer.get_visible_symbols(root, root)
    assert {"obj", "run"} <= module_names
    assert {"method", "hidden", "local"}.isdisjoint(module_names)

    block = next(
        node
        for statement in root.children
        if statement.type == "if_statement"
        for node in statement.children
        if node.type == "statement_block"
    )
    assert "hidden" in analyzer.get_visible_symbols(block, root)

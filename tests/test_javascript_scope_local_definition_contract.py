"""Visible JavaScript names from real nested scopes."""

from pathlib import Path

from chunker import get_parser
from chunker.context.factory import ContextFactory


FIXTURE = Path(__file__).parent / "fixtures/boundary_ir/repos/javascript/service.js"


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

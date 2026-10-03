"""Visible Python names from real imports and nested definitions."""

from pathlib import Path

from chunker import get_parser
from chunker.context.factory import ContextFactory


FIXTURE = Path(__file__).parent / "fixtures/context/python_import_bindings.py"


def test_python_scope_reports_imports_and_local_definitions() -> None:
    tree = get_parser("python").parse(FIXTURE.read_bytes())
    root = tree.root_node
    assert root.type == "module"
    assert not root.has_error

    definitions = {
        node.child_by_field_name("name").text.decode("utf-8"): node
        for node in root.children
        if node.type in {"class_definition", "function_definition"}
    }
    analyzer = ContextFactory.create_scope_analyzer("python")
    module_names = analyzer.get_visible_symbols(root, root)
    assert {
        "os",
        "abc",
        "Path",
        "Sequence",
        "Mapping",
        "Container",
        "build",
        "first",
        "second",
    } <= module_names
    assert {
        "path",
        "collections",
        "Iterable",
        "read",
        "local",
        "value",
        "local_sqrt",
        "class_sqrt",
        "class_value",
        "left",
        "right",
    }.isdisjoint(module_names)

    class_names = ContextFactory.create_scope_analyzer("python").get_visible_symbols(
        definitions["Container"], root
    )
    assert {"read", "Nested", "class_sqrt", "class_value"} <= class_names

    nested_class = next(
        node
        for node in definitions["Container"].child_by_field_name("body").children
        if node.type == "class_definition"
    )
    nested_names = ContextFactory.create_scope_analyzer("python").get_visible_symbols(
        nested_class, root
    )
    assert "Container" in nested_names
    assert {"Nested", "class_sqrt", "class_value"}.isdisjoint(nested_names)

    method = next(
        node
        for node in definitions["Container"].child_by_field_name("body").children
        if node.type == "function_definition"
    )
    method_body = method.child_by_field_name("body")
    assert method_body is not None
    method_names = ContextFactory.create_scope_analyzer("python").get_visible_symbols(
        method_body, root
    )
    assert {"Container", "Path", "local"} <= method_names
    assert {"class_sqrt", "class_value", "read"}.isdisjoint(method_names)

    build_body = definitions["build"].child_by_field_name("body")
    assert build_body is not None
    function_names = ContextFactory.create_scope_analyzer("python").get_visible_symbols(
        build_body, root
    )
    assert {
        "Container",
        "build",
        "value",
        "left",
        "right",
        "local_sqrt",
    } <= function_names

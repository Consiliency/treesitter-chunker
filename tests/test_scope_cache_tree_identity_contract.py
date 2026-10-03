"""Scope caches must not mix independently parsed trees."""

from chunker import get_parser
from chunker.context.factory import ContextFactory


def test_visible_symbols_do_not_reuse_another_tree_results() -> None:
    parser = get_parser("javascript")
    analyzer = ContextFactory.create_scope_analyzer("javascript")

    for index in range(512):
        name = f"name{index}"
        root = parser.parse(f'import {name} from "pkg";'.encode()).root_node
        assert not root.has_error
        assert analyzer.get_visible_symbols(root, root) == {name}


def test_enclosing_scope_does_not_reuse_another_tree_parent() -> None:
    parser = get_parser("javascript")
    analyzer = ContextFactory.create_scope_analyzer("javascript")

    for index in range(512):
        name = f"outer{index}"
        root = parser.parse(
            f"function {name}() {{ const local = 1; }}".encode()
        ).root_node
        assert not root.has_error
        function = next(
            node for node in root.children if node.type == "function_declaration"
        )
        body = function.child_by_field_name("body")
        assert body is not None
        local = next(
            node
            for statement in body.children
            for node in statement.children
            if node.type == "variable_declarator"
        )
        enclosing = analyzer.get_enclosing_scope(local)
        assert enclosing is not None
        assert enclosing.child_by_field_name("name").text == name.encode()

"""Local JavaScript import bindings remain visible to scope analysis."""

from pathlib import Path

from chunker import get_parser
from chunker.context.factory import ContextFactory


FIXTURE = Path(__file__).parent / "fixtures/context/import_bindings.js"


def test_javascript_scope_uses_local_import_binding_names() -> None:
    source = FIXTURE.read_bytes()
    tree = get_parser("javascript").parse(source)
    assert tree.root_node.type == "program"
    assert not tree.root_node.has_error

    analyzer = ContextFactory.create_scope_analyzer("javascript")
    imports = analyzer._get_imported_symbols(tree.root_node)
    assert imports == {"defaultName", "localName", "unchanged", "utils"}
    assert "original" not in imports

    visible = analyzer.get_visible_symbols(tree.root_node, tree.root_node)
    assert imports <= visible

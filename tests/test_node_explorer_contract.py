"""Real-parser navigation contract for the routed debug node explorer."""

from pathlib import Path

from chunker.debug.interactive.node_explorer import NodeExplorer, Prompt


FIXTURE = Path(__file__).parent / "fixtures/boundary_ir/repos/python/app/service.py"


def test_explorer_selected_child_bookmark_and_return(monkeypatch, capsys):
    commands = iter(("child 1", "bookmark selected", "back", "goto selected", "quit"))
    monkeypatch.setattr(Prompt, "ask", lambda *args, **kwargs: next(commands))

    explorer = NodeExplorer("python")
    explorer.explore_file(str(FIXTURE))

    assert explorer.current_tree is not None
    root = explorer.current_tree.root_node
    assert root.child_count >= 2
    selected = root.children[1]
    assert selected.type == "class_definition"
    assert explorer.current_node == selected
    assert explorer.bookmarks["selected"].node == selected
    assert explorer.node_history[-1].node == root
    output = capsys.readouterr().out
    assert "Bookmarked current node as 'selected'" in output
    assert "Jumped to bookmark 'selected'" in output


def test_explorer_breadcrumb_and_siblings_follow_parsed_tree(capsys):
    source = FIXTURE.read_text(encoding="utf-8")
    explorer = NodeExplorer("python")
    explorer.current_content = source
    explorer.current_tree = explorer.parser.parse(source.encode("utf-8"))
    root = explorer.current_tree.root_node
    class_node = root.children[1]

    root_info = explorer._get_node_info(root)
    assert root_info.path == []
    assert root_info.depth == 0

    info = explorer._get_node_info(class_node)
    assert info.path == [1]
    assert info.breadcrumb == "1"
    assert info.depth == 1
    assert info.parent == root
    assert info.siblings == list(root.children)

    nested = class_node.children[-1]
    nested_info = explorer._get_node_info(nested)
    assert nested_info.path == [1, class_node.child_count - 1]
    assert nested_info.depth == 2

    explorer.current_node = class_node
    explorer._display_current_node()
    assert "Location: 1" in capsys.readouterr().out

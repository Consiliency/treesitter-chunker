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

"""Parent context from a real JavaScript arrow-function parse."""

from pathlib import Path

from chunker import get_parser
from chunker.context.factory import ContextFactory
from chunker.interfaces.context import ContextType


FIXTURE = Path(__file__).parent / "fixtures/context/arrow_parent.js"


def test_arrow_call_parent_context_names_the_lexical_binding() -> None:
    source = FIXTURE.read_bytes()
    tree = get_parser("javascript").parse(source)
    assert tree.root_node.type == "program"
    assert not tree.root_node.has_error

    pending = [tree.root_node]
    call = None
    while pending:
        node = pending.pop()
        if node.type == "call_expression" and node.text == b"normalized.trim()":
            call = node
            break
        pending.extend(node.children)
    assert call is not None

    extractor = ContextFactory.create_context_extractor("javascript")
    parents = extractor.extract_parent_context(call, tree.root_node, source)
    assert [(item.type, item.content, item.line_number) for item in parents] == [
        (ContextType.PARENT_SCOPE, "const transform = (value) => ...", 3)
    ]

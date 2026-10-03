"""Observable semantic records from a real Svelte parse."""

from pathlib import Path

from chunker import get_parser
from chunker.languages.svelte import SveltePlugin


FIXTURE = Path(__file__).parent / "fixtures/language_smoke/samples/semantic.svelte"


def test_svelte_semantic_records_preserve_script_context_and_source() -> None:
    source = FIXTURE.read_bytes()
    tree = get_parser("svelte").parse(source)
    assert tree.root_node.type == "document"
    assert not tree.root_node.has_error

    records = SveltePlugin.get_semantic_chunks(tree.root_node, source)
    scripts = [record for record in records if record["type"] == "script_element"]
    assert [(record["context"], record["language"]) for record in scripts] == [
        ("module", "typescript"),
        ("instance", "javascript"),
    ]
    assert "answer: number = 42" in scripts[0]["content"]
    assert "let items = [1, 2]" in scripts[1]["content"]

    reactive = [record for record in records if record["type"] == "reactive_statement"]
    assert len(reactive) == 1
    assert reactive[0]["content"].strip() == "$: count = items.length;"
    assert reactive[0]["start_line"] == 6

    styles = [record for record in records if record["type"] == "style_element"]
    assert len(styles) == 1
    assert styles[0]["preprocessor"] == "scss"
    assert "color: red" in styles[0]["content"]

    each = [record for record in records if record["type"] == "each_block"]
    assert len(each) == 1
    assert each[0]["start_line"] == 8
    assert each[0]["content"] == "{#each items as item}"

"""Tests for the installed native BAML grammar capsule."""

from pathlib import Path

from tree_sitter import Language, Parser
from treesitter_chunker_baml_grammar import language


FIXTURES = Path(__file__).parent / "fixtures"


def walk(node):
    yield node
    for child in node.children:
        yield from walk(child)


def test_abi_and_capsule():
    grammar = Language(language())
    assert grammar.abi_version == 15
    parser = Parser(grammar)
    tree = parser.parse(b'function hello() -> string { client: "x" prompt: `hi` }')
    assert not tree.root_node.has_error


def test_current_baml_fixtures_parse_without_recovery():
    parser = Parser(Language(language()))
    expected = {
        "complex-prompt.baml": ["function_declaration"],
        "declarations.baml": [
            "class_declaration",
            "enum_declaration",
            "interface_declaration",
            "implements_for_declaration",
            "client_declaration",
            "generator_declaration",
            "retry_policy_declaration",
            "template_string_declaration",
            "test_declaration",
            "testset_declaration",
        ],
        "generics-bigint.baml": [
            "class_declaration",
            "type_alias_declaration",
            "function_declaration",
        ],
        "prompt-crlf.baml": ["function_declaration"] * 3,
        "prompt-variants.baml": ["function_declaration"] * 3,
        "release-0201.baml": [
            "class_declaration",
            "function_declaration",
            "type_alias_declaration",
            "function_declaration",
        ],
    }
    for name, declarations in expected.items():
        source = (FIXTURES / name).read_bytes()
        root = parser.parse(source).root_node
        assert not root.has_error, name
        assert not any(node.is_error or node.is_missing for node in walk(root)), name
        assert [node.type for node in root.named_children] == declarations, name
        for node in root.named_children:
            assert source[node.start_byte : node.end_byte], name
        for prompt in (node for node in walk(root) if node.type == "prompt_field"):
            value = prompt.child_by_field_name("value")
            assert value is not None
            body = source[value.start_byte : value.end_byte]
            assert source[prompt.start_byte : prompt.end_byte].startswith(b"prompt")
            assert body.startswith((b"`", b'#"'))
            for interpolation in (
                node for node in walk(value) if node.type == "interpolation"
            ):
                text = source[interpolation.start_byte : interpolation.end_byte]
                assert text.startswith(b"${") and text.endswith(b"}")


def test_crlf_spans_are_original_byte_offsets():
    source = (FIXTURES / "prompt-crlf.baml").read_bytes()
    root = Parser(Language(language())).parse(source).root_node
    assert b"\r\n" in source
    declarations = root.named_children
    assert declarations[1].start_byte == source.index(b"function multiline_prompt")
    assert source[declarations[1].start_byte : declarations[1].end_byte].endswith(b"}")


def test_implements_for_exposes_interface_and_target_fields():
    source = (FIXTURES / "declarations.baml").read_bytes()
    root = Parser(Language(language())).parse(source).root_node
    implementation = next(
        node
        for node in root.named_children
        if node.type == "implements_for_declaration"
    )
    interface = implementation.child_by_field_name("interface")
    target = implementation.child_by_field_name("target")
    assert interface is not None and target is not None
    assert source[interface.start_byte : interface.end_byte] == b"Named"
    assert source[target.start_byte : target.end_byte] == b"Box<string>"

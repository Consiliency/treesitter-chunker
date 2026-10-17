import pytest

from chunker import core
from chunker.fallback.base import FallbackWarning
from tests.test_language_pack import _isolate_default_492


@pytest.mark.parametrize("language", ["python", "javascript"])
@pytest.mark.parametrize("character", ["\u017f", "\u212a"])
@pytest.mark.parametrize("newline", ["\n", "\r\n"], ids=("lf", "crlf"))
@pytest.mark.parametrize("from_file", [False, True])
def test_492_unicode_chunk_spans(
    monkeypatch, tmp_path, language, character, newline, from_file
):
    _isolate_default_492(monkeypatch, tmp_path)
    if language == "python":
        prefix = f"# \u00e9 {character}{newline}{newline}"
        declaration = f"def work():{newline}    return '{character}'"
        filename = tmp_path / "source.py"
        expected_type = "function_definition"
    else:
        prefix = f"// \u00e9 {character}{newline}{newline}"
        declaration = f"function work() {{ return '{character}'; }}"
        filename = tmp_path / "source.js"
        expected_type = "function_declaration"
    source = prefix + declaration + newline
    data = source.encode("utf-8")
    assert not core.get_parser(language).parse(data).root_node.has_error
    if from_file:
        filename.write_bytes(data)
        chunks = core.chunk_file(filename, language)
    else:
        chunks = core.chunk_text(source, language, file_path=str(filename))
    declarations = [chunk for chunk in chunks if chunk.node_type == expected_type]
    assert len(declarations) == 1
    chunk = declarations[0]
    assert chunk.content == declaration
    assert chunk.byte_start == len(prefix.encode("utf-8"))
    assert chunk.byte_end == len((prefix + declaration).encode("utf-8"))
    assert data[chunk.byte_start : chunk.byte_end].decode("utf-8") == declaration
    assert chunk.start_line == 3
    assert chunk.end_line == (4 if language == "python" else 3)


def test_flat_declarations_do_not_copy_source_prefixes():
    class MeasuredBytes(bytes):
        copied = 0

        def __getitem__(self, key):
            result = super().__getitem__(key)
            if isinstance(key, slice):
                self.copied += len(result)
            return result

    source = MeasuredBytes(
        "\n".join(f"def f{i}():\n    pass" for i in range(200)).encode()
    )
    tree = core.get_parser("python").parse(source)
    chunks = core._walk(tree.root_node, source, "python")
    assert len(chunks) == 200
    assert source.copied < 2 * len(source)
    assert [(c.start_line, c.end_line) for c in chunks] == [
        (2 * i + 1, 2 * i + 2) for i in range(200)
    ]


def test_chunk_text_uses_fallback_when_walk_recurses_too_deep(monkeypatch):
    class Parser:
        def parse(self, _source):
            return type("Tree", (), {"root_node": object()})()

    monkeypatch.setattr(core, "get_parser", lambda _language: Parser())
    monkeypatch.setattr(
        core, "_walk", lambda *_args, **_kwargs: (_ for _ in ()).throw(RecursionError())
    )
    monkeypatch.setattr(
        core.MetadataExtractorFactory, "create_extractor", lambda _language: None
    )
    monkeypatch.setattr(
        core.MetadataExtractorFactory, "create_analyzer", lambda _language: None
    )

    with pytest.warns(FallbackWarning):
        chunks = core.chunk_text("one\ntwo\n", "python", file_path="example.py")

    assert chunks

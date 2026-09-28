import pytest

from chunker import core
from chunker.fallback.base import FallbackWarning


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

import pytest

from chunker import core
from chunker.fallback.base import FallbackWarning


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

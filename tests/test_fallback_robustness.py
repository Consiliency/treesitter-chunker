from chunker.auto import ZeroConfigAPI
from chunker.exceptions import LanguageNotFoundError


class _InstalledRegistry:
    def is_language_installed(self, _language):
        return True


def test_auto_chunk_falls_back_for_grammar_load_failure(tmp_path, monkeypatch):
    source = tmp_path / "example.py"
    source.write_text("def example():\n    return 1\n")
    monkeypatch.setattr(
        "chunker.auto.chunk_file",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            LanguageNotFoundError("python", [])
        ),
    )

    result = ZeroConfigAPI(_InstalledRegistry()).auto_chunk_file(source)

    assert result.fallback_used is True
    assert result.chunks


def test_auto_chunk_replaces_invalid_utf8_in_fallback(tmp_path):
    source = tmp_path / "notes.unknown"
    source.write_bytes(b"valid\xff text\n")

    result = ZeroConfigAPI(_InstalledRegistry()).auto_chunk_file(source)

    assert result.fallback_used is True
    assert "\ufffd" in result.chunks[0]["content"]

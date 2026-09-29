"""BAML uses the pinned companion and preserves source spans across routes."""

import json
from pathlib import Path

import pytest

from chunker._internal.registry import LanguageRegistry
from chunker.auto import ZeroConfigAPI
from chunker.chunker import chunk_text_with_token_limit
from chunker.core import chunk_file, chunk_text
from chunker.exceptions import BamlExtraRequiredError, ParsingError
from chunker.grammar.registry import UniversalLanguageRegistry
from chunker.parser import acquire_parser, get_parser
from chunker.repo.processor import GitAwareRepoProcessor, RepoProcessor
from chunker.streaming import chunk_file_streaming
from chunker.vfs import LocalFileSystem
from chunker.vfs_chunker import VFSChunker


FIXTURES = (
    Path(__file__).parent.parent / "packages" / "baml-grammar" / "tests" / "fixtures"
)


class _InstalledRegistry:
    def is_language_installed(self, language):
        return language == "baml"


@pytest.mark.parametrize(
    "name",
    [
        "complex-prompt.baml",
        "declarations.baml",
        "generics-bigint.baml",
        "prompt-crlf.baml",
        "prompt-variants.baml",
        "release-0201.baml",
    ],
)
def test_companion_fixtures_chunk_with_source_exact_spans(name):
    path = FIXTURES / name
    source = path.read_bytes()
    regular = chunk_file(path, "baml", extract_metadata=False)
    streamed = list(chunk_file_streaming(path, "baml"))
    assert regular
    assert [
        (c.node_type, c.byte_start, c.byte_end, c.qualified_route) for c in regular
    ] == [(c.node_type, c.byte_start, c.byte_end, c.qualified_route) for c in streamed]
    assert all(
        source[c.byte_start : c.byte_end].decode("utf-8") == c.content for c in regular
    )


def test_declarations_and_routes():
    path = FIXTURES / "declarations.baml"
    source = path.read_bytes()
    regular = chunk_file(path, "baml", extract_metadata=False)
    streamed = list(chunk_file_streaming(path, "baml"))
    assert len(regular) == len(streamed) == 14
    assert [c.node_type for c in regular] == [c.node_type for c in streamed]
    assert [c.qualified_route for c in regular] == [c.qualified_route for c in streamed]
    assert [c.node_id for c in regular] == [c.node_id for c in streamed]
    canonical = chunk_text(
        source.decode("utf-8"),
        "baml",
        "fixtures/declarations.baml",
        extract_metadata=False,
    )
    golden = json.loads(
        (Path(__file__).parent / "fixtures" / "baml" / "golden.json").read_text(
            encoding="utf-8"
        )
    )
    assert [
        {
            "type": c.node_type,
            "start": c.byte_start,
            "end": c.byte_end,
            "route": c.qualified_route,
            "id": c.node_id,
        }
        for c in canonical
    ] == golden
    assert all(
        source[c.byte_start : c.byte_end].decode("utf-8") == c.content for c in regular
    )
    assert any("Named for Box<string>" in c.qualified_route[-1] for c in regular)
    assert all("anon@" not in part for c in regular for part in c.qualified_route)
    assert all(
        c.node_type
        not in {
            "let_declaration",
            "empty_statement",
            "dynamic_type_declaration",
            "associated_type_declaration",
        }
        for c in regular
    )


def test_crlf_bytes_and_zero_config(tmp_path):
    source = (FIXTURES / "prompt-crlf.baml").read_bytes()
    path = tmp_path / "source.baml"
    path.write_bytes(source)
    regular = chunk_file(path, "baml", extract_metadata=False)
    streamed = list(chunk_file_streaming(path, "baml"))
    assert [(c.byte_start, c.byte_end) for c in regular] == [
        (c.byte_start, c.byte_end) for c in streamed
    ]
    assert all(
        source[c.byte_start : c.byte_end].decode("utf-8") == c.content for c in regular
    )
    auto = ZeroConfigAPI(_InstalledRegistry()).auto_chunk_file(path)
    assert auto.language == "baml" and not auto.fallback_used
    assert [c["content"] for c in auto.chunks] == [c.content for c in regular]


def test_large_prompt_token_splits_preserve_source():
    source = (FIXTURES / "complex-prompt.baml").read_text(encoding="utf-8")
    chunks = chunk_text_with_token_limit(source, "baml", 30)
    assert len(chunks) > 1
    raw = source.encode("utf-8")
    assert all(
        raw[c.byte_start : c.byte_end].decode("utf-8") == c.content for c in chunks
    )


def test_malformed_file_is_atomic_across_routes(tmp_path):
    source = "function okay() -> string { prompt: `hi` }\r\nfunction broken( {"
    path = tmp_path / "broken.baml"
    path.write_bytes(source.encode("utf-8"))
    with pytest.raises(ParsingError):
        chunk_file(path, "baml")
    with pytest.raises(ParsingError):
        list(chunk_file_streaming(path, "baml"))
    with pytest.raises(ParsingError):
        chunk_text_with_token_limit(source, "baml", 20)
    with pytest.raises(ParsingError):
        ZeroConfigAPI(_InstalledRegistry()).auto_chunk_file(path)
    with pytest.raises(ParsingError):
        list(
            VFSChunker(LocalFileSystem(tmp_path)).chunk_file(
                "broken.baml", streaming=True
            )
        )

    (tmp_path / "good.baml").write_text(
        "function good() -> string { prompt: `hi` }", encoding="utf-8"
    )
    processor = RepoProcessor(show_progress=False)
    result = processor.process_repository(str(tmp_path), incremental=False)
    assert any(
        e["type"] == "ParsingError" and e["file"] == "broken.baml"
        for e in result.errors
    )
    assert any(r.file_path == "good.baml" and r.chunks for r in result.file_results)
    assert any(
        r.file_path == "broken.baml"
        and not r.chunks
        and isinstance(r.error, ParsingError)
        for r in result.file_results
    )
    iterator_results = list(processor.process_files_iterator(str(tmp_path)))
    assert any(
        r.file_path == "broken.baml"
        and not r.chunks
        and isinstance(r.error, ParsingError)
        for r in iterator_results
    )
    deltas = GitAwareRepoProcessor(show_progress=False)._build_watch_deltas(
        tmp_path, ["broken.baml", "good.baml"], set()
    )
    assert [e["file"] for e in deltas["errors"]] == ["broken.baml"]
    assert any(n["file"].endswith("good.baml") for n in deltas["nodes_added"])


def test_absent_companion_never_uses_ambient_grammar(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "chunker._internal.registry.baml_companion_available", lambda: False
    )
    monkeypatch.setattr(
        "chunker._internal.registry.baml_companion_version", lambda: None
    )
    monkeypatch.setattr(
        "chunker._internal.factory.baml_companion_version", lambda: None
    )
    monkeypatch.setattr("chunker.auto.baml_companion_available", lambda: False)
    monkeypatch.setattr(
        "chunker.repo.processor.baml_companion_available", lambda: False
    )
    registry = LanguageRegistry(tmp_path / "missing.so")
    monkeypatch.setattr(
        registry,
        "_try_load_from_individual_library_safely",
        lambda name: pytest.fail("ambient grammar used"),
    )
    monkeypatch.setattr(
        registry,
        "_try_load_from_language_pack",
        lambda name: pytest.fail("pack grammar used"),
    )
    assert not registry.has_language("baml")
    with pytest.raises(BamlExtraRequiredError, match="treesitter-chunker\\[baml\\]"):
        registry.get_language("baml")
    with pytest.raises(BamlExtraRequiredError):
        get_parser("baml")
    with pytest.raises(BamlExtraRequiredError):
        acquire_parser("baml")
    monkeypatch.setattr(
        "chunker.parser.TreeSitterGrammarManager",
        lambda: pytest.fail("grammar manager used"),
    )
    with pytest.raises(BamlExtraRequiredError):
        get_parser("baml")
    source = tmp_path / "sample.baml"
    source.write_text("function example() -> string { prompt: `hi` }", encoding="utf-8")
    fallback = ZeroConfigAPI(_InstalledRegistry()).auto_chunk_file(source)
    assert fallback.fallback_used and fallback.language == "unknown"
    with pytest.raises(BamlExtraRequiredError):
        ZeroConfigAPI(_InstalledRegistry()).auto_chunk_file(source, language="baml")
    assert ".baml" not in RepoProcessor._build_language_extension_map()
    assert not RepoProcessor(show_progress=False).get_processable_files(str(tmp_path))


def test_universal_registry_never_downloads_baml(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "chunker._internal.registry.baml_companion_available", lambda: False
    )
    registry = UniversalLanguageRegistry(
        tmp_path / "missing.so",
        discovery_service=None,
        download_service=None,
        cache_dir=tmp_path / "cache",
    )
    assert not registry.is_language_installed("baml")
    assert not registry.install_language("baml")
    with pytest.raises(BamlExtraRequiredError):
        registry.get_parser("baml")


def test_wrong_companion_version_fails_without_pack_fallback(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "chunker._internal.registry.baml_companion_available", lambda: False
    )
    monkeypatch.setattr(
        "chunker._internal.registry.baml_companion_version", lambda: "0.2.0"
    )
    monkeypatch.setattr(
        "chunker._internal.factory.baml_companion_version", lambda: "0.2.0"
    )
    registry = LanguageRegistry(tmp_path / "missing.so")
    monkeypatch.setattr(
        registry,
        "_try_load_from_language_pack",
        lambda name: pytest.fail("pack grammar used"),
    )
    with pytest.raises(BamlExtraRequiredError, match="0.1.0 required; installed 0.2.0"):
        registry.get_language("baml")
    with pytest.raises(BamlExtraRequiredError, match="0.1.0 required; installed 0.2.0"):
        get_parser("baml")


def test_companion_parser_metadata():
    registry = LanguageRegistry(Path("missing.so"))
    assert registry.has_language("baml")
    assert "baml" in registry.list_languages()
    metadata = registry.get_metadata("baml")
    assert metadata.version == "15"
    assert metadata.capabilities["companion_version"] == "0.1.0"
    assert chunk_text("function good() -> string { prompt: `hi` }", "baml")

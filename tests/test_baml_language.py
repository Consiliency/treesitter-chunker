"""BAML uses the pinned companion and preserves source spans across routes."""

import json
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import pytest

from chunker._internal.registry import LanguageRegistry
from chunker.auto import ZeroConfigAPI
from chunker.boundary.adapter import extract_boundary_ir
from chunker.chunker import chunk_text_with_token_limit
from chunker.core import chunk_file, chunk_text
from chunker.exceptions import BamlExtraRequiredError, ParserInitError, ParsingError
from chunker.grammar.registry import UniversalLanguageRegistry
from chunker.parser import acquire_parser, get_parser
from chunker.repo.processor import GitAwareRepoProcessor, RepoProcessor
from chunker.streaming import chunk_file_streaming
from chunker.symbol_graph import (
    collect_source_files,
    extract_symbol_facts_for_file,
    extract_symbol_graph,
)
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
        source.replace(b"\r\n", b"\n").decode("utf-8"),
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


def test_canonical_baml_detection_with_actual_registry(tmp_path):
    source = (FIXTURES / "declarations.baml").read_bytes()
    path = tmp_path / "declarations.baml"
    path.write_bytes(source)
    registry = UniversalLanguageRegistry(
        tmp_path / "missing.so",
        discovery_service=None,
        download_service=None,
        cache_dir=tmp_path / "metadata",
    )
    api = ZeroConfigAPI(registry)
    assert registry.is_language_installed("baml")
    assert api.EXTENSION_MAP[path.suffix] == "baml"
    assert api.detect_language(path) == "baml"
    implicit = api.auto_chunk_file(path)
    explicit = api.auto_chunk_file(path, language="baml")
    assert implicit.language == explicit.language == "baml"
    assert not implicit.fallback_used and not explicit.fallback_used
    assert len(implicit.chunks) == 14
    assert implicit.chunks == explicit.chunks
    assert all(c["content"] in source.decode("utf-8") for c in implicit.chunks)
    assert api.list_supported_extensions()["baml"] == [".baml"]
    assert collect_source_files(tmp_path) == [path]
    boundary = extract_boundary_ir(tmp_path, cache_dir=tmp_path / "boundary-cache")
    assert boundary["files"][0]["language"] == "baml"
    assert boundary["files"][0]["status"] == "parsed"
    assert len(boundary["nodes"]) == 14
    assert not boundary["diagnostics"]
    regular = chunk_file(path, "baml", extract_metadata=False)
    assert {
        (n["span"]["byte_start"], n["span"]["byte_end"]) for n in boundary["nodes"]
    } == {(c.byte_start, c.byte_end) for c in regular}
    assert all(
        source[c.byte_start : c.byte_end].decode("utf-8") == c.content for c in regular
    )


@pytest.mark.parametrize("companion_version", [None, "0.2.0"])
def test_automatic_baml_scans_require_supported_companion(
    tmp_path, monkeypatch, companion_version
):
    def distribution_version(name):
        if name == "treesitter-chunker-baml-grammar":
            if companion_version is None:
                raise PackageNotFoundError(name)
            return companion_version
        return version(name)

    monkeypatch.setattr("chunker._internal.registry.version", distribution_version)
    baml = tmp_path / "declarations.baml"
    baml.write_bytes((FIXTURES / "declarations.baml").read_bytes())
    python = tmp_path / "service.py"
    python.write_bytes(
        (
            Path(__file__).parent / "fixtures/boundary_ir/repos/python/app/service.py"
        ).read_bytes()
    )
    registry = UniversalLanguageRegistry(
        tmp_path / "missing.so",
        discovery_service=None,
        download_service=None,
        cache_dir=tmp_path / "metadata",
    )
    api = ZeroConfigAPI(registry)
    assert "baml" not in api.list_supported_extensions()
    assert api.detect_language(baml) is None
    assert api.auto_chunk_file(baml).fallback_used
    assert collect_source_files(tmp_path) == [python]
    graph = extract_symbol_graph(tmp_path, fail_fast=True)
    assert graph["metadata"]["files_processed"] == 1
    assert not graph["metadata"]["errors"]
    assert graph["symbols"]["functions"]
    facts = extract_symbol_facts_for_file(baml, tmp_path, fail_fast=True)
    assert (
        facts["language"] is None and not facts["chunk_records"] and not facts["errors"]
    )
    boundary = extract_boundary_ir(
        tmp_path, cache_dir=tmp_path / "boundary-cache", fail_fast=True
    )
    assert [f["path"] for f in boundary["files"]] == ["service.py"]
    assert boundary["nodes"] and not boundary["diagnostics"]
    direct = extract_boundary_ir(
        baml, cache_dir=tmp_path / "direct-cache", fail_fast=True
    )
    assert direct["files"][0]["language"] is None
    assert not direct["nodes"] and not direct["diagnostics"]
    with pytest.raises(BamlExtraRequiredError):
        extract_symbol_facts_for_file(baml, tmp_path, "baml", fail_fast=True)
    with pytest.raises(BamlExtraRequiredError):
        extract_boundary_ir(
            baml, "baml", cache_dir=tmp_path / "explicit-cache", fail_fast=True
        )


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


@pytest.mark.parametrize("streaming", [False, True])
def test_vfs_directory_continues_after_malformed_baml(tmp_path, streaming):
    (tmp_path / "broken.baml").write_text("function broken( {", encoding="utf-8")
    (tmp_path / "good.baml").write_text(
        "function good() -> string { prompt: `hi` }", encoding="utf-8"
    )
    results = list(
        VFSChunker(LocalFileSystem(tmp_path)).chunk_directory(".", streaming=streaming)
    )
    assert len(results) == 1
    assert results[0][0] == "good.baml"
    assert results[0][1]


def test_invalid_utf8_baml_reports_file_error_and_continues(tmp_path):
    (tmp_path / "broken.baml").write_bytes(b"\xff")
    (tmp_path / "good.baml").write_text(
        "function good() -> string { prompt: `hi` }", encoding="utf-8"
    )
    with pytest.raises(UnicodeDecodeError):
        list(chunk_file_streaming(tmp_path / "broken.baml", "baml"))
    vfs = VFSChunker(LocalFileSystem(tmp_path))
    for streaming in (False, True):
        results = list(vfs.chunk_directory(".", streaming=streaming))
        assert len(results) == 1 and results[0][0] == "good.baml"
    processor = RepoProcessor(show_progress=False)
    iterator_results = list(processor.process_files_iterator(str(tmp_path)))
    assert any(
        r.file_path == "broken.baml" and isinstance(r.error, UnicodeDecodeError)
        for r in iterator_results
    )
    assert any(r.file_path == "good.baml" and r.chunks for r in iterator_results)
    result = processor.process_repository(str(tmp_path), incremental=False)
    assert any(
        e["file"] == "broken.baml" and e["type"] == "UnicodeDecodeError"
        for e in result.errors
    )
    deltas = GitAwareRepoProcessor(show_progress=False)._build_watch_deltas(
        tmp_path, ["broken.baml", "good.baml"], set()
    )
    assert any(
        e["file"] == "broken.baml" and e["type"] == "UnicodeDecodeError"
        for e in deltas["errors"]
    )
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


def test_zero_config_does_not_hide_companion_load_failure(monkeypatch, tmp_path):
    source = tmp_path / "sample.baml"
    source.write_text("function sample() -> string { prompt: `hi` }", encoding="utf-8")

    def fail(*_args, **_kwargs):
        raise ParserInitError("baml", "companion ABI incompatible")

    monkeypatch.setattr("chunker.auto.chunk_file", fail)
    monkeypatch.setattr("chunker.auto.chunk_text", fail)
    api = ZeroConfigAPI(_InstalledRegistry())
    with pytest.raises(ParserInitError, match="companion ABI incompatible"):
        api.auto_chunk_file(source)
    with pytest.raises(ParserInitError, match="companion ABI incompatible"):
        api.chunk_text(source.read_text(encoding="utf-8"), "baml")


def test_companion_parser_metadata():
    registry = LanguageRegistry(Path("missing.so"))
    assert registry.has_language("baml")
    assert "baml" in registry.list_languages()
    metadata = registry.get_metadata("baml")
    assert metadata.version == "15"
    assert metadata.capabilities["companion_version"] == "0.1.0"
    assert chunk_text("function good() -> string { prompt: `hi` }", "baml")

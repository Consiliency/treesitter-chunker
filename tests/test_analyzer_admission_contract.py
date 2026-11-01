"""Analyzer pin lookup and the retired dependency inspector (treesitter-chunker#362).

ADMIT SL-ins: ``GrammarAnalyzer.analyze_grammar_file`` passes only the one-field
``{"sha256": ...}`` record to ``probe_native_grammar`` (rule 3), stores and
reuses its inspector metadata only under its own inspector key
(``grammar_analyzer.v1``), and ``GrammarMetadataExtractor.extract_from_dependencies``
is retired (inventory A1): no tool runs. Native checks use the real BAML
grammar compiled from ``packages/baml-grammar/src``.
"""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path

import pytest

from chunker._internal.grammar_management import SmartGrammarManager
from chunker.grammar.integrity import probe_native_grammar
from chunker.languages.compatibility import grammar_analyzer
from chunker.languages.compatibility.grammar_analyzer import (
    GrammarAnalyzer,
    GrammarMetadataExtractor,
)
from tests.test_compiled_grammar_analysis_contract import SOURCE, _compile_probe_fixture


def require(condition: object, name: str) -> None:
    if not condition:
        raise AssertionError(name)


@pytest.fixture(scope="module")
def baml_bytes(tmp_path_factory: pytest.TempPathFactory) -> bytes:
    return _compile_probe_fixture(
        tmp_path_factory.mktemp("analyzer"), [SOURCE / "parser.c"]
    ).read_bytes()


@pytest.fixture
def probes(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, object]]:
    calls: list[dict[str, object]] = []

    def recording(path, language, *, provenance, **kwargs):
        calls.append(
            {"path": Path(path), "language": language, "provenance": provenance}
        )
        return probe_native_grammar(path, language, provenance=provenance, **kwargs)

    monkeypatch.setattr(grammar_analyzer, "probe_native_grammar", recording)
    return calls


def _grammars(tmp_path: Path, data: bytes) -> Path:
    directory = tmp_path / "grammars"
    directory.mkdir()
    (directory / "baml.so").write_bytes(data)
    (directory / "other.so").write_bytes(b"other bytes")
    return directory


def test_analyzer_forwards_only_one_field_record(tmp_path, baml_bytes, probes):
    pin = {"sha256": sha256(baml_bytes).hexdigest()}
    analyzer = GrammarAnalyzer(
        _grammars(tmp_path, baml_bytes),
        trusted_artifacts={"baml": {**pin, "note": "ignored"}, "other": {"sha256": 7}},
    )
    version = analyzer.analyze_grammar_file("baml")
    require(version is not None, "pinned grammar analyzed")
    require(len(probes) == 1 and probes[0]["provenance"] == pin, f"{probes}")
    require(analyzer.analyze_grammar_file("other") is None, "non-str pin")
    require(
        analyzer._capabilities["other"]["validation_reason"] == "untrusted",
        f"{analyzer._capabilities['other']}",
    )
    require(len(probes) == 1, "a non-str pin never calls the probe")


def test_analyzer_metadata_is_reused_only_under_its_own_inspector(
    tmp_path, baml_bytes, probes
):
    directory = _grammars(tmp_path, baml_bytes)
    pins = {"baml": {"sha256": sha256(baml_bytes).hexdigest()}}
    # Another inspecting site admits the same bytes first, with other metadata.
    manager = SmartGrammarManager(
        directory, tmp_path / "sources", trusted_artifacts=pins
    )
    require(manager.diagnose_grammar_issues("baml").status == "healthy", "manager ok")
    analyzer = GrammarAnalyzer(directory, trusted_artifacts=pins)
    first = analyzer.analyze_grammar_file("baml")
    require(first is not None, "analyzer ran its own inspector")
    capabilities = analyzer._capabilities["baml"]
    require(capabilities["symbols_count"] > 0, f"own metadata {capabilities}")
    require(capabilities["file_size"] == len(baml_bytes), f"{capabilities}")
    probe_count = len(probes)
    second = analyzer.analyze_grammar_file("baml")
    require(second is not None and len(probes) == probe_count, "reused in-process")
    require(analyzer._capabilities["baml"] == capabilities, "same admitted metadata")


def test_dependency_inspection_is_retired(tmp_path, baml_bytes, monkeypatch):
    library = tmp_path / "baml.so"
    library.write_bytes(baml_bytes)

    def refuse(*args, **kwargs):
        raise AssertionError(f"tool run: {args}")

    monkeypatch.setattr(grammar_analyzer.subprocess, "run", refuse)
    require(
        GrammarMetadataExtractor.extract_from_dependencies(library)
        == {"dependencies": [], "dependencies_status": "retired"},
        "retired, distinguishable from no dependencies",
    )

"""Compiled grammar analysis reports real artifacts and absent languages."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from chunker.grammar_management.core import load_compiled_grammar
from chunker.languages.compatibility.grammar_analyzer import GrammarAnalyzer


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "packages/baml-grammar/src"
FIXTURE = ROOT / "packages/baml-grammar/tests/fixtures/declarations.baml"


@pytest.mark.skipif(sys.platform != "linux", reason="Analyzer inspects ELF .so symbols")
def test_local_baml_grammar_capabilities_and_missing_language(tmp_path: Path) -> None:
    grammar_path = tmp_path / "baml.so"
    subprocess.run(
        [
            "cc",
            "-shared",
            "-fPIC",
            "-O2",
            "-I",
            str(SOURCE),
            str(SOURCE / "parser.c"),
            "-o",
            str(grammar_path),
        ],
        check=True,
        capture_output=True,
    )
    source = FIXTURE.read_bytes()
    tree = load_compiled_grammar(grammar_path, "baml").parse(source)
    assert tree.root_node.type == "source_file"
    assert not tree.root_node.has_error

    analyzer = GrammarAnalyzer(tmp_path)
    assert analyzer.supported_languages == ["baml"]
    grammar = analyzer.analyze_grammar_file("baml")
    assert grammar is not None
    assert grammar.language == "baml"
    assert grammar.grammar_file == str(grammar_path)
    assert grammar.version
    capabilities = analyzer.get_grammar_capabilities("baml")
    assert capabilities["supported"] is True
    assert capabilities["version"] == grammar.version
    assert capabilities["file_size"] == grammar_path.stat().st_size
    assert capabilities["symbols_count"] > 0

    assert analyzer.analyze_grammar_file("missing") is None
    missing = analyzer.get_grammar_capabilities("missing")
    assert missing["supported"] is False
    assert missing["version"] is None
    assert missing["symbols_count"] == 0
    assert missing["file_size"] == 0

    report = analyzer.generate_grammar_report("baml")
    assert "Status: Supported" in report
    assert f"Version: {grammar.version}" in report
    assert f"Symbols Count: {capabilities['symbols_count']}" in report
    assert "Status: Not Supported" in analyzer.generate_grammar_report("missing")

    export_path = tmp_path / "analysis.json"
    analyzer.export_analysis_data(export_path)
    exported = json.loads(export_path.read_text(encoding="utf-8"))
    assert exported["metadata"]["total_languages"] == 1
    assert exported["grammars"]["baml"]["file"] == str(grammar_path)
    assert exported["grammars"]["baml"]["capabilities"]["supported"] is True
    assert exported["grammars"]["baml"]["capabilities"]["symbols_count"] > 0
    assert (
        not load_compiled_grammar(grammar_path, "baml")
        .parse(source)
        .root_node.has_error
    )


@pytest.mark.skipif(
    sys.platform != "linux", reason="Fixture uses ELF compiler comments"
)
def test_grammar_metadata_does_not_infer_versions_or_releases_from_mtime(
    tmp_path: Path,
) -> None:
    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"
    first_dir.mkdir()
    second_dir.mkdir()
    first = first_dir / "baml.so"
    second = second_dir / "baml.so"
    subprocess.run(
        [
            "cc",
            "-shared",
            "-fPIC",
            "-O2",
            "-I",
            str(SOURCE),
            str(SOURCE / "parser.c"),
            "-o",
            str(first),
        ],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["objcopy", "--remove-section=.comment", str(first)],
        check=True,
        capture_output=True,
    )
    tree = load_compiled_grammar(first, "baml").parse(FIXTURE.read_bytes())
    assert tree.root_node.type == "source_file"
    assert not tree.root_node.has_error
    second.write_bytes(first.read_bytes())
    os.utime(first, (1609459200, 1609459200))
    os.utime(second, (1640995200, 1640995200))
    assert first.read_bytes() == second.read_bytes()
    assert first.stat().st_mtime != second.stat().st_mtime

    for directory, artifact in ((first_dir, first), (second_dir, second)):
        analyzer = GrammarAnalyzer(directory)
        assert analyzer.extract_grammar_version(artifact) is None
        grammar = analyzer.analyze_grammar_file("baml")
        assert grammar is not None
        assert grammar.version == "unknown"
        assert grammar.release_date is None
        assert grammar.to_dict()["release_date"] is None
        assert "Version: unknown" in analyzer.generate_grammar_report("baml")
        export = directory / "analysis.json"
        analyzer.export_analysis_data(export)
        exported = json.loads(export.read_text(encoding="utf-8"))
        assert exported["grammars"]["baml"]["version"] == "unknown"
        assert exported["grammars"]["baml"]["capabilities"]["version"] == "unknown"

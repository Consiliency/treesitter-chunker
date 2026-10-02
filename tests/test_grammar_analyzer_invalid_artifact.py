"""Compiled grammar analysis rejects an artifact the runtime cannot load."""

import subprocess
import sys
from pathlib import Path

import pytest

from chunker.grammar_management.core import load_compiled_grammar
from chunker.languages.compatibility.grammar_analyzer import GrammarAnalyzer


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "packages/baml-grammar/src"
FIXTURE = ROOT / "packages/baml-grammar/tests/fixtures/declarations.baml"


@pytest.mark.skipif(sys.platform != "linux", reason="Compiles an ELF grammar")
def test_analyzer_tracks_current_compiled_artifact(tmp_path: Path, monkeypatch) -> None:
    grammar_path = tmp_path / "baml.so"
    grammar_path.touch()
    analyzer = GrammarAnalyzer(tmp_path)
    assert analyzer.supported_languages == []

    assert analyzer.analyze_grammar_file("baml") is None
    invalid = analyzer.get_grammar_capabilities("baml")
    assert invalid["supported"] is False
    assert invalid["version"] is None
    assert invalid["symbols_count"] == 0

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
    tree = load_compiled_grammar(grammar_path, "baml").parse(FIXTURE.read_bytes())
    assert not tree.root_node.has_error
    valid = analyzer.analyze_grammar_file("baml")
    assert valid is not None
    assert valid.grammar_file == str(grammar_path)
    assert analyzer.get_grammar_capabilities("baml")["supported"] is True
    assert analyzer.supported_languages == ["baml"]

    monkeypatch.chdir(tmp_path)
    relative = GrammarAnalyzer(Path.cwd())
    assert relative.analyze_grammar_file("baml") is not None

    replacement = tmp_path / "empty.so"
    replacement.touch()
    replacement.replace(grammar_path)
    assert analyzer.analyze_grammar_file("baml") is None
    assert analyzer.get_grammar_capabilities("baml")["supported"] is False
    assert analyzer.supported_languages == []

    grammar_path.write_bytes(b"not a shared library")
    assert GrammarAnalyzer(tmp_path).supported_languages == []

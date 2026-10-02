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
def test_analyzer_rejects_empty_artifact_but_accepts_real_grammar(
    tmp_path: Path,
) -> None:
    grammar_path = tmp_path / "baml.so"
    grammar_path.touch()
    analyzer = GrammarAnalyzer(tmp_path)

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

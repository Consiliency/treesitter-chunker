"""Grammar info exits according to the requested local grammar's health."""

import subprocess
import sys
from pathlib import Path

import pytest

from chunker._internal.user_grammar_tools import UserGrammarTools
from chunker.cli import grammar_commands
from chunker.cli.__main__ import main
from chunker.grammar_management.core import load_compiled_grammar


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "packages/baml-grammar/src"
FIXTURE = ROOT / "packages/baml-grammar/tests/fixtures/declarations.baml"


def test_missing_grammar_info_is_unsuccessful(tmp_path, monkeypatch, capsys) -> None:
    tools = UserGrammarTools(tmp_path / "build", tmp_path / "sources")
    monkeypatch.setattr(grammar_commands, "get_grammar_tools", lambda: tools)
    monkeypatch.setattr(sys, "argv", ["chunker", "grammar", "info", "missing_language"])

    assert main() == 1
    assert "Status: ⚠️ missing" in capsys.readouterr().out


@pytest.mark.skipif(sys.platform != "linux", reason="Compiles ELF grammar fixture")
def test_installed_grammar_info_succeeds(tmp_path, monkeypatch, capsys) -> None:
    build = tmp_path / "build"
    build.mkdir()
    grammar = build / "baml.so"
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
            str(grammar),
        ],
        check=True,
        capture_output=True,
    )
    tree = load_compiled_grammar(grammar, "baml").parse(FIXTURE.read_bytes())
    assert not tree.root_node.has_error
    tools = UserGrammarTools(build, tmp_path / "sources")
    monkeypatch.setattr(grammar_commands, "get_grammar_tools", lambda: tools)
    monkeypatch.setattr(sys, "argv", ["chunker", "grammar", "info", "baml"])

    assert main() == 0
    assert "Status: ✅ healthy" in capsys.readouterr().out

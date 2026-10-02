"""Compiled grammar analysis rejects an artifact the runtime cannot load."""

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

    wrong_source = tmp_path / "wrong.c"
    wrong_source.write_text(
        "void *_tree_sitter_wrong(void) { return 0; }\n", encoding="utf-8"
    )
    wrong_grammar = tmp_path / "wrong.so"
    subprocess.run(
        ["cc", "-shared", "-fPIC", str(wrong_source), "-o", str(wrong_grammar)],
        check=True,
        capture_output=True,
    )
    assert GrammarAnalyzer(tmp_path).analyze_grammar_file("wrong") is None

    null_source = tmp_path / "null.c"
    null_source.write_text(
        "void *tree_sitter_null(void) { return 0; }\n", encoding="utf-8"
    )
    null_grammar = tmp_path / "null.so"
    subprocess.run(
        ["cc", "-shared", "-fPIC", str(null_source), "-o", str(null_grammar)],
        check=True,
        capture_output=True,
    )
    assert GrammarAnalyzer(tmp_path).analyze_grammar_file("null") is None

    first_grammar = tmp_path / "a.so"
    subprocess.run(
        [
            "cc",
            "-shared",
            "-fPIC",
            "-O2",
            "-Dtree_sitter_baml=tree_sitter_a",
            "-I",
            str(SOURCE),
            str(SOURCE / "parser.c"),
            "-o",
            str(first_grammar),
        ],
        check=True,
        capture_output=True,
    )
    bulk = GrammarAnalyzer(tmp_path)
    assert bulk.supported_languages == ["a", "baml"]
    empty_first = tmp_path / "empty-a.so"
    empty_first.touch()
    empty_first.replace(first_grammar)
    assert set(bulk.analyze_all_grammars()) == {"baml"}

    monkeypatch.chdir(tmp_path)
    relative = GrammarAnalyzer(Path.cwd())
    assert relative.analyze_grammar_file("baml") is not None

    replacement = tmp_path / "empty.so"
    replacement.touch()
    replacement.replace(grammar_path)
    assert analyzer.analyze_grammar_file("baml") is None
    assert analyzer.get_grammar_capabilities("baml")["supported"] is False
    assert analyzer.supported_languages == []

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
    assert analyzer.analyze_grammar_file("baml") is not None
    stat = grammar_path.stat()
    grammar_path.write_bytes(b"x" * stat.st_size)
    os.utime(grammar_path, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    current = grammar_path.stat()
    assert (current.st_ino, current.st_size, current.st_mtime_ns) == (
        stat.st_ino,
        stat.st_size,
        stat.st_mtime_ns,
    )
    assert analyzer.analyze_grammar_file("baml") is None
    assert GrammarAnalyzer(tmp_path).supported_languages == []

"""Legacy grammar tools recognize a platform's compiled library extension."""

import subprocess
import sys
from pathlib import Path

import pytest

from chunker._internal import grammar_management
from chunker._internal import user_grammar_tools
from chunker._internal.user_grammar_tools import UserGrammarTools
from chunker.grammar_management.core import load_compiled_grammar


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "packages/baml-grammar/src"
FIXTURE = ROOT / "packages/baml-grammar/tests/fixtures/declarations.baml"


def test_running_platform_scans_its_native_library_suffix(tmp_path: Path) -> None:
    expected = {"darwin": ".dylib", "win32": ".dll"}.get(sys.platform, ".so")
    build = tmp_path / "build"
    build.mkdir()
    (build / f"baml{expected}").touch()
    tools = UserGrammarTools(build, tmp_path / "sources")

    assert tools.manager.library_suffix == expected
    assert tools.manager._library_path("baml") == build / f"baml{expected}"
    assert tools.list_installed_grammars()["total_grammars"] == 1


@pytest.mark.skipif(sys.platform != "linux", reason="Compiles an ELF fixture")
@pytest.mark.parametrize(
    ("system", "suffix"),
    [("Linux", ".so"), ("Darwin", ".dylib"), ("Windows", ".dll")],
)
def test_native_library_is_diagnosed_listed_and_removed(
    tmp_path: Path, monkeypatch, system: str, suffix: str
) -> None:
    build = tmp_path / "build"
    build.mkdir()
    grammar = build / f"baml{suffix}"
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
    monkeypatch.setattr(grammar_management.platform, "system", lambda: system)
    tools = UserGrammarTools(build, tmp_path / "sources")

    assert tools.manager.library_suffix == suffix
    assert tools.get_grammar_info("baml")["health"].status == "healthy"
    assert tools.get_grammar_info("baml")["compatibility"].compilation_date
    listed = tools.list_installed_grammars()
    assert listed["total_grammars"] == 1
    assert listed["healthy_grammars"] == 1
    assert set(tools.manager.validate_all_grammars()) == {"baml"}

    assert tools.remove_grammar("baml")["status"] == "success"
    assert not grammar.exists()
    assert tools.list_installed_grammars()["total_grammars"] == 0


@pytest.mark.skipif(sys.platform != "linux", reason="Compiles an ELF fixture")
def test_install_update_select_requested_grammar_not_unrelated_native_file(
    tmp_path: Path, monkeypatch
) -> None:
    source_dir = tmp_path / "sources" / "tree-sitter-baml"
    source_dir.mkdir(parents=True)
    grammar = source_dir / "baml.dll"
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
    (source_dir / "helper.dll").write_bytes(b"unrelated library")
    (source_dir / "baml.so").write_bytes(b"stale Linux library")
    build = tmp_path / "build"
    build.mkdir()
    monkeypatch.setattr(grammar_management.platform, "system", lambda: "Windows")
    tools = UserGrammarTools(build, tmp_path / "sources")

    def local_commands(command, **_kwargs):
        if command[:4] == ["git", "remote", "get-url", "origin"]:
            output = "https://github.com/example/tree-sitter-baml\n"
        elif command[:3] == ["git", "rev-parse", "HEAD"]:
            output = "old\n"
        elif command[:3] == ["git", "rev-parse", "origin/main"]:
            output = "new\n"
        else:
            output = ""
        return subprocess.CompletedProcess(command, 0, stdout=output)

    monkeypatch.setattr(user_grammar_tools.subprocess, "run", local_commands)
    installed = tools.install_grammar(
        "baml", "https://github.com/example/tree-sitter-baml"
    )
    assert installed["status"] == "success"
    assert (build / "baml.dll").read_bytes() == grammar.read_bytes()

    update_build = tmp_path / "update-build"
    update_build.mkdir()
    update_tools = UserGrammarTools(update_build, tmp_path / "sources")
    updated = update_tools.update_grammar("baml")
    assert updated["status"] == "success"
    assert (update_build / "baml.dll").read_bytes() == grammar.read_bytes()

    original = (update_build / "baml.dll").read_bytes()
    grammar.unlink()
    rejected = update_tools.update_grammar("baml")
    assert rejected["status"] == "error"
    assert (update_build / "baml.dll").read_bytes() == original

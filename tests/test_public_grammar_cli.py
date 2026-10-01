"""Contract tests for the exported Click grammar commands."""

import importlib.util
import shutil
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner
from tree_sitter_language_pack import cache_dir as pack_cache_dir

from chunker import get_parser
from chunker.grammar_management import grammar_cli


FIXTURE = Path(__file__).parent / "fixtures/boundary_ir/repos/python/app/service.py"


def test_click_lists_local_grammar_and_reports_missing_language(
    tmp_path: Path, monkeypatch
) -> None:
    tree = get_parser("python").parse(FIXTURE.read_bytes())
    assert tree.root_node.type == "module"
    assert not tree.root_node.has_error

    native_spec = importlib.util.find_spec("tree_sitter_language_pack._native")
    assert native_spec is not None and native_spec.origin is not None

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))

    cache_dir = tmp_path / "grammar-cache"
    user_dir = cache_dir / "grammars" / "user"
    package_dir = cache_dir / "grammars" / "package"
    user_dir.mkdir(parents=True)
    package_dir.mkdir(parents=True)
    user_library = user_dir / "libpython.so"
    shutil.copyfile(native_spec.origin, user_library)
    shutil.copyfile(native_spec.origin, package_dir / "libpython.so")

    runner = CliRunner()
    command = ["--cache-dir", str(cache_dir)]
    listed = runner.invoke(grammar_cli, [*command, "list"])
    assert listed.exit_code == 0
    assert "Total grammars: 1" in listed.output
    assert "User-installed grammars" in listed.output
    assert "python" in listed.output

    info = runner.invoke(grammar_cli, [*command, "info", "python"])
    assert info.exit_code == 0
    assert f"Path: {user_library}" in info.output
    assert "Status: ❌ Unhealthy" in info.output

    missing = runner.invoke(grammar_cli, [*command, "test", "missing", str(FIXTURE)])
    assert missing.exit_code == 1
    assert "Grammar for 'missing' not found" in missing.output


def test_click_parses_with_selected_local_grammar(tmp_path: Path, monkeypatch) -> None:
    if sys.platform != "linux":
        pytest.skip("Pinned pack's local grammar artifact is Linux-only")

    tree = get_parser("python").parse(FIXTURE.read_bytes())
    assert tree.root_node.type == "module"
    assert not tree.root_node.has_error
    native_library = Path(pack_cache_dir()) / "libtree_sitter_python.so"
    assert native_library.is_file()

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    cache_dir = tmp_path / "grammar-cache"
    user_dir = cache_dir / "grammars" / "user"
    user_dir.mkdir(parents=True)
    user_library = user_dir / "libpython.so"
    shutil.copyfile(native_library, user_library)
    runner = CliRunner()
    command = ["--cache-dir", str(cache_dir)]

    info = runner.invoke(grammar_cli, [*command, "info", "python"])
    assert info.exit_code == 0
    assert f"Path: {user_library}" in info.output
    assert "Status: ✅ Healthy" in info.output

    parsed = runner.invoke(grammar_cli, [*command, "test", "python", str(FIXTURE)])
    assert parsed.exit_code == 0
    assert "Grammar test successful" in parsed.output

    malformed = tmp_path / "malformed.py"
    malformed.write_text("def broken(:\n", encoding="utf-8")
    rejected = runner.invoke(grammar_cli, [*command, "test", "python", str(malformed)])
    assert rejected.exit_code == 1
    assert "Grammar test failed" in rejected.output

    shutil.copyfile(native_library, user_dir / "libjavascript.so")
    wrong_grammar = runner.invoke(
        grammar_cli, [*command, "test", "javascript", str(FIXTURE)]
    )
    assert wrong_grammar.exit_code == 1
    assert "tree_sitter_javascript" in wrong_grammar.output

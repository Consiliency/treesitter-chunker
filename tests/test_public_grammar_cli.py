"""Contract tests for the exported Click grammar commands."""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest
from click.testing import CliRunner
from chunker import get_parser
from chunker.grammar_management import grammar_cli


FIXTURE = Path(__file__).parent / "fixtures/boundary_ir/repos/python/app/service.py"
BAML_FIXTURE = (
    Path(__file__).parent.parent
    / "packages/baml-grammar/tests/fixtures/declarations.baml"
)


@pytest.mark.parametrize("library_name", ["libpython.so", "tree_sitter_python.so"])
def test_click_lists_local_grammar_and_reports_missing_language(
    tmp_path: Path, monkeypatch, library_name: str
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
    user_library = user_dir / library_name
    shutil.copyfile(native_spec.origin, user_library)
    shutil.copyfile(native_spec.origin, package_dir / library_name)

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


def test_click_removes_listed_user_library_and_keeps_package_fallback(
    tmp_path: Path, monkeypatch
) -> None:
    source = FIXTURE.read_bytes()
    assert not get_parser("python").parse(source).root_node.has_error
    native_spec = importlib.util.find_spec("tree_sitter_language_pack._native")
    assert native_spec is not None and native_spec.origin is not None

    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "home"))
    cache_dir = tmp_path / "grammar-cache"
    user_dir = cache_dir / "grammars" / "user"
    package_dir = cache_dir / "grammars" / "package"
    user_dir.mkdir(parents=True)
    package_dir.mkdir(parents=True)
    user_library = user_dir / "libpython.so"
    package_library = package_dir / "libpython.so"
    shutil.copyfile(native_spec.origin, user_library)
    shutil.copyfile(native_spec.origin, package_library)

    runner = CliRunner()
    command = ["--cache-dir", str(cache_dir)]
    before = runner.invoke(grammar_cli, [*command, "list"])
    assert before.exit_code == 0
    assert "User-installed grammars" in before.output

    removed = runner.invoke(grammar_cli, [*command, "remove", "python", "--no-confirm"])
    assert removed.exit_code == 0, removed.output
    assert not user_library.exists()
    assert package_library.exists()
    after = runner.invoke(grammar_cli, [*command, "list"])
    assert after.exit_code == 0
    assert "Package-bundled grammars" in after.output
    info = runner.invoke(grammar_cli, [*command, "info", "python"])
    assert info.exit_code == 0
    assert f"Path: {package_library}" in info.output


def test_click_remove_rejects_path_as_language(tmp_path: Path) -> None:
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    marker = outside_dir / "keep.txt"
    marker.write_text("keep", encoding="utf-8")

    result = CliRunner().invoke(
        grammar_cli,
        [
            "--cache-dir",
            str(tmp_path / "grammar-cache"),
            "remove",
            str(outside_dir),
            "--no-confirm",
        ],
    )
    assert result.exit_code == 1
    assert "Invalid grammar language" in result.output
    assert marker.read_text(encoding="utf-8") == "keep"


def test_click_validate_local_missing_and_invalid_grammars(
    tmp_path: Path, monkeypatch
) -> None:
    source = FIXTURE.read_bytes()
    assert not get_parser("python").parse(source).root_node.has_error

    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "home"))
    cache_dir = tmp_path / "grammar-cache"
    user_dir = cache_dir / "grammars" / "user"
    user_dir.mkdir(parents=True)
    grammar_src = Path(__file__).parent.parent / "packages/baml-grammar"
    baml_dir = user_dir / "baml"
    (baml_dir / "src").mkdir(parents=True)
    shutil.copyfile(grammar_src / "src/grammar.js", baml_dir / "grammar.js")
    shutil.copyfile(grammar_src / "src/parser.c", baml_dir / "src/parser.c")
    (user_dir / "libjava.so").touch()

    runner = CliRunner()
    command = ["--cache-dir", str(cache_dir), "validate"]
    valid = runner.invoke(grammar_cli, [*command, "baml", "--fix"])
    assert valid.exit_code == 0, valid.output
    assert "baml: healthy" in valid.output
    assert "Valid: 1" in valid.output

    missing = runner.invoke(grammar_cli, [*command, "missing"])
    assert missing.exit_code == 1
    assert "Grammar for 'missing' not found" in missing.output
    assert not isinstance(missing.exception, TypeError)

    invalid = runner.invoke(grammar_cli, [*command, "java"])
    assert invalid.exit_code == 1
    assert "java: corrupted" in invalid.output
    assert "Grammar file is empty" in invalid.output
    assert not isinstance(invalid.exception, TypeError)


def test_click_exports_selected_local_grammar(tmp_path: Path, monkeypatch) -> None:
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

    output_file = tmp_path / "grammars.json"
    result = CliRunner().invoke(
        grammar_cli,
        ["--cache-dir", str(cache_dir), "export", str(output_file)],
    )
    assert result.exit_code == 0, result.output
    exported = json.loads(output_file.read_text(encoding="utf-8"))
    assert list(exported["grammars"]) == ["python"]
    assert exported["grammars"]["python"]["path"] == str(user_library)
    assert exported["grammars"]["python"]["priority"] == "USER"


def test_click_cleanup_honors_requested_age_and_reports_removal(
    tmp_path: Path, monkeypatch
) -> None:
    parser = get_parser("python")
    source = FIXTURE.read_bytes()
    assert not parser.parse(source).root_node.has_error

    isolated_home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(isolated_home))
    monkeypatch.setenv("USERPROFILE", str(isolated_home))

    cache_dir = tmp_path / "grammar-cache"
    downloads = cache_dir / "downloads"
    builds = cache_dir / "builds"
    downloads.mkdir(parents=True)
    builds.mkdir(parents=True)
    stale = downloads / "stale.py"
    recent = builds / "recent.py"
    stale.write_bytes(source)
    recent.write_bytes(source)
    old_time = time.time() - 25 * 24 * 60 * 60
    recent_time = time.time() - 15 * 24 * 60 * 60
    os.utime(stale, (old_time, old_time))
    os.utime(recent, (recent_time, recent_time))

    result = CliRunner().invoke(
        grammar_cli, ["--cache-dir", str(cache_dir), "cleanup", "--days", "20"]
    )
    assert result.exit_code == 0, result.output
    assert "Files removed: 1" in result.output
    assert "Directories cleaned: downloads" in result.output
    assert not stale.exists()
    assert recent.exists()
    assert not parser.parse(recent.read_bytes()).root_node.has_error
    assert not isolated_home.exists()


def test_click_parses_with_selected_local_grammar(tmp_path: Path, monkeypatch) -> None:
    if sys.platform != "linux":
        pytest.skip("Local shared-library build is Linux-only")

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    cache_dir = tmp_path / "grammar-cache"
    user_dir = cache_dir / "grammars" / "user"
    user_dir.mkdir(parents=True)
    user_library = user_dir / "libbaml.so"
    grammar_src = Path(__file__).parent.parent / "packages/baml-grammar/src"
    subprocess.run(
        [
            "cc",
            "-shared",
            "-fPIC",
            "-O2",
            "-I",
            str(grammar_src),
            str(grammar_src / "parser.c"),
            "-o",
            str(user_library),
        ],
        check=True,
        capture_output=True,
    )
    runner = CliRunner()
    command = ["--cache-dir", str(cache_dir)]

    info = runner.invoke(grammar_cli, [*command, "info", "baml"])
    assert info.exit_code == 0
    assert f"Path: {user_library}" in info.output
    assert "Status: ✅ Healthy" in info.output

    parsed = runner.invoke(grammar_cli, [*command, "test", "baml", str(BAML_FIXTURE)])
    assert parsed.exit_code == 0
    assert "Grammar test successful" in parsed.output

    malformed = tmp_path / "malformed.baml"
    malformed.write_text("class Broken {\n", encoding="utf-8")
    rejected = runner.invoke(grammar_cli, [*command, "test", "baml", str(malformed)])
    assert rejected.exit_code == 1
    assert "Grammar test failed" in rejected.output

    shutil.copyfile(user_library, user_dir / "libjavascript.so")
    wrong_grammar = runner.invoke(
        grammar_cli, [*command, "test", "javascript", str(BAML_FIXTURE)]
    )
    assert wrong_grammar.exit_code == 1
    assert "tree_sitter_javascript" in wrong_grammar.output

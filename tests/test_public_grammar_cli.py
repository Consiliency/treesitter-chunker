"""Contract tests for the exported Click grammar commands."""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from io import BytesIO
from pathlib import Path

import pytest
from click.testing import CliRunner
from chunker import get_parser
from chunker.grammar_management import ComprehensiveGrammarCLI, grammar_cli


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


def test_click_list_all_reveals_shadowed_priority_candidate(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    source = FIXTURE.read_bytes()
    assert not get_parser("python").parse(source).root_node.has_error

    native_spec = importlib.util.find_spec("tree_sitter_language_pack._native")
    assert native_spec is not None and native_spec.origin is not None
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    cache_dir = tmp_path / "grammar-cache"
    user_library = cache_dir / "grammars" / "user" / "libpython.so"
    package_library = cache_dir / "grammars" / "package" / "libpython.so"
    user_library.parent.mkdir(parents=True)
    package_library.parent.mkdir(parents=True)
    shutil.copyfile(native_spec.origin, user_library)
    shutil.copyfile(native_spec.origin, package_library)

    command = ["--cache-dir", str(cache_dir), "--verbose", "list"]
    runner = CliRunner()
    selected = runner.invoke(grammar_cli, command)
    assert selected.exit_code == 0, selected.output
    assert "Total grammars: 1" in selected.output
    assert str(user_library) in selected.output
    assert str(package_library) not in selected.output

    all_candidates = runner.invoke(grammar_cli, [*command, "--all"])
    assert all_candidates.exit_code == 0, all_candidates.output
    assert "Total grammars: 2" in all_candidates.output
    assert "User-installed grammars" in all_candidates.output
    assert "Package-bundled grammars" in all_candidates.output
    assert str(user_library) in all_candidates.output
    assert str(package_library) in all_candidates.output

    fallback = ComprehensiveGrammarCLI(cache_dir=cache_dir)
    fallback.grammar_manager = None
    assert fallback.list_grammars(show_all=True, output_format="json") == 0
    fallback_candidates = json.loads(capsys.readouterr().out)
    assert set(fallback_candidates) == {str(user_library), str(package_library)}
    assert fallback.list_grammars(show_all=True) == 0
    fallback_table = capsys.readouterr().out
    assert "Total grammars: 2" in fallback_table
    assert "User-installed grammars" in fallback_table
    assert "Package-bundled grammars" in fallback_table
    assert not home.exists()


def test_exported_grammar_list_json_filters_local_grammars(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    python_source = FIXTURE.read_bytes()
    javascript_source = (
        Path(__file__).parent / "fixtures/boundary_ir/repos/javascript/service.js"
    ).read_bytes()
    assert not get_parser("python").parse(python_source).root_node.has_error
    assert not get_parser("javascript").parse(javascript_source).root_node.has_error

    native_spec = importlib.util.find_spec("tree_sitter_language_pack._native")
    assert native_spec is not None and native_spec.origin is not None
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    cache_dir = tmp_path / "grammar-cache"
    user_dir = cache_dir / "grammars" / "user"
    user_dir.mkdir(parents=True)
    for language in ("python", "javascript"):
        shutil.copyfile(native_spec.origin, user_dir / f"lib{language}.so")

    cli = ComprehensiveGrammarCLI(cache_dir=cache_dir)
    assert cli.list_grammars(language_filter="PY", output_format="json") == 0
    listed = json.loads(capsys.readouterr().out)
    assert list(listed) == ["python"]
    assert listed["python"]["path"] == str(user_dir / "libpython.so")

    assert cli.list_grammars(language_filter="missing", output_format="json") == 1
    assert "No grammars found matching 'missing'" in capsys.readouterr().out
    assert not home.exists()


def test_exported_grammar_info_json_selects_user_library(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    source = FIXTURE.read_bytes()
    parser = get_parser("python")
    assert not parser.parse(source).root_node.has_error

    native_spec = importlib.util.find_spec("tree_sitter_language_pack._native")
    assert native_spec is not None and native_spec.origin is not None
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    cache_dir = tmp_path / "grammar-cache"
    user_library = cache_dir / "grammars" / "user" / "libpython.so"
    package_library = cache_dir / "grammars" / "package" / "libpython.so"
    user_library.parent.mkdir(parents=True)
    package_library.parent.mkdir(parents=True)
    shutil.copyfile(native_spec.origin, user_library)
    shutil.copyfile(native_spec.origin, package_library)

    result = ComprehensiveGrammarCLI(cache_dir=cache_dir).info_grammar("python", "json")
    assert result == 0
    info = json.loads(capsys.readouterr().out)
    assert info["language"] == "python"
    assert info["path"] == str(user_library)
    assert info["priority"] == "USER"
    assert info["exists"] is True
    assert info["size"] == user_library.stat().st_size
    assert isinstance(info["validation"]["is_valid"], bool)
    assert isinstance(info["validation"]["errors"], list)
    assert package_library.exists()
    assert not parser.parse(source).root_node.has_error
    assert not home.exists()


def test_click_versions_reads_tags_from_configured_github_source(
    tmp_path: Path, monkeypatch
) -> None:
    source = FIXTURE.read_bytes()
    parser = get_parser("python")
    assert not parser.parse(source).root_node.has_error
    isolated_home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(isolated_home))
    monkeypatch.setenv("USERPROFILE", str(isolated_home))
    requested = []
    tags = [{"name": f"v{number}"} for number in range(12, 0, -1)]

    def read_tags(url, timeout):
        requested.append((url, timeout))
        return BytesIO(json.dumps(tags).encode("utf-8"))

    monkeypatch.setattr(urllib.request, "urlopen", read_tags)
    result = CliRunner().invoke(
        grammar_cli,
        [
            "--cache-dir",
            str(tmp_path / "grammar-cache"),
            "--verbose",
            "versions",
            "python",
        ],
    )

    assert result.exit_code == 0, result.output
    assert requested == [
        ("https://api.github.com/repos/tree-sitter/tree-sitter-python/tags", 10)
    ]
    assert (
        "Repository: https://github.com/tree-sitter/tree-sitter-python.git"
        in result.output
    )
    assert "Available Versions (Tags):" in result.output
    for number in range(12, 2, -1):
        assert f"• v{number}" in result.output
    shown = {line.strip() for line in result.output.splitlines()}
    assert "• v2" not in shown
    assert "• v1" not in shown
    assert "... and 2 more" in result.output
    assert "• main (default)" in result.output
    assert not parser.parse(source).root_node.has_error
    assert not isolated_home.exists()


def test_click_versions_reports_empty_tags_and_api_failure(
    tmp_path: Path, monkeypatch
) -> None:
    source = FIXTURE.read_bytes()
    parser = get_parser("python")
    assert not parser.parse(source).root_node.has_error
    isolated_home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(isolated_home))
    monkeypatch.setenv("USERPROFILE", str(isolated_home))
    requested = []

    def empty_tags(url, timeout):
        requested.append((url, timeout))
        return BytesIO(b"[]")

    monkeypatch.setattr(urllib.request, "urlopen", empty_tags)
    command = ["--cache-dir", str(tmp_path / "grammar-cache"), "versions", "python"]
    empty = CliRunner().invoke(grammar_cli, command)
    assert empty.exit_code == 0, empty.output
    assert "No tagged versions found" in empty.output
    assert "Try fetching the latest development version" in empty.output
    assert "• main (default)" in empty.output
    assert "Available Versions (Tags):" not in empty.output

    def unavailable(url, timeout):
        requested.append((url, timeout))
        raise urllib.error.HTTPError(url, 403, "rate limited", {}, None)

    monkeypatch.setattr(urllib.request, "urlopen", unavailable)
    failed = CliRunner().invoke(grammar_cli, command)
    assert failed.exit_code == 0, failed.output
    assert "Could not fetch version info from API: HTTP Error 403" in failed.output
    assert "Repository likely has these common branches" in failed.output
    assert "• main (default)" in failed.output
    assert "Available Versions (Tags):" not in failed.output
    assert requested == [
        ("https://api.github.com/repos/tree-sitter/tree-sitter-python/tags", 10),
        ("https://api.github.com/repos/tree-sitter/tree-sitter-python/tags", 10),
    ]
    assert not parser.parse(source).root_node.has_error
    assert not isolated_home.exists()


def test_click_fetch_unknown_language_suggests_source_without_running_git(
    tmp_path: Path, monkeypatch
) -> None:
    source = FIXTURE.read_bytes()
    parser = get_parser("python")
    assert not parser.parse(source).root_node.has_error
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))

    attempted_commands = []

    def forbid_command(*args, **kwargs):
        attempted_commands.append((args, kwargs))
        raise AssertionError("unknown grammar must not run a command")

    monkeypatch.setattr(subprocess, "run", forbid_command)
    cache_dir = tmp_path / "grammar-cache"
    result = CliRunner().invoke(
        grammar_cli,
        ["--cache-dir", str(cache_dir), "fetch", "pyth"],
    )

    assert result.exit_code == 1, result.output
    assert "No known source for 'pyth' grammar" in result.output
    assert "Did you mean one of these?" in result.output
    assert "• python" in result.output
    assert attempted_commands == []
    assert list((cache_dir / "grammars" / "user").iterdir()) == []
    assert not parser.parse(source).root_node.has_error
    assert not home.exists()


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


def test_click_remove_respects_declined_confirmation(
    tmp_path: Path, monkeypatch
) -> None:
    source = FIXTURE.read_bytes()
    parser = get_parser("python")
    assert not parser.parse(source).root_node.has_error

    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    cache_dir = tmp_path / "grammar-cache"
    user_source = cache_dir / "grammars" / "user" / "python"
    package_source = cache_dir / "grammars" / "package" / "python"
    user_source.mkdir(parents=True)
    package_source.mkdir(parents=True)
    user_fixture = user_source / "service.py"
    package_fixture = package_source / "service.py"
    user_fixture.write_bytes(source)
    package_fixture.write_bytes(source)

    command = ["--cache-dir", str(cache_dir), "remove", "python"]
    declined = CliRunner().invoke(grammar_cli, command, input="n\n")
    assert declined.exit_code == 0, declined.output
    assert "Removal cancelled" in declined.output
    assert user_fixture.read_bytes() == source
    assert package_fixture.read_bytes() == source
    assert not parser.parse(user_fixture.read_bytes()).root_node.has_error
    assert not home.exists()

    confirmed = CliRunner().invoke(grammar_cli, command, input="y\n")
    assert confirmed.exit_code == 0, confirmed.output
    assert not user_source.exists()
    assert package_fixture.read_bytes() == source
    assert not parser.parse(package_fixture.read_bytes()).root_node.has_error
    assert not home.exists()


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


def test_click_bulk_validate_discovers_both_compiled_names_with_priority(
    tmp_path: Path, monkeypatch
) -> None:
    source = FIXTURE.read_bytes()
    assert not get_parser("python").parse(source).root_node.has_error
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "home"))

    cache_dir = tmp_path / "grammar-cache"
    user_dir = cache_dir / "grammars" / "user"
    package_dir = cache_dir / "grammars" / "package"
    fallback_dir = cache_dir / "grammars" / "build"
    user_dir.mkdir(parents=True)
    package_dir.mkdir(parents=True)
    fallback_dir.mkdir(parents=True)
    (user_dir / "libpython.so").touch()
    (user_dir / "tree_sitter_python.so").write_bytes(b"not a library")
    (package_dir / "tree_sitter_python.so").write_bytes(b"not a library")
    (package_dir / "libjavascript.so").touch()
    (fallback_dir / "libgo.so").touch()

    grammar_src = Path(__file__).parent.parent / "packages/baml-grammar"
    baml_dir = user_dir / "baml"
    (baml_dir / "src").mkdir(parents=True)
    shutil.copyfile(grammar_src / "src/grammar.js", baml_dir / "grammar.js")
    shutil.copyfile(grammar_src / "src/parser.c", baml_dir / "src/parser.c")

    result = CliRunner().invoke(
        grammar_cli, ["--cache-dir", str(cache_dir), "validate"]
    )
    assert result.exit_code == 1, result.output
    assert "Validating 4 grammar(s)" in result.output
    assert "baml: healthy" in result.output
    assert "python: corrupted" in result.output
    assert "javascript: corrupted" in result.output
    assert "go: corrupted" in result.output
    assert result.output.count("Grammar file is empty") == 3
    assert "Valid: 1" in result.output
    assert "Invalid: 3" in result.output
    assert not (tmp_path / "home").exists()


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


def test_click_cleanup_fallback_preserves_recent_local_fixture(
    tmp_path: Path, monkeypatch
) -> None:
    source = FIXTURE.read_bytes()
    parser = get_parser("python")
    assert not parser.parse(source).root_node.has_error

    isolated_home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(isolated_home))
    monkeypatch.setenv("USERPROFILE", str(isolated_home))
    monkeypatch.setattr(
        "chunker.grammar_management.cli.GRAMMAR_COMPONENTS_AVAILABLE", False
    )

    cache_dir = tmp_path / "grammar-cache"
    downloads = cache_dir / "downloads"
    downloads.mkdir(parents=True)
    stale = downloads / "stale.py"
    recent = downloads / "recent.py"
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
    assert recent.read_bytes() == source
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

"""Exercise the grammar CLI's npm policy with a local postinstall fixture."""

import json
import os
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from chunker._internal.user_grammar_tools import UserGrammarTools
from chunker.cli import grammar_commands
from chunker.cli.__main__ import main
from chunker.grammar_management import _build_tools


@pytest.mark.parametrize("operation", ["install", "update"])
@pytest.mark.parametrize(
    ("allow_scripts", "approved"), [(False, True), (True, False), (True, True)]
)
def test_npm_postinstall(
    tmp_path, monkeypatch, capsys, operation, allow_scripts, approved
):
    npm = shutil.which("npm")
    if not npm or not shutil.which("node"):
        pytest.skip("npm and Node are required for the lifecycle fixture")

    for key in list(os.environ):
        if key.lower().startswith("npm_config_"):
            monkeypatch.delenv(key)
    user_config = tmp_path / "user.npmrc"
    user_config.write_text(
        f"ignore-scripts={str(allow_scripts).lower()}\n", encoding="utf-8"
    )
    monkeypatch.setenv("npm_config_userconfig", str(user_config))
    monkeypatch.setenv("npm_config_globalconfig", str(tmp_path / "global.npmrc"))
    monkeypatch.setenv("npm_config_cache", str(tmp_path / "cache"))
    monkeypatch.setenv("npm_config_offline", "true")
    monkeypatch.setenv("npm_config_audit", "false")
    monkeypatch.setenv("npm_config_update_notifier", "false")

    url = "https://github.com/example/tree-sitter-fixture"
    fixture = Path(__file__).parent / "fixtures" / "npm_lifecycle"
    tools = UserGrammarTools(tmp_path / "build", tmp_path / "sources")
    checkout = tools.grammars_dir / "tree-sitter-fixture"

    def clone_fixture():
        shutil.copytree(fixture, checkout)
        with tarfile.open(checkout / "fixture-dependency.tgz", "w:gz") as archive:
            archive.add(fixture / "dependency/package.json", "package/package.json")
            archive.add(fixture / "postinstall.cjs", "package/postinstall.cjs")
        if approved:
            manifest = checkout / "package.json"
            package = json.loads(manifest.read_text(encoding="utf-8"))
            package["allowScripts"] = {"file:fixture-dependency.tgz": True}
            manifest.write_text(json.dumps(package), encoding="utf-8")

    npm_major = int(
        subprocess.check_output([npm, "--version"], text=True).split(".")[0]
    )
    if operation == "update":
        clone_fixture()
    monkeypatch.setattr(grammar_commands, "get_grammar_tools", lambda pins: tools)
    monkeypatch.setattr(grammar_commands, "resolve_command_pins", lambda path: None)
    real_run = subprocess.run

    def run(argv, **kwargs):
        if argv[0] == npm:
            return real_run(argv, **kwargs)
        stdout = ""
        if argv[0] == "git":
            if argv[1] == "clone":
                clone_fixture()
            elif argv[1:3] == ["remote", "get-url"]:
                stdout = url
            elif argv[1] == "rev-parse":
                stdout = argv[2]  # distinct HEAD and origin/main
        else:
            assert argv == ["tree-sitter", "generate"]
        return subprocess.CompletedProcess(argv, 0, stdout=stdout, stderr="")

    monkeypatch.setattr(
        _build_tools, "resolve_tool", lambda name: npm if name == "npm" else name
    )
    monkeypatch.setattr(subprocess, "run", run)
    argv = ["chunker", "grammar", operation, "fixture"]
    if operation == "install":
        argv.append(url)
    if allow_scripts:
        argv.append("--allow-npm-scripts")
    monkeypatch.setattr(sys, "argv", argv)

    # The fixture has no compiled library. Both commands finish the dependency
    # step before reporting that the stub generator produced no .so.
    assert main() == 1
    output = capsys.readouterr().out
    assert "No .so files found" in output
    step = (
        "Installed npm dependencies"
        if operation == "install"
        else "Updated dependencies"
    )
    assert step in output, output
    marker = checkout / "postinstall.marker"
    if allow_scripts:
        assert marker.read_text(encoding="utf-8") == "ran"
    else:
        assert not marker.exists()

    dependency = checkout / "node_modules" / "fixture-dependency"
    assert (dependency / "package.json").is_file()
    dep_marker = dependency / "postinstall.marker"
    if allow_scripts and (approved or npm_major < 12):
        assert dep_marker.read_text(encoding="utf-8") == "ran"
    else:
        assert not dep_marker.exists()
    if allow_scripts and not approved and npm_major >= 12:
        assert "allowScripts" in output and "fixture-dependency" in output, output


def test_failed_update_retries_current_revision(tmp_path, monkeypatch):
    build = tmp_path / "build"
    sources = tmp_path / "sources"
    checkout = sources / "tree-sitter-fixture"
    checkout.mkdir(parents=True)
    (checkout / "package.json").write_text("{}", encoding="utf-8")
    head = "old"
    builds = []
    marker = checkout / "postinstall.marker"

    def run(argv, **kwargs):
        nonlocal head
        stdout = ""
        if argv[1:3] == ["remote", "get-url"]:
            stdout = "https://github.com/example/tree-sitter-fixture"
        elif argv[1] == "rev-parse":
            stdout = head if argv[2] == "HEAD" else "new"
        elif argv[1] == "checkout":
            head = "new"
        elif argv[0] == "npm":
            builds.append(argv[2])
            if argv[2] == "--ignore-scripts=false":
                marker.touch()
        elif argv[1] == "generate":
            builds.append("generate")
            if not marker.exists():
                raise subprocess.CalledProcessError(1, argv)
            (checkout / "fixture.so").touch()
        return subprocess.CompletedProcess(argv, 0, stdout, "")

    monkeypatch.setattr(_build_tools, "resolve_tool", lambda name: name)
    monkeypatch.setattr(subprocess, "run", run)
    monkeypatch.setattr(UserGrammarTools, "_publish_library", lambda *args: True)

    def update(**kwargs):
        # CLI retries construct a new tools object.
        tools = UserGrammarTools(build, sources)
        monkeypatch.setattr(
            tools.manager,
            "diagnose_grammar_issues",
            lambda language: SimpleNamespace(status="healthy"),
        )
        return tools.update_grammar("fixture", **kwargs)

    first = update()
    assert any("Failed to regenerate grammar" in error for error in first["errors"])
    assert head == "new"
    retry = update(allow_npm_scripts=True)
    assert retry["status"] == "success", retry
    assert builds == [
        "--ignore-scripts",
        "generate",
        "--ignore-scripts=false",
        "generate",
    ]
    completed = update(allow_npm_scripts=True)
    assert "Grammar is already up to date" in completed["warnings"]
    assert len(builds) == 4

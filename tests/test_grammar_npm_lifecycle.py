"""Exercise the grammar CLI's npm policy with a local postinstall fixture."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from chunker._internal.user_grammar_tools import UserGrammarTools
from chunker.cli import grammar_commands
from chunker.cli.__main__ import main
from chunker.grammar_management import _build_tools


@pytest.mark.parametrize("operation", ["install", "update"])
@pytest.mark.parametrize("allow_scripts", [False, True])
def test_npm_postinstall(tmp_path, monkeypatch, capsys, operation, allow_scripts):
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
    if operation == "update":
        shutil.copytree(fixture, checkout)
    monkeypatch.setattr(grammar_commands, "get_grammar_tools", lambda pins: tools)
    monkeypatch.setattr(grammar_commands, "resolve_command_pins", lambda path: None)
    real_run = subprocess.run

    def run(argv, **kwargs):
        if argv[0] == npm:
            return real_run(argv, **kwargs)
        stdout = ""
        if argv[0] == "git":
            if argv[1] == "clone":
                shutil.copytree(fixture, checkout)
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

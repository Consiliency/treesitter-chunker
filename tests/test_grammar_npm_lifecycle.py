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
    ("allow_scripts", "approved", "previous"),
    [
        pytest.param(False, True, None, id="default"),
        pytest.param(True, False, None, id="unapproved"),
        pytest.param(True, True, None, id="fresh"),
        pytest.param(True, True, "same", id="retry"),
        pytest.param(True, True, "optional", id="optional-retry"),
        pytest.param(True, True, "linked", id="linked-retry"),
        pytest.param(True, True, "older", id="upgrade"),
    ],
)
def test_npm_postinstall(
    tmp_path, monkeypatch, capsys, operation, allow_scripts, approved, previous
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

    def clone_fixture(checkout):
        shutil.copytree(fixture, checkout)
        with tarfile.open(checkout / "fixture-dependency.tgz", "w:gz") as archive:
            archive.add(fixture / "dependency/package.json", "package/package.json")
            archive.add(fixture / "postinstall.cjs", "package/postinstall.cjs")
        if approved:
            manifest = checkout / "package.json"
            package = json.loads(manifest.read_text(encoding="utf-8"))
            package["scripts"]["postinstall"] = "node consume-dependency.cjs"
            package["allowScripts"] = {"file:fixture-dependency.tgz": True}
            if previous == "optional":
                package["optionalDependencies"] = package.pop("dependencies")
                package["scripts"]["postinstall"] = "node postinstall.cjs"
                # Model a native backend unavailable on this machine.
                dep_manifest = checkout / "dependency/package.json"
                backend = json.loads(dep_manifest.read_text(encoding="utf-8"))
                backend["scripts"] = {"install": 'node -e "process.exit(1)"'}
                dep_manifest.write_text(json.dumps(backend), encoding="utf-8")
                with tarfile.open(
                    checkout / "fixture-dependency.tgz", "w:gz"
                ) as archive:
                    archive.add(dep_manifest, "package/package.json")
            if previous == "older":
                # The old hook uses a tool that belongs only to the old revision.
                toolchain = checkout / "old-toolchain.cjs"
                toolchain.write_text("", encoding="utf-8")
                dep_manifest = checkout / "dependency/package.json"
                old_package = json.loads(dep_manifest.read_text(encoding="utf-8"))
                old_package.update(
                    version="0.1.0",
                    scripts={"postinstall": "node ../../old-toolchain.cjs"},
                )
                dep_manifest.write_text(json.dumps(old_package), encoding="utf-8")
                with tarfile.open(checkout / "old.tgz", "w:gz") as archive:
                    archive.add(dep_manifest, "package/package.json")
                package["dependencies"]["fixture-dependency"] = "file:old.tgz"
                package["allowScripts"]["file:old.tgz"] = True
            manifest.write_text(json.dumps(package), encoding="utf-8")

    npm_major = int(
        subprocess.check_output([npm, "--version"], text=True).split(".")[0]
    )
    monkeypatch.setenv("npm_config_json", "true")
    monkeypatch.setenv("npm_config_loglevel", "silent")
    if operation == "update":
        clone_fixture(checkout)
    monkeypatch.setattr(grammar_commands, "get_grammar_tools", lambda pins: tools)
    monkeypatch.setattr(grammar_commands, "resolve_command_pins", lambda path: None)
    real_run = subprocess.run

    def run(argv, **kwargs):
        if argv[0] == npm:
            return real_run(argv, **kwargs)
        stdout = ""
        if argv[0] == "git":
            if argv[1] == "clone":
                clone_fixture(Path(argv[-1]))
            elif argv[1:3] == ["remote", "get-url"]:
                stdout = url
            elif argv[1:] == ["rev-parse", "--absolute-git-dir"]:
                stdout = str(tmp_path)
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
    marker = checkout / "postinstall.marker"
    dependency = checkout / "node_modules" / "fixture-dependency"
    dep_marker = dependency / "postinstall.marker"

    def invoke(args):
        monkeypatch.setattr(sys, "argv", args)
        assert main() == 1  # stub generator produces no library
        output = capsys.readouterr().out
        assert "No .so files found" in output
        step = (
            "Installed npm dependencies"
            if operation == "install"
            else "Updated dependencies"
        )
        assert step in output, output
        return output

    if not allow_scripts or previous:
        invoke(argv)
        assert (dependency / "package.json").is_file()
        assert not marker.exists()
        assert not dep_marker.exists()
    if previous == "same":
        (dependency / "package.json").chmod(0o444)
    if previous == "linked":
        modules = dependency.parent
        outside = tmp_path / "external-packages"
        modules.rename(outside)
        try:
            modules.symlink_to(outside, target_is_directory=True)
        except OSError as error:
            if getattr(error, "winerror", None) == 1314:
                pytest.skip("Creating a directory symlink requires Windows privilege")
            raise
        (outside / "keep").write_bytes(b"external data")
    if previous == "older":
        (checkout / "old-toolchain.cjs").unlink()
        manifest = checkout / "package.json"
        package = json.loads(manifest.read_text(encoding="utf-8"))
        package["dependencies"]["fixture-dependency"] = "file:fixture-dependency.tgz"
        manifest.write_text(json.dumps(package), encoding="utf-8")
    if allow_scripts:
        output = invoke([*argv, "--allow-npm-scripts"])
        assert marker.read_text(encoding="utf-8") == "ran\n"
        if previous != "optional":
            assert (dependency / "package.json").is_file()

    if previous == "linked":
        assert not modules.is_symlink()
        assert (outside / "keep").read_bytes() == b"external data"
        assert not (outside / "fixture-dependency/postinstall.marker").exists()
    if previous == "optional":
        assert not dependency.exists()
    elif allow_scripts and (approved or npm_major < 12):
        assert dep_marker.read_text(encoding="utf-8") == "ran\n"
    else:
        assert not dep_marker.exists()
    if allow_scripts and not approved and npm_major >= 12:
        assert "allowScripts" in output and "fixture-dependency" in output, output


@pytest.mark.parametrize("refused_checkout", [False, True])
def test_failed_update_retries_current_revision(
    tmp_path, monkeypatch, refused_checkout
):
    build = tmp_path / "build"
    sources = tmp_path / "sources"
    language = "x" * 230 if os.name == "posix" else "fixture"
    checkout = sources / f"tree-sitter-{language}"
    repository = tmp_path / "repository"
    repository.mkdir()
    real_run = subprocess.run
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(tmp_path / "gitconfig"))

    def git(*args, cwd=repository):
        return real_run(
            ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
        ).stdout.strip()

    git("init", "-b", "main")
    git("config", "user.name", "Fixture")
    git("config", "user.email", "fixture@example.invalid")
    git("commit", "--allow-empty", "-m", "old")
    (repository / "package.json").write_text("{}", encoding="utf-8")
    git("add", "package.json")
    git("commit", "-m", "new")
    latest = git("rev-parse", "HEAD")
    git("remote", "add", "origin", "https://github.com/example/tree-sitter-fixture")
    git("update-ref", "refs/remotes/origin/main", latest)
    git("worktree", "add", "--detach", str(checkout), "HEAD~1")
    builds = []
    marker = checkout / "postinstall.marker"

    def run(argv, **kwargs):
        if argv[:2] == ["git", "fetch"]:
            return subprocess.CompletedProcess(argv, 0, "", "")
        if argv[0] == "git":
            return real_run(argv, **kwargs)
        if argv[0] == "npm":
            builds.append(argv[2])
            if argv[2] == "--ignore-scripts=false":
                marker.touch()
        elif argv[1] == "generate":
            builds.append("generate")
            if not marker.exists():
                raise subprocess.CalledProcessError(1, argv)
            (checkout / "fixture.so").touch()
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(_build_tools, "resolve_tool", lambda name: name)
    monkeypatch.setattr(subprocess, "run", run)
    monkeypatch.setattr(UserGrammarTools, "_publish_library", lambda *args: True)

    def update(*, during_validation=None, **kwargs):
        # CLI retries construct a new tools object.
        tools = UserGrammarTools(build, sources)
        monkeypatch.setattr(
            tools.manager,
            "diagnose_grammar_issues",
            during_validation or (lambda language: SimpleNamespace(status="healthy")),
        )
        return tools.update_grammar(language, **kwargs)

    # A writable linked checkout need not have a writable parent directory.
    source_mode = sources.stat().st_mode
    if os.name == "posix":
        sources.chmod(0o555)
    try:
        first = update()
        assert any("Failed to regenerate grammar" in error for error in first["errors"])
        assert git("rev-parse", "HEAD", cwd=checkout) == latest
        if refused_checkout:
            # C conflicts with a tracked change in B. The refused checkout must
            # leave B eligible for regeneration when upstream returns to B.
            (repository / "package.json").write_text('{"upstream":true}')
            git("commit", "-am", "conflicting upstream")
            git("update-ref", "refs/remotes/origin/main", "HEAD")
            (checkout / "package.json").write_text('{"local":true}')
            refused = update()
            assert any("Failed to update repository" in e for e in refused["errors"])
            assert git("rev-parse", "HEAD", cwd=checkout) == latest
            git("update-ref", "refs/remotes/origin/main", latest)

        def overlapping_operations(_language):
            other = UserGrammarTools(build, sources)
            for result in (
                other.update_grammar(language),
                other.install_grammar(
                    language, "https://github.com/example/tree-sitter-fixture"
                ),
            ):
                assert result["status"] == "error"
                assert "checkout is busy" in " ".join(result["errors"])
            return SimpleNamespace(status="healthy")

        retry = update(allow_npm_scripts=True, during_validation=overlapping_operations)
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
    finally:
        if os.name == "posix":
            sources.chmod(source_mode)

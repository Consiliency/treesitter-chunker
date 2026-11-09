"""Public adapter contracts for Consiliency/treesitter-chunker#630."""

import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from chunker.build.builder import BuildSystem
from chunker.grammar.builder import TreeSitterGrammarBuilder
from chunker.grammar.download import GrammarDownloadManager


def test_platform_all_excluded_never_detects(tmp_path, monkeypatch):
    builder = BuildSystem()
    builder._grammars_dir = tmp_path / "grammars"
    builder._grammars_dir.mkdir()
    calls = []

    def unexpected(*args, **kwargs):
        calls.append(args)
        raise AssertionError("all excluded must not probe or compile")

    monkeypatch.setattr(subprocess, "run", unexpected)
    monkeypatch.setattr(builder.platform_support, "detect_platform", unexpected)
    label = {"linux": "linux", "darwin": "macos", "win32": "windows"}[sys.platform]
    success, info = builder.compile_grammars(["missing"], label, tmp_path / "out")
    assert not success
    assert info["compiler"] is None
    assert info["libraries"] == {}
    assert any("missing" in error for error in info["errors"])
    assert not calls


@pytest.mark.parametrize("suffix", ["cc", "cpp"])
@pytest.mark.parametrize("outcome", [0, 1, "exception"])
def test_downloader_legacy_golden(tmp_path, monkeypatch, suffix, outcome):
    root = tmp_path / "repro-grammar"
    src = root / "src"
    src.mkdir(parents=True)
    (src / "parser.c").write_text("", encoding="utf-8")
    (src / f"scanner.{suffix}").write_text("", encoding="utf-8")
    output = tmp_path / "out"
    calls = []
    monkeypatch.setenv("CC", "legacy-cc")

    def run(argv, **kwargs):
        calls.append((argv, kwargs))
        if outcome == "exception":
            raise FileNotFoundError("missing compiler")
        return SimpleNamespace(returncode=outcome, stderr="legacy error")

    monkeypatch.setattr(subprocess, "run", run)
    result = GrammarDownloadManager(tmp_path / "cache").compile_grammar(root, output)
    expected = ["legacy-cc", "-fPIC", "-shared"]
    if sys.platform == "darwin":
        expected.append("-dynamiclib")
    expected += [
        "-o",
        str(output / "repro.so"),
        str(src / "parser.c"),
        str(src / f"scanner.{suffix}"),
        "-xc++",
        "-lstdc++",
    ]
    assert calls[0][0] == expected
    assert calls[0][1]["cwd"] == str(root)
    assert len(calls) == 1
    assert result.success == (outcome == 0)


def test_individual_legacy_golden(tmp_path, monkeypatch):
    builder = TreeSitterGrammarBuilder()
    builder.set_source_directory(tmp_path / "grammars")
    builder.set_build_directory(tmp_path / "out")
    root = builder._source_dir / "tree-sitter-repro"
    src = root / "src"
    src.mkdir(parents=True)
    (src / "parser.c").write_text("", encoding="utf-8")
    (src / "scanner.cc").write_text("", encoding="utf-8")
    monkeypatch.setattr("shutil.which", lambda name: "/tools/clang++")
    calls = []

    def run(argv, **kwargs):
        calls.append((argv, kwargs))
        Path(argv[argv.index("-o") + 1]).write_bytes(b"legacy")
        return SimpleNamespace(returncode=0, stderr="")

    monkeypatch.setattr(subprocess, "run", run)
    assert builder.build_individual("repro")
    expected = ["clang++", "-shared"]
    if sys.platform != "win32":
        expected.append("-fPIC")
    expected += [
        "-O2",
        "-o",
        str(builder._build_dir / f"repro{builder._lib_extension}"),
        str(src / "parser.c"),
        str(src / "scanner.cc"),
        "-std=c++17",
        "-lstdc++",
    ]
    assert calls[0][0] == expected
    assert "cwd" not in calls[0][1]
    assert len(calls) == 1


@pytest.mark.parametrize("builder_kind", ["manager", "combined", "platform"])
@pytest.mark.parametrize(
    "excluded", ["missing", "no-parser", "cc", "cpp", "symlink", "dangling"]
)
def test_combined_membership(tmp_path, monkeypatch, builder_kind, excluded):
    from chunker.grammar_manager import GrammarManager
    from tests.test_reproducible_grammar_build import _policy_required

    common = tmp_path / "grammars"
    good = common / "tree-sitter-good" / "src"
    good.mkdir(parents=True)
    (good / "parser.c").write_text("int good;", encoding="utf-8")
    bad = common / "tree-sitter-bad"
    if excluded != "missing":
        (bad / "src").mkdir(parents=True)
        if excluded != "no-parser":
            (bad / "src" / "parser.c").write_text("int bad;", encoding="utf-8")
        if excluded in {"cc", "cpp"}:
            (bad / "src" / f"scanner.{excluded}").touch()
        if excluded in {"symlink", "dangling"}:
            link = bad / "src" / "parser.c"
            link.unlink()
            try:
                link.symlink_to(
                    good / ("parser.c" if excluded == "symlink" else "absent")
                )
            except OSError as error:
                if _policy_required():
                    pytest.fail(f"Required symlink unavailable: {error}")
                pytest.skip(f"Symlink unavailable: {error}")
    calls = []

    def run(argv, **kwargs):
        calls.append(argv)
        assert not any("tree-sitter-bad" in arg for arg in argv)
        Path(argv[argv.index("-o") + 1]).write_bytes(b"built")
        return SimpleNamespace(returncode=0, stderr="")

    monkeypatch.setattr(subprocess, "run", run)
    monkeypatch.setattr("shutil.which", lambda name: "tools/gcc")
    if builder_kind == "manager":
        tool = GrammarManager(tmp_path)
        result = tool.compile_grammars(["bad", "good"])
        # Requested-but-never-fetched keys remain absent (I3).
        assert result == (
            {"good": True} if excluded == "missing" else {"bad": False, "good": True}
        )
    elif builder_kind == "combined":
        tool = TreeSitterGrammarBuilder()
        tool.set_source_directory(common)
        tool.set_build_directory(tmp_path / "out")
        assert tool.build(["bad", "good"]) == {"bad": False, "good": True}
    else:
        # Exercise the Unix route without native platform mismatches.
        monkeypatch.setattr(sys, "platform", "linux")
        tool = BuildSystem()
        tool._grammars_dir = common
        monkeypatch.setattr(
            tool.platform_support, "detect_platform", lambda: {"compiler": "gcc"}
        )
        ok, info = tool.compile_grammars(["bad", "good"], "linux", tmp_path / "out")
        assert ok
        assert info["libraries"]["combined"]
        assert any("bad" in error for error in info["errors"])
    assert len(calls) == 1
    assert Path(calls[0][0]).is_absolute()


@pytest.mark.parametrize("label", ["unknown", "windows", "macos"])
def test_platform_label_declines_before_detection(tmp_path, monkeypatch, label):
    monkeypatch.setattr(sys, "platform", "linux")
    tool = BuildSystem()
    monkeypatch.setattr(
        tool.platform_support,
        "detect_platform",
        lambda: pytest.fail("detector reached"),
    )
    ok, info = tool.compile_grammars([], label, tmp_path)
    assert not ok
    assert info["compiler"] is None
    assert info["libraries"] == {}
    assert info["errors"]


@pytest.mark.parametrize("kind", ["manager", "combined", "platform"])
def test_combined_link_failure_fails_all(tmp_path, monkeypatch, kind):
    from chunker.grammar_manager import GrammarManager

    common = tmp_path / "grammars"
    for lang in ("a", "b"):
        src = common / f"tree-sitter-{lang}" / "src"
        src.mkdir(parents=True)
        (src / "parser.c").touch()
    monkeypatch.setattr("shutil.which", lambda name: "tools/gcc")
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **kw: SimpleNamespace(returncode=1, stderr="duplicate symbol"),
    )
    if kind == "manager":
        assert GrammarManager(tmp_path).compile_grammars(["a", "b"]) == {
            "a": False,
            "b": False,
        }
    elif kind == "combined":
        tool = TreeSitterGrammarBuilder()
        tool.set_source_directory(common)
        tool.set_build_directory(tmp_path / "out")
        assert tool.build(["a", "b"]) == {"a": False, "b": False}
    else:
        monkeypatch.setattr(sys, "platform", "linux")
        tool = BuildSystem()
        tool._grammars_dir = common
        monkeypatch.setattr(
            tool.platform_support, "detect_platform", lambda: {"compiler": "gcc"}
        )
        ok, info = tool.compile_grammars(["a", "b"], "linux", tmp_path / "out")
        assert not ok
        assert info["libraries"] == {}
        assert any("every requested member" in e for e in info["errors"])


@pytest.mark.parametrize("suffix", ["cc", "cpp"])
def test_direct_controlled_helper_declines_cxx(tmp_path, monkeypatch, suffix):
    from chunker.grammar_management import _build_recipe

    src = tmp_path / "src"
    src.mkdir()
    (src / "parser.c").touch()
    (src / f"scanner.{suffix}").touch()
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **kw: pytest.fail("controlled C++ must launch zero processes"),
    )
    with pytest.raises(ValueError, match=r"C\+\+ scanner"):
        _build_recipe.individual_c_argv("/compiler", tmp_path, tmp_path / "out.so")


def test_downloader_scanner_priority_and_missing_explicit_cc(tmp_path, monkeypatch):
    from chunker.grammar_management import _build_tools

    src = tmp_path / "grammar" / "src"
    src.mkdir(parents=True)
    for name in ("parser.c", "scanner.c", "scanner.cc"):
        (src / name).touch()
    monkeypatch.setenv("CC", "one executable with spaces")
    lookups = []
    monkeypatch.setattr(_build_tools, "resolve_tool", lookups.append)
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: pytest.fail("no fallback"))
    result = GrammarDownloadManager(tmp_path / "cache").compile_grammar(
        src.parent, tmp_path / "out"
    )
    assert not result.success
    assert lookups == ["one executable with spaces"]


@pytest.mark.parametrize(
    "operation", ["install-existing", "install-new", "update", "current", "info"]
)
@pytest.mark.parametrize("package", [True, False])
def test_user_tools_parent_resolution(tmp_path, monkeypatch, operation, package):
    from chunker._internal.user_grammar_tools import UserGrammarTools
    from chunker.grammar_management import _build_tools

    common = tmp_path / "grammars"
    root = common / "tree-sitter-repro"
    root.mkdir(parents=True)
    for name in ("git", "npm", "tree-sitter"):
        (root / name).write_text("decoy", encoding="utf-8")
    if package:
        (root / "package.json").write_text("{}", encoding="utf-8")
    tool = UserGrammarTools(tmp_path / "out", common)
    monkeypatch.setattr(tool, "_refuse_shipped_target", lambda *args: False)
    health = SimpleNamespace(status="healthy")
    monkeypatch.setattr(
        tool.manager, "diagnose_grammar_issues", lambda language: health
    )
    monkeypatch.setattr(tool.manager, "get_grammar_compatibility", lambda language: {})
    lookups = []
    calls = []

    def which(name):
        lookups.append(name)
        return f"parent-bin/{name}"

    def run(argv, **kwargs):
        calls.append((argv, kwargs))
        assert Path(argv[0]).is_absolute(), "clone-cwd executable must be absolute"
        assert argv[0] == str(Path(f"parent-bin/{Path(argv[0]).name}").absolute())
        stdout = (
            "https://github.com/example/repro"
            if argv[1:3] == ["remote", "get-url"]
            else "old"
        )
        if argv[1:] == ["rev-parse", "origin/main"] and operation != "current":
            stdout = "new"
        if argv[1] == "clone":
            root.mkdir(parents=True)
            if package:
                (root / "package.json").write_text("{}", encoding="utf-8")
        return SimpleNamespace(returncode=0, stdout=stdout, stderr="")

    monkeypatch.setattr(_build_tools.shutil, "which", which)
    monkeypatch.setattr(subprocess, "run", run)
    if operation == "install-new":
        import shutil

        shutil.rmtree(root)
    if operation.startswith("install"):
        result = tool.install_grammar("repro", "https://github.com/example/repro")
        expected_git = (
            [
                [
                    "clone",
                    "--branch",
                    "main",
                    "--",
                    "https://github.com/example/repro",
                    str(root),
                ]
            ]
            if operation == "install-new"
            else [
                [
                    "remote",
                    "set-url",
                    "origin",
                    "--",
                    "https://github.com/example/repro",
                ],
                ["fetch", "origin"],
                ["checkout", "--detach", "main"],
            ]
        )
        assert result["errors"] == ["No .so files found after generation"]
    elif operation in {"update", "current"}:
        tool.update_grammar("repro")
        expected_git = [
            ["remote", "get-url", "origin"],
            ["fetch", "origin"],
            ["rev-parse", "HEAD"],
            ["rev-parse", "origin/main"],
        ]
        if operation == "update":
            expected_git.append(["checkout", "--detach", "origin/main"])
    else:
        tool.get_grammar_info("repro")
        expected_git = [["log", "--oneline", "-1"], ["remote", "get-url", "origin"]]
    assert [
        argv[1:] for argv, _ in calls if Path(argv[0]).name == "git"
    ] == expected_git
    expected_tools = ["git"]
    if operation not in {"current", "info"}:
        if package:
            expected_tools.append("npm")
        expected_tools.append("tree-sitter")
    assert lookups == expected_tools, "each used tool resolved exactly once"
    for argv, kwargs in calls:
        if argv[1] != "clone":
            assert kwargs["cwd"] == root
    assert [argv[1:] for argv, _ in calls if Path(argv[0]).name == "npm"] == (
        [["install"]] if "npm" in expected_tools else []
    )
    assert [argv[1:] for argv, _ in calls if Path(argv[0]).name == "tree-sitter"] == (
        [["generate"]] if "tree-sitter" in expected_tools else []
    )


@pytest.mark.parametrize("scanner", [None, "cc", "cpp"])
def test_cli_pregenerated_needs_no_node_or_generator(
    tmp_path, monkeypatch, scanner, capsys
):
    from chunker.grammar_management.cli import ComprehensiveGrammarCLI
    from chunker.grammar_management import _build_tools

    tool = ComprehensiveGrammarCLI(tmp_path)
    root = tool.user_grammars_dir / "repro"
    src = root / "src"
    src.mkdir(parents=True)
    (src / "parser.c").touch()
    if scanner:
        (src / f"scanner.{scanner}").touch()
    lookups = []
    monkeypatch.setattr(
        _build_tools,
        "resolve_tool",
        lambda name: lookups.append(name)
        or (str(tmp_path / "gcc") if name == "gcc" else None),
    )
    calls = []

    def run(argv, **kwargs):
        calls.append(argv)
        assert "-shared" in argv
        assert kwargs["cwd"] == root.absolute()
        Path(argv[argv.index("-o") + 1]).write_bytes(b"built")
        return 0, "", ""

    monkeypatch.setattr(tool, "_run_command", run)
    assert tool.build_grammar("repro", force=True) == (1 if scanner else 0)
    if scanner:
        assert not calls
        assert "C++ scanner" in capsys.readouterr().out
    else:
        assert len(calls) == 1
        assert lookups == ["gcc"]
        assert "-std=c99" in calls[0]
        assert "built, not admitted" in capsys.readouterr().out


@pytest.mark.parametrize("kind", ["individual", "download"])
def test_controlled_failure_never_retries_legacy(tmp_path, monkeypatch, kind):
    root = tmp_path / "g" / "tree-sitter-repro"
    (root / "src").mkdir(parents=True)
    (root / "src" / "parser.c").touch()
    calls = []
    monkeypatch.setattr("shutil.which", lambda name: str(tmp_path / "cc"))

    def run(argv, **kwargs):
        calls.append(argv)
        assert Path(argv[0]).is_absolute()
        return SimpleNamespace(returncode=1, stderr="undefined symbol")

    monkeypatch.setattr(subprocess, "run", run)
    if kind == "individual":
        tool = TreeSitterGrammarBuilder()
        tool.set_source_directory(root.parent)
        tool.set_build_directory(tmp_path / "out")
        assert not tool.build_individual("repro")
    else:
        assert (
            not GrammarDownloadManager(tmp_path / "cache")
            .compile_grammar(root, tmp_path / "out")
            .success
        )
    assert len(calls) == 1, "controlled failure must never retry legacy compilation"


@pytest.mark.parametrize(
    "component", ["repository", "grammars", "ocaml", "src", "parser.c"]
)
@pytest.mark.parametrize("dangling", [False, True])
def test_individual_mapped_symlink_has_no_process(
    tmp_path, monkeypatch, component, dangling
):
    import shutil
    from tests.test_reproducible_grammar_build import _policy_required

    common = tmp_path / "g"
    repo = common / "tree-sitter-ocaml"
    root = repo / "grammars" / "ocaml"
    (root / "src").mkdir(parents=True)
    (root / "src" / "parser.c").touch()
    target = {
        "repository": repo,
        "grammars": repo / "grammars",
        "ocaml": root,
        "src": root / "src",
        "parser.c": root / "src" / "parser.c",
    }[component]
    backing = tmp_path / "backing"
    target.rename(backing)
    if dangling:
        if backing.is_dir():
            shutil.rmtree(backing)
        else:
            backing.unlink()
    try:
        target.symlink_to(backing, target_is_directory=component != "parser.c")
    except OSError as error:
        if _policy_required():
            pytest.fail(f"Required symlink unavailable: {error}")
        pytest.skip(f"Symlink unavailable: {error}")
    tool = TreeSitterGrammarBuilder()
    tool.set_source_directory(common)
    tool.set_build_directory(tmp_path / "out")
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: pytest.fail("symlink must not compile or generate"),
    )
    assert not tool.build_individual("ocaml")


def test_cli_generation_is_resolved_once(tmp_path, monkeypatch, capsys):
    from chunker.grammar_management.cli import ComprehensiveGrammarCLI
    from chunker.grammar_management import _build_tools

    tool = ComprehensiveGrammarCLI(tmp_path)
    root = tool.user_grammars_dir / "repro"
    root.mkdir(parents=True)
    calls = []
    lookups = []
    monkeypatch.setattr(
        _build_tools,
        "resolve_tool",
        lambda name: lookups.append(name) or str(tmp_path / name),
    )

    def run(argv, **kwargs):
        calls.append(argv)
        if argv[1:] == ["generate"]:
            (root / "src").mkdir()
            (root / "src" / "parser.c").touch()
        else:
            assert "-shared" in argv
            Path(argv[argv.index("-o") + 1]).write_bytes(b"built")
        return 0, "", ""

    monkeypatch.setattr(tool, "_run_command", run)
    assert tool.build_grammar("repro", force=True) == 0
    assert lookups == ["tree-sitter", "gcc"]
    assert calls[0] == [str(tmp_path / "tree-sitter"), "generate"]
    assert len(calls) == 2


def test_smart_manager_git_log_parent_resolution(tmp_path, monkeypatch):
    from chunker._internal.grammar_management import SmartGrammarManager
    from chunker.grammar_management import _build_tools

    common = tmp_path / "grammars"
    root = common / "tree-sitter-repro"
    root.mkdir(parents=True)
    (root / "git").touch()
    lookups = []
    calls = []
    monkeypatch.setattr(
        _build_tools.shutil,
        "which",
        lambda name: lookups.append(name) or "parent-bin/git",
    )

    def run(argv, **kwargs):
        calls.append((argv, kwargs))
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", run)
    health = SmartGrammarManager(tmp_path / "out", common).diagnose_grammar_issues(
        "repro"
    )
    assert lookups == ["git"]
    assert calls[0][0] == [
        str(Path("parent-bin/git").absolute()),
        "log",
        "--oneline",
        "-1",
    ]
    assert calls[0][1]["cwd"] == root
    assert calls[0][1]["timeout"] == 10
    assert "Grammar source repository is available" in health.recommendations


@pytest.mark.parametrize("kind", ["manager", "combined"])
def test_all_excluded_combined_zero_process(tmp_path, monkeypatch, kind):
    from chunker.grammar_manager import GrammarManager

    src = tmp_path / "grammars" / "tree-sitter-bad" / "src"
    src.mkdir(parents=True)
    (src / "parser.c").touch()
    (src / "scanner.cc").touch()
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **kw: pytest.fail("no accepted members must not probe or compile"),
    )
    monkeypatch.setattr(
        "shutil.which", lambda *a: pytest.fail("no compiler lookup needed")
    )
    if kind == "manager":
        tool = GrammarManager(tmp_path)
        assert tool.compile_grammars(["missing", "bad"]) == {"bad": False}
        assert tool.compile_grammars(["missing"]) == {}
    else:
        tool = TreeSitterGrammarBuilder()
        tool.set_source_directory(tmp_path / "grammars")
        assert tool.build(["missing", "bad"]) == {"missing": False, "bad": False}


def test_combined_source_and_include_order(tmp_path, monkeypatch):
    from chunker.grammar_management import _build_recipe

    common = tmp_path / "g"
    for language in ("zeta", "repro"):
        src = common / f"tree-sitter-{language}" / "src"
        src.mkdir(parents=True)
        for name in ("z.c", "scanner.c", "parser.c", "a.c"):
            (src / name).touch()
        (src.parent / "root.c").touch()
    accepted, sources, includes, errors = _build_recipe.combined_sources(
        common, ["zeta", "repro", "repro"], "root"
    )
    assert accepted == ["repro", "zeta"]
    assert sources == sorted(set(sources)), "sources must be sorted and deduplicated"
    assert includes == sorted(set(includes)), "includes must be sorted and deduplicated"
    assert len(sources) == 10
    assert not errors


def test_wheel_language_selection_is_sorted(tmp_path, monkeypatch):
    tool = BuildSystem()
    names = {f"grammar{i}" for i in range(30)}
    calls = []
    monkeypatch.delenv("CHUNKER_WHEEL_LANGS", raising=False)
    monkeypatch.setattr(tool, "_get_available_languages", lambda: names)
    monkeypatch.setattr(
        tool.platform_support, "detect_platform", lambda: {"platform_tag": "fixture"}
    )

    def compile_grammars(languages, platform, output):
        calls.append(languages)
        return False, {"errors": ["selection only"]}

    monkeypatch.setattr(tool, "compile_grammars", compile_grammars)
    assert not tool.build_wheel("linux", "cp314", tmp_path)[0]
    assert calls == [sorted(names)[:3]], "wheel selection must sort before slicing"


def test_installer_git_resolved_once_across_clone_checkout_and_commit(
    tmp_path, monkeypatch
):
    from chunker.grammar_management import _build_tools, _transactions
    from chunker.grammar_management.core import GrammarInstaller

    tool = GrammarInstaller(cache_dir=tmp_path)
    staging = _transactions.create_staging(tmp_path)
    selection = _build_tools.ToolSelection()
    lookups = []
    calls = []
    monkeypatch.setattr(
        _build_tools.shutil,
        "which",
        lambda name: lookups.append(name) or "parent-bin/git",
    )

    def run(staging, argv, **kwargs):
        calls.append((argv, kwargs))
        return _transactions.StagedRun(0, "commit\n", "", False, True)

    monkeypatch.setattr(tool, "_run_staged", run)
    try:
        ok, source, error = tool._download_grammar(
            "repro",
            "https://github.com/example/repro",
            "v1",
            staging=staging,
            selected_tools=selection,
        )
        assert ok, error
        assert (
            tool._get_commit_hash(source, staging=staging, selected_tools=selection)
            == "commit"
        )
    finally:
        _transactions.discard_staging(staging)
    assert lookups == ["git"]
    assert [argv[0] for argv, _ in calls] == [
        str(Path("parent-bin/git").absolute())
    ] * 3
    assert [argv[1] for argv, _ in calls] == ["clone", "checkout", "rev-parse"]
    assert calls[1][1]["cwd"] == source
    assert calls[2][1]["cwd"] == source


def test_combined_never_uses_obsolete_binding_api(tmp_path, monkeypatch):
    import tree_sitter

    src = tmp_path / "g" / "tree-sitter-repro" / "src"
    src.mkdir(parents=True)
    (src / "parser.c").touch()
    monkeypatch.setattr(
        tree_sitter,
        "Language",
        SimpleNamespace(
            build_library=lambda *a: pytest.fail("obsolete binding API reached")
        ),
    )
    monkeypatch.setattr("shutil.which", lambda name: str(tmp_path / "gcc"))

    def run(argv, **kwargs):
        Path(argv[argv.index("-o") + 1]).touch()
        return SimpleNamespace(returncode=0, stderr="")

    monkeypatch.setattr(subprocess, "run", run)
    tool = TreeSitterGrammarBuilder()
    tool.set_source_directory(src.parent.parent)
    tool.set_build_directory(tmp_path / "out")
    assert tool.build(["repro"]) == {"repro": True}


def test_missing_compiler_fails_required_policy(monkeypatch):
    from tests.test_reproducible_grammar_build import _installer_compiler

    monkeypatch.setenv("CI", "true")
    monkeypatch.setattr("shutil.which", lambda name: None)
    try:
        with pytest.raises(pytest.fail.Exception, match="CI must provide"):
            _installer_compiler()
    except pytest.skip.Exception:
        pytest.fail("required compiler policy must fail, never skip")


@pytest.mark.parametrize("adapter", ["manager", "download", "platform"])
def test_host_flags_use_actual_basename(tmp_path, monkeypatch, adapter):
    from tests.test_reproducible_grammar_build import _public_adapter

    monkeypatch.setattr(sys, "platform", "darwin")
    commands = []

    def run(argv, **kwargs):
        if "-o" in argv:
            output = Path(argv[argv.index("-o") + 1])
            output.write_bytes(b"built")
            commands.append(argv)
        return SimpleNamespace(returncode=0, stdout="compiler", stderr="")

    monkeypatch.setattr(subprocess, "run", run)
    path = _public_adapter(adapter, tmp_path / "root", monkeypatch)
    assert (
        f"-Wl,-install_name,@rpath/{path.name}" in commands[-1]
    ), "flags must use host and actual basename"
    assert "-Wl,-z,defs" not in commands[-1]

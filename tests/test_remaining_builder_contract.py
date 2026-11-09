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
    monkeypatch.setattr(sys, "platform", "linux")
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


@pytest.mark.parametrize("outcome", [0, 1, "exception"])
def test_individual_legacy_golden(tmp_path, monkeypatch, outcome):
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
        if outcome == "exception":
            raise FileNotFoundError("missing legacy compiler")
        if outcome == 0:
            Path(argv[argv.index("-o") + 1]).write_bytes(b"legacy")
        return SimpleNamespace(returncode=outcome, stderr="legacy error")

    monkeypatch.setattr(subprocess, "run", run)
    if outcome == 1:
        from chunker.grammar.builder import BuildError

        with pytest.raises(BuildError, match="Compilation failed: legacy error"):
            builder.build_individual("repro")
    else:
        assert builder.build_individual("repro") == (outcome == 0)
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
    "excluded",
    ["missing", "no-src", "no-c", "no-parser", "cc", "cpp", "symlink", "dangling"],
)
def test_combined_membership(tmp_path, monkeypatch, builder_kind, excluded):
    from chunker.grammar_manager import GrammarManager
    from tests.test_reproducible_grammar_build import _policy_required

    common = tmp_path / "grammars"
    good = common / "tree-sitter-good" / "src"
    good.mkdir(parents=True)
    (good / "parser.c").write_text("int good;", encoding="utf-8")
    bad = common / "tree-sitter-bad"
    if excluded == "no-src":
        bad.mkdir()
    elif excluded != "missing":
        (bad / "src").mkdir(parents=True)
        if excluded == "no-parser":
            (bad / "src" / "scanner.c").touch()
        if excluded not in {"no-parser", "no-c"}:
            (bad / "src" / "parser.c").write_text("int bad;", encoding="utf-8")
        if excluded in {"cc", "cpp"}:
            (bad / "src" / "scanner.c").touch()
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
@pytest.mark.parametrize("failure", ["nonzero", "exception", "missing-output"])
def test_combined_link_failure_fails_all(tmp_path, monkeypatch, kind, failure):
    from chunker.grammar_manager import GrammarManager

    common = tmp_path / "grammars"
    for lang in ("a", "b"):
        src = common / f"tree-sitter-{lang}" / "src"
        src.mkdir(parents=True)
        (src / "parser.c").touch()
    monkeypatch.setattr("shutil.which", lambda name: "tools/gcc")

    def failed_link(*args, **kwargs):
        if failure == "exception":
            raise RuntimeError("link exception")
        return SimpleNamespace(
            returncode=0 if failure == "missing-output" else 1,
            stderr="duplicate symbol",
        )

    monkeypatch.setattr(subprocess, "run", failed_link)
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
        assert Path(argv[0]).is_absolute(), "every invocation must be parent-resolved"
        assert argv[0] == str(Path(f"parent-bin/{Path(argv[0]).name}").absolute())
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
    ("language", "subdir", "component"),
    [
        (language, subdir, component)
        for language, subdir in [
            ("ocaml", "grammars/ocaml"),
            ("typescript", "typescript"),
            ("tsx", "tsx"),
            ("php", "php"),
            ("wat", "wat"),
        ]
        for component in ("repository", *subdir.split("/"), "src", "parser.c", "root.c")
    ],
)
@pytest.mark.parametrize("dangling", [False, True])
def test_individual_mapped_symlink_has_no_process(
    tmp_path, monkeypatch, language, subdir, component, dangling
):
    import shutil
    from tests.test_reproducible_grammar_build import _policy_required

    common = tmp_path / "g"
    repo = common / f"tree-sitter-{language}"
    root = repo / subdir
    (root / "src").mkdir(parents=True)
    (root / "src" / "parser.c").touch()
    if component == "root.c":
        (root / "extra.c").touch()
    target = {
        "repository": repo,
        **{
            part: repo.joinpath(*subdir.split("/")[: index + 1])
            for index, part in enumerate(subdir.split("/"))
        },
        "src": root / "src",
        "parser.c": root / "src" / "parser.c",
        "root.c": root / "extra.c",
    }[component]
    backing = tmp_path / "backing"
    target.rename(backing)
    if dangling:
        if backing.is_dir():
            shutil.rmtree(backing)
        else:
            backing.unlink()
    try:
        target.symlink_to(
            backing, target_is_directory=component not in {"parser.c", "root.c"}
        )
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
    assert not tool.build_individual(language)


def test_cli_generation_is_resolved_once(tmp_path, monkeypatch):
    from click.testing import CliRunner
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
    with CliRunner().isolation():
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

    from chunker.grammar_management import _build_tools

    monkeypatch.setattr(
        _build_tools, "resolve_tool", lambda name: str(tmp_path / "compiler")
    )
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


@pytest.mark.parametrize("detector", ["unknown", "cl"])
def test_platform_detector_failure_shapes(tmp_path, monkeypatch, detector):
    monkeypatch.setattr(sys, "platform", "linux")
    src = tmp_path / "g" / "tree-sitter-repro" / "src"
    src.mkdir(parents=True)
    (src / "parser.c").touch()
    tool = BuildSystem()
    tool._grammars_dir = src.parent.parent
    monkeypatch.setattr(
        tool.platform_support, "detect_platform", lambda: {"compiler": detector}
    )
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **kw: pytest.fail("unsupported detector must not compile"),
    )
    ok, info = tool.compile_grammars(["repro"], "linux", tmp_path / "out")
    assert not ok
    if detector == "unknown":
        assert info == {"error": "No suitable C compiler found"}
    else:
        assert info["compiler"] is None
        assert info["libraries"] == {}
        assert info["errors"]


def test_matching_windows_keeps_msvc_dispatch(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    src = tmp_path / "g" / "tree-sitter-repro" / "src"
    src.mkdir(parents=True)
    (src / "parser.c").touch()
    tool = BuildSystem()
    tool._grammars_dir = src.parent.parent
    monkeypatch.setattr(
        tool.platform_support, "detect_platform", lambda: {"compiler": "cl"}
    )
    calls = []
    monkeypatch.setattr(
        tool,
        "_compile_windows",
        lambda languages, output, info: calls.append((languages, info["compiler"]))
        or True,
    )
    monkeypatch.setattr(
        tool, "_compile_unix", lambda *a: pytest.fail("MSVC must not reach GNU recipe")
    )
    assert tool.compile_grammars(["repro"], "windows", tmp_path / "out")[0]
    assert calls == [(["repro"], "cl")]


@pytest.mark.parametrize(
    "extra", ["extra.c", "src/extra.c", "unused.cpp", "src/unused.cpp"]
)
@pytest.mark.parametrize("kind", ["individual", "download"])
def test_noncanonical_public_route_is_preselected_legacy(
    tmp_path, monkeypatch, extra, kind
):
    from chunker.grammar_management import _build_recipe

    root = tmp_path / "g" / "tree-sitter-repro"
    (root / "src").mkdir(parents=True)
    (root / "src" / "parser.c").touch()
    (root / extra).touch()
    with pytest.raises(ValueError, match="Noncanonical"):
        _build_recipe.individual_c_argv("/compiler", root, tmp_path / "out.so")
    monkeypatch.setattr(
        _build_recipe,
        "individual_c_argv",
        lambda *a, **kw: pytest.fail("noncanonical input must preselect legacy"),
    )
    calls = []

    def run(argv, **kwargs):
        calls.append(argv)
        Path(argv[argv.index("-o") + 1]).write_bytes(b"legacy")
        return SimpleNamespace(returncode=0, stderr="")

    monkeypatch.setattr(subprocess, "run", run)
    if kind == "individual":
        tool = TreeSitterGrammarBuilder()
        tool.set_source_directory(root.parent)
        tool.set_build_directory(tmp_path / "out")
        assert tool.build_individual("repro")
    else:
        assert (
            GrammarDownloadManager(tmp_path / "cache")
            .compile_grammar(root, tmp_path / "out")
            .success
        )
    assert len(calls) == 1
    assert "-Wl,-z,defs" not in calls[0]


@pytest.mark.parametrize(
    ("operation", "missing"),
    [
        (operation, missing)
        for operation in ("install-existing", "install-new", "update")
        for missing in ("git", "npm", "tree-sitter")
    ]
    + [("info", "git"), ("diagnose", "git")],
)
@pytest.mark.parametrize("failure_source", ["process", "lookup"])
def test_missing_tools_keep_public_error_shapes(
    tmp_path, monkeypatch, operation, missing, failure_source
):
    from chunker._internal.user_grammar_tools import UserGrammarTools
    from chunker.grammar_management import _build_tools

    common = tmp_path / "grammars"
    root = common / "tree-sitter-repro"
    root.mkdir(parents=True)
    (root / "package.json").write_text("{}", encoding="utf-8")
    tool = UserGrammarTools(tmp_path / "out", common)
    monkeypatch.setattr(tool, "_refuse_shipped_target", lambda *a: False)
    if operation != "diagnose":
        monkeypatch.setattr(
            tool.manager,
            "diagnose_grammar_issues",
            lambda *a: SimpleNamespace(status="healthy"),
        )
        monkeypatch.setattr(tool.manager, "get_grammar_compatibility", lambda *a: {})
    lookups = []
    calls = []

    def resolve(name):
        lookups.append(name)
        return (
            None
            if failure_source == "lookup" and name == missing
            else str(tmp_path / name)
        )

    def run(argv, **kwargs):
        calls.append(argv)
        if Path(argv[0]).name == missing:
            raise FileNotFoundError(f"Executable not found: {missing}")
        if argv[1] == "clone":
            root.mkdir(parents=True)
            (root / "package.json").write_text("{}", encoding="utf-8")
        stdout = (
            "https://github.com/example/repro"
            if argv[1:3] == ["remote", "get-url"]
            else "old"
        )
        if argv[1:] == ["rev-parse", "origin/main"]:
            stdout = "new"
        return SimpleNamespace(returncode=0, stdout=stdout, stderr="")

    monkeypatch.setattr(_build_tools, "resolve_tool", resolve)
    monkeypatch.setattr(subprocess, "run", run)
    if operation == "install-new":
        import shutil

        shutil.rmtree(root)
    if operation.startswith("install"):
        result = tool.install_grammar("repro", "https://github.com/example/repro")
        assert result["status"] == "error"
        assert result["errors"] == [
            f"Unexpected error: Executable not found: {missing}"
        ]
    elif operation == "update":
        result = tool.update_grammar("repro")
        assert result["status"] == "error"
        assert result["errors"] == [
            f"Unexpected error during update: Executable not found: {missing}"
        ]
    elif operation == "info":
        assert tool.get_grammar_info("repro")["source_info"] == {
            "error": "Could not retrieve source information"
        }
    else:
        health = tool.manager.diagnose_grammar_issues("repro")
        assert "Could not verify grammar source repository status" in health.issues
    assert lookups.count(missing) == 1
    if failure_source == "lookup":
        assert all(Path(argv[0]).name != missing for argv in calls)


def test_cli_missing_generator_is_actionable_without_process(tmp_path, monkeypatch):
    from click.testing import CliRunner
    from chunker.grammar_management.cli import ComprehensiveGrammarCLI
    from chunker.grammar_management import _build_tools

    tool = ComprehensiveGrammarCLI(tmp_path)
    (tool.user_grammars_dir / "repro").mkdir(parents=True)
    monkeypatch.setattr(_build_tools, "resolve_tool", lambda name: None)
    monkeypatch.setattr(
        tool,
        "_run_command",
        lambda *a, **kw: pytest.fail("missing generator must not start a process"),
    )
    with CliRunner().isolation() as streams:
        assert tool.build_grammar("repro", force=True) != 0
        output = streams[-1].getvalue().decode()
    assert "tree-sitter" in output and "PATH" in output


@pytest.mark.parametrize(
    ("label", "suffix"), [("Linux", ".so"), ("Darwin", ".dylib"), ("Windows", ".dll")]
)
@pytest.mark.parametrize("host", ["linux", "darwin", "win32"])
def test_individual_labels_select_names_but_host_selects_flags(
    tmp_path, monkeypatch, label, suffix, host
):
    from chunker.grammar_management import _build_tools

    monkeypatch.setattr("platform.system", lambda: label)
    monkeypatch.setattr(sys, "platform", host)
    monkeypatch.setattr(
        _build_tools, "resolve_tool", lambda name: str(tmp_path / "compiler")
    )
    source = tmp_path / "grammars" / "tree-sitter-repro" / "src"
    source.mkdir(parents=True)
    (source / "parser.c").touch()
    tool = TreeSitterGrammarBuilder()
    tool.set_source_directory(source.parent.parent)
    tool.set_build_directory(tmp_path / "out")
    calls = []

    def run(argv, **kwargs):
        calls.append(argv)
        Path(argv[argv.index("-o") + 1]).write_bytes(b"built")
        return SimpleNamespace(returncode=0, stderr="")

    monkeypatch.setattr(subprocess, "run", run)
    assert tool.build_individual("repro")
    argv = calls[0]
    assert Path(argv[argv.index("-o") + 1]).name == f"repro{suffix}"
    assert "-std=c11" in argv
    assert ("-Wl,-z,defs" in argv) == (host == "linux")
    assert (f"-Wl,-install_name,@rpath/repro{suffix}" in argv) == (host == "darwin")
    assert ("-Wl,--no-insert-timestamp" in argv) == (host == "win32")
    assert ("-Wl,--disable-auto-image-base" in argv) == (host == "win32")


def _required_symlink(link, target, *, directory=True):
    from tests.test_reproducible_grammar_build import _policy_required

    try:
        link.symlink_to(target, target_is_directory=directory)
    except OSError as error:
        if _policy_required():
            pytest.fail(f"Required symlink unavailable: {error}")
        pytest.skip(f"Symlink unavailable: {error}")


_SCOPE_ADAPTERS = [
    "individual",
    "individual-mapped",
    "download",
    "cli",
    "manager",
    "combined",
]
if sys.platform in {"linux", "darwin"}:
    _SCOPE_ADAPTERS.append("platform")


@pytest.mark.parametrize("adapter", _SCOPE_ADAPTERS)
def test_symlinked_ancestor_builds_equal_bytes(tmp_path, monkeypatch, adapter):
    from hashlib import sha256
    from tests.test_reproducible_grammar_build import _public_adapter

    real = tmp_path.resolve() / "real"
    real.mkdir()
    link = tmp_path.resolve() / "link"
    _required_symlink(link, real)
    paths = [
        _public_adapter(adapter, root, monkeypatch)
        for root in (real / "a", link / "bb" / "c")
    ]
    digests = [sha256(path.read_bytes()).hexdigest() for path in paths]
    assert digests[0] == digests[1], "ancestor alias must preserve raw SHA-256"
    print(f"ancestor {adapter} raw_sha256={digests}")


if sys.platform == "darwin":

    def test_macos_unresolved_system_alias_builds(tmp_path, monkeypatch):
        from hashlib import sha256
        from tests.test_reproducible_grammar_build import _public_adapter

        real = tmp_path.resolve()
        assert str(real).startswith(("/private/var/", "/private/tmp/"))
        alias = Path(str(real).removeprefix("/private"))
        assert alias != real and alias.resolve() == real
        paths = [
            _public_adapter("individual", root, monkeypatch)
            for root in (real / "a", alias / "bb" / "c")
        ]
        digests = [sha256(path.read_bytes()).hexdigest() for path in paths]
        assert (
            digests[0] == digests[1]
        ), "macOS /var or /tmp alias must build equal bytes"
        print(f"macOS unresolved alias={alias} raw_sha256={digests}")


@pytest.mark.parametrize(
    "adapter", ["cli", "download", "individual", "manager", "combined", "platform"]
)
@pytest.mark.parametrize("position", ["clone", "src", "parser.c", "root.c"])
@pytest.mark.parametrize("dangling", [False, True])
def test_in_span_link_never_starts_process(
    tmp_path, monkeypatch, adapter, position, dangling
):
    import shutil
    from click.testing import CliRunner
    from chunker.grammar_management.cli import ComprehensiveGrammarCLI
    from chunker.grammar_manager import GrammarManager

    root = tmp_path / "g" / "tree-sitter-repro"
    (root / "src").mkdir(parents=True)
    (root / "src" / "parser.c").touch()
    if position == "root.c":
        (root / "extra.c").touch()
    target = {
        "clone": root,
        "src": root / "src",
        "parser.c": root / "src" / "parser.c",
        "root.c": root / "extra.c",
    }[position]
    backing = tmp_path / "backing"
    target.rename(backing)
    directory = backing.is_dir()
    if dangling:
        if directory:
            shutil.rmtree(backing)
        else:
            backing.unlink()
    _required_symlink(target, backing, directory=directory)
    calls = []

    def unexpected(*args, **kwargs):
        calls.append(args)
        pytest.fail("in-span link must not probe, compile, generate, or retry legacy")

    monkeypatch.setattr(subprocess, "run", unexpected)
    output = tmp_path / "out"
    if adapter == "individual":
        tool = TreeSitterGrammarBuilder()
        tool.set_source_directory(root.parent)
        tool.set_build_directory(output)
        assert not tool.build_individual("repro")
    elif adapter == "download":
        assert (
            not GrammarDownloadManager(tmp_path / "cache")
            .compile_grammar(root, output)
            .success
        )
    elif adapter == "cli":
        tool = ComprehensiveGrammarCLI(tmp_path / "cache")
        monkeypatch.setattr(
            tool, "_get_grammar_priority_order", lambda: [(root.parent, None, None)]
        )
        monkeypatch.setattr(tool, "_run_command", unexpected)
        with CliRunner().isolation():
            assert tool.build_grammar(root.name, force=True) != 0
    elif adapter == "manager":
        tool = GrammarManager(tmp_path)
        tool._grammars_dir = root.parent
        assert tool.compile_grammars(["repro"]) == {"repro": False}
    elif adapter == "combined":
        tool = TreeSitterGrammarBuilder()
        tool.set_source_directory(root.parent)
        assert tool.build(["repro"]) == {"repro": False}
    else:
        # This is the controlled Unix preflight, also tested without processes on Windows.
        monkeypatch.setattr(sys, "platform", "linux")
        tool = BuildSystem()
        tool._grammars_dir = root.parent
        monkeypatch.setattr(tool.platform_support, "detect_platform", unexpected)
        ok, info = tool.compile_grammars(["repro"], "linux", output)
        assert not ok and not info["libraries"] and info["errors"]
    assert not calls, "in-span links must fail before any process"


@pytest.mark.parametrize("component", ["clone", "grammars", "lang"])
@pytest.mark.parametrize("dangling", [False, True])
def test_direct_helper_checks_explicit_clone_span(tmp_path, component, dangling):
    import shutil
    from chunker.grammar_management import _build_recipe

    clone = tmp_path / "clone"
    root = clone / "grammars" / "ocaml"
    (root / "src").mkdir(parents=True)
    (root / "src" / "parser.c").touch()
    target = {"clone": clone, "grammars": clone / "grammars", "lang": root}[component]
    backing = tmp_path / "backing"
    target.rename(backing)
    if dangling:
        shutil.rmtree(backing)
    _required_symlink(target, backing)
    with pytest.raises(ValueError, match="Symlinked|not found"):
        _build_recipe.individual_c_argv(
            "/compiler", root, tmp_path / "out.so", base=clone
        )


@pytest.mark.parametrize("detector", ["cl", "unknown"])
def test_msvc_receives_full_requested_list_without_preflight(
    tmp_path, monkeypatch, detector
):
    from chunker.grammar_management import _build_recipe

    common = tmp_path / "grammars"
    (common / "tree-sitter-cpp" / "src").mkdir(parents=True)
    (common / "tree-sitter-cpp" / "src" / "scanner.cc").touch()
    _required_symlink(common / "tree-sitter-linked", common / "tree-sitter-cpp")
    ancestor = tmp_path / "linked-common"
    _required_symlink(ancestor, common)
    requested = ["cpp", "linked", "missing", "cpp"]
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(
        _build_recipe,
        "combined_sources",
        lambda *a: pytest.fail("MSVC must not use GNU preflight"),
    )
    tool = BuildSystem()
    tool._grammars_dir = ancestor
    monkeypatch.setattr(
        tool.platform_support, "detect_platform", lambda: {"compiler": detector}
    )
    calls = []

    def compile_windows(languages, output, info):
        assert languages is requested
        assert info["errors"] == []
        calls.append(languages)
        return True

    monkeypatch.setattr(tool, "_compile_windows", compile_windows)
    ok, info = tool.compile_grammars(requested, "windows", tmp_path / "out")
    if detector == "unknown":
        assert not ok and info == {"error": "No suitable C compiler found"}
        assert calls == []
    else:
        assert ok and calls == [requested]


def test_combined_creates_default_build_directory(tmp_path, monkeypatch):
    from tests.test_reproducible_grammar_build import _installer_compiler

    _installer_compiler()
    monkeypatch.chdir(tmp_path.resolve())
    src = Path("grammars/tree-sitter-repro/src")
    src.mkdir(parents=True)
    (src / "parser.c").write_text(
        "int tree_sitter_repro(void) { return 1; }", encoding="utf-8"
    )
    tool = TreeSitterGrammarBuilder()
    assert tool.build(["missing"]) == {"missing": False}
    assert not Path("build").exists()
    assert tool.build(["repro"]) == {"repro": True}
    assert (Path("build") / f"languages{tool._lib_extension}").is_file()


@pytest.mark.parametrize("adapter", ["individual", "download"])
def test_scanner_only_keeps_legacy_command(tmp_path, monkeypatch, adapter):
    from chunker.grammar_management import _build_recipe

    root = tmp_path / "g" / "tree-sitter-repro"
    (root / "src").mkdir(parents=True)
    scanner = root / "src" / "scanner.c"
    scanner.touch()
    monkeypatch.setattr(
        _build_recipe,
        "individual_c_argv",
        lambda *a, **kw: pytest.fail("scanner-only must preselect legacy"),
    )
    monkeypatch.setattr("shutil.which", lambda name: str(tmp_path / name))
    monkeypatch.setenv("CC", "legacy-cc")
    calls = []

    def run(argv, **kwargs):
        calls.append((argv, kwargs))
        Path(argv[argv.index("-o") + 1]).write_bytes(b"legacy")
        return SimpleNamespace(returncode=0, stderr="")

    monkeypatch.setattr(subprocess, "run", run)
    output = tmp_path / "out"
    if adapter == "individual":
        tool = TreeSitterGrammarBuilder()
        tool.set_source_directory(root.parent)
        tool.set_build_directory(output)
        assert tool.build_individual("repro")
        expected = ["clang", "-shared"] + ([] if sys.platform == "win32" else ["-fPIC"])
        expected += [
            "-O2",
            "-o",
            str(output / f"repro{tool._lib_extension}"),
            str(scanner),
            "-std=c11",
        ]
        assert "cwd" not in calls[0][1]
    else:
        assert (
            GrammarDownloadManager(tmp_path / "cache")
            .compile_grammar(root, output)
            .success
        )
        expected = ["legacy-cc", "-fPIC", "-shared"] + (
            ["-dynamiclib"] if sys.platform == "darwin" else []
        )
        expected += ["-o", str(output / "tree.so"), str(scanner)]
        assert calls[0][1]["cwd"] == str(root)
    assert len(calls) == 1 and calls[0][0] == expected


def test_direct_helper_rejects_escape_before_inspecting_paths(tmp_path, monkeypatch):
    from chunker.grammar_management import _build_recipe

    clone = tmp_path / "clone"
    root = clone / ".." / "outside"
    monkeypatch.setattr(
        Path,
        "lstat",
        lambda *a, **kw: pytest.fail("escaping span must not inspect paths"),
    )
    with pytest.raises(ValueError, match="outside clone root"):
        _build_recipe.individual_c_argv(
            "/compiler", root, tmp_path / "out.so", base=clone
        )

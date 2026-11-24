"""Repository-scoped ignore decisions, compared with Git on real entries."""

import os
import subprocess
import warnings
from pathlib import Path

import pytest

from chunker.repo import GitignoreMatcher, load_gitignore_patterns
from chunker.repo.git_aware import GitAwareProcessorImpl
from chunker.repo.patterns import GitignorePattern
from chunker.repo.processor import RepoProcessor

SCENARIOS = [
    (
        "escaped-separator",
        {"pkg": [r"a\/b", r"z\\/c", r"\/unanchored", r"trailing\/"]},
        ["a/b/file.py", "deep/a/b/file.py", "z/c", "unanchored", "trailing/file.py"],
    ),
    ("all", {"pkg": ["*", "!keep.py"]}, ["keep.py", "other.py"]),
    ("anchor", {"pkg": ["/generated.py"]}, ["generated.py", "hand.py"]),
    ("basename", {"pkg": ["generated.py"]}, ["generated.py", "hand.py"]),
    ("internal-slash", {"pkg": ["lib/output.py"]}, ["lib/output.py", "output.py"]),
    ("dir", {"pkg": ["build/"]}, ["build/x.py", "plain/build"]),
    (
        "globstar",
        {"pkg": ["src/**/auto?.py", "**/trace.log", "out/**"]},
        [
            "src/auto1.py",
            "src/a/auto2.py",
            "src/a/b/auto3.py",
            "src/auto11.py",
            "trace.log",
            "out/x.py",
        ],
    ),
    (
        "line-syntax",
        {"pkg": ["/", "!", "dangling\\", " leading.py", "#x", "/hit.py"]},
        [" leading.py", "leading.py", "hit.py", "miss.py"],
    ),
    (
        "escape",
        {"pkg": [r"\#source.py", r"\!source.py", r"lit\[1\].py", r"a\ b.py", "# skip"]},
        ["#source.py", "!source.py", "lit[1].py", "lit1.py", "a b.py"],
    ),
    (
        "override",
        {
            "": ["*.log"],
            "pkg": ["!keep.log", "/keep.log"],
            "pkg/deep": ["/keep.log", "!/keep.log"],
        },
        ["keep.log", "other.log"],
    ),
    (
        "excluded-parent",
        {"": ["pkg/hidden/", "!pkg/hidden/keep.py"], "pkg/hidden": ["!keep.py"]},
        ["hidden/keep.py", "visible/keep.py"],
    ),
    (
        "reopened",
        {"pkg": ["blocked/", "!blocked/", "blocked/*", "!blocked/open/"]},
        ["blocked/closed.py", "blocked/open/keep.py"],
    ),
    (
        "siblings",
        {"pkg": ["only.py"], "pkg2": ["other.py"], "pkg/deep": ["!only.py"]},
        ["only.py", "other.py"],
    ),
]
SCOPES = ["", "pkg", "pkg/deep", "pkg/deep/leaf", "pkg2", "other/pkg"]


def git_ignored(root, paths):
    git = [
        "git",
        "-C",
        str(root),
        "-c",
        "core.ignoreCase=false",
        "-c",
        f"core.excludesFile={os.devnull}",
    ]
    env = {**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull}
    subprocess.run([*git, "init", "-q", "--template="], env=env, check=True)
    probe = subprocess.run(
        [*git, "check-ignore", "--no-index", "--stdin", "-z"],
        env=env,
        input=b"".join(p.as_posix().encode() + b"\0" for p in paths),
        capture_output=True,
    )
    assert probe.returncode in (0, 1), probe.stderr
    return {Path(p.decode()) for p in probe.stdout.split(b"\0") if p}


@pytest.mark.parametrize("eol", ["\n", "\r\n"], ids=["lf", "crlf"])
@pytest.mark.parametrize(
    ("name", "files", "stems"), SCENARIOS, ids=[case[0] for case in SCENARIOS]
)
def test_git_membership(tmp_path, eol, name, files, stems):
    for scope in sorted(files, key=lambda p: len(Path(p).parts), reverse=True):
        directory = tmp_path / scope
        directory.mkdir(parents=True, exist_ok=True)
        (directory / ".gitignore").write_bytes((eol.join(files[scope]) + eol).encode())
    paths = {}
    for scope in SCOPES:
        for stem in stems:
            rel = Path(scope, stem)
            (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
            (tmp_path / rel).touch()
            paths[rel] = False
            paths.update((p, True) for p in rel.parents if p.parts)
    ignored = git_ignored(tmp_path, paths)
    matcher = load_gitignore_patterns(tmp_path)
    processor = GitAwareProcessorImpl()
    for rel, directory in paths.items():
        expected = rel in ignored
        context = (name, rel, directory, files, expected)
        assert matcher.should_ignore(rel, directory) == expected, context
        assert matcher.should_ignore(tmp_path / rel, directory) == expected, context
        if not directory:
            assert processor.should_process_file(
                str(tmp_path / rel), str(tmp_path)
            ) == (not expected), context
    survivors = [p for p in paths if p not in ignored]
    assert matcher.filter_paths(list(paths)) == survivors
    assert matcher.filter_paths([tmp_path / p for p in paths]) == [
        tmp_path / p for p in survivors
    ]


def test_anchored_rule_and_plain_processor(tmp_path):
    paths = [
        "generated.py",
        "pkg/generated.py",
        "pkg/deep/generated.py",
        "pkg2/generated.py",
    ]
    for rel in paths:
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).touch()
    (tmp_path / "pkg/.gitignore").write_text("/generated.py\n", encoding="utf-8")
    matcher = load_gitignore_patterns(tmp_path)
    assert not matcher.should_ignore("generated.py")
    assert matcher.should_ignore("pkg/generated.py")
    assert not matcher.should_ignore("pkg/deep/generated.py")
    assert not matcher.should_ignore("pkg2/generated.py")
    assert set(RepoProcessor().get_processable_files(str(tmp_path))) == {
        tmp_path / p for p in paths
    }


@pytest.mark.skipif(
    os.name == "nt",
    reason="POSIX permits trailing whitespace and newlines in filenames",
)
def test_posix_rule_whitespace(tmp_path):
    (tmp_path / ".gitignore").write_bytes(b"thing\\  \nplain.py\n**/match.py\ntab\t\n")
    paths = [
        Path(p)
        for p in (
            "thing ",
            "thing",
            "plain.py\n",
            "line\nbreak/match.py",
            "tab\t",
            "tab",
        )
    ]
    for p in paths:
        (tmp_path / p).parent.mkdir(exist_ok=True)
        (tmp_path / p).touch()
    ignored = git_ignored(tmp_path, paths)
    matcher = load_gitignore_patterns(tmp_path)
    assert {p for p in paths if matcher.should_ignore(p)} == ignored


def test_updates_directory_types_and_relative_root(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    root = Path("repo")
    pkg = root / "pkg"
    (pkg / "cache").mkdir(parents=True)
    rules = pkg / ".gitignore"
    rules.write_text("/cache/  \n", encoding="utf-8-sig")
    matcher = load_gitignore_patterns(root)
    entry = Path("pkg/cache")
    assert matcher.should_ignore(entry, True)
    assert not matcher.should_ignore(entry)
    assert matcher.filter_paths([entry]) == []
    assert matcher.filter_paths([entry], check_is_dir=False) == [entry]
    leaf = entry / "source.py"
    assert matcher.should_ignore(leaf)
    matcher.add_patterns(["!cache/"], pkg)
    assert not matcher.should_ignore(tmp_path / root / leaf)
    rules.write_text("cache/\n", encoding="utf-8")
    matcher.load_gitignore_file(rules)
    assert matcher.should_ignore(leaf)
    assert not matcher.should_ignore(tmp_path / "elsewhere.pyc")
    assert matcher.should_ignore("example.pyc")
    assert not matcher.should_ignore("ordinary.py")
    matcher.add_patterns(["only.py"])
    assert matcher.should_ignore("only.py")
    assert not matcher.should_ignore("ONLY.PY")


def test_order_and_processor_refresh(tmp_path):
    matcher = GitignoreMatcher(["!*.pyc"], tmp_path)
    assert matcher.should_ignore("a.pyc")
    matcher.add_patterns(["!a.pyc"])
    assert not matcher.should_ignore("a.pyc")
    assert [r.original for r in matcher.patterns][0] == "!*.pyc"
    assert matcher.patterns[-1].original == "!a.pyc"
    processor = GitAwareProcessorImpl()
    processor.should_process_file("a.py", str(tmp_path))
    (tmp_path / ".gitignore").write_text("a.py", encoding="utf-8")
    processor.clear_cache()
    assert not processor.should_process_file("a.py", str(tmp_path))


def test_ignored_directory_pruned_before_loading_rules(tmp_path, monkeypatch):
    (tmp_path / ".gitignore").write_text(
        "hidden/\nvisible/\n!visible/\n", encoding="utf-8"
    )
    for name in ("visible", "hidden"):
        (tmp_path / name).mkdir()
        (tmp_path / name / ".gitignore").write_text("example.py", encoding="utf-8")
    loads = []
    original = GitignoreMatcher.load_gitignore_file

    def record(matcher, path):
        loads.append(path)
        original(matcher, path)

    monkeypatch.setattr(GitignoreMatcher, "load_gitignore_file", record)
    load_gitignore_patterns(tmp_path)
    assert loads == [tmp_path / ".gitignore", tmp_path / "visible/.gitignore"]


def test_symlink_discovery(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    other = tmp_path / "other"
    other.mkdir()
    (other / ".gitignore").write_text("canary.py\n", encoding="utf-8")
    try:
        (repo / ".gitignore").symlink_to(other / ".gitignore")
        (repo / "link").symlink_to(other, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symlinks unavailable: {exc}")
    matcher = load_gitignore_patterns(repo)
    assert not matcher.should_ignore("canary.py")
    assert not matcher.should_ignore("link/canary.py")


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="requires POSIX FIFO")
def test_fifo_rule_file_is_never_opened(tmp_path, monkeypatch):
    fifo = tmp_path / ".gitignore"
    os.mkfifo(fifo)
    original = Path.open

    def guarded_open(path, *args, **kwargs):
        assert path != fifo, "discovery tried to read a FIFO"
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded_open)
    assert not load_gitignore_patterns(tmp_path).should_ignore("canary.py")


def test_cached_ancestor_decisions(tmp_path, monkeypatch):
    calls = []
    original = GitignorePattern.matches

    def record(rule, path, is_dir=False):
        calls.append(path)
        return original(rule, path, is_dir)

    monkeypatch.setattr(GitignorePattern, "matches", record)
    matcher = GitignoreMatcher(base_dir=tmp_path)
    assert not matcher.should_ignore("deep/dir/one.py")
    calls.clear()
    assert not matcher.should_ignore("deep/dir/two.py")
    assert set(calls) == {Path("deep/dir/two.py")}


def test_literal_bracket_under_strict_warning_policy(tmp_path):
    (tmp_path / ".gitignore").write_text("file[[]x].py\n/other.py\n", encoding="utf-8")
    with warnings.catch_warnings(action="error", category=FutureWarning):
        matcher = load_gitignore_patterns(tmp_path)
    assert matcher.should_ignore("file[x].py")
    assert matcher.should_ignore("other.py")

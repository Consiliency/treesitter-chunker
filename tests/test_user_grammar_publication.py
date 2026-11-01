"""Staged same-directory grammar publication (treesitter-chunker#162).

A real BAML grammar is compiled in two revisions. Each scenario runs in a
fresh subprocess so a native crash fails the test instead of the runner. Only
Git and generator commands are stubbed; every native load is real.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from hashlib import sha256
from pathlib import Path

import pytest

import chunker._internal.user_grammar_tools as tools_module
from chunker._internal.user_grammar_tools import (
    STAGED_SUFFIX,
    UserGrammarTools,
    publish_native_grammar,
)
from tests.test_compiled_grammar_analysis_contract import (
    FIXTURE,
    SOURCE,
    _compile_probe_fixture,
)

ROOT = Path(__file__).resolve().parents[1]

CHILD = r'''
import json
import os
import shutil
import subprocess
import sys
from hashlib import sha256
from pathlib import Path

root, build_dir, grammars_dir, rev_a, rev_b, fixture = map(Path, sys.argv[1:7])
mode = sys.argv[7]
sys.path.insert(0, str(root))

import chunker._internal.user_grammar_tools as tools_module
from chunker._internal.user_grammar_tools import UserGrammarTools
from chunker.grammar_management.core import load_compiled_grammar

current = {"artifact": rev_a}
real_run = subprocess.run


class StubSubprocess:
    """Stub Git and the grammar generator; everything else runs for real."""

    CalledProcessError = subprocess.CalledProcessError

    @staticmethod
    def run(command, cwd=None, **kwargs):
        if command[0] == "git":
            if command[1] == "clone":
                Path(command[-1]).mkdir(parents=True)
                return subprocess.CompletedProcess(command, 0, "", "")
            if command[1:3] == ["remote", "get-url"]:
                url = "https://github.com/example/tree-sitter-baml\n"
                return subprocess.CompletedProcess(command, 0, url, "")
            if command[1] == "rev-parse":
                commit = "a" * 40 if command[2] == "HEAD" else "b" * 40
                return subprocess.CompletedProcess(command, 0, commit + "\n", "")
            return subprocess.CompletedProcess(command, 0, "", "")
        if command[:2] == ["tree-sitter", "generate"]:
            shutil.copyfile(current["artifact"], Path(cwd) / "baml.so")
            return subprocess.CompletedProcess(command, 0, "", "")
        return real_run(command, cwd=cwd, **kwargs)


tools_module.subprocess = StubSubprocess


def pin(path):
    return {"sha256": sha256(path.read_bytes()).hexdigest()}


source = fixture.read_bytes()
tools = UserGrammarTools(build_dir, grammars_dir, trusted_artifacts={"baml": pin(rev_a)})
installed = tools.install_grammar("baml", "https://github.com/example/tree-sitter-baml")
assert installed["status"] == "success", installed
target = build_dir / "baml.so"
before = os.stat(target)
first_health = tools.manager.diagnose_grammar_issues("baml")

parser = None
if mode == "loaded":
    parser = load_compiled_grammar(target.absolute(), "baml")
    assert parser.language.semantic_version == (0, 1, 0)
    assert not parser.parse(source).root_node.has_error

current["artifact"] = rev_b
if mode != "unadmitted":
    tools.manager.trusted_artifacts["baml"] = pin(rev_b)
updated = tools.update_grammar("baml")
after = os.stat(target)
health = tools.manager.diagnose_grammar_issues("baml")

loaded_version = None
if parser is not None:
    # Keep exercising the parser whose library was just replaced.
    for _ in range(200):
        tree = parser.parse(source)
        assert tree.root_node.type == "source_file"
        assert not tree.root_node.has_error
    loaded_version = parser.language.semantic_version

print(json.dumps({
    "update": {key: updated[key] for key in ("status", "errors", "warnings")},
    "same_inode": (before.st_dev, before.st_ino) == (after.st_dev, after.st_ino),
    "installed_sha256": sha256(target.read_bytes()).hexdigest(),
    "first_health": [first_health.status, first_health.artifact_sha256],
    "health": [health.status, health.artifact_sha256],
    "loaded_semantic_version": loaded_version,
    "build_entries": sorted(entry.name for entry in build_dir.iterdir()),
}), flush=True)
'''

LOAD = r"""
import json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from chunker.grammar_management.core import load_compiled_grammar
parser = load_compiled_grammar(Path(sys.argv[2]), "baml")
root = parser.parse(Path(sys.argv[3]).read_bytes()).root_node
print(json.dumps({"version": parser.language.semantic_version,
                  "ok": root.type == "source_file" and not root.has_error}))
"""


def _digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


@pytest.fixture(scope="module")
def revisions(tmp_path_factory):
    """Compile BAML 0.1.0 and a relaid-out 0.2.0 revision of the same grammar."""
    root = tmp_path_factory.mktemp("baml-revisions")
    (root / "a").mkdir()
    rev_a = _compile_probe_fixture(root / "a", [SOURCE / "parser.c"])
    text = (SOURCE / "parser.c").read_text(encoding="utf-8")
    assert text.count(".minor_version = 1,") == 1
    # The exported function moves the grammar's code to different offsets, so
    # a process still mapping revision A cannot keep running on B's bytes.
    shift = "\n".join(f"  acc = acc * 31 + {index};" for index in range(20000))
    prefix = (
        "#ifdef _WIN32\n#define REVISION_EXPORT __declspec(dllexport)\n#else\n"
        '#define REVISION_EXPORT __attribute__((visibility("default")))\n#endif\n'
        "REVISION_EXPORT int tree_sitter_baml_revision_shift(int x) {\n"
        f"  volatile int acc = x;\n{shift}\n  return acc;\n}}\n"
    )
    (root / "b").mkdir()
    revised = root / "b" / "parser.c"
    revised.write_text(
        prefix + text.replace(".minor_version = 1,", ".minor_version = 2,"),
        encoding="utf-8",
    )
    rev_b = _compile_probe_fixture(root / "b", [revised])
    assert _digest(rev_a) != _digest(rev_b)
    return rev_a, rev_b


def _scenario(tmp_path: Path, revisions, mode: str) -> tuple[dict, Path]:
    rev_a, rev_b = revisions
    build_dir, grammars_dir = tmp_path / "build", tmp_path / "grammars"
    build_dir.mkdir()
    grammars_dir.mkdir()
    environment = {**os.environ, "HOME": str(tmp_path), "USERPROFILE": str(tmp_path)}
    child = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            CHILD,
            str(ROOT),
            str(build_dir),
            str(grammars_dir),
            str(rev_a),
            str(rev_b),
            str(FIXTURE),
            mode,
        ],
        capture_output=True,
        text=True,
        timeout=300,
        env=environment,
        check=False,
    )
    assert child.returncode == 0, (child.returncode, child.stderr[-4000:])
    return json.loads(child.stdout.strip().splitlines()[-1]), build_dir / "baml.so"


def _fresh_load(library: Path) -> dict:
    loaded = subprocess.run(
        [sys.executable, "-I", "-c", LOAD, str(ROOT), str(library), str(FIXTURE)],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert loaded.returncode == 0, (loaded.returncode, loaded.stderr[-4000:])
    return json.loads(loaded.stdout)


def test_update_replaces_loaded_grammar_without_crash(tmp_path, revisions):
    rev_a, rev_b = revisions
    report, installed = _scenario(tmp_path, revisions, "loaded")

    assert report["first_health"] == ["healthy", _digest(rev_a)]
    assert report["loaded_semantic_version"] == [0, 1, 0]
    assert report["build_entries"] == ["baml.so"]
    if sys.platform == "win32":
        # Windows refuses to replace a loaded library; nothing is overwritten.
        assert report["update"]["status"] == "error"
        assert "Could not publish baml.so" in report["update"]["errors"][-1]
        assert "This usually means a running process has the library loaded" in (
            report["update"]["errors"][-1]
        )
        assert report["installed_sha256"] == _digest(rev_a)
        assert _fresh_load(installed) == {"version": [0, 1, 0], "ok": True}
        return
    assert report["update"] == {"status": "success", "errors": [], "warnings": []}
    assert report["same_inode"] is False
    assert report["installed_sha256"] == _digest(rev_b)
    assert report["health"] == ["healthy", _digest(rev_b)]
    assert _fresh_load(installed) == {"version": [0, 2, 0], "ok": True}


def test_update_publishes_new_revision_for_next_load(tmp_path, revisions):
    _, rev_b = revisions
    report, installed = _scenario(tmp_path, revisions, "unloaded")

    assert report["update"] == {"status": "success", "errors": [], "warnings": []}
    assert report["same_inode"] is False
    assert report["installed_sha256"] == _digest(rev_b)
    assert report["health"] == ["healthy", _digest(rev_b)]
    assert report["build_entries"] == ["baml.so"]
    assert _fresh_load(installed) == {"version": [0, 2, 0], "ok": True}


def test_unadmitted_update_leaves_installed_library(tmp_path, revisions):
    rev_a, _ = revisions
    report, installed = _scenario(tmp_path, revisions, "unadmitted")

    assert report["update"]["status"] == "error"
    assert report["update"]["errors"] == [
        "Native admission failed for baml.so: integrity_mismatch (the library "
        "does not match its approved SHA-256 pin); the installed library is "
        "unchanged."
    ]
    assert report["same_inode"] is True
    assert report["installed_sha256"] == _digest(rev_a)
    assert report["health"] == ["healthy", _digest(rev_a)]
    assert report["build_entries"] == ["baml.so"]
    assert _fresh_load(installed) == {"version": [0, 1, 0], "ok": True}


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX symlink contract")
def test_publication_replaces_symlink_without_writing_its_target(tmp_path, revisions):
    rev_a, rev_b = revisions
    outside = tmp_path / "outside.so"
    outside.write_bytes(rev_a.read_bytes())
    build_dir = tmp_path / "build"
    build_dir.mkdir()
    destination = build_dir / "baml.so"
    destination.symlink_to(outside)

    result = publish_native_grammar(
        rev_b, destination, "baml", provenance={"sha256": _digest(rev_b)}
    )

    assert result.supported, result
    assert not destination.is_symlink()
    assert _digest(destination) == _digest(rev_b)
    assert _digest(outside) == _digest(rev_a)
    assert sorted(entry.name for entry in build_dir.iterdir()) == ["baml.so"]


def test_staged_file_is_never_named_like_a_library(tmp_path, revisions, monkeypatch):
    rev_a, _ = revisions
    build_dir = tmp_path / "build"
    build_dir.mkdir()
    seen = []
    real_probe = tools_module.probe_native_grammar

    def observe(path, *args, **kwargs):
        # Spy only: record what a concurrent scan would see, then admit for real.
        seen.append((path.name, sorted(entry.name for entry in build_dir.iterdir())))
        return real_probe(path, *args, **kwargs)

    monkeypatch.setattr(tools_module, "probe_native_grammar", observe)
    result = publish_native_grammar(
        rev_a, build_dir / "baml.so", "baml", provenance={"sha256": _digest(rev_a)}
    )

    assert result.supported, result
    [(staged_name, entries)] = seen
    assert staged_name.startswith(".baml.so-")
    assert staged_name.endswith(STAGED_SUFFIX)
    assert entries == [staged_name]
    assert not any(staged_name.endswith(suffix) for suffix in (".so", ".dylib", ".dll"))


def test_crash_leftover_is_not_listed_as_a_grammar(tmp_path, revisions):
    rev_a, _ = revisions
    build_dir, grammars_dir = tmp_path / "build", tmp_path / "grammars"
    build_dir.mkdir()
    grammars_dir.mkdir()
    (build_dir / f".baml.so-k3j2{STAGED_SUFFIX}").write_bytes(rev_a.read_bytes())
    tools = UserGrammarTools(
        build_dir, grammars_dir, trusted_artifacts={"baml": {"sha256": _digest(rev_a)}}
    )

    assert tools.list_installed_grammars()["grammars"] == {}


def _tools_with_cached_state(tmp_path, pin):
    build_dir, grammars_dir = tmp_path / "build", tmp_path / "grammars"
    build_dir.mkdir()
    grammars_dir.mkdir()
    tools = UserGrammarTools(build_dir, grammars_dir, trusted_artifacts=pin)
    tools.manager.health_cache["baml"] = object()
    tools.manager.compatibility_cache["baml"] = object()
    return tools


@pytest.mark.parametrize("outcome", ["published", "rejected"])
def test_publication_drops_cached_grammar_state(tmp_path, revisions, outcome):
    rev_a, _ = revisions
    pin = {"sha256": _digest(rev_a) if outcome == "published" else "0" * 64}
    tools = _tools_with_cached_state(tmp_path, {"baml": pin})
    result = {"errors": [], "status": "unknown"}

    assert tools._publish_library("baml", rev_a, result) is (outcome == "published")
    assert "baml" not in tools.manager.health_cache
    assert "baml" not in tools.manager.compatibility_cache


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX replacement failure")
def test_failed_replacement_reports_error_and_keeps_destination(tmp_path, revisions):
    rev_a, _ = revisions
    tools = _tools_with_cached_state(tmp_path, {"baml": {"sha256": _digest(rev_a)}})
    # A nonempty directory at the destination makes os.replace fail after
    # the staged library was admitted.
    blocker = tools.build_dir / "baml.so"
    blocker.mkdir()
    (blocker / "keep.txt").write_text("kept", encoding="utf-8")
    result = {"errors": [], "status": "unknown"}

    assert tools._publish_library("baml", rev_a, result) is False
    assert result["status"] == "error"
    [message] = result["errors"]
    assert message.startswith(f"Could not publish {rev_a.name} to {blocker}: ")
    assert message.endswith("The installed library is unchanged.")
    assert "Windows" not in message
    assert (blocker / "keep.txt").read_text(encoding="utf-8") == "kept"
    assert sorted(entry.name for entry in tools.build_dir.iterdir()) == ["baml.so"]
    assert "baml" not in tools.manager.health_cache


@pytest.mark.parametrize(
    ("reason", "explanation"),
    [
        ("missing", "the library file does not exist"),
        ("child_failed", "the probe process failed or ended abnormally"),
        ("inspect_failed", "the artifact inspection step failed"),
        ("ack_missing", "the probe process returned no result"),
        ("ack_invalid", "the probe process returned an invalid result"),
    ],
)
def test_probe_failure_reasons_are_explained(
    tmp_path, monkeypatch, reason, explanation
):
    """Every probe rejection reason is explained in plain English, never the
    generic fallback (treesitter-chunker#539 carry-over)."""
    from chunker.grammar.integrity import NativeProbeResult

    tools = UserGrammarTools(
        tmp_path / "build",
        tmp_path / "grammars",
        trusted_artifacts={"baml": {"sha256": "0" * 64}},
    )
    monkeypatch.setattr(
        tools_module,
        "publish_native_grammar",
        lambda *args, **kwargs: NativeProbeResult(False, reason, None),
    )
    result = {"status": "success", "errors": [], "warnings": []}
    assert tools._publish_library("baml", tmp_path / "baml.so", result) is False
    assert result["errors"] == [
        f"Native admission failed for baml.so: {reason} ({explanation}); the "
        "installed library is unchanged."
    ]

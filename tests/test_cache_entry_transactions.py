"""Concurrency-safe cache entries and cleanup (treesitter-chunker#323).

Cache transaction contract, Primitive 2. Installers and pruners are real
``GrammarInstaller.install_grammar`` and ``GrammarManager.cleanup_cache`` calls
in separate processes, ordered only by seam events (tests/txn_barrier.py).
Builds use the real C compiler on the real BAML grammar sources, and every
native load is real. The only substitution is a ``git`` shim on ``PATH``
inside the child processes; it copies a local fixture repository (with
``copystat``, so sources keep old mtimes) and can leave a grandchild running.
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
import time
from pathlib import Path

import psutil
import pytest

from chunker.grammar_management import _transactions
from tests.test_compiled_grammar_analysis_contract import SOURCE, _compile_probe_fixture
from tests.test_user_grammar_publication import LOAD
from tests.txn_barrier import (
    ROOT,
    SAFETY_TIMEOUT,
    Child,
    exit_at,
    pause_at,
    participants,
    run_mounting,
)

OLD = time.time() - 60 * 86400
URL = "https://github.com/example/tree-sitter-baml"
POSIX_SHIM = pytest.mark.skipif(
    sys.platform == "win32" or shutil.which("gcc") is None,
    reason="the git shim is a POSIX script and the installer builds with gcc",
)

SHIM = r"""#!{python}
import os, shutil, subprocess, sys, time

WRITER = (
    "import os, sys, time\n"
    "os.chdir(sys.argv[1])  # keeps writing into its cwd, wherever it moves\n"
    "i = 0\n"
    "while True:\n"
    "    with open('grandchild.txt', 'a') as handle:\n"
    "        handle.write(f'{{i}}\\n')\n"
    "    i += 1\n"
    "    time.sleep(0.02)\n"
)
args = sys.argv[1:]
if args[:1] == ["clone"]:
    destination = args[-1]
    shutil.copytree(os.environ["TXN_GIT_FIXTURE"], destination, symlinks=True)
    fifo = os.environ.get("TXN_GIT_FIFO")
    if fifo:
        os.mkfifo(os.path.join(destination, fifo))
    pidfile = os.environ.get("TXN_GIT_GRANDCHILD")
    if pidfile:
        grandchild = subprocess.Popen(
            [sys.executable, "-c", WRITER, destination],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        with open(pidfile + ".tmp", "w", encoding="utf-8") as handle:
            handle.write(str(grandchild.pid))
        os.replace(pidfile + ".tmp", pidfile)
        while not os.path.exists(os.path.join(destination, "grandchild.txt")):
            time.sleep(0.01)  # readiness: the grandchild is writing
    sys.exit(0)
if args[:2] == ["rev-parse", "HEAD"]:
    print("a" * 40)
sys.exit(0)
"""

INSTALL = r"""
import logging
from pathlib import Path
from chunker.grammar_management.core import GrammarInstaller

cache, build_timeout = Path(ARGS[0]), float(ARGS[1])
messages = []


class Collect(logging.Handler):
    def emit(self, record):
        messages.append(record.getMessage())


logging.getLogger().addHandler(Collect(level=logging.WARNING))
logging.getLogger().setLevel(logging.WARNING)
installer = GrammarInstaller(cache_dir=cache, build_timeout=build_timeout)
emit("ready")
wait()
ok, error, _info = installer.install_grammar("baml", "https://github.com/example/tree-sitter-baml")
emit("done", success=ok, error=error, warnings=messages)
"""

PRUNE = r"""
from pathlib import Path
from chunker.grammar_management.core import GrammarManager

cache, scratch, days = Path(ARGS[0]), Path(ARGS[1]), float(ARGS[2])
manager = GrammarManager(
    user_dir=scratch / "user", package_dir=scratch / "package", cache_dir=cache
)
emit("ready")
wait()
emit("done", stats=manager.cleanup_cache(older_than_days=days))
"""


def _age(tree: Path, when: float = OLD) -> None:
    """Give a tree, its directories and the root itself one old mtime."""
    no_follow = os.utime in os.supports_follow_symlinks  # not on Windows
    for path in sorted(tree.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        if no_follow:
            os.utime(path, (when, when), follow_symlinks=False)
        elif not path.is_symlink():
            os.utime(path, (when, when))
    os.utime(tree, (when, when))


def _repo(base: Path, *, minor: int = 1, fifo: bool = False) -> Path:
    """A fixture grammar repository whose files and directories are all old."""
    (base / "src" / "tree_sitter").mkdir(parents=True)
    text = (SOURCE / "parser.c").read_text(encoding="utf-8")
    assert text.count(".minor_version = 1,") == 1
    text = text.replace(".minor_version = 1,", f".minor_version = {minor},")
    if fifo:
        text = '#include "hang.h"\n' + text
    (base / "src" / "parser.c").write_text(text, encoding="utf-8")
    shutil.copy2(
        SOURCE / "tree_sitter" / "parser.h", base / "src" / "tree_sitter" / "parser.h"
    )
    _age(base)
    return base


@pytest.fixture
def shim(tmp_path: Path) -> Path:
    directory = tmp_path / "shim"
    directory.mkdir()
    git = directory / "git"
    git.write_text(SHIM.format(python=sys.executable), encoding="utf-8")
    git.chmod(0o755)
    return directory


def _env(shim: Path, repo: Path, **extra: str) -> dict[str, str]:
    return {
        **os.environ,
        "PATH": f"{shim}{os.pathsep}{os.environ.get('PATH', '')}",
        "TXN_GIT_FIXTURE": str(repo),
        **extra,
    }


def _installer(cache: Path, env: dict[str, str], *, timeout: float = 120.0, pauses=()):
    return Child(INSTALL, [cache, timeout], pauses=pauses, env=env)


def _install(cache: Path, env: dict[str, str], **kwargs) -> dict:
    child = _installer(cache, env, **kwargs)
    try:
        child.expect("ready")
        child.release()
        return child.finish()
    finally:
        child.close()


def _kill_pidfile(pidfile: Path) -> None:
    if pidfile.exists():
        try:
            psutil.Process(int(pidfile.read_text(encoding="utf-8"))).kill()
        except psutil.Error:
            pass


def _gone(pid: int) -> bool:
    try:
        process = psutil.Process(pid)
        return process.status() == psutil.STATUS_ZOMBIE
    except psutil.NoSuchProcess:
        return True


def _tree(path: Path) -> dict[str, bytes]:
    return {
        str(p.relative_to(path)): p.read_bytes()
        for p in sorted(path.rglob("*"))
        if p.is_file() and not p.is_symlink()
    }


def _seed(entry: Path, files: dict[str, bytes], when: float = OLD) -> int:
    for name, data in files.items():
        target = entry / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    _age(entry, when)
    return sum(len(data) for data in files.values())


# --- writer and pruner -------------------------------------------------------


@POSIX_SHIM
def test_cleanup_racing_install_keeps_republished_entry(tmp_path, shim):
    """A republished entry is re-checked under the lock and survives.

    ``cleanup_cache`` pauses at ``prune.after_enumerate`` with the expired
    ``tree-sitter-baml`` download as a candidate. A real install republishes
    that name from old-mtime sources. Only the unrelated expired entry is
    removed and counted. Mutations ``prune_without_recheck`` (enumeration-time
    eligibility) and ``trust_copied_mtime`` (no stamp) delete the new entry.
    """
    cache = tmp_path / "cache"
    repo = _repo(tmp_path / "repo")
    stale = _seed(cache / "downloads" / "tree-sitter-baml", {"stale.txt": b"x" * 10})
    assert stale == 10
    expired = _seed(
        cache / "downloads" / "tree-sitter-old", {"a": b"a" * 7, "d/b": b"b" * 5}
    )
    with participants() as children:
        pruner = Child(
            PRUNE,
            [cache, tmp_path, 30],
            pauses=[pause_at("prune.after_enumerate", namespace="downloads")],
        )
        children.append(pruner)
        pruner.expect("ready")
        pruner.release()
        pruner.expect("prune.after_enumerate", namespace="downloads")

        installed = _install(cache, _env(shim, repo))
        assert installed["success"], installed
        published = cache / "downloads" / "tree-sitter-baml"
        assert not (published / "stale.txt").exists()
        before = _tree(published)

        pruner.release()
        stats = pruner.finish()["stats"]

    assert _tree(published) == before
    assert (published / "src" / "parser.c").is_file()
    assert (cache / "builds" / "baml" / "libbaml.so").is_file()
    assert not (cache / "downloads" / "tree-sitter-old").exists()
    assert stats["files_removed"] == 1
    assert stats["bytes_freed"] == expired
    assert stats["errors"] == []


def test_prune_counts_expired_cutoff_and_denied_entries_truthfully(tmp_path):
    """Exact cutoff is kept; only bytes actually unlinked are counted.

    Mutation ``overcount_failed_removal`` (count before unlink) counts the
    denied file.
    """
    root = tmp_path / "cache"
    root.mkdir()
    _transactions.open_cache_root(root)
    cutoff = time.time() - 30 * 86400
    expired = _seed(root / "builds" / "expired", {"lib.so": b"e" * 11, "x/y": b"y" * 3})
    _seed(root / "builds" / "at-cutoff", {"lib.so": b"c" * 13}, when=cutoff)
    result = _transactions.prune_entries(root, "builds", cutoff=cutoff)
    assert (result.entries_removed, result.bytes_freed) == (1, expired)
    assert result.errors == ()
    assert not (root / "builds" / "expired").exists()
    assert (root / "builds" / "at-cutoff" / "lib.so").read_bytes() == b"c" * 13

    if sys.platform == "win32" or os.geteuid() == 0:
        return  # chmod denial is a POSIX, non-root contract
    denied = root / "builds" / "denied"
    _seed(denied, {"ok.bin": b"o" * 17, "locked/held.bin": b"h" * 19})
    (denied / "locked").chmod(0o500)
    _age(denied)
    try:
        result = _transactions.prune_entries(root, "builds", cutoff=cutoff)
    finally:
        for directory in (root / ".txn" / "retired").rglob("locked"):
            directory.chmod(0o700)
    assert result.entries_removed == 1
    assert result.bytes_freed == 17  # held.bin was not unlinked, so not counted
    assert len(result.errors) >= 1 and any("held.bin" in e for e in result.errors)
    leftovers = list((root / ".txn" / "retired").rglob("held.bin"))
    assert [p.read_bytes() for p in leftovers] == [b"h" * 19]
    # A later prune claims the garbage and counts it then, once.
    again = _transactions.prune_entries(root, "builds", cutoff=cutoff)
    assert (again.entries_removed, again.bytes_freed, again.errors) == (0, 19, ())
    assert not list((root / ".txn" / "retired").rglob("held.bin"))


# --- link boundaries -----------------------------------------------------------


def _link(link: Path, target: Path, *, directory: bool = False) -> None:
    try:
        link.symlink_to(target, target_is_directory=directory)
    except OSError as error:
        if getattr(error, "winerror", None) == 1314:
            pytest.skip("this Windows account may not create symbolic links")
        raise


def test_links_inside_entries_are_leaves(tmp_path):
    """File, directory, dangling links and junctions are removed as leaves.

    Their targets are never traversed, removed or counted. A read-only file is
    removed too (git objects on Windows). Mutation ``follow_cache_link``
    (traverse link targets) deletes or counts the outside sentinels.
    """
    outside = tmp_path / "outside"
    (outside / "tree").mkdir(parents=True)
    sentinel = outside / "sentinel.bin"
    sentinel.write_bytes(b"s" * 23)
    (outside / "tree" / "inner.bin").write_bytes(b"i" * 29)
    before = _tree(outside)

    root = tmp_path / "cache"
    root.mkdir()
    _transactions.open_cache_root(root)
    entry = root / "downloads" / "tree-sitter-links"
    owned = _seed(entry, {"own.bin": b"o" * 31, "ro.bin": b"r" * 37})
    (entry / "ro.bin").chmod(stat.S_IREAD)
    _link(entry / "file-link", sentinel)
    _link(entry / "dir-link", outside / "tree", directory=True)
    _link(entry / "dangling", outside / "missing")
    if sys.platform == "win32":
        import _winapi

        _winapi.CreateJunction(str(outside / "tree"), str(entry / "junction"))

    result = _transactions.prune_entries(root, "downloads", cutoff=time.time() + 3600)
    assert result.errors == ()
    assert (result.entries_removed, result.bytes_freed) == (1, owned)
    assert not os.path.lexists(entry)
    assert _tree(outside) == before
    assert sorted(p.name for p in outside.iterdir()) == ["sentinel.bin", "tree"]


# --- owned subprocesses --------------------------------------------------------


@POSIX_SHIM
def test_grandchild_is_gone_before_publication(tmp_path, shim):
    """The clone's grandchild is killed and confirmed gone before publishing.

    Mutation ``publish_before_group_empty`` (skip the kill and confirmation)
    leaves the grandchild writing into the published entry.
    """
    cache = tmp_path / "cache"
    repo = _repo(tmp_path / "repo")
    pidfile = tmp_path / "grandchild.pid"
    try:
        with participants() as children:
            child = _installer(cache, _env(shim, repo, TXN_GIT_GRANDCHILD=str(pidfile)))
            children.append(child)
            child.expect("ready")
            child.release()
            done = child.finish()
        assert done["success"], done
        events = [
            e["event"] + ":" + e.get("program", e.get("name", "")) for e in child.seen
        ]
        assert "run.after_group_empty:git" in events
        assert events.index("run.after_group_empty:git") < events.index(
            "publish.before_promote:tree-sitter-baml"
        )
        assert _gone(int(pidfile.read_text(encoding="utf-8")))
        written = cache / "downloads" / "tree-sitter-baml" / "grandchild.txt"
        first = written.read_bytes()
        assert first
        # A full later operation runs; nothing kept writing to the entry.
        _transactions.prune_entries(cache, "builds", cutoff=OLD)
        assert written.read_bytes() == first
    finally:
        _kill_pidfile(pidfile)


@pytest.mark.skipif(
    sys.platform == "win32" or not shutil.which("gcc") or not shutil.which("make"),
    reason="FIFO-blocked gcc and make fallback are POSIX fixtures",
)
def test_build_timeout_fails_without_fallback_or_publication(tmp_path, shim):
    """A timed-out build kills its group, publishes nothing and stops.

    The staged ``parser.c`` includes a FIFO, so the real compiler blocks until
    the build timeout. A ``Makefile`` plus a valid prebuilt library would make
    the ``make`` fallback succeed. Mutation ``fallback_after_timeout`` (continue
    to the next build method in the same staging) installs it.
    """
    cache = tmp_path / "cache"
    repo = _repo(tmp_path / "repo", fifo=True)
    (repo / "Makefile").write_text("all:\n\t@true\n", encoding="utf-8")
    prebuilt = _compile_probe_fixture(tmp_path, [SOURCE / "parser.c"])
    shutil.copy2(prebuilt, repo / "libbaml.so")
    done = _install(cache, _env(shim, repo, TXN_GIT_FIFO="src/hang.h"), timeout=3)
    assert not done["success"]
    assert "Build aborted: GCC build timed out" in done["error"]
    assert not (cache / "grammars" / "libbaml.so").exists()
    assert not os.path.lexists(cache / "downloads" / "tree-sitter-baml")
    assert not os.path.lexists(cache / "builds" / "baml")
    for process in psutil.process_iter(["cmdline"]):
        assert str(cache) not in " ".join(process.info["cmdline"] or []), process


@POSIX_SHIM
def test_parent_death_leaves_staging_unpublished_and_retained(tmp_path, shim):
    """An installer killed at ``run.after_exit`` leaves only its staging.

    On POSIX the clone's grandchild survives in that staging. A later install
    and a prune neither publish nor delete it.
    """
    cache = tmp_path / "cache"
    repo = _repo(tmp_path / "repo")
    pidfile = tmp_path / "grandchild.pid"
    try:
        child = _installer(
            cache,
            _env(shim, repo, TXN_GIT_GRANDCHILD=str(pidfile)),
            pauses=[exit_at("run.after_exit", program="git")],
        )
        try:
            child.expect("ready")
            child.release()
            assert child.exit_code() == 17
        finally:
            child.close()
        orphan = int(pidfile.read_text(encoding="utf-8"))
        assert not _gone(orphan)
        (staged,) = list(
            (cache / ".txn" / "staging").glob("*/downloads/tree-sitter-baml")
        )

        assert _install(cache, _env(shim, repo))["success"]
        assert not (
            cache / "downloads" / "tree-sitter-baml" / "grandchild.txt"
        ).exists()
        with participants() as children:
            pruner = Child(PRUNE, [cache, tmp_path, 0])
            children.append(pruner)
            pruner.expect("ready")
            pruner.release()
            pruner.finish()
        assert (staged / "grandchild.txt").is_file()
        assert (staged / "src" / "parser.c").is_file()
    finally:
        _kill_pidfile(pidfile)


SPAWNER = r"""
import subprocess, sys, time
pidfile = sys.argv[1]
grandchild = subprocess.Popen(
    [sys.executable, "-c", "import time\nwhile True: time.sleep(0.05)"],
    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
)
with open(pidfile, "w", encoding="utf-8") as handle:
    handle.write(str(grandchild.pid))
"""

RUN_IN_STAGING = r"""
import sys
from pathlib import Path
root, pidfile = Path(ARGS[0]), ARGS[1]
staging = _transactions.create_staging(root)
emit("ready")
wait()
_transactions.run_in_staging(
    staging, [sys.executable, "-c", ARGS[2], pidfile], cwd=staging.path, timeout=60
)
emit("done")
"""


@pytest.mark.skipif(sys.platform != "win32", reason="Windows job-object contract")
def test_windows_job_kills_grandchild_when_parent_dies(tmp_path):
    root = tmp_path / "cache"
    root.mkdir()
    pidfile = tmp_path / "grandchild.pid"
    try:
        child = Child(
            RUN_IN_STAGING,
            [root, pidfile, SPAWNER],
            pauses=[exit_at("run.after_exit", primitive="run_in_staging")],
        )
        try:
            child.expect("ready")
            child.release()
            assert child.exit_code() == 17
        finally:
            child.close()
        grandchild = int(pidfile.read_text(encoding="utf-8"))
        try:
            psutil.Process(grandchild).wait(timeout=SAFETY_TIMEOUT)
        except psutil.NoSuchProcess:
            pass
        assert not psutil.pid_exists(grandchild) or _gone(grandchild)
    finally:
        _kill_pidfile(pidfile)


# --- owned inputs ----------------------------------------------------------------


@POSIX_SHIM
def test_installer_uses_its_own_staged_inputs(tmp_path, shim):
    """Installer A pauses after its build; B installs, then its entries go.

    A resumes and installs its own revision from its staging; a fresh process
    parses A's revision. Mutation ``consume_published_input`` (install from
    the published ``builds/`` path) fails or installs B's revision.
    """
    cache = tmp_path / "cache"
    repo_a = _repo(tmp_path / "repo-a", minor=1)
    repo_b = _repo(tmp_path / "repo-b", minor=2)
    with participants() as children:
        a = _installer(
            cache,
            _env(shim, repo_a),
            pauses=[pause_at("run.after_group_empty", program="gcc")],
        )
        children.append(a)
        a.expect("ready")
        a.release()
        a.expect("run.after_group_empty", program="gcc")

        assert _install(cache, _env(shim, repo_b))["success"]
        assert (cache / "builds" / "baml" / "libbaml.so").is_file()
        for namespace, name in (("downloads", "tree-sitter-baml"), ("builds", "baml")):
            assert (
                _transactions.remove_entry(cache, namespace, name).entries_removed == 1
            )

        a.release()
        done = a.finish()
    assert done["success"], done
    loaded = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            LOAD,
            str(ROOT),
            str(cache / "grammars" / "libbaml.so"),
            str(ROOT / "packages/baml-grammar/tests/fixtures/declarations.baml"),
        ],
        capture_output=True,
        text=True,
        timeout=SAFETY_TIMEOUT,
        check=True,
    )
    assert json.loads(loaded.stdout) == {"version": [0, 1, 0], "ok": True}


# --- republication failures ------------------------------------------------------


@POSIX_SHIM
def test_crash_after_retire_leaves_absent_entry_that_recovers(tmp_path, shim):
    cache = tmp_path / "cache"
    repo = _repo(tmp_path / "repo")
    env = _env(shim, repo)
    assert _install(cache, env)["success"]
    published = cache / "downloads" / "tree-sitter-baml"
    (published / "generation.txt").write_text("old", encoding="utf-8")

    child = _installer(
        cache, env, pauses=[exit_at("publish.after_retire", namespace="downloads")]
    )
    try:
        child.expect("ready")
        child.release()
        event = child.expect("publish.after_retire", namespace="downloads")
        operation = event["operation_id"]
        assert child.exit_code() == 17
    finally:
        child.close()
    assert not os.path.lexists(published)
    garbage = cache / ".txn" / "retired" / operation / "downloads" / "tree-sitter-baml"
    assert (garbage / "generation.txt").read_text(encoding="utf-8") == "old"
    assert (
        cache / ".txn" / "staging" / operation / "downloads" / "tree-sitter-baml"
    ).is_dir()

    result = _transactions.prune_entries(cache, "downloads", cutoff=OLD)
    assert result.errors == ()
    assert not (cache / ".txn" / "retired" / operation).exists()
    assert (cache / ".txn" / "staging" / operation).is_dir()  # staging is retained

    assert _install(cache, env)["success"]
    assert (published / "src" / "parser.c").is_file()


@POSIX_SHIM
def test_failed_promotion_restores_previous_entry_and_install_succeeds(tmp_path, shim):
    """Promotion fails after retirement; the old entry is renamed back.

    The install was already committed, so it still succeeds and reports a
    warning (carried-over Codex finding 1). Mutation ``no_rename_back`` leaves
    the name absent.
    """
    cache = tmp_path / "cache"
    repo = _repo(tmp_path / "repo")
    env = _env(shim, repo)
    assert _install(cache, env)["success"]
    published = cache / "downloads" / "tree-sitter-baml"
    (published / "generation.txt").write_text("old", encoding="utf-8")
    with participants() as children:
        child = _installer(
            cache, env, pauses=[pause_at("publish.after_retire", namespace="downloads")]
        )
        children.append(child)
        child.expect("ready")
        child.release()
        event = child.expect("publish.after_retire", namespace="downloads")
        staged = (
            cache
            / ".txn"
            / "staging"
            / event["operation_id"]
            / "downloads"
            / "tree-sitter-baml"
        )
        shutil.rmtree(staged)  # a non-participant removes the staged entry
        child.release()
        done = child.finish()
    assert done["success"], done
    assert any("cache entry was not published" in w for w in done["warnings"])
    assert any("previous generation was restored" in w for w in done["warnings"])
    assert (published / "generation.txt").read_text(encoding="utf-8") == "old"


# --- nested roots ------------------------------------------------------------------


def test_entry_holding_an_inner_root_is_never_retired(tmp_path):
    """Inner root first at R/downloads/x, then R: every retirement refuses.

    Mutation ``nested_root_retire`` (skip the descendant check in
    ``remove_entry`` and ``publish_entry``) deletes the inner root.
    """
    outer = tmp_path / "outer"
    inner = outer / "downloads" / "x"
    inner.mkdir(parents=True)
    _transactions.open_cache_root(inner)
    (inner / "data.bin").write_bytes(b"d" * 41)
    _age(outer / "downloads")
    _transactions.open_cache_root(outer)

    pruned = _transactions.prune_entries(outer, "downloads", cutoff=time.time() + 3600)
    assert pruned.entries_removed == 0 and pruned.skipped == ("x",)
    assert any("nested cache root" in e for e in pruned.errors)
    with pytest.raises(_transactions.NestedRootError):
        _transactions.remove_entry(outer, "downloads", "x")
    staging = _transactions.create_staging(outer)
    (staging.path / "downloads" / "x").mkdir()
    with pytest.raises(_transactions.NestedRootError):
        _transactions.publish_entry(staging, "downloads", "x")
    assert (staging.path / "downloads" / "x").is_dir()
    assert (inner / _transactions.LOCK_FILE_NAME).is_file()
    assert (inner / "data.bin").read_bytes() == b"d" * 41


OPEN_ROOT = r"""
from pathlib import Path
emit("ready")
wait()
try:
    _transactions.open_cache_root(Path(ARGS[0]))
    emit("done", error=None)
except Exception as error:
    emit("done", error=f"{type(error).__name__}: {error}")
"""


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="Windows cannot rename a directory while its lock file is open",
)
def test_root_moved_during_initialization_fails_post_check(tmp_path):
    inner = tmp_path / "inner"
    inner.mkdir()
    with participants() as children:
        child = Child(
            OPEN_ROOT,
            [inner],
            pauses=[pause_at("root.after_init", primitive="open_cache_root")],
        )
        children.append(child)
        child.expect("ready")
        child.release()
        child.expect("root.after_init", primitive="open_cache_root")
        inner.rename(tmp_path / "moved")
        child.release()
        done = child.finish()
    assert done["error"] and done["error"].startswith("CacheTransactionError")


def test_discarded_staging_is_retired_then_deleted(tmp_path):
    """Claude N6: discard retires staging into ``.txn/retired`` first."""
    root = tmp_path / "cache"
    root.mkdir()
    staging = _transactions.create_staging(root)
    (staging.path / "builds" / "baml").mkdir()
    (staging.path / "builds" / "baml" / "lib.so").write_bytes(b"l" * 43)
    result = _transactions.discard_staging(staging)
    assert result.errors == () and result.bytes_freed == 43
    assert not staging.path.exists()
    assert not (root / ".txn" / "retired" / staging.operation_id).exists()


SPLIT_NAMESPACE = r"""
import json, sys, time
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from chunker.grammar_management import _transactions as t

root = Path(sys.argv[2])
t.open_cache_root(root)
staging = t.create_staging(root)  # before any mount
(staging.path / "builds" / "x").mkdir()
outcomes = {}
try:
    mount_tmpfs(root / "builds")
    (root / "builds" / "old").mkdir()
    (root / "builds" / "old" / "lib.so").write_bytes(b"o" * 7)
    calls = {
        "publish_entry": lambda: t.publish_entry(staging, "builds", "x"),
        "remove_entry": lambda: t.remove_entry(root, "builds", "old"),
        "prune_entries": lambda: t.prune_entries(root, "builds", cutoff=time.time() + 3600),
        "create_staging": lambda: t.create_staging(root),
    }
    for name, call in calls.items():
        try:
            call()
            outcomes[name] = "ok"
        except t.CacheTransactionError as error:
            outcomes[name] = "refused" if "different filesystem" in str(error) else str(error)
        except OSError as error:
            outcomes[name] = f"OSError: {error}"
    outcomes["records"] = sorted(
        t.update_json_records(root, "validation_cache.json", lambda d: {**d, "k": 1})
    )
    outcomes["other_namespace"] = t.prune_entries(
        root, "downloads", cutoff=time.time() + 3600
    ).errors
    outcomes["entries_intact"] = sorted(p.name for p in (root / "builds").iterdir())
    outcomes["staged_intact"] = (staging.path / "builds" / "x").is_dir()
finally:
    unmount_all()
print(json.dumps(outcomes, default=list))
"""


def test_rename_sites_refuse_a_namespace_on_another_filesystem(tmp_path):
    """Amendment A1: a real tmpfs at ``builds/`` is refused before any rename.

    The record update (Primitive 1) and the other namespace keep working.
    Mutation ``drop_same_device_check`` lets the renames fail part-way with
    ``EXDEV`` instead of the actionable refusal.
    """
    root = tmp_path / "cache"
    root.mkdir()
    result = run_mounting(SPLIT_NAMESPACE, [root])
    assert result.returncode == 0, result.stderr[-3000:]
    outcomes = json.loads(result.stdout.strip().splitlines()[-1])
    assert outcomes == {
        "publish_entry": "refused",
        "remove_entry": "refused",
        "prune_entries": "refused",
        "create_staging": "refused",
        "records": ["k"],
        "other_namespace": [],
        "entries_intact": ["old"],
        "staged_intact": True,
    }

"""Concurrency-safe cache entries and cleanup (treesitter-chunker#323).

Cache transaction contract, Primitive 2. Installers and pruners are real
``GrammarInstaller.install_grammar`` and ``GrammarManager.cleanup_cache`` calls
in separate processes, ordered only by seam events (tests/txn_barrier.py).
Builds use the real C compiler on the real BAML grammar sources, and every
native load is real. The only substitution is a ``git`` shim on ``PATH``
inside the child processes; it copies a local fixture repository (with
``copystat``, so sources keep old mtimes) and can leave a grandchild running.
A test may also give ``git rev-parse`` its own short limit while the build keeps
a generous one (treesitter-chunker#606).
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
import threading
import time
from hashlib import sha256
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
    interrupt_at,
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
        with open(pidfile + ".leader", "w", encoding="utf-8") as handle:
            handle.write(str(os.getpid()))
        with open(pidfile + ".tmp", "w", encoding="utf-8") as handle:
            handle.write(str(grandchild.pid))
        os.replace(pidfile + ".tmp", pidfile)
        while not os.path.exists(os.path.join(destination, "grandchild.txt")):
            time.sleep(0.01)  # readiness: the grandchild is writing
    if os.environ.get("TXN_GIT_SLEEP"):
        time.sleep(3600)  # the leader keeps running
    sys.exit(0)
if args[:2] == ["rev-parse", "HEAD"]:
    fault = os.environ.get("TXN_GIT_REVPARSE")
    if fault == "timeout":
        time.sleep(3600)
    if fault == "escape":
        escapee = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(120)"],
            start_new_session=True,  # leaves the group, keeps stdout open
        )
        with open(os.environ["TXN_GIT_PIDFILE"], "w", encoding="utf-8") as handle:
            handle.write(str(escapee.pid))
    print("a" * 40, flush=True)
sys.exit(0)
"""

INSTALL = r"""
import logging
from pathlib import Path
from chunker.grammar_management.core import GrammarInstaller

cache, build_timeout = Path(ARGS[0]), float(ARGS[1])
commit_timeout = float(ARGS[2]) if len(ARGS) > 2 else None
messages = []


class Collect(logging.Handler):
    def emit(self, record):
        messages.append(record.getMessage())


logging.getLogger().addHandler(Collect(level=logging.WARNING))
logging.getLogger().setLevel(logging.WARNING)
installer = GrammarInstaller(cache_dir=cache, build_timeout=build_timeout)
if commit_timeout is not None:
    # Only the commit lookup gets the short limit; the build steps before it
    # keep ``build_timeout``, so a slow ``make`` cannot reach the deadline.
    run_staged = installer._run_staged

    def _run_staged(staging, argv, *, what, **kwargs):
        if what == "Git rev-parse":
            kwargs["timeout"] = commit_timeout
        return run_staged(staging, argv, what=what, **kwargs)

    installer._run_staged = _run_staged
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


def _installer(
    cache: Path,
    env: dict[str, str],
    *,
    timeout: float = 120.0,
    commit_timeout: float | None = None,
    pauses=(),
):
    args = (
        [cache, timeout] if commit_timeout is None else [cache, timeout, commit_timeout]
    )
    return Child(INSTALL, args, pauses=pauses, env=env)


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
        for directory in (root / "builds" / ".txn-retired").rglob("locked"):
            directory.chmod(0o700)
    assert result.entries_removed == 1
    assert result.bytes_freed == 17  # held.bin was not unlinked, so not counted
    # Reported once, for the file that failed (Claude round 2, finding 2).
    assert sum("held.bin" in e for e in result.errors) == 1
    assert len(result.errors) == len(set(result.errors))
    leftovers = list((root / "builds" / ".txn-retired").rglob("held.bin"))
    assert [p.read_bytes() for p in leftovers] == [b"h" * 19]
    # A later prune claims the garbage and counts it then, once.
    again = _transactions.prune_entries(root, "builds", cutoff=cutoff)
    assert (again.entries_removed, again.bytes_freed, again.errors) == (0, 19, ())
    assert not list((root / "builds" / ".txn-retired").rglob("held.bin"))


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
            (cache / "downloads" / ".txn-staging").glob("*/tree-sitter-baml")
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
    staging, [sys.executable, "-c", ARGS[2], pidfile], cwd=staging.path("builds"), timeout=60
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
        (staged_a,) = (cache / "builds" / ".txn-staging").glob("*/baml/libbaml.so")
        staged_digest = sha256(staged_a.read_bytes()).hexdigest()

        assert _install(cache, _env(shim, repo_b))["success"]
        assert (cache / "builds" / "baml" / "libbaml.so").is_file()
        for namespace, name in (("downloads", "tree-sitter-baml"), ("builds", "baml")):
            assert (
                _transactions.remove_entry(cache, namespace, name).entries_removed == 1
            )

        # A's own staged artifact is untouched by B and by the removal.
        assert sha256(staged_a.read_bytes()).hexdigest() == staged_digest
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
    garbage = cache / "downloads" / ".txn-retired" / operation / "tree-sitter-baml"
    assert (garbage / "generation.txt").read_text(encoding="utf-8") == "old"
    assert (
        cache / "downloads" / ".txn-staging" / operation / "tree-sitter-baml"
    ).is_dir()

    result = _transactions.prune_entries(cache, "downloads", cutoff=OLD)
    assert result.errors == ()
    assert not (cache / "downloads" / ".txn-retired" / operation).exists()
    # staging is retained
    assert (cache / "downloads" / ".txn-staging" / operation).is_dir()

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
            / "downloads"
            / ".txn-staging"
            / event["operation_id"]
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
    (staging.path("downloads") / "x").mkdir()
    with pytest.raises(_transactions.NestedRootError):
        _transactions.publish_entry(staging, "downloads", "x")
    assert (staging.path("downloads") / "x").is_dir()
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
    emit("done", error=str(error), transaction=isinstance(error, _transactions.CacheTransactionError))
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
    assert done["error"] and done["transaction"]


def test_discarded_staging_is_retired_then_deleted(tmp_path):
    """Claude N6: discard retires each namespace's staging in place first."""
    root = tmp_path / "cache"
    root.mkdir()
    staging = _transactions.create_staging(root)
    (staging.path("builds") / "baml").mkdir()
    (staging.path("builds") / "baml" / "lib.so").write_bytes(b"l" * 43)
    result = _transactions.discard_staging(staging)
    assert result.errors == () and result.bytes_freed == 43
    for namespace in ("downloads", "builds"):
        assert not staging.path(namespace).exists()
        retired = root / namespace / ".txn-retired" / staging.operation_id
        assert not retired.exists()


CROSS_DEVICE = r"""
import json, logging, os, sys, time
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from chunker.grammar_management import _transactions as t
from chunker.grammar_management.core import GrammarInstaller, GrammarManager

root, scratch = Path(sys.argv[2]), Path(sys.argv[3])
outcomes = {}
warnings = []


class Collect(logging.Handler):
    def emit(self, record):
        warnings.append(record.getMessage())


logging.getLogger().addHandler(Collect(level=logging.WARNING))
logging.getLogger().setLevel(logging.WARNING)


def control_folders_clean():
    # Each .txn-staging holds only its marker; .txn-retired has no op folders.
    leftovers = []
    for namespace in ("downloads", "builds"):
        for folder in (root / namespace / ".txn-staging", root / namespace / ".txn-retired"):
            if folder.exists():
                leftovers += [str(p) for p in folder.iterdir() if p.name != ".txn-keep"]
    return leftovers


def inodes():
    return [os.lstat(root / "downloads" / "tree-sitter-baml").st_ino,
            os.lstat(root / "builds" / "baml").st_ino]
try:
    for namespace in ("downloads", "builds"):
        mount_tmpfs(root / namespace)  # separate filesystems inside the root
    outcomes["split"] = all(
        (root / n).stat().st_dev != root.stat().st_dev for n in ("downloads", "builds")
    )
    old = root / "builds" / "expired"
    old.mkdir()
    (old / "lib.so").write_bytes(b"e" * 9)
    os.utime(old / "lib.so", (1, 1))
    os.utime(old, (1, 1))
    installer = GrammarInstaller(cache_dir=root, build_timeout=120)
    url = "https://github.com/example/tree-sitter-baml"
    outcomes["install"] = installer.install_grammar("baml", url)[:2]
    outcomes["clean_after_install"] = control_folders_clean()
    before = inodes()
    outcomes["reinstall"] = installer.install_grammar("baml", url)[:2]  # retires
    # Republication really replaced both entries (a cross-device rename would
    # leave the old generation and only log a warning).
    outcomes["entries_replaced"] = [a != b for a, b in zip(before, inodes())]
    outcomes["clean_after_reinstall"] = control_folders_clean()
    outcomes["published"] = sorted(
        p.name for n in ("downloads", "builds") for p in (root / n).iterdir()
        if not p.name.startswith(".")
    )
    manager = GrammarManager(
        user_dir=root / "grammars", package_dir=scratch / "package", cache_dir=root
    )
    stats = manager.cleanup_cache(older_than_days=30)
    outcomes["cleanup"] = [stats["files_removed"], stats["bytes_freed"], stats["errors"]]
    outcomes["removed"] = list(manager.remove_grammar("baml", clean_cache=True))
    outcomes["left"] = sorted(
        p.name for n in ("downloads", "builds") for p in (root / n).iterdir()
        if not p.name.startswith(".")
    )
    outcomes["clean_at_end"] = control_folders_clean()
    outcomes["warnings"] = warnings
finally:
    unmount_all()
print(json.dumps(outcomes))
"""


@POSIX_SHIM
def test_split_mount_namespaces_install_republish_prune_and_remove(tmp_path, shim):
    """Maintainer decision (2026-11-01): split-mount roots keep working.

    Real tmpfs mounts at ``downloads/`` and ``builds/`` make each namespace a
    separate filesystem. Staging and retirement live inside each namespace,
    so a real install, a republication, cleanup and removal all succeed.
    Mutation ``retire_outside_namespace`` (retire into a root-level folder)
    fails with ``EXDEV``.
    """
    root = tmp_path / "cache"
    root.mkdir()
    repo = _repo(tmp_path / "repo")
    env = _env(shim, repo)
    result = run_mounting(CROSS_DEVICE, [root, tmp_path], env=env)
    assert result.returncode == 0, result.stderr[-3000:]
    outcomes = json.loads(result.stdout.strip().splitlines()[-1])
    assert outcomes == {
        "split": True,
        "install": [True, None],
        "clean_after_install": [],
        "reinstall": [True, None],
        "entries_replaced": [True, True],
        "clean_after_reinstall": [],
        "published": ["baml", "expired", "tree-sitter-baml"],
        "cleanup": [1, 9, []],
        "removed": [True, None],
        "left": [],
        "clean_at_end": [],
        "warnings": [],
    }


def test_scans_ignore_hidden_transaction_folders(tmp_path):
    """Listing, discovery, analyzers and cleanup never see ``.txn-*`` folders."""
    from chunker.grammar_management.cli import ComprehensiveGrammarCLI
    from chunker.grammar_management.core import GrammarRegistry
    from chunker.languages.compatibility.grammar_analyzer import GrammarAnalyzer

    cache = tmp_path / "cache"
    cli = ComprehensiveGrammarCLI(cache_dir=cache)
    grammars = cli.user_grammars_dir
    for namespace_dir in (grammars, cache / "downloads", cache / "builds"):
        for hidden in (".txn-staging", ".txn-retired"):
            planted = namespace_dir / hidden / ("0" * 32)
            planted.mkdir(parents=True)
            (planted / "libhidden.so").write_bytes(b"x")
            os.utime(planted / "libhidden.so", (1, 1))
            os.utime(planted, (1, 1))
            os.utime(planted.parent, (1, 1))
    assert not any(
        key.startswith(".") or entry["language"].startswith(".")
        for key, entry in cli._get_all_grammars(show_all=True).items()
    )
    registry = GrammarRegistry(
        user_dir=grammars, package_dir=tmp_path / "pkg", cache_dir=cache
    )
    assert "hidden" not in registry.discover_grammars()
    assert GrammarAnalyzer(grammars)._discover_supported_languages() == []
    fallback = cli._cleanup_cache_fallback(1)
    assert fallback["files_removed"] == 0 and fallback["errors"] == []
    pruned = _transactions.prune_entries(cache, "builds", cutoff=time.time() + 3600)
    # Neither folder is an entry. Retired garbage is claimed and deleted (its
    # one byte is counted); staging is never pruned.
    assert (pruned.entries_removed, pruned.skipped, pruned.errors) == (0, (), ())
    assert pruned.bytes_freed == 1
    assert not (cache / "builds" / ".txn-retired" / ("0" * 32)).exists()
    for namespace_dir in (grammars, cache / "downloads", cache / "builds"):
        assert (namespace_dir / ".txn-staging" / ("0" * 32) / "libhidden.so").is_file()
    for namespace_dir in (grammars, cache / "downloads"):
        assert (namespace_dir / ".txn-retired" / ("0" * 32) / "libhidden.so").is_file()


def test_unreadable_candidate_is_reported_and_others_still_pruned(tmp_path):
    """Claude finding 1: one bad entry never aborts the prune or its counts."""
    if sys.platform == "win32" or os.geteuid() == 0:
        pytest.skip("mode 000 denial is a POSIX, non-root contract")
    root = tmp_path / "cache"
    root.mkdir()
    _transactions.open_cache_root(root)
    first = _seed(root / "builds" / "a-first", {"lib.so": b"a" * 11})
    _seed(root / "builds" / "b-bad", {"sub/held.bin": b"h" * 5})
    last = _seed(root / "builds" / "c-last", {"lib.so": b"c" * 13})
    (root / "builds" / "b-bad" / "sub").chmod(0)
    try:
        result = _transactions.prune_entries(root, "builds", cutoff=time.time() - 86400)
    finally:
        for sub in (root / "builds").rglob("sub"):
            sub.chmod(0o700)
    assert result.entries_removed == 2
    assert result.bytes_freed == first + last
    assert result.skipped == ("b-bad",)
    assert len(result.errors) == 1 and "b-bad" in result.errors[0]
    assert sorted(p.name for p in (root / "builds").iterdir() if p.name[0] != ".") == [
        "b-bad"
    ]


ESCAPEE = r"""
import subprocess, sys
pidfile = sys.argv[1]
child = subprocess.Popen(
    [sys.executable, "-c", "import time; time.sleep(120)"],
    start_new_session=True,  # leaves the group but keeps our stdout open
)
open(pidfile, "w").write(str(child.pid))
"""


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX session escape")
def test_escaped_pipe_holder_fails_closed_without_blocking(tmp_path):
    """Claude finding 2: a reader still blocked means not confirmed empty.

    The leader starts a process in a new session that keeps the output pipe
    open. ``run_in_staging`` returns, reports ``group_empty=False``, and the
    staging is unpublishable and retained.
    """
    root = tmp_path / "cache"
    root.mkdir()
    staging = _transactions.create_staging(root)
    pidfile = tmp_path / "escapee.pid"
    try:
        run = _transactions.run_in_staging(
            staging,
            [sys.executable, "-c", ESCAPEE, str(pidfile)],
            cwd=staging.path("builds"),
            timeout=60,
        )
        assert run.returncode == 0 and not run.timed_out and not run.group_empty
        with pytest.raises(_transactions.CacheTransactionError, match="unpublishable"):
            _transactions.publish_entry(staging, "builds", "anything")
        retained = _transactions.discard_staging(staging)
        assert retained.skipped and staging.path("builds").is_dir()
    finally:
        _kill_pidfile(pidfile)


INTERRUPTED = r"""
from pathlib import Path
from chunker.grammar_management.core import GrammarInstaller

cache, pidfile = Path(ARGS[0]), Path(ARGS[1])
installer = GrammarInstaller(cache_dir=cache, build_timeout=120)
emit("ready")
wait()
try:
    installer.install_grammar("baml", "https://github.com/example/tree-sitter-baml")
    emit("done", interrupted=False)
except KeyboardInterrupt:
    import psutil
    pid = int(pidfile.read_text())
    try:
        alive = psutil.Process(pid).status() != psutil.STATUS_ZOMBIE
    except psutil.NoSuchProcess:
        alive = False
    staged = sorted(
        str(p) for p in (cache / "downloads" / ".txn-staging").glob("*/*")
        if p.name != ".txn-keep"
    )
    emit("done", interrupted=True, grandchild_alive=alive, staged=staged)
"""


@POSIX_SHIM
@pytest.mark.parametrize("point", ["run.after_launch", "run.waiting"])
def test_interrupted_run_never_leaves_a_live_writer_without_its_staging(
    tmp_path, shim, point
):
    """Codex P1/P2: SIGINT right after launch, or in the guarded wait.

    The signal is raised deterministically at the named seam point, once the
    clone's grandchild is writing into staging. The contract allows two safe
    outcomes: the group confirmed gone, or the staging retained. Because the
    guard opens immediately after ``Popen``, the group is confirmed gone here.
    Mutations ``launch_outside_guard`` (the launch point runs before the
    guard) and ``mark_after_launch`` (also no conservative marking before
    ``Popen``) leave a live writer, the second with its staging deleted.
    """
    cache = tmp_path / "cache"
    repo = _repo(tmp_path / "repo")
    pidfile = tmp_path / "grandchild.pid"
    env = _env(shim, repo, TXN_GIT_GRANDCHILD=str(pidfile), TXN_GIT_SLEEP="1")
    try:
        with participants() as children:
            child = Child(
                INTERRUPTED,
                [cache, pidfile],
                pauses=[interrupt_at(point, await_file=str(pidfile), program="git")],
                env=env,
            )
            children.append(child)
            child.expect("ready")
            child.release()
            done = child.finish()
        assert done["interrupted"]
        # The contract's disjunction: shutdown confirmed, or staging retained.
        assert not done["grandchild_alive"] or done["staged"], done
        assert not done["grandchild_alive"], done
    finally:
        _kill_pidfile(pidfile)
        _kill_pidfile(Path(str(pidfile) + ".leader"))


@pytest.mark.skipif(
    sys.platform == "win32" or shutil.which("make") is None,
    reason="the git shim is a POSIX script and the fixture builds with make",
)
@pytest.mark.parametrize("fault", ["timeout", "escape"])
def test_aborted_commit_lookup_fails_the_install(tmp_path, shim, fault):
    """Codex P2: a timed-out or unconfirmed ``git rev-parse`` fails the install.

    The commit is resolved before installation, so nothing is installed.
    Mutation ``swallow_commit_abort`` reports success.
    """
    cache = tmp_path / "cache"
    # No src/: the build is the real make fallback copying a prebuilt library.
    # Only rev-parse has the short limit; the build keeps 120 seconds, because
    # ``make`` can be slow to start (the Xcode shim on hosted macOS,
    # treesitter-chunker#606).
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "Makefile").write_text("all:\n\t@true\n", encoding="utf-8")
    shutil.copy2(
        _compile_probe_fixture(tmp_path, [SOURCE / "parser.c"]), repo / "libbaml.so"
    )
    _age(repo)
    pidfile = tmp_path / "escapee.pid"
    extra = {"TXN_GIT_REVPARSE": fault, "TXN_GIT_PIDFILE": str(pidfile)}
    try:
        done = _install(cache, _env(shim, repo, **extra), timeout=120, commit_timeout=3)
    finally:
        _kill_pidfile(pidfile)
    assert not done["success"]
    assert "Commit lookup aborted: Git rev-parse" in done["error"]
    assert not (cache / "grammars" / "libbaml.so").exists()
    assert not (cache / "downloads" / "tree-sitter-baml").exists()


def test_prune_stops_on_a_lock_timeout_with_truthful_partial_counts(
    tmp_path, monkeypatch
):
    """Claude round 2, finding 3: a later lock timeout keeps earlier counts.

    Another holder takes the lock just before the second candidate's section.
    The prune stops, reports the timeout, and returns the entry it already
    removed. Mutation ``abort_prune_on_lock_timeout`` loses the counts.
    """
    root = tmp_path / "cache"
    root.mkdir()
    _transactions.open_cache_root(root)
    size = _seed(root / "builds" / "first", {"lib.so": b"f" * 11})
    _seed(root / "builds" / "second", {"lib.so": b"s" * 11})
    held, release = threading.Event(), threading.Event()
    sections: list[str] = []

    def hold_lock() -> None:
        with _transactions.cache_lock(root):
            held.set()
            release.wait()

    def barrier(point, context):
        if point == "lock.before_acquire" and context["primitive"] == "prune_entries":
            sections.append(point)
            # 1: namespace check, 2: first candidate, 3: second candidate.
            if len(sections) == 3:
                threading.Thread(target=hold_lock, daemon=True).start()
                held.wait()

    monkeypatch.setattr(_transactions, "_BARRIER", barrier)
    try:
        result = _transactions.prune_entries(
            root, "builds", cutoff=time.time() + 3600, timeout=0.5
        )
    finally:
        release.set()
    assert (result.entries_removed, result.bytes_freed) == (1, size)
    assert len(result.errors) == 1 and result.errors[0].startswith("Stopped before ")
    assert "Timed out" in result.errors[0]
    remaining = [p.name for p in (root / "builds").iterdir() if p.name[0] != "."]
    assert len(remaining) == 1

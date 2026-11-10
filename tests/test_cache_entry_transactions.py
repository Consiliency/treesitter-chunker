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

ADMIT (treesitter-chunker#362) admits an installed grammar only under its
approved pin. Each install child pins ``baml`` through the public
``trusted_artifacts=`` argument with ``TXN_PIN_SHA256``: the digest of the
parent's own build of that fixture, computed before the install, independent
of what the installer builds. The parent builds with the installer's own
documented recipe (``_build_recipe.gcc_build_argv``, cwd = the fixture
repository), which gives the same bytes at any path on every platform
(treesitter-chunker#621, #607), so the installer runs the real ``gcc`` on
``PATH`` with no wrapper. The shim directory also holds a failing
``tree-sitter`` stub, so a host CLI can never be the fallback that runs.
A fixture that neither builds nor carries an explicit pin fails the test.
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

from chunker.grammar_management import _build_recipe, _transactions
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

PINS = r"""
import os
pins = {"baml": {"sha256": os.environ["TXN_PIN_SHA256"]}} if "TXN_PIN_SHA256" in os.environ else None
"""

INSTALL = (
    PINS
    + r"""
import logging
from pathlib import Path
from chunker.grammar_management.core import GrammarInstaller

cache, build_timeout = Path(ARGS[0]), float(ARGS[1])
commit_timeout = float(ARGS[2]) if len(ARGS) > 2 else None
messages = []
commit_limits = []  # each short limit actually applied to the commit lookup


class Collect(logging.Handler):
    def emit(self, record):
        messages.append(record.getMessage())


logging.getLogger().addHandler(Collect(level=logging.WARNING))
logging.getLogger().setLevel(logging.WARNING)
installer = GrammarInstaller(
    cache_dir=cache, build_timeout=build_timeout, trusted_artifacts=pins
)
fail_probe = os.environ.get("TXN_FAIL_COMPILER_PROBE") == "1"
if commit_timeout is not None or fail_probe:
    # Only the commit lookup gets the short limit; the build steps before it
    # keep ``build_timeout``, so a slow ``make`` cannot reach the deadline.
    # ``TXN_FAIL_COMPILER_PROBE=1`` makes the compiler's ``--version`` probe
    # exit nonzero (treesitter-chunker#621: a failed probe still installs).
    from chunker.grammar_management._transactions import StagedRun

    run_staged = installer._run_staged

    def _run_staged(staging, argv, *, what, **kwargs):
        if what == "Compiler version" and fail_probe:
            return StagedRun(1, "", "probe patched to fail", False, True)
        if what == "Git rev-parse" and commit_timeout is not None:
            kwargs["timeout"] = commit_timeout
            commit_limits.append(commit_timeout)
        return run_staged(staging, argv, what=what, **kwargs)

    installer._run_staged = _run_staged
emit("ready")
wait()
ok, error, info = installer.install_grammar("baml", "https://github.com/example/tree-sitter-baml")
build = info.metadata.get("build") if info is not None else None
emit(
    "done",
    success=ok,
    error=error,
    warnings=messages,
    commit_limits=commit_limits,
    build=build,
)
"""
)

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
    return _make_shim(tmp_path)


def _make_shim(tmp_path: Path) -> Path:
    """The ``git`` shim and a failing ``tree-sitter`` stub."""
    directory = tmp_path / "shim"
    directory.mkdir()
    git = directory / "git"
    git.write_text(SHIM.format(python=sys.executable), encoding="utf-8")
    git.chmod(0o755)
    # The CLI is the installer's last fallback; a failing stub keeps a host
    # ``tree-sitter`` from ever being the method that runs.
    cli = directory / "tree-sitter"
    cli.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    cli.chmod(0o755)
    return directory


_FIXTURE_DIGESTS: dict[Path, str | None] = {}


def _fixture_digest(repo: Path) -> str | None:
    """SHA-256 of ``repo``'s build with the installer's own gcc recipe.

    The recipe (cwd = ``repo``, relative sources, the platform link flags and
    the output name ``libbaml.so``) depends on neither the source nor the
    output path, so this equals the digest of what the installer builds from
    its staged copy, on every platform. A fixture without
    sources ships a prebuilt ``libbaml.so`` that the make fallback copies, so its
    digest is that file's. ``None`` when the fixture does not build (for example
    the FIFO-hang fixture).
    """
    if repo not in _FIXTURE_DIGESTS and not (repo / "src" / "parser.c").exists():
        prebuilt = repo / "libbaml.so"
        _FIXTURE_DIGESTS[repo] = (
            sha256(prebuilt.read_bytes()).hexdigest() if prebuilt.is_file() else None
        )
    if repo not in _FIXTURE_DIGESTS:
        found = shutil.which("gcc")
        assert found is not None, "the fixture pin is built with the installer's gcc"
        out_dir = repo.parent / f".{repo.name}-pin"
        out_dir.mkdir(exist_ok=True)
        output = out_dir / "libbaml.so"  # the installer's output name
        completed = subprocess.run(
            _build_recipe.gcc_build_argv(
                os.path.abspath(found),  # noqa: PTH100 - as the installer
                "baml",
                output,
                # The installer adds scanner.c when the grammar has one.
                has_scanner=(repo / "src" / "scanner.c").exists(),
            ),
            cwd=repo,
            capture_output=True,
            timeout=300,
            check=False,
        )
        _FIXTURE_DIGESTS[repo] = (
            sha256(output.read_bytes()).hexdigest()
            if completed.returncode == 0
            else None
        )
        shutil.rmtree(out_dir, ignore_errors=True)
    return _FIXTURE_DIGESTS[repo]


def _env(shim: Path, repo: Path, **extra: str) -> dict[str, str]:
    digest = _fixture_digest(repo)
    if digest is None and "TXN_PIN_SHA256" not in extra:
        # Never let an install run unpinned by accident: an unexpectedly
        # successful build would then fail admission for the wrong reason.
        pytest.fail(f"fixture {repo} does not build and has no explicit pin")
    return {
        **os.environ,
        "PATH": f"{shim}{os.pathsep}{os.environ.get('PATH', '')}",
        "TXN_GIT_FIXTURE": str(repo),
        **({"TXN_PIN_SHA256": digest} if digest else {}),
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
        # The installation records how it was built (treesitter-chunker#621).
        build = done["build"]
        assert build["method"] == "gcc", build
        assert build["compiler"]["family"] in {"gcc", "clang"}, build
        assert build["compiler"]["banner"], build
        assert build["platform"].startswith(sys.platform), build
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


@POSIX_SHIM
def test_failed_compiler_probe_still_installs(tmp_path, shim):
    """A failed ``gcc --version`` probe never fails the install.

    ``TXN_FAIL_COMPILER_PROBE=1`` makes the probe exit nonzero; the installed
    grammar records ``metadata.build.compiler`` as ``None``
    (treesitter-chunker#621). Mutation ``probe_failure_fails_install`` fails
    the install.
    """
    cache = tmp_path / "cache"
    repo = _repo(tmp_path / "repo")
    done = _install(cache, _env(shim, repo, TXN_FAIL_COMPILER_PROBE="1"))
    assert done["success"], done
    assert done["build"]["method"] == "gcc", done
    assert done["build"]["compiler"] is None, done
    assert (cache / "grammars" / "libbaml.so").is_file()


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
    # Pin the prebuilt library, so that under the mutation the make fallback's
    # copy would be admitted and installed: the test then fails on success,
    # not merely on a different error message.
    pin = sha256((repo / "libbaml.so").read_bytes()).hexdigest()
    env = _env(shim, repo, TXN_GIT_FIFO="src/hang.h", TXN_PIN_SHA256=pin)
    done = _install(cache, env, timeout=3)
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
    """Installer A pauses at its commit section; B installs, then its entries go.

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
            pauses=[
                pause_at(
                    "lock.before_acquire", primitive="cache_lock", section="commit"
                )
            ],
        )
        children.append(a)
        a.expect("ready")
        a.release()
        a.expect("lock.before_acquire", primitive="cache_lock", section="commit")
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


CROSS_DEVICE = (
    PINS
    + r"""
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
    installer = GrammarInstaller(cache_dir=root, build_timeout=120, trusted_artifacts=pins)
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
)


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


INTERRUPTED = (
    PINS
    + r"""
from pathlib import Path
from chunker.grammar_management.core import GrammarInstaller

cache, pidfile = Path(ARGS[0]), Path(ARGS[1])
installer = GrammarInstaller(cache_dir=cache, build_timeout=120, trusted_artifacts=pins)
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
)


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
    # The override reached the real commit lookup, exactly once.
    assert done["commit_limits"] == [3.0]
    reason = {
        "timeout": "timed out",
        "escape": "left processes that could not be confirmed stopped",
    }[fault]
    assert done["error"] == f"Commit lookup aborted: Git rev-parse {reason}"
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


# treesitter-chunker#577: policy reservations, not measured runtime guarantees.
_READER_G = _transactions._GROUP_CONFIRM_DEADLINE
_READER_J = _transactions._READER_JOIN
_READER_FAULT = 2 * _READER_G + 2 * _READER_J
_READER_RUN = 4 * _READER_G + 2 * _READER_J
_READER_TEARDOWN = (1, 1, 2, 1, 1, 1)
_READER_STEPS = {
    "single": (1, 1, 1, "observe", 1, 1, 2, 1, 1, 1),
    "sticky": (1, 1, 1, "observe", 1, 1, "observe", 2, 1, 1, 1),
    "capture": (1, 1, "observe", 1, "observe", 2, 1, 1, 1),
}
_READER_ABORT = {
    "single": ((1, 7), (2, 7), (3, 7), (4, 7)),
    "sticky": ((1, 7), (2, 7), (3, 7), (4, 7), (5, 7), (6, 7), (7, 5)),
    "capture": ((1, 5), (2, 5), (3, 5), (4, 5), (5, 5)),
}


def _reader_steps(kind, fault=False):
    return tuple(
        (
            (_READER_FAULT if fault else _READER_RUN)
            if step == "observe"
            else step * _READER_G
        )
        for step in _READER_STEPS[kind]
    )


_READER_N = {kind: sum(_reader_steps(kind)) + _READER_G for kind in _READER_STEPS}
for _kind, _ceiling in _READER_N.items():
    for _fault in (False, True):
        _steps = _reader_steps(_kind, _fault)
        assert (
            max(
                sum(_steps),
                *(
                    sum(_steps[:index]) + tail * _READER_G
                    for index, tail in _READER_ABORT[_kind]
                ),
            )
            < _ceiling
            < SAFETY_TIMEOUT
        )

# Shared verbatim by the controller and child scripts; no product introspection.
_READER_WINDOWS_API = r"""
def reader_windows_api():
    import ctypes
    from ctypes import wintypes
    api = ctypes.WinDLL("kernel32", use_last_error=True)
    declarations = {
        "GetCurrentProcess": ([], wintypes.HANDLE),
        "OpenProcess": ([wintypes.DWORD, wintypes.BOOL, wintypes.DWORD], wintypes.HANDLE),
        "GetProcessTimes": ([wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4,
                            wintypes.BOOL),
        "WaitForSingleObject": ([wintypes.HANDLE, wintypes.DWORD], wintypes.DWORD),
        "GetExitCodeProcess": ([wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)],
                               wintypes.BOOL),
        "CloseHandle": ([wintypes.HANDLE], wintypes.BOOL),
    }
    for name, (arguments, result) in declarations.items():
        function = getattr(api, name)
        function.argtypes, function.restype = arguments, result
    return api


def reader_windows_creation(api, handle):
    import ctypes
    from ctypes import wintypes
    values = [wintypes.FILETIME() for _ in range(4)]
    if not api.GetProcessTimes(handle, *(ctypes.byref(value) for value in values)):
        error = ctypes.get_last_error()
        raise ctypes.WinError(error)
    value = (values[0].dwHighDateTime << 32) | values[0].dwLowDateTime
    if not 0 < value < 2**64:
        raise OSError("invalid native process creation identity")
    return value
"""

_READER_WINDOWS_FUNCTIONS = {}
if os.name == "nt":
    # Execute only this fixed test-owned source, also used by isolated children.
    exec(_READER_WINDOWS_API, _READER_WINDOWS_FUNCTIONS)  # noqa: S102

_READER_NATIVE = (
    _READER_WINDOWS_API
    + r"""
from multiprocessing.connection import Client, Listener
from multiprocessing.reduction import send_handle, recv_handle
from pathlib import Path
import psutil
import stat


def pipe_identity(handle):
    if os.name == "nt":
        import _winapi
        assert handle and _winapi.GetFileType(handle) == _winapi.FILE_TYPE_PIPE
        return [_winapi.FILE_TYPE_PIPE]
    value = os.fstat(handle)
    assert stat.S_ISFIFO(value.st_mode)
    return [value.st_dev, value.st_ino]


def close_duplicate(handle):
    if os.name == "nt":
        import _winapi
        _winapi.CloseHandle(handle)
    else:
        os.close(handle)


def command(expected):
    line = sys.stdin.readline()
    if not line or json.loads(line) == "abort":
        raise SystemExit(2)
    assert json.loads(line) == expected, (line, expected)


def identity():
    result = {"pid": os.getpid(), "created": psutil.Process().create_time()}
    if os.name == "nt":
        api = reader_windows_api()
        # GetCurrentProcess is a pseudo handle: never close it.
        result["created_filetime"] = reader_windows_creation(api, api.GetCurrentProcess())
    return result
"""
)

_READER_HOLDER = (
    _READER_NATIVE
    + r"""
address, family = json.loads(ARGS[0])
handle = None
try:
    with Listener(address, family=family) as listener:
        emit("holder-ready", **identity())
        with listener.accept() as connection:
            receipt = connection.recv()
            emit("writer", **receipt)
            handle = recv_handle(connection)
            assert pipe_identity(handle) == receipt["pipe"]
            emit("held", pipe=pipe_identity(handle))
            connection.send("held")
            command("revalidate")
            assert pipe_identity(handle) == receipt["pipe"]
            emit("still-holding", pipe=pipe_identity(handle))
            command("release")
finally:
    if handle is not None:
        close_duplicate(handle)
        handle = None
emit("closed")
"""
)

_READER_WRITER = (
    r"""
import json, os, sys
"""
    + _READER_NATIVE
    + r"""
config = json.loads(sys.argv[1])
sentinel = Path(config["sentinel"])
sentinel.write_text("writer-sentinel", encoding="utf-8")
fd = config["fd"]
handle = fd
if os.name == "nt":
    import msvcrt
    handle = msvcrt.get_osfhandle(fd)
with Client(config["address"], family=config["family"]) as connection:
    connection.send({**identity(), "sentinel": str(sentinel),
                     "pipe": pipe_identity(handle)})
    if config["holder"]:
        send_handle(connection, handle, config["holder"])
    assert connection.recv() == "held"
if config["capture"]:
    for stream, label in ((sys.stdout, "stdout"), (sys.stderr, "stderr")):
        stream.buffer.write((label + "-λ-" + "x" * 70000).encode("utf-8"))
        stream.buffer.flush()
"""
)

_READER_RUNNER = (
    _READER_NATIVE
    + r"""
root = Path(ARGS[0])
root.mkdir()
staging = _transactions.create_staging(root)
configs = json.loads(ARGS[1])
writer = ARGS[2]
G = float(ARGS[3])
recorded = []
real_start = threading.Thread.start
selected = 0
mode = "none"
count = 0
fired = False


def start(thread, *args, **kwargs):
    global count, fired
    if getattr(thread, "_target", None) is not _transactions._read_stream:
        return real_start(thread, *args, **kwargs)
    count += 1
    inject = not fired and mode != "none" and count == selected
    if inject and mode == "before":
        fired = True
        emit("paused", reader=count, timing=mode)
        command("fault")
        raise KeyboardInterrupt
    recorded.append(thread)  # before invoking real start, even if it raises
    result = real_start(thread, *args, **kwargs)
    if inject:
        fired = True
        emit("paused", reader=count, timing=mode)
        command("fault")
        raise KeyboardInterrupt
    return result


original_emit = emit
def emit(event, **fields):
    original_emit(event, emitted_at=time.monotonic(), **fields)

threading.Thread.start = start
emit("runner-ready", **identity())
for phase, config in enumerate(configs):
    command("start" if phase == 0 else "continue")
    recorded.clear()
    count = 0
    fired = False
    selected, mode = config["selected"], config["mode"]
    sentinel = staging.path("builds") / "writer-sentinel"
    config["sentinel"] = str(sentinel)
    result = None
    exception = None
    run_error = None
    try:
        result = _transactions.run_in_staging(
            staging, [sys.executable, "-c", writer, json.dumps(config)],
            cwd=staging.path("builds"), timeout=G,
        )
    except BaseException as error:
        run_error = error
        exception = type(error).__name__
    fields = {"phase": phase, "exception": exception,
              "exception_detail": None if run_error is None else repr(run_error)}
    if result is not None:
        fields.update(timed_out=result.timed_out, group_empty=result.group_empty,
                      returncode=result.returncode)
        if config["capture"]:
            fields["capture_exact"] = all(
                getattr(result, stream) == stream + "-λ-" + "x" * 70000
                for stream in ("stdout", "stderr")
            )
    if run_error is not None or not config["capture"] or phase == len(configs) - 1:
        if config["capture"] and run_error is None:
            published = _transactions.publish_entry(staging, "builds", "writer-sentinel")
            fields["published"] = published.read_text(encoding="utf-8") == "writer-sentinel"
        disposal = _transactions.discard_staging(staging)
        fields.update(skipped=list(map(str, disposal.skipped)), errors=list(disposal.errors),
                      paths=[str(staging.path(ns)) for ns in ("downloads", "builds")],
                      exists=[staging.path(ns).is_dir() for ns in ("downloads", "builds")],
                      sentinel=sentinel.exists())
    emit("snapshot", **fields)
    command("released")
    deadline = time.monotonic() + G
    failures = []
    for thread in recorded:
        try:
            thread.join(max(0, deadline - time.monotonic()))
        except RuntimeError as error:
            failures.append(repr(error))
        else:
            if thread.is_alive():
                failures.append("reader still alive")
    emit("joined", phase=phase, count=len(recorded), failures=failures)
    assert not failures, failures
    if run_error is not None and not (isinstance(run_error, KeyboardInterrupt) and fired):
        raise run_error
emit("done")
"""
)


def _expect_event_until(child, event, deadline):
    import queue

    while True:
        remaining = deadline - time.monotonic()
        assert remaining > 0, f"no {event} within local budget; {child.seen}"
        try:
            item = child._events.get(timeout=remaining)
        except queue.Empty:
            raise AssertionError(
                f"no {event} within local budget; {child.seen}; {child.stderr}"
            ) from None
        assert item is not None, f"EOF before {event}; {child.seen}; {child.stderr}"
        item["observed_at"] = time.monotonic()
        child.seen.append(item)
        if item["event"] == event:
            return item


def _wait_exit_until(process, deadline):
    return process.wait(timeout=max(0, deadline - time.monotonic()))


def _reader_command(child, command):
    assert child.process.stdin is not None
    child.seen.append({"command": command, "sent_at": time.monotonic()})
    child.process.stdin.write(json.dumps(command) + "\n")
    child.process.stdin.flush()


def _reader_address(directories):
    from multiprocessing.connection import arbitrary_address
    from uuid import uuid4

    family = "AF_PIPE" if os.name == "nt" else "AF_UNIX"
    address = arbitrary_address(family)
    if family == "AF_UNIX" and len(os.fsencode(address)) + 1 > (
        108 if sys.platform == "linux" else 104
    ):
        if sys.platform == "linux":
            address = "\0txn-reader-" + uuid4().hex
        else:
            import tempfile

            directory = Path(tempfile.mkdtemp(prefix="r-"))
            directories.append(directory)
            assert stat.S_IMODE(directory.stat().st_mode) == 0o700
            address = str(directory / "p")
            assert (
                len(os.fsencode(address)) + 1 <= 104
            ), "AF_UNIX address exceeds sun_path"
    return address, family


class _ReaderReceipt:
    """Controller-hosted no-holder endpoint, listening before R starts."""

    def __init__(self):
        import queue
        from multiprocessing.connection import Listener

        self.directories = []
        self.address, self.family = _reader_address(self.directories)
        self.listener = Listener(self.address, family=self.family)
        self._events = queue.Queue()
        self.seen = []
        self.stderr = ""
        self.connection = None
        self.thread = threading.Thread(target=self._receive, daemon=True)
        self.thread.start()

    def _receive(self):
        try:
            with self.listener.accept() as connection:
                self.connection = connection
                self._events.put({"event": "writer", **connection.recv()})
                connection.send("held")
        except (OSError, EOFError) as error:
            self.stderr = repr(error)
        finally:
            self._events.put(None)

    def _wake(self, deadline):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("receipt wake deadline expired")
        if self.family == "AF_UNIX":
            import socket

            with socket.socket(socket.AF_UNIX) as wake:
                wake.settimeout(remaining)
                wake.connect(self.address)
            return

        import _winapi

        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("receipt wake deadline expired")
            try:
                # Zero uses the listener's default infinite wait, not a poll.
                _winapi.WaitNamedPipe(self.address, max(1, int(remaining * 1000)))
                if time.monotonic() >= deadline:
                    raise TimeoutError("receipt wake deadline expired")
                handle = _winapi.CreateFile(
                    self.address,
                    _winapi.GENERIC_READ | _winapi.GENERIC_WRITE,
                    0,
                    _winapi.NULL,
                    _winapi.OPEN_EXISTING,
                    0,
                    _winapi.NULL,
                )
            except OSError as error:
                if getattr(error, "winerror", None) not in (
                    _winapi.ERROR_PIPE_BUSY,
                    _winapi.ERROR_SEM_TIMEOUT,
                ):
                    raise
            else:
                _winapi.CloseHandle(handle)
                return

    def close(self, deadline):
        # Capture only the writer connection; the wake's connection owns itself.
        errors = []
        connection = self.connection
        if self.thread.is_alive() and connection is None:
            try:
                self._wake(deadline)
            except OSError as error:
                errors.append(f"receipt wake: {error!r}")
        try:
            self.listener.close()
        except OSError as error:
            errors.append(f"receipt listener close: {error!r}")
        if connection is not None:
            try:
                connection.close()
            except OSError as error:
                errors.append(f"receipt connection close: {error!r}")
        try:
            self.thread.join(max(0, deadline - time.monotonic()))
        except RuntimeError as error:
            errors.append(f"receipt join: {error!r}")
        if self.thread.is_alive():
            errors.append("controller receipt thread still live")
        for directory in self.directories:
            try:
                directory.rmdir()
            except OSError as error:
                errors.append(f"receipt directory {directory}: {error!r}")
        return errors


def _reader_windows_stopped(receipt, observation):
    """Sample cessation once on an identity-pinned Windows process handle.

    Object visibility is not liveness. A zero-time sample is not a second
    blocking wait. Unknown identity/state and incomplete diagnostics fail.
    """
    import ctypes
    from ctypes import wintypes

    pid, expected = receipt.get("pid"), receipt.get("created_filetime")
    if type(pid) is not int or not 0 < pid < 2**32:
        raise OSError("invalid owned writer PID")
    if type(expected) is not int or not 0 < expected < 2**64:
        raise OSError("missing or invalid native writer creation identity")
    api = _READER_WINDOWS_FUNCTIONS["reader_windows_api"]()
    creation = _READER_WINDOWS_FUNCTIONS["reader_windows_creation"]
    # SYNCHRONIZE | PROCESS_QUERY_LIMITED_INFORMATION; non-inheritable.
    handle = api.OpenProcess(0x00100000 | 0x1000, False, pid)
    if not handle:
        error = ctypes.get_last_error()
        observation["open"] = {"error": error}
        if error == 87:
            # A positive valid PID may have vanished. No handle means no
            # kernel-state proof: only independent absence is accepted here.
            try:
                process = psutil.Process(pid)
                observation["absence"] = {
                    "result": "identity still observable",
                    "created": process.create_time(),
                }
            except psutil.NoSuchProcess:
                observation.update(
                    absence={"result": "NoSuchProcess"}, decision="absent"
                )
                return
        raise ctypes.WinError(error)
    observation["open"] = {"success": True, "at": time.monotonic()}
    try:
        observed = creation(api, handle)
        observation["observed_filetime"] = observed
        observation["identity"] = "matched" if observed == expected else "different"
        if observed == expected:
            state = api.WaitForSingleObject(handle, 0)
            state_error = ctypes.get_last_error() if state == 0xFFFFFFFF else None
            observation["state"] = {
                "result": state,
                "error": state_error,
                "at": time.monotonic(),
            }
        else:
            state = None
        code = wintypes.DWORD()
        if not api.GetExitCodeProcess(handle, ctypes.byref(code)):
            error = ctypes.get_last_error()
            observation["exit_code"] = {"error": error}
            raise ctypes.WinError(error)
        observation["exit_code"] = {"value": code.value}
        if observed != expected:
            observation["decision"] = "different identity"
            return
        if state == 0:
            # 259 can be a genuine terminal code; state alone establishes exit.
            observation["decision"] = "signaled"
            return
        if state == 258:
            observation["decision"] = "not stopped"
            raise AssertionError("identity-matched W still live")
        if state == 0xFFFFFFFF:
            raise ctypes.WinError(state_error)
        raise OSError(f"unexpected native process state {state}")
    finally:
        primary = sys.exc_info()[1]
        if api.CloseHandle(handle):
            observation["close"] = {"success": True}
        else:
            error = ctypes.get_last_error()
            observation["close"] = {"error": error}
            observation["decision"] = "observation failed"
            close_error = ctypes.WinError(error)
            if primary is not None:
                primary.add_note(f"process handle close failed: {close_error!r}")
            else:
                raise close_error


def _reader_writer_stopped(receipt, observations=None, *, phase=None, reason="body"):
    if os.name == "nt":
        observation = {
            "pid": receipt.get("pid"),
            "receipt_filetime": receipt.get("created_filetime"),
            "phase": phase,
            "reason": reason,
            "started_at": time.monotonic(),
            "open": "not attempted",
            "observed_filetime": "not applicable",
            "identity": "unknown",
            "absence": "not applicable",
            "state": "not applicable",
            "exit_code": "not applicable",
            "close": "not applicable",
            "decision": "observation failed",
        }
        if observations is not None:
            observations.append(observation)
        try:
            _reader_windows_stopped(receipt, observation)
        except (OSError, psutil.Error, AssertionError) as error:
            observation["error"] = repr(error)
            observation["native_error"] = getattr(error, "winerror", None)
            if observation["decision"] != "not stopped":
                observation["decision"] = "observation failed"
            raise
        finally:
            observation["finished_at"] = time.monotonic()
        return
    try:
        process = psutil.Process(receipt["pid"])
        assert process.create_time() != receipt["created"], "W not reaped by R"
    except psutil.NoSuchProcess:
        pass
    if os.name != "nt":
        for process in psutil.process_iter():
            try:
                assert not (
                    os.getpgid(process.pid) == receipt["pid"]
                    and process.status() != psutil.STATUS_ZOMBIE
                ), f"live W group member {process.pid}"
            except (ProcessLookupError, psutil.NoSuchProcess):
                pass


def _reader_case(
    tmp_path,
    request,
    *,
    selected=0,
    mode="none",
    hold=False,
    stream="stdout",
    kind="single",
    retain=True,
):
    """Real H/R/W; all public oracles execute in persistent R.

    The contract explicitly permits an R-only Thread.start wrapper, targeted
    only at _read_stream. It records every invoked real start in every phase;
    faults pause before start or after its return, then raise KeyboardInterrupt.
    This does not exercise Thread.start's native bootstrap window.
    The selected stream is identified by its _read_stream start ordinal
    (1 = stdout, 2 = stderr), which equals the stream argument because
    _start_readers starts stdout before stderr; any start-order change
    invalidates the parameter IDs and requires re-review.
    """
    ceiling = _READER_N[kind]
    assert request.node.get_closest_marker("timeout").args == (ceiling,)
    steps = _reader_steps(kind, mode != "none")
    children, endpoints, receipts, snapshots = [], [], [], []
    writer_observations = []
    address_directories = []
    holder = runner = None
    holder_closed = False
    holder_revalidation_sent = False
    holder_ack_attempted = False
    holder_reap_attempted = False
    runner_completion_attempted = False
    failed = False
    body_error = None
    try:
        if hold:
            address, family = _reader_address(address_directories)
            holder = Child(_READER_HOLDER, [json.dumps([address, family])])
            children.append(holder)
            ready = _expect_event_until(
                holder, "holder-ready", time.monotonic() + steps[0]
            )
            holder_pid = ready["pid"]
        else:
            holder_pid = 0
        configs = []
        for phase in range(2 if kind != "single" else 1):
            if not hold or phase:
                endpoint = _ReaderReceipt()
                endpoints.append(endpoint)
                address, family = endpoint.address, endpoint.family
            configs.append(
                {
                    "address": address,
                    "family": family,
                    "holder": holder_pid if phase == 0 else 0,
                    "fd": 1 if stream == "stdout" else 2,
                    "capture": kind == "capture",
                    "selected": selected,
                    "mode": mode if phase == 0 else "none",
                }
            )
        runner = Child(
            _READER_RUNNER,
            [tmp_path / "cache", json.dumps(configs), _READER_WRITER, str(_READER_G)],
        )
        children.append(runner)
        _expect_event_until(runner, "runner-ready", time.monotonic() + _READER_G)
        for phase, config in enumerate(configs):
            observation = time.monotonic() + (
                _READER_FAULT if mode != "none" else _READER_RUN
            )
            _reader_command(runner, "start" if phase == 0 else "continue")
            readiness = min(observation, time.monotonic() + _READER_G)
            source = holder if config["holder"] else endpoints[phase - int(hold)]
            receipt = _expect_event_until(source, "writer", readiness)
            receipts.append(receipt)
            assert (
                Path(receipt["sentinel"]).read_text(encoding="utf-8")
                == "writer-sentinel"
            )
            if config["holder"]:
                _expect_event_until(holder, "held", readiness)
            if mode != "none" and phase == 0:
                _expect_event_until(runner, "paused", readiness)
                observation = time.monotonic() + _READER_FAULT
                _reader_command(runner, "fault")
            try:
                snapshot = _expect_event_until(runner, "snapshot", observation)
            except AssertionError as error:
                raise AssertionError("no pre-release snapshot") from error
            snapshots.append(snapshot)
            assert snapshot["exception"] == (
                "KeyboardInterrupt" if config["mode"] != "none" else None
            )
            if config["mode"] == "none":
                assert snapshot["timed_out"] is False
                assert snapshot["group_empty"] is (not bool(config["holder"]))
                assert snapshot["returncode"] == 0
            if kind == "capture":
                assert snapshot["capture_exact"]
                if phase == len(configs) - 1:
                    assert snapshot["published"]
            if "skipped" in snapshot:
                assert snapshot["exists"] == [retain, retain]
                assert snapshot["sentinel"] is retain
                assert set(snapshot["skipped"]) == (
                    set(snapshot["paths"]) if retain else set()
                )
                if not retain:
                    assert not snapshot["errors"]
                for path, exists in zip(
                    snapshot["paths"], snapshot["exists"], strict=True
                ):
                    assert Path(path).is_dir() is exists
            if config["holder"]:
                holder_revalidation_sent = True
                _reader_command(holder, "revalidate")
                _expect_event_until(holder, "still-holding", observation)
                holder_ack_attempted = True
                _reader_command(holder, "release")
                _expect_event_until(holder, "closed", time.monotonic() + _READER_G)
                holder_closed = True
            barrier = time.monotonic() + (
                _READER_G if phase + 1 < len(configs) else 2 * _READER_G
            )
            runner_completion_attempted = True
            _reader_command(runner, "released")
            if config["holder"]:
                holder_reap_attempted = True
                assert _wait_exit_until(holder.process, barrier) == 0
            joined = _expect_event_until(runner, "joined", barrier)
            assert not joined["failures"]
            expected_readers = (
                config["selected"] - int(config["mode"] == "before")
                if config["mode"] != "none"
                else 2
            )
            assert joined["count"] == expected_readers
            _reader_writer_stopped(receipt, writer_observations, phase=phase)
            assert time.monotonic() < barrier
            runner_completion_attempted = False
        runner_completion_attempted = True
        _expect_event_until(runner, "done", barrier)
        assert _wait_exit_until(runner.process, barrier) == 0
    except BaseException as error:
        failed = True
        body_error = error
        raise
    finally:
        # Abort order: H closure/reap, R completion/fallback, W identity,
        # controller drainage. Never use Child's hidden 240-second waits.
        teardown_errors = []
        if holder is not None and holder.process.poll() is None:
            if not holder_closed and not holder_ack_attempted:
                deadline = time.monotonic() + _READER_G
                try:
                    if not holder_revalidation_sent:
                        _reader_command(holder, "revalidate")
                        _expect_event_until(holder, "still-holding", deadline)
                    _reader_command(holder, "release")
                    _expect_event_until(holder, "closed", deadline)
                    holder_closed = True
                except (OSError, AssertionError) as error:
                    teardown_errors.append(str(error))
            deadline = time.monotonic() + _READER_G
            if not holder_closed or holder_reap_attempted:
                teardown_errors.append("forced H termination")
                try:
                    holder.process.terminate()
                except OSError as error:
                    teardown_errors.append(f"H terminate: {error!r}")
            try:
                _wait_exit_until(holder.process, time.monotonic() + _READER_G / 2)
            except subprocess.TimeoutExpired:
                teardown_errors.append("forced H kill")
                try:
                    holder.process.kill()
                    _wait_exit_until(holder.process, deadline)
                except subprocess.TimeoutExpired:
                    teardown_errors.append("H not reaped after kill")
                except OSError as error:
                    teardown_errors.append(f"H kill/reap: {error!r}")
            except OSError as error:
                teardown_errors.append(f"H reap: {error!r}")
        if runner is not None and runner.process.poll() is None:
            try:
                # Never re-wait a failed shared barrier or final completion slot.
                if runner_completion_attempted:
                    raise subprocess.TimeoutExpired("R completion already attempted", 0)
                # Baseline may only return after H closure; collect its diagnosis.
                _reader_command(runner, "released")
                _wait_exit_until(runner.process, time.monotonic() + 2 * _READER_G)
            except (OSError, subprocess.TimeoutExpired):
                teardown_errors.append("forced R termination")
                deadline = time.monotonic() + _READER_G
                try:
                    runner.process.terminate()
                    _wait_exit_until(runner.process, time.monotonic() + _READER_G / 2)
                except subprocess.TimeoutExpired:
                    try:
                        runner.process.kill()
                        _wait_exit_until(runner.process, deadline)
                    except subprocess.TimeoutExpired:
                        teardown_errors.append("R not reaped after kill")
                    except OSError as error:
                        teardown_errors.append(f"R kill/reap: {error!r}")
                except OSError as error:
                    teardown_errors.append(f"R terminate/reap: {error!r}")
        writer_deadline = time.monotonic() + _READER_G
        for phase, receipt in enumerate(receipts):
            try:
                _reader_writer_stopped(
                    receipt,
                    writer_observations,
                    phase=phase,
                    reason="abort cleanup" if failed else "final cleanup",
                )
            except AssertionError as error:
                teardown_errors.append(str(error))
                # Only the positively matched leader, never a reaped PGID.
                try:
                    process = psutil.Process(receipt["pid"])
                    if process.create_time() == receipt["created"]:
                        process.kill()
                        process.wait(timeout=max(0, writer_deadline - time.monotonic()))
                except psutil.NoSuchProcess:
                    pass
                except psutil.TimeoutExpired:
                    teardown_errors.append("identity-matched W survived kill")
                except (psutil.Error, OSError) as cleanup_error:
                    teardown_errors.append(f"W kill/reap: {cleanup_error!r}")
            except (psutil.Error, OSError) as error:
                teardown_errors.append(f"W identity scan: {error!r}")
        deadline = time.monotonic() + _READER_G
        for endpoint in endpoints:
            teardown_errors.extend(endpoint.close(deadline))
        for child in children:
            for reader in child._readers:
                reader.join(max(0, deadline - time.monotonic()))
                if reader.is_alive():
                    teardown_errors.append("live controller reader")
            if not any(reader.is_alive() for reader in child._readers):
                for pipe in (
                    child.process.stdin,
                    child.process.stdout,
                    child.process.stderr,
                ):
                    pipe.close()
            if child.process.returncode != 0:
                teardown_errors.append(
                    f"child exit {child.process.returncode}: {child.stderr}"
                )
        for directory in address_directories:
            try:
                directory.rmdir()
            except OSError as error:
                teardown_errors.append(f"holder directory {directory}: {error!r}")
        import queue

        for child in children:
            while True:
                try:
                    item = child._events.get_nowait()
                except queue.Empty:
                    break
                if item is not None:
                    item["drained_at"] = time.monotonic()
                    child.seen.append(item)
        report = {
            "ceiling": ceiling,
            "steps": steps,
            "snapshots": snapshots,
            "writers": receipts,
            "writer_observations": writer_observations,
            "failed": failed,
            "teardown_errors": teardown_errors,
            "children": [
                {
                    "pid": c.process.pid,
                    "launcher_pid": c.process.pid,
                    "interpreter_identity": next(
                        (
                            event
                            for event in c.seen
                            if event["event"] in ("runner-ready", "holder-ready")
                        ),
                        None,
                    ),
                    "returncode": c.process.returncode,
                    "events": c.seen,
                    "stderr": c.stderr,
                    "readers_alive": [r.is_alive() for r in c._readers],
                }
                for c in children
            ],
        }
        print("READER_LIFECYCLE " + json.dumps(report))
        if body_error is not None:
            if teardown_errors:
                body_error.add_note("Reader teardown errors: " + repr(teardown_errors))
        else:
            assert not teardown_errors, teardown_errors


@pytest.mark.timeout(_READER_N["single"])
@pytest.mark.parametrize(
    ("selected", "stream"),
    [(1, "stdout"), (2, "stderr")],
    ids=["reader1-stdout", "reader2-stderr"],
)
def test_reader_start_interrupt_retains_staging(tmp_path, request, selected, stream):
    """Retention with H is correct; never fix it into confirmation or deletion.

    [reader2-stderr] is an exact kill for unfinished_reader_reports_safe_cleanup.
    [reader1-stdout] is not: stderr is never start-attempted, so both retain.
    """
    _reader_case(
        tmp_path, request, selected=selected, mode="after", hold=True, stream=stream
    )


@pytest.mark.timeout(_READER_N["single"])
def test_reader_start_interrupt_after_both_starts_confirms_and_discards(
    tmp_path, request
):
    """Fresh no-holder key distinguishes real registry ownership from blanket retention."""
    _reader_case(tmp_path, request, selected=2, mode="after", retain=False)


@pytest.mark.timeout(_READER_N["single"])
def test_reader_start_interrupt_after_first_start_retains_staging(tmp_path, request):
    """Retention is correct: stderr was never attempted; deletion is not a fix.

    Not a kill node for unfinished_reader_reports_safe_cleanup: stderr is never
    start-attempted, so fixed and mutant both retain.
    """
    _reader_case(tmp_path, request, selected=1, mode="after")


@pytest.mark.timeout(_READER_N["single"])
@pytest.mark.parametrize("selected", [1, 2], ids=["reader1", "reader2"])
def test_registered_unstarted_reader_preserves_interrupt(tmp_path, request, selected):
    _reader_case(tmp_path, request, selected=selected, mode="before")


@pytest.mark.timeout(_READER_N["capture"])
def test_staged_run_captures_both_streams_after_reader_registration(tmp_path, request):
    _reader_case(tmp_path, request, kind="capture", retain=False)


@pytest.mark.timeout(_READER_N["single"])
@pytest.mark.parametrize("stream", ["stdout", "stderr"])
def test_outside_pipe_holder_prevents_safe_staging_discard(tmp_path, request, stream):
    """Retention is correct while H holds a pipe, even though W exited.

    This retention must not be fixed into confirmation. Both parameters are
    kill nodes for unfinished_reader_reports_safe_cleanup.
    """
    _reader_case(tmp_path, request, hold=True, stream=stream)


@pytest.mark.timeout(_READER_N["sticky"])
def test_confirmed_later_run_does_not_clear_prior_staging_marks(tmp_path, request):
    _reader_case(tmp_path, request, hold=True, kind="sticky")

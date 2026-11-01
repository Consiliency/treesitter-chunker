"""Validation-record merge and containment (treesitter-chunker#370).

Cache transaction contract, Primitive 1. Every writer is a real
``GrammarValidator`` validating a real compiled BAML grammar, and every
pruner is a real ``GrammarManager.cleanup_cache``. Concurrent participants run
in separate processes and are ordered only by seam events (tests/txn_barrier.py).

The records are ``ok`` results from two distinct compiled revisions.

ADMIT (treesitter-chunker#362) requires pins for stored validation records:
an unpinned validator reports ``untrusted`` and never stores a record, and
failures are never stored. So every writer here gets ``trusted_artifacts`` with
its revision's reviewed fixture digest, and record keys come from ADMIT's
verdict-key accessor ``GrammarValidator._verdict_cache_key`` (the frozen
content/pin/environment key; the path-based ``_get_cache_key`` is gone).
Reconciled when ADMIT SL-core-2 (treesitter-chunker#562) merged main after
treesitter-chunker#560, per the roadmap runner's decision.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import signal
import subprocess
import sys
import threading
import time
from hashlib import sha256
from pathlib import Path

import pytest

from chunker.grammar_management import _transactions
from chunker.grammar_management.core import (
    GrammarManager,
    GrammarValidator,
    ValidationLevel,
)
from tests.test_compiled_grammar_analysis_contract import SOURCE, _compile_probe_fixture
from tests.txn_barrier import (
    ROOT,
    SAFETY_TIMEOUT,
    Child,
    pause_at,
    participants,
    run_with_tmpfs,
)

RECORDS = "validation_cache.json"

WRITER = r"""
from pathlib import Path
from chunker.grammar_management.core import GrammarValidator, ValidationLevel

cache, library, digest = Path(ARGS[0]), Path(ARGS[1]), ARGS[2]
validator = GrammarValidator(cache, trusted_artifacts={"baml": {"sha256": digest}})
emit("ready")
wait()
result = validator.validate_grammar(library, "baml", ValidationLevel.STANDARD)
key, _ = validator._verdict_cache_key(library, "baml", ValidationLevel.STANDARD)
emit("done", key=key, valid=result.is_valid, errors=result.errors)
"""

PRUNER = r"""
from pathlib import Path
from chunker.grammar_management.core import GrammarManager

cache, scratch = Path(ARGS[0]), Path(ARGS[1])
manager = GrammarManager(
    user_dir=scratch / "user", package_dir=scratch / "package", cache_dir=cache
)
emit("ready")
wait()
emit("done", stats=manager.cleanup_cache(older_than_days=30))
"""


@pytest.fixture(scope="module")
def revisions(tmp_path_factory) -> tuple[Path, Path]:
    """Compile BAML 0.1.0 and a 0.2.0 revision with different bytes."""
    root = tmp_path_factory.mktemp("baml-validation-revisions")
    (root / "a").mkdir()
    rev_a = _compile_probe_fixture(root / "a", [SOURCE / "parser.c"])
    text = (SOURCE / "parser.c").read_text(encoding="utf-8")
    assert text.count(".minor_version = 1,") == 1
    (root / "b").mkdir()
    revised = root / "b" / "parser.c"
    revised.write_text(
        text.replace(".minor_version = 1,", ".minor_version = 2,"), encoding="utf-8"
    )
    rev_b = _compile_probe_fixture(root / "b", [revised])
    assert sha256(rev_a.read_bytes()).digest() != sha256(rev_b.read_bytes()).digest()
    return rev_a, rev_b


def _digest(library: Path) -> str:
    """The reviewed fixture build's digest (supplied deliberately as its pin)."""
    return sha256(library.read_bytes()).hexdigest()


def _pins(library: Path) -> dict[str, dict[str, str]]:
    return {"baml": {"sha256": _digest(library)}}


def _key(validator: GrammarValidator, library: Path) -> str:
    key, _ = validator._verdict_cache_key(library, "baml", ValidationLevel.STANDARD)
    assert key is not None
    return key


def _records(cache: Path) -> dict:
    return json.loads((cache / RECORDS).read_text(encoding="utf-8"))


@pytest.mark.parametrize("first_writer", ["constructed_first", "constructed_second"])
def test_two_validators_keep_both_records(tmp_path, revisions, first_writer):
    """Both records survive whichever validator writes first.

    Both validators are built (and have read the empty record file) before
    either writes. The first writer pauses at ``json.before_replace`` while it
    holds the lock; the second is observed contending for it.
    Mutation ``stale_validation_snapshot`` (write the instance snapshot instead
    of merging) loses the first record.
    """
    cache = tmp_path / "cache"
    cache.mkdir()
    rev_a, rev_b = revisions
    with participants() as children:
        a = Child(
            WRITER,
            [cache, rev_a, _digest(rev_a)],
            pauses=[pause_at("json.before_replace")],
        )
        children.append(a)
        a.expect("ready")
        b = Child(
            WRITER,
            [cache, rev_b, _digest(rev_b)],
            pauses=[pause_at("json.before_replace")],
        )
        children.append(b)
        b.expect("ready")
        first, second = (a, b) if first_writer == "constructed_first" else (b, a)

        first.release()
        first.expect("json.before_replace", primitive="update_json_records")
        second.release()
        second.expect("lock.contended", primitive="update_json_records")
        first.release()
        first_done = first.finish()
        second.expect("json.before_replace", primitive="update_json_records")
        second.release()
        second_done = second.finish()

    assert first_done["valid"] and second_done["valid"]
    assert first_done["key"] != second_done["key"]
    records = _records(cache)
    for done in (first_done, second_done):
        assert records[done["key"]]["is_valid"] is True
        assert records[done["key"]]["level"] == "standard"
        assert records[done["key"]]["errors"] == []


def test_writer_and_pruner_keep_fresh_record(tmp_path, revisions):
    """The pruner merges into the fresh document and keeps the cutoff rule.

    The writer pauses at ``json.before_replace``; ``cleanup_cache`` is observed
    contending. Afterwards the writer's record and the unexpired record are
    kept, and only the expired record is removed and counted.
    Mutation ``pruner_stale_rewrite`` (read before the lock, write that read)
    loses the writer's record.
    """
    cache = tmp_path / "cache"
    cache.mkdir()
    now = time.time()
    seeded = {
        "expired": {"is_valid": True, "level": "basic", "timestamp": now - 40 * 86400},
        "recent": {"is_valid": True, "level": "basic", "timestamp": now - 86400},
    }
    (cache / RECORDS).write_text(json.dumps(seeded), encoding="utf-8")
    rev_a, _ = revisions
    with participants() as children:
        writer = Child(
            WRITER,
            [cache, rev_a, _digest(rev_a)],
            pauses=[pause_at("json.before_replace")],
        )
        children.append(writer)
        writer.expect("ready")
        pruner = Child(PRUNER, [cache, tmp_path])
        children.append(pruner)
        pruner.expect("ready")

        writer.release()
        writer.expect("json.before_replace", primitive="update_json_records")
        pruner.release()
        pruner.expect("lock.contended", primitive="update_json_records")
        writer.release()
        written = writer.finish()
        stats = pruner.finish()["stats"]

    records = _records(cache)
    assert set(records) == {written["key"], "recent"}
    assert records["recent"] == seeded["recent"]
    assert records[written["key"]]["is_valid"] is True
    assert stats["files_removed"] == 1
    assert stats["directories_cleaned"] == ["validation_cache"]
    assert stats["errors"] == []


def _symlink_or_skip(link: Path, target: Path) -> None:
    try:
        link.symlink_to(target)
    except OSError as error:
        if getattr(error, "winerror", None) == 1314:
            pytest.skip("this Windows account may not create symbolic links")
        raise


def test_symlinked_record_file_never_touches_outside_sentinel(
    tmp_path, revisions, caplog
):
    """A link at ``validation_cache.json`` is refused by reader, writer, pruner.

    Mutation ``follow_validation_symlink`` (open the record file following
    links) reads the outside document, reports nothing and replaces the link.
    """
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "sentinel.json"
    original = b'{"outside": {"timestamp": 0}}'
    sentinel.write_bytes(original)
    cache = tmp_path / "cache"
    cache.mkdir()
    _symlink_or_skip(cache / RECORDS, sentinel)
    rev_a, _ = revisions

    caplog.set_level(logging.WARNING, logger="chunker.grammar_management.core")
    validator = GrammarValidator(cache, trusted_artifacts=_pins(rev_a))  # constructs
    assert validator._cache == {}
    result = validator.validate_grammar(rev_a, "baml", ValidationLevel.STANDARD)
    assert result.is_valid
    load_and_write = [
        r.getMessage() for r in caplog.records if "link" in r.getMessage().lower()
    ]
    assert any(m.startswith("Failed to load validation cache") for m in load_and_write)
    assert any(
        m.startswith("Failed to cache validation result") for m in load_and_write
    )
    # The record is kept in the in-memory read cache only (never written back).
    key = _key(validator, rev_a)
    assert list(validator._cache) == [key]

    manager = GrammarManager(
        user_dir=tmp_path / "user", package_dir=tmp_path / "package", cache_dir=cache
    )
    stats = manager.cleanup_cache(older_than_days=30)
    assert len(stats["errors"]) == 1
    assert "Refusing to follow link" in stats["errors"][0]
    assert RECORDS in stats["errors"][0]
    assert stats["files_removed"] == 0

    assert sentinel.read_bytes() == original
    assert (cache / RECORDS).is_symlink()
    assert sorted(p.name for p in outside.iterdir()) == ["sentinel.json"]


def test_malformed_records_keep_writer_reset_and_pruner_refusal(tmp_path, revisions):
    """Today's malformed-document behavior is kept for both consumers."""
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / RECORDS).write_bytes(b"[1, 2]")
    manager = GrammarManager(
        user_dir=tmp_path / "user", package_dir=tmp_path / "package", cache_dir=cache
    )
    stats = manager.cleanup_cache(older_than_days=30)
    assert len(stats["errors"]) == 1 and "Malformed record file" in stats["errors"][0]
    assert (cache / RECORDS).read_bytes() == b"[1, 2]"

    rev_a, _ = revisions
    validator = GrammarValidator(cache, trusted_artifacts=_pins(rev_a))
    assert validator.validate_grammar(rev_a, "baml", ValidationLevel.STANDARD).is_valid
    key = _key(validator, rev_a)
    assert list(_records(cache)) == [key]


def test_threads_in_one_process_keep_both_records(tmp_path, revisions):
    """In-process writers serialize on the same root lock."""
    cache = tmp_path / "cache"
    cache.mkdir()
    validators = [
        GrammarValidator(cache, trusted_artifacts=_pins(library))
        for library in revisions
    ]
    keys: list[str] = []
    errors: list[BaseException] = []

    def write(validator: GrammarValidator, library: Path) -> None:
        try:
            assert validator.validate_grammar(
                library, "baml", ValidationLevel.STANDARD
            ).is_valid
            keys.append(_key(validator, library))
        except BaseException as error:  # pragma: no cover - reported below
            errors.append(error)

    threads = [
        threading.Thread(target=write, args=pair)
        for pair in zip(validators, revisions, strict=True)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == []
    assert set(_records(cache)) == set(keys) and len(keys) == 2


def test_lock_descriptor_is_not_inheritable_and_reentrant(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    _transactions.open_cache_root(root)
    with _transactions.cache_lock(root):
        (hold,) = (h for h in _transactions._HOLDS.values() if h.owner is not None)
        assert hold.lock_fd is not None
        assert os.get_inheritable(hold.lock_fd) is False
        with _transactions.cache_lock(root):
            assert hold.depth == 2
            if sys.platform != "win32":
                # A second spelling of the same root shares the hold.
                alias = tmp_path / "alias"
                alias.symlink_to(root, target_is_directory=True)
                with _transactions.cache_lock(alias):
                    assert hold.depth == 3
        assert hold.depth == 1
    lock = root / _transactions.LOCK_FILE_NAME
    assert lock.read_bytes() == b"\0"


FORK_CHILD = r"""
import os, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from chunker.grammar_management import _transactions

root = Path(sys.argv[2])
_transactions.open_cache_root(root)
with _transactions.cache_lock(root):
    pid = os.fork()
    if pid == 0:
        code = 1
        try:
            with _transactions.cache_lock(root, timeout=0.2):
                code = 2  # reused the parent's hold: exclusion broken
        except _transactions.CacheLockTimeoutError:
            code = 0
        finally:
            os._exit(code)
    _, status = os.waitpid(pid, 0)
sys.exit(os.waitstatus_to_exitcode(status))
"""


@pytest.mark.skipif(not hasattr(os, "fork"), reason="fork is POSIX-only")
def test_forked_child_must_acquire_again(tmp_path):
    """The at-fork handler drops inherited holds; the child cannot reuse them.

    The fork happens in a fresh single-threaded interpreter.
    """
    root = tmp_path / "root"
    root.mkdir()
    child = subprocess.run(
        [sys.executable, "-I", "-c", FORK_CHILD, str(ROOT), str(root)],
        capture_output=True,
        text=True,
        timeout=SAFETY_TIMEOUT,
        check=False,
    )
    assert child.returncode == 0, (child.returncode, child.stderr[-2000:])


@pytest.mark.parametrize("namespace", ["downloads", "builds", ".txn"])
def test_root_inside_initialized_root_namespace_is_refused(tmp_path, namespace):
    outer = tmp_path / "outer"
    outer.mkdir()
    _transactions.open_cache_root(outer)
    for inner in (outer / namespace, outer / namespace / "x" / "y"):
        inner.mkdir(parents=True, exist_ok=True)
        with pytest.raises(_transactions.NestedRootError):
            _transactions.open_cache_root(inner)
        assert not (inner / _transactions.LOCK_FILE_NAME).exists()
    # The validator still constructs; its record file is simply unavailable.
    validator = GrammarValidator(outer / namespace / "x")
    assert validator._cache == {}


def test_control_directories_keep_markers_against_empty_directory_sweep(tmp_path):
    """Decision D-c: helper directories are never empty, even after a crash."""
    from chunker.grammar_management.config import DirectoryManager, UserConfig

    root = tmp_path / "root"
    root.mkdir()
    _transactions.open_cache_root(root)
    control = root / _transactions.CONTROL_DIR_NAME
    (control / "staging" / _transactions.MARKER_NAME).unlink()
    _transactions.open_cache_root(root)  # a missing marker is created again
    config = UserConfig(tmp_path / "config.json")
    config.set("directories.base_dir", str(root))
    DirectoryManager(config).cleanup_empty_directories()
    for directory in (
        control,
        *(control / name for name in ("staging", "retired", "rollback")),
    ):
        assert (directory / _transactions.MARKER_NAME).is_file()


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX symlink semantics")
def test_linked_control_area_is_refused(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (root / _transactions.CONTROL_DIR_NAME).symlink_to(elsewhere)
    with pytest.raises(_transactions.ContainmentError):
        _transactions.open_cache_root(root)
    assert list(elsewhere.iterdir()) == []


FORK_PENDING = r"""
import os, signal, sys, threading
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from chunker.grammar_management import _transactions

root = Path(sys.argv[2])
_transactions.open_cache_root(root)
at_before, go, acquired = threading.Event(), threading.Event(), threading.Event()


def barrier(point, context):
    if point == "lock.before_acquire" and threading.current_thread().name == "worker":
        at_before.set()
        go.wait()


_transactions._BARRIER = barrier


def worker():
    with _transactions.cache_lock(root):
        acquired.set()
        threading.Event().wait()


threading.Thread(target=worker, name="worker", daemon=True).start()
at_before.wait()  # the worker's lock descriptor is open, acquisition pending
pid = os.fork()
if pid == 0:
    signal.pause()  # the forked child lingers until the test kills it
    os._exit(0)
print(pid, flush=True)
go.set()
acquired.wait()
os._exit(0)  # the holder dies while holding the lock
"""


@pytest.mark.skipif(not hasattr(os, "fork"), reason="fork is POSIX-only")
def test_fork_during_pending_acquisition_does_not_keep_the_lock(tmp_path):
    """A child forked while a thread is acquiring must not keep the lock alive.

    The worker has opened its lock descriptor and is paused at
    ``lock.before_acquire`` when the main thread forks. The worker then
    acquires and its process dies holding the lock. A fresh participant must
    acquire it. Mutation ``fork_keeps_pending_fd`` (register descriptors only
    once acquired) leaves the child holding the open file description.
    """
    root = tmp_path / "root"
    root.mkdir()
    holder = subprocess.Popen(
        [sys.executable, "-I", "-c", FORK_PENDING, str(ROOT), str(root)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    child = int(holder.stdout.readline())
    try:
        assert holder.wait(timeout=SAFETY_TIMEOUT) == 0, holder.stderr.read()
        with _transactions.cache_lock(root, timeout=10.0):
            pass
    finally:
        with contextlib.suppress(ProcessLookupError):
            os.kill(child, signal.SIGKILL)
        holder.stdout.close()
        holder.stderr.close()


FORK_LEAVE = r"""
import os, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from chunker.grammar_management import _transactions

root = Path(sys.argv[2])
other = root / "unrelated.bin"
other.write_bytes(b"x")
_transactions.open_cache_root(root)
mine = []
with _transactions.cache_lock(root):
    (hold,) = [h for h in _transactions._HOLDS.values() if h.owner is not None]
    numbers = {hold.lock_fd, hold.rootdir.fd}
    pid = os.fork()
    if pid == 0:
        # Reuse the numbers the at-fork handler freed for unrelated files.
        while not numbers <= set(mine):
            fd = os.open(other, os.O_RDONLY)
            mine.append(fd)
            if len(mine) > 64:
                break
if pid == 0:
    try:
        for fd in mine:
            os.fstat(fd)  # still open: the helper closed nothing of ours
    except OSError:
        os._exit(2)
    os._exit(0)
_, status = os.waitpid(pid, 0)
sys.exit(os.waitstatus_to_exitcode(status))
"""


@pytest.mark.skipif(not hasattr(os, "fork"), reason="fork is POSIX-only")
def test_forked_child_leaving_a_section_closes_nothing_of_its_own(tmp_path):
    """A child that leaves the parent's section normally must not release it.

    The child reuses the descriptor numbers the at-fork handler freed, then
    leaves the ``with`` block. Mutation ``release_in_forked_child`` (no owner
    PID check) unlocks and closes the child's unrelated descriptors, or raises
    ``EBADF``.
    """
    root = tmp_path / "root"
    root.mkdir()
    result = subprocess.run(
        [sys.executable, "-I", "-c", FORK_LEAVE, str(ROOT), str(root)],
        capture_output=True,
        text=True,
        timeout=SAFETY_TIMEOUT,
        check=False,
    )
    assert result.returncode == 0, (result.returncode, result.stderr[-2000:])


SPLIT_MOUNT = r"""
import json, logging, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from chunker.grammar_management.core import GrammarManager, GrammarValidator, ValidationLevel

cache, library, digest = Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4]
messages = []


class Collect(logging.Handler):
    def emit(self, record):
        messages.append(record.getMessage())


logging.getLogger().addHandler(Collect(level=logging.WARNING))
assert (cache / "grammars").stat().st_dev != cache.stat().st_dev, "not mounted"
validator = GrammarValidator(cache, trusted_artifacts={"baml": {"sha256": digest}})
assert validator.validate_grammar(library, "baml", ValidationLevel.STANDARD).is_valid
key, _ = validator._verdict_cache_key(library, "baml", ValidationLevel.STANDARD)
records = json.loads((cache / "validation_cache.json").read_text(encoding="utf-8"))
manager = GrammarManager(
    user_dir=cache / "grammars", package_dir=cache / "package", cache_dir=cache
)
stats = manager.cleanup_cache(older_than_days=30)
print(json.dumps({"stored": key in records, "reloaded": key in GrammarValidator(cache)._cache,
                  "errors": stats["errors"], "warnings": messages}))
"""


def test_split_mount_root_keeps_validation_records(tmp_path, revisions):
    """A separate filesystem at ``grammars/`` does not stop Primitive 1.

    Amendment A1 applies the same-device check only where a rename crosses
    from ``.txn/`` to a namespace; the record update replaces a file in the
    root directory, which main supports on split-mount roots.
    """
    cache = tmp_path / "cache"
    cache.mkdir()
    rev_a, _ = revisions
    result = run_with_tmpfs(
        cache / "grammars", SPLIT_MOUNT, [cache, rev_a, _digest(rev_a)]
    )
    assert result.returncode == 0, result.stderr[-3000:]
    report = json.loads(result.stdout.strip().splitlines()[-1])
    assert report == {"stored": True, "reloaded": True, "errors": [], "warnings": []}

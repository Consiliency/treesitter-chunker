#!/usr/bin/env python3
"""Trusted-controller producer of scope_root_metadata.v2; never run by a candidate.

Run with python -I -S. It reads only an independently identified, controller-owned
bare Git object store through hardened Git plumbing and never reads a working tree.
Store ownership and no-candidate-write history are controller preconditions, not
facts this tool authenticates. The output binds boundary metadata only, not
committed file content, and this is not a hostile-repository sandbox.

Ctrl-C limit (owner fallback for treesitter-chunker#512): the producer does not own
SIGINT, so a perfectly timed SIGINT can lose the first error and cut cleanup short.
Synchronous first-error, deadline, bounded cleanup and uncertainty rules still hold.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import selectors
import signal
import stat
import subprocess
import time

CAP = 64 * 1024 * 1024
WORK_SECONDS = 60.0
CLEANUP_SECONDS = 2.0
KILL_RESERVE_SECONDS = 1.0
WAIT_SLICE_SECONDS = 0.05
CHUNK = 65536
HEX_LEN = {"sha1": 40, "sha256": 64}
HEX = frozenset("0123456789abcdef")
BLOB_MODES = {b"100644", b"100755"}
# Denied before traversal. include.*/includeIf.* are refused because an include can
# hide a denied key (FREEZE-512 trust-contract hardening, root disposition Q1).
DENIED_CONFIG = {
    "core.alternaterefscommand",
    "core.worktree",
    "extensions.worktreeconfig",
}
DENIED_CONFIG_PREFIXES = ("include.", "includeif.")
# objects/info/http-alternates is an alternates mechanism too (disposition Q2).
ALTERNATES = ("objects/info/alternates", "objects/info/http-alternates")
FLAGS = [
    "--no-replace-objects",
    "--literal-pathspecs",
    "-c",
    "core.hooksPath=" + os.devnull,
    "-c",
    "core.fsmonitor=false",
    "-c",
    "protocol.allow=never",
    "-c",
    "protocol.file.allow=never",
]


class ScopeRefused(ValueError):  # noqa: N818 -- private contract names this exception
    def __init__(self, reason, path=None):
        super().__init__(reason)
        self.reason, self.path = reason, path


class CleanupUncertain(RuntimeError):  # noqa: N818
    """Owned process group or producer-created output could not be confirmed cleaned."""


def canonical(value):
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def environment():
    """Scratch Git environment; no inherited GIT_* variable survives."""
    return {
        "PATH": os.environ.get("PATH", os.defpath),
        "LC_ALL": "C",
        "HOME": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_SYSTEM": os.devnull,
        "GIT_NO_REPLACE_OBJECTS": "1",
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_OPTIONAL_LOCKS": "0",
        "GIT_NO_LAZY_FETCH": "1",
    }


def close_pipe(pipe):
    pipe.close()


class Runner:
    """Bounded Git plumbing runner: one shared work deadline, one cleanup expiry."""

    def __init__(self, gitdir, *, clock=time.monotonic, read=os.read, cap=CAP):
        self.gitdir, self.clock, self.read, self.cap = gitdir, clock, read, cap
        self.deadline = clock() + WORK_SECONDS
        self.cleanup_seconds = CLEANUP_SECONDS
        self.kill_reserve = KILL_RESERVE_SECONDS
        self.slice = WAIT_SLICE_SECONDS
        self.signals = (signal.SIGTERM, signal.SIGKILL)
        self.closer = close_pipe
        self.selector = selectors.DefaultSelector
        self.group_probe = os.killpg
        self.killer = os.killpg
        self.sleep = time.sleep
        self.journal = []
        self.waits = []
        self.reads = []
        self.cleanup_errors = []
        self.uncertain = False
        self.uncertain_cause = None

    def remaining(self):
        return self.deadline - self.clock()

    def expired(self):
        if self.remaining() <= 0:
            raise TimeoutError("git work deadline")

    def git(self, *args):
        """Return (exit code, stdout bytes) of one hardened Git command."""
        budget = self.remaining()
        self.journal.append((args[0] if args else "", budget))
        self.expired()
        argv = ["git", "--git-dir=" + self.gitdir, *FLAGS, *args]
        proc = subprocess.Popen(
            argv,
            cwd=self.gitdir,
            env=environment(),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
            close_fds=True,
            shell=False,
        )
        failed = None
        completed = False
        try:
            try:
                out = self.collect(proc)
                code = self.reap(proc)
                completed = True
            except (
                BaseException
            ) as exc:  # noqa: BLE001 -- first error is re-raised below
                failed = exc
        finally:
            if not completed:
                self.stop_guarded(proc, failed)
            late = self.close(proc)
        if failed is not None:
            raise failed
        if late is not None:
            raise late
        return code, out

    def collect(self, proc):
        """Read stdout and stderr together; never request more than remaining+1.

        The first collection error is kept through selector teardown (S1); a later
        teardown error is recorded, and propagates only when nothing failed before it.
        """
        chunks, total = [], 0
        first = None
        sel = self.selector()
        try:
            sel.register(proc.stdout, selectors.EVENT_READ, "stdout")
            sel.register(proc.stderr, selectors.EVENT_READ, "stderr")
            while sel.get_map():
                self.expired()
                events = sel.select(self.remaining())
                self.expired()
                for key, _ in events:
                    request = min(CHUNK, self.cap - total + 1)
                    data = self.read(key.fd, request)
                    self.reads.append((key.data, total, request, len(data)))
                    if not data:
                        sel.unregister(key.fileobj)
                        continue
                    total += len(data)
                    if total > self.cap:
                        raise ScopeRefused("scope_commitment")
                    if key.data == "stdout":
                        chunks.append(data)
        except BaseException as exc:  # noqa: BLE001 -- re-raised after teardown
            first = exc
        try:
            sel.close()
        except BaseException as later:  # noqa: BLE001 -- recorded; first error kept
            if first is None:
                raise
            self.cleanup_errors.append(type(later).__name__)
        if first is not None:
            raise first
        return b"".join(chunks)

    def reap(self, proc):
        """After pipe EOF, wait for the leader within the work deadline; EOF is not death."""
        while True:
            budget = self.remaining()
            if budget <= 0:
                raise TimeoutError("git work deadline")
            step = min(self.slice, budget)
            self.waits.append(("reap", step))
            try:
                code = proc.wait(timeout=step)
            except subprocess.TimeoutExpired:
                continue
            if self.remaining() < 0:
                raise TimeoutError(
                    "git work deadline"
                )  # reaped after Dw is not success (R03)
            return code

    def stop_guarded(self, proc, cause):
        """Staged TERM/KILL against one absolute cleanup expiry; progression continues."""
        # Bound measured from the observed capture time, even when that is past Dw (R03).
        expiry = self.clock() + self.cleanup_seconds
        stages = (
            (self.signals[0], expiry - self.kill_reserve),
            (self.signals[1], expiry),
        )
        for sig, until in stages:
            try:
                try:  # noqa: SIM105
                    self.killer(proc.pid, sig)
                except ProcessLookupError:
                    pass
                if self.wait_group(proc, until):
                    return
            except (
                BaseException
            ) as later:  # noqa: BLE001 -- recorded; progression continues
                self.cleanup_errors.append(type(later).__name__)
        self.uncertain = True
        self.uncertain_cause = cause

    def wait_group(self, proc, until):
        """True only if the leader is reaped AND the owned process group is empty.

        The remaining allowance is recomputed before EACH separate blocking wait or sleep,
        and each is journaled separately (R03). Requested waits are not scheduler bounds.
        """
        while True:
            left = until - self.clock()
            if left <= 0:
                return False
            if proc.returncode is None:
                step = min(self.slice, left)
                self.waits.append(("cleanup-wait", step))
                try:
                    proc.wait(timeout=step)
                except subprocess.TimeoutExpired:
                    continue
            try:
                self.group_probe(proc.pid, 0)
            except ProcessLookupError:
                return True
            left = until - self.clock()
            if left <= 0:
                return False
            step = min(self.slice, left)
            self.waits.append(("cleanup-sleep", step))
            self.sleep(step)

    def close(self, proc):
        """One close attempt per pipe, after wait; return a cancellation to re-raise."""
        late = None
        for pipe in (proc.stdout, proc.stderr):
            try:
                self.closer(pipe)
            except BaseException as exc:  # noqa: BLE001 -- recorded; cancellation kept
                self.cleanup_errors.append(type(exc).__name__)
                if late is None and not isinstance(exc, Exception):
                    late = exc
        return late


def full_hex(value, length):
    return (
        isinstance(value, str)
        and len(value) == length
        and all(ch in HEX for ch in value)
    )


def valid_path(value):
    return (
        isinstance(value, str)
        and bool(value)
        and not value.startswith("/")
        and "\\" not in value
        and "\0" not in value
        and all(part not in ("", ".", "..") for part in value.split("/"))
    )


def check_store(gitdir):
    """Pre-traversal store checks; nothing here reads object data or follows links."""
    if not isinstance(gitdir, str) or not os.path.isabs(gitdir):  # noqa: PTH117
        raise ScopeRefused("scope_root")
    try:
        info = os.lstat(gitdir)
    except OSError:
        raise ScopeRefused("scope_root") from None
    if not stat.S_ISDIR(info.st_mode):
        raise ScopeRefused("scope_root")
    for name in ALTERNATES:
        if os.path.lexists(os.path.join(gitdir, name)):  # noqa: PTH118
            raise ScopeRefused("scope_commitment")
    for name in ("config", "HEAD", "objects", "refs"):
        if not os.path.lexists(os.path.join(gitdir, name)):  # noqa: PTH118
            raise ScopeRefused("scope_root")
    config_path = os.path.join(gitdir, "config")  # noqa: PTH118
    if not stat.S_ISREG(os.lstat(config_path).st_mode):
        raise ScopeRefused("scope_commitment")


def check_config(runner):
    config = os.path.join(runner.gitdir, "config")  # noqa: PTH118
    code, out = runner.git(
        "config", "--file", config, "--no-includes", "--null", "--list"
    )
    if code != 0:
        raise ScopeRefused("scope_commitment")
    for row in out.split(b"\0"):
        if not row:
            continue
        try:
            key = row.split(b"\n", 1)[0].decode("utf-8", "strict").lower()
        except UnicodeDecodeError:
            raise ScopeRefused("scope_commitment") from None
        if key in DENIED_CONFIG or key.startswith(DENIED_CONFIG_PREFIXES):
            raise ScopeRefused("scope_commitment")


def entries(raw, length):
    """Parse ls-tree -z records as bytes: (mode, type, oid, path_bytes)."""
    rows = []
    for record in raw.split(b"\0"):
        if not record:
            continue
        meta, sep, path = record.partition(b"\t")
        parts = meta.split(b" ")
        if not sep or len(parts) != 3 or not path:
            raise ScopeRefused("scope_commitment")
        mode, kind, oid_bytes = parts
        oid = oid_bytes.decode("ascii", "replace")
        if not full_hex(oid, length):
            raise ScopeRefused("scope_commitment")
        rows.append((mode, kind, oid, path))
    return rows


def gitlink_path(raw):
    """Strict UTF-8 plus the driver's valid_path rule (disposition Q4)."""
    try:
        value = raw.decode("utf-8", "strict")
    except UnicodeDecodeError:
        raise ScopeRefused("scope_commitment") from None
    if not valid_path(value):
        raise ScopeRefused("scope_commitment")
    return value


def produce(gitdir, commit, expected_tree, runner=None):
    check_store(gitdir)
    runner = runner if runner is not None else Runner(gitdir)
    check_config(runner)
    code, out = runner.git("rev-parse", "--is-bare-repository")
    if code != 0 or out != b"true\n":
        raise ScopeRefused("scope_root")
    code, out = runner.git("rev-parse", "--show-object-format")
    object_format = out.decode("ascii", "replace").strip() if code == 0 else ""
    if object_format not in HEX_LEN:
        raise ScopeRefused("scope_commitment")
    length = HEX_LEN[object_format]
    if not full_hex(commit, length) or not full_hex(expected_tree, length):
        raise ScopeRefused("scope_schema")
    code, out = runner.git("cat-file", "-t", commit)
    if code != 0 or out != b"commit\n":
        raise ScopeRefused("scope_commitment")
    for suffix, expected in (("^{commit}", commit), ("^{tree}", expected_tree)):
        code, out = runner.git(
            "rev-parse", "--verify", "--end-of-options", commit + suffix
        )
        if code != 0 or out != expected.encode("ascii") + b"\n":
            raise ScopeRefused("scope_commitment")
    code, out = runner.git("ls-tree", "-z", "--full-tree", commit)
    if code != 0:
        raise ScopeRefused("scope_commitment")
    gitmodules_blob = None
    for mode, kind, oid, path in entries(out, length):
        if path == b".gitmodules":
            if mode not in BLOB_MODES or kind != b"blob":
                raise ScopeRefused("scope_commitment")
            gitmodules_blob = oid
    code, out = runner.git("ls-tree", "-r", "-z", "--full-tree", commit)
    if code != 0:
        raise ScopeRefused("scope_commitment")
    gitlinks, seen = [], set()
    for mode, kind, oid, path in entries(out, length):
        if mode == b"160000" and kind == b"commit":
            value = gitlink_path(path)
            key = value.casefold()  # the driver's check_paths key (governed_scope.py)
            if key in seen:
                raise ScopeRefused("scope_commitment")
            seen.add(key)
            gitlinks.append({"path": value, "object_id": oid})
    return {
        "version": "scope_root_metadata.v2",
        "object_format": object_format,
        "commit": commit,
        "tree": expected_tree,
        "gitlinks": sorted(gitlinks, key=lambda row: row["path"]),
        "gitmodules_blob": gitmodules_blob,
    }


def absent_output(value):
    if not os.path.isabs(value):  # noqa: PTH117
        raise ScopeRefused("scope_root")
    try:
        os.lstat(value)
    except FileNotFoundError:
        return Path(value)
    raise ScopeRefused("scope_root")


def same_created_file(fd, path, *, fstat=os.fstat, lstat=os.lstat):
    """True only if the STILL-OPEN descriptor and the path are one regular file."""
    opened, named = fstat(fd), lstat(path)
    return (
        stat.S_ISREG(opened.st_mode)
        and stat.S_ISREG(named.st_mode)
        and (opened.st_dev, opened.st_ino) == (named.st_dev, named.st_ino)
    )


def write_exclusive(
    path,
    data,
    *,
    write=os.write,
    close=os.close,
    unlink=os.unlink,
    fstat=os.fstat,
    lstat=os.lstat,
):
    """Create-exclusive write; on failure remove only the proven producer-created file.

    Any failure after the exclusive create, including a close failure after a complete
    write, is a nonpass. The file is removed only when the still-open descriptor proves
    identity; otherwise it is left and CleanupUncertain is raised from the original.
    """
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC
    try:
        fd = os.open(path, flags, 0o600)
    except (FileExistsError, FileNotFoundError, NotADirectoryError):
        raise ScopeRefused("scope_root") from None
    failed = None
    try:
        os.fchmod(fd, 0o600)
        view = memoryview(data)
        while view:
            view = view[write(fd, view) :]
    except BaseException as exc:  # noqa: BLE001 -- handled below
        failed = exc
    if failed is None:
        try:
            close(fd)
            return
        except OSError as exc:
            raise CleanupUncertain("output close failed; identity unprovable") from exc
    removed, cleanup_errors = False, []
    try:
        if same_created_file(fd, path, fstat=fstat, lstat=lstat):
            unlink(path)
            removed = True
    except BaseException as exc:  # noqa: BLE001 -- recorded, never primary
        cleanup_errors.append(exc)
    try:
        close(fd)
    except BaseException as exc:  # noqa: BLE001 -- recorded, never primary
        cleanup_errors.append(exc)
    names = [type(exc).__name__ for exc in cleanup_errors]
    failed.producer_cleanup_errors = names  # type: ignore[attr-defined]
    if not isinstance(failed, Exception):
        raise failed
    if removed:
        raise failed
    uncertain = CleanupUncertain("producer-created output left in place")
    uncertain.producer_cleanup_errors = names  # type: ignore[attr-defined]
    raise uncertain from failed


def run(args, runner):
    """Return (exit code, stdout bytes, stderr bytes, terminal error) without printing."""
    try:
        try:
            output = absent_output(args.output)
            metadata = produce(args.git_dir, args.commit, args.expected_tree, runner)
            write_exclusive(output, canonical(metadata))
        except ScopeRefused as exc:
            if runner.uncertain:
                raise CleanupUncertain("cleanup uncertain after refusal") from exc
            diag = {
                "version": "scope_diagnostic.v1",
                "reason": exc.reason,
                "path": exc.path,
            }
            return 1, b"", canonical(diag) + b"\n", exc
    except Exception as exc:
        name = "CleanupUncertain" if runner.uncertain else type(exc).__name__
        return 2, b"", ("scope_setup:" + name + "\n").encode("ascii"), exc
    receipt = {
        "version": "scope_commitment_receipt.v1",
        "metadata_digest": digest(metadata),
        "producer_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    return 0, canonical(receipt) + b"\n", b"", None


def emit(fd, data):
    view = memoryview(data)
    while view:
        view = view[os.write(fd, view) :]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["commit"])
    parser.add_argument("--git-dir", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--expected-tree", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    code, out, err, _ = run(args, Runner(args.git_dir))
    try:
        emit(1, out)
        emit(2, err)
    except OSError as exc:  # receipt/diagnostic write failure is never success (U3)
        try:  # noqa: SIM105
            emit(2, ("scope_setup:" + type(exc).__name__ + "\n").encode("ascii"))
        except OSError:
            pass
        return 2
    return code


if __name__ == "__main__":
    raise SystemExit(main())

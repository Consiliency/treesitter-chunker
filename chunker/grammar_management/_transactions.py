"""Single-host cache transactions for the core grammar manager.

This module implements IF-0-TXNSPEC-1, frozen in
``docs/development/cache-transaction-contract.md``. Participants on one host
share a cache root and serialize on ``<root>/.txn.lock``. Everything the
module opens or creates below the root is checked without following links.

Only the standard library is imported at module level.
"""

from __future__ import annotations

import errno
import json
import logging
import os
import signal
import stat
import subprocess
import threading
import time
import uuid
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import AbstractContextManager, contextmanager, suppress
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final, Literal

logger = logging.getLogger(__name__)

DEFAULT_LOCK_TIMEOUT: Final[float] = 60.0
LOCK_FILE_NAME: Final[str] = ".txn.lock"
CONTROL_DIR_NAME: Final[str] = ".txn"
MARKER_NAME: Final[str] = ".txn-keep"
ROLLBACK_MANIFEST_NAME: Final[str] = "rollback.json"
Namespace = Literal["downloads", "builds"]

# Root-level control area: rollback points (Primitive 3) and their garbage.
# Staging and entry retirement live inside each namespace instead.
_CONTROL_CHILDREN: Final = ("retired", "rollback")
# A root may not be opened at or below another root's managed namespaces.
_MANAGED_NAMES: Final = frozenset({"downloads", "builds", CONTROL_DIR_NAME})

_WINDOWS: Final = os.name == "nt"
_NOFOLLOW: Final[int] = getattr(os, "O_NOFOLLOW", 0)
_DIRECTORY: Final[int] = getattr(os, "O_DIRECTORY", 0)
_CLOEXEC: Final[int] = getattr(os, "O_CLOEXEC", 0)
_NONBLOCK: Final[int] = getattr(os, "O_NONBLOCK", 0)
_BINARY: Final[int] = getattr(os, "O_BINARY", 0)
_NOINHERIT: Final[int] = getattr(os, "O_NOINHERIT", 0)
_REPARSE_POINT: Final[int] = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
_ATTR_DIRECTORY: Final[int] = getattr(stat, "FILE_ATTRIBUTE_DIRECTORY", 0x10)
_ATTR_READONLY: Final[int] = getattr(stat, "FILE_ATTRIBUTE_READONLY", 0x1)

_REPLACE_ATTEMPTS: Final = 10
_REPLACE_WAIT: Final = 0.05
_BACKOFF_FIRST: Final = 0.005
_BACKOFF_MAX: Final = 0.05

# Private test seam (contract "Test seam"). ``None`` in production.
_BARRIER: Callable[[str, Mapping[str, str]], None] | None = None


class CacheTransactionError(Exception):
    """A cache transaction could not run safely."""


class CacheLockTimeoutError(CacheTransactionError):
    """The cache root lock was not acquired within the timeout."""


class ContainmentError(CacheTransactionError):
    """A path below the cache root was a link, reparse point or wrong type."""


class NestedRootError(ContainmentError):
    """A cache root overlaps another root's managed namespace."""


class _RootMovedError(CacheTransactionError):
    """The root path no longer resolves to the directory that was opened."""


def _seam(point: str, context: Mapping[str, str]) -> None:
    barrier = _BARRIER
    if barrier is not None:
        barrier(point, dict(context))


def _new_operation_id() -> str:
    return uuid.uuid4().hex


def _is_link(st: os.stat_result) -> bool:
    return stat.S_ISLNK(st.st_mode) or bool(
        getattr(st, "st_file_attributes", 0) & _REPARSE_POINT
    )


def _identity(st: os.stat_result) -> tuple[int, int]:
    return st.st_dev, st.st_ino


def _check_component(name: str, what: str) -> None:
    """Require one plain, non-reserved path component."""
    separators = {"/", "\\", os.sep, os.altsep or "/"}
    if (
        not isinstance(name, str)
        or name in {"", ".", ".."}
        or any(sep in name for sep in separators)
        or "\0" in name
    ):
        raise ContainmentError(f"{what} must be one path component: {name!r}")
    if name.startswith(CONTROL_DIR_NAME):
        raise ContainmentError(f"{what} uses a reserved cache name: {name!r}")


class _Dir:
    """A real directory at or below the root.

    On POSIX a directory descriptor anchors every operation (``dir_fd``), and
    final components are never followed. On Windows the directory was
    validated as a non-reparse directory, and each name is checked with
    ``lstat`` before use.
    """

    __slots__ = ("fd", "path")

    def __init__(self, path: Path, fd: int | None) -> None:
        self.path = path
        self.fd = fd

    @classmethod
    def open_root(cls, root: Path, identity: tuple[int, int]) -> _Dir:
        if _WINDOWS:
            current = root.stat()
            if _identity(current) != identity:
                raise _RootMovedError(
                    f"Cache root {root} no longer resolves to the directory opened"
                )
            return cls(root, None)
        fd = os.open(root, os.O_RDONLY | _DIRECTORY | _CLOEXEC)
        try:
            if _identity(os.fstat(fd)) != identity:
                raise _RootMovedError(
                    f"Cache root {root} no longer resolves to the directory opened"
                )
        except BaseException:
            os.close(fd)
            raise
        return cls(root, fd)

    def close(self) -> None:
        if self.fd is not None:
            fd, self.fd = self.fd, None
            os.close(fd)

    def __enter__(self) -> _Dir:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _target(self, name: str) -> str:
        return name if self.fd is not None else str(self.path / name)

    def _dir_kw(self) -> dict[str, int]:
        return {"dir_fd": self.fd} if self.fd is not None else {}

    def stat_self(self) -> os.stat_result:
        return os.fstat(self.fd) if self.fd is not None else os.lstat(self.path)

    def lstat(self, name: str) -> os.stat_result | None:
        try:
            target, kw = self._target(name), self._dir_kw()
            return os.stat(target, follow_symlinks=False, **kw)  # noqa: PTH116
        except FileNotFoundError:
            return None

    def child(self, name: str) -> _Dir:
        """Open an existing real subdirectory; links and junctions are refused."""
        path = self.path / name
        if self.fd is None:
            st = os.lstat(path)
            if _is_link(st) or not stat.S_ISDIR(st.st_mode):
                raise ContainmentError(f"Not a real directory: {path}")
            return _Dir(path, None)
        try:
            fd = os.open(
                name,
                os.O_RDONLY | _DIRECTORY | _NOFOLLOW | _CLOEXEC,
                dir_fd=self.fd,
            )
        except OSError as error:
            if error.errno in {errno.ELOOP, errno.ENOTDIR}:
                raise ContainmentError(f"Not a real directory: {path}") from error
            raise
        try:
            after = os.stat(name, dir_fd=self.fd, follow_symlinks=False)
            if _identity(after) != _identity(os.fstat(fd)):
                raise ContainmentError(f"Directory changed while opening: {path}")
        except BaseException:
            os.close(fd)
            raise
        return _Dir(path, fd)

    def mkdir(self, name: str, mode: int = 0o700) -> None:
        os.mkdir(self._target(name), mode, **self._dir_kw())  # noqa: PTH102 - dir_fd

    def open_file(self, name: str, flags: int, mode: int = 0o600) -> int:
        """Open a regular file without following a link at ``name``."""
        path = self.path / name
        if self.fd is not None:
            try:
                fd = os.open(name, flags | _NOFOLLOW | _CLOEXEC, mode, dir_fd=self.fd)
            except OSError as error:
                if error.errno == errno.ELOOP:
                    raise ContainmentError(
                        f"Refusing to follow link: {path}"
                    ) from error
                raise
            try:
                if not stat.S_ISREG(os.fstat(fd).st_mode):
                    raise ContainmentError(f"Not a regular file: {path}")
            except BaseException:
                os.close(fd)
                raise
            return fd
        flags |= _BINARY | _NOINHERIT
        if flags & os.O_CREAT and flags & os.O_EXCL:
            # O_EXCL fails on any existing entry, including a reparse point.
            return os.open(path, flags, mode)
        before = self.lstat(name)
        if before is None:
            if not flags & os.O_CREAT:
                raise FileNotFoundError(errno.ENOENT, "No such file", str(path))
            try:
                return os.open(path, flags | os.O_EXCL, mode)
            except FileExistsError:
                before = self.lstat(name)
                if before is None:
                    raise
        if _is_link(before):
            raise ContainmentError(f"Refusing to follow link: {path}")
        if not stat.S_ISREG(before.st_mode):
            raise ContainmentError(f"Not a regular file: {path}")
        fd = os.open(path, flags & ~os.O_CREAT, mode)
        try:
            if _identity(os.fstat(fd)) != _identity(before):
                raise ContainmentError(f"File changed while opening: {path}")
        except BaseException:
            os.close(fd)
            raise
        return fd

    def unlink(self, name: str) -> None:
        os.unlink(self._target(name), **self._dir_kw())

    def rmdir(self, name: str) -> None:
        os.rmdir(self._target(name), **self._dir_kw())

    def replace_into(self, name: str, target: _Dir, target_name: str) -> None:
        """``os.replace`` one entry, retrying Windows sharing violations."""
        if self.fd is not None:
            os.replace(name, target_name, src_dir_fd=self.fd, dst_dir_fd=target.fd)
            return
        source, destination = self.path / name, target.path / target_name
        for attempt in range(_REPLACE_ATTEMPTS):
            try:
                os.replace(source, destination)  # noqa: PTH105 - retried
                return
            except PermissionError:
                if attempt == _REPLACE_ATTEMPTS - 1:
                    raise
                time.sleep(_REPLACE_WAIT * (attempt + 1))

    def fsync(self) -> None:
        """Flush directory entries (POSIX, best effort)."""
        if self.fd is not None:
            with suppress(OSError):
                os.fsync(self.fd)


# --- Roots ---------------------------------------------------------------

_ROOTS: dict[str, tuple[int, int]] = {}
_ROOTS_GUARD = threading.Lock()


def _absolute(root: Path) -> Path:
    return Path(os.path.abspath(os.fspath(root)))  # noqa: PTH100 - lexical, no resolve


def _record_root(absolute: Path) -> tuple[int, int]:
    try:
        st = absolute.stat()
    except FileNotFoundError as error:
        raise CacheTransactionError(f"Cache root does not exist: {absolute}") from error
    if not stat.S_ISDIR(st.st_mode):
        raise CacheTransactionError(f"Cache root is not a directory: {absolute}")
    identity = _identity(st)
    with _ROOTS_GUARD:
        _ROOTS[str(absolute)] = identity
    return identity


def _current_identity(absolute: Path) -> tuple[int, int]:
    """Identity the root path resolves to now (operator-trusted links followed)."""
    try:
        return _identity(absolute.stat())
    except OSError as error:
        raise _RootMovedError(
            f"Cache root {absolute} no longer resolves to the directory opened: {error}"
        ) from error


def _root_identity(absolute: Path) -> tuple[int, int]:
    with _ROOTS_GUARD:
        identity = _ROOTS.get(str(absolute))
    return identity if identity is not None else _record_root(absolute)


def _refuse_nested(absolute: Path) -> None:
    """Contract "Nested roots" rule 1, on the lexical and the resolved path."""
    candidates = [absolute]
    with suppress(OSError):
        resolved = Path(os.path.realpath(absolute))
        if resolved != absolute:
            candidates.append(resolved)
    for path in candidates:
        for ancestor in path.parents:
            first = path.relative_to(ancestor).parts[0]
            if first not in _MANAGED_NAMES:
                continue
            try:
                st = os.lstat(ancestor / LOCK_FILE_NAME)
            except OSError:
                continue
            if stat.S_ISREG(st.st_mode) and not _is_link(st):
                raise NestedRootError(
                    f"Cache root {absolute} lies inside {ancestor / first}, which "
                    f"belongs to the cache root {ancestor}"
                )


# --- Lock ------------------------------------------------------------------


@dataclass
class _Hold:
    guard: threading.Lock = field(default_factory=threading.Lock)
    owner: int | None = None
    depth: int = 0
    lock_fd: int | None = None
    rootdir: _Dir | None = None
    pid: int = 0  # the process that acquired the hold


_HOLDS: dict[tuple[int, int], _Hold] = {}
_HOLDS_GUARD = threading.Lock()

# Every open lock-file descriptor in this process, whether its acquisition is
# still pending or the lock is held. Opening and registering, and closing and
# forgetting, each happen under ``_FD_GUARD``, which a fork also takes, so a
# forked child always knows every lock descriptor it inherited.
_LOCK_FDS: set[int] = set()
_FD_GUARD = threading.Lock()


def _before_fork() -> None:
    _FD_GUARD.acquire()


def _after_fork_in_parent() -> None:
    _FD_GUARD.release()


def _after_fork_in_child() -> None:
    """Drop every inherited lock descriptor and hold; the child acquires anew.

    Closing the child's copies never unlocks the parent: ``flock`` state
    belongs to the open file description, which the parent still references.
    Without this, a child would keep the description (and so the lock) alive
    after the parent dies, including one the parent was still acquiring.
    """
    global _FD_GUARD, _HOLDS_GUARD, _ROOTS_GUARD
    for fd in _LOCK_FDS:
        with suppress(OSError):
            os.close(fd)
    _LOCK_FDS.clear()
    for hold in list(_HOLDS.values()):
        if hold.rootdir is not None:
            with suppress(OSError):
                hold.rootdir.close()
    _HOLDS.clear()
    _FD_GUARD = threading.Lock()
    _HOLDS_GUARD = threading.Lock()
    _ROOTS_GUARD = threading.Lock()


if hasattr(os, "register_at_fork"):
    os.register_at_fork(
        before=_before_fork,
        after_in_parent=_after_fork_in_parent,
        after_in_child=_after_fork_in_child,
    )


def _lock_key(rootdir: _Dir) -> tuple[int, int] | None:
    st = rootdir.lstat(LOCK_FILE_NAME)
    if st is None:
        return None
    if _is_link(st) or not stat.S_ISREG(st.st_mode):
        raise ContainmentError(f"Lock file is not a regular file: {rootdir.path}")
    return _identity(st)


def _close_lock_fd(fd: int) -> None:
    with _FD_GUARD:
        _LOCK_FDS.discard(fd)
        os.close(fd)


def _open_lock_file(rootdir: _Dir) -> tuple[int, tuple[int, int]]:
    with _FD_GUARD:
        fd = rootdir.open_file(LOCK_FILE_NAME, os.O_RDWR | os.O_CREAT, 0o600)
        _LOCK_FDS.add(fd)
    try:
        if os.get_inheritable(fd):
            raise CacheTransactionError("Cache lock descriptor is inheritable")
        st = os.fstat(fd)
        if st.st_size == 0:
            # One byte of content; a racing creator may already hold byte 0.
            with suppress(OSError):
                os.write(fd, b"\0")
        return fd, _identity(st)
    except BaseException:
        _close_lock_fd(fd)
        raise


def _try_os_lock(fd: int, path: Path) -> bool:
    try:
        if _WINDOWS:
            import msvcrt

            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)  # type: ignore[attr-defined]
        else:
            import fcntl

            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except OSError as error:
        busy = {errno.EAGAIN, errno.EWOULDBLOCK, errno.EACCES}
        busy.add(getattr(errno, "EDEADLOCK", errno.EDEADLK))
        if error.errno in busy:
            return False
        raise CacheTransactionError(
            f"Cache lock is unavailable on this filesystem ({path}): {error}"
        ) from error


def _os_unlock(fd: int) -> None:
    if _WINDOWS:
        import msvcrt

        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)  # type: ignore[attr-defined]
    else:
        import fcntl

        fcntl.flock(fd, fcntl.LOCK_UN)


def _ensure_marker(directory: _Dir) -> None:
    try:
        os.close(directory.open_file(MARKER_NAME, os.O_WRONLY | os.O_CREAT | os.O_EXCL))
    except FileExistsError:
        st = directory.lstat(MARKER_NAME)
        if st is None or _is_link(st) or not stat.S_ISREG(st.st_mode):
            raise ContainmentError(
                f"Control marker is not a regular file: {directory.path}"
            ) from None


def _control_dir(parent: _Dir, name: str) -> _Dir:
    """Create or open a control directory and give it its marker.

    The marker keeps the directory non-empty for
    ``DirectoryManager.cleanup_empty_directories`` (decision D-c). A missing
    marker, left by a crash or a sweep, is created again. If a sweep removes
    the directory before the marker exists, ``mkdir`` and the marker are
    retried once.
    """
    for attempt in range(2):
        with suppress(FileExistsError):
            parent.mkdir(name)
        try:
            directory = parent.child(name)
        except FileNotFoundError:
            if attempt:
                break
            continue
        try:
            _ensure_marker(directory)
            return directory
        except FileNotFoundError:
            directory.close()
            if attempt:
                break
        except BaseException:
            directory.close()
            raise
    raise CacheTransactionError(
        f"Control directory {parent.path / name} disappeared while it was created"
    )


def _initialize(rootdir: _Dir) -> None:
    with _control_dir(rootdir, CONTROL_DIR_NAME) as control:
        for name in _CONTROL_CHILDREN:
            _control_dir(control, name).close()


class _LockContext:
    """Context mapping for seam points, plus the operation identifier."""

    __slots__ = ("context", "operation_id")

    def __init__(self, primitive: str, root: Path, operation_id: str, **extra: str):
        self.operation_id = operation_id
        self.context = {
            "primitive": primitive,
            "root": str(root),
            "operation_id": operation_id,
            **extra,
        }

    def seam(self, point: str, **extra: str) -> None:
        _seam(point, {**self.context, **extra})


@contextmanager
def _locked(root: Path, timeout: float, ctx: _LockContext) -> Iterator[_Dir]:
    """Hold the root lock; reentrant per thread, one descriptor per root."""
    absolute = _absolute(root)
    identity = _root_identity(absolute)
    me = threading.get_ident()
    rootdir = _Dir.open_root(absolute, identity)
    try:
        key = _lock_key(rootdir)
        with _HOLDS_GUARD:
            existing = _HOLDS.get(key) if key is not None else None
        reentrant = existing is not None and existing.owner == me
        if not reentrant:
            _refuse_nested(absolute)
    except BaseException:
        rootdir.close()
        raise
    if reentrant:
        assert existing is not None and existing.rootdir is not None
        rootdir.close()
        existing.depth += 1
        try:
            yield existing.rootdir
        finally:
            existing.depth -= 1
        return

    lock_fd: int | None = None
    hold: _Hold | None = None
    thread_held = False
    try:
        lock_fd, key = _open_lock_file(rootdir)
        with _HOLDS_GUARD:
            hold = _HOLDS.setdefault(key, _Hold())
        deadline = time.monotonic() + timeout
        ctx.seam("lock.before_acquire")
        contended = False
        if not hold.guard.acquire(blocking=False):
            contended = True
            ctx.seam("lock.contended")
            if not hold.guard.acquire(timeout=max(0.0, deadline - time.monotonic())):
                raise CacheLockTimeoutError(_timeout_message(absolute, timeout))
        thread_held = True
        delay = _BACKOFF_FIRST
        while not _try_os_lock(lock_fd, absolute / LOCK_FILE_NAME):
            if not contended:
                contended = True
                ctx.seam("lock.contended")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise CacheLockTimeoutError(_timeout_message(absolute, timeout))
            time.sleep(min(delay, remaining))
            delay = min(delay * 2, _BACKOFF_MAX)
    except BaseException:
        if thread_held and hold is not None:
            hold.guard.release()
        if lock_fd is not None:
            _close_lock_fd(lock_fd)
        rootdir.close()
        raise

    assert hold is not None and lock_fd is not None
    hold.owner, hold.depth, hold.lock_fd, hold.rootdir = me, 1, lock_fd, rootdir
    hold.pid = os.getpid()
    try:
        # The root path may be an operator-trusted link, so follow it here.
        if _current_identity(absolute) != identity or (
            rootdir.fd is not None and _identity(os.fstat(rootdir.fd)) != identity
        ):
            raise _RootMovedError(
                f"Cache root {absolute} no longer resolves to the directory opened"
            )
        if _lock_key(rootdir) != key:
            raise ContainmentError(f"Cache lock file was replaced: {absolute}")
        ctx.seam("lock.acquired")
        _initialize(rootdir)
        ctx.seam("root.after_init")
        # Post-initialization check (contract "Nested roots" rule 2).
        _refuse_nested(absolute)
        if _current_identity(absolute) != identity:
            raise _RootMovedError(
                f"Cache root {absolute} moved while it was initialized"
            )
        yield rootdir
    finally:
        if hold.pid != os.getpid():
            # A forked child leaving the parent's section: the at-fork handler
            # already closed its copies, and this hold is the parent's.
            pass
        else:
            hold.owner, hold.depth, hold.lock_fd, hold.rootdir = None, 0, None, None
            try:
                _os_unlock(lock_fd)
            except OSError:
                pass  # Closing the descriptor releases the lock as well.
            finally:
                _close_lock_fd(lock_fd)
                rootdir.close()
                hold.guard.release()


def _timeout_message(absolute: Path, timeout: float) -> str:
    return (
        f"Timed out after {timeout:g}s waiting for the cache lock "
        f"{absolute / LOCK_FILE_NAME}; another grammar command may be using this "
        "cache root. Retry when it finishes."
    )


def open_cache_root(root: Path) -> Path:
    """Validate and initialize a cache root, then return it unchanged.

    Records the root's identity, creates the lock file and the ``.txn``
    control area with markers, and refuses roots that overlap another root's
    managed namespaces. Consumers call it at construction
    so that a bad root is reported early.
    """
    absolute = _absolute(root)
    _refuse_nested(absolute)
    _record_root(absolute)
    ctx = _LockContext("open_cache_root", absolute, _new_operation_id())
    with _locked(absolute, DEFAULT_LOCK_TIMEOUT, ctx):
        pass
    return root


def cache_lock(
    root: Path, *, timeout: float = DEFAULT_LOCK_TIMEOUT
) -> AbstractContextManager[None]:
    """Hold the root lock for one critical section (reentrant per thread)."""

    @contextmanager
    def section() -> Iterator[None]:
        ctx = _LockContext("cache_lock", _absolute(root), _new_operation_id())
        with _locked(root, timeout, ctx):
            yield

    return section()


# --- Primitive 1: locked JSON record update ---------------------------------


def _check_record_name(name: str) -> None:
    _check_component(name, "Record file name")


def _read_document(rootdir: _Dir, name: str) -> tuple[bytes | None, Path]:
    path = rootdir.path / name
    try:
        fd = rootdir.open_file(name, os.O_RDONLY | _NONBLOCK | _BINARY)
    except FileNotFoundError:
        return None, path
    with os.fdopen(fd, "rb") as handle:
        return handle.read(), path


def _decode_records(data: bytes | None, path: Path) -> dict[str, Any]:
    if data is None:
        return {}
    try:
        document = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as error:
        raise CacheTransactionError(f"Malformed record file {path}: {error}") from error
    if not isinstance(document, dict):
        raise CacheTransactionError(f"Malformed record file {path}: not a JSON object")
    return document


def _replace_bytes(
    rootdir: _Dir,
    name: str,
    data: bytes,
    ctx: _LockContext,
    *,
    before_replace: str | None,
    after_replace: str | None = None,
) -> None:
    """Write a sibling temporary file, then ``os.replace`` it over ``name``."""
    temporary = f".{name}.{ctx.operation_id}.tmp"
    fd = rootdir.open_file(
        temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | _BINARY, 0o600
    )
    replaced = False
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        if before_replace:
            ctx.seam(before_replace)
        rootdir.replace_into(temporary, rootdir, name)
        replaced = True
        rootdir.fsync()
    finally:
        if not replaced:
            with suppress(FileNotFoundError):
                rootdir.unlink(temporary)
    if after_replace:
        ctx.seam(after_replace)


def read_json_records(
    root: Path, name: str, *, timeout: float = DEFAULT_LOCK_TIMEOUT
) -> dict[str, Any]:
    """Read a JSON object record file under the lock, without following links.

    A missing file is ``{}``. A malformed document raises
    :class:`CacheTransactionError`.
    """
    _check_record_name(name)
    ctx = _LockContext("read_json_records", _absolute(root), _new_operation_id())
    with _locked(root, timeout, ctx) as rootdir:
        return _decode_records(*_read_document(rootdir, name))


def update_json_records(
    root: Path,
    name: str,
    mutate: Callable[[dict[str, Any]], dict[str, Any]],
    *,
    reset_malformed: bool = False,
    timeout: float = DEFAULT_LOCK_TIMEOUT,
) -> dict[str, Any]:
    """Merge into a JSON record file: fresh read, ``mutate``, atomic replace.

    Runs under the root lock. ``mutate`` receives a copy of the document read
    from disk and returns the document to write. A malformed document raises
    :class:`CacheTransactionError` and is left unchanged, unless
    ``reset_malformed`` is true, in which case it is logged and treated as
    ``{}``. Returns the document written.
    """
    _check_record_name(name)
    ctx = _LockContext("update_json_records", _absolute(root), _new_operation_id())
    with _locked(root, timeout, ctx) as rootdir:
        data, path = _read_document(rootdir, name)
        try:
            current = _decode_records(data, path)
        except CacheTransactionError as error:
            if not reset_malformed:
                raise
            logger.warning("Resetting malformed record file: %s", error)
            current = {}
        ctx.seam("json.after_read")
        document = mutate(dict(current))
        if not isinstance(document, dict):
            raise CacheTransactionError("Record update must produce a JSON object")
        encoded = json.dumps(document, indent=2).encode("utf-8")
        _replace_bytes(
            rootdir, name, encoded, ctx, before_replace="json.before_replace"
        )
        return document


# --- Primitive 2: staging, owned subprocesses and cache-entry publication ----

_NAMESPACES: Final[tuple[Namespace, ...]] = ("downloads", "builds")
# Per-namespace control folders (maintainer decision, 2026-11-01): staging and
# retirement live inside the namespace they move entries in, so every rename
# stays within one directory tree and one filesystem.
_STAGING_DIR: Final = ".txn-staging"
_RETIRED_DIR: Final = ".txn-retired"
_GROUP_CONFIRM_DEADLINE: Final = 10.0
_READER_JOIN: Final = 10.0


@dataclass(frozen=True)
class StagingArea:
    root: Path
    operation_id: str

    def path(self, namespace: Namespace) -> Path:
        """This operation's staging directory inside ``namespace``.

        ``<root>/<namespace>/.txn-staging/<operation-id>/``; publishability is
        tracked in-process by the helper.
        """
        _check_namespace(namespace)
        return _absolute(self.root) / namespace / _STAGING_DIR / self.operation_id


@dataclass(frozen=True)
class StagedRun:
    returncode: int | None  # None: timed out
    stdout: str
    stderr: str
    timed_out: bool
    group_empty: bool


@dataclass(frozen=True)
class PruneResult:
    entries_removed: int
    bytes_freed: int
    skipped: tuple[str, ...]
    errors: tuple[str, ...]


# Staging areas that may never be published (a run timed out or its group was
# not confirmed empty), and those that must also be retained (not confirmed).
_UNPUBLISHABLE: set[tuple[str, str]] = set()
_RETAINED: set[tuple[str, str]] = set()
_STAGING_GUARD = threading.Lock()


def _staging_key(staging: StagingArea) -> tuple[str, str]:
    return str(_absolute(staging.root)), staging.operation_id


def _check_namespace(namespace: str) -> None:
    if namespace not in _NAMESPACES:
        raise ContainmentError(f"Not a cache namespace: {namespace!r}")


def _check_language(language: str) -> None:
    from chunker.grammar_management.core import _valid_language_name

    if not _valid_language_name(language):
        raise ContainmentError(f"Invalid grammar language: {language!r}")


def _dup(directory: _Dir) -> _Dir:
    return _Dir(
        directory.path, os.dup(directory.fd) if directory.fd is not None else None
    )


def _open_dirs(base: _Dir, *parts: str) -> _Dir:
    """Open ``base/part/...`` one real directory at a time, never following."""
    current = _dup(base)
    for part in parts:
        try:
            following = current.child(part)
        finally:
            current.close()
        current = following
    return current


def _list(directory: _Dir) -> list[str]:
    target = directory.fd if directory.fd is not None else directory.path
    return os.listdir(target)  # noqa: PTH208 - accepts a directory descriptor


def _namespace_dir(rootdir: _Dir, namespace: str, *, create: bool) -> _Dir | None:
    """Open a real namespace directory; re-create it no-follow if missing."""
    _check_namespace(namespace)
    st = rootdir.lstat(namespace)
    if st is None:
        if not create:
            return None
        with suppress(FileExistsError):
            rootdir.mkdir(namespace, 0o755)
    elif _is_link(st) or not stat.S_ISDIR(st.st_mode):
        raise ContainmentError(
            f"Namespace {rootdir.path / namespace} is not a real directory; refused"
        )
    return rootdir.child(namespace)


def _retired_dir(parent: _Dir, operation_id: str, *parts: str) -> _Dir:
    """``<parent>/.txn-retired/<operation-id>/<parts...>``, each with a marker.

    Retired items stay in the directory they were renamed from, so retirement
    never crosses a filesystem boundary.
    """
    current = _control_dir(parent, _RETIRED_DIR)
    for part in (operation_id, *parts):
        try:
            following = _control_dir(current, part)
        finally:
            current.close()
        current = following
    return current


@dataclass
class _Tally:
    bytes_freed: int = 0
    errors: list[str] = field(default_factory=list)


def _unique(errors: list[str]) -> tuple[str, ...]:
    """Each distinct error once, in first-seen order."""
    return tuple(dict.fromkeys(errors))


def _newest_mtime(parent: _Dir, name: str) -> tuple[float, float]:
    """Return (own lstat mtime, newest mtime in the entry), links as leaves.

    Raises :class:`NestedRootError` if a descendant is a regular lock file.
    """
    st = parent.lstat(name)
    if st is None:
        raise FileNotFoundError(errno.ENOENT, "Entry vanished", str(parent.path / name))
    own = st.st_mtime
    if _is_link(st) or not stat.S_ISDIR(st.st_mode):
        return own, own
    newest = own
    with parent.child(name) as directory:
        for child in _list(directory):
            child_st = directory.lstat(child)
            if child_st is None:
                continue
            if (
                child == LOCK_FILE_NAME
                and stat.S_ISREG(child_st.st_mode)
                and not _is_link(child_st)
            ):
                raise NestedRootError(
                    f"{directory.path / child} belongs to a nested cache root; "
                    "the entry is not retired"
                )
            newest = max(newest, _newest_mtime(directory, child)[1])
    return own, newest


def _refuse_nested_entry(parent: _Dir, name: str) -> None:
    _newest_mtime(parent, name)


def _delete_tree(parent: _Dir, name: str, tally: _Tally) -> None:
    """Anchored deletion: links are leaves, ENOENT means already deleted.

    Only the ``lstat`` size of regular files actually unlinked is counted.
    An error is recorded once, for the item that failed; its ancestors are
    then left in place without further messages.
    """
    path = parent.path / name
    try:
        st = parent.lstat(name)
    except OSError as error:
        tally.errors.append(f"{path}: {error}")
        return
    if st is None:
        return
    attributes = getattr(st, "st_file_attributes", 0)
    if stat.S_ISDIR(st.st_mode) and not _is_link(st):
        try:
            directory = parent.child(name)
        except FileNotFoundError:
            return
        except ContainmentError:
            # It became a link after lstat: remove it as a leaf.
            _delete_leaf(parent, name, path, None, tally)
            return
        except OSError as error:
            tally.errors.append(f"{path}: {error}")
            return
        failures = len(tally.errors)
        with directory:
            try:
                children = _list(directory)
            except OSError as error:
                tally.errors.append(f"{path}: {error}")
                return
            for child in children:
                _delete_tree(directory, child, tally)
        if len(tally.errors) > failures:
            return  # a descendant was reported; leave this directory quietly
        try:
            parent.rmdir(name)
        except FileNotFoundError:
            pass
        except OSError as error:
            tally.errors.append(f"{path}: {error}")
        return
    _delete_leaf(parent, name, path, st, tally, attributes)


def _delete_leaf(
    parent: _Dir,
    name: str,
    path: Path,
    st: os.stat_result | None,
    tally: _Tally,
    attributes: int = 0,
) -> None:
    try:
        if _WINDOWS and attributes & _ATTR_DIRECTORY:
            path.rmdir()  # directory symlink or junction: the link only
        else:
            if (
                _WINDOWS
                and st is not None
                and not _is_link(st)
                and attributes & _ATTR_READONLY
            ):
                path.chmod(stat.S_IWRITE)  # git objects are read-only
            parent.unlink(name)
    except FileNotFoundError:
        return
    except OSError as error:
        tally.errors.append(f"{path}: {error}")
        return
    if st is not None and stat.S_ISREG(st.st_mode) and not _is_link(st):
        tally.bytes_freed += st.st_size


def _delete_retired(
    root: Path, directory: Sequence[str], name: str, tally: _Tally
) -> None:
    """Delete ``<root>/<directory...>/<name>`` (retired garbage) outside the lock."""
    absolute = _absolute(root)
    try:
        rootdir = _Dir.open_root(absolute, _root_identity(absolute))
    except (OSError, CacheTransactionError) as error:
        tally.errors.append(f"{absolute}: {error}")
        return
    with rootdir:
        try:
            parent = _open_dirs(rootdir, *directory)
        except FileNotFoundError:
            return
        except (OSError, CacheTransactionError) as error:
            tally.errors.append(f"{absolute.joinpath(*directory)}: {error}")
            return
        with parent:
            _delete_tree(parent, name, tally)


def _retire(source: _Dir, name: str, operation_id: str, *label: str) -> None:
    """Rename ``source/name`` to ``source/.txn-retired/<operation-id>/<label>/<name>``."""
    with _retired_dir(source, operation_id, *label) as target:
        source.replace_into(name, target, name)


def create_staging(root: Path, *, timeout: float = DEFAULT_LOCK_TIMEOUT) -> StagingArea:
    """Create ``<namespace>/.txn-staging/<operation-id>/`` in each namespace."""
    absolute = _absolute(root)
    operation_id = _new_operation_id()
    ctx = _LockContext("create_staging", absolute, operation_id)
    with _locked(root, timeout, ctx) as rootdir:
        for namespace in _NAMESPACES:
            directory = _namespace_dir(rootdir, namespace, create=True)
            assert directory is not None
            with (
                directory,
                _control_dir(directory, _STAGING_DIR) as area,
                _control_dir(area, operation_id),
            ):
                pass
    return StagingArea(root=Path(root), operation_id=operation_id)


def _inside(path: Path, parent: Path) -> bool:
    try:
        Path(os.path.abspath(path)).relative_to(parent)  # noqa: PTH100
    except ValueError:
        return False
    return True


def _read_stream(stream: Any, sink: list[bytes]) -> None:
    with suppress(OSError, ValueError):
        sink.extend(iter(lambda: stream.read(65536), b""))


def _start_readers(
    process: subprocess.Popen[bytes],
) -> tuple[list[bytes], list[bytes], list[threading.Thread]]:
    out: list[bytes] = []
    err: list[bytes] = []
    readers = [
        threading.Thread(target=_read_stream, args=(process.stdout, out), daemon=True),
        threading.Thread(target=_read_stream, args=(process.stderr, err), daemon=True),
    ]
    for reader in readers:
        reader.start()
    return out, err, readers


def _finish_readers(
    process: subprocess.Popen[bytes], readers: list[threading.Thread]
) -> bool:
    """Join the output readers; return False if one is still blocked.

    A reader still running means a process outside the group holds the pipe.
    Its stream is left open (closing it would block on the reader), and the
    run is treated as not confirmed empty.
    """
    finished = True
    for reader, stream in zip(readers, (process.stdout, process.stderr), strict=True):
        reader.join(_READER_JOIN)
        if reader.is_alive():
            finished = False
        elif stream is not None:
            with suppress(OSError):
                stream.close()
    return finished


def _group_members(pgid: int) -> list[Any]:
    """Live (non-zombie) processes in a POSIX process group."""
    import psutil

    members = []
    for process in psutil.process_iter():
        try:
            if os.getpgid(process.pid) != pgid:
                continue
            if process.status() == psutil.STATUS_ZOMBIE:
                continue
        except (ProcessLookupError, PermissionError, psutil.Error):
            continue
        members.append(process)
    return members


def _reap_adopted(pgid: int, leader: int) -> None:
    """Reap zombies of the group that became this process's children."""
    import psutil

    with suppress(psutil.Error):
        for child in psutil.Process().children():
            if child.pid == leader:
                continue
            with suppress(ProcessLookupError, PermissionError, ChildProcessError):
                if os.getpgid(child.pid) == pgid:
                    os.waitpid(child.pid, os.WNOHANG)


def _kill_and_confirm_posix(pgid: int, leader: int) -> bool:
    """Kill the whole group, repeatedly, until no non-zombie member remains.

    Runs while the leader is still unreaped, so the group ID cannot be
    recycled under the kill (N5 on treesitter-chunker#540).
    """
    deadline = time.monotonic() + _GROUP_CONFIRM_DEADLINE
    delay = _BACKOFF_FIRST
    while True:
        with suppress(ProcessLookupError, PermissionError):
            os.killpg(pgid, signal.SIGKILL)
        _reap_adopted(pgid, leader)
        if not _group_members(pgid):
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(delay)
        delay = min(delay * 2, _BACKOFF_MAX)


def _run_posix(
    staging: StagingArea,
    argv: Sequence[str],
    cwd: Path,
    timeout: float,
    env: Mapping[str, str] | None,
    ctx: _LockContext,
    outcome: dict[str, bool],
) -> StagedRun:
    try:
        process = subprocess.Popen(
            list(argv),
            cwd=cwd,
            env=dict(env) if env is not None else None,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
    except OSError:
        outcome["launch_failed"] = True  # nothing was started
        raise
    out: list[bytes] = []
    err: list[bytes] = []
    readers: list[threading.Thread] = []
    exited = threading.Event()
    waiter_started = False
    timed_out = True
    group_empty = False
    returncode: int | None = None
    try:
        # Guarded from the first statement after Popen: the child exists now.
        outcome["launched"] = True
        ctx.seam("run.after_launch")
        out, err, readers = _start_readers(process)
        waitid = getattr(os, "waitid", None)
        nowait = getattr(os, "WNOWAIT", None)

        def wait_without_reaping() -> None:
            """Wait for the leader to exit but leave it unreaped (a zombie).

            An unreaped leader keeps the group ID from being recycled while
            the group is killed and checked. ``os.waitid(WNOWAIT)`` does this
            where it exists; macOS lacks it, so the leader's state is polled.
            """
            if waitid is not None and nowait is not None:
                with suppress(ChildProcessError, OSError):
                    waitid(os.P_PID, process.pid, os.WEXITED | nowait)
            else:
                import psutil

                delay = _BACKOFF_FIRST
                while True:
                    try:
                        status = psutil.Process(process.pid).status()
                        if status == psutil.STATUS_ZOMBIE:
                            break
                    except psutil.NoSuchProcess:
                        break
                    time.sleep(delay)
                    delay = min(delay * 2, _BACKOFF_MAX)
            exited.set()

        threading.Thread(target=wait_without_reaping, daemon=True).start()
        waiter_started = True
        ctx.seam("run.waiting")
        timed_out = not exited.wait(timeout)
        ctx.seam("run.after_exit")
    finally:
        # Always, including on KeyboardInterrupt or any other exception: kill
        # and confirm the group before anyone may dispose of the staging. The
        # leader is still unreaped here, so its group ID cannot be recycled.
        group_empty = _kill_and_confirm_posix(process.pid, process.pid)
        if waiter_started:
            exited.wait(_GROUP_CONFIRM_DEADLINE)
        returncode = process.wait()
        if readers:
            if not _finish_readers(process, readers):
                group_empty = False
        else:
            for stream in (process.stdout, process.stderr):
                if stream is not None:
                    with suppress(OSError):
                        stream.close()
        outcome["group_empty"] = group_empty
    if group_empty:
        ctx.seam("run.after_group_empty")
    return StagedRun(
        returncode=None if timed_out else returncode,
        stdout=b"".join(out).decode("utf-8", "replace"),
        stderr=b"".join(err).decode("utf-8", "replace"),
        timed_out=timed_out,
        group_empty=group_empty,
    )


def _run_windows(
    staging: StagingArea,
    argv: Sequence[str],
    cwd: Path,
    timeout: float,
    env: Mapping[str, str] | None,
    ctx: _LockContext,
    outcome: dict[str, bool],
) -> StagedRun:
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)  # type: ignore[attr-defined]
    ntdll = ctypes.WinDLL("ntdll")  # type: ignore[attr-defined]

    class BasicLimit(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_int64),
            ("PerJobUserTimeLimit", ctypes.c_int64),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class IoCounters(ctypes.Structure):
        _fields_ = [
            (name, ctypes.c_uint64)
            for name in (
                "ReadOperationCount",
                "WriteOperationCount",
                "OtherOperationCount",
                "ReadTransferCount",
                "WriteTransferCount",
                "OtherTransferCount",
            )
        ]

    class ExtendedLimit(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", BasicLimit),
            ("IoInfo", IoCounters),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    class Accounting(ctypes.Structure):
        _fields_ = [
            ("TotalUserTime", ctypes.c_int64),
            ("TotalKernelTime", ctypes.c_int64),
            ("ThisPeriodTotalUserTime", ctypes.c_int64),
            ("ThisPeriodTotalKernelTime", ctypes.c_int64),
            ("TotalPageFaultCount", wintypes.DWORD),
            ("TotalProcesses", wintypes.DWORD),
            ("ActiveProcesses", wintypes.DWORD),
            ("TotalTerminatedProcesses", wintypes.DWORD),
        ]

    kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    kernel32.SetInformationJobObject.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        ctypes.c_void_p,
        wintypes.DWORD,
    ]
    kernel32.QueryInformationJobObject.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.c_void_p,
    ]
    kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel32.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    ntdll.NtResumeProcess.argtypes = [wintypes.HANDLE]

    job = kernel32.CreateJobObjectW(None, None)
    if not job:
        outcome["launch_failed"] = True  # nothing was started
        raise CacheTransactionError(
            f"Could not create a job object: {ctypes.get_last_error()}"  # type: ignore[attr-defined]
        )
    try:
        limits = ExtendedLimit()
        limits.BasicLimitInformation.LimitFlags = 0x2000  # KILL_ON_JOB_CLOSE
        if not kernel32.SetInformationJobObject(
            job, 9, ctypes.byref(limits), ctypes.sizeof(limits)
        ):
            outcome["launch_failed"] = True  # nothing was started
            raise CacheTransactionError("Could not configure the job object")
        try:
            process = subprocess.Popen(
                list(argv),
                cwd=cwd,
                env=dict(env) if env is not None else None,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=0x00000004 | 0x00000200,  # SUSPENDED | NEW_GROUP
            )
        except OSError:
            outcome["launch_failed"] = True  # nothing was started
            raise
        out: list[bytes] = []
        err: list[bytes] = []
        readers: list[threading.Thread] = []
        assigned = False
        timed_out = True
        group_empty = False
        returncode: int | None = None
        try:
            # Guarded from the first statement after Popen: the child exists.
            outcome["launched"] = True
            ctx.seam("run.after_launch")
            handle = int(process._handle)  # type: ignore[attr-defined]
            if not kernel32.AssignProcessToJobObject(job, handle):
                raise CacheTransactionError("Could not assign the process to its job")
            assigned = True
            ntdll.NtResumeProcess(handle)
            out, err, readers = _start_readers(process)
            ctx.seam("run.waiting")
            try:
                process.wait(timeout)
                timed_out = False
            except subprocess.TimeoutExpired:
                pass
            ctx.seam("run.after_exit")
        finally:
            # Always, including on KeyboardInterrupt: terminate the job (or the
            # still-suspended, unassigned child) and confirm it is empty before
            # anyone may dispose of the staging.
            if assigned:
                kernel32.TerminateJobObject(job, 1)
                deadline = time.monotonic() + _GROUP_CONFIRM_DEADLINE
                delay = _BACKOFF_FIRST
                accounting = Accounting()
                while True:
                    if (
                        kernel32.QueryInformationJobObject(
                            job,
                            1,
                            ctypes.byref(accounting),
                            ctypes.sizeof(accounting),
                            None,
                        )
                        and accounting.ActiveProcesses == 0
                    ):
                        group_empty = True
                        break
                    if time.monotonic() >= deadline:
                        break
                    time.sleep(delay)
                    delay = min(delay * 2, _BACKOFF_MAX)
            else:
                # Suspended and never resumed: it has no descendants.
                with suppress(OSError):
                    process.kill()
                group_empty = True
            returncode = process.wait()
            if readers:
                if not _finish_readers(process, readers):
                    group_empty = False
            else:
                for stream in (process.stdout, process.stderr):
                    if stream is not None:
                        with suppress(OSError):
                            stream.close()
            outcome["group_empty"] = group_empty
    finally:
        kernel32.CloseHandle(job)
    if group_empty:
        ctx.seam("run.after_group_empty")
    return StagedRun(
        returncode=None if timed_out else returncode,
        stdout=b"".join(out).decode("utf-8", "replace"),
        stderr=b"".join(err).decode("utf-8", "replace"),
        timed_out=timed_out,
        group_empty=group_empty,
    )


def run_in_staging(
    staging: StagingArea,
    argv: Sequence[str],
    *,
    cwd: Path,
    timeout: float,
    env: Mapping[str, str] | None = None,
) -> StagedRun:
    """Run a subprocess that may write into ``staging``, in its own group/job.

    The whole process group (POSIX) or job (Windows) is killed after the
    direct child exits or times out, and is confirmed empty before return,
    also when the wait is interrupted (for example by ``KeyboardInterrupt``,
    which is re-raised afterwards). A timeout, an unconfirmed group, a reader
    still blocked on the output, or an interruption makes the staging
    unpublishable; an unconfirmed or interrupted-before-confirmation run also
    makes it retained, so ``discard_staging`` never deletes it.
    """
    if not any(_inside(cwd, staging.path(ns)) for ns in _NAMESPACES):
        raise ContainmentError(f"Working directory {cwd} is outside the staging")
    key = _staging_key(staging)
    ctx = _LockContext(
        "run_in_staging",
        _absolute(staging.root),
        staging.operation_id,
        program=Path(argv[0]).name if argv else "",
    )
    runner = _run_windows if _WINDOWS else _run_posix
    outcome = {"launched": False, "launch_failed": False, "group_empty": False}
    with _STAGING_GUARD:
        was_unpublishable = key in _UNPUBLISHABLE
        was_retained = key in _RETAINED
        # Conservatively unsafe *before* the launch: a child may exist as soon
        # as Popen creates it, even if an interruption arrives before Popen
        # returns. Only confirmed shutdown, or a launch that started nothing,
        # clears these marks again.
        _UNPUBLISHABLE.add(key)
        _RETAINED.add(key)
    try:
        result = runner(staging, argv, cwd, timeout, env, ctx, outcome)
    except BaseException:
        with _STAGING_GUARD:
            if outcome["launch_failed"]:
                if not was_unpublishable:
                    _UNPUBLISHABLE.discard(key)
                if not was_retained:
                    _RETAINED.discard(key)
            elif outcome["group_empty"] and not was_retained:
                _RETAINED.discard(key)  # confirmed shutdown: unpublishable only
        raise
    with _STAGING_GUARD:
        if result.group_empty and not was_retained:
            _RETAINED.discard(key)
        if result.group_empty and not result.timed_out and not was_unpublishable:
            _UNPUBLISHABLE.discard(key)
    return result


def _stamp(directory: _Dir, name: str) -> None:
    """Set the staged entry's own mtime to now without following links."""
    st = directory.lstat(name)
    if st is None:
        raise FileNotFoundError(
            errno.ENOENT, "Staged entry missing", str(directory.path / name)
        )
    if _is_link(st):
        raise ContainmentError(f"Staged entry is a link: {directory.path / name}")
    if directory.fd is not None and os.utime in os.supports_dir_fd:
        os.utime(name, dir_fd=directory.fd, follow_symlinks=False)
    else:
        os.utime(directory.path / name)


def publish_entry(
    staging: StagingArea,
    namespace: Namespace,
    name: str,
    *,
    timeout: float = DEFAULT_LOCK_TIMEOUT,
) -> Path:
    """Publish ``<namespace>/.txn-staging/<op>/<name>`` as ``<namespace>/<name>``.

    Under the lock: stamp the staged entry, retire any existing entry to
    ``<namespace>/.txn-retired/<op>/`` (refusing nested roots), then promote
    the staged entry. Every rename stays inside ``<namespace>``. If promotion
    fails the old entry is renamed back; if that fails too, the error names
    all three locations. The retired generation is deleted outside the lock.
    """
    _check_namespace(namespace)
    _check_component(name, "Entry name")
    absolute = _absolute(staging.root)
    with _STAGING_GUARD:
        if _staging_key(staging) in _UNPUBLISHABLE:
            raise CacheTransactionError(
                f"Staging {staging.path(namespace)} is unpublishable: a run timed "
                "out, was interrupted, or its process group was not confirmed empty"
            )
    ctx = _LockContext("publish_entry", absolute, staging.operation_id)
    seam = {"namespace": namespace, "name": name}
    retired = False
    with _locked(staging.root, timeout, ctx) as rootdir:
        target = _namespace_dir(rootdir, namespace, create=True)
        assert target is not None
        with (
            target,
            _open_dirs(target, _STAGING_DIR, staging.operation_id) as staged,
        ):
            _stamp(staged, name)
            if target.lstat(name) is not None:
                _refuse_nested_entry(target, name)
                _retire(target, name, staging.operation_id)
                retired = True
                ctx.seam("publish.after_retire", **seam)
            ctx.seam("publish.before_promote", **seam)
            try:
                staged.replace_into(name, target, name)
            except OSError as error:
                published = absolute / namespace / name
                garbage = (
                    absolute / namespace / _RETIRED_DIR / staging.operation_id / name
                )
                if not retired:
                    raise CacheTransactionError(
                        f"Could not publish {published}: {error}"
                    ) from error
                try:
                    with _retired_dir(target, staging.operation_id) as old:
                        old.replace_into(name, target, name)
                except OSError as back:
                    raise CacheTransactionError(
                        f"Could not publish {published} ({error}) or restore its "
                        f"previous generation ({back}). {published} is absent; the "
                        f"previous generation is in {garbage}; the new one remains "
                        f"in {staging.path(namespace) / name}"
                    ) from error
                raise CacheTransactionError(
                    f"Could not publish {published} ({error}); the previous "
                    "generation was restored"
                ) from error
    if retired:
        tally = _Tally()
        _delete_retired(
            staging.root, (namespace, _RETIRED_DIR), staging.operation_id, tally
        )
        for message in tally.errors:
            logger.warning("Retired cache entry not deleted: %s", message)
    return absolute / namespace / name


def remove_entry(
    root: Path,
    namespace: Namespace,
    name: str,
    *,
    timeout: float = DEFAULT_LOCK_TIMEOUT,
) -> PruneResult:
    """Retire one cache entry under the lock and delete it outside the lock."""
    _check_namespace(namespace)
    _check_component(name, "Entry name")
    operation_id = _new_operation_id()
    ctx = _LockContext("remove_entry", _absolute(root), operation_id)
    with _locked(root, timeout, ctx) as rootdir:
        directory = _namespace_dir(rootdir, namespace, create=False)
        if directory is None:
            return PruneResult(0, 0, (), ())
        with directory:
            if directory.lstat(name) is None:
                return PruneResult(0, 0, (), ())
            _refuse_nested_entry(directory, name)
            _retire(directory, name, operation_id)
    tally = _Tally()
    _delete_retired(root, (namespace, _RETIRED_DIR), operation_id, tally)
    return PruneResult(1, tally.bytes_freed, (), _unique(tally.errors))


def _claim_garbage(
    root: Path,
    namespace: Namespace,
    operation_id: str,
    timeout: float,
    ctx: _LockContext,
) -> None:
    """Move other operations' retired trees under ``<own-id>/claimed/``."""
    with _locked(root, timeout, ctx) as rootdir:
        directory = _namespace_dir(rootdir, namespace, create=False)
        if directory is None:
            return
        with directory:
            if directory.lstat(_RETIRED_DIR) is None:
                return
            with _open_dirs(directory, _RETIRED_DIR) as retired:
                others = [
                    name
                    for name in _list(retired)
                    if name not in (operation_id, MARKER_NAME)
                ]
                if not others:
                    return
                with _retired_dir(directory, operation_id, "claimed") as claimed:
                    for other in others:
                        st = retired.lstat(other)
                        if st is None or _is_link(st) or not stat.S_ISDIR(st.st_mode):
                            continue
                        with suppress(FileNotFoundError):
                            retired.replace_into(other, claimed, other)


def _report_staging(rootdir: _Dir, namespace: str, cutoff: float) -> list[str]:
    """Log staging areas older than the cutoff; staging is never pruned."""
    retained = []
    with (
        suppress(OSError, CacheTransactionError),
        _open_dirs(rootdir, namespace, _STAGING_DIR) as area,
    ):
        for name in _list(area):
            st = area.lstat(name)
            if st is not None and name != MARKER_NAME and st.st_mtime < cutoff:
                retained.append(str(area.path / name))
    for path in retained:
        logger.info("Retaining staging area (never pruned): %s", path)
    return retained


def prune_entries(
    root: Path,
    namespace: Namespace,
    *,
    cutoff: float,
    timeout: float = DEFAULT_LOCK_TIMEOUT,
) -> PruneResult:
    """Retire and delete entries whose whole tree is older than ``cutoff``.

    Candidates are listed without the lock, then each is re-checked under the
    lock (no-follow walk, links as leaves) and retired, within the namespace,
    before deletion. A candidate that cannot be checked or retired is
    reported in ``errors`` and ``skipped``, and the others still run.
    ``bytes_freed`` counts only regular files this call actually unlinked.
    """
    _check_namespace(namespace)
    absolute = _absolute(root)
    operation_id = _new_operation_id()
    ctx = _LockContext("prune_entries", absolute, operation_id)
    skipped: list[str] = []
    tally = _Tally()
    removed = 0
    stopped = False
    with _locked(root, timeout, ctx) as rootdir:
        directory = _namespace_dir(rootdir, namespace, create=False)
    if directory is None:
        return PruneResult(0, 0, (), ())
    directory.close()
    rootdir = _Dir.open_root(absolute, _root_identity(absolute))
    with rootdir, _open_dirs(rootdir, namespace) as listing:
        candidates = _list(listing)
    ctx.seam("prune.after_enumerate", namespace=namespace)
    for name in candidates:
        if name.startswith(CONTROL_DIR_NAME):
            continue  # reserved: .txn-staging, .txn-retired and the like
        retired = False
        try:
            with _locked(root, timeout, ctx) as rootdir:
                current = _namespace_dir(rootdir, namespace, create=False)
                if current is None:
                    break
                with current:
                    try:
                        own, newest = _newest_mtime(current, name)
                    except FileNotFoundError:
                        continue
                    ctx.seam("prune.after_recheck", namespace=namespace, name=name)
                    if newest >= cutoff:
                        if own < cutoff:
                            logger.warning(
                                "Skipping mixed-age cache directory: %s",
                                current.path / name,
                            )
                        continue
                    _retire(current, name, operation_id)
                    retired = True
                    removed += 1
        except NestedRootError as error:
            skipped.append(name)
            tally.errors.append(str(error))
            continue
        except (CacheLockTimeoutError, _RootMovedError) as error:
            # Later candidates would fail the same way: stop, and report the
            # truthful counts of what this call already removed.
            tally.errors.append(f"Stopped before {name}: {error}")
            stopped = True
            break
        except (OSError, CacheTransactionError) as error:
            skipped.append(name)
            tally.errors.append(f"{absolute / namespace / name}: {error}")
            continue
        if retired:
            _delete_retired(root, (namespace, _RETIRED_DIR, operation_id), name, tally)
    try:
        if not stopped:
            _claim_garbage(root, namespace, operation_id, timeout, ctx)
        _delete_retired(root, (namespace, _RETIRED_DIR), operation_id, tally)
        if not stopped:
            with _locked(root, timeout, ctx) as rootdir:
                _report_staging(rootdir, namespace, cutoff)
    except (OSError, CacheTransactionError) as error:
        tally.errors.append(str(error))
    return PruneResult(
        removed, tally.bytes_freed, tuple(skipped), _unique(tally.errors)
    )


def discard_staging(
    staging: StagingArea, *, timeout: float = DEFAULT_LOCK_TIMEOUT
) -> PruneResult:
    """Retire each namespace's staging directory in place, then delete it.

    ``<namespace>/.txn-staging/<op>`` becomes
    ``<namespace>/.txn-retired/<op>/staging``. Staging whose process group was
    not confirmed empty is retained and reported. A file that cannot be
    deleted (for example, a library still loaded on Windows) stays in
    ``.txn-retired`` for a later prune to claim.
    """
    key = _staging_key(staging)
    with _STAGING_GUARD:
        if key in _RETAINED:
            paths = tuple(str(staging.path(ns)) for ns in _NAMESPACES)
            message = (
                f"Staging {', '.join(paths)} is retained: a process group was not "
                "confirmed empty"
            )
            logger.warning(message)
            return PruneResult(0, 0, paths, (message,))
    ctx = _LockContext("discard_staging", _absolute(staging.root), staging.operation_id)
    retired: list[Namespace] = []
    with _locked(staging.root, timeout, ctx) as rootdir:
        for namespace in _NAMESPACES:
            directory = _namespace_dir(rootdir, namespace, create=False)
            if directory is None:
                continue
            with directory:
                if directory.lstat(_STAGING_DIR) is None:
                    continue
                with _open_dirs(directory, _STAGING_DIR) as area:
                    if area.lstat(staging.operation_id) is None:
                        continue
                    with _retired_dir(directory, staging.operation_id) as target:
                        area.replace_into(staging.operation_id, target, "staging")
                    retired.append(namespace)
    tally = _Tally()
    for namespace in retired:
        _delete_retired(
            staging.root, (namespace, _RETIRED_DIR), staging.operation_id, tally
        )
    with _STAGING_GUARD:
        _UNPUBLISHABLE.discard(key)
    return PruneResult(0, tally.bytes_freed, (), _unique(tally.errors))

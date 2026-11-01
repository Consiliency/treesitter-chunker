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
import stat
import threading
import time
import uuid
from collections.abc import Callable, Iterator, Mapping
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

_CONTROL_CHILDREN: Final = ("staging", "retired", "rollback")
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
                raise CacheTransactionError(
                    f"Cache root {root} no longer resolves to the directory opened"
                )
            return cls(root, None)
        fd = os.open(root, os.O_RDONLY | _DIRECTORY | _CLOEXEC)
        try:
            if _identity(os.fstat(fd)) != identity:
                raise CacheTransactionError(
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
        if _identity(absolute.stat()) != identity or (
            rootdir.fd is not None and _identity(os.fstat(rootdir.fd)) != identity
        ):
            raise CacheTransactionError(
                f"Cache root {absolute} no longer resolves to the directory opened"
            )
        if _lock_key(rootdir) != key:
            raise ContainmentError(f"Cache lock file was replaced: {absolute}")
        ctx.seam("lock.acquired")
        _initialize(rootdir)
        ctx.seam("root.after_init")
        # Post-initialization check (contract "Nested roots" rule 2).
        _refuse_nested(absolute)
        if _identity(absolute.stat()) != identity:
            raise CacheTransactionError(
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

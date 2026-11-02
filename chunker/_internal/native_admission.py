"""Shared native-admission helpers around ``probe_native_grammar``.

These helpers implement three rules of the native validation contract
(``docs/development/native-validation-contract.md``, ADMITPIN section) on top
of the one admission mechanism, :func:`chunker.grammar.integrity.probe_native_grammar`:

- rule 3 of IF-0-ADMITPIN-1: a missing candidate is ``missing``; a language
  without a ``str`` pin is ``untrusted`` without opening the candidate; the
  probe receives only a fresh one-field ``{"sha256": ...}`` record;
- the verdict-reuse key: a positive admission is reused only inside the
  process that produced it, keyed by content, pin and environment, never by
  path or stat data;
- "Using an admitted grammar in-process": a site that maps a grammar loads a
  verified private copy that was admitted, never the candidate path.

Nothing here changes the probe or its lifecycle code.
"""

from __future__ import annotations

import atexit
import functools
import hashlib
import hmac
import json
import logging
import os
import platform
import shutil
import stat
import sys
import sysconfig
import tempfile
import threading
from collections.abc import Callable, Mapping
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

from chunker._internal.package_supplier import (
    MISMATCH,
    SUPPLIED,
    package_supplied_digest,
)
from chunker._internal.trusted_artifacts import pin_provenance
from chunker.grammar import integrity
from chunker.grammar.integrity import (
    ArtifactIntegrityError,
    NativeProbeResult,
    verify_artifact,
)

logger = logging.getLogger(__name__)

#: Bumped whenever validation semantics change (verdict-reuse key field).
NATIVE_VERDICT_VALIDATOR_SCHEMA = 1
_VERDICT_SCHEMA = "chunker.native_verdict.v1"
_PROBE_SCHEMA = "native_probe.v1"
#: ``sample=b""`` with ``integrity.DEFAULT_PROBE_TIMEOUT`` (treesitter-chunker#561);
#: ``default-v1`` (the retired 10 s deadline) entries never match it.
_PROBE_PROFILE = "default-v2"
_DEFAULT_SAMPLE = b""
#: Binary read-only open; ``O_BINARY`` keeps Windows from translating bytes.
_READ_FLAGS = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NONBLOCK", 0)
_HEX64 = frozenset("0123456789abcdef")

_lock = threading.RLock()
#: verdict key -> stored inspector metadata (``None`` for probe-only verdicts)
_verdicts: dict[str, Any] = {}
#: (language, content digest) -> verdict keys, so a load failure drops them all
_verdict_index: dict[tuple[str, str], set[str]] = {}
#: (language, digest) -> admitted private copy
_copies: dict[tuple[str, str], Path] = {}
#: (language, digest) -> lock held across check, create and register
_copy_locks: dict[tuple[str, str], threading.Lock] = {}
_copy_roots: list[Path] = []
#: The process that created ``_copy_roots`` and alone may remove them.
_copy_owner_pid = os.getpid()
_cleanup_registered = False


def _reset_after_fork() -> None:
    """Give a forked child an empty admission state (POSIX ``fork``).

    Admission is per process: a child must probe again before its first use of
    an artifact, and it never owns (or removes) its parent's private copies.
    Locks are recreated because the parent's could be held mid-operation.
    """
    global _lock, _copy_owner_pid
    _lock = threading.RLock()
    _verdicts.clear()
    _verdict_index.clear()
    _copies.clear()
    _copy_locks.clear()
    _copy_roots.clear()
    _copy_owner_pid = os.getpid()


if hasattr(os, "register_at_fork"):
    os.register_at_fork(after_in_child=_reset_after_fork)


def _distribution_version(name: str) -> str:
    try:
        return version(name)
    except PackageNotFoundError:
        return "unknown"


@functools.lru_cache(maxsize=1)
def _environment() -> dict[str, Any]:
    return {
        "validator_schema": NATIVE_VERDICT_VALIDATOR_SCHEMA,
        "chunker": _distribution_version("treesitter-chunker"),
        "tree_sitter": _distribution_version("tree-sitter"),
        "python": sys.implementation.cache_tag,
        "abi": sysconfig.get_config_var("SOABI") or "",
        "platform": sys.platform,
        "machine": platform.machine(),
    }


def _verdict_payload(
    *,
    language: str,
    pin_sha256: str,
    content_sha256: str,
    level: str,
    inspector: str,
) -> dict[str, Any]:
    """Return the 15 fields of the frozen ``chunker.native_verdict.v1`` key."""
    return {
        "schema": _VERDICT_SCHEMA,
        "language": language,
        "pin_sha256": pin_sha256.lower(),
        "content_sha256": content_sha256.lower(),
        "level": level,
        "probe_schema": _PROBE_SCHEMA,
        "probe_profile": _PROBE_PROFILE,
        "inspector": inspector,
        **_environment(),
    }


def verdict_key(
    *,
    language: str,
    pin_sha256: str,
    content_sha256: str,
    level: str,
    inspector: str,
) -> str:
    """Return the frozen ``chunker.native_verdict.v1`` reuse key.

    It never contains a path, mtime, size, inode, ctime or timestamp.
    """
    payload = _verdict_payload(
        language=language,
        pin_sha256=pin_sha256,
        content_sha256=content_sha256,
        level=level,
        inspector=inspector,
    )
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def has_verdict(key: str) -> bool:
    """Whether this process holds a fresh positive admission under ``key``."""
    with _lock:
        return key in _verdicts


def store_verdict(
    key: str, *, language: str, content_sha256: str, metadata: Any = None
) -> None:
    """Record a fresh ``ok`` admission produced in this process."""
    with _lock:
        _verdicts[key] = metadata
        _verdict_index.setdefault((language, content_sha256.lower()), set()).add(key)


def drop_verdicts(language: str, content_sha256: str) -> None:
    """Forget every verdict for ``language`` and these bytes (load failure, rule 4)."""
    with _lock:
        for key in _verdict_index.pop((language, content_sha256.lower()), set()):
            _verdicts.pop(key, None)


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and set(value.lower()) <= _HEX64


def hash_regular_file(path: Path) -> str | None:
    """Hash ``path`` from one open descriptor, or ``None`` if it is not usable.

    ``None`` means: not a nonempty regular file, or it could not be opened or
    read. The caller then lets the probe decide (it reports ``untrusted``,
    ``empty``, ``missing`` or ``child_failed``) without any reuse.
    """
    try:
        descriptor = os.open(path, _READ_FLAGS)
    except OSError:
        return None
    try:
        status = os.fstat(descriptor)
        if not stat.S_ISREG(status.st_mode) or status.st_size == 0:
            return None
        digest = hashlib.sha256()
        while True:
            block = os.read(descriptor, 1024 * 1024)
            if not block:
                break
            digest.update(block)
        return digest.hexdigest()
    except OSError:
        return None
    finally:
        os.close(descriptor)


def admission_record(
    path: Path, language: str, trusted_artifacts: Mapping[str, Any] | None
) -> tuple[dict[str, str] | None, NativeProbeResult | None]:
    """Choose the one-field probe record for ``path`` under the one trust rule.

    A RECORD-verified package file of our own wheel uses its RECORD digest and
    needs no pin; a package file whose bytes differ from RECORD is
    ``integrity_mismatch`` and no user pin can override it; any other local
    candidate uses ``trusted_artifacts[language]`` (rule 3) and is
    ``untrusted`` without one.

    Returns:
        ``(record, None)``, or ``(None, rejection)``.
    """
    status, supplied = package_supplied_digest(Path(path))
    if status == MISMATCH:
        return None, NativeProbeResult(False, "integrity_mismatch", None)
    if status == SUPPLIED and supplied is not None:
        return {"sha256": supplied}, None
    record = pin_provenance(trusted_artifacts, language)
    if record is None:
        return None, NativeProbeResult(False, "untrusted", None)
    return record, None


def admit_native_candidate(
    path: Path,
    language: str,
    trusted_artifacts: Mapping[str, Any] | None,
    *,
    level: str = "probe",
    inspector: str = "none",
    inspect_artifact: Callable[[Path], Any] | None = None,
    sample: bytes = _DEFAULT_SAMPLE,
    timeout: float | None = None,
    probe: Callable[..., NativeProbeResult] | None = None,
) -> tuple[NativeProbeResult, Any]:
    """Admit ``path`` for ``language`` under ``trusted_artifacts[language]``.

    Lookup order (contract, "Verdict-reuse key"): a candidate that does not
    exist is ``missing``; a language without a ``str`` pin is ``untrusted``
    and the candidate is neither opened nor probed; the candidate is hashed
    from one open regular file, and a digest that differs from the pin is
    ``integrity_mismatch`` without probing; only then is a verdict produced in
    this process reused. Otherwise the probe runs with the one-field record.

    ``inspect_artifact`` runs on the probe's admitted snapshot; its return
    value is the returned metadata, and it is stored with the verdict under
    ``inspector``. ``timeout=None`` leaves the deadline to the probe's own
    default; no default is restated here. The default profile is
    ``sample=b""`` with that default, compared against the imported
    ``integrity.DEFAULT_PROBE_TIMEOUT`` (an explicit equal value is the same
    profile). A probe with a non-default ``sample`` or ``timeout`` is never
    answered from, or stored in, the verdict store.

    Returns:
        ``(result, metadata)``; ``metadata`` is ``None`` unless the result is
        ``ok`` and an inspector ran (or was reused).
    """
    if (inspect_artifact is None) != (inspector == "none"):
        raise ValueError("inspector must name inspect_artifact, and only it")
    probe_function = probe or integrity.probe_native_grammar
    candidate = Path(path)
    if not os.path.lexists(candidate):
        return NativeProbeResult(False, "missing", None), None
    record, rejection = admission_record(candidate, language, trusted_artifacts)
    if record is None:
        assert rejection is not None
        return rejection, None
    pin = record["sha256"]
    default_profile = sample == _DEFAULT_SAMPLE and (
        timeout is None or timeout == integrity.DEFAULT_PROBE_TIMEOUT
    )
    content = hash_regular_file(candidate) if candidate.is_absolute() else None
    key: str | None = None
    if content is not None and _is_sha256(pin):
        if not hmac.compare_digest(content, pin.lower()):
            return NativeProbeResult(False, "integrity_mismatch", None), None
        if default_profile:
            key = verdict_key(
                language=language,
                pin_sha256=pin,
                content_sha256=content,
                level=level,
                inspector=inspector,
            )
            with _lock:
                if key in _verdicts:
                    return NativeProbeResult(True, "ok", content), _verdicts[key]

    captured: dict[str, Any] = {}

    def inspect(snapshot: Path) -> None:
        assert inspect_artifact is not None
        captured["metadata"] = inspect_artifact(snapshot)

    result = probe_function(
        candidate,
        language,
        provenance=record,
        sample=sample,
        inspect_artifact=inspect if inspect_artifact is not None else None,
        **({} if timeout is None else {"timeout": timeout}),
    )
    if not result.supported:
        return result, None
    metadata = captured.get("metadata")
    if (
        key is not None
        and content is not None
        and result.artifact_sha256 is not None
        and hmac.compare_digest(result.artifact_sha256, content)
    ):
        store_verdict(key, language=language, content_sha256=content, metadata=metadata)
    return result, metadata


def _remove_copy_roots() -> None:
    with _lock:
        if os.getpid() != _copy_owner_pid:
            # Never remove another process's copies (inherited atexit handler).
            return
        roots = list(_copy_roots)
        _copy_roots.clear()
        _copies.clear()
    for root in roots:
        shutil.rmtree(root, ignore_errors=True)


def _register_copy_root(root: Path) -> None:
    global _cleanup_registered
    with _lock:
        _copy_roots.append(root)
        # POSIX may unlink a mapped file; Windows cannot delete a loaded
        # library, so copies left there after exit are a documented residual.
        if not _cleanup_registered and sys.platform != "win32":
            atexit.register(_remove_copy_roots)
            _cleanup_registered = True


def _copy_candidate(candidate: Path, root: Path) -> Path:
    """Copy ``candidate`` from one open regular file into an exclusive file."""
    source_fd = os.open(candidate, _READ_FLAGS)
    try:
        if not stat.S_ISREG(os.fstat(source_fd).st_mode):
            raise ArtifactIntegrityError("Candidate is not a regular file")
        destination_fd, name = tempfile.mkstemp(suffix=candidate.suffix, dir=root)
        try:
            while True:
                block = os.read(source_fd, 1024 * 1024)
                if not block:
                    break
                view = memoryview(block)
                while view:
                    written = os.write(destination_fd, view)
                    view = view[written:]
            os.fsync(destination_fd)
        finally:
            os.close(destination_fd)
        return Path(name)
    finally:
        os.close(source_fd)


def admitted_private_copy(
    path: Path,
    language: str,
    trusted_artifacts: Mapping[str, Any] | None,
    *,
    probe: Callable[..., NativeProbeResult] | None = None,
) -> tuple[NativeProbeResult, Path | None]:
    """Return an admitted private copy of ``path`` that is safe to load in-process.

    The candidate is copied from one open regular file into an exclusively
    created file in a new private ``chunker-admitted-*`` directory, keeping its
    suffix; the copy is verified against the same one-field record, admitted
    with the probe (or a verdict reused under its key), and returned only
    after ``ok``. Load that copy, never ``path``. Each process keeps at most
    one copy per admitted (language, digest) pair.

    Returns:
        ``(result, copy)``; ``copy`` is ``None`` unless ``result.supported``.
    """
    candidate = Path(path)
    if not os.path.lexists(candidate):
        return NativeProbeResult(False, "missing", None), None
    record, rejection = admission_record(candidate, language, trusted_artifacts)
    if record is None:
        assert rejection is not None
        return rejection, None
    pin = record["sha256"]
    if not _is_sha256(pin):
        return NativeProbeResult(False, "untrusted", None), None
    digest = pin.lower()
    content = hash_regular_file(candidate)
    if content is not None and not hmac.compare_digest(content, digest):
        return NativeProbeResult(False, "integrity_mismatch", None), None
    if not candidate.is_absolute():
        return NativeProbeResult(False, "untrusted", None), None
    pair = (language, digest)
    with _lock:
        pair_lock = _copy_locks.setdefault(pair, threading.Lock())
    # One check-create-register at a time per (language, digest), so a process
    # never makes two copies (or two probes) for the same pair.
    with pair_lock:
        with _lock:
            existing = _copies.get(pair)
        if existing is not None and content is not None:
            key = verdict_key(
                language=language,
                pin_sha256=digest,
                content_sha256=digest,
                level="probe",
                inspector="none",
            )
            if has_verdict(key) and hash_regular_file(existing) == digest:
                return NativeProbeResult(True, "ok", digest), existing
        return _create_private_copy(candidate, language, record, digest, probe)


def _create_private_copy(
    candidate: Path,
    language: str,
    record: dict[str, str],
    digest: str,
    probe: Callable[..., NativeProbeResult] | None,
) -> tuple[NativeProbeResult, Path | None]:
    root = Path(tempfile.mkdtemp(prefix="chunker-admitted-"))
    keep = False
    try:
        try:
            copy = _copy_candidate(candidate, root)
        except FileNotFoundError:
            return NativeProbeResult(False, "missing", None), None
        except ArtifactIntegrityError:
            return NativeProbeResult(False, "untrusted", None), None
        except OSError:
            return NativeProbeResult(False, "child_failed", None), None
        if copy.stat().st_size == 0:
            return NativeProbeResult(False, "empty", None), None
        try:
            verify_artifact(copy, record)
        except ArtifactIntegrityError:
            return NativeProbeResult(False, "integrity_mismatch", None), None
        result, _ = admit_native_candidate(
            copy, language, {language: record}, probe=probe
        )
        if not result.supported:
            return result, None
        keep = True
        with _lock:
            _copies[(language, digest)] = copy
        _register_copy_root(root)
        return result, copy
    finally:
        if not keep:
            shutil.rmtree(root, ignore_errors=True)


def forget_private_copy(language: str, digest: str) -> None:
    """Drop the in-process record of a copy whose load failed (rule 4).

    The file itself stays until interpreter exit (POSIX) because a failed load
    may still hold it open.
    """
    with _lock:
        _copies.pop((language, digest.lower()), None)
    drop_verdicts(language, digest)


def _reset_for_tests() -> None:
    """Clear process-local admission state (tests only)."""
    with _lock:
        _verdicts.clear()
        _verdict_index.clear()
        _copies.clear()
        _copy_locks.clear()
    _environment.cache_clear()

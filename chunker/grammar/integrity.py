"""Integrity checks and isolated admission for compiled grammar artifacts."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import math
import os
import re
import stat
import subprocess
import sys
import tempfile
import time
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class ArtifactIntegrityError(ValueError):
    """Raised when an artifact is not covered by trusted provenance."""


@dataclass(frozen=True)
class NativeProbeResult:
    """The admission outcome for one compiled native grammar."""

    supported: bool
    reason: str
    artifact_sha256: str | None


_SHA256 = re.compile(r"[0-9a-fA-F]{64}")
_ACK_SCHEMA = "native_probe.v1"
_DIAGNOSTIC_LIMIT = 64 * 1024
_ACK_LIMIT = 16 * 1024


def verify_artifact(path: Path, provenance: Mapping[str, Any]) -> None:
    """Verify ``path`` against its repo-owned SHA-256 provenance entry."""
    expected = provenance.get("sha256")
    if not isinstance(expected, str) or not _SHA256.fullmatch(expected):
        raise ArtifactIntegrityError("Artifact provenance requires a SHA-256 checksum")
    if not path.is_file():
        raise ArtifactIntegrityError(f"Artifact does not exist: {path}")

    digest = hashlib.sha256()
    with path.open("rb") as artifact:
        for block in iter(lambda: artifact.read(1024 * 1024), b""):
            digest.update(block)
    if not hmac.compare_digest(digest.hexdigest(), expected.lower()):
        raise ArtifactIntegrityError(
            "Artifact checksum does not match trusted provenance"
        )


def _native_probe_child(
    snapshot: str,
    language: str,
    expected_sha256: str,
    sample_b64: str,
    nonce: str,
) -> int:
    """Load and parse a verified snapshot in the isolated child process."""
    record: dict[str, Any] = {
        "schema": _ACK_SCHEMA,
        "nonce": nonce,
        "language": language,
        "sha256": expected_sha256,
    }
    snapshot_path = Path(snapshot)
    try:
        verify_artifact(snapshot_path, {"sha256": expected_sha256})
        from chunker.grammar_management.core import load_compiled_grammar

        parser = load_compiled_grammar(snapshot_path, language)
    except Exception:
        record["failure"] = "load_failed"
        print(json.dumps(record), flush=True)
        return 1

    try:
        root = parser.parse(base64.b64decode(sample_b64, validate=True)).root_node
        if root is None:
            raise ValueError("parser returned no root node")
    except Exception:
        record["failure"] = "parse_failed"
        print(json.dumps(record), flush=True)
        return 1

    record.update({"loader_returned": True, "parse_returned": True})
    print(json.dumps(record), flush=True)
    return 0


def _read_child(
    command: list[str], cwd: Path, timeout: float
) -> tuple[int | None, bytes, bytes, bool, bool]:
    """Run a child while bounding diagnostic and acknowledgment buffers."""
    process = subprocess.Popen(
        command,
        cwd=cwd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert process.stdout is not None
    assert process.stderr is not None
    pipes = {"stdout": process.stdout, "stderr": process.stderr}
    streams = {"stdout": bytearray(), "stderr": bytearray()}
    limits = {"stdout": _ACK_LIMIT, "stderr": _DIAGNOSTIC_LIMIT}
    timed_out = False
    overflow = False
    terminated = False
    deadline = time.monotonic() + timeout

    try:
        if sys.platform == "win32":
            import ctypes
            import msvcrt
            from ctypes import wintypes

            peek = ctypes.WinDLL("kernel32", use_last_error=True).PeekNamedPipe
            peek.argtypes = [
                wintypes.HANDLE,
                wintypes.LPVOID,
                wintypes.DWORD,
                wintypes.LPVOID,
                ctypes.POINTER(wintypes.DWORD),
                wintypes.LPVOID,
            ]
            peek.restype = wintypes.BOOL
        else:
            for pipe in pipes.values():
                os.set_blocking(pipe.fileno(), False)

        while True:
            remaining = deadline - time.monotonic()
            if process.poll() is not None and (overflow or remaining <= 0):
                break
            if remaining <= 0 and not terminated and process.poll() is None:
                timed_out = True
                process.terminate()
                terminated = True
                deadline = time.monotonic() + 1
            if terminated and time.monotonic() >= deadline and process.poll() is None:
                process.kill()
                process.wait()
            read_any = False
            for name, pipe in list(pipes.items()):
                if sys.platform == "win32":
                    available = wintypes.DWORD()
                    if not peek(
                        msvcrt.get_osfhandle(pipe.fileno()),
                        None,
                        0,
                        None,
                        ctypes.byref(available),
                        None,
                    ):
                        error = ctypes.get_last_error()
                        if error in {109, 233}:
                            del pipes[name]
                            continue
                        raise ctypes.WinError(error)
                    if not available.value:
                        continue
                    size = min(8192, available.value)
                else:
                    size = 8192
                try:
                    data = os.read(pipe.fileno(), size)
                except BlockingIOError:
                    continue
                if not data:
                    del pipes[name]
                    continue
                read_any = True
                if len(streams[name]) + len(data) > limits[name]:
                    overflow = True
                    if not terminated:
                        process.terminate()
                        terminated = True
                        deadline = time.monotonic() + 1
                    continue
                streams[name].extend(data)
            if process.poll() is not None and not pipes:
                break
            if not read_any:
                time.sleep(0.01)
        return (
            process.wait(),
            bytes(streams["stdout"]),
            bytes(streams["stderr"]),
            timed_out,
            overflow,
        )
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
        process.stdout.close()
        process.stderr.close()


def _failure(reason: str) -> NativeProbeResult:
    return NativeProbeResult(False, reason, None)


def probe_native_grammar(
    path: Path,
    language: str,
    *,
    provenance: Mapping[str, Any] | None,
    sample: bytes = b"",
    timeout: float = 10.0,
    inspect_artifact: Callable[[Path], Any] | None = None,
) -> NativeProbeResult:
    """Admit a pinned grammar by loading only a private verified snapshot.

    ``inspect_artifact`` is trusted application code. It runs only after the
    isolated child succeeds and must not mutate or load the supplied snapshot.
    """
    candidate = Path(path)
    if not candidate.is_absolute():
        return _failure("untrusted")
    if not isinstance(language, str) or not language:
        return _failure("load_failed")
    if not math.isfinite(timeout) or timeout <= 0:
        return _failure("timeout")

    source_fd: int | None
    try:
        source_fd = os.open(candidate, os.O_RDONLY | getattr(os, "O_NONBLOCK", 0))
    except FileNotFoundError:
        return _failure("missing")
    except OSError:
        return _failure("child_failed")

    try:
        source_stat = os.fstat(source_fd)
        if not stat.S_ISREG(source_stat.st_mode):
            return _failure("untrusted")
        if source_stat.st_size == 0:
            return _failure("empty")
        if not isinstance(provenance, Mapping):
            return _failure("untrusted")
        expected = provenance.get("sha256")
        if not isinstance(expected, str) or not _SHA256.fullmatch(expected):
            return _failure("untrusted")

        with tempfile.TemporaryDirectory(prefix="chunker-native-probe-") as directory:
            snapshot_dir = Path(directory)
            snapshot_fd, snapshot_name = tempfile.mkstemp(
                suffix=candidate.suffix,
                dir=snapshot_dir,
            )
            snapshot = Path(snapshot_name)
            try:
                with (
                    os.fdopen(os.dup(source_fd), "rb") as source,
                    os.fdopen(snapshot_fd, "wb") as destination,
                ):
                    remaining_bytes = source_stat.st_size
                    while remaining_bytes:
                        block = source.read(min(1024 * 1024, remaining_bytes))
                        if not block:
                            break
                        destination.write(block)
                        remaining_bytes -= len(block)
                    destination.flush()
                    os.fsync(destination.fileno())
                os.close(source_fd)
                source_fd = None
                try:
                    verify_artifact(snapshot, provenance)
                except ArtifactIntegrityError:
                    return _failure("integrity_mismatch")

                digest = expected.lower()
                nonce = uuid.uuid4().hex
                package_root = Path(__file__).resolve().parents[2]
                bootstrap = (
                    "import sys; sys.path.insert(0, sys.argv[1]); "
                    "from chunker.grammar.integrity import _native_probe_child; "
                    "raise SystemExit(_native_probe_child(*sys.argv[2:]))"
                )
                command = [
                    sys.executable,
                    "-I",
                    "-c",
                    bootstrap,
                    str(package_root),
                    str(snapshot),
                    language,
                    digest,
                    base64.b64encode(sample).decode("ascii"),
                    nonce,
                ]
                try:
                    returncode, stdout, _stderr, timed_out, overflow = _read_child(
                        command, snapshot_dir, timeout
                    )
                except OSError:
                    return _failure("child_failed")
                if timed_out:
                    return _failure("timeout")
                if overflow:
                    return _failure("ack_invalid")
                try:
                    pairs = json.loads(stdout.decode("utf-8"), object_pairs_hook=list)
                except (ValueError, RecursionError):
                    if returncode != 0:
                        return _failure("child_failed")
                    return _failure("ack_missing" if not stdout else "ack_invalid")
                if not isinstance(pairs, list) or not all(
                    isinstance(pair, tuple) and len(pair) == 2 for pair in pairs
                ):
                    return _failure("ack_invalid")
                acknowledgment = dict(pairs)
                if len(acknowledgment) != len(pairs):
                    return _failure("ack_invalid")
                common = {
                    "schema": _ACK_SCHEMA,
                    "nonce": nonce,
                    "language": language,
                    "sha256": digest,
                }
                if returncode != 0:
                    failure = acknowledgment.get("failure")
                    if (
                        all(
                            acknowledgment.get(key) == value
                            for key, value in common.items()
                        )
                        and isinstance(failure, str)
                        and failure
                        in {
                            "load_failed",
                            "parse_failed",
                        }
                    ):
                        return _failure(failure)
                    return _failure("child_failed")
                expected_acknowledgment = {
                    **common,
                    "loader_returned": True,
                    "parse_returned": True,
                }
                if (
                    acknowledgment != expected_acknowledgment
                    or acknowledgment.get("loader_returned") is not True
                    or acknowledgment.get("parse_returned") is not True
                ):
                    return _failure("ack_invalid")
                if not hmac.compare_digest(
                    hashlib.sha256(snapshot.read_bytes()).hexdigest(), digest
                ):
                    return _failure("integrity_mismatch")
                try:
                    if inspect_artifact is not None:
                        inspect_artifact(snapshot)
                except Exception:
                    return _failure("inspect_failed")
                return NativeProbeResult(True, "ok", digest)
            finally:
                snapshot.unlink(missing_ok=True)
    except OSError:
        return _failure("child_failed")
    finally:
        if source_fd is not None:
            os.close(source_fd)

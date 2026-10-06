"""Integrity checks and isolated admission for compiled grammar artifacts."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import selectors
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
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ, "stdout")
    selector.register(process.stderr, selectors.EVENT_READ, "stderr")
    streams = {"stdout": bytearray(), "stderr": bytearray()}
    limits = {"stdout": _ACK_LIMIT, "stderr": _DIAGNOSTIC_LIMIT}
    timed_out = False
    overflow = False
    terminated = False
    deadline = time.monotonic() + timeout

    try:
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0 and not terminated:
                timed_out = True
                process.terminate()
                terminated = True
                deadline = time.monotonic() + 1
                remaining = 1
            events = selector.select(max(0, min(remaining, 0.1)))
            for key, _ in events:
                data = os.read(key.fd, 8192)
                if not data:
                    selector.unregister(key.fileobj)
                    continue
                name = key.data
                if len(streams[name]) + len(data) > limits[name]:
                    overflow = True
                    if not terminated:
                        process.terminate()
                        terminated = True
                        deadline = time.monotonic() + 1
                    continue
                streams[name].extend(data)
            if terminated and time.monotonic() >= deadline and process.poll() is None:
                process.kill()
                deadline = time.monotonic() + 1
            if process.poll() is not None and not events:
                for key in list(selector.get_map().values()):
                    data = os.read(key.fd, 8192)
                    if data:
                        name = key.data
                        if len(streams[name]) + len(data) <= limits[name]:
                            streams[name].extend(data)
                        else:
                            overflow = True
                    else:
                        selector.unregister(key.fileobj)
        return (
            process.wait(),
            bytes(streams["stdout"]),
            bytes(streams["stderr"]),
            timed_out,
            overflow,
        )
    finally:
        selector.close()
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
    if timeout <= 0:
        return _failure("timeout")

    try:
        source_fd = os.open(candidate, os.O_RDONLY)
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
                    for block in iter(lambda: source.read(1024 * 1024), b""):
                        destination.write(block)
                    destination.flush()
                    os.fsync(destination.fileno())
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
                returncode, stdout, _stderr, timed_out, overflow = _read_child(
                    command, snapshot_dir, timeout
                )
                if timed_out:
                    return _failure("timeout")
                if overflow:
                    return _failure("ack_invalid")
                try:
                    acknowledgment = json.loads(stdout.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    return _failure("ack_missing" if not stdout else "ack_invalid")
                if not isinstance(acknowledgment, dict):
                    return _failure("ack_invalid")
                common = {
                    "schema": _ACK_SCHEMA,
                    "nonce": nonce,
                    "language": language,
                    "sha256": digest,
                }
                if returncode != 0:
                    failure = acknowledgment.get("failure")
                    if all(
                        acknowledgment.get(key) == value
                        for key, value in common.items()
                    ) and failure in {"load_failed", "parse_failed"}:
                        return _failure(failure)
                    return _failure("child_failed")
                expected_acknowledgment = {
                    **common,
                    "loader_returned": True,
                    "parse_returned": True,
                }
                if acknowledgment != expected_acknowledgment:
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
    finally:
        os.close(source_fd)

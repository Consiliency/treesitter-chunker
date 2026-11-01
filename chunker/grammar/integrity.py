"""Integrity checks for grammar download artifacts."""

from __future__ import annotations

import base64
import hashlib
import hmac
import re
import json
import logging
import math
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import psutil

from chunker.grammar._native_policy import (
    APPLICATION_CONTROL_MESSAGE,
    is_application_control_error,
)


class ArtifactIntegrityError(ValueError):
    """Raised when an artifact is not covered by trusted provenance."""


@dataclass(frozen=True)
class NativeProbeResult:
    """The admission outcome for one compiled native grammar."""

    supported: bool
    reason: str
    artifact_sha256: str | None

    @property
    def message(self) -> str | None:
        """Actionable guidance when the OS explicitly blocks native admission."""
        return APPLICATION_CONTROL_MESSAGE if self.reason == "policy_blocked" else None


_SHA256 = re.compile(r"[0-9a-fA-F]{64}")
_ACK_SCHEMA = "native_probe.v1"
_DIAGNOSTIC_LIMIT = 64 * 1024
_ACK_LIMIT = 16 * 1024


def _exception_metadata(error: BaseException) -> dict[str, Any]:
    frames = []
    trace = error.__traceback__
    for _ in range(64):
        if trace is None:
            break
        frames.append(
            {"function": trace.tb_frame.f_code.co_name[:64], "line": trace.tb_lineno}
        )
        frames = frames[-6:]
        trace = trace.tb_next
    return {
        "type": type(error).__name__[:64],
        "errno": value if type(value := getattr(error, "errno", None)) is int else None,
        "winerror": (
            value if type(value := getattr(error, "winerror", None)) is int else None
        ),
        "frames": frames,
    }


def _run_with_owned_cleanup(
    operation: Callable[[], Any], cleanup: Callable[[], Any]
) -> Any:
    """Run one operation and dispose its resource without replacing its error."""
    try:
        result = operation()
    except BaseException:
        try:
            cleanup()
        except BaseException:
            pass
        raise
    cleanup()
    return result


def _file_sha256(path: Path) -> str:
    """Hash one file while preserving a read failure over disposal failures."""
    digest = hashlib.sha256()
    artifact = path.open("rb")

    def read_artifact() -> None:
        for block in iter(lambda: artifact.read(1024 * 1024), b""):
            digest.update(block)

    _run_with_owned_cleanup(read_artifact, artifact.close)
    return digest.hexdigest()


def verify_artifact(path: Path, provenance: Mapping[str, Any]) -> None:
    """Verify ``path`` against its repo-owned SHA-256 provenance entry."""
    expected = provenance.get("sha256")
    if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", expected):
        raise ArtifactIntegrityError("Artifact provenance requires a SHA-256 checksum")
    if not path.is_file():
        raise ArtifactIntegrityError(f"Artifact does not exist: {path}")

    if not hmac.compare_digest(_file_sha256(path), expected.lower()):
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
    _worker_ready(Path(snapshot).parent, nonce)
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
    except Exception as error:
        record["failure"] = (
            "policy_blocked" if is_application_control_error(error) else "load_failed"
        )
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


_WORKER_SCHEMA = "native_probe.worker.v2"
_READY_NAME = ".native-probe-worker.json"
_READY_LIMIT = 4096


class _WindowsProcess:
    """One public Win32 process handle; candidate ownership is initially unarmed."""

    def __init__(self, pid: int | None):
        import ctypes
        from ctypes import wintypes

        self.ctypes: Any = ctypes
        self.api = self.ctypes.WinDLL("kernel32", use_last_error=True)
        signatures = {
            "OpenProcess": (
                [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD],
                wintypes.HANDLE,
            ),
            "GetCurrentProcess": ([], wintypes.HANDLE),
            "GetProcessTimes": (
                [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4,
                wintypes.BOOL,
            ),
            "WaitForSingleObject": ([wintypes.HANDLE, wintypes.DWORD], wintypes.DWORD),
            "GetExitCodeProcess": (
                [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)],
                wintypes.BOOL,
            ),
            "TerminateProcess": ([wintypes.HANDLE, wintypes.UINT], wintypes.BOOL),
            "CloseHandle": ([wintypes.HANDLE], wintypes.BOOL),
        }
        for name, (arguments, result) in signatures.items():
            function = getattr(self.api, name)
            function.argtypes = arguments
            function.restype = result
        self.owned_handle = pid is not None
        self.handle = (
            self.api.OpenProcess(0x100000 | 0x1000 | 0x0001, False, pid)
            if self.owned_handle
            else self.api.GetCurrentProcess()
        )
        if not self.handle:
            raise self.ctypes.WinError(self.ctypes.get_last_error())

    def creation(self) -> str:
        from ctypes import wintypes

        times = [wintypes.FILETIME() for _ in range(4)]
        if not self.api.GetProcessTimes(
            self.handle, *(self.ctypes.byref(t) for t in times)
        ):
            raise self.ctypes.WinError(self.ctypes.get_last_error())
        return f"{(times[0].dwHighDateTime << 32) | times[0].dwLowDateTime:016x}"

    def exited(self) -> bool:
        result = self.api.WaitForSingleObject(self.handle, 0)
        if result == 0:
            return True
        if result == 258:
            return False
        raise self.ctypes.WinError(self.ctypes.get_last_error())

    def status(self) -> int:
        from ctypes import wintypes

        if not self.exited():
            raise OSError("worker status requested before termination")
        code = wintypes.DWORD()
        if not self.api.GetExitCodeProcess(self.handle, self.ctypes.byref(code)):
            raise self.ctypes.WinError(self.ctypes.get_last_error())
        return code.value

    def terminate(self) -> None:
        if not self.exited() and not self.api.TerminateProcess(self.handle, 1):
            raise self.ctypes.WinError(self.ctypes.get_last_error())

    def close(self) -> None:
        handle, self.handle = self.handle, None
        if handle and self.owned_handle and not self.api.CloseHandle(handle):
            raise self.ctypes.WinError(self.ctypes.get_last_error())


@dataclass
class _ProbeLifecycle:
    native: bool = True
    launch_attempted: bool = False
    discovery_complete: bool = False
    cleanup_safe: bool = False
    aborted: bool = False
    forced: bool = False
    worker: psutil.Process | None = None
    worker_handle: _WindowsProcess | None = None
    worker_status: int | None = None
    launcher: subprocess.Popen[bytes] | None = None
    known: dict[int, psutil.Process] = field(default_factory=dict)
    error: str = ""
    trigger: str = ""
    operation: str = "launch"
    exception: dict[str, Any] | None = None
    ready_open_denials: int = 0
    first_ready_open_denial: dict[str, Any] | None = None
    start_attempted: bool = False
    start_completed: bool = False
    launcher_created_at: float | None = None
    worker_created_at: float | None = None

    def record_exception(self, error: BaseException, operation: str) -> None:
        if self.exception is None:
            try:
                self.exception = {
                    "operation": operation,
                    "type": None,
                    "errno": None,
                    "winerror": None,
                    "frames": [],
                }
                self.exception.update(_exception_metadata(error))
            except BaseException:
                # Observing a propagating failure must not replace it.
                pass

    def fail(self, cause: str, *, uncertain: bool = True) -> None:
        self.error = self.error or cause[:256]
        self.aborted = True
        self.cleanup_safe = False
        if uncertain:
            self.discovery_complete = False


def _worker_ready(directory: Path, nonce: str) -> None:
    creation = None
    if sys.platform == "win32":
        candidate = _WindowsProcess(None)
        try:
            creation = candidate.creation()
        finally:
            candidate.close()
    record = {
        "schema": _WORKER_SCHEMA,
        "nonce": nonce,
        "pid": os.getpid(),
        "ppid": os.getppid(),
        "windows_creation_filetime": creation,
    }
    temporary = directory / (_READY_NAME + ".tmp")
    with temporary.open("x", encoding="utf-8") as output:
        json.dump(record, output)
    temporary.replace(directory / _READY_NAME)
    if sys.stdin.buffer.read(1) != b"\x01":
        raise SystemExit(1)


def _read_ready(
    directory: Path, nonce: str, *, lifecycle: _ProbeLifecycle | None = None
) -> dict[str, Any] | None:
    try:
        stream = (directory / _READY_NAME).open("rb")
    except FileNotFoundError:
        return None
    except PermissionError as error:
        if sys.platform != "win32":
            raise
        if lifecycle is not None:  # type: ignore[unreachable]
            lifecycle.ready_open_denials += 1
            if lifecycle.first_ready_open_denial is None:
                try:
                    lifecycle.first_ready_open_denial = _exception_metadata(error)
                except Exception:
                    pass
        return None
    try:
        data = stream.read(_READY_LIMIT + 1)
    except BaseException:
        try:
            stream.close()
        except BaseException:
            # The read failure is already propagating; disposal cannot replace it.
            pass
        raise
    else:
        stream.close()
    if len(data) > _READY_LIMIT:
        raise ValueError("oversized worker registration")
    pairs = json.loads(data, object_pairs_hook=list)
    if not isinstance(pairs, list) or not all(
        isinstance(p, tuple) and len(p) == 2 for p in pairs
    ):
        raise ValueError("invalid worker registration")
    record = dict(pairs)
    keys = {"schema", "nonce", "pid", "ppid", "windows_creation_filetime"}
    if len(pairs) != len(record) or set(record) != keys:
        raise ValueError("invalid worker registration keys")
    if record["schema"] != _WORKER_SCHEMA or record["nonce"] != nonce:
        raise ValueError("worker registration request mismatch")
    if any(type(record[k]) is not int or record[k] <= 0 for k in ("pid", "ppid")):
        raise ValueError("invalid worker registration PID")
    creation = record["windows_creation_filetime"]
    if sys.platform == "win32":
        if not isinstance(creation, str) or not re.fullmatch(r"[0-9a-f]{16}", creation):
            raise ValueError("invalid worker creation FILETIME")
    elif creation is not None:
        raise ValueError("unexpected worker creation FILETIME")
    return record


def _alive(process: psutil.Process) -> bool:
    try:
        return bool(process.is_running() and process.status() != psutil.STATUS_ZOMBIE)
    except psutil.NoSuchProcess:
        return False


def _discover(lifecycle: _ProbeLifecycle) -> None:
    launcher_identity = (
        lifecycle.known.get(lifecycle.launcher.pid) if lifecycle.launcher else None
    )
    roots = [launcher_identity] if launcher_identity is not None else []
    if lifecycle.worker is not None and lifecycle.worker not in roots:
        roots.append(lifecycle.worker)
    for root in roots:
        if (
            lifecycle.launcher is not None
            and root.pid == lifecycle.launcher.pid
            and lifecycle.launcher.poll() is not None
        ):
            continue
        if (
            lifecycle.worker_handle is not None
            and lifecycle.worker is not None
            and root.pid == lifecycle.worker.pid
            and lifecycle.worker_handle.exited()
        ):
            continue
        if not _alive(root):
            continue
        try:
            children = root.children(recursive=True)
        except psutil.NoSuchProcess:
            continue
        for child in children:
            child.create_time()  # Capture incarnation before retaining a signal target.
            lifecycle.known.setdefault(child.pid, child)
    if lifecycle.native and lifecycle.discovery_complete:
        assert lifecycle.launcher is not None and lifecycle.worker is not None
        allowed = {lifecycle.launcher.pid, lifecycle.worker.pid}
        if set(lifecycle.known) - allowed:
            lifecycle.fail("unexpected descendant")


def _register_worker(lifecycle: _ProbeLifecycle, record: dict[str, Any]) -> None:
    launcher = lifecycle.launcher
    if lifecycle.aborted or launcher is None or launcher.poll() is not None:
        raise ValueError("launcher lost before registration")
    launcher_identity = lifecycle.known[launcher.pid]
    if not _alive(launcher_identity):
        raise ValueError("launcher identity lost")
    worker = psutil.Process(record["pid"])
    worker_created_at = worker.create_time()
    if not _alive(worker) or worker.ppid() != record["ppid"]:
        raise ValueError("worker ancestry mismatch")
    if worker.pid == launcher.pid:
        if worker.create_time() != launcher_identity.create_time():
            raise ValueError("worker incarnation mismatch")
    elif sys.platform != "win32" or worker.ppid() != launcher.pid:
        raise ValueError("unsupported indirect worker")
    allowed = {launcher.pid, worker.pid}
    if set(lifecycle.known) - allowed:
        raise ValueError("unsupported worker topology")
    candidate: _WindowsProcess | None = None
    windows = sys.platform == "win32"
    try:
        if windows:
            candidate = _WindowsProcess(worker.pid)
            if (
                candidate.creation() != record["windows_creation_filetime"]
                or candidate.exited()
            ):
                raise ValueError("worker handle identity mismatch")
        if launcher.poll() is not None or not _alive(worker) or lifecycle.aborted:
            raise ValueError("worker lost before start")
        lifecycle.worker = worker
        lifecycle.known[worker.pid] = worker
        lifecycle.worker_handle, candidate = candidate, None
        lifecycle.discovery_complete = True
        lifecycle.worker_created_at = worker_created_at
    finally:
        if candidate is not None:
            pending_error = sys.exception()
            try:
                candidate.close()  # Never signal an unarmed candidate handle.
            except BaseException:
                # Preserve the first cancellation/validation error if one is propagating.
                if pending_error is None:
                    raise


def _worker_exited(lifecycle: _ProbeLifecycle) -> bool:
    if lifecycle.worker is None:
        return False
    if lifecycle.worker_handle is not None:
        if not lifecycle.worker_handle.exited():
            return False
        try:
            lifecycle.worker_status = lifecycle.worker_handle.status()
        except OSError as error:
            lifecycle.fail(str(error), uncertain=False)
        return True
    if (
        lifecycle.launcher is not None
        and lifecycle.worker.pid == lifecycle.launcher.pid
    ):
        lifecycle.worker_status = lifecycle.launcher.poll()
        return lifecycle.worker_status is not None
    return False


def _stop_child(lifecycle: _ProbeLifecycle) -> None:
    """One shared grace and confirmation window, including exceptional exits."""
    process = lifecycle.launcher
    lifecycle.cleanup_safe = False
    if process is None:
        return
    if process.stdin is not None and not process.stdin.closed:
        try:
            process.stdin.close()
        except OSError as error:
            lifecycle.fail(str(error))
    try:
        _discover(lifecycle)
    except (OSError, psutil.Error) as error:
        lifecycle.fail(str(error))
    targets = [p for pid, p in lifecycle.known.items() if pid != process.pid]

    def signal_targets(hard: bool) -> None:
        handle = lifecycle.worker_handle
        if handle is not None:
            try:
                if not handle.exited():
                    lifecycle.forced = True
                    handle.terminate()
            except OSError as error:
                lifecycle.fail(str(error))
        for target in targets:
            if (
                handle is not None
                and lifecycle.worker is not None
                and target.pid == lifecycle.worker.pid
            ):
                continue
            try:
                if _alive(target):
                    lifecycle.forced = True
                    (target.kill if hard else target.terminate)()
            except psutil.NoSuchProcess:
                pass
            except psutil.Error as error:
                lifecycle.fail(str(error))
        if process.poll() is None:
            lifecycle.forced = True
            (process.kill if hard else process.terminate)()

    def gone() -> bool:
        launcher_gone = process.poll() is not None
        try:
            worker_gone = _worker_exited(lifecycle) if lifecycle.worker else True
        except (OSError, psutil.Error) as error:
            lifecycle.fail(str(error))
            worker_gone = False
        other_gone = True
        for target in targets:
            if lifecycle.worker is not None and target.pid == lifecycle.worker.pid:
                continue
            try:
                if _alive(target):
                    other_gone = False
            except psutil.Error as error:
                lifecycle.fail(str(error))
                other_gone = False
        return launcher_gone and worker_gone and other_gone

    if not gone():
        signal_targets(False)
        grace = time.monotonic() + 1.0
        while not gone() and time.monotonic() < grace:
            time.sleep(min(0.01, max(0, grace - time.monotonic())))
        if not gone():
            signal_targets(True)
        confirmation = time.monotonic() + 5.0
        while not gone() and time.monotonic() < confirmation:
            time.sleep(min(0.01, max(0, confirmation - time.monotonic())))
    lifecycle.cleanup_safe = lifecycle.discovery_complete and gone()


def _read_child(
    command: list[str],
    cwd: Path,
    timeout: float,
    *,
    worker_nonce: str | None = None,
    lifecycle: _ProbeLifecycle | None = None,
) -> tuple[int | None, bytes, bytes, bool, bool]:
    """Bound pipes and deadline; actual-worker status lives in caller-owned state."""
    if worker_nonce is not None and lifecycle is None:
        raise ValueError("native worker requires caller-owned lifecycle")
    state = (
        lifecycle
        if lifecycle is not None
        else _ProbeLifecycle(native=worker_nonce is not None)
    )
    streams = {"stdout": bytearray(), "stderr": bytearray()}
    limits = {"stdout": _ACK_LIMIT, "stderr": _DIAGNOSTIC_LIMIT}
    timed_out = overflow = False
    deadline = time.monotonic() + timeout
    state.launch_attempted = True
    primary_error = None
    try:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            stdin=subprocess.PIPE if worker_nonce else subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        state.launcher = process
        identity = psutil.Process(process.pid)
        state.launcher_created_at = identity.create_time()
        state.known[process.pid] = identity
        if worker_nonce is None:
            state.worker = identity
            state.discovery_complete = True
        assert process.stdout is not None and process.stderr is not None
        pipes = {"stdout": process.stdout, "stderr": process.stderr}
        state.operation = "pipe_setup"
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
            if time.monotonic() >= deadline:
                timed_out = True
                state.trigger = "timeout"
                state.aborted = True
                break
            state.operation = "discover"
            _discover(state)
            if state.aborted:
                break
            if worker_nonce is not None and state.worker is None:
                state.operation = "launcher_poll_before_ready"
                if process.poll() is not None:
                    state.fail("launcher lost before ready")
                    break
                state.operation = "ready_read"
                record = _read_ready(cwd, worker_nonce, lifecycle=state)
                if record is not None:
                    state.operation = "register_worker"
                    _register_worker(state, record)
                    if state.aborted or time.monotonic() >= deadline:
                        state.aborted = True
                        state.trigger = "timeout"
                        timed_out = True
                        break
                    assert process.stdin is not None
                    state.operation = "start_write"
                    state.start_attempted = True
                    process.stdin.write(b"\x01")
                    state.operation = "start_flush"
                    process.stdin.flush()
                    state.start_completed = True
                    state.operation = "start_close"
                    process.stdin.close()
            read_any = False
            for name, pipe in list(pipes.items()):
                if sys.platform == "win32":
                    state.operation = name + "_peek"
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
                    state.operation = name + "_read"
                    data = os.read(pipe.fileno(), size)
                except BlockingIOError:
                    continue
                if not data:
                    del pipes[name]
                    continue
                read_any = True
                if len(streams[name]) + len(data) > limits[name]:
                    overflow = True
                    state.trigger = "overflow"
                    state.aborted = True
                    break
                streams[name].extend(data)
            if state.aborted:
                break
            state.operation = "worker_status"
            worker_done = _worker_exited(state)
            state.operation = "launcher_poll"
            if process.poll() is not None and worker_done and not pipes:
                break
            if not read_any:
                time.sleep(min(0.01, max(0, deadline - time.monotonic())))
    except BaseException as error:
        primary_error = error
        state.record_exception(error, state.operation)
        state.fail(type(error).__name__)
        state.trigger = state.trigger or type(error).__name__
        raise
    finally:
        try:
            _stop_child(state)
        except BaseException as error:
            state.record_exception(error, "stop_child")
            state.fail("cleanup: " + type(error).__name__)
            # Preserve the first cancellation/read error if one is already propagating.
            if primary_error is None:
                primary_error = error
                raise
        finally:
            resources: list[Any] = []
            if state.launcher is not None:
                resources.extend(
                    (state.launcher.stdin, state.launcher.stdout, state.launcher.stderr)
                )
            if state.worker_handle is not None:
                resources.append(state.worker_handle)
            close_error = None
            for resource in resources:
                try:
                    if resource is not None:
                        resource.close()
                except BaseException as error:
                    state.record_exception(error, "resource_close")
                    state.fail("close: " + type(error).__name__)
                    close_error = close_error or error
            if close_error is not None and primary_error is None:
                raise close_error
    return (
        state.launcher.returncode if state.launcher else None,
        bytes(streams["stdout"]),
        bytes(streams["stderr"]),
        timed_out,
        overflow,
    )


def _log_probe_failure(
    reason: str | None,
    *,
    phase: str,
    lifecycle: _ProbeLifecycle | None,
    error: BaseException | None = None,
) -> None:
    try:
        logger = logging.getLogger(__name__)
        if not logger.isEnabledFor(logging.DEBUG):
            return
        diagnostic: dict[str, Any] = {
            "schema": "native_probe.diagnostic.v1",
            "reason": reason,
            "phase": phase,
            "exception": _exception_metadata(error) if error is not None else None,
        }
        if lifecycle is not None:
            diagnostic.update(
                operation=lifecycle.operation,
                exception=lifecycle.exception or diagnostic["exception"],
                ready_open_denials=lifecycle.ready_open_denials,
                first_ready_open_denial=lifecycle.first_ready_open_denial,
                start_attempted=lifecycle.start_attempted,
                start_completed=lifecycle.start_completed,
                launch_attempted=lifecycle.launch_attempted,
                discovery_complete=lifecycle.discovery_complete,
                cleanup_safe=lifecycle.cleanup_safe,
                forced=lifecycle.forced,
                trigger=lifecycle.trigger,
                launcher_pid=lifecycle.launcher.pid if lifecycle.launcher else None,
                launcher_status=(
                    lifecycle.launcher.returncode if lifecycle.launcher else None
                ),
                launcher_created_at=lifecycle.launcher_created_at,
                worker_pid=lifecycle.worker.pid if lifecycle.worker else None,
                worker_status=lifecycle.worker_status,
                worker_created_at=lifecycle.worker_created_at,
            )
        logger.debug(
            "Native probe failure: %s",
            json.dumps(diagnostic, sort_keys=True),
            extra={"native_probe_diagnostic": diagnostic},
        )
    except BaseException as diagnostic_error:
        if error is None and not isinstance(diagnostic_error, Exception):
            raise


def _failure(
    reason: str,
    *,
    phase: str = "validate",
    lifecycle: _ProbeLifecycle | None = None,
    error: BaseException | None = None,
) -> NativeProbeResult:
    _log_probe_failure(reason, phase=phase, lifecycle=lifecycle, error=error)
    return NativeProbeResult(False, reason, None)


def probe_native_grammar(
    path: Path,
    language: str,
    *,
    provenance: Mapping[str, Any] | None,
    sample: bytes = b"",
    timeout: float = 30.0,
    inspect_artifact: Callable[[Path], Any] | None = None,
) -> NativeProbeResult:
    """Admit a pinned grammar by loading only a private verified snapshot.

    ``timeout`` is one shared deadline, in seconds, for starting the isolated
    worker, loading and parsing, and its exit. An explicit value is used
    exactly. The 30-second default outlasts a Windows Smart App Control cloud
    check: the first load of a new unsigned library can wait about ten seconds
    for that check before Windows allows it (treesitter-chunker#547).

    ``inspect_artifact`` is trusted application code. It runs only after the
    isolated child succeeds and must not mutate or load the supplied snapshot.
    """
    phase = "validate"
    lifecycle: _ProbeLifecycle | None = None

    def reject(reason: str, error: BaseException | None = None) -> NativeProbeResult:
        return _failure(reason, phase=phase, lifecycle=lifecycle, error=error)

    candidate = Path(path)
    if not candidate.is_absolute():
        return reject("untrusted")
    if not isinstance(language, str) or not language:
        return reject("load_failed")
    if not math.isfinite(timeout) or timeout <= 0:
        return reject("timeout")

    phase = "source_open"
    source_fd: int | None
    try:
        source_fd = os.open(candidate, os.O_RDONLY | getattr(os, "O_NONBLOCK", 0))
    except FileNotFoundError:
        return reject("missing")
    except OSError as error:
        return reject(
            "policy_blocked" if is_application_control_error(error) else "child_failed",
            error,
        )

    try:
        phase = "source_validation"
        source_stat = os.fstat(source_fd)
        if not stat.S_ISREG(source_stat.st_mode):
            return reject("untrusted")
        if source_stat.st_size == 0:
            return reject("empty")
        if not isinstance(provenance, Mapping):
            return reject("untrusted")
        expected = provenance.get("sha256")
        if not isinstance(expected, str) or not _SHA256.fullmatch(expected):
            return reject("untrusted")

        phase = "snapshot_copy"
        snapshot_dir = Path(tempfile.mkdtemp(prefix="chunker-native-probe-"))
        lifecycle = _ProbeLifecycle()
        snapshot_operation_failed = False
        try:
            opened_snapshot_fd, snapshot_name = tempfile.mkstemp(
                suffix=candidate.suffix,
                dir=snapshot_dir,
            )
            snapshot_fd: int | None = opened_snapshot_fd
            snapshot = Path(snapshot_name)

            duplicate_fd: int | None = None

            def close_snapshot_fd() -> None:
                nonlocal snapshot_fd
                if snapshot_fd is not None:
                    descriptor, snapshot_fd = snapshot_fd, None
                    os.close(descriptor)

            def close_duplicate_fd() -> None:
                nonlocal duplicate_fd
                if duplicate_fd is not None:
                    descriptor, duplicate_fd = duplicate_fd, None
                    os.close(descriptor)

            def copy_source() -> None:
                nonlocal duplicate_fd, snapshot_fd
                assert source_fd is not None
                duplicate_fd = os.dup(source_fd)
                source = os.fdopen(duplicate_fd, "rb")
                duplicate_fd = None

                def copy_destination() -> None:
                    nonlocal snapshot_fd
                    assert snapshot_fd is not None
                    destination = os.fdopen(snapshot_fd, "wb")
                    snapshot_fd = None

                    def copy_snapshot() -> None:
                        remaining_bytes = source_stat.st_size
                        while remaining_bytes:
                            block = source.read(min(1024 * 1024, remaining_bytes))
                            if not block:
                                break
                            destination.write(block)
                            remaining_bytes -= len(block)
                        destination.flush()
                        os.fsync(destination.fileno())

                    _run_with_owned_cleanup(copy_snapshot, destination.close)

                _run_with_owned_cleanup(copy_destination, source.close)

            _run_with_owned_cleanup(
                lambda: _run_with_owned_cleanup(copy_source, close_snapshot_fd),
                close_duplicate_fd,
            )
            assert source_fd is not None
            descriptor, source_fd = source_fd, None
            os.close(descriptor)
            phase = "snapshot_verify"
            try:
                verify_artifact(snapshot, provenance)
            except ArtifactIntegrityError as error:
                return reject("integrity_mismatch", error)

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
            phase = "native_worker"
            try:
                returncode, stdout, _stderr, timed_out, overflow = _read_child(
                    command,
                    snapshot_dir,
                    timeout,
                    worker_nonce=nonce,
                    lifecycle=lifecycle,
                )
            except (OSError, ValueError, RecursionError, psutil.Error) as error:
                return reject(
                    (
                        "policy_blocked"
                        if is_application_control_error(error)
                        else "child_failed"
                    ),
                    error,
                )
            phase = "acknowledgment"
            if (
                not lifecycle.cleanup_safe
                or lifecycle.error
                or lifecycle.worker_status is None
            ):
                return reject("child_failed")
            if timed_out:
                return reject("timeout")
            if overflow:
                return reject("ack_invalid")
            if lifecycle.forced:
                return reject("child_failed")
            try:
                pairs = json.loads(stdout.decode("utf-8"), object_pairs_hook=list)
            except (ValueError, RecursionError):
                if returncode != 0 or lifecycle.worker_status != 0:
                    return reject("child_failed")
                return reject("ack_missing" if not stdout else "ack_invalid")
            if not isinstance(pairs, list) or not all(
                isinstance(pair, tuple) and len(pair) == 2 for pair in pairs
            ):
                return reject("ack_invalid")
            acknowledgment = dict(pairs)
            if len(acknowledgment) != len(pairs):
                return reject("ack_invalid")
            common = {
                "schema": _ACK_SCHEMA,
                "nonce": nonce,
                "language": language,
                "sha256": digest,
            }
            if returncode != 0 or lifecycle.worker_status != 0:
                failure = acknowledgment.get("failure")
                if (
                    returncode == lifecycle.worker_status == 1
                    and all(
                        acknowledgment.get(key) == value
                        for key, value in common.items()
                    )
                    and isinstance(failure, str)
                    and failure
                    in {
                        "load_failed",
                        "parse_failed",
                        "policy_blocked",
                    }
                ):
                    return reject(failure)
                return reject("child_failed")
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
                return reject("ack_invalid")
            phase = "snapshot_final_hash"
            if not hmac.compare_digest(_file_sha256(snapshot), digest):
                return reject("integrity_mismatch")
            phase = "inspection"
            try:
                if inspect_artifact is not None:
                    inspect_artifact(snapshot)
            except Exception as error:
                return reject("inspect_failed", error)
            return NativeProbeResult(True, "ok", digest)
        except BaseException:
            snapshot_operation_failed = True
            raise
        finally:
            if not lifecycle.launch_attempted or lifecycle.cleanup_safe:
                try:
                    shutil.rmtree(snapshot_dir)
                except BaseException:
                    if not snapshot_operation_failed:
                        raise
            else:
                diagnostic = (
                    f"Native probe retained unsafe root {snapshot_dir}; "
                    f"trigger={lifecycle.trigger}; error={lifecycle.error}; "
                    f"known_count={len(lifecycle.known)}; identities="
                    f"{[(pid, lifecycle.known[pid].create_time()) for pid in list(lifecycle.known)[:32]]}"
                )
                try:
                    logging.getLogger(__name__).error(diagnostic)
                except BaseException as diagnostic_error:
                    try:
                        print(diagnostic, file=sys.stderr, flush=True)
                    except BaseException:
                        if not snapshot_operation_failed:
                            raise
                    if not snapshot_operation_failed and not isinstance(
                        diagnostic_error, Exception
                    ):
                        raise

    except BaseException as error:
        if source_fd is not None:
            descriptor, source_fd = source_fd, None
            try:
                os.close(descriptor)
            except BaseException:
                pass
        if isinstance(error, OSError):
            return reject(
                (
                    "policy_blocked"
                    if is_application_control_error(error)
                    else "child_failed"
                ),
                error,
            )
        _log_probe_failure(None, phase=phase, lifecycle=lifecycle, error=error)
        raise
    finally:
        if source_fd is not None:
            descriptor, source_fd = source_fd, None
            os.close(descriptor)

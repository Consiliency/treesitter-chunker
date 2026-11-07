"""Regression tests for grammar artifact provenance."""

import hashlib
import sys
import io
import json
import tarfile
import tempfile
from pathlib import Path
from urllib.error import URLError

import pytest

pytestmark = pytest.mark.usefixtures(
    "native_probe_lifetimes", "native_policy_environment"
)

from tests.native_probe_lifetime import remove_retained_probe_root

from chunker.grammar.download import GrammarDownloadManager
from chunker.grammar.integrity import (
    ArtifactIntegrityError,
    _read_child,
    probe_native_grammar,
    verify_artifact,
)


def test_verify_artifact_rejects_checksum_mismatch(tmp_path):
    artifact = tmp_path / "grammar.tar.gz"
    artifact.write_bytes(b"untrusted")

    with pytest.raises(ArtifactIntegrityError, match="checksum"):
        verify_artifact(artifact, {"sha256": "0" * 64})


class _SnapshotFaultStream:
    """Real stream proxy supporting old context and repaired explicit disposal."""

    def __init__(
        self,
        stream,
        events,
        role,
        *,
        operation=None,
        operation_error=None,
        close_error=None,
    ):
        self.stream = stream
        self.events = events
        self.role = role
        self.operation = operation
        self.operation_error = operation_error
        self.close_error = close_error

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()
        return False

    def read(self, size=-1):
        self.events.append(f"{self.role}.read")
        if self.operation == "read":
            raise self.operation_error
        return self.stream.read(size)

    def write(self, data):
        self.events.append(f"{self.role}.write")
        if self.operation == "write":
            raise self.operation_error
        return self.stream.write(data)

    def flush(self):
        self.events.append(f"{self.role}.flush")
        if self.operation == "flush":
            raise self.operation_error
        return self.stream.flush()

    def fileno(self):
        return self.stream.fileno()

    def close(self):
        self.events.append(f"{self.role}.close")
        self.stream.close()
        if self.close_error is not None:
            raise self.close_error


_SNAPSHOT_CLOSE_FAILURES = pytest.mark.parametrize(
    "close_error",
    [OSError("snapshot close failure"), KeyboardInterrupt("second cancellation")],
    ids=["close_oserror", "close_interrupt"],
)


@_SNAPSHOT_CLOSE_FAILURES
def test_verify_reader_preserves_read_cancellation_during_disposal(
    tmp_path, monkeypatch, close_error
):
    import traceback

    artifact = tmp_path / "artifact.bin"
    artifact.write_bytes(b"reviewed bytes")
    original = KeyboardInterrupt("original verification read cancellation")
    events = []
    real_open = Path.open

    def controlled_open(path, mode="r", *args, **kwargs):
        stream = real_open(path, mode, *args, **kwargs)
        if path == artifact and mode == "rb":
            return _SnapshotFaultStream(
                stream,
                events,
                "verify",
                operation="read",
                operation_error=original,
                close_error=close_error,
            )
        return stream

    monkeypatch.setattr(Path, "open", controlled_open)
    try:
        verify_artifact(
            artifact, {"sha256": hashlib.sha256(b"reviewed bytes").hexdigest()}
        )
    except BaseException as error:  # noqa: BLE001 - exact identity is the contract
        caught = error
    else:
        pytest.fail("verification cancellation unexpectedly returned")
    assert caught is original
    assert traceback.extract_tb(caught.__traceback__)[-1].name == "read"
    assert events == ["verify.read", "verify.close"]


def test_verify_reader_successful_body_propagates_close_failure(tmp_path, monkeypatch):
    artifact = tmp_path / "artifact.bin"
    payload = b"reviewed bytes"
    artifact.write_bytes(payload)
    close_error = OSError("verification close failure")
    events = []
    real_open = Path.open

    def controlled_open(path, mode="r", *args, **kwargs):
        stream = real_open(path, mode, *args, **kwargs)
        if path == artifact and mode == "rb":
            return _SnapshotFaultStream(
                stream, events, "verify", close_error=close_error
            )
        return stream

    monkeypatch.setattr(Path, "open", controlled_open)
    with pytest.raises(OSError) as raised:
        try:
            raise LookupError("handled caller exception")
        except LookupError:
            verify_artifact(artifact, {"sha256": hashlib.sha256(payload).hexdigest()})
    assert raised.value is close_error
    assert events == ["verify.read", "verify.read", "verify.close"]


def test_download_refuses_bare_master_default(tmp_path):
    with pytest.raises(ValueError, match="immutable commit"):
        GrammarDownloadManager(cache_dir=tmp_path).download_grammar("python")


def test_download_verifies_manifest_before_extract(tmp_path, monkeypatch):
    manager = GrammarDownloadManager(cache_dir=tmp_path)
    payload = b"trusted archive"
    checksum = hashlib.sha256(payload).hexdigest()
    monkeypatch.setattr(
        manager,
        "ARTIFACT_MANIFEST",
        {"python@0123456789abcdef": {"sha256": checksum}},
    )
    monkeypatch.setattr(
        manager,
        "_download_file",
        lambda _url, destination, _language, _progress: Path(destination).write_bytes(
            payload,
        ),
    )
    monkeypatch.setattr(
        manager,
        "_extract_archive",
        lambda _archive, destination: destination.mkdir(exist_ok=True),
    )

    assert manager.download_grammar("python", "0123456789abcdef").exists()


@pytest.mark.parametrize("outcome", ["success", "checksum", "transport", "extraction"])
def test_download_archive_handle_lifetime(tmp_path, monkeypatch, outcome):
    fixture = Path(__file__).parents[1] / "packages" / "baml-grammar"
    sources = {"src/parser.c": (fixture / "src/parser.c").read_bytes()}
    archive = io.BytesIO()
    with tarfile.open(fileobj=archive, mode="w:gz") as output:
        for name, payload in sources.items():
            member = tarfile.TarInfo(f"fixture/{name}")
            member.size = len(payload)
            output.addfile(member, io.BytesIO(payload))
    payload = b"invalid gzip archive" if outcome == "extraction" else archive.getvalue()
    checksum = (
        "0" * 64 if outcome == "checksum" else hashlib.sha256(payload).hexdigest()
    )
    manager = GrammarDownloadManager(cache_dir=tmp_path / "cache")
    version = "0123456789abcdef"
    monkeypatch.setattr(
        manager, "ARTIFACT_MANIFEST", {f"python@{version}": {"sha256": checksum}}
    )
    created = []
    real_temporary_file = tempfile.NamedTemporaryFile

    def record_temporary_file(*args, **kwargs):
        handle = real_temporary_file(*args, **kwargs)
        created.append(handle)
        return handle

    class Response(io.BytesIO):
        headers = {"Content-Length": str(len(payload))}

    def local_response(request):
        assert request.full_url.endswith(f"/{version}.tar.gz")
        assert len(created) == 1
        assert created[0].closed, "Download creation handle must close before transport"
        if outcome == "transport":
            raise URLError("offline transport failure")
        return Response(payload)

    monkeypatch.setattr(
        "chunker.grammar.download.tempfile.NamedTemporaryFile", record_temporary_file
    )
    monkeypatch.setattr("chunker.grammar.download.urlopen", local_response)
    errors = {
        "checksum": (ArtifactIntegrityError, "checksum"),
        "transport": (RuntimeError, "offline transport failure"),
        "extraction": (tarfile.ReadError, "not a gzip file"),
    }
    if outcome == "success":
        destination = manager.download_grammar("python", version)
        assert (destination / "src/parser.c").read_bytes() == sources["src/parser.c"]
        metadata = json.loads(
            (tmp_path / "cache/metadata.json").read_text(encoding="utf-8")
        )
        assert metadata["grammars"]["python"]["path"] == str(destination)
        assert metadata["grammars"]["python"]["version"] == version
    else:
        error, message = errors[outcome]
        with pytest.raises(error, match=message):
            manager.download_grammar("python", version)
        assert manager._metadata["grammars"] == {}
        assert not (tmp_path / "cache/metadata.json").exists()
        if outcome in {"checksum", "transport"}:
            assert not (tmp_path / "cache" / f"python-{version}").exists()
    assert len(created) == 1
    assert created[0].closed
    assert not Path(created[0].name).exists()


def test_child_timeout_still_applies_after_pipes_close(tmp_path):
    code = "import os,time; os.close(1); os.close(2); time.sleep(60)"
    returncode, stdout, stderr, timed_out, overflow = _read_child(
        [sys.executable, "-I", "-c", code], tmp_path, 1
    )
    assert returncode != 0
    assert timed_out and not overflow
    assert stdout == stderr == b""


@pytest.mark.parametrize(("descriptor", "limit"), [(1, 16384), (2, 65536)])
def test_child_diagnostic_overflow_is_bounded(tmp_path, descriptor, limit):
    code = f"import os,time; os.write({descriptor}, b'x' * 131072); time.sleep(60)"
    returncode, stdout, stderr, timed_out, overflow = _read_child(
        [sys.executable, "-I", "-c", code], tmp_path, 5
    )
    assert returncode != 0
    assert overflow and not timed_out
    assert len(stdout if descriptor == 1 else stderr) <= limit


def test_child_closed_pipes_do_not_hide_normal_completion(tmp_path):
    result = _read_child(
        [sys.executable, "-I", "-c", "import os; os.close(1); os.close(2)"],
        tmp_path,
        5,
    )
    assert result == (0, b"", b"", False, False)


def test_child_drains_all_output_after_exit(tmp_path):
    result = _read_child(
        [sys.executable, "-I", "-c", "import os; os.write(1, b'x' * 12000)"],
        tmp_path,
        10,
    )
    assert result == (0, b"x" * 12000, b"", False, False)


@pytest.mark.parametrize("timeout", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_probe_deadline_is_rejected(tmp_path, timeout):
    candidate = tmp_path / "candidate.so"
    candidate.write_bytes(b"not native")
    result = probe_native_grammar(candidate, "test", provenance=None, timeout=timeout)
    assert not result.supported and result.reason == "timeout"
    assert result.artifact_sha256 is None


def test_probe_and_publish_defaults_are_the_public_deadline():
    import inspect

    from chunker._internal.user_grammar_tools import publish_native_grammar
    from chunker.grammar.integrity import DEFAULT_PROBE_TIMEOUT

    assert DEFAULT_PROBE_TIMEOUT == 30.0
    # The same object, not a restated literal, so one constant moves both.
    for function in (probe_native_grammar, publish_native_grammar):
        default = inspect.signature(function).parameters["timeout"].default
        assert default is DEFAULT_PROBE_TIMEOUT, function.__name__


@pytest.mark.parametrize("timeout", [None, 0.5, 10.0, 45.0])
def test_probe_uses_default_or_exact_caller_deadline(tmp_path, monkeypatch, timeout):
    from chunker.grammar import integrity

    candidate = tmp_path / "candidate.so"
    candidate.write_bytes(b"pinned candidate bytes")
    deadlines = []

    def read(command, cwd, deadline, **kwargs):
        deadlines.append(deadline)
        return None, b"", b"", True, False  # No worker launched; nothing to retain.

    monkeypatch.setattr(integrity, "_read_child", read)
    result = integrity.probe_native_grammar(
        candidate,
        "test",
        provenance={"sha256": hashlib.sha256(candidate.read_bytes()).hexdigest()},
        **({} if timeout is None else {"timeout": timeout}),
    )
    assert deadlines == [30.0 if timeout is None else timeout]
    assert not result.supported and result.artifact_sha256 is None


@pytest.mark.parametrize("timeout", [None, 0.5, 10.0, 45.0])
def test_publish_passes_default_or_exact_caller_deadline(
    tmp_path, monkeypatch, timeout
):
    from chunker._internal import user_grammar_tools
    from chunker.grammar.integrity import NativeProbeResult

    source = tmp_path / "compiled.so"
    source.write_bytes(b"compiled grammar bytes")
    destination = tmp_path / "baml.so"
    deadlines = []

    def probe(path, language, *, provenance, sample, timeout):
        deadlines.append(timeout)
        return NativeProbeResult(False, "timeout", None)

    monkeypatch.setattr(user_grammar_tools, "probe_native_grammar", probe)
    result = user_grammar_tools.publish_native_grammar(
        source,
        destination,
        "baml",
        provenance={"sha256": hashlib.sha256(source.read_bytes()).hexdigest()},
        **({} if timeout is None else {"timeout": timeout}),
    )
    assert deadlines == [30.0 if timeout is None else timeout]
    assert not result.supported and not destination.exists()


def test_native_probe_rejects_untrusted_candidates_before_loading(tmp_path):
    missing = tmp_path / "missing.so"
    empty = tmp_path / "empty.so"
    empty.touch()
    candidate = tmp_path / "candidate.so"
    candidate.write_bytes(b"not a native grammar")

    assert probe_native_grammar(missing, "test", provenance=None).reason == "missing"
    assert probe_native_grammar(empty, "test", provenance=None).reason == "empty"
    assert (
        probe_native_grammar(candidate, "test", provenance=None).reason == "untrusted"
    )
    assert (
        probe_native_grammar(
            candidate,
            "test",
            provenance={"sha256": "0" * 64},
        ).reason
        == "integrity_mismatch"
    )
    assert (
        probe_native_grammar(
            Path("candidate.so"),
            "test",
            provenance={"sha256": hashlib.sha256(candidate.read_bytes()).hexdigest()},
        ).reason
        == "untrusted"
    )


def _compile_ready_gate_probe(tmp_path, monkeypatch):
    """Real grammar whose library entry leaves a marker after the start grant."""
    from tests.test_compiled_grammar_analysis_contract import (
        FIXTURE,
        SOURCE,
        _compile_probe_fixture,
        trusted_artifacts,
    )

    marker = tmp_path / "native-entered"
    monkeypatch.setenv("CHUNKER_TEST_NATIVE_SENTINEL", str(marker))
    source = tmp_path / "entry-marker.c"
    source.write_text(
        """
#include <stdio.h>
#include <stdlib.h>
#ifdef _WIN32
#include <windows.h>
#endif
static void mark_entry(void) {
    const char *path = getenv("CHUNKER_TEST_NATIVE_SENTINEL");
    FILE *marker = path ? fopen(path, "wb") : NULL;
    if (marker) { fputs("entered", marker); fclose(marker); }
}
#ifdef _WIN32
BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)instance; (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) mark_entry();
    return TRUE;
}
#else
__attribute__((constructor)) static void enter_library(void) { mark_entry(); }
#endif
""",
        encoding="utf-8",
    )
    library = _compile_probe_fixture(tmp_path, [SOURCE / "parser.c", source])
    return library, marker, trusted_artifacts(library)["baml"], FIXTURE.read_bytes()


@pytest.mark.parametrize("denial_count", [1, 2])
def test_native_windows_ready_open_denial_recovers_before_start(
    tmp_path, monkeypatch, caplog, denial_count
):
    from types import SimpleNamespace
    from chunker.grammar import integrity

    caplog.set_level("DEBUG", logger=integrity.__name__)
    library, marker, provenance, sample = _compile_ready_gate_probe(
        tmp_path, monkeypatch
    )
    original_open = Path.open
    original_read = integrity._read_child
    original_ready = integrity._read_ready
    original_register = integrity._register_worker
    open_observations, registrations, roots, states = [], [], [], []
    open_denials = []
    denial = PermissionError(13, "ready record temporarily denied")

    def controlled_open(path, mode="r", *args, **kwargs):
        if path.name == integrity._READY_NAME and mode == "rb":
            open_observations.append(marker.exists())
            try:
                if len(open_observations) <= denial_count:
                    raise denial
                return original_open(path, mode, *args, **kwargs)
            except PermissionError as error:
                open_denials.append(error)
                raise
        return original_open(path, mode, *args, **kwargs)

    def ready(directory, nonce, **kwargs):
        if len(open_observations) < denial_count:
            original_sys = integrity.sys
            integrity.sys = SimpleNamespace(platform="win32")
            try:
                return original_ready(directory, nonce, **kwargs)
            finally:
                integrity.sys = original_sys
        return original_ready(directory, nonce, **kwargs)

    def register(state, record):
        assert len(open_observations) > denial_count and not any(open_observations)
        assert not marker.exists(), "native entry preceded validated registration"
        registrations.append(record["pid"])
        return original_register(state, record)

    def read(command, cwd, timeout, **kwargs):
        roots.append(cwd)
        states.append(kwargs["lifecycle"])
        return original_read(command, cwd, timeout, **kwargs)

    monkeypatch.setattr(Path, "open", controlled_open)
    monkeypatch.setattr(integrity, "_read_ready", ready)
    monkeypatch.setattr(integrity, "_register_worker", register)
    monkeypatch.setattr(integrity, "_read_child", read)
    try:
        result = integrity.probe_native_grammar(
            library,
            "baml",
            provenance=provenance,
            sample=sample,
        )
        assert result.supported and result.reason == "ok"
        assert result.artifact_sha256 == provenance["sha256"]
        assert len(registrations) == 1 and marker.read_text() == "entered"
        assert states[0].cleanup_safe and not roots[0].exists()
        # Windows may also deny a real OPEN after our injected denials. Check
        # accounting against every observed denial, not a scheduling assumption.
        assert len(open_denials) >= denial_count
        assert states[0].ready_open_denials == len(open_denials)
        assert states[0].first_ready_open_denial["errno"] == 13
        assert states[0].start_attempted and states[0].start_completed
        assert not any(
            hasattr(record, "native_probe_diagnostic") for record in caplog.records
        ), "a recovered denial must not turn a successful probe into a failure record"
    finally:
        for root in roots:
            if root.exists():
                remove_retained_probe_root(root)


def test_native_windows_ready_open_denial_uses_shared_deadline(
    tmp_path, monkeypatch, caplog
):
    from types import SimpleNamespace
    from chunker.grammar import integrity

    caplog.set_level("DEBUG", logger=integrity.__name__)
    library, marker, provenance, sample = _compile_ready_gate_probe(
        tmp_path, monkeypatch
    )
    original_open = Path.open
    original_read = integrity._read_child
    original_ready = integrity._read_ready
    open_attempts, roots, states, child_results = [], [], [], []

    def denied_open(path, mode="r", *args, **kwargs):
        if path.name == integrity._READY_NAME and mode == "rb":
            open_attempts.append(marker.exists())
            raise PermissionError(13, "ready record remains denied")
        return original_open(path, mode, *args, **kwargs)

    def ready(directory, nonce, **kwargs):
        original_sys = integrity.sys
        integrity.sys = SimpleNamespace(platform="win32")
        try:
            return original_ready(directory, nonce, **kwargs)
        finally:
            integrity.sys = original_sys

    def read(command, cwd, timeout, **kwargs):
        roots.append(cwd)
        states.append(kwargs["lifecycle"])
        child_results.append(original_read(command, cwd, timeout, **kwargs))
        return child_results[-1]

    monkeypatch.setattr(Path, "open", denied_open)
    monkeypatch.setattr(integrity, "_read_ready", ready)
    monkeypatch.setattr(integrity, "_read_child", read)
    try:
        result = integrity.probe_native_grammar(
            library,
            "baml",
            provenance=provenance,
            sample=sample,
            timeout=0.2,
        )
        assert result.reason == "child_failed" and result.artifact_sha256 is None
        assert child_results, "ready-open denial did not reach the shared deadline"
        assert child_results[0][3] and not child_results[0][4]
        assert open_attempts and not any(open_attempts)
        assert not marker.exists(), "persistent denial granted native entry"
        state = states[0]
        assert state.trigger == "timeout" and state.aborted
        assert state.worker is None and state.worker_handle is None
        assert not state.discovery_complete and not state.cleanup_safe
        assert roots[0].exists(), "startup uncertainty must retain the root"
        observations = [
            record.native_probe_diagnostic
            for record in caplog.records
            if hasattr(record, "native_probe_diagnostic")
        ]
        assert len(observations) == 1
        observation = observations[0]
        assert observation["reason"] == "child_failed"
        assert observation["trigger"] == "timeout"
        assert observation["ready_open_denials"] == len(open_attempts)
        assert observation["first_ready_open_denial"]["errno"] == 13
        assert not observation["start_attempted"] and not observation["start_completed"]
        assert not observation["cleanup_safe"]
    finally:
        for root in roots:
            if root.exists():
                remove_retained_probe_root(root)


@pytest.mark.parametrize("fault", ["nonce", "pid", "creation"])
def test_native_windows_ready_open_recovery_keeps_invalid_record_rejected(
    tmp_path, monkeypatch, fault
):
    from types import SimpleNamespace
    from chunker.grammar import integrity

    candidate = tmp_path / "candidate.so"
    candidate.write_bytes(b"startup-only pinned bytes")
    original_open = Path.open
    original_read = integrity._read_child
    original_ready = integrity._read_ready
    open_attempts, registrations, roots, states = [], [], [], []

    def controlled_open(path, mode="r", *args, **kwargs):
        if path.name == integrity._READY_NAME and mode == "rb":
            open_attempts.append(True)
            if len(open_attempts) == 1:
                raise PermissionError(13, "first ready open denied")
        return original_open(path, mode, *args, **kwargs)

    def ready(directory, nonce, **kwargs):
        if len(open_attempts) == 0:
            original_sys = integrity.sys
            integrity.sys = SimpleNamespace(platform="win32")
            try:
                return original_ready(directory, nonce, **kwargs)
            finally:
                integrity.sys = original_sys
        return original_ready(directory, nonce, **kwargs)

    def reject_register(*args):
        registrations.append(args)
        pytest.fail("invalid registration reached identity acquisition")

    def read(command, cwd, timeout, **kwargs):
        roots.append(cwd)
        states.append(kwargs["lifecycle"])
        record = {
            "schema": integrity._WORKER_SCHEMA,
            "nonce": kwargs["worker_nonce"],
            "pid": 1,
            "ppid": 1,
            "windows_creation_filetime": None,
        }
        if fault == "nonce":
            record["nonce"] = "wrong"
        elif fault == "pid":
            record["pid"] = 0
        else:
            record["windows_creation_filetime"] = "invalid"
        (cwd / integrity._READY_NAME).write_text(json.dumps(record), encoding="utf-8")
        return original_read(
            [sys._base_executable, "-I", "-c", "import time; time.sleep(60)"],
            cwd,
            timeout,
            **kwargs,
        )

    monkeypatch.setattr(Path, "open", controlled_open)
    monkeypatch.setattr(integrity, "_read_ready", ready)
    monkeypatch.setattr(integrity, "_register_worker", reject_register)
    monkeypatch.setattr(integrity, "_read_child", read)
    try:
        result = integrity.probe_native_grammar(
            candidate,
            "baml",
            provenance={"sha256": hashlib.sha256(candidate.read_bytes()).hexdigest()},
        )
        assert result.reason == "child_failed" and result.artifact_sha256 is None
        assert len(open_attempts) == 2 and not registrations
        assert states[0].worker is None and states[0].worker_handle is None
        assert not states[0].cleanup_safe and roots[0].exists()
        assert set(states[0].known) == {states[0].launcher.pid}
    finally:
        for root in roots:
            if root.exists():
                remove_retained_probe_root(root)


@pytest.mark.parametrize(
    "stage", ["read_permission", "close_permission", "nonwindows_open", "cancel"]
)
def test_ready_open_polling_does_not_swallow_other_exceptions(
    tmp_path, monkeypatch, stage
):
    from types import SimpleNamespace
    from chunker.grammar import integrity

    fault = (
        KeyboardInterrupt("ready open cancelled")
        if stage == "cancel"
        else PermissionError(13, "outside approved ready open")
    )

    class Stream:
        def __enter__(self):
            return self

        def read(self, _limit):
            if stage == "read_permission":
                raise fault
            return b"{}"

        def close(self):
            if stage == "close_permission":
                raise fault

        def __exit__(self, *_args):
            self.close()
            return False

    def controlled_open(*_args, **_kwargs):
        if stage in {"nonwindows_open", "cancel"}:
            raise fault
        return Stream()

    monkeypatch.setattr(Path, "open", controlled_open)
    original_sys = integrity.sys
    integrity.sys = SimpleNamespace(
        platform="linux" if stage == "nonwindows_open" else "win32"
    )
    try:
        with pytest.raises(type(fault)) as raised:
            integrity._read_ready(tmp_path, "nonce")
        assert raised.value is fault
    finally:
        integrity.sys = original_sys


_READY_CLOSE_FAILURES = pytest.mark.parametrize(
    "close_error",
    [OSError("ready close failure"), KeyboardInterrupt("second cancellation")],
    ids=["close_oserror", "close_interrupt"],
)


def _cancelling_ready_stream(stream, events, original, close_error):
    """Support old context disposal and repaired explicit close with one proxy."""

    class Stream:
        def __enter__(self):
            return self

        def read(self, _limit):
            events.append("read")
            raise original

        def close(self):
            events.append("close")
            if stream is not None:
                stream.close()
            raise close_error

        def __exit__(self, *_args):
            self.close()
            return False

    return Stream()


@_READY_CLOSE_FAILURES
def test_ready_read_cancellation_survives_stream_disposal_failure(
    tmp_path, monkeypatch, close_error
):
    import traceback
    from chunker.grammar import integrity

    events = []
    original = KeyboardInterrupt("original ready read cancellation")
    monkeypatch.setattr(
        Path,
        "open",
        lambda *_args, **_kwargs: _cancelling_ready_stream(
            None, events, original, close_error
        ),
    )

    try:
        integrity._read_ready(tmp_path, "nonce")
    except BaseException as error:  # noqa: BLE001 - exact identity is the contract
        caught = error
    else:
        pytest.fail("ready read cancellation unexpectedly returned")

    assert caught is original, f"original cancellation replaced by {caught!r}"
    assert traceback.extract_tb(caught.__traceback__)[-1].name == "read"
    assert events == ["read", "close"], "stream must be disposed exactly once"


@_READY_CLOSE_FAILURES
def test_native_probe_ready_read_cancellation_survives_disposal_failure(
    tmp_path, monkeypatch, close_error, caplog
):
    import traceback
    from chunker.grammar import integrity

    library, marker, provenance, sample = _compile_ready_gate_probe(
        tmp_path, monkeypatch
    )
    original_open = Path.open
    original_read = integrity._read_child
    events, registrations, roots, states = [], [], [], []
    original = KeyboardInterrupt("original ready read cancellation")
    caplog.set_level("DEBUG", logger=integrity.__name__)

    def controlled_open(path, mode="r", *args, **kwargs):
        stream = original_open(path, mode, *args, **kwargs)
        if path.name == integrity._READY_NAME and mode == "rb":
            return _cancelling_ready_stream(stream, events, original, close_error)
        return stream

    def reject_register(*args):
        registrations.append(args)
        pytest.fail("cancelled ready read reached worker registration")

    def read(command, cwd, timeout, **kwargs):
        roots.append(cwd)
        states.append(kwargs["lifecycle"])
        return original_read(command, cwd, timeout, **kwargs)

    monkeypatch.setattr(Path, "open", controlled_open)
    monkeypatch.setattr(integrity, "_register_worker", reject_register)
    monkeypatch.setattr(integrity, "_read_child", read)
    try:
        try:
            result = integrity.probe_native_grammar(
                library,
                "baml",
                provenance=provenance,
                sample=sample,
            )
        except BaseException as error:  # noqa: BLE001 - exact identity is the contract
            caught = error
        else:
            pytest.fail(f"ready read cancellation became public result {result!r}")

        assert caught is original, f"original cancellation replaced by {caught!r}"
        assert traceback.extract_tb(caught.__traceback__)[-1].name == "read"
        observations = [
            record.native_probe_diagnostic
            for record in caplog.records
            if hasattr(record, "native_probe_diagnostic")
        ]
        assert len(observations) == 1
        assert observations[0]["reason"] is None
        assert observations[0]["exception"]["type"] == "KeyboardInterrupt"
        assert observations[0]["exception"]["operation"] == "ready_read"
        assert observations[0]["exception"]["frames"][-1]["function"] == "read"
        assert events == ["read", "close"], "stream must be disposed exactly once"
        assert not registrations and not marker.exists()
        state = states[0]
        assert state.launch_attempted and state.worker is None
        assert state.worker_handle is None and not state.discovery_complete
        assert not state.cleanup_safe and roots[0].exists()
    finally:
        for root in roots:
            if root.exists():
                remove_retained_probe_root(root)


@pytest.mark.skipif(sys.platform != "win32", reason="Win32 exclusive sharing")
def test_native_windows_actual_exclusive_ready_open_is_pending(tmp_path):
    import ctypes
    import os
    from ctypes import wintypes
    from chunker.grammar import integrity

    nonce = "actual-sharing-control"
    ready = tmp_path / integrity._READY_NAME
    record = {
        "schema": integrity._WORKER_SCHEMA,
        "nonce": nonce,
        "pid": os.getpid(),
        "ppid": os.getppid(),
        "windows_creation_filetime": "0000000000000001",
    }
    ready.write_text(json.dumps(record), encoding="utf-8")
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create = kernel32.CreateFileW
    create.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    create.restype = wintypes.HANDLE
    close = kernel32.CloseHandle
    close.argtypes = [wintypes.HANDLE]
    close.restype = wintypes.BOOL
    handle = create(str(ready), 0x80000000, 0, None, 3, 0x80, None)
    assert handle and handle != wintypes.HANDLE(-1).value
    try:
        assert integrity._read_ready(tmp_path, nonce) is None
    finally:
        assert close(handle)
    assert integrity._read_ready(tmp_path, nonce) == record


@pytest.mark.parametrize("operation", ["read", "write", "flush", "fsync"])
@_SNAPSHOT_CLOSE_FAILURES
def test_native_snapshot_copy_preserves_operation_cancellation_during_disposal(
    tmp_path, monkeypatch, operation, close_error
):
    import traceback
    from chunker.grammar import integrity

    candidate = tmp_path / "candidate.so"
    candidate.write_bytes(b"pinned snapshot copy fixture")
    provenance = {"sha256": hashlib.sha256(candidate.read_bytes()).hexdigest()}
    original = KeyboardInterrupt(f"original snapshot {operation} cancellation")
    events, roots, streams = [], [], []
    real_fdopen = integrity.os.fdopen
    real_fsync = integrity.os.fsync
    real_mkdtemp = integrity.tempfile.mkdtemp

    def controlled_fdopen(fd, mode, *args, **kwargs):
        stream = real_fdopen(fd, mode, *args, **kwargs)
        role = "source" if mode == "rb" else "destination"
        proxy = _SnapshotFaultStream(
            stream,
            events,
            role,
            operation=operation,
            operation_error=original,
            close_error=close_error if role == "destination" else None,
        )
        streams.append(proxy)
        return proxy

    def controlled_fsync(fd):
        events.append("destination.fsync")
        if operation == "fsync":
            raise original
        return real_fsync(fd)

    def controlled_mkdtemp(*args, **kwargs):
        root = Path(real_mkdtemp(*args, **kwargs))
        roots.append(root)
        return str(root)

    monkeypatch.setattr(integrity.os, "fdopen", controlled_fdopen)
    monkeypatch.setattr(integrity.os, "fsync", controlled_fsync)
    monkeypatch.setattr(integrity.tempfile, "mkdtemp", controlled_mkdtemp)
    monkeypatch.setattr(
        integrity,
        "_read_child",
        lambda *_args, **_kwargs: pytest.fail("snapshot fault reached native launch"),
    )
    try:
        try:
            result = integrity.probe_native_grammar(
                candidate,
                "baml",
                provenance=provenance,
                inspect_artifact=lambda _: pytest.fail(
                    "snapshot fault reached inspection"
                ),
            )
        except BaseException as error:  # noqa: BLE001 - exact identity is the contract
            caught = error
        else:
            pytest.fail(f"snapshot cancellation became public result {result!r}")
        assert caught is original
        expected_frame = "controlled_fsync" if operation == "fsync" else operation
        assert traceback.extract_tb(caught.__traceback__)[-1].name == expected_frame
        assert events.count("destination.close") == 1
        assert events.count("source.close") == 1
        assert all(proxy.stream.closed for proxy in streams)
        assert roots and not roots[0].exists(), "prelaunch root must be removed"
    finally:
        for root in roots:
            if root.exists():
                remove_retained_probe_root(root)


@pytest.mark.parametrize("stage", ["dup", "destination_fdopen"])
def test_native_snapshot_copy_acquisition_failure_closes_owned_descriptors(
    tmp_path, monkeypatch, stage
):
    from chunker.grammar import integrity

    candidate = tmp_path / "candidate.so"
    candidate.write_bytes(b"pinned snapshot acquisition fixture")
    provenance = {"sha256": hashlib.sha256(candidate.read_bytes()).hexdigest()}
    original = KeyboardInterrupt(f"original {stage} cancellation")
    snapshot_descriptors, closed = [], []
    real_close = integrity.os.close
    real_dup = integrity.os.dup
    real_fdopen = integrity.os.fdopen
    real_mkstemp = integrity.tempfile.mkstemp

    def controlled_mkstemp(*args, **kwargs):
        descriptor, name = real_mkstemp(*args, **kwargs)
        snapshot_descriptors.append(descriptor)
        return descriptor, name

    def controlled_dup(descriptor):
        if stage == "dup":
            raise original
        return real_dup(descriptor)

    def controlled_fdopen(descriptor, mode, *args, **kwargs):
        if stage == "destination_fdopen" and mode == "wb":
            raise original
        return real_fdopen(descriptor, mode, *args, **kwargs)

    def controlled_close(descriptor):
        if descriptor in snapshot_descriptors and descriptor not in closed:
            closed.append(descriptor)
        return real_close(descriptor)

    monkeypatch.setattr(integrity.tempfile, "mkstemp", controlled_mkstemp)
    monkeypatch.setattr(integrity.os, "dup", controlled_dup)
    monkeypatch.setattr(integrity.os, "fdopen", controlled_fdopen)
    monkeypatch.setattr(integrity.os, "close", controlled_close)
    try:
        with pytest.raises(KeyboardInterrupt) as raised:
            integrity.probe_native_grammar(candidate, "baml", provenance=provenance)
        assert raised.value is original
        assert closed == snapshot_descriptors, "raw snapshot descriptor leaked"
    finally:
        for descriptor in snapshot_descriptors:
            if descriptor not in closed:
                real_close(descriptor)


@_SNAPSHOT_CLOSE_FAILURES
def test_native_snapshot_copy_success_propagates_first_disposal_failure(
    tmp_path, monkeypatch, close_error
):
    from chunker.grammar import integrity

    candidate = tmp_path / "candidate.so"
    candidate.write_bytes(b"pinned successful snapshot copy fixture")
    provenance = {"sha256": hashlib.sha256(candidate.read_bytes()).hexdigest()}
    events = []
    real_fdopen = integrity.os.fdopen

    def controlled_fdopen(fd, mode, *args, **kwargs):
        stream = real_fdopen(fd, mode, *args, **kwargs)
        return _SnapshotFaultStream(
            stream,
            events,
            "source" if mode == "rb" else "destination",
            close_error=close_error if mode == "wb" else None,
        )

    monkeypatch.setattr(integrity.os, "fdopen", controlled_fdopen)
    monkeypatch.setattr(
        integrity,
        "_read_child",
        lambda *_args, **_kwargs: pytest.fail("close failure reached native launch"),
    )
    if isinstance(close_error, OSError):
        result = integrity.probe_native_grammar(
            candidate, "baml", provenance=provenance
        )
        assert result.reason == "child_failed" and result.artifact_sha256 is None
    else:
        with pytest.raises(KeyboardInterrupt) as raised:
            integrity.probe_native_grammar(candidate, "baml", provenance=provenance)
        assert raised.value is close_error
    assert events.count("destination.close") == 1
    assert events.count("source.close") == 1


def test_native_snapshot_copy_preserves_ordinary_operation_error_over_close(
    tmp_path, monkeypatch
):
    from chunker.grammar import integrity

    candidate = tmp_path / "candidate.so"
    candidate.write_bytes(b"pinned ordinary copy failure fixture")
    provenance = {"sha256": hashlib.sha256(candidate.read_bytes()).hexdigest()}
    operation_error = OSError("original snapshot flush failure")
    close_error = KeyboardInterrupt("later snapshot close cancellation")
    events = []
    real_fdopen = integrity.os.fdopen

    def controlled_fdopen(fd, mode, *args, **kwargs):
        stream = real_fdopen(fd, mode, *args, **kwargs)
        return _SnapshotFaultStream(
            stream,
            events,
            "source" if mode == "rb" else "destination",
            operation="flush" if mode == "wb" else None,
            operation_error=operation_error,
            close_error=close_error if mode == "wb" else None,
        )

    monkeypatch.setattr(integrity.os, "fdopen", controlled_fdopen)
    try:
        result = integrity.probe_native_grammar(
            candidate, "baml", provenance=provenance
        )
    except BaseException as error:  # noqa: BLE001 - reject replacement explicitly
        replacement = error
        result = None
    else:
        replacement = None
    assert replacement is None, f"operation error replaced by {replacement!r}"
    assert result is not None
    assert result.reason == "child_failed" and result.artifact_sha256 is None
    assert events.count("destination.close") == 1
    assert events.count("source.close") == 1


@pytest.mark.parametrize(
    "cleanup_error",
    [OSError("snapshot root cleanup failure"), KeyboardInterrupt("cleanup cancelled")],
    ids=["cleanup_oserror", "cleanup_interrupt"],
)
def test_native_snapshot_cleanup_ignores_callers_handled_exception(
    tmp_path, monkeypatch, cleanup_error
):
    from chunker.grammar import integrity

    candidate = tmp_path / "candidate.so"
    candidate.write_bytes(b"pinned cleanup ownership fixture")
    roots = []
    real_mkdtemp = integrity.tempfile.mkdtemp
    real_rmtree = integrity.shutil.rmtree

    def controlled_mkdtemp(*args, **kwargs):
        root = Path(real_mkdtemp(*args, **kwargs))
        roots.append(root)
        return str(root)

    def controlled_rmtree(_root):
        raise cleanup_error

    monkeypatch.setattr(integrity.tempfile, "mkdtemp", controlled_mkdtemp)
    monkeypatch.setattr(integrity.shutil, "rmtree", controlled_rmtree)
    try:
        try:
            raise LookupError("handled caller exception")
        except LookupError:
            if isinstance(cleanup_error, OSError):
                result = integrity.probe_native_grammar(
                    candidate, "baml", provenance={"sha256": "0" * 64}
                )
                assert result.reason == "child_failed"
            else:
                with pytest.raises(KeyboardInterrupt) as raised:
                    integrity.probe_native_grammar(
                        candidate, "baml", provenance={"sha256": "0" * 64}
                    )
                assert raised.value is cleanup_error
        assert roots and roots[0].exists(), "injected cleanup cannot remove the root"
    finally:
        for root in roots:
            if root.exists():
                remove_retained_probe_root(root, remover=real_rmtree)


@_SNAPSHOT_CLOSE_FAILURES
def test_native_final_source_disposal_preserves_acquisition_cancellation(
    tmp_path, monkeypatch, close_error
):
    import traceback
    from chunker.grammar import integrity

    candidate = tmp_path / "candidate.so"
    candidate.write_bytes(b"pinned source descriptor fixture")
    provenance = {"sha256": hashlib.sha256(candidate.read_bytes()).hexdigest()}
    original = KeyboardInterrupt("original snapshot acquisition cancellation")
    events, opened, roots = [], [], []
    real_open = integrity.os.open
    real_close = integrity.os.close
    real_mkdtemp = integrity.tempfile.mkdtemp

    def controlled_open(*args, **kwargs):
        descriptor = real_open(*args, **kwargs)
        opened.append(descriptor)
        return descriptor

    def controlled_close(descriptor):
        if opened and descriptor == opened[0]:
            events.append("source_fd.close")
            real_close(descriptor)
            raise close_error
        return real_close(descriptor)

    def controlled_mkdtemp(*args, **kwargs):
        root = Path(real_mkdtemp(*args, **kwargs))
        roots.append(root)
        return str(root)

    def acquire_snapshot(*_args, **_kwargs):
        raise original

    monkeypatch.setattr(integrity.os, "open", controlled_open)
    monkeypatch.setattr(integrity.os, "close", controlled_close)
    monkeypatch.setattr(integrity.tempfile, "mkdtemp", controlled_mkdtemp)
    monkeypatch.setattr(integrity.tempfile, "mkstemp", acquire_snapshot)
    try:
        try:
            integrity.probe_native_grammar(candidate, "baml", provenance=provenance)
        except BaseException as error:  # noqa: BLE001 - exact identity is the contract
            caught = error
        else:
            pytest.fail("snapshot acquisition cancellation unexpectedly returned")
        assert caught is original
        assert traceback.extract_tb(caught.__traceback__)[-1].name == "acquire_snapshot"
        assert events == ["source_fd.close"]
        assert roots and not roots[0].exists(), "prelaunch root must be removed"
    finally:
        for root in roots:
            if root.exists():
                remove_retained_probe_root(root)


@_SNAPSHOT_CLOSE_FAILURES
def test_native_final_snapshot_hash_preserves_read_cancellation_during_disposal(
    tmp_path, monkeypatch, close_error
):
    import traceback
    from chunker.grammar import integrity

    candidate = tmp_path / "candidate.so"
    candidate.write_bytes(b"pinned final hash fixture")
    digest = hashlib.sha256(candidate.read_bytes()).hexdigest()
    original = KeyboardInterrupt("original final snapshot hash cancellation")
    events, roots = [], []
    snapshot_opens = 0
    real_open = Path.open
    real_mkdtemp = integrity.tempfile.mkdtemp

    def controlled_open(path, mode="r", *args, **kwargs):
        nonlocal snapshot_opens
        stream = real_open(path, mode, *args, **kwargs)
        if path.parent in roots and mode == "rb":
            snapshot_opens += 1
            if snapshot_opens == 2:
                return _SnapshotFaultStream(
                    stream,
                    events,
                    "final_hash",
                    operation="read",
                    operation_error=original,
                    close_error=close_error,
                )
        return stream

    def controlled_mkdtemp(*args, **kwargs):
        root = Path(real_mkdtemp(*args, **kwargs))
        roots.append(root)
        return str(root)

    def acknowledge(command, _cwd, _timeout, **kwargs):
        lifecycle = kwargs["lifecycle"]
        lifecycle.discovery_complete = True
        lifecycle.cleanup_safe = True
        lifecycle.worker_status = 0
        reply = {
            "schema": integrity._ACK_SCHEMA,
            "nonce": command[9],
            "language": command[6],
            "sha256": command[7],
            "loader_returned": True,
            "parse_returned": True,
        }
        return 0, json.dumps(reply).encode(), b"", False, False

    monkeypatch.setattr(Path, "open", controlled_open)
    monkeypatch.setattr(integrity.tempfile, "mkdtemp", controlled_mkdtemp)
    monkeypatch.setattr(integrity, "_read_child", acknowledge)
    try:
        try:
            result = integrity.probe_native_grammar(
                candidate,
                "baml",
                provenance={"sha256": digest},
                inspect_artifact=lambda _: pytest.fail(
                    "final hash cancellation reached inspection"
                ),
            )
        except BaseException as error:  # noqa: BLE001 - exact identity is the contract
            caught = error
        else:
            pytest.fail(f"final hash cancellation became public result {result!r}")
        assert caught is original
        assert traceback.extract_tb(caught.__traceback__)[-1].name == "read"
        assert events == ["final_hash.read", "final_hash.close"]
        assert snapshot_opens == 2
        assert roots and not roots[0].exists()
    finally:
        for root in roots:
            if root.exists():
                remove_retained_probe_root(root)


@pytest.mark.parametrize(
    "fault",
    [
        "nonce",
        "schema",
        "pid_bool",
        "ppid_bool",
        "extra",
        "duplicate",
        "oversized",
        "ancestry",
        "creation",
    ],
)
def test_native_invalid_registration_never_targets_unrelated_pid(
    tmp_path, monkeypatch, fault
):
    import json
    import os
    import subprocess
    import psutil
    from chunker.grammar import integrity

    # These stdlib-only sleepers must each be one fixture-owned OS process.
    # A venv redirector can spawn an undiscovered child after the final scan;
    # production correctly retains that uncertainty, so deleting its cwd races.
    sentinel = subprocess.Popen(
        [sys._base_executable, "-I", "-c", "import time; time.sleep(60)"]
    )
    targets = []
    real_terminate, real_kill = psutil.Process.terminate, psutil.Process.kill
    monkeypatch.setattr(
        psutil.Process,
        "terminate",
        lambda p: (targets.append(p.pid), real_terminate(p))[-1],
    )
    monkeypatch.setattr(
        psutil.Process, "kill", lambda p: (targets.append(p.pid), real_kill(p))[-1]
    )
    candidate = tmp_path / "candidate.so"
    candidate.write_bytes(b"deliberately pinned protocol fixture")
    roots, states = [], []
    original = integrity._read_child

    def invalid(command, cwd, timeout, **kwargs):
        roots.append(cwd)
        states.append(kwargs["lifecycle"])
        nonce = kwargs["worker_nonce"]
        record = {
            "schema": "native_probe.worker.v2",
            "nonce": nonce,
            "pid": sentinel.pid,
            "ppid": os.getpid(),
            "windows_creation_filetime": None,
        }
        if fault == "nonce":
            record["nonce"] = "wrong"
        if fault == "schema":
            record["schema"] = "native_probe.worker.v1"
        if fault == "pid_bool":
            record["pid"] = True
        if fault == "ppid_bool":
            record["ppid"] = True
        if fault == "extra":
            record["extra"] = 1
        if fault == "ancestry":
            record["ppid"] = sentinel.pid
        if fault == "creation":
            record["windows_creation_filetime"] = "0000000000000000"
        payload = json.dumps(record)
        if fault == "duplicate":
            payload = payload[:-1] + ', "pid": 123}'
        if fault == "oversized":
            payload = " " * 4097 + payload
        (cwd / integrity._READY_NAME).write_text(payload, encoding="utf-8")
        return original(
            [sys._base_executable, "-I", "-c", "import time; time.sleep(60)"],
            cwd,
            timeout,
            **kwargs,
        )

    monkeypatch.setattr(integrity, "_read_child", invalid)
    try:
        result = integrity.probe_native_grammar(
            candidate,
            "test",
            provenance={"sha256": hashlib.sha256(candidate.read_bytes()).hexdigest()},
        )
        assert result.reason == "child_failed" and result.artifact_sha256 is None
        assert roots[0].exists() and sentinel.poll() is None
        assert sentinel.pid not in targets
        assert states[0].launcher.poll() is not None
        assert set(states[0].known) == {states[0].launcher.pid}
    finally:
        if sentinel.poll() is None:
            sentinel.kill()
        sentinel.wait(timeout=10)
        for root in roots:
            if root.exists():
                remove_retained_probe_root(root)


@pytest.mark.parametrize("event", ["cancel", "launcher_loss", "creation_boundary"])
def test_native_pre_ready_uncertainty_retains_snapshot(tmp_path, monkeypatch, event):
    import gc
    import psutil
    from chunker.grammar import integrity
    from tests.test_compiled_grammar_analysis_contract import (
        _wait_for_file,
        _NativeObserver,
    )

    candidate = tmp_path / "candidate.so"
    candidate.write_bytes(b"reviewed startup-only fixture")
    go, marker = tmp_path / "go", tmp_path / "worker"
    roots, states, scans = [], [], []
    original_read, original_discover = integrity._read_child, integrity._discover
    worker_code = (
        "import os,time; from pathlib import Path; Path("
        + repr(str(marker))
        + ").write_text(str(os.getpid())); time.sleep(60)"
    )
    launcher_code = (
        "import subprocess,sys,time; from pathlib import Path; "
        f"p=Path({str(go)!r}); "
        "\nwhile not p.exists(): time.sleep(0.01)\n"
        f"subprocess.Popen([sys.executable,'-I','-c',{worker_code!r}], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)\n"
    )
    observer = None

    def read(command, cwd, timeout, **kwargs):
        roots.append(cwd)
        states.append(kwargs["lifecycle"])
        return original_read(
            [sys._base_executable, "-I", "-c", launcher_code], cwd, timeout, **kwargs
        )

    def discover(state):
        nonlocal observer
        original_discover(state)
        if scans:
            return
        scans.append(set(state.known))
        assert scans[0] == {
            state.launcher.pid
        }, "first scan precedes actual worker creation"
        go.touch()
        _wait_for_file(marker)
        pid = int(marker.read_text())
        observer = _NativeObserver(pid, None)
        # Driver binds identity while the delayed, unregistered worker is alive.
        identity = psutil.Process(pid)
        identity.create_time()
        state.launcher.wait(timeout=10)
        assert identity.is_running()
        if event != "launcher_loss":
            raise KeyboardInterrupt("original pre-ready cancellation")

    monkeypatch.setattr(integrity, "_read_child", read)
    monkeypatch.setattr(integrity, "_discover", discover)
    try:
        if event == "launcher_loss":
            result = integrity.probe_native_grammar(
                candidate,
                "test",
                provenance={
                    "sha256": hashlib.sha256(candidate.read_bytes()).hexdigest()
                },
            )
            assert result.reason == "child_failed" and result.artifact_sha256 is None
        else:
            with pytest.raises(
                KeyboardInterrupt, match="original pre-ready cancellation"
            ):
                integrity.probe_native_grammar(
                    candidate,
                    "test",
                    provenance={
                        "sha256": hashlib.sha256(candidate.read_bytes()).hexdigest()
                    },
                )
        pid = int(marker.read_text())
        assert psutil.Process(
            pid
        ).is_running(), "unknown worker is alive before emergency cleanup"
        assert states[0].worker is None and not states[0].cleanup_safe
        assert roots[0].exists()
        gc.collect()
        assert roots[0].exists(), "no finalizer may reclaim an uncertain root"
        assert not (roots[0] / integrity._READY_NAME).exists()
    finally:
        if marker.exists():
            assert (
                observer is not None
            ), f"No retained observer for probe PID {marker.read_text()}; root retained"
            # This deliberately unknown worker belongs to the fixture. Its
            # observer was bound before launcher loss; never reopen a PID here.
            if observer.alive():
                observer.process.kill()
            if observer.handle is not None:
                assert (
                    observer.api.WaitForSingleObject(observer.handle, 10000) == 0
                ), f"Retained probe PID {observer.process.pid} outlived teardown deadline"
            else:
                observer.process.wait(timeout=10)
            assert (
                not observer.alive()
            ), f"Retained probe PID {observer.process.pid} still alive"
        if observer is not None:
            observer.close()
        for root in roots:
            if root.exists():
                remove_retained_probe_root(root)


@pytest.mark.parametrize(
    "stage",
    ["constructor", "setup", "read", "access", "wait", "cancel", "second_interrupt"],
)
def test_native_lifecycle_faults_retain_unsafe_root(tmp_path, monkeypatch, stage):
    import gc
    import subprocess
    from chunker.grammar import integrity

    candidate = tmp_path / "candidate.so"
    candidate.write_bytes(b"reviewed no-native setup fixture")
    real_popen, real_stop, real_ready = (
        integrity.subprocess.Popen,
        integrity._stop_child,
        integrity._read_ready,
    )
    states, roots = [], []
    original_read = integrity._read_child
    injected = (
        RuntimeError("original read fault")
        if stage == "read"
        else KeyboardInterrupt("original cancellation")
    )

    def popen(*args, **kwargs):
        if stage == "constructor":
            raise OSError("ambiguous creation failure")
        return real_popen(
            [sys._base_executable, "-I", "-c", "import time; time.sleep(60)"], **kwargs
        )

    def read(command, cwd, timeout, **kwargs):
        roots.append(cwd)
        states.append(kwargs["lifecycle"])
        return original_read(
            command, cwd, 0.1 if stage == "wait" else timeout, **kwargs
        )

    def ready(*args, **kwargs):
        if stage in {"cancel", "second_interrupt", "read"}:
            raise injected
        if stage == "access":
            raise PermissionError("registration access denied")
        return real_ready(*args, **kwargs)

    def stop(state):
        if stage == "wait":
            raise subprocess.TimeoutExpired("stop", 5)
        if stage == "second_interrupt":
            raise KeyboardInterrupt("second cancellation")
        return real_stop(state)

    monkeypatch.setattr(integrity.subprocess, "Popen", popen)
    monkeypatch.setattr(integrity, "_read_child", read)
    monkeypatch.setattr(integrity, "_read_ready", ready)
    monkeypatch.setattr(integrity, "_stop_child", stop)
    if stage == "setup" and sys.platform != "win32":
        monkeypatch.setattr(
            integrity.os,
            "set_blocking",
            lambda *args: (_ for _ in ()).throw(OSError("setup failed")),
        )
    try:
        if stage in {"cancel", "second_interrupt", "read"}:
            with pytest.raises(type(injected)) as caught:
                integrity.probe_native_grammar(
                    candidate,
                    "test",
                    provenance={
                        "sha256": hashlib.sha256(candidate.read_bytes()).hexdigest()
                    },
                )
            assert caught.value is injected
        elif stage == "wait":
            with pytest.raises(subprocess.TimeoutExpired):
                integrity.probe_native_grammar(
                    candidate,
                    "test",
                    provenance={
                        "sha256": hashlib.sha256(candidate.read_bytes()).hexdigest()
                    },
                )
        else:
            result = integrity.probe_native_grammar(
                candidate,
                "test",
                provenance={
                    "sha256": hashlib.sha256(candidate.read_bytes()).hexdigest()
                },
                timeout=0.1 if stage == "setup" and sys.platform == "win32" else 10,
            )
            assert result.reason == "child_failed" and result.artifact_sha256 is None
        assert states[0].launch_attempted and not states[0].cleanup_safe
        if states[0].launcher is not None:
            assert set(states[0].known) == {states[0].launcher.pid}
        assert roots[0].exists()
        gc.collect()
        assert roots[0].exists()
    finally:
        process = states[0].launcher
        if stage in {"wait", "second_interrupt"} and process is not None:
            # These controls deliberately replace product stop with an exception.
            # Release their stdlib sleeper only after the original assertions;
            # every real product-stop path must exit without a fixture signal.
            if process.poll() is None:
                process.kill()
        # The retained Popen handle must confirm exit even after a fixture signal.
        for root in roots:
            if root.exists():
                remove_retained_probe_root(root)


@pytest.mark.parametrize("diagnostic_error", [OSError, KeyboardInterrupt])
def test_native_retention_diagnostic_failure_preserves_cancellation(
    tmp_path, monkeypatch, capsys, diagnostic_error
):
    from chunker.grammar import integrity

    candidate = tmp_path / "candidate.so"
    candidate.write_bytes(b"reviewed pre-launch fault fixture")
    cancellation = KeyboardInterrupt("original launch cancellation")
    roots = []

    def read(_command, cwd, _timeout, **kwargs):
        roots.append(cwd)
        kwargs["lifecycle"].launch_attempted = True
        raise cancellation

    class FailingLogger:
        def error(self, _message):
            raise diagnostic_error("diagnostic sink failed")

    try:
        with monkeypatch.context() as context:
            context.setattr(integrity, "_read_child", read)
            context.setattr(
                integrity.logging, "getLogger", lambda _name: FailingLogger()
            )
            with pytest.raises(KeyboardInterrupt) as caught:
                integrity.probe_native_grammar(
                    candidate,
                    "test",
                    provenance={
                        "sha256": hashlib.sha256(candidate.read_bytes()).hexdigest()
                    },
                )
            assert caught.value is cancellation
            assert roots[0].exists()
            assert str(roots[0]) in capsys.readouterr().err
    finally:
        for root in roots:
            if root.exists():
                remove_retained_probe_root(root)


def test_native_rejection_diagnostic_preserves_launch_error_without_private_data(
    tmp_path, monkeypatch, caplog
):
    from chunker.grammar import integrity

    candidate = tmp_path / "private-grammar.so"
    candidate.write_bytes(b"private grammar contents")
    error = PermissionError(13, "private error message", "/private/secret-path")
    error.winerror = 32
    roots = []

    def launch(_command, *, cwd, **_kwargs):
        roots.append(cwd)
        raise error

    monkeypatch.setattr(integrity.subprocess, "Popen", launch)
    caplog.set_level("DEBUG", logger=integrity.__name__)
    try:
        result = integrity.probe_native_grammar(
            candidate,
            "test",
            provenance={"sha256": hashlib.sha256(candidate.read_bytes()).hexdigest()},
            sample=b"private source sample",
        )
        assert result == integrity.NativeProbeResult(False, "child_failed", None)
        observations = [
            record.native_probe_diagnostic
            for record in caplog.records
            if hasattr(record, "native_probe_diagnostic")
        ]
        assert (
            len(observations) == 1
        ), "the original rejection needs one structured record"
        observation = observations[0]
        assert observation["schema"] == "native_probe.diagnostic.v1"
        assert observation["phase"] == "native_worker"
        assert observation["exception"]["operation"] == "launch"
        assert observation["exception"]["type"] == "PermissionError"
        assert observation["exception"]["errno"] == 13
        assert observation["exception"]["winerror"] == 32
        assert observation["exception"]["frames"][-1]["function"] == "launch"
        assert observation["launch_attempted"] and not observation["cleanup_safe"]
        assert (
            observation["worker_pid"] is None and observation["worker_status"] is None
        )
        assert not observation["start_attempted"] and not observation["start_completed"]
        assert roots[0].exists(), "diagnostics cannot authorize uncertain cleanup"
        serialized = json.dumps(observation)
        assert len(serialized) < 4096
        assert "private" not in serialized and "secret-path" not in serialized
        record = next(
            record
            for record in caplog.records
            if hasattr(record, "native_probe_diagnostic")
        )
        assert json.loads(record.getMessage().split(": ", 1)[1]) == observation
    finally:
        # The replaced Popen never created a process; only this fixture owns the root.
        for root in roots:
            remove_retained_probe_root(root)


@pytest.mark.parametrize("sink_error", [OSError, KeyboardInterrupt])
def test_native_failure_diagnostic_sink_preserves_original_cancellation(
    tmp_path, monkeypatch, sink_error
):
    from chunker.grammar import integrity

    candidate = tmp_path / "candidate.so"
    candidate.write_bytes(b"no native execution")
    original = KeyboardInterrupt("original launch cancellation")
    roots = []

    def launch(_command, *, cwd, **_kwargs):
        roots.append(cwd)
        raise original

    class FailingLogger:
        def isEnabledFor(self, _level):  # noqa: N802 - logging.Logger interface
            return True

        def debug(self, *_args, **_kwargs):
            raise sink_error("failure observer failed")

        def error(self, *_args, **_kwargs):
            pass

    try:
        with monkeypatch.context() as context:
            context.setattr(integrity.subprocess, "Popen", launch)
            context.setattr(
                integrity.logging, "getLogger", lambda _name: FailingLogger()
            )
            with pytest.raises(KeyboardInterrupt) as caught:
                integrity.probe_native_grammar(
                    candidate,
                    "test",
                    provenance={
                        "sha256": hashlib.sha256(candidate.read_bytes()).hexdigest()
                    },
                )
            assert caught.value is original
        assert roots[0].exists()
    finally:
        for root in roots:
            remove_retained_probe_root(root)


@pytest.mark.parametrize("sink_error", [OSError, KeyboardInterrupt])
def test_native_failure_diagnostic_sink_keeps_rejection_and_new_cancellation(
    monkeypatch, sink_error
):
    from chunker.grammar import integrity

    error = sink_error("diagnostic sink failure")

    class FailingLogger:
        def isEnabledFor(self, _level):  # noqa: N802 - logging.Logger interface
            return True

        def debug(self, *_args, **_kwargs):
            raise error

    with monkeypatch.context() as context:
        context.setattr(integrity.logging, "getLogger", lambda _name: FailingLogger())
        if sink_error is KeyboardInterrupt:
            with pytest.raises(KeyboardInterrupt) as caught:
                integrity.probe_native_grammar(
                    Path("relative.so"), "test", provenance=None
                )
            assert caught.value is error
        else:
            result = integrity.probe_native_grammar(
                Path("relative.so"), "test", provenance=None
            )
            assert result == integrity.NativeProbeResult(False, "untrusted", None)


def test_native_denial_observation_does_not_swallow_cancellation(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from chunker.grammar import integrity

    cancellation = KeyboardInterrupt("cancel while observing recovered denial")
    state = integrity._ProbeLifecycle()

    def denied(*_args, **_kwargs):
        raise PermissionError(13, "ready open denied")

    def cancelled(_error):
        raise cancellation

    monkeypatch.setattr(integrity, "sys", SimpleNamespace(platform="win32"))
    monkeypatch.setattr(Path, "open", denied)
    monkeypatch.setattr(integrity, "_exception_metadata", cancelled)
    with pytest.raises(KeyboardInterrupt) as caught:
        integrity._read_ready(tmp_path, "nonce", lifecycle=state)
    assert caught.value is cancellation
    assert state.ready_open_denials == 1
    assert not state.start_attempted and not state.discovery_complete


@pytest.mark.parametrize("primary_type", [KeyboardInterrupt, PermissionError])
@pytest.mark.parametrize("observer_type", [OSError, KeyboardInterrupt])
def test_native_failed_observation_keeps_first_error_through_cleanup_failure(
    tmp_path, monkeypatch, caplog, primary_type, observer_type
):
    import traceback
    from chunker.grammar import integrity

    candidate = tmp_path / "candidate.so"
    candidate.write_bytes(b"no native execution")
    primary = primary_type("original launch failure")
    cleanup = OSError("secondary stop failure")
    original_observer = integrity._exception_metadata
    roots, states, observed = [], [], []

    def launch(_command, *, cwd, **_kwargs):
        roots.append(cwd)
        raise primary

    def observe(error):
        observed.append(error)
        if len(observed) == 1:
            assert error is primary
            raise observer_type("first observation unavailable")
        return original_observer(error)

    def stop(state):
        states.append(state)
        raise cleanup

    monkeypatch.setattr(integrity.subprocess, "Popen", launch)
    monkeypatch.setattr(integrity, "_exception_metadata", observe)
    monkeypatch.setattr(integrity, "_stop_child", stop)
    caplog.set_level("DEBUG", logger=integrity.__name__)
    try:
        arguments = {
            "provenance": {"sha256": hashlib.sha256(candidate.read_bytes()).hexdigest()}
        }
        if primary_type is KeyboardInterrupt:
            with pytest.raises(KeyboardInterrupt) as caught:
                integrity.probe_native_grammar(candidate, "test", **arguments)
            assert caught.value is primary
            assert traceback.extract_tb(primary.__traceback__)[-1].name == "launch"
        else:
            result = integrity.probe_native_grammar(candidate, "test", **arguments)
            assert result == integrity.NativeProbeResult(False, "child_failed", None)
        observations = [
            record.native_probe_diagnostic
            for record in caplog.records
            if hasattr(record, "native_probe_diagnostic")
        ]
        assert len(observations) == 1
        assert observations[0]["exception"]["operation"] == "launch"
        assert observations[0]["exception"].get("type") in {
            None,
            primary_type.__name__,
        }
        assert len(states) == 1 and not states[0].cleanup_safe
        assert states[0].worker is None and not states[0].start_attempted
        assert roots[0].exists(), "uncertainty must retain the root"
    finally:
        # Popen was replaced before creating a process; these roots are fixture-owned.
        for root in roots:
            remove_retained_probe_root(root)


def test_native_failure_diagnostics_bound_traceback_without_reading_source():
    from chunker.grammar import integrity

    def recurse(depth):
        if depth:
            return recurse(depth - 1)
        raise PermissionError(13, "private error text", "/private/filename")

    try:
        recurse(20)
    except PermissionError as error:
        diagnostic = integrity._exception_metadata(error)
    assert diagnostic["errno"] == 13 and diagnostic["winerror"] is None
    assert len(diagnostic["frames"]) == 6
    assert all(frame["function"] == "recurse" for frame in diagnostic["frames"])
    assert "private" not in json.dumps(diagnostic)

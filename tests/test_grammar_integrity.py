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

    sentinel = subprocess.Popen(
        [sys.executable, "-I", "-c", "import time; time.sleep(60)"]
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
    roots = []
    original = integrity._read_child

    def invalid(command, cwd, timeout, **kwargs):
        roots.append(cwd)
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
            [sys.executable, "-I", "-c", "import time; time.sleep(60)"],
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
    finally:
        sentinel.kill()
        sentinel.wait(timeout=10)
        for root in roots:
            if root.exists():
                integrity.shutil.rmtree(root)


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
            identity = psutil.Process(int(marker.read_text()))
            identity.kill()
            identity.wait(timeout=10)
        if observer is not None:
            observer.close()
        for root in roots:
            if root.exists():
                integrity.shutil.rmtree(root)


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
            [sys.executable, "-I", "-c", "import time; time.sleep(60)"], **kwargs
        )

    def read(command, cwd, timeout, **kwargs):
        roots.append(cwd)
        states.append(kwargs["lifecycle"])
        return original_read(
            command, cwd, 0.1 if stage == "wait" else timeout, **kwargs
        )

    def ready(*args):
        if stage in {"cancel", "second_interrupt", "read"}:
            raise injected
        if stage == "access":
            raise PermissionError("registration access denied")
        return real_ready(*args)

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
        assert roots[0].exists()
        gc.collect()
        assert roots[0].exists()
    finally:
        import psutil

        process = states[0].launcher
        if process is not None:
            # Emergency cleanup follows every assertion and supplies none of its values.
            children = [p for pid, p in states[0].known.items() if pid != process.pid]
            if process.poll() is None:
                for child in psutil.Process(process.pid).children(recursive=True):
                    if child not in children:
                        children.append(child)
            for child in children:
                try:
                    child.kill()
                except psutil.NoSuchProcess:
                    pass
            if process.poll() is None:
                process.kill()
            process.wait(timeout=10)
            _, alive = psutil.wait_procs(children, timeout=10)
            assert not alive, "emergency fixture children remain alive"
        for root in roots:
            if root.exists():
                integrity.shutil.rmtree(root)


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
                integrity.shutil.rmtree(root)

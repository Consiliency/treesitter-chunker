"""Native probe fixtures own process lifetimes and publication barriers."""

import sys
import time
import json
import subprocess
from pathlib import Path
import pytest

pytestmark = pytest.mark.usefixtures("native_probe_lifetimes")
import psutil
from chunker.grammar import integrity
from tests.test_grammar_integrity import (
    test_native_invalid_registration_never_targets_unrelated_pid as exercise,
)
from tests.test_compiled_grammar_analysis_contract import (
    _wait_for_file,
    _NativeObserver,
)


@pytest.mark.skipif(
    sys.platform != "win32", reason="Windows current-directory sharing contract"
)
@pytest.mark.parametrize(
    "fixture", ["invalid_registration", "invalid_ready", "lifecycle_read"]
)
def test_invalid_registration_fixture_owns_its_directory_holder(
    tmp_path, monkeypatch, fixture
):
    real_popen = subprocess.Popen
    real_discover = integrity._discover
    go, marker = tmp_path / "spawn", tmp_path / "actual-worker"
    released = tmp_path / "release"
    captured = {"observer": None, "root": None, "calls": 0, "worker": None}
    worker = (
        "import os,time,json; from pathlib import Path; "
        f'p=Path({str(marker)!r}); q=p.with_suffix(".tmp"); '
        'q.write_text(json.dumps({"pid":os.getpid(),"ppid":os.getppid()}),encoding="utf-8"); q.replace(p); '
        f"r=Path({str(released)!r}); "
        "\nwhile not r.exists(): time.sleep(0.01)\n"
    )
    launcher = (
        "import subprocess,sys,time; from pathlib import Path; "
        f"p=Path({str(go)!r}); "
        "\nwhile not p.exists(): time.sleep(0.01)\n"
        f'child=subprocess.Popen([sys.executable,"-I","-c",{worker!r}]); child.wait()'
    )

    def popen(command, *args, **kwargs):
        if command[0] == sys.executable and kwargs.get("cwd") is not None:
            captured["root"] = Path(kwargs["cwd"])
            return real_popen(
                [sys._base_executable, "-I", "-c", launcher], *args, **kwargs
            )
        # Keep the unrelated sentinel direct, so its fixture teardown owns it.
        if command[0] == sys.executable:
            command = [sys._base_executable, *command[1:]]
        return real_popen(command, *args, **kwargs)

    def discover(state):
        real_discover(state)
        captured["calls"] += 1
        if captured["root"] is not None and captured["calls"] == 2:
            assert set(state.known) == {state.launcher.pid}
            go.touch()
            _wait_for_file(marker, state.launcher, timeout=10)
            record = json.loads(marker.read_text(encoding="utf-8"))
            child = psutil.Process(record["pid"])
            child.create_time()
            assert child.ppid() == state.launcher.pid == record["ppid"]
            captured["worker"] = child
            captured["observer"] = _NativeObserver(child.pid, None)
            print(
                json.dumps(
                    {
                        "known_pids": list(state.known),
                        "launcher": state.launcher.pid,
                        "actual_worker": child.pid,
                        "worker_alive_before_stop": captured["observer"].alive(),
                    }
                ),
                flush=True,
            )

    monkeypatch.setattr(subprocess, "Popen", popen)
    monkeypatch.setattr(integrity, "_discover", discover)
    try:
        if fixture == "invalid_registration":
            exercise(tmp_path, monkeypatch, "ppid_bool")
        else:
            from tests import test_grammar_integrity as grammar

            if fixture == "invalid_ready":
                grammar.test_native_windows_ready_open_recovery_keeps_invalid_record_rejected(
                    tmp_path, monkeypatch, "nonce"
                )
            else:
                grammar.test_native_lifecycle_faults_retain_unsafe_root(
                    tmp_path, monkeypatch, "read"
                )
    finally:
        released.touch()
        if captured["observer"] is not None:
            observer = captured["observer"]
            assert observer.api.WaitForSingleObject(observer.handle, 10000) == 0
            assert not observer.alive()
            observer.close()
        if captured["root"] is not None and captured["root"].exists():
            integrity.shutil.rmtree(captured["root"])
            assert not captured["root"].exists()


@pytest.mark.skipif(
    sys.platform != "win32", reason="Windows mapped-file deletion contract"
)
def test_registered_fault_fixture_reaps_its_mapped_file_owner(tmp_path, monkeypatch):
    import sysconfig
    from tests import test_compiled_grammar_analysis_contract as compiled
    from tests.native_probe_lifetime import ProbeLifetimes

    real_wait = ProbeLifetimes.wait

    def release_before_wait(self, root, timeout=10):
        # This worker intentionally ignores product stop. Release the fixture's
        # barrier only when teardown reaches its identity-bound wait; the old
        # unlink-without-wait control still fails with the DLL mapped.
        if root == owned["root"]:
            release.touch()
        return real_wait(self, root, timeout)

    monkeypatch.setattr(ProbeLifetimes, "wait", release_before_wait)

    real_read, real_popen, real_register = (
        integrity._read_child,
        subprocess.Popen,
        integrity._register_worker,
    )
    marker, release = tmp_path / "mapped", tmp_path / "release-mapping"
    owned = {"worker": None, "creation": None, "root": None}
    # Hold a successfully loaded DLL after registration; this control requires
    # actual native entry and cannot count a failed load as coverage.
    mapping_code = f"""
import sys, time, json
from pathlib import Path
sys.path.insert(0, {sysconfig.get_path('purelib')!r})
sys.path.insert(0, sys.argv[1])
from chunker.grammar.integrity import _worker_ready, verify_artifact
from chunker.grammar_management.core import load_compiled_grammar
snapshot = Path(sys.argv[2])
_worker_ready(snapshot.parent, sys.argv[-1])
verify_artifact(snapshot, {{'sha256': sys.argv[4]}})
parser = load_compiled_grammar(snapshot, sys.argv[3])
assert parser.parse(b'').root_node.type == 'source_file'
p=Path({str(marker)!r}); q=p.with_suffix('.tmp'); q.write_text('mapped',encoding='utf-8'); q.replace(p)
while not Path({str(release)!r}).exists(): time.sleep(0.01)
"""
    launcher_code = (
        "import subprocess,sys; child=subprocess.Popen([sys.executable,*sys.argv[1:]], "
        "stdin=sys.stdin.buffer, stdout=sys.stdout.buffer, stderr=sys.stderr.buffer); raise SystemExit(child.wait())"
    )

    class StartWriter:
        def __init__(self, stream, process):
            self.stream, self.process, self.waited = stream, process, False

        def __getattr__(self, name):
            return getattr(self.stream, name)

        def close(self):
            self.stream.close()
            if not self.waited:
                self.waited = True
                deadline = time.monotonic() + 10
                while not marker.exists():
                    if self.process.poll() is not None:
                        stdout, stderr = self.process.communicate(timeout=5)
                        raise AssertionError(f"worker did not load the DLL: {stderr!r}")
                    assert (
                        time.monotonic() < deadline
                    ), "worker did not reach the mapped-DLL barrier"
                    time.sleep(0.01)

    def popen(command, *args, **kwargs):
        process = real_popen(command, *args, **kwargs)
        if kwargs.get("cwd") is not None and Path(kwargs["cwd"]).name.startswith(
            "chunker-native-probe-"
        ):
            process.stdin = StartWriter(process.stdin, process)
        return process

    def register(state, record):
        real_register(state, record)
        owned.update(worker=state.worker, creation=record["windows_creation_filetime"])

    def read(command, cwd, timeout, **kwargs):
        owned["root"] = cwd
        command = list(command)
        command[3] = mapping_code
        return real_read(
            [sys._base_executable, "-I", "-c", launcher_code, *command[1:]],
            cwd,
            timeout,
            **kwargs,
        )

    def unconfirmed_stop(state):
        # Model a permitted uncertain stop: the launcher died, while the actual
        # registered worker is still alive. Production must retain its root.
        state.cleanup_safe = False
        assert state.launcher.pid != state.worker.pid
        if state.launcher.poll() is None:
            state.launcher.terminate()
        state.launcher.wait(timeout=10)

    monkeypatch.setattr(subprocess, "Popen", popen)
    monkeypatch.setattr(integrity, "_register_worker", register)
    monkeypatch.setattr(integrity, "_read_child", read)
    monkeypatch.setattr(integrity, "_stop_child", unconfirmed_stop)
    try:
        compiled.test_native_registered_read_fault_retains_root_and_original_exception(
            tmp_path, monkeypatch, KeyboardInterrupt
        )
        assert marker.exists()
        assert not owned["root"].exists()
    finally:
        # Own the deliberately surviving process even when exercising the old
        # fixture as a mutation. Bind its identity before allowing it to exit.
        worker = owned["worker"]
        observer = (
            _NativeObserver(worker.pid, owned["creation"])
            if worker is not None and worker.is_running()
            else None
        )
        release.touch()
        if observer is not None:
            assert observer.api.WaitForSingleObject(observer.handle, 10000) == 0
            assert not observer.alive()
            observer.close()
        if owned["root"] is not None and owned["root"].exists():
            integrity.shutil.rmtree(owned["root"])


@pytest.mark.skipif(
    sys.platform != "win32", reason="Windows exclusive publication handle"
)
def test_native_marker_consumer_waits_for_publication_completion(tmp_path, monkeypatch):
    """A visible marker remains unreadable until the publisher releases it."""
    from tests import test_compiled_grammar_analysis_contract as compiled

    original_compile, original_wait = (
        compiled._compile_probe_fixture,
        compiled._wait_for_file,
    )
    unlock = tmp_path / "unlock-publication"
    held_prefix = tmp_path / "publication-held"
    owners = []
    model = r"""
    HANDLE publishing = CreateFileA(marker_path, GENERIC_READ, 0, NULL, OPEN_EXISTING, 0, NULL);
    if (publishing == INVALID_HANDLE_VALUE) abort();
    char held_path[32768];
    snprintf(held_path, sizeof(held_path), "%s.%ld", HELD_PREFIX, (long)PID);
    FILE *held_signal = fopen(held_path, "wb");
    if (!held_signal || fputc('1', held_signal) == EOF || fclose(held_signal)) abort();
    while (GetFileAttributesA(UNLOCK_PATH) == INVALID_FILE_ATTRIBUTES) PAUSE();
    if (!CloseHandle(publishing)) abort();
""".replace(
        "HELD_PREFIX", json.dumps(str(held_prefix))
    ).replace(
        "UNLOCK_PATH", json.dumps(str(unlock))
    )

    def compile_fixture(directory, sources):
        code = sources[0]
        source = code.read_text(encoding="utf-8")
        point = "if (fclose(marker) || rename(pending, marker_path)) abort();"
        assert point in source
        code.write_text(source.replace(point, point + model), encoding="utf-8")
        return original_compile(directory, sources)

    def wait(path, process=None, timeout=45):
        if path.name in {"opened", "opened-published"} and not owners:
            deadline = time.monotonic() + timeout
            while not (signals := list(tmp_path.glob(held_prefix.name + ".*"))):
                if process.poll() is not None:
                    return original_wait(path, process, timeout)
                assert (
                    time.monotonic() < deadline
                ), "publisher never acquired its handle"
                time.sleep(0.01)
            assert len(signals) == 1
            owners.append(_NativeObserver(int(signals[0].suffix[1:]), None))
            assert (tmp_path / "opened").exists()
            assert not (tmp_path / "opened-published").exists()
            with pytest.raises(PermissionError):
                (tmp_path / "opened").read_bytes()
            # An old consumer proceeds from visibility while the publisher still
            # owns its exclusive handle. The completion consumer waits for release.
            if path.name == "opened-published":
                unlock.touch()
        return original_wait(path, process, timeout)

    monkeypatch.setattr(compiled, "_compile_probe_fixture", compile_fixture)
    monkeypatch.setattr(compiled, "_wait_for_file", wait)
    try:
        compiled.test_native_probe_worker_exits_before_snapshot_cleanup(
            tmp_path, "stderr_overflow"
        )
        assert owners and not owners[0].alive()
    finally:
        unlock.touch()
        for owner in owners:
            if owner.alive():
                owner.process.kill()
                assert owner.api.WaitForSingleObject(owner.handle, 10000) == 0
            assert not owner.alive()
            owner.close()
        marker = tmp_path / "opened"
        if owners and marker.exists():
            root = Path(marker.read_text(encoding="utf-8").splitlines()[1]).parent
            if root.exists():
                integrity.shutil.rmtree(root)


def test_retained_probe_deadline_names_live_pid_and_keeps_root(tmp_path):
    from tests.native_probe_lifetime import ProbeLifetimes

    root = tmp_path / "retained"
    root.mkdir()
    process = subprocess.Popen(
        [sys._base_executable, "-I", "-c", "import time; time.sleep(60)"]
    )
    owners = ProbeLifetimes()
    owners.launchers[root] = [process]
    try:
        with pytest.raises(AssertionError, match=rf"PID\(s\).*{process.pid}.*root="):
            owners.wait(root, timeout=0)
        assert root.exists() and process.poll() is None
    finally:
        # The control deliberately creates a survivor; only after proving the
        # required failure do we release its own process and confirm exit.
        process.kill()
        process.wait(timeout=10)


def test_fault_launcher_preserves_real_child_failure(tmp_path, monkeypatch):
    from tests import test_compiled_grammar_analysis_contract as compiled

    original = integrity._read_child
    replies, states = [], []

    def invalid_image(directory, sources):
        candidate = directory / "invalid.dll"
        candidate.write_bytes(b"reviewed invalid native image; cannot execute")
        return candidate

    def observe(*args, **kwargs):
        reply = original(*args, **kwargs)
        replies.append(reply)
        states.append(kwargs["lifecycle"])
        return reply

    monkeypatch.setattr(compiled, "_compile_probe_fixture", invalid_image)
    monkeypatch.setattr(integrity, "_read_child", observe)
    with pytest.raises(AssertionError):
        compiled.test_native_valid_ack_abnormal_worker_launcher_zero(
            tmp_path, monkeypatch
        )
    assert len(replies) == len(states) == 1
    assert states[0].worker_status == 1 and replies[0][0] == 1
    assert json.loads(replies[0][1])["failure"] == "load_failed"
    assert not replies[0][3] and not replies[0][4]

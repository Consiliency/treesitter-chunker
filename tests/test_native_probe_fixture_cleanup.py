"""Native probe fixtures own process lifetimes and publication barriers."""

import sys
import time
import json
import subprocess
from pathlib import Path
import pytest

pytestmark = pytest.mark.usefixtures(
    "native_probe_lifetimes", "native_policy_environment"
)
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
            assert (
                observer.api.WaitForSingleObject(observer.handle, 10000) == 0
            ), f"Retained probe PID {observer.process.pid} outlived teardown deadline"
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
from chunker.grammar._native_policy import NativePolicyBlockedError
from chunker.grammar_management.core import load_compiled_grammar
snapshot = Path(sys.argv[2])
_worker_ready(snapshot.parent, sys.argv[-1])
verify_artifact(snapshot, {{'sha256': sys.argv[4]}})
try:
    parser = load_compiled_grammar(snapshot, sys.argv[3])
except NativePolicyBlockedError as error:
    print(json.dumps({{'schema': 'native_test.policy.v1', 'winerror': error.winerror}}), flush=True)
    raise SystemExit(77)
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
                from types import SimpleNamespace
                from tests.native_policy import skip_policy_subprocess

                deadline = time.monotonic() + 10
                while not marker.exists():
                    if self.process.poll() is not None:
                        stdout, stderr = self.process.communicate(timeout=5)
                        skip_policy_subprocess(
                            SimpleNamespace(
                                returncode=self.process.returncode, stdout=stdout
                            )
                        )
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
            assert (
                observer.api.WaitForSingleObject(observer.handle, 10000) == 0
            ), f"Retained probe PID {observer.process.pid} outlived teardown deadline"
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
                assert (
                    owner.api.WaitForSingleObject(owner.handle, 10000) == 0
                ), f"Retained probe PID {owner.process.pid} outlived teardown deadline"
            assert not owner.alive()
            owner.close()
        marker = tmp_path / "opened"
        if owners and marker.exists():
            root = Path(marker.read_text(encoding="utf-8").splitlines()[1]).parent
            if root.exists():
                integrity.shutil.rmtree(root)


def _sleeper(*, cwd=None):
    return subprocess.Popen(
        [sys._base_executable, "-I", "-c", "import time; time.sleep(60)"], cwd=cwd
    )


def _release(process):
    # Each control deliberately creates a survivor; only after proving the
    # required failure do we release that process and confirm its exit.
    process.kill()
    process.wait(timeout=10)


def test_retained_probe_deadline_names_live_pid_and_keeps_root(
    tmp_path, native_probe_lifetimes
):
    from tests.native_probe_lifetime import remove_retained_probe_root

    root = tmp_path / "retained"
    root.mkdir()
    process = _sleeper()
    native_probe_lifetimes.launchers[root] = [process]
    try:
        with pytest.raises(AssertionError, match=rf"PID\(s\) \[{process.pid}\].*root="):
            remove_retained_probe_root(root, timeout=0)
        assert root.exists() and process.poll() is None
    finally:
        _release(process)


def test_registered_worker_deadline_names_live_pid_and_keeps_root(
    tmp_path, native_probe_lifetimes
):
    from tests.native_probe_lifetime import (
        remove_retained_probe_root,
        retain_probe_observer,
    )

    root = tmp_path / "chunker-native-probe-registered"
    root.mkdir()
    process = _sleeper()
    try:
        # The same identity-bound observer type the fixture acquires before
        # START: a Windows process HANDLE, or a psutil (PID, creation) identity.
        observer = _NativeObserver(process.pid, None)
        assert (observer.handle is not None) == (sys.platform == "win32")
        retain_probe_observer(root, observer)
        assert not native_probe_lifetimes.launchers.get(root)
        with pytest.raises(AssertionError, match=rf"PID\(s\) \[{process.pid}\].*root="):
            remove_retained_probe_root(root, timeout=0)
        assert root.exists() and observer.alive()
    finally:
        _release(process)


def test_discovered_descendant_outliving_noop_stop_is_named(
    tmp_path, monkeypatch, native_probe_lifetimes
):
    """A product-discovered, never-registered descendant blocks root removal."""
    from tests.native_probe_lifetime import remove_retained_probe_root

    root = tmp_path / "chunker-native-probe-discovered"
    root.mkdir()
    marker, discovered = tmp_path / "descendant", tmp_path / "discovered"
    published, release = tmp_path / "descendant-published", tmp_path / "release"
    descendant = (
        "import os,time; from pathlib import Path; "
        f"p=Path({str(marker)!r}); q=p.with_suffix('.tmp'); "
        "q.write_text(str(os.getpid()),encoding='utf-8'); q.replace(p); "
        # Visibility is not completion on Windows: signal after replace returns.
        f"Path({str(published)!r}).touch(); "
        f"r=Path({str(release)!r}); deadline=time.monotonic()+60"
        "\nwhile not r.exists() and time.monotonic() < deadline: time.sleep(0.01)\n"
    )
    # The launcher exits by itself once the product has discovered its child
    # (or the control releases it); the child keeps no product pipe, so the
    # read loop ends on launcher exit.
    launcher = (
        "import subprocess,sys,time; from pathlib import Path; "
        f"subprocess.Popen([sys.executable,'-I','-c',{descendant!r}], "
        "stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); "
        f"p=Path({str(discovered)!r}); r=Path({str(release)!r}); "
        "deadline=time.monotonic()+30"
        "\nwhile not (p.exists() or r.exists()) and time.monotonic() < deadline:"
        " time.sleep(0.01)\n"
    )
    stops, real_discover = [], integrity._discover

    def discover(state):
        real_discover(state)
        if (
            published.exists()
            and int(marker.read_text(encoding="utf-8")) in state.known
        ):
            discovered.touch()

    def noop_stop(state):
        # A permitted uncertain stop that signals nothing.
        stops.append(state)
        state.cleanup_safe = False

    monkeypatch.setattr(integrity, "_discover", discover)
    monkeypatch.setattr(integrity, "_stop_child", noop_stop)
    pid = None
    try:
        reply = integrity._read_child(
            [sys._base_executable, "-I", "-c", launcher], root, 30
        )
        assert reply[0] == 0 and not reply[3] and not reply[4], reply
        assert discovered.exists() and len(stops) == 1
        pid = int(marker.read_text(encoding="utf-8"))
        assert set(stops[0].known) == {stops[0].launcher.pid, pid}
        assert stops[0].launcher.poll() == 0
        with pytest.raises(AssertionError, match=rf"PID\(s\) \[{pid}\].*root="):
            remove_retained_probe_root(root, timeout=0)
        assert root.exists()
        assert psutil.Process(pid) == stops[0].known[pid]
    finally:
        # The fixture's identity-bound teardown wait confirms this exit.
        release.touch()


def test_fault_launcher_maps_only_injected_exit_7(tmp_path):
    from tests.test_compiled_grammar_analysis_contract import (
        _write_fault_launcher,
    )

    launcher, injected = _write_fault_launcher(tmp_path)

    def status(code):
        return subprocess.run(
            [sys._base_executable, "-I", str(launcher), "-I", "-c", code],
            stdin=subprocess.DEVNULL,
            timeout=30,
        ).returncode

    # A genuine child exit 7, without the injecting worker's sentinel, is kept.
    assert status("raise SystemExit(7)") == 7
    assert status("raise SystemExit(1)") == 1
    assert not injected.exists()
    inject = f"open({str(injected)!r}, 'x').close(); raise SystemExit(7)"
    assert status(inject) == 0 and injected.exists()


def test_fixture_popen_type_and_bookkeeping_stay_out_of_product(
    tmp_path, native_probe_lifetimes
):
    from tests.native_probe_lifetime import remove_retained_probe_root

    # The fixture installs a real Popen subclass, not a replacement function.
    assert isinstance(subprocess.Popen, type)
    assert subprocess.Popen.__mro__[1].__name__ == "Popen"
    assert subprocess.Popen[bytes] is not None
    root = tmp_path / "chunker-native-probe-recorded"
    root.mkdir()
    process = _sleeper(cwd=root)
    try:
        assert isinstance(process, subprocess.Popen)
        assert native_probe_lifetimes.launchers[root] == [process]

        class BrokenIdentity:
            def create_time(self):
                raise RuntimeError("fixture bookkeeping fault")

        state = integrity._ProbeLifecycle(native=False)
        state.launcher = process
        state.known = {process.pid: psutil.Process(process.pid), -1: BrokenIdentity()}
        # A fixture failure is recorded for teardown, never raised in product flow.
        integrity._discover(state)
        assert native_probe_lifetimes.fixture_errors == [
            "retain discovered identities: RuntimeError: fixture bookkeeping fault"
        ]
        native_probe_lifetimes.fixture_errors.clear()
    finally:
        _release(process)
    remove_retained_probe_root(root, timeout=0)
    assert not root.exists()


def test_pending_bookkeeping_error_keeps_root_and_names_cause(
    tmp_path, native_probe_lifetimes
):
    from tests.native_probe_lifetime import remove_retained_probe_root

    root = tmp_path / "chunker-native-probe-bookkeeping"
    root.mkdir()
    native_probe_lifetimes.fixture_errors.append("control: lost observer")
    with pytest.raises(
        AssertionError, match=r"bookkeeping failed: \['control: lost observer'\]"
    ):
        remove_retained_probe_root(root, timeout=0)
    assert root.exists()
    native_probe_lifetimes.fixture_errors.clear()
    remove_retained_probe_root(root, timeout=0)
    assert not root.exists()


def test_finish_raises_recorded_bookkeeping_errors():
    from tests.native_probe_lifetime import ProbeLifetimes

    clean = ProbeLifetimes()
    clean.finish()
    owners = ProbeLifetimes()
    owners.fixture_errors.append("control: unrecorded launcher")
    with pytest.raises(
        AssertionError,
        match=r"bookkeeping failed: \['control: unrecorded launcher'\]",
    ):
        owners.finish()


def test_fixture_prefix_matches_real_product_probe_root(
    tmp_path, monkeypatch, native_probe_lifetimes
):
    """Read the probe-root prefix from a real product launch, not a copy."""
    import hashlib
    from tests.native_probe_lifetime import PROBE_ROOT_PREFIX

    candidate = tmp_path / ("invalid" + (".dll" if sys.platform == "win32" else ".so"))
    candidate.write_bytes(b"reviewed invalid native image; cannot execute")
    original, roots = integrity._read_child, []

    def observe(command, cwd, timeout, **kwargs):
        roots.append(Path(cwd))
        return original(command, cwd, timeout, **kwargs)

    monkeypatch.setattr(integrity, "_read_child", observe)
    result = integrity.probe_native_grammar(
        candidate,
        "baml",
        provenance={"sha256": hashlib.sha256(candidate.read_bytes()).hexdigest()},
    )
    assert not result.supported, result
    assert len(roots) == 1, roots
    # The product's real snapshot root carries the prefix the fixture records
    # by, and the fixture actually retained that launcher for its waits.
    assert roots[0].name.startswith(PROBE_ROOT_PREFIX), roots[0]
    assert len(native_probe_lifetimes.launchers.get(roots[0], [])) == 1


def test_fault_launcher_preserves_real_child_failure(tmp_path, monkeypatch):
    from tests import test_compiled_grammar_analysis_contract as compiled

    original = integrity._read_child
    replies, states = [], []

    def invalid_image(directory, sources):
        candidate = directory / "invalid.dll"
        candidate.write_bytes(b"reviewed invalid native image; cannot execute")
        return candidate

    def observe(*args, **kwargs):
        states.append(kwargs["lifecycle"])
        reply = original(*args, **kwargs)
        replies.append(reply)
        return reply

    monkeypatch.setattr(compiled, "_compile_probe_fixture", invalid_image)
    monkeypatch.setattr(integrity, "_read_child", observe)
    if sys.platform != "win32":
        # POSIX correctly rejects this distinct-worker launcher before START.
        # Preserve that protocol assertion instead of requiring native entry.
        compiled.test_native_valid_ack_abnormal_worker_launcher_zero(
            tmp_path, monkeypatch
        )
        assert len(states) == 1 and not replies
        assert states[0].worker is None and not states[0].start_attempted
        assert states[0].exception["type"] == "ValueError"
        assert states[0].exception["operation"] == "register_worker"
        return
    with pytest.raises(AssertionError):
        compiled.test_native_valid_ack_abnormal_worker_launcher_zero(
            tmp_path, monkeypatch
        )
    assert len(replies) == len(states) == 1
    assert states[0].worker_status == 1 and replies[0][0] == 1
    assert json.loads(replies[0][1])["failure"] == "load_failed"
    assert not replies[0][3] and not replies[0][4]

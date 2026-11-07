"""Test-owned process lifetimes; never authorize product cleanup or admission."""

from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
import shutil
import subprocess
import time

import psutil
import pytest


_current = ContextVar("native_probe_lifetimes", default=None)
# The product inlines this mkdtemp prefix and exports no constant. The control
# test_fixture_prefix_matches_real_product_probe_root reads it from a real
# product launch, so a product rename fails loudly instead of emptying waits.
PROBE_ROOT_PREFIX = "chunker-native-probe-"


def _identity_alive(process):
    """psutil compares (PID, creation time); a reused PID is not this process."""
    try:
        return process.is_running() and process.status() != psutil.STATUS_ZOMBIE
    except psutil.NoSuchProcess:
        return False


class ProbeLifetimes:
    def __init__(self):
        self.launchers = {}
        self.workers = {}
        # Every identity the product discovered under a tracked launcher,
        # including descendants rejected before (or never offered for)
        # registration. Keyed by (PID, creation time) to keep incarnations apart.
        self.discovered = {}
        self.fixture_errors = []

    def roots(self):
        return self.launchers.keys() | self.workers.keys() | self.discovered.keys()

    def root_for(self, launcher):
        roots = [
            root
            for root, processes in self.launchers.items()
            if any(process is launcher for process in processes)
        ]
        assert len(roots) <= 1, roots
        return roots[0] if roots else None

    @contextmanager
    def bookkeeping(self, operation):
        """Fixture failures fail teardown; they never become product exceptions."""
        try:
            yield
        except Exception as error:
            self.fixture_errors.append(f"{operation}: {type(error).__name__}: {error}")

    def retain_discovered(self, state):
        root = self.root_for(state.launcher) if state.launcher is not None else None
        if root is None:
            return
        retained = self.discovered.setdefault(root, {})
        for pid, process in list(state.known.items()):
            if pid == state.launcher.pid:
                continue  # The retained Popen owns the launcher's identity.
            # The product captured creation time before retaining this object;
            # keep that same identity rather than reopening its PID later.
            retained.setdefault((pid, process.create_time()), process)

    def _bookkeeping_failure(self, root=None):
        where = f"; root={root}. Root retained" if root is not None else ""
        return f"Native probe fixture bookkeeping failed: {self.fixture_errors}{where}"

    def wait(self, root, timeout=10):
        """One bounded deadline; retain handles until every wait completes."""
        root = Path(root)
        # Incomplete bookkeeping may hide an owner: keep the root and report
        # the real cause, before any wait or removal can proceed.
        assert not self.fixture_errors, self._bookkeeping_failure(root)
        deadline = time.monotonic() + timeout
        pending = []
        for process in self.launchers.get(root, []):
            # Popen retains the original Windows process HANDLE (and the child
            # identity for waitpid on POSIX); never reopen a PID during teardown.
            try:
                process.wait(timeout=max(0, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                pending.append(process.pid)
        for owner in self.workers.get(root, []):
            if owner.handle is not None:
                remaining = max(0, int((deadline - time.monotonic()) * 1000))
                result = owner.api.WaitForSingleObject(owner.handle, remaining)
                assert result in {0, 258}, owner.ctypes.get_last_error()
                if result == 258:
                    pending.append(owner.process.pid)
            else:
                # psutil's retained identity includes creation time. Its
                # is_running check rejects PID reuse; no fresh PID lookup.
                while owner.alive() and time.monotonic() < deadline:
                    time.sleep(min(0.01, max(0, deadline - time.monotonic())))
                if owner.alive():
                    pending.append(owner.process.pid)
        for process in self.discovered.get(root, {}).values():
            while _identity_alive(process) and time.monotonic() < deadline:
                time.sleep(min(0.01, max(0, deadline - time.monotonic())))
            if _identity_alive(process):
                pending.append(process.pid)
        assert not pending, (
            f"Retained native probe outlived {timeout:g}s teardown deadline: "
            f"PID(s) {sorted(set(pending))}; root={root}. "
            "Possible product process leak; root retained."
        )

    def finish(self):
        """Teardown check: recorded bookkeeping failures fail the test."""
        assert not self.fixture_errors, self._bookkeeping_failure()

    def close(self):
        for owners in self.workers.values():
            for owner in owners:
                owner.close()


def retain_probe_observer(root, owner):
    """Transfer a test-owned observer before injecting registration failure."""
    owners = _current.get()
    assert owners is not None, "observer transfer requires native_probe_lifetimes"
    owners.workers.setdefault(Path(root), []).append(owner)


def remove_retained_probe_root(root, *, timeout=10, remover=None):
    owners = _current.get()
    assert owners is not None, "retained-root teardown requires native_probe_lifetimes"
    owners.wait(root, timeout)
    (remover or shutil.rmtree)(root)


@pytest.fixture
def native_probe_lifetimes(monkeypatch):
    from chunker.grammar import integrity
    from tests.test_compiled_grammar_analysis_contract import _NativeObserver

    owners = ProbeLifetimes()
    token = _current.set(owners)
    original_register, original_discover = (
        integrity._register_worker,
        integrity._discover,
    )

    class RecordingPopen(subprocess.Popen):
        """A real Popen type; only records launches whose cwd is a probe root."""

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            with owners.bookkeeping("record launcher"):
                cwd = kwargs.get("cwd")
                if cwd is not None and Path(cwd).name.startswith(PROBE_ROOT_PREFIX):
                    owners.launchers.setdefault(Path(cwd), []).append(self)

    def register(state, record):
        original_register(state, record)
        with owners.bookkeeping("acquire registered worker observer"):
            root = owners.root_for(state.launcher)
            if root is None:
                # Synthetic registration controls construct their own state
                # without launching a probe; their fake identity stays untouched.
                return
            # Acquisition is before START, while the validated worker is alive.
            owner = _NativeObserver(
                state.worker.pid, record["windows_creation_filetime"]
            )
            owners.workers.setdefault(root, []).append(owner)

    def discover(state):
        try:
            original_discover(state)
        finally:
            with owners.bookkeeping("retain discovered identities"):
                owners.retain_discovered(state)

    monkeypatch.setattr(subprocess, "Popen", RecordingPopen)
    monkeypatch.setattr(integrity, "_register_worker", register)
    monkeypatch.setattr(integrity, "_discover", discover)
    try:
        yield owners
    finally:
        try:
            try:
                for root in owners.roots():
                    owners.wait(root)
            finally:
                owners.finish()
        finally:
            owners.close()
            _current.reset(token)

"""Test-owned process lifetimes; never authorize product cleanup or admission."""

from contextvars import ContextVar
from pathlib import Path
import shutil
import subprocess
import time

import pytest


_current = ContextVar("native_probe_lifetimes", default=None)


class ProbeLifetimes:
    def __init__(self):
        self.launchers = {}
        self.workers = {}

    def wait(self, root, timeout=10):
        """One bounded deadline; retain handles until every wait completes."""
        root = Path(root)
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
        assert not pending, (
            f"Retained native probe outlived {timeout:g}s teardown deadline: "
            f"PID(s) {sorted(set(pending))}; root={root}. "
            "Possible product process leak; root retained."
        )

    def close(self):
        for owners in self.workers.values():
            for owner in owners:
                owner.close()


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
    original_popen, original_register = subprocess.Popen, integrity._register_worker

    def popen(*args, **kwargs):
        process = original_popen(*args, **kwargs)
        cwd = kwargs.get("cwd")
        if cwd is not None and Path(cwd).name.startswith("chunker-native-probe-"):
            owners.launchers.setdefault(Path(cwd), []).append(process)
        return process

    def register(state, record):
        original_register(state, record)
        roots = [
            root
            for root, processes in owners.launchers.items()
            if state.launcher in processes
        ]
        if not roots:
            # Synthetic registration controls construct their own state without
            # launching a probe; their fake OS identity must remain untouched.
            return
        assert len(roots) == 1
        # Acquisition is before START, while the validated worker must be alive.
        owner = _NativeObserver(state.worker.pid, record["windows_creation_filetime"])
        owners.workers.setdefault(roots[0], []).append(owner)

    monkeypatch.setattr(subprocess, "Popen", popen)
    monkeypatch.setattr(integrity, "_register_worker", register)
    try:
        yield owners
    finally:
        try:
            for root in owners.launchers.keys() | owners.workers.keys():
                owners.wait(root)
        finally:
            owners.close()
            _current.reset(token)

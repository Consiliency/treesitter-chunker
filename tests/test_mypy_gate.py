"""A crashed checker must never pass or erase the tracked type-debt baseline."""

import subprocess
import sys

import pytest

from scripts import mypy_gate


@pytest.mark.parametrize(
    ("returncode", "stdout", "stderr"),
    [
        (1, "", "ModuleNotFoundError: No module named 'mypy'"),
        (2, "chunker/example.py:1: error: invalid configuration", ""),
        (0, "", "checker failed unexpectedly"),
    ],
)
def test_failed_checker_cannot_update_baseline(
    monkeypatch, tmp_path, returncode, stdout, stderr
):
    baseline = tmp_path / "baseline.txt"
    baseline.write_text("existing debt\n", encoding="utf-8")
    monkeypatch.setattr(mypy_gate, "BASELINE", baseline)
    monkeypatch.setattr(
        mypy_gate.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0], returncode, stdout, stderr
        ),
    )
    with pytest.raises(RuntimeError):
        mypy_gate.main(["--update"])
    assert baseline.read_text(encoding="utf-8") == "existing debt\n"


@pytest.mark.parametrize(
    ("returncode", "stdout"), [(0, ""), (1, "x.py:1: error: debt\n")]
)
def test_completed_checker_uses_current_interpreter(monkeypatch, returncode, stdout):
    def run(command, **kwargs):
        assert command[:3] == [sys.executable, "-m", "mypy"]
        return subprocess.CompletedProcess(command, returncode, stdout, "")

    monkeypatch.setattr(mypy_gate.subprocess, "run", run)
    assert mypy_gate._run_mypy() == stdout.splitlines()

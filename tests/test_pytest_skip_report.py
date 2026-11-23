"""Exercise both suite runners against a tiny real pytest target."""

import json
import os
import re
import subprocess
from types import SimpleNamespace

import pytest

from scripts import run_full_suite, run_platform_core


@pytest.mark.parametrize(
    ("runner", "failure", "write_json"),
    [
        (run_full_suite, False, True),
        (run_platform_core, True, True),
        (run_full_suite, False, False),
    ],
    ids=["full-suite", "platform-core-failure", "log-only"],
)
def test_runner_reports_skips(monkeypatch, tmp_path, runner, failure, write_json):
    report = tmp_path / "skips.json"
    if write_json:
        monkeypatch.setenv("CHUNKER_PYTEST_SKIP_REPORT", str(report))
    else:
        monkeypatch.delenv("CHUNKER_PYTEST_SKIP_REPORT", raising=False)
    monkeypatch.setenv("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")
    monkeypatch.delenv("PYTEST_ADDOPTS", raising=False)
    config = tmp_path / "pytest.ini"
    config.write_text("[pytest]\n", encoding="utf-8")
    (tmp_path / "test_collection.py").write_text(
        "import pytest\npytest.skip('collection reason', allow_module_level=True)\n",
        encoding="utf-8",
    )
    target = tmp_path / "test_sample.py"
    target.write_text(
        """import pytest

def test_pass():
    pass

@pytest.mark.skipif(True, reason="hardware: café")
def test_hardware():
    pass

@pytest.fixture
def unavailable():
    pytest.skip("setup reason")

def test_setup(unavailable):
    pass

def test_runtime():
    pytest.skip("runtime reason")

@pytest.mark.parametrize(
    "value",
    [pytest.param(False, marks=pytest.mark.xfail(reason="xfail reason", strict=True))],
)
def test_expected_failure(value):
    assert value
"""
        + ("\ndef test_failure():\n    assert False\n" if failure else ""),
        encoding="utf-8",
    )

    if runner is run_platform_core:
        monkeypatch.setattr("sys.argv", ["runner", "--platform", "macos"])
        original_targets = run_platform_core.tests_for_platform("macos")
    else:
        original_targets = ["tests", "spec_tests"]

    result = None

    def run_tiny_suite(cmd, *, check):
        nonlocal result
        assert cmd[-len(original_targets) :] == original_targets
        result = subprocess.run(
            [
                *cmd[: -len(original_targets)],
                "--color=no",
                "-c",
                str(config),
                str(tmp_path),
            ],
            check=check,
            capture_output=True,
            encoding="utf-8",
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            timeout=30,
        )

        return result

    monkeypatch.setattr(runner, "subprocess", SimpleNamespace(run=run_tiny_suite))
    assert runner.main() == int(failure), result
    assert result is not None
    assert "runtime reason" in result.stdout
    summary = "1 passed, 4 skipped, 1 xfailed"
    if failure:
        summary = f"1 failed, {summary}"
        assert re.search(
            r"^FAILED .*test_sample\.py::test_failure\b",
            result.stdout,
            re.MULTILINE,
        ), result.stdout
    assert re.fullmatch(rf"{summary} in \d+\.\d+s", result.stdout.splitlines()[-1])

    if write_json:
        assert json.loads(report.read_text(encoding="utf-8")) == [
            {"nodeid": "test_collection.py", "reason": "collection reason"},
            {"nodeid": "test_sample.py::test_hardware", "reason": "hardware: café"},
            {"nodeid": "test_sample.py::test_runtime", "reason": "runtime reason"},
            {"nodeid": "test_sample.py::test_setup", "reason": "setup reason"},
        ]
    else:
        assert not report.exists()

"""A crashed checker must never pass or erase the tracked type-debt baseline."""

import json
import os
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


@pytest.mark.parametrize("new_annotation", ["different_class", "list[int]"])
def test_real_checker_distinguishes_wrapped_messages_and_ignores_line_shifts(
    monkeypatch, tmp_path, capsys, new_annotation
):
    monkeypatch.setenv("MYPY_FORCE_TERMINAL_WIDTH", "80")
    existing = "ExistingExpectedValueType" + "Detail" * 16
    different = "DifferentNewExpectedValueType" + "Detail" * 16
    fixture = tmp_path / "fixture.py"
    code = (
        f"class {existing}:\n    pass\n"
        f"class {different}:\n    pass\n"
        f"value: {existing} = 1\n"
    )
    fixture.write_text(code, encoding="utf-8")
    config = tmp_path / "mypy.ini"
    config.write_text(
        "[mypy]\npretty = True\nshow_error_codes = False\nstrict = True\n",
        encoding="utf-8",
    )
    command = [
        sys.executable,
        "-m",
        "mypy",
        str(fixture),
        "--config-file",
        str(config),
        "--no-error-summary",
        "--no-color-output",
        "--cache-dir",
        str(tmp_path / "mypy-cache"),
    ]
    monkeypatch.setattr(mypy_gate, "MYPY_CMD", command)
    baseline = tmp_path / "baseline.txt"
    monkeypatch.setattr(mypy_gate, "BASELINE", baseline)
    pretty_existing = subprocess.run(
        [*command, "--pretty"],
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "MYPY_FORCE_TERMINAL_WIDTH": "80"},
    )
    assert pretty_existing.returncode == 1 and not pretty_existing.stderr
    existing_header = next(
        line for line in pretty_existing.stdout.splitlines() if " error:" in line
    )
    errors = mypy_gate._run_mypy()
    assert len(errors) == 1
    assert existing in errors[0] and errors[0].endswith("[assignment]")
    assert mypy_gate.main(["--update"]) == 0
    accepted = baseline.read_bytes()
    assert mypy_gate.main([]) == 0
    fixture.write_text("\n\n\n" + code, encoding="utf-8")
    assert mypy_gate.main([]) == 0
    assert baseline.read_bytes() == accepted

    capsys.readouterr()
    annotation = different if new_annotation == "different_class" else new_annotation
    fixture.write_text(
        code.replace(f"value: {existing}", f"value: {annotation}"), encoding="utf-8"
    )
    pretty_new = subprocess.run(
        [*command, "--pretty"],
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "MYPY_FORCE_TERMINAL_WIDTH": "80"},
    )
    assert pretty_new.returncode == 1 and not pretty_new.stderr
    new_header = next(
        line for line in pretty_new.stdout.splitlines() if " error:" in line
    )
    assert mypy_gate._signature(existing_header) == mypy_gate._signature(new_header)
    assert mypy_gate.main([]) == 1
    assert annotation in capsys.readouterr().err
    assert baseline.read_bytes() == accepted


@pytest.mark.parametrize(
    ("accepted_literal", "new_literal"),
    [("a:1:", "a:2:"), (r"a\b", "a//b")],
)
def test_real_checker_keeps_literal_values_in_diagnostic_messages(
    monkeypatch, tmp_path, capsys, accepted_literal, new_literal
):
    monkeypatch.setenv("MYPY_FORCE_TERMINAL_WIDTH", "80")
    fixture = tmp_path / "literal_fixture.py"
    config = tmp_path / "mypy.ini"
    config.write_text("[mypy]\nstrict = True\n", encoding="utf-8")
    monkeypatch.setattr(
        mypy_gate,
        "MYPY_CMD",
        [
            sys.executable,
            "-m",
            "mypy",
            str(fixture),
            "--config-file",
            str(config),
            "--cache-dir",
            str(tmp_path / "mypy-cache"),
            "--no-error-summary",
            "--no-color-output",
        ],
    )
    baseline = tmp_path / "baseline.txt"
    monkeypatch.setattr(mypy_gate, "BASELINE", baseline)
    code = (
        "from typing import Literal\n"
        f"value: Literal[{json.dumps(accepted_literal)}] = 'wrong'\n"
    )
    fixture.write_text(code, encoding="utf-8")
    assert mypy_gate.main(["--update"]) == 0
    accepted = baseline.read_bytes()
    assert mypy_gate.main([]) == 0
    fixture.write_text("\n\n\n" + code, encoding="utf-8")
    assert mypy_gate.main([]) == 0
    assert baseline.read_bytes() == accepted
    fixture.write_text(
        code.replace(json.dumps(accepted_literal), json.dumps(new_literal)),
        encoding="utf-8",
    )
    errors = mypy_gate._run_mypy()
    assert len(errors) == 1 and errors[0].endswith("[assignment]")
    assert mypy_gate.main([]) == 1
    assert baseline.read_bytes() == accepted
    signature = mypy_gate._signature(errors[0])
    location, separator, message = errors[0].partition(": error:")
    assert separator
    assert signature.partition(": error:")[2] == message
    assert message in capsys.readouterr().err
    path = location.rsplit(":", 1)[0]
    for variant in (
        path + ":999" + separator + message,
        path + ":999:42" + separator + message,
        path.replace("/", "\\") + ":999:42" + separator + message,
    ):
        assert mypy_gate._signature(variant) == signature

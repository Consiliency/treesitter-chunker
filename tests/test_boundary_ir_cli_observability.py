import json
from pathlib import Path

from typer.testing import CliRunner

from cli.main import app


runner = CliRunner()


def test_boundary_cli_include_timings_controls_json(tmp_path: Path):
    source = tmp_path / "app.py"
    source.write_text("def greet():\n    return 'hi'\n", encoding="utf-8")

    default = runner.invoke(app, ["boundary", str(source), "--lang", "python"])
    timed = runner.invoke(
        app,
        ["boundary", str(source), "--lang", "python", "--include-timings"],
    )

    assert default.exit_code == 0
    assert timed.exit_code == 0
    default_data = json.loads(default.stdout)
    timed_data = json.loads(timed.stdout)
    assert all(value is None for value in default_data["run"]["timings"].values())
    assert all(
        isinstance(value, int | float) and value >= 0
        for value in timed_data["run"]["timings"].values()
    )


def test_boundary_cli_stdout_json_is_not_polluted_by_default(tmp_path: Path):
    source = tmp_path / "app.py"
    source.write_text("def greet():\n    return 'hi'\n", encoding="utf-8")

    result = runner.invoke(app, ["boundary", str(source), "--lang", "python"])

    assert result.exit_code == 0
    assert json.loads(result.stdout)["schema_version"] == "2.0"
    assert "Boundary IR summary" not in result.stdout


def test_boundary_cli_summary_uses_stderr_without_polluting_stdout(tmp_path: Path):
    source = tmp_path / "app.py"
    source.write_text("def greet():\n    return 'hi'\n", encoding="utf-8")

    result = runner.invoke(
        app,
        ["boundary", str(source), "--lang", "python", "--summary"],
    )

    assert result.exit_code == 0
    assert json.loads(result.stdout)["schema_version"] == "2.0"
    assert "Boundary IR summary" in result.stderr


def test_boundary_cli_output_file_prints_summary_unless_quiet(tmp_path: Path):
    source = tmp_path / "app.py"
    output = tmp_path / "boundary.json"
    quiet_output = tmp_path / "quiet.json"
    source.write_text("def greet():\n    return 'hi'\n", encoding="utf-8")

    result = runner.invoke(
        app,
        ["boundary", str(source), "--lang", "python", "--output", str(output)],
    )
    quiet = runner.invoke(
        app,
        [
            "boundary",
            str(source),
            "--lang",
            "python",
            "--output",
            str(quiet_output),
            "--quiet",
        ],
    )

    assert result.exit_code == 0
    assert "Boundary IR written" in result.stdout
    assert "Boundary IR summary" in result.stdout
    assert quiet.exit_code == 0
    assert quiet.stdout == ""


def test_boundary_cli_fail_fast_exits_nonzero(tmp_path: Path, monkeypatch):
    source = tmp_path / "app.py"
    source.write_text("def greet():\n    return 'hi'\n", encoding="utf-8")

    from cli import main

    def fail_extraction(*args, **kwargs):
        raise RuntimeError("forced extraction failure")

    monkeypatch.setattr(main, "extract_boundary_ir", fail_extraction)

    result = runner.invoke(
        app,
        ["boundary", str(source), "--lang", "python", "--fail-fast"],
    )

    assert result.exit_code != 0
    assert isinstance(result.exception, RuntimeError)

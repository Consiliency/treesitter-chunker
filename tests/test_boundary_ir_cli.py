import json
from pathlib import Path

from typer.testing import CliRunner

from cli.main import app


runner = CliRunner()


def test_boundary_command_writes_json_to_stdout(tmp_path: Path):
    source = tmp_path / "app.py"
    source.write_text("def greet():\n    return 'hi'\n", encoding="utf-8")

    result = runner.invoke(app, ["boundary", str(source), "--lang", "python"])

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["schema_version"] == "2.0"
    assert data["run"]["created_at"] is None
    assert data["run"]["options"]["resolution_mode"] == "strict"
    assert "Boundary IR written" not in result.output


def test_boundary_command_accepts_permissive_resolution_mode(tmp_path: Path):
    source = tmp_path / "app.py"
    source.write_text("def greet():\n    return missing_call()\n", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "boundary",
            str(source),
            "--lang",
            "python",
            "--resolution-mode",
            "permissive",
        ],
    )

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["run"]["options"]["resolution_mode"] == "permissive"


def test_boundary_command_writes_output_file(tmp_path: Path):
    source = tmp_path / "app.py"
    output = tmp_path / "out.json"
    source.write_text("def greet():\n    return 'hi'\n", encoding="utf-8")

    result = runner.invoke(
        app,
        ["boundary", str(source), "--lang", "python", "--output", str(output)],
    )

    assert result.exit_code == 0
    assert "Boundary IR written" in result.output
    data = json.loads(output.read_text(encoding="utf-8"))
    assert data["schema_version"] == "2.0"


def test_boundary_command_quiet_file_output_suppresses_human_text(tmp_path: Path):
    source = tmp_path / "app.py"
    output = tmp_path / "out.json"
    source.write_text("def greet():\n    return 'hi'\n", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "boundary",
            str(source),
            "--lang",
            "python",
            "--output",
            str(output),
            "--quiet",
        ],
    )

    assert result.exit_code == 0
    assert result.output == ""
    assert json.loads(output.read_text(encoding="utf-8"))["schema_version"] == "2.0"


def test_existing_chunk_json_command_still_works(tmp_path: Path):
    source = tmp_path / "app.py"
    source.write_text("def greet():\n    return 'hi'\n", encoding="utf-8")

    result = runner.invoke(app, ["chunk", str(source), "--lang", "python", "--json"])

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data[0]["node_type"] == "function_definition"


def test_existing_batch_json_command_still_works(tmp_path: Path):
    source = tmp_path / "app.py"
    source.write_text("def greet():\n    return 'hi'\n", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "batch",
            str(tmp_path),
            "--lang",
            "python",
            "--output-format",
            "json",
            "--quiet",
        ],
    )

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data[0]["node_type"] == "function_definition"

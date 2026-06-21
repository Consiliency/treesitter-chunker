import json
from pathlib import Path

from typer.testing import CliRunner

from cli.main import app


runner = CliRunner()


def test_boundary_cli_incremental_stdout_is_parseable_and_stable(tmp_path: Path):
    cache_dir = tmp_path / ".boundary-cache"
    (tmp_path / "app.py").write_text("def ok():\n    return 1\n", encoding="utf-8")

    cold = runner.invoke(
        app,
        [
            "boundary",
            str(tmp_path),
            "--lang",
            "python",
            "--incremental",
            "--cache-dir",
            str(cache_dir),
        ],
    )
    warm = runner.invoke(
        app,
        [
            "boundary",
            str(tmp_path),
            "--lang",
            "python",
            "--incremental",
            "--cache-dir",
            str(cache_dir),
        ],
    )

    assert cold.exit_code == 0
    assert warm.exit_code == 0
    assert json.loads(cold.stdout)["schema_version"] == "2.0"
    assert cold.stdout == warm.stdout


def test_boundary_cli_incremental_output_file_quiet_and_cache_dir(tmp_path: Path):
    cache_dir = tmp_path / "cache"
    output = tmp_path / "boundary.json"
    (tmp_path / "app.py").write_text("def ok():\n    return 1\n", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "boundary",
            str(tmp_path),
            "--lang",
            "python",
            "--incremental",
            "--cache-dir",
            str(cache_dir),
            "--force-rebuild",
            "--output",
            str(output),
            "--quiet",
        ],
    )

    assert result.exit_code == 0
    assert result.stdout == ""
    assert output.exists()
    assert (cache_dir / "index.json").exists()

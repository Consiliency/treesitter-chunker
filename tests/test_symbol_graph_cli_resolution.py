import json
import subprocess
import sys
from pathlib import Path


def test_symbols_extract_accepts_resolution_mode_and_legacy_fields(tmp_path: Path):
    source = tmp_path / "service.py"
    source.write_text(
        "def use_missing():\n    return missing_call()\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "chunker.cli",
            "symbols",
            "extract",
            str(tmp_path),
            "--language",
            "python",
            "--resolution-mode",
            "strict",
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[1],
    )

    assert result.returncode == 0
    data = json.loads(result.stdout)
    relationship = next(
        rel for rel in data["relationships"] if rel["reference"] == "missing_call"
    )
    assert relationship["resolution_mode"] == "strict"
    assert {"from", "to", "type", "line", "file", "is_internal"}.issubset(relationship)

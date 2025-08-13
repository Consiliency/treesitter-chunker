import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.skipif(
    not pytest.importorskip("graphviz", reason="graphviz not installed"),
    reason="graphviz required",
)
def test_visualize_ast_script(tmp_path: Path) -> None:
    sample = tmp_path / "sample.py"
    sample.write_text("def hello():\n    return 'hi'\n")
    output = tmp_path / "out.svg"
    subprocess.run(
        [
            sys.executable,
            "scripts/visualize_ast.py",
            str(sample),
            "--lang",
            "python",
            "--out",
            str(output),
        ],
        check=True,
    )
    assert output.exists()

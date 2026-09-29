"""Tracked root cruft and regenerated metadata stay out of the repository."""

import subprocess


CRUFT = (
    ".pypirc",
    ".mypy_coverage/**",
    "logs/**",
    "test_api.py",
    "test_symbol_extraction.py",
    "test_csharp.cs",
    "test_tsx.tsx",
    "test_wasm.wat",
    "tmp_test.Rmd",
    "compatibility.db",
    "troubleshooting.db",
    "validation_report.json",
    "setup.py.bak",
    "CODE_REVIEW_REPORT.md",
    "CODE_REVIEW_v3.2.2.md",
    "CODE_REVIEW_v4.0.0.md",
    "mcp_server.log",
    "treesitter_chunker.egg-info/**",
    "ide/**/node_modules/**",
)


def test_root_cruft_is_untracked_and_generated_paths_are_ignored() -> None:
    tracked = subprocess.run(
        ["git", "ls-files", *CRUFT],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert not tracked
    for path in (
        ".pypirc",
        ".mypy_coverage/",
        "logs/",
        "compatibility.db",
        "mcp_server.log",
        "treesitter_chunker.egg-info/",
        "ide/vscode/treesitter-chunker/node_modules/",
    ):
        assert (
            subprocess.run(["git", "check-ignore", "-q", path], check=False).returncode
            == 0
        )

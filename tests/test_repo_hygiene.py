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
    "CODE_REVIEW*.md",
    "mcp_server.log",
    "treesitter_chunker.egg-info/**",
    "ide/**/node_modules/**",
)


def _tracked_cruft() -> str:
    return subprocess.run(
        ["git", "ls-files", *CRUFT],
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def test_root_cruft_is_untracked_and_generated_paths_are_ignored() -> None:
    assert not _tracked_cruft()
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


def test_new_review_report_is_rejected(tmp_path, monkeypatch) -> None:
    """A new report name must not bypass the lightweight always-on policy.

    Only the tracked-file check runs here: the scratch repository has no
    .gitignore, so the ignore assertions would fail whatever CRUFT says.
    """
    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)
    (tmp_path / "CODE_REVIEW_X.md").write_text("scratch review\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("kept\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True)
    monkeypatch.chdir(tmp_path)
    assert _tracked_cruft().splitlines() == ["CODE_REVIEW_X.md"]

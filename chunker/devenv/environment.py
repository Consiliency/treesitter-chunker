"""Development Environment Implementation

Handles pre-commit hooks, linting, formatting, and CI/CD configuration.
"""

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from chunker.contracts.devenv_contract import DevelopmentEnvironmentContract


class DevelopmentEnvironment(DevelopmentEnvironmentContract):
    """Implementation of development environment setup and management"""

    def __init__(self) -> None:
        """Initialize development environment manager"""
        self._ruff_path = self._find_executable("ruff")
        self._black_path = self._find_executable("black")
        self._mypy_path = self._find_executable("mypy")
        self._pre_commit_path = self._find_executable("pre-commit")

    @staticmethod
    def _find_executable(name: str) -> str | None:
        """Find executable in PATH with common virtualenv fallbacks."""
        path = shutil.which(name)
        if path:
            return path
        try:
            import sys as _sys
            from pathlib import Path as _P

            candidates = []
            # Project-rooted virtualenvs
            here = _P(__file__).resolve()
            project = here.parent.parent.parent
            candidates.append(project / ".fullenv" / "bin" / name)
            candidates.append(project / ".venv" / "bin" / name)
            # Current interpreter's bin directory
            interp_bin = _P(_sys.executable).parent
            candidates.append(interp_bin / name)
            # Local user bin
            candidates.append(_P.home() / ".local" / "bin" / name)
            for c in candidates:
                if c.exists():
                    return str(c)
        except Exception:
            return None
        return None

    def setup_pre_commit_hooks(self, project_root: Path) -> bool:
        """
        Install and configure pre-commit hooks for the project

        Args:
            project_root: Root directory of the project

        Returns:
            True if setup successful, False otherwise
        """
        # Validate prerequisites
        if not self._validate_setup_prerequisites(project_root):
            return False

        # Run pre-commit install
        return self._run_pre_commit_install(project_root)

    def _validate_setup_prerequisites(self, project_root: Path) -> bool:
        """Validate all prerequisites for pre-commit setup."""
        if not project_root.exists() or not project_root.is_dir():
            return False

        git_dir = project_root / ".git"
        if not git_dir.exists():
            return False

        pre_commit_config = project_root / ".pre-commit-config.yaml"
        if not pre_commit_config.exists():
            return False

        return bool(self._pre_commit_path)

    def _run_pre_commit_install(self, project_root: Path) -> bool:
        """Run pre-commit install command."""
        try:
            result = subprocess.run(
                [self._pre_commit_path, "install"],
                check=False,
                cwd=project_root,
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                return False
            hooks_dir = project_root / ".git" / "hooks" / "pre-commit"
            return hooks_dir.exists()
        except (FileNotFoundError, IndexError, KeyError):
            return False

    def run_linting(
        self,
        paths: list[str] | None = None,
        fix: bool = False,
    ) -> tuple[bool, list[dict[str, Any]]]:
        """
        Run linting tools (ruff, mypy) on specified paths

        Args:
            paths: List of file/directory paths to lint (None = all)
            fix: Whether to auto-fix issues where possible

        Returns:
            Tuple of (success, issues) where issues is list of lint errors
        """
        issues: list[dict[str, Any]] = []
        success = True
        if paths is None:
            paths = ["."]
        # Always invoke tool runners; they handle missing executables internally.
        ruff_issues = self._run_ruff(paths, fix)
        if ruff_issues:
            success = False
            issues.extend(ruff_issues)
        mypy_issues = self._run_mypy(paths)
        if mypy_issues:
            success = False
            issues.extend(mypy_issues)
        return success, issues

    def _run_ruff(self, paths: list[str], fix: bool) -> list[dict[str, Any]]:
        """Run ruff linter"""
        issues = []
        try:
            cmd = [self._ruff_path, "check", "--output-format", "json"]
            if fix:
                cmd.append("--fix")
            cmd.extend(paths)
            result = subprocess.run(cmd, check=False, capture_output=True, text=True)
            if result.stdout:
                try:
                    ruff_output = json.loads(result.stdout)
                    issues.extend(
                        {
                            "tool": "ruff",
                            "file": issue.get("filename", ""),
                            "line": issue.get("location", {}).get("row", 0),
                            "column": issue.get("location", {}).get("column", 0),
                            "code": issue.get("code", ""),
                            "message": issue.get("message", ""),
                            "fixable": issue.get("fix") is not None,
                        }
                        for issue in ruff_output
                    )
                except json.JSONDecodeError:
                    if result.returncode != 0:
                        issues.append(
                            {
                                "tool": "ruff",
                                "file": "",
                                "line": 0,
                                "column": 0,
                                "code": "ERROR",
                                "message": result.stdout or result.stderr,
                                "fixable": False,
                            },
                        )
        except (FileNotFoundError, OSError, TypeError) as e:
            issues.append(
                {
                    "tool": "ruff",
                    "file": "",
                    "line": 0,
                    "column": 0,
                    "code": "ERROR",
                    "message": str(e),
                    "fixable": False,
                },
            )
        return issues

    def _run_mypy(self, paths: list[str]) -> list[dict[str, Any]]:
        """Run mypy type checker"""
        issues = []
        try:
            cmd = [self._mypy_path, "--no-error-summary", "--show-column-numbers"]
            cmd.extend(paths)
            result = subprocess.run(cmd, check=False, capture_output=True, text=True)
            if result.stdout:
                for line in result.stdout.strip().split("\n"):
                    if ": error:" in line or ": note:" in line:
                        parts = line.split(":", 4)
                        if len(parts) >= 5:
                            issues.append(
                                {
                                    "tool": "mypy",
                                    "file": parts[0],
                                    "line": int(parts[1]) if parts[1].isdigit() else 0,
                                    "column": (
                                        int(parts[2]) if parts[2].isdigit() else 0
                                    ),
                                    "code": parts[3].strip(),
                                    "message": parts[4].strip(),
                                    "fixable": False,
                                },
                            )
        except (FileNotFoundError, IndexError, KeyError) as e:
            issues.append(
                {
                    "tool": "mypy",
                    "file": "",
                    "line": 0,
                    "column": 0,
                    "code": "ERROR",
                    "message": str(e),
                    "fixable": False,
                },
            )
        return issues

    def format_code(
        self,
        paths: list[str] | None = None,
        check_only: bool = False,
    ) -> tuple[bool, list[str]]:
        """
        Format code using configured formatter (black/ruff)

        Args:
            paths: List of file/directory paths to format (None = all)
            check_only: Only check if formatting needed, don't modify

        Returns:
            Tuple of (formatted_correctly, modified_files)
        """
        if paths is None:
            paths = ["."]
        modified_files = []
        formatted_correctly = True
        # Always attempt ruff format first
        success, files = self._run_ruff_format(paths, check_only)
        if not success:
            formatted_correctly = False
        modified_files.extend(files)
        # Fallback to black if ruff format produced no changes and black is available
        if not files and self._black_path:
            b_success, b_files = self._run_black(paths, check_only)
            if not b_success:
                formatted_correctly = False
            modified_files.extend(b_files)
        return formatted_correctly, modified_files

    def _run_ruff_format(
        self,
        paths: list[str],
        check_only: bool,
    ) -> tuple[bool, list[str]]:
        """Run ruff formatter"""
        modified_files = []
        try:
            cmd = [self._ruff_path, "format"]
            if check_only:
                cmd.append("--check")
            cmd.extend(paths)
            result = subprocess.run(cmd, check=False, capture_output=True, text=True)
            if result.stdout:
                for line in result.stdout.strip().split("\n"):
                    if line and not line.startswith("Would"):
                        if " " in line:
                            file_path = line.split(" ")[0]
                            if Path(file_path).exists():
                                modified_files.append(file_path)
                        elif Path(line).exists():
                            modified_files.append(line)
            return result.returncode == 0, modified_files
        except (FileNotFoundError, IndexError, KeyError):
            return False, []

    def _run_black(self, paths: list[str], check_only: bool) -> tuple[bool, list[str]]:
        """Run black formatter"""
        modified_files = []
        try:
            cmd = [self._black_path]
            if check_only:
                cmd.extend(["--check", "--diff"])
            cmd.extend(paths)
            result = subprocess.run(cmd, check=False, capture_output=True, text=True)
            if result.stderr:
                for line in result.stderr.strip().split("\n"):
                    if "would reformat" in line or "reformatted" in line:
                        parts = line.split()
                        if parts:
                            file_path = parts[0]
                            if Path(file_path).exists():
                                modified_files.append(file_path)
            return result.returncode == 0, modified_files
        except (FileNotFoundError, IndexError, KeyError):
            return False, []

    @staticmethod
    def generate_ci_config(
        platforms: list[str],
        python_versions: list[str],
    ) -> dict[str, Any]:
        """
        Generate CI/CD configuration for specified platforms

        Args:
            platforms: List of platforms (ubuntu, macos, windows)
            python_versions: List of Python versions to test

        Returns:
            CI configuration as dictionary (convertible to YAML)
        """
        config = {
            "name": "CI",
            "on": {
                "push": {"branches": ["main", "develop"]},
                "pull_request": {"branches": ["main"]},
            },
            "jobs": {
                "test": {
                    "runs-on": "${{ matrix.os }}",
                    "strategy": {
                        "matrix": {"os": platforms, "python-version": python_versions},
                        "fail-fast": False,
                    },
                    "steps": [
                        {"uses": "actions/checkout@v4"},
                        {
                            "name": "Set up Python ${{ matrix.python-version }}",
                            "uses": "actions/setup-python@v5",
                            "with": {"python-version": "${{ matrix.python-version }}"},
                        },
                        {
                            "name": "Install dependencies",
                            "run": """|
python -m pip install --upgrade pip
pip install uv
uv pip install -e '.[dev]'""",
                        },
                        {
                            "name": "Fetch grammars",
                            "run": "python scripts/fetch_grammars.py",
                        },
                        {
                            "name": "Build grammars",
                            "run": "python scripts/build_lib.py",
                        },
                        {
                            "name": "Run linting",
                            "run": """|
ruff check .
mypy .""",
                        },
                        {
                            "name": "Run tests",
                            "run": "pytest --cov=chunker --cov-report=xml",
                        },
                        {
                            "name": "Upload coverage",
                            "uses": "codecov/codecov-action@v3",
                            "with": {
                                "file": "./coverage.xml",
                                "fail_ci_if_error": False,
                            },
                        },
                    ],
                },
                "build": {
                    "needs": "test",
                    "runs-on": "${{ matrix.os }}",
                    "strategy": {"matrix": {"os": platforms}},
                    "steps": [
                        {"uses": "actions/checkout@v4"},
                        {
                            "name": "Set up Python",
                            "uses": "actions/setup-python@v5",
                            "with": {"python-version": "3.11"},
                        },
                        {
                            "name": "Install build dependencies",
                            "run": """|
python -m pip install --upgrade pip
pip install build wheel""",
                        },
                        {"name": "Build wheel", "run": "python -m build"},
                        {
                            "name": "Upload artifacts",
                            "uses": "actions/upload-artifact@v4",
                            "with": {"name": "dist-${{ matrix.os }}", "path": "dist/*"},
                        },
                    ],
                },
                "deploy": {
                    "if": "startsWith(github.ref, 'refs/tags/')",
                    "needs": "build",
                    "runs-on": "ubuntu-latest",
                    "steps": [
                        {"uses": "actions/checkout@v4"},
                        {
                            "name": "Download artifacts",
                            "uses": "actions/download-artifact@v4",
                            "with": {
                                "pattern": "dist-*",
                                "path": "dist",
                                "merge-multiple": True,
                            },
                        },
                        {
                            "name": "Publish to PyPI",
                            "uses": "pypa/gh-action-pypi-publish@release/v1",
                            "with": {"password": "${{ secrets.PYPI_API_TOKEN }}"},
                        },
                    ],
                },
            },
        }
        return config

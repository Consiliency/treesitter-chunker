"""Concrete implementation of developer tooling functionality.

Team responsible: Developer Tooling Team
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple  # noqa: UP035

from chunker.contracts.tooling_contract import DeveloperToolingContract


class DeveloperToolingImpl(DeveloperToolingContract):
    """Production implementation of developer tooling functionality"""

    def __init__(self):
        """Initialize the developer tooling implementation"""
        self.project_root = self._find_project_root()

    def _find_project_root(self) -> Path:
        """Find the project root directory (containing pyproject.toml)"""
        current = Path.cwd()
        while current != current.parent:
            if (current / "pyproject.toml").exists():
                return current
            current = current.parent
        # Default to current directory if not found
        return Path.cwd()

    def run_pre_commit_checks(
        self,
        files: list[Path],
    ) -> Tuple[bool, Dict[str, Any]]:  # noqa: UP006
        """Run all pre-commit checks on specified files

        Args:
            files: List of file paths to check

        Returns:
            Tuple of (success: bool, results: dict) where results contains:
            - 'linting': Dict with linting results
            - 'formatting': Dict with formatting results
            - 'type_checking': Dict with type checking results
            - 'tests': Dict with test results
            - 'errors': List of error messages
        """
        results = {
            "linting": {"checked": 0, "errors": 0, "warnings": 0},
            "formatting": {"checked": 0, "formatted": 0},
            "type_checking": {"checked": 0, "errors": 0},
            "tests": {"run": 0, "passed": 0, "failed": 0},
            "errors": [],
        }

        all_success = True

        # Filter to only Python files
        python_files = [f for f in files if f.suffix == ".py" and f.exists()]

        if not python_files:
            results["errors"].append("No valid Python files to check")
            return False, results

        # Run formatting check
        format_results = self.format_code(python_files, fix=False)
        results["formatting"]["checked"] = len(python_files)
        results["formatting"]["formatted"] = len(format_results.get("formatted", []))
        if format_results.get("errors"):
            all_success = False
            results["errors"].extend(
                [f"Format error: {e}" for e in format_results["errors"]],
            )

        # Run linting
        lint_results = self.run_linting(python_files, fix=False)
        results["linting"]["checked"] = len(python_files)
        for issues in lint_results.values():
            for issue in issues:
                if issue.get("severity") == "error":
                    results["linting"]["errors"] += 1
                else:
                    results["linting"]["warnings"] += 1
        if results["linting"]["errors"] > 0:
            all_success = False

        # Run type checking
        type_results = self.run_type_checking(python_files)
        results["type_checking"]["checked"] = len(python_files)
        for issues in type_results.values():
            results["type_checking"]["errors"] += len(issues)
        if results["type_checking"]["errors"] > 0:
            all_success = False

        # Note: We don't run tests here as they're not file-specific
        # Tests would be run separately in a CI/CD pipeline

        return all_success, results

    def format_code(
        self,
        files: list[Path],
        fix: bool = False,
    ) -> Dict[str, Any]:  # noqa: UP006
        """Format code files according to project standards

        Args:
            files: List of file paths to format
            fix: Whether to fix issues in-place

        Returns:
            Dict containing:
            - 'formatted': List of files that were/would be formatted
            - 'errors': List of files with format errors
            - 'diff': Dict mapping file paths to diff strings (if fix=False)
        """
        result = {"formatted": [], "errors": [], "diff": {}}

        # Filter to only Python files that exist
        python_files = [f for f in files if f.suffix == ".py" and f.exists()]

        if not python_files:
            return result

        # Run black
        try:
            cmd = [sys.executable, "-m", "black"]
            if not fix:
                cmd.append("--check")
                cmd.append("--diff")

            # Add file paths
            cmd.extend([str(f) for f in python_files])

            # Run command
            proc = subprocess.run(
                cmd,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                check=False,
            )

            if proc.returncode == 0:
                # All files are already formatted
                pass
            elif proc.returncode == 1:
                # Some files need formatting
                if not fix:
                    # Parse the diff output
                    diff_lines = proc.stdout.split("\n")
                    current_file = None
                    current_diff = []

                    for line in diff_lines:
                        if line.startswith(("--- ", "+++ ")):
                            if line.startswith("--- "):
                                if current_file and current_diff:
                                    result["diff"][str(current_file)] = "\n".join(
                                        current_diff,
                                    )
                                # Extract filename from --- line
                                file_path = line.split("\t")[0][4:]  # Remove "--- "
                                current_file = Path(file_path).resolve()
                                current_diff = [line]
                            elif current_diff:
                                current_diff.append(line)
                        elif current_file:
                            current_diff.append(line)

                    # Add last file
                    if current_file and current_diff:
                        result["diff"][str(current_file)] = "\n".join(current_diff)

                    # Files that would be formatted
                    result["formatted"] = [
                        str(f) for f in python_files if str(f) in result["diff"]
                    ]
                else:
                    # Files were formatted
                    result["formatted"] = [str(f) for f in python_files]
            else:
                # Error occurred
                result["errors"] = [proc.stderr]

        except (FileNotFoundError, IndexError, KeyError) as e:
            result["errors"] = [str(e)]

        return result

    def run_linting(
        self,
        files: list[Path],
        fix: bool = False,
    ) -> Dict[str, List[Dict[str, Any]]]:  # noqa: UP006
        """Run linting checks on specified files

        Args:
            files: List of file paths to lint
            fix: Whether to auto-fix issues

        Returns:
            Dict mapping file paths to lists of issues, each containing:
            - 'line': Line number
            - 'column': Column number
            - 'code': Error code
            - 'message': Error message
            - 'severity': 'error' | 'warning' | 'info'
        """
        results = {}

        # Filter to only Python files that exist
        python_files = [f for f in files if f.suffix == ".py" and f.exists()]

        if not python_files:
            return results

        # Run ruff
        try:
            cmd = [sys.executable, "-m", "ruff", "check", "--output-format", "json"]
            if fix:
                cmd.append("--fix")

            # Add file paths
            cmd.extend([str(f) for f in python_files])

            # Run command
            proc = subprocess.run(
                cmd,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                check=False,
            )

            # Ruff outputs JSON even on failure
            if proc.stdout:

                try:
                    issues = json.loads(proc.stdout)
                    for issue in issues:
                        file_path = str(Path(issue["filename"]).resolve())
                        if file_path not in results:
                            results[file_path] = []

                        results[file_path].append(
                            {
                                "line": issue.get("location", {}).get("row", 0),
                                "column": issue.get("location", {}).get("column", 0),
                                "code": issue.get("code", ""),
                                "message": issue.get("message", ""),
                                "severity": (
                                    "error" if issue.get("fix") is None else "warning"
                                ),
                            },
                        )
                except json.JSONDecodeError:
                    # Fallback to parsing text output
                    pass

        except (AttributeError, FileNotFoundError, IndexError):
            # Return empty results on error
            pass

        return results

    def run_type_checking(
        self,
        files: list[Path],
    ) -> Dict[str, List[Dict[str, Any]]]:  # noqa: UP006
        """Run static type checking on files

        Args:
            files: List of file paths to type check

        Returns:
            Dict mapping file paths to lists of type errors, each containing:
            - 'line': Line number
            - 'column': Column number
            - 'message': Type error message
            - 'severity': 'error' | 'warning' | 'note'
        """
        results = {}

        # Filter to only Python files that exist
        python_files = [f for f in files if f.suffix == ".py" and f.exists()]

        if not python_files:
            return results

        # Run mypy
        try:
            cmd = [sys.executable, "-m", "mypy", "--no-error-summary"]

            # Add file paths
            cmd.extend([str(f) for f in python_files])

            # Run command
            proc = subprocess.run(
                cmd,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                check=False,
            )

            # Parse mypy output
            # Format: file.py:line:col: severity: message
            for line in proc.stdout.split("\n"):
                if not line or ": " not in line:
                    continue

                parts = line.split(":", 4)
                if len(parts) >= 5:
                    file_path = str(Path(parts[0]).resolve())
                    try:
                        line_num = int(parts[1])
                        col_num = int(parts[2]) if parts[2].strip() else 0
                        severity = parts[3].strip().lower()
                        message = parts[4].strip()

                        if file_path not in results:
                            results[file_path] = []

                        results[file_path].append(
                            {
                                "line": line_num,
                                "column": col_num,
                                "message": message,
                                "severity": (
                                    severity
                                    if severity in ["error", "warning", "note"]
                                    else "error"
                                ),
                            },
                        )
                    except (ValueError, IndexError):
                        # Skip malformed lines
                        pass

        except (IndexError, KeyError):
            # Return empty results on error
            pass

        return results

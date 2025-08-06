"""Quality Assurance Implementation

Handles code quality metrics, type coverage, and test coverage analysis.
"""

import contextlib
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from chunker.contracts.devenv_contract import QualityAssuranceContract


class QualityAssurance(QualityAssuranceContract):
    """Implementation of code quality and standards enforcement"""

    def __init__(self) -> None:
        """Initialize quality assurance manager"""
        self._mypy_path = self._find_executable("mypy")
        self._pytest_path = self._find_executable("pytest")
        self._coverage_path = self._find_executable("coverage")

    @staticmethod
    def _find_executable(name: str) -> str | None:
        """Find executable in PATH"""
        return shutil.which(name)

    def check_type_coverage(
        self,
        min_coverage: float = 80.0,
    ) -> tuple[float, dict[str, Any]]:
        """
        Check type annotation coverage using mypy

        Args:
            min_coverage: Minimum required coverage percentage

        Returns:
            Tuple of (coverage_percentage, detailed_report)
        """
        if not self._mypy_path:
            return 0.0, {"error": "mypy not found"}
        try:
            cmd = [
                self._mypy_path,
                "chunker",
                "--html-report",
                ".mypy_coverage",
                "--any-exprs-report",
                ".mypy_coverage",
                "--linecount-report",
                ".mypy_coverage",
                "--linecoverage-report",
                ".mypy_coverage",
                "--no-error-summary",
            ]
            result = subprocess.run(cmd, check=False, capture_output=True, text=True)
            linecount_file = Path(".mypy_coverage/linecount.txt")
            if linecount_file.exists():
                coverage_data = self._parse_mypy_linecount(linecount_file)
                total_lines = coverage_data.get("total_lines", 0)
                typed_lines = coverage_data.get("typed_lines", 0)
                if total_lines > 0:
                    coverage_percentage = typed_lines / total_lines * 100
                else:
                    coverage_percentage = 0.0
                report = {
                    "coverage_percentage": coverage_percentage,
                    "meets_minimum": coverage_percentage >= min_coverage,
                    "total_lines": total_lines,
                    "typed_lines": typed_lines,
                    "untyped_lines": total_lines - typed_lines,
                    "files": coverage_data.get("files", {}),
                }
                return coverage_percentage, report
            return self._estimate_type_coverage(result.stdout)
        except (AttributeError, FileNotFoundError, IndexError) as e:
            return 0.0, {"error": str(e)}

    @classmethod
    def _parse_mypy_linecount(cls, linecount_file: Path) -> dict[str, Any]:
        """Parse mypy linecount report"""
        coverage_data = {"total_lines": 0, "typed_lines": 0, "files": {}}
        try:
            with Path(linecount_file).open("r", encoding="utf-8") as f:
                for line in f:
                    stripped_line = line.strip()
                    if stripped_line and not stripped_line.startswith("Total"):
                        parts = stripped_line.split()
                        if len(parts) >= 4:
                            filename = parts[0]
                            total = int(parts[1]) if parts[1].isdigit() else 0
                            typed = int(parts[2]) if parts[2].isdigit() else 0
                            coverage_data["files"][filename] = {
                                "total_lines": total,
                                "typed_lines": typed,
                                "coverage": typed / total * 100 if total > 0 else 0,
                            }
                            coverage_data["total_lines"] += total
                            coverage_data["typed_lines"] += typed
        except (FileNotFoundError, IndexError, KeyError):
            pass
        return coverage_data

    @staticmethod
    def _estimate_type_coverage(mypy_output: str) -> tuple[
        float,
        dict[str, Any],
    ]:
        """Estimate type coverage from mypy output"""
        lines = mypy_output.strip().split("\n")
        error_count = 0
        file_errors = {}
        for line in lines:
            if ": error:" in line or ": note:" in line:
                error_count += 1
                if ":" in line:
                    filename = line.split(":")[0]
                    file_errors[filename] = file_errors.get(filename, 0) + 1
        if error_count == 0:
            coverage_percentage = 100.0
        elif error_count < 10:
            coverage_percentage = 80.0
        elif error_count < 50:
            coverage_percentage = 60.0
        elif error_count < 100:
            coverage_percentage = 40.0
        else:
            coverage_percentage = 20.0
        report = {
            "coverage_percentage": coverage_percentage,
            "meets_minimum": coverage_percentage >= 80.0,
            "error_count": error_count,
            "files": {
                filename: {
                    "errors": count,
                    "estimated_coverage": max(0, 100 - count * 10),
                }
                for filename, count in file_errors.items()
            },
        }
        return coverage_percentage, report

    def check_test_coverage(
        self,
        min_coverage: float = 80.0,
    ) -> tuple[float, dict[str, Any]]:
        """
        Check test coverage using pytest-cov

        Args:
            min_coverage: Minimum required coverage percentage

        Returns:
            Tuple of (coverage_percentage, detailed_report)
        """
        if not self._pytest_path:
            return 0.0, {"error": "pytest not found"}
        try:
            cmd = [
                self._pytest_path,
                "--cov=chunker",
                "--cov-report=json",
                "--cov-report=term",
                "-q",
                "--tb=no",
            ]
            result = subprocess.run(cmd, check=False, capture_output=True, text=True)
            coverage_json = Path("coverage.json")
            if coverage_json.exists():
                with Path(coverage_json).open("r", encoding="utf-8") as f:
                    coverage_data = json.load(f)
                totals = coverage_data.get("totals", {})
                coverage_percentage = totals.get("percent_covered", 0.0)
                report = {
                    "coverage_percentage": coverage_percentage,
                    "meets_minimum": coverage_percentage >= min_coverage,
                    "lines_covered": totals.get("covered_lines", 0),
                    "lines_missing": totals.get("missing_lines", 0),
                    "total_lines": totals.get("num_statements", 0),
                    "files": {},
                    "uncovered_lines": {},
                }
                files_data = coverage_data.get("files", {})
                for filename, file_info in files_data.items():
                    if filename.startswith("chunker/"):
                        summary = file_info.get("summary", {})
                        report["files"][filename] = {
                            "coverage": summary.get("percent_covered", 0),
                            "missing_lines": summary.get("missing_lines", 0),
                            "covered_lines": summary.get("covered_lines", 0),
                        }
                        missing = file_info.get("missing_lines", [])
                        if missing:
                            report["uncovered_lines"][filename] = missing
                return coverage_percentage, report
            return self._parse_coverage_text(result.stdout)
        except (AttributeError, FileNotFoundError, IndexError) as e:
            return 0.0, {"error": str(e)}

    @staticmethod
    def _parse_coverage_text(coverage_output: str) -> tuple[float, dict[str, Any]]:
        """Parse coverage text output"""
        lines = coverage_output.strip().split("\n")
        coverage_percentage = 0.0
        file_coverage = {}
        for line in lines:
            if "TOTAL" in line:
                parts = line.split()
                for part in parts:
                    if part.endswith("%"):
                        with contextlib.suppress(ValueError):
                            coverage_percentage = float(part.rstrip("%"))
            elif line.startswith("chunker/") and "%" in line:
                parts = line.split()
                if len(parts) >= 4:
                    filename = parts[0]
                    try:
                        for part in reversed(parts):
                            if part.endswith("%"):
                                file_coverage[filename] = float(part.rstrip("%"))
                                break
                    except ValueError:
                        pass
        report = {
            "coverage_percentage": coverage_percentage,
            "meets_minimum": coverage_percentage >= 80.0,
            "files": {
                filename: {"coverage": cov} for filename, cov in file_coverage.items()
            },
            "uncovered_lines": {},
        }
        return coverage_percentage, report

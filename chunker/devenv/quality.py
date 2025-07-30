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

    def _find_executable(self, name: str) -> str | None:
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
            # Run mypy with report generation
            cmd = [
                self._mypy_path,
                "chunker",  # Analyze chunker package
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

            result = subprocess.run(
                cmd,
                check=False,
                capture_output=True,
                text=True,
            )

            # Parse the linecount report
            linecount_file = Path(".mypy_coverage/linecount.txt")
            if linecount_file.exists():
                coverage_data = self._parse_mypy_linecount(linecount_file)

                # Calculate overall coverage
                total_lines = coverage_data.get("total_lines", 0)
                typed_lines = coverage_data.get("typed_lines", 0)

                if total_lines > 0:
                    coverage_percentage = (typed_lines / total_lines) * 100
                else:
                    coverage_percentage = 0.0

                # Build detailed report
                report = {
                    "coverage_percentage": coverage_percentage,
                    "meets_minimum": coverage_percentage >= min_coverage,
                    "total_lines": total_lines,
                    "typed_lines": typed_lines,
                    "untyped_lines": total_lines - typed_lines,
                    "files": coverage_data.get("files", {}),
                }

                return coverage_percentage, report
            # Fallback: estimate from mypy output
            return self._estimate_type_coverage(result.stdout)

        except (AttributeError, FileNotFoundError, IndexError) as e:
            return 0.0, {"error": str(e)}

    def _parse_mypy_linecount(self, linecount_file: Path) -> dict[str, Any]:
        """Parse mypy linecount report"""
        coverage_data = {
            "total_lines": 0,
            "typed_lines": 0,
            "files": {},
        }

        try:
            with open(linecount_file) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("Total"):
                        parts = line.split()
                        if len(parts) >= 4:
                            filename = parts[0]
                            total = int(parts[1]) if parts[1].isdigit() else 0
                            typed = int(parts[2]) if parts[2].isdigit() else 0

                            coverage_data["files"][filename] = {
                                "total_lines": total,
                                "typed_lines": typed,
                                "coverage": (typed / total * 100) if total > 0 else 0,
                            }

                            coverage_data["total_lines"] += total
                            coverage_data["typed_lines"] += typed

        except (FileNotFoundError, IndexError, KeyError):
            pass

        return coverage_data

    def _estimate_type_coverage(self, mypy_output: str) -> tuple[float, dict[str, Any]]:
        """Estimate type coverage from mypy output"""
        # Count errors/warnings as indicators of missing types
        lines = mypy_output.strip().split("\n")
        error_count = 0
        file_errors = {}

        for line in lines:
            if ": error:" in line or ": note:" in line:
                error_count += 1
                # Extract filename
                if ":" in line:
                    filename = line.split(":")[0]
                    file_errors[filename] = file_errors.get(filename, 0) + 1

        # Rough estimation: assume 80% coverage if < 10 errors, decreasing from there
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
                    "estimated_coverage": max(0, 100 - (count * 10)),
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
            # Run pytest with coverage
            cmd = [
                self._pytest_path,
                "--cov=chunker",
                "--cov-report=json",
                "--cov-report=term",
                "-q",  # Quiet mode
                "--tb=no",  # No traceback
            ]

            result = subprocess.run(
                cmd,
                check=False,
                capture_output=True,
                text=True,
            )

            # Parse coverage.json if it exists
            coverage_json = Path("coverage.json")
            if coverage_json.exists():
                with open(coverage_json) as f:
                    coverage_data = json.load(f)

                # Extract coverage percentage
                totals = coverage_data.get("totals", {})
                coverage_percentage = totals.get("percent_covered", 0.0)

                # Build detailed report
                report = {
                    "coverage_percentage": coverage_percentage,
                    "meets_minimum": coverage_percentage >= min_coverage,
                    "lines_covered": totals.get("covered_lines", 0),
                    "lines_missing": totals.get("missing_lines", 0),
                    "total_lines": totals.get("num_statements", 0),
                    "files": {},
                    "uncovered_lines": {},
                }

                # Add file-level details
                files_data = coverage_data.get("files", {})
                for filename, file_info in files_data.items():
                    if filename.startswith("chunker/"):
                        summary = file_info.get("summary", {})
                        report["files"][filename] = {
                            "coverage": summary.get("percent_covered", 0),
                            "missing_lines": summary.get("missing_lines", 0),
                            "covered_lines": summary.get("covered_lines", 0),
                        }

                        # Track uncovered lines
                        missing = file_info.get("missing_lines", [])
                        if missing:
                            report["uncovered_lines"][filename] = missing

                return coverage_percentage, report
            # Fallback: parse text output
            return self._parse_coverage_text(result.stdout)

        except (AttributeError, FileNotFoundError, IndexError) as e:
            return 0.0, {"error": str(e)}

    def _parse_coverage_text(
        self,
        coverage_output: str,
    ) -> tuple[float, dict[str, Any]]:
        """Parse coverage text output"""
        lines = coverage_output.strip().split("\n")
        coverage_percentage = 0.0
        file_coverage = {}

        for line in lines:
            # Look for total coverage line
            if "TOTAL" in line:
                parts = line.split()
                for part in parts:
                    if part.endswith("%"):
                        with contextlib.suppress(ValueError):
                            coverage_percentage = float(part.rstrip("%"))
            # Parse individual file coverage
            elif line.startswith("chunker/") and "%" in line:
                parts = line.split()
                if len(parts) >= 4:
                    filename = parts[0]
                    try:
                        # Find percentage (usually last or second-to-last)
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
            "uncovered_lines": {},  # Not available in text output
        }

        return coverage_percentage, report

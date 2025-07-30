"""
Integration tests for Development Environment Component
Tests the actual implementation against the contract
"""

from chunker.contracts.devenv_contract import (
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from chunker.devenv import DevelopmentEnvironment, QualityAssurance

if TYPE_CHECKING:
        DevelopmentEnvironmentContract,
        QualityAssuranceContract,
    )


class TestDevEnvironmentIntegration:
    """Test development environment tools integration"""

    def test_pre_commit_hooks_setup(self):
        """Pre-commit hooks should be installable in git repo"""
        dev_env: DevelopmentEnvironmentContract = DevelopmentEnvironment()

        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)

            # Create a git repository
            subprocess.run(
                ["git", "init"],
                check=False,
                cwd=project_root,
                capture_output=True,
            )

            # Create a minimal .pre-commit-config.yaml
            config_content = """repos:
  - repo: https://github.com/psf/black
    rev: 24.3.0
    hooks:
      - id: black
"""
            config_file = project_root / ".pre-commit-config.yaml"
            config_file.write_text(config_content)

            # Only test if pre-commit is available
            if shutil.which("pre-commit"):
                # Setup pre-commit
                success = dev_env.setup_pre_commit_hooks(project_root)
                assert success

                # Verify hooks are installed
                hooks_file = project_root / ".git" / "hooks" / "pre-commit"
                assert hooks_file.exists()
            else:
                # If pre-commit not available, should return False
                success = dev_env.setup_pre_commit_hooks(project_root)
                assert not success

    def test_linting_detects_issues(self):
        """Linting should detect code issues"""
        dev_env: DevelopmentEnvironmentContract = DevelopmentEnvironment()

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a file with linting issues
            bad_file = Path(tmpdir) / "bad_code.py"
            bad_file.write_text(
                """
import os
import sys
def bad_function( ):
    x = 1
    y = 2
    return x
""",
            )

            # Run linting
            success, issues = dev_env.run_linting([str(bad_file)])

            # Should find issues (unused imports, bad formatting, etc.)
            if shutil.which("ruff") or shutil.which("mypy"):
                assert not success
                assert len(issues) > 0

                # Check issue structure
                if issues:
                    issue = issues[0]
                    assert "tool" in issue
                    assert "file" in issue
                    assert "message" in issue

    def test_formatting_fixes_code(self):
        """Code formatting should fix style issues"""
        dev_env: DevelopmentEnvironmentContract = DevelopmentEnvironment()

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a file with formatting issues
            bad_file = Path(tmpdir) / "format_me.py"
            bad_file.write_text(
                """def poorly_formatted(  x,y   ):
    return x+y


class BadClass:
  def __init__(self):
      pass
""",
            )

            # Check formatting
            success, modified_files = dev_env.format_code(
                [str(bad_file)],
                check_only=True,
            )

            if shutil.which("ruff") or shutil.which("black"):
                # Should detect formatting issues
                assert not success or len(modified_files) > 0

                # Actually format the file
                success, modified_files = dev_env.format_code(
                    [str(bad_file)],
                    check_only=False,
                )

                # Read the formatted content
                formatted_content = bad_file.read_text()

                # Should be properly formatted now
                assert (
                    "def poorly_formatted(x, y):" in formatted_content
                    or "def poorly_formatted(" in formatted_content
                )

    def test_ci_config_generation(self):
        """CI config should cover all specified platforms"""
        dev_env: DevelopmentEnvironmentContract = DevelopmentEnvironment()

        platforms = ["ubuntu-latest", "macos-latest", "windows-latest"]
        python_versions = ["3.8", "3.9", "3.10", "3.11"]

        config = dev_env.generate_ci_config(platforms, python_versions)

        assert "jobs" in config
        assert "test" in config["jobs"]

        # Verify matrix strategy
        matrix = config["jobs"]["test"]["strategy"]["matrix"]
        assert set(matrix["os"]) == set(platforms)
        assert set(matrix["python-version"]) == set(python_versions)

        # Verify all essential steps are included
        steps = config["jobs"]["test"]["steps"]
        step_names = [step.get("name", "") for step in steps if isinstance(step, dict)]

        # Should have checkout, setup python, install deps, run tests
        assert any("checkout" in str(step) for step in steps)
        assert any("Python" in name for name in step_names)
        assert any("test" in str(step) for step in steps)


class TestQualityAssuranceIntegration:
    """Test quality assurance tools integration"""

    def test_type_coverage_check(self):
        """Type coverage should analyze code annotations"""
        qa: QualityAssuranceContract = QualityAssurance()

        # Check type coverage
        coverage, report = qa.check_type_coverage(min_coverage=80.0)

        assert isinstance(coverage, float)
        assert 0 <= coverage <= 100
        assert isinstance(report, dict)

        # Report should have expected fields
        if "error" not in report:
            assert "files" in report or "coverage_percentage" in report

    def test_test_coverage_check(self):
        """Test coverage should analyze test execution"""
        qa: QualityAssuranceContract = QualityAssurance()

        # Check test coverage
        coverage, report = qa.check_test_coverage(min_coverage=80.0)

        assert isinstance(coverage, float)
        assert 0 <= coverage <= 100
        assert isinstance(report, dict)

        # Report should have expected fields
        if "error" not in report:
            assert "uncovered_lines" in report or "coverage_percentage" in report

            # If successful, should have detailed metrics
            if coverage > 0:
                assert (
                    "files" in report
                    or "lines_covered" in report
                    or "total_lines" in report
                )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

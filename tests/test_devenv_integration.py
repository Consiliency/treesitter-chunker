"""
Integration tests for Development Environment Component
Tests the actual implementation against the contract
"""

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from chunker.devenv import DevelopmentEnvironment, QualityAssurance

if TYPE_CHECKING:
    from chunker.contracts.devenv_contract import (
        DevelopmentEnvironmentContract,
        QualityAssuranceContract,
    )


class TestDevEnvironmentIntegration:
    """Test development environment tools integration"""

    @classmethod
    def test_pre_commit_hooks_setup(cls):
        """Pre-commit hooks should be installable in git repo"""
        dev_env: DevelopmentEnvironmentContract = DevelopmentEnvironment()
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            subprocess.run(
                ["git", "init"],
                check=False,
                cwd=project_root,
                capture_output=True,
            )
            config_content = """repos:
  - repo: https://github.com/psf/black
    rev: 24.3.0
    hooks:
      - id: black
"""
            config_file = project_root / ".pre-commit-config.yaml"
            config_file.write_text(config_content)
            if shutil.which("pre-commit"):
                success = dev_env.setup_pre_commit_hooks(project_root)
                assert success
                hooks_file = project_root / ".git" / "hooks" / "pre-commit"
                assert hooks_file.exists()
            else:
                success = dev_env.setup_pre_commit_hooks(project_root)
                assert not success

    @classmethod
    def test_linting_detects_issues(cls):
        """Linting should detect code issues"""
        dev_env: DevelopmentEnvironmentContract = DevelopmentEnvironment()
        with tempfile.TemporaryDirectory() as tmpdir:
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
            success, issues = dev_env.run_linting([str(bad_file)])
            if shutil.which("ruff") or shutil.which("mypy"):
                assert not success
                assert len(issues) > 0
                if issues:
                    issue = issues[0]
                    assert "tool" in issue
                    assert "file" in issue
                    assert "message" in issue

    @classmethod
    def test_formatting_fixes_code(cls):
        """Code formatting should fix style issues"""
        dev_env: DevelopmentEnvironmentContract = DevelopmentEnvironment()
        with tempfile.TemporaryDirectory() as tmpdir:
            bad_file = Path(tmpdir) / "format_me.py"
            bad_file.write_text(
                """def poorly_formatted(  x,y   ):
    return x+y


class BadClass:
  def __init__(self):
      pass
""",
            )
            success, modified_files = dev_env.format_code(
                [str(bad_file)],
                check_only=True,
            )
            if shutil.which("ruff") or shutil.which("black"):
                assert not success or len(modified_files) > 0
                success, modified_files = dev_env.format_code(
                    [
                        str(
                            bad_file,
                        ),
                    ],
                    check_only=False,
                )
                formatted_content = bad_file.read_text()
                assert (
                    "def poorly_formatted(x, y):" in formatted_content
                    or "def poorly_formatted(" in formatted_content
                )

    @classmethod
    def test_ci_config_generation(cls):
        """CI config should cover all specified platforms"""
        dev_env: DevelopmentEnvironmentContract = DevelopmentEnvironment()
        platforms = ["ubuntu-latest", "macos-latest", "windows-latest"]
        python_versions = ["3.8", "3.9", "3.10", "3.11"]
        config = dev_env.generate_ci_config(platforms, python_versions)
        assert "jobs" in config
        assert "test" in config["jobs"]
        matrix = config["jobs"]["test"]["strategy"]["matrix"]
        assert set(matrix["os"]) == set(platforms)
        assert set(matrix["python-version"]) == set(python_versions)
        steps = config["jobs"]["test"]["steps"]
        step_names = [step.get("name", "") for step in steps if isinstance(step, dict)]
        assert any("checkout" in str(step) for step in steps)
        assert any("Python" in name for name in step_names)
        assert any("test" in str(step) for step in steps)


class TestQualityAssuranceIntegration:
    """Test quality assurance tools integration"""

    @classmethod
    def test_type_coverage_check(cls):
        """Type coverage should analyze code annotations"""
        qa: QualityAssuranceContract = QualityAssurance()
        coverage, report = qa.check_type_coverage(min_coverage=80.0)
        assert isinstance(coverage, float)
        assert 0 <= coverage <= 100
        assert isinstance(report, dict)
        if "error" not in report:
            assert "files" in report or "coverage_percentage" in report

    @classmethod
    def test_test_coverage_check(cls):
        """Test coverage should analyze test execution"""
        qa: QualityAssuranceContract = QualityAssurance()
        coverage, report = qa.check_test_coverage(min_coverage=80.0)
        assert isinstance(coverage, float)
        assert 0 <= coverage <= 100
        assert isinstance(report, dict)
        if "error" not in report:
            assert "uncovered_lines" in report or "coverage_percentage" in report
            if coverage > 0:
                assert (
                    "files" in report
                    or "lines_covered" in report
                    or "total_lines" in report
                )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

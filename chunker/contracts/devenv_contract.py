"""
Contract for Development Environment Component
Defines the interface for pre-commit hooks, linting, and CI/CD integration
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class DevelopmentEnvironmentContract(ABC):
    """Contract for development environment setup and management"""

    @abstractmethod
    def setup_pre_commit_hooks(self, project_root: Path) -> bool:
        """
        Install and configure pre-commit hooks for the project

        Args:
            project_root: Root directory of the project

        Returns:
            True if setup successful, False otherwise

        Preconditions:
            - project_root exists and is a git repository
            - .pre-commit-config.yaml is present

        Postconditions:
            - Pre-commit hooks are installed
            - Hooks run on git commit
        """
        raise NotImplementedError("DevEnv team will implement")

    @abstractmethod
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

        Preconditions:
            - Linting tools are configured
            - Paths exist if specified

        Postconditions:
            - Returns all discovered issues
            - Files are modified if fix=True and fixable issues exist
        """
        raise NotImplementedError("DevEnv team will implement")

    @abstractmethod
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

        Preconditions:
            - Formatter is configured
            - Paths exist if specified

        Postconditions:
            - Files are formatted if check_only=False
            - Returns list of files that were/would be modified
        """
        raise NotImplementedError("DevEnv team will implement")

    @abstractmethod
    def generate_ci_config(
        self,
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

        Preconditions:
            - Platform names are valid
            - Python versions are valid

        Postconditions:
            - Returns complete CI configuration
            - Includes all test, build, and deploy steps
        """
        raise NotImplementedError("DevEnv team will implement")


class QualityAssuranceContract(ABC):
    """Contract for code quality and standards enforcement"""

    @abstractmethod
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

        Preconditions:
            - mypy is configured
            - Project has type annotations

        Postconditions:
            - Returns accurate coverage metrics
            - Report includes file-by-file breakdown
        """
        raise NotImplementedError("DevEnv team will implement")

    @abstractmethod
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

        Preconditions:
            - pytest and pytest-cov are installed
            - Tests exist in project

        Postconditions:
            - Returns accurate coverage metrics
            - Report includes line-by-line coverage
        """
        raise NotImplementedError("DevEnv team will implement")

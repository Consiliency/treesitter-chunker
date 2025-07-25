# File: chunker/contracts/tooling_contract.py
# Purpose: Define the boundary for developer tooling components
# Team responsible: Developer Tooling Team

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Tuple


class DeveloperToolingContract(ABC):
    """Abstract contract defining developer tooling interface"""

    @abstractmethod
    def run_pre_commit_checks(self, files: List[Path]) -> Tuple[bool, Dict[str, Any]]:
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

        Preconditions:
            - Files exist and are readable
            - Development dependencies are installed

        Postconditions:
            - All checks have been run
            - Results are populated for each check type
        """

    @abstractmethod
    def format_code(self, files: List[Path], fix: bool = False) -> Dict[str, Any]:
        """Format code files according to project standards

        Args:
            files: List of file paths to format
            fix: Whether to fix issues in-place

        Returns:
            Dict containing:
            - 'formatted': List of files that were/would be formatted
            - 'errors': List of files with format errors
            - 'diff': Dict mapping file paths to diff strings (if fix=False)

        Preconditions:
            - Files are Python source files
            - Formatter configuration exists

        Postconditions:
            - All files have been checked
            - If fix=True, files are modified in-place
        """

    @abstractmethod
    def run_linting(
        self,
        files: List[Path],
        fix: bool = False,
    ) -> Dict[str, List[Dict[str, Any]]]:
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

        Preconditions:
            - Linting tools are configured
            - Files are valid Python files

        Postconditions:
            - All files have been linted
            - If fix=True, auto-fixable issues are resolved
        """

    @abstractmethod
    def run_type_checking(self, files: List[Path]) -> Dict[str, List[Dict[str, Any]]]:
        """Run static type checking on files

        Args:
            files: List of file paths to type check

        Returns:
            Dict mapping file paths to lists of type errors, each containing:
            - 'line': Line number
            - 'column': Column number
            - 'message': Type error message
            - 'severity': 'error' | 'warning' | 'note'

        Preconditions:
            - Type checker is installed and configured
            - Project has type hints

        Postconditions:
            - All files have been type checked
            - Results include all type violations
        """

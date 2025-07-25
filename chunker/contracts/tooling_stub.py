# File: chunker/contracts/tooling_stub.py
# Purpose: Concrete stub implementation for testing

from pathlib import Path
from typing import Any, Dict, List, Tuple

from .tooling_contract import DeveloperToolingContract


class DeveloperToolingStub(DeveloperToolingContract):
    """Stub implementation that can be instantiated and tested"""

    def run_pre_commit_checks(self, files: List[Path]) -> Tuple[bool, Dict[str, Any]]:
        """Stub that returns valid default values"""
        return (
            False,
            {
                "status": "not_implemented",
                "team": "Developer Tooling",
                "linting": {"checked": 0, "errors": 0, "warnings": 0},
                "formatting": {"checked": 0, "formatted": 0},
                "type_checking": {"checked": 0, "errors": 0},
                "tests": {"run": 0, "passed": 0, "failed": 0},
                "errors": ["Developer Tooling team will implement"],
            },
        )

    def format_code(self, files: List[Path], fix: bool = False) -> Dict[str, Any]:
        """Stub that returns valid default values"""
        return {
            "status": "not_implemented",
            "team": "Developer Tooling",
            "formatted": [],
            "errors": [],
            "diff": {},
        }

    def run_linting(
        self,
        files: List[Path],
        fix: bool = False,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Stub that returns valid default values"""
        return {}

    def run_type_checking(self, files: List[Path]) -> Dict[str, List[Dict[str, Any]]]:
        """Stub that returns valid default values"""
        return {}

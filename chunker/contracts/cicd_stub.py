# File: chunker/contracts/cicd_stub.py
# Purpose: Concrete stub implementation for testing

from pathlib import Path
from typing import Any

from .cicd_contract import CICDPipelineContract


class CICDPipelineStub(CICDPipelineContract):
    """Stub implementation that can be instantiated and tested"""

    def validate_workflow_syntax(self, workflow_path: Path) -> tuple[bool, list[str]]:
        """Stub that returns valid default values"""
        return (False, ["CI/CD team will implement workflow validation"])

    def run_test_matrix(
        self,
        python_versions: list[str],
        platforms: list[str],
    ) -> dict[str, dict[str, Any]]:
        """Stub that returns valid default values"""
        result = {}
        for version in python_versions:
            for platform in platforms:
                key = f"python-{version}-{platform}"
                result[key] = {
                    "status": "not_implemented",
                    "team": "CI/CD",
                    "tests_run": 0,
                    "tests_passed": 0,
                    "duration": 0.0,
                    "errors": ["CI/CD team will implement test matrix"],
                }
        return result

    def build_distribution(self, version: str, platforms: list[str]) -> dict[str, Any]:
        """Stub that returns valid default values"""
        return {
            "status": "not_implemented",
            "team": "CI/CD",
            "wheels": [],
            "sdist": None,
            "checksums": {},
            "build_logs": {},
        }

    def create_release(
        self,
        version: str,
        artifacts: list[Path],
        changelog: str,
    ) -> dict[str, Any]:
        """Stub that returns valid default values"""
        return {
            "status": "not_implemented",
            "team": "CI/CD",
            "release_url": "",
            "tag": "",
            "uploaded_artifacts": [],
        }

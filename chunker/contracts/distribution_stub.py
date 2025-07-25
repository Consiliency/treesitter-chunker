# File: chunker/contracts/distribution_stub.py
# Purpose: Concrete stub implementation for testing

from pathlib import Path
from typing import Any

from .distribution_contract import DistributionContract, ReleaseManagementContract


class DistributionStub(DistributionContract):
    """Stub implementation that can be instantiated and tested"""

    def publish_to_pypi(
        self,
        package_dir: Path,
        repository: str = "pypi",
        dry_run: bool = False,
    ) -> tuple[bool, dict[str, Any]]:
        """Stub that returns valid default values"""
        return (
            False,
            {
                "status": "not_implemented",
                "team": "Distribution",
                "repository": repository,
                "dry_run": dry_run,
                "uploaded": [],
                "errors": ["Distribution team will implement PyPI publishing"],
            },
        )

    def build_docker_image(
        self,
        tag: str,
        platforms: list[str] | None = None,
    ) -> tuple[bool, str]:
        """Stub that returns valid default values"""
        return (False, f"not-implemented-{tag}")

    def create_homebrew_formula(
        self,
        version: str,
        output_path: Path,
    ) -> tuple[bool, Path]:
        """Stub that returns valid default values"""
        stub_formula = output_path / f"treesitter-chunker-{version}.rb"
        return (False, stub_formula)

    def verify_installation(
        self,
        method: str,
        platform: str,
    ) -> tuple[bool, dict[str, Any]]:
        """Stub that returns valid default values"""
        return (
            False,
            {
                "status": "not_implemented",
                "team": "Distribution",
                "method": method,
                "platform": platform,
                "installed": False,
                "functional": False,
                "errors": [
                    "Distribution team will implement installation verification",
                ],
            },
        )


class ReleaseManagementStub(ReleaseManagementContract):
    """Stub implementation for release management"""

    def prepare_release(
        self,
        version: str,
        changelog: str,
    ) -> tuple[bool, dict[str, Any]]:
        """Stub that returns valid default values"""
        return (
            False,
            {
                "status": "not_implemented",
                "team": "Distribution",
                "version": version,
                "tag": f"v{version}",
                "files_updated": [],
                "errors": ["Distribution team will implement release preparation"],
            },
        )

    def create_release_artifacts(self, version: str, output_dir: Path) -> list[Path]:
        """Stub that returns valid default values"""
        return []

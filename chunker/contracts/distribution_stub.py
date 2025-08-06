from pathlib import Path
from typing import Any

from .distribution_contract import DistributionContract, ReleaseManagementContract


class DistributionStub(DistributionContract):
    """Stub implementation that can be instantiated and tested"""

    @staticmethod
    def publish_to_pypi(
        _package_dir: Path,
        repository: str = "pypi",
        dry_run: bool = False,
    ) -> tuple[bool, dict[str, Any]]:
        """Stub that returns valid default values"""
        return False, {
            "status": "not_implemented",
            "team": "Distribution",
            "repository": repository,
            "dry_run": dry_run,
            "uploaded": [],
            "errors": ["Distribution team will implement PyPI publishing"],
        }

    @staticmethod
    def build_docker_image(
        tag: str,
        _platforms: list[str] | None = None,
    ) -> tuple[bool, str]:
        """Stub that returns valid default values"""
        return False, f"not-implemented-{tag}"

    @staticmethod
    def create_homebrew_formula(version: str, output_path: Path) -> tuple[bool, Path]:
        """Stub that returns valid default values"""
        stub_formula = output_path / f"treesitter-chunker-{version}.rb"
        return False, stub_formula

    @staticmethod
    def verify_installation(method: str, platform: str) -> tuple[bool, dict[str, Any]]:
        """Stub that returns valid default values"""
        return False, {
            "status": "not_implemented",
            "team": "Distribution",
            "method": method,
            "platform": platform,
            "installed": False,
            "functional": False,
            "errors": ["Distribution team will implement installation verification"],
        }


class ReleaseManagementStub(ReleaseManagementContract):
    """Stub implementation for release management"""

    @staticmethod
    def prepare_release(version: str, _changelog: str) -> tuple[bool, dict[str, Any]]:
        """Stub that returns valid default values"""
        return False, {
            "status": "not_implemented",
            "team": "Distribution",
            "version": version,
            "tag": f"v{version}",
            "files_updated": [],
            "errors": ["Distribution team will implement release preparation"],
        }

    @staticmethod
    def create_release_artifacts(_version: str, _output_dir: Path) -> list[Path]:
        """Stub that returns valid default values"""
        return []

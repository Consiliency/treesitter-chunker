"""
Contract for Distribution Component
Defines the interface for package distribution across platforms
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class DistributionContract(ABC):
    """Contract for package distribution"""

    @abstractmethod
    def publish_to_pypi(
        self,
        package_dir: Path,
        repository: str = "pypi",
        dry_run: bool = False,
    ) -> tuple[bool, dict[str, Any]]:
        """
        Publish package to PyPI or TestPyPI

        Args:
            package_dir: Directory containing built distributions
            repository: Target repository (pypi or testpypi)
            dry_run: Perform validation without uploading

        Returns:
            Tuple of (success, upload_info)

        Preconditions:
            - Package files exist in package_dir
            - PyPI credentials are configured
            - Package passes twine check

        Postconditions:
            - Package is uploaded to repository (unless dry_run)
            - Upload info includes URLs and hashes
        """
        raise NotImplementedError("Distribution team will implement")

    @abstractmethod
    def build_docker_image(
        self,
        tag: str,
        platforms: list[str] | None = None,
    ) -> tuple[bool, str]:
        """
        Build Docker image for distribution

        Args:
            tag: Docker image tag
            platforms: List of platforms (linux/amd64, linux/arm64)

        Returns:
            Tuple of (success, image_id)

        Preconditions:
            - Dockerfile exists and is valid
            - Docker daemon is running

        Postconditions:
            - Multi-platform image is built
            - Image includes all dependencies
        """
        raise NotImplementedError("Distribution team will implement")

    @abstractmethod
    def create_homebrew_formula(
        self,
        version: str,
        output_path: Path,
    ) -> tuple[bool, Path]:
        """
        Generate Homebrew formula for macOS distribution

        Args:
            version: Package version
            output_path: Path for formula file

        Returns:
            Tuple of (success, formula_path)

        Preconditions:
            - Package metadata is available
            - Version follows semantic versioning

        Postconditions:
            - Valid Homebrew formula is created
            - Formula includes all dependencies
        """
        raise NotImplementedError("Distribution team will implement")

    @abstractmethod
    def verify_installation(
        self,
        method: str,
        platform: str,
    ) -> tuple[bool, dict[str, Any]]:
        """
        Verify package installs correctly via specified method

        Args:
            method: Installation method (pip, conda, docker, homebrew)
            platform: Target platform

        Returns:
            Tuple of (success, verification_details)

        Preconditions:
            - Package is published via method
            - Clean test environment available

        Postconditions:
            - Installation is tested end-to-end
            - All functionality is verified
        """
        raise NotImplementedError("Distribution team will implement")


class ReleaseManagementContract(ABC):
    """Contract for release process management"""

    @abstractmethod
    def prepare_release(
        self,
        version: str,
        changelog: str,
    ) -> tuple[bool, dict[str, Any]]:
        """
        Prepare a new release with version bump and changelog

        Args:
            version: New version number
            changelog: Release notes

        Returns:
            Tuple of (success, release_info)

        Preconditions:
            - Version is higher than current
            - All tests pass

        Postconditions:
            - Version is updated in all files
            - Changelog is updated
            - Git tag is created
        """
        raise NotImplementedError("Distribution team will implement")

    @abstractmethod
    def create_release_artifacts(self, version: str, output_dir: Path) -> list[Path]:
        """
        Create all release artifacts for distribution

        Args:
            version: Release version
            output_dir: Directory for artifacts

        Returns:
            List of created artifact paths

        Preconditions:
            - Source code is tagged with version
            - Build system is configured

        Postconditions:
            - All distribution artifacts are created
            - Artifacts are signed/checksummed
        """
        raise NotImplementedError("Distribution team will implement")

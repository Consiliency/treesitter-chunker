"""
Main Distributor Implementation

Implements the distribution contracts for the treesitter chunker
"""

from pathlib import Path
from typing import Any

from chunker.contracts.distribution_contract import (
    DistributionContract,
    ReleaseManagementContract,
)

from .docker_builder import DockerBuilder
from .homebrew_generator import HomebrewFormulaGenerator
from .pypi_publisher import PyPIPublisher
from .release_manager import ReleaseManager
from .verifier import InstallationVerifier


class Distributor(DistributionContract, ReleaseManagementContract):
    """Main distributor implementing all distribution contracts"""

    def __init__(self, project_root: Path | None = None):
        self.project_root = project_root or Path.cwd()
        self.pypi_publisher = PyPIPublisher()
        self.docker_builder = DockerBuilder()
        self.homebrew_generator = HomebrewFormulaGenerator()
        self.release_manager = ReleaseManager(self.project_root)
        self.verifier = InstallationVerifier()

    # DistributionContract implementation

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
        """
        return self.pypi_publisher.publish(package_dir, repository, dry_run)

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
        """
        # Look for Dockerfile in project root
        dockerfile_path = self.project_root / "Dockerfile"
        if not dockerfile_path.exists():
            # Try Alpine variant
            dockerfile_path = self.project_root / "Dockerfile.alpine"

        return self.docker_builder.build_image(tag, platforms, dockerfile_path)

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
        """
        return self.homebrew_generator.generate_formula(version, output_path)

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
        """
        return self.verifier.verify_installation(method, platform)

    # ReleaseManagementContract implementation

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
        """
        return self.release_manager.prepare_release(version, changelog)

    def create_release_artifacts(self, version: str, output_dir: Path) -> list[Path]:
        """
        Create all release artifacts for distribution

        Args:
            version: Release version
            output_dir: Directory for artifacts

        Returns:
            List of created artifact paths
        """
        return self.release_manager.create_release_artifacts(version, output_dir)

    # Additional helper methods

    def full_release_workflow(
        self,
        version: str,
        changelog: str,
        publish: bool = False,
    ) -> dict[str, Any]:
        """
        Execute complete release workflow

        Args:
            version: New version number
            changelog: Release notes
            publish: Whether to publish to distribution channels

        Returns:
            Dictionary with workflow results
        """
        results = {
            "version": version,
            "prepare": {},
            "artifacts": [],
            "docker": {},
            "homebrew": {},
            "pypi": {},
            "verification": {},
        }

        # Prepare release
        success, info = self.prepare_release(version, changelog)
        results["prepare"] = info
        if not success:
            return results

        # Create artifacts
        output_dir = self.project_root / "dist"
        artifacts = self.create_release_artifacts(version, output_dir)
        results["artifacts"] = [str(a) for a in artifacts]

        if publish:
            # Build Docker image
            success, image_id = self.build_docker_image(f"treesitter-chunker:{version}")
            results["docker"] = {"success": success, "image_id": image_id}

            # Create Homebrew formula
            formula_dir = self.project_root / "homebrew"
            success, formula_path = self.create_homebrew_formula(version, formula_dir)
            results["homebrew"] = {
                "success": success,
                "formula_path": str(formula_path),
            }

            # Publish to PyPI (TestPyPI first for safety)
            success, pypi_info = self.publish_to_pypi(output_dir, "testpypi")
            results["pypi"]["testpypi"] = {"success": success, "info": pypi_info}

            # Verify installations
            for method in ["pip", "docker"]:
                success, details = self.verify_installation(method, "linux")
                results["verification"][method] = {
                    "success": success,
                    "details": details,
                }

        return results

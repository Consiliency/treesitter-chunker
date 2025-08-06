"""
Contract for Build System Component
Defines the interface for cross-platform build support
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class BuildSystemContract(ABC):
    """Contract for cross-platform build system"""

    @staticmethod
    @abstractmethod
    def compile_grammars(
        languages: list[str],
        platform: str,
        output_dir: Path,
    ) -> tuple[bool, dict[str, Any]]:
        """
        Compile tree-sitter grammars for specified platform

        Args:
            languages: List of languages to compile
            platform: Target platform (windows, macos, linux)
            output_dir: Directory for compiled outputs

        Returns:
            Tuple of (success, build_info) with paths and metadata

        Preconditions:
            - Grammar sources are available
            - Platform toolchain is installed
            - Output directory is writable

        Postconditions:
            - Compiled libraries exist in output_dir
            - Libraries are compatible with target platform
        """
        raise NotImplementedError("Build team will implement")

    @staticmethod
    @abstractmethod
    def build_wheel(
        platform: str,
        python_version: str,
        output_dir: Path,
    ) -> tuple[bool, Path]:
        """
        Build platform-specific wheel for distribution

        Args:
            platform: Target platform identifier
            python_version: Python version (e.g., "cp39")
            output_dir: Directory for wheel output

        Returns:
            Tuple of (success, wheel_path)

        Preconditions:
            - Build dependencies are installed
            - Grammars are compiled for platform

        Postconditions:
            - Wheel is created with correct platform tag
            - Wheel includes all necessary files
        """
        raise NotImplementedError("Build team will implement")

    @staticmethod
    @abstractmethod
    def create_conda_package(platform: str, output_dir: Path) -> tuple[bool, Path]:
        """
        Create conda package for distribution

        Args:
            platform: Target platform
            output_dir: Directory for package output

        Returns:
            Tuple of (success, package_path)

        Preconditions:
            - Conda build tools are available
            - meta.yaml is configured

        Postconditions:
            - Conda package is created
            - Package includes all dependencies
        """
        raise NotImplementedError("Build team will implement")

    @staticmethod
    @abstractmethod
    def verify_build(artifact_path: Path, platform: str) -> tuple[bool, dict[str, Any]]:
        """
        Verify build artifact is correctly constructed

        Args:
            artifact_path: Path to built artifact
            platform: Expected platform

        Returns:
            Tuple of (valid, verification_report)

        Preconditions:
            - Artifact exists
            - Verification tools available

        Postconditions:
            - Returns detailed verification results
            - Checks all required components
        """
        raise NotImplementedError("Build team will implement")


class PlatformSupportContract(ABC):
    """Contract for platform-specific support"""

    @staticmethod
    @abstractmethod
    def detect_platform() -> dict[str, str]:
        """
        Detect current platform details

        Returns:
            Platform info including OS, arch, python version

        Postconditions:
            - Returns accurate platform information
            - Includes all relevant details for building
        """
        raise NotImplementedError("Build team will implement")

    @staticmethod
    @abstractmethod
    def install_build_dependencies(platform: str) -> bool:
        """
        Install platform-specific build dependencies

        Args:
            platform: Target platform

        Returns:
            True if all dependencies installed successfully

        Postconditions:
            - All required build tools are available
            - System is ready for compilation
        """
        raise NotImplementedError("Build team will implement")

"""
Build System implementation that wraps the actual BuildSystem class
"""

from pathlib import Path
from typing import Any

from chunker.contracts.build_contract import (
    BuildSystemContract,
    PlatformSupportContract,
)

from .builder import BuildSystem
from .platform import PlatformSupport


class BuildSystemImpl(BuildSystemContract):
    """Implementation wrapper for BuildSystem that matches contract exactly"""

    def __init__(self):
        self._build_system = BuildSystem()

    def compile_grammars(
        self,
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
        """
        return self._build_system.compile_grammars(languages, platform, output_dir)

    def build_wheel(
        self,
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
        """
        return self._build_system.build_wheel(platform, python_version, output_dir)

    def create_conda_package(
        self,
        platform: str,
        output_dir: Path,
    ) -> tuple[bool, Path]:
        """
        Create conda package for distribution

        Args:
            platform: Target platform
            output_dir: Directory for package output

        Returns:
            Tuple of (success, package_path)
        """
        return self._build_system.create_conda_package(platform, output_dir)

    def verify_build(
        self,
        artifact_path: Path,
        platform: str,
    ) -> tuple[bool, dict[str, Any]]:
        """
        Verify build artifact is correctly constructed

        Args:
            artifact_path: Path to built artifact
            platform: Expected platform

        Returns:
            Tuple of (valid, verification_report)
        """
        return self._build_system.verify_build(artifact_path, platform)


class PlatformSupportImpl(PlatformSupportContract):
    """Implementation wrapper for PlatformSupport that matches contract exactly"""

    def __init__(self):
        self._platform_support = PlatformSupport()

    def detect_platform(self) -> dict[str, str]:
        """
        Detect current platform details

        Returns:
            Platform info including OS, arch, python version
        """
        return self._platform_support.detect_platform()

    def install_build_dependencies(self, platform: str) -> bool:
        """
        Install platform-specific build dependencies

        Args:
            platform: Target platform

        Returns:
            True if all dependencies installed successfully
        """
        return self._platform_support.install_build_dependencies(platform)

from pathlib import Path
from typing import Any

from .build_contract import BuildSystemContract, PlatformSupportContract


class BuildSystemStub(BuildSystemContract):
    """Stub implementation that can be instantiated and tested"""

    @staticmethod
    def compile_grammars(
        languages: list[str],
        platform: str,
        output_dir: Path,
    ) -> tuple[bool, dict[str, Any]]:
        """Stub that returns valid default values"""
        return False, {
            "status": "not_implemented",
            "team": "Build",
            "compiled": [],
            "errors": ["Build team will implement grammar compilation"],
            "output_files": [],
        }

    @staticmethod
    def build_wheel(
        platform: str,
        python_version: str,
        output_dir: Path,
    ) -> tuple[bool, Path]:
        """Stub that returns valid default values"""
        stub_wheel = (
            output_dir / f"treesitter_chunker-0.0.0-{python_version}-{platform}.whl"
        )
        return False, stub_wheel

    @staticmethod
    def create_conda_package(platform: str, output_dir: Path) -> tuple[bool, Path]:
        """Stub that returns valid default values"""
        stub_package = output_dir / f"treesitter-chunker-0.0.0-{platform}.tar.bz2"
        return False, stub_package

    @staticmethod
    def verify_build(
        artifact_path: Path,
        platform: str,
    ) -> tuple[bool, dict[str, Any]]:
        """Stub that returns valid default values"""
        return False, {
            "status": "not_implemented",
            "team": "Build",
            "valid": False,
            "errors": ["Build team will implement verification"],
            "components": [],
            "platform_match": False,
        }


class PlatformSupportStub(PlatformSupportContract):
    """Stub implementation for platform support"""

    @staticmethod
    def detect_platform() -> dict[str, str]:
        """Stub that returns valid default values"""
        return {
            "status": "not_implemented",
            "team": "Build",
            "os": "unknown",
            "arch": "unknown",
            "python_version": "unknown",
            "platform_tag": "unknown",
        }

    @staticmethod
    def install_build_dependencies(_platform: str) -> bool:
        """Stub that returns valid default values"""
        return False

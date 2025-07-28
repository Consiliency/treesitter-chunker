"""
Cross-compilation support for building wheels for different platforms
"""

import subprocess
from pathlib import Path
from typing import Any

from .builder import BuildSystem
from .platform import PlatformSupport


class CrossCompiler:
    """Support for cross-platform compilation"""

    def __init__(self):
        self.build_system = BuildSystem()
        self.platform = PlatformSupport()

    def build_for_platforms(
        self,
        platforms: list[str],
        output_dir: Path,
    ) -> dict[str, tuple[bool, Path]]:
        """
        Build wheels for multiple platforms

        Args:
            platforms: List of target platforms
            output_dir: Output directory for wheels

        Returns:
            Dict mapping platform to (success, wheel_path)
        """
        results = {}
        current_platform = self.platform.detect_platform()

        for platform in platforms:
            print(f"\nBuilding for {platform}...")

            if platform == current_platform["os"]:
                # Native build
                success, wheel = self.build_system.build_wheel(
                    platform, current_platform["python_tag"], output_dir,
                )
                results[platform] = (success, wheel)
            else:
                # Cross-compilation attempt
                success, wheel = self._cross_compile(
                    platform, current_platform["python_tag"], output_dir,
                )
                results[platform] = (success, wheel)

        return results

    def _cross_compile(
        self,
        target_platform: str,
        python_version: str,
        output_dir: Path,
    ) -> tuple[bool, Path]:
        """
        Attempt cross-compilation for target platform

        This is a placeholder - real cross-compilation would require:
        - Target platform toolchains
        - Cross-compilers
        - Platform-specific SDKs
        """
        print(f"  Cross-compilation for {target_platform} not yet implemented")
        print("  Consider using Docker or CI/CD for multi-platform builds")

        return False, Path()

    def build_manylinux_wheel(
        self,
        output_dir: Path,
        manylinux_version: str = "manylinux2014",
    ) -> tuple[bool, Path]:
        """
        Build manylinux-compatible wheel using Docker

        Args:
            output_dir: Output directory
            manylinux_version: manylinux standard to use

        Returns:
            Tuple of (success, wheel_path)
        """
        # Check if Docker is available
        try:
            result = subprocess.run(
                ["docker", "--version"], capture_output=True, timeout=5, check=False,
            )
            if result.returncode != 0:
                print("Docker not available for manylinux builds")
                return False, Path()
        except (subprocess.SubprocessError, FileNotFoundError):
            print("Docker not found - required for manylinux builds")
            return False, Path()

        # Use appropriate manylinux image
        image = f"quay.io/pypa/{manylinux_version}_x86_64"

        # Build command
        project_root = Path(__file__).parent.parent.parent
        cmd = [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{project_root}:/project",
            "-v",
            f"{output_dir}:/output",
            image,
            "/bin/bash",
            "-c",
            "cd /project && python -m pip wheel . -w /output",
        ]

        try:
            print(f"Building manylinux wheel using {image}...")
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)

            if result.returncode == 0:
                # Find the built wheel
                wheels = list(output_dir.glob("*.whl"))
                if wheels:
                    # Audit and repair the wheel for manylinux compatibility
                    wheel_path = wheels[0]
                    repaired_wheel = self._repair_wheel(wheel_path, output_dir, image)
                    return True, repaired_wheel
            else:
                print(f"manylinux build failed: {result.stderr}")

        except Exception as e:
            print(f"manylinux build error: {e}")

        return False, Path()

    def _repair_wheel(
        self,
        wheel_path: Path,
        output_dir: Path,
        image: str,
    ) -> Path:
        """Repair wheel for manylinux compatibility using auditwheel"""
        cmd = [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{wheel_path.parent}:/wheels",
            "-v",
            f"{output_dir}:/output",
            image,
            "auditwheel",
            "repair",
            f"/wheels/{wheel_path.name}",
            "-w",
            "/output",
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if result.returncode == 0:
                # Find repaired wheel
                repaired = list(output_dir.glob("*manylinux*.whl"))
                if repaired:
                    return repaired[0]
        except Exception:
            pass

        return wheel_path

    def get_supported_platforms(self) -> dict[str, dict[str, Any]]:
        """
        Get information about supported build platforms

        Returns:
            Dict of platform info
        """
        return {
            "native": {
                "platform": self.platform.detect_platform()["os"],
                "arch": self.platform.detect_platform()["arch"],
                "compiler": self.platform.detect_platform()["compiler"],
                "available": True,
            },
            "manylinux": {
                "versions": [
                    "manylinux1",
                    "manylinux2010",
                    "manylinux2014",
                    "manylinux_2_28",
                ],
                "available": self._check_docker(),
                "requires": "Docker",
            },
            "cross_compile": {
                "targets": ["windows", "macos", "linux"],
                "available": False,
                "note": "Use CI/CD or platform-specific build environments",
            },
        }

    def _check_docker(self) -> bool:
        """Check if Docker is available"""
        try:
            result = subprocess.run(
                ["docker", "--version"], capture_output=True, timeout=5, check=False,
            )
            return result.returncode == 0
        except (subprocess.SubprocessError, FileNotFoundError):
            return False

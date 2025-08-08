"""
Cross-platform wheel building script for treesitter-chunker.

This script handles building platform-specific wheels with compiled grammars.
"""

import argparse
import os
import platform
import subprocess
import sys
from pathlib import Path

from build.env import IsolatedEnvBuilder

from build import ProjectBuilder

try:
    pass
except ImportError:
    print("Please install 'build' package: pip install build")
    sys.exit(1)


class WheelBuilder:
    """Handles cross-platform wheel building."""

    def __init__(self, project_dir: Path, output_dir: Path):
        self.project_dir = project_dir
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def detect_platform() -> str:
        """Detect current platform."""
        system = platform.system().lower()
        machine = platform.machine().lower()
        if system == "darwin":
            if machine == "x86_64":
                return "macosx_10_9_x86_64"
            if machine == "arm64":
                return "macosx_11_0_arm64"
            return "macosx_10_9_universal2"
        if system == "linux":
            if machine in {"x86_64", "amd64"}:
                return "manylinux2014_x86_64"
            if machine == "aarch64":
                return "manylinux2014_aarch64"
            return f"linux_{machine}"
        if system == "windows":
            if machine in {"x86_64", "amd64"}:
                return "win_amd64"
            return "win32"
        return "any"

    def ensure_grammars_built(self):
        """Ensure grammars are fetched and built."""
        scripts_dir = self.project_dir / "scripts"
        grammars_dir = self.project_dir / "grammars"
        if not grammars_dir.exists() or not any(grammars_dir.iterdir()):
            print("Fetching grammars...")
            subprocess.run(
                [sys.executable, str(scripts_dir / "fetch_grammars.py")],
                cwd=self.project_dir,
                check=True,
            )
        print("Building tree-sitter grammars...")
        subprocess.run(
            [sys.executable, str(scripts_dir / "build_lib.py")],
            cwd=self.project_dir,
            check=True,
        )

    def build_sdist(self):
        """Build source distribution."""
        print("Building source distribution...")
        builder = ProjectBuilder(str(self.project_dir))
        with IsolatedEnvBuilder() as env:
            builder.python_executable = env.executable
            builder.scripts_dir = env.scripts_dir
            builder.install_build_deps()
            sdist_path = builder.build("sdist", str(self.output_dir))
            print(f"Built sdist: {sdist_path}")

    def build_wheel(self, universal: bool = False):
        """Build platform-specific or universal wheel."""
        self.ensure_grammars_built()
        print(
            f"Building {'universal' if universal else 'platform-specific'} wheel...",
        )
        builder = ProjectBuilder(str(self.project_dir))
        with IsolatedEnvBuilder() as env:
            builder.python_executable = env.executable
            builder.scripts_dir = env.scripts_dir
            builder.install_build_deps()
            config_settings = {}
            if not universal:
                platform_tag = self.detect_platform()
                config_settings["--plat-name"] = platform_tag
            wheel_path = builder.build(
                "wheel",
                str(self.output_dir),
                config_settings=config_settings,
            )
            print(f"Built wheel: {wheel_path}")
            return wheel_path

    def build_universal_wheel(self):
        """Build universal wheel (pure Python with included binaries)."""
        self.ensure_grammars_built()
        self.project_dir / "build"
        wheel_build_dir = self.output_dir / "wheel_build"
        wheel_build_dir.mkdir(exist_ok=True)
        wheel_path = self.build_wheel(universal=True)
        return wheel_path

    def build_manylinux_wheels(self):
        """Build manylinux wheels using docker."""
        print("Building manylinux wheels...")
        env = os.environ.copy()
        env["CIBW_BUILD"] = "cp310-* cp311-* cp312-*"
        env["CIBW_SKIP"] = "*-musllinux_i686 *-win32 pp*"
        env["CIBW_ARCHS_LINUX"] = "x86_64 aarch64"
        env["CIBW_MANYLINUX_X86_64_IMAGE"] = "manylinux2014"
        env["CIBW_MANYLINUX_AARCH64_IMAGE"] = "manylinux2014"
        env["CIBW_OUTPUT_DIR"] = str(self.output_dir)
        subprocess.run(
            ["cibuildwheel", "--platform", "linux"],
            cwd=self.project_dir,
            env=env,
            check=True,
        )

    def build_all(self, platforms: list[str] | None = None):
        """Build wheels for all specified platforms."""
        if platforms is None:
            platforms = [self.detect_platform()]
        self.build_sdist()
        for plat in platforms:
            if plat == "manylinux":
                self.build_manylinux_wheels()
            else:
                self.build_wheel()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Build wheels for treesitter-chunker")
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=Path("dist"),
        help="Output directory for wheels",
    )
    parser.add_argument(
        "--platform",
        "-p",
        choices=["auto", "manylinux", "macos", "windows", "universal"],
        default="auto",
        help="Target platform",
    )
    parser.add_argument(
        "--sdist-only",
        action="store_true",
        help="Only build source distribution",
    )
    parser.add_argument(
        "--wheel-only",
        action="store_true",
        help="Only build wheel (no sdist)",
    )
    args = parser.parse_args()
    project_dir = Path(__file__).parent.parent.absolute()
    builder = WheelBuilder(project_dir, args.output)
    if args.sdist_only:
        builder.build_sdist()
    elif args.wheel_only:
        if args.platform == "manylinux":
            builder.build_manylinux_wheels()
        elif args.platform == "universal":
            builder.build_universal_wheel()
        else:
            builder.build_wheel()
    elif args.platform == "auto":
        builder.build_all()
    elif args.platform == "manylinux":
        builder.build_all(["manylinux"])
    elif args.platform == "universal":
        builder.build_sdist()
        builder.build_universal_wheel()
    else:
        builder.build_all([args.platform])


if __name__ == "__main__":
    main()

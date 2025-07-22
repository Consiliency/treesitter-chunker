#!/usr/bin/env python3
"""
Cross-platform wheel building script for treesitter-chunker.

This script handles building platform-specific wheels with compiled grammars.
"""

import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

try:
    from build import ProjectBuilder
    from build.env import IsolatedEnvBuilder
except ImportError:
    print("Please install 'build' package: pip install build")
    sys.exit(1)


class WheelBuilder:
    """Handles cross-platform wheel building."""
    
    def __init__(self, project_dir: Path, output_dir: Path):
        self.project_dir = project_dir
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
    def detect_platform(self) -> str:
        """Detect current platform."""
        system = platform.system().lower()
        machine = platform.machine().lower()
        
        if system == "darwin":
            if machine == "x86_64":
                return "macosx_10_9_x86_64"
            elif machine == "arm64":
                return "macosx_11_0_arm64"
            else:
                return "macosx_10_9_universal2"
        elif system == "linux":
            if machine in ("x86_64", "amd64"):
                return "manylinux2014_x86_64"
            elif machine == "aarch64":
                return "manylinux2014_aarch64"
            else:
                return f"linux_{machine}"
        elif system == "windows":
            if machine in ("x86_64", "amd64"):
                return "win_amd64"
            else:
                return "win32"
        else:
            return "any"
    
    def ensure_grammars_built(self):
        """Ensure grammars are fetched and built."""
        scripts_dir = self.project_dir / "scripts"
        
        # Check if grammars exist
        grammars_dir = self.project_dir / "grammars"
        if not grammars_dir.exists() or not any(grammars_dir.iterdir()):
            print("Fetching grammars...")
            subprocess.run([sys.executable, str(scripts_dir / "fetch_grammars.py")], 
                         cwd=self.project_dir, check=True)
        
        # Build the shared library
        print("Building tree-sitter grammars...")
        subprocess.run([sys.executable, str(scripts_dir / "build_lib.py")], 
                     cwd=self.project_dir, check=True)
    
    def build_sdist(self):
        """Build source distribution."""
        print("Building source distribution...")
        builder = ProjectBuilder(str(self.project_dir))
        
        with IsolatedEnvBuilder() as env:
            builder.python_executable = env.executable
            builder.scripts_dir = env.scripts_dir
            
            # Install build dependencies
            builder.install_build_deps()
            
            # Build sdist
            sdist_path = builder.build('sdist', str(self.output_dir))
            print(f"Built sdist: {sdist_path}")
    
    def build_wheel(self, universal: bool = False):
        """Build platform-specific or universal wheel."""
        self.ensure_grammars_built()
        
        print(f"Building {'universal' if universal else 'platform-specific'} wheel...")
        builder = ProjectBuilder(str(self.project_dir))
        
        with IsolatedEnvBuilder() as env:
            builder.python_executable = env.executable
            builder.scripts_dir = env.scripts_dir
            
            # Install build dependencies
            builder.install_build_deps()
            
            # Set platform tag
            config_settings = {}
            if not universal:
                platform_tag = self.detect_platform()
                config_settings['--plat-name'] = platform_tag
            
            # Build wheel
            wheel_path = builder.build('wheel', str(self.output_dir), 
                                     config_settings=config_settings)
            print(f"Built wheel: {wheel_path}")
            
            return wheel_path
    
    def build_universal_wheel(self):
        """Build universal wheel (pure Python with included binaries)."""
        # First ensure grammars are built
        self.ensure_grammars_built()
        
        # Copy platform-specific binaries
        build_dir = self.project_dir / "build"
        wheel_build_dir = self.output_dir / "wheel_build"
        wheel_build_dir.mkdir(exist_ok=True)
        
        # Build a standard wheel
        wheel_path = self.build_wheel(universal=True)
        
        return wheel_path
    
    def build_manylinux_wheels(self):
        """Build manylinux wheels using docker."""
        print("Building manylinux wheels...")
        
        # Use cibuildwheel for manylinux builds
        env = os.environ.copy()
        env['CIBW_BUILD'] = 'cp310-* cp311-* cp312-*'
        env['CIBW_SKIP'] = '*-musllinux_i686 *-win32 pp*'
        env['CIBW_ARCHS_LINUX'] = 'x86_64 aarch64'
        env['CIBW_MANYLINUX_X86_64_IMAGE'] = 'manylinux2014'
        env['CIBW_MANYLINUX_AARCH64_IMAGE'] = 'manylinux2014'
        env['CIBW_OUTPUT_DIR'] = str(self.output_dir)
        
        subprocess.run(['cibuildwheel', '--platform', 'linux'], 
                      cwd=self.project_dir, env=env, check=True)
    
    def build_all(self, platforms: Optional[List[str]] = None):
        """Build wheels for all specified platforms."""
        if platforms is None:
            platforms = [self.detect_platform()]
        
        # Always build source distribution
        self.build_sdist()
        
        # Build wheels for each platform
        for plat in platforms:
            if plat == "manylinux":
                self.build_manylinux_wheels()
            else:
                self.build_wheel()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Build wheels for treesitter-chunker"
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=Path("dist"),
        help="Output directory for wheels"
    )
    parser.add_argument(
        "--platform", "-p",
        choices=["auto", "manylinux", "macos", "windows", "universal"],
        default="auto",
        help="Target platform"
    )
    parser.add_argument(
        "--sdist-only",
        action="store_true",
        help="Only build source distribution"
    )
    parser.add_argument(
        "--wheel-only",
        action="store_true",
        help="Only build wheel (no sdist)"
    )
    
    args = parser.parse_args()
    
    # Find project directory
    project_dir = Path(__file__).parent.parent.absolute()
    
    # Create builder
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
    else:
        if args.platform == "auto":
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
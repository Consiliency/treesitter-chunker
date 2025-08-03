"""
Packaging automation script for treesitter-chunker.

This script automates the entire packaging process including:
- Building source distributions and wheels
- Creating platform-specific packages
- Generating checksums
- Preparing release artifacts
"""
import argparse
import hashlib
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

import requests
import toml

try:
    pass
except ImportError:
    requests = None


class PackageAutomation:
    """Handles automated packaging tasks."""

    def __init__(self, project_dir: Path, version: (str | None) = None):
        self.project_dir = project_dir
        self.version = version or self._get_version()
        self.dist_dir = project_dir / "dist"
        self.dist_dir.mkdir(exist_ok=True)

    def _get_version(self) -> str:
        """Extract version from pyproject.toml."""
        pyproject_path = self.project_dir / "pyproject.toml"
        if pyproject_path.exists():
            data = toml.load(pyproject_path)
            return data.get("project", {}).get("version", "0.1.0")
        return "0.1.0"

    def clean_dist(self):
        """Clean distribution directory."""
        if self.dist_dir.exists():
            shutil.rmtree(self.dist_dir)
        self.dist_dir.mkdir()
        print(f"Cleaned {self.dist_dir}")

    def build_all(self):
        """Build all distribution formats."""
        print(f"Building packages for version {self.version}")
        self._build_grammars()
        self._build_sdist()
        self._build_wheels()
        self._generate_checksums()
        print(f"\nBuild complete! Artifacts in {self.dist_dir}")

    def _build_grammars(self):
        """Ensure grammars are fetched and built."""
        scripts_dir = self.project_dir / "scripts"
        print("Building tree-sitter grammars...")
        subprocess.run([sys.executable, str(scripts_dir /
            "fetch_grammars.py")], cwd=self.project_dir, check=True)
        subprocess.run([sys.executable, str(scripts_dir / "build_lib.py")],
            cwd=self.project_dir, check=True)

    def _build_sdist(self):
        """Build source distribution."""
        print("\nBuilding source distribution...")
        subprocess.run([sys.executable, "-m", "build", "--sdist",
            "--outdir", str(self.dist_dir)], cwd=self.project_dir, check=True)

    def _build_wheels(self):
        """Build platform wheels."""
        print("\nBuilding wheels...")
        subprocess.run([sys.executable, "-m", "build", "--wheel",
            "--outdir", str(self.dist_dir)], cwd=self.project_dir, check=True)
        if shutil.which("cibuildwheel"):
            self._build_platform_wheels()

    def _build_platform_wheels(self):
        """Build platform-specific wheels using cibuildwheel."""
        print("\nBuilding platform-specific wheels...")
        system = platform.system().lower()
        if system == "linux":
            subprocess.run(["cibuildwheel", "--platform", "linux"], check=False, cwd=self.project_dir, env={**os.environ,
                "CIBW_OUTPUT_DIR": str(self.dist_dir)})
        elif system == "darwin":
            subprocess.run(["cibuildwheel", "--platform", "macos"], check=False, cwd=self.project_dir, env={**os.environ,
                "CIBW_OUTPUT_DIR": str(self.dist_dir)})
        elif system == "windows":
            subprocess.run(["cibuildwheel", "--platform", "windows"], check=False, cwd=self.project_dir, env={**os.environ,
                "CIBW_OUTPUT_DIR": str(self.dist_dir)})

    def _generate_checksums(self):
        """Generate checksums for all artifacts."""
        print("\nGenerating checksums...")
        checksums = {}
        for file_path in self.dist_dir.glob("*"):
            if file_path.is_file() and not file_path.name.endswith(".sha256"):
                sha256 = self._calculate_sha256(file_path)
                checksums[file_path.name] = sha256
                with Path(f"{file_path}.sha256").open("w", encoding="utf-8",
                    ) as f:
                    f.write(f"{sha256}  {file_path.name}\n")
        with Path(self.dist_dir / "checksums.txt").open("w", encoding="utf-8",
            ) as f:
            for filename, checksum in sorted(checksums.items()):
                f.write(f"{checksum}  {filename}\n")
        print(f"Generated checksums for {len(checksums)} files")

    @classmethod
    def _calculate_sha256(cls, file_path: Path) -> str:
        """Calculate SHA256 checksum of a file."""
        sha256_hash = hashlib.sha256()
        with Path(file_path).open("rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def prepare_release(self, output_dir: (Path | None) = None):
        """Prepare release artifacts."""
        output_dir = output_dir or self.project_dir / "release"
        output_dir.mkdir(exist_ok=True)
        print(f"\nPreparing release artifacts in {output_dir}")
        dist_output = output_dir / "dist"
        if dist_output.exists():
            shutil.rmtree(dist_output)
        shutil.copytree(self.dist_dir, dist_output)
        self._create_release_notes(output_dir)
        self._create_test_script(output_dir)
        self._package_docker(output_dir)
        print(f"\nRelease artifacts prepared in {output_dir}")

    def _create_release_notes(self, output_dir: Path):
        """Create release notes template."""
        notes_path = output_dir / f"RELEASE_NOTES_{self.version}.md"
        template = f"""# Release Notes - v{self.version}

## Installation

```bash
pip install treesitter-chunker=={self.version}
```

## What's New

- [Add release highlights here]

## Features

- [List new features]

## Bug Fixes

- [List bug fixes]

## Breaking Changes

- [List any breaking changes]

## Contributors

- [List contributors]

## Checksums

See `dist/checksums.txt` for SHA256 checksums of all release artifacts.
"""
        with Path(notes_path).open("w", encoding="utf-8") as f:
            f.write(template)
        print(f"Created release notes template: {notes_path}")

    @classmethod
    def _create_test_script(cls, output_dir: Path):
        """Create installation test script."""
        script_path = output_dir / "test_installation.py"
        script = """#!/usr/bin/env python3
""\"Test installation of treesitter-chunker.""\"

import subprocess
import sys
import tempfile
from pathlib import Path


def test_installation():
    ""\"Test the installation.""\"
    print("Testing treesitter-chunker installation...")

    # Test import
    try:
        import chunker
        print("✓ Import successful")
    except ImportError as e:
        print(f"✗ Import failed: {e}")
        return False

    # Test CLI
    try:
        result = subprocess.run(
            [sys.executable, "-m", "cli.main", "--version"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            print(f"✓ CLI working: {result.stdout.strip()}")
        else:
            print(f"✗ CLI failed: {result.stderr}")
            return False
    except (FileNotFoundError, IOError, IndexError) as e:
        print(f"✗ CLI test failed: {e}")
        return False

    # Test basic functionality
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("def test(): pass")
            temp_file = f.name

        result = subprocess.run(
            [sys.executable, "-m", "cli.main", "chunk", temp_file, "-l", "python"],
            capture_output=True,
            text=True
        )

        Path(temp_file).unlink()

        if result.returncode == 0:
            print("✓ Basic chunking works")
        else:
            print(f"✗ Chunking failed: {result.stderr}")
            return False
    except (FileNotFoundError, OSError, TypeError) as e:
        print(f"✗ Functionality test failed: {e}")
        return False

    print("\\nAll tests passed!")
    return True


if __name__ == "__main__":
    sys.exit(0 if test_installation() else 1)
"""
        with Path(script_path).open("w", encoding="utf-8") as f:
            f.write(script)
        script_path.chmod(493)
        print(f"Created test script: {script_path}")

    def _package_docker(self, output_dir: Path):
        """Package Docker images."""
        docker_dir = output_dir / "docker"
        docker_dir.mkdir(exist_ok=True)
        for dockerfile in ["Dockerfile", "Dockerfile.alpine"]:
            src = self.project_dir / dockerfile
            if src.exists():
                shutil.copy2(src, docker_dir / dockerfile)
        build_script = docker_dir / "build.sh"
        with Path(build_script).open("w", encoding="utf-8") as f:
            f.write(
                f"""#!/bin/bash
# Build Docker images for treesitter-chunker v{self.version}

echo "Building standard image..."
docker build -t treesitter-chunker:{self.version} -f Dockerfile ..

echo "Building Alpine image..."
docker build -t treesitter-chunker:{self.version}-alpine -f Dockerfile.alpine ..

echo "Tagging latest..."
docker tag treesitter-chunker:{self.version} treesitter-chunker:latest
docker tag treesitter-chunker:{self.version}-alpine treesitter-chunker:alpine

echo "Done! Images built:"
docker images | grep treesitter-chunker
""",
                )
        build_script.chmod(493)
        print(f"Created Docker build script: {build_script}")

    def upload_to_pypi(self, test: bool = True):
        """Upload packages to PyPI."""
        if test:
            print("\nUploading to Test PyPI...")
            repository = "testpypi"
            repo_url = "https://test.pypi.org/legacy/"
        else:
            print("\nUploading to PyPI...")
            repository = "pypi"
            repo_url = "https://upload.pypi.org/legacy/"
        if not shutil.which("twine"):
            print("Error: twine not installed. Run: pip install twine")
            return False
        cmd = ["twine", "upload", "--repository", repository,
            "--repository-url", repo_url, str(self.dist_dir / "*")]
        result = subprocess.run(cmd, check=False)
        return result.returncode == 0


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Automate packaging for treesitter-chunker")
    parser.add_argument("--version", help="Version to build (default: from pyproject.toml)")
    parser.add_argument("--clean", action="store_true", help="Clean dist directory before building")
    parser.add_argument("--release", action="store_true", help="Prepare full release artifacts")
    parser.add_argument("--upload", action="store_true", help="Upload to PyPI after building")
    parser.add_argument("--test-upload", action="store_true", help="Upload to Test PyPI after building")
    args = parser.parse_args()
    project_dir = Path(__file__).parent.parent.absolute()
    automation = PackageAutomation(project_dir, args.version)
    if args.clean:
        automation.clean_dist()
    automation.build_all()
    if args.release:
        automation.prepare_release()
    if args.test_upload:
        automation.upload_to_pypi(test=True)
    elif args.upload:
        automation.upload_to_pypi(test=False)


if __name__ == "__main__":
    main()

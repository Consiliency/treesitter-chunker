"""
Release Management Implementation

Implements the ReleaseManagementContract for release preparation and artifact creation
"""

import hashlib
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from chunker.contracts.distribution_contract import ReleaseManagementContract


class ReleaseManagementImpl(ReleaseManagementContract):
    """Implementation of the release management contract"""

    def __init__(self, project_root: Path | None = None):
        """Initialize the release manager"""
        self.project_root = project_root or Path.cwd()

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
        release_info = {
            "version": version,
            "tag": f"v{version}",
            "files_updated": [],
            "errors": [],
            "status": "pending",
        }

        # Validate version format
        if not re.match(r"^\d+\.\d+\.\d+(-\w+)?$", version):
            release_info["errors"].append(f"Invalid version format: {version}")
            release_info["status"] = "failed"
            return False, release_info

        # Get current version
        current_version = self._get_current_version()
        if current_version and not self._is_version_higher(version, current_version):
            release_info["errors"].append(
                f"Version {version} is not higher than current {current_version}",
            )
            release_info["status"] = "failed"
            return False, release_info

        # Update version in files
        version_files = [
            ("setup.py", r'version\s*=\s*["\']([^"\']+)["\']', f'version="{version}"'),
            (
                "pyproject.toml",
                r'version\s*=\s*["\']([^"\']+)["\']',
                f'version = "{version}"',
            ),
            (
                "chunker/__init__.py",
                r'__version__\s*=\s*["\']([^"\']+)["\']',
                f'__version__ = "{version}"',
            ),
        ]

        for filename, pattern, replacement in version_files:
            filepath = self.project_root / filename
            if filepath.exists():
                try:
                    content = filepath.read_text()
                    new_content = re.sub(pattern, replacement, content)
                    if new_content != content:
                        filepath.write_text(new_content)
                        release_info["files_updated"].append(str(filepath))
                except (OSError, FileNotFoundError, IndexError) as e:
                    release_info["errors"].append(
                        f"Failed to update {filename}: {e!s}",
                    )

        # Update CHANGELOG
        changelog_path = self.project_root / "CHANGELOG.md"
        try:
            if changelog_path.exists():
                existing_changelog = changelog_path.read_text()

                # Create new changelog entry
                date_str = datetime.now().strftime("%Y-%m-%d")
                new_entry = f"\n## [{version}] - {date_str}\n\n{changelog}\n"

                # Insert after the header
                lines = existing_changelog.split("\n")
                insert_pos = 0
                for i, line in enumerate(lines):
                    if line.startswith("# "):
                        insert_pos = i + 1
                        break

                lines.insert(insert_pos, new_entry)
                changelog_path.write_text("\n".join(lines))
                release_info["files_updated"].append(str(changelog_path))
            else:
                # Create new CHANGELOG
                changelog_content = f"""# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [{version}] - {datetime.now().strftime("%Y-%m-%d")}

{changelog}
"""
                changelog_path.write_text(changelog_content)
                release_info["files_updated"].append(str(changelog_path))

        except (OSError, FileNotFoundError, IndexError) as e:
            release_info["errors"].append(f"Failed to update CHANGELOG: {e!s}")

        # Create git tag (check if git is available)
        try:
            subprocess.run(["git", "--version"], capture_output=True, check=True)

            # Check if tag already exists
            result = subprocess.run(
                ["git", "tag", "-l", release_info["tag"]],
                capture_output=True,
                text=True,
                check=False,
            )

            if not result.stdout.strip():
                # Create annotated tag
                subprocess.run(
                    [
                        "git",
                        "tag",
                        "-a",
                        release_info["tag"],
                        "-m",
                        f"Release {version}\n\n{changelog}",
                    ],
                    check=True,
                )
                release_info["git_tag_created"] = True
            else:
                release_info["git_tag_created"] = False
                release_info["errors"].append(
                    f"Tag {release_info['tag']} already exists",
                )

        except subprocess.CalledProcessError:
            release_info["errors"].append("Git not available or tag creation failed")

        # Determine success
        if release_info["errors"]:
            release_info["status"] = (
                "partial_success" if release_info["files_updated"] else "failed"
            )
            success = False
        else:
            release_info["status"] = "success"
            success = True

        return success, release_info

    def create_release_artifacts(self, version: str, output_dir: Path) -> list[Path]:
        """
        Create all release artifacts for distribution

        Args:
            version: Release version
            output_dir: Directory for artifacts

        Returns:
            List of created artifact paths
        """
        artifacts = []
        output_dir.mkdir(parents=True, exist_ok=True)

        # Clean previous builds
        for old_file in output_dir.glob("*"):
            if old_file.is_file():
                old_file.unlink()

        # Build source distribution
        try:
            subprocess.run(
                [sys.executable, "-m", "build", "--sdist", "--outdir", str(output_dir)],
                check=True,
                capture_output=True,
            )

            # Find created sdist
            sdist_files = list(output_dir.glob("*.tar.gz"))
            artifacts.extend(sdist_files)

        except subprocess.CalledProcessError:
            # Fallback to setup.py sdist
            try:
                subprocess.run(
                    [
                        sys.executable,
                        "setup.py",
                        "sdist",
                        "--dist-dir",
                        str(output_dir),
                    ],
                    check=True,
                    capture_output=True,
                )
                sdist_files = list(output_dir.glob("*.tar.gz"))
                artifacts.extend(sdist_files)
            except subprocess.CalledProcessError:
                pass

        # Build wheel
        try:
            subprocess.run(
                [sys.executable, "-m", "build", "--wheel", "--outdir", str(output_dir)],
                check=True,
                capture_output=True,
            )

            # Find created wheels
            wheel_files = list(output_dir.glob("*.whl"))
            artifacts.extend(wheel_files)

        except subprocess.CalledProcessError:
            # Fallback to setup.py bdist_wheel
            try:
                subprocess.run(
                    [
                        sys.executable,
                        "setup.py",
                        "bdist_wheel",
                        "--dist-dir",
                        str(output_dir),
                    ],
                    check=True,
                    capture_output=True,
                )
                wheel_files = list(output_dir.glob("*.whl"))
                artifacts.extend(wheel_files)
            except subprocess.CalledProcessError:
                pass

        # Create checksums
        if artifacts:
            checksum_file = output_dir / f"treesitter-chunker-{version}.sha256"
            with checksum_file.Path("w").open("r") as f:
                for artifact in artifacts:
                    with artifact.Path("rb").open("r") as af:
                        sha256 = hashlib.sha256(af.read()).hexdigest()
                    f.write(f"{sha256}  {artifact.name}\n")
            artifacts.append(checksum_file)

        # Create release notes
        release_notes = output_dir / f"RELEASE_NOTES-{version}.md"
        release_notes.write_text(
            f"""# Release Notes for v{version}

## Installation

```bash
pip install treesitter-chunker=={version}
```

## Docker

```bash
docker pull treesitter-chunker:{version}
```

## Checksums

See `treesitter-chunker-{version}.sha256` for file checksums.
""",
        )
        artifacts.append(release_notes)

        return artifacts

    def _get_current_version(self) -> str | None:
        """Get the current version from project files"""
        # Try setup.py first
        setup_py = self.project_root / "setup.py"
        if setup_py.exists():
            content = setup_py.read_text()
            match = re.search(r'version\s*=\s*["\']([^"\']+)["\']', content)
            if match:
                return match.group(1)

        # Try pyproject.toml
        pyproject = self.project_root / "pyproject.toml"
        if pyproject.exists():
            content = pyproject.read_text()
            match = re.search(r'version\s*=\s*["\']([^"\']+)["\']', content)
            if match:
                return match.group(1)

        return None

    def _is_version_higher(self, new_version: str, current_version: str) -> bool:
        """Check if new version is higher than current"""

        def parse_version(v):
            # Simple version parsing - splits on dots and converts to integers
            parts = re.match(r"(\d+)\.(\d+)\.(\d+)", v)
            if parts:
                return tuple(int(p) for p in parts.groups())
            return (0, 0, 0)

        new_parts = parse_version(new_version)
        current_parts = parse_version(current_version)

        return new_parts > current_parts

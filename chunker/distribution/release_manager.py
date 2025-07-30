"""
Release Manager for version management and release automation

Handles version bumping, changelog updates, and release preparation
"""

import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any


class ReleaseManager:
    """Manages release process and versioning"""

    def __init__(self, project_root: Path | None = None):
        self.project_root = project_root or Path.cwd()
        self.version_files = [
            "pyproject.toml",
            "chunker/__init__.py",
            "setup.py",
        ]

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
        info = {
            "version": version,
            "updated_files": [],
            "git_tag": None,
            "errors": [],
        }

        # Validate version
        current_version = self._get_current_version()
        if not self._validate_version_bump(current_version, version):
            info["errors"].append(
                f"Invalid version bump: {current_version} -> {version}",
            )
            return False, info

        # Update version in all files
        for file_path in self.version_files:
            full_path = self.project_root / file_path
            if full_path.exists():
                if self._update_version_in_file(full_path, version):
                    info["updated_files"].append(str(file_path))
                else:
                    info["errors"].append(f"Failed to update version in {file_path}")

        # Update CHANGELOG.md
        changelog_path = self.project_root / "CHANGELOG.md"
        if self._update_changelog(changelog_path, version, changelog):
            info["updated_files"].append("CHANGELOG.md")
        else:
            info["errors"].append("Failed to update CHANGELOG.md")

        # Check if all tests pass
        if not self._run_tests():
            info["errors"].append("Tests failed. Fix issues before releasing.")
            return False, info

        # Create git tag
        tag_name = f"v{version}"
        if self._create_git_tag(tag_name, f"Release {version}\n\n{changelog}"):
            info["git_tag"] = tag_name
        else:
            info["errors"].append(f"Failed to create git tag: {tag_name}")

        success = len(info["errors"]) == 0
        return success, info

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

        # Build source distribution
        sdist_path = self._build_sdist(output_dir)
        if sdist_path:
            artifacts.append(sdist_path)

        # Build wheel
        wheel_path = self._build_wheel(output_dir)
        if wheel_path:
            artifacts.append(wheel_path)

        # Generate checksums
        checksum_path = self._generate_checksums(artifacts, output_dir)
        if checksum_path:
            artifacts.append(checksum_path)

        # Create release notes
        notes_path = output_dir / f"RELEASE_NOTES_{version}.md"
        if self._create_release_notes(version, notes_path):
            artifacts.append(notes_path)

        return artifacts

    def _get_current_version(self) -> str:
        """Get current version from pyproject.toml"""
        pyproject_path = self.project_root / "pyproject.toml"
        if pyproject_path.exists():
            with Path(pyproject_path).open("r") as f:
                content = f.read()
                match = re.search(r'version\s*=\s*["\']([^"\']+)["\']', content)
                if match:
                    return match.group(1)
        return "0.0.0"

    def _validate_version_bump(self, current: str, new: str) -> bool:
        """Validate that new version is higher than current"""

        def parse_version(v: str) -> tuple[int, ...]:
            return tuple(int(x) for x in v.split("."))

        try:
            return parse_version(new) > parse_version(current)
        except ValueError:
            return False

    def _update_version_in_file(self, file_path: Path, version: str) -> bool:
        """Update version string in a file_path"""
        try:
            with Path(file_path).open("r") as f:
                content = f.read()

            # Different patterns for different files
            if file_path.name == "pyproject.toml":
                content = re.sub(
                    r'version\s*=\s*["\'][^"\']+["\']',
                    f'version = "{version}"',
                    content,
                )
            elif file_path.name == "__init__.py":
                content = re.sub(
                    r'__version__\s*=\s*["\'][^"\']+["\']',
                    f'__version__ = "{version}"',
                    content,
                )
            elif file_path.name == "setup.py":
                content = re.sub(
                    r'version\s*=\s*["\'][^"\']+["\']',
                    f'version="{version}"',
                    content,
                )

            with Path(file_path).open("w") as f:
                f.write(content)
            return True
        except (OSError, FileNotFoundError, IndexError):
            return False

    def _update_changelog(self, changelog_path: Path, version: str, notes: str) -> bool:
        """Update CHANGELOG.md with new release notes"""
        try:
            # Read existing content
            if changelog_path.exists():
                with Path(changelog_path).open("r") as f:
                    existing_content = f.read()
            else:
                existing_content = "# Changelog\n\n"

            # Create new entry
            date_str = datetime.now().strftime("%Y-%m-%d")
            new_entry = f"\n## [{version}] - {date_str}\n\n{notes}\n"

            # Insert after header
            lines = existing_content.split("\n")
            insert_index = 2  # After "# Changelog" and empty line

            # Find the right place to insert
            for i, line in enumerate(lines):
                if line.startswith("## "):
                    insert_index = i
                    break

            lines.insert(insert_index, new_entry)

            # Write back
            with Path(changelog_path).open("w") as f:
                f.write("\n".join(lines))
            return True
        except (OSError, FileNotFoundError, IndexError):
            return False

    def _run_tests(self) -> bool:
        """Run test suite to ensure release quality"""
        try:
            result = subprocess.run(
                ["python", "-m", "pytest", "-xvs"],
                capture_output=True,
                cwd=self.project_root,
                check=False,
            )
            return result.returncode == 0
        except (OSError, IndexError, KeyError):
            return False

    def _create_git_tag(self, tag_name: str, message: str) -> bool:
        """Create annotated git tag"""
        try:
            # Check if tag already exists
            check_result = subprocess.run(
                ["git", "tag", "-l", tag_name],
                capture_output=True,
                text=True,
                cwd=self.project_root,
                check=False,
            )

            if check_result.stdout.strip():
                return False  # Tag already exists

            # Create annotated tag
            subprocess.run(
                ["git", "tag", "-a", tag_name, "-m", message],
                check=True,
                cwd=self.project_root,
            )
            return True
        except subprocess.CalledProcessError:
            return False

    def _build_sdist(self, output_dir: Path) -> Path | None:
        """Build source distribution"""
        try:
            subprocess.run(
                ["python", "-m", "build", "--sdist", "--outdir", str(output_dir)],
                check=True,
                cwd=self.project_root,
            )

            # Find the created file_path
            for file_path in output_dir.glob("*.tar.gz"):
                return file_path
        except (FileNotFoundError, IndexError, KeyError):
            pass
        return None

    def _build_wheel(self, output_dir: Path) -> Path | None:
        """Build wheel distribution"""
        try:
            subprocess.run(
                ["python", "-m", "build", "--wheel", "--outdir", str(output_dir)],
                check=True,
                cwd=self.project_root,
            )

            # Find the created file_path
            for file_path in output_dir.glob("*.whl"):
                return file_path
        except (FileNotFoundError, ImportError, IndexError):
            pass
        return None

    def _generate_checksums(self, files: list[Path], output_dir: Path) -> Path | None:
        """Generate SHA256 checksums for artifacts"""
        import hashlib

        checksum_path = output_dir / "checksums.txt"
        try:
            with Path(checksum_path).open("w") as f:
                for file_path in files:
                    if file_path.exists():
                        with Path(file_path).open("rb") as file_path:
                            sha256 = hashlib.sha256(file_path.read()).hexdigest()
                        f.write(f"{sha256}  {file_path.name}\n")
            return checksum_path
        except (FileNotFoundError, OSError):
            return None

    def _create_release_notes(self, version: str, output_path: Path) -> bool:
        """Create detailed release notes"""
        try:
            # Get changelog entry for this version
            changelog_path = self.project_root / "CHANGELOG.md"
            notes = ""

            if changelog_path.exists():
                with Path(changelog_path).open("r") as f:
                    content = f.read()

                # Extract section for this version
                version_pattern = f"## [{version}]"
                start_index = content.find(version_pattern)
                if start_index != -1:
                    end_index = content.find("\n## ", start_index + 1)
                    if end_index == -1:
                        end_index = len(content)
                    notes = content[start_index:end_index].strip()

            if not notes:
                notes = f"# Release {version}\n\nNo release notes available."

            with Path(output_path).open("w") as f:
                f.write(notes)
            return True
        except (OSError, FileNotFoundError, IndexError):
            return False

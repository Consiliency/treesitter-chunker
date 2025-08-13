"""
PyPI Publisher for package distribution

Handles uploading packages to PyPI and TestPyPI with validation
"""

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any


class PyPIPublisher:
    """Handles PyPI package publishing"""

    def __init__(self):
        # Avoid caching twine path; tests may monkeypatch shutil.which
        self.twine_cmd: str | None = None

    def publish(
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
        info = {
            "repository": repository,
            "dry_run": dry_run,
            "files": [],
            "validation": {},
            "upload_urls": [],
        }

        # Validate prerequisites
        validation_result = self._validate_prerequisites(package_dir, info)
        if not validation_result:
            return False, info

        dist_files = validation_result
        info["files"] = [str(f) for f in dist_files]

        # Check package validity
        if not self._check_package_validity(dist_files, info):
            return False, info

        # Handle dry run
        if dry_run:
            info["message"] = (
                "Dry run completed successfully. Package is ready for upload."
            )
            return True, info

        # Perform actual upload
        return self._perform_upload(dist_files, repository, info)

    def _validate_prerequisites(
        self,
        package_dir: Path,
        info: dict[str, Any],
    ) -> list[Path] | None:
        """Validate distribution files existence and twine availability."""
        # Determine twine availability (tests often monkeypatch this)
        self.twine_cmd = shutil.which("twine")

        # Check for distribution files first
        dist_files = list(package_dir.glob("*.whl")) + list(
            package_dir.glob("*.tar.gz"),
        )
        is_dry_run = bool(info.get("dry_run"))

        if is_dry_run:
            # In dry-run mode, prefer reporting missing artifacts first
            if not dist_files:
                info["error"] = "No distribution files found"
                return None
            if not self.twine_cmd:
                info["error"] = "twine not found. Install with: pip install twine"
                return None
            return dist_files
        # Non-dry-run: twine presence is required regardless of artifacts
        if not self.twine_cmd:
            info["error"] = "twine not found. Install with: pip install twine"
            return None
        if not dist_files:
            info["error"] = "No distribution files found"
            return None
        return dist_files

    def _check_package_validity(
        self,
        dist_files: list[Path],
        info: dict[str, Any],
    ) -> bool:
        """Check package validity using twine check."""
        try:
            check_result = subprocess.run(
                [self.twine_cmd or "twine", "check"] + [str(f) for f in dist_files],
                capture_output=True,
                text=True,
                check=True,
            )
            info["validation"]["check_output"] = check_result.stdout
            info["validation"]["passed"] = True
            return True
        except subprocess.CalledProcessError as e:
            info["validation"]["passed"] = False
            info["validation"]["error"] = e.stderr
            info["error"] = f"Package validation failed: {e.stderr}"
            return False

    def _perform_upload(
        self,
        dist_files: list[Path],
        repository: str,
        info: dict[str, Any],
    ) -> tuple[bool, dict[str, Any]]:
        """Perform the actual upload to PyPI."""
        # Get repository URL
        repo_urls = {
            "pypi": "https://upload.pypi.org/legacy/",
            "testpypi": "https://test.pypi.org/legacy/",
        }

        repo_url = repo_urls.get(repository)
        if not repo_url:
            info["error"] = f"Unknown repository: {repository}"
            return False, info

        # Check credentials
        ok = self._check_credentials(repository)
        if not ok:
            info["error"] = (
                f"No credentials found for {repository}. "
                "Set TWINE_USERNAME and TWINE_PASSWORD or use .pypirc"
            )
            return False, info

        # Upload
        try:
            self.twine_cmd = shutil.which("twine")
            if not self.twine_cmd:
                info["error"] = "twine not found. Install with: pip install twine"
                return False, info
            upload_cmd = [self.twine_cmd, "upload", "--repository-url", repo_url]
            upload_cmd.extend(str(f) for f in dist_files)
            upload_result = subprocess.run(
                upload_cmd,
                capture_output=True,
                text=True,
                check=True,
            )

            # Extract upload URLs
            for line in upload_result.stdout.splitlines():
                if "https://" in line and repository in line:
                    info["upload_urls"].append(line.strip())

            info["upload_output"] = upload_result.stdout
            info["success"] = True
            return True, info
        except subprocess.CalledProcessError as e:
            info["error"] = f"Upload failed: {e.stderr}"
            return False, info

    @classmethod
    def _check_credentials(cls, repository: str) -> bool:
        """Check if PyPI credentials are available"""
        if os.environ.get("TWINE_USERNAME") and os.environ.get(
            "TWINE_PASSWORD",
        ):
            return True
        pypirc_path = Path.home() / ".pypirc"
        if pypirc_path.exists():
            with Path(pypirc_path).open("r", encoding="utf-8") as f:
                content = f.read()
                if f"[{repository}]" in content:
                    return True
        return False

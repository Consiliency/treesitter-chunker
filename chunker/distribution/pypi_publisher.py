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
        self.twine_cmd = shutil.which("twine")

    def publish(self, package_dir: Path, repository: str = "pypi", dry_run:
        bool = False) -> tuple[bool, dict[str, Any]]:
        """
        Publish package to PyPI or TestPyPI

        Args:
            package_dir: Directory containing built distributions
            repository: Target repository (pypi or testpypi)
            dry_run: Perform validation without uploading

        Returns:
            Tuple of (success, upload_info)
        """
        info = {"repository": repository, "dry_run": dry_run, "files": [],
            "validation": {}, "upload_urls": []}
        if not self.twine_cmd:
            info["error"] = "twine not found. Install with: pip install twine"
            return False, info
        dist_files = list(package_dir.glob("*.whl")) + list(package_dir.
            glob("*.tar.gz"))
        if not dist_files:
            info["error"] = f"No distribution files found in {package_dir}"
            return False, info
        info["files"] = [str(f) for f in dist_files]
        try:
            check_result = subprocess.run([self.twine_cmd, "check"] + [str(
                f) for f in dist_files], capture_output=True, text=True,
                check=True)
            info["validation"]["check_output"] = check_result.stdout
            info["validation"]["passed"] = True
        except subprocess.CalledProcessError as e:
            info["validation"]["passed"] = False
            info["validation"]["error"] = e.stderr
            info["error"] = f"Package validation failed: {e.stderr}"
            return False, info
        if dry_run:
            info["message"
                ] = "Dry run completed successfully. Package is ready for upload."
            return True, info
        if repository == "pypi":
            repo_url = "https://upload.pypi.org/legacy/"
        elif repository == "testpypi":
            repo_url = "https://test.pypi.org/legacy/"
        else:
            info["error"] = f"Unknown repository: {repository}"
            return False, info
        if not self._check_credentials(repository):
            info["error"] = (
                f"No credentials found for {repository}. Set TWINE_USERNAME and TWINE_PASSWORD or use .pypirc"
                )
            return False, info
        try:
            upload_cmd = [self.twine_cmd, "upload", "--repository-url",
                repo_url]
            upload_cmd.extend(str(f) for f in dist_files)
            upload_result = subprocess.run(upload_cmd, capture_output=True,
                text=True, check=True)
            for line in upload_result.stdout.splitlines():
                if "https://" in line and repository in line:
                    info["upload_urls"].append(line.strip())
            info["upload_output"] = upload_result.stdout
            info["success"] = True
        except subprocess.CalledProcessError as e:
            info["error"] = f"Upload failed: {e.stderr}"
            return False, info
        return True, info

    @classmethod
    def _check_credentials(cls, repository: str) -> bool:
        """Check if PyPI credentials are available"""
        if os.environ.get("TWINE_USERNAME") and os.environ.get("TWINE_PASSWORD",
            ):
            return True
        pypirc_path = Path.home() / ".pypirc"
        if pypirc_path.exists():
            with Path(pypirc_path).open("r", encoding="utf-8") as f:
                content = f.read()
                if f"[{repository}]" in content:
                    return True
        return False

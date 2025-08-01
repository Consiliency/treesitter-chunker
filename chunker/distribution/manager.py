"""
Distribution Manager Implementation

Implements the DistributionContract for package distribution
"""
import hashlib
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from chunker.contracts.distribution_contract import DistributionContract


class DistributionImpl(DistributionContract):
    """Implementation of the distribution contract"""

    def __init__(self):
        """Initialize the distribution manager"""
        self.project_root = Path.cwd()

    @staticmethod
    def publish_to_pypi(package_dir: Path, repository: str = "pypi", dry_run:
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
        upload_info = {"repository": repository, "dry_run": dry_run,
            "uploaded": [], "errors": [], "status": "pending"}
        if not package_dir.exists():
            upload_info["errors"].append(
                f"Package directory not found: {package_dir}")
            upload_info["status"] = "failed"
            return False, upload_info
        dist_files = list(package_dir.glob("*.whl")) + list(package_dir.
            glob("*.tar.gz"))
        if not dist_files:
            upload_info["errors"].append("No distribution files found")
            upload_info["status"] = "failed"
            return False, upload_info
        try:
            subprocess.run(["twine", "--version"], capture_output=True,
                check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            upload_info["errors"].append(
                "twine not found - install with: pip install twine")
            upload_info["status"] = "failed"
            return False, upload_info
        try:
            result = subprocess.run(["twine", "check"] + [str(f) for f in
                dist_files], capture_output=True, text=True, check=True)
            upload_info["check_output"] = result.stdout
        except subprocess.CalledProcessError as e:
            upload_info["errors"].append(
                f"Package validation failed: {e.stderr}")
            upload_info["status"] = "failed"
            return False, upload_info
        for dist_file in dist_files:
            with dist_file.open("rb", "r") as f:
                file_hash = hashlib.sha256(f.read()).hexdigest()
            file_info = {"filename": dist_file.name, "size": dist_file.stat
                ().st_size, "sha256": file_hash}
            if dry_run:
                file_info["status"] = "would_upload"
            else:
                repo_url = (
                    f"https://{'test.' if repository == 'testpypi' else ''}pypi.org/legacy/"
                    )
                cmd = ["twine", "upload", "--repository-url", repo_url, str
                    (dist_file)]
                try:
                    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                    file_info["status"] = "uploaded"
                    file_info["url"] = (
                        f"https://{'test.' if repository == 'testpypi' else ''}pypi.org/project/treesitter-chunker/"
                        )
                except subprocess.CalledProcessError as e:
                    file_info["status"] = "failed"
                    file_info["error"] = e.stderr
                    upload_info["errors"].append(
                        f"Failed to upload {dist_file.name}: {e.stderr}")
            upload_info["uploaded"].append(file_info)
        if dry_run:
            upload_info["status"] = "dry_run_success"
            success = True
        else:
            failed_uploads = [f for f in upload_info["uploaded"] if f.get(
                "status") == "failed"]
            if failed_uploads:
                upload_info["status"] = "partial_failure"
                success = False
            else:
                upload_info["status"] = "success"
                success = True
        return success, upload_info

    def build_docker_image(self, tag: str, platforms: (list[str] | None) = None,
        ) -> tuple[bool, str]:
        """
        Build Docker image for distribution

        Args:
            tag: Docker image tag
            platforms: List of platforms (linux/amd64, linux/arm64)

        Returns:
            Tuple of (success, image_id)
        """
        if platforms is None:
            platforms = ["linux/amd64"]
        try:
            subprocess.run(["docker", "--version"], capture_output=True,
                check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False, "docker-not-available"
        dockerfile = self.project_root / "Dockerfile"
        if not dockerfile.exists():
            dockerfile_content = """FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \\
    build-essential \\
    git \\
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY . /app/

# Install the package
RUN pip install --no-cache-dir -e .

# Install grammars
RUN python scripts/fetch_grammars.py && python scripts/build_lib.py

ENTRYPOINT ["treesitter-chunker"]
"""
            dockerfile.write_text(dockerfile_content)
        cmd = ["docker", "build", "-t", tag]
        if len(platforms) > 1:
            platform_str = ",".join(platforms)
            cmd.extend(["--platform", platform_str])
        cmd.append(str(self.project_root))
        try:
            subprocess.run(cmd, capture_output=True, text=True, check=True)
            inspect_result = subprocess.run(["docker", "images", "-q", tag],
                capture_output=True, text=True, check=True)
            image_id = inspect_result.stdout.strip()
            return True, image_id
        except subprocess.CalledProcessError:
            return False, "build-failed"

    @staticmethod
    def create_homebrew_formula(version: str, output_path: Path) -> tuple[
        bool, Path]:
        """
        Generate Homebrew formula for macOS distribution

        Args:
            version: Package version
            output_path: Path for formula file

        Returns:
            Tuple of (success, formula_path)
        """
        output_path.mkdir(parents=True, exist_ok=True)
        sha256 = "placeholder_sha256_hash"
        formula_content = f"""class TreesitterChunker < Formula
  include Language::Python::Virtualenv

  desc "Semantic code chunker using Tree-sitter for intelligent code analysis"
  homepage "https://github.com/Consiliency/treesitter-chunker"
  url "https://files.pythonhosted.org/packages/source/t/treesitter-chunker/treesitter-chunker-{version}.tar.gz"
  sha256 "{sha256}"
  license "MIT"
  head "https://github.com/Consiliency/treesitter-chunker.git", branch: "main"

  depends_on "python@3.11"
  depends_on "tree-sitter"

  resource "tree-sitter" do
    url "https://files.pythonhosted.org/packages/source/t/tree-sitter/tree_sitter-0.20.4.tar.gz"
    sha256 "6adb123e2f3e56399bbf2359924633c882cc40ee8344885200bca0922f713be5"
  end

  def install
    virtualenv_install_with_resources

    # Build grammars after installation
    system libexec/"bin/python", libexec/"bin/treesitter-chunker", "--help"
  end

  test do
    system bin/"treesitter-chunker", "--version"

    # Test basic functionality
    (testpath/"test.py").write <<~EOS
      def hello():
          print("Hello, world!")
    EOS

    output = shell_output("#{{bin}}/treesitter-chunker chunk #{{testpath}}/test.py -l python")
    assert_match "hello", output
  end
end
"""
        formula_path = output_path / "treesitter-chunker.rb"
        formula_path.write_text(formula_content)
        return True, formula_path

    @classmethod
    def verify_installation(cls, method: str, platform: str) -> tuple[bool,
        dict[str, Any]]:
        """
        Verify package installs correctly via specified method

        Args:
            method: Installation method (pip, conda, docker, homebrew)
            platform: Target platform

        Returns:
            Tuple of (success, verification_details)
        """
        verification_details = {"method": method, "platform": platform,
            "installed": False, "functional": False, "version": None,
            "errors": []}
        if method == "pip":
            with tempfile.TemporaryDirectory() as tmpdir:
                venv_path = Path(tmpdir) / "venv"
                try:
                    subprocess.run([sys.executable, "-m", "venv", str(
                        venv_path)], check=True, capture_output=True)
                    pip_cmd = str(venv_path / "bin" / "pip",
                        ) if platform != "windows" else str(venv_path /
                        "Scripts" / "pip")
                    subprocess.run([pip_cmd, "install",
                        "treesitter-chunker"], check=True, capture_output=True)
                    verification_details["installed"] = True
                    tsc_cmd = str(venv_path / "bin" / "treesitter-chunker",
                        ) if platform != "windows" else str(venv_path /
                        "Scripts" / "treesitter-chunker")
                    result = subprocess.run([tsc_cmd, "--version"],
                        capture_output=True, text=True, check=True)
                    verification_details["functional"] = True
                    verification_details["version"] = result.stdout.strip()
                except subprocess.CalledProcessError as e:
                    verification_details["errors"].append(
                        f"Installation failed: {e!s}")
        elif method == "docker":
            try:
                subprocess.run(["docker", "run", "--rm",
                    "treesitter-chunker:latest", "--version"], check=True,
                    capture_output=True, text=True)
                verification_details["installed"] = True
                verification_details["functional"] = True
            except subprocess.CalledProcessError:
                verification_details["errors"].append(
                    "Docker image not functional")
        elif method == "homebrew":
            if platform != "darwin":
                verification_details["errors"].append(
                    "Homebrew only available on macOS")
                return False, verification_details
            try:
                result = subprocess.run(["brew", "list",
                    "treesitter-chunker"], capture_output=True, check=False)
                if result.returncode == 0:
                    verification_details["installed"] = True
                    result = subprocess.run(["treesitter-chunker",
                        "--version"], capture_output=True, text=True, check=True)
                    verification_details["functional"] = True
                    verification_details["version"] = result.stdout.strip()
            except subprocess.CalledProcessError:
                verification_details["errors"].append(
                    "Homebrew verification failed")
        elif method == "conda":
            verification_details["errors"].append(
                "Conda distribution not yet implemented")
        success = verification_details["installed"] and verification_details[
            "functional"]
        return success, verification_details

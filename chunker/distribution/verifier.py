"""
Installation Verifier

Verifies package installations across different platforms and methods
"""
import shutil
import subprocess
import tempfile
import venv
from pathlib import Path
from typing import Any


class InstallationVerifier:
    """Verifies installations work correctly across platforms"""

    def verify_installation(self, method: str, platform: str) -> tuple[bool,
        dict[str, Any]]:
        """
        Verify package installs correctly via specified method

        Args:
            method: Installation method (pip, conda, docker, homebrew)
            platform: Target platform

        Returns:
            Tuple of (success, verification_details)
        """
        details = {"method": method, "platform": platform, "tests_passed":
            [], "tests_failed": [], "installation_output": "", "errors": []}
        if method == "pip":
            return self._verify_pip_installation(platform, details)
        if method == "conda":
            return self._verify_conda_installation(platform, details)
        if method == "docker":
            return self._verify_docker_installation(platform, details)
        if method == "homebrew":
            return self._verify_homebrew_installation(platform, details)
        details["errors"].append(f"Unknown installation method: {method}")
        return False, details

    @classmethod
    def _verify_pip_installation(cls, platform: str, details: dict) -> tuple[
        bool, dict]:
        """Verify pip installation"""
        with tempfile.TemporaryDirectory() as tmpdir:
            venv_path = Path(tmpdir) / "test_venv"
            try:
                venv.create(venv_path, with_pip=True)
                if platform.startswith("win"):
                    pip_exe = venv_path / "Scripts" / "pip.exe"
                    python_exe = venv_path / "Scripts" / "python.exe"
                else:
                    pip_exe = venv_path / "bin" / "pip"
                    python_exe = venv_path / "bin" / "python"
                install_result = subprocess.run([str(pip_exe), "install",
                    "treesitter-chunker"], capture_output=True, text=True,
                    check=False)
                details["installation_output"] = install_result.stdout
                if install_result.returncode != 0:
                    details["errors"].append(
                        f"Installation failed: {install_result.stderr}")
                    return False, details
                test_import = subprocess.run([str(python_exe), "-c",
                    "import chunker; print(chunker.__version__)"],
                    capture_output=True, text=True, check=False)
                if test_import.returncode == 0:
                    details["tests_passed"].append("import_test")
                else:
                    details["tests_failed"].append("import_test")
                    details["errors"].append(
                        f"Import failed: {test_import.stderr}")
                chunker_cmd = venv_path / ("Scripts" if platform.startswith
                    ("win") else "bin") / "chunker"
                test_cli = subprocess.run([str(chunker_cmd), "--version"],
                    capture_output=True, text=True, check=False)
                if test_cli.returncode == 0:
                    details["tests_passed"].append("cli_test")
                else:
                    details["tests_failed"].append("cli_test")
                test_code = """
import tempfile
from pathlib import Path
from chunker import Chunker

with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
    f.write("def test():\\n    pass")
    f.flush()

    chunker = Chunker("python")
    chunks = chunker.chunk(Path(f.name))
    assert len(chunks) > 0
    print("Functionality test passed")
"""
                test_func = subprocess.run([str(python_exe), "-c",
                    test_code], capture_output=True, text=True, check=False)
                if test_func.returncode == 0:
                    details["tests_passed"].append("functionality_test")
                else:
                    details["tests_failed"].append("functionality_test")
                    details["errors"].append(
                        f"Functionality test failed: {test_func.stderr}")
            except (IndexError, KeyError) as e:
                details["errors"].append(f"Setup failed: {e!s}")
                return False, details
        success = len(details["tests_failed"]) == 0 and len(details["errors"],
            ) == 0
        return success, details

    @staticmethod
    def _verify_conda_installation(_platform: str, details: dict) -> tuple[
        bool, dict]:
        """Verify conda installation"""
        conda_cmd = shutil.which("conda")
        if not conda_cmd:
            details["errors"].append(
                "Conda not found. Please install Anaconda or Miniconda.")
            return False, details
        with tempfile.TemporaryDirectory() as tmpdir:
            env_name = f"test_chunker_{tmpdir.split('/')[-1]}"
            try:
                create_result = subprocess.run([conda_cmd, "create", "-n",
                    env_name, "python=3.9", "-y"], capture_output=True,
                    text=True, check=False)
                if create_result.returncode != 0:
                    details["errors"].append(
                        f"Failed to create conda env: {create_result.stderr}")
                    return False, details
                install_result = subprocess.run([conda_cmd, "install", "-n",
                    env_name, "-c", "conda-forge", "treesitter-chunker",
                    "-y"], capture_output=True, text=True, check=False)
                details["installation_output"] = install_result.stdout
                test_cmd = (
                    f"conda run -n {env_name} python -c 'import chunker; print(chunker.__version__)'"
                    )
                test_result = subprocess.run(test_cmd, shell=True,
                    capture_output=True, text=True, check=False)
                if test_result.returncode == 0:
                    details["tests_passed"].append("conda_import_test")
                else:
                    details["tests_failed"].append("conda_import_test")
                subprocess.run([conda_cmd, "env", "remove", "-n", env_name,
                    "-y"], capture_output=True, check=False)
            except (ImportError, IndexError, KeyError) as e:
                details["errors"].append(f"Conda test failed: {e!s}")
                subprocess.run([conda_cmd, "env", "remove", "-n", env_name,
                    "-y"], capture_output=True, check=False)
                return False, details
        success = len(details["tests_failed"]) == 0
        return success, details

    @staticmethod
    def _verify_docker_installation(_platform: str, details: dict) -> tuple[
        bool, dict]:
        """Verify Docker installation"""
        docker_cmd = shutil.which("docker")
        if not docker_cmd:
            details["errors"].append("Docker not found. Please install Docker.",
                )
            return False, details
        try:
            image_name = "treesitter-chunker:latest"
            test_result = subprocess.run([docker_cmd, "run", "--rm",
                image_name, "chunker", "--version"], capture_output=True,
                text=True, check=False)
            if test_result.returncode == 0:
                details["tests_passed"].append("docker_cli_test")
                details["installation_output"] = test_result.stdout
            else:
                details["tests_failed"].append("docker_cli_test")
                details["errors"].append(
                    f"Docker run failed: {test_result.stderr}")
            test_code = """
import tempfile
from pathlib import Path
from chunker import Chunker

chunker = Chunker("python")
print("Docker functionality test passed")
"""
            func_result = subprocess.run([docker_cmd, "run", "--rm",
                image_name, "python", "-c", test_code], capture_output=True,
                text=True, check=False)
            if func_result.returncode == 0:
                details["tests_passed"].append("docker_functionality_test")
            else:
                details["tests_failed"].append("docker_functionality_test")
        except (IndexError, KeyError) as e:
            details["errors"].append(f"Docker test failed: {e!s}")
            return False, details
        success = len(details["tests_failed"]) == 0
        return success, details

    @classmethod
    def _verify_homebrew_installation(cls, platform: str, details: dict,
        ) -> tuple[bool, dict]:
        """Verify Homebrew installation"""
        if not platform.startswith(("darwin", "macos")):
            details["errors"].append("Homebrew is only supported on macOS")
            return False, details
        brew_cmd = shutil.which("brew")
        if not brew_cmd:
            details["errors"].append(
                "Homebrew not found. Please install Homebrew.")
            return False, details
        try:
            install_result = subprocess.run([brew_cmd, "install",
                "treesitter-chunker"], capture_output=True, text=True,
                check=False)
            details["installation_output"] = install_result.stdout
            if install_result.returncode != 0:
                formula_path = Path("homebrew/treesitter-chunker.rb")
                if formula_path.exists():
                    install_result = subprocess.run([brew_cmd, "install",
                        str(formula_path)], capture_output=True, text=True,
                        check=False)
            test_result = subprocess.run(["chunker", "--version"],
                capture_output=True, text=True, check=False)
            if test_result.returncode == 0:
                details["tests_passed"].append("homebrew_cli_test")
            else:
                details["tests_failed"].append("homebrew_cli_test")
            test_import = subprocess.run(["python3", "-c",
                "import chunker; print('Homebrew test passed')"],
                capture_output=True, text=True, check=False)
            if test_import.returncode == 0:
                details["tests_passed"].append("homebrew_import_test")
            else:
                details["tests_failed"].append("homebrew_import_test")
        except (ImportError, IndexError, KeyError) as e:
            details["errors"].append(f"Homebrew test failed: {e!s}")
            return False, details
        success = len(details["tests_failed"]) == 0
        return success, details

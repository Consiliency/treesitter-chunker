"""Unit tests for installation verifier"""

from unittest.mock import Mock, patch

from chunker.distribution.verifier import InstallationVerifier


class TestInstallationVerifier:
    """Test installation verification functionality"""

    @classmethod
    def test_verify_unknown_method(cls):
        """Test handling of unknown installation method"""
        verifier = InstallationVerifier()
        success, details = verifier.verify_installation("unknown", "linux")
        assert not success
        assert "Unknown installation method" in details["errors"][0]

    @classmethod
    @patch("venv.create")
    @patch("subprocess.run")
    def test_verify_pip_installation_success(cls, mock_run, mock_venv):
        """Test successful pip installation verification"""
        verifier = InstallationVerifier()
        mock_run.side_effect = [
            Mock(returncode=0, stdout="Successfully installed", stderr=""),
            Mock(returncode=0, stdout="1.0.0", stderr=""),
            Mock(returncode=0, stdout="chunker version 1.0.0", stderr=""),
            Mock(returncode=0, stdout="Functionality test passed", stderr=""),
        ]
        success, details = verifier.verify_installation("pip", "linux")
        assert success
        assert "import_test" in details["tests_passed"]
        assert "cli_test" in details["tests_passed"]
        assert "functionality_test" in details["tests_passed"]
        assert len(details["tests_failed"]) == 0

    @classmethod
    @patch("venv.create")
    @patch("subprocess.run")
    def test_verify_pip_installation_failure(cls, mock_run, mock_venv):
        """Test failed pip installation verification"""
        verifier = InstallationVerifier()
        mock_run.return_value = Mock(
            returncode=1,
            stdout="",
            stderr="ERROR: Package not found",
        )
        success, details = verifier.verify_installation("pip", "linux")
        assert not success
        assert "Installation failed" in details["errors"][0]

    @classmethod
    @patch("venv.create")
    @patch("subprocess.run")
    def test_verify_pip_windows_paths(cls, mock_run, mock_venv):
        """Test pip verification uses correct paths on Windows"""
        verifier = InstallationVerifier()
        called_executables = []

        def track_calls(*args, **kwargs):
            called_executables.append(args[0][0])
            return Mock(returncode=0, stdout="", stderr="")

        mock_run.side_effect = track_calls
        _success, _details = verifier.verify_installation("pip", "windows")
        assert any("Scripts" in exe for exe in called_executables)

    @classmethod
    @patch("shutil.which")
    def test_verify_conda_not_found(cls, mock_which):
        """Test conda verification when conda is not installed"""
        mock_which.return_value = None
        verifier = InstallationVerifier()
        success, details = verifier.verify_installation("conda", "linux")
        assert not success
        assert "Conda not found" in details["errors"][0]

    @classmethod
    @patch("shutil.which")
    @patch("subprocess.run")
    def test_verify_conda_installation(cls, mock_run, mock_which):
        """Test conda installation verification"""
        mock_which.return_value = "/usr/bin/conda"
        verifier = InstallationVerifier()
        mock_run.side_effect = [
            Mock(returncode=0, stdout="Environment created", stderr=""),
            Mock(returncode=0, stdout="Package installed", stderr=""),
            Mock(returncode=0, stdout="1.0.0", stderr=""),
            Mock(returncode=0),
        ]
        success, details = verifier.verify_installation("conda", "linux")
        assert success
        assert "conda_import_test" in details["tests_passed"]

    @classmethod
    @patch("shutil.which")
    def test_verify_docker_not_found(cls, mock_which):
        """Test Docker verification when Docker is not installed"""
        mock_which.return_value = None
        verifier = InstallationVerifier()
        success, details = verifier.verify_installation("docker", "linux")
        assert not success
        assert "Docker not found" in details["errors"][0]

    @classmethod
    @patch("shutil.which")
    @patch("subprocess.run")
    def test_verify_docker_installation(cls, mock_which, mock_run):
        """Test Docker installation verification"""
        mock_which.return_value = "/usr/bin/docker"
        verifier = InstallationVerifier()
        mock_run.side_effect = [
            Mock(returncode=1, stdout="", stderr="Unable to find image"),
        ]
        success, details = verifier.verify_installation("docker", "linux")
        assert isinstance(success, bool)
        assert isinstance(details, dict)
        assert "tests_passed" in details
        assert "tests_failed" in details
        assert "errors" in details

    @classmethod
    def test_verify_homebrew_wrong_platform(cls):
        """Test Homebrew verification on non-macOS platform"""
        verifier = InstallationVerifier()
        success, details = verifier.verify_installation("homebrew", "linux")
        assert not success
        assert "only supported on macOS" in details["errors"][0]

    @classmethod
    @patch("shutil.which")
    def test_verify_homebrew_not_found(cls, mock_which):
        """Test Homebrew verification when brew is not installed"""
        mock_which.return_value = None
        verifier = InstallationVerifier()
        success, details = verifier.verify_installation("homebrew", "darwin")
        assert not success
        assert "Homebrew not found" in details["errors"][0]

    @classmethod
    @patch("shutil.which")
    @patch("subprocess.run")
    def test_verify_homebrew_installation(cls, mock_which, mock_run):
        """Test Homebrew installation verification"""
        mock_which.return_value = "/usr/local/bin/brew"
        verifier = InstallationVerifier()
        mock_run.side_effect = [
            Mock(returncode=1, stdout="", stderr="Formula not found"),
        ]
        success, details = verifier.verify_installation("homebrew", "darwin")
        assert isinstance(success, bool)
        assert isinstance(details, dict)
        assert "tests_passed" in details
        assert "tests_failed" in details
        if not success:
            assert "errors" in details or len(details["tests_failed"]) > 0

    @classmethod
    @patch("shutil.which")
    @patch("subprocess.run")
    @patch("pathlib.Path.exists")
    def test_verify_homebrew_local_formula(cls, mock_exists, mock_run, mock_which):
        """Test Homebrew verification with local formula fallback"""
        mock_which.return_value = "/usr/local/bin/brew"
        mock_exists.return_value = True
        verifier = InstallationVerifier()
        mock_run.side_effect = [
            Mock(returncode=1, stdout="", stderr="Formula not found"),
            Mock(returncode=0, stdout="Formula installed", stderr=""),
            Mock(returncode=0, stdout="1.0.0", stderr=""),
            Mock(returncode=0, stdout="Test passed", stderr=""),
        ]
        success, details = verifier.verify_installation("homebrew", "darwin")
        assert success
        assert "homebrew_cli_test" in details["tests_passed"]

"""Unit tests for PyPI publisher"""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from chunker.distribution.pypi_publisher import PyPIPublisher


class TestPyPIPublisher:
    """Test PyPI publishing functionality"""

    def test_publish_validates_packages(self):
        """Test that packages are validated before upload"""
        publisher = PyPIPublisher()

        with tempfile.TemporaryDirectory() as tmpdir:
            package_dir = Path(tmpdir)

            # No packages case
            success, info = publisher.publish(package_dir, dry_run=True)
            assert not success
            assert "No distribution files found" in info["error"]

    @patch("shutil.which")
    def test_publish_requires_twine(self, mock_which):
        """Test that twine is required for publishing"""
        mock_which.return_value = None
        publisher = PyPIPublisher()

        with tempfile.TemporaryDirectory() as tmpdir:
            success, info = publisher.publish(Path(tmpdir))
            assert not success
            assert "twine not found" in info["error"]

    @patch("subprocess.run")
    @patch("shutil.which")
    def test_dry_run_validates_only(self, mock_which, mock_run):
        """Test dry run only validates without uploading"""
        mock_which.return_value = "/usr/bin/twine"
        mock_run.return_value = Mock(
            returncode=0,
            stdout="Checking dist/package.whl: PASSED",
            stderr="",
        )

        publisher = PyPIPublisher()

        with tempfile.TemporaryDirectory() as tmpdir:
            package_dir = Path(tmpdir)
            # Create dummy wheel
            wheel_path = package_dir / "test-1.0.0-py3-none-any.whl"
            wheel_path.touch()

            success, info = publisher.publish(package_dir, dry_run=True)

            assert success
            assert info["dry_run"]
            assert "Dry run completed successfully" in info["message"]

            # Verify only check was called, not upload
            calls = [call.args[0] for call in mock_run.call_args_list]
            assert any("check" in call for call in calls)
            assert not any("upload" in call for call in calls)

    @patch("subprocess.run")
    @patch("shutil.which")
    @patch.dict(
        "os.environ",
        {"TWINE_USERNAME": "__token__", "TWINE_PASSWORD": "pypi-token"},
    )
    def test_publish_to_pypi(self, mock_which, mock_run):
        """Test publishing to PyPI"""
        mock_which.return_value = "/usr/bin/twine"
        mock_run.side_effect = [
            # twine check
            Mock(returncode=0, stdout="Checking: PASSED", stderr=""),
            # twine upload
            Mock(
                returncode=0,
                stdout="Uploading distributions to https://upload.pypi.org/legacy/\n"
                "Uploading test-1.0.0.whl\n"
                "View at: https://pypi.org/project/test/1.0.0/",
                stderr="",
            ),
        ]

        publisher = PyPIPublisher()

        with tempfile.TemporaryDirectory() as tmpdir:
            package_dir = Path(tmpdir)
            wheel_path = package_dir / "test-1.0.0-py3-none-any.whl"
            wheel_path.touch()

            success, info = publisher.publish(package_dir, repository="pypi")

            assert success
            assert info["repository"] == "pypi"
            assert len(info["upload_urls"]) > 0

    def test_credentials_check(self):
        """Test credential checking logic"""
        publisher = PyPIPublisher()

        # Test with environment variables
        with patch.dict(
            "os.environ",
            {"TWINE_USERNAME": "user", "TWINE_PASSWORD": "pass"},
        ):
            assert publisher._check_credentials("pypi")

        # Test without credentials
        with patch.dict("os.environ", {}, clear=True):
            with patch("pathlib.Path.exists", return_value=False):
                assert not publisher._check_credentials("pypi")

    @patch("subprocess.run")
    @patch("shutil.which")
    def test_repository_url_mapping(self, mock_which, mock_run):
        """Test repository URL mapping"""
        # Mock twine availability
        mock_which.return_value = "/usr/bin/twine"
        # Mock successful twine check
        mock_run.return_value = Mock(returncode=0, stdout="Check passed", stderr="")

        publisher = PyPIPublisher()

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a dummy package so we get past the file check
            package_dir = Path(tmpdir)
            wheel_file = package_dir / "test-1.0.0-py3-none-any.whl"
            wheel_file.touch()

            # Test unknown repository
            success, info = publisher.publish(package_dir, repository="unknown")
            assert not success
            # Should get unknown repository error
            assert "Unknown repository" in info["error"]

"""
Unit tests for distribution implementation
"""
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from chunker.distribution.manager import DistributionImpl
from chunker.distribution.release import ReleaseManagementImpl


class TestDistributionImpl:
    """Test the distribution implementation"""

    @classmethod
    def test_publish_to_pypi_missing_directory(cls):
        """Test publish fails with missing directory"""
        dist = DistributionImpl()
        success, info = dist.publish_to_pypi(Path("/nonexistent"))
        assert success is False
        assert "Package directory not found" in info["errors"][0]
        assert info["status"] == "failed"

    @classmethod
    def test_publish_to_pypi_no_files(cls):
        """Test publish fails with no distribution files"""
        dist = DistributionImpl()
        with tempfile.TemporaryDirectory() as tmpdir:
            success, info = dist.publish_to_pypi(Path(tmpdir))
            assert success is False
            assert "No distribution files found" in info["errors"][0]
            assert info["status"] == "failed"

    @classmethod
    @patch("subprocess.run")
    def test_publish_to_pypi_dry_run(cls, mock_run):
        """Test dry run publish"""
        dist = DistributionImpl()
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            wheel = tmppath / "test-1.0.0-py3-none-any.whl"
            wheel.write_text("dummy wheel")
            success, info = dist.publish_to_pypi(tmppath, dry_run=True)
            assert success is True
            assert info["status"] == "dry_run_success"
            assert len(info["uploaded"]) == 1
            assert info["uploaded"][0]["status"] == "would_upload"

    @classmethod
    @patch("subprocess.run")
    def test_build_docker_image_success(cls, mock_run):
        """Test successful Docker image build"""
        dist = DistributionImpl()
        mock_run.side_effect = [MagicMock(returncode=0), MagicMock(
            returncode=0), MagicMock(returncode=0, stdout="abc123\n")]
        success, image_id = dist.build_docker_image("test:latest")
        assert success is True
        assert image_id == "abc123"

    @classmethod
    @patch("subprocess.run")
    def test_build_docker_image_no_docker(cls, mock_run):
        """Test Docker build when Docker is not available"""
        dist = DistributionImpl()
        mock_run.side_effect = FileNotFoundError()
        success, image_id = dist.build_docker_image("test:latest")
        assert success is False
        assert image_id == "docker-not-available"

    @classmethod
    def test_create_homebrew_formula(cls):
        """Test Homebrew formula generation"""
        dist = DistributionImpl()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir)
            success, formula_path = dist.create_homebrew_formula("1.0.0",
                output_path)
            assert success is True
            assert formula_path.exists()
            assert formula_path.name == "treesitter-chunker.rb"
            content = formula_path.read_text()
            assert "class TreesitterChunker < Formula" in content
            assert 'version "1.0.0"' in content or "treesitter-chunker-1.0.0.tar.gz" in content

    @classmethod
    @patch("subprocess.run")
    def test_verify_installation_pip(cls, mock_run):
        """Test pip installation verification"""
        dist = DistributionImpl()
        mock_run.side_effect = [MagicMock(returncode=0), MagicMock(
            returncode=0), MagicMock(returncode=0, stdout="1.0.0")]
        success, details = dist.verify_installation("pip", "linux")
        assert success is True
        assert details["installed"] is True
        assert details["functional"] is True
        assert details["version"] == "1.0.0"

    @classmethod
    @patch("subprocess.run")
    def test_verify_installation_docker(cls, mock_run):
        """Test Docker installation verification"""
        dist = DistributionImpl()
        mock_run.return_value = MagicMock(returncode=0)
        success, details = dist.verify_installation("docker", "linux")
        assert success is True
        assert details["installed"] is True
        assert details["functional"] is True


class TestReleaseManagementImpl:
    """Test the release management implementation"""

    @classmethod
    def test_prepare_release_invalid_version(cls):
        """Test prepare release with invalid version format"""
        release = ReleaseManagementImpl()
        success, info = release.prepare_release("invalid", "changelog")
        assert success is False
        assert "Invalid version format" in info["errors"][0]
        assert info["status"] == "failed"

    @classmethod
    @patch("subprocess.run")
    def test_prepare_release_success(cls, mock_run):
        """Test successful release preparation"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            release = ReleaseManagementImpl(tmppath)
            setup_py = tmppath / "setup.py"
            setup_py.write_text('version="0.1.0"')
            changelog = tmppath / "CHANGELOG.md"
            changelog.write_text("# Changelog\n\n")
            mock_run.side_effect = [MagicMock(returncode=0), MagicMock(
                returncode=0, stdout=""), MagicMock(returncode=0)]
            success, info = release.prepare_release("1.0.0", "New features")
            assert success is True
            assert info["status"] == "success"
            assert str(setup_py) in info["files_updated"]
            assert str(changelog) in info["files_updated"]
            assert 'version="1.0.0"' in setup_py.read_text()
            assert "[1.0.0]" in changelog.read_text()
            assert "New features" in changelog.read_text()

    @classmethod
    @patch("subprocess.run")
    def test_create_release_artifacts(cls, mock_run):
        """Test release artifact creation"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            release = ReleaseManagementImpl(tmppath)
            output_dir = tmppath / "dist"
            output_dir.mkdir()
            sdist = output_dir / "treesitter-chunker-1.0.0.tar.gz"
            wheel = output_dir / "treesitter_chunker-1.0.0-py3-none-any.whl"

            def create_artifacts(*args, **kwargs):
                if "--sdist" in args[0]:
                    sdist.write_text("sdist content")
                elif "--wheel" in args[0]:
                    wheel.write_text("wheel content")
                return MagicMock(returncode=0, stdout="", stderr="")
            mock_run.side_effect = create_artifacts
            artifacts = release.create_release_artifacts("1.0.0", output_dir)
            assert len(artifacts) >= 2
            checksum_files = [a for a in artifacts if a.name.endswith(
                ".sha256")]
            assert len(checksum_files) == 1
            notes_files = [a for a in artifacts if a.name.startswith(
                "RELEASE_NOTES")]
            assert len(notes_files) == 1

    @classmethod
    def test_version_comparison(cls):
        """Test version comparison logic"""
        release = ReleaseManagementImpl()
        assert release._is_version_higher("1.0.0", "0.9.0") is True
        assert release._is_version_higher("1.0.1", "1.0.0") is True
        assert release._is_version_higher("2.0.0", "1.9.9") is True
        assert release._is_version_higher("1.0.0", "1.0.0") is False
        assert release._is_version_higher("0.9.0", "1.0.0") is False
        assert release._is_version_higher("1.0.0", "1.0.1") is False

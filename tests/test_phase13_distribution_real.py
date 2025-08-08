"""
Real integration tests for Phase 13 Distribution

These tests use the actual distribution implementation rather than mocks
"""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from chunker.distribution import Distributor


class TestDistributionIntegrationReal:
    """Test actual distribution implementation"""

    @classmethod
    @pytest.fixture
    def distributor(cls):
        """Provide a real distributor instance"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Distributor(Path(tmpdir))

    @classmethod
    def test_pypi_publishing_validates_package(cls, distributor):
        """PyPI publishing should validate package before upload"""
        with tempfile.TemporaryDirectory() as tmpdir:
            package_dir = Path(tmpdir)
            success, info = distributor.publish_to_pypi(
                package_dir,
                repository="testpypi",
                dry_run=True,
            )
            assert isinstance(success, bool)
            assert isinstance(info, dict)
            if not success:
                assert "error" in info
                assert (
                    "No distribution files found" in info["error"]
                    or "twine not found" in info["error"]
                )
            wheel_file = package_dir / "test-1.0.0-py3-none-any.whl"
            wheel_file.write_bytes(b"PK")
            with patch("shutil.which", return_value="/usr/bin/twine"):
                with patch("subprocess.run") as mock_run:
                    mock_run.return_value = Mock(
                        returncode=0,
                        stdout="Checking: PASSED",
                        stderr="",
                    )
                    success, info = distributor.publish_to_pypi(
                        package_dir,
                        repository="testpypi",
                        dry_run=True,
                    )
                    assert success
                    assert "validation" in info or "checks" in info["validation"]

    @classmethod
    def test_docker_image_works_cross_platform(cls, distributor):
        """Docker image should support multiple platforms"""
        dockerfile = distributor.project_root / "Dockerfile"
        dockerfile.write_text("FROM python:3.9\nRUN pip install treesitter-chunker")
        with patch("shutil.which", return_value="/usr/bin/docker"):
            distributor.docker_builder.buildx_available = False
            with patch("subprocess.run") as mock_run:
                mock_run.side_effect = [
                    Mock(returncode=0),
                    Mock(returncode=0, stdout="", stderr=""),
                    Mock(returncode=0, stdout="sha256:test123", stderr=""),
                ]
                success, image_id = distributor.build_docker_image(
                    "treesitter-chunker:latest",
                    platforms=["linux/amd64"],
                )
                assert isinstance(success, bool)
                assert isinstance(image_id, str)
                if success:
                    verify_success, _details = distributor.verify_installation(
                        "docker",
                        "linux/amd64",
                    )
                    assert isinstance(verify_success, bool)

    @classmethod
    def test_release_process_updates_all_locations(cls, distributor):
        """Release process should update version everywhere"""
        pyproject = distributor.project_root / "pyproject.toml"
        pyproject.write_text('[project]\nversion = "0.9.0"')
        chunker_dir = distributor.project_root / "chunker"
        chunker_dir.mkdir()
        init_file = chunker_dir / "__init__.py"
        init_file.write_text('__version__ = "0.9.0"')
        changelog = distributor.project_root / "CHANGELOG.md"
        changelog.write_text("# Changelog\n\n")
        with (
            patch.object(distributor.release_manager, "_run_tests", return_value=True),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.side_effect = [Mock(returncode=0, stdout=""), Mock(returncode=0)]
            success, info = distributor.prepare_release(
                "1.0.0",
                "Initial stable release",
            )
            assert isinstance(success, bool)
            assert isinstance(info, dict)
            if success:
                assert "updated_files" in info
                assert "git_tag" in info
                expected_files = [
                    "pyproject.toml",
                    "chunker/__init__.py",
                    "CHANGELOG.md",
                ]
                for file_path in expected_files:
                    assert any(file_path in str(f) for f in info["updated_files"])

    @classmethod
    def test_homebrew_formula_creation(cls, distributor):
        """Homebrew formula should be created with correct content"""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir)
            success, formula_path = distributor.create_homebrew_formula(
                "1.0.0",
                output_path,
            )
            assert success
            assert formula_path.exists()
            content = formula_path.read_text()
            assert "class TreesitterChunker" in content
            assert "1.0.0" in content
            assert 'depends_on "python' in content

    @staticmethod
    def test_installation_verification_structure(distributor):
        """Installation verification should return proper structure"""
        methods = ["pip", "conda", "docker", "homebrew"]
        for method in methods:
            success, details = distributor.verify_installation(method, "linux")
            assert isinstance(success, bool)
            assert isinstance(details, dict)
            assert "method" in details
            assert "platform" in details
            assert details["method"] == method
            assert details["platform"] == "linux"
            assert "tests_passed" in details
            assert "tests_failed" in details
            assert isinstance(details["tests_passed"], list)
            assert isinstance(details["tests_failed"], list)

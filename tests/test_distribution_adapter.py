"""
Test adapter for distribution integration tests

This adapter allows the integration tests to use our actual implementation
"""
import tempfile
from pathlib import Path

import pytest

from chunker.distribution import Distributor


class TestDistributionAdapter:
    """Adapter to make integration tests work with our implementation"""

    @classmethod
    @pytest.fixture
    def distributor(cls):
        """Provide a real distributor instance"""
        return Distributor()

    @classmethod
    def test_pypi_publishing_validates_package(cls, distributor):
        """PyPI publishing should validate package before upload"""
        with tempfile.TemporaryDirectory() as tmpdir:
            package_dir = Path(tmpdir)
            wheel_file = package_dir / "test-1.0.0-py3-none-any.whl"
            wheel_file.touch()
            distributor.pypi_publisher.twine_cmd = None
            success, info = distributor.publish_to_pypi(package_dir,
                repository="testpypi", dry_run=True)
            assert not success
            assert "twine not found" in info.get("error", "")

    @staticmethod
    def test_docker_image_validation(distributor):
        """Docker image building should validate requirements"""
        distributor.docker_builder.docker_cmd = None
        success, message = distributor.build_docker_image(
            "treesitter-chunker:latest", platforms=["linux/amd64",
            "linux/arm64"])
        assert not success
        assert "Docker not found" in message

    @classmethod
    def test_homebrew_formula_generation(cls, distributor):
        """Homebrew formula should be generated correctly"""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir)
            success, formula_path = distributor.create_homebrew_formula("1.0.0"
                , output_path)
            assert success
            assert formula_path.exists()
            assert formula_path.suffix == ".rb"
            content = formula_path.read_text()
            assert "class TreesitterChunker" in content
            assert "1.0.0" in content

    @classmethod
    def test_release_preparation(cls, distributor):
        """Release preparation should update all necessary files"""
        with tempfile.TemporaryDirectory() as tmpdir:
            distributor.release_manager.project_root = Path(tmpdir)
            pyproject = Path(tmpdir) / "pyproject.toml"
            pyproject.write_text('version = "0.9.0"')
            distributor.release_manager._run_tests = lambda: True
            distributor.release_manager._create_git_tag = lambda tag, msg: True
            success, info = distributor.prepare_release("1.0.0",
                "Initial stable release")
            assert success
            assert info["version"] == "1.0.0"
            assert "pyproject.toml" in info["updated_files"]

    @staticmethod
    def test_verification_routing(distributor):
        """Installation verification should route to correct method"""
        success, details = distributor.verify_installation("unknown", "linux")
        assert not success
        assert "Unknown installation method" in details["errors"][0]
        for method in ["pip", "conda", "docker", "homebrew"]:
            success, details = distributor.verify_installation(method, "linux")
            assert isinstance(success, bool)
            assert isinstance(details, dict)
            assert "method" in details
            assert "platform" in details

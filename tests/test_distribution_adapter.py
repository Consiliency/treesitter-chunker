"""
Test adapter for distribution integration tests

This adapter allows the integration tests to use our actual implementation
"""

from pathlib import Path

import pytest

from chunker.distribution import Distributor


class TestDistributionAdapter:
    """Adapter to make integration tests work with our implementation"""

    @pytest.fixture
    def distributor(self):
        """Provide a real distributor instance"""
        return Distributor()

    def test_pypi_publishing_validates_package(self, distributor):
        """PyPI publishing should validate package before upload"""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            package_dir = Path(tmpdir)

            # Create dummy package files
            wheel_file = package_dir / "test-1.0.0-py3-none-any.whl"
            wheel_file.touch()

            # Mock twine command availability
            distributor.pypi_publisher.twine_cmd = None

            # Dry run should validate without uploading
            success, info = distributor.publish_to_pypi(
                package_dir,
                repository="testpypi",
                dry_run=True,
            )

            # Without twine, it should fail
            assert not success
            assert "twine not found" in info.get("error", "")

    def test_docker_image_validation(self, distributor):
        """Docker image building should validate requirements"""
        # Mock docker availability
        distributor.docker_builder.docker_cmd = None

        success, message = distributor.build_docker_image(
            "treesitter-chunker:latest",
            platforms=["linux/amd64", "linux/arm64"],
        )

        assert not success
        assert "Docker not found" in message

    def test_homebrew_formula_generation(self, distributor):
        """Homebrew formula should be generated correctly"""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir)

            success, formula_path = distributor.create_homebrew_formula(
                "1.0.0",
                output_path,
            )

            assert success
            assert formula_path.exists()
            assert formula_path.suffix == ".rb"

            # Check formula content
            content = formula_path.read_text()
            assert "class TreesitterChunker" in content
            assert "1.0.0" in content

    def test_release_preparation(self, distributor):
        """Release preparation should update all necessary files"""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            # Set project root
            distributor.release_manager.project_root = Path(tmpdir)

            # Create minimal project structure
            pyproject = Path(tmpdir) / "pyproject.toml"
            pyproject.write_text('version = "0.9.0"')

            # Mock test runner to avoid running actual tests
            distributor.release_manager._run_tests = lambda: True

            # Mock git tag creation to avoid git repository requirement
            distributor.release_manager._create_git_tag = lambda tag, msg: True

            success, info = distributor.prepare_release(
                "1.0.0",
                "Initial stable release",
            )

            # Should succeed
            assert success
            assert info["version"] == "1.0.0"
            assert "pyproject.toml" in info["updated_files"]

    def test_verification_routing(self, distributor):
        """Installation verification should route to correct method"""
        # Test unknown method
        success, details = distributor.verify_installation("unknown", "linux")
        assert not success
        assert "Unknown installation method" in details["errors"][0]

        # Test known methods return proper structure
        for method in ["pip", "conda", "docker", "homebrew"]:
            success, details = distributor.verify_installation(method, "linux")
            assert isinstance(success, bool)
            assert isinstance(details, dict)
            assert "method" in details
            assert "platform" in details

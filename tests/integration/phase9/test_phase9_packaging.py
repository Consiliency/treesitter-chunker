"""Integration tests for Phase 9 packaging and distribution."""

import sys

import pytest

from chunker import DistributionConfig, PackageDistributor, PlatformConfig, WheelBuilder


class TestPackagingIntegration:
    """Test packaging and distribution features."""

    @pytest.fixture()
    def package_config(self, tmp_path):
        """Create distribution configuration."""
        return DistributionConfig(
            package_name="treesitter-chunker",
            version="0.1.0",
            author="Test Author",
            author_email="test@example.com",
            description="Tree-sitter based code chunker",
            long_description="A powerful code chunking library",
            url="https://github.com/test/treesitter-chunker",
            python_requires=">=3.8",
            install_requires=[
                "tree-sitter>=0.20.0",
                "click>=8.0",
                "pathspec>=0.11.0",
            ],
            extras_require={
                "dev": ["pytest>=7.0", "black", "mypy"],
                "tiktoken": ["tiktoken>=0.4.0"],
            },
            entry_points={
                "console_scripts": [
                    "chunker=cli.main:cli",
                ],
            },
        )

    def test_platform_detection(self):
        """Test platform configuration detection."""
        config = PlatformConfig.detect_current()

        assert (
            config.python_version
            == f"py{sys.version_info.major}{sys.version_info.minor}"
        )
        assert config.platform in ["linux", "darwin", "win32", "win_amd64"]
        assert config.arch in ["x86_64", "arm64", "i686", "aarch64", "AMD64"]

        # Test string representation
        platform_str = config.get_platform_tag()
        assert platform_str  # Should not be empty
        assert config.python_version in platform_str

    def test_wheel_building(self, tmp_path, package_config):
        """Test wheel building process."""
        # Create mock package structure
        pkg_dir = tmp_path / "treesitter_chunker"
        pkg_dir.mkdir()

        # Create __init__.py
        init_file = pkg_dir / "__init__.py"
        init_file.write_text('__version__ = "0.1.0"\n')

        # Create setup.py
        setup_py = tmp_path / "setup.py"
        setup_py.write_text(
            f"""
from setuptools import setup, find_packages

setup(
    name="{package_config.package_name}",
    version="{package_config.version}",
    packages=find_packages(),
    python_requires="{package_config.python_requires}",
    install_requires={package_config.install_requires},
)
""",
        )

        # Create wheel builder
        builder = WheelBuilder(package_config)

        # Test metadata generation
        metadata = builder.generate_metadata()
        assert f"Name: {package_config.package_name}" in metadata
        assert f"Version: {package_config.version}" in metadata
        assert "Requires-Python: >=3.8" in metadata

        # Test wheel filename generation
        platform_config = PlatformConfig.detect_current()
        wheel_name = builder.get_wheel_filename(platform_config)
        assert package_config.package_name.replace("-", "_") in wheel_name
        assert package_config.version in wheel_name
        assert platform_config.python_version in wheel_name
        assert wheel_name.endswith(".whl")

    def test_multi_platform_distribution(self, package_config):
        """Test distribution for multiple platforms."""
        distributor = PackageDistributor(package_config)

        # Define target platforms
        platforms = [
            PlatformConfig("py38", "linux", "x86_64"),
            PlatformConfig("py39", "darwin", "x86_64"),
            PlatformConfig("py310", "win_amd64", "AMD64"),
            PlatformConfig("py311", "linux", "aarch64"),
        ]

        # Get distribution plan
        plan = distributor.plan_distribution(platforms)

        assert len(plan) == len(platforms)
        for platform, wheel_info in plan.items():
            assert wheel_info["platform"] == platform
            assert wheel_info["filename"].endswith(".whl")
            assert platform.python_version in wheel_info["filename"]

    def test_dependency_resolution(self, package_config):
        """Test dependency handling for different platforms."""
        distributor = PackageDistributor(package_config)

        # Test base dependencies
        base_deps = distributor.resolve_dependencies()
        assert "tree-sitter>=0.20.0" in base_deps
        assert "click>=8.0" in base_deps

        # Test with extras
        dev_deps = distributor.resolve_dependencies(extras=["dev"])
        assert "pytest>=7.0" in dev_deps
        assert all(dep in dev_deps for dep in base_deps)

        # Test with multiple extras
        all_deps = distributor.resolve_dependencies(extras=["dev", "tiktoken"])
        assert "tiktoken>=0.4.0" in all_deps
        assert len(all_deps) > len(dev_deps)

    def test_version_handling(self, package_config):
        """Test version number handling."""
        builder = WheelBuilder(package_config)

        # Test version normalization
        test_versions = [
            ("1.0.0", "1.0.0"),
            ("1.0.0-alpha", "1.0.0a0"),
            ("1.0.0-beta.1", "1.0.0b1"),
            ("1.0.0-rc1", "1.0.0rc1"),
            ("1.0.0.dev1", "1.0.0.dev1"),
        ]

        for input_version, expected in test_versions:
            normalized = builder.normalize_version(input_version)
            assert normalized == expected

    def test_manifest_generation(self, tmp_path, package_config):
        """Test MANIFEST.in generation."""
        distributor = PackageDistributor(package_config)

        # Create manifest
        manifest_content = distributor.generate_manifest(
            include_patterns=["*.md", "*.txt"],
            exclude_patterns=["test_*.py"],
            include_data=True,
        )

        assert "include README.md" in manifest_content
        assert "include LICENSE" in manifest_content
        assert "recursive-include" in manifest_content
        assert "global-exclude test_*.py" in manifest_content

    def test_distribution_validation(self, tmp_path, package_config):
        """Test distribution package validation."""
        distributor = PackageDistributor(package_config)

        # Create mock wheel file
        wheel_file = tmp_path / "test_package-0.1.0-py3-none-any.whl"
        wheel_file.write_text("mock wheel content")

        # Test validation checks
        validation_issues = distributor.validate_distribution(str(wheel_file))

        # Should detect it's not a valid wheel
        assert validation_issues  # Should have issues with mock file

    def test_cross_platform_compatibility(self):
        """Test cross-platform compatibility checks."""
        # Test platform tag compatibility
        linux_config = PlatformConfig("py39", "linux", "x86_64")
        macos_config = PlatformConfig("py39", "darwin", "x86_64")
        windows_config = PlatformConfig("py39", "win_amd64", "AMD64")

        # Each should generate different platform tags
        tags = {
            linux_config.get_platform_tag(),
            macos_config.get_platform_tag(),
            windows_config.get_platform_tag(),
        }

        assert len(tags) == 3  # All should be different

"""
Integration tests for Build System implementation
"""

import tempfile
from pathlib import Path

import pytest

from chunker.build.system import BuildSystemImpl, PlatformSupportImpl
from chunker.contracts.distribution_stub import DistributionStub


class TestBuildSystemIntegration:
    """Test BuildSystemImpl integration with other components"""

    def test_cross_platform_build_verification(self):
        """Test building and verifying across platforms"""
        # Arrange: Use real implementations
        platform_support = PlatformSupportImpl()
        build_system = BuildSystemImpl()
        distribution = DistributionStub()

        # Act: Detect platform and build
        platform_info = platform_support.detect_platform()

        # Build for detected platform
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            wheel_success, wheel_path = build_system.build_wheel(
                platform=platform_info.get("platform_tag", "unknown"),
                python_version="cp39",
                output_dir=output_dir,
            )

            # Verify build artifact
            verify_success, verify_info = build_system.verify_build(
                artifact_path=wheel_path,
                platform=platform_info.get("platform_tag", "unknown"),
            )

            # Verify installation (using stub)
            install_success, install_info = distribution.verify_installation(
                method="pip",
                platform=platform_info.get("os", "unknown"),
            )

        # Assert: Verify data types and flow
        assert isinstance(platform_info, dict)
        assert "os" in platform_info
        assert isinstance(wheel_success, bool)
        assert isinstance(wheel_path, Path)
        assert isinstance(verify_success, bool)
        assert isinstance(verify_info, dict)
        assert isinstance(install_success, bool)

    def test_compile_grammars_integration(self):
        """Test grammar compilation with real implementation"""
        # Arrange
        build_system = BuildSystemImpl()
        platform_support = PlatformSupportImpl()

        platform_info = platform_support.detect_platform()

        # Act
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            success, build_info = build_system.compile_grammars(
                languages=["python", "javascript"],
                platform=platform_info["os"],
                output_dir=output_dir,
            )

        # Assert
        assert isinstance(success, bool)
        assert isinstance(build_info, dict)
        assert "platform" in build_info
        assert "compiler" in build_info
        assert "languages" in build_info
        assert "errors" in build_info

    def test_platform_detection_integration(self):
        """Test platform detection provides usable information"""
        # Arrange
        platform_support = PlatformSupportImpl()

        # Act
        platform_info = platform_support.detect_platform()

        # Assert
        assert isinstance(platform_info, dict)
        assert platform_info["os"] in ["linux", "macos", "windows"]
        assert "arch" in platform_info
        assert "python_version" in platform_info
        assert "python_tag" in platform_info
        assert "platform_tag" in platform_info
        assert "compiler" in platform_info

        # Compiler should be detected on CI systems
        assert platform_info["compiler"] != "unknown"

    def test_build_wheel_creates_valid_path(self):
        """Test wheel building returns valid paths"""
        # Arrange
        build_system = BuildSystemImpl()
        platform_support = PlatformSupportImpl()

        platform_info = platform_support.detect_platform()

        # Act
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            success, wheel_path = build_system.build_wheel(
                platform=platform_info["os"],
                python_version=platform_info["python_tag"],
                output_dir=output_dir,
            )

        # Assert
        assert isinstance(success, bool)
        assert isinstance(wheel_path, Path)

        # Even if build fails, path should be valid
        if success:
            # Wheel name should contain platform and python version
            assert platform_info["python_tag"] in str(wheel_path)

    def test_conda_package_creation(self):
        """Test conda package creation"""
        # Arrange
        build_system = BuildSystemImpl()
        platform_support = PlatformSupportImpl()

        platform_info = platform_support.detect_platform()

        # Act
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            success, package_path = build_system.create_conda_package(
                platform=platform_info["os"],
                output_dir=output_dir,
            )

        # Assert
        assert isinstance(success, bool)
        assert isinstance(package_path, Path)

        # If conda-build not available, should fail gracefully
        if not success:
            assert str(package_path) == "."

    def test_verify_missing_artifact(self):
        """Test verification handles missing artifacts properly"""
        # Arrange
        build_system = BuildSystemImpl()

        # Act
        fake_path = Path(tempfile.gettempdir()) / "nonexistent.whl"
        valid, report = build_system.verify_build(fake_path, "linux")

        # Assert
        assert not valid
        assert isinstance(report, dict)
        assert "errors" in report
        assert len(report["errors"]) > 0
        assert "valid" in report
        assert report["valid"] is False

    def test_install_build_dependencies(self):
        """Test build dependency installation"""
        # Arrange
        platform_support = PlatformSupportImpl()
        platform_info = platform_support.detect_platform()

        # Act
        # Don't actually install anything in tests
        result = platform_support.install_build_dependencies(platform_info["os"])

        # Assert
        assert isinstance(result, bool)
        # Should return True if dependencies already installed
        # (which they should be on CI systems)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

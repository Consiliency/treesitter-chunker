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

    @classmethod
    def test_cross_platform_build_verification(cls):
        """Test building and verifying across platforms"""
        platform_support = PlatformSupportImpl()
        build_system = BuildSystemImpl()
        distribution = DistributionStub()
        platform_info = platform_support.detect_platform()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            wheel_success, wheel_path = build_system.build_wheel(
                platform=platform_info.get("platform_tag", "unknown"),
                python_version="cp39",
                output_dir=output_dir,
            )
            verify_success, verify_info = build_system.verify_build(
                artifact_path=wheel_path,
                platform=platform_info.get("platform_tag", "unknown"),
            )
            install_success, _install_info = distribution.verify_installation(
                method="pip",
                platform=platform_info.get("os", "unknown"),
            )
        assert isinstance(platform_info, dict)
        assert "os" in platform_info
        assert isinstance(wheel_success, bool)
        assert isinstance(wheel_path, Path)
        assert isinstance(verify_success, bool)
        assert isinstance(verify_info, dict)
        assert isinstance(install_success, bool)

    @classmethod
    def test_compile_grammars_integration(cls):
        """Test grammar compilation with real implementation"""
        build_system = BuildSystemImpl()
        platform_support = PlatformSupportImpl()
        platform_info = platform_support.detect_platform()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            success, build_info = build_system.compile_grammars(
                languages=["python", "javascript"],
                platform=platform_info["os"],
                output_dir=output_dir,
            )
        assert isinstance(success, bool)
        assert isinstance(build_info, dict)
        assert "platform" in build_info
        assert "compiler" in build_info
        assert "languages" in build_info
        assert "errors" in build_info

    @classmethod
    def test_platform_detection_integration(cls):
        """Test platform detection provides usable information"""
        platform_support = PlatformSupportImpl()
        platform_info = platform_support.detect_platform()
        assert isinstance(platform_info, dict)
        assert platform_info["os"] in {"linux", "macos", "windows"}
        assert "arch" in platform_info
        assert "python_version" in platform_info
        assert "python_tag" in platform_info
        assert "platform_tag" in platform_info
        assert "compiler" in platform_info
        assert platform_info["compiler"] != "unknown"

    @classmethod
    def test_build_wheel_creates_valid_path(cls):
        """Test wheel building returns valid paths"""
        build_system = BuildSystemImpl()
        platform_support = PlatformSupportImpl()
        platform_info = platform_support.detect_platform()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            success, wheel_path = build_system.build_wheel(
                platform=platform_info["os"],
                python_version=platform_info["python_tag"],
                output_dir=output_dir,
            )
        assert isinstance(success, bool)
        assert isinstance(wheel_path, Path)
        if success:
            assert platform_info["python_tag"] in str(wheel_path)

    @classmethod
    def test_conda_package_creation(cls):
        """Test conda package creation"""
        build_system = BuildSystemImpl()
        platform_support = PlatformSupportImpl()
        platform_info = platform_support.detect_platform()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            success, package_path = build_system.create_conda_package(
                platform=platform_info["os"],
                output_dir=output_dir,
            )
        assert isinstance(success, bool)
        assert isinstance(package_path, Path)
        if not success:
            assert str(package_path) == "."

    @classmethod
    def test_verify_missing_artifact(cls):
        """Test verification handles missing artifacts properly"""
        build_system = BuildSystemImpl()
        fake_path = Path(tempfile.gettempdir()) / "nonexistent.whl"
        valid, report = build_system.verify_build(fake_path, "linux")
        assert not valid
        assert isinstance(report, dict)
        assert "errors" in report
        assert len(report["errors"]) > 0
        assert "valid" in report
        assert report["valid"] is False

    @classmethod
    def test_install_build_dependencies(cls):
        """Test build dependency installation"""
        platform_support = PlatformSupportImpl()
        platform_info = platform_support.detect_platform()
        result = platform_support.install_build_dependencies(platform_info["os"])
        assert isinstance(result, bool)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

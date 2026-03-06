"""
Integration tests for actual Build System implementation
"""

import tempfile
from pathlib import Path

import pytest

from chunker.build import BuildSystem, PlatformSupport


class TestBuildSystemImplementation:
    """Test the actual build system implementation"""

    @classmethod
    def test_platform_detection_works(cls):
        """Platform detection should work on current system"""
        platform = PlatformSupport()
        build_sys = BuildSystem()
        info = platform.detect_platform()
        assert info["os"] in {"linux", "macos", "windows"}
        assert info["compiler"] != "unknown"
        info2 = build_sys.platform_support.detect_platform()
        assert info2["os"] == info["os"]

    @classmethod
    def test_grammar_compilation_handles_missing_grammars(cls):
        """Should handle gracefully when grammars aren't fetched"""
        build_sys = BuildSystem()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            platform_info = build_sys.platform_support.detect_platform()
            current_platform = platform_info["os"]
            success, build_info = build_sys.compile_grammars(
                ["python"],
                current_platform,
                output_dir,
            )
            assert isinstance(success, bool)
            assert isinstance(build_info, dict)
            assert "platform" in build_info
            assert "compiler" in build_info
            assert "errors" in build_info
            if not success:
                assert len(build_info["errors"]) > 0

    @classmethod
    def test_wheel_build_returns_proper_types(cls):
        """Wheel build should return expected types even on failure"""
        build_sys = BuildSystem()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            platform_info = build_sys.platform_support.detect_platform()
            success, wheel_path = build_sys.build_wheel(
                platform_info["os"],
                platform_info["python_tag"],
                output_dir,
            )
            assert isinstance(success, bool)
            assert isinstance(wheel_path, Path)

    @classmethod
    def test_verify_build_with_missing_file(cls):
        """Verify should handle missing files properly"""
        build_sys = BuildSystem()
        fake_path = (
            Path(
                tempfile.gettempdir(),
            )
            / "nonexistent_test_artifact.whl"
        )
        valid, report = build_sys.verify_build(fake_path, "linux")
        assert not valid
        assert isinstance(report, dict)
        assert "errors" in report
        assert len(report["errors"]) > 0
        assert "artifact" in report
        assert "platform" in report
        assert report["valid"] is False

    @classmethod
    def test_conda_package_handles_missing_tools(cls):
        """Conda package creation should handle missing conda-build"""
        build_sys = BuildSystem()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            success, package_path = build_sys.create_conda_package("linux", output_dir)
            assert isinstance(success, bool)
            assert isinstance(package_path, Path)
            if not success:
                assert str(package_path) == "."


def test_integration_with_mocked_build_system():
    """Test that mocked version matches our interface"""
    from unittest.mock import Mock

    from chunker.contracts.build_contract import (
        BuildSystemContract,
        PlatformSupportContract,
    )

    mock_build = Mock(spec=BuildSystemContract)
    mock_platform = Mock(spec=PlatformSupportContract)
    mock_platform.detect_platform()
    mock_platform.install_build_dependencies("linux")
    mock_build.compile_grammars(["python"], "linux", Path())
    mock_build.build_wheel("linux", "cp39", Path())
    mock_build.create_conda_package("linux", Path())
    mock_build.verify_build(Path(), "linux")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

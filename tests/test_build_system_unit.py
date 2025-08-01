"""
Unit tests for Build System implementation
"""
import tempfile
from pathlib import Path

import pytest

from chunker.build import BuildSystem, PlatformSupport


class TestPlatformSupport:
    """Test platform detection and support"""

    @classmethod
    def test_detect_platform_returns_required_fields(cls):
        """Platform detection should return all required fields"""
        platform = PlatformSupport()
        info = platform.detect_platform()
        assert "os" in info
        assert "arch" in info
        assert "python_version" in info
        assert "python_impl" in info
        assert "python_tag" in info
        assert "platform_tag" in info
        assert "compiler" in info
        assert info["os"] in {"linux", "macos", "windows"}
        assert info["arch"] in {"x86_64", "arm64", "i386", "aarch64"}
        assert info["python_impl"] in {"cpython", "pypy"}

    @classmethod
    def test_platform_tag_generation(cls):
        """Platform tags should follow PEP standards"""
        platform = PlatformSupport()
        info = platform.detect_platform()
        platform_tag = info["platform_tag"]
        if info["os"] == "windows":
            assert platform_tag.startswith("win")
        elif info["os"] == "macos":
            assert platform_tag.startswith("macosx")
        else:
            assert platform_tag.startswith("linux")


class TestBuildSystem:
    """Test build system functionality"""

    @classmethod
    def test_compile_grammars_basic(cls):
        """Basic grammar compilation should work"""
        builder = BuildSystem()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            _success, build_info = builder.compile_grammars(["python"],
                "linux", output_dir)
            assert isinstance(build_info, dict)
            assert "platform" in build_info
            assert "compiler" in build_info
            assert "languages" in build_info
            assert build_info["languages"] == ["python"]

    @classmethod
    def test_verify_build_nonexistent_file(cls):
        """Verify should handle non-existent files gracefully"""
        builder = BuildSystem()
        fake_path = Path(tempfile.gettempdir()) / "nonexistent.whl"
        valid, report = builder.verify_build(fake_path, "linux")
        assert not valid
        assert "errors" in report
        assert len(report["errors"]) > 0
        assert "Artifact does not exist" in report["errors"][0]

    @classmethod
    def test_build_wheel_structure(cls):
        """Wheel building should create proper structure"""
        builder = BuildSystem()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            success, wheel_path = builder.build_wheel("linux", "cp39",
                output_dir)
            assert isinstance(success, bool)
            assert isinstance(wheel_path, Path)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

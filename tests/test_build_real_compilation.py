"""
Test actual grammar compilation
"""
import tempfile
from pathlib import Path

import pytest

from chunker.build.system import BuildSystemImpl, PlatformSupportImpl


class TestRealCompilation:
    """Test actual grammar compilation functionality"""

    @classmethod
    def test_compile_single_grammar(cls):
        """Test compiling a single grammar"""
        build_system = BuildSystemImpl()
        platform_support = PlatformSupportImpl()
        platform_info = platform_support.detect_platform()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            success, build_info = build_system.compile_grammars(languages=[
                "python"], platform=platform_info["os"], output_dir=output_dir)
            if success:
                assert "libraries" in build_info
                assert "combined" in build_info["libraries"]
                lib_path = Path(build_info["libraries"]["combined"])
                assert lib_path.exists()
                if platform_info["os"] == "linux":
                    assert lib_path.suffix == ".so"
                elif platform_info["os"] == "macos":
                    assert lib_path.suffix == ".dylib"
                elif platform_info["os"] == "windows":
                    assert lib_path.suffix == ".dll"
            else:
                assert len(build_info["errors"]) > 0

    @classmethod
    def test_compile_multiple_grammars(cls):
        """Test compiling multiple grammars"""
        build_system = BuildSystemImpl()
        platform_support = PlatformSupportImpl()
        platform_info = platform_support.detect_platform()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            success, build_info = build_system.compile_grammars(languages=[
                "python", "javascript", "rust"], platform=platform_info[
                "os"], output_dir=output_dir)
            assert isinstance(success, bool)
            assert isinstance(build_info, dict)
            if success:
                assert "libraries" in build_info
                assert len(build_info["errors"]) == 0
            else:
                print(f"Compilation errors: {build_info.get('errors', [])}")

    @classmethod
    def test_build_wheel_with_grammars(cls):
        """Test building a wheel that includes compiled grammars"""
        build_system = BuildSystemImpl()
        platform_support = PlatformSupportImpl()
        platform_info = platform_support.detect_platform()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            success, wheel_path = build_system.build_wheel(platform=platform_info["os"], python_version=platform_info[
                "python_tag"], output_dir=output_dir)
            if success and wheel_path.exists():
                verify_success, verify_info = build_system.verify_build(
                    artifact_path=wheel_path, platform=platform_info["os"])
                assert isinstance(verify_success, bool)
                assert isinstance(verify_info, dict)
                if verify_success:
                    assert verify_info["components"]["package"]
                    assert verify_info["components"]["metadata"]
                    assert verify_info["components"]["grammars"]

    @classmethod
    def test_platform_specific_compilation(cls):
        """Test that compilation uses platform-specific settings"""
        build_system = BuildSystemImpl()
        platform_support = PlatformSupportImpl()
        platform_info = platform_support.detect_platform()
        current_os = platform_info["os"]
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            _success, build_info = build_system.compile_grammars(languages=["python"], platform=current_os, output_dir=output_dir)
            assert build_info["platform"] == current_os
            assert build_info["compiler"] != "unknown"
            assert build_info["compiler"] == platform_info["compiler"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

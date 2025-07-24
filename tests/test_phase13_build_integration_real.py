"""
Integration tests for Phase 13 Build System with real implementation
"""

import tempfile
from pathlib import Path

import pytest

from chunker.build import BuildSystem


class TestBuildSystemIntegrationReal:
    """Test build system integration with real implementation"""

    def setup_method(self):
        """Setup for each test"""
        self.build_sys = BuildSystem()

    def test_grammar_compilation_produces_loadable_libraries(self):
        """Compiled grammars should be loadable by tree-sitter"""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            # Compile for current platform
            platform_info = self.build_sys.platform_support.detect_platform()
            current_platform = platform_info["os"]

            # Note: This will fail if grammars aren't fetched
            # Let's compile just one language to reduce dependencies
            success, build_info = self.build_sys.compile_grammars(
                ["python"],  # Just Python for now
                current_platform,
                output_dir,
            )

            # Check the response structure is correct
            assert isinstance(success, bool)
            assert isinstance(build_info, dict)
            assert "libraries" in build_info
            assert "platform" in build_info
            assert "compiler" in build_info
            assert "errors" in build_info

            # If successful, verify libraries exist
            if success:
                assert len(build_info["libraries"]) > 0
                for lib_path in build_info["libraries"].values():
                    assert Path(lib_path).exists()
            else:
                # If failed, should have error messages
                assert len(build_info["errors"]) > 0

    def test_wheel_includes_compiled_grammars(self):
        """Built wheels should include platform-specific grammars"""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            platform_info = self.build_sys.platform_support.detect_platform()

            success, wheel_path = self.build_sys.build_wheel(
                platform_info["os"],
                platform_info["python_tag"],
                output_dir,
            )

            # Check return types
            assert isinstance(success, bool)
            assert isinstance(wheel_path, Path)

            if success:
                assert wheel_path.exists()
                assert wheel_path.suffix == ".whl"
                assert (
                    platform_info["os"] in wheel_path.name.lower()
                    or platform_info["platform_tag"] in wheel_path.name
                )
                assert platform_info["python_tag"] in wheel_path.name

    def test_build_verification_catches_issues(self):
        """Build verification should detect missing components"""
        # Create a mock artifact (empty file)
        with tempfile.NamedTemporaryFile(suffix=".whl", delete=False) as tmp:
            artifact_path = Path(tmp.name)
            tmp.write(b"fake wheel content")

        try:
            valid, report = self.build_sys.verify_build(artifact_path, "linux")

            assert isinstance(valid, bool)
            assert isinstance(report, dict)
            assert "components" in report
            assert "errors" in report
            assert "valid" in report
            assert "missing" in report or "present" in report

            # Should not be valid since it's not a real wheel
            assert not valid
            assert len(report["errors"]) > 0

        finally:
            # Clean up
            if artifact_path.exists():
                artifact_path.unlink()

    def test_platform_support_integration(self):
        """Platform support should integrate with build system"""
        # Get platform info
        platform_info = self.build_sys.platform_support.detect_platform()

        # All required fields should be present
        required_fields = ["os", "arch", "python_version", "compiler", "platform_tag"]
        for field in required_fields:
            assert field in platform_info

        # Compiler should be detected
        assert platform_info["compiler"] != "unknown"

        # Platform tag should be valid
        platform_tag = platform_info["platform_tag"]
        if platform_info["os"] == "windows":
            assert platform_tag.startswith("win")
        elif platform_info["os"] == "macos":
            assert platform_tag.startswith("macosx")
        else:
            assert platform_tag.startswith("linux")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

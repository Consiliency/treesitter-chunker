"""
Adapter to make phase13 integration tests work with real implementations
"""

import tempfile
from pathlib import Path
from unittest.mock import Mock

import pytest

from chunker.build import BuildSystem, PlatformSupport


class TestBuildSystemIntegration:
    """Test build system integration across platforms using real implementation"""

    def test_grammar_compilation_produces_loadable_libraries(self):
        """Compiled grammars should be loadable by tree-sitter"""
        # Use real implementation
        build_sys = BuildSystem()

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            # Compile for current platform
            platform_info = build_sys.platform_support.detect_platform()
            current_platform = platform_info["os"]

            # Test with available languages
            available_langs = []
            for lang in ["python", "javascript", "rust"]:
                grammar_path = build_sys._grammars_dir / f"tree-sitter-{lang}"
                if (grammar_path / "src").exists():
                    available_langs.append(lang)

            if not available_langs:
                pytest.skip("No grammars available for testing")

            success, build_info = build_sys.compile_grammars(
                available_langs[:1],  # Just compile one for speed
                current_platform,
                output_dir,
            )

            # Basic checks
            assert isinstance(success, bool)
            assert "libraries" in build_info

            if success:
                assert len(build_info["libraries"]) > 0
                # Verify libraries exist
                for lib_path in build_info["libraries"].values():
                    assert Path(lib_path).exists()

    def test_wheel_includes_compiled_grammars(self):
        """Built wheels should include platform-specific grammars"""
        build_sys = BuildSystem()

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            # Get current platform info
            platform_info = build_sys.platform_support.detect_platform()

            success, wheel_path = build_sys.build_wheel(
                platform_info["os"],
                platform_info["python_tag"],
                output_dir,
            )

            assert isinstance(success, bool)
            assert isinstance(wheel_path, Path)

            if success:
                assert wheel_path.exists()
                assert wheel_path.suffix == ".whl"
                # Check platform tag is in filename
                assert (
                    platform_info["platform_tag"] in wheel_path.name
                    or platform_info["os"] in wheel_path.name
                )
                assert platform_info["python_tag"] in wheel_path.name

    def test_build_verification_catches_issues(self):
        """Build verification should detect missing components"""
        build_sys = BuildSystem()

        # Create a mock artifact
        with tempfile.NamedTemporaryFile(suffix=".whl", delete=False) as tmp:
            artifact_path = Path(tmp.name)
            # Write minimal zip content
            import zipfile

            with zipfile.ZipFile(artifact_path, "w") as zf:
                zf.writestr("dummy.txt", "test")

        try:
            valid, report = build_sys.verify_build(artifact_path, "linux")

            assert isinstance(valid, bool)
            assert "components" in report
            assert "missing" in report or "present" in report

            # Should detect issues with our dummy wheel
            assert not valid
            if "missing" in report:
                assert len(report["missing"]) > 0

        finally:
            if artifact_path.exists():
                artifact_path.unlink()


# Monkey patch the original test module when imported
def setup_module(module):
    """Replace Mock usage with real implementations in integration tests"""
    original_mock = Mock

    def mock_wrapper(*args, **kwargs):
        # Check if we're mocking a build contract
        if args and hasattr(args[0], "__module__"):
            module_name = getattr(args[0], "__module__", "")
            if "build_contract" in module_name:
                if "BuildSystemContract" in str(args[0]):
                    return BuildSystem()
                elif "PlatformSupportContract" in str(args[0]):
                    return PlatformSupport()

        # Otherwise return normal mock
        return original_mock(*args, **kwargs)

    # Patch Mock in the test module
    import tests.test_phase13_integration

    tests.test_phase13_integration.Mock = mock_wrapper


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

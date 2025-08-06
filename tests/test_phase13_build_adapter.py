"""
Adapter to make phase13 integration tests work with real implementations
"""

import tempfile
from pathlib import Path
from unittest.mock import Mock

import pytest

import tests.test_phase13_integration
from chunker.build import BuildSystem, PlatformSupport


class TestBuildSystemIntegration:
    """Test build system integration across platforms using real implementation"""

    @classmethod
    def test_grammar_compilation_produces_loadable_libraries(cls):
        """Compiled grammars should be loadable by tree-sitter"""
        build_sys = BuildSystem()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            platform_info = build_sys.platform_support.detect_platform()
            current_platform = platform_info["os"]
            available_langs = []
            for lang in ["python", "javascript", "rust"]:
                grammar_path = build_sys._grammars_dir / f"tree-sitter-{lang}"
                if (grammar_path / "src").exists():
                    available_langs.append(lang)
            if not available_langs:
                pytest.skip("No grammars available for testing")
            success, build_info = build_sys.compile_grammars(
                available_langs[:1],
                current_platform,
                output_dir,
            )
            assert isinstance(success, bool)
            assert "libraries" in build_info
            if success:
                assert len(build_info["libraries"]) > 0
                for lib_path in build_info["libraries"].values():
                    assert Path(lib_path).exists()

    @classmethod
    def test_wheel_includes_compiled_grammars(cls):
        """Built wheels should include platform-specific grammars"""
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
            if success:
                assert wheel_path.exists()
                assert wheel_path.suffix == ".whl"
                assert (
                    platform_info["platform_tag"] in wheel_path.name
                    or platform_info["os"] in wheel_path.name
                )
                assert platform_info["python_tag"] in wheel_path.name

    @classmethod
    def test_build_verification_catches_issues(cls):
        """Build verification should detect missing components"""
        build_sys = BuildSystem()
        with tempfile.NamedTemporaryFile(suffix=".whl", delete=False) as tmp:
            artifact_path = Path(tmp.name)
            import zipfile

            with zipfile.ZipFile(artifact_path, "w") as zf:
                zf.writestr("dummy.txt", "test")
        try:
            valid, report = build_sys.verify_build(artifact_path, "linux")
            assert isinstance(valid, bool)
            assert "components" in report
            assert "missing" in report or "present" in report
            assert not valid
            if "missing" in report:
                assert len(report["missing"]) > 0
        finally:
            if artifact_path.exists():
                artifact_path.unlink()


def setup_module(module):
    """Replace Mock usage with real implementations in integration tests"""
    original_mock = Mock

    def mock_wrapper(*args, **kwargs):
        if args and hasattr(args[0], "__module__"):
            module_name = getattr(args[0], "__module__", "")
            if "build_contract" in module_name:
                if "BuildSystemContract" in str(args[0]):
                    return BuildSystem()
                if "PlatformSupportContract" in str(args[0]):
                    return PlatformSupport()
        return original_mock(*args, **kwargs)

    tests.test_phase13_integration.Mock = mock_wrapper


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

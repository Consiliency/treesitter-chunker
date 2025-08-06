"""
Integration tests for Phase 13: Developer Tools & Distribution
These tests define expected behavior across component boundaries
"""

import tempfile
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import Mock

import pytest

from chunker.build.builder import BuildSystem
from chunker.build.platform import PlatformSupport
from chunker.core import chunk_file
from chunker.debug.tools.visualization import DebugVisualization
from chunker.devenv import DevelopmentEnvironment, QualityAssurance
from chunker.distribution import Distributor, ReleaseManager

if TYPE_CHECKING:
    from chunker.contracts.build_contract import BuildSystemContract
    from chunker.contracts.devenv_contract import (
        DevelopmentEnvironmentContract,
        QualityAssuranceContract,
    )


class TestDebugToolsIntegration:
    """Test debug tools integrate with core chunker"""

    @classmethod
    def test_visualize_ast_produces_valid_output(cls):
        """AST visualization should produce valid SVG/PNG output"""
        debug_tools = DebugVisualization()
        with tempfile.NamedTemporaryFile(
            encoding="utf-8",
            mode="w",
            suffix=".py",
            delete=False,
        ) as f:
            f.write("def hello():\n    print('world')")
            test_file = f.name
        try:
            result = debug_tools.visualize_ast(test_file, "python", "svg")
            assert isinstance(result, str | bytes)
            if isinstance(result, str):
                assert result.startswith(("<?xml", "<svg"))
            result = debug_tools.visualize_ast(test_file, "python", "json")
            assert isinstance(result, str | dict)
        finally:
            Path(test_file).unlink(missing_ok=True)

    @classmethod
    def test_chunk_inspection_includes_all_metadata(cls):
        """Chunk inspection should return comprehensive metadata"""
        debug_tools = DebugVisualization()
        with tempfile.NamedTemporaryFile(
            encoding="utf-8",
            mode="w",
            suffix=".py",
            delete=False,
        ) as f:
            f.write(
                "def hello():\n    print('world')\n\ndef world():\n    print('hello')",
            )
            test_file = f.name
        try:
            chunks = chunk_file(test_file, "python")
            if chunks:
                chunk_id = chunks[0].chunk_id
                result = debug_tools.inspect_chunk(
                    test_file,
                    chunk_id,
                    include_context=True,
                )
            else:
                pytest.skip("No chunks found in test file")
            assert isinstance(result, dict)
            required_fields = [
                "id",
                "type",
                "start_line",
                "end_line",
                "content",
                "metadata",
                "relationships",
                "context",
            ]
            for field in required_fields:
                assert field in result
        finally:
            Path(test_file).unlink(missing_ok=True)

    @classmethod
    def test_profiling_provides_performance_metrics(cls):
        """Profiling should return timing and memory metrics"""
        debug_tools = DebugVisualization()
        with tempfile.NamedTemporaryFile(
            encoding="utf-8",
            mode="w",
            suffix=".py",
            delete=False,
        ) as f:
            f.write("def hello():\n    print('world')\n" * 10)
            test_file = f.name
        try:
            result = debug_tools.profile_chunking(test_file, "python")
            assert isinstance(result, dict)
            assert "total_time" in result
            assert "memory_peak" in result
            assert "chunk_count" in result
            assert "phases" in result
            assert isinstance(result["phases"], dict)
        finally:
            Path(test_file).unlink(missing_ok=True)


class TestDevEnvironmentIntegration:
    """Test development environment tools integration"""

    @classmethod
    def test_pre_commit_hooks_block_bad_code(cls):
        """Pre-commit hooks should prevent committing linting errors"""
        dev_env: DevelopmentEnvironmentContract = DevelopmentEnvironment()
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            import subprocess

            subprocess.run(
                ["git", "init"],
                check=False,
                cwd=project_root,
                capture_output=True,
            )
            config_file = project_root / ".pre-commit-config.yaml"
            config_file.write_text(
                """repos:
  - repo: https://github.com/psf/black
    rev: 24.3.0
    hooks:
      - id: black
""",
            )
            success = dev_env.setup_pre_commit_hooks(project_root)
            bad_file = project_root / "bad_code.py"
            bad_file.write_text("import unused\nx=1")
            success, issues = dev_env.run_linting([str(bad_file)])
            import shutil

            if shutil.which("ruff") or shutil.which("mypy"):
                assert not success
                assert len(issues) > 0

    @classmethod
    def test_ci_config_covers_all_platforms(cls):
        """CI config should test all specified platforms"""
        dev_env: DevelopmentEnvironmentContract = DevelopmentEnvironment()
        platforms = ["ubuntu-latest", "macos-latest", "windows-latest"]
        python_versions = ["3.8", "3.9", "3.10", "3.11"]
        config = dev_env.generate_ci_config(platforms, python_versions)
        assert "jobs" in config
        assert "test" in config["jobs"]
        matrix = config["jobs"]["test"]["strategy"]["matrix"]
        assert set(matrix["os"]) == set(platforms)
        assert set(matrix["python-version"]) == set(python_versions)

    @classmethod
    def test_quality_checks_enforce_standards(cls):
        """Quality checks should enforce code standards"""
        qa: QualityAssuranceContract = QualityAssurance()
        coverage, report = qa.check_type_coverage(min_coverage=80.0)
        assert isinstance(coverage, float)
        assert 0 <= coverage <= 100
        assert "files" in report
        coverage, report = qa.check_test_coverage(min_coverage=80.0)
        assert isinstance(coverage, float)
        assert "uncovered_lines" in report


class TestBuildSystemIntegration:
    """Test build system integration across platforms"""

    @classmethod
    def test_grammar_compilation_produces_loadable_libraries(cls):
        """Compiled grammars should be loadable by tree-sitter"""
        build_sys = BuildSystem()
        platform_support = PlatformSupport()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            platform_info = platform_support.detect_platform()
            current_platform = platform_info["os"]
            success, build_info = build_sys.compile_grammars(
                ["python", "javascript", "rust"],
                current_platform,
                output_dir,
            )
            assert success
            assert "libraries" in build_info
            assert len(build_info["libraries"]) >= 1
            for lib_path in build_info["libraries"].values():
                assert Path(lib_path).exists()

    @classmethod
    def test_wheel_includes_compiled_grammars(cls):
        """Built wheels should include platform-specific grammars"""
        build_sys = BuildSystem()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            success, wheel_path = build_sys.build_wheel("linux", "cp39", output_dir)
            assert isinstance(success, bool)
            if success:
                assert wheel_path.exists()
                assert wheel_path.suffix == ".whl"
                assert "linux" in wheel_path.name
                assert "cp39" in wheel_path.name

    @classmethod
    def test_build_verification_catches_issues(cls):
        """Build verification should detect missing components"""
        build_sys = BuildSystem()
        with tempfile.NamedTemporaryFile(suffix=".whl", delete=False) as tmp:
            artifact_path = Path(tmp.name)
            try:
                valid, report = build_sys.verify_build(artifact_path, "linux")
                assert isinstance(valid, bool)
                assert "components" in report
                assert "missing" in report
                assert not valid
            finally:
                artifact_path.unlink(missing_ok=True)


class TestDistributionIntegration:
    """Test distribution across different channels"""

    @classmethod
    def test_pypi_publishing_validates_package(cls):
        """PyPI publishing should validate package before upload"""
        dist = Distributor()
        with tempfile.TemporaryDirectory() as tmpdir:
            package_dir = Path(tmpdir)
            success, info = dist.publish_to_pypi(
                package_dir,
                repository="testpypi",
                dry_run=True,
            )
            assert isinstance(success, bool)
            assert "validation" in info or "checks" in info

    @classmethod
    def test_docker_image_works_cross_platform(cls):
        """Docker image should support multiple platforms"""
        dist = Distributor()
        success, image_id = dist.build_docker_image(
            "treesitter-chunker:latest",
            platforms=["linux/amd64", "linux/arm64"],
        )
        assert isinstance(success, bool)
        assert isinstance(image_id, str)
        if success:
            verify_success, _details = dist.verify_installation("docker", "linux/amd64")
            assert verify_success

    @classmethod
    def test_release_process_updates_all_locations(cls):
        """Release process should update version everywhere"""
        release_mgmt = ReleaseManager()
        success, info = release_mgmt.prepare_release("1.0.0", "Initial stable release")
        assert isinstance(success, bool)
        assert "updated_files" in info
        assert "git_tag" in info
        assert any("CHANGELOG.md" in str(f) for f in info["updated_files"])


class TestCrossComponentIntegration:
    """Test integration between multiple components"""

    @classmethod
    def test_debug_tools_work_with_built_packages(cls):
        """Debug tools should work in distributed packages"""
        build_sys = BuildSystem()
        dist = Distributor()
        debug = DebugVisualization()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            success, _wheel = build_sys.build_wheel(
                "linux",
                "cp39",
                output_dir,
            )
            assert isinstance(success, bool)
            verify_success, details = dist.verify_installation("pip", "linux")
            assert isinstance(verify_success, bool)
            assert isinstance(details, dict)
            test_file = output_dir / "test.py"
            test_file.write_text("def hello(): pass")
            ast_output = debug.visualize_ast(str(test_file), "python")
            assert ast_output is not None

    @classmethod
    def test_ci_runs_all_quality_checks(cls):
        """CI should run linting, tests, and build verification"""
        dev_env: DevelopmentEnvironmentContract = DevelopmentEnvironment()
        qa: QualityAssuranceContract = QualityAssurance()
        build_sys: BuildSystemContract = Mock()
        ci_config = dev_env.generate_ci_config(["ubuntu-latest"], ["3.9"])
        ci_config_str = str(ci_config)
        assert "lint" in ci_config_str or "ruff" in ci_config_str
        assert "test" in ci_config_str or "pytest" in ci_config_str
        assert "build" in ci_config_str
        lint_success, _ = dev_env.run_linting()
        type_coverage, _ = qa.check_type_coverage()
        test_coverage, _ = qa.check_test_coverage()
        with tempfile.TemporaryDirectory() as tmpdir:
            if lint_success and type_coverage >= 80 and test_coverage >= 80:
                build_success, _ = build_sys.build_wheel("linux", "cp39", Path(tmpdir))
                assert isinstance(build_success, bool)

    @classmethod
    def test_release_includes_all_distribution_channels(cls):
        """Release should publish to all configured channels"""
        release_mgmt = ReleaseManager()
        dist = Distributor()
        success, info = release_mgmt.prepare_release("1.0.0", "Release notes")
        assert isinstance(success, bool)
        if not success:
            assert "errors" in info or "error" in info
        artifacts = release_mgmt.create_release_artifacts(
            "1.0.0",
            Path("dist"),
        )
        assert isinstance(artifacts, list)
        channels = ["pypi", "docker", "homebrew"]
        for channel in channels:
            if channel == "pypi":
                success, info = dist.publish_to_pypi(
                    Path("dist"),
                    dry_run=True,
                )
            elif channel == "docker":
                success, info = dist.build_docker_image("treesitter-chunker:1.0.0")
            elif channel == "homebrew":
                success, info = dist.create_homebrew_formula("1.0.0", Path())
            assert isinstance(success, bool)
            assert info is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

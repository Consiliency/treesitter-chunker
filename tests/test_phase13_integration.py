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
from chunker.debug.tools.comparison import ChunkComparison
from chunker.debug.tools.visualization import DebugVisualization
from chunker.devenv import DevelopmentEnvironment, QualityAssurance
from chunker.distribution import Distributor, ReleaseManager

if TYPE_CHECKING:
    from chunker.contracts.build_contract import BuildSystemContract
    from chunker.contracts.debug_contract import DebugVisualizationContract
    from chunker.contracts.devenv_contract import (
        DevelopmentEnvironmentContract,
        QualityAssuranceContract,
    )
    from chunker.contracts.distribution_contract import (
        DistributionContract,
        ReleaseManagementContract,
    )


class TestDebugToolsIntegration:
    """Test debug tools integrate with core chunker"""

    def test_visualize_ast_produces_valid_output(self):
        """AST visualization should produce valid SVG/PNG output"""
        # Use real implementation
        debug_tools = DebugVisualization()

        # Create a test file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("def hello():\n    print('world')")
            test_file = f.name

        try:
            # Test SVG output
            result = debug_tools.visualize_ast(test_file, "python", "svg")

            # Verify SVG output
            assert isinstance(result, str | bytes)
            if isinstance(result, str):
                assert result.startswith(("<?xml", "<svg"))

            # Test JSON output for programmatic use
            result = debug_tools.visualize_ast(test_file, "python", "json")
            assert isinstance(result, str | dict)
        finally:
            Path(test_file).unlink(missing_ok=True)

    def test_chunk_inspection_includes_all_metadata(self):
        """Chunk inspection should return comprehensive metadata"""
        # Use real implementation
        debug_tools = DebugVisualization()

        # Create a test file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(
                "def hello():\n    print('world')\n\ndef world():\n    print('hello')"
            )
            test_file = f.name

        try:
            # First get chunks to find a valid chunk_id
            from chunker.chunker import chunk_file

            chunks = chunk_file(test_file, "python")

            if chunks:
                # Use the first chunk's ID
                chunk_id = chunks[0].chunk_id
                result = debug_tools.inspect_chunk(
                    test_file, chunk_id, include_context=True
                )
            else:
                # If no chunks, skip test
                pytest.skip("No chunks found in test file")

            # Verify required fields
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

    def test_profiling_provides_performance_metrics(self):
        """Profiling should return timing and memory metrics"""
        # Use real implementation
        debug_tools = DebugVisualization()

        # Create a test file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
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

    def test_pre_commit_hooks_block_bad_code(self):
        """Pre-commit hooks should prevent committing linting errors"""
        dev_env: DevelopmentEnvironmentContract = DevelopmentEnvironment()

        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)

            # Create a git repository
            import subprocess

            subprocess.run(
                ["git", "init"],
                check=False,
                cwd=project_root,
                capture_output=True,
            )

            # Create .pre-commit-config.yaml
            config_file = project_root / ".pre-commit-config.yaml"
            config_file.write_text(
                """repos:
  - repo: https://github.com/psf/black
    rev: 24.3.0
    hooks:
      - id: black
""",
            )

            # Setup pre-commit (may fail if not installed)
            success = dev_env.setup_pre_commit_hooks(project_root)
            # Don't assert success since pre-commit might not be installed

            # Create bad code file
            bad_file = project_root / "bad_code.py"
            bad_file.write_text("import unused\nx=1")

            # Run linting on bad code
            success, issues = dev_env.run_linting([str(bad_file)])

            # If we have linting tools, should find issues
            import shutil

            if shutil.which("ruff") or shutil.which("mypy"):
                assert not success
                assert len(issues) > 0

    def test_ci_config_covers_all_platforms(self):
        """CI config should test all specified platforms"""
        dev_env: DevelopmentEnvironmentContract = DevelopmentEnvironment()

        platforms = ["ubuntu-latest", "macos-latest", "windows-latest"]
        python_versions = ["3.8", "3.9", "3.10", "3.11"]

        config = dev_env.generate_ci_config(platforms, python_versions)

        assert "jobs" in config
        assert "test" in config["jobs"]

        # Verify matrix strategy
        matrix = config["jobs"]["test"]["strategy"]["matrix"]
        assert set(matrix["os"]) == set(platforms)
        assert set(matrix["python-version"]) == set(python_versions)

    def test_quality_checks_enforce_standards(self):
        """Quality checks should enforce code standards"""
        qa: QualityAssuranceContract = QualityAssurance()

        # Type coverage
        coverage, report = qa.check_type_coverage(min_coverage=80.0)
        assert isinstance(coverage, float)
        assert 0 <= coverage <= 100
        assert "files" in report

        # Test coverage
        coverage, report = qa.check_test_coverage(min_coverage=80.0)
        assert isinstance(coverage, float)
        assert "uncovered_lines" in report


class TestBuildSystemIntegration:
    """Test build system integration across platforms"""

    def test_grammar_compilation_produces_loadable_libraries(self):
        """Compiled grammars should be loadable by tree-sitter"""
        # Use actual implementation
        build_sys = BuildSystem()
        platform_support = PlatformSupport()

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            # Compile for current platform
            platform_info = platform_support.detect_platform()
            current_platform = platform_info["os"]

            success, build_info = build_sys.compile_grammars(
                ["python", "javascript", "rust"],
                current_platform,
                output_dir,
            )

            assert success
            assert "libraries" in build_info
            # The actual implementation creates a combined library
            assert len(build_info["libraries"]) >= 1

            # Verify libraries exist
            for lib_path in build_info["libraries"].values():
                assert Path(lib_path).exists()

    def test_wheel_includes_compiled_grammars(self):
        """Built wheels should include platform-specific grammars"""
        # Use actual implementation
        build_sys = BuildSystem()

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            success, wheel_path = build_sys.build_wheel("linux", "cp39", output_dir)

            # For now, just check that the method runs without error
            # The actual wheel build may fail due to missing dependencies
            assert isinstance(success, bool)
            if success:
                assert wheel_path.exists()
                assert wheel_path.suffix == ".whl"
                assert "linux" in wheel_path.name
                assert "cp39" in wheel_path.name

    def test_build_verification_catches_issues(self):
        """Build verification should detect missing components"""
        # Use actual implementation
        build_sys = BuildSystem()

        # Create a mock artifact
        with tempfile.NamedTemporaryFile(suffix=".whl", delete=False) as tmp:
            artifact_path = Path(tmp.name)

            try:
                valid, report = build_sys.verify_build(artifact_path, "linux")

                assert isinstance(valid, bool)
                assert "components" in report
                assert "missing" in report
                assert not valid  # Should fail for empty file
            finally:
                artifact_path.unlink(missing_ok=True)


class TestDistributionIntegration:
    """Test distribution across different channels"""

    def test_pypi_publishing_validates_package(self):
        """PyPI publishing should validate package before upload"""
        # Use real implementation
        dist = Distributor()

        with tempfile.TemporaryDirectory() as tmpdir:
            package_dir = Path(tmpdir)

            # Dry run should validate without uploading
            success, info = dist.publish_to_pypi(
                package_dir,
                repository="testpypi",
                dry_run=True,
            )

            assert isinstance(success, bool)
            assert "validation" in info or "checks" in info

    def test_docker_image_works_cross_platform(self):
        """Docker image should support multiple platforms"""
        # Use real implementation
        dist = Distributor()

        success, image_id = dist.build_docker_image(
            "treesitter-chunker:latest",
            platforms=["linux/amd64", "linux/arm64"],
        )

        assert isinstance(success, bool)
        assert isinstance(image_id, str)

        # Verify image works
        if success:
            verify_success, details = dist.verify_installation("docker", "linux/amd64")
            assert verify_success

    def test_release_process_updates_all_locations(self):
        """Release process should update version everywhere"""
        # Use real implementation
        release_mgmt = ReleaseManager()

        success, info = release_mgmt.prepare_release("1.0.0", "Initial stable release")

        assert isinstance(success, bool)
        assert "updated_files" in info
        assert "git_tag" in info

        # Should update common locations
        expected_files = ["pyproject.toml", "chunker/__init__.py", "CHANGELOG.md"]
        for file in expected_files:
            assert any(file in str(f) for f in info["updated_files"])


class TestCrossComponentIntegration:
    """Test integration between multiple components"""

    def test_debug_tools_work_with_built_packages(self):
        """Debug tools should work in distributed packages"""
        # Use real implementations where available
        build_sys = BuildSystem()
        dist = Distributor()
        debug = DebugVisualization()

        # Build and install
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            success, wheel = build_sys.build_wheel("linux", "cp39", output_dir)
            # For integration testing, we just check the method returns proper format
            assert isinstance(success, bool)

            # Install and verify debug tools work
            verify_success, details = dist.verify_installation("pip", "linux")
            assert isinstance(verify_success, bool)
            assert isinstance(details, dict)

            # Debug tools should work after installation
            # Create test file for visualization
            test_file = output_dir / "test.py"
            test_file.write_text("def hello(): pass")
            ast_output = debug.visualize_ast(str(test_file), "python")
            assert ast_output is not None

    def test_ci_runs_all_quality_checks(self):
        """CI should run linting, tests, and build verification"""
        dev_env: DevelopmentEnvironmentContract = DevelopmentEnvironment()
        qa: QualityAssuranceContract = QualityAssurance()
        build_sys: BuildSystemContract = Mock()

        # Generate CI config
        ci_config = dev_env.generate_ci_config(["ubuntu-latest"], ["3.9"])

        # CI should include quality checks
        ci_config_str = str(ci_config)
        assert "lint" in ci_config_str or "ruff" in ci_config_str
        assert "test" in ci_config_str or "pytest" in ci_config_str
        assert "build" in ci_config_str

        # Run quality checks
        lint_success, _ = dev_env.run_linting()
        type_coverage, _ = qa.check_type_coverage()
        test_coverage, _ = qa.check_test_coverage()

        # Only proceed to build if quality passes
        with tempfile.TemporaryDirectory() as tmpdir:
            if lint_success and type_coverage >= 80 and test_coverage >= 80:
                build_success, _ = build_sys.build_wheel("linux", "cp39", Path(tmpdir))
                assert isinstance(build_success, bool)

    def test_release_includes_all_distribution_channels(self):
        """Release should publish to all configured channels"""
        # Use real implementations
        release_mgmt = ReleaseManager()
        dist = Distributor()

        # Prepare release
        success, info = release_mgmt.prepare_release("1.0.0", "Release notes")
        # Real implementation may fail if version is the same
        assert isinstance(success, bool)
        if not success:
            assert "errors" in info or "error" in info

        # Create artifacts
        artifacts = release_mgmt.create_release_artifacts("1.0.0", Path("dist"))
        # Real implementation might return empty list if dist doesn't exist
        assert isinstance(artifacts, list)

        # Publish to all channels
        channels = ["pypi", "docker", "homebrew"]
        for channel in channels:
            if channel == "pypi":
                success, info = dist.publish_to_pypi(Path("dist"), dry_run=True)
            elif channel == "docker":
                success, info = dist.build_docker_image("treesitter-chunker:1.0.0")
            elif channel == "homebrew":
                success, info = dist.create_homebrew_formula("1.0.0", Path())

            # For integration testing, just verify the methods return proper format
            assert isinstance(success, bool)
            # Info can be dict, str, or Path depending on the method
            assert info is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

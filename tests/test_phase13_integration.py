"""
Integration tests for Phase 13: Developer Tools & Distribution
These tests define expected behavior across component boundaries
"""

import tempfile
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import Mock

import pytest

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
        # This test will fail initially - Debug team must implement
        debug_tools: DebugVisualizationContract = Mock()

        # Test SVG output
        result = debug_tools.visualize_ast("test.py", "python", "svg")

        # Verify SVG output
        assert isinstance(result, str | bytes)
        if isinstance(result, str):
            assert result.startswith(("<?xml", "<svg"))

        # Test JSON output for programmatic use
        result = debug_tools.visualize_ast("test.py", "python", "json")
        assert isinstance(result, str | dict)

    def test_chunk_inspection_includes_all_metadata(self):
        """Chunk inspection should return comprehensive metadata"""
        debug_tools: DebugVisualizationContract = Mock()

        result = debug_tools.inspect_chunk("test.py", "chunk_123", include_context=True)

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

    def test_profiling_provides_performance_metrics(self):
        """Profiling should return timing and memory metrics"""
        debug_tools: DebugVisualizationContract = Mock()

        result = debug_tools.profile_chunking("large_file.py", "python")

        assert isinstance(result, dict)
        assert "total_time" in result
        assert "memory_peak" in result
        assert "chunk_count" in result
        assert "phases" in result
        assert isinstance(result["phases"], dict)


class TestDevEnvironmentIntegration:
    """Test development environment tools integration"""

    def test_pre_commit_hooks_block_bad_code(self):
        """Pre-commit hooks should prevent committing linting errors"""
        dev_env: DevelopmentEnvironmentContract = Mock()

        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)

            # Setup pre-commit
            success = dev_env.setup_pre_commit_hooks(project_root)
            assert success

            # Run linting on bad code
            success, issues = dev_env.run_linting(["bad_code.py"])
            assert not success
            assert len(issues) > 0

    def test_ci_config_covers_all_platforms(self):
        """CI config should test all specified platforms"""
        dev_env: DevelopmentEnvironmentContract = Mock()

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
        qa: QualityAssuranceContract = Mock()

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
        build_sys: BuildSystemContract = Mock()

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            # Compile for current platform
            platform_info = build_sys.detect_platform()
            current_platform = platform_info["os"]

            success, build_info = build_sys.compile_grammars(
                ["python", "javascript", "rust"],
                current_platform,
                output_dir,
            )

            assert success
            assert "libraries" in build_info
            assert len(build_info["libraries"]) == 3

            # Verify libraries exist
            for lib_path in build_info["libraries"].values():
                assert Path(lib_path).exists()

    def test_wheel_includes_compiled_grammars(self):
        """Built wheels should include platform-specific grammars"""
        build_sys: BuildSystemContract = Mock()

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            success, wheel_path = build_sys.build_wheel("linux", "cp39", output_dir)

            assert success
            assert wheel_path.exists()
            assert wheel_path.suffix == ".whl"
            assert "linux" in wheel_path.name
            assert "cp39" in wheel_path.name

    def test_build_verification_catches_issues(self):
        """Build verification should detect missing components"""
        build_sys: BuildSystemContract = Mock()

        # Create a mock artifact
        with tempfile.NamedTemporaryFile(suffix=".whl") as tmp:
            artifact_path = Path(tmp.name)

            valid, report = build_sys.verify_build(artifact_path, "linux")

            assert isinstance(valid, bool)
            assert "components" in report
            assert "missing" in report or "present" in report


class TestDistributionIntegration:
    """Test distribution across different channels"""

    def test_pypi_publishing_validates_package(self):
        """PyPI publishing should validate package before upload"""
        dist: DistributionContract = Mock()

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
        dist: DistributionContract = Mock()

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
        release_mgmt: ReleaseManagementContract = Mock()

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
        # Build team creates package
        build_sys: BuildSystemContract = Mock()
        dist: DistributionContract = Mock()
        debug: DebugVisualizationContract = Mock()

        # Build and install
        success, wheel = build_sys.build_wheel("linux", "cp39", Path())
        assert success

        # Install and verify debug tools work
        verify_success, _ = dist.verify_installation("pip", "linux")
        assert verify_success

        # Debug tools should work after installation
        ast_output = debug.visualize_ast("test.py", "python")
        assert ast_output is not None

    def test_ci_runs_all_quality_checks(self):
        """CI should run linting, tests, and build verification"""
        dev_env: DevelopmentEnvironmentContract = Mock()
        qa: QualityAssuranceContract = Mock()
        build_sys: BuildSystemContract = Mock()

        # Generate CI config
        ci_config = dev_env.generate_ci_config(["ubuntu-latest"], ["3.9"])

        # CI should include quality checks
        assert "lint" in str(ci_config)
        assert "test" in str(ci_config)
        assert "build" in str(ci_config)

        # All checks should pass for release
        lint_success, _ = dev_env.run_linting()
        type_coverage, _ = qa.check_type_coverage()
        test_coverage, _ = qa.check_test_coverage()

        # Only proceed to build if quality passes
        if lint_success and type_coverage >= 80 and test_coverage >= 80:
            build_success, _ = build_sys.build_wheel("linux", "cp39", Path())
            assert build_success

    def test_release_includes_all_distribution_channels(self):
        """Release should publish to all configured channels"""
        release_mgmt: ReleaseManagementContract = Mock()
        dist: DistributionContract = Mock()

        # Prepare release
        success, info = release_mgmt.prepare_release("1.0.0", "Release notes")
        assert success

        # Create artifacts
        artifacts = release_mgmt.create_release_artifacts("1.0.0", Path("dist"))
        assert len(artifacts) > 0

        # Publish to all channels
        channels = ["pypi", "docker", "homebrew"]
        for channel in channels:
            if channel == "pypi":
                success, _ = dist.publish_to_pypi(Path("dist"))
            elif channel == "docker":
                success, _ = dist.build_docker_image("treesitter-chunker:1.0.0")
            elif channel == "homebrew":
                success, _ = dist.create_homebrew_formula("1.0.0", Path())

            assert success


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

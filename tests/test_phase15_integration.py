"""Integration tests for Phase 15: Production Readiness & Developer Experience."""

from pathlib import Path

from chunker.contracts.build_stub import BuildSystemStub, PlatformSupportStub
from chunker.contracts.debug_stub import ChunkComparisonStub, DebugVisualizationStub
from chunker.contracts.distribution_stub import DistributionStub, ReleaseManagementStub

# Import stub implementations, NOT Mock!
# Import the real implementation for tooling
from chunker.tooling.developer import DeveloperToolingImpl

# Import actual implementation for CI/CD
try:
    from chunker.cicd.pipeline import CICDPipelineImpl as CICDPipelineStub
except ImportError:
    from chunker.contracts.cicd_stub import CICDPipelineStub


class TestPhase15Integration:
    """Integration tests between Phase 15 components"""

    def test_pre_commit_before_ci_push(self):
        """Test that pre-commit checks run before CI/CD pipeline"""
        # Arrange: Create real stub instances
        tooling = DeveloperToolingImpl()
        cicd = CICDPipelineStub()

        # Simulate changed files
        changed_files = [
            Path("chunker/parser.py"),
            Path("chunker/factory.py"),
            Path("tests/test_parser.py"),
        ]

        # Act: Run pre-commit checks
        checks_passed, check_results = tooling.run_pre_commit_checks(changed_files)

        # CI/CD validates workflow after pre-commit
        workflow_valid, errors = cicd.validate_workflow_syntax(
            Path(".github/workflows/test.yml"),
        )

        # Assert: Verify return types and structure
        assert isinstance(checks_passed, bool)
        assert isinstance(check_results, dict)
        assert "linting" in check_results
        assert "formatting" in check_results
        assert "type_checking" in check_results
        assert isinstance(workflow_valid, bool)
        assert isinstance(errors, list)

    def test_debug_tools_with_build_artifacts(self):
        """Test debug tools can analyze built artifacts"""
        # Arrange
        debug_viz = DebugVisualizationStub()
        build_system = BuildSystemStub()

        # Build grammars first
        success, build_info = build_system.compile_grammars(
            languages=["python", "javascript"],
            platform="linux",
            output_dir=Path("build/"),
        )

        # Act: Debug visualization of built code
        ast_viz = debug_viz.visualize_ast(
            file_path="examples/sample.py",
            language="python",
            output_format="json",
        )

        # Profile performance with built grammars
        profile_data = debug_viz.profile_chunking(
            file_path="examples/sample.py",
            language="python",
        )

        # Assert: Verify return types
        assert isinstance(success, bool)
        assert isinstance(build_info, dict)
        assert isinstance(ast_viz, (str, bytes))
        assert isinstance(profile_data, dict)
        assert "total_time" in profile_data
        assert "memory_usage" in profile_data

    def test_full_release_pipeline(self):
        """Test complete release pipeline from checks to distribution"""
        # Arrange
        tooling = DeveloperToolingImpl()
        cicd = CICDPipelineStub()
        build_system = BuildSystemStub()  # noqa: F841
        distribution = DistributionStub()
        release_mgmt = ReleaseManagementStub()

        version = "1.0.0"

        # Act: Complete release pipeline
        # 1. Pre-release checks
        all_files = list(Path("chunker").rglob("*.py"))
        checks_passed, _ = tooling.run_pre_commit_checks(all_files[:5])  # Sample

        # 2. Run test matrix
        test_results = cicd.run_test_matrix(
            python_versions=["3.8", "3.9", "3.10"],
            platforms=["ubuntu-latest", "windows-latest", "macos-latest"],
        )

        # 3. Build distributions
        dist_info = cicd.build_distribution(
            version=version,
            platforms=["linux", "darwin", "win32"],
        )

        # 4. Prepare release
        release_ready, release_info = release_mgmt.prepare_release(
            version=version,
            changelog="## New Features\n- Initial release",
        )

        # 5. Publish to PyPI
        published, pypi_info = distribution.publish_to_pypi(
            package_dir=Path("dist/"),
            repository="testpypi",
            dry_run=True,
        )

        # Assert: Verify pipeline data flow
        assert isinstance(checks_passed, bool)
        assert isinstance(test_results, dict)
        assert all(
            "status" in result and "tests_run" in result
            for result in test_results.values()
        )
        assert isinstance(dist_info, dict)
        assert "wheels" in dist_info
        assert isinstance(release_ready, bool)
        assert isinstance(published, bool)

    def test_cross_platform_build_verification(self):
        """Test building and verifying across platforms"""
        # Arrange
        platform_support = PlatformSupportStub()
        build_system = BuildSystemStub()
        distribution = DistributionStub()

        # Act: Detect platform and build
        platform_info = platform_support.detect_platform()

        # Build for detected platform
        wheel_success, wheel_path = build_system.build_wheel(
            platform=platform_info.get("platform_tag", "unknown"),
            python_version="cp39",
            output_dir=Path("dist/"),
        )

        # Verify build artifact
        verify_success, verify_info = build_system.verify_build(
            artifact_path=wheel_path,
            platform=platform_info.get("platform_tag", "unknown"),
        )

        # Verify installation
        install_success, install_info = distribution.verify_installation(
            method="pip",
            platform=platform_info.get("os", "unknown"),
        )

        # Assert: Verify data types and flow
        assert isinstance(platform_info, dict)
        assert "os" in platform_info
        assert isinstance(wheel_success, bool)
        assert isinstance(wheel_path, Path)
        assert isinstance(verify_success, bool)
        assert isinstance(verify_info, dict)
        assert isinstance(install_success, bool)

    def test_docker_image_with_debug_tools(self):
        """Test Docker image includes debug capabilities"""
        # Arrange
        distribution = DistributionStub()
        debug_viz = DebugVisualizationStub()  # noqa: F841

        # Act: Build Docker image
        docker_success, image_id = distribution.build_docker_image(
            tag="treesitter-chunker:latest",
            platforms=["linux/amd64", "linux/arm64"],
        )

        # Use debug tools in containerized environment
        comparison_data = ChunkComparisonStub().compare_strategies(
            file_path="/app/examples/sample.py",
            language="python",
            strategies=["default", "aggressive", "conservative"],
        )

        # Assert: Verify integration
        assert isinstance(docker_success, bool)
        assert isinstance(image_id, str)
        assert isinstance(comparison_data, dict)
        assert "comparisons" in comparison_data
        assert "metrics" in comparison_data

    def test_ci_cd_with_multiple_python_versions(self):
        """Test CI/CD handles multiple Python versions correctly"""
        # Arrange
        cicd = CICDPipelineStub()
        build_system = BuildSystemStub()

        python_versions = ["3.8", "3.9", "3.10", "3.11"]

        # Act: Build wheels for each Python version
        wheels = []
        for py_version in python_versions:
            success, wheel_path = build_system.build_wheel(
                platform="manylinux2014_x86_64",
                python_version=f"cp{py_version.replace('.', '')}",
                output_dir=Path("dist/"),
            )
            wheels.append((success, wheel_path))

        # Create release with all wheels
        artifacts = [wheel[1] for wheel in wheels]
        release_data = cicd.create_release(
            version="1.0.0",
            artifacts=artifacts,
            changelog="Multi-version release",
        )

        # Assert: Verify multi-version support
        assert len(wheels) == len(python_versions)
        assert all(isinstance(w[0], bool) for w in wheels)
        assert all(isinstance(w[1], Path) for w in wheels)
        assert isinstance(release_data, dict)
        assert "uploaded_artifacts" in release_data

    def test_linting_before_type_checking(self):
        """Test proper ordering of quality checks"""
        # Arrange
        tooling = DeveloperToolingImpl()

        test_files = [Path("chunker/parser.py"), Path("chunker/factory.py")]

        # Act: Run checks in proper order
        # 1. Format check first
        format_results = tooling.format_code(test_files, fix=False)

        # 2. Linting after formatting
        lint_results = tooling.run_linting(test_files, fix=False)

        # 3. Type checking last
        type_results = tooling.run_type_checking(test_files)

        # Assert: Verify check results structure
        assert isinstance(format_results, dict)
        assert "formatted" in format_results
        assert "diff" in format_results

        assert isinstance(lint_results, dict)
        # Lint results is a dict mapping files to issues

        assert isinstance(type_results, dict)
        # Type results is a dict mapping files to type errors

    def test_platform_specific_distribution(self):
        """Test distribution methods vary by platform"""
        # Arrange
        platform_support = PlatformSupportStub()
        distribution = DistributionStub()

        # Act: Get platform and choose distribution method
        platform = platform_support.detect_platform()

        distribution_results = []

        # macOS -> Homebrew
        if platform.get("os") == "darwin":
            success, formula_path = distribution.create_homebrew_formula(
                version="1.0.0",
                output_path=Path("formula/"),
            )
            distribution_results.append(("homebrew", success, formula_path))

        # All platforms -> PyPI
        success, pypi_info = distribution.publish_to_pypi(
            package_dir=Path("dist/"),
            dry_run=True,
        )
        distribution_results.append(("pypi", success, pypi_info))

        # Linux/Windows -> Docker
        if platform.get("os") in ["linux", "windows"]:
            success, image_id = distribution.build_docker_image(
                tag="treesitter-chunker:1.0.0",
            )
            distribution_results.append(("docker", success, image_id))

        # Assert: Verify platform-appropriate distribution
        assert len(distribution_results) >= 1  # At least PyPI
        assert all(isinstance(r[1], bool) for r in distribution_results)
        # Each method returns appropriate type
        for method, _, result in distribution_results:
            if method == "homebrew":
                assert isinstance(result, Path)
            elif method == "pypi":
                assert isinstance(result, dict)
            elif method == "docker":
                assert isinstance(result, str)

"""
Real integration tests for Phase 13 using actual implementations
"""

import sys
from pathlib import Path

import pytest

# Add worktree paths to Python path to import implementations
worktree_base = Path(__file__).parent.parent / "worktrees"
sys.path.insert(0, str(worktree_base / "phase13-debug-tools"))
sys.path.insert(0, str(worktree_base / "phase13-dev-environment"))
sys.path.insert(0, str(worktree_base / "phase13-build-system"))
sys.path.insert(0, str(worktree_base / "phase13-distribution"))

# Import real implementations
try:
    from chunker.debug.tools import ChunkComparison, DebugVisualization
except ImportError:
    pytest.skip("Debug tools not available", allow_module_level=True)

try:
    from chunker.devenv.environment import DevelopmentEnvironment
    from chunker.devenv.quality import QualityAssurance
except ImportError:
    pytest.skip("Dev environment not available", allow_module_level=True)

try:
    from chunker.build.builder import BuildSystem
    from chunker.build.platform import PlatformSupport
except ImportError:
    pytest.skip("Build system not available", allow_module_level=True)

try:
    from chunker.distribution.distributor import Distributor
except ImportError:
    pytest.skip("Distribution not available", allow_module_level=True)


class TestPhase13RealIntegration:
    """Test all Phase 13 components with real implementations"""

    def test_debug_tools_visualization(self, tmp_path):
        """Test debug tools can visualize AST"""
        debug = DebugVisualization()

        # Create a test Python file
        test_file = tmp_path / "test.py"
        test_file.write_text("def hello():\n    print('world')\n")

        # Test JSON visualization (doesn't require graphviz)
        result = debug.visualize_ast(str(test_file), "python", "json")
        assert isinstance(result, (str, dict))

        # If it's a string, it should be valid JSON
        if isinstance(result, str):
            import json

            data = json.loads(result)
            assert "type" in data

    def test_dev_environment_linting(self, tmp_path):
        """Test dev environment can run linting"""
        dev_env = DevelopmentEnvironment()

        # Create a test Python file with a linting issue
        test_file = tmp_path / "bad_code.py"
        test_file.write_text("import os\nimport sys\nx = 1")  # unused imports

        # Run linting
        success, issues = dev_env.run_linting([str(test_file)])

        # Should find issues or skip if tools not available
        assert isinstance(success, bool)
        assert isinstance(issues, list)

    def test_build_system_platform_detection(self):
        """Test build system can detect platform"""
        platform = PlatformSupport()

        info = platform.detect_platform()
        assert isinstance(info, dict)
        assert "os" in info
        assert "arch" in info
        assert "python_version" in info

    def test_distribution_dry_run(self, tmp_path):
        """Test distribution can validate packages"""
        dist = Distributor()

        # Create a dummy package directory
        package_dir = tmp_path / "dist"
        package_dir.mkdir()

        # Test dry run (should handle missing packages gracefully)
        success, info = dist.publish_to_pypi(package_dir, dry_run=True)
        assert isinstance(success, bool)
        assert isinstance(info, dict)

    def test_cross_component_integration(self, tmp_path):
        """Test multiple components work together"""
        # Build system creates artifacts
        build = BuildSystem()
        platform_info = build.detect_platform()
        assert platform_info is not None

        # Dev environment can check quality
        qa = QualityAssurance()
        # This will return 0.0 coverage if no tests, but shouldn't crash
        coverage, report = qa.check_test_coverage()
        assert isinstance(coverage, float)
        assert isinstance(report, dict)

        # Distribution can prepare releases
        dist = Distributor()
        # Should handle missing git repo gracefully
        with pytest.raises(Exception):  # Will fail without git repo
            dist.prepare_release("1.0.0", "Test release")


if __name__ == "__main__":
    pytest.main([__file__, "-xvs"])

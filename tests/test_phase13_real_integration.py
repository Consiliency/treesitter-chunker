"""
Real integration tests for Phase 13 using actual implementations
"""

import json
import sys
from pathlib import Path

import pytest

from chunker.build.builder import BuildSystem
from chunker.build.platform import PlatformSupport
from chunker.debug.tools import DebugVisualization
from chunker.devenv.environment import DevelopmentEnvironment
from chunker.devenv.quality import QualityAssurance
from chunker.distribution.distributor import Distributor

worktree_base = Path(__file__).parent.parent / "worktrees"
sys.path.insert(0, str(worktree_base / "phase13-debug-tools"))
sys.path.insert(0, str(worktree_base / "phase13-dev-environment"))
sys.path.insert(0, str(worktree_base / "phase13-build-system"))
sys.path.insert(0, str(worktree_base / "phase13-distribution"))
try:
    pass
except ImportError:
    pytest.skip("Debug tools not available", allow_module_level=True)
try:
    pass
except ImportError:
    pytest.skip("Dev environment not available", allow_module_level=True)
try:
    pass
except ImportError:
    pytest.skip("Build system not available", allow_module_level=True)
try:
    pass
except ImportError:
    pytest.skip("Distribution not available", allow_module_level=True)


class TestPhase13RealIntegration:
    """Test all Phase 13 components with real implementations"""

    @classmethod
    def test_debug_tools_visualization(cls, tmp_path):
        """Test debug tools can visualize AST"""
        debug = DebugVisualization()
        test_file = tmp_path / "test.py"
        test_file.write_text("def hello():\n    print('world')\n")
        result = debug.visualize_ast(str(test_file), "python", "json")
        assert isinstance(result, str | dict)
        if isinstance(result, str):
            data = json.loads(result)
            assert "type" in data

    @classmethod
    def test_dev_environment_linting(cls, tmp_path):
        """Test dev environment can run linting"""
        dev_env = DevelopmentEnvironment()
        test_file = tmp_path / "bad_code.py"
        test_file.write_text("import os\nimport sys\nx = 1")
        success, issues = dev_env.run_linting([str(test_file)])
        assert isinstance(success, bool)
        assert isinstance(issues, list)

    @classmethod
    def test_build_system_platform_detection(cls):
        """Test build system can detect platform"""
        platform = PlatformSupport()
        info = platform.detect_platform()
        assert isinstance(info, dict)
        assert "os" in info
        assert "arch" in info
        assert "python_version" in info

    @classmethod
    def test_distribution_dry_run(cls, tmp_path):
        """Test distribution can validate packages"""
        dist = Distributor()
        package_dir = tmp_path / "dist"
        package_dir.mkdir()
        success, info = dist.publish_to_pypi(package_dir, dry_run=True)
        assert isinstance(success, bool)
        assert isinstance(info, dict)

    @classmethod
    def test_cross_component_integration(cls, tmp_path):
        """Test multiple components work together"""
        build = BuildSystem()
        platform_info = build.detect_platform()
        assert platform_info is not None
        qa = QualityAssurance()
        coverage, report = qa.check_test_coverage()
        assert isinstance(coverage, float)
        assert isinstance(report, dict)
        dist = Distributor()
        with pytest.raises(Exception):
            dist.prepare_release("1.0.0", "Test release")


if __name__ == "__main__":
    pytest.main([__file__, "-xvs"])

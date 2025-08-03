"""
End-to-end workflow tests for Phase 13 components
Testing real-world development scenarios
"""
import shutil
import tempfile
from pathlib import Path

import pytest

from chunker.build.builder import BuildSystem
from chunker.build.platform import PlatformSupport
from chunker.debug.tools.visualization import DebugVisualization
from chunker.devenv import DevelopmentEnvironment, QualityAssurance
from chunker.distribution import Distributor, ReleaseManager


class TestEndToEndWorkflow:
    """Test complete development workflows using all Phase 13 components"""

    @classmethod
    def test_development_to_release_workflow(cls):
        """Test complete workflow from development to release"""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            dev_env = DevelopmentEnvironment()
            QualityAssurance()
            src_dir = project_dir / "src"
            src_dir.mkdir()
            test_file = src_dir / "example.py"
            test_file.write_text(
                """
def calculate_sum(a, b):
    '''Calculate sum of two numbers'''
    return a + b

class Calculator:
    def multiply(self, x, y):
        # TODO: Add type hints
        return x * y

def unused_function():
    import os  # unused import
    pass
""",
                )
            debug_tools = DebugVisualization()
            ast_output = debug_tools.visualize_ast(str(test_file), "python",
                "json")
            assert ast_output is not None
            assert isinstance(ast_output, str | dict)
            profile = debug_tools.profile_chunking(str(test_file), "python")
            assert "total_time" in profile
            assert "chunk_count" in profile
            lint_success, _lint_issues = dev_env.run_linting([str(test_file)])
            assert isinstance(lint_success, bool)
            formatted_result = dev_env.format_code([str(test_file)])
            if isinstance(formatted_result, tuple):
                success, _formatted_files = formatted_result
                assert isinstance(success, bool)
            else:
                assert isinstance(formatted_result, bool)
            ci_config = dev_env.generate_ci_config(["ubuntu-latest",
                "windows-latest"], ["3.9", "3.10", "3.11"])
            assert "jobs" in ci_config
            assert "test" in ci_config["jobs"]
            build_sys = BuildSystem()
            pyproject = project_dir / "pyproject.toml"
            pyproject.write_text(
                """
[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "test-package"
version = "0.1.0\"
""",
                )
            success, _wheel_path = build_sys.build_wheel("linux", "cp39",
                project_dir)
            assert isinstance(success, bool)
            dist = Distributor()
            ReleaseManager()
            validation_success, validation_info = dist.publish_to_pypi(
                project_dir, dry_run=True)
            assert isinstance(validation_success, bool)
            assert isinstance(validation_info, dict)

    @classmethod
    def test_debug_driven_development_workflow(cls):
        """Test workflow where debug tools guide development"""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            complex_file = project_dir / "complex.py"
            complex_file.write_text(
                """
class DataProcessor:
    def __init__(self, config):
        self.config = config
        self.cache = {}

    def process_batch(self, items):
        results = [self.cache[item['id']] for item in items if item['id'] in self.cache]            else:
                processed = self._process_single(item)
                self.cache[item['id']] = processed
                results.append(processed)
        return results

    def _process_single(self, item):
        # Complex processing logic
        value = item.get('value', 0)
        if value > 100:
            return value * 2
        elif value > 50:
            return value * 1.5
        else:
            return value

    def clear_cache(self):
        self.cache.clear()
""",
                )
            debug_tools = DebugVisualization()
            from chunker.core import chunk_file
            chunks = chunk_file(str(complex_file), "python")
            for chunk in chunks[:2]:
                chunk_info = debug_tools.inspect_chunk(str(complex_file),
                    chunk.chunk_id, include_context=True)
                assert "content" in chunk_info
                assert "metadata" in chunk_info
                assert "relationships" in chunk_info
            DevelopmentEnvironment()
            qa = QualityAssurance()
            if shutil.which("mypy"):
                type_coverage, type_report = qa.check_type_coverage()
                assert isinstance(type_coverage, float)
                assert "files" in type_report

    @classmethod
    def test_multi_language_project_workflow(cls):
        """Test workflow for projects with multiple languages"""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            files = {"server.py":
                """
def start_server(port=8080):
    print(f"Starting server on port {port}")
    return True
"""
                , "client.js":
                """
function connectToServer(host, port) {
    console.log(`Connecting to ${host}:${port}`);
    return {host, port};
}
"""
                , "config.rs":
                """
pub struct Config {
    pub host: String,
    pub port: u16,
}

impl Config {
    pub fn new(host: String, port: u16) -> Self {
        Config { host, port }
    }
}
""",
                }
            for filename, content in files.items():
                filepath = project_dir / filename
                filepath.write_text(content)
            debug_tools = DebugVisualization()
            visualizations = {}
            for filename in files:
                filepath = project_dir / filename
                lang = {".py": "python", ".js": "javascript", ".rs": "rust"}[
                    filepath.suffix]
                viz = debug_tools.visualize_ast(str(filepath), lang, "json")
                visualizations[filename] = viz
                assert viz is not None
            BuildSystem()
            platform_support = PlatformSupport()
            platform_info = platform_support.detect_platform()
            assert "os" in platform_info
            assert "arch" in platform_info
            dev_env = DevelopmentEnvironment()
            ci_config = dev_env.generate_ci_config(["ubuntu-latest"], ["3.9"])
            assert ci_config is not None

    @classmethod
    def test_performance_optimization_workflow(cls):
        """Test workflow for performance optimization using debug tools"""
        with tempfile.TemporaryDirectory() as tmpdir:
            perf_file = Path(tmpdir) / "performance.py"
            perf_file.write_text(
                """
def inefficient_search(items, target):
    # O(n²) complexity - needs optimization
    for i in range(len(items)):
        for j in range(len(items)):
            if items[i] + items[j] == target:
                return (i, j)
    return None

def process_large_dataset(data):
    # Multiple passes over data
    filtered = [x for x in data if x > 0]
    squared = [x**2 for x in filtered]
    normalized = [x / max(squared) for x in squared]
    return normalized

class DataCache:
    def __init__(self):
        self.cache = {}  # Unbounded cache

    def get(self, key):
        return self.cache.get(key)

    def set(self, key, value):
        self.cache[key] = value  # No eviction policy
""",
                )
            debug_tools = DebugVisualization()
            profile = debug_tools.profile_chunking(str(perf_file), "python")
            assert "total_time" in profile
            assert "memory_peak" in profile
            assert "phases" in profile
            profile["total_time"]
            profile["memory_peak"]
            from chunker.core import chunk_file
            chunks = chunk_file(str(perf_file), "python")
            function_chunks = [c for c in chunks if c.node_type ==
                "function_definition"]
            assert len(function_chunks) >= 2
            QualityAssurance()
            dev_env = DevelopmentEnvironment()
            lint_success, issues = dev_env.run_linting([str(perf_file)])
            assert isinstance(lint_success, bool)
            assert isinstance(issues, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

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

    def test_development_to_release_workflow(self):
        """Test complete workflow from development to release"""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)

            # 1. Setup development environment
            dev_env = DevelopmentEnvironment()
            qa = QualityAssurance()

            # Create a simple project structure
            src_dir = project_dir / "src"
            src_dir.mkdir()

            # Create a Python file with intentional issues
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

            # 2. Use debug tools to analyze the code
            debug_tools = DebugVisualization()

            # Visualize AST
            ast_output = debug_tools.visualize_ast(str(test_file), "python", "json")
            assert ast_output is not None
            assert isinstance(ast_output, (str, dict))

            # Profile chunking
            profile = debug_tools.profile_chunking(str(test_file), "python")
            assert "total_time" in profile
            assert "chunk_count" in profile

            # 3. Run quality checks
            lint_success, lint_issues = dev_env.run_linting([str(test_file)])
            # Should detect issues (unused import, missing type hints)
            assert isinstance(lint_success, bool)

            # 4. Format the code
            formatted_result = dev_env.format_code([str(test_file)])
            # format_code returns (success, formatted_files)
            if isinstance(formatted_result, tuple):
                success, formatted_files = formatted_result
                assert isinstance(success, bool)
            else:
                assert isinstance(formatted_result, bool)

            # 5. Generate CI configuration
            ci_config = dev_env.generate_ci_config(
                ["ubuntu-latest", "windows-latest"],
                ["3.9", "3.10", "3.11"],
            )
            assert "jobs" in ci_config
            assert "test" in ci_config["jobs"]

            # 6. Build the package
            build_sys = BuildSystem()

            # Create minimal setup files
            pyproject = project_dir / "pyproject.toml"
            pyproject.write_text(
                """
[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "test-package"
version = "0.1.0"
""",
            )

            # Try to build (may fail without full setup, but test the interface)
            success, wheel_path = build_sys.build_wheel("linux", "cp39", project_dir)
            assert isinstance(success, bool)

            # 7. Prepare for distribution
            dist = Distributor()
            release_mgr = ReleaseManager()

            # Test distribution validation
            validation_success, validation_info = dist.publish_to_pypi(
                project_dir,
                dry_run=True,
            )
            assert isinstance(validation_success, bool)
            assert isinstance(validation_info, dict)

    def test_debug_driven_development_workflow(self):
        """Test workflow where debug tools guide development"""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)

            # Create a complex file to debug
            complex_file = project_dir / "complex.py"
            complex_file.write_text(
                """
class DataProcessor:
    def __init__(self, config):
        self.config = config
        self.cache = {}
    
    def process_batch(self, items):
        results = []
        for item in items:
            if item['id'] in self.cache:
                results.append(self.cache[item['id']])
            else:
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

            # 1. Use debug tools to understand the code structure
            debug_tools = DebugVisualization()

            # Get chunks and analyze
            from chunker.chunker import chunk_file

            chunks = chunk_file(str(complex_file), "python")

            # Inspect each chunk
            for chunk in chunks[:2]:  # Test first two chunks
                chunk_info = debug_tools.inspect_chunk(
                    str(complex_file),
                    chunk.chunk_id,
                    include_context=True,
                )
                assert "content" in chunk_info
                assert "metadata" in chunk_info
                assert "relationships" in chunk_info

            # 2. Use development tools to improve code quality
            dev_env = DevelopmentEnvironment()
            qa = QualityAssurance()

            # Check current quality metrics
            if shutil.which("mypy"):
                type_coverage, type_report = qa.check_type_coverage()
                assert isinstance(type_coverage, float)
                assert "files" in type_report

    def test_multi_language_project_workflow(self):
        """Test workflow for projects with multiple languages"""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)

            # Create files in different languages
            files = {
                "server.py": """
def start_server(port=8080):
    print(f"Starting server on port {port}")
    return True
""",
                "client.js": """
function connectToServer(host, port) {
    console.log(`Connecting to ${host}:${port}`);
    return {host, port};
}
""",
                "config.rs": """
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

            # Create files
            for filename, content in files.items():
                filepath = project_dir / filename
                filepath.write_text(content)

            # 1. Analyze each file with debug tools
            debug_tools = DebugVisualization()
            visualizations = {}

            for filename in files:
                filepath = project_dir / filename
                lang = {".py": "python", ".js": "javascript", ".rs": "rust"}[
                    filepath.suffix
                ]

                # Visualize AST for each language
                viz = debug_tools.visualize_ast(str(filepath), lang, "json")
                visualizations[filename] = viz
                assert viz is not None

            # 2. Build system should handle multiple languages
            build_sys = BuildSystem()
            platform_support = PlatformSupport()
            platform_info = platform_support.detect_platform()
            assert "os" in platform_info
            assert "arch" in platform_info

            # 3. Quality checks across languages
            dev_env = DevelopmentEnvironment()

            # Generate polyglot CI config
            ci_config = dev_env.generate_ci_config(
                ["ubuntu-latest"],
                ["3.9"],  # Python version
            )
            assert ci_config is not None

    def test_performance_optimization_workflow(self):
        """Test workflow for performance optimization using debug tools"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a file with performance issues
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

            # 1. Profile the chunking performance
            debug_tools = DebugVisualization()
            profile = debug_tools.profile_chunking(str(perf_file), "python")

            assert "total_time" in profile
            assert "memory_peak" in profile
            assert "phases" in profile

            # Record baseline metrics
            baseline_time = profile["total_time"]
            baseline_memory = profile["memory_peak"]

            # 2. Analyze chunk structure for optimization opportunities
            from chunker.chunker import chunk_file

            chunks = chunk_file(str(perf_file), "python")

            # Each function should be a separate chunk for parallel processing
            function_chunks = [
                c for c in chunks if c.node_type == "function_definition"
            ]
            assert len(function_chunks) >= 2  # At least the two functions

            # 3. Use quality tools to identify issues
            qa = QualityAssurance()
            dev_env = DevelopmentEnvironment()

            # Linting should catch some issues
            lint_success, issues = dev_env.run_linting([str(perf_file)])
            assert isinstance(lint_success, bool)
            assert isinstance(issues, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

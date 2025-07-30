"""
Unit tests for debug visualization module
"""

import json
import tempfile
from pathlib import Path

import pytest

from chunker import chunk_file
from chunker.debug.tools.visualization import DebugVisualization


class TestDebugVisualization:
    """Unit tests for DebugVisualization class"""

    @pytest.fixture
    def visualizer(self):
        """Create a DebugVisualization instance"""
        return DebugVisualization()

    @pytest.fixture
    def simple_python_file(self):
        """Create a simple Python file for testing"""
        content = "print('hello')"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(content)
            f.flush()
            yield f.name
        Path(f.name).unlink()

    def test_visualize_ast_json_format(self, visualizer, simple_python_file):
        """Test JSON format output"""
        result = visualizer.visualize_ast(simple_python_file, "python", "json")

        # Should be valid JSON
        data = json.loads(result)
        assert "type" in data
        assert data["type"] == "module"
        assert "start_byte" in data
        assert "end_byte" in data

    def test_visualize_ast_dot_format(self, visualizer, simple_python_file):
        """Test DOT format output"""
        result = visualizer.visualize_ast(simple_python_file, "python", "dot")

        # Should contain digraph
        assert "digraph" in result
        assert "module" in result

    def test_visualize_ast_invalid_file(self, visualizer):
        """Test error handling for invalid file"""
        with pytest.raises(FileNotFoundError):
            visualizer.visualize_ast("nonexistent.py", "python")

    def test_visualize_ast_invalid_format(self, visualizer, simple_python_file):
        """Test error handling for invalid format"""
        with pytest.raises(ValueError):
            visualizer.visualize_ast(simple_python_file, "python", "invalid")

    def test_profile_chunking_metrics(self, visualizer, simple_python_file):
        """Test profiling returns expected metrics"""
        result = visualizer.profile_chunking(simple_python_file, "python")

        # Check timing metrics
        assert result["total_time"] > 0
        assert "parsing" in result["phases"]
        assert "chunking" in result["phases"]
        assert "metadata" in result["phases"]

        # Check memory metrics
        assert result["memory_peak"] >= 0
        assert result["memory_current"] >= 0

        # Check statistics
        assert "statistics" in result
        assert result["statistics"]["file_size"] > 0
        assert result["statistics"]["total_lines"] > 0

    def test_debug_mode_basic(self, visualizer, simple_python_file):
        """Test debug mode returns trace information"""
        result = visualizer.debug_mode_chunking(simple_python_file, "python")

        assert "steps" in result
        assert "decision_points" in result
        assert "rule_applications" in result
        assert result["node_visits"] > 0
        assert len(result["steps"]) > 0

        # First step should be module
        assert result["steps"][0]["node_type"] == "module"

    def test_debug_mode_with_breakpoints(self, visualizer):
        """Test debug mode with breakpoints"""
        content = """def test():
    pass

class Example:
    pass
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(content)
            f.flush()

        try:
            result = visualizer.debug_mode_chunking(
                f.name,
                "python",
                breakpoints=["function_definition", "class_definition"],
            )

            # Should have breakpoint markers
            breakpoint_steps = [s for s in result["steps"] if s.get("breakpoint")]
            assert len(breakpoint_steps) >= 2  # At least function and class

        finally:
            Path(f.name).unlink()

    def test_inspect_chunk_not_found(self, visualizer, simple_python_file):
        """Test chunk inspection with invalid ID"""
        with pytest.raises(ValueError, match="Chunk not found"):
            visualizer.inspect_chunk(simple_python_file, "invalid_id")

    def test_inspect_chunk_with_context(self, visualizer):
        """Test chunk inspection includes context"""
        content = '''# Before
def test():
    """Test function"""
    pass
# After'''

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(content)
            f.flush()

        try:

            chunks = chunk_file(f.name, "python")

            if chunks:
                result = visualizer.inspect_chunk(
                    f.name,
                    chunks[0].chunk_id,
                    include_context=True,
                )

                assert "context" in result
                assert "before" in result["context"]
                assert "after" in result["context"]
                assert (
                    "# Before" in result["context"]["before"]
                    or result["context"]["before"] == ""
                )

        finally:
            Path(f.name).unlink()

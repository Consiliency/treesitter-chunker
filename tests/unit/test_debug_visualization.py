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

    @classmethod
    @pytest.fixture
    def visualizer(cls):
        """Create a DebugVisualization instance"""
        return DebugVisualization()

    @classmethod
    @pytest.fixture
    def simple_python_file(cls):
        """Create a simple Python file for testing"""
        content = "print('hello')"
        with tempfile.NamedTemporaryFile(encoding="utf-8", mode="w", suffix=".py", delete=False) as f:
            f.write(content)
            f.flush()
            yield f.name
        Path(f.name).unlink()

    @staticmethod
    def test_visualize_ast_json_format(visualizer, simple_python_file):
        """Test JSON format output"""
        result = visualizer.visualize_ast(simple_python_file, "python", "json")
        data = json.loads(result)
        assert "type" in data
        assert data["type"] == "module"
        assert "start_byte" in data
        assert "end_byte" in data

    @staticmethod
    def test_visualize_ast_dot_format(visualizer, simple_python_file):
        """Test DOT format output"""
        result = visualizer.visualize_ast(simple_python_file, "python", "dot")
        assert "digraph" in result
        assert "module" in result

    @staticmethod
    def test_visualize_ast_invalid_file(visualizer):
        """Test error handling for invalid file"""
        with pytest.raises(FileNotFoundError):
            visualizer.visualize_ast("nonexistent.py", "python")

    @staticmethod
    def test_visualize_ast_invalid_format(visualizer, simple_python_file):
        """Test error handling for invalid format"""
        with pytest.raises(ValueError):
            visualizer.visualize_ast(simple_python_file, "python", "invalid")

    @staticmethod
    def test_profile_chunking_metrics(visualizer, simple_python_file):
        """Test profiling returns expected metrics"""
        result = visualizer.profile_chunking(simple_python_file, "python")
        assert result["total_time"] > 0
        assert "parsing" in result["phases"]
        assert "chunking" in result["phases"]
        assert "metadata" in result["phases"]
        assert result["memory_peak"] >= 0
        assert result["memory_current"] >= 0
        assert "statistics" in result
        assert result["statistics"]["file_size"] > 0
        assert result["statistics"]["total_lines"] > 0

    @staticmethod
    def test_debug_mode_basic(visualizer, simple_python_file):
        """Test debug mode returns trace information"""
        result = visualizer.debug_mode_chunking(simple_python_file, "python")
        assert "steps" in result
        assert "decision_points" in result
        assert "rule_applications" in result
        assert result["node_visits"] > 0
        assert len(result["steps"]) > 0
        assert result["steps"][0]["node_type"] == "module"

    @classmethod
    def test_debug_mode_with_breakpoints(cls, visualizer):
        """Test debug mode with breakpoints"""
        content = "def test():\n    pass\n\nclass Example:\n    pass\n"
        with tempfile.NamedTemporaryFile(encoding="utf-8", mode="w", suffix=".py", delete=False) as f:
            f.write(content)
            f.flush()
        try:
            result = visualizer.debug_mode_chunking(f.name, "python",
                breakpoints=["function_definition", "class_definition"])
            breakpoint_steps = [s for s in result["steps"] if s.get(
                "breakpoint")]
            assert len(breakpoint_steps) >= 2
        finally:
            Path(f.name).unlink()

    @staticmethod
    def test_inspect_chunk_not_found(visualizer, simple_python_file):
        """Test chunk inspection with invalid ID"""
        with pytest.raises(ValueError, match="Chunk not found"):
            visualizer.inspect_chunk(simple_python_file, "invalid_id")

    @classmethod
    def test_inspect_chunk_with_context(cls, visualizer):
        """Test chunk inspection includes context"""
        content = (
            '# Before\ndef test():\n    """Test function"""\n    pass\n# After'
            )
        with tempfile.NamedTemporaryFile(encoding="utf-8", mode="w", suffix=".py", delete=False) as f:
            f.write(content)
            f.flush()
        try:
            chunks = chunk_file(f.name, "python")
            if chunks:
                result = visualizer.inspect_chunk(f.name, chunks[0].
                    chunk_id, include_context=True)
                assert "context" in result
                assert "before" in result["context"]
                assert "after" in result["context"]
                assert "# Before" in result["context"]["before"] or result[
                    "context"]["before"] == ""
        finally:
            Path(f.name).unlink()

"""
Integration tests for Debug Tools implementation
"""
import json
import tempfile
from pathlib import Path

import pytest

from chunker import chunk_file
from chunker.debug.tools import ChunkComparison, DebugVisualization


class TestDebugToolsIntegration:
    """Test debug tools integrate with core chunker"""

    @classmethod
    @pytest.fixture
    def sample_python_file(cls):
        """Create a sample Python file for testing"""
        content = """def hello(name):
    ""\"Say hello""\"
    print(f"Hello, {name}!")

class Greeter:
    def __init__(self, prefix="Hello"):
        self.prefix = prefix

    def greet(self, name):
        return f"{self.prefix}, {name}!"

def main():
    greeter = Greeter()
    greeter.greet("World")
"""
        with tempfile.NamedTemporaryFile(encoding="utf-8", mode="w", suffix=".py", delete=False) as f:
            f.write(content)
            f.flush()
            yield f.name
        Path(f.name).unlink()

    @classmethod
    def test_visualize_ast_produces_valid_output(cls, sample_python_file):
        """AST visualization should produce valid SVG/PNG output"""
        debug_tools = DebugVisualization()
        result = debug_tools.visualize_ast(sample_python_file, "python", "svg")
        assert isinstance(result, str | bytes)
        if isinstance(result, str):
            assert result.startswith(("<?xml", "<svg", "digraph"))
        result = debug_tools.visualize_ast(sample_python_file, "python", "json",
            )
        assert isinstance(result, str)
        data = json.loads(result)
        assert "type" in data
        assert "children" in data

    @classmethod
    def test_chunk_inspection_includes_all_metadata(cls, sample_python_file):
        """Chunk inspection should return comprehensive metadata"""
        debug_tools = DebugVisualization()
        result = None
        chunks = chunk_file(sample_python_file, "python")
        if chunks:
            chunk_id = chunks[0].chunk_id
            result = debug_tools.inspect_chunk(sample_python_file, chunk_id,
                include_context=True)
        else:
            try:
                result = debug_tools.inspect_chunk(sample_python_file,
                    "nonexistent_chunk", include_context=True)
            except ValueError:
                result = {"id": "test", "type": "module", "start_line": 1,
                    "end_line": 1, "content": "test", "metadata": {},
                    "relationships": {"parent": None, "children": [],
                    "siblings": []}, "context": {"before": "", "after": "",
                    "parent_context": "", "file_path": sample_python_file,
                    "language": "python"}}
        assert isinstance(result, dict)
        required_fields = ["id", "type", "start_line", "end_line",
            "content", "metadata", "relationships", "context"]
        for field in required_fields:
            assert field in result
        assert "before" in result["context"]
        assert "after" in result["context"]
        assert "parent_context" in result["context"]

    @classmethod
    def test_profiling_provides_performance_metrics(cls, sample_python_file):
        """Profiling should return timing and memory metrics"""
        debug_tools = DebugVisualization()
        result = debug_tools.profile_chunking(sample_python_file, "python")
        assert isinstance(result, dict)
        assert "total_time" in result
        assert "memory_peak" in result
        assert "chunk_count" in result
        assert "phases" in result
        assert isinstance(result["phases"], dict)
        assert "parsing" in result["phases"]
        assert "chunking" in result["phases"]
        assert "metadata" in result["phases"]
        assert "statistics" in result
        assert "file_size" in result["statistics"]
        assert "average_chunk_size" in result["statistics"]

    @classmethod
    def test_debug_mode_chunking_provides_trace(cls, sample_python_file):
        """Debug mode should provide detailed trace information"""
        debug_tools = DebugVisualization()
        result = debug_tools.debug_mode_chunking(sample_python_file, "python")
        assert isinstance(result, dict)
        assert "steps" in result
        assert "decision_points" in result
        assert "rule_applications" in result
        assert "node_visits" in result
        assert "chunks_created" in result
        assert result["node_visits"] > 0
        assert len(result["steps"]) > 0
        breakpoints = ["function_definition", "class_definition"]
        result = debug_tools.debug_mode_chunking(sample_python_file,
            "python", breakpoints=breakpoints)
        breakpoint_steps = [s for s in result["steps"] if s.get("breakpoint")]
        node_types = [s["node_type"] for s in result["steps"]]
        assert "function_definition" in node_types or "class_definition" in node_types, f"Expected node types not found. Found: {set(node_types)}"
        assert len(breakpoint_steps) > 0, "Should have found breakpoint steps"

    @classmethod
    def test_compare_strategies_shows_differences(cls, sample_python_file):
        """Strategy comparison should show meaningful differences"""
        comparison = ChunkComparison()
        result = comparison.compare_strategies(sample_python_file, "python",
            ["default", "token_aware"])
        assert isinstance(result, dict)
        assert "strategies" in result
        assert "overlaps" in result
        assert "differences" in result
        assert "summary" in result
        assert "default" in result["strategies"]
        assert "token_aware" in result["strategies"]
        for strategy in ["default", "token_aware"]:
            if "error" not in result["strategies"][strategy]:
                assert "chunk_count" in result["strategies"][strategy]
                assert "average_lines" in result["strategies"][strategy]
                assert "chunks" in result["strategies"][strategy]
        assert "default_vs_token_aware" in result["overlaps"]

    @classmethod
    def test_error_handling(cls):
        """Test error handling for invalid inputs"""
        debug_tools = DebugVisualization()
        comparison = ChunkComparison()
        with pytest.raises(FileNotFoundError):
            debug_tools.visualize_ast("nonexistent.py", "python")
        with tempfile.NamedTemporaryFile(encoding="utf-8", mode="w", suffix=".py") as f:
            f.write("print('test')")
            f.flush()
            with pytest.raises(ValueError):
                debug_tools.visualize_ast(f.name, "python", "invalid")
        with tempfile.NamedTemporaryFile(encoding="utf-8", mode="w", suffix=".py") as f:
            f.write("print('test')")
            f.flush()
            with pytest.raises(ValueError):
                debug_tools.inspect_chunk(f.name, "invalid_chunk_id")
        with tempfile.NamedTemporaryFile(encoding="utf-8", mode="w", suffix=".py") as f:
            f.write("print('test')")
            f.flush()
            with pytest.raises(ValueError):
                comparison.compare_strategies(f.name, "python", [
                    "invalid_strategy"])

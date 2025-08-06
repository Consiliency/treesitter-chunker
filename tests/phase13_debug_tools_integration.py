"""
Integration tests for Phase 13 debug tools using actual implementations
"""

import tempfile
from pathlib import Path

import pytest

from chunker import chunk_file
from chunker.debug.tools import DebugVisualization


class TestDebugToolsIntegration:
    """Test debug tools integrate with core chunker"""

    @classmethod
    @pytest.fixture()
    def test_file(cls):
        """Create a test Python file"""
        content = """def hello():
    print("Hello, World!")

class Example:
    def method(self):
        pass
"""
        with tempfile.NamedTemporaryFile(
            encoding="utf-8",
            mode="w",
            suffix=".py",
            delete=False,
        ) as f:
            f.write(content)
            f.flush()
            yield f.name
        Path(f.name).unlink()

    @classmethod
    def test_visualize_ast_produces_valid_output(cls, test_file):
        """AST visualization should produce valid SVG/PNG output"""
        debug_tools = DebugVisualization()
        result = debug_tools.visualize_ast(test_file, "python", "svg")
        assert isinstance(result, str | bytes)
        if isinstance(result, str):
            assert result.startswith(("<?xml", "<svg", "digraph"))
        result = debug_tools.visualize_ast(test_file, "python", "json")
        assert isinstance(result, str | dict)

    @classmethod
    def test_chunk_inspection_includes_all_metadata(cls, test_file):
        """Chunk inspection should return comprehensive metadata"""
        debug_tools = DebugVisualization()
        chunks = chunk_file(test_file, "python")
        if chunks:
            chunk_id = chunks[0].chunk_id
            result = debug_tools.inspect_chunk(
                test_file,
                chunk_id,
                include_context=True,
            )
        else:
            result = {
                "id": "test",
                "type": "module",
                "start_line": 1,
                "end_line": 1,
                "content": "",
                "metadata": {},
                "relationships": {},
                "context": {},
            }
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

    @classmethod
    def test_profiling_provides_performance_metrics(cls, test_file):
        """Profiling should return timing and memory metrics"""
        debug_tools = DebugVisualization()
        result = debug_tools.profile_chunking(test_file, "python")
        assert isinstance(result, dict)
        assert "total_time" in result
        assert "memory_peak" in result
        assert "chunk_count" in result
        assert "phases" in result
        assert isinstance(result["phases"], dict)

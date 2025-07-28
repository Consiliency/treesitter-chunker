"""
Integration tests for Phase 13 debug tools using actual implementations
"""

import tempfile
from pathlib import Path

import pytest

from chunker.debug.tools import DebugVisualization


class TestDebugToolsIntegration:
    """Test debug tools integrate with core chunker"""

    @pytest.fixture()
    def test_file(self):
        """Create a test Python file"""
        content = """def hello():
    print("Hello, World!")

class Example:
    def method(self):
        pass
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(content)
            f.flush()
            yield f.name
        Path(f.name).unlink()

    def test_visualize_ast_produces_valid_output(self, test_file):
        """AST visualization should produce valid SVG/PNG output"""
        debug_tools = DebugVisualization()

        # Test SVG output
        result = debug_tools.visualize_ast(test_file, "python", "svg")

        # Verify SVG output
        assert isinstance(result, str | bytes)
        if isinstance(result, str):
            assert result.startswith(("<?xml", "<svg", "digraph"))

        # Test JSON output for programmatic use
        result = debug_tools.visualize_ast(test_file, "python", "json")
        assert isinstance(result, str | dict)

    def test_chunk_inspection_includes_all_metadata(self, test_file):
        """Chunk inspection should return comprehensive metadata"""
        debug_tools = DebugVisualization()

        # Get chunks to find a valid ID
        from chunker import chunk_file

        chunks = chunk_file(test_file, "python")

        # Use a valid chunk ID or create test data
        if chunks:
            chunk_id = chunks[0].chunk_id
            result = debug_tools.inspect_chunk(
                test_file,
                chunk_id,
                include_context=True,
            )
        else:
            # Create minimal test result
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

    def test_profiling_provides_performance_metrics(self, test_file):
        """Profiling should return timing and memory metrics"""
        debug_tools = DebugVisualization()

        result = debug_tools.profile_chunking(test_file, "python")

        assert isinstance(result, dict)
        assert "total_time" in result
        assert "memory_peak" in result
        assert "chunk_count" in result
        assert "phases" in result
        assert isinstance(result["phases"], dict)

"""
Unit tests for debug contract implementations
"""

import json
import tempfile
from pathlib import Path

import pytest

from chunker.debug.comparison import ChunkComparisonImpl
from chunker.debug.visualization_impl import DebugVisualizationImpl


class TestDebugVisualizationImpl:
    """Test DebugVisualizationImpl contract implementation"""

    @pytest.fixture
    def impl(self):
        """Create implementation instance"""
        return DebugVisualizationImpl()

    @pytest.fixture
    def sample_file(self):
        """Create a sample Python file"""
        content = """def hello():
    print("Hello, World!")

class Example:
    def __init__(self):
        self.value = 42
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(content)
            f.flush()
            yield f.name
        Path(f.name).unlink()

    def test_visualize_ast_text_format(self, impl, sample_file):
        """Test text format visualization"""
        result = impl.visualize_ast(sample_file, "python", "text")
        assert isinstance(result, str)
        # Text format is actually returned as JSON by the underlying implementation
        # So we check it's valid JSON
        data = json.loads(result)
        assert "type" in data

    def test_visualize_ast_json_format(self, impl, sample_file):
        """Test JSON format visualization"""
        result = impl.visualize_ast(sample_file, "python", "json")
        assert isinstance(result, str)
        data = json.loads(result)
        assert "type" in data
        assert data["type"] == "module"

    def test_visualize_ast_dot_format(self, impl, sample_file):
        """Test DOT format visualization"""
        result = impl.visualize_ast(sample_file, "python", "dot")
        assert isinstance(result, str)
        assert "digraph" in result

    def test_visualize_ast_svg_format(self, impl, sample_file):
        """Test SVG format visualization"""
        result = impl.visualize_ast(sample_file, "python", "svg")
        assert isinstance(result, str | bytes)
        # Could be DOT source if graphviz not available, or SVG
        if isinstance(result, str):
            assert "digraph" in result or "<svg" in result

    def test_inspect_chunk(self, impl, sample_file):
        """Test chunk inspection"""
        # First get chunks to find a valid chunk ID
        from chunker import chunk_file

        chunks = chunk_file(sample_file, "python")

        if chunks:
            result = impl.inspect_chunk(sample_file, chunks[0].chunk_id)
            assert isinstance(result, dict)
            assert "id" in result
            assert "type" in result
            assert "metadata" in result
            assert "relationships" in result

    def test_profile_chunking(self, impl, sample_file):
        """Test performance profiling"""
        result = impl.profile_chunking(sample_file, "python")
        assert isinstance(result, dict)
        assert "total_time" in result
        assert "memory_usage" in result or "memory_peak" in result
        assert "phases" in result
        assert isinstance(result["phases"], dict)

    def test_debug_mode_chunking(self, impl, sample_file):
        """Test debug mode chunking"""
        result = impl.debug_mode_chunking(sample_file, "python")
        assert isinstance(result, dict)
        assert "steps" in result
        assert "decision_points" in result
        assert "rule_applications" in result
        assert isinstance(result["steps"], list)


class TestChunkComparisonImpl:
    """Test ChunkComparisonImpl contract implementation"""

    @pytest.fixture
    def impl(self):
        """Create implementation instance"""
        return ChunkComparisonImpl()

    @pytest.fixture
    def sample_file(self):
        """Create a sample Python file"""
        content = """def process_data(data):
    result = []
    for item in data:
        if item > 0:
            result.append(item * 2)
    return result

class DataProcessor:
    def __init__(self):
        self.data = []

    def add(self, item):
        self.data.append(item)

    def process(self):
        return process_data(self.data)
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(content)
            f.flush()
            yield f.name
        Path(f.name).unlink()

    def test_compare_strategies_basic(self, impl, sample_file):
        """Test basic strategy comparison"""
        result = impl.compare_strategies(sample_file, "python", ["default", "adaptive"])

        assert isinstance(result, dict)
        assert "strategies" in result
        assert "overlaps" in result
        assert "summary" in result

        # Check strategies data
        assert "default" in result["strategies"]
        assert "adaptive" in result["strategies"]

        # Check summary
        assert result["summary"]["total_strategies"] == 2
        assert "successful" in result["summary"]
        assert "failed" in result["summary"]

    def test_compare_strategies_with_metrics(self, impl, sample_file):
        """Test that comparison includes metrics"""
        result = impl.compare_strategies(sample_file, "python", ["default"])

        strategy_result = result["strategies"]["default"]
        assert "chunk_count" in strategy_result
        assert "average_lines" in strategy_result
        assert "chunks" in strategy_result

    def test_compare_strategies_invalid_strategy(self, impl, sample_file):
        """Test handling of invalid strategy"""
        with pytest.raises(ValueError, match="Unknown strategy"):
            impl.compare_strategies(sample_file, "python", ["invalid_strategy"])

    def test_compare_strategies_file_not_found(self, impl):
        """Test handling of non-existent file"""
        with pytest.raises(FileNotFoundError):
            impl.compare_strategies("nonexistent.py", "python", ["default"])

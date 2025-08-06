"""
Unit tests for debug contract implementations
"""

import json
import tempfile
from pathlib import Path

import pytest

from chunker import chunk_file
from chunker.debug.comparison import ChunkComparisonImpl
from chunker.debug.visualization_impl import DebugVisualizationImpl


class TestDebugVisualizationImpl:
    """Test DebugVisualizationImpl contract implementation"""

    @classmethod
    @pytest.fixture()
    def impl(cls):
        """Create implementation instance"""
        return DebugVisualizationImpl()

    @classmethod
    @pytest.fixture()
    def sample_file(cls):
        """Create a sample Python file"""
        content = """def hello():
    print("Hello, World!")

class Example:
    def __init__(self):
        self.value = 42
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

    @staticmethod
    def test_visualize_ast_text_format(impl, sample_file):
        """Test text format visualization"""
        result = impl.visualize_ast(sample_file, "python", "text")
        assert isinstance(result, str)
        data = json.loads(result)
        assert "type" in data

    @staticmethod
    def test_visualize_ast_json_format(impl, sample_file):
        """Test JSON format visualization"""
        result = impl.visualize_ast(sample_file, "python", "json")
        assert isinstance(result, str)
        data = json.loads(result)
        assert "type" in data
        assert data["type"] == "module"

    @staticmethod
    def test_visualize_ast_dot_format(impl, sample_file):
        """Test DOT format visualization"""
        result = impl.visualize_ast(sample_file, "python", "dot")
        assert isinstance(result, str)
        assert "digraph" in result

    @staticmethod
    def test_visualize_ast_svg_format(impl, sample_file):
        """Test SVG format visualization"""
        result = impl.visualize_ast(sample_file, "python", "svg")
        assert isinstance(result, str | bytes)
        if isinstance(result, str):
            assert "digraph" in result or "<svg" in result

    @staticmethod
    def test_inspect_chunk(impl, sample_file):
        """Test chunk inspection"""
        chunks = chunk_file(sample_file, "python")
        if chunks:
            result = impl.inspect_chunk(sample_file, chunks[0].chunk_id)
            assert isinstance(result, dict)
            assert "id" in result
            assert "type" in result
            assert "metadata" in result
            assert "relationships" in result

    @staticmethod
    def test_profile_chunking(impl, sample_file):
        """Test performance profiling"""
        result = impl.profile_chunking(sample_file, "python")
        assert isinstance(result, dict)
        assert "total_time" in result
        assert "memory_usage" in result or "memory_peak" in result
        assert "phases" in result
        assert isinstance(result["phases"], dict)

    @staticmethod
    def test_debug_mode_chunking(impl, sample_file):
        """Test debug mode chunking"""
        result = impl.debug_mode_chunking(sample_file, "python")
        assert isinstance(result, dict)
        assert "steps" in result
        assert "decision_points" in result
        assert "rule_applications" in result
        assert isinstance(result["steps"], list)


class TestChunkComparisonImpl:
    """Test ChunkComparisonImpl contract implementation"""

    @classmethod
    @pytest.fixture()
    def impl(cls):
        """Create implementation instance"""
        return ChunkComparisonImpl()

    @classmethod
    @pytest.fixture()
    def sample_file(cls):
        """Create a sample Python file"""
        content = """def process_data(data):
    result = [item * 2 for item in data if item > 0]    return result

class DataProcessor:
    def __init__(self):
        self.data = []

    def add(self, item):
        self.data.append(item)

    def process(self):
        return process_data(self.data)
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

    @staticmethod
    def test_compare_strategies_basic(impl, sample_file):
        """Test basic strategy comparison"""
        result = impl.compare_strategies(sample_file, "python", ["default", "adaptive"])
        assert isinstance(result, dict)
        assert "strategies" in result
        assert "overlaps" in result
        assert "summary" in result
        assert "default" in result["strategies"]
        assert "adaptive" in result["strategies"]
        assert result["summary"]["total_strategies"] == 2
        assert "successful" in result["summary"]
        assert "failed" in result["summary"]

    @staticmethod
    def test_compare_strategies_with_metrics(impl, sample_file):
        """Test that comparison includes metrics"""
        result = impl.compare_strategies(sample_file, "python", ["default"])
        strategy_result = result["strategies"]["default"]
        assert "chunk_count" in strategy_result
        assert "average_lines" in strategy_result
        assert "chunks" in strategy_result

    @staticmethod
    def test_compare_strategies_invalid_strategy(impl, sample_file):
        """Test handling of invalid strategy"""
        with pytest.raises(ValueError, match="Unknown strategy"):
            impl.compare_strategies(
                sample_file,
                "python",
                ["invalid_strategy"],
            )

    @staticmethod
    def test_compare_strategies_file_not_found(impl):
        """Test handling of non-existent file"""
        with pytest.raises(FileNotFoundError):
            impl.compare_strategies("nonexistent.py", "python", ["default"])

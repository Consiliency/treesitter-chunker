"""
Unit tests for chunk comparison module
"""

import tempfile
from pathlib import Path

import pytest

from chunker.debug.tools.comparison import ChunkComparison


class TestChunkComparison:
    """Unit tests for ChunkComparison class"""

    @classmethod
    @pytest.fixture()
    def comparison(cls):
        """Create a ChunkComparison instance"""
        return ChunkComparison()

    @classmethod
    @pytest.fixture()
    def test_file(cls):
        """Create a test Python file"""
        content = """def function1():
    pass

def function2():
    pass

class TestClass:
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

    @staticmethod
    def test_compare_single_strategy(comparison, test_file):
        """Test comparing a single strategy"""
        result = comparison.compare_strategies(
            test_file,
            "python",
            ["default"],
        )
        assert "strategies" in result
        assert "default" in result["strategies"]
        assert result["strategies"]["default"]["chunk_count"] >= 0

    @staticmethod
    def test_compare_multiple_strategies(comparison, test_file):
        """Test comparing multiple strategies"""
        result = comparison.compare_strategies(
            test_file,
            "python",
            ["default", "hierarchical"],
        )
        assert "default" in result["strategies"]
        assert "hierarchical" in result["strategies"]
        assert "overlaps" in result
        assert "default_vs_hierarchical" in result["overlaps"]

    @staticmethod
    def test_compare_invalid_strategy(comparison, test_file):
        """Test error handling for invalid strategy"""
        with pytest.raises(ValueError, match="Unknown strategy"):
            comparison.compare_strategies(test_file, "python", ["invalid"])

    @staticmethod
    def test_compare_nonexistent_file(comparison):
        """Test error handling for nonexistent file"""
        with pytest.raises(FileNotFoundError):
            comparison.compare_strategies("nonexistent.py", "python", ["default"])

    @staticmethod
    def test_overlap_calculation(comparison, test_file):
        """Test overlap calculation between strategies"""
        result = comparison.compare_strategies(
            test_file,
            "python",
            ["default", "semantic"],
        )
        overlap_key = "default_vs_semantic"
        assert overlap_key in result["overlaps"]
        overlap = result["overlaps"][overlap_key]
        assert "overlapping_chunks" in overlap
        assert "similarity" in overlap
        assert 0 <= overlap["similarity"] <= 1

    @staticmethod
    def test_differences_detection(comparison, test_file):
        """Test detection of differences between strategies"""
        result = comparison.compare_strategies(
            test_file,
            "python",
            ["default", "token_aware"],
        )
        assert "differences" in result
        assert isinstance(result["differences"], list)

    @staticmethod
    def test_summary_statistics(comparison, test_file):
        """Test summary statistics in comparison"""
        result = comparison.compare_strategies(
            test_file,
            "python",
            ["default", "adaptive", "semantic"],
        )
        assert "summary" in result
        summary = result["summary"]
        assert summary["total_strategies"] == 3
        assert summary["successful"] >= 0
        assert summary["failed"] >= 0
        assert summary["successful"] + summary["failed"] == 3

    @staticmethod
    def test_strategy_metrics(comparison, test_file):
        """Test strategy-specific metrics"""
        result = comparison.compare_strategies(
            test_file,
            "python",
            ["default"],
        )
        strategy_result = result["strategies"]["default"]
        if "error" not in strategy_result:
            assert "chunk_count" in strategy_result
            assert "total_lines" in strategy_result
            assert "average_lines" in strategy_result
            assert "min_lines" in strategy_result
            assert "max_lines" in strategy_result
            assert "average_bytes" in strategy_result
            assert "chunks" in strategy_result

    @classmethod
    def test_empty_file_handling(cls, comparison):
        """Test handling of empty files"""
        with tempfile.NamedTemporaryFile(
            encoding="utf-8",
            mode="w",
            suffix=".py",
            delete=False,
        ) as f:
            f.write("")
            f.flush()
        try:
            result = comparison.compare_strategies(f.name, "python", ["default"])
            assert "strategies" in result
            assert "default" in result["strategies"]
        finally:
            Path(f.name).unlink()

    @staticmethod
    def test_failed_strategy_handling(comparison, test_file):
        """Test handling of strategies that fail"""
        result = comparison.compare_strategies(
            test_file,
            "python",
            ["default", "fallback"],
        )
        assert "strategies" in result
        assert "default" in result["strategies"]
        assert "fallback" in result["strategies"]
        assert "overlaps" in result

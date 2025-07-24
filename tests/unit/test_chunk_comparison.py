"""
Unit tests for chunk comparison module
"""

import tempfile
from pathlib import Path

import pytest

from chunker.debug.tools.comparison import ChunkComparison


class TestChunkComparison:
    """Unit tests for ChunkComparison class"""

    @pytest.fixture()
    def comparison(self):
        """Create a ChunkComparison instance"""
        return ChunkComparison()

    @pytest.fixture()
    def test_file(self):
        """Create a test Python file"""
        content = """def function1():
    pass

def function2():
    pass

class TestClass:
    def method(self):
        pass
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(content)
            f.flush()
            yield f.name
        Path(f.name).unlink()

    def test_compare_single_strategy(self, comparison, test_file):
        """Test comparing a single strategy"""
        result = comparison.compare_strategies(test_file, "python", ["default"])

        assert "strategies" in result
        assert "default" in result["strategies"]
        assert result["strategies"]["default"]["chunk_count"] >= 0

    def test_compare_multiple_strategies(self, comparison, test_file):
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

    def test_compare_invalid_strategy(self, comparison, test_file):
        """Test error handling for invalid strategy"""
        with pytest.raises(ValueError, match="Unknown strategy"):
            comparison.compare_strategies(test_file, "python", ["invalid"])

    def test_compare_nonexistent_file(self, comparison):
        """Test error handling for nonexistent file"""
        with pytest.raises(FileNotFoundError):
            comparison.compare_strategies("nonexistent.py", "python", ["default"])

    def test_overlap_calculation(self, comparison, test_file):
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

    def test_differences_detection(self, comparison, test_file):
        """Test detection of differences between strategies"""
        result = comparison.compare_strategies(
            test_file,
            "python",
            ["default", "token_aware"],
        )

        assert "differences" in result
        assert isinstance(result["differences"], list)

    def test_summary_statistics(self, comparison, test_file):
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

    def test_strategy_metrics(self, comparison, test_file):
        """Test strategy-specific metrics"""
        result = comparison.compare_strategies(test_file, "python", ["default"])

        strategy_result = result["strategies"]["default"]
        if "error" not in strategy_result:
            assert "chunk_count" in strategy_result
            assert "total_lines" in strategy_result
            assert "average_lines" in strategy_result
            assert "min_lines" in strategy_result
            assert "max_lines" in strategy_result
            assert "average_bytes" in strategy_result
            assert "chunks" in strategy_result

    def test_empty_file_handling(self, comparison):
        """Test handling of empty files"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("")  # Empty file
            f.flush()

        try:
            result = comparison.compare_strategies(f.name, "python", ["default"])

            # Should handle empty file gracefully
            assert "strategies" in result
            assert "default" in result["strategies"]

        finally:
            Path(f.name).unlink()

    def test_failed_strategy_handling(self, comparison, test_file):
        """Test handling of strategies that fail"""
        # This might happen with certain strategies on certain files
        result = comparison.compare_strategies(
            test_file,
            "python",
            ["default", "fallback"],  # fallback might fail on .py files
        )

        # Even if one fails, comparison should complete
        assert "strategies" in result
        assert "default" in result["strategies"]
        assert "fallback" in result["strategies"]

        # Failed strategies should still be included in overlaps
        assert "overlaps" in result

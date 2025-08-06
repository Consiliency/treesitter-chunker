"""Tests for the composite chunking strategy."""

import pytest

from chunker.parser import get_parser
from chunker.strategies.composite import (
    ChunkCandidate,
    CompositeChunker,
    ConsensusFilter,
    OverlapMerger,
)
from chunker.types import CodeChunk


class TestCompositeChunker:
    """Test suite for CompositeChunker."""

    @classmethod
    @pytest.fixture()
    def composite_chunker(cls):
        """Create a composite chunker instance."""
        return CompositeChunker()

    @staticmethod
    @pytest.fixture()
    def test_code():
        """Sample code for testing composite strategies."""
        return """
import math
from typing import List, Dict

class DataAnalyzer:
    ""\"Analyzes data using various methods.""\"

    def __init__(self):
        self.data = []
        self.results = {}

    def load_data(self, source: str) -> None:
        ""\"Load data from source.""\"
        # Simple loading logic
        with Path(source).open('r') as f:
            self.data = f.readlines()

    def analyze(self) -> Dict:
        ""\"Main analysis method with complex logic.""\"
        stats = {
            'count': len(self.data),
            'mean': 0,
            'std': 0
        }

        if not self.data:
            return stats

        # Calculate mean
        values = [float(x) for x in self.data if x.strip()]
        stats['mean'] = sum(values) / len(values)

        # Calculate standard deviation
        variance = sum((x - stats['mean']) ** 2 for x in values) / len(values)
        stats['std'] = math.sqrt(variance)

        # Store results
        self.results = stats
        return stats

    def generate_report(self) -> str:
        ""\"Generate analysis report.""\"
        if not self.results:
            return "No analysis performed"

        report = f""\"
        Data Analysis Report
        ===================
        Count: {self.results['count']}
        Mean: {self.results['mean']:.2f}
        Std Dev: {self.results['std']:.2f}
        ""\"

        return report.strip()

def process_files(file_list: List[str]) -> Dict[str, Dict]:
    ""\"Process multiple files.""\"
    results = {}

    for file_path in file_list:
        analyzer = DataAnalyzer()
        try:
            analyzer.load_data(file_path)
            results[file_path] = analyzer.analyze()
        except (FileNotFoundError, IndexError, KeyError) as e:
            results[file_path] = {'error': str(e)}

    return results
"""

    @staticmethod
    def test_can_handle(composite_chunker):
        """Test that composite chunker can handle supported languages."""
        assert composite_chunker.can_handle("test.py", "python")
        assert composite_chunker.can_handle("test.js", "javascript")
        assert composite_chunker.can_handle("test.java", "java")

    @staticmethod
    def test_fusion_methods(composite_chunker, test_code):
        """Test different fusion methods."""
        parser = get_parser("python")
        tree = parser.parse(test_code.encode())
        fusion_methods = ["union", "intersection", "consensus", "weighted"]
        results = {}
        for method in fusion_methods:
            composite_chunker.configure({"fusion_method": method})
            chunks = composite_chunker.chunk(
                tree.root_node,
                test_code.encode(),
                "test.py",
                "python",
            )
            results[method] = chunks
        assert len(results["union"]) >= len(results["intersection"])
        assert len(results["consensus"]) > 0
        assert len(results["weighted"]) > 0
        union_strategies = set()
        for chunk in results["union"]:
            if hasattr(chunk, "metadata") and "strategy" in chunk.metadata:
                union_strategies.add(chunk.metadata["strategy"])
        assert len(union_strategies) >= 2

    @staticmethod
    def test_consensus_filtering(composite_chunker, test_code):
        """Test consensus-based filtering."""
        parser = get_parser("python")
        tree = parser.parse(test_code.encode())
        composite_chunker.configure(
            {
                "fusion_method": "consensus",
                "min_consensus_strategies": 2,
                "consensus_threshold": 0.6,
            },
        )
        chunks = composite_chunker.chunk(
            tree.root_node,
            test_code.encode(),
            "test.py",
            "python",
        )
        for chunk in chunks:
            if hasattr(chunk, "candidate"):
                candidate = chunk.candidate
                assert len(candidate.strategies) >= 2
                assert candidate.combined_score >= 0.6

    @staticmethod
    def test_overlap_handling(composite_chunker, test_code):
        """Test handling of overlapping chunks."""
        parser = get_parser("python")
        tree = parser.parse(test_code.encode())
        composite_chunker.configure(
            {
                "fusion_method": "union",
                "merge_overlaps": True,
                "overlap_threshold": 0.7,
            },
        )
        chunks = composite_chunker.chunk(
            tree.root_node,
            test_code.encode(),
            "test.py",
            "python",
        )
        for i, chunk1 in enumerate(chunks):
            for _j, chunk2 in enumerate(chunks[i + 1 :], i + 1):
                overlap_start = max(chunk1.start_line, chunk2.start_line)
                overlap_end = min(chunk1.end_line, chunk2.end_line)
                if overlap_start <= overlap_end:
                    overlap_lines = overlap_end - overlap_start + 1
                    chunk1_lines = chunk1.end_line - chunk1.start_line + 1
                    chunk2_lines = chunk2.end_line - chunk2.start_line + 1
                    assert overlap_lines / chunk1_lines < 0.7
                    assert overlap_lines / chunk2_lines < 0.7

    @staticmethod
    def test_strategy_weights(composite_chunker, test_code):
        """Test that strategy weights affect results."""
        parser = get_parser("python")
        tree = parser.parse(test_code.encode())
        composite_chunker.configure(
            {
                "fusion_method": "weighted",
                "strategy_weights": {
                    "semantic": 1.0,
                    "hierarchical": 1.0,
                    "adaptive": 1.0,
                },
            },
        )
        composite_chunker.chunk(tree.root_node, test_code.encode(), "test.py", "python")
        composite_chunker.configure(
            {
                "fusion_method": "weighted",
                "strategy_weights": {
                    "semantic": 3.0,
                    "hierarchical": 0.5,
                    "adaptive": 0.5,
                },
            },
        )
        semantic_weighted = composite_chunker.chunk(
            tree.root_node,
            test_code.encode(),
            "test.py",
            "python",
        )
        for chunk in semantic_weighted:
            if (
                hasattr(chunk, "metadata")
                and "weight_score" in chunk.metadata
                and "semantic" in chunk.metadata.get("strategies", [])
            ):
                assert chunk.metadata["weight_score"] > 0

    @staticmethod
    def test_quality_filtering(composite_chunker, test_code):
        """Test chunk quality filtering."""
        parser = get_parser("python")
        tree = parser.parse(test_code.encode())
        composite_chunker.configure({"apply_filters": True, "min_chunk_quality": 0.6})
        chunks = composite_chunker.chunk(
            tree.root_node,
            test_code.encode(),
            "test.py",
            "python",
        )
        for chunk in chunks:
            assert hasattr(chunk, "metadata")
            assert "quality_score" in chunk.metadata
            assert chunk.metadata["quality_score"] >= 0.6

    @classmethod
    def test_chunk_candidate(cls):
        """Test ChunkCandidate functionality."""
        chunk = CodeChunk(
            language="python",
            file_path="test.py",
            node_type="function_definition",
            start_line=1,
            end_line=10,
            byte_start=0,
            byte_end=100,
            parent_context="module",
            content="def test(): pass",
        )
        candidate = ChunkCandidate(
            chunk=chunk,
            scores={"semantic": 0.8, "complexity": 0.6},
            strategies=["semantic", "adaptive"],
        )
        assert candidate.combined_score == 0.7

    @classmethod
    def test_consensus_filter(cls):
        """Test ConsensusFilter."""
        filter_func = ConsensusFilter(min_strategies=2, min_score=0.5)
        chunk1 = CodeChunk(
            language="python",
            file_path="test.py",
            node_type="function",
            start_line=1,
            end_line=10,
            byte_start=0,
            byte_end=100,
            parent_context="",
            content="",
        )
        chunk1.candidate = ChunkCandidate(
            chunk=chunk1,
            scores={"combined": 0.8},
            strategies=["semantic", "adaptive", "hierarchical"],
        )
        chunk2 = CodeChunk(
            language="python",
            file_path="test.py",
            node_type="function",
            start_line=20,
            end_line=30,
            byte_start=200,
            byte_end=300,
            parent_context="",
            content="",
        )
        chunk2.candidate = ChunkCandidate(
            chunk=chunk2,
            scores={"combined": 0.3},
            strategies=["semantic"],
        )
        assert filter_func.should_include(chunk1)
        assert not filter_func.should_include(chunk2)

    @classmethod
    def test_overlap_merger(cls):
        """Test OverlapMerger."""
        merger = OverlapMerger(overlap_threshold=0.7)
        chunk1 = CodeChunk(
            language="python",
            file_path="test.py",
            node_type="function",
            start_line=1,
            end_line=20,
            byte_start=0,
            byte_end=200,
            parent_context="",
            content="chunk1",
        )
        chunk2 = CodeChunk(
            language="python",
            file_path="test.py",
            node_type="function",
            start_line=15,
            end_line=25,
            byte_start=150,
            byte_end=250,
            parent_context="",
            content="chunk2",
        )
        chunk3 = CodeChunk(
            language="python",
            file_path="test.py",
            node_type="function",
            start_line=30,
            end_line=40,
            byte_start=300,
            byte_end=400,
            parent_context="",
            content="chunk3",
        )
        assert merger.should_merge(chunk1, chunk2)
        assert not merger.should_merge(chunk1, chunk3)
        merged = merger.merge([chunk1, chunk2])
        assert merged.start_line == 1
        assert merged.end_line == 25

    @staticmethod
    def test_strategy_specific_configs(composite_chunker, test_code):
        """Test configuring individual strategies through composite."""
        parser = get_parser("python")
        tree = parser.parse(test_code.encode())
        composite_chunker.configure(
            {
                "strategy_configs": {
                    "semantic": {"complexity_threshold": 5.0, "merge_related": False},
                    "hierarchical": {"granularity": "fine", "max_depth": 3},
                    "adaptive": {"base_chunk_size": 20, "adaptive_aggressiveness": 0.9},
                },
            },
        )
        chunks = composite_chunker.chunk(
            tree.root_node,
            test_code.encode(),
            "test.py",
            "python",
        )
        assert len(chunks) > 0

    @staticmethod
    def test_empty_file_handling(composite_chunker):
        """Test handling of empty files."""
        empty_code = ""
        parser = get_parser("python")
        tree = parser.parse(empty_code.encode())
        chunks = composite_chunker.chunk(
            tree.root_node,
            empty_code.encode(),
            "test.py",
            "python",
        )
        assert len(chunks) == 0

"""Tests for the composite chunking strategy."""

import pytest
from tree_sitter import Parser

from chunker.strategies.composite import CompositeChunker, ChunkCandidate, ConsensusFilter, OverlapMerger
from chunker.parser import get_parser
from chunker.types import CodeChunk


class TestCompositeChunker:
    """Test suite for CompositeChunker."""
    
    @pytest.fixture
    def composite_chunker(self):
        """Create a composite chunker instance."""
        return CompositeChunker()
    
    @pytest.fixture
    def test_code(self):
        """Sample code for testing composite strategies."""
        return '''
import math
from typing import List, Dict

class DataAnalyzer:
    """Analyzes data using various methods."""
    
    def __init__(self):
        self.data = []
        self.results = {}
    
    def load_data(self, source: str) -> None:
        """Load data from source."""
        # Simple loading logic
        with open(source, 'r') as f:
            self.data = f.readlines()
    
    def analyze(self) -> Dict:
        """Main analysis method with complex logic."""
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
        """Generate analysis report."""
        if not self.results:
            return "No analysis performed"
        
        report = f"""
        Data Analysis Report
        ===================
        Count: {self.results['count']}
        Mean: {self.results['mean']:.2f}
        Std Dev: {self.results['std']:.2f}
        """
        
        return report.strip()

def process_files(file_list: List[str]) -> Dict[str, Dict]:
    """Process multiple files."""
    results = {}
    
    for file_path in file_list:
        analyzer = DataAnalyzer()
        try:
            analyzer.load_data(file_path)
            results[file_path] = analyzer.analyze()
        except Exception as e:
            results[file_path] = {'error': str(e)}
    
    return results
'''
    
    def test_can_handle(self, composite_chunker):
        """Test that composite chunker can handle supported languages."""
        assert composite_chunker.can_handle("test.py", "python")
        assert composite_chunker.can_handle("test.js", "javascript")
        # Should handle if any sub-strategy can handle
        assert composite_chunker.can_handle("test.java", "java")
    
    def test_fusion_methods(self, composite_chunker, test_code):
        """Test different fusion methods."""
        parser = get_parser("python")
        tree = parser.parse(test_code.encode())
        
        fusion_methods = ['union', 'intersection', 'consensus', 'weighted']
        results = {}
        
        for method in fusion_methods:
            composite_chunker.configure({'fusion_method': method})
            chunks = composite_chunker.chunk(
                tree.root_node,
                test_code.encode(),
                "test.py",
                "python"
            )
            results[method] = chunks
        
        # Different methods should produce different results
        assert len(results['union']) >= len(results['intersection'])
        assert len(results['consensus']) > 0
        assert len(results['weighted']) > 0
        
        # Union should have chunks from all strategies
        union_strategies = set()
        for chunk in results['union']:
            if hasattr(chunk, 'metadata') and 'strategy' in chunk.metadata:
                union_strategies.add(chunk.metadata['strategy'])
        assert len(union_strategies) >= 2
    
    def test_consensus_filtering(self, composite_chunker, test_code):
        """Test consensus-based filtering."""
        parser = get_parser("python")
        tree = parser.parse(test_code.encode())
        
        # Configure for consensus
        composite_chunker.configure({
            'fusion_method': 'consensus',
            'min_consensus_strategies': 2,
            'consensus_threshold': 0.6
        })
        
        chunks = composite_chunker.chunk(
            tree.root_node,
            test_code.encode(),
            "test.py",
            "python"
        )
        
        # Check that chunks have consensus metadata
        for chunk in chunks:
            if hasattr(chunk, 'candidate'):
                candidate = chunk.candidate
                assert len(candidate.strategies) >= 2
                assert candidate.combined_score >= 0.6
    
    def test_overlap_handling(self, composite_chunker, test_code):
        """Test handling of overlapping chunks."""
        parser = get_parser("python")
        tree = parser.parse(test_code.encode())
        
        # Configure to merge overlaps
        composite_chunker.configure({
            'fusion_method': 'union',
            'merge_overlaps': True,
            'overlap_threshold': 0.7
        })
        
        chunks = composite_chunker.chunk(
            tree.root_node,
            test_code.encode(),
            "test.py",
            "python"
        )
        
        # Check that no chunks significantly overlap
        for i, chunk1 in enumerate(chunks):
            for j, chunk2 in enumerate(chunks[i+1:], i+1):
                overlap_start = max(chunk1.start_line, chunk2.start_line)
                overlap_end = min(chunk1.end_line, chunk2.end_line)
                
                if overlap_start <= overlap_end:
                    overlap_lines = overlap_end - overlap_start + 1
                    chunk1_lines = chunk1.end_line - chunk1.start_line + 1
                    chunk2_lines = chunk2.end_line - chunk2.start_line + 1
                    
                    # Should not have high overlap
                    assert overlap_lines / chunk1_lines < 0.7
                    assert overlap_lines / chunk2_lines < 0.7
    
    def test_strategy_weights(self, composite_chunker, test_code):
        """Test that strategy weights affect results."""
        parser = get_parser("python")
        tree = parser.parse(test_code.encode())
        
        # Equal weights
        composite_chunker.configure({
            'fusion_method': 'weighted',
            'strategy_weights': {
                'semantic': 1.0,
                'hierarchical': 1.0,
                'adaptive': 1.0
            }
        })
        equal_chunks = composite_chunker.chunk(
            tree.root_node,
            test_code.encode(),
            "test.py",
            "python"
        )
        
        # Heavily weight semantic
        composite_chunker.configure({
            'fusion_method': 'weighted',
            'strategy_weights': {
                'semantic': 3.0,
                'hierarchical': 0.5,
                'adaptive': 0.5
            }
        })
        semantic_weighted = composite_chunker.chunk(
            tree.root_node,
            test_code.encode(),
            "test.py",
            "python"
        )
        
        # Results should differ based on weights
        # Can't guarantee exact differences, but metadata should reflect weights
        for chunk in semantic_weighted:
            if hasattr(chunk, 'metadata') and 'weight_score' in chunk.metadata:
                # Chunks from semantic strategy should have higher scores
                if 'semantic' in chunk.metadata.get('strategies', []):
                    assert chunk.metadata['weight_score'] > 0
    
    def test_quality_filtering(self, composite_chunker, test_code):
        """Test chunk quality filtering."""
        parser = get_parser("python")
        tree = parser.parse(test_code.encode())
        
        # Configure with quality filtering
        composite_chunker.configure({
            'apply_filters': True,
            'min_chunk_quality': 0.6
        })
        
        chunks = composite_chunker.chunk(
            tree.root_node,
            test_code.encode(),
            "test.py",
            "python"
        )
        
        # All chunks should have quality metadata
        for chunk in chunks:
            assert hasattr(chunk, 'metadata')
            assert 'quality_score' in chunk.metadata
            assert chunk.metadata['quality_score'] >= 0.6
    
    def test_chunk_candidate(self):
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
            content="def test(): pass"
        )
        
        candidate = ChunkCandidate(
            chunk=chunk,
            scores={'semantic': 0.8, 'complexity': 0.6},
            strategies=['semantic', 'adaptive']
        )
        
        # Test combined score calculation
        assert candidate.combined_score == 0.7
    
    def test_consensus_filter(self):
        """Test ConsensusFilter."""
        filter = ConsensusFilter(min_strategies=2, min_score=0.5)
        
        # Create test chunks
        chunk1 = CodeChunk(
            language="python", file_path="test.py", node_type="function",
            start_line=1, end_line=10, byte_start=0, byte_end=100,
            parent_context="", content=""
        )
        chunk1.candidate = ChunkCandidate(
            chunk=chunk1,
            scores={'combined': 0.8},
            strategies=['semantic', 'adaptive', 'hierarchical']
        )
        
        chunk2 = CodeChunk(
            language="python", file_path="test.py", node_type="function",
            start_line=20, end_line=30, byte_start=200, byte_end=300,
            parent_context="", content=""
        )
        chunk2.candidate = ChunkCandidate(
            chunk=chunk2,
            scores={'combined': 0.3},
            strategies=['semantic']
        )
        
        # Test filtering
        assert filter.should_include(chunk1)  # 3 strategies, high score
        assert not filter.should_include(chunk2)  # 1 strategy, low score
    
    def test_overlap_merger(self):
        """Test OverlapMerger."""
        merger = OverlapMerger(overlap_threshold=0.7)
        
        # Create overlapping chunks
        chunk1 = CodeChunk(
            language="python", file_path="test.py", node_type="function",
            start_line=1, end_line=20, byte_start=0, byte_end=200,
            parent_context="", content="chunk1"
        )
        
        chunk2 = CodeChunk(
            language="python", file_path="test.py", node_type="function",
            start_line=15, end_line=25, byte_start=150, byte_end=250,
            parent_context="", content="chunk2"
        )
        
        chunk3 = CodeChunk(
            language="python", file_path="test.py", node_type="function",
            start_line=30, end_line=40, byte_start=300, byte_end=400,
            parent_context="", content="chunk3"
        )
        
        # Test overlap detection
        assert merger.should_merge(chunk1, chunk2)  # Significant overlap
        assert not merger.should_merge(chunk1, chunk3)  # No overlap
        
        # Test merging
        merged = merger.merge([chunk1, chunk2])
        assert merged.start_line == 1
        assert merged.end_line == 25
    
    def test_strategy_specific_configs(self, composite_chunker, test_code):
        """Test configuring individual strategies through composite."""
        parser = get_parser("python")
        tree = parser.parse(test_code.encode())
        
        # Configure individual strategies
        composite_chunker.configure({
            'strategy_configs': {
                'semantic': {
                    'complexity_threshold': 5.0,
                    'merge_related': False
                },
                'hierarchical': {
                    'granularity': 'fine',
                    'max_depth': 3
                },
                'adaptive': {
                    'base_chunk_size': 20,
                    'adaptive_aggressiveness': 0.9
                }
            }
        })
        
        chunks = composite_chunker.chunk(
            tree.root_node,
            test_code.encode(),
            "test.py",
            "python"
        )
        
        # Should produce chunks (exact behavior depends on strategies)
        assert len(chunks) > 0
    
    def test_empty_file_handling(self, composite_chunker):
        """Test handling of empty files."""
        empty_code = ""
        parser = get_parser("python")
        tree = parser.parse(empty_code.encode())
        
        chunks = composite_chunker.chunk(
            tree.root_node,
            empty_code.encode(),
            "test.py",
            "python"
        )
        
        # Should handle empty input gracefully
        assert len(chunks) == 0
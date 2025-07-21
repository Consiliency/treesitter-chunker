"""Composite chunking strategy that combines multiple strategies."""

from typing import List, Dict, Any, Set, Tuple, Optional
from collections import defaultdict
from dataclasses import dataclass
from tree_sitter import Node

from ..interfaces.base import ChunkingStrategy, ChunkFilter, ChunkMerger
from ..types import CodeChunk
from .semantic import SemanticChunker
from .hierarchical import HierarchicalChunker
from .adaptive import AdaptiveChunker


@dataclass
class ChunkCandidate:
    """A candidate chunk with scores from different strategies."""
    chunk: CodeChunk
    scores: Dict[str, float]
    strategies: List[str]
    
    @property
    def combined_score(self) -> float:
        """Calculate combined score from all strategies."""
        if not self.scores:
            return 0.0
        return sum(self.scores.values()) / len(self.scores)


class ConsensusFilter(ChunkFilter):
    """Filter chunks based on strategy consensus."""
    
    def __init__(self, min_strategies: int = 2, min_score: float = 0.5):
        self.min_strategies = min_strategies
        self.min_score = min_score
    
    def should_include(self, chunk: CodeChunk) -> bool:
        """Include chunk if enough strategies agree."""
        if hasattr(chunk, 'candidate'):
            candidate: ChunkCandidate = chunk.candidate
            return (len(candidate.strategies) >= self.min_strategies and
                   candidate.combined_score >= self.min_score)
        return True
    
    def priority(self) -> int:
        """High priority to filter early."""
        return 10


class OverlapMerger(ChunkMerger):
    """Merge overlapping chunks from different strategies."""
    
    def __init__(self, overlap_threshold: float = 0.7):
        self.overlap_threshold = overlap_threshold
    
    def should_merge(self, chunk1: CodeChunk, chunk2: CodeChunk) -> bool:
        """Check if chunks overlap significantly."""
        # Calculate overlap
        overlap_start = max(chunk1.start_line, chunk2.start_line)
        overlap_end = min(chunk1.end_line, chunk2.end_line)
        
        if overlap_start > overlap_end:
            return False
        
        overlap_lines = overlap_end - overlap_start + 1
        chunk1_lines = chunk1.end_line - chunk1.start_line + 1
        chunk2_lines = chunk2.end_line - chunk2.start_line + 1
        
        # Check if overlap is significant for either chunk
        overlap_ratio1 = overlap_lines / chunk1_lines
        overlap_ratio2 = overlap_lines / chunk2_lines
        
        return (overlap_ratio1 >= self.overlap_threshold or
                overlap_ratio2 >= self.overlap_threshold)
    
    def merge(self, chunks: List[CodeChunk]) -> CodeChunk:
        """Merge overlapping chunks, preferring the larger one."""
        if not chunks:
            return None
        
        # Sort by size (descending)
        chunks.sort(key=lambda c: c.end_line - c.start_line, reverse=True)
        
        # Start with the largest chunk
        merged = chunks[0]
        
        # Extend to cover all chunks
        for chunk in chunks[1:]:
            if chunk.start_line < merged.start_line:
                merged.start_line = chunk.start_line
                merged.byte_start = chunk.byte_start
            if chunk.end_line > merged.end_line:
                merged.end_line = chunk.end_line
                merged.byte_end = chunk.byte_end
            
            # Merge metadata
            if hasattr(chunk, 'metadata') and hasattr(merged, 'metadata'):
                merged.metadata['merged_strategies'] = merged.metadata.get('merged_strategies', [])
                merged.metadata['merged_strategies'].extend(
                    chunk.metadata.get('strategies', [chunk.metadata.get('strategy', 'unknown')])
                )
            
            # Merge dependencies
            merged.dependencies = list(set(merged.dependencies + chunk.dependencies))
            merged.references = list(set(merged.references + chunk.references))
        
        return merged


class CompositeChunker(ChunkingStrategy):
    """Combines multiple chunking strategies for optimal results.
    
    Features:
    - Runs multiple strategies in parallel
    - Combines results using configurable fusion methods
    - Handles overlapping chunks intelligently
    - Provides consensus-based filtering
    - Supports custom weighting for each strategy
    """
    
    def __init__(self):
        self.strategies = {
            'semantic': SemanticChunker(),
            'hierarchical': HierarchicalChunker(),
            'adaptive': AdaptiveChunker(),
        }
        
        self.config = {
            # Strategy weights
            'strategy_weights': {
                'semantic': 1.0,
                'hierarchical': 0.8,
                'adaptive': 0.9,
            },
            
            # Fusion method: 'union', 'intersection', 'consensus', 'weighted'
            'fusion_method': 'consensus',
            
            # Consensus parameters
            'min_consensus_strategies': 2,
            'consensus_threshold': 0.6,
            
            # Overlap handling
            'merge_overlaps': True,
            'overlap_threshold': 0.7,
            
            # Quality filters
            'apply_filters': True,
            'min_chunk_quality': 0.5,
            
            # Strategy-specific configs
            'strategy_configs': {
                'semantic': {},
                'hierarchical': {},
                'adaptive': {},
            },
        }
        
        self.filters = [ConsensusFilter()]
        self.merger = OverlapMerger()
    
    def can_handle(self, file_path: str, language: str) -> bool:
        """Can handle if any strategy can handle."""
        return any(strategy.can_handle(file_path, language) 
                  for strategy in self.strategies.values())
    
    def chunk(self, ast: Node, source: bytes, file_path: str, language: str) -> List[CodeChunk]:
        """Apply multiple strategies and combine results."""
        # Configure individual strategies
        for name, config in self.config['strategy_configs'].items():
            if name in self.strategies and config:
                self.strategies[name].configure(config)
        
        # Run each strategy
        strategy_results = {}
        for name, strategy in self.strategies.items():
            if strategy.can_handle(file_path, language):
                try:
                    chunks = strategy.chunk(ast, source, file_path, language)
                    strategy_results[name] = chunks
                except Exception as e:
                    # Log error but continue with other strategies
                    print(f"Strategy {name} failed: {e}")
                    strategy_results[name] = []
        
        # Combine results based on fusion method
        if self.config['fusion_method'] == 'union':
            combined = self._fusion_union(strategy_results, source)
        elif self.config['fusion_method'] == 'intersection':
            combined = self._fusion_intersection(strategy_results, source)
        elif self.config['fusion_method'] == 'consensus':
            combined = self._fusion_consensus(strategy_results, source)
        elif self.config['fusion_method'] == 'weighted':
            combined = self._fusion_weighted(strategy_results, source)
        else:
            combined = self._fusion_union(strategy_results, source)
        
        # Apply filters
        if self.config['apply_filters']:
            combined = self._apply_filters(combined)
        
        # Handle overlaps
        if self.config['merge_overlaps']:
            combined = self._merge_overlapping_chunks(combined, source)
        
        # Final quality check
        combined = self._ensure_chunk_quality(combined, source)
        
        return combined
    
    def configure(self, config: Dict[str, Any]) -> None:
        """Update configuration settings."""
        self.config.update(config)
        
        # Update filters if consensus parameters changed
        if 'min_consensus_strategies' in config or 'consensus_threshold' in config:
            self.filters = [
                ConsensusFilter(
                    self.config.get('min_consensus_strategies', 2),
                    self.config.get('consensus_threshold', 0.6)
                )
            ]
        
        # Update merger if overlap threshold changed
        if 'overlap_threshold' in config:
            self.merger = OverlapMerger(config['overlap_threshold'])
    
    def _fusion_union(self, strategy_results: Dict[str, List[CodeChunk]], 
                     source: bytes) -> List[CodeChunk]:
        """Union fusion: include all chunks from all strategies."""
        all_chunks = []
        
        for strategy_name, chunks in strategy_results.items():
            for chunk in chunks:
                # Tag chunk with strategy
                chunk.metadata = chunk.metadata or {}
                chunk.metadata['strategy'] = strategy_name
                all_chunks.append(chunk)
        
        return all_chunks
    
    def _fusion_intersection(self, strategy_results: Dict[str, List[CodeChunk]], 
                            source: bytes) -> List[CodeChunk]:
        """Intersection fusion: only chunks that appear in multiple strategies."""
        if not strategy_results:
            return []
        
        # Group chunks by position
        position_map = defaultdict(list)
        
        for strategy_name, chunks in strategy_results.items():
            for chunk in chunks:
                # Use position as key
                key = (chunk.start_line, chunk.end_line)
                position_map[key].append((strategy_name, chunk))
        
        # Keep only chunks that appear in multiple strategies
        intersection_chunks = []
        min_strategies = max(2, len(strategy_results) // 2)
        
        for position, strategy_chunks in position_map.items():
            if len(strategy_chunks) >= min_strategies:
                # Use the chunk from the highest-weighted strategy
                best_chunk = self._select_best_chunk(strategy_chunks)
                
                # Add metadata about agreement
                best_chunk.metadata = best_chunk.metadata or {}
                best_chunk.metadata['strategies'] = [s for s, _ in strategy_chunks]
                best_chunk.metadata['agreement_score'] = len(strategy_chunks) / len(strategy_results)
                
                intersection_chunks.append(best_chunk)
        
        return intersection_chunks
    
    def _fusion_consensus(self, strategy_results: Dict[str, List[CodeChunk]], 
                         source: bytes) -> List[CodeChunk]:
        """Consensus fusion: smart combination based on agreement."""
        candidates = self._build_chunk_candidates(strategy_results)
        
        # Score each candidate
        scored_candidates = []
        for candidate in candidates:
            # Calculate consensus score
            num_strategies = len(candidate.strategies)
            total_strategies = len(strategy_results)
            consensus_score = num_strategies / total_strategies
            
            # Calculate quality score
            quality_scores = []
            for strategy in candidate.strategies:
                weight = self.config['strategy_weights'].get(strategy, 1.0)
                quality_scores.append(weight)
            
            quality_score = sum(quality_scores) / len(quality_scores) if quality_scores else 0
            
            # Combined score
            candidate.scores['consensus'] = consensus_score
            candidate.scores['quality'] = quality_score
            candidate.scores['combined'] = (consensus_score + quality_score) / 2
            
            # Add candidate info to chunk
            candidate.chunk.candidate = candidate
            
            scored_candidates.append(candidate)
        
        # Filter based on consensus threshold
        threshold = self.config['consensus_threshold']
        consensus_chunks = [
            c.chunk for c in scored_candidates
            if c.scores['combined'] >= threshold
        ]
        
        return consensus_chunks
    
    def _fusion_weighted(self, strategy_results: Dict[str, List[CodeChunk]], 
                        source: bytes) -> List[CodeChunk]:
        """Weighted fusion: combine based on strategy weights."""
        weighted_chunks = []
        
        # Build candidates with weights
        candidates = self._build_chunk_candidates(strategy_results)
        
        for candidate in candidates:
            # Calculate weighted score
            total_weight = 0
            for strategy in candidate.strategies:
                weight = self.config['strategy_weights'].get(strategy, 1.0)
                total_weight += weight
            
            # Normalize by number of strategies that produced this chunk
            candidate.scores['weighted'] = total_weight / len(candidate.strategies)
            
            # Add to chunk metadata
            chunk = candidate.chunk
            chunk.metadata = chunk.metadata or {}
            chunk.metadata['weight_score'] = candidate.scores['weighted']
            chunk.metadata['strategies'] = candidate.strategies
            
            weighted_chunks.append(chunk)
        
        # Sort by weight score
        weighted_chunks.sort(
            key=lambda c: c.metadata.get('weight_score', 0),
            reverse=True
        )
        
        return weighted_chunks
    
    def _build_chunk_candidates(self, strategy_results: Dict[str, List[CodeChunk]]) -> List[ChunkCandidate]:
        """Build chunk candidates from strategy results."""
        # Group similar chunks
        candidates_map = {}
        
        for strategy_name, chunks in strategy_results.items():
            for chunk in chunks:
                # Create a key based on chunk position
                key = self._get_chunk_key(chunk)
                
                if key not in candidates_map:
                    candidates_map[key] = ChunkCandidate(
                        chunk=chunk,
                        scores={},
                        strategies=[]
                    )
                
                candidate = candidates_map[key]
                candidate.strategies.append(strategy_name)
                
                # Update chunk if this one is better
                if self._is_better_chunk(chunk, candidate.chunk):
                    candidate.chunk = chunk
        
        return list(candidates_map.values())
    
    def _get_chunk_key(self, chunk: CodeChunk) -> Tuple[int, int, str]:
        """Get a key for chunk comparison."""
        # Use approximate position (within 5 lines) and type
        start_bucket = chunk.start_line // 5 * 5
        end_bucket = chunk.end_line // 5 * 5
        return (start_bucket, end_bucket, chunk.node_type)
    
    def _is_better_chunk(self, chunk1: CodeChunk, chunk2: CodeChunk) -> bool:
        """Determine if chunk1 is better than chunk2."""
        # Prefer chunks with more metadata
        metadata1 = len(chunk1.metadata) if hasattr(chunk1, 'metadata') and chunk1.metadata else 0
        metadata2 = len(chunk2.metadata) if hasattr(chunk2, 'metadata') and chunk2.metadata else 0
        
        if metadata1 != metadata2:
            return metadata1 > metadata2
        
        # Prefer chunks with more precise boundaries
        return abs(chunk1.end_line - chunk1.start_line) < abs(chunk2.end_line - chunk2.start_line)
    
    def _select_best_chunk(self, strategy_chunks: List[Tuple[str, CodeChunk]]) -> CodeChunk:
        """Select the best chunk from multiple strategies."""
        # Sort by strategy weight
        weighted = []
        for strategy_name, chunk in strategy_chunks:
            weight = self.config['strategy_weights'].get(strategy_name, 1.0)
            weighted.append((weight, chunk))
        
        weighted.sort(reverse=True, key=lambda x: x[0])
        return weighted[0][1]
    
    def _apply_filters(self, chunks: List[CodeChunk]) -> List[CodeChunk]:
        """Apply configured filters to chunks."""
        filtered = chunks
        
        # Sort filters by priority
        sorted_filters = sorted(self.filters, key=lambda f: f.priority())
        
        for filter_obj in sorted_filters:
            filtered = [c for c in filtered if filter_obj.should_include(c)]
        
        return filtered
    
    def _merge_overlapping_chunks(self, chunks: List[CodeChunk], source: bytes) -> List[CodeChunk]:
        """Merge chunks that overlap significantly."""
        if not chunks:
            return chunks
        
        # Sort chunks by start position
        chunks.sort(key=lambda c: (c.start_line, c.end_line))
        
        merged = []
        merge_groups = []
        current_group = [chunks[0]]
        
        for i in range(1, len(chunks)):
            chunk = chunks[i]
            
            # Check if this chunk overlaps with any in current group
            overlaps = False
            for group_chunk in current_group:
                if self.merger.should_merge(group_chunk, chunk):
                    overlaps = True
                    break
            
            if overlaps:
                current_group.append(chunk)
            else:
                # Start new group
                merge_groups.append(current_group)
                current_group = [chunk]
        
        # Don't forget the last group
        if current_group:
            merge_groups.append(current_group)
        
        # Merge each group
        for group in merge_groups:
            if len(group) > 1:
                merged_chunk = self.merger.merge(group)
                merged.append(merged_chunk)
            else:
                merged.append(group[0])
        
        return merged
    
    def _ensure_chunk_quality(self, chunks: List[CodeChunk], source: bytes) -> List[CodeChunk]:
        """Final pass to ensure chunk quality."""
        quality_chunks = []
        
        for chunk in chunks:
            # Skip empty chunks
            if not chunk.content.strip():
                continue
            
            # Calculate quality score
            quality_score = self._calculate_chunk_quality(chunk)
            
            # Add quality metadata
            chunk.metadata = chunk.metadata or {}
            chunk.metadata['quality_score'] = quality_score
            
            # Include if meets minimum quality
            if quality_score >= self.config['min_chunk_quality']:
                quality_chunks.append(chunk)
        
        return quality_chunks
    
    def _calculate_chunk_quality(self, chunk: CodeChunk) -> float:
        """Calculate quality score for a chunk."""
        scores = []
        
        # Size score (prefer medium-sized chunks)
        lines = chunk.end_line - chunk.start_line + 1
        if lines < 5:
            size_score = 0.5
        elif lines > 200:
            size_score = 0.7
        else:
            size_score = 1.0
        scores.append(size_score)
        
        # Content score (non-empty, meaningful)
        content_lines = [l for l in chunk.content.split('\n') if l.strip()]
        if content_lines:
            content_score = min(1.0, len(content_lines) / lines) if lines > 0 else 0
        else:
            content_score = 0
        scores.append(content_score)
        
        # Metadata score (more metadata = better understanding)
        if hasattr(chunk, 'metadata') and chunk.metadata:
            metadata_score = min(1.0, len(chunk.metadata) / 5)
        else:
            metadata_score = 0.5
        scores.append(metadata_score)
        
        # Strategy agreement score
        if hasattr(chunk, 'metadata') and 'strategies' in chunk.metadata:
            agreement_score = len(chunk.metadata['strategies']) / len(self.strategies)
        else:
            agreement_score = 0.5
        scores.append(agreement_score)
        
        return sum(scores) / len(scores) if scores else 0
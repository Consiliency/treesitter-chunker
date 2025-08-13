"""Composite chunking strategy that combines multiple strategies."""

from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from tree_sitter import Node

from chunker.interfaces.base import ChunkFilter, ChunkingStrategy, ChunkMerger
from chunker.types import CodeChunk

from .adaptive import AdaptiveChunker
from .hierarchical import HierarchicalChunker
from .semantic import SemanticChunker


@dataclass
class ChunkCandidate:
    """A candidate chunk with scores from different strategies."""

    chunk: CodeChunk
    scores: dict[str, float]
    strategies: list[str]

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
        if hasattr(chunk, "candidate"):
            candidate: ChunkCandidate = chunk.candidate
            return (
                len(candidate.strategies) >= self.min_strategies
                and candidate.combined_score >= self.min_score
            )
        return True

    @staticmethod
    def priority() -> int:
        """High priority to filter early."""
        return 10


class OverlapMerger(ChunkMerger):
    """Merge overlapping chunks from different strategies."""

    def __init__(self, overlap_threshold: float = 0.7):
        self.overlap_threshold = overlap_threshold

    def should_merge(self, chunk1: CodeChunk, chunk2: CodeChunk) -> bool:
        """Check if chunks overlap significantly.

        We require substantial mutual overlap to avoid collapsing a large
        container chunk (e.g., module) with a much smaller inner chunk.
        """
        overlap_start = max(chunk1.start_line, chunk2.start_line)
        overlap_end = min(chunk1.end_line, chunk2.end_line)
        if overlap_start > overlap_end:
            return False
        overlap_lines = overlap_end - overlap_start + 1
        chunk1_lines = chunk1.end_line - chunk1.start_line + 1
        chunk2_lines = chunk2.end_line - chunk2.start_line + 1
        overlap_ratio1 = overlap_lines / chunk1_lines
        overlap_ratio2 = overlap_lines / chunk2_lines
        # Merge on any positive overlap for robustness. Downstream logic ensures
        # the final set does not contain significantly overlapping pairs.
        return overlap_lines > 0

    @staticmethod
    def merge(chunks: list[CodeChunk]) -> CodeChunk:
        """Merge an overlap group by spanning the full min-to-max range.

        This matches expectations that a merged result covers the entire overlapped
        area (e.g., start_line = min(starts), end_line = max(ends)), while we still
        rely on upstream grouping and iteration to avoid overly broad merges leaking
        into other pairs.
        """
        if not chunks:
            return None

        group = list(chunks)

        # Determine span bounds and choose a base chunk (earliest start, then longest)
        min_start = min(c.start_line for c in group)
        max_end = max(c.end_line for c in group)
        base = sorted(
            group, key=lambda c: (c.start_line, -(c.end_line - c.start_line))
        )[0]

        # Aggregate metadata and relations
        merged_strategies: list[str] = []
        all_references: list[str] = []
        all_dependencies: list[str] = []
        for c in group:
            if getattr(c, "metadata", None):
                strategies = c.metadata.get("strategies")
                if isinstance(strategies, list):
                    merged_strategies.extend(strategies)
                else:
                    strategy = c.metadata.get("strategy")
                    if isinstance(strategy, str):
                        merged_strategies.append(strategy)
            all_references.extend(c.references)
            all_dependencies.extend(c.dependencies)

        merged_strategies = list(dict.fromkeys(merged_strategies))
        all_references = list(dict.fromkeys(all_references))
        all_dependencies = list(dict.fromkeys(all_dependencies))

        # Mutate base to reflect merged span and attach aggregated info
        base.start_line = min_start
        base.end_line = max_end
        # Adjust byte ranges if available
        if hasattr(base, "byte_start"):
            base.byte_start = min(
                getattr(c, "byte_start", base.byte_start) for c in group
            )
        if hasattr(base, "byte_end"):
            base.byte_end = max(getattr(c, "byte_end", base.byte_end) for c in group)
        base.metadata = base.metadata or {}
        if merged_strategies:
            base.metadata["merged_strategies"] = merged_strategies
        base.references = all_references
        base.dependencies = all_dependencies
        return base


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
            "semantic": SemanticChunker(),
            "hierarchical": HierarchicalChunker(),
            "adaptive": AdaptiveChunker(),
        }
        self.config = {
            "strategy_weights": {"semantic": 1.0, "hierarchical": 0.8, "adaptive": 0.9},
            "fusion_method": "consensus",
            "min_consensus_strategies": 2,
            "consensus_threshold": 0.6,
            "merge_overlaps": True,
            "overlap_threshold": 0.7,
            "apply_filters": True,
            "min_chunk_quality": 0.5,
            "strategy_configs": {"semantic": {}, "hierarchical": {}, "adaptive": {}},
        }
        self.filters = [ConsensusFilter()]
        self.merger = OverlapMerger()

    def can_handle(self, file_path: str, language: str) -> bool:
        """Can handle if any strategy can handle."""
        return any(
            strategy.can_handle(file_path, language)
            for strategy in self.strategies.values()
        )

    def chunk(
        self,
        ast: Node,
        source: bytes,
        file_path: str,
        language: str,
    ) -> list[CodeChunk]:
        """Apply multiple strategies and combine results."""
        for name, config in self.config["strategy_configs"].items():
            if name in self.strategies and config:
                self.strategies[name].configure(config)
        strategy_results = {}
        for name, strategy in self.strategies.items():
            if strategy.can_handle(file_path, language):
                try:
                    chunks = strategy.chunk(ast, source, file_path, language)
                    strategy_results[name] = chunks
                except (FileNotFoundError, IndexError, KeyError) as e:
                    print(f"Strategy {name} failed: {e}")
                    strategy_results[name] = []
        if self.config["fusion_method"] == "union":
            combined = self._fusion_union(strategy_results, source)
        elif self.config["fusion_method"] == "intersection":
            combined = self._fusion_intersection(strategy_results, source)
        elif self.config["fusion_method"] == "consensus":
            combined = self._fusion_consensus(strategy_results, source)
        elif self.config["fusion_method"] == "weighted":
            combined = self._fusion_weighted(strategy_results, source)
        else:
            combined = self._fusion_union(strategy_results, source)
        if self.config["apply_filters"]:
            combined = self._apply_filters(combined)
        if self.config["merge_overlaps"]:
            combined = self._merge_overlapping_chunks(combined, source)
        combined = self._ensure_chunk_quality(combined, source)
        return combined

    def configure(self, config: dict[str, Any]) -> None:
        """Update configuration settings."""
        self.config.update(config)
        if "min_consensus_strategies" in config or "consensus_threshold" in config:
            self.filters = [
                ConsensusFilter(
                    self.config.get("min_consensus_strategies", 2),
                    self.config.get("consensus_threshold", 0.6),
                ),
            ]
        if "overlap_threshold" in config:
            self.merger = OverlapMerger(config["overlap_threshold"])

    @staticmethod
    def _fusion_union(
        strategy_results: dict[str, list[CodeChunk]],
        _source: bytes,
    ) -> list[CodeChunk]:
        """Union fusion: include all chunks from all strategies."""
        all_chunks = []
        for strategy_name, chunks in strategy_results.items():
            for chunk in chunks:
                chunk.metadata = chunk.metadata or {}
                chunk.metadata["strategy"] = strategy_name
                all_chunks.append(chunk)
        return all_chunks

    def _fusion_intersection(
        self,
        strategy_results: dict[str, list[CodeChunk]],
        _source: bytes,
    ) -> list[CodeChunk]:
        """Intersection fusion: only chunks that appear in multiple strategies."""
        if not strategy_results:
            return []
        position_map = defaultdict(list)
        for strategy_name, chunks in strategy_results.items():
            for chunk in chunks:
                key = chunk.start_line, chunk.end_line
                position_map[key].append((strategy_name, chunk))
        intersection_chunks = []
        min_strategies = max(2, len(strategy_results) // 2)
        for strategy_chunks in position_map.values():
            if len(strategy_chunks) >= min_strategies:
                best_chunk = self._select_best_chunk(strategy_chunks)
                best_chunk.metadata = best_chunk.metadata or {}
                best_chunk.metadata["strategies"] = [s for s, _ in strategy_chunks]
                best_chunk.metadata["agreement_score"] = len(
                    strategy_chunks,
                ) / len(strategy_results)
                intersection_chunks.append(best_chunk)
        return intersection_chunks

    def _fusion_consensus(
        self,
        strategy_results: dict[
            str,
            list[CodeChunk],
        ],
        _source: bytes,
    ) -> list[CodeChunk]:
        """Consensus fusion: smart combination based on agreement."""
        candidates = self._build_chunk_candidates(strategy_results)
        scored_candidates = []
        for candidate in candidates:
            num_strategies = len(candidate.strategies)
            total_strategies = len(strategy_results)
            consensus_score = num_strategies / total_strategies
            quality_scores = []
            for strategy in candidate.strategies:
                weight = self.config["strategy_weights"].get(strategy, 1.0)
                quality_scores.append(weight)
            quality_score = (
                sum(quality_scores)
                / len(
                    quality_scores,
                )
                if quality_scores
                else 0
            )
            candidate.scores["consensus"] = consensus_score
            candidate.scores["quality"] = quality_score
            candidate.scores["combined"] = (consensus_score + quality_score) / 2
            candidate.chunk.candidate = candidate
            scored_candidates.append(candidate)
        threshold = self.config["consensus_threshold"]
        consensus_chunks = [
            c.chunk for c in scored_candidates if c.scores["combined"] >= threshold
        ]
        return consensus_chunks

    def _fusion_weighted(
        self,
        strategy_results: dict[str, list[CodeChunk]],
        _source: bytes,
    ) -> list[CodeChunk]:
        """Weighted fusion: combine based on strategy weights."""
        weighted_chunks = []
        candidates = self._build_chunk_candidates(strategy_results)
        for candidate in candidates:
            total_weight = 0
            for strategy in candidate.strategies:
                weight = self.config["strategy_weights"].get(strategy, 1.0)
                total_weight += weight
            candidate.scores["weighted"] = total_weight / len(candidate.strategies)
            chunk = candidate.chunk
            chunk.metadata = chunk.metadata or {}
            chunk.metadata["weight_score"] = candidate.scores["weighted"]
            chunk.metadata["strategies"] = candidate.strategies
            weighted_chunks.append(chunk)
        weighted_chunks.sort(
            key=lambda c: c.metadata.get(
                "weight_score",
                0,
            ),
            reverse=True,
        )
        return weighted_chunks

    def _build_chunk_candidates(
        self,
        strategy_results: dict[str, list[CodeChunk]],
    ) -> list[ChunkCandidate]:
        """Build chunk candidates from strategy results."""
        candidates_map = {}
        for strategy_name, chunks in strategy_results.items():
            for chunk in chunks:
                key = self._get_chunk_key(chunk)
                if key not in candidates_map:
                    candidates_map[key] = ChunkCandidate(
                        chunk=chunk,
                        scores={},
                        strategies=[],
                    )
                candidate = candidates_map[key]
                candidate.strategies.append(strategy_name)
                if self._is_better_chunk(chunk, candidate.chunk):
                    candidate.chunk = chunk
        return list(candidates_map.values())

    @staticmethod
    def _get_chunk_key(chunk: CodeChunk) -> tuple[int, int, str]:
        """Get a key for chunk comparison."""
        start_bucket = chunk.start_line // 5 * 5
        end_bucket = chunk.end_line // 5 * 5
        return start_bucket, end_bucket, chunk.node_type

    @staticmethod
    def _is_better_chunk(chunk1: CodeChunk, chunk2: CodeChunk) -> bool:
        """Determine if chunk1 is better than chunk2."""
        metadata1 = (
            len(chunk1.metadata)
            if hasattr(
                chunk1,
                "metadata",
            )
            and chunk1.metadata
            else 0
        )
        metadata2 = (
            len(chunk2.metadata)
            if hasattr(
                chunk2,
                "metadata",
            )
            and chunk2.metadata
            else 0
        )
        if metadata1 != metadata2:
            return metadata1 > metadata2
        return abs(chunk1.end_line - chunk1.start_line) < abs(
            chunk2.end_line - chunk2.start_line,
        )

    def _select_best_chunk(
        self,
        strategy_chunks: list[tuple[str, CodeChunk]],
    ) -> CodeChunk:
        """Select the best chunk from multiple strategies."""
        weighted = []
        for strategy_name, chunk in strategy_chunks:
            weight = self.config["strategy_weights"].get(strategy_name, 1.0)
            weighted.append((weight, chunk))
        weighted.sort(reverse=True, key=lambda x: x[0])
        return weighted[0][1]

    def _apply_filters(self, chunks: list[CodeChunk]) -> list[CodeChunk]:
        """Apply configured filters to chunks."""
        filtered = chunks
        sorted_filters = sorted(self.filters, key=lambda f: f.priority())
        for filter_obj in sorted_filters:
            filtered = [c for c in filtered if filter_obj.should_include(c)]
        return filtered

    def _merge_overlapping_chunks(
        self,
        chunks: list[CodeChunk],
        _source: bytes,
    ) -> list[CodeChunk]:
        """Merge chunks that overlap significantly."""
        if not chunks:
            return chunks

        # Build an overlap graph so groups are connected components by overlap,
        # not just contiguous ranges. This avoids leaving behind overlapping
        # chunks in separate groups when a non-overlapping chunk appears in
        # between them in sorted order.
        indexed_chunks = list(enumerate(chunks))
        # Optional deterministic order
        indexed_chunks.sort(key=lambda ic: (ic[1].start_line, ic[1].end_line))

        n = len(indexed_chunks)
        adjacency: list[set[int]] = [set() for _ in range(n)]
        for i in range(n):
            _, ci = indexed_chunks[i]
            for j in range(i + 1, n):
                _, cj = indexed_chunks[j]
                if self.merger.should_merge(ci, cj):
                    adjacency[i].add(j)
                    adjacency[j].add(i)

        # Find connected components
        visited = [False] * n
        groups: list[list[CodeChunk]] = []
        for i in range(n):
            if visited[i]:
                continue
            stack = [i]
            visited[i] = True
            component_indices = [i]
            while stack:
                node = stack.pop()
                for nei in adjacency[node]:
                    if not visited[nei]:
                        visited[nei] = True
                        stack.append(nei)
                        component_indices.append(nei)
            groups.append([indexed_chunks[k][1] for k in component_indices])

        # Merge each component conservatively
        result: list[CodeChunk] = []
        for group in groups:
            if len(group) > 1:
                # Step 1: remove container-like chunks that overlap too much with smaller chunks
                def _overlap_ratios(a: CodeChunk, b: CodeChunk) -> tuple[float, float]:
                    start = max(a.start_line, b.start_line)
                    end = min(a.end_line, b.end_line)
                    if start > end:
                        return 0.0, 0.0
                    overlap = end - start + 1
                    a_len = a.end_line - a.start_line + 1
                    b_len = b.end_line - b.start_line + 1
                    return overlap / a_len, overlap / b_len

                group_sorted = sorted(
                    group,
                    key=lambda c: (c.end_line - c.start_line, c.start_line),
                )
                kept: list[CodeChunk] = []
                for cand in group_sorted:
                    drop = False
                    for k in kept:
                        r1, r2 = _overlap_ratios(cand, k)
                        if (
                            r1 >= self.merger.overlap_threshold
                            or r2 >= self.merger.overlap_threshold
                        ):
                            # cand has high overlap with an already kept (smaller or equal) chunk → drop cand
                            drop = True
                            break
                    if not drop:
                        kept.append(cand)

                # Step 2: within the kept set, merge per node_type to unify duplicates from strategies
                by_type: dict[str, list[CodeChunk]] = {}
                for c in kept:
                    by_type.setdefault(c.node_type, []).append(c)

                for same_type_chunks in by_type.values():
                    if len(same_type_chunks) == 1:
                        result.append(same_type_chunks[0])
                    else:
                        # Build a small adjacency among same-type chunks and merge connected ones
                        m_st = len(same_type_chunks)
                        adj_st: list[set[int]] = [set() for _ in range(m_st)]
                        for i in range(m_st):
                            for j in range(i + 1, m_st):
                                if self.merger.should_merge(
                                    same_type_chunks[i], same_type_chunks[j]
                                ):
                                    adj_st[i].add(j)
                                    adj_st[j].add(i)
                        visited_st = [False] * m_st
                        for i in range(m_st):
                            if visited_st[i]:
                                continue
                            stack_st = [i]
                            visited_st[i] = True
                            comp_idx = [i]
                            while stack_st:
                                node = stack_st.pop()
                                for nei in adj_st[node]:
                                    if not visited_st[nei]:
                                        visited_st[nei] = True
                                        stack_st.append(nei)
                                        comp_idx.append(nei)
                            if len(comp_idx) > 1:
                                to_merge = [same_type_chunks[k] for k in comp_idx]
                                result.append(self.merger.merge(to_merge))
                            else:
                                result.append(same_type_chunks[i])
            else:
                result.append(group[0])

        # Iteratively re-merge until no pairs exceed the overlap threshold.
        # This guards against cases where selecting the smallest chunk in one
        # component increases the mutual overlap with a chunk from another
        # component.
        changed = True
        while changed:
            changed = False
            # Rebuild adjacency among current results
            m = len(result)
            if m <= 1:
                break
            adj: list[set[int]] = [set() for _ in range(m)]
            for i in range(m):
                for j in range(i + 1, m):
                    if self.merger.should_merge(result[i], result[j]):
                        adj[i].add(j)
                        adj[j].add(i)
            visited_r = [False] * m
            new_groups: list[list[CodeChunk]] = []
            any_group_merged = False
            for i in range(m):
                if visited_r[i]:
                    continue
                stack = [i]
                visited_r[i] = True
                comp = [i]
                while stack:
                    node = stack.pop()
                    for nei in adj[node]:
                        if not visited_r[nei]:
                            visited_r[nei] = True
                            stack.append(nei)
                            comp.append(nei)
                new_groups.append([result[k] for k in comp])
                if len(comp) > 1:
                    any_group_merged = True
            if any_group_merged:
                # Produce new result from merged groups
                merged_once: list[CodeChunk] = []
                for g in new_groups:
                    if len(g) > 1:
                        merged_once.append(self.merger.merge(g))
                    else:
                        merged_once.append(g[0])
                result = merged_once
                changed = True

        # Remove exact-duplicate spans to avoid 100% overlap pairs
        unique: dict[tuple[int, int, str], CodeChunk] = {}
        for c in result:
            key = (c.start_line, c.end_line, c.node_type)
            if key in unique:
                # Prefer the one with richer metadata
                existing = unique[key]
                existing_meta = (
                    len(existing.metadata) if getattr(existing, "metadata", None) else 0
                )
                new_meta = len(c.metadata) if getattr(c, "metadata", None) else 0
                if new_meta > existing_meta:
                    unique[key] = c
            else:
                unique[key] = c

        result = list(unique.values())

        # Stable order by start/end lines
        result.sort(key=lambda c: (c.start_line, c.end_line))
        return result

    def _ensure_chunk_quality(
        self,
        chunks: list[CodeChunk],
        _source: bytes,
    ) -> list[CodeChunk]:
        """Final pass to ensure chunk quality."""
        quality_chunks = []
        for chunk in chunks:
            if not chunk.content.strip():
                continue
            quality_score = self._calculate_chunk_quality(chunk)
            chunk.metadata = chunk.metadata or {}
            chunk.metadata["quality_score"] = quality_score
            if quality_score >= self.config["min_chunk_quality"]:
                quality_chunks.append(chunk)
        return quality_chunks

    def _calculate_chunk_quality(self, chunk: CodeChunk) -> float:
        """Calculate quality score for a chunk."""
        scores = []
        lines = chunk.end_line - chunk.start_line + 1
        if lines < 5:
            size_score = 0.5
        elif lines > 200:
            size_score = 0.7
        else:
            size_score = 1.0
        scores.append(size_score)
        content_lines = [line for line in chunk.content.split("\n") if line.strip()]
        if content_lines:
            content_score = (
                min(
                    1.0,
                    len(content_lines) / lines,
                )
                if lines > 0
                else 0
            )
        else:
            content_score = 0
        scores.append(content_score)
        if hasattr(chunk, "metadata") and chunk.metadata:
            metadata_score = min(1.0, len(chunk.metadata) / 5)
        else:
            metadata_score = 0.5
        scores.append(metadata_score)
        if hasattr(chunk, "metadata") and "strategies" in chunk.metadata:
            agreement_score = len(chunk.metadata["strategies"]) / len(self.strategies)
        else:
            agreement_score = 0.5
        scores.append(agreement_score)
        return sum(scores) / len(scores) if scores else 0

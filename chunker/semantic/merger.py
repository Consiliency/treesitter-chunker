"""Semantic merger for intelligent chunk merging."""

from collections import defaultdict
from dataclasses import dataclass

from chunker.interfaces.semantic import SemanticMerger
from chunker.types import CodeChunk

from .analyzer import TreeSitterRelationshipAnalyzer


@dataclass
class MergeConfig:
    """Configuration for semantic merging."""

    merge_getters_setters: bool = True
    merge_overloaded_functions: bool = True
    merge_small_methods: bool = True
    merge_interface_implementations: bool = False
    small_method_threshold: int = 10
    max_merged_size: int = 100
    cohesion_threshold: float = 0.6
    language_configs: dict[str, dict] = None

    def __post_init__(self):
        if self.language_configs is None:
            self.language_configs = {
                "python": {"merge_decorators": True, "merge_property_methods": True},
                "java": {"merge_constructors": False, "merge_overrides": True},
                "javascript": {
                    "merge_getters_setters": True,
                    "merge_event_handlers": True,
                },
            }


class TreeSitterSemanticMerger(SemanticMerger):
    """Merge related chunks based on Tree-sitter AST analysis."""

    def __init__(self, config: MergeConfig | None = None):
        """Initialize with configuration."""
        self.config = config or MergeConfig()
        self.analyzer = TreeSitterRelationshipAnalyzer()
        self._merge_cache = {}

    def should_merge(self, chunk1: CodeChunk, chunk2: CodeChunk) -> bool:
        """Determine if two chunks should be merged."""
        # Check basic preconditions
        if not self._basic_merge_checks(chunk1, chunk2):
            return False

        # Check cohesion score
        cohesion = self.analyzer.calculate_cohesion_score(chunk1, chunk2)
        if cohesion < self.config.cohesion_threshold:
            return False

        # Check merge conditions based on configuration
        merge_conditions = [
            (self.config.merge_getters_setters, self._is_getter_setter_pair),
            (self.config.merge_overloaded_functions, self._are_overloaded_functions),
            (self.config.merge_small_methods, self._are_small_related_methods),
        ]

        for config_enabled, check_func in merge_conditions:
            if config_enabled and check_func(chunk1, chunk2):
                return True

        # Check language-specific merge conditions
        return self._check_language_specific_merge(chunk1, chunk2)

    def _basic_merge_checks(self, chunk1: CodeChunk, chunk2: CodeChunk) -> bool:
        """Perform basic merge eligibility checks."""
        if chunk1.file_path != chunk2.file_path:
            return False
        if chunk1.language != chunk2.language:
            return False

        total_lines = (
            chunk1.end_line
            - chunk1.start_line
            + 1
            + (chunk2.end_line - chunk2.start_line + 1)
        )
        return total_lines <= self.config.max_merged_size

    def _check_language_specific_merge(
        self,
        chunk1: CodeChunk,
        chunk2: CodeChunk,
    ) -> bool:
        """Check language-specific merge conditions."""
        lang_config = self.config.language_configs.get(chunk1.language, {})

        if (
            chunk1.language == "python"
            and lang_config.get("merge_property_methods")
            and self._are_property_methods(chunk1, chunk2)
        ):
            return True

        if (
            chunk1.language == "javascript"
            and lang_config.get("merge_event_handlers")
            and self._are_event_handlers(chunk1, chunk2)
        ):
            return True

        return False

    def merge_chunks(self, chunks: list[CodeChunk]) -> list[CodeChunk]:
        """Merge related chunks to reduce fragmentation."""
        if not chunks:
            return []
        merge_groups = self._build_merge_groups(chunks)
        result = []
        processed = set()
        for chunk in chunks:
            if chunk.chunk_id in processed:
                continue
            group = merge_groups.get(chunk.chunk_id)
            if group and len(group) > 1:
                merged = self._merge_chunk_group(group)
                result.append(merged)
                processed.update(c.chunk_id for c in group)
            else:
                result.append(chunk)
                processed.add(chunk.chunk_id)
        return result

    def get_merge_reason(self, chunk1: CodeChunk, chunk2: CodeChunk) -> str | None:
        """Get the reason why two chunks would be merged."""
        if not self.should_merge(chunk1, chunk2):
            return None
        reasons = []
        if self._is_getter_setter_pair(chunk1, chunk2):
            reasons.append("getter/setter pair")
        if self._are_overloaded_functions(chunk1, chunk2):
            reasons.append("overloaded functions")
        if self._are_small_related_methods(chunk1, chunk2):
            reasons.append("small related methods")
        if self._are_property_methods(chunk1, chunk2):
            reasons.append("property methods")
        if self._are_event_handlers(chunk1, chunk2):
            reasons.append("event handlers")
        cohesion = self.analyzer.calculate_cohesion_score(chunk1, chunk2)
        reasons.append(f"cohesion score: {cohesion:.2f}")
        return "; ".join(reasons)

    def _build_merge_groups(
        self,
        chunks: list[CodeChunk],
    ) -> dict[str, list[CodeChunk]]:
        """Build groups of chunks that should be merged together."""
        parent = {chunk.chunk_id: chunk.chunk_id for chunk in chunks}
        {chunk.chunk_id: chunk for chunk in chunks}

        def find(x):
            if parent[x] != x:
                parent[x] = find(parent[x])
            return parent[x]

        def union(x, y):
            px, py = find(x), find(y)
            if px != py:
                parent[px] = py

        for i, chunk1 in enumerate(chunks):
            for chunk2 in chunks[i + 1 :]:
                if self.should_merge(chunk1, chunk2):
                    union(chunk1.chunk_id, chunk2.chunk_id)
        groups = defaultdict(list)
        for chunk in chunks:
            root = find(chunk.chunk_id)
            groups[root].append(chunk)
        result = {}
        for group in groups.values():
            group.sort(key=lambda c: c.start_line)
            for chunk in group:
                result[chunk.chunk_id] = group
        return result

    @classmethod
    def _merge_chunk_group(cls, chunks: list[CodeChunk]) -> CodeChunk:
        """Merge a group of chunks into a single chunk."""
        chunks = sorted(chunks, key=lambda c: c.start_line)
        min_start_line = min(c.start_line for c in chunks)
        max_end_line = max(c.end_line for c in chunks)
        min_byte_start = min(c.byte_start for c in chunks)
        max_byte_end = max(c.byte_end for c in chunks)
        merged_content_lines = []
        for i, chunk in enumerate(chunks):
            merged_content_lines.append(chunk.content)
            if i < len(chunks) - 1:
                merged_content_lines.append("")
        merged_content = "\n".join(merged_content_lines)
        node_types = {c.node_type for c in chunks}
        if len(node_types) == 1:
            merged_node_type = chunks[0].node_type
        else:
            merged_node_type = "merged_chunk"
        all_refs = set()
        all_deps = set()
        for chunk in chunks:
            all_refs.update(chunk.references)
            all_deps.update(chunk.dependencies)
        merged = CodeChunk(
            language=chunks[0].language,
            file_path=chunks[0].file_path,
            node_type=merged_node_type,
            start_line=min_start_line,
            end_line=max_end_line,
            byte_start=min_byte_start,
            byte_end=max_byte_end,
            parent_context=chunks[0].parent_context,
            content=merged_content,
            references=list(all_refs),
            dependencies=list(all_deps),
        )
        merged.chunk_id = merged.generate_id()
        return merged

    def _is_getter_setter_pair(
        self,
        chunk1: CodeChunk,
        chunk2: CodeChunk,
    ) -> bool:
        """Check if chunks form a getter/setter pair."""
        pairs = self.analyzer.find_getter_setter_pairs([chunk1, chunk2])
        return len(pairs) > 0

    def _are_overloaded_functions(
        self,
        chunk1: CodeChunk,
        chunk2: CodeChunk,
    ) -> bool:
        """Check if chunks are overloaded functions."""
        groups = self.analyzer.find_overloaded_functions([chunk1, chunk2])
        return any(len(group) == 2 for group in groups)

    def _are_small_related_methods(
        self,
        chunk1: CodeChunk,
        chunk2: CodeChunk,
    ) -> bool:
        """Check if chunks are small related methods that should be merged."""
        size1 = chunk1.end_line - chunk1.start_line + 1
        size2 = chunk2.end_line - chunk2.start_line + 1
        if (
            size1 > self.config.small_method_threshold
            or size2 > self.config.small_method_threshold
        ):
            return False
        if not chunk1.parent_context or chunk1.parent_context != chunk2.parent_context:
            return False
        if chunk1.node_type not in {
            "function_definition",
            "method_definition",
        }:
            return False
        if chunk2.node_type not in {
            "function_definition",
            "method_definition",
        }:
            return False
        line_distance = abs(chunk2.start_line - chunk1.end_line)
        return not line_distance > 5

    @staticmethod
    def _are_property_methods(chunk1: CodeChunk, chunk2: CodeChunk) -> bool:
        """Check if chunks are Python property methods (@property, @x.setter)."""
        if chunk1.language != "python":
            return False
        content1 = chunk1.content.lower()
        content2 = chunk2.content.lower()
        has_property = "@property" in content1 or "@property" in content2
        has_setter = ".setter" in content1 or ".setter" in content2
        return has_property and has_setter

    @staticmethod
    def _are_event_handlers(chunk1: CodeChunk, chunk2: CodeChunk) -> bool:
        """Check if chunks are related event handlers in JavaScript."""
        if chunk1.language not in {"javascript", "typescript"}:
            return False
        patterns = ["onclick", "onchange", "onsubmit", "onload", "addEventListener"]
        content1_lower = chunk1.content.lower()
        content2_lower = chunk2.content.lower()
        has_handler1 = any(p in content1_lower for p in patterns)
        has_handler2 = any(p in content2_lower for p in patterns)
        if not (has_handler1 and has_handler2):
            return False
        if chunk1.parent_context != chunk2.parent_context:
            return False
        line_distance = abs(chunk2.start_line - chunk1.end_line)
        return line_distance < 10

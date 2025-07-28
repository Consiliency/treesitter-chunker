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
    merge_interface_implementations: bool = False  # Usually kept separate
    small_method_threshold: int = 10  # Lines
    max_merged_size: int = 100  # Lines
    cohesion_threshold: float = 0.6

    # Language-specific settings
    language_configs: dict[str, dict] = None

    def __post_init__(self):
        if self.language_configs is None:
            self.language_configs = {
                "python": {
                    "merge_decorators": True,
                    "merge_property_methods": True,
                },
                "java": {
                    "merge_constructors": False,  # Often too large
                    "merge_overrides": True,
                },
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
        # Quick checks
        if chunk1.file_path != chunk2.file_path:
            return False

        if chunk1.language != chunk2.language:
            return False

        # Check size constraints
        total_lines = (chunk1.end_line - chunk1.start_line + 1) + (
            chunk2.end_line - chunk2.start_line + 1
        )
        if total_lines > self.config.max_merged_size:
            return False

        # Check cohesion threshold
        cohesion = self.analyzer.calculate_cohesion_score(chunk1, chunk2)
        if cohesion < self.config.cohesion_threshold:
            return False

        # Check specific merge patterns
        if self.config.merge_getters_setters:
            if self._is_getter_setter_pair(chunk1, chunk2):
                return True

        if self.config.merge_overloaded_functions:
            if self._are_overloaded_functions(chunk1, chunk2):
                return True

        if self.config.merge_small_methods:
            if self._are_small_related_methods(chunk1, chunk2):
                return True

        # Language-specific checks
        lang_config = self.config.language_configs.get(chunk1.language, {})

        if chunk1.language == "python" and lang_config.get("merge_property_methods"):
            if self._are_property_methods(chunk1, chunk2):
                return True

        if chunk1.language == "javascript" and lang_config.get("merge_event_handlers"):
            if self._are_event_handlers(chunk1, chunk2):
                return True

        return False

    def merge_chunks(self, chunks: list[CodeChunk]) -> list[CodeChunk]:
        """Merge related chunks to reduce fragmentation."""
        if not chunks:
            return []

        # Build merge groups
        merge_groups = self._build_merge_groups(chunks)

        # Create merged chunks
        result = []
        processed = set()

        for chunk in chunks:
            if chunk.chunk_id in processed:
                continue

            group = merge_groups.get(chunk.chunk_id)
            if group and len(group) > 1:
                # Merge the group
                merged = self._merge_chunk_group(group)
                result.append(merged)
                processed.update(c.chunk_id for c in group)
            else:
                # Keep as-is
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
        # Use Union-Find to build connected components
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

        # Find all pairs that should merge
        for i, chunk1 in enumerate(chunks):
            for chunk2 in chunks[i + 1 :]:
                if self.should_merge(chunk1, chunk2):
                    union(chunk1.chunk_id, chunk2.chunk_id)

        # Build groups
        groups = defaultdict(list)
        for chunk in chunks:
            root = find(chunk.chunk_id)
            groups[root].append(chunk)

        # Convert to chunk_id -> group mapping
        result = {}
        for group in groups.values():
            # Sort by start line for consistent ordering
            group.sort(key=lambda c: c.start_line)
            for chunk in group:
                result[chunk.chunk_id] = group

        return result

    def _merge_chunk_group(self, chunks: list[CodeChunk]) -> CodeChunk:
        """Merge a group of chunks into a single chunk."""
        # Sort by start line
        chunks = sorted(chunks, key=lambda c: c.start_line)

        # Calculate merged boundaries
        min_start_line = min(c.start_line for c in chunks)
        max_end_line = max(c.end_line for c in chunks)
        min_byte_start = min(c.byte_start for c in chunks)
        max_byte_end = max(c.byte_end for c in chunks)

        # Merge content (this is simplified - in reality might need file access)
        merged_content_lines = []
        for chunk in chunks:
            merged_content_lines.append(chunk.content)
            if chunk != chunks[-1]:  # Add separator except for last chunk
                merged_content_lines.append("")  # Empty line separator

        merged_content = "\n".join(merged_content_lines)

        # Determine merged node type
        node_types = {c.node_type for c in chunks}
        if len(node_types) == 1:
            merged_node_type = chunks[0].node_type
        else:
            merged_node_type = "merged_chunk"

        # Merge references and dependencies
        all_refs = set()
        all_deps = set()
        for chunk in chunks:
            all_refs.update(chunk.references)
            all_deps.update(chunk.dependencies)

        # Create merged chunk
        merged = CodeChunk(
            language=chunks[0].language,
            file_path=chunks[0].file_path,
            node_type=merged_node_type,
            start_line=min_start_line,
            end_line=max_end_line,
            byte_start=min_byte_start,
            byte_end=max_byte_end,
            parent_context=chunks[0].parent_context,  # Use first chunk's context
            content=merged_content,
            references=list(all_refs),
            dependencies=list(all_deps),
        )

        # Generate new ID for merged chunk
        merged.chunk_id = merged.generate_id()

        return merged

    def _is_getter_setter_pair(self, chunk1: CodeChunk, chunk2: CodeChunk) -> bool:
        """Check if chunks form a getter/setter pair."""
        pairs = self.analyzer.find_getter_setter_pairs([chunk1, chunk2])
        return len(pairs) > 0

    def _are_overloaded_functions(self, chunk1: CodeChunk, chunk2: CodeChunk) -> bool:
        """Check if chunks are overloaded functions."""
        groups = self.analyzer.find_overloaded_functions([chunk1, chunk2])
        return any(len(group) == 2 for group in groups)

    def _are_small_related_methods(self, chunk1: CodeChunk, chunk2: CodeChunk) -> bool:
        """Check if chunks are small related methods that should be merged."""
        # Check if both are small
        size1 = chunk1.end_line - chunk1.start_line + 1
        size2 = chunk2.end_line - chunk2.start_line + 1

        if (
            size1 > self.config.small_method_threshold
            or size2 > self.config.small_method_threshold
        ):
            return False

        # Must be in same class
        if not chunk1.parent_context or chunk1.parent_context != chunk2.parent_context:
            return False

        # Check if they're methods
        if chunk1.node_type not in ["function_definition", "method_definition"]:
            return False
        if chunk2.node_type not in ["function_definition", "method_definition"]:
            return False

        # Check proximity
        line_distance = abs(chunk2.start_line - chunk1.end_line)
        if line_distance > 5:  # Not adjacent
            return False

        return True

    def _are_property_methods(self, chunk1: CodeChunk, chunk2: CodeChunk) -> bool:
        """Check if chunks are Python property methods (@property, @x.setter)."""
        if chunk1.language != "python":
            return False

        # Look for @property and @x.setter decorators
        content1 = chunk1.content.lower()
        content2 = chunk2.content.lower()

        has_property = "@property" in content1 or "@property" in content2
        has_setter = ".setter" in content1 or ".setter" in content2

        return has_property and has_setter

    def _are_event_handlers(self, chunk1: CodeChunk, chunk2: CodeChunk) -> bool:
        """Check if chunks are related event handlers in JavaScript."""
        if chunk1.language not in ["javascript", "typescript"]:
            return False

        # Simple heuristic: check for common event handler patterns
        patterns = ["onclick", "onchange", "onsubmit", "onload", "addEventListener"]

        content1_lower = chunk1.content.lower()
        content2_lower = chunk2.content.lower()

        has_handler1 = any(p in content1_lower for p in patterns)
        has_handler2 = any(p in content2_lower for p in patterns)

        if not (has_handler1 and has_handler2):
            return False

        # Check if they're in the same context and nearby
        if chunk1.parent_context != chunk2.parent_context:
            return False

        line_distance = abs(chunk2.start_line - chunk1.end_line)
        return line_distance < 10

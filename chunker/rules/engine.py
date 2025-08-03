"""Rule engine for executing custom chunking rules."""
import logging
from collections import defaultdict
from typing import Any

from tree_sitter import Node, Tree

from chunker.interfaces.rules import CustomRule, RegexRule, RuleEngine
from chunker.types import CodeChunk

from .custom import BaseRegexRule

logger = logging.getLogger(__name__)


class DefaultRuleEngine(RuleEngine):
    """Default implementation of the rule engine."""

    def __init__(self):
        self._rules: dict[str, CustomRule] = {}
        self._priorities: dict[str, int] = {}
        self._regex_rules: list[RegexRule] = []
        self._node_rules: list[CustomRule] = []

    def add_rule(self, rule: CustomRule, priority: (int | None) = None) -> None:
        """Add a custom rule to the engine."""
        rule_name = rule.get_name()
        if rule_name in self._rules:
            logger.warning("Replacing existing rule: %s", rule_name)
        self._rules[rule_name] = rule
        self._priorities[rule_name
            ] = priority if priority is not None else rule.get_priority()
        if isinstance(rule, RegexRule):
            self._regex_rules.append(rule)
        else:
            self._node_rules.append(rule)
        self._sort_rules()
<<<<<<< HEAD

        logger.info(
            "Added rule '%s' with priority %d",
            rule_name,
            self._priorities[rule_name],
        )
=======
        logger.info("Added rule '%s' with priority %s" % (rule_name, self.
            _priorities[rule_name]))
>>>>>>> origin/main

    def remove_rule(self, rule_name: str) -> bool:
        """Remove a rule by name."""
        if rule_name not in self._rules:
            return False
        rule = self._rules.pop(rule_name)
        self._priorities.pop(rule_name)
        if isinstance(rule, RegexRule):
            self._regex_rules = [r for r in self._regex_rules if r.get_name
                () != rule_name]
        else:
            self._node_rules = [r for r in self._node_rules if r.get_name() !=
                rule_name]
        logger.info("Removed rule: %s", rule_name)
        return True

    def apply_rules(self, tree: Tree, source: bytes, file_path: str) -> list[
        CodeChunk]:
        """Apply all rules to extract chunks."""
        chunks = []
        processed_ranges: set[tuple[int, int]] = set()
        chunks.extend(self._apply_node_rules(tree.root_node, source,
            file_path, processed_ranges))
        chunks.extend(self._apply_bounded_regex_rules(tree.root_node,
            source, file_path, processed_ranges))
        chunks.extend(self._apply_cross_boundary_regex_rules(source,
            file_path, processed_ranges))
        logger.info("Extracted %s chunks from %s", len(chunks), file_path)
        return chunks

    def apply_regex_rules(self, source: bytes, file_path: str) -> list[CodeChunk
        ]:
        """Apply only regex-based rules that work on raw text."""
        chunks = []
        processed_ranges: set[tuple[int, int]] = set()
        for rule in self._regex_rules:
            if rule.should_cross_node_boundaries():
                chunks.extend(self._apply_single_regex_rule(rule, source,
                    file_path, processed_ranges))
        return chunks

    def merge_with_tree_sitter_chunks(self, custom_chunks: list[CodeChunk],
        tree_sitter_chunks: list[CodeChunk]) -> list[CodeChunk]:
        """Merge custom rule chunks with Tree-sitter chunks."""
        range_map: dict[tuple[int, int], list[CodeChunk]] = defaultdict(list)
        for chunk in (tree_sitter_chunks + custom_chunks):
            range_map[chunk.byte_start, chunk.byte_end].append(chunk)
        merged_chunks = []
        processed_ranges: set[tuple[int, int]] = set()
        sorted_ranges = sorted(range_map.keys(), key=lambda r: (r[0], -(r[1
            ] - r[0])))
        for byte_range in sorted_ranges:
            if byte_range in processed_ranges:
                continue
            chunks_at_range = range_map[byte_range]
            if len(chunks_at_range) == 1:
                merged_chunks.append(chunks_at_range[0])
                processed_ranges.add(byte_range)
                continue
            ts_chunks = [c for c in chunks_at_range if not c.node_type.
                startswith(("regex_", "comment_", "file_"))]
            custom_chunks_sorted = sorted([c for c in chunks_at_range if c.
                node_type.startswith(("regex_", "comment_", "file_"))], key=self._get_chunk_priority, reverse=True)
            merged_chunks.extend(ts_chunks)
            for custom_chunk in custom_chunks_sorted:
                if not self._overlaps_with_existing(custom_chunk, merged_chunks,
                    ):
                    merged_chunks.append(custom_chunk)
            processed_ranges.add(byte_range)
        merged_chunks.sort(key=lambda c: (c.byte_start, c.byte_end))
        logger.info(
<<<<<<< HEAD
            "Merged %d TS chunks and %d custom chunks into %d total chunks",
            len(tree_sitter_chunks),
            len(custom_chunks),
            len(merged_chunks),
        )
=======
            "Merged %s TS chunks and %s custom chunks into %s total chunks", (len(tree_sitter_chunks), len(custom_chunks), len(merged_chunks)))
>>>>>>> origin/main
        return merged_chunks

    def list_rules(self) -> list[dict[str, Any]]:
        """List all registered rules with their info."""
        rules_info = []
        for name, rule in self._rules.items():
            rules_info.append({"name": name, "description": rule.
                get_description(), "priority": self._priorities[name],
                "type": rule.__class__.__name__, "is_regex": isinstance(
                rule, RegexRule), "cross_boundary": isinstance(rule,
                RegexRule) and rule.should_cross_node_boundaries()})
        rules_info.sort(key=lambda r: r["priority"], reverse=True)
        return rules_info

    def _sort_rules(self):
        """Sort rules by priority."""
        self._node_rules.sort(key=lambda r: self._priorities[r.get_name()],
            reverse=True)
        self._regex_rules.sort(key=lambda r: self._priorities[r.get_name()],
            reverse=True)

    def _apply_node_rules(self, node: Node, source: bytes, file_path: str,
        processed_ranges: set[tuple[int, int]]) -> list[CodeChunk]:
        """Apply node-based rules recursively."""
        chunks = []
        for rule in self._node_rules:
            if rule.matches(node, source):
                chunk = rule.extract_chunk(node, source, file_path)
                if chunk and (chunk.byte_start, chunk.byte_end,
                    ) not in processed_ranges:
                    chunks.append(chunk)
                    processed_ranges.add((chunk.byte_start, chunk.byte_end))
        for child in node.children:
            chunks.extend(self._apply_node_rules(child, source, file_path,
                processed_ranges))
        return chunks

    def _apply_bounded_regex_rules(self, node: Node, source: bytes,
        file_path: str, processed_ranges: set[tuple[int, int]]) -> list[
        CodeChunk]:
        """Apply regex rules that respect node boundaries."""
        chunks = []
        for rule in self._regex_rules:
            if not rule.should_cross_node_boundaries() and rule.matches(node,
                source):
                chunk = rule.extract_chunk(node, source, file_path)
                if chunk and (chunk.byte_start, chunk.byte_end,
                    ) not in processed_ranges:
                    chunks.append(chunk)
                    processed_ranges.add((chunk.byte_start, chunk.byte_end))
        for child in node.children:
            chunks.extend(self._apply_bounded_regex_rules(child, source,
                file_path, processed_ranges))
        return chunks

    def _apply_cross_boundary_regex_rules(self, source: bytes, file_path:
        str, processed_ranges: set[tuple[int, int]]) -> list[CodeChunk]:
        """Apply regex rules that can cross node boundaries."""
        chunks = []
        for rule in self._regex_rules:
            if rule.should_cross_node_boundaries():
                chunks.extend(self._apply_single_regex_rule(rule, source,
                    file_path, processed_ranges))
        return chunks

    @classmethod
    def _apply_single_regex_rule(cls, rule: BaseRegexRule, source: bytes,
        file_path: str, processed_ranges: set[tuple[int, int]]) -> list[
        CodeChunk]:
        """Apply a single regex rule to the entire source."""
        chunks = []
        matches = rule.find_all_matches(source, file_path)
        for match in matches:
            if (match.start_byte, match.end_byte) not in processed_ranges:
                chunk = CodeChunk(language=rule._get_language_from_path(
                    file_path), file_path=file_path, node_type=f"regex_match_{rule.get_name()}", start_line=match.
                    start_point[0] + 1, end_line=match.end_point[0] + 1,
                    byte_start=match.start_byte, byte_end=match.end_byte,
                    parent_context="file", content=source[match.start_byte:
                    match.end_byte].decode("utf-8", errors="replace"))
                chunks.append(chunk)
                processed_ranges.add((match.start_byte, match.end_byte))
        return chunks

    def _get_chunk_priority(self, chunk: CodeChunk) -> int:
        """Get priority for a chunk based on its rule."""
        if chunk.node_type.startswith("regex_match_"):
            rule_name = chunk.node_type[len("regex_match_"):]
        elif chunk.node_type.startswith("comment_block_"):
            rule_name = "comment_block"
        elif chunk.node_type == "file_metadata":
            rule_name = "file_metadata"
        else:
            return 0
        return self._priorities.get(rule_name, 0)

    @staticmethod
    def _overlaps_with_existing(chunk: CodeChunk, existing_chunks: list[
        CodeChunk]) -> bool:
        """Check if chunk overlaps with any existing chunks."""
        for existing in existing_chunks:
            if (chunk.byte_start < existing.byte_end and chunk.byte_end >
                existing.byte_start):
                return True
        return False

"""Custom rule interfaces for extending Tree-sitter chunking."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from re import Pattern
from typing import Any

from tree_sitter import Node, Tree

from chunker.types import CodeChunk


@dataclass
class RuleMatch:
    """Represents a match from a custom rule."""

    rule_name: str
    start_byte: int
    end_byte: int
    start_point: tuple[int, int]
    end_point: tuple[int, int]
    metadata: dict[str, Any]


class CustomRule(ABC):
    """Define custom chunking rules to extend Tree-sitter."""

    @staticmethod
    @abstractmethod
    def get_name() -> str:
        """Get rule name for identification."""

    @staticmethod
    @abstractmethod
    def get_description() -> str:
        """Get human-readable description of what this rule does."""

    @staticmethod
    @abstractmethod
    def matches(node: Node, source: bytes) -> bool:
        """
        Check if this rule matches the given node.

        Args:
            node: AST node to check
            source: Source code bytes

        Returns:
            True if rule matches this node
        """

    @staticmethod
    @abstractmethod
    def extract_chunk(node: Node, source: bytes, file_path: str) -> CodeChunk | None:
        """
        Extract a chunk based on this rule.

        Args:
            node: AST node that matched
            source: Source code bytes
            file_path: Path to source file

        Returns:
            Extracted chunk or None
        """

    @staticmethod
    @abstractmethod
    def get_priority() -> int:
        """
        Get rule priority (higher numbers = higher priority).

        Returns:
            Priority value
        """


class RegexRule(CustomRule):
    """Base class for regex-based rules."""

    @staticmethod
    @abstractmethod
    def get_pattern() -> Pattern:
        """Get the regex pattern for this rule."""

    @staticmethod
    @abstractmethod
    def should_cross_node_boundaries() -> bool:
        """Whether this rule can match across Tree-sitter node boundaries."""


class CommentBlockRule(CustomRule):
    """Base class for comment block extraction rules."""

    @staticmethod
    @abstractmethod
    def get_comment_markers() -> dict[str, list[str]]:
        """
        Get comment markers for different styles.

        Returns:
            Dict with 'single_line', 'block_start', 'block_end' markers
        """

    @staticmethod
    @abstractmethod
    def should_merge_adjacent_comments() -> bool:
        """Whether to merge adjacent comment lines into blocks."""


class RuleEngine(ABC):
    """Execute custom rules with priority and conflict resolution."""

    @staticmethod
    @abstractmethod
    def add_rule(rule: CustomRule, priority: int | None = None) -> None:
        """
        Add a custom rule to the engine.

        Args:
            rule: The rule to add
            priority: Override rule's default priority
        """

    @staticmethod
    @abstractmethod
    def remove_rule(rule_name: str) -> bool:
        """
        Remove a rule by name.

        Args:
            rule_name: Name of rule to remove

        Returns:
            True if rule was removed
        """

    @staticmethod
    @abstractmethod
    def apply_rules(tree: Tree, source: bytes, file_path: str) -> list[CodeChunk]:
        """
        Apply all rules to extract chunks.

        This should complement Tree-sitter chunks, not replace them.

        Args:
            tree: Tree-sitter parse tree
            source: Source code bytes
            file_path: Path to source file

        Returns:
            List of chunks extracted by custom rules
        """

    @staticmethod
    @abstractmethod
    def apply_regex_rules(source: bytes, file_path: str) -> list[CodeChunk]:
        """
        Apply only regex-based rules that work on raw text.

        Args:
            source: Source code bytes
            file_path: Path to source file

        Returns:
            List of chunks from regex rules
        """

    @staticmethod
    @abstractmethod
    def merge_with_tree_sitter_chunks(
        custom_chunks: list[CodeChunk],
        tree_sitter_chunks: list[CodeChunk],
    ) -> list[CodeChunk]:
        """
        Merge custom rule chunks with Tree-sitter chunks.

        Should handle overlaps and conflicts intelligently.

        Args:
            custom_chunks: Chunks from custom rules
            tree_sitter_chunks: Chunks from Tree-sitter

        Returns:
            Merged list of chunks
        """

    @staticmethod
    @abstractmethod
    def list_rules() -> list[dict[str, Any]]:
        """
        List all registered rules with their info.

        Returns:
            List of rule info dicts with name, description, priority
        """

"""Custom rule interfaces for extending Tree-sitter chunking."""

from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any, Pattern, Tuple
from dataclasses import dataclass
import re

from tree_sitter import Node, Tree
from ..types import CodeChunk


@dataclass
class RuleMatch:
    """Represents a match from a custom rule."""
    rule_name: str
    start_byte: int
    end_byte: int
    start_point: Tuple[int, int]
    end_point: Tuple[int, int]
    metadata: Dict[str, Any]


class CustomRule(ABC):
    """Define custom chunking rules to extend Tree-sitter."""
    
    @abstractmethod
    def get_name(self) -> str:
        """Get rule name for identification."""
        pass
    
    @abstractmethod
    def get_description(self) -> str:
        """Get human-readable description of what this rule does."""
        pass
    
    @abstractmethod
    def matches(self, node: Node, source: bytes) -> bool:
        """
        Check if this rule matches the given node.
        
        Args:
            node: AST node to check
            source: Source code bytes
            
        Returns:
            True if rule matches this node
        """
        pass
    
    @abstractmethod
    def extract_chunk(self, node: Node, source: bytes, file_path: str) -> Optional[CodeChunk]:
        """
        Extract a chunk based on this rule.
        
        Args:
            node: AST node that matched
            source: Source code bytes
            file_path: Path to source file
            
        Returns:
            Extracted chunk or None
        """
        pass
    
    @abstractmethod
    def get_priority(self) -> int:
        """
        Get rule priority (higher numbers = higher priority).
        
        Returns:
            Priority value
        """
        pass


class RegexRule(CustomRule):
    """Base class for regex-based rules."""
    
    @abstractmethod
    def get_pattern(self) -> Pattern:
        """Get the regex pattern for this rule."""
        pass
    
    @abstractmethod
    def should_cross_node_boundaries(self) -> bool:
        """Whether this rule can match across Tree-sitter node boundaries."""
        pass


class CommentBlockRule(CustomRule):
    """Base class for comment block extraction rules."""
    
    @abstractmethod
    def get_comment_markers(self) -> Dict[str, List[str]]:
        """
        Get comment markers for different styles.
        
        Returns:
            Dict with 'single_line', 'block_start', 'block_end' markers
        """
        pass
    
    @abstractmethod
    def should_merge_adjacent_comments(self) -> bool:
        """Whether to merge adjacent comment lines into blocks."""
        pass


class RuleEngine(ABC):
    """Execute custom rules with priority and conflict resolution."""
    
    @abstractmethod
    def add_rule(self, rule: CustomRule, priority: Optional[int] = None) -> None:
        """
        Add a custom rule to the engine.
        
        Args:
            rule: The rule to add
            priority: Override rule's default priority
        """
        pass
    
    @abstractmethod
    def remove_rule(self, rule_name: str) -> bool:
        """
        Remove a rule by name.
        
        Args:
            rule_name: Name of rule to remove
            
        Returns:
            True if rule was removed
        """
        pass
    
    @abstractmethod
    def apply_rules(self, tree: Tree, source: bytes, file_path: str) -> List[CodeChunk]:
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
        pass
    
    @abstractmethod
    def apply_regex_rules(self, source: bytes, file_path: str) -> List[CodeChunk]:
        """
        Apply only regex-based rules that work on raw text.
        
        Args:
            source: Source code bytes
            file_path: Path to source file
            
        Returns:
            List of chunks from regex rules
        """
        pass
    
    @abstractmethod
    def merge_with_tree_sitter_chunks(self, custom_chunks: List[CodeChunk], 
                                    tree_sitter_chunks: List[CodeChunk]) -> List[CodeChunk]:
        """
        Merge custom rule chunks with Tree-sitter chunks.
        
        Should handle overlaps and conflicts intelligently.
        
        Args:
            custom_chunks: Chunks from custom rules
            tree_sitter_chunks: Chunks from Tree-sitter
            
        Returns:
            Merged list of chunks
        """
        pass
    
    @abstractmethod
    def list_rules(self) -> List[Dict[str, Any]]:
        """
        List all registered rules with their info.
        
        Returns:
            List of rule info dicts with name, description, priority
        """
        pass
"""AST-based context extraction interfaces.

Interfaces for extracting and preserving context from the AST,
such as imports, type definitions, and parent scopes.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum

from tree_sitter import Node

from .base import ASTProcessor


class ContextType(Enum):
    """Types of context that can be extracted."""
    IMPORT = "import"
    TYPE_DEF = "type_definition"
    DECORATOR = "decorator"
    PARENT_SCOPE = "parent_scope"
    DEPENDENCY = "dependency"
    NAMESPACE = "namespace"
    CONSTANT = "constant"
    GLOBAL_VAR = "global_variable"


@dataclass
class ContextItem:
    """Represents a single context item.

    Attributes:
        type: Type of context item
        content: The actual content (code)
        node: AST node this was extracted from
        line_number: Line number in source file
        importance: Priority for inclusion (0-100)
    """
    type: ContextType
    content: str
    node: Node
    line_number: int
    importance: int = 50

    def __lt__(self, other: "ContextItem") -> bool:
        """Sort by importance (descending) then line number."""
        if self.importance != other.importance:
            return self.importance > other.importance
        return self.line_number < other.line_number


class ContextExtractor(ASTProcessor):
    """Extract context information from AST."""

    @staticmethod
    @abstractmethod
    def extract_imports(ast: Node, source: bytes) -> list[ContextItem]:
        """Extract all import statements from the AST.

        Args:
            ast: Root node of the AST
            source: Original source code

        Returns:
            List of import context items
        """

    @staticmethod
    @abstractmethod
    def extract_type_definitions(ast: Node, source: bytes) -> list[ContextItem]:
        """Extract type definitions (classes, interfaces, types).

        Args:
            ast: Root node of the AST
            source: Original source code

        Returns:
            List of type definition context items
        """

    @staticmethod
    @abstractmethod
    def extract_dependencies(node: Node, ast: Node, source: bytes) -> list[
        ContextItem]:
        """Extract dependencies for a specific node.

        This includes any symbols, types, or functions that the node
        depends on to function correctly.

        Args:
            node: Node to analyze dependencies for
            ast: Full AST for context
            source: Original source code

        Returns:
            List of dependency context items
        """

    @staticmethod
    @abstractmethod
    def extract_parent_context(node: Node, ast: Node, source: bytes) -> list[
        ContextItem]:
        """Extract parent scope context (enclosing class, function, etc).

        Args:
            node: Node to get parent context for
            ast: Full AST
            source: Original source code

        Returns:
            List of parent context items
        """

    @staticmethod
    @abstractmethod
    def find_decorators(node: Node, source: bytes) -> list[ContextItem]:
        """Extract decorators for a node (if applicable).

        Args:
            node: Node to check for decorators
            source: Original source code

        Returns:
            List of decorator context items
        """

    @staticmethod
    @abstractmethod
    def build_context_prefix(context_items: list[ContextItem], max_size: (
        int | None) = None) -> str:
        """Build a context string to prepend to a chunk.

        Args:
            context_items: List of context items to include
            max_size: Maximum size in characters (None for no limit)

        Returns:
            Formatted context string
        """


class SymbolResolver(ABC):
    """Resolve symbol references in the AST."""

    @staticmethod
    @abstractmethod
    def find_symbol_definition(symbol_name: str, scope_node: Node, ast: Node,
        ) -> (Node | None):
        """Find where a symbol is defined.

        Args:
            symbol_name: Name of the symbol to find
            scope_node: Node representing the current scope
            ast: Full AST to search

        Returns:
            Node where symbol is defined, or None
        """

    @staticmethod
    @abstractmethod
    def get_symbol_type(symbol_node: Node) -> str:
        """Get the type of a symbol (function, class, variable, etc).

        Args:
            symbol_node: Node representing the symbol

        Returns:
            Type identifier (e.g., 'function', 'class', 'variable')
        """

    @staticmethod
    @abstractmethod
    def find_symbol_references(symbol_name: str, ast: Node) -> list[Node]:
        """Find all references to a symbol.

        Args:
            symbol_name: Name of the symbol
            ast: AST to search

        Returns:
            List of nodes that reference the symbol
        """


class ScopeAnalyzer(ABC):
    """Analyze scope relationships in the AST."""

    @staticmethod
    @abstractmethod
    def get_enclosing_scope(node: Node) -> (Node | None):
        """Get the enclosing scope for a node.

        Args:
            node: Node to analyze

        Returns:
            Enclosing scope node (function, class, etc) or None
        """

    @staticmethod
    @abstractmethod
    def get_scope_type(scope_node: Node) -> str:
        """Get the type of a scope.

        Args:
            scope_node: Scope node

        Returns:
            Scope type (e.g., 'function', 'class', 'module')
        """

    @staticmethod
    @abstractmethod
    def get_visible_symbols(scope_node: Node, ast: Node) -> set[str]:
        """Get all symbols visible from a scope.

        Args:
            scope_node: Node representing the scope
            ast: Full AST for context

        Returns:
            Set of visible symbol names
        """

    @staticmethod
    @abstractmethod
    def get_scope_chain(node: Node) -> list[Node]:
        """Get the chain of enclosing scopes.

        Args:
            node: Starting node

        Returns:
            List of scope nodes from innermost to outermost
        """


class ContextFilter(ABC):
    """Filter context items for relevance."""

    @staticmethod
    @abstractmethod
    def is_relevant(context_item: ContextItem, chunk_node: Node) -> bool:
        """Determine if a context item is relevant to a chunk.

        Args:
            context_item: Context item to evaluate
            chunk_node: Node representing the chunk

        Returns:
            True if context is relevant
        """

    @staticmethod
    @abstractmethod
    def score_relevance(context_item: ContextItem, chunk_node: Node) -> float:
        """Score the relevance of a context item (0.0-1.0).

        Args:
            context_item: Context item to score
            chunk_node: Node representing the chunk

        Returns:
            Relevance score between 0.0 and 1.0
        """

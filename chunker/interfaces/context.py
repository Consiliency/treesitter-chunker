"""AST-based context extraction interfaces.

Interfaces for extracting and preserving context from the AST,
such as imports, type definitions, and parent scopes.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Set
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
    
    def __lt__(self, other: 'ContextItem') -> bool:
        """Sort by importance (descending) then line number."""
        if self.importance != other.importance:
            return self.importance > other.importance
        return self.line_number < other.line_number


class ContextExtractor(ASTProcessor):
    """Extract context information from AST."""
    
    @abstractmethod
    def extract_imports(self, ast: Node, source: bytes) -> List[ContextItem]:
        """Extract all import statements from the AST.
        
        Args:
            ast: Root node of the AST
            source: Original source code
            
        Returns:
            List of import context items
        """
        pass
    
    @abstractmethod
    def extract_type_definitions(self, ast: Node, source: bytes) -> List[ContextItem]:
        """Extract type definitions (classes, interfaces, types).
        
        Args:
            ast: Root node of the AST
            source: Original source code
            
        Returns:
            List of type definition context items
        """
        pass
    
    @abstractmethod
    def extract_dependencies(self, node: Node, ast: Node, source: bytes) -> List[ContextItem]:
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
        pass
    
    @abstractmethod
    def extract_parent_context(self, node: Node, ast: Node, source: bytes) -> List[ContextItem]:
        """Extract parent scope context (enclosing class, function, etc).
        
        Args:
            node: Node to get parent context for
            ast: Full AST
            source: Original source code
            
        Returns:
            List of parent context items
        """
        pass
    
    @abstractmethod
    def find_decorators(self, node: Node, source: bytes) -> List[ContextItem]:
        """Extract decorators for a node (if applicable).
        
        Args:
            node: Node to check for decorators
            source: Original source code
            
        Returns:
            List of decorator context items
        """
        pass
    
    @abstractmethod
    def build_context_prefix(self, context_items: List[ContextItem], max_size: Optional[int] = None) -> str:
        """Build a context string to prepend to a chunk.
        
        Args:
            context_items: List of context items to include
            max_size: Maximum size in characters (None for no limit)
            
        Returns:
            Formatted context string
        """
        pass


class SymbolResolver(ABC):
    """Resolve symbol references in the AST."""
    
    @abstractmethod
    def find_symbol_definition(self, symbol_name: str, scope_node: Node, ast: Node) -> Optional[Node]:
        """Find where a symbol is defined.
        
        Args:
            symbol_name: Name of the symbol to find
            scope_node: Node representing the current scope
            ast: Full AST to search
            
        Returns:
            Node where symbol is defined, or None
        """
        pass
    
    @abstractmethod
    def get_symbol_type(self, symbol_node: Node) -> str:
        """Get the type of a symbol (function, class, variable, etc).
        
        Args:
            symbol_node: Node representing the symbol
            
        Returns:
            Type identifier (e.g., 'function', 'class', 'variable')
        """
        pass
    
    @abstractmethod
    def find_symbol_references(self, symbol_name: str, ast: Node) -> List[Node]:
        """Find all references to a symbol.
        
        Args:
            symbol_name: Name of the symbol
            ast: AST to search
            
        Returns:
            List of nodes that reference the symbol
        """
        pass


class ScopeAnalyzer(ABC):
    """Analyze scope relationships in the AST."""
    
    @abstractmethod
    def get_enclosing_scope(self, node: Node) -> Optional[Node]:
        """Get the enclosing scope for a node.
        
        Args:
            node: Node to analyze
            
        Returns:
            Enclosing scope node (function, class, etc) or None
        """
        pass
    
    @abstractmethod
    def get_scope_type(self, scope_node: Node) -> str:
        """Get the type of a scope.
        
        Args:
            scope_node: Scope node
            
        Returns:
            Scope type (e.g., 'function', 'class', 'module')
        """
        pass
    
    @abstractmethod
    def get_visible_symbols(self, scope_node: Node, ast: Node) -> Set[str]:
        """Get all symbols visible from a scope.
        
        Args:
            scope_node: Node representing the scope
            ast: Full AST for context
            
        Returns:
            Set of visible symbol names
        """
        pass
    
    @abstractmethod
    def get_scope_chain(self, node: Node) -> List[Node]:
        """Get the chain of enclosing scopes.
        
        Args:
            node: Starting node
            
        Returns:
            List of scope nodes from innermost to outermost
        """
        pass


class ContextFilter(ABC):
    """Filter context items for relevance."""
    
    @abstractmethod
    def is_relevant(self, context_item: ContextItem, chunk_node: Node) -> bool:
        """Determine if a context item is relevant to a chunk.
        
        Args:
            context_item: Context item to evaluate
            chunk_node: Node representing the chunk
            
        Returns:
            True if context is relevant
        """
        pass
    
    @abstractmethod
    def score_relevance(self, context_item: ContextItem, chunk_node: Node) -> float:
        """Score the relevance of a context item (0.0-1.0).
        
        Args:
            context_item: Context item to score
            chunk_node: Node representing the chunk
            
        Returns:
            Relevance score between 0.0 and 1.0
        """
        pass
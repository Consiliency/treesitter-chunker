"""Metadata extraction interfaces for enriching chunks with additional information."""

from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any, Set
from dataclasses import dataclass

from tree_sitter import Node


@dataclass
class ComplexityMetrics:
    """Code complexity metrics."""
    cyclomatic: int
    cognitive: int
    nesting_depth: int
    lines_of_code: int
    logical_lines: int
    
    
@dataclass
class SignatureInfo:
    """Function/method signature information."""
    name: str
    parameters: List[Dict[str, Any]]  # [{name, type, default}]
    return_type: Optional[str]
    decorators: List[str]
    modifiers: List[str]  # static, async, etc.


class MetadataExtractor(ABC):
    """Extract rich metadata from AST nodes."""
    
    @abstractmethod
    def extract_signature(self, node: Node, source: bytes) -> Optional[SignatureInfo]:
        """
        Extract function/method signature information.
        
        Args:
            node: AST node (should be a function/method)
            source: Source code bytes
            
        Returns:
            Signature information or None
        """
        pass
    
    @abstractmethod
    def extract_docstring(self, node: Node, source: bytes) -> Optional[str]:
        """
        Extract docstring/comment from a node.
        
        Args:
            node: AST node
            source: Source code bytes
            
        Returns:
            Docstring text or None
        """
        pass
    
    @abstractmethod
    def extract_imports(self, node: Node, source: bytes) -> List[str]:
        """
        Extract import statements used within a node.
        
        Args:
            node: AST node
            source: Source code bytes
            
        Returns:
            List of import statements
        """
        pass
    
    @abstractmethod
    def extract_dependencies(self, node: Node, source: bytes) -> Set[str]:
        """
        Extract symbols that this chunk depends on.
        
        Args:
            node: AST node
            source: Source code bytes
            
        Returns:
            Set of dependency symbols
        """
        pass
    
    @abstractmethod
    def extract_exports(self, node: Node, source: bytes) -> Set[str]:
        """
        Extract symbols that this chunk exports/defines.
        
        Args:
            node: AST node
            source: Source code bytes
            
        Returns:
            Set of exported symbols
        """
        pass


class ComplexityAnalyzer(ABC):
    """Analyze code complexity metrics."""
    
    @abstractmethod
    def calculate_cyclomatic_complexity(self, node: Node) -> int:
        """
        Calculate cyclomatic complexity of a code node.
        
        Counts decision points (if, while, for, etc.).
        
        Args:
            node: AST node
            
        Returns:
            Cyclomatic complexity score
        """
        pass
    
    @abstractmethod
    def calculate_cognitive_complexity(self, node: Node) -> int:
        """
        Calculate cognitive complexity of a code node.
        
        Considers nesting, recursion, and logical operators.
        
        Args:
            node: AST node
            
        Returns:
            Cognitive complexity score
        """
        pass
    
    @abstractmethod
    def calculate_nesting_depth(self, node: Node) -> int:
        """
        Calculate maximum nesting depth.
        
        Args:
            node: AST node
            
        Returns:
            Maximum nesting level
        """
        pass
    
    @abstractmethod
    def count_logical_lines(self, node: Node, source: bytes) -> int:
        """
        Count logical lines of code (excluding comments and blanks).
        
        Args:
            node: AST node
            source: Source code bytes
            
        Returns:
            Number of logical lines
        """
        pass
    
    @abstractmethod
    def analyze_complexity(self, node: Node, source: bytes) -> ComplexityMetrics:
        """
        Perform complete complexity analysis.
        
        Args:
            node: AST node
            source: Source code bytes
            
        Returns:
            All complexity metrics
        """
        pass
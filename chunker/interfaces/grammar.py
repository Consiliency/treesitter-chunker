"""Grammar management interfaces.

Interfaces for managing Tree-sitter language grammars,
including fetching, building, and versioning.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set


class GrammarStatus(Enum):
    """Status of a grammar."""
    NOT_FOUND = "not_found"
    NOT_BUILT = "not_built"
    BUILDING = "building"
    READY = "ready"
    ERROR = "error"
    OUTDATED = "outdated"


@dataclass
class GrammarInfo:
    """Information about a language grammar.
    
    Attributes:
        name: Language name (e.g., 'python', 'javascript')
        repository_url: Git repository URL
        commit_hash: Specific commit to use
        abi_version: Tree-sitter ABI version required
        status: Current status of the grammar
        path: Path to compiled grammar file
        error: Error message if status is ERROR
    """
    name: str
    repository_url: str
    commit_hash: Optional[str] = None
    abi_version: Optional[int] = None
    status: GrammarStatus = GrammarStatus.NOT_FOUND
    path: Optional[Path] = None
    error: Optional[str] = None
    
    @property
    def is_available(self) -> bool:
        """Check if grammar is ready to use."""
        return self.status == GrammarStatus.READY


@dataclass
class NodeTypeInfo:
    """Information about a node type in a grammar.
    
    Attributes:
        name: Node type name (e.g., 'function_definition')
        is_named: Whether this is a named node type
        has_children: Whether this node type can have children
        fields: List of field names this node type has
        supertypes: Parent types in the grammar hierarchy
    """
    name: str
    is_named: bool
    has_children: bool
    fields: List[str]
    supertypes: List[str]


class GrammarManager(ABC):
    """Manages Tree-sitter language grammars."""
    
    @abstractmethod
    def add_grammar(self, 
                   name: str,
                   repository_url: str,
                   commit_hash: Optional[str] = None) -> GrammarInfo:
        """Add a new grammar to manage.
        
        Args:
            name: Language name
            repository_url: Git repository URL
            commit_hash: Specific commit (None for latest)
            
        Returns:
            Grammar information
        """
        pass
    
    @abstractmethod
    def fetch_grammar(self, name: str) -> bool:
        """Fetch grammar source from repository.
        
        Args:
            name: Language name
            
        Returns:
            True if successful
        """
        pass
    
    @abstractmethod
    def build_grammar(self, name: str) -> bool:
        """Build grammar from source.
        
        Args:
            name: Language name
            
        Returns:
            True if successful
        """
        pass
    
    @abstractmethod
    def get_grammar_info(self, name: str) -> Optional[GrammarInfo]:
        """Get information about a grammar.
        
        Args:
            name: Language name
            
        Returns:
            Grammar info or None if not found
        """
        pass
    
    @abstractmethod
    def list_grammars(self, status: Optional[GrammarStatus] = None) -> List[GrammarInfo]:
        """List all managed grammars.
        
        Args:
            status: Filter by status (None for all)
            
        Returns:
            List of grammar information
        """
        pass
    
    @abstractmethod
    def update_grammar(self, name: str) -> bool:
        """Update grammar to latest version.
        
        Args:
            name: Language name
            
        Returns:
            True if updated
        """
        pass
    
    @abstractmethod
    def remove_grammar(self, name: str) -> bool:
        """Remove a grammar.
        
        Args:
            name: Language name
            
        Returns:
            True if removed
        """
        pass
    
    @abstractmethod
    def get_node_types(self, language: str) -> List[NodeTypeInfo]:
        """Get all node types for a language.
        
        Args:
            language: Language name
            
        Returns:
            List of node type information
        """
        pass
    
    @abstractmethod
    def validate_grammar(self, name: str) -> Tuple[bool, Optional[str]]:
        """Validate a grammar is working correctly.
        
        Args:
            name: Language name
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        pass


class GrammarBuilder(ABC):
    """Builds Tree-sitter grammars from source."""
    
    @abstractmethod
    def set_build_directory(self, path: Path) -> None:
        """Set directory for build output.
        
        Args:
            path: Build output directory
        """
        pass
    
    @abstractmethod
    def set_source_directory(self, path: Path) -> None:
        """Set directory containing grammar sources.
        
        Args:
            path: Source directory
        """
        pass
    
    @abstractmethod
    def build(self, languages: List[str]) -> Dict[str, bool]:
        """Build specified languages.
        
        Args:
            languages: List of language names
            
        Returns:
            Dictionary mapping language to build success
        """
        pass
    
    @abstractmethod
    def clean(self, language: Optional[str] = None) -> None:
        """Clean build artifacts.
        
        Args:
            language: Specific language (None for all)
        """
        pass
    
    @abstractmethod
    def get_build_log(self, language: str) -> Optional[str]:
        """Get build log for a language.
        
        Args:
            language: Language name
            
        Returns:
            Build log or None
        """
        pass


class GrammarRepository(ABC):
    """Repository of known grammar sources."""
    
    @abstractmethod
    def search(self, query: str) -> List[GrammarInfo]:
        """Search for grammars.
        
        Args:
            query: Search query
            
        Returns:
            List of matching grammars
        """
        pass
    
    @abstractmethod
    def get_popular_grammars(self, limit: int = 20) -> List[GrammarInfo]:
        """Get most popular grammars.
        
        Args:
            limit: Maximum number to return
            
        Returns:
            List of popular grammars
        """
        pass
    
    @abstractmethod
    def get_grammar_by_extension(self, extension: str) -> Optional[GrammarInfo]:
        """Find grammar for a file extension.
        
        Args:
            extension: File extension (e.g., '.py')
            
        Returns:
            Grammar info or None
        """
        pass
    
    @abstractmethod
    def refresh_repository(self) -> bool:
        """Refresh repository data.
        
        Returns:
            True if successful
        """
        pass


class GrammarValidator(ABC):
    """Validates grammar compatibility and correctness."""
    
    @abstractmethod
    def check_abi_compatibility(self, grammar_path: Path) -> Tuple[bool, Optional[str]]:
        """Check if grammar ABI is compatible.
        
        Args:
            grammar_path: Path to compiled grammar
            
        Returns:
            Tuple of (is_compatible, error_message)
        """
        pass
    
    @abstractmethod
    def validate_node_types(self, 
                           language: str,
                           expected_types: Set[str]) -> List[str]:
        """Validate expected node types exist.
        
        Args:
            language: Language name
            expected_types: Set of expected node type names
            
        Returns:
            List of missing node types
        """
        pass
    
    @abstractmethod
    def test_parse(self, 
                  language: str,
                  sample_code: str) -> Tuple[bool, Optional[str]]:
        """Test parsing with sample code.
        
        Args:
            language: Language name
            sample_code: Sample code to parse
            
        Returns:
            Tuple of (success, error_message)
        """
        pass
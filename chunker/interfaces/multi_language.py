"""Multi-language project processing interface."""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Set, Tuple, Any
from dataclasses import dataclass
from enum import Enum

from ..types import CodeChunk


class EmbeddedLanguageType(Enum):
    """Types of embedded languages."""
    TEMPLATE = "template"  # HTML in JS, JSX, etc.
    QUERY = "query"  # SQL in Python/JS, GraphQL, etc.
    SCRIPT = "script"  # JS in HTML, Python in notebooks
    STYLE = "style"  # CSS in HTML/JS
    DOCUMENTATION = "documentation"  # Code in Markdown
    CONFIGURATION = "configuration"  # JSON/YAML in code


@dataclass
class LanguageRegion:
    """A region of code in a specific language."""
    language: str
    start_pos: int
    end_pos: int
    start_line: int
    end_line: int
    embedding_type: Optional[EmbeddedLanguageType] = None
    parent_language: Optional[str] = None


@dataclass
class CrossLanguageReference:
    """A reference between code in different languages."""
    source_chunk: CodeChunk
    target_chunk: CodeChunk
    reference_type: str  # 'import', 'api_call', 'shared_type', etc.
    confidence: float  # 0-1


class MultiLanguageProcessor(ABC):
    """Process projects with multiple languages."""
    
    @abstractmethod
    def detect_project_languages(self, project_path: str) -> Dict[str, float]:
        """
        Detect languages used in project with confidence scores.
        
        This should analyze file extensions, shebang lines, and content
        to determine which languages are present.
        
        Args:
            project_path: Root path of the project
            
        Returns:
            Dict mapping language names to usage percentage (0-1)
        """
        pass
    
    @abstractmethod
    def identify_language_regions(self, file_path: str, content: str) -> List[LanguageRegion]:
        """
        Identify regions of different languages within a file.
        
        Args:
            file_path: Path to the file
            content: File content
            
        Returns:
            List of language regions in the file
        """
        pass
    
    @abstractmethod
    def process_mixed_file(self, file_path: str, 
                          primary_language: str,
                          content: Optional[str] = None) -> List[CodeChunk]:
        """
        Process files with embedded languages.
        
        Examples:
        - HTML files with embedded JS/CSS
        - JSX/TSX files with HTML-like syntax
        - Markdown with code blocks
        - Jupyter notebooks with multiple languages
        
        Args:
            file_path: Path to the file
            primary_language: Main language of the file
            content: Optional file content (will read if not provided)
            
        Returns:
            Chunks from all languages in the file
        """
        pass
    
    @abstractmethod
    def extract_embedded_code(self, content: str, 
                            host_language: str,
                            target_language: str) -> List[Tuple[str, int, int]]:
        """
        Extract embedded code snippets.
        
        Args:
            content: Content to search
            host_language: Language containing the embedded code
            target_language: Language to extract
            
        Returns:
            List of (code_snippet, start_pos, end_pos) tuples
        """
        pass
    
    @abstractmethod
    def cross_language_references(self, chunks: List[CodeChunk]) -> List[CrossLanguageReference]:
        """
        Find references across language boundaries.
        
        Examples:
        - Python backend API called by JavaScript frontend
        - Shared types between TypeScript and Go
        - SQL queries referenced in application code
        
        Args:
            chunks: All chunks from the project
            
        Returns:
            List of cross-language references
        """
        pass
    
    @abstractmethod
    def group_by_feature(self, chunks: List[CodeChunk]) -> Dict[str, List[CodeChunk]]:
        """
        Group chunks from different languages by feature.
        
        This attempts to identify chunks that implement the same feature
        across different languages (e.g., frontend and backend for user auth).
        
        Args:
            chunks: All chunks from the project
            
        Returns:
            Dict mapping feature names to related chunks
        """
        pass


class LanguageDetector(ABC):
    """Detect programming languages in files and content."""
    
    @abstractmethod
    def detect_from_file(self, file_path: str) -> Tuple[str, float]:
        """
        Detect language from file path and content.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Tuple of (language, confidence)
        """
        pass
    
    @abstractmethod
    def detect_from_content(self, content: str, 
                          hint: Optional[str] = None) -> Tuple[str, float]:
        """
        Detect language from content alone.
        
        Args:
            content: Code content
            hint: Optional hint about expected language
            
        Returns:
            Tuple of (language, confidence)
        """
        pass
    
    @abstractmethod
    def detect_multiple(self, content: str) -> List[Tuple[str, float]]:
        """
        Detect multiple languages in content.
        
        Args:
            content: Content that may contain multiple languages
            
        Returns:
            List of (language, percentage) tuples
        """
        pass


class ProjectAnalyzer(ABC):
    """Analyze multi-language project structure."""
    
    @abstractmethod
    def analyze_structure(self, project_path: str) -> Dict[str, Any]:
        """
        Analyze overall project structure.
        
        Returns information about:
        - Primary languages
        - Framework detection
        - Project type (web app, library, etc.)
        - Component boundaries
        
        Args:
            project_path: Root path of project
            
        Returns:
            Project analysis results
        """
        pass
    
    @abstractmethod
    def find_api_boundaries(self, chunks: List[CodeChunk]) -> List[Dict[str, Any]]:
        """
        Find API boundaries between components.
        
        Args:
            chunks: All project chunks
            
        Returns:
            List of API boundary definitions
        """
        pass
    
    @abstractmethod
    def suggest_chunk_grouping(self, chunks: List[CodeChunk]) -> Dict[str, List[CodeChunk]]:
        """
        Suggest how to group chunks for processing.
        
        Args:
            chunks: All project chunks
            
        Returns:
            Suggested groupings
        """
        pass
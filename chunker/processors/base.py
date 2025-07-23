"""Base interface for specialized processors.

This module defines the SpecializedProcessor interface that all
file-type-specific processors must implement.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

from ..types import CodeChunk


@dataclass
class ProcessorConfig:
    """Configuration for specialized processors.
    
    Attributes:
        chunk_size: Target chunk size in lines
        preserve_structure: Whether to preserve file structure
        include_comments: Whether to include comments in chunks
        group_related: Whether to group related items
        format_specific: Format-specific configuration
    """
    chunk_size: int = 50
    preserve_structure: bool = True
    include_comments: bool = True
    group_related: bool = True
    format_specific: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.format_specific is None:
            self.format_specific = {}


class SpecializedProcessor(ABC):
    """Base interface for specialized file processors.
    
    Each processor handles a specific file type or format,
    providing intelligent chunking that preserves the
    semantic structure of the content.
    """
    
    def __init__(self, config: Optional[ProcessorConfig] = None):
        """Initialize processor with configuration.
        
        Args:
            config: Processor configuration
        """
        self.config = config or ProcessorConfig()
    
    @abstractmethod
    def can_handle(self, file_path: str, content: Optional[str] = None) -> bool:
        """Check if this processor can handle the given file.
        
        Args:
            file_path: Path to the file
            content: Optional file content for detection
            
        Returns:
            True if this processor can handle the file
        """
        pass
    
    @abstractmethod
    def detect_format(self, file_path: str, content: str) -> Optional[str]:
        """Detect the specific format of the file.
        
        Args:
            file_path: Path to the file
            content: File content
            
        Returns:
            Format identifier (e.g., 'ini', 'toml', 'yaml') or None
        """
        pass
    
    @abstractmethod
    def parse_structure(self, content: str, format: str) -> Dict[str, Any]:
        """Parse the file structure.
        
        Args:
            content: File content
            format: Detected format
            
        Returns:
            Parsed structure representation
        """
        pass
    
    @abstractmethod
    def chunk_content(self, content: str, structure: Dict[str, Any], 
                     file_path: str) -> List[CodeChunk]:
        """Chunk the content based on its structure.
        
        Args:
            content: File content
            structure: Parsed structure
            file_path: Path to the file
            
        Returns:
            List of code chunks
        """
        pass
    
    def process(self, file_path: str, content: str) -> List[CodeChunk]:
        """Process a file and return chunks.
        
        This is the main entry point that orchestrates the processing.
        
        Args:
            file_path: Path to the file
            content: File content
            
        Returns:
            List of code chunks
        """
        # Detect format
        format = self.detect_format(file_path, content)
        if format is None:
            raise ValueError(f"Cannot detect format for {file_path}")
        
        # Parse structure
        structure = self.parse_structure(content, format)
        
        # Chunk based on structure
        chunks = self.chunk_content(content, structure, file_path)
        
        return chunks
    
    @abstractmethod
    def get_supported_formats(self) -> List[str]:
        """Get list of supported file formats.
        
        Returns:
            List of format identifiers
        """
        pass
    
    @abstractmethod
    def get_format_extensions(self) -> Dict[str, List[str]]:
        """Get file extensions for each format.
        
        Returns:
            Mapping of format to list of extensions
        """
        pass
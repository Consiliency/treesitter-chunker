"""Base interfaces for specialized text processors.

This module defines the abstract base class for all specialized processors
that handle non-code text formats (logs, markdown, config files, etc.).
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Iterator, Tuple
from dataclasses import dataclass
from pathlib import Path


@dataclass
class TextChunk:
    """Represents a chunk of text with metadata."""
    content: str
    start_line: int
    end_line: int
    start_byte: int
    end_byte: int
    metadata: Dict[str, Any]
    chunk_type: str = "text"
    
    @property
    def line_count(self) -> int:
        """Number of lines in this chunk."""
        return self.end_line - self.start_line + 1
    
    @property
    def byte_size(self) -> int:
        """Size of chunk in bytes."""
        return self.end_byte - self.start_byte


class SpecializedProcessor(ABC):
    """Abstract base class for specialized text processors.
    
    Each processor handles a specific text format (logs, markdown, config, etc.)
    and provides format-specific chunking logic.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize processor with optional configuration.
        
        Args:
            config: Processor-specific configuration options
        """
        self.config = config or {}
        self._validate_config()
    
    @abstractmethod
    def _validate_config(self) -> None:
        """Validate processor configuration.
        
        Raises:
            ValueError: If configuration is invalid
        """
        pass
    
    @abstractmethod
    def can_process(self, file_path: Path, content: Optional[str] = None) -> bool:
        """Check if this processor can handle the given file.
        
        Args:
            file_path: Path to the file
            content: Optional file content for format detection
            
        Returns:
            True if this processor can handle the file
        """
        pass
    
    @abstractmethod
    def process(self, content: str, file_path: Optional[Path] = None) -> List[TextChunk]:
        """Process content and return chunks.
        
        Args:
            content: Text content to process
            file_path: Optional file path for context
            
        Returns:
            List of text chunks
        """
        pass
    
    @abstractmethod
    def process_stream(self, stream: Iterator[str], file_path: Optional[Path] = None) -> Iterator[TextChunk]:
        """Process content from a stream.
        
        Args:
            stream: Iterator yielding lines or chunks of text
            file_path: Optional file path for context
            
        Yields:
            Text chunks as they are processed
        """
        pass
    
    def get_supported_formats(self) -> List[str]:
        """Get list of supported file formats/extensions.
        
        Returns:
            List of supported extensions (e.g., ['.log', '.txt'])
        """
        return []
    
    def get_metadata(self) -> Dict[str, Any]:
        """Get processor metadata.
        
        Returns:
            Dictionary with processor information
        """
        return {
            "name": self.__class__.__name__,
            "supported_formats": self.get_supported_formats(),
            "config": self.config
        }
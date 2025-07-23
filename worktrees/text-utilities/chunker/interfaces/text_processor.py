"""
Abstract base class and interfaces for text processing utilities.

This module defines the core abstractions for text boundary detection,
natural break point identification, and text analysis operations.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict, Any, Iterator
from enum import Enum


class BoundaryType(Enum):
    """Types of text boundaries that can be detected."""
    SENTENCE = "sentence"
    PARAGRAPH = "paragraph"
    SECTION = "section"
    QUOTE = "quote"
    CODE_BLOCK = "code_block"


class ConfidenceLevel(Enum):
    """Confidence levels for boundary detection."""
    HIGH = 0.9
    MEDIUM = 0.7
    LOW = 0.5
    UNCERTAIN = 0.3


@dataclass
class TextBoundary:
    """
    Represents a detected text boundary with metadata.
    
    Attributes:
        start: Start position (character index) of the boundary
        end: End position (character index) of the boundary
        boundary_type: Type of boundary detected
        confidence: Confidence score (0.0 to 1.0) for the detection
        metadata: Additional metadata about the boundary
    """
    start: int
    end: int
    boundary_type: BoundaryType
    confidence: float
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        """Validate boundary attributes."""
        if self.start < 0 or self.end < 0:
            raise ValueError("Boundary positions must be non-negative")
        if self.start > self.end:
            raise ValueError("Start position must be less than or equal to end position")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("Confidence must be between 0.0 and 1.0")
    
    @property
    def length(self) -> int:
        """Return the length of the boundary."""
        return self.end - self.start
    
    @property
    def confidence_level(self) -> ConfidenceLevel:
        """Return the confidence level category."""
        if self.confidence >= ConfidenceLevel.HIGH.value:
            return ConfidenceLevel.HIGH
        elif self.confidence >= ConfidenceLevel.MEDIUM.value:
            return ConfidenceLevel.MEDIUM
        elif self.confidence >= ConfidenceLevel.LOW.value:
            return ConfidenceLevel.LOW
        else:
            return ConfidenceLevel.UNCERTAIN


@dataclass
class TextSegment:
    """
    Represents a segment of text with its boundaries.
    
    Attributes:
        text: The actual text content
        start_boundary: Starting boundary of the segment
        end_boundary: Ending boundary of the segment
        segment_type: Type of segment (sentence, paragraph, etc.)
    """
    text: str
    start_boundary: TextBoundary
    end_boundary: Optional[TextBoundary] = None
    segment_type: Optional[BoundaryType] = None
    
    @property
    def start(self) -> int:
        """Get the start position of the segment."""
        return self.start_boundary.start
    
    @property
    def end(self) -> int:
        """Get the end position of the segment."""
        if self.end_boundary:
            return self.end_boundary.end
        return self.start_boundary.end


class TextProcessor(ABC):
    """
    Abstract base class for text processing operations.
    
    Provides the foundation for various text analysis and boundary
    detection implementations.
    """
    
    def __init__(self, language: str = "en", encoding: str = "utf-8"):
        """
        Initialize the text processor.
        
        Args:
            language: ISO 639-1 language code (default: "en")
            encoding: Text encoding (default: "utf-8")
        """
        self.language = language
        self.encoding = encoding
    
    @abstractmethod
    def detect_boundaries(self, text: str) -> List[TextBoundary]:
        """
        Detect all boundaries in the given text.
        
        Args:
            text: The text to analyze
            
        Returns:
            List of detected boundaries with confidence scores
        """
        pass
    
    @abstractmethod
    def find_natural_breaks(self, text: str, max_length: int) -> List[int]:
        """
        Find natural break points in text for chunking.
        
        Args:
            text: The text to analyze
            max_length: Maximum desired chunk length
            
        Returns:
            List of character positions representing natural break points
        """
        pass
    
    @abstractmethod
    def segment_text(self, text: str) -> List[TextSegment]:
        """
        Segment text into logical units.
        
        Args:
            text: The text to segment
            
        Returns:
            List of text segments with boundary information
        """
        pass
    
    def analyze_text(self, text: str) -> Dict[str, Any]:
        """
        Perform comprehensive text analysis.
        
        Args:
            text: The text to analyze
            
        Returns:
            Dictionary containing analysis results
        """
        return {
            "language": self.language,
            "encoding": self.encoding,
            "length": len(text),
            "boundaries": self.detect_boundaries(text),
            "segments": self.segment_text(text)
        }
    
    def process_large_text(self, text: str, chunk_size: int = 10000) -> Iterator[TextSegment]:
        """
        Process large texts in chunks to manage memory.
        
        Args:
            text: The text to process
            chunk_size: Size of chunks to process at once
            
        Yields:
            Text segments as they are processed
        """
        for i in range(0, len(text), chunk_size):
            chunk = text[i:i + chunk_size]
            # Look ahead to avoid breaking in the middle of a sentence
            if i + chunk_size < len(text):
                # Find the next natural break point
                breaks = self.find_natural_breaks(chunk, chunk_size)
                if breaks:
                    chunk = text[i:i + breaks[-1]]
            
            segments = self.segment_text(chunk)
            for segment in segments:
                # Adjust positions to account for chunk offset
                segment.start_boundary.start += i
                segment.start_boundary.end += i
                if segment.end_boundary:
                    segment.end_boundary.start += i
                    segment.end_boundary.end += i
                yield segment


class BoundaryDetector(TextProcessor):
    """
    Abstract base class for specific boundary detection implementations.
    """
    
    @abstractmethod
    def get_boundary_type(self) -> BoundaryType:
        """Return the type of boundary this detector specializes in."""
        pass
    
    def detect_boundaries(self, text: str) -> List[TextBoundary]:
        """
        Detect boundaries of the specific type.
        
        Args:
            text: The text to analyze
            
        Returns:
            List of detected boundaries
        """
        boundaries = self._detect_specific_boundaries(text)
        # Set the boundary type for all detected boundaries
        boundary_type = self.get_boundary_type()
        for boundary in boundaries:
            boundary.boundary_type = boundary_type
        return boundaries
    
    @abstractmethod
    def _detect_specific_boundaries(self, text: str) -> List[TextBoundary]:
        """
        Implement specific boundary detection logic.
        
        Args:
            text: The text to analyze
            
        Returns:
            List of detected boundaries (without type set)
        """
        pass
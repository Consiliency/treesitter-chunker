"""Sliding window interfaces for text processing and chunking."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Iterator, Optional, List, Tuple, Union


class WindowUnit(Enum):
    """Units for measuring window size."""
    LINES = "lines"
    TOKENS = "tokens"
    BYTES = "bytes"
    CHARACTERS = "characters"


class OverlapStrategy(Enum):
    """Strategies for calculating window overlap."""
    FIXED = "fixed"  # Fixed amount of overlap
    PERCENTAGE = "percentage"  # Percentage of window size
    SEMANTIC = "semantic"  # Based on semantic boundaries (sentences, paragraphs)


@dataclass
class WindowConfig:
    """Configuration for sliding window processing."""
    size: int  # Window size in specified units
    unit: WindowUnit = WindowUnit.CHARACTERS
    overlap: int = 0  # Overlap amount (interpretation depends on overlap_strategy)
    overlap_strategy: OverlapStrategy = OverlapStrategy.FIXED
    min_window_size: Optional[int] = None  # Minimum window size (for dynamic adjustment)
    max_window_size: Optional[int] = None  # Maximum window size (for dynamic adjustment)
    preserve_boundaries: bool = True  # Try to preserve word/line boundaries
    trim_whitespace: bool = True  # Trim leading/trailing whitespace from windows
    

@dataclass
class WindowPosition:
    """Represents the current position of a sliding window."""
    start: int  # Start position in original text (always in characters)
    end: int  # End position in original text (always in characters)
    start_line: int = 0  # Start line number (1-based)
    end_line: int = 0  # End line number (1-based)
    window_index: int = 0  # Sequential index of this window
    total_windows: Optional[int] = None  # Total number of windows (if known)
    
    @property
    def size(self) -> int:
        """Size of this window in characters."""
        return self.end - self.start
    
    @property
    def progress(self) -> Optional[float]:
        """Progress percentage if total windows is known."""
        if self.total_windows and self.total_windows > 0:
            return (self.window_index + 1) / self.total_windows * 100
        return None


@dataclass
class Window:
    """A single window of text with metadata."""
    content: str
    position: WindowPosition
    metadata: dict = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
    
    @property
    def is_first(self) -> bool:
        """Check if this is the first window."""
        return self.position.window_index == 0
    
    @property
    def is_last(self) -> bool:
        """Check if this is the last window."""
        if self.position.total_windows:
            return self.position.window_index == self.position.total_windows - 1
        return False


class SlidingWindowEngine(ABC):
    """Abstract base class for sliding window processing."""
    
    @abstractmethod
    def __init__(self, config: WindowConfig):
        """
        Initialize the sliding window engine.
        
        Args:
            config: Window configuration
        """
        self.config = config
    
    @abstractmethod
    def process_text(self, text: str) -> Iterator[Window]:
        """
        Process text using sliding window approach.
        
        Args:
            text: The text to process
            
        Yields:
            Window objects containing text chunks and metadata
        """
        pass
    
    @abstractmethod
    def process_file(self, file_path: str, encoding: str = "utf-8") -> Iterator[Window]:
        """
        Process a file using sliding window approach with streaming.
        
        Args:
            file_path: Path to the file to process
            encoding: File encoding
            
        Yields:
            Window objects containing text chunks and metadata
        """
        pass
    
    @abstractmethod
    def calculate_overlap(self, window_size: int) -> int:
        """
        Calculate the actual overlap amount based on configuration.
        
        Args:
            window_size: Size of the current window
            
        Returns:
            Number of units to overlap
        """
        pass
    
    @abstractmethod
    def find_boundary(self, text: str, position: int, direction: str = "forward") -> int:
        """
        Find the nearest appropriate boundary (word, line, sentence).
        
        Args:
            text: The text to search in
            position: Current position
            direction: "forward" or "backward"
            
        Returns:
            Adjusted position at a boundary
        """
        pass
    
    @abstractmethod
    def estimate_total_windows(self, text_size: int) -> int:
        """
        Estimate the total number of windows for progress tracking.
        
        Args:
            text_size: Total size of text in characters
            
        Returns:
            Estimated number of windows
        """
        pass
    
    @abstractmethod
    def get_window_at_position(self, text: str, position: int) -> Optional[Window]:
        """
        Get the window containing the specified position.
        
        Args:
            text: The text to process
            position: Character position in the text
            
        Returns:
            Window containing the position, or None if position is invalid
        """
        pass
    
    @abstractmethod
    def adjust_window_size(self, text: str, start: int, 
                          suggested_size: int) -> Tuple[int, dict]:
        """
        Dynamically adjust window size based on content density.
        
        Args:
            text: The text being processed
            start: Start position of the window
            suggested_size: Suggested window size
            
        Returns:
            Tuple of (adjusted_size, metadata about the adjustment)
        """
        pass


class WindowNavigator(ABC):
    """Interface for navigating through windows."""
    
    @abstractmethod
    def next_window(self) -> Optional[Window]:
        """Move to and return the next window."""
        pass
    
    @abstractmethod
    def previous_window(self) -> Optional[Window]:
        """Move to and return the previous window."""
        pass
    
    @abstractmethod
    def jump_to_window(self, index: int) -> Optional[Window]:
        """Jump to a specific window by index."""
        pass
    
    @abstractmethod
    def jump_to_position(self, position: int) -> Optional[Window]:
        """Jump to the window containing a specific position."""
        pass
    
    @abstractmethod
    def current_window(self) -> Optional[Window]:
        """Get the current window without moving."""
        pass
    
    @abstractmethod
    def reset(self) -> None:
        """Reset navigation to the beginning."""
        pass
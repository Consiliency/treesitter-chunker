"""Default implementation of the sliding window engine."""

import re
from pathlib import Path
from typing import Iterator, Optional, Tuple, List
import threading
from collections import deque

from ..interfaces.sliding_window import (
    SlidingWindowEngine,
    WindowConfig,
    Window,
    WindowPosition,
    WindowUnit,
    OverlapStrategy
)


class DefaultSlidingWindowEngine(SlidingWindowEngine):
    """Default implementation of sliding window processing."""
    
    def __init__(self, config: WindowConfig):
        """Initialize the sliding window engine."""
        super().__init__(config)
        self._validate_config()
        self._lock = threading.Lock()
        
        # Precompile regex patterns for boundary detection
        self._word_boundary = re.compile(r'\b')
        self._sentence_boundary = re.compile(r'[.!?]+\s+')
        self._line_boundary = re.compile(r'\n')
        self._paragraph_boundary = re.compile(r'\n\s*\n')
        
    def _validate_config(self) -> None:
        """Validate the configuration."""
        if self.config.size <= 0:
            raise ValueError("Window size must be positive")
        
        if self.config.overlap < 0:
            raise ValueError("Overlap cannot be negative")
        
        if self.config.overlap_strategy == OverlapStrategy.PERCENTAGE:
            if self.config.overlap > 100:
                raise ValueError("Overlap percentage cannot exceed 100")
        
        if self.config.min_window_size and self.config.min_window_size <= 0:
            raise ValueError("Minimum window size must be positive")
        
        if self.config.max_window_size and self.config.max_window_size <= 0:
            raise ValueError("Maximum window size must be positive")
        
        if (self.config.min_window_size and self.config.max_window_size and 
            self.config.min_window_size > self.config.max_window_size):
            raise ValueError("Minimum window size cannot exceed maximum")
    
    def process_text(self, text: str) -> Iterator[Window]:
        """Process text using sliding window approach."""
        if not text:
            return
        
        # Convert window size to characters if needed
        window_size_chars = self._convert_to_characters(text, self.config.size)
        overlap_chars = self.calculate_overlap(window_size_chars)
        
        # Calculate total windows for progress tracking
        total_windows = self.estimate_total_windows(len(text))
        
        position = 0
        window_index = 0
        line_number = 1
        
        while position < len(text):
            # Determine window size (may be adjusted dynamically)
            current_size, size_metadata = self.adjust_window_size(
                text, position, window_size_chars
            )
            
            # Calculate end position
            end = min(position + current_size, len(text))
            
            # Adjust boundaries if needed
            if self.config.preserve_boundaries and end < len(text):
                end = self.find_boundary(text, end, "backward")
            
            # Extract window content
            content = text[position:end]
            
            # Trim whitespace if configured
            if self.config.trim_whitespace:
                content = content.strip()
                if not content:  # Skip empty windows
                    position = end
                    continue
            
            # Count lines for metadata
            start_line = line_number
            lines_in_window = content.count('\n')
            end_line = start_line + lines_in_window
            
            # Create window position
            window_pos = WindowPosition(
                start=position,
                end=end,
                start_line=start_line,
                end_line=end_line,
                window_index=window_index,
                total_windows=total_windows
            )
            
            # Create window with metadata
            metadata = {
                "overlap_chars": overlap_chars if window_index > 0 else 0,
                "actual_size": len(content),
                "size_adjusted": size_metadata.get("adjusted", False),
                "adjustment_reason": size_metadata.get("reason", None)
            }
            
            # Add unit-specific metadata
            if self.config.unit == WindowUnit.TOKENS:
                # This would require token counter integration
                metadata["token_count"] = self._estimate_tokens(content)
            elif self.config.unit == WindowUnit.LINES:
                metadata["line_count"] = lines_in_window + 1
            
            window = Window(content=content, position=window_pos, metadata=metadata)
            yield window
            
            # Update counters
            line_number += content[:end-position].count('\n')
            window_index += 1
            
            # Move to next position
            if end >= len(text):
                break
            
            # Apply overlap
            position = end - overlap_chars
            if position <= 0:
                position = end
    
    def process_file(self, file_path: str, encoding: str = "utf-8") -> Iterator[Window]:
        """Process a file using sliding window approach with streaming."""
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # For large files, use chunked reading
        file_size = file_path.stat().st_size
        
        # Define chunk size for reading (1MB chunks)
        read_chunk_size = 1024 * 1024
        
        if file_size <= read_chunk_size * 2:
            # Small file, read entirely
            with open(file_path, 'r', encoding=encoding) as f:
                text = f.read()
            yield from self.process_text(text)
        else:
            # Large file, use streaming with buffer
            yield from self._process_file_streaming(file_path, encoding, read_chunk_size)
    
    def _process_file_streaming(self, file_path: Path, encoding: str, 
                                chunk_size: int) -> Iterator[Window]:
        """Process large files with streaming to minimize memory usage."""
        with open(file_path, 'r', encoding=encoding) as f:
            buffer = deque(maxlen=3)  # Keep last 3 chunks for overlap handling
            window_index = 0
            global_position = 0
            line_number = 1
            
            # Estimate total windows based on file size
            file_size = file_path.stat().st_size
            total_windows = self.estimate_total_windows(file_size)
            
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                
                buffer.append(chunk)
                
                # Process with overlap from previous chunk
                if len(buffer) >= 2:
                    # Combine current and previous chunk for seamless processing
                    combined = ''.join(buffer)
                    
                    # Process combined text
                    for window in self._process_buffer(
                        combined, global_position, window_index, 
                        line_number, total_windows
                    ):
                        yield window
                        window_index += 1
                
                global_position += len(chunk)
                line_number += chunk.count('\n')
    
    def _process_buffer(self, text: str, global_offset: int, 
                       start_window_index: int, start_line: int,
                       total_windows: int) -> Iterator[Window]:
        """Process a buffer of text with proper position tracking."""
        # Similar to process_text but with offset handling
        window_size_chars = self._convert_to_characters(text, self.config.size)
        overlap_chars = self.calculate_overlap(window_size_chars)
        
        position = 0
        window_index = start_window_index
        line_number = start_line
        
        while position < len(text) - window_size_chars:  # Leave last window for next buffer
            current_size, size_metadata = self.adjust_window_size(
                text, position, window_size_chars
            )
            
            end = min(position + current_size, len(text))
            
            if self.config.preserve_boundaries and end < len(text):
                end = self.find_boundary(text, end, "backward")
            
            content = text[position:end]
            
            if self.config.trim_whitespace:
                content = content.strip()
                if not content:
                    position = end
                    continue
            
            lines_in_window = content.count('\n')
            
            window_pos = WindowPosition(
                start=global_offset + position,
                end=global_offset + end,
                start_line=line_number,
                end_line=line_number + lines_in_window,
                window_index=window_index,
                total_windows=total_windows
            )
            
            metadata = {
                "overlap_chars": overlap_chars if window_index > 0 else 0,
                "actual_size": len(content),
                "size_adjusted": size_metadata.get("adjusted", False)
            }
            
            yield Window(content=content, position=window_pos, metadata=metadata)
            
            line_number += content[:end-position].count('\n')
            position = end - overlap_chars
    
    def calculate_overlap(self, window_size: int) -> int:
        """Calculate the actual overlap amount based on configuration."""
        if self.config.overlap_strategy == OverlapStrategy.FIXED:
            return min(self.config.overlap, window_size - 1)
        elif self.config.overlap_strategy == OverlapStrategy.PERCENTAGE:
            return int(window_size * self.config.overlap / 100)
        elif self.config.overlap_strategy == OverlapStrategy.SEMANTIC:
            # For semantic overlap, we use a percentage but ensure it ends at boundaries
            return int(window_size * 0.1)  # Default 10% for semantic
        else:
            return 0
    
    def find_boundary(self, text: str, position: int, direction: str = "forward") -> int:
        """Find the nearest appropriate boundary."""
        if position <= 0 or position >= len(text):
            return position
        
        # Try different boundary types in order of preference
        boundaries = [
            (self._paragraph_boundary, "paragraph"),
            (self._sentence_boundary, "sentence"),
            (self._line_boundary, "line"),
            (self._word_boundary, "word")
        ]
        
        for pattern, boundary_type in boundaries:
            if direction == "forward":
                match = pattern.search(text, position)
                if match and match.start() - position < 100:  # Within reasonable distance
                    return match.end()
            else:  # backward
                # Search in reverse
                matches = list(pattern.finditer(text[:position]))
                if matches and position - matches[-1].end() < 100:
                    return matches[-1].end()
        
        return position
    
    def estimate_total_windows(self, text_size: int) -> int:
        """Estimate the total number of windows for progress tracking."""
        if text_size == 0:
            return 0
        
        # Estimate based on average window size and overlap
        avg_window_size = self.config.size
        if self.config.unit == WindowUnit.LINES:
            # Estimate ~80 characters per line
            avg_window_size *= 80
        elif self.config.unit == WindowUnit.TOKENS:
            # Estimate ~4 characters per token
            avg_window_size *= 4
        
        overlap = self.calculate_overlap(avg_window_size)
        effective_step = max(1, avg_window_size - overlap)
        
        return max(1, (text_size + effective_step - 1) // effective_step)
    
    def get_window_at_position(self, text: str, position: int) -> Optional[Window]:
        """Get the window containing the specified position."""
        if position < 0 or position >= len(text):
            return None
        
        # Find which window contains this position
        for window in self.process_text(text):
            if window.position.start <= position < window.position.end:
                return window
        
        return None
    
    def adjust_window_size(self, text: str, start: int, 
                          suggested_size: int) -> Tuple[int, dict]:
        """Dynamically adjust window size based on content density."""
        metadata = {"adjusted": False}
        
        if not self.config.min_window_size and not self.config.max_window_size:
            return suggested_size, metadata
        
        # Analyze content density in the suggested window
        end = min(start + suggested_size, len(text))
        content = text[start:end]
        
        # Calculate density metrics
        line_count = content.count('\n') + 1
        word_count = len(content.split())
        avg_line_length = len(content) / max(1, line_count)
        
        # Adjust based on density
        adjusted_size = suggested_size
        
        # If content is very dense (long lines, many words), reduce window
        if avg_line_length > 100 and self.config.min_window_size:
            adjusted_size = max(self.config.min_window_size, int(suggested_size * 0.8))
            metadata["adjusted"] = True
            metadata["reason"] = "high_density"
        
        # If content is sparse (short lines, few words), increase window
        elif avg_line_length < 40 and word_count < suggested_size / 10:
            if self.config.max_window_size:
                adjusted_size = min(self.config.max_window_size, int(suggested_size * 1.2))
                metadata["adjusted"] = True
                metadata["reason"] = "low_density"
        
        # Check for structural boundaries (e.g., many blank lines)
        blank_lines = content.count('\n\n')
        if blank_lines > 5:
            # Many paragraph breaks, might want smaller windows
            if self.config.min_window_size:
                adjusted_size = max(self.config.min_window_size, int(suggested_size * 0.9))
                metadata["adjusted"] = True
                metadata["reason"] = "many_paragraphs"
        
        return adjusted_size, metadata
    
    def _convert_to_characters(self, text: str, size: int) -> int:
        """Convert size from configured unit to characters."""
        if self.config.unit == WindowUnit.CHARACTERS:
            return size
        elif self.config.unit == WindowUnit.BYTES:
            # Approximate - assumes ASCII/UTF-8
            return size
        elif self.config.unit == WindowUnit.LINES:
            # Count actual lines in text to get average line length
            lines = text.split('\n')[:size]
            return sum(len(line) + 1 for line in lines)  # +1 for newline
        elif self.config.unit == WindowUnit.TOKENS:
            # Rough estimation - would need actual tokenizer
            return size * 4  # Approximate 4 chars per token
        else:
            return size
    
    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count for text."""
        # Simple estimation - would integrate with actual token counter
        # Rough heuristic: ~1 token per 4 characters
        return len(text) // 4
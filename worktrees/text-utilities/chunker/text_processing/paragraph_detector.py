"""
Paragraph boundary detection based on whitespace patterns and text structure.

This module implements paragraph detection using various heuristics including
blank lines, indentation changes, and structural patterns.
"""

import re
from typing import List, Optional, Dict, Any, Tuple
from chunker.interfaces.text_processor import (
    BoundaryDetector, TextBoundary, BoundaryType, TextSegment
)


class ParagraphDetector(BoundaryDetector):
    """
    Detects paragraph boundaries in text using whitespace and structural patterns.
    
    This implementation handles:
    - Multiple blank lines
    - Indentation changes
    - List items and bullet points
    - Block quotes
    - Code blocks
    - Various text formats (Markdown, plain text, etc.)
    """
    
    def __init__(self, language: str = "en", encoding: str = "utf-8",
                 min_paragraph_length: int = 20,
                 require_blank_line: bool = True,
                 detect_indentation: bool = True):
        """
        Initialize the paragraph detector.
        
        Args:
            language: ISO 639-1 language code
            encoding: Text encoding
            min_paragraph_length: Minimum characters for a valid paragraph
            require_blank_line: Whether blank lines are required for paragraph breaks
            detect_indentation: Whether to detect indentation-based paragraphs
        """
        super().__init__(language, encoding)
        self.min_paragraph_length = min_paragraph_length
        self.require_blank_line = require_blank_line
        self.detect_indentation = detect_indentation
        
        # Compile regex patterns
        self._compile_patterns()
    
    def get_boundary_type(self) -> BoundaryType:
        """Return the boundary type for paragraph detection."""
        return BoundaryType.PARAGRAPH
    
    def _compile_patterns(self):
        """Compile regex patterns for paragraph detection."""
        # Pattern for blank lines (one or more)
        self.blank_line_pattern = re.compile(
            r'\n\s*\n',
            re.MULTILINE
        )
        
        # Pattern for multiple blank lines
        self.multiple_blank_pattern = re.compile(
            r'\n\s*\n\s*\n+',
            re.MULTILINE
        )
        
        # Pattern for indented lines (at least 2 spaces or a tab)
        self.indent_pattern = re.compile(
            r'^[ \t]{2,}',
            re.MULTILINE
        )
        
        # Pattern for list items (bullets, numbers, etc.)
        self.list_pattern = re.compile(
            r'^[ \t]*(?:'
            r'[-*+•]|\d+[.)]\s|'        # Bullet points or numbered lists
            r'[a-zA-Z][.)]\s|'           # Lettered lists
            r'[ivxIVX]+[.)]\s'           # Roman numerals
            r')\s*',
            re.MULTILINE
        )
        
        # Pattern for block quotes (Markdown style)
        self.quote_pattern = re.compile(
            r'^[ \t]*>+[ \t]*',
            re.MULTILINE
        )
        
        # Pattern for code blocks (indented or fenced)
        self.code_block_pattern = re.compile(
            r'(?:^```[^\n]*\n.*?\n```|^[ \t]{4,}.*(?:\n[ \t]{4,}.*)*)',
            re.MULTILINE | re.DOTALL
        )
        
        # Pattern for headers (Markdown, reStructuredText, etc.)
        self.header_pattern = re.compile(
            r'^(?:'
            r'#{1,6}\s+.*|'              # Markdown headers
            r'.*\n[=-]{3,}|'             # Underlined headers
            r'\d+\.\s+[A-Z].*'           # Numbered section headers
            r')$',
            re.MULTILINE
        )
        
        # Pattern for horizontal rules
        self.hr_pattern = re.compile(
            r'^[ \t]*'
            r'(?:[-*_][ \t]*){3,}'          # Three or more -, *, or _
            r'[ \t]*$',
            re.MULTILINE
        )
    
    def _get_line_info(self, text: str, pos: int) -> Tuple[int, int, str]:
        """
        Get information about the line containing the given position.
        
        Args:
            text: The full text
            pos: Position in the text
            
        Returns:
            Tuple of (line_start, line_end, line_text)
        """
        # Find start of line
        line_start = pos
        while line_start > 0 and text[line_start - 1] != '\n':
            line_start -= 1
        
        # Find end of line
        line_end = pos
        while line_end < len(text) and text[line_end] != '\n':
            line_end += 1
        
        return line_start, line_end, text[line_start:line_end]
    
    def _is_structural_break(self, text: str, pos: int) -> bool:
        """
        Check if position represents a structural break (header, HR, etc.).
        
        Args:
            text: The full text
            pos: Position to check
            
        Returns:
            True if this is a structural break
        """
        line_start, line_end, line = self._get_line_info(text, pos)
        
        # Check for headers
        if self.header_pattern.match(line):
            return True
        
        # Check for horizontal rules
        if self.hr_pattern.match(line):
            return True
        
        # Check for code block boundaries
        if line.strip().startswith('```'):
            return True
        
        return False
    
    def _calculate_confidence(self, text: str, start: int, end: int,
                            metadata: Dict[str, Any]) -> float:
        """
        Calculate confidence score for a paragraph boundary.
        
        Args:
            text: The full text
            start: Start position of paragraph
            end: End position of paragraph
            metadata: Additional metadata about the boundary
            
        Returns:
            Confidence score between 0.0 and 1.0
        """
        confidence = 0.8  # Base confidence
        
        paragraph = text[start:end].strip()
        
        # Increase confidence for multiple blank lines
        if metadata.get("blank_lines", 0) > 1:
            confidence += 0.1
        
        # Increase confidence for structural breaks
        if metadata.get("structural_break"):
            confidence += 0.1
        
        # Reduce confidence for very short paragraphs
        if len(paragraph) < self.min_paragraph_length:
            confidence -= 0.3
        
        # Increase confidence for well-formed paragraphs
        if paragraph and paragraph[0].isupper() and paragraph[-1] in '.!?':
            confidence += 0.05
        
        # Reduce confidence if it looks like a list continuation
        if metadata.get("list_item") and not metadata.get("blank_lines"):
            confidence -= 0.2
        
        # Ensure confidence is within bounds
        return max(0.0, min(1.0, confidence))
    
    def _detect_specific_boundaries(self, text: str) -> List[TextBoundary]:
        """
        Detect paragraph boundaries in the text.
        
        Args:
            text: The text to analyze
            
        Returns:
            List of detected paragraph boundaries
        """
        boundaries = []
        last_end = 0
        
        # Find all blank line positions
        blank_positions = []
        for match in self.blank_line_pattern.finditer(text):
            blank_positions.append((match.start(), match.end()))
        
        # Add text start and end as boundaries
        blank_positions.insert(0, (-1, 0))
        blank_positions.append((len(text), len(text)))
        
        # Process each potential paragraph
        for i in range(len(blank_positions) - 1):
            start_pos = blank_positions[i][1]
            end_pos = blank_positions[i + 1][0]
            
            # Skip empty segments
            if start_pos >= end_pos:
                continue
            
            paragraph = text[start_pos:end_pos].strip()
            if not paragraph:
                continue
            
            # Calculate actual positions (excluding leading/trailing whitespace)
            actual_start = start_pos
            while actual_start < end_pos and text[actual_start].isspace():
                actual_start += 1
            
            actual_end = end_pos
            while actual_end > actual_start and text[actual_end - 1].isspace():
                actual_end -= 1
            
            # Build metadata
            metadata = {
                "blank_lines": text[blank_positions[i][0]:blank_positions[i][1]].count('\n') - 1
                if i > 0 else 0,
                "structural_break": self._is_structural_break(text, actual_start),
                "list_item": bool(self.list_pattern.match(paragraph)),
                "indented": bool(self.indent_pattern.match(paragraph)),
                "quoted": bool(self.quote_pattern.match(paragraph)),
            }
            
            # Calculate confidence
            confidence = self._calculate_confidence(text, actual_start, actual_end, metadata)
            
            # Create boundary
            boundary = TextBoundary(
                start=actual_start,
                end=actual_end,
                boundary_type=BoundaryType.PARAGRAPH,
                confidence=confidence,
                metadata=metadata
            )
            boundaries.append(boundary)
        
        # If no blank lines found but indentation detection is enabled
        if len(boundaries) <= 1 and self.detect_indentation:
            boundaries = self._detect_by_indentation(text)
        
        return boundaries
    
    def _detect_by_indentation(self, text: str) -> List[TextBoundary]:
        """
        Detect paragraphs based on indentation changes.
        
        Args:
            text: The text to analyze
            
        Returns:
            List of detected boundaries
        """
        boundaries = []
        lines = text.split('\n')
        current_start = 0
        current_indent = None
        
        for i, line in enumerate(lines):
            # Skip empty lines
            if not line.strip():
                continue
            
            # Get indentation level
            indent_match = re.match(r'^(\s*)', line)
            indent_level = len(indent_match.group(1)) if indent_match else 0
            
            # Check if indentation changed significantly
            if current_indent is not None and abs(indent_level - current_indent) >= 2:
                # End current paragraph
                line_start = sum(len(lines[j]) + 1 for j in range(i))
                
                metadata = {
                    "indentation_change": True,
                    "prev_indent": current_indent,
                    "new_indent": indent_level
                }
                
                confidence = self._calculate_confidence(text, current_start, line_start - 1, metadata)
                
                boundary = TextBoundary(
                    start=current_start,
                    end=line_start - 1,
                    boundary_type=BoundaryType.PARAGRAPH,
                    confidence=confidence,
                    metadata=metadata
                )
                boundaries.append(boundary)
                
                current_start = line_start
            
            if current_indent is None or line.strip():
                current_indent = indent_level
        
        # Add final paragraph
        if current_start < len(text):
            metadata = {"final_paragraph": True}
            confidence = self._calculate_confidence(text, current_start, len(text), metadata)
            
            boundaries.append(TextBoundary(
                start=current_start,
                end=len(text),
                boundary_type=BoundaryType.PARAGRAPH,
                confidence=confidence,
                metadata=metadata
            ))
        
        return boundaries
    
    def find_natural_breaks(self, text: str, max_length: int) -> List[int]:
        """
        Find natural paragraph breaks for chunking.
        
        Args:
            text: The text to analyze
            max_length: Maximum chunk length
            
        Returns:
            List of positions representing natural break points
        """
        boundaries = self.detect_boundaries(text)
        breaks = []
        current_length = 0
        
        for boundary in boundaries:
            if current_length + boundary.length > max_length and current_length > 0:
                # Add break at the start of this paragraph
                breaks.append(boundary.start)
                current_length = boundary.length
            else:
                current_length += boundary.length
        
        return breaks
    
    def segment_text(self, text: str) -> List[TextSegment]:
        """
        Segment text into paragraphs.
        
        Args:
            text: The text to segment
            
        Returns:
            List of paragraph segments
        """
        boundaries = self.detect_boundaries(text)
        segments = []
        
        for i, boundary in enumerate(boundaries):
            paragraph_text = text[boundary.start:boundary.end].strip()
            
            # Determine end boundary
            end_boundary = boundaries[i + 1] if i + 1 < len(boundaries) else None
            
            segment = TextSegment(
                text=paragraph_text,
                start_boundary=boundary,
                end_boundary=end_boundary,
                segment_type=BoundaryType.PARAGRAPH
            )
            segments.append(segment)
        
        return segments
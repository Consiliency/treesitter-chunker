"""
Natural break point finder that combines multiple boundary detection methods.

This module implements algorithms to find the best natural break points in text
for chunking, considering sentences, paragraphs, and structural elements.
"""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import IntEnum

from chunker.interfaces.text_processor import (
    TextProcessor, TextBoundary, BoundaryType, TextSegment
)
from .sentence_detector import SentenceBoundaryDetector
from .paragraph_detector import ParagraphDetector


class BreakPriority(IntEnum):
    """Priority levels for different types of breaks."""
    PARAGRAPH = 100
    SECTION = 90
    SENTENCE = 80
    QUOTE = 70
    CODE_BLOCK = 60
    CLAUSE = 50
    WORD = 10


@dataclass
class BreakPoint:
    """
    Represents a potential break point in text.
    
    Attributes:
        position: Character position of the break
        priority: Priority level of this break type
        boundary: The associated text boundary
        score: Calculated score for this break point
    """
    position: int
    priority: BreakPriority
    boundary: Optional[TextBoundary]
    score: float = 0.0
    
    def __lt__(self, other):
        """Compare break points by position for sorting."""
        return self.position < other.position


class NaturalBreakFinder(TextProcessor):
    """
    Finds natural break points in text by combining multiple boundary detection methods.
    
    This implementation:
    - Uses multiple boundary detectors (sentence, paragraph)
    - Prioritizes different break types
    - Considers context and content when scoring breaks
    - Optimizes for semantic coherence in chunks
    """
    
    def __init__(self, language: str = "en", encoding: str = "utf-8",
                 prefer_paragraphs: bool = True,
                 min_chunk_size: int = 100,
                 max_chunk_size: int = 1000):
        """
        Initialize the natural break finder.
        
        Args:
            language: ISO 639-1 language code
            encoding: Text encoding
            prefer_paragraphs: Whether to prefer paragraph breaks over sentences
            min_chunk_size: Minimum desired chunk size
            max_chunk_size: Maximum desired chunk size
        """
        super().__init__(language, encoding)
        self.prefer_paragraphs = prefer_paragraphs
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size
        
        # Initialize boundary detectors
        self.sentence_detector = SentenceBoundaryDetector(language, encoding)
        self.paragraph_detector = ParagraphDetector(language, encoding)
    
    def detect_boundaries(self, text: str) -> List[TextBoundary]:
        """
        Detect all types of boundaries in the text.
        
        Args:
            text: The text to analyze
            
        Returns:
            List of all detected boundaries, sorted by position
        """
        boundaries = []
        
        # Get sentence boundaries
        sentence_boundaries = self.sentence_detector.detect_boundaries(text)
        boundaries.extend(sentence_boundaries)
        
        # Get paragraph boundaries
        paragraph_boundaries = self.paragraph_detector.detect_boundaries(text)
        boundaries.extend(paragraph_boundaries)
        
        # Sort by start position
        boundaries.sort(key=lambda b: b.start)
        
        # Remove duplicates (same start position)
        unique_boundaries = []
        seen_starts = set()
        for boundary in boundaries:
            if boundary.start not in seen_starts:
                unique_boundaries.append(boundary)
                seen_starts.add(boundary.start)
        
        return unique_boundaries
    
    def _get_break_priority(self, boundary_type: BoundaryType) -> BreakPriority:
        """Map boundary type to break priority."""
        priority_map = {
            BoundaryType.PARAGRAPH: BreakPriority.PARAGRAPH,
            BoundaryType.SECTION: BreakPriority.SECTION,
            BoundaryType.SENTENCE: BreakPriority.SENTENCE,
            BoundaryType.QUOTE: BreakPriority.QUOTE,
            BoundaryType.CODE_BLOCK: BreakPriority.CODE_BLOCK,
        }
        return priority_map.get(boundary_type, BreakPriority.WORD)
    
    def _score_break_point(self, text: str, position: int, 
                          boundary: TextBoundary, context_size: int = 50) -> float:
        """
        Calculate a score for a potential break point.
        
        Args:
            text: The full text
            position: Position of the break
            boundary: The boundary at this position
            context_size: Characters to examine before/after break
            
        Returns:
            Score between 0.0 and 1.0
        """
        base_score = boundary.confidence
        
        # Bonus for high-priority boundaries
        priority = self._get_break_priority(boundary.boundary_type)
        priority_bonus = priority / 200.0  # Normalize to 0-0.5 range
        
        # Check context around break
        before_start = max(0, position - context_size)
        before_text = text[before_start:position].strip()
        
        after_end = min(len(text), position + context_size)
        after_text = text[position:after_end].strip()
        
        # Bonus for complete sentences/thoughts before break
        if before_text and before_text[-1] in '.!?':
            base_score += 0.1
        
        # Bonus for capital letter after break
        if after_text and after_text[0].isupper():
            base_score += 0.05
        
        # Penalty for breaking in quotes
        quote_chars = ['"', "'", '"', '"', ''', ''']
        before_quotes = sum(before_text.count(q) for q in quote_chars)
        if before_quotes % 2 != 0:  # Odd number means we're inside quotes
            base_score -= 0.2
        
        # Penalty for breaking after certain words
        avoid_after = ['the', 'a', 'an', 'and', 'or', 'but', 'of', 'in', 'to']
        last_word = before_text.split()[-1].lower() if before_text.split() else ''
        if last_word in avoid_after:
            base_score -= 0.1
        
        # Combine base score with priority bonus
        final_score = base_score + priority_bonus
        
        # Ensure score is within bounds
        return max(0.0, min(1.0, final_score))
    
    def find_natural_breaks(self, text: str, max_length: int) -> List[int]:
        """
        Find optimal natural break points for chunking.
        
        Args:
            text: The text to analyze
            max_length: Maximum chunk length (guideline, not strict)
            
        Returns:
            List of positions representing natural break points
        """
        # Get all boundaries
        boundaries = self.detect_boundaries(text)
        
        # Convert to break points with scores
        break_points = []
        for boundary in boundaries:
            position = boundary.end
            priority = self._get_break_priority(boundary.boundary_type)
            score = self._score_break_point(text, position, boundary)
            
            break_point = BreakPoint(
                position=position,
                priority=priority,
                boundary=boundary,
                score=score
            )
            break_points.append(break_point)
        
        # Sort by position
        break_points.sort()
        
        # Select optimal breaks
        selected_breaks = []
        current_start = 0
        
        while current_start < len(text):
            # Find candidate breaks within range
            min_pos = current_start + self.min_chunk_size
            max_pos = current_start + max_length
            
            candidates = [
                bp for bp in break_points
                if bp.position > current_start and bp.position >= min_pos and bp.position <= max_pos
            ]
            
            if not candidates:
                # No ideal break found, look for any break after min position
                candidates = [
                    bp for bp in break_points
                    if bp.position >= min_pos
                ]
            
            if candidates:
                # Select best candidate based on score and priority
                if self.prefer_paragraphs:
                    # First try to find paragraph breaks
                    para_candidates = [
                        c for c in candidates 
                        if c.priority == BreakPriority.PARAGRAPH
                    ]
                    if para_candidates:
                        candidates = para_candidates
                
                # Choose highest scoring candidate
                best_break = max(candidates, key=lambda bp: (bp.priority, bp.score))
                selected_breaks.append(best_break.position)
                current_start = best_break.position
            else:
                # No breaks found, use max_length
                break_pos = min(current_start + max_length, len(text))
                if break_pos < len(text):
                    selected_breaks.append(break_pos)
                current_start = break_pos
        
        return selected_breaks
    
    def segment_text(self, text: str) -> List[TextSegment]:
        """
        Segment text using natural breaks.
        
        Args:
            text: The text to segment
            
        Returns:
            List of text segments
        """
        # Use max_chunk_size as the target length
        break_positions = self.find_natural_breaks(text, self.max_chunk_size)
        
        segments = []
        start = 0
        
        for i, end in enumerate(break_positions):
            segment_text = text[start:end].strip()
            
            # Create boundaries for this segment
            start_boundary = TextBoundary(
                start=start,
                end=start,
                boundary_type=BoundaryType.SECTION,
                confidence=0.9,
                metadata={"natural_break": True}
            )
            
            end_boundary = TextBoundary(
                start=end,
                end=end,
                boundary_type=BoundaryType.SECTION,
                confidence=0.9,
                metadata={"natural_break": True}
            )
            
            segment = TextSegment(
                text=segment_text,
                start_boundary=start_boundary,
                end_boundary=end_boundary,
                segment_type=BoundaryType.SECTION
            )
            segments.append(segment)
            
            start = end
        
        # Add final segment if needed
        if start < len(text):
            segment_text = text[start:].strip()
            if segment_text:
                start_boundary = TextBoundary(
                    start=start,
                    end=start,
                    boundary_type=BoundaryType.SECTION,
                    confidence=0.9,
                    metadata={"natural_break": True, "final": True}
                )
                
                segment = TextSegment(
                    text=segment_text,
                    start_boundary=start_boundary,
                    end_boundary=None,
                    segment_type=BoundaryType.SECTION
                )
                segments.append(segment)
        
        return segments
    
    def optimize_breaks(self, text: str, target_size: int, 
                       tolerance: float = 0.2) -> List[int]:
        """
        Find break points optimized for a specific target chunk size.
        
        Args:
            text: The text to analyze
            target_size: Target size for each chunk
            tolerance: Acceptable deviation from target (0.2 = 20%)
            
        Returns:
            List of optimized break positions
        """
        min_size = int(target_size * (1 - tolerance))
        max_size = int(target_size * (1 + tolerance))
        
        # Get all potential breaks
        boundaries = self.detect_boundaries(text)
        break_points = []
        
        for boundary in boundaries:
            position = boundary.end
            priority = self._get_break_priority(boundary.boundary_type)
            score = self._score_break_point(text, position, boundary)
            
            break_point = BreakPoint(
                position=position,
                priority=priority,
                boundary=boundary,
                score=score
            )
            break_points.append(break_point)
        
        # Dynamic programming to find optimal breaks
        n = len(text)
        dp = [float('inf')] * (n + 1)
        dp[0] = 0
        parent = [-1] * (n + 1)
        
        for i in range(n):
            if dp[i] == float('inf'):
                continue
            
            # Try each potential break point
            for bp in break_points:
                if bp.position <= i:
                    continue
                if bp.position > i + max_size:
                    break
                
                chunk_size = bp.position - i
                if chunk_size < min_size:
                    continue
                
                # Calculate cost (deviation from target + break quality)
                size_cost = abs(chunk_size - target_size) / target_size
                break_cost = 1.0 - bp.score
                total_cost = size_cost + break_cost * 0.5
                
                if dp[i] + total_cost < dp[bp.position]:
                    dp[bp.position] = dp[i] + total_cost
                    parent[bp.position] = i
        
        # Reconstruct path
        breaks = []
        pos = n
        
        # Find best ending position
        best_end = n
        best_cost = dp[n]
        
        for i in range(max(0, n - max_size), n):
            if dp[i] < best_cost:
                best_cost = dp[i]
                best_end = i
        
        # Trace back to get breaks
        pos = best_end
        while pos > 0 and parent[pos] != -1:
            breaks.append(pos)
            pos = parent[pos]
        
        breaks.reverse()
        return breaks
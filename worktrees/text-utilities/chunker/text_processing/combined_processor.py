"""
Combined text processor that uses multiple detection strategies.

This module provides a comprehensive text processor that combines
sentence and paragraph detection for optimal text chunking.
"""

from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass
import heapq

from ..interfaces.text_processor import (
    TextProcessor, TextBoundary, TextSegment, BoundaryType
)
from .sentence_detector import SentenceBoundaryDetector, SentenceDetectionConfig
from .paragraph_detector import ParagraphDetector, ParagraphDetectionConfig


@dataclass
class BreakPoint:
    """Represents a potential break point in text."""
    position: int
    score: float
    boundary_type: BoundaryType
    metadata: Optional[Dict[str, Any]] = None
    
    def __lt__(self, other):
        """For heap operations - higher score is better."""
        return self.score > other.score


class CombinedTextProcessor(TextProcessor):
    """
    Advanced text processor combining multiple detection strategies.
    
    Features:
    - Combines sentence and paragraph boundary detection
    - Intelligent break point selection based on context
    - Supports chunking with preference hierarchy
    - Optimized for large document processing
    """
    
    def __init__(self, 
                 language: str = "en",
                 sentence_config: Optional[SentenceDetectionConfig] = None,
                 paragraph_config: Optional[ParagraphDetectionConfig] = None):
        """
        Initialize the combined text processor.
        
        Args:
            language: ISO 639-1 language code
            sentence_config: Configuration for sentence detection
            paragraph_config: Configuration for paragraph detection
        """
        super().__init__(language)
        
        # Initialize detectors
        self.sentence_detector = SentenceBoundaryDetector(language, sentence_config)
        self.paragraph_detector = ParagraphDetector(language, paragraph_config)
        
        # Preference weights for different boundary types
        self.boundary_weights = {
            BoundaryType.PARAGRAPH: 1.5,
            BoundaryType.SENTENCE: 1.0,
            BoundaryType.SECTION: 2.0,
            BoundaryType.QUOTE: 0.8,
            BoundaryType.CODE_BLOCK: 1.2
        }
    
    def detect_boundaries(self, text: str) -> List[TextBoundary]:
        """
        Detect all types of boundaries in the text.
        
        Args:
            text: The text to analyze
            
        Returns:
            List of all detected boundaries, sorted by position
        """
        # Collect boundaries from all detectors
        all_boundaries = []
        
        # Get sentence boundaries
        sentence_boundaries = self.sentence_detector.detect_boundaries(text)
        all_boundaries.extend(sentence_boundaries)
        
        # Get paragraph boundaries
        paragraph_boundaries = self.paragraph_detector.detect_boundaries(text)
        all_boundaries.extend(paragraph_boundaries)
        
        # Sort by position
        all_boundaries.sort(key=lambda b: (b.start, b.end))
        
        # Remove duplicates and merge overlapping boundaries
        merged_boundaries = self._merge_boundaries(all_boundaries)
        
        return merged_boundaries
    
    def _merge_boundaries(self, boundaries: List[TextBoundary]) -> List[TextBoundary]:
        """
        Merge overlapping or adjacent boundaries.
        
        Args:
            boundaries: List of boundaries to merge
            
        Returns:
            List of merged boundaries
        """
        if not boundaries:
            return []
        
        merged = []
        current = boundaries[0]
        
        for boundary in boundaries[1:]:
            # Check if boundaries overlap or are adjacent
            if boundary.start <= current.end + 1:
                # Merge boundaries
                if boundary.confidence > current.confidence:
                    # Use the boundary with higher confidence
                    current = boundary
                elif boundary.boundary_type != current.boundary_type:
                    # Different types - create a composite
                    current = TextBoundary(
                        start=min(current.start, boundary.start),
                        end=max(current.end, boundary.end),
                        boundary_type=self._get_dominant_type(current, boundary),
                        confidence=max(current.confidence, boundary.confidence),
                        metadata={
                            "merged": True,
                            "types": [current.boundary_type.value, boundary.boundary_type.value]
                        }
                    )
            else:
                # No overlap - add current and start new
                merged.append(current)
                current = boundary
        
        # Add the last boundary
        merged.append(current)
        
        return merged
    
    def _get_dominant_type(self, b1: TextBoundary, b2: TextBoundary) -> BoundaryType:
        """Determine the dominant boundary type when merging."""
        weight1 = self.boundary_weights.get(b1.boundary_type, 1.0) * b1.confidence
        weight2 = self.boundary_weights.get(b2.boundary_type, 1.0) * b2.confidence
        
        return b1.boundary_type if weight1 >= weight2 else b2.boundary_type
    
    def find_natural_breaks(self, text: str, max_length: int) -> List[int]:
        """
        Find optimal natural break points for text chunking.
        
        This method uses a sophisticated algorithm that:
        1. Identifies all potential break points
        2. Scores them based on type and context
        3. Selects optimal breaks that respect max_length
        
        Args:
            text: The text to analyze
            max_length: Maximum desired chunk length
            
        Returns:
            List of character positions for natural breaks
        """
        # Get all boundaries
        boundaries = self.detect_boundaries(text)
        
        # Convert to break points with scores
        break_points = []
        for boundary in boundaries:
            score = self._calculate_break_score(boundary, text, max_length)
            break_point = BreakPoint(
                position=boundary.end,
                score=score,
                boundary_type=boundary.boundary_type,
                metadata=boundary.metadata
            )
            break_points.append(break_point)
        
        # Select optimal breaks
        breaks = self._select_optimal_breaks(break_points, text, max_length)
        
        return breaks
    
    def _calculate_break_score(self, boundary: TextBoundary, 
                             text: str, max_length: int) -> float:
        """
        Calculate a score for a potential break point.
        
        Factors considered:
        - Boundary type preference
        - Confidence score
        - Position relative to ideal chunk size
        - Context (e.g., avoiding breaks in quotes)
        
        Args:
            boundary: The boundary to score
            text: The full text
            max_length: Maximum chunk length
            
        Returns:
            Score between 0.0 and 1.0
        """
        # Base score from confidence
        score = boundary.confidence
        
        # Apply boundary type weight
        type_weight = self.boundary_weights.get(boundary.boundary_type, 1.0)
        score *= type_weight
        
        # Penalize breaks that are too close to the start
        if boundary.end < max_length * 0.3:
            score *= 0.7
        
        # Bonus for paragraph boundaries
        if boundary.boundary_type == BoundaryType.PARAGRAPH:
            score *= 1.2
        
        # Check for special contexts
        if boundary.metadata:
            # Bonus for high-confidence structural elements
            if boundary.metadata.get("type") in ["header", "horizontal_rule"]:
                score *= 1.3
            # Penalty for breaks inside quotes or code
            if boundary.metadata.get("inside_quote") or boundary.metadata.get("inside_code"):
                score *= 0.5
        
        # Normalize score
        return min(max(score, 0.0), 1.0)
    
    def _select_optimal_breaks(self, break_points: List[BreakPoint],
                             text: str, max_length: int) -> List[int]:
        """
        Select optimal break points using dynamic programming.
        
        Args:
            break_points: List of potential break points
            text: The full text
            max_length: Maximum chunk length
            
        Returns:
            List of selected break positions
        """
        if not break_points:
            return []
        
        # Sort break points by position
        break_points.sort(key=lambda bp: bp.position)
        
        # Simple greedy algorithm with look-ahead
        selected_breaks = []
        current_pos = 0
        
        while current_pos < len(text):
            # Find all break points within the max_length window
            window_end = min(current_pos + max_length, len(text))
            candidates = [
                bp for bp in break_points
                if current_pos < bp.position <= window_end
            ]
            
            if not candidates:
                # No break points in window - use max_length
                if current_pos + max_length < len(text):
                    selected_breaks.append(current_pos + max_length)
                    current_pos += max_length
                else:
                    break
            else:
                # Select the best break point
                # Prefer breaks closer to the ideal size (70-90% of max_length)
                ideal_pos = current_pos + int(max_length * 0.8)
                
                best_break = max(
                    candidates,
                    key=lambda bp: bp.score - abs(bp.position - ideal_pos) / max_length * 0.3
                )
                
                selected_breaks.append(best_break.position)
                current_pos = best_break.position
        
        return selected_breaks
    
    def segment_text(self, text: str) -> List[TextSegment]:
        """
        Segment text into hierarchical units (paragraphs containing sentences).
        
        Args:
            text: The text to segment
            
        Returns:
            List of text segments with nested structure
        """
        # Get paragraph segments
        paragraph_segments = self.paragraph_detector.segment_text(text)
        
        # For each paragraph, detect sentences within it
        enhanced_segments = []
        
        for para_segment in paragraph_segments:
            # Detect sentences within this paragraph
            para_text = para_segment.text
            sentence_boundaries = self.sentence_detector.detect_boundaries(para_text)
            
            # Adjust sentence boundary positions to account for paragraph offset
            para_start = para_segment.start
            for boundary in sentence_boundaries:
                boundary.start += para_start
                boundary.end += para_start
            
            # Add sentence information to paragraph metadata
            if para_segment.start_boundary.metadata is None:
                para_segment.start_boundary.metadata = {}
            
            para_segment.start_boundary.metadata["sentence_count"] = len(sentence_boundaries)
            para_segment.start_boundary.metadata["sentence_boundaries"] = [
                {"start": b.start, "end": b.end, "confidence": b.confidence}
                for b in sentence_boundaries
            ]
            
            enhanced_segments.append(para_segment)
        
        return enhanced_segments
    
    def chunk_text(self, text: str, 
                   min_chunk_size: int = 100,
                   max_chunk_size: int = 1000,
                   overlap: int = 0) -> List[str]:
        """
        Chunk text into optimal segments.
        
        Args:
            text: The text to chunk
            min_chunk_size: Minimum chunk size
            max_chunk_size: Maximum chunk size
            overlap: Number of characters to overlap between chunks
            
        Returns:
            List of text chunks
        """
        # Find natural break points
        breaks = self.find_natural_breaks(text, max_chunk_size)
        
        # Create chunks
        chunks = []
        start = 0
        
        for break_pos in breaks:
            # Ensure minimum chunk size
            if break_pos - start >= min_chunk_size:
                chunk_text = text[start:break_pos]
                chunks.append(chunk_text.strip())
                
                # Move start position with overlap
                start = break_pos - overlap if overlap > 0 else break_pos
            
        # Add final chunk if needed
        if start < len(text):
            final_chunk = text[start:].strip()
            if final_chunk and len(final_chunk) >= min_chunk_size:
                chunks.append(final_chunk)
            elif chunks and final_chunk:
                # Append to last chunk if too small
                chunks[-1] += " " + final_chunk
        
        return chunks
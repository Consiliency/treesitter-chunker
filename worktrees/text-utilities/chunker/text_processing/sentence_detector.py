"""
Sentence boundary detection implementation with support for multiple languages.

This module implements sophisticated sentence boundary detection using regex patterns,
abbreviation handling, and optional NLTK integration for improved accuracy.
"""

import re
import unicodedata
from typing import List, Set, Optional, Dict, Any
from chunker.interfaces.text_processor import (
    BoundaryDetector, TextBoundary, BoundaryType, TextSegment
)

# Try to import NLTK for enhanced sentence detection
try:
    import nltk
    from nltk.tokenize import punkt
    NLTK_AVAILABLE = True
except ImportError:
    NLTK_AVAILABLE = False


class SentenceBoundaryDetector(BoundaryDetector):
    """
    Detects sentence boundaries in text using regex patterns and heuristics.
    
    This implementation handles:
    - Multiple sentence terminators (. ! ? etc.)
    - Abbreviations and acronyms
    - Quotes and parentheses
    - Multi-byte Unicode characters
    - Optional NLTK integration for improved accuracy
    """
    
    # Common abbreviations by language
    ABBREVIATIONS = {
        "en": {
            # Titles
            "Mr", "Mrs", "Ms", "Dr", "Prof", "Sr", "Jr",
            # Academic
            "Ph.D", "M.D", "B.A", "M.A", "B.S", "M.S",
            # Common
            "Inc", "Ltd", "Co", "Corp", "vs", "etc", "cf", "eg", "e.g", "i.e",
            # Time
            "Jan", "Feb", "Mar", "Apr", "Jun", "Jul", "Aug", "Sep", "Sept",
            "Oct", "Nov", "Dec", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun",
            # Measurements
            "ft", "in", "cm", "mm", "km", "mi", "oz", "lb", "kg", "mph", "kph",
            # Other
            "St", "Ave", "Rd", "Blvd", "no", "No", "pg", "p", "pp", "vol", "Vol",
        },
        "es": {
            "Sr", "Sra", "Srta", "Dr", "Dra", "Prof", "Lic",
            "Av", "Calle", "núm", "pág", "pp", "etc", "Ud", "Uds",
        },
        "fr": {
            "M", "Mme", "Mlle", "Dr", "Prof",
            "av", "bd", "etc", "p", "pp", "vol",
        },
        "de": {
            "Herr", "Frau", "Dr", "Prof",
            "Nr", "Str", "bzw", "usw", "z.B", "d.h",
        },
    }
    
    # Sentence ending punctuation by script/language
    SENTENCE_ENDINGS = {
        "default": r"[.!?]",
        "zh": r"[。！？]",  # Chinese
        "ja": r"[。！？]",  # Japanese
        "ko": r"[.!?。]",   # Korean
        "ar": r"[.!?؟]",   # Arabic
        "hi": r"[।.!?]",   # Hindi
    }
    
    def __init__(self, language: str = "en", encoding: str = "utf-8",
                 use_nltk: bool = True, custom_abbreviations: Optional[Set[str]] = None):
        """
        Initialize the sentence boundary detector.
        
        Args:
            language: ISO 639-1 language code
            encoding: Text encoding
            use_nltk: Whether to use NLTK if available
            custom_abbreviations: Additional abbreviations to recognize
        """
        super().__init__(language, encoding)
        self.use_nltk = use_nltk and NLTK_AVAILABLE
        
        # Initialize abbreviations
        self.abbreviations = self.ABBREVIATIONS.get(language, set()).copy()
        if custom_abbreviations:
            self.abbreviations.update(custom_abbreviations)
        
        # Compile regex patterns
        self._compile_patterns()
        
        # Initialize NLTK tokenizer if available
        self.nltk_tokenizer = None
        if self.use_nltk:
            try:
                self.nltk_tokenizer = punkt.PunktSentenceTokenizer()
            except LookupError:
                # NLTK data not downloaded
                self.use_nltk = False
    
    def get_boundary_type(self) -> BoundaryType:
        """Return the boundary type for sentence detection."""
        return BoundaryType.SENTENCE
    
    def _compile_patterns(self):
        """Compile regex patterns for sentence detection."""
        # Get sentence ending pattern for language
        ending_pattern = self.SENTENCE_ENDINGS.get(
            self.language, 
            self.SENTENCE_ENDINGS["default"]
        )
        
        # Pattern for sentence boundaries with lookahead/lookbehind
        # Handles: period followed by space and capital letter, quotes, etc.
        # For Chinese/Japanese, no space required after punctuation
        if self.language in ["zh", "ja", "ko"]:
            self.sentence_pattern = re.compile(
                rf"({ending_pattern})"          # Sentence ending punctuation
                rf"(?:['\"\)])*",               # Optional closing quotes/parens
                re.UNICODE | re.MULTILINE
            )
        else:
            self.sentence_pattern = re.compile(
                rf"({ending_pattern})"          # Sentence ending punctuation
                rf"(?:['\"\)])*"                 # Optional closing quotes/parens
                rf"(?=\s+[A-Z\u0080-\uFFFF]|$)",  # Followed by space + capital or EOF
                re.UNICODE | re.MULTILINE
            )
        
        # Pattern for abbreviations (word followed by period)
        self.abbrev_pattern = re.compile(
            r"\b([A-Za-z]+\.)",
            re.UNICODE
        )
        
        # Pattern for numbers with decimals
        self.decimal_pattern = re.compile(
            r"\d+\.\d+",
            re.UNICODE
        )
        
        # Pattern for ellipsis
        self.ellipsis_pattern = re.compile(
            r"\.{2,}",
            re.UNICODE
        )
        
        # Pattern for URLs and email addresses
        self.url_email_pattern = re.compile(
            r"(?:https?://|www\.|[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})",
            re.IGNORECASE
        )
    
    def _is_abbreviation(self, text: str, pos: int) -> bool:
        """
        Check if a period at position is part of an abbreviation.
        
        Args:
            text: The full text
            pos: Position of the period
            
        Returns:
            True if the period is part of an abbreviation
        """
        # Look backwards to find the start of the word
        start = pos
        while start > 0 and text[start - 1].isalnum():
            start -= 1
        
        word = text[start:pos]
        
        # Check against known abbreviations
        if word in self.abbreviations:
            return True
        
        # Check for single letter followed by period (initials)
        if len(word) == 1 and word.isupper():
            return True
        
        # Check for patterns like U.S.A, i.e., etc.
        if pos + 1 < len(text) and text[pos + 1] in '.':
            return True
        
        return False
    
    def _calculate_confidence(self, text: str, start: int, end: int) -> float:
        """
        Calculate confidence score for a sentence boundary.
        
        Args:
            text: The full text
            start: Start position of sentence
            end: End position of sentence
            
        Returns:
            Confidence score between 0.0 and 1.0
        """
        confidence = 0.9  # Base confidence
        
        sentence = text[start:end].strip()
        
        # Reduce confidence for very short sentences
        if len(sentence) < 10:
            confidence -= 0.2
        
        # Reduce confidence if sentence starts with lowercase
        if sentence and sentence[0].islower():
            confidence -= 0.1
        
        # Increase confidence for standard punctuation
        if sentence and sentence[-1] in '.!?':
            confidence += 0.05
        
        # Reduce confidence if ends with abbreviation
        words = sentence.split()
        if words and words[-1] in self.abbreviations:
            confidence -= 0.2
        
        # Ensure confidence is within bounds
        return max(0.0, min(1.0, confidence))
    
    def _detect_specific_boundaries(self, text: str) -> List[TextBoundary]:
        """
        Detect sentence boundaries in the text.
        
        Args:
            text: The text to analyze
            
        Returns:
            List of detected sentence boundaries
        """
        boundaries = []
        
        # Use NLTK if available and requested
        if self.use_nltk and self.nltk_tokenizer:
            return self._detect_with_nltk(text)
        
        # Otherwise use regex-based detection
        return self._detect_with_regex(text)
    
    def _detect_with_regex(self, text: str) -> List[TextBoundary]:
        """Detect sentences using regex patterns and heuristics."""
        boundaries = []
        last_end = 0
        
        # Find all potential sentence endings
        for match in self.sentence_pattern.finditer(text):
            end_pos = match.end()
            
            # For non-Asian languages, apply additional heuristics
            if self.language not in ["zh", "ja", "ko"]:
                # Skip if this is a decimal number
                if self.decimal_pattern.match(text[max(0, end_pos - 5):end_pos + 2]):
                    continue
                
                # Skip if this is an abbreviation
                if self._is_abbreviation(text, match.start()):
                    continue
                
                # Skip if inside a URL or email
                url_check_start = max(0, match.start() - 50)
                url_check_end = min(len(text), match.end() + 50)
                if self.url_email_pattern.search(text[url_check_start:url_check_end]):
                    continue
            
            # Calculate confidence
            confidence = self._calculate_confidence(text, last_end, end_pos)
            
            # Create boundary
            boundary = TextBoundary(
                start=last_end,
                end=end_pos,
                boundary_type=BoundaryType.SENTENCE,
                confidence=confidence,
                metadata={
                    "punctuation": match.group(1),
                    "method": "regex"
                }
            )
            boundaries.append(boundary)
            last_end = end_pos
        
        # Add final boundary if there's remaining text
        if last_end < len(text) and text[last_end:].strip():
            boundaries.append(TextBoundary(
                start=last_end,
                end=len(text),
                boundary_type=BoundaryType.SENTENCE,
                confidence=0.7,  # Lower confidence for missing punctuation
                metadata={
                    "punctuation": None,
                    "method": "regex",
                    "incomplete": True
                }
            ))
        
        return boundaries
    
    def _detect_with_nltk(self, text: str) -> List[TextBoundary]:
        """Detect sentences using NLTK tokenizer."""
        boundaries = []
        
        try:
            # Get sentence spans from NLTK
            spans = list(self.nltk_tokenizer.span_tokenize(text))
            
            for start, end in spans:
                # Extract sentence for confidence calculation
                sentence = text[start:end]
                confidence = self._calculate_confidence(text, start, end)
                
                # Determine ending punctuation
                punctuation = None
                if sentence:
                    last_char = sentence.rstrip()[-1]
                    if last_char in '.!?。！？।؟':
                        punctuation = last_char
                
                boundary = TextBoundary(
                    start=start,
                    end=end,
                    boundary_type=BoundaryType.SENTENCE,
                    confidence=confidence,
                    metadata={
                        "punctuation": punctuation,
                        "method": "nltk"
                    }
                )
                boundaries.append(boundary)
                
        except Exception:
            # Fallback to regex if NLTK fails
            return self._detect_with_regex(text)
        
        return boundaries
    
    def find_natural_breaks(self, text: str, max_length: int) -> List[int]:
        """
        Find natural sentence breaks for chunking.
        
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
                # Add break at the start of this sentence
                breaks.append(boundary.start)
                current_length = boundary.length
            else:
                current_length += boundary.length
        
        return breaks
    
    def segment_text(self, text: str) -> List[TextSegment]:
        """
        Segment text into sentences.
        
        Args:
            text: The text to segment
            
        Returns:
            List of sentence segments
        """
        boundaries = self.detect_boundaries(text)
        segments = []
        
        for i, boundary in enumerate(boundaries):
            sentence_text = text[boundary.start:boundary.end].strip()
            
            # Determine end boundary (start of next sentence or None)
            end_boundary = boundaries[i + 1] if i + 1 < len(boundaries) else None
            
            segment = TextSegment(
                text=sentence_text,
                start_boundary=boundary,
                end_boundary=end_boundary,
                segment_type=BoundaryType.SENTENCE
            )
            segments.append(segment)
        
        return segments
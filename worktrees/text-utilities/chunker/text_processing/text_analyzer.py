"""
Comprehensive text analyzer that combines multiple processing capabilities.

This module provides a unified interface for text analysis, including
boundary detection, statistics, and language identification.
"""

import re
import unicodedata
from typing import List, Dict, Any, Optional, Set, Tuple
from collections import Counter
from dataclasses import dataclass

from chunker.interfaces.text_processor import (
    TextProcessor, TextBoundary, BoundaryType, TextSegment
)
from .sentence_detector import SentenceBoundaryDetector
from .paragraph_detector import ParagraphDetector
from .break_finder import NaturalBreakFinder


@dataclass
class TextStatistics:
    """
    Statistics about analyzed text.
    
    Attributes:
        char_count: Total number of characters
        word_count: Total number of words
        sentence_count: Number of sentences
        paragraph_count: Number of paragraphs
        avg_word_length: Average word length
        avg_sentence_length: Average sentence length (in words)
        avg_paragraph_length: Average paragraph length (in sentences)
        vocabulary_size: Number of unique words
        readability_score: Estimated readability score
    """
    char_count: int
    word_count: int
    sentence_count: int
    paragraph_count: int
    avg_word_length: float
    avg_sentence_length: float
    avg_paragraph_length: float
    vocabulary_size: int
    readability_score: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert statistics to dictionary."""
        return {
            "char_count": self.char_count,
            "word_count": self.word_count,
            "sentence_count": self.sentence_count,
            "paragraph_count": self.paragraph_count,
            "avg_word_length": round(self.avg_word_length, 2),
            "avg_sentence_length": round(self.avg_sentence_length, 2),
            "avg_paragraph_length": round(self.avg_paragraph_length, 2),
            "vocabulary_size": self.vocabulary_size,
            "readability_score": round(self.readability_score, 2)
        }


class TextAnalyzer(TextProcessor):
    """
    Comprehensive text analyzer with multiple capabilities.
    
    This implementation provides:
    - Complete text statistics
    - Language detection (basic)
    - Encoding validation
    - Boundary detection aggregation
    - Readability analysis
    - Text complexity metrics
    """
    
    # Common words by language for basic detection
    LANGUAGE_INDICATORS = {
        "en": {"the", "and", "to", "of", "a", "in", "is", "it", "that", "for"},
        "es": {"el", "la", "de", "que", "y", "a", "en", "un", "es", "por"},
        "fr": {"le", "de", "et", "à", "la", "que", "les", "un", "est", "pour"},
        "de": {"der", "die", "und", "in", "das", "zu", "ist", "ein", "mit", "auf"},
        "it": {"il", "di", "e", "la", "che", "a", "un", "in", "per", "è"},
        "pt": {"o", "de", "e", "a", "que", "do", "da", "em", "um", "para"},
    }
    
    def __init__(self, language: str = "auto", encoding: str = "utf-8"):
        """
        Initialize the text analyzer.
        
        Args:
            language: ISO 639-1 language code or "auto" for detection
            encoding: Text encoding
        """
        # Use English as default if auto-detection is requested
        super().__init__("en" if language == "auto" else language, encoding)
        self.auto_detect_language = (language == "auto")
        
        # Initialize component analyzers
        self.sentence_detector = None
        self.paragraph_detector = None
        self.break_finder = None
        
        # Cache for detected language
        self._detected_language = None
    
    def _init_components(self, language: str):
        """Initialize component analyzers with detected language."""
        self.sentence_detector = SentenceBoundaryDetector(language, self.encoding)
        self.paragraph_detector = ParagraphDetector(language, self.encoding)
        self.break_finder = NaturalBreakFinder(language, self.encoding)
    
    def detect_language(self, text: str) -> str:
        """
        Detect the language of the text (basic implementation).
        
        Args:
            text: The text to analyze
            
        Returns:
            ISO 639-1 language code
        """
        if self._detected_language:
            return self._detected_language
        
        # Extract words
        words = re.findall(r'\b\w+\b', text.lower())
        if not words:
            self._detected_language = "en"
            return "en"
        
        # Count word frequencies
        word_freq = {}
        for word in words[:1000]:  # Use first 1000 words
            word_freq[word] = word_freq.get(word, 0) + 1
        
        # Calculate weighted scores for each language
        scores = {}
        for lang, indicators in self.LANGUAGE_INDICATORS.items():
            score = 0
            for indicator in indicators:
                if indicator in word_freq:
                    # Weight by frequency
                    score += word_freq[indicator]
            scores[lang] = score
        
        # Get language with highest score
        if scores:
            detected = max(scores, key=scores.get)
            # Require minimum score to avoid false positives
            if scores[detected] >= 2:
                self._detected_language = detected
                return detected
        
        # Default to English
        self._detected_language = "en"
        return "en"
    
    def validate_encoding(self, text: str) -> Dict[str, Any]:
        """
        Validate text encoding and detect issues.
        
        Args:
            text: The text to validate
            
        Returns:
            Dictionary with encoding information
        """
        issues = []
        
        # Check for common encoding issues
        if '\ufffd' in text:
            issues.append("Replacement characters found (possible encoding error)")
        
        # Check for mixed encodings
        try:
            text.encode(self.encoding)
        except UnicodeEncodeError as e:
            issues.append(f"Cannot encode to {self.encoding}: {e}")
        
        # Detect special characters
        special_chars = set()
        for char in text:
            category = unicodedata.category(char)
            if category.startswith('C'):  # Control characters
                special_chars.add(repr(char))
        
        return {
            "encoding": self.encoding,
            "valid": len(issues) == 0,
            "issues": issues,
            "special_characters": list(special_chars),
            "has_bom": text.startswith('\ufeff'),
            "line_endings": self._detect_line_endings(text)
        }
    
    def _detect_line_endings(self, text: str) -> str:
        """Detect the type of line endings in text."""
        if '\r\n' in text:
            return "CRLF (Windows)"
        elif '\r' in text:
            return "CR (Classic Mac)"
        elif '\n' in text:
            return "LF (Unix/Linux/Mac)"
        else:
            return "None"
    
    def calculate_statistics(self, text: str) -> TextStatistics:
        """
        Calculate comprehensive text statistics.
        
        Args:
            text: The text to analyze
            
        Returns:
            TextStatistics object with metrics
        """
        # Initialize components if needed
        if not self.sentence_detector:
            language = self.detect_language(text) if self.auto_detect_language else self.language
            self._init_components(language)
        
        # Basic counts
        char_count = len(text)
        words = re.findall(r'\b\w+\b', text)
        word_count = len(words)
        
        # Handle empty text
        if not text.strip():
            return TextStatistics(
                char_count=0,
                word_count=0,
                sentence_count=0,
                paragraph_count=0,
                avg_word_length=0.0,
                avg_sentence_length=0.0,
                avg_paragraph_length=0.0,
                vocabulary_size=0,
                readability_score=0.0
            )
        
        # Get boundaries
        sentences = self.sentence_detector.detect_boundaries(text)
        paragraphs = self.paragraph_detector.detect_boundaries(text)
        
        sentence_count = len(sentences)
        paragraph_count = len(paragraphs)
        
        # Calculate averages
        avg_word_length = sum(len(w) for w in words) / word_count if word_count > 0 else 0
        avg_sentence_length = word_count / sentence_count if sentence_count > 0 else 0
        avg_paragraph_length = sentence_count / paragraph_count if paragraph_count > 0 else 0
        
        # Vocabulary analysis
        vocabulary_size = len(set(w.lower() for w in words))
        
        # Calculate readability (simplified Flesch Reading Ease)
        syllable_count = self._estimate_syllables(words)
        if sentence_count > 0 and word_count > 0:
            readability_score = 206.835 - 1.015 * (word_count / sentence_count) - 84.6 * (syllable_count / word_count)
            readability_score = max(0, min(100, readability_score))  # Clamp to 0-100
        else:
            readability_score = 0.0
        
        return TextStatistics(
            char_count=char_count,
            word_count=word_count,
            sentence_count=sentence_count,
            paragraph_count=paragraph_count,
            avg_word_length=avg_word_length,
            avg_sentence_length=avg_sentence_length,
            avg_paragraph_length=avg_paragraph_length,
            vocabulary_size=vocabulary_size,
            readability_score=readability_score
        )
    
    def _estimate_syllables(self, words: List[str]) -> int:
        """Estimate syllable count for readability calculation."""
        total = 0
        for word in words:
            # Simple syllable estimation
            word = word.lower()
            count = 0
            vowels = "aeiouy"
            previous_was_vowel = False
            
            for char in word:
                is_vowel = char in vowels
                if is_vowel and not previous_was_vowel:
                    count += 1
                previous_was_vowel = is_vowel
            
            # Adjust for silent e
            if word.endswith('e'):
                count -= 1
            
            # Ensure at least 1 syllable
            if count == 0:
                count = 1
            
            total += count
        
        return total
    
    def detect_boundaries(self, text: str) -> List[TextBoundary]:
        """
        Detect all types of boundaries in the text.
        
        Args:
            text: The text to analyze
            
        Returns:
            List of all detected boundaries
        """
        # Auto-detect language if needed
        if self.auto_detect_language:
            language = self.detect_language(text)
            self._init_components(language)
        elif not self.sentence_detector:
            self._init_components(self.language)
        
        # Aggregate boundaries from all detectors
        return self.break_finder.detect_boundaries(text)
    
    def find_natural_breaks(self, text: str, max_length: int) -> List[int]:
        """
        Find natural break points using the break finder.
        
        Args:
            text: The text to analyze
            max_length: Maximum chunk length
            
        Returns:
            List of break positions
        """
        # Auto-detect language if needed
        if self.auto_detect_language:
            language = self.detect_language(text)
            self._init_components(language)
        elif not self.break_finder:
            self._init_components(self.language)
        
        return self.break_finder.find_natural_breaks(text, max_length)
    
    def segment_text(self, text: str) -> List[TextSegment]:
        """
        Segment text using natural break finder.
        
        Args:
            text: The text to segment
            
        Returns:
            List of text segments
        """
        # Auto-detect language if needed
        if self.auto_detect_language:
            language = self.detect_language(text)
            self._init_components(language)
        elif not self.break_finder:
            self._init_components(self.language)
        
        return self.break_finder.segment_text(text)
    
    def analyze_complexity(self, text: str) -> Dict[str, Any]:
        """
        Analyze text complexity metrics.
        
        Args:
            text: The text to analyze
            
        Returns:
            Dictionary with complexity metrics
        """
        stats = self.calculate_statistics(text)
        words = re.findall(r'\b\w+\b', text.lower())
        
        # Word frequency analysis
        word_freq = Counter(words)
        unique_words = len(word_freq)
        
        # Calculate lexical diversity
        lexical_diversity = unique_words / len(words) if words else 0
        
        # Find complex words (3+ syllables)
        complex_words = [w for w in set(words) if self._count_syllables(w) >= 3]
        complex_word_ratio = len(complex_words) / unique_words if unique_words > 0 else 0
        
        # Sentence complexity
        sentences = self.sentence_detector.segment_text(text)
        sentence_lengths = [len(s.text.split()) for s in sentences]
        
        return {
            "readability_score": stats.readability_score,
            "lexical_diversity": round(lexical_diversity, 3),
            "complex_word_ratio": round(complex_word_ratio, 3),
            "avg_sentence_length": stats.avg_sentence_length,
            "sentence_length_variance": round(
                self._variance(sentence_lengths), 2
            ) if sentence_lengths else 0,
            "most_common_words": word_freq.most_common(10),
            "complexity_level": self._get_complexity_level(stats.readability_score)
        }
    
    def _count_syllables(self, word: str) -> int:
        """Count syllables in a word."""
        word = word.lower()
        count = 0
        vowels = "aeiouy"
        previous_was_vowel = False
        
        for char in word:
            is_vowel = char in vowels
            if is_vowel and not previous_was_vowel:
                count += 1
            previous_was_vowel = is_vowel
        
        if word.endswith('e'):
            count -= 1
        
        return max(1, count)
    
    def _variance(self, values: List[float]) -> float:
        """Calculate variance of a list of values."""
        if not values:
            return 0.0
        mean = sum(values) / len(values)
        return sum((x - mean) ** 2 for x in values) / len(values)
    
    def _get_complexity_level(self, readability_score: float) -> str:
        """Get complexity level from readability score."""
        if readability_score >= 90:
            return "Very Easy"
        elif readability_score >= 80:
            return "Easy"
        elif readability_score >= 70:
            return "Fairly Easy"
        elif readability_score >= 60:
            return "Standard"
        elif readability_score >= 50:
            return "Fairly Difficult"
        elif readability_score >= 30:
            return "Difficult"
        else:
            return "Very Difficult"
    
    def generate_summary(self, text: str) -> Dict[str, Any]:
        """
        Generate a comprehensive summary of text analysis.
        
        Args:
            text: The text to analyze
            
        Returns:
            Dictionary with complete analysis results
        """
        # Detect language if needed
        language = self.detect_language(text) if self.auto_detect_language else self.language
        if not self.sentence_detector:
            self._init_components(language)
        
        # Perform all analyses
        statistics = self.calculate_statistics(text)
        encoding_info = self.validate_encoding(text)
        complexity = self.analyze_complexity(text)
        boundaries = self.detect_boundaries(text)
        
        # Count boundary types
        boundary_counts = Counter(b.boundary_type for b in boundaries)
        
        return {
            "language": language,
            "encoding": encoding_info,
            "statistics": statistics.to_dict(),
            "complexity": complexity,
            "boundary_summary": {
                "total_boundaries": len(boundaries),
                "by_type": {
                    bt.value: count for bt, count in boundary_counts.items()
                }
            },
            "recommendations": self._generate_recommendations(statistics, complexity)
        }
    
    def _generate_recommendations(self, stats: TextStatistics, 
                                complexity: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on analysis."""
        recommendations = []
        
        # Readability recommendations
        if stats.readability_score < 50:
            recommendations.append(
                "Consider simplifying sentences - current readability is difficult"
            )
        
        # Sentence length recommendations
        if stats.avg_sentence_length > 25:
            recommendations.append(
                "Consider breaking up long sentences for better readability"
            )
        
        # Paragraph recommendations
        if stats.avg_paragraph_length > 7:
            recommendations.append(
                "Consider shorter paragraphs for better structure"
            )
        
        # Vocabulary recommendations
        if complexity["lexical_diversity"] < 0.4:
            recommendations.append(
                "Vocabulary is repetitive - consider using more varied words"
            )
        
        return recommendations
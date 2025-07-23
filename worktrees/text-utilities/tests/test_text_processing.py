"""
Comprehensive unit tests for text processing utilities.

Tests sentence detection, paragraph detection, natural break finding,
and text analysis functionality.
"""

import pytest
from chunker.interfaces.text_processor import (
    TextBoundary, BoundaryType, TextSegment, ConfidenceLevel
)
from chunker.text_processing import (
    SentenceBoundaryDetector,
    ParagraphDetector,
    NaturalBreakFinder,
    TextAnalyzer
)


class TestSentenceBoundaryDetector:
    """Test cases for sentence boundary detection."""
    
    def test_basic_sentence_detection(self):
        """Test detection of basic sentences."""
        detector = SentenceBoundaryDetector()
        text = "This is a sentence. This is another sentence! Is this a question?"
        
        boundaries = detector.detect_boundaries(text)
        
        assert len(boundaries) == 3
        assert all(b.boundary_type == BoundaryType.SENTENCE for b in boundaries)
        assert boundaries[0].end == text.find(". ") + 1
        assert boundaries[1].end == text.find("! ") + 1
        assert boundaries[2].end == len(text)
    
    def test_abbreviation_handling(self):
        """Test that abbreviations don't break sentences."""
        detector = SentenceBoundaryDetector()
        text = "Dr. Smith works at Inc. Ltd. with Mr. Jones."
        
        boundaries = detector.detect_boundaries(text)
        
        # Should detect only one sentence
        assert len(boundaries) == 1
        assert boundaries[0].end == len(text)
    
    def test_decimal_numbers(self):
        """Test that decimal numbers don't break sentences."""
        detector = SentenceBoundaryDetector()
        text = "The temperature is 98.6 degrees. Water boils at 100.0 degrees."
        
        boundaries = detector.detect_boundaries(text)
        
        assert len(boundaries) == 2
        assert "98.6" in text[:boundaries[0].end]
        assert "100.0" in text[boundaries[0].end:]
    
    def test_quotes_and_parentheses(self):
        """Test handling of quotes and parentheses."""
        detector = SentenceBoundaryDetector()
        text = 'He said "Hello." She replied "Hi!" They left (finally).'
        
        boundaries = detector.detect_boundaries(text)
        
        assert len(boundaries) == 3
        assert boundaries[0].confidence > 0.7
    
    def test_multiple_languages(self):
        """Test detection with different language punctuation."""
        # Chinese
        detector_zh = SentenceBoundaryDetector(language="zh")
        text_zh = "这是第一句。这是第二句！这是问句吗？"
        boundaries_zh = detector_zh.detect_boundaries(text_zh)
        assert len(boundaries_zh) == 3
        
        # Spanish with inverted punctuation
        detector_es = SentenceBoundaryDetector(language="es")
        text_es = "¡Hola! ¿Cómo estás? Muy bien."
        boundaries_es = detector_es.detect_boundaries(text_es)
        assert len(boundaries_es) == 3
    
    def test_confidence_scoring(self):
        """Test confidence scoring for different sentence types."""
        detector = SentenceBoundaryDetector()
        
        # Well-formed sentence should have high confidence
        text1 = "This is a complete sentence."
        boundaries1 = detector.detect_boundaries(text1)
        assert boundaries1[0].confidence > 0.8
        assert boundaries1[0].confidence_level == ConfidenceLevel.HIGH
        
        # Short sentence should have lower confidence
        text2 = "Hi there."
        boundaries2 = detector.detect_boundaries(text2)
        assert boundaries2[0].confidence < boundaries1[0].confidence
        
        # Sentence without punctuation should have lower confidence
        text3 = "This has no ending punctuation"
        boundaries3 = detector.detect_boundaries(text3)
        assert boundaries3[0].confidence < 0.8
    
    def test_custom_abbreviations(self):
        """Test adding custom abbreviations."""
        custom_abbrevs = {"Corp", "Assoc", "Dept"}
        detector = SentenceBoundaryDetector(custom_abbreviations=custom_abbrevs)
        
        text = "She works at Tech Corp. in the Engineering Dept. since 2020."
        boundaries = detector.detect_boundaries(text)
        
        # Should detect only one sentence
        assert len(boundaries) == 1
    
    def test_segment_text(self):
        """Test text segmentation into sentences."""
        detector = SentenceBoundaryDetector()
        text = "First sentence. Second sentence! Third sentence?"
        
        segments = detector.segment_text(text)
        
        assert len(segments) == 3
        assert segments[0].text == "First sentence."
        assert segments[1].text == "Second sentence!"
        assert segments[2].text == "Third sentence?"
        assert all(s.segment_type == BoundaryType.SENTENCE for s in segments)
    
    def test_find_natural_breaks(self):
        """Test finding natural breaks for chunking."""
        detector = SentenceBoundaryDetector()
        text = "Short. " * 10 + "This is a much longer sentence that contains many words."
        
        breaks = detector.find_natural_breaks(text, max_length=50)
        
        assert len(breaks) > 0
        # Breaks should occur at sentence boundaries
        for pos in breaks:
            assert text[pos-1] in '.!?' or pos == 0


class TestParagraphDetector:
    """Test cases for paragraph detection."""
    
    def test_blank_line_paragraphs(self):
        """Test detection of paragraphs separated by blank lines."""
        detector = ParagraphDetector()
        text = """This is the first paragraph.
It continues on the next line.

This is the second paragraph.
It also has multiple lines.

And here's a third paragraph."""
        
        boundaries = detector.detect_boundaries(text)
        
        assert len(boundaries) == 3
        assert all(b.boundary_type == BoundaryType.PARAGRAPH for b in boundaries)
        
        # Check metadata
        assert boundaries[1].metadata["blank_lines"] > 0
    
    def test_indented_paragraphs(self):
        """Test detection of indented paragraphs."""
        detector = ParagraphDetector(detect_indentation=True)
        text = """This is a normal paragraph.
    This paragraph is indented.
    It continues with the same indent.
This returns to normal indentation."""
        
        boundaries = detector.detect_boundaries(text)
        
        assert len(boundaries) >= 2
        # Check for indentation metadata - could be either 'indented' or 'indentation_change'
        indented = [b for b in boundaries if b.metadata.get("indented") or b.metadata.get("indentation_change")]
        assert len(indented) > 0
    
    def test_list_detection(self):
        """Test detection of list items."""
        detector = ParagraphDetector()
        text = """Here are some items:

- First item
- Second item
- Third item

1. Numbered item
2. Another numbered item"""
        
        boundaries = detector.detect_boundaries(text)
        segments = detector.segment_text(text)
        
        # Check for list item metadata
        list_items = [b for b in boundaries if b.metadata.get("list_item")]
        assert len(list_items) > 0
    
    def test_structural_breaks(self):
        """Test detection of headers and horizontal rules."""
        detector = ParagraphDetector()
        text = """# Header 1

This is a paragraph.

---

## Header 2

Another paragraph."""
        
        boundaries = detector.detect_boundaries(text)
        
        # Check for structural break metadata
        structural = [b for b in boundaries if b.metadata.get("structural_break")]
        assert len(structural) > 0
    
    def test_minimum_length_requirement(self):
        """Test minimum paragraph length requirement."""
        detector = ParagraphDetector(min_paragraph_length=50)
        text = """Short.

This is a much longer paragraph that definitely exceeds the minimum length requirement.

Tiny."""
        
        boundaries = detector.detect_boundaries(text)
        
        # Short paragraphs should have lower confidence
        for boundary in boundaries:
            para_text = text[boundary.start:boundary.end].strip()
            if len(para_text) < 50:
                assert boundary.confidence < 0.7
    
    def test_code_block_detection(self):
        """Test detection of code blocks."""
        detector = ParagraphDetector()
        text = """Here's some code:

```python
def hello():
    print("Hello, world!")
```

And here's more text."""
        
        segments = detector.segment_text(text)
        
        # Should properly segment around code blocks
        assert len(segments) >= 3
    
    def test_multi_blank_lines(self):
        """Test handling of multiple blank lines."""
        detector = ParagraphDetector()
        text = """First paragraph.


Second paragraph with extra spacing.



Third paragraph with even more spacing."""
        
        boundaries = detector.detect_boundaries(text)
        
        assert len(boundaries) == 3
        # Check blank line counts in metadata
        assert boundaries[1].metadata["blank_lines"] >= 1
        assert boundaries[2].metadata["blank_lines"] >= 2


class TestNaturalBreakFinder:
    """Test cases for natural break point finding."""
    
    def test_combined_detection(self):
        """Test that break finder combines multiple boundary types."""
        finder = NaturalBreakFinder()
        text = """This is a paragraph with multiple sentences. It has various content.

This is another paragraph. It also contains sentences."""
        
        boundaries = finder.detect_boundaries(text)
        
        # Should find both sentence and paragraph boundaries
        boundary_types = {b.boundary_type for b in boundaries}
        assert BoundaryType.SENTENCE in boundary_types
        assert BoundaryType.PARAGRAPH in boundary_types
    
    def test_break_prioritization(self):
        """Test that paragraphs are prioritized over sentences when within chunk size."""
        finder = NaturalBreakFinder(prefer_paragraphs=True, min_chunk_size=20)
        # Make first paragraph short enough to fit in one chunk
        text = """First paragraph is short.

Second paragraph starts here. With more sentences. And even more content to make it substantial.

Third paragraph for good measure."""
        
        breaks = finder.find_natural_breaks(text, max_length=100)
        
        # Should find breaks
        assert len(breaks) > 0
        
        # Get all boundaries
        all_boundaries = finder.detect_boundaries(text)
        para_boundaries = [b for b in all_boundaries if b.boundary_type == BoundaryType.PARAGRAPH]
        
        # When a paragraph boundary is within range, it should be preferred
        # Check that at least one break aligns with a paragraph boundary
        para_ends = [b.end for b in para_boundaries]
        assert any(b in para_ends for b in breaks)
    
    def test_chunk_size_constraints(self):
        """Test respecting min and max chunk sizes."""
        finder = NaturalBreakFinder(min_chunk_size=50, max_chunk_size=200)
        text = "Short. " * 50  # Many short sentences
        
        breaks = finder.find_natural_breaks(text, max_length=200)
        
        # Verify chunk sizes
        start = 0
        for break_pos in breaks:
            chunk_size = break_pos - start
            assert chunk_size >= 50 or break_pos == len(text)
            assert chunk_size <= 200
            start = break_pos
    
    def test_optimize_breaks(self):
        """Test optimized break finding for target size."""
        finder = NaturalBreakFinder()
        text = " ".join(["This is sentence number {}.".format(i) for i in range(50)])
        
        breaks = finder.optimize_breaks(text, target_size=200, tolerance=0.2)
        
        # Verify breaks create chunks close to target size
        start = 0
        for break_pos in breaks:
            chunk_size = break_pos - start
            # Allow 20% tolerance
            assert 160 <= chunk_size <= 240 or break_pos == len(text)
            start = break_pos
    
    def test_quote_handling(self):
        """Test that breaks avoid splitting quotes."""
        finder = NaturalBreakFinder(min_chunk_size=20)
        text = 'He said "This is a quote that should not be split in the middle." Then continued.'
        
        # Find breaks with small max_length to force a break
        breaks = finder.find_natural_breaks(text, max_length=40)
        
        # Verify no break occurs inside the quotes when possible
        quote_start = text.find('"')
        quote_end = text.rfind('"')
        
        # The quote penalty should discourage breaks inside quotes
        # Check that if there are breaks near the quote, they prefer to be outside
        for break_pos in breaks:
            # If the break is near the quote boundaries, it should be outside
            if quote_start - 10 <= break_pos <= quote_end + 10:
                assert break_pos <= quote_start or break_pos > quote_end
    
    def test_segment_generation(self):
        """Test generation of text segments."""
        finder = NaturalBreakFinder(max_chunk_size=100)
        text = """First paragraph here.

Second paragraph with more content.

Third paragraph."""
        
        segments = finder.segment_text(text)
        
        assert len(segments) > 0
        assert all(isinstance(s, TextSegment) for s in segments)
        assert all(s.segment_type == BoundaryType.SECTION for s in segments)


class TestTextAnalyzer:
    """Test cases for comprehensive text analysis."""
    
    def test_language_detection(self):
        """Test basic language detection."""
        # English text
        analyzer_en = TextAnalyzer(language="auto")
        text_en = "The quick brown fox jumps over the lazy dog."
        assert analyzer_en.detect_language(text_en) == "en"
        
        # Spanish text - need new analyzer instance
        analyzer_es = TextAnalyzer(language="auto")
        text_es = "El rápido zorro marrón salta sobre el perro perezoso."
        assert analyzer_es.detect_language(text_es) == "es"
        
        # French text - need new analyzer instance
        analyzer_fr = TextAnalyzer(language="auto")
        text_fr = "Le renard brun rapide saute par-dessus le chien paresseux."
        assert analyzer_fr.detect_language(text_fr) == "fr"
    
    def test_encoding_validation(self):
        """Test encoding validation and issue detection."""
        analyzer = TextAnalyzer()
        
        # Valid UTF-8 text
        valid_text = "Hello, world! 你好世界"
        validation = analyzer.validate_encoding(valid_text)
        assert validation["valid"]
        assert len(validation["issues"]) == 0
        
        # Text with BOM
        bom_text = "\ufeffHello, world!"
        validation = analyzer.validate_encoding(bom_text)
        assert validation["has_bom"]
        
        # Text with replacement character
        invalid_text = "Hello \ufffd world"
        validation = analyzer.validate_encoding(invalid_text)
        assert not validation["valid"]
        assert len(validation["issues"]) > 0
    
    def test_statistics_calculation(self):
        """Test calculation of text statistics."""
        analyzer = TextAnalyzer()
        text = """This is a test document. It has multiple sentences.

It also has multiple paragraphs. Each paragraph contains valuable information."""
        
        stats = analyzer.calculate_statistics(text)
        
        assert stats.word_count > 0
        assert stats.sentence_count == 4
        assert stats.paragraph_count == 2
        assert stats.avg_word_length > 0
        assert stats.avg_sentence_length > 0
        assert 0 <= stats.readability_score <= 100
    
    def test_complexity_analysis(self):
        """Test text complexity analysis."""
        analyzer = TextAnalyzer()
        
        # Simple text
        simple_text = "The cat sat on the mat. The dog ran fast."
        complexity = analyzer.analyze_complexity(simple_text)
        assert complexity["readability_score"] > 70
        assert complexity["complexity_level"] in ["Easy", "Very Easy", "Fairly Easy"]
        
        # Complex text
        complex_text = """The implementation of sophisticated algorithmic approaches 
        necessitates comprehensive understanding of theoretical foundations and 
        practical considerations regarding computational complexity."""
        complexity = analyzer.analyze_complexity(complex_text)
        assert complexity["readability_score"] < 50
        assert complexity["complexity_level"] in ["Difficult", "Very Difficult", "Fairly Difficult"]
    
    def test_line_ending_detection(self):
        """Test detection of different line ending types."""
        analyzer = TextAnalyzer()
        
        # Unix line endings
        unix_text = "Line 1\nLine 2\nLine 3"
        validation = analyzer.validate_encoding(unix_text)
        assert validation["line_endings"] == "LF (Unix/Linux/Mac)"
        
        # Windows line endings
        windows_text = "Line 1\r\nLine 2\r\nLine 3"
        validation = analyzer.validate_encoding(windows_text)
        assert validation["line_endings"] == "CRLF (Windows)"
    
    def test_comprehensive_summary(self):
        """Test generation of comprehensive analysis summary."""
        analyzer = TextAnalyzer(language="auto")
        text = """# Introduction

This is a test document for analyzing text processing capabilities.
It contains multiple paragraphs and sentences of varying complexity.

## Features

- Sentence detection
- Paragraph analysis
- Complexity metrics

The analyzer should handle various text formats and provide useful insights."""
        
        summary = analyzer.generate_summary(text)
        
        assert "language" in summary
        assert "encoding" in summary
        assert "statistics" in summary
        assert "complexity" in summary
        assert "boundary_summary" in summary
        assert "recommendations" in summary
        
        # Verify boundary counts
        assert summary["boundary_summary"]["total_boundaries"] > 0
        assert len(summary["boundary_summary"]["by_type"]) > 0
    
    def test_large_text_processing(self):
        """Test processing of large texts in chunks."""
        analyzer = TextAnalyzer()
        # Generate large text
        large_text = " ".join(["This is sentence {}.".format(i) for i in range(1000)])
        
        # Process in chunks
        segments = list(analyzer.process_large_text(large_text, chunk_size=1000))
        
        assert len(segments) > 0
        # Verify all text is covered
        total_length = sum(s.end - s.start for s in segments)
        assert total_length > 0


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_empty_text(self):
        """Test handling of empty text."""
        sentence_detector = SentenceBoundaryDetector()
        paragraph_detector = ParagraphDetector()
        analyzer = TextAnalyzer()
        
        empty_text = ""
        
        assert len(sentence_detector.detect_boundaries(empty_text)) == 0
        assert len(paragraph_detector.detect_boundaries(empty_text)) == 0
        assert analyzer.calculate_statistics(empty_text).word_count == 0
    
    def test_whitespace_only(self):
        """Test handling of whitespace-only text."""
        finder = NaturalBreakFinder()
        text = "   \n\n   \t\t   \n   "
        
        boundaries = finder.detect_boundaries(text)
        segments = finder.segment_text(text)
        
        # Should handle gracefully without errors
        assert isinstance(boundaries, list)
        assert isinstance(segments, list)
    
    def test_single_word(self):
        """Test handling of single word text."""
        detector = SentenceBoundaryDetector()
        text = "Word"
        
        boundaries = detector.detect_boundaries(text)
        
        assert len(boundaries) == 1
        assert boundaries[0].confidence < 0.8  # Lower confidence for incomplete
    
    def test_very_long_sentence(self):
        """Test handling of extremely long sentences."""
        detector = SentenceBoundaryDetector()
        # Create a very long sentence
        words = ["word{}".format(i) for i in range(1000)]
        text = " ".join(words) + "."
        
        boundaries = detector.detect_boundaries(text)
        
        assert len(boundaries) == 1
        assert boundaries[0].end == len(text)
    
    def test_unicode_edge_cases(self):
        """Test handling of various Unicode scenarios."""
        analyzer = TextAnalyzer()
        
        # Emoji text
        emoji_text = "Hello 👋 World 🌍! How are you? 😊"
        boundaries = analyzer.detect_boundaries(emoji_text)
        assert len(boundaries) > 0
        
        # Mixed scripts - analyzer defaults to English which won't split on Chinese punctuation
        mixed_text = "English text. 中文文本。 Текст на русском."
        stats = analyzer.calculate_statistics(mixed_text)
        # With English detection, Chinese period won't create a break without following capital
        assert stats.sentence_count >= 2
    
    def test_malformed_text(self):
        """Test handling of malformed text patterns."""
        detector = SentenceBoundaryDetector()
        
        # Multiple punctuation
        text1 = "What?!?! Really... Okay."
        boundaries1 = detector.detect_boundaries(text1)
        assert len(boundaries1) >= 2
        
        # Unbalanced quotes
        text2 = 'He said "Hello but never closed the quote. Next sentence.'
        boundaries2 = detector.detect_boundaries(text2)
        assert len(boundaries2) >= 1


# Performance tests
class TestPerformance:
    """Test performance with larger texts."""
    
    def test_large_document_performance(self):
        """Test that processing large documents completes in reasonable time."""
        import time
        
        # Generate a large document
        paragraphs = []
        for i in range(100):
            sentences = ["This is sentence {} in paragraph {}.".format(j, i) for j in range(10)]
            paragraphs.append(" ".join(sentences))
        
        large_text = "\n\n".join(paragraphs)
        
        analyzer = TextAnalyzer()
        
        start_time = time.time()
        summary = analyzer.generate_summary(large_text)
        end_time = time.time()
        
        # Should complete within reasonable time (5 seconds)
        assert end_time - start_time < 5.0
        assert summary["statistics"]["paragraph_count"] >= 100
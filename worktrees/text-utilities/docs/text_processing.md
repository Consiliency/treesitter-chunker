# Text Processing Module Documentation

## Overview

The text processing module provides sophisticated natural language processing utilities for detecting text boundaries, finding natural break points, and analyzing text structure. It supports multiple languages and encodings, with both regex-based and optional NLTK-enhanced implementations.

## Architecture

### Core Components

1. **TextProcessor** (Abstract Base Class)
   - Base interface for all text processing operations
   - Provides common functionality for boundary detection and segmentation
   - Handles large text processing with memory-efficient chunking

2. **SentenceBoundaryDetector**
   - Detects sentence boundaries using regex patterns and heuristics
   - Handles abbreviations, decimals, URLs, and quotes
   - Optional NLTK integration for enhanced accuracy
   - Multi-language support with language-specific punctuation

3. **ParagraphDetector**
   - Identifies paragraph boundaries based on whitespace patterns
   - Detects structural elements (headers, lists, code blocks)
   - Supports indentation-based paragraph detection
   - Handles various text formats (Markdown, plain text)

4. **NaturalBreakFinder**
   - Combines multiple boundary detection methods
   - Prioritizes break points based on semantic importance
   - Optimizes chunk sizes for specific targets
   - Avoids breaking within quotes or important structures

5. **TextAnalyzer**
   - Comprehensive text analysis with statistics
   - Basic language detection
   - Encoding validation
   - Complexity metrics and readability scoring

## Key Features

### Sentence Detection
- **Abbreviation Handling**: Recognizes common abbreviations to avoid false boundaries
- **Decimal Number Support**: Doesn't break on decimal points (e.g., "3.14")
- **Quote Management**: Properly handles quoted text and parentheses
- **URL/Email Detection**: Avoids breaking within URLs and email addresses
- **Multi-language Support**: Language-specific punctuation patterns

### Paragraph Detection
- **Blank Line Detection**: Standard paragraph separation
- **Indentation Analysis**: Detects indented paragraphs and quotes
- **Structural Elements**: Recognizes headers, lists, and code blocks
- **Flexible Configuration**: Adjustable minimum paragraph length

### Natural Break Finding
- **Multi-level Prioritization**: Paragraphs > Sections > Sentences > Words
- **Context-aware Scoring**: Considers surrounding text for break quality
- **Size Optimization**: Dynamic programming for optimal chunk sizes
- **Quote Protection**: Avoids breaking within quoted passages

### Text Analysis
- **Comprehensive Statistics**: Word count, sentence count, vocabulary size
- **Readability Scoring**: Flesch Reading Ease calculation
- **Complexity Metrics**: Lexical diversity, sentence variance
- **Language Detection**: Basic detection for common languages
- **Encoding Validation**: Detects encoding issues and special characters

## Usage Examples

### Basic Sentence Detection

```python
from chunker.text_processing import SentenceBoundaryDetector

# Create detector
detector = SentenceBoundaryDetector(language="en")

# Detect sentences
text = "Dr. Smith works at OpenAI Inc. She specializes in A.I. research!"
segments = detector.segment_text(text)

for segment in segments:
    print(f"Sentence: {segment.text}")
    print(f"Confidence: {segment.start_boundary.confidence}")
```

### Paragraph Detection with Metadata

```python
from chunker.text_processing import ParagraphDetector

# Create detector with custom settings
detector = ParagraphDetector(
    min_paragraph_length=50,
    detect_indentation=True
)

text = """First paragraph here.

Second paragraph with more content.

    Indented paragraph or quote."""

boundaries = detector.detect_boundaries(text)

for boundary in boundaries:
    print(f"Paragraph at {boundary.start}-{boundary.end}")
    print(f"Metadata: {boundary.metadata}")
```

### Finding Natural Breaks for Chunking

```python
from chunker.text_processing import NaturalBreakFinder

# Create break finder
finder = NaturalBreakFinder(
    prefer_paragraphs=True,
    min_chunk_size=200,
    max_chunk_size=500
)

# Find optimal breaks
text = "Your long document text here..."
breaks = finder.find_natural_breaks(text, max_length=400)

# Create chunks
chunks = []
start = 0
for break_pos in breaks:
    chunks.append(text[start:break_pos])
    start = break_pos
```

### Comprehensive Text Analysis

```python
from chunker.text_processing import TextAnalyzer

# Create analyzer with auto language detection
analyzer = TextAnalyzer(language="auto")

# Analyze text
text = "Your text to analyze..."
summary = analyzer.generate_summary(text)

print(f"Language: {summary['language']}")
print(f"Statistics: {summary['statistics']}")
print(f"Complexity: {summary['complexity']}")
print(f"Recommendations: {summary['recommendations']}")
```

## Configuration Options

### SentenceBoundaryDetector
- `language`: ISO 639-1 language code (default: "en")
- `encoding`: Text encoding (default: "utf-8")
- `use_nltk`: Enable NLTK integration if available (default: True)
- `custom_abbreviations`: Additional abbreviations to recognize

### ParagraphDetector
- `min_paragraph_length`: Minimum characters for valid paragraph (default: 20)
- `require_blank_line`: Require blank lines between paragraphs (default: True)
- `detect_indentation`: Enable indentation-based detection (default: True)

### NaturalBreakFinder
- `prefer_paragraphs`: Prioritize paragraph breaks (default: True)
- `min_chunk_size`: Minimum chunk size in characters (default: 100)
- `max_chunk_size`: Maximum chunk size in characters (default: 1000)

### TextAnalyzer
- `language`: Language code or "auto" for detection (default: "auto")
- `encoding`: Text encoding (default: "utf-8")

## Performance Considerations

1. **Large Text Processing**
   - Use `process_large_text()` method for documents > 1MB
   - Processes text in configurable chunks to manage memory
   - Maintains boundary accuracy across chunk boundaries

2. **Caching**
   - Language detection results are cached per analyzer instance
   - Regex patterns are compiled once during initialization

3. **Optional Dependencies**
   - NLTK is optional but improves sentence detection accuracy
   - Install with: `pip install nltk`
   - Download punkt tokenizer: `nltk.download('punkt')`

## Language Support

Currently supported languages with specific handling:
- English (en)
- Spanish (es)
- French (fr)
- German (de)
- Italian (it)
- Portuguese (pt)
- Chinese (zh)
- Japanese (ja)
- Korean (ko)
- Arabic (ar)
- Hindi (hi)

Other languages fall back to default patterns.

## Error Handling

The module handles various edge cases gracefully:
- Empty or whitespace-only text
- Malformed punctuation
- Unbalanced quotes
- Mixed encodings
- Very long sentences or paragraphs

## Future Enhancements

Potential improvements for future versions:
1. Enhanced language detection using more sophisticated models
2. Support for more languages and scripts
3. Integration with spaCy for advanced NLP features
4. Machine learning-based boundary detection
5. Semantic similarity-based chunking
6. Support for structured documents (XML, HTML)

## Testing

The module includes comprehensive unit tests covering:
- Basic functionality for all components
- Edge cases and error conditions
- Multi-language support
- Performance with large texts
- Integration between components

Run tests with:
```bash
pytest tests/test_text_processing.py -v
```
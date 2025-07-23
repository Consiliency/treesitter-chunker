"""
Demonstration of text processing utilities.

This script shows how to use the text processing module for various
natural language processing tasks.
"""

from chunker.text_processing import (
    SentenceBoundaryDetector,
    ParagraphDetector,
    NaturalBreakFinder,
    TextAnalyzer
)


def demo_sentence_detection():
    """Demonstrate sentence boundary detection."""
    print("=== Sentence Detection Demo ===\n")
    
    # Sample text with various sentence types
    text = """
    Dr. Smith works at OpenAI Inc. and specializes in N.L.P. research.
    She earned her Ph.D. from M.I.T. in 2019. "This is amazing!" she exclaimed.
    The temperature was 98.6 degrees. What do you think? I'm not sure...
    Visit our website at www.example.com for more info.
    """
    
    # Create detector
    detector = SentenceBoundaryDetector()
    
    # Detect sentences
    boundaries = detector.detect_boundaries(text.strip())
    segments = detector.segment_text(text.strip())
    
    print(f"Found {len(boundaries)} sentences:\n")
    
    for i, segment in enumerate(segments, 1):
        print(f"{i}. {segment.text}")
        print(f"   Confidence: {segment.start_boundary.confidence:.2f}")
        print(f"   Position: {segment.start} - {segment.end}")
        print()


def demo_paragraph_detection():
    """Demonstrate paragraph boundary detection."""
    print("\n=== Paragraph Detection Demo ===\n")
    
    text = """
# Introduction

This is the first paragraph of our document. It contains multiple sentences
that form a cohesive unit of thought.

This is the second paragraph. Notice how it's separated by a blank line
from the previous one.

- First list item
- Second list item
- Third list item

    This paragraph is indented, which might indicate
    a quote or a special section in the document.

## Conclusion

The final paragraph wraps up our discussion.
"""
    
    # Create detector
    detector = ParagraphDetector()
    
    # Detect paragraphs
    segments = detector.segment_text(text.strip())
    
    print(f"Found {len(segments)} paragraphs:\n")
    
    for i, segment in enumerate(segments, 1):
        print(f"Paragraph {i}:")
        print(f"Text: {segment.text[:50]}..." if len(segment.text) > 50 else f"Text: {segment.text}")
        print(f"Metadata: {segment.start_boundary.metadata}")
        print()


def demo_natural_breaks():
    """Demonstrate natural break point finding."""
    print("\n=== Natural Break Finding Demo ===\n")
    
    text = """
    The history of artificial intelligence began in antiquity, with myths, stories and rumors of artificial beings endowed with intelligence or consciousness by master craftsmen. The seeds of modern AI were planted by classical philosophers who attempted to describe the process of human thinking as the mechanical manipulation of symbols.

    This work culminated in the invention of the programmable digital computer in the 1940s, a machine based on the abstract essence of mathematical reasoning. This device and the ideas behind it inspired a handful of scientists to begin seriously discussing the possibility of building an electronic brain.

    The field of AI research was founded at a workshop held on the campus of Dartmouth College during the summer of 1956. Those who attended would become the leaders of AI research for decades. Many of them predicted that a machine as intelligent as a human being would exist in no more than a generation and they were given millions of dollars to make this vision come true.
    """
    
    # Create break finder
    finder = NaturalBreakFinder(
        prefer_paragraphs=True,
        min_chunk_size=100,
        max_chunk_size=300
    )
    
    # Find natural breaks
    breaks = finder.find_natural_breaks(text.strip(), max_length=300)
    
    print(f"Found {len(breaks)} natural break points\n")
    
    # Show chunks
    start = 0
    for i, break_pos in enumerate(breaks, 1):
        chunk = text[start:break_pos].strip()
        print(f"Chunk {i} ({len(chunk)} chars):")
        print(chunk[:100] + "..." if len(chunk) > 100 else chunk)
        print()
        start = break_pos
    
    # Show final chunk
    if start < len(text):
        final_chunk = text[start:].strip()
        print(f"Final chunk ({len(final_chunk)} chars):")
        print(final_chunk[:100] + "..." if len(final_chunk) > 100 else final_chunk)


def demo_text_analysis():
    """Demonstrate comprehensive text analysis."""
    print("\n\n=== Text Analysis Demo ===\n")
    
    text = """
    Natural language processing (NLP) is a subfield of linguistics, computer science, and artificial intelligence concerned with the interactions between computers and human language, in particular how to program computers to process and analyze large amounts of natural language data.

    The goal is a computer capable of "understanding" the contents of documents, including the contextual nuances of the language within them. The technology can then accurately extract information and insights contained in the documents as well as categorize and organize the documents themselves.

    Challenges in natural language processing frequently involve speech recognition, natural language understanding, and natural language generation. These challenges are closely related to the field of computational linguistics, which combines computer science with linguistics.
    """
    
    # Create analyzer with auto language detection
    analyzer = TextAnalyzer(language="auto")
    
    # Generate comprehensive summary
    summary = analyzer.generate_summary(text.strip())
    
    print("Language:", summary["language"])
    print("\nStatistics:")
    for key, value in summary["statistics"].items():
        print(f"  {key}: {value}")
    
    print("\nComplexity Analysis:")
    for key, value in summary["complexity"].items():
        if key != "most_common_words":
            print(f"  {key}: {value}")
    
    print("\nMost Common Words:")
    for word, count in summary["complexity"]["most_common_words"][:5]:
        print(f"  '{word}': {count} times")
    
    print("\nBoundary Summary:")
    print(f"  Total boundaries: {summary['boundary_summary']['total_boundaries']}")
    for boundary_type, count in summary["boundary_summary"]["by_type"].items():
        print(f"  {boundary_type}: {count}")
    
    if summary["recommendations"]:
        print("\nRecommendations:")
        for rec in summary["recommendations"]:
            print(f"  - {rec}")


def demo_multilingual_support():
    """Demonstrate multilingual text processing."""
    print("\n\n=== Multilingual Support Demo ===\n")
    
    examples = {
        "English": "The quick brown fox jumps over the lazy dog. What a beautiful day!",
        "Spanish": "El rápido zorro marrón salta sobre el perro perezoso. ¡Qué día tan hermoso!",
        "French": "Le renard brun rapide saute par-dessus le chien paresseux. Quelle belle journée!",
        "Chinese": "敏捷的棕色狐狸跳过懒狗。多么美好的一天！",
        "Mixed": "Hello world! Bonjour le monde! ¡Hola mundo! 你好世界！"
    }
    
    for lang_name, text in examples.items():
        print(f"\n{lang_name} text:")
        print(f"  Text: {text}")
        
        # Auto-detect language
        analyzer = TextAnalyzer(language="auto")
        detected_lang = analyzer.detect_language(text)
        print(f"  Detected language: {detected_lang}")
        
        # Detect sentences
        if detected_lang in ["en", "es", "fr", "zh"]:
            detector = SentenceBoundaryDetector(language=detected_lang)
        else:
            detector = SentenceBoundaryDetector()  # Default to English
        
        sentences = detector.segment_text(text)
        print(f"  Sentences found: {len(sentences)}")


def demo_chunking_optimization():
    """Demonstrate optimal chunking for specific size targets."""
    print("\n\n=== Chunking Optimization Demo ===\n")
    
    # Generate a longer text
    text = """
    Machine learning is a method of data analysis that automates analytical model building. It is a branch of artificial intelligence based on the idea that systems can learn from data, identify patterns and make decisions with minimal human intervention.

    Because of new computing technologies, machine learning today is not like machine learning of the past. It was born from pattern recognition and the theory that computers can learn without being programmed to perform specific tasks. Researchers interested in artificial intelligence wanted to see if computers could learn from data.

    The iterative aspect of machine learning is important because as models are exposed to new data, they are able to independently adapt. They learn from previous computations to produce reliable, repeatable decisions and results. It's a science that's not new – but one that has gained fresh momentum.

    While many machine learning algorithms have been around for a long time, the ability to automatically apply complex mathematical calculations to big data – over and over, faster and faster – is a recent development. Here are a few widely publicized examples of machine learning applications you may be familiar with:

    The heavily hyped, self-driving Google car? The essence of machine learning. Online recommendation offers such as those from Amazon and Netflix? Machine learning applications for everyday life. Knowing what customers are saying about you on Twitter? Machine learning combined with linguistic rule creation. Fraud detection? One of the more obvious, important uses in our world today.
    """
    
    # Create break finder
    finder = NaturalBreakFinder()
    
    # Find optimized breaks for target size of 400 characters
    target_size = 400
    breaks = finder.optimize_breaks(text.strip(), target_size=target_size, tolerance=0.2)
    
    print(f"Optimizing for chunks of ~{target_size} characters (±20%)\n")
    
    # Show optimized chunks
    start = 0
    chunks = []
    for break_pos in breaks:
        chunk = text[start:break_pos].strip()
        chunks.append(chunk)
        start = break_pos
    
    # Add final chunk
    if start < len(text):
        chunks.append(text[start:].strip())
    
    # Display chunks with statistics
    total_chars = 0
    for i, chunk in enumerate(chunks, 1):
        chunk_len = len(chunk)
        total_chars += chunk_len
        deviation = abs(chunk_len - target_size) / target_size * 100
        
        print(f"Chunk {i}:")
        print(f"  Size: {chunk_len} chars (deviation: {deviation:.1f}%)")
        print(f"  Text: {chunk[:80]}...")
        print()
    
    avg_size = total_chars / len(chunks)
    print(f"Average chunk size: {avg_size:.1f} characters")


def main():
    """Run all demonstrations."""
    print("Text Processing Utilities Demonstration")
    print("=" * 50)
    
    demo_sentence_detection()
    demo_paragraph_detection()
    demo_natural_breaks()
    demo_text_analysis()
    demo_multilingual_support()
    demo_chunking_optimization()
    
    print("\n\nDemo completed!")


if __name__ == "__main__":
    main()
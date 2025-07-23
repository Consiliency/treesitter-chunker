"""Demo script showing sliding window usage patterns."""

from pathlib import Path
import json

from chunker.sliding_window import (
    DefaultSlidingWindowEngine,
    DefaultWindowNavigator,
    WindowConfig,
    WindowUnit,
    OverlapStrategy
)
from chunker.sliding_window.utils import (
    calculate_window_statistics,
    optimize_window_config,
    find_natural_boundaries,
    create_windows_from_boundaries
)


def basic_usage():
    """Basic sliding window usage."""
    print("=== Basic Sliding Window Usage ===\n")
    
    # Sample text
    text = """The sliding window technique is a method for processing sequential data
by examining fixed-size or variable-size segments that "slide" through the data.
This approach is particularly useful for natural language processing tasks.

Each window captures a portion of the text, and consecutive windows may overlap
to ensure continuity and context preservation. The overlap helps maintain
semantic coherence across window boundaries.

This technique is commonly used in:
- Text summarization
- Language modeling  
- Document chunking for LLMs
- Time series analysis
- Pattern recognition

By adjusting window size and overlap, you can optimize for different use cases."""
    
    # Create configuration
    config = WindowConfig(
        size=100,  # 100 characters per window
        unit=WindowUnit.CHARACTERS,
        overlap=20,  # 20 character overlap
        overlap_strategy=OverlapStrategy.FIXED,
        preserve_boundaries=True,
        trim_whitespace=True
    )
    
    # Create engine
    engine = DefaultSlidingWindowEngine(config)
    
    # Process text
    print(f"Processing text of {len(text)} characters...\n")
    
    for i, window in enumerate(engine.process_text(text)):
        print(f"Window {i + 1}:")
        print(f"  Position: {window.position.start}-{window.position.end}")
        print(f"  Lines: {window.position.start_line}-{window.position.end_line}")
        print(f"  Size: {len(window.content)} chars")
        print(f"  Content: {window.content[:50]}..." if len(window.content) > 50 else f"  Content: {window.content}")
        print(f"  Overlap: {window.metadata.get('overlap_chars', 0)} chars")
        print()


def line_based_windows():
    """Demonstrate line-based window processing."""
    print("\n=== Line-Based Windows ===\n")
    
    # Create some code-like content
    code_text = """def process_data(input_list):
    '''Process a list of data items.'''
    results = []
    
    for item in input_list:
        # Validate item
        if not validate_item(item):
            continue
            
        # Transform item
        transformed = transform(item)
        
        # Apply business logic
        if transformed.value > threshold:
            results.append(transformed)
    
    return results


def validate_item(item):
    '''Check if item is valid.'''
    return item is not None and hasattr(item, 'value')


def transform(item):
    '''Transform item into processed format.'''
    return ProcessedItem(
        value=item.value * 2,
        timestamp=datetime.now()
    )"""
    
    # Configure for line-based windows
    config = WindowConfig(
        size=10,  # 10 lines per window
        unit=WindowUnit.LINES,
        overlap=2,  # 2 line overlap
        overlap_strategy=OverlapStrategy.FIXED
    )
    
    engine = DefaultSlidingWindowEngine(config)
    
    for i, window in enumerate(engine.process_text(code_text)):
        print(f"Window {i + 1} ({window.metadata.get('line_count', 0)} lines):")
        print("-" * 40)
        print(window.content)
        print("-" * 40)
        print()


def percentage_overlap():
    """Demonstrate percentage-based overlap."""
    print("\n=== Percentage-Based Overlap ===\n")
    
    text = "ABCDEFGHIJKLMNOPQRSTUVWXYZ" * 10
    
    config = WindowConfig(
        size=50,
        unit=WindowUnit.CHARACTERS,
        overlap=20,  # 20% overlap
        overlap_strategy=OverlapStrategy.PERCENTAGE
    )
    
    engine = DefaultSlidingWindowEngine(config)
    windows = list(engine.process_text(text))
    
    print(f"Text length: {len(text)} characters")
    print(f"Window size: 50 characters")
    print(f"Overlap: 20% (10 characters)\n")
    
    for i, window in enumerate(windows[:3]):  # Show first 3 windows
        print(f"Window {i + 1}: {window.content}")
        if i < len(windows) - 1:
            overlap_start = windows[i + 1].position.start
            overlap_content = text[overlap_start:window.position.end]
            print(f"  Overlap with next: '{overlap_content}'")
        print()


def dynamic_window_adjustment():
    """Demonstrate dynamic window size adjustment."""
    print("\n=== Dynamic Window Adjustment ===\n")
    
    # Text with varying density
    mixed_text = """Short.

Very short.

This is a much longer paragraph with significantly more content that should 
trigger the dynamic adjustment mechanism to potentially reduce the window size
due to the higher content density and longer lines.

Brief.

Another dense section with lots of information packed into long lines that extend
across the page and contain multiple clauses and ideas that might benefit from
smaller window sizes to avoid overwhelming the processing system."""
    
    config = WindowConfig(
        size=100,
        unit=WindowUnit.CHARACTERS,
        min_window_size=50,
        max_window_size=150
    )
    
    engine = DefaultSlidingWindowEngine(config)
    
    for window in engine.process_text(mixed_text):
        adjusted = window.metadata.get('size_adjusted', False)
        reason = window.metadata.get('adjustment_reason', 'none')
        
        print(f"Window size: {len(window.content)} chars")
        print(f"Adjusted: {adjusted} (reason: {reason})")
        print(f"Content preview: {window.content[:60]}...")
        print()


def navigation_example():
    """Demonstrate window navigation."""
    print("\n=== Window Navigation ===\n")
    
    # Create some structured content
    chapters = []
    for i in range(5):
        chapter = f"Chapter {i + 1}\n" + "=" * 20 + "\n\n"
        chapter += f"This is the content of chapter {i + 1}.\n" * 5
        chapters.append(chapter)
    
    text = "\n\n".join(chapters)
    
    # Create navigator
    config = WindowConfig(size=200, unit=WindowUnit.CHARACTERS)
    engine = DefaultSlidingWindowEngine(config)
    navigator = DefaultWindowNavigator(engine, text)
    
    print(f"Total windows: {navigator.total_windows}")
    print()
    
    # Navigate forward
    print("Forward navigation:")
    for i in range(3):
        window = navigator.next_window() if i > 0 else navigator.current_window()
        if window:
            print(f"  Window {window.position.window_index + 1}: {window.content[:30]}...")
    
    # Jump to specific window
    print("\nJump to window 5:")
    window = navigator.jump_to_window(4)
    if window:
        print(f"  Current: Window {window.position.window_index + 1}")
    
    # Search for content
    print("\nSearch for 'Chapter 3':")
    indices = navigator.find_windows_containing("Chapter 3")
    print(f"  Found in windows: {[i + 1 for i in indices]}")
    
    # Jump to position
    print("\nJump to character position 500:")
    window = navigator.jump_to_position(500)
    if window:
        print(f"  Now at: Window {window.position.window_index + 1}")
        print(f"  Position range: {window.position.start}-{window.position.end}")


def file_processing_example():
    """Demonstrate file processing."""
    print("\n=== File Processing ===\n")
    
    # Create a temporary file
    import tempfile
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        # Write some content
        for i in range(100):
            f.write(f"Line {i + 1}: " + "x" * (50 + i % 20) + "\n")
        temp_path = f.name
    
    try:
        config = WindowConfig(
            size=500,
            unit=WindowUnit.CHARACTERS,
            overlap=50
        )
        
        engine = DefaultSlidingWindowEngine(config)
        
        print(f"Processing file: {temp_path}")
        
        window_count = 0
        total_chars = 0
        
        for window in engine.process_file(temp_path):
            window_count += 1
            total_chars += len(window.content)
            
            if window_count <= 3:  # Show first 3 windows
                print(f"\nWindow {window_count}:")
                print(f"  Size: {len(window.content)} chars")
                print(f"  Lines: {window.position.start_line}-{window.position.end_line}")
                print(f"  Progress: {window.position.progress:.1f}%" if window.position.progress else "  Progress: Unknown")
        
        print(f"\nTotal windows: {window_count}")
        print(f"Total characters processed: {total_chars}")
        
    finally:
        # Cleanup
        Path(temp_path).unlink()


def utility_functions_demo():
    """Demonstrate utility functions."""
    print("\n=== Utility Functions ===\n")
    
    text = """Introduction

This document demonstrates the sliding window technique for text processing.
The technique is useful for breaking large documents into manageable chunks.

Section 1: Basics

The basic concept involves moving a fixed-size window through the text.
Windows can overlap to maintain context between chunks.

Section 2: Advanced Features

Advanced features include dynamic sizing, semantic boundaries, and more.
The system can adapt to different types of content automatically.

Conclusion

The sliding window approach provides a flexible solution for text processing."""
    
    # Optimize configuration
    print("1. Optimizing window configuration for ~5 windows:")
    config = optimize_window_config(text, target_windows=5)
    print(f"   Suggested size: {config.size} {config.unit.value}")
    print(f"   Suggested overlap: {config.overlap}")
    print()
    
    # Find natural boundaries
    print("2. Finding natural boundaries:")
    boundaries = find_natural_boundaries(text, preferred_size=150)
    print(f"   Found {len(boundaries)} boundaries")
    for i, pos in enumerate(boundaries[:5]):
        context = text[max(0, pos-20):pos+20].replace('\n', '\\n')
        print(f"   Boundary {i + 1} at position {pos}: ...{context}...")
    print()
    
    # Create windows from boundaries
    print("3. Creating windows from boundaries:")
    windows = create_windows_from_boundaries(text, boundaries, overlap_size=20)
    print(f"   Created {len(windows)} windows")
    
    # Calculate statistics
    print("\n4. Window statistics:")
    stats = calculate_window_statistics(windows)
    for key, value in stats.items():
        if isinstance(value, float):
            print(f"   {key}: {value:.2f}")
        else:
            print(f"   {key}: {value}")


def semantic_overlap_example():
    """Demonstrate semantic overlap strategy."""
    print("\n=== Semantic Overlap ===\n")
    
    text = """First sentence. Second sentence. Third sentence.
Fourth sentence. Fifth sentence. Sixth sentence.
Seventh sentence. Eighth sentence. Ninth sentence."""
    
    config = WindowConfig(
        size=50,
        unit=WindowUnit.CHARACTERS,
        overlap_strategy=OverlapStrategy.SEMANTIC,
        preserve_boundaries=True
    )
    
    engine = DefaultSlidingWindowEngine(config)
    windows = list(engine.process_text(text))
    
    print("Semantic overlap tries to overlap at natural boundaries:")
    print()
    
    for i, window in enumerate(windows):
        print(f"Window {i + 1}: '{window.content}'")
        if i > 0:
            print(f"  (Overlap: {window.metadata.get('overlap_chars', 0)} chars)")
        print()


def export_windows_json():
    """Export windows to JSON format."""
    print("\n=== JSON Export Example ===\n")
    
    text = "Sample text for JSON export. " * 10
    
    config = WindowConfig(size=50, overlap=10)
    engine = DefaultSlidingWindowEngine(config)
    
    windows_data = []
    for window in engine.process_text(text):
        windows_data.append({
            "index": window.position.window_index,
            "content": window.content,
            "start": window.position.start,
            "end": window.position.end,
            "size": len(window.content),
            "metadata": window.metadata
        })
    
    # Pretty print JSON
    json_output = json.dumps(windows_data[:2], indent=2)  # First 2 windows
    print("Windows in JSON format:")
    print(json_output)


def main():
    """Run all demonstrations."""
    demos = [
        basic_usage,
        line_based_windows,
        percentage_overlap,
        dynamic_window_adjustment,
        navigation_example,
        file_processing_example,
        utility_functions_demo,
        semantic_overlap_example,
        export_windows_json
    ]
    
    for demo in demos:
        try:
            demo()
            print("\n" + "=" * 60 + "\n")
        except Exception as e:
            print(f"Error in {demo.__name__}: {e}")
            print("\n" + "=" * 60 + "\n")


if __name__ == "__main__":
    main()
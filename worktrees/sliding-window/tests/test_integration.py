"""Integration tests for sliding window module."""

import pytest
from pathlib import Path

from chunker.sliding_window import (
    DefaultSlidingWindowEngine,
    DefaultWindowNavigator,
    WindowConfig,
    WindowUnit,
    OverlapStrategy
)


def test_full_integration():
    """Test complete integration of sliding window components."""
    
    # Sample text with various features
    text = """# Introduction

This is a test document with multiple sections and varied content density.
It contains short lines and longer paragraphs to test dynamic adjustment.

## Section 1: Basic Content

Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor 
incididunt ut labore et dolore magna aliqua. This is a longer line that should
trigger density-based adjustments in the sliding window algorithm.

Short line.

## Section 2: Code Example

```python
def hello_world():
    print("Hello, World!")
    return True
```

## Section 3: Lists

- First item in the list
- Second item with more content
- Third item that spans multiple lines because it contains a lot of 
  explanatory text about the item

## Conclusion

This concludes our test document. The sliding window engine should process
this text efficiently while preserving semantic boundaries."""

    # Test 1: Basic character-based windowing
    config = WindowConfig(
        size=200,
        unit=WindowUnit.CHARACTERS,
        overlap=20,
        overlap_strategy=OverlapStrategy.FIXED,
        preserve_boundaries=True
    )
    
    engine = DefaultSlidingWindowEngine(config)
    windows = list(engine.process_text(text))
    
    assert len(windows) > 3  # Should create multiple windows
    assert all(len(w.content) > 0 for w in windows)  # No empty windows
    assert windows[0].position.start == 0  # First window starts at beginning
    assert windows[-1].position.end <= len(text)  # Last window doesn't exceed text
    
    # Test 2: Navigation
    navigator = DefaultWindowNavigator(engine, text)
    
    # Test forward navigation
    first = navigator.current_window()
    second = navigator.next_window()
    assert first.position.window_index < second.position.window_index
    
    # Test backward navigation
    prev = navigator.previous_window()
    assert prev.position.window_index == first.position.window_index
    
    # Test search
    code_windows = navigator.find_windows_containing("def hello_world")
    assert len(code_windows) > 0
    
    # Test 3: Line-based processing
    line_config = WindowConfig(
        size=5,
        unit=WindowUnit.LINES,
        overlap=1,
        overlap_strategy=OverlapStrategy.FIXED
    )
    
    line_engine = DefaultSlidingWindowEngine(line_config)
    line_windows = list(line_engine.process_text(text))
    
    assert len(line_windows) > 0
    # Each window should have roughly 5 lines (except possibly the last)
    for window in line_windows[:-1]:
        line_count = window.content.count('\n') + 1
        assert 3 <= line_count <= 7  # Some flexibility for boundary preservation
    
    # Test 4: Percentage overlap
    pct_config = WindowConfig(
        size=100,
        unit=WindowUnit.CHARACTERS,
        overlap=25,  # 25%
        overlap_strategy=OverlapStrategy.PERCENTAGE
    )
    
    pct_engine = DefaultSlidingWindowEngine(pct_config)
    pct_windows = list(pct_engine.process_text(text))
    
    # Check overlap is ~25% of window size
    for i in range(1, len(pct_windows)):
        overlap = pct_windows[i].metadata.get('overlap_chars', 0)
        assert 20 <= overlap <= 30  # ~25% of 100
    
    # Test 5: Dynamic adjustment
    dynamic_config = WindowConfig(
        size=150,
        unit=WindowUnit.CHARACTERS,
        min_window_size=100,
        max_window_size=200
    )
    
    dynamic_engine = DefaultSlidingWindowEngine(dynamic_config)
    dynamic_windows = list(dynamic_engine.process_text(text))
    
    # Some windows should be adjusted
    adjusted = [w for w in dynamic_windows if w.metadata.get('size_adjusted')]
    assert len(adjusted) > 0
    
    # All windows should be within bounds
    for window in dynamic_windows:
        assert 100 <= len(window.content) <= 200
    
    # Test 6: Coverage validation
    from chunker.sliding_window.utils import validate_window_coverage
    
    is_valid, issues = validate_window_coverage(windows, len(text))
    assert is_valid, f"Coverage issues: {issues}"
    
    # Test 7: Statistics
    from chunker.sliding_window.utils import calculate_window_statistics
    
    stats = calculate_window_statistics(windows)
    assert stats['total_windows'] == len(windows)
    assert stats['average_size'] > 0
    assert stats['total_characters'] > 0
    
    print(f"Integration test passed! Processed {len(windows)} windows")
    print(f"Average window size: {stats['average_size']:.1f} characters")
    print(f"Total overlap: {stats['total_overlap']} characters")


def test_error_handling():
    """Test error handling in various scenarios."""
    
    # Test invalid configurations
    with pytest.raises(ValueError):
        WindowConfig(size=-10)
    
    with pytest.raises(ValueError):
        WindowConfig(size=10, overlap=-5)
    
    with pytest.raises(ValueError):
        WindowConfig(
            size=10, 
            overlap=200, 
            overlap_strategy=OverlapStrategy.PERCENTAGE
        )
    
    # Test empty text handling
    config = WindowConfig(size=10)
    engine = DefaultSlidingWindowEngine(config)
    
    windows = list(engine.process_text(""))
    assert len(windows) == 0
    
    # Test whitespace-only text with trimming
    config_trim = WindowConfig(size=10, trim_whitespace=True)
    engine_trim = DefaultSlidingWindowEngine(config_trim)
    
    windows = list(engine_trim.process_text("   \n\n   \t\t   "))
    assert len(windows) == 0
    
    # Test file not found
    with pytest.raises(FileNotFoundError):
        list(engine.process_file("/nonexistent/file.txt"))


def test_edge_cases():
    """Test edge cases and boundary conditions."""
    
    # Test single character text
    config = WindowConfig(size=10)
    engine = DefaultSlidingWindowEngine(config)
    
    windows = list(engine.process_text("a"))
    assert len(windows) == 1
    assert windows[0].content == "a"
    
    # Test text exactly matching window size
    text = "x" * 50
    config = WindowConfig(size=50)
    engine = DefaultSlidingWindowEngine(config)
    
    windows = list(engine.process_text(text))
    assert len(windows) == 1
    assert len(windows[0].content) == 50
    
    # Test overlap larger than window
    config = WindowConfig(
        size=10,
        overlap=15,
        overlap_strategy=OverlapStrategy.FIXED
    )
    engine = DefaultSlidingWindowEngine(config)
    
    windows = list(engine.process_text("x" * 100))
    # Should handle gracefully
    assert all(w.metadata.get('overlap_chars', 0) < 10 for w in windows)
    
    # Test Unicode handling
    unicode_text = "Hello 世界! 🌍 café señor"
    config = WindowConfig(size=10)
    engine = DefaultSlidingWindowEngine(config)
    
    windows = list(engine.process_text(unicode_text))
    assert len(windows) > 0
    # Verify Unicode is preserved
    combined = "".join(w.content for w in windows)
    assert "世界" in combined
    assert "🌍" in combined
    assert "café" in combined


if __name__ == "__main__":
    test_full_integration()
    test_error_handling()
    test_edge_cases()
    print("All integration tests passed!")
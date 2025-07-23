"""Comprehensive tests for sliding window implementation."""

import pytest
from pathlib import Path
import tempfile
import os

from chunker.sliding_window import (
    DefaultSlidingWindowEngine,
    DefaultWindowNavigator,
    WindowConfig,
    WindowUnit,
    OverlapStrategy,
    Window,
    WindowPosition
)
from chunker.sliding_window.navigator import StreamingWindowNavigator
from chunker.sliding_window.utils import (
    merge_overlapping_windows,
    calculate_window_statistics,
    optimize_window_config,
    find_natural_boundaries,
    validate_window_coverage
)


class TestWindowConfig:
    """Test WindowConfig validation and creation."""
    
    def test_basic_config(self):
        """Test basic configuration creation."""
        config = WindowConfig(size=100, unit=WindowUnit.CHARACTERS)
        assert config.size == 100
        assert config.unit == WindowUnit.CHARACTERS
        assert config.overlap == 0
        assert config.overlap_strategy == OverlapStrategy.FIXED
    
    def test_config_with_overlap(self):
        """Test configuration with overlap."""
        config = WindowConfig(
            size=100,
            unit=WindowUnit.LINES,
            overlap=10,
            overlap_strategy=OverlapStrategy.PERCENTAGE
        )
        assert config.overlap == 10
        assert config.overlap_strategy == OverlapStrategy.PERCENTAGE
    
    def test_config_with_bounds(self):
        """Test configuration with min/max bounds."""
        config = WindowConfig(
            size=100,
            min_window_size=50,
            max_window_size=200
        )
        assert config.min_window_size == 50
        assert config.max_window_size == 200


class TestDefaultSlidingWindowEngine:
    """Test the default sliding window engine implementation."""
    
    @pytest.fixture
    def simple_text(self):
        """Simple text for testing."""
        return "Line 1\nLine 2\nLine 3\nLine 4\nLine 5\n" * 10
    
    @pytest.fixture
    def paragraph_text(self):
        """Text with paragraphs for testing."""
        return """First paragraph with some content.
This is still the first paragraph.

Second paragraph starts here.
It has multiple lines too.

Third paragraph is shorter.

Fourth and final paragraph."""
    
    def test_character_based_windows(self, simple_text):
        """Test character-based window creation."""
        config = WindowConfig(size=20, unit=WindowUnit.CHARACTERS)
        engine = DefaultSlidingWindowEngine(config)
        
        windows = list(engine.process_text(simple_text))
        
        assert len(windows) > 0
        assert all(len(w.content) <= 20 for w in windows)
        assert windows[0].position.start == 0
    
    def test_line_based_windows(self, simple_text):
        """Test line-based window creation."""
        config = WindowConfig(size=3, unit=WindowUnit.LINES)
        engine = DefaultSlidingWindowEngine(config)
        
        windows = list(engine.process_text(simple_text))
        
        assert len(windows) > 0
        for window in windows:
            line_count = window.content.count('\n')
            assert line_count <= 3
    
    def test_fixed_overlap(self, simple_text):
        """Test fixed overlap strategy."""
        config = WindowConfig(
            size=30,
            unit=WindowUnit.CHARACTERS,
            overlap=10,
            overlap_strategy=OverlapStrategy.FIXED
        )
        engine = DefaultSlidingWindowEngine(config)
        
        windows = list(engine.process_text(simple_text))
        
        # Check that windows overlap
        for i in range(len(windows) - 1):
            current = windows[i]
            next_window = windows[i + 1]
            overlap_size = current.position.end - next_window.position.start
            assert overlap_size >= 0  # Should have overlap
    
    def test_percentage_overlap(self, simple_text):
        """Test percentage-based overlap."""
        config = WindowConfig(
            size=50,
            unit=WindowUnit.CHARACTERS,
            overlap=20,  # 20%
            overlap_strategy=OverlapStrategy.PERCENTAGE
        )
        engine = DefaultSlidingWindowEngine(config)
        
        windows = list(engine.process_text(simple_text))
        
        for window in windows[1:]:  # Skip first window
            assert window.metadata.get("overlap_chars", 0) == 10  # 20% of 50
    
    def test_boundary_preservation(self, paragraph_text):
        """Test that boundaries are preserved."""
        config = WindowConfig(
            size=50,
            unit=WindowUnit.CHARACTERS,
            preserve_boundaries=True
        )
        engine = DefaultSlidingWindowEngine(config)
        
        windows = list(engine.process_text(paragraph_text))
        
        # Check that windows tend to end at natural boundaries
        for window in windows[:-1]:  # Exclude last window
            # Should end with whitespace or punctuation
            last_char = window.content[-1] if window.content else ''
            assert last_char in ' \n.!?' or window.position.end == len(paragraph_text)
    
    def test_whitespace_trimming(self):
        """Test whitespace trimming."""
        text = "   Content   \n\n   More content   "
        config = WindowConfig(
            size=20,
            unit=WindowUnit.CHARACTERS,
            trim_whitespace=True
        )
        engine = DefaultSlidingWindowEngine(config)
        
        windows = list(engine.process_text(text))
        
        for window in windows:
            assert not window.content.startswith(' ')
            assert not window.content.endswith(' ')
    
    def test_empty_text(self):
        """Test handling of empty text."""
        config = WindowConfig(size=10)
        engine = DefaultSlidingWindowEngine(config)
        
        windows = list(engine.process_text(""))
        assert len(windows) == 0
    
    def test_text_smaller_than_window(self):
        """Test text smaller than window size."""
        text = "Small text"
        config = WindowConfig(size=100)
        engine = DefaultSlidingWindowEngine(config)
        
        windows = list(engine.process_text(text))
        
        assert len(windows) == 1
        assert windows[0].content == text
        assert windows[0].position.start == 0
        assert windows[0].position.end == len(text)
    
    def test_dynamic_window_adjustment(self):
        """Test dynamic window size adjustment."""
        # Dense text (long lines)
        dense_text = "x" * 200 + "\n" + "y" * 200 + "\n"
        
        config = WindowConfig(
            size=100,
            min_window_size=50,
            max_window_size=150
        )
        engine = DefaultSlidingWindowEngine(config)
        
        windows = list(engine.process_text(dense_text))
        
        # Check that some windows were adjusted
        adjusted_windows = [w for w in windows if w.metadata.get("size_adjusted")]
        assert len(adjusted_windows) > 0
    
    def test_window_position_tracking(self, simple_text):
        """Test window position tracking."""
        config = WindowConfig(size=30)
        engine = DefaultSlidingWindowEngine(config)
        
        windows = list(engine.process_text(simple_text))
        
        # Check position continuity
        for i in range(len(windows) - 1):
            current = windows[i]
            next_window = windows[i + 1]
            
            # Positions should be sequential (with possible overlap)
            assert current.position.window_index == i
            assert next_window.position.window_index == i + 1
            
            # Line numbers should be consistent
            assert current.position.end_line <= next_window.position.start_line + 1
    
    def test_progress_tracking(self, simple_text):
        """Test progress tracking in windows."""
        config = WindowConfig(size=30)
        engine = DefaultSlidingWindowEngine(config)
        
        windows = list(engine.process_text(simple_text))
        
        # Check progress increases
        for i, window in enumerate(windows):
            if window.position.progress:
                expected_progress = (i + 1) / len(windows) * 100
                assert abs(window.position.progress - expected_progress) < 1
    
    def test_get_window_at_position(self, simple_text):
        """Test getting window at specific position."""
        config = WindowConfig(size=30)
        engine = DefaultSlidingWindowEngine(config)
        
        # Test various positions
        positions = [0, 15, 30, 50, len(simple_text) - 1]
        
        for pos in positions:
            window = engine.get_window_at_position(simple_text, pos)
            if pos < len(simple_text):
                assert window is not None
                assert window.position.start <= pos < window.position.end
            else:
                assert window is None
    
    def test_estimate_total_windows(self):
        """Test window count estimation."""
        text = "x" * 1000
        config = WindowConfig(size=100, overlap=10)
        engine = DefaultSlidingWindowEngine(config)
        
        estimated = engine.estimate_total_windows(len(text))
        actual = len(list(engine.process_text(text)))
        
        # Estimation should be reasonably close
        assert abs(estimated - actual) <= 2
    
    def test_invalid_config(self):
        """Test invalid configuration handling."""
        with pytest.raises(ValueError, match="Window size must be positive"):
            WindowConfig(size=-10)
        
        with pytest.raises(ValueError, match="Overlap cannot be negative"):
            WindowConfig(size=10, overlap=-5)
        
        with pytest.raises(ValueError, match="Overlap percentage cannot exceed 100"):
            WindowConfig(size=10, overlap=150, overlap_strategy=OverlapStrategy.PERCENTAGE)


class TestFileProcessing:
    """Test file processing capabilities."""
    
    @pytest.fixture
    def temp_file(self):
        """Create a temporary file for testing."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8') as f:
            content = "\n".join([f"Line {i}" for i in range(1000)])
            f.write(content)
            temp_path = f.name
        
        yield temp_path
        
        # Cleanup
        os.unlink(temp_path)
    
    @pytest.fixture
    def large_temp_file(self):
        """Create a large temporary file for streaming tests."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8') as f:
            # Create 5MB file
            for i in range(100000):
                f.write(f"This is line {i} with some content to make it longer.\n")
            temp_path = f.name
        
        yield temp_path
        
        # Cleanup
        os.unlink(temp_path)
    
    def test_file_processing(self, temp_file):
        """Test basic file processing."""
        config = WindowConfig(size=100)
        engine = DefaultSlidingWindowEngine(config)
        
        windows = list(engine.process_file(temp_file))
        
        assert len(windows) > 0
        assert all(isinstance(w, Window) for w in windows)
    
    def test_large_file_streaming(self, large_temp_file):
        """Test streaming processing for large files."""
        config = WindowConfig(size=1000)
        engine = DefaultSlidingWindowEngine(config)
        
        # Process file in streaming mode
        window_count = 0
        for window in engine.process_file(large_temp_file):
            window_count += 1
            assert isinstance(window, Window)
            assert len(window.content) > 0
        
        assert window_count > 0
    
    def test_file_not_found(self):
        """Test handling of non-existent files."""
        config = WindowConfig(size=100)
        engine = DefaultSlidingWindowEngine(config)
        
        with pytest.raises(FileNotFoundError):
            list(engine.process_file("/nonexistent/file.txt"))


class TestWindowNavigator:
    """Test window navigation functionality."""
    
    @pytest.fixture
    def navigator(self):
        """Create a navigator with test data."""
        text = "\n".join([f"Line {i}" for i in range(100)])
        config = WindowConfig(size=200)
        engine = DefaultSlidingWindowEngine(config)
        return DefaultWindowNavigator(engine, text)
    
    def test_navigation_forward(self, navigator):
        """Test forward navigation."""
        first = navigator.current_window()
        assert first is not None
        assert first.position.window_index == 0
        
        second = navigator.next_window()
        assert second is not None
        assert second.position.window_index == 1
        
        # Continue until end
        while navigator.has_next():
            window = navigator.next_window()
            assert window is not None
        
        # No more windows
        assert navigator.next_window() is None
    
    def test_navigation_backward(self, navigator):
        """Test backward navigation."""
        # Go to end
        while navigator.has_next():
            navigator.next_window()
        
        # Navigate backward
        while navigator.has_previous():
            window = navigator.previous_window()
            assert window is not None
        
        # At beginning
        assert navigator.previous_window() is None
        assert navigator.current_window().position.window_index == 0
    
    def test_jump_to_window(self, navigator):
        """Test jumping to specific window."""
        total = navigator.total_windows
        
        # Jump to middle
        middle = total // 2
        window = navigator.jump_to_window(middle)
        assert window is not None
        assert window.position.window_index == middle
        
        # Jump to last
        last = navigator.jump_to_window(total - 1)
        assert last is not None
        assert last.position.window_index == total - 1
        
        # Invalid jumps
        assert navigator.jump_to_window(-1) is None
        assert navigator.jump_to_window(total + 1) is None
    
    def test_jump_to_position(self, navigator):
        """Test jumping to position."""
        # Jump to various positions
        positions = [0, 100, 200, 300]
        
        for pos in positions:
            window = navigator.jump_to_position(pos)
            if window:
                assert window.position.start <= pos < window.position.end
    
    def test_reset(self, navigator):
        """Test reset functionality."""
        # Navigate somewhere
        navigator.jump_to_window(5)
        assert navigator.current_index == 5
        
        # Reset
        navigator.reset()
        assert navigator.current_index == 0
        assert navigator.current_window().position.window_index == 0
    
    def test_search_windows(self, navigator):
        """Test searching within windows."""
        indices = navigator.find_windows_containing("Line 50")
        assert len(indices) > 0
        
        # Case insensitive search
        indices_ci = navigator.find_windows_containing("line 50", case_sensitive=False)
        assert len(indices_ci) >= len(indices)
    
    def test_window_range(self, navigator):
        """Test getting range of windows."""
        # Get first 3 windows
        first_three = navigator.get_window_range(0, 3)
        assert len(first_three) == 3
        assert all(w.position.window_index == i for i, w in enumerate(first_three))
        
        # Get remaining windows
        remaining = navigator.get_window_range(3)
        assert len(remaining) == navigator.total_windows - 3


class TestStreamingNavigator:
    """Test streaming navigator for large files."""
    
    @pytest.fixture
    def streaming_navigator(self, temp_file):
        """Create a streaming navigator."""
        config = WindowConfig(size=100)
        engine = DefaultSlidingWindowEngine(config)
        return StreamingWindowNavigator(engine, temp_file)
    
    def test_streaming_navigation(self, streaming_navigator):
        """Test basic streaming navigation."""
        # Get first window
        first = streaming_navigator.next_window()
        assert first is not None
        assert first.position.window_index == 0
        
        # Get next windows
        second = streaming_navigator.next_window()
        assert second is not None
        assert second.position.window_index == 1
        
        # Go back
        prev = streaming_navigator.previous_window()
        assert prev is not None
        assert prev.position.window_index == 0
    
    def test_streaming_jump(self, streaming_navigator):
        """Test jumping in streaming mode."""
        # Jump to window 5
        window = streaming_navigator.jump_to_window(5)
        assert window is not None
        assert window.position.window_index == 5
        
        # Current should be updated
        current = streaming_navigator.current_window()
        assert current.position.window_index == 5
    
    def test_streaming_cache(self, streaming_navigator):
        """Test that streaming navigator caches windows."""
        # Navigate forward
        windows = []
        for _ in range(5):
            window = streaming_navigator.next_window()
            if window:
                windows.append(window)
        
        # Go back - should use cache
        for _ in range(3):
            streaming_navigator.previous_window()
        
        # Should be at window 2
        current = streaming_navigator.current_window()
        assert current.position.window_index == 2


class TestUtilityFunctions:
    """Test utility functions."""
    
    def test_merge_overlapping_windows(self):
        """Test merging overlapping windows."""
        # Create overlapping windows
        windows = [
            Window(
                content="Content 1",
                position=WindowPosition(0, 10, 1, 1, 0)
            ),
            Window(
                content="Content 2",
                position=WindowPosition(8, 18, 1, 2, 1)
            ),
            Window(
                content="Content 3", 
                position=WindowPosition(20, 30, 3, 3, 2)
            )
        ]
        
        # Merge without preserving overlap
        merged = merge_overlapping_windows(windows, preserve_overlap=False)
        assert len(merged) == 2  # First two should be merged
        
        # Merge with preserving overlap
        merged_preserve = merge_overlapping_windows(windows, preserve_overlap=True)
        assert len(merged_preserve) == 3  # All windows preserved
        assert "overlap_with_next" in merged_preserve[0].metadata
    
    def test_calculate_window_statistics(self):
        """Test window statistics calculation."""
        windows = [
            Window(
                content="x" * 50,
                position=WindowPosition(0, 50, 1, 1, 0, 3),
                metadata={"overlap_chars": 0}
            ),
            Window(
                content="y" * 60,
                position=WindowPosition(40, 100, 2, 2, 1, 3),
                metadata={"overlap_chars": 10}
            ),
            Window(
                content="z" * 40,
                position=WindowPosition(90, 130, 3, 3, 2, 3),
                metadata={"overlap_chars": 10}
            )
        ]
        
        stats = calculate_window_statistics(windows)
        
        assert stats["total_windows"] == 3
        assert stats["average_size"] == 50
        assert stats["min_size"] == 40
        assert stats["max_size"] == 60
        assert stats["total_overlap"] == 20
    
    def test_optimize_window_config(self):
        """Test window configuration optimization."""
        text = "x" * 1000
        
        # Optimize for 10 windows
        config = optimize_window_config(text, target_windows=10)
        
        assert config.size == 100  # 1000 / 10
        assert config.overlap == 10  # 10% of size
        assert config.unit == WindowUnit.CHARACTERS
    
    def test_find_natural_boundaries(self):
        """Test finding natural boundaries."""
        text = """First paragraph.

Second paragraph with more content.

Third paragraph here.

Fourth paragraph."""
        
        boundaries = find_natural_boundaries(text, preferred_size=30)
        
        assert 0 in boundaries
        assert len(text) in boundaries
        # Should find paragraph boundaries
        assert any(text[b-2:b] == "\n\n" for b in boundaries[1:-1])
    
    def test_validate_window_coverage(self):
        """Test window coverage validation."""
        text = "x" * 100
        
        # Valid windows
        valid_windows = [
            Window(
                content=text[0:50],
                position=WindowPosition(0, 50, 1, 1, 0)
            ),
            Window(
                content=text[40:100],
                position=WindowPosition(40, 100, 1, 2, 1),
                metadata={"overlap_chars": 10}
            )
        ]
        
        is_valid, issues = validate_window_coverage(valid_windows, len(text))
        assert is_valid
        assert len(issues) == 0
        
        # Windows with gap
        gap_windows = [
            Window(
                content=text[0:40],
                position=WindowPosition(0, 40, 1, 1, 0)
            ),
            Window(
                content=text[50:100],
                position=WindowPosition(50, 100, 1, 2, 1),
                metadata={"overlap_chars": 0}
            )
        ]
        
        is_valid, issues = validate_window_coverage(gap_windows, len(text))
        assert not is_valid
        assert any("Gap" in issue for issue in issues)


class TestEdgeCases:
    """Test edge cases and error conditions."""
    
    def test_unicode_handling(self):
        """Test handling of Unicode text."""
        text = "Hello 世界! 🌍 Émojis and ñiños"
        config = WindowConfig(size=10, unit=WindowUnit.CHARACTERS)
        engine = DefaultSlidingWindowEngine(config)
        
        windows = list(engine.process_text(text))
        
        assert len(windows) > 0
        # Ensure Unicode is preserved
        full_text = "".join(w.content for w in windows)
        assert "世界" in full_text
        assert "🌍" in full_text
    
    def test_very_long_lines(self):
        """Test handling of very long lines."""
        text = "x" * 10000 + "\n" + "y" * 10000
        config = WindowConfig(
            size=1000,
            preserve_boundaries=True
        )
        engine = DefaultSlidingWindowEngine(config)
        
        windows = list(engine.process_text(text))
        
        assert len(windows) > 2
        # Should handle long lines gracefully
        assert all(len(w.content) <= 1100 for w in windows)  # Some boundary flexibility
    
    def test_only_whitespace(self):
        """Test handling of whitespace-only text."""
        text = "   \n\n\t\t   \n   "
        config = WindowConfig(size=5, trim_whitespace=True)
        engine = DefaultSlidingWindowEngine(config)
        
        windows = list(engine.process_text(text))
        
        # Should produce no windows when trimming whitespace
        assert len(windows) == 0
    
    def test_single_character_windows(self):
        """Test extremely small window sizes."""
        text = "abcdef"
        config = WindowConfig(size=1, unit=WindowUnit.CHARACTERS)
        engine = DefaultSlidingWindowEngine(config)
        
        windows = list(engine.process_text(text))
        
        assert len(windows) == 6
        assert all(len(w.content) == 1 for w in windows)
    
    def test_overlap_larger_than_window(self):
        """Test overlap larger than window size."""
        config = WindowConfig(
            size=10,
            overlap=15,
            overlap_strategy=OverlapStrategy.FIXED
        )
        engine = DefaultSlidingWindowEngine(config)
        
        text = "x" * 100
        windows = list(engine.process_text(text))
        
        # Should handle gracefully by limiting overlap
        assert all(w.metadata.get("overlap_chars", 0) < 10 for w in windows)
    
    def test_concurrent_access(self):
        """Test thread safety of the engine."""
        import threading
        
        text = "x" * 1000
        config = WindowConfig(size=100)
        engine = DefaultSlidingWindowEngine(config)
        
        results = []
        
        def process():
            windows = list(engine.process_text(text))
            results.append(len(windows))
        
        # Run multiple threads
        threads = []
        for _ in range(5):
            t = threading.Thread(target=process)
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        # All threads should get same result
        assert len(set(results)) == 1
"""Utility functions for sliding window processing."""

from typing import List, Tuple, Optional, Dict, Any
import re
from pathlib import Path

from ..interfaces.sliding_window import Window, WindowConfig, WindowUnit, OverlapStrategy


def merge_overlapping_windows(windows: List[Window], 
                            preserve_overlap: bool = False) -> List[Window]:
    """
    Merge overlapping windows to remove duplicate content.
    
    Args:
        windows: List of windows to merge
        preserve_overlap: If True, keep overlap regions marked
        
    Returns:
        List of merged windows
    """
    if not windows:
        return []
    
    merged = []
    current = windows[0]
    
    for next_window in windows[1:]:
        # Check if windows overlap
        if current.position.end > next_window.position.start:
            if preserve_overlap:
                # Mark the overlapping region in metadata
                overlap_start = next_window.position.start
                overlap_end = current.position.end
                overlap_size = overlap_end - overlap_start
                
                current.metadata["overlap_with_next"] = overlap_size
                next_window.metadata["overlap_with_previous"] = overlap_size
                
                merged.append(current)
                current = next_window
            else:
                # Merge windows by extending current window
                current.position.end = next_window.position.end
                current.content += next_window.content[
                    current.position.end - next_window.position.start:
                ]
                current.position.end_line = next_window.position.end_line
        else:
            # No overlap, add current and move to next
            merged.append(current)
            current = next_window
    
    # Don't forget the last window
    merged.append(current)
    
    return merged


def calculate_window_statistics(windows: List[Window]) -> Dict[str, Any]:
    """
    Calculate statistics about a set of windows.
    
    Args:
        windows: List of windows to analyze
        
    Returns:
        Dictionary with statistics
    """
    if not windows:
        return {
            "total_windows": 0,
            "total_characters": 0,
            "average_size": 0,
            "min_size": 0,
            "max_size": 0,
            "total_overlap": 0,
            "coverage_ratio": 0
        }
    
    sizes = [len(w.content) for w in windows]
    overlaps = [w.metadata.get("overlap_chars", 0) for w in windows[1:]]
    
    total_chars = sum(sizes)
    total_text_length = windows[-1].position.end - windows[0].position.start
    
    return {
        "total_windows": len(windows),
        "total_characters": total_chars,
        "average_size": total_chars / len(windows),
        "min_size": min(sizes),
        "max_size": max(sizes),
        "total_overlap": sum(overlaps),
        "coverage_ratio": total_chars / total_text_length if total_text_length > 0 else 0,
        "size_variance": calculate_variance(sizes),
        "size_std_dev": calculate_std_dev(sizes)
    }


def calculate_variance(values: List[float]) -> float:
    """Calculate variance of a list of values."""
    if not values:
        return 0.0
    mean = sum(values) / len(values)
    return sum((x - mean) ** 2 for x in values) / len(values)


def calculate_std_dev(values: List[float]) -> float:
    """Calculate standard deviation of a list of values."""
    return calculate_variance(values) ** 0.5


def optimize_window_config(text: str, target_windows: int, 
                          unit: WindowUnit = WindowUnit.CHARACTERS) -> WindowConfig:
    """
    Calculate optimal window configuration for a given text and target window count.
    
    Args:
        text: The text to process
        target_windows: Desired number of windows
        unit: The unit to use for window sizing
        
    Returns:
        Optimized WindowConfig
    """
    text_length = len(text)
    
    if unit == WindowUnit.CHARACTERS:
        # Simple calculation for character-based windows
        window_size = max(1, text_length // target_windows)
        overlap = int(window_size * 0.1)  # 10% overlap
    
    elif unit == WindowUnit.LINES:
        line_count = text.count('\n') + 1
        window_size = max(1, line_count // target_windows)
        overlap = max(1, int(window_size * 0.1))
    
    elif unit == WindowUnit.TOKENS:
        # Rough estimation
        estimated_tokens = text_length // 4
        window_size = max(1, estimated_tokens // target_windows)
        overlap = int(window_size * 0.1)
    
    else:  # BYTES
        window_size = max(1, text_length // target_windows)
        overlap = int(window_size * 0.1)
    
    return WindowConfig(
        size=window_size,
        unit=unit,
        overlap=overlap,
        overlap_strategy=OverlapStrategy.FIXED,
        preserve_boundaries=True,
        trim_whitespace=True
    )


def find_natural_boundaries(text: str, 
                           preferred_size: int,
                           tolerance: float = 0.2) -> List[int]:
    """
    Find natural boundaries (paragraphs, sections) in text near preferred positions.
    
    Args:
        text: The text to analyze
        preferred_size: Preferred window size
        tolerance: How much to deviate from preferred size (0.2 = 20%)
        
    Returns:
        List of boundary positions
    """
    boundaries = [0]
    
    # Find all paragraph boundaries
    paragraph_pattern = re.compile(r'\n\s*\n')
    paragraph_boundaries = [m.end() for m in paragraph_pattern.finditer(text)]
    
    # Find section boundaries (e.g., markdown headers, code blocks)
    section_patterns = [
        re.compile(r'\n#{1,6}\s+.*\n'),  # Markdown headers
        re.compile(r'\n```.*\n'),  # Code block starts
        re.compile(r'\n---+\n'),  # Horizontal rules
    ]
    
    section_boundaries = []
    for pattern in section_patterns:
        section_boundaries.extend([m.start() for m in pattern.finditer(text)])
    
    # Combine and sort all boundaries
    all_boundaries = sorted(set(paragraph_boundaries + section_boundaries))
    
    # Select boundaries close to preferred positions
    current_pos = 0
    tolerance_range = int(preferred_size * tolerance)
    
    while current_pos < len(text):
        target_pos = current_pos + preferred_size
        
        # Find boundaries within tolerance range
        candidates = [
            b for b in all_boundaries 
            if target_pos - tolerance_range <= b <= target_pos + tolerance_range
            and b > current_pos
        ]
        
        if candidates:
            # Choose the closest boundary
            chosen = min(candidates, key=lambda x: abs(x - target_pos))
            boundaries.append(chosen)
            current_pos = chosen
        else:
            # No natural boundary found, use target position
            if target_pos < len(text):
                boundaries.append(target_pos)
            current_pos = target_pos
    
    # Add end position
    if boundaries[-1] < len(text):
        boundaries.append(len(text))
    
    return boundaries


def create_windows_from_boundaries(text: str, boundaries: List[int], 
                                 overlap_size: int = 0) -> List[Window]:
    """
    Create windows from a list of boundary positions.
    
    Args:
        text: The source text
        boundaries: List of boundary positions
        overlap_size: Size of overlap between windows
        
    Returns:
        List of Window objects
    """
    windows = []
    
    for i in range(len(boundaries) - 1):
        start = boundaries[i]
        end = boundaries[i + 1]
        
        # Apply overlap from previous window
        if i > 0 and overlap_size > 0:
            start = max(boundaries[i] - overlap_size, boundaries[i - 1])
        
        content = text[start:end].strip()
        if not content:
            continue
        
        # Count lines
        lines_before = text[:start].count('\n')
        lines_in_window = content.count('\n')
        
        position = WindowPosition(
            start=start,
            end=end,
            start_line=lines_before + 1,
            end_line=lines_before + lines_in_window + 1,
            window_index=len(windows),
            total_windows=len(boundaries) - 1
        )
        
        metadata = {
            "boundary_based": True,
            "overlap_size": overlap_size if i > 0 else 0
        }
        
        windows.append(Window(content=content, position=position, metadata=metadata))
    
    return windows


def validate_window_coverage(windows: List[Window], text_length: int) -> Tuple[bool, List[str]]:
    """
    Validate that windows provide complete coverage of the text.
    
    Args:
        windows: List of windows to validate
        text_length: Total length of the source text
        
    Returns:
        Tuple of (is_valid, list_of_issues)
    """
    issues = []
    
    if not windows:
        return False, ["No windows provided"]
    
    # Check for gaps
    for i in range(len(windows) - 1):
        current = windows[i]
        next_window = windows[i + 1]
        
        # Account for overlap
        overlap = next_window.metadata.get("overlap_chars", 0)
        expected_start = current.position.end - overlap
        
        if next_window.position.start > expected_start:
            gap_size = next_window.position.start - expected_start
            issues.append(
                f"Gap of {gap_size} characters between windows {i} and {i+1}"
            )
    
    # Check coverage
    if windows[0].position.start > 0:
        issues.append(f"First window starts at position {windows[0].position.start}, not 0")
    
    if windows[-1].position.end < text_length:
        issues.append(
            f"Last window ends at position {windows[-1].position.end}, "
            f"not {text_length}"
        )
    
    # Check for invalid positions
    for i, window in enumerate(windows):
        if window.position.start >= window.position.end:
            issues.append(f"Window {i} has invalid position range")
        
        if window.position.start < 0 or window.position.end > text_length:
            issues.append(f"Window {i} has out-of-bounds positions")
    
    return len(issues) == 0, issues


# Import WindowPosition for the utility functions
from ..interfaces.sliding_window import WindowPosition
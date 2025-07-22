#!/usr/bin/env python3
"""Direct test of overlapping fallback chunker without full module imports."""

import sys
import os

# Test the overlapping chunker directly
def test_overlapping():
    # Import only the specific modules we need
    from chunker.types import CodeChunk
    from chunker.interfaces.fallback_overlap import OverlapStrategy
    from chunker.interfaces.fallback import FallbackConfig, ChunkingMethod, FallbackReason
    
    # Import the base fallback chunker
    from chunker.fallback.base import FallbackChunker
    
    # Now import our overlapping chunker
    from chunker.fallback.overlapping import OverlappingFallbackChunker, OverlapConfig
    
    print("Successfully imported OverlappingFallbackChunker!")
    
    # Create test content
    test_content = """Line 1: This is the first line
Line 2: This is the second line
Line 3: This is the third line
Line 4: This is the fourth line
Line 5: This is the fifth line
Line 6: This is the sixth line
Line 7: This is the seventh line
Line 8: This is the eighth line
Line 9: This is the ninth line
Line 10: This is the tenth line"""
    
    # Create chunker
    chunker = OverlappingFallbackChunker()
    print("\nCreated chunker instance")
    
    # Test fixed overlap by lines
    print("\n=== Testing Fixed Overlap by Lines ===")
    chunks = chunker.chunk_with_overlap(
        content=test_content,
        file_path="test.txt",
        chunk_size=3,  # 3 lines per chunk
        overlap_size=1,  # 1 line overlap
        strategy=OverlapStrategy.FIXED,
        unit="lines"
    )
    
    print(f"Generated {len(chunks)} chunks")
    for i, chunk in enumerate(chunks):
        print(f"\nChunk {i + 1}:")
        print(f"  Lines: {chunk.start_line}-{chunk.end_line}")
        print(f"  Content preview: {chunk.content[:50]}...")
    
    # Test overlap exists
    if len(chunks) >= 2:
        chunk1_lines = chunks[0].content.splitlines()
        chunk2_lines = chunks[1].content.splitlines()
        print(f"\nOverlap check:")
        print(f"  Last line of chunk 1: {chunk1_lines[-1]}")
        print(f"  First line of chunk 2: {chunk2_lines[0]}")
        print(f"  Overlap exists: {chunk1_lines[-1] == chunk2_lines[0]}")
    
    # Test character-based overlap
    print("\n=== Testing Fixed Overlap by Characters ===")
    chunks_char = chunker.chunk_with_overlap(
        content=test_content,
        file_path="test.txt",
        chunk_size=50,
        overlap_size=10,
        strategy=OverlapStrategy.FIXED,
        unit="characters"
    )
    
    print(f"Generated {len(chunks_char)} chunks")
    for i, chunk in enumerate(chunks_char):
        print(f"\nChunk {i + 1}:")
        print(f"  Size: {len(chunk.content)} chars")
        print(f"  Content: {repr(chunk.content[:30])}...")
    
    # Test asymmetric overlap
    print("\n=== Testing Asymmetric Overlap ===")
    chunks_asym = chunker.chunk_with_asymmetric_overlap(
        content=test_content,
        file_path="test.txt",
        chunk_size=3,
        overlap_before=1,
        overlap_after=2,
        unit="lines"
    )
    
    print(f"Generated {len(chunks_asym)} chunks")
    for i, chunk in enumerate(chunks_asym):
        lines = chunk.content.splitlines()
        print(f"\nChunk {i + 1}: {len(lines)} lines")
    
    # Test natural boundary detection
    print("\n=== Testing Natural Boundary Detection ===")
    test_text = "This is a sentence. Another sentence here.\n\nNew paragraph starts here."
    boundary = chunker.find_natural_overlap_boundary(test_text, 25, 10)
    print(f"Desired position: 25")
    print(f"Found boundary at: {boundary}")
    print(f"Character at boundary: {repr(test_text[boundary-1:boundary+1])}")
    
    print("\n✅ All tests completed successfully!")


if __name__ == "__main__":
    test_overlapping()
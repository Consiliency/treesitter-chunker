"""Simple demonstration of incremental processing components."""

import tempfile
from pathlib import Path

from chunker import (
    DefaultChangeDetector,
    DefaultChunkCache,
    DefaultIncrementalProcessor,
    SimpleIncrementalIndex,
)
from chunker.interfaces.incremental import ChangeType, ChunkChange, ChunkDiff
from chunker.types import CodeChunk


def create_sample_chunks():
    """Create sample chunks for demonstration."""
    return [
        CodeChunk(
            language="python",
            file_path="example.py",
            node_type="function_definition",
            start_line=1,
            end_line=5,
            byte_start=0,
            byte_end=100,
            parent_context="",
            content="def hello():\n    print('Hello')\n    return True\n",
            chunk_id="func_hello",
        ),
        CodeChunk(
            language="python",
            file_path="example.py",
            node_type="function_definition",
            start_line=7,
            end_line=10,
            byte_start=101,
            byte_end=200,
            parent_context="",
            content="def process():\n    data = load()\n    return analyze(data)\n",
            chunk_id="func_process",
        ),
    ]


def demonstrate_change_detection():
    """Demonstrate change detection capabilities."""
    print("=== Change Detection Demo ===")

    detector = DefaultChangeDetector()

    # Original content
    original = """def hello():
    print('Hello')
    return True

def process():
    data = load()
    return analyze(data)
"""

    # Modified content
    modified = """def hello():
    print('Hello, World!')  # Modified
    return True

def process():
    # Added comment
    data = load()
    result = analyze(data)  # Changed variable name
    log_result(result)      # Added line
    return result           # Modified
"""

    # Compute hash to detect changes
    original_hash = detector.compute_file_hash(original)
    modified_hash = detector.compute_file_hash(modified)

    print(f"Original hash: {original_hash[:16]}...")
    print(f"Modified hash: {modified_hash[:16]}...")
    print(f"File changed: {original_hash != modified_hash}")

    # Find changed regions
    regions = detector.find_changed_regions(original, modified)
    print("\nChanged regions:")
    for start, end in regions:
        print(f"  Lines {start}-{end}")


def demonstrate_diff_computation():
    """Demonstrate diff computation between chunks."""
    print("\n=== Diff Computation Demo ===")

    DefaultIncrementalProcessor()

    # Original chunks
    old_chunks = create_sample_chunks()

    # Create modified chunks (simulating what would come from parsing)
    new_chunks = [
        CodeChunk(
            language="python",
            file_path="example.py",
            node_type="function_definition",
            start_line=1,
            end_line=5,
            byte_start=0,
            byte_end=120,
            parent_context="",
            content="def hello():\n    print('Hello, World!')\n    return True\n",
            chunk_id="func_hello",  # Same ID, modified content
        ),
        CodeChunk(
            language="python",
            file_path="example.py",
            node_type="function_definition",
            start_line=7,
            end_line=12,
            byte_start=121,
            byte_end=250,
            parent_context="",
            content="def process():\n    # Process data\n    data = load()\n    result = analyze(data)\n    return result\n",
            chunk_id="func_process",  # Same ID, modified content
        ),
        CodeChunk(
            language="python",
            file_path="example.py",
            node_type="function_definition",
            start_line=14,
            end_line=16,
            byte_start=251,
            byte_end=300,
            parent_context="",
            content="def cleanup():\n    clear_cache()\n",
            chunk_id="func_cleanup",  # New function
        ),
    ]

    # Manually create a diff (simulating what compute_diff would do)

    diff = ChunkDiff(
        changes=[
            ChunkChange(
                chunk_id="func_hello",
                change_type=ChangeType.MODIFIED,
                old_chunk=old_chunks[0],
                new_chunk=new_chunks[0],
                line_changes=[(2, 2)],
                confidence=0.9,
            ),
            ChunkChange(
                chunk_id="func_process",
                change_type=ChangeType.MODIFIED,
                old_chunk=old_chunks[1],
                new_chunk=new_chunks[1],
                line_changes=[(8, 12)],
                confidence=0.85,
            ),
            ChunkChange(
                chunk_id="func_cleanup",
                change_type=ChangeType.ADDED,
                old_chunk=None,
                new_chunk=new_chunks[2],
                line_changes=[(14, 16)],
                confidence=1.0,
            ),
        ],
        added_chunks=[new_chunks[2]],
        deleted_chunks=[],
        modified_chunks=[
            (old_chunks[0], new_chunks[0]),
            (old_chunks[1], new_chunks[1]),
        ],
        unchanged_chunks=[],
        summary={
            "total_old_chunks": 2,
            "total_new_chunks": 3,
            "added": 1,
            "deleted": 0,
            "modified": 2,
            "moved": 0,
            "unchanged": 0,
        },
    )

    print(f"Diff Summary: {diff.summary}")
    print("\nDetailed Changes:")
    for change in diff.changes:
        print(f"  - {change.change_type.value}: {change.chunk_id}")
        print(f"    Confidence: {change.confidence:.2f}")
        if change.line_changes:
            print(f"    Line changes: {change.line_changes}")


def demonstrate_cache():
    """Demonstrate cache functionality."""
    print("\n=== Cache Demo ===")

    with tempfile.TemporaryDirectory() as temp_dir:
        cache = DefaultChunkCache(Path(temp_dir) / ".cache")

        # Store chunks
        chunks = create_sample_chunks()
        cache.store("example.py", chunks, "hash123", metadata={"version": "1.0"})
        print("Stored 2 chunks in cache")

        # Retrieve with correct hash
        entry = cache.retrieve("example.py", "hash123")
        print(f"Retrieved {len(entry.chunks)} chunks with correct hash")

        # Try with wrong hash
        wrong_entry = cache.retrieve("example.py", "wronghash")
        print(f"Retrieved with wrong hash: {wrong_entry is None}")

        # Get statistics
        stats = cache.get_statistics()
        print("\nCache Statistics:")
        print(f"  Entries: {stats['entries']}")
        print(f"  Hit rate: {stats['hit_rate']:.0%}")
        print(f"  Total retrievals: {stats['stats']['retrievals']}")


def demonstrate_index():
    """Demonstrate incremental index functionality."""
    print("\n=== Incremental Index Demo ===")

    index = SimpleIncrementalIndex()
    chunks = create_sample_chunks()

    # Add chunks to index
    for chunk in chunks:
        index.update_chunk(None, chunk)

    print(f"Indexed {len(index.index)} chunks")

    # Search
    results = index.search("hello")
    print(f"\nSearch for 'hello': found {len(results)} results")
    for chunk_id in results:
        print(f"  - {chunk_id}")

    # Simulate updating a chunk
    modified_chunk = CodeChunk(
        language="python",
        file_path="example.py",
        node_type="function_definition",
        start_line=1,
        end_line=5,
        byte_start=0,
        byte_end=100,
        parent_context="",
        content="def hello():\n    print('Goodbye')\n    return False\n",
        chunk_id="func_hello",
    )

    index.update_chunk(chunks[0], modified_chunk)

    # Search again
    results = index.search("goodbye")
    print(f"\nSearch for 'goodbye': found {len(results)} results")

    # Check update log
    print(f"\nUpdate log has {len(index.update_log)} entries")


def demonstrate_move_detection():
    """Demonstrate code move detection."""
    print("\n=== Move Detection Demo ===")

    processor = DefaultIncrementalProcessor()

    # Function in original location
    old_chunk = CodeChunk(
        language="python",
        file_path="utils.py",
        node_type="function_definition",
        start_line=10,
        end_line=15,
        byte_start=200,
        byte_end=300,
        parent_context="",
        content="def helper_function():\n    '''Helper logic'''\n    return do_work()\n",
        chunk_id="utils_helper",
    )

    # Same function moved to different file and location
    new_chunk = CodeChunk(
        language="python",
        file_path="helpers.py",
        node_type="function_definition",
        start_line=25,
        end_line=30,
        byte_start=500,
        byte_end=600,
        parent_context="HelperClass",
        content="def helper_function():\n    '''Helper logic'''\n    return do_work()\n",
        chunk_id="helpers_helper",
    )

    # Detect move
    moved = processor.detect_moved_chunks([old_chunk], [new_chunk])

    if moved:
        print(f"Detected {len(moved)} moved chunks:")
        for old, new in moved:
            print(f"  - From {old.file_path}:{old.start_line}")
            print(f"    To {new.file_path}:{new.start_line}")
            print("    Similarity: Very High (same content)")
    else:
        print("No moves detected")


if __name__ == "__main__":
    demonstrate_change_detection()
    demonstrate_diff_computation()
    demonstrate_cache()
    demonstrate_index()
    demonstrate_move_detection()

    print("\n=== Demo Complete ===")
    print("This demonstrates the key components of incremental processing.")
    print("In real usage, these components work together to efficiently")
    print("process only the changed parts of large codebases.")

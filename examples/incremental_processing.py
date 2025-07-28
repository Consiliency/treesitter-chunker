"""Example of using incremental processing for efficient chunk updates."""

import os
import tempfile

from chunker import (
    DefaultChangeDetector,
    DefaultChunkCache,
    DefaultIncrementalProcessor,
    chunk_file,
)
from chunker.types import CodeChunk


def demonstrate_incremental_processing():
    """Demonstrate incremental processing workflow."""

    # Initialize components
    processor = DefaultIncrementalProcessor()
    cache = DefaultChunkCache()
    detector = DefaultChangeDetector()

    # Example: Processing a Python file
    initial_content = '''def hello():
    """Say hello."""
    print("Hello, World!")

def calculate(a, b):
    """Calculate sum."""
    return a + b

class Calculator:
    """Basic calculator."""

    def __init__(self):
        self.result = 0

    def add(self, value):
        """Add to result."""
        self.result += value
'''

    # Create a temporary file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(initial_content)
        file_path = f.name

    try:
        # Initial processing
        print("=== Initial Processing ===")
        initial_chunks = chunk_file(file_path, language="python")
        file_hash = detector.compute_file_hash(initial_content)

        # Cache the results
        cache.store(file_path, initial_chunks, file_hash)
        print(f"Cached {len(initial_chunks)} chunks")

        # Simulate file modification
        modified_content = '''def hello():
    """Say hello with name."""
    name = input("Enter name: ")
    print(f"Hello, {name}!")

def calculate(a, b, operation="+"):
    """Calculate with operation."""
    if operation == "+":
        return a + b
    elif operation == "-":
        return a - b
    return 0

class Calculator:
    """Advanced calculator."""

    def __init__(self):
        self.result = 0
        self.history = []

    def add(self, value):
        """Add to result and track history."""
        self.result += value
        self.history.append(f"Added {value}")

    def subtract(self, value):
        """Subtract from result."""
        self.result -= value
        self.history.append(f"Subtracted {value}")
'''

        # Write modified content
        with open(file_path, "w") as f:
            f.write(modified_content)

        # Check if file changed
        new_hash = detector.compute_file_hash(modified_content)

        if new_hash != file_hash:
            print("\n=== File Changed - Computing Diff ===")

            # Retrieve cached chunks
            cache_entry = cache.retrieve(file_path, file_hash)
            if cache_entry:
                old_chunks = cache_entry.chunks

                # Compute diff
                diff = processor.compute_diff(old_chunks, modified_content, "python")

                print("\nDiff Summary:")
                print(f"  Added chunks: {diff.summary['added']}")
                print(f"  Deleted chunks: {diff.summary['deleted']}")
                print(f"  Modified chunks: {diff.summary['modified']}")
                print(f"  Moved chunks: {diff.summary['moved']}")
                print(f"  Unchanged chunks: {diff.summary['unchanged']}")

                # Show specific changes
                print("\nDetailed Changes:")
                for change in diff.changes:
                    print(f"  - {change.change_type.value}: {change.chunk_id}")
                    if change.change_type.value == "modified":
                        print(f"    Line changes: {change.line_changes}")

                # Update chunks
                updated_chunks = processor.update_chunks(old_chunks, diff)

                # Cache updated results
                cache.store(file_path, updated_chunks, new_hash)
                print(f"\nUpdated cache with {len(updated_chunks)} chunks")

                # Show cache statistics
                stats = cache.get_statistics()
                print("\nCache Statistics:")
                print(f"  Entries: {stats['entries']}")
                print(f"  Size: {stats['total_size_mb']:.2f} MB")
                print(f"  Hit rate: {stats['hit_rate']:.2%}")

        # Demonstrate change detection
        print("\n=== Change Detection ===")
        regions = detector.find_changed_regions(initial_content, modified_content)
        print(f"Found {len(regions)} changed regions:")
        for start, end in regions:
            print(f"  Lines {start}-{end}")

    finally:
        # Cleanup
        os.unlink(file_path)


def demonstrate_cache_persistence():
    """Demonstrate cache export/import functionality."""
    print("\n=== Cache Persistence Demo ===")

    # Create sample chunks
    chunks = [
        CodeChunk(
            language="python",
            file_path="example.py",
            node_type="function_definition",
            start_line=1,
            end_line=3,
            byte_start=0,
            byte_end=50,
            parent_context="",
            content="def example():\n    pass\n",
        ),
    ]

    # Create and populate cache
    cache1 = DefaultChunkCache(".cache1")
    cache1.store("example.py", chunks, "hash123")

    # Export cache
    export_file = "cache_export.json"
    cache1.export_cache(export_file)
    print(f"Exported cache to {export_file}")

    # Import into new cache
    cache2 = DefaultChunkCache(".cache2")
    cache2.import_cache(export_file)
    print(f"Imported cache from {export_file}")

    # Verify
    entry = cache2.retrieve("example.py")
    if entry:
        print(f"Successfully retrieved {len(entry.chunks)} chunks from imported cache")

    # Cleanup
    import shutil

    shutil.rmtree(".cache1", ignore_errors=True)
    shutil.rmtree(".cache2", ignore_errors=True)
    os.unlink(export_file)


if __name__ == "__main__":
    demonstrate_incremental_processing()
    demonstrate_cache_persistence()

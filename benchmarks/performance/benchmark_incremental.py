"""Benchmarks for incremental parsing performance."""

import shutil
import tempfile
import time
from pathlib import Path

from chunker.performance.enhanced_chunker import EnhancedChunker
from chunker.performance.optimization.incremental import IncrementalParser


def create_large_file() -> tuple[Path, str]:
    """Create a large Python file for testing.

    Returns:
        Tuple of (file_path, original_content)
    """
    temp_dir = Path(tempfile.mkdtemp())
    file_path = temp_dir / "large_file.py"

    # Generate a large Python file
    functions = []
    for i in range(100):
        func = f'''
def function_{i}(param1, param2, param3):
    """Function {i} documentation.

    This is a longer docstring to make the file more realistic.
    It has multiple lines and describes what the function does.
    """
    result = param1 + param2

    if param3 > 0:
        for j in range(param3):
            result += j * 2
            if j % 10 == 0:
                print(f"Processing {{j}}")

    # Some more complex logic
    data = [x * 2 for x in range(100) if x % 2 == 0]
    mapped = {{str(x): x ** 2 for x in data}}

    return result + sum(mapped.values())
'''
        functions.append(func)

    content = '"""Large test file for incremental parsing."""\n\n' + "\n".join(
        functions,
    )
    file_path.write_text(content)

    return file_path, content


def make_small_change(file_path: Path, content: str) -> str:
    """Make a small change to the file.

    Args:
        file_path: Path to file
        content: Current content

    Returns:
        New content
    """
    # Change a function name and add a comment
    new_content = content.replace(
        "def function_50(param1, param2, param3):",
        "def function_50_modified(param1, param2, param3):",
    )
    new_content = new_content.replace(
        "# Some more complex logic",
        "# Some more complex logic\n    # Added comment",
        1,  # Only replace first occurrence
    )

    file_path.write_text(new_content, encoding="utf-8")
    return new_content


def make_medium_change(file_path: Path, content: str) -> str:
    """Make a medium-sized change to the file.

    Args:
        file_path: Path to file
        content: Current content

    Returns:
        New content
    """
    # Add a new function in the middle
    new_function = '''
def new_function_added(x, y, z):
    """Newly added function for testing."""
    result = x * y + z

    for i in range(10):
        result += i

    return result
'''

    lines = content.split("\n")
    # Insert around line 500
    lines.insert(500, new_function)
    new_content = "\n".join(lines)

    file_path.write_text(new_content, encoding="utf-8")
    return new_content


def make_large_change(file_path: Path, content: str) -> str:
    """Make a large change to the file.

    Args:
        file_path: Path to file
        content: Current content

    Returns:
        New content
    """
    # Replace multiple functions
    new_content = content

    for i in range(20, 30):
        old_func = f"def function_{i}(param1, param2, param3):"
        new_func = f"def modified_function_{i}(param1, param2, param3, param4=None):"
        new_content = new_content.replace(old_func, new_func)

    # Add a new class
    new_class = '''
class NewTestClass:
    """A new class added for testing."""

    def __init__(self):
        self.data = []

    def add_item(self, item):
        self.data.append(item)

    def process_all(self):
        return [x * 2 for x in self.data]
'''

    new_content = new_content + "\n\n" + new_class

    file_path.write_text(new_content, encoding="utf-8")
    return new_content


def benchmark_incremental_parsing():
    """Benchmark incremental parsing performance."""
    print("\nBenchmarking incremental parsing performance")
    print("=" * 70)

    file_path, original_content = create_large_file()

    try:
        # Initialize chunkers
        regular_chunker = EnhancedChunker(enable_incremental=False)
        incremental_chunker = EnhancedChunker(enable_incremental=True)

        # Initial parse (both should be similar)
        print("\n1. Initial parse:")

        start = time.perf_counter()
        regular_chunks = regular_chunker.chunk_file(file_path, "python")
        regular_time = time.perf_counter() - start
        print(f"   Regular: {regular_time:.3f}s ({len(regular_chunks)} chunks)")

        start = time.perf_counter()
        incremental_chunks = incremental_chunker.chunk_file(file_path, "python")
        incremental_time = time.perf_counter() - start
        print(
            f"   Incremental: {incremental_time:.3f}s ({len(incremental_chunks)} chunks)",
        )

        # Test small change
        print("\n2. Small change (modify function name + add comment):")
        new_content = make_small_change(file_path, original_content)

        start = time.perf_counter()
        regular_chunks = regular_chunker.chunk_file(
            file_path,
            "python",
            force_reparse=True,
        )
        regular_time = time.perf_counter() - start
        print(f"   Regular reparse: {regular_time:.3f}s")

        start = time.perf_counter()
        incremental_chunks = incremental_chunker.chunk_file_incremental(
            file_path,
            "python",
        )
        incremental_time = time.perf_counter() - start
        print(f"   Incremental: {incremental_time:.3f}s")
        print(f"   Speedup: {regular_time / incremental_time:.2f}x")

        # Test medium change
        print("\n3. Medium change (add new function):")
        new_content = make_medium_change(file_path, new_content)

        start = time.perf_counter()
        regular_chunks = regular_chunker.chunk_file(
            file_path,
            "python",
            force_reparse=True,
        )
        regular_time = time.perf_counter() - start
        print(f"   Regular reparse: {regular_time:.3f}s")

        start = time.perf_counter()
        incremental_chunks = incremental_chunker.chunk_file_incremental(
            file_path,
            "python",
        )
        incremental_time = time.perf_counter() - start
        print(f"   Incremental: {incremental_time:.3f}s")
        print(f"   Speedup: {regular_time / incremental_time:.2f}x")

        # Test large change
        print("\n4. Large change (modify 10 functions + add class):")
        new_content = make_large_change(file_path, new_content)

        start = time.perf_counter()
        regular_chunks = regular_chunker.chunk_file(
            file_path,
            "python",
            force_reparse=True,
        )
        regular_time = time.perf_counter() - start
        print(f"   Regular reparse: {regular_time:.3f}s")

        start = time.perf_counter()
        incremental_chunks = incremental_chunker.chunk_file_incremental(
            file_path,
            "python",
        )
        incremental_time = time.perf_counter() - start
        print(f"   Incremental: {incremental_time:.3f}s")
        print(f"   Speedup: {regular_time / incremental_time:.2f}x")

        # Get statistics
        stats = incremental_chunker.get_stats()
        metrics = stats["metrics"]

        print("\n5. Incremental parsing statistics:")
        if "incremental.success" in metrics:
            print(
                f"   Successful incremental parses: {metrics['incremental.success']['count']}",
            )
        if "incremental.no_change" in metrics:
            print(
                f"   No-change detections: {metrics['incremental.no_change']['count']}",
            )

    finally:
        # Cleanup
        shutil.rmtree(file_path.parent)


def benchmark_change_detection():
    """Benchmark change detection performance."""
    print("\nBenchmarking change detection performance")
    print("=" * 70)

    parser = IncrementalParser()

    # Test different file sizes
    sizes = [1000, 10000, 100000]  # Lines

    for size in sizes:
        # Create content
        lines = [f"line {i}: some content here" for i in range(size)]
        old_content = "\n".join(lines).encode()

        # Make changes at different positions
        positions = ["start", "middle", "end"]

        print(f"\n{size} lines file:")

        for pos in positions:
            if pos == "start":
                new_lines = lines.copy()
                new_lines[10] = "line 10: CHANGED CONTENT"
            elif pos == "middle":
                new_lines = lines.copy()
                mid = len(lines) // 2
                new_lines[mid] = f"line {mid}: CHANGED CONTENT"
            else:  # end
                new_lines = lines.copy()
                new_lines[-10] = f"line {len(lines) - 10}: CHANGED CONTENT"

            new_content = "\n".join(new_lines).encode()

            # Time change detection
            start = time.perf_counter()
            changes = parser.detect_changes(old_content, new_content)
            elapsed = time.perf_counter() - start

            print(
                f"   Change at {pos}: {elapsed * 1000:.3f}ms ({len(changes)} changes)",
            )


def benchmark_incremental_accuracy():
    """Verify that incremental parsing produces correct results."""
    print("\nVerifying incremental parsing accuracy")
    print("=" * 70)

    file_path, content = create_large_file()

    try:
        regular_chunker = EnhancedChunker(enable_incremental=False)
        incremental_chunker = EnhancedChunker(enable_incremental=True)

        # Initial parse
        regular_chunks = regular_chunker.chunk_file(file_path, "python")
        incremental_chunks = incremental_chunker.chunk_file(file_path, "python")

        print("\n1. Initial parse comparison:")
        print(f"   Regular chunks: {len(regular_chunks)}")
        print(f"   Incremental chunks: {len(incremental_chunks)}")
        print(f"   Match: {len(regular_chunks) == len(incremental_chunks)}")

        # Make changes and compare
        changes = [
            ("small", make_small_change),
            ("medium", make_medium_change),
            ("large", make_large_change),
        ]

        for change_type, change_func in changes:
            content = change_func(file_path, content)

            regular_chunks = regular_chunker.chunk_file(
                file_path,
                "python",
                force_reparse=True,
            )
            incremental_chunks = incremental_chunker.chunk_file_incremental(
                file_path,
                "python",
            )

            print(f"\n2. After {change_type} change:")
            print(f"   Regular chunks: {len(regular_chunks)}")
            print(f"   Incremental chunks: {len(incremental_chunks)}")
            print(f"   Match: {len(regular_chunks) == len(incremental_chunks)}")

            # Compare chunk types
            regular_types = sorted([c.node_type for c in regular_chunks])
            incremental_types = sorted([c.node_type for c in incremental_chunks])

            if regular_types == incremental_types:
                print("   Chunk types match: ✓")
            else:
                print("   Chunk types match: ✗")
                print(f"   Difference: {set(regular_types) ^ set(incremental_types)}")

    finally:
        # Cleanup
        shutil.rmtree(file_path.parent)


if __name__ == "__main__":
    # Run benchmarks
    benchmark_incremental_parsing()
    benchmark_change_detection()
    benchmark_incremental_accuracy()

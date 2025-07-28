"""Example demonstrating Virtual File System support in Tree-sitter Chunker."""

from chunker import CompositeFileSystem, InMemoryFileSystem, VFSChunker, optimized_gc


def example_in_memory_vfs():
    """Example: Chunking from in-memory files."""
    print("=== In-Memory VFS Example ===")

    # Create in-memory file system
    vfs = InMemoryFileSystem()

    # Add some Python files
    vfs.add_file(
        "main.py",
        """
def main():
    '''Main entry point.'''
    print("Hello, World!")

class Application:
    def __init__(self):
        self.name = "MyApp"

    def run(self):
        print(f"Running {self.name}")
""",
    )

    vfs.add_file(
        "utils.py",
        """
def calculate_sum(a, b):
    '''Calculate sum of two numbers.'''
    return a + b

def calculate_product(a, b):
    '''Calculate product of two numbers.'''
    return a * b
""",
    )

    # Create chunker with VFS
    chunker = VFSChunker(vfs)

    # Chunk files
    for file_path in ["main.py", "utils.py"]:
        print(f"\nChunking {file_path}:")
        chunks = chunker.chunk_file(file_path, language="python")

        for chunk in chunks:
            print(f"  - {chunk.node_type}: Line {chunk.start_line}-{chunk.end_line}")
            print(f"    Content: {chunk.content.strip()[:50]}...")


def example_zip_vfs():
    """Example: Chunking from ZIP archives."""
    print("\n=== ZIP VFS Example ===")

    # This would chunk a file from a ZIP archive
    # chunks = chunk_from_zip("project.zip", "src/main.py", language="python")
    print("(ZIP example - requires actual ZIP file)")


def example_composite_vfs():
    """Example: Composite file system with multiple sources."""
    print("\n=== Composite VFS Example ===")

    # Create composite file system
    composite = CompositeFileSystem()

    # Mount in-memory FS at /memory
    memory_fs = InMemoryFileSystem()
    memory_fs.add_file("test.py", "def test(): pass")
    composite.mount("/memory", memory_fs)

    # Could also mount other file systems
    # composite.mount("/local", LocalFileSystem("/path/to/project"))
    # composite.mount("/archive", ZipFileSystem("archive.zip"))

    # Create chunker
    chunker = VFSChunker(composite)

    # Chunk from composite FS
    chunks = chunker.chunk_file("/memory/test.py", language="python")
    print(f"Found {len(chunks)} chunks in composite VFS")


def example_gc_optimization():
    """Example: Using GC optimization for batch processing."""
    print("\n=== GC Optimization Example ===")

    # Create in-memory VFS with many files
    vfs = InMemoryFileSystem()

    # Add 100 files
    for i in range(100):
        vfs.add_file(f"file_{i}.py", f"def function_{i}():\n    return {i}")

    chunker = VFSChunker(vfs)

    # Process with optimized GC
    with optimized_gc("batch"):
        chunks_total = 0

        # Process all files
        for result in chunker.chunk_directory("/", file_patterns=["*.py"]):
            file_path, chunks = result
            chunks_total += len(chunks)

        print(f"Processed 100 files, found {chunks_total} chunks")
        print("(GC was optimized for batch processing)")


def example_streaming_large_files():
    """Example: Streaming for large files."""
    print("\n=== Streaming Example ===")

    # Create a large file in memory
    vfs = InMemoryFileSystem()

    # Generate large content
    large_content = []
    for i in range(1000):
        large_content.append(
            f"""
def function_{i}(x, y):
    '''Function number {i}.'''
    result = x + y + {i}
    return result
""",
        )

    vfs.add_file("large_file.py", "\n".join(large_content))

    # Chunk with streaming
    chunker = VFSChunker(vfs)
    chunks = chunker.chunk_file("large_file.py", language="python", streaming=True)

    # Process chunks as stream
    chunk_count = 0
    for chunk in chunks:
        chunk_count += 1
        if chunk_count <= 3:
            print(
                f"  Chunk {chunk_count}: {chunk.node_type} at line {chunk.start_line}",
            )

    print(f"  ... (processed {chunk_count} total chunks via streaming)")


if __name__ == "__main__":
    # Run examples
    example_in_memory_vfs()
    example_zip_vfs()
    example_composite_vfs()
    example_gc_optimization()
    example_streaming_large_files()

    print("\n✅ All VFS examples completed!")

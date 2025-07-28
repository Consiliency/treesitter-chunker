"""Example demonstrating the sliding window fallback integration.

This example shows how to use the SlidingWindowFallback system with:
- Automatic processor selection
- Custom processor registration
- Configuration support
- Processor chaining for hybrid processing
"""

from typing import Any

from chunker.chunker_config import ChunkerConfig
from chunker.fallback import SlidingWindowFallback, TextProcessor
from chunker.fallback.detection.file_type import FileType
from chunker.types import CodeChunk


# Example custom processor for SQL files
class SQLProcessor(TextProcessor):
    """Custom processor for SQL files."""

    def can_process(self, content: str, file_path: str) -> bool:
        """Check if content is SQL."""
        return (
            file_path.endswith(".sql")
            or "SELECT" in content.upper()
            or "CREATE TABLE" in content.upper()
        )

    def process(self, content: str, file_path: str) -> list[CodeChunk]:
        """Process SQL content by statements."""
        chunks = []
        statements = content.split(";")

        current_pos = 0
        for i, statement in enumerate(statements):
            if not statement.strip():
                current_pos += len(statement) + 1
                continue

            # Include semicolon
            if i < len(statements) - 1:
                statement += ";"

            # Calculate line numbers
            lines_before = content[:current_pos].count("\n")
            start_line = lines_before + 1
            end_line = start_line + statement.count("\n")

            chunk = CodeChunk(
                language="sql",
                file_path=file_path,
                node_type="sql_statement",
                start_line=start_line,
                end_line=end_line,
                byte_start=current_pos,
                byte_end=current_pos + len(statement),
                parent_context=f"statement_{i}",
                content=statement,
            )
            chunks.append(chunk)
            current_pos += len(statement)

        return chunks


# Example custom processor for data files
class DataFileProcessor(TextProcessor):
    """Processor for structured data files (CSV, TSV)."""

    def __init__(self, config: Optional[dict[str, Any]] = None):
        super().__init__(config)
        self.rows_per_chunk = self.config.get("rows_per_chunk", 100)
        self.include_header = self.config.get("include_header", True)

    def can_process(self, content: str, file_path: str) -> bool:
        """Check if content is structured data."""
        return (
            file_path.endswith((".csv", ".tsv")) or "\t" in content.splitlines()[0]
            if content
            else False
        )

    def process(self, content: str, file_path: str) -> list[CodeChunk]:
        """Process data file by rows."""
        lines = content.splitlines(keepends=True)
        if not lines:
            return []

        chunks = []
        header = lines[0] if self.include_header else ""

        for i in range(0, len(lines), self.rows_per_chunk):
            chunk_lines = lines[i : i + self.rows_per_chunk]

            # Add header to non-first chunks
            if i > 0 and self.include_header and header:
                chunk_content = header + "".join(chunk_lines)
            else:
                chunk_content = "".join(chunk_lines)

            chunk = CodeChunk(
                language="data",
                file_path=file_path,
                node_type="data_rows",
                start_line=i + 1,
                end_line=min(i + self.rows_per_chunk, len(lines)),
                byte_start=0,
                byte_end=len(chunk_content),
                parent_context=f"rows_{i}_{i+self.rows_per_chunk}",
                content=chunk_content,
            )
            chunks.append(chunk)

        return chunks


def main():
    """Demonstrate sliding window fallback integration."""

    print("=== Sliding Window Fallback Integration Demo ===\n")

    # 1. Basic usage with automatic processor selection
    print("1. Basic Usage - Automatic Processor Selection")
    print("-" * 50)

    fallback = SlidingWindowFallback()

    # Test different file types
    test_files = {
        "example.md": "# Title\n\nSection 1\n\n## Subsection\n\nContent",
        "app.log": "[INFO] Starting\n[ERROR] Failed to connect\n[INFO] Retrying",
        "data.txt": "Just plain text without any special format.\n" * 10,
    }

    for filename, content in test_files.items():
        chunks = fallback.chunk_text(content, filename)
        print(f"\n{filename}: {len(chunks)} chunks")
        for i, chunk in enumerate(chunks):
            processor = chunk.metadata.get("processor", "unknown")
            print(f"  Chunk {i+1}: {chunk.node_type} (processor: {processor})")

    # 2. Custom processor registration
    print("\n\n2. Custom Processor Registration")
    print("-" * 50)

    # Register SQL processor
    fallback.register_custom_processor(
        name="sql_processor",
        processor_class=SQLProcessor,
        file_types={FileType.TEXT},  # SQL might be detected as TEXT
        extensions={".sql"},
        priority=150,  # High priority for SQL files
    )

    # Register data file processor
    fallback.register_custom_processor(
        name="data_processor",
        processor_class=DataFileProcessor,
        file_types={FileType.CSV, FileType.TEXT},
        extensions={".csv", ".tsv"},
        priority=120,
    )

    # Test SQL processing
    sql_content = """
    CREATE TABLE users (
        id INTEGER PRIMARY KEY,
        name VARCHAR(100)
    );

    INSERT INTO users (name) VALUES ('Alice');
    INSERT INTO users (name) VALUES ('Bob');

    SELECT * FROM users WHERE id > 0;
    """

    chunks = fallback.chunk_text(sql_content, "schema.sql")
    print(f"\nSQL file: {len(chunks)} chunks")
    for i, chunk in enumerate(chunks):
        print(f"  Chunk {i+1}: {chunk.content.strip()[:50]}...")

    # 3. Configuration support
    print("\n\n3. Configuration Support")
    print("-" * 50)

    # Create configuration
    config_data = {
        "processors": {
            "data_processor": {
                "enabled": True,
                "priority": 150,
                "config": {
                    "rows_per_chunk": 50,
                    "include_header": True,
                },
            },
        },
    }

    # Create new fallback with configuration
    chunker_config = ChunkerConfig()
    chunker_config.data = config_data

    configured_fallback = SlidingWindowFallback(chunker_config=chunker_config)
    configured_fallback.register_custom_processor(
        name="data_processor",
        processor_class=DataFileProcessor,
        file_types={FileType.CSV},
        extensions={".csv"},
        priority=120,
    )

    # Test CSV processing
    csv_content = "name,age,city\n" + "\n".join(
        [f"Person{i},{20+i},City{i}" for i in range(200)],
    )

    chunks = configured_fallback.chunk_text(csv_content, "data.csv")
    print(f"\nCSV file: {len(chunks)} chunks (configured for 50 rows/chunk)")

    # 4. Processor information and control
    print("\n\n4. Processor Information and Control")
    print("-" * 50)

    # Get processor info for different files
    for filename in ["test.sql", "test.csv", "test.md", "test.xyz"]:
        info = fallback.get_processor_info(filename)
        print(f"\n{filename}:")
        print(f"  File type: {info['file_type']}")
        print(f"  Available processors: {info['available_processors']}")

    # Disable/enable processors
    print("\n\nDisabling SQL processor...")
    fallback.disable_processor("sql_processor")

    chunks = fallback.chunk_text(sql_content, "schema.sql")
    processor_used = chunks[0].metadata.get("processor", "unknown")
    print(f"SQL file processed with: {processor_used}")

    print("\nRe-enabling SQL processor...")
    fallback.enable_processor("sql_processor")

    chunks = fallback.chunk_text(sql_content, "schema.sql")
    processor_used = chunks[0].metadata.get("processor", "unknown")
    print(f"SQL file processed with: {processor_used}")

    # 5. Processor chaining for hybrid processing
    print("\n\n5. Processor Chaining (Hybrid Mode)")
    print("-" * 50)

    # Create a mixed content file
    mixed_content = """
    # Database Schema Documentation

    This document describes our database schema.

    ## Users Table

    ```sql
    CREATE TABLE users (
        id INTEGER PRIMARY KEY,
        name VARCHAR(100)
    );
    ```

    ## Sample Data

    name,age,city
    Alice,25,NYC
    Bob,30,LA
    Charlie,35,Chicago
    """

    # Process with single processor
    chunks = fallback.chunk_text(mixed_content, "schema_doc.md")
    print(f"\nSingle processor: {len(chunks)} chunks")

    # Create processor chain
    # Note: This is a simplified example. Real chaining would need
    # more sophisticated content separation
    chain = fallback.create_processor_chain(["markdown_processor", "sql_processor"])
    if chain:
        print("\nProcessor chain created successfully")

    # 6. Performance monitoring
    print("\n\n6. Performance and Caching")
    print("-" * 50)

    # Process same file multiple times to test caching
    import time

    large_content = "Line of text\n" * 1000

    start = time.time()
    chunks1 = fallback.chunk_text(large_content, "large.txt")
    time1 = time.time() - start

    start = time.time()
    chunks2 = fallback.chunk_text(large_content, "large.txt")
    time2 = time.time() - start

    print(f"\nFirst processing: {time1:.4f}s ({len(chunks1)} chunks)")
    print(f"Second processing: {time2:.4f}s ({len(chunks2)} chunks)")
    print(f"Caching benefit: {(time1 - time2) / time1 * 100:.1f}% faster")

    # Summary
    print("\n\n=== Summary ===")
    print("-" * 50)
    print("The SlidingWindowFallback system provides:")
    print("- Automatic processor selection based on file type")
    print("- Easy custom processor registration")
    print("- Configuration support for processor behavior")
    print("- Processor chaining for complex formats")
    print("- Performance optimization through caching")
    print("- Dynamic processor enabling/disabling")
    print("\nThis allows flexible text processing for any file type!")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Example usage of the Parquet export feature.

This demonstrates how to use the treesitter-chunker with Parquet export.
"""

from pathlib import Path

from chunker import chunk_file
from chunker.exporters import ParquetExporter


def example_basic_export():
    """Basic Parquet export example."""
    print("=== Basic Parquet Export ===")

    # Chunk a Python file
    chunks = chunk_file("chunker/chunker.py", "python")

    # Export to Parquet
    exporter = ParquetExporter()
    exporter.export(chunks, "output/chunks_basic.parquet")
    print(f"Exported {len(chunks)} chunks to output/chunks_basic.parquet")


def example_column_selection():
    """Export with column selection."""
    print("\n=== Parquet Export with Column Selection ===")

    chunks = chunk_file("chunker/chunker.py", "python")

    # Export only specific columns
    exporter = ParquetExporter(
        columns=["language", "node_type", "lines_of_code", "content"],
    )
    exporter.export(chunks, "output/chunks_selected_columns.parquet")
    print("Exported with selected columns: language, node_type, lines_of_code, content")


def example_partitioned_export():
    """Export with partitioning."""
    print("\n=== Partitioned Parquet Export ===")

    # Chunk multiple files
    all_chunks = []
    for file_path in ["chunker/chunker.py", "chunker/parser.py", "cli/main.py"]:
        chunks = chunk_file(file_path, "python")
        all_chunks.extend(chunks)

    # Export with partitioning by node_type
    exporter = ParquetExporter(partition_by=["node_type"])
    exporter.export(all_chunks, "output/chunks_partitioned")
    print(f"Exported {len(all_chunks)} chunks partitioned by node_type")


def example_compressed_export():
    """Export with different compression options."""
    print("\n=== Compressed Parquet Export ===")

    chunks = chunk_file("chunker/chunker.py", "python")

    # Export with zstd compression
    exporter = ParquetExporter(compression="zstd")
    exporter.export(chunks, "output/chunks_compressed.parquet")
    print("Exported with zstd compression")


def cli_examples():
    """Show CLI command examples."""
    print("\n=== CLI Usage Examples ===")
    print("\n# Basic export to Parquet:")
    print("python -m cli.main chunk myfile.py --lang python --parquet output.parquet")

    print("\n# Export with column selection:")
    print(
        "python -m cli.main chunk myfile.py --lang python --parquet output.parquet \\",
    )
    print("    --columns language --columns node_type --columns content")

    print("\n# Export with partitioning:")
    print("python -m cli.main chunk myfile.py --lang python --parquet output_dir/ \\")
    print("    --partition language --partition file_path")

    print("\n# Export with custom compression:")
    print(
        "python -m cli.main chunk myfile.py --lang python --parquet output.parquet \\",
    )
    print("    --compression gzip")


if __name__ == "__main__":
    # Create output directory
    Path("output").mkdir(exist_ok=True)

    # Run examples
    example_basic_export()
    example_column_selection()
    example_partitioned_export()
    example_compressed_export()
    cli_examples()

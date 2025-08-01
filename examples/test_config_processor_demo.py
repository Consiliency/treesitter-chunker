#!/usr/bin/env python3
"""Demo script for testing ConfigProcessor with various config files."""

import json
import sys
from pathlib import Path

# Add parent directory to path to import our modules
sys.path.insert(0, str(Path(__file__).parent))

from chunker.processors.config import ConfigProcessor, ProcessorConfig
from chunker.types import CodeChunk


def print_chunk_info(chunk: CodeChunk):
    """Print information about a chunk."""
    print(f"\n{'=' * 60}")
    print(f"Chunk: {chunk.metadata.get('name', chunk.node_type)}")
    print(f"Type: {chunk.node_type}")
    print(f"Lines: {chunk.start_line}-{chunk.end_line}")
    print(f"Language: {chunk.language}")
    if "section" in chunk.metadata:
        print(f"Section: {chunk.metadata['section']}")
    if "keys" in chunk.metadata:
        print(
            f"Keys: {', '.join(chunk.metadata['keys'][:5])}"
            + ("..." if len(chunk.metadata["keys"]) > 5 else ""),
        )
    print("\nContent preview (first 5 lines):")
    lines = chunk.content.split("\n")[:5]
    for line in lines:
        print(f"  {line}")
    if len(chunk.content.split("\n")) > 5:
        print("  ...")


def process_file(file_path: str, processor: ConfigProcessor):
    """Process a single configuration file."""
    print(f"\n{'#' * 80}")
    print(f"# Processing: {file_path}")
    print("#" * 80)

    path = Path(file_path)
    if not path.exists():
        print(f"Error: File not found: {file_path}")
        return

    content = path.read_text(encoding="utf-8")

    # Detect fmt
    fmt = processor.detect_format(file_path, content)
    print(f"\nDetected fmt: {fmt}")

    if fmt is None:
        print("Error: Could not detect fmt")
        return

    # Process file
    try:
        chunks = processor.process(file_path, content)
        print(f"Generated {len(chunks)} chunks")

        # Show chunk information
        for chunk in chunks:
            print_chunk_info(chunk)

    except (FileNotFoundError, ImportError, ModuleNotFoundError) as e:
        print(f"Error processing file: {e}")
        import traceback

        traceback.print_exc()


def main():
    """Main demo function."""
    # Create processor with default config
    processor = ConfigProcessor(
        ProcessorConfig(
            chunk_size=50,
            preserve_structure=True,
            group_related=True,
        ),
    )

    print("ConfigProcessor Demo")
    print("====================")
    print(f"Supported formats: {', '.join(processor.get_supported_formats())}")

    # Example files to process
    example_dir = Path(__file__).parent / "examples" / "configs"

    if example_dir.exists():
        example_files = [
            "app.ini",
            "pyproject.toml",
            "docker-compose.yml",
            "settings.json",
        ]

        for filename in example_files:
            file_path = example_dir / filename
            if file_path.exists():
                process_file(str(file_path), processor)
            else:
                print(f"\nSkipping {filename} (not found)")
    else:
        print(f"\nError: Examples directory not found: {example_dir}")
        print("\nTesting with inline examples...")

        # Test with inline content
        test_cases = [
            (
                "test.ini",
                """
[database]
host = localhost
port = 5432

[cache]
host = redis
port = 6379
""",
            ),
            (
                "test.json",
                json.dumps(
                    {
                        "name": "test",
                        "version": "1.0",
                        "dependencies": {
                            "lib1": "1.0",
                            "lib2": "2.0",
                        },
                    },
                    indent=2,
                ),
            ),
        ]

        for filename, content in test_cases:
            print(f"\n{'#' * 80}")
            print(f"# Testing inline: {filename}")
            print("#" * 80)

            fmt = processor.detect_format(filename, content)
            print(f"Detected fmt: {fmt}")

            if fmt:
                chunks = processor.process(filename, content)
                print(f"Generated {len(chunks)} chunks")
                for chunk in chunks:
                    print_chunk_info(chunk)

    print("\n" + "=" * 80)
    print("Demo complete!")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Test integration of SlidingWindowFallback with main chunker system.

This script demonstrates how the sliding window fallback integrates
with the existing chunker infrastructure.
"""

import os
import tempfile
from pathlib import Path

# Import main chunker components
from chunker.chunker import Chunker
from chunker.chunker_config import ChunkerConfig

# Import sliding window fallback
from chunker.fallback import SlidingWindowFallback, TextProcessor
from chunker.fallback.detection.file_type import FileType
from chunker.types import CodeChunk


# Custom processor for demo
class DemoProcessor(TextProcessor):
    """Demo processor for testing."""

    def can_process(self, content: str, file_path: str) -> bool:
        return ".demo" in file_path or "DEMO:" in content

    def process(self, content: str, file_path: str) -> list[CodeChunk]:
        chunks = []
        sections = content.split("DEMO:")

        for i, section in enumerate(sections):
            if not section.strip():
                continue

            chunk = CodeChunk(
                language="demo",
                file_path=file_path,
                node_type="demo_section",
                start_line=1,
                end_line=section.count("\n") + 1,
                byte_start=0,
                byte_end=len(section),
                parent_context=f"demo_{i}",
                content=section,
            )
            chunks.append(chunk)

        return chunks


def test_with_tree_sitter_supported():
    """Test with a file that Tree-sitter can parse."""
    print("=== Testing with Tree-sitter Supported File ===")

    # Create a Python file
    python_code = '''
def hello_world():
    """Say hello."""
    print("Hello, World!")

class Example:
    """Example class."""

    def __init__(self):
        self.value = 42

    def get_value(self):
        return self.value
'''

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(python_code)
        temp_file = f.name

    try:
        # Create chunker
        chunker = Chunker()

        # Process file
        chunks = chunker.chunk_file(temp_file, "python")

        print(f"Processed {temp_file}")
        print(f"Found {len(chunks)} chunks using Tree-sitter")
        for chunk in chunks:
            print(f"  - {chunk.node_type}: lines {chunk.start_line}-{chunk.end_line}")

    finally:
        os.unlink(temp_file)


def test_with_fallback_needed():
    """Test with a file that needs fallback."""
    print("\n=== Testing with Fallback Needed ===")

    # Create a file without Tree-sitter support
    content = """
DEMO: Section 1
This is the first demo section.
It contains some content.

DEMO: Section 2
This is the second demo section.
With different content.

Regular text without demo marker.
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".demo", delete=False) as f:
        f.write(content)
        temp_file = f.name

    try:
        # Create sliding window fallback
        fallback = SlidingWindowFallback()

        # Register custom processor
        fallback.register_custom_processor(
            name="demo_processor",
            processor_class=DemoProcessor,
            file_types={FileType.TEXT},
            extensions={".demo"},
            priority=150,
        )

        # In a real integration, the main chunker would use this fallback
        # For testing, we'll use it directly
        chunks = fallback.chunk_text(content, temp_file)

        print(f"Processed {temp_file}")
        print(f"Found {len(chunks)} chunks using fallback")
        for chunk in chunks:
            processor = chunk.metadata.get("processor", "unknown")
            print(f"  - {chunk.node_type} (processor: {processor})")
            print(f"    Content preview: {chunk.content[:50]}...")

    finally:
        os.unlink(temp_file)


def test_mixed_repository():
    """Test processing a mixed repository."""
    print("\n=== Testing Mixed Repository ===")

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create various files
        files = {
            "README.md": "# Project\n\nDescription\n\n## Installation\n\nSteps...",
            "main.py": 'def main():\n    print("Hello")\n\nif __name__ == "__main__":\n    main()',
            "config.ini": "[settings]\nkey=value\n\n[database]\nhost=localhost",
            "app.log": "[INFO] Started\n[ERROR] Connection failed\n[INFO] Retrying",
            "data.csv": "name,age\nAlice,30\nBob,25\nCharlie,35",
            "custom.demo": "DEMO: Feature 1\nImplementation\n\nDEMO: Feature 2\nDetails",
        }

        # Create files
        for filename, content in files.items():
            filepath = Path(tmpdir) / filename
            filepath.write_text(content)

        # Create fallback with custom processor
        fallback = SlidingWindowFallback()
        fallback.register_custom_processor(
            name="demo_processor",
            processor_class=DemoProcessor,
            file_types={FileType.TEXT},
            extensions={".demo"},
            priority=150,
        )

        # Process each file
        print(f"\nProcessing files in {tmpdir}")
        for filename in sorted(files.keys()):
            filepath = Path(tmpdir) / filename
            content = filepath.read_text()

            # Check if Tree-sitter would handle it
            ext = filepath.suffix
            treesitter_supported = ext in [".py"]

            if treesitter_supported:
                print(f"\n{filename}: Would use Tree-sitter")
            else:
                # Use fallback
                chunks = fallback.chunk_text(content, str(filepath))
                processor = (
                    chunks[0].metadata.get("processor", "unknown") if chunks else "none"
                )
                print(f"\n{filename}: Using fallback processor '{processor}'")
                print(f"  Chunks: {len(chunks)}")


def test_processor_info_api():
    """Test processor information API."""
    print("\n=== Testing Processor Info API ===")

    fallback = SlidingWindowFallback()

    # Register some processors
    fallback.register_custom_processor(
        name="demo_processor",
        processor_class=DemoProcessor,
        file_types={FileType.TEXT},
        extensions={".demo"},
        priority=150,
    )

    # Get info for various file types
    test_files = [
        "example.py",  # Tree-sitter supported
        "example.md",  # Markdown processor
        "example.log",  # Log processor
        "example.demo",  # Custom processor
        "example.xyz",  # Unknown - generic fallback
    ]

    print("\nProcessor selection for different file types:")
    for filename in test_files:
        info = fallback.get_processor_info(filename)
        print(f"\n{filename}:")
        print(f"  File type: {info['file_type']}")
        print(f"  Available processors: {info['available_processors'][:3]}...")
        if info["processors"]:
            top_proc = info["processors"][0]
            print(
                f"  Top processor: {top_proc['name']} (priority: {top_proc['priority']})",
            )


def test_configuration_integration():
    """Test configuration integration."""
    print("\n=== Testing Configuration Integration ===")

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create configuration file
        config_path = Path(tmpdir) / "chunker.config.yaml"
        config_content = """
processors:
  demo_processor:
    enabled: true
    priority: 200
    config:
      custom_option: "value"

  generic_sliding_window:
    enabled: true
    config:
      window_size: 500
      overlap: 50

chunker:
  plugin_dirs:
    - ./plugins
"""
        config_path.write_text(config_content)

        # Load configuration
        chunker_config = ChunkerConfig(config_path)

        # Create fallback with config
        fallback = SlidingWindowFallback(chunker_config=chunker_config)

        # Register demo processor
        fallback.register_custom_processor(
            name="demo_processor",
            processor_class=DemoProcessor,
            file_types={FileType.TEXT},
            extensions={".demo"},
            priority=150,  # Will be overridden by config
        )

        print(f"Loaded configuration from {config_path}")
        print("\nProcessor configurations:")

        # Check processor info
        info = fallback.get_processor_info("test.demo")
        for proc in info["processors"][:3]:
            print(
                f"  {proc['name']}: priority={proc['priority']}, enabled={proc['enabled']}",
            )


def main():
    """Run all integration tests."""
    print("Sliding Window Fallback - Main Chunker Integration Tests")
    print("=" * 60)

    try:
        test_with_tree_sitter_supported()
        test_with_fallback_needed()
        test_mixed_repository()
        test_processor_info_api()
        test_configuration_integration()

        print("\n" + "=" * 60)
        print("All integration tests completed successfully!")

    except Exception as e:
        print(f"\nError during testing: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()

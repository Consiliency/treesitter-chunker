"""Test integration of SlidingWindowFallback with main chunker system.

This script demonstrates how the sliding window fallback integrates
with the existing chunker infrastructure.
"""

import tempfile
from pathlib import Path

from chunker.chunker import Chunker
from chunker.chunker_config import ChunkerConfig
from chunker.fallback import SlidingWindowFallback, TextProcessor
from chunker.fallback.detection.file_type import FileType
from chunker.types import CodeChunk


class DemoProcessor(TextProcessor):
    """Demo processor for testing."""

    @staticmethod
    def can_process(content: str, file_path: str) -> bool:
        return ".demo" in file_path or "DEMO:" in content

    @classmethod
    def process(cls, content: str, file_path: str) -> list[CodeChunk]:
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
    python_code = """
def hello_world():
    ""\"Say hello.""\"
    print("Hello, World!")

class Example:
    ""\"Example class.""\"

    def __init__(self):
        self.value = 42

    def get_value(self):
        return self.value
"""
    with tempfile.NamedTemporaryFile(
        encoding="utf-8",
        mode="w",
        suffix=".py",
        delete=False,
    ) as f:
        f.write(python_code)
        temp_file = f.name
    try:
        chunker = Chunker()
        chunks = chunker.chunk_file(temp_file, "python")
        print(f"Processed {temp_file}")
        print(f"Found {len(chunks)} chunks using Tree-sitter")
        for chunk in chunks:
            print(
                f"  - {chunk.node_type}: lines {chunk.start_line}-{chunk.end_line}",
            )
    finally:
        Path(temp_file).unlink()


def test_with_fallback_needed():
    """Test with a file that needs fallback."""
    print("\n=== Testing with Fallback Needed ===")
    content = """
DEMO: Section 1
This is the first demo section.
It contains some content.

DEMO: Section 2
This is the second demo section.
With different content.

Regular text without demo marker.
"""
    with tempfile.NamedTemporaryFile(
        encoding="utf-8",
        mode="w",
        suffix=".demo",
        delete=False,
    ) as f:
        f.write(content)
        temp_file = f.name
    try:
        fallback = SlidingWindowFallback()
        fallback.register_custom_processor(
            name="demo_processor",
            processor_class=DemoProcessor,
            file_types={FileType.TEXT},
            extensions={".demo"},
            priority=150,
        )
        chunks = fallback.chunk_text(content, temp_file)
        print(f"Processed {temp_file}")
        print(f"Found {len(chunks)} chunks using fallback")
        for chunk in chunks:
            processor = chunk.metadata.get("processor", "unknown")
            print(f"  - {chunk.node_type} (processor: {processor})")
            print(f"    Content preview: {chunk.content[:50]}...")
    finally:
        Path(temp_file).unlink()


def test_mixed_repository():
    """Test processing a mixed repository."""
    print("\n=== Testing Mixed Repository ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        files = {
            "README.md": "# Project\n\nDescription\n\n## Installation\n\nSteps...",
            "main.py": """def main():
    print("Hello")

if __name__ == "__main__":
    main()""",
            "config.ini": "[settings]\nkey=value\n\n[database]\nhost=localhost",
            "app.log": """[INFO] Started
[ERROR] Connection failed
[INFO] Retrying""",
            "data.csv": """name,age
Alice,30
Bob,25
Charlie,35""",
            "custom.demo": """DEMO: Feature 1
Implementation

DEMO: Feature 2
Details""",
        }
        for filename, content in files.items():
            filepath = Path(tmpdir) / filename
            filepath.write_text(content)
        fallback = SlidingWindowFallback()
        fallback.register_custom_processor(
            name="demo_processor",
            processor_class=DemoProcessor,
            file_types={FileType.TEXT},
            extensions={".demo"},
            priority=150,
        )
        print(f"\nProcessing files in {tmpdir}")
        for filename in sorted(files.keys()):
            filepath = Path(tmpdir) / filename
            content = filepath.read_text()
            ext = filepath.suffix
            treesitter_supported = ext in {".py"}
            if treesitter_supported:
                print(f"\n{filename}: Would use Tree-sitter")
            else:
                chunks = fallback.chunk_text(content, str(filepath))
                processor = (
                    chunks[0].metadata.get(
                        "processor",
                        "unknown",
                    )
                    if chunks
                    else "none"
                )
                print(f"\n{filename}: Using fallback processor '{processor}'")
                print(f"  Chunks: {len(chunks)}")


def test_processor_info_api():
    """Test processor information API."""
    print("\n=== Testing Processor Info API ===")
    fallback = SlidingWindowFallback()
    fallback.register_custom_processor(
        name="demo_processor",
        processor_class=DemoProcessor,
        file_types={FileType.TEXT},
        extensions={".demo"},
        priority=150,
    )
    test_files = [
        "example.py",
        "example.md",
        "example.log",
        "example.demo",
        "example.xyz",
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
        chunker_config = ChunkerConfig(config_path)
        fallback = SlidingWindowFallback(chunker_config=chunker_config)
        fallback.register_custom_processor(
            name="demo_processor",
            processor_class=DemoProcessor,
            file_types={FileType.TEXT},
            extensions={".demo"},
            priority=150,
        )
        print(f"Loaded configuration from {config_path}")
        print("\nProcessor configurations:")
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
    except (ImportError, ModuleNotFoundError, TypeError) as e:
        print(f"\nError during testing: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()

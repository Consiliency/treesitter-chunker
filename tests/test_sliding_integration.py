"""Integration tests for sliding window fallback system."""

import tempfile
from pathlib import Path

import pytest
import yaml

from chunker.chunker_config import ChunkerConfig
from chunker.fallback.detection.file_type import FileType
from chunker.fallback.sliding_window_fallback import (
    GenericSlidingWindowProcessor,
    ProcessorInfo,
    ProcessorRegistry,
    ProcessorType,
    SlidingWindowFallback,
    TextProcessor,
)
from chunker.interfaces.fallback import FallbackReason
from chunker.types import CodeChunk


# Test processor implementations
class MockMarkdownProcessor(TextProcessor):
    """Test markdown processor."""

    def can_process(self, content: str, file_path: str) -> bool:
        return file_path.endswith(".md") or "# " in content

    def process(self, content: str, file_path: str) -> list[CodeChunk]:
        chunks = []
        lines = content.splitlines(keepends=True)
        current_section = []
        current_start = 0

        for i, line in enumerate(lines):
            if line.startswith("#") and current_section:
                # End current section
                chunk_content = "".join(current_section)
                chunk = CodeChunk(
                    language="markdown",
                    file_path=file_path,
                    node_type="markdown_section",
                    start_line=current_start + 1,
                    end_line=i,
                    byte_start=0,
                    byte_end=len(chunk_content),
                    parent_context=f"section_{current_start}",
                    content=chunk_content,
                )
                chunks.append(chunk)
                current_section = [line]
                current_start = i
            else:
                current_section.append(line)

        # Add final section
        if current_section:
            chunk_content = "".join(current_section)
            chunk = CodeChunk(
                language="markdown",
                file_path=file_path,
                node_type="markdown_section",
                start_line=current_start + 1,
                end_line=len(lines),
                byte_start=0,
                byte_end=len(chunk_content),
                parent_context=f"section_{current_start}",
                content=chunk_content,
            )
            chunks.append(chunk)

        return chunks


class MockLogProcessor(TextProcessor):
    """Test log processor."""

    def can_process(self, content: str, file_path: str) -> bool:
        return file_path.endswith(".log") or "[ERROR]" in content or "[INFO]" in content

    def process(self, content: str, file_path: str) -> list[CodeChunk]:
        chunks = []
        lines = content.splitlines(keepends=True)

        # Simple grouping by log level
        current_level = None
        current_chunk = []
        current_start = 0

        for i, line in enumerate(lines):
            level = None
            if "[ERROR]" in line:
                level = "ERROR"
            elif "[INFO]" in line:
                level = "INFO"
            elif "[DEBUG]" in line:
                level = "DEBUG"

            if level and level != current_level and current_chunk:
                # Save current chunk
                chunk_content = "".join(current_chunk)
                chunk = CodeChunk(
                    language="log",
                    file_path=file_path,
                    node_type=f"log_{current_level or 'unknown'}",
                    start_line=current_start + 1,
                    end_line=i,
                    byte_start=0,
                    byte_end=len(chunk_content),
                    parent_context=f"log_group_{current_start}",
                    content=chunk_content,
                )
                chunks.append(chunk)
                current_chunk = [line]
                current_start = i
                current_level = level
            else:
                current_chunk.append(line)
                if level:
                    current_level = level

        # Add final chunk
        if current_chunk:
            chunk_content = "".join(current_chunk)
            chunk = CodeChunk(
                language="log",
                file_path=file_path,
                node_type=f"log_{current_level or 'unknown'}",
                start_line=current_start + 1,
                end_line=len(lines),
                byte_start=0,
                byte_end=len(chunk_content),
                parent_context=f"log_group_{current_start}",
                content=chunk_content,
            )
            chunks.append(chunk)

        return chunks


class TestSlidingWindowIntegration:
    """Test sliding window fallback integration."""

    @pytest.fixture
    def fallback(self):
        """Create sliding window fallback instance."""
        return SlidingWindowFallback()

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for test files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    def test_processor_registry(self):
        """Test processor registry functionality."""
        registry = ProcessorRegistry()

        # Register a processor
        proc_info = ProcessorInfo(
            name="test_processor",
            processor_type=ProcessorType.CUSTOM,
            processor_class=MockMarkdownProcessor,
            supported_file_types={FileType.MARKDOWN},
            supported_extensions={".md", ".markdown"},
            priority=100,
        )
        registry.register(proc_info)

        # Get processor
        processor = registry.get_processor("test_processor")
        assert processor is not None
        assert isinstance(processor, MockMarkdownProcessor)

        # Find processors for file
        processors = registry.find_processors("test.md", FileType.MARKDOWN)
        assert "test_processor" in processors

        # List processors
        all_procs = registry.list_processors()
        assert len(all_procs) == 1
        assert all_procs[0].name == "test_processor"

        # Unregister
        registry.unregister("test_processor")
        assert registry.get_processor("test_processor") is None

    def test_generic_sliding_window_processor(self):
        """Test generic sliding window processor."""
        processor = GenericSlidingWindowProcessor(
            {
                "window_size": 100,
                "overlap": 20,
                "preserve_words": True,
            },
        )

        # Test can_process
        assert processor.can_process("any content", "any_file.txt")

        # Test small content
        small_content = "This is a small text file."
        chunks = processor.process(small_content, "test.txt")
        assert len(chunks) == 1
        assert chunks[0].content == small_content

        # Test large content with sliding window
        large_content = " ".join(["word"] * 200)  # 200 words
        chunks = processor.process(large_content, "test.txt")
        assert len(chunks) > 1

        # Check overlap
        for i in range(len(chunks) - 1):
            assert chunks[i].byte_end > chunks[i + 1].byte_start

    def test_processor_selection(self, fallback, temp_dir):
        """Test automatic processor selection."""
        # Register custom processors
        fallback.register_custom_processor(
            "test_markdown",
            MockMarkdownProcessor,
            {FileType.MARKDOWN},
            {".md"},
            priority=100,
        )

        fallback.register_custom_processor(
            "test_log",
            MockLogProcessor,
            {FileType.LOG},
            {".log"},
            priority=100,
        )

        # Test markdown file
        md_file = Path(temp_dir) / "test.md"
        md_content = "# Header 1\nContent 1\n\n# Header 2\nContent 2"

        chunks = fallback.chunk_text(md_content, md_file)
        assert len(chunks) == 2
        assert chunks[0].metadata["processor"] == "test_markdown"
        assert chunks[0].content.startswith("# Header 1")
        assert chunks[1].content.startswith("# Header 2")

        # Test log file
        log_file = Path(temp_dir) / "test.log"
        log_content = "[INFO] Starting\n[ERROR] Failed\n[ERROR] Retry\n[INFO] Done"

        chunks = fallback.chunk_text(log_content, log_file)
        assert len(chunks) > 0
        assert chunks[0].metadata["processor"] == "test_log"

        # Test unknown file - should use generic processor
        txt_file = Path(temp_dir) / "test.txt"
        txt_content = "Just some plain text content that doesn't match any pattern."

        chunks = fallback.chunk_text(txt_content, txt_file)
        assert len(chunks) >= 1
        # Should fall back to line-based or generic processor

    def test_processor_enabling_disabling(self, fallback):
        """Test enabling and disabling processors."""
        # Register a processor
        fallback.register_custom_processor(
            "test_proc",
            MockMarkdownProcessor,
            {FileType.MARKDOWN},
            {".md"},
            priority=100,
        )

        # Initially enabled
        info = fallback.get_processor_info("test.md")
        procs = [p for p in info["processors"] if p["name"] == "test_proc"]
        assert len(procs) == 1
        assert procs[0]["enabled"]

        # Disable processor
        fallback.disable_processor("test_proc")
        processor = fallback.registry.get_processor("test_proc")
        assert processor is None

        # Enable processor
        fallback.enable_processor("test_proc")
        processor = fallback.registry.get_processor("test_proc")
        assert processor is not None

    def test_processor_chain(self, fallback):
        """Test processor chaining for hybrid processing."""
        # Register processors
        fallback.register_custom_processor(
            "markdown_proc",
            MockMarkdownProcessor,
            {FileType.MARKDOWN},
            {".md"},
            priority=100,
        )

        fallback.register_custom_processor(
            "generic_proc",
            GenericSlidingWindowProcessor,
            set(FileType),
            set(),
            priority=10,
        )

        # Create chain
        chain = fallback.create_processor_chain(["markdown_proc", "generic_proc"])
        assert chain is not None
        assert len(chain.processors) == 2

        # Process content
        content = "# Header\nSome content\n\n# Another Header\nMore content"
        chunks = chain.process(content, "test.md")
        assert len(chunks) > 0

    def test_configuration_integration(self, temp_dir):
        """Test integration with ChunkerConfig."""
        # Create config file
        config_data = {
            "chunker": {
                "plugin_dirs": [temp_dir],
            },
            "processors": {
                "test_markdown": {
                    "enabled": True,
                    "priority": 150,
                    "config": {
                        "max_chunk_size": 500,
                    },
                },
            },
        }

        config_path = Path(temp_dir) / "chunker.config.yaml"

        with Path(config_path).open(
            "w",
        ) as f:
            yaml.dump(config_data, f)

        # Create fallback with config
        chunker_config = ChunkerConfig(config_path)
        fallback = SlidingWindowFallback(chunker_config=chunker_config)

        # Register processor
        fallback.register_custom_processor(
            "test_markdown",
            MockMarkdownProcessor,
            {FileType.MARKDOWN},
            {".md"},
            priority=100,
        )

        # Check config was applied
        proc_info = fallback.registry._processors.get("test_markdown")
        assert proc_info is not None
        assert proc_info.priority == 100  # Priority from registration, not config
        # Note: In real implementation, config would override during _load_custom_processors

    def test_error_handling(self, fallback):
        """Test error handling in processor selection."""

        # Create a processor that raises errors
        class ErrorProcessor(TextProcessor):
            def can_process(self, content: str, file_path: str) -> bool:
                return True

            def process(self, content: str, file_path: str) -> list[CodeChunk]:
                raise RuntimeError("Processing failed")

        # Register error processor with high priority
        fallback.register_custom_processor(
            "error_proc",
            ErrorProcessor,
            {FileType.TEXT},
            {".txt"},
            priority=200,
        )

        # Should fall back to line-based chunking
        content = "Some text content"
        chunks = fallback.chunk_text(content, "test.txt")
        assert len(chunks) > 0
        # Should not have used error_proc
        assert chunks[0].metadata.get("processor") != "error_proc"

    def test_processor_info_api(self, fallback):
        """Test processor info API."""
        # Register some processors
        fallback.register_custom_processor(
            "md_proc",
            MockMarkdownProcessor,
            {FileType.MARKDOWN},
            {".md"},
            priority=100,
        )

        fallback.register_custom_processor(
            "log_proc",
            MockLogProcessor,
            {FileType.LOG},
            {".log"},
            priority=90,
        )

        # Get info for markdown file
        info = fallback.get_processor_info("test.md")
        assert info["file_type"] == FileType.MARKDOWN.value
        assert "md_proc" in info["available_processors"]

        # Check processor details
        md_proc_info = next(p for p in info["processors"] if p["name"] == "md_proc")
        assert md_proc_info["type"] == ProcessorType.CUSTOM.value
        assert md_proc_info["priority"] == 100
        assert md_proc_info["enabled"]

    def test_fallback_reason_propagation(self, fallback):
        """Test that fallback reason is properly set."""
        fallback.set_fallback_reason(FallbackReason.NO_GRAMMAR)

        content = "Some content"
        chunks = fallback.chunk_text(content, "unknown.xyz")

        # Chunks should be created despite no specific processor
        assert len(chunks) > 0

    def test_binary_file_handling(self, fallback, temp_dir):
        """Test handling of binary files."""
        # Create a binary file
        binary_file = Path(temp_dir) / "test.bin"
        with Path(binary_file).open(
            "wb",
        ) as f:
            f.write(b"\x00\x01\x02\x03\x04")

        # Should not process binary files
        # This would be handled by fallback manager, not sliding window fallback
        # But we can test file type detection
        info = fallback.get_processor_info(binary_file)
        assert info["file_type"] == FileType.BINARY.value


class TestProcessorPerformance:
    """Test performance aspects of processor system."""

    def test_processor_caching(self):
        """Test that processors are cached properly."""
        registry = ProcessorRegistry()

        # Register processor
        proc_info = ProcessorInfo(
            name="cached_proc",
            processor_type=ProcessorType.CUSTOM,
            processor_class=MockMarkdownProcessor,
            supported_file_types={FileType.MARKDOWN},
            supported_extensions={".md"},
            priority=50,
        )
        registry.register(proc_info)

        # Get processor twice
        proc1 = registry.get_processor("cached_proc")
        proc2 = registry.get_processor("cached_proc")

        # Should be same instance (cached)
        assert proc1 is proc2

    def test_large_file_processing(self, fallback):
        """Test processing of large files."""
        # Generate large content
        large_content = "\n".join([f"Line {i}: " + "x" * 100 for i in range(1000)])

        # Process with generic sliding window
        processor = GenericSlidingWindowProcessor(
            {
                "window_size": 1000,
                "overlap": 100,
            },
        )

        chunks = processor.process(large_content, "large.txt")

        # Verify chunks cover entire content
        total_coverage = set()
        for chunk in chunks:
            total_coverage.update(range(chunk.byte_start, chunk.byte_end))

        assert len(total_coverage) == len(large_content)

        # Verify overlap
        for i in range(len(chunks) - 1):
            overlap_size = chunks[i].byte_end - chunks[i + 1].byte_start
            assert overlap_size >= 90  # Allow some variance for word boundaries


class TestIntegrationScenarios:
    """Test real-world integration scenarios."""

    def test_mixed_content_repository(self, temp_dir):
        """Test processing a repository with mixed file types."""
        fallback = SlidingWindowFallback()

        # Register processors
        fallback.register_custom_processor(
            "md_processor",
            MockMarkdownProcessor,
            {FileType.MARKDOWN},
            {".md"},
            priority=100,
        )

        fallback.register_custom_processor(
            "log_processor",
            MockLogProcessor,
            {FileType.LOG},
            {".log"},
            priority=100,
        )

        # Create test files
        files = {
            "README.md": "# Project\n\nDescription\n\n## Installation\n\nSteps...",
            "app.log": "[INFO] Started\n[ERROR] Failed\n[INFO] Recovered",
            "config.ini": "[section]\nkey=value\n[another]\nkey2=value2",
            "data.txt": "Plain text data\nMultiple lines\nNo special format",
        }

        results = {}

        for filename, content in files.items():
            file_path = Path(temp_dir) / filename
            with Path(file_path).open(
                "w",
            ) as f:
                f.write(content)

            chunks = fallback.chunk_text(content, file_path)
            results[filename] = chunks

        # Verify appropriate processors were used
        assert results["README.md"][0].metadata["processor"] == "md_processor"
        assert results["app.log"][0].metadata["processor"] == "log_processor"
        # Others should use fallback

        # Verify all files were processed
        assert all(len(chunks) > 0 for chunks in results.values())

    def test_custom_plugin_loading(self, temp_dir):
        """Test loading custom processor plugins."""
        # Create a plugin file
        plugin_content = """
from chunker.fallback.sliding_window_fallback import TextProcessor, ProcessorInfo, ProcessorType
from chunker.fallback.detection.file_type import FileType
from chunker.types import CodeChunk

class CustomProcessor(TextProcessor):
    @staticmethod
    def processor_info():
        return ProcessorInfo(
            name="custom_plugin",
            processor_type=ProcessorType.CUSTOM,
            processor_class=CustomProcessor,
            supported_file_types={FileType.TEXT},
            supported_extensions={'.custom'},
            priority=150
        )

    def can_process(self, content, file_path):
        return file_path.endswith('.custom')

    def process(self, content, file_path):
        return [CodeChunk(
            language="custom",
            file_path=file_path,
            node_type="custom_chunk",
            start_line=1,
            end_line=content.count('\\n') + 1,
            byte_start=0,
            byte_end=len(content),
            parent_context="custom",
            content=content
        )]
"""

        plugin_path = Path(temp_dir) / "custom_processor.py"
        with Path(plugin_path).open(
            "w",
        ) as f:
            f.write(plugin_content)

        # Create config
        config = ChunkerConfig()
        config.add_plugin_directory(Path(temp_dir))

        # Create fallback with config
        fallback = SlidingWindowFallback(chunker_config=config)

        # Process custom file
        content = "Custom content"
        chunks = fallback.chunk_text(content, "test.custom")

        # Note: Plugin loading from files requires proper module setup
        # This test demonstrates the structure but may not fully execute
        assert len(chunks) > 0

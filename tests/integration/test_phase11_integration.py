"""Integration tests for Phase 11: Sliding Window & Text Processing.

This test suite verifies that all Phase 11 components work together correctly:
- Sliding window engine (if implemented)
- Text processing utilities (if implemented)
- Markdown processor
- Log file processor
- Config file processor
- Integration layer with fallback system
"""

import shutil
import tempfile
from pathlib import Path

import pytest

# Try to import all Phase 11 components
try:
    from chunker.sliding_window import (
        DefaultSlidingWindowEngine,
        OverlapStrategy,
        WindowConfig,
        WindowUnit,
    )

    HAS_SLIDING_WINDOW = True
except ImportError:
    HAS_SLIDING_WINDOW = False

try:
    from chunker.text_processing import ParagraphDetector, SentenceBoundaryDetector

    HAS_TEXT_PROCESSING = True
except ImportError:
    HAS_TEXT_PROCESSING = False

# Import processors - these should be available from the worktrees
try:
    from chunker.processors.markdown import MarkdownProcessor

    HAS_MARKDOWN_PROCESSOR = True
except ImportError:
    HAS_MARKDOWN_PROCESSOR = False

try:
    from chunker.processors.logs import LogProcessor

    HAS_LOG_PROCESSOR = True
except ImportError:
    HAS_LOG_PROCESSOR = False

try:
    from chunker.processors.config import ConfigProcessor

    HAS_CONFIG_PROCESSOR = True
except ImportError:
    HAS_CONFIG_PROCESSOR = False

try:
    from chunker.fallback.sliding_window_fallback import SlidingWindowFallback

    HAS_INTEGRATION = True
except ImportError:
    HAS_INTEGRATION = False


class TestPhase11Integration:
    """Test all Phase 11 components working together."""

    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)

    def teardown_method(self):
        """Clean up test environment."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_component_availability(self):
        """Test which Phase 11 components are available."""
        print("\nPhase 11 Component Availability:")
        print(f"  Sliding Window Engine: {'✓' if HAS_SLIDING_WINDOW else '✗'}")
        print(f"  Text Processing Utils: {'✓' if HAS_TEXT_PROCESSING else '✗'}")
        print(f"  Markdown Processor: {'✓' if HAS_MARKDOWN_PROCESSOR else '✗'}")
        print(f"  Log Processor: {'✓' if HAS_LOG_PROCESSOR else '✗'}")
        print(f"  Config Processor: {'✓' if HAS_CONFIG_PROCESSOR else '✗'}")
        print(f"  Integration Layer: {'✓' if HAS_INTEGRATION else '✗'}")

        # At least some components should be available
        assert any(
            [
                HAS_MARKDOWN_PROCESSOR,
                HAS_LOG_PROCESSOR,
                HAS_CONFIG_PROCESSOR,
                HAS_INTEGRATION,
            ],
        ), "No Phase 11 components found"

    @pytest.mark.skipif(
        not HAS_MARKDOWN_PROCESSOR,
        reason="MarkdownProcessor not available",
    )
    def test_markdown_processor(self):
        """Test Markdown processor functionality."""
        processor = MarkdownProcessor()

        # Create test markdown file
        md_file = self.temp_path / "test.md"
        md_file.write_text(
            """# Introduction

This is a test document with multiple sections.

## Section 1

Here's some content with a code block:

```python
def hello():
    return "world"
```

## Section 2

And a table:

| Column 1 | Column 2 |
|----------|----------|
| Value 1  | Value 2  |

### Subsection

Final content here.
""",
        )

        # Process the file
        # The markdown processor expects process() to be called with content and file_path
        content = md_file.read_text()
        chunks = processor.process(content, str(md_file))

        assert len(chunks) > 0

        # Verify code block is preserved
        assert any(
            "def hello():" in chunk.content and 'return "world"' in chunk.content
            for chunk in chunks
        )
        # Verify table is preserved
        assert any(
            "Column 1" in chunk.content and "Column 2" in chunk.content
            for chunk in chunks
        )

    @pytest.mark.skipif(not HAS_LOG_PROCESSOR, reason="LogProcessor not available")
    def test_log_processor(self):
        """Test log file processor functionality."""
        processor = LogProcessor()

        # Create test log file
        log_file = self.temp_path / "app.log"
        log_file.write_text(
            """2024-01-22 10:00:00 INFO Starting application
2024-01-22 10:00:01 DEBUG Loading configuration
2024-01-22 10:00:02 INFO Configuration loaded
2024-01-22 10:00:03 ERROR Failed to connect to database
java.sql.SQLException: Connection refused
    at com.example.db.connect(Database.java:42)
    at com.example.Main.main(Main.java:15)
2024-01-22 10:00:04 INFO Retrying connection
2024-01-22 10:00:05 INFO Connection established
2024-01-22 10:00:06 INFO Application started successfully
""",
        )

        # Process the file using the correct config format
        from chunker.processors import ProcessorConfig

        processor.config = ProcessorConfig(
            chunk_size=5,
            format_specific={"chunk_by": "lines", "max_chunk_lines": 5},
        )
        chunks = processor.process_file(str(log_file))

        assert len(chunks) > 0

        # Verify error with stack trace is kept together
        error_chunk = next((c for c in chunks if "ERROR" in c.content), None)
        assert error_chunk is not None
        assert "SQLException" in error_chunk.content
        assert "Database.java:42" in error_chunk.content

    @pytest.mark.skipif(
        not HAS_CONFIG_PROCESSOR,
        reason="ConfigProcessor not available",
    )
    def test_config_processor(self):
        """Test config file processor functionality."""
        processor = ConfigProcessor()

        # Test INI file
        ini_file = self.temp_path / "config.ini"
        ini_file.write_text(
            """[database]
host = localhost
port = 5432
name = myapp

[cache]
enabled = true
ttl = 3600

[logging]
level = INFO
file = app.log
""",
        )

        chunks = processor.process_file(str(ini_file))
        assert len(chunks) > 0
        # Verify sections are preserved
        assert any("[database]" in chunk.content for chunk in chunks)

        # Test YAML file
        yaml_file = self.temp_path / "config.yaml"
        yaml_file.write_text(
            """database:
  host: localhost
  port: 5432
  credentials:
    username: admin
    password: ${DB_PASSWORD}

cache:
  enabled: true
  ttl: 3600
""",
        )

        chunks = processor.process_file(str(yaml_file))
        assert len(chunks) > 0
        # Verify nested structure is preserved
        db_chunk = next((c for c in chunks if "database:" in c.content), None)
        assert db_chunk is not None
        assert "credentials:" in db_chunk.content

    @pytest.mark.skipif(not HAS_INTEGRATION, reason="Integration layer not available")
    def test_fallback_integration(self):
        """Test integration with fallback system."""
        fallback = SlidingWindowFallback()

        # Test automatic processor selection
        assert fallback.can_chunk("document.md")
        assert fallback.can_chunk("app.log")
        assert fallback.can_chunk("config.ini")
        assert fallback.can_chunk("random.txt")

        # Create test files
        md_file = self.temp_path / "readme.md"
        md_file.write_text("# Test\n\nThis is a test.")

        log_file = self.temp_path / "test.log"
        log_file.write_text("2024-01-22 INFO Test message")

        # Process different file types
        md_chunks = fallback.chunk_file(str(md_file))
        assert len(md_chunks) > 0

        log_chunks = fallback.chunk_file(str(log_file))
        assert len(log_chunks) > 0

    @pytest.mark.skipif(
        not (HAS_SLIDING_WINDOW and HAS_TEXT_PROCESSING),
        reason="Core components not available",
    )
    def test_sliding_window_with_text_processing(self):
        """Test sliding window engine with text processing utilities."""
        engine = DefaultSlidingWindowEngine()
        detector = SentenceBoundaryDetector()

        text = """This is the first sentence. This is the second sentence.
        This is the third sentence. This is the fourth sentence."""

        config = WindowConfig(
            size=50,
            unit=WindowUnit.CHARACTERS,
            overlap_strategy=OverlapStrategy.SEMANTIC,
            overlap_value=0.2,
        )

        chunks = engine.chunk_text(text, config, boundary_detector=detector)

        assert len(chunks) > 0
        # Verify chunks break at sentence boundaries
        for chunk in chunks:
            # Each chunk should end with a sentence terminator or be the last chunk
            content = chunk.content.strip()
            assert content.endswith(".") or chunk == chunks[-1]

    def test_end_to_end_processing(self):
        """Test complete end-to-end processing of various file types."""
        if not HAS_INTEGRATION:
            pytest.skip("Integration layer not available")

        fallback = SlidingWindowFallback()

        # Create a mixed repository structure
        (self.temp_path / "src").mkdir()
        (self.temp_path / "docs").mkdir()
        (self.temp_path / "logs").mkdir()
        (self.temp_path / "config").mkdir()

        # Python code (should use tree-sitter if available)
        py_file = self.temp_path / "src" / "main.py"
        py_file.write_text(
            """def main():
    print("Hello, world!")

if __name__ == "__main__":
    main()
""",
        )

        # Markdown documentation
        md_file = self.temp_path / "docs" / "README.md"
        md_file.write_text(
            """# Project Documentation

## Installation
Run `pip install myproject`

## Usage
```python
import myproject
myproject.run()
```
""",
        )

        # Log file
        log_file = self.temp_path / "logs" / "app.log"
        log_file.write_text(
            """2024-01-22 10:00:00 INFO Application started
2024-01-22 10:00:01 ERROR Connection failed
2024-01-22 10:00:02 INFO Retrying...
""",
        )

        # Config file
        config_file = self.temp_path / "config" / "settings.toml"
        config_file.write_text(
            """[app]
name = "MyProject"
version = "1.0.0"

[database]
url = "postgresql://localhost/mydb"
""",
        )

        # Process all files
        all_chunks = []
        for file_path in [py_file, md_file, log_file, config_file]:
            chunks = fallback.chunk_file(str(file_path))
            all_chunks.extend(chunks)

        assert len(all_chunks) > 0

        # Verify different processors were used
        chunk_types = set()
        for chunk in all_chunks:
            if hasattr(chunk, "metadata") and "processor" in chunk.metadata:
                chunk_types.add(chunk.metadata["processor"])

        print(f"\nProcessors used: {chunk_types}")

        # We should have at least 2 different processor types
        assert len(chunk_types) >= 2

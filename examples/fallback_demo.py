#!/usr/bin/env python3
"""Demonstration of fallback chunking functionality.

This script shows how the fallback chunking system works for files
that cannot be parsed by Tree-sitter.
"""

import sys
import tempfile
import warnings
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import builtins
import contextlib

from chunker.fallback import (
    FallbackWarning,
    FileTypeDetector,
    LineBasedChunker,
    LogChunker,
    MarkdownChunker,
)
from chunker.fallback.fallback_manager import FallbackManager
from chunker.interfaces.fallback import FallbackReason


def create_sample_files():
    """Create sample files for demonstration."""
    samples = {}

    # Create a log file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
        f.write(
            """2024-01-15 10:30:00 INFO Application started
2024-01-15 10:30:01 DEBUG Loading configuration from config.yaml
2024-01-15 10:30:02 INFO Configuration loaded successfully
2024-01-15 10:30:05 ERROR Failed to connect to database: Connection refused
2024-01-15 10:30:06 ERROR Retrying connection...
2024-01-15 10:30:10 WARN Using fallback data source
2024-01-15 10:30:15 INFO Processing started
2024-01-15 10:31:00 INFO Processed 1000 records
2024-01-15 10:31:30 INFO Processing complete
""",
        )
        samples["log"] = f.name

    # Create a markdown file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(
            """# Fallback Chunking Demo

This document demonstrates the fallback chunking system.

## Introduction

When Tree-sitter grammars are not available, the system falls back to
simple text-based chunking strategies.

### Features

- Line-based chunking
- Pattern-based chunking
- Specialized handlers for common formats

## Code Examples

Here's a Python example:

```python
def process_file(path):
    # This is example code
    with Path(path).open("r", ) as f:
        return f.read()
```

And a JavaScript example:

```javascript
function processFile(path) {
    // This is example code
    return fs.readFileSync(path, 'utf8');
}
```

## Configuration Files

The system can also handle configuration files:

- YAML files
- JSON files
- INI files

## Conclusion

Fallback chunking provides basic functionality when Tree-sitter is unavailable.
""",
        )
        samples["markdown"] = f.name

    # Create a CSV file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write(
            """timestamp,level,message,user_id
2024-01-15T10:30:00Z,INFO,User login,user123
2024-01-15T10:30:05Z,INFO,Page view: /dashboard,user123
2024-01-15T10:30:10Z,ERROR,Failed to load widget,user123
2024-01-15T10:30:15Z,INFO,User logout,user123
2024-01-15T10:30:20Z,INFO,User login,user456
2024-01-15T10:30:25Z,WARN,Slow query detected,user456
2024-01-15T10:30:30Z,INFO,Page view: /profile,user456
""",
        )
        samples["csv"] = f.name

    # Create a config file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".ini", delete=False) as f:
        f.write(
            """[database]
host = localhost
port = 5432
name = myapp
user = appuser

[logging]
level = INFO
format = %(asctime)s - %(name)s - %(levelname)s - %(message)s
file = app.log

[features]
enable_cache = true
cache_ttl = 3600
enable_notifications = false
""",
        )
        samples["config"] = f.name

    return samples


def demo_file_detection():
    """Demonstrate file type detection."""
    print("=== File Type Detection Demo ===\n")

    detector = FileTypeDetector()

    test_files = {
        "script.py": "Python script (has Tree-sitter support)",
        "data.log": "Log file",
        "README.md": "Markdown file",
        "config.yaml": "YAML configuration",
        "data.csv": "CSV data file",
        "notes.txt": "Plain text file",
    }

    for filename, description in test_files.items():
        file_type = detector.detect_file_type(filename)
        should_fallback, reason = detector.should_use_fallback(filename)

        print(f"{filename}:")
        print(f"  Description: {description}")
        print(f"  Detected type: {file_type.value}")
        print(f"  Needs fallback: {should_fallback}")
        if should_fallback:
            print(f"  Reason: {reason.value}")
        print()


def demo_fallback_chunking(sample_files):
    """Demonstrate fallback chunking with warnings."""
    print("\n=== Fallback Chunking Demo ===\n")

    manager = FallbackManager()

    # Configure warning handling
    warnings.filterwarnings("always", category=FallbackWarning)

    for file_type, file_path in sample_files.items():
        print(f"\n--- Processing {file_type} file: {Path(file_path).name} ---")

        # Get fallback info
        info = manager.get_fallback_info(file_path)
        print(f"File type: {info['file_type']}")
        print(f"Can chunk: {info['can_chunk']}")

        if info["suggested_grammar"]:
            print(f"Suggested grammar: {info['suggested_grammar']}")

        # Chunk the file
        try:
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")

                chunks = manager.chunk_file(file_path, FallbackReason.NO_GRAMMAR)

                print(f"\nCreated {len(chunks)} chunks:")
                for i, chunk in enumerate(chunks[:3]):  # Show first 3 chunks
                    print(f"\n  Chunk {i + 1}:")
                    print(f"    Type: {chunk.node_type}")
                    print(f"    Lines: {chunk.start_line}-{chunk.end_line}")
                    print(f"    Context: {chunk.parent_context}")
                    print(f"    Preview: {chunk.content[:60].strip()}...")

                if len(chunks) > 3:
                    print(f"\n  ... and {len(chunks) - 3} more chunks")

                # Show warnings
                if w:
                    print(f"\n⚠️  Warning emitted: {w[0].message}")

        except (FileNotFoundError, IndexError, KeyError) as e:
            print(f"\n❌ Error: {e}")


def demo_specialized_chunking(sample_files):
    """Demonstrate specialized chunking strategies."""
    print("\n\n=== Specialized Chunking Demo ===\n")

    # Demo log chunking by severity
    print("--- Log Chunking by Severity ---")
    log_chunker = LogChunker()
    log_chunker.file_path = sample_files["log"]

    with Path(sample_files["log"]).open(
        "r",
    ) as f:
        log_content = f.read()

    severity_chunks = log_chunker.chunk_by_severity(log_content, group_consecutive=True)
    print(f"Created {len(severity_chunks)} severity-based chunks:")
    for i, chunk in enumerate(severity_chunks):
        lines = chunk.content.strip().split("\n")
        print(f"  Chunk {i + 1} ({chunk.parent_context}): {len(lines)} lines")

    # Demo markdown code block extraction
    print("\n--- Markdown Code Block Extraction ---")
    md_chunker = MarkdownChunker()
    md_chunker.file_path = sample_files["markdown"]

    with Path(sample_files["markdown"]).open(
        "r",
    ) as f:
        md_content = f.read()

    code_blocks = md_chunker.extract_code_blocks(md_content)
    print(f"Found {len(code_blocks)} code blocks:")
    for block in code_blocks:
        print(f"  - {block.language} code at lines {block.start_line}-{block.end_line}")

    # Demo adaptive chunking
    print("\n--- Adaptive Line-Based Chunking ---")
    line_chunker = LineBasedChunker()
    line_chunker.file_path = sample_files["csv"]

    with Path(sample_files["csv"]).open(
        "r",
    ) as f:
        csv_content = f.read()

    adaptive_chunks = line_chunker.adaptive_chunk(
        csv_content,
        min_lines=3,
        max_lines=10,
        target_bytes=200,
    )
    print(f"Created {len(adaptive_chunks)} adaptive chunks based on content density")


def cleanup_files(sample_files):
    """Clean up temporary files."""
    for file_path in sample_files.values():
        with contextlib.suppress(builtins.BaseException):
            Path(file_path).unlink()


def main():
    """Run the demonstration."""
    print("🔄 Tree-sitter Chunker - Fallback System Demo\n")
    print("This demo shows how the system handles files without Tree-sitter support.")
    print("Note: Fallback chunking should only be used as a last resort!\n")

    # Create sample files
    sample_files = create_sample_files()

    try:
        # Run demos
        demo_file_detection()
        demo_fallback_chunking(sample_files)
        demo_specialized_chunking(sample_files)

        print("\n\n✅ Demo complete!")
        print("\nKey takeaways:")
        print(
            "1. Fallback chunking always emits warnings to encourage Tree-sitter usage",
        )
        print("2. Different file types get specialized chunking strategies")
        print("3. The system tries to preserve logical boundaries in the content")
        print("4. Tree-sitter grammars should be added whenever possible")

    finally:
        # Clean up
        cleanup_files(sample_files)


if __name__ == "__main__":
    main()

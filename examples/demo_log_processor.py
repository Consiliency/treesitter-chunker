#!/usr/bin/env python3
"""Demonstration of the LogProcessor capabilities."""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from chunker.processors.logs import LogProcessor


def print_chunk_info(chunk, index):
    """Pretty print chunk information."""
    print(f"\n--- Chunk {index + 1} ---")
    print(f"Type: {chunk.chunk_type}")
    print(f"Lines: {chunk.start_line}-{chunk.end_line} ({chunk.line_count} lines)")
    print(f"Size: {chunk.byte_size} bytes")

    # Print metadata
    print("Metadata:")
    for key, value in chunk.metadata.items():
        print(f"  {key}: {value}")

    # Print first few lines of content
    lines = chunk.content.split("\n")
    preview_lines = min(5, len(lines))
    print(f"\nContent preview (first {preview_lines} lines):")
    for _i, line in enumerate(lines[:preview_lines]):
        print(f"  {line}")
    if len(lines) > preview_lines:
        print(f"  ... ({len(lines) - preview_lines} more lines)")


def demo_time_based_chunking():
    """Demonstrate time-based chunking."""
    print("\n" + "=" * 60)
    print("DEMO: Time-based Chunking")
    print("=" * 60)

    processor = LogProcessor(
        config={
            "chunk_by": "time",
            "time_window": 60,  # 1 minute windows
        },
    )

    log_file = Path(__file__).parent / "logs" / "application.log"
    content = log_file.read_text()

    chunks = processor.process(content, log_file)
    print(f"\nProcessed {log_file.name} into {len(chunks)} time-based chunks")

    for i, chunk in enumerate(chunks[:3]):  # Show first 3 chunks
        print_chunk_info(chunk, i)


def demo_level_based_chunking():
    """Demonstrate log level-based chunking."""
    print("\n" + "=" * 60)
    print("DEMO: Log Level-based Chunking")
    print("=" * 60)

    processor = LogProcessor(
        config={
            "chunk_by": "level",
            "max_chunk_lines": 50,
        },
    )

    log_file = Path(__file__).parent / "logs" / "application.log"
    content = log_file.read_text()

    chunks = processor.process(content, log_file)
    print(f"\nProcessed {log_file.name} into {len(chunks)} level-based chunks")

    # Show chunks by level
    levels = {}
    for chunk in chunks:
        level = chunk.metadata.get("log_level", "UNKNOWN")
        if level not in levels:
            levels[level] = []
        levels[level].append(chunk)

    print("\nChunks by log level:")
    for level, level_chunks in sorted(levels.items()):
        total_lines = sum(c.line_count for c in level_chunks)
        print(f"  {level}: {len(level_chunks)} chunks, {total_lines} total lines")


def demo_session_detection():
    """Demonstrate session-based chunking."""
    print("\n" + "=" * 60)
    print("DEMO: Session-based Chunking")
    print("=" * 60)

    processor = LogProcessor(
        config={
            "chunk_by": "session",
            "detect_sessions": True,
        },
    )

    log_file = Path(__file__).parent / "logs" / "multiformat.log"
    content = log_file.read_text()

    chunks = processor.process(content, log_file)
    print(f"\nProcessed {log_file.name} into {len(chunks)} session-based chunks")

    for i, chunk in enumerate(chunks):
        session_id = chunk.metadata.get("session_id", "no_session")
        print(f"\nChunk {i + 1}: {session_id}")
        print(f"  Lines: {chunk.start_line}-{chunk.end_line}")

        # Show session markers if present
        lines = chunk.content.split("\n")
        for line in lines:
            if any(
                keyword in line.lower() for keyword in ["login", "session", "logout"]
            ):
                print(f"  Session marker: {line.strip()}")


def demo_error_context():
    """Demonstrate error context extraction."""
    print("\n" + "=" * 60)
    print("DEMO: Error Context Extraction")
    print("=" * 60)

    processor = LogProcessor(
        config={
            "chunk_by": "time",
            "time_window": 300,
            "group_errors": True,
            "context_lines": 3,
        },
    )

    log_file = Path(__file__).parent / "logs" / "application.log"
    content = log_file.read_text()

    chunks = processor.process(content, log_file)

    # Find chunks with errors
    error_chunks = [c for c in chunks if c.metadata.get("has_errors")]
    print(f"\nFound {len(error_chunks)} chunks containing errors")

    for i, chunk in enumerate(error_chunks):
        print(f"\nError Chunk {i + 1}:")
        print(f"  Error count: {chunk.metadata['error_count']}")
        print(f"  Lines: {chunk.start_line}-{chunk.end_line}")

        # Show error lines
        lines = chunk.content.split("\n")
        print("  Error messages:")
        for line in lines:
            if "[ERROR]" in line or "[CRITICAL]" in line:
                print(f"    {line.strip()}")


def demo_format_detection():
    """Demonstrate multi-format log processing."""
    print("\n" + "=" * 60)
    print("DEMO: Multi-format Log Detection")
    print("=" * 60)

    processor = LogProcessor()

    # Process different log formats
    log_files = [
        "syslog_sample.log",
        "apache_access.log",
        "application.log",
        "multiformat.log",
    ]

    for filename in log_files:
        log_file = Path(__file__).parent / "logs" / filename
        if log_file.exists():
            content = log_file.read_text()
            chunks = processor.process(content, log_file)

            if chunks:
                formats = set()
                for chunk in chunks:
                    formats.update(chunk.metadata.get("formats", []))

                print(f"\n{filename}:")
                print(
                    f"  Detected formats: {', '.join(formats) if formats else 'generic'}",
                )
                print(f"  Total chunks: {len(chunks)}")
                print(f"  Total lines: {sum(c.line_count for c in chunks)}")


def demo_streaming():
    """Demonstrate streaming log processing."""
    print("\n" + "=" * 60)
    print("DEMO: Streaming Log Processing")
    print("=" * 60)

    processor = LogProcessor(
        config={
            "chunk_by": "lines",
            "max_chunk_lines": 10,
        },
    )

    # Simulate streaming by reading file line by line
    log_file = Path(__file__).parent / "logs" / "application.log"

    print(f"\nStreaming {log_file.name}...")

    def line_generator():
        with Path(log_file).open(
            "r",
        ) as f:
            yield from f

    chunk_count = 0
    total_lines = 0

    for chunk in processor.process_stream(line_generator(), log_file):
        chunk_count += 1
        total_lines += chunk.line_count

        # Show progress every 5 chunks
        if chunk_count % 5 == 0:
            print(f"  Processed {chunk_count} chunks, {total_lines} lines...")

    print(f"\nStreaming complete: {chunk_count} chunks, {total_lines} lines")


def main():
    """Run all demonstrations."""
    print("Log Processor Demonstration")
    print("===========================")

    demos = [
        demo_format_detection,
        demo_time_based_chunking,
        demo_level_based_chunking,
        demo_session_detection,
        demo_error_context,
        demo_streaming,
    ]

    for demo in demos:
        try:
            demo()
        except (TypeError, ValueError) as e:
            print(f"\nError in {demo.__name__}: {e}")

    print("\n" + "=" * 60)
    print("Demonstration complete!")


if __name__ == "__main__":
    main()

"""Log file processor with timestamp-based chunking and session detection.

This module implements specialized processing for log files, supporting various
formats (syslog, apache, custom) with features like:
- Timestamp-based chunking
- Log level grouping
- Session boundary detection
- Error context extraction
- Multi-line log entry handling
"""

import re
from collections import deque
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from .base import SpecializedProcessor, TextChunk

# Common log patterns - Order matters! More specific patterns should come first
LOG_PATTERNS = {
    # Java/Log4j style: 2024-01-01 12:00:00,000 INFO [Thread-1] com.example.Class - message
    "log4j": re.compile(
        r"^(?P<timestamp>\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}[,\.]\d{3})\s+"
        r"(?P<level>\w+)\s+\[(?P<thread>[^\]]+)\]\s+"
        r"(?P<logger>\S+)\s*-\s*(?P<message>.*?)$",
    ),
    # Syslog format: Jan 1 00:00:00 hostname process[pid]: message
    "syslog": re.compile(
        r"^(?P<timestamp>\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})\s+"
        r"(?P<hostname>\S+)\s+(?P<process>[^\[\s]+)(?:\[(?P<pid>\d+)\])?\s*:\s*"
        r"(?P<message>.*?)$",
    ),
    # Apache common/combined log format
    "apache": re.compile(
        r"^(?P<ip>\S+)\s+\S+\s+\S+\s+\[(?P<timestamp>[^\]]+)\]\s+"
        r'"(?P<request>[^"]+)"\s+(?P<status>\d+)\s+(?P<size>\S+)'
        r'(?:\s+"(?P<referer>[^"]+)"\s+"(?P<agent>[^"]+)")?',
    ),
    # Common application logs: 2024-01-01 12:00:00,000 [LEVEL] message
    "iso_timestamp": re.compile(
        r"^(?P<timestamp>\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}(?:[,\.]\d{3})?(?:Z|[+-]\d{2}:?\d{2})?)\s*"
        r"(?:\[(?P<level>\w+)\])?\s*(?P<message>.*?)$",
    ),
    # Generic timestamp at start of line
    "generic_timestamp": re.compile(
        r"^(?P<timestamp>(?:\d{4}[-/]\d{2}[-/]\d{2}|\w{3}\s+\d{1,2})\s+\d{2}:\d{2}:\d{2}(?:[,\.]\d{3})?)\s+",
    ),
}

# Log level patterns
LOG_LEVELS = {
    "CRITICAL": re.compile(r"\b(?:CRITICAL|FATAL|EMERG(?:ENCY)?)\b", re.I),
    "ERROR": re.compile(r"\b(?:ERROR|ERR|SEVERE)\b", re.I),
    "WARNING": re.compile(r"\b(?:WARNING|WARN)\b", re.I),
    "INFO": re.compile(r"\b(?:INFO|INFORMATION|NOTICE)\b", re.I),
    "DEBUG": re.compile(r"\b(?:DEBUG|TRACE|VERBOSE)\b", re.I),
}

# Session boundary patterns
SESSION_PATTERNS = {
    "start": [
        re.compile(r"session\s+start|login|authentication\s+success", re.I),
        re.compile(r"connection\s+established|connected\s+from", re.I),
        re.compile(r"starting\s+service|server\s+started", re.I),
    ],
    "end": [
        re.compile(r"session\s+end|logout|disconnected", re.I),
        re.compile(r"connection\s+closed|connection\s+terminated", re.I),
        re.compile(r"stopping\s+service|server\s+stopped|shutdown", re.I),
    ],
}

# Stack trace patterns
STACK_TRACE_PATTERNS = [
    re.compile(r"^\s*at\s+[\w\.$]+\([\w\.]+:\d+\)"),  # Java
    re.compile(r'^\s*File\s+"[^"]+",\s+line\s+\d+'),  # Python
    re.compile(r"^\s*#\d+\s+0x[0-9a-fA-F]+\s+in\s+"),  # C/C++
    re.compile(r"^\s*\^\s*~+"),  # Error indicator lines
    re.compile(r"^Caused by:|^Traceback|^Exception|^Stack trace:", re.I),
]


@dataclass
class LogEntry:
    """Represents a single log entry with parsed metadata."""

    content: str
    timestamp: datetime | None = None
    level: str | None = None
    line_numbers: list[int] = field(default_factory=list)
    byte_offsets: tuple[int, int] = (0, 0)
    metadata: dict[str, Any] = field(default_factory=dict)
    is_continuation: bool = False


class LogProcessor(SpecializedProcessor):
    """Processor for log files with advanced chunking capabilities."""

    def __init__(self, config: dict[str, Any] | None = None):
        """Initialize log processor.

        Config options:
            chunk_by: 'time' | 'lines' | 'session' | 'level' (default: 'time')
            time_window: seconds for time-based chunking (default: 300)
            max_chunk_lines: maximum lines per chunk (default: 1000)
            context_lines: lines to include for error context (default: 5)
            detect_sessions: enable session detection (default: True)
            group_errors: group error messages with context (default: True)
            patterns: additional custom patterns
            timezone: timezone for parsing (default: UTC)
        """
        # Store config first
        # Call parent init first to set up config properly
        super().__init__(config)

        # Configure chunking strategy
        if isinstance(self.config, dict):
            self.chunk_by = self.config.get("chunk_by", "time")
            self.time_window = timedelta(seconds=self.config.get("time_window", 300))
            self.max_chunk_lines = self.config.get("max_chunk_lines", 1000)
            self.context_lines = self.config.get("context_lines", 5)
            self.detect_sessions = self.config.get("detect_sessions", True)
            self.group_errors = self.config.get("group_errors", True)
        else:
            # ProcessorConfig object
            self.chunk_by = self.config.format_specific.get("chunk_by", "time")
            self.time_window = timedelta(
                seconds=self.config.format_specific.get("time_window", 300),
            )
            self.max_chunk_lines = self.config.format_specific.get(
                "max_chunk_lines",
                1000,
            )
            self.context_lines = self.config.format_specific.get("context_lines", 5)
            self.detect_sessions = self.config.format_specific.get(
                "detect_sessions",
                True,
            )
            self.group_errors = self.config.format_specific.get("group_errors", True)

        # Initialize pattern matchers
        self._init_patterns()

        # State for streaming
        self._buffer: deque[LogEntry] = deque()
        self._current_session_id: str | None = None
        self._session_counter = 0

    def _validate_config(self) -> None:
        """Validate processor configuration."""
        # Skip validation for now since we're handling both dict and ProcessorConfig

    def _validate_config_old(self) -> None:
        """Validate processor configuration."""
        valid_chunk_by = {"time", "lines", "session", "level"}
        if self.chunk_by not in valid_chunk_by:
            raise ValueError(
                f"Invalid chunk_by: {self.chunk_by}. Must be one of {valid_chunk_by}",
            )

        if self.time_window.total_seconds() <= 0:
            raise ValueError("time_window must be positive")

        if self.max_chunk_lines <= 0:
            raise ValueError("max_chunk_lines must be positive")

    def _init_patterns(self) -> None:
        """Initialize pattern matchers from config and defaults."""
        # Use OrderedDict to preserve pattern matching order
        from collections import OrderedDict

        self.patterns = OrderedDict(LOG_PATTERNS)

        # Add custom patterns from config
        # Get custom patterns from config
        if isinstance(self.config, dict):
            custom_patterns = self.config.get("patterns", {})
        else:
            # ProcessorConfig object
            custom_patterns = self.config.format_specific.get("patterns", {})
        for name, pattern in custom_patterns.items():
            if isinstance(pattern, str):
                self.patterns[name] = re.compile(pattern)
            else:
                self.patterns[name] = pattern

    def can_handle(self, file_path: str, content: str | None = None) -> bool:
        """Check if this processor can handle the file."""
        return self.can_process(Path(file_path), content)

    def can_process(self, file_path: Path, content: str | None = None) -> bool:
        """Check if this processor can handle the given file."""
        # Check by extension
        log_extensions = {".log", ".txt", ".out"}
        if file_path.suffix.lower() in log_extensions:
            return True

        # Check common log file names
        log_names = {"syslog", "messages", "access", "error", "debug"}
        if any(name in file_path.name.lower() for name in log_names):
            return True

        # Check content for log patterns if provided
        if content:
            lines = content.split("\n", 10)  # Check first 10 lines
            for line in lines:
                if self._detect_log_format(line):
                    return True

        return False

    def process_file(
        self,
        file_path: str | Path,
        config: dict[str, Any] | None = None,
    ) -> list[TextChunk]:
        """Process a log file and return text chunks."""
        with open(file_path, encoding="utf-8") as f:
            content = f.read()
        return self.process(content, Path(file_path))

    def process(self, content: str, file_path: Path | None = None) -> list[TextChunk]:
        """Process log content and return chunks."""
        if not content or not content.strip():
            return []

        chunks = []
        lines = content.split("\n")

        # Parse all entries first
        entries = self._parse_entries(lines)

        # Apply chunking strategy
        if self.chunk_by == "time":
            chunks = self._chunk_by_time(entries)
        elif self.chunk_by == "lines":
            chunks = self._chunk_by_lines(entries)
        elif self.chunk_by == "session":
            chunks = self._chunk_by_session(entries)
        elif self.chunk_by == "level":
            chunks = self._chunk_by_level(entries)

        # Post-process for error grouping if enabled
        if self.group_errors:
            chunks = self._group_error_contexts(chunks, entries)

        return chunks

    def process_stream(
        self,
        stream: Iterator[str],
        file_path: Path | None = None,
    ) -> Iterator[TextChunk]:
        """Process log content from a stream."""
        line_number = 0
        byte_offset = 0

        for line in stream:
            line_number += 1
            line_bytes = len(line.encode("utf-8"))

            entry = self._parse_line(line, line_number, byte_offset)
            byte_offset += line_bytes

            # Add to buffer
            self._buffer.append(entry)

            # Check if we should emit a chunk
            chunk = self._check_emit_chunk()
            if chunk:
                yield chunk

        # Emit final chunk
        if self._buffer:
            chunk = self._create_chunk_from_buffer()
            if chunk:
                yield chunk

    def _parse_entries(self, lines: list[str]) -> list[LogEntry]:
        """Parse all log entries from lines."""
        entries = []
        current_entry = None
        byte_offset = 0

        for i, line in enumerate(lines):
            line_bytes = len(line.encode("utf-8"))

            # Check if this is a new entry or continuation
            if self._is_new_entry(line):
                if current_entry:
                    entries.append(current_entry)

                current_entry = self._parse_line(line, i + 1, byte_offset)
            # Continuation of previous entry
            elif current_entry:
                current_entry.content += "\n" + line
                current_entry.line_numbers.append(i + 1)
                current_entry.byte_offsets = (
                    current_entry.byte_offsets[0],
                    byte_offset + line_bytes,
                )
            else:
                # Orphan line at start
                current_entry = LogEntry(
                    content=line,
                    line_numbers=[i + 1],
                    byte_offsets=(byte_offset, byte_offset + line_bytes),
                    is_continuation=True,
                )

            byte_offset += line_bytes

        # Don't forget the last entry
        if current_entry:
            entries.append(current_entry)

        return entries

    def _parse_line(self, line: str, line_number: int, byte_offset: int) -> LogEntry:
        """Parse a single log line into a LogEntry."""
        line_bytes = len(line.encode("utf-8"))
        entry = LogEntry(
            content=line,
            line_numbers=[line_number],
            byte_offsets=(byte_offset, byte_offset + line_bytes),
        )

        # Try to match against known patterns
        for format_name, pattern in self.patterns.items():
            match = pattern.match(line)
            if match:
                groups = match.groupdict()
                entry.metadata["format"] = format_name

                # Extract timestamp
                if "timestamp" in groups:
                    entry.timestamp = self._parse_timestamp(
                        groups["timestamp"],
                        format_name,
                    )

                # Extract log level
                if groups.get("level"):
                    entry.level = groups["level"].upper()
                else:
                    # Try to detect level from content
                    entry.level = self._detect_log_level(line)

                # Store other metadata
                for key, value in groups.items():
                    if key not in ("timestamp", "level", "message"):
                        entry.metadata[key] = value

                break

        # If no pattern matched, try generic detection
        if not entry.metadata.get("format"):
            entry.level = self._detect_log_level(line)

        return entry

    def _is_new_entry(self, line: str) -> bool:
        """Check if line starts a new log entry."""
        # Empty lines are not new entries
        if not line.strip():
            return False

        # Check for timestamp at start
        for pattern in self.patterns.values():
            if pattern.match(line):
                return True

        # Check for stack trace patterns (these are continuations)
        for pattern in STACK_TRACE_PATTERNS:
            if pattern.match(line):
                return False

        # Lines starting with whitespace are usually continuations
        if line[0].isspace():
            return False

        return True

    def _detect_log_format(self, line: str) -> str | None:
        """Detect log format from a line."""
        for format_name, pattern in self.patterns.items():
            if pattern.match(line):
                return format_name
        return None

    def _detect_log_level(self, line: str) -> str | None:
        """Detect log level from line content."""
        for level, pattern in LOG_LEVELS.items():
            if pattern.search(line):
                return level
        return None

    def _parse_timestamp(self, timestamp_str: str, format_name: str) -> datetime | None:
        """Parse timestamp string based on format."""
        try:
            if format_name == "syslog":
                # Syslog doesn't include year, assume current year
                current_year = datetime.now().year
                dt = datetime.strptime(
                    f"{current_year} {timestamp_str}",
                    "%Y %b %d %H:%M:%S",
                )
                # Add UTC timezone for consistency
                from datetime import timezone

                return dt.replace(tzinfo=timezone.utc)
            if format_name == "apache":
                return datetime.strptime(timestamp_str, "%d/%b/%Y:%H:%M:%S %z")
            if format_name in ("iso_timestamp", "log4j"):
                # Try various ISO formats
                formats = [
                    "%Y-%m-%d %H:%M:%S,%f",
                    "%Y-%m-%d %H:%M:%S.%f",
                    "%Y-%m-%dT%H:%M:%S",
                    "%Y-%m-%dT%H:%M:%S.%f",
                    "%Y-%m-%dT%H:%M:%S%z",
                    "%Y-%m-%dT%H:%M:%S.%f%z",
                ]
                for fmt in formats:
                    try:
                        dt = datetime.strptime(timestamp_str, fmt)
                        # If no timezone info, assume UTC for consistency
                        if dt.tzinfo is None:
                            from datetime import timezone

                            dt = dt.replace(tzinfo=timezone.utc)
                        return dt
                    except ValueError:
                        continue
            else:
                # Try generic parsing
                try:
                    from dateutil import parser

                    dt = parser.parse(timestamp_str)
                    # If no timezone info, assume UTC
                    if dt.tzinfo is None:
                        from datetime import timezone

                        dt = dt.replace(tzinfo=timezone.utc)
                    return dt
                except:
                    pass
        except Exception:
            pass
        return None

    def _chunk_by_time(self, entries: list[LogEntry]) -> list[TextChunk]:
        """Create chunks based on time windows."""
        if not entries:
            return []

        chunks = []
        current_chunk_entries = []
        chunk_start_time = None

        for entry in entries:
            if entry.timestamp:
                if chunk_start_time is None:
                    chunk_start_time = entry.timestamp

                # Check if this entry exceeds time window
                if entry.timestamp - chunk_start_time > self.time_window:
                    # Create chunk from accumulated entries
                    if current_chunk_entries:
                        chunk = self._create_chunk(current_chunk_entries)
                        chunks.append(chunk)

                    # Start new chunk
                    current_chunk_entries = [entry]
                    chunk_start_time = entry.timestamp
                else:
                    current_chunk_entries.append(entry)
            else:
                # No timestamp, add to current chunk
                current_chunk_entries.append(entry)

            # Check max lines limit
            if len(current_chunk_entries) >= self.max_chunk_lines:
                chunk = self._create_chunk(current_chunk_entries)
                chunks.append(chunk)
                current_chunk_entries = []
                chunk_start_time = None

        # Don't forget the last chunk
        if current_chunk_entries:
            chunk = self._create_chunk(current_chunk_entries)
            chunks.append(chunk)

        return chunks

    def _chunk_by_lines(self, entries: list[LogEntry]) -> list[TextChunk]:
        """Create chunks based on line count."""
        chunks = []

        for i in range(0, len(entries), self.max_chunk_lines):
            chunk_entries = entries[i : i + self.max_chunk_lines]
            chunk = self._create_chunk(chunk_entries)
            chunks.append(chunk)

        return chunks

    def _chunk_by_session(self, entries: list[LogEntry]) -> list[TextChunk]:
        """Create chunks based on session boundaries."""
        if not self.detect_sessions:
            return self._chunk_by_time(entries)

        chunks = []
        current_session_entries = []

        for entry in entries:
            # Check for session start
            if self._is_session_start(entry):
                # End previous session
                if current_session_entries:
                    chunk = self._create_chunk(current_session_entries)
                    chunk.metadata["session_id"] = self._get_session_id()
                    chunks.append(chunk)

                # Start new session
                self._session_counter += 1
                current_session_entries = [entry]

            # Check for session end
            elif self._is_session_end(entry):
                current_session_entries.append(entry)
                # Create chunk for completed session
                chunk = self._create_chunk(current_session_entries)
                chunk.metadata["session_id"] = self._get_session_id()
                chunks.append(chunk)
                current_session_entries = []

            else:
                current_session_entries.append(entry)

            # Apply max lines limit
            if len(current_session_entries) >= self.max_chunk_lines:
                chunk = self._create_chunk(current_session_entries)
                chunk.metadata["session_id"] = self._get_session_id()
                chunks.append(chunk)
                current_session_entries = []

        # Handle remaining entries
        if current_session_entries:
            chunk = self._create_chunk(current_session_entries)
            chunk.metadata["session_id"] = self._get_session_id()
            chunks.append(chunk)

        return chunks

    def _chunk_by_level(self, entries: list[LogEntry]) -> list[TextChunk]:
        """Create chunks grouped by log level."""
        level_groups = {}

        for entry in entries:
            level = entry.level or "UNKNOWN"
            if level not in level_groups:
                level_groups[level] = []
            level_groups[level].append(entry)

        chunks = []
        for level, level_entries in level_groups.items():
            # Further chunk by max lines
            for i in range(0, len(level_entries), self.max_chunk_lines):
                chunk_entries = level_entries[i : i + self.max_chunk_lines]
                chunk = self._create_chunk(chunk_entries)
                chunk.metadata["log_level"] = level
                chunks.append(chunk)

        # Sort chunks by first entry's line number
        chunks.sort(key=lambda c: c.start_line)

        return chunks

    def _group_error_contexts(
        self,
        chunks: list[TextChunk],
        all_entries: list[LogEntry],
    ) -> list[TextChunk]:
        """Group error messages with surrounding context."""
        if not self.group_errors:
            return chunks

        # Build entry index for quick lookup
        entry_by_line = {}
        for entry in all_entries:
            for line_num in entry.line_numbers:
                entry_by_line[line_num] = entry

        enhanced_chunks = []

        for chunk in chunks:
            # Check if chunk contains errors
            error_lines = []
            for line_num in range(chunk.start_line, chunk.end_line + 1):
                entry = entry_by_line.get(line_num)
                if entry and entry.level in ("ERROR", "CRITICAL"):
                    error_lines.append(line_num)

            if error_lines:
                # Expand chunk to include context
                context_start = max(1, min(error_lines) - self.context_lines)
                context_end = max(error_lines) + self.context_lines

                # Collect entries in context range
                context_entries = []
                for line_num in range(context_start, context_end + 1):
                    if line_num in entry_by_line:
                        entry = entry_by_line[line_num]
                        if entry not in context_entries:
                            context_entries.append(entry)

                # Create enhanced chunk
                if context_entries:
                    enhanced_chunk = self._create_chunk(context_entries)
                    enhanced_chunk.metadata.update(chunk.metadata)
                    enhanced_chunk.metadata["has_errors"] = True
                    enhanced_chunk.metadata["error_count"] = len(error_lines)
                    enhanced_chunks.append(enhanced_chunk)
            else:
                enhanced_chunks.append(chunk)

        return enhanced_chunks

    def _is_session_start(self, entry: LogEntry) -> bool:
        """Check if entry indicates session start."""
        for pattern in SESSION_PATTERNS["start"]:
            if pattern.search(entry.content):
                return True
        return False

    def _is_session_end(self, entry: LogEntry) -> bool:
        """Check if entry indicates session end."""
        for pattern in SESSION_PATTERNS["end"]:
            if pattern.search(entry.content):
                return True
        return False

    def _get_session_id(self) -> str:
        """Get current session ID."""
        return f"session_{self._session_counter}"

    def _create_chunk(self, entries: list[LogEntry]) -> TextChunk:
        """Create a TextChunk from a list of LogEntry objects."""
        if not entries:
            return None

        # Combine content
        content = "\n".join(entry.content for entry in entries)

        # Calculate line range
        all_lines = []
        for entry in entries:
            all_lines.extend(entry.line_numbers)
        start_line = min(all_lines)
        end_line = max(all_lines)

        # Calculate byte range
        start_byte = entries[0].byte_offsets[0]
        end_byte = entries[-1].byte_offsets[1]

        # Collect metadata
        metadata = {
            "entry_count": len(entries),
            "formats": list(
                {e.metadata.get("format") for e in entries if e.metadata.get("format")},
            ),
            "levels": list({e.level for e in entries if e.level}),
        }

        # Add timestamp range if available
        timestamps = [e.timestamp for e in entries if e.timestamp]
        if timestamps:
            metadata["start_time"] = min(timestamps).isoformat()
            metadata["end_time"] = max(timestamps).isoformat()

        return TextChunk(
            content=content,
            start_line=start_line,
            end_line=end_line,
            start_byte=start_byte,
            end_byte=end_byte,
            metadata=metadata,
            chunk_type="log",
        )

    def _check_emit_chunk(self) -> TextChunk | None:
        """Check if buffer should be emitted as a chunk."""
        if not self._buffer:
            return None

        should_emit = False

        if self.chunk_by == "lines" and len(self._buffer) >= self.max_chunk_lines:
            should_emit = True

        elif self.chunk_by == "time" and len(self._buffer) > 1:
            # Check time window
            first_ts = self._buffer[0].timestamp
            last_ts = self._buffer[-1].timestamp
            if first_ts and last_ts and (last_ts - first_ts) > self.time_window:
                should_emit = True

        elif self.chunk_by == "session":
            # Check for session end in buffer
            for entry in self._buffer:
                if self._is_session_end(entry):
                    should_emit = True
                    break

        if should_emit:
            return self._create_chunk_from_buffer()

        return None

    def _create_chunk_from_buffer(self) -> TextChunk | None:
        """Create chunk from current buffer and clear it."""
        if not self._buffer:
            return None

        entries = list(self._buffer)
        self._buffer.clear()

        return self._create_chunk(entries)

    def get_supported_formats(self) -> list[str]:
        """Get list of supported file formats."""
        return [".log", ".txt", ".out"]

    def get_metadata(self) -> dict[str, Any]:
        """Get processor metadata."""
        metadata = super().get_metadata()
        metadata.update(
            {
                "chunk_by": self.chunk_by,
                "time_window": self.time_window.total_seconds(),
                "max_chunk_lines": self.max_chunk_lines,
                "context_lines": self.context_lines,
                "detect_sessions": self.detect_sessions,
                "group_errors": self.group_errors,
                "pattern_names": list(self.patterns.keys()),
            },
        )
        return metadata

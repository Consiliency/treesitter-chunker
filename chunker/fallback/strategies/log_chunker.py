"""Specialized chunker for log files."""

import logging
import re
from datetime import datetime, timedelta
from re import Pattern
from typing import ClassVar

from chunker.fallback.base import FallbackChunker
from chunker.interfaces.fallback import ChunkingMethod, FallbackConfig
from chunker.interfaces.fallback import LogChunker as ILogChunker
from chunker.types import CodeChunk

logger = logging.getLogger(__name__)


class LogChunker(FallbackChunker, ILogChunker):
    """Specialized chunker for log files.

    Supports chunking by:
    - Time windows
    - Log severity levels
    - Session/request IDs
    - Mixed strategies
    """

    TIMESTAMP_PATTERNS: ClassVar[list[tuple[str, str]]] = [
        (
            "(\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d{3})?(?:Z|[+-]\\d{2}:\\d{2})?)",
            "%Y-%m-%dT%H:%M:%S",
        ),
        ("(\\d{4}-\\d{2}-\\d{2} \\d{2}:\\d{2}:\\d{2})", "%Y-%m-%d %H:%M:%S"),
        ("(\\w{3} \\d{1,2} \\d{2}:\\d{2}:\\d{2})", "%b %d %H:%M:%S"),
        (
            "\\[(\\d{2}/\\w{3}/\\d{4}:\\d{2}:\\d{2}:\\d{2} [+-]\\d{4})\\]",
            "%d/%b/%Y:%H:%M:%S %z",
        ),
    ]
    LEVEL_PATTERNS: ClassVar[list[str]] = [
        "\\b(TRACE|DEBUG|INFO|WARN(?:ING)?|ERROR|FATAL|CRITICAL)\\b",
        "\\b(trace|debug|info|warn(?:ing)?|error|fatal|critical)\\b",
        "\\[\\s*(TRACE|DEBUG|INFO|WARN(?:ING)?|ERROR|FATAL|CRITICAL)\\s*\\]",
    ]

    def __init__(self):
        """Initialize log chunker."""
        config = FallbackConfig(method=ChunkingMethod.LINE_BASED)
        super().__init__(config)
        self._timestamp_pattern: Pattern | None = None
        self._timestamp_format: str | None = None
        self._level_pattern: Pattern | None = None

    def detect_log_format(self, content: str) -> dict[str, any]:
        """Detect log format from content sample.

        Args:
            content: Log content sample

        Returns:
            Dictionary with detected format info
        """
        format_info = {
            "has_timestamps": False,
            "timestamp_pattern": None,
            "timestamp_format": None,
            "has_levels": False,
            "level_pattern": None,
            "multiline": False,
        }
        lines = content.splitlines()[:100]
        sample = "\n".join(lines)
        for pattern_str, date_format in self.TIMESTAMP_PATTERNS:
            pattern = re.compile(pattern_str)
            if pattern.search(sample):
                format_info["has_timestamps"] = True
                format_info["timestamp_pattern"] = pattern
                format_info["timestamp_format"] = date_format
                self._timestamp_pattern = pattern
                self._timestamp_format = date_format
                break
        for level_pattern_str in self.LEVEL_PATTERNS:
            pattern = re.compile(level_pattern_str)
            if pattern.search(sample):
                format_info["has_levels"] = True
                format_info["level_pattern"] = pattern
                self._level_pattern = pattern
                break
        if format_info["has_timestamps"]:
            non_timestamp_lines = 0
            for line in lines[1:]:
                if line.strip() and not format_info["timestamp_pattern"].match(line):
                    non_timestamp_lines += 1
            if non_timestamp_lines > len(lines) * 0.2:
                format_info["multiline"] = True
        return format_info

    def chunk_by_timestamp(
        self,
        content: str,
        time_window_seconds: int,
    ) -> list[CodeChunk]:
        """Chunk logs by time window.

        Args:
            content: Log content
            time_window_seconds: Size of time window

        Returns:
            List of chunks grouped by time
        """
        format_info = self.detect_log_format(content)
        if not format_info["has_timestamps"]:
            logger.warning(
                "No timestamps detected, falling back to line-based chunking",
            )
            return self.chunk_by_lines(content, 100, 0)
        chunks = []
        current_chunk_lines = []
        current_window_start = None
        current_start_line = 1
        lines = content.splitlines(keepends=True)
        for i, line in enumerate(lines):
            timestamp = self._extract_timestamp(line)
            if timestamp:
                if current_window_start is None:
                    current_window_start = timestamp
                    current_start_line = i + 1
                window_end = current_window_start + timedelta(
                    seconds=time_window_seconds,
                )
                if timestamp > window_end:
                    if current_chunk_lines:
                        chunk = self._create_log_chunk(
                            current_chunk_lines,
                            current_start_line,
                            i,
                            f"time_window_{current_window_start.isoformat()}",
                        )
                        chunks.append(chunk)
                    current_chunk_lines = [line]
                    current_window_start = timestamp
                    current_start_line = i + 1
                else:
                    current_chunk_lines.append(line)
            else:
                current_chunk_lines.append(line)
        if current_chunk_lines:
            chunk = self._create_log_chunk(
                current_chunk_lines,
                current_start_line,
                len(lines),
                f"time_window_{current_window_start.isoformat() if current_window_start else 'unknown'}",
            )
            chunks.append(chunk)
        return chunks

    def chunk_by_severity(
        self,
        content: str,
        group_consecutive: bool = True,
    ) -> list[CodeChunk]:
        """Chunk logs by severity level.

        Args:
            content: Log content
            group_consecutive: Group consecutive same-severity entries

        Returns:
            List of chunks grouped by severity
        """
        format_info = self.detect_log_format(content)
        if not format_info["has_levels"]:
            logger.warning(
                "No log levels detected, falling back to line-based chunking",
            )
            return self.chunk_by_lines(content, 100, 0)
        chunks = []
        current_chunk_lines = []
        current_level = None
        current_start_line = 1
        lines = content.splitlines(keepends=True)
        for i, line in enumerate(lines):
            level = self._extract_log_level(line)
            if level:
                if (
                    not group_consecutive or (current_level and level != current_level)
                ) and current_chunk_lines:
                    chunk = self._create_log_chunk(
                        current_chunk_lines,
                        current_start_line,
                        i,
                        f"severity_{current_level or 'unknown'}",
                    )
                    chunks.append(chunk)
                    current_chunk_lines = []
                    current_start_line = i + 1
                current_level = level
                current_chunk_lines.append(line)
            else:
                current_chunk_lines.append(line)
        if current_chunk_lines:
            chunk = self._create_log_chunk(
                current_chunk_lines,
                current_start_line,
                len(lines),
                f"severity_{current_level or 'unknown'}",
            )
            chunks.append(chunk)
        return chunks

    def chunk_by_session(self, content: str, session_pattern: str) -> list[CodeChunk]:
        """Chunk logs by session/request ID.

        Args:
            content: Log content
            session_pattern: Regex pattern to extract session ID

        Returns:
            List of chunks grouped by session
        """
        pattern = re.compile(session_pattern)
        chunks = []
        session_logs: dict[str, list[tuple[int, str]]] = {}
        lines = content.splitlines(keepends=True)
        for i, line in enumerate(lines):
            match = pattern.search(line)
            if match:
                session_id = match.group(1) if match.groups() else match.group(0)
                if session_id not in session_logs:
                    session_logs[session_id] = []
                session_logs[session_id].append((i + 1, line))
            else:
                if "unknown" not in session_logs:
                    session_logs["unknown"] = []
                session_logs["unknown"].append((i + 1, line))
        for session_id, session_lines in session_logs.items():
            if not session_lines:
                continue
            session_lines.sort(key=lambda x: x[0])
            content_lines = [line for _, line in session_lines]
            start_line = session_lines[0][0]
            end_line = session_lines[-1][0]
            chunk = self._create_log_chunk(
                content_lines,
                start_line,
                end_line,
                f"session_{session_id}",
            )
            chunks.append(chunk)
        chunks.sort(key=lambda c: c.start_line)
        return chunks

    def _extract_timestamp(self, line: str) -> datetime | None:
        """Extract timestamp from log line."""
        if not self._timestamp_pattern or not self._timestamp_format:
            return None
        match = self._timestamp_pattern.search(line)
        if match:
            try:
                timestamp_str = match.group(1)
                if "%Y" not in self._timestamp_format:
                    timestamp_str = f"{datetime.now().year} {timestamp_str}"
                    format_str = "%Y " + self._timestamp_format
                else:
                    format_str = self._timestamp_format
                return datetime.strptime(timestamp_str.split(".")[0], format_str)
            except ValueError as e:
                logger.debug("Failed to parse timestamp: %s", e)
        return None

    def _extract_log_level(self, line: str) -> str | None:
        """Extract log level from line."""
        if not self._level_pattern:
            return None
        match = self._level_pattern.search(line)
        if match:
            return match.group(1).upper()
        return None

    def _create_log_chunk(
        self,
        lines: list[str],
        start_line: int,
        end_line: int,
        context: str,
    ) -> CodeChunk:
        """Create a log chunk from lines."""
        content = "".join(lines)
        return CodeChunk(
            language="log",
            file_path=self.file_path or "",
            node_type="log_chunk",
            start_line=start_line,
            end_line=end_line,
            byte_start=0,
            byte_end=len(content),
            parent_context=context,
            content=content,
        )

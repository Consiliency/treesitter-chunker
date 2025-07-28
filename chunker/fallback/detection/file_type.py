"""File type detection for fallback chunking."""

import logging
import mimetypes
import os
from enum import Enum
from typing import Any

import chardet

from chunker.interfaces.fallback import FallbackReason, FallbackStrategy

logger = logging.getLogger(__name__)


class FileType(Enum):
    """Detected file types."""

    TEXT = "text"
    LOG = "log"
    MARKDOWN = "markdown"
    CSV = "csv"
    JSON = "json"
    XML = "xml"
    YAML = "yaml"
    CONFIG = "config"
    BINARY = "binary"
    UNKNOWN = "unknown"


class EncodingDetector:
    """Detect file encoding."""

    @staticmethod
    def detect_encoding(file_path: str, sample_size: int = 8192) -> tuple[str, float]:
        """Detect file encoding.

        Args:
            file_path: Path to file
            sample_size: Bytes to sample for detection

        Returns:
            Tuple of (encoding, confidence)
        """
        try:
            with open(file_path, "rb") as f:
                raw_data = f.read(sample_size)

            if not raw_data:
                return "utf-8", 1.0

            # Try to detect encoding
            result = chardet.detect(raw_data)

            if result["encoding"]:
                return result["encoding"], result["confidence"]
            # Default to utf-8
            return "utf-8", 0.0

        except Exception as e:
            logger.warning(f"Error detecting encoding for {file_path}: {e}")
            return "utf-8", 0.0

    @staticmethod
    def read_with_encoding(
        file_path: str,
        encoding: str | None = None,
    ) -> tuple[str, str]:
        """Read file with proper encoding.

        Args:
            file_path: Path to file
            encoding: Encoding to use (auto-detect if None)

        Returns:
            Tuple of (content, encoding_used)
        """
        if encoding is None:
            encoding, _ = EncodingDetector.detect_encoding(file_path)

        try:
            with open(file_path, encoding=encoding) as f:
                content = f.read()
            return content, encoding
        except UnicodeDecodeError:
            # Try with error handling
            try:
                with open(file_path, encoding=encoding, errors="replace") as f:
                    content = f.read()
                logger.warning(f"Had to use error replacement for {file_path}")
                return content, encoding
            except Exception as e:
                logger.error(f"Failed to read {file_path}: {e}")
                raise


class FileTypeDetector(FallbackStrategy):
    """Detect file types and determine fallback needs."""

    def __init__(self):
        """Initialize file type detector."""
        # Common file extensions by type
        self.extension_map = {
            # Text files
            ".txt": FileType.TEXT,
            ".text": FileType.TEXT,
            # Log files
            ".log": FileType.LOG,
            ".logs": FileType.LOG,
            ".out": FileType.LOG,
            ".err": FileType.LOG,
            # Markdown
            ".md": FileType.MARKDOWN,
            ".markdown": FileType.MARKDOWN,
            ".mdown": FileType.MARKDOWN,
            ".mkd": FileType.MARKDOWN,
            # Data formats
            ".csv": FileType.CSV,
            ".tsv": FileType.CSV,
            ".json": FileType.JSON,
            ".jsonl": FileType.JSON,
            ".xml": FileType.XML,
            ".yaml": FileType.YAML,
            ".yml": FileType.YAML,
            # Config files
            ".ini": FileType.CONFIG,
            ".cfg": FileType.CONFIG,
            ".conf": FileType.CONFIG,
            ".config": FileType.CONFIG,
            ".properties": FileType.CONFIG,
            ".toml": FileType.CONFIG,
        }

        # Patterns for content-based detection
        self.content_patterns = {
            FileType.LOG: [
                r"^\d{4}-\d{2}-\d{2}",  # ISO date
                r"^\[\d{4}-\d{2}-\d{2}",  # Bracketed date
                r"^\w+ \d+ \d{2}:\d{2}:\d{2}",  # Syslog format
                r"\b(ERROR|WARN|INFO|DEBUG|TRACE)\b",  # Log levels
            ],
            FileType.MARKDOWN: [
                r"^#{1,6} ",  # Headers
                r"^\* ",  # Bullet lists
                r"^\d+\. ",  # Numbered lists
                r"\[.*\]\(.*\)",  # Links
                r"^```",  # Code blocks
            ],
        }

    def detect_file_type(self, file_path: str) -> FileType:
        """Detect file type from path and content.

        Args:
            file_path: Path to file

        Returns:
            Detected file type
        """
        # First try extension
        ext = os.path.splitext(file_path)[1].lower()
        if ext in self.extension_map:
            return self.extension_map[ext]

        # Try MIME type
        mime_type, _ = mimetypes.guess_type(file_path)
        if mime_type:
            if mime_type.startswith("text/"):
                return FileType.TEXT
            if mime_type == "application/json":
                return FileType.JSON
            if mime_type == "application/xml":
                return FileType.XML

        # Try content-based detection
        try:
            # Check if binary
            if self._is_binary(file_path):
                return FileType.BINARY

            # Read sample content
            content, _ = EncodingDetector.read_with_encoding(file_path)
            sample = content[:4096]  # First 4KB

            # Check patterns
            for file_type, patterns in self.content_patterns.items():
                for pattern in patterns:
                    import re

                    if re.search(pattern, sample, re.MULTILINE):
                        return file_type

        except Exception as e:
            logger.warning(f"Error detecting file type for {file_path}: {e}")

        return FileType.UNKNOWN

    def should_use_fallback(
        self,
        file_path: str,
        language: str | None = None,
    ) -> tuple[bool, FallbackReason]:
        """Determine if fallback should be used.

        Args:
            file_path: Path to file
            language: Language hint (if available)

        Returns:
            Tuple of (should_use_fallback, reason)
        """
        # Check if file exists
        if not os.path.exists(file_path):
            return True, FallbackReason.PARSE_FAILURE

        file_type = self.detect_file_type(file_path)

        # Binary files always need fallback (or skip)
        if file_type == FileType.BINARY:
            return True, FallbackReason.BINARY_FILE

        # Check if we have a grammar for known types
        grammar_supported = {
            FileType.JSON: True,  # tree-sitter-json exists
            FileType.YAML: True,  # tree-sitter-yaml exists
            FileType.MARKDOWN: True,  # tree-sitter-markdown exists
        }

        if file_type in grammar_supported and not language:
            # Grammar exists but not loaded
            return True, FallbackReason.NO_GRAMMAR

        # Text-based files without grammar
        if file_type in [FileType.TEXT, FileType.LOG, FileType.CSV, FileType.CONFIG]:
            return True, FallbackReason.NO_GRAMMAR

        # Unknown files
        if file_type == FileType.UNKNOWN:
            return True, FallbackReason.NO_GRAMMAR

        return False, FallbackReason.NO_GRAMMAR

    def suggest_grammar(self, file_path: str) -> str | None:
        """Suggest a grammar that could handle this file.

        Args:
            file_path: Path to file

        Returns:
            Grammar repository URL or None
        """
        file_type = self.detect_file_type(file_path)

        suggestions = {
            FileType.JSON: "https://github.com/tree-sitter/tree-sitter-json",
            FileType.YAML: "https://github.com/tree-sitter-grammars/tree-sitter-yaml",
            FileType.MARKDOWN: "https://github.com/tree-sitter-grammars/tree-sitter-markdown",
            FileType.XML: "https://github.com/tree-sitter-grammars/tree-sitter-xml",
        }

        return suggestions.get(file_type)

    def get_metadata(self, file_path: str) -> dict[str, Any]:
        """Get file metadata.

        Args:
            file_path: Path to file

        Returns:
            Metadata dictionary
        """
        metadata = {
            "file_type": self.detect_file_type(file_path).value,
            "size": 0,
            "encoding": "unknown",
            "mime_type": None,
        }

        try:
            stat = os.stat(file_path)
            metadata["size"] = stat.st_size
            metadata["modified"] = stat.st_mtime

            encoding, confidence = EncodingDetector.detect_encoding(file_path)
            metadata["encoding"] = encoding
            metadata["encoding_confidence"] = confidence

            mime_type, _ = mimetypes.guess_type(file_path)
            metadata["mime_type"] = mime_type

        except Exception as e:
            logger.warning(f"Error getting metadata for {file_path}: {e}")

        return metadata

    def _is_binary(self, file_path: str, sample_size: int = 8192) -> bool:
        """Check if file is binary.

        Args:
            file_path: Path to file
            sample_size: Bytes to check

        Returns:
            True if file appears to be binary
        """
        try:
            with open(file_path, "rb") as f:
                chunk = f.read(sample_size)

            if not chunk:
                return False

            # Check for null bytes (common in binary files)
            if b"\x00" in chunk:
                return True

            # Check if mostly printable
            text_chars = bytearray({7, 8, 9, 10, 12, 13, 27} | set(range(0x20, 0x100)))
            non_text = sum(1 for byte in chunk if byte not in text_chars)

            # If more than 30% non-text, consider binary
            return non_text / len(chunk) > 0.3

        except Exception:
            return True

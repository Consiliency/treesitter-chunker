"""File type detection for fallback chunking."""

import logging
import mimetypes
from enum import Enum
from pathlib import Path
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
            with Path(file_path).open("rb") as f:
                raw_data = f.read(sample_size)
            if not raw_data:
                return "utf-8", 1.0
            result = chardet.detect(raw_data)
            if result["encoding"]:
                return result["encoding"], result["confidence"]
            return "utf-8", 0.0
        except (OSError, FileNotFoundError, IndexError) as e:
            logger.warning("Error detecting encoding for %s: %s", file_path, e)
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
            with Path(file_path).open(encoding=encoding) as f:
                content = f.read()
            return content, encoding
        except UnicodeDecodeError:
            try:
                with Path(file_path).open(
                    encoding=encoding,
                    errors="replace",
                ) as f:
                    content = f.read()
                logger.warning(
                    "Had to use error replacement for %s",
                    file_path,
                )
                return content, encoding
            except (FileNotFoundError, OSError) as e:
                logger.error("Failed to read %s: %s", file_path, e)
                raise


class FileTypeDetector(FallbackStrategy):
    """Detect file types and determine fallback needs."""

    def __init__(self):
        """Initialize file type detector."""
        self.extension_map = {
            ".txt": FileType.TEXT,
            ".text": FileType.TEXT,
            ".log": FileType.LOG,
            ".logs": FileType.LOG,
            ".out": FileType.LOG,
            ".err": FileType.LOG,
            ".md": FileType.MARKDOWN,
            ".markdown": FileType.MARKDOWN,
            ".mdown": FileType.MARKDOWN,
            ".mkd": FileType.MARKDOWN,
            ".csv": FileType.CSV,
            ".tsv": FileType.CSV,
            ".json": FileType.JSON,
            ".jsonl": FileType.JSON,
            ".xml": FileType.XML,
            ".yaml": FileType.YAML,
            ".yml": FileType.YAML,
            ".ini": FileType.CONFIG,
            ".cfg": FileType.CONFIG,
            ".conf": FileType.CONFIG,
            ".config": FileType.CONFIG,
            ".properties": FileType.CONFIG,
            ".toml": FileType.CONFIG,
        }
        self.content_patterns = {
            FileType.LOG: [
                "^\\d{4}-\\d{2}-\\d{2}",
                "^\\[\\d{4}-\\d{2}-\\d{2}",
                "^\\w+ \\d+ \\d{2}:\\d{2}:\\d{2}",
                "\\b(ERROR|WARN|INFO|DEBUG|TRACE)\\b",
            ],
            FileType.MARKDOWN: [
                "^#{1,6} ",
                "^\\* ",
                "^\\d+\\. ",
                "\\[.*\\]\\(.*\\)",
                "^```",
            ],
        }

    def detect_file_type(self, file_path: str) -> FileType:
        """Detect file type from path and content.

        Args:
            file_path: Path to file

        Returns:
            Detected file type
        """
        # List of detection methods in priority order
        detection_methods = [
            self._detect_by_extension,
            self._detect_by_mime_type,
            self._detect_by_content,
        ]

        # Try each detection method
        for method in detection_methods:
            result = method(file_path)
            if result != FileType.UNKNOWN:
                return result

        return FileType.UNKNOWN

    def _detect_by_extension(self, file_path: str) -> FileType:
        """Detect file type by extension."""
        ext = Path(file_path).suffix.lower()
        return self.extension_map.get(ext, FileType.UNKNOWN)

    @staticmethod
    def _detect_by_mime_type(file_path: str) -> FileType:
        """Detect file type by MIME type."""
        mime_type, _ = mimetypes.guess_type(file_path)
        if not mime_type:
            return FileType.UNKNOWN

        # Map MIME types to FileType
        mime_map = {
            "text/": FileType.TEXT,  # prefix match
            "application/json": FileType.JSON,
            "application/xml": FileType.XML,
        }

        for mime_pattern, file_type in mime_map.items():
            if mime_pattern.endswith("/"):
                if mime_type.startswith(mime_pattern):
                    return file_type
            elif mime_type == mime_pattern:
                return file_type

        return FileType.UNKNOWN

    def _detect_by_content(self, file_path: str) -> FileType:
        """Detect file type by content analysis."""
        try:
            if self._is_binary(file_path):
                return FileType.BINARY

            content, _ = EncodingDetector.read_with_encoding(file_path)
            sample = content[:4096]

            # Check content patterns
            import re

            for file_type, patterns in self.content_patterns.items():
                for pattern in patterns:
                    if re.search(pattern, sample, re.MULTILINE):
                        return file_type
        except (FileNotFoundError, ImportError, IndexError) as e:
            logger.warning(
                "Error detecting file type for %s: %s",
                file_path,
                e,
            )

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
        if not Path(file_path).exists():
            return True, FallbackReason.PARSE_FAILURE
        file_type = self.detect_file_type(file_path)
        if file_type == FileType.BINARY:
            return True, FallbackReason.BINARY_FILE
        grammar_supported = {
            FileType.JSON: True,
            FileType.YAML: True,
            FileType.MARKDOWN: True,
        }
        if file_type in grammar_supported and not language:
            return True, FallbackReason.NO_GRAMMAR
        if file_type in {FileType.TEXT, FileType.LOG, FileType.CSV, FileType.CONFIG}:
            return True, FallbackReason.NO_GRAMMAR
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
            stat = Path(file_path).stat()
            metadata["size"] = stat.st_size
            metadata["modified"] = stat.st_mtime
            encoding, confidence = EncodingDetector.detect_encoding(file_path)
            metadata["encoding"] = encoding
            metadata["encoding_confidence"] = confidence
            mime_type, _ = mimetypes.guess_type(file_path)
            metadata["mime_type"] = mime_type
        except (FileNotFoundError, IndexError, KeyError) as e:
            logger.warning("Error getting metadata for %s: %s", file_path, e)
        return metadata

    @classmethod
    def _is_binary(cls, file_path: str, sample_size: int = 8192) -> bool:
        """Check if file is binary.

        Args:
            file_path: Path to file
            sample_size: Bytes to check

        Returns:
            True if file appears to be binary
        """
        try:
            with Path(file_path).open("rb") as f:
                chunk = f.read(sample_size)
            if not chunk:
                return False
            if b"\x00" in chunk:
                return True
            text_chars = bytearray({7, 8, 9, 10, 12, 13, 27} | set(range(32, 256)))
            non_text = sum(1 for byte in chunk if byte not in text_chars)
            return non_text / len(chunk) > 0.3
        except (RuntimeError, ValueError):
            return True

"""Manager for fallback chunking strategies."""
import logging
import warnings

from chunker.interfaces.fallback import FallbackReason
from chunker.types import CodeChunk

from .base import FallbackChunker, FallbackWarning
from .detection.file_type import EncodingDetector, FileType, FileTypeDetector
from .strategies.line_based import LineBasedChunker
from .strategies.log_chunker import LogChunker
from .strategies.markdown import MarkdownChunker

logger = logging.getLogger(__name__)


class FallbackManager:
    """Manages fallback chunking strategies.

    This class coordinates between file type detection and appropriate
    fallback chunking strategies.
    """

    def __init__(self):
        """Initialize fallback manager."""
        self.detector = FileTypeDetector()
        self.chunker_map: dict[FileType, type[FallbackChunker]] = {FileType
            .LOG: LogChunker, FileType.MARKDOWN: MarkdownChunker, FileType.
            TEXT: LineBasedChunker, FileType.CSV: LineBasedChunker,
            FileType.CONFIG: LineBasedChunker, FileType.JSON:
            LineBasedChunker, FileType.XML: LineBasedChunker, FileType.YAML:
            LineBasedChunker}
        self._chunker_cache: dict[FileType, FallbackChunker] = {}

    def can_chunk(self, file_path: str) -> bool:
        """Check if file can be chunked with fallback.

        Args:
            file_path: Path to file

        Returns:
            True if file can be chunked
        """
        file_type = self.detector.detect_file_type(file_path)
        return file_type not in {FileType.BINARY, FileType.UNKNOWN}

    def chunk_file(self, file_path: str, reason: (FallbackReason | None) = None,
        ) -> list[CodeChunk]:
        """Chunk a file using appropriate fallback strategy.

        Args:
            file_path: Path to file
            reason: Reason for using fallback (auto-detected if None)

        Returns:
            List of chunks

        Raises:
            ValueError: If file cannot be chunked
        """
        file_type = self.detector.detect_file_type(file_path)
        if file_type == FileType.BINARY:
            raise ValueError(f"Cannot chunk binary file: {file_path}")
        if file_type == FileType.UNKNOWN:
            logger.warning("Unknown file type, using line-based chunking: %s",
                file_path)
            file_type = FileType.TEXT
        chunker = self._get_chunker(file_type)
        if reason is None:
            _, reason = self.detector.should_use_fallback(file_path)
        chunker.set_fallback_reason(reason)
        warnings.warn(
            f"Using fallback chunking for {file_path} (type: {file_type.value}, reason: {reason})"
            , FallbackWarning, stacklevel=2)
        try:
            content, _encoding = EncodingDetector.read_with_encoding(file_path)
        except (FileNotFoundError, OSError) as e:
            logger.error("Failed to read file %s: %s", file_path, e)
            raise
        if file_type == FileType.LOG:
            chunks = chunker.chunk_by_timestamp(content, 300)
            if not chunks:
                chunks = chunker.chunk_by_severity(content)
            if not chunks:
                chunks = chunker.chunk_by_lines(content, 100, 10)
        elif file_type == FileType.MARKDOWN:
            chunks = chunker.chunk_by_headers(content, max_level=3)
            if not chunks:
                chunks = chunker.chunk_by_sections(content)
        elif file_type == FileType.CSV:
            chunks = chunker.chunk_csv(content, include_header=True)
        else:
            chunks = chunker.adaptive_chunk(content)
        for chunk in chunks:
            if not chunk.file_path:
                chunk.file_path = file_path
        logger.info("Created %s chunks for %s using %s strategy", (len(
            chunks), file_path, file_type.value))
        return chunks

    def _get_chunker(self, file_type: FileType) -> FallbackChunker:
        """Get or create chunker for file type.

        Args:
            file_type: Type of file

        Returns:
            Appropriate chunker instance
        """
        if file_type not in self._chunker_cache:
            chunker_class = self.chunker_map.get(file_type, LineBasedChunker)
            self._chunker_cache[file_type] = chunker_class()
        return self._chunker_cache[file_type]

    def get_supported_extensions(self) -> list[str]:
        """Get list of file extensions that can be chunked.

        Returns:
            List of extensions (with dots)
        """
        return list(self.detector.extension_map.keys())

    def get_fallback_info(self, file_path: str) -> dict[str, any]:
        """Get information about fallback handling for a file.

        Args:
            file_path: Path to file

        Returns:
            Dictionary with fallback information
        """
        file_type = self.detector.detect_file_type(file_path)
        should_fallback, reason = self.detector.should_use_fallback(file_path)
        metadata = self.detector.get_metadata(file_path)
        return {"file_type": file_type.value, "can_chunk": self.can_chunk(
            file_path), "should_use_fallback": should_fallback,
            "fallback_reason": reason.value if reason else None,
            "suggested_grammar": self.detector.suggest_grammar(file_path),
            "metadata": metadata}

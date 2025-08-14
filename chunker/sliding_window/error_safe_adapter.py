"""Error-safe adapter for SlidingWindowFallback with enhanced exception handling.

This adapter wraps the sliding window fallback system to provide comprehensive
error handling that catches all processor exceptions and gracefully falls back
to alternative processors or default text chunking.
"""

import logging
from pathlib import Path
from typing import Any

from chunker.chunker_config import ChunkerConfig
from chunker.fallback.sliding_window_fallback import SlidingWindowFallback
from chunker.types import CodeChunk

logger = logging.getLogger(__name__)


class ErrorSafeSlidingWindowFallback(SlidingWindowFallback):
    """Error-safe wrapper for SlidingWindowFallback with comprehensive exception handling.

    This adapter extends the base SlidingWindowFallback to catch all possible
    processor exceptions, not just the limited set handled by the base class.
    When a processor fails, it gracefully falls back to the next available
    processor or default text chunking.
    """

    def chunk_text(
        self,
        content: str,
        file_path: str | Path,
        language: str | None = None,
    ) -> list[CodeChunk]:
        """Chunk content using appropriate processor with comprehensive error handling.

        Args:
            content: Content to chunk
            file_path: Path to the file
            language: Language hint (if available)

        Returns:
            List of chunks
        """
        file_type = self.detector.detect_file_type(file_path)
        processor_names = self.registry.find_processors(str(file_path), file_type)

        for proc_name in processor_names:
            processor = self.registry.get_processor(proc_name)
            path_str = str(file_path)

            if processor and processor.can_process(content, path_str):
                logger.info("Using processor '%s' for %s", proc_name, file_path)

                try:
                    chunks = processor.process(content, path_str)

                    # Add processor metadata to chunks
                    for chunk in chunks:
                        if not hasattr(chunk, "metadata"):
                            chunk.metadata = {}
                        chunk.metadata["processor"] = proc_name
                        chunk.metadata["processor_type"] = self.registry._processors[
                            proc_name
                        ].processor_type.value

                    return chunks

                except Exception as e:
                    # Catch ALL exceptions, not just the limited set in base class
                    logger.error("Processor '%s' failed with error: %s", proc_name, e)
                    logger.debug("Exception details", exc_info=True)
                    # Continue to try next processor
                    continue

        # If no processors worked, fall back to base line-based chunking
        logger.warning(
            "No suitable processor found for %s, using line-based chunking",
            file_path,
        )
        # Call the base FallbackChunker.chunk_text directly to avoid
        # the SlidingWindowFallback's processor selection logic
        from chunker.fallback.base import FallbackChunker

        return FallbackChunker.chunk_text(self, content, file_path, language)

    def register_custom_processor(
        self,
        name: str,
        processor_class: type,
        supported_file_types: set,
        supported_extensions: set,
        priority: int = 50,
    ) -> None:
        """Register a custom processor with error-safe wrapper.

        Args:
            name: Processor name
            processor_class: Processor class
            supported_file_types: File types this processor supports
            supported_extensions: File extensions this processor supports
            priority: Priority level (higher = more priority)
        """
        # Delegate to parent implementation
        super().register_custom_processor(
            name,
            processor_class,
            supported_file_types,
            supported_extensions,
            priority,
        )

    def disable_processor(self, name: str) -> None:
        """Disable a processor with error handling.

        Args:
            name: Name of processor to disable
        """
        try:
            super().disable_processor(name)
        except Exception as e:
            logger.error("Failed to disable processor '%s': %s", name, e)

    def enable_processor(self, name: str) -> None:
        """Enable a processor with error handling.

        Args:
            name: Name of processor to enable
        """
        try:
            super().enable_processor(name)
        except Exception as e:
            logger.error("Failed to enable processor '%s': %s", name, e)

    def get_processor_info(self, file_path: str) -> dict[str, Any]:
        """Get processor information with error handling.

        Args:
            file_path: Path to the file

        Returns:
            Dictionary with processor selection information
        """
        try:
            return super().get_processor_info(file_path)
        except Exception as e:
            logger.error("Failed to get processor info for '%s': %s", file_path, e)
            return {
                "file_type": "unknown",
                "processors": [],
                "available_processors": [],
                "error": str(e),
            }

    def create_processor_chain(self, processor_names: list[str]):
        """Create processor chain with error handling.

        Args:
            processor_names: List of processor names

        Returns:
            Processor chain or None if creation fails
        """
        try:
            return super().create_processor_chain(processor_names)
        except Exception as e:
            logger.error("Failed to create processor chain: %s", e)
            return None

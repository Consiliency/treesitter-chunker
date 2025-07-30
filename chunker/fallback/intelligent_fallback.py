"""Intelligent fallback strategy that makes smart decisions about chunking methods.

This module implements an intelligent fallback system that automatically chooses
between tree-sitter and sliding window chunking based on:
- File type and language support
- Token limits and chunk sizes
- Parse failures or errors
- Content characteristics
"""

import logging
from enum import Enum
from pathlib import Path
from typing import Any

from chunker.chunker import chunk_text, chunk_text_with_token_limit
from chunker.interfaces.fallback import FallbackReason
from chunker.parser import list_languages
from chunker.token.counter import TiktokenCounter
from chunker.types import CodeChunk

from .base import FallbackChunker
from .detection.file_type import FileType, FileTypeDetector
from .sliding_window_fallback import SlidingWindowFallback

logger = logging.getLogger(__name__)


class ChunkingDecision(Enum):
    """Decision about which chunking method to use."""

    TREE_SITTER = "tree_sitter"
    TREE_SITTER_WITH_SPLIT = "tree_sitter_with_split"
    SLIDING_WINDOW = "sliding_window"
    SPECIALIZED_PROCESSOR = "specialized_processor"


class DecisionMetrics:
    """Metrics used to make chunking decisions."""

    def __init__(self):
        self.has_tree_sitter_support = False
        self.parse_success = False
        self.largest_chunk_tokens = 0
        self.average_chunk_tokens = 0
        self.total_tokens = 0
        self.file_type = FileType.UNKNOWN
        self.is_code_file = False
        self.has_specialized_processor = False
        self.specialized_processor_name = None
        self.token_limit_exceeded = False
        self.parse_error = None
        self.detected_language = None


class IntelligentFallbackChunker(FallbackChunker):
    """Intelligent fallback that makes smart decisions about chunking methods."""

    def __init__(
        self,
        token_limit: int | None = None,
        model: str = "gpt-4",
        sliding_window_config: dict[str, Any] | None = None,
    ):
        """Initialize intelligent fallback chunker.

        Args:
            token_limit: Maximum tokens per chunk (None for no limit)
            model: Tokenizer model to use
            sliding_window_config: Configuration for sliding window fallback
        """
        super().__init__()
        self.token_limit = token_limit
        self.model = model
        self.token_counter = TiktokenCounter()
        self.file_detector = FileTypeDetector()
        self.sliding_window = SlidingWindowFallback(config=sliding_window_config)

        # Cache supported languages
        self._supported_languages = set(list_languages())

        # Language mapping for common file extensions
        self.extension_to_language = {
            ".py": "python",
            ".js": "javascript",
            ".jsx": "javascript",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".java": "java",
            ".c": "c",
            ".cpp": "cpp",
            ".cc": "cpp",
            ".cxx": "cpp",
            ".h": "c",
            ".hpp": "cpp",
            ".rs": "rust",
            ".go": "go",
            ".rb": "ruby",
            ".php": "php",
            ".cs": "csharp",
            ".swift": "swift",
            ".kt": "kotlin",
            ".scala": "scala",
            ".r": "r",
            ".m": "objc",
            ".mm": "objcpp",
            ".lua": "lua",
            ".jl": "julia",
            ".ml": "ocaml",
            ".ex": "elixir",
            ".clj": "clojure",
            ".hs": "haskell",
            ".pl": "perl",
            ".sh": "bash",
            ".vim": "vim",
            ".el": "elisp",
        }

    def _detect_language(self, file_path: str, content: str) -> str | None:
        """Detect programming language from file path and content.

        Args:
            file_path: Path to the file
            content: File content

        Returns:
            Language identifier or None
        """
        # Try extension-based detection first
        ext = Path(file_path).suffix.lower()
        if ext in self.extension_to_language:
            lang = self.extension_to_language[ext]
            if lang in self._supported_languages:
                return lang

        # Try shebang detection for scripts
        if content.startswith("#!"):
            first_line = content.split("\n")[0]
            if "python" in first_line:
                return "python" if "python" in self._supported_languages else None
            if "node" in first_line or "javascript" in first_line:
                return (
                    "javascript" if "javascript" in self._supported_languages else None
                )
            if "bash" in first_line or "/sh" in first_line:
                return "bash" if "bash" in self._supported_languages else None
            if "ruby" in first_line:
                return "ruby" if "ruby" in self._supported_languages else None

        return None

    def _analyze_content(
        self,
        content: str,
        file_path: str,
        language: str | None,
    ) -> DecisionMetrics:
        """Analyze content to gather decision metrics.

        Args:
            content: File content
            file_path: Path to the file
            language: Language hint

        Returns:
            Decision metrics
        """
        metrics = DecisionMetrics()

        # Detect file type
        metrics.file_type = self.file_detector.detect_file_type(file_path)
        # Determine if it's a code file based on extension
        ext = Path(file_path).suffix.lower()
        code_extensions = {
            ".py",
            ".js",
            ".jsx",
            ".ts",
            ".tsx",
            ".java",
            ".c",
            ".cpp",
            ".cc",
            ".h",
            ".hpp",
            ".cs",
            ".go",
            ".rs",
            ".rb",
            ".php",
            ".swift",
            ".kt",
            ".scala",
            ".r",
            ".m",
            ".lua",
            ".jl",
        }
        metrics.is_code_file = ext in code_extensions

        # Check for specialized processor
        processor_info = self.sliding_window.get_processor_info(file_path)
        available_processors = processor_info.get("available_processors", [])
        if available_processors:
            # Check if any non-generic processor is available
            for proc_name in available_processors:
                if "generic" not in proc_name:
                    metrics.has_specialized_processor = True
                    metrics.specialized_processor_name = proc_name
                    break

        # Detect language if not provided
        if not language:
            language = self._detect_language(file_path, content)

        # Store detected language
        metrics.detected_language = language

        # Check tree-sitter support
        if language and language in self._supported_languages:
            metrics.has_tree_sitter_support = True

            # Try parsing with tree-sitter
            try:
                chunks = chunk_text(content, language, file_path)
                metrics.parse_success = True

                # Check if we got any chunks
                if not chunks:
                    # Tree-sitter parsed but produced no chunks
                    # This happens with simple scripts that have no functions/classes
                    metrics.parse_success = False
                    metrics.parse_error = "No chunks produced"

                # Analyze chunk sizes
                elif chunks:
                    token_counts = []
                    for chunk in chunks:
                        token_count = self.token_counter.count_tokens(
                            chunk.content,
                            self.model,
                        )
                        token_counts.append(token_count)

                    metrics.largest_chunk_tokens = max(token_counts)
                    metrics.average_chunk_tokens = sum(token_counts) / len(token_counts)
                    metrics.total_tokens = sum(token_counts)

                    # Check if any chunk exceeds limit
                    if (
                        self.token_limit
                        and metrics.largest_chunk_tokens > self.token_limit
                    ):
                        metrics.token_limit_exceeded = True

            except (FileNotFoundError, OSError, SyntaxError) as e:
                metrics.parse_success = False
                metrics.parse_error = str(e)
                logger.debug("Tree-sitter parse failed for %s: %s", file_path, e)

        # Count total tokens in content
        if not metrics.total_tokens:
            metrics.total_tokens = self.token_counter.count_tokens(content, self.model)

        return metrics

    def _make_decision(self, metrics: DecisionMetrics) -> tuple[ChunkingDecision, str]:
        """Make chunking decision based on metrics.

        Args:
            metrics: Analysis metrics

        Returns:
            Tuple of (decision, reason)
        """
        # Priority 1: Use specialized processor for non-code files
        if metrics.has_specialized_processor and not metrics.is_code_file:
            return (
                ChunkingDecision.SPECIALIZED_PROCESSOR,
                f"Using specialized processor: {metrics.specialized_processor_name}",
            )

        # Priority 2: Use tree-sitter for supported code files
        if metrics.has_tree_sitter_support and metrics.parse_success:
            if self.token_limit and metrics.token_limit_exceeded:
                return (
                    ChunkingDecision.TREE_SITTER_WITH_SPLIT,
                    f"Tree-sitter with splitting (largest chunk: {metrics.largest_chunk_tokens} tokens)",
                )
            return (
                ChunkingDecision.TREE_SITTER,
                "Tree-sitter parsing successful",
            )

        # Priority 3: Use sliding window for everything else
        reasons = []
        if not metrics.has_tree_sitter_support:
            reasons.append("no tree-sitter support")
        elif not metrics.parse_success:
            reasons.append(f"parse failed: {metrics.parse_error}")

        if metrics.has_specialized_processor:
            reasons.append(
                f"specialized processor available: {metrics.specialized_processor_name}",
            )

        return (
            ChunkingDecision.SLIDING_WINDOW,
            "Using sliding window: " + ", ".join(reasons),
        )

    def chunk_text(
        self,
        content: str,
        file_path: str,
        language: str | None = None,
    ) -> list[CodeChunk]:
        """Intelligently chunk content using the best available method.

        Args:
            content: Content to chunk
            file_path: Path to the file
            language: Language hint

        Returns:
            List of chunks
        """
        # Analyze content
        metrics = self._analyze_content(content, file_path, language)

        # Use detected language if none provided
        if not language and metrics.detected_language:
            language = metrics.detected_language

        # Make decision
        decision, reason = self._make_decision(metrics)

        logger.info("Chunking decision for %s: %s - %s", file_path, decision.value, reason)

        # Execute decision
        chunks = []

        if decision == ChunkingDecision.TREE_SITTER:
            # Use regular tree-sitter chunking
            # Ensure we have a valid language
            lang_to_use = language
            if not lang_to_use:
                lang_to_use = self._detect_language(file_path, content)
            if not lang_to_use:
                logger.error("No language detected for %s", file_path)
                # Fall back to sliding window
                return self.sliding_window.chunk_text(content, file_path, language)
            chunks = chunk_text(content, lang_to_use, file_path)

        elif decision == ChunkingDecision.TREE_SITTER_WITH_SPLIT:
            # Use tree-sitter with token limit
            # Ensure we have a valid language
            lang_to_use = language
            if not lang_to_use:
                lang_to_use = self._detect_language(file_path, content)
            if not lang_to_use:
                logger.error("No language detected for %s", file_path)
                # Fall back to sliding window
                return self.sliding_window.chunk_text(content, file_path, language)
            chunks = chunk_text_with_token_limit(
                content,
                lang_to_use,
                self.token_limit,
                file_path,
                self.model,
            )

        elif decision in [
            ChunkingDecision.SLIDING_WINDOW,
            ChunkingDecision.SPECIALIZED_PROCESSOR,
        ]:
            # Use sliding window fallback (which includes specialized processors)
            chunks = self.sliding_window.chunk_text(content, file_path, language)

        # Add decision metadata to chunks
        for chunk in chunks:
            if not hasattr(chunk, "metadata"):
                chunk.metadata = {}
            chunk.metadata["chunking_decision"] = decision.value
            chunk.metadata["chunking_reason"] = reason

            # Add token count if not already present
            if "token_count" not in chunk.metadata and self.token_limit:
                chunk.metadata["token_count"] = self.token_counter.count_tokens(
                    chunk.content,
                    self.model,
                )
                chunk.metadata["tokenizer_model"] = self.model

        return chunks

    def can_handle(self, _file_path: str, _language: str) -> bool:
        """Check if this fallback can handle the file.

        Args:
            file_path: Path to the file
            language: Language identifier

        Returns:
            True (intelligent fallback can handle any file)
        """
        return True

    def get_fallback_reason(self, file_path: str, language: str) -> FallbackReason:
        """Get the reason for using fallback.

        Args:
            file_path: Path to the file
            language: Language identifier

        Returns:
            Fallback reason
        """
        # Try to detect why fallback would be needed
        if language and language not in self._supported_languages:
            return FallbackReason.NO_GRAMMAR

        # Check file type
        file_type = self.file_detector.detect_file_type(file_path)
        if file_type == FileType.BINARY:
            return FallbackReason.BINARY_FILE

        # Default reason - no grammar available
        return FallbackReason.NO_GRAMMAR

    def get_decision_info(
        self,
        file_path: str,
        content: str,
        language: str | None = None,
    ) -> dict[str, Any]:
        """Get detailed information about the chunking decision.

        Args:
            file_path: Path to the file
            content: File content
            language: Language hint

        Returns:
            Dictionary with decision details
        """
        metrics = self._analyze_content(content, file_path, language)
        decision, reason = self._make_decision(metrics)

        return {
            "decision": decision.value,
            "reason": reason,
            "metrics": {
                "has_tree_sitter_support": metrics.has_tree_sitter_support,
                "parse_success": metrics.parse_success,
                "largest_chunk_tokens": metrics.largest_chunk_tokens,
                "average_chunk_tokens": metrics.average_chunk_tokens,
                "total_tokens": metrics.total_tokens,
                "file_type": metrics.file_type.value,
                "is_code_file": metrics.is_code_file,
                "has_specialized_processor": metrics.has_specialized_processor,
                "specialized_processor_name": metrics.specialized_processor_name,
                "token_limit_exceeded": metrics.token_limit_exceeded,
                "parse_error": metrics.parse_error,
            },
            "token_limit": self.token_limit,
            "model": self.model,
        }

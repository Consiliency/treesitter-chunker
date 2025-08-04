"""Zero-configuration API for automatic language setup and chunking.

This module provides a simple, zero-config interface for chunking code files
with automatic language detection and grammar management.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .chunker import chunk_file_with_token_limit, chunk_text_with_token_limit

from .contracts.auto_contract import AutoChunkResult, ZeroConfigContract
from .core import chunk_file, chunk_text
from .exceptions import ChunkerError
from .fallback.sliding_window_fallback import SlidingWindowFallback

if TYPE_CHECKING:
    from .contracts.registry_contract import UniversalRegistryContract


class ZeroConfigAPI(ZeroConfigContract):
    """Zero-configuration API for automatic chunking.

    This class provides a simple interface that automatically:
    - Detects languages from file extensions and content
    - Downloads and sets up grammars as needed
    - Falls back to text chunking when tree-sitter is unavailable
    """
    EXTENSION_MAP = {".py": "python", ".js": "javascript", ".jsx":
        "javascript", ".ts": "typescript", ".tsx": "typescript", ".java":
        "java", ".c": "c", ".h": "c", ".cc": "cpp", ".cpp": "cpp", ".cxx":
        "cpp", ".hpp": "cpp", ".rs": "rust", ".go": "go", ".rb": "ruby",
        ".php": "php", ".cs": "csharp", ".swift": "swift", ".kt": "kotlin",
        ".scala": "scala", ".r": "r", ".lua": "lua", ".jl": "julia", ".sh":
        "bash", ".bash": "bash", ".zsh": "bash", ".ps1": "powershell",
        ".yaml": "yaml", ".yml": "yaml", ".json": "json", ".xml": "xml",
        ".html": "html", ".css": "css", ".scss": "css", ".sql": "sql",
        ".md": "markdown", ".rst": "restructuredtext", ".tex": "latex",
        ".vim": "vim", ".el": "elisp", ".clj": "clojure", ".ex": "elixir",
        ".exs": "elixir", ".erl": "erlang", ".hrl": "erlang", ".fs":
        "fsharp", ".fsx": "fsharp", ".ml": "ocaml", ".mli": "ocaml", ".pl":
        "perl", ".pm": "perl", ".raku": "raku", ".dart": "dart", ".zig":
        "zig", ".nim": "nim", ".v": "verilog", ".vhdl": "vhdl", ".m":
        "matlab", ".f90": "fortran", ".f95": "fortran", ".cob": "cobol",
        ".pas": "pascal", ".asm": "assembly", ".s": "assembly"}
    SHEBANG_PATTERNS = {"python[0-9.]*": "python", "ruby": "ruby",
        "node|nodejs": "javascript", "perl": "perl", "bash|sh": "bash",
        "zsh": "bash", "fish": "bash", "php": "php", "lua": "lua", "julia":
        "julia", "Rscript": "r"}

    def __init__(self, registry: UniversalRegistryContract):
        """Initialize the zero-config API.

        Args:
            registry: Universal language registry instance
        """
        self.registry = registry
        self._fallback_chunker = SlidingWindowFallback()

    def ensure_language(self, language: str, version: (str | None) = None,
        ) -> bool:
        """Ensure a language is available for use.

        Args:
            language: Language name
            version: Specific version required

        Returns:
            True if language is ready to use
        """
        if self.registry.is_language_installed(language):
            if version:
                installed_version = self.registry.get_language_version(language,
                    )
                if installed_version == version:
                    return True
                success, _ = self.registry.update_language(language)
                return success
            return True
        available = self.registry.list_available_languages()
        if language not in available:
            return False
        return self.registry.install_language(language, version)

    def auto_chunk_file(self, file_path: (str | Path), language: (str |
        None) = None, token_limit: (int | None) = None) -> AutoChunkResult:
        """Automatically chunk a file with zero configuration.

        Args:
            file_path: Path to file
            language: Override language detection
            token_limit: Optional token limit per chunk

        Returns:
            Chunking result with metadata
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise ValueError(f"File not found: {file_path}")
        if not language:
            detected = self.detect_language(file_path)
            if not detected:
                content = file_path.read_text(encoding="utf-8")
                code_chunks = self._fallback_chunker.chunk_text(content,
                    str(file_path))
                chunks = []
                for chunk in code_chunks:
                    chunk_dict = {"content": chunk.content, "type": chunk.
                        node_type, "start_line": chunk.start_line,
                        "end_line": chunk.end_line}
                    if hasattr(chunk, "metadata") and chunk.metadata:
                        chunk_dict["metadata"] = chunk.metadata
                    chunks.append(chunk_dict)
                return AutoChunkResult(chunks=chunks, language="unknown",
                    grammar_downloaded=False, fallback_used=True, metadata={"file_path": str(file_path)})
            language = detected
        grammar_downloaded = False
        if not self.registry.is_language_installed(language):
            grammar_downloaded = self.ensure_language(language)
        try:
            if self.registry.is_language_installed(language):
                if token_limit:
                    chunks = chunk_file_with_token_limit(file_path,
                        language, max_tokens=token_limit)
                else:
                    chunks = chunk_file(file_path, language)
                chunk_dicts = []
                for chunk in chunks:
                    chunk_dict = {"content": chunk.content, "type": chunk.
                        node_type, "start_line": chunk.start_line,
                        "end_line": chunk.end_line}
                    if hasattr(chunk, "metadata") and chunk.metadata:
                        chunk_dict["metadata"] = chunk.metadata
                    chunk_dicts.append(chunk_dict)
                return AutoChunkResult(chunks=chunk_dicts, language=language, grammar_downloaded=grammar_downloaded,
                    fallback_used=False, metadata={"file_path": str(
                    file_path), "tree_sitter_version": "0.20.0"})
        except (OSError, FileNotFoundError, IndexError):
            pass
        content = file_path.read_text(encoding="utf-8")
        code_chunks = self._fallback_chunker.chunk_text(content, str(file_path),
            )
        chunks = []
        for chunk in code_chunks:
            chunk_dict = {"content": chunk.content, "type": chunk.node_type,
                "start_line": chunk.start_line, "end_line": chunk.end_line}
            if hasattr(chunk, "metadata") and chunk.metadata:
                chunk_dict["metadata"] = chunk.metadata
            chunks.append(chunk_dict)
        return AutoChunkResult(chunks=chunks, language=language,
            grammar_downloaded=grammar_downloaded, fallback_used=True,
            metadata={"file_path": str(file_path), "fallback_reason":
            "tree_sitter_failed"})

    def detect_language(self, file_path: (str | Path)) -> (str | None):
        """Detect the language of a file.

        Args:
            file_path: Path to file

        Returns:
            Detected language name or None
        """
        file_path = Path(file_path)
        suffix = file_path.suffix.lower()
        if suffix in self.EXTENSION_MAP:
            return self.EXTENSION_MAP[suffix]
        try:
            with Path(file_path).open("rb") as f:
                first_line = f.readline()
                if first_line.startswith(b"#!"):
                    shebang = first_line.decode("utf-8", errors="ignore",
                        ).strip()
                    for pattern, lang in self.SHEBANG_PATTERNS.items():
                        if re.search(pattern, shebang):
                            return lang
        except (FileNotFoundError, OSError):
            pass
        if file_path.name == "Makefile":
            return "makefile"
        if file_path.name == "Dockerfile":
            return "dockerfile"
        if file_path.name == "CMakeLists.txt":
            return "cmake"
        if file_path.name.endswith(".gemspec"):
            return "ruby"
        if file_path.name == "Cargo.toml":
            return "toml"
        if file_path.name == "package.json":
            return "json"
        return None

    def chunk_text(self, text: str, language: str, token_limit: (int | None
        ) = None) -> AutoChunkResult:
        """Chunk text content with automatic setup.

        Args:
            text: Text content to chunk
            language: Language of the text
            token_limit: Optional token limit

        Returns:
            Chunking result
        """
        if not text:
            raise ValueError("Text cannot be empty")
        if not language:
            raise ValueError("Language must be specified for text chunking")
        grammar_downloaded = False
        if not self.registry.is_language_installed(language):
            grammar_downloaded = self.ensure_language(language)
        try:
            if self.registry.is_language_installed(language):
                if token_limit:
                    chunks = chunk_text_with_token_limit(text, language,
                        max_tokens=token_limit)
                else:
                    chunks = chunk_text(text, language)
                chunk_dicts = []
                for chunk in chunks:
                    chunk_dict = {"content": chunk.content, "type": chunk.
                        node_type, "start_line": chunk.start_line,
                        "end_line": chunk.end_line}
                    if hasattr(chunk, "metadata") and chunk.metadata:
                        chunk_dict["metadata"] = chunk.metadata
                    chunk_dicts.append(chunk_dict)
                return AutoChunkResult(chunks=chunk_dicts, language=language, grammar_downloaded=grammar_downloaded,
                    fallback_used=False, metadata={"tree_sitter_version":
                    "0.20.0"})
        except (IndexError, KeyError):
            pass
        code_chunks = self._fallback_chunker.chunk_text(text, "<text>")
        chunks = []
        for chunk in code_chunks:
            chunk_dict = {"content": chunk.content, "type": chunk.node_type,
                "start_line": chunk.start_line, "end_line": chunk.end_line}
            if hasattr(chunk, "metadata") and chunk.metadata:
                chunk_dict["metadata"] = chunk.metadata
            chunks.append(chunk_dict)
        return AutoChunkResult(chunks=chunks, language=language,
            grammar_downloaded=grammar_downloaded, fallback_used=True,
            metadata={"fallback_reason": "tree_sitter_failed"})

    def list_supported_extensions(self) -> dict[str, list[str]]:
        """List all supported file extensions.

        Returns:
            Dict mapping language to extensions
        """
        language_extensions: dict[str, list[str]] = {}
        for ext, lang in self.EXTENSION_MAP.items():
            if lang not in language_extensions:
                language_extensions[lang] = []
            language_extensions[lang].append(ext)
        for lang in language_extensions:
            language_extensions[lang].sort()
        return language_extensions

    def get_chunker_for_language(self, language: str, auto_download: bool = True,
        ) -> Any:
        """Get a chunker instance for a specific language.

        Args:
            language: Language name
            auto_download: Download grammar if needed

        Returns:
            Configured chunker instance
        """
        if auto_download and not self.registry.is_language_installed(language,
            ) and not self.ensure_language(language):
            raise ChunkerError(f"Failed to setup language: {language}")
        parser = self.registry.get_parser(language, auto_download=False)
        if not parser:
            raise ChunkerError(f"No parser available for language: {language}")

        class LanguageChunker:

            def __init__(self, lang: str):
                self.language = lang

            def chunk_file(self, file_path: (str | Path)) -> list[Any]:
                return chunk_file(file_path, self.language)

            def chunk_text(self, text: str) -> list[Any]:
                return chunk_text(text, self.language)
        return LanguageChunker(language)

    def preload_languages(self, languages: list[str]) -> dict[str, bool]:
        """Preload multiple language grammars.

        Args:
            languages: List of languages to preload

        Returns:
            Dict of language -> success status
        """
        results = {}
        for language in languages:
            results[language] = self.ensure_language(language)
        return results

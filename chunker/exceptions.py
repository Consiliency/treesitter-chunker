"""Custom exception hierarchy for the tree-sitter chunker."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path


class ChunkerError(Exception):
    """Base exception for all chunker errors."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def __str__(self) -> str:
        if self.details:
            detail_str = ", ".join(f"{k}={v}" for k, v in self.details.items())
            return f"{self.message} ({detail_str})"
        return self.message


class LanguageError(ChunkerError):
    """Base class for language-related errors."""


class LanguageNotFoundError(LanguageError):
    """Raised when requested language is not available."""

    def __init__(self, language: str, available: list[str]):
        message = f"Language '{language}' not found"
        if available:
            message += f". Available languages: {', '.join(sorted(available))}"
        else:
            message += ". No languages available (check library compilation)"

        # Add user guidance for common scenarios
        guidance = self._get_user_guidance(language, available)
        if guidance:
            message += f"\n\n{guidance}"

        super().__init__(message, {"requested": language, "available": available})
        self.language = language
        self.available = available

    def _get_user_guidance(self, language: str, available: list[str]) -> str:
        """Provide user guidance based on the error context."""
        guidance_parts = []

        # Check if this is a common language that should be available
        common_languages = {
            "python",
            "javascript",
            "rust",
            "go",
            "c",
            "cpp",
            "java",
            "csharp",
            "typescript",
            "ruby",
            "php",
            "kotlin",
            "swift",
            "dart",
        }

        if language.lower() in common_languages:
            if not available:
                guidance_parts.append(
                    "💡 This appears to be a common language that should be available.",
                )
                guidance_parts.append(
                    "   The grammar libraries may not be compiled yet.",
                )
                guidance_parts.append(
                    "   Try running the grammar compilation process first.",
                )
            else:
                guidance_parts.append(
                    "💡 This language is not currently compiled but may be available.",
                )
                guidance_parts.append(
                    "   Check if the grammar source is available in the grammars/ directory.",
                )

        # Provide specific guidance for missing grammars
        if not available:
            guidance_parts.append("\n🔧 To resolve this issue:")
            guidance_parts.append("   1. Check that grammar libraries are compiled")
            guidance_parts.append(
                "   2. Verify the grammars/ directory contains source repositories",
            )
            guidance_parts.append("   3. Run grammar compilation scripts if needed")
        else:
            guidance_parts.append(f"\n🔧 To add support for '{language}':")
            guidance_parts.append(
                "   1. Check if grammar source exists in grammars/ directory",
            )
            guidance_parts.append("   2. Compile the grammar to a .so library")
            guidance_parts.append(
                "   3. Place the .so file in chunker/data/grammars/build/",
            )

        # Add troubleshooting tips
        guidance_parts.append("\n💡 Troubleshooting tips:")
        guidance_parts.append(
            "   - Verify the language name is correct (check for typos)",
        )
        guidance_parts.append(
            "   - Check if the language uses a different name (e.g., 'csharp' vs 'c_sharp')",
        )
        guidance_parts.append(
            "   - Ensure the grammar is compatible with your tree-sitter version",
        )

        return "\n".join(guidance_parts)


class LanguageLoadError(LanguageError):
    """Raised when language fails to load from library."""

    def __init__(self, language: str, reason: str):
        message = f"Failed to load language '{language}': {reason}"

        # Add user guidance for common loading issues
        guidance = self._get_loading_guidance(language, reason)
        if guidance:
            message += f"\n\n{guidance}"

        super().__init__(message, {"language": language, "reason": reason})
        self.language = language
        self.reason = reason

    def _get_loading_guidance(self, language: str, reason: str) -> str:
        """Provide user guidance for language loading failures."""
        guidance_parts = []

        # Common loading failure patterns and solutions
        if "symbol" in reason.lower():
            guidance_parts.append("🔧 This appears to be a symbol/library issue:")
            guidance_parts.append(
                "   1. The grammar library may be corrupted or incomplete",
            )
            guidance_parts.append("   2. Try recompiling the grammar from source")
            guidance_parts.append(
                "   3. Check if the grammar is compatible with your tree-sitter version",
            )

        elif "version" in reason.lower():
            guidance_parts.append(
                "🔧 This appears to be a version compatibility issue:",
            )
            guidance_parts.append(
                "   1. The grammar may be compiled for a different tree-sitter version",
            )
            guidance_parts.append(
                "   2. Try recompiling the grammar with your current tree-sitter",
            )
            guidance_parts.append("   3. Check grammar compatibility matrix")

        elif "permission" in reason.lower() or "access" in reason.lower():
            guidance_parts.append("🔧 This appears to be a permission issue:")
            guidance_parts.append("   1. Check file permissions on the grammar library")
            guidance_parts.append("   2. Ensure the .so file is readable by your user")
            guidance_parts.append("   3. Try running with appropriate permissions")

        else:
            guidance_parts.append("🔧 General troubleshooting steps:")
            guidance_parts.append(
                "   1. Verify the grammar library file exists and is not corrupted",
            )
            guidance_parts.append("   2. Check if the grammar source is up to date")
            guidance_parts.append("   3. Try recompiling the grammar from source")
            guidance_parts.append("   4. Check system compatibility (architecture, OS)")

        # Add specific guidance for the language
        guidance_parts.append(f"\n💡 For {language} specifically:")
        guidance_parts.append("   - Check if the grammar repository has recent updates")
        guidance_parts.append(
            "   - Verify the grammar supports your target language version",
        )
        guidance_parts.append(
            "   - Consider using a different grammar version if available",
        )

        return "\n".join(guidance_parts)


class ParserError(ChunkerError):
    """Base class for parser-related errors."""


class ParserInitError(ParserError):
    """Raised when parser initialization fails."""

    def __init__(self, language: str, reason: str):
        super().__init__(
            f"Failed to initialize parser for '{language}': {reason}",
            {"language": language, "reason": reason},
        )
        self.language = language
        self.reason = reason


class ParserConfigError(ParserError):
    """Raised when parser configuration is invalid."""

    def __init__(self, config_name: str, value: Any, reason: str):
        super().__init__(
            f"Invalid parser configuration '{config_name}' = {value}: {reason}",
            {"config_name": config_name, "value": value, "reason": reason},
        )
        self.config_name = config_name
        self.value = value
        self.reason = reason


class LibraryError(ChunkerError):
    """Base class for shared library errors."""


class LibraryNotFoundError(LibraryError):
    """Raised when .so file is missing."""

    def __init__(self, path: Path):
        message = f"Shared library not found at {path}"

        # Add user guidance for missing libraries
        guidance = self._get_library_guidance(path)
        if guidance:
            message += f"\n\n{guidance}"

        super().__init__(
            message,
            {
                "path": str(path),
                "recovery": "Run 'python scripts/build_lib.py' to compile grammars",
            },
        )
        self.path = path

    def _get_library_guidance(self, path: Path) -> str:
        """Provide user guidance for missing library files."""
        guidance_parts = []

        # Check if this is a package grammar directory
        if "chunker/data/grammars/build" in str(path):
            guidance_parts.append(
                "🔧 This is a package grammar library that should be available:",
            )
            guidance_parts.append("   1. The grammar libraries may not be compiled yet")
            guidance_parts.append(
                "   2. Check if the package was built with grammar support",
            )
            guidance_parts.append(
                "   3. Try reinstalling the package or building from source",
            )

        # Check if this is a user grammar directory
        elif "cache" in str(path) or "home" in str(path):
            guidance_parts.append("🔧 This is a user-installed grammar library:")
            guidance_parts.append("   1. The grammar may not be installed yet")
            guidance_parts.append(
                "   2. Try installing the grammar using the CLI tools",
            )
            guidance_parts.append("   3. Check if the grammar source is available")

        # General guidance
        guidance_parts.append("\n💡 To resolve this issue:")
        guidance_parts.append(
            "   1. Verify the grammar source exists in the grammars/ directory",
        )
        guidance_parts.append("   2. Compile the grammar to a .so library")
        guidance_parts.append(
            "   3. Ensure the .so file is placed in the correct directory",
        )

        # Add troubleshooting tips
        guidance_parts.append("\n🔍 Troubleshooting steps:")
        guidance_parts.append(
            "   - Check if the grammar repository exists in grammars/",
        )
        guidance_parts.append("   - Verify the grammar can be compiled successfully")
        guidance_parts.append("   - Check file permissions and directory access")
        guidance_parts.append("   - Ensure the grammar is compatible with your system")

        return "\n".join(guidance_parts)


class LibraryLoadError(LibraryError):
    """Raised when shared library fails to load."""

    def __init__(self, path: Path, reason: str):
        super().__init__(
            f"Failed to load shared library {path}: {reason}",
            {"path": str(path), "reason": reason},
        )
        self.path = path
        self.reason = reason


class ParsingError(ChunkerError):
    """Raised when code parsing fails due to grammar compatibility issues."""

    def __init__(self, language: str, reason: str, code_sample: str = None):
        message = f"Failed to parse {language} code: {reason}"

        # Add user guidance for parsing failures
        guidance = self._get_parsing_guidance(language, reason, code_sample)
        if guidance:
            message += f"\n\n{guidance}"

        super().__init__(
            message,
            {"language": language, "reason": reason, "code_sample": code_sample},
        )
        self.language = language
        self.reason = reason
        self.code_sample = code_sample

    def _get_parsing_guidance(
        self,
        language: str,
        reason: str,
        code_sample: str = None,
    ) -> str:
        """Provide user guidance for parsing failures."""
        guidance_parts = []

        # Common parsing failure patterns and solutions
        if "syntax" in reason.lower():
            guidance_parts.append("🔧 This appears to be a syntax compatibility issue:")
            guidance_parts.append(
                "   1. Your code may use syntax not supported by the current grammar",
            )
            guidance_parts.append(
                "   2. The grammar may be outdated for your language version",
            )
            guidance_parts.append(
                "   3. Try updating the grammar or using compatible syntax",
            )

        elif "version" in reason.lower():
            guidance_parts.append(
                "🔧 This appears to be a version compatibility issue:",
            )
            guidance_parts.append(
                "   1. Your code may use features from a newer language version",
            )
            guidance_parts.append(
                "   2. The grammar may not support the language version you're using",
            )
            guidance_parts.append(
                "   3. Consider updating the grammar or using an older language version",
            )

        elif "feature" in reason.lower() or "construct" in reason.lower():
            guidance_parts.append(
                "🔧 This appears to be a feature compatibility issue:",
            )
            guidance_parts.append(
                "   1. Your code uses language features not yet supported by the grammar",
            )
            guidance_parts.append("   2. The grammar may be incomplete or experimental")
            guidance_parts.append(
                "   3. Try simplifying the code or using supported features",
            )

        else:
            guidance_parts.append("🔧 General parsing troubleshooting:")
            guidance_parts.append(
                "   1. Check if your code uses standard, supported syntax",
            )
            guidance_parts.append(
                "   2. Verify the grammar supports your language version",
            )
            guidance_parts.append("   3. Consider updating the grammar if available")

        # Add specific guidance for the language
        guidance_parts.append(f"\n💡 For {language} specifically:")
        guidance_parts.append(
            "   - Check if the grammar supports your language version",
        )
        guidance_parts.append("   - Verify the grammar is up to date")
        guidance_parts.append(
            "   - Consider using a different grammar version if available",
        )

        # Add code-specific guidance if sample provided
        if code_sample:
            guidance_parts.append("\n🔍 Code analysis:")
            guidance_parts.append("   - Review the code for non-standard syntax")
            guidance_parts.append(
                "   - Check for language features that may not be supported",
            )
            guidance_parts.append("   - Consider simplifying complex constructs")

        # Add recovery steps
        guidance_parts.append("\n🛠️ Recovery options:")
        guidance_parts.append("   1. Try updating the grammar to a newer version")
        guidance_parts.append(
            "   2. Use alternative syntax that's more widely supported",
        )
        guidance_parts.append(
            "   3. Check if there are grammar forks with better support",
        )
        guidance_parts.append("   4. Report the issue to the grammar maintainers")

        return "\n".join(guidance_parts)


class LibrarySymbolError(LibraryError):
    """Raised when a symbol cannot be found in the library."""

    def __init__(self, symbol: str, library_path: Path):
        super().__init__(
            f"Symbol '{symbol}' not found in library {library_path}",
            {
                "symbol": symbol,
                "library": str(library_path),
                "recovery": "Rebuild library or check grammar compilation",
            },
        )
        self.symbol = symbol
        self.library_path = library_path

    def __str__(self) -> str:
        base = super().__str__()
        return f"{base}. Rebuild library with 'python scripts/build_lib.py' or verify grammar files."


class ConfigurationError(ChunkerError):
    """Raised when configuration loading or parsing fails.

    This exception provides clear context about where the error occurred
    (file path) and what went wrong (invalid JSON, missing file, etc.).
    """

    def __init__(self, message: str, path: str | None = None):
        details = {}
        if path:
            details["path"] = str(path)
        super().__init__(message, details)
        self.path = path


class CacheError(ChunkerError):
    """Base class for cache-related errors."""


class CacheCorruptionError(CacheError):
    """Raised when cache data integrity check fails."""

    def __init__(self, path: Path, reason: str):
        super().__init__(
            f"Cache corruption detected for {path}: {reason}",
            {"path": str(path), "reason": reason},
        )
        self.path = path
        self.reason = reason


class CacheVersionError(CacheError):
    """Raised when cache version is incompatible."""

    def __init__(self, cache_version: str, expected_version: str):
        super().__init__(
            f"Cache version mismatch: got {cache_version}, expected {expected_version}",
            {"cache_version": cache_version, "expected_version": expected_version},
        )
        self.cache_version = cache_version
        self.expected_version = expected_version


__all__ = [
    "CacheCorruptionError",
    "CacheError",
    "CacheVersionError",
    "ChunkerError",
    "ConfigurationError",
    "LanguageError",
    "LanguageLoadError",
    "LanguageNotFoundError",
    "LibraryError",
    "LibraryLoadError",
    "LibraryNotFoundError",
    "ParserConfigError",
    "ParserError",
    "ParserInitError",
    "ParsingError",
]

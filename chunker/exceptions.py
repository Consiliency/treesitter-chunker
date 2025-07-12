"""Custom exception hierarchy for the tree-sitter chunker."""
from __future__ import annotations
from typing import Optional, Dict, List, Any
from pathlib import Path


class ChunkerError(Exception):
    """Base exception for all chunker errors."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
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
    pass


class LanguageNotFoundError(LanguageError):
    """Raised when requested language is not available."""
    
    def __init__(self, language: str, available: List[str]):
        message = f"Language '{language}' not found"
        if available:
            message += f". Available languages: {', '.join(sorted(available))}"
        else:
            message += ". No languages available (check library compilation)"
        
        super().__init__(
            message,
            {"requested": language, "available": available}
        )
        self.language = language
        self.available = available


class LanguageLoadError(LanguageError):
    """Raised when language fails to load from library."""
    
    def __init__(self, language: str, reason: str):
        super().__init__(
            f"Failed to load language '{language}': {reason}",
            {"language": language, "reason": reason}
        )
        self.language = language
        self.reason = reason


class ParserError(ChunkerError):
    """Base class for parser-related errors."""
    pass


class ParserInitError(ParserError):
    """Raised when parser initialization fails."""
    
    def __init__(self, language: str, reason: str):
        super().__init__(
            f"Failed to initialize parser for '{language}': {reason}",
            {"language": language, "reason": reason}
        )
        self.language = language
        self.reason = reason


class ParserConfigError(ParserError):
    """Raised when parser configuration is invalid."""
    
    def __init__(self, config_name: str, value: Any, reason: str):
        super().__init__(
            f"Invalid parser configuration '{config_name}' = {value}: {reason}",
            {"config_name": config_name, "value": value, "reason": reason}
        )
        self.config_name = config_name
        self.value = value
        self.reason = reason


class LibraryError(ChunkerError):
    """Base class for shared library errors."""
    pass


class LibraryNotFoundError(LibraryError):
    """Raised when .so file is missing."""
    
    def __init__(self, path: Path):
        super().__init__(
            f"Shared library not found at {path}",
            {
                "path": str(path),
                "recovery": "Run 'python scripts/build_lib.py' to compile grammars"
            }
        )
        self.path = path
    
    def __str__(self) -> str:
        base = super().__str__()
        return f"{base}. Run 'python scripts/fetch_grammars.py' then 'python scripts/build_lib.py' to build the library."


class LibraryLoadError(LibraryError):
    """Raised when shared library fails to load."""
    
    def __init__(self, path: Path, reason: str):
        super().__init__(
            f"Failed to load shared library at {path}: {reason}",
            {
                "path": str(path),
                "reason": reason,
                "recovery": "Check library dependencies with 'ldd' command"
            }
        )
        self.path = path
        self.reason = reason
    
    def __str__(self) -> str:
        base = super().__str__()
        return f"{base}. Check library dependencies with 'ldd {self.path}' or rebuild with 'python scripts/build_lib.py'."


class LibrarySymbolError(LibraryError):
    """Raised when a symbol cannot be found in the library."""
    
    def __init__(self, symbol: str, library_path: Path):
        super().__init__(
            f"Symbol '{symbol}' not found in library {library_path}",
            {
                "symbol": symbol,
                "library": str(library_path),
                "recovery": "Rebuild library or check grammar compilation"
            }
        )
        self.symbol = symbol
        self.library_path = library_path
    
    def __str__(self) -> str:
        base = super().__str__()
        return f"{base}. Rebuild library with 'python scripts/build_lib.py' or verify grammar files."
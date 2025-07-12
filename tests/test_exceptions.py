"""Tests for exception hierarchy."""
import pytest
from pathlib import Path

from chunker.exceptions import (
    ChunkerError, LanguageError, LanguageNotFoundError, LanguageLoadError,
    ParserError, ParserInitError, ParserConfigError,
    LibraryError, LibraryNotFoundError, LibraryLoadError, LibrarySymbolError
)


class TestChunkerError:
    """Test base ChunkerError class."""
    
    def test_basic_error(self):
        """Test basic error creation."""
        err = ChunkerError("Something went wrong")
        assert str(err) == "Something went wrong"
        assert err.message == "Something went wrong"
        assert err.details == {}
    
    def test_error_with_details(self):
        """Test error with details."""
        err = ChunkerError("Error occurred", {"code": 42, "file": "test.py"})
        assert err.message == "Error occurred"
        assert err.details == {"code": 42, "file": "test.py"}
        assert str(err) == "Error occurred (code=42, file=test.py)"
    
    def test_inheritance(self):
        """Test that ChunkerError inherits from Exception."""
        err = ChunkerError("Test")
        assert isinstance(err, Exception)


class TestLanguageErrors:
    """Test language-related errors."""
    
    def test_language_not_found_error(self):
        """Test LanguageNotFoundError."""
        err = LanguageNotFoundError("golang", ["python", "javascript", "rust"])
        
        assert isinstance(err, LanguageError)
        assert isinstance(err, ChunkerError)
        assert err.language == "golang"
        assert err.available == ["python", "javascript", "rust"]
        assert "golang" in str(err)
        assert "Available languages: javascript, python, rust" in str(err)
    
    def test_language_not_found_no_available(self):
        """Test LanguageNotFoundError with no available languages."""
        err = LanguageNotFoundError("python", [])
        
        assert "No languages available" in str(err)
        assert "check library compilation" in str(err)
    
    def test_language_load_error(self):
        """Test LanguageLoadError."""
        err = LanguageLoadError("rust", "Symbol not found")
        
        assert isinstance(err, LanguageError)
        assert err.language == "rust"
        assert err.reason == "Symbol not found"
        assert "Failed to load language 'rust'" in str(err)
        assert "Symbol not found" in str(err)


class TestParserErrors:
    """Test parser-related errors."""
    
    def test_parser_init_error(self):
        """Test ParserInitError."""
        err = ParserInitError("python", "Version mismatch")
        
        assert isinstance(err, ParserError)
        assert isinstance(err, ChunkerError)
        assert err.language == "python"
        assert err.reason == "Version mismatch"
        assert "Failed to initialize parser for 'python'" in str(err)
        assert "Version mismatch" in str(err)
    
    def test_parser_config_error(self):
        """Test ParserConfigError."""
        err = ParserConfigError("timeout_ms", -100, "Must be positive")
        
        assert isinstance(err, ParserError)
        assert err.config_name == "timeout_ms"
        assert err.value == -100
        assert err.reason == "Must be positive"
        assert "Invalid parser configuration 'timeout_ms' = -100" in str(err)
        assert "Must be positive" in str(err)


class TestLibraryErrors:
    """Test library-related errors."""
    
    def test_library_not_found_error(self):
        """Test LibraryNotFoundError."""
        path = Path("/path/to/missing.so")
        err = LibraryNotFoundError(path)
        
        assert isinstance(err, LibraryError)
        assert isinstance(err, ChunkerError)
        assert err.path == path
        assert "Shared library not found at /path/to/missing.so" in str(err)
        
        # Check that recovery suggestion is in details
        assert "recovery" in err.details
        assert "build_lib.py" in err.details["recovery"]
        
        # Check that recovery message is in string representation
        error_str = str(err)
        assert "fetch_grammars.py" in error_str
        assert "build_lib.py" in error_str
    
    def test_library_load_error(self):
        """Test LibraryLoadError."""
        path = Path("/path/to/broken.so")
        err = LibraryLoadError(path, "Missing dependency")
        
        assert isinstance(err, LibraryError)
        assert err.path == path
        assert err.reason == "Missing dependency"
        assert "Failed to load shared library" in str(err)
        assert "Missing dependency" in str(err)
        
        # Check recovery suggestion
        assert "recovery" in err.details
        assert "ldd" in err.details["recovery"]
        
        # Check that recovery message is in string representation
        error_str = str(err)
        assert "ldd" in error_str
        assert "build_lib.py" in error_str
    
    def test_library_symbol_error(self):
        """Test LibrarySymbolError."""
        path = Path("/path/to/lib.so")
        err = LibrarySymbolError("tree_sitter_golang", path)
        
        assert isinstance(err, LibraryError)
        assert err.symbol == "tree_sitter_golang"
        assert err.library_path == path
        assert "Symbol 'tree_sitter_golang' not found" in str(err)
        
        # Check recovery suggestion
        assert "recovery" in err.details
        assert "Rebuild library" in err.details["recovery"]
        
        # Check that recovery message is in string representation
        error_str = str(err)
        assert "build_lib.py" in error_str
        assert "verify grammar files" in error_str


class TestExceptionHierarchy:
    """Test the overall exception hierarchy."""
    
    def test_all_inherit_from_chunker_error(self):
        """Test that all exceptions inherit from ChunkerError."""
        exceptions = [
            LanguageNotFoundError("test", []),
            LanguageLoadError("test", "reason"),
            ParserInitError("test", "reason"),
            ParserConfigError("config", "value", "reason"),
            LibraryNotFoundError(Path("test.so")),
            LibraryLoadError(Path("test.so"), "reason"),
            LibrarySymbolError("symbol", Path("test.so"))
        ]
        
        for exc in exceptions:
            assert isinstance(exc, ChunkerError)
            assert isinstance(exc, Exception)
    
    def test_error_categories(self):
        """Test error categorization."""
        # Language errors
        assert isinstance(LanguageNotFoundError("test", []), LanguageError)
        assert isinstance(LanguageLoadError("test", "reason"), LanguageError)
        
        # Parser errors
        assert isinstance(ParserInitError("test", "reason"), ParserError)
        assert isinstance(ParserConfigError("config", "value", "reason"), ParserError)
        
        # Library errors
        assert isinstance(LibraryNotFoundError(Path("test")), LibraryError)
        assert isinstance(LibraryLoadError(Path("test"), "reason"), LibraryError)
        assert isinstance(LibrarySymbolError("symbol", Path("test")), LibraryError)
    
    def test_exception_catching(self):
        """Test exception catching patterns."""
        # Can catch specific exceptions
        with pytest.raises(LanguageNotFoundError):
            raise LanguageNotFoundError("test", [])
        
        # Can catch category exceptions
        with pytest.raises(LanguageError):
            raise LanguageNotFoundError("test", [])
        
        # Can catch base exception
        with pytest.raises(ChunkerError):
            raise ParserConfigError("config", "value", "reason")


class TestErrorMessages:
    """Test error message formatting."""
    
    def test_consistent_formatting(self):
        """Test that error messages follow consistent format."""
        errors = [
            LanguageNotFoundError("golang", ["python", "rust"]),
            LanguageLoadError("rust", "Symbol error"),
            ParserInitError("python", "Version 15"),
            ParserConfigError("timeout", -1, "Must be positive"),
            LibraryNotFoundError(Path("/lib.so")),
            LibraryLoadError(Path("/lib.so"), "Permission denied"),
            LibrarySymbolError("tree_sitter_go", Path("/lib.so"))
        ]
        
        for err in errors:
            msg = str(err)
            # All messages should be descriptive
            assert len(msg) > 10
            # Should contain relevant context
            if hasattr(err, 'language'):
                assert err.language in msg
            if hasattr(err, 'path'):
                assert str(err.path) in msg
            if hasattr(err, 'symbol'):
                assert err.symbol in msg
    
    def test_details_in_string_representation(self):
        """Test that details are included in string representation."""
        err = ChunkerError("Test error", {"key1": "value1", "key2": 42})
        msg = str(err)
        
        assert "Test error" in msg
        assert "key1=value1" in msg
        assert "key2=42" in msg
        assert msg == "Test error (key1=value1, key2=42)"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
"""Unit tests for context factory."""
import pytest

from chunker.context import ContextFactory
from chunker.context.languages.javascript import (
    JavaScriptContextExtractor,
    JavaScriptContextFilter,
    JavaScriptScopeAnalyzer,
    JavaScriptSymbolResolver,
)
from chunker.context.languages.python import (
    PythonContextExtractor,
    PythonContextFilter,
    PythonScopeAnalyzer,
    PythonSymbolResolver,
)


class TestContextFactory:
    """Test the context factory."""

    @staticmethod
    def test_create_context_extractor_python():
        """Test creating a Python context extractor."""
        extractor = ContextFactory.create_context_extractor("python")
        assert isinstance(extractor, PythonContextExtractor)
        assert extractor.language == "python"

    @staticmethod
    def test_create_context_extractor_javascript():
        """Test creating a JavaScript context extractor."""
        extractor = ContextFactory.create_context_extractor("javascript")
        assert isinstance(extractor, JavaScriptContextExtractor)
        assert extractor.language == "javascript"

    @staticmethod
    def test_create_context_extractor_unsupported():
        """Test creating extractor for unsupported language."""
        with pytest.raises(ValueError) as exc_info:
            ContextFactory.create_context_extractor("rust")
        assert "No context extractor available" in str(exc_info.value)
        assert "rust" in str(exc_info.value)

    @staticmethod
    def test_create_symbol_resolver_python():
        """Test creating a Python symbol resolver."""
        resolver = ContextFactory.create_symbol_resolver("python")
        assert isinstance(resolver, PythonSymbolResolver)
        assert resolver.language == "python"

    @staticmethod
    def test_create_symbol_resolver_javascript():
        """Test creating a JavaScript symbol resolver."""
        resolver = ContextFactory.create_symbol_resolver("javascript")
        assert isinstance(resolver, JavaScriptSymbolResolver)
        assert resolver.language == "javascript"

    @staticmethod
    def test_create_symbol_resolver_unsupported():
        """Test creating resolver for unsupported language."""
        with pytest.raises(ValueError) as exc_info:
            ContextFactory.create_symbol_resolver("c++")
        assert "No symbol resolver available" in str(exc_info.value)

    @staticmethod
    def test_create_scope_analyzer_python():
        """Test creating a Python scope analyzer."""
        analyzer = ContextFactory.create_scope_analyzer("python")
        assert isinstance(analyzer, PythonScopeAnalyzer)
        assert analyzer.language == "python"

    @staticmethod
    def test_create_scope_analyzer_javascript():
        """Test creating a JavaScript scope analyzer."""
        analyzer = ContextFactory.create_scope_analyzer("javascript")
        assert isinstance(analyzer, JavaScriptScopeAnalyzer)
        assert analyzer.language == "javascript"

    @staticmethod
    def test_create_scope_analyzer_unsupported():
        """Test creating analyzer for unsupported language."""
        with pytest.raises(ValueError) as exc_info:
            ContextFactory.create_scope_analyzer("go")
        assert "No scope analyzer available" in str(exc_info.value)

    @staticmethod
    def test_create_context_filter_python():
        """Test creating a Python context filter_func."""
        filter_func = ContextFactory.create_context_filter("python")
        assert isinstance(filter_func, PythonContextFilter)
        assert filter_func.language == "python"

    @staticmethod
    def test_create_context_filter_javascript():
        """Test creating a JavaScript context filter_func."""
        filter_func = ContextFactory.create_context_filter("javascript")
        assert isinstance(filter_func, JavaScriptContextFilter)
        assert filter_func.language == "javascript"

    @staticmethod
    def test_create_context_filter_unsupported():
        """Test creating filter_func for unsupported language."""
        with pytest.raises(ValueError) as exc_info:
            ContextFactory.create_context_filter("java")
        assert "No context filter_func available" in str(exc_info.value)

    @staticmethod
    def test_create_all_python():
        """Test creating all components for Python."""
        extractor, resolver, analyzer, filter_func = ContextFactory.create_all(
            "python")
        assert isinstance(extractor, PythonContextExtractor)
        assert isinstance(resolver, PythonSymbolResolver)
        assert isinstance(analyzer, PythonScopeAnalyzer)
        assert isinstance(filter_func, PythonContextFilter)

    @staticmethod
    def test_create_all_javascript():
        """Test creating all components for JavaScript."""
        extractor, resolver, analyzer, filter_func = ContextFactory.create_all(
            "javascript")
        assert isinstance(extractor, JavaScriptContextExtractor)
        assert isinstance(resolver, JavaScriptSymbolResolver)
        assert isinstance(analyzer, JavaScriptScopeAnalyzer)
        assert isinstance(filter_func, JavaScriptContextFilter)

    @staticmethod
    def test_create_all_unsupported():
        """Test creating all components for unsupported language."""
        with pytest.raises(ValueError):
            ContextFactory.create_all("ruby")

    @staticmethod
    def test_is_language_supported():
        """Test checking if a language is supported."""
        assert ContextFactory.is_language_supported("python")
        assert ContextFactory.is_language_supported("javascript")
        assert not ContextFactory.is_language_supported("rust")
        assert not ContextFactory.is_language_supported("unknown")

    @staticmethod
    def test_get_supported_languages():
        """Test getting list of supported languages."""
        languages = ContextFactory.get_supported_languages()
        assert isinstance(languages, list)
        assert "python" in languages
        assert "javascript" in languages
        assert len(languages) >= 2
        assert languages == sorted(languages)

"""Unit tests for context factory."""

import pytest

from chunker.context import ContextFactory
from chunker.context.languages.python import (
    PythonContextExtractor,
    PythonSymbolResolver,
    PythonScopeAnalyzer,
    PythonContextFilter
)
from chunker.context.languages.javascript import (
    JavaScriptContextExtractor,
    JavaScriptSymbolResolver,
    JavaScriptScopeAnalyzer,
    JavaScriptContextFilter
)


class TestContextFactory:
    """Test the context factory."""
    
    def test_create_context_extractor_python(self):
        """Test creating a Python context extractor."""
        extractor = ContextFactory.create_context_extractor('python')
        assert isinstance(extractor, PythonContextExtractor)
        assert extractor.language == 'python'
    
    def test_create_context_extractor_javascript(self):
        """Test creating a JavaScript context extractor."""
        extractor = ContextFactory.create_context_extractor('javascript')
        assert isinstance(extractor, JavaScriptContextExtractor)
        assert extractor.language == 'javascript'
    
    def test_create_context_extractor_unsupported(self):
        """Test creating extractor for unsupported language."""
        with pytest.raises(ValueError) as exc_info:
            ContextFactory.create_context_extractor('rust')
        
        assert "No context extractor available" in str(exc_info.value)
        assert "rust" in str(exc_info.value)
    
    def test_create_symbol_resolver_python(self):
        """Test creating a Python symbol resolver."""
        resolver = ContextFactory.create_symbol_resolver('python')
        assert isinstance(resolver, PythonSymbolResolver)
        assert resolver.language == 'python'
    
    def test_create_symbol_resolver_javascript(self):
        """Test creating a JavaScript symbol resolver."""
        resolver = ContextFactory.create_symbol_resolver('javascript')
        assert isinstance(resolver, JavaScriptSymbolResolver)
        assert resolver.language == 'javascript'
    
    def test_create_symbol_resolver_unsupported(self):
        """Test creating resolver for unsupported language."""
        with pytest.raises(ValueError) as exc_info:
            ContextFactory.create_symbol_resolver('c++')
        
        assert "No symbol resolver available" in str(exc_info.value)
    
    def test_create_scope_analyzer_python(self):
        """Test creating a Python scope analyzer."""
        analyzer = ContextFactory.create_scope_analyzer('python')
        assert isinstance(analyzer, PythonScopeAnalyzer)
        assert analyzer.language == 'python'
    
    def test_create_scope_analyzer_javascript(self):
        """Test creating a JavaScript scope analyzer."""
        analyzer = ContextFactory.create_scope_analyzer('javascript')
        assert isinstance(analyzer, JavaScriptScopeAnalyzer)
        assert analyzer.language == 'javascript'
    
    def test_create_scope_analyzer_unsupported(self):
        """Test creating analyzer for unsupported language."""
        with pytest.raises(ValueError) as exc_info:
            ContextFactory.create_scope_analyzer('go')
        
        assert "No scope analyzer available" in str(exc_info.value)
    
    def test_create_context_filter_python(self):
        """Test creating a Python context filter."""
        filter = ContextFactory.create_context_filter('python')
        assert isinstance(filter, PythonContextFilter)
        assert filter.language == 'python'
    
    def test_create_context_filter_javascript(self):
        """Test creating a JavaScript context filter."""
        filter = ContextFactory.create_context_filter('javascript')
        assert isinstance(filter, JavaScriptContextFilter)
        assert filter.language == 'javascript'
    
    def test_create_context_filter_unsupported(self):
        """Test creating filter for unsupported language."""
        with pytest.raises(ValueError) as exc_info:
            ContextFactory.create_context_filter('java')
        
        assert "No context filter available" in str(exc_info.value)
    
    def test_create_all_python(self):
        """Test creating all components for Python."""
        extractor, resolver, analyzer, filter = ContextFactory.create_all('python')
        
        assert isinstance(extractor, PythonContextExtractor)
        assert isinstance(resolver, PythonSymbolResolver)
        assert isinstance(analyzer, PythonScopeAnalyzer)
        assert isinstance(filter, PythonContextFilter)
    
    def test_create_all_javascript(self):
        """Test creating all components for JavaScript."""
        extractor, resolver, analyzer, filter = ContextFactory.create_all('javascript')
        
        assert isinstance(extractor, JavaScriptContextExtractor)
        assert isinstance(resolver, JavaScriptSymbolResolver)
        assert isinstance(analyzer, JavaScriptScopeAnalyzer)
        assert isinstance(filter, JavaScriptContextFilter)
    
    def test_create_all_unsupported(self):
        """Test creating all components for unsupported language."""
        with pytest.raises(ValueError):
            ContextFactory.create_all('ruby')
    
    def test_is_language_supported(self):
        """Test checking if a language is supported."""
        assert ContextFactory.is_language_supported('python') == True
        assert ContextFactory.is_language_supported('javascript') == True
        assert ContextFactory.is_language_supported('rust') == False
        assert ContextFactory.is_language_supported('unknown') == False
    
    def test_get_supported_languages(self):
        """Test getting list of supported languages."""
        languages = ContextFactory.get_supported_languages()
        
        assert isinstance(languages, list)
        assert 'python' in languages
        assert 'javascript' in languages
        assert len(languages) >= 2
        
        # Should be sorted
        assert languages == sorted(languages)
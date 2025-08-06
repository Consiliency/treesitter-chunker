"""Factory for creating language-specific context extractors."""

from typing import ClassVar

from chunker.interfaces.context import (
    ContextExtractor,
    ContextFilter,
    ScopeAnalyzer,
    SymbolResolver,
)

from .languages.javascript import (
    JavaScriptContextExtractor,
    JavaScriptContextFilter,
    JavaScriptScopeAnalyzer,
    JavaScriptSymbolResolver,
)
from .languages.python import (
    PythonContextExtractor,
    PythonContextFilter,
    PythonScopeAnalyzer,
    PythonSymbolResolver,
)


class ContextFactory:
    """Factory for creating language-specific context components."""

    # Registry of language implementations
    _extractors: ClassVar[dict[str, type[ContextExtractor]]] = {
        "python": PythonContextExtractor,
        "javascript": JavaScriptContextExtractor,
    }

    _symbol_resolvers: ClassVar[dict[str, type[SymbolResolver]]] = {
        "python": PythonSymbolResolver,
        "javascript": JavaScriptSymbolResolver,
    }

    _scope_analyzers: ClassVar[dict[str, type[ScopeAnalyzer]]] = {
        "python": PythonScopeAnalyzer,
        "javascript": JavaScriptScopeAnalyzer,
    }

    _context_filters: ClassVar[dict[str, type[ContextFilter]]] = {
        "python": PythonContextFilter,
        "javascript": JavaScriptContextFilter,
    }

    @classmethod
    def create_context_extractor(cls, language: str) -> ContextExtractor:
        """Create a context extractor for the specified language.

        Args:
            language: Language identifier

        Returns:
            Language-specific context extractor

        Raises:
            ValueError: If language is not supported
        """
        if language not in cls._extractors:
            raise ValueError(f"No context extractor available for language: {language}")

        extractor_class = cls._extractors[language]
        return extractor_class()

    @classmethod
    def create_symbol_resolver(cls, language: str) -> SymbolResolver:
        """Create a symbol resolver for the specified language.

        Args:
            language: Language identifier

        Returns:
            Language-specific symbol resolver

        Raises:
            ValueError: If language is not supported
        """
        if language not in cls._symbol_resolvers:
            raise ValueError(f"No symbol resolver available for language: {language}")

        resolver_class = cls._symbol_resolvers[language]
        return resolver_class()

    @classmethod
    def create_scope_analyzer(cls, language: str) -> ScopeAnalyzer:
        """Create a scope analyzer for the specified language.

        Args:
            language: Language identifier

        Returns:
            Language-specific scope analyzer

        Raises:
            ValueError: If language is not supported
        """
        if language not in cls._scope_analyzers:
            raise ValueError(f"No scope analyzer available for language: {language}")

        analyzer_class = cls._scope_analyzers[language]
        return analyzer_class()

    @classmethod
    def create_context_filter(cls, language: str) -> ContextFilter:
        """Create a context filter for the specified language.

        Args:
            language: Language identifier

        Returns:
            Language-specific context filter

        Raises:
            ValueError: If language is not supported
        """
        if language not in cls._context_filters:
            raise ValueError(f"No context filter available for language: {language}")

        filter_class = cls._context_filters[language]
        return filter_class()

    @classmethod
    def create_all(
        cls,
        language: str,
    ) -> tuple[ContextExtractor, SymbolResolver, ScopeAnalyzer, ContextFilter]:
        """Create all context components for a language.

        Args:
            language: Language identifier

        Returns:
            Tuple of (extractor, resolver, analyzer, filter)

        Raises:
            ValueError: If language is not supported
        """
        return (
            cls.create_context_extractor(language),
            cls.create_symbol_resolver(language),
            cls.create_scope_analyzer(language),
            cls.create_context_filter(language),
        )

    @classmethod
    def is_language_supported(cls, language: str) -> bool:
        """Check if a language is supported for context extraction.

        Args:
            language: Language identifier

        Returns:
            True if language is supported
        """
        return (
            language in cls._extractors
            and language in cls._symbol_resolvers
            and language in cls._scope_analyzers
            and language in cls._context_filters
        )

    @classmethod
    def get_supported_languages(cls) -> list[str]:
        """Get list of supported languages.

        Returns:
            List of language identifiers
        """
        # Return languages that have all components
        all_langs = set(cls._extractors.keys())
        all_langs &= set(cls._symbol_resolvers.keys())
        all_langs &= set(cls._scope_analyzers.keys())
        all_langs &= set(cls._context_filters.keys())

        return sorted(all_langs)

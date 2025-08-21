"""Factory for creating language-specific metadata extractors."""

from typing import ClassVar

from chunker.interfaces.metadata import ComplexityAnalyzer, MetadataExtractor

from .languages import (
    CMetadataExtractor,
    CppMetadataExtractor,
    GoMetadataExtractor,
    JavaScriptComplexityAnalyzer,
    JavaScriptMetadataExtractor,
    PythonComplexityAnalyzer,
    PythonMetadataExtractor,
    RustMetadataExtractor,
    TypeScriptComplexityAnalyzer,
    TypeScriptMetadataExtractor,
)


class MetadataExtractorFactory:
    """Factory for creating language-specific metadata extractors."""

    # Registry of language-specific extractors
    _extractors: ClassVar[dict[str, type[MetadataExtractor]]] = {
        "python": PythonMetadataExtractor,
        "javascript": JavaScriptMetadataExtractor,
        "typescript": TypeScriptMetadataExtractor,
        "tsx": TypeScriptMetadataExtractor,  # TSX uses same extractor
        "jsx": JavaScriptMetadataExtractor,  # JSX uses same extractor
        "rust": RustMetadataExtractor,
        "go": GoMetadataExtractor,
        "c": CMetadataExtractor,
        "cpp": CppMetadataExtractor,
    }

    _analyzers: ClassVar[dict[str, type[ComplexityAnalyzer]]] = {
        "python": PythonComplexityAnalyzer,
        "javascript": JavaScriptComplexityAnalyzer,
        "typescript": TypeScriptComplexityAnalyzer,
        "tsx": TypeScriptComplexityAnalyzer,
        "jsx": JavaScriptComplexityAnalyzer,
    }

    @classmethod
    def create_extractor(cls, language: str) -> MetadataExtractor | None:
        """
        Create a metadata extractor for the given language.

        Args:
            language: Programming language name

        Returns:
            MetadataExtractor instance or None if language not supported
        """
        extractor_class = cls._extractors.get(language.lower())
        if extractor_class:
            # Pass language to the extractor constructor
            return extractor_class(language.lower())
        return None

    @classmethod
    def create_analyzer(cls, language: str) -> ComplexityAnalyzer | None:
        """
        Create a complexity analyzer for the given language.

        Args:
            language: Programming language name

        Returns:
            ComplexityAnalyzer instance or None if language not supported
        """
        analyzer_class = cls._analyzers.get(language.lower())
        if analyzer_class:
            return analyzer_class()
        return None

    @classmethod
    def create_both(
        cls,
        language: str,
    ) -> tuple[MetadataExtractor | None, ComplexityAnalyzer | None]:
        """
        Create both metadata extractor and complexity analyzer.

        Args:
            language: Programming language name

        Returns:
            Tuple of (MetadataExtractor, ComplexityAnalyzer) or (None, None)
        """
        return cls.create_extractor(language), cls.create_analyzer(language)

    @classmethod
    def is_supported(cls, language: str) -> bool:
        """
        Check if language is supported for metadata extraction.

        Args:
            language: Programming language name

        Returns:
            True if language is supported
        """
        return language.lower() in cls._extractors

    @classmethod
    def supported_languages(cls) -> list[str]:
        """
        Get list of supported languages.

        Returns:
            List of supported language names
        """
        return sorted(cls._extractors.keys())

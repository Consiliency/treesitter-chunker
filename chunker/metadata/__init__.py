"""Metadata extraction module for enriching chunks with additional information."""

from .extractor import BaseMetadataExtractor
from .metrics import BaseComplexityAnalyzer
from .factory import MetadataExtractorFactory

__all__ = [
    'BaseMetadataExtractor',
    'BaseComplexityAnalyzer',
    'MetadataExtractorFactory',
]
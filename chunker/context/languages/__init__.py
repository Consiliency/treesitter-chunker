"""Language-specific context extractors."""

from .javascript import (
    JavaScriptContextExtractor,
    JavaScriptContextFilter,
    JavaScriptScopeAnalyzer,
    JavaScriptSymbolResolver,
)
from .python import (
    PythonContextExtractor,
    PythonContextFilter,
    PythonScopeAnalyzer,
    PythonSymbolResolver,
)

__all__ = [
    "JavaScriptContextExtractor",
    "JavaScriptContextFilter",
    "JavaScriptScopeAnalyzer",
    "JavaScriptSymbolResolver",
    "PythonContextExtractor",
    "PythonContextFilter",
    "PythonScopeAnalyzer",
    "PythonSymbolResolver",
]

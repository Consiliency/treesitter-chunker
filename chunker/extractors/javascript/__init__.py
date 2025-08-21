"""
JavaScript/TypeScript extractor module for Phase 2 call site extraction.

This module provides specialized extraction capabilities for JavaScript and TypeScript
source code, using robust regex-based pattern matching to identify various types
of function calls and method invocations.
"""

from .javascript_extractor import JavaScriptExtractor, JavaScriptPatterns

__all__ = ["JavaScriptExtractor", "JavaScriptPatterns"]

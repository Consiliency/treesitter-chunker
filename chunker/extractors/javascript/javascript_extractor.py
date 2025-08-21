"""
JavaScript/TypeScript extractor for Phase 2 call site extraction.

This module provides specialized extraction for JavaScript and TypeScript source code,
using robust regex-based pattern matching to identify function calls, method calls,
and other call site patterns specific to JavaScript/TypeScript syntax.
"""

import logging
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from ..core.extraction_framework import (
    BaseExtractor,
    CallSite,
    ExtractionResult,
    ExtractionUtils,
)

logger = logging.getLogger(__name__)


class JavaScriptExtractor(BaseExtractor):
    """Specialized extractor for JavaScript/TypeScript source code."""

    def __init__(self):
        """Initialize JavaScript extractor."""
        super().__init__("javascript")
        self.patterns = JavaScriptPatterns()
        self._is_initialized = True

        # Track extraction statistics
        self.extraction_stats = {
            "function_calls": 0,
            "method_calls": 0,
            "constructor_calls": 0,
            "jsx_calls": 0,
            "template_calls": 0,
            "total_processed": 0,
        }

        self.logger.debug("JavaScript extractor initialized with pattern matching")

    def extract_calls(
        self,
        source_code: str,
        file_path: Path | None = None,
    ) -> ExtractionResult:
        """
        Extract call sites from JavaScript source code.

        Args:
            source_code: The JavaScript/TypeScript source code to analyze
            file_path: Optional path to the source file

        Returns:
            ExtractionResult containing found call sites and metadata
        """
        start_time = time.perf_counter()
        result = ExtractionResult()

        try:
            # Validate input
            self._validate_input(source_code, file_path)

            # Set default file path if not provided
            if file_path is None:
                file_path = Path("unknown.js")
            elif isinstance(file_path, str):
                file_path = Path(file_path)

            # Validate source code
            if not self.validate_source(source_code):
                result.add_warning(
                    "Source code validation failed, proceeding with extraction",
                )

            # Extract different types of calls
            with self._measure_performance("function_calls"):
                function_calls = self.extract_function_calls(source_code)
                result.call_sites.extend(function_calls)
                self.extraction_stats["function_calls"] += len(function_calls)

            with self._measure_performance("method_calls"):
                method_calls = self.extract_method_calls(source_code)
                result.call_sites.extend(method_calls)
                self.extraction_stats["method_calls"] += len(method_calls)

            with self._measure_performance("constructor_calls"):
                constructor_calls = self.extract_constructor_calls(source_code)
                result.call_sites.extend(constructor_calls)
                self.extraction_stats["constructor_calls"] += len(constructor_calls)

            with self._measure_performance("jsx_calls"):
                jsx_calls = self.extract_jsx_calls(source_code)
                result.call_sites.extend(jsx_calls)
                self.extraction_stats["jsx_calls"] += len(jsx_calls)

            with self._measure_performance("template_calls"):
                template_calls = self.extract_template_calls(source_code)
                result.call_sites.extend(template_calls)
                self.extraction_stats["template_calls"] += len(template_calls)

            # Set file path for all call sites
            for call_site in result.call_sites:
                call_site.file_path = file_path
                call_site.language = self.language

            # Remove duplicates and validate
            result.call_sites = self._deduplicate_calls(result.call_sites)
            self._validate_call_sites(result, source_code)

            # Add metadata
            result.metadata.update(
                {
                    "extractor": "JavaScriptExtractor",
                    "language": self.language,
                    "file_path": str(file_path),
                    "source_length": len(source_code),
                    "lines_count": source_code.count("\n") + 1,
                    "extraction_stats": self.extraction_stats.copy(),
                    "patterns_used": "regex_based",
                },
            )

            # Add file metadata if file exists
            if file_path.exists():
                file_metadata = ExtractionUtils.extract_file_metadata(file_path)
                result.metadata["file_metadata"] = file_metadata

            self.extraction_stats["total_processed"] += 1

        except Exception as e:
            result.add_error("JavaScript extraction failed", e)

        finally:
            result.extraction_time = time.perf_counter() - start_time
            result.performance_metrics = self.get_performance_metrics()

        self.logger.debug(
            f"JavaScript extraction completed: {len(result.call_sites)} calls found in {result.extraction_time:.3f}s",
        )

        return result

    def validate_source(self, source_code: str) -> bool:
        """
        Validate JavaScript source code.

        Args:
            source_code: The source code to validate

        Returns:
            True if valid, False otherwise
        """
        try:
            if not isinstance(source_code, str):
                return False

            if not source_code.strip():
                return False

            # Basic syntax validation
            # Check for balanced brackets
            if not self._check_balanced_brackets(source_code):
                self.logger.warning("Unbalanced brackets detected in JavaScript code")
                return False

            # Check for basic JavaScript syntax indicators
            js_indicators = [
                r"\bfunction\b",
                r"\bvar\b|\blet\b|\bconst\b",
                r"\bif\b|\belse\b|\bfor\b|\bwhile\b",
                r"\breturn\b",
                r"=>",  # Arrow functions
                r"\bclass\b",
                r"\bimport\b|\bexport\b",
                r"\basync\b|\bawait\b",
            ]

            # Should match at least one JavaScript indicator
            has_js_syntax = any(
                re.search(pattern, source_code) for pattern in js_indicators
            )

            if not has_js_syntax:
                self.logger.warning("No JavaScript syntax indicators found")

            return True

        except Exception as e:
            self.logger.error(f"Error validating JavaScript source: {e}")
            return False

    def extract_function_calls(self, source_code: str) -> list[CallSite]:
        """
        Extract function calls from JavaScript code.

        Args:
            source_code: JavaScript source code

        Returns:
            List of CallSite objects for function calls
        """
        call_sites = []

        try:
            # Find function calls using patterns
            function_calls = self.patterns.find_function_calls(source_code)

            for call_info in function_calls:
                try:
                    call_site = self._create_call_site_from_match(
                        call_info,
                        source_code,
                        "function",
                    )
                    if call_site:
                        call_sites.append(call_site)

                except Exception as e:
                    self.logger.warning(f"Error processing function call: {e}")
                    continue

        except Exception as e:
            self.logger.error(f"Error extracting function calls: {e}")

        return call_sites

    def extract_method_calls(self, source_code: str) -> list[CallSite]:
        """
        Extract method calls from JavaScript code.

        Args:
            source_code: JavaScript source code

        Returns:
            List of CallSite objects for method calls
        """
        call_sites = []

        try:
            # Find method calls using patterns
            method_calls = self.patterns.find_method_calls(source_code)

            for call_info in method_calls:
                try:
                    call_site = self._create_call_site_from_match(
                        call_info,
                        source_code,
                        "method",
                    )
                    if call_site:
                        call_sites.append(call_site)

                except Exception as e:
                    self.logger.warning(f"Error processing method call: {e}")
                    continue

        except Exception as e:
            self.logger.error(f"Error extracting method calls: {e}")

        return call_sites

    def extract_constructor_calls(self, source_code: str) -> list[CallSite]:
        """
        Extract constructor calls (new expressions) from JavaScript code.

        Args:
            source_code: JavaScript source code

        Returns:
            List of CallSite objects for constructor calls
        """
        call_sites = []

        try:
            # Find constructor calls using patterns
            constructor_calls = self.patterns.find_constructor_calls(source_code)

            for call_info in constructor_calls:
                try:
                    call_site = self._create_call_site_from_match(
                        call_info,
                        source_code,
                        "constructor",
                    )
                    if call_site:
                        call_sites.append(call_site)

                except Exception as e:
                    self.logger.warning(f"Error processing constructor call: {e}")
                    continue

        except Exception as e:
            self.logger.error(f"Error extracting constructor calls: {e}")

        return call_sites

    def extract_jsx_calls(self, source_code: str) -> list[CallSite]:
        """
        Extract JSX component calls from JavaScript/TypeScript code.

        Args:
            source_code: JavaScript/TypeScript source code

        Returns:
            List of CallSite objects for JSX calls
        """
        call_sites = []

        try:
            # Find JSX calls using patterns
            jsx_calls = self.patterns.find_jsx_calls(source_code)

            for call_info in jsx_calls:
                try:
                    call_site = self._create_call_site_from_match(
                        call_info,
                        source_code,
                        "jsx",
                    )
                    if call_site:
                        call_sites.append(call_site)

                except Exception as e:
                    self.logger.warning(f"Error processing JSX call: {e}")
                    continue

        except Exception as e:
            self.logger.error(f"Error extracting JSX calls: {e}")

        return call_sites

    def extract_template_calls(self, source_code: str) -> list[CallSite]:
        """
        Extract function calls within template literals from JavaScript code.

        Args:
            source_code: JavaScript source code

        Returns:
            List of CallSite objects for template literal calls
        """
        call_sites = []

        try:
            # Find template literal calls using patterns
            template_calls = self.patterns.find_template_calls(source_code)

            for call_info in template_calls:
                try:
                    call_site = self._create_call_site_from_match(
                        call_info,
                        source_code,
                        "template",
                    )
                    if call_site:
                        call_sites.append(call_site)

                except Exception as e:
                    self.logger.warning(f"Error processing template call: {e}")
                    continue

        except Exception as e:
            self.logger.error(f"Error extracting template calls: {e}")

        return call_sites

    def _create_call_site_from_match(
        self,
        call_info: dict[str, Any],
        source_code: str,
        call_type: str,
    ) -> CallSite | None:
        """
        Create a CallSite object from pattern match information.

        Args:
            call_info: Dictionary containing match information
            source_code: Original source code
            call_type: Type of call (function, method, etc.)

        Returns:
            CallSite object or None if creation failed
        """
        try:
            function_name = call_info.get("name", "")
            if not function_name:
                return None

            start_pos = call_info.get("start", 0)
            end_pos = call_info.get("end", start_pos)

            # Calculate line and column
            line_number, column_number = ExtractionUtils.calculate_line_column(
                source_code,
                start_pos,
            )

            # Extract context
            context = call_info.get("context", {})
            context.update(self.patterns.extract_call_context(call_info, source_code))

            # Create CallSite
            call_site = CallSite(
                function_name=function_name,
                line_number=line_number,
                column_number=column_number,
                byte_start=start_pos,
                byte_end=end_pos,
                call_type=call_type,
                context=context,
                language=self.language,
                file_path=Path("unknown.js"),  # Will be set by caller
            )

            return call_site

        except Exception as e:
            self.logger.warning(f"Error creating CallSite: {e}")
            return None

    def _check_balanced_brackets(self, source_code: str) -> bool:
        """Check if brackets are balanced in the source code."""
        try:
            # Remove string literals and comments to avoid false positives
            cleaned_code = self._remove_strings_and_comments(source_code)

            brackets = {"(": ")", "[": "]", "{": "}"}
            stack = []

            for char in cleaned_code:
                if char in brackets:
                    stack.append(brackets[char])
                elif char in brackets.values():
                    if not stack or stack.pop() != char:
                        return False

            return len(stack) == 0

        except Exception:
            return True  # If we can't check, assume it's okay

    def _remove_strings_and_comments(self, source_code: str) -> str:
        """Remove string literals and comments from source code."""
        try:
            # Remove single line comments
            source_code = re.sub(r"//.*?$", "", source_code, flags=re.MULTILINE)

            # Remove multi-line comments
            source_code = re.sub(r"/\*.*?\*/", "", source_code, flags=re.DOTALL)

            # Remove string literals (simplified)
            source_code = re.sub(r'"([^"\\\\]|\\\\.)*"', '""', source_code)
            source_code = re.sub(r"'([^'\\\\]|\\\\.)*'", "''", source_code)
            source_code = re.sub(r"`([^`\\\\]|\\\\.)*`", "``", source_code)

            return source_code

        except Exception:
            return source_code

    def _deduplicate_calls(self, call_sites: list[CallSite]) -> list[CallSite]:
        """Remove duplicate call sites based on position and name."""
        seen = set()
        deduplicated = []

        for call_site in call_sites:
            key = (
                call_site.function_name,
                call_site.byte_start,
                call_site.byte_end,
                call_site.call_type,
            )
            if key not in seen:
                seen.add(key)
                deduplicated.append(call_site)

        return deduplicated

    def _validate_call_sites(self, result: ExtractionResult, source_code: str) -> None:
        """Validate extracted call sites and add warnings for invalid ones."""
        valid_calls = []

        for call_site in result.call_sites:
            validation_errors = ExtractionUtils.validate_call_site(
                call_site,
                source_code,
            )
            if validation_errors:
                result.add_warning(
                    f"Invalid call site {call_site.function_name}: {'; '.join(validation_errors)}",
                )
            else:
                valid_calls.append(call_site)

        result.call_sites = valid_calls


class JavaScriptPatterns:
    """JavaScript-specific pattern recognition using regex."""

    # Comprehensive regex patterns for JavaScript/TypeScript
    FUNCTION_CALL_PATTERNS = [
        # Basic function calls: func(), func(args)
        r"(?<![.\w])([a-zA-Z_$][a-zA-Z0-9_$]*)\s*\(",
        # Async function calls: await func()
        r"await\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\s*\(",
        # Function calls with complex expressions: func().then()
        r"([a-zA-Z_$][a-zA-Z0-9_$]*)\s*\([^)]*\)\s*\.",
        # Callback functions: setTimeout(func, 1000)
        r"([a-zA-Z_$][a-zA-Z0-9_$]*)\s*\([^)]*\b([a-zA-Z_$][a-zA-Z0-9_$]*)\b[^)]*\)",
    ]

    METHOD_CALL_PATTERNS = [
        # Basic method calls: obj.method(), obj.method(args)
        r"([a-zA-Z_$][a-zA-Z0-9_$]*(?:\.[a-zA-Z_$][a-zA-Z0-9_$]*)*?)\.([a-zA-Z_$][a-zA-Z0-9_$]*)\s*\(",
        # Optional chaining: obj?.method(), obj?.method?.()
        r"([a-zA-Z_$][a-zA-Z0-9_$]*(?:\??\.[a-zA-Z_$][a-zA-Z0-9_$]*)*?)\?\.([a-zA-Z_$][a-zA-Z0-9_$]*)\s*\(",
        # Array method calls: arr.map(), arr.filter()
        r"([a-zA-Z_$][a-zA-Z0-9_$]*)\s*\[\s*[^\]]*\s*\]\.([a-zA-Z_$][a-zA-Z0-9_$]*)\s*\(",
        # Chained method calls: obj.method1().method2()
        r"\.([a-zA-Z_$][a-zA-Z0-9_$]*)\s*\(",
    ]

    CONSTRUCTOR_PATTERNS = [
        # new expressions: new Class(), new Class(args)
        r"\bnew\s+([a-zA-Z_$][a-zA-Z0-9_$]*(?:\.[a-zA-Z_$][a-zA-Z0-9_$]*)*)\s*\(",
        # super() calls
        r"\bsuper\s*\(",
    ]

    JSX_PATTERNS = [
        # JSX component calls: <Component>, <Component />
        r"<([A-Z][a-zA-Z0-9_$]*)",
        # JSX with props: <Component prop={value}>
        r"<([A-Z][a-zA-Z0-9_$]*)\s+[^>]*>",
        # Self-closing JSX: <Component />
        r"<([A-Z][a-zA-Z0-9_$]*)\s*/>",
    ]

    TEMPLATE_LITERAL_PATTERNS = [
        # Function calls in template literals: `${func()}`
        r"`[^`]*\$\{[^}]*\b([a-zA-Z_$][a-zA-Z0-9_$]*)\s*\([^}]*\}[^`]*`",
        # Method calls in template literals: `${obj.method()}`
        r"`[^`]*\$\{[^}]*\b([a-zA-Z_$][a-zA-Z0-9_$]*\.[a-zA-Z_$][a-zA-Z0-9_$]*)\s*\([^}]*\}[^`]*`",
    ]

    @staticmethod
    def find_function_calls(source_code: str) -> list[dict[str, Any]]:
        """
        Find function calls using regex patterns.

        Args:
            source_code: JavaScript source code

        Returns:
            List of dictionaries containing function call information
        """
        calls = []

        try:
            # Remove comments and strings to avoid false matches
            cleaned_code = JavaScriptPatterns._clean_source_for_pattern_matching(
                source_code,
            )

            for pattern in JavaScriptPatterns.FUNCTION_CALL_PATTERNS:
                try:
                    for match in re.finditer(pattern, cleaned_code, re.MULTILINE):
                        if match.groups():
                            function_name = match.group(1).strip()
                            if (
                                function_name
                                and JavaScriptPatterns._is_valid_identifier(
                                    function_name,
                                )
                            ):
                                call_info = {
                                    "name": function_name,
                                    "start": match.start(),
                                    "end": match.end(),
                                    "full_match": match.group(0),
                                    "pattern": pattern,
                                    "context": {},
                                }
                                calls.append(call_info)

                except re.error as e:
                    logger.warning(f"Invalid regex pattern: {pattern}, error: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error finding function calls: {e}")

        return calls

    @staticmethod
    def find_method_calls(source_code: str) -> list[dict[str, Any]]:
        """
        Find method calls using regex patterns.

        Args:
            source_code: JavaScript source code

        Returns:
            List of dictionaries containing method call information
        """
        calls = []

        try:
            # Remove comments and strings to avoid false matches
            cleaned_code = JavaScriptPatterns._clean_source_for_pattern_matching(
                source_code,
            )

            for pattern in JavaScriptPatterns.METHOD_CALL_PATTERNS:
                try:
                    for match in re.finditer(pattern, cleaned_code, re.MULTILINE):
                        if match.groups():
                            if len(match.groups()) >= 2:
                                object_name = match.group(1).strip()
                                method_name = match.group(2).strip()
                                full_name = f"{object_name}.{method_name}"
                            else:
                                method_name = match.group(1).strip()
                                full_name = method_name

                            if method_name and JavaScriptPatterns._is_valid_identifier(
                                method_name,
                            ):
                                call_info = {
                                    "name": full_name,
                                    "method_name": method_name,
                                    "start": match.start(),
                                    "end": match.end(),
                                    "full_match": match.group(0),
                                    "pattern": pattern,
                                    "context": {
                                        "object_name": (
                                            object_name
                                            if len(match.groups()) >= 2
                                            else None
                                        ),
                                    },
                                }
                                calls.append(call_info)

                except re.error as e:
                    logger.warning(f"Invalid regex pattern: {pattern}, error: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error finding method calls: {e}")

        return calls

    @staticmethod
    def find_constructor_calls(source_code: str) -> list[dict[str, Any]]:
        """
        Find constructor calls using regex patterns.

        Args:
            source_code: JavaScript source code

        Returns:
            List of dictionaries containing constructor call information
        """
        calls = []

        try:
            # Remove comments and strings to avoid false matches
            cleaned_code = JavaScriptPatterns._clean_source_for_pattern_matching(
                source_code,
            )

            for pattern in JavaScriptPatterns.CONSTRUCTOR_PATTERNS:
                try:
                    for match in re.finditer(pattern, cleaned_code, re.MULTILINE):
                        if "super" in match.group(0):
                            constructor_name = "super"
                        elif match.groups():
                            constructor_name = match.group(1).strip()
                        else:
                            continue

                        if constructor_name and (
                            constructor_name == "super"
                            or JavaScriptPatterns._is_valid_identifier(constructor_name)
                        ):
                            call_info = {
                                "name": constructor_name,
                                "start": match.start(),
                                "end": match.end(),
                                "full_match": match.group(0),
                                "pattern": pattern,
                                "context": {
                                    "is_super_call": constructor_name == "super",
                                },
                            }
                            calls.append(call_info)

                except re.error as e:
                    logger.warning(f"Invalid regex pattern: {pattern}, error: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error finding constructor calls: {e}")

        return calls

    @staticmethod
    def find_jsx_calls(source_code: str) -> list[dict[str, Any]]:
        """
        Find JSX component calls using regex patterns.

        Args:
            source_code: JavaScript/TypeScript source code

        Returns:
            List of dictionaries containing JSX call information
        """
        calls = []

        try:
            # For JSX, we need to be more careful about cleaning
            # Only remove comments, not string literals since JSX attributes matter
            cleaned_code = JavaScriptPatterns._remove_comments_only(source_code)

            for pattern in JavaScriptPatterns.JSX_PATTERNS:
                try:
                    for match in re.finditer(pattern, cleaned_code, re.MULTILINE):
                        if match.groups():
                            component_name = match.group(1).strip()

                            if (
                                component_name
                                and JavaScriptPatterns._is_valid_jsx_component(
                                    component_name,
                                )
                            ):
                                call_info = {
                                    "name": component_name,
                                    "start": match.start(),
                                    "end": match.end(),
                                    "full_match": match.group(0),
                                    "pattern": pattern,
                                    "context": {
                                        "is_jsx": True,
                                        "is_self_closing": "/>" in match.group(0),
                                    },
                                }
                                calls.append(call_info)

                except re.error as e:
                    logger.warning(f"Invalid regex pattern: {pattern}, error: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error finding JSX calls: {e}")

        return calls

    @staticmethod
    def find_template_calls(source_code: str) -> list[dict[str, Any]]:
        """
        Find function calls within template literals using regex patterns.

        Args:
            source_code: JavaScript source code

        Returns:
            List of dictionaries containing template call information
        """
        calls = []

        try:
            for pattern in JavaScriptPatterns.TEMPLATE_LITERAL_PATTERNS:
                try:
                    for match in re.finditer(
                        pattern,
                        source_code,
                        re.MULTILINE | re.DOTALL,
                    ):
                        if match.groups():
                            function_name = match.group(1).strip()

                            # Handle method calls in templates
                            if "." in function_name:
                                method_parts = function_name.split(".")
                                display_name = method_parts[-1]
                            else:
                                display_name = function_name

                            if (
                                display_name
                                and JavaScriptPatterns._is_valid_identifier(
                                    display_name,
                                )
                            ):
                                call_info = {
                                    "name": function_name,
                                    "start": match.start(),
                                    "end": match.end(),
                                    "full_match": match.group(0),
                                    "pattern": pattern,
                                    "context": {
                                        "in_template_literal": True,
                                        "is_method_call": "." in function_name,
                                    },
                                }
                                calls.append(call_info)

                except re.error as e:
                    logger.warning(f"Invalid regex pattern: {pattern}, error: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error finding template calls: {e}")

        return calls

    @staticmethod
    def extract_call_context(
        call_info: dict[str, Any],
        source_code: str,
    ) -> dict[str, Any]:
        """
        Extract context information from JavaScript call match.

        Args:
            call_info: Dictionary containing match information
            source_code: Original source code

        Returns:
            Dictionary containing context information
        """
        context = {}

        try:
            start_pos = call_info.get("start", 0)
            end_pos = call_info.get("end", start_pos)
            full_match = call_info.get("full_match", "")

            # Extract surrounding context (50 characters before and after)
            context_start = max(0, start_pos - 50)
            context_end = min(len(source_code), end_pos + 50)
            surrounding_text = source_code[context_start:context_end]

            context["surrounding_text"] = surrounding_text.strip()
            context["match_text"] = full_match
            context["pattern_used"] = call_info.get("pattern", "")

            # Analyze the call for additional context
            if "async" in full_match or "await" in full_match:
                context["is_async"] = True

            if "=>" in surrounding_text:
                context["in_arrow_function"] = True

            if "function" in surrounding_text:
                context["in_function_definition"] = True

            if "class" in surrounding_text:
                context["in_class"] = True

            # Count parentheses to estimate argument complexity
            paren_count = full_match.count("(") - full_match.count(")")
            if paren_count != 0:
                context["unbalanced_parentheses"] = True

            # Check for optional chaining
            if "?." in full_match:
                context["uses_optional_chaining"] = True

            # Extract line context
            lines = source_code.split("\n")
            line_num, _ = ExtractionUtils.calculate_line_column(source_code, start_pos)
            if 1 <= line_num <= len(lines):
                context["line_text"] = lines[line_num - 1].strip()

        except Exception as e:
            logger.warning(f"Error extracting call context: {e}")
            context["extraction_error"] = str(e)

        return context

    @staticmethod
    def _clean_source_for_pattern_matching(source_code: str) -> str:
        """
        Clean source code for more accurate pattern matching.

        Args:
            source_code: Original source code

        Returns:
            Cleaned source code
        """
        try:
            # Remove single line comments
            cleaned = re.sub(r"//.*?$", "", source_code, flags=re.MULTILINE)

            # Remove multi-line comments
            cleaned = re.sub(r"/\*.*?\*/", "", cleaned, flags=re.DOTALL)

            # Remove string literals (but preserve structure)
            cleaned = re.sub(r'"([^"\\\\]|\\\\.)*"', '""', cleaned)
            cleaned = re.sub(r"'([^'\\\\]|\\\\.)*'", "''", cleaned)
            cleaned = re.sub(r"`([^`\\\\]|\\\\.)*`", "``", cleaned)

            # Remove regex literals
            cleaned = re.sub(r"/([^/\\\\]|\\\\.)+/[gimuy]*", "/regex/", cleaned)

            return cleaned

        except Exception as e:
            logger.warning(f"Error cleaning source code: {e}")
            return source_code

    @staticmethod
    def _remove_comments_only(source_code: str) -> str:
        """
        Remove only comments from source code, preserving strings.

        Args:
            source_code: Original source code

        Returns:
            Source code with comments removed
        """
        try:
            # Remove single line comments
            cleaned = re.sub(r"//.*?$", "", source_code, flags=re.MULTILINE)

            # Remove multi-line comments
            cleaned = re.sub(r"/\*.*?\*/", "", cleaned, flags=re.DOTALL)

            return cleaned

        except Exception as e:
            logger.warning(f"Error removing comments: {e}")
            return source_code

    @staticmethod
    def _is_valid_identifier(name: str) -> bool:
        """
        Check if a name is a valid JavaScript identifier.

        Args:
            name: Name to validate

        Returns:
            True if valid identifier
        """
        if not name or not isinstance(name, str):
            return False

        # JavaScript identifier pattern
        js_identifier_pattern = r"^[a-zA-Z_$][a-zA-Z0-9_$]*$"
        return bool(re.match(js_identifier_pattern, name))

    @staticmethod
    def _is_valid_jsx_component(name: str) -> bool:
        """
        Check if a name is a valid JSX component name.

        Args:
            name: Component name to validate

        Returns:
            True if valid JSX component name
        """
        if not name or not isinstance(name, str):
            return False

        # JSX component names must start with uppercase letter
        jsx_component_pattern = r"^[A-Z][a-zA-Z0-9_$]*$"
        return bool(re.match(jsx_component_pattern, name))

"""
Multi-language extractors for Phase 2 call site extraction.

This module provides specialized extractors for Go, C, C++, Java, and other languages
using regex-based pattern matching to identify function calls and method invocations.
"""

import logging
import re
import time
from pathlib import Path
from re import Pattern
from typing import Any, Dict, List, Optional, Tuple, Union

from ..core.extraction_framework import (
    BaseExtractor,
    CallSite,
    ExtractionResult,
    ExtractionUtils,
)

logger = logging.getLogger(__name__)


class GoExtractor(BaseExtractor):
    """Specialized extractor for Go source code."""

    def __init__(self):
        """Initialize Go extractor."""
        super().__init__("go")
        self.patterns = GoPatterns()

    def extract_calls(
        self,
        source_code: str,
        file_path: Path | None = None,
    ) -> ExtractionResult:
        """Extract call sites from Go source code."""
        if file_path is None:
            file_path = Path("unknown.go")

        result = ExtractionResult()
        start_time = time.perf_counter()

        try:
            self._validate_input(source_code, file_path)

            with self._measure_performance("go_extraction"):
                call_sites = []

                # Extract different types of calls
                call_sites.extend(self._extract_function_calls(source_code, file_path))
                call_sites.extend(self._extract_method_calls(source_code, file_path))
                call_sites.extend(self._extract_defer_calls(source_code, file_path))
                call_sites.extend(self._extract_goroutine_calls(source_code, file_path))
                call_sites.extend(self._extract_package_calls(source_code, file_path))

                result.call_sites = call_sites
                result.metadata = {
                    "language": self.language,
                    "file_path": str(file_path),
                    "total_calls": len(call_sites),
                    "extractor_type": "regex_based",
                    **ExtractionUtils.extract_file_metadata(file_path),
                }

        except Exception as e:
            result.add_error("Error extracting Go calls", e)

        result.extraction_time = time.perf_counter() - start_time
        result.performance_metrics = self.get_performance_metrics()

        return result

    def _extract_function_calls(
        self,
        source_code: str,
        file_path: Path,
    ) -> list[CallSite]:
        """Extract regular function calls."""
        calls = []

        for match in self.patterns.function_call_pattern.finditer(source_code):
            function_name = match.group(1).strip()
            if not function_name or function_name in self.patterns.go_keywords:
                continue

            line_num, col_num = ExtractionUtils.calculate_line_column(
                source_code,
                match.start(),
            )

            call_site = CallSite(
                function_name=function_name,
                line_number=line_num,
                column_number=col_num,
                byte_start=match.start(),
                byte_end=match.end(),
                call_type="function",
                context={"match_text": match.group(0).strip()[:100]},
                language=self.language,
                file_path=file_path,
            )
            calls.append(call_site)

        return calls

    def _extract_method_calls(
        self,
        source_code: str,
        file_path: Path,
    ) -> list[CallSite]:
        """Extract method calls on objects."""
        calls = []

        for match in self.patterns.method_call_pattern.finditer(source_code):
            method_name = match.group(2).strip()
            if not method_name or method_name in self.patterns.go_keywords:
                continue

            line_num, col_num = ExtractionUtils.calculate_line_column(
                source_code,
                match.start(),
            )

            call_site = CallSite(
                function_name=method_name,
                line_number=line_num,
                column_number=col_num,
                byte_start=match.start(),
                byte_end=match.end(),
                call_type="method",
                context={
                    "receiver": match.group(1).strip(),
                    "match_text": match.group(0).strip()[:100],
                },
                language=self.language,
                file_path=file_path,
            )
            calls.append(call_site)

        return calls

    def _extract_defer_calls(self, source_code: str, file_path: Path) -> list[CallSite]:
        """Extract defer statements."""
        calls = []

        for match in self.patterns.defer_pattern.finditer(source_code):
            function_name = match.group(1).strip()
            if not function_name or function_name in self.patterns.go_keywords:
                continue

            line_num, col_num = ExtractionUtils.calculate_line_column(
                source_code,
                match.start(),
            )

            call_site = CallSite(
                function_name=function_name,
                line_number=line_num,
                column_number=col_num,
                byte_start=match.start(),
                byte_end=match.end(),
                call_type="defer",
                context={"match_text": match.group(0).strip()[:100]},
                language=self.language,
                file_path=file_path,
            )
            calls.append(call_site)

        return calls

    def _extract_goroutine_calls(
        self,
        source_code: str,
        file_path: Path,
    ) -> list[CallSite]:
        """Extract goroutine calls."""
        calls = []

        for match in self.patterns.goroutine_pattern.finditer(source_code):
            function_name = match.group(1).strip()
            if not function_name or function_name in self.patterns.go_keywords:
                continue

            line_num, col_num = ExtractionUtils.calculate_line_column(
                source_code,
                match.start(),
            )

            call_site = CallSite(
                function_name=function_name,
                line_number=line_num,
                column_number=col_num,
                byte_start=match.start(),
                byte_end=match.end(),
                call_type="goroutine",
                context={"match_text": match.group(0).strip()[:100]},
                language=self.language,
                file_path=file_path,
            )
            calls.append(call_site)

        return calls

    def _extract_package_calls(
        self,
        source_code: str,
        file_path: Path,
    ) -> list[CallSite]:
        """Extract package function calls."""
        calls = []

        for match in self.patterns.package_call_pattern.finditer(source_code):
            function_name = match.group(2).strip()
            if not function_name or function_name in self.patterns.go_keywords:
                continue

            line_num, col_num = ExtractionUtils.calculate_line_column(
                source_code,
                match.start(),
            )

            call_site = CallSite(
                function_name=function_name,
                line_number=line_num,
                column_number=col_num,
                byte_start=match.start(),
                byte_end=match.end(),
                call_type="package_function",
                context={
                    "package": match.group(1).strip(),
                    "match_text": match.group(0).strip()[:100],
                },
                language=self.language,
                file_path=file_path,
            )
            calls.append(call_site)

        return calls

    def validate_source(self, source_code: str) -> bool:
        """Validate Go source code."""
        if not source_code or not isinstance(source_code, str):
            return False

        # Basic Go validation
        if not self.patterns.package_declaration.search(source_code):
            logger.warning("No package declaration found in Go source")
            return False

        # Check for balanced braces
        open_braces = source_code.count("{")
        close_braces = source_code.count("}")
        if abs(open_braces - close_braces) > 1:  # Allow small tolerance
            logger.warning("Unbalanced braces in Go source")
            return False

        return True


class CExtractor(BaseExtractor):
    """Specialized extractor for C source code."""

    def __init__(self):
        """Initialize C extractor."""
        super().__init__("c")
        self.patterns = CPatterns()

    def extract_calls(
        self,
        source_code: str,
        file_path: Path | None = None,
    ) -> ExtractionResult:
        """Extract call sites from C source code."""
        if file_path is None:
            file_path = Path("unknown.c")

        result = ExtractionResult()
        start_time = time.perf_counter()

        try:
            self._validate_input(source_code, file_path)

            with self._measure_performance("c_extraction"):
                call_sites = []

                # Extract different types of calls
                call_sites.extend(self._extract_function_calls(source_code, file_path))
                call_sites.extend(
                    self._extract_function_pointer_calls(source_code, file_path),
                )
                call_sites.extend(self._extract_macro_calls(source_code, file_path))
                call_sites.extend(
                    self._extract_struct_member_calls(source_code, file_path),
                )

                result.call_sites = call_sites
                result.metadata = {
                    "language": self.language,
                    "file_path": str(file_path),
                    "total_calls": len(call_sites),
                    "extractor_type": "regex_based",
                    **ExtractionUtils.extract_file_metadata(file_path),
                }

        except Exception as e:
            result.add_error("Error extracting C calls", e)

        result.extraction_time = time.perf_counter() - start_time
        result.performance_metrics = self.get_performance_metrics()

        return result

    def _extract_function_calls(
        self,
        source_code: str,
        file_path: Path,
    ) -> list[CallSite]:
        """Extract regular function calls."""
        calls = []

        for match in self.patterns.function_call_pattern.finditer(source_code):
            function_name = match.group(1).strip()
            if not function_name or function_name in self.patterns.c_keywords:
                continue

            line_num, col_num = ExtractionUtils.calculate_line_column(
                source_code,
                match.start(),
            )

            call_site = CallSite(
                function_name=function_name,
                line_number=line_num,
                column_number=col_num,
                byte_start=match.start(),
                byte_end=match.end(),
                call_type="function",
                context={"match_text": match.group(0).strip()[:100]},
                language=self.language,
                file_path=file_path,
            )
            calls.append(call_site)

        return calls

    def _extract_function_pointer_calls(
        self,
        source_code: str,
        file_path: Path,
    ) -> list[CallSite]:
        """Extract function pointer calls."""
        calls = []

        for match in self.patterns.function_pointer_pattern.finditer(source_code):
            pointer_name = match.group(1) or match.group(2)
            if not pointer_name:
                continue
            pointer_name = pointer_name.strip()
            if not pointer_name or pointer_name in self.patterns.c_keywords:
                continue

            line_num, col_num = ExtractionUtils.calculate_line_column(
                source_code,
                match.start(),
            )

            call_site = CallSite(
                function_name=pointer_name,
                line_number=line_num,
                column_number=col_num,
                byte_start=match.start(),
                byte_end=match.end(),
                call_type="function_pointer",
                context={"match_text": match.group(0).strip()[:100]},
                language=self.language,
                file_path=file_path,
            )
            calls.append(call_site)

        return calls

    def _extract_macro_calls(self, source_code: str, file_path: Path) -> list[CallSite]:
        """Extract macro calls."""
        calls = []

        for match in self.patterns.macro_call_pattern.finditer(source_code):
            macro_name = match.group(1).strip()
            if not macro_name or macro_name in self.patterns.c_keywords:
                continue

            line_num, col_num = ExtractionUtils.calculate_line_column(
                source_code,
                match.start(),
            )

            call_site = CallSite(
                function_name=macro_name,
                line_number=line_num,
                column_number=col_num,
                byte_start=match.start(),
                byte_end=match.end(),
                call_type="macro",
                context={"match_text": match.group(0).strip()[:100]},
                language=self.language,
                file_path=file_path,
            )
            calls.append(call_site)

        return calls

    def _extract_struct_member_calls(
        self,
        source_code: str,
        file_path: Path,
    ) -> list[CallSite]:
        """Extract struct member function calls."""
        calls = []

        for match in self.patterns.struct_member_pattern.finditer(source_code):
            member_name = match.group(2).strip()
            if not member_name or member_name in self.patterns.c_keywords:
                continue

            line_num, col_num = ExtractionUtils.calculate_line_column(
                source_code,
                match.start(),
            )

            call_site = CallSite(
                function_name=member_name,
                line_number=line_num,
                column_number=col_num,
                byte_start=match.start(),
                byte_end=match.end(),
                call_type="struct_member",
                context={
                    "struct_var": match.group(1).strip(),
                    "match_text": match.group(0).strip()[:100],
                },
                language=self.language,
                file_path=file_path,
            )
            calls.append(call_site)

        return calls

    def validate_source(self, source_code: str) -> bool:
        """Validate C source code."""
        if not source_code or not isinstance(source_code, str):
            return False

        # Basic C validation - check for includes or function definitions
        if not (
            self.patterns.include_pattern.search(source_code)
            or self.patterns.function_definition_pattern.search(source_code)
        ):
            logger.warning("No includes or function definitions found in C source")
            return False

        return True


class CppExtractor(BaseExtractor):
    """Specialized extractor for C++ source code."""

    def __init__(self):
        """Initialize C++ extractor."""
        super().__init__("cpp")
        self.patterns = CppPatterns()

    def extract_calls(
        self,
        source_code: str,
        file_path: Path | None = None,
    ) -> ExtractionResult:
        """Extract call sites from C++ source code."""
        if file_path is None:
            file_path = Path("unknown.cpp")

        result = ExtractionResult()
        start_time = time.perf_counter()

        try:
            self._validate_input(source_code, file_path)

            with self._measure_performance("cpp_extraction"):
                call_sites = []

                # Extract different types of calls
                call_sites.extend(self._extract_method_calls(source_code, file_path))
                call_sites.extend(
                    self._extract_static_method_calls(source_code, file_path),
                )
                call_sites.extend(self._extract_template_calls(source_code, file_path))
                call_sites.extend(self._extract_namespace_calls(source_code, file_path))
                call_sites.extend(
                    self._extract_constructor_calls(source_code, file_path),
                )
                call_sites.extend(self._extract_operator_calls(source_code, file_path))

                result.call_sites = call_sites
                result.metadata = {
                    "language": self.language,
                    "file_path": str(file_path),
                    "total_calls": len(call_sites),
                    "extractor_type": "regex_based",
                    **ExtractionUtils.extract_file_metadata(file_path),
                }

        except Exception as e:
            result.add_error("Error extracting C++ calls", e)

        result.extraction_time = time.perf_counter() - start_time
        result.performance_metrics = self.get_performance_metrics()

        return result

    def _extract_method_calls(
        self,
        source_code: str,
        file_path: Path,
    ) -> list[CallSite]:
        """Extract object method calls."""
        calls = []

        for match in self.patterns.method_call_pattern.finditer(source_code):
            method_name = match.group(2).strip()
            if not method_name or method_name in self.patterns.cpp_keywords:
                continue

            line_num, col_num = ExtractionUtils.calculate_line_column(
                source_code,
                match.start(),
            )

            call_site = CallSite(
                function_name=method_name,
                line_number=line_num,
                column_number=col_num,
                byte_start=match.start(),
                byte_end=match.end(),
                call_type="method",
                context={
                    "object": match.group(1).strip(),
                    "match_text": match.group(0).strip()[:100],
                },
                language=self.language,
                file_path=file_path,
            )
            calls.append(call_site)

        return calls

    def _extract_static_method_calls(
        self,
        source_code: str,
        file_path: Path,
    ) -> list[CallSite]:
        """Extract static method calls."""
        calls = []

        for match in self.patterns.static_method_pattern.finditer(source_code):
            method_name = match.group(2).strip()
            if not method_name or method_name in self.patterns.cpp_keywords:
                continue

            line_num, col_num = ExtractionUtils.calculate_line_column(
                source_code,
                match.start(),
            )

            call_site = CallSite(
                function_name=method_name,
                line_number=line_num,
                column_number=col_num,
                byte_start=match.start(),
                byte_end=match.end(),
                call_type="static_method",
                context={
                    "class": match.group(1).strip(),
                    "match_text": match.group(0).strip()[:100],
                },
                language=self.language,
                file_path=file_path,
            )
            calls.append(call_site)

        return calls

    def _extract_template_calls(
        self,
        source_code: str,
        file_path: Path,
    ) -> list[CallSite]:
        """Extract template function calls."""
        calls = []

        for match in self.patterns.template_call_pattern.finditer(source_code):
            function_name = match.group(1).strip()
            if not function_name or function_name in self.patterns.cpp_keywords:
                continue

            line_num, col_num = ExtractionUtils.calculate_line_column(
                source_code,
                match.start(),
            )

            call_site = CallSite(
                function_name=function_name,
                line_number=line_num,
                column_number=col_num,
                byte_start=match.start(),
                byte_end=match.end(),
                call_type="template_function",
                context={"match_text": match.group(0).strip()[:100]},
                language=self.language,
                file_path=file_path,
            )
            calls.append(call_site)

        return calls

    def _extract_namespace_calls(
        self,
        source_code: str,
        file_path: Path,
    ) -> list[CallSite]:
        """Extract namespace function calls."""
        calls = []

        for match in self.patterns.namespace_call_pattern.finditer(source_code):
            function_name = match.group(2).strip()
            if not function_name or function_name in self.patterns.cpp_keywords:
                continue

            line_num, col_num = ExtractionUtils.calculate_line_column(
                source_code,
                match.start(),
            )

            call_site = CallSite(
                function_name=function_name,
                line_number=line_num,
                column_number=col_num,
                byte_start=match.start(),
                byte_end=match.end(),
                call_type="namespace_function",
                context={
                    "namespace": match.group(1).strip(),
                    "match_text": match.group(0).strip()[:100],
                },
                language=self.language,
                file_path=file_path,
            )
            calls.append(call_site)

        return calls

    def _extract_constructor_calls(
        self,
        source_code: str,
        file_path: Path,
    ) -> list[CallSite]:
        """Extract constructor calls."""
        calls = []

        for match in self.patterns.constructor_pattern.finditer(source_code):
            class_name = match.group(1).strip()
            if not class_name or class_name in self.patterns.cpp_keywords:
                continue

            line_num, col_num = ExtractionUtils.calculate_line_column(
                source_code,
                match.start(),
            )

            call_site = CallSite(
                function_name=class_name,
                line_number=line_num,
                column_number=col_num,
                byte_start=match.start(),
                byte_end=match.end(),
                call_type="constructor",
                context={"match_text": match.group(0).strip()[:100]},
                language=self.language,
                file_path=file_path,
            )
            calls.append(call_site)

        return calls

    def _extract_operator_calls(
        self,
        source_code: str,
        file_path: Path,
    ) -> list[CallSite]:
        """Extract operator overload calls."""
        calls = []

        for match in self.patterns.operator_call_pattern.finditer(source_code):
            operator_name = f"operator{match.group(1).strip()}"

            line_num, col_num = ExtractionUtils.calculate_line_column(
                source_code,
                match.start(),
            )

            call_site = CallSite(
                function_name=operator_name,
                line_number=line_num,
                column_number=col_num,
                byte_start=match.start(),
                byte_end=match.end(),
                call_type="operator",
                context={"match_text": match.group(0).strip()[:100]},
                language=self.language,
                file_path=file_path,
            )
            calls.append(call_site)

        return calls

    def validate_source(self, source_code: str) -> bool:
        """Validate C++ source code."""
        if not source_code or not isinstance(source_code, str):
            return False

        # Basic C++ validation - check for includes, namespaces, or classes
        if not (
            self.patterns.include_pattern.search(source_code)
            or self.patterns.namespace_pattern.search(source_code)
            or self.patterns.class_pattern.search(source_code)
        ):
            logger.warning("No C++ constructs found in source")
            return False

        return True


class JavaExtractor(BaseExtractor):
    """Specialized extractor for Java source code."""

    def __init__(self):
        """Initialize Java extractor."""
        super().__init__("java")
        self.patterns = JavaPatterns()

    def extract_calls(
        self,
        source_code: str,
        file_path: Path | None = None,
    ) -> ExtractionResult:
        """Extract call sites from Java source code."""
        if file_path is None:
            file_path = Path("unknown.java")

        result = ExtractionResult()
        start_time = time.perf_counter()

        try:
            self._validate_input(source_code, file_path)

            with self._measure_performance("java_extraction"):
                call_sites = []

                # Extract different types of calls
                call_sites.extend(self._extract_method_calls(source_code, file_path))
                call_sites.extend(
                    self._extract_static_method_calls(source_code, file_path),
                )
                call_sites.extend(
                    self._extract_constructor_calls(source_code, file_path),
                )
                call_sites.extend(self._extract_super_calls(source_code, file_path))
                call_sites.extend(self._extract_this_calls(source_code, file_path))
                call_sites.extend(self._extract_lambda_calls(source_code, file_path))

                result.call_sites = call_sites
                result.metadata = {
                    "language": self.language,
                    "file_path": str(file_path),
                    "total_calls": len(call_sites),
                    "extractor_type": "regex_based",
                    **ExtractionUtils.extract_file_metadata(file_path),
                }

        except Exception as e:
            result.add_error("Error extracting Java calls", e)

        result.extraction_time = time.perf_counter() - start_time
        result.performance_metrics = self.get_performance_metrics()

        return result

    def _extract_method_calls(
        self,
        source_code: str,
        file_path: Path,
    ) -> list[CallSite]:
        """Extract object method calls."""
        calls = []

        for match in self.patterns.method_call_pattern.finditer(source_code):
            method_name = match.group(2).strip()
            if not method_name or method_name in self.patterns.java_keywords:
                continue

            line_num, col_num = ExtractionUtils.calculate_line_column(
                source_code,
                match.start(),
            )

            call_site = CallSite(
                function_name=method_name,
                line_number=line_num,
                column_number=col_num,
                byte_start=match.start(),
                byte_end=match.end(),
                call_type="method",
                context={
                    "object": match.group(1).strip(),
                    "match_text": match.group(0).strip()[:100],
                },
                language=self.language,
                file_path=file_path,
            )
            calls.append(call_site)

        return calls

    def _extract_static_method_calls(
        self,
        source_code: str,
        file_path: Path,
    ) -> list[CallSite]:
        """Extract static method calls."""
        calls = []

        for match in self.patterns.static_method_pattern.finditer(source_code):
            method_name = match.group(2).strip()
            if not method_name or method_name in self.patterns.java_keywords:
                continue

            line_num, col_num = ExtractionUtils.calculate_line_column(
                source_code,
                match.start(),
            )

            call_site = CallSite(
                function_name=method_name,
                line_number=line_num,
                column_number=col_num,
                byte_start=match.start(),
                byte_end=match.end(),
                call_type="static_method",
                context={
                    "class": match.group(1).strip(),
                    "match_text": match.group(0).strip()[:100],
                },
                language=self.language,
                file_path=file_path,
            )
            calls.append(call_site)

        return calls

    def _extract_constructor_calls(
        self,
        source_code: str,
        file_path: Path,
    ) -> list[CallSite]:
        """Extract constructor calls."""
        calls = []

        for match in self.patterns.constructor_pattern.finditer(source_code):
            class_name = match.group(1).strip()
            if not class_name or class_name in self.patterns.java_keywords:
                continue

            line_num, col_num = ExtractionUtils.calculate_line_column(
                source_code,
                match.start(),
            )

            call_site = CallSite(
                function_name=class_name,
                line_number=line_num,
                column_number=col_num,
                byte_start=match.start(),
                byte_end=match.end(),
                call_type="constructor",
                context={"match_text": match.group(0).strip()[:100]},
                language=self.language,
                file_path=file_path,
            )
            calls.append(call_site)

        return calls

    def _extract_super_calls(self, source_code: str, file_path: Path) -> list[CallSite]:
        """Extract super() calls."""
        calls = []

        for match in self.patterns.super_call_pattern.finditer(source_code):
            method_name = match.group(1).strip() if match.group(1) else "super"

            line_num, col_num = ExtractionUtils.calculate_line_column(
                source_code,
                match.start(),
            )

            call_site = CallSite(
                function_name=method_name,
                line_number=line_num,
                column_number=col_num,
                byte_start=match.start(),
                byte_end=match.end(),
                call_type="super_call",
                context={"match_text": match.group(0).strip()[:100]},
                language=self.language,
                file_path=file_path,
            )
            calls.append(call_site)

        return calls

    def _extract_this_calls(self, source_code: str, file_path: Path) -> list[CallSite]:
        """Extract this() calls."""
        calls = []

        for match in self.patterns.this_call_pattern.finditer(source_code):
            method_name = match.group(1).strip() if match.group(1) else "this"

            line_num, col_num = ExtractionUtils.calculate_line_column(
                source_code,
                match.start(),
            )

            call_site = CallSite(
                function_name=method_name,
                line_number=line_num,
                column_number=col_num,
                byte_start=match.start(),
                byte_end=match.end(),
                call_type="this_call",
                context={"match_text": match.group(0).strip()[:100]},
                language=self.language,
                file_path=file_path,
            )
            calls.append(call_site)

        return calls

    def _extract_lambda_calls(
        self,
        source_code: str,
        file_path: Path,
    ) -> list[CallSite]:
        """Extract lambda expression calls."""
        calls = []

        for match in self.patterns.lambda_call_pattern.finditer(source_code):
            method_name = match.group(1).strip()
            if not method_name or method_name in self.patterns.java_keywords:
                continue

            line_num, col_num = ExtractionUtils.calculate_line_column(
                source_code,
                match.start(),
            )

            call_site = CallSite(
                function_name=method_name,
                line_number=line_num,
                column_number=col_num,
                byte_start=match.start(),
                byte_end=match.end(),
                call_type="lambda",
                context={"match_text": match.group(0).strip()[:100]},
                language=self.language,
                file_path=file_path,
            )
            calls.append(call_site)

        return calls

    def validate_source(self, source_code: str) -> bool:
        """Validate Java source code."""
        if not source_code or not isinstance(source_code, str):
            return False

        # Basic Java validation - check for package, class, or interface
        if not (
            self.patterns.package_pattern.search(source_code)
            or self.patterns.class_pattern.search(source_code)
            or self.patterns.interface_pattern.search(source_code)
        ):
            logger.warning("No Java constructs found in source")
            return False

        return True


class OtherLanguagesExtractor(BaseExtractor):
    """Generic extractor for other supported languages."""

    def __init__(self, language: str):
        """Initialize generic extractor for specified language."""
        super().__init__(language)
        self.patterns = GenericPatterns()

    def extract_calls(
        self,
        source_code: str,
        file_path: Path | None = None,
    ) -> ExtractionResult:
        """Extract call sites using generic patterns."""
        if file_path is None:
            file_path = Path(f"unknown.{self.language}")

        result = ExtractionResult()
        start_time = time.perf_counter()

        try:
            self._validate_input(source_code, file_path)

            with self._measure_performance("generic_extraction"):
                call_sites = []

                # Extract different types of calls using generic patterns
                call_sites.extend(self._extract_function_calls(source_code, file_path))
                call_sites.extend(self._extract_method_calls(source_code, file_path))
                call_sites.extend(self._extract_dotted_calls(source_code, file_path))

                result.call_sites = call_sites
                result.metadata = {
                    "language": self.language,
                    "file_path": str(file_path),
                    "total_calls": len(call_sites),
                    "extractor_type": "generic_regex",
                    **ExtractionUtils.extract_file_metadata(file_path),
                }

        except Exception as e:
            result.add_error(f"Error extracting {self.language} calls", e)

        result.extraction_time = time.perf_counter() - start_time
        result.performance_metrics = self.get_performance_metrics()

        return result

    def _extract_function_calls(
        self,
        source_code: str,
        file_path: Path,
    ) -> list[CallSite]:
        """Extract generic function calls."""
        calls = []

        for match in self.patterns.function_call_pattern.finditer(source_code):
            function_name = match.group(1).strip()
            if not function_name:
                continue

            line_num, col_num = ExtractionUtils.calculate_line_column(
                source_code,
                match.start(),
            )

            call_site = CallSite(
                function_name=function_name,
                line_number=line_num,
                column_number=col_num,
                byte_start=match.start(),
                byte_end=match.end(),
                call_type="function",
                context={"match_text": match.group(0).strip()[:100]},
                language=self.language,
                file_path=file_path,
            )
            calls.append(call_site)

        return calls

    def _extract_method_calls(
        self,
        source_code: str,
        file_path: Path,
    ) -> list[CallSite]:
        """Extract generic method calls."""
        calls = []

        for match in self.patterns.method_call_pattern.finditer(source_code):
            method_name = match.group(2).strip()
            if not method_name:
                continue

            line_num, col_num = ExtractionUtils.calculate_line_column(
                source_code,
                match.start(),
            )

            call_site = CallSite(
                function_name=method_name,
                line_number=line_num,
                column_number=col_num,
                byte_start=match.start(),
                byte_end=match.end(),
                call_type="method",
                context={
                    "object": match.group(1).strip(),
                    "match_text": match.group(0).strip()[:100],
                },
                language=self.language,
                file_path=file_path,
            )
            calls.append(call_site)

        return calls

    def _extract_dotted_calls(
        self,
        source_code: str,
        file_path: Path,
    ) -> list[CallSite]:
        """Extract dotted notation calls."""
        calls = []

        for match in self.patterns.dotted_call_pattern.finditer(source_code):
            function_name = match.group(2).strip()
            if not function_name:
                continue

            line_num, col_num = ExtractionUtils.calculate_line_column(
                source_code,
                match.start(),
            )

            call_site = CallSite(
                function_name=function_name,
                line_number=line_num,
                column_number=col_num,
                byte_start=match.start(),
                byte_end=match.end(),
                call_type="dotted_call",
                context={
                    "module": match.group(1).strip(),
                    "match_text": match.group(0).strip()[:100],
                },
                language=self.language,
                file_path=file_path,
            )
            calls.append(call_site)

        return calls

    def validate_source(self, source_code: str) -> bool:
        """Validate source code using generic patterns."""
        if not source_code or not isinstance(source_code, str):
            return False

        # Generic validation - just check for some identifiers and function-like patterns
        if not (
            self.patterns.identifier_pattern.search(source_code)
            and (
                self.patterns.function_call_pattern.search(source_code)
                or self.patterns.method_call_pattern.search(source_code)
            )
        ):
            logger.warning(f"No recognizable {self.language} patterns found in source")
            return False

        return True


# Pattern classes for each language


class GoPatterns:
    """Go-specific pattern recognition."""

    def __init__(self):
        """Initialize Go patterns."""
        # Go function call: functionName(args)
        self.function_call_pattern = re.compile(
            r"\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\(",
            re.MULTILINE,
        )

        # Go method call: obj.methodName(args)
        self.method_call_pattern = re.compile(
            r"([a-zA-Z_][a-zA-Z0-9_]*)\s*\.\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\(",
            re.MULTILINE,
        )

        # Defer statements: defer funcName(args)
        self.defer_pattern = re.compile(
            r"\bdefer\s+([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*)\s*\(",
            re.MULTILINE,
        )

        # Goroutine calls: go funcName(args)
        self.goroutine_pattern = re.compile(
            r"\bgo\s+([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*)\s*\(",
            re.MULTILINE,
        )

        # Package function calls: pkg.Function(args)
        self.package_call_pattern = re.compile(
            r"([a-zA-Z_][a-zA-Z0-9_]*)\s*\.\s*([A-Z][a-zA-Z0-9_]*)\s*\(",
            re.MULTILINE,
        )

        # Package declaration
        self.package_declaration = re.compile(
            r"^\s*package\s+[a-zA-Z_][a-zA-Z0-9_]*",
            re.MULTILINE,
        )

        # Go keywords to exclude
        self.go_keywords = {
            "if",
            "else",
            "for",
            "range",
            "switch",
            "case",
            "default",
            "func",
            "var",
            "const",
            "type",
            "struct",
            "interface",
            "package",
            "import",
            "return",
            "break",
            "continue",
            "go",
            "defer",
            "chan",
            "select",
            "map",
        }


class CPatterns:
    """C-specific pattern recognition."""

    def __init__(self):
        """Initialize C patterns."""
        # C function call: functionName(args)
        self.function_call_pattern = re.compile(
            r"(?<!\w)([a-zA-Z_][a-zA-Z0-9_]*)\s*\(",
            re.MULTILINE,
        )

        # Function pointer calls: (*ptr)(args) or ptr(args)
        self.function_pointer_pattern = re.compile(
            r"(?:\(\s*\*\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\)|([a-zA-Z_][a-zA-Z0-9_]*(?:_ptr|_fn)))\s*\(",
            re.MULTILINE,
        )

        # Macro calls: MACRO_NAME(args)
        self.macro_call_pattern = re.compile(r"\b([A-Z_][A-Z0-9_]*)\s*\(", re.MULTILINE)

        # Struct member access: struct.member(args) or struct->member(args)
        self.struct_member_pattern = re.compile(
            r"([a-zA-Z_][a-zA-Z0-9_]*)\s*(?:\.|->)\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\(",
            re.MULTILINE,
        )

        # Include statements
        self.include_pattern = re.compile(r'^\s*#include\s*[<"]', re.MULTILINE)

        # Function definitions
        self.function_definition_pattern = re.compile(
            r"\b[a-zA-Z_][a-zA-Z0-9_*\s]*\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\([^)]*\)\s*{",
            re.MULTILINE,
        )

        # C keywords to exclude
        self.c_keywords = {
            "if",
            "else",
            "for",
            "while",
            "do",
            "switch",
            "case",
            "default",
            "return",
            "break",
            "continue",
            "goto",
            "int",
            "char",
            "float",
            "double",
            "void",
            "long",
            "short",
            "signed",
            "unsigned",
            "const",
            "volatile",
            "static",
            "extern",
            "auto",
            "register",
            "struct",
            "union",
            "enum",
            "typedef",
            "sizeof",
            "malloc",
            "free",
            "printf",
            "scanf",
        }


class CppPatterns:
    """C++-specific pattern recognition."""

    def __init__(self):
        """Initialize C++ patterns."""
        # Method calls: obj.method(args)
        self.method_call_pattern = re.compile(
            r"([a-zA-Z_][a-zA-Z0-9_]*)\s*\.\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\(",
            re.MULTILINE,
        )

        # Static method calls: Class::method(args)
        self.static_method_pattern = re.compile(
            r"([a-zA-Z_][a-zA-Z0-9_]*)\s*::\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\(",
            re.MULTILINE,
        )

        # Template function calls: func<Type>(args)
        self.template_call_pattern = re.compile(
            r"([a-zA-Z_][a-zA-Z0-9_]*)\s*<[^>]+>\s*\(",
            re.MULTILINE,
        )

        # Namespace function calls: namespace::func(args)
        self.namespace_call_pattern = re.compile(
            r"([a-zA-Z_][a-zA-Z0-9_]*)\s*::\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\(",
            re.MULTILINE,
        )

        # Constructor calls: new ClassName(args) or ClassName(args)
        self.constructor_pattern = re.compile(
            r"(?:\bnew\s+)?([A-Z][a-zA-Z0-9_]*)\s*\(",
            re.MULTILINE,
        )

        # Operator calls: operator+(args)
        self.operator_call_pattern = re.compile(
            r"\boperator\s*([+\-*/=<>!&|^%]+)\s*\(",
            re.MULTILINE,
        )

        # Include statements
        self.include_pattern = re.compile(r'^\s*#include\s*[<"]', re.MULTILINE)

        # Namespace declarations
        self.namespace_pattern = re.compile(
            r"^\s*namespace\s+[a-zA-Z_][a-zA-Z0-9_]*",
            re.MULTILINE,
        )

        # Class declarations
        self.class_pattern = re.compile(
            r"^\s*class\s+[a-zA-Z_][a-zA-Z0-9_]*",
            re.MULTILINE,
        )

        # C++ keywords to exclude
        self.cpp_keywords = {
            "if",
            "else",
            "for",
            "while",
            "do",
            "switch",
            "case",
            "default",
            "return",
            "break",
            "continue",
            "goto",
            "try",
            "catch",
            "throw",
            "int",
            "char",
            "float",
            "double",
            "void",
            "long",
            "short",
            "bool",
            "signed",
            "unsigned",
            "const",
            "volatile",
            "static",
            "extern",
            "auto",
            "register",
            "mutable",
            "inline",
            "virtual",
            "explicit",
            "class",
            "struct",
            "union",
            "enum",
            "namespace",
            "using",
            "template",
            "typename",
            "public",
            "private",
            "protected",
            "new",
            "delete",
            "this",
            "operator",
            "friend",
            "sizeof",
        }


class JavaPatterns:
    """Java-specific pattern recognition."""

    def __init__(self):
        """Initialize Java patterns."""
        # Method calls: obj.method(args)
        self.method_call_pattern = re.compile(
            r"([a-zA-Z_][a-zA-Z0-9_]*)\s*\.\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\(",
            re.MULTILINE,
        )

        # Static method calls: Class.method(args)
        self.static_method_pattern = re.compile(
            r"([A-Z][a-zA-Z0-9_]*)\s*\.\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\(",
            re.MULTILINE,
        )

        # Constructor calls: new ClassName(args)
        self.constructor_pattern = re.compile(
            r"\bnew\s+([A-Z][a-zA-Z0-9_]*)\s*\(",
            re.MULTILINE,
        )

        # Super calls: super.method(args) or super(args)
        self.super_call_pattern = re.compile(
            r"\bsuper\s*(?:\.\s*([a-zA-Z_][a-zA-Z0-9_]*))?\s*\(",
            re.MULTILINE,
        )

        # This calls: this.method(args) or this(args)
        self.this_call_pattern = re.compile(
            r"\bthis\s*(?:\.\s*([a-zA-Z_][a-zA-Z0-9_]*))?\s*\(",
            re.MULTILINE,
        )

        # Lambda expressions with method calls: (args) -> methodCall(args)
        self.lambda_call_pattern = re.compile(
            r"->\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\(",
            re.MULTILINE,
        )

        # Package declarations
        self.package_pattern = re.compile(
            r"^\s*package\s+[a-zA-Z_][a-zA-Z0-9_.]*",
            re.MULTILINE,
        )

        # Class declarations
        self.class_pattern = re.compile(
            r"^\s*(?:public\s+)?class\s+[a-zA-Z_][a-zA-Z0-9_]*",
            re.MULTILINE,
        )

        # Interface declarations
        self.interface_pattern = re.compile(
            r"^\s*(?:public\s+)?interface\s+[a-zA-Z_][a-zA-Z0-9_]*",
            re.MULTILINE,
        )

        # Java keywords to exclude
        self.java_keywords = {
            "if",
            "else",
            "for",
            "while",
            "do",
            "switch",
            "case",
            "default",
            "return",
            "break",
            "continue",
            "try",
            "catch",
            "finally",
            "throw",
            "throws",
            "int",
            "char",
            "float",
            "double",
            "void",
            "long",
            "short",
            "byte",
            "boolean",
            "final",
            "static",
            "public",
            "private",
            "protected",
            "abstract",
            "class",
            "interface",
            "enum",
            "extends",
            "implements",
            "import",
            "package",
            "new",
            "this",
            "super",
            "instanceof",
            "synchronized",
            "volatile",
            "transient",
            "native",
            "strictfp",
            "assert",
            "ArrayList",
            "String",
            "Object",
            "System",
        }


class GenericPatterns:
    """Generic pattern recognition for other languages."""

    def __init__(self):
        """Initialize generic patterns."""
        # Generic function call: functionName(args)
        self.function_call_pattern = re.compile(
            r"\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\(",
            re.MULTILINE,
        )

        # Generic method call: obj.method(args)
        self.method_call_pattern = re.compile(
            r"([a-zA-Z_][a-zA-Z0-9_]*)\s*\.\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\(",
            re.MULTILINE,
        )

        # Dotted calls: module.function(args) - same as method calls for generic patterns
        self.dotted_call_pattern = re.compile(
            r"([a-zA-Z_][a-zA-Z0-9_]*)\s*\.\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\(",
            re.MULTILINE,
        )

        # Generic identifier pattern
        self.identifier_pattern = re.compile(
            r"\b[a-zA-Z_][a-zA-Z0-9_]*\b",
            re.MULTILINE,
        )

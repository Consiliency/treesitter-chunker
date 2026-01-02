"""
Core extraction framework for Phase 2 call site extraction.

This module provides the foundational classes and utilities for extracting
function call sites from source code across multiple programming languages.
"""

import logging
import re
import time
import traceback
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, Tuple, Union

logger = logging.getLogger(__name__)


@dataclass
class CallSite:
    """Represents a call site with precise location information."""

    function_name: str
    line_number: int
    column_number: int
    byte_start: int
    byte_end: int
    call_type: str  # 'function', 'method', 'constructor', etc.
    context: dict[str, Any]
    language: str
    file_path: Path

    def __post_init__(self):
        """Validate CallSite data after initialization."""
        if not self.function_name:
            raise ValueError("function_name cannot be empty")
        if self.line_number < 1:
            raise ValueError("line_number must be >= 1")
        if self.column_number < 0:
            raise ValueError("column_number must be >= 0")
        if self.byte_start < 0:
            raise ValueError("byte_start must be >= 0")
        if self.byte_end < self.byte_start:
            raise ValueError("byte_end must be >= byte_start")
        if not self.language:
            raise ValueError("language cannot be empty")
        if not self.call_type:
            raise ValueError("call_type cannot be empty")

        # Ensure file_path is a Path object
        if isinstance(self.file_path, str):
            self.file_path = Path(self.file_path)

    def to_dict(self) -> dict[str, Any]:
        """Convert CallSite to dictionary for serialization."""
        return {
            "function_name": self.function_name,
            "line_number": self.line_number,
            "column_number": self.column_number,
            "byte_start": self.byte_start,
            "byte_end": self.byte_end,
            "call_type": self.call_type,
            "context": self.context,
            "language": self.language,
            "file_path": str(self.file_path),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CallSite":
        """Create CallSite from dictionary."""
        return cls(
            function_name=data["function_name"],
            line_number=data["line_number"],
            column_number=data["column_number"],
            byte_start=data["byte_start"],
            byte_end=data["byte_end"],
            call_type=data["call_type"],
            context=data["context"],
            language=data["language"],
            file_path=Path(data["file_path"]),
        )


@dataclass
class ExtractionResult:
    """Standardized result for all language extractors."""

    call_sites: list[CallSite] = field(default_factory=list)
    extraction_time: float = 0.0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    performance_metrics: dict[str, Any] = field(default_factory=dict)

    def add_error(self, error: str, exception: Exception | None = None) -> None:
        """Add an error to the result."""
        if exception:
            error_msg = f"{error}: {exception!s}"
            logger.error(error_msg)
        else:
            error_msg = error
            logger.error(error_msg)

        self.errors.append(error_msg)

    def add_warning(self, warning: str) -> None:
        """Add a warning to the result."""
        logger.warning(warning)
        self.warnings.append(warning)

    def is_successful(self) -> bool:
        """Check if extraction was successful (no errors)."""
        return len(self.errors) == 0

    def get_call_count(self) -> int:
        """Get total number of call sites found."""
        return len(self.call_sites)

    def get_calls_by_type(self) -> dict[str, list[CallSite]]:
        """Group call sites by call type."""
        result = {}
        for call_site in self.call_sites:
            call_type = call_site.call_type
            if call_type not in result:
                result[call_type] = []
            result[call_type].append(call_site)
        return result

    def to_dict(self) -> dict[str, Any]:
        """Convert ExtractionResult to dictionary for serialization."""
        return {
            "call_sites": [cs.to_dict() for cs in self.call_sites],
            "extraction_time": self.extraction_time,
            "errors": self.errors,
            "warnings": self.warnings,
            "metadata": self.metadata,
            "performance_metrics": self.performance_metrics,
        }


class BaseExtractor(ABC):
    """Abstract base class for all language-specific extractors."""

    def __init__(self, language: str):
        """Initialize the extractor for a specific language."""
        if not language:
            raise ValueError("language cannot be empty")

        self.language = language.lower()
        self.logger = logging.getLogger(f"{__name__}.{self.language}")
        self.performance_metrics = {}
        self._parser = None
        self._is_initialized = False

        self.logger.debug(f"Initialized {self.language} extractor")

    @abstractmethod
    def extract_calls(
        self,
        source_code: str,
        file_path: Path | None = None,
    ) -> ExtractionResult:
        """
        Extract call sites from source code.

        Args:
            source_code: The source code to analyze
            file_path: Optional path to the source file

        Returns:
            ExtractionResult containing found call sites and metadata
        """

    @abstractmethod
    def validate_source(self, source_code: str) -> bool:
        """
        Validate source code for the language.

        Args:
            source_code: The source code to validate

        Returns:
            True if valid, False otherwise
        """

    def get_performance_metrics(self) -> dict[str, Any]:
        """Get performance metrics for the extractor."""
        return self.performance_metrics.copy()

    def cleanup(self) -> None:
        """Clean up resources used by the extractor."""
        if self._parser:
            try:
                # Clean up parser resources
                self._parser = None
                self.logger.debug(f"Cleaned up {self.language} extractor resources")
            except Exception as e:
                self.logger.warning(f"Error during cleanup: {e}")

        self._is_initialized = False

    def _measure_performance(self, operation: str) -> "PerformanceContext":
        """Context manager for measuring operation performance."""
        return PerformanceContext(self, operation)

    def _safe_extract(self, func: Callable, *args, **kwargs) -> Any:
        """Safely execute extraction function with error handling."""
        try:
            return func(*args, **kwargs)
        except Exception as e:
            self.logger.error(f"Error in {func.__name__}: {e}", exc_info=True)
            raise

    def _validate_input(
        self,
        source_code: str,
        file_path: Path | None = None,
    ) -> None:
        """Validate input parameters."""
        if not isinstance(source_code, str):
            raise TypeError("source_code must be a string")

        if source_code.strip() == "":
            raise ValueError("source_code cannot be empty")

        if file_path is not None and not isinstance(file_path, (str, Path)):
            raise TypeError("file_path must be a string or Path object")


class PerformanceContext:
    """Context manager for measuring operation performance."""

    def __init__(self, extractor: BaseExtractor, operation: str):
        self.extractor = extractor
        self.operation = operation
        self.start_time = None

    def __enter__(self):
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time is not None:
            duration = time.perf_counter() - self.start_time
            self.extractor.performance_metrics[self.operation] = duration


class CommonPatterns:
    """Common pattern recognition utilities for all extractors."""

    @staticmethod
    def is_function_call(node: Any) -> bool:
        """
        Check if AST node represents a function call.

        Args:
            node: AST node to check

        Returns:
            True if node represents a function call
        """
        if not hasattr(node, "type"):
            return False

        # Common function call node types across languages
        function_call_types = {
            "call_expression",  # JavaScript, TypeScript
            "call",  # Python
            "function_call",  # Various languages
            "method_call",  # Java, C#
            "invocation",  # General
            "apply",  # Functional languages
        }

        node_type = getattr(node, "type", "").lower()
        return node_type in function_call_types

    @staticmethod
    def is_method_call(node: Any) -> bool:
        """
        Check if AST node represents a method call.

        Args:
            node: AST node to check

        Returns:
            True if node represents a method call
        """
        if not hasattr(node, "type"):
            return False

        # Common method call node types
        method_call_types = {
            "method_call",
            "member_expression",
            "attribute_access",
            "property_access",
            "dot_expression",
            "field_access",
        }

        node_type = getattr(node, "type", "").lower()
        return node_type in method_call_types

    @staticmethod
    def extract_call_context(node: Any) -> dict[str, Any]:
        """
        Extract context information from call node.

        Args:
            node: AST node to extract context from

        Returns:
            Dictionary containing context information
        """
        context = {}

        try:
            # Extract basic node information
            if hasattr(node, "type"):
                context["node_type"] = node.type

            # Extract parent context if available
            if hasattr(node, "parent") and node.parent:
                context["parent_type"] = getattr(node.parent, "type", "unknown")

            # Extract arguments count if available
            if hasattr(node, "children"):
                context["child_count"] = len(node.children)

                # Try to identify arguments
                args = []
                for child in node.children:
                    if hasattr(child, "type") and "argument" in child.type.lower():
                        args.append(child.type)

                if args:
                    context["argument_types"] = args

            # Extract text representation if available
            if hasattr(node, "text"):
                text = node.text
                if isinstance(text, bytes):
                    text = text.decode("utf-8", errors="ignore")

                # Limit text length for context
                if len(text) > 100:
                    text = text[:97] + "..."

                context["text_snippet"] = text

            # Extract position information
            if hasattr(node, "start_point"):
                context["start_row"] = node.start_point[0]
                context["start_col"] = node.start_point[1]

            if hasattr(node, "end_point"):
                context["end_row"] = node.end_point[0]
                context["end_col"] = node.end_point[1]

        except Exception as e:
            logger.warning(f"Error extracting context: {e}")
            context["extraction_error"] = str(e)

        return context

    @staticmethod
    def calculate_byte_offsets(node: Any, source_code: str) -> tuple[int, int]:
        """
        Calculate byte start and end offsets for a node.

        Args:
            node: AST node
            source_code: Original source code

        Returns:
            Tuple of (start_byte, end_byte)
        """
        try:
            # Try tree-sitter node byte positions first
            if hasattr(node, "start_byte") and hasattr(node, "end_byte"):
                start_byte = node.start_byte
                end_byte = node.end_byte

                # Validate against source code length
                source_length = len(source_code.encode("utf-8"))
                if 0 <= start_byte <= end_byte <= source_length:
                    return start_byte, end_byte

            # Fallback: calculate from line/column positions
            if hasattr(node, "start_point") and hasattr(node, "end_point"):
                start_row, start_col = node.start_point
                end_row, end_col = node.end_point

                lines = source_code.split("\n")

                # Calculate start byte
                start_byte = 0
                for i in range(start_row):
                    if i < len(lines):
                        start_byte += (
                            len(lines[i].encode("utf-8")) + 1
                        )  # +1 for newline
                start_byte += len(lines[start_row][:start_col].encode("utf-8"))

                # Calculate end byte
                end_byte = 0
                for i in range(end_row):
                    if i < len(lines):
                        end_byte += len(lines[i].encode("utf-8")) + 1  # +1 for newline
                end_byte += len(lines[end_row][:end_col].encode("utf-8"))

                return start_byte, end_byte

        except Exception as e:
            logger.warning(f"Error calculating byte offsets: {e}")

        # Ultimate fallback
        return 0, 0

    @staticmethod
    def extract_function_name(node: Any) -> str:
        """
        Extract function name from call node.

        Args:
            node: AST node representing a function call

        Returns:
            Function name or empty string if not found
        """
        try:
            # Common patterns for extracting function names
            if hasattr(node, "children") and node.children:
                # Look for identifier in children
                for child in node.children:
                    if hasattr(child, "type"):
                        child_type = child.type.lower()
                        if "identifier" in child_type or "name" in child_type:
                            if hasattr(child, "text"):
                                text = child.text
                                if isinstance(text, bytes):
                                    text = text.decode("utf-8", errors="ignore")
                                return text.strip()

            # Try direct text extraction
            if hasattr(node, "text"):
                text = node.text
                if isinstance(text, bytes):
                    text = text.decode("utf-8", errors="ignore")

                # Extract identifier pattern from text
                match = re.match(r"^([a-zA-Z_][a-zA-Z0-9_]*)", text.strip())
                if match:
                    return match.group(1)

        except Exception as e:
            logger.warning(f"Error extracting function name: {e}")

        return ""


class ExtractionUtils:
    """Common utility functions for all extractors."""

    @staticmethod
    def safe_extract(extractor_func: Callable, *args, **kwargs) -> Any:
        """
        Safely execute extraction with error handling.

        Args:
            extractor_func: Function to execute safely
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function

        Returns:
            Function result or None if error occurred
        """
        try:
            return extractor_func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error in {extractor_func.__name__}: {e}", exc_info=True)
            return None

    @staticmethod
    def validate_byte_offsets(start: int, end: int, source_length: int) -> bool:
        """
        Validate byte offset values.

        Args:
            start: Start byte offset
            end: End byte offset
            source_length: Length of source code in bytes

        Returns:
            True if offsets are valid
        """
        return (
            isinstance(start, int)
            and isinstance(end, int)
            and isinstance(source_length, int)
            and 0 <= start <= end <= source_length
        )

    @staticmethod
    def normalize_function_name(name: str) -> str:
        """
        Normalize function names for consistency.

        Args:
            name: Raw function name

        Returns:
            Normalized function name
        """
        if not isinstance(name, str):
            return ""

        # Remove whitespace
        name = name.strip()

        # Remove common prefixes/suffixes
        name = re.sub(r"^(function\s+|def\s+|fn\s+)", "", name)
        name = re.sub(r"\s*\(.*$", "", name)  # Remove parameter list

        # Extract valid identifier
        match = re.match(r"^([a-zA-Z_][a-zA-Z0-9_]*)", name)
        if match:
            return match.group(1)

        return name

    @staticmethod
    def extract_file_metadata(file_path: Path) -> dict[str, Any]:
        """
        Extract metadata from file path.

        Args:
            file_path: Path to the file

        Returns:
            Dictionary containing file metadata
        """
        metadata = {}

        try:
            if isinstance(file_path, str):
                file_path = Path(file_path)

            metadata["filename"] = file_path.name
            metadata["extension"] = file_path.suffix
            metadata["directory"] = str(file_path.parent)
            metadata["absolute_path"] = str(file_path.absolute())

            # File size and modification time if file exists
            if file_path.exists():
                stat = file_path.stat()
                metadata["size_bytes"] = stat.st_size
                metadata["modified_time"] = datetime.fromtimestamp(
                    stat.st_mtime,
                ).isoformat()

        except Exception as e:
            logger.warning(f"Error extracting file metadata: {e}")
            metadata["extraction_error"] = str(e)

        return metadata

    @staticmethod
    def calculate_line_column(source_code: str, byte_offset: int) -> tuple[int, int]:
        """
        Calculate line and column from byte offset.

        Args:
            source_code: Source code string
            byte_offset: Byte offset position

        Returns:
            Tuple of (line_number, column_number) (1-based)
        """
        try:
            # Convert to bytes for accurate offset calculation
            source_bytes = source_code.encode("utf-8")

            if byte_offset < 0 or byte_offset > len(source_bytes):
                return 1, 0

            # Count lines and find column
            lines_before = source_bytes[:byte_offset].count(b"\n")
            line_number = lines_before + 1

            # Find start of current line
            last_newline = source_bytes.rfind(b"\n", 0, byte_offset)
            if last_newline == -1:
                column_number = byte_offset
            else:
                column_number = byte_offset - last_newline - 1

            return line_number, column_number

        except Exception as e:
            logger.warning(f"Error calculating line/column: {e}")
            return 1, 0

    @staticmethod
    def validate_call_site(call_site: CallSite, source_code: str) -> list[str]:
        """
        Validate a CallSite object for consistency.

        Args:
            call_site: CallSite to validate
            source_code: Original source code

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        try:
            # Basic field validation
            if not call_site.function_name:
                errors.append("function_name is empty")

            if call_site.line_number < 1:
                errors.append("line_number must be >= 1")

            if call_site.column_number < 0:
                errors.append("column_number must be >= 0")

            # Byte offset validation
            source_length = len(source_code.encode("utf-8"))
            if not ExtractionUtils.validate_byte_offsets(
                call_site.byte_start,
                call_site.byte_end,
                source_length,
            ):
                errors.append("invalid byte offsets")

            # Verify line/column matches byte offsets
            calc_line, _calc_col = ExtractionUtils.calculate_line_column(
                source_code,
                call_site.byte_start,
            )

            if abs(calc_line - call_site.line_number) > 1:  # Allow 1 line tolerance
                errors.append(
                    f"line_number mismatch: expected ~{calc_line}, got {call_site.line_number}",
                )

        except Exception as e:
            errors.append(f"validation error: {e}")

        return errors

    @staticmethod
    def merge_extraction_results(results: list[ExtractionResult]) -> ExtractionResult:
        """
        Merge multiple extraction results into one.

        Args:
            results: List of ExtractionResult objects to merge

        Returns:
            Merged ExtractionResult
        """
        if not results:
            return ExtractionResult()

        merged = ExtractionResult()

        # Merge call sites
        for result in results:
            merged.call_sites.extend(result.call_sites)

        # Sum extraction times
        merged.extraction_time = sum(r.extraction_time for r in results)

        # Merge errors and warnings
        for result in results:
            merged.errors.extend(result.errors)
            merged.warnings.extend(result.warnings)

        # Merge metadata and performance metrics
        for result in results:
            merged.metadata.update(result.metadata)
            merged.performance_metrics.update(result.performance_metrics)

        # Add merge metadata
        merged.metadata["merged_from"] = len(results)
        merged.metadata["total_call_sites"] = len(merged.call_sites)

        return merged

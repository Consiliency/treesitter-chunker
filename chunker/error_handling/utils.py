"""Utility functions for the error handling system.

This module provides common utility functions that are used across the
error handling system components. These utilities help with error analysis,
formatting, and common operations that multiple components need.

Group C, D, and E agents can import and use these utilities to avoid
duplicating common functionality.
"""

import hashlib
import json
import logging
import re
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)


# Error pattern matching utilities
def extract_error_pattern(error_message: str) -> str:
    """Extract a normalized error pattern from an error message.

    Args:
        error_message: The raw error message

    Returns:
        Normalized error pattern for matching
    """
    if not error_message:
        return ""

    # Remove variable parts like file paths, line numbers, etc.
    pattern = error_message

    # Remove file paths (both absolute and relative)
    pattern = re.sub(r"/[^\s:]+", "<PATH>", pattern)
    pattern = re.sub(r"[./\\][^\s:]+", "<PATH>", pattern)

    # Remove line numbers
    pattern = re.sub(r":\d+", ":N", pattern)
    pattern = re.sub(r"line \d+", "line N", pattern)

    # Remove specific version numbers
    pattern = re.sub(r"\d+\.\d+\.\d+", "<VERSION>", pattern)
    pattern = re.sub(r"\d+\.\d+", "<VERSION>", pattern)

    # Remove specific error codes
    pattern = re.sub(r"error \d+", "error <CODE>", pattern)
    pattern = re.sub(r"code \d+", "code <CODE>", pattern)

    # Normalize whitespace
    pattern = re.sub(r"\s+", " ", pattern).strip()

    return pattern


def calculate_error_similarity(error1: str, error2: str) -> float:
    """Calculate similarity between two error messages.

    Args:
        error1: First error message
        error2: Second error message

    Returns:
        Similarity score between 0.0 and 1.0
    """
    if not error1 or not error2:
        return 0.0

    # Extract patterns
    pattern1 = extract_error_pattern(error1)
    pattern2 = extract_error_pattern(error2)

    if pattern1 == pattern2:
        return 1.0

    # Simple similarity based on common words
    words1 = set(pattern1.lower().split())
    words2 = set(pattern2.lower().split())

    if not words1 or not words2:
        return 0.0

    intersection = words1.intersection(words2)
    union = words1.union(words2)

    return len(intersection) / len(union)


# Error context utilities
def extract_file_context(
    file_path: Path,
    line_number: int,
    context_lines: int = 3,
) -> dict[str, Any]:
    """Extract context around a specific line in a file.

    Args:
        file_path: Path to the file
        line_number: Line number to extract context around
        context_lines: Number of lines before and after to include

    Returns:
        Dictionary with context information
    """
    context = {
        "file_path": str(file_path),
        "line_number": line_number,
        "context_lines": context_lines,
        "before_lines": [],
        "target_line": "",
        "after_lines": [],
        "total_lines": 0,
    }

    try:
        if not file_path.exists():
            context["error"] = f"File does not exist: {file_path}"
            return context

        with open(file_path, encoding="utf-8") as f:
            lines = f.readlines()

        context["total_lines"] = len(lines)

        # Validate line number
        if line_number < 1 or line_number > len(lines):
            context["error"] = (
                f"Line number {line_number} out of range (1-{len(lines)})"
            )
            return context

        # Extract context lines
        start_line = max(1, line_number - context_lines)
        end_line = min(len(lines), line_number + context_lines)

        # Lines before target
        for i in range(start_line, line_number):
            if i > 0:
                context["before_lines"].append(
                    {"line_number": i, "content": lines[i - 1].rstrip("\n")},
                )

        # Target line
        context["target_line"] = {
            "line_number": line_number,
            "content": lines[line_number - 1].rstrip("\n"),
        }

        # Lines after target
        for i in range(line_number + 1, end_line + 1):
            if i <= len(lines):
                context["after_lines"].append(
                    {"line_number": i, "content": lines[i - 1].rstrip("\n")},
                )

    except Exception as e:
        context["error"] = f"Failed to extract context: {e}"
        logger.error(f"Error extracting file context: {e}")

    return context


def extract_stack_trace_info(exc_info: tuple) -> dict[str, Any]:
    """Extract useful information from exception info.

    Args:
        exc_info: Exception info tuple from sys.exc_info()

    Returns:
        Dictionary with stack trace information
    """
    if not exc_info or len(exc_info) != 3:
        return {}

    exc_type, exc_value, exc_traceback = exc_info

    stack_info = {
        "exception_type": exc_type.__name__ if exc_type else None,
        "exception_message": str(exc_value) if exc_value else None,
        "stack_frames": [],
        "last_frame": None,
    }

    try:
        if exc_traceback:
            # Extract stack frames
            tb = exc_traceback
            while tb:
                frame_info = {
                    "filename": tb.tb_frame.f_code.co_filename,
                    "function": tb.tb_frame.f_code.co_name,
                    "line_number": tb.tb_lineno,
                    "locals": {},
                }

                # Extract relevant local variables (avoid sensitive data)
                for name, value in tb.tb_frame.f_locals.items():
                    if not name.startswith("_") and name not in [
                        "password",
                        "secret",
                        "key",
                    ]:
                        try:
                            # Convert to string representation, limit length
                            str_value = str(value)
                            if len(str_value) > 100:
                                str_value = str_value[:100] + "..."
                            frame_info["locals"][name] = str_value
                        except (TypeError, ValueError, AttributeError, RecursionError):
                            frame_info["locals"][name] = "<unrepresentable>"

                stack_info["stack_frames"].append(frame_info)
                tb = tb.tb_next

            # Set last frame
            if stack_info["stack_frames"]:
                stack_info["last_frame"] = stack_info["stack_frames"][-1]

    except Exception as e:
        logger.error(f"Error extracting stack trace info: {e}")
        stack_info["error"] = str(e)

    return stack_info


# Error formatting utilities
def format_error_message(
    error_type: str,
    message: str,
    context: dict[str, Any] | None = None,
) -> str:
    """Format an error message with context.

    Args:
        error_type: Type of error (e.g., "SyntaxError", "CompatibilityError")
        message: Error message
        context: Optional context information

    Returns:
        Formatted error message
    """
    formatted = f"{error_type}: {message}"

    if context:
        if "file_path" in context:
            formatted += f"\nFile: {context['file_path']}"

        if "line_number" in context:
            formatted += f"\nLine: {context['line_number']}"

        if "language" in context:
            formatted += f"\nLanguage: {context['language']}"

    return formatted


def format_user_guidance(steps: list[str], examples: list[str] | None = None) -> str:
    """Format user guidance steps and examples.

    Args:
        steps: List of guidance steps
        examples: Optional list of examples

    Returns:
        Formatted guidance text
    """
    if not steps:
        return "No guidance available."

    guidance = "To resolve this issue:\n"

    for i, step in enumerate(steps, 1):
        guidance += f"{i}. {step}\n"

    if examples:
        guidance += "\nExamples:\n"
        for i, example in enumerate(examples, 1):
            guidance += f"{i}. {example}\n"

    return guidance


# Error categorization utilities
def categorize_error_by_message(message: str) -> str:
    """Categorize error based on message content.

    Args:
        message: Error message

    Returns:
        Error category
    """
    message_lower = message.lower()

    # Syntax errors
    if any(
        word in message_lower for word in ["syntax", "parse", "token", "unexpected"]
    ):
        return "syntax"

    # Compatibility errors
    if any(
        word in message_lower
        for word in ["compatibility", "version", "unsupported", "deprecated"]
    ):
        return "compatibility"

    # Grammar errors
    if any(word in message_lower for word in ["grammar", "tree-sitter", "parser"]):
        return "grammar"

    # Configuration errors
    if any(
        word in message_lower for word in ["config", "setting", "option", "parameter"]
    ):
        return "configuration"

    # System errors
    if any(word in message_lower for word in ["system", "permission", "access", "io"]):
        return "system"

    # Network errors
    if any(
        word in message_lower for word in ["network", "connection", "timeout", "http"]
    ):
        return "network"

    return "unknown"


def estimate_error_severity(
    error_type: str,
    message: str,
    context: dict[str, Any] | None = None,
) -> str:
    """Estimate error severity based on type and context.

    Args:
        error_type: Type of error
        message: Error message
        context: Optional context information

    Returns:
        Estimated severity level
    """
    # Critical errors
    if any(word in error_type.lower() for word in ["fatal", "critical", "panic"]):
        return "critical"

    # System-level errors
    if error_type in ["PermissionError", "OSError", "IOError"]:
        return "error"

    # Syntax errors are usually errors
    if error_type in ["SyntaxError", "IndentationError"]:
        return "error"

    # Compatibility issues are warnings
    if error_type in ["CompatibilityError", "VersionError"]:
        return "warning"

    # Configuration issues are usually warnings
    if error_type in ["ConfigurationError", "ValueError"]:
        return "warning"

    # Default to error for unknown types
    return "error"


# Error ID generation
def generate_error_id(
    error_type: str,
    message: str,
    context: dict[str, Any] | None = None,
) -> str:
    """Generate a unique error ID for tracking.

    Args:
        error_type: Type of error
        message: Error message
        context: Optional context information

    Returns:
        Unique error ID
    """
    # Create a hashable representation
    error_data = {
        "type": error_type,
        "message": message,
        "timestamp": datetime.now().isoformat(),
    }

    if context:
        # Include relevant context (avoid large objects)
        if "file_path" in context:
            error_data["file"] = str(context["file_path"])
        if "line_number" in context:
            error_data["line"] = context["line_number"]
        if "language" in context:
            error_data["language"] = context["language"]

    # Generate hash
    error_str = json.dumps(error_data, sort_keys=True)
    error_hash = hashlib.md5(error_str.encode()).hexdigest()

    return f"{error_type}_{error_hash[:8]}"


# Performance utilities
def measure_execution_time(func):
    """Decorator to measure function execution time.

    Args:
        func: Function to measure

    Returns:
        Decorated function with timing
    """

    def wrapper(*args, **kwargs):
        start_time = datetime.now()
        try:
            result = func(*args, **kwargs)
            return result
        finally:
            end_time = datetime.now()
            execution_time = (end_time - start_time).total_seconds()
            logger.debug(f"Function {func.__name__} took {execution_time:.3f} seconds")

    return wrapper


# Validation utilities
def validate_error_context(context: dict[str, Any]) -> list[str]:
    """Validate error context data.

    Args:
        context: Error context dictionary

    Returns:
        List of validation errors
    """
    errors = []

    if "file_path" in context:
        file_path = Path(context["file_path"])
        if not file_path.exists():
            errors.append(f"File path does not exist: {file_path}")

    if "line_number" in context:
        line_num = context["line_number"]
        if not isinstance(line_num, int) or line_num < 1:
            errors.append(f"Invalid line number: {line_num}")

    if "language" in context:
        language = context["language"]
        if not isinstance(language, str) or not language.strip():
            errors.append(f"Invalid language: {language}")

    return errors

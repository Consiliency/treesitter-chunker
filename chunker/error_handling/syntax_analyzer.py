"""Syntax error analyzer for Phase 1.7 - Smart Error Handling & User Guidance."""

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

# Import from completed Task C1
from .classifier import (
    ClassifiedError,
    ErrorCategory,
    ErrorContext,
    ErrorSeverity,
    ErrorSource,
)

logger = logging.getLogger(__name__)


class SyntaxErrorAnalyzer:
    """Analyzes syntax errors for patterns and causes."""

    def __init__(self):
        """Initialize the syntax error analyzer."""
        self.syntax_patterns = self._load_syntax_patterns()
        self.language_patterns = self._load_language_patterns()
        self.error_categories = self._load_error_categories()
        self.error_counter = 0
        logger.info("Initialized SyntaxErrorAnalyzer")

    def _load_syntax_patterns(self) -> dict[str, list[re.Pattern]]:
        """Load regex patterns for syntax error detection."""
        patterns = {
            "missing_bracket": [
                re.compile(
                    r"missing\s+closing\s+(bracket|brace|parenthesis)",
                    re.IGNORECASE,
                ),
                re.compile(r"unmatched\s+(bracket|brace|parenthesis)", re.IGNORECASE),
                re.compile(r'expected\s+["\']?[\)\]\}]', re.IGNORECASE),
                re.compile(r"unclosed\s+(bracket|brace|parenthesis)", re.IGNORECASE),
            ],
            "unexpected_token": [
                re.compile(r'unexpected\s+token\s+["\']?(\w+)', re.IGNORECASE),
                re.compile(r'unexpected\s+["\']?(\w+)', re.IGNORECASE),
                re.compile(r'expected\s+.*\s+but\s+got\s+["\']?(\w+)', re.IGNORECASE),
                re.compile(r"unexpected\s+end\s+of\s+(file|input)", re.IGNORECASE),
            ],
            "invalid_syntax": [
                re.compile(r"invalid\s+syntax", re.IGNORECASE),
                re.compile(r"syntax\s+error", re.IGNORECASE),
                re.compile(r"parse\s+error", re.IGNORECASE),
                re.compile(r"illegal\s+(character|token)", re.IGNORECASE),
            ],
            "indentation": [
                re.compile(r"indentation\s+error", re.IGNORECASE),
                re.compile(r"unexpected\s+indent", re.IGNORECASE),
                re.compile(r"expected\s+an?\s+indented\s+block", re.IGNORECASE),
                re.compile(r"inconsistent\s+indentation", re.IGNORECASE),
            ],
            "unterminated_string": [
                re.compile(r"unterminated\s+string", re.IGNORECASE),
                re.compile(r"unclosed\s+string", re.IGNORECASE),
                re.compile(r"EOF\s+while\s+scanning\s+string", re.IGNORECASE),
                re.compile(r"missing\s+closing\s+quote", re.IGNORECASE),
            ],
            "missing_colon": [
                re.compile(r'expected\s+["\']?:', re.IGNORECASE),
                re.compile(r"missing\s+colon", re.IGNORECASE),
                re.compile(r"invalid\s+syntax.*expected.*:", re.IGNORECASE),
            ],
            "missing_semicolon": [
                re.compile(r'expected\s+["\']?;', re.IGNORECASE),
                re.compile(r"missing\s+semicolon", re.IGNORECASE),
                re.compile(r"statement\s+not\s+terminated", re.IGNORECASE),
            ],
            "invalid_identifier": [
                re.compile(r"invalid\s+identifier", re.IGNORECASE),
                re.compile(r"illegal\s+name", re.IGNORECASE),
                re.compile(r"not\s+a\s+valid\s+identifier", re.IGNORECASE),
                re.compile(r"reserved\s+keyword", re.IGNORECASE),
            ],
            "type_error": [
                re.compile(r"type\s+error", re.IGNORECASE),
                re.compile(r"type\s+mismatch", re.IGNORECASE),
                re.compile(r"incompatible\s+types?", re.IGNORECASE),
                re.compile(r"cannot\s+convert", re.IGNORECASE),
            ],
        }
        logger.debug(f"Loaded {sum(len(p) for p in patterns.values())} syntax patterns")
        return patterns

    def _load_language_patterns(self) -> dict[str, dict[str, list[re.Pattern]]]:
        """Load language-specific syntax patterns."""
        patterns = {
            "python": {
                "indentation": [
                    re.compile(r"IndentationError"),
                    re.compile(r"TabError"),
                    re.compile(r"expected\s+an?\s+indented\s+block"),
                ],
                "syntax": [
                    re.compile(r"SyntaxError"),
                    re.compile(r"invalid\s+syntax"),
                    re.compile(r"EOL\s+while\s+scanning"),
                ],
                "import": [
                    re.compile(r"ImportError"),
                    re.compile(r"ModuleNotFoundError"),
                    re.compile(r"cannot\s+import\s+name"),
                ],
            },
            "javascript": {
                "syntax": [
                    re.compile(r"SyntaxError"),
                    re.compile(r"Unexpected\s+token"),
                    re.compile(r"Unexpected\s+identifier"),
                ],
                "reference": [
                    re.compile(r"ReferenceError"),
                    re.compile(r"is\s+not\s+defined"),
                    re.compile(r"undefined\s+variable"),
                ],
                "type": [
                    re.compile(r"TypeError"),
                    re.compile(r"is\s+not\s+a\s+function"),
                    re.compile(r"Cannot\s+read\s+property"),
                ],
            },
            "rust": {
                "syntax": [
                    re.compile(r"expected\s+.*,\s+found"),
                    re.compile(r"unexpected\s+token"),
                    re.compile(r"missing\s+lifetime\s+specifier"),
                ],
                "type": [
                    re.compile(r"mismatched\s+types"),
                    re.compile(r"type\s+mismatch"),
                    re.compile(r"expected\s+.*\s+found\s+.*\s+type"),
                ],
                "borrow": [
                    re.compile(r"cannot\s+borrow"),
                    re.compile(r"borrowed\s+value\s+does\s+not\s+live"),
                    re.compile(r"lifetime\s+.*\s+does\s+not\s+live"),
                ],
            },
            "go": {
                "syntax": [
                    re.compile(r"syntax\s+error"),
                    re.compile(r"unexpected\s+.*\s+expecting"),
                    re.compile(r"missing\s+.*\s+at\s+end"),
                ],
                "type": [
                    re.compile(r"cannot\s+use\s+.*\s+as\s+type"),
                    re.compile(r"type\s+.*\s+is\s+not\s+an?\s+expression"),
                    re.compile(r"incompatible\s+type"),
                ],
                "import": [
                    re.compile(r"imported\s+and\s+not\s+used"),
                    re.compile(r"undefined:\s+"),
                    re.compile(r"cannot\s+find\s+package"),
                ],
            },
            "java": {
                "syntax": [
                    re.compile(r"error:\s+.*\s+expected"),
                    re.compile(r"illegal\s+start\s+of"),
                    re.compile(r"reached\s+end\s+of\s+file"),
                ],
                "type": [
                    re.compile(r"incompatible\s+types"),
                    re.compile(r"cannot\s+find\s+symbol"),
                    re.compile(r"method\s+.*\s+cannot\s+be\s+applied"),
                ],
                "class": [
                    re.compile(r"class\s+.*\s+is\s+public"),
                    re.compile(r"duplicate\s+class"),
                    re.compile(r"class\s+.*\s+not\s+found"),
                ],
            },
            "cpp": {
                "syntax": [
                    re.compile(r'expected\s+["\'].*["\']?\s+before'),
                    re.compile(r"missing\s+terminating"),
                    re.compile(r"stray\s+.*\s+in\s+program"),
                ],
                "type": [
                    re.compile(r"invalid\s+conversion"),
                    re.compile(r"no\s+matching\s+function"),
                    re.compile(r"undefined\s+reference"),
                ],
                "preprocessor": [
                    re.compile(r"#error"),
                    re.compile(r"unterminated\s+#"),
                    re.compile(r"invalid\s+preprocessing\s+directive"),
                ],
            },
        }
        logger.debug(f"Loaded patterns for {len(patterns)} languages")
        return patterns

    def _load_error_categories(self) -> dict[str, ErrorCategory]:
        """Load mapping of syntax errors to categories."""
        categories = {
            "missing_bracket": ErrorCategory.SYNTAX,
            "unexpected_token": ErrorCategory.SYNTAX,
            "invalid_syntax": ErrorCategory.SYNTAX,
            "indentation": ErrorCategory.SYNTAX,
            "unterminated_string": ErrorCategory.SYNTAX,
            "missing_colon": ErrorCategory.SYNTAX,
            "missing_semicolon": ErrorCategory.SYNTAX,
            "invalid_identifier": ErrorCategory.SYNTAX,
            "type_error": ErrorCategory.SYNTAX,
            "import_error": ErrorCategory.CONFIGURATION,
            "reference_error": ErrorCategory.SYNTAX,
        }
        logger.debug(f"Loaded {len(categories)} error category mappings")
        return categories

    def analyze_syntax_error(
        self,
        error_message: str,
        language: str | None = None,
        file_path: Path | None = None,
    ) -> ClassifiedError:
        """Analyze a syntax error and classify it.

        Args:
            error_message: The error message to analyze
            language: Optional language identifier
            file_path: Optional path to the source file

        Returns:
            ClassifiedError object for the syntax error
        """
        try:
            # Generate error ID
            self.error_counter += 1
            error_id = f"SYNTAX_{datetime.now().strftime('%Y%m%d%H%M%S')}_{self.error_counter:04d}"

            # Detect language from file if not provided
            if not language and file_path:
                language = self._detect_language_from_file(file_path)

            # Detect error type
            error_type = self.detect_syntax_error_type(
                error_message,
                language or "unknown",
            )

            # Extract location
            line_number, column_number = self.extract_syntax_error_location(
                error_message,
            )

            # Identify the problem
            problem = self.identify_syntax_problem(error_message, language or "unknown")

            # Get suggestions
            suggestions = self.suggest_syntax_fix(
                error_type,
                language or "unknown",
                error_message,
            )

            # Categorize error
            category = self.categorize_syntax_error(
                error_message,
                language or "unknown",
            )

            # Determine severity
            severity = self.determine_syntax_error_severity(
                error_type,
                language or "unknown",
            )

            # Create context
            context = ErrorContext(
                file_path=str(file_path) if file_path else None,
                line_number=line_number,
                column_number=column_number,
                language=language,
                timestamp=datetime.now(),
            )

            # Create classified error
            classified_error = ClassifiedError(
                error_id=error_id,
                message=f"{problem}: {error_message}",
                category=category,
                severity=severity,
                source=ErrorSource.TREE_SITTER,
                context=context,
                suggested_actions=suggestions,
                confidence=0.85,
            )

            logger.info(f"Analyzed syntax error {error_id}: {error_type}")
            return classified_error

        except Exception as e:
            logger.error(f"Error analyzing syntax error: {e}")
            # Return a basic classified error
            return ClassifiedError(
                error_id=f"SYNTAX_ERROR_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                message=error_message,
                category=ErrorCategory.SYNTAX,
                severity=ErrorSeverity.ERROR,
                source=ErrorSource.TREE_SITTER,
                context=ErrorContext(),
                confidence=0.5,
            )

    def _detect_language_from_file(self, file_path: Path) -> str | None:
        """Detect language from file extension."""
        try:
            extension_map = {
                ".py": "python",
                ".js": "javascript",
                ".jsx": "javascript",
                ".ts": "typescript",
                ".tsx": "typescript",
                ".rs": "rust",
                ".go": "go",
                ".java": "java",
                ".cpp": "cpp",
                ".cc": "cpp",
                ".cxx": "cpp",
                ".c": "c",
                ".h": "c",
                ".hpp": "cpp",
                ".rb": "ruby",
                ".php": "php",
                ".swift": "swift",
                ".kt": "kotlin",
                ".scala": "scala",
                ".cs": "csharp",
            }

            suffix = file_path.suffix.lower()
            return extension_map.get(suffix)

        except Exception as e:
            logger.error(f"Error detecting language from file: {e}")
            return None

    def detect_syntax_error_type(self, error_message: str, language: str) -> str:
        """Detect the specific type of syntax error.

        Args:
            error_message: The error message
            language: Language identifier

        Returns:
            String identifying error type
        """
        try:
            error_lower = error_message.lower()

            # Check language-specific patterns first
            if language in self.language_patterns:
                for error_type, patterns in self.language_patterns[language].items():
                    for pattern in patterns:
                        if pattern.search(error_message):
                            logger.debug(
                                f"Detected {language}-specific error type: {error_type}",
                            )
                            return f"{language}_{error_type}"

            # Check general syntax patterns
            for error_type, patterns in self.syntax_patterns.items():
                for pattern in patterns:
                    if pattern.search(error_message):
                        logger.debug(f"Detected general error type: {error_type}")
                        return error_type

            # Default to generic syntax error
            return "invalid_syntax"

        except Exception as e:
            logger.error(f"Error detecting syntax error type: {e}")
            return "unknown_syntax_error"

    def extract_syntax_error_location(
        self,
        error_message: str,
    ) -> tuple[int | None, int | None]:
        """Extract line and column numbers from syntax error.

        Args:
            error_message: The error message

        Returns:
            Tuple of (line_number, column_number) or (None, None)
        """
        try:
            line_number = None
            column_number = None

            # Common patterns for line/column information
            patterns = [
                # Line X, Column Y format
                re.compile(r"line\s+(\d+),?\s*(?:column|col)?\s*(\d+)", re.IGNORECASE),
                # (Line:Column) format
                re.compile(r"\((\d+):(\d+)\)"),
                # Line X format
                re.compile(r"line\s+(\d+)", re.IGNORECASE),
                # :X:Y format (common in compilers)
                re.compile(r":(\d+):(\d+)"),
                # at line X format
                re.compile(r"at\s+line\s+(\d+)", re.IGNORECASE),
                # row X, col Y format
                re.compile(r"row\s+(\d+),?\s*col\s+(\d+)", re.IGNORECASE),
            ]

            for pattern in patterns:
                match = pattern.search(error_message)
                if match:
                    groups = match.groups()
                    if len(groups) >= 1:
                        line_number = int(groups[0])
                    if len(groups) >= 2:
                        column_number = int(groups[1])
                    if line_number:
                        break

            logger.debug(
                f"Extracted location: line {line_number}, column {column_number}",
            )
            return (line_number, column_number)

        except Exception as e:
            logger.error(f"Error extracting location: {e}")
            return (None, None)

    def identify_syntax_problem(self, error_message: str, language: str) -> str:
        """Identify the specific syntax problem.

        Args:
            error_message: The error message
            language: Language identifier

        Returns:
            String describing the syntax problem
        """
        try:
            error_lower = error_message.lower()

            # Common problem descriptions
            problems = {
                "missing_bracket": "Missing or unmatched bracket/brace/parenthesis",
                "unexpected_token": "Unexpected token or symbol",
                "invalid_syntax": "Invalid syntax structure",
                "indentation": "Incorrect indentation",
                "unterminated_string": "Unterminated string literal",
                "missing_colon": "Missing colon",
                "missing_semicolon": "Missing semicolon",
                "invalid_identifier": "Invalid identifier or variable name",
                "type_error": "Type mismatch or conversion error",
                "import_error": "Import or module error",
                "reference_error": "Undefined reference or variable",
            }

            # Check for specific problem patterns
            for problem_type, patterns in self.syntax_patterns.items():
                for pattern in patterns:
                    if pattern.search(error_message):
                        return problems.get(problem_type, "Syntax error")

            # Language-specific problem descriptions
            if language == "python" and "indentation" in error_lower:
                return "Python indentation error"
            if language == "javascript" and "unexpected" in error_lower:
                return "JavaScript syntax error"
            if language == "rust" and "lifetime" in error_lower:
                return "Rust lifetime or borrowing error"
            if language == "go" and "expecting" in error_lower:
                return "Go syntax error"
            if language == "java" and "symbol" in error_lower:
                return "Java symbol resolution error"

            return "Syntax error"

        except Exception as e:
            logger.error(f"Error identifying problem: {e}")
            return "Unknown syntax problem"

    def suggest_syntax_fix(
        self,
        error_type: str,
        language: str,
        context: str,
    ) -> list[str]:
        """Suggest fixes for syntax errors.

        Args:
            error_type: Type of syntax error
            language: Language identifier
            context: Error context or message

        Returns:
            List of fix suggestions
        """
        try:
            suggestions = []

            # General suggestions based on error type
            general_fixes = {
                "missing_bracket": [
                    "Check for missing closing brackets, braces, or parentheses",
                    "Ensure all opening brackets have matching closing brackets",
                    "Look for extra or misplaced brackets",
                    "Use an editor with bracket matching to identify the issue",
                ],
                "unexpected_token": [
                    "Check for typos or invalid characters",
                    "Verify the syntax is correct for this language version",
                    "Look for missing operators or keywords",
                    "Check if a statement was terminated properly",
                ],
                "invalid_syntax": [
                    "Review the language syntax documentation",
                    "Check for missing keywords or operators",
                    "Verify statement structure is correct",
                    "Look for invisible or special characters",
                ],
                "indentation": [
                    "Use consistent indentation (spaces or tabs, not both)",
                    "Check indentation levels match the code structure",
                    "Ensure block statements are properly indented",
                    "Use an auto-formatter to fix indentation",
                ],
                "unterminated_string": [
                    "Check for missing closing quotes",
                    "Look for unescaped quotes within the string",
                    "Verify multi-line strings are properly formatted",
                    "Check for accidental line breaks in strings",
                ],
                "missing_colon": [
                    "Add a colon at the end of the statement",
                    "Check if/else/for/while/def statements",
                    "Verify dictionary or object literal syntax",
                    "Look for missing colons in type annotations",
                ],
                "missing_semicolon": [
                    "Add a semicolon at the end of the statement",
                    "Check if automatic semicolon insertion applies",
                    "Verify statement termination requirements",
                    "Consider using a linter to catch missing semicolons",
                ],
            }

            # Add general suggestions
            if error_type in general_fixes:
                suggestions.extend(general_fixes[error_type][:2])

            # Language-specific suggestions
            if language == "python":
                if "indent" in error_type.lower():
                    suggestions.append(
                        "Python requires consistent indentation (usually 4 spaces)",
                    )
                elif "colon" in error_type.lower():
                    suggestions.append(
                        "Python requires colons after if/else/for/while/def/class statements",
                    )
            elif language == "javascript":
                if "semicolon" in error_type.lower():
                    suggestions.append(
                        "JavaScript allows optional semicolons but they're recommended",
                    )
                elif "unexpected" in error_type.lower():
                    suggestions.append("Check for missing commas in objects or arrays")
            elif language == "rust":
                if "lifetime" in context.lower():
                    suggestions.append(
                        "Add lifetime annotations or use 'static lifetime",
                    )
                elif "borrow" in context.lower():
                    suggestions.append("Check ownership and borrowing rules")
            elif language == "go":
                if "import" in context.lower():
                    suggestions.append("Ensure all imported packages are used")
                elif "expecting" in context.lower():
                    suggestions.append(
                        "Go has strict syntax rules - check statement structure",
                    )
            elif language == "java":
                if "class" in context.lower():
                    suggestions.append("Java requires class names to match file names")
                elif "symbol" in context.lower():
                    suggestions.append("Check import statements and class paths")

            # Add a general suggestion if no specific ones were added
            if not suggestions:
                suggestions.append("Review the error message for specific details")
                suggestions.append("Check surrounding code for context")

            return suggestions[:4]  # Return top 4 suggestions

        except Exception as e:
            logger.error(f"Error generating suggestions: {e}")
            return ["Review syntax documentation for this language"]

    def categorize_syntax_error(
        self,
        error_message: str,
        language: str,
    ) -> ErrorCategory:
        """Categorize syntax error into appropriate category.

        Args:
            error_message: The error message
            language: Language identifier

        Returns:
            ErrorCategory enum value
        """
        try:
            # Check for import/module errors
            import_patterns = [
                re.compile(r"import\s+error", re.IGNORECASE),
                re.compile(r"module\s+not\s+found", re.IGNORECASE),
                re.compile(r"cannot\s+import", re.IGNORECASE),
                re.compile(r"unresolved\s+import", re.IGNORECASE),
            ]

            for pattern in import_patterns:
                if pattern.search(error_message):
                    return ErrorCategory.CONFIGURATION

            # Check for parsing errors
            parse_patterns = [
                re.compile(r"parse\s+error", re.IGNORECASE),
                re.compile(r"parsing\s+failed", re.IGNORECASE),
                re.compile(r"ast\s+error", re.IGNORECASE),
            ]

            for pattern in parse_patterns:
                if pattern.search(error_message):
                    return ErrorCategory.PARSING

            # Default to syntax category
            return ErrorCategory.SYNTAX

        except Exception as e:
            logger.error(f"Error categorizing syntax error: {e}")
            return ErrorCategory.SYNTAX

    def determine_syntax_error_severity(
        self,
        error_type: str,
        language: str,
    ) -> ErrorSeverity:
        """Determine severity level of syntax error.

        Args:
            error_type: Type of syntax error
            language: Language identifier

        Returns:
            ErrorSeverity enum value
        """
        try:
            # Critical syntax errors (prevent any execution)
            critical_types = [
                "parse_error",
                "compilation_error",
                "fatal_error",
            ]

            if any(crit in error_type.lower() for crit in critical_types):
                return ErrorSeverity.CRITICAL

            # Errors (prevent normal execution)
            error_types = [
                "syntax_error",
                "invalid_syntax",
                "unexpected_token",
                "missing_bracket",
                "type_error",
            ]

            if any(err in error_type.lower() for err in error_types):
                return ErrorSeverity.ERROR

            # Warnings (may work but not recommended)
            warning_types = [
                "deprecated",
                "unused",
                "redundant",
            ]

            if any(warn in error_type.lower() for warn in warning_types):
                return ErrorSeverity.WARNING

            # Language-specific severity adjustments
            if language == "python" and "indent" in error_type.lower():
                return ErrorSeverity.ERROR  # Indentation is critical in Python
            if language == "go" and "unused" in error_type.lower():
                return ErrorSeverity.ERROR  # Go treats unused imports as errors

            # Default to ERROR for syntax issues
            return ErrorSeverity.ERROR

        except Exception as e:
            logger.error(f"Error determining severity: {e}")
            return ErrorSeverity.ERROR

    def analyze_multiple_syntax_errors(
        self,
        error_messages: list[str],
        language: str,
    ) -> list[ClassifiedError]:
        """Analyze multiple syntax errors in batch.

        Args:
            error_messages: List of error messages
            language: Language identifier

        Returns:
            List of ClassifiedError objects
        """
        try:
            classified_errors = []
            error_counts = {}

            for message in error_messages:
                # Analyze each error
                classified = self.analyze_syntax_error(message, language)
                classified_errors.append(classified)

                # Track error types for patterns
                error_type = self.detect_syntax_error_type(message, language)
                error_counts[error_type] = error_counts.get(error_type, 0) + 1

            # Look for patterns and add related errors
            if len(classified_errors) > 1:
                # Check for cascade errors (one error causing others)
                for i, error in enumerate(classified_errors):
                    for j, other in enumerate(classified_errors):
                        if i != j:
                            # Check if errors are on consecutive lines
                            if (
                                error.context.line_number
                                and other.context.line_number
                                and abs(
                                    error.context.line_number
                                    - other.context.line_number,
                                )
                                <= 2
                            ):
                                error.add_related_error(other.error_id)
                                other.add_related_error(error.error_id)

            # Add summary suggestion if multiple errors of same type
            for error_type, count in error_counts.items():
                if count >= 3:
                    for error in classified_errors:
                        if error_type in error.message.lower():
                            error.add_suggested_action(
                                f"Multiple {error_type} errors detected - consider using a linter",
                            )

            logger.info(f"Analyzed {len(classified_errors)} syntax errors")
            return classified_errors

        except Exception as e:
            logger.error(f"Error analyzing multiple syntax errors: {e}")
            return []

    def get_syntax_error_statistics(
        self,
        error_messages: list[str],
        language: str,
    ) -> dict[str, Any]:
        """Get statistics about syntax errors.

        Args:
            error_messages: List of error messages
            language: Language identifier

        Returns:
            Dictionary with error statistics
        """
        try:
            stats = {
                "total_errors": len(error_messages),
                "language": language,
                "error_types": {},
                "severity_distribution": {},
                "line_distribution": {},
                "most_common_type": None,
                "average_confidence": 0.0,
            }

            if not error_messages:
                return stats

            # Analyze all errors
            classified_errors = self.analyze_multiple_syntax_errors(
                error_messages,
                language,
            )

            # Count error types
            for error in classified_errors:
                error_type = self.detect_syntax_error_type(error.message, language)
                stats["error_types"][error_type] = (
                    stats["error_types"].get(error_type, 0) + 1
                )

                # Count severities
                severity = error.severity.value
                stats["severity_distribution"][severity] = (
                    stats["severity_distribution"].get(severity, 0) + 1
                )

                # Track line numbers
                if error.context.line_number:
                    line_range = f"{(error.context.line_number // 10) * 10}-{(error.context.line_number // 10 + 1) * 10}"
                    stats["line_distribution"][line_range] = (
                        stats["line_distribution"].get(line_range, 0) + 1
                    )

            # Calculate most common error type
            if stats["error_types"]:
                stats["most_common_type"] = max(
                    stats["error_types"],
                    key=stats["error_types"].get,
                )

            # Calculate average confidence
            if classified_errors:
                stats["average_confidence"] = sum(
                    e.confidence for e in classified_errors
                ) / len(classified_errors)

            logger.debug(f"Generated statistics for {len(error_messages)} errors")
            return stats

        except Exception as e:
            logger.error(f"Error generating statistics: {e}")
            return {"error": str(e)}

    def export_syntax_analysis(self, output_path: Path) -> None:
        """Export syntax error analysis to file.

        Args:
            output_path: Path to write the export file
        """
        try:
            import json

            # Prepare export data
            export_data = {
                "exported_at": datetime.now().isoformat(),
                "analyzer": "SyntaxErrorAnalyzer",
                "patterns": {
                    "general": {
                        key: [p.pattern for p in patterns]
                        for key, patterns in self.syntax_patterns.items()
                    },
                    "languages": {
                        lang: {
                            key: [p.pattern for p in patterns]
                            for key, patterns in lang_patterns.items()
                        }
                        for lang, lang_patterns in self.language_patterns.items()
                    },
                },
                "error_categories": {
                    k: v.value for k, v in self.error_categories.items()
                },
                "total_errors_analyzed": self.error_counter,
            }

            # Write to file
            with open(output_path, "w") as f:
                json.dump(export_data, f, indent=2)

            logger.info(f"Exported syntax analysis to {output_path}")

        except Exception as e:
            logger.error(f"Error exporting syntax analysis: {e}")
            raise


class LanguageSpecificSyntaxAnalyzer:
    """Language-specific syntax error analysis."""

    def __init__(self, language: str):
        """Initialize language-specific analyzer.

        Args:
            language: Language to analyze
        """
        self.language = language.lower()
        self.patterns = self._load_language_patterns()
        logger.info(f"Initialized LanguageSpecificSyntaxAnalyzer for {language}")

    def _load_language_patterns(self) -> dict[str, list[re.Pattern]]:
        """Load patterns specific to this language."""
        all_patterns = {
            "python": {
                "indentation": [
                    re.compile(r"IndentationError:\s*(.+)"),
                    re.compile(r"TabError:\s*(.+)"),
                    re.compile(r"unexpected\s+indent"),
                ],
                "syntax": [
                    re.compile(r"SyntaxError:\s*(.+)"),
                    re.compile(r"invalid\s+syntax"),
                    re.compile(r"EOL\s+while\s+scanning\s+string"),
                ],
                "name": [
                    re.compile(r'NameError:\s*name\s+["\'](\w+)["\']'),
                    re.compile(r"UnboundLocalError:\s*(.+)"),
                ],
                "type": [
                    re.compile(r"TypeError:\s*(.+)"),
                    re.compile(r"unsupported\s+operand\s+type"),
                ],
            },
            "javascript": {
                "syntax": [
                    re.compile(r"SyntaxError:\s*(.+)"),
                    re.compile(r"Unexpected\s+token\s+(\w+)"),
                    re.compile(r"Unexpected\s+identifier"),
                ],
                "reference": [
                    re.compile(r"ReferenceError:\s*(.+)"),
                    re.compile(r"(\w+)\s+is\s+not\s+defined"),
                ],
                "type": [
                    re.compile(r"TypeError:\s*(.+)"),
                    re.compile(r"(\w+)\s+is\s+not\s+a\s+function"),
                ],
            },
            "rust": {
                "syntax": [
                    re.compile(r"error\[E\d+\]:\s*(.+)"),
                    re.compile(r"expected\s+(.+),\s+found\s+(.+)"),
                ],
                "lifetime": [
                    re.compile(r"lifetime\s+[`\'](\w+)[`\']"),
                    re.compile(r"borrowed\s+value\s+does\s+not\s+live"),
                ],
                "type": [
                    re.compile(r"mismatched\s+types"),
                    re.compile(r"expected\s+(.+)\s+found\s+(.+)"),
                ],
            },
            "go": {
                "syntax": [
                    re.compile(r"syntax\s+error:\s*(.+)"),
                    re.compile(r"unexpected\s+(\w+),\s+expecting\s+(\w+)"),
                ],
                "undefined": [
                    re.compile(r"undefined:\s*(\w+)"),
                    re.compile(r"(\w+)\s+declared\s+and\s+not\s+used"),
                ],
                "type": [
                    re.compile(r"cannot\s+use\s+(.+)\s+as\s+type\s+(.+)"),
                    re.compile(r"incompatible\s+type"),
                ],
            },
            "java": {
                "syntax": [
                    re.compile(r"error:\s*(.+)\s+expected"),
                    re.compile(r"illegal\s+start\s+of\s+(\w+)"),
                ],
                "symbol": [
                    re.compile(r"cannot\s+find\s+symbol"),
                    re.compile(r"symbol:\s*(\w+)\s+(\w+)"),
                ],
                "type": [
                    re.compile(r"incompatible\s+types:\s*(.+)"),
                    re.compile(r"required:\s*(.+)\s+found:\s*(.+)"),
                ],
            },
        }

        return all_patterns.get(self.language, {})

    def analyze_python_syntax_error(self, error_message: str) -> dict[str, Any]:
        """Analyze Python-specific syntax errors.

        Args:
            error_message: The error message

        Returns:
            Dictionary with analysis results
        """
        try:
            analysis = {
                "language": "python",
                "error_type": None,
                "details": {},
                "suggestions": [],
            }

            # Check for IndentationError
            if "IndentationError" in error_message:
                analysis["error_type"] = "indentation"
                analysis["details"]["issue"] = "Incorrect indentation"
                analysis["suggestions"] = [
                    "Use 4 spaces for indentation (PEP 8 standard)",
                    "Don't mix tabs and spaces",
                    "Check that all blocks are properly indented",
                ]

            # Check for SyntaxError
            elif "SyntaxError" in error_message:
                analysis["error_type"] = "syntax"
                if "invalid syntax" in error_message:
                    analysis["details"]["issue"] = "Invalid Python syntax"
                elif "EOL while scanning" in error_message:
                    analysis["details"]["issue"] = "Unterminated string or statement"
                analysis["suggestions"] = [
                    "Check for missing colons after if/for/while/def",
                    "Verify parentheses and brackets are balanced",
                    "Look for unterminated strings",
                ]

            # Check for NameError
            elif "NameError" in error_message:
                match = re.search(r"name\s+['\"](\w+)['\"]", error_message)
                if match:
                    analysis["details"]["undefined_name"] = match.group(1)
                analysis["error_type"] = "name"
                analysis["suggestions"] = [
                    "Check if the variable is defined before use",
                    "Verify import statements",
                    "Check for typos in variable names",
                ]

            return analysis

        except Exception as e:
            logger.error(f"Error analyzing Python syntax: {e}")
            return {"error": str(e)}

    def analyze_javascript_syntax_error(self, error_message: str) -> dict[str, Any]:
        """Analyze JavaScript-specific syntax errors.

        Args:
            error_message: The error message

        Returns:
            Dictionary with analysis results
        """
        try:
            analysis = {
                "language": "javascript",
                "error_type": None,
                "details": {},
                "suggestions": [],
            }

            # Check for Unexpected token
            if "Unexpected token" in error_message:
                match = re.search(r"Unexpected\s+token\s+(\w+)", error_message)
                if match:
                    analysis["details"]["unexpected_token"] = match.group(1)
                analysis["error_type"] = "syntax"
                analysis["suggestions"] = [
                    "Check for missing commas in objects or arrays",
                    "Verify semicolons are used correctly",
                    "Look for typos in keywords",
                ]

            # Check for ReferenceError
            elif "ReferenceError" in error_message:
                match = re.search(r"(\w+)\s+is\s+not\s+defined", error_message)
                if match:
                    analysis["details"]["undefined_reference"] = match.group(1)
                analysis["error_type"] = "reference"
                analysis["suggestions"] = [
                    "Check if the variable is declared",
                    "Verify scope of the variable",
                    "Check for typos in variable names",
                ]

            # Check for TypeError
            elif "TypeError" in error_message:
                if "is not a function" in error_message:
                    analysis["details"][
                        "issue"
                    ] = "Attempting to call non-function as function"
                analysis["error_type"] = "type"
                analysis["suggestions"] = [
                    "Verify the object type before calling",
                    "Check if the function is defined",
                    "Ensure proper this binding",
                ]

            return analysis

        except Exception as e:
            logger.error(f"Error analyzing JavaScript syntax: {e}")
            return {"error": str(e)}

    def analyze_rust_syntax_error(self, error_message: str) -> dict[str, Any]:
        """Analyze Rust-specific syntax errors.

        Args:
            error_message: The error message

        Returns:
            Dictionary with analysis results
        """
        try:
            analysis = {
                "language": "rust",
                "error_type": None,
                "details": {},
                "suggestions": [],
            }

            # Check for lifetime errors
            if "lifetime" in error_message.lower():
                analysis["error_type"] = "lifetime"
                analysis["details"]["issue"] = "Lifetime annotation issue"
                analysis["suggestions"] = [
                    "Add explicit lifetime annotations",
                    "Check borrowing rules",
                    "Consider using 'static lifetime if appropriate",
                ]

            # Check for type mismatch
            elif "mismatched types" in error_message:
                analysis["error_type"] = "type"
                match = re.search(r"expected\s+(.+)\s+found\s+(.+)", error_message)
                if match:
                    analysis["details"]["expected"] = match.group(1)
                    analysis["details"]["found"] = match.group(2)
                analysis["suggestions"] = [
                    "Check type annotations",
                    "Use type conversion methods",
                    "Verify function return types",
                ]

            # Check for borrow checker errors
            elif "cannot borrow" in error_message or "borrowed value" in error_message:
                analysis["error_type"] = "borrow"
                analysis["details"]["issue"] = "Borrow checker violation"
                analysis["suggestions"] = [
                    "Check ownership rules",
                    "Use references instead of moving values",
                    "Consider using Rc or Arc for shared ownership",
                ]

            return analysis

        except Exception as e:
            logger.error(f"Error analyzing Rust syntax: {e}")
            return {"error": str(e)}

    def analyze_generic_syntax_error(self, error_message: str) -> dict[str, Any]:
        """Analyze generic syntax errors.

        Args:
            error_message: The error message

        Returns:
            Dictionary with analysis results
        """
        try:
            analysis = {
                "language": "generic",
                "error_type": "syntax",
                "details": {},
                "suggestions": [],
            }

            # Extract any line/column information
            line_match = re.search(r"line\s+(\d+)", error_message, re.IGNORECASE)
            if line_match:
                analysis["details"]["line"] = int(line_match.group(1))

            col_match = re.search(r"column\s+(\d+)", error_message, re.IGNORECASE)
            if col_match:
                analysis["details"]["column"] = int(col_match.group(1))

            # Generic suggestions
            analysis["suggestions"] = [
                "Review syntax documentation",
                "Check for typos",
                "Verify statement structure",
            ]

            return analysis

        except Exception as e:
            logger.error(f"Error analyzing generic syntax: {e}")
            return {"error": str(e)}

    def get_language_specific_fixes(self, error_type: str) -> list[str]:
        """Get language-specific fix suggestions.

        Args:
            error_type: Type of error

        Returns:
            List of fix suggestions
        """
        try:
            fixes = {
                "python": {
                    "indentation": [
                        "Use 'python -m py_compile file.py' to check syntax",
                        "Use autopep8 or black to auto-format code",
                        "Enable 'show whitespace' in your editor",
                    ],
                    "syntax": [
                        "Use pylint or flake8 for detailed error checking",
                        "Check Python version compatibility",
                        "Use python -m ast to validate syntax",
                    ],
                },
                "javascript": {
                    "syntax": [
                        "Use ESLint for automatic error detection",
                        "Enable strict mode with 'use strict'",
                        "Use Prettier for automatic formatting",
                    ],
                    "reference": [
                        "Use 'let' or 'const' instead of 'var'",
                        "Check variable scope and hoisting",
                        "Use TypeScript for type safety",
                    ],
                },
                "rust": {
                    "lifetime": [
                        "Use 'cargo clippy' for additional checks",
                        "Read the Rust Book chapter on lifetimes",
                        "Use rust-analyzer for IDE support",
                    ],
                    "type": [
                        "Use 'cargo check' for quick type checking",
                        "Add explicit type annotations",
                        "Use turbofish syntax ::<Type> when needed",
                    ],
                },
                "go": {
                    "syntax": [
                        "Use 'go fmt' to format code",
                        "Use 'go vet' for additional checks",
                        "Enable gopls for IDE support",
                    ],
                    "undefined": [
                        "Use 'go build' to check compilation",
                        "Remove unused imports with goimports",
                        "Check package visibility rules",
                    ],
                },
            }

            lang_fixes = fixes.get(self.language, {})
            return lang_fixes.get(error_type, ["Check language documentation"])

        except Exception as e:
            logger.error(f"Error getting language-specific fixes: {e}")
            return []


class SyntaxErrorPatternMatcher:
    """Advanced pattern matching for syntax errors."""

    def __init__(self):
        """Initialize the pattern matcher."""
        self.compiled_patterns = {}
        self.pattern_metadata = {}
        logger.info("Initialized SyntaxErrorPatternMatcher")

    def add_syntax_pattern(
        self,
        name: str,
        pattern: str,
        language: str,
        error_type: str,
        severity: ErrorSeverity,
    ) -> None:
        """Add a new syntax error pattern.

        Args:
            name: Pattern name
            pattern: Regex pattern
            language: Language this pattern applies to
            error_type: Type of error
            severity: Error severity
        """
        try:
            # Compile pattern
            compiled = re.compile(pattern, re.IGNORECASE | re.MULTILINE)

            # Create unique key for language-specific patterns
            key = f"{language}:{name}"
            self.compiled_patterns[key] = compiled

            # Store metadata
            self.pattern_metadata[key] = {
                "name": name,
                "pattern": pattern,
                "language": language,
                "error_type": error_type,
                "severity": severity,
                "added_at": datetime.now(),
            }

            logger.info(f"Added syntax pattern '{name}' for {language}")

        except re.error as e:
            logger.error(f"Invalid regex pattern: {e}")
            raise ValueError(f"Invalid regex pattern: {e}")
        except Exception as e:
            logger.error(f"Error adding pattern: {e}")
            raise

    def match_syntax_patterns(
        self,
        error_message: str,
        language: str,
    ) -> list[dict[str, Any]]:
        """Match error message against language-specific patterns.

        Args:
            error_message: The error message
            language: Language to match patterns for

        Returns:
            List of pattern match results
        """
        try:
            matches = []

            for key, pattern in self.compiled_patterns.items():
                # Check if pattern is for this language or generic
                if key.startswith((f"{language}:", "generic:")):
                    match = pattern.search(error_message)
                    if match:
                        metadata = self.pattern_metadata[key].copy()
                        metadata["match"] = {
                            "start": match.start(),
                            "end": match.end(),
                            "matched_text": match.group(0),
                            "groups": match.groups(),
                        }
                        matches.append(metadata)

            logger.debug(f"Found {len(matches)} pattern matches for {language}")
            return matches

        except Exception as e:
            logger.error(f"Error matching patterns: {e}")
            return []

    def get_best_syntax_match(
        self,
        error_message: str,
        language: str,
    ) -> dict[str, Any] | None:
        """Get the best matching syntax pattern.

        Args:
            error_message: The error message
            language: Language to match patterns for

        Returns:
            Best match dictionary or None
        """
        try:
            matches = self.match_syntax_patterns(error_message, language)

            if not matches:
                return None

            # Score matches based on specificity and coverage
            best_match = None
            best_score = 0

            for match in matches:
                # Calculate score
                match_length = match["match"]["end"] - match["match"]["start"]
                coverage = match_length / len(error_message)

                # Prefer language-specific over generic
                specificity = 1.0 if match["language"] == language else 0.5

                score = coverage * specificity

                if score > best_score:
                    best_score = score
                    best_match = match

            if best_match:
                best_match["score"] = best_score
                logger.debug(
                    f"Best match: {best_match['name']} (score: {best_score:.2f})",
                )

            return best_match

        except Exception as e:
            logger.error(f"Error getting best match: {e}")
            return None

    def remove_syntax_pattern(self, name: str) -> bool:
        """Remove a syntax pattern by name.

        Args:
            name: Pattern name to remove

        Returns:
            True if removed, False if not found
        """
        try:
            removed = False
            keys_to_remove = []

            for key in self.compiled_patterns:
                if key.endswith(f":{name}"):
                    keys_to_remove.append(key)

            for key in keys_to_remove:
                del self.compiled_patterns[key]
                del self.pattern_metadata[key]
                removed = True
                logger.info(f"Removed pattern '{key}'")

            return removed

        except Exception as e:
            logger.error(f"Error removing pattern: {e}")
            return False

    def list_syntax_patterns(self, language: str) -> list[str]:
        """List all syntax patterns for a language.

        Args:
            language: Language to list patterns for

        Returns:
            List of pattern names
        """
        try:
            patterns = []

            for key in self.compiled_patterns:
                if key.startswith(f"{language}:"):
                    name = key.split(":", 1)[1]
                    patterns.append(name)

            return patterns

        except Exception as e:
            logger.error(f"Error listing patterns: {e}")
            return []


class SyntaxErrorFormatter:
    """Formats syntax errors for user consumption."""

    def __init__(self):
        """Initialize the syntax error formatter."""
        self.formatting_templates = self._load_formatting_templates()
        logger.info("Initialized SyntaxErrorFormatter")

    def _load_formatting_templates(self) -> dict[str, str]:
        """Load formatting templates for syntax errors."""
        templates = {
            "default": (
                "{problem}\n"
                "  File: {file_path}\n"
                "  Line: {line_number}, Column: {column_number}\n"
                "  Error: {error_message}"
            ),
            "detailed": (
                "SYNTAX ERROR DETECTED\n"
                "=" * 50 + "\n"
                "Problem: {problem}\n"
                "Location: {file_path}:{line_number}:{column_number}\n"
                "Language: {language}\n"
                "Error Type: {error_type}\n"
                "Severity: {severity}\n"
                "\nOriginal Error:\n{error_message}\n"
                "\nSuggested Fixes:\n{suggestions}"
            ),
            "compact": ("{file_path}:{line_number}:{column_number}: {problem}"),
        }
        logger.debug(f"Loaded {len(templates)} formatting templates")
        return templates

    def format_syntax_error(
        self,
        error_type: str,
        language: str,
        line_number: int | None,
        column_number: int | None,
        problem_description: str,
    ) -> str:
        """Format a syntax error message.

        Args:
            error_type: Type of error
            language: Language identifier
            line_number: Line number of error
            column_number: Column number of error
            problem_description: Description of the problem

        Returns:
            Formatted error message
        """
        try:
            template = self.formatting_templates.get("default", "")

            message = template.format(
                problem=problem_description,
                file_path=(
                    "Unknown" if not hasattr(self, "file_path") else self.file_path
                ),
                line_number=line_number or "Unknown",
                column_number=column_number or "Unknown",
                error_message=f"{error_type} in {language} code",
            )

            return message

        except Exception as e:
            logger.error(f"Error formatting syntax error: {e}")
            return f"Syntax error: {problem_description}"

    def format_syntax_fix_suggestions(
        self,
        suggestions: list[str],
        language: str,
    ) -> str:
        """Format syntax fix suggestions.

        Args:
            suggestions: List of suggestions
            language: Language identifier

        Returns:
            Formatted suggestions
        """
        try:
            if not suggestions:
                return f"No specific suggestions available for {language}"

            formatted = f"Suggested fixes for {language}:\n"
            for i, suggestion in enumerate(suggestions, 1):
                formatted += f"  {i}. {suggestion}\n"

            return formatted.strip()

        except Exception as e:
            logger.error(f"Error formatting suggestions: {e}")
            return "Error formatting suggestions"

    def generate_syntax_error_report(
        self,
        errors: list[ClassifiedError],
        language: str,
    ) -> str:
        """Generate comprehensive syntax error report.

        Args:
            errors: List of classified errors
            language: Language identifier

        Returns:
            Formatted report
        """
        try:
            report = []
            report.append("=" * 60)
            report.append(f"SYNTAX ERROR REPORT - {language.upper()}")
            report.append("=" * 60)
            report.append(f"Total Errors: {len(errors)}")
            report.append("")

            # Group errors by type
            error_types = {}
            for error in errors:
                error_type = (
                    error.message.split(":")[0] if ":" in error.message else "Unknown"
                )
                if error_type not in error_types:
                    error_types[error_type] = []
                error_types[error_type].append(error)

            # Report by type
            for error_type, type_errors in error_types.items():
                report.append(f"\n{error_type} ({len(type_errors)} occurrences):")
                report.append("-" * 40)

                for error in type_errors[:3]:  # Show first 3 of each type
                    report.append(f"  • {error.message}")
                    if error.context.line_number:
                        report.append(f"    Line {error.context.line_number}")
                    if error.suggested_actions:
                        report.append(f"    Fix: {error.suggested_actions[0]}")

                if len(type_errors) > 3:
                    report.append(f"  ... and {len(type_errors) - 3} more")

            # Summary
            report.append("")
            report.append("SUMMARY:")
            report.append("-" * 40)

            # Severity distribution
            severity_counts = {}
            for error in errors:
                severity = error.severity.value
                severity_counts[severity] = severity_counts.get(severity, 0) + 1

            for severity, count in severity_counts.items():
                report.append(f"  {severity.upper()}: {count}")

            # Recommendations
            report.append("")
            report.append("RECOMMENDATIONS:")
            report.append("-" * 40)
            report.append("  1. Fix critical errors first")
            report.append("  2. Use a linter for automatic detection")
            report.append("  3. Enable syntax highlighting in your editor")
            report.append(f"  4. Review {language} syntax documentation")

            report.append("")
            report.append("=" * 60)

            return "\n".join(report)

        except Exception as e:
            logger.error(f"Error generating report: {e}")
            return f"Error generating syntax error report: {e}"

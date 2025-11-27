"""Error classification system for Phase 1.7 - Smart Error Handling & User Guidance."""

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class ErrorSeverity(Enum):
    """Error severity levels."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """Error categories for classification."""

    SYNTAX = "syntax"
    COMPATIBILITY = "compatibility"
    GRAMMAR = "grammar"
    PARSING = "parsing"
    CONFIGURATION = "configuration"
    SYSTEM = "system"
    NETWORK = "network"
    PERMISSION = "permission"
    UNKNOWN = "unknown"


class ErrorSource(Enum):
    """Source of the error."""

    TREE_SITTER = "tree_sitter"
    GRAMMAR_LOADER = "grammar_loader"
    METADATA_EXTRACTOR = "metadata_extractor"
    VERSION_DETECTOR = "version_detector"
    COMPATIBILITY_CHECKER = "compatibility_checker"
    USER_INPUT = "user_input"
    SYSTEM = "system"
    EXTERNAL = "external"


@dataclass
class ErrorContext:
    """Context information for an error."""

    file_path: str | None = None
    line_number: int | None = None
    column_number: int | None = None
    language: str | None = None
    grammar_version: str | None = None
    user_agent: str | None = None
    timestamp: datetime = field(default_factory=datetime.now)
    session_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "file_path": self.file_path,
            "line_number": self.line_number,
            "column_number": self.column_number,
            "language": self.language,
            "grammar_version": self.grammar_version,
            "user_agent": self.user_agent,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "session_id": self.session_id,
        }

    def __str__(self) -> str:
        """String representation of error context."""
        parts = []
        if self.file_path:
            parts.append(f"File: {self.file_path}")
        if self.line_number is not None:
            parts.append(f"Line: {self.line_number}")
        if self.column_number is not None:
            parts.append(f"Column: {self.column_number}")
        if self.language:
            parts.append(f"Language: {self.language}")
        return " | ".join(parts) if parts else "No context available"


@dataclass
class ClassifiedError:
    """A classified error with all relevant information."""

    error_id: str
    message: str
    category: ErrorCategory
    severity: ErrorSeverity
    source: ErrorSource
    context: ErrorContext
    raw_error: Any | None = None
    suggested_actions: list[str] = field(default_factory=list)
    related_errors: list[str] = field(default_factory=list)
    confidence: float = 1.0

    def __post_init__(self):
        """Validate error data."""
        if not self.error_id or not self.message:
            raise ValueError("Error ID and message are required")
        if not isinstance(self.category, ErrorCategory):
            raise ValueError("Category must be ErrorCategory enum")
        if not isinstance(self.severity, ErrorSeverity):
            raise ValueError("Severity must be ErrorSeverity enum")
        if not isinstance(self.source, ErrorSource):
            raise ValueError("Source must be ErrorSource enum")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("Confidence must be between 0.0 and 1.0")

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "error_id": self.error_id,
            "message": self.message,
            "category": self.category.value,
            "severity": self.severity.value,
            "source": self.source.value,
            "context": self.context.to_dict(),
            "raw_error": str(self.raw_error) if self.raw_error else None,
            "suggested_actions": self.suggested_actions,
            "related_errors": self.related_errors,
            "confidence": self.confidence,
        }

    def __str__(self) -> str:
        """String representation of classified error."""
        return (
            f"[{self.severity.value.upper()}] {self.category.value}: {self.message} "
            f"(ID: {self.error_id}, Confidence: {self.confidence:.2f})"
        )

    def add_suggested_action(self, action: str) -> None:
        """Add a suggested action for resolving this error."""
        if action and action not in self.suggested_actions:
            self.suggested_actions.append(action)
            logger.debug(f"Added suggested action to error {self.error_id}: {action}")

    def add_related_error(self, error_id: str) -> None:
        """Add a related error ID."""
        if (
            error_id
            and error_id != self.error_id
            and error_id not in self.related_errors
        ):
            self.related_errors.append(error_id)
            logger.debug(f"Added related error {error_id} to error {self.error_id}")

    def update_confidence(self, confidence: float) -> None:
        """Update the confidence level of this classification."""
        if not 0.0 <= confidence <= 1.0:
            raise ValueError("Confidence must be between 0.0 and 1.0")
        self.confidence = confidence
        logger.debug(
            f"Updated confidence for error {self.error_id} to {confidence:.2f}",
        )


class ErrorClassifier:
    """Main class for classifying errors into categories and severity levels."""

    def __init__(self):
        """Initialize the error classifier."""
        self.patterns = self._load_error_patterns()
        self.classification_rules = self._load_classification_rules()
        self.severity_mapping = self._load_severity_mapping()
        self.error_counter = 0
        logger.info("Initialized ErrorClassifier")

    def _load_error_patterns(self) -> dict[str, list[re.Pattern]]:
        """Load regex patterns for error detection."""
        patterns = {
            ErrorCategory.SYNTAX: [
                re.compile(r"syntax\s+error", re.IGNORECASE),
                re.compile(r"unexpected\s+token", re.IGNORECASE),
                re.compile(r"expected\s+.*\s+but\s+got", re.IGNORECASE),
                re.compile(r"invalid\s+syntax", re.IGNORECASE),
                re.compile(r"unterminated\s+string", re.IGNORECASE),
                re.compile(r"missing\s+(bracket|parenthesis|brace)", re.IGNORECASE),
            ],
            ErrorCategory.COMPATIBILITY: [
                re.compile(r"version\s+mismatch", re.IGNORECASE),
                re.compile(r"incompatible\s+version", re.IGNORECASE),
                re.compile(r"requires\s+.*\s+version", re.IGNORECASE),
                re.compile(r"not\s+supported\s+in\s+version", re.IGNORECASE),
                re.compile(r"deprecated\s+in\s+version", re.IGNORECASE),
            ],
            ErrorCategory.GRAMMAR: [
                re.compile(r"grammar\s+error", re.IGNORECASE),
                re.compile(r"failed\s+to\s+load\s+grammar", re.IGNORECASE),
                re.compile(r"invalid\s+grammar", re.IGNORECASE),
                re.compile(r"grammar\s+not\s+found", re.IGNORECASE),
                re.compile(r"tree-sitter.*error", re.IGNORECASE),
            ],
            ErrorCategory.PARSING: [
                re.compile(r"parse\s+error", re.IGNORECASE),
                re.compile(r"failed\s+to\s+parse", re.IGNORECASE),
                re.compile(r"parsing\s+failed", re.IGNORECASE),
                re.compile(r"invalid\s+ast", re.IGNORECASE),
                re.compile(r"cannot\s+parse", re.IGNORECASE),
            ],
            ErrorCategory.CONFIGURATION: [
                re.compile(r"configuration\s+error", re.IGNORECASE),
                re.compile(r"invalid\s+configuration", re.IGNORECASE),
                re.compile(r"config\s+file\s+not\s+found", re.IGNORECASE),
                re.compile(r"missing\s+configuration", re.IGNORECASE),
                re.compile(r"malformed\s+config", re.IGNORECASE),
            ],
            ErrorCategory.SYSTEM: [
                re.compile(r"system\s+error", re.IGNORECASE),
                re.compile(r"out\s+of\s+memory", re.IGNORECASE),
                re.compile(r"segmentation\s+fault", re.IGNORECASE),
                re.compile(r"stack\s+overflow", re.IGNORECASE),
                re.compile(r"resource\s+exhausted", re.IGNORECASE),
            ],
            ErrorCategory.NETWORK: [
                re.compile(r"network\s+error", re.IGNORECASE),
                re.compile(r"connection\s+refused", re.IGNORECASE),
                re.compile(r"timeout", re.IGNORECASE),
                re.compile(r"dns\s+resolution\s+failed", re.IGNORECASE),
                re.compile(r"cannot\s+connect", re.IGNORECASE),
            ],
            ErrorCategory.PERMISSION: [
                re.compile(r"permission\s+denied", re.IGNORECASE),
                re.compile(r"access\s+denied", re.IGNORECASE),
                re.compile(r"unauthorized", re.IGNORECASE),
                re.compile(r"insufficient\s+privileges", re.IGNORECASE),
                re.compile(r"read-only", re.IGNORECASE),
            ],
        }
        logger.debug(f"Loaded {sum(len(p) for p in patterns.values())} error patterns")
        return patterns

    def _load_classification_rules(self) -> dict[str, dict[str, Any]]:
        """Load rules for error classification."""
        rules = {
            "priority_order": [
                ErrorSeverity.CRITICAL,
                ErrorSeverity.ERROR,
                ErrorSeverity.WARNING,
                ErrorSeverity.INFO,
            ],
            "source_detection": {
                "tree_sitter": ["tree-sitter", "ts_", "TSNode", "TSTree"],
                "grammar_loader": ["grammar", "load_grammar", ".so", "compile"],
                "metadata_extractor": ["metadata", "extract", "analyze"],
                "version_detector": [
                    "version",
                    "detect",
                    "python_version",
                    "node_version",
                ],
                "compatibility_checker": ["compatible", "compatibility", "mismatch"],
                "user_input": ["user", "input", "argument", "parameter"],
                "system": ["system", "os", "memory", "cpu", "disk"],
                "external": ["network", "http", "api", "remote"],
            },
            "confidence_adjustments": {
                "multiple_patterns_matched": 0.1,
                "context_available": 0.05,
                "known_error_format": 0.1,
                "source_identified": 0.05,
            },
        }
        logger.debug("Loaded classification rules")
        return rules

    def _load_severity_mapping(self) -> dict[str, ErrorSeverity]:
        """Load mapping of error types to severity levels."""
        mapping = {
            # Critical patterns
            "segmentation fault": ErrorSeverity.CRITICAL,
            "stack overflow": ErrorSeverity.CRITICAL,
            "out of memory": ErrorSeverity.CRITICAL,
            "system error": ErrorSeverity.CRITICAL,
            # Error patterns
            "syntax error": ErrorSeverity.ERROR,
            "parse error": ErrorSeverity.ERROR,
            "grammar error": ErrorSeverity.ERROR,
            "permission denied": ErrorSeverity.ERROR,
            "file not found": ErrorSeverity.ERROR,
            # Warning patterns
            "deprecated": ErrorSeverity.WARNING,
            "version mismatch": ErrorSeverity.WARNING,
            "incompatible": ErrorSeverity.WARNING,
            "not recommended": ErrorSeverity.WARNING,
            # Info patterns
            "notice": ErrorSeverity.INFO,
            "information": ErrorSeverity.INFO,
            "hint": ErrorSeverity.INFO,
            "suggestion": ErrorSeverity.INFO,
        }
        logger.debug(f"Loaded severity mapping for {len(mapping)} patterns")
        return mapping

    def classify_error(
        self,
        error_message: str,
        raw_error: Any | None = None,
        context: ErrorContext | None = None,
    ) -> ClassifiedError:
        """Classify an error message into categories and severity."""
        try:
            # Generate unique error ID
            self.error_counter += 1
            error_id = f"ERR_{datetime.now().strftime('%Y%m%d%H%M%S')}_{self.error_counter:04d}"

            # Create context if not provided
            if context is None:
                context = ErrorContext()

            # Detect category
            category = self.detect_error_category(error_message)

            # Determine severity
            severity = self.determine_error_severity(error_message, category)

            # Identify source
            source = self.identify_error_source(error_message, raw_error)

            # Extract additional context
            extracted_context = self.extract_error_context(error_message, raw_error)
            if extracted_context:
                # Merge extracted context with provided context
                for key, value in extracted_context.__dict__.items():
                    if value is not None and getattr(context, key) is None:
                        setattr(context, key, value)

            # Generate suggested actions
            suggested_actions = self.generate_suggested_actions(category, severity)

            # Calculate confidence
            patterns_matched = self._count_pattern_matches(error_message)
            confidence = self.calculate_confidence(error_message, patterns_matched)

            # Create classified error
            classified_error = ClassifiedError(
                error_id=error_id,
                message=error_message,
                category=category,
                severity=severity,
                source=source,
                context=context,
                raw_error=raw_error,
                suggested_actions=suggested_actions,
                related_errors=[],
                confidence=confidence,
            )

            logger.info(
                f"Classified error {error_id}: {category.value}/{severity.value} "
                f"(confidence: {confidence:.2f})",
            )
            return classified_error

        except Exception as e:
            logger.error(f"Error classifying error message: {e}")
            # Return a default classification for unknown errors
            return ClassifiedError(
                error_id=f"ERR_UNKNOWN_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                message=error_message,
                category=ErrorCategory.UNKNOWN,
                severity=ErrorSeverity.ERROR,
                source=ErrorSource.EXTERNAL,
                context=context or ErrorContext(),
                raw_error=raw_error,
                confidence=0.0,
            )

    def detect_error_category(self, error_message: str) -> ErrorCategory:
        """Detect the category of an error from its message."""
        try:
            error_lower = error_message.lower()
            best_match = ErrorCategory.UNKNOWN
            best_score = 0

            for category, patterns in self.patterns.items():
                score = 0
                for pattern in patterns:
                    if pattern.search(error_message):
                        score += 1

                if score > best_score:
                    best_score = score
                    best_match = category

            logger.debug(f"Detected category {best_match.value} for error message")
            return best_match

        except Exception as e:
            logger.error(f"Error detecting category: {e}")
            return ErrorCategory.UNKNOWN

    def determine_error_severity(
        self,
        error_message: str,
        category: ErrorCategory,
    ) -> ErrorSeverity:
        """Determine the severity level of an error."""
        try:
            error_lower = error_message.lower()

            # Check direct severity mapping
            for pattern, severity in self.severity_mapping.items():
                if pattern in error_lower:
                    logger.debug(
                        f"Determined severity {severity.value} from pattern '{pattern}'",
                    )
                    return severity

            # Default severity based on category
            category_severity = {
                ErrorCategory.SYNTAX: ErrorSeverity.ERROR,
                ErrorCategory.COMPATIBILITY: ErrorSeverity.WARNING,
                ErrorCategory.GRAMMAR: ErrorSeverity.ERROR,
                ErrorCategory.PARSING: ErrorSeverity.ERROR,
                ErrorCategory.CONFIGURATION: ErrorSeverity.WARNING,
                ErrorCategory.SYSTEM: ErrorSeverity.CRITICAL,
                ErrorCategory.NETWORK: ErrorSeverity.ERROR,
                ErrorCategory.PERMISSION: ErrorSeverity.ERROR,
                ErrorCategory.UNKNOWN: ErrorSeverity.WARNING,
            }

            severity = category_severity.get(category, ErrorSeverity.WARNING)
            logger.debug(
                f"Determined severity {severity.value} from category {category.value}",
            )
            return severity

        except Exception as e:
            logger.error(f"Error determining severity: {e}")
            return ErrorSeverity.WARNING

    def identify_error_source(self, error_message: str, raw_error: Any) -> ErrorSource:
        """Identify the source of an error."""
        try:
            error_lower = error_message.lower()

            # Check raw error type if available
            if raw_error:
                raw_str = str(type(raw_error).__name__).lower()
                for source, keywords in self.classification_rules[
                    "source_detection"
                ].items():
                    if any(keyword in raw_str for keyword in keywords):
                        source_enum = ErrorSource[source.upper()]
                        logger.debug(
                            f"Identified source {source_enum.value} from raw error type",
                        )
                        return source_enum

            # Check error message for source indicators
            for source, keywords in self.classification_rules[
                "source_detection"
            ].items():
                if any(keyword in error_lower for keyword in keywords):
                    source_enum = ErrorSource[source.upper()]
                    logger.debug(
                        f"Identified source {source_enum.value} from error message",
                    )
                    return source_enum

            return ErrorSource.EXTERNAL

        except Exception as e:
            logger.error(f"Error identifying source: {e}")
            return ErrorSource.EXTERNAL

    def extract_error_context(self, error_message: str, raw_error: Any) -> ErrorContext:
        """Extract context information from an error."""
        try:
            context = ErrorContext()

            # Extract file path
            file_pattern = re.compile(r'(?:file|File)\s*["\']?([^"\':\s]+\.[a-zA-Z]+)')
            file_match = file_pattern.search(error_message)
            if file_match:
                context.file_path = file_match.group(1)

            # Extract line number
            line_pattern = re.compile(r"(?:line|Line)\s*:?\s*(\d+)")
            line_match = line_pattern.search(error_message)
            if line_match:
                context.line_number = int(line_match.group(1))

            # Extract column number
            column_pattern = re.compile(r"(?:column|Column|col|Col)\s*:?\s*(\d+)")
            column_match = column_pattern.search(error_message)
            if column_match:
                context.column_number = int(column_match.group(1))

            # Extract language
            lang_pattern = re.compile(
                r"\b(python|javascript|typescript|rust|go|java|cpp|c)\b",
                re.IGNORECASE,
            )
            lang_match = lang_pattern.search(error_message)
            if lang_match:
                context.language = lang_match.group(1).lower()

            logger.debug(f"Extracted context: {context}")
            return context

        except Exception as e:
            logger.error(f"Error extracting context: {e}")
            return ErrorContext()

    def generate_suggested_actions(
        self,
        category: ErrorCategory,
        severity: ErrorSeverity,
    ) -> list[str]:
        """Generate suggested actions for resolving an error."""
        try:
            actions = []

            # Category-specific suggestions
            category_actions = {
                ErrorCategory.SYNTAX: [
                    "Check for missing or mismatched brackets, parentheses, or braces",
                    "Verify proper indentation (especially for Python)",
                    "Look for unterminated strings or comments",
                    "Review language syntax documentation",
                ],
                ErrorCategory.COMPATIBILITY: [
                    "Check language version requirements",
                    "Update to a compatible grammar version",
                    "Consider using a different language version",
                    "Review compatibility documentation",
                ],
                ErrorCategory.GRAMMAR: [
                    "Verify grammar file exists and is accessible",
                    "Rebuild or recompile the grammar if necessary",
                    "Check grammar version compatibility",
                    "Ensure Tree-sitter is properly installed",
                ],
                ErrorCategory.PARSING: [
                    "Verify file syntax is correct",
                    "Check for unsupported language features",
                    "Ensure file encoding is correct (UTF-8)",
                    "Try parsing a simpler version of the file",
                ],
                ErrorCategory.CONFIGURATION: [
                    "Review configuration file syntax",
                    "Check for required configuration parameters",
                    "Verify configuration file path",
                    "Use default configuration as a template",
                ],
                ErrorCategory.SYSTEM: [
                    "Check system resources (memory, CPU, disk)",
                    "Restart the application",
                    "Check system logs for more details",
                    "Contact system administrator if issue persists",
                ],
                ErrorCategory.NETWORK: [
                    "Check network connectivity",
                    "Verify firewall settings",
                    "Check proxy configuration if applicable",
                    "Retry the operation",
                ],
                ErrorCategory.PERMISSION: [
                    "Check file/directory permissions",
                    "Run with appropriate privileges",
                    "Verify user has necessary access rights",
                    "Check file ownership",
                ],
                ErrorCategory.UNKNOWN: [
                    "Review the full error message for clues",
                    "Check application logs for more details",
                    "Try reproducing the error with debug mode enabled",
                    "Search for similar issues in documentation",
                ],
            }

            # Add category-specific actions
            if category in category_actions:
                actions.extend(category_actions[category][:2])  # Take top 2 suggestions

            # Add severity-specific actions
            if severity == ErrorSeverity.CRITICAL:
                actions.insert(0, "IMMEDIATE ACTION REQUIRED: This is a critical error")
            elif severity == ErrorSeverity.ERROR:
                actions.insert(0, "This error needs to be resolved before continuing")
            elif severity == ErrorSeverity.WARNING:
                actions.insert(
                    0,
                    "Consider addressing this warning to prevent future issues",
                )

            logger.debug(f"Generated {len(actions)} suggested actions")
            return actions

        except Exception as e:
            logger.error(f"Error generating suggested actions: {e}")
            return ["Review the error message and try again"]

    def calculate_confidence(
        self,
        error_message: str,
        patterns_matched: list[str],
    ) -> float:
        """Calculate confidence level for error classification."""
        try:
            confidence = 0.5  # Base confidence

            # Adjust based on number of patterns matched
            if len(patterns_matched) > 0:
                confidence += min(len(patterns_matched) * 0.1, 0.3)

            # Adjust based on error message structure
            if re.match(r"^[A-Z]+Error:", error_message):
                confidence += self.classification_rules["confidence_adjustments"][
                    "known_error_format"
                ]

            # Adjust if multiple categories matched
            if len(patterns_matched) > 1:
                confidence += self.classification_rules["confidence_adjustments"][
                    "multiple_patterns_matched"
                ]

            # Cap confidence at 1.0
            confidence = min(confidence, 1.0)

            logger.debug(f"Calculated confidence: {confidence:.2f}")
            return confidence

        except Exception as e:
            logger.error(f"Error calculating confidence: {e}")
            return 0.5

    def _count_pattern_matches(self, error_message: str) -> list[str]:
        """Count how many patterns match the error message."""
        matches = []
        for category, patterns in self.patterns.items():
            for pattern in patterns:
                if pattern.search(error_message):
                    matches.append(f"{category.value}:{pattern.pattern}")
        return matches

    def batch_classify_errors(self, error_messages: list[str]) -> list[ClassifiedError]:
        """Classify multiple errors in batch."""
        try:
            classified_errors = []

            for message in error_messages:
                classified = self.classify_error(message)
                classified_errors.append(classified)

                # Look for related errors
                for other in classified_errors[:-1]:
                    # Check if errors are related (similar category or message)
                    if (
                        other.category == classified.category
                        or self._calculate_similarity(other.message, classified.message)
                        > 0.7
                    ):
                        classified.add_related_error(other.error_id)
                        other.add_related_error(classified.error_id)

            logger.info(f"Batch classified {len(classified_errors)} errors")
            return classified_errors

        except Exception as e:
            logger.error(f"Error in batch classification: {e}")
            return []

    def _calculate_similarity(self, msg1: str, msg2: str) -> float:
        """Calculate similarity between two error messages."""
        try:
            # Simple word-based similarity
            words1 = set(msg1.lower().split())
            words2 = set(msg2.lower().split())

            if not words1 or not words2:
                return 0.0

            intersection = words1.intersection(words2)
            union = words1.union(words2)

            return len(intersection) / len(union)

        except Exception:
            return 0.0

    def update_classification_rules(self, new_rules: dict[str, Any]) -> None:
        """Update classification rules dynamically."""
        try:
            self.classification_rules.update(new_rules)
            logger.info(f"Updated classification rules with {len(new_rules)} new rules")
        except Exception as e:
            logger.error(f"Error updating classification rules: {e}")

    def export_classification_rules(self, output_path: str) -> None:
        """Export current classification rules to file."""
        try:
            output_path = Path(output_path)

            # Prepare exportable data
            export_data = {
                "classification_rules": self.classification_rules,
                "severity_mapping": {
                    k: v.value for k, v in self.severity_mapping.items()
                },
                "patterns": {
                    cat.value: [p.pattern for p in patterns]
                    for cat, patterns in self.patterns.items()
                },
                "exported_at": datetime.now().isoformat(),
            }

            with open(output_path, "w") as f:
                json.dump(export_data, f, indent=2)

            logger.info(f"Exported classification rules to {output_path}")

        except Exception as e:
            logger.error(f"Error exporting classification rules: {e}")
            raise

    def import_classification_rules(self, input_path: str) -> None:
        """Import classification rules from file."""
        try:
            input_path = Path(input_path)

            with open(input_path) as f:
                import_data = json.load(f)

            # Update classification rules
            if "classification_rules" in import_data:
                self.classification_rules = import_data["classification_rules"]

            # Update severity mapping
            if "severity_mapping" in import_data:
                self.severity_mapping = {
                    k: ErrorSeverity(v)
                    for k, v in import_data["severity_mapping"].items()
                }

            # Update patterns
            if "patterns" in import_data:
                self.patterns = {}
                for cat_str, pattern_strs in import_data["patterns"].items():
                    category = ErrorCategory(cat_str)
                    self.patterns[category] = [re.compile(p) for p in pattern_strs]

            logger.info(f"Imported classification rules from {input_path}")

        except Exception as e:
            logger.error(f"Error importing classification rules: {e}")
            raise


class ErrorPatternMatcher:
    """Advanced pattern matching for error classification."""

    def __init__(self):
        """Initialize the pattern matcher."""
        self.compiled_patterns = {}
        self.pattern_metadata = {}
        logger.info("Initialized ErrorPatternMatcher")

    def add_pattern(
        self,
        name: str,
        pattern: str,
        category: ErrorCategory,
        severity: ErrorSeverity,
        confidence: float = 1.0,
    ) -> None:
        """Add a new error pattern."""
        try:
            # Compile the pattern
            compiled = re.compile(pattern, re.IGNORECASE)
            self.compiled_patterns[name] = compiled

            # Store metadata
            self.pattern_metadata[name] = {
                "pattern": pattern,
                "category": category,
                "severity": severity,
                "confidence": confidence,
                "added_at": datetime.now(),
            }

            logger.info(f"Added pattern '{name}' for {category.value}/{severity.value}")

        except re.error as e:
            logger.error(f"Invalid regex pattern '{pattern}': {e}")
            raise ValueError(f"Invalid regex pattern: {e}")
        except Exception as e:
            logger.error(f"Error adding pattern '{name}': {e}")
            raise

    def match_patterns(self, error_message: str) -> list[dict[str, Any]]:
        """Match error message against all patterns."""
        try:
            matches = []

            for name, pattern in self.compiled_patterns.items():
                match = pattern.search(error_message)
                if match:
                    metadata = self.pattern_metadata[name].copy()
                    metadata["name"] = name
                    metadata["match"] = {
                        "start": match.start(),
                        "end": match.end(),
                        "matched_text": match.group(0),
                    }
                    matches.append(metadata)

            logger.debug(f"Found {len(matches)} pattern matches")
            return matches

        except Exception as e:
            logger.error(f"Error matching patterns: {e}")
            return []

    def get_best_match(self, error_message: str) -> dict[str, Any] | None:
        """Get the best matching pattern for an error message."""
        try:
            matches = self.match_patterns(error_message)

            if not matches:
                return None

            # Score matches based on confidence and match length
            best_match = None
            best_score = 0

            for match in matches:
                # Calculate score based on confidence and match coverage
                match_length = match["match"]["end"] - match["match"]["start"]
                coverage = match_length / len(error_message)
                score = match["confidence"] * (0.5 + 0.5 * coverage)

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

    def remove_pattern(self, name: str) -> bool:
        """Remove a pattern by name."""
        try:
            if name in self.compiled_patterns:
                del self.compiled_patterns[name]
                del self.pattern_metadata[name]
                logger.info(f"Removed pattern '{name}'")
                return True
            logger.warning(f"Pattern '{name}' not found")
            return False

        except Exception as e:
            logger.error(f"Error removing pattern '{name}': {e}")
            return False

    def list_patterns(self) -> list[str]:
        """List all pattern names."""
        return list(self.compiled_patterns.keys())


class ErrorConfidenceScorer:
    """Scores confidence levels for error classifications."""

    def __init__(self):
        """Initialize the confidence scorer."""
        self.scoring_rules = self._load_scoring_rules()
        logger.info("Initialized ErrorConfidenceScorer")

    def _load_scoring_rules(self) -> dict[str, float]:
        """Load rules for confidence scoring."""
        rules = {
            # Base scores for different factors
            "base_score": 0.5,
            "pattern_match": 0.15,
            "context_present": 0.1,
            "source_identified": 0.1,
            "known_format": 0.1,
            "multiple_indicators": 0.05,
            # Penalties
            "ambiguous_message": -0.1,
            "no_patterns_matched": -0.2,
            "unknown_category": -0.15,
            # Category confidence modifiers
            "category_confidence": {
                ErrorCategory.SYNTAX: 0.1,
                ErrorCategory.COMPATIBILITY: 0.05,
                ErrorCategory.GRAMMAR: 0.1,
                ErrorCategory.PARSING: 0.1,
                ErrorCategory.CONFIGURATION: 0.05,
                ErrorCategory.SYSTEM: 0.15,
                ErrorCategory.NETWORK: 0.1,
                ErrorCategory.PERMISSION: 0.15,
                ErrorCategory.UNKNOWN: -0.2,
            },
        }
        logger.debug("Loaded confidence scoring rules")
        return rules

    def score_classification(
        self,
        error_message: str,
        category: ErrorCategory,
        patterns_matched: list[str],
        context: ErrorContext | None = None,
    ) -> float:
        """Score the confidence of a classification."""
        try:
            score = self.scoring_rules["base_score"]

            # Add score for pattern matches
            if patterns_matched:
                score += min(
                    len(patterns_matched) * self.scoring_rules["pattern_match"],
                    0.3,
                )
            else:
                score += self.scoring_rules["no_patterns_matched"]

            # Add score for context
            if context and (context.file_path or context.line_number):
                score += self.scoring_rules["context_present"]

            # Add category-specific confidence
            if category in self.scoring_rules["category_confidence"]:
                score += self.scoring_rules["category_confidence"][category]

            # Check for known error format
            if re.match(r"^[A-Z][a-zA-Z]*Error:", error_message):
                score += self.scoring_rules["known_format"]

            # Check for ambiguous message
            if len(error_message.split()) < 3:
                score += self.scoring_rules["ambiguous_message"]

            # Adjust for context if available
            if context:
                score = self.adjust_confidence_for_context(score, context)

            # Ensure score is between 0 and 1
            score = max(0.0, min(1.0, score))

            logger.debug(f"Calculated confidence score: {score:.2f}")
            return score

        except Exception as e:
            logger.error(f"Error scoring classification: {e}")
            return 0.5

    def adjust_confidence_for_context(
        self,
        base_confidence: float,
        context: ErrorContext,
    ) -> float:
        """Adjust confidence based on context information."""
        try:
            adjusted = base_confidence

            # Boost confidence if we have specific location information
            if context.line_number and context.column_number:
                adjusted += 0.05

            # Boost confidence if we have language information
            if context.language:
                adjusted += 0.03

            # Boost confidence if we have grammar version
            if context.grammar_version:
                adjusted += 0.02

            # Ensure adjusted score doesn't exceed 1.0
            adjusted = min(1.0, adjusted)

            logger.debug(
                f"Adjusted confidence from {base_confidence:.2f} to {adjusted:.2f}",
            )
            return adjusted

        except Exception as e:
            logger.error(f"Error adjusting confidence: {e}")
            return base_confidence

    def get_confidence_explanation(self, confidence: float) -> str:
        """Get human-readable explanation of confidence score."""
        try:
            if confidence >= 0.9:
                return "Very High - Classification is almost certain"
            if confidence >= 0.75:
                return "High - Classification is likely correct"
            if confidence >= 0.6:
                return "Moderate - Classification is probable"
            if confidence >= 0.4:
                return "Low - Classification is uncertain"
            return "Very Low - Classification is highly uncertain"

        except Exception as e:
            logger.error(f"Error getting confidence explanation: {e}")
            return "Unknown confidence level"

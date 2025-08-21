"""Compatibility error detection for Phase 1.7 - Smart Error Handling & User Guidance."""

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from ..error_handling.classifier import (
    ClassifiedError,
    ErrorCategory,
    ErrorContext,
    ErrorSeverity,
    ErrorSource,
)
from ..languages.compatibility.database import CompatibilityDatabase
from ..languages.compatibility.schema import (
    CompatibilityLevel,
    GrammarVersion,
    LanguageVersion,
)
from ..languages.version_detection.cpp_detector import CppVersionDetector
from ..languages.version_detection.go_detector import GoVersionDetector
from ..languages.version_detection.java_detector import JavaVersionDetector
from ..languages.version_detection.javascript_detector import JavaScriptVersionDetector

# Import from completed tasks
from ..languages.version_detection.python_detector import PythonVersionDetector
from ..languages.version_detection.rust_detector import RustVersionDetector

logger = logging.getLogger(__name__)


class CompatibilityErrorDetector:
    """Detects version compatibility issues between languages and grammars."""

    def __init__(self, compatibility_db: CompatibilityDatabase):
        """Initialize the compatibility error detector.

        Args:
            compatibility_db: Compatibility database instance
        """
        self.compatibility_db = compatibility_db
        self.version_detectors = self._initialize_version_detectors()
        self.compatibility_patterns = self._load_compatibility_patterns()
        self.error_counter = 0
        logger.info("Initialized CompatibilityErrorDetector")

    def _initialize_version_detectors(self) -> dict[str, Any]:
        """Initialize version detectors for all supported languages."""
        try:
            detectors = {
                "python": PythonVersionDetector(),
                "javascript": JavaScriptVersionDetector(),
                "rust": RustVersionDetector(),
                "go": GoVersionDetector(),
                "cpp": CppVersionDetector(),
                "c": CppVersionDetector(),  # Use same detector for C
                "java": JavaVersionDetector(),
            }
            logger.debug(f"Initialized {len(detectors)} version detectors")
            return detectors

        except Exception as e:
            logger.error(f"Error initializing version detectors: {e}")
            return {}

    def _load_compatibility_patterns(self) -> dict[str, list[re.Pattern]]:
        """Load patterns for detecting compatibility errors."""
        patterns = {
            "version_mismatch": [
                re.compile(
                    r"version\s+(\d+\.\d+(?:\.\d+)?)\s+.*\s+required\s+(\d+\.\d+(?:\.\d+)?)",
                    re.IGNORECASE,
                ),
                re.compile(r"incompatible\s+.*\s+version", re.IGNORECASE),
                re.compile(
                    r"requires\s+.*\s+version\s+(\d+\.\d+(?:\.\d+)?)",
                    re.IGNORECASE,
                ),
                re.compile(r"expected\s+version\s+(\d+\.\d+(?:\.\d+)?)", re.IGNORECASE),
            ],
            "feature_unsupported": [
                re.compile(r"feature\s+.*\s+not\s+supported", re.IGNORECASE),
                re.compile(r"unsupported\s+.*\s+feature", re.IGNORECASE),
                re.compile(r"not\s+available\s+in\s+.*\s+version", re.IGNORECASE),
                re.compile(r"requires\s+.*\s+feature", re.IGNORECASE),
            ],
            "deprecated": [
                re.compile(
                    r"deprecated\s+in\s+version\s+(\d+\.\d+(?:\.\d+)?)",
                    re.IGNORECASE,
                ),
                re.compile(
                    r"removed\s+in\s+version\s+(\d+\.\d+(?:\.\d+)?)",
                    re.IGNORECASE,
                ),
                re.compile(r"no\s+longer\s+supported", re.IGNORECASE),
                re.compile(r"obsolete\s+.*\s+version", re.IGNORECASE),
            ],
            "breaking_change": [
                re.compile(r"breaking\s+change", re.IGNORECASE),
                re.compile(r"incompatible\s+api\s+change", re.IGNORECASE),
                re.compile(r"migration\s+required", re.IGNORECASE),
                re.compile(r"not\s+backward\s+compatible", re.IGNORECASE),
            ],
        }
        logger.debug(
            f"Loaded {sum(len(p) for p in patterns.values())} compatibility patterns",
        )
        return patterns

    def detect_compatibility_errors(
        self,
        error_message: str,
        file_path: Path | None = None,
        language: str | None = None,
    ) -> list[ClassifiedError]:
        """Detect compatibility errors from error messages and file analysis.

        Args:
            error_message: The error message to analyze
            file_path: Optional path to the source file
            language: Optional language identifier

        Returns:
            List of ClassifiedError objects for detected compatibility issues
        """
        try:
            errors = []

            # Detect language if not provided
            if not language and file_path:
                language = self._detect_language_from_file(file_path)

            # Check for version mismatch patterns in error message
            for pattern_type, patterns in self.compatibility_patterns.items():
                for pattern in patterns:
                    if pattern.search(error_message):
                        error = self._create_compatibility_error(
                            pattern_type,
                            error_message,
                            file_path,
                            language,
                        )
                        if error:
                            errors.append(error)
                        break

            # If we have a file and language, do deep analysis
            if file_path and language:
                analysis = self.analyze_file_compatibility(file_path, language)
                if analysis.get("has_issues"):
                    for issue in analysis.get("issues", []):
                        error = self._create_compatibility_error_from_analysis(
                            issue,
                            file_path,
                            language,
                        )
                        if error:
                            errors.append(error)

            logger.info(f"Detected {len(errors)} compatibility errors")
            return errors

        except Exception as e:
            logger.error(f"Error detecting compatibility errors: {e}")
            return []

    def _detect_language_from_file(self, file_path: Path) -> str | None:
        """Detect language from file extension."""
        try:
            extension_map = {
                ".py": "python",
                ".js": "javascript",
                ".jsx": "javascript",
                ".ts": "javascript",
                ".tsx": "javascript",
                ".rs": "rust",
                ".go": "go",
                ".java": "java",
                ".cpp": "cpp",
                ".cc": "cpp",
                ".cxx": "cpp",
                ".c": "c",
                ".h": "c",
                ".hpp": "cpp",
            }

            suffix = file_path.suffix.lower()
            return extension_map.get(suffix)

        except Exception as e:
            logger.error(f"Error detecting language from file: {e}")
            return None

    def _create_compatibility_error(
        self,
        pattern_type: str,
        error_message: str,
        file_path: Path | None,
        language: str | None,
    ) -> ClassifiedError | None:
        """Create a ClassifiedError for a compatibility issue."""
        try:
            self.error_counter += 1
            error_id = f"COMPAT_{datetime.now().strftime('%Y%m%d%H%M%S')}_{self.error_counter:04d}"

            # Determine severity based on pattern type
            severity_map = {
                "version_mismatch": ErrorSeverity.ERROR,
                "feature_unsupported": ErrorSeverity.ERROR,
                "deprecated": ErrorSeverity.WARNING,
                "breaking_change": ErrorSeverity.CRITICAL,
            }
            severity = severity_map.get(pattern_type, ErrorSeverity.WARNING)

            # Create context
            context = ErrorContext(
                file_path=str(file_path) if file_path else None,
                language=language,
                timestamp=datetime.now(),
            )

            # Generate suggested actions
            actions = self._generate_compatibility_actions(pattern_type, language)

            return ClassifiedError(
                error_id=error_id,
                message=error_message,
                category=ErrorCategory.COMPATIBILITY,
                severity=severity,
                source=ErrorSource.COMPATIBILITY_CHECKER,
                context=context,
                suggested_actions=actions,
                confidence=0.8,
            )

        except Exception as e:
            logger.error(f"Error creating compatibility error: {e}")
            return None

    def _create_compatibility_error_from_analysis(
        self,
        issue: dict[str, Any],
        file_path: Path,
        language: str,
    ) -> ClassifiedError | None:
        """Create a ClassifiedError from analysis results."""
        try:
            self.error_counter += 1
            error_id = f"COMPAT_ANALYSIS_{datetime.now().strftime('%Y%m%d%H%M%S')}_{self.error_counter:04d}"

            message = issue.get("message", "Compatibility issue detected")
            severity = ErrorSeverity(issue.get("severity", "warning"))

            context = ErrorContext(
                file_path=str(file_path),
                language=language,
                grammar_version=issue.get("grammar_version"),
                timestamp=datetime.now(),
            )

            return ClassifiedError(
                error_id=error_id,
                message=message,
                category=ErrorCategory.COMPATIBILITY,
                severity=severity,
                source=ErrorSource.COMPATIBILITY_CHECKER,
                context=context,
                suggested_actions=issue.get("suggestions", []),
                confidence=issue.get("confidence", 0.7),
            )

        except Exception as e:
            logger.error(f"Error creating error from analysis: {e}")
            return None

    def _generate_compatibility_actions(
        self,
        pattern_type: str,
        language: str | None,
    ) -> list[str]:
        """Generate suggested actions for compatibility issues."""
        actions = {
            "version_mismatch": [
                "Check the required language version for this project",
                "Update to a compatible language version",
                "Use a different grammar version that supports your language version",
                (
                    f"Run version detection to identify current {language} version"
                    if language
                    else "Identify the language version being used"
                ),
            ],
            "feature_unsupported": [
                "Check if this feature is available in your language version",
                "Consider upgrading to a newer language version",
                "Use an alternative syntax or feature",
                "Review language documentation for feature availability",
            ],
            "deprecated": [
                "Update code to use modern syntax",
                "Review migration guide for deprecated features",
                "Plan migration to newer version",
                "Check for automated migration tools",
            ],
            "breaking_change": [
                "Review breaking changes documentation",
                "Update code to comply with new API",
                "Consider using compatibility mode if available",
                "Test thoroughly after making changes",
            ],
        }

        return actions.get(pattern_type, ["Review compatibility documentation"])

    def analyze_file_compatibility(
        self,
        file_path: Path,
        language: str,
    ) -> dict[str, Any]:
        """Analyze a file for compatibility issues.

        Args:
            file_path: Path to the file to analyze
            language: Language of the file

        Returns:
            Dictionary with compatibility analysis results
        """
        try:
            analysis = {
                "file": str(file_path),
                "language": language,
                "has_issues": False,
                "issues": [],
                "detected_version": None,
                "grammar_version": None,
                "compatibility_level": None,
            }

            # Check if we have a detector for this language
            if language not in self.version_detectors:
                logger.warning(f"No version detector for language: {language}")
                return analysis

            # Read file content
            try:
                with open(file_path, encoding="utf-8") as f:
                    content = f.read()
            except Exception as e:
                logger.error(f"Error reading file {file_path}: {e}")
                return analysis

            # Detect version
            detector = self.version_detectors[language]
            version_info = detector.detect_version(content, file_path)

            # Get the most likely version
            detected_version = self._get_most_likely_version(version_info)
            if detected_version:
                analysis["detected_version"] = detected_version

                # Check compatibility with available grammars
                lang_version = LanguageVersion(
                    language=language,
                    version=detected_version,
                )

                # Find compatible grammar
                compatible_grammar = self.compatibility_db.find_compatible_grammar(
                    lang_version,
                )

                if compatible_grammar:
                    analysis["grammar_version"] = compatible_grammar.version
                    analysis["compatibility_level"] = (
                        self.compatibility_db.get_compatibility_level(
                            lang_version,
                            compatible_grammar,
                        ).value
                    )

                    # Check for issues based on compatibility level
                    if analysis["compatibility_level"] in [
                        "partially_compatible",
                        "incompatible",
                    ]:
                        analysis["has_issues"] = True
                        analysis["issues"].append(
                            {
                                "type": "compatibility_level",
                                "message": f"Language version {detected_version} has {analysis['compatibility_level']} "
                                f"compatibility with grammar version {compatible_grammar.version}",
                                "severity": (
                                    "warning"
                                    if analysis["compatibility_level"]
                                    == "partially_compatible"
                                    else "error"
                                ),
                                "suggestions": self.suggest_compatible_versions(
                                    detected_version,
                                    language,
                                ),
                                "confidence": 0.8,
                            },
                        )
                else:
                    analysis["has_issues"] = True
                    analysis["issues"].append(
                        {
                            "type": "no_compatible_grammar",
                            "message": f"No compatible grammar found for {language} version {detected_version}",
                            "severity": "error",
                            "suggestions": [
                                "Install a compatible grammar version",
                                "Update to a supported language version",
                                "Check available grammars for this language",
                            ],
                            "confidence": 0.9,
                        },
                    )

                # Check for breaking changes
                breaking_changes = self._check_breaking_changes(
                    language,
                    detected_version,
                )
                if breaking_changes:
                    analysis["has_issues"] = True
                    for change in breaking_changes:
                        analysis["issues"].append(
                            {
                                "type": "breaking_change",
                                "message": f"Breaking change: {change.description}",
                                "severity": "warning",
                                "suggestions": (
                                    [change.migration_guide]
                                    if change.migration_guide
                                    else []
                                ),
                                "confidence": 0.7,
                                "from_version": change.from_version,
                                "to_version": change.to_version,
                            },
                        )

            logger.debug(f"Compatibility analysis for {file_path}: {analysis}")
            return analysis

        except Exception as e:
            logger.error(f"Error analyzing file compatibility: {e}")
            return {
                "file": str(file_path),
                "language": language,
                "has_issues": True,
                "issues": [
                    {
                        "type": "analysis_error",
                        "message": f"Error analyzing compatibility: {e}",
                        "severity": "error",
                    },
                ],
            }

    def _get_most_likely_version(
        self,
        version_info: dict[str, str | None],
    ) -> str | None:
        """Extract the most likely version from version detection results."""
        try:
            # Priority order for version sources
            priority_keys = [
                "explicit_version",
                "config_version",
                "shebang",
                "requirement_version",
                "detected_version",
                "compiler_version",
                "runtime_version",
            ]

            for key in priority_keys:
                if version_info.get(key):
                    return version_info[key]

            # Check for any non-None value
            for value in version_info.values():
                if value:
                    return value

            return None

        except Exception as e:
            logger.error(f"Error getting most likely version: {e}")
            return None

    def _check_breaking_changes(self, language: str, version: str) -> list[Any]:
        """Check for breaking changes affecting the given version."""
        try:
            # For now, return empty list - would query database for breaking changes
            # This would typically call: self.compatibility_db.get_breaking_changes(language, from_version, to_version)
            return []
        except Exception as e:
            logger.error(f"Error checking breaking changes: {e}")
            return []

    def detect_version_mismatch(
        self,
        detected_version: str,
        grammar_version: str,
        language: str,
    ) -> ClassifiedError | None:
        """Detect version mismatches between detected and grammar versions.

        Args:
            detected_version: Detected language version
            grammar_version: Grammar version
            language: Language identifier

        Returns:
            ClassifiedError for version mismatch or None if compatible
        """
        try:
            # Create version objects
            lang_version = LanguageVersion(language=language, version=detected_version)

            # Get grammar versions for this language
            grammar_versions = self.compatibility_db.get_grammar_versions(language)

            # Find the specific grammar version
            target_grammar = None
            for gv in grammar_versions:
                if gv.version == grammar_version:
                    target_grammar = gv
                    break

            if not target_grammar:
                logger.warning(
                    f"Grammar version {grammar_version} not found for {language}",
                )
                return None

            # Check compatibility
            compatibility_level = self.compatibility_db.get_compatibility_level(
                lang_version,
                target_grammar,
            )

            if compatibility_level in [
                CompatibilityLevel.INCOMPATIBLE,
                CompatibilityLevel.UNKNOWN,
            ]:
                self.error_counter += 1
                error_id = f"MISMATCH_{datetime.now().strftime('%Y%m%d%H%M%S')}_{self.error_counter:04d}"

                message = (
                    f"Version mismatch: {language} {detected_version} is "
                    f"{compatibility_level.value} with grammar {grammar_version}"
                )

                return ClassifiedError(
                    error_id=error_id,
                    message=message,
                    category=ErrorCategory.COMPATIBILITY,
                    severity=ErrorSeverity.ERROR,
                    source=ErrorSource.COMPATIBILITY_CHECKER,
                    context=ErrorContext(
                        language=language,
                        grammar_version=grammar_version,
                    ),
                    suggested_actions=self.suggest_compatible_versions(
                        detected_version,
                        language,
                    ),
                    confidence=0.9,
                )

            return None

        except Exception as e:
            logger.error(f"Error detecting version mismatch: {e}")
            return None

    def detect_feature_incompatibility(
        self,
        required_features: list[str],
        supported_features: list[str],
        language: str,
    ) -> list[ClassifiedError]:
        """Detect feature incompatibilities.

        Args:
            required_features: Features required by the code
            supported_features: Features supported by the grammar
            language: Language identifier

        Returns:
            List of ClassifiedError objects for incompatibilities
        """
        try:
            errors = []

            # Find unsupported features
            unsupported = set(required_features) - set(supported_features)

            for feature in unsupported:
                self.error_counter += 1
                error_id = f"FEATURE_{datetime.now().strftime('%Y%m%d%H%M%S')}_{self.error_counter:04d}"

                message = f"Feature '{feature}' is not supported by the current {language} grammar"

                error = ClassifiedError(
                    error_id=error_id,
                    message=message,
                    category=ErrorCategory.COMPATIBILITY,
                    severity=ErrorSeverity.ERROR,
                    source=ErrorSource.COMPATIBILITY_CHECKER,
                    context=ErrorContext(language=language),
                    suggested_actions=[
                        f"Update grammar to support '{feature}'",
                        f"Use alternative syntax without '{feature}'",
                        "Check if feature is available in a different grammar version",
                    ],
                    confidence=0.85,
                )
                errors.append(error)

            logger.info(f"Detected {len(errors)} feature incompatibilities")
            return errors

        except Exception as e:
            logger.error(f"Error detecting feature incompatibility: {e}")
            return []

    def detect_breaking_changes(
        self,
        from_version: str,
        to_version: str,
        language: str,
    ) -> list[ClassifiedError]:
        """Detect breaking changes between versions.

        Args:
            from_version: Starting version
            to_version: Target version
            language: Language identifier

        Returns:
            List of ClassifiedError objects for breaking changes
        """
        try:
            errors = []

            # Get breaking changes from database
            breaking_changes = self.compatibility_db.get_breaking_changes(
                language,
                from_version,
                to_version,
            )

            for change in breaking_changes:
                self.error_counter += 1
                error_id = f"BREAKING_{datetime.now().strftime('%Y%m%d%H%M%S')}_{self.error_counter:04d}"

                message = (
                    f"Breaking change when migrating from {language} {from_version} "
                    f"to {to_version}: {change.description}"
                )

                # Determine severity based on impact level
                severity_map = {
                    "critical": ErrorSeverity.CRITICAL,
                    "high": ErrorSeverity.ERROR,
                    "medium": ErrorSeverity.WARNING,
                    "low": ErrorSeverity.INFO,
                }
                severity = severity_map.get(change.impact_level, ErrorSeverity.WARNING)

                actions = []
                if change.migration_guide:
                    actions.append(change.migration_guide)
                actions.extend(
                    [
                        "Review breaking changes documentation",
                        "Test thoroughly after migration",
                        "Consider gradual migration approach",
                    ],
                )

                error = ClassifiedError(
                    error_id=error_id,
                    message=message,
                    category=ErrorCategory.COMPATIBILITY,
                    severity=severity,
                    source=ErrorSource.COMPATIBILITY_CHECKER,
                    context=ErrorContext(language=language),
                    suggested_actions=actions,
                    confidence=0.95,
                )
                errors.append(error)

            logger.info(f"Detected {len(errors)} breaking changes")
            return errors

        except Exception as e:
            logger.error(f"Error detecting breaking changes: {e}")
            return []

    def generate_compatibility_report(self, file_path: Path, language: str) -> str:
        """Generate comprehensive compatibility report for a file.

        Args:
            file_path: Path to the file
            language: Language of the file

        Returns:
            Formatted compatibility report
        """
        try:
            analysis = self.analyze_file_compatibility(file_path, language)

            report = []
            report.append("=" * 60)
            report.append("COMPATIBILITY ANALYSIS REPORT")
            report.append("=" * 60)
            report.append(f"File: {analysis['file']}")
            report.append(f"Language: {analysis['language']}")
            report.append(
                f"Detected Version: {analysis.get('detected_version', 'Unknown')}",
            )
            report.append(
                f"Grammar Version: {analysis.get('grammar_version', 'Not found')}",
            )
            report.append(
                f"Compatibility Level: {analysis.get('compatibility_level', 'Unknown')}",
            )
            report.append("")

            if analysis["has_issues"]:
                report.append("COMPATIBILITY ISSUES FOUND:")
                report.append("-" * 40)
                for i, issue in enumerate(analysis["issues"], 1):
                    report.append(f"{i}. {issue['message']}")
                    report.append(
                        f"   Severity: {issue.get('severity', 'unknown').upper()}",
                    )
                    if issue.get("suggestions"):
                        report.append("   Suggestions:")
                        for suggestion in issue["suggestions"]:
                            report.append(f"   - {suggestion}")
                    report.append("")
            else:
                report.append("✓ No compatibility issues detected")

            # Add recommendations
            report.append("RECOMMENDATIONS:")
            report.append("-" * 40)

            if analysis.get("detected_version"):
                compatible_versions = self.suggest_compatible_versions(
                    analysis["detected_version"],
                    language,
                )
                if compatible_versions:
                    report.append("Compatible versions:")
                    for version in compatible_versions[:3]:
                        report.append(f"  - {version}")

            report.append("")
            report.append("=" * 60)

            return "\n".join(report)

        except Exception as e:
            logger.error(f"Error generating compatibility report: {e}")
            return f"Error generating report: {e}"

    def suggest_compatible_versions(
        self,
        current_version: str,
        language: str,
    ) -> list[str]:
        """Suggest compatible versions for a language.

        Args:
            current_version: Current language version
            language: Language identifier

        Returns:
            List of compatible version suggestions
        """
        try:
            suggestions = []

            # Get all language versions from database
            all_versions = self.compatibility_db.get_language_versions(language)

            # Get all grammar versions
            grammar_versions = self.compatibility_db.get_grammar_versions(language)

            if not grammar_versions:
                logger.warning(f"No grammar versions found for {language}")
                return ["No compatible versions found - check grammar installation"]

            # Find versions with good compatibility
            current_lang_version = LanguageVersion(
                language=language,
                version=current_version,
            )

            for lang_version in all_versions:
                for grammar_version in grammar_versions:
                    compatibility = self.compatibility_db.get_compatibility_level(
                        lang_version,
                        grammar_version,
                    )

                    if compatibility in [
                        CompatibilityLevel.FULLY_COMPATIBLE,
                        CompatibilityLevel.MOSTLY_COMPATIBLE,
                    ]:
                        suggestion = f"{language} {lang_version.version} with grammar {grammar_version.version}"
                        if suggestion not in suggestions:
                            suggestions.append(suggestion)

            # If no specific suggestions, provide general guidance
            if not suggestions:
                suggestions = [
                    f"Check supported {language} versions in documentation",
                    "Update to the latest stable version",
                    "Use the version specified in project requirements",
                ]

            return suggestions[:5]  # Return top 5 suggestions

        except Exception as e:
            logger.error(f"Error suggesting compatible versions: {e}")
            return ["Error retrieving version suggestions"]

    def validate_grammar_compatibility(self, language: str, version: str) -> bool:
        """Validate if grammar is compatible with language version.

        Args:
            language: Language identifier
            version: Language version

        Returns:
            True if compatible, False otherwise
        """
        try:
            lang_version = LanguageVersion(language=language, version=version)

            # Find compatible grammar
            compatible_grammar = self.compatibility_db.find_compatible_grammar(
                lang_version,
            )

            if compatible_grammar:
                compatibility = self.compatibility_db.get_compatibility_level(
                    lang_version,
                    compatible_grammar,
                )
                return compatibility in [
                    CompatibilityLevel.FULLY_COMPATIBLE,
                    CompatibilityLevel.MOSTLY_COMPATIBLE,
                ]

            return False

        except Exception as e:
            logger.error(f"Error validating grammar compatibility: {e}")
            return False

    def get_compatibility_details(self, language: str, version: str) -> dict[str, Any]:
        """Get detailed compatibility information.

        Args:
            language: Language identifier
            version: Language version

        Returns:
            Dictionary with compatibility details
        """
        try:
            details = {
                "language": language,
                "version": version,
                "compatible_grammars": [],
                "incompatible_grammars": [],
                "breaking_changes": [],
                "recommendations": [],
            }

            lang_version = LanguageVersion(language=language, version=version)

            # Check all grammar versions
            grammar_versions = self.compatibility_db.get_grammar_versions(language)

            for grammar in grammar_versions:
                compatibility = self.compatibility_db.get_compatibility_level(
                    lang_version,
                    grammar,
                )

                grammar_info = {
                    "version": grammar.version,
                    "compatibility": compatibility.value,
                    "min_version": grammar.min_language_version,
                    "max_version": grammar.max_language_version,
                }

                if compatibility in [
                    CompatibilityLevel.FULLY_COMPATIBLE,
                    CompatibilityLevel.MOSTLY_COMPATIBLE,
                ]:
                    details["compatible_grammars"].append(grammar_info)
                else:
                    details["incompatible_grammars"].append(grammar_info)

            # Add recommendations
            if details["compatible_grammars"]:
                details["recommendations"].append(
                    f"Use grammar version {details['compatible_grammars'][0]['version']} "
                    f"for best compatibility",
                )
            else:
                details["recommendations"].append(
                    "No fully compatible grammar found - consider updating language version",
                )

            logger.debug(f"Got compatibility details for {language} {version}")
            return details

        except Exception as e:
            logger.error(f"Error getting compatibility details: {e}")
            return {"language": language, "version": version, "error": str(e)}

    def update_compatibility_cache(self, language: str) -> None:
        """Update compatibility cache for a language.

        Args:
            language: Language to update cache for
        """
        try:
            # Trigger database update for this language
            self.compatibility_db.update_compatibility_data()
            logger.info(f"Updated compatibility cache for {language}")

        except Exception as e:
            logger.error(f"Error updating compatibility cache: {e}")

    def export_compatibility_errors(self, output_path: Path) -> None:
        """Export detected compatibility errors to file.

        Args:
            output_path: Path to write the export file
        """
        try:
            import json

            # This would typically export accumulated errors
            # For now, export current configuration
            export_data = {
                "exported_at": datetime.now().isoformat(),
                "detectors": list(self.version_detectors.keys()),
                "patterns": {
                    key: [p.pattern for p in patterns]
                    for key, patterns in self.compatibility_patterns.items()
                },
                "error_count": self.error_counter,
            }

            with open(output_path, "w") as f:
                json.dump(export_data, f, indent=2)

            logger.info(f"Exported compatibility errors to {output_path}")

        except Exception as e:
            logger.error(f"Error exporting compatibility errors: {e}")
            raise


class VersionCompatibilityAnalyzer:
    """Analyzes version compatibility in detail."""

    def __init__(self, compatibility_db: CompatibilityDatabase):
        """Initialize the version compatibility analyzer.

        Args:
            compatibility_db: Compatibility database instance
        """
        self.compatibility_db = compatibility_db
        logger.info("Initialized VersionCompatibilityAnalyzer")

    def analyze_version_range(
        self,
        language: str,
        min_version: str,
        max_version: str,
    ) -> dict[str, Any]:
        """Analyze compatibility across a version range.

        Args:
            language: Language identifier
            min_version: Minimum version in range
            max_version: Maximum version in range

        Returns:
            Dictionary with compatibility analysis
        """
        try:
            analysis = {
                "language": language,
                "range": f"{min_version} - {max_version}",
                "compatible_grammars": [],
                "partially_compatible_grammars": [],
                "incompatible_grammars": [],
                "coverage": 0.0,
            }

            # Get all grammar versions
            grammar_versions = self.compatibility_db.get_grammar_versions(language)

            # Check each grammar against the range
            for grammar in grammar_versions:
                # Check if grammar supports the range
                supports_min = (
                    self._version_compare(
                        min_version,
                        grammar.min_language_version or "0.0",
                    )
                    >= 0
                )
                supports_max = True
                if grammar.max_language_version:
                    supports_max = (
                        self._version_compare(max_version, grammar.max_language_version)
                        <= 0
                    )

                grammar_info = {
                    "version": grammar.version,
                    "min_supported": grammar.min_language_version,
                    "max_supported": grammar.max_language_version,
                }

                if supports_min and supports_max:
                    analysis["compatible_grammars"].append(grammar_info)
                elif supports_min or supports_max:
                    analysis["partially_compatible_grammars"].append(grammar_info)
                else:
                    analysis["incompatible_grammars"].append(grammar_info)

            # Calculate coverage
            total_grammars = len(grammar_versions)
            if total_grammars > 0:
                analysis["coverage"] = (
                    len(analysis["compatible_grammars"]) / total_grammars
                )

            logger.debug(
                f"Analyzed version range {min_version}-{max_version} for {language}",
            )
            return analysis

        except Exception as e:
            logger.error(f"Error analyzing version range: {e}")
            return {
                "language": language,
                "range": f"{min_version} - {max_version}",
                "error": str(e),
            }

    def _version_compare(self, v1: str, v2: str) -> int:
        """Compare two version strings.

        Returns:
            -1 if v1 < v2, 0 if equal, 1 if v1 > v2
        """
        try:
            # Simple version comparison - split by dots and compare numerically
            parts1 = [int(x) for x in re.sub(r"[^\d.]", "", v1).split(".")]
            parts2 = [int(x) for x in re.sub(r"[^\d.]", "", v2).split(".")]

            # Pad with zeros
            max_len = max(len(parts1), len(parts2))
            parts1.extend([0] * (max_len - len(parts1)))
            parts2.extend([0] * (max_len - len(parts2)))

            for p1, p2 in zip(parts1, parts2, strict=False):
                if p1 < p2:
                    return -1
                if p1 > p2:
                    return 1

            return 0

        except Exception:
            return 0

    def find_optimal_grammar_version(
        self,
        language: str,
        target_version: str,
    ) -> str | None:
        """Find the optimal grammar version for a language version.

        Args:
            language: Language identifier
            target_version: Target language version

        Returns:
            Optimal grammar version or None
        """
        try:
            lang_version = LanguageVersion(language=language, version=target_version)

            # Find compatible grammar
            compatible_grammar = self.compatibility_db.find_compatible_grammar(
                lang_version,
            )

            if compatible_grammar:
                logger.debug(
                    f"Found optimal grammar {compatible_grammar.version} "
                    f"for {language} {target_version}",
                )
                return compatible_grammar.version

            return None

        except Exception as e:
            logger.error(f"Error finding optimal grammar version: {e}")
            return None

    def get_migration_path(
        self,
        from_version: str,
        to_version: str,
        language: str,
    ) -> list[str]:
        """Get migration path between versions.

        Args:
            from_version: Starting version
            to_version: Target version
            language: Language identifier

        Returns:
            List of intermediate versions for migration
        """
        try:
            path = []

            # Get all language versions
            all_versions = self.compatibility_db.get_language_versions(language)

            # Sort versions
            sorted_versions = sorted(
                all_versions,
                key=lambda v: [
                    int(x) for x in re.sub(r"[^\d.]", "", v.version).split(".")
                ],
            )

            # Find versions between from and to
            in_range = False
            for version in sorted_versions:
                if version.version == from_version:
                    in_range = True
                    continue

                if in_range:
                    path.append(version.version)

                if version.version == to_version:
                    break

            logger.debug(f"Migration path from {from_version} to {to_version}: {path}")
            return path

        except Exception as e:
            logger.error(f"Error getting migration path: {e}")
            return []

    def analyze_dependency_compatibility(
        self,
        dependencies: dict[str, str],
    ) -> dict[str, Any]:
        """Analyze compatibility of multiple dependencies.

        Args:
            dependencies: Dictionary mapping language to version

        Returns:
            Dictionary with dependency compatibility analysis
        """
        try:
            analysis = {
                "dependencies": dependencies,
                "compatible": True,
                "issues": [],
                "recommendations": [],
            }

            # Check each dependency
            for language, version in dependencies.items():
                lang_version = LanguageVersion(language=language, version=version)

                # Find compatible grammar
                compatible_grammar = self.compatibility_db.find_compatible_grammar(
                    lang_version,
                )

                if not compatible_grammar:
                    analysis["compatible"] = False
                    analysis["issues"].append(
                        f"No compatible grammar for {language} {version}",
                    )
                    analysis["recommendations"].append(
                        f"Update {language} to a supported version",
                    )
                else:
                    compatibility = self.compatibility_db.get_compatibility_level(
                        lang_version,
                        compatible_grammar,
                    )

                    if compatibility == CompatibilityLevel.PARTIALLY_COMPATIBLE:
                        analysis["issues"].append(
                            f"{language} {version} is only partially compatible",
                        )

            logger.debug(f"Analyzed compatibility for {len(dependencies)} dependencies")
            return analysis

        except Exception as e:
            logger.error(f"Error analyzing dependency compatibility: {e}")
            return {"dependencies": dependencies, "error": str(e)}


class CompatibilityErrorFormatter:
    """Formats compatibility errors for user consumption."""

    def __init__(self):
        """Initialize the compatibility error formatter."""
        self.error_templates = self._load_error_templates()
        logger.info("Initialized CompatibilityErrorFormatter")

    def _load_error_templates(self) -> dict[str, str]:
        """Load error message templates."""
        templates = {
            "version_mismatch": (
                "Version Mismatch: {language} {detected_version} is incompatible with "
                "grammar version {grammar_version}.\n"
                "Expected: {expected_version}\n"
                "Detected: {detected_version}"
            ),
            "feature_incompatibility": (
                "Feature Incompatibility: The following features are not supported in "
                "{language} {version}:\n{missing_features}\n"
                "Consider updating to a newer version or using alternative syntax."
            ),
            "breaking_change": (
                "Breaking Change Alert: Migrating from {from_version} to {to_version} "
                "involves the following breaking changes:\n{changes}\n"
                "Review the migration guide before proceeding."
            ),
            "deprecated_feature": (
                "Deprecated Feature: {feature} has been deprecated in {language} {version}.\n"
                "It will be removed in {removal_version}.\n"
                "Recommended alternative: {alternative}"
            ),
            "no_compatible_grammar": (
                "No Compatible Grammar: Unable to find a compatible grammar for "
                "{language} {version}.\n"
                "Available grammars support: {supported_versions}"
            ),
        }
        logger.debug(f"Loaded {len(templates)} error templates")
        return templates

    def format_version_mismatch_error(
        self,
        detected_version: str,
        grammar_version: str,
        language: str,
    ) -> str:
        """Format version mismatch error message.

        Args:
            detected_version: Detected language version
            grammar_version: Grammar version
            language: Language identifier

        Returns:
            Formatted error message
        """
        try:
            template = self.error_templates.get("version_mismatch", "")

            # TODO: Get expected version from grammar metadata
            expected_version = "Unknown"

            message = template.format(
                language=language,
                detected_version=detected_version,
                grammar_version=grammar_version,
                expected_version=expected_version,
            )

            return message

        except Exception as e:
            logger.error(f"Error formatting version mismatch: {e}")
            return f"Version mismatch: {language} {detected_version} incompatible with grammar {grammar_version}"

    def format_feature_incompatibility_error(
        self,
        missing_features: list[str],
        language: str,
        version: str,
    ) -> str:
        """Format feature incompatibility error message.

        Args:
            missing_features: List of unsupported features
            language: Language identifier
            version: Language version

        Returns:
            Formatted error message
        """
        try:
            template = self.error_templates.get("feature_incompatibility", "")

            features_list = "\n".join(f"  - {feature}" for feature in missing_features)

            message = template.format(
                language=language,
                version=version,
                missing_features=features_list,
            )

            return message

        except Exception as e:
            logger.error(f"Error formatting feature incompatibility: {e}")
            return f"Features not supported in {language} {version}: {', '.join(missing_features)}"

    def format_breaking_change_error(
        self,
        breaking_changes: list[dict[str, Any]],
    ) -> str:
        """Format breaking change error message.

        Args:
            breaking_changes: List of breaking change information

        Returns:
            Formatted error message
        """
        try:
            if not breaking_changes:
                return "No breaking changes detected"

            template = self.error_templates.get("breaking_change", "")

            # Get version range
            from_version = breaking_changes[0].get("from_version", "Unknown")
            to_version = breaking_changes[0].get("to_version", "Unknown")

            # Format changes list
            changes_list = "\n".join(
                f"  - {change.get('description', 'Unknown change')}"
                for change in breaking_changes
            )

            message = template.format(
                from_version=from_version,
                to_version=to_version,
                changes=changes_list,
            )

            return message

        except Exception as e:
            logger.error(f"Error formatting breaking change: {e}")
            return "Breaking changes detected - review migration guide"

    def generate_resolution_steps(
        self,
        error_type: str,
        language: str,
        version: str,
    ) -> list[str]:
        """Generate resolution steps for compatibility errors.

        Args:
            error_type: Type of compatibility error
            language: Language identifier
            version: Language version

        Returns:
            List of resolution steps
        """
        try:
            steps = {
                "version_mismatch": [
                    f"1. Check current {language} version: Run version detection",
                    "2. Review project requirements for version constraints",
                    "3. Update to a compatible version or install matching grammar",
                    "4. Test code after version change",
                    "5. Update project documentation with version requirements",
                ],
                "feature_incompatibility": [
                    f"1. Identify unsupported features in {language} {version}",
                    "2. Check if features are available in newer versions",
                    "3. Rewrite code using supported alternatives",
                    "4. Consider using polyfills or compatibility libraries",
                    "5. Document feature requirements for future reference",
                ],
                "breaking_change": [
                    "1. Review breaking changes documentation",
                    "2. Create backup of current code",
                    "3. Apply required code modifications",
                    "4. Run comprehensive tests",
                    "5. Update dependencies if needed",
                ],
                "deprecated_feature": [
                    "1. Identify all uses of deprecated features",
                    "2. Review recommended alternatives",
                    "3. Plan migration timeline",
                    "4. Update code incrementally",
                    "5. Test thoroughly after each change",
                ],
            }

            return steps.get(
                error_type,
                [
                    "1. Review error details",
                    "2. Check compatibility documentation",
                    "3. Seek support if needed",
                ],
            )

        except Exception as e:
            logger.error(f"Error generating resolution steps: {e}")
            return ["Review error message and documentation"]

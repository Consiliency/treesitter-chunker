"""Comprehensive user action guidance engine for Phase 1.7 - Smart Error Handling & User Guidance.

This module implements a sophisticated guidance system that:
- Generates comprehensive guidance for classified errors
- Creates step-by-step action sequences for resolution
- Suggests immediate and preventive actions
- Generates human-readable error explanations
- Adapts guidance for different user experience levels
- Personalizes guidance based on user preferences
- Assesses guidance quality and effectiveness

The system integrates with all Group C components (classifier, compatibility detector, syntax analyzer)
and the Group D1 templates system to provide contextual, actionable guidance for users.
"""

from __future__ import annotations

import json
import logging
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

# Import Group C dependencies
try:
    from .classifier import (
        ClassifiedError,
        ErrorCategory,
        ErrorContext,
        ErrorSeverity,
        ErrorSource,
    )
    from .compatibility_detector import CompatibilityErrorDetector
    from .syntax_analyzer import SyntaxErrorAnalyzer
except ImportError as e:
    logging.warning(f"Failed to import Group C components: {e}")
    # Provide fallback definitions for testing
    ClassifiedError = None
    ErrorCategory = None
    ErrorSeverity = None
    ErrorSource = None
    ErrorContext = None
    CompatibilityErrorDetector = None
    SyntaxErrorAnalyzer = None

# Import Group D1 dependencies
try:
    from .templates import (
        ErrorTemplate,
        TemplateFormat,
        TemplateManager,
        TemplateType,
        render_template,
    )
except ImportError as e:
    logging.warning(f"Failed to import Group D1 templates: {e}")
    # Provide fallback definitions for testing
    TemplateManager = None
    ErrorTemplate = None
    TemplateFormat = None
    TemplateType = None
    render_template = None

logger = logging.getLogger(__name__)


class UserExperienceLevel(Enum):
    """User experience levels for guidance personalization."""

    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"


class GuidanceType(Enum):
    """Types of guidance that can be generated."""

    IMMEDIATE_ACTION = "immediate_action"
    DIAGNOSTIC_STEPS = "diagnostic_steps"
    RESOLUTION_SEQUENCE = "resolution_sequence"
    PREVENTIVE_MEASURES = "preventive_measures"
    LEARNING_RESOURCES = "learning_resources"
    TROUBLESHOOTING = "troubleshooting"


class ActionPriority(Enum):
    """Priority levels for guidance actions."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    OPTIONAL = "optional"


@dataclass
class GuidanceAction:
    """Represents a single actionable guidance step."""

    id: str
    title: str
    description: str
    priority: ActionPriority
    category: GuidanceType
    command: str | None = None
    expected_outcome: str | None = None
    troubleshooting_notes: str | None = None
    dependencies: list[str] = field(default_factory=list)
    estimated_time: str | None = None
    difficulty_level: UserExperienceLevel = UserExperienceLevel.INTERMEDIATE
    success_criteria: list[str] = field(default_factory=list)
    failure_indicators: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "priority": self.priority.value,
            "category": self.category.value,
            "command": self.command,
            "expected_outcome": self.expected_outcome,
            "troubleshooting_notes": self.troubleshooting_notes,
            "dependencies": self.dependencies,
            "estimated_time": self.estimated_time,
            "difficulty_level": self.difficulty_level.value,
            "success_criteria": self.success_criteria,
            "failure_indicators": self.failure_indicators,
        }


@dataclass
class UserProfile:
    """User profile for guidance personalization."""

    user_id: str
    experience_level: UserExperienceLevel
    preferred_guidance_style: str = "step_by_step"  # step_by_step, summary, detailed
    language_preferences: list[str] = field(default_factory=lambda: ["python"])
    completed_actions: list[str] = field(default_factory=list)
    failed_actions: list[str] = field(default_factory=list)
    feedback_history: list[dict[str, Any]] = field(default_factory=list)
    learning_goals: list[str] = field(default_factory=list)
    preferred_formats: list[str] = field(default_factory=lambda: ["text", "markdown"])
    session_context: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "user_id": self.user_id,
            "experience_level": self.experience_level.value,
            "preferred_guidance_style": self.preferred_guidance_style,
            "language_preferences": self.language_preferences,
            "completed_actions": self.completed_actions,
            "failed_actions": self.failed_actions,
            "feedback_history": self.feedback_history,
            "learning_goals": self.learning_goals,
            "preferred_formats": self.preferred_formats,
            "session_context": self.session_context,
        }


@dataclass
class GuidanceSequence:
    """Represents a sequence of guidance actions with dependencies."""

    id: str
    name: str
    description: str
    error_context: dict[str, Any] | None
    actions: list[GuidanceAction]
    estimated_total_time: str | None = None
    difficulty_level: UserExperienceLevel = UserExperienceLevel.INTERMEDIATE
    success_rate: float = 0.0
    tags: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def get_actions_by_priority(self, priority: ActionPriority) -> list[GuidanceAction]:
        """Get all actions with specified priority."""
        return [action for action in self.actions if action.priority == priority]

    def get_critical_actions(self) -> list[GuidanceAction]:
        """Get all critical priority actions."""
        return self.get_actions_by_priority(ActionPriority.CRITICAL)

    def validate_dependencies(self) -> list[str]:
        """Validate action dependencies and return any issues."""
        issues = []
        action_ids = {action.id for action in self.actions}

        for action in self.actions:
            for dep_id in action.dependencies:
                if dep_id not in action_ids:
                    issues.append(
                        f"Action {action.id} depends on missing action {dep_id}",
                    )

        return issues

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "error_context": self.error_context,
            "actions": [action.to_dict() for action in self.actions],
            "estimated_total_time": self.estimated_total_time,
            "difficulty_level": self.difficulty_level.value,
            "success_rate": self.success_rate,
            "tags": self.tags,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class UserActionGuidanceEngine:
    """Main engine for generating comprehensive user action guidance."""

    def __init__(
        self,
        template_manager: TemplateManager | None = None,
        compatibility_detector: CompatibilityErrorDetector | None = None,
        syntax_analyzer: SyntaxErrorAnalyzer | None = None,
    ):
        """Initialize the user action guidance engine.

        Args:
            template_manager: Template manager instance for formatting guidance
            compatibility_detector: Compatibility error detector for version issues
            syntax_analyzer: Syntax error analyzer for language-specific issues
        """
        self.template_manager = template_manager
        self.compatibility_detector = compatibility_detector
        self.syntax_analyzer = syntax_analyzer

        # Initialize guidance patterns and rules
        self.guidance_patterns = self._load_guidance_patterns()
        self.action_templates = self._load_action_templates()
        self.dependency_rules = self._load_dependency_rules()

        # Statistics and tracking
        self.guidance_counter = 0
        self.generated_sequences: dict[str, GuidanceSequence] = {}
        self.user_profiles: dict[str, UserProfile] = {}

        logger.info("Initialized UserActionGuidanceEngine")

    def _load_guidance_patterns(self) -> dict[str, dict[str, Any]]:
        """Load patterns for generating guidance based on error types."""
        patterns = {
            "syntax_error": {
                "immediate_actions": [
                    "Review the exact line and column where the error occurred",
                    "Check for common syntax issues (brackets, quotes, semicolons)",
                    "Verify language-specific syntax requirements",
                ],
                "diagnostic_steps": [
                    "Examine surrounding code for context",
                    "Use syntax highlighting to identify issues",
                    "Check for invisible characters or encoding problems",
                ],
                "resolution_sequence": [
                    "Fix the immediate syntax error",
                    "Run syntax validation",
                    "Test with a simple example",
                    "Verify the fix doesn't introduce new errors",
                ],
                "preventive_measures": [
                    "Use a linter or code formatter",
                    "Enable editor syntax checking",
                    "Follow language style guides",
                    "Use version control with pre-commit hooks",
                ],
            },
            "compatibility_error": {
                "immediate_actions": [
                    "Check language and grammar version requirements",
                    "Verify system compatibility",
                    "Review project configuration",
                ],
                "diagnostic_steps": [
                    "Run version detection commands",
                    "Check dependency compatibility",
                    "Review system requirements",
                ],
                "resolution_sequence": [
                    "Update to compatible versions",
                    "Modify configuration if needed",
                    "Test compatibility",
                    "Document version requirements",
                ],
                "preventive_measures": [
                    "Maintain version compatibility matrix",
                    "Use dependency management tools",
                    "Implement compatibility testing",
                    "Document system requirements",
                ],
            },
            "parsing_error": {
                "immediate_actions": [
                    "Verify file is valid and accessible",
                    "Check file encoding and format",
                    "Review parser configuration",
                ],
                "diagnostic_steps": [
                    "Test with simpler file content",
                    "Check parser logs for details",
                    "Verify grammar installation",
                ],
                "resolution_sequence": [
                    "Fix file format issues",
                    "Update parser configuration",
                    "Retry parsing operation",
                    "Verify successful parsing",
                ],
                "preventive_measures": [
                    "Validate files before processing",
                    "Use robust file handling",
                    "Implement fallback strategies",
                    "Monitor parsing success rates",
                ],
            },
            "configuration_error": {
                "immediate_actions": [
                    "Check configuration file syntax",
                    "Verify required settings are present",
                    "Review file permissions",
                ],
                "diagnostic_steps": [
                    "Validate configuration against schema",
                    "Check for missing dependencies",
                    "Review environment variables",
                ],
                "resolution_sequence": [
                    "Fix configuration syntax",
                    "Add missing required settings",
                    "Test configuration",
                    "Document configuration requirements",
                ],
                "preventive_measures": [
                    "Use configuration validation",
                    "Provide configuration templates",
                    "Document all settings",
                    "Implement configuration backup",
                ],
            },
            "system_error": {
                "immediate_actions": [
                    "Check system resources (memory, disk, CPU)",
                    "Review system logs for errors",
                    "Verify system permissions",
                ],
                "diagnostic_steps": [
                    "Monitor system performance",
                    "Check for resource limitations",
                    "Review system configuration",
                ],
                "resolution_sequence": [
                    "Address resource constraints",
                    "Restart services if needed",
                    "Verify system stability",
                    "Monitor for recurring issues",
                ],
                "preventive_measures": [
                    "Implement resource monitoring",
                    "Set up system alerts",
                    "Plan for capacity scaling",
                    "Maintain system documentation",
                ],
            },
        }
        logger.debug(f"Loaded guidance patterns for {len(patterns)} error types")
        return patterns

    def _load_action_templates(self) -> dict[str, dict[str, Any]]:
        """Load templates for generating specific actions."""
        templates = {
            "check_syntax": {
                "title": "Check Syntax",
                "description": "Verify code syntax is correct for {language}",
                "command": "python -m py_compile {file_path}",
                "expected_outcome": "No syntax errors reported",
                "estimated_time": "1-2 minutes",
            },
            "run_linter": {
                "title": "Run Code Linter",
                "description": "Use a linter to identify code quality issues",
                "command": "pylint {file_path}",
                "expected_outcome": "Code quality report generated",
                "estimated_time": "2-5 minutes",
            },
            "check_versions": {
                "title": "Check Version Compatibility",
                "description": "Verify language and tool versions are compatible",
                "command": "python --version && pip list",
                "expected_outcome": "Version information displayed",
                "estimated_time": "1 minute",
            },
            "update_grammar": {
                "title": "Update Grammar",
                "description": "Update tree-sitter grammar for {language}",
                "command": "treesitter-chunker download-grammar {language}",
                "expected_outcome": "Grammar downloaded and installed",
                "estimated_time": "2-10 minutes",
            },
            "validate_config": {
                "title": "Validate Configuration",
                "description": "Check configuration file syntax and completeness",
                "command": "treesitter-chunker validate-config {config_path}",
                "expected_outcome": "Configuration validated successfully",
                "estimated_time": "1-2 minutes",
            },
            "test_parsing": {
                "title": "Test File Parsing",
                "description": "Test parsing with a simple file",
                "command": "treesitter-chunker parse {test_file}",
                "expected_outcome": "File parsed successfully",
                "estimated_time": "1-3 minutes",
            },
            "check_permissions": {
                "title": "Check File Permissions",
                "description": "Verify file and directory permissions",
                "command": "ls -la {file_path}",
                "expected_outcome": "Permissions displayed",
                "estimated_time": "30 seconds",
            },
        }
        logger.debug(f"Loaded {len(templates)} action templates")
        return templates

    def _load_dependency_rules(self) -> dict[str, list[str]]:
        """Load rules for action dependencies."""
        rules = {
            "check_syntax": [],
            "run_linter": ["check_syntax"],
            "update_grammar": ["check_versions"],
            "test_parsing": ["update_grammar"],
            "validate_config": ["check_permissions"],
            "fix_syntax_error": ["check_syntax"],
            "fix_compatibility": ["check_versions", "update_grammar"],
            "fix_configuration": ["validate_config"],
            "verify_fix": [
                "fix_syntax_error",
                "fix_compatibility",
                "fix_configuration",
            ],
        }
        logger.debug(f"Loaded dependency rules for {len(rules)} actions")
        return rules

    def generate_guidance(
        self,
        classified_error: ClassifiedError,
        user_profile: UserProfile | None = None,
        guidance_types: list[GuidanceType] | None = None,
    ) -> GuidanceSequence:
        """Generate comprehensive guidance for a classified error.

        Args:
            classified_error: The classified error to generate guidance for
            user_profile: Optional user profile for personalization
            guidance_types: Optional list of specific guidance types to generate

        Returns:
            GuidanceSequence containing all guidance actions
        """
        if not classified_error:
            raise ValueError("classified_error is required")

        try:
            self.guidance_counter += 1
            sequence_id = f"guidance_{datetime.now().strftime('%Y%m%d%H%M%S')}_{self.guidance_counter:04d}"

            # Default guidance types if not specified
            if guidance_types is None:
                guidance_types = [
                    GuidanceType.IMMEDIATE_ACTION,
                    GuidanceType.DIAGNOSTIC_STEPS,
                    GuidanceType.RESOLUTION_SEQUENCE,
                    GuidanceType.PREVENTIVE_MEASURES,
                ]

            # Get error category for pattern matching
            error_category = (
                classified_error.category.value
                if classified_error.category
                else "unknown"
            )

            # Generate actions for each guidance type
            all_actions = []

            for guidance_type in guidance_types:
                actions = self._generate_actions_for_type(
                    classified_error,
                    guidance_type,
                    user_profile,
                )
                all_actions.extend(actions)

            # Add specialized actions based on error analysis
            specialized_actions = self._generate_specialized_actions(
                classified_error,
                user_profile,
            )
            all_actions.extend(specialized_actions)

            # Create guidance sequence
            sequence = GuidanceSequence(
                id=sequence_id,
                name=f"Guidance for {error_category} error",
                description=f"Comprehensive guidance for resolving: {classified_error.message}",
                error_context={
                    "error_id": classified_error.error_id,
                    "category": error_category,
                    "severity": (
                        classified_error.severity.value
                        if classified_error.severity
                        else "unknown"
                    ),
                    "source": (
                        classified_error.source.value
                        if classified_error.source
                        else "unknown"
                    ),
                    "context": (
                        classified_error.context.to_dict()
                        if classified_error.context
                        else {}
                    ),
                },
                actions=all_actions,
                estimated_total_time=self._calculate_total_time(all_actions),
                difficulty_level=self._determine_difficulty_level(
                    classified_error,
                    user_profile,
                ),
                tags=[error_category, "auto_generated"],
            )

            # Validate sequence
            dependency_issues = sequence.validate_dependencies()
            if dependency_issues:
                logger.warning(
                    f"Dependency issues in sequence {sequence_id}: {dependency_issues}",
                )

            # Store sequence
            self.generated_sequences[sequence_id] = sequence

            logger.info(
                f"Generated guidance sequence {sequence_id} with {len(all_actions)} actions",
            )
            return sequence

        except Exception as e:
            logger.error(f"Error generating guidance: {e}")
            raise RuntimeError(f"Failed to generate guidance: {e}") from e

    def _generate_actions_for_type(
        self,
        classified_error: ClassifiedError,
        guidance_type: GuidanceType,
        user_profile: UserProfile | None,
    ) -> list[GuidanceAction]:
        """Generate actions for a specific guidance type."""
        try:
            actions = []
            error_category = (
                classified_error.category.value
                if classified_error.category
                else "unknown"
            )

            # Get patterns for this error category
            patterns = self.guidance_patterns.get(f"{error_category}_error", {})
            type_patterns = patterns.get(guidance_type.value, [])

            # Generate actions from patterns
            for i, pattern in enumerate(type_patterns):
                action_id = f"{guidance_type.value}_{error_category}_{i + 1}"

                action = GuidanceAction(
                    id=action_id,
                    title=self._format_action_title(pattern, classified_error),
                    description=self._format_action_description(
                        pattern,
                        classified_error,
                    ),
                    priority=self._determine_action_priority(
                        guidance_type,
                        classified_error,
                    ),
                    category=guidance_type,
                    estimated_time="2-5 minutes",
                    difficulty_level=(
                        user_profile.experience_level
                        if user_profile
                        else UserExperienceLevel.INTERMEDIATE
                    ),
                )

                # Add command and expected outcome if available
                self._enhance_action_with_template(action, pattern, classified_error)

                actions.append(action)

            return actions

        except Exception as e:
            logger.error(f"Error generating actions for type {guidance_type}: {e}")
            return []

    def _generate_specialized_actions(
        self,
        classified_error: ClassifiedError,
        user_profile: UserProfile | None,
    ) -> list[GuidanceAction]:
        """Generate specialized actions based on detailed error analysis."""
        try:
            actions = []

            # Analyze error with specialized components
            if (
                self.syntax_analyzer
                and classified_error.category
                and classified_error.category.value == "syntax"
            ):
                syntax_actions = self._generate_syntax_specific_actions(
                    classified_error,
                    user_profile,
                )
                actions.extend(syntax_actions)

            if (
                self.compatibility_detector
                and classified_error.category
                and classified_error.category.value == "compatibility"
            ):
                compat_actions = self._generate_compatibility_specific_actions(
                    classified_error,
                    user_profile,
                )
                actions.extend(compat_actions)

            # Add context-specific actions
            context_actions = self._generate_context_specific_actions(
                classified_error,
                user_profile,
            )
            actions.extend(context_actions)

            return actions

        except Exception as e:
            logger.error(f"Error generating specialized actions: {e}")
            return []

    def _generate_syntax_specific_actions(
        self,
        classified_error: ClassifiedError,
        user_profile: UserProfile | None,
    ) -> list[GuidanceAction]:
        """Generate syntax-specific guidance actions."""
        try:
            actions = []

            if not self.syntax_analyzer:
                return actions

            # Get language from error context
            language = (
                classified_error.context.language
                if classified_error.context
                else "unknown"
            )

            # Generate language-specific syntax checking action
            check_action = GuidanceAction(
                id=f"syntax_check_{language}",
                title=f"Check {language.title()} Syntax",
                description=f"Verify {language} syntax using language-specific tools",
                priority=ActionPriority.HIGH,
                category=GuidanceType.DIAGNOSTIC_STEPS,
                command=self._get_syntax_check_command(language),
                expected_outcome="Syntax validation completed",
                estimated_time="1-3 minutes",
                difficulty_level=UserExperienceLevel.BEGINNER,
            )
            actions.append(check_action)

            # Add linting action for supported languages
            if language in ["python", "javascript", "typescript"]:
                lint_action = GuidanceAction(
                    id=f"lint_{language}",
                    title=f"Run {language.title()} Linter",
                    description=f"Use linter to identify {language} code quality issues",
                    priority=ActionPriority.MEDIUM,
                    category=GuidanceType.DIAGNOSTIC_STEPS,
                    command=self._get_linter_command(language),
                    expected_outcome="Code quality report generated",
                    dependencies=[check_action.id],
                    estimated_time="2-5 minutes",
                    difficulty_level=UserExperienceLevel.INTERMEDIATE,
                )
                actions.append(lint_action)

            return actions

        except Exception as e:
            logger.error(f"Error generating syntax-specific actions: {e}")
            return []

    def _generate_compatibility_specific_actions(
        self,
        classified_error: ClassifiedError,
        user_profile: UserProfile | None,
    ) -> list[GuidanceAction]:
        """Generate compatibility-specific guidance actions."""
        try:
            actions = []

            if not self.compatibility_detector:
                return actions

            language = (
                classified_error.context.language
                if classified_error.context
                else "unknown"
            )

            # Version check action
            version_action = GuidanceAction(
                id=f"check_version_{language}",
                title=f"Check {language.title()} Version",
                description=f"Verify current {language} version and compatibility",
                priority=ActionPriority.HIGH,
                category=GuidanceType.DIAGNOSTIC_STEPS,
                command=self._get_version_check_command(language),
                expected_outcome="Version information displayed",
                estimated_time="1 minute",
                difficulty_level=UserExperienceLevel.BEGINNER,
            )
            actions.append(version_action)

            # Grammar update action
            grammar_action = GuidanceAction(
                id=f"update_grammar_{language}",
                title=f"Update {language.title()} Grammar",
                description=f"Download/update tree-sitter grammar for {language}",
                priority=ActionPriority.MEDIUM,
                category=GuidanceType.RESOLUTION_SEQUENCE,
                command=f"treesitter-chunker download-grammar {language}",
                expected_outcome="Grammar updated successfully",
                dependencies=[version_action.id],
                estimated_time="2-10 minutes",
                difficulty_level=UserExperienceLevel.INTERMEDIATE,
            )
            actions.append(grammar_action)

            return actions

        except Exception as e:
            logger.error(f"Error generating compatibility-specific actions: {e}")
            return []

    def _generate_context_specific_actions(
        self,
        classified_error: ClassifiedError,
        user_profile: UserProfile | None,
    ) -> list[GuidanceAction]:
        """Generate actions based on error context."""
        try:
            actions = []

            if not classified_error.context:
                return actions

            context = classified_error.context

            # File-specific actions
            if context.file_path:
                file_action = GuidanceAction(
                    id="check_file_access",
                    title="Check File Access",
                    description=f"Verify file {context.file_path} is accessible",
                    priority=ActionPriority.HIGH,
                    category=GuidanceType.DIAGNOSTIC_STEPS,
                    command=f"ls -la {context.file_path}",
                    expected_outcome="File information displayed",
                    estimated_time="30 seconds",
                    difficulty_level=UserExperienceLevel.BEGINNER,
                )
                actions.append(file_action)

            # Location-specific actions
            if context.line_number:
                location_action = GuidanceAction(
                    id="examine_error_location",
                    title="Examine Error Location",
                    description=f"Review code at line {context.line_number}",
                    priority=ActionPriority.HIGH,
                    category=GuidanceType.IMMEDIATE_ACTION,
                    command=f"sed -n '{max(1, context.line_number - 2)},{context.line_number + 2}p' {context.file_path or 'file'}",
                    expected_outcome="Context around error location displayed",
                    estimated_time="1 minute",
                    difficulty_level=UserExperienceLevel.BEGINNER,
                )
                actions.append(location_action)

            return actions

        except Exception as e:
            logger.error(f"Error generating context-specific actions: {e}")
            return []

    def _format_action_title(
        self,
        pattern: str,
        classified_error: ClassifiedError,
    ) -> str:
        """Format action title from pattern."""
        try:
            # Convert pattern to title case and make it action-oriented
            title = pattern.replace("_", " ").title()

            # Make it action-oriented
            if not any(
                title.startswith(verb)
                for verb in ["Check", "Verify", "Review", "Fix", "Update", "Run"]
            ):
                title = "Review " + title

            return title

        except Exception:
            return "Perform Action"

    def _format_action_description(
        self,
        pattern: str,
        classified_error: ClassifiedError,
    ) -> str:
        """Format action description from pattern."""
        try:
            # Use the pattern as description, with some context
            description = pattern

            # Add context if available
            if classified_error.context and classified_error.context.language:
                description += f" for {classified_error.context.language}"

            return description

        except Exception:
            return "Perform the specified action to address the error"

    def _determine_action_priority(
        self,
        guidance_type: GuidanceType,
        classified_error: ClassifiedError,
    ) -> ActionPriority:
        """Determine priority for an action based on guidance type and error severity."""
        try:
            severity = (
                classified_error.severity.value
                if classified_error.severity
                else "warning"
            )

            # Map severity and guidance type to priority
            if severity == "critical":
                if guidance_type == GuidanceType.IMMEDIATE_ACTION:
                    return ActionPriority.CRITICAL
                return ActionPriority.HIGH
            if severity == "error":
                if guidance_type == GuidanceType.IMMEDIATE_ACTION:
                    return ActionPriority.HIGH
                return ActionPriority.MEDIUM
            if guidance_type == GuidanceType.PREVENTIVE_MEASURES:
                return ActionPriority.LOW
            return ActionPriority.MEDIUM

        except Exception:
            return ActionPriority.MEDIUM

    def _enhance_action_with_template(
        self,
        action: GuidanceAction,
        pattern: str,
        classified_error: ClassifiedError,
    ):
        """Enhance action with template data if available."""
        try:
            # Map patterns to template keys
            pattern_lower = pattern.lower()
            template_key = None

            if "syntax" in pattern_lower:
                template_key = "check_syntax"
            elif "linter" in pattern_lower or "lint" in pattern_lower:
                template_key = "run_linter"
            elif "version" in pattern_lower:
                template_key = "check_versions"
            elif "grammar" in pattern_lower:
                template_key = "update_grammar"
            elif "config" in pattern_lower:
                template_key = "validate_config"
            elif "permission" in pattern_lower:
                template_key = "check_permissions"

            if template_key and template_key in self.action_templates:
                template = self.action_templates[template_key]

                # Format template with error context
                context = classified_error.context
                variables = {
                    "language": (
                        context.language if context and context.language else "unknown"
                    ),
                    "file_path": (
                        context.file_path if context and context.file_path else "file"
                    ),
                    "config_path": "chunker.config.yaml",
                }

                if "command" in template:
                    action.command = template["command"].format(**variables)
                if "expected_outcome" in template:
                    action.expected_outcome = template["expected_outcome"]
                if "estimated_time" in template:
                    action.estimated_time = template["estimated_time"]

                # Add dependencies if defined
                if template_key in self.dependency_rules:
                    action.dependencies = self.dependency_rules[template_key].copy()

        except Exception as e:
            logger.debug(f"Could not enhance action with template: {e}")

    def _calculate_total_time(self, actions: list[GuidanceAction]) -> str:
        """Calculate estimated total time for all actions."""
        try:
            total_minutes = 0

            for action in actions:
                if action.estimated_time:
                    # Extract minutes from time estimates like "2-5 minutes"
                    time_match = re.search(
                        r"(\d+)(?:-(\d+))?\s*minutes?",
                        action.estimated_time,
                    )
                    if time_match:
                        min_time = int(time_match.group(1))
                        max_time = (
                            int(time_match.group(2))
                            if time_match.group(2)
                            else min_time
                        )
                        avg_time = (min_time + max_time) / 2
                        total_minutes += avg_time

            if total_minutes < 60:
                return f"{int(total_minutes)} minutes"
            hours = int(total_minutes // 60)
            minutes = int(total_minutes % 60)
            return f"{hours}h {minutes}m"

        except Exception:
            return "Unknown"

    def _determine_difficulty_level(
        self,
        classified_error: ClassifiedError,
        user_profile: UserProfile | None,
    ) -> UserExperienceLevel:
        """Determine difficulty level for the guidance sequence."""
        try:
            # Base difficulty on error severity and type
            severity = (
                classified_error.severity.value
                if classified_error.severity
                else "warning"
            )
            category = (
                classified_error.category.value
                if classified_error.category
                else "unknown"
            )

            if severity == "critical":
                base_level = UserExperienceLevel.ADVANCED
            elif severity == "error":
                base_level = UserExperienceLevel.INTERMEDIATE
            else:
                base_level = UserExperienceLevel.BEGINNER

            # Adjust based on error category
            if category in ["system", "compatibility"]:
                # Bump up difficulty for system and compatibility issues
                levels = list(UserExperienceLevel)
                current_index = levels.index(base_level)
                if current_index < len(levels) - 1:
                    base_level = levels[current_index + 1]

            # Consider user profile if available
            if user_profile:
                user_level = user_profile.experience_level
                # Use the higher of the two levels
                levels = list(UserExperienceLevel)
                base_index = levels.index(base_level)
                user_index = levels.index(user_level)
                base_level = levels[max(base_index, user_index)]

            return base_level

        except Exception:
            return UserExperienceLevel.INTERMEDIATE

    def _get_syntax_check_command(self, language: str) -> str | None:
        """Get syntax check command for a language."""
        commands = {
            "python": "python -m py_compile {file_path}",
            "javascript": "node --check {file_path}",
            "typescript": "tsc --noEmit {file_path}",
            "go": "go fmt -n {file_path}",
            "rust": "rustc --parse-only {file_path}",
            "java": "javac -Xstdout /dev/null {file_path}",
            "cpp": "g++ -fsyntax-only {file_path}",
            "c": "gcc -fsyntax-only {file_path}",
        }
        return commands.get(language.lower())

    def _get_linter_command(self, language: str) -> str | None:
        """Get linter command for a language."""
        commands = {
            "python": "pylint {file_path}",
            "javascript": "eslint {file_path}",
            "typescript": "tslint {file_path}",
            "go": "golint {file_path}",
            "rust": "cargo clippy",
            "java": "checkstyle {file_path}",
        }
        return commands.get(language.lower())

    def _get_version_check_command(self, language: str) -> str | None:
        """Get version check command for a language."""
        commands = {
            "python": "python --version",
            "javascript": "node --version",
            "typescript": "tsc --version",
            "go": "go version",
            "rust": "rustc --version",
            "java": "java -version",
            "cpp": "g++ --version",
            "c": "gcc --version",
        }
        return commands.get(language.lower())

    def personalize_guidance(
        self,
        sequence: GuidanceSequence,
        user_profile: UserProfile,
    ) -> GuidanceSequence:
        """Personalize guidance sequence for a specific user profile.

        Args:
            sequence: Original guidance sequence
            user_profile: User profile for personalization

        Returns:
            Personalized guidance sequence
        """
        try:
            # Create a copy of the sequence for personalization
            personalized_actions = []

            for action in sequence.actions:
                # Adjust action based on user experience level
                personalized_action = self._personalize_action(action, user_profile)

                # Filter based on user preferences
                if self._should_include_action(personalized_action, user_profile):
                    personalized_actions.append(personalized_action)

            # Create personalized sequence
            personalized_sequence = GuidanceSequence(
                id=f"{sequence.id}_personalized_{user_profile.user_id}",
                name=f"{sequence.name} (Personalized)",
                description=f"Personalized for {user_profile.experience_level.value} user: {sequence.description}",
                error_context=sequence.error_context,
                actions=personalized_actions,
                estimated_total_time=self._calculate_total_time(personalized_actions),
                difficulty_level=user_profile.experience_level,
                success_rate=sequence.success_rate,
                tags=[
                    *sequence.tags,
                    "personalized",
                    user_profile.experience_level.value,
                ],
            )

            logger.info(
                f"Personalized guidance sequence for user {user_profile.user_id}",
            )
            return personalized_sequence

        except Exception as e:
            logger.error(f"Error personalizing guidance: {e}")
            return sequence  # Return original if personalization fails

    def _personalize_action(
        self,
        action: GuidanceAction,
        user_profile: UserProfile,
    ) -> GuidanceAction:
        """Personalize a single action for a user profile."""
        try:
            personalized_action = GuidanceAction(
                id=f"{action.id}_personalized",
                title=action.title,
                description=self._personalize_description(
                    action.description,
                    user_profile,
                ),
                priority=action.priority,
                category=action.category,
                command=action.command,
                expected_outcome=action.expected_outcome,
                troubleshooting_notes=action.troubleshooting_notes,
                dependencies=action.dependencies,
                estimated_time=self._adjust_time_estimate(
                    action.estimated_time,
                    user_profile,
                ),
                difficulty_level=action.difficulty_level,
                success_criteria=action.success_criteria,
                failure_indicators=action.failure_indicators,
            )

            # Adjust difficulty-specific attributes
            if user_profile.experience_level == UserExperienceLevel.BEGINNER:
                # Add more detailed explanations for beginners
                personalized_action.description += (
                    " (Step-by-step guidance will be provided)"
                )
                if action.command:
                    personalized_action.troubleshooting_notes = (
                        f"Run this command in your terminal: {action.command}"
                    )
            elif user_profile.experience_level == UserExperienceLevel.EXPERT:
                # Provide more concise instructions for experts
                personalized_action.description = self._make_description_concise(
                    action.description,
                )

            return personalized_action

        except Exception as e:
            logger.error(f"Error personalizing action: {e}")
            return action

    def _personalize_description(
        self,
        description: str,
        user_profile: UserProfile,
    ) -> str:
        """Personalize action description based on user profile."""
        try:
            if user_profile.experience_level == UserExperienceLevel.BEGINNER:
                # Add more context for beginners
                if "check" in description.lower():
                    description += (
                        ". This will help identify the root cause of the issue."
                    )
                elif "fix" in description.lower():
                    description += (
                        ". Make sure to backup your code before making changes."
                    )

            # Adjust for preferred languages
            if user_profile.language_preferences:
                primary_lang = user_profile.language_preferences[0]
                description = description.replace("language", primary_lang)

            return description

        except Exception:
            return description

    def _should_include_action(
        self,
        action: GuidanceAction,
        user_profile: UserProfile,
    ) -> bool:
        """Determine if an action should be included for this user."""
        try:
            # Check if user has already completed this type of action
            if action.id in user_profile.completed_actions:
                return False

            # Filter based on experience level
            if (
                user_profile.experience_level == UserExperienceLevel.EXPERT
                and action.difficulty_level == UserExperienceLevel.BEGINNER
                and action.category == GuidanceType.LEARNING_RESOURCES
            ):
                return False

            # Filter based on user preferences
            if (
                user_profile.preferred_guidance_style == "summary"
                and action.category == GuidanceType.DIAGNOSTIC_STEPS
                and action.priority in [ActionPriority.LOW, ActionPriority.OPTIONAL]
            ):
                return False

            return True

        except Exception:
            return True

    def _adjust_time_estimate(
        self,
        time_estimate: str | None,
        user_profile: UserProfile,
    ) -> str | None:
        """Adjust time estimate based on user experience level."""
        try:
            if not time_estimate:
                return time_estimate

            # Beginners typically take longer
            if user_profile.experience_level == UserExperienceLevel.BEGINNER:
                # Extract minutes and multiply by 1.5
                time_match = re.search(r"(\d+)(?:-(\d+))?\s*minutes?", time_estimate)
                if time_match:
                    min_time = int(time_match.group(1))
                    max_time = (
                        int(time_match.group(2)) if time_match.group(2) else min_time
                    )

                    adj_min = int(min_time * 1.5)
                    adj_max = int(max_time * 1.5)

                    if adj_min == adj_max:
                        return f"{adj_min} minutes"
                    return f"{adj_min}-{adj_max} minutes"

            # Experts typically take less time
            elif user_profile.experience_level == UserExperienceLevel.EXPERT:
                time_match = re.search(r"(\d+)(?:-(\d+))?\s*minutes?", time_estimate)
                if time_match:
                    min_time = int(time_match.group(1))
                    max_time = (
                        int(time_match.group(2)) if time_match.group(2) else min_time
                    )

                    adj_min = max(1, int(min_time * 0.7))
                    adj_max = max(1, int(max_time * 0.7))

                    if adj_min == adj_max:
                        return f"{adj_min} minutes"
                    return f"{adj_min}-{adj_max} minutes"

            return time_estimate

        except Exception:
            return time_estimate

    def _make_description_concise(self, description: str) -> str:
        """Make description more concise for expert users."""
        try:
            # Remove unnecessary words and phrases
            concise = description

            removals = [
                "Please ",
                "Make sure to ",
                "Don't forget to ",
                "It's important to ",
                "You should ",
                "Try to ",
            ]

            for removal in removals:
                concise = concise.replace(removal, "")

            # Capitalize first letter after removal
            if concise:
                concise = concise[0].upper() + concise[1:]

            return concise

        except Exception:
            return description


class ActionSequenceGenerator:
    """Generates action sequences with dependency management."""

    def __init__(self):
        """Initialize the action sequence generator."""
        self.dependency_graph: dict[str, set[str]] = defaultdict(set)
        self.action_registry: dict[str, GuidanceAction] = {}

        logger.info("Initialized ActionSequenceGenerator")

    def register_action(self, action: GuidanceAction):
        """Register an action in the sequence generator.

        Args:
            action: Action to register
        """
        self.action_registry[action.id] = action

        # Update dependency graph
        for dep_id in action.dependencies:
            self.dependency_graph[action.id].add(dep_id)

    def generate_sequence(self, action_ids: list[str]) -> list[GuidanceAction]:
        """Generate ordered sequence of actions respecting dependencies.

        Args:
            action_ids: List of action IDs to sequence

        Returns:
            List of actions in dependency order

        Raises:
            ValueError: If circular dependencies or missing actions are found
        """
        try:
            # Validate all actions exist
            missing_actions = [
                aid for aid in action_ids if aid not in self.action_registry
            ]
            if missing_actions:
                raise ValueError(f"Missing actions: {missing_actions}")

            # Collect all required actions (including dependencies)
            required_actions = set(action_ids)
            queue = list(action_ids)

            while queue:
                current_id = queue.pop(0)
                if current_id in self.action_registry:
                    action = self.action_registry[current_id]
                    for dep_id in action.dependencies:
                        if dep_id not in required_actions:
                            required_actions.add(dep_id)
                            queue.append(dep_id)

            # Topological sort to respect dependencies
            sorted_actions = self._topological_sort(list(required_actions))

            # Return action objects in order
            return [
                self.action_registry[aid]
                for aid in sorted_actions
                if aid in self.action_registry
            ]

        except Exception as e:
            logger.error(f"Error generating action sequence: {e}")
            raise RuntimeError(f"Failed to generate sequence: {e}") from e

    def _topological_sort(self, action_ids: list[str]) -> list[str]:
        """Perform topological sort on action dependencies."""
        try:
            # Build in-degree count
            in_degree = dict.fromkeys(action_ids, 0)

            for action_id in action_ids:
                if action_id in self.action_registry:
                    action = self.action_registry[action_id]
                    for dep_id in action.dependencies:
                        if dep_id in in_degree:
                            in_degree[action_id] += 1

            # Kahn's algorithm
            queue = [aid for aid, degree in in_degree.items() if degree == 0]
            result = []

            while queue:
                current = queue.pop(0)
                result.append(current)

                # Find actions that depend on current
                for action_id in action_ids:
                    if action_id in self.action_registry:
                        action = self.action_registry[action_id]
                        if current in action.dependencies:
                            in_degree[action_id] -= 1
                            if in_degree[action_id] == 0:
                                queue.append(action_id)

            # Check for cycles
            if len(result) != len(action_ids):
                remaining = [aid for aid in action_ids if aid not in result]
                raise ValueError(
                    f"Circular dependency detected in actions: {remaining}",
                )

            return result

        except Exception as e:
            logger.error(f"Error in topological sort: {e}")
            raise

    def validate_dependencies(self, action_ids: list[str]) -> list[str]:
        """Validate action dependencies and return any issues.

        Args:
            action_ids: List of action IDs to validate

        Returns:
            List of validation error messages
        """
        issues = []

        try:
            for action_id in action_ids:
                if action_id not in self.action_registry:
                    issues.append(f"Action {action_id} not found in registry")
                    continue

                action = self.action_registry[action_id]
                for dep_id in action.dependencies:
                    if dep_id not in self.action_registry:
                        issues.append(
                            f"Action {action_id} depends on missing action {dep_id}",
                        )

            # Test for circular dependencies
            try:
                self._topological_sort(action_ids)
            except ValueError as e:
                issues.append(str(e))

        except Exception as e:
            issues.append(f"Validation error: {e}")

        return issues

    def get_action_dependencies(self, action_id: str) -> list[str]:
        """Get all dependencies for an action (transitive).

        Args:
            action_id: Action ID

        Returns:
            List of all dependency action IDs
        """
        try:
            if action_id not in self.action_registry:
                return []

            dependencies = set()
            queue = [action_id]
            visited = set()

            while queue:
                current = queue.pop(0)
                if current in visited:
                    continue

                visited.add(current)

                if current in self.action_registry:
                    action = self.action_registry[current]
                    for dep_id in action.dependencies:
                        if dep_id not in dependencies:
                            dependencies.add(dep_id)
                            queue.append(dep_id)

            return list(dependencies)

        except Exception as e:
            logger.error(f"Error getting dependencies for {action_id}: {e}")
            return []


class GuidancePersonalizer:
    """Personalizes guidance based on user preferences and history."""

    def __init__(self):
        """Initialize the guidance personalizer."""
        self.user_profiles: dict[str, UserProfile] = {}
        self.personalization_rules: dict[str, Any] = self._load_personalization_rules()

        logger.info("Initialized GuidancePersonalizer")

    def _load_personalization_rules(self) -> dict[str, Any]:
        """Load rules for personalizing guidance."""
        rules = {
            "experience_adjustments": {
                UserExperienceLevel.BEGINNER: {
                    "add_explanations": True,
                    "include_learning_resources": True,
                    "time_multiplier": 1.5,
                    "priority_filter": None,
                    "detailed_commands": True,
                },
                UserExperienceLevel.INTERMEDIATE: {
                    "add_explanations": False,
                    "include_learning_resources": False,
                    "time_multiplier": 1.0,
                    "priority_filter": None,
                    "detailed_commands": False,
                },
                UserExperienceLevel.ADVANCED: {
                    "add_explanations": False,
                    "include_learning_resources": False,
                    "time_multiplier": 0.8,
                    "priority_filter": [ActionPriority.HIGH, ActionPriority.CRITICAL],
                    "detailed_commands": False,
                },
                UserExperienceLevel.EXPERT: {
                    "add_explanations": False,
                    "include_learning_resources": False,
                    "time_multiplier": 0.6,
                    "priority_filter": [ActionPriority.CRITICAL],
                    "detailed_commands": False,
                },
            },
            "style_preferences": {
                "step_by_step": {
                    "include_all_steps": True,
                    "detailed_descriptions": True,
                    "show_dependencies": True,
                },
                "summary": {
                    "include_all_steps": False,
                    "detailed_descriptions": False,
                    "show_dependencies": False,
                    "max_actions": 5,
                },
                "detailed": {
                    "include_all_steps": True,
                    "detailed_descriptions": True,
                    "show_dependencies": True,
                    "add_troubleshooting": True,
                    "include_background_info": True,
                },
            },
        }
        return rules

    def register_user_profile(self, user_profile: UserProfile):
        """Register a user profile for personalization.

        Args:
            user_profile: User profile to register
        """
        self.user_profiles[user_profile.user_id] = user_profile
        logger.debug(f"Registered user profile for {user_profile.user_id}")

    def get_user_profile(self, user_id: str) -> UserProfile | None:
        """Get user profile by ID.

        Args:
            user_id: User ID

        Returns:
            User profile if found, None otherwise
        """
        return self.user_profiles.get(user_id)

    def personalize_sequence(
        self,
        sequence: GuidanceSequence,
        user_id: str,
    ) -> GuidanceSequence:
        """Personalize a guidance sequence for a specific user.

        Args:
            sequence: Original guidance sequence
            user_id: User ID for personalization

        Returns:
            Personalized guidance sequence
        """
        try:
            user_profile = self.user_profiles.get(user_id)
            if not user_profile:
                logger.warning(f"No profile found for user {user_id}, using defaults")
                return sequence

            # Get personalization rules for this user
            exp_rules = self.personalization_rules["experience_adjustments"].get(
                user_profile.experience_level,
                {},
            )
            style_rules = self.personalization_rules["style_preferences"].get(
                user_profile.preferred_guidance_style,
                {},
            )

            # Filter and modify actions
            personalized_actions = []

            for action in sequence.actions:
                # Apply experience-level filtering
                if self._should_include_action_for_user(
                    action,
                    user_profile,
                    exp_rules,
                ):
                    personalized_action = self._personalize_action_for_user(
                        action,
                        user_profile,
                        exp_rules,
                        style_rules,
                    )
                    personalized_actions.append(personalized_action)

            # Apply style-specific modifications
            if style_rules.get("max_actions"):
                # Limit number of actions for summary style
                max_actions = style_rules["max_actions"]
                # Keep highest priority actions
                personalized_actions.sort(
                    key=lambda a: self._get_priority_value(a.priority),
                    reverse=True,
                )
                personalized_actions = personalized_actions[:max_actions]

            # Create personalized sequence
            personalized_sequence = GuidanceSequence(
                id=f"{sequence.id}_personalized_{user_id}",
                name=f"{sequence.name} (Personalized for {user_profile.experience_level.value})",
                description=self._personalize_description(
                    sequence.description,
                    user_profile,
                ),
                error_context=sequence.error_context,
                actions=personalized_actions,
                estimated_total_time=self._adjust_total_time(
                    sequence.estimated_total_time,
                    exp_rules.get("time_multiplier", 1.0),
                ),
                difficulty_level=user_profile.experience_level,
                success_rate=sequence.success_rate,
                tags=[*sequence.tags, "personalized", f"user_{user_id}"],
            )

            logger.info(f"Personalized sequence for user {user_id}")
            return personalized_sequence

        except Exception as e:
            logger.error(f"Error personalizing sequence for user {user_id}: {e}")
            return sequence

    def _should_include_action_for_user(
        self,
        action: GuidanceAction,
        user_profile: UserProfile,
        rules: dict[str, Any],
    ) -> bool:
        """Determine if action should be included for user."""
        try:
            # Check priority filter
            priority_filter = rules.get("priority_filter")
            if priority_filter and action.priority not in priority_filter:
                return False

            # Check if user has completed similar actions
            if (
                action.category == GuidanceType.LEARNING_RESOURCES
                and len(user_profile.completed_actions) > 10
            ):
                # Skip learning resources for experienced users
                return False

            # Check language preferences
            if user_profile.language_preferences:
                action_desc = action.description.lower()
                if any(
                    lang in action_desc for lang in user_profile.language_preferences
                ):
                    return True
                # If action is language-specific but not user's preference, deprioritize
                if any(
                    lang in action_desc
                    for lang in ["python", "javascript", "java", "rust", "go"]
                ):
                    return action.priority in [
                        ActionPriority.CRITICAL,
                        ActionPriority.HIGH,
                    ]

            return True

        except Exception:
            return True

    def _personalize_action_for_user(
        self,
        action: GuidanceAction,
        user_profile: UserProfile,
        exp_rules: dict[str, Any],
        style_rules: dict[str, Any],
    ) -> GuidanceAction:
        """Personalize an individual action for a user."""
        try:
            personalized_action = GuidanceAction(
                id=f"{action.id}_user_{user_profile.user_id}",
                title=action.title,
                description=self._personalize_action_description(
                    action.description,
                    user_profile,
                    exp_rules,
                    style_rules,
                ),
                priority=action.priority,
                category=action.category,
                command=self._personalize_command(
                    action.command,
                    user_profile,
                    exp_rules,
                ),
                expected_outcome=action.expected_outcome,
                troubleshooting_notes=self._personalize_troubleshooting(
                    action.troubleshooting_notes,
                    user_profile,
                    style_rules,
                ),
                dependencies=action.dependencies,
                estimated_time=self._adjust_action_time(
                    action.estimated_time,
                    exp_rules.get("time_multiplier", 1.0),
                ),
                difficulty_level=action.difficulty_level,
                success_criteria=action.success_criteria,
                failure_indicators=action.failure_indicators,
            )

            return personalized_action

        except Exception as e:
            logger.error(f"Error personalizing action: {e}")
            return action

    def _personalize_action_description(
        self,
        description: str,
        user_profile: UserProfile,
        exp_rules: dict[str, Any],
        style_rules: dict[str, Any],
    ) -> str:
        """Personalize action description."""
        try:
            personalized = description

            # Add explanations for beginners
            if (
                exp_rules.get("add_explanations")
                and user_profile.experience_level == UserExperienceLevel.BEGINNER
            ):
                if "syntax" in description.lower():
                    personalized += (
                        " (Syntax refers to the rules of the programming language)"
                    )
                elif "linter" in description.lower():
                    personalized += (
                        " (A linter checks code for potential errors and style issues)"
                    )
                elif "grammar" in description.lower():
                    personalized += (
                        " (Grammar files help parse specific programming languages)"
                    )

            # Make more concise for advanced users
            if user_profile.experience_level in [
                UserExperienceLevel.ADVANCED,
                UserExperienceLevel.EXPERT,
            ]:
                # Remove unnecessary words
                personalized = re.sub(
                    r"\b(please|kindly|make sure to)\b",
                    "",
                    personalized,
                    flags=re.IGNORECASE,
                )
                personalized = re.sub(r"\s+", " ", personalized).strip()

            # Adjust for style preferences
            if not style_rules.get("detailed_descriptions"):
                # Make more concise for summary style
                sentences = personalized.split(".")
                personalized = sentences[0] + "." if sentences else personalized

            return personalized

        except Exception:
            return description

    def _personalize_command(
        self,
        command: str | None,
        user_profile: UserProfile,
        exp_rules: dict[str, Any],
    ) -> str | None:
        """Personalize command based on user preferences."""
        try:
            if not command:
                return command

            personalized = command

            # Add detailed explanation for beginners
            if (
                exp_rules.get("detailed_commands")
                and user_profile.experience_level == UserExperienceLevel.BEGINNER
            ):
                # Could add explanatory comments or fuller paths
                if "python" in command:
                    personalized = f"# Check Python syntax\n{command}"
                elif "git" in command:
                    personalized = f"# Git command\n{command}"

            return personalized

        except Exception:
            return command

    def _personalize_troubleshooting(
        self,
        notes: str | None,
        user_profile: UserProfile,
        style_rules: dict[str, Any],
    ) -> str | None:
        """Personalize troubleshooting notes."""
        try:
            if not notes:
                if style_rules.get("add_troubleshooting"):
                    return "If this step fails, check the error message and try the next step"
                return notes

            if user_profile.experience_level == UserExperienceLevel.BEGINNER:
                # Add more detailed troubleshooting
                return f"{notes}. If you encounter issues, double-check the command syntax and ensure you have proper permissions."
            if user_profile.experience_level == UserExperienceLevel.EXPERT:
                # Keep it concise
                return notes.split(".")[0] + "." if "." in notes else notes

            return notes

        except Exception:
            return notes

    def _personalize_description(
        self,
        description: str,
        user_profile: UserProfile,
    ) -> str:
        """Personalize sequence description."""
        try:
            personalized = description

            if user_profile.experience_level == UserExperienceLevel.BEGINNER:
                personalized += " This guidance is tailored for beginners and includes detailed explanations."
            elif user_profile.experience_level == UserExperienceLevel.EXPERT:
                personalized += " This guidance is optimized for expert users with concise instructions."

            return personalized

        except Exception:
            return description

    def _adjust_total_time(
        self,
        time_str: str | None,
        multiplier: float,
    ) -> str | None:
        """Adjust total time estimate based on multiplier."""
        try:
            if not time_str or multiplier == 1.0:
                return time_str

            # Extract time components
            if "h" in time_str and "m" in time_str:
                # Format: "2h 30m"
                hours_match = re.search(r"(\d+)h", time_str)
                minutes_match = re.search(r"(\d+)m", time_str)

                if hours_match and minutes_match:
                    hours = int(hours_match.group(1))
                    minutes = int(minutes_match.group(1))
                    total_minutes = hours * 60 + minutes

                    adjusted_minutes = int(total_minutes * multiplier)
                    adj_hours = adjusted_minutes // 60
                    adj_mins = adjusted_minutes % 60

                    if adj_hours > 0:
                        return f"{adj_hours}h {adj_mins}m"
                    return f"{adj_mins} minutes"

            elif "minutes" in time_str:
                # Format: "30 minutes"
                minutes_match = re.search(r"(\d+)", time_str)
                if minutes_match:
                    minutes = int(minutes_match.group(1))
                    adjusted = int(minutes * multiplier)
                    return f"{adjusted} minutes"

            return time_str

        except Exception:
            return time_str

    def _adjust_action_time(
        self,
        time_str: str | None,
        multiplier: float,
    ) -> str | None:
        """Adjust action time estimate."""
        try:
            if not time_str or multiplier == 1.0:
                return time_str

            # Handle ranges like "2-5 minutes"
            range_match = re.search(r"(\d+)-(\d+)\s*minutes?", time_str)
            if range_match:
                min_time = int(range_match.group(1))
                max_time = int(range_match.group(2))

                adj_min = int(min_time * multiplier)
                adj_max = int(max_time * multiplier)

                return f"{adj_min}-{adj_max} minutes"

            # Handle single values
            single_match = re.search(r"(\d+)\s*minutes?", time_str)
            if single_match:
                minutes = int(single_match.group(1))
                adjusted = int(minutes * multiplier)
                return f"{adjusted} minutes"

            return time_str

        except Exception:
            return time_str

    def _get_priority_value(self, priority: ActionPriority) -> int:
        """Get numeric value for priority sorting."""
        priority_values = {
            ActionPriority.CRITICAL: 5,
            ActionPriority.HIGH: 4,
            ActionPriority.MEDIUM: 3,
            ActionPriority.LOW: 2,
            ActionPriority.OPTIONAL: 1,
        }
        return priority_values.get(priority, 0)

    def update_user_feedback(
        self,
        user_id: str,
        action_id: str,
        feedback: dict[str, Any],
    ):
        """Update user profile with feedback from completed actions.

        Args:
            user_id: User ID
            action_id: Action ID that was completed
            feedback: Feedback data (success, time_taken, difficulty, etc.)
        """
        try:
            if user_id not in self.user_profiles:
                return

            user_profile = self.user_profiles[user_id]

            # Add to feedback history
            feedback_entry = {
                "action_id": action_id,
                "timestamp": datetime.now(UTC).isoformat(),
                "feedback": feedback,
            }
            user_profile.feedback_history.append(feedback_entry)

            # Update completed/failed actions
            if feedback.get("success"):
                if action_id not in user_profile.completed_actions:
                    user_profile.completed_actions.append(action_id)
                # Remove from failed if previously failed
                if action_id in user_profile.failed_actions:
                    user_profile.failed_actions.remove(action_id)
            elif action_id not in user_profile.failed_actions:
                user_profile.failed_actions.append(action_id)

            # Adjust experience level based on feedback patterns
            self._adjust_experience_level(user_profile)

            logger.debug(f"Updated user {user_id} feedback for action {action_id}")

        except Exception as e:
            logger.error(f"Error updating user feedback: {e}")

    def _adjust_experience_level(self, user_profile: UserProfile):
        """Adjust user experience level based on feedback history."""
        try:
            if len(user_profile.feedback_history) < 5:
                return  # Need more data

            recent_feedback = user_profile.feedback_history[-10:]  # Last 10 actions

            success_rate = sum(
                1 for f in recent_feedback if f["feedback"].get("success", False)
            ) / len(recent_feedback)
            avg_difficulty_handled = sum(
                self._get_difficulty_value(
                    f["feedback"].get("difficulty_level", "intermediate"),
                )
                for f in recent_feedback
            ) / len(recent_feedback)

            # Promote if consistently successful with current level
            if (
                success_rate > 0.8
                and avg_difficulty_handled
                >= self._get_difficulty_value(user_profile.experience_level.value)
            ):
                levels = list(UserExperienceLevel)
                current_index = levels.index(user_profile.experience_level)
                if current_index < len(levels) - 1:
                    user_profile.experience_level = levels[current_index + 1]
                    logger.info(
                        f"Promoted user {user_profile.user_id} to {user_profile.experience_level.value}",
                    )

            # Consider demotion if consistently failing
            elif success_rate < 0.4:
                levels = list(UserExperienceLevel)
                current_index = levels.index(user_profile.experience_level)
                if current_index > 0:
                    user_profile.experience_level = levels[current_index - 1]
                    logger.info(
                        f"Demoted user {user_profile.user_id} to {user_profile.experience_level.value}",
                    )

        except Exception as e:
            logger.error(f"Error adjusting experience level: {e}")

    def _get_difficulty_value(self, difficulty: str) -> int:
        """Get numeric value for difficulty level."""
        difficulty_values = {
            "beginner": 1,
            "intermediate": 2,
            "advanced": 3,
            "expert": 4,
        }
        return difficulty_values.get(difficulty.lower(), 2)


class GuidanceQualityAssessor:
    """Assesses the quality and effectiveness of generated guidance."""

    def __init__(self):
        """Initialize the guidance quality assessor."""
        self.quality_metrics = self._load_quality_metrics()
        self.assessment_history: list[dict[str, Any]] = []

        logger.info("Initialized GuidanceQualityAssessor")

    def _load_quality_metrics(self) -> dict[str, dict[str, Any]]:
        """Load quality assessment metrics."""
        metrics = {
            "completeness": {
                "weight": 0.25,
                "criteria": [
                    "covers_immediate_actions",
                    "includes_diagnostic_steps",
                    "provides_resolution_sequence",
                    "suggests_preventive_measures",
                ],
            },
            "clarity": {
                "weight": 0.20,
                "criteria": [
                    "clear_action_titles",
                    "descriptive_instructions",
                    "unambiguous_commands",
                    "appropriate_language_level",
                ],
            },
            "actionability": {
                "weight": 0.25,
                "criteria": [
                    "executable_commands",
                    "realistic_time_estimates",
                    "clear_success_criteria",
                    "defined_expected_outcomes",
                ],
            },
            "relevance": {
                "weight": 0.15,
                "criteria": [
                    "matches_error_category",
                    "appropriate_for_context",
                    "user_level_appropriate",
                    "technology_specific",
                ],
            },
            "effectiveness": {
                "weight": 0.15,
                "criteria": [
                    "dependency_order_correct",
                    "comprehensive_coverage",
                    "error_prevention_included",
                    "learning_opportunities",
                ],
            },
        }
        return metrics

    def assess_guidance_quality(
        self,
        sequence: GuidanceSequence,
        error_context: dict[str, Any] | None = None,
        user_profile: UserProfile | None = None,
    ) -> dict[str, Any]:
        """Assess the quality of a guidance sequence.

        Args:
            sequence: Guidance sequence to assess
            error_context: Optional error context for relevance assessment
            user_profile: Optional user profile for personalization assessment

        Returns:
            Dictionary containing quality assessment results
        """
        try:
            assessment = {
                "sequence_id": sequence.id,
                "overall_score": 0.0,
                "metric_scores": {},
                "strengths": [],
                "weaknesses": [],
                "recommendations": [],
                "assessed_at": datetime.now(UTC).isoformat(),
            }

            total_weighted_score = 0.0

            # Assess each quality metric
            for metric_name, metric_config in self.quality_metrics.items():
                score = self._assess_metric(
                    sequence,
                    metric_name,
                    metric_config,
                    error_context,
                    user_profile,
                )
                weight = metric_config["weight"]

                assessment["metric_scores"][metric_name] = {
                    "score": score,
                    "weight": weight,
                    "weighted_score": score * weight,
                }

                total_weighted_score += score * weight

            assessment["overall_score"] = total_weighted_score

            # Generate insights
            assessment["strengths"] = self._identify_strengths(
                assessment["metric_scores"],
            )
            assessment["weaknesses"] = self._identify_weaknesses(
                assessment["metric_scores"],
            )
            assessment["recommendations"] = self._generate_recommendations(
                assessment,
                sequence,
            )

            # Store assessment
            self.assessment_history.append(assessment)

            logger.info(
                f"Assessed guidance quality for {sequence.id}: {assessment['overall_score']:.2f}",
            )
            return assessment

        except Exception as e:
            logger.error(f"Error assessing guidance quality: {e}")
            return {"sequence_id": sequence.id, "overall_score": 0.0, "error": str(e)}

    def _assess_metric(
        self,
        sequence: GuidanceSequence,
        metric_name: str,
        metric_config: dict[str, Any],
        error_context: dict[str, Any] | None,
        user_profile: UserProfile | None,
    ) -> float:
        """Assess a specific quality metric."""
        try:
            if metric_name == "completeness":
                return self._assess_completeness(sequence)
            if metric_name == "clarity":
                return self._assess_clarity(sequence, user_profile)
            if metric_name == "actionability":
                return self._assess_actionability(sequence)
            if metric_name == "relevance":
                return self._assess_relevance(sequence, error_context, user_profile)
            if metric_name == "effectiveness":
                return self._assess_effectiveness(sequence)
            return 0.5  # Default neutral score

        except Exception as e:
            logger.error(f"Error assessing metric {metric_name}: {e}")
            return 0.0

    def _assess_completeness(self, sequence: GuidanceSequence) -> float:
        """Assess completeness of guidance sequence."""
        try:
            score = 0.0
            total_criteria = 4

            # Check for immediate actions
            immediate_actions = [
                a
                for a in sequence.actions
                if a.category == GuidanceType.IMMEDIATE_ACTION
            ]
            if immediate_actions:
                score += 0.25

            # Check for diagnostic steps
            diagnostic_actions = [
                a
                for a in sequence.actions
                if a.category == GuidanceType.DIAGNOSTIC_STEPS
            ]
            if diagnostic_actions:
                score += 0.25

            # Check for resolution sequence
            resolution_actions = [
                a
                for a in sequence.actions
                if a.category == GuidanceType.RESOLUTION_SEQUENCE
            ]
            if resolution_actions:
                score += 0.25

            # Check for preventive measures
            preventive_actions = [
                a
                for a in sequence.actions
                if a.category == GuidanceType.PREVENTIVE_MEASURES
            ]
            if preventive_actions:
                score += 0.25

            return min(score, 1.0)

        except Exception:
            return 0.0

    def _assess_clarity(
        self,
        sequence: GuidanceSequence,
        user_profile: UserProfile | None,
    ) -> float:
        """Assess clarity of guidance instructions."""
        try:
            score = 0.0
            total_actions = len(sequence.actions)

            if total_actions == 0:
                return 0.0

            clear_titles = 0
            descriptive_instructions = 0
            clear_commands = 0
            appropriate_level = 0

            for action in sequence.actions:
                # Clear action titles (not empty, has verb)
                if action.title and len(action.title.split()) >= 2:
                    if any(
                        action.title.lower().startswith(verb)
                        for verb in ["check", "run", "verify", "fix", "update"]
                    ):
                        clear_titles += 1

                # Descriptive instructions
                if action.description and len(action.description) > 20:
                    descriptive_instructions += 1

                # Clear commands
                if action.command and not any(
                    unclear in action.command.lower()
                    for unclear in ["todo", "fixme", "placeholder"]
                ):
                    clear_commands += 1

                # Appropriate language level
                if user_profile:
                    if self._is_language_appropriate(action, user_profile):
                        appropriate_level += 1
                else:
                    appropriate_level += 1  # Assume appropriate if no profile

            # Calculate average score
            score = (
                (clear_titles / total_actions) * 0.25
                + (descriptive_instructions / total_actions) * 0.25
                + (
                    clear_commands
                    / max(1, sum(1 for a in sequence.actions if a.command))
                )
                * 0.25
                + (appropriate_level / total_actions) * 0.25
            )

            return min(score, 1.0)

        except Exception:
            return 0.0

    def _assess_actionability(self, sequence: GuidanceSequence) -> float:
        """Assess actionability of guidance steps."""
        try:
            score = 0.0
            total_actions = len(sequence.actions)

            if total_actions == 0:
                return 0.0

            executable_commands = 0
            realistic_times = 0
            clear_criteria = 0
            defined_outcomes = 0

            for action in sequence.actions:
                # Executable commands
                if action.command and self._is_command_executable(action.command):
                    executable_commands += 1

                # Realistic time estimates
                if action.estimated_time and self._is_time_realistic(
                    action.estimated_time,
                ):
                    realistic_times += 1

                # Clear success criteria
                if action.success_criteria:
                    clear_criteria += 1

                # Defined expected outcomes
                if action.expected_outcome:
                    defined_outcomes += 1

            score = (
                (
                    executable_commands
                    / max(1, sum(1 for a in sequence.actions if a.command))
                )
                * 0.25
                + (realistic_times / total_actions) * 0.25
                + (clear_criteria / total_actions) * 0.25
                + (defined_outcomes / total_actions) * 0.25
            )

            return min(score, 1.0)

        except Exception:
            return 0.0

    def _assess_relevance(
        self,
        sequence: GuidanceSequence,
        error_context: dict[str, Any] | None,
        user_profile: UserProfile | None,
    ) -> float:
        """Assess relevance of guidance to error and user."""
        try:
            score = 0.0

            # Matches error category
            if error_context and sequence.error_context:
                error_category = error_context.get("category", "")
                sequence_category = sequence.error_context.get("category", "")
                if error_category == sequence_category:
                    score += 0.25
            else:
                score += 0.125  # Partial credit if context missing

            # Appropriate for context
            if sequence.error_context:
                score += 0.25  # Has context

            # User level appropriate
            if user_profile:
                if sequence.difficulty_level == user_profile.experience_level:
                    score += 0.25
                elif (
                    abs(
                        list(UserExperienceLevel).index(sequence.difficulty_level)
                        - list(UserExperienceLevel).index(
                            user_profile.experience_level,
                        ),
                    )
                    <= 1
                ):
                    score += 0.15  # Close enough
            else:
                score += 0.125  # Partial credit if no profile

            # Technology specific
            if sequence.error_context and sequence.error_context.get("context", {}).get(
                "language",
            ):
                score += 0.25

            return min(score, 1.0)

        except Exception:
            return 0.0

    def _assess_effectiveness(self, sequence: GuidanceSequence) -> float:
        """Assess effectiveness of guidance sequence."""
        try:
            score = 0.0

            # Dependency order correct
            dependency_issues = sequence.validate_dependencies()
            if not dependency_issues:
                score += 0.25

            # Comprehensive coverage
            categories_covered = {action.category for action in sequence.actions}
            expected_categories = {
                GuidanceType.IMMEDIATE_ACTION,
                GuidanceType.DIAGNOSTIC_STEPS,
                GuidanceType.RESOLUTION_SEQUENCE,
            }
            coverage_ratio = len(
                categories_covered.intersection(expected_categories),
            ) / len(expected_categories)
            score += coverage_ratio * 0.25

            # Error prevention included
            preventive_actions = [
                a
                for a in sequence.actions
                if a.category == GuidanceType.PREVENTIVE_MEASURES
            ]
            if preventive_actions:
                score += 0.25

            # Learning opportunities
            learning_actions = [
                a
                for a in sequence.actions
                if a.category == GuidanceType.LEARNING_RESOURCES
            ]
            troubleshooting_notes = [
                a for a in sequence.actions if a.troubleshooting_notes
            ]
            if learning_actions or troubleshooting_notes:
                score += 0.25

            return min(score, 1.0)

        except Exception:
            return 0.0

    def _is_language_appropriate(
        self,
        action: GuidanceAction,
        user_profile: UserProfile,
    ) -> bool:
        """Check if action language is appropriate for user level."""
        try:
            description = action.description.lower()

            if user_profile.experience_level == UserExperienceLevel.BEGINNER:
                # Beginner-friendly terms
                complex_terms = [
                    "refactor",
                    "transpile",
                    "deprecated",
                    "polymorphism",
                    "abstraction",
                ]
                return not any(term in description for term in complex_terms)
            if user_profile.experience_level == UserExperienceLevel.EXPERT:
                # Should be concise, technical terms OK
                return len(description.split()) < 50  # Not too verbose

            return True  # Intermediate/Advanced are generally OK

        except Exception:
            return True

    def _is_command_executable(self, command: str) -> bool:
        """Check if command appears to be executable."""
        try:
            # Basic checks for executable commands
            if not command.strip():
                return False

            # Contains placeholder that wasn't replaced
            if "{" in command and "}" in command:
                return False

            # Has recognizable command structure
            common_commands = [
                "python",
                "node",
                "git",
                "npm",
                "pip",
                "cargo",
                "go",
                "java",
                "gcc",
                "ls",
                "cat",
                "grep",
            ]
            first_word = command.split(maxsplit=1)[0].lower()

            return any(cmd in first_word for cmd in common_commands)

        except Exception:
            return False

    def _is_time_realistic(self, time_estimate: str) -> bool:
        """Check if time estimate is realistic."""
        try:
            # Extract minutes
            minutes_match = re.search(
                r"(\d+)(?:-(\d+))?\s*(?:minutes?|mins?)",
                time_estimate.lower(),
            )
            if minutes_match:
                min_time = int(minutes_match.group(1))
                max_time = (
                    int(minutes_match.group(2)) if minutes_match.group(2) else min_time
                )

                # Realistic range: 30 seconds to 2 hours
                return 0.5 <= min_time <= 120 and max_time <= 120

            # Check for hours
            hours_match = re.search(r"(\d+)h", time_estimate.lower())
            if hours_match:
                hours = int(hours_match.group(1))
                return hours <= 8  # Not more than a work day

            return True  # Assume OK if we can't parse

        except Exception:
            return True

    def _identify_strengths(
        self,
        metric_scores: dict[str, dict[str, float]],
    ) -> list[str]:
        """Identify strengths based on metric scores."""
        strengths = []

        for metric, scores in metric_scores.items():
            if scores["score"] >= 0.8:
                if metric == "completeness":
                    strengths.append("Comprehensive coverage of all guidance types")
                elif metric == "clarity":
                    strengths.append("Clear and well-written instructions")
                elif metric == "actionability":
                    strengths.append("Practical and executable action steps")
                elif metric == "relevance":
                    strengths.append(
                        "Highly relevant to the specific error and user context",
                    )
                elif metric == "effectiveness":
                    strengths.append("Well-structured and effective guidance sequence")

        return strengths

    def _identify_weaknesses(
        self,
        metric_scores: dict[str, dict[str, float]],
    ) -> list[str]:
        """Identify weaknesses based on metric scores."""
        weaknesses = []

        for metric, scores in metric_scores.items():
            if scores["score"] < 0.6:
                if metric == "completeness":
                    weaknesses.append(
                        "Missing some guidance categories (immediate actions, diagnostics, resolution, or prevention)",
                    )
                elif metric == "clarity":
                    weaknesses.append("Instructions could be clearer or more detailed")
                elif metric == "actionability":
                    weaknesses.append(
                        "Some actions lack clear commands or success criteria",
                    )
                elif metric == "relevance":
                    weaknesses.append(
                        "May not be fully relevant to the error context or user level",
                    )
                elif metric == "effectiveness":
                    weaknesses.append(
                        "Guidance structure or dependencies could be improved",
                    )

        return weaknesses

    def _generate_recommendations(
        self,
        assessment: dict[str, Any],
        sequence: GuidanceSequence,
    ) -> list[str]:
        """Generate recommendations for improvement."""
        recommendations = []

        metric_scores = assessment["metric_scores"]

        # Low completeness
        if metric_scores.get("completeness", {}).get("score", 0) < 0.7:
            missing_categories = []
            existing_categories = {action.category for action in sequence.actions}

            if GuidanceType.IMMEDIATE_ACTION not in existing_categories:
                missing_categories.append("immediate actions")
            if GuidanceType.DIAGNOSTIC_STEPS not in existing_categories:
                missing_categories.append("diagnostic steps")
            if GuidanceType.RESOLUTION_SEQUENCE not in existing_categories:
                missing_categories.append("resolution sequence")
            if GuidanceType.PREVENTIVE_MEASURES not in existing_categories:
                missing_categories.append("preventive measures")

            if missing_categories:
                recommendations.append(
                    f"Add {', '.join(missing_categories)} to improve completeness",
                )

        # Low clarity
        if metric_scores.get("clarity", {}).get("score", 0) < 0.7:
            recommendations.append(
                "Improve action titles and descriptions for better clarity",
            )
            recommendations.append(
                "Ensure commands are properly formatted and complete",
            )

        # Low actionability
        if metric_scores.get("actionability", {}).get("score", 0) < 0.7:
            recommendations.append(
                "Add clear success criteria and expected outcomes for each action",
            )
            recommendations.append("Provide more specific and executable commands")

        # Low relevance
        if metric_scores.get("relevance", {}).get("score", 0) < 0.7:
            recommendations.append(
                "Better align guidance with specific error context and user level",
            )
            recommendations.append("Include more technology-specific guidance")

        # Low effectiveness
        if metric_scores.get("effectiveness", {}).get("score", 0) < 0.7:
            recommendations.append("Review action dependencies and sequencing")
            recommendations.append("Add more comprehensive error prevention strategies")

        # General recommendations
        if assessment["overall_score"] < 0.8:
            recommendations.append("Consider user feedback to refine guidance quality")
            recommendations.append("Test guidance sequences with real users")

        return recommendations

    def get_quality_statistics(self) -> dict[str, Any]:
        """Get statistics about guidance quality assessments.

        Returns:
            Dictionary containing quality statistics
        """
        try:
            if not self.assessment_history:
                return {"message": "No assessments available"}

            scores = [
                a["overall_score"]
                for a in self.assessment_history
                if "overall_score" in a
            ]

            if not scores:
                return {"message": "No valid scores available"}

            stats = {
                "total_assessments": len(self.assessment_history),
                "average_quality_score": sum(scores) / len(scores),
                "highest_score": max(scores),
                "lowest_score": min(scores),
                "quality_distribution": {
                    "excellent": len([s for s in scores if s >= 0.9]),
                    "good": len([s for s in scores if 0.7 <= s < 0.9]),
                    "fair": len([s for s in scores if 0.5 <= s < 0.7]),
                    "poor": len([s for s in scores if s < 0.5]),
                },
            }

            # Most common strengths and weaknesses
            all_strengths = []
            all_weaknesses = []

            for assessment in self.assessment_history:
                all_strengths.extend(assessment.get("strengths", []))
                all_weaknesses.extend(assessment.get("weaknesses", []))

            if all_strengths:
                strength_counts = defaultdict(int)
                for strength in all_strengths:
                    strength_counts[strength] += 1
                stats["common_strengths"] = sorted(
                    strength_counts.items(),
                    key=lambda x: x[1],
                    reverse=True,
                )[:3]

            if all_weaknesses:
                weakness_counts = defaultdict(int)
                for weakness in all_weaknesses:
                    weakness_counts[weakness] += 1
                stats["common_weaknesses"] = sorted(
                    weakness_counts.items(),
                    key=lambda x: x[1],
                    reverse=True,
                )[:3]

            return stats

        except Exception as e:
            logger.error(f"Error generating quality statistics: {e}")
            return {"error": str(e)}


# Factory function for easy setup
def create_guidance_system(
    template_manager: TemplateManager | None = None,
    compatibility_detector: CompatibilityErrorDetector | None = None,
    syntax_analyzer: SyntaxErrorAnalyzer | None = None,
) -> tuple[
    UserActionGuidanceEngine,
    ActionSequenceGenerator,
    GuidancePersonalizer,
    GuidanceQualityAssessor,
]:
    """Create a complete guidance system with all components.

    Args:
        template_manager: Optional template manager for formatting
        compatibility_detector: Optional compatibility error detector
        syntax_analyzer: Optional syntax error analyzer

    Returns:
        Tuple of (engine, generator, personalizer, assessor)
    """
    engine = UserActionGuidanceEngine(
        template_manager,
        compatibility_detector,
        syntax_analyzer,
    )
    generator = ActionSequenceGenerator()
    personalizer = GuidancePersonalizer()
    assessor = GuidanceQualityAssessor()

    logger.info("Created complete guidance system")
    return engine, generator, personalizer, assessor

"""Comprehensive error handling pipeline integration for Phase 1.7 - Smart Error Handling & User Guidance.

This module implements the complete error handling pipeline integration that orchestrates
all Phase 1.7 components to provide intelligent error handling and user guidance.

The integration includes:
- ErrorHandlingPipeline: Complete pipeline processing errors through all phases
- ErrorHandlingOrchestrator: Session management and coordination
- Pipeline statistics tracking and health monitoring
- Fallback response generation for graceful degradation
- CLI integration points for Phase 1.8 alignment

Key Features:
- Processes errors through complete pipeline (classify → detect → analyze → guide → troubleshoot)
- Session management for tracking error contexts across requests
- Pipeline health validation and performance metrics collection
- Graceful fallback mechanisms when components are unavailable
- CLI integration points for grammar validation commands
- Error reporting for grammar management workflows
- Compatibility checking for grammar validation
- User experience optimization for CLI users

Phase 1.8 Alignment:
- CLI Integration Points: Grammar validation commands and error reporting
- Error Reporting: Grammar management workflow integration
- Compatibility Checking: Grammar validation and version compatibility
- User Experience: CLI-optimized guidance and troubleshooting

The system is designed to be production-ready with comprehensive error handling,
logging, and graceful degradation capabilities.
"""

from __future__ import annotations

import json
import logging
import threading
import time
import uuid
import weakref
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import UTC, datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

# Import Group C dependencies with fallback handling
try:
    from .classifier import (
        ClassifiedError,
        ErrorCategory,
        ErrorClassifier,
        ErrorContext,
        ErrorSeverity,
        ErrorSource,
    )
except ImportError as e:
    logging.warning(f"Failed to import Group C classifier: {e}")
    ErrorClassifier = None
    ClassifiedError = None
    ErrorCategory = None
    ErrorSeverity = None
    ErrorSource = None
    ErrorContext = None

try:
    from .compatibility_detector import CompatibilityErrorDetector
except ImportError as e:
    logging.warning(f"Failed to import Group C compatibility_detector: {e}")
    CompatibilityErrorDetector = None

try:
    from .syntax_analyzer import SyntaxErrorAnalyzer
except ImportError as e:
    logging.warning(f"Failed to import Group C syntax_analyzer: {e}")
    SyntaxErrorAnalyzer = None

# Import Group D dependencies with fallback handling
try:
    from .templates import (
        ErrorTemplate,
        TemplateFormat,
        TemplateManager,
        TemplateType,
        create_template_system,
        render_template,
    )
except ImportError as e:
    logging.warning(f"Failed to import Group D templates: {e}")
    TemplateManager = None
    ErrorTemplate = None
    TemplateFormat = None
    TemplateType = None
    render_template = None
    create_template_system = None

try:
    from .guidance_engine import (
        ActionPriority,
        GuidanceAction,
        GuidanceSequence,
        GuidanceType,
        UserActionGuidanceEngine,
        UserExperienceLevel,
        UserProfile,
    )
except ImportError as e:
    logging.warning(f"Failed to import Group D guidance_engine: {e}")
    UserActionGuidanceEngine = None
    GuidanceSequence = None
    GuidanceAction = None
    UserProfile = None
    UserExperienceLevel = None
    GuidanceType = None
    ActionPriority = None

try:
    from .troubleshooting import (
        Solution,
        SolutionType,
        TroubleshootingCategory,
        TroubleshootingDatabase,
        TroubleshootingEntry,
    )
except ImportError as e:
    logging.warning(f"Failed to import Group D troubleshooting: {e}")
    TroubleshootingDatabase = None
    TroubleshootingEntry = None
    Solution = None
    TroubleshootingCategory = None
    SolutionType = None

logger = logging.getLogger(__name__)


class PipelineStage(Enum):
    """Pipeline processing stages."""

    CLASSIFY = "classify"
    DETECT = "detect"
    ANALYZE = "analyze"
    GUIDE = "guide"
    TROUBLESHOOT = "troubleshoot"
    COMPLETE = "complete"
    FAILED = "failed"


class SessionStatus(Enum):
    """Error handling session status."""

    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"


@dataclass
class PipelineMetrics:
    """Pipeline performance and health metrics."""

    total_processed: int = 0
    successful_processed: int = 0
    failed_processed: int = 0
    avg_processing_time: float = 0.0
    stage_success_rates: dict[PipelineStage, float] = field(default_factory=dict)
    component_availability: dict[str, bool] = field(default_factory=dict)
    last_health_check: datetime = field(
        default_factory=lambda: datetime.now(UTC),
    )
    error_distribution: dict[str, int] = field(default_factory=lambda: defaultdict(int))

    def update_processing_time(self, processing_time: float) -> None:
        """Update average processing time with new measurement."""
        if self.total_processed == 0:
            self.avg_processing_time = processing_time
        else:
            # Moving average
            self.avg_processing_time = (
                self.avg_processing_time * self.total_processed + processing_time
            ) / (self.total_processed + 1)

    def record_success(self, stage: PipelineStage, processing_time: float) -> None:
        """Record a successful processing stage."""
        self.successful_processed += 1
        self.total_processed += 1
        self.update_processing_time(processing_time)

        # Update stage success rate
        if stage not in self.stage_success_rates:
            self.stage_success_rates[stage] = 1.0
        else:
            current_rate = self.stage_success_rates[stage]
            # Simple moving average for success rate
            self.stage_success_rates[stage] = (current_rate + 1.0) / 2.0

    def record_failure(self, stage: PipelineStage, error_type: str) -> None:
        """Record a failed processing stage."""
        self.failed_processed += 1
        self.total_processed += 1
        self.error_distribution[error_type] += 1

        # Update stage success rate
        if stage not in self.stage_success_rates:
            self.stage_success_rates[stage] = 0.0
        else:
            current_rate = self.stage_success_rates[stage]
            # Simple moving average for success rate
            self.stage_success_rates[stage] = current_rate / 2.0

    def get_success_rate(self) -> float:
        """Calculate overall pipeline success rate."""
        if self.total_processed == 0:
            return 0.0
        return self.successful_processed / self.total_processed

    def to_dict(self) -> dict[str, Any]:
        """Convert metrics to dictionary representation."""
        return {
            "total_processed": self.total_processed,
            "successful_processed": self.successful_processed,
            "failed_processed": self.failed_processed,
            "success_rate": self.get_success_rate(),
            "avg_processing_time": self.avg_processing_time,
            "stage_success_rates": {
                stage.value: rate for stage, rate in self.stage_success_rates.items()
            },
            "component_availability": self.component_availability,
            "last_health_check": self.last_health_check.isoformat(),
            "error_distribution": dict(self.error_distribution),
        }


@dataclass
class ErrorHandlingSession:
    """Tracks error handling session state and context."""

    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str | None = None
    start_time: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_activity: datetime = field(default_factory=lambda: datetime.now(UTC))
    status: SessionStatus = SessionStatus.ACTIVE
    current_stage: PipelineStage = PipelineStage.CLASSIFY
    errors_processed: list[str] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)
    user_profile: UserProfile | None = None
    processing_history: list[dict[str, Any]] = field(default_factory=list)
    fallback_count: int = 0

    def update_activity(self) -> None:
        """Update last activity timestamp."""
        self.last_activity = datetime.now(UTC)

    def add_error(self, error_id: str, stage: PipelineStage) -> None:
        """Add processed error to session."""
        self.errors_processed.append(error_id)
        self.current_stage = stage
        self.update_activity()

    def add_processing_record(
        self,
        stage: PipelineStage,
        success: bool,
        processing_time: float,
        details: dict[str, Any],
    ) -> None:
        """Add processing record to session history."""
        record = {
            "stage": stage.value,
            "success": success,
            "processing_time": processing_time,
            "timestamp": datetime.now(UTC).isoformat(),
            "details": details,
        }
        self.processing_history.append(record)
        self.update_activity()

    def is_expired(self, timeout_minutes: int = 30) -> bool:
        """Check if session has expired."""
        if self.status != SessionStatus.ACTIVE:
            return True

        timeout_delta = datetime.now(UTC) - self.last_activity
        return timeout_delta.total_seconds() > (timeout_minutes * 60)

    def to_dict(self) -> dict[str, Any]:
        """Convert session to dictionary representation."""
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "start_time": self.start_time.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "status": self.status.value,
            "current_stage": self.current_stage.value,
            "errors_processed": self.errors_processed,
            "context": self.context,
            "processing_history": self.processing_history,
            "fallback_count": self.fallback_count,
        }


@dataclass
class PipelineResult:
    """Result from error handling pipeline processing."""

    session_id: str
    error_id: str
    success: bool
    stage_reached: PipelineStage
    processing_time: float
    classified_error: ClassifiedError | None = None
    compatibility_issues: dict[str, Any] | None = None
    syntax_analysis: dict[str, Any] | None = None
    guidance_sequence: GuidanceSequence | None = None
    troubleshooting_entries: list[TroubleshootingEntry] = field(default_factory=list)
    fallback_response: dict[str, Any] | None = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert result to dictionary representation."""
        return {
            "session_id": self.session_id,
            "error_id": self.error_id,
            "success": self.success,
            "stage_reached": self.stage_reached.value,
            "processing_time": self.processing_time,
            "classified_error": (
                self.classified_error.to_dict() if self.classified_error else None
            ),
            "compatibility_issues": self.compatibility_issues,
            "syntax_analysis": self.syntax_analysis,
            "guidance_sequence": (
                self.guidance_sequence.to_dict() if self.guidance_sequence else None
            ),
            "troubleshooting_entries": [
                entry.to_dict() for entry in self.troubleshooting_entries
            ],
            "fallback_response": self.fallback_response,
            "errors": self.errors,
            "warnings": self.warnings,
            "metadata": self.metadata,
        }


class ErrorHandlingPipeline:
    """Complete error handling pipeline that integrates all Phase 1.7 components."""

    def __init__(
        self,
        error_classifier: ErrorClassifier | None = None,
        compatibility_detector: CompatibilityErrorDetector | None = None,
        syntax_analyzer: SyntaxErrorAnalyzer | None = None,
        template_manager: TemplateManager | None = None,
        guidance_engine: UserActionGuidanceEngine | None = None,
        troubleshooting_db: TroubleshootingDatabase | None = None,
        max_concurrent_processes: int = 4,
    ):
        """Initialize the error handling pipeline.

        Args:
            error_classifier: Error classification component
            compatibility_detector: Compatibility detection component
            syntax_analyzer: Syntax analysis component
            template_manager: Template management component
            guidance_engine: User action guidance component
            troubleshooting_db: Troubleshooting database component
            max_concurrent_processes: Maximum concurrent pipeline processes
        """
        # Initialize components with graceful fallback
        self.error_classifier = error_classifier
        self.compatibility_detector = compatibility_detector
        self.syntax_analyzer = syntax_analyzer
        self.template_manager = template_manager
        self.guidance_engine = guidance_engine
        self.troubleshooting_db = troubleshooting_db

        # Create fallback components if needed
        if self.template_manager is None and create_template_system:
            try:
                library, _renderer, _validator = create_template_system()
                self.template_manager = library.manager
                logger.info("Created fallback template system")
            except Exception as e:
                logger.warning(f"Failed to create fallback template system: {e}")

        # Pipeline configuration
        self.max_concurrent_processes = max_concurrent_processes
        self.executor = ThreadPoolExecutor(max_workers=max_concurrent_processes)

        # Processing locks for thread safety (initialize first)
        self._metrics_lock = threading.Lock()

        # Pipeline metrics and health monitoring
        self.metrics = PipelineMetrics()
        self._update_component_availability()

        logger.info(
            f"Initialized ErrorHandlingPipeline with {self._count_available_components()} available components",
        )

    def _count_available_components(self) -> int:
        """Count available pipeline components."""
        components = [
            self.error_classifier,
            self.compatibility_detector,
            self.syntax_analyzer,
            self.template_manager,
            self.guidance_engine,
            self.troubleshooting_db,
        ]
        return sum(1 for component in components if component is not None)

    def _update_component_availability(self) -> None:
        """Update component availability in metrics."""
        with self._metrics_lock:
            self.metrics.component_availability = {
                "error_classifier": self.error_classifier is not None,
                "compatibility_detector": self.compatibility_detector is not None,
                "syntax_analyzer": self.syntax_analyzer is not None,
                "template_manager": self.template_manager is not None,
                "guidance_engine": self.guidance_engine is not None,
                "troubleshooting_db": self.troubleshooting_db is not None,
            }
            self.metrics.last_health_check = datetime.now(UTC)

    def process_error(
        self,
        error_message: str,
        error_context: dict[str, Any] | None = None,
        session: ErrorHandlingSession | None = None,
        user_profile: UserProfile | None = None,
    ) -> PipelineResult:
        """Process error through complete pipeline.

        Args:
            error_message: Error message to process
            error_context: Optional error context information
            session: Optional error handling session
            user_profile: Optional user profile for personalization

        Returns:
            PipelineResult with processing results
        """
        start_time = time.time()
        error_id = str(uuid.uuid4())

        if session is None:
            session = ErrorHandlingSession()

        result = PipelineResult(
            session_id=session.session_id,
            error_id=error_id,
            success=False,
            stage_reached=PipelineStage.CLASSIFY,
            processing_time=0.0,
        )

        try:
            # Stage 1: Classify Error
            classified_error = self._classify_error(
                error_message,
                error_context,
                session,
                result,
            )
            result.classified_error = classified_error
            result.stage_reached = PipelineStage.CLASSIFY

            if classified_error is None:
                result.warnings.append(
                    "Error classification failed, proceeding with fallback",
                )

            # Stage 2: Detect Compatibility Issues
            if self.compatibility_detector and classified_error:
                compatibility_issues = self._detect_compatibility(
                    classified_error,
                    session,
                    result,
                )
                result.compatibility_issues = compatibility_issues
                result.stage_reached = PipelineStage.DETECT

            # Stage 3: Analyze Syntax
            if self.syntax_analyzer and classified_error:
                syntax_analysis = self._analyze_syntax(
                    classified_error,
                    session,
                    result,
                )
                result.syntax_analysis = syntax_analysis
                result.stage_reached = PipelineStage.ANALYZE

            # Stage 4: Generate Guidance
            if self.guidance_engine and classified_error:
                guidance_sequence = self._generate_guidance(
                    classified_error,
                    user_profile,
                    session,
                    result,
                )
                result.guidance_sequence = guidance_sequence
                result.stage_reached = PipelineStage.GUIDE

            # Stage 5: Search Troubleshooting Database
            if self.troubleshooting_db:
                troubleshooting_entries = self._search_troubleshooting(
                    error_message,
                    classified_error,
                    session,
                    result,
                )
                result.troubleshooting_entries = troubleshooting_entries
                result.stage_reached = PipelineStage.TROUBLESHOOT

            # Stage 6: Generate Fallback Response if needed
            if not any([result.guidance_sequence, result.troubleshooting_entries]):
                fallback_response = self._generate_fallback_response(
                    error_message,
                    classified_error,
                    error_context,
                )
                result.fallback_response = fallback_response
                session.fallback_count += 1

            result.stage_reached = PipelineStage.COMPLETE
            result.success = True

        except Exception as e:
            error_msg = f"Pipeline processing failed: {e}"
            result.errors.append(error_msg)
            result.stage_reached = PipelineStage.FAILED
            logger.error(error_msg, exc_info=True)

        finally:
            # Calculate processing time and update metrics
            processing_time = time.time() - start_time
            result.processing_time = processing_time

            # Update session
            session.add_error(error_id, result.stage_reached)
            session.add_processing_record(
                result.stage_reached,
                result.success,
                processing_time,
                {
                    "error_id": error_id,
                    "errors": result.errors,
                    "warnings": result.warnings,
                },
            )

            # Update pipeline metrics
            with self._metrics_lock:
                if result.success:
                    self.metrics.record_success(result.stage_reached, processing_time)
                else:
                    error_type = result.errors[0] if result.errors else "unknown_error"
                    self.metrics.record_failure(result.stage_reached, error_type)

        return result

    def _classify_error(
        self,
        error_message: str,
        error_context: dict[str, Any] | None,
        session: ErrorHandlingSession,
        result: PipelineResult,
    ) -> ClassifiedError | None:
        """Classify error using error classifier."""
        try:
            if not self.error_classifier or not ClassifiedError:
                return None

            # Convert context to ErrorContext if available
            context_obj = None
            if error_context and ErrorContext:
                try:
                    context_obj = ErrorContext(
                        file_path=error_context.get("file_path"),
                        line_number=error_context.get("line_number"),
                        column_number=error_context.get("column_number"),
                        language=error_context.get("language"),
                        grammar_version=error_context.get("grammar_version"),
                        user_agent=error_context.get("user_agent"),
                        session_id=error_context.get("session_id"),
                    )
                except Exception as e:
                    logger.warning(f"Failed to create ErrorContext: {e}")

            # Classify the error
            classified = self.error_classifier.classify_error(
                error_message,
                context_obj,
            )

            if classified:
                logger.debug(f"Successfully classified error: {classified.category}")

            return classified

        except Exception as e:
            error_msg = f"Error classification failed: {e}"
            result.errors.append(error_msg)
            logger.error(error_msg, exc_info=True)
            return None

    def _detect_compatibility(
        self,
        classified_error: ClassifiedError,
        session: ErrorHandlingSession,
        result: PipelineResult,
    ) -> dict[str, Any] | None:
        """Detect compatibility issues."""
        try:
            if not self.compatibility_detector:
                return None

            # Detect compatibility issues
            issues = self.compatibility_detector.detect_compatibility_errors(
                classified_error.message,
                (
                    classified_error.context.file_path
                    if classified_error.context
                    else None
                ),
                classified_error.context.language if classified_error.context else None,
            )

            if issues:
                logger.debug(f"Detected {len(issues)} compatibility issues")
                return {"issues": issues, "total_count": len(issues)}

            return None

        except Exception as e:
            error_msg = f"Compatibility detection failed: {e}"
            result.errors.append(error_msg)
            logger.error(error_msg, exc_info=True)
            return None

    def _analyze_syntax(
        self,
        classified_error: ClassifiedError,
        session: ErrorHandlingSession,
        result: PipelineResult,
    ) -> dict[str, Any] | None:
        """Analyze syntax errors."""
        try:
            if not self.syntax_analyzer:
                return None

            # Perform syntax analysis
            analysis = self.syntax_analyzer.analyze_syntax_error(
                classified_error.message,
                classified_error.context.language if classified_error.context else None,
                (
                    classified_error.context.file_path
                    if classified_error.context
                    else None
                ),
            )

            if analysis:
                logger.debug("Successfully performed syntax analysis")
                return analysis

            return None

        except Exception as e:
            error_msg = f"Syntax analysis failed: {e}"
            result.errors.append(error_msg)
            logger.error(error_msg, exc_info=True)
            return None

    def _generate_guidance(
        self,
        classified_error: ClassifiedError,
        user_profile: UserProfile | None,
        session: ErrorHandlingSession,
        result: PipelineResult,
    ) -> GuidanceSequence | None:
        """Generate user action guidance."""
        try:
            if not self.guidance_engine:
                return None

            # Generate guidance sequence
            sequence = self.guidance_engine.generate_guidance(
                classified_error,
                user_profile,
            )

            if sequence:
                logger.debug(
                    f"Generated guidance sequence with {len(sequence.actions)} actions",
                )

            return sequence

        except Exception as e:
            error_msg = f"Guidance generation failed: {e}"
            result.errors.append(error_msg)
            logger.error(error_msg, exc_info=True)
            return None

    def _search_troubleshooting(
        self,
        error_message: str,
        classified_error: ClassifiedError | None,
        session: ErrorHandlingSession,
        result: PipelineResult,
    ) -> list[TroubleshootingEntry]:
        """Search troubleshooting database."""
        try:
            if not self.troubleshooting_db:
                return []

            # Search for relevant troubleshooting entries
            search_results = self.troubleshooting_db.search(
                error_message,
                max_results=5,
            )
            entries = [entry for entry, score in search_results]

            if entries:
                logger.debug(f"Found {len(entries)} troubleshooting entries")

            return entries

        except Exception as e:
            error_msg = f"Troubleshooting search failed: {e}"
            result.errors.append(error_msg)
            logger.error(error_msg, exc_info=True)
            return []

    def _generate_fallback_response(
        self,
        error_message: str,
        classified_error: ClassifiedError | None,
        error_context: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Generate fallback response when main components fail."""
        try:
            fallback = {
                "type": "fallback_response",
                "error_message": error_message,
                "general_guidance": self._get_general_guidance(error_message),
                "suggested_actions": self._get_suggested_actions(
                    error_message,
                    classified_error,
                ),
                "resources": self._get_helpful_resources(error_message),
                "timestamp": datetime.now(UTC).isoformat(),
            }

            # Add context-specific guidance if available
            if error_context:
                if "language" in error_context:
                    fallback["language_specific_tips"] = self._get_language_tips(
                        error_context["language"],
                    )

                if "file_path" in error_context:
                    fallback["file_specific_tips"] = self._get_file_tips(
                        error_context["file_path"],
                    )

            logger.info("Generated fallback response")
            return fallback

        except Exception as e:
            logger.error(f"Failed to generate fallback response: {e}")
            return {
                "type": "minimal_fallback",
                "message": "Unable to provide detailed guidance. Please check the error message and documentation.",
                "timestamp": datetime.now(UTC).isoformat(),
            }

    def _get_general_guidance(self, error_message: str) -> list[str]:
        """Get general guidance based on error message patterns."""
        guidance = []

        error_lower = error_message.lower()

        if "syntax" in error_lower:
            guidance.extend(
                [
                    "Check for missing colons, parentheses, or brackets",
                    "Verify proper indentation",
                    "Look for typos in keywords or variable names",
                ],
            )

        if "file not found" in error_lower or "no such file" in error_lower:
            guidance.extend(
                [
                    "Verify the file path is correct",
                    "Check if the file exists in the expected location",
                    "Ensure you have proper file permissions",
                ],
            )

        if "permission" in error_lower or "access denied" in error_lower:
            guidance.extend(
                [
                    "Check file and directory permissions",
                    "Run with appropriate user privileges",
                    "Verify you have read/write access to the location",
                ],
            )

        if "grammar" in error_lower:
            guidance.extend(
                [
                    "Ensure the language grammar is installed",
                    "Try updating the grammar to the latest version",
                    "Check if the language is supported",
                ],
            )

        if not guidance:
            guidance = [
                "Review the error message carefully for clues",
                "Check the documentation for similar issues",
                "Try simplifying the operation to isolate the problem",
            ]

        return guidance

    def _get_suggested_actions(
        self,
        error_message: str,
        classified_error: ClassifiedError | None,
    ) -> list[str]:
        """Get suggested actions based on error classification."""
        actions = []

        if classified_error and hasattr(classified_error, "category"):
            if (
                classified_error.category
                and "syntax" in str(classified_error.category).lower()
            ):
                actions.extend(
                    [
                        "Use a code editor with syntax highlighting",
                        "Run a syntax checker or linter",
                        "Compare with working code examples",
                    ],
                )
            elif (
                classified_error.category
                and "compatibility" in str(classified_error.category).lower()
            ):
                actions.extend(
                    [
                        "Check version compatibility requirements",
                        "Update to compatible versions",
                        "Review migration documentation",
                    ],
                )

        # General actions based on error message
        error_lower = error_message.lower()

        if "install" in error_lower or "download" in error_lower:
            actions.extend(
                [
                    "Install missing dependencies",
                    "Check internet connectivity",
                    "Verify package repository access",
                ],
            )

        if "config" in error_lower:
            actions.extend(
                [
                    "Review configuration settings",
                    "Check configuration file syntax",
                    "Restore default configuration if needed",
                ],
            )

        return actions or ["Consult documentation and community resources"]

    def _get_helpful_resources(self, error_message: str) -> list[dict[str, str]]:
        """Get helpful resources based on error message."""
        resources = []

        # Add general resources
        resources.append(
            {
                "title": "TreeSitter Chunker Documentation",
                "type": "documentation",
                "url": "https://github.com/DataBassGit/treesitter-chunker",
            },
        )

        # Add language-specific resources based on error context
        if "python" in error_message.lower():
            resources.append(
                {
                    "title": "Python Documentation",
                    "type": "official_docs",
                    "url": "https://docs.python.org/",
                },
            )

        if "javascript" in error_message.lower():
            resources.append(
                {
                    "title": "MDN JavaScript Reference",
                    "type": "reference",
                    "url": "https://developer.mozilla.org/en-US/docs/Web/JavaScript",
                },
            )

        # Add grammar-specific resources
        if "grammar" in error_message.lower():
            resources.append(
                {
                    "title": "Tree-sitter Grammar Guide",
                    "type": "guide",
                    "url": "https://tree-sitter.github.io/tree-sitter/",
                },
            )

        return resources

    def _get_language_tips(self, language: str) -> list[str]:
        """Get language-specific tips."""
        tips = {
            "python": [
                "Use proper indentation (4 spaces recommended)",
                "Check for Python 2 vs Python 3 syntax differences",
                "Use pylint or flake8 for code quality checks",
            ],
            "javascript": [
                "Use a modern JavaScript parser for ES6+ features",
                "Check for missing semicolons or brackets",
                "Validate JSON syntax if working with JSON",
            ],
            "java": [
                "Ensure proper class and package structure",
                "Check for missing imports",
                "Verify Java version compatibility",
            ],
            "go": [
                "Run 'go fmt' to check formatting",
                "Use 'go vet' for static analysis",
                "Check module and import paths",
            ],
        }

        return tips.get(
            language.lower(),
            [
                f"Consult the {language} documentation",
                f"Use {language}-specific development tools",
                f"Check {language} community resources",
            ],
        )

    def _get_file_tips(self, file_path: str) -> list[str]:
        """Get file-specific tips."""
        if not file_path:
            return []

        file_path_lower = file_path.lower()

        if file_path_lower.endswith((".py", ".pyw")):
            return [
                "Check Python syntax and indentation",
                "Verify imports and module structure",
            ]
        if file_path_lower.endswith((".js", ".jsx")):
            return ["Validate JavaScript syntax", "Check for ES6+ compatibility"]
        if file_path_lower.endswith((".ts", ".tsx")):
            return ["Check TypeScript configuration", "Verify type definitions"]
        if file_path_lower.endswith(".json"):
            return ["Validate JSON syntax", "Check for trailing commas"]
        if file_path_lower.endswith((".yml", ".yaml")):
            return ["Check YAML indentation", "Validate YAML syntax"]

        return ["Check file format and syntax", "Verify file encoding"]

    def get_pipeline_health(self) -> dict[str, Any]:
        """Get pipeline health status and metrics."""
        with self._metrics_lock:
            health = {
                "status": (
                    "healthy"
                    if self.metrics.get_success_rate() > 0.8
                    else (
                        "degraded"
                        if self.metrics.get_success_rate() > 0.5
                        else "unhealthy"
                    )
                ),
                "metrics": self.metrics.to_dict(),
                "components": {
                    "available": sum(self.metrics.component_availability.values()),
                    "total": len(self.metrics.component_availability),
                    "details": self.metrics.component_availability,
                },
                "recommendations": [],
            }

            # Add recommendations based on health
            if health["status"] == "unhealthy":
                health["recommendations"].append(
                    "Check component availability and error logs",
                )

            if self.metrics.get_success_rate() < 0.9:
                health["recommendations"].append(
                    "Monitor error patterns and consider component updates",
                )

            if sum(self.metrics.component_availability.values()) < len(
                self.metrics.component_availability,
            ):
                unavailable = [
                    name
                    for name, available in self.metrics.component_availability.items()
                    if not available
                ]
                health["recommendations"].append(
                    f"Initialize missing components: {', '.join(unavailable)}",
                )

        return health

    def shutdown(self) -> None:
        """Shutdown pipeline and cleanup resources."""
        try:
            self.executor.shutdown(wait=True)
            logger.info("Pipeline shutdown completed")
        except Exception as e:
            logger.error(f"Error during pipeline shutdown: {e}")


class ErrorHandlingOrchestrator:
    """Orchestrates error handling sessions and manages pipeline instances."""

    def __init__(
        self,
        pipeline: ErrorHandlingPipeline,
        max_sessions: int = 100,
        session_timeout_minutes: int = 30,
    ):
        """Initialize the error handling orchestrator.

        Args:
            pipeline: Error handling pipeline instance
            max_sessions: Maximum number of concurrent sessions
            session_timeout_minutes: Session timeout in minutes
        """
        self.pipeline = pipeline
        self.max_sessions = max_sessions
        self.session_timeout_minutes = session_timeout_minutes

        # Session management
        self.active_sessions: dict[str, ErrorHandlingSession] = {}
        self.session_history: deque = deque(maxlen=1000)  # Keep last 1000 sessions

        # Thread safety
        self._sessions_lock = threading.Lock()

        # Start background cleanup task
        self._cleanup_timer = threading.Timer(
            300,
            self._cleanup_expired_sessions,
        )  # 5 minutes
        self._cleanup_timer.daemon = True
        self._cleanup_timer.start()

        logger.info(
            f"Initialized ErrorHandlingOrchestrator with max {max_sessions} sessions",
        )

    def create_session(
        self,
        user_id: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> ErrorHandlingSession:
        """Create a new error handling session.

        Args:
            user_id: Optional user identifier
            context: Optional session context

        Returns:
            New ErrorHandlingSession instance
        """
        with self._sessions_lock:
            # Cleanup expired sessions if needed
            if len(self.active_sessions) >= self.max_sessions:
                self._cleanup_expired_sessions()

            # Create new session
            session = ErrorHandlingSession(user_id=user_id)
            if context:
                session.context.update(context)

            self.active_sessions[session.session_id] = session
            logger.debug(f"Created new session: {session.session_id}")

            return session

    def get_session(self, session_id: str) -> ErrorHandlingSession | None:
        """Get existing session by ID.

        Args:
            session_id: Session identifier

        Returns:
            ErrorHandlingSession if found, None otherwise
        """
        with self._sessions_lock:
            session = self.active_sessions.get(session_id)

            if session and session.is_expired(self.session_timeout_minutes):
                # Move to history and remove from active
                session.status = SessionStatus.EXPIRED
                self.session_history.append(session)
                del self.active_sessions[session_id]
                return None

            if session:
                session.update_activity()

            return session

    def process_error_in_session(
        self,
        session_id: str,
        error_message: str,
        error_context: dict[str, Any] | None = None,
        user_profile: UserProfile | None = None,
    ) -> PipelineResult:
        """Process error within an existing session.

        Args:
            session_id: Session identifier
            error_message: Error message to process
            error_context: Optional error context
            user_profile: Optional user profile

        Returns:
            PipelineResult with processing results
        """
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found or expired")

        # Update session user profile if provided
        if user_profile:
            session.user_profile = user_profile

        # Process error through pipeline
        result = self.pipeline.process_error(
            error_message,
            error_context,
            session,
            user_profile or session.user_profile,
        )

        # Update session status based on result
        if result.success:
            session.status = (
                SessionStatus.COMPLETED
                if result.stage_reached == PipelineStage.COMPLETE
                else SessionStatus.ACTIVE
            )
        else:
            session.status = SessionStatus.FAILED

        return result

    def close_session(self, session_id: str) -> bool:
        """Close and archive a session.

        Args:
            session_id: Session identifier

        Returns:
            True if session was closed, False if not found
        """
        with self._sessions_lock:
            session = self.active_sessions.get(session_id)
            if not session:
                return False

            # Update status and move to history
            session.status = SessionStatus.COMPLETED
            self.session_history.append(session)
            del self.active_sessions[session_id]

            logger.debug(f"Closed session: {session_id}")
            return True

    def _cleanup_expired_sessions(self) -> None:
        """Cleanup expired sessions (background task)."""
        try:
            with self._sessions_lock:
                expired_sessions = []

                for session_id, session in list(self.active_sessions.items()):
                    if session.is_expired(self.session_timeout_minutes):
                        expired_sessions.append(session_id)

                # Move expired sessions to history
                for session_id in expired_sessions:
                    session = self.active_sessions[session_id]
                    session.status = SessionStatus.EXPIRED
                    self.session_history.append(session)
                    del self.active_sessions[session_id]

                if expired_sessions:
                    logger.info(f"Cleaned up {len(expired_sessions)} expired sessions")

            # Schedule next cleanup
            self._cleanup_timer = threading.Timer(300, self._cleanup_expired_sessions)
            self._cleanup_timer.daemon = True
            self._cleanup_timer.start()

        except Exception as e:
            logger.error(f"Error during session cleanup: {e}")

    def get_session_statistics(self) -> dict[str, Any]:
        """Get session management statistics.

        Returns:
            Dictionary containing session statistics
        """
        with self._sessions_lock:
            active_count = len(self.active_sessions)
            total_history = len(self.session_history)

            # Status distribution in history
            status_counts = defaultdict(int)
            for session in self.session_history:
                status_counts[session.status.value] += 1

            # Average session duration
            durations = []
            for session in list(self.session_history)[-100:]:  # Last 100 sessions
                if session.status in [SessionStatus.COMPLETED, SessionStatus.EXPIRED]:
                    duration = (
                        session.last_activity - session.start_time
                    ).total_seconds()
                    durations.append(duration)

            avg_duration = sum(durations) / len(durations) if durations else 0

            return {
                "active_sessions": active_count,
                "total_processed_sessions": total_history,
                "status_distribution": dict(status_counts),
                "average_session_duration_seconds": avg_duration,
                "max_sessions": self.max_sessions,
                "session_timeout_minutes": self.session_timeout_minutes,
                "pipeline_health": self.pipeline.get_pipeline_health(),
            }

    def shutdown(self) -> None:
        """Shutdown orchestrator and cleanup resources."""
        try:
            # Cancel cleanup timer
            if hasattr(self, "_cleanup_timer"):
                self._cleanup_timer.cancel()

            # Close all active sessions
            with self._sessions_lock:
                for session in self.active_sessions.values():
                    session.status = SessionStatus.COMPLETED
                    self.session_history.append(session)
                self.active_sessions.clear()

            # Shutdown pipeline
            self.pipeline.shutdown()

            logger.info("Orchestrator shutdown completed")

        except Exception as e:
            logger.error(f"Error during orchestrator shutdown: {e}")


# CLI Integration Points for Phase 1.8 Alignment


class CLIErrorIntegration:
    """CLI integration points for grammar management error handling."""

    def __init__(self, orchestrator: ErrorHandlingOrchestrator):
        """Initialize CLI error integration.

        Args:
            orchestrator: Error handling orchestrator instance
        """
        self.orchestrator = orchestrator

    def handle_grammar_validation_error(
        self,
        language: str,
        error_message: str,
        grammar_path: str | None = None,
    ) -> dict[str, Any]:
        """Handle grammar validation errors for CLI commands.

        Args:
            language: Programming language
            error_message: Error message from grammar validation
            grammar_path: Optional path to grammar file

        Returns:
            Dictionary containing error analysis and guidance
        """
        # Create CLI-specific context
        context = {
            "language": language,
            "source": "cli_grammar_validation",
            "grammar_path": grammar_path,
            "cli_context": True,
        }

        # Create session for this CLI operation
        session = self.orchestrator.create_session(context=context)

        try:
            # Process error through pipeline
            result = self.orchestrator.process_error_in_session(
                session.session_id,
                error_message,
                context,
            )

            # Format for CLI consumption
            cli_response = {
                "success": result.success,
                "error_category": (
                    result.classified_error.category.value
                    if result.classified_error
                    else "unknown"
                ),
                "severity": (
                    result.classified_error.severity.value
                    if result.classified_error
                    else "warning"
                ),
                "guidance": self._format_guidance_for_cli(result.guidance_sequence),
                "troubleshooting": self._format_troubleshooting_for_cli(
                    result.troubleshooting_entries,
                ),
                "quick_fixes": self._extract_quick_fixes(result),
                "suggested_commands": self._extract_cli_commands(result),
            }

            return cli_response

        finally:
            # Clean up session
            self.orchestrator.close_session(session.session_id)

    def handle_grammar_download_error(
        self,
        language: str,
        error_message: str,
        url: str | None = None,
    ) -> dict[str, Any]:
        """Handle grammar download errors for CLI commands.

        Args:
            language: Programming language
            error_message: Error message from download attempt
            url: Optional download URL

        Returns:
            Dictionary containing error analysis and guidance
        """
        context = {
            "language": language,
            "source": "cli_grammar_download",
            "url": url,
            "cli_context": True,
        }

        session = self.orchestrator.create_session(context=context)

        try:
            result = self.orchestrator.process_error_in_session(
                session.session_id,
                error_message,
                context,
            )

            cli_response = {
                "success": result.success,
                "error_category": (
                    result.classified_error.category.value
                    if result.classified_error
                    else "network"
                ),
                "network_accessible": self._check_network_guidance(result),
                "alternative_sources": self._get_alternative_sources(language),
                "guidance": self._format_guidance_for_cli(result.guidance_sequence),
                "troubleshooting_steps": self._get_download_troubleshooting_steps(
                    result,
                ),
            }

            return cli_response

        finally:
            self.orchestrator.close_session(session.session_id)

    def _format_guidance_for_cli(
        self,
        guidance_sequence: GuidanceSequence | None,
    ) -> list[dict[str, Any]]:
        """Format guidance sequence for CLI display."""
        if not guidance_sequence:
            return []

        cli_guidance = []
        for action in guidance_sequence.actions:
            cli_action = {
                "title": action.title,
                "description": action.description,
                "command": action.command,
                "priority": (
                    action.priority.value
                    if hasattr(action.priority, "value")
                    else str(action.priority)
                ),
                "estimated_time": action.estimated_time,
            }
            cli_guidance.append(cli_action)

        return cli_guidance

    def _format_troubleshooting_for_cli(
        self,
        entries: list[TroubleshootingEntry],
    ) -> list[dict[str, Any]]:
        """Format troubleshooting entries for CLI display."""
        cli_troubleshooting = []

        for entry in entries[:3]:  # Limit to top 3 entries
            cli_entry = {
                "title": entry.title,
                "description": entry.description,
                "solutions": [],
            }

            # Add best solution
            best_solution = entry.get_best_solution()
            if best_solution:
                cli_entry["solutions"].append(
                    {
                        "title": best_solution.title,
                        "steps": best_solution.steps,
                        "difficulty": best_solution.difficulty_level,
                        "estimated_time": best_solution.estimated_time,
                    },
                )

            cli_troubleshooting.append(cli_entry)

        return cli_troubleshooting

    def _extract_quick_fixes(self, result: PipelineResult) -> list[str]:
        """Extract quick fix commands from pipeline result."""
        quick_fixes = []

        # From guidance sequence
        if result.guidance_sequence:
            for action in result.guidance_sequence.actions:
                if (
                    hasattr(action, "priority")
                    and hasattr(action.priority, "value")
                    and action.priority.value == "critical"
                    and action.command
                ):
                    quick_fixes.append(action.command)

        # From troubleshooting entries
        for entry in result.troubleshooting_entries:
            for solution in entry.solutions:
                if (
                    hasattr(solution, "solution_type")
                    and hasattr(solution.solution_type, "value")
                    and solution.solution_type.value == "quick_fix"
                    and solution.steps
                ):
                    quick_fixes.extend(solution.steps[:2])  # First 2 steps only

        return quick_fixes[:5]  # Limit to 5 quick fixes

    def _extract_cli_commands(self, result: PipelineResult) -> list[str]:
        """Extract CLI commands from pipeline result."""
        commands = []

        # Look for commands in guidance
        if result.guidance_sequence:
            for action in result.guidance_sequence.actions:
                if action.command and "treesitter-chunker" in action.command:
                    commands.append(action.command)

        # Add general helpful commands
        if result.classified_error and result.classified_error.context:
            language = result.classified_error.context.language
            if language:
                commands.append(f"treesitter-chunker download-grammar {language}")
                commands.append(
                    f"treesitter-chunker list-grammars --language {language}",
                )

        return commands[:3]  # Limit to 3 commands

    def _check_network_guidance(self, result: PipelineResult) -> bool:
        """Check if result contains network-related guidance."""
        if result.guidance_sequence:
            for action in result.guidance_sequence.actions:
                if any(
                    keyword in action.description.lower()
                    for keyword in ["network", "internet", "connection", "download"]
                ):
                    return True
        return False

    def _get_alternative_sources(self, language: str) -> list[dict[str, str]]:
        """Get alternative grammar sources for a language."""
        alternatives = [
            {
                "source": "GitHub Releases",
                "url": f"https://github.com/tree-sitter/tree-sitter-{language}/releases",
                "type": "official",
            },
            {
                "source": "NPM Registry",
                "url": f"https://www.npmjs.com/package/tree-sitter-{language}",
                "type": "package_manager",
            },
        ]

        return alternatives

    def _get_download_troubleshooting_steps(self, result: PipelineResult) -> list[str]:
        """Get download-specific troubleshooting steps."""
        steps = [
            "Check internet connectivity",
            "Verify proxy settings if behind a corporate firewall",
            "Try downloading manually from GitHub releases",
            "Check available disk space",
            "Ensure you have proper permissions to write to the grammar directory",
        ]

        # Add result-specific steps
        if result.fallback_response:
            general_guidance = result.fallback_response.get("general_guidance", [])
            steps.extend(general_guidance[:3])

        return steps[:7]  # Limit to 7 steps


# Factory Functions


def create_error_handling_system(
    max_concurrent_processes: int = 4,
    max_sessions: int = 100,
    session_timeout_minutes: int = 30,
    enable_troubleshooting_db: bool = True,
    troubleshooting_db_path: Path | None = None,
) -> tuple[ErrorHandlingPipeline, ErrorHandlingOrchestrator, CLIErrorIntegration]:
    """Create a complete error handling system with all components.

    Args:
        max_concurrent_processes: Maximum concurrent pipeline processes
        max_sessions: Maximum number of concurrent sessions
        session_timeout_minutes: Session timeout in minutes
        enable_troubleshooting_db: Whether to enable troubleshooting database
        troubleshooting_db_path: Optional path for troubleshooting database

    Returns:
        Tuple of (pipeline, orchestrator, cli_integration)
    """
    try:
        # Initialize components with graceful fallback
        error_classifier = None
        if ErrorClassifier:
            try:
                error_classifier = ErrorClassifier()
                logger.info("Initialized ErrorClassifier")
            except Exception as e:
                logger.warning(f"Failed to initialize ErrorClassifier: {e}")

        compatibility_detector = None
        if CompatibilityErrorDetector:
            try:
                # Import and initialize CompatibilityDatabase
                from ..languages.compatibility.database import CompatibilityDatabase

                compat_db = CompatibilityDatabase()
                compatibility_detector = CompatibilityErrorDetector(compat_db)
                logger.info("Initialized CompatibilityErrorDetector")
            except Exception as e:
                logger.warning(f"Failed to initialize CompatibilityErrorDetector: {e}")

        syntax_analyzer = None
        if SyntaxErrorAnalyzer:
            try:
                syntax_analyzer = SyntaxErrorAnalyzer()
                logger.info("Initialized SyntaxErrorAnalyzer")
            except Exception as e:
                logger.warning(f"Failed to initialize SyntaxErrorAnalyzer: {e}")

        template_manager = None
        if create_template_system:
            try:
                library, _renderer, _validator = create_template_system()
                template_manager = library.manager
                logger.info("Initialized TemplateManager")
            except Exception as e:
                logger.warning(f"Failed to initialize TemplateManager: {e}")

        guidance_engine = None
        if UserActionGuidanceEngine:
            try:
                guidance_engine = UserActionGuidanceEngine(
                    template_manager,
                    compatibility_detector,
                    syntax_analyzer,
                )
                logger.info("Initialized UserActionGuidanceEngine")
            except Exception as e:
                logger.warning(f"Failed to initialize UserActionGuidanceEngine: {e}")

        troubleshooting_db = None
        if enable_troubleshooting_db and TroubleshootingDatabase:
            try:
                troubleshooting_db = TroubleshootingDatabase(troubleshooting_db_path)
                logger.info("Initialized TroubleshootingDatabase")
            except Exception as e:
                logger.warning(f"Failed to initialize TroubleshootingDatabase: {e}")

        # Create pipeline
        pipeline = ErrorHandlingPipeline(
            error_classifier=error_classifier,
            compatibility_detector=compatibility_detector,
            syntax_analyzer=syntax_analyzer,
            template_manager=template_manager,
            guidance_engine=guidance_engine,
            troubleshooting_db=troubleshooting_db,
            max_concurrent_processes=max_concurrent_processes,
        )

        # Create orchestrator
        orchestrator = ErrorHandlingOrchestrator(
            pipeline=pipeline,
            max_sessions=max_sessions,
            session_timeout_minutes=session_timeout_minutes,
        )

        # Create CLI integration
        cli_integration = CLIErrorIntegration(orchestrator)

        logger.info("Created complete error handling system")
        return pipeline, orchestrator, cli_integration

    except Exception as e:
        logger.error(f"Failed to create error handling system: {e}")
        raise RuntimeError(f"Error handling system creation failed: {e}") from e


def get_system_health_report(
    pipeline: ErrorHandlingPipeline,
    orchestrator: ErrorHandlingOrchestrator,
) -> dict[str, Any]:
    """Get comprehensive system health report.

    Args:
        pipeline: Error handling pipeline
        orchestrator: Error handling orchestrator

    Returns:
        Dictionary containing comprehensive health report
    """
    try:
        pipeline_health = pipeline.get_pipeline_health()
        session_stats = orchestrator.get_session_statistics()

        # Calculate overall system health
        pipeline_score = (
            100
            if pipeline_health["status"] == "healthy"
            else 60 if pipeline_health["status"] == "degraded" else 20
        )
        session_score = min(
            100,
            (session_stats["active_sessions"] / session_stats["max_sessions"]) * 100,
        )

        overall_score = (pipeline_score + session_score) / 2

        health_report = {
            "overall_health": {
                "score": overall_score,
                "status": (
                    "healthy"
                    if overall_score >= 80
                    else "degraded" if overall_score >= 50 else "unhealthy"
                ),
                "timestamp": datetime.now(UTC).isoformat(),
            },
            "pipeline_health": pipeline_health,
            "session_management": session_stats,
            "recommendations": [],
        }

        # Add system-level recommendations
        if overall_score < 80:
            health_report["recommendations"].append(
                "Monitor system performance and consider scaling",
            )

        if (
            pipeline_health["components"]["available"]
            < pipeline_health["components"]["total"]
        ):
            health_report["recommendations"].append(
                "Initialize missing pipeline components",
            )

        if session_stats["active_sessions"] > session_stats["max_sessions"] * 0.8:
            health_report["recommendations"].append(
                "Consider increasing maximum session limit",
            )

        return health_report

    except Exception as e:
        logger.error(f"Failed to generate health report: {e}")
        return {
            "overall_health": {
                "score": 0,
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now(UTC).isoformat(),
            },
        }

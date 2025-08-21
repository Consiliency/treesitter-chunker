"""Error handling and user guidance system for Phase 1.7.

This package provides intelligent error handling that detects language version 
compatibility issues and provides clear user guidance for the treesitter-chunker.

Components:
- Error Classification: Categorizes and analyzes errors by type and severity
- Compatibility Detection: Identifies language version compatibility issues
- Syntax Analysis: Analyzes syntax errors and provides context
- User Guidance: Generates actionable steps for resolving errors
- Integration: Connects all components into the main chunking pipeline

The system is designed to work seamlessly with the existing chunker while
providing enhanced error reporting and user guidance capabilities.
"""

# Version information
__version__ = "1.0.0"
__author__ = "treesitter-chunker team"

# All Group D components are now implemented

# Error classification system (Task C1)
from .classifier import (
    ClassifiedError,
    ErrorCategory,
    ErrorClassifier,
    ErrorConfidenceScorer,
    ErrorContext,
    ErrorPatternMatcher,
    ErrorSeverity,
    ErrorSource,
)

# Compatibility error detection (Task C2)
from .compatibility_detector import (
    CompatibilityErrorDetector,
    CompatibilityErrorFormatter,
    VersionCompatibilityAnalyzer,
)

# User action guidance (Task D2)
from .guidance_engine import (
    GuidanceAction,
    GuidancePersonalizer,
    GuidanceQualityAssessor,
    GuidanceSequence,
    GuidanceType,
    UserActionGuidanceEngine,
)

# Integration pipeline (Task E1)
from .integration import (
    CLIErrorIntegration,
    ErrorHandlingOrchestrator,
    ErrorHandlingPipeline,
    PipelineMetrics,
    PipelineResult,
    PipelineStage,
)

# Syntax error analysis (Task C3)
from .syntax_analyzer import (
    LanguageSpecificSyntaxAnalyzer,
    SyntaxErrorAnalyzer,
    SyntaxErrorFormatter,
    SyntaxErrorPatternMatcher,
)

# Error message templates (Task D1)
from .templates import (
    ErrorTemplate,
    TemplateFormat,
    TemplateLibrary,
    TemplateManager,
    TemplateRenderer,
    TemplateType,
    TemplateValidator,
    create_template_system,
    render_template,
    validate_template_string,
)

# Troubleshooting database (Task D3)
from .troubleshooting import (
    Solution,
    SolutionType,
    TroubleshootingAnalytics,
    TroubleshootingCategory,
    TroubleshootingDatabase,
    TroubleshootingEntry,
    TroubleshootingSearchEngine,
    create_sample_troubleshooting_data,
    initialize_troubleshooting_system,
)

# Define public API
__all__ = [
    "CLIErrorIntegration",
    "ClassifiedError",
    # Compatibility error detection (Task C2)
    "CompatibilityErrorDetector",
    "CompatibilityErrorFormatter",
    "ErrorCategory",
    "ErrorClassifier",
    "ErrorConfidenceScorer",
    "ErrorContext",
    "ErrorHandlingOrchestrator",
    # Integration pipeline (Task E1)
    "ErrorHandlingPipeline",
    "ErrorPatternMatcher",
    # Error classification system (Task C1)
    "ErrorSeverity",
    "ErrorSource",
    "ErrorTemplate",
    "GuidanceAction",
    "GuidancePersonalizer",
    "GuidanceQualityAssessor",
    "GuidanceSequence",
    "GuidanceType",
    "LanguageSpecificSyntaxAnalyzer",
    "PipelineMetrics",
    "PipelineResult",
    "PipelineStage",
    "Solution",
    "SolutionType",
    # Syntax error analysis (Task C3)
    "SyntaxErrorAnalyzer",
    "SyntaxErrorFormatter",
    "SyntaxErrorPatternMatcher",
    "TemplateFormat",
    "TemplateLibrary",
    "TemplateManager",
    "TemplateRenderer",
    # Error message templates (Task D1)
    "TemplateType",
    "TemplateValidator",
    "TroubleshootingAnalytics",
    # Troubleshooting database (Task D3)
    "TroubleshootingCategory",
    "TroubleshootingDatabase",
    "TroubleshootingEntry",
    "TroubleshootingSearchEngine",
    # User action guidance (Task D2)
    "UserActionGuidanceEngine",
    "VersionCompatibilityAnalyzer",
    "create_sample_troubleshooting_data",
    "create_template_system",
    "initialize_troubleshooting_system",
    "render_template",
    "validate_template_string",
]

# Package metadata
__all__.extend(["__author__", "__version__"])

# Logging setup for the error handling system
import logging

# Create logger for the error handling package
logger = logging.getLogger(__name__)

# Set up basic logging if not already configured
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

logger.debug(
    "Error handling package initialized - All Group C and D components implemented",
)

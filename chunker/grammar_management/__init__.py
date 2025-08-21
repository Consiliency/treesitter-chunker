"""Grammar management infrastructure for treesitter-chunker.

This module provides comprehensive grammar management capabilities with
Phase 1.8 specification compliance and Task E1 error handling integration.

Key Components:
- ComprehensiveGrammarCLI: Main CLI interface with all required commands
- Grammar selection priority: User → Package → Fallback
- Error handling integration with Phase 1.7 components
- Progress indicators and user guidance
- Comprehensive validation and testing

Phase 1.8 Compliance:
- ~/.cache/treesitter-chunker/grammars/ directory structure
- All specified CLI commands: list, info, versions, fetch, build, remove, test, validate
- Grammar priority selection order
- Error handling for all failure scenarios

Integration Features:
- ErrorHandlingPipeline integration for comprehensive error processing
- CLIErrorIntegration for grammar-specific error handling
- User guidance and troubleshooting suggestions
- Graceful degradation when components are unavailable
"""

from .cli import ComprehensiveGrammarCLI, ProgressIndicator, grammar_cli
from .core import (
    GrammarInstallationError,
    GrammarInstaller,
    GrammarManagementError,
    GrammarManager,
    GrammarPriority,
    GrammarRegistry,
    GrammarRegistryError,
    GrammarValidationError,
    GrammarValidator,
    InstallationInfo,
    ValidationLevel,
    ValidationResult,
)

# Re-export GrammarStatus from interfaces for compatibility
try:
    from chunker.interfaces.grammar import GrammarStatus
except ImportError:
    # Fallback definition if interfaces not available
    from enum import Enum

    class GrammarStatus(Enum):
        NOT_FOUND = "not_found"
        NOT_BUILT = "not_built"
        BUILDING = "building"
        READY = "ready"
        ERROR = "error"
        OUTDATED = "outdated"


__all__ = [
    # CLI components
    "ComprehensiveGrammarCLI",
    "GrammarInstallationError",
    "GrammarInstaller",
    # Exceptions
    "GrammarManagementError",
    # Core components
    "GrammarManager",
    # Enums and data classes
    "GrammarPriority",
    "GrammarRegistry",
    "GrammarRegistryError",
    "GrammarStatus",
    "GrammarValidationError",
    "GrammarValidator",
    "InstallationInfo",
    "ProgressIndicator",
    "ValidationLevel",
    "ValidationResult",
    "grammar_cli",
]

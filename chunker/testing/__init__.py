"""Testing package for Phase 1.7: Smart Error Handling & User Guidance.

This package provides comprehensive testing capabilities for all Phase 1.7 components:
- Integration testing framework
- End-to-end workflow testing
- Performance and scalability testing
- Cross-group integration validation
"""

# Version information
__version__ = "1.0.0"
__author__ = "treesitter-chunker team"

# Import testing framework
try:
    from .integration_framework import (
        IntegrationTestFramework,
        IntegrationTestResult,
        IntegrationTestSuite,
        run_integration_tests,
    )

    __all__ = [
        "IntegrationTestFramework",
        "IntegrationTestResult",
        "IntegrationTestSuite",
        "run_integration_tests",
    ]
except ImportError:
    # Framework not yet fully implemented
    __all__ = []

# Package metadata
__all__.extend(["__author__", "__version__"])

# Logging setup
import logging

logger = logging.getLogger(__name__)

if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

logger.debug("Testing package initialized")

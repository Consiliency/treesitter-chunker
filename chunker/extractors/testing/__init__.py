"""
Testing module for Phase 2 call site extractors.

This module provides comprehensive integration testing for all language extractors,
including accuracy validation, performance benchmarking, error handling verification,
and cross-language consistency checks.
"""

from .integration_tester import (
    ExtractorTestSuite,
    IntegrationTester,
    TestResult,
    run_complete_extractor_test_suite,
)

__all__ = [
    "ExtractorTestSuite",
    "IntegrationTester",
    "TestResult",
    "run_complete_extractor_test_suite",
]

# Version information
__version__ = "1.0.0"
__author__ = "Phase 2 Integration Team"
__description__ = "Comprehensive testing framework for language extractors"

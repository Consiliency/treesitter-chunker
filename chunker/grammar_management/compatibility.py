"""Grammar compatibility engine for treesitter-chunker.

This module provides comprehensive grammar compatibility checking, testing, and smart
selection functionality for Phase 1.8 Task 1.8.4. Implements compatibility matrix
generation, breaking change detection, performance benchmarking, and database persistence.

Key Components:
- CompatibilityChecker: Grammar-language version compatibility validation
- GrammarTester: Grammar functionality and performance testing
- SmartSelector: Intelligent grammar selection with conflict resolution
- CompatibilityDatabase: Persistent compatibility data storage

Features:
- Grammar-language version compatibility matrix
- Breaking change detection across grammar versions
- Performance benchmarking and profiling
- Error pattern analysis and reporting
- Smart grammar selection with priority scoring
- SQLite persistence for compatibility data
- Upgrade recommendation system
"""

from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import statistics
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from chunker.grammar_management.core import (
    GrammarManager,
    GrammarPriority,
    GrammarValidator,
    ValidationLevel,
    ValidationResult,
)
from chunker.interfaces.grammar import GrammarInfo, GrammarStatus

logger = logging.getLogger(__name__)


class CompatibilityLevel(Enum):
    """Grammar compatibility level indicators."""

    PERFECT = "perfect"  # Full compatibility, no issues
    COMPATIBLE = "compatible"  # Compatible with minor warnings
    DEGRADED = "degraded"  # Compatible with performance issues
    LIMITED = "limited"  # Limited compatibility, some features broken
    INCOMPATIBLE = "incompatible"  # Not compatible, major issues
    UNKNOWN = "unknown"  # Compatibility not yet determined


class BreakingChangeType(Enum):
    """Types of breaking changes between grammar versions."""

    NODE_TYPE_REMOVED = "node_type_removed"
    NODE_TYPE_RENAMED = "node_type_renamed"
    FIELD_REMOVED = "field_removed"
    FIELD_RENAMED = "field_renamed"
    STRUCTURE_CHANGED = "structure_changed"
    ABI_INCOMPATIBLE = "abi_incompatible"
    PERFORMANCE_DEGRADED = "performance_degraded"


class SelectionCriterion(Enum):
    """Criteria for smart grammar selection."""

    COMPATIBILITY = "compatibility"
    PERFORMANCE = "performance"
    RELIABILITY = "reliability"
    FEATURES = "features"
    RECENCY = "recency"
    COMMUNITY = "community"


@dataclass
class CompatibilityResult:
    """Result of compatibility checking."""

    language: str
    grammar_version: str
    language_version: str | None
    level: CompatibilityLevel
    score: float = 0.0
    issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    breaking_changes: list[dict[str, Any]] = field(default_factory=list)
    performance_impact: dict[str, float] | None = None
    test_results: dict[str, Any] | None = None
    timestamp: float = field(default_factory=time.time)


@dataclass
class TestResult:
    """Result of grammar testing."""

    language: str
    grammar_version: str
    test_type: str
    success: bool
    duration: float
    memory_usage: float | None = None
    error_message: str | None = None
    sample_results: list[dict[str, Any]] = field(default_factory=list)
    performance_metrics: dict[str, float] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


@dataclass
class SelectionCandidate:
    """Grammar candidate for smart selection."""

    language: str
    version: str
    grammar_path: Path
    priority: GrammarPriority
    compatibility_score: float = 0.0
    performance_score: float = 0.0
    reliability_score: float = 0.0
    feature_score: float = 0.0
    recency_score: float = 0.0
    overall_score: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


class CompatibilityChecker:
    """Checks grammar compatibility with language versions and detects breaking changes."""

    def __init__(
        self,
        grammar_manager: GrammarManager,
        database: CompatibilityDatabase | None = None,
    ):
        """Initialize compatibility checker.

        Args:
            grammar_manager: Grammar manager instance
            database: Compatibility database instance
        """
        self.grammar_manager = grammar_manager
        self.database = database
        self.validator = GrammarValidator()

        # Language version patterns for detection
        self.version_patterns = {
            "python": [
                r"python\s*(\d+\.\d+(?:\.\d+)?)",
                r"#!/usr/bin/env python(\d+)",
                r"# -\*- python-version: (\d+\.\d+) -\*-",
            ],
            "javascript": [
                r'"version":\s*"(\d+\.\d+(?:\.\d+)?)"',
                r"node\s+v?(\d+\.\d+(?:\.\d+)?)",
                r"// @ts-version (\d+\.\d+)",
            ],
            "java": [
                r"sourceCompatibility\s*=\s*['\"](\d+(?:\.\d+)?)['\"]",
                r"<maven.compiler.source>(\d+)</maven.compiler.source>",
                r"// Java (\d+)",
            ],
        }

    def check_compatibility(
        self,
        language: str,
        grammar_version: str | None = None,
        language_version: str | None = None,
        code_samples: list[str] | None = None,
    ) -> CompatibilityResult:
        """Check grammar compatibility comprehensively.

        Args:
            language: Target language name
            grammar_version: Grammar version to check
            language_version: Language version to check against
            code_samples: Sample code for testing

        Returns:
            Comprehensive compatibility result
        """
        try:
            logger.info(f"Checking compatibility for {language}")

            # Get grammar information
            grammar_info = self.grammar_manager.get_grammar_metadata(language)
            if not grammar_info:
                return CompatibilityResult(
                    language=language,
                    grammar_version="unknown",
                    language_version=language_version,
                    level=CompatibilityLevel.INCOMPATIBLE,
                    issues=[f"Grammar not found for {language}"],
                )

            grammar_version = grammar_version or grammar_info.get("version", "unknown")

            # Check cache first
            if self.database:
                cached_result = self.database.get_compatibility_result(
                    language,
                    grammar_version,
                    language_version,
                )
                if cached_result and self._is_cache_valid(cached_result):
                    return cached_result

            # Perform compatibility checks
            result = CompatibilityResult(
                language=language,
                grammar_version=grammar_version,
                language_version=language_version,
                level=CompatibilityLevel.UNKNOWN,
            )

            # Basic validation check
            validation_result = self.grammar_manager.validate_grammar(
                language,
                ValidationLevel.STANDARD,
            )

            if not validation_result.is_valid:
                result.level = CompatibilityLevel.INCOMPATIBLE
                result.issues.extend(validation_result.errors)
                result.warnings.extend(validation_result.warnings)
                result.score = 0.0
            else:
                # Perform detailed compatibility analysis
                result = self._perform_detailed_compatibility_check(
                    result,
                    grammar_info,
                    code_samples or [],
                )

            # Store result in database
            if self.database:
                self.database.store_compatibility_result(result)

            return result

        except Exception as e:
            logger.error(f"Compatibility check failed for {language}: {e}")
            return CompatibilityResult(
                language=language,
                grammar_version=grammar_version or "unknown",
                language_version=language_version,
                level=CompatibilityLevel.UNKNOWN,
                issues=[f"Compatibility check error: {e!s}"],
            )

    def generate_compatibility_matrix(
        self,
        languages: list[str] | None = None,
    ) -> dict[str, dict[str, CompatibilityResult]]:
        """Generate comprehensive compatibility matrix.

        Args:
            languages: Languages to check (None for all available)

        Returns:
            Matrix mapping language -> version -> compatibility result
        """
        try:
            if languages is None:
                languages = list(self.grammar_manager.list_installed_grammars().keys())

            matrix = {}

            for language in languages:
                logger.info(f"Generating compatibility matrix for {language}")

                matrix[language] = {}

                # Get available versions for this language
                versions = self._get_available_versions(language)

                for version in versions:
                    try:
                        result = self.check_compatibility(language, version)
                        matrix[language][version] = result
                    except Exception as e:
                        logger.error(f"Failed to check {language} v{version}: {e}")
                        matrix[language][version] = CompatibilityResult(
                            language=language,
                            grammar_version=version,
                            language_version=None,
                            level=CompatibilityLevel.UNKNOWN,
                            issues=[str(e)],
                        )

            return matrix

        except Exception as e:
            logger.error(f"Failed to generate compatibility matrix: {e}")
            return {}

    def detect_breaking_changes(
        self,
        language: str,
        old_version: str,
        new_version: str,
    ) -> list[dict[str, Any]]:
        """Detect breaking changes between grammar versions.

        Args:
            language: Language name
            old_version: Previous grammar version
            new_version: New grammar version

        Returns:
            List of detected breaking changes
        """
        try:
            logger.info(
                f"Detecting breaking changes for {language}: {old_version} -> {new_version}",
            )

            breaking_changes = []

            # Get compatibility results for both versions
            old_result = self.check_compatibility(language, old_version)
            new_result = self.check_compatibility(language, new_version)

            # Compare compatibility levels
            if (
                old_result.level != CompatibilityLevel.INCOMPATIBLE
                and new_result.level == CompatibilityLevel.INCOMPATIBLE
            ):
                breaking_changes.append(
                    {
                        "type": BreakingChangeType.ABI_INCOMPATIBLE.value,
                        "description": f"Grammar became incompatible in version {new_version}",
                        "impact": "high",
                        "issues": new_result.issues,
                    },
                )

            # Compare performance impact
            if old_result.performance_impact and new_result.performance_impact:
                old_performance = old_result.performance_impact.get(
                    "average_parse_time",
                    0,
                )
                new_performance = new_result.performance_impact.get(
                    "average_parse_time",
                    0,
                )

                if new_performance > old_performance * 1.5:  # 50% slower
                    breaking_changes.append(
                        {
                            "type": BreakingChangeType.PERFORMANCE_DEGRADED.value,
                            "description": f"Performance degraded by {((new_performance / old_performance - 1) * 100):.1f}%",
                            "impact": "medium",
                            "old_time": old_performance,
                            "new_time": new_performance,
                        },
                    )

            # Analyze test result differences
            breaking_changes.extend(self._compare_test_results(old_result, new_result))

            return breaking_changes

        except Exception as e:
            logger.error(f"Failed to detect breaking changes: {e}")
            return [
                {
                    "type": "analysis_error",
                    "description": f"Failed to analyze changes: {e!s}",
                    "impact": "unknown",
                },
            ]

    def suggest_grammar_version(
        self,
        language: str,
        language_version: str | None = None,
        requirements: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Suggest best grammar version based on compatibility and requirements.

        Args:
            language: Target language
            language_version: Target language version
            requirements: Specific requirements (performance, features, etc.)

        Returns:
            Suggestion with version and reasoning
        """
        try:
            logger.info(f"Suggesting grammar version for {language}")

            # Get all available versions
            versions = self._get_available_versions(language)
            if not versions:
                return None

            # Score each version
            version_scores = {}

            for version in versions:
                try:
                    result = self.check_compatibility(
                        language,
                        version,
                        language_version,
                    )

                    # Base score from compatibility
                    score = self._calculate_compatibility_score(result)

                    # Apply requirement weights
                    if requirements:
                        score = self._apply_requirement_weights(
                            score,
                            result,
                            requirements,
                        )

                    version_scores[version] = {"score": score, "result": result}

                except Exception as e:
                    logger.warning(f"Failed to score version {version}: {e}")
                    continue

            if not version_scores:
                return None

            # Find best version
            best_version = max(
                version_scores.keys(),
                key=lambda v: version_scores[v]["score"],
            )
            best_result = version_scores[best_version]["result"]

            return {
                "recommended_version": best_version,
                "score": version_scores[best_version]["score"],
                "compatibility_level": best_result.level.value,
                "reasoning": self._generate_recommendation_reasoning(
                    best_result,
                    version_scores,
                    requirements,
                ),
                "alternatives": sorted(
                    [
                        {
                            "version": v,
                            "score": data["score"],
                            "level": data["result"].level.value,
                        }
                        for v, data in version_scores.items()
                        if v != best_version
                    ],
                    key=lambda x: x["score"],
                    reverse=True,
                )[
                    :3
                ],  # Top 3 alternatives
            }

        except Exception as e:
            logger.error(f"Failed to suggest grammar version: {e}")
            return None

    def _perform_detailed_compatibility_check(
        self,
        result: CompatibilityResult,
        grammar_info: dict[str, Any],
        code_samples: list[str],
    ) -> CompatibilityResult:
        """Perform detailed compatibility analysis."""
        try:
            # Start with basic compatibility
            result.level = CompatibilityLevel.COMPATIBLE
            result.score = 1.0

            # Check ABI compatibility
            validation_info = grammar_info.get("validation", {})
            if validation_info.get("errors"):
                result.level = CompatibilityLevel.INCOMPATIBLE
                result.score = 0.0
                result.issues.extend(validation_info["errors"])
            elif validation_info.get("warnings"):
                result.level = CompatibilityLevel.DEGRADED
                result.score = 0.7
                result.warnings.extend(validation_info["warnings"])

            # Performance analysis
            performance_metrics = grammar_info.get("performance", {})
            if performance_metrics:
                result.performance_impact = self._analyze_performance_impact(
                    performance_metrics,
                )

                # Adjust score based on performance
                avg_parse_time = performance_metrics.get("parse_time", 0)
                if avg_parse_time > 2.0:  # Slow parsing
                    result.score *= 0.8
                    result.warnings.append(
                        f"Slow parsing detected: {avg_parse_time:.2f}s average",
                    )
                elif avg_parse_time > 5.0:  # Very slow
                    result.level = CompatibilityLevel.DEGRADED
                    result.score *= 0.5

            # Test with code samples if provided
            if code_samples:
                test_results = self._test_code_samples(result.language, code_samples)
                result.test_results = test_results

                # Adjust compatibility based on test results
                success_rate = test_results.get("success_rate", 0.0)
                if success_rate < 0.5:
                    result.level = CompatibilityLevel.INCOMPATIBLE
                    result.score *= success_rate
                elif success_rate < 0.8:
                    result.level = CompatibilityLevel.LIMITED
                    result.score *= success_rate

            return result

        except Exception as e:
            logger.error(f"Detailed compatibility check failed: {e}")
            result.issues.append(f"Analysis error: {e!s}")
            result.level = CompatibilityLevel.UNKNOWN
            result.score = 0.0
            return result

    def _get_available_versions(self, language: str) -> list[str]:
        """Get available versions for a language."""
        try:
            # This would be implemented to discover available versions
            # For now, return a basic version list
            grammar_info = self.grammar_manager.get_grammar_metadata(language)
            if grammar_info and "version" in grammar_info:
                return [grammar_info["version"]]
            return ["latest"]
        except Exception:
            return ["latest"]

    def _test_code_samples(self, language: str, samples: list[str]) -> dict[str, Any]:
        """Test grammar with code samples."""
        try:
            success_count = 0
            total_samples = len(samples)
            sample_results = []

            for i, sample in enumerate(samples):
                try:
                    # Use validator's test method
                    success, errors = self.validator.test_parse_samples(
                        language,
                        [sample],
                    )

                    sample_result = {
                        "index": i,
                        "success": success,
                        "errors": errors if not success else [],
                    }
                    sample_results.append(sample_result)

                    if success:
                        success_count += 1

                except Exception as e:
                    sample_results.append(
                        {"index": i, "success": False, "errors": [str(e)]},
                    )

            return {
                "success_rate": (
                    success_count / total_samples if total_samples > 0 else 0.0
                ),
                "successful_samples": success_count,
                "total_samples": total_samples,
                "sample_results": sample_results,
            }

        except Exception as e:
            return {"success_rate": 0.0, "error": str(e)}

    def _analyze_performance_impact(self, metrics: dict[str, Any]) -> dict[str, float]:
        """Analyze performance impact from metrics."""
        impact = {}

        if "parse_time" in metrics:
            parse_time = metrics["parse_time"]
            impact["average_parse_time"] = parse_time

            # Classify performance impact
            if parse_time < 0.1:
                impact["impact_level"] = 0.0  # No impact
            elif parse_time < 0.5:
                impact["impact_level"] = 0.2  # Low impact
            elif parse_time < 2.0:
                impact["impact_level"] = 0.5  # Medium impact
            else:
                impact["impact_level"] = 0.8  # High impact

        if "memory_delta_mb" in metrics:
            memory_delta = metrics["memory_delta_mb"]
            impact["memory_impact"] = memory_delta

        return impact

    def _compare_test_results(
        self,
        old_result: CompatibilityResult,
        new_result: CompatibilityResult,
    ) -> list[dict[str, Any]]:
        """Compare test results to find breaking changes."""
        changes = []

        old_tests = old_result.test_results or {}
        new_tests = new_result.test_results or {}

        old_success_rate = old_tests.get("success_rate", 1.0)
        new_success_rate = new_tests.get("success_rate", 1.0)

        if old_success_rate > 0.8 and new_success_rate < 0.5:
            changes.append(
                {
                    "type": BreakingChangeType.STRUCTURE_CHANGED.value,
                    "description": f"Test success rate dropped from {old_success_rate:.1%} to {new_success_rate:.1%}",
                    "impact": "high",
                },
            )

        return changes

    def _calculate_compatibility_score(self, result: CompatibilityResult) -> float:
        """Calculate overall compatibility score."""
        base_scores = {
            CompatibilityLevel.PERFECT: 1.0,
            CompatibilityLevel.COMPATIBLE: 0.9,
            CompatibilityLevel.DEGRADED: 0.7,
            CompatibilityLevel.LIMITED: 0.5,
            CompatibilityLevel.INCOMPATIBLE: 0.0,
            CompatibilityLevel.UNKNOWN: 0.3,
        }

        base_score = base_scores.get(result.level, 0.0)

        # Apply test results if available
        if result.test_results:
            success_rate = result.test_results.get("success_rate", 1.0)
            base_score *= success_rate

        # Apply performance penalty
        if result.performance_impact:
            impact_level = result.performance_impact.get("impact_level", 0.0)
            base_score *= 1.0 - impact_level * 0.3  # Up to 30% penalty

        return max(0.0, min(1.0, base_score))

    def _apply_requirement_weights(
        self,
        base_score: float,
        result: CompatibilityResult,
        requirements: dict[str, Any],
    ) -> float:
        """Apply requirement-specific weights to score."""
        weighted_score = base_score

        # Performance requirements
        if requirements.get("performance_critical"):
            if result.performance_impact:
                impact = result.performance_impact.get("impact_level", 0.0)
                weighted_score *= 1.0 - impact

        # Reliability requirements
        if requirements.get("reliability_critical"):
            if result.test_results:
                success_rate = result.test_results.get("success_rate", 1.0)
                weighted_score *= success_rate

        return weighted_score

    def _generate_recommendation_reasoning(
        self,
        best_result: CompatibilityResult,
        all_scores: dict[str, dict[str, Any]],
        requirements: dict[str, Any] | None,
    ) -> list[str]:
        """Generate reasoning for recommendation."""
        reasoning = []

        reasoning.append(f"Compatibility level: {best_result.level.value}")
        reasoning.append(f"Overall score: {best_result.score:.2f}")

        if best_result.test_results:
            success_rate = best_result.test_results.get("success_rate", 0.0)
            reasoning.append(f"Test success rate: {success_rate:.1%}")

        if best_result.performance_impact:
            parse_time = best_result.performance_impact.get("average_parse_time", 0.0)
            if parse_time > 0:
                reasoning.append(f"Average parse time: {parse_time:.3f}s")

        if requirements:
            if requirements.get("performance_critical"):
                reasoning.append("Optimized for performance requirements")
            if requirements.get("reliability_critical"):
                reasoning.append("Selected for high reliability")

        return reasoning

    def _is_cache_valid(self, cached_result: CompatibilityResult) -> bool:
        """Check if cached result is still valid."""
        # Cache valid for 24 hours
        return time.time() - cached_result.timestamp < 86400


class GrammarTester:
    """Tests grammar functionality and performance with comprehensive benchmarking."""

    def __init__(self, grammar_manager: GrammarManager):
        """Initialize grammar tester.

        Args:
            grammar_manager: Grammar manager instance
        """
        self.grammar_manager = grammar_manager
        self.validator = GrammarValidator()

        # Built-in test suites
        self.test_suites = {
            "python": [
                "def hello(): pass",
                "class TestClass:\n    def method(self):\n        return 42",
                "import os\nfrom typing import List\n\ndef func(items: List[str]) -> str:\n    return ''.join(items)",
                "async def async_func():\n    await something()",
                "with open('file.txt') as f:\n    content = f.read()",
            ],
            "javascript": [
                "function hello() {}",
                "const obj = { key: 'value', method() { return this.key; } };",
                "class TestClass extends BaseClass {\n    constructor() {\n        super();\n    }\n}",
                "const asyncFunc = async () => {\n    const result = await fetch('/api');\n    return result.json();\n};",
                "export default { name: 'module', version: '1.0' };",
            ],
            "rust": [
                "fn main() {}",
                "struct Point { x: i32, y: i32 }",
                "impl Point {\n    fn new(x: i32, y: i32) -> Self {\n        Point { x, y }\n    }\n}",
                "enum Option<T> {\n    Some(T),\n    None,\n}",
                "fn generic_function<T: Clone>(item: T) -> T {\n    item.clone()\n}",
            ],
        }

    def run_comprehensive_test(
        self,
        language: str,
        test_types: list[str] | None = None,
    ) -> TestResult:
        """Run comprehensive grammar testing.

        Args:
            language: Language to test
            test_types: Types of tests to run (None for all)

        Returns:
            Comprehensive test result
        """
        try:
            logger.info(f"Running comprehensive tests for {language}")

            start_time = time.time()

            # Get grammar info
            grammar_info = self.grammar_manager.get_grammar_metadata(language)
            if not grammar_info:
                return TestResult(
                    language=language,
                    grammar_version="unknown",
                    test_type="comprehensive",
                    success=False,
                    duration=time.time() - start_time,
                    error_message=f"Grammar not found for {language}",
                )

            grammar_version = grammar_info.get("version", "unknown")

            # Initialize result
            result = TestResult(
                language=language,
                grammar_version=grammar_version,
                test_type="comprehensive",
                success=True,
                duration=0.0,
            )

            test_types = test_types or ["syntax", "performance", "memory", "stress"]

            # Run each test type
            for test_type in test_types:
                try:
                    if test_type == "syntax":
                        self._run_syntax_tests(result)
                    elif test_type == "performance":
                        self._run_performance_tests(result)
                    elif test_type == "memory":
                        self._run_memory_tests(result)
                    elif test_type == "stress":
                        self._run_stress_tests(result)
                except Exception as e:
                    result.success = False
                    result.error_message = f"Test {test_type} failed: {e!s}"
                    logger.error(f"Test {test_type} failed for {language}: {e}")

            result.duration = time.time() - start_time

            return result

        except Exception as e:
            logger.error(f"Comprehensive test failed for {language}: {e}")
            return TestResult(
                language=language,
                grammar_version="unknown",
                test_type="comprehensive",
                success=False,
                duration=time.time() - start_time,
                error_message=str(e),
            )

    def benchmark_parsing_performance(
        self,
        language: str,
        sample_sizes: list[int] | None = None,
    ) -> dict[str, Any]:
        """Benchmark parsing performance with various sample sizes.

        Args:
            language: Language to benchmark
            sample_sizes: Code sample sizes to test (lines)

        Returns:
            Performance benchmark results
        """
        try:
            logger.info(f"Benchmarking parsing performance for {language}")

            sample_sizes = sample_sizes or [10, 100, 1000, 5000]
            benchmark_results = {
                "language": language,
                "sample_sizes": sample_sizes,
                "results": [],
                "summary": {},
            }

            for size in sample_sizes:
                try:
                    # Generate test code of specified size
                    test_code = self._generate_test_code(language, size)

                    # Measure parsing performance
                    start_time = time.time()
                    start_memory = self._get_memory_usage()

                    success, errors = self.validator.test_parse_samples(
                        language,
                        [test_code],
                    )

                    end_time = time.time()
                    end_memory = self._get_memory_usage()

                    parse_time = end_time - start_time
                    memory_delta = (
                        end_memory - start_memory
                        if start_memory and end_memory
                        else None
                    )

                    result = {
                        "sample_size": size,
                        "parse_time": parse_time,
                        "memory_delta": memory_delta,
                        "success": success,
                        "errors": errors if not success else [],
                    }

                    benchmark_results["results"].append(result)

                except Exception as e:
                    logger.error(f"Benchmark failed for size {size}: {e}")
                    benchmark_results["results"].append(
                        {"sample_size": size, "error": str(e), "success": False},
                    )

            # Calculate summary statistics
            successful_results = [
                r for r in benchmark_results["results"] if r.get("success")
            ]

            if successful_results:
                parse_times = [r["parse_time"] for r in successful_results]

                benchmark_results["summary"] = {
                    "avg_parse_time": statistics.mean(parse_times),
                    "median_parse_time": statistics.median(parse_times),
                    "max_parse_time": max(parse_times),
                    "min_parse_time": min(parse_times),
                    "successful_tests": len(successful_results),
                    "total_tests": len(benchmark_results["results"]),
                }

            return benchmark_results

        except Exception as e:
            logger.error(f"Performance benchmark failed for {language}: {e}")
            return {"language": language, "error": str(e), "success": False}

    def analyze_error_patterns(
        self,
        language: str,
        code_samples: list[str],
    ) -> dict[str, Any]:
        """Analyze error patterns in parsing failures.

        Args:
            language: Language to analyze
            code_samples: Code samples to test

        Returns:
            Error pattern analysis results
        """
        try:
            logger.info(f"Analyzing error patterns for {language}")

            analysis = {
                "language": language,
                "total_samples": len(code_samples),
                "successful_parses": 0,
                "failed_parses": 0,
                "error_patterns": {},
                "common_errors": [],
                "failure_rate": 0.0,
            }

            error_counts = {}

            for i, sample in enumerate(code_samples):
                try:
                    success, errors = self.validator.test_parse_samples(
                        language,
                        [sample],
                    )

                    if success:
                        analysis["successful_parses"] += 1
                    else:
                        analysis["failed_parses"] += 1

                        # Categorize errors
                        for error in errors:
                            error_key = self._categorize_error(error)
                            error_counts[error_key] = error_counts.get(error_key, 0) + 1

                except Exception as e:
                    analysis["failed_parses"] += 1
                    error_key = f"exception: {type(e).__name__}"
                    error_counts[error_key] = error_counts.get(error_key, 0) + 1

            # Calculate failure rate
            analysis["failure_rate"] = (
                analysis["failed_parses"] / analysis["total_samples"]
                if analysis["total_samples"] > 0
                else 0.0
            )

            # Identify common error patterns
            analysis["error_patterns"] = error_counts
            analysis["common_errors"] = sorted(
                error_counts.items(),
                key=lambda x: x[1],
                reverse=True,
            )[
                :10
            ]  # Top 10 most common errors

            return analysis

        except Exception as e:
            logger.error(f"Error pattern analysis failed for {language}: {e}")
            return {"language": language, "error": str(e), "success": False}

    def _run_syntax_tests(self, result: TestResult):
        """Run syntax parsing tests."""
        test_samples = self.test_suites.get(result.language, [])

        if not test_samples:
            result.sample_results.append(
                {
                    "test_type": "syntax",
                    "warning": f"No built-in test samples for {result.language}",
                },
            )
            return

        start_time = time.time()

        success, errors = self.validator.test_parse_samples(
            result.language,
            test_samples,
        )

        syntax_result = {
            "test_type": "syntax",
            "success": success,
            "duration": time.time() - start_time,
            "samples_tested": len(test_samples),
            "errors": errors if not success else [],
        }

        result.sample_results.append(syntax_result)
        result.performance_metrics["syntax_test_time"] = syntax_result["duration"]

        if not success:
            result.success = False

    def _run_performance_tests(self, result: TestResult):
        """Run performance tests."""
        try:
            # Test with progressively larger samples
            test_sizes = [100, 500, 1000]
            performance_results = []

            for size in test_sizes:
                test_code = self._generate_test_code(result.language, size)

                start_time = time.time()
                success, _errors = self.validator.test_parse_samples(
                    result.language,
                    [test_code],
                )
                duration = time.time() - start_time

                performance_results.append(
                    {
                        "size": size,
                        "duration": duration,
                        "success": success,
                        "throughput": size / duration if duration > 0 else 0,
                    },
                )

            # Calculate average performance
            successful_tests = [r for r in performance_results if r["success"]]
            if successful_tests:
                avg_throughput = statistics.mean(
                    [r["throughput"] for r in successful_tests],
                )
                result.performance_metrics["avg_throughput_lines_per_sec"] = (
                    avg_throughput
                )

            result.sample_results.append(
                {"test_type": "performance", "results": performance_results},
            )

        except Exception as e:
            result.sample_results.append({"test_type": "performance", "error": str(e)})

    def _run_memory_tests(self, result: TestResult):
        """Run memory usage tests."""
        try:
            import os

            import psutil

            process = psutil.Process(os.getpid())

            # Baseline memory
            baseline_memory = process.memory_info().rss / 1024 / 1024  # MB

            # Test with large code sample
            large_code = self._generate_test_code(result.language, 5000)

            success, _errors = self.validator.test_parse_samples(
                result.language,
                [large_code],
            )

            # Measure memory after parsing
            post_parse_memory = process.memory_info().rss / 1024 / 1024  # MB

            memory_delta = post_parse_memory - baseline_memory

            result.memory_usage = post_parse_memory
            result.performance_metrics["memory_delta_mb"] = memory_delta

            result.sample_results.append(
                {
                    "test_type": "memory",
                    "baseline_memory_mb": baseline_memory,
                    "post_parse_memory_mb": post_parse_memory,
                    "memory_delta_mb": memory_delta,
                    "success": success,
                },
            )

        except ImportError:
            result.sample_results.append(
                {
                    "test_type": "memory",
                    "warning": "psutil not available for memory testing",
                },
            )
        except Exception as e:
            result.sample_results.append({"test_type": "memory", "error": str(e)})

    def _run_stress_tests(self, result: TestResult):
        """Run stress tests with edge cases."""
        stress_samples = self._generate_stress_test_samples(result.language)

        start_time = time.time()

        results = []
        for i, sample in enumerate(stress_samples):
            try:
                success, errors = self.validator.test_parse_samples(
                    result.language,
                    [sample],
                )
                results.append(
                    {
                        "sample_index": i,
                        "success": success,
                        "errors": errors if not success else [],
                    },
                )
            except Exception as e:
                results.append({"sample_index": i, "success": False, "error": str(e)})

        success_count = sum(1 for r in results if r.get("success", False))
        success_rate = success_count / len(results) if results else 0.0

        result.sample_results.append(
            {
                "test_type": "stress",
                "duration": time.time() - start_time,
                "samples_tested": len(stress_samples),
                "success_rate": success_rate,
                "results": results,
            },
        )

        result.performance_metrics["stress_success_rate"] = success_rate

        if success_rate < 0.8:  # Less than 80% success rate
            result.success = False

    def _generate_test_code(self, language: str, target_lines: int) -> str:
        """Generate test code of specified size."""
        base_samples = self.test_suites.get(language, ["// Empty"])

        # Repeat and vary base samples to reach target size
        lines = []
        sample_index = 0

        while len(lines) < target_lines:
            sample = base_samples[sample_index % len(base_samples)]

            # Add some variation
            if language == "python":
                lines.extend([f"# Generated line {len(lines) + 1}", sample, ""])
            elif language == "javascript":
                lines.extend([f"// Generated line {len(lines) + 1}", sample, ""])
            else:
                lines.extend([sample, ""])

            sample_index += 1

        return "\n".join(lines[:target_lines])

    def _generate_stress_test_samples(self, language: str) -> list[str]:
        """Generate stress test samples with edge cases."""
        stress_samples = []

        # Common stress test patterns
        stress_samples.extend(
            [
                "",  # Empty file
                " " * 1000,  # Whitespace only
                "\n" * 100,  # Many newlines
            ],
        )

        if language == "python":
            stress_samples.extend(
                [
                    "def " + "a" * 100 + "(): pass",  # Very long function name
                    "class A:\n" + "    def method(self): pass\n" * 50,  # Many methods
                    "x = " + repr("a" * 1000),  # Very long string literal
                    "#" + "x" * 500,  # Very long comment
                ],
            )
        elif language == "javascript":
            stress_samples.extend(
                [
                    "function " + "a" * 100 + "() {}",  # Very long function name
                    "{" + '"key": "value",' * 100 + "}",  # Large object literal
                    "var x = '" + "a" * 1000 + "';",  # Very long string
                    "//" + "x" * 500,  # Very long comment
                ],
            )

        return stress_samples

    def _categorize_error(self, error_message: str) -> str:
        """Categorize error message into pattern."""
        error_lower = error_message.lower()

        if "syntax" in error_lower:
            return "syntax_error"
        if "parse" in error_lower:
            return "parse_error"
        if "timeout" in error_lower:
            return "timeout_error"
        if "memory" in error_lower:
            return "memory_error"
        if "abi" in error_lower or "compatibility" in error_lower:
            return "abi_error"
        return "other_error"

    def _get_memory_usage(self) -> float | None:
        """Get current memory usage in MB."""
        try:
            import os

            import psutil

            process = psutil.Process(os.getpid())
            return process.memory_info().rss / 1024 / 1024
        except ImportError:
            return None
        except Exception:
            return None


class SmartSelector:
    """Implements smart grammar selection algorithms with priority scoring and conflict resolution."""

    def __init__(
        self,
        grammar_manager: GrammarManager,
        compatibility_checker: CompatibilityChecker,
        database: CompatibilityDatabase | None = None,
    ):
        """Initialize smart selector.

        Args:
            grammar_manager: Grammar manager instance
            compatibility_checker: Compatibility checker instance
            database: Compatibility database instance
        """
        self.grammar_manager = grammar_manager
        self.compatibility_checker = compatibility_checker
        self.database = database

        # Selection weights for different criteria
        self.default_weights = {
            SelectionCriterion.COMPATIBILITY: 0.35,
            SelectionCriterion.PERFORMANCE: 0.25,
            SelectionCriterion.RELIABILITY: 0.20,
            SelectionCriterion.FEATURES: 0.10,
            SelectionCriterion.RECENCY: 0.05,
            SelectionCriterion.COMMUNITY: 0.05,
        }

    def select_best_grammar(
        self,
        language: str,
        criteria_weights: dict[SelectionCriterion, float] | None = None,
        constraints: dict[str, Any] | None = None,
    ) -> SelectionCandidate | None:
        """Select the best grammar using smart algorithms.

        Args:
            language: Target language
            criteria_weights: Custom weights for selection criteria
            constraints: Additional constraints (version, performance, etc.)

        Returns:
            Best grammar candidate or None
        """
        try:
            logger.info(f"Smart selecting best grammar for {language}")

            # Discover all available grammar candidates
            candidates = self._discover_candidates(language)

            if not candidates:
                logger.warning(f"No grammar candidates found for {language}")
                return None

            # Score each candidate
            weights = criteria_weights or self.default_weights

            for candidate in candidates:
                candidate.overall_score = self._score_candidate(
                    candidate,
                    weights,
                    constraints,
                )

            # Apply conflict resolution if needed
            resolved_candidates = self._resolve_conflicts(candidates)

            # Select best candidate
            best_candidate = max(resolved_candidates, key=lambda c: c.overall_score)

            logger.info(
                f"Selected {best_candidate.version} for {language} (score: {best_candidate.overall_score:.3f})",
            )

            return best_candidate

        except Exception as e:
            logger.error(f"Smart selection failed for {language}: {e}")
            return None

    def select_multiple_grammars(
        self,
        languages: list[str],
        global_constraints: dict[str, Any] | None = None,
    ) -> dict[str, SelectionCandidate | None]:
        """Select best grammars for multiple languages with global optimization.

        Args:
            languages: List of languages to select grammars for
            global_constraints: Global constraints across all selections

        Returns:
            Dictionary mapping language to selected candidate
        """
        try:
            logger.info(f"Smart selecting grammars for {len(languages)} languages")

            selections = {}

            # First pass: individual selections
            for language in languages:
                try:
                    candidate = self.select_best_grammar(language)
                    selections[language] = candidate
                except Exception as e:
                    logger.error(f"Failed to select grammar for {language}: {e}")
                    selections[language] = None

            # Second pass: global optimization
            if global_constraints:
                selections = self._optimize_global_selection(
                    selections,
                    global_constraints,
                )

            return selections

        except Exception as e:
            logger.error(f"Multiple grammar selection failed: {e}")
            return dict.fromkeys(languages)

    def resolve_grammar_conflicts(
        self,
        conflicts: list[tuple[str, list[SelectionCandidate]]],
    ) -> dict[str, SelectionCandidate]:
        """Resolve conflicts between grammar candidates.

        Args:
            conflicts: List of (language, conflicting_candidates) tuples

        Returns:
            Dictionary mapping language to resolved candidate
        """
        try:
            logger.info(f"Resolving conflicts for {len(conflicts)} languages")

            resolutions = {}

            for language, candidates in conflicts:
                try:
                    # Use conflict resolution algorithm
                    resolved_candidate = self._resolve_single_conflict(
                        language,
                        candidates,
                    )
                    resolutions[language] = resolved_candidate
                except Exception as e:
                    logger.error(f"Failed to resolve conflict for {language}: {e}")
                    # Fall back to highest priority candidate
                    resolutions[language] = min(
                        candidates,
                        key=lambda c: c.priority.value,
                    )

            return resolutions

        except Exception as e:
            logger.error(f"Conflict resolution failed: {e}")
            return {}

    def recommend_grammar_upgrades(
        self,
        current_grammars: dict[str, str],
    ) -> dict[str, dict[str, Any]]:
        """Recommend grammar upgrades based on compatibility and performance.

        Args:
            current_grammars: Current grammar versions by language

        Returns:
            Upgrade recommendations by language
        """
        try:
            logger.info(
                f"Generating upgrade recommendations for {len(current_grammars)} grammars",
            )

            recommendations = {}

            for language, current_version in current_grammars.items():
                try:
                    # Find better candidates
                    candidates = self._discover_candidates(language)

                    if not candidates:
                        continue

                    # Filter out current version and worse options
                    current_candidate = next(
                        (c for c in candidates if c.version == current_version),
                        None,
                    )

                    if not current_candidate:
                        continue

                    # Score all candidates
                    for candidate in candidates:
                        candidate.overall_score = self._score_candidate(
                            candidate,
                            self.default_weights,
                        )

                    # Find better alternatives
                    better_candidates = [
                        c
                        for c in candidates
                        if c.overall_score > current_candidate.overall_score
                    ]

                    if better_candidates:
                        best_alternative = max(
                            better_candidates,
                            key=lambda c: c.overall_score,
                        )

                        # Check for breaking changes
                        breaking_changes = (
                            self.compatibility_checker.detect_breaking_changes(
                                language,
                                current_version,
                                best_alternative.version,
                            )
                        )

                        recommendations[language] = {
                            "current_version": current_version,
                            "recommended_version": best_alternative.version,
                            "score_improvement": best_alternative.overall_score
                            - current_candidate.overall_score,
                            "breaking_changes": breaking_changes,
                            "upgrade_risk": self._assess_upgrade_risk(breaking_changes),
                            "benefits": self._describe_upgrade_benefits(
                                current_candidate,
                                best_alternative,
                            ),
                        }

                except Exception as e:
                    logger.error(
                        f"Failed to generate recommendation for {language}: {e}",
                    )
                    continue

            return recommendations

        except Exception as e:
            logger.error(f"Upgrade recommendation generation failed: {e}")
            return {}

    def _discover_candidates(self, language: str) -> list[SelectionCandidate]:
        """Discover all available grammar candidates for a language."""
        candidates = []

        try:
            # Get available grammars from registry
            registry_grammars = self.grammar_manager._registry.discover_grammars()

            if language in registry_grammars:
                for grammar_path, priority in registry_grammars[language]:
                    # Get version info
                    version = "unknown"
                    metadata = {}

                    # Try to get installation info
                    install_info = (
                        self.grammar_manager._installer._load_installation_info(
                            language,
                        )
                    )
                    if install_info:
                        version = install_info.version
                        metadata = install_info.metadata

                    candidate = SelectionCandidate(
                        language=language,
                        version=version,
                        grammar_path=grammar_path,
                        priority=priority,
                        metadata=metadata,
                    )

                    candidates.append(candidate)

            return candidates

        except Exception as e:
            logger.error(f"Failed to discover candidates for {language}: {e}")
            return []

    def _score_candidate(
        self,
        candidate: SelectionCandidate,
        weights: dict[SelectionCriterion, float],
        constraints: dict[str, Any] | None = None,
    ) -> float:
        """Score a grammar candidate using multiple criteria."""
        try:
            # Calculate individual scores
            candidate.compatibility_score = self._score_compatibility(candidate)
            candidate.performance_score = self._score_performance(candidate)
            candidate.reliability_score = self._score_reliability(candidate)
            candidate.feature_score = self._score_features(candidate)
            candidate.recency_score = self._score_recency(candidate)

            # Calculate weighted overall score
            overall_score = (
                weights.get(SelectionCriterion.COMPATIBILITY, 0)
                * candidate.compatibility_score
                + weights.get(SelectionCriterion.PERFORMANCE, 0)
                * candidate.performance_score
                + weights.get(SelectionCriterion.RELIABILITY, 0)
                * candidate.reliability_score
                + weights.get(SelectionCriterion.FEATURES, 0) * candidate.feature_score
                + weights.get(SelectionCriterion.RECENCY, 0) * candidate.recency_score
            )

            # Apply constraints penalties
            if constraints:
                overall_score = self._apply_constraint_penalties(
                    overall_score,
                    candidate,
                    constraints,
                )

            return max(0.0, min(1.0, overall_score))

        except Exception as e:
            logger.error(f"Failed to score candidate {candidate.version}: {e}")
            return 0.0

    def _score_compatibility(self, candidate: SelectionCandidate) -> float:
        """Score compatibility of a grammar candidate."""
        try:
            # Check compatibility
            compat_result = self.compatibility_checker.check_compatibility(
                candidate.language,
                candidate.version,
            )

            return self.compatibility_checker._calculate_compatibility_score(
                compat_result,
            )

        except Exception as e:
            logger.error(f"Failed to score compatibility for {candidate.version}: {e}")
            return 0.0

    def _score_performance(self, candidate: SelectionCandidate) -> float:
        """Score performance of a grammar candidate."""
        try:
            # Get performance metrics from metadata
            metadata = candidate.metadata
            performance_data = metadata.get("performance", {})

            if not performance_data:
                return 0.5  # Neutral score if no data

            # Score based on parse time (lower is better)
            parse_time = performance_data.get("parse_time", 1.0)

            if parse_time < 0.1:
                return 1.0
            if parse_time < 0.5:
                return 0.9
            if parse_time < 1.0:
                return 0.7
            if parse_time < 2.0:
                return 0.5
            return 0.2

        except Exception:
            return 0.5

    def _score_reliability(self, candidate: SelectionCandidate) -> float:
        """Score reliability of a grammar candidate."""
        try:
            # Base score from priority
            priority_scores = {
                GrammarPriority.USER: 0.8,
                GrammarPriority.PACKAGE: 0.9,
                GrammarPriority.FALLBACK: 0.6,
            }

            base_score = priority_scores.get(candidate.priority, 0.5)

            # Adjust based on validation results
            metadata = candidate.metadata
            validation_data = metadata.get("validation", {})

            if validation_data.get("errors"):
                base_score *= 0.3  # Significant penalty for errors
            elif validation_data.get("warnings"):
                base_score *= 0.8  # Minor penalty for warnings

            return base_score

        except Exception:
            return 0.5

    def _score_features(self, candidate: SelectionCandidate) -> float:
        """Score feature completeness of a grammar candidate."""
        try:
            # This would analyze the grammar's feature completeness
            # For now, return a placeholder based on metadata
            metadata = candidate.metadata

            # Check for advanced features in metadata
            feature_indicators = [
                "node_types_count",
                "field_support",
                "query_support",
                "incremental_parsing",
            ]

            feature_count = sum(
                1 for indicator in feature_indicators if indicator in metadata
            )

            return min(1.0, feature_count / len(feature_indicators))

        except Exception:
            return 0.5

    def _score_recency(self, candidate: SelectionCandidate) -> float:
        """Score recency of a grammar candidate."""
        try:
            # Get installation date from metadata
            metadata = candidate.metadata

            # This would calculate recency based on installation date, commit date, etc.
            # For now, return a neutral score
            return 0.5

        except Exception:
            return 0.5

    def _resolve_conflicts(
        self,
        candidates: list[SelectionCandidate],
    ) -> list[SelectionCandidate]:
        """Resolve conflicts between grammar candidates."""
        if len(candidates) <= 1:
            return candidates

        # Group by version and priority conflicts
        conflicts = {}
        for candidate in candidates:
            key = (candidate.language, candidate.version)
            if key not in conflicts:
                conflicts[key] = []
            conflicts[key].append(candidate)

        resolved = []

        for version_candidates in conflicts.values():
            if len(version_candidates) == 1:
                resolved.extend(version_candidates)
            else:
                # Resolve by keeping highest priority
                best_candidate = min(version_candidates, key=lambda c: c.priority.value)
                resolved.append(best_candidate)

        return resolved

    def _resolve_single_conflict(
        self,
        language: str,
        candidates: list[SelectionCandidate],
    ) -> SelectionCandidate:
        """Resolve conflict for a single language."""
        if len(candidates) == 1:
            return candidates[0]

        # Score all candidates with default weights
        for candidate in candidates:
            candidate.overall_score = self._score_candidate(
                candidate,
                self.default_weights,
            )

        # Return highest scoring candidate
        return max(candidates, key=lambda c: c.overall_score)

    def _optimize_global_selection(
        self,
        selections: dict[str, SelectionCandidate | None],
        global_constraints: dict[str, Any],
    ) -> dict[str, SelectionCandidate | None]:
        """Optimize selections globally considering cross-language constraints."""
        # This would implement global optimization logic
        # For now, return unchanged selections
        return selections

    def _apply_constraint_penalties(
        self,
        base_score: float,
        candidate: SelectionCandidate,
        constraints: dict[str, Any],
    ) -> float:
        """Apply constraint penalties to candidate score."""
        penalty_factor = 1.0

        # Version constraints
        if "min_version" in constraints:
            # This would check version compatibility
            pass

        if "max_version" in constraints:
            # This would check version compatibility
            pass

        # Performance constraints
        if "max_parse_time" in constraints:
            metadata = candidate.metadata
            performance_data = metadata.get("performance", {})
            parse_time = performance_data.get("parse_time", 0)

            max_allowed = constraints["max_parse_time"]
            if parse_time > max_allowed:
                penalty_factor *= 0.5  # Significant penalty

        return base_score * penalty_factor

    def _assess_upgrade_risk(self, breaking_changes: list[dict[str, Any]]) -> str:
        """Assess risk level of grammar upgrade."""
        if not breaking_changes:
            return "low"

        high_impact_changes = [c for c in breaking_changes if c.get("impact") == "high"]

        if high_impact_changes:
            return "high"
        if len(breaking_changes) > 3:
            return "medium"
        return "low"

    def _describe_upgrade_benefits(
        self,
        current: SelectionCandidate,
        upgrade: SelectionCandidate,
    ) -> list[str]:
        """Describe benefits of upgrading."""
        benefits = []

        score_diff = upgrade.overall_score - current.overall_score
        if score_diff > 0.1:
            benefits.append(f"Overall quality improvement: +{score_diff:.1%}")

        if upgrade.performance_score > current.performance_score:
            benefits.append("Improved parsing performance")

        if upgrade.compatibility_score > current.compatibility_score:
            benefits.append("Better compatibility")

        if upgrade.reliability_score > current.reliability_score:
            benefits.append("Enhanced reliability")

        return benefits


class CompatibilityDatabase:
    """Persistent storage for grammar compatibility data using SQLite."""

    def __init__(self, database_path: Path | None = None):
        """Initialize compatibility database.

        Args:
            database_path: Path to SQLite database file
        """
        self.database_path = database_path or (
            Path.home() / ".cache" / "treesitter-chunker" / "compatibility.db"
        )

        # Ensure directory exists
        self.database_path.parent.mkdir(parents=True, exist_ok=True)

        self._init_database()

    def _init_database(self):
        """Initialize database schema."""
        try:
            with sqlite3.connect(self.database_path) as conn:
                conn.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS compatibility_results (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        language TEXT NOT NULL,
                        grammar_version TEXT NOT NULL,
                        language_version TEXT,
                        level TEXT NOT NULL,
                        score REAL NOT NULL,
                        issues TEXT,  -- JSON encoded
                        warnings TEXT,  -- JSON encoded
                        breaking_changes TEXT,  -- JSON encoded
                        performance_impact TEXT,  -- JSON encoded
                        test_results TEXT,  -- JSON encoded
                        timestamp REAL NOT NULL,
                        UNIQUE(language, grammar_version, language_version)
                    );

                    CREATE TABLE IF NOT EXISTS test_results (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        language TEXT NOT NULL,
                        grammar_version TEXT NOT NULL,
                        test_type TEXT NOT NULL,
                        success BOOLEAN NOT NULL,
                        duration REAL NOT NULL,
                        memory_usage REAL,
                        error_message TEXT,
                        sample_results TEXT,  -- JSON encoded
                        performance_metrics TEXT,  -- JSON encoded
                        timestamp REAL NOT NULL
                    );

                    CREATE TABLE IF NOT EXISTS grammar_metadata (
                        language TEXT PRIMARY KEY,
                        last_updated REAL,
                        available_versions TEXT,  -- JSON encoded
                        metadata TEXT  -- JSON encoded
                    );

                    CREATE INDEX IF NOT EXISTS idx_compatibility_language ON compatibility_results(language);
                    CREATE INDEX IF NOT EXISTS idx_compatibility_timestamp ON compatibility_results(timestamp);
                    CREATE INDEX IF NOT EXISTS idx_test_results_language ON test_results(language);
                    CREATE INDEX IF NOT EXISTS idx_test_results_timestamp ON test_results(timestamp);
                """,
                )

                logger.info(f"Initialized compatibility database: {self.database_path}")

        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise

    def store_compatibility_result(self, result: CompatibilityResult):
        """Store compatibility result in database.

        Args:
            result: Compatibility result to store
        """
        try:
            with sqlite3.connect(self.database_path) as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO compatibility_results
                    (language, grammar_version, language_version, level, score,
                     issues, warnings, breaking_changes, performance_impact,
                     test_results, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        result.language,
                        result.grammar_version,
                        result.language_version,
                        result.level.value,
                        result.score,
                        json.dumps(result.issues),
                        json.dumps(result.warnings),
                        json.dumps(result.breaking_changes),
                        (
                            json.dumps(result.performance_impact)
                            if result.performance_impact
                            else None
                        ),
                        (
                            json.dumps(result.test_results)
                            if result.test_results
                            else None
                        ),
                        result.timestamp,
                    ),
                )

        except Exception as e:
            logger.error(f"Failed to store compatibility result: {e}")

    def get_compatibility_result(
        self,
        language: str,
        grammar_version: str,
        language_version: str | None = None,
    ) -> CompatibilityResult | None:
        """Get compatibility result from database.

        Args:
            language: Language name
            grammar_version: Grammar version
            language_version: Language version

        Returns:
            Cached compatibility result or None
        """
        try:
            with sqlite3.connect(self.database_path) as conn:
                cursor = conn.execute(
                    """
                    SELECT level, score, issues, warnings, breaking_changes,
                           performance_impact, test_results, timestamp
                    FROM compatibility_results
                    WHERE language = ? AND grammar_version = ?
                    AND (language_version = ? OR language_version IS NULL)
                    ORDER BY timestamp DESC
                    LIMIT 1
                """,
                    (language, grammar_version, language_version),
                )

                row = cursor.fetchone()
                if row:
                    return CompatibilityResult(
                        language=language,
                        grammar_version=grammar_version,
                        language_version=language_version,
                        level=CompatibilityLevel(row[0]),
                        score=row[1],
                        issues=json.loads(row[2]) if row[2] else [],
                        warnings=json.loads(row[3]) if row[3] else [],
                        breaking_changes=json.loads(row[4]) if row[4] else [],
                        performance_impact=json.loads(row[5]) if row[5] else None,
                        test_results=json.loads(row[6]) if row[6] else None,
                        timestamp=row[7],
                    )

                return None

        except Exception as e:
            logger.error(f"Failed to get compatibility result: {e}")
            return None

    def store_test_result(self, result: TestResult):
        """Store test result in database.

        Args:
            result: Test result to store
        """
        try:
            with sqlite3.connect(self.database_path) as conn:
                conn.execute(
                    """
                    INSERT INTO test_results
                    (language, grammar_version, test_type, success, duration,
                     memory_usage, error_message, sample_results, performance_metrics, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        result.language,
                        result.grammar_version,
                        result.test_type,
                        result.success,
                        result.duration,
                        result.memory_usage,
                        result.error_message,
                        json.dumps(result.sample_results),
                        json.dumps(result.performance_metrics),
                        result.timestamp,
                    ),
                )

        except Exception as e:
            logger.error(f"Failed to store test result: {e}")

    def get_compatibility_history(
        self,
        language: str,
        limit: int = 100,
    ) -> list[CompatibilityResult]:
        """Get compatibility history for a language.

        Args:
            language: Language name
            limit: Maximum number of results

        Returns:
            List of historical compatibility results
        """
        try:
            with sqlite3.connect(self.database_path) as conn:
                cursor = conn.execute(
                    """
                    SELECT grammar_version, language_version, level, score,
                           issues, warnings, breaking_changes, performance_impact,
                           test_results, timestamp
                    FROM compatibility_results
                    WHERE language = ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                """,
                    (language, limit),
                )

                results = []
                for row in cursor.fetchall():
                    result = CompatibilityResult(
                        language=language,
                        grammar_version=row[0],
                        language_version=row[1],
                        level=CompatibilityLevel(row[2]),
                        score=row[3],
                        issues=json.loads(row[4]) if row[4] else [],
                        warnings=json.loads(row[5]) if row[5] else [],
                        breaking_changes=json.loads(row[6]) if row[6] else [],
                        performance_impact=json.loads(row[7]) if row[7] else None,
                        test_results=json.loads(row[8]) if row[8] else None,
                        timestamp=row[9],
                    )
                    results.append(result)

                return results

        except Exception as e:
            logger.error(f"Failed to get compatibility history: {e}")
            return []

    def get_performance_trends(self, language: str, days: int = 30) -> dict[str, Any]:
        """Get performance trends for a language.

        Args:
            language: Language name
            days: Number of days to analyze

        Returns:
            Performance trend analysis
        """
        try:
            cutoff_time = time.time() - (days * 24 * 60 * 60)

            with sqlite3.connect(self.database_path) as conn:
                cursor = conn.execute(
                    """
                    SELECT performance_metrics, timestamp
                    FROM test_results
                    WHERE language = ? AND timestamp > ? AND performance_metrics IS NOT NULL
                    ORDER BY timestamp
                """,
                    (language, cutoff_time),
                )

                data_points = []
                for row in cursor.fetchall():
                    metrics = json.loads(row[0])
                    data_points.append({"metrics": metrics, "timestamp": row[1]})

                if not data_points:
                    return {"error": "No performance data available"}

                # Analyze trends
                parse_times = [
                    dp["metrics"].get("avg_throughput_lines_per_sec", 0)
                    for dp in data_points
                    if "avg_throughput_lines_per_sec" in dp["metrics"]
                ]

                memory_usage = [
                    dp["metrics"].get("memory_delta_mb", 0)
                    for dp in data_points
                    if "memory_delta_mb" in dp["metrics"]
                ]

                trends = {
                    "language": language,
                    "days_analyzed": days,
                    "data_points": len(data_points),
                }

                if parse_times:
                    trends["throughput"] = {
                        "average": statistics.mean(parse_times),
                        "median": statistics.median(parse_times),
                        "trend": (
                            "improving"
                            if parse_times[-1] > parse_times[0]
                            else "declining"
                        ),
                    }

                if memory_usage:
                    trends["memory"] = {
                        "average_delta": statistics.mean(memory_usage),
                        "median_delta": statistics.median(memory_usage),
                        "trend": (
                            "improving"
                            if memory_usage[-1] < memory_usage[0]
                            else "declining"
                        ),
                    }

                return trends

        except Exception as e:
            logger.error(f"Failed to get performance trends: {e}")
            return {"error": str(e)}

    def cleanup_old_data(self, days_to_keep: int = 90) -> dict[str, int]:
        """Clean up old compatibility data.

        Args:
            days_to_keep: Number of days of data to retain

        Returns:
            Cleanup statistics
        """
        try:
            cutoff_time = time.time() - (days_to_keep * 24 * 60 * 60)

            stats = {"compatibility_results": 0, "test_results": 0}

            with sqlite3.connect(self.database_path) as conn:
                # Clean compatibility results
                cursor = conn.execute(
                    """
                    DELETE FROM compatibility_results WHERE timestamp < ?
                """,
                    (cutoff_time,),
                )
                stats["compatibility_results"] = cursor.rowcount

                # Clean test results
                cursor = conn.execute(
                    """
                    DELETE FROM test_results WHERE timestamp < ?
                """,
                    (cutoff_time,),
                )
                stats["test_results"] = cursor.rowcount

                # Vacuum database
                conn.execute("VACUUM")

                logger.info(f"Cleaned up {stats} old database records")

            return stats

        except Exception as e:
            logger.error(f"Failed to cleanup database: {e}")
            return {"error": str(e)}

    def get_database_stats(self) -> dict[str, Any]:
        """Get database statistics.

        Returns:
            Database usage statistics
        """
        try:
            with sqlite3.connect(self.database_path) as conn:
                stats = {}

                # Count records
                cursor = conn.execute("SELECT COUNT(*) FROM compatibility_results")
                stats["compatibility_results"] = cursor.fetchone()[0]

                cursor = conn.execute("SELECT COUNT(*) FROM test_results")
                stats["test_results"] = cursor.fetchone()[0]

                cursor = conn.execute("SELECT COUNT(*) FROM grammar_metadata")
                stats["grammar_metadata"] = cursor.fetchone()[0]

                # Database file size
                stats["database_size_mb"] = (
                    self.database_path.stat().st_size / 1024 / 1024
                )

                # Date range
                cursor = conn.execute(
                    """
                    SELECT MIN(timestamp), MAX(timestamp) FROM compatibility_results
                """,
                )
                min_time, max_time = cursor.fetchone()

                if min_time and max_time:
                    stats["oldest_record"] = min_time
                    stats["newest_record"] = max_time
                    stats["data_span_days"] = (max_time - min_time) / (24 * 60 * 60)

                return stats

        except Exception as e:
            logger.error(f"Failed to get database stats: {e}")
            return {"error": str(e)}

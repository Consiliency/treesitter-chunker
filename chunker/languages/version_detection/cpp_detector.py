"""C/C++ version detection module for Phase 1.7."""

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class CppVersionDetector:
    """Detects C/C++ version from compiler directives and code."""

    def __init__(self):
        self.version_patterns = {
            "pragma_version": r"#pragma\s+version\s+(\d+(?:\.\d+)?)",
            "compiler_version": r"//\s*(?:gcc|clang|msvc|icc)\s+(\d+\.\d+(?:\.\d+)?)",
            "cxx_standard": r"//\s*C\+\+(\d{2})|std::c\+\+(\d{2})|/std:c\+\+(\d{2})",
            "feature_test": r"__cpp_(\w+)\s*(?:>=?)?\s*(\d+)L?",
            "c_standard": r"//\s*C(\d{2})|__STDC_VERSION__\s*==\s*(\d+)L",
        }

        # Map C++ standards to years and versions
        self.cpp_standard_map = {
            "98": {"year": 1998, "name": "C++98"},
            "03": {"year": 2003, "name": "C++03"},
            "11": {"year": 2011, "name": "C++11"},
            "14": {"year": 2014, "name": "C++14"},
            "17": {"year": 2017, "name": "C++17"},
            "20": {"year": 2020, "name": "C++20"},
            "23": {"year": 2023, "name": "C++23"},
            "26": {"year": 2026, "name": "C++26"},
        }

        # Map C standards
        self.c_standard_map = {
            "89": {"year": 1989, "name": "C89/ANSI C"},
            "90": {"year": 1990, "name": "C90/ISO C"},
            "95": {"year": 1995, "name": "C95"},
            "99": {"year": 1999, "name": "C99"},
            "11": {"year": 2011, "name": "C11"},
            "17": {"year": 2017, "name": "C17"},
            "23": {"year": 2023, "name": "C23"},
        }

        # Map feature test macros to C++ standards
        self.feature_test_map = {
            "__cpp_exceptions": {"min_std": "98", "value": 199711},
            "__cpp_rtti": {"min_std": "98", "value": 199711},
            "__cpp_static_assert": {"min_std": "11", "value": 200410},
            "__cpp_variadic_templates": {"min_std": "11", "value": 200704},
            "__cpp_rvalue_references": {"min_std": "11", "value": 200610},
            "__cpp_initializer_lists": {"min_std": "11", "value": 200806},
            "__cpp_lambdas": {"min_std": "11", "value": 200907},
            "__cpp_constexpr": {"min_std": "11", "value": 200704},
            "__cpp_decltype": {"min_std": "11", "value": 200707},
            "__cpp_auto": {"min_std": "11", "value": 200712},
            "__cpp_binary_literals": {"min_std": "14", "value": 201304},
            "__cpp_generic_lambdas": {"min_std": "14", "value": 201304},
            "__cpp_return_type_deduction": {"min_std": "14", "value": 201304},
            "__cpp_variable_templates": {"min_std": "14", "value": 201304},
            "__cpp_if_constexpr": {"min_std": "17", "value": 201606},
            "__cpp_structured_bindings": {"min_std": "17", "value": 201606},
            "__cpp_inline_variables": {"min_std": "17", "value": 201606},
            "__cpp_fold_expressions": {"min_std": "17", "value": 201603},
            "__cpp_concepts": {"min_std": "20", "value": 201907},
            "__cpp_coroutines": {"min_std": "20", "value": 201902},
            "__cpp_modules": {"min_std": "20", "value": 201907},
            "__cpp_ranges": {"min_std": "20", "value": 201911},
            "__cpp_three_way_comparison": {"min_std": "20", "value": 201907},
        }

        logger.debug(
            "Initialized CppVersionDetector with %d patterns",
            len(self.version_patterns),
        )

    def detect_from_pragma(self, content: str) -> str | None:
        """Extract version from #pragma directives.

        Args:
            content: The file content to search

        Returns:
            Version string or None if not found
        """
        try:
            # Look for #pragma version
            patterns = [
                r"#pragma\s+version\s*\(\s*(\d+(?:\.\d+)?)\s*\)",
                r"#pragma\s+version\s+(\d+(?:\.\d+)?)",
                r"#pragma\s+clang\s+version\s+(\d+(?:\.\d+)?)",
                r"#pragma\s+GCC\s+version\s+(\d+(?:\.\d+)?)",
            ]

            for pattern in patterns:
                match = re.search(pattern, content)
                if match:
                    version = match.group(1)
                    logger.debug("Found pragma version: %s", version)
                    return version

            # Check for target pragma
            pattern = r'#pragma\s+GCC\s+target\s*\([^)]*"std=c\+\+(\d{2})"'
            match = re.search(pattern, content)
            if match:
                std = match.group(1)
                logger.debug("Found target C++ standard: C++%s", std)
                return f"C++{std}"

        except Exception as e:
            logger.error("Error detecting from pragma: %s", e)

        return None

    def detect_compiler_version(self, content: str) -> str | None:
        """Detect compiler version from comments.

        Args:
            content: The file content to search

        Returns:
            Compiler version string or None if not found
        """
        try:
            # Look for compiler version comments
            patterns = [
                r"//\s*gcc\s+(\d+\.\d+(?:\.\d+)?)",
                r"//\s*g\+\+\s+(\d+\.\d+(?:\.\d+)?)",
                r"//\s*clang\s+(\d+\.\d+(?:\.\d+)?)",
                r"//\s*clang\+\+\s+(\d+\.\d+(?:\.\d+)?)",
                r"//\s*msvc\s+(\d+(?:\.\d+)?)",
                r"//\s*icc\s+(\d+(?:\.\d+)?)",
                r"/\*\s*Compiled with\s+\w+\s+(\d+\.\d+(?:\.\d+)?)\s*\*/",
            ]

            for pattern in patterns:
                match = re.search(pattern, content, re.IGNORECASE)
                if match:
                    version = match.group(1)
                    logger.debug("Found compiler version: %s", version)
                    return version

            # Check for version macros
            if "__GNUC__" in content:
                pattern = r"__GNUC__\s*==\s*(\d+)"
                match = re.search(pattern, content)
                if match:
                    major = match.group(1)
                    pattern = r"__GNUC_MINOR__\s*==\s*(\d+)"
                    minor_match = re.search(pattern, content)
                    if minor_match:
                        minor = minor_match.group(1)
                        version = f"{major}.{minor}"
                        logger.debug("Found GCC version from macros: %s", version)
                        return version

        except Exception as e:
            logger.error("Error detecting compiler version: %s", e)

        return None

    def detect_cxx_standard(self, content: str) -> str | None:
        """Detect C++ standard version from code.

        Args:
            content: The file content to search

        Returns:
            C++ standard like "11", "14", "17", "20" or None
        """
        try:
            # Look for C++ standard comments
            patterns = [
                r"//\s*C\+\+(\d{2})",
                r"/\*\s*C\+\+(\d{2})\s*\*/",
                r"//\s*requires\s+C\+\+(\d{2})",
                r"//\s*std:c\+\+(\d{2})",
                r"/std:c\+\+(\d{2})",
            ]

            standards = []
            for pattern in patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                for match in matches:
                    if match in self.cpp_standard_map:
                        standards.append(match)

            # Check for __cplusplus macro
            pattern = r"__cplusplus\s*(?:==|>=)\s*(\d+)L?"
            matches = re.findall(pattern, content)
            for match in matches:
                value = int(match)
                # Map __cplusplus values to standards
                if value >= 202002:
                    standards.append("20")
                elif value >= 201703:
                    standards.append("17")
                elif value >= 201402:
                    standards.append("14")
                elif value >= 201103:
                    standards.append("11")
                elif value >= 199711:
                    standards.append("98")

            # Check for C++11+ features
            feature_indicators = {
                r"\bauto\s+\w+\s*=": "11",  # auto keyword
                r"nullptr": "11",  # nullptr
                r"override\b": "11",  # override specifier
                r"final\b": "11",  # final specifier
                r"constexpr\s+": "11",  # constexpr
                r"static_assert\s*\(": "11",  # static_assert
                r"std::unique_ptr": "11",  # unique_ptr
                r"std::shared_ptr": "11",  # shared_ptr
                r"std::make_unique": "14",  # make_unique
                r"if\s+constexpr\s*\(": "17",  # if constexpr
                r"std::optional": "17",  # optional
                r"std::variant": "17",  # variant
                r"std::string_view": "17",  # string_view
                r"concept\s+\w+\s*=": "20",  # concepts
                r"co_await": "20",  # coroutines
                r"co_return": "20",  # coroutines
                r"co_yield": "20",  # coroutines
                r"<=>": "20",  # spaceship operator
                r"std::ranges::": "20",  # ranges
            }

            for pattern, std in feature_indicators.items():
                if re.search(pattern, content):
                    standards.append(std)
                    logger.debug("Detected C++%s feature: %s", std, pattern)

            if standards:
                # Return the highest standard detected
                max_standard = max(standards)
                logger.debug("Detected C++ standard: C++%s", max_standard)
                return max_standard

        except Exception as e:
            logger.error("Error detecting C++ standard: %s", e)

        return None

    def detect_feature_test_macros(self, content: str) -> list[str]:
        """Detect C++ feature test macros.

        Args:
            content: The file content to search

        Returns:
            List of detected feature test macros
        """
        features = []

        try:
            # Look for feature test macros
            pattern = r"(__cpp_\w+)\s*(?:>=?)?\s*(\d+)L?"
            matches = re.findall(pattern, content)

            for macro, value in matches:
                if macro in self.feature_test_map:
                    features.append(macro)
                    logger.debug("Detected feature test macro: %s = %s", macro, value)

            # Also check for ifdef/ifndef
            pattern = r"#ifn?def\s+(__cpp_\w+)"
            matches = re.findall(pattern, content)
            for macro in matches:
                if macro not in features and macro in self.feature_test_map:
                    features.append(macro)
                    logger.debug("Detected feature test macro in ifdef: %s", macro)

        except Exception as e:
            logger.error("Error detecting feature test macros: %s", e)

        return features

    def map_features_to_standard(self, features: list[str]) -> str | None:
        """Map feature test macros to C++ standard version.

        Args:
            features: List of feature test macros

        Returns:
            C++ standard version or None
        """
        try:
            if not features:
                return None

            # Find minimum required standard for all features
            min_standards = []
            for feature in features:
                if feature in self.feature_test_map:
                    min_std = self.feature_test_map[feature]["min_std"]
                    min_standards.append(min_std)

            if min_standards:
                # Return the highest minimum standard
                max_min_standard = max(min_standards)
                logger.debug("Mapped features to C++%s", max_min_standard)
                return max_min_standard

        except Exception as e:
            logger.error("Error mapping features to standard: %s", e)

        return None

    def detect_c_standard(self, content: str) -> str | None:
        """Detect C standard version from code.

        Args:
            content: The file content to search

        Returns:
            C standard like "99", "11", "17" or None
        """
        try:
            # Look for C standard comments
            patterns = [
                r"//\s*C(\d{2})",
                r"/\*\s*C(\d{2})\s*\*/",
                r"//\s*requires\s+C(\d{2})",
                r"//\s*std=c(\d{2})",
            ]

            for pattern in patterns:
                match = re.search(pattern, content)
                if match:
                    std = match.group(1)
                    if std in self.c_standard_map:
                        logger.debug("Found C standard: C%s", std)
                        return std

            # Check for __STDC_VERSION__ macro
            pattern = r"__STDC_VERSION__\s*(?:==|>=)\s*(\d+)L?"
            match = re.search(pattern, content)
            if match:
                value = int(match.group(1))
                # Map __STDC_VERSION__ values to standards
                if value >= 202300:
                    return "23"
                if value >= 201710:
                    return "17"
                if value >= 201112:
                    return "11"
                if value >= 199901:
                    return "99"
                if value >= 199409:
                    return "95"

        except Exception as e:
            logger.error("Error detecting C standard: %s", e)

        return None

    def detect_version(
        self,
        content: str,
        file_path: Path | None = None,
    ) -> dict[str, str | None]:
        """Main method to detect C/C++ version from all sources.

        Args:
            content: The file content to analyze
            file_path: Optional path to the file being analyzed

        Returns:
            Dictionary with results from each detection method
        """
        results = {}

        try:
            # Determine if it's C or C++ based on file extension or content
            is_cpp = False
            if file_path:
                if file_path.suffix in [
                    ".cpp",
                    ".cxx",
                    ".cc",
                    ".C",
                    ".c++",
                    ".hpp",
                    ".hxx",
                    ".h++",
                ]:
                    is_cpp = True
                elif file_path.suffix in [".c", ".h"]:
                    # Check content for C++ indicators
                    cpp_indicators = [
                        "class ",
                        "namespace ",
                        "template",
                        "std::",
                        "iostream",
                        "using namespace",
                        "public:",
                        "private:",
                        "protected:",
                    ]
                    if any(indicator in content for indicator in cpp_indicators):
                        is_cpp = True
            elif "std::" in content or "namespace" in content or "class " in content:
                is_cpp = True

            results["language"] = "C++" if is_cpp else "C"

            # Try all detection methods
            results["pragma_version"] = self.detect_from_pragma(content)
            results["compiler_version"] = self.detect_compiler_version(content)

            if is_cpp:
                results["cxx_standard"] = self.detect_cxx_standard(content)
                features = self.detect_feature_test_macros(content)
                if features:
                    results["feature_test_macros"] = features
                    mapped_std = self.map_features_to_standard(features)
                    if mapped_std:
                        results["standard_from_features"] = mapped_std
            else:
                results["c_standard"] = self.detect_c_standard(content)

            # Add file path context if available
            if file_path:
                results["file_path"] = str(file_path)
                results["file_type"] = (
                    "header" if file_path.suffix in [".h", ".hpp", ".hxx"] else "source"
                )

            logger.info(
                "Version detection complete: %s",
                {
                    k: v
                    for k, v in results.items()
                    if v and k not in ["feature_test_macros", "file_path"]
                },
            )

        except Exception as e:
            logger.error("Error in version detection: %s", e)

        return results

    def get_primary_version(
        self,
        detection_results: dict[str, str | None],
    ) -> str | None:
        """Determine the primary version from multiple detection results.

        Prioritizes: pragma > compiler > C++ standard > features > C standard

        Args:
            detection_results: Dictionary of detection results

        Returns:
            Most reliable version string or None
        """
        try:
            # Check language
            language = detection_results.get("language", "C")

            # Priority order depends on language
            if language == "C++":
                priority_order = [
                    "pragma_version",
                    "cxx_standard",
                    "standard_from_features",
                    "compiler_version",
                ]

                for source in priority_order:
                    if detection_results.get(source):
                        version = detection_results[source]
                        if (
                            source == "cxx_standard"
                            or source == "standard_from_features"
                        ):
                            version = f"C++{version}"
                        logger.debug(
                            "Selected primary version %s from %s",
                            version,
                            source,
                        )
                        return version
            else:
                priority_order = ["pragma_version", "c_standard", "compiler_version"]

                for source in priority_order:
                    if detection_results.get(source):
                        version = detection_results[source]
                        if source == "c_standard":
                            version = f"C{version}"
                        logger.debug(
                            "Selected primary version %s from %s",
                            version,
                            source,
                        )
                        return version

        except Exception as e:
            logger.error("Error determining primary version: %s", e)

        return None


class CppVersionInfo:
    """Container for C/C++ version information."""

    def __init__(
        self,
        compiler_version: str | None,
        cxx_standard: str | None,
        features: list[str],
        source: str,
    ):
        """Initialize version info container.

        Args:
            compiler_version: Compiler version if detected
            cxx_standard: C++ standard version if detected
            features: List of detected features
            source: The source of the version detection
        """
        self.compiler_version = compiler_version
        self.cxx_standard = cxx_standard
        self.features = features or []
        self.source = source
        self.detected_at = datetime.now()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation.

        Returns:
            Dictionary with all version info fields
        """
        return {
            "compiler_version": self.compiler_version,
            "cxx_standard": self.cxx_standard,
            "features": self.features,
            "source": self.source,
            "detected_at": self.detected_at.isoformat(),
        }

    def __str__(self) -> str:
        """String representation of version info.

        Returns:
            Human-readable version info string
        """
        parts = []
        if self.compiler_version:
            parts.append(f"Compiler {self.compiler_version}")
        if self.cxx_standard:
            parts.append(f"C++{self.cxx_standard}")
        if self.features:
            parts.append(f"{len(self.features)} features")

        if parts:
            return f"{', '.join(parts)} (from {self.source})"
        return f"No C/C++ version detected (from {self.source})"

    def __repr__(self) -> str:
        """Developer representation of version info.

        Returns:
            Detailed representation for debugging
        """
        return (
            f"CppVersionInfo(compiler_version='{self.compiler_version}', "
            f"cxx_standard='{self.cxx_standard}', features={self.features}, "
            f"source='{self.source}')"
        )

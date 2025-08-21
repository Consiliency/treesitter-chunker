"""Grammar version analyzer for Phase 1.7."""

import json
import logging
import os
import platform
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .schema import CompatibilityLevel, GrammarVersion, LanguageVersion

logger = logging.getLogger(__name__)


class GrammarAnalyzer:
    """Analyzes compiled grammar files to extract version and capability information."""

    def __init__(self, grammars_dir: Path):
        """Initialize the grammar analyzer.

        Args:
            grammars_dir: Path to directory containing compiled grammar .so files
        """
        self.grammars_dir = Path(grammars_dir)
        self.grammar_cache: dict[str, GrammarVersion] = {}
        self.supported_languages = self._discover_supported_languages()
        self.metadata_extractor = GrammarMetadataExtractor()
        self.feature_detector = FeatureDetector()
        logger.debug(
            f"Initialized GrammarAnalyzer with {len(self.supported_languages)} languages",
        )

    def _discover_supported_languages(self) -> list[str]:
        """Discover all supported languages from grammar directory.

        Returns:
            List of language names (e.g., ['python', 'javascript', 'rust'])
        """
        languages = []

        try:
            if not self.grammars_dir.exists():
                logger.warning(f"Grammar directory does not exist: {self.grammars_dir}")
                return languages

            # Scan for .so files
            for grammar_file in self.grammars_dir.glob("*.so"):
                language = grammar_file.stem
                languages.append(language)
                logger.debug(f"Discovered language: {language}")

            languages.sort()
            logger.info(f"Discovered {len(languages)} supported languages")

        except Exception as e:
            logger.error(f"Error discovering languages: {e}")

        return languages

    def analyze_grammar_file(self, language: str) -> GrammarVersion | None:
        """Analyze a specific grammar file to extract version information.

        Args:
            language: Name of the language to analyze

        Returns:
            GrammarVersion object or None if analysis fails
        """
        try:
            # Check cache first
            if language in self.grammar_cache:
                return self.grammar_cache[language]

            grammar_path = self.grammars_dir / f"{language}.so"
            if not grammar_path.exists():
                logger.warning(f"Grammar file not found: {grammar_path}")
                return None

            # Extract version
            version = self.extract_grammar_version(grammar_path)
            if not version:
                # Use default version if extraction fails
                version = "1.0.0"
                logger.warning(
                    f"Could not extract version for {language}, using default: {version}",
                )

            # Analyze symbols
            symbols = self.analyze_grammar_symbols(grammar_path)

            # Detect features
            features = self.detect_supported_features(language, symbols)

            # Determine language version support
            min_version, max_version = self.determine_language_version_support(
                language,
                version,
            )

            # Create GrammarVersion object
            grammar_version = GrammarVersion(
                language=language,
                version=version,
                grammar_file=str(grammar_path),
                supported_features=features,
                min_language_version=min_version,
                max_language_version=max_version,
                release_date=datetime.fromtimestamp(grammar_path.stat().st_mtime),
            )

            # Cache the result
            self.grammar_cache[language] = grammar_version
            logger.info(f"Analyzed grammar for {language}: version {version}")

            return grammar_version

        except Exception as e:
            logger.error(f"Error analyzing grammar for {language}: {e}")
            return None

    def extract_grammar_version(self, so_file_path: Path) -> str | None:
        """Extract version information from a compiled grammar .so file.

        Args:
            so_file_path: Path to the .so file

        Returns:
            Version string or None if not found
        """
        try:
            # Try multiple extraction methods

            # Method 1: Extract from symbols
            version = self.metadata_extractor.extract_from_symbols(so_file_path).get(
                "version",
            )
            if version:
                return version

            # Method 2: Extract from strings
            version = self.metadata_extractor.extract_from_strings(so_file_path).get(
                "version",
            )
            if version:
                return version

            # Method 3: Extract from headers
            version = self.metadata_extractor.extract_from_headers(so_file_path).get(
                "version",
            )
            if version:
                return version

            # Method 4: Use file modification time as version hint
            mtime = so_file_path.stat().st_mtime
            date_version = datetime.fromtimestamp(mtime).strftime("%Y.%m.%d")
            logger.debug(
                f"Using date-based version for {so_file_path.name}: {date_version}",
            )
            return date_version

        except Exception as e:
            logger.error(f"Error extracting version from {so_file_path}: {e}")
            return None

    def analyze_grammar_symbols(self, so_file_path: Path) -> dict[str, Any]:
        """Analyze symbols in grammar file to understand capabilities.

        Args:
            so_file_path: Path to the .so file

        Returns:
            Dict with symbol information
        """
        symbols = {"functions": [], "constants": [], "data": [], "undefined": []}

        try:
            # Use nm command to list symbols
            if platform.system() == "Windows":
                logger.warning("Symbol analysis not fully supported on Windows")
                return symbols

            result = subprocess.run(
                ["nm", "-D", str(so_file_path)],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )

            if result.returncode != 0:
                # Try without -D flag
                result = subprocess.run(
                    ["nm", str(so_file_path)],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    check=False,
                )

            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    parts = line.split()
                    if len(parts) >= 2:
                        symbol_type = parts[-2] if len(parts) >= 3 else "U"
                        symbol_name = parts[-1]

                        if symbol_type in ["T", "t"]:  # Text (functions)
                            symbols["functions"].append(symbol_name)
                        elif symbol_type in ["D", "d", "B", "b"]:  # Data
                            symbols["data"].append(symbol_name)
                        elif symbol_type in ["R", "r"]:  # Read-only data
                            symbols["constants"].append(symbol_name)
                        elif symbol_type == "U":  # Undefined
                            symbols["undefined"].append(symbol_name)

            logger.debug(
                f"Found {len(symbols['functions'])} functions, "
                f"{len(symbols['data'])} data symbols in {so_file_path.name}",
            )

        except subprocess.TimeoutExpired:
            logger.warning(f"Timeout analyzing symbols in {so_file_path}")
        except FileNotFoundError:
            logger.warning("nm command not found - symbol analysis unavailable")
        except Exception as e:
            logger.error(f"Error analyzing symbols: {e}")

        return symbols

    def detect_supported_features(
        self,
        language: str,
        symbols: dict[str, Any],
    ) -> list[str]:
        """Detect supported language features based on grammar symbols.

        Args:
            language: The language name
            symbols: Symbol information from grammar analysis

        Returns:
            List of supported feature names
        """
        return self.feature_detector.detect_features(language, symbols)

    def determine_language_version_support(
        self,
        language: str,
        grammar_version: str,
    ) -> tuple[str, str]:
        """Determine min/max language versions supported by grammar.

        Args:
            language: The language name
            grammar_version: The grammar version

        Returns:
            Tuple of (min_version, max_version)
        """
        # Default version ranges for known languages
        version_ranges = {
            "python": ("3.6", "3.12"),
            "javascript": ("ES2015", "ES2023"),
            "typescript": ("3.0", "5.0"),
            "rust": ("1.0", "1.75"),
            "go": ("1.11", "1.21"),
            "java": ("8", "21"),
            "cpp": ("11", "23"),
            "c": ("99", "23"),
            "csharp": ("7.0", "12.0"),
            "ruby": ("2.5", "3.3"),
            "php": ("7.0", "8.3"),
            "swift": ("4.0", "5.9"),
            "kotlin": ("1.0", "1.9"),
        }

        if language in version_ranges:
            return version_ranges[language]

        # Default for unknown languages
        return ("1.0", None)

    def analyze_all_grammars(self) -> dict[str, GrammarVersion]:
        """Analyze all available grammar files.

        Returns:
            Dict mapping language to GrammarVersion
        """
        results = {}

        try:
            for language in self.supported_languages:
                grammar_version = self.analyze_grammar_file(language)
                if grammar_version:
                    results[language] = grammar_version

            logger.info(f"Analyzed {len(results)} grammars successfully")

        except Exception as e:
            logger.error(f"Error analyzing all grammars: {e}")

        return results

    def get_grammar_capabilities(self, language: str) -> dict[str, Any]:
        """Get comprehensive capabilities for a specific grammar.

        Args:
            language: The language name

        Returns:
            Dict with grammar capabilities
        """
        capabilities = {
            "language": language,
            "supported": False,
            "version": None,
            "features": [],
            "min_language_version": None,
            "max_language_version": None,
            "symbols_count": 0,
            "file_size": 0,
        }

        try:
            grammar_version = self.analyze_grammar_file(language)
            if grammar_version:
                capabilities["supported"] = True
                capabilities["version"] = grammar_version.version
                capabilities["features"] = grammar_version.supported_features
                capabilities["min_language_version"] = (
                    grammar_version.min_language_version
                )
                capabilities["max_language_version"] = (
                    grammar_version.max_language_version
                )

                # Add file info
                grammar_path = Path(grammar_version.grammar_file)
                if grammar_path.exists():
                    capabilities["file_size"] = grammar_path.stat().st_size

                    # Count symbols
                    symbols = self.analyze_grammar_symbols(grammar_path)
                    capabilities["symbols_count"] = sum(
                        len(v) if isinstance(v, list) else 0 for v in symbols.values()
                    )

            logger.debug(f"Got capabilities for {language}: {capabilities}")

        except Exception as e:
            logger.error(f"Error getting capabilities for {language}: {e}")

        return capabilities

    def validate_grammar_compatibility(
        self,
        language: str,
        target_version: str,
    ) -> CompatibilityLevel:
        """Validate if grammar is compatible with target language version.

        Args:
            language: The language name
            target_version: Target language version to check

        Returns:
            CompatibilityLevel enum value
        """
        try:
            grammar_version = self.analyze_grammar_file(language)
            if not grammar_version:
                return CompatibilityLevel.UNKNOWN

            # Create a LanguageVersion for comparison
            lang_version = LanguageVersion(language=language, version=target_version)

            return grammar_version.get_compatibility_level(lang_version)

        except Exception as e:
            logger.error(f"Error validating compatibility: {e}")
            return CompatibilityLevel.UNKNOWN

    def generate_grammar_report(self, language: str) -> str:
        """Generate human-readable report for grammar analysis.

        Args:
            language: The language name

        Returns:
            Formatted report string
        """
        try:
            capabilities = self.get_grammar_capabilities(language)

            report = []
            report.append(f"Grammar Analysis Report: {language}")
            report.append("=" * 50)

            if capabilities["supported"]:
                report.append("Status: Supported")
                report.append(f"Version: {capabilities['version']}")
                report.append(f"File Size: {capabilities['file_size']:,} bytes")
                report.append(f"Symbols Count: {capabilities['symbols_count']}")
                report.append(
                    f"Language Version Range: {capabilities['min_language_version']} - "
                    f"{capabilities['max_language_version'] or 'latest'}",
                )

                if capabilities["features"]:
                    report.append(
                        f"\nSupported Features ({len(capabilities['features'])}):",
                    )
                    for feature in capabilities["features"]:
                        report.append(f"  - {feature}")
            else:
                report.append("Status: Not Supported")
                report.append("Grammar file not found or could not be analyzed")

            return "\n".join(report)

        except Exception as e:
            logger.error(f"Error generating report for {language}: {e}")
            return f"Error generating report for {language}: {e}"

    def export_analysis_data(self, output_path: Path) -> None:
        """Export analysis data to JSON or other format.

        Args:
            output_path: Path to write the analysis data
        """
        try:
            output_path = Path(output_path)

            # Analyze all grammars
            all_grammars = self.analyze_all_grammars()

            # Convert to exportable format
            export_data = {
                "metadata": {
                    "generated_at": datetime.now().isoformat(),
                    "grammars_dir": str(self.grammars_dir),
                    "total_languages": len(all_grammars),
                },
                "grammars": {},
            }

            for language, grammar_version in all_grammars.items():
                export_data["grammars"][language] = {
                    "version": grammar_version.version,
                    "file": grammar_version.grammar_file,
                    "features": grammar_version.supported_features,
                    "min_language_version": grammar_version.min_language_version,
                    "max_language_version": grammar_version.max_language_version,
                    "capabilities": self.get_grammar_capabilities(language),
                }

            # Write to file
            with open(output_path, "w") as f:
                json.dump(export_data, f, indent=2, default=str)

            logger.info(f"Exported analysis data to {output_path}")

        except Exception as e:
            logger.error(f"Error exporting analysis data: {e}")
            raise


class GrammarMetadataExtractor:
    """Extracts metadata from grammar files using various methods."""

    @staticmethod
    def extract_from_symbols(so_file_path: Path) -> dict[str, Any]:
        """Extract metadata using symbol table analysis.

        Args:
            so_file_path: Path to the .so file

        Returns:
            Dict with symbol metadata
        """
        metadata = {}

        try:
            if platform.system() == "Windows":
                return metadata

            # Look for version symbols
            result = subprocess.run(
                ["nm", "-D", str(so_file_path)],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )

            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    if "version" in line.lower():
                        # Try to extract version number
                        match = re.search(r"(\d+\.\d+\.\d+)", line)
                        if match:
                            metadata["version"] = match.group(1)
                            break
                    elif "tree_sitter" in line.lower():
                        metadata["tree_sitter"] = True

        except Exception as e:
            logger.debug(f"Error extracting from symbols: {e}")

        return metadata

    @staticmethod
    def extract_from_strings(so_file_path: Path) -> dict[str, Any]:
        """Extract metadata using string analysis.

        Args:
            so_file_path: Path to the .so file

        Returns:
            Dict with string metadata
        """
        metadata = {}

        try:
            if platform.system() == "Windows":
                return metadata

            # Use strings command to find version strings
            result = subprocess.run(
                ["strings", str(so_file_path)],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )

            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    # Look for version patterns
                    match = re.search(r"(\d+\.\d+\.\d+)", line)
                    if match and "version" in line.lower():
                        metadata["version"] = match.group(1)
                        break
                    if match and not metadata.get("version"):
                        # Use first version-like string as fallback
                        metadata["version"] = match.group(1)

        except Exception as e:
            logger.debug(f"Error extracting from strings: {e}")

        return metadata

    @staticmethod
    def extract_from_headers(so_file_path: Path) -> dict[str, Any]:
        """Extract metadata from file headers.

        Args:
            so_file_path: Path to the .so file

        Returns:
            Dict with header metadata
        """
        metadata = {}

        try:
            if platform.system() == "Windows":
                return metadata

            # Use file command to get file type info
            result = subprocess.run(
                ["file", str(so_file_path)],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )

            if result.returncode == 0:
                output = result.stdout
                if "ELF" in output:
                    metadata["format"] = "ELF"
                if "64-bit" in output:
                    metadata["arch"] = "64-bit"
                elif "32-bit" in output:
                    metadata["arch"] = "32-bit"

        except Exception as e:
            logger.debug(f"Error extracting from headers: {e}")

        return metadata

    @staticmethod
    def extract_from_dependencies(so_file_path: Path) -> dict[str, Any]:
        """Extract metadata from library dependencies.

        Args:
            so_file_path: Path to the .so file

        Returns:
            Dict with dependency metadata
        """
        metadata = {"dependencies": []}

        try:
            if platform.system() == "Windows":
                return metadata

            # Use ldd to list dependencies
            result = subprocess.run(
                ["ldd", str(so_file_path)],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )

            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    if "=>" in line:
                        lib_name = line.split("=>")[0].strip()
                        metadata["dependencies"].append(lib_name)

        except Exception as e:
            logger.debug(f"Error extracting from dependencies: {e}")

        return metadata


class FeatureDetector:
    """Detects language features based on grammar analysis."""

    def __init__(self):
        """Initialize the feature detector."""
        self.feature_patterns = self._load_feature_patterns()

    def _load_feature_patterns(self) -> dict[str, list[str]]:
        """Load patterns for detecting language features.

        Returns:
            Dict mapping language to feature patterns
        """
        return {
            "python": [
                "async_def",
                "await_expr",
                "f_string",
                "match_statement",
                "walrus_operator",
                "type_hint",
                "decorator",
                "generator",
                "comprehension",
                "context_manager",
            ],
            "javascript": [
                "arrow_function",
                "async_function",
                "class",
                "template_literal",
                "destructuring",
                "spread_operator",
                "optional_chaining",
                "nullish_coalescing",
                "bigint",
                "private_field",
            ],
            "typescript": [
                "type_annotation",
                "interface",
                "enum",
                "generic",
                "decorator",
                "namespace",
                "type_alias",
                "conditional_type",
                "mapped_type",
                "literal_type",
            ],
            "rust": [
                "async_fn",
                "unsafe_block",
                "macro",
                "trait",
                "impl",
                "lifetime",
                "pattern_matching",
                "closure",
                "const_generics",
            ],
            "go": [
                "goroutine",
                "channel",
                "defer",
                "interface",
                "struct",
                "method",
                "type_assertion",
                "type_switch",
                "generics",
            ],
            "java": [
                "lambda",
                "stream",
                "optional",
                "record",
                "sealed_class",
                "pattern_matching",
                "text_block",
                "switch_expression",
                "var_keyword",
                "module",
            ],
            "cpp": [
                "template",
                "lambda",
                "auto",
                "constexpr",
                "concepts",
                "coroutine",
                "module",
                "ranges",
                "spaceship_operator",
            ],
        }

    def detect_features(self, language: str, symbols: dict[str, Any]) -> list[str]:
        """Detect features for a specific language.

        Args:
            language: The language name
            symbols: Symbol information from grammar analysis

        Returns:
            List of detected features
        """
        detected_features = []

        try:
            # Get known features for the language
            known_features = self.feature_patterns.get(language, [])

            # Check symbols for feature indicators
            all_symbols = []
            for symbol_list in symbols.values():
                if isinstance(symbol_list, list):
                    all_symbols.extend(symbol_list)

            # Convert symbols to lowercase for matching
            all_symbols_lower = [s.lower() for s in all_symbols]

            for feature in known_features:
                # Check if feature name appears in symbols
                feature_lower = feature.lower()
                if any(feature_lower in symbol for symbol in all_symbols_lower) or any(
                    feature_lower.replace("_", "") in symbol
                    for symbol in all_symbols_lower
                ):
                    detected_features.append(feature)

            logger.debug(f"Detected {len(detected_features)} features for {language}")

        except Exception as e:
            logger.error(f"Error detecting features for {language}: {e}")

        return detected_features

    def get_feature_compatibility(
        self,
        language: str,
        features: list[str],
    ) -> dict[str, str]:
        """Get version requirements for specific features.

        Args:
            language: The language name
            features: List of features to check

        Returns:
            Dict mapping features to version requirements
        """
        # Feature to minimum version mapping
        feature_versions = {
            "python": {
                "async_def": "3.5",
                "await_expr": "3.5",
                "f_string": "3.6",
                "match_statement": "3.10",
                "walrus_operator": "3.8",
                "type_hint": "3.5",
            },
            "javascript": {
                "arrow_function": "ES2015",
                "async_function": "ES2017",
                "class": "ES2015",
                "optional_chaining": "ES2020",
                "nullish_coalescing": "ES2020",
                "bigint": "ES2020",
            },
            "rust": {
                "async_fn": "1.39",
                "const_generics": "1.51",
                "pattern_matching": "1.0",
            },
            "go": {"generics": "1.18", "goroutine": "1.0", "channel": "1.0"},
        }

        result = {}
        lang_features = feature_versions.get(language, {})

        for feature in features:
            if feature in lang_features:
                result[feature] = lang_features[feature]
            else:
                result[feature] = "unknown"

        return result

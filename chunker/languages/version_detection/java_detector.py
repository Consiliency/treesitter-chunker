"""Java version detection module for Phase 1.7."""

import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class JavaVersionDetector:
    """Detects Java version from pom.xml, build.gradle, and code."""

    def __init__(self):
        self.version_patterns = {
            "java_version": r"<java\.version>(\d+)</java\.version>",
            "maven_compiler_source": r"<maven\.compiler\.source>(\d+)</maven\.compiler\.source>",
            "maven_compiler_target": r"<maven\.compiler\.target>(\d+)</maven\.compiler\.target>",
            "source_compatibility": r'sourceCompatibility\s*=\s*[\'"]?(\d+(?:\.\d+)?)[\'"]?',
            "target_compatibility": r'targetCompatibility\s*=\s*[\'"]?(\d+(?:\.\d+)?)[\'"]?',
            "java_home": r"JAVA_HOME.*[/\\]jdk-?(\d+)",
            "system_property": r'System\.getProperty\("java\.(?:version|specification\.version)"\)',
            "module_info": r"module\s+[\w.]+\s*\{",
            "gradle_java": r"java\s*\{\s*toolchain\s*\{\s*languageVersion\s*=\s*JavaLanguageVersion\.of\((\d+)\)",
        }

        # Map Java versions to release years and features
        self.java_version_map = {
            "1.0": {"year": 1996, "version": "1.0"},
            "1.1": {"year": 1997, "version": "1.1"},
            "1.2": {"year": 1998, "version": "1.2"},
            "1.3": {"year": 2000, "version": "1.3"},
            "1.4": {"year": 2002, "version": "1.4"},
            "1.5": {"year": 2004, "version": "5"},
            "5": {"year": 2004, "version": "5"},
            "1.6": {"year": 2006, "version": "6"},
            "6": {"year": 2006, "version": "6"},
            "1.7": {"year": 2011, "version": "7"},
            "7": {"year": 2011, "version": "7"},
            "1.8": {"year": 2014, "version": "8"},
            "8": {"year": 2014, "version": "8", "lts": True},
            "9": {"year": 2017, "version": "9"},
            "10": {"year": 2018, "version": "10"},
            "11": {"year": 2018, "version": "11", "lts": True},
            "12": {"year": 2019, "version": "12"},
            "13": {"year": 2019, "version": "13"},
            "14": {"year": 2020, "version": "14"},
            "15": {"year": 2020, "version": "15"},
            "16": {"year": 2021, "version": "16"},
            "17": {"year": 2021, "version": "17", "lts": True},
            "18": {"year": 2022, "version": "18"},
            "19": {"year": 2022, "version": "19"},
            "20": {"year": 2023, "version": "20"},
            "21": {"year": 2023, "version": "21", "lts": True},
        }

        # Map features to minimum Java versions
        self.feature_map = {
            "var ": "10",  # Local variable type inference
            "record ": "14",  # Records (preview in 14, stable in 16)
            "sealed ": "15",  # Sealed classes (preview in 15, stable in 17)
            "yield ": "13",  # Switch expressions with yield
            '"""': "15",  # Text blocks
            "->": "8",  # Lambda expressions
            "::": "8",  # Method references
            "Stream<": "8",  # Stream API
            "Optional<": "8",  # Optional
            "CompletableFuture": "8",  # CompletableFuture
            "module ": "9",  # Module system
            "List.of": "9",  # Collection factory methods
            "HttpClient": "11",  # New HTTP client
            "switch.*->": "14",  # Switch expressions
            "Pattern ": "16",  # Pattern matching (preview)
            "instanceof.*&&": "16",  # Pattern matching for instanceof
        }

        logger.debug(
            "Initialized JavaVersionDetector with %d patterns",
            len(self.version_patterns),
        )

    def detect_from_pom_xml(self, content: str) -> str | None:
        """Extract Java version from pom.xml.

        Args:
            content: The file content to search

        Returns:
            Java version like "11" or None if not found
        """
        try:
            # Try to parse as XML
            try:
                root = ET.fromstring(content)
                # Look for properties/java.version
                for prop in root.findall(".//properties/java.version"):
                    if prop.text:
                        version = prop.text.strip()
                        logger.debug("Found java.version in pom.xml: %s", version)
                        return self.normalize_java_version(version)

                # Look for maven.compiler properties
                for prop in root.findall(".//properties/maven.compiler.source"):
                    if prop.text:
                        version = prop.text.strip()
                        logger.debug("Found maven.compiler.source: %s", version)
                        return self.normalize_java_version(version)

                # Look for compiler plugin configuration
                for config in root.findall(
                    './/plugin[artifactId="maven-compiler-plugin"]//configuration',
                ):
                    source = config.find("source")
                    if source is not None and source.text:
                        version = source.text.strip()
                        logger.debug("Found compiler plugin source: %s", version)
                        return self.normalize_java_version(version)

            except ET.ParseError:
                # Fall back to regex parsing
                pass

            # Use regex patterns as fallback
            patterns = [
                r"<java\.version>(\d+(?:\.\d+)?)</java\.version>",
                r"<maven\.compiler\.source>(\d+(?:\.\d+)?)</maven\.compiler\.source>",
                r"<source>(\d+(?:\.\d+)?)</source>",
                r"<target>(\d+(?:\.\d+)?)</target>",
                r"<release>(\d+)</release>",
            ]

            for pattern in patterns:
                match = re.search(pattern, content)
                if match:
                    version = match.group(1)
                    normalized = self.normalize_java_version(version)
                    logger.debug(
                        "Found Java version via regex: %s -> %s",
                        version,
                        normalized,
                    )
                    return normalized

        except Exception as e:
            logger.error("Error detecting from pom.xml: %s", e)

        return None

    def detect_from_maven_compiler(self, content: str) -> str | None:
        """Extract Java version from Maven compiler plugin.

        Args:
            content: The file content to search

        Returns:
            Java version like "11" or None if not found
        """
        try:
            # Look for maven compiler configuration
            patterns = [
                r"<maven\.compiler\.source>(\d+(?:\.\d+)?)</maven\.compiler\.source>",
                r"<maven\.compiler\.target>(\d+(?:\.\d+)?)</maven\.compiler\.target>",
                r"<maven\.compiler\.release>(\d+)</maven\.compiler\.release>",
            ]

            versions = []
            for pattern in patterns:
                match = re.search(pattern, content)
                if match:
                    version = self.normalize_java_version(match.group(1))
                    versions.append(version)

            if versions:
                # Return the highest version
                max_version = max(versions, key=lambda v: int(v) if v.isdigit() else 0)
                logger.debug("Found Maven compiler version: %s", max_version)
                return max_version

        except Exception as e:
            logger.error("Error detecting Maven compiler version: %s", e)

        return None

    def detect_from_gradle(self, content: str) -> str | None:
        """Extract Java version from build.gradle.

        Args:
            content: The file content to search

        Returns:
            Java version like "11" or None if not found
        """
        try:
            # Look for Gradle Java configuration
            patterns = [
                r'sourceCompatibility\s*=\s*[\'"]?(\d+(?:\.\d+)?)[\'"]?',
                r'targetCompatibility\s*=\s*[\'"]?(\d+(?:\.\d+)?)[\'"]?',
                r"JavaVersion\.VERSION_(\d+)(?:_(\d+))?",
                r"languageVersion\s*=\s*JavaLanguageVersion\.of\((\d+)\)",
                r'jvmTarget\s*=\s*[\'"]?(\d+(?:\.\d+)?)[\'"]?',
            ]

            versions = []
            for pattern in patterns:
                matches = re.findall(pattern, content)
                for match in matches:
                    if isinstance(match, tuple):
                        # Handle VERSION_1_8 format
                        if match[1]:
                            version = f"{match[0]}.{match[1]}"
                        else:
                            version = match[0]
                    else:
                        version = match
                    normalized = self.normalize_java_version(version)
                    versions.append(normalized)

            if versions:
                # Return the highest version
                max_version = max(versions, key=lambda v: int(v) if v.isdigit() else 0)
                logger.debug("Found Gradle Java version: %s", max_version)
                return max_version

        except Exception as e:
            logger.error("Error detecting from Gradle: %s", e)

        return None

    def detect_from_system_property(self, content: str) -> str | None:
        """Detect Java version from System.getProperty usage.

        Args:
            content: The file content to search

        Returns:
            Java version or None if not found
        """
        try:
            # Look for System.getProperty calls
            patterns = [
                r'System\.getProperty\("java\.version"\)\s*(?:==|\.startsWith\()\s*"(\d+(?:\.\d+)?)"',
                r'System\.getProperty\("java\.specification\.version"\)\s*(?:==|\.equals\()\s*"(\d+(?:\.\d+)?)"',
                r"Runtime\.version\(\)\.feature\(\)\s*(?:==|>=)\s*(\d+)",
            ]

            for pattern in patterns:
                match = re.search(pattern, content)
                if match:
                    version = self.normalize_java_version(match.group(1))
                    logger.debug("Found System property version check: %s", version)
                    return version

            # Check for general version checks
            if 'System.getProperty("java.version")' in content:
                logger.debug("Found java.version property access")
                # Can't determine specific version, but indicates version awareness

        except Exception as e:
            logger.error("Error detecting System property: %s", e)

        return None

    def detect_from_module_info(self, content: str) -> str | None:
        """Detect Java version from module-info.java.

        Args:
            content: The file content to search

        Returns:
            Java version "9" or higher, or None if not found
        """
        try:
            # module-info.java indicates Java 9+
            if "module " in content and "{" in content:
                # Look for specific module features
                if "requires static" in content:
                    logger.debug("Found module with static requires (Java 9+)")
                    return "9"
                if "requires transitive" in content:
                    logger.debug("Found module with transitive requires (Java 9+)")
                    return "9"
                if "provides " in content and " with " in content:
                    logger.debug("Found module with service provider (Java 9+)")
                    return "9"
                logger.debug("Found basic module declaration (Java 9+)")
                return "9"

        except Exception as e:
            logger.error("Error detecting from module-info: %s", e)

        return None

    def detect_language_features(self, content: str) -> list[str]:
        """Detect Java language features that indicate minimum version.

        Args:
            content: The source code to analyze

        Returns:
            List of detected features with their minimum versions
        """
        features = []
        min_versions = []

        try:
            for feature_pattern, min_version in self.feature_map.items():
                if re.search(feature_pattern, content):
                    features.append(f"{feature_pattern.strip()} (Java {min_version}+)")
                    min_versions.append(min_version)
                    logger.debug(
                        "Detected Java %s feature: %s",
                        min_version,
                        feature_pattern,
                    )

            # Additional feature detection
            # Records (Java 14+, stable in 16)
            if re.search(r"\brecord\s+\w+\s*\([^)]*\)\s*\{", content):
                features.append("records (Java 14+)")
                min_versions.append("14")

            # Sealed classes (Java 15+, stable in 17)
            if re.search(r"\bsealed\s+(class|interface)\s+\w+", content):
                features.append("sealed classes (Java 15+)")
                min_versions.append("15")

            # Pattern matching for switch (Java 17+)
            if re.search(r"switch\s*\([^)]+\)\s*\{[^}]*case\s+\w+\s+\w+\s*->", content):
                features.append("pattern matching switch (Java 17+)")
                min_versions.append("17")

            # Virtual threads (Java 19+, preview)
            if (
                "Thread.startVirtualThread" in content
                or "Executors.newVirtualThreadPerTaskExecutor" in content
            ):
                features.append("virtual threads (Java 19+)")
                min_versions.append("19")

        except Exception as e:
            logger.error("Error detecting language features: %s", e)

        return features

    def parse_version_requirements(self, version_str: str) -> dict[str, str]:
        """Parse Java version requirements and constraints.

        Args:
            version_str: Version string to parse

        Returns:
            Dictionary with version requirements
        """
        requirements = {}

        try:
            # Normalize the version first
            normalized = self.normalize_java_version(version_str)
            requirements["version"] = normalized

            # Check if it's an LTS version
            if normalized in self.java_version_map:
                version_info = self.java_version_map[normalized]
                if version_info.get("lts"):
                    requirements["lts"] = True
                requirements["year"] = version_info["year"]

            # Determine version type
            if normalized.isdigit():
                version_num = int(normalized)
                if version_num >= 9:
                    requirements["type"] = "modern"  # Java 9+
                else:
                    requirements["type"] = "legacy"  # Java 8 and below
            else:
                requirements["type"] = "unknown"

            logger.debug(
                "Parsed version requirements: %s -> %s",
                version_str,
                requirements,
            )

        except Exception as e:
            logger.error("Error parsing version requirements: %s", e)

        return requirements

    def normalize_java_version(self, version: str) -> str:
        """Normalize Java version to standard format.

        Args:
            version: Raw version string

        Returns:
            Normalized version (e.g., "1.8" -> "8")
        """
        try:
            # Remove common prefixes
            version = version.strip()
            version = re.sub(r"^java\s*", "", version, flags=re.IGNORECASE)
            version = re.sub(r"^jdk\s*", "", version, flags=re.IGNORECASE)

            # Handle 1.x format
            if version.startswith("1."):
                # Convert 1.5 -> 5, 1.6 -> 6, etc.
                parts = version.split(".")
                if len(parts) >= 2 and parts[1].isdigit():
                    major = int(parts[1])
                    if major >= 5:
                        return str(major)

            # Extract just the major version
            match = re.match(r"(\d+)", version)
            if match:
                return match.group(1)

            return version

        except Exception as e:
            logger.error("Error normalizing version %s: %s", version, e)
            return version

    def detect_version(
        self,
        content: str,
        file_path: Path | None = None,
    ) -> dict[str, str | None]:
        """Main method to detect Java version from all sources.

        Args:
            content: The file content to analyze
            file_path: Optional path to the file being analyzed

        Returns:
            Dictionary with results from each detection method
        """
        results = {}

        try:
            # Determine file type and apply appropriate detection
            if file_path:
                results["file_path"] = str(file_path)

                if file_path.name == "pom.xml":
                    results["file_type"] = "maven"
                    results["maven_version"] = self.detect_from_pom_xml(content)
                    results["compiler_version"] = self.detect_from_maven_compiler(
                        content,
                    )

                elif file_path.name in ["build.gradle", "build.gradle.kts"]:
                    results["file_type"] = "gradle"
                    results["gradle_version"] = self.detect_from_gradle(content)

                elif file_path.name == "module-info.java":
                    results["file_type"] = "module"
                    results["module_version"] = self.detect_from_module_info(content)

                elif file_path.suffix == ".java":
                    results["file_type"] = "source"

                else:
                    results["file_type"] = "unknown"
            else:
                # No file path, try all methods
                results["maven_version"] = self.detect_from_pom_xml(content)
                results["gradle_version"] = self.detect_from_gradle(content)
                results["module_version"] = self.detect_from_module_info(content)

            # Always check for language features and system properties
            results["system_property"] = self.detect_from_system_property(content)

            features = self.detect_language_features(content)
            if features:
                results["detected_features"] = features
                # Extract minimum versions from features
                min_versions = []
                for feature in features:
                    match = re.search(r"Java (\d+)\+", feature)
                    if match:
                        min_versions.append(match.group(1))
                if min_versions:
                    max_min_version = max(
                        min_versions,
                        key=lambda v: int(v) if v.isdigit() else 0,
                    )
                    results["min_version_from_features"] = max_min_version

            # Parse version requirements for primary version
            primary_version = self.get_primary_version(results)
            if primary_version:
                requirements = self.parse_version_requirements(primary_version)
                results["version_requirements"] = requirements

            logger.info(
                "Version detection complete: %s",
                {
                    k: v
                    for k, v in results.items()
                    if v
                    and k
                    not in ["detected_features", "file_path", "version_requirements"]
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

        Prioritizes: maven_version > gradle_version > compiler_version >
                    system_property > min_version_from_features > module_version

        Args:
            detection_results: Dictionary of detection results

        Returns:
            Most reliable version string or None
        """
        try:
            # Priority order for different sources
            priority_order = [
                "maven_version",
                "gradle_version",
                "compiler_version",
                "system_property",
                "min_version_from_features",
                "module_version",
            ]

            for source in priority_order:
                if detection_results.get(source):
                    version = detection_results[source]
                    logger.debug("Selected primary version %s from %s", version, source)
                    return version

        except Exception as e:
            logger.error("Error determining primary version: %s", e)

        return None


class JavaVersionInfo:
    """Container for Java version information."""

    def __init__(
        self,
        java_version: str | None,
        maven_version: str | None,
        module_system: bool,
        source: str,
    ):
        """Initialize version info container.

        Args:
            java_version: The detected Java version
            maven_version: Maven-specific version if detected
            module_system: Whether module system is used
            source: The source of the version detection
        """
        self.java_version = java_version
        self.maven_version = maven_version
        self.module_system = module_system
        self.source = source
        self.detected_at = datetime.now()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation.

        Returns:
            Dictionary with all version info fields
        """
        return {
            "java_version": self.java_version,
            "maven_version": self.maven_version,
            "module_system": self.module_system,
            "source": self.source,
            "detected_at": self.detected_at.isoformat(),
        }

    def __str__(self) -> str:
        """String representation of version info.

        Returns:
            Human-readable version info string
        """
        parts = []
        if self.java_version:
            parts.append(f"Java {self.java_version}")
        if self.maven_version:
            parts.append(f"Maven {self.maven_version}")
        if self.module_system:
            parts.append("with modules")

        if parts:
            return f"{', '.join(parts)} (from {self.source})"
        return f"No Java version detected (from {self.source})"

    def __repr__(self) -> str:
        """Developer representation of version info.

        Returns:
            Detailed representation for debugging
        """
        return (
            f"JavaVersionInfo(java_version='{self.java_version}', "
            f"maven_version='{self.maven_version}', module_system={self.module_system}, "
            f"source='{self.source}')"
        )

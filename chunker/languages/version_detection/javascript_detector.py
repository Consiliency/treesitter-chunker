"""JavaScript/Node.js version detection module for Phase 1.7."""

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class JavaScriptVersionDetector:
    """Detects JavaScript/Node.js version from multiple sources."""

    def __init__(self):
        self.version_patterns = {
            "engines": r'"engines"\s*:\s*\{[^}]*"node"\s*:\s*"([^"]+)"',
            "process_version": r'process\.version\s*[:=]\s*[\'"]([^\'"]+)[\'"]',
            "es_version": r"//\s*ES(\d{4})|ES(\d{4})\s+features|/\*\s*ES(\d{4})\s*\*/|use\s+ES(\d{4})",
            "typescript": r"//\s*TypeScript\s+(\d+\.\d+\.\d+)|/\*\s*TypeScript\s+(\d+\.\d+\.\d+)\s*\*/",
        }
        logger.debug(
            "Initialized JavaScriptVersionDetector with %d patterns",
            len(self.version_patterns),
        )

    def detect_from_package_json(self, content: str) -> str | None:
        """Extract Node.js version from package.json engines field.

        Args:
            content: The file content to search

        Returns:
            Version constraint like ">=16.0.0" or None if not found
        """
        try:
            # Try to parse as JSON first
            try:
                data = json.loads(content)
                if isinstance(data, dict):
                    engines = data.get("engines", {})
                    if isinstance(engines, dict):
                        node_version = engines.get("node")
                        if node_version:
                            logger.debug(
                                "Found Node.js version in engines: %s",
                                node_version,
                            )
                            return node_version
                        npm_version = engines.get("npm")
                        if npm_version:
                            logger.debug(
                                "Found npm version in engines: %s",
                                npm_version,
                            )
                            # npm version can hint at Node version
            except (json.JSONDecodeError, ValueError):
                # Fall back to regex parsing
                pass

            # Use regex as fallback
            patterns = [
                r'"engines"\s*:\s*\{[^}]*"node"\s*:\s*"([^"]+)"',
                r'"node"\s*:\s*"([^"]+)"',
                r'"nodeVersion"\s*:\s*"([^"]+)"',
            ]

            for pattern in patterns:
                match = re.search(pattern, content)
                if match:
                    version = match.group(1)
                    logger.debug("Found Node.js version via regex: %s", version)
                    return version

        except Exception as e:
            logger.error("Error detecting from package.json: %s", e)

        return None

    def detect_from_process_version(self, content: str) -> str | None:
        """Extract Node.js version from process.version usage.

        Args:
            content: The file content to search

        Returns:
            Version string like "v16.0.0" or None if not found
        """
        try:
            # Look for process.version references
            patterns = [
                r'process\.version\s*[:=]\s*[\'"]([^\'"]+)[\'"]',
                r'process\.version\s*===?\s*[\'"]([^\'"]+)[\'"]',
                r'process\.version\s*!==?\s*[\'"]([^\'"]+)[\'"]',
                r'process\.versions\.node\s*[:=]\s*[\'"]([^\'"]+)[\'"]',
                r"console\.log\([^)]*process\.version[^)]*\)",
            ]

            for pattern in patterns:
                match = re.search(pattern, content)
                if match and match.lastindex:
                    version = match.group(1)
                    logger.debug("Found process.version: %s", version)
                    return version

            # Check for version comparisons
            pattern = r'process\.version\s*[><=]+\s*[\'"]([^\'"]+)[\'"]'
            match = re.search(pattern, content)
            if match:
                version = match.group(1)
                logger.debug("Found process.version comparison: %s", version)
                return version

        except Exception as e:
            logger.error("Error detecting process.version: %s", e)

        return None

    def detect_es_version(self, content: str) -> str | None:
        """Detect ECMAScript version from code comments and features.

        Args:
            content: The file content to search

        Returns:
            ES version like "2015", "2020", "2022" or None if not found
        """
        try:
            # Look for ES version comments
            patterns = [
                r"//\s*ES(\d{4})",
                r"/\*\s*ES(\d{4})\s*\*/",
                r"//\s*ECMAScript\s*(\d{4})",
                r"/\*\s*ECMAScript\s*(\d{4})\s*\*/",
                r'"use\s+strict";\s*//\s*ES(\d+)',
                r"@es(\d{4})",
            ]

            es_versions = []
            for pattern in patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                for match in matches:
                    if match:
                        version = match if isinstance(match, str) else match[0]
                        es_versions.append(version)

            # Detect ES features to infer version
            feature_versions = {
                r"\basync\s+function\b|\bawait\s+": "2017",  # async/await
                r"\bclass\s+\w+\s*\{": "2015",  # classes
                r"=>": "2015",  # arrow functions
                r"`[^`]*\$\{[^}]+\}[^`]*`": "2015",  # template literals
                r"\bconst\s+\w+\s*=|\blet\s+\w+\s*=": "2015",  # const/let
                r"\.\.\.\w+": "2015",  # spread operator
                r"Object\.entries\(": "2017",  # Object.entries
                r"Object\.values\(": "2017",  # Object.values
                r"Array\.prototype\.flat\(": "2019",  # Array.flat
                r"Promise\.allSettled\(": "2020",  # Promise.allSettled
                r"\?\?": "2020",  # nullish coalescing
                r"\?\.": "2020",  # optional chaining
                r"#\w+\s*;": "2022",  # private fields
            }

            detected_features = []
            for pattern, version in feature_versions.items():
                if re.search(pattern, content):
                    detected_features.append(version)
                    logger.debug("Detected ES%s feature: %s", version, pattern)

            # Return the most recent version found
            all_versions = es_versions + detected_features
            if all_versions:
                max_version = max(all_versions)
                logger.debug("Detected ES version: %s", max_version)
                return max_version

        except Exception as e:
            logger.error("Error detecting ES version: %s", e)

        return None

    def detect_typescript_version(self, content: str) -> str | None:
        """Detect TypeScript version from comments and configuration.

        Args:
            content: The file content to search

        Returns:
            TypeScript version like "4.9.0" or None if not found
        """
        try:
            # Look for TypeScript version comments
            patterns = [
                r"//\s*TypeScript\s+(\d+\.\d+(?:\.\d+)?)",
                r"/\*\s*TypeScript\s+(\d+\.\d+(?:\.\d+)?)\s*\*/",
                r"//\s*@ts-version\s+(\d+\.\d+(?:\.\d+)?)",
                r'"typescript"\s*:\s*"[\^~]?(\d+\.\d+(?:\.\d+)?)"',
            ]

            for pattern in patterns:
                match = re.search(pattern, content, re.IGNORECASE)
                if match:
                    version = match.group(1)
                    logger.debug("Found TypeScript version: %s", version)
                    return version

            # Check tsconfig.json patterns
            if "tsconfig" in content.lower() or '"compilerOptions"' in content:
                # Try to parse as JSON
                try:
                    data = json.loads(content)
                    if isinstance(data, dict):
                        compiler_options = data.get("compilerOptions", {})
                        target = compiler_options.get("target")
                        if target:
                            # Map target to minimum TS version
                            target_map = {
                                "ES3": "1.0",
                                "ES5": "1.0",
                                "ES2015": "1.5",
                                "ES2016": "2.0",
                                "ES2017": "2.1",
                                "ES2018": "2.7",
                                "ES2019": "3.2",
                                "ES2020": "3.8",
                                "ES2021": "4.2",
                                "ES2022": "4.6",
                                "ESNext": "4.9",
                            }
                            if target in target_map:
                                version = target_map[target]
                                logger.debug(
                                    "Inferred TypeScript version from target: %s",
                                    version,
                                )
                                return version
                except (json.JSONDecodeError, ValueError):
                    pass

        except Exception as e:
            logger.error("Error detecting TypeScript version: %s", e)

        return None

    def parse_engine_requirements(self, engines_str: str) -> dict[str, str]:
        """Parse engine requirements string into version constraints.

        Args:
            engines_str: Engine requirement string like ">=16.0.0 <18.0.0"

        Returns:
            Dictionary with min, max, exact versions
        """
        requirements = {}

        try:
            # Parse different constraint patterns
            patterns = {
                "exact": r"^(\d+\.\d+\.\d+)$",
                "min": r">=?\s*(\d+\.\d+(?:\.\d+)?)",
                "max": r"<=?\s*(\d+\.\d+(?:\.\d+)?)",
                "caret": r"\^(\d+\.\d+(?:\.\d+)?)",
                "tilde": r"~(\d+\.\d+(?:\.\d+)?)",
                "range": r"(\d+\.\d+(?:\.\d+)?)\s*-\s*(\d+\.\d+(?:\.\d+)?)",
            }

            for constraint_type, pattern in patterns.items():
                match = re.search(pattern, engines_str)
                if match:
                    if constraint_type == "range":
                        requirements["min"] = match.group(1)
                        requirements["max"] = match.group(2)
                    elif constraint_type == "caret":
                        # ^1.2.3 means >=1.2.3 <2.0.0
                        version = match.group(1)
                        requirements["min"] = version
                        major = version.split(".")[0]
                        requirements["max"] = f"{int(major) + 1}.0.0"
                    elif constraint_type == "tilde":
                        # ~1.2.3 means >=1.2.3 <1.3.0
                        version = match.group(1)
                        requirements["min"] = version
                        parts = version.split(".")
                        if len(parts) >= 2:
                            requirements["max"] = f"{parts[0]}.{int(parts[1]) + 1}.0"
                    else:
                        requirements[constraint_type] = match.group(1)

            # Handle multiple constraints
            if "||" in engines_str:
                requirements["alternatives"] = engines_str.split("||")
            elif " " in engines_str and not requirements:
                # Space-separated constraints
                parts = engines_str.split()
                for part in parts:
                    sub_req = self.parse_engine_requirements(part.strip())
                    requirements.update(sub_req)

            logger.debug(
                "Parsed engine requirements: %s -> %s",
                engines_str,
                requirements,
            )

        except Exception as e:
            logger.error("Error parsing engine requirements: %s", e)

        return requirements

    def detect_version(
        self,
        content: str,
        file_path: Path | None = None,
    ) -> dict[str, str | None]:
        """Main method to detect JavaScript version from all sources.

        Args:
            content: The file content to analyze
            file_path: Optional path to the file being analyzed

        Returns:
            Dictionary with results from each detection method
        """
        results = {}

        try:
            # Try all detection methods
            results["node_version"] = self.detect_from_package_json(content)
            results["process_version"] = self.detect_from_process_version(content)
            results["es_version"] = self.detect_es_version(content)
            results["typescript_version"] = self.detect_typescript_version(content)

            # Parse engine requirements if found
            if results["node_version"]:
                requirements = self.parse_engine_requirements(results["node_version"])
                if requirements:
                    results["engine_requirements"] = requirements

            # Add file path context if available
            if file_path:
                results["file_path"] = str(file_path)

                # Check file type
                if file_path.name == "package.json":
                    results["file_type"] = "package"
                elif file_path.name == "tsconfig.json":
                    results["file_type"] = "tsconfig"
                elif file_path.suffix == ".ts":
                    results["file_type"] = "typescript"
                elif file_path.suffix == ".tsx":
                    results["file_type"] = "typescript_jsx"
                elif file_path.suffix in [".js", ".mjs", ".cjs"]:
                    results["file_type"] = "javascript"
                elif file_path.suffix == ".jsx":
                    results["file_type"] = "javascript_jsx"
                else:
                    results["file_type"] = "unknown"

            logger.info(
                "Version detection complete: %s",
                {k: v for k, v in results.items() if v},
            )

        except Exception as e:
            logger.error("Error in version detection: %s", e)

        return results

    def get_primary_version(
        self,
        detection_results: dict[str, str | None],
    ) -> str | None:
        """Determine the primary version from multiple detection results.

        Prioritizes: engines > process.version > ES version > TypeScript version

        Args:
            detection_results: Dictionary of detection results

        Returns:
            Most reliable version string or None
        """
        try:
            # Priority order for different sources
            priority_order = [
                "node_version",
                "process_version",
                "es_version",
                "typescript_version",
            ]

            for source in priority_order:
                if detection_results.get(source):
                    version = detection_results[source]
                    logger.debug("Selected primary version %s from %s", version, source)
                    return version

            # Check engine requirements as fallback
            if "engine_requirements" in detection_results:
                req = detection_results["engine_requirements"]
                if "exact" in req:
                    return req["exact"]
                if "min" in req:
                    return f">={req['min']}"

        except Exception as e:
            logger.error("Error determining primary version: %s", e)

        return None


class JavaScriptVersionInfo:
    """Container for JavaScript version information."""

    def __init__(
        self,
        node_version: str | None,
        es_version: str | None,
        typescript_version: str | None,
        source: str,
    ):
        """Initialize version info container.

        Args:
            node_version: Node.js version if detected
            es_version: ECMAScript version if detected
            typescript_version: TypeScript version if detected
            source: The source of the version detection
        """
        self.node_version = node_version
        self.es_version = es_version
        self.typescript_version = typescript_version
        self.source = source
        self.detected_at = datetime.now()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation.

        Returns:
            Dictionary with all version info fields
        """
        return {
            "node_version": self.node_version,
            "es_version": self.es_version,
            "typescript_version": self.typescript_version,
            "source": self.source,
            "detected_at": self.detected_at.isoformat(),
        }

    def __str__(self) -> str:
        """String representation of version info.

        Returns:
            Human-readable version info string
        """
        parts = []
        if self.node_version:
            parts.append(f"Node.js {self.node_version}")
        if self.es_version:
            parts.append(f"ES{self.es_version}")
        if self.typescript_version:
            parts.append(f"TypeScript {self.typescript_version}")

        if parts:
            return f"{', '.join(parts)} (from {self.source})"
        return f"No version detected (from {self.source})"

    def __repr__(self) -> str:
        """Developer representation of version info.

        Returns:
            Detailed representation for debugging
        """
        return (
            f"JavaScriptVersionInfo(node_version='{self.node_version}', "
            f"es_version='{self.es_version}', typescript_version='{self.typescript_version}', "
            f"source='{self.source}')"
        )

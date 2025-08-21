"""Python version detection module for Phase 1.7."""

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class PythonVersionDetector:
    """Detects Python version from multiple sources in code and configuration."""

    def __init__(self):
        self.version_patterns = {
            "shebang": r"^#!.*python(\d+(?:\.\d+)?)",
            "version_string": r'__version__\s*=\s*[\'"]([^\'"]+)[\'"]',
            "sys_version": r"sys\.version_info(?:\s*\[|\.)((?:major|minor|\d+))",
            "python_version": r'python_version\s*[:=]\s*[\'"]([^\'"]+)[\'"]',
            "python_requires": r'python_requires\s*=\s*[\'"]([^\'"]+)[\'"]',
            "requires_python": r"Requires-Python:\s*([^\n]+)",
            "pyproject_requires": r'requires-python\s*=\s*[\'"]([^\'"]+)[\'"]',
        }
        logger.debug(
            "Initialized PythonVersionDetector with %d patterns",
            len(self.version_patterns),
        )

    def detect_from_shebang(self, content: str) -> str | None:
        """Extract Python version from shebang line.

        Args:
            content: The file content to search

        Returns:
            Version string like "3.9" or None if not found
        """
        try:
            lines = content.split("\n")
            if not lines:
                return None

            first_line = lines[0].strip()
            if not first_line.startswith("#!"):
                return None

            # Match various shebang patterns
            patterns = [
                r"#!/usr/bin/env python(\d+(?:\.\d+)?)",
                r"#!/usr/bin/python(\d+(?:\.\d+)?)",
                r"#!/usr/local/bin/python(\d+(?:\.\d+)?)",
                r"#!.*python(\d+(?:\.\d+)?)",
            ]

            for pattern in patterns:
                match = re.search(pattern, first_line)
                if match:
                    version = match.group(1)
                    logger.debug("Found Python version %s in shebang", version)
                    return version

            # Check for just "python" without version
            if "python3" in first_line:
                logger.debug("Found Python 3 in shebang (no specific version)")
                return "3"
            if "python2" in first_line:
                logger.debug("Found Python 2 in shebang")
                return "2"

        except Exception as e:
            logger.error("Error detecting version from shebang: %s", e)

        return None

    def detect_from_version_string(self, content: str) -> str | None:
        """Extract Python version from __version__ variable.

        Args:
            content: The file content to search

        Returns:
            Version string like "1.2.3" or None if not found
        """
        try:
            # Look for __version__ patterns
            pattern = r'__version__\s*=\s*[\'"]([^\'"]+)[\'"]'
            match = re.search(pattern, content)
            if match:
                version = match.group(1)
                logger.debug("Found version string: %s", version)
                return version

            # Also check for VERSION constant
            pattern = r'VERSION\s*=\s*[\'"]([^\'"]+)[\'"]'
            match = re.search(pattern, content)
            if match:
                version = match.group(1)
                logger.debug("Found VERSION constant: %s", version)
                return version

        except Exception as e:
            logger.error("Error detecting version string: %s", e)

        return None

    def detect_from_sys_version(self, content: str) -> str | None:
        """Extract Python version from sys.version usage.

        Args:
            content: The file content to search

        Returns:
            Version string like "3.9.0" or None if not found
        """
        try:
            # Look for sys.version_info usage
            patterns = [
                r"sys\.version_info\s*>=?\s*\((\d+),\s*(\d+)",
                r"sys\.version_info\[0:2\]\s*==?\s*\((\d+),\s*(\d+)",
                r"sys\.version_info\.major\s*==?\s*(\d+)",
                r"sys\.version_info\.minor\s*==?\s*(\d+)",
            ]

            for pattern in patterns:
                matches = re.findall(pattern, content)
                if matches:
                    if isinstance(matches[0], tuple) and len(matches[0]) >= 2:
                        major, minor = matches[0][:2]
                        version = f"{major}.{minor}"
                        logger.debug("Found sys.version_info: %s", version)
                        return version
                    if matches[0]:
                        # Single version component found
                        logger.debug("Found partial sys.version_info: %s", matches[0])

            # Look for sys.version string
            pattern = r"sys\.version\s*\[?:?(\d+\.\d+(?:\.\d+)?)"
            match = re.search(pattern, content)
            if match:
                version = match.group(1)
                logger.debug("Found sys.version: %s", version)
                return version

        except Exception as e:
            logger.error("Error detecting sys.version: %s", e)

        return None

    def detect_from_requirements(self, content: str) -> str | None:
        """Extract Python version from requirements.txt or setup.py.

        Args:
            content: The file content to search

        Returns:
            Version constraint like ">=3.7" or None if not found
        """
        try:
            # Check setup.py patterns
            patterns = [
                r'python_requires\s*=\s*[\'"]([^\'"]+)[\'"]',
                r"Programming Language :: Python :: (\d+(?:\.\d+)?)",
                r'requires_python\s*=\s*[\'"]([^\'"]+)[\'"]',
            ]

            for pattern in patterns:
                match = re.search(pattern, content)
                if match:
                    version = match.group(1)
                    logger.debug("Found Python requirement: %s", version)
                    return version

            # Check pyproject.toml patterns
            if "pyproject.toml" in str(content)[:100] or "[tool.poetry]" in content:
                pattern = r'python\s*=\s*[\'"]([^\'"]+)[\'"]'
                match = re.search(pattern, content)
                if match:
                    version = match.group(1)
                    logger.debug("Found pyproject.toml Python version: %s", version)
                    return version

            # Check requirements.txt for Python version markers
            pattern = r'python_version\s*[><=]=?\s*[\'"]?(\d+\.\d+)[\'"]?'
            match = re.search(pattern, content)
            if match:
                version = match.group(1)
                logger.debug("Found requirements.txt Python version: %s", version)
                return f">={version}"

        except Exception as e:
            logger.error("Error detecting requirements: %s", e)

        return None

    def normalize_version(self, version: str) -> str:
        """Normalize version string to standard format.

        Args:
            version: Raw version string

        Returns:
            Normalized version string
        """
        if not version:
            return ""

        try:
            # Remove common prefixes
            version = version.strip()
            version = re.sub(r"^v", "", version, flags=re.IGNORECASE)
            version = re.sub(r"^python\s*", "", version, flags=re.IGNORECASE)

            # Handle version constraints
            if any(op in version for op in [">=", "<=", "==", ">", "<", "~=", "^"]):
                # Keep constraint operators
                return version.strip()

            # Handle version ranges
            if "," in version:
                # Return the range as-is
                return version.strip()

            # Parse semantic version
            match = re.match(
                r"(\d+)(?:\.(\d+))?(?:\.(\d+))?(?:([ab]|rc)(\d+))?",
                version,
            )
            if match:
                major = match.group(1)
                minor = match.group(2) or "0"
                patch = match.group(3) or "0"
                prerelease = match.group(4)
                prerelease_num = match.group(5)

                normalized = f"{major}.{minor}.{patch}"
                if prerelease:
                    normalized += f"{prerelease}{prerelease_num}"

                logger.debug("Normalized version %s to %s", version, normalized)
                return normalized

            # Return as-is if can't parse
            return version.strip()

        except Exception as e:
            logger.error("Error normalizing version %s: %s", version, e)
            return version

    def detect_version(
        self,
        content: str,
        file_path: Path | None = None,
    ) -> dict[str, str | None]:
        """Main method to detect Python version from all sources.

        Args:
            content: The file content to analyze
            file_path: Optional path to the file being analyzed

        Returns:
            Dictionary with results from each detection method
        """
        results = {}

        try:
            # Try all detection methods
            results["shebang"] = self.detect_from_shebang(content)
            results["version_string"] = self.detect_from_version_string(content)
            results["sys_version"] = self.detect_from_sys_version(content)
            results["requirements"] = self.detect_from_requirements(content)

            # Normalize all detected versions
            for key, value in results.items():
                if value:
                    results[key] = self.normalize_version(value)

            # Add file path context if available
            if file_path:
                results["file_path"] = str(file_path)

                # Check file name for hints
                if file_path.name == "setup.py":
                    results["file_type"] = "setup"
                elif file_path.name == "pyproject.toml":
                    results["file_type"] = "pyproject"
                elif file_path.name == "requirements.txt":
                    results["file_type"] = "requirements"
                else:
                    results["file_type"] = "source"

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

        Prioritizes: shebang > requirements > sys_version > version_string

        Args:
            detection_results: Dictionary of detection results

        Returns:
            Most reliable version string or None
        """
        try:
            # Priority order for different sources
            priority_order = [
                "shebang",
                "requirements",
                "sys_version",
                "version_string",
            ]

            for source in priority_order:
                if detection_results.get(source):
                    version = detection_results[source]
                    logger.debug("Selected primary version %s from %s", version, source)
                    return version

            # If no prioritized source, check any available
            for source, version in detection_results.items():
                if version and source not in ["file_path", "file_type"]:
                    logger.debug(
                        "Selected version %s from %s (fallback)",
                        version,
                        source,
                    )
                    return version

        except Exception as e:
            logger.error("Error determining primary version: %s", e)

        return None


class PythonVersionInfo:
    """Container for Python version information."""

    def __init__(self, version: str, source: str, confidence: float):
        """Initialize version info container.

        Args:
            version: The detected version string
            source: The source of the version detection
            confidence: Confidence score (0.0 to 1.0)
        """
        self.version = version
        self.source = source
        self.confidence = confidence
        self.detected_at = datetime.now()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation.

        Returns:
            Dictionary with all version info fields
        """
        return {
            "version": self.version,
            "source": self.source,
            "confidence": self.confidence,
            "detected_at": self.detected_at.isoformat(),
        }

    def __str__(self) -> str:
        """String representation of version info.

        Returns:
            Human-readable version info string
        """
        return f"Python {self.version} (from {self.source}, confidence: {self.confidence:.0%})"

    def __repr__(self) -> str:
        """Developer representation of version info.

        Returns:
            Detailed representation for debugging
        """
        return f"PythonVersionInfo(version='{self.version}', source='{self.source}', confidence={self.confidence})"

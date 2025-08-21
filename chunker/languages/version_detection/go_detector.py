"""Go version detection module for Phase 1.7."""

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class GoVersionDetector:
    """Detects Go version from go.mod and code."""

    def __init__(self):
        self.version_patterns = {
            "go_version": r"^\s*go\s+(\d+\.\d+(?:\.\d+)?)",
            "runtime_version": r"runtime\.Version\(\)",
            "build_constraints": r"//\s*\+build\s+go(\d+)\.(\d+)",
            "go_build_tags": r"//go:build\s+go(\d+)\.(\d+)",
            "toolchain": r"^\s*toolchain\s+go(\d+\.\d+(?:\.\d+)?)",
            "min_version": r"//\s*requires\s+go\s*(\d+\.\d+(?:\.\d+)?)",
        }

        # Map Go versions to features
        self.version_features = {
            "1.11": ["modules"],
            "1.13": ["error_wrapping", "number_literals"],
            "1.14": ["vendoring_improvements", "test_cleanup"],
            "1.15": ["module_improvements"],
            "1.16": ["embed", "io_fs"],
            "1.17": ["type_params_preview", "pruned_modules"],
            "1.18": ["generics", "fuzzing", "workspaces"],
            "1.19": ["atomic_types", "revised_memory_model"],
            "1.20": ["comparable_constraint", "slice_to_array"],
            "1.21": ["min_max_clear", "slog"],
            "1.22": ["range_over_int", "http_routing"],
        }

        logger.debug(
            "Initialized GoVersionDetector with %d patterns",
            len(self.version_patterns),
        )

    def detect_from_go_mod(self, content: str) -> str | None:
        """Extract Go version from go.mod file.

        Args:
            content: The file content to search

        Returns:
            Version string like "1.19" or None if not found
        """
        try:
            # Look for go directive
            pattern = r"^\s*go\s+(\d+\.\d+(?:\.\d+)?)"
            match = re.search(pattern, content, re.MULTILINE)
            if match:
                version = match.group(1)
                # Normalize to major.minor format
                parts = version.split(".")
                if len(parts) >= 2:
                    version = f"{parts[0]}.{parts[1]}"
                logger.debug("Found Go version in go.mod: %s", version)
                return version

            # Look for toolchain directive (Go 1.21+)
            pattern = r"^\s*toolchain\s+go(\d+\.\d+(?:\.\d+)?)"
            match = re.search(pattern, content, re.MULTILINE)
            if match:
                version = match.group(1)
                parts = version.split(".")
                if len(parts) >= 2:
                    version = f"{parts[0]}.{parts[1]}"
                logger.debug("Found Go toolchain version: %s", version)
                return version

            # Look in replace directives for version hints
            pattern = r"replace\s+.*//\s*go(\d+\.\d+)"
            match = re.search(pattern, content)
            if match:
                version = match.group(1)
                logger.debug("Found Go version hint in replace: %s", version)
                return version

        except Exception as e:
            logger.error("Error detecting from go.mod: %s", e)

        return None

    def detect_from_build_constraints(self, content: str) -> str | None:
        """Extract Go version from build constraints.

        Args:
            content: The file content to search

        Returns:
            Version string like "1.19" or None if not found
        """
        try:
            # Check new style build constraints (//go:build)
            pattern = r"//go:build\s+.*go(\d+)\.(\d+)"
            matches = re.findall(pattern, content)
            if matches:
                # Get the highest version from constraints
                versions = [f"{major}.{minor}" for major, minor in matches]
                max_version = max(versions)
                logger.debug("Found go:build constraint: %s", max_version)
                return max_version

            # Check old style build constraints (// +build)
            pattern = r"//\s*\+build\s+.*go(\d+)\.(\d+)"
            matches = re.findall(pattern, content)
            if matches:
                versions = [f"{major}.{minor}" for major, minor in matches]
                max_version = max(versions)
                logger.debug("Found +build constraint: %s", max_version)
                return max_version

            # Check for negated constraints
            pattern = r"//\s*\+build\s+!go(\d+)\.(\d+)"
            matches = re.findall(pattern, content)
            if matches:
                # Negated means requires version after this
                versions = [
                    f"{int(major)}.{int(minor) + 1}" for major, minor in matches
                ]
                if versions:
                    min_version = min(versions)
                    logger.debug(
                        "Found negated build constraint implying: %s",
                        min_version,
                    )
                    return min_version

        except Exception as e:
            logger.error("Error detecting build constraints: %s", e)

        return None

    def detect_from_runtime_version(self, content: str) -> str | None:
        """Detect Go version from runtime.Version() usage.

        Args:
            content: The file content to search

        Returns:
            Version string like "go1.19" or None if not found
        """
        try:
            # Look for runtime.Version() calls
            if "runtime.Version()" in content:
                logger.debug("Found runtime.Version() call")

                # Check for version comparisons
                patterns = [
                    r'runtime\.Version\(\)\s*==\s*"go(\d+\.\d+(?:\.\d+)?)"',
                    r'strings\.HasPrefix\(runtime\.Version\(\),\s*"go(\d+\.\d+)"',
                    r'runtime\.Version\(\)\[2:\]\s*==\s*"(\d+\.\d+)"',
                ]

                for pattern in patterns:
                    match = re.search(pattern, content)
                    if match:
                        version = match.group(1)
                        logger.debug("Found runtime version check: %s", version)
                        return version

            # Look for debug.ReadBuildInfo
            if "debug.ReadBuildInfo" in content:
                logger.debug("Found debug.ReadBuildInfo usage")
                # This suggests Go 1.18+ for module build info
                return "1.18"

            # Look for build info comments
            pattern = r"//\s*Built with go(\d+\.\d+(?:\.\d+)?)"
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                version = match.group(1)
                logger.debug("Found build info comment: %s", version)
                return version

        except Exception as e:
            logger.error("Error detecting runtime version: %s", e)

        return None

    def parse_version_constraints(self, version_str: str) -> dict[str, str]:
        """Parse Go version constraints and requirements.

        Args:
            version_str: Version string with possible constraints

        Returns:
            Dictionary with version requirements
        """
        constraints = {}

        try:
            # Handle simple version
            if re.match(r"^\d+\.\d+(?:\.\d+)?$", version_str):
                constraints["exact"] = version_str
                constraints["min"] = version_str

            # Handle >= constraint
            elif version_str.startswith(">="):
                version = version_str[2:].strip()
                constraints["min"] = version

            # Handle > constraint
            elif version_str.startswith(">"):
                version = version_str[1:].strip()
                parts = version.split(".")
                if len(parts) >= 2:
                    minor = int(parts[1]) + 1
                    constraints["min"] = f"{parts[0]}.{minor}"

            # Handle <= constraint
            elif version_str.startswith("<="):
                version = version_str[2:].strip()
                constraints["max"] = version

            # Handle < constraint
            elif version_str.startswith("<"):
                version = version_str[1:].strip()
                constraints["max"] = version

            # Handle range (e.g., "1.18 || 1.19")
            elif "||" in version_str:
                versions = [v.strip() for v in version_str.split("||")]
                constraints["alternatives"] = versions

            logger.debug(
                "Parsed version constraints: %s -> %s",
                version_str,
                constraints,
            )

        except Exception as e:
            logger.error("Error parsing version constraints: %s", e)

        return constraints

    def detect_language_features(self, content: str) -> list[str]:
        """Detect Go language features that indicate minimum version.

        Args:
            content: The source code to analyze

        Returns:
            List of detected features
        """
        features = []

        try:
            # Check for generics (Go 1.18+)
            if re.search(r"func\s+\w+\[[^\]]+\]\s*\(|\type\s+\w+\[[^\]]+\]", content):
                features.append("generics")
                logger.debug("Detected generics feature")

            # Check for embed directive (Go 1.16+)
            if re.search(r"//go:embed\s+", content):
                features.append("embed")
                logger.debug("Detected embed feature")

            # Check for io/fs usage (Go 1.16+)
            if re.search(r"io/fs|embed\.FS", content):
                features.append("io_fs")
                logger.debug("Detected io/fs feature")

            # Check for errors.Is/As (Go 1.13+)
            if re.search(r"errors\.(Is|As)\(", content):
                features.append("error_wrapping")
                logger.debug("Detected error wrapping feature")

            # Check for number literals (Go 1.13+)
            if re.search(r"\b0b[01]+|0o[0-7]+|\d+_\d+", content):
                features.append("number_literals")
                logger.debug("Detected number literals feature")

            # Check for type parameters (Go 1.18+)
            if re.search(r"type\s+\w+\[.*\s+any\s*\]|comparable\s*\]", content):
                features.append("type_params")
                logger.debug("Detected type parameters")

            # Check for fuzzing (Go 1.18+)
            if re.search(r"func\s+Fuzz\w+\(.*\*testing\.F\)", content):
                features.append("fuzzing")
                logger.debug("Detected fuzzing support")

            # Check for min/max/clear (Go 1.21+)
            if re.search(r"\b(min|max|clear)\(", content):
                features.append("min_max_clear")
                logger.debug("Detected min/max/clear builtins")

            # Check for slog (Go 1.21+)
            if re.search(r"log/slog|slog\.\w+", content):
                features.append("slog")
                logger.debug("Detected slog package")

            # Check for range over int (Go 1.22+)
            if re.search(r"for\s+\w+\s*:=\s*range\s+\d+", content):
                features.append("range_over_int")
                logger.debug("Detected range over int")

        except Exception as e:
            logger.error("Error detecting language features: %s", e)

        return features

    def detect_version(
        self,
        content: str,
        file_path: Path | None = None,
    ) -> dict[str, str | None]:
        """Main method to detect Go version from all sources.

        Args:
            content: The file content to analyze
            file_path: Optional path to the file being analyzed

        Returns:
            Dictionary with results from each detection method
        """
        results = {}

        try:
            # Try all detection methods
            results["go_mod_version"] = self.detect_from_go_mod(content)
            results["build_constraints"] = self.detect_from_build_constraints(content)
            results["runtime_version"] = self.detect_from_runtime_version(content)

            # Detect language features
            features = self.detect_language_features(content)
            if features:
                results["detected_features"] = features

                # Map features to minimum version
                min_versions = []
                for version, version_features in self.version_features.items():
                    for feature in features:
                        if feature in version_features:
                            min_versions.append(version)

                if min_versions:
                    max_min_version = max(min_versions)
                    results["min_version_from_features"] = max_min_version

            # Parse version constraints if found
            if results["go_mod_version"]:
                constraints = self.parse_version_constraints(results["go_mod_version"])
                if constraints:
                    results["version_constraints"] = constraints

            # Add file path context if available
            if file_path:
                results["file_path"] = str(file_path)

                # Check file type
                if file_path.name == "go.mod":
                    results["file_type"] = "module"
                elif file_path.name == "go.sum":
                    results["file_type"] = "checksum"
                elif file_path.suffix == ".go":
                    results["file_type"] = "source"
                    # Check if it's a test file
                    if "_test.go" in file_path.name:
                        results["file_type"] = "test"
                else:
                    results["file_type"] = "unknown"

            logger.info(
                "Version detection complete: %s",
                {k: v for k, v in results.items() if v and k != "version_constraints"},
            )

        except Exception as e:
            logger.error("Error in version detection: %s", e)

        return results

    def get_primary_version(
        self,
        detection_results: dict[str, str | None],
    ) -> str | None:
        """Determine the primary version from multiple detection results.

        Prioritizes: go.mod > build constraints > runtime version > features

        Args:
            detection_results: Dictionary of detection results

        Returns:
            Most reliable version string or None
        """
        try:
            # Priority order for different sources
            priority_order = [
                "go_mod_version",
                "build_constraints",
                "runtime_version",
                "min_version_from_features",
            ]

            for source in priority_order:
                if detection_results.get(source):
                    version = detection_results[source]
                    # Normalize go prefix if present
                    if version.startswith("go"):
                        version = version[2:]
                    logger.debug("Selected primary version %s from %s", version, source)
                    return version

            # Check version constraints as fallback
            if "version_constraints" in detection_results:
                constraints = detection_results["version_constraints"]
                if "exact" in constraints:
                    return constraints["exact"]
                if "min" in constraints:
                    return constraints["min"]

        except Exception as e:
            logger.error("Error determining primary version: %s", e)

        return None


class GoVersionInfo:
    """Container for Go version information."""

    def __init__(
        self,
        go_version: str | None,
        build_constraints: list[str],
        source: str,
    ):
        """Initialize version info container.

        Args:
            go_version: The detected Go version
            build_constraints: List of build constraints found
            source: The source of the version detection
        """
        self.go_version = go_version
        self.build_constraints = build_constraints or []
        self.source = source
        self.detected_at = datetime.now()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation.

        Returns:
            Dictionary with all version info fields
        """
        return {
            "go_version": self.go_version,
            "build_constraints": self.build_constraints,
            "source": self.source,
            "detected_at": self.detected_at.isoformat(),
        }

    def __str__(self) -> str:
        """String representation of version info.

        Returns:
            Human-readable version info string
        """
        parts = []
        if self.go_version:
            parts.append(f"Go {self.go_version}")
        if self.build_constraints:
            parts.append(f"{len(self.build_constraints)} constraints")

        if parts:
            return f"{', '.join(parts)} (from {self.source})"
        return f"No Go version detected (from {self.source})"

    def __repr__(self) -> str:
        """Developer representation of version info.

        Returns:
            Detailed representation for debugging
        """
        return (
            f"GoVersionInfo(go_version='{self.go_version}', "
            f"build_constraints={self.build_constraints}, source='{self.source}')"
        )

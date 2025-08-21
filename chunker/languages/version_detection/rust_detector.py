"""Rust version detection module for Phase 1.7."""

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class RustVersionDetector:
    """Detects Rust version from Cargo.toml and code."""

    def __init__(self):
        self.version_patterns = {
            "edition": r'edition\s*=\s*["\'](\d{4})["\']',
            "rustc_version": r"//\s*rustc\s+(\d+\.\d+(?:\.\d+)?)",
            "feature_flags": r"#\[feature\(([^)]+)\)\]",
            "cargo_version": r"cargo\s+(\d+\.\d+(?:\.\d+)?)",
            "rust_version": r'rust-version\s*=\s*["\']([^"\']+)["\']',
            "minimum_version": r"//\s*min\s+rust:\s*(\d+\.\d+(?:\.\d+)?)",
        }

        # Map editions to minimum Rust versions
        self.edition_map = {
            "2015": "1.0.0",
            "2018": "1.31.0",
            "2021": "1.56.0",
            "2024": "1.80.0",  # Future edition
        }

        # Map features to minimum Rust versions
        self.feature_map = {
            "const_fn": "1.31.0",
            "async_await": "1.39.0",
            "const_generics": "1.51.0",
            "const_generics_defaults": "1.59.0",
            "generic_associated_types": "1.65.0",
            "let_chains": "1.64.0",
            "if_let_guard": "1.65.0",
            "const_trait_impl": "1.61.0",
        }

        logger.debug(
            "Initialized RustVersionDetector with %d patterns",
            len(self.version_patterns),
        )

    def detect_from_cargo_toml(self, content: str) -> str | None:
        """Extract Rust edition from Cargo.toml.

        Args:
            content: The file content to search

        Returns:
            Edition year like "2021" or None if not found
        """
        try:
            # Look for edition field
            pattern = r'edition\s*=\s*["\'](\d{4})["\']'
            match = re.search(pattern, content)
            if match:
                edition = match.group(1)
                logger.debug("Found Rust edition: %s", edition)
                return edition

            # Look for rust-version field (MSRV)
            pattern = r'rust-version\s*=\s*["\']([^"\']+)["\']'
            match = re.search(pattern, content)
            if match:
                version = match.group(1)
                logger.debug("Found rust-version (MSRV): %s", version)
                # Map version to edition
                if version:
                    v_parts = version.split(".")
                    if len(v_parts) >= 2:
                        major = int(v_parts[0])
                        minor = int(v_parts[1])
                        if major == 1:
                            if minor >= 56:
                                return "2021"
                            if minor >= 31:
                                return "2018"
                            return "2015"

            # Look for package.edition in workspace
            pattern = r'\[package\][^[]*edition\s*=\s*["\'](\d{4})["\']'
            match = re.search(pattern, content, re.DOTALL)
            if match:
                edition = match.group(1)
                logger.debug("Found package edition: %s", edition)
                return edition

        except Exception as e:
            logger.error("Error detecting from Cargo.toml: %s", e)

        return None

    def detect_from_rustc_comments(self, content: str) -> str | None:
        """Extract rustc version from code comments.

        Args:
            content: The file content to search

        Returns:
            Version string like "1.70.0" or None if not found
        """
        try:
            # Look for rustc version comments
            patterns = [
                r"//\s*rustc\s+(\d+\.\d+(?:\.\d+)?)",
                r"/\*\s*rustc\s+(\d+\.\d+(?:\.\d+)?)\s*\*/",
                r"//\s*Rust\s+(\d+\.\d+(?:\.\d+)?)",
                r"//\s*minimum\s+rust:\s*(\d+\.\d+(?:\.\d+)?)",
                r"//\s*MSRV:\s*(\d+\.\d+(?:\.\d+)?)",
                r'#\[doc\s*=\s*".*rust\s+(\d+\.\d+(?:\.\d+)?)',
            ]

            for pattern in patterns:
                match = re.search(pattern, content, re.IGNORECASE)
                if match:
                    version = match.group(1)
                    logger.debug("Found rustc version in comment: %s", version)
                    return version

            # Check for version in build.rs comments
            if "build.rs" in str(content)[:100] or "fn main()" in content:
                pattern = r'println!\("cargo:rustc-version=(\d+\.\d+(?:\.\d+)?)\"\)'
                match = re.search(pattern, content)
                if match:
                    version = match.group(1)
                    logger.debug("Found rustc version in build.rs: %s", version)
                    return version

        except Exception as e:
            logger.error("Error detecting rustc version: %s", e)

        return None

    def detect_edition_features(self, content: str) -> list[str]:
        """Detect Rust edition-specific features used in code.

        Args:
            content: The file content to search

        Returns:
            List of required edition features
        """
        features = []

        try:
            # Check for async/await (2018 edition)
            if re.search(r"\basync\s+fn\b|\bawait\b", content):
                features.append("async_await")
                logger.debug("Detected async/await feature")

            # Check for const generics (2021 edition)
            if re.search(r"const\s+\w+:\s*\w+\s*[,>]", content):
                features.append("const_generics")
                logger.debug("Detected const generics feature")

            # Check for let-else (2021 edition)
            if re.search(r"\blet\s+.*\s+else\s*\{", content):
                features.append("let_else")
                logger.debug("Detected let-else feature")

            # Check for format args capture (2021 edition)
            if re.search(r"format!\([^)]*\{[^:}]+\}", content):
                features.append("format_args_capture")
                logger.debug("Detected format args capture")

            # Check for or patterns (2021 edition)
            if re.search(r"match.*\{[^}]*\|[^}]*=>", content, re.DOTALL):
                features.append("or_patterns")
                logger.debug("Detected or patterns")

            # Check for feature attributes
            pattern = r"#!\[feature\(([^)]+)\)\]"
            matches = re.findall(pattern, content)
            for match in matches:
                feature_list = [f.strip() for f in match.split(",")]
                features.extend(feature_list)
                logger.debug("Detected feature flags: %s", feature_list)

            # Check for cfg attributes
            pattern = r'#\[cfg\(.*min_rust_version\s*=\s*"([^"]+)"\)'
            match = re.search(pattern, content)
            if match:
                version = match.group(1)
                features.append(f"min_version_{version}")
                logger.debug("Detected min version cfg: %s", version)

        except Exception as e:
            logger.error("Error detecting edition features: %s", e)

        return features

    def parse_edition_requirements(self, edition: str) -> dict[str, Any]:
        """Parse edition requirements and capabilities.

        Args:
            edition: The Rust edition year

        Returns:
            Dictionary with edition capabilities
        """
        capabilities = {
            "edition": edition,
            "min_rust_version": self.edition_map.get(edition, "1.0.0"),
            "features": [],
        }

        try:
            if edition == "2015":
                capabilities["features"] = [
                    "lifetimes",
                    "traits",
                    "generics",
                    "macros",
                    "pattern_matching",
                ]
            elif edition == "2018":
                capabilities["features"] = [
                    "non_lexical_lifetimes",
                    "impl_trait",
                    "dyn_trait",
                    "async_await",
                    "try_operator",
                    "module_path_clarity",
                ]
            elif edition == "2021":
                capabilities["features"] = [
                    "disjoint_captures",
                    "format_args_capture",
                    "const_generics",
                    "or_patterns",
                    "let_else",
                    "named_lifetimes",
                ]

            # Add common capabilities
            capabilities["stability"] = (
                "stable" if edition in ["2015", "2018", "2021"] else "preview"
            )
            capabilities["async_support"] = edition in ["2018", "2021"]
            capabilities["const_generics_support"] = edition == "2021"

            logger.debug("Parsed edition %s requirements: %s", edition, capabilities)

        except Exception as e:
            logger.error("Error parsing edition requirements: %s", e)

        return capabilities

    def detect_version(
        self,
        content: str,
        file_path: Path | None = None,
    ) -> dict[str, str | None]:
        """Main method to detect Rust version from all sources.

        Args:
            content: The file content to analyze
            file_path: Optional path to the file being analyzed

        Returns:
            Dictionary with results from each detection method
        """
        results = {}

        try:
            # Try all detection methods
            results["edition"] = self.detect_from_cargo_toml(content)
            results["rustc_version"] = self.detect_from_rustc_comments(content)

            # Detect features
            features = self.detect_edition_features(content)
            if features:
                results["detected_features"] = features

                # Determine minimum version from features
                min_versions = []
                for feature in features:
                    if feature in self.feature_map:
                        min_versions.append(self.feature_map[feature])

                if min_versions:
                    # Get the highest minimum version
                    max_min_version = max(min_versions)
                    results["min_version_from_features"] = max_min_version

            # Parse edition requirements if found
            if results["edition"]:
                requirements = self.parse_edition_requirements(results["edition"])
                results["edition_capabilities"] = requirements

            # Check for rust-version field
            pattern = r'rust-version\s*=\s*["\']([^"\']+)["\']'
            match = re.search(pattern, content)
            if match:
                results["rust_version"] = match.group(1)

            # Add file path context if available
            if file_path:
                results["file_path"] = str(file_path)

                # Check file type
                if file_path.name == "Cargo.toml":
                    results["file_type"] = "cargo"
                elif file_path.name == "build.rs":
                    results["file_type"] = "build"
                elif file_path.suffix == ".rs":
                    results["file_type"] = "source"
                else:
                    results["file_type"] = "unknown"

            logger.info(
                "Version detection complete: %s",
                {k: v for k, v in results.items() if v and k != "edition_capabilities"},
            )

        except Exception as e:
            logger.error("Error in version detection: %s", e)

        return results

    def get_primary_version(
        self,
        detection_results: dict[str, str | None],
    ) -> str | None:
        """Determine the primary version from multiple detection results.

        Prioritizes: rust_version > rustc_version > edition > feature analysis

        Args:
            detection_results: Dictionary of detection results

        Returns:
            Most reliable version string or None
        """
        try:
            # Check for explicit rust-version first
            if detection_results.get("rust_version"):
                version = detection_results["rust_version"]
                logger.debug("Selected rust-version: %s", version)
                return version

            # Then rustc version
            if detection_results.get("rustc_version"):
                version = detection_results["rustc_version"]
                logger.debug("Selected rustc version: %s", version)
                return version

            # Then edition with mapping
            if detection_results.get("edition"):
                edition = detection_results["edition"]
                if edition in self.edition_map:
                    version = self.edition_map[edition]
                    logger.debug(
                        "Selected version from edition %s: %s",
                        edition,
                        version,
                    )
                    return version

            # Then feature analysis
            if "min_version_from_features" in detection_results:
                version = detection_results["min_version_from_features"]
                logger.debug("Selected version from features: %s", version)
                return version

        except Exception as e:
            logger.error("Error determining primary version: %s", e)

        return None


class RustVersionInfo:
    """Container for Rust version information."""

    def __init__(
        self,
        edition: str | None,
        rustc_version: str | None,
        features: list[str],
        source: str,
    ):
        """Initialize version info container.

        Args:
            edition: Rust edition (2015, 2018, 2021)
            rustc_version: Rust compiler version
            features: List of detected features
            source: The source of the version detection
        """
        self.edition = edition
        self.rustc_version = rustc_version
        self.features = features or []
        self.source = source
        self.detected_at = datetime.now()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation.

        Returns:
            Dictionary with all version info fields
        """
        return {
            "edition": self.edition,
            "rustc_version": self.rustc_version,
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
        if self.edition:
            parts.append(f"Edition {self.edition}")
        if self.rustc_version:
            parts.append(f"rustc {self.rustc_version}")
        if self.features:
            parts.append(f"{len(self.features)} features")

        if parts:
            return f"Rust {', '.join(parts)} (from {self.source})"
        return f"No Rust version detected (from {self.source})"

    def __repr__(self) -> str:
        """Developer representation of version info.

        Returns:
            Detailed representation for debugging
        """
        return (
            f"RustVersionInfo(edition='{self.edition}', rustc_version='{self.rustc_version}', "
            f"features={self.features}, source='{self.source}')"
        )

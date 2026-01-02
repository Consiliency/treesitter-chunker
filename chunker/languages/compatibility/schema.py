"""Compatibility database schema for Phase 1.7."""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


class CompatibilityLevel(Enum):
    """Compatibility levels for language-grammar pairs."""

    FULLY_COMPATIBLE = "fully_compatible"
    MOSTLY_COMPATIBLE = "mostly_compatible"
    PARTIALLY_COMPATIBLE = "partially_compatible"
    INCOMPATIBLE = "incompatible"
    UNKNOWN = "unknown"


class VersionConstraint(Enum):
    """Types of version constraints."""

    EXACT = "exact"
    MINIMUM = "minimum"
    MAXIMUM = "maximum"
    RANGE = "range"
    WILDCARD = "wildcard"


@dataclass
class LanguageVersion:
    """Represents a specific language version."""

    language: str
    version: str
    edition: str | None = None  # For languages like Rust
    build: str | None = None  # For languages like Go
    features: list[str] = field(default_factory=list)
    release_date: datetime | None = None
    end_of_life: datetime | None = None

    def __post_init__(self):
        """Validate language version data."""
        if not self.language or not self.version:
            raise ValueError("Language and version are required")

        # Normalize language name
        self.language = self.language.lower().strip()

        # Validate version format
        if not re.match(r"^\d+(\.\d+)*([a-zA-Z]\d*)?$", self.version):
            logger.warning(f"Unusual version format: {self.version}")

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "language": self.language,
            "version": self.version,
            "edition": self.edition,
            "build": self.build,
            "features": self.features,
            "release_date": (
                self.release_date.isoformat() if self.release_date else None
            ),
            "end_of_life": self.end_of_life.isoformat() if self.end_of_life else None,
        }

    def __str__(self) -> str:
        """String representation of language version."""
        result = f"{self.language} {self.version}"
        if self.edition:
            result += f" (edition {self.edition})"
        if self.build:
            result += f" [build {self.build}]"
        return result

    def is_compatible_with(self, other: "LanguageVersion") -> bool:
        """Check if this version is compatible with another."""
        if self.language != other.language:
            return False

        # Parse versions for comparison
        self_parts = self.get_major_minor()
        other_parts = other.get_major_minor()

        if not self_parts or not other_parts:
            return False

        # Check major version compatibility
        if self_parts[0] != other_parts[0]:
            return False

        # Minor version backward compatibility
        if len(self_parts) > 1 and len(other_parts) > 1:
            if self_parts[1] < other_parts[1]:
                return False

        return True

    def get_major_minor(self) -> tuple:
        """Extract major.minor version numbers."""
        try:
            # Remove any pre-release suffixes
            clean_version = re.sub(r"[a-zA-Z].*$", "", self.version)
            parts = clean_version.split(".")

            if len(parts) >= 2:
                return (int(parts[0]), int(parts[1]))
            if len(parts) == 1:
                return (int(parts[0]), 0)
            return ()
        except (ValueError, IndexError) as e:
            logger.error(f"Error parsing version {self.version}: {e}")
            return ()


@dataclass
class GrammarVersion:
    """Represents a specific grammar version."""

    language: str
    version: str
    grammar_file: str
    supported_features: list[str] = field(default_factory=list)
    min_language_version: str | None = None
    max_language_version: str | None = None
    breaking_changes: list[str] = field(default_factory=list)
    release_date: datetime | None = None

    def __post_init__(self):
        """Validate grammar version data."""
        if not self.language or not self.version or not self.grammar_file:
            raise ValueError("Language, version, and grammar_file are required")

        # Normalize language name
        self.language = self.language.lower().strip()

        # Validate file path
        if not self.grammar_file.endswith(".so"):
            logger.warning(
                f"Grammar file doesn't have .so extension: {self.grammar_file}",
            )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "language": self.language,
            "version": self.version,
            "grammar_file": self.grammar_file,
            "supported_features": self.supported_features,
            "min_language_version": self.min_language_version,
            "max_language_version": self.max_language_version,
            "breaking_changes": self.breaking_changes,
            "release_date": (
                self.release_date.isoformat() if self.release_date else None
            ),
        }

    def __str__(self) -> str:
        """String representation of grammar version."""
        result = f"{self.language} grammar v{self.version} ({self.grammar_file})"
        if self.min_language_version or self.max_language_version:
            result += f" [supports {self.min_language_version or '*'} - {self.max_language_version or '*'}]"
        return result

    def supports_language_version(self, lang_version: LanguageVersion) -> bool:
        """Check if this grammar supports the given language version."""
        if self.language != lang_version.language:
            return False

        # Check minimum version constraint
        if self.min_language_version:
            if (
                self._compare_versions(lang_version.version, self.min_language_version)
                < 0
            ):
                return False

        # Check maximum version constraint
        if self.max_language_version:
            if (
                self._compare_versions(lang_version.version, self.max_language_version)
                > 0
            ):
                return False

        return True

    def get_compatibility_level(
        self,
        lang_version: LanguageVersion,
    ) -> CompatibilityLevel:
        """Determine compatibility level with a language version."""
        if self.language != lang_version.language:
            return CompatibilityLevel.INCOMPATIBLE

        if not self.supports_language_version(lang_version):
            return CompatibilityLevel.INCOMPATIBLE

        # Check if all features are supported
        missing_features = set(lang_version.features) - set(self.supported_features)

        if not missing_features:
            return CompatibilityLevel.FULLY_COMPATIBLE
        if len(missing_features) <= 2:
            return CompatibilityLevel.MOSTLY_COMPATIBLE
        return CompatibilityLevel.PARTIALLY_COMPATIBLE

    def _compare_versions(self, v1: str, v2: str) -> int:
        """Compare two version strings.

        Returns:
            -1 if v1 < v2, 0 if v1 == v2, 1 if v1 > v2
        """
        try:
            # Simple version comparison
            v1_parts = [int(x) for x in re.sub(r"[a-zA-Z].*$", "", v1).split(".")]
            v2_parts = [int(x) for x in re.sub(r"[a-zA-Z].*$", "", v2).split(".")]

            # Pad with zeros
            max_len = max(len(v1_parts), len(v2_parts))
            v1_parts.extend([0] * (max_len - len(v1_parts)))
            v2_parts.extend([0] * (max_len - len(v2_parts)))

            for p1, p2 in zip(v1_parts, v2_parts, strict=False):
                if p1 < p2:
                    return -1
                if p1 > p2:
                    return 1

            return 0
        except Exception as e:
            logger.error(f"Error comparing versions {v1} and {v2}: {e}")
            return 0


@dataclass
class CompatibilityRule:
    """Defines compatibility rules between language and grammar versions."""

    language: str
    language_version_constraint: str
    grammar_version_constraint: str
    compatibility_level: CompatibilityLevel
    notes: str | None = None
    created_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        """Validate compatibility rule data."""
        if not self.language or not self.language_version_constraint:
            raise ValueError("Language and version constraint are required")

        # Normalize language name
        self.language = self.language.lower().strip()

        # Validate compatibility level
        if not isinstance(self.compatibility_level, CompatibilityLevel):
            raise ValueError("Invalid compatibility level")

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "language": self.language,
            "language_version_constraint": self.language_version_constraint,
            "grammar_version_constraint": self.grammar_version_constraint,
            "compatibility_level": self.compatibility_level.value,
            "notes": self.notes,
            "created_at": self.created_at.isoformat(),
        }

    def __str__(self) -> str:
        """String representation of compatibility rule."""
        return (
            f"{self.language} {self.language_version_constraint} "
            f"<-> grammar {self.grammar_version_constraint}: "
            f"{self.compatibility_level.value}"
        )

    def matches_language_version(self, lang_version: LanguageVersion) -> bool:
        """Check if this rule matches a language version."""
        if self.language != lang_version.language:
            return False

        return self._check_version_constraint(
            lang_version.version,
            self.language_version_constraint,
        )

    def matches_grammar_version(self, grammar_version: GrammarVersion) -> bool:
        """Check if this rule matches a grammar version."""
        if self.language != grammar_version.language:
            return False

        return self._check_version_constraint(
            grammar_version.version,
            self.grammar_version_constraint,
        )

    def _check_version_constraint(self, version: str, constraint: str) -> bool:
        """Check if a version matches a constraint.

        Supports:
        - Exact match: "1.2.3"
        - Minimum: ">=1.2.0"
        - Maximum: "<=2.0.0"
        - Range: "1.2.0-2.0.0"
        - Wildcard: "1.*"
        """
        try:
            # Wildcard match
            if "*" in constraint:
                pattern = constraint.replace(".", r"\.").replace("*", r".*")
                return bool(re.match(f"^{pattern}$", version))

            # Range match
            if (
                "-" in constraint
                and not constraint.startswith(">")
                and not constraint.startswith("<")
            ):
                min_v, max_v = constraint.split("-")
                return (
                    self._compare_versions(version, min_v) >= 0
                    and self._compare_versions(version, max_v) <= 0
                )

            # Operator match
            if constraint.startswith(">="):
                return self._compare_versions(version, constraint[2:]) >= 0
            if constraint.startswith("<="):
                return self._compare_versions(version, constraint[2:]) <= 0
            if constraint.startswith(">"):
                return self._compare_versions(version, constraint[1:]) > 0
            if constraint.startswith("<"):
                return self._compare_versions(version, constraint[1:]) < 0

            # Exact match
            return version == constraint

        except Exception as e:
            logger.error(
                f"Error checking constraint {constraint} against {version}: {e}",
            )
            return False

    def _compare_versions(self, v1: str, v2: str) -> int:
        """Compare two version strings."""
        try:
            v1_parts = [int(x) for x in re.sub(r"[a-zA-Z].*$", "", v1).split(".")]
            v2_parts = [int(x) for x in re.sub(r"[a-zA-Z].*$", "", v2).split(".")]

            max_len = max(len(v1_parts), len(v2_parts))
            v1_parts.extend([0] * (max_len - len(v1_parts)))
            v2_parts.extend([0] * (max_len - len(v2_parts)))

            for p1, p2 in zip(v1_parts, v2_parts, strict=False):
                if p1 < p2:
                    return -1
                if p1 > p2:
                    return 1

            return 0
        except Exception:
            return 0


@dataclass
class BreakingChange:
    """Represents a breaking change between versions."""

    language: str
    from_version: str
    to_version: str
    change_type: str  # "syntax", "api", "feature", "deprecation"
    description: str
    impact_level: str  # "low", "medium", "high", "critical"
    migration_guide: str | None = None
    affected_features: list[str] = field(default_factory=list)
    detected_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        """Validate breaking change data."""
        if not all(
            [
                self.language,
                self.from_version,
                self.to_version,
                self.change_type,
                self.description,
                self.impact_level,
            ],
        ):
            raise ValueError("All required fields must be provided")

        # Normalize language name
        self.language = self.language.lower().strip()

        # Validate change type
        valid_types = ["syntax", "api", "feature", "deprecation"]
        if self.change_type not in valid_types:
            raise ValueError(f"Invalid change type: {self.change_type}")

        # Validate impact level
        valid_impacts = ["low", "medium", "high", "critical"]
        if self.impact_level not in valid_impacts:
            raise ValueError(f"Invalid impact level: {self.impact_level}")

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "language": self.language,
            "from_version": self.from_version,
            "to_version": self.to_version,
            "change_type": self.change_type,
            "description": self.description,
            "impact_level": self.impact_level,
            "migration_guide": self.migration_guide,
            "affected_features": self.affected_features,
            "detected_at": self.detected_at.isoformat(),
        }

    def __str__(self) -> str:
        """String representation of breaking change."""
        return (
            f"{self.language} {self.from_version} -> {self.to_version}: "
            f"{self.change_type} change ({self.impact_level}): {self.description}"
        )

    def affects_feature(self, feature: str) -> bool:
        """Check if this breaking change affects a specific feature."""
        return feature in self.affected_features


class CompatibilitySchema:
    """Main schema class for managing compatibility data."""

    def __init__(self):
        self.language_versions: dict[str, list[LanguageVersion]] = {}
        self.grammar_versions: dict[str, list[GrammarVersion]] = {}
        self.compatibility_rules: list[CompatibilityRule] = []
        self.breaking_changes: list[BreakingChange] = []
        logger.debug("Initialized CompatibilitySchema")

    def add_language_version(self, lang_version: LanguageVersion) -> None:
        """Add a language version to the schema."""
        try:
            language = lang_version.language
            if language not in self.language_versions:
                self.language_versions[language] = []

            # Check for duplicates
            for existing in self.language_versions[language]:
                if existing.version == lang_version.version:
                    logger.warning(f"Language version already exists: {lang_version}")
                    return

            self.language_versions[language].append(lang_version)
            logger.debug(f"Added language version: {lang_version}")

        except Exception as e:
            logger.error(f"Error adding language version: {e}")
            raise

    def add_grammar_version(self, grammar_version: GrammarVersion) -> None:
        """Add a grammar version to the schema."""
        try:
            language = grammar_version.language
            if language not in self.grammar_versions:
                self.grammar_versions[language] = []

            # Check for duplicates
            for existing in self.grammar_versions[language]:
                if existing.version == grammar_version.version:
                    logger.warning(f"Grammar version already exists: {grammar_version}")
                    return

            self.grammar_versions[language].append(grammar_version)
            logger.debug(f"Added grammar version: {grammar_version}")

        except Exception as e:
            logger.error(f"Error adding grammar version: {e}")
            raise

    def add_compatibility_rule(self, rule: CompatibilityRule) -> None:
        """Add a compatibility rule to the schema."""
        try:
            # Check for duplicates
            for existing in self.compatibility_rules:
                if (
                    existing.language == rule.language
                    and existing.language_version_constraint
                    == rule.language_version_constraint
                    and existing.grammar_version_constraint
                    == rule.grammar_version_constraint
                ):
                    logger.warning(f"Compatibility rule already exists: {rule}")
                    return

            self.compatibility_rules.append(rule)
            logger.debug(f"Added compatibility rule: {rule}")

        except Exception as e:
            logger.error(f"Error adding compatibility rule: {e}")
            raise

    def add_breaking_change(self, breaking_change: BreakingChange) -> None:
        """Add a breaking change to the schema."""
        try:
            # Check for duplicates
            for existing in self.breaking_changes:
                if (
                    existing.language == breaking_change.language
                    and existing.from_version == breaking_change.from_version
                    and existing.to_version == breaking_change.to_version
                    and existing.change_type == breaking_change.change_type
                ):
                    logger.warning(f"Breaking change already exists: {breaking_change}")
                    return

            self.breaking_changes.append(breaking_change)
            logger.debug(f"Added breaking change: {breaking_change}")

        except Exception as e:
            logger.error(f"Error adding breaking change: {e}")
            raise

    def get_language_versions(self, language: str) -> list[LanguageVersion]:
        """Get all versions for a specific language."""
        language = language.lower().strip()
        return self.language_versions.get(language, [])

    def get_grammar_versions(self, language: str) -> list[GrammarVersion]:
        """Get all grammar versions for a specific language."""
        language = language.lower().strip()
        return self.grammar_versions.get(language, [])

    def find_compatible_grammar(
        self,
        lang_version: LanguageVersion,
    ) -> GrammarVersion | None:
        """Find a compatible grammar for a language version."""
        try:
            grammars = self.get_grammar_versions(lang_version.language)

            best_grammar = None
            best_level = CompatibilityLevel.INCOMPATIBLE

            for grammar in grammars:
                level = grammar.get_compatibility_level(lang_version)

                # Check rules for override
                for rule in self.compatibility_rules:
                    if rule.matches_language_version(
                        lang_version,
                    ) and rule.matches_grammar_version(grammar):
                        level = rule.compatibility_level
                        break

                # Update best match
                if level != CompatibilityLevel.INCOMPATIBLE:
                    if best_grammar is None or self._is_better_compatibility(
                        level,
                        best_level,
                    ):
                        best_grammar = grammar
                        best_level = level

            if best_grammar:
                logger.debug(
                    f"Found compatible grammar for {lang_version}: {best_grammar}",
                )
            else:
                logger.warning(f"No compatible grammar found for {lang_version}")

            return best_grammar

        except Exception as e:
            logger.error(f"Error finding compatible grammar: {e}")
            return None

    def get_compatibility_level(
        self,
        lang_version: LanguageVersion,
        grammar_version: GrammarVersion,
    ) -> CompatibilityLevel:
        """Get compatibility level between language and grammar versions."""
        try:
            # Check rules first
            for rule in self.compatibility_rules:
                if rule.matches_language_version(
                    lang_version,
                ) and rule.matches_grammar_version(grammar_version):
                    return rule.compatibility_level

            # Fall back to grammar's own assessment
            return grammar_version.get_compatibility_level(lang_version)

        except Exception as e:
            logger.error(f"Error getting compatibility level: {e}")
            return CompatibilityLevel.UNKNOWN

    def get_breaking_changes(
        self,
        language: str,
        from_version: str,
        to_version: str,
    ) -> list[BreakingChange]:
        """Get breaking changes between two versions."""
        try:
            language = language.lower().strip()
            result = []

            for change in self.breaking_changes:
                if change.language != language:
                    continue

                # Check if change is in the version range
                if self._version_in_range(
                    change.from_version,
                    from_version,
                    to_version,
                ) or self._version_in_range(
                    change.to_version,
                    from_version,
                    to_version,
                ):
                    result.append(change)

            return result

        except Exception as e:
            logger.error(f"Error getting breaking changes: {e}")
            return []

    def validate_schema(self) -> list[str]:
        """Validate the entire schema and return any errors."""
        errors = []

        try:
            # Check for orphaned rules
            for rule in self.compatibility_rules:
                lang_found = False
                grammar_found = False

                for lang_version in self.language_versions.get(rule.language, []):
                    if rule.matches_language_version(lang_version):
                        lang_found = True
                        break

                for grammar_version in self.grammar_versions.get(rule.language, []):
                    if rule.matches_grammar_version(grammar_version):
                        grammar_found = True
                        break

                if not lang_found:
                    errors.append(f"Rule references unknown language version: {rule}")
                if not grammar_found:
                    errors.append(f"Rule references unknown grammar version: {rule}")

            # Check for version conflicts
            for language, versions in self.language_versions.items():
                version_numbers = [v.version for v in versions]
                if len(version_numbers) != len(set(version_numbers)):
                    errors.append(f"Duplicate language versions for {language}")

            for language, versions in self.grammar_versions.items():
                version_numbers = [v.version for v in versions]
                if len(version_numbers) != len(set(version_numbers)):
                    errors.append(f"Duplicate grammar versions for {language}")

            # Check breaking changes
            for change in self.breaking_changes:
                if change.language not in self.language_versions:
                    errors.append(
                        f"Breaking change references unknown language: {change.language}",
                    )

            if errors:
                logger.warning(f"Schema validation found {len(errors)} errors")
            else:
                logger.debug("Schema validation passed")

        except Exception as e:
            logger.error(f"Error validating schema: {e}")
            errors.append(f"Validation error: {e}")

        return errors

    def to_dict(self) -> dict[str, Any]:
        """Convert entire schema to dictionary representation."""
        try:
            return {
                "language_versions": {
                    lang: [v.to_dict() for v in versions]
                    for lang, versions in self.language_versions.items()
                },
                "grammar_versions": {
                    lang: [v.to_dict() for v in versions]
                    for lang, versions in self.grammar_versions.items()
                },
                "compatibility_rules": [r.to_dict() for r in self.compatibility_rules],
                "breaking_changes": [c.to_dict() for c in self.breaking_changes],
            }
        except Exception as e:
            logger.error(f"Error converting schema to dict: {e}")
            return {}

    def from_dict(self, data: dict[str, Any]) -> None:
        """Load schema from dictionary representation."""
        try:
            # Clear existing data
            self.language_versions.clear()
            self.grammar_versions.clear()
            self.compatibility_rules.clear()
            self.breaking_changes.clear()

            # Load language versions
            for lang, versions in data.get("language_versions", {}).items():
                for v_data in versions:
                    lang_version = LanguageVersion(
                        language=v_data["language"],
                        version=v_data["version"],
                        edition=v_data.get("edition"),
                        build=v_data.get("build"),
                        features=v_data.get("features", []),
                        release_date=(
                            datetime.fromisoformat(v_data["release_date"])
                            if v_data.get("release_date")
                            else None
                        ),
                        end_of_life=(
                            datetime.fromisoformat(v_data["end_of_life"])
                            if v_data.get("end_of_life")
                            else None
                        ),
                    )
                    self.add_language_version(lang_version)

            # Load grammar versions
            for lang, versions in data.get("grammar_versions", {}).items():
                for v_data in versions:
                    grammar_version = GrammarVersion(
                        language=v_data["language"],
                        version=v_data["version"],
                        grammar_file=v_data["grammar_file"],
                        supported_features=v_data.get("supported_features", []),
                        min_language_version=v_data.get("min_language_version"),
                        max_language_version=v_data.get("max_language_version"),
                        breaking_changes=v_data.get("breaking_changes", []),
                        release_date=(
                            datetime.fromisoformat(v_data["release_date"])
                            if v_data.get("release_date")
                            else None
                        ),
                    )
                    self.add_grammar_version(grammar_version)

            # Load compatibility rules
            for r_data in data.get("compatibility_rules", []):
                rule = CompatibilityRule(
                    language=r_data["language"],
                    language_version_constraint=r_data["language_version_constraint"],
                    grammar_version_constraint=r_data["grammar_version_constraint"],
                    compatibility_level=CompatibilityLevel(
                        r_data["compatibility_level"],
                    ),
                    notes=r_data.get("notes"),
                    created_at=(
                        datetime.fromisoformat(r_data["created_at"])
                        if r_data.get("created_at")
                        else datetime.now()
                    ),
                )
                self.add_compatibility_rule(rule)

            # Load breaking changes
            for c_data in data.get("breaking_changes", []):
                change = BreakingChange(
                    language=c_data["language"],
                    from_version=c_data["from_version"],
                    to_version=c_data["to_version"],
                    change_type=c_data["change_type"],
                    description=c_data["description"],
                    impact_level=c_data["impact_level"],
                    migration_guide=c_data.get("migration_guide"),
                    affected_features=c_data.get("affected_features", []),
                    detected_at=(
                        datetime.fromisoformat(c_data["detected_at"])
                        if c_data.get("detected_at")
                        else datetime.now()
                    ),
                )
                self.add_breaking_change(change)

            logger.info("Schema loaded from dictionary")

        except Exception as e:
            logger.error(f"Error loading schema from dict: {e}")
            raise

    def _is_better_compatibility(
        self,
        level1: CompatibilityLevel,
        level2: CompatibilityLevel,
    ) -> bool:
        """Check if level1 is better than level2."""
        order = [
            CompatibilityLevel.FULLY_COMPATIBLE,
            CompatibilityLevel.MOSTLY_COMPATIBLE,
            CompatibilityLevel.PARTIALLY_COMPATIBLE,
            CompatibilityLevel.UNKNOWN,
            CompatibilityLevel.INCOMPATIBLE,
        ]

        try:
            return order.index(level1) < order.index(level2)
        except ValueError:
            return False

    def _version_in_range(
        self,
        version: str,
        from_version: str,
        to_version: str,
    ) -> bool:
        """Check if a version is within a range."""
        try:
            v_parts = [int(x) for x in re.sub(r"[a-zA-Z].*$", "", version).split(".")]
            from_parts = [
                int(x) for x in re.sub(r"[a-zA-Z].*$", "", from_version).split(".")
            ]
            to_parts = [
                int(x) for x in re.sub(r"[a-zA-Z].*$", "", to_version).split(".")
            ]

            max_len = max(len(v_parts), len(from_parts), len(to_parts))
            v_parts.extend([0] * (max_len - len(v_parts)))
            from_parts.extend([0] * (max_len - len(from_parts)))
            to_parts.extend([0] * (max_len - len(to_parts)))

            return from_parts <= v_parts <= to_parts

        except Exception:
            return False

"""Go version detection module for Phase 1.7."""

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# Go build-constraint minimum-release computation (treesitter-chunker#438).
#
# This is not a build-constraint evaluator. A release tag ``goX.Y`` is true
# exactly at Go releases >= X.Y; every other tag is an independent free
# variable. The reported minimum is the lowest release at which the
# expression can be true for some assignment of the free tags, so releases
# below it cannot satisfy the constraint.

_GO_RELEASE_TAG = re.compile(r"go(\d+)\.(\d+)")
_GO_BUILD_TAG = re.compile(r"[A-Za-z0-9_.]+")
_GO_MODERN_LINE = re.compile(r"^[ \t]*//go:build[ \t]+(.*?)[ \t]*\r?$", re.MULTILINE)
_GO_LEGACY_LINE = re.compile(
    r"^[ \t]*//[ \t]*\+build[ \t]+(\S.*?)[ \t]*\r?$", re.MULTILINE
)
_GO_MODERN_TOKEN = re.compile(r"[ \t]*(\(|\)|!|&&|\|\||[A-Za-z0-9_.]+)")
_GO_MAX_TOKENS = 1000
_GO_MAX_DEPTH = 100
_GO_MAX_FREE_TAGS = 32
_GO_MAX_SEARCH_STEPS = 10_000

# Expression nodes: ("tag", name), ("const", bool), ("not", node),
# ("and", children), ("or", children). AND/OR are n-ary so that recursion
# depth follows parenthesis nesting, not expression length.
_GoExpr = tuple[Any, ...]


class _GoConstraintUnknownError(Exception):
    """The constraint cannot be interpreted; the hint is unknown."""


def _parse_modern_go_build(expression: str) -> _GoExpr:
    tokens: list[str] = []
    position = 0
    while position < len(expression):
        match = _GO_MODERN_TOKEN.match(expression, position)
        if match is None:
            if expression[position:].strip(" \t") == "":
                break
            raise _GoConstraintUnknownError(f"unexpected text in {expression!r}")
        tokens.append(match.group(1))
        position = match.end()
        if len(tokens) > _GO_MAX_TOKENS:
            raise _GoConstraintUnknownError("expression too large")
    if not tokens:
        raise _GoConstraintUnknownError("empty //go:build expression")
    index = 0

    def peek() -> str | None:
        return tokens[index] if index < len(tokens) else None

    def take() -> str:
        nonlocal index
        token = tokens[index]
        index += 1
        return token

    def parse_or(depth: int) -> _GoExpr:
        children = [parse_and(depth)]
        while peek() == "||":
            take()
            children.append(parse_and(depth))
        return children[0] if len(children) == 1 else ("or", tuple(children))

    def parse_and(depth: int) -> _GoExpr:
        children = [parse_unary(depth)]
        while peek() == "&&":
            take()
            children.append(parse_unary(depth))
        return children[0] if len(children) == 1 else ("and", tuple(children))

    def parse_unary(depth: int) -> _GoExpr:
        if depth > _GO_MAX_DEPTH:
            raise _GoConstraintUnknownError("expression nested too deeply")
        token = peek()
        if token is None:
            raise _GoConstraintUnknownError(f"unexpected end of {expression!r}")
        if token == "!":
            take()
            return ("not", parse_unary(depth + 1))
        if token == "(":
            take()
            node = parse_or(depth + 1)
            if peek() != ")":
                raise _GoConstraintUnknownError(
                    f"unbalanced parentheses in {expression!r}"
                )
            take()
            return node
        if _GO_BUILD_TAG.fullmatch(token):
            take()
            return ("tag", token)
        raise _GoConstraintUnknownError(f"unexpected {token!r} in {expression!r}")

    node = parse_or(0)
    if index != len(tokens):
        raise _GoConstraintUnknownError(
            f"unexpected {tokens[index]!r} in {expression!r}"
        )
    return node


def _parse_legacy_go_build(fields_text: str) -> _GoExpr:
    """Fields are OR-ed; comma-separated atoms are AND-ed; ``!tag`` negates."""
    fields = fields_text.split()
    if sum(len(field.split(",")) for field in fields) > _GO_MAX_TOKENS:
        raise _GoConstraintUnknownError("expression too large")
    if not fields:
        raise _GoConstraintUnknownError("empty +build line")
    disjuncts: list[_GoExpr] = []
    for field in fields:
        terms: list[_GoExpr] = []
        for atom in field.split(","):
            negated = atom.startswith("!")
            name = atom[1:] if negated else atom
            if not _GO_BUILD_TAG.fullmatch(name):
                raise _GoConstraintUnknownError(f"invalid +build term {atom!r}")
            terms.append(("not", ("tag", name)) if negated else ("tag", name))
        disjuncts.append(("and", tuple(terms)))
    return ("or", tuple(disjuncts))


def _go_release(name: str) -> tuple[int, int] | None:
    match = _GO_RELEASE_TAG.fullmatch(name)
    return (int(match.group(1)), int(match.group(2))) if match else None


def _go_tags(node: _GoExpr, found: set[str]) -> set[str]:
    kind = node[0]
    if kind == "tag":
        found.add(node[1])
    elif kind == "not":
        _go_tags(node[1], found)
    elif kind in ("and", "or"):
        for child in node[1]:
            _go_tags(child, found)
    return found


def _go_assign(node: _GoExpr, values: dict[str, bool]) -> _GoExpr:
    """Substitute known tag values and fold constants."""
    kind = node[0]
    if kind == "tag":
        value = values.get(node[1])
        return node if value is None else ("const", value)
    if kind == "const":
        return node
    if kind == "not":
        inner = _go_assign(node[1], values)
        return ("const", not inner[1]) if inner[0] == "const" else ("not", inner)
    absorbing = kind == "or"  # True absorbs OR, False absorbs AND
    children: list[_GoExpr] = []
    for child in node[1]:
        folded = _go_assign(child, values)
        if folded[0] == "const":
            if folded[1] is absorbing:
                return folded
            continue  # the identity element drops out
        children.append(folded)
    if not children:
        return ("const", not absorbing)
    return children[0] if len(children) == 1 else (kind, tuple(children))


def _go_satisfiable(node: _GoExpr, budget: list[int]) -> bool:
    if node[0] == "const":
        return bool(node[1])
    budget[0] -= 1
    if budget[0] < 0:
        raise _GoConstraintUnknownError("expression too complex")
    name = min(_go_tags(node, set()))
    return _go_satisfiable(_go_assign(node, {name: True}), budget) or (
        _go_satisfiable(_go_assign(node, {name: False}), budget)
    )


def _go_minimum_release(node: _GoExpr) -> tuple[int, int] | None:
    """Lowest release at which ``node`` can hold; ``None`` if no minimum.

    Raises ``_GoConstraintUnknownError`` when no release can satisfy it or the
    search is too large.
    """
    tags = _go_tags(node, set())
    releases = sorted({r for tag in tags if (r := _go_release(tag)) is not None})
    if len(tags) - len(releases) > _GO_MAX_FREE_TAGS:
        raise _GoConstraintUnknownError("too many build tags")
    budget = [_GO_MAX_SEARCH_STEPS]
    # Release tags change value only at mentioned releases, so these points
    # cover every release: below all of them, then each in ascending order.
    for point in [None, *releases]:
        values = {
            tag: point is not None and release <= point
            for tag in tags
            if (release := _go_release(tag)) is not None
        }
        if _go_satisfiable(_go_assign(node, values), budget):
            return point
    raise _GoConstraintUnknownError("no Go release satisfies the constraint")


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

    def analyze_build_constraints(self, content: str) -> dict[str, str | None]:
        """Infer the minimum Go release a file's build constraints require.

        Recognizes ``//go:build`` expressions (``&&``, ``||``, ``!``,
        parentheses) and legacy ``// +build`` lines (whitespace-separated
        fields are OR-ed, comma-separated atoms AND-ed, ``!tag`` negated).
        When any ``//go:build`` line is present, legacy lines are ignored;
        several lines of one kind are AND-ed.

        A release tag ``goX.Y`` holds exactly at releases >= X.Y. Every other
        tag (GOOS, GOARCH, ``cgo``, custom tags) is treated as independent
        and free, so this is a necessary minimum, not a build evaluation
        (treesitter-chunker#438).

        Returns:
            ``{"minimum", "status", "reason"}``. ``status`` is ``"minimum"``
            (``minimum`` is a ``"major.minor"`` string), ``"unconstrained"``
            (the constraint can hold below every mentioned release, so it
            implies no minimum), ``"unknown"`` (malformed, unsatisfiable or
            too large; ``reason`` says which) or ``"absent"`` (no constraint
            line).
        """
        try:
            modern = _GO_MODERN_LINE.findall(content)
            if modern:
                nodes = [_parse_modern_go_build(expression) for expression in modern]
            else:
                legacy = _GO_LEGACY_LINE.findall(content)
                if not legacy:
                    return {"minimum": None, "status": "absent", "reason": None}
                nodes = [_parse_legacy_go_build(fields) for fields in legacy]
            node = nodes[0] if len(nodes) == 1 else ("and", tuple(nodes))
            minimum = _go_minimum_release(node)
        except _GoConstraintUnknownError as e:
            logger.debug("Go build constraint hint unknown: %s", e)
            return {"minimum": None, "status": "unknown", "reason": str(e)}
        if minimum is None:
            return {"minimum": None, "status": "unconstrained", "reason": None}
        version = f"{minimum[0]}.{minimum[1]}"
        logger.debug("Go build constraints require at least %s", version)
        return {"minimum": version, "status": "minimum", "reason": None}

    def detect_from_build_constraints(self, content: str) -> str | None:
        """Extract the minimum Go version implied by build constraints.

        Args:
            content: The file content to search

        Returns:
            Version string like "1.19", or None when the constraints are
            absent, imply no minimum, or cannot be interpreted (see
            ``analyze_build_constraints``).
        """
        return self.analyze_build_constraints(content)["minimum"]

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
            constraint_hint = self.analyze_build_constraints(content)
            results["build_constraints"] = constraint_hint["minimum"]
            results["build_constraints_status"] = constraint_hint["status"]
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

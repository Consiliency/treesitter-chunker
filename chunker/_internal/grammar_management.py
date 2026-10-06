"""Smart grammar management with user guidance and error handling."""

import logging
import subprocess
from dataclasses import dataclass, field
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from chunker.grammar.integrity import probe_native_grammar


logger = logging.getLogger(__name__)


@dataclass
class GrammarHealth:
    """Health status of a grammar library."""

    language: str
    status: str  # "healthy", "corrupted", "missing", "incompatible"
    issues: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    last_checked: str | None = None
    validation_reason: str | None = None
    artifact_sha256: str | None = None
    file_size: int = 0


@dataclass
class GrammarCompatibility:
    """Compatibility information for a grammar."""

    language: str
    tree_sitter_version: str
    system_architecture: str
    os_platform: str
    compilation_date: str | None = None
    compatibility_score: float = 0.0  # 0.0 to 1.0


class SmartGrammarManager:
    """Smart grammar manager with intelligent error handling and user guidance."""

    def __init__(
        self,
        build_dir: Path,
        grammars_dir: Path,
        *,
        trusted_artifacts: Mapping[str, Mapping[str, Any]] | None = None,
    ):
        """Initialize the smart grammar manager.

        Args:
            build_dir: Directory containing compiled .so files
            grammars_dir: Directory containing grammar source repositories
        """
        self.build_dir = Path(build_dir)
        self.grammars_dir = Path(grammars_dir)
        self.trusted_artifacts = {
            language: dict(provenance)
            for language, provenance in (trusted_artifacts or {}).items()
            if isinstance(provenance, Mapping)
        }
        self.health_cache: dict[str, GrammarHealth] = {}
        self.compatibility_cache: dict[str, GrammarCompatibility] = {}

    def diagnose_grammar_issues(self, language: str) -> GrammarHealth:
        """Diagnose issues with a specific grammar.

        Args:
            language: Language name to diagnose

        Returns:
            GrammarHealth object with detailed diagnosis
        """
        health = GrammarHealth(language=language, status="unknown")

        so_file = (self.build_dir / f"{language}.so").absolute()
        snapshot_metadata = {}

        def inspect(snapshot: Path) -> None:
            snapshot_metadata["file_size"] = snapshot.stat().st_size

        probe = probe_native_grammar(
            so_file,
            language,
            provenance=self.trusted_artifacts.get(language),
            inspect_artifact=inspect,
        )
        health.validation_reason = probe.reason
        health.artifact_sha256 = probe.artifact_sha256
        if probe.supported:
            health.file_size = snapshot_metadata["file_size"]
        if probe.reason == "missing":
            health.status = "missing"
            health.issues.append(f"Grammar library {so_file} not found")
            health.recommendations.extend(
                [
                    "Check if the grammar source exists in grammars/ directory",
                    "Compile the grammar using the appropriate build script",
                    "Verify the grammar repository was cloned correctly",
                ],
            )
        elif probe.reason in {"empty", "load_failed", "parse_failed"}:
            health.status = "corrupted"
            health.issues.append(f"Native admission failed: {probe.reason}")
            health.recommendations.append("Recompile the grammar from source")
        elif probe.supported:
            health.status = "healthy"
            health.recommendations.append("Grammar appears to be working correctly")
        else:
            health.status = "incompatible"
            health.issues.append(f"Native admission failed: {probe.reason}")
            if probe.reason in {"untrusted", "integrity_mismatch"}:
                health.recommendations.append(
                    "Supply an independently approved SHA-256 provenance pin",
                )
            else:
                health.recommendations.extend(
                    [
                        "Check system compatibility (architecture, OS)",
                        "Verify tree-sitter version compatibility",
                        "Try recompiling on current system",
                    ],
                )

        # Check source repository
        source_dir = self.grammars_dir / f"tree-sitter-{language}"
        if not source_dir.exists():
            health.issues.append(f"Grammar source repository not found: {source_dir}")
            health.recommendations.append(
                "Clone the grammar repository to grammars/ directory",
            )
        else:
            # Check if source is up to date
            try:
                result = subprocess.run(
                    ["git", "log", "--oneline", "-1"],
                    cwd=source_dir,
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=False,
                )
                if result.returncode == 0:
                    health.recommendations.append(
                        "Grammar source repository is available",
                    )
                else:
                    health.issues.append("Grammar source repository may be corrupted")
                    health.recommendations.append("Re-clone the grammar repository")
            except Exception:
                health.issues.append(
                    "Could not verify grammar source repository status",
                )

        self.health_cache[language] = health
        return health

    def get_grammar_compatibility(self, language: str) -> GrammarCompatibility:
        """Get compatibility information for a grammar.

        Args:
            language: Language name

        Returns:
            GrammarCompatibility object with compatibility details
        """
        if language in self.compatibility_cache:
            return self.compatibility_cache[language]

        compatibility = GrammarCompatibility(
            language=language,
            tree_sitter_version="unknown",
            system_architecture="unknown",
            os_platform="unknown",
        )

        # Get system information
        try:
            import platform

            compatibility.system_architecture = platform.machine()
            compatibility.os_platform = platform.system()
        except Exception:
            pass

        # Get tree-sitter version
        try:
            import tree_sitter

            compatibility.tree_sitter_version = getattr(
                tree_sitter,
                "__version__",
                "unknown",
            )
        except Exception:
            pass

        # Calculate compatibility score
        score = 0.0
        if compatibility.tree_sitter_version != "unknown":
            score += 0.3
        if compatibility.system_architecture != "unknown":
            score += 0.3
        if compatibility.os_platform != "unknown":
            score += 0.2
        compatibility.compatibility_score = score

        self.compatibility_cache[language] = compatibility
        return compatibility

    def generate_recovery_plan(
        self, language: str, *, health: GrammarHealth | None = None
    ) -> dict[str, Any]:
        """Generate a recovery plan for a problematic grammar.

        Args:
            language: Language name with issues

        Returns:
            Recovery plan with specific steps
        """
        if health is None:
            health = self.diagnose_grammar_issues(language)
        plan: dict[str, Any] = {
            "language": language,
            "current_status": health.status,
            "validation_reason": health.validation_reason,
            "artifact_sha256": health.artifact_sha256,
            "issues": health.issues,
            "recovery_steps": [],
            "estimated_time": "unknown",
            "difficulty": "unknown",
        }

        if health.status == "missing":
            plan["recovery_steps"] = [
                f"Clone grammar repository: git clone <repo_url> grammars/tree-sitter-{language}",
                f"Navigate to grammar directory: cd grammars/tree-sitter-{language}",
                "Install dependencies: npm install (if package.json exists)",
                "Generate grammar: tree-sitter generate",
                "Copy .so file to build directory: cp *.so ../../chunker/data/grammars/build/",
            ]
            plan["estimated_time"] = "5-15 minutes"
            plan["difficulty"] = "easy"

        elif health.status == "corrupted":
            plan["recovery_steps"] = [
                f"Remove corrupted .so file: rm chunker/data/grammars/build/{language}.so",
                f"Clean grammar source: cd grammars/tree-sitter-{language} && git clean -fd",
                "Pull latest changes: git pull origin main",
                "Recompile grammar: tree-sitter generate",
                "Copy new .so file to build directory",
            ]
            plan["estimated_time"] = "3-10 minutes"
            plan["difficulty"] = "easy"

        elif health.status == "incompatible":
            plan["recovery_steps"] = [
                "Check system compatibility requirements",
                "Verify tree-sitter version compatibility",
                "Recompile grammar on current system",
                "Check for architecture-specific issues",
                "Consider using a different grammar version",
            ]
            plan["estimated_time"] = "10-30 minutes"
            plan["difficulty"] = "medium"

        if health.status != "healthy":
            plan["recovery_steps"].append(
                "Supply an independently approved SHA-256 provenance pin for the final artifact"
            )
        return plan

    def validate_all_grammars(self) -> dict[str, GrammarHealth]:
        """Validate all available grammars and report health status.

        Returns:
            Dictionary mapping language names to health status
        """
        all_health = {}

        # Get all .so files in build directory
        so_files = list(self.build_dir.glob("*.so"))

        for so_file in so_files:
            language = so_file.stem
            all_health[language] = self.diagnose_grammar_issues(language)

        return all_health

    def get_system_requirements(self) -> dict[str, Any]:
        """Get system requirements for grammar compilation.

        Returns:
            System requirements information
        """
        requirements = {
            "tree_sitter_cli": False,
            "node_npm": False,
            "git": False,
            "compiler": False,
            "python_deps": False,
        }

        # Check tree-sitter CLI
        try:
            result = subprocess.run(
                ["tree-sitter", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            requirements["tree_sitter_cli"] = result.returncode == 0
        except Exception:
            pass

        # Check Node.js and npm
        try:
            result = subprocess.run(
                ["npm", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            requirements["node_npm"] = result.returncode == 0
        except Exception:
            pass

        # Check git
        try:
            result = subprocess.run(
                ["git", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            requirements["git"] = result.returncode == 0
        except Exception:
            pass

        # Check C compiler
        try:
            result = subprocess.run(
                ["gcc", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            requirements["compiler"] = result.returncode == 0
        except Exception:
            try:
                result = subprocess.run(
                    ["clang", "--version"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    check=False,
                )
                requirements["compiler"] = result.returncode == 0
            except Exception:
                pass

        # Check Python dependencies
        try:
            import tree_sitter as _tree_sitter

            requirements["python_deps"] = _tree_sitter is not None
        except ImportError:
            pass

        return requirements

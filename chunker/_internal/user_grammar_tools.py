"""User-friendly tools for managing tree-sitter grammars."""

import logging
import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from .grammar_management import SmartGrammarManager, _require_language_component
from .package_supplier import is_record_entry
from .trusted_artifacts import pin_provenance
from ..grammar.integrity import (
    DEFAULT_PROBE_TIMEOUT,
    NativeProbeResult,
    probe_native_grammar,
)
from ..grammar.source_validation import validate_grammar_source

logger = logging.getLogger(__name__)

#: Suffix of staged publication files. It never ends in a library suffix, so
#: ``*.so``/``*.dylib``/``*.dll`` scans never list or load a staged file.
STAGED_SUFFIX = ".staged"

_ADMISSION_EXPLANATIONS = {
    "untrusted": "the library is not trusted by an approved SHA-256 pin",
    "integrity_mismatch": "the library does not match its approved SHA-256 pin",
    "empty": "the library is empty",
    "load_failed": "the library could not be loaded",
    "parse_failed": "the library loaded but could not parse",
    "timeout": "the admission probe timed out",
    "missing": "the library file does not exist",
    "child_failed": "the probe process failed or ended abnormally",
    "inspect_failed": "the artifact inspection step failed",
    "ack_missing": "the probe process returned no result",
    "ack_invalid": "the probe process returned an invalid result",
}


def publish_native_grammar(
    source: Path,
    destination: Path,
    language: str,
    *,
    provenance: Mapping[str, Any] | None,
    sample: bytes = b"",
    timeout: float = DEFAULT_PROBE_TIMEOUT,
) -> NativeProbeResult:
    """Publish a compiled grammar without overwriting the existing library file.

    The bytes of ``source`` are copied to a new sibling temporary file in
    ``destination``'s directory and admitted there with
    :func:`~chunker.grammar.integrity.probe_native_grammar` (``provenance``,
    ``sample`` and ``timeout`` are passed through). Only an admitted file is
    moved over ``destination`` with :func:`os.replace`, so the old directory
    entry, or the symlink itself, is swapped and no existing file is opened for
    writing or truncated. A process that has the old library loaded keeps its
    mapping; later loads by a new process read the new file. The probe itself
    loads a private snapshot of the staged file.

    The staged file is named ``.<destination name>-<random>.staged``. It never
    ends in a library suffix, so grammar scans never list or load it. A file of
    that name left by a crash is safe to delete.

    Returns:
        The admission result. ``destination`` changed only if
        ``result.supported`` is true; otherwise the staged file is removed and
        ``destination`` is untouched.

    Raises:
        OSError: If staging or replacement fails (for example, Windows refuses
            to replace a library that a process has loaded). The staged file is
            removed and ``destination`` is untouched.
    """
    destination = Path(destination).absolute()
    descriptor, staged_name = tempfile.mkstemp(
        prefix=f".{destination.name}-",
        suffix=STAGED_SUFFIX,
        dir=destination.parent,
    )
    staged = Path(staged_name)
    published = False
    try:
        with (
            os.fdopen(descriptor, "wb") as staged_file,
            Path(source).open("rb") as source_file,
        ):
            shutil.copyfileobj(source_file, staged_file)
            staged_file.flush()
            os.fsync(staged_file.fileno())
        shutil.copymode(source, staged)
        result = probe_native_grammar(
            staged,
            language,
            provenance=provenance,
            sample=sample,
            timeout=timeout,
        )
        if result.supported:
            staged.replace(destination)  # os.replace: swaps the entry atomically
            published = True
        return result
    finally:
        if not published:
            staged.unlink(missing_ok=True)


class UserGrammarTools:
    """User-friendly tools for grammar management."""

    def __init__(
        self,
        build_dir: Path,
        grammars_dir: Path,
        *,
        trusted_artifacts: Mapping[str, Mapping[str, Any]] | None = None,
    ):
        """Initialize user grammar tools.

        Args:
            build_dir: Directory containing compiled grammar libraries
            grammars_dir: Directory containing grammar source repositories
        """
        self.build_dir = Path(build_dir)
        self.grammars_dir = Path(grammars_dir)
        self.manager = SmartGrammarManager(
            build_dir,
            grammars_dir,
            trusted_artifacts=trusted_artifacts,
        )

    def _publish_library(
        self, language: str, library: Path, result: dict[str, Any]
    ) -> bool:
        """Publish ``library`` as ``<language>.so`` via staged admission.

        Records an error and returns ``False`` if admission or replacement
        fails; the installed library is then unchanged. The manager's cached
        health and compatibility for ``language`` are dropped either way.
        """
        target = self.build_dir / f"{language}.so"
        if self._refuse_shipped_target(language, result):
            self.manager.health_cache.pop(language, None)
            self.manager.compatibility_cache.pop(language, None)
            return False
        provenance = pin_provenance(self.manager.trusted_artifacts, language)
        if provenance is None:
            # Rule 3: without a pin nothing is staged and the probe is not
            # called; the existing untrusted error is reported.
            self.manager.health_cache.pop(language, None)
            self.manager.compatibility_cache.pop(language, None)
            result["errors"].append(
                f"Native admission failed for {library.name}: untrusted "
                f"({_ADMISSION_EXPLANATIONS['untrusted']}); the installed "
                f"library is unchanged. No approved pin was supplied for "
                f"{language}: add its reviewed SHA-256 to the user-config pin "
                "file, pass --trusted-artifacts PATH to the grammar command, or "
                "pass trusted_artifacts to UserGrammarTools."
            )
            result["status"] = "error"
            return False
        try:
            probe = publish_native_grammar(
                library,
                target,
                language,
                provenance=provenance,
            )
        except OSError as error:
            hint = ""
            if sys.platform == "win32" and isinstance(error, PermissionError):
                hint = (
                    " This usually means a running process has the library "
                    "loaded, and Windows cannot replace a loaded library; close "
                    "those processes, then reinstall."
                )
            result["errors"].append(
                f"Could not publish {library.name} to {target}: {error}. The "
                f"installed library is unchanged.{hint}",
            )
            result["status"] = "error"
            return False
        finally:
            self.manager.health_cache.pop(language, None)
            self.manager.compatibility_cache.pop(language, None)
        if not probe.supported:
            explanation = probe.message or _ADMISSION_EXPLANATIONS.get(
                probe.reason, "the native admission probe rejected it"
            )
            message = (
                f"Native admission failed for {library.name}: {probe.reason} "
                f"({explanation}); the installed library is unchanged."
            )
            result["errors"].append(message)
            result["status"] = "error"
            return False
        return True

    def _refuse_shipped_target(self, language: str, result: dict[str, Any]) -> bool:
        """Record an error if ``<language>.so`` here is a shipped RECORD entry."""
        target = self.build_dir / f"{language}.so"
        if not is_record_entry(target):
            return False
        result["errors"].append(
            f"Refusing to replace {target}: it is a grammar shipped with the "
            "installed treesitter-chunker package (listed in its RECORD), and "
            "the shipped grammar cannot be replaced in place. Use a separate "
            "build directory for local grammars and pin those instead."
        )
        result["status"] = "error"
        return True

    def _refuse_shadowed_legacy_copy(
        self, language: str, result: dict[str, Any]
    ) -> bool:
        """Record an error if a native entry would shadow a new legacy ``.so``."""
        native, legacy = self.manager._library_candidates(language)
        if native == legacy or not os.path.lexists(native):
            return False
        result["errors"].append(
            f"Refusing to copy {legacy.name}: existing native library {native} "
            "would take priority over it; no grammar library was copied",
        )
        result["status"] = "error"
        return True

    def install_grammar(
        self,
        language: str,
        repo_url: str,
        branch: str = "main",
    ) -> dict[str, Any]:
        """Install a grammar from a repository.

        Args:
            language: Language name
            repo_url: Git repository URL
            branch: Branch to checkout

        Returns:
            Installation result with status and details
        """
        result = {
            "language": language,
            "status": "unknown",
            "steps_completed": [],
            "errors": [],
            "warnings": [],
        }

        try:
            _require_language_component(language)
            if self._refuse_shipped_target(language, result):
                return result  # before any clone or build
            repo_url = validate_grammar_source(repo_url)
            if branch.startswith("-"):
                raise ValueError("Grammar branch must not start with '-'")
            # Step 1: Clone repository
            target_dir = self.grammars_dir / f"tree-sitter-{language}"
            if target_dir.exists():
                result["warnings"].append(f"Directory {target_dir} already exists")
                # Try to update instead
                try:
                    # Re-pin origin to the validated URL before fetching so the
                    # update never trusts a tampered stored remote (SUPPLY hardening).
                    subprocess.run(
                        ["git", "remote", "set-url", "origin", "--", repo_url],
                        cwd=target_dir,
                        check=False,
                        capture_output=True,
                        text=True,
                    )
                    subprocess.run(
                        ["git", "fetch", "origin"],
                        cwd=target_dir,
                        check=True,
                        capture_output=True,
                        text=True,
                    )
                    subprocess.run(
                        ["git", "checkout", "--detach", branch],
                        cwd=target_dir,
                        check=True,
                        capture_output=True,
                        text=True,
                    )
                    result["steps_completed"].append("Updated existing repository")
                except subprocess.CalledProcessError as e:
                    result["errors"].append(f"Failed to update repository: {e}")
                    result["status"] = "error"
                    return result
            else:
                try:
                    subprocess.run(
                        [
                            "git",
                            "clone",
                            "--branch",
                            branch,
                            "--",
                            repo_url,
                            str(target_dir),
                        ],
                        check=True,
                        capture_output=True,
                        text=True,
                    )
                    result["steps_completed"].append("Cloned repository")
                except subprocess.CalledProcessError as e:
                    result["errors"].append(f"Failed to clone repository: {e}")
                    result["status"] = "error"
                    return result

            # Step 2: Install dependencies
            package_json = target_dir / "package.json"
            if package_json.exists():
                try:
                    subprocess.run(
                        ["npm", "install"],
                        cwd=target_dir,
                        check=True,
                        capture_output=True,
                        text=True,
                    )
                    result["steps_completed"].append("Installed npm dependencies")
                except subprocess.CalledProcessError as e:
                    result["warnings"].append(
                        f"Failed to install npm dependencies: {e}",
                    )

            # Step 3: Generate grammar
            try:
                subprocess.run(
                    ["tree-sitter", "generate"],
                    cwd=target_dir,
                    check=True,
                    capture_output=True,
                    text=True,
                )
                result["steps_completed"].append("Generated grammar")
            except subprocess.CalledProcessError as e:
                result["errors"].append(f"Failed to generate grammar: {e}")
                result["status"] = "error"
                return result

            # Step 4: Copy .so file to build directory
            so_files = list(target_dir.glob("*.so"))
            if so_files:
                if self._refuse_shadowed_legacy_copy(language, result):
                    return result
                for so_file in so_files:
                    if not self._publish_library(language, so_file, result):
                        return result
                    result["steps_completed"].append(
                        f"Copied {so_file.name} to build directory",
                    )
            else:
                result["errors"].append("No .so files found after generation")
                result["status"] = "error"
                return result

            # Step 5: Validate installation
            health = self.manager.diagnose_grammar_issues(language)
            if health.status == "healthy":
                result["status"] = "success"
                result["steps_completed"].append("Validated grammar installation")
            else:
                result["status"] = "warning"
                result["warnings"].append(
                    f"Grammar installed but native admission failed: {health.validation_reason}",
                )

        except Exception as e:
            result["status"] = "error"
            result["errors"].append(f"Unexpected error: {e}")

        return result

    def remove_grammar(self, language: str) -> dict[str, Any]:
        """Remove a grammar and its source.

        Args:
            language: Language name to remove

        Returns:
            Removal result with status and details
        """
        result = {
            "language": language,
            "status": "unknown",
            "steps_completed": [],
            "errors": [],
            "warnings": [],
        }

        try:
            # Remove the requested language's native and legacy .so libraries
            removed_library = False
            for library in dict.fromkeys(self.manager._library_candidates(language)):
                if os.path.lexists(library):
                    library.unlink()
                    if not removed_library:
                        result["steps_completed"].append(
                            "Removed compiled grammar library"
                        )
                        removed_library = True
                    result["steps_completed"].append(
                        f"Removed compiled grammar library: {library.name}",
                    )
            if not removed_library:
                result["warnings"].append("No compiled grammar library found")

            # Remove source directory
            source_dir = self.grammars_dir / f"tree-sitter-{language}"
            if source_dir.exists():
                shutil.rmtree(source_dir)
                result["steps_completed"].append("Removed grammar source directory")
            else:
                result["warnings"].append("No grammar source directory found")

            result["status"] = "success"

        except Exception as e:
            result["status"] = "error"
            result["errors"].append(f"Failed to remove grammar: {e}")

        return result

    def update_grammar(self, language: str) -> dict[str, Any]:
        """Update a grammar to the latest version.

        Args:
            language: Language name to update

        Returns:
            Update result with status and details
        """
        result = {
            "language": language,
            "status": "unknown",
            "steps_completed": [],
            "errors": [],
            "warnings": [],
        }

        try:
            _require_language_component(language)
            if self._refuse_shipped_target(language, result):
                return result  # before any fetch or build
            source_dir = self.grammars_dir / f"tree-sitter-{language}"
            if not source_dir.exists():
                result["errors"].append(f"Grammar source not found: {source_dir}")
                return result

            # Update repository
            try:
                # Re-validate the stored origin before fetching so an existing
                # checkout with a tampered remote cannot pull attacker code
                # (SUPPLY hardening — codex finding on the update path).
                stored_origin = subprocess.run(
                    ["git", "remote", "get-url", "origin"],
                    cwd=source_dir,
                    capture_output=True,
                    text=True,
                    check=True,
                ).stdout.strip()
                validate_grammar_source(stored_origin)
                subprocess.run(
                    ["git", "fetch", "origin"],
                    cwd=source_dir,
                    check=True,
                    capture_output=True,
                    text=True,
                )
                result["steps_completed"].append("Fetched latest changes")

                # Get current and latest commit
                current = subprocess.run(
                    ["git", "rev-parse", "HEAD"],
                    cwd=source_dir,
                    capture_output=True,
                    text=True,
                    check=True,
                ).stdout.strip()

                latest = subprocess.run(
                    ["git", "rev-parse", "origin/main"],
                    cwd=source_dir,
                    capture_output=True,
                    text=True,
                    check=True,
                ).stdout.strip()

                if current == latest:
                    result["warnings"].append("Grammar is already up to date")
                    health = self.manager.diagnose_grammar_issues(language)
                    if health.status == "healthy":
                        result["status"] = "success"
                    else:
                        result["status"] = "warning"
                        result["warnings"].append(
                            f"Existing grammar failed native admission: {health.validation_reason}",
                        )
                    return result

                # Checkout latest
                subprocess.run(
                    ["git", "checkout", "--detach", "origin/main"],
                    cwd=source_dir,
                    check=True,
                    capture_output=True,
                    text=True,
                )
                result["steps_completed"].append("Updated to latest version")

            except subprocess.CalledProcessError as e:
                result["errors"].append(f"Failed to update repository: {e}")
                result["status"] = "error"
                return result

            # Reinstall dependencies if needed
            package_json = source_dir / "package.json"
            if package_json.exists():
                try:
                    subprocess.run(
                        ["npm", "install"],
                        cwd=source_dir,
                        check=True,
                        capture_output=True,
                        text=True,
                    )
                    result["steps_completed"].append("Updated dependencies")
                except subprocess.CalledProcessError as e:
                    result["warnings"].append(f"Failed to update dependencies: {e}")

            # Regenerate grammar
            try:
                subprocess.run(
                    ["tree-sitter", "generate"],
                    cwd=source_dir,
                    check=True,
                    capture_output=True,
                    text=True,
                )
                result["steps_completed"].append("Regenerated grammar")
            except subprocess.CalledProcessError as e:
                result["errors"].append(f"Failed to regenerate grammar: {e}")
                return result

            # Copy new .so file
            so_files = list(source_dir.glob("*.so"))
            if so_files:
                if self._refuse_shadowed_legacy_copy(language, result):
                    return result
                for so_file in so_files:
                    if not self._publish_library(language, so_file, result):
                        return result
                    result["steps_completed"].append("Updated compiled grammar library")
            else:
                result["errors"].append("No .so files found after regeneration")
                return result

            health = self.manager.diagnose_grammar_issues(language)
            if health.status == "healthy":
                result["status"] = "success"
            else:
                result["status"] = "warning"
                result["warnings"].append(
                    f"Updated grammar failed native admission: {health.validation_reason}",
                )

        except Exception as e:
            result["status"] = "error"
            result["errors"].append(f"Unexpected error during update: {e}")

        return result

    def list_installed_grammars(self) -> dict[str, Any]:
        """List all installed grammars with their status.

        Returns:
            Dictionary with grammar information
        """
        result = {
            "total_grammars": 0,
            "healthy_grammars": 0,
            "problematic_grammars": 0,
            "grammars": {},
        }

        languages = self.manager._library_languages()
        result["total_grammars"] = len(languages)

        for language in languages:
            health = self.manager.diagnose_grammar_issues(language)
            compatibility = self.manager.get_grammar_compatibility(language)

            grammar_info = {
                "status": health.status,
                "issues": health.issues,
                "recommendations": health.recommendations,
                "compatibility_score": compatibility.compatibility_score,
                "compilation_date": compatibility.compilation_date,
                "file_size": health.file_size,
                "validation_reason": health.validation_reason,
                "artifact_sha256": health.artifact_sha256,
            }

            result["grammars"][language] = grammar_info

            if health.status == "healthy":
                result["healthy_grammars"] += 1
            else:
                result["problematic_grammars"] += 1

        return result

    def get_grammar_info(self, language: str) -> dict[str, Any]:
        """Get detailed information about a specific grammar.

        Args:
            language: Language name

        Returns:
            Detailed grammar information
        """
        result = {
            "language": language,
            "health": None,
            "compatibility": None,
            "recovery_plan": None,
            "source_info": None,
        }

        # Get health status
        health = self.manager.diagnose_grammar_issues(language)
        result["health"] = health

        # Get compatibility info
        result["compatibility"] = self.manager.get_grammar_compatibility(language)

        # Get recovery plan if needed
        if health.status != "healthy":
            result["recovery_plan"] = self.manager.generate_recovery_plan(
                language, health=health
            )

        # Get source repository info
        source_dir = self.grammars_dir / f"tree-sitter-{language}"
        if source_dir.exists():
            try:
                # Get git info
                git_log = subprocess.run(
                    ["git", "log", "--oneline", "-1"],
                    cwd=source_dir,
                    capture_output=True,
                    text=True,
                    check=False,
                )

                git_remote = subprocess.run(
                    ["git", "remote", "get-url", "origin"],
                    cwd=source_dir,
                    capture_output=True,
                    text=True,
                    check=False,
                )

                result["source_info"] = {
                    "repository_url": (
                        git_remote.stdout.strip()
                        if git_remote.returncode == 0
                        else "unknown"
                    ),
                    "latest_commit": (
                        git_log.stdout.strip() if git_log.returncode == 0 else "unknown"
                    ),
                    "source_directory": str(source_dir),
                    "has_package_json": (source_dir / "package.json").exists(),
                    "has_grammar_js": (source_dir / "grammar.js").exists(),
                }
            except Exception:
                result["source_info"] = {
                    "error": "Could not retrieve source information",
                }

        return result

    def check_system_health(self) -> dict[str, Any]:
        """Check overall system health for grammar management.

        Returns:
            System health report
        """
        result = {
            "system_requirements": self.manager.get_system_requirements(),
            "directory_permissions": {},
            "recommendations": [],
        }

        # Check directory permissions
        for dir_path, dir_name in [
            (self.build_dir, "build directory"),
            (self.grammars_dir, "grammars directory"),
        ]:
            try:
                if dir_path.exists():
                    result["directory_permissions"][dir_name] = {
                        "exists": True,
                        "readable": os.access(dir_path, os.R_OK),
                        "writable": os.access(dir_path, os.W_OK),
                        "executable": os.access(dir_path, os.X_OK),
                    }
                else:
                    result["directory_permissions"][dir_name] = {"exists": False}
            except Exception as e:
                result["directory_permissions"][dir_name] = {"error": str(e)}

        # Generate recommendations
        requirements = result["system_requirements"]

        if not requirements["tree_sitter_cli"]:
            result["recommendations"].append(
                "Install tree-sitter CLI: npm install -g tree-sitter-cli",
            )

        if not requirements["node_npm"]:
            result["recommendations"].append(
                "Install Node.js and npm for grammar compilation",
            )

        if not requirements["git"]:
            result["recommendations"].append(
                "Install git for managing grammar repositories",
            )

        if not requirements["compiler"]:
            result["recommendations"].append(
                "Install a C compiler (gcc or clang) for building grammars",
            )

        if not requirements["python_deps"]:
            result["recommendations"].append(
                "Install Python tree-sitter package: pip install tree-sitter",
            )

        return result

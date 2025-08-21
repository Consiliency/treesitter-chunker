"""User-friendly tools for managing tree-sitter grammars."""

import json
import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from .grammar_management import GrammarCompatibility, GrammarHealth, SmartGrammarManager

logger = logging.getLogger(__name__)


class UserGrammarTools:
    """User-friendly tools for grammar management."""

    def __init__(self, build_dir: Path, grammars_dir: Path):
        """Initialize user grammar tools.

        Args:
            build_dir: Directory containing compiled .so files
            grammars_dir: Directory containing grammar source repositories
        """
        self.build_dir = Path(build_dir)
        self.grammars_dir = Path(grammars_dir)
        self.manager = SmartGrammarManager(build_dir, grammars_dir)

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
            # Step 1: Clone repository
            target_dir = self.grammars_dir / f"tree-sitter-{language}"
            if target_dir.exists():
                result["warnings"].append(f"Directory {target_dir} already exists")
                # Try to update instead
                try:
                    subprocess.run(
                        ["git", "fetch", "origin"],
                        cwd=target_dir,
                        check=True,
                        capture_output=True,
                        text=True,
                    )
                    subprocess.run(
                        ["git", "checkout", branch],
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
                        ["git", "clone", "--branch", branch, repo_url, str(target_dir)],
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
                for so_file in so_files:
                    target_so = self.build_dir / f"{language}.so"
                    shutil.copy2(so_file, target_so)
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
                    f"Grammar installed but has issues: {health.status}",
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
            # Remove .so file
            so_file = self.build_dir / f"{language}.so"
            if so_file.exists():
                so_file.unlink()
                result["steps_completed"].append("Removed compiled grammar library")
            else:
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
            source_dir = self.grammars_dir / f"tree-sitter-{language}"
            if not source_dir.exists():
                result["errors"].append(f"Grammar source not found: {source_dir}")
                return result

            # Update repository
            try:
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
                    result["status"] = "success"
                    return result

                # Checkout latest
                subprocess.run(
                    ["git", "checkout", "origin/main"],
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
                for so_file in so_files:
                    target_so = self.build_dir / f"{language}.so"
                    shutil.copy2(so_file, target_so)
                    result["steps_completed"].append("Updated compiled grammar library")
            else:
                result["errors"].append("No .so files found after regeneration")
                return result

            result["status"] = "success"

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

        # Get all .so files
        so_files = list(self.build_dir.glob("*.so"))
        result["total_grammars"] = len(so_files)

        for so_file in so_files:
            language = so_file.stem
            health = self.manager.diagnose_grammar_issues(language)
            compatibility = self.manager.get_grammar_compatibility(language)

            grammar_info = {
                "status": health.status,
                "issues": health.issues,
                "recommendations": health.recommendations,
                "compatibility_score": compatibility.compatibility_score,
                "compilation_date": compatibility.compilation_date,
                "file_size": so_file.stat().st_size if so_file.exists() else 0,
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
        result["health"] = self.manager.diagnose_grammar_issues(language)

        # Get compatibility info
        result["compatibility"] = self.manager.get_grammar_compatibility(language)

        # Get recovery plan if needed
        if result["health"].status != "healthy":
            result["recovery_plan"] = self.manager.generate_recovery_plan(language)

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

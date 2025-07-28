"""Git-aware repository processing capabilities."""

import hashlib
import json
import logging
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from chunker.interfaces.repo import GitAwareProcessor

from .patterns import GitignoreMatcher, load_gitignore_patterns

logger = logging.getLogger(__name__)


class GitAwareProcessorImpl(GitAwareProcessor):
    """Implementation of Git-aware processing capabilities."""

    def __init__(self):
        """Initialize the Git-aware processor."""
        self._gitignore_cache: dict[str, GitignoreMatcher] = {}
        self._state_dir = ".chunker"
        self._state_file = "incremental_state.json"

    def _run_git_command(self, cmd: list[str], repo_path: str) -> str | None:
        """
        Run a git command and return output.

        Args:
            cmd: Git command as list of arguments
            repo_path: Repository path

        Returns:
            Command output or None if failed
        """
        try:
            result = subprocess.run(
                ["git", *cmd],
                cwd=repo_path,
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            logger.debug(f"Git command failed: {' '.join(cmd)}, error: {e}")
            return None
        except FileNotFoundError:
            logger.warning("Git not found in PATH")
            return None

    def _is_git_repository(self, repo_path: str) -> bool:
        """Check if the given path is a git repository."""
        git_dir = Path(repo_path) / ".git"
        return git_dir.exists() and git_dir.is_dir()

    def get_changed_files(
        self,
        repo_path: str,
        since_commit: str | None = None,
        branch: str | None = None,
    ) -> list[str]:
        """
        Get files changed since a commit or between branches.

        Args:
            repo_path: Path to repository root
            since_commit: Commit hash or reference (HEAD~1, etc.)
            branch: Branch to compare against (default: current branch)

        Returns:
            List of changed file paths relative to repo root
        """
        if not self._is_git_repository(repo_path):
            logger.debug(f"{repo_path} is not a git repository")
            return []

        # Build git diff command
        cmd = ["diff", "--name-only"]

        if branch:
            # Compare against another branch
            cmd.append(f"{branch}...HEAD")
        elif since_commit:
            # Compare against specific commit
            cmd.append(since_commit)
        else:
            # Get uncommitted changes + staged changes
            staged = self._run_git_command(
                ["diff", "--cached", "--name-only"],
                repo_path,
            )
            unstaged = self._run_git_command(["diff", "--name-only"], repo_path)
            untracked = self._run_git_command(
                ["ls-files", "--others", "--exclude-standard"],
                repo_path,
            )

            files = set()
            if staged:
                files.update(staged.splitlines())
            if unstaged:
                files.update(unstaged.splitlines())
            if untracked:
                files.update(untracked.splitlines())

            return sorted(files)

        # Run the diff command
        output = self._run_git_command(cmd, repo_path)
        if output:
            return output.splitlines()
        return []

    def should_process_file(self, file_path: str, repo_path: str) -> bool:
        """
        Check if file should be processed based on git status and .gitignore.

        Args:
            file_path: Path to file
            repo_path: Path to repository root

        Returns:
            True if file should be processed
        """
        # Get or create gitignore matcher for this repo
        if repo_path not in self._gitignore_cache:
            self._gitignore_cache[repo_path] = load_gitignore_patterns(Path(repo_path))

        matcher = self._gitignore_cache[repo_path]

        # Check if file is ignored
        file_path_obj = Path(file_path)
        if file_path_obj.is_absolute():
            try:
                file_path_obj = file_path_obj.relative_to(repo_path)
            except ValueError:
                # File is not in repo
                return False

        return not matcher.should_ignore(file_path_obj, is_dir=False)

    def get_file_history(
        self,
        file_path: str,
        repo_path: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Get commit history for a file.

        Args:
            file_path: Path to file
            repo_path: Path to repository root
            limit: Maximum number of commits

        Returns:
            List of commit info dicts with hash, author, date, message
        """
        if not self._is_git_repository(repo_path):
            return []

        # Make file path relative to repo
        file_path_obj = Path(file_path)
        if file_path_obj.is_absolute():
            try:
                file_path_obj = file_path_obj.relative_to(repo_path)
            except ValueError:
                return []

        # Get commit log for file
        cmd = [
            "log",
            f"--max-count={limit}",
            "--pretty=format:%H|%an|%ae|%at|%s",
            "--",
            str(file_path_obj),
        ]

        output = self._run_git_command(cmd, repo_path)
        if not output:
            return []

        commits = []
        for line in output.splitlines():
            parts = line.split("|", 4)
            if len(parts) == 5:
                commits.append(
                    {
                        "hash": parts[0],
                        "author": parts[1],
                        "email": parts[2],
                        "date": datetime.fromtimestamp(int(parts[3])).isoformat(),
                        "message": parts[4],
                    },
                )

        return commits

    def load_gitignore_patterns(self, repo_path: str) -> list[str]:
        """
        Load and parse .gitignore patterns.

        Args:
            repo_path: Path to repository root

        Returns:
            List of gitignore patterns
        """
        patterns = []
        repo_path_obj = Path(repo_path)

        # Find all .gitignore files
        for gitignore_path in repo_path_obj.rglob(".gitignore"):
            try:
                with open(gitignore_path, encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#"):
                            # Add the pattern with its directory context
                            rel_dir = gitignore_path.parent.relative_to(repo_path_obj)
                            if rel_dir != Path():
                                # Prefix pattern with its directory
                                patterns.append(f"{rel_dir}/{line}")
                            else:
                                patterns.append(line)
            except Exception as e:
                logger.debug(f"Error reading {gitignore_path}: {e}")

        return patterns

    def save_incremental_state(self, repo_path: str, state: dict[str, Any]) -> None:
        """
        Save incremental processing state.

        Args:
            repo_path: Path to repository root
            state: State to save (last commit, file hashes, etc.)
        """
        state_dir = Path(repo_path) / self._state_dir
        state_dir.mkdir(exist_ok=True)

        # Add metadata
        state["timestamp"] = datetime.now().isoformat()
        state["version"] = "1.0"

        # Get current commit if in git repo
        if self._is_git_repository(repo_path):
            commit = self._run_git_command(["rev-parse", "HEAD"], repo_path)
            if commit:
                state["last_commit"] = commit

        # Save state
        state_file = state_dir / self._state_file
        try:
            with open(state_file, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save incremental state: {e}")

    def load_incremental_state(self, repo_path: str) -> dict[str, Any] | None:
        """
        Load incremental processing state.

        Args:
            repo_path: Path to repository root

        Returns:
            Saved state or None
        """
        state_file = Path(repo_path) / self._state_dir / self._state_file

        if not state_file.exists():
            return None

        try:
            with open(state_file, encoding="utf-8") as f:
                state = json.load(f)

            # Validate state version
            if state.get("version") != "1.0":
                logger.warning(f"Incompatible state version: {state.get('version')}")
                return None

            return state
        except Exception as e:
            logger.error(f"Failed to load incremental state: {e}")
            return None

    def get_file_hash(self, file_path: Path) -> str:
        """
        Calculate hash of file contents for change detection.

        Args:
            file_path: Path to file

        Returns:
            SHA256 hash of file contents
        """
        try:
            with open(file_path, "rb") as f:
                return hashlib.sha256(f.read()).hexdigest()
        except Exception:
            return ""

    def clear_cache(self):
        """Clear internal caches."""
        self._gitignore_cache.clear()

"""Repository-level processing interfaces."""

from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from chunker.types import CodeChunk


@dataclass
class FileChunkResult:
    """Result of chunking a single file."""

    file_path: str
    chunks: list[CodeChunk]
    error: Exception | None = None
    processing_time: float = 0.0


@dataclass
class RepoChunkResult:
    """Result of processing an entire repository."""

    repo_path: str
    file_results: list[FileChunkResult]
    total_chunks: int
    total_files: int
    skipped_files: list[str]
    errors: dict[str, Exception]
    processing_time: float
    metadata: dict[str, Any]


class RepoProcessor(ABC):
    """Process entire repositories efficiently."""

    @abstractmethod
    def process_repository(
        self,
        repo_path: str,
        incremental: bool = True,
        file_pattern: str | None = None,
        exclude_patterns: list[str] | None = None,
    ) -> RepoChunkResult:
        """
        Process all files in a repository.

        Args:
            repo_path: Path to repository root
            incremental: Only process changed files since last run
            file_pattern: Glob pattern for files to include
            exclude_patterns: List of glob patterns to exclude

        Returns:
            Repository processing result
        """

    @abstractmethod
    def process_files_iterator(
        self,
        repo_path: str,
        file_pattern: str | None = None,
        exclude_patterns: list[str] | None = None,
    ) -> Iterator[FileChunkResult]:
        """
        Process repository files as an iterator for memory efficiency.

        Args:
            repo_path: Path to repository root
            file_pattern: Glob pattern for files to include
            exclude_patterns: List of glob patterns to exclude

        Yields:
            File processing results one at a time
        """

    @abstractmethod
    def estimate_processing_time(self, repo_path: str) -> float:
        """
        Estimate time to process repository.

        Args:
            repo_path: Path to repository root

        Returns:
            Estimated seconds
        """

    @abstractmethod
    def get_processable_files(
        self,
        repo_path: str,
        file_pattern: str | None = None,
        exclude_patterns: list[str] | None = None,
    ) -> list[Path]:
        """
        Get list of files that would be processed.

        Args:
            repo_path: Path to repository root
            file_pattern: Glob pattern for files to include
            exclude_patterns: List of glob patterns to exclude

        Returns:
            List of file paths
        """


class GitAwareProcessor(ABC):
    """Git-aware processing capabilities."""

    @abstractmethod
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

    @abstractmethod
    def should_process_file(self, file_path: str, repo_path: str) -> bool:
        """
        Check if file should be processed based on git status and .gitignore.

        Args:
            file_path: Path to file
            repo_path: Path to repository root

        Returns:
            True if file should be processed
        """

    @abstractmethod
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

    @abstractmethod
    def load_gitignore_patterns(self, repo_path: str) -> list[str]:
        """
        Load and parse .gitignore patterns.

        Args:
            repo_path: Path to repository root

        Returns:
            List of gitignore patterns
        """

    @abstractmethod
    def save_incremental_state(self, repo_path: str, state: dict[str, Any]) -> None:
        """
        Save incremental processing state.

        Args:
            repo_path: Path to repository root
            state: State to save (last commit, file hashes, etc.)
        """

    @abstractmethod
    def load_incremental_state(self, repo_path: str) -> dict[str, Any] | None:
        """
        Load incremental processing state.

        Args:
            repo_path: Path to repository root

        Returns:
            Saved state or None
        """

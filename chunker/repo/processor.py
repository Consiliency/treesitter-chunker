"""Repository processor implementation with Git awareness."""

import json
import os
import time
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any

import git
import pathspec
from tqdm import tqdm

from chunker.exceptions import ChunkerError
from chunker.interfaces.repo import FileChunkResult, GitAwareProcessor, RepoChunkResult
from chunker.interfaces.repo import RepoProcessor as RepoProcessorInterface

from .chunker_adapter import Chunker


class RepoProcessor(RepoProcessorInterface):
    """Process entire repositories efficiently."""

    def __init__(
        self,
        chunker: Chunker | None = None,
        max_workers: int = 4,
        show_progress: bool = True,
        traversal_strategy: str = "depth-first",
    ):
        """
        Initialize repository processor.

        Args:
            chunker: Chunker instance to use (creates default if None)
            max_workers: Maximum number of parallel workers
            show_progress: Whether to show progress bar
            traversal_strategy: "depth-first" or "breadth-first"
        """
        self.chunker = chunker or Chunker()
        self.max_workers = max_workers
        self.show_progress = show_progress
        self.traversal_strategy = traversal_strategy
        self._language_extensions = self._build_language_extension_map()

    def _build_language_extension_map(self) -> dict[str, str]:
        """Build map of file extensions to language names."""
        extension_map = {
            ".py": "python",
            ".js": "javascript",
            ".jsx": "javascript",
            ".ts": "javascript",
            ".tsx": "javascript",
            ".c": "c",
            ".h": "c",
            ".cpp": "cpp",
            ".cc": "cpp",
            ".cxx": "cpp",
            ".hpp": "cpp",
            ".hxx": "cpp",
            ".rs": "rust",
            ".go": "go",
            ".java": "java",
            ".rb": "ruby",
        }
        return extension_map

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
        start_time = time.time()
        repo_path = Path(repo_path).resolve()

        if not repo_path.exists():
            raise ChunkerError(f"Repository path does not exist: {repo_path}")

        # Get files to process
        files_to_process = self.get_processable_files(
            str(repo_path),
            file_pattern,
            exclude_patterns,
        )

        # Filter for incremental processing if needed
        if incremental and hasattr(self, "get_changed_files"):
            state = self.load_incremental_state(str(repo_path))
            if state and "last_commit" in state:
                changed_files = self.get_changed_files(
                    str(repo_path),
                    since_commit=state["last_commit"],
                )
                changed_paths = {repo_path / f for f in changed_files}
                files_to_process = [f for f in files_to_process if f in changed_paths]

        # Process files
        file_results = []
        errors = {}
        skipped_files = []
        total_chunks = 0

        # Progress tracking
        progress_bar = None
        if self.show_progress:
            progress_bar = tqdm(total=len(files_to_process), desc="Processing files")

        try:
            # Process files in parallel
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # Submit all files for processing
                future_to_file = {
                    executor.submit(
                        self._process_single_file,
                        file_path,
                        repo_path,
                    ): file_path
                    for file_path in files_to_process
                }

                # Collect results
                for future in as_completed(future_to_file):
                    file_path = future_to_file[future]
                    try:
                        result = future.result()
                        if result:
                            file_results.append(result)
                            total_chunks += len(result.chunks)
                            if result.error:
                                errors[str(file_path)] = result.error
                        else:
                            skipped_files.append(str(file_path))
                    except (FileNotFoundError, IndexError, KeyError) as e:
                        errors[str(file_path)] = e
                        skipped_files.append(str(file_path))

                    if progress_bar:
                        progress_bar.update(1)
        finally:
            if progress_bar:
                progress_bar.close()

        # Save incremental state if Git-aware
        if incremental and hasattr(self, "save_incremental_state"):
            try:
                repo = git.Repo(repo_path)
                state = {
                    "last_commit": repo.head.commit.hexsha,
                    "processed_at": datetime.now().isoformat(),
                    "total_files": len(file_results),
                    "total_chunks": total_chunks,
                }
                self.save_incremental_state(str(repo_path), state)
            except (AttributeError, FileNotFoundError, OSError):
                pass  # Not a git repo or other error

        processing_time = time.time() - start_time

        return RepoChunkResult(
            repo_path=str(repo_path),
            file_results=file_results,
            total_chunks=total_chunks,
            total_files=len(files_to_process),
            skipped_files=skipped_files,
            errors=errors,
            processing_time=processing_time,
            metadata={
                "traversal_strategy": self.traversal_strategy,
                "max_workers": self.max_workers,
                "incremental": incremental,
            },
        )

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
        repo_path = Path(repo_path).resolve()
        files_to_process = self.get_processable_files(
            str(repo_path),
            file_pattern,
            exclude_patterns,
        )

        for file_path in files_to_process:
            result = self._process_single_file(file_path, repo_path)
            if result:
                yield result

    def estimate_processing_time(self, repo_path: str) -> float:
        """
        Estimate time to process repository.

        Args:
            repo_path: Path to repository root

        Returns:
            Estimated seconds
        """
        files = self.get_processable_files(repo_path)

        # Estimate based on file sizes and types
        total_size = 0
        language_counts = {}

        for file_path in files:
            try:
                size = file_path.stat().st_size
                total_size += size

                ext = file_path.suffix.lower()
                if ext in self._language_extensions:
                    lang = self._language_extensions[ext]
                    language_counts[lang] = language_counts.get(lang, 0) + 1
            except (AttributeError, FileNotFoundError, IndexError):
                pass

        # Rough estimates: 1MB/sec with overhead per file
        base_time = total_size / (1024 * 1024)  # MB/sec
        file_overhead = len(files) * 0.1  # 0.1 sec per file

        return base_time + file_overhead

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
        repo_path = Path(repo_path).resolve()

        # Default exclude patterns
        default_excludes = [
            "__pycache__",
            "*.pyc",
            ".git",
            ".svn",
            ".hg",
            "node_modules",
            "venv",
            ".venv",
            "env",
            ".env",
            "*.egg-info",
            "dist",
            "build",
            ".idea",
            ".vscode",
            "*.so",
            "*.dylib",
            "*.dll",
            "*.exe",
        ]

        if exclude_patterns:
            all_excludes = default_excludes + exclude_patterns
        else:
            all_excludes = default_excludes

        # Build pathspec for exclusions
        exclude_spec = pathspec.PathSpec.from_lines("gitwildmatch", all_excludes)

        # Get all files based on traversal strategy
        files = []

        if self.traversal_strategy == "breadth-first":
            # Breadth-first traversal
            dirs_to_process = [repo_path]
            while dirs_to_process:
                current_dir = dirs_to_process.pop(0)
                try:
                    for item in current_dir.iterdir():
                        if item.is_dir():
                            if not exclude_spec.match_file(
                                str(item.relative_to(repo_path)),
                            ):
                                dirs_to_process.append(item)
                        elif item.is_file():
                            rel_path = item.relative_to(repo_path)
                            if not exclude_spec.match_file(str(rel_path)) and self._should_process_file(item, file_pattern):
                                    files.append(item)
                except PermissionError:
                    pass
        else:
            # Depth-first traversal (default)
            for root, dirs, filenames in os.walk(repo_path):
                root_path = Path(root)
                rel_root = root_path.relative_to(repo_path)

                # Filter directories
                dirs[:] = [
                    d for d in dirs if not exclude_spec.match_file(str(rel_root / d))
                ]

                # Process files
                for filename in filenames:
                    file_path = root_path / filename
                    rel_path = file_path.relative_to(repo_path)

                    if not exclude_spec.match_file(str(rel_path)) and self._should_process_file(file_path, file_pattern):
                            files.append(file_path)

        return sorted(files)

    def _should_process_file(self, file_path: Path, file_pattern: str | None) -> bool:
        """Check if file should be processed based on extension and pattern."""
        # Check pattern first
        if file_pattern and not file_path.match(file_pattern):
            return False

        # Check if we support this file type
        ext = file_path.suffix.lower()
        return ext in self._language_extensions

    def _process_single_file(
        self,
        file_path: Path,
        repo_path: Path,
    ) -> FileChunkResult | None:
        """Process a single file and return results."""
        start_time = time.time()
        rel_path = file_path.relative_to(repo_path)

        try:
            # Determine language
            ext = file_path.suffix.lower()
            language = self._language_extensions.get(ext)

            if not language:
                return None

            # Read file content
            try:
                content = file_path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                # Try alternative encodings
                for encoding in ["latin-1", "cp1252"]:
                    try:
                        content = file_path.read_text(encoding=encoding)
                        break
                    except (OSError, FileNotFoundError, IndexError):
                        continue
                else:
                    return FileChunkResult(
                        file_path=str(rel_path),
                        chunks=[],
                        error=ChunkerError(f"Unable to decode file: {rel_path}"),
                        processing_time=time.time() - start_time,
                    )

            # Chunk the file
            chunks = self.chunker.chunk(content, language=language)

            # Add file path to chunk metadata
            for chunk in chunks:
                if not chunk.metadata:
                    chunk.metadata = {}
                chunk.metadata["file_path"] = str(rel_path)
                chunk.metadata["repo_path"] = str(repo_path)

            return FileChunkResult(
                file_path=str(rel_path),
                chunks=chunks,
                processing_time=time.time() - start_time,
            )

        except (FileNotFoundError, IndexError, KeyError) as e:
            return FileChunkResult(
                file_path=str(rel_path),
                chunks=[],
                error=e,
                processing_time=time.time() - start_time,
            )


class GitAwareRepoProcessor(RepoProcessor, GitAwareProcessor):
    """Repository processor with Git awareness."""

    def __init__(self, *args, **kwargs):
        """Initialize Git-aware processor."""
        super().__init__(*args, **kwargs)
        self._incremental_state_file = ".chunker_state.json"

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
        try:
            repo = git.Repo(repo_path)

            if branch:
                # Compare with another branch
                diff = repo.head.commit.diff(branch)
            elif since_commit:
                # Compare with specific commit
                diff = repo.commit(since_commit).diff(repo.head.commit)
            # Default to changes since last commit
            elif repo.head.is_valid():
                diff = repo.head.commit.diff("HEAD~1")
            else:
                # No commits yet
                return []

            changed_files = []
            for item in diff:
                # Get the path that exists
                path = item.b_path if item.b_path else item.a_path
                if path and Path(repo_path, path).exists():
                    changed_files.append(path)

            return changed_files

        except git.InvalidGitRepositoryError:
            raise ChunkerError(f"Not a valid git repository: {repo_path}")
        except git.GitCommandError as e:
            raise ChunkerError(f"Git error: {e}")

    def should_process_file(self, file_path: str, repo_path: str) -> bool:
        """
        Check if file should be processed based on git status and .gitignore.

        Args:
            file_path: Path to file
            repo_path: Path to repository root

        Returns:
            True if file should be processed
        """
        try:
            repo = git.Repo(repo_path)

            # Check if file is ignored by git
            try:
                repo.git.check_ignore(file_path)
                return False  # File is ignored
            except git.GitCommandError:
                # File is not ignored
                pass

            # Check if file is tracked
            rel_path = Path(file_path).relative_to(repo_path)
            if str(rel_path) not in [item.path for item in repo.index.entries]:
                # Check if it's untracked but not ignored
                untracked = repo.untracked_files
                if str(rel_path) in untracked:
                    return True  # Process untracked files
                return False

            return True

        except (FileNotFoundError, IndexError, KeyError):
            # If git operations fail, fall back to processing the file
            return True

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
        try:
            repo = git.Repo(repo_path)
            rel_path = Path(file_path).relative_to(repo_path)

            commits = list(repo.iter_commits(paths=str(rel_path), max_count=limit))

            history = []
            for commit in commits:
                history.append(
                    {
                        "hash": commit.hexsha,
                        "author": str(commit.author),
                        "date": commit.committed_datetime.isoformat(),
                        "message": commit.message.strip(),
                    },
                )

            return history

        except (FileNotFoundError, IndexError, KeyError) as e:
            raise ChunkerError(f"Error getting file history: {e}")

    def load_gitignore_patterns(self, repo_path: str) -> list[str]:
        """
        Load and parse .gitignore patterns.

        Args:
            repo_path: Path to repository root

        Returns:
            List of gitignore patterns
        """
        patterns = []
        gitignore_path = Path(repo_path) / ".gitignore"

        if gitignore_path.exists():
            try:
                with Path(gitignore_path).open("r") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#"):
                            patterns.append(line)
            except (OSError, FileNotFoundError, IndexError):
                pass

        # Also check for global gitignore
        try:
            repo = git.Repo(repo_path)
            excludes_file = repo.config_reader().get_value("core", "excludesfile", None)
            if excludes_file:
                excludes_path = Path(excludes_file).expanduser()
                if excludes_path.exists():
                    with Path(excludes_path).open("r") as f:
                        for line in f:
                            line = line.strip()
                            if line and not line.startswith("#"):
                                patterns.append(line)
        except (OSError, FileNotFoundError, IndexError):
            pass

        return patterns

    def save_incremental_state(self, repo_path: str, state: dict[str, Any]) -> None:
        """
        Save incremental processing state.

        Args:
            repo_path: Path to repository root
            state: State to save (last commit, file hashes, etc.)
        """
        state_path = Path(repo_path) / self._incremental_state_file

        try:
            with Path(state_path).open("w") as f:
                json.dump(state, f, indent=2)
        except (OSError, FileNotFoundError, IndexError):
            # Log error but don't fail
            pass

    def load_incremental_state(self, repo_path: str) -> dict[str, Any] | None:
        """
        Load incremental processing state.

        Args:
            repo_path: Path to repository root

        Returns:
            Saved state or None
        """
        state_path = Path(repo_path) / self._incremental_state_file

        if state_path.exists():
            try:
                with Path(state_path).open("r") as f:
                    return json.load(f)
            except (OSError, FileNotFoundError, IndexError):
                pass

        return None

    def get_processable_files(
        self,
        repo_path: str,
        file_pattern: str | None = None,
        exclude_patterns: list[str] | None = None,
    ) -> list[Path]:
        """
        Override to use gitignore patterns.

        Args:
            repo_path: Path to repository root
            file_pattern: Glob pattern for files to include
            exclude_patterns: List of glob patterns to exclude

        Returns:
            List of file paths
        """
        # Get base list from parent
        files = super().get_processable_files(repo_path, file_pattern, exclude_patterns)

        # If it's a git repo, filter using git
        try:
            git.Repo(repo_path)

            # Load gitignore patterns
            gitignore_patterns = self.load_gitignore_patterns(repo_path)
            if gitignore_patterns:
                gitignore_spec = pathspec.PathSpec.from_lines(
                    "gitwildmatch",
                    gitignore_patterns,
                )

                # Filter files
                filtered_files = []
                for file_path in files:
                    rel_path = file_path.relative_to(repo_path)
                    if not gitignore_spec.match_file(str(rel_path)) and self.should_process_file(str(file_path), repo_path):
                            filtered_files.append(file_path)

                return filtered_files
        except (FileNotFoundError, IndexError, KeyError):
            # Not a git repo, return original list
            pass

        return files

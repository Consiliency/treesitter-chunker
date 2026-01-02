"""Repository processor implementation with Git awareness."""

import json
import os
import time
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor, as_completed
from configparser import NoOptionError
from datetime import datetime
from pathlib import Path
from typing import Any

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
        self._git = None
        self._language_extensions = self._build_language_extension_map()

    @property
    def git(self):
        """Lazy import of git module to avoid circular imports."""
        if self._git is None:
            import git

            self._git = git
        return self._git

    @staticmethod
    def _build_language_extension_map() -> dict[str, str]:
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
        max_workers: int | None = None,
    ) -> RepoChunkResult:
        """
        Process all files in a repository.

        Args:
            repo_path: Path to repository root
            incremental: Only process changed files since last run
            file_pattern: Glob pattern for files to include
            exclude_patterns: List of glob patterns to exclude
            max_workers: Maximum number of parallel workers (overrides instance setting)

        Returns:
            Repository processing result
        """
        start_time = time.time()
        repo_path = Path(repo_path).resolve()
        if not repo_path.exists():
            raise ChunkerError(f"Repository path does not exist: {repo_path}")
        files_to_process = self.get_processable_files(
            str(repo_path),
            file_pattern,
            exclude_patterns,
        )
        if incremental and hasattr(self, "get_changed_files"):
            state = self.load_incremental_state(str(repo_path))
            if state and "last_commit" in state:
                changed_files = self.get_changed_files(
                    str(repo_path),
                    since_commit=state["last_commit"],
                )
                changed_paths = {(repo_path / f) for f in changed_files}
                files_to_process = [f for f in files_to_process if f in changed_paths]
        # Process files in parallel
        processing_result = self._process_files_parallel(
            files_to_process,
            repo_path,
            max_workers,
        )

        file_results = processing_result["file_results"]
        errors = processing_result["errors"]
        skipped_files = processing_result["skipped_files"]
        total_chunks = processing_result["total_chunks"]
        if incremental and hasattr(self, "save_incremental_state"):
            try:
                repo = self.git.Repo(repo_path)
                state = {
                    "last_commit": repo.head.commit.hexsha,
                    "processed_at": datetime.now().isoformat(),
                    "total_files": len(file_results),
                    "total_chunks": total_chunks,
                }
                self.save_incremental_state(str(repo_path), state)
            except (AttributeError, FileNotFoundError, OSError):
                pass
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
        total_size = 0
        language_counts = {}
        for file_path in files:
            # Use LBYL pattern to avoid try-except in loop
            if file_path.exists():
                try:
                    stat_info = file_path.stat()
                    total_size += stat_info.st_size
                    ext = file_path.suffix.lower()
                    if ext in self._language_extensions:
                        lang = self._language_extensions[ext]
                        language_counts[lang] = language_counts.get(lang, 0) + 1
                except (AttributeError, OSError):
                    # Handle rare cases where file is deleted between exists() and stat()
                    pass
        base_time = total_size / (1024 * 1024)
        file_overhead = len(files) * 0.1
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
        exclude_spec = pathspec.PathSpec.from_lines("gitwildmatch", all_excludes)
        files = []
        if self.traversal_strategy == "breadth-first":
            files = self._traverse_breadth_first(repo_path, exclude_spec, file_pattern)
        else:
            files = self._traverse_depth_first(repo_path, exclude_spec, file_pattern)
        return sorted(files)

    def _process_files_parallel(
        self,
        files_to_process: list[Path],
        repo_path: Path,
        max_workers: int | None = None,
    ) -> dict[str, Any]:
        """Process files in parallel and return results."""
        file_results = []
        errors = []
        skipped_files = []
        total_chunks = 0

        if self.show_progress:
            pbar = tqdm(total=len(files_to_process), desc="Processing files")

        effective_max_workers = (
            max_workers if max_workers is not None else self.max_workers
        )
        with ThreadPoolExecutor(max_workers=effective_max_workers) as executor:
            futures = {
                executor.submit(
                    self._process_single_file,
                    file_path,
                    repo_path,
                ): file_path
                for file_path in files_to_process
            }

            for future in as_completed(futures):
                file_path = futures[future]
                rel_path = file_path.relative_to(repo_path)

                try:
                    result = future.result()
                    if result:
                        file_results.append(result)
                        total_chunks += len(result.chunks)
                    else:
                        skipped_files.append(str(rel_path))
                except Exception as e:
                    errors.append(
                        {
                            "file": str(rel_path),
                            "error": str(e),
                            "type": type(e).__name__,
                        },
                    )

                if self.show_progress:
                    pbar.update(1)

        if self.show_progress:
            pbar.close()

        return {
            "file_results": file_results,
            "errors": errors,
            "skipped_files": skipped_files,
            "total_chunks": total_chunks,
        }

    def _should_process_file(
        self,
        file_path: Path,
        file_pattern: str | None,
    ) -> bool:
        """Check if file should be processed based on extension and pattern."""
        if file_pattern and not file_path.match(file_pattern):
            return False
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
            ext = file_path.suffix.lower()
            language = self._language_extensions.get(ext)
            if not language:
                return None
            content = RepoProcessor._read_file_with_fallback_encoding(
                file_path,
                rel_path,
                start_time,
            )
            if isinstance(content, FileChunkResult):
                return content
            chunks = self.chunker.chunk(content, language=language)
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

    def _traverse_breadth_first(
        self,
        repo_path: Path,
        exclude_spec: pathspec.PathSpec,
        file_pattern: str | None,
    ) -> list[Path]:
        """Traverse directory tree breadth-first."""
        files = []
        dirs_to_process = [repo_path]

        while dirs_to_process:
            current_dir = dirs_to_process.pop(0)
            items = RepoProcessor._get_directory_items(current_dir)

            for item in items:
                if item.is_dir():
                    if RepoProcessor._should_include_directory(
                        item,
                        repo_path,
                        exclude_spec,
                    ):
                        dirs_to_process.append(item)
                elif item.is_file() and self._should_include_file(
                    item,
                    repo_path,
                    exclude_spec,
                    file_pattern,
                ):
                    files.append(item)

        return files

    def _traverse_depth_first(
        self,
        repo_path: Path,
        exclude_spec: pathspec.PathSpec,
        file_pattern: str | None,
    ) -> list[Path]:
        """Traverse directory tree depth-first."""
        files = []

        for root, dirs, filenames in os.walk(repo_path):
            root_path = Path(root)
            rel_root = root_path.relative_to(repo_path)

            # Filter directories in-place
            dirs[:] = [
                d for d in dirs if not exclude_spec.match_file(str(rel_root / d))
            ]

            # Process files
            for filename in filenames:
                file_path = root_path / filename
                if self._should_include_file(
                    file_path,
                    repo_path,
                    exclude_spec,
                    file_pattern,
                ):
                    files.append(file_path)

        return files

    @staticmethod
    def _get_directory_items(directory: Path) -> list[Path]:
        """Get directory items, handling permission errors."""
        try:
            return list(directory.iterdir())
        except PermissionError:
            return []

    @staticmethod
    def _should_include_directory(
        directory: Path,
        repo_path: Path,
        exclude_spec: pathspec.PathSpec,
    ) -> bool:
        """Check if directory should be included in traversal."""
        rel_path = directory.relative_to(repo_path)
        return not exclude_spec.match_file(str(rel_path))

    def _should_include_file(
        self,
        file_path: Path,
        repo_path: Path,
        exclude_spec: pathspec.PathSpec,
        file_pattern: str | None,
    ) -> bool:
        """Check if file should be included in processing."""
        rel_path = file_path.relative_to(repo_path)
        return not exclude_spec.match_file(str(rel_path)) and self._should_process_file(
            file_path,
            file_pattern,
        )

    @staticmethod
    def _read_file_with_fallback_encoding(
        file_path: Path,
        rel_path: Path,
        start_time: float,
    ) -> str | FileChunkResult:
        """Read file with fallback encoding support."""
        try:
            return file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            pass

        # Try fallback encodings
        for encoding in ["latin-1", "cp1252"]:
            try:
                return file_path.read_text(encoding=encoding)
            except (OSError, FileNotFoundError, IndexError):
                continue

        # Unable to decode file
        return FileChunkResult(
            file_path=str(rel_path),
            chunks=[],
            error=ChunkerError(f"Unable to decode file: {rel_path}"),
            processing_time=time.time() - start_time,
        )

    @staticmethod
    def read_ignore_patterns(file_path: Path) -> list[str]:
        """Read ignore patterns from a file."""
        patterns = []
        try:
            with file_path.open("r", encoding="utf-8") as f:
                for line in f:
                    stripped_line = line.strip()
                    if stripped_line and not stripped_line.startswith("#"):
                        patterns.append(stripped_line)
        except (OSError, FileNotFoundError, IndexError):
            pass
        return patterns


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
            repo = self.git.Repo(repo_path)
            if branch:
                diff = repo.head.commit.diff(branch)
            elif since_commit:
                diff = repo.commit(since_commit).diff(repo.head.commit)
            elif repo.head.is_valid():
                try:
                    # Check if HEAD~1 exists
                    repo.commit("HEAD~1")
                    diff = repo.head.commit.diff("HEAD~1")
                except (self.git.BadName, self.git.GitCommandError):
                    # No previous commit (initial commit scenario)
                    return []
            else:
                return []
            changed_files = []
            for item in diff:
                path = item.b_path if item.b_path else item.a_path
                if path and Path(repo_path, path).exists():
                    changed_files.append(path)
            return changed_files
        except self.git.InvalidGitRepositoryError:
            # Not a git repository, return empty list
            return []
        except self.git.GitCommandError as e:
            raise ChunkerError(f"Git error: {e}") from e

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
            repo = self.git.Repo(repo_path)
            try:
                repo.git.check_ignore(file_path)
                return False
            except self.git.GitCommandError:
                pass
            rel_path = Path(file_path).relative_to(repo_path)
            tracked_files = {path for path, stage in repo.index.entries.keys()}
            if str(rel_path) not in tracked_files:
                untracked = repo.untracked_files
                return str(rel_path) in untracked
            return True
        except (FileNotFoundError, IndexError, KeyError):
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
            repo = self.git.Repo(repo_path)
            rel_path = Path(file_path).relative_to(repo_path)
            commits = list(repo.iter_commits(paths=str(rel_path), max_count=limit))
            history = [
                {
                    "hash": commit.hexsha,
                    "author": str(commit.author),
                    "date": commit.committed_datetime.isoformat(),
                    "message": commit.message.strip(),
                }
                for commit in commits
            ]
            return history
        except (FileNotFoundError, IndexError, KeyError) as e:
            raise ChunkerError(f"Error getting file history: {e}") from e

    def load_gitignore_patterns(self, repo_path: str) -> list[str]:
        """
        Load and parse .gitignore patterns.

        Args:
            repo_path: Path to repository root

        Returns:
            List of gitignore patterns
        """
        patterns = []

        # Load patterns from .gitignore file
        gitignore_path = Path(repo_path) / ".gitignore"
        if gitignore_path.exists():
            patterns.extend(RepoProcessor.read_ignore_patterns(gitignore_path))

        # Load patterns from global excludes file
        excludes_path = self._get_global_excludes_path(repo_path)
        if excludes_path and excludes_path.exists():
            patterns.extend(RepoProcessor.read_ignore_patterns(excludes_path))

        return patterns

    def _get_global_excludes_path(self, repo_path: str) -> Path | None:
        """Get the path to the global excludes file."""
        try:
            repo = self.git.Repo(repo_path)
            # Check if repository is bare
            if repo.bare:
                return None
            config_reader = repo.config_reader()
            try:
                excludes_file = config_reader.get_value("core", "excludesfile")
                if excludes_file:
                    return Path(excludes_file).expanduser()
            except (KeyError, AttributeError, NoOptionError):
                # No excludesfile configured, which is normal
                pass
        except (
            OSError,
            FileNotFoundError,
            IndexError,
            self.git.InvalidGitRepositoryError,
        ):
            pass
        return None

    def save_incremental_state(
        self,
        repo_path: str,
        state: dict[str, Any],
    ) -> None:
        """
        Save incremental processing state.

        Args:
            repo_path: Path to repository root
            state: State to save (last commit, file hashes, etc.)
        """
        state_path = Path(repo_path) / self._incremental_state_file
        try:
            with Path(state_path).open("w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)
        except (OSError, FileNotFoundError, IndexError):
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
                with Path(state_path).open("r", encoding="utf-8") as f:
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
        files = super().get_processable_files(repo_path, file_pattern, exclude_patterns)
        try:
            repo = self.git.Repo(repo_path)
            # Check if repository is bare
            if repo.bare:
                from chunker.exceptions import ChunkerError

                raise ChunkerError(
                    f"Cannot process bare repository: {repo_path}. "
                    "Bare repositories have no working tree to process.",
                )
            gitignore_patterns = self.load_gitignore_patterns(repo_path)
            if gitignore_patterns:
                gitignore_spec = pathspec.PathSpec.from_lines(
                    "gitwildmatch",
                    gitignore_patterns,
                )
                filtered_files = []
                for file_path in files:
                    rel_path = file_path.relative_to(repo_path)
                    if not gitignore_spec.match_file(
                        str(rel_path),
                    ) and self.should_process_file(str(file_path), repo_path):
                        filtered_files.append(file_path)
                return filtered_files
        except (
            FileNotFoundError,
            IndexError,
            KeyError,
            self.git.InvalidGitRepositoryError,
        ):
            pass
        return files

    def watch_repository(
        self,
        repo_path: str,
        on_update,
        poll_interval: float = 1.0,
    ) -> None:
        """
        Watch a repository for changes and emit deltas via callback.

        on_update signature: (deltas: dict) -> None
        deltas keys: nodes_added, nodes_updated, nodes_removed, edges, spans
        """
        from time import sleep

        repo_root = Path(repo_path).resolve()
        if not repo_root.exists():
            raise ChunkerError(f"Repository path does not exist: {repo_root}")

        last_state = self.load_incremental_state(str(repo_root)) or {}
        last_commit = last_state.get("last_commit")

        try:
            repo = self.git.Repo(repo_root)
        except Exception:
            repo = None

        known_ids: set[str] = set()
        while True:
            changed_files: list[str] = []
            if repo:
                try:
                    if last_commit:
                        changed_files = self.get_changed_files(
                            str(repo_root),
                            since_commit=last_commit,
                        )
                    else:
                        # first run, process all
                        changed_files = [
                            str(p.relative_to(repo_root))
                            for p in self.get_processable_files(str(repo_root))
                        ]
                except Exception:
                    changed_files = []
            else:
                # Fallback: process all files on first loop
                changed_files = [
                    str(p.relative_to(repo_root))
                    for p in self.get_processable_files(str(repo_root))
                ]

            # Build deltas
            nodes_added: list[dict] = []
            nodes_updated: list[dict] = []
            nodes_removed: list[str] = []
            all_chunks = []
            for rel in changed_files:
                path = repo_root / rel
                ext = path.suffix.lower()
                language = self._language_extensions.get(ext)
                if not language or not path.exists():
                    continue
                try:
                    content = path.read_text(encoding="utf-8")
                except Exception:
                    continue
                from chunker.core import chunk_text

                chunks = chunk_text(content, language, str(path))
                all_chunks.extend(chunks)
                for c in chunks:
                    node = {
                        "id": c.node_id or c.chunk_id,
                        "file": c.file_path,
                        "lang": c.language,
                        "symbol": c.symbol_id,
                        "kind": c.node_type,
                        "attrs": c.metadata or {},
                    }
                    if node["id"] in known_ids:
                        nodes_updated.append(node)
                    else:
                        nodes_added.append(node)
                        known_ids.add(node["id"])

            from chunker.graph.xref import build_xref

            _nodes, edges = build_xref(all_chunks)
            spans = [
                {
                    "file_id": getattr(c, "file_id", ""),
                    "symbol_id": getattr(c, "symbol_id", None),
                    "start_byte": getattr(c, "byte_start", 0),
                    "end_byte": getattr(c, "byte_end", 0),
                }
                for c in all_chunks
            ]

            deltas = {
                "nodes_added": nodes_added,
                "nodes_updated": nodes_updated,
                "nodes_removed": nodes_removed,
                "edges": edges,
                "spans": spans,
            }
            try:
                on_update(deltas)
            except Exception:
                pass

            # Update last_commit
            try:
                if repo and repo.head.is_valid():
                    last_commit = repo.head.commit.hexsha
                    self.save_incremental_state(
                        str(repo_root),
                        {"last_commit": last_commit},
                    )
            except Exception:
                pass

            sleep(poll_interval)

from __future__ import annotations

import multiprocessing as mp
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from concurrent.futures import TimeoutError as FutureTimeout
from pathlib import Path
from typing import TYPE_CHECKING

from ._internal.cache import ASTCache
from .core import chunk_file
from .streaming import chunk_file_streaming

if TYPE_CHECKING:
    from .types import CodeChunk


class ParallelChunker:
    """Process multiple files in parallel using multiprocessing."""

    def __init__(
        self,
        language: str,
        num_workers: int | None = None,
        use_cache: bool = True,
        use_streaming: bool = False,
        timeout_seconds: float | None = None,
    ):
        self.language = language
        self.num_workers = num_workers or mp.cpu_count()
        self.use_cache = use_cache
        self.use_streaming = use_streaming
        self.cache = ASTCache() if use_cache else None
        # Optional wall-clock budget for collecting all results. When set, a
        # hung worker cannot exceed it without being cancelled and recorded as a
        # timeout. Default None = UNBOUNDED: a legitimate large file must not be
        # killed just for being slow — the timeout is an opt-in safety valve for
        # callers that need to bound a possibly-hung worker, not a global ceiling.
        self.timeout_seconds = timeout_seconds

    def _process_single_file(self, file_path: Path) -> tuple[Path, list[CodeChunk]]:
        """Process a single file, using cache if available."""
        # Check cache first
        if self.cache:
            cached_chunks = self.cache.get_cached_chunks(file_path, self.language)
            if cached_chunks is not None:
                return file_path, cached_chunks

        # Process file
        if self.use_streaming:
            chunks = list(chunk_file_streaming(file_path, self.language))
        else:
            chunks = chunk_file(file_path, self.language)

        # Cache results
        if self.cache and chunks:
            self.cache.cache_chunks(file_path, self.language, chunks)

        return file_path, chunks

    def chunk_files_parallel(
        self,
        file_paths: list[Path],
    ) -> dict[Path, list[CodeChunk]]:
        """Process multiple files in parallel."""
        results: dict[Path, list[CodeChunk]] = {}
        timeout_seconds = self.timeout_seconds
        # A None timeout means UNBOUNDED — never impose a deadline on a slow but
        # legitimate worker. deadline stays None and every wait is unbounded.
        deadline = (
            time.monotonic() + timeout_seconds if timeout_seconds is not None else None
        )

        # Manage the executor manually so a hung worker cannot block us on
        # __exit__: we tear it down with wait=False and cancel pending futures.
        executor = ProcessPoolExecutor(max_workers=self.num_workers)
        try:
            # Submit all tasks
            future_to_path = {
                executor.submit(self._process_single_file, path): path
                for path in file_paths
            }

            try:
                # Bounding as_completed with a wall-clock timeout is what makes
                # the deadline real: a hung worker never *completes*, so without
                # this the iterator would block forever and result(timeout=...)
                # would never even be reached. With timeout_seconds=None the
                # iterator blocks until every worker finishes (unbounded).
                for future in as_completed(
                    future_to_path,
                    timeout=timeout_seconds,
                ):
                    path = future_to_path[future]
                    remaining = (
                        deadline - time.monotonic() if deadline is not None else None
                    )
                    try:
                        file_path, chunks = future.result(
                            timeout=(
                                max(0.0, remaining) if remaining is not None else None
                            ),
                        )
                        results[file_path] = chunks
                    except FutureTimeout:
                        future.cancel()
                        print(
                            f"Timeout processing {path}: exceeded {timeout_seconds}s",
                        )
                        results[path] = []
                    except (
                        FileNotFoundError,
                        IndexError,
                        KeyError,
                        PermissionError,
                    ) as e:
                        # Normalize known failure classes
                        print(f"Error processing {path}: {e}")
                        results[path] = []
                    except Exception as e:
                        # Handle any other worker crashes or unexpected exceptions
                        print(f"Unexpected error processing {path}: {e}")
                        results[path] = []
            except FutureTimeout:
                # The wall-clock deadline elapsed while waiting on a worker that
                # never completed. We ABANDON it — record a timeout and stop
                # waiting so the CALL returns within budget. Note: a future that
                # is already running cannot truly be cancelled, and shutdown()
                # below does not join/kill the OS child, so a genuinely hung
                # worker process is orphaned (it exits on its own or with the
                # interpreter), not force-killed. That is the ProcessPoolExecutor
                # limitation; the contract here is "the caller is unblocked",
                # not "the child is terminated".
                for outstanding, pending_path in future_to_path.items():
                    if not outstanding.done():
                        outstanding.cancel()
                        results.setdefault(pending_path, [])
                        print(
                            f"Timeout processing {pending_path}: "
                            f"exceeded {timeout_seconds}s",
                        )
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

        return results

    def chunk_directory_parallel(
        self,
        directory: Path,
        extensions: list[str] | None = None,
    ) -> dict[Path, list[CodeChunk]]:
        """Process all files in a directory in parallel."""
        if extensions is None:
            # Default extensions based on language
            ext_map = {
                "python": [".py"],
                "rust": [".rs"],
                "javascript": [".js", ".jsx"],
                "typescript": [".ts", ".tsx"],
                "c": [".c", ".h"],
                "cpp": [".cpp", ".cxx", ".cc", ".hpp", ".h"],
            }
            extensions = ext_map.get(self.language, [])

        # Find all matching files
        file_paths = []
        for ext in extensions:
            file_paths.extend(directory.rglob(f"*{ext}"))

        return self.chunk_files_parallel(file_paths)


def chunk_files_parallel(
    file_paths: list[str | Path],
    language: str,
    num_workers: int | None = None,
    use_cache: bool = True,
    use_streaming: bool = False,
) -> dict[Path, list[CodeChunk]]:
    """Convenience function to process multiple files in parallel."""
    chunker = ParallelChunker(language, num_workers, use_cache, use_streaming)
    paths = [Path(p) for p in file_paths]
    return chunker.chunk_files_parallel(paths)


def chunk_directory_parallel(
    directory: str | Path,
    language: str,
    extensions: list[str] | None = None,
    num_workers: int | None = None,
    use_cache: bool = True,
    use_streaming: bool = False,
) -> dict[Path, list[CodeChunk]]:
    """Convenience function to process a directory in parallel."""
    chunker = ParallelChunker(language, num_workers, use_cache, use_streaming)
    return chunker.chunk_directory_parallel(Path(directory), extensions)

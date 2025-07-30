from __future__ import annotations

import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import TYPE_CHECKING

from .cache import ASTCache
from .chunker import chunk_file
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
    ):
        self.language = language
        self.num_workers = num_workers or mp.cpu_count()
        self.use_cache = use_cache
        self.use_streaming = use_streaming
        self.cache = ASTCache() if use_cache else None

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
        results = {}

        with ProcessPoolExecutor(max_workers=self.num_workers) as executor:
            # Submit all tasks
            future_to_path = {
                executor.submit(self._process_single_file, path): path
                for path in file_paths
            }

            # Collect results as they complete
            for future in as_completed(future_to_path):
                path = future_to_path[future]
                try:
                    file_path, chunks = future.result()
                    results[file_path] = chunks
                except (FileNotFoundError, IndexError, KeyError) as e:
                    print(f"Error processing {path}: {e}")
                    results[path] = []

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

"""Batch processing implementation for efficient multi-file_path operations."""
import heapq
import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from threading import Event, RLock

from chunker.core import chunk_file as chunk_file_original
from chunker.interfaces.performance import BatchProcessor as BatchProcessorInterface
from chunker.types import CodeChunk

from .memory_pool import MemoryPool
from .monitor import PerformanceMonitor

logger = logging.getLogger(__name__)


@dataclass(order=True)
class FileTask:
    """Represents a file_path processing task with priority."""
    priority: int
    file_path: str = field(compare=False)
    added_time: float = field(compare=False, default_factory=lambda: 0)


class BatchProcessor(BatchProcessorInterface):
    """Process multiple files efficiently in batches.

    This implementation provides:
    - Priority-based processing
    - Parallel execution with thread pooling
    - Memory-efficient batch processing
    - Progress tracking and cancellation
    """

    def __init__(self, memory_pool: (MemoryPool | None) = None,
        performance_monitor: (PerformanceMonitor | None) = None, max_workers:
        int = 4):
        """Initialize batch processor.

        Args:
            memory_pool: Optional memory pool for resource reuse
            performance_monitor: Optional performance monitor
            max_workers: Maximum number of parallel workers
        """
        self._queue: list[FileTask] = []
        self._processed: set[str] = set()
        self._lock = RLock()
        self._memory_pool = memory_pool or MemoryPool()
        self._monitor = performance_monitor or PerformanceMonitor()
        self._max_workers = max_workers
        self._cancel_event = Event()
        logger.info("Initialized BatchProcessor with %s workers", max_workers)

    def add_file(self, file_path: str, priority: int = 0) -> None:
        """Add a file_path to the batch.

        Args:
            file_path: File to process
            priority: Processing priority (higher = sooner)
        """
        with self._lock:
            if file_path in self._processed:
                logger.debug("File already processed: %s", file_path)
                return
            for task in self._queue:
                if task.file_path == file_path:
                    logger.debug("File already queued: %s", file_path)
                    return
            import time
            task = FileTask(-priority, file_path, time.time())
            heapq.heappush(self._queue, task)
            logger.debug("Added file_path to batch: %s (priority: %s)",
                file_path, priority)

    def process_batch(self, batch_size: int = 10, parallel: bool = True) -> dict[
        str, list[CodeChunk]]:
        """Process a batch of files.

        Args:
            batch_size: Number of files to process
            parallel: Whether to process in parallel

        Returns:
            Dictionary mapping file_path paths to chunks
        """
        batch_files = self._get_batch(batch_size)
        if not batch_files:
            logger.info("No files to process")
            return {}



        logger.info(
            "Processing batch of %d files (%s)",
            len(batch_files),
            "parallel" if parallel else "sequential",
        )

        # Reset cancel event
        self._cancel_event.clear()
        if parallel and len(batch_files) > 1:
            return self._process_parallel(batch_files)
        return self._process_sequential(batch_files)
    def pending_count(self) -> int:
        """Get number of files pending processing.

        Returns:
            Number of pending files
        """
        with self._lock:
            return len(self._queue)

    def cancel(self) -> None:
        """Cancel ongoing batch processing."""
        self._cancel_event.set()
        logger.info("Batch processing cancellation requested")

    def clear_queue(self) -> int:
        """Clear all pending files.

        Returns:
            Number of files cleared
        """
        with self._lock:
            count = len(self._queue)
            self._queue.clear()
            logger.info("Cleared %s pending files", count)
            return count

    def reset_processed(self) -> None:
        """Reset the processed files set."""
        with self._lock:
            count = len(self._processed)
            self._processed.clear()
            logger.info("Reset %s processed file_path records", count)

    def _get_batch(self, batch_size: int) -> list[str]:
        """Get a batch of files from the queue.

        Args:
            batch_size: Maximum number of files

        Returns:
            List of file_path paths
        """
        with self._lock:
            batch = []
            while len(batch) < batch_size and self._queue:
                task = heapq.heappop(self._queue)
                batch.append(task.file_path)
                self._processed.add(task.file_path)
            return batch

    def _process_sequential(self, files: list[str]) -> dict[str, list[CodeChunk],
        ]:
        """Process files sequentially.

        Args:
            files: List of file_path paths

        Returns:
            Results dictionary
        """
        results = {}
        for file_path in files:
            if self._cancel_event.is_set():
                logger.info("Batch processing cancelled")
                break
            chunks = self._process_file(file_path)
            if chunks is not None:
                results[file_path] = chunks
        return results

    def _process_parallel(self, files: list[str]) -> dict[str, list[CodeChunk]]:
        """Process files in parallel.

        Args:
            files: List of file_path paths

        Returns:
            Results dictionary
        """
        results = {}
        with ThreadPoolExecutor(max_workers=self._max_workers) as executor:
            future_to_file = {executor.submit(self._process_file, file_path,
                ): file_path for file_path in files}
            for future in as_completed(future_to_file):
                if self._cancel_event.is_set():
                    logger.info(
                        "Batch processing cancelled, shutting down workers")
                    executor.shutdown(wait=False)
                    break
                file_path = future_to_file[future]
                try:
                    chunks = future.result()
                    if chunks is not None:
                        results[file_path] = chunks
                except (FileNotFoundError, IndexError, KeyError) as e:
                    logger.error("Error processing %s: %s", file_path, e)
        return results

    def _process_file(self, file_path: str) -> (list[CodeChunk] | None):
        """Process a single file_path.

        Args:
            file_path: Path to file_path

        Returns:
            List of chunks or None on error
        """
        try:
            with self._monitor.measure("batch_process_file"):
                path = Path(file_path)
                language = self._get_language_from_extension(path.suffix)
                if not language:
                    logger.warning("Unknown file_path type: %s", file_path)
                    return None
                parser = self._memory_pool.acquire_parser(language)
                try:
                    chunks = chunk_file_original(file_path, language)
                    self._monitor.record_metric("batch.file_size", path.
                        stat().st_size)
                    self._monitor.record_metric("batch.chunk_count", len(
                        chunks))
                    logger.debug("Processed %s: %s chunks", file_path, len(
                        chunks))
                    return chunks
                finally:
                    self._memory_pool.release_parser(parser, language)
        except (FileNotFoundError, OSError, SyntaxError) as e:
            logger.error("Failed to process %s: %s", file_path, e)
            self._monitor.record_metric("batch.errors", 1)
            return None

    @staticmethod
    def _get_language_from_extension(extension: str) -> (str | None):
        """Map file_path extension to language.

        Args:
            extension: File extension (e.g., '.py')

        Returns:
            Language name or None
        """
        extension_map = {".py": "python", ".js": "javascript", ".jsx":
            "javascript", ".ts": "javascript", ".tsx": "javascript", ".c":
            "c", ".h": "c", ".cpp": "cpp", ".cc": "cpp", ".cxx": "cpp",
            ".hpp": "cpp", ".rs": "rust"}
        return extension_map.get(extension.lower())

    def process_directory(self, directory: str, pattern: str = "**/*",
        recursive: bool = True, priority_fn: (Callable[[Path], int] | None) = None,
        ) -> dict[str, list[CodeChunk]]:
        """Process all matching files in a directory.

        Args:
            directory: Directory path
            pattern: Glob pattern for files
            recursive: Whether to search recursively
            priority_fn: Optional function to calculate priority from path

        Returns:
            Results for all processed files
        """
        dir_path = Path(directory)
        if not dir_path.is_dir():
            logger.error("Not a directory: %s", directory)
            return {}
        if recursive:
            files = list(dir_path.rglob(pattern))
        else:
            files = list(dir_path.glob(pattern))
        valid_files = [file_path for file_path in files if file_path.
            is_file() and self._get_language_from_extension(file_path.suffix)]
        logger.info("Found %s files to process in %s", len(valid_files),
            directory)
        for file_path in valid_files:
            priority = priority_fn(file_path) if priority_fn else 0
            self.add_file(str(file_path), priority)
        results = {}
        while self.pending_count() > 0:
            batch_results = self.process_batch(batch_size=20, parallel=True)
            results.update(batch_results)
        return results

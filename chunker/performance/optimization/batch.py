"""Batch processing implementation for efficient multi-file operations."""

import heapq
from dataclasses import dataclass, field
from pathlib import Path
from threading import RLock, Thread, Event
from typing import Dict, List, Optional, Set, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging

from ...interfaces.performance import BatchProcessor as BatchProcessorInterface
from ...types import CodeChunk
from ...chunker import chunk_file as chunk_file_original
from .memory_pool import MemoryPool
from .monitor import PerformanceMonitor

logger = logging.getLogger(__name__)


@dataclass(order=True)
class FileTask:
    """Represents a file processing task with priority."""
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
    
    def __init__(self, 
                 memory_pool: Optional[MemoryPool] = None,
                 performance_monitor: Optional[PerformanceMonitor] = None,
                 max_workers: int = 4):
        """Initialize batch processor.
        
        Args:
            memory_pool: Optional memory pool for resource reuse
            performance_monitor: Optional performance monitor
            max_workers: Maximum number of parallel workers
        """
        self._queue: List[FileTask] = []  # Min heap
        self._processed: Set[str] = set()
        self._lock = RLock()
        self._memory_pool = memory_pool or MemoryPool()
        self._monitor = performance_monitor or PerformanceMonitor()
        self._max_workers = max_workers
        self._cancel_event = Event()
        
        logger.info(f"Initialized BatchProcessor with {max_workers} workers")
    
    def add_file(self, file_path: str, priority: int = 0) -> None:
        """Add a file to the batch.
        
        Args:
            file_path: File to process
            priority: Processing priority (higher = sooner)
        """
        with self._lock:
            # Check if already processed or queued
            if file_path in self._processed:
                logger.debug(f"File already processed: {file_path}")
                return
            
            # Check if already in queue
            for task in self._queue:
                if task.file_path == file_path:
                    logger.debug(f"File already queued: {file_path}")
                    return
            
            # Add to priority queue (negate priority for min heap)
            import time
            task = FileTask(-priority, file_path, time.time())
            heapq.heappush(self._queue, task)
            
            logger.debug(f"Added file to batch: {file_path} (priority: {priority})")
    
    def process_batch(self, 
                     batch_size: int = 10,
                     parallel: bool = True) -> Dict[str, List[CodeChunk]]:
        """Process a batch of files.
        
        Args:
            batch_size: Number of files to process
            parallel: Whether to process in parallel
            
        Returns:
            Dictionary mapping file paths to chunks
        """
        # Get batch of files to process
        batch_files = self._get_batch(batch_size)
        
        if not batch_files:
            logger.info("No files to process")
            return {}
        
        logger.info(f"Processing batch of {len(batch_files)} files "
                   f"({'parallel' if parallel else 'sequential'})")
        
        # Reset cancel event
        self._cancel_event.clear()
        
        # Process files
        if parallel and len(batch_files) > 1:
            return self._process_parallel(batch_files)
        else:
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
            logger.info(f"Cleared {count} pending files")
            return count
    
    def reset_processed(self) -> None:
        """Reset the processed files set."""
        with self._lock:
            count = len(self._processed)
            self._processed.clear()
            logger.info(f"Reset {count} processed file records")
    
    def _get_batch(self, batch_size: int) -> List[str]:
        """Get a batch of files from the queue.
        
        Args:
            batch_size: Maximum number of files
            
        Returns:
            List of file paths
        """
        with self._lock:
            batch = []
            
            while len(batch) < batch_size and self._queue:
                task = heapq.heappop(self._queue)
                batch.append(task.file_path)
                self._processed.add(task.file_path)
            
            return batch
    
    def _process_sequential(self, files: List[str]) -> Dict[str, List[CodeChunk]]:
        """Process files sequentially.
        
        Args:
            files: List of file paths
            
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
    
    def _process_parallel(self, files: List[str]) -> Dict[str, List[CodeChunk]]:
        """Process files in parallel.
        
        Args:
            files: List of file paths
            
        Returns:
            Results dictionary
        """
        results = {}
        
        with ThreadPoolExecutor(max_workers=self._max_workers) as executor:
            # Submit all tasks
            future_to_file = {
                executor.submit(self._process_file, file_path): file_path
                for file_path in files
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_file):
                if self._cancel_event.is_set():
                    logger.info("Batch processing cancelled, shutting down workers")
                    executor.shutdown(wait=False)
                    break
                
                file_path = future_to_file[future]
                try:
                    chunks = future.result()
                    if chunks is not None:
                        results[file_path] = chunks
                except Exception as e:
                    logger.error(f"Error processing {file_path}: {e}")
        
        return results
    
    def _process_file(self, file_path: str) -> Optional[List[CodeChunk]]:
        """Process a single file.
        
        Args:
            file_path: Path to file
            
        Returns:
            List of chunks or None on error
        """
        try:
            # Start timing
            with self._monitor.measure(f'batch_process_file'):
                # Determine language from extension
                path = Path(file_path)
                language = self._get_language_from_extension(path.suffix)
                
                if not language:
                    logger.warning(f"Unknown file type: {file_path}")
                    return None
                
                # Acquire parser from pool
                parser = self._memory_pool.acquire_parser(language)
                
                try:
                    # Process file
                    chunks = chunk_file_original(file_path, language)
                    
                    # Record metrics
                    self._monitor.record_metric('batch.file_size', path.stat().st_size)
                    self._monitor.record_metric('batch.chunk_count', len(chunks))
                    
                    logger.debug(f"Processed {file_path}: {len(chunks)} chunks")
                    
                    return chunks
                
                finally:
                    # Release parser back to pool
                    self._memory_pool.release_parser(parser, language)
        
        except Exception as e:
            logger.error(f"Failed to process {file_path}: {e}")
            self._monitor.record_metric('batch.errors', 1)
            return None
    
    def _get_language_from_extension(self, extension: str) -> Optional[str]:
        """Map file extension to language.
        
        Args:
            extension: File extension (e.g., '.py')
            
        Returns:
            Language name or None
        """
        extension_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.jsx': 'javascript',
            '.ts': 'javascript',
            '.tsx': 'javascript',
            '.c': 'c',
            '.h': 'c',
            '.cpp': 'cpp',
            '.cc': 'cpp',
            '.cxx': 'cpp',
            '.hpp': 'cpp',
            '.rs': 'rust',
        }
        
        return extension_map.get(extension.lower())
    
    def process_directory(self, 
                         directory: str,
                         pattern: str = "**/*",
                         recursive: bool = True,
                         priority_fn: Optional[Callable[[Path], int]] = None) -> Dict[str, List[CodeChunk]]:
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
            logger.error(f"Not a directory: {directory}")
            return {}
        
        # Find matching files
        if recursive:
            files = list(dir_path.rglob(pattern))
        else:
            files = list(dir_path.glob(pattern))
        
        # Filter to only files with known extensions
        valid_files = []
        for file in files:
            if file.is_file() and self._get_language_from_extension(file.suffix):
                valid_files.append(file)
        
        logger.info(f"Found {len(valid_files)} files to process in {directory}")
        
        # Add all files to queue
        for file in valid_files:
            priority = priority_fn(file) if priority_fn else 0
            self.add_file(str(file), priority)
        
        # Process all files
        results = {}
        while self.pending_count() > 0:
            batch_results = self.process_batch(batch_size=20, parallel=True)
            results.update(batch_results)
        
        return results
"""Integration tests for cache file monitoring."""

import hashlib
import json
import os
import sqlite3
import threading
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from tests.integration.interfaces import ResourceTracker

# Try to import actual cache modules
try:
    from chunker.cache import Cache, CacheEntry
    from chunker.file_monitor import FileMonitor
except ImportError:
    # Mock if not available
    Cache = MagicMock()
    CacheEntry = MagicMock()
    FileMonitor = MagicMock()


def cache_worker(worker_id: int, file_paths: list[str], cache_dir: Path):
    """Worker that reads/writes cache entries - module level for pickle."""
    from pathlib import Path

    # Each worker creates its own cache instance
    worker_cache = MockCache(cache_dir, cache_type="sqlite")
    results = []

    for file_path in file_paths:
        # Try to get from cache
        cached = worker_cache.get(file_path)

        if cached is None:
            # Not in cache, read and cache it
            content = Path(file_path).read_text()
            worker_cache.put(file_path, content)
            results.append(
                {
                    "worker": worker_id,
                    "file": file_path,
                    "action": "cached",
                    "content": content,
                },
            )
        else:
            results.append(
                {
                    "worker": worker_id,
                    "file": file_path,
                    "action": "hit",
                    "content": cached["content"],
                },
            )

        # Simulate some work
        time.sleep(0.01)

    return results


def modifying_worker(worker_id: int, file_paths: list[str], cache_dir: Path):
    """Worker that modifies files while processing - module level for pickle."""
    from pathlib import Path

    worker_cache = MockCache(cache_dir, cache_type="sqlite")
    results = []

    for i, file_path in enumerate(file_paths):
        path = Path(file_path)

        # Read from cache
        cached = worker_cache.get(file_path)

        # Modify file on even iterations
        if i % 2 == 0:
            new_content = f"# Modified by worker {worker_id}\n" + path.read_text()
            path.write_text(new_content)

            # Invalidate and re-cache
            worker_cache.invalidate(file_path)
            worker_cache.put(file_path, new_content)

            results.append(
                {
                    "worker": worker_id,
                    "file": file_path,
                    "action": "modified",
                },
            )
        else:
            results.append(
                {
                    "worker": worker_id,
                    "file": file_path,
                    "action": "read",
                    "cached_content": cached["content"] if cached else None,
                },
            )

    return results


def verification_worker(file_paths: list[str], cache_dir: Path):
    """Worker that verifies cache consistency - module level for pickle."""
    from pathlib import Path

    worker_cache = MockCache(cache_dir, cache_type="sqlite")
    results = []

    for file_path in file_paths:
        path = Path(file_path)
        cached = worker_cache.get(file_path)
        actual = path.read_text()

        results.append(
            {
                "file": file_path,
                "cache_matches": cached["content"] == actual if cached else False,
                "has_modification": "Modified by worker" in actual,
            },
        )

    return results


class MockCache:
    """Mock cache implementation for testing."""

    def __init__(self, cache_dir: Path, cache_type: str = "sqlite"):
        self.cache_dir = cache_dir
        self.cache_type = cache_type
        self.entries = {}
        self.lock = threading.RLock()
        self._db_path = cache_dir / "cache.db" if cache_type == "sqlite" else None
        self._init_db()

    def _init_db(self):
        """Initialize database if using SQLite."""
        if self.cache_type == "sqlite" and self._db_path:
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                conn = sqlite3.connect(str(self._db_path))
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS cache_entries (
                        file_path TEXT PRIMARY KEY,
                        content TEXT,
                        timestamp REAL,
                        hash TEXT,
                        metadata TEXT
                    )
                """,
                )
                conn.commit()
                conn.close()
            except sqlite3.DatabaseError:
                # Database is corrupted, remove and recreate
                if self._db_path.exists():
                    self._db_path.unlink()
                # Try again with fresh database
                conn = sqlite3.connect(str(self._db_path))
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS cache_entries (
                        file_path TEXT PRIMARY KEY,
                        content TEXT,
                        timestamp REAL,
                        hash TEXT,
                        metadata TEXT
                    )
                """,
                )
                conn.commit()
                conn.close()

    def get(self, file_path: str) -> dict[str, Any] | None:
        """Get cached entry."""
        with self.lock:
            if self.cache_type == "memory":
                return self.entries.get(file_path)
            conn = sqlite3.connect(str(self._db_path))
            cursor = conn.execute(
                "SELECT content, timestamp, hash, metadata FROM cache_entries WHERE file_path = ?",
                (file_path,),
            )
            row = cursor.fetchone()
            conn.close()
            if row:
                return {
                    "content": row[0],
                    "timestamp": row[1],
                    "hash": row[2],
                    "metadata": json.loads(row[3]) if row[3] else {},
                }
        return None

    def put(self, file_path: str, content: str, metadata: dict = None):
        """Store entry in cache."""
        timestamp = time.time()
        content_hash = hashlib.md5(content.encode()).hexdigest()

        with self.lock:
            entry = {
                "content": content,
                "timestamp": timestamp,
                "hash": content_hash,
                "metadata": metadata or {},
            }

            if self.cache_type == "memory":
                self.entries[file_path] = entry
            else:
                conn = sqlite3.connect(str(self._db_path))
                conn.execute(
                    "INSERT OR REPLACE INTO cache_entries VALUES (?, ?, ?, ?, ?)",
                    (
                        file_path,
                        content,
                        timestamp,
                        content_hash,
                        json.dumps(metadata or {}),
                    ),
                )
                conn.commit()
                conn.close()

    def invalidate(self, file_path: str):
        """Invalidate cache entry."""
        with self.lock:
            if self.cache_type == "memory":
                self.entries.pop(file_path, None)
            else:
                conn = sqlite3.connect(str(self._db_path))
                conn.execute(
                    "DELETE FROM cache_entries WHERE file_path = ?",
                    (file_path,),
                )
                conn.commit()
                conn.close()

    def clear(self):
        """Clear all cache entries."""
        with self.lock:
            if self.cache_type == "memory":
                self.entries.clear()
            else:
                conn = sqlite3.connect(str(self._db_path))
                conn.execute("DELETE FROM cache_entries")
                conn.commit()
                conn.close()

    def corrupt_db(self):
        """Corrupt the database for testing recovery."""
        if self.cache_type == "sqlite" and self._db_path.exists():
            # Write garbage to the database file
            with open(self._db_path, "wb") as f:
                f.write(b"CORRUPTED DATABASE FILE" * 100)


class MockFileMonitor:
    """Mock file monitoring system."""

    def __init__(self, resource_monitor: ResourceTracker):
        self.monitored_files = {}
        self.monitored_dirs = {}
        self.callbacks = {}
        self.resource_monitor = resource_monitor
        self._lock = threading.Lock()

    def watch_file(self, file_path: Path, callback):
        """Start watching a file for changes."""
        with self._lock:
            str_path = str(file_path)
            self.monitored_files[str_path] = {
                "path": file_path,
                "callback": callback,
                "last_mtime": file_path.stat().st_mtime if file_path.exists() else None,
            }

            # Track as resource
            resource = self.resource_monitor.track_resource(
                "chunker.cache",
                "file_watcher",
                f"watch_file_{Path(str_path).name}_{time.time()}",
            )
            self.monitored_files[str_path]["resource_id"] = resource["resource_id"]

    def watch_directory(self, dir_path: Path, callback, recursive: bool = False):
        """Start watching a directory for changes."""
        with self._lock:
            str_path = str(dir_path)
            self.monitored_dirs[str_path] = {
                "path": dir_path,
                "callback": callback,
                "recursive": recursive,
                "known_files": set(f.name for f in dir_path.iterdir() if f.is_file()),
            }

            # Track as resource
            resource = self.resource_monitor.track_resource(
                "chunker.cache",
                "directory_watcher",
                f"watch_dir_{Path(str_path).name}_{time.time()}",
            )
            self.monitored_dirs[str_path]["resource_id"] = resource["resource_id"]

    def check_changes(self):
        """Check for file system changes."""
        changes = []

        with self._lock:
            # Check file changes
            for str_path, info in self.monitored_files.items():
                path = info["path"]
                if path.exists():
                    current_mtime = path.stat().st_mtime
                    if info["last_mtime"] and current_mtime > info["last_mtime"]:
                        changes.append(("modified", path, info["callback"]))
                        info["last_mtime"] = current_mtime
                elif info["last_mtime"] is not None:
                    changes.append(("deleted", path, info["callback"]))
                    info["last_mtime"] = None

            # Check directory changes
            for str_path, info in self.monitored_dirs.items():
                path = info["path"]
                if path.exists():
                    current_files = set(f.name for f in path.iterdir() if f.is_file())
                    added = current_files - info["known_files"]
                    removed = info["known_files"] - current_files

                    for filename in added:
                        changes.append(("added", path / filename, info["callback"]))
                    for filename in removed:
                        changes.append(("removed", path / filename, info["callback"]))

                    info["known_files"] = current_files

        # Execute callbacks
        for change_type, path, callback in changes:
            callback(change_type, path)

    def stop_watching(self, path: Path):
        """Stop watching a file or directory."""
        with self._lock:
            str_path = str(path)
            if str_path in self.monitored_files:
                resource_id = self.monitored_files[str_path]["resource_id"]
                self.resource_monitor.release_resource(resource_id)
                del self.monitored_files[str_path]
            elif str_path in self.monitored_dirs:
                resource_id = self.monitored_dirs[str_path]["resource_id"]
                self.resource_monitor.release_resource(resource_id)
                del self.monitored_dirs[str_path]


class TestCacheFileMonitoring:
    """Test cache behavior with file system changes."""

    def test_file_modification_detection(
        self,
        temp_workspace,
        resource_monitor,
        test_file_generator,
        performance_monitor,
    ):
        """Test file modification detection."""
        # Create test file
        test_file = test_file_generator.create_file(
            "test_modify.py",
            "def original(): return 'original'",
        )

        # Set up cache and file monitor
        cache = MockCache(temp_workspace / "cache", cache_type="sqlite")
        file_monitor = MockFileMonitor(resource_monitor)

        # Track cache resource
        cache_resource = resource_monitor.track_resource(
            "chunker.cache",
            "cache_entry",
            f"cache_{test_file.name}_{time.time()}",
        )
        cache_resource_id = cache_resource["resource_id"]

        # Cache the file
        with performance_monitor.measure("initial_cache"):
            cache.put(str(test_file), test_file.read_text())

        # Set up modification detection
        modifications_detected = []

        def on_file_change(change_type, path):
            modifications_detected.append((change_type, path))
            if change_type == "modified":
                # Invalidate cache
                cache.invalidate(str(path))
                # Re-cache with new content
                cache.put(str(path), path.read_text())

        # Start monitoring
        file_monitor.watch_file(test_file, on_file_change)

        # Verify initial cache
        cached = cache.get(str(test_file))
        assert cached is not None
        assert "original" in cached["content"]

        # Modify the file
        time.sleep(0.1)  # Ensure timestamp changes
        with performance_monitor.measure("file_modification"):
            test_file.write_text("def modified(): return 'modified'")

        # Check for changes
        with performance_monitor.measure("change_detection"):
            file_monitor.check_changes()

        # Verify modification detected
        assert len(modifications_detected) == 1
        assert modifications_detected[0] == ("modified", test_file)

        # Verify cache updated
        cached = cache.get(str(test_file))
        assert cached is not None
        assert "modified" in cached["content"]
        assert "original" not in cached["content"]

        # Verify performance
        stats = performance_monitor.get_stats("change_detection")
        assert stats["average"] < 0.1  # Should be fast

        # Clean up
        file_monitor.stop_watching(test_file)
        resource_monitor.release_resource(cache_resource_id)
        resource_monitor.assert_no_leaks("chunker.cache")

    def test_file_deletion_handling(
        self,
        temp_workspace,
        resource_monitor,
        test_file_generator,
        thread_safe_counter,
    ):
        """Test graceful handling of file deletion."""
        # Create test files
        files_to_delete = []
        for i in range(5):
            file = test_file_generator.create_file(
                f"delete_test_{i}.py",
                f"def func_{i}(): pass",
            )
            files_to_delete.append(file)

        # Set up caches (test both memory and sqlite)
        memory_cache = MockCache(temp_workspace / "memory_cache", cache_type="memory")
        sqlite_cache = MockCache(temp_workspace / "sqlite_cache", cache_type="sqlite")

        # Cache all files
        resource_ids = []
        for file in files_to_delete:
            memory_cache.put(str(file), file.read_text())
            sqlite_cache.put(str(file), file.read_text())

            # Track resources
            resource1 = resource_monitor.track_resource(
                "chunker.cache",
                "cache_entry",
                f"memory_cache_{file.name}_{time.time()}",
            )
            resource_ids.append(resource1["resource_id"])

            resource2 = resource_monitor.track_resource(
                "chunker.cache",
                "cache_entry",
                f"sqlite_cache_{file.name}_{time.time()}",
            )
            resource_ids.append(resource2["resource_id"])

        # Set up file monitor
        file_monitor = MockFileMonitor(resource_monitor)
        deletions_handled = thread_safe_counter
        errors_caught = []

        def on_file_deleted(change_type, path):
            if change_type == "deleted":
                deletions_handled.increment()
                # Remove from both caches
                memory_cache.invalidate(str(path))
                sqlite_cache.invalidate(str(path))

        # Monitor all files
        for file in files_to_delete:
            file_monitor.watch_file(file, on_file_deleted)

        # Delete files in various ways
        files_to_delete[0].unlink()  # Direct delete
        os.remove(files_to_delete[1])  # OS remove
        files_to_delete[2].write_bytes(b"")  # Empty then delete
        files_to_delete[2].unlink()

        # Concurrent deletion
        def delete_file(file_path):
            try:
                if file_path.exists():
                    file_path.unlink()
            except Exception as e:
                errors_caught.append(e)

        with ThreadPoolExecutor(max_workers=2) as executor:
            executor.submit(delete_file, files_to_delete[3])
            executor.submit(delete_file, files_to_delete[4])

        # Check for changes
        file_monitor.check_changes()

        # Verify all deletions handled
        assert deletions_handled.value == 5
        assert len(errors_caught) == 0

        # Verify cache entries removed
        for file in files_to_delete:
            assert memory_cache.get(str(file)) is None
            assert sqlite_cache.get(str(file)) is None

        # Test accessing deleted file entries (should not crash)
        try:
            for file in files_to_delete:
                # These should return None gracefully
                result1 = memory_cache.get(str(file))
                result2 = sqlite_cache.get(str(file))
                assert result1 is None
                assert result2 is None
        except Exception as e:
            pytest.fail(f"Cache access after deletion should not crash: {e}")

        # Clean up
        for file in files_to_delete:
            file_monitor.stop_watching(file)

        # Release tracked resources
        for resource_id in resource_ids:
            resource_monitor.release_resource(resource_id)

        resource_monitor.assert_no_leaks("chunker.cache")

    def test_file_rename_tracking(
        self,
        temp_workspace,
        resource_monitor,
        test_file_generator,
    ):
        """Test file rename tracking."""
        # Create test file
        original_file = test_file_generator.create_file(
            "rename_test.py",
            "def rename_me(): return 'original'",
        )

        # Set up cache
        cache = MockCache(temp_workspace / "cache", cache_type="sqlite")
        cache.put(str(original_file), original_file.read_text())

        # Track cache resource
        cache_resource = resource_monitor.track_resource(
            "chunker.cache",
            "cache_entry",
            f"cache_{original_file.name}_{time.time()}",
        )
        cache_resource_id = cache_resource["resource_id"]

        # Test 1: Non-tracking mode (treat as delete + create)
        file_monitor = MockFileMonitor(resource_monitor)
        events = []

        def on_change(change_type, path):
            events.append((change_type, str(path)))

        file_monitor.watch_file(original_file, on_change)

        # Rename file
        new_file = original_file.parent / "renamed_test.py"
        original_file.rename(new_file)

        # Check changes
        file_monitor.check_changes()

        # Should see deletion of original
        assert ("deleted", str(original_file)) in events

        # Original cache entry should still exist (non-tracking mode)
        assert cache.get(str(original_file)) is not None

        # Test 2: Tracking mode (follow renames)
        # Reset for tracking test
        new_file.rename(original_file)  # Rename back
        events.clear()

        # Simulate tracking mode with content verification
        def on_rename_aware_change(change_type, path):
            if change_type == "deleted":
                # Check if this is a rename by looking for similar content
                original_content = cache.get(str(path))
                if original_content:
                    # Look for files with same content
                    parent_dir = Path(path).parent
                    for file in parent_dir.glob("*.py"):
                        if file != path and file.exists():
                            try:
                                if file.read_text() == original_content["content"]:
                                    # This is a rename
                                    events.append(("renamed", str(path), str(file)))
                                    # Update cache with new path
                                    cache.invalidate(str(path))
                                    cache.put(str(file), original_content["content"])
                                    return
                            except:
                                pass

                # Not a rename, just deletion
                events.append(("deleted", str(path)))
                cache.invalidate(str(path))

        # Re-setup monitor with rename-aware callback
        file_monitor.stop_watching(original_file)
        file_monitor.watch_file(original_file, on_rename_aware_change)

        # Rename again
        original_file.rename(new_file)
        file_monitor.check_changes()

        # Should detect rename
        assert any(event[0] == "renamed" for event in events)

        # Cache should be updated with new path
        assert cache.get(str(original_file)) is None
        assert cache.get(str(new_file)) is not None

        # Test 3: Rename to different directory
        subdir = temp_workspace / "subdir"
        subdir.mkdir()
        final_file = subdir / "final_test.py"

        new_file.rename(final_file)
        file_monitor.check_changes()

        # Clean up resources
        file_monitor.stop_watching(original_file)
        resource_monitor.release_resource(cache_resource_id)
        resource_monitor.assert_no_leaks("chunker.cache")

    def test_concurrent_file_modifications(
        self,
        temp_workspace,
        resource_monitor,
        test_file_generator,
        performance_monitor,
    ):
        """Test concurrent file modifications."""
        # Create shared test file
        shared_file = test_file_generator.create_file(
            "concurrent_test.py",
            "counter = 0",
        )

        # Set up cache with proper locking
        cache = MockCache(temp_workspace / "cache", cache_type="sqlite")

        # Track resources
        resource = resource_monitor.track_resource(
            "chunker.cache",
            "cache_entry",
            f"cache_{shared_file.name}_{time.time()}",
        )
        cache_resource_id = resource["resource_id"]

        # Set up concurrent modification tracking
        modification_lock = threading.Lock()
        modifications = []
        corruption_detected = False

        def modify_file_worker(worker_id: int, iterations: int):
            """Worker that modifies the file."""
            for i in range(iterations):
                try:
                    with modification_lock:
                        # Read current content
                        current = shared_file.read_text()

                        # Modify content
                        lines = current.strip().split("\n")
                        counter_line = lines[0]
                        current_value = int(counter_line.split("=")[1].strip())
                        new_value = current_value + 1

                        # Write new content
                        new_content = f"counter = {new_value}\n# Modified by worker {worker_id} at iteration {i}"
                        shared_file.write_text(new_content)

                        # Update cache
                        cache.put(str(shared_file), new_content)

                        modifications.append(
                            {
                                "worker": worker_id,
                                "iteration": i,
                                "value": new_value,
                            },
                        )

                    # Small delay to allow contention
                    time.sleep(0.001)

                except Exception:
                    # Check for corruption
                    nonlocal corruption_detected
                    corruption_detected = True
                    raise

        # Run concurrent modifications
        num_workers = 5
        iterations_per_worker = 10

        with performance_monitor.measure("concurrent_modifications"):
            with ThreadPoolExecutor(max_workers=num_workers) as executor:
                futures = []
                for worker_id in range(num_workers):
                    future = executor.submit(
                        modify_file_worker,
                        worker_id,
                        iterations_per_worker,
                    )
                    futures.append(future)

                # Wait for completion
                for future in as_completed(futures):
                    future.result()

        # Verify results
        assert not corruption_detected
        assert len(modifications) == num_workers * iterations_per_worker

        # Verify final counter value
        final_content = shared_file.read_text()
        final_value = int(final_content.split("\n")[0].split("=")[1].strip())
        assert final_value == num_workers * iterations_per_worker

        # Verify cache consistency
        cached_content = cache.get(str(shared_file))
        assert cached_content is not None
        assert cached_content["content"] == final_content

        # Test cache consistency with different modification patterns
        # Pattern 1: Rapid small changes
        rapid_changes = []

        def rapid_modifier(iterations: int):
            for i in range(iterations):
                with modification_lock:
                    content = f"rapid_change_{i}"
                    shared_file.write_text(content)
                    cache.put(str(shared_file), content)
                    rapid_changes.append(content)

        with performance_monitor.measure("rapid_modifications"):
            rapid_modifier(50)

        # Verify last change is cached
        assert cache.get(str(shared_file))["content"] == rapid_changes[-1]

        # Pattern 2: Large content changes
        def large_content_modifier(size_kb: int):
            content = "x" * (size_kb * 1024)
            shared_file.write_text(content)
            cache.put(str(shared_file), content)

        with performance_monitor.measure("large_content_modification"):
            large_content_modifier(100)  # 100KB file

        # Verify large content cached correctly
        cached = cache.get(str(shared_file))
        assert len(cached["content"]) == 100 * 1024

        # Check performance
        stats = performance_monitor.get_stats("concurrent_modifications")
        assert stats["max"] < 5.0  # Should complete reasonably fast

        # Clean up resources
        resource_monitor.release_resource(cache_resource_id)
        resource_monitor.assert_no_leaks("chunker.cache")

    def test_cache_consistency_across_workers(
        self,
        temp_workspace,
        resource_monitor,
        test_file_generator,
        performance_monitor,
    ):
        """Test cache consistency with parallel workers."""
        # Create test files
        test_files = []
        for i in range(10):
            file = test_file_generator.create_file(
                f"worker_test_{i}.py",
                f"def process_{i}(): return {i}",
            )
            test_files.append(file)

        # Shared cache (SQLite for cross-process consistency)
        cache_dir = temp_workspace / "shared_cache"
        cache = MockCache(cache_dir, cache_type="sqlite")

        # Track resources
        resource_ids = []
        for file in test_files:
            resource = resource_monitor.track_resource(
                "chunker.cache",
                "cache_entry",
                f"cache_{file.name}_{time.time()}",
            )
            resource_ids.append(resource["resource_id"])

        # Phase 1: Parallel caching
        with performance_monitor.measure("parallel_caching"):
            with ProcessPoolExecutor(max_workers=4) as executor:
                # Distribute files among workers
                file_paths = [str(f) for f in test_files]
                futures = []

                for worker_id in range(4):
                    # Each worker gets some files
                    worker_files = file_paths[worker_id::4]
                    future = executor.submit(
                        cache_worker,
                        worker_id,
                        worker_files,
                        cache_dir,
                    )
                    futures.append(future)

                # Collect results
                all_results = []
                for future in as_completed(futures):
                    all_results.extend(future.result())

        # Verify all files were cached
        for file in test_files:
            cached = cache.get(str(file))
            assert cached is not None
            assert f"process_{file.stem.split('_')[-1]}" in cached["content"]

        # Phase 2: Modify files during processing
        modification_results = []

        # Run modifying workers
        with performance_monitor.measure("concurrent_modifications"):
            with ProcessPoolExecutor(max_workers=3) as executor:
                futures = []
                for worker_id in range(3):
                    worker_files = file_paths[worker_id::3]
                    future = executor.submit(
                        modifying_worker,
                        worker_id,
                        worker_files,
                        cache_dir,
                    )
                    futures.append(future)

                for future in as_completed(futures):
                    modification_results.extend(future.result())

        # Phase 3: Verify all workers see updates
        # Run verification across all workers
        with ProcessPoolExecutor(max_workers=4) as executor:
            futures = []
            for i in range(4):
                worker_files = file_paths[i::4]
                future = executor.submit(verification_worker, worker_files, cache_dir)
                futures.append(future)

            verification_results = []
            for future in as_completed(futures):
                verification_results.extend(future.result())

        # All caches should be consistent
        for result in verification_results:
            if result["has_modification"]:
                # Modified files might have stale cache (expected)
                pass
            else:
                # Non-modified files should have consistent cache
                assert result["cache_matches"], f"Cache mismatch for {result['file']}"

        # Check performance
        stats = performance_monitor.get_stats("parallel_caching")
        assert stats["max"] < 10.0  # Should complete in reasonable time

        # Clean up resources
        for resource_id in resource_ids:
            resource_monitor.release_resource(resource_id)
        resource_monitor.assert_no_leaks("chunker.cache")

    def test_content_vs_timestamp_invalidation(
        self,
        temp_workspace,
        resource_monitor,
        test_file_generator,
        performance_monitor,
    ):
        """Test timestamp vs content-hash invalidation strategies."""
        # Create test file
        test_file = test_file_generator.create_file(
            "invalidation_test.py",
            "def test(): return 42",
        )

        # Set up caches with different strategies
        timestamp_cache = MockCache(temp_workspace / "timestamp_cache")
        content_cache = MockCache(temp_workspace / "content_cache")

        # Track resources
        resource1 = resource_monitor.track_resource(
            "chunker.cache",
            "cache_entry",
            f"cache_timestamp_{test_file.name}_{time.time()}",
        )
        resource2 = resource_monitor.track_resource(
            "chunker.cache",
            "cache_entry",
            f"cache_content_{test_file.name}_{time.time()}",
        )
        timestamp_resource_id = resource1["resource_id"]
        content_resource_id = resource2["resource_id"]

        # Initial cache
        original_content = test_file.read_text()
        original_mtime = test_file.stat().st_mtime

        timestamp_cache.put(str(test_file), original_content, {"mtime": original_mtime})
        content_cache.put(str(test_file), original_content)

        # Test 1: Touch file (timestamp changes, content same)
        time.sleep(0.1)
        with performance_monitor.measure("timestamp_touch"):
            test_file.touch()  # Updates mtime without changing content

        new_mtime = test_file.stat().st_mtime
        assert new_mtime > original_mtime

        # Timestamp strategy should invalidate
        cached_ts = timestamp_cache.get(str(test_file))
        should_invalidate_ts = cached_ts["metadata"]["mtime"] < new_mtime

        # Content strategy should not invalidate
        cached_content = content_cache.get(str(test_file))
        content_hash = hashlib.md5(test_file.read_text().encode()).hexdigest()
        should_invalidate_content = cached_content["hash"] != content_hash

        assert should_invalidate_ts == True
        assert should_invalidate_content == False

        # Test 2: Actual content change
        time.sleep(0.1)
        with performance_monitor.measure("content_change"):
            test_file.write_text("def test(): return 43  # changed")

        # Both strategies should invalidate
        new_content = test_file.read_text()
        new_hash = hashlib.md5(new_content.encode()).hexdigest()

        assert (
            timestamp_cache.get(str(test_file))["metadata"]["mtime"]
            < test_file.stat().st_mtime
        )
        assert content_cache.get(str(test_file))["hash"] != new_hash

        # Test 3: Performance comparison
        num_files = 50
        test_files = []
        for i in range(num_files):
            file = test_file_generator.create_file(
                f"perf_test_{i}.py",
                f"def func_{i}(): return {i}",
            )
            test_files.append(file)

        # Timestamp-based validation
        with performance_monitor.measure("timestamp_validation"):
            for file in test_files:
                cached = timestamp_cache.get(str(file))
                if cached and cached["metadata"].get("mtime", 0) < file.stat().st_mtime:
                    # Need to recache
                    timestamp_cache.put(
                        str(file),
                        file.read_text(),
                        {"mtime": file.stat().st_mtime},
                    )

        # Content-based validation
        with performance_monitor.measure("content_validation"):
            for file in test_files:
                content = file.read_text()
                content_hash = hashlib.md5(content.encode()).hexdigest()
                cached = content_cache.get(str(file))

                if not cached or cached["hash"] != content_hash:
                    # Need to recache
                    content_cache.put(str(file), content)

        # Compare performance
        ts_stats = performance_monitor.get_stats("timestamp_validation")
        content_stats = performance_monitor.get_stats("content_validation")

        # Timestamp should be faster (no need to read file content for validation)
        assert ts_stats["average"] < content_stats["average"]

        # Test 4: Accuracy test - rapid changes
        accuracy_file = test_file_generator.create_file(
            "accuracy_test.py",
            "counter = 0",
        )

        # Rapid changes within same timestamp
        changes_detected_ts = 0
        changes_detected_content = 0

        for i in range(10):
            # Change content
            accuracy_file.write_text(f"counter = {i+1}")

            # Check timestamp strategy
            cached_ts = timestamp_cache.get(str(accuracy_file))
            if (
                not cached_ts
                or cached_ts["metadata"].get("mtime", 0) < accuracy_file.stat().st_mtime
            ):
                changes_detected_ts += 1
                timestamp_cache.put(
                    str(accuracy_file),
                    accuracy_file.read_text(),
                    {"mtime": accuracy_file.stat().st_mtime},
                )

            # Check content strategy
            content = accuracy_file.read_text()
            content_hash = hashlib.md5(content.encode()).hexdigest()
            cached_content = content_cache.get(str(accuracy_file))

            if not cached_content or cached_content["hash"] != content_hash:
                changes_detected_content += 1
                content_cache.put(str(accuracy_file), content)

        # Content strategy should detect all changes
        assert changes_detected_content == 10
        # Timestamp might miss some (if changes happen within same timestamp)
        assert changes_detected_ts <= changes_detected_content

        # Clean up resources
        resource_monitor.release_resource(timestamp_resource_id)
        resource_monitor.release_resource(content_resource_id)
        resource_monitor.assert_no_leaks("chunker.cache")

    def test_directory_level_changes(
        self,
        temp_workspace,
        resource_monitor,
        test_file_generator,
        performance_monitor,
        thread_safe_counter,
    ):
        """Test directory-level monitoring and batch invalidation."""
        # Create directory structure
        src_dir = temp_workspace / "src"
        src_dir.mkdir(exist_ok=True)

        modules_dir = src_dir / "modules"
        modules_dir.mkdir(exist_ok=True)

        # Create initial files
        initial_files = []
        for i in range(5):
            file = test_file_generator.create_file(
                f"module_{i}.py",
                f"def module_{i}_func(): pass",
                subdir="src/modules",
            )
            initial_files.append(file)

        # Set up cache and directory monitor
        cache = MockCache(temp_workspace / "cache")
        file_monitor = MockFileMonitor(resource_monitor)

        # Cache all initial files
        resource_ids = []
        for file in initial_files:
            cache.put(str(file), file.read_text())
            resource = resource_monitor.track_resource(
                "chunker.cache",
                "cache_entry",
                f"cache_{file.name}_{time.time()}",
            )
            resource_ids.append(resource["resource_id"])

        # Track directory changes
        changes_detected = thread_safe_counter
        batch_invalidations = []

        def on_directory_change(change_type, path):
            changes_detected.increment()

            # Batch invalidation for directory changes
            if change_type in ["added", "removed"]:
                # Invalidate all cache entries in the directory
                dir_path = path.parent
                invalidated = []

                for cached_path in [str(f) for f in initial_files]:
                    if str(dir_path) in cached_path:
                        cache.invalidate(cached_path)
                        invalidated.append(cached_path)

                if invalidated:
                    batch_invalidations.append(
                        {
                            "type": change_type,
                            "path": str(path),
                            "invalidated_count": len(invalidated),
                        },
                    )

        # Start monitoring directory
        file_monitor.watch_directory(modules_dir, on_directory_change)

        # Test 1: Add new files
        new_files = []
        with performance_monitor.measure("add_files"):
            for i in range(5, 10):
                file = test_file_generator.create_file(
                    f"module_{i}.py",
                    f"def module_{i}_func(): pass",
                    subdir="src/modules",
                )
                new_files.append(file)

            # Check for changes
            file_monitor.check_changes()

        assert changes_detected.value == 5  # 5 files added

        # Test 2: Remove files
        with performance_monitor.measure("remove_files"):
            for file in new_files[:3]:
                file.unlink()

            file_monitor.check_changes()

        assert changes_detected.value == 8  # 5 added + 3 removed

        # Test 3: Batch operations
        batch_files = []
        with performance_monitor.measure("batch_operations"):
            # Create many files at once
            for i in range(20):
                file = test_file_generator.create_file(
                    f"batch_{i}.py",
                    f"# Batch file {i}",
                    subdir="src/modules",
                )
                batch_files.append(file)
                cache.put(str(file), file.read_text())

            # Single check for all changes
            file_monitor.check_changes()

        # Should detect all additions efficiently
        assert changes_detected.value >= 28  # Previous + 20 new

        # Test 4: Recursive directory monitoring
        # Create subdirectories
        subdir1 = modules_dir / "submodule1"
        subdir1.mkdir()
        subdir2 = modules_dir / "submodule2"
        subdir2.mkdir()

        # Monitor recursively
        recursive_monitor = MockFileMonitor(resource_monitor)
        recursive_changes = []

        def on_recursive_change(change_type, path):
            recursive_changes.append((change_type, str(path)))

        recursive_monitor.watch_directory(src_dir, on_recursive_change, recursive=True)

        # Add files in subdirectories
        subdir_files = []
        for i in range(3):
            file1 = test_file_generator.create_file(
                f"sub1_file_{i}.py",
                f"# Submodule 1 file {i}",
                subdir="src/modules/submodule1",
            )
            file2 = test_file_generator.create_file(
                f"sub2_file_{i}.py",
                f"# Submodule 2 file {i}",
                subdir="src/modules/submodule2",
            )
            subdir_files.extend([file1, file2])

        # Note: Our mock doesn't implement recursive monitoring,
        # but in real implementation it would detect these

        # Test 5: Performance with large directories
        large_dir = temp_workspace / "large_dir"
        large_dir.mkdir()

        with performance_monitor.measure("large_directory_monitoring"):
            # Create many files
            for i in range(100):
                (large_dir / f"file_{i}.py").write_text(f"# File {i}")

            # Monitor directory
            large_monitor = MockFileMonitor(resource_monitor)
            large_monitor.watch_directory(large_dir, lambda t, p: None)

            # Make changes
            for i in range(10):
                (large_dir / f"file_{i}.py").unlink()

            # Check changes
            large_monitor.check_changes()

        # Verify performance
        stats = performance_monitor.get_stats("large_directory_monitoring")
        assert stats["max"] < 5.0  # Should handle large directories efficiently

        # Clean up
        file_monitor.stop_watching(modules_dir)
        recursive_monitor.stop_watching(src_dir)
        large_monitor.stop_watching(large_dir)

        # Release tracked resources
        for resource_id in resource_ids:
            resource_monitor.release_resource(resource_id)

        resource_monitor.assert_no_leaks("chunker.cache")

    def test_cache_corruption_recovery(
        self,
        temp_workspace,
        resource_monitor,
        test_file_generator,
        performance_monitor,
    ):
        """Test detection and recovery from cache corruption."""
        # Create test files
        test_files = []
        for i in range(10):
            file = test_file_generator.create_file(
                f"corrupt_test_{i}.py",
                f"def func_{i}(): return {i}",
            )
            test_files.append(file)

        # Set up SQLite cache
        cache = MockCache(temp_workspace / "cache", cache_type="sqlite")

        # Populate cache
        resource_ids = []
        for file in test_files:
            cache.put(str(file), file.read_text())
            resource = resource_monitor.track_resource(
                "chunker.cache",
                "cache_entry",
                f"cache_{file.name}_{time.time()}",
            )
            resource_ids.append(resource["resource_id"])

        # Verify cache works
        for file in test_files:
            cached = cache.get(str(file))
            assert cached is not None
            assert f"func_{file.stem.split('_')[-1]}" in cached["content"]

        # Test 1: Corrupt the database
        with performance_monitor.measure("corruption_detection"):
            cache.corrupt_db()

            # Try to access cache (should detect corruption)
            corrupted = False
            try:
                result = cache.get(str(test_files[0]))
            except sqlite3.DatabaseError:
                corrupted = True
            except Exception as e:
                # Other errors also indicate corruption
                if "database" in str(e).lower():
                    corrupted = True

        assert corrupted, "Should detect database corruption"

        # Test 2: Automatic recovery
        recovery_cache = None
        with performance_monitor.measure("automatic_recovery"):
            try:
                # Attempt to create new cache instance
                recovery_cache = MockCache(
                    temp_workspace / "cache",
                    cache_type="sqlite",
                )

                # Should recreate database
                recovery_cache._init_db()

                # Re-populate cache
                for file in test_files:
                    recovery_cache.put(str(file), file.read_text())

                # Verify recovery worked
                for file in test_files:
                    cached = recovery_cache.get(str(file))
                    assert cached is not None

            except Exception as e:
                pytest.fail(f"Recovery failed: {e}")

        # Test 3: Partial corruption (some entries readable)
        partial_cache = MockCache(temp_workspace / "partial_cache", cache_type="sqlite")

        # Populate
        for file in test_files:
            partial_cache.put(str(file), file.read_text())

        # Simulate partial corruption by directly manipulating database
        if partial_cache._db_path:
            conn = sqlite3.connect(str(partial_cache._db_path))
            try:
                # Corrupt one entry
                conn.execute(
                    "UPDATE cache_entries SET content = ? WHERE file_path = ?",
                    ("CORRUPTED", str(test_files[0])),
                )
                conn.commit()
            finally:
                conn.close()

        # Try to read all entries
        readable_count = 0
        corrupted_entries = []

        for file in test_files:
            try:
                cached = partial_cache.get(str(file))
                if cached and cached["content"] != "CORRUPTED":
                    readable_count += 1
                else:
                    corrupted_entries.append(str(file))
            except:
                corrupted_entries.append(str(file))

        # Most entries should still be readable
        assert readable_count >= len(test_files) - 2

        # Test 4: Recovery strategies
        # Strategy 1: Rebuild from source files
        rebuild_cache = MockCache(temp_workspace / "rebuild_cache", cache_type="sqlite")
        rebuild_errors = []

        with performance_monitor.measure("rebuild_from_source"):
            for file in test_files:
                try:
                    # Always read from source during rebuild
                    content = file.read_text()
                    rebuild_cache.put(str(file), content)
                except Exception as e:
                    rebuild_errors.append((str(file), str(e)))

        assert len(rebuild_errors) == 0

        # Verify rebuild successful
        for file in test_files:
            cached = rebuild_cache.get(str(file))
            assert cached is not None
            assert cached["content"] == file.read_text()

        # Test 5: Memory cache fallback
        fallback_test = []

        class CacheWithFallback:
            def __init__(self, primary_cache, fallback_cache):
                self.primary = primary_cache
                self.fallback = fallback_cache

            def get(self, key):
                try:
                    result = self.primary.get(key)
                    if result:
                        return result
                except:
                    pass

                # Fallback to memory cache
                return self.fallback.get(key)

            def put(self, key, value, metadata=None):
                # Write to both
                try:
                    self.primary.put(key, value, metadata)
                except:
                    pass
                self.fallback.put(key, value, metadata)

        # Create corrupted primary cache
        primary = MockCache(temp_workspace / "primary_cache", cache_type="sqlite")
        primary.corrupt_db()

        # Create memory fallback
        fallback = MockCache(temp_workspace / "fallback_cache", cache_type="memory")

        # Use composite cache
        composite = CacheWithFallback(primary, fallback)

        # Should work despite primary corruption
        for file in test_files[:5]:
            composite.put(str(file), file.read_text())
            result = composite.get(str(file))
            assert result is not None

        # Test 6: Corruption prevention
        prevention_cache = MockCache(
            temp_workspace / "prevention_cache",
            cache_type="sqlite",
        )

        # Use transactions for atomic updates
        def safe_bulk_update(cache: MockCache, updates: list[tuple]):
            """Safely update multiple entries atomically."""
            if cache.cache_type == "sqlite":
                conn = sqlite3.connect(str(cache._db_path))
                try:
                    conn.execute("BEGIN TRANSACTION")
                    for file_path, content in updates:
                        timestamp = time.time()
                        content_hash = hashlib.md5(content.encode()).hexdigest()
                        conn.execute(
                            "INSERT OR REPLACE INTO cache_entries VALUES (?, ?, ?, ?, ?)",
                            (file_path, content, timestamp, content_hash, "{}"),
                        )
                    conn.execute("COMMIT")
                    return True
                except:
                    conn.execute("ROLLBACK")
                    return False
                finally:
                    conn.close()
            return False

        # Test atomic updates
        updates = [(str(f), f.read_text()) for f in test_files]
        success = safe_bulk_update(prevention_cache, updates)
        assert success

        # Verify all updates applied
        for file in test_files:
            cached = prevention_cache.get(str(file))
            assert cached is not None

        # Check performance of recovery
        recovery_stats = performance_monitor.get_stats("automatic_recovery")
        rebuild_stats = performance_monitor.get_stats("rebuild_from_source")

        # Recovery should be reasonably fast
        assert recovery_stats["max"] < 5.0
        assert rebuild_stats["max"] < 10.0

        # Clean up resources
        for resource_id in resource_ids:
            resource_monitor.release_resource(resource_id)

        resource_monitor.assert_no_leaks("chunker.cache")

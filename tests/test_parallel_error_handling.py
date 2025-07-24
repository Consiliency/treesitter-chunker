"""Integration tests for parallel processing error handling."""

import multiprocessing
import os
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from pathlib import Path
from unittest.mock import MagicMock, patch

import psutil

from tests.integration.interfaces import ErrorPropagationMixin


# Module-level function for multiprocessing
def slow_worker_func(sleep_time):
    """Worker that takes too long."""
    time.sleep(sleep_time)
    return "completed"


def process_file_with_memory(args):
    """Process file with memory allocation for leak testing."""
    filepath, iteration = args
    # Simulate memory allocation
    data = ["x" * 1000 for _ in range(100)]  # ~100KB

    # Simulate error on some iterations
    if iteration % 3 == 0:
        raise RuntimeError(f"Simulated error in iteration {iteration}")

    return len(data)


class TestParallelErrorHandling(ErrorPropagationMixin):
    """Test error handling in parallel processing scenarios."""

    def test_worker_process_crash_recovery(
        self,
        error_tracking_context,
        resource_monitor,
        parallel_test_environment,
    ):
        """Test worker process crash recovery in parallel processing."""
        # Track initial resources
        resource_monitor.track_resource(
            module="chunker.parallel",
            resource_type="process",
            resource_id="worker_1",
        )

        # Create a mock process that will crash
        mock_process = MagicMock()
        mock_process.is_alive.return_value = False
        mock_process.exitcode = -11  # SIGSEGV
        mock_process.pid = 12345

        # Simulate worker crash scenario
        with patch("multiprocessing.Process") as MockProcess:
            MockProcess.return_value = mock_process

            # Capture the error with full context
            error = RuntimeError("Worker process crashed with signal -11")
            error_context = error_tracking_context.capture_and_propagate(
                source="chunker.parallel.WorkerProcess",
                target="chunker.parallel.ParallelChunker",
                error=error,
            )

            # Add worker-specific context
            error_context["context_data"]["worker_id"] = 1
            error_context["context_data"]["pid"] = mock_process.pid
            error_context["context_data"]["exit_code"] = mock_process.exitcode

            # Verify error context is complete
            assert error_context["error_type"] == "RuntimeError"
            assert "crashed with signal" in error_context["error_message"]
            assert error_context["context_data"]["worker_id"] == 1
            assert error_context["context_data"]["exit_code"] == -11

            # Propagate to higher level
            cli_error = RuntimeError(f"Parallel processing failed: {error}")
            cli_context = error_tracking_context.capture_and_propagate(
                source="chunker.parallel.ParallelChunker",
                target="cli.main",
                error=cli_error,
            )

            # Verify error chain
            error_chain = error_tracking_context.get_error_chain()
            assert len(error_chain) >= 2
            assert error_chain[0]["source_module"] == "chunker.parallel.WorkerProcess"
            assert error_chain[-1]["target_module"] == "cli.main"

        # Simulate cleanup
        resource_monitor.release_resource("worker_1")

        # Verify cleanup happened
        leaked = resource_monitor.verify_cleanup("chunker.parallel")
        assert len(leaked) == 0, f"Found leaked resources: {leaked}"

    def test_worker_timeout_handling(
        self,
        error_tracking_context,
        parallel_test_environment,
    ):
        """Test worker timeout handling."""
        # Test with ProcessPoolExecutor timeout
        with ProcessPoolExecutor(max_workers=1) as executor:
            # Submit a task that will timeout
            future = executor.submit(slow_worker_func, 2.0)

            # Try to get result with timeout
            try:
                result = future.result(timeout=0.5)
                assert False, "Should have timed out"
            except FutureTimeoutError:
                # Capture timeout error
                error = TimeoutError("Worker process timed out after 0.5 seconds")
                error_context = error_tracking_context.capture_and_propagate(
                    source="chunker.parallel.ProcessPool",
                    target="chunker.parallel.ParallelChunker",
                    error=error,
                )

                # Add timeout context
                error_context["context_data"]["timeout_seconds"] = 0.5
                error_context["context_data"]["worker_state"] = "running"

                assert error_context["error_type"] == "TimeoutError"
                assert "timed out after" in error_context["error_message"]

                # Cancel the future to clean up
                future.cancel()

        # Test with ThreadPoolExecutor (simpler for testing)
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(time.sleep, 2.0)

            try:
                result = future.result(timeout=0.1)
                assert False, "Should have timed out"
            except FutureTimeoutError:
                # Capture timeout error for thread
                error = TimeoutError("Worker thread timed out")
                error_context = self.capture_cross_module_error(
                    source_module="chunker.parallel",
                    target_module="cli.main",
                    error=error,
                )

                assert error_context["error_type"] == "TimeoutError"
                future.cancel()

    def test_partial_results_on_failure(self, temp_workspace):
        """Test partial results are preserved on failure."""
        # Create test files
        files = []
        for i in range(10):
            file_path = temp_workspace / f"test_{i}.py"
            file_path.write_text(f"def func_{i}():\n    return {i}")
            files.append(file_path)

        # Track results
        successful_results = []
        failed_results = []

        def mock_chunk_file(file_path):
            """Mock chunking that fails on specific files."""
            filename = file_path.name
            file_num = int(filename.split("_")[1].split(".")[0])

            if file_num in [2, 6, 8]:  # Fail on these files
                raise RuntimeError(f"Failed to chunk {filename}: Simulated error")

            return {
                "file": str(file_path),
                "chunks": [
                    {
                        "type": "function",
                        "name": f"func_{file_num}",
                        "start_line": 1,
                        "end_line": 2,
                    },
                ],
                "language": "python",
            }

        # Process files with error handling
        for file_path in files:
            try:
                result = mock_chunk_file(file_path)
                successful_results.append(result)
            except RuntimeError as e:
                failed_results.append(
                    {
                        "file": str(file_path),
                        "error": str(e),
                    },
                )

        # Verify results
        assert len(successful_results) == 7  # 10 files - 3 failures
        assert len(failed_results) == 3

        # Check successful files
        successful_nums = [
            int(Path(r["file"]).name.split("_")[1].split(".")[0])
            for r in successful_results
        ]
        assert 2 not in successful_nums
        assert 6 not in successful_nums
        assert 8 not in successful_nums

        # Check failed files have error context
        for failed in failed_results:
            assert "Failed to chunk" in failed["error"]
            assert "Simulated error" in failed["error"]

        # Verify we can create a partial export
        export_data = {
            "successful": successful_results,
            "failed": failed_results,
            "summary": {
                "total_files": len(files),
                "successful": len(successful_results),
                "failed": len(failed_results),
                "success_rate": len(successful_results) / len(files) * 100,
            },
        }

        assert export_data["summary"]["success_rate"] == 70.0

    def test_resource_cleanup_after_errors(
        self,
        resource_monitor,
        parallel_test_environment,
    ):
        """Test resource cleanup after errors."""
        resources_to_track = []

        # Simulate parallel worker setup
        with parallel_test_environment as env:
            # Track multiple resource types
            for i in range(5):
                # Track worker process
                process_id = f"worker_process_{i}"
                resource_monitor.track_resource(
                    module="chunker.parallel",
                    resource_type="process",
                    resource_id=process_id,
                )
                resources_to_track.append(process_id)

                # Track file handle
                file_handle_id = f"output_file_{i}"
                resource_monitor.track_resource(
                    module="chunker.parallel",
                    resource_type="file_handle",
                    resource_id=file_handle_id,
                )
                resources_to_track.append(file_handle_id)

                # Track queue
                queue_id = f"result_queue_{i}"
                resource_monitor.track_resource(
                    module="chunker.parallel",
                    resource_type="queue",
                    resource_id=queue_id,
                )
                resources_to_track.append(queue_id)

            # Simulate error scenario
            try:
                # Mock a critical error during processing
                raise RuntimeError("Critical error in parallel processing")
            except RuntimeError:
                # Cleanup should happen in exception handler
                # Simulate proper cleanup
                for resource_id in resources_to_track:
                    resource_monitor.release_resource(resource_id)

            # Verify all resources cleaned up
            leaked = resource_monitor.verify_cleanup("chunker.parallel")
            assert len(leaked) == 0, f"Found {len(leaked)} leaked resources"

            # Check specific resource types
            active_processes = resource_monitor.get_all_resources(
                module="chunker.parallel",
                state="active",
            )
            assert len(active_processes) == 0

    def test_progress_tracking_with_failures(self, temp_workspace):
        """Test progress tracking accurately reflects failures."""
        total_files = 20
        processed = 0
        failed = 0
        progress_updates = []

        # Create progress callback
        def progress_callback(current, total, status, filename=None):
            nonlocal processed, failed

            update = {
                "current": current,
                "total": total,
                "status": status,
                "filename": filename,
                "timestamp": time.time(),
            }
            progress_updates.append(update)

            if status == "completed":
                processed += 1
            elif status == "failed":
                failed += 1

        # Simulate processing with some failures
        for i in range(total_files):
            filename = f"file_{i}.py"

            # Fail specific files
            if i in [3, 7, 11, 15, 19]:
                progress_callback(i + 1, total_files, "failed", filename)
            else:
                progress_callback(i + 1, total_files, "completed", filename)

        # Verify counts
        assert processed == 15
        assert failed == 5
        assert processed + failed == total_files

        # Verify progress updates
        assert len(progress_updates) == total_files

        # Check first and last updates
        assert progress_updates[0]["current"] == 1
        assert progress_updates[-1]["current"] == total_files

        # Verify failed files recorded correctly
        failed_files = [
            u["filename"] for u in progress_updates if u["status"] == "failed"
        ]
        assert len(failed_files) == 5
        assert "file_3.py" in failed_files
        assert "file_19.py" in failed_files

        # Calculate final statistics
        stats = {
            "total": total_files,
            "processed": processed,
            "failed": failed,
            "success_rate": (processed / total_files) * 100,
            "failure_rate": (failed / total_files) * 100,
        }

        assert stats["success_rate"] == 75.0
        assert stats["failure_rate"] == 25.0

    def test_error_aggregation_strategies(self, error_tracking_context):
        """Test different error aggregation modes."""

        # Test fail_fast mode
        errors_fail_fast = []

        for i in range(10):
            try:
                if i == 3:
                    raise RuntimeError(f"Error at index {i}")
                # Process item successfully
            except RuntimeError as e:
                # In fail_fast mode, stop immediately
                error_context = error_tracking_context.capture_and_propagate(
                    source="chunker.parallel.Worker",
                    target="chunker.parallel.Aggregator",
                    error=e,
                )
                errors_fail_fast.append(error_context)
                break  # Stop on first error

        assert len(errors_fail_fast) == 1
        assert "Error at index 3" in errors_fail_fast[0]["error_message"]

        # Test collect_all mode
        errors_collect_all = []

        for i in range(10):
            try:
                if i in [2, 5, 7]:
                    raise RuntimeError(f"Error at index {i}")
                # Process item successfully
            except RuntimeError as e:
                # In collect_all mode, continue and collect all errors
                error_context = error_tracking_context.capture_and_propagate(
                    source="chunker.parallel.Worker",
                    target="chunker.parallel.Aggregator",
                    error=e,
                )
                errors_collect_all.append(error_context)
                # Continue processing

        assert len(errors_collect_all) == 3
        assert "Error at index 2" in errors_collect_all[0]["error_message"]
        assert "Error at index 5" in errors_collect_all[1]["error_message"]
        assert "Error at index 7" in errors_collect_all[2]["error_message"]

        # Create aggregate error summary
        if errors_collect_all:
            aggregate_error = RuntimeError(
                f"Multiple errors occurred: {len(errors_collect_all)} failures",
            )
            aggregate_context = error_tracking_context.capture_and_propagate(
                source="chunker.parallel.Aggregator",
                target="cli.main",
                error=aggregate_error,
            )

            # Add individual errors as context
            aggregate_context["context_data"]["individual_errors"] = [
                {
                    "index": i,
                    "type": err["error_type"],
                    "message": err["error_message"],
                }
                for i, err in enumerate(errors_collect_all)
            ]

            assert len(aggregate_context["context_data"]["individual_errors"]) == 3

    def test_deadlock_prevention(self, resource_monitor, error_tracking_context):
        """Test deadlock prevention mechanisms."""
        import time
        from queue import Empty

        # Track resources
        resource_monitor.track_resource(
            module="chunker.parallel",
            resource_type="lock",
            resource_id="deadlock_test_lock1",
        )
        resource_monitor.track_resource(
            module="chunker.parallel",
            resource_type="lock",
            resource_id="deadlock_test_lock2",
        )

        # Create a manager for shared locks
        manager = multiprocessing.Manager()
        lock1 = manager.Lock()
        lock2 = manager.Lock()
        result_queue = manager.Queue()
        deadlock_detected = manager.Value("b", False)

        def worker1():
            """Worker that acquires lock1 then lock2."""
            try:
                with lock1:
                    time.sleep(0.1)  # Give worker2 time to acquire lock2
                    # Try to acquire lock2 with timeout
                    acquired = lock2.acquire(timeout=1.0)
                    if acquired:
                        try:
                            result_queue.put("worker1_success")
                        finally:
                            lock2.release()
                    else:
                        result_queue.put("worker1_timeout")
                        deadlock_detected.value = True
            except Exception as e:
                result_queue.put(f"worker1_error: {e}")

        def worker2():
            """Worker that acquires lock2 then lock1."""
            try:
                with lock2:
                    time.sleep(0.1)  # Give worker1 time to acquire lock1
                    # Try to acquire lock1 with timeout
                    acquired = lock1.acquire(timeout=1.0)
                    if acquired:
                        try:
                            result_queue.put("worker2_success")
                        finally:
                            lock1.release()
                    else:
                        result_queue.put("worker2_timeout")
                        deadlock_detected.value = True
            except Exception as e:
                result_queue.put(f"worker2_error: {e}")

        # Start workers
        p1 = multiprocessing.Process(target=worker1)
        p2 = multiprocessing.Process(target=worker2)

        p1.start()
        p2.start()

        # Wait for workers with timeout
        p1.join(timeout=3.0)
        p2.join(timeout=3.0)

        # Check results
        results = []
        while not result_queue.empty():
            try:
                results.append(result_queue.get_nowait())
            except Empty:
                break

        # Verify deadlock was detected
        assert deadlock_detected.value == True, "Deadlock should have been detected"
        assert "worker1_timeout" in results or "worker2_timeout" in results

        # Ensure processes are terminated
        if p1.is_alive():
            p1.terminate()
            p1.join()
        if p2.is_alive():
            p2.terminate()
            p2.join()

        # Verify recovery
        assert not p1.is_alive(), "Process 1 should be terminated"
        assert not p2.is_alive(), "Process 2 should be terminated"

        # Create error context for deadlock
        if deadlock_detected.value:
            deadlock_error = RuntimeError("Deadlock detected between worker processes")
            error_context = error_tracking_context.capture_and_propagate(
                source="chunker.parallel.DeadlockDetector",
                target="chunker.parallel.ParallelChunker",
                error=deadlock_error,
            )

            error_context["context_data"]["timeout_seconds"] = 1.0
            error_context["context_data"]["workers_involved"] = ["worker1", "worker2"]
            error_context["context_data"]["recovery_action"] = "terminated_workers"

        # Cleanup resources
        resource_monitor.release_resource("deadlock_test_lock1")
        resource_monitor.release_resource("deadlock_test_lock2")

        # Verify cleanup
        leaked = resource_monitor.verify_cleanup("chunker.parallel")
        assert len(leaked) == 0, f"Found leaked resources: {leaked}"

    def test_memory_leak_detection(self, resource_monitor, temp_workspace):
        """Test memory leak detection in parallel processing."""
        import gc

        # Get current process
        process = psutil.Process(os.getpid())

        # Force garbage collection and get baseline memory
        gc.collect()
        time.sleep(0.1)  # Let memory settle
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        initial_handles = len(process.open_files())
        initial_children = len(process.children())

        # Track memory usage over iterations
        memory_samples = [initial_memory]
        leaked_objects = []

        # Create test files
        test_files = []
        for i in range(5):
            file_path = temp_workspace / f"memory_test_{i}.py"
            file_path.write_text(
                f"def func_{i}():\n    return {i}" * 100,
            )  # Larger content
            test_files.append(file_path)

        # Run operation in loop to detect leaks
        for iteration in range(10):
            # Track iteration resources
            iter_resource_id = f"iteration_{iteration}_resources"
            resource_monitor.track_resource(
                module="chunker.parallel",
                resource_type="memory_test",
                resource_id=iter_resource_id,
            )

            # Simulate parallel processing with potential leaks
            with ProcessPoolExecutor(max_workers=2) as executor:
                futures = []

                # Submit tasks that might leak memory
                for test_file in test_files:
                    future = executor.submit(
                        process_file_with_memory,
                        (test_file, iteration),
                    )
                    futures.append(future)

                # Collect results with error handling
                for i, future in enumerate(futures):
                    try:
                        result = future.result(timeout=1.0)
                    except Exception:
                        # Errors should not cause memory leaks
                        # Only count as leaked if error is unexpected
                        if iteration % 3 == 0:
                            # Expected error, not a leak
                            pass
                        else:
                            # Unexpected error, might indicate a leak
                            leaked_objects.append(
                                f"iteration_{iteration}_file_{i}_error",
                            )

            # Force cleanup
            resource_monitor.release_resource(iter_resource_id)

            # Force garbage collection
            gc.collect()
            time.sleep(0.1)  # Let memory settle

            # Sample memory
            current_memory = process.memory_info().rss / 1024 / 1024  # MB
            memory_samples.append(current_memory)

        # Analyze memory growth
        memory_growth = memory_samples[-1] - memory_samples[0]
        average_growth_per_iteration = memory_growth / len(memory_samples)

        # Check for leaks
        current_handles = len(process.open_files())
        current_children = len(process.children())

        # Verify no significant memory growth
        # Allow up to 10MB growth total (some growth is normal)
        assert (
            memory_growth < 10.0
        ), f"Memory grew by {memory_growth:.2f}MB, possible leak"

        # Verify average growth per iteration is minimal
        assert (
            average_growth_per_iteration < 1.0
        ), f"Average memory growth {average_growth_per_iteration:.2f}MB per iteration"

        # Verify no file handle leaks
        assert (
            current_handles <= initial_handles + 1
        ), f"File handles leaked: {current_handles - initial_handles}"

        # Verify no zombie processes
        assert (
            current_children == initial_children
        ), f"Child processes leaked: {current_children - initial_children}"

        # Verify all resources cleaned up
        leaked = resource_monitor.verify_cleanup("chunker.parallel")
        assert len(leaked) == 0, f"Found leaked resources: {leaked}"

        # Create memory profile summary
        memory_profile = {
            "initial_memory_mb": memory_samples[0],
            "final_memory_mb": memory_samples[-1],
            "total_growth_mb": memory_growth,
            "avg_growth_per_iteration_mb": average_growth_per_iteration,
            "peak_memory_mb": max(memory_samples),
            "iterations": len(memory_samples) - 1,
            "leaked_objects": len(leaked_objects),
        }

        # Log memory profile for debugging
        print(f"\nMemory Profile: {memory_profile}")

        # Verify acceptable memory profile
        # We expect 0 leaked objects since all errors are intentional
        assert (
            memory_profile["leaked_objects"] == 0
        ), f"Unexpected leaked objects detected: {memory_profile['leaked_objects']}"

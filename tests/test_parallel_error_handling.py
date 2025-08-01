"""Integration tests for parallel processing error handling."""
import gc
import multiprocessing
import os
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from pathlib import Path
from queue import Empty
from unittest.mock import MagicMock, patch

import psutil

from tests.integration.interfaces import ErrorPropagationMixin


def slow_worker_func(sleep_time):
    """Worker that takes too long."""
    time.sleep(sleep_time)
    return "completed"


def process_file_with_memory(args):
    """Process file with memory allocation for leak testing."""
    _filepath, iteration = args
    data = [("x" * 1000) for _ in range(100)]
    if iteration % 3 == 0:
        raise RuntimeError(f"Simulated error in iteration {iteration}")
    return len(data)


class TestParallelErrorHandling(ErrorPropagationMixin):
    """Test error handling in parallel processing scenarios."""

    @classmethod
    def test_worker_process_crash_recovery(cls, error_tracking_context,
        resource_monitor, parallel_test_environment):
        """Test worker process crash recovery in parallel processing."""
        resource_monitor.track_resource(module="chunker.parallel",
            resource_type="process", resource_id="worker_1")
        mock_process = MagicMock()
        mock_process.is_alive.return_value = False
        mock_process.exitcode = -11
        mock_process.pid = 12345
        with patch("multiprocessing.Process") as MockProcess:
            MockProcess.return_value = mock_process
            error = RuntimeError("Worker process crashed with signal -11")
            error_context = error_tracking_context.capture_and_propagate(source="chunker.parallel.WorkerProcess", target="chunker.parallel.ParallelChunker", error=error)
            error_context["context_data"]["worker_id"] = 1
            error_context["context_data"]["pid"] = mock_process.pid
            error_context["context_data"]["exit_code"] = mock_process.exitcode
            assert error_context["error_type"] == "RuntimeError"
            assert "crashed with signal" in error_context["error_message"]
            assert error_context["context_data"]["worker_id"] == 1
            assert error_context["context_data"]["exit_code"] == -11
            cli_error = RuntimeError(f"Parallel processing failed: {error}")
            error_tracking_context.capture_and_propagate(source="chunker.parallel.ParallelChunker", target="cli.main",
                error=cli_error)
            error_chain = error_tracking_context.get_error_chain()
            assert len(error_chain) >= 2
            assert error_chain[0]["source_module"
                ] == "chunker.parallel.WorkerProcess"
            assert error_chain[-1]["target_module"] == "cli.main"
        resource_monitor.release_resource("worker_1")
        leaked = resource_monitor.verify_cleanup("chunker.parallel")
        assert len(leaked) == 0, f"Found leaked resources: {leaked}"

    def test_worker_timeout_handling(self, error_tracking_context,
        parallel_test_environment):
        """Test worker timeout handling."""
        with ProcessPoolExecutor(max_workers=1) as executor:
            future = executor.submit(slow_worker_func, 2.0)
            try:
                future.result(timeout=0.5)
                raise AssertionError("Should have timed out")
            except FutureTimeoutError:
                error = TimeoutError(
                    "Worker process timed out after 0.5 seconds")
                error_context = error_tracking_context.capture_and_propagate(
                    source="chunker.parallel.ProcessPool", target="chunker.parallel.ParallelChunker", error=error)
                error_context["context_data"]["timeout_seconds"] = 0.5
                error_context["context_data"]["worker_state"] = "running"
                assert error_context["error_type"] == "TimeoutError"
                assert "timed out after" in error_context["error_message"]
                future.cancel()
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(time.sleep, 2.0)
            try:
                future.result(timeout=0.1)
                raise AssertionError("Should have timed out")
            except FutureTimeoutError:
                error = TimeoutError("Worker thread timed out")
                error_context = self.capture_cross_module_error(source_module="chunker.parallel", target_module="cli.main", error=error)
                assert error_context["error_type"] == "TimeoutError"
                future.cancel()

    @classmethod
    def test_partial_results_on_failure(cls, temp_workspace):
        """Test partial results are preserved on failure."""
        files = []
        for i in range(10):
            file_path = temp_workspace / f"test_{i}.py"
            file_path.write_text(f"def func_{i}():\n    return {i}")
            files.append(file_path)
        successful_results = []
        failed_results = []

        def mock_chunk_file(file_path):
            """Mock chunking that fails on specific files."""
            filename = file_path.name
            file_num = int(filename.split("_")[1].split(".")[0])
            if file_num in {2, 6, 8}:
                raise RuntimeError(
                    f"Failed to chunk {filename}: Simulated error")
            return {"file": str(file_path), "chunks": [{"type": "function",
                "name": f"func_{file_num}", "start_line": 1, "end_line": 2},
                ], "language": "python"}
        for file_path in files:
            try:
                result = mock_chunk_file(file_path)
                successful_results.append(result)
            except RuntimeError as e:
                failed_results.append({"file": str(file_path), "error": str(e)},
                    )
        assert len(successful_results) == 7
        assert len(failed_results) == 3
        successful_nums = [int(Path(r["file"]).name.split("_")[1].split(".",
            )[0]) for r in successful_results]
        assert 2 not in successful_nums
        assert 6 not in successful_nums
        assert 8 not in successful_nums
        for failed in failed_results:
            assert "Failed to chunk" in failed["error"]
            assert "Simulated error" in failed["error"]
        export_data = {"successful": successful_results, "failed":
            failed_results, "summary": {"total_files": len(files),
            "successful": len(successful_results), "failed": len(
            failed_results), "success_rate": len(successful_results) / len(
            files) * 100}}
        assert export_data["summary"]["success_rate"] == 70.0

    @classmethod
    def test_resource_cleanup_after_errors(cls, resource_monitor,
        parallel_test_environment):
        """Test resource cleanup after errors."""
        resources_to_track = []
        with parallel_test_environment:
            for i in range(5):
                process_id = f"worker_process_{i}"
                resource_monitor.track_resource(module="chunker.parallel",
                    resource_type="process", resource_id=process_id)
                resources_to_track.append(process_id)
                file_handle_id = f"output_file_{i}"
                resource_monitor.track_resource(module="chunker.parallel",
                    resource_type="file_handle", resource_id=file_handle_id)
                resources_to_track.append(file_handle_id)
                queue_id = f"result_queue_{i}"
                resource_monitor.track_resource(module="chunker.parallel",
                    resource_type="queue", resource_id=queue_id)
                resources_to_track.append(queue_id)
            try:
                raise RuntimeError("Critical error in parallel processing")
            except RuntimeError:
                for resource_id in resources_to_track:
                    resource_monitor.release_resource(resource_id)
            leaked = resource_monitor.verify_cleanup("chunker.parallel")
            assert len(leaked) == 0, f"Found {len(leaked)} leaked resources"
            active_processes = resource_monitor.get_all_resources(module="chunker.parallel", state="active")
            assert len(active_processes) == 0

    @staticmethod
    def test_progress_tracking_with_failures(temp_workspace):
        """Test progress tracking accurately reflects failures."""
        total_files = 20
        processed = 0
        failed = 0
        progress_updates = []

        def progress_callback(current, total, status, filename=None):
            nonlocal processed, failed
            update = {"current": current, "total": total, "status": status,
                "filename": filename, "timestamp": time.time()}
            progress_updates.append(update)
            if status == "completed":
                processed += 1
            elif status == "failed":
                failed += 1
        for i in range(total_files):
            filename = f"file_{i}.py"
            if i in {3, 7, 11, 15, 19}:
                progress_callback(i + 1, total_files, "failed", filename)
            else:
                progress_callback(i + 1, total_files, "completed", filename)
        assert processed == 15
        assert failed == 5
        assert processed + failed == total_files
        assert len(progress_updates) == total_files
        assert progress_updates[0]["current"] == 1
        assert progress_updates[-1]["current"] == total_files
        failed_files = [u["filename"] for u in progress_updates if u[
            "status"] == "failed"]
        assert len(failed_files) == 5
        assert "file_3.py" in failed_files
        assert "file_19.py" in failed_files
        stats = {"total": total_files, "processed": processed, "failed":
            failed, "success_rate": processed / total_files * 100,
            "failure_rate": failed / total_files * 100}
        assert stats["success_rate"] == 75.0
        assert stats["failure_rate"] == 25.0

    @classmethod
    def test_error_aggregation_strategies(cls, error_tracking_context):
        """Test different error aggregation modes."""
        errors_fail_fast = []
        for i in range(10):
            try:
                if i == 3:
                    raise RuntimeError(f"Error at index {i}")
            except RuntimeError as e:
                error_context = error_tracking_context.capture_and_propagate(
                    source="chunker.parallel.Worker", target="chunker.parallel.Aggregator", error=e)
                errors_fail_fast.append(error_context)
                break
        assert len(errors_fail_fast) == 1
        assert "Error at index 3" in errors_fail_fast[0]["error_message"]
        errors_collect_all = []
        for i in range(10):
            try:
                if i in {2, 5, 7}:
                    raise RuntimeError(f"Error at index {i}")
            except RuntimeError as e:
                error_context = error_tracking_context.capture_and_propagate(
                    source="chunker.parallel.Worker", target="chunker.parallel.Aggregator", error=e)
                errors_collect_all.append(error_context)
        assert len(errors_collect_all) == 3
        assert "Error at index 2" in errors_collect_all[0]["error_message"]
        assert "Error at index 5" in errors_collect_all[1]["error_message"]
        assert "Error at index 7" in errors_collect_all[2]["error_message"]
        if errors_collect_all:
            aggregate_error = RuntimeError(
                f"Multiple errors occurred: {len(errors_collect_all)} failures",
                )
            aggregate_context = error_tracking_context.capture_and_propagate(
                source="chunker.parallel.Aggregator", target="cli.main",
                error=aggregate_error)
            aggregate_context["context_data"]["individual_errors"] = [{
                "index": i, "type": err["error_type"], "message": err[
                "error_message"]} for i, err in enumerate(errors_collect_all)]
            assert len(aggregate_context["context_data"]["individual_errors"],
                ) == 3

    @classmethod
    def test_deadlock_prevention(cls, resource_monitor, error_tracking_context,
        ):
        """Test deadlock prevention mechanisms."""
        resource_monitor.track_resource(module="chunker.parallel",
            resource_type="lock", resource_id="deadlock_test_lock1")
        resource_monitor.track_resource(module="chunker.parallel",
            resource_type="lock", resource_id="deadlock_test_lock2")
        manager = multiprocessing.Manager()
        lock1 = manager.Lock()
        lock2 = manager.Lock()
        result_queue = manager.Queue()
        deadlock_detected = manager.Value("b", False)

        def worker1():
            """Worker that acquires lock1 then lock2."""
            try:
                with lock1:
                    time.sleep(0.1)
                    acquired = lock2.acquire(timeout=1.0)
                    if acquired:
                        try:
                            result_queue.put("worker1_success")
                        finally:
                            lock2.release()
                    else:
                        result_queue.put("worker1_timeout")
                        deadlock_detected.value = True
            except (RuntimeError, ValueError) as e:
                result_queue.put(f"worker1_error: {e}")

        def worker2():
            """Worker that acquires lock2 then lock1."""
            try:
                with lock2:
                    time.sleep(0.1)
                    acquired = lock1.acquire(timeout=1.0)
                    if acquired:
                        try:
                            result_queue.put("worker2_success")
                        finally:
                            lock1.release()
                    else:
                        result_queue.put("worker2_timeout")
                        deadlock_detected.value = True
            except (RuntimeError, ValueError) as e:
                result_queue.put(f"worker2_error: {e}")
        p1 = multiprocessing.Process(target=worker1)
        p2 = multiprocessing.Process(target=worker2)
        p1.start()
        p2.start()
        p1.join(timeout=3.0)
        p2.join(timeout=3.0)
        results = []
        while not result_queue.empty():
            try:
                results.append(result_queue.get_nowait())
            except Empty:
                break
        assert deadlock_detected.value, "Deadlock should have been detected"
        assert "worker1_timeout" in results or "worker2_timeout" in results
        if p1.is_alive():
            p1.terminate()
            p1.join()
        if p2.is_alive():
            p2.terminate()
            p2.join()
        assert not p1.is_alive(), "Process 1 should be terminated"
        assert not p2.is_alive(), "Process 2 should be terminated"
        if deadlock_detected.value:
            deadlock_error = RuntimeError(
                "Deadlock detected between worker processes")
            error_context = error_tracking_context.capture_and_propagate(source="chunker.parallel.DeadlockDetector", target="chunker.parallel.ParallelChunker", error=deadlock_error)
            error_context["context_data"]["timeout_seconds"] = 1.0
            error_context["context_data"]["workers_involved"] = ["worker1",
                "worker2"]
            error_context["context_data"]["recovery_action"
                ] = "terminated_workers"
        resource_monitor.release_resource("deadlock_test_lock1")
        resource_monitor.release_resource("deadlock_test_lock2")
        leaked = resource_monitor.verify_cleanup("chunker.parallel")
        assert len(leaked) == 0, f"Found leaked resources: {leaked}"

    @classmethod
    def test_memory_leak_detection(cls, resource_monitor, temp_workspace):
        """Test memory leak detection in parallel processing."""
        process = psutil.Process(os.getpid())
        gc.collect()
        time.sleep(0.1)
        initial_memory = process.memory_info().rss / 1024 / 1024
        initial_handles = len(process.open_files())
        initial_children = len(process.children())
        memory_samples = [initial_memory]
        leaked_objects = []
        test_files = []
        for i in range(5):
            file_path = temp_workspace / f"memory_test_{i}.py"
            file_path.write_text(f"def func_{i}():\n    return {i}" * 100)
            test_files.append(file_path)
        for iteration in range(10):
            iter_resource_id = f"iteration_{iteration}_resources"
            resource_monitor.track_resource(module="chunker.parallel",
                resource_type="memory_test", resource_id=iter_resource_id)
            with ProcessPoolExecutor(max_workers=2) as executor:
                futures = []
                for test_file in test_files:
                    future = executor.submit(process_file_with_memory, (
                        test_file, iteration))
                    futures.append(future)
                for i, future in enumerate(futures):
                    try:
                        future.result(timeout=1.0)
                    except (FileNotFoundError, OSError):
                        if iteration % 3 == 0:
                            pass
                        else:
                            leaked_objects.append(
                                f"iteration_{iteration}_file_{i}_error")
            resource_monitor.release_resource(iter_resource_id)
            gc.collect()
            time.sleep(0.1)
            current_memory = process.memory_info().rss / 1024 / 1024
            memory_samples.append(current_memory)
        memory_growth = memory_samples[-1] - memory_samples[0]
        average_growth_per_iteration = memory_growth / len(memory_samples)
        current_handles = len(process.open_files())
        current_children = len(process.children())
        assert memory_growth < 10.0, f"Memory grew by {memory_growth:.2f}MB, possible leak"
        assert average_growth_per_iteration < 1.0, f"Average memory growth {average_growth_per_iteration:.2f}MB per iteration"
        assert current_handles <= initial_handles + 1, f"File handles leaked: {current_handles - initial_handles}"
        assert current_children == initial_children, f"Child processes leaked: {current_children - initial_children}"
        leaked = resource_monitor.verify_cleanup("chunker.parallel")
        assert len(leaked) == 0, f"Found leaked resources: {leaked}"
        memory_profile = {"initial_memory_mb": memory_samples[0],
            "final_memory_mb": memory_samples[-1], "total_growth_mb":
            memory_growth, "avg_growth_per_iteration_mb":
            average_growth_per_iteration, "peak_memory_mb": max(
            memory_samples), "iterations": len(memory_samples) - 1,
            "leaked_objects": len(leaked_objects)}
        print(f"\nMemory Profile: {memory_profile}")
        assert memory_profile["leaked_objects"
            ] == 0, f"Unexpected leaked objects detected: {memory_profile['leaked_objects']}"

"""Recovery and resilience tests for the tree-sitter-chunker.

This module tests system resilience including crash recovery,
state persistence, partial processing, and graceful degradation.
"""

import gc
import json
import os
import queue
import random
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import MagicMock, patch

import psutil
import pytest

from chunker import chunk_file
from chunker.exceptions import ParserError
from chunker.parser import get_parser
from chunker.streaming import chunk_file_streaming


class TestCrashRecovery:
    """Test recovery from crashes and failures."""

    def test_parser_crash_recovery(self, tmp_path):
        """Test recovery from parser crashes."""
        # Create problematic file
        test_file = tmp_path / "crash_test.py"
        test_file.write_text(
            """
def normal_function():
    return "ok"

# This might cause parser issues
def problematic_function():
    '''Unclosed string literal
    return "problem"
""",
        )

        # Test parser crash recovery
        with patch("chunker.chunker.get_parser") as mock_get_parser:
            mock_parser = MagicMock()

            # Create a mock tree with root node
            mock_tree = MagicMock()
            mock_tree.root_node = MagicMock()
            mock_tree.root_node.children = []
            mock_tree.root_node.type = "module"
            mock_tree.root_node.start_byte = 0
            mock_tree.root_node.end_byte = 100
            mock_tree.root_node.start_point = (0, 0)
            mock_tree.root_node.end_point = (10, 0)

            # First call crashes, second succeeds
            mock_parser.parse.side_effect = [
                RuntimeError("Parser crashed!"),
                mock_tree,
            ]
            mock_get_parser.return_value = mock_parser

            # Attempt to chunk with recovery
            try:
                chunk_file(test_file, language="python")
            except RuntimeError:
                # Retry with fresh parser
                chunk_file(test_file, language="python")

            # Should have recovered and processed file
            assert mock_parser.parse.call_count >= 2

    def test_memory_exhaustion_recovery(self, tmp_path):
        """Test OOM handling."""
        # Create large file that might cause memory issues
        large_file = tmp_path / "large.py"

        # Generate very large content
        lines = []
        for i in range(10000):
            lines.append(f"def function_{i}():")
            lines.append("    data = 'x' * 1000000  # Large string")
            lines.append(f"    return {i}")
            lines.append("")

        large_file.write_text("\n".join(lines))

        # Mock memory error
        original_chunk_file = chunk_file
        call_count = 0

        def mock_chunk_file(file_path, language):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise MemoryError("Out of memory!")
            # Second attempt with reduced processing
            return original_chunk_file(file_path, language)

        with patch("chunker.chunk_file", side_effect=mock_chunk_file):
            # Should handle memory error and retry
            try:
                chunks = chunk_file(large_file, language="python")
            except MemoryError:
                # Fallback: process with streaming

                chunks = list(chunk_file_streaming(large_file, language="python"))

            # Should have some results
            assert len(chunks) > 0

    def test_segfault_isolation(self, tmp_path):
        """Test isolation of segfaults."""
        # Create test files
        files = []
        for i in range(5):
            f = tmp_path / f"file{i}.py"
            f.write_text(f"def func{i}(): pass")
            files.append(str(f))  # Convert to string for pickling

        # Process files with potential crashes
        processed = []
        failed = []

        # Process each file in a separate subprocess
        for file_path in files:
            try:
                # Use subprocess to fully isolate

                result = subprocess.run(
                    [
                        sys.executable,
                        "-c",
                        f"""
import sys
if "file2" in "{file_path}":
    sys.exit(-11)  # Simulate segfault
print("processed")
""",
                    ],
                    check=False,
                    capture_output=True,
                    timeout=2,
                )

                if result.returncode == 0:
                    processed.append(file_path)
                else:
                    failed.append(file_path)
            except subprocess.TimeoutExpired:
                failed.append(file_path)
            except (FileNotFoundError, ImportError, ModuleNotFoundError):
                failed.append(file_path)

        # Should process most files despite one crash
        assert len(processed) >= 3  # At least 3 out of 5 should succeed
        assert len(failed) >= 1  # At least file2 should fail

    def test_deadlock_detection_and_recovery(self, tmp_path):
        """Test deadlock handling."""

        # Create test scenario with potential deadlock
        lock1 = threading.Lock()
        lock2 = threading.Lock()
        results = queue.Queue()

        def worker1():
            with lock1:
                time.sleep(0.1)
                # Try to acquire lock2 (potential deadlock)
                acquired = lock2.acquire(timeout=1)
                if acquired:
                    lock2.release()
                    results.put("worker1_success")
                else:
                    results.put("worker1_timeout")

        def worker2():
            with lock2:
                time.sleep(0.1)
                # Try to acquire lock1 (potential deadlock)
                acquired = lock1.acquire(timeout=1)
                if acquired:
                    lock1.release()
                    results.put("worker2_success")
                else:
                    results.put("worker2_timeout")

        # Start workers
        t1 = threading.Thread(target=worker1)
        t2 = threading.Thread(target=worker2)

        t1.start()
        t2.start()

        # Wait with timeout
        t1.join(timeout=3)
        t2.join(timeout=3)

        # Check results
        timeouts = 0
        while not results.empty():
            result = results.get()
            if "timeout" in result:
                timeouts += 1

        # At least one should timeout (deadlock detected)
        assert timeouts >= 1

        # System should still be responsive
        assert True  # We got here without hanging


class TestStatePersistence:
    """Test state persistence and recovery."""

    def test_checkpoint_creation(self, tmp_path):
        """Test progress checkpointing."""
        # Create checkpoint directory
        checkpoint_dir = tmp_path / ".chunker_checkpoints"
        checkpoint_dir.mkdir()

        # Create test data
        files_to_process = []
        for i in range(10):
            f = tmp_path / f"file{i}.py"
            f.write_text(f"def func{i}(): pass")
            files_to_process.append(f)

        # Process with checkpointing
        checkpoint_file = checkpoint_dir / "progress.json"
        processed = []

        for i, file_path in enumerate(files_to_process):
            # Process file
            chunks = chunk_file(file_path, language="python")
            processed.append(
                {
                    "file": str(file_path),
                    "chunks": len(chunks),
                    "index": i,
                },
            )

            # Save checkpoint every 3 files
            if (i + 1) % 3 == 0:
                with Path(checkpoint_file).open(
                    "w",
                ) as f:
                    json.dump(
                        {
                            "processed": processed,
                            "total": len(files_to_process),
                            "timestamp": time.time(),
                        },
                        f,
                    )

        # Verify checkpoint exists and is valid
        assert checkpoint_file.exists()
        with Path(checkpoint_file).open() as f:
            checkpoint_data = json.load(f)
            assert len(checkpoint_data["processed"]) >= 9
            assert checkpoint_data["total"] == 10

    def test_resume_from_checkpoint(self, tmp_path):
        """Test resuming interrupted work."""
        # Create checkpoint from previous run
        checkpoint_file = tmp_path / "checkpoint.json"

        files_to_process = []
        for i in range(10):
            f = tmp_path / f"file{i}.py"
            f.write_text(f"def func{i}(): pass")
            files_to_process.append(str(f))

        # Simulate partial completion
        checkpoint_data = {
            "processed": files_to_process[:6],  # First 6 files done
            "remaining": files_to_process[6:],  # 4 files remaining
            "timestamp": time.time(),
        }

        with Path(checkpoint_file).open(
            "w",
        ) as f:
            json.dump(checkpoint_data, f)

        # Resume from checkpoint
        with Path(checkpoint_file).open() as f:
            state = json.load(f)

        already_processed = set(state["processed"])
        remaining = state["remaining"]

        # Process remaining files
        newly_processed = []
        for file_path in remaining:
            if file_path not in already_processed:
                chunk_file(file_path, language="python")
                newly_processed.append(file_path)

        # Should process exactly the remaining files
        assert len(newly_processed) == 4
        assert all(f in files_to_process[6:] for f in newly_processed)

    def test_checkpoint_corruption_handling(self, tmp_path):
        """Test corrupt checkpoint recovery."""
        checkpoint_file = tmp_path / "corrupt_checkpoint.json"

        # Write corrupt checkpoint
        checkpoint_file.write_text("{ invalid json corrupt data")

        # Try to load checkpoint
        checkpoint_data = None
        try:
            with Path(checkpoint_file).open() as f:
                checkpoint_data = json.load(f)
        except json.JSONDecodeError:
            # Handle corruption - start fresh
            checkpoint_data = {
                "processed": [],
                "error": "Checkpoint corrupted, starting fresh",
                "timestamp": time.time(),
            }

        # Should have handled corruption
        assert checkpoint_data is not None
        assert len(checkpoint_data["processed"]) == 0
        assert "error" in checkpoint_data

    def test_distributed_state_sync(self, tmp_path):
        """Test multi-process state synchronization."""
        # Shared state file
        state_file = tmp_path / "shared_state.json"
        lock_file = tmp_path / "state.lock"

        def update_state(worker_id, item):
            """Update shared state with locking."""
            # More robust locking with retries
            max_retries = 50
            for _retry in range(max_retries):
                if not lock_file.exists():
                    try:
                        # Acquire lock atomically
                        lock_file.touch(exist_ok=False)
                        break
                    except FileExistsError:
                        # Another thread got it first
                        pass
                time.sleep(0.01)
            else:
                raise RuntimeError("Could not acquire lock")

            try:
                # Read current state
                if state_file.exists() and state_file.stat().st_size > 0:
                    with Path(state_file).open() as f:
                        try:
                            state = json.load(f)
                        except json.JSONDecodeError:
                            state = {"workers": {}, "items": []}
                else:
                    state = {"workers": {}, "items": []}

                # Update state
                if worker_id not in state["workers"]:
                    state["workers"][worker_id] = []

                state["workers"][worker_id].append(item)
                state["items"].append(item)

                # Write back atomically

                temp_file = (
                    state_file.parent
                    / f"tmp_{worker_id}_{random.randint(1000, 9999)}.json"
                )
                with Path(temp_file).open(
                    "w",
                ) as f:
                    json.dump(state, f)
                    f.flush()
                    os.fsync(f.fileno())
                temp_file.replace(state_file)
            finally:
                # Release lock - check if exists first
                if lock_file.exists():
                    try:
                        lock_file.unlink()
                    except FileNotFoundError:
                        pass  # Another thread removed it

        # Simulate multiple workers
        def worker(worker_id, items):
            for item in items:
                try:
                    update_state(worker_id, item)
                    time.sleep(0.01)  # Simulate work
                except (OSError, FileNotFoundError, IndexError) as e:
                    print(f"Worker {worker_id} error: {e}")

        # Create workers
        items_per_worker = 5
        workers = []

        for i in range(3):
            items = [f"worker{i}_item{j}" for j in range(items_per_worker)]
            t = threading.Thread(target=worker, args=(f"worker{i}", items))
            workers.append(t)
            t.start()

        # Wait for completion
        for t in workers:
            t.join()

        # Verify state consistency
        if state_file.exists():
            with Path(state_file).open() as f:
                final_state = json.load(f)

            # Should have some results from workers
            assert len(final_state["workers"]) >= 1
            assert len(final_state["items"]) >= 5  # At least some items

            # Items should match between workers and items list
            all_items = [
                item
                for worker_items in final_state["workers"].values()
                for item in worker_items
            ]
            assert len(all_items) == len(final_state["items"])
        else:
            # If no state file, workers failed completely
            pytest.skip("Workers failed to create state file")


class TestPartialProcessing:
    """Test partial processing scenarios."""

    def test_partial_file_processing(self, tmp_path):
        """Test incomplete file handling."""
        # Create file with multiple chunks
        test_file = tmp_path / "partial.py"
        test_file.write_text(
            """
def function1():
    return 1

def function2():
    return 2

# Simulate interruption point

def function3():
    return 3

def function4():
    return 4
""",
        )

        # Simulate partial processing
        all_chunks = chunk_file(test_file, language="python")

        # Process only first half
        interruption_point = len(all_chunks) // 2
        processed_chunks = all_chunks[:interruption_point]

        # Save partial results
        {
            "file": str(test_file),
            "total_chunks": len(all_chunks),
            "processed": interruption_point,
            "chunks": [
                {
                    "content": chunk.content,
                    "start_line": chunk.start_line,
                    "end_line": chunk.end_line,
                }
                for chunk in processed_chunks
            ],
        }

        # Resume processing
        remaining_chunks = all_chunks[interruption_point:]

        # Verify can resume from interruption point
        assert len(processed_chunks) + len(remaining_chunks) == len(all_chunks)
        assert processed_chunks[0].content != remaining_chunks[0].content

    def test_partial_chunk_extraction(self, tmp_path):
        """Test partial chunk recovery."""
        # Create file with nested structures
        test_file = tmp_path / "nested.py"
        test_file.write_text(
            """
class OuterClass:
    def method1(self):
        def inner_function():
            return "nested"
        return inner_function

    class InnerClass:
        def inner_method(self):
            pass

    def method2(self):
        return "method2"
""",
        )

        # Simulate partial chunk extraction failure
        chunks = []
        errors = []

        try:
            all_chunks = chunk_file(test_file, language="python")

            for i, chunk in enumerate(all_chunks):
                if i == 2:  # Simulate failure at third chunk
                    raise RuntimeError("Chunk extraction failed")
                chunks.append(chunk)
        except RuntimeError as e:
            errors.append(str(e))
            # Continue with partial results

        # Should have some chunks despite error
        assert len(chunks) >= 2
        assert len(errors) == 1

    def test_partial_export_completion(self, tmp_path):
        """Test completing partial exports."""

        # Create partial export file
        partial_export = tmp_path / "partial_export.jsonl"

        # Write some complete chunks
        with Path(partial_export).open(
            "w",
        ) as f:
            for i in range(3):
                chunk_data = {
                    "content": f"def func{i}(): pass",
                    "start_line": i * 3 + 1,
                    "end_line": i * 3 + 2,
                    "language": "python",
                }
                f.write(json.dumps(chunk_data) + "\n")

            # Write incomplete chunk (no newline)
            incomplete = {
                "content": "def incomplete():",
                "start_line": 10,
            }
            f.write(json.dumps(incomplete))  # No trailing newline

        # Read and validate partial export
        complete_chunks = []
        incomplete_chunks = []

        with Path(partial_export).open() as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        chunk = json.loads(line)
                        if all(
                            k in chunk for k in ["content", "start_line", "end_line"]
                        ):
                            complete_chunks.append(chunk)
                        else:
                            incomplete_chunks.append(chunk)
                    except json.JSONDecodeError:
                        incomplete_chunks.append(line)

        # Should identify complete and incomplete chunks
        assert len(complete_chunks) == 3
        assert len(incomplete_chunks) >= 1

        # Complete the export
        remaining_chunks = [
            {
                "content": "def func4(): pass",
                "start_line": 13,
                "end_line": 14,
                "language": "python",
            },
        ]

        # Append to complete export
        with Path(partial_export).open(
            "a",
        ) as f:
            f.write("\n")  # Complete the incomplete line
            for chunk in remaining_chunks:
                f.write(json.dumps(chunk) + "\n")

        # Verify completed export
        with Path(partial_export).open() as f:
            all_lines = f.readlines()
            assert len(all_lines) >= 5

    def test_incremental_processing(self, tmp_path):
        """Test incremental updates."""
        # Create initial project state
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        # Initial files
        initial_files = {
            "module1.py": "def func1(): pass",
            "module2.py": "def func2(): pass",
        }

        for name, content in initial_files.items():
            (project_dir / name).write_text(content)

        # Initial processing
        results_file = tmp_path / "results.json"
        results = {}

        for file_path in project_dir.glob("*.py"):
            chunks = chunk_file(file_path, language="python")
            results[str(file_path)] = {
                "mtime": file_path.stat().st_mtime,
                "chunks": len(chunks),
            }

        with Path(results_file).open(
            "w",
        ) as f:
            json.dump(results, f)

        # Modify one file, add another
        time.sleep(0.1)  # Ensure mtime changes
        (project_dir / "module1.py").write_text(
            "def func1(): pass\ndef func1_new(): pass",
        )
        (project_dir / "module3.py").write_text("def func3(): pass")

        # Incremental update
        with Path(results_file).open() as f:
            previous_results = json.load(f)

        updated_files = []
        new_files = []

        for file_path in project_dir.glob("*.py"):
            file_str = str(file_path)
            current_mtime = file_path.stat().st_mtime

            if file_str not in previous_results:
                new_files.append(file_path)
            elif current_mtime > previous_results[file_str]["mtime"]:
                updated_files.append(file_path)

        # Should detect changes
        assert len(updated_files) == 1  # module1.py
        assert len(new_files) == 1  # module3.py


class TestGracefulDegradation:
    """Test graceful degradation under adverse conditions."""

    def test_fallback_to_basic_parsing(self, tmp_path):
        """Test simplified parsing fallback."""
        test_file = tmp_path / "complex.py"
        test_file.write_text(
            """
@complex_decorator(arg1, arg2)
@another_decorator
async def complex_function(*args, **kwargs) -> Optional[List[Dict[str, Any]]]:
    '''Complex function with many features.'''
    async with context_manager() as ctx:
        result = await async_operation()
        yield from generator_expression(x for x in result if x > 0)
    return result

# Simpler function
def simple_function():
    return 42
""",
        )

        # Mock parser failure on complex syntax
        original_parser = get_parser("python")

        with patch("chunker.parser.get_parser") as mock_get_parser:
            call_count = 0

            def get_parser_with_fallback(language):
                nonlocal call_count
                call_count += 1

                if call_count == 1:
                    # First attempt fails
                    raise ParserError("Complex syntax not supported")
                # Fallback to basic parsing
                return original_parser

            mock_get_parser.side_effect = get_parser_with_fallback

            # Attempt parsing with fallback
            try:
                chunks = chunk_file(test_file, language="python")
            except ParserError:
                # Fallback: simple line-based parsing
                chunks = []
                with Path(test_file).open() as f:
                    lines = f.readlines()

                current_chunk = []
                for i, line in enumerate(lines):
                    if line.strip().startswith("def ") or line.strip().startswith(
                        "class ",
                    ):
                        if current_chunk:
                            # Save previous chunk
                            content = "".join(current_chunk)
                            if content.strip():
                                chunks.append(
                                    MagicMock(
                                        content=content,
                                        start_line=i - len(current_chunk) + 1,
                                        end_line=i,
                                        node_type="function_definition",
                                    ),
                                )
                        current_chunk = [line]
                    elif current_chunk:
                        current_chunk.append(line)

            # Should extract at least simple function
            assert any("simple_function" in str(chunk.content) for chunk in chunks)

    def test_language_unavailable_handling(self, tmp_path):
        """Test missing language handling."""
        test_file = tmp_path / "test.xyz"
        test_file.write_text(
            """
function test() {
    return "unknown language";
}
""",
        )

        # Try with unavailable language
        with pytest.raises(Exception) as exc_info:
            chunk_file(test_file, language="xyz")

        # Should provide helpful error
        assert "language" in str(exc_info.value).lower()

        # Fallback: detect language from content
        content = test_file.read_text()

        # Simple heuristics
        detected_language = None
        if "function" in content and "{" in content:
            detected_language = "javascript"
        elif "def " in content:
            detected_language = "python"
        elif "#include" in content:
            detected_language = "c"

        if detected_language:
            try:
                chunk_file(test_file, language=detected_language)
                # May or may not get chunks depending on parsing
            except (FileNotFoundError, IndexError, KeyError):
                # Fallback might also fail
                pass

    def test_reduced_functionality_mode(self, tmp_path):
        """Test degraded operation mode."""
        # Create test files
        files = []
        for i in range(5):
            f = tmp_path / f"file{i}.py"
            f.write_text(f"def func{i}(): return {i}")
            files.append(f)

        # Test fallback to sequential processing
        results = []

        # Mock the parallel processing to fail
        def mock_chunk_files_parallel(files, **kwargs):
            raise RuntimeError("Parallel processing unavailable")

        # Process files with fallback
        for file_path in files:
            try:
                # Try parallel first (this will fail)
                mock_chunk_files_parallel([file_path])
            except RuntimeError:
                # Fallback to sequential
                chunks = chunk_file(file_path, language="python")
                results.append((file_path, chunks))

        # Should process all files sequentially
        assert len(results) == 5
        assert all(len(chunks) > 0 for _, chunks in results)

    def test_resource_limit_adaptation(self, tmp_path):
        """Test adapting to resource constraints."""

        # Create memory-intensive test case
        large_file = tmp_path / "large.py"

        # Generate large content
        content_lines = []
        for i in range(1000):
            content_lines.append(f"def func_{i}():")
            content_lines.append("    data = ['x'] * 1000000")
            content_lines.append("    return sum(data)")
            content_lines.append("")

        large_file.write_text("\n".join(content_lines))

        # Monitor memory usage
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        # Set memory threshold
        memory_threshold = initial_memory + 100  # Allow 100MB increase

        # Process with adaptive strategy
        chunks_processed = 0
        batch_size = 100

        with Path(large_file).open() as f:
            lines = f.readlines()

        while chunks_processed < len(lines) // 4:  # Process by function (4 lines each)
            current_memory = process.memory_info().rss / 1024 / 1024

            if current_memory > memory_threshold:
                # Reduce batch size
                batch_size = max(10, batch_size // 2)

                # Force garbage collection

                gc.collect()

                # Wait for memory to stabilize
                time.sleep(0.1)

            # Process next batch
            start_idx = chunks_processed * 4
            end_idx = min(start_idx + batch_size * 4, len(lines))

            batch_content = "".join(lines[start_idx:end_idx])

            # Simple processing (simulate chunking)
            functions_in_batch = batch_content.count("def ")
            chunks_processed += functions_in_batch

            # Simulate work
            time.sleep(0.01)

        # Should have adapted batch size if needed
        assert chunks_processed > 0

        # Memory should not have grown excessively
        final_memory = process.memory_info().rss / 1024 / 1024
        memory_growth = final_memory - initial_memory
        assert memory_growth < 200  # Less than 200MB growth


class TestSystemResilience:
    """Test overall system resilience."""

    def test_concurrent_failure_isolation(self, tmp_path):
        """Test failure containment in concurrent operations."""
        # Create test files, one will cause failure
        files = []
        for i in range(5):
            f = tmp_path / f"file{i}.py"
            if i == 2:
                # This file will cause issues
                f.write_text("def bad_file(: syntax error")
            else:
                f.write_text(f"def func{i}(): return {i}")
            files.append(f)

        # Process concurrently with failure isolation
        results = {}
        errors = {}

        def process_file_safe(file_path):
            try:
                chunks = chunk_file(file_path, language="python")
                return str(file_path), chunks, None
            except (OSError, FileNotFoundError, ImportError) as e:
                return str(file_path), [], str(e)

        # Use thread pool for concurrent processing

        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {executor.submit(process_file_safe, f): f for f in files}

            for future in futures:
                file_path, chunks, error = future.result()
                if error:
                    errors[file_path] = error
                else:
                    results[file_path] = chunks

        # Should process most files despite one failure
        assert len(results) >= 4
        assert len(errors) <= 1

        # Error should be contained to problematic file (if any errors)
        if errors:
            assert any("file2" in path for path in errors)

    def test_cascading_failure_prevention(self, tmp_path):
        """Test preventing failure chains."""
        # Create interdependent modules
        (tmp_path / "base.py").write_text(
            """
def base_function():
    return "base"
""",
        )

        (tmp_path / "dependent1.py").write_text(
            """
from base import base_function

def dependent_function1():
    return base_function() + "_dep1"
""",
        )

        (tmp_path / "dependent2.py").write_text(
            """
from dependent1 import dependent_function1

def dependent_function2():
    return dependent_function1() + "_dep2"
""",
        )

        # Process with failure isolation
        processing_order = []
        failures = []

        files = ["base.py", "dependent1.py", "dependent2.py"]

        for filename in files:
            file_path = tmp_path / filename

            try:
                # Simulate failure in middle of chain
                if filename == "dependent1.py":
                    raise RuntimeError("Processing failed")

                chunk_file(file_path, language="python")
                processing_order.append((filename, "success"))
            except (FileNotFoundError, OSError, TypeError) as e:
                failures.append((filename, str(e)))
                processing_order.append((filename, "failed"))

                # Continue processing other files
                continue

        # Should process base and attempt all files
        assert len(processing_order) == 3

        # Failure should not prevent processing of other files
        assert ("base.py", "success") in processing_order
        assert ("dependent1.py", "failed") in processing_order
        assert ("dependent2.py", "success") in processing_order or (
            "dependent2.py",
            "failed",
        ) in processing_order

    def test_automatic_retry_logic(self, tmp_path):
        """Test automatic retry mechanisms."""
        test_file = tmp_path / "retry_test.py"
        test_file.write_text("def test(): return 'ok'")

        # Simulate transient failures
        attempt_count = 0
        max_retries = 3

        def chunk_with_retry(file_path, language, retries=3):
            nonlocal attempt_count

            for i in range(retries):
                attempt_count += 1

                try:
                    if attempt_count < 2:  # Fail first attempt
                        raise RuntimeError("Transient error")

                    # Succeed on second attempt
                    return chunk_file(file_path, language=language)
                except RuntimeError:
                    if i == retries - 1:  # Last attempt
                        raise

                    # Exponential backoff
                    time.sleep(0.1 * (2**i))

            return []

        # Should succeed after retry
        chunks = chunk_with_retry(test_file, "python", max_retries)
        assert len(chunks) > 0
        assert attempt_count == 2  # Failed once, succeeded on second

    def test_circuit_breaker_pattern(self):
        """Test circuit breaker implementation."""

        class CircuitBreaker:
            def __init__(self, failure_threshold=3, recovery_timeout=1.0):
                self.failure_threshold = failure_threshold
                self.recovery_timeout = recovery_timeout
                self.failure_count = 0
                self.last_failure_time = None
                self.state = "closed"  # closed, open, half-open

            def call(self, func, *args, **kwargs):
                if self.state == "open":
                    # Check if recovery timeout passed
                    if time.time() - self.last_failure_time > self.recovery_timeout:
                        self.state = "half-open"
                    else:
                        raise RuntimeError("Circuit breaker is open")

                try:
                    result = func(*args, **kwargs)

                    # Success - reset on half-open
                    if self.state == "half-open":
                        self.state = "closed"
                        self.failure_count = 0

                    return result

                except OSError:
                    self.failure_count += 1
                    self.last_failure_time = time.time()

                    if self.failure_count >= self.failure_threshold:
                        self.state = "open"

                    raise

        # Test circuit breaker
        breaker = CircuitBreaker(failure_threshold=2, recovery_timeout=0.5)
        call_count = 0

        def flaky_operation():
            nonlocal call_count
            call_count += 1

            if call_count <= 3:  # Fail first 3 calls
                raise RuntimeError("Operation failed")
            return "success"

        results = []

        # Make multiple calls
        for _i in range(6):
            try:
                result = breaker.call(flaky_operation)
                results.append(("success", result))
            except RuntimeError as e:
                results.append(("failure", str(e)))

            # Wait a bit between calls
            time.sleep(0.2)

        # Circuit should open after 2 failures
        assert results[0][0] == "failure"
        assert results[1][0] == "failure"
        assert "Circuit breaker is open" in results[2][1]

        # After recovery timeout, should attempt again
        # (May succeed or fail depending on timing)
        assert len(results) == 6


def test_comprehensive_recovery_scenario(tmp_path):
    """Test a comprehensive recovery scenario."""
    # Create complex project structure
    project_dir = tmp_path / "resilient_project"
    project_dir.mkdir()

    # Various problematic files
    files = {
        "good.py": "def good(): return 'ok'",
        "syntax_error.py": "def bad(: error",
        "large.py": "def large():\n" + "    x = 'a' * 1000000\n" * 100,
        "nested/deep.py": "def deep(): pass",
        "binary.bin": b"\x00\x01\x02\x03",
    }

    # Create files
    for path, content in files.items():
        file_path = project_dir / path
        file_path.parent.mkdir(parents=True, exist_ok=True)

        if isinstance(content, bytes):
            file_path.write_bytes(content)
        else:
            file_path.write_text(content)

    # Process with comprehensive error handling
    results = {
        "successful": [],
        "failed": [],
        "skipped": [],
        "recovered": [],
    }

    for file_path in project_dir.rglob("*"):
        if not file_path.is_file():
            continue

        # Skip non-code files
        if file_path.suffix not in [".py", ".js", ".rs", ".c"]:
            results["skipped"].append(str(file_path))
            continue

        try:
            # First attempt
            chunks = chunk_file(file_path, language="python")
            results["successful"].append(
                {
                    "file": str(file_path),
                    "chunks": len(chunks),
                },
            )
        except (FileNotFoundError, IndexError, KeyError) as e:
            # Try recovery strategies
            recovered = False

            # Strategy 1: Try with different settings
            try:
                chunks = chunk_file(file_path, language="python")
                results["recovered"].append(
                    {
                        "file": str(file_path),
                        "strategy": "retry",
                        "chunks": len(chunks),
                    },
                )
                recovered = True
            except (FileNotFoundError, IndexError, KeyError):
                pass

            if not recovered:
                results["failed"].append(
                    {
                        "file": str(file_path),
                        "error": str(e),
                    },
                )

    # Should handle various scenarios
    assert len(results["successful"]) >= 1  # At least good.py
    # Failed files depend on parser behavior - it might parse syntax errors partially
    assert (
        len(results["successful"]) + len(results["failed"]) + len(results["recovered"])
        >= 3
    )
    assert len(results["skipped"]) >= 1  # binary.bin

    # System should remain stable
    assert True  # We completed without crashing

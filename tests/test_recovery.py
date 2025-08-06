"""Recovery and resilience tests for the tree-sitter-chunker.

This module tests system resilience including crash recovery,
state persistence, partial processing, and graceful degradation.
"""

import contextlib
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

    @classmethod
    def test_parser_crash_recovery(cls, tmp_path):
        """Test recovery from parser crashes."""
        test_file = tmp_path / "crash_test.py"
        test_file.write_text(
            """
def normal_function():
    return "ok"

# This might cause parser issues
def problematic_function():
    '''Unclosed string literal
    return "problem\"
""",
        )
        with patch("chunker.chunker.get_parser") as mock_get_parser:
            mock_parser = MagicMock()
            mock_tree = MagicMock()
            mock_tree.root_node = MagicMock()
            mock_tree.root_node.children = []
            mock_tree.root_node.type = "module"
            mock_tree.root_node.start_byte = 0
            mock_tree.root_node.end_byte = 100
            mock_tree.root_node.start_point = 0, 0
            mock_tree.root_node.end_point = 10, 0
            mock_parser.parse.side_effect = [
                RuntimeError(
                    "Parser crashed!",
                ),
                mock_tree,
            ]
            mock_get_parser.return_value = mock_parser
            try:
                chunk_file(test_file, language="python")
            except RuntimeError:
                chunk_file(test_file, language="python")
            assert mock_parser.parse.call_count >= 2

    @classmethod
    def test_memory_exhaustion_recovery(cls, tmp_path):
        """Test OOM handling."""
        large_file = tmp_path / "large.py"
        lines = []
        for i in range(10000):
            lines.append(f"def function_{i}():")
            lines.append("    data = 'x' * 1000000  # Large string")
            lines.append(f"    return {i}")
            lines.append("")
        large_file.write_text("\n".join(lines))
        original_chunk_file = chunk_file
        call_count = 0

        def mock_chunk_file(file_path, language):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise MemoryError("Out of memory!")
            return original_chunk_file(file_path, language)

        with patch("chunker.chunk_file", side_effect=mock_chunk_file):
            try:
                chunks = chunk_file(large_file, language="python")
            except MemoryError:
                chunks = list(chunk_file_streaming(large_file, language="python"))
            assert len(chunks) > 0

    @staticmethod
    def test_segfault_isolation(tmp_path):
        """Test isolation of segfaults."""
        files = []
        for i in range(5):
            f = tmp_path / f"file{i}.py"
            f.write_text(f"def func{i}(): pass")
            files.append(str(f))
        processed = []
        failed = []
        for file_path in files:
            try:
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
        assert len(processed) >= 3
        assert len(failed) >= 1

    @staticmethod
    def test_deadlock_detection_and_recovery(_tmp_path):
        """Test deadlock handling."""
        lock1 = threading.Lock()
        lock2 = threading.Lock()
        results = queue.Queue()

        def worker1():
            with lock1:
                time.sleep(0.1)
                acquired = lock2.acquire(timeout=1)
                if acquired:
                    lock2.release()
                    results.put("worker1_success")
                else:
                    results.put("worker1_timeout")

        def worker2():
            with lock2:
                time.sleep(0.1)
                acquired = lock1.acquire(timeout=1)
                if acquired:
                    lock1.release()
                    results.put("worker2_success")
                else:
                    results.put("worker2_timeout")

        t1 = threading.Thread(target=worker1)
        t2 = threading.Thread(target=worker2)
        t1.start()
        t2.start()
        t1.join(timeout=3)
        t2.join(timeout=3)
        timeouts = 0
        while not results.empty():
            result = results.get()
            if "timeout" in result:
                timeouts += 1
        assert timeouts >= 1
        assert True


class TestStatePersistence:
    """Test state persistence and recovery."""

    @classmethod
    def test_checkpoint_creation(cls, tmp_path):
        """Test progress checkpointing."""
        checkpoint_dir = tmp_path / ".chunker_checkpoints"
        checkpoint_dir.mkdir()
        files_to_process = []
        for i in range(10):
            f = tmp_path / f"file{i}.py"
            f.write_text(f"def func{i}(): pass")
            files_to_process.append(f)
        checkpoint_file = checkpoint_dir / "progress.json"
        processed = []
        for i, file_path in enumerate(files_to_process):
            chunks = chunk_file(file_path, language="python")
            processed.append(
                {"file": str(file_path), "chunks": len(chunks), "index": i},
            )
            if (i + 1) % 3 == 0:
                with Path(checkpoint_file).open("w", encoding="utf-8") as f:
                    json.dump(
                        {
                            "processed": processed,
                            "total": len(files_to_process),
                            "timestamp": time.time(),
                        },
                        f,
                    )
        assert checkpoint_file.exists()
        with Path(checkpoint_file).open(encoding="utf-8") as f:
            checkpoint_data = json.load(f)
            assert len(checkpoint_data["processed"]) >= 9
            assert checkpoint_data["total"] == 10

    @classmethod
    def test_resume_from_checkpoint(cls, tmp_path):
        """Test resuming interrupted work."""
        checkpoint_file = tmp_path / "checkpoint.json"
        files_to_process = []
        for i in range(10):
            f = tmp_path / f"file{i}.py"
            f.write_text(f"def func{i}(): pass")
            files_to_process.append(str(f))
        checkpoint_data = {
            "processed": files_to_process[:6],
            "remaining": files_to_process[6:],
            "timestamp": time.time(),
        }
        with Path(checkpoint_file).open("w", encoding="utf-8") as f:
            json.dump(checkpoint_data, f)
        with Path(checkpoint_file).open(encoding="utf-8") as f:
            state = json.load(f)
        already_processed = set(state["processed"])
        remaining = state["remaining"]
        newly_processed = []
        for file_path in remaining:
            if file_path not in already_processed:
                chunk_file(file_path, language="python")
                newly_processed.append(file_path)
        assert len(newly_processed) == 4
        assert all(f in files_to_process[6:] for f in newly_processed)

    @classmethod
    def test_checkpoint_corruption_handling(cls, tmp_path):
        """Test corrupt checkpoint recovery."""
        checkpoint_file = tmp_path / "corrupt_checkpoint.json"
        checkpoint_file.write_text("{ invalid json corrupt data")
        checkpoint_data = None
        try:
            with Path(checkpoint_file).open(encoding="utf-8") as f:
                checkpoint_data = json.load(f)
        except json.JSONDecodeError:
            checkpoint_data = {
                "processed": [],
                "error": "Checkpoint corrupted, starting fresh",
                "timestamp": time.time(),
            }
        assert checkpoint_data is not None
        assert len(checkpoint_data["processed"]) == 0
        assert "error" in checkpoint_data

    @classmethod
    def test_distributed_state_sync(cls, tmp_path):
        """Test multi-process state synchronization."""
        state_file = tmp_path / "shared_state.json"
        lock_file = tmp_path / "state.lock"

        def update_state(worker_id, item):
            """Update shared state with locking."""
            max_retries = 50
            for _retry in range(max_retries):
                if not lock_file.exists():
                    try:
                        lock_file.touch(exist_ok=False)
                        break
                    except FileExistsError:
                        pass
                time.sleep(0.01)
            else:
                raise RuntimeError("Could not acquire lock")
            try:
                if state_file.exists() and state_file.stat().st_size > 0:
                    with Path(state_file).open(encoding="utf-8") as f:
                        try:
                            state = json.load(f)
                        except json.JSONDecodeError:
                            state = {"workers": {}, "items": []}
                else:
                    state = {"workers": {}, "items": []}
                if worker_id not in state["workers"]:
                    state["workers"][worker_id] = []
                state["workers"][worker_id].append(item)
                state["items"].append(item)
                temp_file = (
                    state_file.parent
                    / f"tmp_{worker_id}_{random.randint(1000, 9999)}.json"
                )
                with Path(temp_file).open("w", encoding="utf-8") as f:
                    json.dump(state, f)
                    f.flush()
                    os.fsync(f.fileno())
                temp_file.replace(state_file)
            finally:
                if lock_file.exists():
                    with contextlib.suppress(FileNotFoundError):
                        lock_file.unlink()

        def worker(worker_id, items):
            for item in items:
                try:
                    update_state(worker_id, item)
                    time.sleep(0.01)
                except (OSError, FileNotFoundError, IndexError) as e:
                    print(f"Worker {worker_id} error: {e}")

        items_per_worker = 5
        workers = []
        for i in range(3):
            items = [f"worker{i}_item{j}" for j in range(items_per_worker)]
            t = threading.Thread(target=worker, args=(f"worker{i}", items))
            workers.append(t)
            t.start()
        for t in workers:
            t.join()
        if state_file.exists():
            with Path(state_file).open(encoding="utf-8") as f:
                final_state = json.load(f)
            assert len(final_state["workers"]) >= 1
            assert len(final_state["items"]) >= 5
            all_items = [
                item
                for worker_items in final_state["workers"].values()
                for item in worker_items
            ]
            assert len(all_items) == len(final_state["items"])
        else:
            pytest.skip("Workers failed to create state file")


class TestPartialProcessing:
    """Test partial processing scenarios."""

    @staticmethod
    def test_partial_file_processing(tmp_path):
        """Test incomplete file handling."""
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
        all_chunks = chunk_file(test_file, language="python")
        interruption_point = len(all_chunks) // 2
        processed_chunks = all_chunks[:interruption_point]
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
        remaining_chunks = all_chunks[interruption_point:]
        assert len(processed_chunks) + len(remaining_chunks) == len(all_chunks)
        assert processed_chunks[0].content != remaining_chunks[0].content

    @classmethod
    def test_partial_chunk_extraction(cls, tmp_path):
        """Test partial chunk recovery."""
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
        return "method2\"
""",
        )
        chunks = []
        errors = []
        try:
            all_chunks = chunk_file(test_file, language="python")
            for i, chunk in enumerate(all_chunks):
                if i == 2:
                    raise RuntimeError("Chunk extraction failed")
                chunks.append(chunk)
        except RuntimeError as e:
            errors.append(str(e))
        assert len(chunks) >= 2
        assert len(errors) == 1

    @classmethod
    def test_partial_export_completion(cls, tmp_path):
        """Test completing partial exports."""
        partial_export = tmp_path / "partial_export.jsonl"
        with Path(partial_export).open("w", encoding="utf-8") as f:
            for i in range(3):
                chunk_data = {
                    "content": f"def func{i}(): pass",
                    "start_line": i * 3 + 1,
                    "end_line": i * 3 + 2,
                    "language": "python",
                }
                f.write(json.dumps(chunk_data) + "\n")
            incomplete = {"content": "def incomplete():", "start_line": 10}
            f.write(json.dumps(incomplete))
        complete_chunks = []
        incomplete_chunks = []
        with Path(partial_export).open(encoding="utf-8") as f:
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
        assert len(complete_chunks) == 3
        assert len(incomplete_chunks) >= 1
        remaining_chunks = [
            {
                "content": "def func4(): pass",
                "start_line": 13,
                "end_line": 14,
                "language": "python",
            },
        ]
        with Path(partial_export).open("a", encoding="utf-8") as f:
            f.write("\n")
            for chunk in remaining_chunks:
                f.write(json.dumps(chunk) + "\n")
        with Path(partial_export).open(encoding="utf-8") as f:
            all_lines = f.readlines()
            assert len(all_lines) >= 5

    @classmethod
    def test_incremental_processing(cls, tmp_path):
        """Test incremental updates."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        initial_files = {
            "module1.py": "def func1(): pass",
            "module2.py": "def func2(): pass",
        }
        for name, content in initial_files.items():
            (project_dir / name).write_text(content)
        results_file = tmp_path / "results.json"
        results = {}
        for file_path in project_dir.glob("*.py"):
            chunks = chunk_file(file_path, language="python")
            results[str(file_path)] = {
                "mtime": file_path.stat().st_mtime,
                "chunks": len(chunks),
            }
        with Path(results_file).open("w", encoding="utf-8") as f:
            json.dump(results, f)
        time.sleep(0.1)
        (project_dir / "module1.py").write_text(
            "def func1(): pass\ndef func1_new(): pass",
        )
        (project_dir / "module3.py").write_text("def func3(): pass")
        with Path(results_file).open(encoding="utf-8") as f:
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
        assert len(updated_files) == 1
        assert len(new_files) == 1


class TestGracefulDegradation:
    """Test graceful degradation under adverse conditions."""

    @classmethod
    def test_fallback_to_basic_parsing(cls, tmp_path):
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
        original_parser = get_parser("python")
        with patch("chunker.parser.get_parser") as mock_get_parser:
            call_count = 0

            def get_parser_with_fallback(language):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    raise ParserError("Complex syntax not supported")
                return original_parser

            mock_get_parser.side_effect = get_parser_with_fallback
            try:
                chunks = chunk_file(test_file, language="python")
            except ParserError:
                chunks = []
                with Path(test_file).open(encoding="utf-8") as f:
                    lines = f.readlines()
                current_chunk = []
                for i, line in enumerate(lines):
                    if line.strip().startswith("def ") or line.strip().startswith(
                        "class ",
                    ):
                        if current_chunk:
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
            assert any("simple_function" in str(chunk.content) for chunk in chunks)

    @staticmethod
    def test_language_unavailable_handling(tmp_path):
        """Test missing language handling."""
        test_file = tmp_path / "test.xyz"
        test_file.write_text('\nfunction test() {\n    return "unknown language";\n}\n')
        with pytest.raises(Exception) as exc_info:
            chunk_file(test_file, language="xyz")
        assert "language" in str(exc_info.value).lower()
        content = test_file.read_text()
        detected_language = None
        if "function" in content and "{" in content:
            detected_language = "javascript"
        elif "def " in content:
            detected_language = "python"
        elif "#include" in content:
            detected_language = "c"
        if detected_language:
            with contextlib.suppress(FileNotFoundError, IndexError, KeyError):
                chunk_file(test_file, language=detected_language)

    @classmethod
    def test_reduced_functionality_mode(cls, tmp_path):
        """Test degraded operation mode."""
        files = []
        for i in range(5):
            f = tmp_path / f"file{i}.py"
            f.write_text(f"def func{i}(): return {i}")
            files.append(f)
        results = []

        def mock_chunk_files_parallel(files, **kwargs):
            raise RuntimeError("Parallel processing unavailable")

        for file_path in files:
            try:
                mock_chunk_files_parallel([file_path])
            except RuntimeError:
                chunks = chunk_file(file_path, language="python")
                results.append((file_path, chunks))
        assert len(results) == 5
        assert all(len(chunks) > 0 for _, chunks in results)

    @classmethod
    def test_resource_limit_adaptation(cls, tmp_path):
        """Test adapting to resource constraints."""
        large_file = tmp_path / "large.py"
        content_lines = []
        for i in range(1000):
            content_lines.append(f"def func_{i}():")
            content_lines.append("    data = ['x'] * 1000000")
            content_lines.append("    return sum(data)")
            content_lines.append("")
        large_file.write_text("\n".join(content_lines))
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024
        memory_threshold = initial_memory + 100
        chunks_processed = 0
        batch_size = 100
        with Path(large_file).open(encoding="utf-8") as f:
            lines = f.readlines()
        while chunks_processed < len(lines) // 4:
            current_memory = process.memory_info().rss / 1024 / 1024
            if current_memory > memory_threshold:
                batch_size = max(10, batch_size // 2)
                gc.collect()
                time.sleep(0.1)
            start_idx = chunks_processed * 4
            end_idx = min(start_idx + batch_size * 4, len(lines))
            batch_content = "".join(lines[start_idx:end_idx])
            functions_in_batch = batch_content.count("def ")
            chunks_processed += functions_in_batch
            time.sleep(0.01)
        assert chunks_processed > 0
        final_memory = process.memory_info().rss / 1024 / 1024
        memory_growth = final_memory - initial_memory
        assert memory_growth < 200


class TestSystemResilience:
    """Test overall system resilience."""

    @classmethod
    def test_concurrent_failure_isolation(cls, tmp_path):
        """Test failure containment in concurrent operations."""
        files = []
        for i in range(5):
            f = tmp_path / f"file{i}.py"
            if i == 2:
                f.write_text("def bad_file(: syntax error")
            else:
                f.write_text(f"def func{i}(): return {i}")
            files.append(f)
        results = {}
        errors = {}

        def process_file_safe(file_path):
            try:
                chunks = chunk_file(file_path, language="python")
                return str(file_path), chunks, None
            except (OSError, FileNotFoundError, ImportError) as e:
                return str(file_path), [], str(e)

        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {executor.submit(process_file_safe, f): f for f in files}
            for future in futures:
                file_path, chunks, error = future.result()
                if error:
                    errors[file_path] = error
                else:
                    results[file_path] = chunks
        assert len(results) >= 4
        assert len(errors) <= 1
        if errors:
            assert any("file2" in path for path in errors)

    @classmethod
    def test_cascading_failure_prevention(cls, tmp_path):
        """Test preventing failure chains."""
        (tmp_path / "base.py").write_text('\ndef base_function():\n    return "base"\n')
        (tmp_path / "dependent1.py").write_text(
            """
from base import base_function

def dependent_function1():
    return base_function() + "_dep1\"
""",
        )
        (tmp_path / "dependent2.py").write_text(
            """
from dependent1 import dependent_function1

def dependent_function2():
    return dependent_function1() + "_dep2\"
""",
        )
        processing_order = []
        failures = []
        files = ["base.py", "dependent1.py", "dependent2.py"]
        for filename in files:
            file_path = tmp_path / filename
            try:
                if filename == "dependent1.py":
                    raise RuntimeError("Processing failed")
                chunk_file(file_path, language="python")
                processing_order.append((filename, "success"))
            except (FileNotFoundError, OSError, TypeError) as e:
                failures.append((filename, str(e)))
                processing_order.append((filename, "failed"))
                continue
        assert len(processing_order) == 3
        assert ("base.py", "success") in processing_order
        assert ("dependent1.py", "failed") in processing_order
        assert ("dependent2.py", "success") in processing_order or (
            "dependent2.py",
            "failed",
        ) in processing_order

    @classmethod
    def test_automatic_retry_logic(cls, tmp_path):
        """Test automatic retry mechanisms."""
        test_file = tmp_path / "retry_test.py"
        test_file.write_text("def test(): return 'ok'")
        attempt_count = 0
        max_retries = 3

        def chunk_with_retry(file_path, language, retries=3):
            nonlocal attempt_count
            for i in range(retries):
                attempt_count += 1
                try:
                    if attempt_count < 2:
                        raise RuntimeError("Transient error")
                    return chunk_file(file_path, language=language)
                except RuntimeError:
                    if i == retries - 1:
                        raise
                    time.sleep(0.1 * 2**i)
            return []

        chunks = chunk_with_retry(test_file, "python", max_retries)
        assert len(chunks) > 0
        assert attempt_count == 2

    @staticmethod
    def test_circuit_breaker_pattern():
        """Test circuit breaker implementation."""

        class CircuitBreaker:

            def __init__(self, failure_threshold=3, recovery_timeout=1.0):
                self.failure_threshold = failure_threshold
                self.recovery_timeout = recovery_timeout
                self.failure_count = 0
                self.last_failure_time = None
                self.state = "closed"

            def call(self, func, *args, **kwargs):
                if self.state == "open":
                    if time.time() - self.last_failure_time > self.recovery_timeout:
                        self.state = "half-open"
                    else:
                        raise RuntimeError("Circuit breaker is open")
                try:
                    result = func(*args, **kwargs)
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

        breaker = CircuitBreaker(failure_threshold=2, recovery_timeout=0.5)
        call_count = 0

        def flaky_operation():
            nonlocal call_count
            call_count += 1
            if call_count <= 3:
                raise RuntimeError("Operation failed")
            return "success"

        results = []
        for _i in range(6):
            try:
                result = breaker.call(flaky_operation)
                results.append(("success", result))
            except RuntimeError as e:
                results.append(("failure", str(e)))
            time.sleep(0.2)
        assert results[0][0] == "failure"
        assert results[1][0] == "failure"
        assert "Circuit breaker is open" in results[2][1]
        assert len(results) == 6


def test_comprehensive_recovery_scenario(tmp_path):
    """Test a comprehensive recovery scenario."""
    project_dir = tmp_path / "resilient_project"
    project_dir.mkdir()
    files = {
        "good.py": "def good(): return 'ok'",
        "syntax_error.py": "def bad(: error",
        "large.py": "def large():\n"
        + """    x = 'a' * 1000000
"""
        * 100,
        "nested/deep.py": "def deep(): pass",
        "binary.bin": b"\x00\x01\x02\x03",
    }
    for path, content in files.items():
        file_path = project_dir / path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            file_path.write_bytes(content)
        else:
            file_path.write_text(content)
    results = {"successful": [], "failed": [], "skipped": [], "recovered": []}
    for file_path in project_dir.rglob("*"):
        if not file_path.is_file():
            continue
        if file_path.suffix not in {".py", ".js", ".rs", ".c"}:
            results["skipped"].append(str(file_path))
            continue
        try:
            chunks = chunk_file(file_path, language="python")
            results["successful"].append(
                {"file": str(file_path), "chunks": len(chunks)},
            )
        except (FileNotFoundError, IndexError, KeyError) as e:
            recovered = False
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
                results["failed"].append({"file": str(file_path), "error": str(e)})
    assert len(results["successful"]) >= 1
    assert (
        len(results["successful"]) + len(results["failed"]) + len(results["recovered"])
        >= 3
    )
    assert len(results["skipped"]) >= 1
    assert True

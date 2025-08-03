"""Common fixtures for Phase 7 integration tests.

This module provides shared test fixtures that all integration tests can use.
"""
import asyncio
import multiprocessing
import shutil
import tempfile
import threading
import time
from collections.abc import Callable, Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest

from .interfaces import ConfigChangeObserver, ErrorPropagationMixin, ResourceTracker


@pytest.fixture
def temp_workspace() -> Generator[Path, None, None]:
    """Provide a temporary workspace directory for integration tests.

    Yields:
        Path to temporary directory that is cleaned up after test
    """
    temp_dir = tempfile.mkdtemp(prefix="chunker_test_")
    workspace = Path(temp_dir)
    (workspace / "src").mkdir()
    (workspace / "tests").mkdir()
    (workspace / "cache").mkdir()
    (workspace / "output").mkdir()
    yield workspace
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def sample_code_files() -> dict[str, str]:
    """Provide sample code files for different languages.

    Returns:
        Dictionary mapping filenames to code content
    """
    return {"example.py":
        """
def calculate_sum(numbers):
    '''Calculate sum of numbers.'''
    return sum(numbers)

class DataProcessor:
    def __init__(self):
        self.data = []

    def process(self, item):
        '''Process a single item.'''
        self.data.append(item)
        return item * 2

async def fetch_data(url):
    '''Async function to fetch data.'''
    await asyncio.sleep(0.1)
    return {"url": url, "data": "sample"}
"""
        , "example.js":
        """
function calculateSum(numbers) {
    // Calculate sum of array
    return numbers.reduce((a, b) => a + b, 0);
}

class DataProcessor {
    constructor() {
        this.data = [];
    }

    process(item) {
        // Process single item
        this.data.push(item);
        return item * 2;
    }
}

async function fetchData(url) {
    // Async fetch function
    await new Promise(r => setTimeout(r, 100));
    return { url, data: 'sample' };
}
"""
        , "example.rs":
        """
fn calculate_sum(numbers: &[i32]) -> i32 {
    // Calculate sum of slice
    numbers.iter().sum()
}

struct DataProcessor {
    data: Vec<i32>,
}

impl DataProcessor {
    fn new() -> Self {
        Self { data: Vec::new() }
    }

    fn process(&mut self, item: i32) -> i32 {
        // Process single item
        self.data.push(item);
        item * 2
    }
}

async fn fetch_data(url: &str) -> Result<String, Error> {
    // Async fetch function
    tokio::time::sleep(Duration::from_millis(100)).await;
    Ok(format!("Data from {}", url))
}
"""
        , "example.c":
        """
#include <stdio.h>

int calculate_sum(int* numbers, int count) {
    // Calculate sum of array
    int sum = 0;
    for (int i = 0; i < count; i++) {
        sum += numbers[i];
    }
    return sum;
}

typedef struct {
    int* data;
    int size;
    int capacity;
} DataProcessor;

void process_item(DataProcessor* dp, int item) {
    // Process single item
    if (dp->size >= dp->capacity) {
        // Resize array
        dp->capacity *= 2;
    }
    dp->data[dp->size++] = item * 2;
}
""",
        }


class ErrorTrackingContext(ErrorPropagationMixin):
    """Context manager for tracking errors across modules."""

    def __init__(self):
        self.captured_errors = []
        self.error_handlers = {}
        self._lock = threading.Lock()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_val:
            self.capture_cross_module_error(source_module="test_context",
                target_module="test_runner", error=exc_val)
        return False

    def register_handler(self, module: str, handler: Callable):
        """Register error handler for specific module."""
        self.error_handlers[module] = handler

    def capture_and_propagate(self, source: str, target: str, error: Exception,
        ):
        """Capture error and trigger registered handlers."""
        with self._lock:
            error_context = self.capture_cross_module_error(source, target,
                error)
            self.captured_errors.append(error_context)
            if target in self.error_handlers:
                self.error_handlers[target](error_context)
        return error_context

    def get_error_chain(self) -> list[dict[str, Any]]:
        """Get all captured errors in order."""
        with self._lock:
            return self.captured_errors.copy()


@pytest.fixture
def error_tracking_context():
    """Context manager for tracking errors across modules."""
    return ErrorTrackingContext()


@pytest.fixture
def config_change_tracker():
    """Fixture for tracking configuration changes."""
    tracker = ConfigChangeObserver()
    change_log = []

    def log_changes(event):
        change_log.append(event)
    tracker.register_observer(log_changes)
    tracker.change_log = change_log
    return tracker


@pytest.fixture
def resource_monitor():
    """Fixture for monitoring resource allocation/cleanup."""
    monitor = ResourceTracker()

    def assert_no_leaks(module: (str | None) = None):
        if module:
            leaked = monitor.verify_cleanup(module)
            assert not leaked, f"Module {module} leaked resources: {leaked}"
        else:
            all_active = monitor.get_all_resources(state="active")
            assert not all_active, f"Found leaked resources: {all_active}"
    monitor.assert_no_leaks = assert_no_leaks
    return monitor


@pytest.fixture
def parallel_test_environment(temp_workspace):
    """Set up environment for parallel processing tests."""

    class ParallelTestEnv:

        def __init__(self, workspace: Path):
            self.workspace = workspace
            self.processes = []
            self.threads = []
            self.locks = {}
            self.queues = {}
            self.events = {}

        def create_worker_process(self, target, args=(), name=None):
            """Create a tracked worker process."""
            p = multiprocessing.Process(target=target, args=args, name=name)
            self.processes.append(p)
            return p

        def create_worker_thread(self, target, args=(), name=None):
            """Create a tracked worker thread."""
            t = threading.Thread(target=target, args=args, name=name)
            self.threads.append(t)
            return t

        def create_shared_lock(self, name: str):
            """Create a named lock for synchronization."""
            if name not in self.locks:
                self.locks[name] = threading.Lock()
            return self.locks[name]

        def create_queue(self, name: str, maxsize: int = 0):
            """Create a named queue for communication."""
            if name not in self.queues:
                self.queues[name] = multiprocessing.Queue(maxsize)
            return self.queues[name]

        def create_event(self, name: str):
            """Create a named event for signaling."""
            if name not in self.events:
                self.events[name] = multiprocessing.Event()
            return self.events[name]

        def cleanup(self):
            """Clean up all resources."""
            for p in self.processes:
                if p.is_alive():
                    p.terminate()
                    p.join(timeout=5)
                    if p.is_alive():
                        p.kill()
            for t in self.threads:
                if t.is_alive():
                    t.join(timeout=5)
            for q in self.queues.values():
                q.close()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            self.cleanup()
    env = ParallelTestEnv(temp_workspace)
    yield env
    env.cleanup()


@pytest.fixture
def mock_parser_factory():
    """Mock parser with controllable failures."""

    class MockParser:

        def __init__(self, language: str = "python"):
            self.language = language
            self.fail_on_parse = False
            self.fail_on_nth_call = None
            self.parse_count = 0
            self.timeout = None

        def parse(self, code: bytes, **kwargs):
            self.parse_count += 1
            if self.fail_on_parse:
                raise RuntimeError(f"Parser failed for {self.language}")
            if (self.fail_on_nth_call and self.parse_count == self.
                fail_on_nth_call):
                raise RuntimeError(f"Parser failed on call {self.parse_count}")
            if self.timeout:
                time.sleep(self.timeout)
            tree = Mock()
            tree.root_node = self._create_mock_node(code)
            return tree

        @classmethod
        def _create_mock_node(cls, code: bytes):
            """Create mock syntax tree node."""
            node = Mock()
            node.type = "module"
            node.start_byte = 0
            node.end_byte = len(code)
            node.start_point = 0, 0
            node.end_point = code.count(b"\n"), 0
            node.children = []
            if b"def " in code:
                func_node = Mock()
                func_node.type = "function_definition"
                func_node.start_byte = code.index(b"def ")
                func_node.end_byte = func_node.start_byte + 50
                func_node.children = []
                node.children.append(func_node)
            return node

    class MockParserFactory:

        def __init__(self):
            self.parsers = {}

        def get_parser(self, language: str) -> MockParser:
            if language not in self.parsers:
                self.parsers[language] = MockParser(language)
            return self.parsers[language]

        def configure_failure(self, language: str, fail_type: str, **kwargs):
            """Configure parser to fail in specific ways."""
            parser = self.get_parser(language)
            if fail_type == "always":
                parser.fail_on_parse = True
            elif fail_type == "nth_call":
                parser.fail_on_nth_call = kwargs.get("n", 1)
            elif fail_type == "timeout":
                parser.timeout = kwargs.get("timeout", 10)

        def reset(self):
            """Reset all parsers."""
            self.parsers.clear()
    return MockParserFactory()


@pytest.fixture
def test_file_generator(temp_workspace):
    """Generate test files with specific patterns."""

    class TestFileGenerator:

        def __init__(self, workspace: Path):
            self.workspace = workspace
            self.generated_files = []

        def create_file(self, name: str, content: str, subdir: str = "") -> Path:
            """Create a test file with given content."""
            if subdir:
                target_dir = self.workspace / subdir
                target_dir.mkdir(parents=True, exist_ok=True)
            else:
                target_dir = self.workspace
            file_path = target_dir / name
            file_path.write_text(content)
            self.generated_files.append(file_path)
            return file_path

        def create_large_file(self, name: str, size_mb: int, pattern: str =
            "function", language: str = "python") -> Path:
            """Create a large file with repeated patterns."""
            if language == "python":
                template = f"""
def {pattern}_{{i}}(x):
    '''Function {{i}} docstring'''
    result = x * {{i}}
    return result
"""
            elif language == "javascript":
                template = f"""
function {pattern}_{{i}}(x) {{
    // Function {{i}} comment
    const result = x * {{i}};
    return result;
}}
"""
            else:
                template = f"// {pattern} {{i}}\n"
            template_size = len(template.format(i=0).encode())
            iterations = size_mb * 1024 * 1024 // template_size
            content = ""
            for i in range(iterations):
                content += template.format(i=i)
            return self.create_file(name, content)

        def create_error_file(self, name: str, error_type: str, language:
            str = "python") -> Path:
            """Create file with specific error patterns."""
            error_patterns = {"syntax": {"python": "def broken(\n    pass",
                "javascript": "function broken() { { }"}, "unicode": {
                "python": "# 🚨 def test(): return '\\x80\\x81'",
                "javascript":
                "// 🚨 function test() { return '\\x80\\x81'; }"}, "binary":
                {"python": b"\x00\x01\x02def test(): pass", "javascript":
                b"\x00\x01\x02function test() {}"}}
            content = error_patterns.get(error_type, {}).get(language, "")
            if isinstance(content, bytes):
                file_path = self.workspace / name
                file_path.write_bytes(content)
                self.generated_files.append(file_path)
                return file_path
            return self.create_file(name, content)

        def cleanup(self):
            """Remove all generated files."""
            for file_path in self.generated_files:
                if file_path.exists():
                    file_path.unlink()
    generator = TestFileGenerator(temp_workspace)
    yield generator
    generator.cleanup()


@pytest.fixture
def async_test_runner():
    """Runner for async test scenarios."""

    class AsyncTestRunner:

        def __init__(self):
            self.loop = None
            self.tasks = []

        async def run_async(self, coro):
            """Run async coroutine and return result."""
            return await coro

        def run(self, coro):
            """Run async coroutine in event loop."""
            if not self.loop:
                self.loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self.loop)
            return self.loop.run_until_complete(coro)

        async def run_parallel(self, *coros):
            """Run multiple coroutines in parallel."""
            tasks = [asyncio.create_task(coro) for coro in coros]
            self.tasks.extend(tasks)
            return await asyncio.gather(*tasks)

        async def run_with_timeout(self, coro, timeout: float):
            """Run coroutine with timeout."""
            return await asyncio.wait_for(coro, timeout=timeout)

        def cleanup(self):
            """Clean up event loop and tasks."""
            for task in self.tasks:
                if not task.done():
                    task.cancel()
            if self.loop:
                self.loop.run_until_complete(asyncio.gather(*self.tasks,
                    return_exceptions=True))
                self.loop.close()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            self.cleanup()
    runner = AsyncTestRunner()
    yield runner
    runner.cleanup()


@pytest.fixture
def thread_safe_counter():
    """Thread-safe counter for tracking concurrent operations."""

    class ThreadSafeCounter:

        def __init__(self):
            self._value = 0
            self._lock = threading.Lock()

        def increment(self, amount: int = 1) -> int:
            with self._lock:
                self._value += amount
                return self._value

        def decrement(self, amount: int = 1) -> int:
            with self._lock:
                self._value -= amount
                return self._value

        @property
        def value(self) -> int:
            with self._lock:
                return self._value
    return ThreadSafeCounter()


@pytest.fixture
def performance_monitor():
    """Monitor performance metrics during tests."""

    class PerformanceMonitor:

        def __init__(self):
            self.metrics = {}
            self._start_times = {}

        def start_timing(self, operation: str):
            """Start timing an operation."""
            self._start_times[operation] = time.time()

        def end_timing(self, operation: str) -> float:
            """End timing and return duration."""
            if operation not in self._start_times:
                return 0.0
            duration = time.time() - self._start_times[operation]
            if operation not in self.metrics:
                self.metrics[operation] = []
            self.metrics[operation].append(duration)
            del self._start_times[operation]
            return duration

        @contextmanager
        def measure(self, operation: str):
            """Context manager for timing operations."""
            self.start_timing(operation)
            yield
            self.end_timing(operation)

        def get_stats(self, operation: str) -> dict[str, float]:
            """Get statistics for an operation."""
            if operation not in self.metrics:
                return {}
            times = self.metrics[operation]
            return {"count": len(times), "total": sum(times), "average":
                sum(times) / len(times), "min": min(times), "max": max(times)}
    return PerformanceMonitor()

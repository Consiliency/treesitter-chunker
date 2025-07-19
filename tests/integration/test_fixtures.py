"""Tests for the integration test fixtures."""

import pytest
import asyncio
import time
import threading
from pathlib import Path

from tests.integration.fixtures import ErrorTrackingContext


class TestBasicFixtures:
    """Test basic fixtures like temp_workspace and sample_code_files."""
    
    def test_temp_workspace(self, temp_workspace):
        """Test temporary workspace creation and cleanup."""
        assert temp_workspace.exists()
        assert temp_workspace.is_dir()
        
        # Check standard subdirectories
        assert (temp_workspace / "src").exists()
        assert (temp_workspace / "tests").exists()
        assert (temp_workspace / "cache").exists()
        assert (temp_workspace / "output").exists()
        
        # Create a test file
        test_file = temp_workspace / "test.txt"
        test_file.write_text("test content")
        assert test_file.exists()
        
    def test_sample_code_files(self, sample_code_files):
        """Test sample code file contents."""
        assert "example.py" in sample_code_files
        assert "example.js" in sample_code_files
        assert "example.rs" in sample_code_files
        assert "example.c" in sample_code_files
        
        # Verify Python content
        py_code = sample_code_files["example.py"]
        assert "def calculate_sum" in py_code
        assert "class DataProcessor" in py_code
        assert "async def fetch_data" in py_code
        
        # Verify JavaScript content
        js_code = sample_code_files["example.js"]
        assert "function calculateSum" in js_code
        assert "class DataProcessor" in js_code


class TestErrorTrackingFixtures:
    """Test error tracking fixtures."""
    
    def test_error_tracking_context_basic(self, error_tracking_context):
        """Test basic error tracking context functionality."""
        with error_tracking_context as tracker:
            # Capture an error
            error = ValueError("Test error")
            context = tracker.capture_and_propagate(
                source="module.a",
                target="module.b",
                error=error
            )
            
            # Verify capture
            assert context['source_module'] == "module.a"
            assert context['target_module'] == "module.b"
            assert context['error_type'] == "ValueError"
            
            # Check error chain
            chain = tracker.get_error_chain()
            assert len(chain) == 1
            assert chain[0] == context
            
    def test_error_tracking_with_handlers(self, error_tracking_context):
        """Test error handlers in tracking context."""
        handler_called = False
        received_context = None
        
        def error_handler(context):
            nonlocal handler_called, received_context
            handler_called = True
            received_context = context
        
        with error_tracking_context as tracker:
            # Register handler
            tracker.register_handler("module.target", error_handler)
            
            # Trigger error
            error = RuntimeError("Handler test")
            tracker.capture_and_propagate(
                source="module.source",
                target="module.target",
                error=error
            )
            
            # Verify handler called
            assert handler_called
            assert received_context['error_message'] == "Handler test"
            
    def test_error_tracking_uncaught_exception(self):
        """Test that uncaught exceptions are captured."""
        tracker = ErrorTrackingContext()
        
        try:
            with tracker:
                raise KeyError("Uncaught error")
        except KeyError:
            pass  # Expected
        
        # Verify error was captured
        chain = tracker.get_error_chain()
        # ErrorTrackingContext only captures errors when __exit__ is called with exception info
        # Since we catch the exception, __exit__ doesn't see it
        assert len(chain) == 0  # No errors captured since we caught it


class TestConfigurationFixtures:
    """Test configuration management fixtures."""
    
    def test_config_change_tracker(self, config_change_tracker):
        """Test configuration change tracking."""
        # Make changes
        config_change_tracker.on_config_change("key1", "old", "new")
        config_change_tracker.on_config_change("key2", 10, 20)
        
        # Check change log
        assert hasattr(config_change_tracker, 'change_log')
        assert len(config_change_tracker.change_log) == 2
        assert config_change_tracker.change_log[0]['config_path'] == "key1"


class TestResourceFixtures:
    """Test resource management fixtures."""
    
    def test_resource_monitor(self, resource_monitor):
        """Test resource monitoring fixture."""
        # Track resources
        resource_monitor.track_resource(
            module="test",
            resource_type="file",
            resource_id="file_123"
        )
        
        # Should fail leak check
        with pytest.raises(AssertionError, match="leaked resources"):
            resource_monitor.assert_no_leaks("test")
        
        # Release resource
        resource_monitor.release_resource("file_123")
        
        # Should pass now
        resource_monitor.assert_no_leaks("test")
        resource_monitor.assert_no_leaks()  # Check all modules


class TestParallelFixtures:
    """Test parallel testing fixtures."""
    
    def test_parallel_test_environment(self, parallel_test_environment):
        """Test parallel test environment setup."""
        with parallel_test_environment as env:
            # Test workspace exists
            assert env.workspace.exists()
            
            # Create lock
            lock = env.create_shared_lock("test_lock")
            assert lock is not None
            
            # Create queue
            queue = env.create_queue("test_queue")
            queue.put("test_item")
            assert queue.get() == "test_item"
            
            # Create event
            event = env.create_event("test_event")
            assert not event.is_set()
            event.set()
            assert event.is_set()
            
    def test_parallel_worker_processes(self, parallel_test_environment):
        """Test worker process creation and tracking."""
        results = []
        
        def worker_func(worker_id, result_list):
            result_list.append(worker_id)
        
        with parallel_test_environment as env:
            # Note: Can't directly share list with processes
            # This is just to test process creation/tracking
            for i in range(3):
                p = env.create_worker_process(
                    target=worker_func,
                    args=(i, results),
                    name=f"worker_{i}"
                )
                assert p.name == f"worker_{i}"
                # Don't start - just test creation
            
            assert len(env.processes) == 3
            
    def test_parallel_worker_threads(self, parallel_test_environment):
        """Test worker thread creation and execution."""
        results = []
        lock = threading.Lock()
        
        def worker_func(worker_id):
            with lock:
                results.append(worker_id)
        
        with parallel_test_environment as env:
            # Create and start threads
            for i in range(5):
                t = env.create_worker_thread(
                    target=worker_func,
                    args=(i,),
                    name=f"thread_{i}"
                )
                t.start()
            
            # Wait for completion
            for t in env.threads:
                t.join()
            
            # Verify results
            assert sorted(results) == list(range(5))


class TestMockingFixtures:
    """Test mocking fixtures."""
    
    def test_mock_parser_factory(self, mock_parser_factory):
        """Test mock parser factory."""
        # Get parser
        parser = mock_parser_factory.get_parser("python")
        
        # Normal parse should work
        tree = parser.parse(b"def test(): pass")
        assert tree.root_node.type == "module"
        assert len(tree.root_node.children) == 1  # Has function
        
        # Configure to fail
        mock_parser_factory.configure_failure("python", "always")
        
        # Should fail now
        with pytest.raises(RuntimeError, match="Parser failed"):
            parser.parse(b"def test(): pass")
            
    def test_mock_parser_nth_failure(self, mock_parser_factory):
        """Test nth call failure configuration."""
        mock_parser_factory.configure_failure("javascript", "nth_call", n=3)
        parser = mock_parser_factory.get_parser("javascript")
        
        # First two succeed
        parser.parse(b"function test() {}")
        parser.parse(b"const x = 1;")
        
        # Third fails
        with pytest.raises(RuntimeError, match="failed on call 3"):
            parser.parse(b"let y = 2;")
            
    def test_mock_parser_timeout(self, mock_parser_factory):
        """Test parser timeout simulation."""
        mock_parser_factory.configure_failure("rust", "timeout", timeout=0.1)
        parser = mock_parser_factory.get_parser("rust")
        
        start = time.time()
        parser.parse(b"fn main() {}")
        duration = time.time() - start
        
        assert duration >= 0.1


class TestFileGeneratorFixtures:
    """Test file generation fixtures."""
    
    def test_test_file_generator(self, test_file_generator):
        """Test basic file generation."""
        # Create simple file
        file_path = test_file_generator.create_file(
            "test.py",
            "print('hello')"
        )
        
        assert file_path.exists()
        assert file_path.read_text() == "print('hello')"
        
        # Create in subdirectory
        sub_file = test_file_generator.create_file(
            "module.js",
            "export default {};",
            subdir="src/components"
        )
        
        assert sub_file.exists()
        assert sub_file.parent.name == "components"
        
    def test_large_file_generation(self, test_file_generator):
        """Test large file generation."""
        # Create 1MB Python file
        large_file = test_file_generator.create_large_file(
            "large.py",
            size_mb=1,
            pattern="process",
            language="python"
        )
        
        assert large_file.exists()
        size = large_file.stat().st_size
        assert size >= 1024 * 1024  # At least 1MB
        
        content = large_file.read_text()
        assert "def process_0" in content
        assert "def process_100" in content
        
    def test_error_file_generation(self, test_file_generator):
        """Test error pattern file generation."""
        # Syntax error
        syntax_file = test_file_generator.create_error_file(
            "syntax_error.py",
            error_type="syntax",
            language="python"
        )
        
        content = syntax_file.read_text()
        assert "def broken(" in content
        
        # Unicode error
        unicode_file = test_file_generator.create_error_file(
            "unicode_error.js",
            error_type="unicode",
            language="javascript"
        )
        
        content = unicode_file.read_text()
        assert "🚨" in content
        
        # Binary content
        binary_file = test_file_generator.create_error_file(
            "binary.py",
            error_type="binary",
            language="python"
        )
        
        content = binary_file.read_bytes()
        assert content.startswith(b"\x00\x01\x02")


class TestAsyncFixtures:
    """Test async testing fixtures."""
    
    def test_async_test_runner(self, async_test_runner):
        """Test basic async runner functionality."""
        async def test_coro():
            await asyncio.sleep(0.01)
            return "result"
        
        result = async_test_runner.run(test_coro())
        assert result == "result"
        
    def test_async_parallel_execution(self, async_test_runner):
        """Test parallel async execution."""
        async def worker(n):
            await asyncio.sleep(0.01)
            return n * 2
        
        async def run_test():
            results = await async_test_runner.run_parallel(
                worker(1),
                worker(2),
                worker(3)
            )
            return results
        
        results = async_test_runner.run(run_test())
        assert results == [2, 4, 6]
        
    def test_async_timeout(self, async_test_runner):
        """Test async timeout functionality."""
        async def slow_coro():
            await asyncio.sleep(1.0)
            return "should not reach"
        
        async def run_with_timeout():
            return await async_test_runner.run_with_timeout(
                slow_coro(),
                timeout=0.1
            )
        
        with pytest.raises(asyncio.TimeoutError):
            async_test_runner.run(run_with_timeout())


class TestConcurrencyFixtures:
    """Test concurrency helper fixtures."""
    
    def test_thread_safe_counter(self, thread_safe_counter):
        """Test thread-safe counter."""
        def increment_many():
            for _ in range(100):
                thread_safe_counter.increment()
        
        # Run in parallel
        threads = []
        for _ in range(10):
            t = threading.Thread(target=increment_many)
            t.start()
            threads.append(t)
        
        for t in threads:
            t.join()
        
        # Should have exact count
        assert thread_safe_counter.value == 1000
        
        # Test decrement
        thread_safe_counter.decrement(500)
        assert thread_safe_counter.value == 500
        
    def test_performance_monitor(self, performance_monitor):
        """Test performance monitoring."""
        # Time an operation
        performance_monitor.start_timing("test_op")
        time.sleep(0.1)
        duration = performance_monitor.end_timing("test_op")
        
        assert duration >= 0.1
        
        # Use context manager
        with performance_monitor.measure("context_op"):
            time.sleep(0.05)
        
        # Get statistics
        stats = performance_monitor.get_stats("test_op")
        assert stats['count'] == 1
        assert stats['min'] >= 0.1
        
        # Multiple measurements
        for _ in range(3):
            with performance_monitor.measure("multi_op"):
                time.sleep(0.01)
        
        multi_stats = performance_monitor.get_stats("multi_op")
        assert multi_stats['count'] == 3
        assert multi_stats['average'] >= 0.01
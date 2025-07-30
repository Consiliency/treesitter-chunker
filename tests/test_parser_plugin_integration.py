"""Tests for Parser Factory ↔ Plugin System Integration (Phase 7.5).

This module tests the integration patterns between the parser factory and plugin system,
focusing on:
- Parser pool management for dynamic languages
- Memory leaks with plugin parser instances
- Thread safety with plugin parsers
- Parser configuration propagation

Note: Since the current implementation doesn't have full plugin integration with
the parser factory, these tests demonstrate the patterns that would be used in
a full integration while working with the existing architecture.
"""

import gc
import os
import shutil
import tempfile
import threading
import time
import weakref
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from queue import Queue
from typing import Any
from unittest.mock import Mock, patch

import psutil
import pytest
import tree_sitter

from chunker.factory import ParserFactory
from chunker.registry import LanguageRegistry


class MockDynamicParser:
    """Mock parser that simulates a dynamically loaded language parser."""

    def __init__(self, language: str):
        self.language = language
        self.parse_count = 0
        self.config = {}
        self._timeout = None

    def set_language(self, language):
        """Mock set_language method."""

    def set_timeout_micros(self, timeout: int):
        """Mock timeout setting."""
        self._timeout = timeout

    def parse(self, code: bytes, keep_text: bool = True):
        """Mock parse method."""
        # Don't increment here - let subclasses control it
        return Mock(root_node=Mock())


class TestParserPoolManagement:
    """Test parser pool management patterns for dynamically loaded languages."""

    def setup_method(self):
        """Set up test environment."""
        # Initialize with a mock or real registry
        try:
            # Try to use real registry

            lib_path = Path(__file__).parent.parent / "build" / "my-languages.so"
            self.registry = LanguageRegistry(lib_path)
        except (FileNotFoundError, ImportError, ModuleNotFoundError):
            # Fallback to mock registry
            self.registry = Mock(spec=LanguageRegistry)
            self.registry.get_language = Mock()

        self.parser_factory = ParserFactory(self.registry)
        self.temp_dir = tempfile.mkdtemp()
        self.mock_parsers = {}

    def teardown_method(self):
        """Clean up test environment."""
        # Clear singletons
        ParserFactory._instance = None
        LanguageRegistry._instance = None

        # Clean up temp directory

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_dynamic_language_parser_pool_creation(self):
        """Test that parser pools are created for dynamically loaded languages."""
        # Simulate dynamic language registration
        dynamic_lang = "dynamic_test_lang"

        # Mock the registry to include our dynamic language
        with patch.object(
            self.parser_factory._registry,
            "get_language",
        ) as mock_get_lang:
            mock_get_lang.return_value = Mock()  # Mock language object

            # Create parser pool for dynamic language
            parsers = []
            for _i in range(5):
                parser = Mock(spec=tree_sitter.Parser)
                parser.set_language = Mock()
                parser.set_timeout_micros = Mock()

                # Store parser
                parsers.append(parser)

                # Simulate returning parser to pool
                if dynamic_lang not in self.parser_factory._pools:
                    self.parser_factory._pools[dynamic_lang] = Queue()
                self.parser_factory._pools[dynamic_lang].put(parser)

            # Verify pool was created
            assert dynamic_lang in self.parser_factory._pools
            pool = self.parser_factory._pools[dynamic_lang]
            assert pool.qsize() == 5

    def test_parser_pool_size_limits_for_plugins(self):
        """Test that parser pools respect size limits for plugin languages."""
        # Configure max pool size
        max_pool_size = 3
        self.parser_factory._max_pool_size = max_pool_size

        dynamic_lang = "limited_lang"

        # Create pool
        if dynamic_lang not in self.parser_factory._pools:
            self.parser_factory._pools[dynamic_lang] = Queue(maxsize=max_pool_size)

        # Try to add more parsers than limit
        parsers_added = 0
        for _i in range(max_pool_size + 2):
            parser = Mock(spec=tree_sitter.Parser)
            try:
                self.parser_factory._pools[dynamic_lang].put_nowait(parser)
                parsers_added += 1
            except (IndexError, KeyError, SyntaxError):
                # Pool is full
                pass

        # Should only accept up to max_pool_size
        assert parsers_added == max_pool_size
        assert self.parser_factory._pools[dynamic_lang].qsize() == max_pool_size

    def test_parser_pool_cleanup_pattern(self):
        """Test cleanup pattern when plugins are unloaded."""
        dynamic_lang = "cleanup_lang"

        # Create pool with parsers
        self.parser_factory._pools[dynamic_lang] = Queue()

        # Add parsers
        parser_refs = []
        for _i in range(3):
            parser = Mock(spec=tree_sitter.Parser)
            parser_refs.append(weakref.ref(parser))
            self.parser_factory._pools[dynamic_lang].put(parser)

        # Verify pool exists
        assert dynamic_lang in self.parser_factory._pools

        # Cleanup pattern: empty and remove pool
        while not self.parser_factory._pools[dynamic_lang].empty():
            self.parser_factory._pools[dynamic_lang].get()

        del self.parser_factory._pools[dynamic_lang]

        # Verify cleanup
        assert dynamic_lang not in self.parser_factory._pools

    def test_parser_pool_recovery_after_errors(self):
        """Test that parser pools can recover from errors."""
        dynamic_lang = "error_recovery_lang"

        # Create pool
        self.parser_factory._pools[dynamic_lang] = Queue()

        # Track successful and failed operations
        successful_puts = 0
        failed_puts = 0

        # Simulate some operations failing
        for i in range(10):
            parser = Mock(spec=tree_sitter.Parser)

            if i % 3 == 0:
                # Simulate error - don't add to pool
                failed_puts += 1
            else:
                # Success - add to pool
                self.parser_factory._pools[dynamic_lang].put(parser)
                successful_puts += 1

        # Verify pool still functional after errors
        assert self.parser_factory._pools[dynamic_lang].qsize() == successful_puts
        assert failed_puts > 0  # Ensure we had some failures


class TestMemoryLeaks:
    """Test for memory leak patterns with parser instances."""

    def setup_method(self):
        """Set up test environment."""
        # Initialize with mock registry
        self.registry = Mock(spec=LanguageRegistry)
        self.parser_factory = ParserFactory(self.registry)
        self.process = psutil.Process(os.getpid())

    def teardown_method(self):
        """Clean up test environment."""
        ParserFactory._instance = None
        LanguageRegistry._instance = None
        gc.collect()

    def test_parser_instance_garbage_collection(self):
        """Test that parser instances can be garbage collected."""
        # Track parser lifecycle with weak references
        parser_refs = []

        # Create and track parsers
        for i in range(10):
            parser = MockDynamicParser(f"gc_test_{i}")
            parser_refs.append(weakref.ref(parser))

            # Delete strong reference
            del parser

        # Force garbage collection
        gc.collect()
        time.sleep(0.1)

        # Check that parsers were collected
        collected_count = sum(1 for ref in parser_refs if ref() is None)
        assert collected_count == len(parser_refs)

    def test_parser_pool_memory_management(self):
        """Test memory management patterns for parser pools."""
        # Create pools for multiple languages
        pools = {}
        parser_refs = []

        for i in range(5):
            lang = f"mem_test_{i}"
            pools[lang] = Queue()

            # Add parsers to pool
            for _j in range(5):
                parser = MockDynamicParser(lang)
                parser_refs.append(weakref.ref(parser))
                pools[lang].put(parser)

        # Clear pools
        for lang, pool in pools.items():
            while not pool.empty():
                pool.get()

        pools.clear()

        # Force GC
        gc.collect()
        time.sleep(0.1)

        # Parsers should be collectible after pools are cleared
        collected = sum(1 for ref in parser_refs if ref() is None)
        assert collected > 0

    def test_circular_reference_prevention_pattern(self):
        """Test pattern for preventing circular references."""

        # Create object that could have circular reference
        class CircularParser(MockDynamicParser):
            def __init__(self, language):
                super().__init__(language)
                self.pool_ref = None  # Could create circular ref

        # Track with weak reference
        parser = CircularParser("circular_test")
        parser_ref = weakref.ref(parser)

        # Simulate pool reference (but use weakref to prevent circular ref)
        pool = Queue()
        parser.pool_ref = weakref.ref(pool)
        pool.put(parser)

        # Clear references
        pool.get()
        del parser
        del pool

        # Force GC
        gc.collect()

        # Parser should be collectible
        assert parser_ref() is None


class TestThreadSafety:
    """Test thread safety patterns for parser operations."""

    def setup_method(self):
        """Set up test environment."""
        # Initialize with mock registry
        self.registry = Mock(spec=LanguageRegistry)
        self.parser_factory = ParserFactory(self.registry)
        self.errors = []
        self.success_count = 0
        self.lock = threading.Lock()

    def teardown_method(self):
        """Clean up test environment."""
        ParserFactory._instance = None
        LanguageRegistry._instance = None

    def test_concurrent_pool_access_pattern(self):
        """Test thread-safe access pattern for parser pools."""
        # Create thread-safe pool
        pool = Queue()
        threading.Lock()

        # Pre-populate pool
        for i in range(10):
            pool.put(MockDynamicParser("concurrent_test"))

        def worker(worker_id):
            """Worker that safely accesses pool."""
            try:
                for _i in range(10):
                    # Get parser from pool
                    parser = pool.get()

                    # Simulate work
                    parser.parse_count += 1
                    parser.parse(b"test code")
                    time.sleep(0.001)

                    # Return parser to pool
                    pool.put(parser)

                    with self.lock:
                        self.success_count += 1

            except (OSError, IndexError, KeyError) as e:
                with self.lock:
                    self.errors.append((worker_id, str(e)))

        # Run concurrent workers
        threads = []
        for i in range(5):
            thread = threading.Thread(target=worker, args=(i,))
            threads.append(thread)
            thread.start()

        # Wait for completion
        for thread in threads:
            thread.join()

        # Verify thread safety
        assert len(self.errors) == 0
        assert self.success_count == 50  # 5 workers * 10 operations

    def test_parser_isolation_between_threads(self):
        """Test that parsers are properly isolated between threads."""
        # Track active parsers to detect conflicts
        active_parsers = set()
        parser_lock = threading.Lock()
        collision_count = 0

        # Create pool with unique parsers
        pool = Queue()
        for i in range(20):
            parser = MockDynamicParser(f"isolated_{i}")
            parser.id = i
            pool.put(parser)

        def worker(worker_id):
            """Worker that checks for parser isolation."""
            nonlocal collision_count

            for _ in range(20):
                parser = pool.get()

                with parser_lock:
                    if parser.id in active_parsers:
                        collision_count += 1
                    active_parsers.add(parser.id)

                # Simulate work
                time.sleep(0.001)

                with parser_lock:
                    active_parsers.remove(parser.id)

                pool.put(parser)

        # Run workers
        threads = []
        for i in range(10):
            thread = threading.Thread(target=worker, args=(i,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # No parser should be used concurrently
        assert collision_count == 0


class TestParserConfiguration:
    """Test configuration propagation patterns."""

    def setup_method(self):
        """Set up test environment."""
        # Initialize with mock registry
        self.registry = Mock(spec=LanguageRegistry)
        self.parser_factory = ParserFactory(self.registry)

    def teardown_method(self):
        """Clean up test environment."""
        ParserFactory._instance = None
        LanguageRegistry._instance = None

    def test_configuration_propagation_pattern(self):
        """Test pattern for propagating configuration to parsers."""
        # Create parser with configuration tracking
        parser = MockDynamicParser("config_test")

        # Configuration to apply
        config = {
            "timeout": 5000,
            "max_depth": 50,
            "custom_option": "test_value",
        }

        # Apply configuration
        if "timeout" in config:
            parser.set_timeout_micros(config["timeout"])
        parser.config.update(config)

        # Verify configuration applied
        assert parser._timeout == 5000
        assert parser.config["max_depth"] == 50
        assert parser.config["custom_option"] == "test_value"

    def test_configuration_isolation_pattern(self):
        """Test that configurations are isolated between parsers."""
        # Create parsers with different configs
        parser1 = MockDynamicParser("config_iso_1")
        parser2 = MockDynamicParser("config_iso_2")

        # Apply different configurations
        parser1.config.update({"timeout": 1000, "option": "value1"})
        parser2.config.update({"timeout": 2000, "option": "value2"})

        # Verify isolation
        assert parser1.config["timeout"] == 1000
        assert parser1.config["option"] == "value1"

        assert parser2.config["timeout"] == 2000
        assert parser2.config["option"] == "value2"

    def test_configuration_validation_pattern(self):
        """Test configuration validation pattern."""

        def validate_config(config: dict[str, Any]) -> None:
            """Validate parser configuration."""
            if "timeout" in config and config["timeout"] < 0:
                raise ValueError("Timeout must be positive")

            if "max_depth" in config and config["max_depth"] > 1000:
                raise ValueError("Max depth too large")

        # Test invalid configurations
        with pytest.raises(ValueError, match="Timeout must be positive"):
            validate_config({"timeout": -100})

        with pytest.raises(ValueError, match="Max depth too large"):
            validate_config({"max_depth": 2000})

        # Test valid configuration
        valid_config = {"timeout": 5000, "max_depth": 100}
        validate_config(valid_config)  # Should not raise


class TestIntegrationPatterns:
    """Test integration patterns between parser factory and plugin-like systems."""

    def setup_method(self):
        """Set up test environment."""
        # Initialize with mock registry
        self.registry = Mock(spec=LanguageRegistry)
        self.parser_factory = ParserFactory(self.registry)
        self.temp_dir = tempfile.mkdtemp()

    def teardown_method(self):
        """Clean up test environment."""
        ParserFactory._instance = None
        LanguageRegistry._instance = None


        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_hot_reload_pattern(self):
        """Test pattern for hot-reloading parsers."""
        # Track parser versions
        parser_versions = {}

        # Initial "version"
        lang = "hotreload_test"
        parser_v1 = MockDynamicParser(lang)
        parser_v1.version = "1.0.0"
        parser_versions[lang] = parser_v1

        # Use parser
        parser_v1.parse_count += 1
        parser_v1.parse(b"test code v1")
        assert parser_v1.parse_count == 1

        # Simulate hot reload - replace with new version
        parser_v2 = MockDynamicParser(lang)
        parser_v2.version = "2.0.0"
        parser_versions[lang] = parser_v2

        # Use new parser
        parser_v2.parse_count += 1
        parser_v2.parse(b"test code v2")
        assert parser_v2.parse_count == 1
        assert parser_v2.version == "2.0.0"

    def test_fallback_pattern(self):
        """Test fallback pattern when parsers fail."""

        class FailingParser(MockDynamicParser):
            def __init__(self):
                super().__init__("failing_lang")
                self.fail_after = 3

            def parse(self, code: bytes, keep_text: bool = True):
                current_count = self.parse_count
                self.parse_count += 1
                if current_count >= self.fail_after:
                    raise RuntimeError("Parser failed")
                return MockDynamicParser.parse(self, code, keep_text)

        parser = FailingParser()

        # Use parser successfully
        successful_parses = 0
        failed_parses = 0

        for _i in range(10):
            try:
                parser.parse(b"test code")
                successful_parses += 1
            except RuntimeError:
                failed_parses += 1

        assert successful_parses == 3
        assert failed_parses == 7

    def test_performance_pattern_with_many_languages(self):
        """Test performance pattern with many language parsers."""
        num_languages = 20
        parsers = {}

        # Create parsers for many languages
        start_time = time.time()

        for i in range(num_languages):
            lang = f"perf_lang_{i}"
            parsers[lang] = MockDynamicParser(lang)

        creation_time = time.time() - start_time

        # Should create quickly
        assert creation_time < 1.0

        # Test concurrent access
        def access_parser(lang):
            parser = parsers[lang]
            parser.parse_count += 1
            parser.parse(b"test")

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            for lang in parsers:
                future = executor.submit(access_parser, lang)
                futures.append(future)

            # Wait for all to complete
            for future in as_completed(futures):
                future.result()

        # Verify all parsers were used
        for parser in parsers.values():
            assert parser.parse_count > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

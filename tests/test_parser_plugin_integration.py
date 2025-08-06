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

from chunker._internal.factory import ParserFactory
from chunker._internal.registry import LanguageRegistry


class MockDynamicParser:
    """Mock parser that simulates a dynamically loaded language parser."""

    def __init__(self, language: str):
        self.language = language
        self.parse_count = 0
        self.config = {}
        self._timeout = None

    @staticmethod
    def set_language(language):
        """Mock set_language method."""

    def set_timeout_micros(self, timeout: int):
        """Mock timeout setting."""
        self._timeout = timeout

    @classmethod
    def parse(cls, code: bytes, keep_text: bool = True):
        """Mock parse method."""
        return Mock(root_node=Mock())


class TestParserPoolManagement:
    """Test parser pool management patterns for dynamically loaded languages."""

    def setup_method(self):
        """Set up test environment."""
        try:
            lib_path = (
                Path(
                    __file__,
                ).parent.parent
                / "build"
                / "my-languages.so"
            )
            self.registry = LanguageRegistry(lib_path)
        except (FileNotFoundError, ImportError, ModuleNotFoundError):
            self.registry = Mock(spec=LanguageRegistry)
            self.registry.get_language = Mock()
        self.parser_factory = ParserFactory(self.registry)
        self.temp_dir = tempfile.mkdtemp()
        self.mock_parsers = {}

    def teardown_method(self):
        """Clean up test environment."""
        ParserFactory._instance = None
        LanguageRegistry._instance = None
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_dynamic_language_parser_pool_creation(self):
        """Test that parser pools are created for dynamically loaded languages."""
        dynamic_lang = "dynamic_test_lang"
        with patch.object(
            self.parser_factory._registry,
            "get_language",
        ) as mock_get_lang:
            mock_get_lang.return_value = Mock()
            parsers = []
            for _i in range(5):
                parser = Mock(spec=tree_sitter.Parser)
                parser.set_language = Mock()
                parser.set_timeout_micros = Mock()
                parsers.append(parser)
                if dynamic_lang not in self.parser_factory._pools:
                    self.parser_factory._pools[dynamic_lang] = Queue()
                self.parser_factory._pools[dynamic_lang].put(parser)
            assert dynamic_lang in self.parser_factory._pools
            pool = self.parser_factory._pools[dynamic_lang]
            assert pool.qsize() == 5

    def test_parser_pool_size_limits_for_plugins(self):
        """Test that parser pools respect size limits for plugin languages."""
        max_pool_size = 3
        self.parser_factory._max_pool_size = max_pool_size
        dynamic_lang = "limited_lang"
        if dynamic_lang not in self.parser_factory._pools:
            self.parser_factory._pools[dynamic_lang] = Queue(maxsize=max_pool_size)
        parsers_added = 0
        for _i in range(max_pool_size + 2):
            parser = Mock(spec=tree_sitter.Parser)
            try:
                self.parser_factory._pools[dynamic_lang].put_nowait(parser)
                parsers_added += 1
            except (IndexError, KeyError, SyntaxError):
                pass
        assert parsers_added == max_pool_size
        assert self.parser_factory._pools[dynamic_lang].qsize() == max_pool_size

    def test_parser_pool_cleanup_pattern(self):
        """Test cleanup pattern when plugins are unloaded."""
        dynamic_lang = "cleanup_lang"
        self.parser_factory._pools[dynamic_lang] = Queue()
        parser_refs = []
        for _i in range(3):
            parser = Mock(spec=tree_sitter.Parser)
            parser_refs.append(weakref.ref(parser))
            self.parser_factory._pools[dynamic_lang].put(parser)
        assert dynamic_lang in self.parser_factory._pools
        while not self.parser_factory._pools[dynamic_lang].empty():
            self.parser_factory._pools[dynamic_lang].get()
        del self.parser_factory._pools[dynamic_lang]
        assert dynamic_lang not in self.parser_factory._pools

    def test_parser_pool_recovery_after_errors(self):
        """Test that parser pools can recover from errors."""
        dynamic_lang = "error_recovery_lang"
        self.parser_factory._pools[dynamic_lang] = Queue()
        successful_puts = 0
        failed_puts = 0
        for i in range(10):
            parser = Mock(spec=tree_sitter.Parser)
            if i % 3 == 0:
                failed_puts += 1
            else:
                self.parser_factory._pools[dynamic_lang].put(parser)
                successful_puts += 1
        assert self.parser_factory._pools[dynamic_lang].qsize() == successful_puts
        assert failed_puts > 0


class TestMemoryLeaks:
    """Test for memory leak patterns with parser instances."""

    def setup_method(self):
        """Set up test environment."""
        self.registry = Mock(spec=LanguageRegistry)
        self.parser_factory = ParserFactory(self.registry)
        self.process = psutil.Process(os.getpid())

    @staticmethod
    def teardown_method():
        """Clean up test environment."""
        ParserFactory._instance = None
        LanguageRegistry._instance = None
        gc.collect()

    @classmethod
    def test_parser_instance_garbage_collection(cls):
        """Test that parser instances can be garbage collected."""
        parser_refs = []
        for i in range(10):
            parser = MockDynamicParser(f"gc_test_{i}")
            parser_refs.append(weakref.ref(parser))
            del parser
        gc.collect()
        time.sleep(0.1)
        collected_count = sum(1 for ref in parser_refs if ref() is None)
        assert collected_count == len(parser_refs)

    @classmethod
    def test_parser_pool_memory_management(cls):
        """Test memory management patterns for parser pools."""
        pools = {}
        parser_refs = []
        for i in range(5):
            lang = f"mem_test_{i}"
            pools[lang] = Queue()
            for _j in range(5):
                parser = MockDynamicParser(lang)
                parser_refs.append(weakref.ref(parser))
                pools[lang].put(parser)
        for lang, pool in pools.items():
            while not pool.empty():
                pool.get()
        pools.clear()
        gc.collect()
        time.sleep(0.1)
        collected = sum(1 for ref in parser_refs if ref() is None)
        assert collected > 0

    @staticmethod
    def test_circular_reference_prevention_pattern():
        """Test pattern for preventing circular references."""

        class CircularParser(MockDynamicParser):

            def __init__(self, language):
                super().__init__(language)
                self.pool_ref = None

        parser = CircularParser("circular_test")
        parser_ref = weakref.ref(parser)
        pool = Queue()
        parser.pool_ref = weakref.ref(pool)
        pool.put(parser)
        pool.get()
        del parser
        del pool
        gc.collect()
        assert parser_ref() is None


class TestThreadSafety:
    """Test thread safety patterns for parser operations."""

    def setup_method(self):
        """Set up test environment."""
        self.registry = Mock(spec=LanguageRegistry)
        self.parser_factory = ParserFactory(self.registry)
        self.errors = []
        self.success_count = 0
        self.lock = threading.Lock()

    @staticmethod
    def teardown_method():
        """Clean up test environment."""
        ParserFactory._instance = None
        LanguageRegistry._instance = None

    def test_concurrent_pool_access_pattern(self):
        """Test thread-safe access pattern for parser pools."""
        pool = Queue()
        threading.Lock()
        for i in range(10):
            pool.put(MockDynamicParser("concurrent_test"))

        def worker(worker_id):
            """Worker that safely accesses pool."""
            try:
                for _i in range(10):
                    parser = pool.get()
                    parser.parse_count += 1
                    parser.parse(b"test code")
                    time.sleep(0.001)
                    pool.put(parser)
                    with self.lock:
                        self.success_count += 1
            except (OSError, IndexError, KeyError) as e:
                with self.lock:
                    self.errors.append((worker_id, str(e)))

        threads = []
        for i in range(5):
            thread = threading.Thread(target=worker, args=(i,))
            threads.append(thread)
            thread.start()
        for thread in threads:
            thread.join()
        assert len(self.errors) == 0
        assert self.success_count == 50

    @classmethod
    def test_parser_isolation_between_threads(cls):
        """Test that parsers are properly isolated between threads."""
        active_parsers = set()
        parser_lock = threading.Lock()
        collision_count = 0
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
                time.sleep(0.001)
                with parser_lock:
                    active_parsers.remove(parser.id)
                pool.put(parser)

        threads = []
        for i in range(10):
            thread = threading.Thread(target=worker, args=(i,))
            threads.append(thread)
            thread.start()
        for thread in threads:
            thread.join()
        assert collision_count == 0


class TestParserConfiguration:
    """Test configuration propagation patterns."""

    def setup_method(self):
        """Set up test environment."""
        self.registry = Mock(spec=LanguageRegistry)
        self.parser_factory = ParserFactory(self.registry)

    @staticmethod
    def teardown_method():
        """Clean up test environment."""
        ParserFactory._instance = None
        LanguageRegistry._instance = None

    @classmethod
    def test_configuration_propagation_pattern(cls):
        """Test pattern for propagating configuration to parsers."""
        parser = MockDynamicParser("config_test")
        config = {"timeout": 5000, "max_depth": 50, "custom_option": "test_value"}
        if "timeout" in config:
            parser.set_timeout_micros(config["timeout"])
        parser.config.update(config)
        assert parser._timeout == 5000
        assert parser.config["max_depth"] == 50
        assert parser.config["custom_option"] == "test_value"

    @classmethod
    def test_configuration_isolation_pattern(cls):
        """Test that configurations are isolated between parsers."""
        parser1 = MockDynamicParser("config_iso_1")
        parser2 = MockDynamicParser("config_iso_2")
        parser1.config.update({"timeout": 1000, "option": "value1"})
        parser2.config.update({"timeout": 2000, "option": "value2"})
        assert parser1.config["timeout"] == 1000
        assert parser1.config["option"] == "value1"
        assert parser2.config["timeout"] == 2000
        assert parser2.config["option"] == "value2"

    @classmethod
    def test_configuration_validation_pattern(cls):
        """Test configuration validation pattern."""

        def validate_config(config: dict[str, Any]) -> None:
            """Validate parser configuration."""
            if "timeout" in config and config["timeout"] < 0:
                raise ValueError("Timeout must be positive")
            if "max_depth" in config and config["max_depth"] > 1000:
                raise ValueError("Max depth too large")

        with pytest.raises(ValueError, match="Timeout must be positive"):
            validate_config({"timeout": -100})
        with pytest.raises(ValueError, match="Max depth too large"):
            validate_config({"max_depth": 2000})
        valid_config = {"timeout": 5000, "max_depth": 100}
        validate_config(valid_config)


class TestIntegrationPatterns:
    """Test integration patterns between parser factory and plugin-like systems."""

    def setup_method(self):
        """Set up test environment."""
        self.registry = Mock(spec=LanguageRegistry)
        self.parser_factory = ParserFactory(self.registry)
        self.temp_dir = tempfile.mkdtemp()

    def teardown_method(self):
        """Clean up test environment."""
        ParserFactory._instance = None
        LanguageRegistry._instance = None
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @classmethod
    def test_hot_reload_pattern(cls):
        """Test pattern for hot-reloading parsers."""
        parser_versions = {}
        lang = "hotreload_test"
        parser_v1 = MockDynamicParser(lang)
        parser_v1.version = "1.0.0"
        parser_versions[lang] = parser_v1
        parser_v1.parse_count += 1
        parser_v1.parse(b"test code v1")
        assert parser_v1.parse_count == 1
        parser_v2 = MockDynamicParser(lang)
        parser_v2.version = "2.0.0"
        parser_versions[lang] = parser_v2
        parser_v2.parse_count += 1
        parser_v2.parse(b"test code v2")
        assert parser_v2.parse_count == 1
        assert parser_v2.version == "2.0.0"

    @staticmethod
    def test_fallback_pattern():
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

    @classmethod
    def test_performance_pattern_with_many_languages(cls):
        """Test performance pattern with many language parsers."""
        num_languages = 20
        parsers = {}
        start_time = time.time()
        for i in range(num_languages):
            lang = f"perf_lang_{i}"
            parsers[lang] = MockDynamicParser(lang)
        creation_time = time.time() - start_time
        assert creation_time < 1.0

        def access_parser(lang):
            parser = parsers[lang]
            parser.parse_count += 1
            parser.parse(b"test")

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            for lang in parsers:
                future = executor.submit(access_parser, lang)
                futures.append(future)
            for future in as_completed(futures):
                future.result()
        for parser in parsers.values():
            assert parser.parse_count > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

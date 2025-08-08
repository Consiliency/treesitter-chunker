"""Tests for ParserFactory component."""

import threading
import time
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from tree_sitter import Parser

from chunker._internal.factory import LRUCache, ParserConfig, ParserFactory, ParserPool
from chunker._internal.registry import LanguageRegistry
from chunker.exceptions import LanguageNotFoundError, ParserConfigError, ParserInitError


class TestParserConfig:
    """Test ParserConfig validation."""

    @classmethod
    def test_valid_config(cls):
        """Test valid configuration."""
        config = ParserConfig(timeout_ms=1000)
        config.validate()
        config = ParserConfig(included_ranges=[])
        config.validate()

    @classmethod
    def test_invalid_timeout(cls):
        """Test invalid timeout values."""
        config = ParserConfig(timeout_ms=-1)
        with pytest.raises(ParserConfigError) as exc_info:
            config.validate()
        assert exc_info.value.config_name == "timeout_ms"
        assert exc_info.value.value == -1
        config = ParserConfig(timeout_ms="not a number")
        with pytest.raises(ParserConfigError):
            config.validate()

    @classmethod
    def test_invalid_ranges(cls):
        """Test invalid included_ranges."""
        config = ParserConfig(included_ranges="not a list")
        with pytest.raises(ParserConfigError) as exc_info:
            config.validate()
        assert exc_info.value.config_name == "included_ranges"


class TestLRUCache:
    """Test LRU cache implementation."""

    @classmethod
    def test_basic_operations(cls):
        """Test basic get/put operations."""
        cache = LRUCache(maxsize=3)
        parser1 = Mock(spec=Parser)
        parser2 = Mock(spec=Parser)
        cache.put("python", parser1)
        cache.put("javascript", parser2)
        assert cache.get("python") is parser1
        assert cache.get("javascript") is parser2
        assert cache.get("nonexistent") is None

    @classmethod
    def test_lru_eviction(cls):
        """Test LRU eviction policy."""
        cache = LRUCache(maxsize=2)
        parser1 = Mock(spec=Parser)
        parser2 = Mock(spec=Parser)
        parser3 = Mock(spec=Parser)
        cache.put("python", parser1)
        cache.put("javascript", parser2)
        cache.get("python")
        cache.put("rust", parser3)
        assert cache.get("python") is parser1
        assert cache.get("rust") is parser3
        assert cache.get("javascript") is None

    @classmethod
    def test_clear(cls):
        """Test cache clearing."""
        cache = LRUCache(maxsize=3)
        cache.put("python", Mock(spec=Parser))
        cache.put("javascript", Mock(spec=Parser))
        cache.clear()
        assert cache.get("python") is None
        assert cache.get("javascript") is None

    @classmethod
    def test_thread_safety(cls):
        """Test thread-safe operations."""
        cache = LRUCache(maxsize=10)
        errors = []

        def worker(thread_id):
            try:
                for i in range(10):
                    parser = Mock(spec=Parser)
                    cache.put(f"lang{thread_id}_{i}", parser)
                    retrieved = cache.get(f"lang{thread_id}_{i}")
                    assert retrieved is parser
            except (OSError, AttributeError, IndexError) as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(errors) == 0


class TestParserPool:
    """Test parser pool implementation."""

    @classmethod
    def test_pool_operations(cls):
        """Test basic pool get/put."""
        pool = ParserPool("python", max_size=3)
        assert pool.get() is None
        parser1 = Mock(spec=Parser)
        parser2 = Mock(spec=Parser)
        assert pool.put(parser1) is True
        assert pool.put(parser2) is True
        assert pool.size() == 2
        assert pool.get() is parser1
        assert pool.get() is parser2
        assert pool.get() is None

    @classmethod
    def test_pool_max_size(cls):
        """Test pool size limits."""
        pool = ParserPool("python", max_size=2)
        parser1 = Mock(spec=Parser)
        parser2 = Mock(spec=Parser)
        parser3 = Mock(spec=Parser)
        assert pool.put(parser1) is True
        assert pool.put(parser2) is True
        assert pool.put(parser3) is False


class TestParserFactory:
    """Test ParserFactory functionality."""

    @classmethod
    @pytest.fixture
    def registry(cls):
        """Create a real registry for testing."""
        lib_path = Path(__file__).parent.parent / "build" / "my-languages.so"
        return LanguageRegistry(lib_path)

    @classmethod
    def test_parser_creation(cls, registry):
        """Test basic parser creation."""
        factory = ParserFactory(registry)
        parser = factory.get_parser("python")
        assert isinstance(parser, Parser)
        assert factory._parser_count == 1

    @classmethod
    def test_parser_caching(cls, registry):
        """Test that parsers are cached."""
        factory = ParserFactory(registry, cache_size=5)
        parser1 = factory.get_parser("python")
        parser2 = factory.get_parser("python")
        assert parser1 is parser2
        assert factory._parser_count == 1

    @classmethod
    def test_parser_with_config(cls, registry):
        """Test parser creation with configuration."""
        factory = ParserFactory(registry)
        config = ParserConfig(timeout_ms=1000)
        parser = factory.get_parser("python", config)
        assert isinstance(parser, Parser)
        parser2 = factory.get_parser("python", config)
        assert parser is not parser2

    @classmethod
    def test_invalid_language(cls, registry):
        """Test error for invalid language."""
        factory = ParserFactory(registry)
        with pytest.raises(LanguageNotFoundError) as exc_info:
            factory.get_parser("nonexistent")
        assert "nonexistent" in str(exc_info.value)
        assert "python" in exc_info.value.available

    @classmethod
    def test_invalid_config(cls, registry):
        """Test error for invalid configuration."""
        factory = ParserFactory(registry)
        config = ParserConfig(timeout_ms=-1)
        with pytest.raises(ParserConfigError):
            factory.get_parser("python", config)

    @classmethod
    def test_return_parser(cls, registry):
        """Test returning parser to pool."""
        factory = ParserFactory(registry, pool_size=2)
        parser1 = factory.get_parser("python")
        initial_count = factory._parser_count
        factory.return_parser("python", parser1)
        factory.get_parser("python")
        assert factory._parser_count == initial_count

    @classmethod
    def test_clear_cache(cls, registry):
        """Test cache clearing."""
        factory = ParserFactory(registry)
        parser1 = factory.get_parser("python")
        factory.get_parser("javascript")
        factory.clear_cache()
        parser3 = factory.get_parser("python")
        assert parser3 is not parser1

    @classmethod
    def test_get_stats(cls, registry):
        """Test factory statistics."""
        factory = ParserFactory(registry)
        factory.get_parser("python")
        factory.get_parser("javascript")
        stats = factory.get_stats()
        assert "total_parsers_created" in stats
        assert stats["total_parsers_created"] == 2
        assert "cache_size" in stats
        assert "pools" in stats

    @classmethod
    def test_concurrent_access(cls, registry):
        """Test thread-safe concurrent access."""
        factory = ParserFactory(registry)
        errors = []
        parsers = []

        def worker(lang, thread_id):
            try:
                for _i in range(5):
                    parser = factory.get_parser(lang)
                    parsers.append((thread_id, parser))
                    factory.return_parser(lang, parser)
                    time.sleep(0.001)
            except (OSError, IndexError, KeyError) as e:
                errors.append(e)

        threads = []
        for i in range(3):
            for lang in ["python", "javascript"]:
                t = threading.Thread(target=worker, args=(lang, i))
                threads.append(t)
                t.start()
        for t in threads:
            t.join()
        assert len(errors) == 0
        assert len(parsers) == 30

    @classmethod
    def test_parser_init_error(cls, registry):
        """Test handling of parser initialization errors."""
        factory = ParserFactory(registry)
        with patch.object(registry, "get_language") as mock_get:
            mock_get.side_effect = Exception("Failed to get language")
            with pytest.raises(ParserInitError) as exc_info:
                factory.get_parser("python")
            assert "Failed to get language" in str(exc_info.value)

    @classmethod
    def test_parser_config_application(cls, registry):
        """Test that configuration is applied to parsers."""
        factory = ParserFactory(registry)
        config = ParserConfig(timeout_ms=500)
        parser = factory.get_parser("python", config)
        assert parser.timeout_micros == 500000


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

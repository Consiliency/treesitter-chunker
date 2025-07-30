"""Tests for ParserFactory component."""

import threading
import time
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from tree_sitter import Parser

from chunker.exceptions import LanguageNotFoundError, ParserConfigError, ParserInitError
from chunker.factory import LRUCache, ParserConfig, ParserFactory, ParserPool
from chunker.registry import LanguageRegistry


class TestParserConfig:
    """Test ParserConfig validation."""

    def test_valid_config(self):
        """Test valid configuration."""
        config = ParserConfig(timeout_ms=1000)
        config.validate()  # Should not raise

        config = ParserConfig(included_ranges=[])
        config.validate()  # Should not raise

    def test_invalid_timeout(self):
        """Test invalid timeout values."""
        config = ParserConfig(timeout_ms=-1)
        with pytest.raises(ParserConfigError) as exc_info:
            config.validate()
        assert exc_info.value.config_name == "timeout_ms"
        assert exc_info.value.value == -1

        config = ParserConfig(timeout_ms="not a number")
        with pytest.raises(ParserConfigError):
            config.validate()

    def test_invalid_ranges(self):
        """Test invalid included_ranges."""
        config = ParserConfig(included_ranges="not a list")
        with pytest.raises(ParserConfigError) as exc_info:
            config.validate()
        assert exc_info.value.config_name == "included_ranges"


class TestLRUCache:
    """Test LRU cache implementation."""

    def test_basic_operations(self):
        """Test basic get/put operations."""
        cache = LRUCache(maxsize=3)

        # Add items
        parser1 = Mock(spec=Parser)
        parser2 = Mock(spec=Parser)

        cache.put("python", parser1)
        cache.put("javascript", parser2)

        # Get items
        assert cache.get("python") is parser1
        assert cache.get("javascript") is parser2
        assert cache.get("nonexistent") is None

    def test_lru_eviction(self):
        """Test LRU eviction policy."""
        cache = LRUCache(maxsize=2)

        parser1 = Mock(spec=Parser)
        parser2 = Mock(spec=Parser)
        parser3 = Mock(spec=Parser)

        cache.put("python", parser1)
        cache.put("javascript", parser2)

        # Access python to make it more recently used
        cache.get("python")

        # Add third item, should evict javascript
        cache.put("rust", parser3)

        assert cache.get("python") is parser1
        assert cache.get("rust") is parser3
        assert cache.get("javascript") is None

    def test_clear(self):
        """Test cache clearing."""
        cache = LRUCache(maxsize=3)

        cache.put("python", Mock(spec=Parser))
        cache.put("javascript", Mock(spec=Parser))

        cache.clear()

        assert cache.get("python") is None
        assert cache.get("javascript") is None

    def test_thread_safety(self):
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

    def test_pool_operations(self):
        """Test basic pool get/put."""
        pool = ParserPool("python", max_size=3)

        # Empty pool returns None
        assert pool.get() is None

        # Add parsers
        parser1 = Mock(spec=Parser)
        parser2 = Mock(spec=Parser)

        assert pool.put(parser1) is True
        assert pool.put(parser2) is True
        assert pool.size() == 2

        # Get parsers back
        assert pool.get() is parser1
        assert pool.get() is parser2
        assert pool.get() is None

    def test_pool_max_size(self):
        """Test pool size limits."""
        pool = ParserPool("python", max_size=2)

        parser1 = Mock(spec=Parser)
        parser2 = Mock(spec=Parser)
        parser3 = Mock(spec=Parser)

        assert pool.put(parser1) is True
        assert pool.put(parser2) is True
        assert pool.put(parser3) is False  # Pool full


class TestParserFactory:
    """Test ParserFactory functionality."""

    @pytest.fixture
    def registry(self):
        """Create a real registry for testing."""

        lib_path = Path(__file__).parent.parent / "build" / "my-languages.so"
        return LanguageRegistry(lib_path)

    def test_parser_creation(self, registry):
        """Test basic parser creation."""
        factory = ParserFactory(registry)

        parser = factory.get_parser("python")
        assert isinstance(parser, Parser)
        assert factory._parser_count == 1

    def test_parser_caching(self, registry):
        """Test that parsers are cached."""
        factory = ParserFactory(registry, cache_size=5)

        # Get same parser multiple times
        parser1 = factory.get_parser("python")
        parser2 = factory.get_parser("python")

        # Should be the same instance from cache
        assert parser1 is parser2
        assert factory._parser_count == 1

    def test_parser_with_config(self, registry):
        """Test parser creation with configuration."""
        factory = ParserFactory(registry)

        config = ParserConfig(timeout_ms=1000)
        parser = factory.get_parser("python", config)

        assert isinstance(parser, Parser)
        # Configured parsers shouldn't be cached
        parser2 = factory.get_parser("python", config)
        assert parser is not parser2

    def test_invalid_language(self, registry):
        """Test error for invalid language."""
        factory = ParserFactory(registry)

        with pytest.raises(LanguageNotFoundError) as exc_info:
            factory.get_parser("nonexistent")
        assert "nonexistent" in str(exc_info.value)
        assert "python" in exc_info.value.available

    def test_invalid_config(self, registry):
        """Test error for invalid configuration."""
        factory = ParserFactory(registry)

        config = ParserConfig(timeout_ms=-1)
        with pytest.raises(ParserConfigError):
            factory.get_parser("python", config)

    def test_return_parser(self, registry):
        """Test returning parser to pool."""
        factory = ParserFactory(registry, pool_size=2)

        # Get parser and return it
        parser1 = factory.get_parser("python")
        initial_count = factory._parser_count

        factory.return_parser("python", parser1)

        # Get parser again - should reuse from pool
        factory.get_parser("python")
        assert factory._parser_count == initial_count  # No new parser created

    def test_clear_cache(self, registry):
        """Test cache clearing."""
        factory = ParserFactory(registry)

        # Populate cache
        parser1 = factory.get_parser("python")
        factory.get_parser("javascript")

        factory.clear_cache()

        # Cache should be empty, but parsers still work
        parser3 = factory.get_parser("python")
        assert parser3 is not parser1  # Different instance

    def test_get_stats(self, registry):
        """Test factory statistics."""
        factory = ParserFactory(registry)

        # Create some parsers
        factory.get_parser("python")
        factory.get_parser("javascript")

        stats = factory.get_stats()

        assert "total_parsers_created" in stats
        assert stats["total_parsers_created"] == 2
        assert "cache_size" in stats
        assert "pools" in stats

    def test_concurrent_access(self, registry):
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
        assert len(parsers) == 30  # 3 threads * 2 languages * 5 iterations

    def test_parser_init_error(self, registry):
        """Test handling of parser initialization errors."""
        factory = ParserFactory(registry)

        # Try to create parser for language with issues
        # Since all our languages work, we'll mock the registry method
        with patch.object(registry, "get_language") as mock_get:
            mock_get.side_effect = Exception("Failed to get language")

            with pytest.raises(ParserInitError) as exc_info:
                factory.get_parser("python")
            assert "Failed to get language" in str(exc_info.value)

    def test_parser_config_application(self, registry):
        """Test that configuration is applied to parsers."""
        factory = ParserFactory(registry)

        config = ParserConfig(timeout_ms=500)
        parser = factory.get_parser("python", config)

        # Check that timeout was set (in microseconds)
        assert parser.timeout_micros == 500000


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

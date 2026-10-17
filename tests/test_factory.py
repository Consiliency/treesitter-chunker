"""Tests for ParserFactory component."""

import threading
import time
import types
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from tree_sitter import Parser

from chunker._internal.factory import LRUCache, ParserConfig, ParserFactory, ParserPool
from chunker._internal.registry import LanguageRegistry
from chunker.exceptions import LanguageNotFoundError, ParserConfigError, ParserInitError
from tests.test_language_pack import _isolate_default_492


class TestParserConfig:
    """Test ParserConfig validation."""

    def test_valid_config(self):
        """Test valid configuration."""
        config = ParserConfig()
        config.validate()
        config = ParserConfig(included_ranges=[])
        config.validate()

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
        parser1 = Mock(spec=Parser)
        parser2 = Mock(spec=Parser)
        cache.put("python", parser1)
        cache.put("javascript", parser2)
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
        cache.get("python")
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
        assert pool.get() is None
        parser1 = Mock(spec=Parser)
        parser2 = Mock(spec=Parser)
        assert pool.put(parser1) is True
        assert pool.put(parser2) is True
        assert pool.size() == 2
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
        assert pool.put(parser3) is False


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
        parser1 = factory.get_parser("python")
        parser2 = factory.get_parser("python")
        assert parser1 is parser2
        assert factory._parser_count == 1

    def test_parser_with_config(self, registry):
        """Test parser creation with configuration."""
        factory = ParserFactory(registry)
        config = ParserConfig()
        parser = factory.get_parser("python", config)
        assert isinstance(parser, Parser)
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
        parser1 = factory.get_parser("python")
        initial_count = factory._parser_count
        factory.return_parser("python", parser1)
        factory.get_parser("python")
        assert factory._parser_count == initial_count

    def test_clear_cache(self, registry):
        """Test cache clearing."""
        factory = ParserFactory(registry)
        parser1 = factory.get_parser("python")
        factory.get_parser("javascript")
        factory.clear_cache()
        parser3 = factory.get_parser("python")
        assert parser3 is not parser1

    def test_get_stats(self, registry):
        """Test factory statistics."""
        factory = ParserFactory(registry)
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
        assert len(parsers) == 30

    def test_parser_init_error(self, registry):
        """Test handling of parser initialization errors."""
        factory = ParserFactory(registry)
        with patch.object(registry, "get_language") as mock_get:
            mock_get.side_effect = Exception("Failed to get language")
            with pytest.raises(ParserInitError) as exc_info:
                factory.get_parser("python")
            assert "Failed to get language" in str(exc_info.value)

    @pytest.mark.parametrize("language", ["python", "javascript"])
    def test_492_incompatible_custom_never_uses_pack(self, monkeypatch, language):
        import tree_sitter_language_pack as pack

        registry = Mock(spec=LanguageRegistry)
        registry.has_language.return_value = True
        registry.get_language.return_value = object()
        monkeypatch.setattr(
            pack,
            "get_parser",
            lambda *args, **kwargs: pytest.fail("pack parser used"),
        )

        with pytest.raises(ParserInitError, match=language):
            ParserFactory(registry).get_parser(language)

    @pytest.mark.parametrize("language", ["python", "javascript"])
    @pytest.mark.parametrize(
        "failure",
        ["module", "native", "missing-capsule", "invalid-capsule", "abi"],
    )
    def test_492_required_grammar_failure_never_uses_pack_or_build(
        self, monkeypatch, tmp_path, language, failure
    ):
        import tree_sitter
        import tree_sitter_language_pack as pack

        from chunker import parser as parser_module
        from chunker._internal import language_pack

        _isolate_default_492(monkeypatch, tmp_path)
        real_module = language_pack.import_module(f"tree_sitter_{language}")
        if failure == "module":
            injected = ImportError("missing official module")
        elif failure == "native":
            injected = OSError("official native load failed")
        elif failure == "missing-capsule":
            injected = types.SimpleNamespace()
        elif failure == "invalid-capsule":
            injected = types.SimpleNamespace(language=object)
        else:
            injected = real_module
            monkeypatch.setattr(
                tree_sitter,
                "Parser",
                lambda language: (_ for _ in ()).throw(
                    ValueError("official grammar ABI rejected")
                ),
            )
        if isinstance(injected, Exception):
            monkeypatch.setattr(
                language_pack,
                "import_module",
                lambda name: (_ for _ in ()).throw(injected),
            )
        else:
            monkeypatch.setattr(language_pack, "import_module", lambda name: injected)
        monkeypatch.setattr(
            pack,
            "get_language",
            lambda *args, **kwargs: pytest.fail("pack language used"),
        )
        monkeypatch.setattr(
            pack,
            "get_parser",
            lambda *args, **kwargs: pytest.fail("pack parser used"),
        )
        manager = Mock(side_effect=AssertionError("automatic grammar build used"))
        monkeypatch.setattr(parser_module, "TreeSitterGrammarManager", manager)

        with pytest.raises(ParserInitError, match=f"tree-sitter-{language}==0.25.0"):
            parser_module.get_parser(language)
        manager.assert_not_called()

    def test_parser_config_application(self, registry):
        """Test that configuration is applied to parsers."""
        config = ParserConfig(timeout_ms=500)

        parser_with_setter = Mock()
        ParserFactory._apply_config(parser_with_setter, config)
        parser_with_setter.set_timeout_micros.assert_called_once_with(500000)

        class ParserWithProperty:
            timeout_micros = None

        parser_with_property = ParserWithProperty()
        parser_with_property.timeout_micros = None
        ParserFactory._apply_config(parser_with_property, config)
        assert parser_with_property.timeout_micros == 500000

        class ParserWithoutTimeoutApi:
            pass

        parser_without_timeout_api = ParserWithoutTimeoutApi()
        with pytest.raises(ParserConfigError, match="does not support timeout_ms"):
            ParserFactory._apply_config(parser_without_timeout_api, config)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

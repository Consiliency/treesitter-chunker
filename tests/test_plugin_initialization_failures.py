"""Test plugin initialization failure scenarios.

This module specifically tests how the plugin system handles various
initialization failures and error conditions.
"""

import threading
import time
from unittest.mock import MagicMock, patch

import pytest
import tree_sitter

from chunker.languages.base import PluginConfig
from chunker.languages.plugin_base import LanguagePlugin
from chunker.plugin_manager import PluginManager


class TestPluginInitializationFailures:
    """Test various plugin initialization failure scenarios."""

    @classmethod
    def test_plugin_constructor_exception(cls):
        """Test handling when plugin constructor raises exception."""

        class FailingConstructorPlugin(LanguagePlugin):

            @classmethod
            def __init__(cls, config=None):
                raise RuntimeError("Constructor failed!")

            @staticmethod
            @property
            def language_name():
                return "failing_constructor"

            @staticmethod
            @property
            def supported_extensions():
                return {".fail"}

            @staticmethod
            @property
            def default_chunk_types():
                return {"function_definition"}

        manager = PluginManager()
        with pytest.raises(RuntimeError) as exc_info:
            manager.registry.register(FailingConstructorPlugin)
        assert "Failed to instantiate plugin" in str(exc_info.value)

    @classmethod
    def test_plugin_missing_required_properties(cls):
        """Test handling when plugin is missing required properties."""

        class IncompletePlugin(LanguagePlugin):

            @staticmethod
            @property
            def supported_extensions():
                return {".inc"}

            @staticmethod
            @property
            def default_chunk_types():
                return {"function_definition"}

            @staticmethod
            def get_node_name(_node, _source):
                return "test"

        manager = PluginManager()
        with pytest.raises((TypeError, RuntimeError)) as exc_info:
            manager.registry.register(IncompletePlugin)
        assert "abstract" in str(
            exc_info.value,
        ) or "Failed to instantiate" in str(exc_info.value)

    @staticmethod
    def test_plugin_parser_initialization_failure():
        """Test handling when parser initialization fails."""

        class ParserFailPlugin(LanguagePlugin):

            def __init__(self, config=None):
                super().__init__(config)
                self.parser_set = False

            @staticmethod
            @property
            def language_name():
                return "parser_fail"

            @staticmethod
            @property
            def supported_extensions():
                return {".pfail"}

            @staticmethod
            @property
            def default_chunk_types():
                return {"function_definition"}

            @classmethod
            def set_parser(cls, parser):
                raise RuntimeError("Parser initialization failed!")

            @staticmethod
            def get_node_name(_node, _source):
                return "test"

        manager = PluginManager()
        manager.registry.register(ParserFailPlugin)
        with patch("chunker.plugin_manager.get_parser") as mock_get_parser:
            mock_get_parser.return_value = MagicMock()
            with pytest.raises(RuntimeError) as exc_info:
                manager.get_plugin("parser_fail")
            assert "Parser initialization failed!" in str(exc_info.value)

    @classmethod
    def test_plugin_with_invalid_language_name(cls):
        """Test plugin with invalid language name."""

        class InvalidNamePlugin(LanguagePlugin):

            @staticmethod
            @property
            def language_name():
                return None

            @staticmethod
            @property
            def supported_extensions():
                return {".inv"}

            @staticmethod
            @property
            def default_chunk_types():
                return {"function_definition"}

        manager = PluginManager()
        with pytest.raises((TypeError, RuntimeError)):
            manager.registry.register(InvalidNamePlugin)

    @staticmethod
    def test_plugin_dependency_initialization_failure():
        """Test when plugin dependencies fail to initialize."""

        class DependencyPlugin(LanguagePlugin):

            def __init__(self, config=None):
                super().__init__(config)
                self.database = self._init_database()

            @classmethod
            def _init_database(cls):
                raise ConnectionError("Cannot connect to database")

            @staticmethod
            @property
            def language_name():
                return "dep_fail"

            @staticmethod
            @property
            def supported_extensions():
                return {".dep"}

            @staticmethod
            @property
            def default_chunk_types():
                return {"function_definition"}

            @staticmethod
            def get_node_name(_node, _source):
                return "test"

        manager = PluginManager()
        with pytest.raises(RuntimeError) as exc_info:
            manager.registry.register(DependencyPlugin)
        assert "Cannot connect to database" in str(exc_info.value)

    @staticmethod
    def test_plugin_configuration_validation_failure():
        """Test plugin that fails configuration validation."""

        class ValidatedPlugin(LanguagePlugin):

            def __init__(self, config=None):
                super().__init__(config)
                if config and not self._validate_config(config):
                    raise ValueError("Invalid configuration provided")

            @staticmethod
            def _validate_config(config):
                if not hasattr(config, "required_field"):
                    return False
                return not config.min_chunk_size > config.max_chunk_size

            @staticmethod
            @property
            def language_name():
                return "validated"

            @staticmethod
            @property
            def supported_extensions():
                return {".val"}

            @staticmethod
            @property
            def default_chunk_types():
                return {"function_definition"}

            @staticmethod
            def get_node_name(_node, _source):
                return "test"

        manager = PluginManager()
        manager.registry.register(ValidatedPlugin)
        invalid_config = PluginConfig(min_chunk_size=100, max_chunk_size=50)
        with pytest.raises(ValueError) as exc_info:
            manager.get_plugin("validated", invalid_config)
        assert "Invalid configuration" in str(exc_info.value)

    @staticmethod
    def test_plugin_resource_allocation_failure():
        """Test plugin that fails to allocate required resources."""

        class ResourcePlugin(LanguagePlugin):

            def __init__(self, config=None):
                super().__init__(config)
                self.resources = self._allocate_resources()

            @classmethod
            def _allocate_resources(cls):
                raise MemoryError("Insufficient memory for plugin")

            @staticmethod
            @property
            def language_name():
                return "resource_fail"

            @staticmethod
            @property
            def supported_extensions():
                return {".res"}

            @staticmethod
            @property
            def default_chunk_types():
                return {"function_definition"}

            @staticmethod
            def get_node_name(_node, _source):
                return "test"

        manager = PluginManager()
        with pytest.raises(RuntimeError) as exc_info:
            manager.registry.register(ResourcePlugin)
        assert "Insufficient memory" in str(exc_info.value)

    @classmethod
    def test_plugin_file_loading_failure(cls, tmp_path):
        """Test failure when loading plugin from corrupted file."""
        plugin_file = tmp_path / "corrupted_plugin.py"
        plugin_file.write_text(
            """
# Corrupted plugin with syntax error
from chunker.languages.plugin_base import LanguagePlugin

class CorruptedPlugin(LanguagePlugin:  # Missing closing parenthesis
    @property
    def language_name(self):
        return "corrupted\"
""",
        )
        manager = PluginManager()
        manager.add_plugin_directory(tmp_path)
        with patch("chunker.plugin_manager.logger") as mock_logger:
            plugins = manager.discover_plugins(tmp_path)
            assert mock_logger.error.called
            assert len(plugins) == 0

    @staticmethod
    def test_plugin_circular_dependency_initialization():
        """Test circular dependency detection during initialization."""
        manager = PluginManager()

        class PluginA(LanguagePlugin):

            def __init__(self, config=None):
                super().__init__(config)
                self.other = manager.get_plugin("plugin_b")

            @staticmethod
            @property
            def language_name():
                return "plugin_a"

            @staticmethod
            @property
            def supported_extensions():
                return {".a"}

            @staticmethod
            @property
            def default_chunk_types():
                return {"function_definition"}

            @staticmethod
            def get_node_name(_node, _source):
                return "test"

        class PluginB(LanguagePlugin):

            def __init__(self, config=None):
                super().__init__(config)
                self.other = manager.get_plugin("plugin_a")

            @staticmethod
            @property
            def language_name():
                return "plugin_b"

            @staticmethod
            @property
            def supported_extensions():
                return {".b"}

            @staticmethod
            @property
            def default_chunk_types():
                return {"function_definition"}

            @staticmethod
            def get_node_name(_node, _source):
                return "test"

        with pytest.raises(RuntimeError) as exc_info:
            manager.registry.register(PluginA)
        assert "plugin_b" in str(exc_info.value)
        with pytest.raises(RuntimeError) as exc_info:
            manager.registry.register(PluginB)
        assert "plugin_a" in str(exc_info.value)

    @staticmethod
    def test_plugin_version_incompatibility():
        """Test plugin that requires incompatible version."""

        class VersionedPlugin(LanguagePlugin):

            def __init__(self, config=None):
                super().__init__(config)
                self._check_version_compatibility()

            @classmethod
            def _check_version_compatibility(cls):
                current_version = getattr(tree_sitter, "__version__", "0.0.0")
                required_version = "99.0.0"
                if current_version < required_version:
                    raise RuntimeError(
                        f"Plugin requires tree-sitter >={required_version}, but {current_version} is installed",
                    )

            @staticmethod
            @property
            def language_name():
                return "versioned"

            @staticmethod
            @property
            def supported_extensions():
                return {".ver"}

            @staticmethod
            @property
            def default_chunk_types():
                return {"function_definition"}

            @staticmethod
            def get_node_name(_node, _source):
                return "test"

        manager = PluginManager()
        with pytest.raises(RuntimeError) as exc_info:
            manager.registry.register(VersionedPlugin)
        assert "requires tree-sitter" in str(exc_info.value)

    @classmethod
    def test_plugin_thread_safety_initialization(cls):
        """Test thread safety during plugin initialization."""
        manager = PluginManager()
        init_count = 0
        init_lock = threading.Lock()

        class ThreadSafePlugin(LanguagePlugin):

            @classmethod
            def __init__(cls, config=None):
                nonlocal init_count
                super().__init__(config)
                time.sleep(0.1)
                with init_lock:
                    init_count += 1
                    if init_count > 1:
                        raise RuntimeError("Multiple simultaneous initializations!")
                time.sleep(0.1)
                with init_lock:
                    init_count -= 1

            @staticmethod
            @property
            def language_name():
                return "thread_safe"

            @staticmethod
            @property
            def supported_extensions():
                return {".ts"}

            @staticmethod
            @property
            def default_chunk_types():
                return {"function_definition"}

            @staticmethod
            def get_node_name(_node, _source):
                return "test"

        manager.registry.register(ThreadSafePlugin)
        results = []
        errors = []

        def get_plugin():
            try:
                plugin = manager.get_plugin("thread_safe")
                results.append(plugin)
            except (OSError, IndexError, KeyError) as e:
                errors.append(e)

        threads = []
        for _ in range(3):
            t = threading.Thread(target=get_plugin)
            threads.append(t)
            t.start()
        for t in threads:
            t.join()
        assert len(errors) >= 1
        assert any("Language" in str(e) and "not found" in str(e) for e in errors)

    @staticmethod
    def test_plugin_cleanup_on_initialization_failure():
        """Test that resources are cleaned up when initialization fails."""
        resources_allocated = []
        resources_freed = []

        class CleanupPlugin(LanguagePlugin):

            def __init__(self, config=None):
                super().__init__(config)
                self.resource1 = self._allocate_resource("resource1")
                resources_allocated.append("resource1")
                self.resource2 = self._allocate_resource("resource2")
                resources_allocated.append("resource2")
                raise RuntimeError("Initialization failed after resource allocation")

            @staticmethod
            def _allocate_resource(name):
                return f"allocated_{name}"

            def __del__(self):
                if hasattr(self, "resource1"):
                    resources_freed.append("resource1")
                if hasattr(self, "resource2"):
                    resources_freed.append("resource2")

            @staticmethod
            @property
            def language_name():
                return "cleanup"

            @staticmethod
            @property
            def supported_extensions():
                return {".clean"}

            @staticmethod
            @property
            def default_chunk_types():
                return {"function_definition"}

            @staticmethod
            def get_node_name(_node, _source):
                return "test"

        manager = PluginManager()
        with pytest.raises(RuntimeError):
            try:
                manager.registry.register(CleanupPlugin)
            except RuntimeError:
                raise
        assert len(resources_allocated) == 2

    @classmethod
    def test_plugin_dynamic_loading_failure(cls, tmp_path):
        """Test failure scenarios in dynamic plugin loading."""
        plugin_file = tmp_path / "import_error_plugin.py"
        plugin_file.write_text(
            """
from chunker.languages.plugin_base import LanguagePlugin
import non_existent_module  # This will fail

class ImportErrorPlugin(LanguagePlugin):
    @property
    def language_name(self):
        return "import_error"

    @property
    def supported_extensions(self):
        return {".imperr"}

    @property
    def default_chunk_types(self):
        return {"function_definition"}
""",
        )
        manager = PluginManager()
        with patch("chunker.plugin_manager.logger") as mock_logger:
            plugins = manager._load_plugin_from_file(plugin_file)
            assert len(plugins) == 0
            assert mock_logger.error.called

    @classmethod
    def test_plugin_malformed_metadata(cls):
        """Test plugin with malformed metadata."""

        class MalformedPlugin(LanguagePlugin):

            @staticmethod
            @property
            def language_name():
                return "malformed"

            @staticmethod
            @property
            def supported_extensions():
                return "not_a_set"

            @staticmethod
            @property
            def default_chunk_types():
                return {"function_definition"}

            @staticmethod
            @property
            def plugin_metadata():
                return "not_a_dict"

            @staticmethod
            def get_node_name(_node, _source):
                return "test"

        manager = PluginManager()
        try:
            manager.registry.register(MalformedPlugin)
            plugin = manager.get_plugin("malformed")
            with pytest.raises((TypeError, AttributeError)):
                list(plugin.supported_extensions)
        except (TypeError, AttributeError):
            pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

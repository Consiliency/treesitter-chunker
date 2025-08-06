"""Comprehensive tests for custom plugin directory scanning.

This module tests various scenarios for discovering and loading plugins
from custom directories, including edge cases and error conditions.
"""

import os
import pathlib
from unittest.mock import patch

import pytest

from chunker.plugin_manager import PluginManager


class TestCustomPluginDirectoryScanning:
    """Test comprehensive plugin directory scanning scenarios."""

    @classmethod
    def test_single_custom_directory(cls, tmp_path):
        """Test scanning a single custom plugin directory."""
        plugin_dir = tmp_path / "my_plugins"
        plugin_dir.mkdir()
        plugins_created = []
        plugin1_file = plugin_dir / "simple_plugin.py"
        plugin1_file.write_text(
            """
from chunker.languages.plugin_base import LanguagePlugin

class SimplePlugin(LanguagePlugin):
    @property
    def language_name(self):
        return "simple"

    @property
    def supported_extensions(self):
        return {".simp"}

    @property
    def default_chunk_types(self):
        return {"function", "class"}

    @property
    def plugin_metadata(self):
        return {"name": "simple-plugin", "version": "1.0.0"}

    def get_node_name(self, node, source):
        return "test\"
""",
        )
        plugins_created.append("SimplePlugin")
        plugin2_file = plugin_dir / "complex_plugin.py"
        plugin2_file.write_text(
            """
import json
import re
from chunker.languages.plugin_base import LanguagePlugin

class ComplexPlugin(LanguagePlugin):
    def __init__(self, config=None):
        super().__init__(config)
        self.patterns = [re.compile(r'\\bfunction\\b'), re.compile(r'\\bclass\\b')]

    @property
    def language_name(self):
        return "complex"

    @property
    def supported_extensions(self):
        return {".comp", ".cmplx"}

    @property
    def default_chunk_types(self):
        return {"function", "class", "method"}

    @property
    def plugin_metadata(self):
        return {"name": "complex-plugin", "version": "2.0.0", "author": "test"}

    def get_node_name(self, node, source):
        return "test\"
""",
        )
        plugins_created.append("ComplexPlugin")
        manager = PluginManager()
        manager.add_plugin_directory(plugin_dir)
        discovered = manager.discover_plugins(plugin_dir)
        discovered_names = {p.__name__ for p in discovered}
        print(f"Discovered plugins: {discovered_names}")
        for expected in plugins_created:
            assert expected in discovered_names
        loaded_count = manager.load_plugins_from_directory(plugin_dir)
        print(f"Loaded {loaded_count} plugins")
        assert loaded_count >= 1
        languages = manager.registry.list_languages()
        print(f"Available languages: {languages}")
        assert len(languages) >= 1
        assert "simple" in languages or "complex" in languages
        if "simple" in languages:
            assert manager.registry._plugins.get("simple") is not None
        if "complex" in languages:
            assert manager.registry._plugins.get("complex") is not None

    @classmethod
    def test_multiple_plugin_directories(cls, tmp_path):
        """Test scanning multiple custom plugin directories."""
        dir1 = tmp_path / "plugins_set1"
        dir2 = tmp_path / "plugins_set2"
        dir3 = tmp_path / "plugins_set3"
        for d in [dir1, dir2, dir3]:
            d.mkdir()
        plugin_template = """
from chunker.languages.plugin_base import LanguagePlugin

class {class_name}(LanguagePlugin):
    @property
    def language_name(self):
        return "{lang_name}"

    @property
    def supported_extensions(self):
        return {{".{ext}"}}

    @property
    def default_chunk_types(self):
        return {{"function"}}

    @property
    def plugin_metadata(self):
        return {{"name": "{lang_name}-plugin", "version": "1.0.0"}}

    def get_node_name(self, node, source):
        return "test\"
"""
        (dir1 / "lang1_plugin.py").write_text(
            plugin_template.format(
                class_name="Lang1Plugin",
                lang_name="lang1",
                ext="l1",
            ),
        )
        (dir1 / "lang2_plugin.py").write_text(
            plugin_template.format(
                class_name="Lang2Plugin",
                lang_name="lang2",
                ext="l2",
            ),
        )
        (dir2 / "lang3_plugin.py").write_text(
            plugin_template.format(
                class_name="Lang3Plugin",
                lang_name="lang3",
                ext="l3",
            ),
        )
        (dir3 / "lang4_plugin.py").write_text(
            plugin_template.format(
                class_name="Lang4Plugin",
                lang_name="lang4",
                ext="l4",
            ),
        )
        (dir3 / "lang5_plugin.py").write_text(
            plugin_template.format(
                class_name="Lang5Plugin",
                lang_name="lang5",
                ext="l5",
            ),
        )
        manager = PluginManager()
        for d in [dir1, dir2, dir3]:
            manager.add_plugin_directory(d)
        total_loaded = 0
        for d in [dir1, dir2, dir3]:
            loaded = manager.load_plugins_from_directory(d)
            total_loaded += loaded
        assert total_loaded >= 5
        languages = manager.registry.list_languages()
        for i in range(1, 6):
            assert f"lang{i}" in languages

    @classmethod
    def test_nested_directory_structure(cls, tmp_path):
        """Test scanning nested plugin directory structures."""
        root_dir = tmp_path / "plugin_root"
        sub_dir1 = root_dir / "category1"
        sub_dir2 = root_dir / "category2"
        deep_dir = sub_dir1 / "subcategory"
        for d in [root_dir, sub_dir1, sub_dir2, deep_dir]:
            d.mkdir(parents=True, exist_ok=True)
        for d in [root_dir, sub_dir1, sub_dir2, deep_dir]:
            (d / "__init__.py").write_text("")
        plugin_template = """
from chunker.languages.plugin_base import LanguagePlugin

class {class_name}(LanguagePlugin):
    @property
    def language_name(self):
        return "{name}"

    @property
    def supported_extensions(self):
        return {{".{ext}"}}

    @property
    def default_chunk_types(self):
        return {{"function"}}

    @property
    def plugin_metadata(self):
        return {{"name": "{name}-plugin", "version": "1.0.0", "location": "{location}"}}

    def get_node_name(self, node, source):
        return "test\"
"""
        (root_dir / "root_plugin.py").write_text(
            plugin_template.format(
                class_name="RootPlugin",
                name="root",
                ext="root",
                location="root",
            ),
        )
        (sub_dir1 / "cat1_plugin.py").write_text(
            plugin_template.format(
                class_name="Cat1Plugin",
                name="cat1",
                ext="c1",
                location="category1",
            ),
        )
        (sub_dir2 / "cat2_plugin.py").write_text(
            plugin_template.format(
                class_name="Cat2Plugin",
                name="cat2",
                ext="c2",
                location="category2",
            ),
        )
        (deep_dir / "deep_plugin.py").write_text(
            plugin_template.format(
                class_name="DeepPlugin",
                name="deep",
                ext="deep",
                location="subcategory",
            ),
        )
        manager = PluginManager()
        manager.add_plugin_directory(root_dir)
        root_plugins = manager.discover_plugins(root_dir)
        assert len(root_plugins) >= 1
        sub1_plugins = manager.discover_plugins(sub_dir1)
        assert len(sub1_plugins) >= 1
        sub2_plugins = manager.discover_plugins(sub_dir2)
        assert len(sub2_plugins) >= 1
        deep_plugins = manager.discover_plugins(deep_dir)
        assert len(deep_plugins) >= 1
        for d in [root_dir, sub_dir1, sub_dir2, deep_dir]:
            manager.load_plugins_from_directory(d)
        languages = manager.registry.list_languages()
        assert "root" in languages
        assert "cat1" in languages
        assert "cat2" in languages
        assert "deep" in languages

    @classmethod
    def test_directory_with_invalid_plugins(cls, tmp_path):
        """Test handling directories with invalid plugin files."""
        plugin_dir = tmp_path / "mixed_plugins"
        plugin_dir.mkdir()
        valid_plugin = plugin_dir / "valid_plugin.py"
        valid_plugin.write_text(
            """
from chunker.languages.plugin_base import LanguagePlugin

class ValidPlugin(LanguagePlugin):
    @property
    def language_name(self):
        return "valid"

    @property
    def supported_extensions(self):
        return {".valid"}

    @property
    def default_chunk_types(self):
        return {"function"}

    @property
    def plugin_metadata(self):
        return {"name": "valid-plugin", "version": "1.0.0"}

    def get_node_name(self, node, source):
        return "test\"
""",
        )
        syntax_error_file = plugin_dir / "syntax_error.py"
        syntax_error_file.write_text(
            """
from chunker.languages.plugin_base import LanguagePlugin

class SyntaxErrorPlugin(LanguagePlugin  # Missing closing parenthesis
    @property
    def language_name(self):
        return "syntax_error\"
""",
        )
        import_error_file = plugin_dir / "import_error.py"
        import_error_file.write_text(
            """
from chunker.languages.plugin_base import LanguagePlugin
import non_existent_module

class ImportErrorPlugin(LanguagePlugin):
    @property
    def language_name(self):
        return "import_error\"
""",
        )
        not_plugin_file = plugin_dir / "not_plugin.py"
        not_plugin_file.write_text(
            """
# Just a regular Python file
def hello():
    return "world\"
""",
        )
        wrong_base_file = plugin_dir / "wrong_base.py"
        wrong_base_file.write_text(
            """
class WrongBasePlugin:  # Not inheriting from LanguagePlugin
    @property
    def language_name(self):
        return "wrong_base\"
""",
        )
        manager = PluginManager()
        manager.add_plugin_directory(plugin_dir)
        with patch("chunker.plugin_manager.logger") as mock_logger:
            plugins = manager.discover_plugins(plugin_dir)
            plugin_names = {p.__name__ for p in plugins}
            assert "ValidPlugin" in plugin_names
            assert "SyntaxErrorPlugin" not in plugin_names
            assert "ImportErrorPlugin" not in plugin_names
            assert "WrongBasePlugin" not in plugin_names
            assert mock_logger.error.call_count >= 2

    @classmethod
    def test_directory_permissions_and_access(cls, tmp_path):
        """Test handling of directory permission issues."""
        readable_dir = tmp_path / "readable_plugins"
        readable_dir.mkdir()
        plugin_file = readable_dir / "readable_plugin.py"
        plugin_file.write_text(
            """
from chunker.languages.plugin_base import LanguagePlugin

class ReadablePlugin(LanguagePlugin):
    @property
    def language_name(self):
        return "readable"

    @property
    def supported_extensions(self):
        return {".read"}

    @property
    def default_chunk_types(self):
        return {"function"}

    @property
    def plugin_metadata(self):
        return {"name": "readable-plugin", "version": "1.0.0"}

    def get_node_name(self, node, source):
        return "test\"
""",
        )
        manager = PluginManager()
        non_existent = tmp_path / "non_existent"
        with patch("chunker.plugin_manager.logger") as mock_logger:
            manager.add_plugin_directory(non_existent)
            assert mock_logger.warning.called
            plugins = manager.discover_plugins(non_existent)
            assert len(plugins) == 0
        file_path = tmp_path / "not_a_directory.txt"
        file_path.write_text("I'm a file, not a directory")
        with patch("chunker.plugin_manager.logger") as mock_logger:
            manager.add_plugin_directory(file_path)
            assert mock_logger.warning.called
        manager.add_plugin_directory(readable_dir)
        plugins = manager.discover_plugins(readable_dir)
        assert len(plugins) >= 1
        if os.name != "nt":
            unreadable_dir = tmp_path / "unreadable_plugins"
            unreadable_dir.mkdir()
            pathlib.Path(unreadable_dir).chmod(0)
            try:
                with patch("chunker.plugin_manager.logger") as mock_logger:
                    plugins = manager.discover_plugins(unreadable_dir)
                    assert len(plugins) == 0
            finally:
                pathlib.Path(unreadable_dir).chmod(0o755)

    @classmethod
    def test_plugin_file_patterns(cls, tmp_path):
        """Test different plugin file naming patterns."""
        plugin_dir = tmp_path / "various_plugins"
        plugin_dir.mkdir()
        plugin_template = """
from chunker.languages.plugin_base import LanguagePlugin

class {class_name}(LanguagePlugin):
    @property
    def language_name(self):
        return "{name}"

    @property
    def supported_extensions(self):
        return {{".{ext}"}}

    @property
    def default_chunk_types(self):
        return {{"function"}}

    @property
    def plugin_metadata(self):
        return {{"name": "{name}-plugin", "version": "1.0.0"}}

    def get_node_name(self, node, source):
        return "test\"
"""
        patterns = [
            ("plugin_lang1.py", "PluginLang1", "lang1", "l1"),
            ("lang2_plugin.py", "Lang2Plugin", "lang2", "l2"),
            ("my_custom_lang.py", "MyCustomLang", "customlang", "cl"),
            ("advanced_lang_support.py", "AdvancedLangSupport", "advlang", "al"),
            ("__test_plugin.py", "TestPlugin", "testlang", "tl"),
        ]
        for filename, class_name, lang_name, ext in patterns:
            if not filename.startswith("__"):
                file_path = plugin_dir / filename
                file_path.write_text(
                    plugin_template.format(
                        class_name=class_name,
                        name=lang_name,
                        ext=ext,
                    ),
                )
        manager = PluginManager()
        plugins = manager.discover_plugins(plugin_dir)
        assert len(plugins) >= 4
        manager.load_plugins_from_directory(plugin_dir)
        languages = manager.registry.list_languages()
        expected_langs = ["lang1", "lang2", "customlang", "advlang"]
        loaded_langs = [lang for lang in expected_langs if lang in languages]
        print(f"Loaded languages: {loaded_langs} out of {expected_langs}")
        assert len(loaded_langs) >= 2

    @classmethod
    def test_plugin_hot_directory_scanning(cls, tmp_path):
        """Test adding/removing plugins from directory while running."""
        plugin_dir = tmp_path / "hot_plugins"
        plugin_dir.mkdir()
        manager = PluginManager()
        manager.add_plugin_directory(plugin_dir)
        plugins = manager.discover_plugins(plugin_dir)
        assert len(plugins) == 0
        plugin1_file = plugin_dir / "hot_plugin1.py"
        plugin1_file.write_text(
            """
from chunker.languages.plugin_base import LanguagePlugin

class HotPlugin1(LanguagePlugin):
    @property
    def language_name(self):
        return "hot1"

    @property
    def supported_extensions(self):
        return {".hot1"}

    @property
    def default_chunk_types(self):
        return {"function"}

    @property
    def plugin_metadata(self):
        return {"name": "hot1-plugin", "version": "1.0.0"}

    def get_node_name(self, node, source):
        return "test\"
""",
        )
        plugins = manager.discover_plugins(plugin_dir)
        assert len(plugins) == 1
        plugin2_file = plugin_dir / "hot_plugin2.py"
        plugin2_file.write_text(
            """
from chunker.languages.plugin_base import LanguagePlugin

class HotPlugin2(LanguagePlugin):
    @property
    def language_name(self):
        return "hot2"

    @property
    def supported_extensions(self):
        return {".hot2"}

    @property
    def default_chunk_types(self):
        return {"function"}

    @property
    def plugin_metadata(self):
        return {"name": "hot2-plugin", "version": "1.0.0"}

    def get_node_name(self, node, source):
        return "test\"
""",
        )
        plugins = manager.discover_plugins(plugin_dir)
        assert len(plugins) == 2
        plugin1_file.unlink()
        plugins = manager.discover_plugins(plugin_dir)
        assert len(plugins) == 1
        assert plugins[0].__name__ == "HotPlugin2"

    @classmethod
    def test_symlink_directory_handling(cls, tmp_path):
        """Test handling of symlinked directories."""
        if os.name == "nt":
            try:
                test_link = tmp_path / "test_link"
                test_target = tmp_path / "test_target"
                test_target.mkdir()
                test_link.symlink_to(test_target)
                test_link.unlink()
                test_target.rmdir()
            except OSError:
                pytest.skip("Symlinks not supported on this Windows system")
        actual_dir = tmp_path / "actual_plugins"
        actual_dir.mkdir()
        plugin_file = actual_dir / "symlinked_plugin.py"
        plugin_file.write_text(
            """
from chunker.languages.plugin_base import LanguagePlugin

class SymlinkedPlugin(LanguagePlugin):
    @property
    def language_name(self):
        return "symlinked"

    @property
    def supported_extensions(self):
        return {".sym"}

    @property
    def default_chunk_types(self):
        return {"function"}

    @property
    def plugin_metadata(self):
        return {"name": "symlinked-plugin", "version": "1.0.0"}

    def get_node_name(self, node, source):
        return "test\"
""",
        )
        symlink_dir = tmp_path / "plugin_link"
        symlink_dir.symlink_to(actual_dir)
        manager = PluginManager()
        manager.add_plugin_directory(symlink_dir)
        plugins = manager.discover_plugins(symlink_dir)
        assert len(plugins) == 1
        loaded = manager.load_plugins_from_directory(symlink_dir)
        assert loaded >= 1
        assert "symlinked" in manager.registry.list_languages()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

#!/usr/bin/env python3
"""
Tests for the plugin architecture components.
"""
import tempfile
from pathlib import Path

import pytest

from chunker import PluginConfig, PluginManager, get_plugin_manager
from chunker.chunker_config import ChunkerConfig
from chunker.languages import JavaScriptPlugin, PythonPlugin, RustPlugin


def test_plugin_registry():
    """Test the plugin registry functionality."""
    manager = PluginManager()

    # Register a plugin
    manager.registry.register(PythonPlugin)

    # Check it's registered
    assert "python" in manager.registry.list_languages()

    # Get plugin instance
    plugin = manager.registry.get_plugin("python")
    assert isinstance(plugin, PythonPlugin)
    assert plugin.language_name == "python"

    # Check extensions
    extensions = manager.registry.list_extensions()
    assert extensions[".py"] == "python"
    assert extensions[".pyi"] == "python"


def test_plugin_discovery():
    """Test plugin discovery from directories."""
    manager = PluginManager()

    # Discover built-in plugins
    builtin_dir = Path(__file__).parent.parent / "chunker" / "languages"
    plugins = manager.discover_plugins(builtin_dir)

    # Should find at least Python, Rust, and JavaScript plugins
    plugin_names = {p.__name__ for p in plugins}
    assert "PythonPlugin" in plugin_names
    assert "RustPlugin" in plugin_names
    assert "JavaScriptPlugin" in plugin_names


def test_plugin_config():
    """Test plugin configuration."""
    config = PluginConfig(
        enabled=True,
        chunk_types={"function_definition", "class_definition"},
        min_chunk_size=5,
        max_chunk_size=100,
        custom_options={"include_docstrings": True},
    )

    assert config.enabled
    assert "function_definition" in config.chunk_types
    assert config.min_chunk_size == 5
    assert config.custom_options["include_docstrings"]


def test_chunker_config():
    """Test configuration management."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "test_config.yaml"

        # Create and save config
        config = ChunkerConfig()
        config.plugin_dirs = [Path("/tmp/plugins")]
        config.enabled_languages = {"python", "rust"}
        config.set_plugin_config(
            "python",
            PluginConfig(
                enabled=True,
                custom_options={"include_docstrings": False},
            ),
        )

        config.save(config_path)
        assert config_path.exists()

        # Load config
        loaded_config = ChunkerConfig(config_path)
        assert loaded_config.enabled_languages == {"python", "rust"}

        python_config = loaded_config.get_plugin_config("python")
        assert python_config.enabled
        assert not python_config.custom_options.get("include_docstrings", True)


def test_language_plugins():
    """Test individual language plugins."""
    # Test Python plugin
    python_plugin = PythonPlugin()
    assert python_plugin.language_name == "python"
    assert ".py" in python_plugin.supported_extensions
    assert "function_definition" in python_plugin.default_chunk_types

    # Test Rust plugin
    rust_plugin = RustPlugin()
    assert rust_plugin.language_name == "rust"
    assert ".rs" in rust_plugin.supported_extensions
    assert "function_item" in rust_plugin.default_chunk_types

    # Test JavaScript plugin
    js_plugin = JavaScriptPlugin()
    assert js_plugin.language_name == "javascript"
    assert ".js" in js_plugin.supported_extensions
    assert ".tsx" in js_plugin.supported_extensions
    assert "function_declaration" in js_plugin.default_chunk_types


def test_plugin_manager_integration():
    """Test the complete plugin manager integration."""
    manager = get_plugin_manager()

    # Should have built-in plugins loaded
    languages = manager.registry.list_languages()
    assert "python" in languages
    assert "rust" in languages
    assert "javascript" in languages

    # Test file extension mapping
    assert manager.registry.get_language_for_file(Path("test.py")) == "python"
    assert manager.registry.get_language_for_file(Path("test.rs")) == "rust"
    assert manager.registry.get_language_for_file(Path("test.js")) == "javascript"
    assert manager.registry.get_language_for_file(Path("test.tsx")) == "javascript"


def test_chunk_filtering():
    """Test chunk filtering based on configuration."""
    plugin = PythonPlugin(
        PluginConfig(
            min_chunk_size=5,
            max_chunk_size=20,
        ),
    )

    # Create a mock chunk
    from chunker import CodeChunk

    # Too small chunk (3 lines)
    small_chunk = CodeChunk(
        language="python",
        file_path="test.py",
        node_type="function_definition",
        start_line=1,
        end_line=3,
        byte_start=0,
        byte_end=50,
        parent_context="",
        content="def foo():\n    pass",
    )
    assert not plugin.should_include_chunk(small_chunk)

    # Good size chunk (10 lines)
    good_chunk = CodeChunk(
        language="python",
        file_path="test.py",
        node_type="function_definition",
        start_line=1,
        end_line=10,
        byte_start=0,
        byte_end=200,
        parent_context="",
        content="def foo():\n" + "    pass\n" * 8,
    )
    assert plugin.should_include_chunk(good_chunk)

    # Too large chunk (25 lines)
    large_chunk = CodeChunk(
        language="python",
        file_path="test.py",
        node_type="function_definition",
        start_line=1,
        end_line=25,
        byte_start=0,
        byte_end=500,
        parent_context="",
        content="def foo():\n" + "    pass\n" * 23,
    )
    assert not plugin.should_include_chunk(large_chunk)


def test_h_file_detection():
    """Test language detection for .h files."""
    manager = PluginManager()

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create a C header file
        c_header = tmpdir / "test_c.h"
        c_header.write_text(
            """
#ifndef TEST_H
#define TEST_H

typedef struct {
    int x;
    int y;
} Point;

int add(int a, int b);
void process_data(const char* data);

#endif
""",
        )

        # Create a C++ header file
        cpp_header = tmpdir / "test_cpp.h"
        cpp_header.write_text(
            """
#pragma once

#include <string>
#include <vector>

namespace MyNamespace {

class MyClass {
public:
    MyClass();
    virtual ~MyClass();
    
    void process(const std::string& data);
    
private:
    std::vector<int> m_data;
};

template<typename T>
T max(T a, T b) {
    return a > b ? a : b;
}

} // namespace MyNamespace
""",
        )

        # Test C header detection
        assert manager._detect_h_file_language(c_header) == "c"

        # Test C++ header detection
        assert manager._detect_h_file_language(cpp_header) == "cpp"

        # Test empty file
        empty_header = tmpdir / "empty.h"
        empty_header.write_text("")
        assert manager._detect_h_file_language(empty_header) == "c"  # Defaults to C

        # Test file with mixed features (should detect as C++)
        mixed_header = tmpdir / "mixed.h"
        mixed_header.write_text(
            """
// Some C-style code
typedef struct Point {
    int x, y;
} Point;

// But also has C++ features
class Shape {
public:
    virtual void draw() = 0;
};
""",
        )
        assert manager._detect_h_file_language(mixed_header) == "cpp"


def test_explicit_language_override():
    """Test that explicit language specification overrides detection."""
    manager = get_plugin_manager()

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a .h file that would normally be detected as C++
        h_file = Path(tmpdir) / "test.h"
        h_file.write_text(
            """
class TestClass {
public:
    void method();
};
""",
        )

        # Without language specified, should detect as C++
        # (Would test this but need parser setup)

        # With explicit language, should use that
        # This would be tested in integration tests with actual parsers


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

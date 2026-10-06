# Plugin Development

Plugins are an explicit extraction path through `PluginManager.chunk_file()`.
Registering one does not redirect top-level `chunk_file()`/`chunk_text()` or
the installed CLI, which use core extraction and `language_config_registry`.
A plugin also needs a parser for its language; registration alone does not
install a grammar.

## Create a Plugin

Save as `example_plugin.py`. This example customizes Python extraction using
the existing real parser, rather than inventing a new grammar identifier:

```python
from chunker.languages.plugin_base import LanguagePlugin

class ExamplePythonPlugin(LanguagePlugin):
    @property
    def language_name(self):
        return "python"

    @property
    def supported_extensions(self):
        return {".py"}

    @property
    def default_chunk_types(self):
        return {"function_definition", "class_definition"}

    @staticmethod
    def get_node_name(node, source):
        name = node.child_by_field_name("name")
        return source[name.start_byte:name.end_byte].decode("utf-8") if name else None

    def process_node(self, node, source, file_path, parent_context=None):
        chunk = super().process_node(node, source, file_path, parent_context)
        if chunk is not None:
            chunk.metadata["example_label"] = self.config.custom_options.get(
                "example_label", "custom"
            )
        return chunk
```

The base implementation selects node types, creates `CodeChunk`, and applies
size filtering. `PluginConfig.max_chunk_size` defaults to `None`; call the
base `should_include_chunk()` before adding filters, rather than comparing a
line count to `None`. Override `create_chunk()` to customize chunk construction.

## Register and Use

Run this beside `example_plugin.py`, with a real `example.py` fixture:

```python
from pathlib import Path
from chunker import PluginManager, PluginConfig
from example_plugin import ExamplePythonPlugin

manager = PluginManager()
manager.registry.register(ExamplePythonPlugin)
chunks = manager.chunk_file(
    Path("example.py"), "python",
    config=PluginConfig(custom_options={"example_label": "checked"})
)
assert chunks and all(c.metadata["example_label"] == "checked" for c in chunks)
```

Loading a custom plugin directory imports and executes its Python modules;
use trusted plugin code.

Load built-ins with `manager.load_builtin_plugins()` and custom directories
with `manager.load_plugins_from_directory(Path(...))`. Register a replacement
after built-ins and **before first use** when overriding a language. Registration
does not evict an already cached plugin instance; use a fresh `PluginManager`
when changing an active application's plugin. Inspect registered languages
with `manager.registry.list_languages()`.

## Configuration

```toml
# chunker.config.toml
[languages.python]
enabled = true
chunk_types = ["function_definition"]
min_chunk_size = 1
max_chunk_size = 200
example_label = "from-file"
```

Additional language keys become `custom_options`. There is no automatic
`[plugins.python]` schema or nested `custom_options` interpretation. Load the
file and pass the settings to the manager:

```python
from pathlib import Path
from chunker import ChunkerConfig

config = ChunkerConfig(Path("chunker.config.toml"))
chunks = manager.chunk_file(
    Path("example.py"), "python", config=config.get_plugin_config("python")
)
assert all(c.metadata["example_label"] == "from-file" for c in chunks)
```

Supported overrides include `CHUNKER_LANGUAGES_PYTHON_MIN_CHUNK_SIZE` and
`CHUNKER_LANGUAGES_PYTHON_EXAMPLE_LABEL`. They are applied while loading a file;
custom values remain strings. The application must explicitly apply plugin
directories and enabled-language selection. See [configuration](configuration.md)
and [environment variables](environment_variables.md).

## Test with Real Parsing

Save as `test_example_plugin.py` beside the plugin. Run using the locked
project environment (`uv run --locked pytest test_example_plugin.py`).

```python
from chunker import PluginManager
from example_plugin import ExamplePythonPlugin

def test_custom_plugin(tmp_path):
    source = tmp_path / "example.py"
    source.write_text("def hello():\n    return 1\n", encoding="utf-8")
    manager = PluginManager()
    manager.registry.register(ExamplePythonPlugin)
    chunks = manager.chunk_file(source, "python")
    assert len(chunks) == 1
    assert chunks[0].node_type == "function_definition"
    assert chunks[0].content == "def hello():\n    return 1"
    assert chunks[0].metadata["example_label"] == "custom"
```

The metadata assertion proves the custom hook ran. Testing top-level
`chunk_file()` here would exercise the core path and miss a broken plugin.

## Distribution and Language Support

A Python distribution can expose a plugin class, but current discovery scans
explicit directories; it does not automatically load setuptools entry points.
Import the installed class and register it, or load its directory explicitly.

For a new language, verify parser availability and node types with real
fixtures before selecting chunk types. See [language coverage](language-coverage.md)
for the difference between parser availability and verified extraction. Core
language changes belong in existing `LanguageConfig` registrations and their
tests; follow [CONTRIBUTING.md](https://github.com/Consiliency/treesitter-chunker/blob/main/CONTRIBUTING.md).

`ChunkRule` accepts `node_types`, `include_children`, `priority` and `metadata`;
it has no regex `pattern` or metadata-extractor callback. Implement application
classification in a hook or after extraction. Optional Boundary IR semantic
resolvers must preserve syntax-only operation without new mandatory services;
see [Boundary IR](interface-boundary-spec.md).

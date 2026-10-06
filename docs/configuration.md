# Configuration Reference

Version 5.2.0 has two configuration interfaces. Their discovery, schemas and
consumers differ; loading a configuration object does not configure every API.

## CLI Configuration

`treesitter-chunker chunk` and `batch` load **TOML** through `cli.main.load_config`.
`--config PATH` selects one file explicitly. Otherwise discovery walks upward
from the input path (first path for batch), then checks `~/.chunkerrc`.
Batch stdin checks only the working directory and home, without walking
parents. A missing explicit config path is currently ignored.
It uses the first successfully loaded file; it does not merge a stack of files.
The conventional filename is `.chunkerrc`.

```toml
# .chunkerrc
chunk_types = ["function_definition", "class_definition"]
min_chunk_size = 1
max_chunk_size = 200
include_patterns = ["*.py"]
exclude_patterns = ["*/vendor/*"]
parallel_workers = 2
```

| Key | Consumer | Behavior |
| --- | --- | --- |
| `chunk_types` | `chunk`, `batch` | Filter extracted chunks by node type |
| `min_chunk_size` | `chunk`, `batch` | Minimum lines in returned chunks |
| `max_chunk_size` | `chunk`, `batch` | Maximum lines in returned chunks; filters rather than splits |
| `include_patterns` | `batch` | Include paths matching shell patterns |
| `exclude_patterns` | `batch` | Exclude paths matching shell patterns |
| `parallel_workers` | `batch` | Thread-pool size; defaults to CPU count |

```bash
treesitter-chunker chunk example.py --lang python --config .chunkerrc --json
treesitter-chunker batch src/ --lang python --config .chunkerrc --parallel 2 --quiet --output-format jsonl
```

Explicit flags override the corresponding file values. These commands do not
interpret `[languages]` plugin settings, `${VAR}` expansion, or the
`ChunkerConfig` environment overrides. YAML/JSON files passed to these commands
are not supported. `cache_size`, `cache_enabled`, `log_level`, export settings
and memory limits are not consumed by this CLI loader.

`boundary`, `repo` and the auxiliary `python -m chunker.cli` commands have their
own options; consult their `--help` rather than assuming this schema applies.

## Plugin Configuration

`ChunkerConfig` supports TOML, YAML and JSON and provides `PluginConfig` objects that you pass to `PluginManager.chunk_file()`.
Calling `ChunkerConfig.find_config()` returns a path; pass that path to the
constructor to load it. Construction without a path does not discover or load
files or apply environment overrides.

Discovery searches for `chunker.config.toml`, `.yaml`, `.yml` or `.json` in the
starting directory and parents, then `~/.chunker/config.*`. It does not search
`.chunkerrc` or `/etc/chunker`.

```toml
# chunker.config.toml
[chunker]
plugin_dirs = ["./plugins"]
enabled_languages = ["python"]

[chunker.default_plugin_config]
min_chunk_size = 1

[languages.python]
enabled = true
chunk_types = ["function_definition", "class_definition"]
min_chunk_size = 1
max_chunk_size = 200
```

```python
from pathlib import Path
from chunker import ChunkerConfig, PluginManager

config = ChunkerConfig(Path("chunker.config.toml"))
manager = PluginManager()
manager.load_builtin_plugins()
chunks = manager.chunk_file(
    Path("example.py"), "python", config=config.get_plugin_config("python")
)
print(len(chunks))
```

Plugin defaults are `enabled=True`, `chunk_types=None`, `min_chunk_size=1` and
`max_chunk_size=None`. Additional language keys become `custom_options`; they
only affect behavior when a plugin actually reads them. Unknown options are
not automatic implementations of progress, logging, memory or export controls.
Core `chunk_file()` and `chunk_text()` do not take a `ChunkerConfig` argument.
`PluginManager` also does not accept that object in its constructor; your
application must apply `plugin_dirs` and `enabled_languages` explicitly.
`PluginConfig.enabled` is not enforced by the manager; callers must check it
before invoking extraction.

## Environment Variables

When a file is loaded with `use_env_vars=True`, `ChunkerConfig` expands `${VAR}`
and `${VAR:default}`, parses plugin settings, then applies supported overrides.
See [Environment Variables](environment_variables.md) for the exact names.
Expansion produces strings; use numeric literals for numeric plugin settings,
or use the supported numeric environment overrides.

```python
from pathlib import Path
from chunker import ChunkerConfig

config = ChunkerConfig(Path("chunker.config.toml"), use_env_vars=False)
print(config.get_plugin_config("python"))
```

There is no general `config.validate()` method. File decoding and supported
constructor/method contracts provide validation; test the consuming plugin
with representative fixtures. TOML writing with `config.save()` uses the
included `tomli-w` dependency.

## See Also

- [CLI Reference](cli-reference.md)
- [Plugin Development](plugin-development.md)
- [API Reference](api-reference.md)

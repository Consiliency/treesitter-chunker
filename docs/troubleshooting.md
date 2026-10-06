# Troubleshooting

## Confirm the Environment

```bash
python -c "from importlib.metadata import version; print(version('treesitter-chunker')); print(version('tree-sitter')); print(version('tree-sitter-language-pack'))"
python -m pip check
treesitter-chunker --help
```

Use the same interpreter/environment for installation and execution. The
5.2.0 stack pins Tree-sitter 0.26 and language-pack 1.20. In a source checkout,
restore the locked environment with `uv sync --locked --all-extras`; do not
install py-tree-sitter from Git to work around an ABI mismatch. Linux parser
wheels require glibc 2.34 or newer. See [packaging](packaging.md).

## Import Errors

These imports are supported:

```python
from chunker import ASTCache, CodeChunk, chunk_file, chunk_text
from chunker.parallel import chunk_files_parallel, chunk_directory_parallel
from chunker.streaming import StreamingChunker
from chunker.auto import ZeroConfigAPI
```

`chunker.cache`, `chunker.factory` and `chunker.registry` are old paths; prefer
public APIs. `chunker.chunker` contains token helpers, not `chunk_file`.
`ZeroConfigAPI` requires a registry; it is not a top-level export or a universal
no-argument grammar installer. See [Zero-Config API](zero_config_api.md).

## No Chunks Returned

A loadable grammar is not a promise of verified semantic extraction. Check
[language coverage](language-coverage.md), input content, selected node types
and size filters. There is no default rule that excludes all test files.
Inspect the nearest `.chunkerrc` and any explicit `--include`/`--exclude` flags.

```bash
treesitter-chunker chunk example.py --lang python --min-size 1 --json
treesitter-chunker batch src/ --lang python --include '*.py' --quiet --output-format jsonl
```

For Python, verify that the file contains a function or class; a file of only
assignments may correctly produce no semantic chunks. The CLI's size limits
filter chunks; they do not split large chunks into smaller ones.

## Parser or Grammar Failures

First try prefetching the required pack grammar while online:

```bash
python -c "import tree_sitter_language_pack as p; p.prefetch(['python'])"
```

BAML needs the companion extra:

```bash
python -m pip install 'treesitter-chunker[baml]==5.2.0'
```

Local grammar compilation is an auxiliary workflow. Check pinned provenance,
compiler availability and the recorded error before building. Do not delete
cache trees or replace a loaded native library as a generic recovery step.
See [grammar management](grammar_management.md).

## CLI Output and Subprocesses

`chunk` and `batch` already detect languages when `--lang` is omitted. There are
no `auto-chunk` or `auto-batch` commands. Use `--help` on the installed command
rather than older examples. Use `--quiet --output-format json` (or `jsonl`) for
successful machine-readable output; always check the exit status and validate the payload before parsing.

CLI JSON is an array of chunk objects. The source REST server wraps chunks in
an object containing `chunks`, `total_chunks` and `language`. These are
different response shapes; see [cross-language usage](cross-language-usage.md).

## Slow Processing or Large Exports

Direct `chunk_file()` does not automatically use the SQLite chunk cache.
See [performance](performance-guide.md) for explicit caching and correctly
configured process pools. Streaming saves chunk-list memory but still builds
a whole syntax tree.

```python
from chunker import chunk_file_streaming
from chunker.export import JSONLExporter

JSONLExporter().stream_export(
    chunk_file_streaming("example.py", "python"), "output.jsonl"
)
```

For `JSONExporter`/`JSONLExporter`, `compress=True` appends `.gz` to the supplied
filename; pass `output.json` rather than `output.json.gz`.

## Tests and Support

Follow [CONTRIBUTING.md](https://github.com/Consiliency/treesitter-chunker/blob/main/CONTRIBUTING.md)
for the locked test tiers. A new skip or xfail needs an explanation, rather
than being dismissed as an expected ABI mismatch. Include package versions,
platform, a small real fixture, the exact invocation and the error traceback in
this repository's [issue tracker](https://github.com/Consiliency/treesitter-chunker/issues).

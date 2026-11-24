# CLI Reference

This page summarizes the command-line interface for Tree-sitter Chunker.

For packaging and release operations, see `docs/packaging.md` and `docs/development/RELEASE_CHECKLIST.md`.

## Installation

Install the CLI from PyPI:

```bash
# Install the latest stable version
pip install treesitter-chunker

# With visualization tools (requires graphviz)
pip install "treesitter-chunker[viz]"

# With all optional dependencies
pip install "treesitter-chunker[all]"
```

## Commands

### Chunk a single file

```bash
treesitter-chunker chunk example.py -l python
# Output options
treesitter-chunker chunk example.py -l python --json > chunks.json
```

Source paths must be regular files; symlinks to regular files work. `chunk`,
`batch`, `boundary` and the `debug` commands reject FIFOs, devices and sockets
without opening them, print `<path> is not a regular file (...)` and exit 1.
`chunk` and the `debug` commands also reject a directory; `batch` and `boundary`
walk directories and skip non-regular entries. `batch` applies `--include` and
`--exclude` first, so an excluded path is never reported.
To chunk piped input, use `chunk --stdin --lang <language>` or save it to a
file first.

### Batch process a directory

```bash
treesitter-chunker batch src/ --recursive
# Include / exclude patterns
treesitter-chunker batch src/ --include "**/*.py" --exclude "**/tests/**,**/*.tmp"
```

### Automatic language detection

`chunk` and `batch` detect language from file paths when `--lang` is omitted:

```bash
treesitter-chunker chunk example.py --json
treesitter-chunker batch src/ --quiet --output-format jsonl
```

For stdin, pass `--lang` explicitly. Detection is not a promise of text fallback
for every unknown extension; see [language coverage](language-coverage.md).
There are no `auto-chunk` or `auto-batch` commands.

### List available languages

```bash
# Show all supported languages
treesitter-chunker languages
```

### Boundary IR

```bash
# Generate canonical Boundary IR; strict resolution is the default
treesitter-chunker boundary src/ --lang python --output boundary.json

# Preserve discovery-oriented relationship references
treesitter-chunker boundary src/ --lang python --resolution-mode permissive

# Stop on the first extraction failure
treesitter-chunker boundary src/ --lang python --fail-fast

# Include measured stage timings in JSON
treesitter-chunker boundary src/ --lang python --include-timings

# Print a concise run summary without polluting stdout JSON
treesitter-chunker boundary src/ --lang python --summary

# Reuse persisted per-file Boundary IR cache records on warm runs
treesitter-chunker boundary src/ --lang python --incremental --cache-dir .cache/boundary

# Ignore valid cache records and refresh the incremental cache
treesitter-chunker boundary src/ --lang python --incremental --force-rebuild

# Experimental: narrow ambiguous call edges (auto-detected languages, no filter)
treesitter-chunker boundary src/ --call-resolution structural
```

When `--output` is used, the boundary command prints the output path and summary
unless `--quiet` is set. Without `--output`, JSON is written to stdout; `--summary`
uses stderr so stdout remains parseable JSON.

`--incremental` keeps stdout JSON canonical and does not print cache stats.
`--cache-dir` selects the persistent Boundary IR cache directory. `--force-rebuild`
bypasses cache reads and refreshes records for the current snapshot.

`--call-resolution` is experimental (treesitter-chunker#682). See
[Call resolution](call-resolution.md) for the modes, test scoping and known
limits. `name`, the default, is the usual name-only resolution.
`structural` narrows `ambiguous`
call edges whose callee is a bare identifier in a Python, JavaScript, TypeScript
or TSX file. For JavaScript, TypeScript and TSX callers it resolves an edge
when a lexical binding in the caller's file proves its one target
(`t1.lexical`; `t1.ts_overload` for a TS overload set; `t1.js_hoist` for the
last of repeated plain-JavaScript function declarations). A script-goal top
level resolves only when no other file of the run may declare the name as a
global, and merged TS namespace bodies never resolve. For Python callers it
resolves an edge when the LEGB scope chain proves one unconditional,
undecorated definition (`t1.lexical`); redefinitions narrow to their group
and never resolve. Elsewhere only the symbol-kind and language-family filters
narrow. `imports` adds Tier 2: JavaScript, TypeScript and TSX calls bound by a
relative ES import resolve when the specifier names exactly one file of the run
and its exports lead to one proven definition (`t2.import`, `t2.namespace`);
more than one file variant leaves the edge unchanged. Python calls bound by an
import (`from m import t`, `m.t()`) resolve when the module name resolves from
the extraction root to exactly one file and leads to one proven definition;
other files' writes to a module's globals make it unprovable, so for Python
`imports` can resolve fewer calls than `structural`, and a file that may load
or write any module (`exec`, `compile`, `pickle.loads`, a code object such
as `f.__code__`, heap walking with `gc`, a frame's `f_locals`, a `.patch`
call with a computed target, a non-literal `import_module`, `sys.path`
changes, ...) turns Python Tier 2 off. Run `boundary` without
`--lang` for Tier 2, since a language filter leaves other variants uncollected.
Narrowed edges carry
`provenance.call_resolution`
and `provenance.call_rules`, and `run.options.call_resolution` records the mode.
Use a separate `--cache-dir` per mode: switching modes on one cache directory is a
cold run.

### Symbol graph extraction

```bash
# Extract symbols and relationships; permissive resolution is the default
python -m chunker.cli symbols extract src/ --language python --output symbols.json

# Request strict relationship classification in symbol JSON
python -m chunker.cli symbols extract src/ --language python --resolution-mode strict

# Experimental: narrow ambiguous call edges, as for `boundary` above
python -m chunker.cli symbols extract src/ --language python --call-resolution structural
```

`symbols extract` always applies its `--language` (default `python`) to every
file, so it cannot run unfiltered.

### Debug and visualization

```bash
# Debug commands (requires graphviz or install with [viz] extra)
treesitter-chunker debug --help

# AST visualization
treesitter-chunker debug ast example.py --lang python --fmt tree
```

### Configuration

You can pass a configuration file to adjust chunk sizes and filters:

```bash
treesitter-chunker chunk example.py --config .chunkerrc --lang python
```

The `chunk`/`batch` CLI loader accepts TOML. Plugin configuration is a separate
TOML/YAML/JSON interface; see [Configuration](configuration.md).

### Grammar commands and approved pins

The `grammar` command group and its `--trusted-artifacts PATH` option, the
user-config pin file, and the rule that every grammar subcommand exits 2 on a
missing or defective pin file are documented in the
[Grammar Management Guide](grammar_management.md#approved-pins).

### Export helpers

Use exporters from Python for structured outputs (JSON, JSONL, Parquet, GraphML, Neo4j). See the Export Formats guide for examples.

## Output and installed version

`chunk` supports `table`, `json`, `jsonl` and `minimal`. `batch` supports
`summary`, `json`, `jsonl`, `minimal` and `csv`. Use `--quiet` for machine-readable
batch output. An extraction failure returns status 1 and reports its input/error
on stderr, including with `--quiet`. Structured stdout contains only chunks:
JSON emits `[]` when none succeeded; JSONL emits no lines in that case. A batch
continues after individual failures, emits successful chunks, and returns 1 if
any selected input failed. Successful empty structured extraction returns 0.
Unmapped extensions still warn and skip rather than failing extraction.
`.baml` files select BAML automatically. Install `treesitter-chunker[baml]`
to parse them; a missing companion produces installation guidance and status 1.
Implicit ZeroConfigAPI detection separately retains its text fallback when the
companion is absent.
`chunk` takes one file;
use `batch` or `boundary` for a directory.

Callers upgrading from the earlier per-file status/stdout behavior should check
the nonzero status while retaining useful partial-batch stdout. Validate the
decoded payload as usual.

```bash
python -c "from importlib.metadata import version; print(version('treesitter-chunker'))"
treesitter-chunker --help
treesitter-chunker batch --help
```

The installed CLI has no `--version` option. See
[Environment Variables](environment_variables.md) for the settings actually
consumed by each interface.

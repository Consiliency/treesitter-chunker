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

### Batch process a directory

```bash
treesitter-chunker batch src/ --recursive
# Include / exclude patterns
treesitter-chunker batch src/ --include "**/*.py" --exclude "**/tests/**,**/*.tmp"
```

### Zero-config auto-detection

```bash
# Automatically detect language for a file and chunk it
treesitter-chunker auto-chunk path/to/file

# Auto-chunk an entire directory using detection + intelligent fallbacks
treesitter-chunker auto-batch path/to/repo
```

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
```

When `--output` is used, the boundary command prints the output path and summary
unless `--quiet` is set. Without `--output`, JSON is written to stdout; `--summary`
uses stderr so stdout remains parseable JSON.

`--incremental` keeps stdout JSON canonical and does not print cache stats.
`--cache-dir` selects the persistent Boundary IR cache directory. `--force-rebuild`
bypasses cache reads and refreshes records for the current snapshot.

### Symbol graph extraction

```bash
# Extract symbols and relationships; permissive resolution is the default
python -m chunker.cli symbols extract src/ --language python --output symbols.json

# Request strict relationship classification in symbol JSON
python -m chunker.cli symbols extract src/ --language python --resolution-mode strict
```

### Debug and visualization

```bash
# Debug commands (requires graphviz or install with [viz] extra)
treesitter-chunker debug --help

# AST visualization
treesitter-chunker debug ast example.py --lang python --format tree
```

### Configuration

You can pass a configuration file to adjust chunk sizes, language rules, and filters:

```bash
treesitter-chunker chunk src/ --config .chunkerrc
```

Supported formats: TOML, YAML, JSON. See the Configuration guide for details.

### Export helpers

Use exporters from Python for structured outputs (JSON, JSONL, Parquet, GraphML, Neo4j). See the Export Formats guide for examples.

## Environment variables

- `CHUNKER_BUILD_VERBOSE=1` — enable verbose build logs (build system)
- `CHUNKER_WHEEL_LANGS=python,javascript,rust` — limit grammars compiled into wheels
- `CHUNKER_BUILD_TIMEOUT=240` — build timeout in seconds

These are primarily for contributors building distribution artifacts.

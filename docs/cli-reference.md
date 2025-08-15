# CLI Reference

This page summarizes the command-line interface for Tree-sitter Chunker.

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

# CLI Reference

This page summarizes the command-line interface for Tree-sitter Chunker.

## Installation

Run the CLI from the repository:

```bash
python -m pip install -e ".[dev]"
# or use uv
uv pip install -e ".[dev]"
```

## Commands

### Chunk a single file

```bash
python cli/main.py chunk example.py -l python
# Output options
python cli/main.py chunk example.py -l python --json > chunks.json
```

### Batch process a directory

```bash
python cli/main.py batch src/ --recursive
# Include / exclude patterns
python cli/main.py batch src/ --include "**/*.py" --exclude "**/tests/**,**/*.tmp"
```

### Zero-config auto-detection

```bash
# Automatically detect language for a file and chunk it
python cli/main.py auto-chunk path/to/file

# Auto-chunk an entire directory using detection + intelligent fallbacks
python cli/main.py auto-batch path/to/repo
```

### Configuration

You can pass a configuration file to adjust chunk sizes, language rules, and filters:

```bash
python cli/main.py chunk src/ --config .chunkerrc
```

Supported formats: TOML, YAML, JSON. See the Configuration guide for details.

### Export helpers

Use exporters from Python for structured outputs (JSON, JSONL, Parquet, GraphML, Neo4j). See the Export Formats guide for examples.

## Environment variables

- `CHUNKER_BUILD_VERBOSE=1` — enable verbose build logs (build system)
- `CHUNKER_WHEEL_LANGS=python,javascript,rust` — limit grammars compiled into wheels
- `CHUNKER_BUILD_TIMEOUT=240` — build timeout in seconds

These are primarily for contributors building distribution artifacts.

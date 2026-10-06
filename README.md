# Tree-sitter Chunker

[![PyPI](https://img.shields.io/pypi/v/treesitter-chunker.svg)](https://pypi.org/project/treesitter-chunker/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Test Suite](https://github.com/Consiliency/treesitter-chunker/actions/workflows/test.yml/badge.svg)](https://github.com/Consiliency/treesitter-chunker/actions/workflows/test.yml)
[![codecov](https://codecov.io/gh/Consiliency/treesitter-chunker/branch/main/graph/badge.svg)](https://codecov.io/gh/Consiliency/treesitter-chunker)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

Split source code into functions, classes, and other syntax units for code
search, embeddings, and AI context. Tree-sitter provides the syntax tree;
Chunker returns source content, line and byte spans, and context metadata.

## Install

Requires Python 3.11 or newer. The main package is a universal Python wheel.

```bash
pip install treesitter-chunker
```

The default parser stack uses Tree-sitter 0.26 and language-pack 1.20.
Parser libraries download on first use and are cached by pack version and
platform. The supported Linux wheel path requires glibc 2.34 or newer.
For offline use, prefetch the languages you need while online:

```bash
python -c "import tree_sitter_language_pack as p; p.prefetch(['python', 'javascript', 'typescript'])"
```

See [packaging and parser integrity](docs/packaging.md) for platform limits,
offline custody, and release procedures. Debian, RPM, and Homebrew packages
are currently suspended.

Optional extras include `viz` for visualization and `advanced` for additional
query dependencies. Graphviz visualization also requires the system `dot`
executable. The `api` extra installs REST API dependencies; the server under
`api/` runs from a source checkout and is not included in the main wheel.

## Chunk a file or source text

```python
from chunker import chunk_file, chunk_text

chunks = chunk_file("app.py", language="python")
for chunk in chunks:
    print(chunk.node_type, chunk.start_line, chunk.end_line)
    print(chunk.content)

source = "def greet(name):\n    return f'Hello, {name}'\n"
chunks = chunk_text(source, language="python", file_path="greet.py")
```

Pass a stable `file_path` when chunking text if you persist chunk identities.
See the [chunk identity contract](docs/chunk-identity.md) and
[Boundary IR specification](docs/interface-boundary-spec.md) for identity,
determinism, and relationship semantics.

The CLI can return JSON for use from other languages:

```bash
treesitter-chunker chunk app.py --lang python --json
printf 'def greet():\n    return "hello"\n' | treesitter-chunker chunk --stdin --lang python --json
treesitter-chunker boundary app.py --lang python --pretty
treesitter-chunker languages
treesitter-chunker --help
```

To check the installed version:

```bash
python -c "from importlib.metadata import version; print(version('treesitter-chunker'))"
```

## Language support

The pinned language pack contains 371 parsers: 370 pass the bounded load
gate, while COBOL is disabled after a native parser hang. Loading a parser
does not establish useful chunk extraction. The committed coverage report
records 28 extraction-verified languages and 12 languages with deterministic
Boundary IR golden fixtures.

See the [language coverage report](docs/language-coverage.md) for the
per-language results and remaining extraction gaps.

### BAML

Install the optional companion grammar for structural `.baml` chunking:

```bash
pip install 'treesitter-chunker[baml]'
treesitter-chunker chunk example.baml --json
```

The extra pins `treesitter-chunker-baml-grammar==0.1.0`. It uses BoundaryML's
official grammar with a temporary overlay for BAML 0.20.1 backtick prompts.
Native wheels cover Linux glibc x86_64/aarch64, macOS x86_64/arm64, and Windows
x86_64, with tests on Python 3.11–3.13. Source installs require a C compiler.

Without the extra, main CLI BAML inputs give installation guidance and status 1;
implicit ZeroConfigAPI file chunking falls back to text, and automatic symbol
and Boundary repository scans skip BAML. Malformed BAML fails before
returning structural chunks. See the [companion grammar README](packages/baml-grammar/README.md).

## Documentation

- [Documentation site](https://consiliency.github.io/treesitter-chunker/)
- [Getting started](docs/getting-started.md) and [CLI reference](docs/cli-reference.md)
- [Python API](docs/api-reference.md), [configuration](docs/configuration.md), and [cookbook](docs/cookbook.md)
- [Export formats](docs/export-formats.md) and [GraphML](docs/graphml_export.md)
- [Architecture](docs/architecture.md) and [plugin development](docs/plugin-development.md)
- [Release history](CHANGELOG.md) and [contributing](CONTRIBUTING.md)

## Development

```bash
git clone https://github.com/Consiliency/treesitter-chunker.git
cd treesitter-chunker
uv sync --locked --all-extras
uv run --locked --with toml --all-extras python scripts/run_ci_smoke.py
```

[CONTRIBUTING.md](CONTRIBUTING.md) describes local validation, platform checks,
and Boundary IR changes. Coverage work remains in progress under
treesitter-chunker#69; the Codecov badge reports the CI measurement and is not
a claim that the full package meets a percentage target.

Report bugs through [GitHub issues](https://github.com/Consiliency/treesitter-chunker/issues).
Licensed under [MIT](LICENSE).

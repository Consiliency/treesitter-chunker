# Deployment Guide

> Maintainer documentation. This page is omitted from public navigation.

## Supported Installation

Use Python 3.11 or newer. The main wheel is pure Python; native parser and
other runtime dependencies must also have compatible wheels. The pinned
parser wheels require **glibc 2.34 or newer on Linux**; Ubuntu 18.04 is not a
supported target for that stack. Verify the target architecture and Python
version using a wheel-only installation, rather than assuming an OS name is
sufficient. See [packaging](../packaging.md) for platform details.

```bash
python -m venv .venv
# On Windows, use .venv\Scripts\python.exe instead.
.venv/bin/python -m pip install --only-binary=:all: "treesitter-chunker==5.2.0"
.venv/bin/python -m pip check
.venv/bin/python -c "from importlib.metadata import version; print(version('treesitter-chunker'))"
.venv/bin/treesitter-chunker --help
```

Prefetch required grammars while online, under the account that will run the
application. The grammar pack may download native parsers on first use:

```bash
.venv/bin/python -c "import tree_sitter_language_pack as p; p.prefetch(['python', 'javascript'])"
printf 'def hello():\n    return 1\n' | .venv/bin/treesitter-chunker chunk --stdin --lang python --json
```

Size memory and worker counts by measuring representative input. Streaming
still constructs a full syntax tree. No fixed RAM minimum or unimplemented
`CHUNKER_MAX_MEMORY_USAGE` setting can guarantee a workload fits.

## Source Environment

```bash
git clone https://github.com/Consiliency/treesitter-chunker.git
cd treesitter-chunker
uv sync --locked --all-extras
uv run --locked treesitter-chunker --help
```

Use the locked parser stack. Do not install an unpinned Git version of
py-tree-sitter or rebuild grammars to bypass a compatibility gate.

## REST Server

The `api` package is **source-checkout only**. The PyPI `api` extra installs
dependencies; it does not package the server. From the checkout above:

```bash
# Supply a private token through your deployment's secret mechanism.
export TREE_SITTER_CHUNKER_API_ROOT="$(pwd)"
uv run --locked uvicorn api.server:app --host 127.0.0.1 --port 8000
```

Set `TREE_SITTER_CHUNKER_API_TOKEN` in the server environment before starting
it to enable filesystem-backed endpoints.
`/chunk/file` accepts paths relative to the configured root and requires a
Bearer token; absolute paths, traversal and symlink escapes are rejected.
`/chunk/text`, `/health` and `/languages` do not require that token. Request
bodies are limited to 1 MiB. Use the generated `/docs` for request schemas.
See [cross-language usage](../cross-language-usage.md) for client examples.

## Containers

There is no current container publication workflow in this repository. Do not
assume `ghcr.io/consiliency/treesitter-chunker:latest` is a maintained release.
The checked-in Dockerfile is a legacy source-build recipe, and its runtime
stage installs only the wheel: it cannot run the source-only REST server.

For a CLI container, create your own deployment image from a glibc-based
Python image with compatible wheels:

```dockerfile
FROM python:3.13-slim-bookworm
RUN pip install --no-cache-dir --only-binary=:all: treesitter-chunker==5.2.0
RUN python -c "import tree_sitter_language_pack as p; p.prefetch(['python'])"
WORKDIR /workspace
ENTRYPOINT ["treesitter-chunker"]
```

```bash
docker build -t chunker-cli:5.2.0 -f Dockerfile.cli .
docker run --rm -v "$(pwd):/workspace:ro" chunker-cli:5.2.0 chunk /workspace/example.py --lang python --json
```

Save the recipe as `Dockerfile.cli`. This is an example for your deployment,
not a claim that the image has been published or tested on every architecture.
A server image must additionally include the `api/` source and its dependencies.

## Configuration and Operations

Use explicit CLI flags or the documented TOML `.chunkerrc` for `chunk`/`batch`.
For plugin consumers use `ChunkerConfig`; these are separate configuration
interfaces. See [configuration](../configuration.md) and
[performance](../performance-guide.md).

Treat a successful health response as process readiness, not extraction
acceptance. Exercise a real parser, check CLI exit status and validate returned
chunks. Keep grammar/result caches private and writable by the service user.

## Releases

Only `.github/workflows/release.yml` publishes the main package to PyPI.
Ordinary main CI does not publish it. Follow [packaging](../packaging.md) and
the [release checklist](RELEASE_CHECKLIST.md); release tags must match project
metadata. For support, use this repository's
[issue tracker](https://github.com/Consiliency/treesitter-chunker/issues).

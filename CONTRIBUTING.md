# Contributing to Tree-sitter Chunker

## Setup

Use Python 3.11 or newer and the project environment:

```bash
git clone https://github.com/Consiliency/treesitter-chunker.git
cd treesitter-chunker
uv sync --locked --all-extras
```

The lock pairs Tree-sitter 0.26 with language-pack 1.20. Prefetch the languages
needed by your work while online; the default parser path does not require
local grammar compilation.

```bash
uv run --locked python -c "import tree_sitter_language_pack as p; p.prefetch(['python', 'javascript', 'typescript'])"
```

Source grammar development needs a C compiler. See
[plugin development](docs/plugin-development.md) and
[the BAML companion](packages/baml-grammar/README.md) for their respective workflows.

## Worktrees

Use an isolated branch and worktree for each change. Probe
`/etc/consiliency/team-host` first, then `/mnt/workspace`:

- On a team host, use `$WORKTREE_ROOT/<project>-<branch>`; if unset, use
  `$HOME/workspace/worktrees/<project>-<branch>`. Keep worktrees and writable
  build outputs private to the user.
- On other hosts with `/mnt/workspace`, use
  `/mnt/workspace/worktrees/<project>-<branch>`.
- Otherwise, use the usual Git worktree conventions.

## Make a focused change

Follow existing patterns and keep each PR limited to one behavior or repair.
Test observable behavior with real parsers and fixtures where applicable.
Record separately discovered defects in their own issues. Qualify every issue
and PR reference with its repository, such as `treesitter-chunker#69`.

Update the user-facing docs for changed contracts and add a changelog entry
for changes that affect consumers. Release history belongs in
[CHANGELOG.md](CHANGELOG.md); execution plans and review evidence belong in
their existing plan or issue records.

## Validate locally before pushing

Run the narrow affected tests first, then the local CI checks:

```bash
uv run --locked --all-extras ruff check chunker/ cli/ tests/ --exclude archive --exclude logs --exclude site
uv run --locked --all-extras black --check chunker/ cli/ tests/ scripts/
uv run --locked --all-extras python scripts/mypy_gate.py
uv run --locked --with toml --all-extras python scripts/run_ci_smoke.py
```

The mypy gate blocks new errors against the committed baseline; it does not
require clearing all existing type debt. Pull-request CI runs the fast smoke
lane, and the Test Suite workflow confirms platform-core behavior on Linux,
macOS, and Windows. The scheduled CI job and release validation run the full
`tests/` and `spec_tests/` suite.

The type gate compares complete messages and error codes, normalizing only
leading file locations. Literal values, numeric colons and backslashes inside
messages remain significant. For a diagnostic-format migration, measure and
reconcile the baseline from unchanged accepted code before candidate edits. A new
candidate's errors must be fixed or tracked separately; do not use `--update`
to absorb them into the baseline. Ordinary baseline updates remove cleared debt.

For broad behavior changes, run the platform-core and full tiers locally:

```bash
uv run --locked --with toml --all-extras python scripts/run_platform_core.py --platform linux
uv run --locked --with toml --all-extras python scripts/run_full_suite.py
```

Use representative full-suite coverage to find behavior gaps; do not use
unsupported coverage claims or a blanket 95% requirement. Coverage slices
under treesitter-chunker#69 are accepted by their stated behavior contracts
and named mutations.

### Platform checks

Reproduce a matrix failure with the narrow affected test before retrying CI.
Use explicit UTF-8 file I/O, portable paths, and robust process readiness
checks. Avoid assertions that depend on tight wall-clock limits.
Cached parallel checks verify persisted fixture chunks and actual warm cache
payload reuse. Performance observations belong in a controlled benchmark run.
File-hash checks compare actual fixture bytes with an independent SHA-256 oracle
across read sizes and input changes, without individual timing-ratio gates.
Concurrent configuration checks assert actual fixture results for every worker
using a preloaded configuration. They do not impose throughput or lock-wait
budgets, or claim concurrent configuration writes are supported.

Before pushing changes to configuration, paths, temporary files, extraction,
fallback logic, or export formatting, run the standing Windows preflight:

```bash
ssh win 'powershell -NoProfile -Command "cd $HOME\\code\\treesitter-chunker; git fetch origin; git checkout main; git pull --ff-only; uv run --with toml --all-extras python scripts/run_windows_preflight.py"'
```

Use the fleet's Linux and macOS preflights for broad regression confirmation
when those hosts are available. Hosted CI confirms the matrix; local checks
should discover ordinary regressions first.

## Boundary IR changes

The determinism gates cover all `SUPPORTED_BOUNDARY_LANGUAGES` with golden
snapshots, nonempty extraction checks, and an exact grammar/runtime pin
assertion. For an intentional IR change, regenerate on the locked stack:

```bash
uv run --locked --all-extras python scripts/regenerate_boundary_goldens.py
uv run --locked --all-extras pytest tests/test_boundary_ir_golden_snapshots.py tests/test_boundary_ir_determinism.py -q
```

Review the generated golden diff in the PR. Regeneration is idempotent:
running it a second time must produce no additional diff. Never hand-edit
goldens or change parser pins to make a failing gate pass. Explain consumer
impact using the [Boundary IR specification](docs/interface-boundary-spec.md).

## Documentation and releases

Build docs into a temporary directory so tracked `site/` output stays clean:

```bash
uv run --locked --all-extras --with mkdocs --with mkdocs-material --with mkdocstrings-python mkdocs build --strict --site-dir "$(mktemp -d)"
```

Start user documentation in [README.md](README.md) and the
[documentation site](https://consiliency.github.io/treesitter-chunker/).
For publication, follow [packaging](docs/packaging.md) and the
[release checklist](docs/development/RELEASE_CHECKLIST.md). Only the guarded
release workflow publishes the main package to PyPI.

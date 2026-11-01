# Contributing to Tree-sitter Chunker

## Setup

Python 3.14 is the main version: CI and release validation run on it. Python
3.12 stays the supported minimum until the next major release (7.0) drops it
(treesitter-chunker#599). Keep source syntax compatible with 3.12 and check
changes on both. `.python-version` pins 3.12, so a plain sync uses it:

```bash
git clone https://github.com/Consiliency/treesitter-chunker.git
cd treesitter-chunker
uv sync --locked --all-extras
```

For 3.14, select the interpreter explicitly and keep its environment separate
from the 3.12 `.venv`. The locked environment installs from wheels on both
interpreters; it needs no compiler, libffi or Rust toolchain:

```bash
export UV_PROJECT_ENVIRONMENT="$PWD/.venv-3.14" UV_PYTHON=3.14
uv sync --locked --all-extras
```

Run the validation commands below in that shell to repeat them on 3.14.

The lock pairs Tree-sitter 0.26 with language-pack 1.20 and the official
`tree-sitter-python==0.25.0` and `tree-sitter-javascript==0.25.0` wheels. Those
official wheels are the default Python/JavaScript providers; the pack remains
the fallback for other languages. Prefetch other languages needed by your work
while online; the default parser path does not require local grammar compilation.

```bash
uv run --locked python -c "import tree_sitter_language_pack as p; p.prefetch(['typescript'])"
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
uv run --locked --all-extras ruff check chunker/ chunker/build/ cli/ tests/ tools/governed_group.py tools/governed_scope.py tools/sync_governed_test_transport.py --exclude archive --exclude logs --exclude site
uv run --locked --all-extras black --check chunker/ cli/ tests/ scripts/ tools/governed_group.py tools/governed_scope.py tools/sync_governed_test_transport.py
uv run --locked --all-extras python scripts/mypy_gate.py
uv run --locked --all-extras mypy --follow-imports=silent --allow-untyped-defs --allow-incomplete-defs --allow-untyped-calls --check-untyped-defs --no-pretty --no-error-summary --show-error-codes tools/sync_governed_test_transport.py
uv run --locked --with toml --all-extras python scripts/run_ci_smoke.py
```

The Ruff command names `chunker/build/` explicitly. Ruff's recursive discovery
honors the `build/` ignore and exclude entries meant for generated output, which
also match that tracked source package. `ci.yml`, `release.yml` and this block
use the same lint and format path lists; `tests/test_lint_path_policy.py`
checks that they match.

The mypy gate blocks new errors against the committed baseline; it does not
require clearing all existing type debt. Pull-request CI runs the fast smoke
lane, and the Test Suite workflow confirms platform-core behavior on Linux,
macOS, and Windows. The scheduled CI job and release validation run the full
`tests/` and `spec_tests/` suite.

The explicitly listed governed tools use a separate zero-error body-type check
without annotation requirements; excluded paths and strict-annotation debt are
tracked separately, never in the baseline. Ruff and Black cover all three listed
governed tools. The body-type check covers only
`tools/sync_governed_test_transport.py`; `tools/governed_group.py` and
`tools/governed_scope.py` are excluded because of existing body-type findings
tracked under treesitter-chunker#514.

CI runs lint, the type gate and the smoke tier once, on Linux 3.14. The
scheduled full tier and release full validation also run on 3.14. The 3.12
minimum keeps only two main-package checks: the Linux platform-core job (macOS
and Windows run 3.14) and the release installed-wheel check (3.12 and 3.14).
Separately, the BAML companion workflow's `source` and `wheel` jobs run on 3.12,
the companion's own minimum. No interpreter is chosen by event, and every job
that runs `uv` names its interpreter (setup-python or `UV_PYTHON`), so none
falls back to `.python-version`.

Workflow text (`.yml` and `.yaml`, comments and `echo` output included) is
checked by a plain-text scan. Quotes and backslashes are removed before
matching, so `-"p"`, `--pyth''on` and `\-p` count as their plain spellings.
Outside the floor jobs, these fail:

- `--python`;
- a `-p` option: a single `-` not preceded by a letter, digit or `-`, then
  letters including `p` (`-p`, `-qp`, `${X}-p`);
- `UV_PYTHON` in any case, and `PYENV_VERSION`;
- `python3.N`, `Python3NN` paths, and `python@N` or `pypy@`/`graalpy@` (but
  not `setup-python@`);
- `py -3.N`, `py -V:3.N` and `py.exe`;
- `uv python pin|install|find`;
- writes to `.python-version`;
- any `python-version` mention.

A canonical 3.14 setting at the start of a line is allowed: `python-version:`
or `UV_PYTHON:` set to 3.14, a literal list of only 3.14, or
`${{ matrix.python-version }}` over a literal matrix. The rest of that line is
still scanned. The named exclusions each cover only their own token:
`pytest -p no:`, `mkdir -p`, `tar -cpf`, the `test.yml` cache key
`}}-py${{ matrix.python-version }}`, and `setup-python@`.

The Linux platform-core floor is narrower than a whole job. It covers exactly
one literal include entry whose platform matches `linux`, in a job that runs on
`${{ matrix.platform }}`, and only that entry's own `python-version` line, when
the line holds nothing else.

YAML anchors and aliases are not allowed in workflows. This is a text scan: it
catches plain spellings and these common quoting tricks, not arbitrary shell
obfuscation, which review has to catch.
`tests/test_release_hygiene_policy.py` checks this layout
(treesitter-chunker#502).

The type gate compares complete messages and error codes, normalizing only
leading file locations. Literal values, numeric colons and backslashes inside
messages remain significant. For a diagnostic-format migration, measure and
reconcile the baseline from unchanged accepted code before candidate edits. A new
candidate's errors must be fixed or tracked separately. `--update` only
removes cleared signatures: when mypy reports a signature absent from the
baseline, it fails and leaves the file unchanged, so new errors cannot be
absorbed (treesitter-chunker#587).

`[tool.mypy] python_version` stays at the 3.12 floor, so the gate checks the
same target whichever interpreter runs it. On unchanged main its output was
identical under 3.12 and 3.14. Release validation runs the same lint, format
and type commands as CI; `tests/test_type_gate_policy.py` checks the type
commands in `ci.yml`, `release.yml`, this file and the release checklist.

For broad behavior changes, run the platform-core and full tiers locally:

```bash
uv run --locked --with toml --all-extras python scripts/run_platform_core.py --platform linux
uv run --locked --with toml --all-extras python scripts/run_full_suite.py
```

Use representative full-suite coverage to find behavior gaps; do not use
unsupported coverage claims or a blanket 95% requirement. Coverage slices
under treesitter-chunker#69 are accepted by their stated behavior contracts
and named mutations.

### Verification scratch

Put verification and review scratch, such as disposable checkouts, virtual
environments and generated outputs, under the inherited disk `TMPDIR`. Create
it with `tempfile.TemporaryDirectory`, `tempfile.mkdtemp` or `mktemp -d`, never
a literal `/tmp` path, and remove disposable trees in `finally` or an `EXIT`
trap. pytest's `tmp_path` already follows `TMPDIR`. On shared hosts the system
temporary directory can be RAM-backed, and scratch left there exhausts memory.
Fallbacks such as `${TMPDIR:-/tmp}` count as a literal `/tmp` path.

`tests/test_scratch_root_policy.py` rejects literal `/tmp` and `/dev/shm`
roots in tracked Python, shell, PowerShell and JavaScript/TypeScript scripts,
tools and tests. It matches literal spellings only. It does not scan
`archive/`, which keeps historical helpers unchanged as evidence, or the
product package `chunker/`.

### Platform checks

The POSIX SIGINT contract observes the actual CLI's return of parsed regular-file
fixture chunks, then signals it during a bounded Python pause installed by the
test harness. It drains both output pipes and reaps the child on success or
failure. This does not establish
interruption during arbitrary native parsing or blocked input reads.
Its readiness and shutdown bounds safeguard cleanup; they are not throughput
requirements. Windows deliberately skips this POSIX-only contract.

Reproduce a matrix failure with the narrow affected test before retrying CI.
Use explicit UTF-8 file I/O, portable paths, and robust process readiness
checks. Avoid assertions that depend on tight wall-clock limits.
The Python Unicode extraction fixture writes explicit UTF-8. The streaming
chmod-denial test exercises
actual POSIX read denial and cleanup; Windows deliberately skips it because
chmod does not provide a Windows ACL-denial contract.
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

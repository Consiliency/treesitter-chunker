# AGENTS.md

## Local-First CI Workflow

- Before relying on GitHub Actions, reproduce the Linux CI workflow locally.
- Use the project environment through `uv run`, not host-installed tools.
- Match the workflow dependency set with all optional extras plus `toml`.

### Preferred local validation loop

1. Run lint and format checks:
   - `uv run --all-extras ruff check chunker/ cli/ tests/ --exclude archive --exclude logs --exclude site`
   - `uv run --all-extras black --check chunker/ cli/ tests/ scripts/`
2. Run the fast CI-equivalent pytest command:
   - `uv run --with toml --all-extras python scripts/run_ci_smoke.py`
3. Only use GitHub Actions for cross-platform confirmation and matrix-specific failures.
4. Use the platform-core matrix workflow as confirmation, not as the primary place to discover broad regressions.

## Cross-Platform Triage

- If GitHub fails only on Windows or macOS, reproduce the narrow failing test locally first when possible.
- Favor platform-robust tests over platform-specific expectations.
- Before pushing changes that touch config, paths, temp files, extraction, fallback logic, or export formatting, run the standing Windows preflight batch on `win`:
  - `ssh win 'powershell -NoProfile -Command "cd $HOME\\code\\treesitter-chunker; git fetch origin; git checkout main; git pull --ff-only; uv run --with toml --all-extras python scripts/run_windows_preflight.py"'`
- Common failure classes in this repo:
  - Windows path separator and temp-file locking issues
  - Windows default encoding issues; prefer explicit `encoding="utf-8"`
  - macOS timing-sensitive assertions; avoid overly tight thresholds
  - multiprocessing spawn/pickling differences on macOS

## Changing the Boundary IR

- The canonical Boundary IR is guarded by a determinism gate: per-language
  golden snapshots (`tests/test_boundary_ir_golden_snapshots.py`), a non-empty
  extraction guard, and a fail-closed grammar/runtime pin assertion
  (`tests/test_boundary_ir_determinism.py`). Goldens cover all
  `SUPPORTED_BOUNDARY_LANGUAGES` (C# excluded until its grammar ABI is fixed).
- Any *intentional* Boundary IR change MUST be made by running
  `python scripts/regenerate_boundary_goldens.py` on the pinned, ABI-paired
  stack (tree_sitter 0.24 / tree-sitter-language-pack 0.9) and reviewing the
  resulting golden diff in the PR. The script is idempotent — running it twice
  produces no git diff.
- Do NOT hand-edit goldens and do NOT bump `tree_sitter` or
  `tree-sitter-language-pack` to make the gate pass: an unintended bump is
  exactly what `test_grammar_runtime_pins_match` exists to catch. Unintended IR
  changes fail loudly in CI by design.

## Notes

- The `mypy` step currently reports many pre-existing issues and is non-blocking in CI.
- The full serial `pytest -m "not integration"` suite is much slower than the fast CI-equivalent command; use targeted reruns for serial-only failures.
- The GitHub `CI` workflow is intentionally a smoke lane now; broad regression coverage belongs in local preflight and the `Test Suite` matrix workflow.
- The GitHub `Test Suite` workflow is intentionally a platform-core lane now; broad regression coverage should stay local, with `leno`, and with `macmini` before pushing.

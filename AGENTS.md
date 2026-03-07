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
   - `uv run --with toml --all-extras python -m pytest -n auto --timeout=60 --ignore=tests/integration/ -x -q`
3. Only use GitHub Actions for cross-platform confirmation and matrix-specific failures.

## Cross-Platform Triage

- If GitHub fails only on Windows or macOS, reproduce the narrow failing test locally first when possible.
- Favor platform-robust tests over platform-specific expectations.
- Common failure classes in this repo:
  - Windows path separator and temp-file locking issues
  - Windows default encoding issues; prefer explicit `encoding="utf-8"`
  - macOS timing-sensitive assertions; avoid overly tight thresholds
  - multiprocessing spawn/pickling differences on macOS

## Notes

- The `mypy` step currently reports many pre-existing issues and is non-blocking in CI.
- The full serial `pytest -m "not integration"` suite is much slower than the fast CI-equivalent command; use targeted reruns for serial-only failures.

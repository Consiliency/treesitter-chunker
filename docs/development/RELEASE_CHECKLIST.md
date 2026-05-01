# Release Checklist

> Maintainer/internal documentation. This page is intentionally omitted from
> public navigation and is linked from packaging and deployment guidance.

Use this checklist for any production PyPI release.

## Before You Release

- `main` is green in GitHub Actions
- choose one `TARGET_VERSION` in `X.Y.Z` form
- `pyproject.toml` has `TARGET_VERSION`
- the top `CHANGELOG.md` heading matches `TARGET_VERSION`
- no uncommitted local changes remain in the release branch

## Release Prep

```bash
uv run --with toml --all-extras pytest tests/test_cicd_pipeline.py -q
uv run --with toml --all-extras pytest tests/unit/distribution/test_release_manager.py tests/test_distribution_impl.py tests/test_phase13_contracts.py -q
uv run --with toml --all-extras python -m build --outdir "dist/phase9-release-check-${TARGET_VERSION}"
uv run --with toml --all-extras python -m twine check "dist/phase9-release-check-${TARGET_VERSION}"/*
```

Confirm the fresh wheel and sdist filenames both contain `TARGET_VERSION`.

## Standard Tag Release

```bash
git checkout main
git pull --ff-only
git tag vX.Y.Z
git push origin vX.Y.Z
```

Expected behavior:

- `.github/workflows/release.yml` builds distributions once
- the workflow creates a GitHub Release
- the workflow publishes to PyPI using trusted publishing

## Manual Release Dispatch

Use `workflow_dispatch` only when you intentionally want a controlled release run.

- the entered version must match `pyproject.toml`
- the release prep commit and local validation should already be complete
- prerelease runs should be used only for prerelease artifacts and validation
- production publishing still follows the guarded release workflow

## Guards That Must Pass

- tag format is `vX.Y.Z`
- tag version matches `pyproject.toml`
- the top `CHANGELOG.md` heading matches `TARGET_VERSION`
- version does not already exist on PyPI
- build and package checks succeed
- wheel artifact workflow uploads artifacts only and does not publish to PyPI

## Release Hygiene Gates

- `uv run --with toml --all-extras --with mkdocs --with mkdocs-material --with mkdocstrings-python mkdocs build --strict`
- `uv run --with toml --all-extras pytest tests/test_release_hygiene_policy.py tests/test_auto.py tests/test_fallback_chunking.py tests/test_overlapping_fallback.py -q`
- no xfail, xpass, or `pytest.mark.xfail` results in focused tests or smoke validation

## Registry Compatibility Gates

- `uv run --with toml --all-extras pytest -W error::DeprecationWarning tests/test_registry_fallback.py tests/test_registry.py -q`
- `uv run --with toml --all-extras pytest -W error::DeprecationWarning tests/test_factory.py tests/test_parser.py tests/test_chunking.py -q`
- `uv run --with toml --all-extras pytest -W error::DeprecationWarning tests/test_cli.py tests/test_boundary_ir_golden_snapshots.py -q`

## Local-First Validation

- `uv run --all-extras ruff check chunker/ cli/ tests/ --exclude archive --exclude logs --exclude site`
- `uv run --all-extras black --check chunker/ cli/ tests/ scripts/`
- `uv run --with toml --all-extras python scripts/run_ci_smoke.py`
- `uv run --with toml --all-extras python scripts/run_platform_core.py --platform linux`
- `ssh win 'powershell -NoProfile -Command "cd $HOME\\code\\treesitter-chunker; git fetch origin; git checkout main; git pull --ff-only; uv run --with toml --all-extras python scripts/run_windows_preflight.py"'`

Confirm `git status --short` is clean before creating or pushing the release tag. Ignored package artifacts under `dist/` may remain locally.

## After Release

- confirm the GitHub Release exists with expected artifacts
- confirm the new version is visible on PyPI
- test installation from PyPI in a clean environment
- spot-check `treesitter-chunker --version`

## If Release Fails

- tag/version mismatch: fix `pyproject.toml` or retag
- version already exists: bump version and retry with a new tag
- build issue: reproduce locally with `uv run --with toml --all-extras python -m build` and `uv run --with toml --all-extras python -m twine check`

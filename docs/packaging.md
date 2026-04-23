# Packaging and Release Guide

This document is the source of truth for packaging and PyPI publishing.

## Current Release Model

- `main` CI validates code, docs, and tests only; it does not publish to PyPI
- `.github/workflows/release.yml` is the only workflow that publishes to PyPI
- `.github/workflows/build-wheels.yml` builds wheel artifacts but does not publish them
- Production publishing uses GitHub trusted publishing
- A release tag must match the version in `pyproject.toml`

## Version Source of Truth

- Package version lives in `pyproject.toml`
- Release tags must use the form `vX.Y.Z`
- `release.yml` fails if the tag and package version differ
- `release.yml` also fails if that version already exists on PyPI

## Standard Release Flow

1. Make sure `main` is green
2. Choose one `TARGET_VERSION` in `X.Y.Z` form
3. Bump `pyproject.toml` to `TARGET_VERSION`
4. Update the top `CHANGELOG.md` entry to `TARGET_VERSION`
5. Run the focused release tests and local package checks
6. Commit the release prep
7. Confirm the working tree is clean
8. Create and push a tag such as `v2.2.23`
9. Let `release.yml` build distributions, create the GitHub Release, and publish to PyPI

See `docs/development/RELEASE_CHECKLIST.md` for the maintainer checklist.

## Manual Release Dispatch

`release.yml` also supports `workflow_dispatch`.

- Use manual dispatch when you need a controlled release run without pushing a tag first
- The entered version must still match `pyproject.toml`
- Prerelease runs may create GitHub release artifacts without publishing to production PyPI, depending on the selected prerelease input

## Local Packaging Commands

Local package building is still useful for validation and troubleshooting.

```bash
TARGET_VERSION=2.2.23
OUTDIR="dist/phase9-release-check-${TARGET_VERSION}"
uv run --with toml --all-extras python -m build --outdir "$OUTDIR"
uv run --with toml --all-extras python -m twine check "$OUTDIR"/*
```

Optional wheel helper:

```bash
python scripts/build_wheels.py --platform auto
```

These local commands do not publish to PyPI.

## What Publishes to PyPI

Only this path publishes production packages:

- trigger: `push` tag `v*` or approved manual release dispatch
- workflow: `.github/workflows/release.yml`
- auth: trusted publishing

The repository no longer has a second token-based publish path in `build-wheels.yml`.

## Troubleshooting

- Tag/version mismatch: update `pyproject.toml` or retag before rerunning
- Version already on PyPI: bump the version; do not reuse an existing release number
- Build failure: reproduce locally with `uv run --with toml --all-extras python -m build` and `uv run --with toml --all-extras python -m twine check`
- Wheel issues: use `python scripts/build_wheels.py --platform auto` for local diagnosis

## Related Docs

- `docs/development/RELEASE_CHECKLIST.md`
- `specs/release-process-spec.md`
- `.github/workflows/release.yml`
- `.github/workflows/build-wheels.yml`

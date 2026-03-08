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
2. Bump `pyproject.toml` to the target version
3. Update `CHANGELOG.md` if needed
4. Commit the release prep
5. Create and push a tag such as `v2.2.4`
6. Let `release.yml` build distributions, create the GitHub Release, and publish to PyPI

See `docs/development/RELEASE_CHECKLIST.md` for the maintainer checklist.

## Manual Release Dispatch

`release.yml` also supports `workflow_dispatch`.

- Use manual dispatch when you need a controlled release run without pushing a tag first
- The entered version must still match `pyproject.toml`
- Prerelease runs may create GitHub release artifacts without publishing to production PyPI, depending on the selected prerelease input

## Local Packaging Commands

Local package building is still useful for validation and troubleshooting.

```bash
python scripts/fetch_grammars.py
python scripts/build_lib.py
python -m build
python -m twine check dist/*
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
- Build failure: reproduce locally with `python -m build` and `python -m twine check dist/*`
- Wheel issues: use `python scripts/build_wheels.py --platform auto` for local diagnosis

## Related Docs

- `docs/development/RELEASE_CHECKLIST.md`
- `specs/release-process-spec.md`
- `.github/workflows/release.yml`
- `.github/workflows/build-wheels.yml`

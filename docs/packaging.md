# Packaging and Release Guide

This document is the source of truth for packaging and PyPI publishing.

## Current Release Model

- `main` CI validates code, docs, and tests only; it does not publish to PyPI
- `.github/workflows/release.yml` is the only workflow that publishes to PyPI
- `.github/workflows/build-wheels.yml` builds wheel artifacts but does not publish them
- Production publishing uses GitHub trusted publishing
- A release tag must match the version in `pyproject.toml`
- The PyPI release workflow requires the full `tests/` and `spec_tests/` tier,
  lint, formatting and the baseline type gate on Python 3.11, 3.12 and 3.13.
  A failing or timed-out validation job blocks its build and publication jobs.
- The built wheel is installed in a fresh environment using hashed, locked runtime
  dependencies and exercised outside the source checkout. Distribution checksums
  are retained with the artifacts and verified before publication.

### Native package status for the v5 candidate

The owner approved **PyPI-only v5 distribution on 2026-09-11**. Debian, RPM and
Homebrew distribution is suspended. `.github/workflows/packages.yml` has no tag
trigger, build, artifact upload or release job. Manual dispatch fails with an
explicit suspension notice. The recipes under `packaging/` are retained for
future repair, but are not supported v5 installation methods. This decision does
not disable local source builds or local grammar compilation.

### Native distribution rebuild backlog

Re-enablement is deferred beyond this v5 PyPI scope. Close all of the following
before restoring native release triggers or advertising native installation:

- **Debian:** reconcile all runtime dependencies and supported Python/parser
  ranges with `pyproject.toml`; fix the build/install procedure and verify a
  clean installation with no undeclared dependencies.
- **RPM:** derive the version from the release source, declare complete runtime
  dependencies, and correct architecture metadata for bundled native libraries.
- **Homebrew:** replace the obsolete source URL/version, placeholder checksum,
  Python/runtime resources and CLI test with verified release inputs.
- **All three:** establish grammar artifact hashes, acquisition and offline cache
  behavior for the supported OS/architecture matrix; run clean package install,
  CLI, parser and dependency checks. Record supported platform minimums.
- **Publication:** require the accepted source-validation gate and verified
  artifacts before any native asset upload. Review the exact recipe/workflow
  candidate and its platform receipts before restoring distribution.

This suspension resolves the native release-path scope question only. The v5
candidate still has unresolved full-suite failures and has not been released.

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
5. Run the focused release tests, hygiene gates, registry gates, and local package checks
6. Run the repo local-first validation loop plus Linux platform-core and Windows preflight on `win`
7. Commit the release prep
8. Confirm the tracked working tree is clean
9. Create and push a tag such as `v2.2.24`
10. Let `release.yml` build distributions, create the GitHub Release, and publish to PyPI

See `docs/development/RELEASE_CHECKLIST.md` for the maintainer checklist.

## Manual Release Dispatch

`release.yml` also supports `workflow_dispatch` after the same version bump and local validation steps.

- Use manual dispatch when you need a controlled release run without pushing a tag first
- The entered version must still match `pyproject.toml`
- Prerelease runs may create GitHub release artifacts without publishing to production PyPI, depending on the selected prerelease input

## Local Packaging Commands

Local package building is still useful for validation and troubleshooting.

```bash
TARGET_VERSION=2.2.24
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
- `specs/active/release-process-spec.md`
- `.github/workflows/release.yml`
- `.github/workflows/build-wheels.yml`

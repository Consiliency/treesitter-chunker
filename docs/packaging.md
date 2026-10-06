# Packaging and Release Guide

This document is the source of truth for packaging and PyPI publishing.

## Current Release Model

The optional BAML grammar is a separate native distribution at
`treesitter-chunker-baml-grammar==0.1.0`. Its
`.github/workflows/baml-grammar-wheels.yml` release uses the
`baml-grammar-pypi` trusted publishing environment and a
`baml-grammar-v*` tag. It publishes `cp311-abi3` wheels for Linux glibc
x86_64/aarch64, macOS x86_64/arm64, and Windows x86_64, tested on Python
3.11–3.13, plus an sdist. Other platforms require a compiler for the sdist.
The main `treesitter-chunker` wheel stays `py3-none-any`; the BAML native
artifact is installed only by the `baml` extra. Both packages must be installed
before offline BAML parsing, which then needs no network or compiler.

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

### Native package status for v5

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

The main package is published on PyPI; native system packages remain suspended.
See the [release history](https://github.com/Consiliency/treesitter-chunker/releases)
for published versions.

## Parser artifact integrity and offline custody

The Python lock authenticates the selected package distributions, not every
first-use native parser download. In language-pack 1.20.0's
[download implementation](https://github.com/xberg-io/tree-sitter-language-pack/blob/v1.20.0/crates/ts-pack-core/src/download.rs),
new and cached bundle archives are checked against SHA-256 values in the parser
manifest. That manifest is fetched separately from the versioned upstream release
(or a configured mirror); its digest is not pinned in this repository's lock.
Package version pinning therefore does not independently freeze those remote bytes.

For reproducible/offline installations, retain the tested platform's manifest,
bundle and extracted grammar hashes alongside the wheel hash, prefetch required
languages while online, and validate the prepared cache with networking disabled.
Do not treat a cache directory from a different OS/architecture as interchangeable.
The accepted binary Linux path uses glibc 2.34 or newer. musl and older-glibc
source-build/runtime paths have not been accepted for the current parser stack.

## Version Source of Truth

- Package version lives in `pyproject.toml`
- Release tags must use the form `vX.Y.Z`
- `release.yml` fails if the tag and package version differ
- `release.yml` also fails if that version already exists on PyPI

## Standard Release Flow

1. Make sure `main` is green
2. Choose one `TARGET_VERSION` in `X.Y.Z` form
3. Bump `pyproject.toml` and the version mirrors in `chunker/__init__.py` and
   `chunker/_version.py` to `TARGET_VERSION`; regenerate `uv.lock` with the uv
   version pinned in `release.yml` and review the diff for unrelated pin changes
4. Update the top `CHANGELOG.md` entry to `TARGET_VERSION`
5. Run the focused release tests, hygiene gates, registry gates, and local package checks
6. Run the repo local-first validation loop plus Linux platform-core and Windows preflight on `win`
7. Commit the release prep
8. Confirm the tracked working tree is clean
9. Create and push the matching `vX.Y.Z` tag
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
TARGET_VERSION=5.2.0  # Use the version in pyproject.toml
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

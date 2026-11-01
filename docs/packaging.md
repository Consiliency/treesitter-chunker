# Packaging and Release Guide

This document is the source of truth for packaging and PyPI publishing.

Development and the next release require Python >=3.12. Python 3.14 is the main
version: CI, the scheduled full tier and release validation run on it, and the
locked development environment installs from wheels on it
(treesitter-chunker#502). The 3.12 minimum keeps Linux platform-core and
installed-wheel checks until the next major release (7.0) drops it
(treesitter-chunker#599). Already published 6.0.0 keeps its original >=3.11
metadata.

## Current Release Model

The optional BAML grammar is a separate native distribution at
`treesitter-chunker-baml-grammar==0.1.0`. Its
`.github/workflows/baml-grammar-wheels.yml` release uses the
`baml-grammar-pypi` trusted publishing environment and a
`baml-grammar-v*` tag. It publishes `cp311-abi3` wheels for Linux glibc
x86_64/aarch64, macOS x86_64/arm64, and Windows x86_64, tested on Python
3.11–3.13, plus an sdist. Other platforms require a compiler for the sdist.
The companion source now requires >=3.12 and builds `cp312-abi3` wheels. Its
workflow tests each native target during the 3.12 build and installs the wheel
outside checkout on 3.14. These source changes need a separate future companion
version and release; they do not replace published 0.1.0 or change the main
package's existing optional dependency pin.
The main `treesitter-chunker` wheel stays `py3-none-any`; the BAML native
artifact is installed only by the `baml` extra. Both packages must be installed
before offline BAML parsing, which then needs no network or compiler.

- `main` CI validates code, docs, and tests only; it does not publish to PyPI
- `.github/workflows/release.yml` is the only workflow that publishes to PyPI
- `.github/workflows/build-wheels.yml` is a manual-only wheel artifact helper;
  obsolete duplicate tag builds were removed, so release tags build once
- Production publishing uses GitHub trusted publishing
- A release tag must match the version in `pyproject.toml`
- The PyPI release workflow requires the full `tests/` and `spec_tests/` tier,
  lint, formatting, the baseline type gate and the governed-tools type check on
  Python 3.14. Installed-wheel checks below cover the 3.12 floor.
  A failing or timed-out validation job blocks its build and publication jobs.
- The built wheel is installed in a fresh environment using hashed, locked runtime
  dependencies and exercised outside the source checkout. Distribution checksums
  are retained with the artifacts and verified before publication. Installed-wheel
  verification runs on both Python 3.12 and 3.14.

### Native package status

The owner approved **PyPI-only v5 distribution on 2026-09-11**. Debian, RPM and
Homebrew distribution remains suspended for 6.0.0. `.github/workflows/packages.yml` has no tag
trigger, build, artifact upload or release job. Manual dispatch fails with an
explicit suspension notice. The recipes under `packaging/` are retained for
future repair, but are not supported installation methods. This decision does
not disable local source builds or local grammar compilation.

### Native distribution rebuild backlog

Re-enablement remains deferred beyond this PyPI release scope. Close all of the following
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

The main package requires the exact official
`tree-sitter-python==0.25.0` and `tree-sitter-javascript==0.25.0` distributions
for default Python and JavaScript parsing. Their `cp310-abi3` wheels cover the
supported CPython 3.12–3.14 range on Linux glibc/musl x86_64 and aarch64,
macOS x86_64/arm64, and Windows x86_64/arm64. These installed wheel grammars
take precedence over `tree-sitter-language-pack` for the two languages because
the standalone pack 1.20 grammars remain affected by treesitter-chunker#492.
Explicit compiled custom grammars still take priority and remain under the
caller's artifact and ABI custody.

The Python lock authenticates the selected package distributions, not every
first-use native parser download. In language-pack 1.20.0's
[download implementation](https://github.com/xberg-io/tree-sitter-language-pack/blob/v1.20.0/crates/ts-pack-core/src/download.rs),
new and cached bundle archives are checked against SHA-256 values in the parser
manifest. That manifest is fetched separately from the versioned upstream release
(or a configured mirror); its digest is not pinned in this repository's lock.
Package version pinning therefore does not independently freeze those remote bytes.

For reproducible/offline installations, retain the tested platform's official
Python/JavaScript grammar wheel hashes and the pack manifest, bundle and
extracted grammar hashes alongside the Chunker wheel hash. Prefetch required
pack languages while online and validate the prepared cache with networking disabled.
Do not treat a cache directory from a different OS/architecture as interchangeable.
The accepted binary Linux path uses glibc 2.34 or newer. musl and older-glibc
source-build/runtime paths have not been accepted for the current parser stack.

## Version Source of Truth

- Package version lives in `pyproject.toml`
- Release tags must use the form `vX.Y.Z`
- `release.yml` fails if the tag and package version differ
- `release.yml` also fails if that version already exists on PyPI
- Update the reviewed wheel payload inventory/version in `chunker/build/builder.py`
  and its source-parity tests when changing the release version or required files.

## Public wheel structural verification

`chunker.build.BuildSystem.verify_build` and `BuildSystemImpl.verify_build` check
the current unreleased `treesitter-chunker` 6.0.0 source profile: Python >=3.12,
the paired Tree-sitter runtime/language-pack ranges, and the exact official
Python/JavaScript grammar dependencies. The embedded required-minimum inventory
contains 330 Python modules/resources, including `py.typed` and the Boundary IR
schema. It is independent of candidate contents and the installed filesystem.
Unknown versions or other profiles are outside this verifier's supported payload
contract. In particular, published 6.0.0 retains >=3.11 metadata and is not
retroactively accepted by this source-profile verifier. Rejection on that basis
does not establish that an older published artifact is corrupt.

The verifier requires one top-level metadata directory, direct METADATA, WHEEL,
RECORD and entry-point files, consistent distribution identity and expanded tags,
and the exact commands `treesitter-chunker` and `tsc`, both targeting
`cli.main:app`. It checks ZIP CRCs; RECORD presence is structural, not digest
authentication. Required payload may be relocated once under the matching
distribution's `.data/purelib` or `.data/platlib`. Duplicate members, noncanonical
file paths and multiple members mapping to one installation destination fail,
even with equal bytes. This is a lexical destination check, not an exhaustive
installer or host-filesystem audit.

Universal wheels need no bundled grammar and reject native filenames anywhere
in the archive, including case variants and versioned shared-library suffixes.
Native wheel compatibility checks require a platform-matching grammar directly
under normalized `chunker/data/grammars/build`. No candidate is installed or
native-loaded by verification. Filename classification cannot detect disguised
native bytes. A structurally valid result establishes neither provenance, ABI
compatibility, native admission safety nor `NativeProbeResult.supported`.

Reports retain existing keys and add `components.missing_payload`, the exact
missing paths, with `missing_modules` as its Python-only subset. Any missing
payload sets `package=false`; errors or missing requirements make `valid=false`.
A trusted verifier installation supplies the completeness policy; a maliciously
replaced verifier or an installation missing the verifier itself is outside this
contract. Future source/version changes require explicit inventory and parity
test maintenance; the inventory digest describes path names, not trusted bytes.

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
TARGET_VERSION=6.0.0  # Use the version in pyproject.toml
OUTDIR="dist/phase9-release-check-${TARGET_VERSION}"
uv run --locked --all-extras --python 3.12 python -m build --outdir "$OUTDIR"
uv run --locked --all-extras --python 3.12 python -m twine check "$OUTDIR"/*
```

The main package uses the standard build command above for its universal
`py3-none-any` wheel and sdist. The old `scripts/build_wheels.py` helper and
root platform-specific cibuildwheel recipes are retired; `scripts/package.py`
also builds its wheel through `python -m build` without optional platform builds.
The native BAML companion keeps its separate build configuration and workflow.
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
- Build failure: reproduce with the locked local build and twine commands above
- Wheel issues: rerun the locked local `python -m build` command above and inspect its output

## Related Docs

- `docs/development/RELEASE_CHECKLIST.md`
- `specs/active/release-process-spec.md`
- `.github/workflows/release.yml`
- `.github/workflows/build-wheels.yml`

# Release Process Spec

- **File**: `specs/active/release-process-spec.md`
- **Owner**: Core Chunker Team
- **Status**: Active
- **Purpose**: Define the supported GitHub-to-PyPI release process

## Invariants

- Production PyPI publishing happens only through `.github/workflows/release.yml`
- `.github/workflows/build-wheels.yml` may build artifacts but does not publish to PyPI
- Production publishing uses GitHub trusted publishing
- Ordinary `push`/`pull_request` CI on `main` never publishes to PyPI
- Release tags must use the form `vX.Y.Z`
- The tag version must exactly match `pyproject.toml`
- The release workflow must fail before publish if that version already exists on PyPI
- Build and publication depend on full source validation across Python 3.11–3.13
- The built wheel must pass a fresh installation with hashed locked runtime requirements
- Missing artifacts or checksum verification failures stop publication
- v5 distribution is PyPI-only (owner decision, 2026-09-11); Debian/RPM/Homebrew
  distribution is suspended. `packages.yml` has no automatic trigger or publication
  path, and manual dispatch fails. Re-enablement requires the rebuild gates in
  `docs/packaging.md`.

## Supported Release Triggers

1. Push a version tag `vX.Y.Z`
2. Run `release.yml` via `workflow_dispatch`

## Standard Release Flow

1. Merge code to `main`
2. Verify CI is green
3. Bump `pyproject.toml`
4. Update the top `CHANGELOG.md` entry
5. Run the focused release-policy tests, hygiene and registry gates, package build/check, and local-first platform validation
6. Confirm the tracked worktree is clean
7. Push the release tag
8. Let `release.yml` build distributions, create the GitHub Release, and publish to PyPI

## Non-Goals

- Publishing every successful `main` commit to PyPI
- Maintaining multiple production PyPI publish workflows
- Treating local helper scripts as the production release authority

## Operational References

- `docs/packaging.md`
- `docs/development/RELEASE_CHECKLIST.md`
- `.github/workflows/release.yml`
- `.github/workflows/build-wheels.yml`

# Release Checklist

Use this checklist for any production PyPI release.

## Before You Release

- `main` is green in GitHub Actions
- `pyproject.toml` has the target version
- release notes or changelog updates are ready
- no uncommitted local changes remain in the release branch

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
- prerelease runs should be used only for prerelease artifacts and validation
- production publishing still follows the guarded release workflow

## Guards That Must Pass

- tag format is `vX.Y.Z`
- tag version matches `pyproject.toml`
- version does not already exist on PyPI
- build and package checks succeed

## After Release

- confirm the GitHub Release exists with expected artifacts
- confirm the new version is visible on PyPI
- test installation from PyPI in a clean environment
- spot-check `treesitter-chunker --version`

## If Release Fails

- tag/version mismatch: fix `pyproject.toml` or retag
- version already exists: bump version and retry with a new tag
- build issue: reproduce locally with `python -m build` and `python -m twine check dist/*`

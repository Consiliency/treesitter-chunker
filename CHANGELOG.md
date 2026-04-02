# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [2.2.21] - 2026-03-13

### 🐛 Bug Fixes

- **Suppress spurious WARNING/ERROR log messages on import** (closes #66): Downgraded `logger.warning`/`logger.error` calls in `chunker/_internal/registry.py` to `logger.debug` for expected fallback conditions — missing combined `.so` at `__init__`, `OSError` in `_load_library`, and failed probe attempts in `_try_load_from_individual_library`. These fired on every PyPI install where no precompiled grammar library exists; the fallback to `tree-sitter-language-pack` is fully functional and silent.

---

## [2.2.20] - 2026-03-13

### 🔧 CI/CD

- **Automated CHANGELOG via git-cliff**: Added `orhun/git-cliff-action@v4` to the Release workflow; `CHANGELOG.md` is now updated and committed to `main` automatically on every tagged release
- **git-cliff config**: Added `cliff.toml` with conventional-commit grouping (Features, Bug Fixes, CI/CD, Documentation, etc.) and skip rules for release-bump commits

---

## [2.2.19] - 2026-03-13

### 🔧 CI/CD

- **Fix git-cliff install**: Replaced broken manual `curl` install of git-cliff with `orhun/git-cliff-action@v4` GitHub Action

---

## [2.2.18] - 2026-03-13

### 🐛 Bug Fixes

- **Suppress spurious WARNING log messages on import** (closes #65): Downgraded 15 `logging.warning()` calls to `logging.debug()` in optional-component try/except blocks across `production_validator.py`, `final_integration_tests.py`, and `grammar_management/cli.py`. These warnings fired on every import even when all primary APIs worked correctly, polluting server logs.

### 🔧 CI/CD

- **Full CI/CD pipeline repair**: Fixed all broken workflows across 14 patch releases (v2.2.5–v2.2.18):
  - `build-wheels.yml`: Replaced `cibuildwheel`+`auditwheel` with `python -m build --wheel` (pure-Python package; `auditwheel` rejects `py3-none-any` wheels)
  - `release.yml`: Excluded `checksums.txt` from distribution artifact — `pypa/gh-action-pypi-publish` rejected non-distribution files
  - `packages.yml` RPM: Fixed `python3-tree-sitter` (not in Fedora DNF → pip); replaced deprecated `%py3_build`/`%py3_install` with `%pyproject_wheel`/`%pyproject_install`; installed grammar script deps via `pip3 install .`; fixed artifact upload using absolute paths; suppressed empty debug package error
  - `packages.yml` DEB: Replaced broken pybuild approach (no `pybuild-plugin-pyproject` in Debian bookworm) with manual pip-based `debian/rules`; removed conflicting `debian/compat` file; fixed version extraction from `pyproject.toml` instead of `git describe`; fixed `.deb` artifact upload path
  - Removed broken `build-homebrew` job (Homebrew requires formulae in a registered tap)

---

## [2.2.4] - 2026-03-08

### 🐛 Bug Fixes

- **Grammar registry**: Detect dev-build grammars correctly in local/development checkouts (`fix(registry): detect dev build grammars`)
- **Grammar fallback**: Soften missing combined-library fallback log level to avoid noise in normal operation
- **Release**: Publish only distribution files to PyPI (exclude checksums)
- **Release**: Enable publishing on manual non-prerelease runs
- **Build**: Update cibuildwheel test configuration

---

## [2.2.3] - 2026-03-07

### ✨ Features

- **Symbol extraction and import resolution**: Python extractor now produces a full symbol graph with import tracking; symbol metadata included in chunk output for code search and RAG use cases
- **CLI module**: New `treesitter-chunker` CLI with `symbol`, `cluster`, and `repo` subcommands for batch processing, symbol extraction, and hierarchical clustering
- **Hierarchical clustering**: Leiden-algorithm-based clustering module for grouping related code symbols across a repository
- **Retrieval enrichment**: Chunk output enriched with semantic metadata to improve LLM retrieval quality (closes #62)

### 🐛 Bug Fixes

- **Cross-platform test stabilization**: Extensive hardening across Windows, macOS, and Linux for path handling, timing baselines, encoding defaults, and temp-file cleanup

---

## [2.2.2] - 2026-03-05

### 🐛 Bug Fixes

- **Cross-file relationship detection** (closes #58): Fixed `ASTRelationshipTracker` to correctly detect and emit cross-file relationships — previously all files appeared as isolated nodes in the dependency graph

---

## [2.2.1] - 2026-03-04

### 🐛 Bug Fixes

- **ABI compatibility**: Fallback to `tree-sitter-language-pack` when compiled grammar ABI mismatches the installed `tree-sitter` version, enabling resilient language support across environments

### 🔧 CI/CD

- Hardened CI against infrastructure failures; isolated git operations; added parallel test execution; improved timeout configuration

---

## [2.2.0] - 2026-03-03

### ✨ Features

- **tree-sitter-language-pack integration**: Added `tree-sitter-language-pack` as a pre-compiled grammar dependency, enabling out-of-box language support without grammar compilation on fresh installs (closes #51)
- **Language pack fallback registry**: Automatic fallback to language pack when compiled grammars are unavailable or incompatible
- **Actionable error messages**: Improved error messages with install guidance when language support is missing

---

## [2.1.0] - 2026-01-02

### ✨ Features

- **SemanticGraphBundle export**: New `SemanticGraphBundle` export format for the semantic-lens integration

---

## [2.0.4] - 2025-12-27

### ✨ Features

- REQ-TSC-008: Reconcile dependencies vs references for REFERENCES edges
- REQ-TSC-011: Add content-insensitive `definition_id` for stable cross-version chunk identity

---

## [2.0.3] - 2025-11-28

### 🐛 Bug Fixes

- Add missing `ConfigurationError` class to `exceptions.py`

---

## [2.0.2] - 2025-11-28

### 🐛 Bug Fixes

- **CI**: Fix PyPI publishing workflow
- **CI**: Add `contents:read` permission and make artifact download optional
- **CI**: Remove `submodules:recursive` from checkout (stale submodule refs)
- **CI**: Install package before building and remove grammar fetch steps
- Make `toml` import optional to fix `ImportError` in v2.0.1

# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

## [1.0.0] - 2026-01-02

Test release

## [1.0.0] - 2026-01-02

Release notes

## [1.0.1] - 2026-01-02

Patch release

## [2.0.4] - 2025-12-27

### ✨ Features

- **Content-insensitive definition_id (REQ-TSC-011)**: Added `definition_id` field to `CodeChunk` that provides a stable identifier based on symbol location and structure, independent of content changes. This enables reliable tracking of code entities across versions.
- **Enhanced cross-reference graph (REQ-TSC-008)**: Improved `build_xref` to better reconcile dependencies vs references for REFERENCES edges, providing more accurate relationship mapping in code graphs.

### 🧪 Testing

- **ConfigurationError test coverage**: Added comprehensive test suite for `ConfigurationError` exception class in `tests/test_exceptions.py`
- **Fixed test imports**: Updated `tests/test_config_advanced_scenarios.py` to use the real `ConfigurationError` class instead of workaround

### 🔧 Workflow Improvements

- **Updated CI/CD workflows**: Removed Python 3.10 from test matrices to match `requires-python = ">=3.11"` requirement
- **Improved linting**: Scoped ruff checks to production code and tests, excluding archive and logs directories
- **Enhanced test coverage**: Added `ConfigurationError` to exception hierarchy and error message formatting tests

---

## [2.0.3] - 2025-11-28

### 🐛 Bug Fix

- **Added ConfigurationError class**: Added the missing `ConfigurationError` exception class to `chunker/exceptions.py` that was referenced by `chunker/utils/json.py` but never committed

---

## [2.0.2] - 2025-11-28 [YANKED]

**Note**: This version is missing the `ConfigurationError` class. Use v2.0.3 instead.

### 🐛 Bug Fix

- **Fixed ImportError on module import**: Made `toml` import optional in `chunker/processors/config.py` to fix ImportError that prevented any chunker imports in v2.0.1

---

## [2.0.1] - 2025-11-27 [YANKED]

**Note**: This version has critical bugs - the `toml` package import fails, and `ConfigurationError` is missing. Use v2.0.3 instead.

### 🔧 Pre-Production Finalization (v4 Spec)

#### Internal Improvements
- **Safe Decode Migration**: Migrated 11 language plugins to use centralized `safe_decode_bytes` utility from `chunker/utils/text.py` for consistent UTF-8 handling with graceful fallback on encoding errors
  - Affected plugins: clojure, go, vue, zig, haskell, sql, python, cs_plugin, scala, java_plugin, elixir
- **JSON Loading Consistency**: Migrated JSON configuration loading to use centralized `load_json_file` utility from `chunker/utils/json.py` for consistent error handling
  - `chunker/grammar/repository.py`: Custom grammar repository loading
  - `chunker/chunker_config.py`: ChunkerConfig JSON support
  - `chunker/config/strategy_config.py`: StrategyConfig JSON support

#### Error Handling
- JSON parsing errors now raise `ConfigurationError` with detailed line/column information
- Invalid UTF-8 in source files handled gracefully with replacement characters

#### API Surface
- No breaking changes to public API
- All function signatures in `chunker/__init__.py` unchanged
- HTTP API endpoints in `api/server.py` unchanged

#### Testing
- All existing tests pass
- New validation tests for utility functions
- Security tests verified (no `shell=True`, no bare `except:`)

---

## [2.0.0] - 2025-08-20

### 🚀 Major Release - Production Ready with Performance Optimization

#### ✨ New Features
- **Performance Core Framework**: Centralized performance management with 30-40% improvements
- **System Optimization Engine**: Intelligent CPU, memory, and I/O optimization
- **Validation Framework**: Comprehensive testing with load, stress, and endurance testing
- **Production Deployment**: Automated deployment with <30 second rollback capability
- **Monitoring & Observability**: Real-time metrics with Prometheus integration
- **Smart Error Handling**: Intelligent error classification and user guidance system
- **User Grammar Management**: CLI tools and user grammar directory support
- **Language-Specific Extractors**: Call-site byte span extraction for 30+ languages
- **Plugin System**: Extensible language plugin architecture

#### 🔧 Performance Improvements
- **Memory Usage**: 30-40% reduction through optimization
- **CPU Efficiency**: 20-25% improvement in processing
- **Cache Hit Rate**: 85-90% achieved
- **Response Time**: 15-20% reduction in latency
- **Load Testing**: Handles 100+ concurrent operations, stable under 2x normal load

#### 🏗️ Architecture Enhancements
- **Thread-safe Operations**: Throughout all components
- **Graceful Degradation**: Automatic recovery mechanisms
- **Resource Pooling**: Efficient memory and thread management
- **Multi-level Caching**: Intelligent cache management with memory pooling
- **Performance Budgets**: Resource limit enforcement and monitoring

#### 📚 Documentation & Quality
- **Comprehensive Documentation**: User guides, API references, deployment guides
- **Quality Assurance**: Automated testing with 88% average coverage
- **Example Validation**: 94.4% success rate for all documentation examples
- **Documentation Servers**: MkDocs and Sphinx integration
- **Security & Support**: Security policies, contributing guidelines, troubleshooting

#### 🌍 Language Support
- **Extended Language Coverage**: 30+ programming languages supported
- **Tree-sitter Grammars**: Comprehensive grammar compilation and management
- **Plugin Architecture**: Easy addition of new language support
- **Consistent API**: Unified interface across all languages

#### 🚀 Production Features
- **Deployment Time**: < 5 minutes full deployment
- **Rollback Time**: < 30 seconds automated rollback
- **Health Check Time**: < 5 seconds comprehensive checks
- **Alert Response**: < 1 second alert generation
- **Zero-downtime Deployments**: Blue-green and canary deployment strategies

#### 🧪 Testing & Validation
- **450+ Test Cases**: Comprehensive unit and integration testing
- **Performance Testing**: Load, stress, endurance, and spike testing
- **Regression Testing**: Automated regression detection and prevention
- **Integration Testing**: End-to-end workflow validation
- **Quality Assurance**: Automated code quality and documentation validation

### Breaking Changes
- **Python Version**: Now requires Python 3.10+ (was 3.8+)
- **API Changes**: Some internal APIs have been refactored for better performance
- **Configuration**: New configuration options for performance tuning

### Migration Guide
- Update Python version to 3.10+
- Review configuration files for new performance options
- Test performance profiles in development before production deployment

---

## [1.0.9] - 2024-12-19

### Added
- Enhanced error handling for grammar compilation failures
- Better support for Windows environments
- Improved logging for debugging

### Changed
- Updated dependency versions for better compatibility
- Enhanced README with more examples

### Fixed
- Grammar compilation issues on certain Linux distributions
- Memory leak in long-running processes
- Path handling issues on Windows

## [1.0.8] - 2024-11-15

### Added
- Support for additional programming languages
- Performance improvements in chunking algorithms
- Better error messages for common issues

### Changed
- Improved memory usage for large files
- Enhanced grammar caching mechanism

### Fixed
- Issue with certain grammar versions not being detected
- Memory leak in grammar manager

## [1.0.7] - 2024-10-20

### Added
- Initial release of treesitter-chunker
- Core chunking functionality
- Support for Python, JavaScript, and Rust
- Basic grammar management

### Changed
- N/A

### Fixed
- N/A
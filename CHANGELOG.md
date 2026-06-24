# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [3.2.0] - 2026-06-24

ADDITIVE minor — turnkey C# + a future-proof tree-sitter runtime, proven
byte-stable for every existing language by the new determinism gate.

### ✨ Added / Changed

- **runtime**: Bumped the tree-sitter runtime `tree_sitter>=0.24,<0.25` →
  `>=0.25,<0.26` (now supports grammar ABI 13–15), keeping
  `tree-sitter-language-pack>=0.9,<1.0`. Purely additive: the determinism gate
  confirms the canonical Boundary IR is **byte-identical** for all
  previously-supported languages, Python included. NOTE: this byte-stability
  holds because the language-pack is **held at 0.9.0** — the runtime bump alone
  does not change Python's IR. (A pack *float* to ≥1.x ships a newer Python
  grammar that drops the `docstring:` line; the pack `<1.0` upper bound — asserted
  fail-closed by the determinism gate — is the load-bearing guard. This was NOT a
  docstring "fix"; nothing in extraction changed.) No consumer re-index required.
  **Downstream:** consumers (e.g. spec's realized Python gate) stay byte-stable
  only if they likewise resolve language-pack 0.9.x; floating to ≥1.x inherits the
  docstring drop.
- **csharp**: C# boundary extraction now works **out of the box** — the 0.25
  runtime loads the language-pack's ABI-15 C# grammar (no grammar pin / override
  needed), emitting class/interface/method/field/enum boundaries. C# is now a
  first-class language in the determinism gate (fixture + golden + guards);
  canonical language key is `csharp`.

### 🧪 Testing

- **boundary-ir**: Determinism gate — extended golden Boundary IR coverage from
  the 4 P0 languages to all 11 supported languages (python, javascript,
  typescript, go, java, cpp, c, ruby, kotlin, swift, php — and C#, added in this
  same release via the 0.25 runtime (12 total). Added a non-empty-extraction guard
  (`test_extraction_nonempty`) that fails loudly on the silent-`{}` /
  ABI-mismatch failure mode, and a fail-closed grammar/runtime pin assertion
  (`test_grammar_runtime_pins_match`) that trips on an unintended
  tree_sitter / tree-sitter-language-pack bump. Added
  `scripts/regenerate_boundary_goldens.py` as the sole sanctioned, idempotent
  golden-regenerate path, and wired the new guards into `scripts/run_ci_smoke.py`.
  Additive / guard-only — no extraction behavior changed.

## [3.1.0] - 2026-06-23

### 🐛 Bug Fixes

- **cpp**: Register CppConfig + complete C++ boundary mapping (C# blocked on grammar ABI, deferred) (#77)



### 📚 Documentation

- **changelog**: Update for v3.0.0


- **changelog**: Update for v3.0.0



### 🧪 Testing

- Drop @classmethod over @pytest.fixture across suite (#76)



## [3.0.0] - 2026-06-21

### 🐛 Bug Fixes

- Probe language pack fallback languages


- Avoid eager language pack loads while listing



### 📚 Documentation

- **changelog**: Update for v2.2.23



### 🔧 CI/CD

- Update GitHub Actions runtimes


- Update codecov action runtime


- Report nonblocking mypy as warnings


- Use bash for mypy warning wrapper


- Pin ruff to the locked 0.12.5 (fix unpinned-ruff drift reddening main) (#72)



### 🔧 Maintenance

- Update lockfile for v2.2.23


- Gitignore .dev-skills/ (phase-loop v18 handoff layout)



### 🧪 Testing

- Release traversal memory before assertion



## [2.2.23] - 2026-04-23

### ✨ Features

- Add Backstage catalog registration and repo standard layout


- Add Consiliency maintenance worker trigger workflow



### 📚 Documentation

- **changelog**: Update for v2.2.22


- Update for v2.2.22 — platform fixes, badges, version refs


- Add interface boundary spec and delivery roadmap


- Move interface boundary spec to Greenfield



### 🔧 Maintenance

- Transfer repo ownership to ViperJuice


- Update all Consiliency→ViperJuice references post-transfer


- Prepare v2.2.23 release



## [2.2.22] - 2026-04-03

### 🎨 Style

- **test**: Apply Black formatting to test_config_advanced_scenarios.py


- **tests**: Apply Black formatting to fix CI lint failures


- **tests**: Replace delattr() with del statement (ruff B043)


- **tests**: Reformat with Black 25.12.0 (matches pinned CI version)


- Run black formatter on cli.py and multi_language.py



### 🐛 Bug Fixes

- **grammar**: Re-clone when .git is a submodule file, not a real repo


- **grammar**: Detect empty submodule placeholders and reclone


- **types**: Add missing type annotations in patterns.py


- **ci**: Pin py-tree-sitter, fix ctypes Windows, re-enable coverage


- **types**: Clean up mypy errors in vfs.py


- **types**: Clean up mypy errors in top 4 error-count files


- **registry**: Use platform-native lib extension when scanning for grammars


- **tests**: Use platform-native lib extension in registry fallback tests



### 📚 Documentation

- **changelog**: Update for v2.2.20


- **changelog**: Update for v2.2.21



### 🔧 CI/CD

- Update stale action versions to v4/v5



### 🔧 Maintenance

- Remove orphaned submodule gitlinks and ignore grammars/



### 🧪 Testing

- **registry**: Mark 4 language-pack tests as xfail (API break in v1.x)


- **cli**: Xfail test_languages_command on macOS (pre-existing grammar discovery issue)


- **cli**: Extend xfail to Windows (same grammar discovery issue)



## [2.2.4] - 2026-03-08

### 🐛 Bug Fixes

- **build**: Update cibuildwheel test configuration


- **release**: Publish only distribution files to PyPI


- **release**: Publish on manual non-prerelease runs


- **release**: Remove checksums before PyPI publish


- **registry**: Soften missing combined library fallback logs



## [2.2.3] - 2026-03-08

### 🎨 Style

- **test**: Apply Black formatting


- **test**: Apply Black formatting


- **validation**: Apply Black formatting



### 🐛 Bug Fixes

- **test**: Guard zero-time config overhead baseline


- **registry**: Detect dev build grammars


- **test**: Normalize complex env plugin paths


- **test**: Floor tiny timing baselines in overhead checks


- **test**: Normalize library error path assertions


- **test**: Normalize extraction path assertions


- **test**: Stabilize export performance comparison


- **test**: Close temp file before fallback detection cleanup


- **test**: Harden fallback temp-file cleanup on Windows


- **ci**: Narrow quick pytest suite and remove random load errors


- **ci**: Reduce GitHub workflow to smoke coverage


- **ci**: Focus Test Suite on platform core coverage



## [2.2.21] - 2026-03-13

### 🐛 Bug Fixes

- **registry**: Downgrade spurious WARNING/ERROR logs to DEBUG (closes #66)



## [2.2.20] - 2026-03-13

### 🐛 Bug Fixes

- **ci**: Use orhun/git-cliff-action instead of manual curl install



## [2.2.19] - 2026-03-13

### 📚 Documentation

- **changelog**: Catch up CHANGELOG and automate with git-cliff



## [2.2.5] - 2026-03-13

### ✨ Features

- Add symbol extraction and import resolution to Python extractor


- **clustering**: Add hierarchical clustering module with Leiden algorithm


- **cli**: Add CLI module with symbol extraction and clustering commands


- **retrieval**: Enrich chunk output for code search


- **symbols**: Add metadata-driven graph and stabilize CI



### 🎨 Style

- Apply Black formatting to cross-file tests


- Fix Ruff linting error in test_cache.py (use elif)


- Apply Black formatting to test_cache.py


- **ci**: Apply Black formatting


- **ci**: Apply Black formatting fixes


- **test**: Apply Black formatting



### 🐛 Bug Fixes

- Mark phase9 metadata tests as integration tests


- **tests**: Resolve Windows file permission errors in test_auto.py


- **tests**: Resolve Windows cache cleanup permission errors


- **tests**: Add integration markers to 7 test files


- **tests**: Move parallel and recovery tests to integration suite


- **tests**: Move performance framework tests to integration suite


- **ci**: Increase pytest timeout to 60 minutes for integration-heavy suite


- **export**: Auto-extract relationships in SemanticLensExporter


- **ci**: Ignore Ruff init-module rule


- **ci**: Align Ruff config across environments


- **cli**: Keep batch summary output in quiet mode


- **test**: Handle parser config and path edge cases


- **test**: Harden cross-platform parser and temp-file assertions


- **test**: Stabilize platform-specific parser and tooling checks


- **test**: Relax environment-specific compatibility assertions


- **test**: Stabilize config path and queue IPC checks


- **test**: Allow platform-specific grammar metadata


- **test**: Handle config reload and path separators


- **debug**: Avoid unicode-only match markers


- **test**: Relax contention and Windows temp-file checks


- **test**: Tolerate platform timing and encoding defaults


- **test**: Normalize circular include paths in TOML


- **test**: Normalize env-expanded plugin paths


- **registry**: Detect dev build grammars


- **test**: Guard zero-time config overhead baseline



### 📚 Documentation

- **repo**: Capture local-first CI workflow



### 🔧 CI/CD

- Increase pytest timeout from 20 to 30 minutes


- Increase pytest timeout to 40 minutes



### 🔧 Maintenance

- Add clustering dependencies and export Python extractor symbols


- Ignore .stow-symbols.json data file


- **repo**: Archive stale artifacts and align release docs


- **repo**: Refresh grammar pointers and package metadata



## [2.2.2] - 2026-01-04

### 🐛 Bug Fixes

- Resolve all flaky integration test issues


- Enable cross-file relationship detection in ASTRelationshipTracker



### 🔧 Maintenance

- Bump version to 2.2.2



## [2.2.1] - 2026-01-04

### 🎨 Style

- Format conf.py with black


- Fix isort import ordering in affected files



### 🐛 Bug Fixes

- **tests**: Update test expectations for new error messages and behavior


- **export**: Convert signature dict to string and flatten complexity in SemanticLensExporter


- **ci**: Resolve ruff linting errors for CI/CD pipeline


- **ci**: Format with black and fix sphinx docs


- **docs**: Simplify sphinx index to only include existing docs


- **docs**: Switch to alabaster theme for sphinx 9 compatibility


- **ci**: Pin black version to 25.12.0 for consistent formatting


- **ci**: Update uv.lock to use black 25.12.0


- **ci**: Disable ruff auto-fix in CI


- **ci**: Fix Python 3.11 compatibility and trailing comma lint


- Python 3.11 compatibility for LRUCache generic syntax


- **ci**: Scope linting checks to project directories only


- **ci**: Remove isort check, use ruff for import sorting


- **ci**: Allow mypy to continue on error until type issues resolved


- **ci**: Install all required optional dependencies for tests


- **ci**: Skip broken tests and install all test dependencies


- **ci**: Add pytest timeout and skip slow/integration tests


- **ci**: Skip all integration tests in main CI workflow


- **ci**: Add parallel test execution and skip slow tests


- **ci**: Remove coverage from CI for faster test execution


- **ci**: Make CI resilient to infrastructure failures


- **ci**: Isolate git operations and increase timeouts


- Fallback to tree-sitter-language-pack for ABI compatibility + CI fixes



### 🔧 Maintenance

- Bump version to 2.2.1



## [2.2.0] - 2026-01-02

### ✨ Features

- **roadmap**: Add Phase 20 for PyPI install fix (#51)


- **P20-SL-DEPS**: Add tree-sitter-language-pack dependency


- **P20-SL-REGISTRY**: Add language pack integration for fallback language loading


- **P20-SL-ERRORS**: Improve error messages with actionable guidance



### 🐛 Bug Fixes

- **settings**: Correct tool name casing for Claude Code validation



### 🔧 Maintenance

- Add ai-dev-kit plugin assets (v3)


- **P20-SL-DEPS**: Scaffold test file for dependency validation


- **P20-SL-DEPS**: Update uv.lock for tree-sitter-language-pack


- Ignore phase execution artifacts


- Release 2.2.0



### 🧪 Testing

- **P20-SL-VERIFY**: Add fresh install verification tests



## [2.1.0] - 2026-01-02

### ✨ Features

- **export**: Add SemanticGraphBundle export format for semantic-lens



### 🔧 Maintenance

- Prepare release 2.1.0



## [2.0.4] - 2025-12-27

### ✨ Features

- REQ-TSC-008 - reconcile dependencies vs references for REFERENCES edges


- **types**: Add content-insensitive definition_id for REQ-TSC-011



### 🔧 Maintenance

- Prepare release 2.0.4



## [2.0.3] - 2025-11-28

### 🐛 Bug Fixes

- Add missing ConfigurationError class to exceptions.py



## [2.0.2] - 2025-11-28

### 🐛 Bug Fixes

- **ci**: Fix PyPI publishing workflow


- **ci**: Add contents:read permission and make artifact download optional


- **ci**: Remove submodules:recursive from checkout (stale submodule refs)


- **ci**: Install package before building and remove grammar fetch steps


- Make toml import optional to fix ImportError in v2.0.1



### 📚 Documentation

- Add migration guide for v2.0.0 → v2.0.1


- Update README.md version references to 2.0.1



## [2.0.1] - 2025-11-27

### ✨ Features

- Implement V3 consistency completion (JSON/decode/graph rationalization)


- Add CLI setup command for grammar management



### 🐛 Bug Fixes

- Implement Phase 1 critical fixes from code review


- Implement Phase 2 high-priority fixes from code review


- Implement Phase 3 medium-priority fixes from code review


- Implement Phase 4 low-priority improvements from code review


- Update dependency version constraints (Phase 5)


- Implement v4 pre-production finalization (safe decode & JSON consistency)



### 📚 Documentation

- Add comprehensive code review report



### 🔧 Maintenance

- Bump version to 2.0.1 for PyPI release



## [2.0.0] - 2025-08-20

### ✨ Features

- **cli**: Enhance grammar management CLI with complete Phase 1.8 functionality



### 📚 Documentation

- Update CHANGELOG.md and README.md for production release 1.0.9; add PyPI installation instructions and no-local-builds feature


- Comprehensive update for production release; update installation instructions, CLI commands, and remove development references



## [1.0.9] - 2025-08-15

### 🐛 Bug Fixes

- Dynamic version from package metadata; graceful graphviz handling in CLI debug commands



## [1.0.8] - 2025-08-15

### 🐛 Bug Fixes

- **cli**: Make debug commands truly optional; graceful handling of missing graphviz



## [1.0.7] - 2025-08-15

### 🔧 CI/CD

- **wheels**: Package prebuilt grammars; set packaged build dir; cibuildwheel env; version 1.0.7


- **wheels**: Ensure tree_sitter present in build env before building grammars



### 🔧 Maintenance

- **gitignore**: Ignore env files; remove committed env files



## [1.0.6] - 2025-08-14

### ✨ Features

- **core,types,api**: Stable node_id/file_id/symbol_id with parent_route; add xref builder; token claude-3.5; update exporters to prefer node_id; API endpoints for xref/export placeholders; fix streaming + lint; add spec file


- **spec**: Stable IDs + parent_route; streaming parity; pack_hint; GraphCut; Postgres spec exporter + API endpoints; nearest-tests; repo watch; tests and fixes.\n\n- Update CodeChunk model and traversal\n- Streaming walker IDs/routes\n- Token pack_hint\n- GraphCut and nearest-tests\n- Postgres spec exporter and API wiring\n- Watch mode in RepoProcessor\n- Tests: packing_hint; adjust types tests\n- Fix memory pool and fallback regex default\n- Adjust Postgres exporter for copy format files



### 🎨 Style

- Auto-lint chunker/ (black, isort, ruff --fix)



### 🐛 Bug Fixes

- Resolve all G004 logging f-string linting errors


- Additional formatting and import fixes from pre-commit hooks


- Resolve all CI/CD linting issues that prevented clean commits


- Summary of all linting fixes in this session


- Replace f-strings in logging statements with % formatting (G004)


- Resolve merge conflicts in api and internal modules


- Resolve all merge conflicts across the codebase


- Resolve linting errors and modernize codebase


- Resolve linting errors blocking CI/CD pipeline


- Apply linting and formatting fixes to resolve CI/CD issues


- Resolve test failures and add C/Rust support ⚠️ **BREAKING**


- Resolve remaining test failures


- Resolve final test failures



### 📚 Documentation

- Add PyPI publishing guide and update Dockerfile


- Clarify language support in README


- Refresh README with Quick Start, incremental/query/streaming examples, build flags, and API summary


- Add GraphML/Neo4j walkthroughs, zero-config CLI section, and MkDocs config for API docs


- Streamline index (remove phase labels), fix MkDocs nav to use relative filenames


- Add CLI reference, fix configuration link, clean nav warnings


- Add Configuration and CLI Reference to nav



### 🔧 CI/CD

- Add PyPI publishing to release workflow


- Update linting configuration for more focused checks


- Update linting configuration to use project defaults


- Update linting configuration for more focused checks


- Add cibuildwheel workflow to ship prebuilt grammars; docs: explain no-local-build option



### 🔧 Maintenance

- Apply linter formatting to test files


- Checkpoint progress across exporters, fallback, plugin mapping, registry, types [skip ci]


- Checkpoint progress; structured export edges, equality semantics, fallback fixes [skip ci]



## [1.0.0] - 2025-07-31

### ✨ Features

- Implement Language Configuration Framework (Phase 2.1) (#6)


- Add plugin architecture for extensible language support (Phase 1.2) (#5)


- Integrate all parallel development features (v2) (#8)


- Complete Phase 6.2 Documentation (#docs) (#9)


- Add Phase 8 interface definitions for parallel development


- Add token counting with tiktoken support (#18)


- Implement chunk hierarchy building and navigation (#19)


- Define Phase 10 interfaces and update documentation


- Add Phase 9 integration tests and Phase 10 setup


- Implement SmartContextProvider for Phase 10 (#27)


- Implement advanced query system for Phase 10 (#28)


- Implement config file processor for INI/TOML/YAML/JSON


- Integrate config file processor for INI/TOML/YAML/JSON


- Implement Markdown processor with structure-aware chunking


- Implement log file processor with multi-format support


- Integrate sliding window system with fallback chunker


- Integrate sliding window fallback system


- Phase 11 integration - 4 of 6 components complete


- Define Phase 12 component contracts for graph and database export


- Phase 12 interfaces and integration tests for Graph & Database Export


- Implement GraphML export for code chunk visualization


- Integrate GraphML export for code visualization


- Integrate Neo4j export with CSV and Cypher formats


- Implement Neo4j export functionality for Phase 12


- Integrate DOT export for Graphviz visualization


- Implement SQLite export with normalized schema and FTS5


- Integrate SQLite export with FTS5 and normalized schema


- Implement PostgreSQL exporter with advanced features


- Integrate PostgreSQL export with JSONB and advanced features


- Implement comprehensive Phase 2.1 config tests


- Define Phase 13 contracts for parallel development


- Implement debug tools for Phase 13


- Implement Development Environment component for Phase 13


- Implement Phase 13 Development Environment & Quality Assurance contracts


- Implement Phase 13 Build System component


- Add build system implementation modules


- Define Phase 13 contracts for parallel development


- Define Phase 14 component contracts and stub implementations


- **phase14**: Implement GrammarDiscoveryService with GitHub API integration


- Integrate Grammar Discovery Service for Phase 14


- **phase14**: Implement GrammarDownloadManager for universal language support


- Integrate Grammar Download Manager for Phase 14


- **registry**: Implement UniversalLanguageRegistry with auto-download capabilities


- Integrate Universal Language Registry for Phase 14


- **phase14**: Implement zero-configuration API for automatic chunking


- Integrate Zero-Config API for Phase 14 - Universal Language Support


- Define Phase 15 contracts and stub implementations


- Implement DeveloperToolingImpl for Phase 15


- Implement CI/CD pipeline component for Phase 15


- **debug**: Implement Debug & Visualization Tools contracts


- Implement BuildSystemImpl and PlatformSupportImpl for Phase 15


- Implement distribution component for Phase 15


- **contracts**: Add Phase 19 contracts for language expansion


- Implement GrammarManager for Phase 19


- **languages**: Implement Tier 2 language plugins for Phase 19


- Implement Tier 3 language plugins for Phase 19


- **languages**: Implement Tier 4 language plugins (Assembly/Low-level) for Phase 19


- **phase19**: Implement TemplateGeneratorContract for Template Team


- Prepare for v1.0.0 release - Major refactoring and improvements



### 🎨 Style

- Improve code formatting in workflow validator



### 🐛 Bug Fixes

- Fix Phase 10 interface imports and add integration status


- Resolve merge conflicts for Markdown processor integration


- Resolve merge conflicts for log processor integration


- Update DOT exporter for CodeChunk compatibility


- Update DOT exporter test to check for shape instead of text


- Update Phase 11 tests for compatibility with Phase 12


- Update test_config_advanced_scenarios.py to fix all failing tests


- Update debug tools for improved reliability and test coverage


- Update build system tests for cross-platform compatibility


- Remove .gitmodules file causing CI failures


- Resolve type annotation and test issues in Phase 14 contracts


- Add linting suppressions for type annotation compatibility


- Phase 3 and 4 - Fix PTH123 path operations and BLE001 blind except errors


- Fix majority of linting errors for CI/CD pipeline


- Reduce linting errors from 5200+ to 1208


- Further reduce linting errors from 1176 to 799


- Resolve all syntax errors in codebase


- Phase 2/3 linting fixes - PERF401, PTH123, SIM102, B904


- Phase 3 - Additional PERF401 fixes


- Phase 3 - More linting fixes


- Phase 3 - Fixed more PERF401 errors in multi_language.py


- Phase 3/4 - Mixed linting fixes


- Critical bug fixes - circular imports and syntax errors


- Summary of all linting fixes in this session



### 📚 Documentation

- Add Phase 10 status report


- Add Neo4j export implementation summary


- Add comprehensive implementation summary for PostgreSQL exporter


- Update ROADMAP.md for Phase 12 completion


- Update documentation for Phase 11 and 12 completion


- Update roadmap for phase 13 progress


- Update documentation to reflect Phase 15 completion


- Update CHANGELOG for v1.0.0 release



### 🔧 Maintenance

- Ignore __pycache__ directories



### 🧪 Testing

- Add comprehensive test for PostgreSQL advanced features



---

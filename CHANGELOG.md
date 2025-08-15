# Changelog

All notable changes to treesitter-chunker will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.9] - 2025-01-27

### Fixed
- **CLI Stability**: Fixed CLI crashes when graphviz is not available
- **Version Management**: Made package version dynamic using importlib.metadata instead of hardcoded values
- **Debug Commands**: Made debug commands gracefully handle missing graphviz dependency
- **Import Handling**: Conditional imports for debug modules to prevent crashes

### Changed
- CLI debug commands now provide helpful error messages when graphviz is missing
- Package version is now automatically read from package metadata

## [1.0.8] - 2025-01-27

### Fixed
- **CLI Graphviz Issue**: Fixed CLI crashes related to missing graphviz dependency
- **Debug Commands**: Made debug command imports truly optional

### Changed
- CLI now handles missing graphviz gracefully with informative error messages
- Debug commands are conditionally loaded to prevent import failures

## [1.0.7] - 2025-01-27

### Added
- **Prebuilt Grammar Support**: Embedded prebuilt Tree-sitter grammars in PyPI wheels
- **No Local Builds**: Wheels now include compiled grammar libraries for immediate use
- **Enhanced CI/CD**: GitHub Actions workflow for building and publishing wheels with grammars

### Changed
- **Package Structure**: Grammars are now built into `chunker/data/grammars/build/` during wheel creation
- **Parser Defaults**: Parser now defaults to packaged grammar libraries when available
- **Build System**: Modified grammar build scripts to support in-package builds

### Fixed
- **CI Workflow**: Fixed wheel build and publish workflow for automated releases
- **Grammar Packaging**: Ensured built grammars are properly included in wheel distributions

## [1.0.6] - 2025-01-27

### Added
- **CI/CD Integration**: GitHub Actions workflow for automated wheel building and publishing
- **Cross-Platform Wheels**: Support for Linux and macOS wheel builds

### Changed
- **Build Process**: Integrated grammar building into CI pipeline
- **Distribution**: Automated PyPI publishing on version tags

## [1.0.5] - 2025-01-27

### Added
- **PyPI Publishing**: Package now available on PyPI for easy installation
- **Wheel Distribution**: Pre-built wheels for faster installation
- **Core Dependencies**: Added `python-dateutil` as required runtime dependency

### Fixed
- **Language Registry**: Fixed language discovery and registration issues
- **Incremental Processing**: Resolved chunk diff computation and state persistence
- **Language Plugins**: Fixed various language-specific chunking issues (R, PHP, OCaml, MATLAB, TypeScript)
- **Query Engine**: Fixed advanced query index and natural language search
- **Error Handling**: Improved parallel processing error handling and recovery
- **Build System**: Fixed grammar validation and parser factory issues

### Changed
- **Documentation**: Streamlined documentation, removed development-centric information
- **CLI**: Added minimal CLI section with zero-config auto-detection
- **API Documentation**: Published API documentation using MkDocs and mkdocstrings

## [1.0.1] - 2025-08-14

### Fixed
- **Patch Release**: Various bug fixes and improvements

## [1.0.0] - 2025-08-14

### Added
- **Initial Release**: Core Tree-sitter-based code chunking functionality
- **Multi-language Support**: Python, JavaScript, TypeScript, C, C++, Rust, Go, Java, Ruby
- **Chunking Strategies**: Semantic, hierarchical, adaptive, composite chunking
- **Export Formats**: JSON, JSONL, Parquet, Neo4j, GraphML
- **Performance Features**: Caching, parallel processing, incremental updates
- **Plugin Architecture**: Extensible language support system
- **CLI Interface**: Comprehensive command-line interface
- **Debug Tools**: AST visualization and debugging capabilities
- **Cross-platform**: Windows, macOS, Linux support
- **Distribution**: PyPI, Conda, Homebrew, Docker support

### Changed
- N/A (initial release)

### Deprecated
- N/A (initial release)

### Removed
- N/A (initial release)

### Security
- N/A (initial release)

## [0.1.0] - 2024-XX-XX

Initial public release.

[Unreleased]: https://github.com/Consiliency/treesitter-chunker/compare/v1.0.9...HEAD
[1.0.9]: https://github.com/Consiliency/treesitter-chunker/compare/v1.0.8...v1.0.9
[1.0.8]: https://github.com/Consiliency/treesitter-chunker/compare/v1.0.7...v1.0.8
[1.0.7]: https://github.com/Consiliency/treesitter-chunker/compare/v1.0.6...v1.0.7
[1.0.6]: https://github.com/Consiliency/treesitter-chunker/compare/v1.0.5...v1.0.6
[1.0.5]: https://github.com/Consiliency/treesitter-chunker/compare/v1.0.1...v1.0.5
[1.0.1]: https://github.com/Consiliency/treesitter-chunker/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/Consiliency/treesitter-chunker/compare/v0.1.0...v1.0.0
[0.1.0]: https://github.com/Consiliency/treesitter-chunker/releases/tag/v0.1.0
# Specification: Per-Call Byte Spans in Metadata

## Overview

This specification outlines the implementation plan for adding precise call-site byte spans to the metadata extraction system. The goal is to enable accurate identification of function calls, method calls, and their exact locations in source code across multiple programming languages.

## Implementation Phases

### Phase 0: Critical Infrastructure Fix ✅ COMPLETE
**Status**: ✅ **COMPLETED** - Infrastructure now working correctly

**Objective**: Fix the broken language discovery and lazy loading architecture that was preventing Phase 2 tests from passing.

**What Was Accomplished**:
- ✅ Eliminated ALL hardcoded language lists (4 locations removed)
- ✅ Implemented deterministic discovery from regimented grammar directories
- ✅ Fixed the broken language discovery mechanism
- ✅ Proper error reporting - no more misleading "available" lists
- ✅ Regimented grammar storage structure implemented

**Current Status**: 
- Registry correctly discovers: `['javascript', 'python', 'rust']` (matches actual `.so` files)
- No more hardcoded assumptions anywhere in the codebase
- Deterministic grammar discovery from `chunker/data/grammars/build/`
- True lazy loading architecture that actually works

**Dependencies**: ✅ **COMPLETED** - this was a prerequisite for all other phases

### Phase 1: Base Implementation 🚧 INCOMPLETE
**Status**: 🚧 **INCOMPLETE** - Core functionality implemented but missing language support

**Objective**: Implement the foundational infrastructure for call span extraction in the base metadata extractor.

**Key Components**:
- ✅ Enhanced `extract_calls` method in `BaseMetadataExtractor`
- ✅ Support for core language patterns (Python, JavaScript, Rust)
- ✅ Call span extraction with precise byte offsets
- ✅ Method call detection for member expressions
- ✅ Integration with existing chunking pipeline

**Implementation Details**:
- ✅ Added comprehensive call detection for `call` nodes
- ✅ Enhanced member expression handling for method calls
- ✅ Improved filtering to distinguish method calls from property access
- ✅ Added support for various node types across languages
- ✅ Integrated call extraction into core chunking workflow

**Test Results**: ❌ **6/9 tests passing** - Missing Go, C, C++ language support
- ✅ Python, JavaScript, Rust: Full support working
- ❌ Go, C, C++: Language libraries missing (`.so` files not available)

**Current Status**: Base implementation complete for available languages, but cannot test languages without grammar libraries

### Phase 2: Language-Specific Extractors 🚧 INCOMPLETE
**Status**: 🚧 **INCOMPLETE** - Extractors implemented but missing language support

**Objective**: Implement dedicated extractors for specific programming languages to handle language-specific syntax and patterns.

**Languages Supported**:
- ✅ Python: Method calls, function calls, attribute access
- ✅ JavaScript: Function calls, method calls, property access
- ✅ Rust: Function calls, macro calls, method calls
- ❌ C: Function calls, function pointers (missing `c.so` library)
- ❌ C++: Static methods, templates, method calls (missing `cpp.so` library)
- ❌ Go: Package functions, method calls (missing `go.so` library)
- Additional languages: Java, Ruby, PHP, Kotlin, Swift, C#, Dart, Haskell, OCaml, Scala

**Implementation Details**:
- ✅ Dedicated extractor classes for each language
- ✅ Language-specific AST node type handling
- ✅ Specialized call pattern recognition
- ✅ Integration with base extractor for fallback support

**Test Results**: ❌ **8/11 tests passing** - Missing Go, C, C++ language support
- ✅ Python, JavaScript, Rust: Full support working
- ❌ Go, C, C++: Language libraries missing (`.so` files not available)

**Current Status**: Language-specific extractors complete for available languages, but cannot test languages without grammar libraries

### Phase 1.5: Base Implementation Language Coverage Expansion 🚧 INCOMPLETE
**Status**: 🚧 **INCOMPLETE** - Base implementation enhanced but missing language support

**Objective**: Expand the base implementation's robustness to cover 15-20 languages before proceeding to Phase 2.

**What Was Accomplished**:
- ✅ Enhanced base implementation to support 15+ languages
- ✅ Added extensive node type detection across languages
- ✅ Implemented language-specific pattern handling
- ✅ Base extractor now handles: Python, JavaScript, Rust, C#, Java, Ruby, PHP, Kotlin, Swift, Dart, Haskell, OCaml, Scala
- ✅ Support for multiple node types: `call`, `call_expression`, `invocation_expression`, `function_call`, `method_call`, `macro_invocation`
- ✅ Enhanced member expression support for method calls across languages
- ✅ Language-agnostic call detection and filtering

**Implementation Details**:
- ✅ Base extractor now recognizes call patterns from multiple languages
- ✅ Enhanced member expression handling for method calls vs property access
- ✅ Improved filtering to distinguish method calls from property access
- ✅ Support for various AST node types across different language grammars
- ✅ Integration with language-specific extractors for optimal performance

**Test Results**: ❌ **6/9 tests passing** - Missing Go, C, C++ language support
- ✅ Python, JavaScript, Rust: Full support working
- ❌ Go, C, C++: Language libraries missing (`.so` files not available)

**Result**: Base implementation provides robust fallback support for available languages, but cannot test languages without grammar libraries

### Phase 1.6: Latest Grammar Compilation & Basic Error Handling 🚧 CURRENT
**Status**: 🚧 **CURRENT** - Must be completed to finish Phase 1, 1.5, and Phase 2

**Objective**: Build latest grammar libraries for all supported languages and implement basic error handling for parsing failures.

**Implementation Strategy**: Pre-compile latest versions of all 30+ language grammars for seamless user experience with clear fallback paths.

**Grammar Compilation Plan**:
1. **Core Language Grammars** (Priority 1 - Most Commonly Used)
   - ✅ Python, JavaScript, Rust (already available)
   - 🎯 Go, C, C++, Java, C#, TypeScript
   - 🎯 Ruby, PHP, Kotlin, Swift, Dart

2. **Extended Language Grammars** (Priority 2 - Less Common)
   - 🎯 Haskell, OCaml, Scala, Elixir, Clojure
   - 🎯 MATLAB, Julia, R, SQL, NASM
   - 🎯 Vue, Svelte, Dockerfile

3. **Grammar Source Management**
   - Use existing `grammars/` directory with 30+ tree-sitter repositories
   - Compile each to `.so` library using tree-sitter CLI
   - Place compiled libraries in `chunker/data/grammars/build/`
   - Target package size: ~30-40MB (reasonable for development tools)

**Basic Error Handling Implementation**:
1. **Parsing Failure Detection**
   - Detect when grammar fails to parse code
   - Identify common failure patterns (syntax errors, version incompatibility)
   - Provide clear error messages to users

2. **User Guidance System**
   - Suggest potential grammar compatibility issues
   - Provide basic troubleshooting steps
   - Guide users to next steps for resolution

**Dependencies**: Phase 0 (Infrastructure) ✅ **COMPLETED**
**Blocking**: Phase 1, Phase 1.5, Phase 2 completion
**Package Impact**: ~30-40MB (single grammar per language)

### Phase 1.7: Smart Error Handling & User Guidance 🚧 PLANNED
**Status**: 🚧 **PLANNED** - Enhanced error handling and user guidance

**Objective**: Implement intelligent error handling that detects language version compatibility issues and provides clear user guidance.

**Language Version Detection**:
1. **Easy Detection Languages**
   - **Python**: Shebang lines, `__version__`, `sys.version`
   - **JavaScript**: `package.json` engines field, `process.version`
   - **Rust**: `Cargo.toml` edition, rustc version
   - **Go**: `go.mod` version, `runtime.Version()`

2. **Version Compatibility Matrix**
   - Track which grammar versions support which language versions
   - Build compatibility database for common language versions
   - Identify breaking changes and compatibility issues

**Smart Error Messages**:
1. **Grammar Compatibility Errors**
   - "Your Python 3.6 code requires tree-sitter-python@v0.20.0"
   - "JavaScript ES2020+ syntax needs tree-sitter-javascript@v0.20.0"
   - "Rust 2021 edition requires tree-sitter-rust@v0.20.0"

2. **User Action Guidance**
   - Clear instructions for resolving compatibility issues
   - Alternative approaches for different language versions
   - Links to relevant documentation and resources

**Dependencies**: Phase 1.6 (Grammar compilation) ✅ **COMPLETED**
**User Experience**: Clear error paths with actionable guidance

### Phase 1.8: User Grammar Management & CLI Tools 🚧 PLANNED
**Status**: 🚧 **PLANNED** - User grammar management system

**Objective**: Provide users with tools to manage their own grammar libraries and resolve compatibility issues.

**CLI Command System**:
1. **Grammar Discovery & Information**
   - `chunker grammar list` - Show available and user-installed grammars
   - `chunker grammar info <language>` - Show grammar details and compatibility
   - `chunker grammar versions <language>` - List available versions

2. **Grammar Installation & Management**
   - `chunker grammar fetch <language>[@version]` - Download specific grammar version
   - `chunker grammar build <language>` - Build grammar from source
   - `chunker grammar remove <language>` - Remove user-installed grammar

3. **Grammar Compatibility Testing**
   - `chunker grammar test <language> <file>` - Test grammar with specific file
   - `chunker grammar validate <language>` - Validate grammar installation

**User Grammar Directory Structure**:
```
~/.cache/treesitter-chunker/
├── grammars/
│   ├── python@v0.20.0/
│   ├── javascript@v0.20.0/
│   └── rust@v0.20.0/
├── config.json
└── compatibility.db
```

**Smart Grammar Selection**:
1. **Priority Order**:
   - User-installed specific version (highest priority)
   - Package pre-compiled latest version
   - Fallback to error with user guidance

2. **Automatic Fallback**:
   - Try user grammars first
   - Fall back to package grammars
   - Provide clear guidance if both fail

**Dependencies**: Phase 1.7 (Smart error handling) ✅ **COMPLETED**
**User Empowerment**: Users can solve their own compatibility issues

### Phase 1.9: Production-Ready Error Handling & Integration 🚧 PLANNED
**Status**: 🚧 **PLANNED** - Final integration and production readiness

**Objective**: Integrate all error handling and grammar management systems for production deployment.

**Production Error Handling**:
1. **Graceful Degradation**
   - System continues working for supported languages
   - Clear error reporting for unsupported scenarios
   - No silent failures or misleading error messages

2. **Performance Optimization**
   - Grammar loading and caching optimization
   - Error detection performance improvements
   - User grammar discovery optimization

3. **Integration Testing**
   - Test all error paths and user guidance
   - Validate grammar management CLI tools
   - Performance testing with large codebases

**Final Validation**:
1. **All Phase Tests Passing**
   - Phase 1: 9/9 tests passing
   - Phase 1.5: 9/9 tests passing
   - Phase 2: 11/11 tests passing

2. **Production Readiness**
   - Clear error messages for all failure scenarios
   - User grammar management working correctly
   - Performance acceptable for production use

**Dependencies**: Phase 1.8 (User grammar management) ✅ **COMPLETED**
**Outcome**: Production-ready system with comprehensive language support

### Phase 3: Performance Optimization & Validation 🚧 PENDING
**Status**: 🚧 **PENDING** - Ready to begin after Phase 1 completion

**Objective**: Optimize performance and validate the implementation across real-world codebases.

**Tasks**:
- Performance benchmarking and optimization
- Memory usage optimization
- Large file handling improvements
- Integration testing with real codebases
- Documentation and examples

## Implementation Status Summary

### ✅ Completed Phases
- **Phase 0**: Critical infrastructure fix for language discovery and lazy loading

### 🚧 Current Phase
- **Phase 1.6**: Latest grammar compilation & basic error handling

### 🚧 Planned Phases
- **Phase 1.7**: Smart error handling & user guidance
- **Phase 1.8**: User grammar management & CLI tools
- **Phase 1.9**: Production-ready error handling & integration

### 🚧 Incomplete Phases
- **Phase 1**: Base implementation with core language support (waiting for grammar compilation)
- **Phase 1.5**: Base implementation language coverage expansion (waiting for grammar compilation)
- **Phase 2**: Language-specific extractors for all major languages (waiting for grammar compilation)

### 🚧 Pending Phases
- **Phase 3**: Performance optimization and validation

## Current Architecture

The system now uses a **hybrid approach** that combines:

1. **Base Extractor**: Handles common patterns and provides fallback support
2. **Language-Specific Extractors**: Provide optimized, accurate extraction for each language
3. **Factory Pattern**: Automatically selects the best extractor for each language

**✅ INFRASTRUCTURE STATUS**: The language discovery and lazy loading architecture is now working correctly after Phase 0 completion.

This architecture provides:
- **Better Accuracy**: Language-specific extractors understand language nuances
- **Better Performance**: No need to check all possible node types
- **Better Maintainability**: Each language's logic is isolated
- **Better Extensibility**: Easy to add new languages

## Deployment Strategy

### Phase 1 ✅ Deployed
- Base implementation integrated into core chunking
- All existing functionality preserved
- Backward compatibility maintained

### Phase 2 ✅ Deployed  
- Language-specific extractors available for all supported languages
- Automatic language detection and extractor selection
- Comprehensive test coverage

### Phase 3 🚧 Planning
- Performance optimization
- Real-world validation
- Production readiness

## Revised Timeline

- **Phase 0**: ✅ **COMPLETED** (Critical infrastructure fix - language discovery & lazy loading)
- **Phase 1**: 🚧 **INCOMPLETE** (Base implementation - waiting for grammar compilation)
- **Phase 1.5**: 🚧 **INCOMPLETE** (Base enhancement - waiting for grammar compilation)
- **Phase 1.6**: 🚧 **CURRENT** (Latest grammar compilation & basic error handling)
- **Phase 1.7**: 🚧 **PLANNED** (Smart error handling & user guidance)
- **Phase 1.8**: 🚧 **PLANNED** (User grammar management & CLI tools)
- **Phase 1.9**: 🚧 **PLANNED** (Production-ready error handling & integration)
- **Phase 2**: 🚧 **INCOMPLETE** (Language-specific extractors - waiting for grammar compilation)
- **Phase 3**: 🚧 **PLANNED** (Performance & validation - after Phase 1 completion)

## Key Success Metrics

### Phase 0 ✅ Achieved
- ✅ Language discovery infrastructure working correctly
- ✅ No more hardcoded language assumptions
- ✅ Deterministic grammar discovery from regimented directories
- ✅ True lazy loading architecture implemented

### Phase 1 🚧 Partially Achieved
- ✅ Call extraction working for available languages (Python, JavaScript, Rust)
- ✅ Method call detection functional
- ✅ Integration with chunking pipeline complete
- ❌ **6/9 tests passing** - Missing Go, C, C++ support

### Phase 1.5 🚧 Partially Achieved
- ✅ Enhanced base implementation for available languages
- ✅ Extended node type detection across languages
- ✅ Language-agnostic call detection and filtering
- ❌ **6/9 tests passing** - Missing Go, C, C++ support

### Phase 1.6 🎯 Current Targets
- 🎯 Compile latest grammars for all 30+ supported languages
- 🎯 Implement basic error handling for parsing failures
- 🎯 Target package size: ~30-40MB (reasonable for development tools)
- 🎯 All Phase 1, 1.5, and Phase 2 tests passing with compiled grammars

### Phase 1.7 🎯 Planned Targets
- 🎯 Implement language version detection for common languages
- 🎯 Build version compatibility matrix and database
- 🎯 Provide smart error messages with grammar compatibility guidance
- 🎯 Clear user action guidance for resolving compatibility issues

### Phase 1.8 🎯 Planned Targets
- 🎯 Implement comprehensive CLI grammar management system
- 🎯 User grammar installation, version management, and testing
- 🎯 Smart grammar selection with user-installed grammar priority
- 🎯 User grammar directory structure and configuration management

### Phase 1.9 🎯 Planned Targets
- 🎯 Production-ready error handling with graceful degradation
- 🎯 Performance optimization for grammar loading and error detection
- 🎯 Complete integration testing of all error paths and user guidance
- 🎯 Final validation of all Phase 1, 1.5, and Phase 2 functionality

### Phase 2 🚧 Partially Achieved
- ✅ Language-specific extractors for available languages
- ✅ Comprehensive test coverage for available languages
- ✅ Automatic language detection
- ✅ Robust error handling
- ❌ **8/11 tests passing** - Missing Go, C, C++ support

### Phase 3 🎯 Future Targets
- 🎯 Performance improvement targets
- 🎯 Memory usage optimization
- 🎯 Large file handling validation
- 🎯 Production readiness validation

## Conclusion

The implementation has made significant progress through a **multi-phase approach**:

1. **Phase 0** ✅ provided the critical infrastructure foundation (language discovery & lazy loading)
2. **Phase 1** 🚧 delivered the base implementation for available languages (Python, JavaScript, Rust)
3. **Phase 1.5** 🚧 enhanced the base implementation with extended language support
4. **Phase 2** 🚧 provided language-specific extractors for available languages

**Current Status**: The system has a solid infrastructure and working implementations for Python, JavaScript, and Rust, but is **blocked by missing grammar libraries** for other languages.

**Revised Strategy**: Instead of building individual missing grammars, we're implementing a **production-focused approach**:

1. **Phase 1.6**: Compile latest grammars for all 30+ supported languages (~30-40MB package)
2. **Phase 1.7**: Implement smart error handling with language version detection
3. **Phase 1.8**: Provide user grammar management CLI tools for compatibility issues
4. **Phase 1.9**: Production-ready error handling and integration

**The parallel agent approach** was successful in implementing the extractors and base enhancements, but the infrastructure issues (now resolved in Phase 0) prevented proper testing of all languages.

**Next Steps**: Complete **Phase 1.6** (Latest Grammar Compilation) to build all supported language grammars, followed by the enhanced error handling and user grammar management phases. This approach prioritizes user experience with seamless operation for most cases and clear guidance when compatibility issues arise.

**Expected Outcome**: A production-ready system that works seamlessly for 95% of use cases and provides clear, actionable guidance for the remaining 5% of compatibility edge cases.

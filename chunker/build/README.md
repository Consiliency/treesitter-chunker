# Build System Component

This component provides cross-platform build support for tree-sitter grammars and package distribution.

## Overview

The build system handles:
- Cross-platform grammar compilation (Windows, macOS, Linux)
- Platform-specific wheel building
- Conda package creation
- Build artifact verification
- Platform detection and dependency management

## Architecture

### Core Classes

- **BuildSystem**: Main build orchestrator implementing `BuildSystemContract`
  - Compiles grammars for target platforms
  - Builds distribution packages (wheels, conda)
  - Verifies build artifacts
  
- **PlatformSupport**: Platform detection and setup implementing `PlatformSupportContract`
  - Detects OS, architecture, Python version
  - Manages compiler detection
  - Installs platform-specific dependencies

## Usage

```python
from chunker.build import BuildSystem, PlatformSupport

# Initialize build system
build_sys = BuildSystem()

# Detect current platform
platform_info = build_sys.platform_support.detect_platform()
print(f"Platform: {platform_info['os']} {platform_info['arch']}")

# Compile grammars
success, build_info = build_sys.compile_grammars(
    languages=["python", "javascript", "rust"],
    platform=platform_info["os"],
    output_dir=Path("./build")
)

# Build wheel
success, wheel_path = build_sys.build_wheel(
    platform=platform_info["os"],
    python_version=platform_info["python_tag"],
    output_dir=Path("./dist")
)

# Verify build
valid, report = build_sys.verify_build(wheel_path, platform_info["os"])
```

## Platform Support

### Supported Platforms
- **Linux**: x86_64, arm64, i386
- **macOS**: x86_64, arm64 (M1/M2)
- **Windows**: x86_64, i386

### Compiler Detection
- **Linux**: gcc, g++, clang
- **macOS**: clang (via Xcode Command Line Tools)
- **Windows**: cl.exe (Visual Studio Build Tools)

### Platform Tags
The system generates PEP-compliant platform tags:
- Linux: `linux_x86_64`, `linux_aarch64`
- macOS: `macosx_10_9_x86_64`, `macosx_11_0_arm64`
- Windows: `win_amd64`, `win32`

## Build Process

### Grammar Compilation

1. **Source Collection**: Gathers C source files from grammar repositories
2. **Compiler Selection**: Uses platform-appropriate compiler
3. **Compilation**: Creates shared libraries (.so, .dylib, .dll)
4. **Verification**: Ensures libraries are properly built

### Wheel Building

1. **Package Assembly**: Copies Python code and metadata
2. **Grammar Integration**: Includes compiled grammars
3. **Metadata Generation**: Creates wheel metadata
4. **Tag Application**: Applies correct platform/Python tags

### Verification

The verification process checks:
- Package structure completeness
- Metadata presence and correctness
- Grammar library inclusion
- Platform tag matching

## Error Handling

The build system handles various failure scenarios:
- Missing compilers → Clear error messages with installation instructions
- Failed compilation → Detailed error logs
- Missing dependencies → Graceful degradation with actionable messages

## Testing

Run tests with:
```bash
# Unit tests
pytest tests/test_build_system_unit.py -v

# Integration tests  
pytest tests/test_phase13_build_integration_real.py -v
```

## Dependencies

- **Build tools**: Platform-specific compilers
- **Python packages**: setuptools, wheel
- **Optional**: conda-build for conda packages

## Future Enhancements

- Docker-based builds for reproducibility
- Cross-compilation support
- Automated dependency installation
- Build caching for faster rebuilds
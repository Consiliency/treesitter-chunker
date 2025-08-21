"""Version detection modules for Phase 1.7 - Smart Error Handling & User Guidance.

This package provides language-specific version detection capabilities for:
- Python
- JavaScript/TypeScript/Node.js
- Rust
- Go
- C/C++
- Java

Each detector can identify language versions from multiple sources including:
- Configuration files (package.json, pom.xml, Cargo.toml, go.mod, etc.)
- Build files and scripts
- Source code comments and directives
- Language features and syntax
- Compiler/runtime version checks
"""

from .cpp_detector import CppVersionDetector, CppVersionInfo
from .go_detector import GoVersionDetector, GoVersionInfo
from .java_detector import JavaVersionDetector, JavaVersionInfo
from .javascript_detector import JavaScriptVersionDetector, JavaScriptVersionInfo
from .python_detector import PythonVersionDetector, PythonVersionInfo
from .rust_detector import RustVersionDetector, RustVersionInfo

__all__ = [
    # C/C++
    "CppVersionDetector",
    "CppVersionInfo",
    # Go
    "GoVersionDetector",
    "GoVersionInfo",
    # JavaScript
    "JavaScriptVersionDetector",
    "JavaScriptVersionInfo",
    # Java
    "JavaVersionDetector",
    "JavaVersionInfo",
    # Python
    "PythonVersionDetector",
    "PythonVersionInfo",
    # Rust
    "RustVersionDetector",
    "RustVersionInfo",
]

# Version of this module
__version__ = "1.0.0"

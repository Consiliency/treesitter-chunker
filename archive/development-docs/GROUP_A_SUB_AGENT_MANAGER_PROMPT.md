# GROUP A SUB-AGENT MANAGER PROMPT
# Phase 1.7: Smart Error Handling & User Guidance
# Language Version Detection Modules

## AGENT IDENTIFICATION & ROLES

**WHO I AM**: I am the primary AI agent working on Phase 1.7 implementation planning and coordination. I will NOT touch any of the files assigned to sub-agents in this prompt.

**WHO YOU ARE**: You are the sub-agent manager responsible for coordinating parallel execution of Group A tasks. You will assign these tasks to sub-agents and coordinate their work.

**WHO THE SUB-AGENTS ARE**: Individual AI agents that will implement specific language version detection modules. Each sub-agent works on exactly ONE file and ONE task.

## EXECUTION STRATEGY

**PARALLEL EXECUTION**: All 6 Group A tasks can run simultaneously by different sub-agents.
**FILE ISOLATION**: Each sub-agent touches ONLY their assigned file - no cross-file dependencies.
**COORDINATION**: You will manage the parallel execution and collect results from all sub-agents.

## GROUP A TASKS OVERVIEW

**OBJECTIVE**: Implement language version detection modules for 6 major programming languages.
**DEPENDENCIES**: None - all tasks are completely independent.
**OUTPUT**: 6 fully functional version detection modules with comprehensive testing.

---

## TASK A1: PYTHON VERSION DETECTION MODULE

**ASSIGNED FILE**: `chunker/languages/version_detection/python_detector.py`
**SUB-AGENT**: Python Version Detection Specialist
**IMPLEMENTATION DEADLINE**: Complete within assigned timeframe

### FILE STRUCTURE TO CREATE:
```python
# chunker/languages/version_detection/python_detector.py

from typing import Optional, Dict, List, Tuple
import re
from pathlib import Path

class PythonVersionDetector:
    """Detects Python version from multiple sources in code and configuration."""
    
    def __init__(self):
        self.version_patterns = {
            'shebang': r'^#!.*python(\d+\.\d+)',
            'version_string': r'__version__\s*=\s*[\'"]([^\'"]+)[\'"]',
            'sys_version': r'sys\.version\s*[:=]\s*[\'"]([^\'"]+)[\'"]',
            'python_version': r'python_version\s*[:=]\s*[\'"]([^\'"]+)[\'"]'
        }
    
    def detect_from_shebang(self, content: str) -> Optional[str]:
        """Extract Python version from shebang line."""
        # Implementation: Parse #!/usr/bin/env python3.9 or #!/usr/bin/python3.9
        # Return: "3.9" or None if not found
        
    def detect_from_version_string(self, content: str) -> Optional[str]:
        """Extract Python version from __version__ variable."""
        # Implementation: Find __version__ = "1.2.3" patterns
        # Return: "1.2.3" or None if not found
        
    def detect_from_sys_version(self, content: str) -> Optional[str]:
        """Extract Python version from sys.version usage."""
        # Implementation: Find sys.version references and parse output
        # Return: "3.9.0" or None if not found
        
    def detect_from_requirements(self, content: str) -> Optional[str]:
        """Extract Python version from requirements.txt or setup.py."""
        # Implementation: Parse python_requires, python_version fields
        # Return: ">=3.7" or None if not found
        
    def normalize_version(self, version: str) -> str:
        """Normalize version string to standard format."""
        # Implementation: Convert various formats to semantic versioning
        # Handle: "3.9", "3.9.0", "3.9.0a1", "3.9.0b1"
        # Return: Normalized version string
        
    def detect_version(self, content: str, file_path: Optional[Path] = None) -> Dict[str, Optional[str]]:
        """Main method to detect Python version from all sources."""
        # Implementation: Try all detection methods
        # Return: Dict with results from each method
        
    def get_primary_version(self, detection_results: Dict[str, Optional[str]]) -> Optional[str]:
        """Determine the primary version from multiple detection results."""
        # Implementation: Prioritize shebang > __version__ > sys.version > requirements
        # Return: Most reliable version string or None

class PythonVersionInfo:
    """Container for Python version information."""
    
    def __init__(self, version: str, source: str, confidence: float):
        self.version = version
        self.source = source
        self.confidence = confidence
        self.detected_at = datetime.now()
    
    def to_dict(self) -> Dict[str, any]:
        """Convert to dictionary representation."""
        
    def __str__(self) -> str:
        """String representation of version info."""
```

### IMPLEMENTATION REQUIREMENTS:
1. **Complete all methods** with full implementation
2. **Add comprehensive type hints** for all functions
3. **Include detailed docstrings** explaining each method's purpose
4. **Handle edge cases** like malformed version strings, missing files
5. **Implement error handling** with graceful fallbacks
6. **Add logging** for debugging and monitoring
7. **Create unit tests** covering all detection methods

### TESTING REQUIREMENTS:
- Test with various Python version formats (3.9, 3.9.0, 3.9.0a1)
- Test with different shebang patterns
- Test with malformed or missing version information
- Test error handling and edge cases
- Achieve 90%+ code coverage

---

## TASK A2: JAVASCRIPT VERSION DETECTION MODULE

**ASSIGNED FILE**: `chunker/languages/version_detection/javascript_detector.py`
**SUB-AGENT**: JavaScript Version Detection Specialist
**IMPLEMENTATION DEADLINE**: Complete within assigned timeframe

### FILE STRUCTURE TO CREATE:
```python
# chunker/languages/version_detection/javascript_detector.py

from typing import Optional, Dict, List, Tuple
import json
import re
from pathlib import Path

class JavaScriptVersionDetector:
    """Detects JavaScript/Node.js version from multiple sources."""
    
    def __init__(self):
        self.version_patterns = {
            'engines': r'"engines"\s*:\s*\{[^}]*"node"\s*:\s*"([^"]+)"',
            'process_version': r'process\.version\s*[:=]\s*[\'"]([^\'"]+)[\'"]',
            'es_version': r'//\s*ES(\d{4})|ES(\d{4})\s+features',
            'typescript': r'//\s*TypeScript\s+(\d+\.\d+\.\d+)'
        }
    
    def detect_from_package_json(self, content: str) -> Optional[str]:
        """Extract Node.js version from package.json engines field."""
        # Implementation: Parse "engines": {"node": ">=16.0.0"}
        # Return: ">=16.0.0" or None if not found
        
    def detect_from_process_version(self, content: str) -> Optional[str]:
        """Extract Node.js version from process.version usage."""
        # Implementation: Find process.version references
        # Return: "v16.0.0" or None if not found
        
    def detect_es_version(self, content: str) -> Optional[str]:
        """Detect ECMAScript version from code comments and features."""
        # Implementation: Parse ES2015, ES2020, ES2022 comments
        # Return: "2015", "2020", "2022" or None if not found
        
    def detect_typescript_version(self, content: str) -> Optional[str]:
        """Detect TypeScript version from comments and configuration."""
        # Implementation: Parse TypeScript version comments
        # Return: "4.9.0" or None if not found
        
    def parse_engine_requirements(self, engines_str: str) -> Dict[str, str]:
        """Parse engine requirements string into version constraints."""
        # Implementation: Parse ">=16.0.0 <18.0.0" patterns
        # Return: Dict with min, max, exact versions
        
    def detect_version(self, content: str, file_path: Optional[Path] = None) -> Dict[str, Optional[str]]:
        """Main method to detect JavaScript version from all sources."""
        # Implementation: Try all detection methods
        # Return: Dict with results from each method
        
    def get_primary_version(self, detection_results: Dict[str, Optional[str]]) -> Optional[str]:
        """Determine the primary version from multiple detection results."""
        # Implementation: Prioritize engines > process.version > ES version
        # Return: Most reliable version string or None

class JavaScriptVersionInfo:
    """Container for JavaScript version information."""
    
    def __init__(self, node_version: Optional[str], es_version: Optional[str], 
                 typescript_version: Optional[str], source: str):
        self.node_version = node_version
        self.es_version = es_version
        self.typescript_version = typescript_version
        self.source = source
        self.detected_at = datetime.now()
    
    def to_dict(self) -> Dict[str, any]:
        """Convert to dictionary representation."""
        
    def __str__(self) -> str:
        """String representation of version info."""
```

### IMPLEMENTATION REQUIREMENTS:
1. **Complete all methods** with full implementation
2. **Handle package.json parsing** with proper JSON validation
3. **Support multiple ES versions** (ES2015, ES2020, ES2022, etc.)
4. **Parse complex engine requirements** (>=16.0.0 <18.0.0)
5. **Add comprehensive error handling** for malformed JSON/config
6. **Include logging** for debugging and monitoring
7. **Create unit tests** covering all detection methods

### TESTING REQUIREMENTS:
- Test with various Node.js version formats
- Test with different ES version specifications
- Test with malformed package.json files
- Test engine requirement parsing
- Achieve 90%+ code coverage

---

## TASK A3: RUST VERSION DETECTION MODULE

**ASSIGNED FILE**: `chunker/languages/version_detection/rust_detector.py`
**SUB-AGENT**: Rust Version Detection Specialist
**IMPLEMENTATION DEADLINE**: Complete within assigned timeframe

### FILE STRUCTURE TO CREATE:
```python
# chunker/languages/version_detection/rust_detector.py

from typing import Optional, Dict, List, Tuple
import re
from pathlib import Path

class RustVersionDetector:
    """Detects Rust version from Cargo.toml and code."""
    
    def __init__(self):
        self.version_patterns = {
            'edition': r'edition\s*=\s*"(\d{4})"',
            'rustc_version': r'//\s*rustc\s+(\d+\.\d+\.\d+)',
            'feature_flags': r'#\[feature\(([^)]+)\)\]',
            'cargo_version': r'cargo\s+(\d+\.\d+\.\d+)'
        }
    
    def detect_from_cargo_toml(self, content: str) -> Optional[str]:
        """Extract Rust edition from Cargo.toml."""
        # Implementation: Parse edition = "2021" field
        # Return: "2021" or None if not found
        
    def detect_from_rustc_comments(self, content: str) -> Optional[str]:
        """Extract rustc version from code comments."""
        # Implementation: Parse // rustc 1.70.0 comments
        # Return: "1.70.0" or None if not found
        
    def detect_edition_features(self, content: str) -> List[str]:
        """Detect Rust edition-specific features used in code."""
        # Implementation: Parse feature flags and edition requirements
        # Return: List of required edition features
        
    def parse_edition_requirements(self, edition: str) -> Dict[str, any]:
        """Parse edition requirements and capabilities."""
        # Implementation: Map editions to supported features
        # Return: Dict with edition capabilities
        
    def detect_version(self, content: str, file_path: Optional[Path] = None) -> Dict[str, Optional[str]]:
        """Main method to detect Rust version from all sources."""
        # Implementation: Try all detection methods
        # Return: Dict with results from each method
        
    def get_primary_version(self, detection_results: Dict[str, Optional[str]]) -> Optional[str]:
        """Determine the primary version from multiple detection results."""
        # Implementation: Prioritize edition > rustc version > feature analysis
        # Return: Most reliable version string or None

class RustVersionInfo:
    """Container for Rust version information."""
    
    def __init__(self, edition: Optional[str], rustc_version: Optional[str], 
                 features: List[str], source: str):
        self.edition = edition
        self.rustc_version = rustc_version
        self.features = features
        self.source = source
        self.detected_at = datetime.now()
    
    def to_dict(self) -> Dict[str, any]:
        """Convert to dictionary representation."""
        
    def __str__(self) -> str:
        """String representation of version info."""
```

### IMPLEMENTATION REQUIREMENTS:
1. **Complete all methods** with full implementation
2. **Handle Rust editions** (2015, 2018, 2021) with feature mapping
3. **Parse feature flags** and edition requirements
4. **Support rustc version detection** from comments
5. **Add comprehensive error handling** for malformed TOML
6. **Include logging** for debugging and monitoring
7. **Create unit tests** covering all detection methods

### TESTING REQUIREMENTS:
- Test with various Rust editions (2015, 2018, 2021)
- Test with different rustc version formats
- Test feature flag parsing and edition mapping
- Test with malformed Cargo.toml files
- Achieve 90%+ code coverage

---

## TASK A4: GO VERSION DETECTION MODULE

**ASSIGNED FILE**: `chunker/languages/version_detection/go_detector.py`
**SUB-AGENT**: Go Version Detection Specialist
**IMPLEMENTATION DEADLINE**: Complete within assigned timeframe

### FILE STRUCTURE TO CREATE:
```python
# chunker/languages/version_detection/go_detector.py

from typing import Optional, Dict, List, Tuple
import re
from pathlib import Path

class GoVersionDetector:
    """Detects Go version from go.mod and code."""
    
    def __init__(self):
        self.version_patterns = {
            'go_version': r'go\s+(\d+\.\d+)',
            'runtime_version': r'runtime\.Version\(\)',
            'build_constraints': r'//\s*\+build\s+go(\d+\.\d+)',
            'go_build_tags': r'//go:build\s+go(\d+\.\d+)'
        }
    
    def detect_from_go_mod(self, content: str) -> Optional[str]:
        """Extract Go version from go.mod file."""
        # Implementation: Parse go 1.19 directive
        # Return: "1.19" or None if not found
        
    def detect_from_build_constraints(self, content: str) -> Optional[str]:
        """Extract Go version from build constraints."""
        # Implementation: Parse // +build go1.19 or //go:build go1.19
        # Return: "1.19" or None if not found
        
    def detect_from_runtime_version(self, content: str) -> Optional[str]:
        """Detect Go version from runtime.Version() usage."""
        # Implementation: Find runtime.Version() calls
        # Return: "go1.19" or None if not found
        
    def parse_version_constraints(self, version_str: str) -> Dict[str, str]:
        """Parse Go version constraints and requirements."""
        # Implementation: Parse version strings and constraints
        # Return: Dict with version requirements
        
    def detect_version(self, content: str, file_path: Optional[Path] = None) -> Dict[str, Optional[str]]:
        """Main method to detect Go version from all sources."""
        # Implementation: Try all detection methods
        # Return: Dict with results from each method
        
    def get_primary_version(self, detection_results: Dict[str, Optional[str]]) -> Optional[str]:
        """Determine the primary version from multiple detection results."""
        # Implementation: Prioritize go.mod > build constraints > runtime version
        # Return: Most reliable version string or None

class GoVersionInfo:
    """Container for Go version information."""
    
    def __init__(self, go_version: Optional[str], build_constraints: List[str], 
                 source: str):
        self.go_version = go_version
        self.build_constraints = build_constraints
        self.source = source
        self.detected_at = datetime.now()
    
    def to_dict(self) -> Dict[str, any]:
        """Convert to dictionary representation."""
        
    def __str__(self) -> str:
        """String representation of version info."""
```

### IMPLEMENTATION REQUIREMENTS:
1. **Complete all methods** with full implementation
2. **Handle go.mod parsing** with proper format validation
3. **Support build constraints** (// +build and //go:build)
4. **Parse version constraints** and requirements
5. **Add comprehensive error handling** for malformed go.mod
6. **Include logging** for debugging and monitoring
7. **Create unit tests** covering all detection methods

### TESTING REQUIREMENTS:
- Test with various Go version formats (1.16, 1.17, 1.18, 1.19, 1.20)
- Test with different build constraint formats
- Test version constraint parsing
- Test with malformed go.mod files
- Achieve 90%+ code coverage

---

## TASK A5: C/C++ VERSION DETECTION MODULE

**ASSIGNED FILE**: `chunker/languages/version_detection/cpp_detector.py`
**SUB-AGENT**: C/C++ Version Detection Specialist
**IMPLEMENTATION DEADLINE**: Complete within assigned timeframe

### FILE STRUCTURE TO CREATE:
```python
# chunker/languages/version_detection/cpp_detector.py

from typing import Optional, Dict, List, Tuple
import re
from pathlib import Path

class CppVersionDetector:
    """Detects C/C++ version from compiler directives and code."""
    
    def __init__(self):
        self.version_patterns = {
            'pragma_version': r'#pragma\s+version\s+(\d+\.\d+)',
            'compiler_version': r'//\s*(?:gcc|clang|msvc)\s+(\d+\.\d+\.\d+)',
            'cxx_standard': r'//\s*C\+\+(\d{2})|std::c\+\+(\d{2})',
            'feature_test': r'__cpp_(\w+)\s*(\d+)(\d{3})'
        }
    
    def detect_from_pragma(self, content: str) -> Optional[str]:
        """Extract version from #pragma directives."""
        # Implementation: Parse #pragma version 17.0
        # Return: "17.0" or None if not found
        
    def detect_compiler_version(self, content: str) -> Optional[str]:
        """Detect compiler version from comments."""
        # Implementation: Parse // gcc 11.2.0 or // clang 13.0.0
        # Return: "11.2.0" or None if not found
        
    def detect_cxx_standard(self, content: str) -> Optional[str]:
        """Detect C++ standard version from code."""
        # Implementation: Parse C++11, C++14, C++17, C++20 references
        # Return: "11", "14", "17", "20" or None if not found
        
    def detect_feature_test_macros(self, content: str) -> List[str]:
        """Detect C++ feature test macros."""
        # Implementation: Parse __cpp_concepts, __cpp_modules, etc.
        # Return: List of detected feature test macros
        
    def map_features_to_standard(self, features: List[str]) -> Optional[str]:
        """Map feature test macros to C++ standard version."""
        # Implementation: Map features to minimum C++ standard
        # Return: C++ standard version or None
        
    def detect_version(self, content: str, file_path: Optional[Path] = None) -> Dict[str, Optional[str]]:
        """Main method to detect C/C++ version from all sources."""
        # Implementation: Try all detection methods
        # Return: Dict with results from each method
        
    def get_primary_version(self, detection_results: Dict[str, Optional[str]]) -> Optional[str]:
        """Determine the primary version from multiple detection results."""
        # Implementation: Prioritize pragma > compiler > C++ standard > features
        # Return: Most reliable version string or None

class CppVersionInfo:
    """Container for C/C++ version information."""
    
    def __init__(self, compiler_version: Optional[str], cxx_standard: Optional[str], 
                 features: List[str], source: str):
        self.compiler_version = compiler_version
        self.cxx_standard = cxx_standard
        self.features = features
        self.source = source
        self.detected_at = datetime.now()
    
    def to_dict(self) -> Dict[str, any]:
        """Convert to dictionary representation."""
        
    def __str__(self) -> str:
        """String representation of version info."""
```

### IMPLEMENTATION REQUIREMENTS:
1. **Complete all methods** with full implementation
2. **Handle multiple compilers** (GCC, Clang, MSVC)
3. **Support C++ standards** (C++11, C++14, C++17, C++20)
4. **Parse feature test macros** and map to standards
5. **Add comprehensive error handling** for malformed directives
6. **Include logging** for debugging and monitoring
7. **Create unit tests** covering all detection methods

### TESTING REQUIREMENTS:
- Test with various compiler version formats
- Test with different C++ standard specifications
- Test feature test macro parsing and mapping
- Test with malformed pragma directives
- Achieve 90%+ code coverage

---

## TASK A6: JAVA VERSION DETECTION MODULE

**ASSIGNED FILE**: `chunker/languages/version_detection/java_detector.py`
**SUB-AGENT**: Java Version Detection Specialist
**IMPLEMENTATION DEADLINE**: Complete within assigned timeframe

### FILE STRUCTURE TO CREATE:
```python
# chunker/languages/version_detection/java_detector.py

from typing import Optional, Dict, List, Tuple
import re
from pathlib import Path

class JavaVersionDetector:
    """Detects Java version from pom.xml and code."""
    
    def __init__(self):
        self.version_patterns = {
            'java_version': r'<java\.version>(\d+)</java\.version>',
            'maven_compiler': r'<maven\.compiler\.source>(\d+)</maven\.compiler\.source>',
            'system_property': r'System\.getProperty\("java\.version"\)',
            'module_info': r'module\s+\w+\s*\{\s*requires\s+java\.base\s*;\s*\}'
        }
    
    def detect_from_pom_xml(self, content: str) -> Optional[str]:
        """Extract Java version from pom.xml."""
        # Implementation: Parse <java.version>11</java.version>
        # Return: "11" or None if not found
        
    def detect_from_maven_compiler(self, content: str) -> Optional[str]:
        """Extract Java version from Maven compiler plugin."""
        # Implementation: Parse <maven.compiler.source>11</maven.compiler.source>
        # Return: "11" or None if not found
        
    def detect_from_system_property(self, content: str) -> Optional[str]:
        """Detect Java version from System.getProperty usage."""
        # Implementation: Find System.getProperty("java.version") calls
        # Return: "11" or None if not found
        
    def detect_from_module_info(self, content: str) -> Optional[str]:
        """Detect Java version from module-info.java."""
        # Implementation: Parse module requirements and Java version
        # Return: "9" or None if not found
        
    def parse_version_requirements(self, version_str: str) -> Dict[str, str]:
        """Parse Java version requirements and constraints."""
        # Implementation: Parse version strings and constraints
        # Return: Dict with version requirements
        
    def detect_version(self, content: str, file_path: Optional[Path] = None) -> Dict[str, Optional[str]]:
        """Main method to detect Java version from all sources."""
        # Implementation: Try all detection methods
        # Return: Dict with results from each method
        
    def get_primary_version(self, detection_results: Dict[str, Optional[str]]) -> Optional[str]:
        """Determine the primary version from multiple detection results."""
        # Implementation: Prioritize pom.xml > maven compiler > system property > module info
        # Return: Most reliable version string or None

class JavaVersionInfo:
    """Container for Java version information."""
    
    def __init__(self, java_version: Optional[str], maven_version: Optional[str], 
                 module_system: bool, source: str):
        self.java_version = java_version
        self.maven_version = maven_version
        self.module_system = module_system
        self.source = source
        self.detected_at = datetime.now()
    
    def to_dict(self) -> Dict[str, any]:
        """Convert to dictionary representation."""
        
    def __str__(self) -> str:
        """String representation of version info."""
```

### IMPLEMENTATION REQUIREMENTS:
1. **Complete all methods** with full implementation
2. **Handle Maven POM parsing** with proper XML validation
3. **Support Java versions** (8, 9, 11, 17, 21)
4. **Parse module system** requirements
5. **Add comprehensive error handling** for malformed XML
6. **Include logging** for debugging and monitoring
7. **Create unit tests** covering all detection methods

### TESTING REQUIREMENTS:
- Test with various Java version formats (8, 9, 11, 17, 21)
- Test with different Maven POM structures
- Test module system detection
- Test with malformed pom.xml files
- Achieve 90%+ code coverage

---

## SUB-AGENT ASSIGNMENT INSTRUCTIONS

### FOR EACH SUB-AGENT:

1. **READ THE ENTIRE TASK DESCRIPTION** before starting
2. **ONLY TOUCH THE ASSIGNED FILE** - no other files
3. **IMPLEMENT ALL METHODS** completely with full functionality
4. **ADD COMPREHENSIVE TYPE HINTS** for all functions
5. **INCLUDE DETAILED DOCSTRINGS** explaining each method
6. **HANDLE EDGE CASES** and error conditions gracefully
7. **ADD LOGGING** for debugging and monitoring
8. **CREATE UNIT TESTS** with 90%+ code coverage
9. **FOLLOW PYTHON CODING STANDARDS** (PEP 8, type hints, etc.)

### SUB-AGENT PROMPT TEMPLATE:

```
You are assigned to implement [LANGUAGE] Version Detection Module.

YOUR FILE: [FILE_PATH]
YOUR TASK: [TASK_DESCRIPTION]

REQUIREMENTS:
- Implement ALL methods in the class structure provided
- Add comprehensive type hints and docstrings
- Handle edge cases and error conditions
- Include logging and error handling
- Create unit tests with 90%+ coverage
- ONLY touch the assigned file

DO NOT:
- Modify any other files
- Skip any methods
- Leave TODO comments
- Create incomplete implementations

START IMPLEMENTATION NOW.
```

---

## COORDINATION & REPORTING

### SUB-AGENT MANAGER RESPONSIBILITIES:

1. **ASSIGN TASKS**: Give each sub-agent their specific task and file
2. **MONITOR PROGRESS**: Check in on sub-agents periodically
3. **COLLECT RESULTS**: Gather completed implementations from all sub-agents
4. **VALIDATE COMPLETION**: Ensure all tasks are fully implemented
5. **REPORT SUMMARY**: Provide summary of all completed work

### COMPLETION CRITERIA:

Each sub-agent task is complete when:
- ✅ All methods are fully implemented
- ✅ Type hints are complete and correct
- ✅ Docstrings are comprehensive and clear
- ✅ Error handling is robust and graceful
- ✅ Logging is implemented throughout
- ✅ Unit tests achieve 90%+ coverage
- ✅ Code follows Python standards
- ✅ No TODO or incomplete code remains

### FINAL REPORT FORMAT:

```
GROUP A COMPLETION REPORT
========================

TASK A1 (Python): [STATUS] - [SUB-AGENT NAME]
- File: chunker/languages/version_detection/python_detector.py
- Methods implemented: [LIST]
- Test coverage: [PERCENTAGE]
- Issues/notes: [ANY]

TASK A2 (JavaScript): [STATUS] - [SUB-AGENT NAME]
- File: chunker/languages/version_detection/javascript_detector.py
- Methods implemented: [LIST]
- Test coverage: [PERCENTAGE]
- Issues/notes: [ANY]

[Continue for all 6 tasks...]

OVERALL STATUS: [COMPLETE/INCOMPLETE]
NEXT STEPS: [WHAT COMES AFTER GROUP A]
```

---

## IMPORTANT NOTES

### FILE BOUNDARIES:
- **EACH SUB-AGENT TOUCHES EXACTLY ONE FILE**
- **NO CROSS-FILE DEPENDENCIES** in Group A
- **ALL IMPORTS MUST BE STANDARD LIBRARY** or already available
- **NO NEW DEPENDENCIES** can be added

### IMPLEMENTATION STANDARDS:
- **FULL IMPLEMENTATION** - no stubs or placeholders
- **PRODUCTION-READY CODE** - not prototype quality
- **COMPREHENSIVE TESTING** - 90%+ coverage required
- **ERROR HANDLING** - graceful degradation for all edge cases
- **LOGGING** - meaningful debug and info messages

### COORDINATION:
- **PARALLEL EXECUTION** - all 6 tasks can run simultaneously
- **INDEPENDENT WORK** - no coordination needed between sub-agents
- **MANAGER OVERSIGHT** - you coordinate and collect results
- **QUALITY GATES** - validate completion before reporting

---

## EXECUTION COMMAND

**COPY AND PASTE THIS ENTIRE PROMPT** into your sub-agent manager system to begin parallel execution of Group A tasks.

**EXPECTED DURATION**: 2-3 days with parallel execution
**EXPECTED OUTCOME**: 6 fully functional language version detection modules
**NEXT PHASE**: Group B (Compatibility Database) after Group A completion

**START EXECUTION NOW** with the sub-agent assignment instructions above.

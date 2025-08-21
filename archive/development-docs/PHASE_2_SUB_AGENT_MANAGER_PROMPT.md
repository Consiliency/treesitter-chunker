# PHASE 2 SUB-AGENT MANAGER PROMPT
# Language-Specific Extractors - Parallel Execution

## AGENT IDENTIFICATION & ROLES

**WHO I AM**: I am the primary AI agent working on Phase 1.7, Phase 1.8, Phase 1.9, and Phase 2 implementation planning and coordination. I will NOT touch any of the files assigned to sub-agents in this prompt.

**WHO YOU ARE**: You are the sub-agent manager responsible for coordinating execution of Phase 2 tasks. These tasks implement dedicated language-specific extractors for all 30+ supported programming languages.

**WHO THE SUB-AGENTS ARE**: Individual AI agents that will implement specific language extractors and testing components. Each sub-agent works on exactly ONE file and ONE task.

## EXECUTION STRATEGY

**PARALLEL EXECUTION**: 6 tasks designed for parallel execution with clear dependencies.
**FILE ISOLATION**: Each sub-agent touches ONLY their assigned file - no cross-file dependencies.
**QUALITY ASSURANCE**: 95%+ test coverage and production-ready code required.
**DEPENDENCY MANAGEMENT**: Core framework must complete before language extractors can start.

## PHASE 2 TASKS OVERVIEW

**OBJECTIVE**: Implement comprehensive language-specific extractors for all 30+ supported programming languages.
**DEPENDENCIES**: Phase 1.9 (Production-ready integration & polish) must be complete.
**OUTPUT**: Complete language support with specialized extractors for each language.
**TIMELINE**: 3 weeks with parallel execution.

**PARALLEL EXECUTION MODEL:**
- **Task 2.1**: Must complete first (core extraction framework)
- **Tasks 2.2, 2.3, 2.4, 2.5**: Can start simultaneously after Task 2.1 completion
- **Task 2.6**: Must wait for ALL other tasks completion

---

## TASK 2.1: CORE EXTRACTION FRAMEWORK

**ASSIGNED FILE**: `chunker/extractors/core/extraction_framework.py`
**SUB-AGENT**: Core Framework Specialist
**IMPLEMENTATION DEADLINE**: Complete within assigned timeframe
**DEPENDENCIES**: Phase 1.9 must be complete

### FILE STRUCTURE TO CREATE:
```python
# chunker/extractors/core/extraction_framework.py

from typing import Dict, List, Optional, Any, Union, Tuple, Protocol
from pathlib import Path
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
import time

logger = logging.getLogger(__name__)

@dataclass
class CallSite:
    """Represents a call site with precise location information."""
    function_name: str
    line_number: int
    column_number: int
    byte_start: int
    byte_end: int
    call_type: str  # 'function', 'method', 'constructor', etc.
    context: Dict[str, Any]
    language: str
    file_path: Path

@dataclass
class ExtractionResult:
    """Standardized result for all language extractors."""
    call_sites: List[CallSite]
    extraction_time: float
    errors: List[str]
    warnings: List[str]
    metadata: Dict[str, Any]
    performance_metrics: Dict[str, Any]

class BaseExtractor(ABC):
    """Abstract base class for all language-specific extractors."""
    
    def __init__(self, language: str):
        """Initialize the extractor for a specific language."""
        self.language = language
        self.logger = logging.getLogger(f"{__name__}.{language}")
        self.performance_metrics = {}
        
    @abstractmethod
    def extract_calls(self, source_code: str, file_path: Optional[Path] = None) -> ExtractionResult:
        """Extract call sites from source code."""
        pass
    
    @abstractmethod
    def validate_source(self, source_code: str) -> bool:
        """Validate source code for the language."""
        pass
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics for the extractor."""
        return self.performance_metrics.copy()
    
    def cleanup(self) -> None:
        """Clean up resources used by the extractor."""
        pass

class CommonPatterns:
    """Common pattern recognition utilities for all extractors."""
    
    @staticmethod
    def is_function_call(node: Any) -> bool:
        """Check if AST node represents a function call."""
        # Implementation: Generic function call detection
        
    @staticmethod
    def is_method_call(node: Any) -> bool:
        """Check if AST node represents a method call."""
        # Implementation: Generic method call detection
        
    @staticmethod
    def extract_call_context(node: Any) -> Dict[str, Any]:
        """Extract context information from call node."""
        # Implementation: Context extraction
        
    @staticmethod
    def calculate_byte_offsets(node: Any, source_code: str) -> Tuple[int, int]:
        """Calculate byte start and end offsets for a node."""
        # Implementation: Byte offset calculation

class ExtractionUtils:
    """Common utility functions for all extractors."""
    
    @staticmethod
    def safe_extract(extractor_func: callable, *args, **kwargs) -> Any:
        """Safely execute extraction with error handling."""
        # Implementation: Safe execution wrapper
        
    @staticmethod
    def validate_byte_offsets(start: int, end: int, source_length: int) -> bool:
        """Validate byte offset values."""
        # Implementation: Offset validation
        
    @staticmethod
    def normalize_function_name(name: str) -> str:
        """Normalize function names for consistency."""
        # Implementation: Name normalization
        
    @staticmethod
    def extract_file_metadata(file_path: Path) -> Dict[str, Any]:
        """Extract metadata from file path."""
        # Implementation: File metadata extraction
```

### IMPLEMENTATION REQUIREMENTS:
1. **Complete all classes and methods** with full implementation
2. **Provide robust base framework** for all language extractors
3. **Add comprehensive type hints** for all functions
4. **Include detailed docstrings** explaining each method
5. **Handle edge cases** and error conditions gracefully
6. **Add logging** for debugging and monitoring
7. **Create unit tests** covering all methods
8. **Ensure no cross-file dependencies** within this task

---

## TASK 2.2: PYTHON EXTRACTOR

**ASSIGNED FILE**: `chunker/extractors/python/python_extractor.py`
**SUB-AGENT**: Python Extractor Specialist
**IMPLEMENTATION DEADLINE**: Complete within assigned timeframe
**DEPENDENCIES**: Task 2.1 (Core Framework) must be complete

### FILE STRUCTURE TO CREATE:
```python
# chunker/extractors/python/python_extractor.py

from typing import Dict, List, Optional, Any, Union, Tuple
from pathlib import Path
import logging
import ast
from ast import NodeVisitor, Call, FunctionDef, ClassDef, Attribute

from ..core.extraction_framework import BaseExtractor, ExtractionResult, CallSite

logger = logging.getLogger(__name__)

class PythonCallVisitor(NodeVisitor):
    """AST visitor for Python call site detection."""
    
    def __init__(self, source_code: str, file_path: Optional[Path] = None):
        """Initialize the Python call visitor."""
        self.source_code = source_code
        self.file_path = file_path
        self.call_sites = []
        self.current_context = {}
        
    def visit_Call(self, node: Call) -> None:
        """Visit call nodes to extract call site information."""
        # Implementation: Call node processing
        
    def visit_FunctionDef(self, node: FunctionDef) -> None:
        """Visit function definitions to update context."""
        # Implementation: Function context tracking
        
    def visit_ClassDef(self, node: ClassDef) -> None:
        """Visit class definitions to update context."""
        # Implementation: Class context tracking
        
    def visit_Attribute(self, node: Attribute) -> None:
        """Visit attribute nodes for method call detection."""
        # Implementation: Attribute processing

class PythonExtractor(BaseExtractor):
    """Specialized extractor for Python source code."""
    
    def __init__(self):
        """Initialize Python extractor."""
        super().__init__("python")
        self.patterns = PythonPatterns()
        
    def extract_calls(self, source_code: str, file_path: Optional[Path] = None) -> ExtractionResult:
        """Extract call sites from Python source code."""
        # Implementation: Python call extraction
        
    def validate_source(self, source_code: str) -> bool:
        """Validate Python source code."""
        # Implementation: Python validation
        
    def extract_function_calls(self, source_code: str) -> List[CallSite]:
        """Extract function calls from Python code."""
        # Implementation: Function call extraction
        
    def extract_method_calls(self, source_code: str) -> List[CallSite]:
        """Extract method calls from Python code."""
        # Implementation: Method call extraction

class PythonPatterns:
    """Python-specific pattern recognition."""
    
    @staticmethod
    def is_function_call(node: ast.Call) -> bool:
        """Check if call node represents a function call."""
        # Implementation: Function call detection
        
    @staticmethod
    def is_method_call(node: ast.Call) -> bool:
        """Check if call node represents a method call."""
        # Implementation: Method call detection
        
    @staticmethod
    def extract_call_context(node: ast.Call, context: Dict[str, Any]) -> Dict[str, Any]:
        """Extract context information from Python call node."""
        # Implementation: Context extraction
```

### IMPLEMENTATION REQUIREMENTS:
1. **Complete all classes and methods** with full implementation
2. **Integrate with Task 2.1** core framework
3. **Add comprehensive type hints** for all functions
4. **Include detailed docstrings** explaining each method
5. **Handle edge cases** and error conditions gracefully
6. **Add logging** for debugging and monitoring
7. **Create unit tests** covering all methods
8. **Ensure no cross-file dependencies** within this task

---

## TASK 2.3: JAVASCRIPT EXTRACTOR

**ASSIGNED FILE**: `chunker/extractors/javascript/javascript_extractor.py`
**SUB-AGENT**: JavaScript Extractor Specialist
**IMPLEMENTATION DEADLINE**: Complete within assigned timeframe
**DEPENDENCIES**: Task 2.1 (Core Framework) must be complete

### FILE STRUCTURE TO CREATE:
```python
# chunker/extractors/javascript/javascript_extractor.py

from typing import Dict, List, Optional, Any, Union, Tuple
from pathlib import Path
import logging
import re

from ..core.extraction_framework import BaseExtractor, ExtractionResult, CallSite

logger = logging.getLogger(__name__)

class JavaScriptExtractor(BaseExtractor):
    """Specialized extractor for JavaScript/TypeScript source code."""
    
    def __init__(self):
        """Initialize JavaScript extractor."""
        super().__init__("javascript")
        self.patterns = JavaScriptPatterns()
        
    def extract_calls(self, source_code: str, file_path: Optional[Path] = None) -> ExtractionResult:
        """Extract call sites from JavaScript source code."""
        # Implementation: JavaScript call extraction
        
    def validate_source(self, source_code: str) -> bool:
        """Validate JavaScript source code."""
        # Implementation: JavaScript validation
        
    def extract_function_calls(self, source_code: str) -> List[CallSite]:
        """Extract function calls from JavaScript code."""
        # Implementation: Function call extraction
        
    def extract_method_calls(self, source_code: str) -> List[CallSite]:
        """Extract method calls from JavaScript code."""
        # Implementation: Method call extraction

class JavaScriptPatterns:
    """JavaScript-specific pattern recognition."""
    
    @staticmethod
    def find_function_calls(source_code: str) -> List[Dict[str, Any]]:
        """Find function calls using regex patterns."""
        # Implementation: Function call detection
        
    @staticmethod
    def find_method_calls(source_code: str) -> List[Dict[str, Any]]:
        """Find method calls using regex patterns."""
        # Implementation: Method call detection
        
    @staticmethod
    def extract_call_context(match: re.Match, source_code: str) -> Dict[str, Any]:
        """Extract context information from JavaScript call match."""
        # Implementation: Context extraction
```

### IMPLEMENTATION REQUIREMENTS:
1. **Complete all classes and methods** with full implementation
2. **Integrate with Task 2.1** core framework
3. **Add comprehensive type hints** for all functions
4. **Include detailed docstrings** explaining each method
5. **Handle edge cases** and error conditions gracefully
6. **Add logging** for debugging and monitoring
7. **Create unit tests** covering all methods
8. **Ensure no cross-file dependencies** within this task

---

## TASK 2.4: RUST EXTRACTOR

**ASSIGNED FILE**: `chunker/extractors/rust/rust_extractor.py`
**SUB-AGENT**: Rust Extractor Specialist
**IMPLEMENTATION DEADLINE**: Complete within assigned timeframe
**DEPENDENCIES**: Task 2.1 (Core Framework) must be complete

### FILE STRUCTURE TO CREATE:
```python
# chunker/extractors/rust/rust_extractor.py

from typing import Dict, List, Optional, Any, Union, Tuple
from pathlib import Path
import logging
import re

from ..core.extraction_framework import BaseExtractor, ExtractionResult, CallSite

logger = logging.getLogger(__name__)

class RustExtractor(BaseExtractor):
    """Specialized extractor for Rust source code."""
    
    def __init__(self):
        """Initialize Rust extractor."""
        super().__init__("rust")
        self.patterns = RustPatterns()
        
    def extract_calls(self, source_code: str, file_path: Optional[Path] = None) -> ExtractionResult:
        """Extract call sites from Rust source code."""
        # Implementation: Rust call extraction
        
    def validate_source(self, source_code: str) -> bool:
        """Validate Rust source code."""
        # Implementation: Rust validation
        
    def extract_function_calls(self, source_code: str) -> List[CallSite]:
        """Extract function calls from Rust code."""
        # Implementation: Function call extraction
        
    def extract_method_calls(self, source_code: str) -> List[CallSite]:
        """Extract method calls from Rust code."""
        # Implementation: Method call extraction

class RustPatterns:
    """Rust-specific pattern recognition."""
    
    @staticmethod
    def find_function_calls(source_code: str) -> List[Dict[str, Any]]:
        """Find function calls using regex patterns."""
        # Implementation: Function call detection
        
    @staticmethod
    def find_method_calls(source_code: str) -> List[Dict[str, Any]]:
        """Find method calls using regex patterns."""
        # Implementation: Method call detection
        
    @staticmethod
    def find_macro_calls(source_code: str) -> List[Dict[str, Any]]:
        """Find macro invocations using regex patterns."""
        # Implementation: Macro call detection
```

### IMPLEMENTATION REQUIREMENTS:
1. **Complete all classes and methods** with full implementation
2. **Integrate with Task 2.1** core framework
3. **Add comprehensive type hints** for all functions
4. **Include detailed docstrings** explaining each method
5. **Handle edge cases** and error conditions gracefully
6. **Add logging** for debugging and monitoring
7. **Create unit tests** covering all methods
8. **Ensure no cross-file dependencies** within this task

---

## TASK 2.5: MULTI-LANGUAGE EXTRACTORS

**ASSIGNED FILE**: `chunker/extractors/multi_language/multi_extractor.py`
**SUB-AGENT**: Multi-Language Extractor Specialist
**IMPLEMENTATION DEADLINE**: Complete within assigned timeframe
**DEPENDENCIES**: Task 2.1 (Core Framework) must be complete

### FILE STRUCTURE TO CREATE:
```python
# chunker/extractors/multi_language/multi_extractor.py

from typing import Dict, List, Optional, Any, Union, Tuple
from pathlib import Path
import logging
import re

from ..core.extraction_framework import BaseExtractor, ExtractionResult, CallSite

logger = logging.getLogger(__name__)

class GoExtractor(BaseExtractor):
    """Specialized extractor for Go source code."""
    
    def __init__(self):
        """Initialize Go extractor."""
        super().__init__("go")
        self.patterns = GoPatterns()
        
    def extract_calls(self, source_code: str, file_path: Optional[Path] = None) -> ExtractionResult:
        """Extract call sites from Go source code."""
        # Implementation: Go call extraction

class CExtractor(BaseExtractor):
    """Specialized extractor for C source code."""
    
    def __init__(self):
        """Initialize C extractor."""
        super().__init__("c")
        self.patterns = CPatterns()
        
    def extract_calls(self, source_code: str, file_path: Optional[Path] = None) -> ExtractionResult:
        """Extract call sites from C source code."""
        # Implementation: C call extraction

class CppExtractor(BaseExtractor):
    """Specialized extractor for C++ source code."""
    
    def __init__(self):
        """Initialize C++ extractor."""
        super().__init__("cpp")
        self.patterns = CppPatterns()
        
    def extract_calls(self, source_code: str, file_path: Optional[Path] = None) -> ExtractionResult:
        """Extract call sites from C++ source code."""
        # Implementation: C++ call extraction

class JavaExtractor(BaseExtractor):
    """Specialized extractor for Java source code."""
    
    def __init__(self):
        """Initialize Java extractor."""
        super().__init__("java")
        self.patterns = JavaPatterns()
        
    def extract_calls(self, source_code: str, file_path: Optional[Path] = None) -> ExtractionResult:
        """Extract call sites from Java source code."""
        # Implementation: Java call extraction

class OtherLanguagesExtractor(BaseExtractor):
    """Generic extractor for other supported languages."""
    
    def __init__(self, language: str):
        """Initialize generic extractor for specified language."""
        super().__init__(language)
        self.patterns = GenericPatterns()
        
    def extract_calls(self, source_code: str, file_path: Optional[Path] = None) -> ExtractionResult:
        """Extract call sites using generic patterns."""
        # Implementation: Generic call extraction

# Pattern classes for each language...
class GoPatterns:
    """Go-specific pattern recognition."""
    pass

class CPatterns:
    """C-specific pattern recognition."""
    pass

class CppPatterns:
    """C++-specific pattern recognition."""
    pass

class JavaPatterns:
    """Java-specific pattern recognition."""
    pass

class GenericPatterns:
    """Generic pattern recognition for other languages."""
    pass
```

### IMPLEMENTATION REQUIREMENTS:
1. **Complete all classes and methods** with full implementation
2. **Integrate with Task 2.1** core framework
3. **Add comprehensive type hints** for all functions
4. **Include detailed docstrings** explaining each method
5. **Handle edge cases** and error conditions gracefully
6. **Add logging** for debugging and monitoring
7. **Create unit tests** covering all methods
8. **Ensure no cross-file dependencies** within this task

---

## TASK 2.6: INTEGRATION TESTING

**ASSIGNED FILE**: `chunker/extractors/testing/integration_tester.py`
**SUB-AGENT**: Integration Testing Specialist
**IMPLEMENTATION DEADLINE**: Complete within assigned timeframe
**DEPENDENCIES**: All other tasks (2.1, 2.2, 2.3, 2.4, 2.5) must be complete

### FILE STRUCTURE TO CREATE:
```python
# chunker/extractors/testing/integration_tester.py

from typing import Dict, List, Optional, Any, Union, Tuple
from pathlib import Path
import logging
import time
import json

# Import from all other tasks
from ..core.extraction_framework import BaseExtractor
from ..python.python_extractor import PythonExtractor
from ..javascript.javascript_extractor import JavaScriptExtractor
from ..rust.rust_extractor import RustExtractor
from ..multi_language.multi_extractor import (
    GoExtractor, CExtractor, CppExtractor, JavaExtractor, OtherLanguagesExtractor
)

logger = logging.getLogger(__name__)

class ExtractorTestSuite:
    """Complete test suite for all language extractors."""
    
    def __init__(self):
        """Initialize the test suite."""
        self.extractors = {
            'python': PythonExtractor(),
            'javascript': JavaScriptExtractor(),
            'rust': RustExtractor(),
            'go': GoExtractor(),
            'c': CExtractor(),
            'cpp': CppExtractor(),
            'java': JavaExtractor(),
        }
        
    def run_all_tests(self) -> Dict[str, Any]:
        """Run complete test suite for all extractors."""
        # Implementation: Complete test execution
        
    def test_language_extractors(self) -> Dict[str, Any]:
        """Test individual language extractors."""
        # Implementation: Language-specific testing
        
    def test_cross_language_integration(self) -> Dict[str, Any]:
        """Test integration between different language extractors."""
        # Implementation: Cross-language testing
        
    def benchmark_performance(self) -> Dict[str, Any]:
        """Benchmark performance of all extractors."""
        # Implementation: Performance benchmarking

class IntegrationTester:
    """Integration testing for the complete extractor system."""
    
    def __init__(self):
        """Initialize integration tester."""
        self.test_suite = ExtractorTestSuite()
        
    def test_complete_workflow(self) -> Dict[str, Any]:
        """Test complete extraction workflow."""
        # Implementation: Workflow testing
        
    def validate_accuracy(self) -> Dict[str, Any]:
        """Validate accuracy of all extractors."""
        # Implementation: Accuracy validation
        
    def test_error_handling(self) -> Dict[str, Any]:
        """Test error handling across all extractors."""
        # Implementation: Error handling testing
        
    def test_performance_integration(self) -> Dict[str, Any]:
        """Test performance integration."""
        # Implementation: Performance integration testing

def run_complete_extractor_test_suite() -> Dict[str, Any]:
    """Run complete extractor test suite."""
    # Implementation: Complete test suite execution
```

### IMPLEMENTATION REQUIREMENTS:
1. **Complete all classes and methods** with full implementation
2. **Integrate with all other tasks** (import all components)
3. **Add comprehensive type hints** for all functions
4. **Include detailed docstrings** explaining each method
5. **Handle edge cases** and error conditions gracefully
6. **Add logging** for debugging and monitoring
7. **Create unit tests** covering all methods
8. **Ensure comprehensive testing** of all extractors

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
8. **CREATE UNIT TESTS** with 95%+ coverage
9. **FOLLOW PYTHON CODING STANDARDS** (PEP 8, type hints, etc.)
10. **ENSURE PRODUCTION-READY CODE** - no prototypes or stubs

### EXECUTION ORDER:

**IMPORTANT**: These tasks have specific dependencies:

1. **Task 2.1**: Must complete first (core extraction framework)
2. **Tasks 2.2, 2.3, 2.4, 2.5**: Can start simultaneously after Task 2.1 completion
3. **Task 2.6**: Must wait for ALL other tasks completion

### SUB-AGENT PROMPT TEMPLATE:

```
You are assigned to implement [TASK_NAME] for Phase 2.

YOUR FILE: [FILE_PATH]
YOUR TASK: [TASK_DESCRIPTION]
DEPENDENCIES: [LIST OF DEPENDENCIES]
PHASE 2 ALIGNMENT: [SPECIFIC ALIGNMENT REQUIREMENTS]

REQUIREMENTS:
- Implement ALL methods in the class structure provided
- Add comprehensive type hints and docstrings
- Handle edge cases and error conditions
- Include logging and error handling
- Create unit tests with 95%+ coverage
- ONLY touch the assigned file
- Ensure compatibility with [DEPENDENT_TASKS] if applicable
- Maintain production-ready code quality

DO NOT:
- Modify any other files
- Skip any methods
- Leave TODO comments
- Create incomplete implementations
- Deviate from Phase 2 specification requirements

START IMPLEMENTATION NOW.
```

---

## COORDINATION & REPORTING

### SUB-AGENT MANAGER RESPONSIBILITIES:

1. **EXECUTE CORE TASK FIRST**: Start Task 2.1 (Core Extraction Framework) immediately
2. **WAIT FOR CORE COMPLETION**: Ensure Task 2.1 is complete before starting other tasks
3. **EXECUTE LANGUAGE EXTRACTORS**: Start Tasks 2.2, 2.3, 2.4, 2.5 simultaneously after Task 2.1 completion
4. **EXECUTE INTEGRATION TESTING**: Start Task 2.6 after all other tasks complete
5. **COLLECT RESULTS**: Gather completed implementations from each sub-agent
6. **VALIDATE COMPLETION**: Ensure all tasks are fully implemented
7. **VERIFY PHASE 2 READINESS**: Confirm system is ready for production
8. **REPORT SUMMARY**: Provide summary of all completed work

### COMPLETION CRITERIA:

Each sub-agent task is complete when:
- ✅ All methods are fully implemented
- ✅ Type hints are complete and correct
- ✅ Docstrings are comprehensive and clear
- ✅ Error handling is robust and graceful
- ✅ Logging is implemented throughout
- ✅ Unit tests achieve 95%+ coverage
- ✅ Code follows Python standards
- ✅ No TODO or incomplete code remains
- ✅ Dependencies are properly integrated
- ✅ Production-ready quality achieved

### FINAL REPORT FORMAT:

```
PHASE 2 COMPLETION REPORT
=========================

TASK 2.1 (Core Framework): [STATUS] - [SUB-AGENT NAME]
- File: chunker/extractors/core/extraction_framework.py
- Methods implemented: [LIST]
- Test coverage: [PERCENTAGE]
- Production readiness: [STATUS]
- Issues/notes: [ANY]

TASK 2.2 (Python Extractor): [STATUS] - [SUB-AGENT NAME]
- File: chunker/extractors/python/python_extractor.py
- Methods implemented: [LIST]
- Test coverage: [PERCENTAGE]
- Python features: [LIST]
- Production readiness: [STATUS]
- Issues/notes: [ANY]

TASK 2.3 (JavaScript Extractor): [STATUS] - [SUB-AGENT NAME]
- File: chunker/extractors/javascript/javascript_extractor.py
- Methods implemented: [LIST]
- Test coverage: [PERCENTAGE]
- JavaScript features: [LIST]
- Production readiness: [STATUS]
- Issues/notes: [ANY]

TASK 2.4 (Rust Extractor): [STATUS] - [SUB-AGENT NAME]
- File: chunker/extractors/rust/rust_extractor.py
- Methods implemented: [LIST]
- Test coverage: [PERCENTAGE]
- Rust features: [LIST]
- Production readiness: [STATUS]
- Issues/notes: [ANY]

TASK 2.5 (Multi-Language Extractors): [STATUS] - [SUB-AGENT NAME]
- File: chunker/extractors/multi_language/multi_extractor.py
- Methods implemented: [LIST]
- Test coverage: [PERCENTAGE]
- Languages supported: [LIST]
- Production readiness: [STATUS]
- Issues/notes: [ANY]

TASK 2.6 (Integration Testing): [STATUS] - [SUB-AGENT NAME]
- File: chunker/extractors/testing/integration_tester.py
- Methods implemented: [LIST]
- Test coverage: [PERCENTAGE]
- Integration tests: [LIST]
- Production readiness: [STATUS]
- Issues/notes: [ANY]

OVERALL STATUS: [COMPLETE/INCOMPLETE]
PHASE 2 READINESS: [READY/NOT READY]
NEXT STEPS: [PHASE 3 IMPLEMENTATION]
```

---

## IMPORTANT NOTES

### FILE BOUNDARIES:
- **EACH SUB-AGENT TOUCHES EXACTLY ONE FILE**
- **NO CROSS-FILE DEPENDENCIES** within individual tasks
- **ALL IMPORTS MUST BE STANDARD LIBRARY** or from completed tasks
- **NO NEW DEPENDENCIES** can be added

### DEPENDENCY MANAGEMENT:
- **2.1 (Core)**: No dependencies - can start immediately
- **2.2, 2.3, 2.4, 2.5**: Depend on Task 2.1 completion
- **2.6 (Testing)**: Depends on ALL other tasks completion

### QUALITY STANDARDS:
- **FULL IMPLEMENTATION** - no stubs or placeholders
- **PRODUCTION-READY CODE** - not prototype quality
- **COMPREHENSIVE TESTING** - 95%+ coverage required
- **ERROR HANDLING** - graceful degradation for all edge cases
- **LOGGING** - meaningful debug and info messages
- **PHASE 2 COMPLIANCE** - specification requirements met

### COORDINATION:
- **SEQUENTIAL EXECUTION** - Task 2.1 must complete first
- **PARALLEL EXECUTION** - Tasks 2.2-2.5 can start simultaneously after Task 2.1
- **DEPENDENCY VALIDATION** - ensure previous tasks complete before starting dependent tasks
- **MANAGER OVERSIGHT** - you coordinate and ensure proper execution order
- **QUALITY GATES** - validate completion before proceeding to dependent tasks
- **PRODUCTION READINESS** - confirm system meets all quality requirements

---

## EXECUTION COMMAND

**COPY AND PASTE THIS ENTIRE PROMPT** into your sub-agent manager system to begin execution of Phase 2 tasks.

**EXPECTED DURATION**: 3 weeks with parallel execution
**EXPECTED OUTCOME**: Complete Phase 2 system with all language extractors implemented
**NEXT PHASE**: Phase 3 (Performance optimization and validation)

## PHASE 2 READINESS VALIDATION

### FINAL VALIDATION CHECKLIST:

Before marking Phase 2 complete, verify:

1. **Core Framework**: ✅ Fully functional and robust
2. **Python Extractor**: ✅ Accurate Python call extraction
3. **JavaScript Extractor**: ✅ Accurate JavaScript call extraction
4. **Rust Extractor**: ✅ Accurate Rust call extraction
5. **Multi-Language Extractors**: ✅ All languages supported
6. **Integration Testing**: ✅ Complete system validation and testing
7. **Production Readiness**: ✅ System ready for production deployment
8. **Quality Standards**: ✅ 95%+ test coverage achieved
9. **Language Support**: ✅ All 30+ languages working correctly
10. **Performance**: ✅ Meets production performance benchmarks

**START EXECUTION NOW** with Task 2.1 (Core Extraction Framework), then proceed with Tasks 2.2-2.5 in parallel after completion, and finally Task 2.6 for integration testing.

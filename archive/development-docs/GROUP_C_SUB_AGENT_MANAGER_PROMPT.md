# GROUP C SUB-AGENT MANAGER PROMPT
# Phase 1.7: Smart Error Handling & User Guidance
# Error Analysis & Classification

## AGENT IDENTIFICATION & ROLES

**WHO I AM**: I am the primary AI agent working on Phase 1.7 implementation planning and coordination. I will NOT touch any of the files assigned to sub-agents in this prompt.

**WHO YOU ARE**: You are the sub-agent manager responsible for coordinating execution of Group C tasks. These tasks have mixed dependencies - some independent, some dependent.

**WHO THE SUB-AGENTS ARE**: Individual AI agents that will implement specific error analysis and classification components. Each sub-agent works on exactly ONE file and ONE task.

## EXECUTION STRATEGY

**MIXED EXECUTION**: Some tasks can run in parallel, others have dependencies.
**FILE ISOLATION**: Each sub-agent touches ONLY their assigned file - no cross-file dependencies.
**COORDINATION**: You will manage the execution order and ensure dependencies are met.

## GROUP C TASKS OVERVIEW

**OBJECTIVE**: Implement error analysis and classification system for detecting and categorizing various types of errors.
**DEPENDENCIES**: Mixed - C1 is independent, C2 depends on Group A and B, C3 depends on C1.
**OUTPUT**: Complete error analysis and classification system.

---

## TASK C1: ERROR CLASSIFICATION SYSTEM

**ASSIGNED FILE**: `chunker/error_handling/classifier.py`
**SUB-AGENT**: Error Classification Specialist
**IMPLEMENTATION DEADLINE**: Complete within assigned timeframe
**DEPENDENCIES**: None - can start immediately

### FILE STRUCTURE TO CREATE:
```python
# chunker/error_handling/classifier.py

from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import re
import logging

logger = logging.getLogger(__name__)

class ErrorSeverity(Enum):
    """Error severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

class ErrorCategory(Enum):
    """Error categories for classification."""
    SYNTAX = "syntax"
    COMPATIBILITY = "compatibility"
    GRAMMAR = "grammar"
    PARSING = "parsing"
    CONFIGURATION = "configuration"
    SYSTEM = "system"
    NETWORK = "network"
    PERMISSION = "permission"
    UNKNOWN = "unknown"

class ErrorSource(Enum):
    """Source of the error."""
    TREE_SITTER = "tree_sitter"
    GRAMMAR_LOADER = "grammar_loader"
    METADATA_EXTRACTOR = "metadata_extractor"
    VERSION_DETECTOR = "version_detector"
    COMPATIBILITY_CHECKER = "compatibility_checker"
    USER_INPUT = "user_input"
    SYSTEM = "system"
    EXTERNAL = "external"

@dataclass
class ErrorContext:
    """Context information for an error."""
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    column_number: Optional[int] = None
    language: Optional[str] = None
    grammar_version: Optional[str] = None
    user_agent: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    session_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        
    def __str__(self) -> str:
        """String representation of error context."""

@dataclass
class ClassifiedError:
    """A classified error with all relevant information."""
    error_id: str
    message: str
    category: ErrorCategory
    severity: ErrorSeverity
    source: ErrorSource
    context: ErrorContext
    raw_error: Optional[Any] = None
    suggested_actions: List[str] = field(default_factory=list)
    related_errors: List[str] = field(default_factory=list)
    confidence: float = 1.0
    
    def __post_init__(self):
        """Validate error data."""
        if not self.error_id or not self.message:
            raise ValueError("Error ID and message are required")
        if not isinstance(self.category, ErrorCategory):
            raise ValueError("Category must be ErrorCategory enum")
        if not isinstance(self.severity, ErrorSeverity):
            raise ValueError("Severity must be ErrorSeverity enum")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        
    def __str__(self) -> str:
        """String representation of classified error."""
        
    def add_suggested_action(self, action: str) -> None:
        """Add a suggested action for resolving this error."""
        
    def add_related_error(self, error_id: str) -> None:
        """Add a related error ID."""
        
    def update_confidence(self, confidence: float) -> None:
        """Update the confidence level of this classification."""

class ErrorClassifier:
    """Main class for classifying errors into categories and severity levels."""
    
    def __init__(self):
        self.patterns = self._load_error_patterns()
        self.classification_rules = self._load_classification_rules()
        self.severity_mapping = self._load_severity_mapping()
        
    def _load_error_patterns(self) -> Dict[str, List[re.Pattern]]:
        """Load regex patterns for error detection."""
        # Implementation: Define patterns for different error types
        # Return: Dict mapping ErrorCategory to list of regex patterns
        
    def _load_classification_rules(self) -> Dict[str, Dict[str, Any]]:
        """Load rules for error classification."""
        # Implementation: Define classification rules and logic
        # Return: Dict with classification rules
        
    def _load_severity_mapping(self) -> Dict[str, ErrorSeverity]:
        """Load mapping of error types to severity levels."""
        # Implementation: Map error patterns to severity levels
        # Return: Dict mapping error patterns to ErrorSeverity
        
    def classify_error(self, error_message: str, raw_error: Optional[Any] = None,
                      context: Optional[ErrorContext] = None) -> ClassifiedError:
        """Classify an error message into categories and severity."""
        # Implementation: Apply patterns and rules to classify error
        # Return: ClassifiedError object
        
    def detect_error_category(self, error_message: str) -> ErrorCategory:
        """Detect the category of an error from its message."""
        # Implementation: Apply category detection patterns
        # Return: ErrorCategory enum value
        
    def determine_error_severity(self, error_message: str, category: ErrorCategory) -> ErrorSeverity:
        """Determine the severity level of an error."""
        # Implementation: Apply severity mapping rules
        # Return: ErrorSeverity enum value
        
    def identify_error_source(self, error_message: str, raw_error: Any) -> ErrorSource:
        """Identify the source of an error."""
        # Implementation: Analyze error to determine source
        # Return: ErrorSource enum value
        
    def extract_error_context(self, error_message: str, raw_error: Any) -> ErrorContext:
        """Extract context information from an error."""
        # Implementation: Parse error for file, line, column, language info
        # Return: ErrorContext object
        
    def generate_suggested_actions(self, category: ErrorCategory, 
                                 severity: ErrorSeverity) -> List[str]:
        """Generate suggested actions for resolving an error."""
        # Implementation: Map error type to resolution actions
        # Return: List of suggested action strings
        
    def calculate_confidence(self, error_message: str, patterns_matched: List[str]) -> float:
        """Calculate confidence level for error classification."""
        # Implementation: Score confidence based on pattern matches
        # Return: Confidence score between 0.0 and 1.0
        
    def batch_classify_errors(self, error_messages: List[str]) -> List[ClassifiedError]:
        """Classify multiple errors in batch."""
        # Implementation: Process multiple errors efficiently
        # Return: List of ClassifiedError objects
        
    def update_classification_rules(self, new_rules: Dict[str, Any]) -> None:
        """Update classification rules dynamically."""
        # Implementation: Add or modify classification rules
        # Return: None, updates internal rules
        
    def export_classification_rules(self, output_path: str) -> None:
        """Export current classification rules to file."""
        # Implementation: Serialize rules to JSON or other format
        # Return: None, writes to specified path
        
    def import_classification_rules(self, input_path: str) -> None:
        """Import classification rules from file."""
        # Implementation: Load rules from file
        # Return: None, loads rules into memory

class ErrorPatternMatcher:
    """Advanced pattern matching for error classification."""
    
    def __init__(self):
        self.compiled_patterns = {}
        self.pattern_metadata = {}
        
    def add_pattern(self, name: str, pattern: str, category: ErrorCategory,
                   severity: ErrorSeverity, confidence: float = 1.0) -> None:
        """Add a new error pattern."""
        # Implementation: Compile and store pattern with metadata
        # Return: None, adds pattern to matcher
        
    def match_patterns(self, error_message: str) -> List[Dict[str, Any]]:
        """Match error message against all patterns."""
        # Implementation: Apply all patterns and return matches
        # Return: List of pattern match results
        
    def get_best_match(self, error_message: str) -> Optional[Dict[str, Any]]:
        """Get the best matching pattern for an error message."""
        # Implementation: Score matches and return best one
        # Return: Best match dict or None
        
    def remove_pattern(self, name: str) -> bool:
        """Remove a pattern by name."""
        # Implementation: Remove pattern from matcher
        # Return: True if removed, False if not found
        
    def list_patterns(self) -> List[str]:
        """List all pattern names."""
        # Implementation: Return list of pattern names
        # Return: List of pattern name strings

class ErrorConfidenceScorer:
    """Scores confidence levels for error classifications."""
    
    def __init__(self):
        self.scoring_rules = self._load_scoring_rules()
        
    def _load_scoring_rules(self) -> Dict[str, float]:
        """Load rules for confidence scoring."""
        # Implementation: Define scoring weights and rules
        # Return: Dict with scoring rules
        
    def score_classification(self, error_message: str, category: ErrorCategory,
                           patterns_matched: List[str], context: Optional[ErrorContext] = None) -> float:
        """Score the confidence of a classification."""
        # Implementation: Apply scoring algorithm
        # Return: Confidence score between 0.0 and 1.0
        
    def adjust_confidence_for_context(self, base_confidence: float, 
                                    context: ErrorContext) -> float:
        """Adjust confidence based on context information."""
        # Implementation: Modify confidence based on context
        # Return: Adjusted confidence score
        
    def get_confidence_explanation(self, confidence: float) -> str:
        """Get human-readable explanation of confidence score."""
        # Implementation: Explain what confidence level means
        # Return: Explanation string
```

### IMPLEMENTATION REQUIREMENTS:
1. **Complete all classes and methods** with full implementation
2. **Add comprehensive type hints** for all functions
3. **Include detailed docstrings** explaining each method's purpose
4. **Handle edge cases** like malformed error messages, missing context
5. **Implement pattern matching** with regex and rule-based systems
6. **Add comprehensive error handling** for classification failures
7. **Include logging** for debugging and monitoring
8. **Create unit tests** covering all classification methods

### TESTING REQUIREMENTS:
- Test with various error message formats
- Test pattern matching accuracy
- Test severity level determination
- Test context extraction
- Test confidence scoring
- Achieve 90%+ code coverage

---

## TASK C2: COMPATIBILITY ERROR DETECTOR

**ASSIGNED FILE**: `chunker/error_handling/compatibility_detector.py`
**SUB-AGENT**: Compatibility Error Detection Specialist
**IMPLEMENTATION DEADLINE**: Complete within assigned timeframe
**DEPENDENCIES**: Tasks A1-A6 (Language Version Detection) and B3 (Compatibility Database) must be completed first

### FILE STRUCTURE TO CREATE:
```python
# chunker/error_handling/compatibility_detector.py

from typing import Dict, List, Optional, Any, Tuple, Union
from pathlib import Path
import logging
import re
from datetime import datetime

# Import from completed tasks
from ..languages.version_detection.python_detector import PythonVersionDetector
from ..languages.version_detection.javascript_detector import JavaScriptVersionDetector
from ..languages.version_detection.rust_detector import RustVersionDetector
from ..languages.version_detection.go_detector import GoVersionDetector
from ..languages.version_detection.cpp_detector import CppVersionDetector
from ..languages.version_detection.java_detector import JavaVersionDetector
from ..languages.compatibility.database import CompatibilityDatabase
from ..error_handling.classifier import ClassifiedError, ErrorCategory, ErrorSeverity, ErrorSource

logger = logging.getLogger(__name__)

class CompatibilityErrorDetector:
    """Detects version compatibility issues between languages and grammars."""
    
    def __init__(self, compatibility_db: CompatibilityDatabase):
        self.compatibility_db = compatibility_db
        self.version_detectors = self._initialize_version_detectors()
        self.compatibility_patterns = self._load_compatibility_patterns()
        
    def _initialize_version_detectors(self) -> Dict[str, Any]:
        """Initialize version detectors for all supported languages."""
        # Implementation: Create detector instances for each language
        # Return: Dict mapping language to detector instance
        
    def _load_compatibility_patterns(self) -> Dict[str, List[re.Pattern]]:
        """Load patterns for detecting compatibility errors."""
        # Implementation: Define regex patterns for compatibility issues
        # Return: Dict mapping error type to list of patterns
        
    def detect_compatibility_errors(self, error_message: str, file_path: Optional[Path] = None,
                                  language: Optional[str] = None) -> List[ClassifiedError]:
        """Detect compatibility errors from error messages and file analysis."""
        # Implementation: Analyze error for compatibility issues
        # Return: List of ClassifiedError objects
        
    def analyze_file_compatibility(self, file_path: Path, language: str) -> Dict[str, Any]:
        """Analyze a file for compatibility issues."""
        # Implementation: Use version detectors to analyze file
        # Return: Dict with compatibility analysis results
        
    def detect_version_mismatch(self, detected_version: str, grammar_version: str,
                              language: str) -> Optional[ClassifiedError]:
        """Detect version mismatches between detected and grammar versions."""
        # Implementation: Compare versions and identify mismatches
        # Return: ClassifiedError for version mismatch or None
        
    def detect_feature_incompatibility(self, required_features: List[str],
                                    supported_features: List[str],
                                    language: str) -> List[ClassifiedError]:
        """Detect feature incompatibilities."""
        # Implementation: Compare required vs supported features
        # Return: List of ClassifiedError objects for incompatibilities
        
    def detect_breaking_changes(self, from_version: str, to_version: str,
                              language: str) -> List[ClassifiedError]:
        """Detect breaking changes between versions."""
        # Implementation: Query compatibility database for breaking changes
        # Return: List of ClassifiedError objects for breaking changes
        
    def generate_compatibility_report(self, file_path: Path, language: str) -> str:
        """Generate comprehensive compatibility report for a file."""
        # Implementation: Create detailed compatibility analysis report
        # Return: Formatted report string
        
    def suggest_compatible_versions(self, current_version: str, language: str) -> List[str]:
        """Suggest compatible versions for a language."""
        # Implementation: Query compatibility database for alternatives
        # Return: List of compatible version strings
        
    def validate_grammar_compatibility(self, language: str, version: str) -> bool:
        """Validate if grammar is compatible with language version."""
        # Implementation: Check compatibility database
        # Return: True if compatible, False otherwise
        
    def get_compatibility_details(self, language: str, version: str) -> Dict[str, Any]:
        """Get detailed compatibility information."""
        # Implementation: Query compatibility database for details
        # Return: Dict with compatibility information
        
    def update_compatibility_cache(self, language: str) -> None:
        """Update compatibility cache for a language."""
        # Implementation: Refresh compatibility data from database
        # Return: None, updates internal cache
        
    def export_compatibility_errors(self, output_path: Path) -> None:
        """Export detected compatibility errors to file."""
        # Implementation: Serialize compatibility errors to file
        # Return: None, writes to specified path

class VersionCompatibilityAnalyzer:
    """Analyzes version compatibility in detail."""
    
    def __init__(self, compatibility_db: CompatibilityDatabase):
        self.compatibility_db = compatibility_db
        
    def analyze_version_range(self, language: str, min_version: str, max_version: str) -> Dict[str, Any]:
        """Analyze compatibility across a version range."""
        # Implementation: Check compatibility for version range
        # Return: Dict with compatibility analysis
        
    def find_optimal_grammar_version(self, language: str, target_version: str) -> Optional[str]:
        """Find the optimal grammar version for a language version."""
        # Implementation: Query database for best grammar match
        # Return: Optimal grammar version or None
        
    def get_migration_path(self, from_version: str, to_version: str, language: str) -> List[str]:
        """Get migration path between versions."""
        # Implementation: Find intermediate versions for migration
        # Return: List of intermediate versions
        
    def analyze_dependency_compatibility(self, dependencies: Dict[str, str]) -> Dict[str, Any]:
        """Analyze compatibility of multiple dependencies."""
        # Implementation: Check compatibility across all dependencies
        # Return: Dict with dependency compatibility analysis

class CompatibilityErrorFormatter:
    """Formats compatibility errors for user consumption."""
    
    def __init__(self):
        self.error_templates = self._load_error_templates()
        
    def _load_error_templates(self) -> Dict[str, str]:
        """Load error message templates."""
        # Implementation: Define templates for different error types
        # Return: Dict mapping error type to template
        
    def format_version_mismatch_error(self, detected_version: str, grammar_version: str,
                                    language: str) -> str:
        """Format version mismatch error message."""
        # Implementation: Apply template and format error message
        # Return: Formatted error message string
        
    def format_feature_incompatibility_error(self, missing_features: List[str],
                                          language: str, version: str) -> str:
        """Format feature incompatibility error message."""
        # Implementation: Apply template and format error message
        # Return: Formatted error message string
        
    def format_breaking_change_error(self, breaking_changes: List[Dict[str, Any]]) -> str:
        """Format breaking change error message."""
        # Implementation: Apply template and format error message
        # Return: Formatted error message string
        
    def generate_resolution_steps(self, error_type: str, language: str, version: str) -> List[str]:
        """Generate resolution steps for compatibility errors."""
        # Implementation: Create step-by-step resolution guide
        # Return: List of resolution step strings
```

### IMPLEMENTATION REQUIREMENTS:
1. **Complete all methods** with full implementation
2. **Integrate with completed Tasks A1-A6** (version detectors)
3. **Integrate with completed Task B3** (compatibility database)
4. **Handle version comparison** and compatibility checking
5. **Implement comprehensive error detection** for all compatibility issues
6. **Add comprehensive error handling** for detection failures
7. **Include logging** for debugging and monitoring
8. **Create unit tests** covering all detection methods

### TESTING REQUIREMENTS:
- Test with various version formats
- Test compatibility checking accuracy
- Test error detection for different issue types
- Test integration with version detectors
- Test integration with compatibility database
- Achieve 90%+ code coverage

---

## TASK C3: SYNTAX ERROR ANALYZER

**ASSIGNED FILE**: `chunker/error_handling/syntax_analyzer.py`
**SUB-AGENT**: Syntax Error Analysis Specialist
**IMPLEMENTATION DEADLINE**: Complete within assigned timeframe
**DEPENDENCIES**: Task C1 (Error Classification) must be completed first

### FILE STRUCTURE TO CREATE:
```python
# chunker/error_handling/syntax_analyzer.py

from typing import Dict, List, Optional, Any, Tuple, Union
import re
import logging
from pathlib import Path
from datetime import datetime

# Import from completed Task C1
from .classifier import ClassifiedError, ErrorCategory, ErrorSeverity, ErrorSource, ErrorContext

logger = logging.getLogger(__name__)

class SyntaxErrorAnalyzer:
    """Analyzes syntax errors for patterns and causes."""
    
    def __init__(self):
        self.syntax_patterns = self._load_syntax_patterns()
        self.language_patterns = self._load_language_patterns()
        self.error_categories = self._load_error_categories()
        
    def _load_syntax_patterns(self) -> Dict[str, List[re.Pattern]]:
        """Load regex patterns for syntax error detection."""
        # Implementation: Define patterns for common syntax errors
        # Return: Dict mapping error type to list of patterns
        
    def _load_language_patterns(self) -> Dict[str, Dict[str, List[re.Pattern]]]:
        """Load language-specific syntax patterns."""
        # Implementation: Define patterns for each language
        # Return: Dict mapping language to error type patterns
        
    def _load_error_categories(self) -> Dict[str, ErrorCategory]:
        """Load mapping of syntax errors to categories."""
        # Implementation: Map syntax error types to ErrorCategory
        # Return: Dict mapping error type to category
        
    def analyze_syntax_error(self, error_message: str, language: Optional[str] = None,
                           file_path: Optional[Path] = None) -> ClassifiedError:
        """Analyze a syntax error and classify it."""
        # Implementation: Parse error message and classify syntax error
        # Return: ClassifiedError object for syntax error
        
    def detect_syntax_error_type(self, error_message: str, language: str) -> str:
        """Detect the specific type of syntax error."""
        # Implementation: Apply language-specific patterns
        # Return: String identifying error type
        
    def extract_syntax_error_location(self, error_message: str) -> Tuple[Optional[int], Optional[int]]:
        """Extract line and column numbers from syntax error."""
        # Implementation: Parse error message for location information
        # Return: Tuple of (line_number, column_number) or (None, None)
        
    def identify_syntax_problem(self, error_message: str, language: str) -> str:
        """Identify the specific syntax problem."""
        # Implementation: Analyze error to determine problem
        # Return: String describing the syntax problem
        
    def suggest_syntax_fix(self, error_type: str, language: str, context: str) -> List[str]:
        """Suggest fixes for syntax errors."""
        # Implementation: Generate fix suggestions based on error type
        # Return: List of fix suggestion strings
        
    def categorize_syntax_error(self, error_message: str, language: str) -> ErrorCategory:
        """Categorize syntax error into appropriate category."""
        # Implementation: Map syntax error to ErrorCategory
        # Return: ErrorCategory enum value
        
    def determine_syntax_error_severity(self, error_type: str, language: str) -> ErrorSeverity:
        """Determine severity level of syntax error."""
        # Implementation: Map error type to severity level
        # Return: ErrorSeverity enum value
        
    def analyze_multiple_syntax_errors(self, error_messages: List[str], language: str) -> List[ClassifiedError]:
        """Analyze multiple syntax errors in batch."""
        # Implementation: Process multiple errors efficiently
        # Return: List of ClassifiedError objects
        
    def get_syntax_error_statistics(self, error_messages: List[str], language: str) -> Dict[str, Any]:
        """Get statistics about syntax errors."""
        # Implementation: Analyze error patterns and frequencies
        # Return: Dict with error statistics
        
    def export_syntax_analysis(self, output_path: Path) -> None:
        """Export syntax error analysis to file."""
        # Implementation: Serialize analysis results to file
        # Return: None, writes to specified path

class LanguageSpecificSyntaxAnalyzer:
    """Language-specific syntax error analysis."""
    
    def __init__(self, language: str):
        self.language = language
        self.patterns = self._load_language_patterns()
        
    def _load_language_patterns(self) -> Dict[str, List[re.Pattern]]:
        """Load patterns specific to this language."""
        # Implementation: Load language-specific syntax patterns
        # Return: Dict mapping error type to patterns
        
    def analyze_python_syntax_error(self, error_message: str) -> Dict[str, Any]:
        """Analyze Python-specific syntax errors."""
        # Implementation: Parse Python syntax error messages
        # Return: Dict with analysis results
        
    def analyze_javascript_syntax_error(self, error_message: str) -> Dict[str, Any]:
        """Analyze JavaScript-specific syntax errors."""
        # Implementation: Parse JavaScript syntax error messages
        # Return: Dict with analysis results
        
    def analyze_rust_syntax_error(self, error_message: str) -> Dict[str, Any]:
        """Analyze Rust-specific syntax errors."""
        # Implementation: Parse Rust syntax error messages
        # Return: Dict with analysis results
        
    def analyze_generic_syntax_error(self, error_message: str) -> Dict[str, Any]:
        """Analyze generic syntax errors."""
        # Implementation: Parse generic syntax error messages
        # Return: Dict with analysis results
        
    def get_language_specific_fixes(self, error_type: str) -> List[str]:
        """Get language-specific fix suggestions."""
        # Implementation: Return fixes specific to this language
        # Return: List of fix suggestion strings

class SyntaxErrorPatternMatcher:
    """Advanced pattern matching for syntax errors."""
    
    def __init__(self):
        self.compiled_patterns = {}
        self.pattern_metadata = {}
        
    def add_syntax_pattern(self, name: str, pattern: str, language: str,
                          error_type: str, severity: ErrorSeverity) -> None:
        """Add a new syntax error pattern."""
        # Implementation: Compile and store pattern with metadata
        # Return: None, adds pattern to matcher
        
    def match_syntax_patterns(self, error_message: str, language: str) -> List[Dict[str, Any]]:
        """Match error message against language-specific patterns."""
        # Implementation: Apply language-specific patterns
        # Return: List of pattern match results
        
    def get_best_syntax_match(self, error_message: str, language: str) -> Optional[Dict[str, Any]]:
        """Get the best matching syntax pattern."""
        # Implementation: Score matches and return best one
        # Return: Best match dict or None
        
    def remove_syntax_pattern(self, name: str) -> bool:
        """Remove a syntax pattern by name."""
        # Implementation: Remove pattern from matcher
        # Return: True if removed, False if not found
        
    def list_syntax_patterns(self, language: str) -> List[str]:
        """List all syntax patterns for a language."""
        # Implementation: Return list of pattern names for language
        # Return: List of pattern name strings

class SyntaxErrorFormatter:
    """Formats syntax errors for user consumption."""
    
    def __init__(self):
        self.formatting_templates = self._load_formatting_templates()
        
    def _load_formatting_templates(self) -> Dict[str, str]:
        """Load formatting templates for syntax errors."""
        # Implementation: Define templates for different error types
        # Return: Dict mapping error type to template
        
    def format_syntax_error(self, error_type: str, language: str, 
                           line_number: Optional[int], column_number: Optional[int],
                           problem_description: str) -> str:
        """Format a syntax error message."""
        # Implementation: Apply template and format error message
        # Return: Formatted error message string
        
    def format_syntax_fix_suggestions(self, suggestions: List[str], language: str) -> str:
        """Format syntax fix suggestions."""
        # Implementation: Format suggestions for display
        # Return: Formatted suggestions string
        
    def generate_syntax_error_report(self, errors: List[ClassifiedError], language: str) -> str:
        """Generate comprehensive syntax error report."""
        # Implementation: Create detailed error report
        # Return: Formatted report string
```

### IMPLEMENTATION REQUIREMENTS:
1. **Complete all methods** with full implementation
2. **Integrate with completed Task C1** (Error Classification)
3. **Handle language-specific syntax patterns** for multiple languages
4. **Implement comprehensive pattern matching** for syntax errors
5. **Add comprehensive error handling** for analysis failures
6. **Include logging** for debugging and monitoring
7. **Create unit tests** covering all analysis methods
8. **Support multiple programming languages** with specific patterns

### TESTING REQUIREMENTS:
- Test with various syntax error formats
- Test language-specific pattern matching
- Test error location extraction
- Test fix suggestion generation
- Test integration with error classifier
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

### EXECUTION ORDER:

**IMPORTANT**: These tasks have mixed dependencies:

1. **Task C1 (Error Classification)**: Must be completed FIRST - no dependencies
2. **Task C2 (Compatibility Error Detector)**: Can start AFTER Group A and Group B are complete
3. **Task C3 (Syntax Error Analyzer)**: Can start AFTER C1 is complete

### SUB-AGENT PROMPT TEMPLATE:

```
You are assigned to implement [TASK_NAME] for Group C.

YOUR FILE: [FILE_PATH]
YOUR TASK: [TASK_DESCRIPTION]
DEPENDENCIES: [LIST OF DEPENDENCIES]

REQUIREMENTS:
- Implement ALL methods in the class structure provided
- Add comprehensive type hints and docstrings
- Handle edge cases and error conditions
- Include logging and error handling
- Create unit tests with 90%+ coverage
- ONLY touch the assigned file
- Ensure compatibility with [DEPENDENT_TASKS] if applicable

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

1. **EXECUTE C1 FIRST**: Start with C1 (Error Classification) - no dependencies
2. **WAIT FOR DEPENDENCIES**: Ensure Group A and Group B complete before starting C2
3. **EXECUTE C3 AFTER C1**: Start C3 once C1 is complete
4. **COLLECT RESULTS**: Gather completed implementations from each sub-agent
5. **VALIDATE COMPLETION**: Ensure all tasks are fully implemented
6. **REPORT SUMMARY**: Provide summary of all completed work

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
- ✅ Dependencies are properly integrated (for C2 and C3)

### FINAL REPORT FORMAT:

```
GROUP C COMPLETION REPORT
========================

TASK C1 (Error Classification): [STATUS] - [SUB-AGENT NAME]
- File: chunker/error_handling/classifier.py
- Methods implemented: [LIST]
- Test coverage: [PERCENTAGE]
- Issues/notes: [ANY]

TASK C2 (Compatibility Error Detector): [STATUS] - [SUB-AGENT NAME]
- File: chunker/error_handling/compatibility_detector.py
- Methods implemented: [LIST]
- Test coverage: [PERCENTAGE]
- Dependencies met: [GROUP A STATUS, GROUP B STATUS]
- Issues/notes: [ANY]

TASK C3 (Syntax Error Analyzer): [STATUS] - [SUB-AGENT NAME]
- File: chunker/error_handling/syntax_analyzer.py
- Methods implemented: [LIST]
- Test coverage: [PERCENTAGE]
- Dependencies met: [C1 STATUS]
- Issues/notes: [ANY]

OVERALL STATUS: [COMPLETE/INCOMPLETE]
DEPENDENCY CHAIN: [C1] -> [C2: A+B] -> [C3: C1] - [STATUS]
NEXT STEPS: [WHAT COMES AFTER GROUP C]
```

---

## IMPORTANT NOTES

### FILE BOUNDARIES:
- **EACH SUB-AGENT TOUCHES EXACTLY ONE FILE**
- **NO CROSS-FILE DEPENDENCIES** within individual tasks
- **ALL IMPORTS MUST BE STANDARD LIBRARY** or from completed tasks
- **NO NEW DEPENDENCIES** can be added

### DEPENDENCY MANAGEMENT:
- **C1 (Error Classification)**: No dependencies - can start immediately
- **C2 (Compatibility Error Detector)**: Depends on Group A (A1-A6) and Group B (B3)
- **C3 (Syntax Error Analyzer)**: Depends on C1 (Error Classification)

### IMPLEMENTATION STANDARDS:
- **FULL IMPLEMENTATION** - no stubs or placeholders
- **PRODUCTION-READY CODE** - not prototype quality
- **COMPREHENSIVE TESTING** - 90%+ coverage required
- **ERROR HANDLING** - graceful degradation for all edge cases
- **LOGGING** - meaningful debug and info messages

### COORDINATION:
- **MIXED EXECUTION** - C1 can start immediately, C2 and C3 wait for dependencies
- **DEPENDENCY VALIDATION** - ensure dependencies complete before starting dependent tasks
- **MANAGER OVERSIGHT** - you coordinate and ensure proper execution order
- **QUALITY GATES** - validate completion before proceeding to dependent tasks

---

## EXECUTION COMMAND

**COPY AND PASTE THIS ENTIRE PROMPT** into your sub-agent manager system to begin execution of Group C tasks.

**EXPECTED DURATION**: 3-4 days with dependency-aware execution
**EXPECTED OUTCOME**: Complete error analysis and classification system
**NEXT PHASE**: Group D (User Guidance) after Group C completion

**START EXECUTION NOW** with Task C1 (Error Classification), then proceed based on dependencies.

# GROUP B SUB-AGENT MANAGER PROMPT
# Phase 1.7: Smart Error Handling & User Guidance
# Version Compatibility Database

## AGENT IDENTIFICATION & ROLES

**WHO I AM**: I am the primary AI agent working on Phase 1.7 implementation planning and coordination. I will NOT touch any of the files assigned to sub-agents in this prompt.

**WHO YOU ARE**: You are the sub-agent manager responsible for coordinating execution of Group B tasks. These tasks have sequential dependencies and must be executed in order.

**WHO THE SUB-AGENTS ARE**: Individual AI agents that will implement specific compatibility database components. Each sub-agent works on exactly ONE file and ONE task.

## EXECUTION STRATEGY

**SEQUENTIAL EXECUTION**: Group B tasks must be executed in order due to dependencies.
**FILE ISOLATION**: Each sub-agent touches ONLY their assigned file - no cross-file dependencies.
**COORDINATION**: You will manage the sequential execution and ensure dependencies are met.

## GROUP B TASKS OVERVIEW

**OBJECTIVE**: Implement version compatibility database system for mapping language versions to grammar versions.
**DEPENDENCIES**: Tasks B2 and B3 depend on previous tasks being completed.
**OUTPUT**: Complete compatibility database system with schema, analyzer, and builder.

---

## TASK B1: COMPATIBILITY DATABASE SCHEMA

**ASSIGNED FILE**: `chunker/languages/compatibility/schema.py`
**SUB-AGENT**: Database Schema Specialist
**IMPLEMENTATION DEADLINE**: Complete within assigned timeframe
**DEPENDENCIES**: None - can start immediately

### FILE STRUCTURE TO CREATE:
```python
# chunker/languages/version_detection/compatibility/schema.py

from typing import Dict, List, Optional, Union, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

class CompatibilityLevel(Enum):
    """Compatibility levels for language-grammar pairs."""
    FULLY_COMPATIBLE = "fully_compatible"
    MOSTLY_COMPATIBLE = "mostly_compatible"
    PARTIALLY_COMPATIBLE = "partially_compatible"
    INCOMPATIBLE = "incompatible"
    UNKNOWN = "unknown"

class VersionConstraint(Enum):
    """Types of version constraints."""
    EXACT = "exact"
    MINIMUM = "minimum"
    MAXIMUM = "maximum"
    RANGE = "range"
    WILDCARD = "wildcard"

@dataclass
class LanguageVersion:
    """Represents a specific language version."""
    language: str
    version: str
    edition: Optional[str] = None  # For languages like Rust
    build: Optional[str] = None    # For languages like Go
    features: List[str] = field(default_factory=list)
    release_date: Optional[datetime] = None
    end_of_life: Optional[datetime] = None
    
    def __post_init__(self):
        """Validate language version data."""
        if not self.language or not self.version:
            raise ValueError("Language and version are required")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        
    def __str__(self) -> str:
        """String representation of language version."""
        
    def is_compatible_with(self, other: 'LanguageVersion') -> bool:
        """Check if this version is compatible with another."""
        
    def get_major_minor(self) -> tuple:
        """Extract major.minor version numbers."""

@dataclass
class GrammarVersion:
    """Represents a specific grammar version."""
    language: str
    version: str
    grammar_file: str
    supported_features: List[str] = field(default_factory=list)
    min_language_version: Optional[str] = None
    max_language_version: Optional[str] = None
    breaking_changes: List[str] = field(default_factory=list)
    release_date: Optional[datetime] = None
    
    def __post_init__(self):
        """Validate grammar version data."""
        if not self.language or not self.version or not self.grammar_file:
            raise ValueError("Language, version, and grammar_file are required")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        
    def __str__(self) -> str:
        """String representation of grammar version."""
        
    def supports_language_version(self, lang_version: LanguageVersion) -> bool:
        """Check if this grammar supports the given language version."""
        
    def get_compatibility_level(self, lang_version: LanguageVersion) -> CompatibilityLevel:
        """Determine compatibility level with a language version."""

@dataclass
class CompatibilityRule:
    """Defines compatibility rules between language and grammar versions."""
    language: str
    language_version_constraint: str
    grammar_version_constraint: str
    compatibility_level: CompatibilityLevel
    notes: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    
    def __post_init__(self):
        """Validate compatibility rule data."""
        if not self.language or not self.language_version_constraint:
            raise ValueError("Language and version constraint are required")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        
    def __str__(self) -> str:
        """String representation of compatibility rule."""
        
    def matches_language_version(self, lang_version: LanguageVersion) -> bool:
        """Check if this rule matches a language version."""
        
    def matches_grammar_version(self, grammar_version: GrammarVersion) -> bool:
        """Check if this rule matches a grammar version."""

@dataclass
class BreakingChange:
    """Represents a breaking change between versions."""
    language: str
    from_version: str
    to_version: str
    change_type: str  # "syntax", "api", "feature", "deprecation"
    description: str
    impact_level: str  # "low", "medium", "high", "critical"
    migration_guide: Optional[str] = None
    affected_features: List[str] = field(default_factory=list)
    detected_at: datetime = field(default_factory=datetime.now)
    
    def __post_init__(self):
        """Validate breaking change data."""
        if not all([self.language, self.from_version, self.to_version, 
                   self.change_type, self.description, self.impact_level]):
            raise ValueError("All required fields must be provided")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        
    def __str__(self) -> str:
        """String representation of breaking change."""
        
    def affects_feature(self, feature: str) -> bool:
        """Check if this breaking change affects a specific feature."""

class CompatibilitySchema:
    """Main schema class for managing compatibility data."""
    
    def __init__(self):
        self.language_versions: Dict[str, List[LanguageVersion]] = {}
        self.grammar_versions: Dict[str, List[GrammarVersion]] = {}
        self.compatibility_rules: List[CompatibilityRule] = []
        self.breaking_changes: List[BreakingChange] = []
    
    def add_language_version(self, lang_version: LanguageVersion) -> None:
        """Add a language version to the schema."""
        
    def add_grammar_version(self, grammar_version: GrammarVersion) -> None:
        """Add a grammar version to the schema."""
        
    def add_compatibility_rule(self, rule: CompatibilityRule) -> None:
        """Add a compatibility rule to the schema."""
        
    def add_breaking_change(self, breaking_change: BreakingChange) -> None:
        """Add a breaking change to the schema."""
        
    def get_language_versions(self, language: str) -> List[LanguageVersion]:
        """Get all versions for a specific language."""
        
    def get_grammar_versions(self, language: str) -> List[GrammarVersion]:
        """Get all grammar versions for a specific language."""
        
    def find_compatible_grammar(self, lang_version: LanguageVersion) -> Optional[GrammarVersion]:
        """Find a compatible grammar for a language version."""
        
    def get_compatibility_level(self, lang_version: LanguageVersion, 
                              grammar_version: GrammarVersion) -> CompatibilityLevel:
        """Get compatibility level between language and grammar versions."""
        
    def get_breaking_changes(self, language: str, from_version: str, 
                           to_version: str) -> List[BreakingChange]:
        """Get breaking changes between two versions."""
        
    def validate_schema(self) -> List[str]:
        """Validate the entire schema and return any errors."""
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert entire schema to dictionary representation."""
        
    def from_dict(self, data: Dict[str, Any]) -> None:
        """Load schema from dictionary representation."""
```

### IMPLEMENTATION REQUIREMENTS:
1. **Complete all classes and methods** with full implementation
2. **Add comprehensive type hints** for all functions
3. **Include detailed docstrings** explaining each method's purpose
4. **Handle edge cases** like invalid data, missing fields
5. **Implement data validation** in `__post_init__` methods
6. **Add error handling** with graceful fallbacks
7. **Include logging** for debugging and monitoring
8. **Create unit tests** covering all classes and methods

### TESTING REQUIREMENTS:
- Test all dataclass validations
- Test compatibility level calculations
- Test breaking change detection
- Test schema validation and error handling
- Test data serialization/deserialization
- Achieve 90%+ code coverage

---

## TASK B2: GRAMMAR VERSION ANALYZER

**ASSIGNED FILE**: `chunker/languages/compatibility/grammar_analyzer.py`
**SUB-AGENT**: Grammar Analysis Specialist
**IMPLEMENTATION DEADLINE**: Complete within assigned timeframe
**DEPENDENCIES**: Task B1 (Schema) must be completed first

### FILE STRUCTURE TO CREATE:
```python
# chunker/languages/version_detection/compatibility/grammar_analyzer.py

import os
import re
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import logging
from .schema import GrammarVersion, LanguageVersion, CompatibilityLevel

logger = logging.getLogger(__name__)

class GrammarAnalyzer:
    """Analyzes compiled grammar files to extract version and capability information."""
    
    def __init__(self, grammars_dir: Path):
        self.grammars_dir = grammars_dir
        self.grammar_cache: Dict[str, GrammarVersion] = {}
        self.supported_languages = self._discover_supported_languages()
    
    def _discover_supported_languages(self) -> List[str]:
        """Discover all supported languages from grammar directory."""
        # Implementation: Scan grammars_dir for .so files
        # Return: List of language names (e.g., ['python', 'javascript', 'rust'])
        
    def analyze_grammar_file(self, language: str) -> Optional[GrammarVersion]:
        """Analyze a specific grammar file to extract version information."""
        # Implementation: Analyze .so file for language
        # Return: GrammarVersion object or None if analysis fails
        
    def extract_grammar_version(self, so_file_path: Path) -> Optional[str]:
        """Extract version information from a compiled grammar .so file."""
        # Implementation: Use nm, objdump, or similar tools
        # Return: Version string or None if not found
        
    def analyze_grammar_symbols(self, so_file_path: Path) -> Dict[str, Any]:
        """Analyze symbols in grammar file to understand capabilities."""
        # Implementation: Parse symbol table for function names, constants
        # Return: Dict with symbol information
        
    def detect_supported_features(self, language: str, symbols: Dict[str, Any]) -> List[str]:
        """Detect supported language features based on grammar symbols."""
        # Implementation: Map symbols to language features
        # Return: List of supported feature names
        
    def determine_language_version_support(self, language: str, 
                                         grammar_version: str) -> Tuple[str, str]:
        """Determine min/max language versions supported by grammar."""
        # Implementation: Use known compatibility data or heuristics
        # Return: Tuple of (min_version, max_version)
        
    def analyze_all_grammars(self) -> Dict[str, GrammarVersion]:
        """Analyze all available grammar files."""
        # Implementation: Process all .so files in grammars directory
        # Return: Dict mapping language to GrammarVersion
        
    def get_grammar_capabilities(self, language: str) -> Dict[str, Any]:
        """Get comprehensive capabilities for a specific grammar."""
        # Implementation: Combine all analysis results
        # Return: Dict with grammar capabilities
        
    def validate_grammar_compatibility(self, language: str, 
                                    target_version: str) -> CompatibilityLevel:
        """Validate if grammar is compatible with target language version."""
        # Implementation: Check version constraints and features
        # Return: CompatibilityLevel enum value
        
    def generate_grammar_report(self, language: str) -> str:
        """Generate human-readable report for grammar analysis."""
        # Implementation: Format analysis results as readable text
        # Return: Formatted report string
        
    def export_analysis_data(self, output_path: Path) -> None:
        """Export analysis data to JSON or other format."""
        # Implementation: Serialize analysis results to file
        # Return: None, writes to specified path

class GrammarMetadataExtractor:
    """Extracts metadata from grammar files using various methods."""
    
    @staticmethod
    def extract_from_symbols(so_file_path: Path) -> Dict[str, Any]:
        """Extract metadata using symbol table analysis."""
        # Implementation: Use nm command to analyze symbols
        # Return: Dict with symbol metadata
        
    @staticmethod
    def extract_from_strings(so_file_path: Path) -> Dict[str, Any]:
        """Extract metadata using string analysis."""
        # Implementation: Use strings command to find version strings
        # Return: Dict with string metadata
        
    @staticmethod
    def extract_from_headers(so_file_path: Path) -> Dict[str, Any]:
        """Extract metadata from file headers."""
        # Implementation: Use file command and other header analysis
        # Return: Dict with header metadata
        
    @staticmethod
    def extract_from_dependencies(so_file_path: Path) -> Dict[str, Any]:
        """Extract metadata from library dependencies."""
        # Implementation: Use ldd or similar to analyze dependencies
        # Return: Dict with dependency metadata

class FeatureDetector:
    """Detects language features based on grammar analysis."""
    
    def __init__(self):
        self.feature_patterns = self._load_feature_patterns()
    
    def _load_feature_patterns(self) -> Dict[str, List[str]]:
        """Load patterns for detecting language features."""
        # Implementation: Define regex patterns for feature detection
        # Return: Dict mapping language to feature patterns
        
    def detect_features(self, language: str, symbols: Dict[str, Any]) -> List[str]:
        """Detect features for a specific language."""
        # Implementation: Apply feature patterns to symbols
        # Return: List of detected features
        
    def get_feature_compatibility(self, language: str, 
                                features: List[str]) -> Dict[str, str]:
        """Get version requirements for specific features."""
        # Implementation: Map features to minimum version requirements
        # Return: Dict mapping features to version requirements
```

### IMPLEMENTATION REQUIREMENTS:
1. **Complete all methods** with full implementation
2. **Integrate with Task B1 schema** classes
3. **Handle system commands** (nm, objdump, strings, ldd) safely
4. **Implement comprehensive error handling** for file analysis failures
5. **Add logging** for debugging and monitoring
6. **Create unit tests** covering all analysis methods
7. **Handle cross-platform compatibility** (Linux, macOS, Windows)

### TESTING REQUIREMENTS:
- Test with various grammar file formats
- Test error handling for corrupted files
- Test cross-platform compatibility
- Test feature detection accuracy
- Test metadata extraction methods
- Achieve 90%+ code coverage

---

## TASK B3: COMPATIBILITY DATABASE BUILDER

**ASSIGNED FILE**: `chunker/languages/compatibility/database.py`
**SUB-AGENT**: Database Builder Specialist
**IMPLEMENTATION DEADLINE**: Complete within assigned timeframe
**DEPENDENCIES**: Tasks B1 (Schema) and B2 (Grammar Analyzer) must be completed first

### FILE STRUCTURE TO CREATE:
```python
# chunker/languages/version_detection/compatibility/database.py

import json
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import logging
from datetime import datetime
from .schema import (CompatibilitySchema, LanguageVersion, GrammarVersion, 
                    CompatibilityRule, BreakingChange, CompatibilityLevel)
from .grammar_analyzer import GrammarAnalyzer

logger = logging.getLogger(__name__)

class CompatibilityDatabase:
    """Main database class for managing compatibility information."""
    
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or Path("compatibility.db")
        self.schema = CompatibilitySchema()
        self.grammar_analyzer = None
        self._init_database()
    
    def _init_database(self) -> None:
        """Initialize the database and create tables."""
        # Implementation: Create SQLite tables for all schema classes
        # Return: None, creates database structure
        
    def _create_tables(self) -> None:
        """Create all necessary database tables."""
        # Implementation: SQL CREATE TABLE statements
        # Return: None, creates tables
        
    def add_language_version(self, lang_version: LanguageVersion) -> bool:
        """Add a language version to the database."""
        # Implementation: Insert into language_versions table
        # Return: True if successful, False otherwise
        
    def add_grammar_version(self, grammar_version: GrammarVersion) -> bool:
        """Add a grammar version to the database."""
        # Implementation: Insert into grammar_versions table
        # Return: True if successful, False otherwise
        
    def add_compatibility_rule(self, rule: CompatibilityRule) -> bool:
        """Add a compatibility rule to the database."""
        # Implementation: Insert into compatibility_rules table
        # Return: True if successful, False otherwise
        
    def add_breaking_change(self, breaking_change: BreakingChange) -> bool:
        """Add a breaking change to the database."""
        # Implementation: Insert into breaking_changes table
        # Return: True if successful, False otherwise
        
    def get_language_versions(self, language: str) -> List[LanguageVersion]:
        """Get all versions for a specific language."""
        # Implementation: Query language_versions table
        # Return: List of LanguageVersion objects
        
    def get_grammar_versions(self, language: str) -> List[GrammarVersion]:
        """Get all grammar versions for a specific language."""
        # Implementation: Query grammar_versions table
        # Return: List of GrammarVersion objects
        
    def find_compatible_grammar(self, lang_version: LanguageVersion) -> Optional[GrammarVersion]:
        """Find a compatible grammar for a language version."""
        # Implementation: Query compatibility rules and grammar versions
        # Return: Compatible GrammarVersion or None
        
    def get_compatibility_level(self, lang_version: LanguageVersion, 
                              grammar_version: GrammarVersion) -> CompatibilityLevel:
        """Get compatibility level between language and grammar versions."""
        # Implementation: Query compatibility rules and calculate level
        # Return: CompatibilityLevel enum value
        
    def get_breaking_changes(self, language: str, from_version: str, 
                           to_version: str) -> List[BreakingChange]:
        """Get breaking changes between two versions."""
        # Implementation: Query breaking_changes table
        # Return: List of BreakingChange objects
        
    def update_compatibility_data(self) -> None:
        """Update compatibility data from grammar analysis."""
        # Implementation: Use GrammarAnalyzer to refresh data
        # Return: None, updates database
        
    def export_database(self, output_path: Path) -> None:
        """Export database to JSON or other format."""
        # Implementation: Serialize all data to file
        # Return: None, writes to specified path
        
    def import_database(self, input_path: Path) -> None:
        """Import database from JSON or other format."""
        # Implementation: Deserialize data and populate database
        # Return: None, populates database
        
    def validate_database(self) -> List[str]:
        """Validate database integrity and return any errors."""
        # Implementation: Check referential integrity and data consistency
        # Return: List of validation errors
        
    def optimize_database(self) -> None:
        """Optimize database performance."""
        # Implementation: Create indexes, analyze tables, vacuum
        # Return: None, optimizes database
        
    def backup_database(self, backup_path: Path) -> None:
        """Create a backup of the database."""
        # Implementation: Copy database file to backup location
        # Return: None, creates backup
        
    def restore_database(self, backup_path: Path) -> None:
        """Restore database from backup."""
        # Implementation: Restore from backup file
        # Return: None, restores database

class DatabaseManager:
    """High-level database management operations."""
    
    def __init__(self, db_path: Path):
        self.database = CompatibilityDatabase(db_path)
        self.grammar_analyzer = GrammarAnalyzer(Path("chunker/data/grammars/build"))
    
    def populate_from_grammars(self) -> None:
        """Populate database with data from grammar analysis."""
        # Implementation: Analyze all grammars and populate database
        # Return: None, populates database
        
    def add_known_compatibility_data(self) -> None:
        """Add known compatibility data for common language versions."""
        # Implementation: Add hardcoded compatibility information
        # Return: None, adds known data
        
    def update_breaking_changes(self) -> None:
        """Update breaking changes information."""
        # Implementation: Add known breaking changes between versions
        # Return: None, updates breaking changes
        
    def generate_compatibility_report(self, language: str) -> str:
        """Generate comprehensive compatibility report for a language."""
        # Implementation: Create detailed compatibility analysis
        # Return: Formatted report string
        
    def get_language_support_matrix(self) -> Dict[str, Dict[str, Any]]:
        """Get support matrix for all languages."""
        # Implementation: Generate support matrix from database
        # Return: Dict with language support information
```

### IMPLEMENTATION REQUIREMENTS:
1. **Complete all methods** with full implementation
2. **Integrate with Tasks B1 and B2** classes and functionality
3. **Implement SQLite database** with proper table structure
4. **Handle database operations** safely with transactions
5. **Add comprehensive error handling** for database failures
6. **Include logging** for debugging and monitoring
7. **Create unit tests** covering all database operations
8. **Implement data validation** and integrity checks

### TESTING REQUIREMENTS:
- Test all database CRUD operations
- Test data integrity and validation
- Test error handling for database failures
- Test import/export functionality
- Test performance with large datasets
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

**IMPORTANT**: These tasks must be executed sequentially due to dependencies:

1. **Task B1 (Schema)**: Must be completed FIRST - no dependencies
2. **Task B2 (Grammar Analyzer)**: Can start AFTER B1 is complete
3. **Task B3 (Database Builder)**: Can start AFTER both B1 and B2 are complete

### SUB-AGENT PROMPT TEMPLATE:

```
You are assigned to implement [TASK_NAME] for Group B.

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

1. **EXECUTE SEQUENTIALLY**: Start with B1, then B2, then B3
2. **VALIDATE DEPENDENCIES**: Ensure each task completes before starting the next
3. **COLLECT RESULTS**: Gather completed implementations from each sub-agent
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
- ✅ Dependencies are properly integrated (for B2 and B3)

### FINAL REPORT FORMAT:

```
GROUP B COMPLETION REPORT
========================

TASK B1 (Schema): [STATUS] - [SUB-AGENT NAME]
- File: chunker/languages/compatibility/schema.py
- Methods implemented: [LIST]
- Test coverage: [PERCENTAGE]
- Issues/notes: [ANY]

TASK B2 (Grammar Analyzer): [STATUS] - [SUB-AGENT NAME]
- File: chunker/languages/compatibility/grammar_analyzer.py
- Methods implemented: [LIST]
- Test coverage: [PERCENTAGE]
- Dependencies met: [B1 STATUS]
- Issues/notes: [ANY]

TASK B3 (Database Builder): [STATUS] - [SUB-AGENT NAME]
- File: chunker/languages/compatibility/database.py
- Methods implemented: [LIST]
- Test coverage: [PERCENTAGE]
- Dependencies met: [B1 STATUS, B2 STATUS]
- Issues/notes: [ANY]

OVERALL STATUS: [COMPLETE/INCOMPLETE]
DEPENDENCY CHAIN: [B1 -> B2 -> B3] - [STATUS]
NEXT STEPS: [WHAT COMES AFTER GROUP B]
```

---

## IMPORTANT NOTES

### FILE BOUNDARIES:
- **EACH SUB-AGENT TOUCHES EXACTLY ONE FILE**
- **NO CROSS-FILE DEPENDENCIES** within individual tasks
- **ALL IMPORTS MUST BE STANDARD LIBRARY** or from completed tasks
- **NO NEW DEPENDENCIES** can be added

### DEPENDENCY MANAGEMENT:
- **B1 (Schema)**: No dependencies - can start immediately
- **B2 (Grammar Analyzer)**: Depends on B1 schema classes
- **B3 (Database Builder)**: Depends on B1 schema and B2 analyzer

### IMPLEMENTATION STANDARDS:
- **FULL IMPLEMENTATION** - no stubs or placeholders
- **PRODUCTION-READY CODE** - not prototype quality
- **COMPREHENSIVE TESTING** - 90%+ coverage required
- **ERROR HANDLING** - graceful degradation for all edge cases
- **LOGGING** - meaningful debug and info messages

### COORDINATION:
- **SEQUENTIAL EXECUTION** - tasks must be completed in order
- **DEPENDENCY VALIDATION** - ensure each task completes before starting next
- **MANAGER OVERSIGHT** - you coordinate and ensure proper sequence
- **QUALITY GATES** - validate completion before proceeding to next task

---

## EXECUTION COMMAND

**COPY AND PASTE THIS ENTIRE PROMPT** into your sub-agent manager system to begin sequential execution of Group B tasks.

**EXPECTED DURATION**: 3-4 days with sequential execution
**EXPECTED OUTCOME**: Complete compatibility database system
**NEXT PHASE**: Group C (Error Analysis) after Group B completion

**START EXECUTION NOW** with Task B1 (Schema), then proceed sequentially through B2 and B3.

# GROUP D SUB-AGENT MANAGER PROMPT
# Phase 1.7: Smart Error Handling & User Guidance
# User Guidance System - ENHANCED VERSION

## AGENT IDENTIFICATION & ROLES

**WHO I AM**: I am the primary AI agent working on Phase 1.7 implementation planning and coordination. I will NOT touch any of the files assigned to sub-agents in this prompt.

**WHO YOU ARE**: You are the sub-agent manager responsible for coordinating execution of Group D tasks. These tasks have mixed dependencies - some independent, some dependent.

**WHO THE SUB-AGENTS ARE**: Individual AI agents that will implement specific user guidance components. Each sub-agent works on exactly ONE file and ONE task.

## EXECUTION STRATEGY

**MIXED EXECUTION**: Some tasks can run in parallel, others have dependencies.
**FILE ISOLATION**: Each sub-agent touches ONLY their assigned file - no cross-file dependencies.
**COORDINATION**: You will manage the execution order and ensure dependencies are met.

## GROUP D TASKS OVERVIEW

**OBJECTIVE**: Implement user guidance system that provides actionable steps for resolving errors.
**DEPENDENCIES**: Mixed - D1 and D3 are independent, D2 depends on Group C.
**OUTPUT**: Complete user guidance system with error message templates, guidance engine, and troubleshooting database.

**ENHANCEMENTS**: This prompt has been enhanced with better integration planning, performance considerations, and comprehensive testing requirements.

---

## TASK D1: ERROR MESSAGE TEMPLATES

**ASSIGNED FILE**: `chunker/error_handling/templates.py`
**SUB-AGENT**: Error Message Template Specialist
**IMPLEMENTATION DEADLINE**: Complete within assigned timeframe
**DEPENDENCIES**: None - can start immediately

### FILE STRUCTURE TO CREATE:
```python
# chunker/error_handling/templates.py

from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field
from datetime import datetime
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class TemplateType(Enum):
    """Types of error message templates."""
    COMPATIBILITY = "compatibility"
    SYNTAX = "syntax"
    GRAMMAR = "grammar"
    SYSTEM = "system"
    CONFIGURATION = "configuration"
    NETWORK = "network"
    PERMISSION = "permission"
    UNKNOWN = "unknown"

class TemplateFormat(Enum):
    """Template output formats."""
    TEXT = "text"
    HTML = "html"
    MARKDOWN = "markdown"
    JSON = "json"
    XML = "xml"

@dataclass
class ErrorTemplate:
    """Template for generating error messages."""
    template_id: str
    template_type: TemplateType
    language: str
    error_category: str
    severity: str
    template_text: str
    variables: List[str] = field(default_factory=list)
    format_type: TemplateFormat = TemplateFormat.TEXT
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def __post_init__(self):
        """Validate template data."""
        if not self.template_id or not self.template_text:
            raise ValueError("Template ID and text are required")
        if not isinstance(self.template_type, TemplateType):
            raise ValueError("Template type must be TemplateType enum")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        
    def __str__(self) -> str:
        """String representation of error template."""
        
    def get_variables(self) -> List[str]:
        """Get list of variables used in template."""
        
    def validate_variables(self, provided_vars: Dict[str, Any]) -> List[str]:
        """Validate that all required variables are provided."""
        
    def render(self, variables: Dict[str, Any]) -> str:
        """Render template with provided variables."""
        
    def update_template(self, new_text: str) -> None:
        """Update template text."""
        
    def add_variable(self, variable: str) -> None:
        """Add a new variable to the template."""

class TemplateManager:
    """Manages error message templates."""
    
    def __init__(self, templates_dir: Optional[Path] = None):
        self.templates_dir = templates_dir or Path("chunker/data/templates")
        self.templates: Dict[str, ErrorTemplate] = {}
        self.template_cache: Dict[str, str] = {}
        self._load_templates()
        
    def _load_templates(self) -> None:
        """Load all templates from templates directory."""
        # Implementation: Load templates from files or database
        # Return: None, populates templates dict
        
    def add_template(self, template: ErrorTemplate) -> bool:
        """Add a new template."""
        # Implementation: Add template to manager
        # Return: True if successful, False otherwise
        
    def get_template(self, template_id: str) -> Optional[ErrorTemplate]:
        """Get template by ID."""
        # Implementation: Retrieve template from manager
        # Return: ErrorTemplate object or None
        
    def find_templates(self, template_type: Optional[TemplateType] = None,
                      language: Optional[str] = None,
                      error_category: Optional[str] = None) -> List[ErrorTemplate]:
        """Find templates matching criteria."""
        # Implementation: Filter templates by criteria
        # Return: List of matching templates
        
    def render_template(self, template_id: str, variables: Dict[str, Any]) -> Optional[str]:
        """Render a template with variables."""
        # Implementation: Get template and render with variables
        # Return: Rendered template string or None
        
    def update_template(self, template_id: str, new_text: str) -> bool:
        """Update an existing template."""
        # Implementation: Update template text
        # Return: True if successful, False otherwise
        
    def remove_template(self, template_id: str) -> bool:
        """Remove a template."""
        # Implementation: Remove template from manager
        # Return: True if successful, False otherwise
        
    def export_templates(self, output_path: Path, format_type: str = "json") -> None:
        """Export all templates to file."""
        # Implementation: Serialize templates to file
        # Return: None, writes to specified path
        
    def import_templates(self, input_path: Path) -> None:
        """Import templates from file."""
        # Implementation: Load templates from file
        # Return: None, loads templates into manager
        
    def validate_all_templates(self) -> List[str]:
        """Validate all templates and return any errors."""
        # Implementation: Check all templates for validity
        # Return: List of validation error messages
        
    def get_template_statistics(self) -> Dict[str, Any]:
        """Get statistics about templates."""
        # Implementation: Calculate template statistics
        # Return: Dict with template statistics

class TemplateRenderer:
    """Renders templates with variable substitution."""
    
    def __init__(self):
        self.renderers = self._initialize_renderers()
        
    def _initialize_renderers(self) -> Dict[TemplateFormat, Any]:
        """Initialize renderers for different formats."""
        # Implementation: Create renderer instances for each format
        # Return: Dict mapping format to renderer
        
    def render_template(self, template: ErrorTemplate, variables: Dict[str, Any],
                       output_format: TemplateFormat = TemplateFormat.TEXT) -> str:
        """Render template with variables in specified format."""
        # Implementation: Apply variables and format output
        # Return: Rendered template string
        
    def render_text_template(self, template: ErrorTemplate, variables: Dict[str, Any]) -> str:
        """Render template as plain text."""
        # Implementation: Simple text substitution
        # Return: Rendered text string
        
    def render_html_template(self, template: ErrorTemplate, variables: Dict[str, Any]) -> str:
        """Render template as HTML."""
        # Implementation: HTML-safe variable substitution
        # Return: Rendered HTML string
        
    def render_markdown_template(self, template: ErrorTemplate, variables: Dict[str, Any]) -> str:
        """Render template as Markdown."""
        # Implementation: Markdown-safe variable substitution
        # Return: Rendered Markdown string
        
    def render_json_template(self, template: ErrorTemplate, variables: Dict[str, Any]) -> str:
        """Render template as JSON."""
        # Implementation: JSON-safe variable substitution
        # Return: Rendered JSON string
        
    def validate_variables(self, template: ErrorTemplate, variables: Dict[str, Any]) -> List[str]:
        """Validate variables against template requirements."""
        # Implementation: Check required vs provided variables
        # Return: List of missing or invalid variables
        
    def escape_variables(self, variables: Dict[str, Any], format_type: TemplateFormat) -> Dict[str, Any]:
        """Escape variables for safe rendering."""
        # Implementation: Apply format-specific escaping
        # Return: Dict with escaped variables

class TemplateValidator:
    """Validates template syntax and structure."""
    
    def __init__(self):
        self.validation_rules = self._load_validation_rules()
        
    def _load_validation_rules(self) -> Dict[str, Any]:
        """Load validation rules for templates."""
        # Implementation: Define validation rules and patterns
        # Return: Dict with validation rules
        
    def validate_template(self, template: ErrorTemplate) -> List[str]:
        """Validate a single template."""
        # Implementation: Apply validation rules to template
        # Return: List of validation error messages
        
    def validate_template_syntax(self, template_text: str) -> List[str]:
        """Validate template syntax."""
        # Implementation: Check template syntax for errors
        # Return: List of syntax error messages
        
    def validate_template_variables(self, template: ErrorTemplate) -> List[str]:
        """Validate template variable definitions."""
        # Implementation: Check variable definitions for consistency
        # Return: List of variable validation errors
        
    def validate_template_format(self, template: ErrorTemplate) -> List[str]:
        """Validate template format compatibility."""
        # Implementation: Check format-specific requirements
        # Return: List of format validation errors
        
    def suggest_template_improvements(self, template: ErrorTemplate) -> List[str]:
        """Suggest improvements for template."""
        # Implementation: Analyze template and suggest improvements
        # Return: List of improvement suggestions

class TemplateLibrary:
    """Pre-built template library for common error types."""
    
    def __init__(self):
        self.builtin_templates = self._load_builtin_templates()
        
    def _load_builtin_templates(self) -> Dict[str, ErrorTemplate]:
        """Load built-in templates for common errors."""
        # Implementation: Create templates for common error scenarios
        # Return: Dict mapping template ID to ErrorTemplate
        
    def get_compatibility_templates(self) -> List[ErrorTemplate]:
        """Get all compatibility error templates."""
        # Implementation: Return compatibility error templates
        # Return: List of compatibility templates
        
    def get_syntax_templates(self) -> List[ErrorTemplate]:
        """Get all syntax error templates."""
        # Implementation: Return syntax error templates
        # Return: List of syntax templates
        
    def get_grammar_templates(self) -> List[ErrorTemplate]:
        """Get all grammar error templates."""
        # Implementation: Return grammar error templates
        # Return: List of grammar templates
        
    def get_system_templates(self) -> List[ErrorTemplate]:
        """Get all system error templates."""
        # Implementation: Return system error templates
        # Return: List of system templates
        
    def get_template_for_error(self, error_type: str, language: str) -> Optional[ErrorTemplate]:
        """Get appropriate template for error type and language."""
        # Implementation: Find best template for error
        # Return: Appropriate ErrorTemplate or None
        
    def add_custom_template(self, template: ErrorTemplate) -> bool:
        """Add a custom template to the library."""
        # Implementation: Add custom template
        # Return: True if successful, False otherwise
```

### IMPLEMENTATION REQUIREMENTS:
1. **Complete all classes and methods** with full implementation
2. **Add comprehensive type hints** for all functions
3. **Include detailed docstrings** explaining each method's purpose
4. **Handle template rendering** with variable substitution
5. **Implement multiple output formats** (text, HTML, Markdown, JSON)
6. **Add comprehensive error handling** for template failures
7. **Include logging** for debugging and monitoring
8. **Create unit tests** covering all template methods

### ENHANCED REQUIREMENTS:
9. **Performance optimization** - Implement caching for frequently used templates
10. **Memory management** - Handle large template libraries efficiently
11. **Error recovery** - Graceful fallback when template rendering fails
12. **Template validation** - Comprehensive validation of template syntax and variables
13. **Internationalization support** - Prepare for future multi-language support
14. **Template versioning** - Support for template updates and backward compatibility

### TESTING REQUIREMENTS:
- Test template rendering with various variables
- Test multiple output formats
- Test template validation
- Test variable substitution
- Test built-in template library
- Achieve 90%+ code coverage

### ENHANCED TESTING:
- **Performance testing** - Measure template rendering speed and memory usage
- **Stress testing** - Test with large numbers of templates and variables
- **Error handling testing** - Test all failure scenarios and recovery mechanisms
- **Integration testing** - Test with Group C components when available
- **Edge case testing** - Test with malformed templates and invalid variables
- **Memory leak testing** - Ensure no memory leaks during template operations

---

## TASK D2: USER ACTION GUIDANCE ENGINE

**ASSIGNED FILE**: `chunker/error_handling/guidance_engine.py`
**SUB-AGENT**: User Guidance Engine Specialist
**IMPLEMENTATION DEADLINE**: Complete within assigned timeframe
**DEPENDENCIES**: Tasks C1, C2, C3 (Error Analysis & Classification) must be completed first

### FILE STRUCTURE TO CREATE:
```python
# chunker/error_handling/guidance_engine.py

from typing import Dict, List, Optional, Any, Tuple, Union
from pathlib import Path
import logging
from datetime import datetime

# Import from completed Group C tasks
from .classifier import ClassifiedError, ErrorCategory, ErrorSeverity, ErrorSource
from .compatibility_detector import CompatibilityErrorDetector
from .syntax_analyzer import SyntaxErrorAnalyzer
from .templates import TemplateManager, ErrorTemplate, TemplateType

logger = logging.getLogger(__name__)

class UserActionGuidanceEngine:
    """Main engine for generating user action guidance."""
    
    def __init__(self, template_manager: TemplateManager,
                 compatibility_detector: Optional[CompatibilityErrorDetector] = None,
                 syntax_analyzer: Optional[SyntaxErrorAnalyzer] = None):
        self.template_manager = template_manager
        self.compatibility_detector = compatibility_detector
        self.syntax_analyzer = syntax_analyzer
        self.guidance_rules = self._load_guidance_rules()
        self.action_database = self._load_action_database()
        
    def _load_guidance_rules(self) -> Dict[str, Any]:
        """Load rules for generating user guidance."""
        # Implementation: Define guidance generation rules
        # Return: Dict with guidance rules
        
    def _load_action_database(self) -> Dict[str, List[str]]:
        """Load database of user actions for different error types."""
        # Implementation: Load predefined action sequences
        # Return: Dict mapping error type to action lists
        
    def generate_guidance(self, error: ClassifiedError, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Generate comprehensive guidance for an error."""
        # Implementation: Analyze error and generate guidance
        # Return: Dict with guidance information
        
    def generate_action_sequence(self, error: ClassifiedError) -> List[Dict[str, Any]]:
        """Generate sequence of actions to resolve error."""
        # Implementation: Create step-by-step action sequence
        # Return: List of action dictionaries
        
    def suggest_immediate_actions(self, error: ClassifiedError) -> List[str]:
        """Suggest immediate actions user can take."""
        # Implementation: Generate quick action suggestions
        # Return: List of immediate action strings
        
    def suggest_preventive_actions(self, error: ClassifiedError) -> List[str]:
        """Suggest actions to prevent similar errors."""
        # Implementation: Generate preventive action suggestions
        # Return: List of preventive action strings
        
    def generate_error_explanation(self, error: ClassifiedError) -> str:
        """Generate human-readable explanation of the error."""
        # Implementation: Create clear error explanation
        # Return: Explanation string
        
    def generate_resolution_steps(self, error: ClassifiedError) -> List[str]:
        """Generate step-by-step resolution instructions."""
        # Implementation: Create detailed resolution steps
        # Return: List of resolution step strings
        
    def suggest_alternative_solutions(self, error: ClassifiedError) -> List[Dict[str, Any]]:
        """Suggest alternative solutions for the error."""
        # Implementation: Generate alternative approaches
        # Return: List of alternative solution dictionaries
        
    def estimate_resolution_time(self, error: ClassifiedError) -> str:
        """Estimate time required to resolve the error."""
        # Implementation: Calculate estimated resolution time
        # Return: Time estimate string
        
    def generate_troubleshooting_guide(self, error: ClassifiedError) -> str:
        """Generate comprehensive troubleshooting guide."""
        # Implementation: Create detailed troubleshooting guide
        # Return: Formatted troubleshooting guide string
        
    def adapt_guidance_for_user_level(self, guidance: Dict[str, Any], user_level: str) -> Dict[str, Any]:
        """Adapt guidance for different user experience levels."""
        # Implementation: Modify guidance based on user level
        # Return: Adapted guidance dictionary
        
    def validate_guidance_effectiveness(self, error: ClassifiedError, guidance: Dict[str, Any]) -> float:
        """Validate effectiveness of generated guidance."""
        # Implementation: Score guidance quality and effectiveness
        # Return: Effectiveness score between 0.0 and 1.0

class ActionSequenceGenerator:
    """Generates sequences of user actions for error resolution."""
    
    def __init__(self):
        self.action_templates = self._load_action_templates()
        self.dependency_graph = self._load_dependency_graph()
        
    def _load_action_templates(self) -> Dict[str, Dict[str, Any]]:
        """Load templates for different types of actions."""
        # Implementation: Load action templates from configuration
        # Return: Dict with action templates
        
    def _load_dependency_graph(self) -> Dict[str, List[str]]:
        """Load dependency graph for action sequences."""
        # Implementation: Load action dependencies
        # Return: Dict mapping actions to prerequisites
        
    def generate_sequence(self, error_type: str, language: str, severity: ErrorSeverity) -> List[Dict[str, Any]]:
        """Generate action sequence for error resolution."""
        # Implementation: Create ordered action sequence
        # Return: List of action dictionaries
        
    def validate_sequence(self, sequence: List[Dict[str, Any]]) -> List[str]:
        """Validate action sequence for completeness and correctness."""
        # Implementation: Check sequence validity
        # Return: List of validation error messages
        
    def optimize_sequence(self, sequence: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Optimize action sequence for efficiency."""
        # Implementation: Reorder actions for optimal execution
        # Return: Optimized action sequence
        
    def add_custom_action(self, action: Dict[str, Any]) -> bool:
        """Add custom action to the system."""
        # Implementation: Add user-defined action
        # Return: True if successful, False otherwise
        
    def get_action_prerequisites(self, action_id: str) -> List[str]:
        """Get prerequisites for a specific action."""
        # Implementation: Return action prerequisites
        # Return: List of prerequisite action IDs

class GuidancePersonalizer:
    """Personalizes guidance based on user preferences and history."""
    
    def __init__(self):
        self.user_profiles = {}
        self.learning_history = {}
        
    def create_user_profile(self, user_id: str, preferences: Dict[str, Any]) -> None:
        """Create or update user profile."""
        # Implementation: Create/update user profile
        # Return: None, updates user profiles
        
    def personalize_guidance(self, guidance: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """Personalize guidance for specific user."""
        # Implementation: Adapt guidance to user preferences
        # Return: Personalized guidance dictionary
        
    def learn_from_user_feedback(self, user_id: str, error: ClassifiedError,
                               guidance: Dict[str, Any], feedback: Dict[str, Any]) -> None:
        """Learn from user feedback to improve future guidance."""
        # Implementation: Update learning history with feedback
        # Return: None, updates learning history
        
    def suggest_improvements(self, user_id: str, error: ClassifiedError) -> List[str]:
        """Suggest improvements based on user history."""
        # Implementation: Analyze user history for improvements
        # Return: List of improvement suggestions
        
    def get_user_preferences(self, user_id: str) -> Dict[str, Any]:
        """Get user preferences for guidance personalization."""
        # Implementation: Retrieve user preferences
        # Return: Dict with user preferences
        
    def update_user_preferences(self, user_id: str, preferences: Dict[str, Any]) -> None:
        """Update user preferences."""
        # Implementation: Update user preference settings
        # Return: None, updates preferences

class GuidanceQualityAssessor:
    """Assesses quality and effectiveness of generated guidance."""
    
    def __init__(self):
        self.quality_metrics = self._load_quality_metrics()
        
    def _load_quality_metrics(self) -> Dict[str, Any]:
        """Load quality assessment metrics."""
        # Implementation: Define quality assessment criteria
        # Return: Dict with quality metrics
        
    def assess_guidance_quality(self, guidance: Dict[str, Any], error: ClassifiedError) -> Dict[str, Any]:
        """Assess overall quality of generated guidance."""
        # Implementation: Apply quality metrics to guidance
        # Return: Dict with quality assessment results
        
    def assess_action_sequence_quality(self, sequence: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Assess quality of action sequence."""
        # Implementation: Evaluate action sequence quality
        # Return: Dict with sequence quality assessment
        
    def assess_explanation_clarity(self, explanation: str) -> Dict[str, Any]:
        """Assess clarity of error explanation."""
        # Implementation: Evaluate explanation clarity
        # Return: Dict with clarity assessment
        
    def suggest_quality_improvements(self, guidance: Dict[str, Any]) -> List[str]:
        """Suggest improvements to increase guidance quality."""
        # Implementation: Analyze guidance and suggest improvements
        # Return: List of improvement suggestions
        
    def generate_quality_report(self, guidance: Dict[str, Any]) -> str:
        """Generate quality assessment report."""
        # Implementation: Create comprehensive quality report
        # Return: Formatted quality report string
```

### IMPLEMENTATION REQUIREMENTS:
1. **Complete all methods** with full implementation
2. **Integrate with completed Group C tasks** (Error Analysis & Classification)
3. **Integrate with completed Task D1** (Error Message Templates)
4. **Handle guidance generation** for all error types
5. **Implement action sequence generation** with dependencies
6. **Add comprehensive error handling** for guidance failures
7. **Include logging** for debugging and monitoring
8. **Create unit tests** covering all guidance methods

### CRITICAL GROUP C INTEGRATION REQUIREMENTS:
9. **Pre-Implementation Validation**: Test ALL Group C imports before starting
10. **Constructor Compatibility**: Ensure all Group C classes are properly instantiated
11. **Error Handling Integration**: Test error scenarios with Group C components
12. **Dependency Verification**: Confirm all required Group C methods exist and work
13. **Integration Testing**: Test complete workflow with Groups A, B, and C

### TESTING REQUIREMENTS:
- Test guidance generation for various error types
- Test action sequence generation and validation
- Test guidance personalization
- Test quality assessment
- Test integration with error analysis components
- Achieve 90%+ code coverage

---

## TASK D3: TROUBLESHOOTING DATABASE

**ASSIGNED FILE**: `chunker/error_handling/troubleshooting.py`
**SUB-AGENT**: Troubleshooting Database Specialist
**IMPLEMENTATION DEADLINE**: Complete within assigned timeframe
**DEPENDENCIES**: None - can start immediately

### FILE STRUCTURE TO CREATE:
```python
# chunker/error_handling/troubleshooting.py

from typing import Dict, List, Optional, Any, Union, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import json
import logging
from pathlib import Path
from enum import Enum

logger = logging.getLogger(__name__)

class TroubleshootingCategory(Enum):
    """Categories of troubleshooting information."""
    COMPATIBILITY = "compatibility"
    SYNTAX = "syntax"
    GRAMMAR = "grammar"
    SYSTEM = "system"
    CONFIGURATION = "configuration"
    NETWORK = "network"
    PERMISSION = "permission"
    PERFORMANCE = "performance"
    SECURITY = "security"
    GENERAL = "general"

class SolutionType(Enum):
    """Types of solutions for problems."""
    WORKAROUND = "workaround"
    FIX = "fix"
    PREVENTION = "prevention"
    ALTERNATIVE = "alternative"
    UPGRADE = "upgrade"
    CONFIGURATION = "configuration"

@dataclass
class TroubleshootingEntry:
    """Entry in the troubleshooting database."""
    entry_id: str
    category: TroubleshootingCategory
    language: str
    error_pattern: str
    problem_description: str
    root_cause: str
    solutions: List[Dict[str, Any]] = field(default_factory=list)
    prerequisites: List[str] = field(default_factory=list)
    difficulty_level: str = "medium"  # "easy", "medium", "hard"
    estimated_time: str = "15 minutes"
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    success_rate: float = 0.8
    
    def __post_init__(self):
        """Validate troubleshooting entry data."""
        if not self.entry_id or not self.problem_description:
            raise ValueError("Entry ID and problem description are required")
        if not isinstance(self.category, TroubleshootingCategory):
            raise ValueError("Category must be TroubleshootingCategory enum")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        
    def __str__(self) -> str:
        """String representation of troubleshooting entry."""
        
    def add_solution(self, solution: Dict[str, Any]) -> None:
        """Add a solution to this entry."""
        
    def add_tag(self, tag: str) -> None:
        """Add a tag to this entry."""
        
    def update_success_rate(self, new_rate: float) -> None:
        """Update the success rate of this entry."""
        
    def get_best_solution(self) -> Optional[Dict[str, Any]]:
        """Get the best solution for this problem."""
        
    def get_solutions_by_type(self, solution_type: SolutionType) -> List[Dict[str, Any]]:
        """Get solutions of a specific type."""

@dataclass
class Solution:
    """Solution for a troubleshooting problem."""
    solution_id: str
    title: str
    description: str
    solution_type: SolutionType
    steps: List[str] = field(default_factory=list)
    code_examples: List[Dict[str, str]] = field(default_factory=list)
    verification_steps: List[str] = field(default_factory=list)
    prerequisites: List[str] = field(default_factory=list)
    difficulty: str = "medium"
    estimated_time: str = "10 minutes"
    success_rate: float = 0.9
    user_feedback: List[Dict[str, Any]] = field(default_factory=list)
    
    def __post_init__(self):
        """Validate solution data."""
        if not self.solution_id or not self.title or not self.description:
            raise ValueError("Solution ID, title, and description are required")
        if not isinstance(self.solution_type, SolutionType):
            raise ValueError("Solution type must be SolutionType enum")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        
    def __str__(self) -> str:
        """String representation of solution."""
        
    def add_step(self, step: str) -> None:
        """Add a step to the solution."""
        
    def add_code_example(self, language: str, code: str) -> None:
        """Add a code example to the solution."""
        
    def add_verification_step(self, step: str) -> None:
        """Add a verification step to the solution."""
        
    def add_user_feedback(self, feedback: Dict[str, Any]) -> None:
        """Add user feedback for this solution."""
        
    def calculate_success_rate(self) -> float:
        """Calculate success rate from user feedback."""
        
    def get_formatted_steps(self) -> str:
        """Get formatted steps for display."""

class TroubleshootingDatabase:
    """Main database for troubleshooting information."""
    
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or Path("troubleshooting.db")
        self.entries: Dict[str, TroubleshootingEntry] = {}
        self.solutions: Dict[str, Solution] = {}
        self.category_index: Dict[TroubleshootingCategory, List[str]] = {}
        self.language_index: Dict[str, List[str]] = {}
        self.tag_index: Dict[str, List[str]] = {}
        self._init_database()
        
    def _init_database(self) -> None:
        """Initialize the troubleshooting database."""
        # Implementation: Load database and create indexes
        # Return: None, initializes database
        
    def add_entry(self, entry: TroubleshootingEntry) -> bool:
        """Add a troubleshooting entry to the database."""
        # Implementation: Add entry and update indexes
        # Return: True if successful, False otherwise
        
    def add_solution(self, solution: Solution) -> bool:
        """Add a solution to the database."""
        # Implementation: Add solution to database
        # Return: True if successful, False otherwise
        
    def get_entry(self, entry_id: str) -> Optional[TroubleshootingEntry]:
        """Get troubleshooting entry by ID."""
        # Implementation: Retrieve entry from database
        # Return: TroubleshootingEntry object or None
        
    def get_solution(self, solution_id: str) -> Optional[Solution]:
        """Get solution by ID."""
        # Implementation: Retrieve solution from database
        # Return: Solution object or None
        
    def search_entries(self, query: str, category: Optional[TroubleshootingCategory] = None,
                      language: Optional[str] = None, tags: Optional[List[str]] = None) -> List[TroubleshootingEntry]:
        """Search troubleshooting entries."""
        # Implementation: Search entries by various criteria
        # Return: List of matching TroubleshootingEntry objects
        
    def find_entries_by_error(self, error_message: str, language: str) -> List[TroubleshootingEntry]:
        """Find entries that match an error message."""
        # Implementation: Match error message against patterns
        # Return: List of matching entries
        
    def get_entries_by_category(self, category: TroubleshootingCategory) -> List[TroubleshootingEntry]:
        """Get all entries in a specific category."""
        # Implementation: Return entries by category
        # Return: List of entries in category
        
    def get_entries_by_language(self, language: str) -> List[TroubleshootingEntry]:
        """Get all entries for a specific language."""
        # Implementation: Return entries by language
        # Return: List of entries for language
        
    def get_entries_by_tags(self, tags: List[str]) -> List[TroubleshootingEntry]:
        """Get entries that have specific tags."""
        # Implementation: Return entries matching tags
        # Return: List of matching entries
        
    def update_entry(self, entry_id: str, updates: Dict[str, Any]) -> bool:
        """Update an existing troubleshooting entry."""
        # Implementation: Update entry with new data
        # Return: True if successful, False otherwise
        
    def remove_entry(self, entry_id: str) -> bool:
        """Remove a troubleshooting entry."""
        # Implementation: Remove entry from database
        # Return: True if successful, False otherwise
        
    def export_database(self, output_path: Path, format_type: str = "json") -> None:
        """Export troubleshooting database to file."""
        # Implementation: Serialize database to file
        # Return: None, writes to specified path
        
    def import_database(self, input_path: Path) -> None:
        """Import troubleshooting database from file."""
        # Implementation: Load database from file
        # Return: None, loads database from file
        
    def backup_database(self, backup_path: Path) -> None:
        """Create backup of troubleshooting database."""
        # Implementation: Copy database to backup location
        # Return: None, creates backup
        
    def restore_database(self, backup_path: Path) -> None:
        """Restore database from backup."""
        # Implementation: Restore from backup file
        # Return: None, restores database
        
    def get_database_statistics(self) -> Dict[str, Any]:
        """Get statistics about the troubleshooting database."""
        # Implementation: Calculate database statistics
        # Return: Dict with database statistics
        
    def validate_database(self) -> List[str]:
        """Validate database integrity and return any errors."""
        # Implementation: Check database consistency
        # Return: List of validation error messages

class TroubleshootingSearchEngine:
    """Advanced search engine for troubleshooting database."""
    
    def __init__(self, database: TroubleshootingDatabase):
        self.database = database
        self.search_index = self._build_search_index()
        
    def _build_search_index(self) -> Dict[str, Any]:
        """Build search index for efficient searching."""
        # Implementation: Create search index from database
        # Return: Search index structure
        
    def search(self, query: str, filters: Optional[Dict[str, Any]] = None) -> List[TroubleshootingEntry]:
        """Search troubleshooting database with advanced filters."""
        # Implementation: Perform advanced search with filters
        # Return: List of matching entries
        
    def fuzzy_search(self, query: str, threshold: float = 0.7) -> List[Tuple[TroubleshootingEntry, float]]:
        """Perform fuzzy search for similar entries."""
        # Implementation: Fuzzy string matching for search
        # Return: List of (entry, similarity_score) tuples
        
    def search_by_similarity(self, error_message: str, language: str) -> List[Tuple[TroubleshootingEntry, float]]:
        """Search for entries similar to an error message."""
        # Implementation: Find similar error patterns
        # Return: List of (entry, similarity_score) tuples
        
    def suggest_search_terms(self, partial_query: str) -> List[str]:
        """Suggest search terms based on partial query."""
        # Implementation: Generate search term suggestions
        # Return: List of suggested search terms
        
    def get_search_suggestions(self, query: str) -> List[str]:
        """Get search suggestions for a query."""
        # Implementation: Generate search suggestions
        # Return: List of search suggestions

class TroubleshootingAnalytics:
    """Analytics and insights for troubleshooting database."""
    
    def __init__(self, database: TroubleshootingDatabase):
        self.database = database
        
    def get_popular_problems(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get most frequently encountered problems."""
        # Implementation: Analyze problem frequency
        # Return: List of popular problems with statistics
        
    def get_solution_effectiveness(self) -> Dict[str, float]:
        """Get effectiveness ratings for different solution types."""
        # Implementation: Calculate solution effectiveness
        # Return: Dict mapping solution types to effectiveness scores
        
    def get_user_satisfaction_metrics(self) -> Dict[str, Any]:
        """Get user satisfaction metrics for solutions."""
        # Implementation: Analyze user feedback and satisfaction
        # Return: Dict with satisfaction metrics
        
    def get_problem_trends(self, time_period: str = "month") -> Dict[str, Any]:
        """Get trends in problem occurrence over time."""
        # Implementation: Analyze problem trends over time
        # Return: Dict with trend information
        
    def generate_insights_report(self) -> str:
        """Generate comprehensive insights report."""
        # Implementation: Create insights report
        # Return: Formatted insights report string
        
    def identify_common_patterns(self) -> List[Dict[str, Any]]:
        """Identify common patterns in troubleshooting data."""
        # Implementation: Analyze data for common patterns
        # Return: List of identified patterns
```

### IMPLEMENTATION REQUIREMENTS:
1. **Complete all classes and methods** with full implementation
2. **Add comprehensive type hints** for all functions
3. **Include detailed docstrings** explaining each method's purpose
4. **Handle database operations** safely with proper indexing
5. **Implement search functionality** with fuzzy matching
6. **Add comprehensive error handling** for database failures
7. **Include logging** for debugging and monitoring
8. **Create unit tests** covering all troubleshooting methods

### TESTING REQUIREMENTS:
- Test database CRUD operations
- Test search functionality
- Test fuzzy matching
- Test analytics and insights
- Test import/export functionality
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

1. **Task D1 (Error Message Templates)**: Must be completed FIRST - no dependencies
2. **Task D2 (User Action Guidance Engine)**: Can start AFTER Group C is complete
3. **Task D3 (Troubleshooting Database)**: Can start immediately - no dependencies

### SUB-AGENT PROMPT TEMPLATE:

```
You are assigned to implement [TASK_NAME] for Group D.

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

1. **EXECUTE D1 AND D3 FIRST**: Start with D1 and D3 - no dependencies
2. **WAIT FOR GROUP C**: Ensure Group C completes before starting D2
3. **EXECUTE D2 AFTER GROUP C**: Start D2 once Group C is complete
4. **COLLECT RESULTS**: Gather completed implementations from each sub-agent
5. **VALIDATE COMPLETION**: Ensure all tasks are fully implemented
6. **REPORT SUMMARY**: Provide summary of all completed work

### CRITICAL VALIDATION STEPS:
7. **VERIFY GROUP C STATUS**: Confirm Group C is 100% functional before D2
8. **TEST INTEGRATION POINTS**: Validate Group C components work with D2 requirements
9. **VALIDATE DEPENDENCIES**: Ensure all required Group C classes and methods exist
10. **TEST ERROR SCENARIOS**: Verify error handling works with Group C components

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
- ✅ Dependencies are properly integrated (for D2)

### FINAL REPORT FORMAT:

```
GROUP D COMPLETION REPORT
========================

TASK D1 (Error Message Templates): [STATUS] - [SUB-AGENT NAME]
- File: chunker/error_handling/templates.py
- Methods implemented: [LIST]
- Test coverage: [PERCENTAGE]
- Issues/notes: [ANY]

TASK D2 (User Action Guidance Engine): [STATUS] - [SUB-AGENT NAME]
- File: chunker/error_handling/guidance_engine.py
- Methods implemented: [LIST]
- Test coverage: [PERCENTAGE]
- Dependencies met: [GROUP C STATUS]
- Issues/notes: [ANY]

TASK D3 (Troubleshooting Database): [STATUS] - [SUB-AGENT NAME]
- File: chunker/error_handling/troubleshooting.py
- Methods implemented: [LIST]
- Test coverage: [PERCENTAGE]
- Issues/notes: [ANY]

OVERALL STATUS: [COMPLETE/INCOMPLETE]
DEPENDENCY CHAIN: [D1, D3] -> [D2: GROUP C] - [STATUS]
NEXT STEPS: [WHAT COMES AFTER GROUP D]
```

---

## IMPORTANT NOTES

### FILE BOUNDARIES:
- **EACH SUB-AGENT TOUCHES EXACTLY ONE FILE**
- **NO CROSS-FILE DEPENDENCIES** within individual tasks
- **ALL IMPORTS MUST BE STANDARD LIBRARY** or from completed tasks
- **NO NEW DEPENDENCIES** can be added

### DEPENDENCY MANAGEMENT:
- **D1 (Error Message Templates)**: No dependencies - can start immediately
- **D2 (User Action Guidance Engine)**: Depends on Group C (C1, C2, C3)
- **D3 (Troubleshooting Database)**: No dependencies - can start immediately

### IMPLEMENTATION STANDARDS:
- **FULL IMPLEMENTATION** - no stubs or placeholders
- **PRODUCTION-READY CODE** - not prototype quality
- **COMPREHENSIVE TESTING** - 90%+ coverage required
- **ERROR HANDLING** - graceful degradation for all edge cases
- **LOGGING** - meaningful debug and info messages

### COORDINATION:
- **MIXED EXECUTION** - D1 and D3 can start immediately, D2 waits for Group C
- **DEPENDENCY VALIDATION** - ensure Group C completes before starting D2
- **MANAGER OVERSIGHT** - you coordinate and ensure proper execution order
- **QUALITY GATES** - validate completion before proceeding to dependent tasks

---

## EXECUTION COMMAND

**COPY AND PASTE THIS ENTIRE PROMPT** into your sub-agent manager system to begin execution of Group D tasks.

**EXPECTED DURATION**: 3-4 days with dependency-aware execution
**EXPECTED OUTCOME**: Complete user guidance system
**NEXT PHASE**: Group E (Integration & Testing) after Group D completion

## ENHANCED IMPLEMENTATION GUIDANCE

### PERFORMANCE CONSIDERATIONS:
- **Template Caching**: Cache frequently used templates for better performance
- **Memory Efficiency**: Handle large template libraries without memory issues
- **Rendering Optimization**: Optimize template rendering for speed
- **Batch Processing**: Process multiple templates efficiently

### USER EXPERIENCE STRATEGIES:
- **Progressive Disclosure**: Show essential information first, details on demand
- **Actionable Guidance**: Provide clear, step-by-step solutions
- **Context Awareness**: Adapt guidance based on user's current situation
- **Learning Integration**: Remember user preferences and improve over time

### QUALITY ASSURANCE:
- **Template Validation**: Ensure all templates are syntactically correct
- **Variable Safety**: Prevent template injection and security issues
- **Accessibility**: Ensure error messages are accessible to all users
- **Internationalization**: Prepare for future multi-language support

### CRITICAL LESSONS FROM GROUP C IMPLEMENTATION:
- **Constructor Validation**: Ensure all required arguments are properly documented and validated
- **Import Robustness**: Test all imports work before proceeding with implementation
- **Error Handling**: Implement graceful degradation for all edge cases
- **Integration Testing**: Test with Group C components to ensure compatibility
- **Initialization Safety**: Validate that all required dependencies are available

### PRE-IMPLEMENTATION VALIDATION CHECKLIST:
Before starting implementation, each sub-agent must:
1. **Verify Group C Integration**: Test imports from Group C components
2. **Validate Dependencies**: Ensure all required classes and methods exist
3. **Test Constructor Calls**: Verify all required arguments are documented
4. **Check Import Paths**: Ensure all import statements are correct
5. **Validate Error Handling**: Test error scenarios with Group C components

**START EXECUTION NOW** with Tasks D1 and D3, then proceed with D2 based on dependencies.

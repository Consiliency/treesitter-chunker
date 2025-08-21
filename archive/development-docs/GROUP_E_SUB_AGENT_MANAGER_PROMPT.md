# GROUP E SUB-AGENT MANAGER PROMPT
# Phase 1.7: Smart Error Handling & User Guidance - FINAL INTEGRATION
# Integration & Testing - PHASE 1.8 READINESS VERSION

## AGENT IDENTIFICATION & ROLES

**WHO I AM**: I am the primary AI agent working on Phase 1.7 implementation planning and coordination. I will NOT touch any of the files assigned to sub-agents in this prompt.

**WHO YOU ARE**: You are the sub-agent manager responsible for coordinating execution of Group E tasks. These tasks integrate all Phase 1.7 components and prepare for Phase 1.8.

**WHO THE SUB-AGENTS ARE**: Individual AI agents that will implement specific integration and testing components. Each sub-agent works on exactly ONE file and ONE task.

## EXECUTION STRATEGY

**SEQUENTIAL EXECUTION**: Tasks must be completed in order due to dependencies.
**FILE ISOLATION**: Each sub-agent touches ONLY their assigned file - no cross-file dependencies.
**PHASE 1.8 ALIGNMENT**: All implementations must align with SPEC_CALL_SPANS_IMPLEMENTATION.md requirements.

## GROUP E TASKS OVERVIEW

**OBJECTIVE**: Complete Phase 1.7 integration and prepare system for Phase 1.8 (User Grammar Management & CLI Tools).
**DEPENDENCIES**: Groups A, B, C, D must be complete before starting.
**OUTPUT**: Fully integrated Phase 1.7 system with Phase 1.8 infrastructure ready.

**PHASE 1.8 ALIGNMENT**: This implementation directly prepares for the CLI grammar management system specified in SPEC_CALL_SPANS_IMPLEMENTATION.md.

---

## TASK E1: ERROR HANDLING PIPELINE INTEGRATION

**ASSIGNED FILE**: `chunker/error_handling/integration.py`
**SUB-AGENT**: Error Handling Integration Specialist
**IMPLEMENTATION DEADLINE**: Complete within assigned timeframe
**DEPENDENCIES**: Groups A, B, C, D must be complete

### FILE STRUCTURE TO CREATE:
```python
# chunker/error_handling/integration.py

from typing import Dict, List, Optional, Any, Union, Tuple
from pathlib import Path
import logging
from datetime import datetime

# Import from completed Phase 1.7 components
from .classifier import ErrorClassifier, ClassifiedError, ErrorCategory, ErrorSeverity
from .compatibility_detector import CompatibilityErrorDetector
from .syntax_analyzer import SyntaxErrorAnalyzer
from .templates import TemplateManager
from .guidance_engine import UserActionGuidanceEngine
from .troubleshooting import TroubleshootingDatabase

logger = logging.getLogger(__name__)

class ErrorHandlingPipeline:
    """Main pipeline integrating all Phase 1.7 error handling components."""
    
    def __init__(self, template_manager: TemplateManager,
                 guidance_engine: UserActionGuidanceEngine,
                 troubleshooting_db: TroubleshootingDatabase):
        """Initialize the error handling pipeline."""
        self.template_manager = template_manager
        self.guidance_engine = guidance_engine
        self.troubleshooting_db = troubleshooting_db
        self.error_classifier = ErrorClassifier()
        self.compatibility_detector = None  # Will be initialized when needed
        self.syntax_analyzer = SyntaxErrorAnalyzer()
        self.pipeline_stats = self._initialize_stats()
        logger.info("Initialized ErrorHandlingPipeline")
        
    def _initialize_stats(self) -> Dict[str, Any]:
        """Initialize pipeline statistics."""
        return {
            'total_errors_processed': 0,
            'errors_by_category': {},
            'errors_by_severity': {},
            'processing_times': [],
            'success_rate': 1.0,
            'last_updated': datetime.now()
        }
    
    def process_error(self, error_message: str, context: Optional[Dict[str, Any]] = None,
                     language: Optional[str] = None) -> Dict[str, Any]:
        """Process an error through the complete pipeline."""
        start_time = datetime.now()
        
        try:
            # Step 1: Classify the error
            classified_error = self.error_classifier.classify_error(error_message, context)
            
            # Step 2: Detect compatibility issues if language is known
            compatibility_issues = []
            if language:
                compatibility_issues = self._detect_compatibility_issues(language, context)
            
            # Step 3: Analyze syntax if applicable
            syntax_analysis = None
            if classified_error.category == ErrorCategory.SYNTAX:
                syntax_analysis = self._analyze_syntax_error(error_message, context)
            
            # Step 4: Generate user guidance
            guidance = self.guidance_engine.generate_guidance(classified_error, context)
            
            # Step 5: Find troubleshooting information
            troubleshooting = self._find_troubleshooting_info(classified_error, language)
            
            # Step 6: Update statistics
            self._update_stats(classified_error, datetime.now() - start_time)
            
            return {
                'error_id': classified_error.error_id,
                'classification': {
                    'category': classified_error.category.value,
                    'severity': classified_error.severity.value,
                    'source': classified_error.source.value,
                    'confidence': classified_error.confidence
                },
                'compatibility_issues': compatibility_issues,
                'syntax_analysis': syntax_analysis,
                'user_guidance': guidance,
                'troubleshooting': troubleshooting,
                'processing_time': (datetime.now() - start_time).total_seconds(),
                'pipeline_version': '1.7.0'
            }
            
        except Exception as e:
            logger.error(f"Error in pipeline processing: {e}")
            return self._generate_fallback_response(error_message, str(e))
    
    def _detect_compatibility_issues(self, language: str, context: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Detect language version compatibility issues."""
        try:
            if self.compatibility_detector is None:
                # Lazy initialization
                from ..languages.compatibility.database import CompatibilityDatabase
                db = CompatibilityDatabase()
                self.compatibility_detector = CompatibilityErrorDetector(compatibility_db=db)
            
            # Detect compatibility issues
            issues = self.compatibility_detector.detect_compatibility_errors(
                f"Language: {language}", 
                context.get('file_path') if context else None,
                language
            )
            
            return [issue.to_dict() for issue in issues]
            
        except Exception as e:
            logger.warning(f"Compatibility detection failed: {e}")
            return []
    
    def _analyze_syntax_error(self, error_message: str, context: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Analyze syntax errors for patterns and causes."""
        try:
            # Use syntax analyzer to get detailed information
            analysis = self.syntax_analyzer.analyze_error(error_message, context)
            return analysis
            
        except Exception as e:
            logger.warning(f"Syntax analysis failed: {e}")
            return None
    
    def _find_troubleshooting_info(self, error: ClassifiedError, language: Optional[str]) -> List[Dict[str, Any]]:
        """Find relevant troubleshooting information."""
        try:
            # Search troubleshooting database
            entries = self.troubleshooting_db.find_entries_by_error(
                error.message, 
                language or 'unknown'
            )
            
            return [entry.to_dict() for entry in entries[:3]]  # Limit to top 3
            
        except Exception as e:
            logger.warning(f"Troubleshooting lookup failed: {e}")
            return []
    
    def _update_stats(self, error: ClassifiedError, processing_time: datetime) -> None:
        """Update pipeline statistics."""
        self.pipeline_stats['total_errors_processed'] += 1
        
        # Update category stats
        category = error.category.value
        if category not in self.pipeline_stats['errors_by_category']:
            self.pipeline_stats['errors_by_category'][category] = 0
        self.pipeline_stats['errors_by_category'][category] += 1
        
        # Update severity stats
        severity = error.severity.value
        if severity not in self.pipeline_stats['errors_by_severity']:
            self.pipeline_stats['errors_by_severity'][severity] = 0
        self.pipeline_stats['errors_by_severity'][severity] += 1
        
        # Update processing times
        self.pipeline_stats['processing_times'].append(processing_time.total_seconds())
        if len(self.pipeline_stats['processing_times']) > 100:
            self.pipeline_stats['processing_times'] = self.pipeline_stats['processing_times'][-100:]
        
        # Update success rate
        total_processed = self.pipeline_stats['total_errors_processed']
        successful = sum(1 for t in self.pipeline_stats['processing_times'] if t < 5.0)  # <5s is successful
        self.pipeline_stats['success_rate'] = successful / total_processed if total_processed > 0 else 1.0
        
        self.pipeline_stats['last_updated'] = datetime.now()
    
    def _generate_fallback_response(self, error_message: str, error_details: str) -> Dict[str, Any]:
        """Generate fallback response when pipeline fails."""
        return {
            'error_id': f"fallback_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            'classification': {
                'category': 'unknown',
                'severity': 'error',
                'source': 'pipeline',
                'confidence': 0.0
            },
            'compatibility_issues': [],
            'syntax_analysis': None,
            'user_guidance': {
                'message': 'Error processing failed. Please check your input and try again.',
                'actions': ['Verify input format', 'Check system requirements', 'Contact support if issue persists']
            },
            'troubleshooting': [],
            'processing_time': 0.0,
            'pipeline_version': '1.7.0',
            'fallback_used': True,
            'fallback_reason': error_details
        }
    
    def get_pipeline_stats(self) -> Dict[str, Any]:
        """Get current pipeline statistics."""
        stats = self.pipeline_stats.copy()
        stats['last_updated'] = stats['last_updated'].isoformat()
        
        # Calculate average processing time
        if stats['processing_times']:
            stats['avg_processing_time'] = sum(stats['processing_times']) / len(stats['processing_times'])
        else:
            stats['avg_processing_time'] = 0.0
        
        return stats
    
    def reset_pipeline_stats(self) -> None:
        """Reset pipeline statistics."""
        self.pipeline_stats = self._initialize_stats()
        logger.info("Pipeline statistics reset")
    
    def validate_pipeline_health(self) -> Dict[str, Any]:
        """Validate pipeline health and component status."""
        health_status = {
            'pipeline_status': 'healthy',
            'components': {},
            'last_check': datetime.now().isoformat()
        }
        
        # Check each component
        try:
            self.error_classifier.classify_error("test error")
            health_status['components']['error_classifier'] = 'healthy'
        except Exception as e:
            health_status['components']['error_classifier'] = f'unhealthy: {e}'
            health_status['pipeline_status'] = 'degraded'
        
        try:
            self.syntax_analyzer.analyze_error("test syntax error")
            health_status['components']['syntax_analyzer'] = 'healthy'
        except Exception as e:
            health_status['components']['syntax_analyzer'] = f'unhealthy: {e}'
            health_status['pipeline_status'] = 'degraded'
        
        try:
            self.template_manager.get_template("test")
            health_status['components']['template_manager'] = 'healthy'
        except Exception as e:
            health_status['components']['template_manager'] = f'unhealthy: {e}'
            health_status['pipeline_status'] = 'degraded'
        
        try:
            self.guidance_engine.generate_guidance(
                ClassifiedError("test", "test", ErrorCategory.SYNTAX, ErrorSeverity.ERROR, ErrorSource.TREE_SITTER)
            )
            health_status['components']['guidance_engine'] = 'healthy'
        except Exception as e:
            health_status['components']['guidance_engine'] = f'unhealthy: {e}'
            health_status['pipeline_status'] = 'degraded'
        
        try:
            self.troubleshooting_db.get_database_statistics()
            health_status['components']['troubleshooting_db'] = 'healthy'
        except Exception as e:
            health_status['components']['troubleshooting_db'] = f'unhealthy: {e}'
            health_status['pipeline_status'] = 'degraded'
        
        return health_status

class ErrorHandlingOrchestrator:
    """Orchestrates error handling across multiple components."""
    
    def __init__(self, pipeline: ErrorHandlingPipeline):
        """Initialize the orchestrator."""
        self.pipeline = pipeline
        self.active_sessions = {}
        self.logger = logging.getLogger(__name__)
        
    def create_error_session(self, session_id: str, user_context: Optional[Dict[str, Any]] = None) -> str:
        """Create a new error handling session."""
        self.active_sessions[session_id] = {
            'created_at': datetime.now(),
            'user_context': user_context or {},
            'errors_processed': [],
            'session_stats': {}
        }
        self.logger.info(f"Created error session: {session_id}")
        return session_id
    
    def process_error_in_session(self, session_id: str, error_message: str, 
                               context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Process an error within a specific session."""
        if session_id not in self.active_sessions:
            raise ValueError(f"Session {session_id} not found")
        
        # Process the error
        result = self.pipeline.process_error(error_message, context)
        
        # Update session
        session = self.active_sessions[session_id]
        session['errors_processed'].append({
            'timestamp': datetime.now().isoformat(),
            'error_id': result['error_id'],
            'category': result['classification']['category'],
            'severity': result['classification']['severity']
        })
        
        # Update session statistics
        session['session_stats'] = {
            'total_errors': len(session['errors_processed']),
            'errors_by_category': {},
            'errors_by_severity': {},
            'avg_processing_time': 0.0
        }
        
        # Calculate session-specific stats
        for error in session['errors_processed']:
            category = error['category']
            severity = error['severity']
            
            if category not in session['session_stats']['errors_by_category']:
                session['session_stats']['errors_by_category'][category] = 0
            session['session_stats']['errors_by_category'][category] += 1
            
            if severity not in session['session_stats']['errors_by_severity']:
                session['session_stats']['errors_by_severity'][severity] = 0
            session['session_stats']['errors_by_severity'][severity] += 1
        
        return result
    
    def get_session_summary(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get summary of an error handling session."""
        if session_id not in self.active_sessions:
            return None
        
        session = self.active_sessions[session_id]
        return {
            'session_id': session_id,
            'created_at': session['created_at'].isoformat(),
            'user_context': session['user_context'],
            'session_stats': session['session_stats'],
            'errors_processed': session['errors_processed']
        }
    
    def close_session(self, session_id: str) -> bool:
        """Close an error handling session."""
        if session_id in self.active_sessions:
            del self.active_sessions[session_id]
            self.logger.info(f"Closed error session: {session_id}")
            return True
        return False
```

### IMPLEMENTATION REQUIREMENTS:
1. **Complete all classes and methods** with full implementation
2. **Integrate with all completed Phase 1.7 components** (Groups A, B, C, D)
3. **Implement error handling pipeline** with fallback mechanisms
4. **Add comprehensive error handling** for pipeline failures
5. **Include logging** for debugging and monitoring
6. **Create unit tests** covering all pipeline methods
7. **Ensure Phase 1.8 readiness** for CLI integration

### PHASE 1.8 ALIGNMENT REQUIREMENTS:
8. **CLI Integration Points**: Prepare for grammar validation commands
9. **Error Reporting**: Integrate with grammar management workflows
10. **Compatibility Checking**: Support grammar compatibility validation
11. **User Experience**: Ensure seamless error handling for CLI users

---

## TASK E2: GRAMMAR MANAGEMENT INFRASTRUCTURE

**ASSIGNED FILE**: `chunker/grammar_management/cli.py`
**SUB-AGENT**: Grammar Management CLI Specialist
**IMPLEMENTATION DEADLINE**: Complete within assigned timeframe
**DEPENDENCIES**: Task E1 must be complete

### FILE STRUCTURE TO CREATE:
```python
# chunker/grammar_management/cli.py

import click
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

# Import from completed Phase 1.7 components
from ..error_handling.integration import ErrorHandlingPipeline, ErrorHandlingOrchestrator

logger = logging.getLogger(__name__)

@click.group()
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose logging')
@click.option('--config', '-c', type=click.Path(exists=True), help='Configuration file path')
def grammar(verbose, config):
    """Grammar management commands for treesitter-chunker."""
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Initialize error handling pipeline
    # This will be fully implemented when Group D completes
    
@grammar.command()
def list():
    """List available and user-installed grammars."""
    click.echo("Available Grammars:")
    # Implementation: List grammars from package and user directories
    
@grammar.command()
@click.argument('language')
def info(language):
    """Show grammar details and compatibility information."""
    click.echo(f"Grammar Information for {language}:")
    # Implementation: Display grammar details and compatibility
    
@grammar.command()
@click.argument('language')
def versions(language):
    """List available versions for a language."""
    click.echo(f"Available versions for {language}:")
    # Implementation: List available grammar versions
    
@grammar.command()
@click.argument('language')
@click.option('--version', '-v', help='Specific version to fetch')
def fetch(language, version):
    """Download specific grammar version."""
    click.echo(f"Fetching grammar for {language}")
    # Implementation: Download and install grammar
    
@grammar.command()
@click.argument('language')
def build(language):
    """Build grammar from source."""
    click.echo(f"Building grammar for {language}")
    # Implementation: Build grammar from source
    
@grammar.command()
@click.argument('language')
def remove(language):
    """Remove user-installed grammar."""
    click.echo(f"Removing grammar for {language}")
    # Implementation: Remove user grammar
    
@grammar.command()
@click.argument('language')
@click.argument('file', type=click.Path(exists=True))
def test(language, file):
    """Test grammar with specific file."""
    click.echo(f"Testing {language} grammar with {file}")
    # Implementation: Test grammar compatibility
    
@grammar.command()
@click.argument('language')
def validate(language):
    """Validate grammar installation."""
    click.echo(f"Validating {language} grammar")
    # Implementation: Validate grammar installation
```

### IMPLEMENTATION REQUIREMENTS:
1. **Implement all CLI commands** as specified in Phase 1.8
2. **Integrate with error handling pipeline** from Task E1
3. **Handle grammar discovery and management** operations
4. **Add comprehensive error handling** for CLI operations
5. **Include logging** for debugging and monitoring
6. **Create unit tests** covering all CLI commands
7. **Ensure Phase 1.8 specification compliance**

### PHASE 1.8 ALIGNMENT REQUIREMENTS:
8. **CLI Commands**: Implement all specified commands exactly
9. **Directory Structure**: Support `~/.cache/treesitter-chunker/grammars/`
10. **Grammar Selection**: Implement user-installed → package → fallback priority
11. **Error Handling**: Provide clear guidance for all failure scenarios

---

## TASK E3: SYSTEM INTEGRATION TESTING

**ASSIGNED FILE**: `chunker/testing/system_integration.py`
**SUB-AGENT**: System Integration Testing Specialist
**IMPLEMENTATION DEADLINE**: Complete within assigned timeframe
**DEPENDENCIES**: Tasks E1 and E2 must be complete

### FILE STRUCTURE TO CREATE:
```python
# chunker/testing/system_integration.py

from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
import logging
import time
import json
from datetime import datetime

# Import from completed Phase 1.7 components
from ..error_handling.integration import ErrorHandlingPipeline, ErrorHandlingOrchestrator
from ..grammar_management.cli import grammar

logger = logging.getLogger(__name__)

class SystemIntegrationTester:
    """Comprehensive testing of complete Phase 1.7 system."""
    
    def __init__(self):
        """Initialize the system integration tester."""
        self.test_results = {}
        self.performance_metrics = {}
        self.logger = logging.getLogger(__name__)
        
    def run_complete_system_test(self) -> Dict[str, Any]:
        """Run complete system integration test."""
        # Implementation: Test all Phase 1.7 components working together
        
    def test_error_handling_pipeline(self) -> Dict[str, Any]:
        """Test error handling pipeline integration."""
        # Implementation: Test error handling pipeline
        
    def test_grammar_management_cli(self) -> Dict[str, Any]:
        """Test grammar management CLI functionality."""
        # Implementation: Test CLI commands
        
    def test_end_to_end_workflows(self) -> Dict[str, Any]:
        """Test complete end-to-end workflows."""
        # Implementation: Test complete workflows
        
    def test_performance_metrics(self) -> Dict[str, Any]:
        """Test system performance and scalability."""
        # Implementation: Performance testing
        
    def generate_integration_report(self) -> str:
        """Generate comprehensive integration test report."""
        # Implementation: Generate test report
```

### IMPLEMENTATION REQUIREMENTS:
1. **Implement comprehensive system testing** for all components
2. **Test error handling pipeline** integration and workflows
3. **Validate grammar management CLI** functionality
4. **Test end-to-end workflows** across all groups
5. **Include performance testing** and benchmarking
6. **Create detailed test reports** with metrics
7. **Ensure Phase 1.8 readiness** validation

### PHASE 1.8 ALIGNMENT REQUIREMENTS:
8. **CLI Testing**: Validate all grammar management commands
9. **Integration Testing**: Test CLI + error handling + grammar management
10. **User Experience Testing**: Validate error handling workflows
11. **Performance Validation**: Ensure CLI performance meets requirements

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
10. **ENSURE PHASE 1.8 ALIGNMENT** with specification requirements

### EXECUTION ORDER:

**IMPORTANT**: These tasks have strict dependencies:

1. **Task E1**: Must be completed FIRST - creates error handling pipeline
2. **Task E2**: Can start AFTER Task E1 - depends on pipeline integration
3. **Task E3**: Can start AFTER Tasks E1 and E2 - tests complete system

### SUB-AGENT PROMPT TEMPLATE:

```
You are assigned to implement [TASK_NAME] for Group E.

YOUR FILE: [FILE_PATH]
YOUR TASK: [TASK_DESCRIPTION]
DEPENDENCIES: [LIST OF DEPENDENCIES]
PHASE 1.8 ALIGNMENT: [SPECIFIC ALIGNMENT REQUIREMENTS]

REQUIREMENTS:
- Implement ALL methods in the class structure provided
- Add comprehensive type hints and docstrings
- Handle edge cases and error conditions
- Include logging and error handling
- Create unit tests with 90%+ coverage
- ONLY touch the assigned file
- Ensure compatibility with [DEPENDENT_TASKS] if applicable
- Maintain Phase 1.8 specification compliance

DO NOT:
- Modify any other files
- Skip any methods
- Leave TODO comments
- Create incomplete implementations
- Deviate from Phase 1.8 specification requirements

START IMPLEMENTATION NOW.
```

---

## COORDINATION & REPORTING

### SUB-AGENT MANAGER RESPONSIBILITIES:

1. **EXECUTE E1 FIRST**: Start with Task E1 (Error Handling Pipeline)
2. **WAIT FOR E1 COMPLETION**: Ensure E1 is complete before starting E2
3. **EXECUTE E2 AFTER E1**: Start E2 once E1 is complete
4. **EXECUTE E3 AFTER E2**: Start E3 once both E1 and E2 are complete
5. **COLLECT RESULTS**: Gather completed implementations from each sub-agent
6. **VALIDATE COMPLETION**: Ensure all tasks are fully implemented
7. **VERIFY PHASE 1.8 READINESS**: Confirm system is ready for Phase 1.8
8. **REPORT SUMMARY**: Provide summary of all completed work

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
- ✅ Dependencies are properly integrated
- ✅ Phase 1.8 alignment is verified

### FINAL REPORT FORMAT:

```
GROUP E COMPLETION REPORT
========================

TASK E1 (Error Handling Pipeline Integration): [STATUS] - [SUB-AGENT NAME]
- File: chunker/error_handling/integration.py
- Methods implemented: [LIST]
- Test coverage: [PERCENTAGE]
- Phase 1.8 readiness: [STATUS]
- Issues/notes: [ANY]

TASK E2 (Grammar Management Infrastructure): [STATUS] - [SUB-AGENT NAME]
- File: chunker/grammar_management/cli.py
- Methods implemented: [LIST]
- Test coverage: [PERCENTAGE]
- CLI commands implemented: [LIST]
- Phase 1.8 compliance: [STATUS]
- Issues/notes: [ANY]

TASK E3 (System Integration Testing): [STATUS] - [SUB-AGENT NAME]
- File: chunker/testing/system_integration.py
- Methods implemented: [LIST]
- Test coverage: [PERCENTAGE]
- Integration tests: [LIST]
- Performance metrics: [STATUS]
- Issues/notes: [ANY]

OVERALL STATUS: [COMPLETE/INCOMPLETE]
PHASE 1.8 READINESS: [READY/NOT READY]
NEXT STEPS: [PHASE 1.8 IMPLEMENTATION]
```

---

## IMPORTANT NOTES

### FILE BOUNDARIES:
- **EACH SUB-AGENT TOUCHES EXACTLY ONE FILE**
- **NO CROSS-FILE DEPENDENCIES** within individual tasks
- **ALL IMPORTS MUST BE STANDARD LIBRARY** or from completed tasks
- **NO NEW DEPENDENCIES** can be added

### DEPENDENCY MANAGEMENT:
- **E1 (Error Handling Pipeline)**: No dependencies - can start immediately
- **E2 (Grammar Management CLI)**: Depends on Task E1 completion
- **E3 (System Integration Testing)**: Depends on Tasks E1 and E2 completion

### PHASE 1.8 ALIGNMENT:
- **CLI Commands**: Must match specification exactly
- **Directory Structure**: Must support specified user grammar paths
- **Grammar Selection**: Must implement specified priority order
- **Error Handling**: Must provide clear user guidance

### IMPLEMENTATION STANDARDS:
- **FULL IMPLEMENTATION** - no stubs or placeholders
- **PRODUCTION-READY CODE** - not prototype quality
- **COMPREHENSIVE TESTING** - 90%+ coverage required
- **ERROR HANDLING** - graceful degradation for all edge cases
- **LOGGING** - meaningful debug and info messages
- **PHASE 1.8 COMPLIANCE** - specification requirements met

### COORDINATION:
- **SEQUENTIAL EXECUTION** - E1 → E2 → E3 due to dependencies
- **DEPENDENCY VALIDATION** - ensure previous tasks complete before starting next
- **MANAGER OVERSIGHT** - you coordinate and ensure proper execution order
- **QUALITY GATES** - validate completion before proceeding to dependent tasks
- **PHASE 1.8 VERIFICATION** - confirm system meets specification requirements

---

## EXECUTION COMMAND

**COPY AND PASTE THIS ENTIRE PROMPT** into your sub-agent manager system to begin execution of Group E tasks.

**EXPECTED DURATION**: 2-3 days with sequential execution
**EXPECTED OUTCOME**: Complete Phase 1.7 system with Phase 1.8 infrastructure ready
**NEXT PHASE**: Phase 1.8 (User Grammar Management & CLI Tools) after Group E completion

## PHASE 1.8 READINESS VALIDATION

### FINAL VALIDATION CHECKLIST:

Before marking Group E complete, verify:

1. **Error Handling Pipeline**: ✅ Fully functional and integrated
2. **Grammar Management CLI**: ✅ All commands implemented and working
3. **System Integration**: ✅ All components working together
4. **Phase 1.8 Alignment**: ✅ Specification requirements met
5. **Performance**: ✅ System performance acceptable
6. **Testing**: ✅ Comprehensive test coverage achieved
7. **Documentation**: ✅ All components documented
8. **Production Readiness**: ✅ System ready for production use

**START EXECUTION NOW** with Task E1, then proceed with E2 and E3 based on dependencies.

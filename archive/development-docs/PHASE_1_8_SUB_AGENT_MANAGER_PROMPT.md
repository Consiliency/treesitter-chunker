# PHASE 1.8 SUB-AGENT MANAGER PROMPT
# User Grammar Management & CLI Tools - Parallel Execution

## AGENT IDENTIFICATION & ROLES

**WHO I AM**: I am the primary AI agent working on Phase 1.7 implementation planning and coordination. I will NOT touch any of the files assigned to sub-agents in this prompt.

**WHO YOU ARE**: You are the sub-agent manager responsible for coordinating execution of Phase 1.8 tasks. These tasks implement the user grammar management system with CLI tools.

**WHO THE SUB-AGENTS ARE**: Individual AI agents that will implement specific grammar management components. Each sub-agent works on exactly ONE file and ONE task.

## EXECUTION STRATEGY

**PARALLEL EXECUTION**: 5 tasks designed for parallel execution with clear dependencies.
**FILE ISOLATION**: Each sub-agent touches ONLY their assigned file - no cross-file dependencies.
**QUALITY ASSURANCE**: 90%+ test coverage and production-ready code required.
**DEPENDENCY MANAGEMENT**: Some tasks must complete before others can start.

## PHASE 1.8 TASKS OVERVIEW

**OBJECTIVE**: Implement user grammar management system with CLI tools for Phase 1.8.
**DEPENDENCIES**: Phase 1.7 (Smart Error Handling) must be complete.
**OUTPUT**: Complete grammar management system with CLI interface.
**TIMELINE**: 1 week with parallel execution.

**PARALLEL EXECUTION MODEL:**
- **Tasks 1.8.1, 1.8.3, 1.8.4**: Can start simultaneously (no dependencies)
- **Task 1.8.2**: Must wait for Task 1.8.1 completion
- **Task 1.8.5**: Must wait for all other tasks completion

---

## TASK 1.8.1: GRAMMAR MANAGEMENT CORE

**ASSIGNED FILE**: `chunker/grammar_management/core.py`
**SUB-AGENT**: Grammar Management Core Specialist
**IMPLEMENTATION DEADLINE**: Complete within assigned timeframe
**DEPENDENCIES**: None (can start immediately)

### FILE STRUCTURE TO CREATE:
```python
# chunker/grammar_management/core.py

from typing import Dict, List, Optional, Any, Union, Tuple
from pathlib import Path
import logging
from datetime import datetime
import hashlib
import json

logger = logging.getLogger(__name__)

class GrammarManager:
    """Core grammar management engine."""
    
    def __init__(self, user_grammar_dir: Optional[Path] = None):
        """Initialize grammar manager."""
        self.user_grammar_dir = user_grammar_dir or self._get_default_user_dir()
        self.package_grammar_dir = self._get_package_grammar_dir()
        self.registry = GrammarRegistry()
        self.installer = GrammarInstaller(self.user_grammar_dir)
        self.validator = GrammarValidator()
        self._discover_grammars()
    
    def _get_default_user_dir(self) -> Path:
        """Get default user grammar directory."""
        # Implementation: Return default user directory
        
    def _get_package_grammar_dir(self) -> Path:
        """Get package grammar directory."""
        # Implementation: Return package grammar directory
        
    def _discover_grammars(self) -> None:
        """Discover and register available grammars."""
        # Implementation: Scan directories and register grammars
        
    def discover_grammars(self) -> Dict[str, List[Dict[str, Any]]]:
        """Discover all available grammars from package and user directories."""
        # Implementation: Return discovered grammar information
        
    def install_grammar(self, language: str, version: Optional[str] = None, 
                       source: str = "official") -> bool:
        """Install grammar for specified language and version."""
        # Implementation: Download, build, install, and validate
        
    def remove_grammar(self, language: str, version: Optional[str] = None) -> bool:
        """Remove specified grammar version."""
        # Implementation: Remove grammar and clean up dependencies
        
    def get_grammar_info(self, language: str, version: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get detailed information about grammar."""
        # Implementation: Retrieve grammar metadata and status
        
    def validate_grammar(self, language: str, version: Optional[str] = None) -> Dict[str, Any]:
        """Validate grammar installation and performance."""
        # Implementation: Run comprehensive validation tests

class GrammarRegistry:
    """Manages grammar registration and lookup."""
    
    def __init__(self):
        """Initialize grammar registry."""
        self.grammars = {}
        self.sources = {}
        self.versions = {}
    
    def register_grammar(self, language: str, version: str, source: str, 
                        path: Path, metadata: Dict[str, Any]) -> None:
        """Register a grammar in the registry."""
        # Implementation: Add grammar to registry with metadata
        
    def find_grammar(self, language: str, version: Optional[str] = None, 
                     source: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Find grammar matching criteria."""
        # Implementation: Search registry with priority logic
        
    def get_grammar_versions(self, language: str) -> List[str]:
        """Get all available versions for a language."""
        # Implementation: Return sorted version list
        
    def detect_conflicts(self, language: str) -> List[Dict[str, Any]]:
        """Detect version conflicts for a language."""
        # Implementation: Identify and analyze conflicts

class GrammarInstaller:
    """Handles grammar installation and build processes."""
    
    def __init__(self, user_grammar_dir: Path):
        """Initialize grammar installer."""
        self.user_grammar_dir = user_grammar_dir
        self.download_cache = user_grammar_dir / "cache" / "downloads"
        self.build_cache = user_grammar_dir / "cache" / "builds"
        self._setup_cache_directories()
    
    def _setup_cache_directories(self) -> None:
        """Create cache directory structure."""
        # Implementation: Create cache directories
        
    def download_grammar(self, language: str, version: str, source: str) -> Path:
        """Download grammar from specified source."""
        # Implementation: Download with progress tracking and validation
        
    def build_grammar(self, source_path: Path, language: str, version: str) -> Path:
        """Build grammar from source."""
        # Implementation: Compile grammar with appropriate flags
        
    def install_grammar(self, grammar_path: Path, language: str, version: str) -> bool:
        """Install compiled grammar to user directory."""
        # Implementation: Copy to user directory and update registry
        
    def rollback_installation(self, language: str, version: str) -> bool:
        """Rollback failed installation."""
        # Implementation: Remove failed installation and restore previous state

class GrammarValidator:
    """Validates grammar installations and performance."""
    
    def __init__(self):
        """Initialize grammar validator."""
        self.test_samples = self._load_test_samples()
    
    def _load_test_samples(self) -> Dict[str, List[Path]]:
        """Load test sample files."""
        # Implementation: Load test samples for validation
        
    def validate_integrity(self, grammar_path: Path) -> Dict[str, Any]:
        """Validate grammar file integrity."""
        # Implementation: Checksum validation and file structure checking
        
    def validate_compatibility(self, grammar_path: Path, language: str, 
                             version: str) -> Dict[str, Any]:
        """Validate grammar compatibility."""
        # Implementation: Test with sample code and version checking
        
    def test_performance(self, grammar_path: Path, language: str) -> Dict[str, Any]:
        """Test grammar performance."""
        # Implementation: Parse time and memory usage testing
        
    def run_health_check(self, grammar_path: Path) -> Dict[str, Any]:
        """Run comprehensive health check."""
        # Implementation: Full validation suite
```

### IMPLEMENTATION REQUIREMENTS:
1. **Complete all classes and methods** with full implementation
2. **Add comprehensive type hints** for all functions
3. **Include detailed docstrings** explaining each method
4. **Handle edge cases** and error conditions gracefully
5. **Add logging** for debugging and monitoring
6. **Create unit tests** covering all methods
7. **Ensure no cross-file dependencies** within this task

---

## TASK 1.8.2: CLI INTERFACE

**ASSIGNED FILE**: `chunker/grammar_management/cli.py`
**SUB-AGENT**: CLI Interface Specialist
**IMPLEMENTATION DEADLINE**: Complete within assigned timeframe
**DEPENDENCIES**: Task 1.8.1 (Grammar Management Core) must be complete

### FILE STRUCTURE TO CREATE:
```python
# chunker/grammar_management/cli.py

import click
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

# Import from Task 1.8.1
from .core import GrammarManager

logger = logging.getLogger(__name__)

@click.group()
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose logging')
@click.option('--config', '-c', type=click.Path(exists=True), help='Configuration file path')
@click.option('--user-dir', '-u', type=click.Path(), help='User grammar directory')
def grammar(verbose, config, user_dir):
    """Grammar management commands for treesitter-chunker."""
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Initialize grammar manager
    user_grammar_dir = Path(user_dir) if user_dir else None
    ctx.obj = GrammarManager(user_grammar_dir=user_grammar_dir)

@grammar.command()
@click.option('--user-only', is_flag=True, help='Show only user-installed grammars')
@click.option('--package-only', is_flag=True, help='Show only package grammars')
@click.option('--format', type=click.Choice(['table', 'json', 'yaml']), default='table')
@click.pass_context
def list(ctx, user_only, package_only, format):
    """List available and user-installed grammars."""
    # Implementation: List grammars with filtering and formatting

@grammar.command()
@click.argument('language')
@click.option('--version', '-v', help='Specific version to show info for')
@click.option('--detailed', '-d', is_flag=True, help='Show detailed compatibility info')
@click.pass_context
def info(ctx, language, version, detailed):
    """Show grammar details and compatibility information."""
    # Implementation: Display grammar information

@grammar.command()
@click.argument('language')
@click.option('--available', is_flag=True, help='Show only available versions')
@click.option('--compatible', help='Show versions compatible with specific language version')
@click.pass_context
def versions(ctx, language, available, compatible):
    """List available versions for a language."""
    # Implementation: List grammar versions

@grammar.command()
@click.argument('language')
@click.option('--version', '-v', help='Specific version to fetch')
@click.option('--force', '-f', is_flag=True, help='Force re-download if exists')
@click.option('--verify', is_flag=True, help='Verify grammar after download')
@click.pass_context
def fetch(ctx, language, version, force, verify):
    """Download specific grammar version."""
    # Implementation: Download and install grammar

@grammar.command()
@click.argument('language')
@click.option('--source', '-s', help='Custom source directory')
@click.option('--optimize', '-o', is_flag=True, help='Enable optimization flags')
@click.option('--parallel', '-p', is_flag=True, help='Enable parallel compilation')
@click.pass_context
def build(ctx, language, source, optimize, parallel):
    """Build grammar from source."""
    # Implementation: Build grammar from source

@grammar.command()
@click.argument('language')
@click.option('--version', '-v', help='Specific version to remove')
@click.option('--all-versions', '-a', is_flag=True, help='Remove all versions')
@click.option('--force', '-f', is_flag=True, help='Force removal without confirmation')
@click.pass_context
def remove(ctx, language, version, all_versions, force):
    """Remove user-installed grammar."""
    # Implementation: Remove grammar

@grammar.command()
@click.argument('language')
@click.argument('file', type=click.Path(exists=True))
@click.option('--grammar-version', '-g', help='Test specific grammar version')
@click.option('--output', '-o', type=click.Path(), help='Save test results to file')
@click.pass_context
def test(ctx, language, file, grammar_version, output):
    """Test grammar with specific file."""
    # Implementation: Test grammar with file

@grammar.command()
@click.argument('language')
@click.option('--comprehensive', '-c', is_flag=True, help='Run comprehensive validation')
@click.option('--fix', '-f', is_flag=True, help='Attempt to fix validation issues')
@click.pass_context
def validate(ctx, language, comprehensive, fix):
    """Validate grammar installation."""
    # Implementation: Validate grammar installation

# Helper functions for display and formatting
def _display_grammars_table(grammars):
    """Display grammars in table format."""
    # Implementation: Create formatted table display
    
def _display_grammars_yaml(grammars):
    """Display grammars in YAML format."""
    # Implementation: Create YAML formatted output
    
def _display_detailed_info(info):
    """Display detailed grammar information."""
    # Implementation: Show comprehensive grammar details
    
def _display_basic_info(info):
    """Display basic grammar information."""
    # Implementation: Show essential grammar details
    
def _display_versions(language, versions, available, compatible):
    """Display grammar versions."""
    # Implementation: Show version information
    
def _display_validation_results(validation):
    """Display validation results."""
    # Implementation: Show validation output
    
def _display_test_results(results):
    """Display test results."""
    # Implementation: Show test output
    
def _save_test_results(results, output_path):
    """Save test results to file."""
    # Implementation: Save results to specified file
```

### IMPLEMENTATION REQUIREMENTS:
1. **Implement all 8 CLI commands** with full functionality
2. **Integrate with Task 1.8.1** GrammarManager class
3. **Add comprehensive error handling** for CLI operations
4. **Include progress bars and user feedback** for long operations
5. **Create unit tests** covering all CLI commands
6. **Ensure no cross-file dependencies** within this task

---

## TASK 1.8.3: USER CONFIGURATION SYSTEM

**ASSIGNED FILE**: `chunker/grammar_management/config.py`
**SUB-AGENT**: Configuration System Specialist
**IMPLEMENTATION DEADLINE**: Complete within assigned timeframe
**DEPENDENCIES**: None (can start immediately)

### FILE STRUCTURE TO CREATE:
```python
# chunker/grammar_management/config.py

from typing import Dict, List, Optional, Any, Union
from pathlib import Path
import json
import logging
from datetime import datetime
import os
import shutil

logger = logging.getLogger(__name__)

class UserConfig:
    """Manages user configuration for grammar management."""
    
    def __init__(self, config_file: Optional[Path] = None):
        """Initialize user configuration."""
        self.config_file = config_file or self._get_default_config_file()
        self.config = self._load_config()
        self._validate_config()
    
    def _get_default_config_file(self) -> Path:
        """Get default configuration file path."""
        # Implementation: Return default config file path
        
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from file."""
        # Implementation: Load and parse configuration
        
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration."""
        # Implementation: Return default configuration values
        
    def _validate_config(self) -> None:
        """Validate configuration values."""
        # Implementation: Validate all configuration values
        
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value."""
        # Implementation: Retrieve nested configuration value
        
    def set(self, key: str, value: Any) -> None:
        """Set configuration value."""
        # Implementation: Set nested configuration value
        
    def save(self) -> None:
        """Save configuration to file."""
        # Implementation: Persist configuration changes
        
    def reset_to_defaults(self) -> None:
        """Reset configuration to defaults."""
        # Implementation: Restore default configuration

class DirectoryManager:
    """Manages user grammar directory structure."""
    
    def __init__(self, base_dir: Path):
        """Initialize directory manager."""
        self.base_dir = base_dir
        self.grammars_dir = base_dir / "grammars"
        self.cache_dir = base_dir / "cache"
        self.logs_dir = base_dir / "logs"
        self._setup_directories()
    
    def _setup_directories(self) -> None:
        """Create necessary directory structure."""
        # Implementation: Create all required directories
        
    def get_grammar_dir(self, language: str, version: str) -> Path:
        """Get directory for specific grammar version."""
        # Implementation: Return grammar-specific directory
        
    def cleanup_old_versions(self, language: str, keep_versions: int = 3) -> None:
        """Clean up old grammar versions."""
        # Implementation: Remove old versions, keep specified number
        
    def backup_configuration(self, backup_path: Path) -> bool:
        """Backup configuration and user grammars."""
        # Implementation: Create backup archive
        
    def restore_configuration(self, backup_path: Path) -> bool:
        """Restore configuration from backup."""
        # Implementation: Restore from backup archive

class CacheManager:
    """Manages caching for grammar management."""
    
    def __init__(self, cache_dir: Path, max_size_mb: int = 1024):
        """Initialize cache manager."""
        self.cache_dir = cache_dir
        self.max_size_mb = max_size_mb
        self.download_cache = cache_dir / "downloads"
        self.build_cache = cache_dir / "builds"
        self._setup_cache_directories()
    
    def _setup_cache_directories(self) -> None:
        """Create cache directory structure."""
        # Implementation: Create cache directories
        
    def get_cache_size(self) -> int:
        """Get current cache size in bytes."""
        # Implementation: Calculate total cache size
        
    def cleanup_cache(self, target_size_mb: Optional[int] = None) -> None:
        """Clean up cache to target size."""
        # Implementation: Remove old cache entries
        
    def get_cached_item(self, key: str) -> Optional[Path]:
        """Get cached item by key."""
        # Implementation: Retrieve cached item
        
    def cache_item(self, key: str, item_path: Path) -> bool:
        """Cache item with key."""
        # Implementation: Store item in cache
        
    def invalidate_cache(self, key: str) -> None:
        """Invalidate cached item."""
        # Implementation: Remove specific cache entry

class ConfigurationCLI:
    """CLI commands for configuration management."""
    
    def __init__(self, config: UserConfig):
        """Initialize configuration CLI."""
        self.config = config
    
    def show_config(self, key: Optional[str] = None) -> None:
        """Show configuration values."""
        # Implementation: Display configuration
        
    def edit_config(self, key: str, value: Any) -> None:
        """Edit configuration value."""
        # Implementation: Update configuration
        
    def reset_config(self, key: Optional[str] = None) -> None:
        """Reset configuration to defaults."""
        # Implementation: Reset configuration
        
    def export_config(self, output_path: Path) -> None:
        """Export configuration to file."""
        # Implementation: Export configuration
        
    def import_config(self, input_path: Path) -> None:
        """Import configuration from file."""
        # Implementation: Import configuration
```

### IMPLEMENTATION REQUIREMENTS:
1. **Complete all classes and methods** with full implementation
2. **Add comprehensive type hints** for all functions
3. **Include detailed docstrings** explaining each method
4. **Handle edge cases** and error conditions gracefully
5. **Add logging** for debugging and monitoring
6. **Create unit tests** covering all methods
7. **Ensure no cross-file dependencies** within this task

---

## TASK 1.8.4: GRAMMAR COMPATIBILITY ENGINE

**ASSIGNED FILE**: `chunker/grammar_management/compatibility.py`
**SUB-AGENT**: Compatibility Engine Specialist
**IMPLEMENTATION DEADLINE**: Complete within assigned timeframe
**DEPENDENCIES**: Task 1.8.1 (Grammar Management Core) must be complete

### FILE STRUCTURE TO CREATE:
```python
# chunker/grammar_management/compatibility.py

from typing import Dict, List, Optional, Any, Union, Tuple
from pathlib import Path
import logging
from datetime import datetime
import sqlite3
import json

# Import from Task 1.8.1
from .core import GrammarManager

logger = logging.getLogger(__name__)

class CompatibilityChecker:
    """Checks grammar compatibility with language versions."""
    
    def __init__(self, grammar_manager: GrammarManager):
        """Initialize compatibility checker."""
        self.grammar_manager = grammar_manager
        self.compatibility_db = CompatibilityDatabase()
    
    def check_compatibility(self, language: str, grammar_version: str, 
                           language_version: str) -> Dict[str, Any]:
        """Check compatibility between grammar and language version."""
        # Implementation: Comprehensive compatibility checking
        
    def detect_breaking_changes(self, language: str, old_version: str, 
                               new_version: str) -> List[Dict[str, Any]]:
        """Detect breaking changes between grammar versions."""
        # Implementation: Identify breaking changes
        
    def get_compatibility_matrix(self, language: str) -> Dict[str, List[str]]:
        """Get compatibility matrix for language."""
        # Implementation: Return compatibility data
        
    def suggest_grammar_version(self, language: str, language_version: str) -> Optional[str]:
        """Suggest optimal grammar version for language version."""
        # Implementation: Recommend best grammar version

class GrammarTester:
    """Tests grammar functionality and performance."""
    
    def __init__(self, test_samples_dir: Optional[Path] = None):
        """Initialize grammar tester."""
        self.test_samples_dir = test_samples_dir or self._get_default_test_dir()
        self.test_results = {}
    
    def _get_default_test_dir(self) -> Path:
        """Get default test samples directory."""
        # Implementation: Return default test directory
        
    def test_grammar(self, grammar_path: Path, language: str, 
                     test_files: Optional[List[Path]] = None) -> Dict[str, Any]:
        """Test grammar with sample files."""
        # Implementation: Comprehensive grammar testing
        
    def benchmark_performance(self, grammar_path: Path, language: str) -> Dict[str, Any]:
        """Benchmark grammar performance."""
        # Implementation: Performance testing
        
    def detect_error_patterns(self, grammar_path: Path, language: str) -> List[Dict[str, Any]]:
        """Detect common error patterns."""
        # Implementation: Error pattern analysis
        
    def validate_syntax_support(self, grammar_path: Path, language: str, 
                               features: List[str]) -> Dict[str, bool]:
        """Validate syntax feature support."""
        # Implementation: Feature validation

class SmartSelector:
    """Implements smart grammar selection algorithms."""
    
    def __init__(self, grammar_manager: GrammarManager, 
                 compatibility_checker: CompatibilityChecker):
        """Initialize smart selector."""
        self.grammar_manager = grammar_manager
        self.compatibility_checker = compatibility_checker
        self.selection_cache = {}
    
    def select_grammar(self, language: str, language_version: str, 
                       user_preferences: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """Select optimal grammar based on criteria."""
        # Implementation: Smart selection algorithm
        
    def get_grammar_priority(self, grammar: Dict[str, Any], language_version: str) -> float:
        """Calculate grammar priority score."""
        # Implementation: Priority scoring
        
    def resolve_conflicts(self, language: str, candidates: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Resolve conflicts between grammar candidates."""
        # Implementation: Conflict resolution
        
    def suggest_upgrade(self, language: str, current_version: str) -> Optional[Dict[str, Any]]:
        """Suggest grammar upgrade if available."""
        # Implementation: Upgrade recommendations

class CompatibilityDatabase:
    """Persistent storage for compatibility data."""
    
    def __init__(self, db_path: Optional[Path] = None):
        """Initialize compatibility database."""
        self.db_path = db_path or self._get_default_db_path()
        self._setup_database()
    
    def _get_default_db_path(self) -> Path:
        """Get default database path."""
        # Implementation: Return default database path
        
    def _setup_database(self) -> None:
        """Setup database schema."""
        # Implementation: Create database tables
        
    def store_compatibility_data(self, language: str, grammar_version: str, 
                                language_version: str, compatibility_data: Dict[str, Any]) -> None:
        """Store compatibility data."""
        # Implementation: Store compatibility information
        
    def get_compatibility_data(self, language: str, grammar_version: str, 
                              language_version: str) -> Optional[Dict[str, Any]]:
        """Get compatibility data."""
        # Implementation: Retrieve compatibility information
        
    def update_compatibility_matrix(self, language: str, matrix: Dict[str, List[str]]) -> None:
        """Update compatibility matrix."""
        # Implementation: Update compatibility data
        
    def get_compatibility_history(self, language: str) -> List[Dict[str, Any]]:
        """Get compatibility change history."""
        # Implementation: Retrieve historical data
```

### IMPLEMENTATION REQUIREMENTS:
1. **Complete all classes and methods** with full implementation
2. **Integrate with Task 1.8.1** GrammarManager class
3. **Add comprehensive type hints** for all functions
4. **Include detailed docstrings** explaining each method
5. **Handle edge cases** and error conditions gracefully
6. **Add logging** for debugging and monitoring
7. **Create unit tests** covering all methods
8. **Ensure no cross-file dependencies** within this task

---

## TASK 1.8.5: INTEGRATION & TESTING

**ASSIGNED FILE**: `chunker/grammar_management/testing.py`
**SUB-AGENT**: Integration Testing Specialist
**IMPLEMENTATION DEADLINE**: Complete within assigned timeframe
**DEPENDENCIES**: All other tasks (1.8.1, 1.8.2, 1.8.3, 1.8.4) must be complete

### FILE STRUCTURE TO CREATE:
```python
# chunker/grammar_management/testing.py

from typing import Dict, List, Optional, Any, Union, Tuple
from pathlib import Path
import logging
import time
import json
from datetime import datetime

# Import from all other tasks
from .core import GrammarManager
from .cli import grammar
from .config import UserConfig, DirectoryManager, CacheManager
from .compatibility import CompatibilityChecker, GrammarTester, SmartSelector

logger = logging.getLogger(__name__)

class IntegrationTester:
    """Tests complete grammar management system integration."""
    
    def __init__(self):
        """Initialize integration tester."""
        self.test_results = {}
        self.performance_metrics = {}
    
    def test_complete_workflow(self) -> Dict[str, Any]:
        """Test complete grammar management workflow."""
        # Implementation: End-to-end workflow testing
        
    def test_cross_component_integration(self) -> Dict[str, Any]:
        """Test integration between all components."""
        # Implementation: Cross-component testing
        
    def test_error_scenarios(self) -> Dict[str, Any]:
        """Test error handling and recovery."""
        # Implementation: Error scenario testing
        
    def test_performance_under_load(self) -> Dict[str, Any]:
        """Test system performance under load."""
        # Implementation: Load testing

class CLIValidator:
    """Validates CLI functionality and user experience."""
    
    def __init__(self):
        """Initialize CLI validator."""
        self.test_results = {}
    
    def test_all_commands(self) -> Dict[str, Any]:
        """Test all CLI commands."""
        # Implementation: Command testing
        
    def test_user_experience(self) -> Dict[str, Any]:
        """Test user experience workflows."""
        # Implementation: UX testing
        
    def test_error_handling(self) -> Dict[str, Any]:
        """Test CLI error handling."""
        # Implementation: Error handling testing
        
    def test_help_and_documentation(self) -> Dict[str, Any]:
        """Test help system and documentation."""
        # Implementation: Help system testing

class SystemValidator:
    """Validates system health and stability."""
    
    def __init__(self):
        """Initialize system validator."""
        self.health_metrics = {}
    
    def check_system_health(self) -> Dict[str, Any]:
        """Check overall system health."""
        # Implementation: Health checking
        
    def monitor_resource_usage(self) -> Dict[str, Any]:
        """Monitor system resource usage."""
        # Implementation: Resource monitoring
        
    def test_stability(self, duration_minutes: int = 30) -> Dict[str, Any]:
        """Test system stability over time."""
        # Implementation: Stability testing
        
    def validate_configuration(self) -> Dict[str, Any]:
        """Validate system configuration."""
        # Implementation: Configuration validation

class PerformanceBenchmark:
    """Benchmarks system performance and scalability."""
    
    def __init__(self):
        """Initialize performance benchmark."""
        self.benchmark_results = {}
    
    def benchmark_grammar_operations(self) -> Dict[str, Any]:
        """Benchmark grammar management operations."""
        # Implementation: Operation benchmarking
        
    def test_scalability(self, max_grammars: int = 100) -> Dict[str, Any]:
        """Test system scalability."""
        # Implementation: Scalability testing
        
    def optimize_performance(self) -> Dict[str, Any]:
        """Identify and apply performance optimizations."""
        # Implementation: Performance optimization
        
    def generate_performance_report(self) -> str:
        """Generate comprehensive performance report."""
        # Implementation: Report generation

def run_complete_test_suite() -> Dict[str, Any]:
    """Run complete test suite for grammar management system."""
    # Implementation: Run all tests and generate report
```

### IMPLEMENTATION REQUIREMENTS:
1. **Complete all classes and methods** with full implementation
2. **Integrate with all other tasks** (import all components)
3. **Add comprehensive type hints** for all functions
4. **Include detailed docstrings** explaining each method
5. **Handle edge cases** and error conditions gracefully
6. **Add logging** for debugging and monitoring
7. **Create unit tests** covering all methods
8. **Ensure comprehensive testing** of the complete system

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
8. **CREATE UNIT TESTS** with 90%+ coverage
9. **FOLLOW PYTHON CODING STANDARDS** (PEP 8, type hints, etc.)
10. **ENSURE PRODUCTION-READY CODE** - no prototypes or stubs

### EXECUTION ORDER:

**IMPORTANT**: These tasks have specific dependencies:

1. **Tasks 1.8.1, 1.8.3, 1.8.4**: Can start immediately (no dependencies)
2. **Task 1.8.2**: Must wait for Task 1.8.1 completion
3. **Task 1.8.5**: Must wait for ALL other tasks completion

### SUB-AGENT PROMPT TEMPLATE:

```
You are assigned to implement [TASK_NAME] for Phase 1.8.

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
- Maintain production-ready code quality

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

1. **EXECUTE PARALLEL TASKS FIRST**: Start Tasks 1.8.1, 1.8.3, 1.8.4 simultaneously
2. **WAIT FOR CORE COMPLETION**: Ensure Task 1.8.1 is complete before starting 1.8.2
3. **EXECUTE DEPENDENT TASKS**: Start 1.8.2 after 1.8.1 completion
4. **EXECUTE INTEGRATION TASK**: Start 1.8.5 after all other tasks complete
5. **COLLECT RESULTS**: Gather completed implementations from each sub-agent
6. **VALIDATE COMPLETION**: Ensure all tasks are fully implemented
7. **VERIFY PHASE 1.8 READINESS**: Confirm system is ready for production
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
- ✅ Production-ready quality achieved

### FINAL REPORT FORMAT:

```
PHASE 1.8 COMPLETION REPORT
===========================

TASK 1.8.1 (Grammar Management Core): [STATUS] - [SUB-AGENT NAME]
- File: chunker/grammar_management/core.py
- Methods implemented: [LIST]
- Test coverage: [PERCENTAGE]
- Production readiness: [STATUS]
- Issues/notes: [ANY]

TASK 1.8.2 (CLI Interface): [STATUS] - [SUB-AGENT NAME]
- File: chunker/grammar_management/cli.py
- Methods implemented: [LIST]
- Test coverage: [PERCENTAGE]
- CLI commands implemented: [LIST]
- Production readiness: [STATUS]
- Issues/notes: [ANY]

TASK 1.8.3 (User Configuration System): [STATUS] - [SUB-AGENT NAME]
- File: chunker/grammar_management/config.py
- Methods implemented: [LIST]
- Test coverage: [PERCENTAGE]
- Configuration features: [LIST]
- Production readiness: [STATUS]
- Issues/notes: [ANY]

TASK 1.8.4 (Grammar Compatibility Engine): [STATUS] - [SUB-AGENT NAME]
- File: chunker/grammar_management/compatibility.py
- Methods implemented: [LIST]
- Test coverage: [PERCENTAGE]
- Compatibility features: [LIST]
- Production readiness: [STATUS]
- Issues/notes: [ANY]

TASK 1.8.5 (Integration & Testing): [STATUS] - [SUB-AGENT NAME]
- File: chunker/grammar_management/testing.py
- Methods implemented: [LIST]
- Test coverage: [PERCENTAGE]
- Integration tests: [LIST]
- Performance metrics: [STATUS]
- Issues/notes: [ANY]

OVERALL STATUS: [COMPLETE/INCOMPLETE]
PHASE 1.8 READINESS: [READY/NOT READY]
NEXT STEPS: [PHASE 1.9 IMPLEMENTATION]
```

---

## IMPORTANT NOTES

### FILE BOUNDARIES:
- **EACH SUB-AGENT TOUCHES EXACTLY ONE FILE**
- **NO CROSS-FILE DEPENDENCIES** within individual tasks
- **ALL IMPORTS MUST BE STANDARD LIBRARY** or from completed tasks
- **NO NEW DEPENDENCIES** can be added

### DEPENDENCY MANAGEMENT:
- **1.8.1 (Core)**: No dependencies - can start immediately
- **1.8.3 (Config)**: No dependencies - can start immediately
- **1.8.4 (Compatibility)**: No dependencies - can start immediately
- **1.8.2 (CLI)**: Depends on Task 1.8.1 completion
- **1.8.5 (Testing)**: Depends on ALL other tasks completion

### QUALITY STANDARDS:
- **FULL IMPLEMENTATION** - no stubs or placeholders
- **PRODUCTION-READY CODE** - not prototype quality
- **COMPREHENSIVE TESTING** - 90%+ coverage required
- **ERROR HANDLING** - graceful degradation for all edge cases
- **LOGGING** - meaningful debug and info messages
- **PHASE 1.8 COMPLIANCE** - specification requirements met

### COORDINATION:
- **PARALLEL EXECUTION** - Tasks 1.8.1, 1.8.3, 1.8.4 can start simultaneously
- **DEPENDENCY VALIDATION** - ensure previous tasks complete before starting dependent tasks
- **MANAGER OVERSIGHT** - you coordinate and ensure proper execution order
- **QUALITY GATES** - validate completion before proceeding to dependent tasks
- **PRODUCTION READINESS** - confirm system meets all quality requirements

---

## EXECUTION COMMAND

**COPY AND PASTE THIS ENTIRE PROMPT** into your sub-agent manager system to begin execution of Phase 1.8 tasks.

**EXPECTED DURATION**: 1 week with parallel execution
**EXPECTED OUTCOME**: Complete Phase 1.8 system with CLI tools and grammar management
**NEXT PHASE**: Phase 1.9 (Production-ready error handling and integration)

## PHASE 1.8 READINESS VALIDATION

### FINAL VALIDATION CHECKLIST:

Before marking Phase 1.8 complete, verify:

1. **Grammar Management Core**: ✅ Fully functional and robust
2. **CLI Interface**: ✅ All 8 commands implemented and working
3. **User Configuration System**: ✅ Configuration management complete
4. **Grammar Compatibility Engine**: ✅ Compatibility checking functional
5. **Integration & Testing**: ✅ Complete system testing and validation
6. **Production Readiness**: ✅ System ready for production use
7. **Quality Standards**: ✅ 90%+ test coverage achieved
8. **User Experience**: ✅ CLI workflows intuitive and user-friendly

**START EXECUTION NOW** with Tasks 1.8.1, 1.8.3, and 1.8.4 in parallel, then proceed with 1.8.2 and 1.8.5 based on dependencies.

# PHASE 1.8 PARALLEL EXECUTION PLAN
# User Grammar Management & CLI Tools

## Overview

Phase 1.8 implements the user grammar management system with CLI tools, designed for parallel execution by 5 sub-agents working on isolated files. This phase provides users with comprehensive tools to manage their own grammar libraries and resolve compatibility issues.

## Parallel Execution Strategy

### **EXECUTION MODEL:**
- **5 Parallel Tasks**: Each sub-agent works on exactly one file
- **File Isolation**: No cross-file dependencies within individual tasks
- **Sequential Dependencies**: Some tasks must complete before others can start
- **Quality Assurance**: 90%+ test coverage and production-ready code required

### **DEPENDENCY CHAIN:**
```
Task 1.8.1 (Core) → Task 1.8.2 (CLI) → Task 1.8.5 (Testing)
Task 1.8.1 (Core) → Task 1.8.3 (Config) → Task 1.8.5 (Testing)
Task 1.8.1 (Core) → Task 1.8.4 (Compatibility) → Task 1.8.5 (Testing)
```

**Parallel Execution**: Tasks 1.8.1, 1.8.3, and 1.8.4 can start simultaneously
**Sequential Execution**: Task 1.8.2 depends on Task 1.8.1, Task 1.8.5 depends on all others

---

## TASK BREAKDOWN

### **TASK 1.8.1: GRAMMAR MANAGEMENT CORE**
**ASSIGNED FILE**: `chunker/grammar_management/core.py`
**SUB-AGENT**: Grammar Management Core Specialist
**DEPENDENCIES**: None (can start immediately)
**IMPLEMENTATION DEADLINE**: Complete within assigned timeframe

#### **OBJECTIVE:**
Implement the core grammar management engine that handles grammar discovery, installation, removal, and basic operations.

#### **KEY COMPONENTS TO IMPLEMENT:**

1. **GrammarManager Class**
   - Grammar discovery (package vs. user-installed)
   - Grammar installation and removal
   - Version management and conflict resolution
   - Grammar validation and health checking

2. **GrammarRegistry Class**
   - Grammar registration and lookup
   - Source tracking (package vs. user)
   - Version conflict detection
   - Priority-based selection

3. **GrammarInstaller Class**
   - Download management with progress tracking
   - Build system integration
   - Installation validation
   - Rollback capabilities

4. **GrammarValidator Class**
   - Integrity checking
   - Compatibility validation
   - Performance testing
   - Health monitoring

#### **FILE STRUCTURE:**
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
    
    def discover_grammars(self) -> Dict[str, List[Dict[str, Any]]]:
        """Discover all available grammars from package and user directories."""
        # Implementation: Scan both directories and build registry
        
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

#### **IMPLEMENTATION REQUIREMENTS:**
1. **Complete all classes and methods** with full implementation
2. **Add comprehensive type hints** for all functions
3. **Include detailed docstrings** explaining each method
4. **Handle edge cases** and error conditions gracefully
5. **Add logging** for debugging and monitoring
6. **Create unit tests** covering all methods
7. **Ensure no cross-file dependencies** within this task

---

### **TASK 1.8.2: CLI INTERFACE**
**ASSIGNED FILE**: `chunker/grammar_management/cli.py`
**SUB-AGENT**: CLI Interface Specialist
**DEPENDENCIES**: Task 1.8.1 (Grammar Management Core) must be complete
**IMPLEMENTATION DEADLINE**: Complete within assigned timeframe

#### **OBJECTIVE:**
Implement the Click-based CLI interface with all 8 grammar management commands.

#### **KEY COMPONENTS TO IMPLEMENT:**

1. **Main CLI Group**
   - Grammar command group with options
   - Verbose logging and configuration support
   - Error handling and user feedback

2. **Grammar Discovery Commands**
   - `chunker grammar list` - Show available grammars
   - `chunker grammar info <language>` - Show grammar details
   - `chunker grammar versions <language>` - List versions

3. **Grammar Management Commands**
   - `chunker grammar fetch <language>[@version]` - Download grammar
   - `chunker grammar build <language>` - Build from source
   - `chunker grammar remove <language>` - Remove grammar

4. **Grammar Testing Commands**
   - `chunker grammar test <language> <file>` - Test grammar
   - `chunker grammar validate <language>` - Validate installation

#### **FILE STRUCTURE:**
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
    manager = ctx.obj
    grammars = manager.discover_grammars()
    
    # Filter based on options
    if user_only:
        grammars = {k: v for k, v in grammars.items() if any(g['source'] == 'user' for g in v)}
    elif package_only:
        grammars = {k: v for k, v in grammars.items() if any(g['source'] == 'package' for g in v)}
    
    # Display in specified format
    if format == 'table':
        _display_grammars_table(grammars)
    elif format == 'json':
        click.echo(json.dumps(grammars, indent=2))
    elif format == 'yaml':
        _display_grammars_yaml(grammars)

@grammar.command()
@click.argument('language')
@click.option('--version', '-v', help='Specific version to show info for')
@click.option('--detailed', '-d', is_flag=True, help='Show detailed compatibility info')
@click.pass_context
def info(ctx, language, version, detailed):
    """Show grammar details and compatibility information."""
    manager = ctx.obj
    info = manager.get_grammar_info(language, version)
    
    if not info:
        click.echo(f"No grammar found for {language}")
        return
    
    if detailed:
        _display_detailed_info(info)
    else:
        _display_basic_info(info)

@grammar.command()
@click.argument('language')
@click.option('--available', is_flag=True, help='Show only available versions')
@click.option('--compatible', help='Show versions compatible with specific language version')
@click.pass_context
def versions(ctx, language, available, compatible):
    """List available versions for a language."""
    manager = ctx.obj
    versions = manager.get_grammar_versions(language)
    
    if not versions:
        click.echo(f"No versions found for {language}")
        return
    
    _display_versions(language, versions, available, compatible)

@grammar.command()
@click.argument('language')
@click.option('--version', '-v', help='Specific version to fetch')
@click.option('--force', '-f', is_flag=True, help='Force re-download if exists')
@click.option('--verify', is_flag=True, help='Verify grammar after download')
@click.pass_context
def fetch(ctx, language, version, force, verify):
    """Download specific grammar version."""
    manager = ctx.obj
    
    with click.progressbar(length=100, label=f'Fetching {language} grammar') as bar:
        try:
            success = manager.install_grammar(language, version, source="official")
            if success:
                click.echo(f"Successfully installed {language} grammar")
                if verify:
                    click.echo("Verifying installation...")
                    validation = manager.validate_grammar(language, version)
                    _display_validation_results(validation)
            else:
                click.echo(f"Failed to install {language} grammar")
        except Exception as e:
            click.echo(f"Error installing {language} grammar: {e}")

@grammar.command()
@click.argument('language')
@click.option('--source', '-s', help='Custom source directory')
@click.option('--optimize', '-o', is_flag=True, help='Enable optimization flags')
@click.option('--parallel', '-p', is_flag=True, help='Enable parallel compilation')
@click.pass_context
def build(ctx, language, source, optimize, parallel):
    """Build grammar from source."""
    manager = ctx.obj
    
    click.echo(f"Building {language} grammar from source...")
    try:
        success = manager.install_grammar(language, source="source", 
                                        source_path=source, optimize=optimize, 
                                        parallel=parallel)
        if success:
            click.echo(f"Successfully built {language} grammar")
        else:
            click.echo(f"Failed to build {language} grammar")
    except Exception as e:
        click.echo(f"Error building {language} grammar: {e}")

@grammar.command()
@click.argument('language')
@click.option('--version', '-v', help='Specific version to remove')
@click.option('--all-versions', '-a', is_flag=True, help='Remove all versions')
@click.option('--force', '-f', is_flag=True, help='Force removal without confirmation')
@click.pass_context
def remove(ctx, language, version, all_versions, force):
    """Remove user-installed grammar."""
    manager = ctx.obj
    
    if not force:
        if not click.confirm(f"Are you sure you want to remove {language} grammar?"):
            return
    
    try:
        if all_versions:
            success = manager.remove_all_grammars(language)
            if success:
                click.echo(f"Removed all versions of {language} grammar")
            else:
                click.echo(f"Failed to remove all versions of {language} grammar")
        else:
            success = manager.remove_grammar(language, version)
            if success:
                click.echo(f"Removed {language} grammar")
            else:
                click.echo(f"Failed to remove {language} grammar")
    except Exception as e:
        click.echo(f"Error removing {language} grammar: {e}")

@grammar.command()
@click.argument('language')
@click.argument('file', type=click.Path(exists=True))
@click.option('--grammar-version', '-g', help='Test specific grammar version')
@click.option('--output', '-o', type=click.Path(), help='Save test results to file')
@click.pass_context
def test(ctx, language, file, grammar_version, output):
    """Test grammar with specific file."""
    manager = ctx.obj
    
    click.echo(f"Testing {language} grammar with {file}...")
    try:
        results = manager.test_grammar(language, file, grammar_version)
        _display_test_results(results)
        
        if output:
            _save_test_results(results, output)
            click.echo(f"Test results saved to {output}")
    except Exception as e:
        click.echo(f"Error testing {language} grammar: {e}")

@grammar.command()
@click.argument('language')
@click.option('--comprehensive', '-c', is_flag=True, help='Run comprehensive validation')
@click.option('--fix', '-f', is_flag=True, help='Attempt to fix validation issues')
@click.pass_context
def validate(ctx, language, comprehensive, fix):
    """Validate grammar installation."""
    manager = ctx.obj
    
    click.echo(f"Validating {language} grammar...")
    try:
        validation = manager.validate_grammar(language, comprehensive=comprehensive)
        _display_validation_results(validation)
        
        if fix and validation.get('issues'):
            click.echo("Attempting to fix issues...")
            fixed = manager.fix_grammar_issues(language, validation['issues'])
            if fixed:
                click.echo("Issues fixed successfully")
            else:
                click.echo("Some issues could not be fixed automatically")
    except Exception as e:
        click.echo(f"Error validating {language} grammar: {e}")

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

#### **IMPLEMENTATION REQUIREMENTS:**
1. **Implement all 8 CLI commands** with full functionality
2. **Integrate with Task 1.8.1** GrammarManager class
3. **Add comprehensive error handling** for CLI operations
4. **Include progress bars and user feedback** for long operations
5. **Create unit tests** covering all CLI commands
6. **Ensure no cross-file dependencies** within this task

---

### **TASK 1.8.3: USER CONFIGURATION SYSTEM**
**ASSIGNED FILE**: `chunker/grammar_management/config.py`
**SUB-AGENT**: Configuration System Specialist
**DEPENDENCIES**: None (can start immediately)
**IMPLEMENTATION DEADLINE**: Complete within assigned timeframe

#### **OBJECTIVE:**
Implement the user configuration system for grammar management preferences, directory management, and caching.

#### **KEY COMPONENTS TO IMPLEMENT:**

1. **UserConfig Class**
   - User preferences and settings
   - Configuration validation and defaults
   - Environment variable support

2. **DirectoryManager Class**
   - User grammar directory structure
   - Cache management and cleanup
   - Backup and restore functionality

3. **CacheManager Class**
   - Download and build cache management
   - Cache size limits and cleanup
   - Performance optimization

4. **ConfigurationCLI Class**
   - CLI commands for configuration management
   - Configuration editing and validation
   - Import/export functionality

#### **FILE STRUCTURE:**
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
        config_dir = Path.home() / ".cache" / "treesitter-chunker"
        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir / "config.json"
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from file."""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                logger.info(f"Configuration loaded from {self.config_file}")
                return config
            except Exception as e:
                logger.warning(f"Failed to load config: {e}, using defaults")
        
        return self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration."""
        return {
            "grammar_management": {
                "user_grammar_directory": str(Path.home() / ".cache" / "treesitter-chunker" / "grammars"),
                "cache_directory": str(Path.home() / ".cache" / "treesitter-chunker" / "cache"),
                "log_directory": str(Path.home() / ".cache" / "treesitter-chunker" / "logs"),
                "max_cache_size_mb": 1024,
                "auto_cleanup": True,
                "cleanup_interval_hours": 24
            },
            "grammar_selection": {
                "priority_order": ["user_specific", "user_compatible", "package_latest", "package_compatible"],
                "fallback_strategy": "graceful",
                "compatibility_threshold": "compatible",
                "auto_upgrade": False,
                "preferred_sources": ["official", "community", "user"]
            },
            "installation": {
                "verify_downloads": True,
                "auto_test_after_install": True,
                "parallel_downloads": 3,
                "timeout_seconds": 300,
                "retry_attempts": 3
            },
            "performance": {
                "enable_caching": True,
                "cache_ttl_hours": 168,
                "max_cached_grammars": 50,
                "memory_limit_mb": 512
            }
        }
    
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

#### **IMPLEMENTATION REQUIREMENTS:**
1. **Complete all classes and methods** with full implementation
2. **Add comprehensive type hints** for all functions
3. **Include detailed docstrings** explaining each method
4. **Handle edge cases** and error conditions gracefully
5. **Add logging** for debugging and monitoring
6. **Create unit tests** covering all methods
7. **Ensure no cross-file dependencies** within this task

---

### **TASK 1.8.4: GRAMMAR COMPATIBILITY ENGINE**
**ASSIGNED FILE**: `chunker/grammar_management/compatibility.py`
**SUB-AGENT**: Compatibility Engine Specialist
**DEPENDENCIES**: Task 1.8.1 (Grammar Management Core) must be complete
**IMPLEMENTATION DEADLINE**: Complete within assigned timeframe

#### **OBJECTIVE:**
Implement the grammar compatibility engine for version compatibility checking, testing, and smart selection.

#### **KEY COMPONENTS TO IMPLEMENT:**

1. **CompatibilityChecker Class**
   - Version compatibility validation
   - Language feature detection
   - Breaking change identification

2. **GrammarTester Class**
   - Grammar testing with sample code
   - Performance benchmarking
   - Error pattern detection

3. **SmartSelector Class**
   - Priority-based grammar selection
   - Fallback strategy implementation
   - Conflict resolution

4. **CompatibilityDatabase Class**
   - Compatibility data persistence
   - Version mapping storage
   - Historical compatibility tracking

#### **FILE STRUCTURE:**
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

#### **IMPLEMENTATION REQUIREMENTS:**
1. **Complete all classes and methods** with full implementation
2. **Integrate with Task 1.8.1** GrammarManager class
3. **Add comprehensive type hints** for all functions
4. **Include detailed docstrings** explaining each method
5. **Handle edge cases** and error conditions gracefully
6. **Add logging** for debugging and monitoring
7. **Create unit tests** covering all methods
8. **Ensure no cross-file dependencies** within this task

---

### **TASK 1.8.5: INTEGRATION & TESTING**
**ASSIGNED FILE**: `chunker/grammar_management/testing.py`
**SUB-AGENT**: Integration Testing Specialist
**DEPENDENCIES**: All other tasks (1.8.1, 1.8.2, 1.8.3, 1.8.4) must be complete
**IMPLEMENTATION DEADLINE**: Complete within assigned timeframe

#### **OBJECTIVE:**
Implement comprehensive testing and integration for the complete grammar management system.

#### **KEY COMPONENTS TO IMPLEMENT:**

1. **IntegrationTester Class**
   - End-to-end workflow testing
   - Cross-component integration testing
   - Performance validation

2. **CLIValidator Class**
   - CLI command validation
   - User experience testing
   - Error handling validation

3. **SystemValidator Class**
   - System health checking
   - Resource usage monitoring
   - Stability testing

4. **PerformanceBenchmark Class**
   - Performance benchmarking
   - Scalability testing
   - Resource optimization

#### **FILE STRUCTURE:**
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

#### **IMPLEMENTATION REQUIREMENTS:**
1. **Complete all classes and methods** with full implementation
2. **Integrate with all other tasks** (import all components)
3. **Add comprehensive type hints** for all functions
4. **Include detailed docstrings** explaining each method
5. **Handle edge cases** and error conditions gracefully
6. **Add logging** for debugging and monitoring
7. **Create unit tests** covering all methods
8. **Ensure comprehensive testing** of the complete system

---

## IMPLEMENTATION STRATEGY

### **1. PARALLEL EXECUTION APPROACH**
- **Tasks 1.8.1, 1.8.3, 1.8.4**: Can start simultaneously (no dependencies)
- **Task 1.8.2**: Must wait for Task 1.8.1 completion
- **Task 1.8.5**: Must wait for all other tasks completion

### **2. QUALITY ASSURANCE**
- **90%+ Test Coverage**: All tasks must achieve high test coverage
- **Production-Ready Code**: No prototypes or incomplete implementations
- **Comprehensive Error Handling**: Graceful degradation for all edge cases
- **Performance Optimization**: Efficient algorithms and resource management

### **3. INTEGRATION POINTS**
- **Task 1.8.1**: Provides core functionality for all other tasks
- **Task 1.8.2**: Integrates with core for CLI operations
- **Task 1.8.3**: Provides configuration for all components
- **Task 1.8.4**: Integrates with core for compatibility checking
- **Task 1.8.5**: Tests complete system integration

### **4. DEPENDENCY MANAGEMENT**
- **Clear Dependencies**: Each task has explicit dependency requirements
- **Validation Gates**: Dependencies must be validated before starting dependent tasks
- **Rollback Capability**: Failed tasks can be rolled back without affecting others
- **Progress Tracking**: Clear visibility into task completion status

---

## SUCCESS CRITERIA

### **FUNCTIONAL REQUIREMENTS**
- ✅ All 8 CLI commands implemented and functional
- ✅ User grammar directory structure working
- ✅ Smart grammar selection algorithms operational
- ✅ Grammar compatibility testing functional
- ✅ Configuration management system complete

### **QUALITY REQUIREMENTS**
- ✅ 90%+ test coverage for all components
- ✅ Production-ready code with comprehensive error handling
- ✅ Performance benchmarks met (<30s installation, <100ms selection)
- ✅ User experience workflows validated and intuitive

### **INTEGRATION REQUIREMENTS**
- ✅ All components work together seamlessly
- ✅ Error handling integrates with Phase 1.7 system
- ✅ CLI integrates with existing chunker functionality
- ✅ Configuration system provides user customization

---

## TIMELINE

### **WEEK 1: Core Implementation**
- **Days 1-2**: Tasks 1.8.1, 1.8.3, 1.8.4 (parallel execution)
- **Days 3-4**: Task 1.8.2 (after 1.8.1 completion)
- **Day 5**: Task 1.8.5 (after all other tasks completion)

### **EXPECTED OUTCOME**
- **Complete Phase 1.8 system** with all components working
- **Ready for Phase 1.9** (Production-ready error handling)
- **Foundation for Phase 2** (Language-specific extractors)
- **Production-ready grammar management** for users

---

## CONCLUSION

**Phase 1.8 Parallel Execution Plan is now complete!** 🎉

### **What We've Accomplished:**
1. **✅ Complete Task Breakdown**: 5 parallel tasks with clear objectives
2. **✅ File Isolation Strategy**: Each task works on exactly one file
3. **✅ Dependency Mapping**: Clear dependency relationships defined
4. **✅ Implementation Specifications**: Detailed file structures and requirements
5. **✅ Quality Assurance Framework**: 90%+ test coverage and production-ready code
6. **✅ Timeline Planning**: Realistic 1-week implementation schedule

### **Ready for Execution:**
- **Immediate Launch**: Can begin as soon as Group E completes
- **Parallel Execution**: 5 sub-agents working simultaneously
- **Clear Dependencies**: Sequential execution where required
- **Quality Standards**: Production-ready code requirements defined

**Phase 1.8 will provide users with powerful, intuitive grammar management tools that integrate seamlessly with the Phase 1.7 error handling system! 🚀**

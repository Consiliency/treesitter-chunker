"""Comprehensive grammar management CLI for Phase 1.8 alignment.

This module implements the complete CLI grammar management system with comprehensive
error handling integration, user guidance, and Phase 1.8 specification compliance.

Key Features:
- All CLI commands: list, info, versions, fetch, build, remove, test, validate
- Integration with error handling pipeline from Task E1
- Support for ~/.cache/treesitter-chunker/grammars/ directory
- User-installed → package → fallback priority for grammar selection
- Comprehensive error handling with clear user guidance
- Progress indicators for long operations
- Verbose mode for debugging

Phase 1.8 Compliance:
- Directory structure: ~/.cache/treesitter-chunker/grammars/
- Grammar selection priority order
- All specified CLI commands with exact signatures
- Error handling for all failure scenarios

Integration with Task E1:
- Uses ErrorHandlingPipeline for comprehensive error processing
- Uses ErrorHandlingOrchestrator for session management
- Uses CLIErrorIntegration for CLI-specific error handling
- Provides intelligent error guidance and troubleshooting
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from urllib.parse import urlparse
from urllib.request import urlopen, urlretrieve

import click

# Import error handling components from Task E1
try:
    from ..error_handling.integration import (
        CLIErrorIntegration,
        ErrorHandlingOrchestrator,
        ErrorHandlingPipeline,
        create_error_handling_system,
        get_system_health_report,
    )

    ERROR_HANDLING_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Error handling integration not available: {e}")
    ERROR_HANDLING_AVAILABLE = False

    # Create stub classes for graceful fallback
    class ErrorHandlingPipeline:
        def __init__(self, **kwargs):
            pass

        def process_error(self, *args, **kwargs):
            return {"success": False}

    class ErrorHandlingOrchestrator:
        def __init__(self, *args, **kwargs):
            pass

        def create_session(self, *args, **kwargs):
            return None

        def close_session(self, *args):
            return True

    class CLIErrorIntegration:
        def __init__(self, *args):
            pass

        def handle_grammar_validation_error(self, *args, **kwargs):
            return {"success": False, "guidance": [], "quick_fixes": []}

        def handle_grammar_download_error(self, *args, **kwargs):
            return {"success": False, "guidance": [], "troubleshooting_steps": []}


# Import grammar management components from core
try:
    from .core import (
        GrammarInstallationError,
        GrammarInstaller,
        GrammarManagementError,
        GrammarManager,
        GrammarPriority,
        GrammarRegistry,
        GrammarValidationError,
        GrammarValidator,
        InstallationInfo,
        ValidationLevel,
        ValidationResult,
    )

    GRAMMAR_COMPONENTS_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Grammar core components not available: {e}")
    GRAMMAR_COMPONENTS_AVAILABLE = False

    # Create stub classes for graceful fallback
    class GrammarManager:
        def __init__(self, **kwargs):
            pass

        def discover_available_grammars(self):
            return {}

        def install_grammar(self, *args, **kwargs):
            return False, "GrammarManager not available"

        def remove_grammar(self, *args, **kwargs):
            return False, "GrammarManager not available"

        def validate_grammar(self, *args, **kwargs):
            return None

    class ValidationLevel:
        BASIC = "basic"
        STANDARD = "standard"
        EXTENSIVE = "extensive"


# Import optional compatibility components
try:
    from .compatibility import CompatibilityManager

    COMPATIBILITY_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Compatibility components not available: {e}")
    COMPATIBILITY_AVAILABLE = False

logger = logging.getLogger(__name__)


# Use GrammarPriority from core if available, otherwise define fallback
if not GRAMMAR_COMPONENTS_AVAILABLE:

    class GrammarPriority:
        """Grammar selection priority levels (fallback)."""

        USER = 1
        PACKAGE = 2
        FALLBACK = 3


class GrammarStatus:
    """Grammar status indicators."""

    HEALTHY = "healthy"
    MISSING = "missing"
    CORRUPTED = "corrupted"
    INCOMPATIBLE = "incompatible"
    BUILDING = "building"
    DOWNLOADING = "downloading"
    UNKNOWN = "unknown"


class ProgressIndicator:
    """Progress indicator for long-running operations."""

    def __init__(self, description: str, verbose: bool = False):
        """Initialize progress indicator.

        Args:
            description: Description of the operation
            verbose: Whether to show verbose output
        """
        self.description = description
        self.verbose = verbose
        self.start_time = time.time()
        self.spinner_chars = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
        self.spinner_index = 0
        self.running = False
        self.thread = None

    def start(self) -> None:
        """Start the progress indicator."""
        if self.verbose:
            click.echo(f"Starting: {self.description}")
        else:
            self.running = True
            self.thread = threading.Thread(target=self._spin, daemon=True)
            self.thread.start()

    def update(self, message: str) -> None:
        """Update progress message.

        Args:
            message: Progress update message
        """
        if self.verbose:
            click.echo(f"  {message}")

    def stop(self, success: bool = True, message: str | None = None) -> None:
        """Stop the progress indicator.

        Args:
            success: Whether operation was successful
            message: Final message
        """
        if not self.verbose and self.running:
            self.running = False
            if self.thread:
                self.thread.join(timeout=0.1)
            # Clear the spinner line
            click.echo("\r" + " " * 80 + "\r", nl=False)

        elapsed = time.time() - self.start_time
        status = "✅" if success else "❌"
        final_msg = message or ("completed" if success else "failed")

        if self.verbose:
            click.echo(f"Finished: {self.description} - {final_msg} ({elapsed:.1f}s)")
        else:
            click.echo(f"{status} {self.description} - {final_msg} ({elapsed:.1f}s)")

    def _spin(self) -> None:
        """Spinner animation loop."""
        while self.running:
            char = self.spinner_chars[self.spinner_index % len(self.spinner_chars)]
            click.echo(f"\r{char} {self.description}...", nl=False)
            self.spinner_index += 1
            time.sleep(0.1)


class ComprehensiveGrammarCLI:
    """Comprehensive grammar management CLI with error handling integration."""

    def __init__(self, cache_dir: Path | None = None, verbose: bool = False):
        """Initialize the comprehensive grammar CLI.

        Args:
            cache_dir: Cache directory for grammars (defaults to ~/.cache/treesitter-chunker/grammars/)
            verbose: Enable verbose output
        """
        self.verbose = verbose

        # Set up cache directory (Phase 1.8 specification compliance)
        if cache_dir is None:
            cache_base = Path.home() / ".cache" / "treesitter-chunker"
        else:
            cache_base = Path(cache_dir)

        self.cache_dir = cache_base
        self.grammars_dir = cache_base / "grammars"
        self.user_grammars_dir = self.grammars_dir / "user"
        self.package_grammars_dir = self.grammars_dir / "package"
        self.build_dir = self.grammars_dir / "build"

        # Create directories if they don't exist
        for directory in [
            self.cache_dir,
            self.grammars_dir,
            self.user_grammars_dir,
            self.package_grammars_dir,
            self.build_dir,
        ]:
            directory.mkdir(parents=True, exist_ok=True)

        # Initialize error handling system (Task E1 integration)
        self.error_handling_available = ERROR_HANDLING_AVAILABLE
        self.pipeline = None
        self.orchestrator = None
        self.cli_integration = None

        if self.error_handling_available:
            try:
                self.pipeline, self.orchestrator, self.cli_integration = (
                    create_error_handling_system(
                        max_concurrent_processes=2,
                        max_sessions=50,
                        session_timeout_minutes=15,
                    )
                )
                if self.verbose:
                    click.echo("✅ Error handling system initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize error handling system: {e}")
                self.error_handling_available = False

        # Initialize grammar management components
        self.grammar_manager = None
        self.compatibility_manager = None

        if GRAMMAR_COMPONENTS_AVAILABLE:
            try:
                self.grammar_manager = GrammarManager(
                    user_dir=self.user_grammars_dir,
                    package_dir=self.package_grammars_dir,
                    cache_dir=self.cache_dir,
                )
                if self.verbose:
                    click.echo("✅ Core grammar manager initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize grammar manager: {e}")

        if COMPATIBILITY_AVAILABLE:
            try:
                self.compatibility_manager = CompatibilityManager(
                    cache_dir=self.cache_dir,
                )
                if self.verbose:
                    click.echo("✅ Compatibility manager initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize compatibility manager: {e}")

        # Known grammar sources (Phase 1.8 specification)
        self.grammar_sources = {
            "python": "https://github.com/tree-sitter/tree-sitter-python",
            "javascript": "https://github.com/tree-sitter/tree-sitter-javascript",
            "typescript": "https://github.com/tree-sitter/tree-sitter-typescript",
            "java": "https://github.com/tree-sitter/tree-sitter-java",
            "go": "https://github.com/tree-sitter/tree-sitter-go",
            "rust": "https://github.com/tree-sitter/tree-sitter-rust",
            "c": "https://github.com/tree-sitter/tree-sitter-c",
            "cpp": "https://github.com/tree-sitter/tree-sitter-cpp",
            "ruby": "https://github.com/tree-sitter/tree-sitter-ruby",
            "php": "https://github.com/tree-sitter/tree-sitter-php",
        }

        # Load additional grammar sources if available
        self._load_grammar_sources()

        if self.verbose:
            click.echo(f"✅ Grammar CLI initialized with cache at: {self.cache_dir}")

    def _load_grammar_sources(self) -> None:
        """Load additional grammar sources from configuration."""
        try:
            config_file = (
                Path(__file__).parent.parent.parent / "config" / "grammar_sources.json"
            )
            if config_file.exists():
                with open(config_file) as f:
                    additional_sources = json.load(f)
                    self.grammar_sources.update(additional_sources)
                    if self.verbose:
                        click.echo(
                            f"✅ Loaded {len(additional_sources)} additional grammar sources",
                        )
        except Exception as e:
            logger.warning(f"Failed to load additional grammar sources: {e}")

    def _handle_error(
        self,
        error_msg: str,
        language: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Handle error using integrated error handling pipeline.

        Args:
            error_msg: Error message
            language: Optional language context
            context: Optional additional context

        Returns:
            Dictionary with error handling results
        """
        if not self.error_handling_available or not self.cli_integration:
            return {
                "success": False,
                "guidance": [f"Error: {error_msg}"],
                "quick_fixes": [],
                "suggested_commands": [],
            }

        try:
            if language and "grammar" in error_msg.lower():
                return self.cli_integration.handle_grammar_validation_error(
                    language,
                    error_msg,
                    context.get("grammar_path") if context else None,
                )
            if "download" in error_msg.lower() or "fetch" in error_msg.lower():
                return self.cli_integration.handle_grammar_download_error(
                    language or "unknown",
                    error_msg,
                    context.get("url") if context else None,
                )
            # General error handling
            session = self.orchestrator.create_session(
                context={"cli_operation": True},
            )
            try:
                result = self.orchestrator.process_error_in_session(
                    session.session_id,
                    error_msg,
                    context,
                )
                return {
                    "success": result.success,
                    "guidance": self._extract_guidance_messages(result),
                    "quick_fixes": self._extract_quick_fixes(result),
                    "suggested_commands": self._extract_commands(result),
                }
            finally:
                self.orchestrator.close_session(session.session_id)
        except Exception as e:
            logger.error(f"Error in error handling pipeline: {e}")
            return {
                "success": False,
                "guidance": [f"Error: {error_msg}"],
                "quick_fixes": [],
                "suggested_commands": [],
            }

    def _extract_guidance_messages(self, result) -> List[str]:
        """Extract guidance messages from pipeline result."""
        messages = []
        if hasattr(result, "guidance_sequence") and result.guidance_sequence:
            for action in result.guidance_sequence.actions:
                messages.append(f"{action.title}: {action.description}")
        if hasattr(result, "fallback_response") and result.fallback_response:
            messages.extend(result.fallback_response.get("general_guidance", []))
        return messages

    def _extract_quick_fixes(self, result) -> List[str]:
        """Extract quick fixes from pipeline result."""
        fixes = []
        if hasattr(result, "guidance_sequence") and result.guidance_sequence:
            for action in result.guidance_sequence.actions:
                if hasattr(action, "command") and action.command:
                    fixes.append(action.command)
        return fixes[:3]  # Limit to 3 quick fixes

    def _extract_commands(self, result) -> List[str]:
        """Extract suggested CLI commands from pipeline result."""
        commands = []
        if hasattr(result, "guidance_sequence") and result.guidance_sequence:
            for action in result.guidance_sequence.actions:
                if (
                    hasattr(action, "command")
                    and action.command
                    and "treesitter-chunker" in action.command
                ):
                    commands.append(action.command)
        return commands

    def _get_grammar_priority_order(self) -> List[tuple[Path, str, Any]]:
        """Get grammar search paths in priority order (Phase 1.8 specification).

        Returns:
            List of (path, description, priority) tuples
        """
        if GRAMMAR_COMPONENTS_AVAILABLE:
            return [
                (self.user_grammars_dir, "user-installed", GrammarPriority.USER),
                (self.package_grammars_dir, "package-bundled", GrammarPriority.PACKAGE),
                (self.build_dir, "fallback", GrammarPriority.FALLBACK),
            ]
        return [
            (self.user_grammars_dir, "user-installed", 1),
            (self.package_grammars_dir, "package-bundled", 2),
            (self.build_dir, "fallback", 3),
        ]

    def _find_grammar(
        self,
        language: str,
    ) -> tuple[Path, str, GrammarPriority] | None:
        """Find grammar following priority order.

        Args:
            language: Language to search for

        Returns:
            Tuple of (path, description, priority) if found, None otherwise
        """
        for search_path, description, priority in self._get_grammar_priority_order():
            # Check for compiled grammar
            so_file = search_path / f"tree_sitter_{language}.so"
            if so_file.exists():
                return (so_file, description, priority)

            # Check for source directory
            source_dir = search_path / language
            if source_dir.exists() and source_dir.is_dir():
                return (source_dir, description, priority)

        return None

    def _get_all_grammars(self) -> dict[str, dict[str, Any]]:
        """Get information about all available grammars.

        Returns:
            Dictionary mapping language names to grammar information
        """
        grammars = {}

        # Collect from all priority locations
        for search_path, source, priority in self._get_grammar_priority_order():
            if not search_path.exists():
                continue

            # Find .so files
            for so_file in search_path.glob("tree_sitter_*.so"):
                language = so_file.stem.replace("tree_sitter_", "")
                if language not in grammars:
                    grammars[language] = {
                        "language": language,
                        "path": str(so_file),
                        "source": source,
                        "priority": priority,
                        "status": self._check_grammar_status(so_file),
                        "type": "compiled",
                    }

            # Find source directories
            if search_path.is_dir():
                for source_dir in search_path.iterdir():
                    if source_dir.is_dir() and source_dir.name not in [".", ".."]:
                        language = source_dir.name
                        if language not in grammars:
                            grammars[language] = {
                                "language": language,
                                "path": str(source_dir),
                                "source": source,
                                "priority": priority,
                                "status": self._check_source_status(source_dir),
                                "type": "source",
                            }

        return grammars

    def _check_grammar_status(self, grammar_path: Path) -> str:
        """Check status of a compiled grammar.

        Args:
            grammar_path: Path to grammar file

        Returns:
            Status string
        """
        if not grammar_path.exists():
            return GrammarStatus.MISSING

        try:
            # Basic file checks
            if grammar_path.stat().st_size == 0:
                return GrammarStatus.CORRUPTED

            # Try to load the grammar (simplified check)
            # In a real implementation, this would use tree-sitter to verify
            return GrammarStatus.HEALTHY

        except Exception:
            return GrammarStatus.CORRUPTED

    def _check_source_status(self, source_dir: Path) -> str:
        """Check status of grammar source directory.

        Args:
            source_dir: Path to source directory

        Returns:
            Status string
        """
        if not source_dir.exists() or not source_dir.is_dir():
            return GrammarStatus.MISSING

        # Check for required files
        has_grammar_js = (source_dir / "grammar.js").exists()
        has_package_json = (source_dir / "package.json").exists()
        has_src = (source_dir / "src").exists()

        if has_grammar_js and (has_package_json or has_src):
            return GrammarStatus.HEALTHY
        return GrammarStatus.INCOMPATIBLE

    def _run_command(
        self,
        cmd: List[str],
        cwd: Path | None = None,
        timeout: int = 300,
    ) -> tuple[int, str, str]:
        """Run shell command with timeout.

        Args:
            cmd: Command to run
            cwd: Working directory
            timeout: Timeout in seconds

        Returns:
            Tuple of (return_code, stdout, stderr)
        """
        try:
            result = subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return 1, "", f"Command timed out after {timeout} seconds"
        except Exception as e:
            return 1, "", f"Command failed: {e}"

    # CLI Command Implementations (Phase 1.8 specification compliance)

    def list_grammars(
        self,
        language_filter: str | None = None,
        show_all: bool = False,
        output_format: str = "table",
    ) -> int:
        """List available and user-installed grammars with enhanced functionality.

        Args:
            language_filter: Optional language filter
            show_all: Show grammars from all priority levels
            output_format: Output format (table, json, yaml)

        Returns:
            Exit code (0 for success, 1 for error)
        """
        try:
            if output_format not in ["table", "json", "yaml"]:
                click.echo(f"❌ Invalid output format: {output_format}")
                return 1

            # Use core grammar manager if available
            if self.grammar_manager:
                grammars = self.grammar_manager.discover_available_grammars()
            else:
                grammars = self._get_all_grammars_fallback()

            if language_filter:
                grammars = {
                    k: v
                    for k, v in grammars.items()
                    if language_filter.lower() in k.lower()
                }

            if not grammars:
                if language_filter:
                    click.echo(f"❌ No grammars found matching '{language_filter}'")
                else:
                    click.echo("❌ No grammars found")
                    click.echo("\n💡 Try downloading a grammar:")
                    click.echo("   treesitter-chunker grammar fetch python")
                return 1

            # Output in requested format
            if output_format == "json":
                import json

                click.echo(json.dumps(grammars, indent=2, default=str))
            elif output_format == "yaml":
                try:
                    import yaml

                    click.echo(yaml.dump(grammars, default_flow_style=False))
                except ImportError:
                    click.echo(
                        "❌ PyYAML not installed. Install with: pip install pyyaml",
                    )
                    return 1
            else:
                # Table format (default)
                self._display_grammars_table(grammars)

            return 0

        except Exception as e:
            error_result = self._handle_error(
                str(e),
                context={"operation": "list_grammars"},
            )
            click.echo(f"❌ Error listing grammars: {e}")

            if error_result["guidance"]:
                click.echo("\n💡 Guidance:")
                for guidance in error_result["guidance"]:
                    click.echo(f"  • {guidance}")

            return 1

    def _display_grammars_table(self, grammars: dict[str, dict[str, Any]]) -> None:
        """Display grammars in table format.

        Args:
            grammars: Dictionary of grammar information
        """
        click.echo("📋 Grammar Status Summary")
        click.echo("=" * 50)

        # Summary statistics
        total_count = len(grammars)
        healthy_count = sum(
            1
            for g in grammars.values()
            if g.get("validation", {}).get("is_valid", False)
            or g.get("status", "unknown") in ["healthy", "HEALTHY"]
        )

        click.echo(f"Total grammars: {total_count}")
        click.echo(f"Healthy: {healthy_count}")
        click.echo(f"Issues: {total_count - healthy_count}")
        click.echo()

        # Group by priority for display
        priority_groups = {}
        for lang, grammar in grammars.items():
            priority = grammar.get("priority", "unknown")
            if priority not in priority_groups:
                priority_groups[priority] = []
            grammar["language"] = lang  # Ensure language field is set
            priority_groups[priority].append(grammar)

        # Display by priority
        priority_order = (
            ["USER", "PACKAGE", "FALLBACK"]
            if GRAMMAR_COMPONENTS_AVAILABLE
            else [1, 2, 3]
        )
        priority_names = {
            "USER": "🏠 User-installed grammars",
            "PACKAGE": "📦 Package-bundled grammars",
            "FALLBACK": "🔄 Fallback grammars",
            1: "🏠 User-installed grammars",
            2: "📦 Package-bundled grammars",
            3: "🔄 Fallback grammars",
        }

        for priority in priority_order:
            if priority not in priority_groups:
                continue

            priority_name = priority_names.get(priority, f"Priority {priority}")
            click.echo(priority_name)

            for grammar in sorted(
                priority_groups[priority],
                key=lambda g: g.get("language", ""),
            ):
                # Determine status and emoji
                is_valid = grammar.get("validation", {}).get(
                    "is_valid",
                    grammar.get("exists", False),
                )
                status = grammar.get("status", "unknown")

                if is_valid or status in ["healthy", "HEALTHY"]:
                    status_emoji = "✅"
                    status_text = "healthy"
                else:
                    status_emoji = "❌"
                    status_text = status or "unknown"

                type_indicator = "🔧"  # Default to compiled
                if "type" in grammar and grammar["type"] == "source":
                    type_indicator = "📁"

                lang_name = grammar.get("language", "unknown")
                click.echo(
                    f"  {status_emoji} {type_indicator} {lang_name} ({status_text})",
                )

                if self.verbose:
                    path = grammar.get("path", "unknown")
                    click.echo(f"    Path: {path}")
                    if "version" in grammar:
                        click.echo(f"    Version: {grammar['version']}")
                    if "install_date" in grammar:
                        import time

                        date_str = time.strftime(
                            "%Y-%m-%d %H:%M",
                            time.localtime(grammar["install_date"]),
                        )
                        click.echo(f"    Installed: {date_str}")
            click.echo()

    def _get_all_grammars_fallback(self) -> dict[str, dict[str, Any]]:
        """Fallback method to get all grammars when core manager unavailable.

        Returns:
            Dictionary mapping language names to grammar information
        """
        return self._get_all_grammars()

    def info_grammar(self, language: str, output_format: str = "table") -> int:
        """Show comprehensive grammar details and compatibility information.

        Args:
            language: Language name
            output_format: Output format (table, json, yaml)

        Returns:
            Exit code (0 for success, 1 for error)
        """
        try:
            if output_format not in ["table", "json", "yaml"]:
                click.echo(f"❌ Invalid output format: {output_format}")
                return 1

            # Get comprehensive grammar metadata
            if self.grammar_manager:
                metadata = self.grammar_manager.get_grammar_metadata(language)
                if not metadata:
                    click.echo(f"❌ Grammar for '{language}' not found")
                    if language in self.grammar_sources:
                        click.echo(
                            f"\n💡 Grammar source available: {self.grammar_sources[language]}",
                        )
                        click.echo(
                            f"   Run: treesitter-chunker grammar fetch {language}",
                        )
                    return 1
            else:
                # Fallback method
                grammar_info = self._find_grammar(language)
                if not grammar_info:
                    click.echo(f"❌ Grammar for '{language}' not found")
                    if language in self.grammar_sources:
                        click.echo(
                            f"\n💡 Grammar source available: {self.grammar_sources[language]}",
                        )
                        click.echo(
                            f"   Run: treesitter-chunker grammar fetch {language}",
                        )
                    return 1

                grammar_path, source, priority = grammar_info
                metadata = self._build_grammar_metadata_fallback(
                    language,
                    grammar_path,
                    source,
                    priority,
                )

            # Output in requested format
            if output_format == "json":
                import json

                click.echo(json.dumps(metadata, indent=2, default=str))
            elif output_format == "yaml":
                try:
                    import yaml

                    click.echo(yaml.dump(metadata, default_flow_style=False))
                except ImportError:
                    click.echo(
                        "❌ PyYAML not installed. Install with: pip install pyyaml",
                    )
                    return 1
            else:
                # Table format (default)
                self._display_grammar_info_table(language, metadata)

            return 0

        except Exception as e:
            error_result = self._handle_error(
                str(e),
                language,
                {"operation": "grammar_info"},
            )
            click.echo(f"❌ Error getting grammar info: {e}")

            if error_result["guidance"]:
                click.echo("\n💡 Guidance:")
                for guidance in error_result["guidance"]:
                    click.echo(f"  • {guidance}")

            return 1

    def _display_grammar_info_table(
        self,
        language: str,
        metadata: dict[str, Any],
    ) -> None:
        """Display grammar information in table format.

        Args:
            language: Language name
            metadata: Grammar metadata dictionary
        """
        click.echo(f"📊 Grammar Information: {language}")
        click.echo("=" * 50)

        # Basic information
        click.echo(f"Language: {language}")

        # Status with validation information
        validation = metadata.get("validation", {})
        is_valid = validation.get("is_valid", False)
        status = "healthy" if is_valid else "unhealthy"
        status_emoji = "✅" if is_valid else "❌"
        click.echo(f"Status: {status_emoji} {status.title()}")

        # Path and source information
        if "path" in metadata:
            click.echo(f"Path: {metadata['path']}")
        if "priority" in metadata:
            priority_name = {
                "USER": "User-installed",
                "PACKAGE": "Package-bundled",
                "FALLBACK": "Fallback",
            }.get(str(metadata["priority"]), str(metadata["priority"]))
            click.echo(f"Source: {priority_name}")

        # File information
        if "size" in metadata:
            click.echo(f"File size: {metadata['size']:,} bytes")
        if "modified" in metadata:
            import time

            modified_time = time.ctime(metadata["modified"])
            click.echo(f"Last modified: {modified_time}")

        click.echo()

        # Version and installation information
        if (
            "version" in metadata
            or "install_date" in metadata
            or "source_url" in metadata
        ):
            click.echo("📦 Installation Information")
            click.echo("-" * 30)

            if "version" in metadata:
                click.echo(f"Version: {metadata['version']}")
            if "install_date" in metadata:
                import time

                install_time = time.strftime(
                    "%Y-%m-%d %H:%M",
                    time.localtime(metadata["install_date"]),
                )
                click.echo(f"Installed: {install_time}")
            if "source_url" in metadata:
                click.echo(f"Repository: {metadata['source_url']}")
            if metadata.get("source_commit"):
                commit = (
                    metadata["source_commit"][:8]
                    if len(metadata["source_commit"]) > 8
                    else metadata["source_commit"]
                )
                click.echo(f"Commit: {commit}")

            click.echo()

        # Validation details
        if validation:
            click.echo("🔍 Validation Details")
            click.echo("-" * 30)

            if validation.get("errors"):
                click.echo("Errors:")
                for error in validation["errors"]:
                    click.echo(f"  ❌ {error}")

            if validation.get("warnings"):
                click.echo("Warnings:")
                for warning in validation["warnings"]:
                    click.echo(f"  ⚠️ {warning}")

            if not validation.get("errors") and not validation.get("warnings"):
                click.echo("✅ No validation issues found")

            click.echo()

        # Performance metrics
        performance = metadata.get("performance", {})
        if performance:
            click.echo("📊 Performance Metrics")
            click.echo("-" * 30)

            if "parse_time" in performance:
                click.echo(f"Parse time: {performance['parse_time']:.3f} seconds")
            if "memory_delta_mb" in performance:
                click.echo(f"Memory usage: {performance['memory_delta_mb']:.2f} MB")
            if "samples_tested" in performance:
                click.echo(f"Samples tested: {performance['samples_tested']}")

            click.echo()

        # Compatibility information
        self._display_compatibility_info(metadata)

        # Recommendations
        recommendations = self._get_enhanced_recommendations(language, metadata)
        if recommendations:
            click.echo("💡 Recommendations")
            click.echo("-" * 30)
            for rec in recommendations:
                click.echo(f"  • {rec}")
            click.echo()

    def _display_compatibility_info(self, metadata: dict[str, Any]) -> None:
        """Display compatibility information.

        Args:
            metadata: Grammar metadata dictionary
        """
        click.echo("🔧 Compatibility Information")
        click.echo("-" * 30)

        # System information
        click.echo(f"OS: {platform.system()} {platform.release()}")
        click.echo(f"Architecture: {platform.machine()}")
        click.echo(f"Python: {platform.python_version()}")

        # ABI compatibility (if available)
        if self.compatibility_manager:
            try:
                path = Path(metadata.get("path", ""))
                if path.exists() and path.suffix == ".so":
                    is_compatible = (
                        self.compatibility_manager.check_grammar_compatibility(
                            str(path),
                        )
                    )
                    click.echo(
                        f"ABI Compatible: {'✅ Yes' if is_compatible else '❌ No'}",
                    )
            except Exception as e:
                click.echo(f"ABI Check: ⚠️ Could not determine ({e})")

        # Tree-sitter version compatibility
        try:
            import tree_sitter

            click.echo(
                f"Tree-sitter version: {tree_sitter.__version__ if hasattr(tree_sitter, '__version__') else 'unknown'}",
            )
        except ImportError:
            click.echo("Tree-sitter: ❌ Not installed")

        click.echo()

    def _build_grammar_metadata_fallback(
        self,
        language: str,
        grammar_path: Path,
        source: str,
        priority: Any,
    ) -> dict[str, Any]:
        """Build grammar metadata using fallback methods.

        Args:
            language: Language name
            grammar_path: Path to grammar
            source: Source description
            priority: Priority level

        Returns:
            Metadata dictionary
        """
        metadata = {
            "language": language,
            "path": str(grammar_path),
            "priority": priority,
            "exists": grammar_path.exists(),
        }

        if grammar_path.exists():
            stat_info = grammar_path.stat()
            metadata.update({"size": stat_info.st_size, "modified": stat_info.st_mtime})

            # Basic validation
            if grammar_path.suffix == ".so":
                status = self._check_grammar_status(grammar_path)
            else:
                status = self._check_source_status(grammar_path)

            metadata["validation"] = {
                "is_valid": status == "healthy",
                "errors": [] if status == "healthy" else [f"Grammar status: {status}"],
                "warnings": [],
            }

        return metadata

    def _get_enhanced_recommendations(
        self,
        language: str,
        metadata: dict[str, Any],
    ) -> List[str]:
        """Get enhanced recommendations based on grammar metadata.

        Args:
            language: Language name
            metadata: Grammar metadata

        Returns:
            List of recommendation strings
        """
        recommendations = []

        validation = metadata.get("validation", {})

        if not validation.get("is_valid", False):
            if not metadata.get("exists", False):
                recommendations.append(
                    f"Download grammar: treesitter-chunker grammar fetch {language}",
                )
            else:
                recommendations.append(
                    f"Rebuild grammar: treesitter-chunker grammar build {language}",
                )
                recommendations.append(
                    f"Or re-download: treesitter-chunker grammar fetch {language} --force",
                )
        else:
            recommendations.append("Grammar is healthy - no action needed")
            if language in self.grammar_sources:
                recommendations.append(
                    f"Check for updates: treesitter-chunker grammar versions {language}",
                )

        # Performance recommendations
        performance = metadata.get("performance", {})
        if performance.get("parse_time", 0) > 5.0:
            recommendations.append("Consider optimizing for better parse performance")

        return recommendations

    def _format_status(self, status: str) -> str:
        """Format status with emoji.

        Args:
            status: Status string

        Returns:
            Formatted status string
        """
        emoji_map = {
            GrammarStatus.HEALTHY: "✅",
            GrammarStatus.MISSING: "❌",
            GrammarStatus.CORRUPTED: "💥",
            GrammarStatus.INCOMPATIBLE: "⚠️",
            GrammarStatus.BUILDING: "🔨",
            GrammarStatus.DOWNLOADING: "📥",
            GrammarStatus.UNKNOWN: "❓",
        }
        emoji = emoji_map.get(status, "❓")
        return f"{emoji} {status.title()}"

    def _get_grammar_recommendations(
        self,
        language: str,
        status: str,
        path: Path,
    ) -> List[str]:
        """Get recommendations for grammar improvement.

        Args:
            language: Language name
            status: Current status
            path: Grammar path

        Returns:
            List of recommendation strings
        """
        recommendations = []

        if status == GrammarStatus.MISSING:
            recommendations.append(
                f"Download grammar: treesitter-chunker grammar fetch {language}",
            )

        elif status == GrammarStatus.CORRUPTED:
            recommendations.append(
                f"Rebuild grammar: treesitter-chunker grammar build {language}",
            )
            recommendations.append(
                f"Or re-download: treesitter-chunker grammar fetch {language}",
            )

        elif status == GrammarStatus.INCOMPATIBLE:
            if path.is_dir():
                recommendations.append("Check grammar.js file exists and is valid")
                recommendations.append(
                    "Ensure src/ directory contains generated parser files",
                )
                recommendations.append(
                    f"Try building: treesitter-chunker grammar build {language}",
                )

        elif status == GrammarStatus.HEALTHY:
            recommendations.append("Grammar is healthy - no action needed")
            if language in self.grammar_sources:
                recommendations.append(
                    f"Check for updates: treesitter-chunker grammar versions {language}",
                )

        return recommendations

    def versions_grammar(self, language: str) -> int:
        """List available versions for a language.

        Args:
            language: Language name

        Returns:
            Exit code (0 for success, 1 for error)
        """
        try:
            click.echo(f"📋 Available Versions: {language}")
            click.echo("=" * 50)

            if language not in self.grammar_sources:
                click.echo(f"❌ No known source for '{language}' grammar")
                click.echo("\n💡 Known languages:")
                for known_lang in sorted(self.grammar_sources.keys())[:5]:
                    click.echo(f"  • {known_lang}")
                if len(self.grammar_sources) > 5:
                    click.echo(f"  ... and {len(self.grammar_sources) - 5} more")
                return 1

            repo_url = self.grammar_sources[language]
            click.echo(f"Repository: {repo_url}")
            click.echo()

            progress = ProgressIndicator("Fetching version information", self.verbose)
            progress.start()

            try:
                # Try to get versions from GitHub API if it's a GitHub repo
                if "github.com" in repo_url:
                    api_url = (
                        repo_url.replace("github.com", "api.github.com/repos") + "/tags"
                    )

                    try:
                        import json
                        import urllib.request

                        with urllib.request.urlopen(api_url, timeout=10) as response:
                            tags_data = json.loads(response.read().decode())

                        progress.stop(True, "versions fetched")

                        if tags_data:
                            click.echo("📦 Available Versions (Tags):")
                            for tag in tags_data[:10]:  # Show latest 10
                                click.echo(f"  • {tag['name']}")

                            if len(tags_data) > 10:
                                click.echo(f"  ... and {len(tags_data) - 10} more")
                        else:
                            click.echo("📦 No tagged versions found")
                            click.echo("💡 Try fetching the latest development version")

                        click.echo()
                        click.echo("🔄 Available Branches:")
                        click.echo("  • main (default)")
                        click.echo("  • master")
                        click.echo("  • develop")

                    except Exception as e:
                        progress.stop(False, "API request failed")
                        click.echo(f"⚠️ Could not fetch version info from API: {e}")
                        click.echo("💡 Repository likely has these common branches:")
                        click.echo("  • main (default)")
                        click.echo("  • master")

                else:
                    progress.stop(True, "basic info provided")
                    click.echo("⚠️ Non-GitHub repository - version detection limited")
                    click.echo("💡 Common branches to try:")
                    click.echo("  • main (default)")
                    click.echo("  • master")
                    click.echo("  • develop")

                click.echo()
                click.echo("📥 To fetch a specific version:")
                click.echo(
                    f"  treesitter-chunker grammar fetch {language} --branch main",
                )
                click.echo(
                    f"  treesitter-chunker grammar fetch {language} --version v1.0.0",
                )

                return 0

            except Exception as e:
                progress.stop(False, str(e))
                raise

        except Exception as e:
            error_result = self._handle_error(
                str(e),
                language,
                {"operation": "versions"},
            )
            click.echo(f"❌ Error fetching versions: {e}")

            if error_result["guidance"]:
                click.echo("\n💡 Guidance:")
                for guidance in error_result["guidance"]:
                    click.echo(f"  • {guidance}")

            return 1

    def fetch_grammar(
        self,
        language: str,
        version: str | None = None,
        branch: str = "main",
        force: bool = False,
    ) -> int:
        """Download specific grammar version with enhanced functionality.

        Args:
            language: Language name
            version: Specific version/tag to fetch
            branch: Branch to fetch (default: main)
            force: Force re-download even if exists

        Returns:
            Exit code (0 for success, 1 for error)
        """
        try:
            click.echo(f"📥 Fetching Grammar: {language}")
            click.echo("=" * 50)

            if language not in self.grammar_sources:
                click.echo(f"❌ No known source for '{language}' grammar")

                # Try to suggest similar languages
                similar = [
                    lang
                    for lang in self.grammar_sources.keys()
                    if language.lower() in lang.lower()
                    or lang.lower() in language.lower()
                ]
                if similar:
                    click.echo("\n💡 Did you mean one of these?")
                    for sim_lang in similar[:3]:
                        click.echo(f"  • {sim_lang}")

                return 1

            repo_url = self.grammar_sources[language]

            # Use core grammar manager if available
            if self.grammar_manager:
                success, error_msg = self.grammar_manager.install_grammar(
                    language,
                    repo_url,
                    version,
                    force,
                )

                if success:
                    click.echo(f"✅ Successfully installed {language} grammar!")
                    click.echo("\n🔄 Next steps:")
                    click.echo(
                        f"  • Validate: treesitter-chunker grammar validate {language}",
                    )
                    click.echo(
                        f"  • Test: treesitter-chunker grammar test {language} <file>",
                    )
                    click.echo(f"  • Info: treesitter-chunker grammar info {language}")
                    return 0
                click.echo(f"❌ Installation failed: {error_msg}")

                error_result = self._handle_error(
                    error_msg or "Installation failed",
                    language,
                    {"operation": "fetch", "url": repo_url},
                )

                if error_result.get("troubleshooting_steps"):
                    click.echo("\n🔧 Troubleshooting steps:")
                    for step in error_result["troubleshooting_steps"]:
                        click.echo(f"  • {step}")

                return 1
            # Fallback to manual installation
            return self._fetch_grammar_fallback(
                language,
                version,
                branch,
                force,
                repo_url,
            )

        except Exception as e:
            error_result = self._handle_error(
                str(e),
                language,
                {"operation": "fetch", "url": self.grammar_sources.get(language)},
            )
            click.echo(f"❌ Error fetching grammar: {e}")

            if error_result.get("troubleshooting_steps"):
                click.echo("\n🔧 Troubleshooting:")
                for step in error_result["troubleshooting_steps"]:
                    click.echo(f"  • {step}")

            return 1

    def _fetch_grammar_fallback(
        self,
        language: str,
        version: str | None,
        branch: str,
        force: bool,
        repo_url: str,
    ) -> int:
        """Fallback method for grammar fetching when core manager unavailable.

        Args:
            language: Language name
            version: Specific version/tag to fetch
            branch: Branch to fetch
            force: Force re-download
            repo_url: Repository URL

        Returns:
            Exit code
        """
        target_dir = self.user_grammars_dir / language

        click.echo(f"Repository: {repo_url}")
        click.echo(f"Target: {target_dir}")
        click.echo(f"Branch/Version: {version or branch}")
        click.echo()

        # Check if already exists
        if target_dir.exists() and not force:
            click.echo(f"⚠️ Grammar already exists at {target_dir}")
            if not click.confirm("Overwrite existing grammar?"):
                click.echo("📦 Fetch cancelled")
                return 0
            shutil.rmtree(target_dir)

        progress = ProgressIndicator(f"Downloading {language} grammar", self.verbose)
        progress.start()

        try:
            # Prepare git command
            git_cmd = ["git", "clone"]
            if version:
                # For specific version, we'll clone then checkout
                git_cmd.extend([repo_url, str(target_dir)])
            else:
                # For branch, clone specific branch
                git_cmd.extend(
                    ["--branch", branch, "--depth", "1", repo_url, str(target_dir)],
                )

            progress.update("Cloning repository...")

            # Run git clone
            returncode, stdout, stderr = self._run_command(git_cmd, timeout=120)

            if returncode != 0:
                progress.stop(False, "clone failed")
                click.echo(f"❌ Git clone failed: {stderr}")
                return 1

            # If specific version requested, checkout that version
            if version:
                progress.update(f"Checking out version {version}...")
                checkout_cmd = ["git", "checkout", version]
                returncode, stdout, stderr = self._run_command(
                    checkout_cmd,
                    cwd=target_dir,
                )

                if returncode != 0:
                    progress.stop(False, f"checkout {version} failed")
                    click.echo(f"❌ Failed to checkout version {version}: {stderr}")
                    return 1

            progress.update("Verifying download...")

            # Verify the download
            if not target_dir.exists():
                progress.stop(False, "target directory not created")
                click.echo("❌ Download failed - target directory not created")
                return 1

            # Check for essential files
            has_grammar_js = (target_dir / "grammar.js").exists()

            if not has_grammar_js:
                progress.stop(False, "grammar.js not found")
                click.echo(
                    "⚠️ Warning: grammar.js not found - this may not be a valid tree-sitter grammar",
                )
            else:
                progress.update("Grammar files verified")

            progress.stop(True, "download completed")

            click.echo(f"✅ Successfully fetched {language} grammar!")
            click.echo(f"📁 Location: {target_dir}")
            click.echo()

            # Show next steps
            click.echo("🔄 Next steps:")
            if has_grammar_js:
                click.echo(
                    f"  • Build grammar: treesitter-chunker grammar build {language}",
                )
                click.echo(
                    f"  • Test grammar: treesitter-chunker grammar test {language} <file>",
                )
            else:
                click.echo(
                    f"  • Check grammar structure: treesitter-chunker grammar info {language}",
                )

            return 0

        except Exception as e:
            progress.stop(False, str(e))
            raise

    def build_grammar(self, language: str, force: bool = False) -> int:
        """Build grammar from source.

        Args:
            language: Language name
            force: Force rebuild even if compiled version exists

        Returns:
            Exit code (0 for success, 1 for error)
        """
        try:
            click.echo(f"🔨 Building Grammar: {language}")
            click.echo("=" * 50)

            # Find source directory
            source_dir = None
            for search_path, _, _ in self._get_grammar_priority_order():
                potential_source = search_path / language
                if potential_source.exists() and potential_source.is_dir():
                    source_dir = potential_source
                    break

            if not source_dir:
                click.echo(f"❌ No source found for '{language}' grammar")
                if language in self.grammar_sources:
                    click.echo(
                        f"💡 Try fetching first: treesitter-chunker grammar fetch {language}",
                    )
                return 1

            # Check if already built
            compiled_grammar = self.build_dir / f"tree_sitter_{language}.so"
            if compiled_grammar.exists() and not force:
                click.echo(f"⚠️ Compiled grammar already exists: {compiled_grammar}")
                if not click.confirm("Rebuild anyway?"):
                    click.echo("🔨 Build cancelled")
                    return 0

            click.echo(f"Source: {source_dir}")
            click.echo(f"Target: {compiled_grammar}")
            click.echo()

            progress = ProgressIndicator(f"Building {language} grammar", self.verbose)
            progress.start()

            try:
                # Check for build requirements
                progress.update("Checking build requirements...")

                # Check for Node.js (required for tree-sitter)
                node_check = self._run_command(["node", "--version"])
                if node_check[0] != 0:
                    progress.stop(False, "Node.js not found")
                    click.echo("❌ Node.js is required but not found")
                    click.echo("💡 Install Node.js: https://nodejs.org/")
                    return 1

                # Check for tree-sitter CLI
                ts_check = self._run_command(["npx", "tree-sitter", "--version"])
                if ts_check[0] != 0:
                    progress.update("Installing tree-sitter CLI...")
                    install_cmd = ["npm", "install", "-g", "tree-sitter-cli"]
                    install_result = self._run_command(install_cmd, timeout=120)
                    if install_result[0] != 0:
                        progress.stop(False, "tree-sitter CLI installation failed")
                        click.echo("❌ Failed to install tree-sitter CLI")
                        click.echo("💡 Try: npm install -g tree-sitter-cli")
                        return 1

                # Generate parser files if needed
                progress.update("Generating parser files...")

                generate_cmd = ["npx", "tree-sitter", "generate"]
                generate_result = self._run_command(
                    generate_cmd,
                    cwd=source_dir,
                    timeout=60,
                )

                if generate_result[0] != 0:
                    progress.stop(False, "parser generation failed")
                    click.echo(f"❌ Failed to generate parser: {generate_result[2]}")

                    error_result = self._handle_error(
                        generate_result[2],
                        language,
                        {
                            "operation": "build_generate",
                            "grammar_path": str(source_dir),
                        },
                    )

                    if error_result.get("quick_fixes"):
                        click.echo("\n🔧 Quick fixes:")
                        for fix in error_result["quick_fixes"]:
                            click.echo(f"  • {fix}")

                    return 1

                # Compile the grammar
                progress.update("Compiling grammar...")

                # Create compilation script
                compile_script = self._create_compile_script(
                    language,
                    source_dir,
                    compiled_grammar,
                )

                if not compile_script:
                    progress.stop(False, "compilation setup failed")
                    click.echo("❌ Failed to set up compilation")
                    return 1

                # Execute compilation
                compile_result = self._run_command(
                    ["python", str(compile_script)],
                    cwd=source_dir,
                    timeout=120,
                )

                if compile_result[0] != 0:
                    progress.stop(False, "compilation failed")
                    click.echo(f"❌ Compilation failed: {compile_result[2]}")

                    error_result = self._handle_error(
                        compile_result[2],
                        language,
                        {"operation": "build_compile", "grammar_path": str(source_dir)},
                    )

                    if error_result.get("guidance"):
                        click.echo("\n💡 Guidance:")
                        for guidance in error_result["guidance"]:
                            click.echo(f"  • {guidance}")

                    return 1

                progress.update("Verifying build...")

                # Verify the build
                if not compiled_grammar.exists():
                    progress.stop(False, "compiled grammar not found")
                    click.echo("❌ Build completed but compiled grammar not found")
                    return 1

                # Test loading the grammar
                try:
                    import ctypes

                    lib = ctypes.CDLL(str(compiled_grammar))
                    progress.update("Grammar loadable")
                except Exception as e:
                    progress.stop(False, f"grammar not loadable: {e}")
                    click.echo(f"⚠️ Grammar built but may not be loadable: {e}")
                    return 1

                progress.stop(True, "build completed successfully")

                click.echo(f"✅ Successfully built {language} grammar!")
                click.echo(f"📁 Location: {compiled_grammar}")
                click.echo(f"📊 Size: {compiled_grammar.stat().st_size:,} bytes")
                click.echo()

                click.echo("🔄 Next steps:")
                click.echo(
                    f"  • Test grammar: treesitter-chunker grammar test {language} <file>",
                )
                click.echo(
                    f"  • Validate grammar: treesitter-chunker grammar validate {language}",
                )

                return 0

            except Exception as e:
                progress.stop(False, str(e))
                raise

        except Exception as e:
            error_result = self._handle_error(
                str(e),
                language,
                {
                    "operation": "build",
                    "grammar_path": (
                        str(source_dir) if "source_dir" in locals() else None
                    ),
                },
            )
            click.echo(f"❌ Error building grammar: {e}")

            if error_result.get("guidance"):
                click.echo("\n💡 Guidance:")
                for guidance in error_result["guidance"]:
                    click.echo(f"  • {guidance}")

            return 1

    def _create_compile_script(
        self,
        language: str,
        source_dir: Path,
        output_path: Path,
    ) -> Path | None:
        """Create compilation script for grammar.

        Args:
            language: Language name
            source_dir: Source directory
            output_path: Output path for compiled grammar

        Returns:
            Path to compile script if created successfully, None otherwise
        """
        try:
            script_content = f'''#!/usr/bin/env python3
"""Auto-generated compilation script for {language} grammar."""

import os
import sys
from pathlib import Path
from distutils.core import setup, Extension
from distutils.command.build_ext import build_ext
from distutils.util import get_platform

# Grammar source files
src_dir = Path(__file__).parent / "src"
parser_c = src_dir / "parser.c"
scanner_c = src_dir / "scanner.c"  # Optional

sources = [str(parser_c)]
if scanner_c.exists():
    sources.append(str(scanner_c))

# Extension definition
extension = Extension(
    name="tree_sitter_{language}",
    sources=sources,
    include_dirs=[str(src_dir)],
    extra_compile_args=["-std=c99"],
)

class BuildExt(build_ext):
    def build_extension(self, ext):
        # Build the extension
        build_ext.build_extension(self, ext)
        
        # Move to target location
        built_path = self.get_ext_fullpath(ext.name)
        target_path = Path("{output_path}")
        
        # Ensure target directory exists
        target_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Copy built file to target
        import shutil
        shutil.copy2(built_path, target_path)
        print(f"Grammar compiled to: {{target_path}}")

if __name__ == "__main__":
    setup(
        name="tree_sitter_{language}",
        ext_modules=[extension],
        cmdclass={{"build_ext": BuildExt}},
        script_args=["build_ext", "--inplace"],
    )
'''

            script_path = source_dir / f"compile_{language}.py"
            with open(script_path, "w") as f:
                f.write(script_content)

            script_path.chmod(0o755)
            return script_path

        except Exception as e:
            logger.error(f"Failed to create compile script: {e}")
            return None

    def remove_grammar(
        self,
        language: str,
        confirm: bool = True,
        clean_cache: bool = True,
    ) -> int:
        """Remove user-installed grammar with enhanced cleanup.

        Args:
            language: Language name
            confirm: Whether to ask for confirmation
            clean_cache: Whether to clean associated cache files

        Returns:
            Exit code (0 for success, 1 for error)
        """
        try:
            click.echo(f"🗑️ Removing Grammar: {language}")
            click.echo("=" * 50)

            # Find grammar locations
            locations_to_remove = []

            # Check user-installed source
            user_source = self.user_grammars_dir / language
            if user_source.exists():
                locations_to_remove.append(("source directory", user_source))

            # Check compiled grammar
            compiled_grammar = self.build_dir / f"tree_sitter_{language}.so"
            if compiled_grammar.exists():
                locations_to_remove.append(("compiled grammar", compiled_grammar))

            if not locations_to_remove:
                click.echo(f"❌ No user-installed grammar found for '{language}'")

                # Check if grammar exists in other locations
                grammar_info = self._find_grammar(language)
                if grammar_info:
                    _, source, priority = grammar_info
                    # Handle both core enum and fallback integer values
                    priority_val = (
                        priority.value if hasattr(priority, "value") else priority
                    )
                    if priority_val != 1:  # Not USER priority
                        click.echo(
                            f"💡 Grammar exists as {source} but cannot be removed",
                        )
                        click.echo("   Only user-installed grammars can be removed")

                return 1

            # Show what will be removed
            click.echo("The following will be removed:")
            for desc, path in locations_to_remove:
                click.echo(f"  • {desc}: {path}")
            click.echo()

            # Confirmation
            if confirm and not click.confirm(
                f"Are you sure you want to remove {language} grammar?",
            ):
                click.echo("🗑️ Removal cancelled")
                return 0

            # Remove each location
            removed_count = 0
            errors = []

            for desc, path in locations_to_remove:
                try:
                    if path.is_dir():
                        shutil.rmtree(path)
                    else:
                        path.unlink()

                    click.echo(f"✅ Removed {desc}: {path}")
                    removed_count += 1

                except Exception as e:
                    error_msg = f"Failed to remove {desc}: {e}"
                    errors.append(error_msg)
                    click.echo(f"❌ {error_msg}")

            click.echo()

            if removed_count > 0:
                click.echo(
                    f"🎉 Successfully removed {removed_count} grammar components!",
                )

            if errors:
                click.echo("⚠️ Some errors occurred:")
                for error in errors:
                    click.echo(f"  • {error}")
                return 1

            return 0

        except Exception as e:
            error_result = self._handle_error(str(e), language, {"operation": "remove"})
            click.echo(f"❌ Error removing grammar: {e}")

            if error_result.get("guidance"):
                click.echo("\n💡 Guidance:")
                for guidance in error_result["guidance"]:
                    click.echo(f"  • {guidance}")

            return 1

    def test_grammar(
        self,
        language: str,
        file_path: str,
        show_ast: bool = False,
    ) -> int:
        """Test grammar with specific file.

        Args:
            language: Language name
            file_path: Path to test file
            show_ast: Whether to show AST output

        Returns:
            Exit code (0 for success, 1 for error)
        """
        try:
            click.echo(f"🧪 Testing Grammar: {language}")
            click.echo("=" * 50)

            test_file = Path(file_path)
            if not test_file.exists():
                click.echo(f"❌ Test file not found: {file_path}")
                return 1

            # Find grammar
            grammar_info = self._find_grammar(language)
            if not grammar_info:
                click.echo(f"❌ Grammar for '{language}' not found")
                if language in self.grammar_sources:
                    click.echo(f"💡 Try: treesitter-chunker grammar fetch {language}")
                return 1

            grammar_path, source, priority = grammar_info

            click.echo(f"Test file: {file_path}")
            click.echo(f"Grammar: {grammar_path} ({source})")
            click.echo(f"File size: {test_file.stat().st_size:,} bytes")
            click.echo()

            progress = ProgressIndicator(f"Testing {language} grammar", self.verbose)
            progress.start()

            try:
                # Try to parse the file using tree-sitter
                if grammar_path.suffix == ".so":
                    # Use compiled grammar
                    result = self._test_compiled_grammar(
                        language,
                        grammar_path,
                        test_file,
                        show_ast,
                    )
                else:
                    # Use source grammar via tree-sitter CLI
                    result = self._test_source_grammar(
                        language,
                        grammar_path,
                        test_file,
                        show_ast,
                    )

                progress.stop(
                    result["success"],
                    "parsing successful" if result["success"] else "parsing failed",
                )

                if result["success"]:
                    click.echo("✅ Grammar test successful!")
                    click.echo(f"📊 Parsed {result.get('nodes', 0)} nodes")

                    if result.get("parse_time"):
                        click.echo(f"⏱️ Parse time: {result['parse_time']:.3f} seconds")

                    if show_ast and result.get("ast"):
                        click.echo("\n🌳 Abstract Syntax Tree:")
                        click.echo("-" * 30)
                        click.echo(result["ast"])

                    if result.get("errors"):
                        click.echo("\n⚠️ Parse Errors:")
                        for error in result["errors"]:
                            click.echo(f"  • {error}")
                else:
                    click.echo("❌ Grammar test failed!")
                    if result.get("error"):
                        click.echo(f"Error: {result['error']}")

                    error_result = self._handle_error(
                        result.get("error", "Grammar test failed"),
                        language,
                        {"operation": "test", "test_file": file_path},
                    )

                    if error_result.get("guidance"):
                        click.echo("\n💡 Guidance:")
                        for guidance in error_result["guidance"]:
                            click.echo(f"  • {guidance}")

                return 0 if result["success"] else 1

            except Exception as e:
                progress.stop(False, str(e))
                raise

        except Exception as e:
            error_result = self._handle_error(
                str(e),
                language,
                {"operation": "test", "test_file": file_path},
            )
            click.echo(f"❌ Error testing grammar: {e}")

            if error_result.get("guidance"):
                click.echo("\n💡 Guidance:")
                for guidance in error_result["guidance"]:
                    click.echo(f"  • {guidance}")

            return 1

    def _test_compiled_grammar(
        self,
        language: str,
        grammar_path: Path,
        test_file: Path,
        show_ast: bool,
    ) -> dict[str, Any]:
        """Test compiled grammar.

        Args:
            language: Language name
            grammar_path: Path to compiled grammar
            test_file: Path to test file
            show_ast: Whether to generate AST

        Returns:
            Dictionary with test results
        """
        try:
            # Try to use tree-sitter Python bindings if available
            try:
                import tree_sitter

                # Load the language
                language_lib = tree_sitter.Language(str(grammar_path), language)
                parser = tree_sitter.Parser()
                parser.set_language(language_lib)

                # Read test file
                with open(test_file, "rb") as f:
                    source_code = f.read()

                # Parse
                start_time = time.time()
                tree = parser.parse(source_code)
                parse_time = time.time() - start_time

                # Count nodes
                def count_nodes(node):
                    count = 1
                    for child in node.children:
                        count += count_nodes(child)
                    return count

                node_count = count_nodes(tree.root_node)

                result = {
                    "success": True,
                    "nodes": node_count,
                    "parse_time": parse_time,
                    "errors": [],
                }

                if show_ast:
                    result["ast"] = tree.root_node.sexp()

                # Check for parse errors
                def find_errors(node):
                    errors = []
                    if node.type == "ERROR":
                        errors.append(
                            f"Parse error at {node.start_point}: {node.text[:50]}",
                        )
                    for child in node.children:
                        errors.extend(find_errors(child))
                    return errors

                result["errors"] = find_errors(tree.root_node)

                return result

            except ImportError:
                # Fall back to tree-sitter CLI
                return self._test_with_cli(
                    language,
                    grammar_path.parent,
                    test_file,
                    show_ast,
                )

        except Exception as e:
            return {"success": False, "error": str(e)}

    def _test_source_grammar(
        self,
        language: str,
        grammar_path: Path,
        test_file: Path,
        show_ast: bool,
    ) -> dict[str, Any]:
        """Test source grammar using CLI.

        Args:
            language: Language name
            grammar_path: Path to grammar source directory
            test_file: Path to test file
            show_ast: Whether to generate AST

        Returns:
            Dictionary with test results
        """
        return self._test_with_cli(language, grammar_path, test_file, show_ast)

    def _test_with_cli(
        self,
        language: str,
        grammar_dir: Path,
        test_file: Path,
        show_ast: bool,
    ) -> dict[str, Any]:
        """Test grammar using tree-sitter CLI.

        Args:
            language: Language name
            grammar_dir: Grammar directory (source or build)
            test_file: Test file path
            show_ast: Whether to show AST

        Returns:
            Dictionary with test results
        """
        try:
            # Use tree-sitter parse command
            cmd = ["npx", "tree-sitter", "parse", str(test_file)]
            if show_ast:
                cmd.append("--debug")

            start_time = time.time()
            returncode, stdout, stderr = self._run_command(
                cmd,
                cwd=grammar_dir,
                timeout=30,
            )
            parse_time = time.time() - start_time

            if returncode == 0:
                # Parse was successful
                result = {"success": True, "parse_time": parse_time, "errors": []}

                # Extract node count from output if available
                lines = stdout.split("\n")
                for line in lines:
                    if "node" in line.lower():
                        # Try to extract node count
                        import re

                        numbers = re.findall(r"\d+", line)
                        if numbers:
                            result["nodes"] = int(numbers[-1])
                            break

                if show_ast:
                    result["ast"] = stdout

                # Check for error nodes in output
                if "ERROR" in stdout:
                    error_lines = [line for line in lines if "ERROR" in line]
                    result["errors"] = error_lines[:5]  # Limit to 5 errors

                return result
            return {"success": False, "error": stderr or "Parse failed"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def validate_grammar(
        self,
        language: str | None = None,
        fix: bool = False,
    ) -> int:
        """Validate grammar installation.

        Args:
            language: Specific language to validate (None for all)
            fix: Attempt to fix issues automatically

        Returns:
            Exit code (0 for success, 1 for error)
        """
        try:
            if language:
                click.echo(f"🔍 Validating Grammar: {language}")
            else:
                click.echo("🔍 Validating All Grammars")
            click.echo("=" * 50)

            grammars_to_validate = {}

            if language:
                grammar_info = self._find_grammar(language)
                if not grammar_info:
                    click.echo(f"❌ Grammar for '{language}' not found")
                    return 1
                grammars_to_validate[language] = grammar_info
            else:
                all_grammars = self._get_all_grammars()
                grammars_to_validate = {
                    lang: (Path(info["path"]), info["source"], info["priority"])
                    for lang, info in all_grammars.items()
                }

            if not grammars_to_validate:
                click.echo("❌ No grammars found to validate")
                return 1

            click.echo(f"Validating {len(grammars_to_validate)} grammar(s)...")
            click.echo()

            validation_results = {}
            overall_success = True

            for lang, (path, source, priority) in grammars_to_validate.items():
                click.echo(f"🔍 Validating {lang}...")

                result = self._validate_single_grammar(lang, path, source, fix)
                validation_results[lang] = result

                status_emoji = "✅" if result["valid"] else "❌"
                click.echo(f"  {status_emoji} {lang}: {result['status']}")

                if result["issues"]:
                    for issue in result["issues"]:
                        click.echo(f"    ⚠️ {issue}")

                if result["fixes_applied"]:
                    for fix_msg in result["fixes_applied"]:
                        click.echo(f"    🔧 {fix_msg}")

                if not result["valid"]:
                    overall_success = False

                click.echo()

            # Summary
            click.echo("📊 Validation Summary")
            click.echo("-" * 30)

            valid_count = sum(1 for r in validation_results.values() if r["valid"])
            invalid_count = len(validation_results) - valid_count

            click.echo(f"✅ Valid: {valid_count}")
            click.echo(f"❌ Invalid: {invalid_count}")

            if invalid_count > 0:
                click.echo("\n💡 Recommendations:")
                for lang, result in validation_results.items():
                    if not result["valid"] and result["recommendations"]:
                        click.echo(f"  {lang}:")
                        for rec in result["recommendations"]:
                            click.echo(f"    • {rec}")

            return 0 if overall_success else 1

        except Exception as e:
            error_result = self._handle_error(
                str(e),
                language,
                {"operation": "validate"},
            )
            click.echo(f"❌ Error validating grammar: {e}")

            if error_result.get("guidance"):
                click.echo("\n💡 Guidance:")
                for guidance in error_result["guidance"]:
                    click.echo(f"  • {guidance}")

            return 1

    def _validate_single_grammar(
        self,
        language: str,
        path: Path,
        source: str,
        fix: bool,
    ) -> dict[str, Any]:
        """Validate a single grammar.

        Args:
            language: Language name
            path: Grammar path
            source: Grammar source description
            fix: Whether to attempt fixes

        Returns:
            Dictionary with validation results
        """
        result = {
            "valid": False,
            "status": "unknown",
            "issues": [],
            "recommendations": [],
            "fixes_applied": [],
        }

        try:
            if not path.exists():
                result["status"] = "missing"
                result["issues"].append("Grammar file/directory does not exist")
                result["recommendations"].append(
                    f"Download grammar: treesitter-chunker grammar fetch {language}",
                )
                return result

            if path.suffix == ".so":
                # Validate compiled grammar
                result = self._validate_compiled_grammar(language, path, fix)
            else:
                # Validate source grammar
                result = self._validate_source_grammar(language, path, fix)

        except Exception as e:
            result["status"] = "error"
            result["issues"].append(f"Validation failed: {e}")

        return result

    def _validate_compiled_grammar(
        self,
        language: str,
        grammar_path: Path,
        fix: bool,
    ) -> dict[str, Any]:
        """Validate compiled grammar.

        Args:
            language: Language name
            grammar_path: Path to compiled grammar
            fix: Whether to attempt fixes

        Returns:
            Validation results
        """
        result = {
            "valid": False,
            "status": "unknown",
            "issues": [],
            "recommendations": [],
            "fixes_applied": [],
        }

        # Check file size
        if grammar_path.stat().st_size == 0:
            result["status"] = "corrupted"
            result["issues"].append("Grammar file is empty")
            result["recommendations"].append(
                f"Rebuild grammar: treesitter-chunker grammar build {language}",
            )
            return result

        # Try to load the grammar
        try:
            import ctypes

            lib = ctypes.CDLL(str(grammar_path))

            # Basic load test passed
            result["valid"] = True
            result["status"] = "healthy"

        except Exception as e:
            result["status"] = "corrupted"
            result["issues"].append(f"Grammar is not loadable: {e}")
            result["recommendations"].append(
                f"Rebuild grammar: treesitter-chunker grammar build {language}",
            )

            if fix:
                # Attempt to fix by rebuilding
                try:
                    click.echo(f"    🔧 Attempting to rebuild {language}...")
                    build_result = self.build_grammar(language, force=True)
                    if build_result == 0:
                        result["fixes_applied"].append("Grammar rebuilt successfully")
                        result["valid"] = True
                        result["status"] = "fixed"
                    else:
                        result["fixes_applied"].append("Grammar rebuild failed")
                except Exception as fix_error:
                    result["fixes_applied"].append(f"Fix attempt failed: {fix_error}")

        return result

    def _validate_source_grammar(
        self,
        language: str,
        source_path: Path,
        fix: bool,
    ) -> dict[str, Any]:
        """Validate source grammar.

        Args:
            language: Language name
            source_path: Path to source directory
            fix: Whether to attempt fixes

        Returns:
            Validation results
        """
        result = {
            "valid": False,
            "status": "unknown",
            "issues": [],
            "recommendations": [],
            "fixes_applied": [],
        }

        # Check required files
        grammar_js = source_path / "grammar.js"
        package_json = source_path / "package.json"
        src_dir = source_path / "src"

        if not grammar_js.exists():
            result["issues"].append("Missing grammar.js file")

        if not (package_json.exists() or src_dir.exists()):
            result["issues"].append("Missing package.json or src/ directory")

        if result["issues"]:
            result["status"] = "incompatible"
            result["recommendations"].append(
                f"Re-fetch grammar: treesitter-chunker grammar fetch {language}",
            )
            return result

        # Check if parser files exist
        if src_dir.exists():
            parser_c = src_dir / "parser.c"
            if not parser_c.exists():
                result["issues"].append("Missing generated parser.c file")
                result["recommendations"].append(
                    f"Build grammar: treesitter-chunker grammar build {language}",
                )

                if fix:
                    # Attempt to generate parser files
                    try:
                        click.echo(
                            f"    🔧 Attempting to generate parser for {language}...",
                        )
                        generate_cmd = ["npx", "tree-sitter", "generate"]
                        returncode, stdout, stderr = self._run_command(
                            generate_cmd,
                            cwd=source_path,
                        )

                        if returncode == 0:
                            result["fixes_applied"].append(
                                "Parser files generated successfully",
                            )
                            if parser_c.exists():
                                result["valid"] = True
                                result["status"] = "fixed"
                        else:
                            result["fixes_applied"].append(
                                f"Parser generation failed: {stderr}",
                            )
                    except Exception as fix_error:
                        result["fixes_applied"].append(
                            f"Fix attempt failed: {fix_error}",
                        )
            else:
                result["valid"] = True
                result["status"] = "healthy"
        else:
            result["valid"] = True
            result["status"] = "healthy"

        return result

    def export_grammars(self, output_file: str, format: str = "json") -> int:
        """Export grammar configurations to file.

        Args:
            output_file: Output file path
            format: Export format (json, yaml)

        Returns:
            Exit code (0 for success, 1 for error)
        """
        try:
            click.echo("📤 Exporting Grammar Configurations")
            click.echo("=" * 50)

            if self.grammar_manager:
                grammars = self.grammar_manager.discover_available_grammars()
            else:
                grammars = self._get_all_grammars_fallback()

            if not grammars:
                click.echo("❌ No grammars found to export")
                return 1

            output_path = Path(output_file)

            # Prepare export data
            export_data = {
                "exported_at": time.time(),
                "version": "1.0",
                "grammars": grammars,
                "sources": self.grammar_sources,
            }

            # Export in requested format
            if format == "json":
                with output_path.open("w") as f:
                    import json

                    json.dump(export_data, f, indent=2, default=str)
            elif format == "yaml":
                try:
                    import yaml

                    with output_path.open("w") as f:
                        yaml.dump(export_data, f, default_flow_style=False)
                except ImportError:
                    click.echo(
                        "❌ PyYAML not installed. Install with: pip install pyyaml",
                    )
                    return 1
            else:
                click.echo(f"❌ Invalid format: {format}")
                return 1

            click.echo(f"✅ Exported {len(grammars)} grammars to {output_path}")
            return 0

        except Exception as e:
            click.echo(f"❌ Export failed: {e}")
            return 1

    def cleanup_cache(self, older_than_days: int = 7) -> int:
        """Clean up old cache files.

        Args:
            older_than_days: Remove cache files older than this many days

        Returns:
            Exit code (0 for success, 1 for error)
        """
        try:
            click.echo(f"🧹 Cleaning Up Cache (older than {older_than_days} days)")
            click.echo("=" * 50)

            if self.grammar_manager:
                stats = self.grammar_manager.cleanup_cache(older_than_days)
            else:
                # Fallback cleanup
                stats = self._cleanup_cache_fallback(older_than_days)

            click.echo("✅ Cleanup completed:")
            click.echo(f"  • Files removed: {stats.get('files_removed', 0)}")
            click.echo(
                f"  • Space freed: {stats.get('bytes_freed', 0) / 1024 / 1024:.2f} MB",
            )

            if stats.get("directories_cleaned"):
                click.echo(
                    f"  • Directories cleaned: {', '.join(stats['directories_cleaned'])}",
                )

            if stats.get("errors"):
                click.echo("\n⚠️ Some errors occurred:")
                for error in stats["errors"]:
                    click.echo(f"  • {error}")
                return 1

            return 0

        except Exception as e:
            click.echo(f"❌ Cache cleanup failed: {e}")
            return 1

    def _cleanup_cache_fallback(self, older_than_days: int) -> dict[str, Any]:
        """Fallback cache cleanup method.

        Args:
            older_than_days: Days threshold

        Returns:
            Cleanup statistics
        """
        stats = {
            "files_removed": 0,
            "bytes_freed": 0,
            "directories_cleaned": [],
            "errors": [],
        }

        cutoff_time = time.time() - (older_than_days * 24 * 60 * 60)

        # Clean specific cache directories
        cache_dirs = [
            self.cache_dir / "downloads",
            self.cache_dir / "builds",
            self.cache_dir / "tmp",
        ]

        for cache_dir in cache_dirs:
            if cache_dir.exists():
                try:
                    for item in cache_dir.iterdir():
                        try:
                            item_stat = item.stat()
                            if item_stat.st_mtime < cutoff_time:
                                if item.is_file():
                                    stats["bytes_freed"] += item_stat.st_size
                                    item.unlink()
                                    stats["files_removed"] += 1
                                elif item.is_dir():
                                    stats["bytes_freed"] += sum(
                                        f.stat().st_size
                                        for f in item.rglob("*")
                                        if f.is_file()
                                    )
                                    shutil.rmtree(item)
                                    stats["files_removed"] += 1
                        except Exception as e:
                            stats["errors"].append(f"Failed to clean {item}: {e}")

                    if stats["files_removed"] > 0:
                        stats["directories_cleaned"].append(cache_dir.name)

                except Exception as e:
                    stats["errors"].append(f"Failed to access {cache_dir}: {e}")

        return stats


# Click CLI Interface


@click.group(name="grammar")
@click.option("--cache-dir", type=click.Path(), help="Grammar cache directory")
@click.option("--verbose", is_flag=True, help="Enable verbose output")
@click.pass_context
def grammar_cli(ctx, cache_dir, verbose):
    """Comprehensive grammar management for treesitter-chunker."""
    ctx.ensure_object(dict)
    ctx.obj["cache_dir"] = Path(cache_dir) if cache_dir else None
    ctx.obj["verbose"] = verbose
    ctx.obj["cli"] = ComprehensiveGrammarCLI(
        cache_dir=ctx.obj["cache_dir"],
        verbose=verbose,
    )


@grammar_cli.command()
@click.option("--language", help="Filter by language")
@click.option("--all", "show_all", is_flag=True, help="Show all priority levels")
@click.pass_context
def list(ctx, language, show_all):
    """List available and user-installed grammars."""
    cli = ctx.obj["cli"]
    sys.exit(cli.list_grammars(language, show_all))


@grammar_cli.command()
@click.argument("language")
@click.pass_context
def info(ctx, language):
    """Show grammar details and compatibility information."""
    cli = ctx.obj["cli"]
    sys.exit(cli.info_grammar(language))


@grammar_cli.command()
@click.argument("language")
@click.pass_context
def versions(ctx, language):
    """List available versions for a language."""
    cli = ctx.obj["cli"]
    sys.exit(cli.versions_grammar(language))


@grammar_cli.command()
@click.argument("language")
@click.option("--version", help="Specific version/tag to fetch")
@click.option("--branch", default="main", help="Branch to fetch")
@click.option("--force", is_flag=True, help="Force re-download")
@click.pass_context
def fetch(ctx, language, version, branch, force):
    """Download specific grammar version."""
    cli = ctx.obj["cli"]
    sys.exit(cli.fetch_grammar(language, version, branch, force))


@grammar_cli.command()
@click.argument("language")
@click.option("--force", is_flag=True, help="Force rebuild")
@click.pass_context
def build(ctx, language, force):
    """Build grammar from source."""
    cli = ctx.obj["cli"]
    sys.exit(cli.build_grammar(language, force))


@grammar_cli.command()
@click.argument("language")
@click.option("--no-confirm", is_flag=True, help="Skip confirmation")
@click.pass_context
def remove(ctx, language, no_confirm):
    """Remove user-installed grammar."""
    cli = ctx.obj["cli"]
    sys.exit(cli.remove_grammar(language, not no_confirm))


@grammar_cli.command()
@click.argument("language")
@click.argument("file_path")
@click.option("--ast", is_flag=True, help="Show AST output")
@click.pass_context
def test(ctx, language, file_path, ast):
    """Test grammar with specific file."""
    cli = ctx.obj["cli"]
    sys.exit(cli.test_grammar(language, file_path, ast))


@grammar_cli.command()
@click.argument("language", required=False)
@click.option("--fix", is_flag=True, help="Attempt to fix issues")
@click.option(
    "--level",
    default="standard",
    type=click.Choice(["basic", "standard", "extensive"]),
    help="Validation level",
)
@click.option(
    "--format",
    "output_format",
    default="table",
    type=click.Choice(["table", "json", "yaml"]),
    help="Output format",
)
@click.pass_context
def validate(ctx, language, fix, level, output_format):
    """Validate grammar installation with comprehensive testing."""
    cli = ctx.obj["cli"]
    sys.exit(cli.validate_grammar(language, fix, level, output_format))


@grammar_cli.command()
@click.argument("output_file")
@click.option(
    "--format",
    default="json",
    type=click.Choice(["json", "yaml"]),
    help="Export format",
)
@click.pass_context
def export(ctx, output_file, format):
    """Export grammar configurations to file."""
    cli = ctx.obj["cli"]
    sys.exit(cli.export_grammars(output_file, format))


@grammar_cli.command(name="cleanup")
@click.option(
    "--days",
    default=7,
    type=int,
    help="Remove cache files older than N days",
)
@click.pass_context
def cleanup_cmd(ctx, days):
    """Clean up old cache files."""
    cli = ctx.obj["cli"]
    sys.exit(cli.cleanup_cache(days))


if __name__ == "__main__":
    grammar_cli()

"""
User experience enhancement module for Phase 1.9 production-ready integration.
"""

import json
import logging
import os
import shutil
import sys
import textwrap
import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable
from contextlib import contextmanager
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

# Import from Phase 1.7 and 1.8
from ..error_handling import ErrorHandlingPipeline, UserGuidanceEngine
from ..grammar_management import GrammarManager, UserConfig

# Import from Phase 1.9 tasks
from .core_integration import SystemIntegrator
from .performance_optimizer import PerformanceOptimizer

logger = logging.getLogger(__name__)


class InteractionMode(Enum):
    """User interaction modes."""

    CLI = "cli"
    PROGRAMMATIC = "programmatic"
    INTERACTIVE = "interactive"
    SILENT = "silent"


class FeedbackLevel(Enum):
    """Feedback verbosity levels."""

    MINIMAL = "minimal"
    NORMAL = "normal"
    DETAILED = "detailed"
    DEBUG = "debug"


class UserExperienceManager:
    """Manages user experience enhancements for the integrated system."""

    def __init__(self, config: dict[str, Any] | None = None):
        """Initialize user experience manager."""
        self.config = config or {}
        self.interaction_mode = InteractionMode(
            self.config.get("interaction_mode", InteractionMode.CLI.value),
        )
        self.feedback_level = FeedbackLevel(
            self.config.get("feedback_level", FeedbackLevel.NORMAL.value),
        )

        # Core components
        self.system_integrator = SystemIntegrator.get_instance()
        self.performance_optimizer = PerformanceOptimizer(
            self.config.get("performance", {}),
        )

        # UX components
        self.interactive_setup = InteractiveSetup(self)
        self.smart_suggestions = SmartSuggestions(self)
        self.progress_tracker = ProgressTracker(self)
        self.feedback_collector = FeedbackCollector(self)
        self.help_system = HelpSystem(self)

        # State management
        self._operation_history = deque(maxlen=100)
        self._error_patterns = defaultdict(int)
        self._user_preferences = {}
        self._session_start = time.time()
        self._lock = threading.RLock()

        logger.info("UserExperienceManager initialized")

    def setup_first_run(self) -> dict[str, Any]:
        """Run first-time setup wizard."""
        with self._lock:
            if self.interaction_mode == InteractionMode.SILENT:
                return self._auto_configure()

            return self.interactive_setup.run_wizard()

    def _auto_configure(self) -> dict[str, Any]:
        """Auto-configure with smart defaults."""
        config = {
            "grammar_source": "auto",
            "cache_enabled": True,
            "auto_update": False,
            "performance_mode": "balanced",
            "error_verbosity": "normal",
        }

        # Save configuration
        user_config = UserConfig()
        for key, value in config.items():
            user_config.set(f"ux.{key}", value)

        return {"status": "configured", "method": "auto", "config": config}

    def execute_with_feedback(
        self,
        operation: Callable,
        operation_name: str,
        *args,
        **kwargs,
    ) -> Any:
        """Execute operation with rich feedback."""
        with self._lock:
            # Start progress tracking
            progress_id = self.progress_tracker.start_operation(
                operation_name,
                self.feedback_level,
            )

            try:
                # Execute operation
                start_time = time.time()
                result = operation(*args, **kwargs)
                duration = time.time() - start_time

                # Record success
                self._operation_history.append(
                    {
                        "operation": operation_name,
                        "status": "success",
                        "duration": duration,
                        "timestamp": datetime.now().isoformat(),
                    },
                )

                # Complete progress
                self.progress_tracker.complete_operation(
                    progress_id,
                    "success",
                    duration,
                )

                return result

            except Exception as e:
                # Record error
                self._operation_history.append(
                    {
                        "operation": operation_name,
                        "status": "error",
                        "error": str(e),
                        "timestamp": datetime.now().isoformat(),
                    },
                )

                # Track error pattern
                self._error_patterns[type(e).__name__] += 1

                # Get user-friendly error message
                friendly_error = self._get_friendly_error(e, operation_name)

                # Complete progress with error
                self.progress_tracker.complete_operation(
                    progress_id,
                    "error",
                    time.time() - start_time,
                )

                # Show error with suggestions
                self._show_error_with_suggestions(friendly_error)

                raise

    def _get_friendly_error(self, error: Exception, operation: str) -> dict[str, Any]:
        """Convert technical error to user-friendly message."""
        error_type = type(error).__name__

        friendly_messages = {
            "FileNotFoundError": "The required file or directory doesn't exist",
            "PermissionError": "Permission denied - check file permissions",
            "ConnectionError": "Network connection failed - check your internet",
            "ValueError": "Invalid input provided - check your parameters",
            "KeyError": "Required configuration missing",
            "ImportError": "Required dependency not installed",
        }

        return {
            "message": friendly_messages.get(error_type, str(error)),
            "operation": operation,
            "type": error_type,
            "suggestions": self.smart_suggestions.get_error_suggestions(error),
            "documentation": self.help_system.get_error_help(error_type),
        }

    def _show_error_with_suggestions(self, error_info: dict[str, Any]) -> None:
        """Display error with helpful suggestions."""
        if self.interaction_mode == InteractionMode.SILENT:
            return

        print("\n" + "=" * 60)
        print("❌ Operation Failed")
        print("=" * 60)
        print(f"Operation: {error_info['operation']}")
        print(f"Error: {error_info['message']}")

        if error_info["suggestions"]:
            print("\n💡 Suggestions:")
            for i, suggestion in enumerate(error_info["suggestions"], 1):
                print(f"  {i}. {suggestion}")

        if error_info["documentation"]:
            print(f"\n📚 Documentation: {error_info['documentation']}")

        print("=" * 60 + "\n")

    def get_simplified_api(self) -> "SimplifiedAPI":
        """Get simplified API for common operations."""
        return SimplifiedAPI(self)

    def show_performance_insights(self) -> None:
        """Display performance insights and recommendations."""
        report = self.performance_optimizer.get_performance_report()

        if self.interaction_mode != InteractionMode.SILENT:
            print("\n" + "=" * 60)
            print("📊 Performance Insights")
            print("=" * 60)

            # System health
            health = report.get("health_score", 0)
            health_emoji = "🟢" if health > 0.8 else "🟡" if health > 0.5 else "🔴"
            print(f"{health_emoji} System Health: {health:.0%}")

            # Key metrics
            print("\n📈 Key Metrics:")
            metrics = report.get("metrics", {})
            print(f"  • Cache Hit Rate: {metrics.get('cache_hit_rate', 0):.1%}")
            print(f"  • Avg Response Time: {metrics.get('avg_response_time', 0):.2f}s")
            print(f"  • Memory Usage: {metrics.get('memory_usage_mb', 0):.0f} MB")

            # Recommendations
            if report.get("recommendations"):
                print("\n💡 Recommendations:")
                for rec in report["recommendations"][:3]:
                    print(f"  • {rec}")

            print("=" * 60 + "\n")

    def collect_feedback(self, category: str, feedback: str) -> None:
        """Collect user feedback."""
        self.feedback_collector.add_feedback(category, feedback)

    def show_help(self, topic: str | None = None) -> None:
        """Show context-sensitive help."""
        help_content = self.help_system.get_help(topic)

        if self.interaction_mode != InteractionMode.SILENT:
            print(help_content)


class InteractiveSetup:
    """Interactive setup wizard for first-run configuration."""

    def __init__(self, manager: UserExperienceManager):
        """Initialize interactive setup."""
        self.manager = manager
        self.config_steps = [
            self._configure_grammar_source,
            self._configure_performance,
            self._configure_caching,
            self._configure_error_handling,
            self._configure_updates,
        ]

    def run_wizard(self) -> dict[str, Any]:
        """Run the interactive setup wizard."""
        print("\n" + "=" * 60)
        print("🚀 Tree-sitter Chunker Setup Wizard")
        print("=" * 60)
        print("Let's configure your grammar management system.\n")

        config = {}

        for step in self.config_steps:
            step_config = step()
            config.update(step_config)

        # Save configuration
        self._save_configuration(config)

        print("\n✅ Setup complete! Your configuration has been saved.")
        print("=" * 60 + "\n")

        return {"status": "configured", "method": "interactive", "config": config}

    def _configure_grammar_source(self) -> dict[str, Any]:
        """Configure grammar source preference."""
        print("\n📦 Grammar Source Configuration")
        print("-" * 40)
        print("Where should grammars be loaded from?")
        print("1. User directory (highest priority)")
        print("2. Package directory")
        print("3. Auto-download from GitHub")
        print("4. Automatic (try all sources)")

        choice = self._get_choice(1, 4, default=4)

        sources = {1: "user", 2: "package", 3: "github", 4: "auto"}

        return {"grammar_source": sources[choice]}

    def _configure_performance(self) -> dict[str, Any]:
        """Configure performance preferences."""
        print("\n⚡ Performance Configuration")
        print("-" * 40)
        print("Choose performance mode:")
        print("1. Conservative (low resource usage)")
        print("2. Balanced (recommended)")
        print("3. Aggressive (maximum performance)")

        choice = self._get_choice(1, 3, default=2)

        modes = {1: "conservative", 2: "balanced", 3: "aggressive"}

        return {"performance_mode": modes[choice]}

    def _get_choice(self, min_val: int, max_val: int, default: int) -> int:
        """Get user choice within range."""
        while True:
            try:
                response = input(
                    f"Enter choice ({min_val}-{max_val}, default {default}): ",
                ).strip()
                if not response:
                    return default
                choice = int(response)
                if min_val <= choice <= max_val:
                    return choice
                print(f"Please enter a number between {min_val} and {max_val}")
            except ValueError:
                print("Please enter a valid number")
            except KeyboardInterrupt:
                print("\nSetup cancelled")
                return default

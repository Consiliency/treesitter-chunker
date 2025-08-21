"""Configuration and settings for the error handling system.

This module provides configuration management for the Phase 1.7 error handling
system. It defines default settings, configuration validation, and provides
a centralized way to manage system behavior.

Group D and E agents will use this configuration to customize error handling
behavior, user guidance preferences, and system integration settings.
"""

import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class LogLevel(Enum):
    """Logging levels for the error handling system."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ErrorReportingLevel(Enum):
    """Levels of error reporting detail."""

    MINIMAL = "minimal"  # Basic error messages only
    STANDARD = "standard"  # Standard error + basic guidance
    DETAILED = "detailed"  # Full error analysis + detailed guidance
    DEBUG = "debug"  # Full error analysis + debug information


class UserGuidanceStyle(Enum):
    """Styles of user guidance presentation."""

    CONCISE = "concise"  # Short, actionable steps
    DETAILED = "detailed"  # Comprehensive explanations
    INTERACTIVE = "interactive"  # Step-by-step guidance
    AUTOMATIC = "automatic"  # Automatic problem resolution


@dataclass
class ErrorHandlingConfig:
    """Configuration for the error handling system."""

    # Logging configuration
    log_level: LogLevel = LogLevel.INFO
    log_file: Path | None = None
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # Error reporting configuration
    error_reporting_level: ErrorReportingLevel = ErrorReportingLevel.STANDARD
    include_stack_traces: bool = True
    include_context_info: bool = True
    max_error_context_lines: int = 10

    # User guidance configuration
    guidance_style: UserGuidanceStyle = UserGuidanceStyle.STANDARD
    max_guidance_steps: int = 5
    include_examples: bool = True
    include_links: bool = True

    # Compatibility checking configuration
    enable_version_detection: bool = True
    enable_compatibility_checking: bool = True
    strict_mode: bool = False
    fallback_to_basic_errors: bool = True

    # Performance configuration
    max_analysis_time: float = 30.0  # seconds
    cache_error_patterns: bool = True
    max_cached_patterns: int = 1000

    # Integration configuration
    auto_integrate_with_chunker: bool = True
    provide_fallback_handling: bool = True
    enable_error_analytics: bool = False

    # File paths and directories
    config_file: Path | None = None
    cache_directory: Path | None = None
    template_directory: Path | None = None

    def __post_init__(self):
        """Validate configuration after initialization."""
        self._validate_config()
        self._setup_defaults()

    def _validate_config(self):
        """Validate configuration values."""
        if self.max_guidance_steps < 1 or self.max_guidance_steps > 20:
            raise ValueError("max_guidance_steps must be between 1 and 20")

        if self.max_analysis_time < 1.0 or self.max_analysis_time > 300.0:
            raise ValueError("max_analysis_time must be between 1.0 and 300.0 seconds")

        if self.max_cached_patterns < 100 or self.max_cached_patterns > 10000:
            raise ValueError("max_cached_patterns must be between 100 and 10000")

    def _setup_defaults(self):
        """Set up default values for optional paths."""
        if self.cache_directory is None:
            self.cache_directory = (
                Path.home() / ".cache" / "treesitter-chunker" / "error_handling"
            )

        if self.template_directory is None:
            self.template_directory = Path(__file__).parent / "templates"

    def to_dict(self) -> dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            "log_level": self.log_level.value,
            "log_file": str(self.log_file) if self.log_file else None,
            "log_format": self.log_format,
            "error_reporting_level": self.error_reporting_level.value,
            "include_stack_traces": self.include_stack_traces,
            "include_context_info": self.include_context_info,
            "max_error_context_lines": self.max_error_context_lines,
            "guidance_style": self.guidance_style.value,
            "max_guidance_steps": self.max_guidance_steps,
            "include_examples": self.include_examples,
            "include_links": self.include_links,
            "enable_version_detection": self.enable_version_detection,
            "enable_compatibility_checking": self.enable_compatibility_checking,
            "strict_mode": self.strict_mode,
            "fallback_to_basic_errors": self.fallback_to_basic_errors,
            "max_analysis_time": self.max_analysis_time,
            "cache_error_patterns": self.cache_error_patterns,
            "max_cached_patterns": self.max_cached_patterns,
            "auto_integrate_with_chunker": self.auto_integrate_with_chunker,
            "provide_fallback_handling": self.provide_fallback_handling,
            "enable_error_analytics": self.enable_error_analytics,
            "config_file": str(self.config_file) if self.config_file else None,
            "cache_directory": str(self.cache_directory),
            "template_directory": str(self.template_directory),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ErrorHandlingConfig":
        """Create configuration from dictionary."""
        # Convert enum values back to enum instances
        if "log_level" in data:
            data["log_level"] = LogLevel(data["log_level"])
        if "error_reporting_level" in data:
            data["error_reporting_level"] = ErrorReportingLevel(
                data["error_reporting_level"],
            )
        if "guidance_style" in data:
            data["guidance_style"] = UserGuidanceStyle(data["guidance_style"])

        # Convert string paths back to Path objects
        if data.get("log_file"):
            data["log_file"] = Path(data["log_file"])
        if data.get("config_file"):
            data["config_file"] = Path(data["config_file"])
        if "cache_directory" in data:
            data["cache_directory"] = Path(data["cache_directory"])
        if "template_directory" in data:
            data["template_directory"] = Path(data["template_directory"])

        return cls(**data)

    def save_to_file(self, file_path: Path) -> None:
        """Save configuration to file."""
        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, "w") as f:
                json.dump(self.to_dict(), f, indent=2)
            logger.info(f"Configuration saved to {file_path}")
        except Exception as e:
            logger.error(f"Failed to save configuration to {file_path}: {e}")
            raise

    @classmethod
    def load_from_file(cls, file_path: Path) -> "ErrorHandlingConfig":
        """Load configuration from file."""
        try:
            with open(file_path) as f:
                data = json.load(f)
            config = cls.from_dict(data)
            logger.info(f"Configuration loaded from {file_path}")
            return config
        except Exception as e:
            logger.error(f"Failed to load configuration from {file_path}: {e}")
            raise

    def get_default_config(self) -> "ErrorHandlingConfig":
        """Get a copy of the default configuration."""
        return ErrorHandlingConfig()


# Default configuration instance
DEFAULT_CONFIG = ErrorHandlingConfig()


# Configuration validation functions
def validate_config(config: ErrorHandlingConfig) -> list[str]:
    """Validate configuration and return list of validation errors."""
    errors = []

    try:
        config._validate_config()
    except ValueError as e:
        errors.append(str(e))

    # Additional validation logic can be added here

    return errors


def create_config_from_env() -> ErrorHandlingConfig:
    """Create configuration from environment variables."""
    import os

    config = ErrorHandlingConfig()

    # Override with environment variables if present
    if "ERROR_HANDLING_LOG_LEVEL" in os.environ:
        try:
            config.log_level = LogLevel(os.environ["ERROR_HANDLING_LOG_LEVEL"])
        except ValueError:
            logger.warning(
                f"Invalid log level: {os.environ['ERROR_HANDLING_LOG_LEVEL']}",
            )

    if "ERROR_HANDLING_REPORTING_LEVEL" in os.environ:
        try:
            config.error_reporting_level = ErrorReportingLevel(
                os.environ["ERROR_HANDLING_REPORTING_LEVEL"],
            )
        except ValueError:
            logger.warning(
                f"Invalid reporting level: {os.environ['ERROR_HANDLING_REPORTING_LEVEL']}",
            )

    if "ERROR_HANDLING_GUIDANCE_STYLE" in os.environ:
        try:
            config.guidance_style = UserGuidanceStyle(
                os.environ["ERROR_HANDLING_GUIDANCE_STYLE"],
            )
        except ValueError:
            logger.warning(
                f"Invalid guidance style: {os.environ['ERROR_HANDLING_GUIDANCE_STYLE']}",
            )

    return config

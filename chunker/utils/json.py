"""JSON and configuration file utilities.

This module provides safe JSON loading with clear error reporting.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from chunker.exceptions import ConfigurationError

logger = logging.getLogger(__name__)


def load_json_file(path: Path | str) -> dict[str, Any]:
    """Load and parse a JSON file with clear error reporting.

    Provides detailed error messages for common failure modes including
    file not found, permission errors, and JSON syntax errors.

    Args:
        path: Path to the JSON file.

    Returns:
        Parsed JSON data as a dictionary.

    Raises:
        ConfigurationError: If the file cannot be read or contains invalid JSON.

    Example:
        >>> config = load_json_file(Path("config.json"))
        >>> settings = load_json_file("/etc/app/settings.json")
    """
    path = Path(path) if isinstance(path, str) else path

    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error("Configuration file not found: %s", path)
        raise ConfigurationError(f"Configuration file not found: {path}", path) from None
    except PermissionError:
        logger.error("Permission denied reading configuration file: %s", path)
        raise ConfigurationError(
            f"Permission denied reading configuration file: {path}", path,
        ) from None
    except json.JSONDecodeError as e:
        logger.error("Invalid JSON in %s: %s (line %d, column %d)", path, e.msg, e.lineno, e.colno)
        raise ConfigurationError(
            f"Invalid JSON in {path}: {e.msg} (line {e.lineno}, column {e.colno})",
            path,
        ) from e
    except UnicodeDecodeError as e:
        logger.error("Invalid encoding in %s: %s", path, e)
        raise ConfigurationError(f"Invalid encoding in {path}: {e}", path) from e


def load_json_string(content: str, source: str = "<string>") -> dict[str, Any]:
    """Parse JSON from a string with clear error reporting.

    Args:
        content: JSON string to parse.
        source: Description of the source for error messages.

    Returns:
        Parsed JSON data as a dictionary.

    Raises:
        ConfigurationError: If the string contains invalid JSON.
    """
    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        logger.error("Invalid JSON from %s: %s (line %d, column %d)", source, e.msg, e.lineno, e.colno)
        raise ConfigurationError(
            f"Invalid JSON from {source}: {e.msg} (line {e.lineno}, column {e.colno})",
        ) from e


def safe_json_loads(content: str, default: dict[str, Any] | None = None) -> dict[str, Any]:
    """Parse JSON with a default fallback for invalid content.

    Unlike load_json_string, this function returns a default value instead of
    raising an exception on parse errors. Useful for optional configuration.

    Args:
        content: JSON string to parse.
        default: Default value to return on parse error (default: empty dict).

    Returns:
        Parsed JSON data, or the default value if parsing fails.
    """
    if default is None:
        default = {}

    try:
        result = json.loads(content)
        return result if isinstance(result, dict) else default
    except (json.JSONDecodeError, TypeError):
        logger.debug("Failed to parse JSON, using default")
        return default

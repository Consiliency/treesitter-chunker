"""Interface definitions for Phase 7 integration tests.

These interfaces ensure consistent cross-module testing across all parallel worktrees.
The integration coordinator worktree implements the full versions of these interfaces.
"""

import time
from typing import Any


class ErrorPropagationMixin:
    """Mixin for tracking error propagation across module boundaries."""

    def capture_cross_module_error(
        self,
        source_module: str,
        target_module: str,
        error: Exception,
    ) -> dict[str, Any]:
        """Capture error with full context."""
        return {
            "source_module": source_module,
            "target_module": target_module,
            "operation": self.__class__.__name__,
            "original_error": error,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "timestamp": time.time(),
            "context_data": {
                "traceback": self._get_traceback(error),
                "call_stack": self._get_call_stack(),
            },
        }

    def verify_error_context(
        self,
        error: dict[str, Any],
        expected_context: dict[str, Any],
    ) -> None:
        """Verify error has expected context."""
        for key, value in expected_context.items():
            assert key in error, f"Missing context key: {key}"
            if key != "timestamp":  # Don't check exact timestamp
                assert (
                    error[key] == value
                ), f"Context mismatch for {key}: {error[key]} != {value}"

    def _get_traceback(self, error: Exception) -> list[str]:
        """Extract traceback information."""
        import traceback

        return traceback.format_exception(type(error), error, error.__traceback__)

    def _get_call_stack(self) -> list[str]:
        """Get current call stack."""
        import inspect

        return [
            f"{frame.filename}:{frame.lineno} in {frame.function}"
            for frame in inspect.stack()[2:]
        ]  # Skip this method and caller


class ConfigChangeObserver:
    """Observer for configuration changes during runtime."""

    def __init__(self):
        self._observers = []
        self._change_log = []
        self._module_config_map = {
            "chunk_types": ["chunker", "languages"],
            "parser_timeout": ["parser", "factory"],
            "cache_dir": ["cache", "streaming"],
            "num_workers": ["parallel"],
            "plugin_dirs": ["plugin_manager"],
        }

    def on_config_change(
        self,
        config_key: str,
        old_value: Any,
        new_value: Any,
    ) -> dict[str, Any]:
        """Record config change event."""
        event = {
            "config_path": config_key,
            "old_value": old_value,
            "new_value": new_value,
            "affected_modules": self.get_affected_modules(config_key),
            "timestamp": time.time(),
        }
        self._change_log.append(event)
        self._notify_observers(event)
        return event

    def get_affected_modules(self, config_key: str) -> list[str]:
        """Determine which modules are affected by config change."""
        # Check direct mappings
        if config_key in self._module_config_map:
            return self._module_config_map[config_key]

        # Check nested keys (e.g., 'languages.python.chunk_types')
        for key, modules in self._module_config_map.items():
            if key in config_key:
                return modules

        # Default: all modules potentially affected
        return ["parser", "chunker", "cache", "parallel", "plugin_manager"]

    def register_observer(self, callback):
        """Register callback for config changes."""
        self._observers.append(callback)

    def _notify_observers(self, event: dict[str, Any]):
        """Notify all registered observers."""
        for observer in self._observers:
            observer(event)

    def get_change_log(self) -> list[dict[str, Any]]:
        """Get all recorded changes."""
        return self._change_log.copy()


class ResourceTracker:
    """Track resource allocation and cleanup across modules."""

    def __init__(self):
        self._resources = {}
        self._allocation_order = []

    def track_resource(
        self,
        module: str,
        resource_type: str,
        resource_id: str,
    ) -> dict[str, Any]:
        """Track a new resource allocation."""
        resource = {
            "resource_id": resource_id,
            "resource_type": resource_type,
            "owner_module": module,
            "created_at": time.time(),
            "state": "active",
            "metadata": {},
        }
        self._resources[resource_id] = resource
        self._allocation_order.append(resource_id)
        return resource

    def release_resource(self, resource_id: str) -> None:
        """Mark resource as released."""
        if resource_id in self._resources:
            self._resources[resource_id]["state"] = "released"
            self._resources[resource_id]["released_at"] = time.time()

    def verify_cleanup(self, module: str) -> list[dict[str, Any]]:
        """Verify all resources for module are cleaned up."""
        leaked = []
        for resource in self._resources.values():
            if resource["owner_module"] == module and resource["state"] == "active":
                leaked.append(resource)
        return leaked

    def get_resource_state(self, resource_id: str) -> dict[str, Any] | None:
        """Get current state of a resource."""
        return self._resources.get(resource_id)

    def get_all_resources(
        self,
        module: str | None = None,
        state: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get resources filtered by module and/or state."""
        resources = list(self._resources.values())
        if module:
            resources = [r for r in resources if r["owner_module"] == module]
        if state:
            resources = [r for r in resources if r["state"] == state]
        return resources

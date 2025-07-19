"""Interface definitions for Phase 7 integration tests.

These interfaces ensure consistent cross-module testing across all parallel worktrees.
The integration coordinator worktree will implement the full versions of these interfaces.
"""

from typing import Any, Dict, List, Optional


class ErrorPropagationMixin:
    """Mixin for tracking error propagation across module boundaries.
    
    This interface ensures consistent error context tracking and verification
    across all integration tests.
    """
    
    def capture_cross_module_error(self, source_module: str, target_module: str, 
                                   error: Exception) -> Dict[str, Any]:
        """Capture error with full context for cross-module propagation testing.
        
        Args:
            source_module: Module where error originated (e.g., 'chunker.parallel')
            target_module: Module receiving the error (e.g., 'cli.main')
            error: The original exception
            
        Returns:
            Dictionary with error context including timestamp and metadata
        """
        # TO BE IMPLEMENTED BY COORDINATOR WORKTREE
        raise NotImplementedError("Coordinator worktree will implement this")
    
    def verify_error_context(self, error: Dict[str, Any], 
                            expected_context: Dict[str, Any]) -> None:
        """Verify error contains expected context information.
        
        Args:
            error: Captured error dictionary
            expected_context: Expected context keys and values
            
        Raises:
            AssertionError: If context doesn't match expectations
        """
        # TO BE IMPLEMENTED BY COORDINATOR WORKTREE
        raise NotImplementedError("Coordinator worktree will implement this")


class ConfigChangeObserver:
    """Observer for configuration changes during runtime.
    
    This interface tracks configuration changes and their effects on
    different modules during active operations.
    """
    
    def __init__(self):
        """Initialize observer with empty state."""
        # TO BE IMPLEMENTED BY COORDINATOR WORKTREE
        pass
        
    def on_config_change(self, config_key: str, old_value: Any, 
                        new_value: Any) -> Dict[str, Any]:
        """Record a configuration change event.
        
        Args:
            config_key: Configuration key that changed
            old_value: Previous value
            new_value: New value
            
        Returns:
            Change event dictionary with timestamp and affected modules
        """
        # TO BE IMPLEMENTED BY COORDINATOR WORKTREE
        raise NotImplementedError("Coordinator worktree will implement this")
    
    def get_affected_modules(self, config_key: str) -> List[str]:
        """Determine which modules are affected by a config change.
        
        Args:
            config_key: Configuration key that changed
            
        Returns:
            List of affected module names
        """
        # TO BE IMPLEMENTED BY COORDINATOR WORKTREE
        raise NotImplementedError("Coordinator worktree will implement this")


class ResourceTracker:
    """Track resource allocation and cleanup across modules.
    
    This interface ensures proper resource lifecycle management and
    helps detect resource leaks in error scenarios.
    """
    
    def __init__(self):
        """Initialize tracker with empty resource registry."""
        # TO BE IMPLEMENTED BY COORDINATOR WORKTREE
        pass
        
    def track_resource(self, module: str, resource_type: str, 
                      resource_id: str) -> Dict[str, Any]:
        """Track a new resource allocation.
        
        Args:
            module: Module that allocated the resource
            resource_type: Type of resource (e.g., 'process', 'file_handle')
            resource_id: Unique identifier for the resource
            
        Returns:
            Resource tracking record
        """
        # TO BE IMPLEMENTED BY COORDINATOR WORKTREE
        raise NotImplementedError("Coordinator worktree will implement this")
    
    def release_resource(self, resource_id: str) -> None:
        """Mark a resource as released.
        
        Args:
            resource_id: Resource to mark as released
        """
        # TO BE IMPLEMENTED BY COORDINATOR WORKTREE
        raise NotImplementedError("Coordinator worktree will implement this")
    
    def verify_cleanup(self, module: str) -> List[Dict[str, Any]]:
        """Verify all resources for a module are properly cleaned up.
        
        Args:
            module: Module to check for resource leaks
            
        Returns:
            List of leaked resources (empty if all cleaned up)
        """
        # TO BE IMPLEMENTED BY COORDINATOR WORKTREE
        raise NotImplementedError("Coordinator worktree will implement this")
"""
API Wrapper Example

This module demonstrates how to create a set of related tools for wrapping
an external API. The pattern shown here can be adapted for any REST API.

Tools:
    - get_resource: Fetch a resource by ID
    - update_resource: Update a resource
    - list_resources: List all resources

Usage:
    from dev_tools.agent_tools.examples.api_wrapper import get_resource, update_resource

    # Fetch a resource
    data = get_resource.run(resource_id="123")

    # Update a resource
    result = update_resource.run(resource_id="123", data={"name": "New Name"})
"""

from . import get_resource, update_resource

__all__ = ["get_resource", "update_resource"]

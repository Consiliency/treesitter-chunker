#!/usr/bin/env python3
"""
Tool: update_resource
Description: Update a resource via API

This is an example tool demonstrating API wrapper patterns for write operations.
Replace the placeholder API calls with your actual API.

Args:
    resource_id (str): The unique identifier of the resource to update
    data (dict): The data to update the resource with
    partial (bool): Use PATCH for partial update, PUT for full replace (default: True)

Returns:
    dict: The updated resource data

Example:
    >>> result = run(resource_id="123", data={"title": "New Title"})
    >>> print(result["status"])
    "success"

Environment Variables:
    API_BASE_URL: Base URL for the API (default: https://api.example.com)
    API_KEY: API authentication key (required for writes)
"""

import json
import os
from typing import Any
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

# Configuration
API_BASE_URL = os.environ.get("API_BASE_URL", "https://jsonplaceholder.typicode.com")
API_KEY = os.environ.get("API_KEY", "")


def make_request(endpoint: str, method: str, data: dict) -> dict:
    """Make a request to the API."""
    url = f"{API_BASE_URL}{endpoint}"
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "AgentTools/1.0",
    }

    if API_KEY:
        headers["Authorization"] = f"Bearer {API_KEY}"

    body = json.dumps(data).encode("utf-8")
    req = Request(url, data=body, headers=headers, method=method)

    try:
        with urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode())
    except HTTPError as e:
        raise Exception(f"API error ({e.code}): {e.read().decode()}")
    except URLError as e:
        raise Exception(f"Connection error: {e.reason}")


def run(
    resource_id: str,
    data: dict[str, Any],
    partial: bool = True
) -> dict[str, Any]:
    """
    Update a resource via the API.

    Args:
        resource_id: The unique identifier of the resource
        data: The data to update
        partial: If True, use PATCH (partial update). If False, use PUT (full replace)

    Returns:
        Dictionary containing the update result

    Raises:
        ValueError: If resource_id is empty or data is empty
        Exception: If API request fails
    """
    if not resource_id:
        raise ValueError("resource_id cannot be empty")

    if not data:
        raise ValueError("data cannot be empty")

    # Example using JSONPlaceholder as a demo API
    # Replace with your actual API endpoint
    endpoint = f"/posts/{resource_id}"
    method = "PATCH" if partial else "PUT"

    response_data = make_request(endpoint, method, data)

    return {
        "status": "success",
        "resource_id": resource_id,
        "method": method,
        "updated_data": response_data,
    }


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} <resource_id> '<json_data>' [--full]")
        print('Example: python update_resource.py 1 \'{"title": "New Title"}\'')
        sys.exit(1)

    resource_id = sys.argv[1]
    data = json.loads(sys.argv[2])
    partial = "--full" not in sys.argv

    try:
        result = run(resource_id, data, partial=partial)
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

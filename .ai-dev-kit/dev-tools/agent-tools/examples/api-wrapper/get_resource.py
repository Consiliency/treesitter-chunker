#!/usr/bin/env python3
"""
Tool: get_resource
Description: Fetch a resource from an API by its ID

This is an example tool demonstrating API wrapper patterns.
Replace the placeholder API calls with your actual API.

Args:
    resource_id (str): The unique identifier of the resource
    include_metadata (bool): Include metadata in response (default: False)

Returns:
    dict: The resource data with optional metadata

Example:
    >>> result = run(resource_id="123")
    >>> print(result["data"]["name"])
    "Example Resource"

Environment Variables:
    API_BASE_URL: Base URL for the API (default: https://api.example.com)
    API_KEY: API authentication key
"""

import json
import os
from typing import Any
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

# Configuration
API_BASE_URL = os.environ.get("API_BASE_URL", "https://jsonplaceholder.typicode.com")
API_KEY = os.environ.get("API_KEY", "")


def make_request(endpoint: str) -> dict:
    """Make a GET request to the API."""
    url = f"{API_BASE_URL}{endpoint}"
    headers = {
        "Accept": "application/json",
        "User-Agent": "AgentTools/1.0",
    }

    if API_KEY:
        headers["Authorization"] = f"Bearer {API_KEY}"

    req = Request(url, headers=headers)

    try:
        with urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode())
    except HTTPError as e:
        raise Exception(f"API error ({e.code}): {e.read().decode()}")
    except URLError as e:
        raise Exception(f"Connection error: {e.reason}")


def run(resource_id: str, include_metadata: bool = False) -> dict[str, Any]:
    """
    Fetch a resource from the API.

    Args:
        resource_id: The unique identifier of the resource
        include_metadata: Include metadata in response

    Returns:
        Dictionary containing the resource data

    Raises:
        ValueError: If resource_id is empty
        Exception: If API request fails
    """
    if not resource_id:
        raise ValueError("resource_id cannot be empty")

    # Example using JSONPlaceholder as a demo API
    # Replace with your actual API endpoint
    endpoint = f"/posts/{resource_id}"

    data = make_request(endpoint)

    result = {
        "status": "success",
        "resource_id": resource_id,
        "data": data,
    }

    if include_metadata:
        result["metadata"] = {
            "api_base": API_BASE_URL,
            "endpoint": endpoint,
            "authenticated": bool(API_KEY),
        }

    return result


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <resource_id> [--metadata]")
        print("Example: python get_resource.py 1")
        sys.exit(1)

    resource_id = sys.argv[1]
    include_meta = "--metadata" in sys.argv

    try:
        result = run(resource_id, include_metadata=include_meta)
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

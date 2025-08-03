#!/usr/bin/env python3
"""Test the REST API endpoints."""

import json

import requests

BASE_URL = "http://localhost:8000"

<<<<<<< HEAD
=======
# Default timeout for all requests (in seconds)
DEFAULT_TIMEOUT = 30

>>>>>>> origin/main

def test_health():
    """Test health endpoint."""
    print("Testing /health endpoint...")
    response = requests.get(f"{BASE_URL}/health", timeout=DEFAULT_TIMEOUT)
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    print()


def test_languages():
    """Test languages endpoint."""
    print("Testing /languages endpoint...")
    response = requests.get(f"{BASE_URL}/languages", timeout=DEFAULT_TIMEOUT)
    print(f"Status: {response.status_code}")
    languages = response.json()
    print(f"Available languages: {', '.join(languages)}")
    print()


def test_chunk_text():
    """Test chunk text endpoint."""
    print("Testing /chunk/text endpoint...")

    test_code = '''def hello_world():
    """Print hello world."""
    print("Hello, World!")

def add_numbers(a, b):
    """Add two numbers."""
    return a + b

class Calculator:
    """Simple calculator class."""

    def multiply(self, x, y):
        """Multiply two numbers."""
        return x * y
'''

    payload = {
        "content": test_code,
        "language": "python",
        "min_chunk_size": 1,  # Include small chunks
    }

<<<<<<< HEAD
    response = requests.post(f"{BASE_URL}/chunk/text", json=payload)
=======
    response = requests.post(
        f"{BASE_URL}/chunk/text", json=payload, timeout=DEFAULT_TIMEOUT,
    )
>>>>>>> origin/main
    print(f"Status: {response.status_code}")

    if response.status_code == 200:
        data = response.json()
        print(f"Found {data['total_chunks']} chunks:")
        for i, chunk in enumerate(data["chunks"], 1):
            print(
                f"  {i}. {chunk['node_type']} at lines {chunk['start_line']}-{chunk['end_line']}",
            )
    else:
        print(f"Error: {response.text}")
    print()


def test_chunk_file():
    """Test chunk file endpoint with an actual file."""
    print("Testing /chunk/file endpoint...")

    # Use an existing example file
<<<<<<< HEAD
    payload = {
        "file_path": "examples/example.py",
        "language": "python",
    }

    response = requests.post(f"{BASE_URL}/chunk/file", json=payload)
=======
    payload = {"file_path": "examples/example.py", "language": "python"}

    response = requests.post(
        f"{BASE_URL}/chunk/file", json=payload, timeout=DEFAULT_TIMEOUT,
    )
>>>>>>> origin/main
    print(f"Status: {response.status_code}")

    if response.status_code == 200:
        data = response.json()
        print(f"Found {data['total_chunks']} chunks in {payload['file_path']}:")
        for i, chunk in enumerate(data["chunks"], 1):
            print(
                f"  {i}. {chunk['node_type']} at lines {chunk['start_line']}-{chunk['end_line']}",
            )
    else:
        print(f"Error: {response.text}")


if __name__ == "__main__":
    print("Testing Tree-sitter Chunker REST API")
    print("=" * 40)

    try:
        test_health()
        test_languages()
        test_chunk_text()
        test_chunk_file()

        print("\nAll tests completed successfully!")
    except requests.exceptions.ConnectionError:
        print("Error: Could not connect to API server at http://localhost:8000")
        print("Make sure the server is running with: python -m uvicorn api.server:app")
    except Exception as e:
        print(f"Error: {e}")

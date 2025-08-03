#!/usr/bin/env python3
"""
Example client for the Tree-sitter Chunker REST API.

This demonstrates how to use the API from Python, but the same
HTTP calls can be made from any programming language.
"""

from typing import Any

import requests

<<<<<<< HEAD
=======
# Default timeout for all requests (in seconds)
DEFAULT_TIMEOUT = 30

>>>>>>> origin/main

class ChunkerClient:
    """Simple client for the Tree-sitter Chunker API."""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip("/")

    def health_check(self) -> dict[str, Any]:
        """Check if the API is healthy."""
        response = requests.get(f"{self.base_url}/health", timeout=DEFAULT_TIMEOUT)
        response.raise_for_status()
        return response.json()

    def list_languages(self) -> list[str]:
        """Get list of supported languages."""
        response = requests.get(f"{self.base_url}/languages", timeout=DEFAULT_TIMEOUT)
        response.raise_for_status()
        return response.json()

    def chunk_text(
        self,
        content: str,
        language: str,
        min_chunk_size: int | None = None,
        max_chunk_size: int | None = None,
        chunk_types: list[str] | None = None,
    ) -> dict[str, Any]:
        """Chunk source code text."""
<<<<<<< HEAD
        payload = {
            "content": content,
            "language": language,
        }
=======
        payload = {"content": content, "language": language}
>>>>>>> origin/main

        if min_chunk_size is not None:
            payload["min_chunk_size"] = min_chunk_size
        if max_chunk_size is not None:
            payload["max_chunk_size"] = max_chunk_size
        if chunk_types:
            payload["chunk_types"] = chunk_types

        response = requests.post(
            f"{self.base_url}/chunk/text",
            json=payload,
<<<<<<< HEAD
=======
            timeout=DEFAULT_TIMEOUT,
>>>>>>> origin/main
        )
        response.raise_for_status()
        return response.json()

    def chunk_file(
        self,
        file_path: str,
        language: str | None = None,
        min_chunk_size: int | None = None,
        max_chunk_size: int | None = None,
        chunk_types: list[str] | None = None,
    ) -> dict[str, Any]:
        """Chunk a source code file."""
<<<<<<< HEAD
        payload = {
            "file_path": file_path,
        }
=======
        payload = {"file_path": file_path}
>>>>>>> origin/main

        if language:
            payload["language"] = language
        if min_chunk_size is not None:
            payload["min_chunk_size"] = min_chunk_size
        if max_chunk_size is not None:
            payload["max_chunk_size"] = max_chunk_size
        if chunk_types:
            payload["chunk_types"] = chunk_types

        response = requests.post(
            f"{self.base_url}/chunk/file",
            json=payload,
<<<<<<< HEAD
=======
            timeout=DEFAULT_TIMEOUT,
>>>>>>> origin/main
        )
        response.raise_for_status()
        return response.json()


def main():
    """Example usage of the chunker client."""
    # Create client
    client = ChunkerClient()

    # Check health
    print("Health check:", client.health_check())

    # List languages
    print("\nSupported languages:", client.list_languages())

    # Example Python code
    python_code = '''
def calculate_fibonacci(n):
    """Calculate the nth Fibonacci number."""
    if n <= 0:
        return 0
    elif n == 1:
        return 1
    else:
        return calculate_fibonacci(n-1) + calculate_fibonacci(n-2)

class MathUtils:
    """Utility class for mathematical operations."""

    def factorial(self, n):
        """Calculate factorial of n."""
        if n <= 1:
            return 1
        return n * self.factorial(n - 1)

    def is_prime(self, n):
        """Check if n is prime."""
        if n < 2:
            return False
        for i in range(2, int(n**0.5) + 1):
            if n % i == 0:
                return False
        return True
'''

    # Chunk the code
    result = client.chunk_text(
        content=python_code,
        language="python",
        min_chunk_size=3,  # Filter out small chunks
    )

    print(f"\nFound {result['total_chunks']} chunks:")
    for i, chunk in enumerate(result["chunks"], 1):
        print(
            f"\n{i}. {chunk['node_type']} (lines {chunk['start_line']}-{chunk['end_line']})",
        )
        if chunk["parent_context"]:
            print(f"   Parent: {chunk['parent_context']}")
        print(f"   Size: {chunk['size']} lines")
        print(
            "   Content preview:",
            (
                chunk["content"][:100] + "..."
                if len(chunk["content"]) > 100
                else chunk["content"]
            ),
        )


if __name__ == "__main__":
    main()

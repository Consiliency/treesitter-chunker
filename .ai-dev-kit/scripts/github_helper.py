"""GitHub helper shim for ai-dev-kit plugin scripts.

This wrapper exposes the package-level GitHubHelper while keeping the script
path stable for plugin users. It supports environment-based token discovery and
remains importable as a standalone script.
"""

from ai_dev_kit.github_helper import GitHubHelper

__all__ = ["GitHubHelper"]

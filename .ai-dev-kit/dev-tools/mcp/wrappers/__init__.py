"""MCP Wrappers for Progressive Disclosure.

This package provides Python wrappers for MCP servers that enable on-demand
server spawning with connection pooling, instead of eager loading via .mcp.json.

Available wrappers:
    - PlaywrightWrapper: Browser automation
    - BrightDataWrapper: Web scraping with CAPTCHA bypass
    - MCPClient: Base class for custom wrappers

Usage:
    from dev_tools.mcp.wrappers import PlaywrightWrapper, BrightDataWrapper

    # Browser automation
    pw = PlaywrightWrapper()
    pw.navigate("https://example.com")
    snapshot = pw.snapshot()

    # Web scraping
    bd = BrightDataWrapper()
    content = bd.scrape_markdown("https://example.com")
"""

from .mcp_client import MCPClient, load_env_file
from .playwright_wrapper import PlaywrightWrapper
from .brightdata_wrapper import BrightDataWrapper

__all__ = [
    "MCPClient",
    "PlaywrightWrapper",
    "BrightDataWrapper",
    "load_env_file",
]

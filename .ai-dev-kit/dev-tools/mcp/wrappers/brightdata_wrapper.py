#!/usr/bin/env python3
"""Bright Data MCP wrapper for Progressive Disclosure.

This wrapper provides web scraping capabilities via the Bright Data MCP server,
spawned on-demand with connection pooling. No MCP tools are loaded into context
until explicitly needed.

Usage (CLI):
    # Scrape a URL as markdown
    python3 brightdata_wrapper.py scrape "https://example.com"

    # Search Google
    python3 brightdata_wrapper.py search "python tutorials"

    # Batch scrape multiple URLs
    python3 brightdata_wrapper.py scrape-batch "https://a.com" "https://b.com"

    # List available tools
    python3 brightdata_wrapper.py --list-tools

Usage (Python):
    from brightdata_wrapper import BrightDataWrapper

    bd = BrightDataWrapper()
    content = bd.scrape_markdown("https://example.com")
    results = bd.search("python tutorials")
    bd.shutdown()

Prerequisites:
    - BRIGHTDATA_API_KEY or API_TOKEN environment variable
    - Or .env file with BRIGHTDATA_API_KEY=...
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add parent to path for mcp_client import
sys.path.insert(0, str(Path(__file__).parent))
from mcp_client import MCPClient, load_env_file


class BrightDataWrapper:
    """Wrapper for Bright Data MCP server with connection pooling."""

    def __init__(
        self,
        api_token: Optional[str] = None,
        idle_timeout: float = 60.0,
    ):
        """Initialize Bright Data wrapper.

        Args:
            api_token: Bright Data API token. If not provided, reads from env/file.
            idle_timeout: Seconds of inactivity before auto-terminating server
        """
        # Resolve API token
        self.api_token = api_token or self._resolve_token()
        if not self.api_token:
            raise RuntimeError(
                "Bright Data API token not found. "
                "Set BRIGHTDATA_API_KEY or API_TOKEN environment variable, "
                "or add to .env file."
            )

        command = ["npx", "-y", "@brightdata/mcp"]

        self._client = MCPClient(
            name="brightdata",
            command=command,
            env={"API_TOKEN": self.api_token},
            idle_timeout=idle_timeout,
        )

    def _resolve_token(self) -> str:
        """Resolve API token from environment or .env file."""
        # Check environment first
        for key in ("API_TOKEN", "BRIGHTDATA_API_KEY"):
            if os.environ.get(key):
                return os.environ[key]

        # Check .env file
        env = load_env_file()
        for key in ("API_TOKEN", "BRIGHTDATA_API_KEY"):
            if env.get(key):
                return env[key]

        return ""

    def _call(self, tool: str, **kwargs: Any) -> Any:
        """Call a Bright Data MCP tool."""
        args = {k: v for k, v in kwargs.items() if v is not None}
        return self._client.call(tool, args)

    # Scraping

    def scrape_markdown(self, url: str) -> str:
        """Scrape a URL and return content as markdown.

        This tool can bypass bot detection and CAPTCHAs.

        Args:
            url: URL to scrape

        Returns:
            Page content as markdown
        """
        return self._call("scrape_as_markdown", url=url)

    def scrape_batch(self, urls: List[str]) -> List[Dict[str, Any]]:
        """Scrape multiple URLs (up to 10).

        Args:
            urls: List of URLs to scrape

        Returns:
            List of scrape results
        """
        if len(urls) > 10:
            raise ValueError("Maximum 10 URLs per batch")
        return self._call("scrape_batch", urls=urls)

    # Search

    def search(
        self,
        query: str,
        engine: str = "google",
        cursor: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Search using a search engine.

        Args:
            query: Search query
            engine: Search engine ("google", "bing", "yandex")
            cursor: Pagination cursor for next page

        Returns:
            Search results with URLs, titles, descriptions
        """
        return self._call("search_engine", query=query, engine=engine, cursor=cursor)

    def search_batch(
        self,
        queries: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Run multiple search queries (up to 10).

        Args:
            queries: List of query dicts with keys: query, engine (optional), cursor (optional)

        Returns:
            List of search results
        """
        if len(queries) > 10:
            raise ValueError("Maximum 10 queries per batch")
        return self._call("search_engine_batch", queries=queries)

    # Lifecycle

    def shutdown(self) -> None:
        """Shutdown the MCP client."""
        self._client.close()

    def get_tools(self) -> List[Dict[str, Any]]:
        """Get list of available tools from this server."""
        return self._client.get_tools()


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Bright Data MCP wrapper for web scraping",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s scrape "https://example.com"
  %(prog)s search "python tutorials"
  %(prog)s search "news today" --engine bing
  %(prog)s scrape-batch "https://a.com" "https://b.com"
  %(prog)s --list-tools
        """,
    )

    parser.add_argument(
        "--api-token",
        help="Bright Data API token (default: from env)",
    )
    parser.add_argument(
        "--list-tools",
        action="store_true",
        help="List available tools and exit",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON",
    )

    subparsers = parser.add_subparsers(dest="command")

    # scrape
    p_scrape = subparsers.add_parser("scrape", help="Scrape a URL as markdown")
    p_scrape.add_argument("url", help="URL to scrape")

    # scrape-batch
    p_batch = subparsers.add_parser("scrape-batch", help="Scrape multiple URLs")
    p_batch.add_argument("urls", nargs="+", help="URLs to scrape (max 10)")

    # search
    p_search = subparsers.add_parser("search", help="Search using a search engine")
    p_search.add_argument("query", help="Search query")
    p_search.add_argument("--engine", default="google", choices=["google", "bing", "yandex"])
    p_search.add_argument("--cursor", help="Pagination cursor")

    # search-batch
    p_sbatch = subparsers.add_parser("search-batch", help="Run multiple searches")
    p_sbatch.add_argument("queries", nargs="+", help="Search queries")
    p_sbatch.add_argument("--engine", default="google", choices=["google", "bing", "yandex"])

    args = parser.parse_args()

    def output(result: Any) -> None:
        if args.json or isinstance(result, (dict, list)):
            print(json.dumps(result, indent=2) if isinstance(result, (dict, list)) else json.dumps(result))
        else:
            print(result)

    try:
        bd = BrightDataWrapper(api_token=args.api_token)
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    try:
        if args.list_tools:
            tools = bd.get_tools()
            for tool in tools:
                name = tool.get("name", "unknown")
                desc = tool.get("description", "No description")
                print(f"- {name}: {desc}")
            return 0

        if args.command == "scrape":
            output(bd.scrape_markdown(args.url))
        elif args.command == "scrape-batch":
            output(bd.scrape_batch(args.urls))
        elif args.command == "search":
            output(bd.search(args.query, engine=args.engine, cursor=args.cursor))
        elif args.command == "search-batch":
            queries = [{"query": q, "engine": args.engine} for q in args.queries]
            output(bd.search_batch(queries))
        else:
            parser.print_help()
            return 1

        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    finally:
        pass  # Let idle timeout handle cleanup


if __name__ == "__main__":
    sys.exit(main())

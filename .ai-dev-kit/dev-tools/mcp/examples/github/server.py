#!/usr/bin/env python3
"""
GitHub MCP Server

A simple MCP server for GitHub API operations.
Demonstrates API wrapper patterns with authentication.

NOTE: For full GitHub integration, use the official server:
    claude mcp add github -- npx -y @modelcontextprotocol/server-github

This example shows how to build custom API wrappers.

Configuration in .mcp.json:
    {
      "mcpServers": {
        "github": {
          "command": "python3",
          "args": ["dev-tools/mcp/examples/github/server.py"],
          "env": {
            "GITHUB_TOKEN": "${GITHUB_TOKEN}"
          }
        }
      }
    }
"""

import asyncio
import json
import os
import sys
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Configuration
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_API = "https://api.github.com"

server = Server("github")


def github_request(endpoint: str, method: str = "GET", data: dict = None) -> dict:
    """Make a request to the GitHub API."""
    url = f"{GITHUB_API}{endpoint}"
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "MCP-GitHub-Server",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"

    body = json.dumps(data).encode() if data else None

    req = Request(url, data=body, headers=headers, method=method)

    try:
        with urlopen(req) as response:
            return json.loads(response.read().decode())
    except HTTPError as e:
        error_body = e.read().decode()
        try:
            error_json = json.loads(error_body)
            raise Exception(f"GitHub API error ({e.code}): {error_json.get('message', error_body)}")
        except json.JSONDecodeError:
            raise Exception(f"GitHub API error ({e.code}): {error_body}")


def format_issue(issue: dict) -> str:
    """Format an issue for display."""
    labels = ", ".join(l["name"] for l in issue.get("labels", []))
    return (
        f"#{issue['number']}: {issue['title']}\n"
        f"  State: {issue['state']} | Author: {issue['user']['login']}\n"
        f"  Labels: {labels or '(none)'}\n"
        f"  URL: {issue['html_url']}"
    )


def format_pr(pr: dict) -> str:
    """Format a pull request for display."""
    return (
        f"#{pr['number']}: {pr['title']}\n"
        f"  State: {pr['state']} | Author: {pr['user']['login']}\n"
        f"  Base: {pr['base']['ref']} <- Head: {pr['head']['ref']}\n"
        f"  URL: {pr['html_url']}"
    )


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Define available GitHub tools."""
    return [
        Tool(
            name="list_issues",
            description="List issues in a GitHub repository.",
            inputSchema={
                "type": "object",
                "properties": {
                    "owner": {"type": "string", "description": "Repository owner"},
                    "repo": {"type": "string", "description": "Repository name"},
                    "state": {
                        "type": "string",
                        "enum": ["open", "closed", "all"],
                        "description": "Filter by state",
                        "default": "open",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max issues to return",
                        "default": 10,
                    },
                },
                "required": ["owner", "repo"],
            },
        ),
        Tool(
            name="get_issue",
            description="Get details of a specific issue.",
            inputSchema={
                "type": "object",
                "properties": {
                    "owner": {"type": "string", "description": "Repository owner"},
                    "repo": {"type": "string", "description": "Repository name"},
                    "issue_number": {"type": "integer", "description": "Issue number"},
                },
                "required": ["owner", "repo", "issue_number"],
            },
        ),
        Tool(
            name="list_prs",
            description="List pull requests in a GitHub repository.",
            inputSchema={
                "type": "object",
                "properties": {
                    "owner": {"type": "string", "description": "Repository owner"},
                    "repo": {"type": "string", "description": "Repository name"},
                    "state": {
                        "type": "string",
                        "enum": ["open", "closed", "all"],
                        "description": "Filter by state",
                        "default": "open",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max PRs to return",
                        "default": 10,
                    },
                },
                "required": ["owner", "repo"],
            },
        ),
        Tool(
            name="get_repo",
            description="Get repository information.",
            inputSchema={
                "type": "object",
                "properties": {
                    "owner": {"type": "string", "description": "Repository owner"},
                    "repo": {"type": "string", "description": "Repository name"},
                },
                "required": ["owner", "repo"],
            },
        ),
        Tool(
            name="search_code",
            description="Search for code in GitHub repositories.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "limit": {
                        "type": "integer",
                        "description": "Max results to return",
                        "default": 10,
                    },
                },
                "required": ["query"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle GitHub tool invocations."""
    try:
        if name == "list_issues":
            owner = arguments["owner"]
            repo = arguments["repo"]
            state = arguments.get("state", "open")
            limit = arguments.get("limit", 10)

            endpoint = f"/repos/{owner}/{repo}/issues?state={state}&per_page={limit}"
            issues = github_request(endpoint)

            if not issues:
                return [TextContent(type="text", text="No issues found.")]

            # Filter out pull requests (they appear in issues endpoint)
            issues = [i for i in issues if "pull_request" not in i][:limit]

            result = [f"Issues in {owner}/{repo} ({state}):", ""]
            result.extend(format_issue(i) for i in issues)
            return [TextContent(type="text", text="\n".join(result))]

        elif name == "get_issue":
            owner = arguments["owner"]
            repo = arguments["repo"]
            issue_number = arguments["issue_number"]

            issue = github_request(f"/repos/{owner}/{repo}/issues/{issue_number}")

            result = [
                f"Issue #{issue['number']}: {issue['title']}",
                f"State: {issue['state']}",
                f"Author: {issue['user']['login']}",
                f"Created: {issue['created_at']}",
                f"Labels: {', '.join(l['name'] for l in issue.get('labels', [])) or '(none)'}",
                f"URL: {issue['html_url']}",
                "",
                "Body:",
                issue.get("body") or "(no description)",
            ]
            return [TextContent(type="text", text="\n".join(result))]

        elif name == "list_prs":
            owner = arguments["owner"]
            repo = arguments["repo"]
            state = arguments.get("state", "open")
            limit = arguments.get("limit", 10)

            endpoint = f"/repos/{owner}/{repo}/pulls?state={state}&per_page={limit}"
            prs = github_request(endpoint)

            if not prs:
                return [TextContent(type="text", text="No pull requests found.")]

            result = [f"Pull Requests in {owner}/{repo} ({state}):", ""]
            result.extend(format_pr(pr) for pr in prs[:limit])
            return [TextContent(type="text", text="\n".join(result))]

        elif name == "get_repo":
            owner = arguments["owner"]
            repo = arguments["repo"]

            repo_info = github_request(f"/repos/{owner}/{repo}")

            result = [
                f"Repository: {repo_info['full_name']}",
                f"Description: {repo_info.get('description') or '(none)'}",
                f"Stars: {repo_info['stargazers_count']} | Forks: {repo_info['forks_count']}",
                f"Language: {repo_info.get('language') or 'Unknown'}",
                f"Default Branch: {repo_info['default_branch']}",
                f"Open Issues: {repo_info['open_issues_count']}",
                f"Created: {repo_info['created_at']}",
                f"URL: {repo_info['html_url']}",
            ]
            return [TextContent(type="text", text="\n".join(result))]

        elif name == "search_code":
            query = arguments["query"]
            limit = arguments.get("limit", 10)

            endpoint = f"/search/code?q={query}&per_page={limit}"
            results = github_request(endpoint)

            if not results.get("items"):
                return [TextContent(type="text", text="No results found.")]

            output = [f"Code search results for: {query}", ""]
            for item in results["items"][:limit]:
                output.append(
                    f"- {item['repository']['full_name']}: {item['path']}\n"
                    f"  {item['html_url']}"
                )

            return [TextContent(type="text", text="\n".join(output))]

        else:
            raise ValueError(f"Unknown tool: {name}")

    except Exception as e:
        return [TextContent(type="text", text=f"Error: {e}")]


async def main():
    """Run the GitHub MCP server."""
    print("GitHub MCP Server starting...", file=sys.stderr)
    if not GITHUB_TOKEN:
        print("Warning: GITHUB_TOKEN not set. API rate limits will apply.", file=sys.stderr)

    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())

#!/usr/bin/env python3
"""
Tool: search_tools
Description: Meta-tool for discovering available agent tools by keyword search

This tool helps AI agents discover relevant tools in the agent-tools directory
without loading all tool definitions upfront (saving tokens).

Usage:
    from dev_tools.agent_tools.search_tools import search, list_all, get_tool_info

    # Search for tools by keyword
    results = search("api")

    # List all available tools
    all_tools = list_all()

    # Get detailed info about a specific tool
    info = get_tool_info("examples/api-wrapper/get_resource.py")
"""

import ast
import os
import re
from pathlib import Path
from typing import Optional

# Base directory for agent tools
TOOLS_DIR = Path(__file__).parent


def extract_docstring(filepath: Path) -> Optional[str]:
    """Extract the module docstring from a Python file."""
    try:
        with open(filepath, "r") as f:
            tree = ast.parse(f.read())
            return ast.get_docstring(tree)
    except (SyntaxError, FileNotFoundError):
        return None


def parse_tool_docstring(docstring: str) -> dict:
    """Parse a tool docstring into structured info."""
    info = {
        "name": "",
        "description": "",
        "args": [],
        "returns": "",
    }

    if not docstring:
        return info

    lines = docstring.strip().split("\n")

    # Parse Tool: and Description: from first lines
    for line in lines:
        if line.startswith("Tool:"):
            info["name"] = line.replace("Tool:", "").strip()
        elif line.startswith("Description:"):
            info["description"] = line.replace("Description:", "").strip()

    # Parse Args section
    in_args = False
    for line in lines:
        if line.strip().startswith("Args:"):
            in_args = True
            continue
        elif line.strip().startswith(("Returns:", "Example:", "Environment")):
            in_args = False
        elif in_args and line.strip():
            # Parse "param (type): description" format
            match = re.match(r"\s*(\w+)\s*\(([^)]+)\):\s*(.+)", line)
            if match:
                info["args"].append({
                    "name": match.group(1),
                    "type": match.group(2),
                    "description": match.group(3),
                })

    # Parse Returns section
    for i, line in enumerate(lines):
        if line.strip().startswith("Returns:"):
            if i + 1 < len(lines):
                info["returns"] = lines[i + 1].strip()
            break

    return info


def list_all() -> list[dict]:
    """
    List all available tools in the agent-tools directory.

    Returns:
        List of tool info dictionaries with keys: path, name, description
    """
    tools = []

    for root, dirs, files in os.walk(TOOLS_DIR):
        # Skip template and hidden directories
        dirs[:] = [d for d in dirs if not d.startswith(("_", "."))]

        for file in files:
            if file.endswith(".py") and not file.startswith("_"):
                filepath = Path(root) / file
                rel_path = filepath.relative_to(TOOLS_DIR)

                docstring = extract_docstring(filepath)
                info = parse_tool_docstring(docstring or "")

                tools.append({
                    "path": str(rel_path),
                    "name": info["name"] or file.replace(".py", ""),
                    "description": info["description"] or "(no description)",
                })

    return tools


def search(keyword: str, include_args: bool = False) -> list[dict]:
    """
    Search for tools matching a keyword.

    Args:
        keyword: Search term (case-insensitive)
        include_args: Include argument info in results (default: False)

    Returns:
        List of matching tool info dictionaries
    """
    keyword_lower = keyword.lower()
    results = []

    for root, dirs, files in os.walk(TOOLS_DIR):
        dirs[:] = [d for d in dirs if not d.startswith(("_", "."))]

        for file in files:
            if file.endswith(".py") and not file.startswith("_"):
                filepath = Path(root) / file
                rel_path = filepath.relative_to(TOOLS_DIR)

                # Search in filename
                if keyword_lower in file.lower():
                    match = True
                else:
                    # Search in docstring
                    docstring = extract_docstring(filepath) or ""
                    match = keyword_lower in docstring.lower()

                if match:
                    docstring = extract_docstring(filepath)
                    info = parse_tool_docstring(docstring or "")

                    result = {
                        "path": str(rel_path),
                        "name": info["name"] or file.replace(".py", ""),
                        "description": info["description"] or "(no description)",
                    }

                    if include_args:
                        result["args"] = info["args"]
                        result["returns"] = info["returns"]

                    results.append(result)

    return results


def get_tool_info(tool_path: str) -> dict:
    """
    Get detailed information about a specific tool.

    Args:
        tool_path: Relative path to the tool file from agent-tools/

    Returns:
        Dictionary with full tool info including args and returns
    """
    filepath = TOOLS_DIR / tool_path

    if not filepath.exists():
        raise FileNotFoundError(f"Tool not found: {tool_path}")

    docstring = extract_docstring(filepath)
    info = parse_tool_docstring(docstring or "")

    return {
        "path": tool_path,
        "name": info["name"] or filepath.stem,
        "description": info["description"],
        "args": info["args"],
        "returns": info["returns"],
        "full_docstring": docstring,
    }


def run(action: str = "list", keyword: str = "", path: str = "") -> dict:
    """
    Main entry point for the search_tools tool.

    Args:
        action: 'list', 'search', or 'info'
        keyword: Search keyword (for action='search')
        path: Tool path (for action='info')

    Returns:
        Dictionary with results
    """
    if action == "list":
        return {"tools": list_all()}
    elif action == "search":
        if not keyword:
            raise ValueError("keyword required for search action")
        return {"results": search(keyword, include_args=True)}
    elif action == "info":
        if not path:
            raise ValueError("path required for info action")
        return {"tool": get_tool_info(path)}
    else:
        raise ValueError(f"Unknown action: {action}. Use 'list', 'search', or 'info'")


if __name__ == "__main__":
    import json
    import sys

    if len(sys.argv) < 2:
        print("Usage:")
        print("  search_tools.py list              - List all tools")
        print("  search_tools.py search <keyword>  - Search for tools")
        print("  search_tools.py info <path>       - Get tool details")
        sys.exit(1)

    action = sys.argv[1]

    try:
        if action == "list":
            result = run("list")
        elif action == "search" and len(sys.argv) > 2:
            result = run("search", keyword=sys.argv[2])
        elif action == "info" and len(sys.argv) > 2:
            result = run("info", path=sys.argv[2])
        else:
            print(f"Unknown action or missing argument: {action}")
            sys.exit(1)

        print(json.dumps(result, indent=2))
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

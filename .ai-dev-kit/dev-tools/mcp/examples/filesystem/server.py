#!/usr/bin/env python3
"""
Filesystem MCP Server

A simple MCP server that provides safe file operations within allowed paths.
Demonstrates path validation and sandboxing patterns.

Configuration in .mcp.json:
    {
      "mcpServers": {
        "filesystem": {
          "command": "python3",
          "args": ["dev-tools/mcp/examples/filesystem/server.py"],
          "env": {
            "ALLOWED_PATHS": "./src:./docs"
          }
        }
      }
    }

Environment Variables:
    ALLOWED_PATHS: Colon-separated list of paths to allow access to.
                   Defaults to current directory.
"""

import asyncio
import os
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Configuration
ALLOWED_PATHS = os.environ.get("ALLOWED_PATHS", ".").split(":")
ALLOWED_PATHS = [Path(p).resolve() for p in ALLOWED_PATHS]

server = Server("filesystem")


def is_path_allowed(path: Path) -> bool:
    """Check if a path is within allowed directories."""
    resolved = path.resolve()
    return any(
        resolved == allowed or allowed in resolved.parents
        for allowed in ALLOWED_PATHS
    )


def validate_path(path_str: str) -> Path:
    """Validate and resolve a path, raising if not allowed."""
    path = Path(path_str).resolve()
    if not is_path_allowed(path):
        raise PermissionError(
            f"Access denied: {path} is not in allowed paths: {ALLOWED_PATHS}"
        )
    return path


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Define available filesystem tools."""
    return [
        Tool(
            name="read_file",
            description="Read the contents of a file. Only works within allowed paths.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file to read",
                    },
                },
                "required": ["path"],
            },
        ),
        Tool(
            name="write_file",
            description="Write content to a file. Creates parent directories if needed. Only works within allowed paths.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file to write",
                    },
                    "content": {
                        "type": "string",
                        "description": "Content to write to the file",
                    },
                },
                "required": ["path", "content"],
            },
        ),
        Tool(
            name="list_directory",
            description="List contents of a directory. Only works within allowed paths.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the directory to list",
                    },
                },
                "required": ["path"],
            },
        ),
        Tool(
            name="file_info",
            description="Get information about a file (size, modified time, type). Only works within allowed paths.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file",
                    },
                },
                "required": ["path"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle filesystem tool invocations."""
    try:
        if name == "read_file":
            path = validate_path(arguments["path"])
            if not path.is_file():
                return [TextContent(type="text", text=f"Error: {path} is not a file")]
            content = path.read_text()
            return [TextContent(type="text", text=content)]

        elif name == "write_file":
            path = validate_path(arguments["path"])
            content = arguments["content"]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
            return [TextContent(type="text", text=f"Successfully wrote to {path}")]

        elif name == "list_directory":
            path = validate_path(arguments["path"])
            if not path.is_dir():
                return [TextContent(type="text", text=f"Error: {path} is not a directory")]
            entries = []
            for entry in sorted(path.iterdir()):
                entry_type = "dir" if entry.is_dir() else "file"
                entries.append(f"[{entry_type}] {entry.name}")
            result = "\n".join(entries) if entries else "(empty directory)"
            return [TextContent(type="text", text=result)]

        elif name == "file_info":
            path = validate_path(arguments["path"])
            if not path.exists():
                return [TextContent(type="text", text=f"Error: {path} does not exist")]
            stat = path.stat()
            info = {
                "path": str(path),
                "type": "directory" if path.is_dir() else "file",
                "size": stat.st_size,
                "modified": stat.st_mtime,
            }
            result = "\n".join(f"{k}: {v}" for k, v in info.items())
            return [TextContent(type="text", text=result)]

        else:
            raise ValueError(f"Unknown tool: {name}")

    except PermissionError as e:
        return [TextContent(type="text", text=f"Permission denied: {e}")]
    except Exception as e:
        return [TextContent(type="text", text=f"Error: {e}")]


async def main():
    """Run the filesystem MCP server."""
    print(f"Filesystem MCP Server starting...", file=__import__("sys").stderr)
    print(f"Allowed paths: {ALLOWED_PATHS}", file=__import__("sys").stderr)

    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())

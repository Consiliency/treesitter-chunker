#!/usr/bin/env python3
"""
MCP Server Template (Python)

A starter template for building Model Context Protocol servers.
Uses the official MCP Python SDK.

Usage:
    1. Copy this directory to dev-tools/mcp/your-server-name/
    2. Install dependencies: uv pip install -r requirements.txt
    3. Modify the tools below to implement your functionality
    4. Register in .mcp.json

For more information, see:
    - MCP SDK: https://github.com/modelcontextprotocol/python-sdk
    - MCP Spec: https://spec.modelcontextprotocol.io/
"""

import asyncio
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Create the MCP server instance
server = Server("your-server-name")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Define the tools this server provides."""
    return [
        Tool(
            name="example_tool",
            description="An example tool that echoes input. Replace with your implementation.",
            inputSchema={
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "The message to echo back",
                    }
                },
                "required": ["message"],
            },
        ),
        # Add more tools here...
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool invocations."""
    if name == "example_tool":
        message = arguments.get("message", "")
        return [TextContent(type="text", text=f"Echo: {message}")]

    raise ValueError(f"Unknown tool: {name}")


async def main():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())

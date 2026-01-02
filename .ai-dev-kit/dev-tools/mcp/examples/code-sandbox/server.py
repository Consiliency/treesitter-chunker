#!/usr/bin/env python3
"""
Code Sandbox MCP Server

A simple MCP server that executes code in a sandboxed environment.
Demonstrates safe code execution patterns with timeout and output limits.

SECURITY WARNING: This is a basic example. For production use, consider:
- Docker/container isolation
- Resource limits (CPU, memory)
- Network isolation
- Filesystem isolation

Configuration in .mcp.json:
    {
      "mcpServers": {
        "code-sandbox": {
          "command": "python3",
          "args": ["dev-tools/mcp/examples/code-sandbox/server.py"],
          "env": {
            "TIMEOUT_SECONDS": "10",
            "MAX_OUTPUT_BYTES": "10000"
          }
        }
      }
    }
"""

import asyncio
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Configuration
TIMEOUT_SECONDS = int(os.environ.get("TIMEOUT_SECONDS", "10"))
MAX_OUTPUT_BYTES = int(os.environ.get("MAX_OUTPUT_BYTES", "10000"))
ALLOWED_LANGUAGES = {"python", "javascript", "bash"}

server = Server("code-sandbox")


def run_python(code: str, timeout: int) -> tuple[str, str, int]:
    """Execute Python code and return stdout, stderr, return code."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(code)
        f.flush()
        try:
            result = subprocess.run(
                [sys.executable, f.name],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=tempfile.gettempdir(),
            )
            return result.stdout, result.stderr, result.returncode
        finally:
            Path(f.name).unlink(missing_ok=True)


def run_javascript(code: str, timeout: int) -> tuple[str, str, int]:
    """Execute JavaScript code using Node.js."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".js", delete=False) as f:
        f.write(code)
        f.flush()
        try:
            result = subprocess.run(
                ["node", f.name],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=tempfile.gettempdir(),
            )
            return result.stdout, result.stderr, result.returncode
        finally:
            Path(f.name).unlink(missing_ok=True)


def run_bash(code: str, timeout: int) -> tuple[str, str, int]:
    """Execute Bash code."""
    result = subprocess.run(
        ["bash", "-c", code],
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=tempfile.gettempdir(),
    )
    return result.stdout, result.stderr, result.returncode


def truncate_output(text: str, max_bytes: int) -> str:
    """Truncate output to max bytes."""
    if len(text.encode("utf-8")) > max_bytes:
        truncated = text.encode("utf-8")[:max_bytes].decode("utf-8", errors="ignore")
        return truncated + "\n... (output truncated)"
    return text


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Define available code execution tools."""
    return [
        Tool(
            name="run_code",
            description=f"Execute code in a sandboxed environment. Supported languages: {', '.join(ALLOWED_LANGUAGES)}. Has a {TIMEOUT_SECONDS}s timeout.",
            inputSchema={
                "type": "object",
                "properties": {
                    "language": {
                        "type": "string",
                        "enum": list(ALLOWED_LANGUAGES),
                        "description": "Programming language to use",
                    },
                    "code": {
                        "type": "string",
                        "description": "Code to execute",
                    },
                },
                "required": ["language", "code"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle code execution requests."""
    if name != "run_code":
        raise ValueError(f"Unknown tool: {name}")

    language = arguments.get("language", "").lower()
    code = arguments.get("code", "")

    if language not in ALLOWED_LANGUAGES:
        return [
            TextContent(
                type="text",
                text=f"Error: Unsupported language '{language}'. Allowed: {', '.join(ALLOWED_LANGUAGES)}",
            )
        ]

    try:
        runners = {
            "python": run_python,
            "javascript": run_javascript,
            "bash": run_bash,
        }

        runner = runners[language]
        stdout, stderr, returncode = runner(code, TIMEOUT_SECONDS)

        stdout = truncate_output(stdout, MAX_OUTPUT_BYTES)
        stderr = truncate_output(stderr, MAX_OUTPUT_BYTES)

        result_parts = []
        if stdout:
            result_parts.append(f"STDOUT:\n{stdout}")
        if stderr:
            result_parts.append(f"STDERR:\n{stderr}")
        result_parts.append(f"Exit code: {returncode}")

        return [TextContent(type="text", text="\n\n".join(result_parts))]

    except subprocess.TimeoutExpired:
        return [
            TextContent(
                type="text",
                text=f"Error: Code execution timed out after {TIMEOUT_SECONDS} seconds",
            )
        ]
    except FileNotFoundError as e:
        return [
            TextContent(
                type="text",
                text=f"Error: Runtime not found. Make sure {language} is installed. ({e})",
            )
        ]
    except Exception as e:
        return [TextContent(type="text", text=f"Error: {type(e).__name__}: {e}")]


async def main():
    """Run the code sandbox MCP server."""
    print(f"Code Sandbox MCP Server starting...", file=sys.stderr)
    print(f"Timeout: {TIMEOUT_SECONDS}s, Max output: {MAX_OUTPUT_BYTES} bytes", file=sys.stderr)

    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())

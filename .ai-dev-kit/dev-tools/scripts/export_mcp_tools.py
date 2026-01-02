#!/usr/bin/env python3
"""Export MCP tools from any MCP server for progressive disclosure.

This script spawns an MCP server, queries its available tools, and exports them
to a JSON file. This enables on-demand tool discovery without loading tool
definitions into the AI's context.

Usage:
    # Export Bright Data tools (uses env token)
    python3 export_mcp_tools.py --server brightdata --output .tmp/brightdata-tools.json

    # Export Playwright tools
    python3 export_mcp_tools.py --server playwright \
        --command "npx -y @playwright/mcp@latest --cdp-endpoint http://localhost:9222" \
        --output .tmp/playwright-tools.json

    # Export from any MCP server
    python3 export_mcp_tools.py \
        --server custom \
        --command "python3 my_server.py" \
        --env "API_KEY=secret" \
        --output .tmp/custom-tools.json

Preset servers:
    - brightdata: Bright Data MCP (requires BRIGHTDATA_API_KEY or API_TOKEN env)
    - playwright: Playwright MCP (requires Chrome with --remote-debugging-port=9222)

Environment variables for brightdata:
    - API_TOKEN
    - BRIGHTDATA_API_KEY
    - Also checks .env file
"""
from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


# Preset server configurations
PRESETS: Dict[str, Dict[str, Any]] = {
    "brightdata": {
        "command": ["npx", "-y", "@brightdata/mcp"],
        "env_keys": ["API_TOKEN", "BRIGHTDATA_API_KEY"],
        "env_var": "API_TOKEN",
    },
    "playwright": {
        "command": ["npx", "-y", "@playwright/mcp@latest", "--cdp-endpoint", "http://localhost:9222"],
        "env_keys": [],
        "env_var": None,
    },
}


def _load_env_file(path: Path) -> Dict[str, str]:
    """Load environment variables from a file."""
    env: Dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        env[key.strip()] = value.strip()
    return env


def _find_env_file() -> Optional[Path]:
    """Search for .env files in current directory and parents."""
    candidates = []
    cwd = Path.cwd()
    candidates.append(cwd / ".env")
    candidates.append(cwd / ".claude" / ".env")
    for parent in cwd.parents:
        candidates.append(parent / ".env")
        candidates.append(parent / ".claude" / ".env")
    script_root = Path(__file__).resolve()
    for parent in script_root.parents:
        candidates.append(parent / ".env")
        candidates.append(parent / ".claude" / ".env")
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _resolve_env_value(keys: List[str]) -> str:
    """Resolve value from environment or .env file."""
    for key in keys:
        if os.environ.get(key):
            return os.environ[key]
    env_path = _find_env_file()
    if env_path:
        env = _load_env_file(env_path)
        for key in keys:
            if env.get(key):
                return env[key]
    return ""


def _send(proc: subprocess.Popen, payload: Dict[str, Any]) -> None:
    """Send a JSON-RPC message to the MCP server."""
    proc.stdin.write(json.dumps(payload) + "\n")
    proc.stdin.flush()


def _read_response(proc: subprocess.Popen, target_id: int, timeout_s: float) -> Dict[str, Any]:
    """Read a JSON-RPC response with the given ID."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        line = proc.stdout.readline()
        if not line:
            time.sleep(0.05)
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(message, dict) and message.get("id") == target_id:
            return message
    raise TimeoutError(f"Timed out waiting for response id={target_id}.")


def export_tools(
    command: List[str],
    env: Optional[Dict[str, str]] = None,
    protocol_version: str = "2024-11-05",
    timeout: float = 10.0,
    server_name: str = "mcp-server",
) -> List[Dict[str, Any]]:
    """Export tools from an MCP server.

    Args:
        command: Command to spawn the MCP server
        env: Additional environment variables for the server
        protocol_version: MCP protocol version
        timeout: Timeout for MCP responses in seconds
        server_name: Human-readable server name for logging

    Returns:
        List of tool definitions
    """
    proc_env = os.environ.copy()
    if env:
        proc_env.update(env)

    try:
        proc = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=proc_env,
        )
    except FileNotFoundError as e:
        raise RuntimeError(f"Failed to start MCP server: {e}") from e

    try:
        _send(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": protocol_version,
                    "clientInfo": {"name": f"{server_name}-tool-export", "version": "1.0"},
                    "capabilities": {},
                },
            },
        )
        _read_response(proc, 1, timeout)
        _send(proc, {"jsonrpc": "2.0", "method": "initialized", "params": {}})
        _send(proc, {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        response = _read_response(proc, 2, timeout)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except Exception:
            proc.kill()

    return response.get("result", {}).get("tools", [])


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export MCP tools from any MCP server.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Export Bright Data tools
  %(prog)s --server brightdata --output .tmp/brightdata-tools.json

  # Export Playwright tools
  %(prog)s --server playwright --output .tmp/playwright-tools.json

  # Custom server with command
  %(prog)s --server custom --command "npx -y @my/mcp" --output .tmp/tools.json

  # Custom server with environment
  %(prog)s --server custom --command "python3 server.py" --env "KEY=value" --output .tmp/tools.json
        """,
    )
    parser.add_argument(
        "--server",
        default="brightdata",
        help="Server name (preset: brightdata, playwright) or custom name",
    )
    parser.add_argument(
        "--command",
        help="Command to spawn MCP server (overrides preset). Use quotes for args.",
    )
    parser.add_argument(
        "--env",
        action="append",
        default=[],
        help="Environment variable as KEY=value (can be repeated)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(".tmp/mcp-tools.json"),
        help="Output path for tool list JSON.",
    )
    parser.add_argument(
        "--protocol-version",
        default="2024-11-05",
        help="MCP protocol version to use for initialization.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="Timeout in seconds for MCP responses.",
    )
    args = parser.parse_args()

    # Resolve command
    if args.command:
        command = shlex.split(args.command)
    elif args.server in PRESETS:
        command = PRESETS[args.server]["command"]
    else:
        print(f"Unknown server preset '{args.server}'. Use --command to specify.", file=sys.stderr)
        return 1

    # Resolve environment
    env: Dict[str, str] = {}
    for env_str in args.env:
        if "=" in env_str:
            key, value = env_str.split("=", 1)
            env[key] = value

    # For preset servers, resolve token from environment
    if args.server in PRESETS and not args.command:
        preset = PRESETS[args.server]
        if preset["env_keys"]:
            token = _resolve_env_value(preset["env_keys"])
            if not token:
                print(
                    f"Missing API token for {args.server}. "
                    f"Set one of: {', '.join(preset['env_keys'])}",
                    file=sys.stderr,
                )
                return 1
            if preset["env_var"]:
                env[preset["env_var"]] = token

    try:
        tools = export_tools(
            command=command,
            env=env if env else None,
            protocol_version=args.protocol_version,
            timeout=args.timeout,
            server_name=args.server,
        )
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps({"server": args.server, "tools": tools}, indent=2),
        encoding="utf-8",
    )
    print(f"Exported {len(tools)} tools from '{args.server}' to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

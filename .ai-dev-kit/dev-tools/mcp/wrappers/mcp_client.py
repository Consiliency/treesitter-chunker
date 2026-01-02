#!/usr/bin/env python3
"""Base MCP client with connection pooling for Progressive Disclosure.

This module provides a reusable MCP client that:
- Spawns MCP servers on-demand (first call)
- Maintains persistent connections with idle timeout
- Auto-terminates after configurable idle period (default 60s)
- Handles server crashes and reconnection

Usage:
    from mcp_client import MCPClient

    client = MCPClient(
        name="playwright",
        command=["npx", "-y", "@playwright/mcp@latest"],
        idle_timeout=60.0
    )

    # First call spawns the server
    result = client.call("browser_navigate", {"url": "https://example.com"})

    # Subsequent calls reuse the connection
    result = client.call("browser_snapshot", {})

    # Server auto-terminates after 60s of inactivity
    # Or manually close:
    client.close()
"""
from __future__ import annotations

import atexit
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable


class MCPClient:
    """MCP client with connection pooling and idle timeout."""

    # Class-level registry for cleanup on exit
    _instances: List["MCPClient"] = []
    _cleanup_registered = False

    def __init__(
        self,
        name: str,
        command: List[str],
        env: Optional[Dict[str, str]] = None,
        idle_timeout: float = 60.0,
        protocol_version: str = "2024-11-05",
        response_timeout: float = 30.0,
    ):
        """Initialize MCP client.

        Args:
            name: Human-readable name for this server
            command: Command to spawn the MCP server (e.g., ["npx", "-y", "@playwright/mcp@latest"])
            env: Additional environment variables for the server
            idle_timeout: Seconds of inactivity before auto-terminating (0 = never)
            protocol_version: MCP protocol version for initialization
            response_timeout: Timeout in seconds for individual RPC calls
        """
        self.name = name
        self.command = command
        self.env = env or {}
        self.idle_timeout = idle_timeout
        self.protocol_version = protocol_version
        self.response_timeout = response_timeout

        self._proc: Optional[subprocess.Popen] = None
        self._lock = threading.Lock()
        self._last_activity = time.time()
        self._request_id = 0
        self._idle_timer: Optional[threading.Timer] = None
        self._initialized = False
        self._tools: List[Dict[str, Any]] = []

        # Register for cleanup
        MCPClient._instances.append(self)
        if not MCPClient._cleanup_registered:
            atexit.register(MCPClient._cleanup_all)
            MCPClient._cleanup_registered = True

    @classmethod
    def _cleanup_all(cls) -> None:
        """Clean up all MCP client instances on exit."""
        for instance in cls._instances:
            try:
                instance.close()
            except Exception:
                pass

    def _start_server(self) -> None:
        """Start the MCP server process."""
        if self._proc is not None and self._proc.poll() is None:
            return  # Already running

        env = os.environ.copy()
        env.update(self.env)

        try:
            self._proc = subprocess.Popen(
                self.command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
                bufsize=1,  # Line buffered
            )
        except FileNotFoundError as e:
            raise RuntimeError(f"Failed to start MCP server '{self.name}': {e}") from e

        self._initialized = False
        self._initialize()

    def _initialize(self) -> None:
        """Send MCP initialization handshake."""
        if self._initialized:
            return

        # Initialize request
        self._send({
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "initialize",
            "params": {
                "protocolVersion": self.protocol_version,
                "clientInfo": {"name": f"mcp-wrapper-{self.name}", "version": "1.0"},
                "capabilities": {},
            },
        })

        # Wait for initialize response
        response = self._read_response(self._request_id, self.response_timeout)
        if "error" in response:
            raise RuntimeError(f"MCP initialization failed: {response['error']}")

        # Send initialized notification
        self._send({"jsonrpc": "2.0", "method": "initialized", "params": {}})

        # Query available tools
        self._send({
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "tools/list",
            "params": {},
        })

        tools_response = self._read_response(self._request_id, self.response_timeout)
        self._tools = tools_response.get("result", {}).get("tools", [])

        self._initialized = True

    def _next_id(self) -> int:
        """Generate next request ID."""
        self._request_id += 1
        return self._request_id

    def _send(self, payload: Dict[str, Any]) -> None:
        """Send a JSON-RPC message to the server."""
        if self._proc is None or self._proc.stdin is None:
            raise RuntimeError("MCP server not running")

        message = json.dumps(payload) + "\n"
        self._proc.stdin.write(message)
        self._proc.stdin.flush()

    def _read_response(self, target_id: int, timeout: float) -> Dict[str, Any]:
        """Read a JSON-RPC response with matching ID."""
        if self._proc is None or self._proc.stdout is None:
            raise RuntimeError("MCP server not running")

        deadline = time.time() + timeout

        while time.time() < deadline:
            if self._proc.poll() is not None:
                stderr = self._proc.stderr.read() if self._proc.stderr else ""
                raise RuntimeError(f"MCP server crashed: {stderr}")

            line = self._proc.stdout.readline()
            if not line:
                time.sleep(0.01)
                continue

            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                continue

            # Handle notifications (no id field)
            if "id" not in message:
                continue

            if message.get("id") == target_id:
                return message

        raise TimeoutError(f"Timeout waiting for response id={target_id}")

    def _reset_idle_timer(self) -> None:
        """Reset the idle timeout timer."""
        self._last_activity = time.time()

        if self.idle_timeout <= 0:
            return

        if self._idle_timer is not None:
            self._idle_timer.cancel()

        self._idle_timer = threading.Timer(self.idle_timeout, self._idle_shutdown)
        self._idle_timer.daemon = True
        self._idle_timer.start()

    def _idle_shutdown(self) -> None:
        """Shutdown server after idle timeout."""
        with self._lock:
            elapsed = time.time() - self._last_activity
            if elapsed >= self.idle_timeout:
                self._shutdown()

    def _shutdown(self) -> None:
        """Shutdown the MCP server."""
        if self._idle_timer is not None:
            self._idle_timer.cancel()
            self._idle_timer = None

        if self._proc is not None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                self._proc.kill()
            self._proc = None

        self._initialized = False

    def is_running(self) -> bool:
        """Check if the MCP server is currently running."""
        return self._proc is not None and self._proc.poll() is None

    def get_tools(self) -> List[Dict[str, Any]]:
        """Get list of available tools from this server."""
        with self._lock:
            if not self.is_running():
                self._start_server()
            return self._tools.copy()

    def call(self, tool_name: str, arguments: Optional[Dict[str, Any]] = None) -> Any:
        """Call an MCP tool.

        Args:
            tool_name: Name of the tool to call
            arguments: Tool arguments (optional)

        Returns:
            Tool result (content from the response)

        Raises:
            RuntimeError: If server fails or returns an error
            TimeoutError: If call times out
        """
        with self._lock:
            # Ensure server is running
            if not self.is_running():
                self._start_server()

            # Reset idle timer
            self._reset_idle_timer()

            # Build and send request
            request_id = self._next_id()
            self._send({
                "jsonrpc": "2.0",
                "id": request_id,
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": arguments or {},
                },
            })

            # Read response
            response = self._read_response(request_id, self.response_timeout)

            if "error" in response:
                error = response["error"]
                raise RuntimeError(f"MCP tool error: {error.get('message', error)}")

            result = response.get("result", {})

            # Extract content from result
            content = result.get("content", [])
            if isinstance(content, list) and len(content) == 1:
                item = content[0]
                if item.get("type") == "text":
                    return item.get("text", "")

            return result

    def close(self) -> None:
        """Close the MCP client and shutdown server."""
        with self._lock:
            self._shutdown()
            if self in MCPClient._instances:
                MCPClient._instances.remove(self)


def load_env_file(path: Optional[Path] = None) -> Dict[str, str]:
    """Load environment variables from a .env file.

    Args:
        path: Path to .env file. If None, searches common locations.

    Returns:
        Dictionary of environment variables
    """
    if path is None:
        # Search common locations
        candidates = [
            Path.cwd() / ".env",
            Path.cwd() / ".claude" / ".env",
        ]
        for parent in Path.cwd().parents:
            candidates.append(parent / ".env")
            candidates.append(parent / ".claude" / ".env")

        for candidate in candidates:
            if candidate.exists():
                path = candidate
                break

    if path is None or not path.exists():
        return {}

    env: Dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        env[key.strip()] = value.strip()

    return env


if __name__ == "__main__":
    # Simple test
    import argparse

    parser = argparse.ArgumentParser(description="Test MCP client")
    parser.add_argument("--command", nargs="+", required=True, help="MCP server command")
    parser.add_argument("--tool", help="Tool to call")
    parser.add_argument("--args", type=json.loads, default={}, help="Tool arguments as JSON")
    parser.add_argument("--list-tools", action="store_true", help="List available tools")
    args = parser.parse_args()

    client = MCPClient(name="test", command=args.command)

    try:
        if args.list_tools:
            tools = client.get_tools()
            for tool in tools:
                print(f"- {tool['name']}: {tool.get('description', 'No description')}")
        elif args.tool:
            result = client.call(args.tool, args.args)
            print(json.dumps(result, indent=2) if isinstance(result, (dict, list)) else result)
        else:
            print("Specify --tool or --list-tools")
            sys.exit(1)
    finally:
        client.close()

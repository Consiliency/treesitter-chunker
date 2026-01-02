#!/usr/bin/env python3
"""Build a minimal MCP tool index for progressive disclosure.

This script takes a full MCP tool export and creates a minimal index
with just names, servers, and descriptions. This keeps context small
by only loading full tool schemas when actually needed.

Usage:
    python3 index_mcp_tools.py --input .tmp/mcp-tools.json --output .tmp/tool-index.json

Options:
    --include-schema    Include full input/output schemas (larger, but complete)
    --default-server    Server name for tools without a server prefix
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple


def _split_name(name: str) -> Tuple[str, str]:
    """Split tool name into server and tool parts."""
    if "__" in name:
        parts = name.split("__")
        if len(parts) >= 3 and parts[0].lower() == "mcp":
            return parts[1], "__".join(parts[2:])
        return parts[0], "__".join(parts[1:])
    if "." in name:
        server, tool = name.split(".", 1)
        return server, tool
    return "unknown", name


def _pick(tool: Dict[str, Any], keys: List[str]) -> Any:
    """Pick the first available key from a dict."""
    for key in keys:
        if key in tool:
            return tool[key]
    return None


def _normalize_tools(data: Any) -> List[Dict[str, Any]]:
    """Normalize various tool list formats."""
    if isinstance(data, list):
        return [t for t in data if isinstance(t, dict)]
    if isinstance(data, dict):
        if isinstance(data.get("tools"), list):
            return [t for t in data["tools"] if isinstance(t, dict)]
        if isinstance(data.get("data"), list):
            return [t for t in data["data"] if isinstance(t, dict)]
    return []


def _load_input(path: Path | None) -> Any:
    """Load input from file or stdin."""
    if path:
        return json.loads(path.read_text(encoding="utf-8"))
    raw = sys.stdin.read()
    if not raw.strip():
        raise ValueError("No input provided. Use --input or pipe JSON to stdin.")
    return json.loads(raw)


def _write_json(path: Path, payload: Any) -> None:
    """Write JSON to a file, creating parent directories."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _build_index(
    tools: List[Dict[str, Any]],
    include_schema: bool,
    default_server: str | None,
) -> List[Dict[str, Any]]:
    """Build a minimal tool index."""
    index: List[Dict[str, Any]] = []
    for tool in tools:
        name = str(tool.get("name", "")).strip()
        if not name:
            continue
        server, tool_name = _split_name(name)
        if default_server and server == "unknown":
            server = default_server
        description = _pick(tool, ["description", "summary", "help"]) or ""
        entry: Dict[str, Any] = {
            "name": name,
            "server": server,
            "tool": tool_name,
            "description": description,
        }
        if include_schema:
            input_schema = _pick(tool, ["input_schema", "inputSchema", "parameters", "schema"])
            output_schema = _pick(tool, ["output_schema", "outputSchema", "returns"])
            if input_schema is not None:
                entry["input_schema"] = input_schema
            if output_schema is not None:
                entry["output_schema"] = output_schema
        index.append(entry)
    index.sort(key=lambda item: (item.get("server", ""), item.get("tool", ""), item.get("name", "")))
    return index


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a minimal MCP tool index.")
    parser.add_argument("--input", type=Path, help="Path to MCP tool list JSON.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(".tmp/tool-index.json"),
        help="Output path for the tool index JSON.",
    )
    parser.add_argument(
        "--include-schema",
        action="store_true",
        help="Include input/output schema fields in index.",
    )
    parser.add_argument(
        "--default-server",
        help="Server name to use when tool names have no server prefix.",
    )
    args = parser.parse_args()

    try:
        data = _load_input(args.input)
    except Exception as exc:
        print(f"Failed to load input: {exc}", file=sys.stderr)
        return 1

    tools = _normalize_tools(data)
    default_server = args.default_server.strip() if args.default_server else None
    index = _build_index(tools, include_schema=args.include_schema, default_server=default_server)
    _write_json(args.output, {"tools": index})
    print(f"Built index with {len(index)} tools at {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

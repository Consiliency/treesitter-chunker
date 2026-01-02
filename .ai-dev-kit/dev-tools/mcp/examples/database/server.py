#!/usr/bin/env python3
"""
Database MCP Server

A simple MCP server for querying SQLite databases.
Demonstrates read-only database access patterns.

Configuration in .mcp.json:
    {
      "mcpServers": {
        "database": {
          "command": "python3",
          "args": ["dev-tools/mcp/examples/database/server.py"],
          "env": {
            "DATABASE_PATH": "./data/app.db",
            "MAX_ROWS": "100"
          }
        }
      }
    }

For other databases (Postgres, MySQL), see the official MCP servers:
    - @modelcontextprotocol/server-postgres
    - @modelcontextprotocol/server-mysql
"""

import asyncio
import os
import sqlite3
import sys
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent, Resource

# Configuration
DATABASE_PATH = os.environ.get("DATABASE_PATH", ":memory:")
MAX_ROWS = int(os.environ.get("MAX_ROWS", "100"))
READ_ONLY = os.environ.get("READ_ONLY", "true").lower() == "true"

server = Server("database")


def get_connection() -> sqlite3.Connection:
    """Get a database connection."""
    if DATABASE_PATH == ":memory:":
        # Create a demo database for testing
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, email TEXT)")
        conn.execute("INSERT INTO users VALUES (1, 'Alice', 'alice@example.com')")
        conn.execute("INSERT INTO users VALUES (2, 'Bob', 'bob@example.com')")
        conn.execute("CREATE TABLE products (id INTEGER PRIMARY KEY, name TEXT, price REAL)")
        conn.execute("INSERT INTO products VALUES (1, 'Widget', 9.99)")
        conn.execute("INSERT INTO products VALUES (2, 'Gadget', 19.99)")
        conn.commit()
        return conn

    path = Path(DATABASE_PATH)
    if not path.exists():
        raise FileNotFoundError(f"Database not found: {DATABASE_PATH}")

    # Use URI mode for read-only access
    uri = f"file:{path}?mode=ro" if READ_ONLY else f"file:{path}"
    return sqlite3.connect(uri, uri=True)


def format_results(cursor: sqlite3.Cursor, max_rows: int) -> str:
    """Format query results as a table."""
    columns = [desc[0] for desc in cursor.description] if cursor.description else []
    rows = cursor.fetchmany(max_rows + 1)

    if not columns:
        return "(no results)"

    # Calculate column widths
    widths = [len(col) for col in columns]
    for row in rows[:max_rows]:
        for i, val in enumerate(row):
            widths[i] = max(widths[i], len(str(val)))

    # Format header
    header = " | ".join(col.ljust(widths[i]) for i, col in enumerate(columns))
    separator = "-+-".join("-" * w for w in widths)

    # Format rows
    formatted_rows = []
    for row in rows[:max_rows]:
        formatted_rows.append(
            " | ".join(str(val).ljust(widths[i]) for i, val in enumerate(row))
        )

    result = [header, separator] + formatted_rows

    if len(rows) > max_rows:
        result.append(f"... (truncated, showing {max_rows} of more rows)")

    return "\n".join(result)


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Define available database tools."""
    tools = [
        Tool(
            name="query",
            description=f"Execute a SQL query against the database. Returns up to {MAX_ROWS} rows. {'Read-only mode.' if READ_ONLY else 'Read-write mode.'}",
            inputSchema={
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": "SQL query to execute",
                    },
                },
                "required": ["sql"],
            },
        ),
        Tool(
            name="list_tables",
            description="List all tables in the database with their schemas.",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="describe_table",
            description="Get the schema of a specific table.",
            inputSchema={
                "type": "object",
                "properties": {
                    "table": {
                        "type": "string",
                        "description": "Name of the table to describe",
                    },
                },
                "required": ["table"],
            },
        ),
    ]
    return tools


@server.list_resources()
async def list_resources() -> list[Resource]:
    """Expose database schema as a resource."""
    return [
        Resource(
            uri=f"db://schema",
            name="Database Schema",
            description="Full schema of all tables",
            mimeType="text/plain",
        ),
    ]


@server.read_resource()
async def read_resource(uri: str) -> str:
    """Read database schema resource."""
    if uri == "db://schema":
        try:
            conn = get_connection()
            cursor = conn.execute(
                "SELECT name, sql FROM sqlite_master WHERE type='table' ORDER BY name"
            )
            tables = cursor.fetchall()
            conn.close()

            if not tables:
                return "No tables found in database."

            return "\n\n".join(f"-- Table: {name}\n{sql}" for name, sql in tables if sql)
        except Exception as e:
            return f"Error reading schema: {e}"

    raise ValueError(f"Unknown resource: {uri}")


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle database tool invocations."""
    try:
        conn = get_connection()

        if name == "query":
            sql = arguments.get("sql", "")

            # Basic SQL injection prevention for read-only mode
            if READ_ONLY:
                sql_upper = sql.upper().strip()
                if any(
                    sql_upper.startswith(kw)
                    for kw in ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE"]
                ):
                    return [
                        TextContent(
                            type="text",
                            text="Error: Write operations not allowed in read-only mode.",
                        )
                    ]

            cursor = conn.execute(sql)
            result = format_results(cursor, MAX_ROWS)

            if cursor.rowcount >= 0 and not cursor.description:
                result = f"Query executed. Rows affected: {cursor.rowcount}"

            conn.close()
            return [TextContent(type="text", text=result)]

        elif name == "list_tables":
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
            tables = [row[0] for row in cursor.fetchall()]
            conn.close()

            if not tables:
                return [TextContent(type="text", text="No tables found.")]

            return [TextContent(type="text", text="Tables:\n" + "\n".join(f"  - {t}" for t in tables))]

        elif name == "describe_table":
            table = arguments.get("table", "")
            cursor = conn.execute(f"PRAGMA table_info({table})")
            columns = cursor.fetchall()
            conn.close()

            if not columns:
                return [TextContent(type="text", text=f"Table '{table}' not found.")]

            result = [f"Table: {table}", ""]
            result.append("Column          | Type        | Nullable | Default  | PK")
            result.append("----------------|-------------|----------|----------|---")
            for col in columns:
                cid, name, type_, notnull, default, pk = col
                nullable = "NO" if notnull else "YES"
                default = str(default) if default else ""
                pk_str = "YES" if pk else ""
                result.append(f"{name:15} | {type_:11} | {nullable:8} | {default:8} | {pk_str}")

            return [TextContent(type="text", text="\n".join(result))]

        else:
            raise ValueError(f"Unknown tool: {name}")

    except sqlite3.Error as e:
        return [TextContent(type="text", text=f"Database error: {e}")]
    except Exception as e:
        return [TextContent(type="text", text=f"Error: {type(e).__name__}: {e}")]


async def main():
    """Run the database MCP server."""
    print(f"Database MCP Server starting...", file=sys.stderr)
    print(f"Database: {DATABASE_PATH}", file=sys.stderr)
    print(f"Read-only: {READ_ONLY}, Max rows: {MAX_ROWS}", file=sys.stderr)

    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())

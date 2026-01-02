# Database MCP Server

A simple MCP server for querying SQLite databases with read-only support.

## Features

- **query**: Execute SQL queries with result formatting
- **list_tables**: Show all tables in the database
- **describe_table**: Get table schema details
- Read-only mode by default (prevents accidental writes)
- Result truncation to prevent token bloat

## Configuration

Add to your `.mcp.json`:

```json
{
  "mcpServers": {
    "database": {
      "command": "python3",
      "args": ["dev-tools/mcp/examples/database/server.py"],
      "env": {
        "DATABASE_PATH": "./data/app.db",
        "MAX_ROWS": "100",
        "READ_ONLY": "true"
      }
    }
  }
}
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_PATH` | Path to SQLite database file | `:memory:` (demo DB) |
| `MAX_ROWS` | Maximum rows to return per query | `100` |
| `READ_ONLY` | Prevent write operations | `true` |

## Demo Mode

If `DATABASE_PATH` is not set or set to `:memory:`, the server creates a demo database with sample tables:

- `users`: id, name, email
- `products`: id, name, price

## Usage Examples

Once configured, Claude Code can use these tools:

```
"List all tables in the database"
"Describe the users table"
"SELECT * FROM users WHERE name LIKE 'A%'"
"SELECT name, price FROM products ORDER BY price DESC LIMIT 5"
```

## Dependencies

```bash
uv pip install mcp
```

SQLite is included in Python's standard library.

## For Other Databases

This example uses SQLite for simplicity. For production databases, use the official MCP servers:

### PostgreSQL

```bash
claude mcp add postgres -- npx -y @modelcontextprotocol/server-postgres postgresql://user:pass@localhost/db
```

### MySQL

```bash
claude mcp add mysql -- npx -y @modelcontextprotocol/server-mysql mysql://user:pass@localhost/db
```

## Extending

To add write support, set `READ_ONLY=false` and remove the write check in `call_tool()`. Consider adding:

- Transaction support
- Parameterized queries
- Query history
- Schema diff tools

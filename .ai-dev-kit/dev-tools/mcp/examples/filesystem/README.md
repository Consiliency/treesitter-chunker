# Filesystem MCP Server

A simple MCP server that provides safe file operations within allowed paths.

## Features

- **read_file**: Read file contents
- **write_file**: Write content to a file (creates parent directories)
- **list_directory**: List directory contents
- **file_info**: Get file metadata (size, type, modified time)

## Security

All operations are restricted to paths specified in the `ALLOWED_PATHS` environment variable. Attempts to access files outside these paths will be denied.

## Configuration

Add to your `.mcp.json`:

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "python3",
      "args": ["dev-tools/mcp/examples/filesystem/server.py"],
      "env": {
        "ALLOWED_PATHS": "./src:./docs:./config"
      }
    }
  }
}
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `ALLOWED_PATHS` | Colon-separated list of allowed directories | `.` (current dir) |

## Usage Examples

Once configured, Claude Code can use these tools:

```
"Read the contents of src/main.py"
"List all files in the docs directory"
"Write 'Hello World' to output/test.txt"
"Get info about config/settings.json"
```

## Dependencies

```bash
uv pip install mcp
```

## Customization

This server is a starting point. Consider adding:

- File search/grep functionality
- File move/copy/delete operations
- Pattern-based file filtering
- Binary file handling
- File watching for changes

# Python MCP Server Template

A starter template for building MCP servers in Python using the official SDK.

## Quick Start

1. **Copy this template**
   ```bash
   cp -r dev-tools/mcp/_templates/python dev-tools/mcp/my-server
   ```

2. **Install dependencies**
   ```bash
   cd dev-tools/mcp/my-server
   uv pip install -r requirements.txt
   ```

3. **Modify `server.py`**
   - Update the server name
   - Add your tools in `list_tools()`
   - Implement tool logic in `call_tool()`

4. **Register in `.mcp.json`**
   ```json
   {
     "mcpServers": {
       "my-server": {
         "command": "python3",
         "args": ["dev-tools/mcp/my-server/server.py"]
       }
     }
   }
   ```

5. **Test your server**
   ```bash
   # In Claude Code, use /mcp to check status
   ```

## Server Structure

```python
@server.list_tools()
async def list_tools() -> list[Tool]:
    """Define available tools with their schemas."""
    return [
        Tool(
            name="my_tool",
            description="What this tool does",
            inputSchema={
                "type": "object",
                "properties": {
                    "param1": {"type": "string", "description": "..."},
                },
                "required": ["param1"],
            },
        ),
    ]

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool invocations."""
    if name == "my_tool":
        # Your implementation here
        return [TextContent(type="text", text="result")]
```

## Adding Resources

MCP servers can also expose resources (files, data):

```python
from mcp.types import Resource

@server.list_resources()
async def list_resources() -> list[Resource]:
    return [
        Resource(
            uri="file:///path/to/resource",
            name="My Resource",
            mimeType="text/plain",
        ),
    ]

@server.read_resource()
async def read_resource(uri: str) -> str:
    # Return resource content
    return "Resource content here"
```

## Environment Variables

Access environment variables passed from `.mcp.json`:

```python
import os

allowed_paths = os.environ.get("ALLOWED_PATHS", "./")
api_key = os.environ.get("API_KEY")
```

## Resources

- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [MCP Specification](https://spec.modelcontextprotocol.io/)
- [Example Servers](https://github.com/modelcontextprotocol/servers)

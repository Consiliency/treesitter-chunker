# Agent Tools (Code-as-API Pattern)

> **Important**: This is **NOT MCP**. These are filesystem-based tools that Claude discovers by browsing directories and executes via native Bash. See [MCP vs Code-as-API](#mcp-vs-code-as-api) below.

This directory contains discoverable tools that AI agents can find and execute on-demand, following [Anthropic's code-as-API pattern](https://www.anthropic.com/engineering/code-execution-with-mcp).

## How It Works

Instead of loading all tool definitions into context upfront (which consumes tokens), agents:

1. **Browse the filesystem** to discover available tools (`ls`, `tree`, or Read tool)
2. **Read specific tool files** to understand inputs/outputs (only when needed)
3. **Execute tools via Bash** - `python3 dev-tools/agent-tools/examples/api-wrapper/get_resource.py`

This reduces token usage by ~98% compared to loading hundreds of tool definitions at startup.

```
agent-tools/
├── README.md                 # This file
├── search_tools.py           # Meta-tool: search for tools by keyword
├── _template/               # Templates for new tools
└── examples/
    └── api-wrapper/         # Example: wrap an external API
        ├── __init__.py
        ├── get_resource.py
        └── update_resource.py
```

## Execution Environment

**Tools run directly on your machine via Bash** - they are NOT sandboxed.

| What This Means | Implication |
|-----------------|-------------|
| Full filesystem access | Tools can read/write any files your user can |
| Network access | Tools can make API calls, web requests |
| No resource limits | No automatic timeout or memory limits |
| Your user permissions | Tools run as you, not in isolation |

This is the same security model as Claude Code's native Bash tool. If you need sandboxing, consider:
- Docker containers (future enhancement)
- The `code-sandbox` MCP server (provides timeout/output limits only)

## MCP vs Code-as-API

These are **complementary patterns**, not alternatives:

| Aspect | MCP Servers (Eager) | MCP Wrappers | Code-as-API (This Directory) |
|--------|---------------------|--------------|------------------------------|
| **How tools load** | All at startup via `.mcp.json` | On-demand via Python wrapper | On-demand via filesystem |
| **Token cost** | Upfront (all tool schemas) | Minimal (only when called) | Minimal (only what's needed) |
| **Execution** | Via MCP protocol | Via MCP protocol (wrapped) | Via Bash/subprocess |
| **Best for** | Frequent use, real-time | Third-party services | Internal utilities |
| **Examples** | N/A (avoid eager loading) | Playwright, Bright Data | Data processing, scripts |

**Use MCP Wrappers** (`dev-tools/mcp/wrappers/`): For external services like browser automation or web scraping that need MCP protocol but shouldn't load at startup.

**Use Code-as-API** (this directory): For internal tools, data processing, and simple script execution.

**Avoid Eager MCP Loading**: Don't add servers to `.mcp.json` unless absolutely necessary - it wastes context tokens.

### MCP Wrappers

The `dev-tools/mcp/wrappers/` directory provides Python wrappers for MCP servers that implement **Progressive Disclosure**:

```bash
# Browser automation (spawns Playwright MCP on-demand)
python3 dev-tools/mcp/wrappers/playwright_wrapper.py navigate "https://example.com"
python3 dev-tools/mcp/wrappers/playwright_wrapper.py snapshot

# Web scraping with CAPTCHA bypass (spawns Bright Data MCP on-demand)
python3 dev-tools/mcp/wrappers/brightdata_wrapper.py scrape "https://example.com"
```

See `dev-tools/mcp/wrappers/README.md` for details.

## Using Agent Tools

### Discovery

Claude discovers tools by exploring the filesystem:

```bash
# List available tool categories
ls dev-tools/agent-tools/examples/

# Read a specific tool to understand it
cat dev-tools/agent-tools/examples/api-wrapper/get_resource.py

# Or use the search helper
python3 dev-tools/agent-tools/search_tools.py --search "api"
```

### Execution

Tools are executed via Bash:

```bash
# Run a tool directly
python3 dev-tools/agent-tools/examples/api-wrapper/get_resource.py --id 123

# Or import in a Python session
python3 -c "from examples.api_wrapper.get_resource import run; print(run('123'))"
```

## Creating New Tools

1. Copy the template:
   ```bash
   cp -r dev-tools/agent-tools/_template dev-tools/agent-tools/my-tools
   ```

2. Create tool files with the standard format:
   ```python
   """
   Tool: my_tool
   Description: What this tool does

   Args:
       param1 (str): Description of param1
       param2 (int): Description of param2

   Returns:
       dict: Description of return value
   """

   def run(param1: str, param2: int = 10) -> dict:
       # Implementation
       return {"result": "..."}

   if __name__ == "__main__":
       import sys
       # Simple CLI wrapper
       result = run(sys.argv[1] if len(sys.argv) > 1 else "default")
       print(result)
   ```

3. Document in the directory's `__init__.py`

## Tool File Format

Each tool file should:

1. Have a clear docstring with Args and Returns
2. Export a `run()` function as the main entry point
3. Use type hints for discoverability
4. Include a `__main__` block for CLI execution
5. Handle errors gracefully

```python
"""
Tool: fetch_weather
Description: Get current weather for a location

Args:
    city (str): City name
    units (str): 'celsius' or 'fahrenheit' (default: 'celsius')

Returns:
    dict: Weather data with temp, conditions, humidity
"""

import os
import sys
import json
from urllib.request import urlopen

API_KEY = os.environ.get("WEATHER_API_KEY", "")

def run(city: str, units: str = "celsius") -> dict:
    """Fetch weather for a city."""
    if not API_KEY:
        raise ValueError("WEATHER_API_KEY environment variable required")

    url = f"https://api.weather.com/v1/current?city={city}&units={units}&key={API_KEY}"

    with urlopen(url) as response:
        return json.loads(response.read().decode())

if __name__ == "__main__":
    city = sys.argv[1] if len(sys.argv) > 1 else "London"
    print(json.dumps(run(city), indent=2))
```

## Search Tools

The `search_tools.py` utility helps agents find relevant tools:

```bash
# Search by keyword
python3 dev-tools/agent-tools/search_tools.py --search "weather"

# List all available tools
python3 dev-tools/agent-tools/search_tools.py --list
```

## Future Enhancements

- **Docker sandboxing**: Run tools in isolated containers (not yet implemented)
- **Resource limits**: Automatic timeout and memory limits
- **Tool registry**: Centralized tool metadata for faster discovery

## Resources

- [Code Execution with MCP (Anthropic)](https://www.anthropic.com/engineering/code-execution-with-mcp) - Original pattern description
- [MCP Specification](https://spec.modelcontextprotocol.io/) - For traditional MCP servers
- [dev-tools/mcp/](../mcp/) - MCP server templates and examples

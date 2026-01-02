# MCP Wrappers for Progressive Disclosure

This directory contains Python wrappers that spawn MCP servers **on-demand** instead of loading them eagerly via `.mcp.json`. This implements the Progressive Disclosure pattern, keeping context clean until tools are actually needed.

## Why Progressive Disclosure?

When MCP servers are configured in `.mcp.json`, Claude Code loads ALL their tools at startup:

```
Before (Eager Loading):
┌─────────────────────────────────────────┐
│ Claude Code Startup                      │
│                                          │
│ .mcp.json → Load Playwright → 22 tools  │
│          → Load Brightdata → 6 tools    │
│                                          │
│ Context: ~5000 tokens of tool schemas   │
└─────────────────────────────────────────┘
```

With Progressive Disclosure:

```
After (On-Demand):
┌─────────────────────────────────────────┐
│ Claude Code Startup                      │
│                                          │
│ .mcp.json → Empty                        │
│                                          │
│ Context: 0 tokens of MCP tools          │
└─────────────────────────────────────────┘

When browser automation needed:
┌─────────────────────────────────────────┐
│ python3 playwright_wrapper.py navigate "https://..." │
│                                          │
│ Wrapper spawns MCP server → executes → result │
│ Server stays alive for 60s (connection pooling) │
└─────────────────────────────────────────┘
```

## Available Wrappers

### PlaywrightWrapper

Browser automation via Playwright MCP server.

**Prerequisites:**
- Chrome running with debugging: `google-chrome --remote-debugging-port=9222`

**CLI:**
```bash
python3 playwright_wrapper.py navigate "https://example.com"
python3 playwright_wrapper.py snapshot
python3 playwright_wrapper.py click --ref "button[0]" --element "Submit"
python3 playwright_wrapper.py evaluate "document.title"
```

**Python:**
```python
from playwright_wrapper import PlaywrightWrapper

pw = PlaywrightWrapper()
pw.navigate("https://example.com")
snapshot = pw.snapshot()
title = pw.evaluate("document.title")
```

### BrightDataWrapper

Web scraping with CAPTCHA bypass via Bright Data MCP server.

**Prerequisites:**
- `BRIGHTDATA_API_KEY` environment variable or in `.env`

**CLI:**
```bash
python3 brightdata_wrapper.py scrape "https://example.com"
python3 brightdata_wrapper.py search "python tutorials"
```

**Python:**
```python
from brightdata_wrapper import BrightDataWrapper

bd = BrightDataWrapper()
content = bd.scrape_markdown("https://example.com")
results = bd.search("python tutorials")
```

## Creating Custom Wrappers

Use `MCPClient` as the base:

```python
from mcp_client import MCPClient

class MyWrapper:
    def __init__(self):
        self._client = MCPClient(
            name="my-server",
            command=["npx", "-y", "@my/mcp-server"],
            env={"API_KEY": "..."},
            idle_timeout=60.0,  # Auto-terminate after 60s idle
        )

    def my_tool(self, arg: str) -> str:
        return self._client.call("tool_name", {"arg": arg})
```

## Connection Pooling

Wrappers use connection pooling by default:
- First call spawns the MCP server
- Subsequent calls reuse the connection
- Server auto-terminates after 60s of inactivity
- Manual shutdown: `wrapper.shutdown()`

This balances performance (no startup overhead per call) with resource efficiency (no idle servers).

## Integration with Agents

The `docs-fetch-url` agent uses these wrappers for Tier 3 (Playwright) and Tier 4 (Bright Data):

```python
# Tier 3: Browser automation
pw = PlaywrightWrapper()
pw.navigate(url)
content = pw.evaluate("document.documentElement.outerHTML")
pw.close()

# Tier 4: CAPTCHA bypass (only if Tier 3 fails)
bd = BrightDataWrapper()
content = bd.scrape_markdown(url)
```

## Files

| File | Description |
|------|-------------|
| `mcp_client.py` | Base MCP client with connection pooling |
| `playwright_wrapper.py` | Browser automation wrapper |
| `brightdata_wrapper.py` | Web scraping wrapper |
| `__init__.py` | Package exports |

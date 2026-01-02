# MCP Servers

This directory contains Model Context Protocol (MCP) servers for extending AI agent capabilities.

## What is MCP?

The [Model Context Protocol](https://modelcontextprotocol.io/) is an open standard for connecting AI assistants to external tools and data sources. MCP servers expose tools that Claude Code and other AI agents can discover and use.

## Directory Structure

```
dev-tools/mcp/
├── README.md                 # This file
├── _templates/               # Starter templates for new servers
│   ├── python/              # Python MCP server template
│   └── typescript/          # TypeScript MCP server template
└── examples/                 # Example server implementations
    ├── filesystem/          # Safe file operations
    ├── code-sandbox/        # Code execution in sandbox
    ├── database/            # Database query wrapper
    └── github/              # GitHub API wrapper
```

## Language Support

Templates are provided for Python and TypeScript. For other languages, use the official MCP SDKs where available or wrap the service with a small Python/TypeScript bridge.

## Quick Start

### Using an Example Server

1. Choose an example from `examples/`
2. Install dependencies (see example's README)
3. Add to your `.mcp.json`:

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "python3",
      "args": ["dev-tools/mcp/examples/filesystem/server.py"],
      "env": {
        "ALLOWED_PATHS": "./src:./docs"
      }
    }
  }
}
```

4. Restart Claude Code or run `/mcp` to verify

### Creating a New Server

1. Copy a template:
   ```bash
   cp -r dev-tools/mcp/_templates/python dev-tools/mcp/my-server
   ```

2. Edit `server.py` to add your tools

3. Register in `.mcp.json`

4. Test with `/mcp` in Claude Code

## Configuration

### Project-Scoped (`.mcp.json`)

Shared with your team via version control. Use for project-specific tools.

```json
{
  "mcpServers": {
    "my-tool": {
      "command": "python3",
      "args": ["dev-tools/mcp/my-tool/server.py"]
    }
  }
}
```

### User-Scoped (`.mcp.local.json`)

For personal tools or those requiring secrets. Add to `.gitignore`.

```json
{
  "mcpServers": {
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_TOKEN}"
      }
    }
  }
}
```

### Environment Variables

Use `${VAR}` or `${VAR:-default}` syntax:

```json
{
  "env": {
    "API_KEY": "${MY_API_KEY}",
    "TIMEOUT": "${TIMEOUT:-30}"
  }
}
```

## Available Examples

| Server | Description | Use Case |
|--------|-------------|----------|
| `filesystem` | Safe file read/write | Sandboxed file access |
| `code-sandbox` | Execute code safely | Run untrusted code |
| `database` | Query databases | Data exploration |
| `github` | GitHub API wrapper | Issue/PR management |

## Browser Automation (Playwright MCP)

The Playwright MCP server provides browser automation for tasks like:
- Web scraping and data extraction
- Human-in-the-loop verification (CAPTCHA solving)
- Screenshot capture and visual testing
- Form filling and interaction

### Basic Setup (Linux/macOS)

```json
{
  "mcpServers": {
    "playwright": {
      "command": "npx",
      "args": ["-y", "@playwright/mcp@latest"]
    }
  }
}
```

### WSL2 + Windows Chrome Setup

When running Claude Code in WSL2, use Chrome DevTools Protocol (CDP) to connect to a Windows Chrome instance. This enables headed browser mode for human intervention.

**Step 1: Configure MCP** (in `.mcp.json`):
```json
{
  "mcpServers": {
    "playwright": {
      "command": "npx",
      "args": ["-y", "@playwright/mcp@latest", "--cdp-endpoint", "http://localhost:9222"]
    }
  }
}
```

**Step 2: Launch Chrome with debugging**:

**Option A: Automatic launch (recommended)**:
Enable auto-launch when activating the environment:
```bash
export AUTO_LAUNCH_CHROME_DEBUG=true
source activate-env.sh
```
Chrome will automatically launch if not already running.

**Option B: Using the helper script (from WSL2)**:
```bash
./dev-tools/scripts/launch-chrome-debug.sh
```

**Option C: Manual launch (in Windows PowerShell)**:
```powershell
& "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir=C:\temp\chrome-debug-profile
```

> **Important**: The `--user-data-dir` flag is required. Without it, Chrome may restore previous sessions and ignore the debugging flag.

**Step 3: Verify connection**:
- In Windows Chrome, navigate to `http://localhost:9222/json/version`
- You should see JSON output with browser version info
- Or run the verification script: `./dev-tools/scripts/verify-playwright-mcp.sh`

**Verification script options**:
```bash
# Human-readable output (default)
./dev-tools/scripts/verify-playwright-mcp.sh

# JSON output for programmatic use
./dev-tools/scripts/verify-playwright-mcp.sh --json

# Auto-launch Chrome if not running
./dev-tools/scripts/verify-playwright-mcp.sh --auto-launch
```

**Exit codes**:
- `0` = Playwright MCP ready to use
- `1` = Not configured or missing dependencies
- `2` = Chrome debugging endpoint not running

**WSL2 Networking Notes**:
- **Mirrored networking mode** (default in newer WSL2): Use `localhost` (recommended)
- **NAT mode**: Use the Windows host IP from `cat /etc/resolv.conf | grep nameserver`

**If port mirroring is disabled**, you may need to:
1. Update `.mcp.json` to use Windows host IP instead of `localhost`:
   ```json
   "args": ["-y", "@playwright/mcp@latest", "--cdp-endpoint", "http://10.255.255.254:9222"]
   ```
   (Replace `10.255.255.254` with your actual Windows host IP)

2. Or enable port mirroring in WSL2 (Windows 11 22H2+):
   - Edit `%USERPROFILE%\.wslconfig` on Windows
   - Add: `[experimental]` and `networkingMode=mirrored`
   - Restart WSL: `wsl --shutdown` then restart your distro

### Playwright MCP Options

| Flag | Description |
|------|-------------|
| `--headless` | Run in headless mode (default is headed) |
| `--cdp-endpoint <url>` | Connect to existing browser via CDP |
| `--browser <type>` | Browser type: chrome, firefox, webkit, msedge |
| `--executable-path <path>` | Custom browser executable path |
| `--extension` | Connect via Playwright MCP Bridge extension |
| `--isolated` | Keep browser profile in memory only |

Run `npx @playwright/mcp@latest --help` for all options.

## External MCP Servers

Popular community servers you can add:

```bash
# GitHub (issues, PRs, repos)
claude mcp add github -- npx -y @modelcontextprotocol/server-github

# Fetch (HTTP requests)
claude mcp add fetch -- uvx mcp-server-fetch

# Playwright (browser automation - recommended)
claude mcp add playwright -- npx -y @playwright/mcp@latest

# Postgres
claude mcp add postgres -- npx -y @modelcontextprotocol/server-postgres
```

See [ai-docs/guides/mcp/pages/available-servers.toon](../../../../ai-docs/guides/mcp/pages/available-servers.toon) for a full catalog.

## Debugging

```bash
# Check MCP status in Claude Code
/mcp

# View server logs (stderr)
# Servers print to stderr, which appears in Claude Code's output

# Test server manually
echo '{"jsonrpc":"2.0","method":"initialize","id":1,"params":{}}' | python3 server.py
```

## Resources

- [MCP Specification](https://spec.modelcontextprotocol.io/)
- [Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [TypeScript SDK](https://github.com/modelcontextprotocol/typescript-sdk)
- [Example Servers](https://github.com/modelcontextprotocol/servers)
- [Claude Code MCP Docs](https://docs.anthropic.com/claude-code/mcp)

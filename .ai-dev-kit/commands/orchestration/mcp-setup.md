---
name: mcp-setup
description: Guide the user through setting up MCP (Model Context Protocol) servers
---

# /ai-dev-kit:mcp-setup - MCP Server Configuration Wizard

Guide the user through setting up MCP (Model Context Protocol) servers for their project.

## Instructions

When the user invokes `/ai-dev-kit:mcp-setup`, follow this interactive process:

### 1. Check Current Configuration

First, examine the current MCP setup:
- Check if `.mcp.json` exists
- Check if `.mcp.local.json` exists
- List any enabled/disabled servers
- Report current status to the user

### 2. Determine User's Needs

Ask the user what they want to configure:

```
## MCP Setup Options

What would you like to do?

1. **Enable a local example server** - Use pre-built servers from `.claude/ai-dev-kit/dev-tools/mcp/examples/`
2. **Add an external MCP server** - Install a community/official MCP server
3. **Create a custom server** - Build a new MCP server from template
4. **Configure secrets** - Set up `.mcp.local.json` for API keys
5. **View available servers** - See catalog of popular MCP servers
```

### 3. Option-Specific Workflows

#### Option 1: Enable Local Server

Show available servers in `.claude/ai-dev-kit/dev-tools/mcp/examples/`:
- **filesystem** - Safe file read/write with path restrictions
- **code-sandbox** - Execute Python/JS/Bash with sandboxing
- **database** - Query SQLite databases (read-only)
- **github** - GitHub API operations

For the chosen server:
1. Show any required environment variables
2. Update `.mcp.json` to enable the server (remove `_disabled: true`)
3. If secrets needed, guide them to set up `.mcp.local.json`

#### Option 2: Add External Server

Reference `ai-docs/guides/mcp/pages/available-servers.toon` for the catalog.

Common external servers:
- `@modelcontextprotocol/server-github` - GitHub integration
- `@modelcontextprotocol/server-postgres` - PostgreSQL queries
- `@modelcontextprotocol/server-filesystem` - Official filesystem
- `mcp-server-fetch` - HTTP requests
- `@playwright/mcp` - Browser automation (recommended)

For each:
1. Show the `claude mcp add` command
2. Or provide the JSON configuration for `.mcp.local.json`
3. List required environment variables

#### Option 3: Create Custom Server

Guide them through:
1. Choose language: Python or TypeScript
2. Copy template:
   ```bash
   cp -r .claude/ai-dev-kit/dev-tools/mcp/_templates/python .claude/ai-dev-kit/dev-tools/mcp/my-server
   # or
   cp -r .claude/ai-dev-kit/dev-tools/mcp/_templates/typescript .claude/ai-dev-kit/dev-tools/mcp/my-server
   ```
3. Explain the server structure
4. Show how to register in `.mcp.json`
5. Point to `ai-docs/guides/mcp/pages/creating-servers.toon`

#### Option 4: Configure Secrets

1. Check if `.mcp.local.json.template` exists
2. Guide them to copy it:
   ```bash
   cp .mcp.local.json.template .mcp.local.json
   ```
3. Explain the environment variable syntax: `${VAR_NAME}`
4. Verify `.mcp.local.json` is in `.gitignore`

#### Option 5: View Server Catalog

Display contents from `ai-docs/guides/mcp/pages/available-servers.toon`:
- Official servers (GitHub, Fetch, Playwright, PostgreSQL, SQLite, Filesystem, Memory)
- Community servers (Slack, Google Drive, Notion, Linear, Jira)
- Links to find more servers

### 4. Verify Setup

After any configuration change:
1. Remind user to restart Claude Code to pick up changes
2. Suggest running `/mcp` to verify server status
3. Offer to test a simple tool call if applicable

### 5. Security Reminders

Always remind users:
- Never commit `.mcp.local.json` (contains secrets)
- Use environment variables for API keys
- Review server permissions before enabling
- Point to `ai-docs/guides/mcp/pages/security.toon` for best practices

## Quick Reference

```bash
# Check MCP status
/mcp

# Add external server (CLI)
claude mcp add <name> -- <command> [args...]

# Test server manually
echo '{"jsonrpc":"2.0","method":"tools/list","id":1}' | python3 server.py
```

## Usage Examples

```
/ai-dev-kit:mcp-setup                    # Start interactive wizard
/ai-dev-kit:mcp-setup enable filesystem  # Quick enable a local server
/ai-dev-kit:mcp-setup add github         # Add GitHub integration
/ai-dev-kit:mcp-setup secrets            # Configure .mcp.local.json
```

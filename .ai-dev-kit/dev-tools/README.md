# Development Tools

This directory contains scripts, utilities, and infrastructure for ai-dev-kit development and operations.

## Directory Structure

```
dev-tools/
├── README.md              # This file
├── orchestration/         # Multi-agent orchestration infrastructure
├── scripts/               # Utility scripts (TOON fixers, MCP tools)
├── observability/         # Real-time dashboard (skeleton)
├── mcp/                   # MCP server examples and templates
├── agent-tools/           # Reusable tools for agents
├── agents/                # Legacy agent definitions
└── commands/              # Legacy command definitions
```

## Orchestration

Multi-provider task routing and execution.

### Provider Scripts

| Script | Purpose | Usage |
|--------|---------|-------|
| `providers/claude-code/spawn.sh` | Spawn Claude Code subprocess | `./spawn.sh "your task"` |
| `providers/codex/execute.sh` | Execute via OpenAI Codex | `./execute.sh "your task"` |
| `providers/codex/sandbox.sh` | Sandboxed Codex execution | `./sandbox.sh "code"` |
| `providers/gemini/query.sh` | Query Gemini CLI | `./query.sh "your task"` |
| `providers/gemini/search.sh` | Gemini web search | `./search.sh "query"` |
| `providers/cursor/agent.sh` | Cursor Agent CLI | `./agent.sh "your task"` |
| `providers/ollama/query.sh` | Local Ollama query | `./query.sh "your task"` |
| `providers/opencode/execute.sh` | OpenCode execution | `./execute.sh "your task"` |

### Monitoring

| Script | Purpose | Usage |
|--------|---------|-------|
| `monitoring/cost-status.sh` | Show usage across providers | `./cost-status.sh` |
| `monitoring/provider-check.py` | Check provider availability | `python3 provider-check.py` |
| `monitoring/log-usage.sh` | Log usage to JSONL | `./log-usage.sh` |

### Routing

| Script | Purpose | Usage |
|--------|---------|-------|
| `routing/route-task.py` | Route task to best provider | `python3 route-task.py "task"` |
| `routing/fallback-chain.py` | Execute with fallback providers | `python3 fallback-chain.py "task"` |
| `routing/priority-matrix.json` | Provider priority configuration | (configuration file) |

## Scripts

Utility scripts for TOON format and development.

### TOON Format Fixers

| Script | Purpose |
|--------|---------|
| `fix_toon_blank_lines.py` | Fix blank line issues in TOON files |
| `fix_toon_commas.py` | Fix comma usage in TOON arrays |
| `fix_toon_comments.py` | Fix comment formatting |
| `fix_toon_multiline.py` | Fix multiline string handling |
| `fix_toon_nested_lists.py` | Fix nested list formatting |
| `fix_toon_pipes.py` | Fix pipe delimiter issues |
| `fix_toon_yaml_lists.py` | Convert YAML lists to TOON format |

Usage:
```bash
python3 dev-tools/scripts/fix_toon_commas.py ai-docs/libraries/*/
```

### MCP Tools

| Script | Purpose |
|--------|---------|
| `export_mcp_tools.py` | Export MCP server tools to JSON |
| `index_mcp_tools.py` | Build minimal tool index |

Usage:
```bash
# Export Bright Data MCP tools
python3 dev-tools/scripts/export_mcp_tools.py --output .tmp/mcp-tools.json

# Build minimal index
python3 dev-tools/scripts/index_mcp_tools.py \
  --input .tmp/mcp-tools.json \
  --output .tmp/tool-index.json \
  --default-server brightdata
```

### Browser/Chrome

| Script | Purpose |
|--------|---------|
| `launch-chrome-debug.sh` | Launch Chrome with debugging port |
| `auto-launch-chrome-debug.sh` | Auto-launch for Playwright MCP |
| `verify-playwright-mcp.sh` | Verify Playwright MCP connection |

### Plugin Management

| Script | Purpose |
|--------|---------|
| `install-plugin.sh` | Install ai-dev-kit plugin |

## Observability

Real-time dashboard for agent execution monitoring.

**Status**: Skeleton implemented, full implementation planned for v1.1.

```
observability/
├── README.md
├── manage.sh           # start/stop/status
├── server/             # Bun + WebSocket server
│   └── package.json
└── client/             # Vue + Vite client
    └── package.json
```

When complete, will provide:
- Real-time WebSocket streaming
- Agent session tracking
- Tool call visualization
- Lane/phase execution status
- Run log visualization

## MCP

MCP (Model Context Protocol) server examples and templates.

```
mcp/
├── README.md
├── _templates/         # Template for new MCP servers
│   └── typescript/
└── examples/           # Example MCP servers
    ├── filesystem/
    ├── code-sandbox/
    └── database/
```

## Agent Tools

Reusable tools for AI agents.

```
agent-tools/
├── search_tools.py     # Web search tools
└── examples/
    └── api-wrapper/    # Example API wrapper tools
```

## Legacy Directories

These directories contain legacy definitions from before the plugin system:

- `agents/` - Moved to `plugins/ai-dev-kit/agents/`
- `commands/` - Moved to `plugins/ai-dev-kit/commands/`

These may still be referenced by some tools during transition.

## Environment Variables

Some scripts require environment variables:

```bash
# Provider API keys
export ANTHROPIC_API_KEY="..."
export OPENAI_API_KEY="..."
export GEMINI_API_KEY="..."
export BRIGHTDATA_API_KEY="..."

# Optional configuration
export AUTO_LAUNCH_CHROME_DEBUG=true  # Auto-launch Chrome for Playwright
```

## Integration with Commands

Many dev-tools scripts are called by plugin commands:

| Command | Scripts Used |
|---------|--------------|
| `/ai-dev-kit:cost-status` | `monitoring/cost-status.sh` |
| `/ai-dev-kit:provider-check` | `monitoring/provider-check.py` |
| `/ai-dev-kit:route` | `routing/route-task.py` |
| `/ai-dev-kit:delegate` | `providers/*/` scripts |

## Development

### Adding a New Script

1. Create script in appropriate directory
2. Add executable permissions: `chmod +x script.sh`
3. Document in this README
4. Update relevant plugin command if needed

### Testing Scripts

```bash
# Test provider availability
./dev-tools/orchestration/monitoring/cost-status.sh

# Test routing
python3 dev-tools/orchestration/routing/route-task.py "test task"

# Test TOON fixer
python3 dev-tools/scripts/fix_toon_commas.py --dry-run ai-docs/
```

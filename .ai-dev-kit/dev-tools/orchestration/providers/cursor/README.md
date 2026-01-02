# Cursor Provider

Execute agentic tasks using Cursor CLI.

## Authentication

Interactive (uses subscription):

```bash
cursor-agent login
```

Headless (requires API key):

```bash
export CURSOR_API_KEY="csk_..."  # From cursor.com/dashboard
```

## Available Models (December 2025)

| Model | Use Case | Model ID |
|-------|----------|----------|
| Composer | Cursor's own fast coding model | `composer` |

Cursor also provides access to other models (GPT-5.2, Claude Sonnet 4.5, etc.) through its interface.

## Capabilities

- Agentic file operations
- Grep-based code search
- MCP server integration
- Quick edits with full context
- Multi-agent parallel execution (up to 8 agents)

## Usage

### Agentic Task

```bash
./agent.sh "your task" [model]
# model: auto (default) | composer | gpt-5.2 | claude-sonnet-4.5
```

## Output Format

JSON object:

```json
{
  "success": true,
  "output": "Cursor response",
  "agent": "cursor",
  "model": "composer",
  "timestamp": "2025-12-10T00:00:00Z"
}
```

## Rate Limits

- Pro ($20/mo): ~$20 compute credits (~225 Sonnet-equivalent requests)
- Use strategically for IDE-specific tasks

## Example

```bash
# Simple task
./agent.sh "add error handling to this function"

# With specific model
./agent.sh "refactor this component" composer
```

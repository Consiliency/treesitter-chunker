# OpenAI Codex Provider

Execute tasks using OpenAI Codex CLI with ChatGPT Pro subscription.

## Authentication

Uses subscription auth by default:

```bash
codex login  # Browser OAuth to ChatGPT
codex login status  # Verify
```

For headless/CI: `export CODEX_API_KEY="sk-..."`

## Available Models (December 2025)

| Model | Use Case | Model ID |
|-------|----------|----------|
| GPT-5.2 | Flagship, complex tasks | `gpt-5.2` |
| GPT-5.2 Mini | Fast, cost-efficient | `gpt-5.2-mini` |
| GPT-5.2-Codex | Optimized for coding | `gpt-5.2-codex` |
| GPT-5.2-Codex-Mini | Fast coding | `gpt-5.2-codex-mini` |

## Usage

### Standard Execution

```bash
./execute.sh "your task" [sandbox_mode]
# sandbox_mode: read-only | workspace-write (default) | full-access
```

### Sandboxed Mode

```bash
./sandbox.sh "your task"
# Runs in isolated sandbox with no filesystem access
```

## Output Format

JSON object:

```json
{
  "success": true,
  "output": "Codex response",
  "agent": "codex",
  "sandbox": "workspace-write",
  "timestamp": "2025-12-10T00:00:00Z"
}
```

## Rate Limits

- Pro: 300-1,500 messages per 5-hour window
- Unlimited GPT-5.2 access with Pro subscription

## Sandbox Modes

| Mode | Description |
|------|-------------|
| `read-only` | Can read files, no writes |
| `workspace-write` | Can write to current workspace only |
| `full-access` | Full filesystem access (use with caution) |

## Example

```bash
# Standard execution
./execute.sh "write unit tests for the authentication module"

# Sandboxed execution
./sandbox.sh "analyze this code for security issues"

# With full access
./execute.sh "refactor the entire codebase" full-access
```

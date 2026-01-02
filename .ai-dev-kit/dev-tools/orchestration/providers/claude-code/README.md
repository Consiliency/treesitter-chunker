# Claude Code Provider

Execute tasks using Claude Code CLI with Max subscription.

## Authentication

Uses subscription auth by default. Ensure:

- `ANTHROPIC_API_KEY` is **NOT** set (or unset it)
- Run `claude /status` to verify subscription

For headless execution, copy `~/.claude/.credentials.json` to the target environment.

## Available Models (December 2025)

| Model | Use Case | Model ID |
|-------|----------|----------|
| Opus 4.5 | Complex reasoning, flagship | `claude-opus-4-5` |
| Sonnet 4.5 | Balanced performance | `claude-sonnet-4-5` |
| Haiku 4.5 | Fast, cost-efficient | `claude-haiku-4-5` |

## Usage

### Single Task

```bash
./spawn.sh "your task description" [model]
# model: sonnet (default) | opus | haiku
```

### Parallel Tasks (via worktrees)

```bash
./parallel.py --tasks tasks.json --max-instances 4
```

## Output Format

JSON object:

```json
{
  "success": true,
  "output": "Claude's response",
  "agent": "claude-code",
  "model": "sonnet",
  "timestamp": "2025-12-10T00:00:00Z"
}
```

## Rate Limits

- Max 20x: 200-800 prompts per 5-hour window (shared with web/mobile)
- Weekly: 240-480 hours Sonnet, 24-40 hours Opus

## Example

```bash
# Simple task
./spawn.sh "implement a function to validate email addresses"

# With specific model
./spawn.sh "refactor this complex module" opus

# Fast task
./spawn.sh "add a docstring to this function" haiku
```

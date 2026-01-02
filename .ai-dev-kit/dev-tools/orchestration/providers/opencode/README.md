# OpenCode Provider

Execute tasks using the OpenCode CLI with provider-agnostic models.

## Authentication

OpenCode uses its own config and provider credentials. Configure via `opencode auth`.

## Usage

```bash
./execute.sh "your task" [model]
```

## Defaults

- Default model: `anthropic/claude-sonnet-4-5`
- Override with `OPENCODE_MODEL` or the second argument

## Output Format

```json
{
  "success": true,
  "output": "OpenCode response",
  "agent": "opencode",
  "model": "anthropic/claude-sonnet-4-5",
  "timestamp": "2025-12-10T00:00:00Z"
}
```

## Example

```bash
./execute.sh "summarize this repo" "anthropic/claude-haiku-4-5"
```

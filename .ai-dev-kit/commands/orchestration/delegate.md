---
name: delegate
argument-hint: "[provider] [task] [file...]"
description: "Delegate a task to a specific AI provider (claude, openai, gemini, cursor, opencode, ollama)"
allowed-tools: ["Bash", "Read"]
---

# Delegate Task to Provider

Delegate a task to a specific AI provider.

## Arguments

- `provider`: Target provider (claude, openai, gemini, cursor, opencode, ollama)
- `task`: The task description to delegate
- `file...` (optional): File paths to attach (supported by Gemini; ignored by others)

## Process

1. First, check current usage status across all providers:

```bash
.claude/ai-dev-kit/dev-tools/orchestration/monitoring/cost-status.sh
```

2. Then execute the delegation to the specified provider:

```bash
# Map provider to script
case "$provider" in
    claude)
        .claude/ai-dev-kit/dev-tools/orchestration/providers/claude-code/spawn.sh "$task"
        ;;
    openai|codex)
        .claude/ai-dev-kit/dev-tools/orchestration/providers/codex/execute.sh "$task"
        ;;
    gemini)
        .claude/ai-dev-kit/dev-tools/orchestration/providers/gemini/query.sh "$task"
        ;;
    cursor)
        .claude/ai-dev-kit/dev-tools/orchestration/providers/cursor/agent.sh "$task"
        ;;
    opencode)
        .claude/ai-dev-kit/dev-tools/orchestration/providers/opencode/execute.sh "$task"
        ;;
    ollama)
        .claude/ai-dev-kit/dev-tools/orchestration/providers/ollama/query.sh "$task"
        ;;
esac
```

3. Parse and summarize the results.

## Available Providers

| Provider | Best For |
|----------|----------|
| `claude` | Complex reasoning, multi-file operations |
| `openai` | Sandboxed execution, coding tasks |
| `gemini` | Large context, multimodal, web search |
| `cursor` | Quick edits, IDE-integrated tasks |
| `opencode` | Provider-agnostic routing |
| `ollama` | Offline/private execution |

## Example Usage

```
/ai-dev-kit:delegate openai "write comprehensive tests for the auth module"
/ai-dev-kit:delegate gemini "analyze this architecture diagram" diagram.png
/ai-dev-kit:delegate cursor "add error handling to this function"
```

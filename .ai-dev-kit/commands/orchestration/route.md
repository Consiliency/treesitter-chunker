---
name: route
argument-hint: "[task description]"
description: "Intelligently route a task to the best available AI provider"
allowed-tools: ["Bash", "Read"]
---

# Intelligent Task Routing

Route a task to the best available AI provider based on task characteristics and provider availability.

## Arguments

- `task`: The task description to route

## Process

1. Analyze the task to determine its type (complex reasoning, sandboxed execution, large context, etc.)

2. Check provider availability and rate limits:

```bash
.claude/ai-dev-kit/dev-tools/orchestration/monitoring/cost-status.sh
```

3. Route to the best available provider:

```bash
.claude/ai-dev-kit/dev-tools/orchestration/routing/route-task.py "$task"
```

4. If you want to see the routing decision without executing:

```bash
.claude/ai-dev-kit/dev-tools/orchestration/routing/route-task.py "$task" --dry-run
```

## How Routing Works

The router uses a priority matrix to match task types to providers:

| Task Type | Priority 1 | Priority 2 | Priority 3 |
|-----------|------------|------------|------------|
| Complex reasoning | Claude | OpenAI | Gemini |
| Sandboxed execution | OpenAI | Cursor | Claude |
| Large context (>100k) | Gemini | Claude | OpenAI |
| Multimodal | Gemini | Claude | OpenAI |
| Quick codegen | Claude | Cursor | OpenAI |
| Extended reasoning | OpenAI | Gemini | Claude |
| Web search | Gemini | OpenAI | Claude |
| Privacy/offline | Ollama | Claude | OpenAI |

## Task Type Detection

The router detects task types using pattern matching:

- **complex_reasoning**: "analyze", "architect", "design", "debug complex"
- **sandboxed_execution**: "sandbox", "isolated", "safe execute"
- **large_context**: "entire codebase", "all files", "whole repo"
- **multimodal**: "image", "screenshot", "diagram", "video"
- **web_search**: "search web", "latest", "current news"
- **privacy_offline**: "offline", "air-gapped", "private", "sensitive"

## Fallback Behavior

If the primary provider is rate-limited or unavailable, the router automatically selects the next available provider in the priority list.

## Example Usage

```
/ai-dev-kit:route "refactor this complex authentication module"
/ai-dev-kit:route "analyze this screenshot for UI issues"
/ai-dev-kit:route "search for the latest React 19 features"
```

# Multi-Agent Orchestration

This directory contains tools for orchestrating tasks across multiple AI providers.
All tools can be executed directly via Bash - no MCP configuration required.

## Quick Start

```bash
# Check which agents are available and their current usage
./monitoring/cost-status.sh

# Check provider CLI availability (and optionally apply)
./monitoring/provider-check.py

# Route a task to the best available agent
./routing/route-task.py "your task description"

# Direct execution to specific provider
./providers/claude-code/spawn.sh "implement feature X"
./providers/codex/execute.sh "write tests for module Y"
./providers/gemini/query.sh "analyze this architecture"
./providers/cursor/agent.sh "refactor this function"
./providers/opencode/execute.sh "summarize this repo"
./providers/ollama/query.sh "summarize this repo"
```

## Provider Capabilities (December 2025)

| Provider | Best For | Models |
|----------|----------|--------|
| **Claude Code** | Complex reasoning, multi-file ops | Opus 4.5, Sonnet 4.5, Haiku 4.5 |
| **OpenAI (Codex)** | Sandboxed execution, coding | GPT-5.2, GPT-5.2 Mini, GPT-5.2-Codex |
| **Gemini** | Large context, multimodal, search | 3 Pro, 3 Deep Think, 3 Flash-Lite |
| **Cursor** | Quick edits, agentic tasks | Composer |
| **OpenCode** | Provider-agnostic routing | Provider-specific |
| **Ollama** | Offline/private execution | Local models |

## Priority Matrix

| Task Type | Priority 1 | Priority 2 | Priority 3 |
|-----------|------------|------------|------------|
| Complex reasoning | Claude (Opus 4.5) | OpenAI (GPT-5.2) | Gemini (3 Deep Think) |
| Sandboxed execution | OpenAI (GPT-5.2) | Cursor (Composer) | Claude (Opus 4.5) |
| Large context (>100k) | Gemini (3 Pro) | Claude (Opus 4.5) | OpenAI (GPT-5.2) |
| Multimodal (images/video) | Gemini (3 Pro) | Claude (Opus 4.5) | OpenAI (GPT-5.2) |
| Quick codegen | Claude (Haiku 4.5) | Cursor (Composer) | OpenAI (GPT-5.2 Mini) |
| Extended reasoning | OpenAI (GPT-5.2) | Gemini (3 Deep Think) | Claude (Opus 4.5) |
| Web search/grounding | Gemini (3 Pro) | OpenAI (GPT-5.2) | Claude (Opus 4.5) |
| Privacy/offline | Ollama (local) | Claude (Opus 4.5) | OpenAI (GPT-5.2) |

## Directory Structure

```
orchestration/
├── README.md                 # This file
├── config.json               # Provider configuration
├── providers/                # Provider-specific wrappers
│   ├── claude-code/          # Claude Code CLI wrappers
│   ├── codex/                # OpenAI Codex CLI wrappers
│   ├── gemini/               # Gemini CLI wrappers
│   ├── cursor/               # Cursor CLI wrappers
│   ├── opencode/             # OpenCode CLI wrappers
│   └── ollama/               # Ollama CLI wrappers
├── routing/                  # Task routing logic
│   ├── route-task.py         # Intelligent task router
│   ├── fallback-chain.py     # Automatic failover
│   └── priority-matrix.json  # Configurable priorities
├── monitoring/               # Usage tracking
│   ├── cost-status.sh        # Cross-provider status
│   └── log-usage.sh          # Usage logging
└── quality/                  # Multi-model QA (planned)
```

## Authentication

Each provider uses subscription auth by default. API keys are only needed for CI/CD or when subscriptions are exhausted.

| Provider | Subscription Auth | Headless Auth |
|----------|-------------------|---------------|
| Claude Code | Unset `ANTHROPIC_API_KEY` | Copy `~/.claude/.credentials.json` |
| Codex | `codex login` (browser OAuth) | `CODEX_API_KEY` |
| Gemini | `gemini` → Google OAuth | `GEMINI_API_KEY` |
| Cursor | `cursor-agent login` | `CURSOR_API_KEY` |
| OpenCode | `opencode auth` | Provider-specific |
| Ollama | Local only | N/A |

## Fallback Behavior

All agents can perform all tasks. If the primary agent is rate-limited:

1. `route-task.py` automatically selects the next available agent
2. Use `fallback-chain.py` for explicit fallback logic
3. Check `config.json` to customize fallback order

## Configuration

Edit `config.json` to:

- Enable/disable providers
- Set daily usage limits
- Configure model preferences
- Customize fallback order

## Integration with Existing Workflows

This orchestration layer integrates with:

- `/execute-lane` - Can delegate to non-Claude agents
- `/parallel` - Enhanced with cross-agent support
- Documentation pipeline - Uses appropriate agent for each task

## Usage Monitoring

```bash
# View current usage across all providers
./monitoring/cost-status.sh

# Output:
#   claude    [████████░░░░░░░░░░░░]  120/500  (24%) - Max 20x
#   openai    [██░░░░░░░░░░░░░░░░░░]   45/800  ( 6%) - Pro
#   gemini    [░░░░░░░░░░░░░░░░░░░░]    5/1000 ( 1%) - Ultra
#   cursor    [██████░░░░░░░░░░░░░░]   15/50   (30%) - Pro
#   opencode  [██░░░░░░░░░░░░░░░░░░]   12/300  ( 4%) - Flex
#   ollama    [░░░░░░░░░░░░░░░░░░░░]    0/0    ( 0%) - Local
```

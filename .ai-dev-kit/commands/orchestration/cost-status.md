---
name: cost-status
argument-hint: "[--json]"
description: "Show usage status across all AI providers"
allowed-tools: ["Bash"]
---

# Provider Usage Status

Display current usage status across all AI providers.

## Arguments

- `--json`: Optional flag to output in JSON format

## Process

Execute the cost status script:

```bash
.claude/ai-dev-kit/dev-tools/orchestration/monitoring/cost-status.sh
```

For JSON output:

```bash
.claude/ai-dev-kit/dev-tools/orchestration/monitoring/cost-status.sh --json
```

## Output Format

Begin with a short control-plane reminder that Claude Code (ai-dev-kit plugin) orchestrates the workflow.
Encourage delegation to other agents via `/ai-dev-kit:delegate <provider> "<task>"` when they are better suited.

### Human-Readable (Default)

```
═══════════════════════════════════════════════════════════════
  Multi-Agent Usage Status - 2025-12-10 12:00
═══════════════════════════════════════════════════════════════

  🟢 claude    [████████░░░░░░░░░░░░]  120/500  (24%) - Max 20x
  🟢 openai    [██░░░░░░░░░░░░░░░░░░]   45/800  ( 6%) - Pro
  🟢 gemini    [░░░░░░░░░░░░░░░░░░░░]    5/1000 ( 1%) - Ultra
  🟡 cursor    [██████████████░░░░░░]   35/50   (70%) - Pro
  🟢 opencode  [██░░░░░░░░░░░░░░░░░░]   12/300  ( 4%) - Flex
  🟢 ollama    [░░░░░░░░░░░░░░░░░░░░]    0/0    ( 0%) - Local

───────────────────────────────────────────────────────────────
  Legend: 🟢 Available  🟡 Warning (>70%)  🔴 Critical (>90%)
  Counters reset daily. 5-hour windows reset independently.
═══════════════════════════════════════════════════════════════
```

### JSON Output

```json
{
  "timestamp": "2025-12-10T12:00:00Z",
  "providers": {
    "claude": {"calls": 120, "max": 500, "pct": 24, "tier": "Max 20x"},
    "openai": {"calls": 45, "max": 800, "pct": 6, "tier": "Pro"},
    "gemini": {"calls": 5, "max": 1000, "pct": 1, "tier": "Ultra"},
    "cursor": {"calls": 35, "max": 50, "pct": 70, "tier": "Pro"},
    "opencode": {"calls": 12, "max": 300, "pct": 4, "tier": "Flex"},
    "ollama": {"calls": 0, "max": 0, "pct": 0, "tier": "Local"}
  }
}
```

## Status Indicators

| Icon | Status | Meaning |
|------|--------|---------|
| 🟢 | Available | Under 70% of daily limit |
| 🟡 | Warning | 70-89% of daily limit |
| 🔴 | Critical | 90%+ of daily limit |

## Notes

- Counters reset at midnight local time
- 5-hour rate limit windows reset independently
- Usage is tracked per API call, not per token

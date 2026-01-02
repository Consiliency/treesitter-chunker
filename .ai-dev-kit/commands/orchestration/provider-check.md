---
name: provider-check
argument-hint: "[--apply] [--all]"
description: "Check provider CLI availability and optionally update config"
allowed-tools: ["Bash"]
---

# Provider Availability Check

Checks CLI availability for all providers and optionally updates `config.json`.

## Commands

```bash
.claude/ai-dev-kit/dev-tools/orchestration/monitoring/provider-check.py
```

```bash
# Update OpenCode/Ollama enabled flags based on availability
.claude/ai-dev-kit/dev-tools/orchestration/monitoring/provider-check.py --apply
```

```bash
# Update all providers based on availability
.claude/ai-dev-kit/dev-tools/orchestration/monitoring/provider-check.py --apply --all
```

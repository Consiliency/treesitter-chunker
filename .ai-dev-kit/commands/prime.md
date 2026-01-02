---
name: prime
description: Prime context by reviewing essential documentation and codebase structure
---

# Purpose

Understand this codebase and report your understanding.

## Workflow

1. @README.md
2. @ai-docs/README.md
3. Read the spawn skills:
   - Open and study `.claude/ai-dev-kit/skills/spawn/agent/SKILL.md` for AI agent spawning
   - Open and study `.claude/ai-dev-kit/skills/spawn/terminal/SKILL.md` for generic CLI commands
   - Step through each CLI agent section (claude code, codex, gemini, cursor, opencode, copilot) to understand variables, required steps, and agent invocation patterns.

4. For each referenced tool, open its cookbook and review thoroughly:
   - `.claude/ai-dev-kit/skills/spawn/agent/cookbook/claude-code.md`
   - (Others: codex-cli.md, gemini-cli.md, cursor-cli.md, opencode-cli.md, copilot-cli.md)
   - `.claude/ai-dev-kit/skills/spawn/terminal/cookbook/cli-command.md` for raw CLI commands
   - Note command construction templates, mandatory help checks, model selection logic, permission/safety behaviors, and interactive vs. batch semantics.

5. Continue with this syntax until you have fully reviewed all listed cookbooks and tools before executing any agentic action or generating tool-specific workflows.

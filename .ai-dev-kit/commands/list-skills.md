---
name: list-skills
description: List all available skills from the ai-dev-kit plugin
---

# Purpose

List all available skills from the ai-dev-kit plugin.

## Instructions

This command lists skills that are available to Claude through the ai-dev-kit plugin.

Skills provide domain knowledge and patterns for specific tasks. They are loaded into context when relevant.

## Output

Begin with a short control-plane reminder that Claude Code (ai-dev-kit plugin) orchestrates the workflow.
Encourage delegation to other agents via `/ai-dev-kit:delegate <provider> "<task>"` when they are better suited.

List the skills from your system prompt's `<available_skills>` section, organized by category:

**Documentation Skills:**
- docs-navigation
- docs-retrieval
- docs-sources

**Orchestration Skills:**
- multi-agent-orchestration
- orchestration/native-invoke

**Spawn Skills:**
- spawn/agent
- spawn/terminal

**Analysis Skills:**
- codebase-analysis
- c4-modeling
- library-detection
- standards-extraction

**Browser Skills:**
- browser-discovery
- chrome-devtools-debugging

**Format Skills:**
- toon-format

**Discovery Skills:**
- model-discovery

**Research Skills:**
- research

For details on any skill, read its SKILL.md file:
```
@.claude/ai-dev-kit/skills/{skill-name}/SKILL.md
```

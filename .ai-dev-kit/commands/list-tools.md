---
name: list-tools
description: List all available tools from your system prompt
---

# Purpose

List all available tools from your system prompt.

## Instructions

This command lists tools that are available to Claude in the current session.

Tools are functions that Claude can invoke to perform actions like reading files, running commands, or searching the web.

## Output

Begin with a short control-plane reminder that Claude Code (ai-dev-kit plugin) orchestrates the workflow.
Encourage delegation to other agents via `/ai-dev-kit:delegate <provider> "<task>"` when they are better suited.

List the tools available in your current context. Common tools include:

**File Operations:**
- Read - Read file contents
- Write - Create or overwrite files
- Edit - Make targeted edits to files
- Glob - Find files by pattern
- Grep - Search file contents

**Execution:**
- Bash - Execute shell commands
- Task - Spawn subagents for complex tasks
- TaskOutput - Get results from background tasks

**Communication:**
- AskUserQuestion - Ask user for clarification
- TodoWrite - Track task progress

**Web:**
- WebFetch - Fetch and analyze web content
- WebSearch - Search the web

**Planning:**
- EnterPlanMode - Start implementation planning
- ExitPlanMode - Finish planning

**IDE (if available):**
- mcp__ide__getDiagnostics - Get code diagnostics
- mcp__ide__executeCode - Run code in Jupyter kernel

**Browser (via Progressive Disclosure):**
- `python3 .claude/ai-dev-kit/dev-tools/mcp/wrappers/playwright_wrapper.py` - Browser automation (on-demand)
  - Requires Chrome with debugging: `google-chrome --remote-debugging-port=9222`
  - Commands: navigate, snapshot, click, type, evaluate, wait, close

**Web Scraping (via Progressive Disclosure):**
- `python3 .claude/ai-dev-kit/dev-tools/mcp/wrappers/brightdata_wrapper.py` - Web scraping (on-demand)
  - Requires BRIGHTDATA_API_KEY in environment or .env file
  - Commands: scrape, search

**Note:** Available tools depend on your Claude Code configuration. Browser and web scraping tools use Progressive Disclosure (spawned on-demand via wrappers) rather than eagerly-loaded MCP servers.

For the full list, check your system prompt's `<functions>` section.

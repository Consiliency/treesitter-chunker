---
name: docs-management-protocol
version: "1.0"
description: "Protocol for automatic documentation context retrieval. Ensures agents never work with external libraries without loading relevant documentation first."
applies-to:
  - agents working with external libraries
  - commands that spawn sub-agents
  - any task involving libraries in ai-docs/libraries/
---

# Documentation Management Protocol

## Priority Order (Local-First, Not Local-Only)

1. **Check local ai-docs first** - Always start here for speed and curated context
2. **Use web search/fetch when:**
   - Local docs don't exist for the library
   - Local docs don't cover the specific topic needed
   - Information is time-sensitive (release dates, latest versions)
   - User explicitly requests current web information
3. **Flag gaps** - Suggest `/ai-dev-kit:docs-add` when local docs missing for frequently-needed library

This applies to ALL libraries, including AI tools like Claude Code, BAML, MCP servers, etc.

---

## Core Principle

**Never work with an external library without loading its documentation first.**

Hallucinated APIs, outdated patterns, and missing gotchas cause more rework than the time saved by skipping documentation lookup. This protocol ensures agents automatically gather relevant context before executing tasks.

---

## When This Protocol Applies

### Automatic Triggers

This protocol activates when a task involves:

1. **Explicit library references**
   - Library names from `ai-docs/libraries/_registry.json`
   - Import statements from external packages
   - Configuration of third-party tools

2. **Implicit library signals**
   - Keywords: "configure", "integrate", "set up", "migrate", "implement"
   - Error messages mentioning external packages
   - File paths in known library directories

3. **Task patterns**
   - "Set up X integration"
   - "Configure X for Y"
   - "Fix X error in Y library"
   - "Migrate from X to Y"

### Libraries Tracked

Check `ai-docs/libraries/_registry.json` for the current list. Common examples:
- BAML - Structured LLM outputs
- MCP - Model Context Protocol
- Anthropic SDK - Claude API client
- (others as added)

**AI Development Tools (this repo maintains these):**
- Claude Code - The CLI tool itself
- Claude Agent SDK - Building custom agents
- BAML - Structured LLM outputs
- MCP - Model Context Protocol
- TOON - Token-Oriented Object Notation

These are first-party tools for this repo - always check local docs first.

---

## Protocol Execution

### Step 1: Task Analysis

When receiving a task, immediately scan for:

```
[ ] Library names mentioned?
[ ] External package imports implied?
[ ] Configuration or integration work?
[ ] Error involving external dependency?
```

If ANY checkbox is true -> proceed to Step 2.
If ALL are false -> proceed directly to task execution.

### Step 2: Documentation Check

For each identified library:

```
1. Check if documented: ai-docs/libraries/{library}/_index.toon
2. If exists -> proceed to Step 3
3. If not exists -> note gap, proceed with caution, suggest /ai-dev-kit:docs-add
```

### Step 3: Context Loading

Based on task complexity, load appropriate context:

| Task Complexity | What to Load | Token Budget |
|-----------------|--------------|--------------|
| Single API call | One page summary | ~300 |
| Feature work | 2-4 relevant pages | ~1,000 |
| Integration | Library index + key pages | ~1,500 |
| Migration/refactor | full-context.md | ~5,000+ |

**Loading methods:**

**Quick (know what you need):**
```
@ai-docs/libraries/{library}/_index.toon
-> Find page in common_tasks or section index
-> @ai-docs/libraries/{library}/{section}/pages/{page}.toon
```

**Search (uncertain):**
```
@ai-docs/libraries/_index.toon
-> Match need against library descriptions
-> Navigate into matching library
```

**Deep (complex multi-library):**
```
Spawn docs-context-gatherer agent with task description
-> Receive consolidated context
```

### Step 4: Execute with Context

Now proceed with the task, documentation loaded.

---

## Sub-Agent Spawning Protocol

When spawning sub-agents for tasks involving external libraries:

### Pre-Spawn Checklist

```
[ ] Identified libraries sub-agent will need?
[ ] Gathered relevant documentation?
[ ] Prepared context injection block?
```

### Spawn Template

```markdown
Use the {agent-name} agent to {task-description}.

## Documentation Context (Pre-loaded)

### {Library 1}: {Relevant Topic}
**Purpose**: {from page summary}
**Key Points**: {concepts}
**Gotchas**: {warnings}
**Pattern**:
```{language}
{code example}
```

### {Library 2}: {Relevant Topic}
...

---

## Task

{Actual task description with full details}

## Constraints

{Any constraints}
```

### Why Pre-Load?

- Sub-agents don't inherit parent's loaded context
- Re-navigation wastes time and tokens
- Consistent context prevents divergent implementations
- Gotchas are surfaced before mistakes are made

---

## Red Flags: Stop and Load Docs

### Immediate Stops

If you're about to:

| Action | Stop Signal |
|--------|-------------|
| Write API calls | "I think the syntax is..." |
| Configure library | "Usually you configure it like..." |
| Debug library error | "This error probably means..." |
| Assume behavior | "Libraries like this typically..." |

**STOP** -> Load documentation -> Then proceed

### Warning Phrases

If you catch yourself thinking:
- "I'm pretty sure..."
- "From what I remember..."
- "It should be something like..."
- "Based on similar libraries..."

These indicate you're about to hallucinate. Load docs first.

---

## Context Budget Guidelines

### Token Allocation

| Scenario | Budget | Strategy |
|----------|--------|----------|
| Quick fix | 300-500 | Single page summary |
| Feature impl | 800-1,500 | Key pages for feature area |
| Full integration | 1,500-3,000 | Library index + core pages |
| Migration | 3,000-8,000 | Full context, multiple libs |
| Learning/exploration | 5,000+ | full-context.md |

### Efficiency Rules

1. **Start narrow, expand if needed** - Don't load full-context.md for a simple question
2. **Index files are cheap** - ~100-200 tokens to understand what's available
3. **Page summaries are designed for this** - ~300-400 tokens of high-signal content
4. **Gotchas are gold** - Always worth loading, prevent costly mistakes

---

## Documentation Gaps

### When Docs Don't Exist

If you need a library that isn't in `ai-docs/libraries/`:

1. **Note the gap** - "Documentation needed for {library}"
2. **Suggest addition** - "Consider running `/ai-dev-kit:docs-add {url} {name}`"
3. **Proceed carefully** - Use your training knowledge, but flag uncertainty
4. **Don't hallucinate confidence** - Say "I believe..." not "The API is..."

### When Docs Are Outdated

If documentation doesn't match current library behavior:

1. **Note the discrepancy** - "Docs may be outdated for {feature}"
2. **Suggest update** - "Consider running `/ai-dev-kit:docs-update {library}`"
3. **Trust current behavior** - If code works, docs may just need refresh

---

## Integration Points

### Commands That Should Follow This Protocol

- `/ai-dev-kit:plan-phase` - Load docs for libraries in the phase
- `/ai-dev-kit:execute-lane` - Pre-load docs for sub-agents
- `/ai-dev-kit:parallel` - Include docs context in worktree setup

### Agents That Should Follow This Protocol

All agents that might work with external libraries should:
1. Reference this protocol in their definition
2. Include Step 1 (Task Analysis) in their process
3. Load context before implementation work

### CLAUDE.md Integration

CLAUDE.md should contain a minimal reference pointing here. The full protocol lives in this file to:
- Survive CLAUDE.md regeneration
- Provide single source of truth
- Allow protocol updates without touching CLAUDE.md

---

## Quick Reference Card

```
+-------------------------------------------------------------+
|           DOCUMENTATION PROTOCOL QUICK REF                  |
+-------------------------------------------------------------+
|                                                             |
|  BEFORE working with external library:                      |
|  +-----------------------------------------------------+   |
|  | 1. Check: ai-docs/libraries/{lib}/_index.toon       |   |
|  | 2. Load: relevant page summaries                    |   |
|  | 3. Note: gotchas before coding                      |   |
|  +-----------------------------------------------------+   |
|                                                             |
|  WHEN spawning sub-agents:                                  |
|  +-----------------------------------------------------+   |
|  | 1. Gather docs for sub-agent's task                 |   |
|  | 2. Include in spawn prompt                          |   |
|  | 3. Sub-agent receives pre-loaded context            |   |
|  +-----------------------------------------------------+   |
|                                                             |
|  RED FLAGS (stop and load docs):                            |
|  * "I think the syntax is..."                               |
|  * "Usually you configure..."                               |
|  * "It should be something like..."                         |
|                                                             |
|  COMMANDS:                                                  |
|  * /ai-dev-kit:docs-find [query] - Search documentation                |
|  * /ai-dev-kit:docs-update [lib] - Refresh documentation               |
|  * /ai-dev-kit:docs-add [url] [name] - Add new source                  |
|                                                             |
+-------------------------------------------------------------+
```

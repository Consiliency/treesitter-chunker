---
name: docs-check
argument-hint: "[source|--all]"
description: "Check for documentation updates without making changes. Dry-run of /ai-dev-kit:docs-update."
allowed-tools: Read, Bash(curl:*), Task
---

# Check Documentation for Updates

Runs discovery phase only to report what would be updated.

## CRITICAL: Agent Invocation

Use the **Task tool** with `subagent_type` to spawn discovery agents. DO NOT manually implement discovery.

## Inputs

- `$1`: Source identifier or `--all`

## Workflow

### 1. Load Registry

```
@ai-docs/libraries/_registry.json
```

### 2. For Each Source

**Use Task tool** to spawn appropriate discovery agent:

```
subagent_type: "docs-discover-llmstxt"  # or docs-discover-github, docs-discover-web
description: "Check {source_id} docs"
prompt: |
  Discover documentation changes (discovery only, no updates).

  Input:
  - source_id: {id}
  - config: {JSON of source config}
  - existing_meta: {JSON of .meta.json}

  Return: JSON change report
```

Collect change reports without proceeding to summarization.

### 3. Report

```markdown
## Documentation Update Check

| Source | Status | Total | New | Changed | Deleted |
|--------|--------|-------|-----|---------|---------|
| baml | Has changes | 47 | 2 | 3 | 1 |
| mcp | Up to date | 28 | 0 | 0 | 0 |
| anthropic-sdk | Error | - | - | - | - |

### baml - Changes Detected

**New pages:**
- guide/new-feature (https://...)

**Changed pages:**
- reference/types (hash: abc -> def)
- reference/function (hash: 123 -> 456)
- guide/error-handling (hash: xyz -> uvw)

**Deleted pages:**
- guide/deprecated-api

### anthropic-sdk - Error

Failed to fetch: https://docs.anthropic.com/llms.txt
HTTP Status: 404

### Recommendations

Run `/ai-dev-kit:docs-update baml` to apply updates.
Check anthropic-sdk configuration in _registry.json.
```

## Usage

```bash
# Check all sources
/ai-dev-kit:docs-check --all

# Check specific source
/ai-dev-kit:docs-check baml
```

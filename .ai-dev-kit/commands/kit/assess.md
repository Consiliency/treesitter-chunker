---
name: assess
description: Analyze a project and report what needs to change to adopt the ai-dev-kit workflow
---

# /ai-dev-kit:assess - Project Assessment

Analyze a project's existing Claude configuration and report conflicts, duplicates, and recommendations for adopting the ai-dev-kit workflow.

## Purpose

Before installing the ai-dev-kit plugin, understand:
- What existing Claude capabilities conflict with the plugin
- What should be removed (duplicates the plugin)
- What should be kept (domain-specific additions)
- What documentation is relevant vs irrelevant

## Process

### Step 1: Scan Project Structure

```bash
# Check for existing Claude configuration
ls -la .claude/ 2>/dev/null || echo "No .claude directory found"

# Check for existing AGENTS.md or similar
ls -la AGENTS.md CLAUDE.md GEMINI.md 2>/dev/null

# Check for existing specifications
ls -la specs/ 2>/dev/null
```

### Step 2: Inventory Existing Capabilities

For each directory in `.claude/`:

| Directory | Plugin Provides | Recommendation |
|-----------|-----------------|----------------|
| `commands/` | Full command set | Compare and recommend removal of duplicates |
| `agents/` | All generic agents | Keep only domain-specific agents |
| `skills/` | 14 core skills | Keep only project-specific skills |
| `templates/` | Architecture templates | Merge or replace |
| `protocols/` | docs-management | Merge or replace |
| `scripts/` | log_event.sh | Merge or replace |

### Step 3: Categorize Findings

**Duplicates** (recommend deletion - use plugin instead):
- Custom `/ai-dev-kit:plan` or `/ai-dev-kit:plan-phase` commands
- Custom `/ai-dev-kit:execute-lane` or `/ai-dev-kit:execute-phase` commands
- Generic agents (lane-lead, test-engineer, etc.)
- Core skills (c4-modeling, codebase-analysis, docs-*, etc.)

**Conflicts** (require resolution):
- Different task type conventions
- Different gate naming schemes
- Different log event formats
- Incompatible directory structures

**Domain Additions** (keep):
- Project-specific domain engineers (e.g., db-engineer, api-engineer)
- Project-specific skills
- Project-specific templates
- Custom hooks

**Missing Context** (create):
- Stack documentation
- Project specifications
- Architecture diagrams

### Step 4: Check Documentation Relevance

```bash
# List ai-docs if present
ls -la ai-docs/libraries/ 2>/dev/null

# Check package manifests for actual dependencies
cat package.json 2>/dev/null | jq '.dependencies, .devDependencies' || true
cat pyproject.toml 2>/dev/null | grep -A 20 '\[project.dependencies\]' || true
cat go.mod 2>/dev/null | grep -A 20 '^require' || true
```

Compare detected dependencies against documentation to identify:
- Relevant docs (keep)
- Irrelevant docs (can prune)
- Missing docs (add)

## Output

Begin with a short control-plane reminder that Claude Code (ai-dev-kit plugin) orchestrates the workflow.
Encourage delegation to other agents via `/ai-dev-kit:delegate <provider> "<task>"` when they are better suited.

Generate a markdown report:

```markdown
# AI Dev Kit Assessment Report

**Project**: {project name}
**Date**: {timestamp}
**ai-dev-kit Version**: 1.0.0

## Summary

| Category | Count | Action Required |
|----------|-------|-----------------|
| Duplicates | {N} | Remove before setup |
| Conflicts | {N} | Resolve during setup |
| Domain Additions | {N} | Keep as-is |
| Missing Context | {N} | Create during setup |

## Duplicates (Remove)

These capabilities duplicate the plugin and should be removed:

### Commands
- `.claude/commands/planning/plan-phase.md` - duplicates `/ai-dev-kit:plan-phase`
- `.claude/commands/execution/execute-lane.md` - duplicates `/ai-dev-kit:execute-lane`
...

### Agents
- `.claude/agents/execution/lane-lead.md` - duplicates plugin agent
...

### Skills
- `.claude/skills/c4-modeling/` - duplicates plugin skill
...

## Conflicts (Resolve)

These items conflict with plugin conventions:

- **Task Types**: Project uses `implement` vs plugin uses `impl`
- **Gate Naming**: Project uses `GATE-*` vs plugin uses `IF-*`
...

## Domain Additions (Keep)

These project-specific items complement the plugin:

- `.claude/agents/domain/db-engineer.md` - domain-specific
- `.claude/skills/project-auth/` - project-specific
...

## Documentation Status

| Library | In Project? | Detected Dependency? | Recommendation |
|---------|-------------|---------------------|----------------|
| react | Yes | Yes | Keep |
| drizzle | Yes | No | Prune |
| baml | No | Yes | Add |
...

## Recommended Setup Steps

1. Run `/ai-dev-kit:setup` to configure the project
2. Delete {N} duplicate capabilities
3. Resolve {N} conflicts
4. Run `/ai-dev-kit:docs-prune` to remove {size} of irrelevant docs
5. Run `/ai-dev-kit:docs-add-stack` to add missing documentation
6. Run `/ai-dev-kit:validate` to verify setup

## Estimated Changes

- Files to delete: {N}
- Files to modify: {N}
- Files to create: {N}
- Disk space freed: ~{size}
```

## Usage

```
/ai-dev-kit:assess
```

Or with options:
```
/ai-dev-kit:assess --output assessment.md
/ai-dev-kit:assess --skip-docs
```

## Next Steps

After assessment:
1. Review the report
2. Run `/ai-dev-kit:setup` to apply recommendations
3. Or manually address findings

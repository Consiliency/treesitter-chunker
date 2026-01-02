---
name: setup
description: Configure an existing (brownfield) codebase to use the ai-dev-kit workflow
---

# /ai-dev-kit:setup - Brownfield Setup

Configure an existing repository to use the ai-dev-kit plugin workflow.

## Purpose

Transform a brownfield codebase to use the ai-dev-kit development workflow:
- Remove conflicting capabilities
- Set up project configuration
- Deploy documentation
- Configure recommended plugins

## Prerequisites

- ai-dev-kit plugin installed
- Project is a git repository
- User has reviewed `/ai-dev-kit:assess` output (recommended)

## Process

### Step 1: Run Assessment

```bash
# If not already run, perform assessment first
echo "Running project assessment..."
```

Spawn `/ai-dev-kit:assess` and capture findings.

### Step 2: Confirm Deletions

Present duplicates to user and confirm removal:

```
The following items duplicate plugin capabilities and should be removed:

Commands:
- .claude/commands/planning/plan-phase.md
- .claude/commands/execution/execute-lane.md

Agents:
- .claude/agents/execution/lane-lead.md

Skills:
- .claude/skills/c4-modeling/

Total: 15 files (~45KB)

Remove these duplicates? [Y/n]
```

If confirmed:
```bash
# Remove duplicate commands
rm -rf .claude/commands/planning/plan-phase.md
rm -rf .claude/commands/execution/execute-lane.md
# ... etc

# Remove duplicate agents
rm -rf .claude/agents/execution/lane-lead.md
# ... etc

# Remove duplicate skills
rm -rf .claude/skills/c4-modeling/
# ... etc
```

### Step 3: Resolve Conflicts

For each conflict identified in assessment:

```
Conflict: Task type naming

Project uses:     implement, test, verify
Plugin expects:   impl, test, verify

Options:
1. Update project to use plugin conventions (recommended)
2. Keep project conventions (requires manual updates)

Choose [1/2]:
```

Apply chosen resolution.

### Step 4: Configure Project Settings

Enable the ai-dev-kit plugin in `.claude/settings.json`:

```json
{
  "$schema": "https://json.schemastore.org/claude-code-settings.json",
  "permissions": {
    "allow": ["Read", "Write", "Execute"],
    "deny": []
  },
  "enabledPlugins": {
    "ai-dev-kit@ai-dev-kit": true
  }
}
```

Stack detection is automatic via the `library-detection` skill - no manual configuration needed.

For project-specific conventions, create `AGENTS.local.md` (see docs/AGENTS-LOCAL.md).

### Step 5: Set Up Directory Structure

```bash
# Create architecture directory
mkdir -p architecture/c4

# Create specs directory if not exists
mkdir -p specs/phases
mkdir -p specs/external-requests

# Create run infrastructure
mkdir -p .claude/run-logs
mkdir -p .claude/run-reports

# Create local ai-dev-kit asset cache
mkdir -p .claude/ai-dev-kit
```

### Step 5b: Sync Plugin Assets Locally

Use the ai-dev-kit CLI to sync plugin assets into `.claude/ai-dev-kit/`.

```bash
# Ensure local cache exists
mkdir -p .claude/ai-dev-kit

# Install the helper CLI if needed
if ! command -v ai-dev-kit >/dev/null 2>&1; then
  if command -v uv >/dev/null 2>&1; then
    uv tool install viper-dev-kit
  else
    echo "uv not found. Install uv or run ai-dev-kit sync manually later."
  fi
fi

# Sync assets from the plugin install or local repo
if command -v ai-dev-kit >/dev/null 2>&1; then
  ai-dev-kit sync --target .claude/ai-dev-kit
else
  echo "Fallback: set AI_DEV_KIT_SOURCE and run ai-dev-kit sync after installing uv."
fi
```

### Step 6: Documentation Setup

```
Documentation Setup

Checking ai-docs/ status...

Current state:
- ai-docs/ exists: {yes/no}
- Libraries indexed: {N}
- Detected stack: react, typescript, vitest

Options:
1. Deploy full documentation (~1MB)
2. Deploy relevant docs only (~{size})
3. Skip documentation setup

Choose [1/2/3]:
```

If option 1 or 2:
- Copy documentation from plugin
- Run `/ai-dev-kit:docs-audit`
- Optionally prune irrelevant docs
- Add missing docs for detected stack

### Step 7: Install Recommended Plugins

```
Recommended Plugins

These official Anthropic plugins complement ai-dev-kit:

Required:
- commit-commands (git workflow)
- security-guidance (security hooks)

Recommended:
- code-review (PR quality)
- pr-review-toolkit (comprehensive review)

Install all? [Y/n/select]
```

If confirmed:
```bash
# Install plugins (if Claude plugin CLI available)
claude plugin install commit-commands
claude plugin install security-guidance
claude plugin install code-review
claude plugin install pr-review-toolkit
```

### Step 7b: Configure Multi-Agent Orchestration Permissions

For multi-provider orchestration (Codex, Gemini, Cursor), add CLI permissions to `.claude/settings.json`:

```
Multi-Agent Orchestration Setup

ai-dev-kit supports invoking external AI CLIs for multi-provider reviews
and parallel agent execution. This requires pre-approving CLI commands.

Detected CLI tools:
- codex: {installed/not found}
- gemini: {installed/not found}
- cursor-agent: {installed/not found}

Add permissions for installed CLIs? [Y/n]
```

If confirmed, update `.claude/settings.json`:

```bash
# Read existing settings or create new
SETTINGS_FILE=".claude/settings.json"
mkdir -p .claude

# Add CLI permissions
```

```json
{
  "permissions": {
    "allow": [
      "Bash(codex:*)",
      "Bash(gemini:*)",
      "Bash(cursor-agent:*)"
    ]
  }
}
```

Note: These permissions enable native Task agents to invoke external AI CLIs
without interactive prompts. Users can also approve commands individually
when prompted.

### Step 8: Create AGENTS.md

If not exists, create symlinked agent files:

```bash
# Check if AGENTS.md exists
if [ ! -f AGENTS.md ]; then
  # Copy template from plugin
  cp .claude/ai-dev-kit/templates/AGENTS.md.template AGENTS.md
fi

# Create symlinks for tool compatibility
ln -sf AGENTS.md CLAUDE.md 2>/dev/null || true
ln -sf AGENTS.md GEMINI.md 2>/dev/null || true
```

### Step 9: Run Validation

Run `/ai-dev-kit:validate` to verify setup.

## Output

Begin with a short control-plane reminder that Claude Code (ai-dev-kit plugin) orchestrates the workflow.
Encourage delegation to other agents via `/ai-dev-kit:delegate <provider> "<task>"` when they are better suited.

```
AI Dev Kit Setup Complete

Project: {name}
Date: {timestamp}

Changes Made:
- Removed: {N} duplicate capabilities
- Resolved: {N} conflicts
- Configured: .claude/settings.json
- Created: architecture/ directory
- Created: specs/ directory structure

Documentation:
- Deployed: {N} library docs
- Pruned: {N} irrelevant docs
- Added: {N} docs for detected stack

Plugins Installed:
- commit-commands
- security-guidance
- code-review
- pr-review-toolkit

Next Steps:
1. Review .claude/settings.json for accuracy
2. Run /ai-dev-kit:explore-architecture to analyze codebase
3. Create your first phase plan with /ai-dev-kit:plan-phase
4. Check /ai-dev-kit:validate for any issues

Commands available:
- /ai-dev-kit:plan - Architecture-first planning
- /ai-dev-kit:plan-phase - Plan a development phase
- /ai-dev-kit:execute-lane - Execute a swim lane
- /ai-dev-kit:docs-find - Search documentation
```

## Usage

```
/ai-dev-kit:setup
```

Or with options:
```
/ai-dev-kit:setup --skip-plugins
/ai-dev-kit:setup --skip-docs
/ai-dev-kit:setup --force  # Skip confirmations
```

## Rollback

If setup needs to be undone:

```bash
# Disable the plugin
claude plugin disable ai-dev-kit

# Restore from git
git checkout -- .claude/
```

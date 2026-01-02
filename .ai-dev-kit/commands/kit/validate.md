---
name: validate
description: Verify the ai-dev-kit plugin works correctly in the current project
---

# /ai-dev-kit:validate - Installation Validation

Verify that the ai-dev-kit plugin is correctly configured and working in the current project.

## Purpose

After setup or init, validate that:
- All agents are resolvable
- All skills load correctly
- Commands are accessible
- Run logging infrastructure works
- Documentation is accessible

## Process

### Step 1: Check Plugin Installation

```bash
echo "Checking ai-dev-kit plugin installation..."

# Check if plugin is installed
if ! claude plugin list 2>/dev/null | grep -q "ai-dev-kit"; then
  echo "WARNING: ai-dev-kit plugin not found in installed plugins"
  echo "  Run: claude plugin install ai-dev-kit"
  WARNINGS+=("Plugin not installed")
fi
```

### Step 2: Validate Project Configuration

```bash
echo "Checking project configuration..."

# Check .claude/settings.json
if [ -f ".claude/settings.json" ]; then
  echo "✓ .claude/settings.json exists"

  # Validate JSON
  if python3 -c "import json; json.load(open('.claude/settings.json'))" 2>/dev/null; then
    echo "✓ settings.json is valid JSON"
  else
    echo "✗ settings.json is invalid JSON"
    ERRORS+=("Invalid settings.json")
  fi

  # Check if ai-dev-kit plugin is enabled
  if grep -q "ai-dev-kit@ai-dev-kit" .claude/settings.json; then
    echo "✓ ai-dev-kit plugin is enabled"
  else
    echo "⚠ ai-dev-kit plugin may not be enabled"
  fi
else
  echo "✗ .claude/settings.json not found"
  ERRORS+=("Missing settings.json - run /ai-dev-kit:setup or /ai-dev-kit:init")
fi
```

### Step 3: Validate Directory Structure

```bash
echo "Checking directory structure..."

REQUIRED_DIRS=(
  ".claude/run-logs"
  ".claude/run-reports"
  "architecture"
  "specs"
)

for dir in "${REQUIRED_DIRS[@]}"; do
  if [ -d "$dir" ]; then
    echo "✓ $dir exists"
  else
    echo "✗ $dir missing"
    WARNINGS+=("Missing directory: $dir")
  fi
done
```

### Step 4: Validate Agents

```bash
echo "Checking agent availability..."

CORE_AGENTS=(
  "architecture-explorer"
  "roadmap-planner"
  "lane-lead"
  "lane-executor"
  "test-engineer"
  "quality-gate-guardian"
  "docs-summarize-page"
  "docs-assemble"
)

for agent in "${CORE_AGENTS[@]}"; do
  # Check if agent file exists in plugin
  if [ -f ".claude/ai-dev-kit/agents/*/${agent}.md" ] 2>/dev/null; then
    echo "✓ Agent: $agent"
  else
    # Check via glob
    found=$(find .claude/ai-dev-kit/agents -name "${agent}.md" 2>/dev/null | head -1)
    if [ -n "$found" ]; then
      echo "✓ Agent: $agent"
    else
      echo "✗ Agent: $agent not found"
      ERRORS+=("Missing agent: $agent")
    fi
  fi
done
```

### Step 5: Validate Skills

```bash
echo "Checking skill availability..."

CORE_SKILLS=(
  "c4-modeling"
  "codebase-analysis"
  "docs-navigation"
  "docs-retrieval"
  "docs-sources"
  "library-detection"
  "multi-agent-orchestration"
  "toon-format"
)

for skill in "${CORE_SKILLS[@]}"; do
  if [ -d ".claude/ai-dev-kit/skills/${skill}" ]; then
    echo "✓ Skill: $skill"
  else
    echo "✗ Skill: $skill not found"
    ERRORS+=("Missing skill: $skill")
  fi
done
```

### Step 6: Validate Commands

```bash
echo "Checking command availability..."

CORE_COMMANDS=(
  "planning/plan"
  "planning/plan-phase"
  "planning/plan-roadmap"
  "planning/explore-architecture"
  "execution/execute-lane"
  "execution/execute-phase"
  "documentation/docs-find"
  "documentation/docs-update"
  "kit/setup"
  "kit/assess"
)

for cmd in "${CORE_COMMANDS[@]}"; do
  if [ -f ".claude/ai-dev-kit/commands/${cmd}.md" ]; then
    echo "✓ Command: $cmd"
  else
    echo "✗ Command: $cmd not found"
    ERRORS+=("Missing command: $cmd")
  fi
done
```

### Step 7: Test Run Logging

```bash
echo "Testing run logging infrastructure..."

# Create test log
TEST_RUN_ID="validate-$(date +%s)"
TEST_LOG=".claude/run-logs/test-${TEST_RUN_ID}.jsonl"

# Use log_event.sh if available
if [ -x ".claude/ai-dev-kit/scripts/log_event.sh" ]; then
  .claude/ai-dev-kit/scripts/log_event.sh \
    "$TEST_LOG" "$TEST_RUN_ID" "validate" "-" "-" \
    "test_event" "ok" "validation test" "" ""

  if [ -f "$TEST_LOG" ]; then
    echo "✓ Run logging works"
    rm "$TEST_LOG"
  else
    echo "✗ Run logging failed"
    ERRORS+=("Run logging not working")
  fi
else
  echo "⚠ log_event.sh not found - run logging not configured"
  WARNINGS+=("log_event.sh missing")
fi
```

### Step 8: Test Documentation Access

```bash
echo "Checking documentation access..."

if [ -d "ai-docs/libraries" ]; then
  LIBS=$(ls ai-docs/libraries 2>/dev/null | grep -v "^_" | wc -l)
  echo "✓ ai-docs accessible ($LIBS libraries)"

  # Check for index
  if [ -f "ai-docs/libraries/_index.toon" ]; then
    echo "✓ Library index exists"
  else
    echo "⚠ Library index missing"
    WARNINGS+=("ai-docs/_index.toon missing")
  fi
else
  echo "⚠ ai-docs/libraries not found"
  WARNINGS+=("ai-docs not configured - run /ai-dev-kit:docs-add-stack")
fi
```

### Step 9: Check Recommended Plugins

```bash
echo "Checking recommended plugins..."

RECOMMENDED_PLUGINS=(
  "commit-commands"
  "security-guidance"
)

for plugin in "${RECOMMENDED_PLUGINS[@]}"; do
  if claude plugin list 2>/dev/null | grep -q "$plugin"; then
    echo "✓ Plugin: $plugin installed"
  else
    echo "⚠ Plugin: $plugin not installed (recommended)"
    WARNINGS+=("Recommended plugin not installed: $plugin")
  fi
done
```

### Step 10: Check AGENTS.md

```bash
echo "Checking agent configuration files..."

if [ -f "AGENTS.md" ]; then
  echo "✓ AGENTS.md exists"

  # Check symlinks
  if [ -L "CLAUDE.md" ] && [ "$(readlink CLAUDE.md)" = "AGENTS.md" ]; then
    echo "✓ CLAUDE.md symlink correct"
  else
    echo "⚠ CLAUDE.md not symlinked to AGENTS.md"
    WARNINGS+=("CLAUDE.md not symlinked")
  fi
else
  echo "⚠ AGENTS.md not found"
  WARNINGS+=("AGENTS.md missing")
fi
```

## Output

Begin with a short control-plane reminder that Claude Code (ai-dev-kit plugin) orchestrates the workflow.
Encourage delegation to other agents via `/ai-dev-kit:delegate <provider> "<task>"` when they are better suited.

```markdown
# AI Dev Kit Validation Report

**Project**: {project name}
**Date**: {timestamp}
**Plugin Version**: 1.0.0

## Summary

| Check | Status |
|-------|--------|
| Plugin Installation | ✓ |
| Project Configuration | ✓ |
| Directory Structure | ✓ |
| Core Agents | ✓ (8/8) |
| Core Skills | ✓ (8/8) |
| Core Commands | ✓ (10/10) |
| Run Logging | ✓ |
| Documentation | ✓ (15 libraries) |
| Recommended Plugins | ⚠ (2/4 installed) |
| AGENTS.md | ✓ |

## Status: {PASS | WARN | FAIL}

### Errors (0)
{none}

### Warnings (2)
- Recommended plugin not installed: code-review
- Recommended plugin not installed: pr-review-toolkit

## Recommendations

1. Install missing recommended plugins:
   ```
   claude plugin install code-review
   claude plugin install pr-review-toolkit
   ```

## Workflow Ready

The ai-dev-kit workflow is ready to use. Available commands:

**Planning**:
- `/ai-dev-kit:explore-architecture` - Analyze codebase
- `/ai-dev-kit:plan-roadmap` - Create development roadmap
- `/ai-dev-kit:plan-phase` - Plan a development phase

**Execution**:
- `/ai-dev-kit:execute-lane` - Execute a swim lane
- `/ai-dev-kit:execute-phase` - Execute all lanes in a phase

**Documentation**:
- `/ai-dev-kit:docs-find` - Search documentation
- `/ai-dev-kit:docs-update` - Update documentation

**Orchestration**:
- `/ai-dev-kit:delegate` - Delegate to specific agent
- `/ai-dev-kit:route` - Intelligent task routing
```

## Exit Codes

- 0: All checks passed (PASS)
- 1: Warnings but functional (WARN)
- 2: Critical errors (FAIL)

## Usage

```
/ai-dev-kit:validate
```

Or with options:
```
/ai-dev-kit:validate --verbose     # Show all checks
/ai-dev-kit:validate --json        # Output as JSON
/ai-dev-kit:validate --fix         # Attempt to fix issues
```

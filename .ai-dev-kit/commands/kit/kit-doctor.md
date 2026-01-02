---
name: kit-doctor
description: Validate AI Dev Kit installation for missing files, symlinks, or directories
---

# /ai-dev-kit:kit-doctor - Validate Kit Installation

Check an AI Dev Kit installation for missing files, symlinks, or directories.

## Instructions

When the user invokes `/kit-doctor`:

### 1. Check Required Files

Verify these exist in the current project:
- `AGENTS.md` or `CLAUDE.md` (agent instructions file)
- `.claude/settings.json` (plugin configuration)

### 2. Check Plugin + CLI Installation

```bash
# Check plugin cache location
ls -la ~/.claude/plugins/cache/ai-dev-kit/ai-dev-kit/*/

# Check helper CLI
command -v ai-dev-kit >/dev/null && ai-dev-kit version || echo "ai-dev-kit CLI missing"
```

### 3. Check Configuration

```bash
# Check for Claude settings
cat .claude/settings.json 2>/dev/null || echo "No .claude/settings.json found"
cat .claude/settings.local.json 2>/dev/null || echo "No .claude/settings.local.json found"
```

### 4. Validate Plugin Structure + Local Cache

Check the plugin has required components:
```bash
PLUGIN_DIR=$(find ~/.claude/plugins/cache/ai-dev-kit -type d -name "ai-dev-kit" 2>/dev/null | head -1)
if [ -n "$PLUGIN_DIR" ]; then
  echo "Plugin found at: $PLUGIN_DIR"
  ls "$PLUGIN_DIR/.claude-plugin/plugin.json" 2>/dev/null && echo "✓ Plugin manifest exists"
  ls "$PLUGIN_DIR/commands/" 2>/dev/null | wc -l | xargs -I{} echo "✓ {} command directories"
  ls "$PLUGIN_DIR/skills/" 2>/dev/null | wc -l | xargs -I{} echo "✓ {} skills"
  ls "$PLUGIN_DIR/agents/" 2>/dev/null | wc -l | xargs -I{} echo "✓ {} agent directories"
else
  echo "✗ Plugin not found in cache"
fi

# Check local asset cache
if [ -f ".claude/ai-dev-kit/manifest.json" ]; then
  echo "✓ Local assets synced"
else
  echo "⚠ Local asset cache missing - run ai-dev-kit sync"
fi
```

### 5. Output Summary

```markdown
## Kit Doctor Report

### Plugin Status
- [status from checks above]

### Project Configuration
- AGENTS.md: [found/missing]
- .claude/settings.json: [found/missing]
- Plugin enabled: [yes/no]

### Recommendations
- [any issues to fix]

### Status
- OK / Issues found
```

## Usage

```
/kit-doctor
```

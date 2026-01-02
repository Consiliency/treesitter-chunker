---
name: kit-update
description: Update the AI Dev Kit Claude Code plugin bundle from source
---

# /ai-dev-kit:kit-update - Update Plugin Bundle

Update the AI Dev Kit local asset cache using the ai-dev-kit CLI.

## Instructions

When the user invokes `/ai-dev-kit:kit-update`:

### 1. Ensure CLI Is Installed

```bash
if ! command -v ai-dev-kit >/dev/null 2>&1; then
  uv tool install viper-dev-kit
fi
```

### 2. Upgrade CLI

```bash
uv tool install --upgrade ai-dev-kit
```

### 3. Sync Local Assets

```bash
ai-dev-kit sync --target .claude/ai-dev-kit
```

### 4. Optional: Update the Plugin

If plugin files are out of date, reinstall via Claude Code:
```bash
claude plugin install ai-dev-kit@ai-dev-kit
```

### 5. Output Summary

```markdown
## Kit Update Summary

### Local Assets
- Synced from: [source path]
- CLI version: [version]

### Next Steps
1. Restart Claude Code to reload plugins
2. Run `/kit-doctor` to validate installation
```

## Usage

```
/ai-dev-kit:kit-update
```

## Notes

- The plugin is cached at `~/.claude/plugins/cache/ai-dev-kit/ai-dev-kit/<version>/`
- Updates require either:
  - Access to the ai-dev-kit source repository
  - Manual copy of new plugin files
- After updating, restart Claude Code to reload the plugin

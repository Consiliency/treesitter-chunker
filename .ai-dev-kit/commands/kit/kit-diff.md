---
name: kit-diff
description: "[DEPRECATED] Show template divergence from the legacy .ai-kit subtree system"
---

# /ai-dev-kit:kit-diff - Show Template Divergence

> **DEPRECATED**: This command uses the legacy `.ai-kit/` subtree system which is deprecated as of v1.0.0.
> The ai-dev-kit is now distributed as a Claude Code plugin. To see plugin version differences, compare your
> installed plugin version with the latest release on the ai-dev-kit repository.

Show differences between local template and remote template repository.

## Instructions

When the user invokes `/kit-diff`:

### 1. Fetch Latest Remote State
```bash
# For subtree
git fetch origin-template

# For standalone clone
cd .ai-kit/base && git fetch origin && cd ../..
```

### 2. Show Divergence
```bash
# For subtree - compare local subtree to remote
git diff origin-template/main -- .ai-kit/base/

# For standalone clone
cd .ai-kit/base
git log --oneline HEAD..origin/main  # Remote has, we don't
git log --oneline origin/main..HEAD  # We have, remote doesn't
git diff origin/main
cd ../..
```

### 3. Output Summary
```markdown
## Kit Divergence Report

### Local Changes (not pushed)
Changes in `.ai-kit/base/` that aren't in the template repo:

| File | Status | Description |
|------|--------|-------------|
| `ai-docs/frameworks/vue.md` | Added | New Vue.js documentation |
| `CLAUDE.md` | Modified | Added new workflow section |

### Remote Changes (not pulled)
Changes in template repo that aren't in this project:

| File | Status | Description |
|------|--------|-------------|
| `.claude/commands/test.md` | Added | New test command |
| `ai-docs/patterns/auth.md` | Modified | Updated auth patterns |

### Recommendations

**To sync local → remote**: `/kit-push`
**To sync remote → local**: `/kit-pull`

### Potential Conflicts
These files have changes in both directions:
- `CLAUDE.md` - Review both versions before syncing
```

## Usage

```
/kit-diff
```

## Notes

- This only shows differences in `.ai-kit/base/`
- Local overrides in `.ai-kit/local/` are not compared
- Use this before `/kit-pull` or `/kit-push` to understand impact

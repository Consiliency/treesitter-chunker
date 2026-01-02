---
name: kit-pull
description: "[DEPRECATED] Pull template updates from the legacy .ai-kit subtree system"
---

# /ai-dev-kit:kit-pull - Pull Template Updates

> **DEPRECATED**: This command uses the legacy `.ai-kit/` subtree system which is deprecated as of v1.0.0.
> The ai-dev-kit is now distributed as a Claude Code plugin. For updates, use Claude Code's plugin update mechanism.

Pull the latest changes from the ai-dev-kit template repository into the current project.

## Instructions

When the user invokes `/kit-pull`:

### 1. Check Current State
```bash
# Check if we're using subtree or standalone clone
if [ -f ".ai-kit/base/.git" ]; then
  echo "Using standalone clone"
else
  echo "Using git subtree"
fi
```

### 2. For Git Subtree (Recommended)
```bash
# Pull latest from template repo
git subtree pull --prefix=.ai-kit/base origin-template main --squash
```

### 3. For Standalone Clone
```bash
cd .ai-kit/base
git fetch origin
git pull origin main
cd ../..
```

### 4. Review Changes
- Show what files were updated
- Highlight any potential conflicts with local overrides
- Suggest reviewing `.ai-kit/local/` for needed updates

### 5. Output Summary
```markdown
## Kit Pull Summary

**Template Version**: X.Y.Z → A.B.C

### Updated Files
- `CLAUDE.md` - Updated core instructions
- `.claude/commands/plan.md` - New planning format

### Review Recommended
The following local files may need updates to match:
- `.ai-kit/local/CLAUDE.md` - Check for new base features

### Next Steps
1. Review changes in `.ai-kit/base/`
2. Update `.ai-kit/local/` if needed
3. Test that everything still works
```

## Usage

```
/kit-pull
```

## Notes

- Always commit local changes before pulling
- Review changes before using them
- Local overrides in `.ai-kit/local/` are never affected

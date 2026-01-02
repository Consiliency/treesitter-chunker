---
name: kit-push
description: "[DEPRECATED] Push template improvements to the legacy .ai-kit subtree system"
---

# /ai-dev-kit:kit-push - Push Template Improvements

> **DEPRECATED**: This command uses the legacy `.ai-kit/` subtree system which is deprecated as of v1.0.0.
> The ai-dev-kit is now distributed as a Claude Code plugin. For contributing improvements, submit PRs directly
> to the ai-dev-kit repository.

Push improvements made in `.ai-kit/base/` back to the template repository.

## Instructions

When the user invokes `/kit-push`:

### 1. Identify Changes
```bash
# Show what's changed in base/
cd .ai-kit/base
git status
git diff
```

### 2. Review Before Pushing
Confirm with the user:
- What changes are being pushed
- That these are universal improvements (not project-specific)
- That project-specific content isn't accidentally included

### 3. For Git Subtree
```bash
# Push changes back to template repo
git subtree push --prefix=.ai-kit/base origin-template main
```

### 4. For Standalone Clone
```bash
cd .ai-kit/base
git add -A
git commit -m "Template update: [description]"
git push origin main
cd ../..
```

### 5. Output Summary
```markdown
## Kit Push Summary

### Changes Pushed
- `ai-docs/frameworks/nextjs.md` - Added App Router patterns
- `.claude/commands/new-command.md` - New slash command

### Commit Message
Template update: Add Next.js App Router docs and new command

### Next Steps
1. Other projects can now `/kit-pull` to get these updates
2. Consider updating the template version if significant
```

## Usage

```
/kit-push
/kit-push "Add new React patterns documentation"
```

## Pre-Push Checklist

Before pushing, verify:
- [ ] Changes are generic/reusable (not project-specific)
- [ ] No secrets or project-specific paths included
- [ ] Documentation is clear and helpful
- [ ] Changes work correctly in current project

## Notes

- Only changes in `.ai-kit/base/` are pushed
- Changes in `.ai-kit/local/` are never pushed
- Consider the impact on other projects using this template

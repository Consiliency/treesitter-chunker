# Worktree Setup Checklist

This checklist ensures you don't create worktrees before committing files (avoiding missing ROADMAP.md and other critical files).

## Before Creating Worktrees

- [ ] Run `git status` - must show "nothing to commit, working tree clean"
- [ ] All implementation files committed:
  - [ ] `chunker/parser.py` (updated)
  - [ ] `chunker/registry.py` (new)
  - [ ] `chunker/factory.py` (new)
  - [ ] `chunker/exceptions.py` (new)
- [ ] Documentation committed:
  - [ ] `specs/ROADMAP.md`
  - [ ] `PARALLEL_DEVELOPMENT_COMMANDS.md`
  - [ ] `CLAUDE.md`
- [ ] Configuration committed:
  - [ ] `.claude/settings.json`
- [ ] Scripts committed:
  - [ ] `scripts/setup-worktree-env.sh`
  - [ ] `scripts/launch-claude-sessions.sh`
- [ ] Tests committed:
  - [ ] `tests/test_registry.py`
  - [ ] `tests/test_factory.py`
  - [ ] `tests/test_exceptions.py`
  - [ ] `tests/test_integration.py`
- [ ] Pushed to origin/main: `git push origin main`
- [ ] Verified with: `git ls-tree -r HEAD | grep -E "(ROADMAP.md|registry.py|factory.py)"`

## Creating Worktrees

- [ ] All files verified in git
- [ ] Run worktree creation commands from PARALLEL_DEVELOPMENT_COMMANDS.md
- [ ] Test one worktree: `cd ../treesitter-chunker-worktrees/docs && ls specs/ROADMAP.md`
- [ ] If file not found, STOP and use fix instructions

## After Creating Worktrees

- [ ] All worktrees have latest files
- [ ] Environment setup completed for each worktree (run setup-worktree-env.sh)
- [ ] Ready to copy commands from PARALLEL_DEVELOPMENT_COMMANDS.md

## Common Issues

### Issue: "File does not exist" in Claude sessions
**Cause**: Worktrees created before files were committed
**Fix**: See "Fixing Existing Worktrees" in PARALLEL_DEVELOPMENT_COMMANDS.md

### Issue: Worktrees missing recent changes
**Cause**: Changes not pushed to origin/main
**Fix**: Commit and push in main, then reset worktrees

## Remember

**The #1 rule**: ALWAYS commit everything before creating worktrees!

This prevents:
- Missing files in worktrees
- Failed Claude sessions
- Wasted time and context
- Having to reset multiple branches
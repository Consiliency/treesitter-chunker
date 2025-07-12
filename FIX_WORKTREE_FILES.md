# Fix for Worktree Missing Files

The worktrees were created from an earlier commit (526d87a) before the ROADMAP.md and other files were added. Here's how to fix it:

## For Each Worktree (run these commands in the worktree directory):

```bash
# 1. Fetch latest changes
git fetch origin

# 2. Merge or rebase with main to get all the latest files
git merge origin/main
# OR if you prefer rebase:
git rebase origin/main

# 3. Verify the files are now present
ls specs/ROADMAP.md
```

## Specific Fix for CLI Enhancement Worktree:

```bash
cd ../treesitter-chunker-worktrees/cli-enhance
git fetch origin
git merge origin/main
ls specs/ROADMAP.md
```

## Alternative: Cherry-pick specific commits

If you want to be more selective, you can cherry-pick the commits that added the files:

```bash
# Get the commit that added ROADMAP.md and other files
git log --oneline origin/main -- specs/ROADMAP.md

# Cherry-pick that commit
git cherry-pick <commit-hash>
```

## Why this happened:

The worktrees were created from commit 526d87a which was before you added:
- specs/ROADMAP.md
- Updated parser implementation
- .claude/settings.json
- Other recent changes

After fixing this, the Claude session in that worktree will be able to read the ROADMAP.md and implement the features correctly.
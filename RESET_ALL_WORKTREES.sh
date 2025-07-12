#!/bin/bash
# Reset all worktrees to start fresh with ROADMAP.md

echo "=== RESETTING ALL WORKTREES ==="
echo ""
echo "This will DELETE all work done in worktrees (which was done without ROADMAP.md)"
echo "and reset them to main branch with all proper files."
echo ""
read -p "Are you sure you want to DELETE all worktree changes? (y/N) " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cancelled."
    exit 1
fi

# First, ensure main is up to date
echo ""
echo "Step 1: Ensuring main branch has all files committed..."
cd ~/code/treesitter-chunker

if [[ -n $(git status --porcelain) ]]; then
    echo "You have uncommitted changes in main. Please run ./COMMIT_EVERYTHING_NOW.sh first!"
    exit 1
fi

# List of all worktrees
WORKTREES="lang-config plugin-arch cli-enhance export-json performance docs export-parquet export-graph export-db lang-python lang-rust lang-javascript lang-c lang-cpp"

echo ""
echo "Step 2: Resetting all worktrees to main..."
echo ""

for worktree in $WORKTREES; do
    if [ -d "../treesitter-chunker-worktrees/$worktree" ]; then
        echo "----------------------------------------"
        echo "Resetting $worktree..."
        cd ../treesitter-chunker-worktrees/$worktree
        
        # Show what will be lost
        if [[ -n $(git status --porcelain) ]]; then
            echo "  WARNING: The following changes will be DELETED:"
            git status --short | head -5
            if [ $(git status --short | wc -l) -gt 5 ]; then
                echo "  ... and $(($(git status --short | wc -l) - 5)) more files"
            fi
        fi
        
        # Reset to main
        git fetch origin
        git reset --hard origin/main
        git clean -fd
        
        # Verify ROADMAP exists
        if [ -f "specs/ROADMAP.md" ]; then
            echo "  ✓ ROADMAP.md present"
        else
            echo "  ✗ ERROR: ROADMAP.md still missing!"
        fi
    else
        echo "Skipping $worktree (not found)"
    fi
done

cd ~/code/treesitter-chunker

echo ""
echo "=== RESET COMPLETE ==="
echo ""
echo "All worktrees have been reset to main with proper files."
echo "You can now start fresh Claude sessions with the correct ROADMAP.md!"
echo ""
echo "Next steps:"
echo "1. Set up environment in each worktree: ../treesitter-chunker/scripts/setup-worktree-env.sh"
echo "2. Launch Claude sessions using commands from PARALLEL_DEVELOPMENT_COMMANDS.md"
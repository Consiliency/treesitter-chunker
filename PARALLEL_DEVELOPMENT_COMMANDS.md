# Parallel Development Commands for Tree-sitter Chunker

Copy and paste these commands into separate terminal windows/tabs to start parallel development.

## CRITICAL: Pre-Flight Checklist (DO THIS FIRST!)

Before creating ANY worktrees or starting parallel development:

1. **Verify all files are committed:**
   ```bash
   git status
   # Should show: "nothing to commit, working tree clean"
   ```

2. **If you have uncommitted changes, commit them NOW:**
   ```bash
   git add .
   git commit -m "Add ROADMAP, parser refactoring, and all implementation files"
   git push origin main
   ```

3. **Verify critical files exist in git:**
   ```bash
   git ls-tree -r HEAD | grep -E "(ROADMAP.md|parser.py|registry.py|factory.py)"
   # Should show all files
   ```

4. **Only proceed if step 3 shows all files!**

## Fixing Existing Worktrees (REQUIRED - All Were Created Without ROADMAP)

Since ALL worktrees were created before ROADMAP.md existed, they contain work done without proper direction. We MUST reset them completely.

### Step 1: Commit Everything in Main First
```bash
# CRITICAL: Run this first!
cd ~/code/treesitter-chunker
./COMMIT_EVERYTHING_NOW.sh

# Or manually:
git add .
git commit -m "Add ROADMAP, parser refactoring, and parallelization setup"
git push origin main
```

### Step 2: Hard Reset ALL Worktrees (Discards All Previous Work)
```bash
# This will DELETE all work done without ROADMAP.md and start fresh
for worktree in lang-config plugin-arch cli-enhance export-json performance docs export-parquet export-graph export-db lang-python lang-rust lang-javascript lang-c lang-cpp; do
    echo "RESETTING $worktree to main (discarding all local work)..."
    cd ../treesitter-chunker-worktrees/$worktree
    git fetch origin
    git reset --hard origin/main  # This DELETES all local changes
    git clean -fd  # Remove any untracked files
    echo "$worktree is now clean and has ROADMAP.md"
done

cd ~/code/treesitter-chunker
echo "All worktrees reset. Ready to start fresh with proper direction!"
```

### Alternative: Delete and Recreate All Worktrees
```bash
# Nuclear option - completely remove and recreate
cd ~/code/treesitter-chunker

# Remove ALL worktrees
git worktree list | grep -v "\[main\]" | awk '{print $1}' | xargs -I {} git worktree remove {} --force

# Verify they're gone
git worktree list  # Should only show main

# Now recreate them fresh (continue with "Creating New Worktrees" section)
```

⚠️ **WARNING**: Both options above will DELETE all work done in the worktrees. This is necessary because that work was done without the ROADMAP.md guidance.

## Creating New Worktrees

⚠️ **WARNING**: Only run these commands AFTER completing the Pre-Flight Checklist above!

```bash
# Create parent directory structure
cd ..
mkdir -p treesitter-chunker-worktrees
cd treesitter-chunker

# Create worktrees for immediate work (no dependencies)
git worktree add ../treesitter-chunker-worktrees/lang-config -b feature/lang-config
git worktree add ../treesitter-chunker-worktrees/plugin-arch -b feature/plugin-arch
git worktree add ../treesitter-chunker-worktrees/cli-enhance -b feature/cli-enhance
git worktree add ../treesitter-chunker-worktrees/export-json -b feature/export-json
git worktree add ../treesitter-chunker-worktrees/performance -b feature/performance
git worktree add ../treesitter-chunker-worktrees/docs -b feature/docs

# Create worktrees for language modules (wait for lang-config to merge)
git worktree add ../treesitter-chunker-worktrees/lang-python -b feature/lang-python
git worktree add ../treesitter-chunker-worktrees/lang-rust -b feature/lang-rust
git worktree add ../treesitter-chunker-worktrees/lang-javascript -b feature/lang-javascript
git worktree add ../treesitter-chunker-worktrees/lang-c -b feature/lang-c
git worktree add ../treesitter-chunker-worktrees/lang-cpp -b feature/lang-cpp

# Additional export format worktrees
git worktree add ../treesitter-chunker-worktrees/export-parquet -b feature/export-parquet
git worktree add ../treesitter-chunker-worktrees/export-graph -b feature/export-graph
git worktree add ../treesitter-chunker-worktrees/export-db -b feature/export-db
```

## 1. CRITICAL PATH - Start This First (Terminal 1)

```bash
# Language Configuration Framework (blocks 5 other features)
cd ../treesitter-chunker-worktrees/lang-config
git fetch origin
git reset --hard origin/main  # Start fresh with latest files
../../treesitter-chunker/scripts/setup-worktree-env.sh
source .venv/bin/activate
claude "Implement Phase 2.1 Language Configuration Framework from specs/ROADMAP.md. Create LanguageConfig base class, configuration attributes for chunk_types, ignore_types, support inheritance for language families, and add validation. This is critical path that blocks 5 language modules."
```

## 2. IMMEDIATE PARALLEL STARTS (Terminals 2-7)

### Terminal 2: Plugin Architecture
```bash
cd ../treesitter-chunker-worktrees/plugin-arch
git fetch origin
git reset --hard origin/main  # Start fresh with latest files
../../treesitter-chunker/scripts/setup-worktree-env.sh
source .venv/bin/activate
claude "Implement Phase 1.2 Plugin Architecture from specs/ROADMAP.md. Create abstract base classes for language plugins, plugin discovery mechanism, dynamic loading from directories, and configuration management with TOML/YAML support."
```

### Terminal 3: CLI Enhancements
```bash
cd ../treesitter-chunker-worktrees/cli-enhance
git fetch origin
git reset --hard origin/main  # Start fresh with latest files
../../treesitter-chunker/scripts/setup-worktree-env.sh
source .venv/bin/activate
claude "Implement Phase 5.1 Advanced CLI Features and 5.3 User Experience from specs/ROADMAP.md. Add batch processing, directory input, glob patterns, file filtering, progress bars, and .chunkerrc configuration support."
```

### Terminal 4: JSON Export
```bash
cd ../treesitter-chunker-worktrees/export-json
git fetch origin
git reset --hard origin/main  # Start fresh with latest files
../../treesitter-chunker/scripts/setup-worktree-env.sh
source .venv/bin/activate
claude "Implement JSON/JSONL export format from Phase 5.2 in specs/ROADMAP.md. Add streaming JSONL output, custom JSON schemas, include relationship data, and compression support. Integrate with existing CLI."
```

### Terminal 5: Performance Optimization
```bash
cd ../treesitter-chunker-worktrees/performance
git fetch origin
git reset --hard origin/main  # Start fresh with latest files
../../treesitter-chunker/scripts/setup-worktree-env.sh
source .venv/bin/activate
claude "Implement Phase 4.1 Efficient Processing and 4.2 Caching from specs/ROADMAP.md. Add streaming file processing, multiprocessing support, AST caching with file hashing, and performance benchmarks."
```

### Terminal 6: Documentation
```bash
cd ../treesitter-chunker-worktrees/docs
git fetch origin
git reset --hard origin/main  # Start fresh with latest files
../../treesitter-chunker/scripts/setup-worktree-env.sh
source .venv/bin/activate
claude "Create comprehensive documentation per Phase 6.2 in specs/ROADMAP.md. Generate API docs from docstrings, create user guide, getting started tutorial, cookbook with examples, and architecture diagrams."
```

### Terminal 7: Parquet Export (Optional)
```bash
cd ../treesitter-chunker-worktrees/export-parquet
git fetch origin
git reset --hard origin/main  # Start fresh with latest files
../../treesitter-chunker/scripts/setup-worktree-env.sh
source .venv/bin/activate
claude "Implement Parquet export format from Phase 5.2 in specs/ROADMAP.md. Use Apache Parquet writer, support nested schema for metadata, add partitioning options, and column selection. Integrate with CLI."
```

## 3. AFTER LANG-CONFIG MERGES (Save for Later)

Once the Language Configuration Framework is merged, you can start these in parallel:

### Python Language Module
```bash
cd ../treesitter-chunker-worktrees/lang-python
git fetch origin
git rebase origin/main  # This will include the merged lang-config changes
../../treesitter-chunker/scripts/setup-worktree-env.sh
source .venv/bin/activate
claude "Implement Python Language Module from Phase 2.2 in specs/ROADMAP.md. Define chunk node types for functions, classes, async functions, comprehensions, imports, and docstrings using the new Language Configuration Framework from Phase 2.1."
```

### Rust Language Module
```bash
cd ../treesitter-chunker-worktrees/lang-rust
git fetch origin
git rebase origin/main  # This will include the merged lang-config changes
../../treesitter-chunker/scripts/setup-worktree-env.sh
source .venv/bin/activate
claude "Implement Rust Language Module from Phase 2.2 in specs/ROADMAP.md. Define chunk node types for functions, impl blocks, traits, structs, enums, modules, and macros using the new Language Configuration Framework."
```

### JavaScript Language Module
```bash
cd ../treesitter-chunker-worktrees/lang-javascript
git fetch origin
git rebase origin/main  # This will include the merged lang-config changes
../../treesitter-chunker/scripts/setup-worktree-env.sh
source .venv/bin/activate
claude "Implement JavaScript/TypeScript Module from Phase 2.2 in specs/ROADMAP.md. Define chunk node types for functions, classes, methods, arrow functions, React components, and TypeScript constructs using the Language Configuration Framework."
```

### C Language Module
```bash
cd ../treesitter-chunker-worktrees/lang-c
git fetch origin
git rebase origin/main  # This will include the merged lang-config changes
../../treesitter-chunker/scripts/setup-worktree-env.sh
source .venv/bin/activate
claude "Implement C Language Module from Phase 2.2 in specs/ROADMAP.md. Define chunk node types for functions, structs, unions, typedefs, and preprocessor directives using the Language Configuration Framework."
```

### C++ Language Module
```bash
cd ../treesitter-chunker-worktrees/lang-cpp
git fetch origin
git rebase origin/main  # This will include the merged lang-config changes
../../treesitter-chunker/scripts/setup-worktree-env.sh
source .venv/bin/activate
claude "Implement C++ Language Module from Phase 2.2 in specs/ROADMAP.md. Inherit from C module, add classes, namespaces, templates, methods, constructors/destructors using the Language Configuration Framework."
```

## Quick Reference Commands

### Check worktree status
```bash
git worktree list
```

### Update ROADMAP.md in your branch
```bash
# In your worktree, update only your section and Branch Status Tracking
git add specs/ROADMAP.md
git commit -m "Update ROADMAP.md: Mark [phase] tasks as completed"
```

### Before merging any branch
```bash
git fetch origin
git rebase origin/main
python -m pytest
git push -f origin feature/[branch-name]
```

### After merging, clean up worktree
```bash
cd ~/code/treesitter-chunker
git worktree remove ../treesitter-chunker-worktrees/[completed-feature]
```

## Important Notes

1. **Permissions are automatic**: The `.claude/settings.json` file means each Claude instance will have the necessary permissions
2. **Start Terminal 1 first**: Language Config is the critical path that blocks 5 other features
3. **Terminals 2-7 can run simultaneously**: These are all independent features
4. **Each Claude session** will have its own context and can work autonomously
5. **Update ROADMAP.md** following the merge conflict prevention rules in each branch
6. **Environment setup** is required once per worktree (the script handles everything)

## Workflow Tips

- Use terminal tabs or tmux/screen for managing multiple sessions
- Name your terminal tabs after the feature for easy identification
- Keep the main repo terminal open for merging completed features
- Monitor progress across branches with `git worktree list`
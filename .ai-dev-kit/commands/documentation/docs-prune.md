---
name: docs-prune
description: Remove documentation for libraries not used in the project
---

# /ai-dev-kit:docs-prune - Prune Irrelevant Documentation

Remove documentation directories for libraries that are not dependencies of the current project.

## Purpose

After `/ai-dev-kit:docs-audit`:
- Remove irrelevant documentation to reduce repository size
- Keep documentation lean and focused on actual stack
- Maintain audit trail of what was pruned

## Safety Features

- **Never auto-deletes** - always requires confirmation
- **Preserves registry** - only removes content, keeps registry entries
- **Creates backup** - option to backup before pruning
- **Audit log** - tracks what was pruned and when
- **Easy recovery** - can re-add via `/ai-dev-kit:docs-add`

## Process

### Step 1: Run Audit

If not recently run:
```
Running /ai-dev-kit:docs-audit to identify prunable docs...
```

### Step 2: Present Pruning Plan

```
Documentation Pruning Plan

The following documentation is NOT used by this project:

Library           Size      Pages   Last Accessed
────────────────────────────────────────────────
angular           580 KB    28      Never
vue               490 KB    25      Never
django            420 KB    22      Never
flask             380 KB    19      Never
fastapi           350 KB    18      Never
sqlalchemy        310 KB    16      Never
prisma            290 KB    14      Never
express           280 KB    15      Never
gatsby            240 KB    12      Never
svelte            220 KB    11      Never
nest              200 KB    10      Never
graphql           180 KB    9       Never
────────────────────────────────────────────────
Total             3.94 MB   199 pages

This will free ~4 MB of disk space.

Proceed with pruning? [Y/n/select]
```

### Step 3: Handle Selection Mode

If user chooses `select`:

```
Select libraries to prune (space to toggle, enter to confirm):

[x] angular           580 KB
[x] vue               490 KB
[x] django            420 KB
[x] flask             380 KB
[ ] fastapi           350 KB    <- user deselected
[x] sqlalchemy        310 KB
[x] prisma            290 KB
[x] express           280 KB
[x] gatsby            240 KB
[x] svelte            220 KB
[x] nest              200 KB
[x] graphql           180 KB

Selected: 11 libraries (3.59 MB)
```

### Step 4: Optional Backup

```
Create backup before pruning? [y/N]
```

If yes:
```bash
# Create backup archive
backup_dir=".claude/backups"
backup_file="docs-backup-$(date +%Y%m%d-%H%M%S).tar.gz"
mkdir -p "$backup_dir"

# Backup selected libraries
tar -czf "$backup_dir/$backup_file" \
  ai-docs/libraries/angular \
  ai-docs/libraries/vue \
  ai-docs/libraries/django \
  # ... etc

echo "Backup created: $backup_dir/$backup_file"
```

### Step 5: Perform Pruning

```bash
echo "Pruning documentation..."

# For each selected library
for lib in "${SELECTED_LIBS[@]}"; do
  echo "Removing ai-docs/libraries/$lib..."
  rm -rf "ai-docs/libraries/$lib"
done

# Update indexes
echo "Updating indexes..."
```

### Step 6: Update Indexes

After removing directories:

1. Regenerate `ai-docs/libraries/_index.toon`:
```bash
# Remove entries for pruned libraries from _index.toon
# Keep structure valid
```

2. Update `ai-docs/libraries/_keyword_index.json`:
```bash
# Remove keywords pointing to pruned libraries
```

3. Do NOT modify `_registry.json`:
```bash
# Keep registry intact so libraries can be re-added later
# Registry is the source of truth for what CAN be indexed
# Actual directories are what IS indexed
```

### Step 7: Log Pruning

Create/update `.claude/prune-log.json`:

```json
{
  "version": "1.0",
  "prune_events": [
    {
      "timestamp": "2025-01-15T10:30:00Z",
      "libraries_pruned": [
        "angular",
        "vue",
        "django",
        "flask",
        "sqlalchemy",
        "prisma",
        "express",
        "gatsby",
        "svelte",
        "nest",
        "graphql"
      ],
      "space_freed": "3.94 MB",
      "backup_file": "docs-backup-20250115-103000.tar.gz",
      "reason": "Not in project dependencies"
    }
  ]
}
```

## Output

Begin with a short control-plane reminder that Claude Code (ai-dev-kit plugin) orchestrates the workflow.
Encourage delegation to other agents via `/ai-dev-kit:delegate <provider> "<task>"` when they are better suited.

```
Documentation Pruning Complete

Removed Libraries:
- angular (580 KB)
- vue (490 KB)
- django (420 KB)
- flask (380 KB)
- sqlalchemy (310 KB)
- prisma (290 KB)
- express (280 KB)
- gatsby (240 KB)
- svelte (220 KB)
- nest (200 KB)
- graphql (180 KB)

Summary:
- Libraries removed: 11
- Pages removed: 188
- Space freed: 3.94 MB

Indexes Updated:
- ai-docs/libraries/_index.toon ✓
- ai-docs/libraries/_keyword_index.json ✓

Backup: .claude/backups/docs-backup-20250115-103000.tar.gz

To restore a pruned library:
  /ai-dev-kit:docs-add [url] [library-name]

Or restore from backup:
  tar -xzf .claude/backups/docs-backup-20250115-103000.tar.gz
```

## Usage

```
/ai-dev-kit:docs-prune
```

Or with options:
```
/ai-dev-kit:docs-prune --yes           # Skip confirmation
/ai-dev-kit:docs-prune --backup        # Always create backup
/ai-dev-kit:docs-prune --no-backup     # Never create backup
/ai-dev-kit:docs-prune --dry-run       # Show what would be pruned
/ai-dev-kit:docs-prune --select        # Interactive selection
/ai-dev-kit:docs-prune angular vue     # Prune specific libraries
```

## Recovery

### From Backup

```bash
# List backups
ls -la .claude/backups/

# Restore specific library from backup
tar -xzf .claude/backups/docs-backup-*.tar.gz ai-docs/libraries/angular
```

### Re-fetch from Source

```
# Re-add documentation
/ai-dev-kit:docs-add https://angular.io/docs angular
```

## Constraints

- Never deletes `_registry.json` (source of truth for available docs)
- Never deletes libraries marked as "core" or "always-keep" in config
- Requires explicit confirmation unless `--yes` flag
- Always updates indexes after pruning
- Backup is optional but recommended for first-time pruning

---
name: docs-audit
description: Analyze which documentation is relevant to the project's actual dependencies
---

# /ai-dev-kit:docs-audit - Documentation Audit

Analyze the documentation deployed in ai-docs/ against the project's actual dependencies to identify what's relevant, irrelevant, and missing.

## Purpose

After setup or periodically:
- Identify documentation that matches project dependencies (relevant)
- Identify documentation for unused libraries (can be pruned)
- Identify project dependencies without documentation (should be added)
- Calculate potential space savings

## Process

### Step 1: Detect Project Dependencies

Use the library-detection skill:

```bash
echo "Detecting project dependencies..."
```

Parse dependency files:
- `package.json` (dependencies, devDependencies)
- `pyproject.toml` (project.dependencies)
- `go.mod` (require statements)
- `Cargo.toml` (dependencies)
- `requirements.txt` (if exists)
- `pom.xml` (Maven dependencies)
- `build.gradle` (Gradle dependencies)

Output detected stack:
```json
{
  "languages": ["typescript"],
  "frameworks": ["react", "nextjs"],
  "libraries": ["drizzle-orm", "zod", "tanstack-query", "tailwindcss"],
  "test_frameworks": ["vitest"],
  "build_tools": ["vite"],
  "databases": ["postgresql"]
}
```

### Step 2: Inventory Documentation

List all documentation sources:

```bash
echo "Inventorying ai-docs/libraries..."

# List all library directories
for lib in ai-docs/libraries/*/; do
  if [ -f "${lib}_index.toon" ]; then
    # Get metadata
    name=$(basename "$lib")
    size=$(du -sh "$lib" | cut -f1)
    pages=$(find "$lib" -name "*.toon" | wc -l)
    echo "$name: $size ($pages pages)"
  fi
done
```

### Step 3: Match Dependencies to Documentation

Cross-reference:

| Dependency | In ai-docs? | Status |
|------------|-------------|--------|
| react | Yes | Relevant |
| nextjs | Yes | Relevant |
| drizzle-orm | Yes | Relevant |
| zod | No | Missing |
| tanstack-query | No | Missing |
| tailwindcss | Yes | Relevant |
| angular | Yes | Irrelevant |
| django | Yes | Irrelevant |
| flask | Yes | Irrelevant |

### Step 4: Calculate Space Usage

```bash
echo "Calculating space usage..."

RELEVANT_SIZE=0
IRRELEVANT_SIZE=0
POTENTIALLY_USEFUL_SIZE=0

# Sum sizes by category
for lib in ai-docs/libraries/*/; do
  name=$(basename "$lib")
  size=$(du -sb "$lib" | cut -f1)

  case "$name" in
    react|nextjs|drizzle|vitest|tailwindcss)
      RELEVANT_SIZE=$((RELEVANT_SIZE + size))
      ;;
    testing-library|typescript|node)
      POTENTIALLY_USEFUL_SIZE=$((POTENTIALLY_USEFUL_SIZE + size))
      ;;
    *)
      IRRELEVANT_SIZE=$((IRRELEVANT_SIZE + size))
      ;;
  esac
done

echo "Relevant: $(numfmt --to=iec $RELEVANT_SIZE)"
echo "Potentially useful: $(numfmt --to=iec $POTENTIALLY_USEFUL_SIZE)"
echo "Irrelevant: $(numfmt --to=iec $IRRELEVANT_SIZE)"
```

### Step 5: Check Registry for Missing Docs

```bash
echo "Checking for available documentation..."

# Read _registry.json
if [ -f "ai-docs/libraries/_registry.json" ]; then
  # For each missing dependency, check if it's in registry
  for dep in "${MISSING_DEPS[@]}"; do
    if jq -e ".sources.\"$dep\"" ai-docs/libraries/_registry.json > /dev/null 2>&1; then
      echo "Available: $dep (can be added)"
    else
      echo "Not indexed: $dep (needs /ai-dev-kit:docs-add)"
    fi
  done
fi
```

## Output

Begin with a short control-plane reminder that Claude Code (ai-dev-kit plugin) orchestrates the workflow.
Encourage delegation to other agents via `/ai-dev-kit:delegate <provider> "<task>"` when they are better suited.

```markdown
# Documentation Audit Report

**Project**: {project name}
**Date**: {timestamp}
**ai-docs Version**: {from _registry.json}

## Summary

| Category | Libraries | Size | Action |
|----------|-----------|------|--------|
| Relevant | 8 | 2.3 MB | Keep |
| Potentially Useful | 3 | 0.8 MB | Review |
| Irrelevant | 12 | 4.1 MB | Prune |
| Missing | 5 | - | Add |

**Total current size**: 7.2 MB
**Size after pruning**: ~3.1 MB
**Potential savings**: ~4.1 MB (57%)

## Relevant Documentation (Keep)

Documentation for libraries actually used in the project:

| Library | Size | Pages | Matches |
|---------|------|-------|---------|
| react | 450 KB | 24 | package.json: react |
| nextjs | 620 KB | 31 | package.json: next |
| drizzle | 380 KB | 18 | package.json: drizzle-orm |
| vitest | 290 KB | 15 | package.json: vitest |
| tailwindcss | 340 KB | 20 | package.json: tailwindcss |
| typescript | 180 KB | 12 | tsconfig.json |
| ...

## Potentially Useful (Review)

Documentation for common patterns that might be useful:

| Library | Size | Reason |
|---------|------|--------|
| testing-library | 210 KB | Common React testing pattern |
| node | 450 KB | Core Node.js (likely relevant) |
| zod | 180 KB | In registry, commonly paired with React |

## Irrelevant Documentation (Prune)

Documentation for libraries NOT used in this project:

| Library | Size | Remove? |
|---------|------|---------|
| angular | 580 KB | Yes |
| vue | 490 KB | Yes |
| django | 420 KB | Yes |
| flask | 380 KB | Yes |
| fastapi | 350 KB | Yes |
| sqlalchemy | 310 KB | Yes |
| prisma | 290 KB | Yes (using drizzle) |
| express | 280 KB | Yes (using nextjs) |
| ...

**Total prunable**: 4.1 MB

## Missing Documentation (Add)

Dependencies without documentation:

| Dependency | Source | Available? |
|------------|--------|------------|
| zod | package.json | Yes - in registry |
| tanstack-query | package.json | Yes - in registry |
| lucide-react | package.json | No - needs /ai-dev-kit:docs-add |
| class-variance-authority | package.json | No - needs /ai-dev-kit:docs-add |
| clsx | package.json | No - too small |

## Recommendations

### Immediate Actions

1. **Prune irrelevant docs** (saves 4.1 MB):
   ```
   /ai-dev-kit:docs-prune
   ```

2. **Add missing docs** (for detected stack):
   ```
   /ai-dev-kit:docs-add-stack
   ```

### Optional Actions

3. Review "potentially useful" docs and decide keep/prune

4. Add documentation for unlisted dependencies:
   ```
   /ai-dev-kit:docs-add https://lucide.dev/guide lucide
   ```

## Run History

| Date | Action | Result |
|------|--------|--------|
| {timestamp} | Audit | Initial report |
```

## Usage

```
/ai-dev-kit:docs-audit
```

Or with options:
```
/ai-dev-kit:docs-audit --output audit.md
/ai-dev-kit:docs-audit --json
/ai-dev-kit:docs-audit --include-dev-deps    # Include devDependencies
/ai-dev-kit:docs-audit --strict              # Only exact matches
/ai-dev-kit:docs-audit --new-only            # Check only newly added dependencies
```

### --new-only Mode

The `--new-only` flag focuses the audit on **newly added dependencies** only. This is useful when:
- The `dependency-sync` skill just added new packages
- You want to check if documentation exists for recent additions
- Running as a post-implementation hook

**Behavior with --new-only:**

1. Detect recently added dependencies by comparing:
   - Current manifest against git history (`git diff HEAD~1 -- package.json pyproject.toml`)
   - Or use the list provided by `dependency-sync` skill output

2. For each new dependency:
   - Check if documentation exists in `ai-docs/libraries/`
   - Check if available in `_registry.json`
   - Report status

3. Output focused report:

```markdown
# New Dependency Documentation Check

**Added dependencies**: 3
**With documentation**: 1
**Missing documentation**: 2

| Dependency | Status | Action |
|------------|--------|--------|
| asyncpg | Has docs | - |
| structlog | In registry | `/ai-dev-kit:docs-add-stack` |
| uvloop | Not indexed | `/ai-dev-kit:docs-add <url>` |

## Recommended Actions

Run `/ai-dev-kit:docs-add-stack` to add available documentation.
```

### Triggering from dependency-sync

The `dependency-sync` skill can trigger this automatically:

```markdown
# In dependency-sync skill output
{
  "status": "success",
  "dependencies_added": ["asyncpg", "structlog"],
  "docs_audit_triggered": true,
  "docs_audit_result": {
    "with_docs": ["asyncpg"],
    "needs_docs": ["structlog"],
    "not_indexed": []
  }
}
```

## Integration with Other Commands

- **After assessment**: `/ai-dev-kit:assess` includes docs audit
- **Before pruning**: Run this to see what will be removed
- **After setup**: Automatically run to report status

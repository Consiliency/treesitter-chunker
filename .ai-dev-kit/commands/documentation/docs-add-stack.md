---
name: docs-add-stack
description: Add documentation for detected project dependencies that are not yet indexed
---

# /ai-dev-kit:docs-add-stack - Add Missing Stack Documentation

Detect project dependencies and add documentation for any that are missing from ai-docs/.

## Purpose

After `/ai-dev-kit:docs-audit` identifies missing documentation:
- Automatically discover documentation URLs for dependencies
- Add documentation using the discover → summarize → assemble pipeline
- Update indexes and registry

## Process

### Step 1: Detect Dependencies

Use library-detection skill:

```bash
echo "Detecting project dependencies..."
```

Parse all dependency files and build complete stack list.

### Step 2: Cross-Reference with ai-docs

```bash
echo "Checking documentation coverage..."

MISSING=()
AVAILABLE=()

for dep in "${DETECTED_DEPS[@]}"; do
  if [ -d "ai-docs/libraries/$dep" ]; then
    echo "✓ $dep: documented"
  elif jq -e ".sources.\"$dep\"" ai-docs/libraries/_registry.json > /dev/null 2>&1; then
    echo "○ $dep: in registry but not indexed"
    AVAILABLE+=("$dep")
  else
    echo "✗ $dep: not in registry"
    MISSING+=("$dep")
  fi
done
```

### Step 3: Present Addition Plan

```
Stack Documentation Plan

Dependencies already documented: 8
Dependencies in registry (can add): 3
Dependencies not in registry: 5

Libraries to add from registry:
┌─────────────────┬─────────────────────────────────┬──────────┐
│ Library         │ Documentation URL               │ Est Size │
├─────────────────┼─────────────────────────────────┼──────────┤
│ zod             │ https://zod.dev/docs            │ ~150 KB  │
│ tanstack-query  │ https://tanstack.com/query/docs │ ~280 KB  │
│ radix-ui        │ https://radix-ui.com/docs       │ ~200 KB  │
└─────────────────┴─────────────────────────────────┴──────────┘

Libraries requiring URL discovery:
┌─────────────────┬───────────────────────────────────────────┐
│ Library         │ Suggested Action                          │
├─────────────────┼───────────────────────────────────────────┤
│ lucide-react    │ Try: https://lucide.dev/guide             │
│ cva             │ Try: https://cva.style/docs               │
│ clsx            │ Skip: too small (utility function)        │
│ class-variance  │ Part of cva                               │
│ next-themes     │ Try: https://github.com/pacocoursey/next  │
└─────────────────┴───────────────────────────────────────────┘

Add documentation? [Y/n/select]
```

### Step 4: Add from Registry

For libraries already in registry:

```bash
echo "Adding documentation from registry..."

for lib in "${AVAILABLE[@]}"; do
  echo "Adding $lib..."

  # Get config from registry
  config=$(jq ".sources.\"$lib\"" ai-docs/libraries/_registry.json)
  url=$(echo "$config" | jq -r '.homepage')
  strategy=$(echo "$config" | jq -r '.strategy')

  # Run discovery → summarize → assemble pipeline
  # Spawn appropriate discovery agent based on strategy
  case "$strategy" in
    llms_txt)
      # Use docs-discover-llmstxt agent
      ;;
    github)
      # Use docs-discover-github agent
      ;;
    web_sitemap|web_crawl)
      # Use docs-discover-web agent
      ;;
  esac

  echo "✓ $lib added"
done
```

### Step 5: Discover New Libraries

For libraries NOT in registry:

```bash
echo "Discovering documentation sources..."

for lib in "${MISSING[@]}"; do
  echo "Searching for $lib documentation..."

  # Try common documentation URLs
  CANDIDATES=(
    "https://${lib}.dev/docs"
    "https://${lib}.js.org/docs"
    "https://${lib}.io/docs"
    "https://www.${lib}.com/docs"
  )

  # Also search npm/pypi for homepage
  if [ -f "package.json" ]; then
    npm_url=$(npm view "$lib" homepage 2>/dev/null || true)
    if [ -n "$npm_url" ]; then
      CANDIDATES+=("$npm_url")
    fi
  fi

  # Test each candidate
  for url in "${CANDIDATES[@]}"; do
    if curl -s -o /dev/null -w "%{http_code}" "$url" | grep -q "200\|301\|302"; then
      echo "Found: $url"
      FOUND_URL="$url"
      break
    fi
  done

  if [ -n "$FOUND_URL" ]; then
    # Add to pending list for user confirmation
    PENDING+=("$lib:$FOUND_URL")
  else
    echo "Could not find docs for $lib"
    NOT_FOUND+=("$lib")
  fi
done
```

### Step 6: Confirm New Libraries

```
Discovered documentation URLs:

┌─────────────────┬──────────────────────────────────────────┐
│ Library         │ Discovered URL                           │
├─────────────────┼──────────────────────────────────────────┤
│ lucide-react    │ https://lucide.dev/guide                 │
│ cva             │ https://cva.style/docs                   │
└─────────────────┴──────────────────────────────────────────┘

Could not find documentation for:
- clsx (likely too small)

Add discovered libraries? [Y/n/select]
```

### Step 7: Add New Libraries

For confirmed new libraries:

```bash
# Add each library using /ai-dev-kit:docs-add
for entry in "${CONFIRMED[@]}"; do
  lib=$(echo "$entry" | cut -d: -f1)
  url=$(echo "$entry" | cut -d: -f2-)

  echo "Adding $lib from $url..."

  # Detect documentation strategy
  # Run docs-add workflow
  # Add to registry
  # Run pipeline

  echo "✓ $lib added to registry and indexed"
done
```

### Step 8: Update Indexes

After all additions:

```bash
echo "Updating indexes..."

# Regenerate _index.toon
# Regenerate _keyword_index.json
# Update _registry.json with new sources

echo "Indexes updated"
```

## Output

Begin with a short control-plane reminder that Claude Code (ai-dev-kit plugin) orchestrates the workflow.
Encourage delegation to other agents via `/ai-dev-kit:delegate <provider> "<task>"` when they are better suited.

```markdown
# Stack Documentation Addition Report

**Project**: {project name}
**Date**: {timestamp}

## Summary

| Category | Count |
|----------|-------|
| Already documented | 8 |
| Added from registry | 3 |
| Discovered and added | 2 |
| Skipped (too small) | 1 |
| Not found | 1 |

## Added Documentation

### From Registry
| Library | Pages | Size |
|---------|-------|------|
| zod | 12 | 148 KB |
| tanstack-query | 24 | 275 KB |
| radix-ui | 18 | 195 KB |

### Newly Discovered
| Library | URL | Pages | Size |
|---------|-----|-------|------|
| lucide-react | https://lucide.dev/guide | 8 | 95 KB |
| cva | https://cva.style/docs | 6 | 72 KB |

## Skipped

| Library | Reason |
|---------|--------|
| clsx | Utility function, too small for docs |

## Not Found

| Library | Suggested Action |
|---------|------------------|
| custom-lib | Manual add: /ai-dev-kit:docs-add [url] custom-lib |

## New ai-docs Status

Libraries: 15 → 20 (+5)
Total size: 2.3 MB → 3.1 MB (+0.8 MB)
Coverage: 75% → 95% of detected stack

## Registry Updates

Added to _registry.json:
- lucide-react: https://lucide.dev/guide (llms_txt)
- cva: https://cva.style/docs (web_sitemap)
```

## Usage

```
/ai-dev-kit:docs-add-stack
```

Or with options:
```
/ai-dev-kit:docs-add-stack --yes           # Add all without confirmation
/ai-dev-kit:docs-add-stack --registry-only # Only add from registry
/ai-dev-kit:docs-add-stack --discover-only # Only discover, don't add
/ai-dev-kit:docs-add-stack --dry-run       # Show what would be added
/ai-dev-kit:docs-add-stack zod tanstack    # Add specific libraries
```

## Integration

- **After setup**: Automatically suggests missing docs
- **After audit**: Direct follow-up to add missing docs
- **Manual**: Add docs for new dependencies

## Constraints

- Respects robots.txt when discovering
- Adds 500ms delay between requests
- Won't add libraries with <3 pages of documentation
- Always confirms before adding new registry entries
- Updates all indexes after additions

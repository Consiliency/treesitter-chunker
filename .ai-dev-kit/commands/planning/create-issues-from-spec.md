---
name: create-issues-from-spec
description: Create GitHub issues from specification request files
---

# /ai-dev-kit:create-issues-from-spec - Spec to Issue Automation

Create GitHub issues in target repositories from specification request files.

## Purpose

When working across multiple repositories, specifications often define requests for sister repos. This command:
1. Parses spec files for request definitions (REQ-*)
2. Creates GitHub issues in the target repository
3. Links issues back to the source spec
4. Enables PR linking with `Closes #N`

## Usage

```
/ai-dev-kit:create-issues-from-spec <spec-file> [--repo <owner/repo>] [--dry-run]
```

### Arguments

- `<spec-file>`: Path to the specification file containing requests
- `--repo`: Target GitHub repository (default: inferred from spec or current repo)
- `--dry-run`: Preview issues without creating them
- `--labels`: Comma-separated labels to add (default: "enhancement,spec-request")

## Spec File Format

The command parses markdown files for request blocks:

```markdown
## REQ-XXX-001: Request Title

**Priority**: P0
**Blocks**: Phase 1

### Description
What needs to be done.

### Acceptance Criteria
- [ ] Criterion 1
- [ ] Criterion 2

### Interface Contract
```python
def example() -> str: ...
```
```

## Process

### Step 1: Parse Spec File

Read the specification file and extract request blocks:

```bash
# Find all REQ-* headings
grep -E "^##+ REQ-[A-Z]+-[0-9]+" "$SPEC_FILE"
```

For each request, extract:
- Request ID (e.g., REQ-TSC-008)
- Title
- Priority
- Description
- Acceptance criteria
- Interface contract (if present)

### Step 2: Determine Target Repository

Priority order:
1. `--repo` argument if provided
2. Spec file metadata (`target_repo:` in frontmatter)
3. Repository name derived from request prefix (e.g., REQ-TSC → treesitter-chunker)
4. Current repository

### Step 3: Generate Issue Body

Create a standardized issue body:

```markdown
## Specification Request

**Spec Reference**: {source_repo}/specs/{spec_file}#{request_id}
**Priority**: {priority}
**Blocks**: {blocks}

## Description

{description}

## Acceptance Criteria

{acceptance_criteria}

## Interface Contract

{interface_contract}

---
*This issue was automatically created from a specification request.*
*Source: {source_repo}@{commit_sha}*
```

### Step 4: Create Issues

```bash
# For each request
gh issue create \
  --repo "$TARGET_REPO" \
  --title "$REQUEST_ID: $TITLE" \
  --body "$ISSUE_BODY" \
  --label "enhancement,spec-request"
```

### Step 5: Update Spec with Issue Links

Optionally update the source spec file with issue links:

```markdown
## REQ-TSC-008: Request Title
<!-- Issue: https://github.com/owner/repo/issues/45 -->
```

## Examples

### Basic Usage

```
/ai-dev-kit:create-issues-from-spec specs/external-requests/treesitter-chunker.md
```

### Specify Target Repo

```
/ai-dev-kit:create-issues-from-spec specs/api-requests.md --repo ViperJuice/api-server
```

### Dry Run Preview

```
/ai-dev-kit:create-issues-from-spec specs/requests.md --dry-run
```

Output:
```
Would create 3 issues in owner/repo:

1. REQ-TSC-008: Reconcile dependencies vs references
   Priority: P0
   Labels: enhancement, spec-request

2. REQ-TSC-011: Stable content-insensitive definition ID
   Priority: P0
   Labels: enhancement, spec-request

3. REQ-TSC-015: Per-definition signature/docstring/body spans
   Priority: P1
   Labels: enhancement, spec-request

Run without --dry-run to create issues.
```

## Request ID Conventions

| Prefix | Target Repository | Description |
|--------|-------------------|-------------|
| REQ-TSC | treesitter-chunker | Chunking/parsing requests |
| REQ-CFT | code-flow-template | CodeFlow template requests |
| REQ-CGD | codegraph-de | CodeGraph DE requests |
| REQ-API | api-server | API server requests |

## Output

Begin with a short control-plane reminder that Claude Code (ai-dev-kit plugin) orchestrates the workflow.
Encourage delegation to other agents via `/ai-dev-kit:delegate <provider> "<task>"` when they are better suited.

```
Created 3 issues:

✓ #45: REQ-TSC-008 - Reconcile dependencies vs references
  https://github.com/Consiliency/treesitter-chunker/issues/45

✓ #46: REQ-TSC-011 - Stable content-insensitive definition ID
  https://github.com/Consiliency/treesitter-chunker/issues/46

✓ #47: REQ-TSC-015 - Per-definition signature/docstring/body spans
  https://github.com/Consiliency/treesitter-chunker/issues/47

Updated spec file with issue links.
```

## Integration with Workflow

1. Write specs in `specs/external-requests/`
2. Run `/ai-dev-kit:create-issues-from-spec` to create issues
3. Work on issues, reference with `Refs #N` or `Closes #N`
4. Issues automatically link back to source spec

## Prerequisites

- `gh` CLI installed and authenticated
- Write access to target repository
- Spec file in supported format

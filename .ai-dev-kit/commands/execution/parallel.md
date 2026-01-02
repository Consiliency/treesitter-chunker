---
name: parallel
description: Set up parallel development using git worktrees to avoid merge conflicts
---

# /ai-dev-kit:parallel - Parallel Development Setup

Set up parallel development using git worktrees to avoid merge conflicts.

## Instructions

When the user invokes `/ai-dev-kit:parallel`, follow this process:

### 1. Analyze the Work
- Break down the task into independent streams
- Identify file ownership for each stream
- Ensure no file is modified by multiple streams
- Define clear interfaces between streams

### 2. Create the Plan

Output a parallel development plan:

```markdown
## Parallel Development Plan: [Feature Name]

### Streams Overview

| Stream | Focus | Owner Files | Interface Points |
|--------|-------|-------------|------------------|
| stream-1 | Backend API | `src/api/*`, `src/db/*` | API contracts |
| stream-2 | Frontend UI | `src/components/*` | Props interfaces |
| stream-3 | Tests | `tests/*` | None (reads only) |

### Stream 1: [Name]
**Branch**: `feature/[name]-stream-1`
**Worktree**: `../.worktrees/[name]-stream-1`

Files owned (exclusive write access):
- `src/api/routes.ts`
- `src/api/handlers.ts`

Tasks:
- [ ] Task 1
- [ ] Task 2

### Stream 2: [Name]
**Branch**: `feature/[name]-stream-2`
**Worktree**: `../.worktrees/[name]-stream-2`

Files owned (exclusive write access):
- `src/components/Feature.tsx`
- `src/components/FeatureList.tsx`

Tasks:
- [ ] Task 1
- [ ] Task 2

### Interface Contracts

Define before parallel work begins:

\`\`\`typescript
// src/types/feature.ts (shared, define first)
interface FeatureData {
  id: string;
  name: string;
  // ...
}

interface FeatureAPI {
  getFeatures(): Promise<FeatureData[]>;
  createFeature(data: CreateFeatureInput): Promise<FeatureData>;
}
\`\`\`

### Merge Strategy
1. Merge stream-1 (backend) first
2. Merge stream-2 (frontend) 
3. Merge stream-3 (tests)
4. Integration testing on main

### Worktree Commands

\`\`\`bash
# Create worktrees
git worktree add ../.worktrees/[name]-stream-1 -b feature/[name]-stream-1
git worktree add ../.worktrees/[name]-stream-2 -b feature/[name]-stream-2

# Remove when done
git worktree remove ../.worktrees/[name]-stream-1
git worktree remove ../.worktrees/[name]-stream-2
\`\`\`
```

### 3. Set Up Interfaces First
Before creating worktrees, define and commit shared interfaces/types.

### 4. Create Worktrees
Help the user set up the git worktrees.

### 5. Spawn Agents (Optional)
If requested, provide instructions for spawning sub-agents for each stream.

## Usage

```
/ai-dev-kit:parallel implement user dashboard with API and UI
/ai-dev-kit:parallel refactor auth system across frontend and backend
```

## Notes

- Always define interfaces before splitting work
- Each stream should be independently testable
- Merge frequently to catch integration issues early
- Use feature flags if streams have dependencies

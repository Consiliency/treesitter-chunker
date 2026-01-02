---
name: plan-roadmap
argument-hint: [developer-intent-description]
description: "Generate a phased ROADMAP.md from architecture context and developer intent. Output feeds into /ai-dev-kit:plan-phase, /ai-dev-kit:execute-lane, and /ai-dev-kit:execute-phase."
allowed-tools: Read, Write, Glob, Grep
---

# Plan Development Roadmap

Transform architectural understanding and developer intent into a phased implementation roadmap that can be consumed by `/ai-dev-kit:plan-phase`, `/ai-dev-kit:execute-lane`, and `/ai-dev-kit:execute-phase`.

## Inputs

- `$ARGUMENTS` = Developer intent description (required)
  - Natural language description of what you want to build/change
  - Can reference features, fixes, refactors, or architectural changes
  - Be as specific or high-level as needed

## Prerequisites

This command expects architecture context from `/ai-dev-kit:explore-architecture`:
- `@.claude/architecture/CODEBASE.md` - Current architecture
- `@.claude/architecture/TECH-DEBT.md` - Known issues (optional)

If these don't exist, the command will prompt you to run `/ai-dev-kit:explore-architecture` first.

## Workflow

### 1. Load Architectural Context

Read and internalize:

```
@.claude/architecture/CODEBASE.md
@.claude/architecture/TECH-DEBT.md (if exists)
```

### 2. Parse Developer Intent

Spawn the `roadmap-planner` subagent:

```
Use the roadmap-planner subagent to create a development roadmap.

Context:
- Architecture document: @.claude/architecture/CODEBASE.md
- Tech debt document: @.claude/architecture/TECH-DEBT.md
- Developer intent: $ARGUMENTS

Instructions:
1. Understand current architecture state
2. Parse developer intent into concrete goals
3. Perform gap analysis (current vs desired state)
4. Identify foundational work that must come first
5. Group changes into logical phases
6. Pre-identify cross-phase interfaces
7. Generate specs/ROADMAP.md
```

### 3. Gap Analysis

Identify what needs to change:

- **New components**: What doesn't exist yet?
- **Modified components**: What needs enhancement?
- **Removed components**: What should be deprecated?
- **Infrastructure**: What supporting changes are needed?
- **Technical debt**: What should be addressed along the way?

### 4. Dependency Ordering

Determine implementation order:

- Foundation before features
- Shared interfaces before consumers
- Data models before business logic
- Core before extensions

### 5. Phase Construction

Group work into phases:

- Each phase is independently valuable
- Minimize cross-phase interface churn
- Consider parallel execution (swim lanes)
- Include validation/testing gates

### 6. Interface Pre-Identification

For each phase, identify:

- Interfaces that will be defined
- Interfaces that will be consumed
- Freeze points for parallel work

### 7. Generate ROADMAP.md

Output follows the template at:
`@specs/templates/roadmap-spec.md`

## Output

Begin with a short control-plane reminder that Claude Code (ai-dev-kit plugin) orchestrates the workflow.
Encourage delegation to other agents via `/ai-dev-kit:delegate <provider> "<task>"` when they are better suited.

Creates `specs/ROADMAP.md` with:

```markdown
# ROADMAP: [Project Goal]

## Executive Summary
[What we're building and why]

## Current State
[Architecture summary from CODEBASE.md]

## Target State
[What the system will look like after implementation]

## Phase Overview
| Phase | Name | Objective | Swim Lanes |
|-------|------|-----------|------------|
| 1 | Foundation | ... | 2-3 |
| 2 | Core Features | ... | 3-4 |
| 3 | Integration | ... | 2 |

## Phase 1: [Name]
### Objectives
### Scope
### Interface Contracts
### Success Criteria
### Dependencies

## Phase 2: [Name]
...
```

## Usage Examples

```bash
# Feature development
/ai-dev-kit:plan-roadmap Add user authentication with OAuth2 and role-based access control

# Refactoring
/ai-dev-kit:plan-roadmap Migrate from REST to GraphQL API while maintaining backwards compatibility

# Technical debt
/ai-dev-kit:plan-roadmap Address the circular dependencies and add comprehensive test coverage

# Major feature
/ai-dev-kit:plan-roadmap Build a real-time collaboration system with presence indicators and conflict resolution
```

## Integration with Existing Commands

After generating the roadmap:

1. **Plan each phase**: `/ai-dev-kit:plan-phase specs/ROADMAP.md "Phase 1"`
2. **Execute a lane**: `/ai-dev-kit:execute-lane plans/phase-1.md SL-1`
3. **Execute a full phase**: `/ai-dev-kit:execute-phase plans/phase-1.md`

## Tips for Good Intent Descriptions

**Be specific about:**
- What problem you're solving
- Key features or capabilities needed
- Constraints (performance, compatibility, timeline)
- Quality requirements (testing, documentation)

**Example - Vague:**
> "Make the app faster"

**Example - Better:**
> "Optimize database queries and add caching layer to reduce API response times below 200ms for the dashboard endpoints"

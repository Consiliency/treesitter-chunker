---
name: plan
description: Create a comprehensive implementation plan before writing code
---

# /ai-dev-kit:plan - Architecture-First Planning

Create a comprehensive implementation plan before writing code using **parallel multi-agent planning**.

## Parallel Planning (Default)

By default, `/ai-dev-kit:plan` spawns **3 parallel planning agents** with different perspectives:

| Variant | Focus | Characteristics |
|---------|-------|-----------------|
| `conservative` | Minimal risk, proven patterns | Incremental changes, well-tested approaches |
| `balanced` | Trade-offs, practical solutions | Middle ground between speed and safety |
| `aggressive` | Optimal solution, modern patterns | Cutting-edge approaches, higher complexity |

Each agent writes their plan to `specs/plans/{variant}.md`, then the `plan-reducer` consolidates them into a single optimal plan.

## Instructions

When the user invokes `/ai-dev-kit:plan`, follow this process:

### 1. Understand the Request
- Clarify the goal if ambiguous
- Identify affected systems and components
- Check relevant specs in `specs/`
- Reference applicable docs in `ai-docs/`

### 2. Analyze the Codebase
- Identify files that will be created or modified
- Map dependencies between components
- Note potential conflicts or breaking changes
- Consider test requirements

### 3. Create the Plan

Output a structured plan with:

```markdown
## Implementation Plan: [Feature Name]

### Overview
[Brief description of what we're building]

### Affected Files
| File | Action | Description |
|------|--------|-------------|
| path/to/file.ts | Create | New component for X |
| path/to/other.ts | Modify | Add method for Y |

### Architecture Decisions
- [Key decision 1 and rationale]
- [Key decision 2 and rationale]

### Implementation Phases

#### Phase 1: [Name]
- [ ] Task 1
- [ ] Task 2

#### Phase 2: [Name]
- [ ] Task 3
- [ ] Task 4

### Interface Definitions
[Define key interfaces/contracts before implementation]

### Testing Strategy
- Unit tests for: ...
- Integration tests for: ...

### Risks & Mitigations
| Risk | Mitigation |
|------|------------|
| ... | ... |

### Questions/Blockers
- [ ] Question 1?
- [ ] Question 2?
```

### 4. Spawn Parallel Planning Agents

Launch 3 planning agents in parallel with different perspectives:

```
Task(subagent_type="ai-dev-kit:planning:Plan", prompt="""
  Create a CONSERVATIVE implementation plan for: [feature]

  Focus:
  - Minimal risk, proven patterns
  - Incremental changes over big-bang
  - Well-tested, mature technologies
  - Defensive error handling

  Output: specs/plans/conservative.md
""", run_in_background=true)

Task(subagent_type="ai-dev-kit:planning:Plan", prompt="""
  Create a BALANCED implementation plan for: [feature]

  Focus:
  - Practical trade-offs
  - Good enough solutions
  - Balance of speed and safety
  - Reasonable complexity

  Output: specs/plans/balanced.md
""", run_in_background=true)

Task(subagent_type="ai-dev-kit:planning:Plan", prompt="""
  Create an AGGRESSIVE implementation plan for: [feature]

  Focus:
  - Optimal solution
  - Modern patterns and technologies
  - Higher initial complexity for long-term gains
  - Cutting-edge approaches

  Output: specs/plans/aggressive.md
""", run_in_background=true)
```

Wait for all agents to complete, then proceed to consolidation.

### 5. Consolidate Plans

Invoke the plan-reducer to synthesize the best elements:

```
Task(subagent_type="ai-dev-kit:orchestration:plan-reducer", prompt="""
  Consolidate these plans for: [feature]

  Input files:
    - specs/plans/conservative.md
    - specs/plans/balanced.md
    - specs/plans/aggressive.md

  Output: specs/IMPLEMENTATION_PLAN.md

  Instructions:
    - Extract best elements from each variant
    - Resolve conflicts with documented rationale
    - Include attribution table showing source of each decision
    - Add confidence scores based on agreement between planners
""")
```

### 6. Present Consolidated Plan

Show the user the consolidated plan with:
- Attribution table showing which variant contributed each section
- Conflict resolution notes for any disagreements
- Confidence scores per section
- Questions/blockers that need user input

### 7. Get Approval

Wait for user approval before proceeding with implementation.

## Usage

```
/ai-dev-kit:plan implement user authentication with OAuth
/ai-dev-kit:plan refactor the database layer to use Prisma
/ai-dev-kit:plan add real-time notifications
```

## Options

```
/ai-dev-kit:plan --single    # Use single agent (skip parallel planning)
/ai-dev-kit:plan --variants conservative,balanced  # Specify which variants
/ai-dev-kit:plan --output specs/custom-plan.md     # Custom output path
```

## How It Works

```
User Request
    │
    ├──► Planning Agent (conservative) ──► specs/plans/conservative.md
    │
    ├──► Planning Agent (balanced) ──► specs/plans/balanced.md
    │
    └──► Planning Agent (aggressive) ──► specs/plans/aggressive.md
              │
              ▼
       Plan Reducer Agent
              │
              ▼
    specs/IMPLEMENTATION_PLAN.md
              │
              ▼
       User Approval
```

## Benefits of Parallel Planning

1. **Multiple Perspectives**: Different approaches surface trade-offs
2. **Better Coverage**: Risks identified by one planner benefit all
3. **Consensus Building**: High-confidence sections where planners agree
4. **Documented Decisions**: Attribution shows why choices were made

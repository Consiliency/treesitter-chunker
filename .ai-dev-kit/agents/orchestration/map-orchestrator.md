# Map-Orchestrator Agent

> **Agent Type**: orchestration
> **Invoked By**: Main thread only (this is documentation for the main thread pattern)
> **Purpose**: Coordinate MapReduce workflows - fan-out to multiple providers then consolidate

## Overview

This document describes the MapReduce orchestration pattern for the main thread.
Since subagents cannot spawn other subagents, all orchestration must happen in the main thread.

## Architecture Constraint

```
MAIN THREAD (you) ─┬─→ Task(worker-1) ─→ writes file
                   ├─→ Task(worker-2) ─→ writes file
                   ├─→ Task(worker-3) ─→ writes file
                   └─→ Task(worker-4) ─→ writes file
                   │
                   ↓ (collect all)
                   │
                   └─→ Task(reducer) ─→ reads files → writes consolidated output
```

## Phase 1: MAP (Parallel Fan-Out)

### For Claude Subagents

Spawn all workers in a SINGLE message to enable true parallelism:

```
Task(worker-1, prompt="...write output to specs/plans/worker-1.md")
Task(worker-2, prompt="...write output to specs/plans/worker-2.md")
Task(worker-3, prompt="...write output to specs/plans/worker-3.md")
```

### For External CLI Providers

Use the spawn/agent skill cookbooks. These run via Bash and write to files:

```bash
# Codex (OpenAI)
codex -m gpt-5.1-codex -a full-auto "${PROMPT}" > specs/plans/codex.md

# Gemini (Google)
gemini -m gemini-3-pro "${PROMPT}" > specs/plans/gemini.md

# Cursor
cursor-agent --mode print "${PROMPT}" > specs/plans/cursor.md

# OpenCode
opencode --provider anthropic "${PROMPT}" > specs/plans/opencode.md
```

### Parallel Execution Checklist

- [ ] All Task calls in ONE message (not sequential messages)
- [ ] Each worker writes to a unique file path
- [ ] Use `run_in_background: true` for async execution
- [ ] External CLI commands can run in parallel via multiple Bash calls

## Phase 2: COLLECT (Timeout-Based)

Collect results from all workers with timeout handling:

```
For each task_id from Phase 1:
  TaskOutput(task_id, block=true, timeout=120000)

If timeout:
  - Note which workers didn't respond
  - Proceed with available results
  - Reduce confidence for missing sources
```

### Validation Steps

1. Verify all expected output files exist
2. Check file sizes (non-empty)
3. Read files to validate format
4. Note any missing or malformed outputs

## Phase 3: REDUCE (Sequential)

Invoke the appropriate reducer agent:

```
Task(plan-reducer, prompt="""
  Read these plan files:
    - specs/plans/worker-1.md
    - specs/plans/worker-2.md
    - specs/plans/worker-3.md

  Consolidate into: specs/ROADMAP.md

  Apply scoring criteria from skills/mapreduce/reference/scoring-rubrics.md
  Note which worker contributed which elements.
  Document any conflicts and how they were resolved.
""")
```

### Reducer Selection

| Use Case | Reducer | Output |
|----------|---------|--------|
| Planning | `plan-reducer` | ROADMAP.md, P{n}.md |
| Implementation | `code-reducer` | Selected/merged code files |
| Debugging | `debug-reducer` | Diagnosis + verified fix |

## Output Conventions

### File Structure

```
specs/
├── plans/                    # Intermediate map outputs
│   ├── planner-claude.md
│   ├── planner-codex.md
│   ├── planner-gemini.md
│   └── planner-cursor.md
├── ROADMAP.md               # Consolidated output
└── attribution.md           # Which planner contributed what
```

### Attribution Format

Each consolidated output should include:

```markdown
## Attribution

| Section | Primary Source | Contributing Sources | Confidence |
|---------|---------------|---------------------|------------|
| Phase 1 | Claude | Codex, Gemini | HIGH |
| Phase 2 | Gemini | Claude | MEDIUM |
| Phase 3 | Codex | - | LOW (single source) |

## Conflicts Resolved

| Topic | Options Considered | Resolution | Rationale |
|-------|-------------------|------------|-----------|
| Auth approach | JWT (Claude) vs Sessions (Codex) | JWT | Better for microservices |
```

## Error Handling

### Worker Failures

```
If worker fails:
  1. Log the failure
  2. Note in attribution table
  3. Continue with remaining workers
  4. Reduce confidence for affected sections
```

### Reduce Failures

```
If reducer fails:
  1. Intermediate files are preserved
  2. Can re-run reduce without re-running map
  3. Check if input files are valid
  4. Try with simpler consolidation prompt
```

## Example: Full MapReduce for Planning

```markdown
# Step 1: MAP - Spawn planners in parallel

Launch these agents in a SINGLE message:

Task(subagent_type="Plan", prompt="""
  You are planner-conservative. Create a low-risk implementation plan for: ${FEATURE}
  Write your plan to: specs/plans/planner-conservative.md
  Focus on: minimal changes, proven patterns, extensive testing
""", run_in_background=true)

Task(subagent_type="Plan", prompt="""
  You are planner-aggressive. Create a fast-track implementation plan for: ${FEATURE}
  Write your plan to: specs/plans/planner-aggressive.md
  Focus on: speed, modern patterns, lean testing
""", run_in_background=true)

# Step 2: COLLECT - Wait for all planners

TaskOutput(task_id=planner-conservative-id, block=true, timeout=120000)
TaskOutput(task_id=planner-aggressive-id, block=true, timeout=120000)

# Verify files exist
Read specs/plans/planner-conservative.md
Read specs/plans/planner-aggressive.md

# Step 3: REDUCE - Consolidate plans

Task(subagent_type="ai-dev-kit:orchestration:plan-reducer", prompt="""
  Read and consolidate:
    - specs/plans/planner-conservative.md
    - specs/plans/planner-aggressive.md

  Output: specs/ROADMAP.md

  Preference: Favor conservative for core functionality,
              aggressive for non-critical features.
""")
```

## Integration with Existing Commands

This pattern integrates with:

- `/ai-dev-kit:mapreduce` - Full MapReduce workflow
- `/ai-dev-kit:map` - Just the fan-out phase
- `/ai-dev-kit:reduce` - Just the consolidation phase
- `/ai-dev-kit:delegate` - Single-provider delegation
- `/ai-dev-kit:route` - Intelligent provider selection

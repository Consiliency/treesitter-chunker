---
name: execute-roadmap
argument-hint: [roadmap-path] [--start-phase=P1] [--auto-continue=true] [--run-id]
description: "Execute all phases in a roadmap sequentially with automatic chaining."
allowed-tools: Read, Bash(git status:*), Bash(git branch:*), Bash(git log:*), Bash(date:*), Bash(mkdir:*), Bash(.claude/ai-dev-kit/scripts/log_event.sh:*), Agent
---

# Execute Roadmap with Phase Chaining

## Purpose

Orchestrate complete roadmap execution by chaining phases automatically. When one phase
completes successfully, the next phase starts without manual intervention.

## Inputs

- `$1` = Roadmap document path (e.g., `specs/IMPLEMENTATION_PLAN.md`)
- `--start-phase` = Phase to start from (default: first phase in roadmap)
- `--auto-continue` = Continue to next phase on success (default: `true`)
- `--run-id` = Run ID for the entire roadmap execution

## Execution Strategy

### 1. Parse Roadmap Document

Read the roadmap: `@$1`

Extract:
- `ROADMAP_ID` from the title or first H1
- Phase list and order from `## Phases` or `## Implementation Phases`
- Acceptance criteria per phase
- Phase document paths (relative to roadmap)

Expected format:
```markdown
# Implementation Roadmap: Feature X

## Phases

| Phase | Document | Description |
|-------|----------|-------------|
| P1 | plans/P1-core.md | Core infrastructure |
| P2 | plans/P2-api.md | API layer |
| P3 | plans/P3-ui.md | UI components |

## Acceptance Criteria

### P1
- [ ] Core services operational
- [ ] Unit tests passing

### P2
- [ ] API endpoints available
- [ ] Integration tests passing
```

Compute:
- `TOTAL_PHASES` = Number of phases in roadmap
- `START_PHASE` = `--start-phase` if provided, else first phase
- `RUN_ID` = `--run-id` if provided, else `ROADMAP-<YYYYMMDD-HHMMSS>`

### 2. Initialize Roadmap Execution

Setup observability:
```bash
REPO_ROOT=$(git rev-parse --show-toplevel)
LOG_DIR="$REPO_ROOT/.claude/run-logs"
LOG_PATH="$LOG_DIR/$RUN_ID-roadmap.jsonl"
REPORT_PATH="$REPO_ROOT/.claude/run-reports/$RUN_ID-roadmap.md"
mkdir -p "$LOG_DIR" "$(dirname "$REPORT_PATH")"
```

Log roadmap start:
```bash
"$REPO_ROOT/.claude/ai-dev-kit/scripts/log_event.sh" \
  "$LOG_PATH" "$RUN_ID" "-" "-" "-" \
  "roadmap_start" "ok" "" "0" "phases=$TOTAL_PHASES,start=$START_PHASE"
```

### 3. Execute Phase Loop

For each phase starting from `START_PHASE`:

```
CURRENT_PHASE=$START_PHASE
PHASE_INDEX=1

while [ $PHASE_INDEX -le $TOTAL_PHASES ]; do
  1. Load phase document path from roadmap
  2. Determine next phase (if any)
  3. Call /ai-dev-kit:execute-phase with phase doc
  4. Check result
  5. If success AND auto-continue AND more phases:
     - Log phase_chain_continue
     - Increment PHASE_INDEX
     - Continue loop
  6. If failure:
     - Log phase_chain_stop
     - Report failure with retry instructions
     - EXIT
done
```

### 4. Phase Execution Delegation

For each phase, spawn execute-phase:

```
/ai-dev-kit:execute-phase <phase-doc-path> <base-branch> \
  --run-id $RUN_ID-$PHASE_ID \
  --next-phase <next-phase-doc-path-if-any>
```

After execute-phase returns:
- Check if output contains `PHASE_COMPLETE_CONTINUE: <next-phase>`
- If yes AND `--auto-continue=true`: proceed to next phase
- If no: stop and report

### 5. Phase Transition Logging

On successful phase completion:
```bash
"$REPO_ROOT/.claude/ai-dev-kit/scripts/log_event.sh" \
  "$LOG_PATH" "$RUN_ID" "$PHASE_ID" "-" "-" \
  "phase_chain_continue" "ok" "" "0" "next=$NEXT_PHASE"
```

On phase failure:
```bash
"$REPO_ROOT/.claude/ai-dev-kit/scripts/log_event.sh" \
  "$LOG_PATH" "$RUN_ID" "$PHASE_ID" "-" "-" \
  "phase_chain_stop" "failed" "" "1" "reason=phase_failed"
```

### 6. Roadmap Completion

When all phases complete successfully:

1. Log roadmap completion:
   ```bash
   "$REPO_ROOT/.claude/ai-dev-kit/scripts/log_event.sh" \
     "$LOG_PATH" "$RUN_ID" "-" "-" "-" \
     "roadmap_complete" "ok" "" "0" "phases_completed=$TOTAL_PHASES"
   ```

2. Generate combined PR:
   - Aggregate PR drafts from all phases
   - Create summary of all changes
   - List all acceptance criteria met

3. Write roadmap report to `$REPORT_PATH`

### 7. Failure Handling

If any phase fails:

1. Stop execution immediately
2. Report which phase failed and why
3. Provide resume command:
   ```
   /ai-dev-kit:execute-roadmap $1 --start-phase=$FAILED_PHASE --run-id=$RUN_ID
   ```
4. List remaining phases not executed

## Output

### Success Output

```
ROADMAP_COMPLETE
Roadmap: <ROADMAP_ID>
Run ID: <RUN_ID>
Phases completed: P1, P2, P3
Total lanes: 12
All acceptance criteria met: Yes
PR draft: .claude/run-reports/<RUN_ID>-roadmap.md
```

### Failure Output

```
ROADMAP_STOPPED
Roadmap: <ROADMAP_ID>
Run ID: <RUN_ID>
Failed at: P2
Phases completed: P1
Remaining phases: P3
Reason: Cross-lane validation failed

Resume with:
/ai-dev-kit:execute-roadmap $1 --start-phase=P2 --run-id=<RUN_ID>
```

## Notes

- This command orchestrates phase-level chaining, not lane execution
- Each phase uses its own run-id suffix: `<ROADMAP_RUN_ID>-<PHASE_ID>`
- Cross-lane validation must pass before moving to next phase
- Use `--auto-continue=false` to pause between phases for manual review

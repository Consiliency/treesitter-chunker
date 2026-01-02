---
name: execute-phase
argument-hint: [phase-doc-path] [base-branch=current] [worktree-root=.worktrees] [max-parallel-lanes=4] [task-worktrees=auto] [run-id] [log-path=.claude/run-logs/<run-id>.jsonl] [checkpoint-path=.claude/ai-dev-kit/run-logs/checkpoints.json] [--resume] [--rollback] [--next-phase=<path>]
description: "Execute all swim lanes in a phase using isolated lane worktrees, optional per-task worktrees, serialized merge queue, and checkpointed resume/rollback."
allowed-tools: Read, Bash(git status:*), Bash(git branch:*), Bash(git rev-parse:*), Bash(git show-ref:*), Bash(git worktree:*), Bash(git checkout:*), Bash(git merge:*), Bash(git rebase:*), Bash(git log:*), Bash(git diff:*), Bash(git -C:*), Bash(mkdir:*), Bash(ls:*), Bash(date:*), Bash(printf:*), Bash(cat:*), Bash(.claude/ai-dev-kit/scripts/log_event.sh:*), Agent
---

# Execute Phase with Parallel Lane Orchestration

## Inputs
- `$1` = Phase document path (e.g., `plans/phase-2-ingestion.md`)
- `$2` (optional) = Base/integration branch to merge into (default: current branch)
- `$3` (optional) = Worktree root directory (default: `.worktrees/`)
- `$4` (optional) = Max parallel lanes (default: `4`)
- `$5` (optional) = Task worktrees mode: `off|auto|on` (default: `auto`)
- `$6` (optional) = Run ID for observability logs
- `$7` (optional) = Log path for JSONL run logs (default: `.claude/run-logs/<run-id>.jsonl`)
- `$8` (optional) = Checkpoint path (default: `.claude/ai-dev-kit/run-logs/checkpoints.json`)
- `--resume` (flag) = Resume the orchestrator state and ready lanes from the last checkpoint (idempotent)
- `--rollback` (flag) = Roll back the orchestrator and lane entries to the safest checkpoint (`before_lane_start`)
- `--next-phase` (optional) = Path to next phase document for roadmap chaining

## Execution Strategy

### 1. Load and Parse the Phase Plan

Read the phase document:
- `@$1`

Extract:
- `PHASE_ID` from the first H1 (e.g., `# P1: Core Infrastructure` -> `P1`)
- Interface freeze gates (`## Interface Freeze Gates`) and which are already complete (`[x]`)
- Lane list and dependencies:
  - Prefer `## Lane Index & Dependencies`
  - If missing, derive lanes from `## D. Swim Lanes` and warn that dependencies are ambiguous

Validate:
- `## H. Test Execution Plan` exists; if missing, stop and request a plan update.
- Every task in each lane includes `Task Type`, `Tests owned files`, and `Test command(s)`.
  - If any are missing, stop and request a plan update.

Compute:
- `BASE_BRANCH` = `$2` if provided else current branch
- `WORKTREE_ROOT` = `$3` if provided else `.worktrees`
- `MAX_PARALLEL_LANES` = `$4` if provided else `4`
- `TASK_WORKTREES` = `$5` if provided else `auto`
- `RUN_ID` = `$6` if provided else `<PHASE_ID>-<YYYYMMDD-HHMMSS>`
- If `--resume` is set, `RUN_ID` MUST match the checkpoint entry being resumed.

If `Lane Index & Dependencies` is missing:
- List derived lanes and stop unless the user confirms.
- Recommend adding a lane index for reliable parallel orchestration.

### 2. Validate Git Preconditions (Base Worktree)

- Repo root: run `git rev-parse --show-toplevel` and set `REPO_ROOT`.
- Current branch: run `git branch --show-current`.
- Base/integration branch:
  - If `$2` provided, treat it as the base branch.
  - Else base branch is the current branch.
- If `$2` is provided and current branch != `$2`: stop and check out the base branch first.
- Base worktree must be clean: run `git status --short`.
  - If dirty: stop. A dirty base worktree makes merges unsafe.

Ensure worktree root exists:
- Run `mkdir -p "<WORKTREE_ROOT>"`.

Ensure observability paths exist:
- Compute:
  - `LOG_DIR` = `<REPO_ROOT>/.claude/run-logs`
  - `LOG_PATH` = `$7` if provided else `<LOG_DIR>/<RUN_ID>.jsonl`
  - `REPORT_PATH` = `<REPO_ROOT>/.claude/run-reports/<RUN_ID>.md`
- `CHECKPOINT_PATH` = `$8` if provided else `<REPO_ROOT>/.claude/ai-dev-kit/run-logs/checkpoints.json`
- Run `mkdir -p "<LOG_DIR>" "<REPO_ROOT>/.claude/run-reports" "$(dirname "$CHECKPOINT_PATH")"` before any checkpoint writes.
- Ensure `CHECKPOINT_PATH` exists and defaults to `[]` when empty (see `protocols/recovery.md`): after creating the directory, run `test -s "$CHECKPOINT_PATH" || echo "[]" > "$CHECKPOINT_PATH"`.
- Use an absolute `LOG_PATH` so all worktrees append to the same file.
- Log format (JSONL, one line per event):
  - Required fields: `ts`, `run_id`, `phase`, `lane`, `task`, `event`, `status`
  - Optional fields: `cmd`, `exit_code`, `notes`
- Use the helper script: `<REPO_ROOT>/.claude/ai-dev-kit/scripts/log_event.sh`.
  - Do not hand-write JSON or use placeholders like `$(date ...)`.
- Append a `phase_start` event to `LOG_PATH` before spawning lanes.
  - Use `lane` and `task` values of `-` for phase-level events.

### 3. Build the Lane Execution Queue

For each lane from the Lane Index:
- Determine readiness:
  - All required gates (`IF-*`, `IF-XR-*`) must be `[x]`.
  - All dependent lanes must be completed.
- Maintain a queue of ready lanes, and a list of blocked lanes with reasons.
- Write or update a `before_lane_start` checkpoint for each ready lane with `status=ready`, base branch, and `resume_hint="/ai-dev-kit:execute-lane $1 <LANE_ID> --resume --run-id <RUN_ID>"`.
- On `--resume`, read the latest checkpoint for `(RUN_ID, PHASE_ID, LANE_ID)` to skip already-completed stages and revalidate cleanliness before dispatching a lane lead.

### 4. Spawn Lane Leads (Parallel, Up To `$4`)

For each ready lane (up to `$4` at a time), spawn the lane-lead subagent.

Use this template:
```
Use the lane-lead subagent to execute lane <LANE_ID> from <PHASE_ID>

Context:
- Phase doc: $1
- Phase ID: <PHASE_ID>
- Lane ID: <LANE_ID>
- Base branch: <BASE_BRANCH>
- Worktree root: <WORKTREE_ROOT>
- Task worktrees: <off|auto|on>
- Dependencies satisfied: [list]
- Run ID: <RUN_ID>
- Log path: <LOG_PATH>

Constraints:
- Create one lane worktree under <WORKTREE_ROOT>/<PHASE_ID>/<LANE_ID>
- If task worktrees are enabled, create task worktrees as siblings under:
  <WORKTREE_ROOT>/<PHASE_ID>/<LANE_ID>/tasks/<TASK_ID>
- Do not merge to base branch; report when lane branch is ready for merge
```

Track lane progress:
- completed (lane branch ready to merge)
- in progress
- blocked (missing dependencies or conflicts)
- After a lane-lead reports worktree creation, update `after_lane_start` checkpoints with worktree paths and branches.
- After lane verification/tests, update `after_lane_tests` checkpoints with test commands and exit codes.
- Immediately before handing off to the merge queue or PR creation, update `pre_pr` checkpoints with head SHA and target branch.
- `--rollback` must reuse the checkpoint data to reset to `before_lane_start`, clean any worktrees/branches, mark the checkpoint `rolled_back`, and print a user prompt describing the rollback and how to start fresh.

### 5. Merge Queue (Serialized)

When a lane-lead reports `LANE_READY_TO_MERGE`:

1. Ensure base worktree still clean:
   - Run `git status --short`.
2. Use the worktree-integrator subagent with `RUN_ID` and `LOG_PATH` to:
   - Rebase lane branch onto base
   - Merge into base (prefer `--ff-only`)
   - Remove lane worktree and branch
   - Log merge events using the run log path
3. Mark lane complete and unblock dependent lanes.

Important: merges are serialized. Only one lane is merged at a time.

### 5.5 Cross-Lane Validation (Post-Merge)

After ALL lanes have merged, run cross-lane validation:

1. Spawn `quality-gate-guardian` subagent for cross-validation:
   ```
   Use the quality-gate-guardian subagent to validate phase <PHASE_ID>

   Context:
   - Phase ID: <PHASE_ID>
   - Base branch: <BASE_BRANCH>
   - Merged lanes: [list of completed lanes]
   - Test plan: Read from phase doc ## H. Test Execution Plan
   - Run ID: <RUN_ID>
   - Log path: <LOG_PATH>
   ```

2. Run integration test commands from `## H. Test Execution Plan`:
   - Execute test commands marked as `cross-lane` or `integration`
   - Capture stdout, stderr, exit codes

3. If tests PASS:
   - Log `cross_lane_validation_pass` event
   - Update manifest with `validation_passed: true`
   - Proceed to phase completion

4. If tests FAIL:
   - Log `cross_lane_validation_fail` event with failing tests
   - Update manifest with `validation_passed: false`
   - Create fix task: `FIX-<PHASE_ID>-001`
   - Report failure and block phase completion
   - Provide retry instructions

5. Log validation event:
   ```bash
   "$REPO_ROOT/.claude/ai-dev-kit/scripts/log_event.sh" \
     "$LOG_PATH" "$RUN_ID" "$PHASE_ID" "-" "-" \
     "cross_lane_validation" "$STATUS" "$TEST_CMD" "$EXIT_CODE" "$NOTES"
   ```

### 6. Phase Completion Report

Provide a final summary:
- Lanes completed (with merge commits)
- Remaining blocked lanes and reasons
- Any interface gate issues
- Follow-up recommendations

Write a short run report to `REPORT_PATH` including:
- Phase ID, run ID, base branch
- Lanes completed and blocked
- Log path and any failures

Append a `phase_done` event to `LOG_PATH` after the report is written.

### Phase Chaining Output

If `--next-phase` was provided AND all lanes succeeded AND cross-lane validation passed:

Output this signal for the roadmap orchestrator:
```
PHASE_COMPLETE_CONTINUE: <next-phase-path>
```

This tells `/ai-dev-kit:execute-roadmap` to automatically proceed to the next phase.

If phase failed or validation failed:
```
PHASE_COMPLETE_STOP: <reason>
```

Log the chaining decision:
```bash
"$REPO_ROOT/.claude/ai-dev-kit/scripts/log_event.sh" \
  "$LOG_PATH" "$RUN_ID" "$PHASE_ID" "-" "-" \
  "phase_chain_signal" "ok" "" "0" "signal=CONTINUE,next=$NEXT_PHASE"
```

### Checkpointed Resume/Rollback Prompts

- On resume entry, print: `Checkpoint found at $CHECKPOINT_PATH for $RUN_ID (lane=$LANE_ID, stage=$STAGE). Continuing without re-creating worktrees.`
- On rollback entry, print: `Rollback to before_lane_start completed using $CHECKPOINT_PATH for $RUN_ID (lane=$LANE_ID). Re-run without --rollback to start clean.`
- Network failure detected. Saved checkpoint at $CHECKPOINT_PATH. Re-run with --resume $RUN_ID after connectivity is restored or use --rollback to return to before_lane_start.
- Tests failed; checkpoint stored at $CHECKPOINT_PATH (after_lane_tests). Resume with --resume $RUN_ID after fixes or use --rollback to clean the lane worktree.
- PR creation failed; checkpoint stored at $CHECKPOINT_PATH (pre_pr). Resume with --resume $RUN_ID once permissions/network recover or use --rollback to revert the lane branch safely.

## Notes

- This command orchestrates lane-level parallelism. It does not edit files directly.
- `task-worktrees=auto` enables per-task worktrees only when tasks are parallel and file-disjoint.
- If you need to run a single lane manually, use `/ai-dev-kit:execute-lane`.

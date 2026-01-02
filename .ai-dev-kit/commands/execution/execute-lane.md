---
name: execute-lane
argument-hint: [phase-doc-path] [swim-lane-id] [base-branch=current] [worktree-root=.worktrees] [task-worktrees=auto] [run-id] [log-path=.claude/run-logs/<run-id>.jsonl] [checkpoint-path=.claude/ai-dev-kit/run-logs/checkpoints.json] [--resume] [--rollback]
description: "Execute a swim lane inside an isolated git worktree (one worktree per lane), optionally using per-task worktrees, with checkpointed recovery, resume, rollback, and merge cleanup."
allowed-tools: Read, Bash(git status:*), Bash(git branch:*), Bash(git rev-parse:*), Bash(git show-ref:*), Bash(git worktree:*), Bash(git checkout:*), Bash(git merge:*), Bash(git rebase:*), Bash(git log:*), Bash(git diff:*), Bash(git -C:*), Bash(mkdir:*), Bash(ls:*), Bash(date:*), Bash(printf:*), Bash(.claude/ai-dev-kit/scripts/log_event.sh:*), Agent
---

# Execute Swim Lane with Parallel Sub-Agents

## Inputs
- `$1` = Phase document path (e.g., `plans/phase-2-ingestion.md`)
- `$2` = Swim lane identifier (e.g., `SL-1`, `lane-api-routes`, etc.)
- `$3` (optional) = Base/integration branch to merge into (default: current branch)
- `$4` (optional) = Worktree root directory (default: `.worktrees/`)
- `$5` (optional) = Task worktrees mode: `off|auto|on` (default: `auto`)
- `$6` (optional) = Run ID for observability logs
- `$7` (optional) = Log path for JSONL run logs (default: `.claude/run-logs/<run-id>.jsonl`)
- `$8` (optional) = Checkpoint path for recovery state (default: `.claude/ai-dev-kit/run-logs/checkpoints.json`)
- `--resume` (flag) = Resume from the latest checkpoint for this `(run_id, phase, lane)` tuple (idempotent re-entry)
- `--rollback` (flag) = Rollback to the last safe checkpoint (before_lane_start) and mark the run as `rolled_back`

## Execution Strategy

### 1. Load Phase Plan and Extract Swim Lane

Read the phase implementation document:
- `@$1`

Locate swim lane `$2` within the document. Extract:
- Swim lane scope: component boundaries, files, interfaces owned
- Task list: individual work items with dependencies, task types, and test commands
- Interface contracts: frozen interfaces this lane depends on or provides
- Acceptance criteria: definition of done for this lane

If any task is missing `Task Type`, `Tests owned files`, or `Test command(s)`, stop and
request a plan update.

### 2. Verify Preconditions (Before Any Worktree Creation)

Before spawning agents, check:

Interface dependencies:
- All interfaces this lane consumes must be frozen (have `IF-*` gate marked complete).
- If any dependency is not ready, list them and stop with message:
```
  Cannot proceed - waiting on interface freeze gates:
  - IF-0-xyz: [description]

  Recommend: Execute dependent lanes first or request interface definition.
```

Git state:
- Repo root: run `git rev-parse --show-toplevel`.
- Current branch: run `git branch --show-current`.
- Base/integration branch:
  - If `$3` provided, treat it as the base branch name.
  - Else base branch is the current branch.
- If `$3` is provided and the current branch is not `$3`, stop and check out the base branch
  first (to ensure merges land in the intended branch).
- Check for uncommitted changes in the base worktree: run `git status --short`.
  - If dirty: stop. A dirty base worktree makes merges and cleanup unsafe.

File conflicts:
- Check if any files in this lane's scope are already modified in working tree.
  - This should be empty if base worktree is clean. If not, stop.

Observability (run logs):
- `REPO_ROOT` = repo root path from `git rev-parse --show-toplevel`.
- `RUN_ID` = `$6` if provided else `<PHASE_ID>-<LANE_ID>-<YYYYMMDD-HHMMSS>`.
- `LOG_DIR` = `<REPO_ROOT>/.claude/run-logs`.
- `LOG_PATH` = `$7` if provided else `<LOG_DIR>/<RUN_ID>.jsonl`.
- Ensure the log directory exists: run `mkdir -p "<LOG_DIR>"`.
- Use an absolute `LOG_PATH` so worktrees append to the same file.
- Log format (JSONL, one line per event):
  - Required fields: `ts`, `run_id`, `phase`, `lane`, `task`, `event`, `status`
  - Optional fields: `cmd`, `exit_code`, `notes`
- Use the helper script: `<REPO_ROOT>/.claude/ai-dev-kit/scripts/log_event.sh`.
  - Do not hand-write JSON or use placeholders like `$(date ...)`.
- Append `lane_start` before spawning tasks and `lane_ready_to_merge` when lane work is
  complete.
- Checkpoints (see `protocols/recovery.md`):
  - `CHECKPOINT_PATH` = `$8` if provided else `<REPO_ROOT>/.claude/ai-dev-kit/run-logs/checkpoints.json`.
  - Ensure the file exists with valid JSON (write `[]` if missing or empty): `mkdir -p "$(dirname "$CHECKPOINT_PATH")"` then `test -s "$CHECKPOINT_PATH" || echo "[]" > "$CHECKPOINT_PATH"`.
  - Persist checkpoints at `before_lane_start`, `after_lane_start`, `after_lane_tests`, and `pre_pr`.
  - Each record MUST replace the existing `(run_id, phase, lane, stage)` entry to keep re-entry idempotent.
  - Include `resume_hint="/ai-dev-kit:execute-lane $1 $2 --resume --run-id $RUN_ID"` and `rollback_hint="/ai-dev-kit:execute-lane $1 $2 --rollback --run-id $RUN_ID"` in the record.
  - On startup with `--resume` or `--rollback`, load the latest checkpoint for `(RUN_ID, PHASE_ID, LANE_ID)` and print a user prompt with the stage, checkpoint path, and next actions.

### 3. Create or Reuse an Isolated Lane Worktree

Goal: implement lane `$2` without interfering with other lanes by using:
- a dedicated branch for the lane, and
- a dedicated git worktree directory for that branch.

Derive identifiers

From the phase document (`@$1`), extract:
- `PHASE_ID` from the first H1 (example: `# P1: Core Infrastructure` -> `PHASE_ID=P1`).

All commands below use placeholders like `<PHASE_ID>`; substitute with your computed values
before running.

Compute:
- `BASE_BRANCH` = `$3` if provided else current branch (run `git branch --show-current`).
- `LANE_ID` = `$2`.
- `LANE_BRANCH` = `lane/<PHASE_ID>/<LANE_ID>`.
- `WORKTREE_ROOT` = `$4` if provided else `.worktrees`.
- `WORKTREE_PATH` = `<WORKTREE_ROOT>/<PHASE_ID>/<LANE_ID>`.

Create or reuse the worktree

1. Ensure worktree root exists:
   - Run `mkdir -p "<WORKTREE_ROOT>/<PHASE_ID>"`.
2. If the lane branch exists:
   - If `WORKTREE_PATH` already exists and is a git worktree: reuse it.
   - Else add the worktree for the existing branch:
     - Run `git worktree add "<WORKTREE_PATH>" "<LANE_BRANCH>"`.
3. If the lane branch does not exist:
   - Create it from `BASE_BRANCH` and add the worktree:
     - Run `git worktree add -b "<LANE_BRANCH>" "<WORKTREE_PATH>" "<BASE_BRANCH>"`.

Verify worktree cleanliness

- Confirm the lane worktree is clean before spawning agents:
  - Run `git -C "<WORKTREE_PATH>" status --short`.
  - If dirty: stop and fix (stash/commit/clean) before continuing.

Important

- All sub-agents spawned for this lane must run inside `WORKTREE_PATH`.
- Do not merge into `BASE_BRANCH` until lane work is verified and rebased onto the latest base.
- Before creating worktrees, write the `before_lane_start` checkpoint with `status=ready` and base/branch metadata. When resuming and this checkpoint already exists, skip rewriting it.
- After the worktree(s) are created, write the `after_lane_start` checkpoint with branch/worktree paths. On `--resume`, reuse this checkpoint to skip worktree creation while re-validating cleanliness.

### 4. Task Dependency Analysis

From the task list for lane `$2`:
- Build dependency graph (which tasks can run in parallel vs sequential).
- Identify tasks with no dependencies (ready tasks).
- Group related tasks that should execute sequentially in one agent.
- Enforce ordering by task type: `test` -> `impl` -> `verify` (respecting explicit dependencies).

Grouping heuristics:
- Tasks touching the same file -> same agent (sequential)
- Tasks with direct data dependencies -> same agent (sequential)
- Tasks on different files with no dependencies -> parallel agents
- Avoid creating more than 5 parallel agents (diminishing returns)

Task worktrees mode (`$5`):
- `off`: run all tasks sequentially in the lane worktree.
- `auto`: if tasks are parallel-capable and file-disjoint, use per-task worktrees.
- `on`: always use per-task worktrees (one per task or task group).

### 4b. Optional: Task Worktrees for Parallel Tasks

If you decide to run tasks in parallel, use per-task worktrees to avoid conflicts.

Task worktree conventions:
- Branch: `lane-task/<PHASE_ID>/<LANE_ID>/<TASK_ID>`
- Worktree: `<WORKTREE_ROOT>/<PHASE_ID>/<LANE_ID>/tasks/<TASK_ID>`

Create a task worktree:
```
git worktree add -b "<TASK_BRANCH>" "<TASK_WORKTREE>" "<LANE_BRANCH>"
```

After task completion (in the lane worktree = `<WORKTREE_PATH>`):
```
git -C "<WORKTREE_PATH>" merge --no-ff "<TASK_BRANCH>"
git worktree remove "<TASK_WORKTREE>"
git branch -d "<TASK_BRANCH>"
```

### 5. Spawn Sub-Agents for Tasks (Worktree-Scoped)

For each task or task group:

Use the `test-engineer` subagent for `Task Type: test|verify` tasks.

Use the `lane-executor` subagent for `Task Type: impl` tasks.

Spawn with context:
```
Use the lane-executor subagent to implement [task description]

Context:
- Phase: [phase name from $1]
- Phase ID: [PHASE_ID]
- Swim Lane: $2
- Task ID: [task-id]
- Task Type: [test|impl|verify]
- Worktree path: [WORKTREE_PATH] (lane or task)
- Branch: [LANE_BRANCH]
- Files in scope: [list]
- Interfaces to implement: [list with signatures]
- Interfaces to consume: [list with usage notes]
- Acceptance criteria: [specific criteria for this task]
- Run ID: [RUN_ID]
- Log path: [LOG_PATH]

Constraints:
- Do not modify files outside this task's scope
- Do not change interface signatures (they are frozen)
- Do all work inside the worktree directory [WORKTREE_PATH]
- Follow existing code patterns in adjacent files
- Write tests for new functionality unless the plan assigns tests to Task Type: test tasks
- Commit work with message: "feat(<PHASE_ID>-<LANE_ID>): [task description]"

If you encounter blockers, report them and pause for guidance.
```

For parallel agents:
- Track spawned agent IDs.
- Monitor for completion or blockers.
- Handle conflicts if agents touch overlapping concerns (should be rare with good task division).

### 6. Progress Monitoring

Track:
- Completed tasks (agent finished successfully)
- In-progress tasks (agent still working)
- Blocked tasks (agent reported blocker)
- Failed tasks (agent encountered error)

Report progress after each task group completes.

### 7. Integration and Verification

After all agents complete:

Integration checks:
- Run full test suite for this swim lane's components.
- Verify interface contracts match specifications.
- Check for any introduced file conflicts.
- Validate all acceptance criteria met.

If issues found:
- Spawn additional lane-executor agent to fix specific issues.
- Re-run verification.

If all pass:
- Rebase lane branch onto the latest base branch.
- Merge lane branch into base (prefer fast-forward).
- Remove the lane worktree and branch.
- Update the phase document to mark the lane complete.

### 8. Completion Report

Provide summary:
- Tasks executed and their commit hashes
- Interfaces implemented
- Files modified
- Tests run and results
- Next steps for dependent lanes

### Checkpointed Execution Flow

- On new runs, emit a prompt: `Checkpoint saved at $CHECKPOINT_PATH (before_lane_start). Resume with --resume --run-id $RUN_ID; rollback with --rollback.`.
- On `--resume`, print `Checkpoint found at $CHECKPOINT_PATH for $RUN_ID/$LANE_ID (stage=$STAGE). Resuming without recreating worktrees.` and continue from the recorded stage.
- On `--rollback`, reset to the `before_lane_start` checkpoint, clean worktrees/branches, mark the checkpoint `rolled_back`, and prompt: `Rollback complete to before_lane_start. Re-run without --rollback to start fresh.`.
- Update `after_lane_tests` checkpoints immediately after executing the lane test suite, including `test_cmd` and `exit_code` in the `notes`.
- Update `pre_pr` checkpoints before merge/PR actions with head SHA, target branch, and ready-to-merge status.

## Error Recovery Procedures

### Failure Scenario Prompts (Checkpoint Aware)

- Network failure detected. Saved checkpoint at $CHECKPOINT_PATH. Re-run with --resume $RUN_ID after connectivity is restored or use --rollback to return to before_lane_start.
- Tests failed; checkpoint stored at $CHECKPOINT_PATH (after_lane_tests). Resume with --resume $RUN_ID after fixes or use --rollback to clean the lane worktree.
- PR creation failed; checkpoint stored at $CHECKPOINT_PATH (pre_pr). Resume with --resume $RUN_ID once permissions/network recover or use --rollback to revert the lane branch safely.

### Worktree Creation Failure

If `git worktree add` fails:

```bash
# Check if worktree already exists but is corrupted
git worktree list | grep "<WORKTREE_PATH>"

# If listed but missing on disk, remove the stale entry
git worktree remove --force "<WORKTREE_PATH>"

# If branch exists but worktree doesn't, recreate
git worktree add "<WORKTREE_PATH>" "<LANE_BRANCH>"

# If both exist and are valid, reuse
cd "<WORKTREE_PATH>" && git status
```

Log the recovery:
```bash
"$REPO_ROOT/.claude/ai-dev-kit/scripts/log_event.sh" \
  "$LOG_PATH" "$RUN_ID" "$PHASE_ID" "$LANE_ID" "-" \
  "worktree_recovery" "ok" "" "" "Recreated stale worktree"
```

### Agent Failure Mid-Task

If an agent fails or times out:

1. Log the failure:
```bash
"$REPO_ROOT/.claude/ai-dev-kit/scripts/log_event.sh" \
  "$LOG_PATH" "$RUN_ID" "$PHASE_ID" "$LANE_ID" "$TASK_ID" \
  "task_failed" "error" "" "" "Agent timeout after 30 minutes"
```

2. Check worktree state:
```bash
git -C "<WORKTREE_PATH>" status --short
git -C "<WORKTREE_PATH>" log --oneline -5
```

3. Recovery options:
   - If work was committed: continue with next task
   - If work is uncommitted but valid: commit it and continue
   - If work is broken: reset to last commit and retry
   ```bash
   git -C "<WORKTREE_PATH>" reset --hard HEAD
   ```

4. Resume the agent or spawn a new one with the same task

### Merge Conflict During Task Branch Merge

If `git merge` fails with conflicts:

1. Log the conflict:
```bash
"$REPO_ROOT/.claude/ai-dev-kit/scripts/log_event.sh" \
  "$LOG_PATH" "$RUN_ID" "$PHASE_ID" "$LANE_ID" "$TASK_ID" \
  "merge_conflict" "blocked" "git merge $TASK_BRANCH" "1" \
  "Conflicting files: $(git -C "$WORKTREE_PATH" diff --name-only --diff-filter=U)"
```

2. Abort the merge:
```bash
git -C "<WORKTREE_PATH>" merge --abort
```

3. Investigate the conflict:
   - Which files are conflicting?
   - Are they in the task's scope?
   - Did another task modify them incorrectly?

4. Resolution options:
   - If caused by parallel task overlap: run tasks sequentially instead
   - If caused by stale base: rebase task branch and retry
   ```bash
   git -C "<TASK_WORKTREE>" rebase "<LANE_BRANCH>"
   ```
   - If genuine conflict: spawn lane-executor to resolve

### Lane Verification Failure

If integration tests fail after all tasks complete:

1. Log the failure:
```bash
"$REPO_ROOT/.claude/ai-dev-kit/scripts/log_event.sh" \
  "$LOG_PATH" "$RUN_ID" "$PHASE_ID" "$LANE_ID" "-" \
  "lane_verification_failed" "error" "$TEST_CMD" "$EXIT_CODE" \
  "$(tail -20 test-output.log)"
```

2. Analyze the failure:
   - Which tests failed?
   - Which tasks touched those areas?
   - Is it a test bug or implementation bug?

3. Recovery options:
   - Spawn lane-executor to fix the specific issue
   - If test is wrong, spawn test-engineer to fix it
   - After fix, re-run verification

4. Do NOT merge to base until verification passes

---

## Cleanup Procedures

### Successful Lane Completion

After lane merges successfully:

```bash
# Remove lane worktree
git worktree remove "<WORKTREE_PATH>"

# Delete lane branch (it's merged)
git branch -d "<LANE_BRANCH>"

# Clean up any task worktrees that weren't removed
for tw in "<WORKTREE_ROOT>/<PHASE_ID>/<LANE_ID>/tasks/"*; do
  git worktree remove "$tw" 2>/dev/null || true
done

# Delete task branches
git branch --list "lane-task/<PHASE_ID>/<LANE_ID>/*" | xargs -r git branch -d
```

### Aborted Lane Execution

If lane is abandoned mid-execution:

```bash
# Remove all task worktrees for this lane
for tw in "<WORKTREE_ROOT>/<PHASE_ID>/<LANE_ID>/tasks/"*; do
  git worktree remove --force "$tw" 2>/dev/null || true
done

# Delete task branches (force since not merged)
git branch --list "lane-task/<PHASE_ID>/<LANE_ID>/*" | xargs -r git branch -D

# Remove lane worktree
git worktree remove --force "<WORKTREE_PATH>"

# Optionally keep or delete lane branch depending on whether to resume later
# To delete: git branch -D "<LANE_BRANCH>"
# To keep for resume: leave it
```

Log the abort:
```bash
"$REPO_ROOT/.claude/ai-dev-kit/scripts/log_event.sh" \
  "$LOG_PATH" "$RUN_ID" "$PHASE_ID" "$LANE_ID" "-" \
  "lane_aborted" "error" "" "" "User requested abort"
```

### Orphaned Worktree Cleanup

Periodically clean orphaned worktrees:

```bash
# List all worktrees and check for stale entries
git worktree list --porcelain | grep "worktree" | while read -r _ path; do
  if [ ! -d "$path" ]; then
    echo "Stale worktree: $path"
    git worktree remove --force "$path" 2>/dev/null || true
  fi
done

# Prune definitely-stale entries
git worktree prune
```

---

## Rollback Procedures

### Rollback a Merged Lane

If a lane was merged but needs to be reverted:

```bash
# Find the merge commit
MERGE_COMMIT=$(git log --oneline --merges -1 --grep="<LANE_ID>")

# Revert the merge
git revert -m 1 "$MERGE_COMMIT"

# Log the rollback
"$REPO_ROOT/.claude/ai-dev-kit/scripts/log_event.sh" \
  "$LOG_PATH" "$RUN_ID" "$PHASE_ID" "$LANE_ID" "-" \
  "lane_rollback" "ok" "git revert $MERGE_COMMIT" "0" "Lane reverted due to issues"
```

### Rollback to Pre-Lane State

If multiple lanes need rollback:

```bash
# Find the commit before any lane work started
PRE_LANE_COMMIT=$(git log --oneline --before="<RUN_START_TIME>" -1)

# Create a new branch from that point
git checkout -b "rollback-$RUN_ID" "$PRE_LANE_COMMIT"

# Cherry-pick any commits you want to keep
# git cherry-pick <good-commit>
```

---

## Interface Gate Validation

### Gate Checking Pseudocode

Before spawning any agents, validate interface gates:

```
FOR each interface in lane.interfaces_consumed:
  gate_id = "IF-*-" + interface.id
  gate_status = parse_gate_checkbox(phase_doc, gate_id)

  IF gate_status != "checked":
    blocked_gates.append(gate_id)

IF blocked_gates.not_empty():
  log_event("gate_check_failed", "blocked", notes=blocked_gates)
  STOP with message:
    "Cannot proceed - waiting on interface freeze gates:
     - {blocked_gates}
     Recommend: Execute dependent lanes first or request interface definition."
ELSE:
  log_event("gate_check_passed", "ok")
  CONTINUE
```

### Gate Parsing

Parse gate checkboxes from phase document:

```markdown
## Interface Freeze Gates

- [x] IF-0-P1-AUTH: Authentication service interface
- [ ] IF-0-P1-SESSION: Session management interface  <- NOT READY
- [x] IF-1-P1-EMAIL: Email service interface
```

Regex pattern: `- \[([ x])\] (IF-[0-9XR]+-[A-Z0-9-]+):`

---

## Notes

- This command orchestrates; the `lane-executor` and `test-engineer` subagents do the actual coding.
- Ideal swim lanes have 2 to 8 tasks each (too few = underutilized parallelism; too many = overhead).
- If a lane has more than 10 tasks, consider running command multiple times on task subgroups.
- Resume capability: if interrupted, you can resume individual agents by their IDs.
- Always prefer cleanup over accumulating stale worktrees and branches.
- Log all significant events for post-mortem analysis.

---
name: recovery-protocol
version: "1.0"
description: "Checkpoint and recovery contract for execute-lane and execute-phase runs."
applies-to:
  - commands/execution/execute-lane
  - commands/execution/execute-phase
---

# Recovery Contract

All execution commands MUST persist checkpoints to allow safe resumption and rollback. Checkpoints are stored in:

- Path: `.claude/ai-dev-kit/run-logs/checkpoints.json`
- Format: JSON array. Create the file with `[]` if it does not exist.
- Update strategy: replace the record matching `(run_id, phase, lane, stage)` to keep runs idempotent.

## Required Checkpoints

- **before_lane_start**: After preconditions pass, before creating or modifying any worktrees.
- **after_lane_start**: Immediately after lane worktree (and task worktrees if enabled) are created and branches checked out.
- **after_lane_tests**: After lane test suites execute, capturing the test command and exit code.
- **pre_pr**: Just before PR or merge actions, recording commit SHAs and target branch.

## Checkpoint Schema

- `run_id`: Stable identifier used across resume/rollback.
- `phase`: Phase identifier (e.g., `P1`).
- `lane`: Lane identifier (e.g., `SL-1`, or `-` for phase-level).
- `stage`: One of `before_lane_start|after_lane_start|after_lane_tests|pre_pr|retry_attempt`.
- `status`: `ready|in_progress|failed|blocked|complete|rolled_back|retrying`.
- `base_branch`: Integration branch for the run.
- `worktree_path`: Absolute path for the lane worktree.
- `log_path`: Absolute path to the JSONL run log.
- `timestamp`: ISO-8601 UTC timestamp of the checkpoint write.
- `notes`: Free-form context (e.g., last command, blocking dependency).
- `resume_hint`: Shell-friendly command showing how to resume with `--resume`.
- `rollback_hint`: Shell-friendly command showing how to rollback with `--rollback`.
- `retry_attempt`: (optional) Current retry attempt number (1-based).
- `max_retries`: (optional) Maximum retries configured for this lane.
- `failure_context`: (optional) Array of error messages from previous attempts.

## Resume and Rollback Expectations

- `--resume` MUST rehydrate state from the latest checkpoint for the `(run_id, phase, lane)` tuple and skip completed steps (idempotent re-entry).
- `--rollback` MUST reset the worktree/branch to the safest prior checkpoint stage, mark the checkpoint `rolled_back`, and surface the `rollback_hint`.
- On resume or rollback, commands MUST print a user prompt that includes:
  - current stage
  - checkpoint path
  - next actions for resume
  - how to rollback to `before_lane_start`

## Automatic Retry Behavior

When a lane has `retries > 0` configured, the execution engine will automatically retry on failure:

1. **On failure**: Checkpoint with `stage=retry_attempt`, `status=retrying`
2. **Capture context**: Store error message and last 5 log entries in `failure_context`
3. **Increment attempt**: Update `retry_attempt` counter
4. **Re-invoke runner**: Pass `failure_context` to help the agent learn from mistakes
5. **Max retries reached**: If `retry_attempt > max_retries`, set `status=failed` and stop

### Retry Checkpoint Example

```json
{
  "run_id": "P1-SL-AUTH-20251227",
  "phase": "P1",
  "lane": "SL-AUTH",
  "stage": "retry_attempt",
  "status": "retrying",
  "retry_attempt": 2,
  "max_retries": 3,
  "failure_context": [
    "Attempt 1: TypeError: undefined is not a function",
    "Test failed: AuthService.register"
  ],
  "timestamp": "2025-12-27T10:30:00Z"
}
```

## Failure Scenarios

- **Network failure**: Persist checkpoint with `status=failed`, include last attempted command, and prompt to rerun with `--resume` after connectivity returns or `--rollback` to revert to `before_lane_start`.
- **Test failure**: Persist checkpoint at `after_lane_tests` with the failing test command and exit code. If `retries > 0`, auto-retry with failure context. Otherwise, prompt to resume after fixes or rollback.
- **PR creation failure**: Persist checkpoint at `pre_pr` with merge target and head SHA, prompt to resume once permissions/network issues are resolved, or rollback the lane branch safely.
- **Retry exhausted**: Persist checkpoint with `status=failed`, `retry_attempt=max_retries`, and full `failure_context` array. Prompt for manual intervention.

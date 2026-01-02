---
name: lane-result-manifest
version: "1.0"
description: "Specification for artifacts produced when executing a single swim lane."
applies-to:
  - /ai-dev-kit:execute-lane
  - /ai-dev-kit:execute-phase
  - automated validation harnesses
---

# Lane Result Manifest

## Purpose

Define the minimum set of artifacts a lane execution must generate so downstream tools
(merge queue, validation reports, observability dashboards) can consume consistent data.

## Required Artifacts

1. **Git commit**
   - Message format: `feat(<PHASE_ID>-<LANE_ID>): <lane name>`
   - Contains only files owned by the lane scope
   - Working tree is clean after the commit

2. **PR summary template**
   - Location: `.ai-dev-kit/pr-body-template.md`
   - Section heading: `## <PHASE_ID> / <LANE_ID> - <lane name>`
   - Includes:
     - Summary line (what changed)
     - Commit reference (message or SHA)
     - Test bullet list with pass/fail status and command text

3. **Run logs**
   - Location: `.claude/run-logs/<PHASE_ID>-<LANE_ID>.jsonl`
   - JSONL entries are append-only, one per event
   - Required fields: `ts`, `event`, `phase`, `lane`
   - Common events:
     - `lane_start` with `run_id`
     - `task_written` with `task` and `path`
     - `test_command` with `cmd`, `status`, `stdout`, `stderr`
     - `commit` with `message`
     - `pr_body_updated` with `path`
     - `lane_complete` with `run_id`

## Manifest Consumption Rules

- **Deduplicate by heading**: if a section for a lane already exists in the PR template,
  update it instead of appending a duplicate block.
- **Validate commit hygiene**: reject the manifest if a dirty working tree remains after
  execution or if the commit message is missing the phase/lane prefix.
- **Preserve ordering**: run logs must reflect chronological execution to support
  observability playback and flake triage.

## Example

- Commit: `feat(P0-SL-1): Core Artifact Lane`
- PR template section:
  ```
  ## P0 / SL-1 - Core Artifact Lane
  - Summary: Writes the primary artifact and validates the contents end-to-end.
  - Commit: feat(P0-SL-1): Core Artifact Lane
  - Tests:
    - `python scripts/run_lane_tests.py --target artifacts/lane-1.txt --expect "Lane SL-1 completed"` → ok
  ```
- Run log file: `.claude/run-logs/P0-SL-1.jsonl` containing the event sequence above.

## Cross-Lane Validation (Post-Merge)

After all lanes merge, the phase manifest includes validation results:

### Validation Schema

```json
{
  "phase_id": "P1",
  "cross_lane_validation": {
    "ran": true,
    "passed": false,
    "timestamp": "2025-12-27T10:30:00Z",
    "test_commands": [
      {
        "cmd": "pytest tests/integration/",
        "exit_code": 1,
        "failing_tests": ["test_auth_integration", "test_api_e2e"]
      }
    ],
    "fix_task_created": "FIX-P1-001",
    "errors": ["Cross-lane validation failed"]
  }
}
```

### Validation Fields

| Field | Type | Description |
|-------|------|-------------|
| `ran` | bool | Whether validation was executed |
| `passed` | bool | Whether all validation tests passed |
| `timestamp` | string | ISO-8601 timestamp of validation run |
| `test_commands` | array | Commands executed with results |
| `failing_tests` | array | Names of failing test cases |
| `fix_task_created` | string | ID of fix task if validation failed |
| `errors` | array | Error messages from validation |

### Validation Behavior

1. **After all lanes merge**: Run integration tests across combined code
2. **If tests pass**: `passed=true`, phase can proceed
3. **If tests fail**: `passed=false`, create fix task, block phase completion
4. **Fix task**: New lane task to address integration failures

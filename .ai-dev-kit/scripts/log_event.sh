#!/usr/bin/env bash
#
# log_event.sh - JSONL event logger for run observability
#
# Usage:
#   log_event.sh <LOG_PATH> <RUN_ID> <PHASE> <LANE> <TASK> <EVENT> <STATUS> [CMD] [EXIT_CODE] [NOTES]
#
# Events:
#   phase_start, phase_done
#   lane_start, lane_ready_to_merge, lane_blocked
#   task_start, task_done, task_blocked
#   test_start, test_done
#   gate_check, gate_frozen
#
# Status values:
#   ok, error, blocked, skipped
#
# Example:
#   log_event.sh /tmp/run.jsonl "P1-A-20251221" "P1" "A" "A1" "task_start" "ok"
#   log_event.sh /tmp/run.jsonl "P1-A-20251221" "P1" "A" "A1" "task_done" "ok" "npm test" "0"
#   log_event.sh /tmp/run.jsonl "P1-A-20251221" "P1" "-" "-" "phase_start" "ok"

set -euo pipefail

LOG_PATH="${1:-}"
RUN_ID="${2:-}"
PHASE="${3:-}"
LANE="${4:-}"
TASK="${5:-}"
EVENT="${6:-}"
STATUS="${7:-}"
CMD="${8:-}"
EXIT_CODE="${9:-}"
NOTES="${10:-}"

# Validate required fields
if [[ -z "$LOG_PATH" || -z "$RUN_ID" || -z "$PHASE" || -z "$LANE" || -z "$TASK" || -z "$EVENT" || -z "$STATUS" ]]; then
    echo "Usage: log_event.sh <LOG_PATH> <RUN_ID> <PHASE> <LANE> <TASK> <EVENT> <STATUS> [CMD] [EXIT_CODE] [NOTES]" >&2
    echo "Required: LOG_PATH, RUN_ID, PHASE, LANE, TASK, EVENT, STATUS" >&2
    exit 1
fi

# Generate UTC timestamp
TS=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# Escape JSON strings (handle quotes and backslashes)
json_escape() {
    local str="$1"
    # Escape backslashes first, then quotes, then newlines
    str="${str//\\/\\\\}"
    str="${str//\"/\\\"}"
    str="${str//$'\n'/\\n}"
    str="${str//$'\r'/\\r}"
    str="${str//$'\t'/\\t}"
    printf '%s' "$str"
}

# Build JSON object
JSON="{\"ts\":\"$TS\",\"run_id\":\"$(json_escape "$RUN_ID")\",\"phase\":\"$(json_escape "$PHASE")\",\"lane\":\"$(json_escape "$LANE")\",\"task\":\"$(json_escape "$TASK")\",\"event\":\"$(json_escape "$EVENT")\",\"status\":\"$(json_escape "$STATUS")\""

# Add optional fields if provided
if [[ -n "$CMD" ]]; then
    JSON+=",\"cmd\":\"$(json_escape "$CMD")\""
fi

if [[ -n "$EXIT_CODE" ]]; then
    JSON+=",\"exit_code\":$EXIT_CODE"
fi

if [[ -n "$NOTES" ]]; then
    JSON+=",\"notes\":\"$(json_escape "$NOTES")\""
fi

JSON+="}"

# Ensure log directory exists
LOG_DIR=$(dirname "$LOG_PATH")
mkdir -p "$LOG_DIR"

# Append to log file (atomic write with lock)
{
    flock -x 200
    echo "$JSON" >> "$LOG_PATH"
} 200>"${LOG_PATH}.lock"

# Also echo for caller visibility (stderr to not pollute stdout)
echo "$JSON" >&2

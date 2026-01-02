# Run Log Event Format

Standard event format for ai-dev-kit observability.

## Event Structure

All events follow this base structure:

```json
{
  "timestamp": "2025-01-15T10:30:00.000Z",
  "event_type": "tool_call",
  "session_id": "abc123",
  "agent_name": "lane-executor",
  "lane_id": "auth-feature",
  "phase_id": "phase-1",
  "task_id": "task-001",
  "payload": { ... }
}
```

## Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `timestamp` | ISO 8601 | Event time |
| `event_type` | EventType | Event classification |
| `session_id` | string | Claude Code session identifier |

## Optional Context Fields

| Field | Type | Description |
|-------|------|-------------|
| `agent_name` | string | Agent that generated event |
| `lane_id` | string | Swim lane identifier |
| `phase_id` | string | Phase identifier |
| `task_id` | string | Task identifier |
| `payload` | object | Event-specific data |

## Event Types

### Workflow Events

#### `workflow_start`

```json
{
  "event_type": "workflow_start",
  "agent_name": "parallel-researcher",
  "payload": {
    "workflow": "extensive-research",
    "skill": "research",
    "query": "WebSocket authentication"
  }
}
```

#### `workflow_complete`

```json
{
  "event_type": "workflow_complete",
  "agent_name": "parallel-researcher",
  "payload": {
    "workflow": "extensive-research",
    "duration_ms": 45000,
    "status": "success"
  }
}
```

### Lane Execution Events

#### `lane_start`

```json
{
  "event_type": "lane_start",
  "lane_id": "auth-core",
  "phase_id": "phase-1",
  "payload": {
    "task_count": 5,
    "worktree_path": "/tmp/worktree-auth-core"
  }
}
```

#### `lane_complete`

```json
{
  "event_type": "lane_complete",
  "lane_id": "auth-core",
  "phase_id": "phase-1",
  "payload": {
    "tasks_completed": 5,
    "tasks_failed": 0,
    "duration_ms": 120000,
    "merged": true
  }
}
```

### Task Events

#### `task_start`

```json
{
  "event_type": "task_start",
  "task_id": "task-001",
  "lane_id": "auth-core",
  "payload": {
    "description": "Implement OAuth2 token validation",
    "files": ["src/auth/validator.ts"]
  }
}
```

#### `task_complete`

```json
{
  "event_type": "task_complete",
  "task_id": "task-001",
  "lane_id": "auth-core",
  "payload": {
    "status": "success",
    "files_modified": ["src/auth/validator.ts"],
    "tests_passed": true,
    "duration_ms": 30000
  }
}
```

### Agent Lifecycle Events

#### `agent_start`

```json
{
  "event_type": "agent_start",
  "agent_name": "researcher-web-1",
  "payload": {
    "subagent_type": "general-purpose",
    "model": "haiku",
    "prompt_preview": "Research WebSocket auth..."
  }
}
```

#### `agent_end`

```json
{
  "event_type": "agent_end",
  "agent_name": "researcher-web-1",
  "payload": {
    "status": "completed",
    "duration_ms": 15000,
    "tokens_used": 1234
  }
}
```

### Verification Events

#### `verification_pass`

```json
{
  "event_type": "verification_pass",
  "task_id": "task-001",
  "lane_id": "auth-core",
  "payload": {
    "check": "unit_tests",
    "details": "All 12 tests passed"
  }
}
```

#### `verification_fail`

```json
{
  "event_type": "verification_fail",
  "task_id": "task-001",
  "lane_id": "auth-core",
  "payload": {
    "check": "type_check",
    "error": "Property 'token' missing in type 'AuthRequest'"
  }
}
```

### Research Events

#### `research_synthesis`

```json
{
  "event_type": "research_synthesis",
  "agent_name": "parallel-researcher",
  "payload": {
    "mode": "extensive",
    "agents_launched": 8,
    "agents_responded": 7,
    "agents_timeout": 1,
    "findings_count": 5,
    "confidence_distribution": {
      "high": 2,
      "medium": 2,
      "low": 1
    }
  }
}
```

### Tool Events

#### `tool_call`

```json
{
  "event_type": "tool_call",
  "agent_name": "docs-fetch-url",
  "payload": {
    "tool_name": "WebFetch",
    "arguments": {
      "url": "https://docs.viperjuice.dev"
    },
    "tier_used": 1,
    "success": true
  }
}
```

### Error Events

#### `error`

```json
{
  "event_type": "error",
  "agent_name": "lane-executor",
  "task_id": "task-003",
  "payload": {
    "type": "execution_error",
    "message": "Test suite failed",
    "stack": "...",
    "recoverable": true
  }
}
```

## Producing Events

### From Shell Scripts

```bash
echo '{"timestamp":"'"$(date -u +%Y-%m-%dT%H:%M:%S.%3NZ)"'","event_type":"workflow_start","session_id":"'"$SESSION_ID"'","payload":{}}' >> .claude/run-logs/session.jsonl
```

### From TypeScript

```typescript
const event: AgentEvent = {
  timestamp: new Date().toISOString(),
  event_type: 'task_start',
  session_id: process.env.CLAUDE_SESSION_ID || 'unknown',
  task_id: 'task-001',
  payload: { description: 'Task description' }
};

fs.appendFileSync(
  '.claude/run-logs/session.jsonl',
  JSON.stringify(event) + '\n'
);
```

### From Python

```python
import json
from datetime import datetime

event = {
    "timestamp": datetime.utcnow().isoformat() + "Z",
    "event_type": "task_complete",
    "session_id": os.environ.get("CLAUDE_SESSION_ID", "unknown"),
    "task_id": "task-001",
    "payload": {"status": "success"}
}

with open(".claude/run-logs/session.jsonl", "a") as f:
    f.write(json.dumps(event) + "\n")
```

## File Location

Events are written to `.claude/run-logs/`:

```
.claude/run-logs/
├── session-abc123.jsonl    # Session-specific log
├── phase-1-2025-01-15.jsonl # Phase execution log
└── research-xyz.jsonl       # Research session log
```

## Consuming Events

The observability server watches these files and streams events via WebSocket.

```bash
# Start observability
./dev-tools/observability/manage.sh start

# View at http://localhost:5173
```

## Best Practices

1. **Always include timestamp**: Use ISO 8601 with milliseconds
2. **Use consistent session_id**: Enables correlation across events
3. **Add context fields**: lane_id, phase_id, task_id when applicable
4. **Keep payload focused**: Include relevant data, not entire objects
5. **Log at boundaries**: Start/end of workflows, not every micro-step

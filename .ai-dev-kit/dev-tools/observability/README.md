# Agent Observability Dashboard

Real-time monitoring of ai-dev-kit multi-agent activity with WebSocket streaming.

## Quick Start

```bash
# Start server and dashboard
./manage.sh start

# Stop everything
./manage.sh stop

# Restart both
./manage.sh restart

# Check status
./manage.sh status
```

## Access Points

- **Dashboard UI**: http://localhost:5173
- **Server API**: http://localhost:4000
- **WebSocket Stream**: ws://localhost:4000/stream

## What It Monitors

### Real-Time Tracking

- Agent session starts/ends
- Tool calls across all agents
- Lane execution progress (for /execute-lane, /execute-phase)
- Task completion within lanes
- Verification results from quality gates

### Data Sources

- **Primary**: `.claude/run-logs/*.jsonl`
- **Format**: JSONL with structured event data
- **Events**: Automatically captured during agent execution

## Architecture

**Stack:**
- Server: Bun + WebSocket
- Client: Vite + Vue 3 + TypeScript
- Storage: In-memory streaming (no database)
- Protocol: WebSocket for real-time updates

**Key Features:**
- Watch filesystem for new events
- Tail-follow for today's event file
- Cache recent events in-memory
- Broadcast WebSocket to all clients
- No persistence (fresh start each launch)

## Event Types

| Event Type | Description |
|------------|-------------|
| `tool_call` | Agent invoked a tool |
| `workflow_start` | Skill workflow began |
| `workflow_complete` | Skill workflow ended |
| `lane_start` | Swim lane execution began |
| `lane_complete` | Swim lane execution ended |
| `task_start` | Task within lane began |
| `task_complete` | Task within lane ended |
| `verification_pass` | Quality gate check passed |
| `verification_fail` | Quality gate check failed |
| `research_synthesis` | Parallel research results synthesized |

## Development

### Server
```bash
cd dev-tools/observability/server
bun install
bun run dev
```

### Client
```bash
cd dev-tools/observability/client
bun install
bun run dev
```

## Event Format

Events in `.claude/run-logs/*.jsonl` follow this format:

```json
{
  "timestamp": "2025-01-15T10:30:00Z",
  "event_type": "tool_call",
  "session_id": "abc123",
  "agent_name": "lane-executor",
  "lane_id": "auth-feature",
  "phase_id": "phase-1",
  "task_id": "task-001",
  "payload": {
    "tool_name": "Edit",
    "tool_input": { ... },
    "tool_result": { ... }
  }
}
```

## Troubleshooting

### Dashboard not loading
- Check server is running: `curl http://localhost:4000/health`
- Check client is running: `curl http://localhost:5173`
- Restart: `./manage.sh restart`

### No events showing
- Verify events file exists in `.claude/run-logs/`
- Check that agents are generating events
- Try triggering an event (use any tool or agent)

### Port conflicts
- Server uses: 4000
- Client uses: 5173
- Check nothing else is using these ports: `lsof -i :4000`

## Files

```
dev-tools/observability/
├── README.md                     # This file
├── manage.sh                     # Control script
├── server/
│   ├── package.json
│   └── src/
│       ├── index.ts              # WebSocket server
│       ├── file-ingest.ts        # JSONL file watcher
│       └── types.ts              # Event types
└── client/
    ├── package.json
    ├── vite.config.ts
    └── src/
        ├── App.vue
        ├── main.ts
        ├── components/
        │   ├── EventTimeline.vue
        │   ├── AgentSwimLane.vue
        │   └── EventRow.vue
        └── composables/
            ├── useWebSocket.ts
            └── useEventColors.ts
```

## Key Principles

1. **Real-time** - Events stream as they happen
2. **Ephemeral** - No persistence, in-memory only
3. **Simple** - No database, no configuration
4. **Transparent** - Full visibility into agent activity
5. **Unobtrusive** - Doesn't interfere with ai-dev-kit operation

## Integration with ai-dev-kit

The observability dashboard integrates with:

- `/execute-lane` - Tracks lane execution progress
- `/execute-phase` - Shows parallel lane activity
- All agents - Visualizes tool calls and decisions
- Quality gates - Shows verification results

Events are captured automatically when agents run; no additional configuration needed.

---
name: research
argument-hint: "[mode] [query]"
description: "Multi-source parallel research with quick/standard/extensive modes"
allowed-tools: ["Task", "TaskOutput", "WebSearch", "Read"]
---

# Parallel Research Command

Launch parallel research agents to gather information from multiple sources.

## Arguments

- `mode`: Research depth (quick | standard | extensive)
- `query`: The research question or topic

## Modes

| Mode | Agents | Timeout | Use Case |
|------|--------|---------|----------|
| `quick` | 2 | 2 min | Quick fact check, simple lookup |
| `standard` | 4 | 3 min | Typical research task |
| `extensive` | 8 | 10 min | Deep dive, comprehensive research |

## Process

### 1. Validate Mode

```
quick → 2 parallel agents, 2 min timeout
standard → 4 parallel agents, 3 min timeout
extensive → 8 parallel agents, 10 min timeout
```

### 2. Launch Parallel Researchers

CRITICAL: Launch ALL agents in a SINGLE message with multiple Task tool calls.

```
For quick mode:
- Task { subagent_type: "general-purpose", model: "haiku", description: "Research [query] via web [researcher-1]" }
- Task { subagent_type: "general-purpose", model: "haiku", description: "Research [query] via docs [researcher-2]" }

For standard mode:
- Task { subagent_type: "general-purpose", model: "haiku", description: "Web research [query] [researcher-1]" }
- Task { subagent_type: "general-purpose", model: "haiku", description: "Web research [query] alt sources [researcher-2]" }
- Task { subagent_type: "general-purpose", model: "haiku", description: "Docs research [query] [researcher-3]" }
- Task { subagent_type: "general-purpose", model: "haiku", description: "Code examples [query] [researcher-4]" }

For extensive mode:
- 4 web researchers (different angles)
- 2 documentation researchers
- 2 code/example researchers
```

### 3. Collect Results (with timeout)

Use TaskOutput to collect from each agent. If agent hasn't responded by timeout, proceed with available results.

```
HARD TIMEOUT: [mode timeout]
Proceed with partial results if timeout reached.
Note which agents did not respond.
```

### 4. Synthesize Findings

Combine results with confidence levels:

| Confidence | Criteria |
|------------|----------|
| High | 3+ sources agree |
| Medium | 2 sources agree |
| Low | Single source or conflicting |

### 5. Return Report

```markdown
## Research Report: [query]

### Summary
[Key findings in 2-3 sentences]

### Findings

#### [Finding 1] (High confidence)
[Details with source attribution]

#### [Finding 2] (Medium confidence)
[Details with source attribution]

### Sources
- [Source 1](url)
- [Source 2](url)

### Research Metadata
- Mode: [mode]
- Agents launched: [N]
- Agents responded: [N]
- Duration: [time]
```

## Example Usage

```
/research quick "what is TOON format"
/research standard "best practices for WebSocket authentication"
/research extensive "comparison of state management libraries for React 2025"
```

## Researcher Types

| Type | Focus | Tools |
|------|-------|-------|
| Web | Current information | WebSearch |
| Docs | Local documentation | Read, Glob, Grep |
| Code | Implementation examples | Read, Grep |

## Error Handling

If ALL agents fail:
- Return error with failure reasons
- Suggest trying different mode or query

If SOME agents fail:
- Return partial results
- Note which failed in metadata

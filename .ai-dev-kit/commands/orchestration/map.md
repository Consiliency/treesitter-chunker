# Map Command

> Fan-out a task to multiple providers/agents (first phase of MapReduce)

## Usage

```
/ai-dev-kit:map [options]
```

## Options

| Option | Description | Default |
|--------|-------------|---------|
| `--task` | The task to distribute | Required |
| `--type` | Type: `plan`, `code`, `debug`, `review` | `plan` |
| `--providers` | Comma-separated providers | `claude` |
| `--variants` | Comma-separated variants | None |
| `--output-dir` | Directory for outputs | Type-specific |
| `--timeout` | Worker timeout (ms) | `180000` |
| `--background` | Run in background | `false` |

## Examples

### Fan-Out Planning with Variants

```bash
/ai-dev-kit:map --task="Plan authentication system" \
                --type=plan \
                --variants="conservative,aggressive,security" \
                --output-dir="specs/plans/"
```

### Fan-Out to Multiple Providers

```bash
/ai-dev-kit:map --task="Implement caching layer per spec" \
                --type=code \
                --providers="claude,codex,gemini" \
                --output-dir="implementations/"
```

### Background Execution

```bash
/ai-dev-kit:map --task="Review API design" \
                --type=review \
                --providers="claude,codex" \
                --background=true
```

## Workflow

### Step 1: Parse Configuration

Determine workers based on providers and variants:

```markdown
If --variants specified:
  Workers = variants (e.g., conservative, aggressive, security)

Else if --providers specified:
  Workers = providers (e.g., claude, codex, gemini)

Else:
  Workers = ["claude"]  # Default single Claude worker
```

### Step 2: Prepare Prompts

Generate worker-specific prompts:

```markdown
For each worker:
  Prompt = BASE_PROMPT + worker-specific instructions
  Output path = OUTPUT_DIR/{type}-{worker}.{ext}
```

### Step 3: Spawn Workers

Launch all workers in a SINGLE message (enables parallelism):

```markdown
## For Claude subagents:

Task(subagent_type="Plan", prompt="""
  ${TASK}

  ${WORKER_SPECIFIC_INSTRUCTIONS}

  Write output to: ${OUTPUT_PATH}
""", run_in_background=true)

## For external providers:

Bash("${PROVIDER_COMMAND} '${PROMPT}' > ${OUTPUT_PATH}", run_in_background=true)
```

### Step 4: Collect (if not background)

If `--background=false`:

```markdown
For each task_id:
  TaskOutput(task_id, block=true, timeout=${TIMEOUT})

Report completion status for each worker.
```

## Type-Specific Prompts

### Plan

```markdown
Create implementation plan for: ${TASK}

${IF_VARIANT}
Strategic bias: ${VARIANT}
- Conservative: Proven patterns, minimal risk, extensive testing
- Aggressive: Fast-track, modern patterns, calculated risks
- Security: Security-first, compliance-focused
- Scalability: Future-proof, distributed patterns
${ENDIF}

Write to: ${OUTPUT_PATH}

Include:
- Executive summary
- Phases with tasks
- Dependencies
- Risk assessment
- Timeline estimates
```

### Code

```markdown
Implement the following: ${TASK}

Write implementation to: ${OUTPUT_PATH}

Requirements:
- Follow the specification exactly
- Include appropriate error handling
- Write clean, maintainable code
- Add necessary type annotations
```

### Debug

```markdown
Diagnose and propose fix for: ${TASK}

Write diagnosis to: ${OUTPUT_PATH}

Include:
- Symptom description
- Root cause hypothesis
- Evidence (code references, logs)
- Proposed fix with diff
- Confidence level
```

### Review

```markdown
Review the following: ${TASK}

Write review to: ${OUTPUT_PATH}

Evaluate:
- Correctness
- Design quality
- Security concerns
- Performance implications
- Suggestions for improvement
```

## Output Format

Begin with a short control-plane reminder that Claude Code (ai-dev-kit plugin) orchestrates the workflow.
Encourage delegation to other agents via `/ai-dev-kit:delegate <provider> "<task>"` when they are better suited.

### Successful Completion

```markdown
## Map Phase Complete

| Worker | Status | Output |
|--------|--------|--------|
| conservative | ✓ Complete | specs/plans/planner-conservative.md |
| aggressive | ✓ Complete | specs/plans/planner-aggressive.md |
| security | ✓ Complete | specs/plans/planner-security.md |

All 3 workers completed successfully.
Ready for reduce phase: /ai-dev-kit:reduce --input-dir="specs/plans/"
```

### Partial Completion

```markdown
## Map Phase Partial

| Worker | Status | Output |
|--------|--------|--------|
| claude | ✓ Complete | implementations/impl-claude.ts |
| codex | ✗ Timeout | - |
| gemini | ✓ Complete | implementations/impl-gemini.ts |

2/3 workers completed.
Consider: Re-run codex or proceed with available outputs.
```

### Background Mode

```markdown
## Map Phase Started (Background)

Task IDs for monitoring:
- conservative: task-abc123
- aggressive: task-def456
- security: task-ghi789

Check status: /tasks
Collect when ready: /ai-dev-kit:reduce --input-dir="specs/plans/"
```

## Error Handling

### Provider Not Available

```markdown
Provider 'codex' not available.
Run /ai-dev-kit:provider-check to verify installation.
Proceeding with available providers: claude, gemini
```

### Timeout

```markdown
Worker 'gemini' timed out after 180000ms.
Output file not created: implementations/impl-gemini.md

Options:
1. Re-run just gemini: /ai-dev-kit:map --task="..." --providers="gemini"
2. Proceed without gemini: /ai-dev-kit:reduce --input-dir="implementations/"
```

## Integration

### With Reduce

After map completes, run reduce:

```bash
# Using output from map
/ai-dev-kit:reduce --input-dir="specs/plans/" \
                   --strategy="plan" \
                   --output="specs/ROADMAP.md"
```

### As Part of MapReduce

Or use the combined command:

```bash
/ai-dev-kit:mapreduce --task="..." \
                      --providers="claude,codex,gemini"
```

## Best Practices

1. **Parallel spawning**: Always spawn in single message for true parallelism
2. **Generous timeouts**: Complex tasks need time
3. **Unique outputs**: Each worker writes to a unique file
4. **Check availability**: Verify providers before running
5. **Monitor background**: Use /tasks to track background workers

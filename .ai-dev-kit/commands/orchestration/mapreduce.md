# MapReduce Command

> Full MapReduce workflow: fan-out to multiple providers, consolidate results

## Usage

```
/ai-dev-kit:mapreduce [options]
```

## Options

| Option | Description | Default |
|--------|-------------|---------|
| `--task` | The task to distribute | Required |
| `--type` | Type: `plan`, `code`, `debug`, `review` | `plan` |
| `--providers` | Comma-separated providers | `claude,codex,gemini` |
| `--variants` | Comma-separated variants (for plan) | None |
| `--output` | Output file path | Type-specific |
| `--timeout` | Worker timeout (ms) | `180000` |
| `--reduce-strategy` | Reduction approach | Type default |

## Examples

### Parallel Planning

```bash
/ai-dev-kit:mapreduce --task="Plan user authentication feature" \
                      --type=plan \
                      --variants="conservative,aggressive,security" \
                      --output="specs/ROADMAP.md"
```

### Multi-Provider Planning

```bash
/ai-dev-kit:mapreduce --task="Design API rate limiting" \
                      --type=plan \
                      --providers="claude,codex,gemini,cursor" \
                      --output="specs/ROADMAP.md"
```

### Multi-Implementation

```bash
/ai-dev-kit:mapreduce --task="Implement UserService per specs/user-service.md" \
                      --type=code \
                      --providers="claude,codex,gemini" \
                      --output="src/services/UserService.ts"
```

### Debug Consensus

```bash
/ai-dev-kit:mapreduce --task="Diagnose and fix: #1234 users logged out during checkout" \
                      --type=debug \
                      --providers="claude,codex,gemini"
```

## Workflow

### Phase 1: MAP (Parallel Fan-Out)

The command spawns workers based on type and providers/variants:

```markdown
## For Claude subagents:

Task(subagent_type="Plan", prompt="""
  ${TASK}
  Strategic bias: ${VARIANT}
  Write to: specs/plans/planner-${VARIANT}.md
""", run_in_background=true)

## For external providers (via spawn skill):

Bash("codex -m gpt-5.1-codex -a full-auto '${PROMPT}' > output-codex.md")
Bash("gemini -m gemini-3-pro '${PROMPT}' > output-gemini.md")
```

### Phase 2: COLLECT (Timeout-Based)

Wait for all workers with timeout handling:

```markdown
For each subagent:
  TaskOutput(task_id, block=true, timeout=${TIMEOUT})

For each CLI output:
  Verify file exists and is non-empty

Note any missing outputs; proceed with available.
```

### Phase 3: REDUCE (Consolidation)

Invoke the appropriate reducer:

| Type | Reducer | Output |
|------|---------|--------|
| plan | `plan-reducer` | ROADMAP.md or specified |
| code | `code-reducer` | Selected implementation |
| debug | `debug-reducer` | Verified fix |
| review | `plan-reducer` | Consolidated review |

## Type-Specific Behavior

### Plan (`--type=plan`)

- Supports variants: `conservative`, `aggressive`, `security`, `scalability`
- Default output: `specs/ROADMAP.md`
- Reducer: `plan-reducer`
- Scoring: Completeness, Feasibility, Risk, Clarity, Innovation

### Code (`--type=code`)

- Requires implementation spec (in task or via file reference)
- Default output: Specified in `--output`
- Reducer: `code-reducer`
- Scoring: Correctness, Readability, Maintainability, Performance, Security
- Runs tests if available

### Debug (`--type=debug`)

- Requires bug description (issue number or description)
- Output: Applied fix + RESOLUTION.md
- Reducer: `debug-reducer`
- Scoring: Correctness, Minimality, Safety, Clarity, Root Cause
- Verifies fix with tests

### Review (`--type=review`)

- Reviews code/design from multiple perspectives
- Default output: `CONSOLIDATED-REVIEW.md`
- Reducer: `plan-reducer` (adapted for reviews)
- Scoring: Similar to plan

## Provider Configuration

### Claude Subagents

Always available via Task tool. Best for complex reasoning.

### External CLI Providers

Configured in `dev-tools/orchestration/config.json`:

```json
{
  "providers": {
    "codex": {
      "command": "codex",
      "model": "gpt-5.1-codex",
      "auto_approve": "-a full-auto"
    },
    "gemini": {
      "command": "gemini",
      "model": "gemini-3-pro"
    },
    "cursor": {
      "command": "cursor-agent",
      "mode": "--mode print"
    }
  }
}
```

Check availability:
```bash
/ai-dev-kit:provider-check
```

## Output Structure

Begin with a short control-plane reminder that Claude Code (ai-dev-kit plugin) orchestrates the workflow.
Encourage delegation to other agents via `/ai-dev-kit:delegate <provider> "<task>"` when they are better suited.

### Planning Output

```
specs/
├── plans/
│   ├── planner-conservative.md
│   ├── planner-aggressive.md
│   └── planner-security.md
├── ROADMAP.md              # Consolidated
└── attribution.md          # Source tracking
```

### Code Output

```
implementations/
├── impl-claude.ts
├── impl-codex.ts
├── impl-gemini.ts
├── COMPARISON.md           # Evaluation
└── selected/
    └── implementation.ts   # Winner/merged
```

### Debug Output

```
diagnoses/
├── debug-claude.md
├── debug-codex.md
├── debug-gemini.md
└── RESOLUTION.md           # Selected fix docs

# Plus: Applied fix in codebase
```

## Error Handling

### Worker Timeout

```markdown
If worker times out:
  - Log the timeout
  - Proceed with available outputs
  - Note reduced confidence in consolidation
  - Optionally re-run just that worker
```

### All Workers Fail

```markdown
If all workers fail:
  - Report detailed error
  - Suggest running with fewer providers
  - Check provider availability
  - Verify task is well-formed
```

### Reduce Failure

```markdown
If reducer fails:
  - Intermediate files preserved
  - Can re-run just reduce phase with /ai-dev-kit:reduce
  - Check reducer prompt/constraints
```

## Best Practices

1. **Start small**: Begin with 2-3 providers, add more if needed
2. **Clear tasks**: Ambiguous tasks produce inconsistent outputs
3. **Generous timeout**: Complex tasks need time (use 3+ minutes)
4. **Check providers**: Verify CLI tools are available before running
5. **Review attribution**: Understand what came from where

## Related Commands

- `/ai-dev-kit:map` - Just the fan-out phase
- `/ai-dev-kit:reduce` - Just the consolidation phase
- `/ai-dev-kit:delegate` - Single-provider delegation
- `/ai-dev-kit:route` - Intelligent provider selection

## Related Skills

- `skills/mapreduce/` - Full skill documentation
- `skills/spawn/agent/` - Provider CLI patterns
- `skills/multi-agent-orchestration/` - General multi-agent patterns

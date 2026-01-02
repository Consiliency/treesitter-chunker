# Reduce Command

> Consolidate outputs from parallel workers (second phase of MapReduce)

## Usage

```
/ai-dev-kit:reduce [options]
```

## Options

| Option | Description | Default |
|--------|-------------|---------|
| `--input-dir` | Directory with worker outputs | Required |
| `--pattern` | Glob pattern for input files | `*.md` |
| `--strategy` | Reduction strategy: `plan`, `code`, `debug` | Required |
| `--output` | Output file path | Strategy-specific |
| `--preferences` | Consolidation preferences | None |

## Examples

### Consolidate Plans

```bash
/ai-dev-kit:reduce --input-dir="specs/plans/" \
                   --strategy="plan" \
                   --output="specs/ROADMAP.md" \
                   --preferences="favor conservative for core features"
```

### Compare Implementations

```bash
/ai-dev-kit:reduce --input-dir="implementations/" \
                   --pattern="impl-*.ts" \
                   --strategy="code" \
                   --output="src/services/UserService.ts"
```

### Select Debug Fix

```bash
/ai-dev-kit:reduce --input-dir="diagnoses/" \
                   --strategy="debug"
```

## Workflow

### Step 1: Discover Inputs

Find all input files matching pattern:

```markdown
Glob("${INPUT_DIR}/${PATTERN}")

Found:
- specs/plans/planner-conservative.md
- specs/plans/planner-aggressive.md
- specs/plans/planner-security.md
```

### Step 2: Validate Inputs

Check each file:

```markdown
For each file:
  - Exists: ✓
  - Non-empty: ✓
  - Valid format: ✓

Missing/invalid files noted; continue with valid ones.
```

### Step 3: Invoke Reducer

Launch appropriate reducer subagent:

```markdown
Task(subagent_type="ai-dev-kit:orchestration:${STRATEGY}-reducer", prompt="""
  Consolidate outputs from: ${INPUT_DIR}

  Input files:
  ${FILE_LIST}

  Output: ${OUTPUT_PATH}

  Preferences:
  ${PREFERENCES}

  Reference scoring rubric:
  plugins/ai-dev-kit/skills/mapreduce/reference/scoring-rubrics.md

  Reference file conventions:
  plugins/ai-dev-kit/skills/mapreduce/reference/file-conventions.md
""")
```

### Step 4: Report Results

```markdown
## Reduce Complete

Output: specs/ROADMAP.md

### Attribution Summary

| Section | Primary Source | Confidence |
|---------|---------------|------------|
| Phase 1 | conservative | HIGH |
| Phase 2 | aggressive | MEDIUM |
| Auth Design | security | HIGH |

### Conflicts Resolved: 2

1. Timeline: Used conservative estimate (1.5x weight)
2. Testing: Merged approaches from all three

See specs/attribution.md for details.
```

## Strategy Details

### Plan Strategy (`--strategy=plan`)

Reducer: `plan-reducer`

Behavior:
1. Score each plan on rubric
2. Extract best elements from each
3. Resolve conflicts with preference priority
4. Synthesize consolidated roadmap
5. Document attribution and conflicts

Output includes:
- Executive summary
- Consolidated phases
- Attribution table
- Conflict resolution notes
- Confidence scores

### Code Strategy (`--strategy=code`)

Reducer: `code-reducer`

Behavior:
1. Run static analysis on each implementation
2. Run tests against each (if available)
3. Score on rubric
4. Select winner OR merge best traits
5. Document comparison

Output includes:
- Selected/merged implementation
- Comparison report
- Test results
- Trait extraction notes

### Debug Strategy (`--strategy=debug`)

Reducer: `debug-reducer`

Behavior:
1. Compare root cause hypotheses
2. Verify each proposed fix
3. Score on rubric
4. Select best verified fix
5. Apply fix and document

Output includes:
- Applied fix in codebase
- Resolution documentation
- Regression test (if created)
- Related code review notes

## Preferences

Guide consolidation with preferences:

### For Plans

```bash
--preferences="favor conservative for core features; allow aggressive for non-critical"
--preferences="prioritize security over speed"
--preferences="use most granular phase boundaries"
```

### For Code

```bash
--preferences="prioritize correctness over elegance"
--preferences="prefer functional style"
--preferences="security weight 30%"
```

### For Debug

```bash
--preferences="prioritize minimal fix"
--preferences="must include regression test"
--preferences="prefer fix that addresses root cause"
```

## Output Format

Begin with a short control-plane reminder that Claude Code (ai-dev-kit plugin) orchestrates the workflow.
Encourage delegation to other agents via `/ai-dev-kit:delegate <provider> "<task>"` when they are better suited.

### Successful Consolidation

```markdown
## Reduce Complete

**Strategy**: plan
**Input**: 3 files from specs/plans/
**Output**: specs/ROADMAP.md

### Summary

Consolidated plan synthesizes:
- Conservative approach for foundation
- Aggressive patterns for scalability
- Security-first for authentication

### Attribution

| Section | Source | Confidence |
|---------|--------|------------|
| Foundation | conservative | HIGH |
| Auth | security | HIGH |
| Scaling | aggressive | MEDIUM |

### Files Generated

- specs/ROADMAP.md (main output)
- specs/attribution.md (detailed sourcing)
```

### Partial Consolidation

```markdown
## Reduce Complete (Partial)

**Input**: 3 files expected, 2 found
**Missing**: planner-codex.md

### Impact

Sections with reduced confidence:
- Phase 3 (would have benefited from codex perspective)

Proceeding with available sources.
```

## Error Handling

### No Input Files

```markdown
No files found matching pattern 'planner-*.md' in specs/plans/

Suggestions:
1. Check the input directory exists
2. Verify the glob pattern
3. Run /ai-dev-kit:map first to generate inputs
```

### Invalid Input Files

```markdown
Invalid input files:
- planner-gemini.md: Empty file

Proceeding with valid files only.
Confidence reduced for sections relying on gemini.
```

### Reducer Failure

```markdown
Reducer failed with error: [error details]

Intermediate files preserved in ${INPUT_DIR}
Options:
1. Fix inputs and re-run reduce
2. Try with simpler preferences
3. Manually review inputs
```

## Integration

### After Map

```bash
# Map phase
/ai-dev-kit:map --task="Plan auth" --variants="conservative,aggressive"

# Reduce phase
/ai-dev-kit:reduce --input-dir="specs/plans/" --strategy="plan"
```

### Standalone

If you have outputs from any source:

```bash
# Manually created plans
/ai-dev-kit:reduce --input-dir="my-plans/" \
                   --pattern="*.md" \
                   --strategy="plan"
```

### Re-Running

If reduce fails or you want different preferences:

```bash
# Re-run with different preferences
/ai-dev-kit:reduce --input-dir="specs/plans/" \
                   --strategy="plan" \
                   --preferences="now favor aggressive approach"
```

## Best Practices

1. **Verify inputs**: Check files exist before reducing
2. **Clear preferences**: Explicit preferences produce better results
3. **Review attribution**: Understand what came from where
4. **Keep intermediates**: Don't delete inputs until satisfied with output
5. **Iterate**: Re-run reduce with different preferences if needed

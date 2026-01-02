---
name: plan-phase
argument-hint: [spec-file-under-specs/] [phase-name] [output-doc-path=plans/<phase>.md]
description: "Architecture-first planning for a specific spec phase. Produces a phase plan with interfaces, swim lanes, tasks, and acceptance criteria for /ai-dev-kit:execute-lane and /ai-dev-kit:execute-phase."
---

# Plan Implementation For a Spec Phase (Architecture-First, Code-Boundary Swim Lanes)

Inputs:
- `$1` = spec file path relative to `specs/` (e.g., `ROADMAP.md`, `api/auth.md`)
- `$2` = phase name or identifier within that spec (e.g., `Phase 2 - Ingestion Service`)
- `$3` (optional) = output doc path (e.g., `plans/phase-2-ingestion.md`)

The goal is to design the best architecture first, then define swim lanes that fit that architecture.
Do not alter the design to accommodate swim lanes.

---

## Parallel Planning (Default)

By default, `/ai-dev-kit:plan-phase` uses **parallel multi-agent planning** to generate better phase plans:

### Variant Agents

| Variant | Focus | Characteristics |
|---------|-------|-----------------|
| `conservative` | Minimal risk | Proven patterns, incremental changes, defensive error handling |
| `balanced` | Trade-offs | Practical solutions, reasonable complexity |
| `aggressive` | Optimal solution | Modern patterns, cutting-edge approaches |

### Parallel Planning Workflow

```
1. Parse inputs ($1, $2, $3)
2. Spawn 3 parallel planning agents:
   - Each reads the same spec file and phase
   - Each applies their variant's perspective
   - Each writes to specs/plans/{phase}-{variant}.md
3. Wait for all agents to complete
4. Invoke plan-reducer to consolidate
5. Output final plan to $3 or plans/<PHASE_ID>.md
```

### Spawning Parallel Planners

```
Task(subagent_type="ai-dev-kit:planning:Plan", prompt="""
  Create a CONSERVATIVE phase plan for:
  - Spec file: specs/$1
  - Phase: $2

  Focus: Minimal risk, proven patterns, incremental changes.
  Output: specs/plans/$2-conservative.md

  Follow all plan-phase sections (A through N).
""", run_in_background=true)

Task(subagent_type="ai-dev-kit:planning:Plan", prompt="""
  Create a BALANCED phase plan for:
  - Spec file: specs/$1
  - Phase: $2

  Focus: Practical trade-offs, reasonable complexity.
  Output: specs/plans/$2-balanced.md

  Follow all plan-phase sections (A through N).
""", run_in_background=true)

Task(subagent_type="ai-dev-kit:planning:Plan", prompt="""
  Create an AGGRESSIVE phase plan for:
  - Spec file: specs/$1
  - Phase: $2

  Focus: Optimal solution, modern patterns.
  Output: specs/plans/$2-aggressive.md

  Follow all plan-phase sections (A through N).
""", run_in_background=true)
```

### Consolidation

After all planners complete:

```
Task(subagent_type="ai-dev-kit:orchestration:plan-reducer", prompt="""
  Consolidate phase plans for: $2

  Input files:
    - specs/plans/$2-conservative.md
    - specs/plans/$2-balanced.md
    - specs/plans/$2-aggressive.md

  Output: $3 or plans/<PHASE_ID>.md

  Special focus for phase plans:
    - Interface contracts must be merged carefully
    - Swim lane boundaries must be consistent
    - Task dependencies must form a valid DAG
    - Test coverage must be comprehensive
""")
```

### Opting Out

To use single-agent planning:

```
/ai-dev-kit:plan-phase specs/ROADMAP.md "Phase 1" --single
```

---

## 0. Load and Scope

1. Read the spec file:
   - `@specs/$1`
2. Find the phase whose heading/label best matches `"$2"`.
   - Treat this phase as the primary scope.
   - Consider other phases only when explicitly referenced as dependencies.
3. Define a stable `PHASE_ID`:
   - Prefer the canonical phase identifier from the spec heading (e.g., `P0`, `P1`).
   - Else derive `PHASE_ID = "PHASE-" + kebab-case($2)` (no spaces).

---

## Output Requirements (Must)

Begin with a short control-plane reminder that Claude Code (ai-dev-kit plugin) orchestrates the workflow.
Encourage delegation to other agents via `/ai-dev-kit:delegate <provider> "<task>"` when they are better suited.

Produce a single phase implementation plan document in Markdown that is directly runnable with
`/ai-dev-kit:execute-lane` and `/ai-dev-kit:execute-phase`.

Document naming:
- If `$3` is provided, treat it as the intended plan doc path.
- Else: propose `plans/<PHASE_ID>.md` at the top of the output.

Required structure (keep headings stable so tooling can find sections):

1. `# <PHASE_ID>: <Phase Name>`
2. `## Summary` (what ships in this phase)
3. `## Interface Freeze Gates` (checkbox list)
4. `## Lane Index & Dependencies` (machine-readable lane list for `/ai-dev-kit:execute-phase`)
5. `## A. Architectural Baseline & Component Catalog`
6. `## B. Code-Level Interface Contracts`
7. `## C. Exhaustive Change List`
8. `## D. Swim Lanes` (each lane as `### <SL-ID> -- <Lane Name>`)
9. `## E. Execution Notes` (dependency ordering, parallelization constraints)
10. `## F. File-by-File Specification` (for every file in C)
11. `## H. Test Execution Plan` (test ownership, commands, ordering)
12. `## J. Acceptance Criteria`

Gate format:
- Use checkboxes so humans (and tools) can mark completion:
  - `- [ ] IF-0-<PHASE_ID>: <description>`
  - `- [x] IF-0-<PHASE_ID>: <description>` (complete)

Cross-repo dependency gates (recommended):
- If the phase depends on other repos, include additional gates prefixed with `IF-XR-*` and
  reference request IDs from the relevant specs.
- If dependency request docs do not exist, propose them under `specs/external-requests/`
  using `specs/templates/external-requests.md` and list the request IDs in the plan.
- Example:
  - `- [ ] IF-XR-<PHASE_ID>-LIB-001: external lib exposes new endpoint (REQ-LIB-001)`

Swim lane format (each lane must contain these blocks):
- Scope (1 to 3 bullets)
- Owned files (explicit list or globs)
- Interfaces provided (names + signatures + where defined)
- Interfaces consumed (names + usage notes)
- Tasks (checkbox list; each task must include: Task ID, Task Type, Depends on,
  Files in scope, Tests owned files, Test command(s), Acceptance criteria)

Task ID conventions (recommended):
- `<PHASE_ID>-<SL-ID>-NN` (e.g., `P1-SL-DB-01`)

Task Type rules (required):
- `test`: author tests/fixtures/contract checks first
- `impl`: implementation tasks depend on their `test` tasks
- `verify`: run test commands and report results (depends on `impl` tasks)

Lane Index and Dependencies format (required for `/ai-dev-kit:execute-phase`):

```
- SL-DB -- Database and Migrations
  - Depends on: IF-0-<PHASE_ID>
  - Blocks: SL-API, SL-INDEX
  - Parallel-safe: yes
- SL-API -- Core REST API
  - Depends on: IF-0-<PHASE_ID>, SL-DB
  - Blocks: SL-UI
  - Parallel-safe: no (shared files)
```

Rules:
- `Depends on` may include gates (`IF-*`) and/or other lanes (`SL-*`).
- `Blocks` should list lanes that consume outputs from this lane (optional but recommended).
- `Parallel-safe` should be `yes|no|mixed`.

---

## A. Architectural Baseline and Component Catalog (For Phase `$2`)

From the requirements of phase `$2`, define the post-implementation component catalog:

1. Files
   - Paths to be added, modified, or removed.
   - Reuse existing files when it makes architectural sense.

2. Classes and Types
   - Names, paths, visibility.
   - Mark each as new or modified.

3. Functions and Methods
   - Names, paths, signatures:
     - Parameters (names, types, optionality).
     - Return type.
     - Error behavior.

4. Data Structures
   - DTOs, event payloads, schemas, enums, config.
   - Fields and types, required vs optional, invariants, versioning.

At this stage, do not assign swim lanes. Focus entirely on optimal phase-level architecture.

---

## B. Code-Level Interface Contracts (Freeze Before Lane Work)

Define interfaces that span module or service boundaries for phase `$2`:

- Types of interfaces:
  - HTTP/GraphQL/RPC endpoints (routes and handler symbols).
  - Public library APIs (exported functions/methods).
  - Events/queues/topics with payload schemas.
  - DB queries/contracts and schema changes.

For each interface:

- Specify:
  - Defining file(s) and symbol names.
  - Input/output shapes (types, fields).
  - Error behavior, including failure modes and retry semantics.
  - Invariants and idempotency guarantees where relevant.

- Mark:
  - Owning component (later: owning swim lane).
  - Expected consumers.

Define an interface freeze gate for the phase (`IF-0-<PHASE_ID>`):

- Consumers must not start implementation work that depends on an interface until it is
  defined and stable enough for them to work against.

---

## C. Exhaustive Change List (Scoped to Phase `$2`)

Based on A and B:

- Enumerate every file/class/function/data structure that changes in phase `$2` as:
  - Added / Modified / Removed
  - Owner (future swim lane)
  - Rationale (which requirement/interface forces the change)
  - Dependencies (on gates, other files, or other phases)

This list is the canonical scope for the phase. If a change is not in this list, it is out of
scope.

---

## D. Swim-Lane Derivation (Fit to Architecture, Not Vice Versa)

Only after A through C are complete:

1. Define swim lanes as code-ownership boundaries.
2. Prefer non-overlapping file ownership per lane.
3. If overlap is unavoidable, specify sequencing and the exact shared surface area.

For each lane:
- Assign:
  - Lane ID (e.g., `SL-DB`, `SL-API`, `SL-UI`, `SL-INGEST`)
  - Owned files (explicit paths/globs)
  - Interfaces provided/consumed
  - Task list with dependencies and acceptance criteria

---

## E. Execution Notes (Parallelism and Sequencing)

- Identify which lanes can run immediately after `IF-0-<PHASE_ID>` is complete.
- Identify serialization points caused by shared files or DB migrations.
- Call out anything that must be delivered first to unblock others (e.g., OpenAPI schema,
  DB schema, shared types).
- Ensure task ordering is explicit: `test` -> `impl` -> `verify`.

---

## F. File-by-File Specification (Enough to Implement)

For every file in the change list (C), include:

- `path/to/file` -- [added|modified|removed] -- Owner: `<SL-ID>`
  - Purpose
  - Key responsibilities
  - Interfaces exposed
  - Tests required

---

## H. Test Execution Plan

- List test commands by lane or shared component.
- Identify ordering constraints (e.g., run DB migrations before API tests).
- Specify smoke tests vs full suites.

---

## J. Acceptance Criteria

List objective pass/fail criteria for the phase (must be testable).

---

## K. Cross-Repo Dependency Discovery

When the phase depends on external systems or repos, follow this workflow.

### 1. Identify External Dependencies

During architecture design (Section A), identify interfaces that:
- Consume APIs from other services
- Depend on shared libraries from other repos
- Require data or events from external systems
- Need infrastructure changes managed elsewhere

### 2. Check Existing Request Specs

```bash
# List existing external request specs
ls specs/external-requests/

# Search for requests related to a system
grep -r "REQ-<SYSTEM>" specs/external-requests/
```

### 3. Create New Request Specs

If a dependency doesn't have a request spec:

1. Create the request file:
   - Path: `specs/external-requests/<SYSTEM>.md`
   - Use template: `specs/templates/external-requests.md`

2. Assign request ID:
   - Format: `REQ-<SYSTEM>-NNN`
   - Example: `REQ-NOTIFY-001`, `REQ-AUTHLIB-002`

3. Fill in all sections:
   - Summary
   - Rationale
   - Current capability
   - Requested change
   - Interface contract
   - Acceptance criteria
   - Test and validation
   - Compatibility and rollout

### 4. Add Cross-Repo Gates to Phase Plan

For each external dependency, add an `IF-XR-*` gate:

```markdown
## Interface Freeze Gates

### Core Interfaces (IF-0)
- [x] IF-0-P1-AUTH: Authentication service interface

### Cross-Repo Dependencies (IF-XR)
- [ ] IF-XR-P1-NOTIFY-001: Notification service exposes sendEmail endpoint (REQ-NOTIFY-001)
- [ ] IF-XR-P1-AUTHLIB-002: Auth library supports JWT refresh tokens (REQ-AUTHLIB-002)
```

### 5. Track Request Status

In the request spec, update status as it progresses:
- `Draft` - Request created, not yet shared
- `In Review` - Shared with dependency owner
- `Approved` - Owner committed to implementing
- `Shipped` - Implementation complete and available

### 6. Handle Blocked Dependencies

If a cross-repo gate cannot be satisfied:

1. Document the blocker in the phase plan
2. Consider fallback strategies:
   - Feature flags to disable dependent features
   - Mock implementations for development
   - Graceful degradation

3. Add fallback to lane constraints:
```markdown
### SL-NOTIFY -- Notification Integration

**Fallback mode**: If IF-XR-P1-NOTIFY-001 not ready, use console logging
```

---

## L. File Conflict Detection

Before assigning files to swim lanes, check for conflicts.

### 1. List All Files to Modify

From Section C (Exhaustive Change List), extract all file paths:

```bash
# Collect all files mentioned in the change list
FILES=(
  "src/services/auth.ts"
  "src/services/session.ts"
  "src/routes/auth.ts"
  # ...
)
```

### 2. Check for Existing Modifications

```bash
# Check if any files are already modified
git status --short -- "${FILES[@]}"

# Check for uncommitted changes
git diff --name-only -- "${FILES[@]}"
```

If files are already modified:
- They must be committed or stashed before lane execution
- Consider if they belong to an in-progress lane

### 3. Detect Lane Overlap

Build a file-to-lane mapping:

```markdown
| File | Lane |
|------|------|
| src/services/auth.ts | SL-AUTH |
| src/routes/auth.ts | SL-API |
| src/middleware/auth.ts | SL-AUTH, SL-API | <- OVERLAP
```

For overlapping files:
- Assign to ONE lane as primary owner
- Add explicit dependency between lanes
- Document which parts each lane modifies

### 4. Resolve Overlaps

Options:
1. **Sequential execution**: Lane B waits for Lane A to complete
2. **Split the file**: Extract shared code to a new file
3. **Interface boundary**: Define interface in shared file, implement in separate files

Document resolution in Section E (Execution Notes).

---

## M. Output Validation Checklist

Before finalizing the phase plan, verify:

### Structure
- [ ] Document has correct `# <PHASE_ID>: <Phase Name>` heading
- [ ] All required sections (A through J) are present
- [ ] Lane Index & Dependencies section is machine-parseable

### Gates
- [ ] All interface contracts have `IF-*` gates
- [ ] Cross-repo dependencies have `IF-XR-*` gates
- [ ] Gate IDs follow naming convention

### Lanes
- [ ] Each lane has unique ID
- [ ] Each lane has explicit file ownership
- [ ] No unresolved file overlaps
- [ ] Dependencies form a DAG (no cycles)

### Tasks
- [ ] Each task has Task ID, Task Type, Depends On
- [ ] Each task has Tests owned files and Test command(s)
- [ ] Task ordering: test → impl → verify
- [ ] No task modifies files outside its lane

### Acceptance Criteria
- [ ] All criteria are testable (not subjective)
- [ ] Each criterion maps to specific tests
- [ ] No unverifiable "should be good" criteria

---

## Quick Reference

### ID Conventions

| Type | Format | Example |
|------|--------|---------|
| Phase ID | `P<N>` | `P1`, `P2` |
| Lane ID | `SL-<NAME>` | `SL-AUTH`, `SL-API` |
| Task ID | `<PHASE>-<LANE>-<NN>` | `P1-SL-AUTH-01` |
| Interface Gate | `IF-<N>-<PHASE>-<NAME>` | `IF-0-P1-AUTH` |
| Cross-Repo Gate | `IF-XR-<PHASE>-<SYSTEM>-<NNN>` | `IF-XR-P1-NOTIFY-001` |
| Request ID | `REQ-<SYSTEM>-<NNN>` | `REQ-NOTIFY-001` |

### Task Types

| Type | Purpose | Agent |
|------|---------|-------|
| `test` | Write tests before implementation | test-engineer |
| `impl` | Implement production code | lane-executor |
| `verify` | Run tests and check results | test-engineer |

---

## N. Test Scaffolding Integration

For TDD workflows, test files should exist before implementation begins. The planner
can auto-populate the `Tests Owned Files` column.

### Auto-Populate Tests Owned Files

For each `impl` task, derive test file paths from `Files in Scope`:

| Language | Source File | Test File |
|----------|-------------|-----------|
| Python | `src/auth/login.py` | `tests/auth/test_login.py` |
| TypeScript | `src/auth/login.ts` | `src/auth/login.test.ts` |
| Go | `pkg/auth/login.go` | `pkg/auth/login_test.go` |

### Using `/ai-dev-kit:scaffold-tests`

After generating a phase plan, run the scaffolder to populate test stubs:

```bash
# Extract sources from plan and generate scaffolds
/ai-dev-kit:scaffold-tests --from-plan plans/P1-auth.md

# Preview without writing
/ai-dev-kit:scaffold-tests --from-plan plans/P1-auth.md --dry-run
```

### Task Table with Tests Owned Files

Each task table must include the `Tests Owned Files` column:

```markdown
| Task ID | Task Type | Depends On | Files in Scope | Tests Owned Files | Test Command(s) |
|---------|-----------|------------|----------------|-------------------|-----------------|
| P1-SL-AUTH-01 | test | IF-0-P1 | - | tests/auth/test_login.py | pytest tests/auth/test_login.py |
| P1-SL-AUTH-02 | impl | P1-SL-AUTH-01 | src/auth/login.py | tests/auth/test_login.py | pytest tests/auth/test_login.py |
```

### Validation

- [ ] Every `impl` task has non-empty `Tests Owned Files`
- [ ] Test file paths follow project naming convention
- [ ] Test commands are valid for detected framework
- [ ] Test tasks exist for all test files

### Lane Dependencies

Express dependencies with:
- `Depends on: IF-0-P1-AUTH` - needs frozen interface
- `Depends on: SL-DB` - needs another lane complete
- `Blocks: SL-API, SL-UI` - other lanes wait for this

### Parallel Safety

| Value | Meaning |
|-------|---------|
| `yes` | Lane can run in parallel with any other |
| `no` | Lane must run alone (shared files) |
| `mixed` | Some tasks parallel, some sequential |

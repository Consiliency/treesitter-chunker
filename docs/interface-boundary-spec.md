# Interface Boundary Parsing Spec (for External Orchestrator Repo)

## Purpose

This specification defines how a separate orchestrator repository should derive deterministic **interface boundaries** from source code by using `treesitter-chunker` as a dependency.

Scope in this spec is intentionally limited to parsing and boundary extraction. Agent policy, scheduling, and runtime orchestration are out of scope.

## Normative Terms

- **MUST**: required for compliance.
- **SHOULD**: recommended unless a strong reason exists not to.
- **MAY**: optional.

## System Context

The orchestrator:

1. MUST call `chunk_file(..., extract_metadata=True, include_retrieval_metadata=True)` and/or `extract_symbol_graph()` from `treesitter-chunker`.
2. MUST convert extractor output into a canonical Interface Boundary IR (defined below).
3. MUST produce reproducible output for the same repo state + tool versions.

## Inputs

### Required inputs

- Repository root path.
- Commit SHA or equivalent content snapshot identifier.
- Language selection mode:
  - explicit language allowlist, or
  - auto-detect through file extension mapping.

### Optional inputs

- Path include/exclude globs.
- File size limits.
- Maximum parse concurrency.
- Strictness mode (`strict` | `permissive`).

## Required extraction primitives from `treesitter-chunker`

The orchestrator MUST consume these primitives where available:

- structural identity: `definition_id`, `node_id`, `qualified_route`.
- normalized metadata: `kind`, `symbol`, `qualified_name`, `parent_symbol`, `semantic_path`, `signature_text`.
- graph context: symbols and relationships from `extract_symbol_graph()`.

If `definition_id` is unavailable, fallback identity SHOULD be:

1. `module + qualified_name`, then
2. `node_id`.

## Canonical Interface Boundary IR

The orchestrator MUST emit a canonical JSON document with this structure:

```json
{
  "schema_version": "v0.1",
  "repo": {
    "root": "...",
    "commit": "..."
  },
  "nodes": [
    {
      "boundary_id": "...",
      "kind": "module|class|interface|struct|trait|function|method",
      "name": "...",
      "qualified_name": "...",
      "file": "...",
      "line_start": 0,
      "line_end": 0,
      "language": "...",
      "signature": "...",
      "parent_boundary_id": "...",
      "provenance": {
        "definition_id": "...",
        "node_id": "..."
      }
    }
  ],
  "edges": [
    {
      "from": "boundary_id",
      "to": "boundary_id|external_ref",
      "type": "imports|dependencies|calls",
      "resolution": "resolved|ambiguous|unresolved",
      "is_internal": true
    }
  ],
  "stats": {
    "files_processed": 0,
    "nodes_total": 0,
    "edges_total": 0,
    "ambiguous_edges": 0,
    "unresolved_edges": 0
  }
}
```

## Canonicalization rules

To ensure deterministic output, the orchestrator MUST:

1. sort `nodes` by `(file, line_start, kind, name, boundary_id)`.
2. sort `edges` by `(from, to, type, resolution)`.
3. emit UTF-8 JSON with stable key ordering.
4. include `schema_version` and repo snapshot metadata.

## Boundary derivation rules

1. A boundary node MUST map to one extracted symbol-like unit (`module/class/interface/struct/trait/function/method`).
2. `boundary_id` MUST prefer `definition_id` when present.
3. If multiple extractor records map to one boundary candidate, deduplication MUST be deterministic and preserve first record by sorted order.
4. Nodes with missing `name` and missing stable provenance MUST be dropped and counted as skipped.

## Relationship resolution rules

- In `strict` mode:
  - ambiguous targets MUST remain `ambiguous` (no guessed target).
  - unresolved targets MUST remain `unresolved`.
- In `permissive` mode:
  - heuristic fallback MAY be used, but original resolution state MUST be preserved in metadata.

## Error handling and observability

The orchestrator MUST output structured diagnostics:

- parse failures by file/language,
- skipped nodes with reason,
- edge resolution summary,
- extraction duration metrics.

No single-file parse failure should terminate full-repo extraction unless configured `fail_fast=true`.

## Compliance checklist (minimum)

An implementation is compliant only if all are true:

- [ ] Canonical IR shape is emitted with required fields.
- [ ] Deterministic sorting/canonicalization is applied.
- [ ] Boundary IDs use required precedence.
- [ ] Edge resolution state is explicit.
- [ ] Diagnostics include skipped/ambiguous/unresolved counts.

## Out of scope

- Agent ownership policy language.
- Authorization decisions.
- Patch apply/reject workflows.
- Runtime autonomous agent execution.

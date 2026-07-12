# Interface Boundary Specification

This document is the canonical implementation-facing Boundary IR contract for
`treesitter-chunker`. Phase 0 (`SCHEMA`) freezes the syntax-only Boundary IR
baseline around `schema_version == "1.0"` so downstream adapters, serializers,
tests, and external orchestrators have a stable contract to build on.

The repository already implements additional Boundary IR capabilities beyond the
original Phase 0 boundary. Those later contracts remain documented here only as
clearly labeled additive downstream extensions. They are not prerequisites for
completing `SCHEMA`.

## Scope

Phase 0 owns the base data contract for:

- the required top-level Boundary IR object keys;
- stable node identity precedence;
- canonical JSON serialization rules; and
- backward-compatibility policy for downstream consumers.

Boundary IR is a deterministic, language-neutral representation of source
inputs, file records, structural code nodes, relationships, diagnostics,
metrics, and run metadata. The Phase 0 baseline is intentionally syntax-first
and policy-neutral.

## Non-goals

Phase 0 does not require this repository to introduce:

- new adapter behavior;
- relationship-resolution runtime changes;
- observability runtime changes;
- incremental recomputation changes;
- semantic resolver integrations; or
- ownership, authorization, or policy enforcement workflows.

Those concerns live in downstream phases or in external orchestrators.

## Phase 0 Baseline

The syntax-only Boundary IR schema version is `1.0`. The live constant for that
baseline is `BOUNDARY_IR_SCHEMA_VERSION` in `chunker.boundary.types`.

The Phase 0 top-level Boundary IR object keys are frozen as:

- `schema_version`
- `source`
- `files`
- `nodes`
- `edges`
- `diagnostics`
- `metrics`
- `run`

These keys match the live `TOP_LEVEL_KEYS` constant in
`chunker.boundary.types`.

`source` identifies the input repository or source root. `files`, `nodes`,
`edges`, and `diagnostics` are arrays. `metrics` and `run` are objects.

## Identity Precedence

Stable node identity precedence is frozen exactly as:

1. `definition_id`
2. `module + qualified_name`
3. `node_id`

The selected source must be recorded in `node.identity.source` as
`definition_id`, `module + qualified_name`, or `node_id`.

When `definition_id` is available, `node.id` uses it. When it is absent and
`module + qualified_name` is available, `node.id` uses that composed value.
When neither structural identity is available, `node.id` falls back to
`node_id`.

This matches the live identity-selection behavior in
`chunker.boundary.identity.select_node_identity()`.

All three identity sources — `definition_id`, `module + qualified_name`, and
`node_id` — are **Tier-2 occurrence fingerprints** (deterministic hashes of
content and/or location), **not** refactor-stable Tier-1 logical identities. They
change on rename, move, or file-path change, so they identify a snapshot
occurrence, not a durable logical entity. Rename/move continuity (Tier-1) is owned
by the consuming orchestrator, not by Boundary IR. See
`docs/agent-interface-readiness.md` ("Identity model: precedence and
occurrence-vs-logical") and `idmodel` (`_SPINE.md` S2) for the full model.

## Canonical JSON

Canonical JSON for the Phase 0 baseline is frozen as:

- UTF-8 encoding.
- Lexicographic object-key ordering at every object level.
- Deterministic ordering for the four top-level arrays (`files`, `nodes`,
  `edges`, `diagnostics`) and for the explicit set-semantic nested-list
  allow-list below; all other lists preserve insertion order.
- Compact separators equivalent to `,` and `:` with no extra whitespace.
- Exactly one trailing newline for file output.

The canonical ordering rules are:

- `files` sort by `path`, then `id`.
- `nodes` sort by `id`, then `path`, then `span.start_line`.
- `edges` sort by `source`, then `target`, then `type`, then `id`.
- `diagnostics` sort by `path`, then `location.start_line`, then `code`, then
  `id`.

Beyond the four top-level arrays above, exactly three nested **lists** are
declared set-semantic and are sorted (lexicographically, by their string
elements) at construction time. This is the complete, frozen allow-list of
order-insensitive lists:

- `edges[].candidates`
- `nodes[].relationships`
- `files[].diagnostics`

In addition, `metrics.failure_buckets` is an object (a `code -> count` map), not
a list; its keys are emitted in sorted order at construction and are also
normalized by the lexicographic object-key ordering rule above, so its byte
representation is independent of insertion order.

**Every other list preserves insertion order.** Reordering any non-allow-listed
list (for example `params`, `metadata.imports`, `metadata.dependencies`,
`metadata.exports`) is a different logical value and MUST change the canonical
bytes. The serializer never content-sniffs a list to decide whether to sort it:
the only authorized list reorders are the four top-level array sorts and the
three set-semantic nested-list sorts named above.

This matches the live serializer contract in
`chunker.boundary.serialization.dumps_boundary_ir()` and
`canonicalize_boundary_ir()`, which applies the four top-level array sorts and
the three set-semantic nested-list sorts and otherwise preserves insertion order
via `_canonicalize_value`.

## Compatibility

The top-level `schema_version` field is required. Syntax-only output must use
`"1.0"`.

Compatibility policy is frozen as:

- additive-compatible changes stay within the current major version;
- breaking changes require a major version bump; and
- downstream consumers may reject unknown major versions.

Examples of additive-compatible changes include new optional fields, new
diagnostic codes, or new deterministic metadata keys that consumers may ignore.
Examples of breaking changes include removing a required field, renaming a
frozen key, changing canonical ordering, or changing the meaning of an existing
field.

## Additive Downstream Extensions

The repository already contains implemented contracts beyond the Phase 0 base
contract. They remain valid, but they are additive downstream extensions rather
than `SCHEMA` prerequisites.

### Resolution extension

Relationship-resolution status values (`resolved`, `ambiguous`,
`unresolved`) and strict/permissive mode semantics are downstream of the Phase 0
baseline. They extend the frozen top-level schema rather than redefining it.

### Observability extension

Deterministic metrics keys, fixed `run.timings` keys, structured diagnostics,
and `fail_fast` runtime behavior are downstream observability contracts layered
on top of the Phase 0 baseline.

### Incremental extension

Incremental cache keys, warm-run invalidation rules, and impacted-neighbor
recompute behavior are downstream additive contracts. They do not change the
syntax-only `1.0` baseline or the Phase 0 canonical JSON rules.

Each cache key includes the installed `tree-sitter-language-pack` and
`tree-sitter` runtime versions. A grammar-pack or runtime change therefore
invalidates persisted per-file records instead of combining stale records with
new extraction output.

### Parity extension

The parity view represents floats with the ECMAScript
`Number.prototype.toString` spelling before canon serialization: `1e-05` is
`"0.00001"`, `1e-07` is `"1e-7"`, and `-0.0` is `"0"`. Its byte view and
digest are checked against a committed cross-tool golden, so an in-process
agreement cannot silently redefine the contract.

### Semantic extension

Optional semantic resolvers are a downstream additive extension. When callers
explicitly supply semantic resolvers, enriched output may use the additive
semantic schema version `1.1`
(`BOUNDARY_IR_SEMANTIC_SCHEMA_VERSION`). Semantic enrichment remains opt-in and
must not redefine or replace the syntax-only `1.0` baseline.

## Minimal Baseline Example

```json
{"diagnostics":[],"edges":[],"files":[],"metrics":{},"nodes":[],"run":{"canonical":true},"schema_version":"1.0","source":{"kind":"repository","path":"."}}
```

## SCHEMA Contract Checklist

- [x] IF-0-SCHEMA-1: `docs/interface-boundary-spec.md` is the canonical
  implementation-facing Boundary IR contract, and the Phase 0 base contract is
  frozen around syntax-only `schema_version == "1.0"`.
- [x] IF-0-SCHEMA-2: the base top-level Boundary IR object keys are frozen as
  `schema_version`, `source`, `files`, `nodes`, `edges`, `diagnostics`,
  `metrics`, and `run`, matching the live `TOP_LEVEL_KEYS` constant.
- [x] IF-0-SCHEMA-3: identity precedence is frozen exactly as
  `definition_id` -> `module + qualified_name` -> `node_id`, and the chosen
  source is documented as `node.identity.source`.
- [x] IF-0-SCHEMA-4: Canonical JSON rules are frozen and cross-checked against
  the live serializer contract: UTF-8 encoding, lexicographic object-key
  ordering, deterministic list ordering, compact separators, and exactly one
  trailing newline for file output.
- [x] IF-0-SCHEMA-5: Compatibility policy is frozen for downstream consumers:
  additive-compatible changes stay within the major version, breaking changes
  require a major version bump, and consumers may reject unknown major
  versions.
- [x] IF-0-SCHEMA-6: already-implemented later-phase contracts kept in the spec
  are clearly labeled additive downstream extensions, not Phase 0
  prerequisites.

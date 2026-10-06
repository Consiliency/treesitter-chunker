# Interface Boundary Specification

This document is the canonical implementation-facing Boundary IR contract for
`treesitter-chunker`. Current syntax-only output uses `schema_version == "2.0"`,
and opt-in semantic output uses `"2.1"`. The original Phase 0 (`SCHEMA`) contract
used `1.0`; the canonical identity change in chunker 3.0.0 introduced the existing
2.x boundary. Consumers of 1.x documents must re-extract and re-index.

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

The current syntax-only Boundary IR schema version is `2.0`. Its live constant
is `BOUNDARY_IR_SCHEMA_VERSION` in `chunker.boundary.types`. The original Phase 0
key and identity vocabulary remains applicable across the 2.x migration.

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

File records use status `parsed`, `skipped`, or `error`. An unmapped file is
`skipped`; its unknown `language` and `parser` values are null. Parsed and error
records require a string `language`, and a supplied `parser` must be a string.
Null metadata is allowed only for skipped files. Node languages remain strings.

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
`"2.0"`; explicit semantic enrichment uses `"2.1"`. The current published JSON
Schema rejects 1.x documents. The existing major-version migration changed
canonical IDs and bytes; consumers must re-extract and re-index old documents.

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
syntax-only `2.0` baseline or the canonical JSON rules.

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
semantic schema version `2.1`
(`BOUNDARY_IR_SEMANTIC_SCHEMA_VERSION`). Semantic enrichment remains opt-in and
must not redefine or replace the syntax-only `2.0` baseline.

## Minimal Baseline Example

This schema-valid output comes from a Python file containing only
`# A source file with no declarations.` followed by a newline. Volatile source
and run paths are shown as `empty.py`; the tool version is illustrative.

```json
{"diagnostics":[],"edges":[],"files":[{"content_hash":"sha1:7eb4e49617b13df62d2b7cc8f24b036e2493c7b3","diagnostics":[],"id":"62a603819930ab104a88fbe7f15a28da7ab28e86","language":"python","parser":"tree-sitter-python","path":"empty.py","status":"parsed"}],"metrics":{"ambiguous_edges":0,"diagnostics_total":0,"edges_total":0,"failure_buckets":{},"files_failed":0,"files_parsed":1,"files_processed":1,"files_skipped":0,"files_total":1,"graph_failures":0,"metadata_failures":0,"nodes_total":0,"parse_failures":0,"resolved_edges":0,"serialization_failures":0,"unresolved_edges":0},"nodes":[],"run":{"canonical":true,"created_at":null,"options":{"fail_fast":false,"include_retrieval_metadata":true,"include_timings":false,"language":"python","resolution_mode":"strict"},"root":"empty.py","timings":{"graph_assembly_ms":null,"metadata_normalization_ms":null,"parse_ms":null,"resolution_ms":null,"serialization_ms":null,"total_ms":null},"tool":"treesitter-chunker","tool_version":"5.2.0"},"schema_version":"2.0","source":{"kind":"file","path":"empty.py"}}
```

## Historical Phase 0 SCHEMA Contract Checklist

The checklist below records the original Phase 0 1.0 contract. It is historical
acceptance, not a claim that current emitters use 1.0 or a new IF approval.
The current version and migration requirements are described above.

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

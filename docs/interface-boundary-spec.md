# Interface Boundary Specification

This document is the canonical implementation-facing Boundary IR contract for
`treesitter-chunker`. It freezes the schema surface that downstream adapters,
serializers, tests, and policy orchestrators can rely on before runtime export
work begins.

The syntax-only schema version is `1.0`. Output enriched with optional semantic
resolver edges uses the additive semantic schema version `1.1`.

## Scope

Boundary IR is a deterministic, language-neutral representation of source files,
structural code nodes, relationships, extraction diagnostics, deterministic
metrics, and run metadata. The contract is designed to be produced from existing
`CodeChunk` fields, retrieval metadata, and symbol graph output.

The schema is a data interchange contract. It does not require this repository
to implement a policy engine, semantic enrichment, ownership manifest, or patch
authorization workflow.

## Non-goals

Policy engines, ownership manifests, patch authorization, and allow/reject
enforcement live outside `treesitter-chunker`. This repository may emit the
boundary facts those systems consume, but it does not own agent policy decisions.

Semantic enrichment from LSPs, type checkers, or other external analyzers is
optional. This repository defines the hook contract and merge behavior, but it
does not ship mandatory resolver integrations, own policy decisions, or convert
confidence scores into authorization outcomes. The baseline contract remains
useful when only Tree-sitter-derived syntax and normalized metadata are
available.

## Versioning

The top-level `schema_version` field is required. Syntax-only output must use
the string `1.0`. Output produced with explicit semantic resolvers uses `1.1`,
which is additive over the syntax-only schema.

Additive-compatible changes retain the current major version. Examples include
adding optional fields, adding new diagnostic codes, or adding new metadata keys
that consumers may ignore.

Breaking changes require a major version bump. Examples include removing a
required field, changing a field's meaning, changing canonical ordering, or
renaming frozen keys. Downstream consumers may reject unknown major versions
before reading the rest of the document.

Consumers that do not understand semantic enrichment can ignore edge records
where `provenance.source == "semantic"` and continue reading syntax-derived
records where `provenance.source == "syntax"`.

## Top-level Object

The top-level Boundary IR object keys are frozen as:

- `schema_version`
- `source`
- `files`
- `nodes`
- `edges`
- `diagnostics`
- `metrics`
- `run`

`source` identifies the input repository or source root. `files`, `nodes`,
`edges`, and `diagnostics` are arrays. `metrics` and `run` are objects.

## File Records

File records are frozen with these keys:

- `id`: stable file identifier, preferably derived from `compute_file_id()`.
- `path`: repository-relative or configured display path.
- `language`: detected or requested language name.
- `content_hash`: deterministic hash of the file content used for this run.
- `parser`: parser or grammar identifier used for extraction.
- `status`: extraction status such as `parsed`, `skipped`, or `error`.
- `diagnostics`: diagnostic IDs associated with this file.

File statuses are frozen as exactly `parsed`, `skipped`, and `error`. Extraction
continues by default after per-file parse or metadata failures: failed file
records use `status: error`, attach the relevant diagnostic IDs, and successful
records from other files remain in the document. `fail_fast=True` raises on the
first parse, metadata, graph, or serialization failure instead of returning
partial Boundary IR.

## Node Records

Node records are frozen with these keys:

- `id`: canonical node identity for Boundary IR references.
- `identity`: object describing which identity source was selected.
- `definition_id`: content-insensitive definition identity when available.
- `node_id`: content-sensitive chunk identity when available.
- `symbol_id`: symbol identity when available.
- `file_id`: containing file identity.
- `path`: file path for the node.
- `language`: node language.
- `kind`: normalized kind such as `class`, `function`, `method`, or `import`.
- `symbol`: local symbol name when available.
- `qualified_name`: language-neutral qualified symbol name when available.
- `semantic_path`: path-like retrieval identity when available.
- `signature`: normalized signature text when available.
- `span`: object containing line and byte offsets.
- `parent`: parent node identity or `null`.
- `relationships`: relationship IDs or compact relationship summaries known at
  node assembly time.
- `metadata`: additional deterministic extraction metadata.
- `provenance`: extraction source information for audit and debugging.

`span` should contain deterministic source coordinates, including
`start_line`, `end_line`, `byte_start`, and `byte_end` when available.

`metadata` may include normalized retrieval fields already produced by this
repository, including `parent_symbol`, `imports`, `exports`, `dependencies`,
and `semantic_text`.

## Edge Records

Edge records are frozen with these keys:

- `id`: deterministic edge identifier.
- `source`: source node ID.
- `target`: target node ID or unresolved reference string.
- `type`: relationship type such as `imports`, `dependencies`, or `calls`.
- `resolution`: one of `resolved`, `ambiguous`, or `unresolved`.
- `reference`: original normalized reference text.
- `candidates`: possible target IDs for ambiguous or unresolved references.
- `location`: source location for the reference.
- `provenance`: extraction and resolution source information.
- `metadata`: additional deterministic edge metadata.

Strict consumers should use `resolution` instead of inferring certainty from the
shape of `target`.

Resolution status values are frozen as exactly `resolved`, `ambiguous`, and
`unresolved`. Resolution mode values are frozen as exactly `strict` and
`permissive`.

Candidate classification is deterministic:

- exactly one candidate emits `resolution: resolved`;
- multiple candidates emit `resolution: ambiguous`;
- zero candidates emit `resolution: unresolved`.

Candidate IDs are sorted lexicographically before emission. Boundary IR defaults
to strict mode. In strict mode, ambiguous and unresolved edges must not guess a
target node identity: `target` is the normalized reference string and
`candidates` carries possible node IDs only when available. Permissive mode
preserves discovery-friendly references and syntax provenance, records
`resolution_mode: permissive`, and does not emit an enforcement grade.

Syntax-derived edges use `provenance.source: syntax` and record the syntax
resolver and resolution mode. Supplemental semantic edges use
`provenance.source: semantic` and must record:

- `resolver`: stable resolver ID.
- `resolver_version`: resolver implementation version.
- `resolver_api_version`: semantic resolver API version, currently `1.0`.
- `confidence`: numeric confidence in the inclusive range `[0.0, 1.0]`.

Semantic confidence is data only. This repository does not turn confidence into
ownership, authorization, or enforcement policy.

Semantic enrichment is append-only relative to the syntax baseline. It must not
rewrite or delete syntax edges, syntax edge IDs, syntax node IDs, or syntax
provenance. Duplicate semantic results are deduplicated deterministically by
resolver ID, source, target, type, and reference; the highest-confidence result
is retained.

## Diagnostic Records

Diagnostic records are frozen with these keys:

- `id`: deterministic diagnostic identifier.
- `severity`: `info`, `warning`, or `error`.
- `code`: stable diagnostic code.
- `message`: human-readable message.
- `path`: related file path or `null`.
- `location`: source location or `null`.
- `stage`: extraction stage such as `discovery`, `parse`, `metadata`, `graph`,
  `resolution`, `semantic`, or `serialization`.
- `details`: deterministic structured details.

Diagnostic stages are frozen as exactly `discovery`, `parse`, `metadata`,
`graph`, `resolution`, `semantic`, and `serialization`. Diagnostic IDs are
deterministic hashes over `stage`, `code`, `path`, `location`, `message`, and
canonicalized `details`; they must not depend on encounter-order indexes.

Semantic resolver failures emit `boundary.semantic_resolver_error` diagnostics
when `fail_fast=False`. With `fail_fast=True`, resolver exceptions are raised.
Non-fail-fast semantic failures preserve baseline syntax records.

## Metrics

`metrics` contains deterministic counters and summaries. It must not contain
volatile timing values when byte-identical canonical output is requested.

Required counter keys are:

- `files_total`
- `files_processed`
- `files_parsed`
- `files_skipped`
- `files_failed`
- `nodes_total`
- `edges_total`
- `diagnostics_total`
- `resolved_edges`
- `ambiguous_edges`
- `unresolved_edges`
- `parse_failures`
- `metadata_failures`
- `graph_failures`
- `serialization_failures`
- `failure_buckets`

`failure_buckets` is a lexicographically sorted diagnostic-code-to-count
mapping. Additional deterministic counters may be added without a major version
bump. Volatile timings must be omitted, set to `null`, or emitted only in
opt-in run metadata.

## Run Metadata

`run` describes deterministic run context needed to interpret the output.

Required keys are:

- `tool`: tool name.
- `tool_version`: tool version when known.
- `root`: normalized source root display path.
- `created_at`: timestamp or `null`.
- `canonical`: boolean indicating whether canonical serialization was requested.
- `options`: deterministic option values that affect output shape.
- `timings`: fixed timing keys for extraction stages.

`run.options` records `include_retrieval_metadata`, `language`,
`resolution_mode`, `fail_fast`, and `include_timings`. `resolution_mode` records
the mode used to shape relationship output. Boundary IR generation defaults to
`strict`; symbol graph extraction defaults to `permissive` for legacy discovery
compatibility.

`run.timings` always contains exactly `parse_ms`,
`metadata_normalization_ms`, `graph_assembly_ms`, `resolution_ms`,
`serialization_ms`, and `total_ms`. Values are `null` by default so canonical
output remains byte-identical across double runs. When `include_timings=True`,
values are nonnegative millisecond numbers.

When canonical byte-identical output is requested, volatile fields such as wall
clock durations, process IDs, temporary paths, and generated timestamps must be
omitted, set to `null`, or moved to a non-canonical observability report. If
`created_at` is present in canonical output, it must be caller-provided and
stable for the compared runs.

## Optional Semantic Enrichment

`chunker.boundary` exports the semantic resolver contract:

- `SEMANTIC_RESOLVER_API_VERSION = "1.0"`
- `BOUNDARY_IR_SEMANTIC_SCHEMA_VERSION = "1.1"`
- `SemanticResolverContext`
- `SemanticEdge`
- `SemanticResolver`

A `SemanticResolver` exposes stable `resolver_id`, `resolver_version`, and
`supported_languages`, and implements `enrich(context) -> Iterable[SemanticEdge]`.
Resolvers are not imported by baseline extraction; callers or explicitly
registered plugins must provide them.

`SemanticResolverContext` contains the source root, language, resolution mode,
file records, node records, syntax edges, and current diagnostics. Resolvers
must treat the context as read-only.

`SemanticEdge` requires source node ID, relationship type, resolution status,
reference, resolver identity, confidence, and either a target node ID or
reference target. Candidate IDs are sorted deterministically. Confidence accepts
only values in `[0.0, 1.0]`.

The public API is:

```python
extract_boundary_ir(
    path,
    language=None,
    *,
    canonical=True,
    created_at=None,
    resolution_mode="strict",
    fail_fast=False,
    include_timings=False,
    incremental=False,
    cache_dir=None,
    force_rebuild=False,
    semantic_resolvers=None,
    semantic_min_confidence=0.0,
)
```

`semantic_resolvers=None` preserves the exact syntax-only execution path,
`schema_version == "1.0"`, `run.options`, cache key input, and canonical JSON.
When resolvers are supplied, semantic edges below `semantic_min_confidence` are
filtered, semantic edge IDs are added to the source node `relationships` list,
and the output uses schema version `1.1`.

## Incremental Boundary Cache

`extract_boundary_ir(path, language=None, *, canonical=True, created_at=None,
resolution_mode="strict", fail_fast=False, include_timings=False,
incremental=False, cache_dir=None, force_rebuild=False, semantic_resolvers=None,
semantic_min_confidence=0.0)` is the public Boundary IR API.
`incremental=False` preserves the default non-incremental execution path and
keeps `run.options` unchanged when `semantic_resolvers=None`.

`incremental=True` uses persisted JSON cache records for per-file Boundary IR
slices and symbol facts. If `cache_dir` is provided, cache files are written
there. Otherwise, they are written under the user cache namespace for the
repository root. Cache paths, cache hit/miss stats, recomputed path sets, and
benchmark measurements are diagnostics only; they are not canonical Boundary IR
fields and must not appear in stdout JSON.

Boundary cache keys are frozen as `boundary:v1:<sha256>`. The hash input is
canonical JSON with exactly these fields, in this contract order:

- `path`
- `content_hash`
- `language`
- `grammar_version`
- `tool_version`
- `schema_version`
- `resolution_mode`
- `fail_fast`
- `include_retrieval_metadata`

`created_at`, `canonical`, `include_timings`, `incremental`, `cache_dir`, and
`force_rebuild` are excluded from cache-key input. They also do not enter
canonical Boundary IR except for the existing `created_at`, `canonical`, and
`include_timings` run metadata fields.

When semantic resolvers are supplied, the incremental cache key hash input is
extended additively with `semantic_schema_version`, `semantic_resolvers`, and
`semantic_min_confidence`. Syntax-only cache keys do not include those fields,
so syntax-only records are not reused for enriched output and enriched records
do not change baseline cache identity.

Warm-run invalidation recomputes added files, deleted files, content/key
mismatches, malformed cache records, and impacted neighbors. Impacted neighbors
are the deterministic union of changed files, relationship-sensitive endpoints
from previous and current records, and reverse import, dependency, or call
references whose module or symbol candidates mention changed files. Returned
path lists are normalized to POSIX separators and sorted lexicographically.

For the same repository snapshot and options with `include_timings=False`, cold
incremental output and warm incremental output must serialize to byte-identical
`dumps_boundary_ir()` bytes. `force_rebuild=True` bypasses cache reads and
refreshes all records without changing canonical output.

## Identity Precedence

Node identity precedence is frozen as:

1. `definition_id`
2. `module + qualified_name`
3. `node_id`

The selected source must be recorded in `node.identity.source` as
`definition_id`, `module + qualified_name`, or `node_id`.

When `definition_id` is available, `node.id` must use it. When it is missing and
`module + qualified_name` is available, `node.id` must use that composed value.
When neither structural identity is available, `node.id` must fall back to
`node_id`.

## Canonical JSON

Canonical JSON serialization is frozen as:

- UTF-8 encoding.
- Lexicographic object key ordering at every object level.
- Deterministic list ordering for `files`, `nodes`, `edges`, `diagnostics`, and
  any nested list that affects output equality.
- Compact separators equivalent to `,` and `:` with no extra whitespace.
- Exactly one trailing newline for file output.

Canonical ordering rules:

- `files` sort by `path`, then `id`.
- `nodes` sort by `id`, then `path`, then `span.start_line`.
- `edges` sort by `source`, then `target`, then `type`, then `id`.
- `diagnostics` sort by `path`, then `location.start_line`, then `code`, then
  `id`.
- `candidates` and other ID lists sort lexicographically unless a field-specific
  semantic order is documented in a later compatible revision.

## Conformance Fixtures

The P0 Boundary IR conformance language IDs are exactly `python`, `javascript`,
`typescript`, and `go`. JavaScript and TypeScript are separate language IDs for
fixture and assertion purposes even though they share a language-family roadmap
entry.

Fixture source repositories live under
`tests/fixtures/boundary_ir/repos/<language>/`. Checked golden snapshots live
under `tests/fixtures/boundary_ir/golden/<language>.json`.

Golden snapshot comparison uses `dumps_boundary_ir()` canonical JSON. The only
field normalized before snapshot comparison is `run.tool_version`, which is set
to a sentinel value in checked snapshots. `files`, `nodes`, `edges`,
`diagnostics`, `metrics`, `run.options`, `run.timings`, and `created_at` are not
normalized.

Double-run determinism checks extract the same fixture input twice in one
process and assert byte-identical `dumps_boundary_ir(extract_boundary_ir(...))`
output with no normalization.

Required-field validation covers top-level fields, source metadata, file
records, node records, edge records, diagnostic records, metrics, and run
metadata. Language parity assertions cover node `kind`, `qualified_name`,
callable signatures, metadata `imports` and `dependencies`, `calls` edges, and
`resolved`, `ambiguous`, and `unresolved` resolution states where syntax-derived
extraction can produce them. Language-specific syntax-only limitations must be
recorded in `tests/fixtures/boundary_ir/manifest.json`.

The fast local CI-equivalent smoke batch includes the deterministic Boundary IR
golden conformance gate through `scripts/run_ci_smoke.py`.

## Minimal Example

```json
{"diagnostics":[],"edges":[{"candidates":[],"id":"edge:example-source:example-target:imports","location":{"byte_end":12,"byte_start":0,"end_line":1,"start_line":1},"metadata":{},"provenance":{"resolution_mode":"strict","source":"syntax"},"reference":"example.module","resolution":"resolved","source":"def:example-source","target":"def:example-target","type":"imports"}],"files":[{"content_hash":"sha1:placeholder","diagnostics":[],"id":"file:example","language":"python","parser":"tree-sitter-python","path":"src/example.py","status":"parsed"}],"metrics":{"ambiguous_edges":0,"diagnostics_total":0,"edges_total":1,"failure_buckets":{},"files_failed":0,"files_parsed":1,"files_processed":1,"files_skipped":0,"files_total":1,"graph_failures":0,"metadata_failures":0,"nodes_total":1,"parse_failures":0,"resolved_edges":1,"serialization_failures":0,"unresolved_edges":0},"nodes":[{"definition_id":"def:example-source","file_id":"file:example","id":"def:example-source","identity":{"source":"definition_id","value":"def:example-source"},"kind":"function","language":"python","metadata":{"dependencies":[],"exports":[],"imports":["example.module"],"parent_symbol":null,"semantic_text":"function example"},"node_id":"node:placeholder","parent":null,"path":"src/example.py","provenance":{"extractor":"chunk_file","metadata":"retrieval"},"qualified_name":"example","relationships":["edge:example-source:example-target:imports"],"semantic_path":"src/example.py::example","signature":"example()","span":{"byte_end":42,"byte_start":0,"end_line":3,"start_line":1},"symbol":"example","symbol_id":"sym:placeholder"}],"run":{"canonical":true,"created_at":null,"options":{"fail_fast":false,"include_retrieval_metadata":true,"include_timings":false,"language":"python","resolution_mode":"strict"},"root":".","timings":{"graph_assembly_ms":null,"metadata_normalization_ms":null,"parse_ms":null,"resolution_ms":null,"serialization_ms":null,"total_ms":null},"tool":"treesitter-chunker","tool_version":"placeholder"},"schema_version":"1.0","source":{"kind":"repository","path":"."}}
```

## Compatibility

Consumers should accept unknown optional fields within a known major version
unless they operate in a stricter validation mode. Consumers may reject unknown
major versions, missing required frozen keys, non-canonical ordering, or outputs
that mix volatile timing data into canonical deterministic exports.

Compatibility notes for future revisions must identify whether changes are
additive-compatible or breaking.

Migration note for semantic enrichment: syntax-only consumers can continue to
require `schema_version == "1.0"`. Consumers that accept `1.1` should either
ignore `provenance.source == "semantic"` edges or explicitly trust resolver IDs,
versions, API version, and confidence according to their own policy.

## Contract Checklist

- [x] IF-0-SCHEMA-1: `docs/interface-boundary-spec.md` is the canonical Boundary
  IR contract and defines `schema_version` with initial version `1.0`.
- [x] IF-0-SCHEMA-2: top-level keys are `schema_version`, `source`, `files`,
  `nodes`, `edges`, `diagnostics`, `metrics`, and `run`.
- [x] IF-0-SCHEMA-3: file records define `id`, `path`, `language`,
  `content_hash`, `parser`, `status`, and `diagnostics`.
- [x] IF-0-SCHEMA-4: node records define `id`, `identity`, `definition_id`,
  `node_id`, `symbol_id`, `file_id`, `path`, `language`, `kind`, `symbol`,
  `qualified_name`, `semantic_path`, `signature`, `span`, `parent`,
  `relationships`, `metadata`, and `provenance`.
- [x] IF-0-SCHEMA-5: edge records define `id`, `source`, `target`, `type`,
  `resolution`, `reference`, `candidates`, `location`, `provenance`, and
  `metadata`.
- [x] IF-0-SCHEMA-6: diagnostic records define `id`, `severity`, `code`,
  `message`, `path`, `location`, `stage`, and `details`.
- [x] IF-0-SCHEMA-7: metrics and run metadata separate deterministic counters
  from volatile timing fields.
- [x] IF-0-SCHEMA-8: identity precedence is `definition_id` ->
  `module + qualified_name` -> `node_id`, with the chosen source recorded in
  `node.identity.source`.
- [x] IF-0-SCHEMA-9: Canonical JSON requires UTF-8, lexicographic object key
  ordering, deterministic list ordering, compact separators, and exactly one
  trailing newline for file output.
- [x] IF-0-SCHEMA-10: schema evolution policy keeps additive-compatible changes
  on the same major version, requires major bumps for breaking changes, and
  permits downstream consumers to reject unknown major versions.
- [x] IF-0-RESOLUTION-3: relationship resolution exposes `resolved`,
  `ambiguous`, and `unresolved` states with strict/permissive mode semantics.
- [x] IF-0-RESOLUTION-3A: public resolution values are exactly
  `ResolutionStatus = Literal["resolved", "ambiguous", "unresolved"]` and
  `ResolutionMode = Literal["strict", "permissive"]`, exported from
  `chunker.boundary`.
- [x] IF-0-RESOLUTION-3B: `extract_symbol_graph(path, language=None,
  resolution_mode="permissive")` preserves legacy relationship fields and adds
  `reference`, `resolution`, `candidates`, `resolution_mode`, and syntax
  provenance.
- [x] IF-0-RESOLUTION-3C: candidate classification is deterministic and
  candidate IDs are sorted lexicographically.
- [x] IF-0-RESOLUTION-3D: `extract_boundary_ir(path, language=None, *,
  canonical=True, created_at=None, resolution_mode="strict")` emits normalized
  reference targets for ambiguous and unresolved edges.
- [x] IF-0-RESOLUTION-3E: Boundary IR metrics count resolved, ambiguous, and
  unresolved edges from emitted edge statuses, and `run.options.resolution_mode`
  records the selected mode.
- [x] IF-0-CONFORMANCE-4: golden fixture and double-run determinism test
  contract is frozen for Python, JavaScript/TypeScript, and Go.
- [x] IF-0-CONFORMANCE-4A: P0 conformance language IDs are exactly `python`,
  `javascript`, `typescript`, and `go`.
- [x] IF-0-CONFORMANCE-4B: fixture source roots live under
  `tests/fixtures/boundary_ir/repos/<language>/` and golden snapshots live under
  `tests/fixtures/boundary_ir/golden/<language>.json`.
- [x] IF-0-CONFORMANCE-4C: golden comparison uses `dumps_boundary_ir()`
  canonical JSON with only `run.tool_version` normalized to a sentinel.
- [x] IF-0-CONFORMANCE-4D: double-run determinism asserts byte-identical
  canonical JSON output for the same fixture input and language in one process.
- [x] IF-0-CONFORMANCE-4E: required-field validation covers top-level fields,
  file records, node records, edge records, diagnostic records, metrics, and run
  metadata.
- [x] IF-0-CONFORMANCE-4F: per-language parity assertions cover node `kind`,
  `qualified_name`, signatures, metadata `imports` and `dependencies`, `calls`
  edges, and available resolution states.
- [x] IF-0-CONFORMANCE-4G: `scripts/run_ci_smoke.py` includes the deterministic
  Boundary IR conformance gate in the fast local CI-equivalent smoke batch.
- [x] IF-0-OBSERVABILITY-5: Boundary IR exposes deterministic diagnostics,
  metrics, default recovery, fail-fast behavior, and opt-in run timings.
- [x] IF-0-OBSERVABILITY-5A: `extract_boundary_ir(path, language=None, *,
  canonical=True, created_at=None, resolution_mode="strict", fail_fast=False,
  include_timings=False)` is the public Boundary IR API contract, and
  `extract_symbol_graph(..., fail_fast=False)` preserves legacy default
  behavior.
- [x] IF-0-OBSERVABILITY-5B: `run.timings` contains `parse_ms`,
  `metadata_normalization_ms`, `graph_assembly_ms`, `resolution_ms`,
  `serialization_ms`, and `total_ms`; values are `null` unless
  `include_timings=True`.
- [x] IF-0-OBSERVABILITY-5C: `run.options` records
  `include_retrieval_metadata`, `language`, `resolution_mode`, `fail_fast`, and
  `include_timings`.
- [x] IF-0-OBSERVABILITY-5D: metrics include file, failure, edge, diagnostic,
  and lexicographically sorted failure bucket counters.
- [x] IF-0-OBSERVABILITY-5E: diagnostics keep frozen keys and deterministic IDs
  derived from canonical diagnostic content.
- [x] IF-0-OBSERVABILITY-5F: default extraction continues after parser or
  metadata failures and records failed file diagnostics.
- [x] IF-0-OBSERVABILITY-5G: `fail_fast=True` raises on parser, metadata, graph,
  or serialization failures without returning partial Boundary IR.
- [x] IF-0-OBSERVABILITY-5H: the `boundary` CLI exposes `--fail-fast`,
  `--include-timings`, and `--summary` without polluting stdout JSON.
- [x] IF-0-INCREMENTAL-6: Boundary cache key format, warm-run invalidation
  rules, and impacted-neighbor recomputation contract are frozen.
- [x] IF-0-INCREMENTAL-6A: Boundary cache keys use `boundary:v1:<sha256>` over
  exactly `path`, `content_hash`, `language`, `grammar_version`, `tool_version`,
  `schema_version`, `resolution_mode`, `fail_fast`, and
  `include_retrieval_metadata`.
- [x] IF-0-INCREMENTAL-6B: `extract_boundary_ir()` exposes `incremental`,
  `cache_dir`, and `force_rebuild` as additive keyword-only options.
- [x] IF-0-INCREMENTAL-6C: incremental mode stores JSON cache records under the
  selected cache directory and keeps cache diagnostics out of canonical Boundary
  IR.
- [x] IF-0-INCREMENTAL-6D: warm runs invalidate added, deleted, changed,
  malformed, and forced records deterministically.
- [x] IF-0-INCREMENTAL-6E: impacted neighbors include reverse import,
  dependency, and call references that mention changed modules or symbols.
- [x] IF-0-INCREMENTAL-6F: cold and warm incremental runs serialize to
  byte-identical canonical JSON when `include_timings=False`.
- [x] IF-0-INCREMENTAL-6G: deterministic fixture coverage proves warm runs
  reprocess fewer files without relying on wall-clock-only assertions.
- [x] IF-0-SEMANTIC-7: Optional semantic enrichment plugin interface,
  provenance, confidence, and schema migration contract are frozen.
- [x] IF-0-SEMANTIC-7A: Semantic resolver API version is `1.0`; the public
  contract exposes `SemanticResolver`, `SemanticResolverContext`, and
  `SemanticEdge` from `chunker.boundary`.
- [x] IF-0-SEMANTIC-7B: `SemanticResolver` requires stable `resolver_id`,
  `resolver_version`, `supported_languages`, and `enrich(context)`.
- [x] IF-0-SEMANTIC-7C: `extract_boundary_ir()` exposes additive
  `semantic_resolvers` and `semantic_min_confidence` keyword-only parameters,
  while `semantic_resolvers=None` preserves syntax-only output.
- [x] IF-0-SEMANTIC-7D: Semantic edges use `provenance.source == "semantic"`
  with resolver identity, resolver API version, and confidence in `[0.0, 1.0]`.
- [x] IF-0-SEMANTIC-7E: Semantic enrichment never rewrites syntax edges, syntax
  edge IDs, syntax node IDs, or syntax-first ordering.
- [x] IF-0-SEMANTIC-7F: Resolver errors emit deterministic
  `boundary.semantic_resolver_error` diagnostics unless `fail_fast=True`.
- [x] IF-0-SEMANTIC-7G: Syntax-only output keeps schema `1.0`; enriched output
  uses the additive semantic schema version with migration notes for consumers.
- [x] IF-0-SEMANTIC-7H: Semantic confidence is data only and is not converted
  into ownership, authorization, or enforcement policy in this repository.

# Agent Interface Ownership Readiness (Repository Assessment)

> This document is a readiness assessment.
> The canonical Phase 0 Boundary IR contract now lives in this repository:
> `docs/interface-boundary-spec.md`.
> The execution plan lives in:
> `docs/interface-boundary-roadmap.md`.

This document evaluates how ready `treesitter-chunker` is to support
**agent-oriented code surface ownership** enforced via **AST-derived
boundaries**.

## Bottom line

This repository is a strong foundation for an AST-first ownership system, but it is currently optimized for chunking, metadata enrichment, and relationship inference rather than strict policy enforcement. The primitives you need already exist (stable IDs, symbol extraction, relationship graphs, multi-language adapters), while policy/runtime guardrails are still missing.

## Should this live in this repo or above it?

Recommendation: keep ownership-policy enforcement in a **separate orchestrator project** and use `treesitter-chunker` as a dependency.

Why:

- This package's primary contract is extraction/chunking and language support.
- Ownership policy and multi-agent authorization is a higher-level orchestration concern.
- Keeping policy external lets you iterate policy rules and governance models without coupling them to parser/chunker release cadence.

Reasonable split:

- `treesitter-chunker` owns AST parsing, symbol extraction, metadata normalization, and graph export.
- The orchestrator owns agent manifests, policy evaluation, patch validation, and allow/reject enforcement.

## What is already in place

### 1) AST ingestion and multi-language coverage

- Core processing is Tree-sitter-based and language-aware, with dynamic language discovery and plugin support.
- The architecture is explicitly modular around parser management, chunk extraction, and language plugins.

**Implication for ownership model:** You already have a production AST ingestion plane suitable for deterministic, repeatable extraction.

### 2) Stable identity primitives

- `CodeChunk` includes `node_id`, `file_id`, `symbol_id`, `qualified_route`, and `definition_id`.
- `definition_id` is content-insensitive (it survives body edits) but is derived
  from `file_path + language + qualified_route`, so it is an **occurrence
  fingerprint**, not a durable logical-entity identity: it changes on rename, on
  move to a different structural location, and on any file-path change. It is a
  **Tier-2** identity (content/location evidence), not a refactor-stable
  **Tier-1** identity.

**Implication for ownership model:** You can key on these structural fingerprints
to test whether *this occurrence* of a definition matches a stored snapshot, but
you cannot rely on them to follow a definition across a rename or move. Durable
rename/move continuity (Tier-1) must be owned by the consuming orchestrator
(`spec`), which maintains a correspondence map on top of these Tier-2 IDs. See
the identity model in `idmodel` (`_SPINE.md` S2).

#### Identity model: precedence and occurrence-vs-logical

All five Boundary-IR identity fields — `definition_id`, `node_id`, `file_id`,
`symbol_id`, and the composed `module + qualified_name` key — are **Tier-2
occurrence fingerprints**. Each is a deterministic hash of content and/or
location; none of them is a refactor-stable Tier-1 logical-entity identity. A
rename, a move, or a file-path change produces a *different* fingerprint for what
is logically the same entity. Treat them as evidence that two occurrences are the
same snapshot, not as proof that two snapshots are the same logical entity.

**Node identity precedence.** `chunker.boundary.identity.select_node_identity()`
picks `node.id` and records the chosen source in `node.identity.source` in this
frozen order:

1. `definition_id` (when present on the chunk);
2. `module + qualified_name` (when both metadata fields are present);
3. `node_id` (fallback).

This is a precedence among Tier-2 fingerprints — choosing an earlier source does
not upgrade the result to Tier-1. The same precedence is frozen in
`docs/interface-boundary-spec.md`.

**How each ID is derived** (see `chunker/types.py`):

- `definition_id = sha1("def:" + file_path + "|" + language + "|" + qualified_route)`.
  Body-stable, but breaks on rename, move, or file-path change — its own
  docstring states this, and `tests/test_definition_id.py` locks the behavior in.
  For anonymous definitions the `qualified_route` element falls back to a
  line-brittle `"<kind>:anon@<start_line>"` form (`chunker/core.py:562`,
  `chunker/streaming.py:111`), so inserting a line above an anonymous definition
  changes its `definition_id`.
- `node_id = sha1(file_path + "|" + language + "|" + route + "|" + text_hash16(content))`.
  Content-sensitive. Because the key is `(file_path, language, route,
  content-hash)` with no positional disambiguator, two sibling nodes that share a
  parent route and have byte-identical content (e.g. two anonymous siblings with
  the same body) hash to the **same** `node_id` — a latent collision. Consumers
  that need to distinguish such siblings must not rely on `node_id` alone.
- `file_id = sha1("file:" + file_path)` and
  `symbol_id = sha1("sym:" + language + ":" + file_path + ":" + symbol_name)` are
  location/name fingerprints with the same Tier-2 caveats.

**Hash-width recommendation (MEDIUM).** All of the above use SHA-1, and
`compute_text_hash16` (`chunker/types.py:32`) further truncates SHA-1 to 16 hex
characters (64 bits) before folding it into `node_id`. SHA-1 is collision-prone
and 64 bits is well within practical collision range for large corpora. The
recommended content-identity primitive is an **untruncated SHA-256**, which
aligns with the spine's single-hash decision (`_SPINE.md`). This is a
content-identity hardening recommendation, not a Phase 0 blocker, but it should
land with the MAJOR identity revision.

### 3) Language-agnostic retrieval metadata normalization

- The core metadata pipeline normalizes kind/symbol/qualified_name/semantic_path and dependency-style fields in a language-agnostic shape.

**Implication for ownership model:** This is already a near-IR substrate. You can promote this retrieval metadata into a formal ownership IR with fewer transformations.

### 4) Existing symbol graph extraction

- `extract_symbol_graph()` already builds a graph-like structure with symbols, internal/external relationships, imports/dependencies/calls, and per-symbol lookup records.
- Symbol IDs currently combine module and qualified names where available.

**Implication for ownership model:** The repo already has an initial “program graph projection” that can seed ownership checks and policy evaluation.

### 5) Export pathway for graph consumers

- Semantic lens export maps chunk node kinds and relationship kinds into a normalized bundle model.

**Implication for ownership model:** You can either keep policy local or export to an external policy/graph engine without inventing a fresh interchange format from scratch.

## Gaps that block deterministic enforcement today

### 1) No first-class ownership policy engine

There is no built-in concept of:

- agent-to-symbol ownership mapping,
- allowed/forbidden cross-boundary calls,
- reject/allow decisions over proposed code edits.

### 2) Relationship inference has heuristic edges

Current relationship resolution includes tokenized candidate matching and unique-name heuristics. That is useful for discovery, but policy enforcement should avoid heuristic ambiguity at decision time.

### 3) Limited semantic guarantees

Tree-sitter coverage is strong, but this repo does not currently provide full type/binding resolution for authoritative call-target disambiguation in all languages.

### 4) No patch-to-IR validator workflow

There is no built-in gate that:

1. parses a patch,
2. maps edits to structural symbol identities,
3. enforces ownership policy,
4. returns machine-verifiable allow/reject outcomes.

## Recommended architecture using this repo as a dependency

Use `treesitter-chunker` as the **front-end extractor dependency**, then add a slim policy service layer:

1. **Ingest** with `chunk_file(..., extract_metadata=True, include_retrieval_metadata=True)` and/or `extract_symbol_graph()`.
2. **Normalize to ownership IR** using the structural fingerprints
   (`definition_id` preferred, fallback to module+qualified_name). These are
   Tier-2 occurrence identities (content/location fingerprints), **not**
   refactor-stable logical identities — the orchestrator owns rename/move
   continuity on top of them (a Tier-1 correspondence map), since
   `definition_id` breaks on rename/move (see "Stable identity primitives" above
   and the identity-precedence notes below).
3. **Attach policy** via a separate manifest (e.g., `agent_policy.yaml`) mapping agent scopes and allowed edge types.
4. **Validate edits** by parsing changed files and reconciling changed definitions against policy.
5. **Fail closed** for unresolved symbol mappings in enforcement mode (log separately for triage).

## Suggested near-term implementation phases

### Phase 1: Deterministic ownership MVP

- Define ownership IR schema from existing chunk metadata + symbol graph output.
- Use `definition_id` and `qualified_name` as canonical node keys.
- Implement read-only report mode (`violations` list only).

### Phase 2: Pre-merge enforcement mode

- Add strict policy checker that fails when modified symbols are outside agent scope.
- Only allow relationship checks when target resolution is deterministic; otherwise classify as unresolved and fail closed (configurable).

### Phase 3: Optional semantic upgrades

- Use the optional Boundary IR semantic resolver API for high-confidence edge
  disambiguation where callers explicitly provide LSP/type-checker augmentation.
- Keep enforcement decisions in the policy layer above this package; semantic
  confidence is resolver provenance data, not authorization.

## Practical readiness score

- **Extractor readiness:** High
- **IR readiness:** Medium-high (close, not formalized)
- **Policy enforcement readiness:** Low-medium (needs new module)
- **Cross-language viability:** Medium-high (with per-language adapters)

Overall: **good dependency choice** for bootstrapping an AST-governed agent ownership system, as long as you plan to build a dedicated policy/enforcement layer on top.

## Optimization gaps to fill in `treesitter-chunker` itself

If the goal is to make this package maximally ready as a dependency for deterministic agent systems, these are the highest-leverage improvements:

### 1) Determinism hardening for symbol/edge resolution

- Add a strict mode that disallows heuristic fallback in relationship resolution when targets are ambiguous.
- Emit explicit resolution status (`resolved`, `ambiguous`, `unresolved`) for every edge candidate.
- Support fail-closed exports for downstream policy engines.

### 2) First-class IR export mode

- Promote current normalized metadata + symbol graph into the documented,
  versioned Boundary IR schema in `docs/interface-boundary-spec.md`, treating
  the Phase 0 syntax-only baseline as the canonical contract and later runtime
  behavior as additive extensions.
- Add schema versioning and compatibility checks for downstream consumers.
- Guarantee canonical ordering of nodes/edges in output for reproducible diffs.

### 3) Incremental graph recomputation

- Recompute symbols/relationships only for changed files + impacted neighbors.
- Persist index artifacts keyed by file hash + grammar version.
- Add a “cold vs warm graph build” benchmark target in CI smoke tooling.

Status: implemented for Boundary IR incremental mode. Cache keys include path,
content hash, language, grammar/tool/schema versions, resolution mode,
`fail_fast`, and retrieval metadata mode. Warm runs reuse valid per-file records,
recompute changed files and impacted neighbors, and preserve canonical stdout
JSON byte identity when timings are disabled.

### 4) Stronger cross-language extraction contracts

- Tighten per-language conformance tests for `kind`, `qualified_name`, signatures, imports/dependencies/calls.
- Require extractor contract fixtures for new languages before merge.
- Add parity score reporting to prevent regressions in less-common grammars.

### 5) Better observability for large-repo runs

- Boundary IR now emits deterministic counters for skipped files, failed files,
  parse failures, graph failures, unresolved edges, ambiguous edges, and failure
  buckets.
- Boundary IR now includes fixed `run.timings` keys with `null` defaults and
  opt-in measured values through `include_timings=True`.
- The `boundary` CLI now provides `--summary`, `--include-timings`, and
  `--fail-fast` for policy pipeline diagnostics without polluting stdout JSON.
- The `boundary` CLI now provides `--incremental`, `--cache-dir`, and
  `--force-rebuild` for persistent warm-run reuse without adding cache stats to
  canonical JSON.

### 6) Optional semantic augmentation hooks

- Boundary IR now defines optional semantic resolver hooks exposed from
  `chunker.boundary`.
- `extract_boundary_ir(..., semantic_resolvers=None)` preserves the syntax-only
  baseline; callers opt in by passing resolver objects or discovering them from
  explicitly registered language plugins.
- Enriched edges record `provenance.source == "semantic"`, resolver identity,
  resolver API version, and confidence. Downstream policy decides whether to
  trust them.

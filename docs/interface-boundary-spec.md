# Interface Boundary Specification

This document is the canonical implementation-facing Boundary IR contract for
`treesitter-chunker`. Current syntax-only output uses `schema_version == "3.0"`,
and opt-in semantic output uses `"3.1"`. The 3.x boundary makes canonical
definition-derived occurrence IDs authoritative across symbol graphs and
Boundary IR relationship ownership. Consumers of earlier documents must
re-extract, re-index, and rebuild ID-based joins and incremental caches.

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

The current syntax-only Boundary IR schema version is `3.0`. Its live constant
is `BOUNDARY_IR_SCHEMA_VERSION` in `chunker.boundary.types`. The original Phase 0
key and identity vocabulary remains applicable across the 3.x migration.

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
When multiple chunks select the same base identity, their occurrence IDs are
the base followed by stable `#1`, `#2`, and later suffixes in extraction order.
Occurrences are counted across all extracted chunks before symbol-graph kind
filtering. Exact occurrence IDs are indexed before qualified-name and symbol
aliases, so aliases cannot steal exact graph or Boundary edge ownership.
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
`"3.0"`; explicit semantic enrichment uses `"3.1"`. The current published JSON
Schema rejects earlier documents. This major-version migration changes graph
keys, relationship endpoints and canonical bytes; consumers must re-extract and
re-index old documents.

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

Imports and dependencies remain deduplicated by source, target, relationship
type and normalized reference. Calls instead preserve every recognized syntax
site. The public symbol graph exposes resolution-independent `call_facts`; each
fact contains its canonical caller and file, exact callee source slice, full-call
and callee half-open UTF-8 byte spans, actual 1-based line bounds, call kind and
deterministic full-SHA-1 `call:` ID. Identical calls at different sites and calls
whose heuristic target is their own source both survive. The resolved target and
candidate set annotate a fact but do not participate in its identity.

Byte offsets and exact slices refer to the UTF-8 buffer parsed by core
extraction. For valid UTF-8 input this is the original file buffer, with line
endings preserved. If malformed UTF-8 triggers core replacement decoding, the
offsets and slices refer to the replacement-decoded UTF-8 buffer; they must not
be applied to the original undecodable bytes.

Each syntax `calls` Boundary edge reuses the raw fact ID as both `id` and
`call_site_id`, preserves the exact reference and location, and carries the
canonical source path in both top-level `file` and `metadata.file`. These fields
are required only for syntax call edges; non-call syntax edges and semantic call
edges keep their existing shapes. Default resolution remains heuristic and does
not establish language-level binding; the experimental opt-in call resolution
below narrows only call edges that are already ambiguous. Parser forms that an
extractor does not recognize are not manufactured as facts.

Call-target lookup accepts only complete `[A-Za-z_][A-Za-z0-9_]*` identifier/member
chains (including whitespace-separated `.`, `?.`, `::` and `->` members) for the existing
simple-qualified heuristic. Comments, computed members, strings and other complex
callee expressions remain raw, unresolved observations; incidental identifiers
inside them do not bind local definitions. This guard does not strip or rewrite
the reference, remove call sites, or change import/dependency resolution. The
simple-qualified fallback still does not establish semantic language binding.
Names outside this subset, including JavaScript `$` names, Unicode identifiers
and parenthesized callees, stay unresolved even if the old resolver could match
their whole spelling. This is a conservative resolution limit, not invalid syntax.
Previously emitted graph/IR resolution annotations and derived digests can change;
consumers must qualify the corrected source profile and recapture affected outputs
rather than reinterpret historical captures.

In Python, the outer call of a callable-return expression is its own syntax
`calls` fact (treesitter-chunker#516). This covers `getattr(obj, 'audit')()`,
`f()()` (one fact per call level) and a parenthesized inner call such as
`(f())()`. Its `reference` is the raw callee: the inner call expression's
exact source bytes, with any parentheses or comments. `location` spans the
whole outer call. In the symbol-graph output (`calls` relationships and
`call_facts`), `callee_byte_start` and `callee_byte_end` span the callee
expression; Boundary IR `calls` edges carry `location` but not the callee byte
fields. It has its own `call:` site ID, owner and lines. The fact is always
unresolved: the guard above gives it no candidates, so it never binds a local
definition through an incidental name. The inner call's fact is unchanged,
including its ID. Consumers must recapture graph/IR outputs and the derived
counts, memberships, aggregates and digests, because one `calls` edge is added
per outer site. Other complex callees are not emitted as outer sites, for
example subscript callees (`h['a']()`), parenthesized names (`(f)()`),
parenthesized `await` or conditional expressions (`(await f())()`,
`(a() if c else b())()`), and the JavaScript equivalents
(treesitter-chunker#602).

Per-site calls can increase edge counts, node memberships, clustering weights
and dependency aggregates. Regenerate affected graph/IR outputs and their
derived aggregates for 6.0.0. Incremental caches persist the raw facts and
reassemble resolution annotations on each run, so adding an unrelated callee
definition can change resolution without changing call-site IDs.

### Call resolution extension (experimental)

`call_resolution` is an opt-in, experimental option on `extract_symbol_graph`,
`extract_boundary_ir` and the `symbols extract` and `boundary` CLI commands
(`--call-resolution`), orthogonal to `resolution_mode`
(treesitter-chunker#682). `"name"`, the default, is the heuristic above, and
its output, cache keys and cache records are byte-identical to runs that omit
the option. Unknown values raise `ValueError`.

With `"structural"`, a per-file scope pass narrows syntax `calls` edges that are
`ambiguous` today, when the caller's file is Python, JavaScript, TypeScript or
TSX and the callee is a bare identifier. The rules only remove candidates and
never empty the set, so an ambiguous edge keeps two or more candidates, all from
today's set. An edge becomes `resolved` only when its one remaining candidate is
proven by a lexical binding; filtering by symbol kind (`t1.kind`) or language
family (`t1.family`) never resolves an edge by itself. Resolved, unresolved and
member-call edges are never changed. Currently `"structural"` proves
bindings for JavaScript, TypeScript and TSX callers (`t1.lexical`;
`t1.ts_overload` for a TS overload set; `t1.js_hoist` for the last of two or
more plain-JavaScript function declarations in one function body or script
top level, unless a block-level declaration, an expression binding or a write
of the name exists there). A script-goal top level proves a binding only when
no other file of the run may declare that name as a global; this holds within
the run only, so scripts outside it and global writes no syntactic rule sees
are not tracked. A lookup through a merged TS namespace body proves nothing.
For Python callers it proves bindings through the LEGB scope chain
(`t1.lexical`): a single unconditional, undecorated `def` or `class`. Python
redefinitions narrow to their group and never resolve; module-scope and
class-body lookups in a file that may bind names at run time (`exec`,
`globals`, `sys.modules` and the like) or has a star import prove nothing, as
do module-level definitions of builtin names, class-body lookups in a class
with a base or keyword argument, and every lookup in a file that mentions
`f_locals`; monkeypatching from other modules is not tracked.

With `"imports"`, everything `"structural"` does applies, and a JavaScript,
TypeScript or TSX call whose callee a relative ES import binds (`import { t }`,
a default import, or `ns.t()` on `import * as ns`) resolves when the
specifier names exactly one file of the run, in TypeScript's candidate order,
and that module's export table leads, within three re-export or `export *`
hops, to one definition its own scope lookup proves (`t2.import`,
`t2.namespace`). More than one file variant, a `.d.ts` target, a bare or
non-relative specifier, a star conflict, a cycle, a reassigned export, and
CommonJS reach (a module whose exports object CommonJS code or another file
of the run may write) leave the edge unchanged. Specifiers and quoted names
are compared by their exact string value. A sibling `<stem>.<segment>.<ext>`
(a platform or module suffix such as `svc.ios.ts`) leaves the edge unchanged
unless the segment is on a closed list of names no resolver uses (`test`,
`spec`, `stories`, `types`, …). Some files can rewrite any module's exports
object: a code evaluator, a non-literal `require` or `import()`, `createRequire`,
`mainModule`, `getBuiltinModule` or an import of `module`, the CommonJS
`module` object handed on, or an unparsed file whose text spells one. Any such
file in production code turns Tier 2 off for the whole run, and the cause is
logged. Three uses are exempt by closed lists: an import of only
`builtinModules` or `isBuiltin` from `module`; `const r = createRequire(…)`
used only as `r('<literal>')` (which counts as a `require` of that path) or
`r.resolve('<literal>')`; and a `.constructor` read used only for `.name`, an
equality or `instanceof` comparison, or `typeof`. Such a file in test code (a basename with a `.test.` or `.spec.`
segment, or a `__tests__`, `__mocks__`, `test` or `tests` directory) turns
Tier 2 off only for calls made from test files, and so does any module write
or escape spelled in test code. A test-named file that production code
imports, directly or transitively, counts as production. Every test file counts as
production when a directory symlink lies under the root, or when production
code uses a specifier that cannot be located (a `#` package import, an
absolute path, a `file:` or `data:` URL, a path through a skipped directory
such as `build/` or `node_modules/`, `import.meta.glob`, or `createRequire`
with a base other than the file itself). A `createRequire` base counts as the
file itself only when it is an unwritten `import.meta.url`/`filename`, or an
unbound and unwritten `__filename` that no file of the run can redefine as a
global. Skipped directories are matched case-insensitively, ignoring a
trailing dot or space, and a path segment that is an 8.3 short name or contains
`:` cannot be located, and URL schemes after stripping surrounding whitespace
and control characters. `jest.mock`/`vi.mock` of a relative path
counts as a write to that module for the mocking file's callers.
A JavaScript or TypeScript file the parser cannot read cleanly (including any
file with a lone carriage return, U+2028, U+2029 or an HTML-like comment,
including a JavaScript `<!--` or `-->` that the parser reads as code)
counts as rewriting any module (scoped like any other cause: test code affects only test
callers unless production code reaches it). For JavaScript and TypeScript
callers, wherever Tier 2 is off the output equals `"structural"`.

For Python callers `"imports"` resolves a call bound by `from m import t`
(relative forms and function-local imports included) or a member chain on an
imported module (`m.t()`, `pkg.mod.t()`) when the module name resolves, one
component at a time from the root (a package before a module before a
namespace directory), to exactly one run file, and its module-scope binding
leads within three re-export hops to one definition its own scope lookup
proves (`t2.import`, `t2.namespace`). Two or more imports of one name narrow
to their group. A sibling in the importer's own directory, a standard-library
module name, a relative import leaving the root, a name that is also a
submodule, a single conditional import, star imports and module
`__getattr__` leave the edge unchanged. Other files' writes to a module's
globals are counted: an imported module object may only be read, called
through, compared with `is`, or written by name; a named write (or a constant
`mock.patch('m.t')`-style string) makes that name unprovable, and any other
use (passed to a function, aliased, returned, `__dict__`, `vars(m)`, a
literal `import_module('m')` or `sys.modules['m']`) makes the whole module,
and every module it exposes, unprovable. That also applies to the written
module's own module-level `"structural"` proofs, so `"imports"` can resolve
fewer Python calls than `"structural"`. A Python file that may load or write
any module (`exec`, `eval`, a non-literal loader, other `importlib` uses,
`runpy`, `sys.modules` other than a literal key, `sys.path` changes,
`__globals__`, frame globals, `builtins`, `__main__`) or that tree-sitter and
CPython may read differently turns Python Tier 2 off, scoped like the
JavaScript causes (test files: `test_*.py`, `*_test.py`, `conftest.py`, or a
`tests` or `test` directory). On the real trees measured for
treesitter-chunker#682, Python Tier 2 resolved no additional calls: every tree
had such production code.

A narrowed edge changes only `target`, `resolution`, `candidates` and
`metadata.is_internal`, and adds `provenance.call_resolution` (the mode) and
`provenance.call_rules` (the rule IDs that removed candidates, in application
order). A narrowed resolved edge has every field of a natively resolved edge
with its usual meaning. Unchanged edges keep their provenance exactly.
`run.options.call_resolution` records the mode. These keys are additive, so
`schema_version` stays `"3.0"` (`"3.1"` with semantic resolvers), and no key
appears when the mode is `"name"`.

Node IDs, `definition_id`s, `#N` suffixes, edge `id`s and `call_site_id`s are
byte-identical with the option on and off. Because `target` is a sort key, a
narrowed edge can move within `edges`; consumers key edges on `id`.
`metrics.resolved_edges` and `metrics.ambiguous_edges` can change, but not their
sum, `unresolved_edges` or `edges_total`. `parity_digest` changes for every
on-mode document, because `run.options` is part of the parity view. Semantic
resolvers run after syntax edges are built, so they see the narrowed edges.

On-mode cache keys add `call_resolution` and `call_resolution_version`, the
per-file scope-fact version of the file's language family, and on-mode records
store the scope facts. A missing or malformed scope-fact record is a safe miss.
`BOUNDARY_CACHE_VERSION` and `BOUNDARY_CACHE_KEY_FIELDS` are unchanged. Switching
modes on one cache directory is a cold run in both directions and orphans the
other mode's records, so use one cache directory per mode.

### Observability extension

Deterministic metrics keys, fixed `run.timings` keys, structured diagnostics,
and `fail_fast` runtime behavior are downstream observability contracts layered
on top of the Phase 0 baseline.

### Incremental extension

Incremental cache keys, warm-run invalidation rules, and impacted-neighbor
recompute behavior are downstream contracts. IR 3.x records use cache version
`3` and the `boundary:v3:` key namespace. Cache version 1 and 2 records are
misses, including records whose stored schema otherwise matches, because they
cannot supply the required per-site raw call facts. Missing or malformed
`call_facts` in a version 3 record also causes a safe miss and re-extraction.

Each cache key includes the installed `tree-sitter-language-pack` and
`tree-sitter` runtime versions. Python and JavaScript keys additionally bind the
actual selected grammar source: either the exact official distribution/version
or the SHA-256 digest of the successfully loaded custom library. A grammar-pack,
runtime, official grammar, or selected custom-library change therefore
invalidates persisted per-file records instead of combining stale records with
new extraction output. Existing Python/JavaScript records without that source
identity are re-extracted. This changes cache eligibility only: source bytes,
half-open UTF-8 spans, node identities, schema vocabulary and canonical output
rules are unchanged.

If Python/JavaScript provider selection fails before key construction,
`fail_fast=true` raises the typed initialization error. Non-fail-fast extraction
returns the normal per-file structured diagnostics, continues unaffected files,
and does not use or mutate an incremental cache under an invented identity.

### Parity extension

The parity view represents floats with the ECMAScript
`Number.prototype.toString` spelling before canon serialization: `1e-05` is
`"0.00001"`, `1e-07` is `"1e-7"`, and `-0.0` is `"0"`. Its byte view and
digest are checked against a committed cross-tool golden, so an in-process
agreement cannot silently redefine the contract.

### Semantic extension

Optional semantic resolvers are a downstream additive extension. When callers
explicitly supply semantic resolvers, enriched output may use the additive
semantic schema version `3.1`
(`BOUNDARY_IR_SEMANTIC_SCHEMA_VERSION`). Semantic enrichment remains opt-in and
must not redefine or replace the syntax-only `3.0` baseline.

## Minimal Baseline Example

This schema-valid output comes from a Python file containing only
`# A source file with no declarations.` followed by a newline. Volatile source
and run paths are shown as `empty.py`; the tool version is illustrative.

```json
{"diagnostics":[],"edges":[],"files":[{"content_hash":"sha1:7eb4e49617b13df62d2b7cc8f24b036e2493c7b3","diagnostics":[],"id":"62a603819930ab104a88fbe7f15a28da7ab28e86","language":"python","parser":"tree-sitter-python","path":"empty.py","status":"parsed"}],"metrics":{"ambiguous_edges":0,"diagnostics_total":0,"edges_total":0,"failure_buckets":{},"files_failed":0,"files_parsed":1,"files_processed":1,"files_skipped":0,"files_total":1,"graph_failures":0,"metadata_failures":0,"nodes_total":0,"parse_failures":0,"resolved_edges":0,"serialization_failures":0,"unresolved_edges":0},"nodes":[],"run":{"canonical":true,"created_at":null,"options":{"fail_fast":false,"include_retrieval_metadata":true,"include_timings":false,"language":"python","resolution_mode":"strict"},"root":"empty.py","timings":{"graph_assembly_ms":null,"metadata_normalization_ms":null,"parse_ms":null,"resolution_ms":null,"serialization_ms":null,"total_ms":null},"tool":"treesitter-chunker","tool_version":"5.2.0"},"schema_version":"3.0","source":{"kind":"file","path":"empty.py"}}
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

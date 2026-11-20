---
automation:
  suite_command: "uv run --locked --all-extras pytest tests/test_call_resolution_*.py tests/test_symbol_graph_resolution.py tests/test_symbol_graph_incremental_facts.py tests/test_boundary_ir_resolution_modes.py tests/test_boundary_ir_incremental_cache.py tests/test_boundary_ir_golden_snapshots.py tests/test_boundary_ir_determinism.py -q"
---

# Scope-aware call resolution, opt-in (treesitter-chunker#682)

Status: **revision 2**, applying the president's ruling ("APPROVED AS AMENDED",
`evidence/treesitter-chunker/plan-682-review/president-ruling.md`, RC-1 to
RC-45). Appendix B maps every required change to the sections that apply it.
No product or test code is written by this plan. Releasing the feature, and
naming any version, are separate owner questions.

## 1. Decisions at a glance

| Topic | Decision |
| --- | --- |
| Opt-in surface | A new keyword-only option, `call_resolution`, orthogonal to `resolution_mode`. Values: `"name"` (default, today's behavior), `"structural"` (Tier 1) and `"imports"` (Tier 1 + Tier 2). It is not a `resolution_mode` value and not a `SemanticResolver`. Marked **experimental** until PR 6. |
| What can change | Only call edges that are `ambiguous` today (two or more candidates). Only `target`/`to`, `resolution`, `candidates` and `is_internal`, plus two additive provenance keys, on those edges. Derived counts follow. |
| Core rule | **Binding-proof invariant** (ruling 2.1). An edge becomes `resolved` only when its one remaining candidate is proven by a binding: it lies in the group-rule result of a Tier 1 lexical lookup, or of a Tier 2 import's resolved export target. The kind and family filters can only narrow: they apply when two or more candidates remain, or when the single survivor is binding-proven. Every step only removes candidates and never empties the set. |
| Which calls | Bare-identifier callees (`t()`, `new Box()`) in Tier 1 and Tier 2, plus namespace-import member calls (`ns.f()`, `m.f()`) in Tier 2. Every other member call (`self.m()`, `obj.m()`, `globalThis.f()`) is untouched, so dynamic dispatch stays ambiguous. |
| What it fixes | Collisions among candidates the resolver already found. It does not add missing edges or repair wrong single-candidate edges (Q1, Q8). |
| Where facts come from | A new per-file scope pass, run only when the option is on. The metadata extractors are not changed. |
| Redefinition policy | An **executive decision that Greenfield accepted in writing** (section 8). It is stricter than the issue's Python rule. Python redefinitions are never resolved. Plain-JS hoisted function declarations resolve to the last one (`t1.js_hoist`, in its own PR). TS duplicate bodies stay ambiguous. A TS overload set resolves to its implementation. |
| Extension collisions | When a relative import matches more than one file variant, the result is `none` (ruling 2.2). Owner question O-1 is open with default (a) applied. |
| IDs | No ID input changes. `definition_id`, `node_id`, `#N` and `call_site_id` are byte-identical on and off. A harness proves it for every fixture, on both the symbol graph and Boundary IR. |
| Schema and cache | Boundary IR stays at `3.0`, and the new provenance keys are additive. On-mode `parity_digest` changes, which Greenfield accepted. Off-mode cache keys are unchanged. Switching modes on one cache directory is a cold run in both directions. |
| Delivery | Seven strictly sequential PRs (0–6). All of Tier 1 merges before any Tier 2. Only PR 6 closes treesitter-chunker#682. No heavy local runs on dev0; full validation runs in CI. No release. |
| Greenfield agreements | **Received**: Greenfield agreed in writing on 2026-11-20 (Greenfield Exec thread, relayed by the executive) to the reworded gates and parity-digest change (ruling 2.4), and to interpretation (c) of its hoisting condition (ruling 2.6). |

## 2. Problem and motivating failure

`chunker/symbol_graph.py` resolves a call reference by name only, with one
syntax guard.

- `_build_resolution_indexes` indexes every symbol in the run by
  `qualified_name` and by `name`.
- `_resolve_call_reference_candidates` accepts only plain identifier and member
  chains.
- `_resolve_reference_candidates` builds **C0**, today's candidate set
  (section 6.2 gives the exact construction).
- `_resolution_status` turns one candidate into `resolved`, two or more into
  `ambiguous` and none into `unresolved`.

Nothing looks at scope, imports, module paths, symbol kind or language.

5.x hid the collisions by keying symbols as `module_stem:qualified_name`, so the
last definition won. On Greenfield's `r9-ts` tree, 5.3.0 kept only
`web/svc.tsx`'s `t`, so six of the seven `t` calls in `web/svc.ts` resolved to
the wrong file (evidence `r9-ts-5.3.0.txt`). **That misattribution is the
failure the exactly-one-target rule and the binding-proof invariant guard
against.** No rule may pick a winner among candidates it cannot tell apart.

treesitter-chunker#496 (6.0.0) gave every definition its own ID, which exposed
the collisions as `ambiguous` edges. Greenfield (ViperJuice/greenfield#48, O-5)
then either drops those edges or over-approximates them.

## 3. Baseline evidence (current main)

Every number below was re-derived for revision 2:

- product code identical to main `f213f1c2` (the plan branch adds only this
  file), Python 3.14.10, `uv run --locked --all-extras`;
- narrow, single-process `extract_symbol_graph` runs, after `free -h` showed 21
  GiB available and load fell below the core count;
- Greenfield's trees copied out of `gf48-probes` first and verified against
  `evidence-manifest.sha256` (sha256
  `40575a9bd9612fd1d307dda1e8e94f0ca7af5dff19659ca45cbb7fad649a1e46`).

Appendix A has the scripts.

### 3.1 Call edges today, and against Greenfield's 6.0.0 IRs

| Tree | Call edges on main | Node IDs vs 6.0.0 | Edge differences vs 6.0.0 |
| --- | --- | --- | --- |
| r9-ts | 9 ambiguous | identical | none |
| r9-py | 9 resolved, 2 ambiguous, 1 unresolved | identical | none |
| r9b-py | 2 resolved | identical | none |
| py-sameline | 5 resolved | identical | none |
| rt-pycond | 2 resolved, 1 ambiguous | identical | none |
| rt-pyrec | 2 resolved, 2 ambiguous, 1 unresolved | identical | 1 (below) |
| rt-js | 2 resolved, 1 ambiguous | identical | none |
| rt-tsclass | 2 resolved | identical | none |
| rt-go | 2 resolved | identical | none |
| rt-rust | 3 resolved | identical | none |
| rt-cpp | 2 resolved, 1 ambiguous | identical | none |
| rt-java, rt-kotlin | no edges | identical | none |
| clo-go, clo-kotlin, clo-rust | 4 unresolved; none; 6 unresolved | (no 6.0.0 IR) | — |

One edge differs from 6.0.0. In rt-pyrec, `uses_c2 → C().c` was `ambiguous`
over both `C` classes in 6.0.0, and is `unresolved` with no candidates on main.
That change comes from the 7.0.0 complex-callee guard (commit `b8e992aa`), not
from this work.

### 3.2 The ambiguous edges this work targets

| Tree | Call (file:line, caller → reference) | C0 today |
| --- | --- | --- |
| r9-ts | `svc.ts:4` A.m → `t`; `:5` A.m2 → `t` (×2); `:9` d → `t` (×2); `:14` caller → `t` | svc.ts:1 `t`, svc.tsx:1 `t` |
| r9-ts | `svc.ts:12`, `:13` caller → `d` | svc.ts:8 `d` (signature), svc.ts:9 `d` |
| r9-ts | `svc.tsx:2` View → `t` | svc.ts:1 `t`, svc.tsx:1 `t` |
| r9-py | `svc.py:16` C.b → `C` | class C @9, class C @14 |
| r9-py | `svc.py:31` caller → `d` | d @19, d @24 |
| rt-pycond | `svc.py:21` caller → `d` | d @13, d @16 (if/else branches) |
| rt-pyrec | `svc.py:23` d → `d`; `:27` uses_c2 → `C` | d @18, d @22; class C @5, class C @10 |
| rt-js | `k.js:9` g → `d` | d @3, d @6 |
| probe | `over.ts:6` g → `f`; g → `new Box` | f @1, f @2, f @3; interface Box @4, class Box @5 |
| probe | `svc.ts:2` caller → `t` (×2); `use.ts:2` user → `t` | svc.ts `t`, svc.tsx `t` |
| probe (py root) | `c.py:4` use → `helper`; `pkg/__init__.py:5` call_k → `k`; `redef.py:11` caller → `d` | a/b `helper`; pkg.py/pkg/__init__ `k`; d @1, d @4 |

**How C0 is built** matters for these rows. The qualified-name match comes
first, so a nested definition (`outer.t`, `K.helper`, `wrap.f.t`) is never in
C0 when any top-level symbol of that name exists in the run. The innermost
binding is then often not a candidate. When that happens the option leaves the
edge unchanged (section 6.3).

### 3.3 What chunk metadata exposes today

| Fact | Exposed? | Notes |
| --- | --- | --- |
| Symbol kind | Yes (`metadata.kind`) | TS: `function`, `method`, `class`, `interface`, `type`, `enum`, `module`. Python: `function`, `method`, `class`. |
| Parent and qualified name | Yes | Gives the parent's name, not its kind. Blocks never appear in the route. |
| TS overload signatures | Yes | Separate symbols with `node_type` `function_signature` or `method_signature`, and no `signature` key. |
| `declare` forms | Yes | `function_signature` with an empty parent context. |
| Arrow-function consts | Yes | The `arrow_function` chunk is the symbol (name `<anonymous>`, `qualified_name` = the const name). An anonymous arrow returned from a function also takes that function's `qualified_name`: `mk` and its returned arrow both appear as `mk`. |
| Interface members | Yes | `method_signature`, kind `method`. |
| Imports (TS/JS) | Partly | Raw strings only; aliases are lost. |
| Imports (Python) | **No** | Module-level imports produce no chunk. |
| Exports | Partly | A mixed name set; not an export table. |
| Scopes, parameters, locals, conditionals | **No** | — |

So the facts come from a separate scope pass. The extractors stay unchanged,
because their output is part of node metadata and must be byte-identical when
the option is off.

## 4. Opt-in surface

### 4.1 Options weighed

| Option | Verdict | Why |
| --- | --- | --- |
| New `resolution_mode` value | Rejected | `strict`/`permissive` is an enforcement label and a closed enum (`boundary_ir.schema.json`, `RESOLUTION_MODES`). A third value would make "strict plus scoped" impossible. |
| First-party `SemanticResolver` | Rejected for this work | Semantic resolvers **add** edges whose IDs hash the target, under schema `3.1`. Their context carries `root` but no parse trees and no per-file facts, so a resolver would have to re-parse outside the cache key. It stays the home for later receiver-typed, language-server resolution. |
| New orthogonal option | **Chosen** | Narrows today's call edges in place. Composes with both `resolution_mode` values and with semantic resolvers. |

### 4.2 API

- `chunker/types.py`, re-exported from `chunker.boundary.types`:
  `CallResolution = Literal["name", "structural", "imports"]` and
  `CALL_RESOLUTION_MODES`. The values are cumulative.
- Keyword-only `call_resolution: CallResolution = "name"` on:
  - `extract_symbol_graph`, `extract_symbol_facts_for_file` and
    `assemble_symbol_graph`;
  - `extract_boundary_ir`, both its cold and incremental paths;
  - `_extract_file_cache_record` and `_cache_key_payload`;
  - **the `ParserInitError` fallback**, which re-enters `extract_boundary_ir`
    at `adapter.py:1376-1389` and must pass `call_resolution` through. A test
    covers this.

  An unknown value raises `ValueError`.
- **Tier 2 input (PR 1).** `assemble_symbol_graph` gains the keyword
  `language_filter: str | None = None`: the run's `language` argument, passed
  by `extract_symbol_graph` and by both Boundary paths. The file set comes from
  the facts' `path` values, so assembly still does no filesystem access. It
  lands in PR 1, so the public surface changes once.
- **Language filters and Tier 2 TS/JS (P8).** Any language filter makes some
  extension variants uncollected, and an uncollected variant gives `none`
  (9.2). Tier 2 TS/JS therefore needs an unfiltered run:
  - Python API: `language=None`;
  - CLI: `boundary` without `--lang`, which auto-detects and does not filter.

  `symbols extract` cannot do an unfiltered run: it defaults to `-l python` and
  forces its language onto every file. Its Tier 2 covers only that language.
- CLI: `--call-resolution {name,structural,imports}` (default `name`) on
  `symbols extract` and `boundary`. Help text says "experimental".
- With a mode other than `name`, `assemble_symbol_graph` requires `scope_facts`
  in every fact and raises `ValueError` otherwise.
- PR 1 introduces `name` and `structural`; PR 5 introduces `imports`.

### 4.3 Output when the option is on

- **Symbol graph.** A call relationship whose candidate set changed gets new
  `to`, `resolution`, `candidates` and `is_internal`. It also gets
  `provenance.call_resolution` (the mode) and `provenance.call_rules` (rule IDs
  that removed candidates, in application order, for example
  `["t1.lexical", "t1.ts_overload"]`). Unchanged edges keep today's provenance
  exactly. `metadata.call_resolution` is added.
- **Boundary IR.** `_edge_record` copies those two keys from the relationship.
  `run.options.call_resolution` is added. `metrics.resolved_edges` and
  `ambiguous_edges` change; their sum, `unresolved_edges` and `edges_total`
  cannot. A narrowed edge can move within `edges` because `target` is a sort
  key. Consumers key on `id` (B16 spec text).
- **`parity_digest`.** It changes for every on-mode document, because
  `run.options` is inside the parity view (`serialization.py`
  `_PARITY_EXCLUDED_RUN_FIELDS`). Greenfield accepted this on 2026-11-20.
- **Semantic resolvers** run after syntax edges are built, so they see the
  narrowed edges.
- **When off.** None of these keys appear, and output is byte-identical to
  today.
- **Resolved shape** (Greenfield's gate as ruled in 2.4, agreed):
  - symbol graph `to` / Boundary `target` is the definition's ID or node ID;
  - `resolution == "resolved"`;
  - `candidates == [target]`;
  - `is_internal` (Boundary `metadata.is_internal`) is true;
  - `provenance` differs from a natively resolved edge only by
    `call_resolution` and `call_rules`. That follows the precedent of
    `enforcement_grade` and the schema's `additionalProperties: true`.
- **Historical fallback** (moot because Greenfield agreed): if Greenfield had
  declined, Boundary edges would have carried no new keys, while the symbol
  graph keys and `run.options.call_resolution` stayed.

### 4.4 Schema and cache

- **Schema.** `boundary_ir.schema.json` documents optional
  `provenance.call_resolution` (enum `structural`, `imports`),
  `provenance.call_rules` (array of strings) and `run.options.call_resolution`.
  These are additive, so `schema_version` stays `"3.0"` (`"3.1"` with semantic
  resolvers, as today).
- **Cache key.**
  - No `BOUNDARY_CACHE_VERSION` bump, and no change to
    `BOUNDARY_CACHE_KEY_FIELDS`.
  - **Off mode omits the new fields**, so off-mode keys and records are
    unchanged and still reused.
  - When the mode is not `name`, `_cache_key_payload` adds `call_resolution`
    and `call_resolution_version`, the fact version for the file's language
    family (4.6). **Both branches** of `_build_boundary_cache_key` hash them:
    the plain `build_boundary_cache_key` path and the semantic path.
- **Cache tests:**
  - keys for `name`, `structural` and `imports` all differ, with and without
    semantic resolvers;
  - off-mode records never contain `scope_facts`;
  - the off-mode payload and key match the values recorded by PR 0;
  - an on-mode record whose `scope_facts` is missing or malformed is a safe
    miss.
- **Switching modes on one cache directory** is a cold run in both directions,
  and leaves the other mode's records orphaned. We recommend one cache
  directory per mode.
- **Rules run at assembly** on every run. Changing them, including the hop
  limit, needs no version bump.

### 4.5 Experimental label

The option is marked experimental in CLI help, docstrings and CHANGELOG
(Unreleased) from PR 1 until PR 6. Each PR's CHANGELOG entry states exactly
what each value does at that head. For example, after PR 1, `structural`
applies only the kind and family filters and resolves nothing.

### 4.6 Fact versions

- **Per-language-family fact versions:**
  `CALL_RESOLUTION_FACT_VERSIONS = {"js": "1", "python": "1"}`. A PR that
  changes one family's per-file facts bumps only that family's version.
- **Pinned digests.** `tests/fixtures/call_resolution/scope_facts_digests.json`
  holds, per family, the version and a digest of every fixture file's scope
  facts. The test fails if the digest changes while the version stays the same.

## 5. Architecture

### 5.1 Modules

`chunker/call_resolution/` contains:

- `engine.py`: eligibility, the binding-proof algorithm, filters and
  provenance. Pure functions with no filesystem access.
- `js_scope.py`: the analyzer for javascript, typescript and tsx.
- `py_scope.py`: the Python analyzer.
- `modules.py`: Tier 2 resolution.
- `allowlist.py`: the binding allow-list (7.5).

PR 1 ships stub analyzers. They report `supported: true` with every outcome
`none(stub)`, and still fail closed on trees with errors.

### 5.2 Per-file scope facts

When the mode is not `name`, `extract_symbol_facts_for_file` re-parses the file
with `get_parser(language)`. It **reuses the bytes already read at
`symbol_graph.py:512`**, plus core's lone-CR substitution for Python, so spans
match `call_spans`. It stores `facts["scope_facts"]`:

- `version`, `language`, `supported`;
- `goal`: `module` if there is any top-level `import` or `export`, otherwise
  `script`;
- `bindings` keyed by callee span;
- `script_globals`, `exports` and `module_bindings`.

`scope_facts` is never emitted, and is stored only in on-mode cache records.
Streaming and VFS paths are untouched, because the symbol graph calls only
`chunk_file`.

### 5.3 Failure modes (B8)

These all give `supported: false` for the file:

- an analyzer exception;
- `RecursionError`;
- a parser initialization failure;
- a tree with errors.

None of them adds anything to `facts["errors"]` or diagnostics, and none
raises, even with `fail_fast`. A debug log line is allowed. A file with
`supported: false` never narrows, and contributes no exports to Tier 2. Tests:
an injected exception, deep nesting and a syntax error, each asserting that on
equals off.

### 5.4 The join is total and fails closed (B9)

- Bindings are keyed by the call fact's callee byte span
  (`callee_byte_start`, `callee_byte_end`).
- A call fact with no binding entry gives `none(no-binding-fact)`.
- Declarations map to symbol IDs by `(node_type, byte_start, byte_end)`. A
  declaration that maps to no symbol, or a duplicate key, is a non-symbol
  binding (`none(unmapped)`).
- Fixtures cover a call inside a template string (`js-template-call`) and a
  decorator call re-owned to the decorated function (`py-decorated`).
  The named synthetic-facts tests in 10.6 cover `no-binding-fact` and
  `unmapped`.
- **Exported declarations (N-1).** On main, `export function t()` produces two
  chunks: an `export_statement` at [0, 33) and the inner `function_declaration`
  at [7, 33). The join must use the chunk that carries the symbol, the inner
  declaration. Otherwise every exported definition fails closed as `unmapped`,
  and every positive fails.

## 6. Rule engine

### 6.1 Eligibility

A call edge is processed only when all of these hold:

1. The mode is not `name`.
2. The caller's file is python, javascript, typescript or tsx, and its facts
   say `supported`.
3. `|C0| >= 2`.
4. The reference is a bare identifier, or (Tier 2) a namespace member chain
   (section 9).

Resolved and unresolved edges are never touched.

### 6.2 C0 and lookup outcomes

**C0 construction** (`_reference_candidates`, `_resolve_reference_candidates`):

1. The reference is tokenized into identifier/member chains. Each chain
   contributes itself, then its dot-separated parts, and the whole reference is
   appended. Import keywords are dropped, and duplicates keep their first
   position.
2. **Qualified pass:** the first token in that order that is a `qualified_name`
   anywhere in the run gives C0, and the pass stops.
3. **Name pass:** only if no token matched, C0 is the union of name matches
   over all tokens.

Consequences:

- A nested definition is never in C0 when a same-named top-level symbol exists.
- For `svc.t()`, the order is `svc.t`, `svc`, `t`. A top-level symbol named
  `svc` therefore becomes C0 on its own, before `t` is tried (P9).
- Remove-only rules cannot repair such a C0. They can only leave it unchanged.

**Lookup outcomes** per eligible call:

- `local(G)`: the innermost binding scope binds the name only through symbol
  definitions in this file.
- `import(b)`: the name binds to an import.
- `none(reason)`: any other case. The reasons are listed in 7.6 and 9.8.

### 6.3 Algorithm: the binding-proof invariant (ruling 2.1)

```
C := C0                                   # |C0| >= 2
P := proven(outcome, mode)                # local(G) -> group_rule(G)
                                          # import(b), "imports" mode -> group_rule(resolve(b))
                                          # otherwise the empty set
1. binding   if P nonempty: X := C ∩ P; if X nonempty and X != C: C := X
             (t1.lexical | t2.import | t2.namespace, plus any group-rule id)
2. filters   F := callable_kind(same_family(C))
             if F != C and (|F| >= 2 or (|F| == 1 and F ⊆ P)): C := F   (t1.kind, t1.family)
3. result    |C| == 1 -> resolved          # invariant: a resolved C is ⊆ P
             else ambiguous, sorted C (|C| >= 2)
```

- Every step only removes candidates, and a step that would empty C is
  skipped. An ambiguous edge always keeps two or more candidates, all from C0.
- **Kind and family removals prove the removed candidates wrong, not the
  survivor.** So a filter alone never resolves an edge. The counterexamples
  are kept as fixtures: a parameter `t` (`ts-param-kind`), the builtin `open`
  (`py-builtin-family`), an external import (`ts-external-import-kind`) and a
  local enum (`ts-enum-shadow`).
- **A proof whose binding is not in C0** (`X` empty): the binding step has no
  effect and P proves no candidate, so the edge is **never resolved**. The
  filters may still narrow it to two or more candidates under the step-2
  condition. Its remaining candidates are then known to be wrong. In the
  current examples (ts-nested-scope, py-closure-2, js-tdz, ts-alias-import)
  nothing is filterable, so their rows stay as Today. Repairing such edges is
  treesitter-chunker#685.
- Tier 1 and Tier 2 never compete: the innermost binding decides. In
  `structural` mode an `import(b)` outcome proves nothing.

## 7. Tier 1 rules (`structural`)

### 7.1 Filters: `t1.kind` and `t1.family`

| Rule ID | Removes | Applies to |
| --- | --- | --- |
| `t1.kind` | Candidates of kind `interface`, `type`, `enum`, `module` (namespaces, `declare module`), `struct` or `trait` | Every eligible edge, under the 6.3 condition |
| `t1.family` | Candidates whose language family differs from the caller's (`{javascript, typescript, tsx}` vs `{python}` vs each other language) | Every eligible edge, under the 6.3 condition |

The JS-only rows "a plain call removes a class" and "`new` removes a method"
are **cut** (ruling 2.1). The binding proof covers those cases.

### 7.2 `t1.lexical`, JS/TS scope chain

- **Scopes, innermost first:**
  - block (`statement_block`, `switch_body`, `for_statement`,
    `for_in_statement`, `catch_clause`);
  - `class_static_block`, which has its own var scope;
  - function body;
  - **parameter scope**: the parameters only, between a function and its
    parent. Default values and other expressions in `formal_parameters` look up
    from here outward;
  - **a named function or generator expression's self scope**: its own name,
    bound as a non-symbol (`none(self-binding)`). A class expression's own name
    works the same way;
  - TS namespace body (`internal_module`, `module`);
  - `program`.
- **`class_body` binds no bare names.** Method bodies skip the class and
  continue in the scope enclosing it.
- **Lookup does not depend on position.** `let`, `const` and `class` bind
  across their whole block, because of the TDZ. Function declarations and `var`
  bind across their whole function or program.
- **Symbol bindings:**
  - `function_declaration` and `generator_function_declaration`;
  - TS `function_signature`;
  - `class_declaration` and `abstract_class_declaration`;
  - a single `const` declarator whose value is an `arrow_function` or
    `function_expression` (interpretation 2.6(c));
  - TS `enum_declaration` and `internal_module`, which are value declarations
    but not callable.
- **Type-space declarations are ignored:** `interface_declaration`,
  `type_alias_declaration` and type-only imports. A value lookup that would
  find only a type-only import gives `none(type-only)`.
- **Non-symbol bindings** (`none`):
  - parameters, including destructured ones, and the implicit `arguments`
    (`parameter`);
  - `catch` and loop variables, other `let`/`var`/`const` declarators,
    destructuring, and `using`/`await using` (`local-variable`);
  - `var`, `let` or `const` with a function or arrow initializer that is not a
    single `const` (`expression-bound`);
  - TS `import_alias` (`import t = NS.f`), a value binding treated as
    non-symbol.
- **Block-level function declarations** give `none(block-function)` in every
  lookup, inside or outside their block (2.6(b)). They also turn off
  `t1.js_hoist` for that name (2.6(a), A7).
- **Reassignment.** Any assignment, update or compound assignment to the name
  anywhere in the binding's scope subtree turns off narrowing
  (`none(reassigned)`). That includes nested functions that do not shadow the
  name. Targets are read fail-closed (PR 2, treesitter-chunker#689 panel):
  every identifier under an assignment target, an update argument or a bare
  `for … of/in` target counts as a write, through parentheses and TS wrappers
  (`(t)++`, `(t as any) = x`, `t! = x`, `<any>t`, `satisfies`) and patterns.
  The one exception is the object of a member or subscript access
  (`t.x = 1`). Computed method and property names are evaluated, so they are
  read too.
- **Fail closed** with `none(dynamic-scope)` when a direct `eval(...)`
  encloses the lookup, or a `with` lies on the lookup chain. A direct eval can
  assign any binding visible from its site, so every scope from the eval out
  to `program` is dynamic. Parenthesized and TS-wrapped callees (`(eval)(s)`,
  `eval!(s)`, `(eval as any)(s)`) are direct eval. Also fail closed with
  `none(unmapped)` on an unclassified declaration node (7.5).
- **Script goal and `script_globals`:**
  - `script_globals` holds the `var`, `let`, `const`, `class` and `function`
    top-level names of every script-goal JS/TS file.
  - It also holds any assignment in a script-goal file to an identifier with no
    declaration on its scope chain in that file (an implicit global), not only
    top-level ones.
  - `window.x =`, `globalThis.x =` and `self.x =` count as declarations of `x`
    in a file of either goal.
  - A lookup that lands on a script-goal top level narrows only if no other
    file in the run declares that name in `script_globals`. Otherwise it gives
    `none(script-global)`.
  - **Precedence (R-1(i)).** `script-goal-deferred` (PR 2) and
    `script-global` (PR 3) apply only when the lookup would otherwise prove a
    group. When the lookup meets an outcome that proves nothing, that
    outcome's own reason is reported. Such outcomes include a non-symbol
    binding (`parameter`, `local-variable`, `expression-bound`),
    `block-function` and `dynamic-scope`. js-require, js-cjs-local, js-var-fn,
    js-block-fn and js-eval-with therefore keep their own reasons and stay in
    PR 2.
  - Files outside the run are not scanned (risk R9): HTML-included scripts,
    `dist/`, `node_modules`, and scripts loaded by other means.
- **CommonJS files stay script goal** (R2). That is conservative: the
  script-global check only adds `none`, and hoisting works the same inside the
  CommonJS wrapper.
- **TS namespaces.** A lookup through a namespace body gives
  `none(namespace-merged)` when the namespace has more than one declaration in
  the run, or lives in a script-goal file.
- **Ambient status** is inherited from enclosing `declare` blocks
  (`declare namespace`, `declare module`, `declare global`). A binding made only
  of ambient declarations gives `none(ambient)`.

### 7.3 `t1.lexical`, Python scope chain

- **Scopes:** `module`, `function_definition`, `lambda`, `class_definition`, and
  comprehensions. A comprehension's first iterable is evaluated in the
  enclosing scope.
- **Class scope (ruling A10 as modified):**
  - **Code that runs in the class body** looks up starting at the class scope.
    That covers class-level statements, method decorators, default values and
    annotations, and nested class bases.
  - **A name the class body binds** (anywhere in the body) gives
    `none(class-scope-bound)` when looked up from class-body code. There is no
    positional variant.
  - **A free name** (one the class body does not bind) continues through any
    enclosing **function** scopes, then the module, then builtins. A class
    nested in a function reads that function's binding (`py-class-free-var`).
  - **Code inside methods, nested functions, lambdas and comprehensions** in a
    class skips the class scope. It continues in enclosing function scopes,
    then the module.
- **A name assigned anywhere in a function body is local to the whole body.**
  The bindings come from 7.5's allow-list: defs, classes, parameters,
  assignment and augmented assignment, annotated names, `for` targets, `with`
  targets, `except` names, imports, walrus (bound in the nearest function
  scope), `match` captures, `del`, PEP 695 type parameters and `type`
  statements.
- **Redirects.** `global` sends the lookup to module scope; `nonlocal` to the
  nearest enclosing function.
- **Unbound at module scope** means a builtin or `NameError`:
  `none(unbound)`.
- **Fail closed** with `none(dynamic-scope)` for module-scope lookups in a file
  that calls bare `exec`, `globals` or `vars` anywhere, or writes through
  `sys.modules[__name__]` (`setattr`, item or attribute assignment). A
  `wildcard_import` gives `none(star-import)` for module-scope lookups.
- A function that declares `global name` and binds it adds a non-definition
  binding at module scope (`none(mixed-bindings)`).
- **`nonlocal` writes (Codex review of treesitter-chunker#683).** A nested function that declares
  `nonlocal name` and binds it (assignment, augmented assignment, `del`, a
  `for`/`with`/`except` target, walrus, or a `def`/`class` of that name) adds a
  non-definition binding to the enclosing function scope that owns `name`, the
  same way `global` does for module scope. Any lookup that reaches that
  binding scope then gives `none(mixed-bindings)`. Example:
  `def outer(): def helper(): …; def swap(): nonlocal helper; helper = other;
  swap(); helper()` must not resolve to `outer.helper`. Fixture:
  `py-nonlocal-rebind` (near-miss).
- **Conditional.** A definition is conditional if an `if`, `elif`, `else`,
  `try`, `except`, `finally`, `while`, `for`, `with` or `match` statement lies
  between it and its scope body. `decorated_definition` is transparent.
- A module-level call before the only definition is a `NameError` at runtime,
  so resolving it is harmless.

### 7.4 Group rules

First drop non-callable kinds (namespaces, enums). If nothing is left, the
result is `none(non-callable)`. Then:

| Language | Group | Result | Rule ID |
| --- | --- | --- | --- |
| Any | Any group with **no body** (signatures only, or all ambient; ambient is inherited) | `none(ambient)` if every member is ambient (ambient wins over bodyless, R-1(iii)); otherwise `none(bodyless)` | — |
| Any | One definition | That definition (Python: only if unconditional; a single conditional definition gives `none(conditional)`) | `t1.lexical` |
| TS/TSX | k ≥ 1 bodyless `function_signature` plus exactly one body, contiguous, in one scope, the body last and a `function_declaration` (PR 2). Any other shape, such as a body before a signature or a `const` arrow body, proves every member, which can narrow but never resolve | The body | `t1.ts_overload` |
| TS/TSX | Two or more bodies | The bodies, `ambiguous` | `t1.lexical` |
| JS | Two or more `function_declaration`/`generator_function_declaration` directly in one function body or one script-goal `program`; no block-level declaration, expression binding or other binding of the name in that scope | The last one | `t1.js_hoist` (PR 3) |
| JS | The same at an ES-module top level (an early error) | The group, `ambiguous` | `t1.lexical` |
| Python | Two or more definitions in one scope | The group, `ambiguous` | `t1.lexical` |
| Any | Definitions mixed with non-definition bindings | `none(mixed-bindings)` | — |

**Settled in PR 2 (treesitter-chunker#688 panel, B7).** An ambient enum called
as a function, `declare enum E {}` then `E()`, gives `none(non-callable)`:
non-callable kinds are dropped first, as this section says, and `ambient` and
`bodyless` then apply only to the callable members left. The rulings support
this order:

- R-1(iii) of the plan ruling orders only `ambient` before `bodyless`
  (ts-declare-ambient) and says nothing about enums or namespaces;
- the treesitter-chunker#688 president's ruling (note 1) restates this
  section's drop-first order as the analyzer contract;
- the engine already rejects any proof that names a non-callable symbol.

The edge is unchanged either way; only the recorded reason differs. A function
merged with an ambient namespace (`declare function g(): void;` plus
`declare namespace g {}`) drops the namespace and gives `none(ambient)`. Both
cases are pinned by `test_b7_*` in `tests/test_call_resolution_tier1_js.py` on
trees the test writes, because a committed tree would change the off-mode
baseline (11.2).

### 7.5 Binding allow-list (A5)

`chunker/call_resolution/allowlist.py` classifies every named node kind of each
pinned grammar (javascript, typescript, tsx, python) that can introduce a
binding. Each kind is either:

- **handled**: with its binding class;
- **ignored**: with a reason (labels, for example);
- **fail-closed**: gives `none(unmapped)`;
- **non-binding**: the kind cannot introduce a binding (expressions, literals
  and the like). The completeness check needs every named kind classified,
  so this class records the review of kinds outside the binding forms.

An unclassified kind is treated as fail-closed. The check applies to the
grammars listed in `REVIEWED_LANGUAGES`: PR 2 adds javascript, typescript and
tsx, and PR 4 adds python. A test (PR 1) fails if a family's analyzer emits any
outcome other than `none(stub)` on the fixtures while one of its grammars is
unreviewed.

These are named explicitly:

- TS `import_alias`;
- `for (const/let … of/in)`;
- `using` and `await using`. They fail closed if the pinned grammar lacks them.

`tests/test_call_resolution_allowlist.py` enumerates node kinds from the loaded
`Language` (or the packaged `node-types.json`), runs in CI without grammar
sources, and fails on any unclassified kind. A grammar bump therefore cannot add
an unreviewed binding form.

### 7.6 `none` reasons (Tier 1)

| Reason | Meaning |
| --- | --- |
| `unbound` | No binding in the file (global or builtin) |
| `parameter` | A parameter, including destructured ones and `arguments` |
| `local-variable` | `catch`/loop/`with`/`except`/comprehension/walrus/`match` targets, `let`/`var`/non-function `const`, destructuring |
| `expression-bound` | A function or arrow bound by `var`/`let`, or a `const` that is not a single declaration |
| `self-binding` | A function or class expression's own name |
| `reassigned` | The name is assigned somewhere in the binding's subtree |
| `block-function` | A block-level function declaration binds the name |
| `conditional` | Python: a single conditional definition or import |
| `mixed-bindings` | Definitions mixed with other bindings, or duplicate imports |
| `class-scope-bound` | Python class-body lookup of a name the class binds |
| `star-import` | Python module-scope lookup in a file with `from m import *` |
| `dynamic-scope` | `eval`/`with` (JS); `exec`/`globals`/`vars`/`sys.modules` writes (Python) |
| `ambient` | Only ambient declarations bind the name |
| `bodyless` | Only bodyless signatures bind the name |
| `non-callable` | The binding is only an enum or namespace |
| `namespace-merged` | The lookup passes through a merged or script-goal namespace |
| `script-global` | Another file declares the name as a script global |
| `type-only` | Only a type-only import binds the name |
| `unmapped` | A declaration with no symbol, a duplicate span, or an unclassified node |
| `no-binding-fact` | The call has no binding entry |
| `stub` | PR 1 only |
| `script-goal-deferred`, `namespace-deferred` | PR 2 only; replaced by real handling in PR 3 |

Unsupported files (5.3) produce no outcomes at all.

**Precedence when two reasons apply (R-1).** Exactly one reason is recorded
per call, decided in this order:

1. The outcome's own reason (`parameter`, `local-variable`,
   `expression-bound`, `self-binding`, `reassigned`, `block-function`,
   `dynamic-scope`, `star-import`, `class-scope-bound`, `mixed-bindings`,
   `type-only`, `unmapped`, `no-binding-fact`) wins over `script-goal-deferred`,
   `script-global`, `namespace-deferred` and `namespace-merged`. Those apply
   only when the lookup would otherwise prove a group.
2. In a definition group, non-callable kinds are dropped first (7.4), so a
   group of only enums and namespaces gives `non-callable`, even when it is
   ambient (`declare enum E {}`; B7, settled in PR 2). Among the callable
   members left, `ambient` wins over `bodyless`: `declare function amb():
   void;` is both, and ts-declare-ambient expects `ambient`. Then comes
   `conditional`.
3. Tier 2 reasons (9.8) are checked in the order 9.2, 9.5 and 9.6 list them.
   For Python, `script-dir-shadow` is checked before `module-not-found`.

## 8. Sequential redefinition policy

**Attribution.** This policy is an **executive decision** (the executive's
update 2 to the plan author, 2026-11-20). **Greenfield accepted it in
writing**, as relayed in the same update. On 2026-11-20 Greenfield also
confirmed interpretation (c) below in writing (Greenfield Exec thread, relayed
by the executive). The president ruled it within delegated authority (ruling
2.5–2.6). It replaces the issue's text, "Python redefinitions resolve only when
every definition is unconditional and in the same scope", with a stricter rule.
No separate owner confirmation is on record; the owner is told through the
ruling's owner notice.

**Greenfield's condition, quoted verbatim:**

> block-level and expression-bound functions never resolve

**How it is implemented** (ruling 2.6; Greenfield says (a), (b) and (c) are
exactly what it meant):

- **(a)** Block-level function declarations and expression-bound functions
  (`var`, `let` or `const` with a function or arrow initializer, or an
  assignment) never join a `t1.js_hoist` group. If any of them binds the name
  in the scope, `t1.js_hoist` is off for that name.
- **(b)** Block-level function declarations give `none` in every lookup, inside
  or outside their block.
- **(c)** A single `const` binding with an arrow or function initializer cannot
  be redeclared or reassigned, so it is not a redefinition. It may resolve
  through `t1.lexical` (`ts-arrow-const` stays a positive case). *Fallback,
  kept for the record and moot after Greenfield's confirmation:* had Greenfield
  read the condition literally, `const`-bound functions would give
  `none(expression-bound)`, and ts-arrow-const would become a near-miss.

| Form | Result | Fixture proof |
| --- | --- | --- |
| Python `def`/`class` defined twice in one scope | `ambiguous`, narrowed to the group | r9-py `C`, `d`; rt-pyrec `d`, `C`; probe `redef.py`; **py-redef-narrow** (narrows from 3 to 2) |
| Python conditional definitions | `ambiguous`, group kept; a single conditional definition gives `none` | rt-pycond; py-cond-e |
| Python `@overload` | `ambiguous` | py-overload |
| Python module-level call between redefinitions | `ambiguous` (no positional rule) | py-module-positional |
| Plain JS hoisted function declarations in one function body or script top level | **resolved to the last one** | rt-js; js-hoist-fnbody |
| JS block-level declarations, Annex B overwrite | unchanged | js-block-fn; js-annexb-overwrite |
| JS `var`/`let` function bindings | unchanged | js-var-fn |
| JS duplicates at an ES-module top level | `ambiguous` group | js-esm-dup |
| The same JS global in two script files, or an implicit global | unchanged | js-script-global; js-implicit-global |
| TS duplicate bodies | `ambiguous` group | ts-dup-impl; ts-dup-method (member calls, not eligible); rt-tsclass has no calls to `K.m` and is only a control (N-2) |
| TS overload set | **resolved to the body** | r9-ts `d`; probe `f` |

**Why Python does not use "last wins".** A function can be called at module
level between two definitions:

```python
def d(): return 1
def caller(): return d()
caller()        # runs the first d
def d(): return 2
```

JS hoisting binds every function declaration of a scope before any statement
runs. Given (a), (b) and the reassignment rule, the earlier declarations are
never the binding's value.

**`t1.js_hoist` lands alone in PR 3**, under its own rule ID, so it can be
reverted on its own. **Edges that change for Greenfield's round-1 trees:**
r9-ts's 9 edges (PR 2) and rt-js's 1 edge (PR 3). Nothing else changes.

## 9. Tier 2 rules (`imports`)

Tier 2 proves `P` from an import binding and intersects it with C0. **The
option fixes collisions, not missing edges** (Q1).

- A renamed import whose local name differs from the exported one
  (`{ t as tt }`, `import x as y`) never has its target in C0, so it is **left
  unchanged**.
- A renamed import whose local name matches one unrelated symbol is wrongly
  resolved today, and stays wrongly resolved with the option on
  (ts-alias-import shows the ambiguous form).

### 9.1 TS/JS import bindings

| Form | Binding |
| --- | --- |
| `import d from './m'` | `d` → (m, `default`) |
| `import { a }`, `import { a as b }` | `b` → (m, `a`) |
| `import * as ns from './m'` | `ns` → module m; `ns.a()` (two segments) is eligible |
| `import type …`, `import { type a }` | not a value binding (`none(type-only)`) |
| `import x = require()`, `const x = require()`, `import()` | `none` (non-symbol binding; CommonJS is deferred) |

### 9.2 TS/JS module resolution (ruling 2.2)

- Only relative specifiers are resolved. Bare specifiers, `node_modules`,
  tsconfig `paths`/`baseUrl`, `#imports`, `node:`, URLs and paths outside the
  root give `none(external-module)` or `none(outside-root)`.
- **Candidate list (TypeScript's order):**
  1. a specifier ending in `.js` → `p.ts`, `p.tsx`, `p.d.ts`, `p.js`;
  2. ending in `.jsx` → `p.tsx`, `p.d.ts`, `p.jsx`;
  3. ending in `.ts`, `.tsx` or `.d.ts` → that file;
  4. ending in `.mjs`, `.cjs`, `.mts` or `.cts` → `none(unknown-variant)`;
  5. otherwise → `p.ts`, `p.tsx`, `p.d.ts`, `p.js`, `p.jsx`, then `p/index.`
     with the same five extensions.
- **A JS importer with an explicit extension** maps to that exact file only.
- **The decision:**
  - If any candidate's extension was not collected in this run, or the
    candidate lies under a skipped directory → `none(unknown-variant)`.
  - Else, if **more than one** candidate exists in the run →
    `none(ambiguous-extension)`. The toolchains disagree here (tsc and Vite vs
    esbuild and Bun), and this is the 5.3.0 file pair (O-1).
  - Else, if exactly one exists → that file. If it is a `.d.ts` →
    `none(dts-target)`.
  - Else → `none(module-not-found)`.
- **Note.** `.d.ts` files are collected (as `.ts`). `.mjs`, `.cjs`, `.mts` and
  `.cts` are not collected.
- A directory's `package.json` (`main`, `types`, `exports`) is not read (R6).

### 9.3 TS/JS export lookup and re-exports

For name `x` in target module M:

1. M's explicit local exports: `export function|class x`,
   `export const x = <fn>`, `export default function|class`,
   `export default <identifier>`, `export { y as x }`. These are resolved with
   M's Tier 1 lookup and group rules. An import in M is a re-export hop.
2. `export { a as x } from` and `export { x } from` are hops.
3. `export * as x` gives `none(namespace-export)`.
4. Star exports (when x has no explicit export and is not `default`): exactly
   one provider → that provider. None → `none(export-not-found)`; several →
   `none(star-conflict)`.
5. `export =`, a CommonJS-only module, or a type-only export →
   `none(commonjs)` or `none(type-only)`.
6. **At most 3 re-export hops** after the first target module. More →
   `none(hop-limit)`; a cycle → `none(cycle)`. The limit is documented in the
   spec section, not in the fact version. It is pinned by `ts-reexport-3hop`
   (resolves) and `ts-reexport-4hop` (unchanged).

### 9.4 Python import bindings

| Form | Binding |
| --- | --- |
| `import a`, `import a.b` | `a` → module `a`; the chain `a.b.f()` is eligible |
| `import a.b as m` | `m` → module `a.b` |
| `from m import x [as y]`, relative forms | `y` → (m, x) |
| `from m import *` | `none(star-import)` |
| Imports under `try`/`if` (including `TYPE_CHECKING`), and function-local conditional imports | conditional: two or more narrow to the group; a single one gives `none(conditional)` |
| Function-local imports | bind in the function scope |

### 9.5 Python module paths

- Module names are dotted paths relative to the extraction root, which is
  treated as the `sys.path` entry.
- **Absolute name D:**
  - `D/__init__.py` (a regular package) comes before `D.py`;
  - `D.py` beats a namespace directory `D/` (A14), so `from D.sub` gives
    `none(module-not-found)` when D is a module;
  - a namespace directory alone is usable only as a path to submodules.
- **Dotted names resolve one component at a time (Codex review of treesitter-chunker#683).** For
  `a.b.c`, resolve `a`, then `a.b` inside `a`, then `a.b.c` inside `a.b`, applying
  the package-versus-module precedence above at every component. If any
  intermediate component resolves to a module (a `.py` file) rather than a
  package or namespace directory, the result is `none(module-not-found)`; never
  test only the final `D/__init__.py` or `D.py` path. Example: with `a.py` and
  `a/b.py` but no `a/__init__.py`, `from a.b import helper` gives
  `none(module-not-found)`, because Python loads `a.py` and `a` is not a
  package. The same applies to relative imports after the leading dots.
  Fixture: `py-ancestor-module-shadow` (near-miss).
- **Script-directory rule (A11, simplified).** An absolute import gives
  `none(script-dir-shadow)` when its first component resolves inside the
  importer's own directory and that directory is not the root. A script run
  directly, or under pytest's rootdir insertion, would import the sibling.
  Scripts that import siblings therefore stay ambiguous (Q5). **This rule is
  checked before `module-not-found`** (R-1(ii)). So the probe one-root case
  (`py/c.py: from a import helper` with root `probe-r9/`, where `a` resolves to
  `py/a.py` inside the importer's non-root directory) gives
  `none(script-dir-shadow)`.
- **Relative imports** start at the importer's package directory. Leaving the
  root gives `none(outside-root)`.
- A module not found in the run gives `none(module-not-found)` (external). No
  suffix matching.

### 9.6 Python name lookup in the target module

1. M's module-scope bindings: definitions follow the group rules. An import is
   a hop (this covers `__init__` re-exports). Anything else gives `none`.
2. **Attribute versus submodule (A12):** if M binds `x` and also has a
   submodule `x` → `none(attr-submodule-conflict)`.
3. x is a submodule only: calling it gives `none`; it may head a member chain.
4. Otherwise `none(export-not-found)`. The 3-hop limit is pinned by
   `py-reexport-3hop` and `py-reexport-4hop`.

### 9.7 What stays ambiguous or unresolved

- **TS/JS:** everything listed in 9.2–9.3 as `none`, plus nested namespace
  chains (`ns.sub.f`).
- **Python:** star imports, conditional imports (narrow only), `importlib` and
  `__import__`, `sys.path` changes, other roots, external packages, module
  `__getattr__`, `.pyi` stubs and extension modules.
- **Everywhere:** member calls other than namespace or module imports, and
  computed callees.

### 9.8 `none` reasons (Tier 2)

`external-module`, `outside-root`, `module-not-found`, `unknown-variant`,
`ambiguous-extension`, `dts-target`, `export-not-found`, `star-conflict`,
`namespace-export`, `commonjs`, `type-only`, `hop-limit`, `cycle`,
`script-dir-shadow`, `attr-submodule-conflict`, `conditional`, `star-import`.

## 10. Fixtures

### 10.1 Layout, provenance and tool exclusions

`tests/fixtures/call_resolution/`:

- **`greenfield-r1/<tree>/`**: all 16 round-1 trees, byte-for-byte. Greenfield
  confirmed them synthetic and safe to commit.
- **`probe-r9/`**: the probe tree, original layout.
- **`authored/<case>/`**: 108 trees (sections 10.3–10.5): the 106 that the
  president's re-check verified, plus `py-nonlocal-rebind` and
  `py-ancestor-module-shadow` from the Codex review of treesitter-chunker#683.
- **`expected/<tree>.json`**: per call (file, call span, reference):
  - `today`: the off-mode edge (resolution and candidates as
    `file:line:qualified_name`);
  - per mode, the lookup outcome (`local`, `import`, or `none` with its reason)
    and the expected edge;
  - `pr`: the PR whose head first asserts the final expectation.

  These are hand-written oracle tables, not generated goldens.
- **`provenance.json` and `PROVENANCE.md`**: source path, sha256 and source
  manifest for every copied file. The Greenfield manifest sha256 is
  `40575a9b…a1e46`. The evidence `SHA256SUMS` (sha256 `e1e0b01c…250e`) covers
  only the outputs and `r9probe_run.py`, so the probe files' hashes were
  computed for this plan:

  | File | sha256 |
  | --- | --- |
  | `pkg/over.ts` | `251c363f322d24c867a41c94def6dce86cf2fe2468eda7422d388623928c9446` |
  | `pkg/svc.ts` | `a373e3684282efc21a9005b1f9a543f3b78811bb0366159559e2667a274f58eb` |
  | `pkg/svc.tsx` | `2906c06b6c7bdc8388a58b6718a1f0533c3afa37768ef8dc0af5b30e9b5dbf8f` |
  | `pkg/use.ts` | `c7af3463aeef0a153d9638a251bc6a0e0b7147ec554c1ea03d6f4802658a354c` |
  | `py/a.py` | `b6631639de17fb869c43278f858c465cc5b71c8ec51c8c25d803905361f8a544` |
  | `py/b.py` | `80db5c431a8c630a959c421fba66ac80327fae4b813ada82ba2deae5c8d4532c` |
  | `py/c.py` | `bd7c3914703ec6fa39ca98113d2534841181032b80820ebc7c9d66cb8bcdb382` |
  | `py/pkg/__init__.py` | `11a2d0ad935bd347586d68821e82c9dc8bbd0f324f9ed572ea7c732490b9241b` |
  | `py/pkg.py` | `76adf090c7316f6da950398ec0da093577f5fce1e621fdc21c29fd41a307fccd` |
  | `py/redef.py` | `98a171ca61216a4f8d23b864733e4ce8f169744319cc37b11715ebe60d44ae66` |
- **`off_mode_baseline/`** (11.2) and **`scope_facts_digests.json`** (4.6).

Tool exclusions, all in PR 0:

- pytest `addopts += --ignore=tests/fixtures/call_resolution`.
  `greenfield-r1/r9-py/tests/test_svc.py` would otherwise be collected and fail.
- Black `extend-exclude` and Ruff `extend-exclude` entries for the directory.
  Ruff needs `extend-exclude`, not `exclude`: the canonical CI command's
  `--exclude archive --exclude logs --exclude site` flags replace the
  configured `exclude` list, so an `exclude` entry would be ignored in CI.
- `tests/test_call_resolution_fixture_collection.py` asserts that collecting
  `tests/fixtures` yields no tests. `test_lint_path_policy.py` stays green.
- `.gitattributes`: `tests/fixtures/call_resolution/** -text`.
- `MANIFEST.in`: `recursive-include tests/fixtures/call_resolution *`, so sdist
  tests keep their fixtures. A test checks the line exists and covers every
  fixture extension (`.ts`, `.tsx`, `.kt`, `.cs`, `.json`, …).

Extraction roots:

- each Greenfield and authored tree is its own root;
- the probe uses `probe-r9/` for TS and `probe-r9/py/` for Python;
- `probe-r9/` as a single root is also a near-miss.

### 10.2 Matrix: Greenfield round-1 and probe

"=" means unchanged from Today. PR is the head that first asserts the row's
final expectation. Every Today cell is from main.

| Tree | Call | Today | `structural` | `imports` | Rule or reason | PR |
| --- | --- | --- | --- | --- | --- | --- |
| r9-ts | svc.ts:4 A.m → t | amb {svc.ts:1 t, svc.tsx:1 t} | **resolved svc.ts:1 t** | = structural | t1.lexical | 2 |
| r9-ts | svc.ts:5 A.m2 → t (×2) | same | **resolved svc.ts:1 t** | = | t1.lexical | 2 |
| r9-ts | svc.ts:9 d → t (×2) | same | **resolved svc.ts:1 t** | = | t1.lexical | 2 |
| r9-ts | svc.ts:12, :13 caller → d | amb {svc.ts:8 d, svc.ts:9 d} | **resolved svc.ts:9 d** | = | t1.lexical, t1.ts_overload | 2 |
| r9-ts | svc.ts:14 caller → t | amb {svc.ts:1 t, svc.tsx:1 t} | **resolved svc.ts:1 t** | = | t1.lexical | 2 |
| r9-ts | svc.tsx:2 View → t | same | **resolved svc.tsx:1 t** | = | t1.lexical | 2 |
| r9-py | svc.py:16 C.b → C | amb {C@9, C@14} | = | = | group = C0 | 4 |
| r9-py | svc.py:31 caller → d | amb {d@19, d@24} | = | = | group = C0 | 4 |
| r9-py | 9 resolved; `unknown_thing` unresolved | — | = | = | not eligible | 1 |
| r9b-py, py-sameline, rt-tsclass | all resolved | — | = | = | not eligible | 1 |
| rt-pycond | svc.py:21 caller → d | amb {d@13, d@16} | = | = | conditional group = C0 | 4 |
| rt-pyrec | svc.py:23 d → d | amb {d@18, d@22} | = | = | group = C0 | 4 |
| rt-pyrec | svc.py:27 uses_c2 → C | amb {C@5, C@10} | = | = | group = C0 | 4 |
| rt-pyrec | `self.c` resolved; `C().c` unresolved | — | = | = | not eligible | 1 |
| rt-js | k.js:9 g → d | amb {d@3, d@6} | **resolved k.js:6 d** | = | t1.lexical, t1.js_hoist | 3 |
| probe | over.ts:6 g → f | amb {f@1, f@2, f@3} | **resolved over.ts:3 f** | = | t1.lexical, t1.ts_overload | 2 |
| probe | over.ts:6 g → new Box | amb {interface Box@4, class Box@5} | **resolved class Box@5** | = | t1.lexical | 2 |
| probe | svc.ts:2 caller → t (×2) | amb {svc.ts t, svc.tsx t} | **resolved svc.ts t** | = | t1.lexical | 2 |
| probe | use.ts:2 user → t | amb {svc.ts t, svc.tsx t} | = (import) | = | ambiguous-extension (O-1 default) | 5 |
| probe (py root) | c.py:4 use → helper | amb {a.py helper, b.py helper} | = (import) | **resolved a.py helper** | t2.import | 6 |
| probe (py root) | pkg/__init__.py:5 call_k → k | amb {pkg.py k, pkg/__init__.py k} | **resolved pkg/__init__.py k** | = | t1.lexical | 4 |
| probe (py root) | redef.py:11 caller → d | amb {d@1, d@4} | = | = | group = C0 | 4 |
| probe (one root) | py/c.py:4 use → helper | amb {py/a, py/b} | = | = | script-dir-shadow (`a` resolves inside the non-root directory `py/`; 9.5) | 6 |

### 10.3 Authored positives

| Case | Call | Today | `structural` | `imports` | Rule | PR |
| --- | --- | --- | --- | --- | --- | --- |
| ts-kind-filter | x.ts:1 use → t | amb {a.ts type t, e.ts enum t, b.ts t, c.ts t} | amb {b.ts t, c.ts t} | = | t1.kind | 1 |
| mixed-family | x.ts:1 use → helper | amb {a.ts, d.ts, b.py, c.go} | amb {a.ts, d.ts} | = | t1.family | 1 |
| ts-class-body | svc.ts:4 A.m → t | amb {svc.ts t, other.ts t} | resolved svc.ts t | = | t1.lexical (class body skipped) | 2 |
| ts-nested-only | a.ts:3 outer → t | amb {a.ts outer.t, b.ts other.t} | resolved a.ts outer.t | = | t1.lexical | 2 |
| ts-arrow-const | a.ts:2 f → helper | amb {a.ts helper (arrow), b.ts helper} | resolved a.ts helper | = | t1.lexical (2.6(c)) | 2 |
| ts-namespace-merge | a.ts:3 use → NS | amb {a.ts NS fn, a.ts NS module, b.ts NS} | resolved a.ts NS fn | = | t1.lexical (PR 1 interim: amb {a.ts NS fn, b.ts NS} by t1.kind) | 2 |
| js-class-plain-call | a.js:2 mk → Foo | amb {a.js class Foo, b.js Foo} | resolved a.js class Foo | = | t1.lexical | 2 |
| tsx-local | a.tsx:2 App → Foo | amb {a.tsx Foo, b.tsx Foo} | resolved a.tsx Foo | = | t1.lexical | 2 |
| js-template-call | a.js:2 g → t (in a template literal) | amb {a.js t, b.js t} | resolved a.js t | = | t1.lexical (join) | 2 |
| js-locals | a.js:5, :6 c4/c6 → mk | amb {a.js:7 mk, a.js:7 mk (returned arrow)} | resolved a.js:7 mk (function) | = | t1.lexical | 2 |
| ts-param-shadow | a.ts:3 loc → make | amb {a.ts:4 make, a.ts:4 make (arrow)} | resolved a.ts:4 make | = | t1.lexical | 2 |
| js-hoist-fnbody | a.js:4 g → d | amb {g.d@2, g.d@3, b.js h.d} | resolved g.d@3 | = | t1.lexical, t1.js_hoist (PR 2 interim: amb {g.d@2, g.d@3}) | 3 |
| py-class-scope-2 | a.py:10 K.meth → helper | amb {a.py helper, b.py helper} | resolved a.py helper | = | t1.lexical (class scope skipped) | 4 |
| py-nested-only | a.py:5 outer → helper | amb {a.py outer.helper, b.py other.helper} | resolved outer.helper | = | t1.lexical | 4 |
| py-class-call | a.py:6 make → C | amb {a.py class C, b.py C} | resolved a.py class C | = | t1.lexical | 4 |
| py-class-free-var | a.py:16 class J → helper | amb {a.py helper, b.py helper} | resolved a.py helper | = | t1.lexical (free name → module) | 4 |
| py-decorated | a.py:9 decorator of f → helper | amb {a.py helper, b.py helper} | resolved a.py helper | = | t1.lexical (decorator in enclosing scope; re-owned call) | 4 |
| py-redef-narrow | a.py:10 caller → d | amb {a.py d@1, a.py d@5, b.py d@1} | amb {a.py d@1, a.py d@5} | = | t1.lexical | 4 |
| ts-default-import | use.ts:2 → t | amb {svc.ts t, other.ts t} | = | resolved svc.ts t | t2.import | 5 |
| ts-export-default-ident | use.ts:2 → t | amb {svc.ts t, other.ts t} | = | resolved svc.ts t | t2.import | 5 |
| ts-namespace-import | use.ts:2 → svc.t | amb {svc.ts t, other.ts t} | = | resolved svc.ts t | t2.namespace | 5 |
| ts-ext-order | use.ts:3 → t (`./svc.js`, only svc.ts exists) | amb {svc.ts t, other.ts t} | = | resolved svc.ts t | t2.import | 5 |
| ts-ext-order | use.ts:3 → u (`./lib`, only lib/index.ts exists) | amb {lib/index.ts u, other2.ts u} | = | resolved lib/index.ts u | t2.import | 5 |
| js-importer-ext-order | use.js:2 → t (`./svc.js`; svc.js and svc.ts exist) | amb {svc.js t, svc.ts t} | = | resolved svc.js t | t2.import (exact JS extension) | 5 |
| ts-barrel | use.ts:2 → t (star, one provider); → v | amb {a.ts t, other.ts t}; amb {b.ts v, other.ts v} | = | resolved a.ts t; resolved b.ts v | t2.import | 5 |
| ts-reexport-3hop | use.ts:2 → t | amb {impl.ts t, other.ts t} | = | resolved impl.ts t | t2.import | 5 |
| ts-language-filter (unfiltered) | use.ts:2 → t | amb {svc.tsx t, a.ts t, b.ts t} | = | resolved svc.tsx t | t2.import | 5 |
| py-relative | pkg/sub/x.py:5 → helper | amb {pkg/util.py, pkg/other.py} | = | resolved pkg/util.py helper | t2.import | 6 |
| py-import-as | app.py:6 → u.helper; → pkg.util.helper | amb {pkg/util.py, other.py} (both) | = | resolved pkg/util.py helper (both) | t2.namespace | 6 |
| py-init-reexport | app.py:5 → helper | amb {pkg/impl.py, other.py} | = | resolved pkg/impl.py helper | t2.import | 6 |
| py-local-import | c.py:3 → helper | amb {a.py, b.py} | = | resolved a.py helper | t2.import | 6 |
| py-reexport-3hop | app.py:5 → helper | amb {impl.py, other.py} | = | resolved impl.py helper | t2.import | 6 |
| py-try-import | app.py:8 → helper | amb {fast, slow, other} | = | amb {fast, slow} | t2.import | 6 |
| py-two-imports | app.py:6 → helper | amb {a, b, c} | = | amb {a, b} | t2.import | 6 |

### 10.4 Authored near-misses (must stay unchanged)

All Today cells are `ambiguous` unless noted.

**TS/JS, Tier 1:**

| Case | Call | Today | Reason (both modes) | PR |
| --- | --- | --- | --- | --- |
| ts-nested-scope | a.ts:4 outer → t; a.ts:7 blk → t | {a.ts t, b.ts t} | binding not in C0 | 2 |
| ts-param-kind | u.ts:1 run → t | {k.ts interface t, j.ts t} | parameter (filter survivor unproven) | 2 |
| ts-enum-shadow | a.ts:2 f → E | {a.ts enum E, b.ts E} | non-callable (filter survivor unproven) | 2 |
| ts-dup-impl | a.ts:3 use → f | {a.ts f@1, a.ts f@2, other.ts f} | **narrows to {a.ts f@1, f@2}** (t1.lexical), stays ambiguous | 2 |
| ts-param-shadow | a.ts:2 run → t; a.ts:3 loc → t | {a.ts t, b.ts t} | parameter; local-variable | 2 |
| ts-signature-only | a.ts:2 use → s | {a.ts s (signature), b.ts s} | bodyless | 2 |
| ts-declare-ambient | a.ts:2 use → amb | {a.ts amb (declare), b.js amb} | ambient | 2 |
| ts-reassign | a.ts:2 g → t | {a.ts t, b.ts t} | reassigned | 2 |
| ts-type-only-import | use.ts:2 → t | {svc.ts t, other.ts t} | type-only | 2 |
| ts-two-imports | use.ts:3 → t | {a.ts t, b.ts t} | mixed-bindings | 2 |
| ts-dynamic-import | use.ts:1 → m.t | {svc.ts t, other.ts t} | local-variable | 2 |
| js-require | use.js:3 → t; → m.t | {svc.js t, other.js t} | local-variable (CommonJS deferred) | 2 |
| js-cjs-local | a.js:2 use → t | {lib.js t, other.js t} | local-variable | 2 |
| js-fnexpr-self | a.js:3 g.t → t | {a.js:2 t, b.js t} | self-binding | 2 |
| js-class-expr-self | a.js:2 K.m → t | {a.js t, b.js t} | self-binding | 2 |
| js-default-param | a.js:2 wrap.f → t | {b.js h.t, a.js wrap.f.t} | parameter (parameter scope) | 2 |
| js-tdz | a.js:3 g → t | {a.js t, b.js t} | binding not in C0 (block `const`) | 2 |
| js-block-fn | a.js:2 g → d | {a.js:1 d, a.js:1 d} | block-function | 2 |
| js-annexb-overwrite | a.js:4 g → d | {g.d@2, g.d@3} | block-function | 2 |
| js-var-fn | a.js:3 g → d | {a.js d@1, a.js d@2, b.js d} | expression-bound | 2 |
| js-esm-dup | a.js:3 g → d | {a.js d@1, a.js d@2, other.js d} | **narrows to {a.js d@1, d@2}** (t1.lexical), stays ambiguous | 2 |
| js-eval-with | a.js:2 e → t; a.js:3 w → t | {a.js t, b.js t} | dynamic-scope | 2 |
| js-locals | a.js:2–6 c1, c2, c4, c6 → t; c3 → t; args.js:2 c5 → arguments | {a.js t, b.js t}; {args.js, args2.js arguments} | local-variable; parameter | 2 |
| ts-declare-namespace | a.ts:2 N.use → f | {b.ts f, c.ts f} | namespace-merged (PR 2: namespace-deferred) | 3 |
| ts-namespace-global | c.ts:1 N.g → f | {a.ts N.f, b.ts N.f} | namespace-merged | 3 |
| js-script-global | s2.js:2 g → d | {s1.js d, s2.js d} | script-global (two browser scripts) | 3 |
| js-implicit-global | a.js:2 g → d | {a.js d, c.js d} | script-global (implicit global in b.js) | 3 |
| ts-dup-method | k.ts:10 `this.m`; k.ts:12 `new K().m` | {K.m@4, K.m@7}; **unresolved** | not eligible (member; guard) | 1 |
| ts-globalThis | a.ts:2 `globalThis.t`, `window.t` | {a.ts t, b.ts t} | not eligible (member) | 1 |
| ts-namespace-global | c.ts:2 `N.f` | {a.ts N.f, b.ts N.f} | not eligible (member) | 1 |

**TS/JS, Tier 2** (`structural` leaves all unchanged as an `import` outcome
without proof):

| Case | Call | Today | `imports` reason | PR |
| --- | --- | --- | --- | --- |
| ts-ext-collision-tsx | use.ts:2 → t | {svc.ts t, svc.tsx t} | ambiguous-extension | 5 |
| ts-ext-collision-js | use.ts:2 → t | {svc.ts t, svc.js t} | ambiguous-extension | 5 |
| ts-ext-collision-index | use.ts:2 → t | {p.js t, p/index.ts t} | ambiguous-extension | 5 |
| js-importer-ext-order | use2.js:2 → t (`./svc`) | {svc.js t, svc.ts t} | ambiguous-extension | 5 |
| js-importer-ext-order | use3.js:2 → u (`./only.js`, only only.ts exists) | {only.ts u, other.js u} | module-not-found | 5 |
| ts-dts | use.ts:2 → t | {lib.d.ts t, lib.js t, other.ts t} | ambiguous-extension | 5 |
| ts-dts-only | use.ts:2 → t | {lib.d.ts t, other.ts t} | dts-target | 5 |
| ts-export-missing | use.ts:2 → u | {a.ts u, b.ts u} | export-not-found | 5 |
| ts-import-cjs | use.ts:2 → t; use2.ts:2 → t (`import = require`) | {eq.ts t, other.ts t, svc.js t} | commonjs; local-variable | 5 |
| ts-alias-import | use.ts:2 → helper | {h1.ts helper, h2.ts helper} | binding not in C0 | 5 |
| ts-bare-specifier | use.ts:2 → t | {a.ts t, b.ts t} | external-module | 5 |
| ts-external-import-kind | u.ts:2 → t | {k.ts interface t, j.ts t} | external-module | 5 |
| ts-reexport-4hop | use.ts:2 → t | {impl.ts t, other.ts t} | hop-limit | 5 |
| ts-reexport-cycle | use.ts:2 → t | {a.ts t, b.ts t} | cycle | 5 |
| ts-star-conflict | use.ts:2 → t | {a.ts t, b.ts t} | star-conflict | 5 |
| ts-export-star-as | use.ts:2 → t | {impl.ts t, other.ts t} | namespace-export | 5 |
| ts-skipped-dir | use.ts:2 → t (`./dist/t`) | {a.ts t, b.ts t} | unknown-variant | 5 |
| ts-mjs-specifier | use.ts:2 → t | {a.ts t, b.ts t} | unknown-variant | 5 |
| ts-language-filter (`language="typescript"`) | use.ts:2 → t | {a.ts t, b.ts t} | unknown-variant | 5 |

**Python** (Tier 1 rows assert both modes):

| Case | Call | Today | Reason | PR |
| --- | --- | --- | --- | --- |
| py-cond-e | svc.py:18 caller → e | {e@9, e@14} | conditional group = C0 | 4 |
| py-cond-e | svc.py:12 e → e (after nested conditional `def e`) | {e@9, e@14} | conditional | 4 |
| py-closure-2 | a.py:10 inner → helper | {a.py, b.py} | binding not in C0 (outer.helper) | 4 |
| py-class-default | a.py:9 default of K.m → helper | {a.py, b.py} | class-scope-bound | 4 |
| py-class-free-var | a.py:10 class K (inside f) → helper | {a.py, b.py} | binding not in C0 (f.helper) | 4 |
| py-param-shadow | a.py:6 use → helper; a.py:11 loc → helper | {a.py, b.py} | parameter; local-variable | 4 |
| py-global-unbound | c.py:2 → helper | {a.py, b.py} | unbound | 4 |
| py-global-rebind | a.py:11 use → helper | {a.py, b.py} | mixed-bindings | 4 |
| py-builtin-family | c.py:2 → open | {a.py open, x.js open} | unbound (family survivor unproven) | 4 |
| py-overload | a.py:13 use → f | {f@5, f@7, f@8} | group = C0 | 4 |
| py-module-positional | a.py:13 caller → d | {d@1, d@8} | group = C0 | 4 |
| py-scopes | comprehension, walrus, nonlocal, del, with, for and match callers → helper; lambda → helper | {a.py, b.py} each | local-variable; parameter | 4 |
| py-nonlocal-rebind | a.py:14 outer → helper (outer defines `helper`; nested `swap` does `nonlocal helper; helper = other`); b.py:5 f → helper (f's own nested `helper`). No top-level `helper` exists, so both nested defs are candidates | {a.py outer.helper, b.py f.helper} each | outer → helper: mixed-bindings (nonlocal write); f → helper: **resolved b.py f.helper** (t1.lexical) | 4 |
| py-dynamic-scope | a1–a4 go → helper (exec, globals, vars, sys.modules) | {a1, a2, a3, a4} | dynamic-scope | 4 |
| py-star-import | c.py:5 → helper | {a.py, b.py} | star-import | 4 |
| py-dynamic-import | app.py:6 → m.helper | {a.py, b.py} | local-variable | 4 |
| py-closure | a.py:10 inner → helper | **resolved** to a.py:1 helper (wrong; Q8) | not eligible | 1 |
| py-class-scope | a.py:10 K.meth → helper | **resolved** a.py helper | not eligible | 1 |
| py-dynamic-dispatch | a.py:6 `self.run`; a.py:15 `x.run` | {A.run, B.run} | not eligible (member) | 1 |
| py-type-checking | app.py:8 → helper | {a.py, b.py} | conditional (`imports`) | 6 |
| py-local-cond-import | app.py:4 → helper | {a.py, b.py} | conditional (`imports`) | 6 |
| py-relative-root | x.py:5 → helper | {a.py, b.py} | outside-root | 6 |
| py-script-dir-import | tools/run.py:5 → helper | {util.py, tools/util.py} | script-dir-shadow | 6 |
| py-attr-vs-submodule | app.py:5 → helper | {pkg/impl.py, pkg/helper.py} | attr-submodule-conflict | 6 |
| py-namespace-dir | app.py:5 → helper | {D/sub.py, other.py, D.py} | module-not-found (D is `D.py`) | 6 |
| py-ancestor-module-shadow | app.py: `from a.b import helper` then `helper()`, with `a.py`, `a/b.py` (no `a/__init__.py`) and `other.py` each defining `helper` | {a.py, a/b.py, other.py} | module-not-found (intermediate `a` is a module) | 6 |
| py-reexport-4hop | app.py:5 → helper | {impl.py, other.py} | hop-limit | 6 |

### 10.5 Controls

| Tree | Today | On (both modes) | PR |
| --- | --- | --- | --- |
| ctl-go | a/a.go:5 → helper amb {a/a.go, b/b.go, c/c.go type} | byte-identical | 1 |
| ctl-rust | a.rs:2 → helper amb {a.rs, b.rs, c.rs struct} | byte-identical | 1 |
| ctl-c | a.c:2 → helper amb {a.c, b.c, c.c struct} | byte-identical | 1 |
| ctl-cpp | a.cpp:2 → helper amb {a.cpp, b.cpp, c.cpp struct} | byte-identical | 1 |
| ctl-java, ctl-kotlin, ctl-csharp | no call edges | byte-identical; a test asserts they emit no call edges | 1 |
| mixed-family | c.go:5 use2 → helper amb {a.ts, d.ts, b.py, c.go} | unchanged (Go caller not eligible) | 1 |
| Greenfield rt-go, rt-rust, rt-cpp, rt-java, rt-kotlin, clo-go, clo-kotlin, clo-rust | as in 3.1 | byte-identical | 1 |
| `tests/fixtures/boundary_ir/repos/*` | existing goldens (ambiguous edges in go, javascript, python, typescript) | harness inputs: identity invariants on and off | 1 |

"Byte-identical" for a control means identical except
`run.options.call_resolution`, with no edge carrying the new keys (gate 7).

### 10.6 Traceability (C4)

The suite fails unless every rule ID and every `none` reason has at least one
case below. Expected tables record each call's lookup outcome, and a test
compares the analyzer's output with them.

| ID or reason | Cases |
| --- | --- |
| t1.kind | ts-kind-filter; ts-namespace-merge (PR 1 interim) |
| t1.family | mixed-family |
| t1.lexical | r9-ts, probe, ts-class-body, ts-nested-only, tsx-local, py-class-scope-2, py-redef-narrow, … |
| t1.ts_overload | r9-ts `d`; probe `f` |
| t1.js_hoist | rt-js; js-hoist-fnbody |
| t2.import | ts-default-import, ts-barrel, ts-reexport-3hop, py-relative, py-init-reexport, py-try-import, … |
| t2.namespace | ts-namespace-import; py-import-as |
| binding not in C0 | ts-nested-scope, js-tdz, py-closure-2, py-class-free-var (K), ts-alias-import |
| unbound | py-global-unbound, py-builtin-family, ts-kind-filter, mixed-family |
| parameter | ts-param-kind, ts-param-shadow, js-default-param, js-locals (c3, `arguments`), py-param-shadow, py-scopes (lambda) |
| local-variable | ts-param-shadow, js-locals, js-cjs-local, js-require, ts-dynamic-import, ts-import-cjs (`import =`), py-scopes, py-dynamic-import |
| expression-bound | js-var-fn |
| self-binding | js-fnexpr-self, js-class-expr-self |
| reassigned | ts-reassign |
| block-function | js-block-fn, js-annexb-overwrite |
| conditional | py-cond-e (inner), py-type-checking, py-local-cond-import |
| mixed-bindings | ts-two-imports, py-global-rebind, py-nonlocal-rebind |
| class-scope-bound | py-class-default |
| star-import | py-star-import |
| dynamic-scope | js-eval-with, py-dynamic-scope |
| ambient | ts-declare-ambient |
| bodyless | ts-signature-only |
| non-callable | ts-enum-shadow; B7 `declare enum` (`test_b7_*`, written by the test) |
| namespace-merged | ts-declare-namespace, ts-namespace-global |
| script-global | js-script-global, js-implicit-global |
| type-only | ts-type-only-import |
| no-binding-fact, unmapped | named synthetic-facts tests (R-3; listed below the table) |
| unsupported file | named end-to-end failure-mode tests (R-3; listed below the table) |
| TS `using` / `await using` (fail closed, 7.5) | `test_using_near_miss_end_to_end` in `tests/test_call_resolution_tier1_js.py`, on a tree the test writes (a committed tree would change the off-mode baseline, 11.2) |
| stub, script-goal-deferred, namespace-deferred | interim heads only (PR 1, PR 2) |
| external-module | ts-bare-specifier, ts-external-import-kind |
| outside-root | py-relative-root |
| module-not-found | js-importer-ext-order (use3), py-namespace-dir, py-ancestor-module-shadow |
| unknown-variant | ts-skipped-dir, ts-mjs-specifier, ts-language-filter (filtered) |
| ambiguous-extension | probe use.ts, ts-ext-collision-*, js-importer-ext-order (use2), ts-dts |
| dts-target | ts-dts-only |
| export-not-found | ts-export-missing |
| star-conflict | ts-star-conflict |
| namespace-export | ts-export-star-as |
| commonjs | ts-import-cjs |
| hop-limit | ts-reexport-4hop, py-reexport-4hop |
| cycle | ts-reexport-cycle |
| script-dir-shadow | py-script-dir-import, probe one-root (`probe-r9/` as root) |
| attr-submodule-conflict | py-attr-vs-submodule |

**Generated coverage for the three reasons no valid tree produces (R-3).**

- **Synthetic-facts tests** start from a committed tree's real facts, apply one
  mutation, run the real `assemble_symbol_graph`, and assert two things: the
  recorded reason, and that the edge equals its off-mode form. They live in
  `tests/test_call_resolution_failure_modes.py`:

  | Test | Base tree (committed) | Mutation | Expected |
  | --- | --- | --- | --- |
  | `test_no_binding_fact_dropped_entry_js` | `authored/ts-class-body` | drop the binding entry for `svc.ts:4` `t` | `none(no-binding-fact)`; edge = off |
  | `test_no_binding_fact_dropped_entry_py` | `authored/py-class-scope-2` | drop the binding entry for `a.py:10` `helper` | `none(no-binding-fact)`; edge = off |
  | `test_unmapped_missing_symbol` | `authored/tsx-local` | drop the symbol record that `a.tsx:1` `Foo` maps to | `none(unmapped)`; edge = off |
  | `test_unmapped_duplicate_key` | `authored/py-class-call` | duplicate the `(node_type, span)` key of `a.py` class `C` | `none(unmapped)`; edge = off |
  | `test_unmapped_unclassified_node` | `authored/ts-nested-only` | remove `function_declaration` from the allow-list (monkeypatched) | `none(unmapped)`; edge = off |

- **End-to-end failure-mode tests** run `extract_symbol_graph` on a temporary
  copy of a committed tree with one change, and assert `supported: false` for
  the file and on equals off for every edge. Also in
  `tests/test_call_resolution_failure_modes.py`:

  | Test | Base tree (committed) | Change |
  | --- | --- | --- |
  | `test_unsupported_syntax_error` | `authored/ts-class-body` | append a syntax error to `svc.ts` |
  | `test_unsupported_deep_nesting` | `authored/py-class-scope-2` | append a deeply nested expression that triggers `RecursionError` in the analyzer |
  | `test_unsupported_analyzer_exception` | `greenfield-r1/r9-ts` | monkeypatch the JS analyzer to raise |

- The traceability test asserts that each named test exists, so coverage
  cannot pass vacuously. If PR 2 or PR 4 finds a natural form that produces
  `unmapped`, it is added as a committed near-miss.

## 11. Identity stability proof

### 11.1 Harness

`tests/call_resolution_harness.py` and `tests/test_call_resolution_identity.py`
run over every fixture tree (Greenfield, probe, authored, controls) and every
`tests/fixtures/boundary_ir/repos/*` repo. They are **parametrized per tree and
mode**, because smoke runs with `-n 2 --timeout=60`.

**Symbol graph, off versus on:**

1. `symbol_lookup` (keys include `#N`), `symbols`, `call_facts` and non-call
   relationships are equal, in order.
2. Call relationships have the same length, order and `call_site_id`s. Fields
   are equal except `to`, `resolution`, `candidates`, `is_internal` and
   `provenance`. Provenance differs only by the two keys, and only on changed
   edges.
3. Narrowing:
   - on-candidates ⊆ off-candidates;
   - an edge that is not `ambiguous` off is identical on;
   - an `ambiguous` edge on has two or more candidates and `to == reference`;
   - a `resolved` edge on has `candidates == [to]`, `to` ∈ off-candidates,
     `is_internal` true, and `call_rules` naming a binding rule (`t1.lexical`,
     `t2.import` or `t2.namespace`).
4. `metadata` is equal except `call_resolution`.

**Boundary IR, off versus on**, by edge `id`, for both `resolution_mode`
values:

5. `nodes`, `files`, `diagnostics`, `source` and `schema_version` are
   byte-identical.
6. The edge `id` set is the same. Non-call edges are byte-identical. Call edges
   are equal except `target`, `resolution`, `candidates`,
   `metadata.is_internal` and the two provenance keys. `call_site_id == id`.
7. **Boundary narrowing invariants (B2):**
   - an edge that is not `ambiguous` off is byte-identical on;
   - on-candidates ⊆ off-candidates;
   - an `ambiguous` edge on has two or more candidates, `target == reference`
     and `metadata.is_internal` false;
   - a `resolved` edge on has `target` ∈ off-candidates,
     `candidates == [target]` and `metadata.is_internal` true;
   - on both sides, ambiguous edges keep `target == reference`, and candidates
     are sorted and unique;
   - a changed edge carries both provenance keys, with the run's mode and a
     non-empty list of known rule IDs.
8. `metrics` are equal except `resolved_edges` and `ambiguous_edges`, whose sum
   is unchanged. `run.options` is equal except `call_resolution`.

**Off-mode equals today:**

9. `call_resolution="name"` is byte-identical to omitting the argument.
10. Off-mode output equals the PR 0 baseline (11.2).
11. Boundary goldens pass with no regeneration.

**Cache and determinism:**

12. On-mode cold and warm runs are byte-identical, and repeated cold runs are
    byte-identical.
13. The 4.4 cache tests pass, plus a cold run after switching modes on one
    directory, in both directions.

### 11.2 Off-mode baseline (PR 0, B4)

- **What it stores.** `tests/fixtures/call_resolution/off_mode_baseline/<tree>/`
  holds canonical off-mode documents for every fixture tree:
  - the symbol graph, as canonical JSON with paths relative to the root;
  - the Boundary IR parity view, for `strict` and `permissive`.

  They are captured cold, and an incremental warm run must reproduce them.
- **Capture script.** `scripts/capture_call_resolution_off_baseline.py` checks
  by default and writes only with `--write`.
- **Pinning.** `off_mode_baseline/MANIFEST.sha256` lists every document, and
  its own sha256 is pinned in the test module.
- **Provenance.** PR 0 changes no product code, so CI proves the baseline came
  from unmodified code. PR 0's description records a one-time comparison of
  parity digests against the released 7.0.0 wheel, or says why it could not be
  done.
- **Regeneration.** A lock-change regeneration is its own PR with no product
  change. A cross-OS mismatch is a portability bug, never a reason to
  regenerate. This replaces revision 1's R5.

### 11.3 Mutation proofs

Comparator self-tests apply each mutation to a real (off, on) pair. M5–M8 and
M12 also run on Boundary IR.

| # | Mutation | Must fail |
| --- | --- | --- |
| M1 | Change one `definition_id` | 1, 5 |
| M2 | Swap two `#N` suffixes | 1, 5 |
| M3 | Change one `call_site_id` (or hash the target into it) | 2, 6 |
| M4 | Change a non-call edge's target or resolution | 1, 6 |
| M5 | Empty an ambiguous edge's candidates | 3, 7 |
| M6 | Add a candidate not in the off set | 3, 7 |
| M7 | Re-target an edge that is resolved when off | 3, 7 |
| M8 | Change an unresolved edge | 3, 7 |
| M9 | Reorder call relationships | 2 |
| M10 | Drop an edge | 2, 6 |
| M11 | Add an extra provenance key | 2, 6 |
| M12 | Resolved edge with `candidates != [target]` | 3, 7 |
| M13 | Change one byte of off-mode output | 10 |
| M14 | Resolve an edge with `call_rules == ["t1.kind"]` only | 3 |

Each product PR also records one manual product mutation in its description:
the command, the head SHA, the failing harness output and the revert (B18).

## 12. Consumer impact

**Default (off).** Nothing changes: output, cache keys and records are
byte-identical.

**When on:**

- No identity changes. Joins on `call_site_id`, `definition_id`, node IDs and
  `#N` stay valid.
- **Every resolved edge is binding-proven.** It has today's resolved shape plus
  the two provenance keys (4.3).
- Ambiguous edges keep two or more candidates, always a subset of today's.
- An edge whose proven binding is not in C0 is never resolved. The filters may
  still narrow it to two or more candidates, which are then known to be wrong
  (treesitter-chunker#685).
- `parity_digest` changes for on-mode documents. Derived counts (`metrics`,
  clustering weights) change, so recompute them.
- Boundary edge positions can move; key on `id`.
- Semantic resolvers see the narrowed edges.
- **Caches:** switching modes on one cache directory is cold both ways and
  orphans the other mode's records. Use one cache directory per mode.
- **CLI:** `symbols extract` defaults to `-l python` and cannot run unfiltered,
  so its Tier 2 never links `.ts` with `.tsx`. Use `boundary` or the API for
  TS/JS.

**Greenfield.**

- Round 1: r9-ts's 9 edges (PR 2 head) and rt-js's 1 edge (PR 3 head) resolve.
  Nothing else changes.
- Greenfield's adapter (`greenfield/interface_boundary.py` `_adapt_edges`)
  rebuilds edges from type, source, target and resolution, and copies neither
  provenance nor `run.options`.
- It also sees the 7.0.0 `C().c` change (3.1) regardless of the option.
- Greenfield reported 15 ambiguous edges on 5.0.1 that really are different
  definitions (Greenfield Exec, relayed by the executive's 2026-11-20 update;
  Greenfield's count, not re-verified here). Of those, the dynamic-dispatch
  edges stay ambiguous because member calls are never narrowed. The import
  edges resolve only in `imports` mode, with a proof, and only when the target
  is in C0.

**Code-Index-MCP.** It is off by default, and the same shape rules apply if it
opts in. Revision 1's specific claims about Code-Index-MCP had no cited
evidence and are removed (B14).

## 13. Delivery

### 13.1 Seven PRs, strictly sequential (ruling 2.3)

Each PR merges with a merge commit at its exact reviewed head, after panel and
president approval and full CI. The next PR starts only after the previous one
merges. All of Tier 1 merges before any Tier 2. Every PR refs
treesitter-chunker#682; **only PR 6 closes it**. The executive sizes each panel.

| PR | Contents | Rows it finalizes |
| --- | --- | --- |
| **0** | **Test-only.** Fixture trees and provenance; `.gitattributes`; pytest, Black, Ruff and `MANIFEST.in` entries and the collection test; the off-mode baseline with its guarded script; the `today` fields of the expected tables, with their test. | Today cells |
| **1** | **Surface and engine.** Types, parameters (including `language_filter` and the fallback path), CLI flags, `run.options`, provenance copy, schema and spec text, cache keys in both branches. Engine with the binding-proof invariant, `t1.kind`, `t1.family`, per-family fact versions and the scope-facts schema. Stub analyzers. Allow-list scaffold. Identity harness and mutation self-tests. Experimental label. | PR 1 rows: filters narrow; nothing resolves |
| **2** | **Tier 1 TS/JS core:** scope chain, class-body skip, parameter scope, self-binding, position independence, block functions → `none`, reassignment, module-goal lookups, `t1.ts_overload`, duplicate-body groups, the JS/TS allow-list. Script-goal top levels, namespace bodies and ambient handling give interim `none`. **Panel note (N-1):** an exported function yields both an `export_statement` chunk and the inner function chunk; the join must pick the one that carries the symbol (5.4), or every exported positive fails closed as `unmapped`. | PR 2 rows (r9-ts) |
| **3** | **`t1.js_hoist` and globals:** hoisting with Annex B, `script_globals` including implicit globals, script-goal lookups, TS namespace merging, inherited ambient status. | PR 3 rows (rt-js) |
| **4** | **Tier 1 Python.** | PR 4 rows |
| **5** | **Tier 2 TS/JS.** Introduces `imports`. Applies the O-1 decision (default (a)). | PR 5 rows |
| **6** | **Tier 2 Python.** Closes treesitter-chunker#682. Removes the experimental label if the owner agrees. | PR 6 rows |

### 13.2 Test lanes

- **New test files:** `tests/test_call_resolution_{surface,identity,fixture_provenance,fixture_collection,today,allowlist,cache,failure_modes,tier1_js,tier1_py,tier2_js,tier2_py}.py`.
- **PR CI.** The new files go in `CI_SMOKE_TESTS` (Linux 3.14, `-n 2
  --timeout=60`). The identity and Tier 2 files also go in
  `run_platform_core.py` (Linux, macOS, Windows). Lane policy tests must stay
  green.
- **Before merge.** A manual full dispatch, with its run URL and head SHA
  recorded in the PR.
- **Local on dev0, narrow only.** Check `free -h`, `/proc/loadavg`, `nproc` and
  memory pressure first. Run serially or with `-n 2`. Never run
  `run_platform_core.py` or `run_full_suite.py` locally. The command is this
  plan's `automation.suite_command`, plus CONTRIBUTING's Ruff, Black and mypy
  commands.
- **Windows preflight** (CONTRIBUTING) for PRs 5 and 6 when the shared WIN host
  is free; otherwise rely on CI's Windows job, and say so.

### 13.3 Release gates for any release the owner approves

These gates are not part of treesitter-chunker#682's delivery. Gates 1–7 are automated tests from
PR 1 onward (11.1); gates 8–9 apply at release time. **Greenfield agreed in
writing on 2026-11-20 (Greenfield Exec thread, relayed by the executive)** to
the wording of gates 5 and 7 and to the parity-digest change.

1. Off mode is byte-identical to today: the baseline is unchanged and goldens
   are never regenerated.
2. `call_site_id` is unchanged on and off.
3. `definition_id`, `node_id` and `#N` are unchanged on and off.
4. Every ambiguous edge keeps a `candidates` list: narrowed, never emptied, two
   or more entries, a subset of today's.
5. **A narrowed resolved edge** has every field of a natively resolved edge,
   with today's meaning:
   - `target` is the definition's node ID;
   - `resolution` is `resolved`;
   - `candidates == [target]`;
   - `metadata.is_internal` is true;
   - its provenance differs from a natively resolved edge's only by
     `call_resolution` and `call_rules`.
6. Non-call edges, and calls that are not ambiguous when off, are identical.
7. **The controls are identical on and off** except
   `run.options.call_resolution`, and no control edge carries the new keys.
8. Greenfield runs its 42 reference IRs with the option on and signs off on the
   changed-edge report.
9. Full three-OS CI passes at the release head.

## 14. Deferred, explicitly out of scope

- Go, Java, Kotlin, C#, Rust and C/C++ resolution.
- Receiver-typed member calls (`self.m()`, `this.m()`, `obj.m()`).
- Class-qualified static calls across files.
- CommonJS `require`/`module.exports`, and TS `import = require`.
- tsconfig `paths`/`baseUrl`, and `package.json` `exports`/`main`/`types`.
- Pairing `.d.ts` files with their implementations.
- Nested namespace re-exports.
- Python roots other than the extraction root.
- Python positional resolution and `@overload` grouping.
- Binding substitution for renamed imports (Q1, treesitter-chunker#684), and
  demotion of wrong single candidates (Q8, treesitter-chunker#685).

## 15. Risks, open questions and owner question

| # | Item | Status and recommendation |
| --- | --- | --- |
| Q1 | Remove-only: renamed imports stay unchanged; the option fixes collisions, not missing edges | **Settled:** remove-only. Follow-up issue "binding substitution for renamed imports": filed by the executive as treesitter-chunker#684 ("Call resolution: binding substitution for renamed imports"). |
| Q2 | Provenance keys on changed edges | **Settled:** kept, under the 2.4 gate wording that Greenfield agreed. |
| Q3 | Kind-only resolution | **Settled (ruling 2.1):** resolution needs a binding proof. Filters only narrow. |
| Q4 | Python redefinition | **Settled:** an executive decision Greenfield accepted (section 8). Positional resolution and `@overload` stay deferred. |
| Q5 | Python roots | Accept: root-relative only, plus the script-directory rule. Scripts importing siblings stay ambiguous. |
| Q6 | `.d.ts` targets | Accept: `none(dts-target)`. |
| Q7 | Hop limit | 3 hops, pinned by the 3- and 4-hop fixtures for TS and Python. Not part of the fact version. |
| Q8 | Wrong single-candidate edges, and proofs whose binding is not in C0 | Out of scope. Follow-up issue filed by the executive as treesitter-chunker#685 ("Call resolution: demote wrong single-candidate edges caused by qualified-name-first matching"). |
| **O-1** | **Owner question, non-blocking; answer before PR 5 merges.** When `./svc` matches more than one file (for example `svc.ts` and `svc.tsx`), toolchains disagree: tsc and Vite pick `svc.ts`, esbuild and Bun pick `svc.tsx`. **(a) default, applied:** leave the edge unchanged; the probe `use.ts` call stays ambiguous. (b) Pick `svc.ts` by TypeScript's order. (c) Pick as in (b), but tag the edge `t2.import_ext_order`. | **Default (a) is in effect** unless the owner overrides it before PR 5 merges. If (b) or (c) is chosen, PR 5 changes the probe `use.ts` row and the ts-ext-collision rows accordingly. |
| R1 | The analyzer misses a binding form | Fail closed; the allow-list test (7.5). |
| R2 | JS goal detection. CommonJS files stay script goal (a top-level `require(` also occurs in AMD browser scripts). | Accept. Misclassification only adds `none` through the script-global check; hoisting behaves the same inside a CommonJS wrapper. |
| R3 | A third parse per file when on | Opt-in only. Record timings in each PR. |
| R4 | Edge reordering in Boundary IR | Documented; consumers key on `id`. |
| R5 | Baseline regeneration | Replaced by the 11.2 process. |
| R6 | A directory's `package.json` changes TS resolution | Accept. The NIT to record such directories is **rejected** (A14): `package.json` is not a collected file, so reading it would make per-file facts depend on a file outside the cache key. |
| R7 | Python extension modules shadow `.py` | Accept. |
| R8 | Interim behavior between PRs | Experimental label, plus a per-head CHANGELOG statement (4.5). |
| R9 | Scripts outside the run (HTML-included, `dist/`, `node_modules`) can redefine a global | Accept: they are not scanned. |
| R10 | Python monkeypatching (`import a; a.d = x`, `setattr(a, "d", …)`, `mock.patch("a.d")`) is not tracked | Accept. This is the same kind of risk as the module-scope preference the issue asks for. |

**Owner notice** (informational, from the ruling): these are delegated
decisions, all stricter than or consistent with the issue:

- JS hoisting resolves to the last declaration;
- Python redefinitions never resolve;
- kind or family filtering alone never resolves an edge;
- extension collisions give `none` (subject to O-1).

## 16. Acceptance criteria for this plan

- Rules per tier and language, with the binding-proof invariant (sections 6–9).
- The opt-in surface with API, provenance, schema and cache (section 4).
- A fixture matrix with re-derived Today cells, per-PR assignment and
  traceability (section 10).
- The identity proof with baseline and mutations (section 11).
- Consumer impact, delivery, release gates, deferred work, risks and O-1
  (sections 12–15).
- Ruling traceability (appendix B).

## Appendix A: how the baseline was produced

Narrow runs only, after checking headroom. When load was 62–68 on 24 cores, the
runs were deferred until load fell below 22. Scripts lived in a scratch
directory; trees were copied out of `gf48-probes` and the evidence directory
first.

Today cells (one process, all trees):

```python
import sys
from pathlib import Path
from chunker.symbol_graph import extract_symbol_graph

for arg in sys.argv[1:]:
    root, _, lang = arg.partition("=")          # "tree" or "tree=language"
    g = extract_symbol_graph(Path(root), lang or None)
    s = g["symbol_lookup"]
    lab = lambda i: f"{s[i]['file']}:{s[i]['line']}:{s[i]['qualified_name']}({s[i]['kind']})"
    for e in g["relationships"]:
        if e["type"] == "calls":
            print(e["file"], e["line"], lab(e["from"]), e["reference"],
                  e["resolution"], [lab(c) for c in e["candidates"]])
```

6.0.0 comparison (Boundary IR on main against `r1/out/upstream-<tree>.json`):

```python
import json, sys
from pathlib import Path
from chunker.boundary import extract_boundary_ir

trees, upstream = Path(sys.argv[1]), Path(sys.argv[2])
for name in sys.argv[3:]:
    new = extract_boundary_ir(trees / name)
    old = json.loads((upstream / f"upstream-{name}.json").read_text(encoding="utf-8"))
    a = {e["id"]: e for e in old["edges"]}
    b = {e["id"]: e for e in new["edges"]}
    same_nodes = sorted(n["id"] for n in old["nodes"]) == sorted(n["id"] for n in new["nodes"])
    diffs = [(k, f, a[k].get(f), b[k].get(f))
             for k in sorted(set(a) & set(b))
             for f in ("source", "target", "resolution", "candidates", "type", "reference")
             if a[k].get(f) != b[k].get(f)]
    diffs += [(k, "added" if k in b else "removed") for k in sorted(set(a) ^ set(b))]
    print(name, "node_ids_same:", same_nodes, "edge_diffs:", diffs)
```

## Appendix B: Ruling traceability

| RC | Applied in |
| --- | --- |
| RC-1 [P] | §1 Core rule; §6.3 algorithm and invariant; §11.1 check 3 and M14; §12 (the `t1.kind` advice is deleted); §15 Q3 |
| RC-2 [P] | §7.1 (split IDs; JS rows cut); §6.3; §10.3 (ts-kind-filter, mixed-family); §10.6 |
| RC-3 | §2; §3.2 (C0 note); §6.2 (C0 construction, P9); §6.3 and §12 (binding not in C0; Q8) |
| RC-4 | §7.2 (self-binding, parameter scope, position and TDZ, `class_static_block`, block functions, reassignment) |
| RC-5 | §7.2 `script_globals` and implicit globals; §15 R9 |
| RC-6 | §7.4 (no-body row; inherited ambient status); §7.2 Ambient |
| RC-7 [P] | §7.3 class scope (A10 as modified); the "skips enclosing functions" wording removed |
| RC-8 | §7.3 fail-closed (`vars`, `sys.modules`) |
| RC-9 | §7.5 allow-list and test |
| RC-10 | §7.2 CommonJS; §15 R2 |
| RC-11 [P] | §9.2 rewritten; §10.2 probe `use.ts`; §10.3 ts-ext-order and js-importer-ext-order; §10.4 collision near-misses |
| RC-12 | §9.5 script-directory rule |
| RC-13 | §9.5 (`D.py` vs `D/`); §9.6 (attribute vs submodule) |
| RC-14 | §4.2 `language_filter` and P8; §12 CLI |
| RC-15 | §9 intro; §1 "What it fixes"; §15 Q1 |
| RC-16 | §9.3 item 6; §9.6 item 4; §10.3–10.4 3- and 4-hop fixtures (TS and Python) |
| RC-17 [P] | §3 (re-derivation); §10.2–10.5 Today cells; §10.1 `today` field; §13.1 PR 0 |
| RC-18 | §8 table; §10.3 py-redef-narrow |
| RC-19 | §6.3 counterexamples; §10.3 js-class-plain-call and mixed-family; §10.4 ts-param-kind, py-builtin-family, ts-external-import-kind, ts-enum-shadow |
| RC-20 | §10.3–10.4: js-fnexpr-self, js-default-param, js-tdz, js-annexb-overwrite, js-implicit-global, ts-signature-only, ts-declare-namespace, tsx-local, js-cjs-local, js-script-global, py-class-default, py-class-free-var, py-script-dir-import, py-attr-vs-submodule |
| RC-21 | §10.5 controls |
| RC-22 | §10.1 expected tables; §10.6; §7.6 and §9.8 reason lists; C4 near-misses (js-locals, js-class-expr-self, ts-type-only-import, ts-export-default-ident, ts-export-star-as, ts-skipped-dir, ts-mjs-specifier, ts-reexport-cycle, ts-reexport-3hop, py-scopes, py-dynamic-scope, py-decorated, …) |
| RC-23 [P] | §10.2–10.5 PR column; probe `new Box` is `t1.lexical`; PR 1 resolves nothing |
| RC-24 | §10.4 py-relative-root, py-type-checking, py-local-cond-import |
| RC-25 | §11.1 check 7; §11.3 (M5–M8 and M12 on Boundary IR) |
| RC-26 [P] | §13.3 gates 5 and 7; §4.3 parity digest and resolved shape; §12; Greenfield's agreement recorded as received; fallback kept as a historical note (§4.3) |
| RC-27 | §11.2; §15 R5 |
| RC-28 | §4.4 cache tests; §12 |
| RC-29 | §4.2 fallback path |
| RC-30 | §5.3 |
| RC-31 | §5.4 |
| RC-32 | §4.6 |
| RC-33 | §11.1 (parametrized); §11.2 (no cross-OS regeneration); §13.2 (dispatch URL and SHA) |
| RC-34 | §4.5; §4.2 CLI help |
| RC-35 | §4.3 (semantic resolvers); §4.2 and §12 (`-l python`); §12 (5.0.1 count cited; Code-Index-MCP claims removed) |
| RC-36 | §4.1 (B15); §4.3 and §6.3 (B16: identity by `id`; "Resolution remains heuristic" updated in the spec text, PR 1); §10.1 (B17 `MANIFEST.in`); §11.3 (B18) |
| RC-37 [P] | §13.1 seven PRs; §1 Delivery; §4.2 (PR 1 introduces `name`/`structural`, PR 5 `imports`) |
| RC-38 | §1; §8 attribution, the verbatim condition, (a)–(c) with the (c) fallback, and Greenfield's confirmation received; §15 Q4 |
| RC-39 | §8 (PR 3, own rule ID); §7.2 (what is not scanned); §15 R9 |
| RC-40 | §13.3 renamed; no version named anywhere |
| RC-41 | Front matter `automation.suite_command` |
| RC-42 | §15 R6, R9, R10 |
| RC-43 | §15 Q1 (treesitter-chunker#684) and Q8 (treesitter-chunker#685); §14; §6.3; §12 |
| RC-44 | §15 O-1 and owner notice; §1; §9.2 |
| RC-45 | Appendix A (6.0.0 comparison script); §9.2 note on `.d.ts`, `.mjs`, `.cjs`, `.mts` and `.cts` |

**Re-check edits (president's re-check of head 2cd08564):**

| Item | Applied in |
| --- | --- |
| R-1(i): own reason beats script-goal reasons | §7.2 "Precedence (R-1(i))"; §7.6 "Precedence when two reasons apply", item 1. js-require, js-cjs-local, js-var-fn, js-block-fn and js-eval-with keep PR 2 (§10.4). |
| R-1(ii): `script-dir-shadow` before `module-not-found` | §9.5 script-directory rule; §7.6 precedence item 3; §10.2 probe one-root row (now `script-dir-shadow`); §10.6 reason rows |
| R-1(iii): `ambient` wins over `bodyless` | §7.4 no-body row; §7.6 precedence item 2 |
| R-2: a proof not in C0 is never resolved, though filters may still narrow | §6.3; §12 |
| R-3: named generated tests | §10.6 "Generated coverage …" tables; §5.4 |
| RC-43 issue numbers | §6.3 and §12 (treesitter-chunker#685); §14; §15 Q1 (treesitter-chunker#684) and Q8 (treesitter-chunker#685). No placeholder remains. |
| N-1: exported-declaration join (PR 2 panel note) | §13.1 PR 2 row; §5.4 |
| N-2: rt-tsclass cited correctly | §8 table (rt-tsclass is a control with no `K.m` calls) |

### Codex review of treesitter-chunker#683 at d486c029 (executive fold)

| Finding | Applied in |
| --- | --- |
| `nonlocal` writes rebind the enclosing function's binding | §7.3 "`nonlocal` writes"; §10.4 py-nonlocal-rebind (near-miss plus an f → f.helper positive); §10.6 mixed-bindings row |
| Dotted Python module paths resolve one component at a time | §9.5 "Dotted names resolve one component at a time"; §10.4 py-ancestor-module-shadow; §10.6 module-not-found row |

Both tighten the rules (fail closed); neither departs from a ruling. Today cells for both fixtures were derived on main f213f1c2.

### PR 2: treesitter-chunker#688 panel item B7

| Item | Applied in |
| --- | --- |
| B7: `declare enum E {}` then `E()` | §7.4 (settled: `non-callable`, non-callable kinds dropped first); §7.6 precedence item 2; §10.6 non-callable row |

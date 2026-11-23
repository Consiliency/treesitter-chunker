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
| Extension collisions | When a relative import matches more than one file variant, the result is `none` (ruling 2.2). **O-1 decided (a) by the owner** (PR 5): the edge is left unchanged. |
| Test-file scoping | **O-2 decided "scope by caller" by the owner** (PR 5 fold 2): Tier 2 causes and taints that originate in test files apply only to edges whose caller is a test file; production causes stay run-wide. A test file any production file reaches is production (9.9). |
| Python Tier 2 outcome | **O-3 decided by the owner: ship PR 6 as designed** (fold 1 on #705). On the measured real trees Python `imports` resolves no additional calls (each tree has genuine production run-wide causes), and it resolves fewer calls than `structural` where other files may write a module (#697 taints). Both are documented outcomes (9.10). |
| Experimental label | **O-4 decided by the owner: keep it** on `structural` and `imports` after PR 6, because real-code precision has not been measured (4.5, 13.1). |
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
(Unreleased) from PR 1, and **stays experimental after PR 6** for both
`structural` and `imports` (owner decision O-4: real-code precision has not
been measured). Each PR's CHANGELOG entry states exactly
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
- a tree with errors;
- a JS/TS file that spells any name with a Unicode escape (`\u0074`,
  `\u{74}`), in an identifier, property, private, label or type name
  (PR 2, Codex review of treesitter-chunker#689). Names are compared by
  their source spelling, so an escaped parameter, write or `eval` would
  otherwise be missed. Backslashes in strings, templates, regexes, comments
  and JSX text do not count;
- a JS/TS file with an expression statement whose first token is `{`
  (PR 3, #691 panel A1 and the president's B-1). Valid JavaScript never has
  one, but tree-sitter parses `{ L: function d() {} }` as an object literal
  without an error, alone or glued to what follows (`[0]`, `(0)`, `+0`, a
  template, a regex), which would hide a block-level declaration;
- a Python file with a non-ASCII identifier, or any non-ASCII character
  outside string literals and comments (PR 4). Python compares identifiers
  after NFKC normalization (`ﬁle` is `file`, `ｈelper` is `helper`), while
  the analysis and the chunker's symbol names use the source spelling, so a
  normalized write or parameter would otherwise be missed. ASCII names are
  NFKC-invariant;
- a Python file in which any line's leading whitespace has a space before a
  tab, or a form feed (#695 panel A4). tree-sitter counts a tab as eight
  more columns, while CPython advances to the next multiple of eight, so
  "seven spaces and a tab" can move a `def` into a different block without a
  parse error. Likewise a line whose first non-blank character is a
  backslash continuation (the president's #695 ruling, B-2): CPython takes
  the logical line's indentation from that line, tree-sitter from the next.
  The ruling's generator of 50,625 nested-`def` sources finds 73 silent
  nesting mismatches past the tab rule alone and none with this rule
  (`test_whitespace_differential_has_no_silent_misparse`).

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
  - **TS enum body** (`enum_body`; PR 2, the president's treesitter-chunker#689
    ruling, B-1). Inside it the member names of every declaration of that
    enum are in scope for the initializers and shadow outer bindings: tsc
    emits `E.t()` for `enum E { t = 1, B = (t as any)() }`, also across merged
    declarations. Merged declarations, possibly in other files, make that
    member set non-local, so Tier 1 fails closed for every bare-name lookup
    that reaches an enum body, member or not: `none(enum-scope)`. A binding
    found before the body (a parameter of an arrow in an initializer, say)
    still decides. Lookups outside the enum are unaffected;
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
  read too. **Mapped `arguments` (PR 3).** In a non-arrow function that
  mentions `arguments` anywhere, a body binding that shares a parameter's
  name is reassigned: `arguments[0] = x` writes that binding.
- **Fail closed** with `none(dynamic-scope)` when the lookup chain meets a
  scope that contains a direct `eval(...)`, or a `with` lies on the lookup
  chain. A direct eval can
  assign any binding visible from its site, so every scope from the eval out
  to `program` is dynamic. Parenthesized and TS-wrapped callees (`(eval)(s)`,
  `eval!(s)`, `(eval as any)(s)`) are direct eval. Also fail closed with
  `none(unmapped)` on an unclassified declaration node (7.5).
- **Script goal and `script_globals`:**
  - `script_globals` holds the `var`, `let`, `const`, `class` and `function`
    top-level names of every script-goal JS/TS file.
  - It also holds any assignment, in any JS/TS file, to an identifier with no
    declaration on its scope chain in that file (an implicit global), not only
    top-level ones. In a module (strict code) such a write reassigns a global
    another script declared (PR 3, #691 panel A2).
  - `window.x =`, `globalThis.x =` and `self.x =` count as declarations of `x`
    in a file of either goal.
  - **Fail closed (PR 3).** So do `global.x =`, `top.x =`, `parent.x =`,
    `frames.x =`, `<any>.defaultView.x =`, alias chains (`window.top.x =`),
    string-literal keys (`globalThis["x"] =`), and every write form
    (compound, update, pattern, `for … of` target, `delete`). An alias counts
    when nothing binds it, or only a script's top level does (`var self;`
    there is the global object's own property).
  - **`this.x =`** counts in a file of either goal wherever `this` comes
    from a non-arrow function or method, because a host may pass the global
    object as the receiver even to strict code (`setTimeout(K.prototype.m)`,
    `window.m()`; #691 panel A4). Excluded: class constructors, field
    initializers, static blocks and a module top level (`static
    constructor()` is an ordinary method and counts). Alias chains count
    from a receiver `this` too (`this.window.x =`), as do `this.eval(…)`,
    `this.setTimeout(…)` and `Object.assign(this, …)`. `super` counts like
    `this` (`super.x = v` sets `x` on the receiver), and a computed link in
    such a chain (`this[k].x =`) may name the global object, so `x` is
    recorded; a computed final key still gives `*`. A literal subscript
    key writes that key; a non-literal key gives `*`. At a script top level,
    in sloppy functions and in object-literal methods, `this` used as a value
    gives `*` too.
  - A write the analysis cannot read gives the wildcard `*`, which declares
    every name: a non-literal key; the global object used as a value
    (`f(window)`, `const g = globalThis`, `window[k]()`, `{ window }`,
    `const w = document.defaultView`); any reference to `eval`, `Function`
    or `execScript`; a called, `new`-ed or handed-on `x.constructor` (which
    reaches the function constructors), or its `.call`/`.apply`/`.bind`,
    or a `{ constructor: F }` pattern;
    and `setTimeout`/`setInterval` used other than as a direct callee (an
    alias, `.call`, `Reflect.apply`) or called with a first argument that is
    not certainly a function (a function or arrow expression, or a name the
    file proves to be a local function that is not a script top level).
    An **unsupported** JS/TS file in the run counts as `*`, because its
    globals are unknown, and so does every in-run file of a language that
    can carry inline scripts (HTML, XML, PHP; #691 panel B5). Markdown and
    reStructuredText do not count: they run nothing themselves (the
    president's #691 ruling, 3.1).
  - **Literal keys equal dot access** for every name the analysis recognizes
    (property writers, evaluators, `constructor`, timers and their
    invokers, global-object names, `defaultView`): `X['name']` and
    ``X[`name`]`` without substitutions match exactly like `X.name`, and a
    string or template key with an escape fails closed (Codex 4652498471 on
    #691). Property writers are `Object`/`Reflect` members reached by name,
    through the global object (`globalThis.Object.assign`) or a receiver
    `this` (`this.Object.assign`; C-1), through a comma callee
    (`(0, Object.assign)(…)`), or through `.call`/`.apply`/`.bind`; a
    computed or escaped key on `Object` or `Reflect` counts as one.
    Commas, and parentheses with no comment inside them, are looked
    through at every level, on the writer, its namespace and its target
    (`(0, Object.assign).call(null, this, …)`, `(0, Object).assign(this,
    …)`, `Object.assign((0, this), …)`); invokers nest on the writer
    (`Object.assign.call.call(…)`; an invoker's own receiver argument is
    not read as the writer), a bound writer called later counts
    (`Object.assign.bind(null)(this, …)`), and so do
    `Reflect.apply(Object.assign, null, [this, …])` and a computed key on
    `Reflect` read as `apply` (treesitter-chunker#694). A call also gives
    `*` whenever the positional reading of js fact version 20 does (the
    target read from the raw argument list, comments included), so the
    comment-aware reading only adds `*` (the #717 review).
  - In a script, a global-object write of `x` (or `*`) also makes that
    file's top-level binding of `x` (or of every name) `reassigned`.
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
    `dist/`, `node_modules`, `.mjs`/`.cjs` files and inline `<script>` in
    `.vue` and `.svelte` files (not collected), and scripts loaded by other
    means. Strict code given the global object as `this` through a call the
    analysis cannot see, open-ended global-object references and string-code
    paths no syntactic rule closes are risk R11. Resolution therefore holds
    within the run only.
- **CommonJS files stay script goal** (R2). That is conservative: the
  script-global check only adds `none`, and hoisting works the same inside the
  CommonJS wrapper.
- **TS namespaces.** A lookup through a namespace body gives
  `none(namespace-merged)` when the namespace has more than one declaration in
  the run, or lives in a script-goal file. In a module, other declarations of
  the namespace are counted in its declaring scope (PR 3), and an enum
  declaration of the same name counts too. A module-level namespace the
  module exports (an `export` modifier, an `export { … }` clause including
  `as` aliases, or `export =`) is always merged, because TS module
  augmentation (`declare module './a' { namespace N { … } }`) merges into it
  from another file (#691 panel A3); `export default N` and a namespace the
  module does not export cannot be augmented. A dotted namespace
  (`namespace A.B`, whose body also sees the members of every `A` and `A.B`),
  `declare module 'm'` and `declare global` bodies are always treated as
  merged; for those two ambient bodies the rule is defensive, since they hold
  no calls. A lookup that ends unbound inside a merged body also gives
  `namespace-merged`: another declaration may bind the name. An exported
  `const` in a namespace body is `expression-bound`, because tsc rewrites its
  uses to properties of the namespace object.
- **Ambient status** is inherited from enclosing `declare` blocks
  (`declare namespace`, `declare module`, `declare global`). A binding made only
  of ambient declarations gives `none(ambient)`. Every declaration under
  `declare`, at any depth, is ambient (PR 3), and as a binding's own reason
  `ambient` wins over `namespace-merged`.

### 7.3 `t1.lexical`, Python scope chain

- **Scopes:** `module`, `function_definition`, `lambda`, `class_definition`, and
  comprehensions. A comprehension's first iterable is evaluated in the
  enclosing scope.
- **Annotations prove nothing (#695 re-check at 14e8f044, Q-2).** A name
  looked up inside any annotation gives `none(dynamic-scope)`: a parameter
  annotation (`typed_parameter`, `typed_default_parameter`), a return
  annotation, or a variable annotation at module, class or function level
  (the `type` of an annotated assignment). On 3.14 annotations are evaluated
  lazily (PEP 649/749), and `annotationlib` runs an annotation scope again
  under substitute globals for the `FORWARDREF` and `STRING` formats. Ordinary
  callers use those formats: `@dataclass`, `typing.get_type_hints`,
  `inspect.signature`, `functools.singledispatch` `.register` and `pydoc`. A
  call there may then reach a stand-in (`annotationlib._Stringifier`), not
  the binding the lookup would prove. A function-local variable annotation
  is never evaluated, so failing closed there costs nothing.
  **The value of a `type` statement** proves nothing either, at any level
  (#695 re-check at a6734480, S-2). It is evaluated lazily too (PEP 695), and
  in a class body it reads the live class namespace through `__classdict__`.
  So a write to the class after the class statement rebinds what it calls,
  and the attribute-write rule sees only a literal attribute name at the
  write site, not `setattr(K, *('helper', len))`, a same-file
  `put(K, 'helper', len)`, a `dict(helper=len)` key or a descriptor's
  `__set_name__`. A module-level `type` value has no caller symbol, so it
  gives no edge in the first place.
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
  - **Open class namespaces (#695 panel A1, B4; Codex 4653329444).** When the
    class statement has any base or any keyword argument, every lookup from
    class-body-evaluated code (the code listed above, the first comprehension
    iterable, and class annotation and type-parameter scopes) gives
    `none(class-scope-bound)`: a metaclass's `__prepare__`, inherited through
    a base possibly defined in another file, or a `__missing__` namespace may
    supply any name. No committed fixture class has bases.
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
  so resolving it is harmless, **unless the name is a builtin** (#695 panel
  A3): then the call reaches the builtin until the definition runs. A
  module-scope definition or import whose name is a builtin (CPython 3.14's
  `dir(builtins)`, pinned by a test, plus the Python 2 builtins) never
  proves: `none(builtin-shadow)`.
- **Fail-closed refinements (PR 4).** Each only adds `none`; no expected row
  changes.
  - **Decorated definitions.** A decorator can replace the function, so a
    decorated `def` or `class` binds the decorator's result: a single one is
    `none(expression-bound)`. It still joins a redefinition group, which never
    resolves (py-overload stays "group = C0").
  - **Every write form binds**, read fail-closed: every identifier under an
    assignment, augmented or annotated target, `for`/`with`/`except`/
    comprehension target or `del`, through tuples, lists, starred targets and
    parentheses, except the object of an attribute or subscript. Any other
    target form poisons the scope (`unmapped`). Every identifier in a `case`
    pattern binds except a dotted value pattern, a class pattern's class and
    a keyword pattern's keyword. `from __future__ import x` binds `x`.
  - **Python 2 forms the grammar accepts.** `except E, e:` binds `e`, a list
    comprehension's targets also bind in the enclosing scope (Python 2 leaked
    them), and the `exec` statement is dynamic.
  - **Dynamic binding.** `dynamic-scope` applies to module-scope lookups, and
    to class-body lookups (a class namespace is a dict that `exec` and
    `locals()` can write), in a file that mentions
    `exec`, `eval`, `globals`, `vars`, `locals`, `__import__`,
    `__builtins__`, `builtins`, `importlib` or `execfile` outside an
    attribute name, a keyword-argument name or a `def`/`class` name (so
    `import builtins as b` and `from importlib import import_module` count);
    that writes or reads `sys.modules` or a dunder attribute of `sys`, with
    `sys` reached by name, by an `as` alias or as `os.sys`; that hands the
    `sys` module on as a value (`getattr(sys, "modules")`); that imports
    `modules` from `sys`; or that touches `__globals__`, `f_globals`,
    `f_locals`, `f_builtins` or `inspect.getmodule`, or reaches the
    builtins namespace as an attribute (`f.__builtins__`,
    `os.__builtins__`, or `len.__self__`, which is the `builtins` module;
    #695 re-check at 606c689f), or reaches the `builtins` module as another
    module's attribute (`inspect.builtins`, `site.builtins`, and
    `enum.bltns`, the one other name the stdlib binds it to) or in a
    constant string (`mock.patch('builtins.helper', len, create=True)`,
    `pydoc.locate('builtins')`; #695 re-check at 8fd7c1a2). The #695 panel fold
    adds: `__main__` or an alias of it used other than in an import (A5),
    any name a `from __main__` import binds, any import of `sys` or
    `__main__` in a class body (#695 J-3/J-4), and a constant string with a
    `__main__` component (`mock.patch('__main__.helper')`,
    `pydoc.locate('__main__')`), except on a **positive allow-list** (#695
    K-3, then L-2 and M-2; executive decision after three rounds of escapes
    through a deny-list exemption). A `'__main__'` constant is exempt only
    when all of these hold:
    1. it is exactly `'__main__'`, a plain string, and an operand of the
       test of an `if` or `elif` statement at module top level (not nested in
       a function, class, lambda, comprehension or `match`, and not a default
       or decorator);
    2. the test is exactly one comparison, `__name__ == '__main__'`,
       `'__main__' == __name__` or the same with `!=`, with parentheses
       allowed around the whole test or either operand (no chains, `in`,
       tuples, `and`/`or`/`not`);
    3. `__name__` is the bare identifier and the file never rebinds it
       (`global`/`nonlocal`, parameters, imports, targets, walrus, `del`,
       `match` captures, or an attribute write `x.__name__ = v`).

    At module top level `__name__` is read from module globals, which only the
    rebinding forms above, the existing dynamic triggers (`globals()`,
    `sys.modules`, frames, `vars`) and R12 can replace. The comparison is
    between a module-global `str` and a literal, so no user `__eq__` runs and
    no class namespace or `__prepare__` is involved. Everything else with a
    `__main__` component fails closed, including guards in functions or
    methods, `in` forms and every `match __name__` form. `__mp_main__`, the name a multiprocessing spawn
    child imports the script under, counts as `__main__`. Constant strings
    split on `.` and `:` (the `pkgutil.resolve_name('pkg.mod:attr')` form)
    for this rule, the own-name rule and the dynamic attribute names; no
    resolver maps `/` to this module's namespace. Also a
    constant string (a literal, adjacent literals or literals joined by `+`)
    that is one of those attribute names or `modules`, alone or as a part of
    a dotted path (`getattr(f, '__globals__')`, `attrgetter('sys.modules')`;
    A6, B2); an import of the file's own module (`import a`, `import pkg.a as
    m` or `from . import a` in `a.py`; the package name for `__init__.py`;
    A7); and `X.modules[__name__]`, `X.modules.get(__name__)` (also
    `__getitem__`, `setdefault`, `pop`) through any receiver `X` (B3).
    Precedence: `dynamic-scope`, then `star-import`, then `unmapped`.
  - **The file's own module: one general rule (the president's re-check of
    #695, N-1 to N-3).** It replaces the per-shape self-import and
    submodule fixes.
    - **Which names can denote the module.** The names the import system
      derives from the path can denote this file's module: every suffix of
      its dotted module path, relative to the run root and to every ancestor
      directory, because the root and any ancestor may be packages, regular
      or PEP 420 namespace packages. Each of those, and any longer path
      ending in one, ends with the file's own name: its raw stem, or the
      package directory's raw name for `__init__.py`, with no identifier
      filter (`my-mod` is importable; re-check N-5). A loader may choose any
      other name (`spec_from_file_location`, `runpy`): writes through such a
      module in the spellings the attribute-write rule lists fail closed, and
      every other spelling is R12. A file whose own name cannot be computed
      (no path: `None` or `""`) fails closed.
    - **Self-reference.** Module-scope lookups give `dynamic-scope` when the
      own name is a component of any of these:
      - any import's path or imported names, absolute or relative, in any
        scope;
      - any identifier that is not a parameter or `def`/`class` name, whatever
        node spells it: an attribute (`R.a.helper = …` through a parent package
        or the run root), a keyword argument, a class pattern's keyword
        (`case object(a=m)`, re-check N-4), a dotted name;
      - any constant string, alone or dotted: `getattr(pkg, 'a')`,
        `pkg.__dict__['a']`, `NAME = 'a'`.

      A root-level `__init__.py`, which includes any `__init__.py` run as a
      single file, has no own name in the run. Every absolute import, and
      every relative import whose dots leave the run (`from .. import R`;
      re-check N-6), may name it; only a single-dot relative import cannot.
      The level is the number of `.` tokens, wherever whitespace or a
      backslash continuation separates them (re-check N-7). The rule
      over-triggers by design: losing a proof is acceptable, a wrong edge is
      not. The remaining ways to reach the module
      object without spelling its name are either dynamic triggers already
      (`__import__`, `importlib`, `sys.modules`, `globals()`, frames) or R10
      and R12 (another module, iterating a package's namespace, `gc`).
    - **Attribute writes through any receiver (re-check R-5 family).** The
      receiver may be this module, handed over by a sibling's re-export, a
      function's return value, a parameter or a loader. Writing attribute
      `name` of anything gives `name` a non-definition binding at module
      scope. That covers `x.name = v`, `del x.name`, `x['name'] = v` with a
      constant key, `setattr`/`delattr`/`__setattr__`/`__setitem__` with a
      constant string, and `x.__dict__.update(name=v)`, `.update({'name':
      v})`, `.setdefault`, `.pop`, `.__ior__`, the constants of a literal
      `*` splat (`setattr(mod, *('helper', f))`), `x |= {'name': v}`, and
      `operator.setitem(x, 'name', v)` (also `delitem`, `__setitem__`,
      `__delitem__`, `ior` and `iadd`, and names imported from `operator`)
      on any receiver.
    - **Writers handed on and namespace writes (#695 fold 18, executive
      ruling).** These use only spelled names and ordinary binding and call
      semantics, so they fail closed (module-scope `dynamic-scope`; a
      namespace write cannot reach a function's locals or closure cells, so
      function-scope proofs stand):
      - **a writer anywhere but as the callee of a direct call**: `setattr`,
        `delattr`, `__setattr__`, `__delattr__` (so `object.__setattr__`),
        as an assignment or walrus value, an argument (`partial(setattr,
        mod)`, `map(setattr, …)`), a container element, a conditional
        branch, a default value or a return value, or as a constant string
        (`getattr(mod, '__setattr__')`). Definition names (`def
        __setattr__`), parameter names, keyword-argument names and imports
        do not count;
      - **a namespace receiver** is `x.__dict__`, `vars(x)`, a call with a
        `'__dict__'` constant argument (`getattr(x, '__dict__')`), any of
        these in parentheses, or a name assigned one of them anywhere in the
        file (`d = mod.__dict__`, flow-insensitive, transitive). Taking a
        mutator off one without calling it fails closed (`u =
        mod.__dict__.update`; `update`, `setdefault`, `pop`, `popitem`,
        `clear`, `__setitem__`, `__delitem__`, `__ior__`); so does a write
        through one whose names are not all constants (`mod.__dict__.update(D)`,
        `.setdefault(k, f)`, `mod.__dict__[k] = f`, `mod.__dict__ |= D`,
        `operator.setitem(mod.__dict__, k, f)`);
      - **an `operator` writer handed on** (`partial(operator.setitem,
        mod.__dict__)`, or as a constant string) fails closed in a file that
        names a namespace dict (a `__dict__` attribute or constant string,
        or a namespace alias). The bound keeps `functools.reduce(operator.ior,
        sets)` and the like resolving elsewhere.
      Plain `.update`, `.pop` and `.setdefault` aliases and computed
      subscript writes on receivers that are not namespace dicts are
      unchanged.
    - **Computed writes are closed at the write site (#695 fold 19,
      executive ruling E-19, narrowed by E-20).** The guarantee is that
      **every write spelled in this file is recorded or fails closed**;
      writes performed inside a library function on an object handed to it
      are R12 (E-20). Whatever route obtained the module or its namespace, a
      write spelled here needs a name, and these fail closed (module-scope
      `dynamic-scope`):
      - **W-1:** a writer (`setattr`, `delattr`, `__setattr__`,
        `__delattr__`, in every fold-17/18 spelling) whose name argument is
        not a constant string, on **any** receiver, including a `*` splat of
        anything but a literal sequence (`setattr(mod, n, f)`,
        `setattr(mod, *t)`, `setattr(*t)`). The name is the second argument
        of `setattr`/`delattr` and of an unbound `X.__setattr__(obj, n, v)`,
        the first of a bound `obj.__setattr__(n, v)`;
      - **W-2:** a namespace receiver that escapes: a call argument (other
        than the receiver of an unbound namespace mutator or `operator`
        writer, which the write rules read), a container element, a return
        or yield value, a parameter default, a lambda body, a `with` item, a
        `for` or comprehension iterable, or an attribute or subscript
        target (`ChainMap(ns)`, `nullcontext(ns)`, `[ns][0]`, `for d in
        [ns]`, `put(mod.__dict__, n, f)`, `K.ns = mod.__dict__`);
      - **W-3:** `unittest.mock` (or `mock`) `patch`, `patch.dict` with a
        target that is not a constant string, and `patch.object` with an
        attribute name that is not one, through `mock.patch`,
        `unittest.mock.patch`, `from unittest.mock import patch` (and
        aliases) and decorators; `patch` handed on fails closed too. A
        constant `patch.object` attribute and the `patch.multiple` keywords
        are attribute writes; a constant `patch('a.helper')` keeps the
        own-name rule. Fold 20 adds receiver-based patchers with the same
        rules: any `X.patch.object`, `X.patch.dict` or `X.patch.multiple`
        chain, whatever `X` is, and `.patch` on a pytest-mock fixture
        (`mocker`, `module_mocker`, `class_mocker`, `package_mocker`,
        `session_mocker`), called or handed on; a plain `.patch(url)` on any
        other receiver (an HTTP client) is untouched. Fold 21 (B-5) tracks
        mock-module and pytest-mock aliases through assignment, walrus,
        tuple targets, class bodies and `self.X = …` (`mk = mock`,
        `K.mk`, `mm = mocker`, `self.mocker = mocker`); a mock-module name
        used anywhere but as an attribute receiver, a direct callee or an
        alias value fails closed (`getattr(mock, 'patch')`,
        `attrgetter('patch')(mock)`), and so does a constant `'patch'` in a
        file that imports the mock module (`mock.__dict__['patch']`).
      - **Acquisition triggers (fold 21, E-20).** A mention in any position
        of a stdlib string-to-module resolver fails closed, like `importlib`:
        `resolve_name` (`pkgutil`), `safeimport` and `find_class` in every
        spelling, `locate` on a `pydoc` binding or imported from `pydoc`,
        `_resolve`/`_importer` on `logging.config` or imported from it, and
        a constant string naming `resolve_name`, `safeimport` or
        `find_class`. So do a constant `'__dict__'` subscript key
        (`types.ModuleType.__dict__['__dict__'].__get__(m)`) and
        `X._sys.modules` (another module's private `sys`).
      The namespace rules also cover (B-2): unbound mutators whose first
      argument is a namespace receiver (`dict.update(ns, D)`,
      `dict.__ior__(ns, D)`, `type(ns).update(ns, D)`, and `setdefault`,
      `pop`, `clear`, `__setitem__`, `__delitem__`), `operator.__ior__` and
      `__iadd__`, a mutator taken by constant name (`getattr(ns, 'update')`,
      `attrgetter` through `__dict__`, `methodcaller('<mutator>', …)`), and
      namespace aliases through tuple and starred targets, a walrus,
      conditional and boolean operands (`ns if c else {}`, `ns or {}`) and
      `match ns: case d` captures, and (fold 21, B-4) a namespace alias
      read back as an attribute or by constant name: a module-level `NS` as
      `m.NS`, a class-body `ns` as `K.ns` or `self.ns`, a `global NS`, and
      `getattr(K, 'ns')`. Constant strings are read through
      comments in implicit concatenations and parentheses, and an f-string
      whose interpolations are all constant strings is a constant (B-1,
      W-4: `getattr(helper, '__glo'  # c\n 'bals__')`, `f"__glo{'bals'}__"`).
    - **One alias/readback/escape mechanism for every sensitive kind (#695
      fold 22).** The sensitive kinds are a namespace dict, the mock module
      (an import, an alias, `X.mock` for any `X`, `getattr(X, 'mock')`),
      `patch` (an import, or `.patch` on the mock module or a fixture) and a
      pytest-mock fixture (`mocker`, `module_mocker`, `class_mocker`,
      `package_mocker`, `session_mocker`). For all four alike:
      - **alias binding:** assignment, tuple/list/starred targets, walrus,
        conditional and boolean operands, a `for` target, `with … as`, a
        `match` capture, a class-body binding, `self.X = …`,
        `global`/`nonlocal`, and `setattr(T, 'name', v)` with a constant
        name make an alias of the kind the value carries (a value carries
        a kind as itself or as an element of a tuple, list or set; a call,
        attribute read or subscript of it does not, so
        `ns.get('p')` and `C.__dict__.get('p')` are values, not the
        namespace). **Every import of the mock module or `patch` is an
        alias too** (fold 24, Y-5), in any spelling and at any scope:
        `import mock`, `import mock as mk`, `from unittest import mock
        [as mk]`, `import unittest.mock as um`, `from unittest.mock import
        patch [as P]`, `from mock import patch [as P]`; so `m.mk`,
        `getattr(m, 'um')`, `m.__dict__['P']`, `m.__dict__.get('P')`,
        `K.mk` and `case object(um=x)` carry the kind. Beside the
        canonical `from unittest.mock import patch`, any `X.patch` is
        spelled like the readback `m.patch`, so a computed target fails
        closed whatever `X` is (0 stdlib and repository test files);
      - **readback:** a name, an `X.<alias>` attribute, any call with a
        constant argument naming an alias (`getattr(K, 'ns')`,
        `type.__getattribute__(K, 'ns')`, `attrgetter('ns')(K)`) and a
        subscript with such a constant key (`K.__dict__['ns']`) read the
        kind back;
      - **use:** since fold 23 the uses of a sensitive value are THE CLOSED
        ALLOW-LIST below; the fold-22 escape deny-list is gone.
      A constant `'mock'` string, like `'patch'`, fails closed in a file
      that imports the mock module.
    - **THE RULE for sensitive values: a closed allow-list (#695 fold 23,
      executive ruling E-21).** A value of a sensitive kind (followed
      through parentheses, walrus values and conditional or boolean
      operands) may appear only in these uses; **every other use fails
      closed** (module-scope `dynamic-scope`): any other attribute,
      including every dunder (`__call__`, `__get__`, `__ior__`,
      `__class__`, `__or__`), any other method (`copy`, `fromkeys`), any
      other call or argument position, a container, a return, a `match`
      subject, a bare expression statement. The tables live in one place
      in `py_scope.py` (`_NS_READS`, `_NS_WRITES`, `_MOCK_SAFE`,
      `_MOCKER_SAFE`, `_PATCH_SAFE`, read by `_safe_use`):
      - **every kind:** a binding position (parameter, target, import,
        pattern capture; an import's name is itself an alias, so each of
        its readbacks is checked in turn, fold 24), and an alias binding:
        the value assigned or walrus-bound to one name a computed read
        cannot reach (a function local);
      - **namespace dict, pure reads** whose result cannot reach the
        namespace: `ns[c]` with constant keys and `ns.get(c, …)` (a key
        naming an alias is a readback; a `'__builtins__'` string is a
        dynamic-attribute literal and a `'__dict__'` subscript key is an
        acquisition trigger, both failing closed), `c in ns`,
        `c not in ns`, `len(ns)`. **THE RULE for results** (fold 27, Codex
        4657978945): an A-1 read may treat its result as ordinary only
        when that result cannot reach the namespace at run time. An int
        (`len`) or a bool (`in`, `not in`) cannot; a stored value by
        constant key can reach it only through a spelled acquisition the
        other rules track (`__globals__`, `__dict__`, an alias, a module
        whose writes are recorded on any receiver); `'__loader__'` and
        `'__spec__'` hold no namespace (a module they load is such an
        ordinary module). A view, iterator or proxy of the namespace is
        not ordinary: **`ns.values()` and `ns.items()`** (fold 24, Y-6)
        and **`ns.keys()`** (fold 27: a keys view's `.mapping` is a proxy
        of the namespace itself) are off the list, in any file. Option (i),
        removing `keys`, cost 0 of 638 stdlib and 0 of 488 repository test
        files, the same as option (ii), treating its result as the
        namespace kind. The fold-23 `c not in ns` entry never matched (the
        grammar reads `not in` as one token); fold 27 fixes it;
      - **namespace dict, recognized writes**, as expression statements
        only, with constant keys or literal mappings recorded and anything
        else failing closed in the write rules: `ns[c] = v`, `del ns[c]`,
        `ns.update(…)`, `ns.setdefault(c, …)`, `ns.pop(c, …)`, `ns |= …`,
        and the unbound `dict.`/`operator` writers with `ns` first
        (`dict.update(ns, …)`, `operator.setitem(ns, c, v)`,
        `from operator import setitem`);
      - **mock module:** `mock.Mock`, `MagicMock`, `AsyncMock`,
        `NonCallableMock`, `PropertyMock`, `call`, `ANY`, `sentinel`,
        `DEFAULT`, `create_autospec`, `mock_open`, `seal`, and
        `mock.patch`;
      - **pytest-mock fixture:** `mocker.spy`, `stub`, `Mock`, `MagicMock`,
        `resetall`, `stopall`, and `mocker.patch`;
      - **`patch`:** called (`patch(…)`, `@patch(…)`), or
        `patch.object`/`patch.dict`/`patch.multiple` called, with W-3
        semantics.
      A class-pattern keyword reads an attribute of the subject, so a
      keyword naming `__dict__`, `mock`, `patch` or an alias fails closed
      whatever the subject (`case object(__dict__=x)`). **Allow-listed
      callees are verified by binding** (fold 25, Codex 4657695001): an
      entry that hands a sensitive value to a callee named by spelling is
      safe only if the name is that object. `len` and `dict` must be the
      builtins: bound nowhere in the file (no `def`, `class`, assignment,
      import, parameter, `global`/`nonlocal`, `for`/`with`/`except`
      target, comprehension variable, pattern capture, type parameter or
      `del`, read from the scope pass's binding record) and never written
      into a namespace by a recorded write (`m.len = f`,
      `ns['dict'] = C`). `operator` and its writers must come from
      `import operator [as op]` or `from operator import <writer> [as s]`,
      every binding of the name being such an import. **Allow-listed
      callees are verified by the ordinary lookup at the use site** (fold
      28, Codex 4658232413): once the scopes are complete, the name is
      looked up from the use exactly as an ordinary edge would be, and a
      builtin must give `none(unbound)` (unbound on the path), a stdlib
      name its tracked import binding. Every reason the lookup fails
      closed therefore fails the verification too: an open class
      namespace on the path (a base or keyword, so `__prepare__` or
      `__missing__` may supply the name: `class K(metaclass=M): len(ns)`)
      or a binding in the class (`class-scope-bound`), an annotation or a
      dynamic file (`dynamic-scope`), a mangled name (`unmapped`), a star
      import, a conditional or doubled import (`conditional`,
      `mixed-bindings`), a recorded write (`local-variable`) and a module
      definition (`builtin-shadow`). A method or comprehension body inside
      such a class skips the class namespace, as Python does, and still
      resolves. The binding-event check above stays as the stricter belt
      (it also refuses bindings in scopes the lookup never consults); for
      builtin names the recorded-write check is now redundant with the
      lookup, and for writer members it is still needed. **A writer relied on
      through a module attribute or a from-import is relied on by its
      member name too** (fold 26, AA-4): `operator.setitem(ns, …)` and
      `from operator import setitem as s` rely on the module's `setitem`,
      so a recorded write of `setitem` anywhere in the file
      (`operator.__dict__.update(setitem=f)`, through an alias, `getattr`,
      `dict.update` or a handed-in module) fails closed; writes of other
      names do not. `operator` is the only verified stdlib module an
      entry reads a member of: builtin `dict` methods cannot be
      reassigned (an immutable type), and the mock module and `patch`
      are sensitive kinds whose `__dict__` is off the list. Otherwise the use
      is off the list and fails closed (A-2): so a same-file
      `def len(d): d.update(…)`, a class `U.update(ns, …)`, a bare
      `setitem(ns, …)` with no import, and `dict = client` all fail
      closed. `type(ns).update(ns, …)` already fails closed (the inner
      `type(ns)` is an argument). Producers and writers named by spelling
      (`vars(x)`, `getattr(x, '__dict__')`, `setattr`, the mock module,
      `patch`) only over-recognize when shadowed, which fails closed; the
      module object a shadowed `setattr` receives is no sensitive kind,
      since its writes in a same-file body are recorded or fail closed on
      any receiver, and in a library they are R12 (#699). `c in ns` is
      syntax, so it calls the real dict. Cost: 0 of 638 stdlib and 0 of
      488 repository test files change. A binding a
      computed read can reach (module or class scope, `global`, an
      attribute or subscript target) still fails closed (fold 22). Cost
      against fold 22: 0 of 595 stdlib files and 0 of 359 repository test
      files change. Cost of fold 24 against fold 23, over all 638
      supported non-test stdlib files and all 488 supported repository
      test files: Y-5 changes none; Y-6 changes one stdlib file
      (`multiprocessing/process.py`, `list(signal.__dict__.items())`: 6
      of its 29 identifier-callee calls no longer resolve) and no test
      file.
    - **Callees and receivers are classified after unwrapping parentheses
      (Codex 4656123247).** Parentheses are only a spelling: the rules above
      and the `X.modules.get(__name__)` getters look through any number of
      them, and through a comment inside them, around a callee, an
      attribute callee or an argument. So `(setattr)(mod, 'helper', f)`,
      `((setattr))(…)`, `(mod.__setattr__)('helper', f)`,
      `(object.__setattr__)(…)`, `(mod.__dict__.update)({'helper': f})`,
      `.update(({'helper': f}))`, `.update(**({'helper': f}))` and
      `(x.modules.get)(__name__)` count. A trailing-comma tuple, `(setattr,)`,
      is not a parenthesized callee. Identifier-based triggers (`exec`,
      `globals`, `vars`, `sys`, the dynamic attributes and the file-wide
      names) match any position already, so `(globals)()['x'] = v` and
      `(sys).modules[__name__]` were never affected. An alias of a writer
      (`w = setattr`, `(w := setattr)`, `functools.partial(setattr, mod)`,
      `u = mod.__dict__.update`) fails closed since fold 18 (above).
    - **Names come from tokens (re-check N-7).** Every import name, dotted
      path and relative level is read from identifier and `.` tokens, never
      from raw node text, because whitespace, comments and backslash
      continuations may sit between them (`from . helper import M`, `from .
      . import R`).
    - **Name triggers whatever node spells them (re-check N-4).** The dynamic
      attribute names (`__globals__`, `f_globals`, `f_locals`, `f_builtins`,
      `getmodule`) count in any identifier position, and `X[__name__]` or
      `X.get(__name__)` (also `__getitem__`, `setdefault`, `pop`) on any
      receiver is dynamic.
    - **Submodule rebinding.** In any `__init__.py`, every import is resolved
      to a full dotted path, with relative dots joined to the file's module
      path. Wherever the own name is followed by a component `X`, loading
      the submodule sets this package's global `X`. That is a non-definition
      binding at module scope, also when the import is in a function.
      Examples: `import pkg.sub.X`, `from ..sub.X import y`, `from . import
      X`.
  - **`f_locals` (#695 panel A2, B1).** A frame's `f_locals` writes through
    to a function's locals (PEP 667, Python 3.13+). A file that mentions
    `f_locals` anywhere, as an attribute or a constant string, gives
    `dynamic-scope` for every lookup, function scopes included. Without it,
    `exec` and `locals()` cannot rebind a function's locals. The same
    file-wide rule covers every other route that rebinds a binding without
    spelling an assignment to that name (Codex 4655078224): closure cells
    (`__closure__`, `cell_contents`, `types.CellType`), a function rebuilt over
    existing code (`types.FunctionType`/`LambdaType`), code-object surgery
    (`__code__`, `CodeType`, `gi_code`/`cr_code`/`ag_code`/`f_code`, and the
    `co_*` fields `code.replace` rewrites, and the code objects `dis` and
    `sys.monitoring` hand over: `dis`, `codeobj`, `_get_code_object`,
    `monitoring`, and the profiler's `getstats`), a frame's live locals
    through `inspect` (`getgeneratorlocals`, `getcoroutinelocals`,
    `getasyncgenlocals` and `getargvalues(frame).locals` return the PEP 667
    write-through `f_locals` proxy; #695 re-check at 8fd7c1a2), more code-object
    and live-locals sources (`traceback.FrameSummary._code`,
    `bdb.Bdb().code_linenos`, `pdb.Pdb().curframe_locals`) and `annotationlib`
    running a user function under substitute globals
    (`call_annotate_function`, `call_evaluate_function`, `__annotate__`; #695
    re-check at 14e8f044; and `__annotate_func__`, the class-dict key behind
    `type.__annotate__`, re-check at a6734480), raw C-level access (`ctypes`, `pythonapi`,
    `PyFrame_LocalsToFast`) and a `closure=` keyword argument
    (`exec(code, g, closure=cells)`), each in any identifier position, with
    every mangled spelling, or as a constant string. The function type is
    reachable without naming it (`type(f)`, `f.__class__`,
    `type(lambda: 0)`), so a function rebuilt over existing code is caught
    through the code object it needs (#695 re-check at 606c689f).
  - **Line continuations.** A backslash continuation inside a target is only
    a token. Valid targets the reader does not understand still poison the
    scope: `del f()`, `with a as f():` and `type(x).attr = v` (which
    tree-sitter parses as a `type` statement) are committed as test-written
    near-misses (10.6).
  - **Type-parameter scopes.** A PEP 695 generic `def`, `class` or `type`
    statement gets a type-parameter scope between it and its enclosing scope.
    Lookups from its annotations, bases, body and, conservatively, its
    default values pass through it (CPython evaluates defaults outside it,
    so this can only fail closed); a type parameter is `parameter`. An
    annotation scope immediately inside a class still sees the class.
  - **Implicit names.** Module and class namespaces bind every dunder name
    implicitly (a non-definition binding), and a method's bare `__class__`
    is the implicit class cell (`none(local-variable)`).

### 7.4 Group rules

First drop non-callable kinds (namespaces, enums). If nothing is left, the
result is `none(non-callable)`. Then:

| Language | Group | Result | Rule ID |
| --- | --- | --- | --- |
| Any | Any group with **no body** (signatures only, or all ambient; ambient is inherited) | `none(ambient)` if every member is ambient (ambient wins over bodyless, R-1(iii)); otherwise `none(bodyless)` | — |
| Any | One definition | That definition (Python: only if unconditional; a single conditional definition gives `none(conditional)`) | `t1.lexical` |
| TS/TSX | k ≥ 1 bodyless `function_signature` immediately followed by exactly one body that is a `function_declaration`, contiguous, in one scope (PR 2) | The body | `t1.ts_overload` |
| TS/TSX | Signatures with one body in any other shape (a body before a signature, a `const` arrow body, not contiguous) | Every member; narrows, never resolves | `t1.lexical` |
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
| `expression-bound` | A function or arrow bound by `var`/`let`, or a `const` that is not a single declaration; Python: a single decorated `def` or `class`, which binds the decorator's result (PR 4) |
| `self-binding` | A function or class expression's own name |
| `reassigned` | The name is assigned somewhere in the binding's subtree |
| `block-function` | A block-level function declaration binds the name |
| `conditional` | Python: a single conditional definition or import |
| `builtin-shadow` | Python: a module-scope definition or import whose name is a builtin, which the name reaches until it runs (PR 4, #695 panel A3) |
| `mixed-bindings` | Definitions mixed with other bindings, or duplicate imports |
| `class-scope-bound` | Python class-body lookup of a name the class binds |
| `star-import` | Python module-scope lookup in a file with `from m import *` |
| `dynamic-scope` | `eval`/`with` (JS); `exec`/`eval`/`globals`/`vars`/`locals`/`builtins`/`importlib`/`sys.modules` and the other forms of 7.3 (Python), for module-scope and class-body lookups |
| `ambient` | Only ambient declarations bind the name |
| `bodyless` | Only bodyless signatures bind the name |
| `non-callable` | The binding is only an enum or namespace |
| `namespace-merged` | The lookup passes through a merged or script-goal namespace |
| `script-global` | Another file declares the name as a script global |
| `type-only` | Only a type-only import binds the name |
| `enum-scope` | The lookup reaches a TS enum body, where the members of every declaration of the enum shadow outer names (7.2) |
| `unmapped` | A declaration with no symbol, a duplicate span, or an unclassified node; Python: a private name (`__x`) looked up inside a class, which CPython mangles to `_<Class>__x` (the president's #695 ruling, B-1) |
| `no-binding-fact` | The call has no binding entry |
| `stub` | PR 1 only |
| `script-goal-deferred`, `namespace-deferred` | PR 2 only; replaced by real handling in PR 3 |

Unsupported files (5.3) produce no outcomes at all.

**Precedence when two reasons apply (R-1).** Exactly one reason is recorded
per call, decided in this order:

1. The outcome's own reason (`parameter`, `local-variable`,
   `expression-bound`, `self-binding`, `reassigned`, `block-function`,
   `dynamic-scope`, `enum-scope`, `star-import`, `class-scope-bound`,
   `mixed-bindings`, `type-only`, `unmapped`, `no-binding-fact`) wins over
   `script-goal-deferred`,
   `script-global`, `namespace-deferred` and `namespace-merged`. Those apply
   only when the lookup would otherwise prove a group.
2. In a definition group, non-callable kinds are dropped first (7.4), so a
   group of only enums and namespaces gives `non-callable`, even when it is
   ambient (`declare enum E {}`; B7, settled in PR 2). Among the callable
   members left, `ambient` wins over `bodyless`: `declare function amb():
   void;` is both, and ts-declare-ambient expects `ambient`. Then comes
   `conditional`, then (Python, module scope) `builtin-shadow`.
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

**Applied in PR 5:**

- **Exact string values (owner rule).** A module specifier and a quoted
  import or export name (`import {"a-b" as x}`, `export {x as "y"}`) are
  compared by their ECMAScript string value, decoded exactly for strict
  code (`\xHH`, `\uHHHH`, `\u{…}`, single-character escapes, line
  continuations, `\0`). A literal that does not decode exactly (a legacy
  octal escape, `\8`, a malformed escape, a lone surrogate, which
  `IsStringWellFormedUnicode` rejects) fails closed: on the import side the
  binding is `none(unmapped)`, on the export side the module is opaque
  (every lookup in it gives `export-not-found`). Raw source text is never
  compared. Identifiers keep their source spelling, because a file that
  spells any name with an escape is unsupported (5.3).
- **Namespace member calls.** `ns.f()` is eligible only when the reference
  is exactly two segments, the analyzer records the member from the tree
  (a plain `property_identifier`; parentheses, computed keys, private
  names, optional chains and longer chains record none) and the head's
  lookup is a namespace import. A mismatch between the reference and the
  recorded member fails closed (`export-not-found`). Calling the namespace
  itself (`ns()`) is `non-callable`. Every other member call stays
  ineligible in both modes, so the filters never touch it.
- **Import attributes** (`with { type: "json" }`) give `unknown-variant`.

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

**Applied in PR 5** (each only adds `none`):

- `/`-absolute specifiers and anything with a scheme (`node:`, URLs) are
  `external-module`. Specifiers containing `?`, `#`, `%`, `\`, an empty
  segment (`//`) or a trailing `/`, and a JS/TS extension that is not
  lower case (`./svc.JS`), are read differently by toolchains:
  `unknown-variant`.
- A `.js` or `.jsx` specifier also lists `p.js/index.<ext>` (TypeScript
  tries that directory after the file), which can only add ambiguity.
- A candidate that a run file matches only after case folding and NFC
  normalization gives `unknown-variant`: a case-insensitive file system
  would find that file.
- **Platform and module suffixes.** A run file `<stem>.<segment>.<ext>`
  next to a candidate `<stem>.<ext>` gives `ambiguous-extension` unless the
  segment is on a closed allow-list of names no resolver uses as a suffix
  (`test`, `spec`, `stories`, `story`, `bench`, `d`, `types`, `styles`,
  `mock`, `mocks`, `fixture`, `fixtures`, `e2e`, `config`). React Native
  picks `svc.ios.ts` before `svc.ts`, and TypeScript `moduleSuffixes` does
  the same.
- **Directory imports.** When the target is a `p/index.<ext>` candidate and
  `p/package.json` is in the run, or a language filter leaves `.json`
  uncollected, the result is `unknown-variant`: TypeScript and Node read
  that `package.json` (`types`, `main`) first.
- The copies of the collected extensions and skipped directories in
  `modules.py` are pinned against `chunker.auto` and `symbol_graph` by a
  test.

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

**Applied in PR 5:**

- **The export table** is read from a closed list of top-level export
  statement forms; any other form makes the module opaque
  (`export-not-found`). `export default function|class x` and
  `export { y as default }` bind the local; `export default <identifier>`
  (through parentheses and TS wrappers) looks the identifier up; any other
  default expression is `expression-bound`. Type-space exports
  (`export interface`, `export type T =`, `export type { … }`,
  `export { type x }`) give `type-only` only when no value export has the
  name, since a TS interface and a function merge. Two different value
  exports of one name give `mixed-bindings`. `export as namespace X` is
  ignored (it declares a UMD global only).
- **Live bindings** are covered by the exporting module's Tier 1 lookup:
  any write of the binding anywhere in that module (`export let f; f = …`,
  a setter function) gives `reassigned`; `export let f = () => …` is
  `expression-bound`.
- **Stars.** A star source that cannot be resolved or read (external,
  missing, ambiguous, CommonJS, opaque, unsupported, a cycle, the hop
  limit) fails the whole lookup closed with its reason, because it might
  provide the name. Stars never provide `default`. A star step counts as a
  hop.
- **CommonJS reach** (executive scope rule, §15 R12). When TS or a bundler
  emits CommonJS, `import { t }` reads `exports.t` at call time and the
  exports object is shared and mutable. A module gives `commonjs` wherever
  a lookup reaches it (the first target or any hop) when: it is
  script-goal, has `export =`, or mentions `exports`, `module`, a
  top-level `this` or a top-level `arguments`; or another file of the run
  may write its exports object. A file taints a module through a namespace
  import used outside a closed allow-list of read positions of `ns.name`
  (call, `new`, argument, member object, initializer, return, operand,
  array or object value, assignment right side, type position; each use
  found by the ordinary lookup at its site, after unwrapping parentheses
  and TS wrappers), `export * as x from`, and any `require(<string>)`,
  `import(<string>)` or `import x = require(<string>)` (every candidate the
  specifier may name, under either importer language). A file taints every
  module (`taint_all`) through `require` or `import()` used any other way,
  `module` other than `module.exports`, the names `mainModule`,
  `createRequire` and `getBuiltinModule` (also as string keys), an import
  of `module`/`node:module`, an undecodable specifier, the `*` script
  global (code evaluators and global-object escapes, 7.2), or by being an
  unsupported JS/TS file.

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
  chains (`ns.sub.f`), `ns?.f()`, `ns["f"]()`, CommonJS modules and
  `require` bindings, and the routes named in §15 R12 (TS/JS)
  (treesitter-chunker#702).
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
PR 5 also reports Tier 1 reasons where they fit: the target module's own
lookup reason (`reassigned`, `expression-bound`, `ambient`, …),
`mixed-bindings` for a duplicate export name, `expression-bound` for a
default expression, `non-callable` for a called namespace object and
`unmapped` for an import literal that does not decode. Fold 1 adds
`run-tainted:evaluator`, `run-tainted:dynamic-loader`,
`run-tainted:module-system`, `run-tainted:module-object`,
`run-tainted:unparsed-file` and `run-tainted:unresolvable-writer` (9.9).
PR 6 (Python, 9.10) adds `module-escape` (a module another file may write
wholly), `module-getattr` (fold 2, E6-3: a package's module `__getattr__`
may answer a submodule name) and reports `reassigned` for a name another file writes,
`non-callable` for a called submodule, `external-module` for a
standard-library name and `unknown-variant` for a skipped-directory
component.

### 9.9 PR 5 fold 1 (the president's rulings E5-1..E5-5 on #703)

Each rule only adds `none`.

- **E5-1, CommonJS emit is in scope.** Any JS/TS file of the run may be
  compiled to CommonJS, where an import binding reads the shared, mutable
  exports object at call time.
  - **A1:** a write to a named, default or namespace import binding
    (assignment, compound or logical assignment, update, destructuring, a
    `for … of/in` head, through casts), found by the ordinary lookup at the
    write site, taints the exporting module in every file.
  - **A2/B-5:** under CommonJS emit, `ns.f()` passes the exports object as
    `this`. The narrowest sound rule: every allow-listed use of
    `ns.name` is recorded, and the engine requires `name` to be a verified
    export of that module (any other member, such as `__defineGetter__`,
    `__defineSetter__` or `__proto__`, taints it). A call `ns.f(…)`, also
    `(ns.f)()`, `ns.f?.()` and a tagged template, additionally requires
    the export to end, through any hops, at declarations that never
    mention `this` or `super` (the export table's `this` flag; nested
    functions count too). Otherwise the namespace's module is tainted.
    Reads, `new ns.K()`, `class C extends ns.Base` and JSX `<ns.Comp />`
    need only a verified export; `typeof import('./x')` in a type
    position is erased and taints nothing.
  - **B-4:** `this` (and `arguments`) is module level wherever a top-level
    evaluation reaches it, by the Tier 1 scope rule applied exhaustively:
    arrow functions inherit it; a non-arrow function or method rebinds it
    for its parameters and body only, not for a computed name or a
    decorator; a class field initializer and a static block rebind it, a
    computed key and the `extends` clause do not. Such a module is
    `commonjs`. The parameters of a non-arrow function evaluate under that
    function's own `this`, so an immediately invoked non-arrow function
    does not count; an immediately invoked arrow function does.
- **E5-2, use-site lookup.** `module`, `exports` and `require` count only
  when the ordinary lookup at the use finds no binding or the program's
  own (a parameter or local named `module` is not CommonJS). A literal
  `require('<x>')` taints whatever binds the name (an AMD `require`
  parameter loads modules too). Timers, `eval`, `Function` and the global
  object are decided by Tier 1's use-site lookup. The identifiers
  `createRequire`, `mainModule` and `getBuiltinModule` count when unbound or
  bound by an import; as property names (`process.mainModule`) and as
  string or template values they are matched by name, because a property's
  receiver may be an alias of `process`.
- **E5-3, the run-wide shutoff is narrowed and visible.** The Tier 1 `*`
  wildcard alone no longer shuts Tier 2 off. The run-wide causes, each
  with its own reason `none(run-tainted:<cause>)` and a logged diagnostic
  naming the first file:
  - `evaluator`: `eval`, `Function`, `execScript`, the `.constructor` route,
    an escaped or computed key that may name one, and a direct timer call
    whose first argument is a string, a non-function expression or an
    unbound name (the sleep idiom `setTimeout(r, ms)` with a local or
    parameter is not one; a saved or reassigned timer is not one, since
    only a call runs text and Node rejects a string timer);
  - `dynamic-loader`: a non-literal `require` or `import()`, `require`
    used other than as a literal call (`typeof require`,
    `require.resolve(…)` and `require.main` compared are inert), and Bun's
    `import.meta.require` or any `import.meta` use other than a plain read;
  - `module-system`: `createRequire`, `mainModule`, `getBuiltinModule`, an
    import, `require` or `import()` of `module`/`node:module`, a specifier
    that does not decode, and a string whose sloppy-mode value names one of
    those (legacy octal escapes decode); templates are matched on their
    cooked text;
  - `module-object`: `module` (resolving to the CommonJS module object)
    used other than as `module.exports`, `typeof module` or a compared
    operand;
  - `unparsed-file`: a JS/TS file whose tree has errors is no longer a
    run-wide cause by itself. Its text is scanned conservatively (also
    after decoding `\u`/`\x` escapes): any spelling of the routes above is
    a run-wide cause, every relative string literal taints the modules it
    may name, and lookups into it fail closed. A file with no text to scan
    is a cause;
  - `unresolvable-writer`: a taint whose target cannot be computed.
  Off, `name` and `structural` output are unchanged. The bundled
  TypeScript grammar does not parse `export type * from` (a parse error,
  so the file is text-scanned); the grammar pin is unchanged.
- **E5-4, rejected specifiers still taint.** A taint resolves leniently:
  a query or hash is cut, `\` becomes `/`, percent escapes are tried both
  ways, empty segments collapse, a trailing `/`, `.` or `..` means a
  directory, extensions match in any case and paths after case folding.
  A target outside the root, or a writer collected through a symlink, is
  `unresolvable-writer`.
- **E5-5, cheap fail-closed rules.** A `.` or `..` segment after the
  leading prefix, and the bare `.` and `..`, give `unknown-variant`. A JS/TS
  file collected through a symbolic link (the file or a directory between
  it and the root, recorded in its facts and in the on-mode cache key)
  never resolves an import from or into it. A run file that matches the
  requested path exactly with another extension (`svc.css` beside
  `svc.css.ts`) gives `unknown-variant`. Template triggers are matched on
  cooked values.
- **Q1 kept:** the inert sibling segments are pinned as a closed list.

**Fold 2: owner decision O-2, "scope by caller".**

- **Classifier** (closed, case-sensitive, path-based; `TEST_NAME_SEGMENTS`
  and `TEST_DIRECTORIES` in `modules.py`): a file is test code when a
  basename segment between dots is exactly `test` or `spec`
  (`svc.test.ts`, `svc.spec.tsx`, `svc.test.d.ts`), or a directory segment
  is exactly `__tests__`, `__mocks__`, `test` or `tests`. Not test code:
  `contest.ts`, `testing/`, `latest.ts`, `my.tests.ts`, `Test/`, `test.ts`.
  `e2e/`, `cypress/` and `playwright/` are not on the list: they are
  usually test-only (graph-studio's `apps/web/e2e/` is its Playwright
  `testDir`), but they are not guaranteed to be, and they also hold support
  modules (`owner-fixture.ts`).
- **Promotion.** Production is the fixpoint over the import graph from
  every non-test file: static imports and re-exports
  (`module_bindings["imports"]`), stars, and literal `require`/`import()`
  and taints, each resolved leniently (E5-4), transitively. A test file a
  production file reaches is production. A production specifier whose
  target cannot be computed promotes every test file.
- **Scoping.** Run-wide causes in production files fail every Tier 2 edge
  closed; those in test-scope files fail only edges whose caller is a
  test-scope file. Per-module taints written in a test-scope file (an
  import-binding write, a namespace escape such as `jest.spyOn(ns, 't')`, a
  rejected-specifier taint, an unverified namespace member) taint the module
  only for test callers. Reasons are unchanged
  (`none(run-tainted:<cause>)`, `none(commonjs)`), and each cause is logged
  with its scope (production or test-scoped).

**Fold 3: closed allow-lists for three run-wide causes** (the E-21
approach). Each list lives in one place; every check uses the ordinary
lookup at the use site; anything outside a list keeps its run-wide effect.

1. **Imports from `module`/`node:module`** (`js_modules.INERT_MODULE_EXPORTS`).
   Inert when the statement is type-only, or every binding is a named import
   of `builtinModules` or `isBuiltin` used only by reads and calls (no
   write), or of `createRequire` used as item 2 allows. Run-wide: a default
   or namespace import, any other name (`Module`, `_load`, `register`,
   `syncBuiltinESMExports`, …), import attributes, `export … from 'module'`,
   and `require`/`import()` of `module`.
2. **`createRequire`** (`js_modules._local_require`). Every use of the
   imported binding must initialize one `const` name
   (`const r = createRequire(<anything>)`, through parentheses), and every
   use of `r`, found by lookup, must be a direct call with one string or
   cooked-constant template argument, or `r.resolve(<literal>)`. A literal
   call taints its target like `require` (with E5-4's lenient
   normalization); `r('module')` is run-wide. Run-wide: a non-literal call,
   `r.cache`, `r.main`, `r` passed on or aliased, a `let`/`var` binding, an
   immediate `createRequire(x)('./a')`, and `createRequire` reached any other
   way (a free identifier, a property, a string).
3. **`.constructor`** (`js_scope._safe_constructor_read`,
   `_SAFE_CONSTRUCTOR_OPERATORS`). Safe only as the object of a
   non-computed `.name` read, an operand of `===`, `!==`, `==`, `!=` or
   `instanceof`, or the argument of `typeof`. Every other position (a call,
   an argument such as `expect(x.constructor)`, an assignment value, a
   return, a container element, a spread, a computed key, any other member
   read, `!`) stays an `evaluator` cause. Tier 1's own `*` wildcard is
   unchanged.

Runtime trace (node v24.22.3): `isBuiltin('fs')` and
`builtinModules.includes('fs')` return values and change nothing; a literal
`r('./svc.js')` returns the same exports object, leaves `r.cache` unchanged
on a repeat and writes no export; `o.constructor.name`,
`o.constructor === K`, `o instanceof o.constructor` and
`typeof o.constructor` never call the constructor (0 calls on a spy class).

**Fold 4 (the president's review at ec86f20c, P5-1..P5-3).**

- **P5-1, the `createRequire` base.** Node resolves `r('<lit>')` from the
  base given to `createRequire`. A local require `r` taints its literal
  targets only when the base is, verified by lookup, `import.meta.url`,
  `import.meta.filename` or `__filename` (free, or bound only at the top
  level). Any other base (`__dirname`, `path.join(…)`, a variable,
  `pathToFileURL(__filename)`, `new URL('./lib/', import.meta.url)`) makes
  every literal target uncomputable: an `unresolvable-writer` cause scoped
  by the file's own classification, and the file's `uncomputable` flag,
  which promotes every test file when the file is production.
- **P5-2, directory symlinks** (the president's option 1). Collection never
  follows a directory symlink, so a production import may reach a test
  file through a path the run never collected. When any directory symlink
  lies under the run root outside the skipped directories
  (`symbol_graph.has_directory_symlink`, computed at collection and passed
  to assembly as `directory_symlinks`), every test file is production. An
  assembly that does not say (`directory_symlinks=None`) is treated the
  same way. The flag is run-level, so per-file facts and cache keys are
  unaffected.
- **P5-3, test-framework module mocks** (`js_modules.MODULE_MOCKS`, a
  closed list): `jest.mock`, `jest.doMock`, `jest.unstable_mockModule`,
  `jest.setMock`, `vi.mock`, `vi.doMock`, with `jest`/`vi` free or imported
  from `@jest/globals`/`vitest` by the ordinary lookup. A relative literal
  first argument taints its target (lenient), scoped by O-2 like any taint;
  a non-literal one is an `unresolvable-writer`; a bare specifier names a
  package outside the run.
- **Item 4, uncomputable production targets.** A package `imports` alias
  (`#x`), an absolute path (`/x`, `C:/x`), a `file:` URL and
  `import.meta.glob`/`globEager` cannot be located, so a production file
  with one promotes every test file, and a write through one
  (`require('#x').t = …`) is an `unresolvable-writer`.

**Fold 5 (the president's re-check at 3344e9db, P5-13..P5-18).**

- **P5-13, own-file bases must be unwritten and unbound.** `__filename` is
  accepted only when (a) the use-site lookup finds no binding of it in the
  file (no `const`/`var`, import or alias import), (b) no assignment target
  in the file is `__filename` (any write form, anywhere in the file), and
  (c) no run file can write a global `__filename` (fold 6 dropped the
  CommonJS-file shortcut, P5-20): a Tier 1 `*` wildcard,
  `globalThis`/`global`/`window`/`self.__filename = …`, a top-level
  `var __filename` in a script, an implicit global, an unsupported JS/TS
  file, or an HTML/XML/PHP file in the run. The analyzer records the
  ES-module case as `filename_taints`; the engine taints them, or makes
  them an `unresolvable-writer` with promotion when a writer exists. The
  `fileURLToPath(import.meta.url)` idiom is not accepted.
  `import.meta.url`/`.filename` are accepted only when no `import.meta.<p>`
  sits in a write position (assignment, compound or destructuring target,
  update, `for … of/in` head, `delete`); an aliased or escaped
  `import.meta` is already `dynamic-loader`.
- **P5-14, skipped directories.** A relative specifier whose leniently
  normalized path has a `SKIP_PARTS` segment is uncomputable: every test
  file is promoted, and a write through it is an `unresolvable-writer`. The
  directory-symlink check still does not walk `node_modules`.
- **P5-18.** `file:` and `data:` are matched in any case; both are
  uncomputable.
- **P5-16.** A Windows directory junction (`Path.is_junction()`) counts as
  a directory symlink.

**Fold 6 (the president's re-check at 9d180a97, P5-20, P5-21).**

- **P5-20.** The CommonJS shortcut is dropped: `filename_taints` always go
  through the engine's run-wide writer check. Every file on this path
  imports from `module` (ESM syntax), so a CommonJS hint (`this`,
  `typeof exports`) never proves `__filename` is the wrapper's parameter.
  A run with no writer still taints exactly.
- **P5-21.** A path segment names a skipped directory after case folding
  and after Win32 strips a trailing dot or space
  (`part.rstrip(". ").casefold()`): `./Build/…`, `./NODE_MODULES/…`,
  `./Dist/…`, `./build./…` and `./build /…` are uncomputable.
- **URL whitespace.** Before the scheme is matched, leading and trailing
  C0 controls and spaces are stripped and every tab, LF and CR is removed
  (WHATWG URL parsing), so `' file:///…'`, `'\tfile:…'` and `'fi\tle:…'`
  are `file:` URLs.

**Fold 7 (the president's re-check at ae5f53a5, P5-27, P5-32).**

- **P5-27.** `filename_taints` feed the O-2 edge graph with `imports`,
  `taints` and `stars`, so a production file that loads a test file through
  `createRequire(__filename)` promotes it. With a writer the file is already
  `uncomputable`; with none the literal resolves leniently.
- **Taint-source audit.** Every analyzer source that can name a file feeds
  `edges[path]` or `uncomputable`:
  - static imports and `export … from`: `imports`;
  - `export *`: `stars`;
  - `export * as`, literal `require`/`import()` (also cooked templates),
    `import x = require`, own-file `createRequire` literals, module mocks,
    import-binding writes, namespace escapes, rejected specifiers (taken
    leniently), and text-scan literals of unparsed files: `taints`;
  - `createRequire(__filename)` literals: `filename_taints` (fold 7);
  - unverified namespace members: the namespace import's specifier, already
    in `imports`;
  - another `createRequire` base, `import.meta.glob`, and a
    `createRequire(__filename)` with a global writer: `uncomputable`;
  - `#`, absolute, `file:`/`data:` and skipped-directory specifiers: an
    uncomputable lenient target (`None`), which promotes every test file.
  `test_every_file_naming_source_promotes` pins 14 of them, from production
  `app.ts` to `tests/w.ts`.
- **P5-32.** A segment counts as a skipped directory after
  `rstrip(". ")` plus `casefold()` or `upper().casefold()`. A segment
  containing `:` (an NTFS stream such as `build::$INDEX_ALLOCATION`), or one
  matching the 8.3 short-name pattern `^[^~]{1,6}~[0-9]+(\.[^.]{0,3})?$`,
  is uncomputable.

**Fold 8 (Codex on 6d0aadd0) and fold 9 (executive ruling E5-7).** Fold 8
replaced the regex fallback for unparsed files with a lexer-level scan; the
president's re-check at a27278b7 found six runtime-confirmed escapes from it
(P5-40..P5-45: regex vs division after `)`, a `typeof` call chain, Unicode
spaces, HTML-like comments, `arguments[1]`, `#`/absolute static imports).
**E5-7 removes the text-scan fallback** (a hand-written JS lexer is an
open-ended deny-list) and walks back the parse-error part of E5-3: **every
JS/TS file that tree-sitter cannot parse cleanly is a run-wide
`unparsed-file` cause, scoped by O-2.** A test-scope unparsed file affects
only test callers; one that a production file reaches by an edge (from a
parsed file) is promoted like any other. Its own outgoing targets are
unknown, but none is needed: as a production file it already shuts every
caller off, and as a test-scope file its targets matter only to test
callers, whom it already shuts off. `js_textscan.py` is deleted, and the
wheel payload returns to 346 files.

- **P5-44 (parsed path).** At module level the CommonJS wrapper's
  `arguments` is `[exports, require, module, __filename, __dirname]`. A free
  module-level `arguments` (by the ordinary lookup, so a function's own
  `arguments` is not one) used other than as `typeof arguments` or an
  equality operand (a closed list) is a `dynamic-loader` cause.
- **P5-41 (parsed path).** `typeof require(<non-literal>)…` was never
  exempt there; a test pins the `dynamic-loader` cause.

**Fold 10 (the president's re-check at 9bcd20c1, P5-47..P5-49).**

- **P5-47.** tree-sitter's `hash_bang_line` and `html_comment` tokens run
  past JS line terminators that V8 and TypeScript honour, with no error. So
  a JS/TS file whose text contains a lone CR (one not followed by LF), a
  U+2028 or a U+2029 anywhere, or whose tree has any `html_comment` node
  (TypeScript has no HTML-like comments), is unparsed (E5-7). The check
  sits next to `has_error` in `compute_scope_facts`. A CRLF file stays
  parsed.
- **P5-48.** In sloppy code a module-scope declaration of `arguments` (a
  `var`, a function declaration, any binding the scope pass records at the
  program scope) still names the CommonJS wrapper's object, so it is a
  `dynamic-loader` cause. A function-local `var arguments` is not one.
- **P5-49.** `module_level` (shared by the module-level `this` check and
  the `arguments` checks) climbs through a **static** field initializer and
  a static block, because tsc below ES2022 hoists them to module scope.
  An instance field initializer runs in the constructor and still stops
  the walk. The module-system names (`require`, `createRequire` and the
  rest) never used this walk; the use-site lookup already treats a static
  block like any other code.
- **P5-37.** The 8.3 short-name match runs on the segment after the Win32
  trailing dot/space strip.

**Fold 11 (the president's re-check at cc3c2d3d, P5-50).**

- **P5-50.** tree-sitter-javascript reads two Annex B HTML-like comments as
  code, with no error and no `html_comment` node: a `-->` after a
  multi-line comment that contains a line break and starts after code, and
  a `<!--` in the middle of a line. V8 (Script goal) makes the rest of the
  line a comment, while tree-sitter can open a template or `/*` there that
  hides the next lines, `require` writes included. So in a JavaScript file
  (`.js`/`.jsx`; TypeScript has no HTML-like comments) each byte is marked
  code or not: not code means inside a `comment`, `html_comment`,
  `hash_bang_line`, `string`, `regex`, `jsx_text` or the text of a
  `template_string` (a `template_substitution` is code again). The file is
  unparsed (E5-7) when (a) a `<!--` starts on a code byte, or (b) a `-->`
  starts on a code byte and every byte between the last line break before
  it and the `-->` is whitespace or inside a comment (that line break may
  sit inside a multi-line comment). A non-ASCII byte counts as whitespace
  there (fail closed). Raw bytes are not scanned, so HTML text in strings,
  templates and regexes is unaffected, and so is `while (i-->0)`. The
  precise rule was chosen over the blunt "any `<!--`/`-->` on a code byte"
  fallback; it costs nothing on the 8 measured trees.

### 9.10 PR 6: Tier 2 Python (applied)

`chunker/call_resolution/py_modules.py`. Each rule only adds `none`, except
the import proofs themselves (9.4-9.6). `structural` output is unchanged.

- **Import bindings (9.4).** `from m import x [as y]` binds `(m, x)`;
  `import a.b` binds `a` to module `a` (the facts' `bound`), `import a.b as
  m` binds `m` to module `a.b`. A call `x()` follows `(m, x)`; a member
  chain `m.f()`, `a.b.f()`, `u.f()` (read from the tree, which must match the
  reference exactly) follows the chain attribute by attribute, each
  intermediate value a module. Two or more imports of one name and nothing
  else (`try`/`except` fallbacks, two sequential imports) form a group: every
  member must prove a target, and the union narrows; it resolves only when
  every member proves the same definitions. A single conditional import is
  `conditional`; a group mixed with any other binding stays
  `mixed-bindings`. `t2.import` for a bare call, `t2.namespace` for a chain.
- **Module paths (9.5).** One component at a time from the root, regular
  package before module before namespace directory; an intermediate module
  gives `module-not-found`. An absolute import whose first component exists
  in the importer's own non-root directory gives `script-dir-shadow`
  (checked first). A first component that is a standard-library module name
  (`STDLIB_MODULES`: CPython 3.14's `sys.stdlib_module_names` plus the
  modules 3.13 removed, pinned by a test) gives `external-module`: builtin
  and frozen modules win over any file, and the root's place on `sys.path`
  relative to the standard library depends on how the program starts. A
  component named like a directory collection skips (`SKIP_PARTS`) gives
  `unknown-variant`. Relative imports start at the importer's package; the
  root is the `sys.path` entry, not a package, so a root-level relative
  import gives `outside-root`. Extension modules and `.pyi` stubs are not
  collected (R7).
- **Name lookup (9.6).** The target's export table is every module-scope
  name's Tier 1 module lookup (so the target's own `dynamic-scope`,
  `star-import`, `conditional`, `expression-bound`, `builtin-shadow`,
  `mixed-bindings` and attribute-write rules apply). A name missing from it
  is `export-not-found` (or the module's own `dynamic-scope`, `star-import`
  or `unmapped`). A package binding the name and holding a submodule of that
  name is `attr-submodule-conflict`, unless the only bindings are its own
  unconditional submodule import (`from . import b`) and the writes that
  import makes (`own_submodules`; fold 2, E6-3). A submodule the resolver
  cannot read (a skipped-directory name, S-1) counts as a submodule. A
  submodule only is a module value (`non-callable` when called), unless the
  package defines a module-level `__getattr__` (`module-getattr`: PEP 562
  answers before the submodule loads, E6-3) or may bind names at run time
  (its own `dynamic-scope`, `star-import` or `unmapped`, A-3). An import
  entry is a hop; more than 3 hops `hop-limit`, a revisited pair `cycle`.
- **Other files' writes (treesitter-chunker#697, executive rule 2).** Every
  use of an imported name is found by the ordinary lookup at the use site
  (every import of the name when the lookup cannot tell, as for a
  `try: import svc / except: svc = None` head; none when it proves the
  file's own binding). An imported module object may appear only in a
  CLOSED allow-list: an attribute read or a call of a member; an attribute
  write (assignment, augmented, `del`, `for`/`with` target, through
  parentheses) or `setattr`/`delattr` with a constant name and the builtin
  verified by the lookup, which records exactly that name; an operand of
  `is`, `is not` or `not`, or a bare `if`/`elif`/`while` test. Every other
  use is an escape: the value the chain reads (the module itself, or a
  submodule or module re-export reached through it) is tainted wholly, and so
  is a module whose dunder attribute other than `__name__`, `__qualname__`,
  `__doc__`, `__file__`, `__module__`, `__version__` is read. A class-level
  import and an import redirected by `global`/`nonlocal` are escapes. So is
  every import binding of a file that hands out its own namespace
  (treesitter-chunker#724, executive ruling R-724-1). The rule is
  token-level: the file hands out its namespace when ANY token in it spells
  a namespace-reaching name, in any role (an identifier, an attribute, an
  import name, a keyword argument name, or a constant string, decoded and
  joined across adjacent literals and `+`, matched exactly or as a dotted,
  `:`, bracket, quoted or format-field (`{`, `}`, `!`) component, so
  `"{0.__globals__!r}"` counts although `string.Formatter` resolves it
  without its caller spelling `get_field`). Shadowing is ignored; any spelling
  counts. The names: `globals`, `locals`, `vars`; `f_globals`, `f_locals`,
  `f_builtins`, `__globals__`; `__import__`, `getmodule`, `getclosurevars`;
  `__loader__`, `__spec__`, `load_module`, `exec_module`; `get_field`
  (`string.Formatter`); `builtins`; the frame-locals readers
  (`getargvalues`, `getgeneratorlocals`, `getcoroutinelocals`,
  `getasyncgenlocals`, `curframe_locals`); and the annotation evaluators
  (`get_type_hints`, `get_annotations`, `eval_str`, `ForwardRef`,
  `evaluate_forward_ref`, `_eval_type`, `call_annotate_function`,
  `call_evaluate_function`); and, since R-724-4 (each kept at a measured
  production cost of 0 edges), `getmembers`, `getmembers_static`,
  `DocTestFinder`, `globs`, `rlcompleter`, `__builtins__` and
  `PyEval_GetGlobals`. Two more routes count since R-724-4: a callee named
  `resolve_name`, `locate` or `resolve` whose first argument is `__name__`
  or a constant whose first component is a component of the file's own
  module path (`pkgutil.resolve_name("use:svc")`), and pytest's
  `request.module`. One closed allow-list (R-724-2) exempts a
  token use whose object the use-site lookup proves is not the file's own
  namespace, covering the costed sites and nothing more: the receiver is a
  *fresh module*, a function local decided by the lookup in its own
  function whose one binding there is `X = F(...)`, with `F` proven by its
  imports (every binding of the head is one import, no star import, no
  recorded write of the head or a chain name) to be `types.ModuleType` or
  `importlib.util.module_from_spec`; the exempt uses are `exec(code,
  X.__dict__)` (the builtin, exactly two positional arguments) and
  `<name>.loader.exec_module(X)` (exactly one positional argument); and
  `__import__(K)` (the builtin, one positional constant absolute name `K`)
  when `K`'s top-level package is no classified module (`sys`,
  `importlib`, `builtins`, `__main__`, `inspect`, `gc`, ...) and no
  component of the file's own module path. `vars(X)`, `getattr(X,
  "<token>")`, an import-binding or literal-dict receiver and `eval` are
  not exempt: no costed site uses them. Any frame, function or
  `globals()` route stays a trigger. R-724-4 voids every exemption of a
  file in which any constant spells a token or a factory's own name
  (`ModuleType`, `module_from_spec`) as a word (split at every
  non-identifier character: the code an exempt `exec` runs, `"import sys;
  d = sys._getframe(1).f_globals"`), or any factory path name (`types`,
  `importlib`, `util`, ...) as a component (a patch target or a module key:
  `mock.patch("importlib.util", U)`, `mock.patch.dict(sys.modules,
  {"types": T})`); and a fresh-module receiver needs a file that writes
  `__class__` on no receiver (`mod.__class__ = M` may give the module a
  `__dict__` property that returns another namespace). Also: an import of `__main__` (an import
  statement, or `"__main__"` as a call argument or subscript key); a bare
  `eval`, `exec` or `execfile` used other than as a binding, with any
  arguments (`exec(code, d)` included: `d` may be the namespace) or handed
  on, and the Python 2 `exec` statement; and, in a file that spells a route
  to the builtins (`__builtins__`, `__builtin__`, `bltns`, `__self__`),
  `X.eval`/`X.exec` or the string `"eval"`/`"exec"`. One narrowing: a
  frame's `f_locals`/`f_globals` read by a constant key (`.get(K)`, `[K]`)
  hands out only the binding `K`, and only when `K` is a non-dunder name
  that is an import binding of the file; a dunder key (`__builtins__`,
  `__loader__`, `__spec__`, `__name__`) or any other key (a function's
  `__globals__` reaches the namespace) hands out every binding, and
  `K in frame.f_globals` none. In a package `__init__.py` the namespace
  holds its submodules too, so a full hand-out taints the package wholly,
  and through it every submodule. A handed-out binding of `sys`,
  `importlib` or `builtins` (any alias) is a run-wide `module-system`
  cause, scoped by O-2 like every cause. A
  literal acquisition (`importlib.import_module('svc')`, `__import__('svc')`,
  `sys.modules['svc']` or `.get`/`.pop`/`.setdefault` with a constant,
  `sys.modules[__name__]`) taints its target wholly; a dotted constant
  string (`mock.patch('svc.t')`, `monkeypatch.setattr('svc.t', f)`,
  `'svc:t'`) records its name; `from m import *` taints wholly every module
  `m` exposes. A wholly tainted module taints every module it exposes as an
  attribute (its submodules, the modules it imports at module scope, its
  star sources' exposures), transitively. A written module name denotes the
  run module of that dotted name and, for an absolute name written from a
  file below the root, the one in the writer's own directory; within one
  process a dotted name is one module object, and the same file imported
  under another name is a separate object a write does not reach, so no
  other module is meant. A tainted name gives `reassigned`, a wholly tainted
  module `module-escape`, wherever a lookup meets it: the first target, any
  hop, any chain step, **and the module's own Tier 1 module-scope proofs in
  `imports` mode** (a proof declaration exported under that name).
- **Run-wide causes (executive rule 3, E5-3 analog).** Every trigger is
  decided by the ordinary lookup at the use site (a builtin is one the file
  does not bind; a module is the import binding the lookup proves).
  `evaluator`: `exec`, `eval`, `execfile` (any use), the Python 2 `exec`
  statement. `compile` alone is no cause (executive ruling on #705, Q2): it
  only builds a code object, which runs through `exec`/`eval` or a globals
  dict a tracked route reaches. `dynamic-loader`: `import_module` or `__import__` with a
  non-literal first argument, a literal naming a module this rule set
  classifies (`importlib`, `builtins`, `sys`, `runpy`, ...), any `importlib`
  use off the closed list (`importlib.metadata`, `importlib.resources`,
  `importlib.abc`, `invalidate_caches`, `util.find_spec`, `import_module`
  with a literal, `reload` of a name), `runpy`, `imp`, `zipimport`, the
  string resolvers (`pkgutil.resolve_name`, `get_loader`, `find_loader`,
  `pydoc.locate`, `safeimport`, `importfile`, `logging.config._resolve`,
  `_importer`, and `resolve_name`/`safeimport`/`find_class` in any
  position). `module-system`: `sys.modules` off its closed list (a literal
  key read or written, a literal getter, `'x' in sys.modules`),
  `sys.path`/`meta_path`/`path_hooks`/`path_importer_cache` other than an
  `in` operand, a dunder of `sys`, `sys` handed on, `os.sys`/`X._sys`
  treated as `sys`, `from sys import modules`, `__path__`,
  `site.addsitedir`, a string naming `sys` and `modules`. `module-object`:
  `__globals__`, `f_globals`, `f_builtins`, `getmodule`, `__builtins__`,
  the `builtins` module, `bltns`, `__main__`/`__mp_main__` outside the
  module-level guard, `pythonapi`, `PyFrame_LocalsToFast`, and a frame's
  `f_locals` other than a read (`.get(...)`, a subscript read, an `in`
  operand), because a module-level frame's `f_locals` is the module's
  globals. `unresolvable-writer`: a relative `import_module` whose package
  is not a literal. As for TS/JS (PR 5), a cause shuts off Tier 2 for the
  callers it applies to (`run-tainted:<cause>`); Tier 1 proofs keep their
  `structural` result except where a taint names their module global.
  **Tier 1 file-wide triggers that become run-wide** in Tier 2: `exec`,
  `eval`, `__import__`, `importlib`, `sys.modules`, `__builtins__`/
  `builtins`, `__main__`, `__globals__`, `f_globals`, `f_builtins`,
  `getmodule`, the string resolvers, `pythonapi`, and `f_locals` (writes).
  **Tier 1 triggers that stay file-local:** `globals`, `vars`, `locals`
  (they reach the file's own namespace; `vars(svc)` is an escape of `svc`),
  the own-name rule, the attribute-write rule, the namespace and mock rules
  (writes through a module are escapes or named writes here), and the
  closure-cell and code-object names (`__closure__`, `cell_contents`,
  `__code__`, `CodeType`, `FunctionType`, `ctypes` without `pythonapi`,
  ...) used on objects no module chain reaches: they change what a function
  runs, not which definition a module attribute holds. A write through an
  attribute chain rooted at an imported module (`svc.t.__code__ = …`) taints
  the chain's first attribute, `svc.t` (fold 2, E6-6); such a write through
  an object obtained otherwise is plan risk R12.
- **Parse classification (E5-7 analog, executive rule 5).** A Python file
  Tier 1 does not analyze (a tree error, `RecursionError`, an analyzer
  failure, a non-ASCII identifier, ambiguous indentation) is a run-wide
  `unparsed-file` cause, scoped by O-2, and so is a file CPython and
  tree-sitter may read differently with no tree error (`parse_hazard`): a
  lone CR, a NUL, vertical-tab or Ctrl-Z byte, a PEP 263 coding declaration
  other than UTF-8 or ASCII (CPython's normalization), a BOM with any coding
  declaration, both tab- and space-indented lines (CPython's `TabError`
  rules), and a `line_continuation` that is not exactly a backslash before
  the line break. No tokenizer is written; the rules are byte rules. Cost on
  the 8 measured trees: 0 files.
- **O-2 for Python (owner decision, executive rule 4).** Classifier
  (`is_test_path`, closed, case-sensitive, path-based): a basename
  `test_*.py`, `*_test.py` or `conftest.py` (pytest loads it only), or a
  directory segment exactly `tests` or `test`. Not test code: `testing/`,
  `contest.py`, `Tests/`, `my_tests.py`, `test.py`, `tests.py`. Promotion is
  the fixpoint over every edge a file may load another through (imports,
  uses, acquisitions, stars, dotted strings, each resolved like a taint
  target, every prefix of a dotted name); a test file a production file
  reaches is production. A directory symlink under the root, or not knowing
  (`directory_symlinks=None`), makes every test file production (P5-2).
  Causes and taints from test-scope files apply only to callers in
  test-scope files.

**Fold 2 (the president's rulings E6-1..E6-8 on #705).** Each rule only adds
`none`, except E6-7 (a narrowing) and the E6-3 own-submodule allowance.

- **E6-1, a module's own bindings are re-checked (A-1, A-4, B1).** A Tier 2
  proof starts from the caller's own binding of the reference's head name.
  Another file's write of that name (`use.t = o`, `setattr(use, 't', o)`,
  `mock.patch('use.t', o)`, `use.svc = other`), a whole-module taint of the
  caller, or, in a package `__init__.py`, a submodule of that name (importing
  `pkg.tool` anywhere sets the package global `tool`) fails the proof closed
  (`reassigned`, `module-escape`, `attr-submodule-conflict`). The same
  submodule check applies to the package's own Tier 1 module-scope proofs in
  `imports` mode.
- **E6-2, intermediaries over-approximated (B2).** The facts record every
  import binding that lands in a module's namespace (`module_imports`),
  whatever its Tier 1 lookup gives (conditional, `try`/`except`, repeated,
  in a file with `globals()`). Chain walks, star exposure, aliases
  (`from mid import svc as s`) and the whole-taint closure follow all of
  them, so a write through `mid.svc` taints `svc`.
- **E6-3, package attributes (A-2/B4, A-3/B3).** `import a.b as m` binds
  `getattr(a, "b")` (CPython 3.7+ `IMPORT_FROM`), so each component after
  the first is resolved as an attribute of its package, with the conflict,
  export and taint checks; the result must be a module, else
  `attr-submodule-conflict`. A package binding `b` other than by its own
  unconditional `from . import b` gives `attr-submodule-conflict`. A package
  with a module-level `__getattr__` makes every submodule access through the
  package attribute `none(module-getattr)`: PEP 562 answers `from pkg import
  sub`, `pkg.sub` and `import pkg.sub as m` before (or instead of) the
  submodule. The reason is new because neither `export-not-found` (the name
  exists) nor `attr-submodule-conflict` (no binding names it) describes it;
  for `import pkg.sub as m` CPython loads the submodule first, so there the
  rule closes an edge that would be right, as ruled.
- **E6-4, pytest's `rootdir` insertion (A-5).** For a test-classified
  importer, every directory from its own up to and including the first
  ancestor without `__init__.py` (pytest's `basedir`, `prepend` mode) may
  come first on `sys.path`, stopping at the root: a first component found in
  any of them gives `script-dir-shadow`, and writes from that importer name
  those directories' modules too.
- **E6-5, patcher targets (A-6, B-S1).** A closed list of callees: `patch`
  from `unittest.mock`/`mock` (`mock.patch`, a pytest-mock fixture's
  `.patch`, a bare `patch`), `X.patch.object`/`.dict`/`.multiple`, and
  `setattr`/`delattr` on a receiver whose name contains `monkeypatch`. A
  target string that is not a constant (`mock.patch(f"svc.{n}")`,
  `monkeypatch.setattr(n, f)`), and a `patch.object` attribute that is not
  one, is an `unresolvable-writer` cause, scoped by O-2. A constant target
  taints the module it names wholly (`patch.multiple('svc', t=o)`), besides
  the dotted-string rule. `requests.patch(url)` is not on the list.
- **E6-6, write chains (B-S2).** A write through an attribute chain rooted at
  an imported module taints the chain's first attribute (`svc.t.__code__ =
  o.__code__` taints `svc.t`).
- **E6-7, safe reads (N1, A-S2).** A plain read of a module's `__path__`,
  `__spec__`, `__file__`, `__name__` or `__doc__` is a safe use, not an
  escape; `__path__` stays a run-wide `module-system` cause.
- **E6-8, cost and cleanup.** The Python module facts are computed only in
  `imports` mode; `structural` and `name` records carry empty tables, as on
  main, and an `imports` assembly given a file without them treats it as
  `unparsed-file`. A submodule name the collector skips for directories
  (`pkg/build.py`) counts as a submodule (S-1). Panel B's 20 surviving
  mutations are killed or recorded as equivalent in the mutation script.

**Fold 3 (the president's review P6-1..P6-4 and N-1 on #705).** Each rule
only adds `none`. Every row is the president's tree, with what CPython 3.14
or pytest ran (`test_fold3_president_cases_keep_their_off_mode_edge`).

- **P6-1, own-submodule imports by full name.** An import in a package
  `__init__.py` is an import of its own submodule only as `from . import b`
  or `from <the package's full dotted name> import b`. `from vendor.utils
  import timezone` in `myapp/utils/__init__.py` binds the vendor module; the
  later `from myapp.utils import timezone` finds that attribute and never
  loads `myapp/utils/timezone.py` (`h10_django_like`, `h1_own_sub_lastpart`:
  `attr-submodule-conflict`). Fold 2 compared only the last component.
- **P6-2, a star import leaves no own-submodule name.** An `__init__.py`
  with any star import records no own-submodule names, and the assembly
  also refuses one there (`not file.stars`): `from .c import *` after `from
  . import b` rebinds `b`, and the submodule already in `sys.modules` is
  never set again (`h9_star_rebind`).
- **P6-3, patchers follow the Tier 1 W-3 aliases.** Which callee is `patch`
  is decided at the use site by the Tier 1 alias sets (the mock-module
  names, the `patch` names and every local alias of the mock module,
  `patch` or a pytest-mock fixture), besides the literal spellings of E6-5:
  `from unittest import mock as m` … `m.patch(...)` (`h3a`), `from
  unittest.mock import patch as p` … `p(...)` (`h3b`). A `MonkeyPatch` is
  any name containing `monkeypatch` (any case) and, to a fixpoint, a name
  bound from one by assignment, walrus or `with … as` (`mp = monkeypatch`,
  `h6`). A first argument of `patch.multiple`/`patch.dict` that is not a
  constant string is an `unresolvable-writer` cause, as for `patch`
  (`h3c`). An object target (`patch.dict(os.environ, …)`) cannot be told
  from a computed string, so it fails closed too; on the measured trees
  that adds one test-scope cause in pmcp (whose tests already had causes)
  and changes no count. `requests.patch(url)` stays unaffected.
- **P6-4, pytest's basedirs for the whole run.** For a test-classified
  importer or writer, the directories that may come first on `sys.path` are
  its own chain (E6-4) and the basedir of every file pytest imports while
  collecting (`test_*.py`, `*_test.py`, `conftest.py`), each the first
  ancestor without `__init__.py`, computed once per run: `tests/conftest.py`
  puts `tests/` first for a test in `tests/unit/` (`h4_conftest_basedir`:
  `script-dir-shadow`). Without the conftest (`h4b`) the import resolves as
  before. Both `resolve_module` and `_Builder.starts` use the set.
- **N-1, function code writes are a cause.** A write of a function's
  `__code__`, `__closure__`, `__defaults__` or `__kwdefaults__` in any file
  (any receiver, or by constant name) is a run-wide `module-object` cause,
  scoped by O-2: `f = svc.t; f.__code__ = other.t.__code__` made CPython run
  `OTHER.t` for `use.py`'s proven `from svc import t` (`h5_code_alias`). Its
  measured cost on the four trees is 0 (each already has a production
  `module-object` cause).

**Fold 4 (the president's re-check P6-5..P6-9; executive ruling E6-9).**
E6-9 reuses Tier 1's E-21 closed allow-list for patcher values, so this class
stops recurring; every rule only adds `none`.

- **E6-9 / P6-6, `MonkeyPatch` is a patcher kind** beside Tier 1's mock
  module, `patch` and `mocker`. Its class is any name `from pytest import
  MonkeyPatch` or `from _pytest.monkeypatch import MonkeyPatch` binds (in any
  alias), the bare name and any `X.MonkeyPatch` attribute (so every alias of
  either module); an instance is the `monkeypatch` fixture, `MonkeyPatch()`,
  `X.context()` on either, and every name bound from one by assignment,
  walrus or `with … as`. Fold 3's substring rule is gone. Its closed
  allow-list: `setattr`, `delattr`, `setitem`, `delitem`, `setenv`,
  `delenv`, `syspath_prepend`, `chdir`, `undo` and `context` called on an
  instance, `MonkeyPatch()`/`MonkeyPatch.context()` called on the class, a
  binding position, an annotation and an alias binding.
  `from pytest import MonkeyPatch as MP; m = MP(); m.setattr(f"svc.{N}", …)`
  ran `OTHER.t` under pytest (`f3_mp_from_import`).
- **E6-9 / P6-5, patcher values off the allow-list.** In a test-classified
  file, any use of a patcher value (the mock module, `patch` and `mocker`,
  decided by Tier 1's alias sets and its `_safe_use`, and `MonkeyPatch`) off
  its allow-list is an `unresolvable-writer` cause, scoped by O-2: an
  argument (decorator arguments included), a container element, `return`
  or `yield`, `functools.partial`, an assignment the alias sets do not
  track. pytest ran `OTHER.t` for `run(patch)`, `@deco(mock.patch)`,
  `[mock.patch][0](…)`, `functools.partial(patch, …)` and
  `helper(monkeypatch)` (`f3_patch_as_arg`, `f3_patch_decorator_arg`,
  `f3_patch_list_escape`, `f3_patch_partial`, `f3_mp_param`). Allowed calls
  with constant targets keep their exact taints. (Fold 4 left production
  files out; E6-9a, below, withdraws that.)
- **E6-9 / P6-7, fixtures by name.** `request.getfixturevalue('<name>')`
  with `monkeypatch` yields a `MonkeyPatch`, and with a pytest-mock fixture
  name (`mocker`, `class_mocker`, `module_mocker`, `package_mocker`,
  `session_mocker`) a fixture whose `.patch` is `patch`
  (`f3_mp_getfixture` ran `OTHER.t`). A computed fixture name is an
  `unresolvable-writer` cause, scoped by O-2.
- **P6-8: no change.** It is off-mode behaviour (§15 R12, Python, PR 6).
- **P6-9 (method).** The Boundary IR hash includes the checkout's absolute
  path, so head-vs-main comparisons are run from one path.

**Fold 5 (the president's re-check P6-10..P6-16; executive ruling E6-9a).**
Every rule only adds `none`.

- **E6-9a / P6-13, the patcher-escape scan runs in every Python file.**
  Fold 4 said production files needed none because Tier 1's E-21 makes the
  hand-off file dynamic. That holds only for the file's own lookups: the
  hidden write still reaches another module. Production `main.py` ran
  `OTHER.t` after production `app.py` did `run(patch)`,
  `helper(pytest.MonkeyPatch())` or `[pytest.MonkeyPatch()][0].setattr(…)`
  (`f4_prod_patch_param`, `f4_prod_mp_param`, `f4_prod_mp_list`). The cause
  stays scoped by O-2 through the file's own classification. The
  `getfixturevalue` rules below apply in every file too, under the same
  scoping; production code does not call `getfixturevalue`. The fixture
  seed is a parameter named `monkeypatch` (as E6-9 says), not the spelling:
  this tool's own local flag `monkeypatch = …` is no fixture. On the measured
  trees the only new production cause is in treesitter-chunker:
  `chunker/call_resolution/py_scope.py`, through Tier 1's own readback rule
  (`mock_names.add("mock")` reads like `getattr(X, "mock")`), which Tier 1
  also applies to that file; it costs no resolved edge.
- **P6-10, `syspath_prepend` is `module-system`.** `monkeypatch.
  syspath_prepend(p)` is `sys.path.insert(0, p)` plus
  `importlib.invalidate_caches()`; pytest ran `shadow/svc.py`'s `t`
  (`f4_mp_syspath_prepend`; the plain `sys.path.insert` control
  `f4_ctl_syspath_insert` was already a cause). It stays on the allow-list
  only so that it is not also an escape.
- **P6-11, MonkeyPatch aliases mirror Tier 1.** An assignment, walrus or
  `with … as` alias is safe only for a binding no computed read reaches
  (Tier 1's `_reachable_binding` is false: a function local, not a module or
  class global or a `global`-declared name). A module-level `MP =
  pytest.MonkeyPatch()` that the test imports (`f4_mp_global_cross`,
  `f4_mp_global_attr`) is now an escape.
- **P6-12 and P6-15, `getfixturevalue` by alias or by name.** An
  `X.getfixturevalue` attribute that is not the callee of a direct call
  (`g = request.getfixturevalue`, `f4_mp_getfixture_alias`), and the
  constant string `"getfixturevalue"` passed to any call (`getattr(request,
  "getfixturevalue")`, `f4_mp_getattr_method`; also `attrgetter`,
  `methodcaller`), count as a computed fixture name: an
  `unresolvable-writer` cause. A plain constant elsewhere names nothing (the
  first fold-5 measurement showed the rule flagging this tool's own
  `_GETFIXTUREVALUE = "getfixturevalue"`; it is now limited to call
  arguments).
- **P6-14, annotations.** A patcher in an annotation is safe only when it is
  the annotation itself or sits in an `attribute`/`subscript`/
  `generic_type`/union chain of it, with no call or argument list in
  between: `def inner(a: helper(monkeypatch))` runs `helper` when the
  annotations are evaluated (`f4_mp_annot_eval`).
- **P6-16: no change** (`chdir`, `setenv`, `delenv` cannot redirect an
  import without a relative `sys.path` entry, every source of which is
  already `module-system`).

**Fold 6 (the president's re-check P6-17..P6-20; executive ruling E6-9b).**
E6-9b ends the MonkeyPatch class structurally: stop proving which receiver
is a MonkeyPatch, and match the method.

- **E6-9b / P6-17, MonkeyPatch methods on any receiver.** pytest hands a
  `MonkeyPatch` out with no seed spelled: `request.node.funcargs
  ["monkeypatch"]` with `usefixtures` or an autouse fixture, a
  `pytest_fixture_setup` hook's value, a closure cell, a frame's `f_locals`
  (its own or a caller's), `locals()`, and `get_type_hints(localns=locals())`
  evaluating a string annotation. pytest ran `OTHER.t` in each of the
  president's eight trees. Every route ends in a spelled method call, so in
  every Python file (causes O-2-scoped by the file's own classification)
  `X.setattr`, `X.delattr`, `X.setitem`, `X.delitem` and `X.syspath_prepend`
  are handled as MonkeyPatch calls whatever `X` is, unless the ordinary
  Tier 1 lookup resolves `X` to the `operator` module:
  - `setattr`/`delattr` string form (two positional arguments; one for
    `delattr`) with a constant target taints the module it names wholly, and
    with any other target is an `unresolvable-writer`;
  - with more positional arguments (the object form, or an unbound
    `MonkeyPatch.setattr(mp, "m.t", v)`), the second one must be a constant;
  - a computed `target=`/`name=` keyword, or a `*`/`**` splat, is an
    `unresolvable-writer`;
  - `syspath_prepend` is `module-system` (P6-10);
  - `setitem`/`delitem` take the mapping as a value, which the #697 use rules
    already classify, so their name adds no cause;
  - the same names as a method reference (`s = mp.setattr`) or as a constant
    call argument (`getattr(mp, "setattr")`, `operator.methodcaller(
    "setattr", …)`) are an `unresolvable-writer` (`module-system` for
    `syspath_prepend`).

  The builtin `setattr(…)` is a bare call and is unaffected. Cost: the tool's
  own `chunker/` and `scripts/` gain no cause; the measured trees gain no
  production cause (§ real-tree outcome).
- **P6-18, `getfixturevalue` by string.** The four string spellings
  (a variable, a loop over a tuple, a concatenation, the class `__dict__`)
  each end in `mp.setattr(…)`, so E6-9b closes them. The `"getfixturevalue"`
  call-argument rule is a best-effort narrowing for pytest-mock fixtures;
  what it misses is named in §15 R12.
- **Removed as redundant.** The MonkeyPatch instance and class kinds of folds
  3–5: the `monkeypatch` parameter seed, `MonkeyPatch` imports in any alias,
  `MonkeyPatch()`/`.context()` results and their alias fixpoint, the
  MonkeyPatch allow-list (its methods, the unreachable-alias rule of P6-11,
  the annotation rule of P6-14), the MonkeyPatch value escape and the
  receiver check in `_scan_patchers`. The pytest-mock fixture-by-name
  tracking stays: `.patch` on an arbitrary receiver is no patcher. Every
  earlier test row stays and passes.
- **P6-19: no change here.** A Tier 1 mock-kind local alias escapes through
  `locals()`, a `nonlocal` cell or a frame (Tier 1 E-21, outside PR 6); the
  executive files the follow-up, and §15 R12 names it.

**Fold 7 (the president's re-check P6-21..P6-26).** One finding, P6-21,
reopened by fold 6: a constant method name was recognised only as a single
string literal passed positionally.

- **P6-21, any constant spelling.** A constant name (a MonkeyPatch write
  method, `syspath_prepend`, `getfixturevalue`) counts in any spelling Tier
  1's `_constant_string` decodes: adjacent literals (also with a comment
  between them), `+` and parentheses, as a positional argument or a keyword
  value. pytest ran `OTHER.t` for `getattr(mp, "set" "attr")`, `getattr(mp,
  "set" + "attr")`, `getattr(mp, ("setattr"))`, the comment-split literals
  and `inspect.getattr_static(mp, attr="setattr")`, and `SHADOW.t` for
  `getattr(mp, "syspath" "_prepend")(…)`.
- **P6-22, subscript keys.** The same constant as a subscript key counts too:
  `MonkeyPatch.__dict__["setattr"]`, `vars(type(mp))["setattr"]` (pytest ran
  `OTHER.t` for both), and the `getfixturevalue`/pytest-mock names alike.
- **Still R12:** a name computed at run time (`M = "setattr"; getattr(mp,
  M)`, the president's `f6p_r1_name_var`, pinned as unresolved by a test).
- The tool's own `chunker/` and `scripts/` gain no cause; the measured trees
  gain no production cause.

**Fold 8 (Codex review r4661935648 on #705).** A module that re-exports an
`import a.b as m` binding resolved `a.b` as a module path, skipping the E6-3
package-attribute check that a direct `import a.b as m` gets. With
`a/__init__.py` doing `from . import b` and then `from vendor import impl as
b`, `facade.py: import a.b as m` and a caller doing `from facade import m;
m.t()`, CPython ran `vendor.impl.t` while the tool proved `a/b.py:t`. The
fix is structural: one resolver per altitude.

- **Proofs: `_resolve_binding`.** Every proof path turns an import binding
  into a value through one function: a direct import in the caller
  (`resolve_import`, for a single import and for each member of an import
  group) and every re-export hop through an intermediary (`_attribute`'s
  import branch, recursively up to the hop limit, so `facade.m`, a two-hop
  re-export and `from facade import m as n` all pass the same checks). It
  applies script-directory and pytest shadowing, standard-library names and
  skipped directories (`resolve_module`, now called only there), and for
  every attribute step `_attribute`'s checks: E6-3 `attr-submodule-conflict`,
  `module-getattr`, P6-1 own imports by full name, the P6-2 star rule, and
  each module's taints (E6-1, E6-2), the intermediary's own taint on the
  re-exported name included.
- **Writer side: `_Builder.module_values`.** The over-approximating twin:
  every run node a module reference may denote, the module path and, for a
  dotted absolute name, the attribute walk through `attr_values`
  (submodules, every import binding of the name, star sources). It now reads
  every `import`-form binding (`binding_values`, so re-exports and the
  whole-taint closure) and every module-object use record (`walk_use`).
  Fold 7 had the same gap there: `import a.b as m; m.t = o` (or `facade.m.t
  = o`) wrote `vendor.impl.t` (CPython ran `OTHER.t` for `use.py`'s `from
  vendor.impl import t`) while only `a/b.py` was tainted.
- **Audit (every place a dotted module path becomes a target):**
  `resolve_import` and `_attribute` → `_resolve_binding`;
  `_Builder.binding_values` (import form) and `walk_use` →
  `module_values`; `_Builder.attr_values` and `exposed` reach bindings only
  through `binding_values`; module-path primitives stay where a module path
  is meant: `from M import …` sources, star sources, literal acquisitions
  (`import_module`/`__import__`/`sys.modules` name `sys.modules` entries),
  O-2 promotion (`_production` walks every prefix and, transitively, each
  intermediary's own imports, so `vendor/impl.py` is reached through
  `a/__init__.py`); dotted constant strings already walk attributes from
  their first component. `own_binding_reason` and `tier1_reason` read the
  caller's own names and follow no binding.
- The analyzer's facts are unchanged (the fix is in assembly), so the
  `python` fact version stays 38 and the digests are unchanged.

**Real-tree outcome (owner decision O-3: shipped as designed).** Python Tier 2
gains nothing on the measured trees. `imports` is compared with `structural`
on git-tracked `.py` files, with Python 3.14, at PR 6 fold 2 and again at
folds 3 to 8 (every resolved, gain and loss count identical; the
treesitter-chunker rows use a copy of the newest head, whose own new code adds
ambiguous edges); each row names
its extraction root (the `sys.path` entry). "ambiguous" counts off-mode
ambiguous Python call edges; "S → I" is the resolved count under
`structural` and then `imports` (gain / lost); "pot" is what Tier 2 would add
with run-wide causes removed (a diagnostic only).

| Tree and root | Files | Prod ambiguous | Prod S → I (gain / lost) | Prod pot | Test ambiguous | Test S → I (gain / lost) | Test pot | Production causes |
| --- | ---: | ---: | --- | ---: | ---: | --- | ---: | --- |
| pmcp: root = repo | 267 | 1772 | 110 → 110 (0 / 0) | 0 | 5580 | 908 → 908 (0 / 0) | 29 | dynamic-loader, evaluator, module-object, module-system |
| pmcp: root = `src/` | 62 | 883 | 63 → 63 (0 / 0) | 1 | – | – | – | dynamic-loader, evaluator, module-object, module-system |
| spec: root = repo | 375 | 4676 | 2410 → 1463 (0 / 947) | 50 | 4026 | 1136 → 1114 (0 / 22) | 0 | dynamic-loader, evaluator, module-object, module-system |
| spec: root = `src/` | 97 | 501 | 200 → 185 (0 / 15) | 6 | – | – | – | evaluator, module-object, module-system |
| treesitter-chunker: root = repo, no fixtures | 852 | 4989 | 412 → 412 (0 / 0) | 59 | 9902 | 1030 → 906 (0 / 124) | 92 | dynamic-loader, module-object, module-system, unresolvable-writer |
| treesitter-chunker: root holds only `chunker/` | 335 | 2896 | 259 → 259 (0 / 0) | 29 | – | – | – | dynamic-loader, module-object, module-system, unresolvable-writer |
| Code-Index-MCP: root = repo | 1111 | 11573 | 279 → 279 (0 / 0) | 8 | 11468 | 797 → 797 (0 / 0) | 6 | dynamic-loader, evaluator, module-object, module-system, unparsed-file, unresolvable-writer |
| Code-Index-MCP: root holds only `mcp_server/` | 290 | 6626 | 103 → 103 (0 / 0) | 7 | – | – | – | dynamic-loader, module-object, module-system, unparsed-file |

Why the gain is zero, and what the losses are:

- **Production causes.** Every tree has genuine production run-wide causes:
  - custom loaders such as `exec(compile(src), module.__dict__)`;
  - `eval(..., vars(module))`;
  - plugin loading with `importlib.import_module(name)` and a computed
    `getattr`;
  - `sys.path` inserts in scripts;
  - `sys.modules[__name__] = …`.
- **Small upside.** Even with the causes removed, Tier 2 would add 0 to 92
  edges per tree. Most ambiguous Python edges are member calls
  (`self.x()`, `obj.x()`), which Tier 2 never touches.
- **Losses: potential writes the rules cannot rule out.** The losses are
  #697 taints, which apply to the written module's Tier 1 module-scope proofs
  in `imports` mode. No file of those trees performs such a write. In `spec`,
  the whole −947 (and −22 for tests) comes from three functions that return
  modules (`return intake, intake_graph`; `return spec_graph`; a lazily
  imported `event_ingress`), repeated in its two bundled copies, plus the
  exposure closure over what those modules import. Tracking returned modules
  through call results is follow-up N2 (treesitter-chunker#706).
- **Code-Index-MCP.** Its earlier −39 came from one read of
  `mcp_server.__path__`. E6-7 makes that read safe, so the loss is now 0.

**Cost (E6-8).** These figures are facts-extraction wall time for git-tracked
`.py` files on a shared host. Before fold 2, `structural` paid for the Tier 2
module facts; it no longer does:

| Tree | Mode | Before fold 2 | `module_facts` before | After fold 2 | `module_facts` after |
| --- | --- | ---: | ---: | ---: | ---: |
| spec | `structural` | 8.8 s | 2.2 s | 6.3 s | 0 s |
| spec | `imports` | 8.9 s | 2.4 s | 9.0 s | 2.5 s |
| Code-Index-MCP | `structural` | 26.9 s | 5.9 s | 20.9 s | 0 s |
| Code-Index-MCP | `imports` | 27.2 s | 6.0 s | 27.7 s | 6.6 s |

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
| probe | use.ts:2 user → t | amb {svc.ts t, svc.tsx t} | = (import) | = | ambiguous-extension (O-1 (a), owner decision) | 5 |
| probe (py root) | c.py:4 use → helper | amb {a.py helper, b.py helper} | = (import) | **resolved a.py helper** | t2.import | 6 |
| probe (py root) | pkg/__init__.py:5 call_k → k | amb {pkg.py k, pkg/__init__.py k} | **resolved pkg/__init__.py k** | = | t1.lexical | 4 |
| probe (py root) | redef.py:11 caller → d | amb {d@1, d@4} | = | = | group = C0 | 4 |
| probe (one root) | py/c.py:4 use → helper | amb {py/a, py/b} | = | = | script-dir-shadow (`a` resolves inside the non-root directory `py/`; 9.5) | 6 |
| probe (one root) | py/pkg/__init__.py:5 call_k → k; py/redef.py:11 caller → d | as the py-root rows | as the py-root rows | = | Tier 1 does not depend on the root (PR 4) | 4 |

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
| builtin-shadow | `test_builtin_shadow_end_to_end` in `tests/test_call_resolution_tier1_py.py`, on a tree the test writes (11.2) |
| expression-bound | js-var-fn; Python decorated definitions (`test_decorated_definitions_keep_their_off_mode_edge`, on trees the test writes) |
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
| enum-scope | `test_enum_scope_end_to_end` and `test_lookups_inside_an_enum_body_fail_closed` in `tests/test_call_resolution_tier1_js.py`, on trees the tests write (a committed tree would change the off-mode baseline, 11.2) |
| no-binding-fact, unmapped | named synthetic-facts tests (R-3; listed below the table) |
| unsupported file | named end-to-end failure-mode tests (R-3; listed below the table) |
| escaped names (unsupported file, 5.3) | `test_escaped_names_end_to_end` in `tests/test_call_resolution_tier1_js.py`, on trees the test writes (11.2) |
| TS `using` / `await using` (fail closed, 7.5) | `test_using_near_miss_end_to_end` in `tests/test_call_resolution_tier1_js.py`, on a tree the test writes (a committed tree would change the off-mode baseline, 11.2) |
| stub, script-goal-deferred, namespace-deferred | interim heads only (PR 1, PR 2); PR 3 drops the latter two from the vocabulary and PR 4 drops `stub` |
| script-global, namespace-merged, t1.js_hoist, inherited ambient (PR 3) | also `test_script_global_end_to_end`, `test_script_global_controls_end_to_end`, `test_js_hoist_end_to_end`, `test_js_hoist_near_misses_end_to_end`, `test_namespace_merging_end_to_end` and `test_inherited_ambient_end_to_end` in `tests/test_call_resolution_tier1_js.py`, on trees the tests write (11.2) |
| Python fail-closed classes (PR 4): write forms, dynamic binding, decorated definitions, non-ASCII identifiers (unsupported file, 5.3) | `test_write_forms_keep_their_off_mode_edge`, `test_dynamic_binding_forms_keep_their_off_mode_edge`, `test_decorated_definitions_keep_their_off_mode_edge`, `test_non_ascii_identifiers_make_the_file_unsupported` and `test_python_positives_end_to_end` in `tests/test_call_resolution_tier1_py.py`; the #695 panel fold adds `test_panel_695_cases_keep_their_off_mode_edge` (panel A's runtime-traced wrong cases), `test_natural_unmapped_forms_keep_their_off_mode_edge` (`del f()`, `with a as f():`, `type(x).attr = v`: natural `unmapped` near-misses), `test_line_continuation_target_end_to_end` and `test_builtin_shadow_end_to_end`, on trees the tests write (11.2), with analyzer unit cases in the same module |
| #691 panel classes A1–A6, B5, and the president's B-1–B-3 (PR 3) | `test_panel_691_cases_keep_their_off_mode_edge`, `test_misparsed_blocks_make_the_file_unsupported`, `test_static_constructor_is_not_the_class_constructor` and `test_markdown_and_rst_in_the_run_do_not_count` in `tests/test_call_resolution_tier1_js.py` (its `codex-4652498471`, `bracket-*` and `template-assign` cases pin literal-key callees, and its `M01`–`M12` cases writers through a receiver `this`, with the matching `test_global_object_uses_fail_closed_with_a_wildcard` cases; `test_writer_through_this_in_a_constructor_still_resolves` is the C-1 control); `test_editing_another_file_reruns_the_script_global_check` in `tests/test_call_resolution_cache.py` |
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
| Tier 2 TS/JS fail-closed classes (PR 5): string decoding, specifier forms, suffix siblings, directory `package.json`, export forms, stars, namespace escapes, CommonJS reach | `test_tier2_positives_resolve_end_to_end`, `test_tier2_near_misses_keep_their_off_mode_edge`, `test_other_member_calls_are_not_eligible` and the unit tests in `tests/test_call_resolution_tier2_js.py`, on trees the tests write (11.2); the `imports` fields of the expected tables (`test_expected_imports_tables_hold_at_this_head`) |
| Tier 2 Python (PR 6): import bindings, module paths, name lookup, member chains, import groups; #697 writes and escapes; run-wide causes; parse classification; O-2 | `test_tier2_positives_resolve_end_to_end`, `test_tier2_near_misses_keep_their_off_mode_edge`, `test_other_files_writes_fail_closed` (the #697 route table), `test_run_wide_causes_fail_closed`, `test_unparsed_files_are_a_run_wide_cause`, `test_test_classifier_is_closed_and_case_sensitive` and the O-2 tests in `tests/test_call_resolution_tier2_py.py`, on trees the tests write (11.2); the PR 6 `imports` fields of the expected tables |

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
| M15 | A changed edge whose `provenance.call_resolution` is not the run's mode (PR 5, `imports` pairs) | 2, 7 |

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
| **5** | **Tier 2 TS/JS.** Introduces `imports`. Applies the owner's O-1 decision (a). | PR 5 rows |
| **6** | **Tier 2 Python.** Closes treesitter-chunker#682 and #697. Keeps the experimental label (owner decision O-4). | PR 6 rows |

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
| **O-1** | **Decided by the owner: (a)** (relayed by the executive for PR 5). When `./svc` matches more than one file (for example `svc.ts` and `svc.tsx`), toolchains disagree: tsc and Vite pick `svc.ts`, esbuild and Bun pick `svc.tsx`. **(a), decided:** leave the edge unchanged (`none(ambiguous-extension)`); the probe `use.ts` call stays ambiguous. Resolve only when exactly one file variant exists. Rejected: (b) pick `svc.ts` by TypeScript's order; (c) as (b), tagged `t2.import_ext_order`. | **Closed.** PR 5 applies (a): the probe `use.ts` row, the ts-ext-collision rows, js-importer-ext-order `use2` and ts-dts give `ambiguous-extension`. |
| **O-2** | **Decided by the owner: "scope by caller"** (relayed by the executive for PR 5 fold 2). Test code never runs in production but can rewire modules at test time. | **Closed.** Run-wide causes and per-module taints from test files fail closed only edges whose caller is a test file; production causes and taints affect every caller. The classifier is closed and path-based, and production reachability promotes test files (9.9). |
| **O-3** | **Decided by the owner: ship PR 6 as designed** (fold 1 on #705). Python Tier 2 gains nothing on the measured trees and loses `structural` resolutions where other files may write a module. | **Closed.** Recorded in 9.10 and the PR 6 description; the gain table is in 9.10. |
| **O-4** | **Decided by the owner: keep the experimental label** on `structural` and `imports` (13.1 had offered to remove it in PR 6). Real-code precision has not been measured. | **Closed.** 4.5 and 13.1 updated; CLI help, docstrings and CHANGELOG keep "experimental". |
| R1 | The analyzer misses a binding form | Fail closed; the allow-list test (7.5). |
| R2 | JS goal detection. CommonJS files stay script goal (a top-level `require(` also occurs in AMD browser scripts). | Accept. Misclassification only adds `none` through the script-global check; hoisting behaves the same inside a CommonJS wrapper. |
| R3 | A third parse per file when on | Opt-in only. Record timings in each PR. |
| R4 | Edge reordering in Boundary IR | Documented; consumers key on `id`. |
| R5 | Baseline regeneration | Replaced by the 11.2 process. |
| R6 | A directory's `package.json` changes TS resolution | Accept. The NIT to record such directories is **rejected** (A14): `package.json` is not a collected file, so reading it would make per-file facts depend on a file outside the cache key. |
| R7 | Python extension modules shadow `.py` | Accept. |
| R8 | Interim behavior between PRs | Experimental label, plus a per-head CHANGELOG statement (4.5). |
| R9 | Scripts outside the run can redefine a global: HTML-included scripts outside the run, `dist/`, `node_modules`, `.mjs` and `.cjs` files, inline `<script>` in `.vue` and `.svelte` files (none of these is collected), and raw HTML in Markdown or reStructuredText that a site generator renders, which, like any generated page, is outside the run | Accept: they are not scanned. In-run HTML, XML and PHP files count as declaring every global (PR 3). |
| R11 | Global writes no syntactic rule sees (PR 3): a strict function (an ES-module function or class method) that receives the global object as `this` through a call the analysis cannot see, beyond what the `this.x =` rule covers (for example an alias of `this` handed on: `const s = this; s.d = f`); open-ended references to the global object (`event.view`, `getGlobal()`); and string-code paths (`require('vm').runInThisContext`, `document.write('<script>…')`, `importScripts`, DOM script injection, inline event handlers). Named examples: a computed call on a receiver `this` that may be an indirect `eval` (`this[k](s)`, `this['ev' + 'al'](s)`; `*` would switch off script-top resolution in about 52 of 1136 npm files); hand-offs of a receiver `this` through a variable or an expression (`const s = this; s.d = f`, `const w = this.window; w.d = f`, `(0, this).d =`, `(c ? this : o).d =`, `(c || this).d =`, the receiver argument of `Reflect.set(o, 'd', v, this)`, `Object.assign(...[this], …)`), except `Object.assign`/`Object.defineProperty`/`Reflect.set(this, …)` with `this` first, which give `*`; `Reflect.get(f, 'constructor')`, and computed keys that may reach `constructor` on arbitrary objects (`x[k](s)`, `x['constr' + 'uctor'](s)`, `f[['constructor']](s)`, `const { [k]: F } = f`); writer hand-offs the analysis cannot identify syntactically (`const a = Object.assign; a(this, …)`, `Function.prototype.call.call(Object.assign, null, this, …)`, `Reflect.apply(Object.assign, null, xs)` with a non-literal argument list, `Object['assign'](...[this], …)`, a conditional writer `(c ? Object.assign : f)(this, …)`, and a helper given `this`: `h(this)`; comma and parenthesized writers before `.call`/`.apply`/`.bind`, bound writers called later and `Reflect.apply` with a literal argument list give `*` since treesitter-chunker#694; not seen at that head either: a comment inside the parentheses around a writer, its namespace or its target (`(/* c */ Object.assign).call(null, this, …)`, `(/* c */ Object).assign(this, …)`, `Object.assign((/* c */ this), …)`), a bound writer returned through an invoker (`Object.assign.bind.call(Object.assign, null)(this, …)`), an invoker's explicit receiver as the writer (`Object.keys.call.call(Object.assign, null, this, …)`), a destructured writer (`const {assign} = Object; assign(this, …)`), a non-literal `.apply` argument list (`Object.assign.apply(null, arguments)`, an array-like `{0: this, 1: …, length: 2}`), spread inside a literal argument list (`Object.assign.apply(null, [...[this], …])`), legacy accessors (`this.__defineGetter__('d', …)`, also through a comma, `.call` or `Object.prototype.__defineGetter__.call(this, …)`), and `Object.setPrototypeOf(this, …)`, which writes the global object's prototype; an own declaration still wins there, so it gives no wrong edge today) | Accept: script-goal resolution holds within what the run's files show syntactically (§7.2). |
| R10 | Python monkeypatching (`import a; a.d = x`, `setattr(a, "d", …)`, `mock.patch("a.d")`) | **Closed for `imports` mode by PR 6** (treesitter-chunker#697, 9.10): named writes, escapes, literal acquisitions and dotted strings in any run file taint the written names or modules, and a taint fails Tier 2 proofs and the module's own Tier 1 module-scope proofs. `structural` stays as on main (byte-identical), so there it remains accepted. **Residual (executive ruling on #705, Q1; treesitter-chunker#699):** a writer whose target module cannot be determined (a non-literal loader, such as `exec(src, mod.__dict__)` with `mod` from a computed import) is a run-wide cause, which shuts off Tier 2 only; it can still invalidate a Tier 1 proof in `imports` mode, as in `structural`. |
| R12 | Python run-time binding no syntactic rule sees (PR 4). **Scope rule** (executive decision, #695 re-check at 606c689f): in Tier 1 Python, a wrong resolved edge in the same file blocks if it can be produced using only names or constant strings that appear in the file, through ordinary binding, attribute or call semantics. Reflective access to interpreter internals is treated differently: that is, objects obtained by introspection rather than spelled out, such as `gc` referents, `inspect.getmembers`, `dir()` plus `getattr`, code objects from `dis`/`monitoring`, frames, and the builtins module reached via `__self__`/`__builtins__`. Such a route gets a trigger when a small one closes it. Otherwise it is named here, filed as a follow-up issue (treesitter-chunker#699), and does not block. **String-code execution through stdlib helpers** is the `exec` family by another name and stays here, like the JS string-code paths of R11 (executive ruling at the 8fd7c1a2 re-check, P-4; treesitter-chunker#699): a constant program a library runs, for example `cProfile.run('helper = len')` and `cProfile.runctx`, `profile.run`, `bdb.Bdb().run`, `trace.Trace().run`, `timeit.timeit('import __main__ as m; m.helper = len')`, `code.InteractiveInterpreter().runsource(…)`, `doctest.testmod()` on the file's own docstrings, and `pickle.loads(b'c__main__\n__dict__\n.')` or `pickle.loads(b'cbuiltins\n__dict__\n.')`. Also here: a third-party module that re-exports `builtins` under another name (the stdlib's one alias, `enum.bltns`, is a trigger; treesitter-chunker#699). Named by the re-check at 14e8f044 (Q-4, Q-7; treesitter-chunker#699): a resolver given a module name taken from `X.__module__`, a computed string (`pydoc.locate(int.__module__).__dict__.update(D)`, `mock.patch(run.__module__ + '.helper', len)`); and `annotationlib.ForwardRef.evaluate` or `typing.evaluate_forward_ref` on a constant string, which is the string-code family above. Named by the re-check at a6734480 (S-4; treesitter-chunker#699): a class with a catch-all `__getattr__` handing a function to `functools.update_wrapper`/`wraps`, whose `__annotate__` copy `annotationlib` then runs under substitute globals (the member name is computed, so no trigger is spelled). Routes that cannot change a proven binding, by the Codex 4655078224 audit: parameter defaults (`__defaults__`, `__kwdefaults__`; parameter lookups never prove); `__func__` (read-only; a rebinding through the function it yields still needs a code object or a cell); `__wrapped__` (introspection metadata only); frames from `sys.settrace`/`setprofile`, `inspect.currentframe`, `sys._getframe` and `sys._current_frames` (`inspect.getgeneratorlocals`/`getcoroutinelocals`/`getasyncgenlocals` and `getargvalues(frame).locals` return the live `f_locals` proxy and are triggers, #695 P-3b; so is `pdb.Pdb().curframe_locals`, #695 Q-3; other frame routes rebind only through `f_locals`/`f_globals`/`f_builtins`/`f_code`, all triggers, or through a computed attribute name, which stays here: `[v for k, v in inspect.getmembers(fr) if k.endswith('_locals')][0]['helper'] = len`, or the same with `dir()` plus `getattr`); any C extension module other than `ctypes`. `__self__` is not such a route: `len.__self__` is the `builtins` module, which is writable, so `__self__` and `__builtins__` are dynamic attributes in every spelling (#695, PR 4 finding O-3b). Heap walking (`gc.get_referents`/`get_referrers`/`get_objects`) gets no trigger (it would cost panel A's correct `gc_referrers` resolution) and stays here under `gc` tricks, among them a gc-found globals dict written with a spelling the attribute-write rule does not list (`g = [o for o in gc.get_referents(run) if type(o) is dict][0]; g.update(D)`) and gc-found code or cells run under `type(f)(…)`. Named by the re-check at 606c689f (PR 4 findings O-3, O-5): computed-name member walks on functions and frames (`inspect.getmembers`, `dir` plus `getattr`); a function rebuilt with a positional closure tuple (and code) taken from `gc` or `inspect.getmembers` (`type(invoke)(code, {}, None, None, cells)`, with no `closure=` keyword); `runpy` re-running the file (`runpy.run_path(__file__, init_globals={'helper': len}, run_name='x')`); recompiling or unmarshalling the file's own source (a second instance of the module); and a same-file `gettext.install()` ahead of a module-level definition that has not run yet. Also: a helper in another module that writes its caller's globals or locals through frames (`sys._getframe(1).f_globals` or `.f_locals` there, not here; #695 panel A2) or `exec(code, mod.__dict__)`; computed strings beyond constant literals (`'__glo' + name`); `X.modules` uses other than `X.modules[__name__]` and its getters (`m = collections._sys.modules; m[__name__]`); `gc` tricks, and C-level access other than through `ctypes`/`pythonapi`; replacing a function's `__code__` (the edge still names the right definition, which then runs other code). Named by the president's #695 ruling (section 4): same-file resolvers that take the module name as a value, `pkgutil.resolve_name(__name__).helper = len`, `pydoc.locate(__name__).helper = len` and `mock.patch(__name__ + '.helper', len)` self-patches; other computed strings (`'%s' % …`, `b'…'.decode()`, including `b'__main__.helper'.decode()`, and an f-string with an interpolation and a `__main__` part, `f'__main__.{h}'`; #695 L-2); `X.modules[__spec__.name]` and other `X.modules` keys, including through a `sys` class attribute or alias with a computed key (`K.ss.modules[k]`, `getattr(K, '_K__s').modules[k]`); `from sys import __dict__ as sd` with a computed key (`sd[''.join(['mod', 'ules'])][k]`; #695 J-3); **cross-file submodule rebinding** (another module importing `pkg.X` sets `pkg/__init__.py`'s global `X` with no write in any source of `pkg/__init__.py`); **builtins injected from another module** (`gettext.install()`, or `builtins.X = …` elsewhere) ahead of a module-level definition that has not run yet, also an R10 item for the deferred follow-up. Also: reaching the module without spelling its name by iterating a package's namespace (`for m in pkg.__dict__.values()` (which fails closed since fold 24), `inspect.getmembers(pkg)`, `pkgutil.iter_modules`, and `g(**pkg.__dict__)`). Named by the re-check at f7f0b0bd (R-5); same-file writes through these in the spellings the attribute-write rule lists (§7.3) fail closed. Fold 18 (executive ruling) moved the former "other write spellings" out of here: writer aliases, `operator.setitem`, `|=` and non-literal `update()` on a namespace dict now fail closed (§7.3). **Computed writes are closed at the write site** (fold 19, executive ruling E-19, which withdraws E-18b): a writer with a computed name on any receiver (W-1), a namespace dict that escapes (W-2) and a `unittest.mock` or pytest-mock patch with a computed target (W-3, extended to receiver-based patchers in fold 20) fail closed (§7.3), so the module or namespace acquisitions this entry names (resolvers given the module name as a value or `X.__module__`, `X.modules` with a computed key, iterating a package's namespace, a module handed over) matter only together with a write, and every write **spelled in this file** is either recorded (a constant name, on any receiver) or fails closed (narrowed by E-20). **What stays here for writes** is reflective and string-code only: heap walking, computed-name member walks and the other reflective routes above, and string-code execution (P-4); treesitter-chunker#699. **Named by E-20 (fold 21; #699):** attribute writes performed inside library functions on an object handed to them, non-blocking as an analog of P-4 (the writing semantics belong to the library): `functools.update_wrapper`/`wraps` (`update_wrapper(m, types.SimpleNamespace(helper=f), assigned=())`), `argparse`/`optparse` namespaces (`parse_args([...], namespace=m)`, `values=m`), `copy._reconstruct`, pickle's BUILD, and third-party equivalents; ancestor-package acquisition with a computed name (`getattr(pkg, __name__.rpartition('.')[2])` in a package submodule) and iterating a package's namespace; `X._sys.modules` is a trigger since fold 21. Pytest framework patchers under other names (an arbitrary `.patch` parameter, a typed `MockerFixture` parameter, `getattr(mocker, 'patch')`) stay #697/#699. Also here: the module object handed over by another module (a sibling re-export, a function returning it, a parameter); a module loaded under a loader-chosen name (`importlib.util.spec_from_file_location`, `runpy` with a custom name); and by-name submodule loading with a computed name in `__init__.py` (`pkgutil.walk_packages(__path__, __name__ + '.')`), which rebinds a package global with no write in the source. Self-references that spell the module's name are no longer here: they give `dynamic-scope` (#695 panel A7, the ruling's B-4 and the general rule of its re-check) | Accept: Python resolution holds within what the file shows syntactically (7.3). |
| R12 (TS/JS, PR 5) | Tier 2 routes no syntactic rule in the run's JS/TS files sees, under the same scope rule (filed as treesitter-chunker#702): bare-specifier aliases into the run (package self-reference, workspace symlinks, tsconfig `paths`) used to write a module's exports object, since taints follow only relative specifiers; resolution configured outside JS/TS files (`package.json` `browser` maps, bundler aliases and extension lists, tsconfig `rootDirs`, `moduleSuffixes` with a segment on the inert list); uncollected siblings a bundler prefers (`.mjs`, `.mts`, `.cjs`, `.json`; also R9); loader hooks (`Module._extensions`, `register()`), `vm`/`process.binding` string code (the R11 family) and build-time transforms. Fold 1 (E5-6, filed on #702): writers outside the run (files not collected, such as `.cjs`/`.mjs`/`.cts`/`.mts`, or removed by a language filter) and build-output directories such as `.next/` (collection is unchanged, which keeps the off-mode identity). Also named in fold 1: `mainModule`/`getBuiltinModule` reached through a computed property key the analysis reads as unreadable (it gives `evaluator` instead); a local AMD `require` parameter called with a non-literal (only a literal call taints); a saved timer later called with source text (Node rejects it). Fold 2 (O-2): a test-only module the classifier does not name (for example under `e2e/` or `cypress/`) counts as production, so its causes stay run-wide (conservative); a production-only module the classifier names but no production file reaches by a static or literal edge (an entry point loaded by configuration, such as a `test/` server script) is treated as test code, and its causes then reach only test callers. Promotion makes production use of a test-named file through the import graph sound. Fold 4 names the routes it closes by promotion rather than resolution: package `imports` aliases (`#x`), absolute and `file:` specifiers, `import.meta.glob`, and directory symlinks under the root (every test file is then production); a createRequire base other than the file itself (`unresolvable-writer`); and test-framework module mocks outside the closed list (`jest.requireMock`, `vi.importMock` and framework config such as `moduleNameMapper`) stay here. Fold 5 adds: a `fileURLToPath(import.meta.url)` base (not accepted, so it fails closed as an `unresolvable-writer`), and any `data:` or `file:` specifier (uncomputable, so it promotes). Fold 6 adds bare specifiers that reach the run through `node_modules` symlinks (workspace links), on #702. Fold 7 removes Windows 8.3 short names from this list: they are now uncomputable (§9.9). Fold 9 (E5-7) removes the text scan, so no text-scan residual remains: an unparsed JS/TS file is always a cause. Every cheap trigger the PR 5 review and folds 1 and 2 found is closed in §9.1–9.3 and §9.9 | Accept: Tier 2 holds within what the run's JS/TS files show syntactically. |
| R12 (Python, PR 6) | Tier 2 Python routes no syntactic rule in the run's files sees, under the executive scope rule (treesitter-chunker#699): a module named by a computed string with no run-wide trigger in its route (a string-code helper such as `cProfile.run`, already R12); writes performed inside library functions on a module handed to them are escapes here (the module is tainted wholly), but a third-party library that obtains a run module by itself (plugin registries, `entry_points().load()`, Django `import_string` from settings) is configuration outside Python files; writers outside the run (uncollected files, `.pth` files, `sitecustomize`, `PYTHONSTARTUP`); extension modules and `.pyc`-only modules that shadow a `.py` (R7); `builtins` written through a route that spells neither `builtins` nor `__builtins__` (`len.__self__`, which Tier 1 still catches in its own file); raw memory through `ctypes` without `pythonapi`; heap walking (`gc`); a module loaded under a loader-chosen name. Run-wide causes shut off Tier 2 only (as for TS/JS; executive ruling on #705, Q1); a write they may make to a module's globals is the R10 residual. The loader refinement (following an `import_module` result through the shared alias mechanism) is a possible future narrowing on #699 (ruling Q3). Fold 2 named a code-object or closure write through an object no module chain reaches (`f.__code__ = …` on a parameter, or a local alias `f = svc.t; f.__code__ = …`); since fold 3 (N-1) a write of `__code__`, `__closure__`, `__defaults__` or `__kwdefaults__` in any file is a run-wide `module-object` cause, so it is no longer here. Fold 2 also names: files CPython rejects but tree-sitter accepts (non-UTF-8 bytes in a comment, zero-width characters, a raw line break in a string; such a file cannot be imported, so no edge in it runs); and module objects handed back by functions (`return intake, intake_graph`), whose tracking through call results is the follow-up N2 (treesitter-chunker#706). Computed patcher targets are no longer here: they are an `unresolvable-writer` cause (E6-5). Fold 3 names: pytest `pythonpath`, `rootdir` and `python_files` settings and `importmode` other than `prepend` (tool configuration; the basedirs follow pytest's default file names), and a `MonkeyPatch` held in an attribute (`self.mp.setattr(...)`), alongside the framework patchers under other names in R12 (PR 4). Fold 4 named the `pytest` or `_pytest.monkeypatch` module object handed on (fold 6, E6-9b, matches MonkeyPatch methods on any receiver, so that no longer matters for MonkeyPatch), and, as an **off-mode residual outside PR 6** (P6-8), a star import in a package `__init__.py` under a condition, in `try` or through a relative middle module that rebinds a submodule name: with no other definition of the name, off mode already resolves the call to the submodule and `structural`/`imports` must keep it byte-identical (decision `None`, Tier 2 never consulted), while CPython runs the star-imported object. Fold 6 names the remaining string-lookup family: a pytest-mock fixture or a `patch`/`mocker` method obtained by a name built at run time (`getattr(request, FN)`, `"getfixture" + "value"`, a class `__dict__` lookup, `getattr(mocker, n)`); the `"getfixturevalue"` call-argument rule is a best-effort narrowing (MonkeyPatch methods are matched by name since E6-9b, in any constant spelling since fold 7, P6-21/P6-22: a positional argument, a keyword value or a subscript key, as adjacent literals, `+` or parenthesized; the residual is a method name computed at run time: `M = "setattr"; getattr(mp, M)`, `getattr(mp, "set" + suffix)`, or a constant that reaches the lookup through a binding, a default, a loop/match target, a splat or a container index, or through `%`/`format`/`join`/`decode`). Also named (P6-19, a Tier 1 E-21 gap outside PR 6, follow-up filed by the executive): introspection (`locals()`, frames, closure cells) makes a function-local mock-kind alias reachable. A file that hands out its own namespace (`helper(globals())`, `helper(locals())`, its own `f_globals`, `fn.__globals__`, `inspect.getmodule(fn)`, `__import__(__name__)`, a string annotation under `get_type_hints`, a one-argument `exec`) is not here: since treesitter-chunker#724 every import binding of such a file is an escape (§9.10); since R-724-1 the trigger is any token that spells a namespace-reaching name, so `exec(code, d)` with `d` holding `None` at run time is closed too. Still here (R-724-1 item 5): another module reading this file's frame (`sys._getframe(1).f_globals` or `inspect.currentframe().f_back.f_globals` there; #699 PY-9), including code that an R-724-2 exempt `exec(code, X.__dict__)`, `loader.exec_module(X)` or `__import__(K)` runs, which may read its caller's frame like any callee; a function handed to another file, which reads `fn.__globals__` there (`helper.patch(svc.u)`, then `fn.__globals__["t"] = f`); another file's `import __main__`, which reaches the script's namespace; a builtin handed back by another file (`def get(): return eval`); heap walking (`gc.get_referrers`); a module name computed from `K.__module__`; and `typing.TypedDict` string annotations evaluated through `ForwardRef.evaluate()`, the string-code family. A handed-out `sys` or `importlib` (`d["sys"].modules["svc"].t = f`) is a run-wide cause, so a Tier 1 proof it reaches is the R10 residual. Named by R-724-4 (the Fable re-check of treesitter-chunker#726 at c387c7ee; #699), each wrong under CPython 3.14 and on main too: the **cross-file-patch** family, in which another file rebinds or patches the fresh-module factory (`types.ModuleType = fake`, `setattr(types, "ModuleType", fake)`, `mock.patch("types.ModuleType", fake)`, `importlib.util.module_from_spec = fake` in `helper.py`), or a run file named `types.py` shadows the standard module, because the factory proof reads one file (trees x03, x03b, x04, x04b, x05); the **loader-chosen-name** family, a second copy of the file run by an exempt use, which holds the same imported modules (`exec(open(__file__).read(), mod.__dict__)`, `spec_from_file_location(n, __file__)` or `find_spec(__name__)` and then `loader.exec_module(probe)`, the code string `"import use; use.svc.t = …"` under an exempt `exec`, the same loader on another importer's file, and `runpy.run_path(__file__)["svc"]`; x09d, x09e, x10, x10b, x10c, t48); a receiver's `__class__` set through a computed name (`setattr(mod, k, M)`); and the S-3 routes no kept token closes: `dir(fn)` with a computed `getattr` and `type(f).__dict__` descriptors (t07, t07b; computed name), the builtins dict reached through `__self__` (`len.__self__.__dict__.items()`, t11; a `__self__` token would cost the route rule's precision, and `__self__` is a route already), a listed name built by a string method or a bytes literal (`" __globals__ ".strip()`, `"__globals__ get".split()`, `b"__globals__".decode()`; t19b, t19c, t28d; computed name), `functools.singledispatch().register` on a string annotation and `fn.__code__ = compile(…)` (t17b, t26; string code), pickle payloads naming `builtins.globals` or the file's own attribute (t24, t24b; the pickle family above), `gc` with `type(sys)` (t12; heap walking), `__init_subclass__` reaching the module through `cls.__module__` (t16; a `K.__module__` computed name), and `X.__dict__.update(OWN.__dict__)` with `OWN` iterated out of `sys.modules` (x08b; that acquisition needs no token and is the R10 residual). A file with a non-ASCII identifier records no Tier 2 facts (`supported: false`), so its writes are invisible; that predates #724 and is filed separately. pytest's `request.module` is a trigger, but a test file's hand-out reaches only test modules' proofs (O-2). | Accept: Tier 2 Python holds within what the run's Python files show syntactically. |

**Owner notice** (informational, from the ruling): these are delegated
decisions, all stricter than or consistent with the issue:

- JS hoisting resolves to the last declaration;
- Python redefinitions never resolve;
- kind or family filtering alone never resolves an edge;
- extension collisions give `none` (O-1 decided (a) by the owner).

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

### PR 2: the president's treesitter-chunker#689 ruling

| Item | Applied in |
| --- | --- |
| B-1: lookups inside a TS enum body | §7.2 scope list (enum body, `none(enum-scope)`); §7.6 reason table and precedence item 1; §10.6 enum-scope row |
| Nit: eval wording | §7.2 fail-closed bullet ("the lookup chain meets a scope that contains a direct `eval(...)`") |
| Nit: overload row layout | §7.4 table (the fallback has its own row) |

### PR 2: Codex review of treesitter-chunker#689 (escaped names)

| Finding | Applied in |
| --- | --- |
| Unicode-escaped names compare by source spelling (comment 4649197239) | §5.3 (an escaped name makes a JS/TS file unsupported); §10.6 row |

### PR 3: hoisting and globals (fail-closed refinements)

`t1.js_hoist` lands in its own commit (js fact version 4), so it can be
reverted alone. The other items tighten §7.2 without changing any expected
row; each only adds `none`.

| Item | Applied in |
| --- | --- |
| `t1.js_hoist`, its own rule ID | §7.4 JS row; §8; §10.2 rt-js and §10.3 js-hoist-fnbody final |
| Global-object writes beyond `window`/`globalThis`/`self`, the wildcard `*`, unsupported files as `*`, same-file writes as `reassigned` | §7.2 script goal |
| Mapped `arguments` aliasing | §7.2 reassignment |
| Namespace merging counted per declaring scope; enums, dotted names, `declare module` and `declare global` always merged; exported namespace `const` is `expression-bound` | §7.2 TS namespaces |
| Ambient status at any depth under `declare`; `ambient` before `namespace-merged` | §7.2 ambient status |

**Reverting `t1.js_hoist`.** Reverting the hoisting commit alone leaves a
consistent tree: rt-js and js-hoist-fnbody go back to their pre-hoist rows
(rt-js ambiguous over k.js:3 and k.js:6, js-hoist-fnbody narrowed to the two
`g.d` declarations), which then contradict §8 and §10 until the plan is
amended. The revert must take a new, higher `js` fact version: **a version
number is never reused**, so no on-mode cache record written under one set
of facts is read under another. The digest test rejects a version decrease.

### PR 3: #691 panel fold

Every item only adds `none`; no expected row changes. `js` fact version 5.

| Item | Applied in |
| --- | --- |
| A1: a statement-level object literal (misparsed labelled block) makes the file unsupported | §5.3 |
| A2: implicit globals count in any JS/TS file | §7.2 script goal |
| A3: exported module-level namespaces are always merged (module augmentation) | §7.2 TS namespaces |
| A4: `this.x =` from non-arrow functions and methods counts in either goal | §7.2 script goal |
| A5: `top`, `parent`, `frames`, `<any>.defaultView` | §7.2 script goal |
| A6, Codex 4649855600 and 4649855604: `x.constructor` and timer uses | §7.2 script goal |
| B5: in-run HTML, XML and PHP count as `*` (Markdown and reStructuredText dropped by the president's ruling, 3.1) | §7.2 script goal; R9 |
| A7, C3, C5: R9 widened; R11 added | §7.2; §15 |
| A8: `.mjs`/`.mts` files are modules | §5.2 note in the code (not collected yet) |
| B3: version numbers are never reused | Appendix B (above); `facts.py`; digest test |

### PR 3: the president's #691 ruling

Every item only adds `none`; no expected row changes. `js` fact version 6.

| Item | Applied in |
| --- | --- |
| B-1: an expression statement whose first token is `{` makes the file unsupported | §5.3 |
| B-2: only a non-static `constructor` is excluded from the receiver `this` rule | §7.2 script goal |
| B-3: receiver `this` through alias chains (`this.window.x =`, `this['self'].x =`) | §7.2 script goal |
| 3.1: Markdown and reStructuredText no longer count as inline-script carriers | §7.2; R9 |
| Section 4: `this.eval`/`this.setTimeout`, `Object.assign(this, …)` and `{ constructor: F }` give `*`; `export import Q = N` counts as an export; the rest named in R11 | §7.2; R11 |

### PR 3: the president's #691 re-check at 6c5f8b81

Every item only adds `none` (names, never `*`, for B-5); no expected row
changes. `js` fact version 7.

| Item | Applied in |
| --- | --- |
| B-4: `super` counts like a receiver `this` (`super.x =`, `super[k] =`, `super.window.x =`, `super.eval(…)`) | §7.2 script goal |
| B-5: a computed link in a receiver `this` chain (`this[k].x =`, ``this[`window`].x =``) records `x` | §7.2 script goal |
| R3: `this[k](…)` and hand-offs through an expression named in R11 | §15 R11 |

### PR 3: Codex 4652498471 (literal-key callees)

No expected row changes. `js` fact version 8. Mostly it only adds `none`.
One part does not: because a substitution-free template key now reads like
the dot form, a template-key read of a global-object name continues the
chain (``window[`top`].name`` reads like `window.top.name`) instead of
giving `*`. That matches the language exactly, and every write or
evaluator use through such a chain still fails closed.

| Item | Applied in |
| --- | --- |
| One helper (`_member_key`/`_static_key`) matches `X.name`, `X['name']` and ``X[`name`]`` at every name-matching site; escaped keys fail closed | §7.2 script goal |
| Property writers by bracket or template key, through the global object, or via `.call`/`.apply`/`.bind`; a computed or escaped key on `Object`/`Reflect` counts | §7.2 script goal |
| Computed (static) `constructor` keys in destructuring patterns | §7.2 script goal |

### PR 3: the president's re-check at 7c681e04

Only adds `none`; no expected row changes. `js` fact version 9.

| Item | Applied in |
| --- | --- |
| C-1: `Object`/`Reflect` reached through a receiver `this` (`this.Object.assign`, `this['Reflect']['set']`, `this.window.Object`) is a property writer; the class-constructor exclusion still applies | §7.2 script goal |
| A comma callee (`(0, Object.assign)(this, …)`) is a property writer | §7.2 script goal |
| Writer aliases, `Reflect.apply`, spread arguments and computed `constructor` keys on arbitrary objects named in R11 | §15 R11 |

### PR 4: Tier 1 Python (fail-closed refinements)

The Python analyzer replaces the stub (`python` fact version 2). Every PR 4
row of §10 holds as planned; the refinements below only add `none`, and no
JS row changes.

| Item | Applied in |
| --- | --- |
| Decorated definitions never prove alone (`expression-bound`); they still join a group | §7.3; §7.6 |
| Every write form binds, read fail-closed; `case` captures; `from __future__` | §7.3 |
| Python 2 forms (`except E, e`, list-comprehension leak, `exec` statement) | §7.3 |
| Dynamic binding widened (`eval`, `locals`, `builtins`, `importlib`, `sys` aliases and dunders, `__globals__`, frame globals) and applied to class-body lookups | §7.3; §7.6 |
| Type-parameter scopes, implicit dunders and `__class__` | §7.3 |
| A non-ASCII identifier makes a Python file unsupported (NFKC) | §5.3 |
| The probe's one-root run asserts the same Tier 1 rows as its py-root run | §10.2 |
| `stub` leaves the vocabulary | §10.6 |
| R12 added | §15 |

### PR 4: #695 panel fold

Every item only adds `none`; no expected row changes. `python` fact version
3.

| Item | Applied in |
| --- | --- |
| A1, B4, Codex 4653329444: a class with any base or keyword opens its namespace (`class-scope-bound`) | §7.3 class scope |
| A2, B1: `f_locals` anywhere makes every lookup `dynamic-scope` | §7.3; R12 |
| A3: module-scope definitions of builtin names give `builtin-shadow` | §7.3; §7.6 |
| A4: a space before a tab, or a form feed, in indentation makes the file unsupported | §5.3 |
| A5: `__main__` like `sys`; A6, B2: constant-string attribute names; A7: self-imports; B3: `X.modules[__name__]` | §7.3 dynamic binding |
| B5, C1: line continuations are tokens; natural `unmapped` near-misses | §7.3; §10.6 |
| B7: expected rows per plan PR pinned | `tests/test_call_resolution_engine.py` |
| B8 (not done): digesting the unit-case sources | Each unit case pins its own outcome, so a fact change there already fails a test in the same change, where the version bump is reviewed; covering them would mean moving several hundred inline sources into a registry the harness can read. **Rule (the president's #695 ruling, section 5): any change to analyzer output bumps the per-family fact version, whether or not committed digests move.** |
| C2 (not in this PR): narrowing the `importlib`/`sys` triggers needs its own soundness argument; A8 (cross-file monkeypatch, R10) is a follow-up | — |

### PR 4: the president's #695 ruling

Every item only adds `none`; no expected row changes. `python` fact version
4, bumped by hand under the B8 rule above. Each fix has the ruling's trees
committed as tests (`test_ruling_695_cases_keep_their_off_mode_edge`), and
removing any one fix fails at least one test.

| Item | Applied in |
| --- | --- |
| B-1: private-name mangling; a `__x` lookup inside a class gives `unmapped`, and bindings, `global` and `nonlocal` there also bind every mangled spelling | §7.3 (via the `py_scope` docstring); §7.6 `unmapped` |
| B-2: a backslash continuation as a line's first non-blank character makes the file unsupported; the ruling's whitespace differential is a test | §5.3 |
| B-3: in `__init__.py`, importing submodule `X` of the own package binds `X` at module scope (non-definition), also from a function | §7.3 dynamic binding (`py_scope` docstring); R12 for the cross-file form |
| B-4: `import pkg.x` in `pkg/__init__.py`; the own module reached as an attribute of a parent package; a root-level `__init__.py` treats every absolute import as a possible self-import (narrower than making the file unsupported: function-local lookups and relative-import-only files still resolve). Superseded by the general rule of the re-check below | §7.3 dynamic binding |
| B-5: parentheses around `__name__` in `X.modules[…]` and the getters | §7.3 dynamic binding |
| B-6: `WindowsError` pinned as a platform builtin; the pin test is a superset check on every OS plus the exact 3.14 list | §7.3 builtin rule |
| Section 4: R12 names `pkgutil.resolve_name`, `pydoc.locate` and `mock.patch` self-patches, cross-file submodule rebinding and builtins injected from elsewhere | §15 R12 |

### PR 4: the president's #695 re-check at 5efc7eec

Every item only adds `none`; no expected row changes. `python` fact version
5. The 13 re-check trees, and variants, are committed as tests
(`test_recheck_695_cases_keep_their_off_mode_edge`,
`test_submodule_imports_rebind_at_any_depth`,
`test_any_possible_self_reference_fails_closed`). Removing any part of the
rule fails tests.

| Item | Applied in |
| --- | --- |
| N-1, N-2, N-3: one general fail-closed rule replaces the per-shape B-3/B-4 fixes. The own name as a component of any import, any attribute name or any constant string makes module-scope lookups `dynamic-scope`. In any `__init__.py`, every resolved import path that passes through the package rebinds its next component. | §7.3 "The file's own module" |
| R12 names iteration over a package's namespace | §15 R12 |

### PR 4: the president's #695 re-check at f7f0b0bd

Every item only adds `none`; no expected row changes. `python` fact version
6. The 10 re-check trees, the R-5 trees and the computed-string trees the new
attribute-write rule closes are committed as tests
(`test_fold4_695_cases_keep_their_off_mode_edge`), with unit pins for each
rule part (`test_fold4_rules_fail_closed`,
`test_attribute_writes_through_any_receiver_rebind`). Removing any part fails
tests.

| Item | Applied in |
| --- | --- |
| N-4: own names and dynamic attribute names count whatever identifier node spells them (attribute, keyword argument, class-pattern keyword, dotted name), except parameter and `def`/`class` names; `X[__name__]` and the getters on any receiver | §7.3 "The file's own module" |
| N-5: raw own names (no identifier filter; dotted stems add their components); no path fails closed | §7.3 |
| N-6: a root-level `__init__.py` treats relative imports with two or more dots as self-imports; the "a relative import cannot reach it" claim is narrowed to a single dot | §7.3 |
| R-5 family: attribute writes through any receiver (`x.name = v`, `setattr`, constant-key subscripts, `__dict__.update`/`setdefault`/`pop`, `__setitem__`) bind `name` at module scope; this also closes `pkgutil_resolve`, `pydoc_locate`, `str_percent`, `str_bytes_decode`, `modules_spec_name` and `str_fstring_nested` | §7.3 |
| R12 names the R-5 shapes; the "every name ends with the own name" claim is narrowed to path-derived names | §15 R12; §7.3 |

### PR 4: the president's #695 re-check at 06f5dc32

Every item only adds `none`; no expected row changes. `python` fact version
7. The seven `ws_*` trees are committed as tests
(`test_fold5_695_cases_keep_their_off_mode_edge`), with unit pins
(`test_module_parts_come_from_tokens`, `test_spaced_import_tokens_fail_closed`,
`test_analyze_without_a_path_fails_closed`). Reverting the token-based
parsing fails 20 tests.

| Item | Applied in |
| --- | --- |
| N-7: a `from` import's relative level counts the `.` tokens of `import_prefix`, and its components come from `dotted_name`'s identifiers; the same level drives B-3/N-1 and N-6 | §7.3 |
| Audit: every place that used raw node text as a name or dotted path now uses identifier tokens (import names and module paths, the `from sys import modules` check, the import-binding text, bound import names, `as` alias targets, `case` value patterns) | §7.3 "Names come from tokens" |
| G-3: the attribute-write rule catches its listed spellings only; R12 names `operator.setitem`, `\|=` on the namespace dict and `update()` with a non-literal mapping | §7.3; §15 R12 |
| G-1 nit: `analyze(path=None)` fails closed like `""` | `py_scope.analyze` |

### PR 4: Codex 4654363963 (mangled names from class code)

Only adds `none`; no expected row changes. `python` fact version 8. A
Codex P2 on ready voided the approval at `e4ed3c5e`: the attribute-write rule
recorded only the source spelling, but `mod.__helper = f` inside class `K`
writes `_K__helper` at run time.

| Item | Applied in |
| --- | --- |
| Every name recorded from an identifier in class code takes every runtime spelling (source and mangled `_Class__x`, by `_record`'s rules): attribute writes (`x.__n = v`, `del`, augmented), the own-name and dynamic-name scans, submodule imports. CPython 3.14 (`co_names`) mangles attribute names, imported module names and aliases, not keyword-argument names, class-pattern keywords or strings; the scans over-trigger on those safely, and string keys stay literal | §7.3 (B-1, via the `py_scope` docstring) |
| Pins: Codex's tree end to end and variants (`del`, augmented assignment, a method body, a nested class, a comprehension target in a lambda, `global` plus an attribute write, a `with` target); mutation: attribute-write 9, scans 1, submodule imports 1 failures | `tests/test_call_resolution_tier1_py.py` |

### PR 4: the president's #695 re-check at 13c38360

Only adds `none`; no expected row changes. `python` fact version 9.

| Item | Applied in |
| --- | --- |
| I-3: the `sys` and `__main__` alias sets are built from every runtime spelling of the alias (`import __main__ as __m` in class `K` binds `_K__m`), and each use is tested by every spelling (`__m` in class code reads `_K__m`). The seven `p18` trees are committed (`test_fold7_695_cases_keep_their_off_mode_edge`), with unit pins (`test_mangled_sys_and_main_aliases_fail_closed`); reverting either side fails 2–4 tests | §7.3 (B-1, via the `py_scope` docstring) |
| Audit of every name set compared against a use: own names (identifier spellings; strings stay literal), `_DYNAMIC_ATTRIBUTES` (spellings), `_DYNAMIC_NAMES`, `_ATTRIBUTE_WRITERS`, `_MODULE_GETTERS`, `__name__` and `__main__` (plain names or dunders, never mangled), scope bindings and `global`/`nonlocal` (mangled since B-1), attribute writes and submodule writes (mangled since Codex 4654363963). No other set compared source spellings only | — |

### PR 4: the president's #695 re-check at eae66582

Only adds `none`; no expected row changes. `python` fact version 10.

| Item | Applied in |
| --- | --- |
| J-3a/J-4(1): an import in a class body (the nearest enclosing `class_definition` before any function or lambda) whose path or imported names include `sys` or `__main__` is dynamic: the bound name is a class attribute (`K.m`, `self.m`, `cls.__m`, `type(self)._K__m`, `getattr(K, 'm')`, `K.__main__`) that no identifier rule sees | §7.3 dynamic binding |
| J-3b/J-4(2): every name a `from __main__ import …` binds joins the `__main__` alias set with every runtime spelling, so any later use (`g.update(D)`, `g[n] = len`, `__dict__.update(D)`) is dynamic; an unused one still resolves (panel A's `import_main_from`) | §7.3 dynamic binding |
| R12 names the `sys` variants with a computed `modules` key and `from sys import __dict__` with a computed key | §15 R12 |
| Pins: the 16 J-3 trees plus `m20_sys_classattr_k` (`test_fold8_695_cases_keep_their_off_mode_edge`), unit pins and resolving controls; mutation: class-body rule 16, from-import names 9, their spellings 1, the function boundary of `_in_class_body` 1 failures | `tests/test_call_resolution_tier1_py.py` |

### PR 4: the president's #695 re-check at f2b38014

Only adds `none`; no expected row changes. `python` fact version 11.

| Item | Applied in |
| --- | --- |
| K-3/K-4: a constant string with a `__main__` component (split on `.` and `:`) is dynamic, except as a comparison operand (through parentheses, or a tuple, list or set operand of `in`) or in a `case` pattern | §7.3 dynamic binding |
| Closing the class: `__mp_main__` (a multiprocessing spawn child's name for the script) counts as `__main__` for the alias and string rules; the own-name and dynamic-attribute string rules also split on `:` (`pkgutil.resolve_name('pkg.a:__dict__')`, `'sys:modules'`); `/` maps no resolver to this module | §7.3 |
| Pins: the 7 K-3 trees (`test_fold9_695_cases_keep_their_off_mode_edge`), unit pins and the guard controls (`==` both ways, `in`, `!=` with parentheses, `case`); mutation: string rule 12, exemption 5, `:` for `__main__` 2, own name 1, dynamic attributes 1, `__mp_main__` 2, `case` exemption 1 failures | `tests/test_call_resolution_tier1_py.py` |

### PR 4: the president's #695 re-check at 3b2d8fae

Only adds `none`; no expected row changes. `python` fact version 12.

| Item | Applied in |
| --- | --- |
| L-2/L-3: the `__main__` constant exemption is narrowed to an operand of a comparison whose every operand is the bare `__name__` or a constant string (or a tuple, list or set of those), or a whole literal `case` pattern (through adjacent literals or `\|`) of `match __name__`; never in a class body; never in a file that binds, declares `global`/`nonlocal`, deletes or attribute-writes `__name__` (the decision runs after the scan, once every attribute write is known) | §7.3 dynamic binding |
| R12 names `b'__main__.helper'.decode()` and interpolated f-strings with a `__main__` part | §15 R12 |
| Pins: the 25 L-2 trees (`test_fold10_695_cases_keep_their_off_mode_edge`), unit pins (`test_narrowed_main_guard_fails_closed`) and the guard controls (`==` both ways, `in`, `not in` a list, `!=` with parentheses, `case` and `case … \| …`, the guard in a function and in a method); mutation: operand check 12, comparison class-body stop 2, `match` subject 3, `match` class-body stop 1, `__name__` binding check 17, attribute-write `__name__` 1 failures; a redundant `case_pattern` type check was removed as dead code | `tests/test_call_resolution_tier1_py.py` |

### PR 4: the president's #695 re-check at 8006c72c

Only adds `none`; no expected row changes. `python` fact version 13.

| Item | Applied in |
| --- | --- |
| M-2 (multi-subject `match`; defaults evaluated in a class namespace): the comparison/`case` deny-list exemption is replaced by a positive allow-list (executive decision): exactly `__name__ == '__main__'` or `!=`, either order, optionally parenthesized, as the whole test of a module-level `if`/`elif`, in a file that never rebinds `__name__`. The `match` exemption, the class-body stops and the operand-shape logic are removed | §7.3 dynamic binding |
| Flipped to fail closed (resolved under the fold-10 deny-list): `in ('__main__',)`, `not in [...]`, `match __name__: case '__main__'` and `case … \| …`, the guard in a function, `__name__ == '__main__'` in a method | `test_main_guards_off_the_allow_list_fail_closed` |
| Pins: the 9 M-2 trees (`test_fold11_695_cases_keep_their_off_mode_edge`); allow-list controls that resolve (`==` both ways, `!=`, a parenthesized test and operand, `elif`) and that fail closed (chain, `and`, `not`, `in`, `<`, `is`, `is not`, `__mp_main__`, another left operand, a concatenated literal, a nested or class-body or function guard, a rebinding); mutation: every allow-list condition fails 1–3 tests | `tests/test_call_resolution_tier1_py.py` |

### PR 4: Codex 4655078224 (closure cells and other non-assignment rebinding)

Only adds `none`; no expected row changes. `python` fact version 14. A Codex
P2 on the re-ready voided the approval at `e314f451`:
`invoke.__closure__[0].cell_contents = replacement` rebinds a closure
variable, and the analyzer still proved the local `helper`.

**Audit** of function, code, frame and cell attributes and the stdlib and
C-level APIs that can rebind a name a lookup depends on without spelling an
assignment to it:

| Route | Decision |
| --- | --- |
| `__closure__`, `cell_contents`, `types.CellType` | **File-wide trigger**: cells hold function-scope bindings |
| `types.FunctionType`, `types.LambdaType` (the same type) | **File-wide trigger**: existing code with a new closure or globals. The type is reachable without its name (`type(f)`, `f.__class__`, `type(lambda: 0)`), so soundness rests on the code-object sources (this row's neighbors and the `dis`/`monitoring`, `getstats` and `_code`/`code_linenos` rows), not on the type's name (corrected at the 606c689f re-check, PR 4 finding O-3a) |
| `__code__`, `types.CodeType`, `gi_code`, `cr_code`, `ag_code`, `f_code`, `co_code`, `co_names`, `co_consts`, `co_varnames`, `co_freevars`, `co_cellvars` (`code.replace(co_names=…)` renames the name a call site loads) | **File-wide trigger** |
| `dis`, `codeobj`, `_get_code_object` (`dis.Bytecode(f).codeobj`, `get_instructions` constants), `monitoring` (code objects handed to `sys.monitoring` callbacks) | **File-wide trigger** (added at the 606c689f re-check, PR 4 finding O-3a): code objects reached without spelling `__code__`, which `type(f)(code, globals)` runs under new bindings |
| `getstats` (`cProfile.Profile().getstats()` entries' `.code`, the only API that exposes `_lsprof`'s code objects) | **File-wide trigger** (added at the 8fd7c1a2 re-check, P-3a): another code-object source |
| `_code` (`traceback.FrameSummary._code`), `code_linenos` (the code objects `bdb.Bdb` caches as keys) | **File-wide trigger** (added at the 14e8f044 re-check, Q-3): more code-object sources |
| `call_annotate_function`, `call_evaluate_function`, `__annotate__`, `__annotate_func__` (the class-dict key behind `type.__annotate__`, also read by `annotationlib.get_annotate_from_class_namespace` for `NamedTuple`/`TypedDict`; added at the a6734480 re-check, S-3) | **File-wide trigger** (added at the 14e8f044 re-check, Q-3): `annotationlib` rebuilds the function it is given from `__code__` under a `_StringifierDict`, so a user function handed over runs under substitute globals |
| `ctypes`, `pythonapi`, `PyFrame_LocalsToFast` | **File-wide trigger**: arbitrary memory |
| a `closure=` keyword argument (`exec(code, g, closure=cells)`, with cells from heap walking) | **File-wide trigger** |
| `f_locals` (also via `sys.settrace`/`setprofile` frames) | already a file-wide trigger (A2) |
| `f_globals`, `f_builtins`, `__globals__`, `globals()`, `vars()`, `sys.modules` | already module-scope triggers |
| `pdb.Pdb().curframe_locals` | **File-wide trigger** (added at the 14e8f044 re-check, Q-3): the deprecated property returns `self.curframe.f_locals`, the PEP 667 write-through proxy |
| `inspect.getgeneratorlocals`, `getcoroutinelocals`, `getasyncgenlocals`, `getargvalues` | **File-wide trigger** (added at the 8fd7c1a2 re-check, P-3b): on 3.13 and later they return a frame's `f_locals`, the PEP 667 write-through proxy, so a write through them rebinds a function local, even with a constant key |
| `inspect.currentframe`, `sys._getframe`, `sys._current_frames`, `sys.settrace`/`setprofile` | no trigger (rewritten at the 8fd7c1a2 re-check): the `inspect` helpers and `pdb.Pdb().curframe_locals`, which hand over a frame's live locals, are triggers (rows above); other frame routes rebind only through `f_locals`/`f_globals`/`f_builtins`/`f_code`, all triggers, or through a computed attribute name (`inspect.getmembers(fr)`, `dir()` plus `getattr`; R12) |
| `gc.get_referents`/`get_referrers`/`get_objects` | no trigger: stays R12 under `gc` tricks (corrected at the 606c689f re-check): `gc`, `inspect.getmembers` and `dir()` plus `getattr` reach objects by computed means, which R12 accepts. Among them: a gc-found globals dict written with an unlisted spelling (`update(D)`), and gc-found code or cells run under `type(f)(…)`. A trigger would also cost panel A's correct `gc_referrers` resolution |
| `__defaults__`, `__kwdefaults__` | no trigger: only parameter values change, and parameter lookups never prove (R12) |
| `__func__` | no trigger: read-only (CPython 3.14 raises `AttributeError`); the function it yields rebinds a name only through a code object or a cell |
| `__self__`, `__builtins__` as an attribute | **Module-scope trigger** (dynamic attribute; corrected at the 606c689f re-check, PR 4 finding O-3b): `__self__` is read-only, but `len.__self__` is the writable `builtins` module; `f.__builtins__` and `os.__builtins__` are its namespace dict. Either reaches the builtins a module-scope lookup falls back to before a module-level definition runs |
| `builtins` as an attribute or a constant string, `bltns` | **Module-scope trigger** (dynamic attribute; added at the 8fd7c1a2 re-check, P-2): `inspect.builtins`, `site.builtins`, `mock.patch('builtins.helper', …)`, `mock.patch.dict('builtins.__dict__', …)`, `pydoc.locate('builtins')`, `pkgutil.resolve_name('builtins')`; `enum.bltns` is the only other stdlib name for the module (a scan of every importable stdlib module). A third-party re-export under another name stays R12 |
| `__wrapped__` | no trigger: introspection metadata; a decorated definition is already not a proof |

Pins: Codex's tree end to end and variants (in a class method, `setattr`
with a string and `getattr` with a concatenated string, `types.CellType` with
`FunctionType`, a nested closure; `test_codex_4655078224_closure_rebinding_end_to_end`),
one function-scope case per trigger name in identifier and string form
against a pinned list, the `closure=` keyword, code surgery and `ctypes`,
and controls that still resolve. Mutation: identifier trigger 30, string
trigger 27, `closure=` 1 failures, and each sampled name 2–3.

### PR 4: re-check at 606c689f (PR 4 finding O-3)

Only adds `none`; no expected row changes. `python` fact version 15. Two
classes still gave wrong `resolved` edges in the caller's own file; both
were already wrong at `e314f451`.

| Item | Applied in |
| --- | --- |
| Executive scope rule: a wrong same-file resolved edge blocks if only names or constant strings the file spells produce it through ordinary binding, attribute or call semantics; reflective access to interpreter internals gets a trigger when a small one closes it, and otherwise is named in R12, filed as a follow-up and does not block | §15 R12 |
| PR 4 finding O-3a: a function rebuilt over existing code without spelling a trigger (`type(run)(dis.Bytecode(run).codeobj, {'helper': len})()`, also via `run.__class__`, `type(lambda: 0)`, `dis.get_instructions` constants, computed keys from `dis`, a `sys.monitoring` callback). `dis`, `codeobj`, `_get_code_object` and `monitoring` are file-wide names | §7.3 `f_locals`; `_FILE_WIDE_NAMES` |
| PR 4 finding O-3b: builtins injected before a module-level definition runs, through `f.__builtins__`, `os.__builtins__` or `len.__self__` (the `builtins` module), written with `update(D)`, `\|=` or `update_wrapper(..., updated=('__dict__',))`. `__builtins__` and `__self__` are dynamic attributes in every spelling | §7.3 dynamic binding; `_DYNAMIC_ATTRIBUTES` |
| Audit corrections: the `FunctionType` row rests on the code-object sources; `__self__` is a trigger, not read-only; frames also rebind through a computed attribute name (R12); the `gc` rationale is "R12 (`gc` tricks)", naming a gc-found globals dict written with `update(D)` and gc-found code or cells run under `type(f)(…)` | PR 4 audit table above; §15 R12 |
| Named in R12: computed-name member walks on functions and frames (`inspect.getmembers`, `dir()` plus `getattr`), a function rebuilt with a positional closure from `gc`/`getmembers`, `runpy` re-running the file, recompiling or unmarshalling the file's own source, a same-file `gettext.install()` | §15 R12 |
| Flipped to fail closed (correct before, harmless): `l1_dis_type_globals_ctrl_call` (imports `dis`), `c32_local_rebuilt` | — |
| Pins: the 12 PR 4 finding O-3 trees end to end (`test_fold13_695_cases_keep_their_off_mode_edge`), one control per tree that still resolves (`test_fold13_controls_still_resolve`), builtins reached as an attribute (`test_builtins_reached_as_an_attribute_fail_closed`), the pinned file-wide list. Mutation: dropping `__builtins__` fails 5 tests, `__self__` 6, `dis` 3, `codeobj` 2, `_get_code_object` 2, `monitoring` 3 | `tests/test_call_resolution_tier1_py.py` |

### PR 4: re-check at 8fd7c1a2 (P-2, P-3, P-4)

Only adds `none`; no expected row changes. `python` fact version 16. All
were already wrong before fold 13.

| Item | Applied in |
| --- | --- |
| P-2a: the `builtins` module reached by spelling `builtins` as another module's attribute (`inspect.builtins`, `site.builtins`) or in a constant string (`mock.patch('builtins.helper', len, create=True)`, `mock.patch.dict('builtins.__dict__', D)`, `pydoc.locate('builtins')`, `pkgutil.resolve_name('builtins')`). P-2b: `enum.bltns`, the stdlib's one other name for it. `builtins` and `bltns` are dynamic attributes | §7.3 dynamic binding; `_DYNAMIC_ATTRIBUTES` |
| P-3a: code objects from the profiler (`cProfile.Profile().getstats()`); P-3b: a function's live locals through `inspect.getgeneratorlocals`/`getcoroutinelocals`/`getasyncgenlocals` and `getargvalues(frame).locals` (PEP 667), even with a constant key. The 5 names are file-wide | §7.3 `f_locals`; `_FILE_WIDE_NAMES` |
| Audit: a `getstats` row, an `inspect` frame-locals row, the frames row rewritten, the `builtins`/`bltns` row; R12's frames text rewritten and "`gc`/`ctypes` tricks" narrowed to `gc` tricks and C-level access other than through `ctypes`/`pythonapi` | PR 4 audit table above; §15 R12 |
| P-4 (executive ruling, not blocking): string-code execution through stdlib helpers (`cProfile.run`/`runctx`, `profile.run`, `bdb`/`trace` `.run`, `timeit`, `code.InteractiveInterpreter`, `doctest.testmod` on the file's own docstrings, `pickle.loads` of a constant) and third-party re-exports of `builtins` under another name are named in R12, citing treesitter-chunker#699 | §15 R12 |
| Flipped to fail closed (correct before, harmless): `g35_argvalues_ctrl` (reads `getargvalues(frame).args`) | `test_getargvalues_alone_fails_closed` |
| Pins: the 15 P-2/P-3 trees end to end (`test_fold14_695_cases_keep_their_off_mode_edge`), one control per tree that still resolves (`test_fold14_controls_still_resolve`), 4 more builtins forms in `test_builtins_reached_as_an_attribute_fail_closed`, the pinned file-wide list. Mutation: dropping `builtins` fails 9 tests, `bltns` 3, `getstats` 3, `getgeneratorlocals` 5, `getcoroutinelocals` 3, `getasyncgenlocals` 3, `getargvalues` 4 | `tests/test_call_resolution_tier1_py.py` |

### PR 4: re-check at 14e8f044 (Q-2, Q-3)

Only adds `none`; no expected row changes. `python` fact version 17. All
were already wrong before fold 14.

| Item | Applied in |
| --- | --- |
| Q-2: a call in an annotation, which `annotationlib` evaluates under substitute globals for `FORWARDREF`/`STRING` (`@dataclass`, `typing.get_type_hints`, `inspect.signature`, `functools.singledispatch`). A name looked up in any annotation (parameter, return, or variable at any level) gives `none(dynamic-scope)` | §7.3 "Annotations prove nothing"; `py_scope._in_annotation` |
| Q-3: `_code` (`traceback.FrameSummary`), `code_linenos` (`bdb`), `curframe_locals` (`pdb`), `call_annotate_function`, `call_evaluate_function` and `__annotate__` are file-wide names | §7.3 `f_locals`; `_FILE_WIDE_NAMES`; PR 4 audit table |
| Named in R12 (treesitter-chunker#699): resolvers given `X.__module__`; `ForwardRef.evaluate`/`typing.evaluate_forward_ref` on a constant string (string-code) | §15 R12 |
| Flipped to fail closed (correct before, harmless): panel A's `class_annotation_free`, so panel A has 38 resolutions; `a37_dataclass_early_ctrl` and `a37_func_value_late_ctrl` (the definition comes first). In panel A's `c1` and in `p3`, three class annotations change reason from `class-scope-bound` to `dynamic-scope` | `test_annotations_prove_nothing` |
| Pins: the 15 Q-2/Q-3 trees end to end (`test_fold15_695_cases_keep_their_off_mode_edge`), one control per tree that still resolves (the call moved to a value position, or the name left out; `test_fold15_controls_still_resolve`), 10 annotation forms, 4 value forms next to annotations, the pinned file-wide list; `test_defaults_and_annotations_run_in_the_enclosing_scope` and `test_class_body_code_sees_names_the_class_binds` now expect annotations to fail closed. Mutation: the annotation rule 20 failures; dropping `typed_parameter` 9, `typed_default_parameter` 1, `assignment` 8, `return_type` 3; `_code`, `code_linenos`, `curframe_locals`, `call_annotate_function`, `call_evaluate_function` 3 each, `__annotate__` 4 | `tests/test_call_resolution_tier1_py.py` |

### PR 4: re-check at a6734480 (S-2, S-3)

Only adds `none`; no expected row changes. `python` fact version 18. All
were already wrong before fold 15.

| Item | Applied in |
| --- | --- |
| S-2: a class-body `type` value is evaluated lazily against the live class namespace (`__classdict__`), so a later class write whose attribute name is not a literal at the write site rebinds it (`setattr(K, *('helper', len))`, `type.__setattr__(K, *[...])`, a same-file `put(K, 'helper', len)`, a name in a variable, a `dict(helper=len)` key, a descriptor's `__set_name__`; also in generic, nested and function-local classes). The value of any `type` statement proves nothing (`none(dynamic-scope)`), the full rule rather than the class-body-only variant | §7.3 "Annotations prove nothing"; `py_scope._in_annotation` |
| S-3: `__annotate_func__`, the class-dict key behind `type.__annotate__` (reached implicitly through `NamedTuple`), is a file-wide name | §7.3 `f_locals`; `_FILE_WIDE_NAMES`; PR 4 audit table |
| S-4, named in R12 (treesitter-chunker#699): a catch-all `__getattr__` handing a function to `functools.update_wrapper`, whose `__annotate__` copy `annotationlib` runs under substitute globals | §15 R12 |
| Flipped to fail closed (correct before, harmless): the probe controls `ta39_alias_class_ctrl`, `ca40_ctrl_no_write` and `ta39_alias_func_closure_ctrl`, all `type` values. `type X[helper] = helper()` changes reason from `parameter` to `dynamic-scope` | `test_type_statement_values_prove_nothing`; `test_type_parameters_bind_for_their_definition` |
| Pins: the 16 S-2/S-3 trees end to end (`test_fold16_695_cases_keep_their_off_mode_edge`), one control per tree that still resolves (S-2: the call in a method body, `ca40_method_body_ctrl`; S-3: the install renamed, `af39_ctrl`; `test_fold16_controls_still_resolve`), 7 `type`-value forms, the pinned file-wide list. Mutation: dropping the `type`-value branch fails 20 tests, `__annotate_func__` 6 | `tests/test_call_resolution_tier1_py.py` |

### PR 4: Codex 4656123247 (fold 17, parenthesized callees)

Only adds `none`; no expected row changes. `python` fact version 19. Codex
P2 on `3341540f`: `(setattr)(mod, 'helper', replacement)` has a
`parenthesized_expression` callee, so the attribute-write rule skipped it,
and `return helper()` in the same function still proved the original
`helper`. Blocking under the scope rule (spelled names, ordinary call
semantics).

| Item | Applied in |
| --- | --- |
| `_unwrap` gains a comment-skipping form; `_setattr_call` unwraps the callee before reading a bare or attribute writer name, and unwraps each argument and a `**` splat's operand; `_module_by_name` unwraps the getter callee | §7.3 "Callees and receivers are classified after unwrapping parentheses"; `py_scope._setattr_call`, `_module_by_name`, `_unwrap` |
| Audited and left alone: identifier-based triggers in `_scan_dynamic` (any position), `_sys_use` (a parenthesized `sys` is handed on, so it already fails closed), assignment targets (`parenthesized_expression` is a target container), `_constant_string` (already unwraps), the `__main__` guard (strict allow-list keeps plain `_unwrap`), `_callee_head` (a parenthesized call-site callee already gives `unbound`) | — |
| Pins: 14 cases that fail without the fix (`test_fold17_695_parenthesized_callees_keep_their_off_mode_edge`), 9 mixed forms that already failed closed, 3 controls that still resolve (a trailing-comma tuple, a write of another name). Mutation: dropping the `_setattr_call` callee unwrap fails 10 tests, its comment skipping 1, the argument unwrap 1, the splat unwrap 1, the `_module_by_name` unwrap 2 | `tests/test_call_resolution_tier1_py.py` |

### PR 4: fold 18 (writer aliases and namespace writes, executive ruling)

Only adds `none`; no expected row changes. `python` fact version 20. The
executive ruled that the writer aliases the fold-17 report left in R12 block:
they use only spelled names and ordinary binding and call semantics.

| Item | Applied in |
| --- | --- |
| Rule 1: `setattr`, `delattr`, `__setattr__`, `__delattr__` anywhere but as the callee of a direct call (after unwrapping parentheses), or as a constant string, give module-scope `dynamic-scope`. Granularity: module-scope `dynamic`, the set of lookups the namespace-write rule already affects; a namespace write cannot reach a function's locals or cells, so function-scope proofs stand | §7.3 "Writers handed on and namespace writes"; `py_scope._writer_mention`, `_literal_use` |
| Rule 2: a namespace mutator taken off a namespace receiver (`x.__dict__`, `vars(x)`, a call with a `'__dict__'` argument, parentheses, a name assigned one of them) without a call fails closed; so does a namespace write whose names are not all constants (`update(D)`, `setdefault(k, …)`, `__setitem__(k, …)`, `__ior__(D)`, `ns[k] = …`) | §7.3; `_namespace_rules`, `_namespace_receiver`, `_namespace_call` |
| Rule 3: `operator` writers (`setitem`, `delitem`, `__setitem__`, `__delitem__`, `ior`, `iadd`, and names imported from `operator`) record a constant key, or a literal mapping's keys, on any receiver (like `x['name'] = v`); on a namespace receiver anything else fails closed; handed on, they fail closed when the file names a namespace dict | §7.3; `_operator_write`, `_writer_mention` |
| Rule 4: `mod.__dict__ \|= {'helper': f}` was not caught; `x \|= {'name': v}` now writes `name` of any receiver (like `.update({...})`), and `\|=` with anything else on a namespace receiver fails closed. `vars(mod)['helper'] = f` was already caught (`vars` is a trigger). A literal `*` splat in a writer call records its constants | §7.3; `_namespace_ior`, `_setattr_call` |
| R12 "other write spellings" emptied of these; what stays is named in R12 with measured costs (computed names at the write site on non-namespace receivers, a namespace dict handed on) | §15 R12 |
| Cost: harness against main unchanged (0 problems, 8 resolved + 1 narrowed, 43 PR 4 rows). Probes: panel A keeps 38 resolutions; 5 former R12 wrong edges in p1–p42 now fail closed (`aw_operator_setitem`, `aw_dict_ior`, `m20_from_sys_dict_computed`, `m21_name_eq_main_dict`, `m37_pydoc_locate_int_module`); no correct resolution lost. Controls updated: `n31_self_ior` and `q34_site_builtins_ior` (`b \|= {'helper': len}` now records), `q34_pydoc_locate_builtins` and `q34_resolve_name_builtins` (non-literal namespace `update`), two fold-16 star-args controls, and `(setattr,)` (a tuple element hands `setattr` on) | `tests/test_call_resolution_tier1_py.py` |
| Pins: `test_fold18_695_writer_aliases_keep_their_off_mode_edge` (32 cases, each failing without the fix), `test_namespace_subscript_writes_were_already_caught` (2), `test_ordinary_mutator_aliases_still_resolve` (9 controls). Mutation: rule 1 identifiers 11 failures, rule 1 strings 1, rule 2 extraction 5, computed namespace calls 3, computed namespace subscripts 1, namespace aliases 2, `operator` writes 5, `operator` from-imports 1, `operator` hand-on 1, `\|=` 3, splat 1 | `tests/test_call_resolution_tier1_py.py` |

### PR 4: fold 19 (re-check at 1d6cbb17, U-3..U-5; executive ruling E-19)

Only adds `none`; no expected row changes. `python` fact version 21. E-19
withdraws E-18b (its premise, that every same-file route to this module is
closed, was false: U-5) and closes computed writes at the write site.

| Item | Applied in |
| --- | --- |
| B-1: `_constant_string` skips comments in implicit concatenations and unwraps parentheses through comments (the president's `fixU1`); W-4: an f-string whose interpolations are all constant strings (no conversion, format spec or `=`) is a constant | `py_scope._constant_string`, `_constant_fstring` |
| B-2: `operator.__ior__`/`__iadd__`; unbound namespace mutators (`dict.update(ns, D)`, `dict.__ior__(ns, D)`, `type(ns).update(ns, D)`, `setdefault`, `pop`, `clear`, `__setitem__`, `__delitem__`): constant keys or literal mappings recorded, anything else fails closed; `getattr(ns, 'update')`, `attrgetter` through `__dict__`, `methodcaller('<mutator>')`; aliases through tuple/starred targets, walrus, conditional and boolean operands, `match` captures; a namespace mutator called with non-constant names, `clear` and `popitem` fail closed | §7.3; `_namespace_rules`, `_namespace_call`, `_namespace_receiver` |
| W-1: a writer whose name argument is not a constant string, on any receiver, and non-literal `*` splats | §7.3; `_writer_name_check` |
| W-2: a namespace receiver escaping into a call argument, container, return/yield, default, lambda body, `with` item, `for`/comprehension iterable or attribute/subscript target | §7.3; `_namespace_escape` |
| W-3: `unittest.mock` `patch`/`patch.dict` with a non-constant target, `patch.object` with a non-constant attribute, `patch` handed on; constant `patch.object` attributes and `patch.multiple` keywords recorded | §7.3; `_mock_rules`, `_patch_call` |
| R12: the computed-write family is removed; what stays for writes is reflective and string-code only (#699, P-4) | §15 R12 |
| Cost: harness against main unchanged (0 problems, 8 resolved + 1 narrowed, 43 PR 4 rows). CPython 3.14 non-test `Lib` (595 files): W-1 fires in 25, W-2 in 38, W-3 in 0 (58 in all); 10 files newly lose module-scope resolution against 1d6cbb17 (the rest were already dynamic). Probes: all 57 wrong p44–p47 trees fail closed; panel A keeps 38 resolutions; p1–p42 close 15 more former R12 wrong edges (the m23/m28/m29 formatting families, `mock_patch_self`, `m37_mock_patch_run_module`) and flip 10 correct ones, each in a file with a computed `setattr` or `mock.patch` target (W-1/W-3) | — |
| Pins: `test_fold19_695_computed_writes_keep_their_off_mode_edge` (57 probe trees plus 18 rule cases, each failing at 1d6cbb17), `test_fold19_controls_still_resolve` (10), `test_fold19_constant_strings` (8); ten fold-16 S-2 controls whose write is computed now fail closed (`test_fold16_computed_write_controls_fail_closed`). Mutation: B-1 concatenation comments 6 failures, parenthesis comments 2, W-4 3, B-2a 1, B-2b 1, B-2c attrgetter 2, methodcaller 1, B-2d match 1, conditional 1, boolean 1, walrus 1, W-1 27, W-1 splat 2, W-2 15, W-3 calls 12, `patch.object` recording 3, `patch` handed on 1; B-2d tuple targets 0 (every tuple or list value holding a namespace dict is a W-2 container escape) | `tests/test_call_resolution_tier1_py.py` |

### PR 4: fold 20 (receiver-based patchers)

Only adds `none`; no expected row changes. `python` fact version 22. Closes
the pytest-mock escape the fold-19 report named: `mocker.patch(__name__ +
'.helper', f)` and `mocker.patch.object(mod, n, f)` went unrecognized because
`mocker` is a fixture parameter, not an import. Under the scope rule a small
trigger closes it.

| Item | Applied in |
| --- | --- |
| W-3 also covers (a) any `X.patch.object`/`X.patch.dict`/`X.patch.multiple` chain, whatever `X` is (parentheses and `patch` aliases included); (b) `.patch`, `.patch.object`, `.patch.dict`, `.patch.multiple` on a name or parameter `mocker`, `module_mocker`, `class_mocker`, `package_mocker`, `session_mocker`; (c) either handed on. Same semantics: a computed target or attribute fails closed, constant `patch.object` attributes and `patch.multiple` keywords are writes, a constant dotted `patch('a.helper')` keeps the own-name rule. A plain `.patch(url)` on other receivers is untouched | §7.3; `py_scope._mock_rules`, `_is_patch`, `_is_patch_attribute` |
| Pins: `test_fold20_695_receiver_patchers_keep_their_off_mode_edge` (11 cases, each failing at 5c138588), `test_fold20_plain_patch_calls_still_resolve` (6 controls: HTTP-client `.patch(url)` on a parameter, an arbitrary receiver and `requests`, constant-target patchers). Mutation: any-`X` chains 5 failures, pytest-mock names 4, `X.patch.object` handed on 1 | `tests/test_call_resolution_tier1_py.py` |

### PR 4: fold 21 (re-check at bb8b75b4, V-4/V-5/V-7; executive ruling E-20)

Only adds `none`; no expected row changes. `python` fact version 23.

| Item | Applied in |
| --- | --- |
| B-4: a namespace alias read back as an attribute (`m.NS`, `K.ns`, `self.ns`, `global NS`) or by `getattr(x, '<alias>')` is a namespace receiver, so its writes and escapes follow W-2 and the namespace write rules | §7.3; `py_scope._namespace_receiver` |
| B-5: mock-module and pytest-mock aliases tracked through assignment, walrus, tuple targets, class bodies and `self.X = …`; a mock-module name used other than as an attribute receiver, a direct callee or an alias value fails closed; a constant `'patch'` in a file importing the mock module fails closed | §7.3; `_mock_aliases`, `_mock_expression`, `_mocker_expression`, `_mock_receiver_use` |
| E-20 triggers: stdlib resolver mentions (`resolve_name`, `safeimport`, `find_class` in every spelling; `locate` on `pydoc`; `_resolve`/`_importer` on `logging.config`; their from-imports; constant strings naming the first three); a constant `'__dict__'` subscript key; `X._sys.modules` | §7.3; `_resolver_rules`, `_literal_use`, `_scan_dynamic` |
| V-8: the guarantee narrowed to every write spelled in this file; R12 names library-internal writers (`update_wrapper`/`wraps`, `argparse`/`optparse`, `copy._reconstruct`, pickle BUILD), ancestor-package acquisition and pytest patchers under other names (#697/#699) | §7.3; §15 R12 |
| Cost: CPython 3.14 non-test `Lib`: 0 of 595 files change (every file mentioning a resolver was already dynamic; the `_sys.modules` trigger newly hits 0). Harness against main unchanged (0 problems, 8 resolved + 1 narrowed, 43 PR 4 rows). The president's p48/p49 trees all fail closed except the three #697 patcher cases; p50's controls still resolve; `sn48_simplenamespace_init` (no runtime write) flips to fail closed. Two fold-14 controls that mentioned `pydoc.locate`/`resolve_name` now use other attributes | — |
| Pins: `test_fold21_695_writes_and_triggers_keep_their_off_mode_edge` (29 cases on a handed-in module, each failing at bb8b75b4), `test_fold21_controls_still_resolve` (8). Mutation: B-4 attributes 6 failures, B-4 `getattr` 1, mock aliases 3, mocker aliases 1, non-receiver use 1, `'patch'` string 1, walrus 1, resolver names 3, `pydoc` attribute 1, `logging.config` attribute 1, `from pydoc` 1, `from logging.config` 1, resolver strings 1, `'__dict__'` key 1, `_sys.modules` 1 | `tests/test_call_resolution_tier1_py.py` |

### PR 4: fold 22 (re-check at 78812ad2, W-5..W-7; one mechanism for all sensitive kinds)

Only adds `none`; no expected row changes. `python` fact version 24. The
executive directed one shared mechanism instead of per-kind alias logic,
because each round found a binding form handled for one sensitive kind and
not another (W-6 is a mock-module spelling that `mocker` lacked).

| Item | Applied in |
| --- | --- |
| One alias/readback/escape mechanism for a namespace dict, the mock module, `patch` and a pytest-mock fixture; the fold-18..21 per-kind alias and escape code (`_contains_namespace`, `_namespace_escape`, `_mock_aliases`, `_mock_receiver_use`, the patch hand-on loop) is replaced | §7.3 "One alias/readback/escape mechanism"; `py_scope._sensitive_rules`, `_sensitive`, `_escape`, `_contains_kind`, `_reachable_binding` |
| W-5: `X.mock` for any `X` and `getattr(X, 'mock')` are the mock module; a constant `'mock'` fails closed in a file importing it. W-6: mocker aliases through every binding form, and `mocker` escaping (`[mocker][0]`, `_p(mocker, …)`) fail closed; `getattr(mocker, 'patch')` (W-8) is `patch` too. W-7: `K.__dict__['ns']`, `type.__getattribute__(K, 'ns')` and `attrgetter('ns')(K)` read an alias back | §7.3 |
| A value carries a kind only as itself or a tuple/list/set element, not through a call, attribute read or subscript: removes the false namespace alias at `string/__init__.py` (`pattern = cls.__dict__.get('pattern', …)`) | `_contains_kind` |
| Cost: CPython 3.14 non-test `Lib`: 0 of 595 files newly dynamic, 1 no longer (`string/__init__.py`, the false alias above); the repository's 359 test files: 0 change; `mocker` passed to any function: 0 occurrences in either corpus, so the full escape rule is kept. Harness against main unchanged (0 problems, 8 resolved + 1 narrowed, 43 PR 4 rows). The president's p48–p53 trees all fail closed except the two #697 patchers under other names (`mk48_other_param`, `mk48_fixture_typed`); `mk_local_func` (`_p(mocker, …)`) now fails closed as intended | — |
| Pins: `test_fold22_695_president_probes_keep_their_off_mode_edge` (17 probe cases, each failing at 78812ad2), `test_fold22_695_cross_kind_matrix_fails_closed` (22 forms x 4 kinds = 88; 24 failed at 78812ad2), `test_fold22_controls_still_resolve` (6). Mutation: alias binding 29 failures, escape 30, `X.mock` 5, `'mock'` string 1, containment narrowing 2; readback and the reachable-binding escape back each other up (0 alone, 31 together), as do the `setattr` binding and escape (35 together) | `tests/test_call_resolution_tier1_py.py` |

### PR 4: fold 23 (re-check at 515de38e, X-5..X-7; executive ruling E-21)

Only adds `none`; no expected row changes. `python` fact version 25. Six
rounds after 3341540f showed that a deny-list of escaping uses does not
converge (X-5: `__ior__` returns the namespace, a fold-22 regression; X-6:
`match` class-pattern keywords; X-7: `patch.__call__`/`__get__`). E-21
inverts the classification to a closed allow-list, as fold 11 did for the
`__main__` guard.

| Item | Applied in |
| --- | --- |
| THE CLOSED ALLOW-LIST of sensitive-value uses (A-1), every other use failing closed (A-2): binding positions and local alias bindings; namespace pure reads and statement-only recognized writes; `_MOCK_SAFE`, `_MOCKER_SAFE`, `_PATCH_SAFE`; class-pattern keywords naming `__dict__`/`mock`/`patch`/an alias fail closed | §7.3 "THE RULE for sensitive values"; `py_scope._NS_READS`, `_NS_WRITES`, `_MOCK_SAFE`, `_MOCKER_SAFE`, `_PATCH_SAFE`, `_safe_use` |
| Deleted as redundant: the fold-22 escape deny-list (`_escape`), `_mutator_receiver`, `match`-capture aliasing, the fold-18 extraction loop and the computed-subscript loop | `py_scope.py` |
| Flipped (still fails closed, reason changes): `mod.__dict__.__setitem__('helper', len)` goes from `mixed-bindings` to `dynamic-scope` (a dunder is off the list; pinned in `test_namespace_dunder_writes_fail_closed`). Probe control `ns_dictsplat_ctrl` (`x = {**m.__dict__}`, a copy) now fails closed: a dict splat is not on A-1, reported rather than added (cost 0) | `tests/test_call_resolution_tier1_py.py` |
| Cost (A-4): 0 of 595 stdlib files and 0 of 359 repository test files change against 515de38e. Harness against main unchanged (0 problems, 8 resolved + 1 narrowed, 43 PR 4 rows). The president's p44–p56 trees all fail closed except the two #697 patchers under other names; panel A keeps 38 resolutions | — |
| Pins: `test_fold23_695_president_probes_keep_their_off_mode_edge` (19: every X-5/X-6/X-7 probe and `mocker.mock_module`, all wrong at 515de38e), `test_fold23_695_allow_list_is_closed` (11 unlisted uses x 4 kinds = 44), `test_fold23_695_allow_list_entries_still_resolve` (39, one per A-1 entry), `test_fold23_695_allow_listed_writes_record_their_name` (5). Mutation: `_NS_READS` 10 failures, `_NS_WRITES` 12, `_MOCK_SAFE` 14, `_MOCKER_SAFE` 6, `_PATCH_SAFE` 6, A-2 (allow everything) 101, class-pattern keywords 4 | `tests/test_call_resolution_tier1_py.py` |

### PR 4: fold 24 (re-check at e9c087d9, Y-5 and Y-6)

Only adds `none`; no expected row changes. `python` fact version 26. Both
findings were pre-existing (wrong at 515de38e too).

| Item | Applied in |
| --- | --- |
| Y-5: every import of the mock module or `patch`, in any spelling and at any scope, is an alias (`self.aliases[_MOCK] \|= mock_import_names`, `self.aliases[_PATCH] \|= patch_import_names` before readbacks are classified), so attribute, constant `getattr`, constant-key and class-pattern-keyword readbacks of the import name carry the kind and W-3 fails a computed target closed | §7.3 alias binding; `py_scope._sensitive_rules` |
| Binding audit: every other binding of a sensitive value a readback can reach fails closed at the binding (module- or class-scope assignment, walrus, `for`, `with`, `match` capture, annotated or tuple targets, `global`, `self.X = …`, `setattr`, a default); a `from unittest.mock import *` gives `star-import`; parameters and other function-local bindings are not reachable; a function-scope import is an alias too (over-approximation); an import of `__dict__` from the file's own module is `dynamic-scope`, from `__main__` fails closed on any use (J-3b), and from another module binds a namespace that cannot hold this file's names | — |
| Y-6: `values()` and `items()` leave `_NS_READS` (simplest option: 1 stdlib file against 0 for the conditional option); `keys()` stays (keys are strings) | §7.3 "THE RULE for sensitive values"; `py_scope._NS_READS` |
| Cosmetic: the duplicate class-pattern keyword check in `_sensitive_rules` is gone (one check after the aliases are known, before the early return) | `py_scope._sensitive_rules` |
| Flipped: fold-22 control `list(signal.__dict__.items())` (`multiprocessing/process.py`) now fails closed (pinned in `test_fold24_695_stdlib_signal_items_fails_closed`); fold-23 entries `ns-values`/`ns-items` leave `test_fold23_695_allow_list_entries_still_resolve` | `tests/test_call_resolution_tier1_py.py` |
| Cost (A-4) against e9c087d9, over 638 supported non-test stdlib files and 488 supported repository test files: Y-5 0 and 0; Y-6 1 stdlib file (6 of 29 identifier-callee calls in `multiprocessing/process.py`) and 0 test files; the conditional Y-6 option would have cost 0 and 0. Beside the canonical `from unittest.mock import patch`, a computed-target `X.patch(u)` on any receiver fails closed (pinned); under `patch as P` or a mock-module import it still resolves (controls). Harness against main unchanged (0 problems, 8 resolved + 1 narrowed, 43 PR 4 rows). The president's p44–p58 trees: exactly the 18 Y-5/Y-6 cases change, all now fail closed; only the two #697 patchers under other names remain wrong; panel A keeps 38 resolutions | — |
| Pins: `test_fold24_695_president_probes_keep_their_off_mode_edge` (18: every Y-5 and Y-6 probe, all wrong at e9c087d9), `test_fold24_695_import_bindings_are_aliases` (the completeness matrix's "import binding read back" rows: 9 import spellings x 6 readbacks = 54), `test_fold24_695_namespace_iteration_fails_closed` (2 methods x 4 kinds = 8), `test_fold24_695_stdlib_signal_items_fails_closed` (1), `test_fold24_695_controls_still_resolve` (10), `test_fold24_695_canonical_patch_import_makes_any_x_patch_patch` (1). Mutation: import seeding removed 48 failures, `values`/`items` back in `_NS_READS` 8, the class-pattern keyword check 14, `keys` removed 4 | `tests/test_call_resolution_tier1_py.py` |

### PR 4: fold 25 (Codex 4657695001 at ab49156a: allow-listed callees verified by binding)

Only adds `none`; no expected row changes. `python` fact version 27. The
Codex P2 showed `len(ns)` allow-listed by spelling only: a same-file
`def len(d): d.update(dict(helper=replacement))` received the namespace as
a plain parameter, and `helper()` got a wrong proof. The audit found the
same hole wider: the unbound mutator entry checked no receiver at all
(`U.update(ns, …)`), and bare `_OPERATOR_WRITERS` names counted without an
import.

| Entry | Binding check | Test |
| --- | --- | --- |
| `len(ns)` | `_builtin_name(len)`: no binding event for `len` anywhere, no recorded write of `len` | `len-*` shadows (9 forms), `codex-4657695001` |
| `dict.update/setdefault/pop/__setitem__/__delitem__/__ior__(ns, …)` (also `clear`/`popitem`, which fail closed anyway) | `_builtin_name(dict)` on the receiver; any other receiver fails closed | `dict-*` shadows (6 methods x 9 forms), `other-receiver` |
| `type(ns).update(ns, …)` | none needed: the inner `type(ns)` puts the namespace in an argument position, which fails closed | `type-of-namespace` |
| `operator.setitem/delitem/ior/iadd/…(ns, …)`, `import operator as op` | `_stdlib_name(operator)`: every binding of the receiver name is `import operator [as x]` | `operator-*` shadows (4 entries x 9 forms), `other-module-as-operator` |
| `from operator import setitem [as s]` | `_stdlib_name(operator, _OPERATOR_WRITERS)`: every binding is `from operator import <writer> [as x]`; a bare writer name with no import fails closed | `from-operator-*` shadows (2 x 9), `bare-writer-no-import`, `from-other-module` |
| `c in ns`, `ns[c]`, `ns.get/keys`, `ns \|= …`, `ns.<writer>(…)` | none needed: syntax or methods of the real dict | — |
| `getattr(x, '__dict__')`, `vars(x)` producers | none needed: shadowing only over-recognizes (fails closed); an alias (`g = getattr`, `v = vars`) is already dynamic or recognized by the constant `'__dict__'` | `test_fold25_695_shadowed_producers_still_fail_closed` |
| `setattr`/`delattr` recorded writes | none needed: a shadowed `setattr` over-records its constant name; the module it receives is no sensitive kind (same-file body writes on it are recorded or fail closed on any receiver; a library's are R12, #699) | `test_fold25_695_shadowed_producers_still_fail_closed`, `test_fold25_695_shadowed_setattr_body_writes_are_recorded` |
| mock constructors, `_MOCKER_SAFE`, `patch` | none needed: the kinds require tracked imports or fixture names, the uses receive no sensitive value, and a rebound `patch` import still counts as `patch` (over-recognition) | `test_fold25_695_shadowed_producers_still_fail_closed` |

The nine shadowing forms are `def`, assignment, import alias, parameter,
`for` target, `global`, a recorded write (`m.<name> = print`), a tuple
`with` target and a type parameter. The binding record is the scope pass's
event list: the sensitive-kind rules run before events are applied to the
scopes, so `scope.bindings` is still empty then. The `builtin-shadow`
lookup rule is not reusable here: it decides a module-level lookup of a
builtin name, not whether the name is bound anywhere.

Pins: `test_fold25_695_shadowed_allowlist_callees_keep_their_off_mode_edge`
(123: the Codex repro, 5 receiver/import probes, 13 entries x 9 shadowing
forms; 98 of the 123 were wrong at ab49156a),
`test_fold25_695_verified_callees_still_resolve` (13),
`test_fold25_695_verified_callees_record_their_name` (3),
`test_fold25_695_shadowed_producers_still_fail_closed` (5),
`test_fold25_695_shadowed_setattr_body_writes_are_recorded` (1). Mutation
(narrow suite): `len` by spelling 9 failures, `dict` receiver unchecked 49,
`operator` receiver unchecked 54, from-imported writer by spelling 7,
recorded-write check removed 12, binding events ignored for builtins 50,
`_stdlib_name` accepting any import among the bindings 6, `_stdlib_name`
ignoring non-import binding events 4.

Cost: 0 of 638 supported non-test stdlib files and 0 of 488 supported
repository test files change against ab49156a. Harness against main
unchanged (byte-identical `cmp`: 0 problems, 8 resolved + 1 narrowed, 43
PR 4 rows). The president's p44–p58 trees are unchanged against fold 24;
panel A keeps 38 resolutions.

### PR 4: fold 26 (re-check at 1b4d112f, AA-4: writer members relied on by name)

Only adds `none`; no expected row changes. `python` fact version 28.
`_stdlib_name(receiver, "operator")` verified the `operator` binding but
not the writer member: `operator.__dict__.update(setitem=evil)` is a
recorded write of `setitem` (a constant keyword spelled in this file), and
`operator.setitem(m.__dict__, 'x', 1)` then calls `evil` with the
namespace. Pre-existing (wrong at ab49156a too).

| Item | Applied in |
| --- | --- |
| The attribute branch of `_safe_use` adds the writer member to `relied_names` (`names & _OPERATOR_WRITERS`), so a recorded write of it fails closed (the president's fix) | `py_scope._safe_use` |
| Generalized: `_stdlib_name` with members adds the imported member as well as the bound name (`from operator import setitem as s` relies on `setitem` and `s`; a write of `setitem` before the import was missed) | `py_scope._stdlib_name`, `_imports_from` (returns the module or member) |
| Audit of A-1 entries reading a module attribute: `operator.<writer>` (fixed) and `from operator import <writer> [as s]` (fixed); `dict.<method>` cannot be reassigned (`TypeError: cannot set 'update' attribute of immutable type 'dict'`; `dict.__dict__` is a read-only mappingproxy); `mock.<constructor>`/`mock.patch`/`patch.object` are uses of sensitive kinds, whose `__dict__` and assignment are off the list (fail closed); `_MOCKER_SAFE` members receive no sensitive value; `len` relies on `builtins.len`, which any `builtins` mention or recorded `len` write already covers | — |
| Cost: 0 of 638 supported non-test stdlib files and 0 of 488 supported repository test files change against 1b4d112f. Harness against main unchanged (byte-identical `cmp`). The president's p60–p62 match his `fix25` outputs exactly (all seven AA-4 cases and `op_monkey_dict_update` fail closed, nothing else changes); p44–p58 and panel A (38) unchanged | — |
| Pins: `test_fold26_695_rebound_operator_members_keep_their_off_mode_edge` (9: the p62 repro, the five other AA-4 spellings, a from-import alias whose member is written first, and `delitem`/`__setitem__` members; all 9 wrong at 1b4d112f), `test_fold26_695_unrelated_writes_keep_the_entry` (6 controls: no write, writes of `attrgetter`, of another writer member `delitem`/`iadd`, an unrelated attribute write, and the from-import alias). Mutation: attribute-member reliance removed 8 failures, from-import member reliance removed 1, every writer relied on (over-broad) 2 | `tests/test_call_resolution_tier1_py.py` |

### PR 4: fold 27 (Codex 4657978945 at 4758e2cc: an allow-listed read's result must not reach the namespace)

Only adds `none`; no expected row changes. `python` fact version 29.
`ns.keys()` was allow-listed with an ordinary result, but a `dict_keys`
view's `.mapping` is a mappingproxy of the namespace itself, so
`next(reversed(mod.__dict__.keys().mapping.values()))` recovered the
file's own `patch` import, defeating Y-6.

| `_NS_READS` / A-1 read | Result at run time | Decision |
| --- | --- | --- |
| `len(ns)` | int | safe (kept) |
| `c in ns`, `c not in ns` | bool | safe (kept); the `not in` check never matched before (one grammar token) and now does |
| `ns[c]`, `ns.get(c, …)` | the stored value | safe for ordinary names (kept): alias names, the mock/`patch` names and the `'__dict__'` key are readbacks; values reach the namespace only through spelled acquisitions the other rules track |
| `ns['__builtins__']`, `ns.get('__builtins__')` | builtins module or dict (can rebind `len`) | already fail closed: `__builtins__` is a dynamic-attribute literal |
| `ns['__dict__']` | — | already fails closed (dynamic-attribute literal) |
| `ns['__loader__']`, `ns['__spec__']` | loader, `ModuleSpec`: no namespace reference | safe (kept): a module they load (`load_module`, `spec.loader`) is an ordinary module whose writes are recorded or fail closed on any receiver (pinned) |
| `ns.keys()` | a view with `.mapping` (namespace proxy) | **removed** from `_NS_READS`, option (i) |
| `ns.values()`, `ns.items()` | views of every value | removed in fold 24 |

| Item | Applied in |
| --- | --- |
| Option (i), removing `keys`, cost 0 of 638 supported non-test stdlib files and 0 of 488 supported repository test files; option (ii), treating `ns.keys()` as the namespace kind, cost the same. The rule picks (i) at a cost of 1 file or less | `py_scope._NS_READS` |
| Flipped: the fold-19 control's `z = list(mod.__dict__.keys())` became `z = len(mod.__dict__)`; the fold-23 `ns-keys` entry and the two fold-24 `keys()` controls were retired and re-pinned as failing closed | `tests/test_call_resolution_tier1_py.py` |
| Cost: 0 and 0 against 4758e2cc with the `not in` fix included. Harness against main unchanged (byte-identical `cmp`); the president's p44–p62 trees and panel A (38) unchanged | — |
| Pins: `test_fold27_695_namespace_views_keep_their_off_mode_edge` (5: the Codex repro, `.mapping` through a keys view in a variable, a walrus and a conditional, and `ns.keys().mapping['P']`; 4 wrong at 4758e2cc, the fifth already caught as an alias readback), `test_fold27_695_namespace_view_reads_fail_closed` (9, including `__builtins__` and `__dict__`), `test_fold27_695_loader_modules_are_tracked` (3), `test_fold27_695_unreachable_results_still_resolve` (7 controls). Mutation: `keys` back in `_NS_READS` 10 failures, the old `not in` check 1, `get` removed 8 | `tests/test_call_resolution_tier1_py.py` |

### PR 4: fold 28 (Codex 4658232413 at 0e96b12f: verification by the ordinary lookup at the use site)

Only adds `none`; no expected row changes. `python` fact version 30. In a
class body with a custom metaclass, `__prepare__` can supply `len`, so
`class K(metaclass=Meta): value = len(mod.__dict__)` handed the namespace to
`evil`. The event-based `_builtin_name` accepted it, because the allow-list
verification did not use the lookup that refuses proofs in open class
scopes. The same held for `dict.update` and `operator.setitem`.

| Item | Applied in |
| --- | --- |
| `_builtin_name` and `_stdlib_name` record each verified use; `_verify_callees` runs once the binding events are applied and looks each one up from its use site with `lookup()`: a builtin must give `none(unbound)`, a stdlib name an `import` outcome whose binding is the tracked `import <module>` (or `from <module> import <writer>`). Otherwise the file goes `dynamic-scope` (A-2) | `py_scope._verify_callees`, `_builtin_name`, `_stdlib_name` |
| Belt and braces: the binding-event check stays (stricter: it refuses bindings in scopes the lookup does not consult; removing it fails 15 tests); the recorded-write check stays for writer members (removing it fails 10); for builtin names it is redundant with the lookup (a recorded write is a module `local-variable` binding) | — |
| Lookup failure reasons and their verification tests: `class-scope-bound` for an open namespace (metaclass, inherited `__prepare__` via a base, a keyword; 12 probes) and for a binding in the class; `dynamic-scope` for an annotation use; `unmapped` for a mangled alias; `star-import`; `conditional` and `mixed-bindings` imports; `local-variable` for a recorded write; `builtin-shadow`. Reachable but fail closed (the president's AD-4): a poisoned scope and the `__class__` cell give `none` at the use site, so verification fails closed. Unreachable at a use site: a missing `nonlocal` target (a syntax error) and `dynamic-scope` from a class body or frame locals (the file is already dynamic) | `tests/test_call_resolution_tier1_py.py` |
| Runtime trace (fold-28 probes, 51 cases): the 12 open-class body and first-iterable cases run the replacement and were WRONG at 0e96b12f; they fail closed now. Methods and comprehension bodies in open classes, plain classes and function scope run the builtin and resolve. Nothing else changes | — |
| Cost: 0 of 638 supported non-test stdlib files and 0 of 488 supported repository test files change against 0e96b12f. Harness against main unchanged (byte-identical `cmp`); the president's p44–p62 and panel A (38) unchanged | — |
| AC nits: the alias paragraph's example is `ns.get('p')`; the `'__dict__'` wording is "subscript key" | §7.3 |
| Pins: `test_fold28_695_open_class_callees_keep_their_off_mode_edge` (12: the Codex repro and `len`/`dict.update`/`operator.setitem` in a metaclass, an inherited-`__prepare__` and a keyword class body, plus three first iterables; all wrong at 0e96b12f), `test_fold28_695_class_nested_scopes_still_resolve` (12: methods and comprehension bodies), `test_fold28_695_plain_scopes_still_resolve` (9 controls), `test_fold28_695_lookup_failures_fail_verification` (9 reasons; 6 only the lookup catches). Mutation: no use-site lookup 19 failures, builtin verified by any `none` 13, event check removed 15, recorded-write check removed 10 | `tests/test_call_resolution_tier1_py.py` |

### PR 5: Tier 2 TS/JS

`call_resolution="imports"` is introduced. `js` fact version 10 (the export
table, star exports, CommonJS reach and taints, exact decoding, the member
of a namespace member call); `python` stays 30. All 31 PR 5 rows of §10
hold as planned (10 resolve, 21 stay unchanged), asserted by their
`imports` fields. `structural` output is byte-identical to main on every
harness run.

| Item | Applied in |
| --- | --- |
| O-1 decided (a) by the owner: more than one existing variant gives `ambiguous-extension`; resolve only when exactly one exists | §1; §9.2; §10.2; §13.1; §15 O-1 and owner notice |
| Owner rule: specifiers and quoted names decoded exactly per ECMAScript, or fail closed; raw text never compared | §9.1 (`chunker/call_resolution/js_strings.py`) |
| Executive scope rule (R12): each cheap trigger closed (CommonJS reach, taints, specifier forms, suffix siblings, directory `package.json`); the rest named | §9.2; §9.3; §15 R12 (TS/JS), treesitter-chunker#702 |
| PR 4 lessons designed in: sensitive-value uses (namespace imports, `require`, `module`) classified by closed allow-lists after unwrapping wrappers; namespace uses found by the ordinary lookup at the use site; every import form treated alike | §9.3 (`chunker/call_resolution/js_modules.py`) |
| Namespace member calls: two segments, member read from the tree, reference and tree must agree | §9.1; `engine.decide`, `engine.proof` |
| Plan nit (the president's AD-4): fold 28's `__class__` and poisoned-scope reasons are reachable but fail closed | Appendix B, fold 28 |
| Lanes: `tests/test_call_resolution_tier2_js.py` in `CI_SMOKE_TESTS` and `run_platform_core.py` | §13.2 |
| Pins: `test_tier2_positives_resolve_end_to_end` (26), `test_tier2_near_misses_keep_their_off_mode_edge` (65), `test_expected_imports_tables_hold_at_this_head`, `test_expected_imports_rows_per_pr_are_pinned` (`{5: 31}`), imports-mode mutation proofs M3, M7, M11, M14, M15 in `tests/test_call_resolution_identity.py`. Rule mutations: 35 of 35 killed (each rule disabled in turn fails a named test) | `tests/test_call_resolution_tier2_js.py`; `tests/test_call_resolution_engine.py`; `tests/test_call_resolution_identity.py` |

### PR 5: fold 1 (#703 panels A, B, C; executive rulings E5-1..E5-6)

`js` fact version 11; `python` stays 30 with unchanged digests. No expected
row changes; the off-mode baseline is untouched.

| Item | Applied in |
| --- | --- |
| CI: the three new modules join `_REQUIRED_WHEEL_PAYLOAD` (346 files) | `chunker/build/builder.py`; `tests/test_supported_wheel_verification.py` |
| E5-1 A1 import-binding writes taint; A2/B-5 verified namespace members and `this`-free calls; B-4 module-level `this` by the exhaustive scope rule | §9.9; `js_modules.py`, `modules.build_module_run` |
| E5-2 use-site lookups for `module`, `exports`, `require` and the module-system identifiers | §9.9 |
| E5-3 run-wide causes narrowed, `none(run-tainted:<cause>)` plus a log line; unparsed files text-scanned | §9.8; §9.9 |
| E5-4 lenient taints for rejected specifiers | §9.9 |
| E5-5 dot segments, symlinks (facts and on-mode cache key), exact other-extension files, cooked templates | §9.9; `adapter._cache_key_payload` |
| E5-6 R12 (TS/JS) additions on #702 | §15 |
| Cost reliefs: `typeof import()`, `extends ns.Base`, JSX `<ns.Comp />` | §9.9 |
| M15 in the mutation table; Q1 list pinned as closed | §11.3; `test_inert_sibling_segments_are_a_closed_list` |
| Rule mutations: `scripts/call_resolution_tier2_mutations.py` (reproducible; covers panel B's 13 survivors) | — |
| Pins: `test_fold1_near_misses_keep_their_off_mode_edge`, `test_fold1_positives_resolve_end_to_end`, `test_symlinked_files_fail_closed`, `test_unparsed_file_without_text_shuts_off_the_run`, `test_the_shutoff_is_logged`, `test_text_scan_of_an_unparsed_file`, `test_symlinked_files_change_the_on_mode_cache_key` | `tests/test_call_resolution_tier2_js.py` |

### PR 5: fold 2 (owner decision O-2, "scope by caller")

`js` fact version 12 (every static specifier, `module_bindings["imports"]`);
`python` stays 30 with unchanged digests. No expected row changes.

| Item | Applied in |
| --- | --- |
| O-2 recorded as an owner decision | §1; §15 O-2 |
| Closed path-based classifier; `e2e`/`cypress`/`playwright` proposed, not added | §9.9; `modules.TEST_NAME_SEGMENTS`, `modules.TEST_DIRECTORIES` |
| Promotion fixpoint over static imports, re-exports, literal loaders and lenient taints | §9.9; `modules._production_files` |
| Causes and taints scoped by caller; logged with their scope | §9.9; `ModuleRun.caller_taints`, `run_tainted_reason` |
| R12 (TS/JS): misclassified files | §15 |
| Pins: `test_test_file_causes_are_scoped_to_test_callers` (6), `test_production_causes_stay_run_wide`, `test_a_test_file_production_reaches_is_promoted`, `test_promotion_is_transitive` (4), `test_an_unreached_test_helper_stays_test_scoped`, `test_an_uncomputable_production_edge_promotes_every_test_file`, `test_test_classifier_entries`, `test_test_classifier_near_misses`, `test_test_classifier_is_closed`, `test_the_shutoff_log_names_its_scope`; 14 O-2 rule mutations | `tests/test_call_resolution_tier2_js.py`; `scripts/call_resolution_tier2_mutations.py` |

### PR 5: fold 3 (closed allow-lists for three run-wide causes)

`js` fact version 13; `python` stays 30 with unchanged digests. No expected
row changes.

| Item | Applied in |
| --- | --- |
| `module`/`node:module` imports: `builtinModules`, `isBuiltin` (reads and calls only), type-only imports | §9.9; `js_modules.INERT_MODULE_EXPORTS`, `_inert_module_import` |
| `createRequire` as a local require function: one `const`, literal calls (which taint) and `r.resolve(<literal>)` | §9.9; `js_modules._local_require` |
| `.constructor`: `.name`, `===`/`!==`/`==`/`!=`/`instanceof`, `typeof` | §9.9; `js_scope._safe_constructor_read` |
| Runtime trace of each safe claim | §9.9 |
| Pins: `test_fold3_safe_uses_leave_the_run_on` (5), `test_fold3_unsafe_uses_stay_run_wide` (31), `test_fold3_create_require_literal_calls_taint_their_target`, `test_fold3_allow_lists_are_closed`; 16 new rule mutations (two equivalent ones are recorded as such in the script) | `tests/test_call_resolution_tier2_js.py`; `scripts/call_resolution_tier2_mutations.py` |

### PR 5: fold 4 (the president's review at ec86f20c, P5-1..P5-3)

`js` fact version 14 (`uncomputable` edges, createRequire bases, module
mocks); `python` stays 30 with unchanged digests. No expected row changes.

| Item | Applied in |
| --- | --- |
| P5-1 createRequire base on a closed list; other bases are uncomputable (`unresolvable-writer`, promotion) | §9.9; `js_modules._own_file_base` |
| P5-2 a directory symlink under the root promotes every test file (option 1) | §9.9; `symbol_graph.has_directory_symlink`; `modules.build_module_run` |
| P5-3 closed list of test-framework module mocks; relative literals taint, non-literals are uncomputable | §9.9; `js_modules.MODULE_MOCKS` |
| Item 4 `#x`, absolute, `file:` and `import.meta.glob` targets are uncomputable | §9.9; `modules._uncomputable_specifier`; R12 (TS/JS) |
| Item 5 the graph-studio `"createRequire"` string-data rule is not narrowed here (executive follow-up) | — |
| Pins: `test_p5_1_president_repros_fail_closed` (2), `test_p5_1_other_bases_make_targets_uncomputable` (6), `test_p5_1_shadowed_filename_is_not_the_file`, `test_p5_1_own_file_bases_taint_exactly` (3), `test_p5_2_directory_symlink_promotes_every_test_file`, `test_p5_2_without_directory_symlinks_o2_scoping_holds`, `test_p5_2_unknown_directory_symlinks_promote`, `test_p5_3_module_mocks_taint_for_test_callers` (8), `test_p5_3_mock_near_misses` (3), `test_uncomputable_production_targets_promote_every_test_file` (6), `test_uncomputable_writer_specifiers`; 14 new rule mutations | `tests/test_call_resolution_tier2_js.py`; `scripts/call_resolution_tier2_mutations.py` |

### PR 5: fold 5 (the president's re-check at 3344e9db, P5-13..P5-18)

`js` fact version 15 (`filename_taints`, unwritten bases); `python` stays 30
with unchanged digests. No expected row changes.

| Item | Applied in |
| --- | --- |
| P5-13 `__filename` unbound, unwritten, CommonJS or no global writer; `import.meta.url`/`.filename` with no `import.meta` write | §9.9; `js_modules._own_file_base`, `_import_meta_written`; `modules.build_module_run` |
| P5-14 specifiers through a skipped directory are uncomputable | §9.9; `modules.lenient_targets` |
| P5-18 case-insensitive `file:`, uncomputable `data:` | §9.9; `modules._uncomputable_specifier` |
| P5-16 directory junctions count as links | §9.9; `symbol_graph.has_directory_symlink` |
| Pins: `test_p5_13_bases_that_may_name_another_file` (12), `test_p5_13_unwritten_import_meta_url_taints_exactly`, `test_p5_13_commonjs_free_filename_taints_exactly` (2), `test_p5_13_esm_free_filename_taints_without_writers`, `test_p5_14_specifier_through_a_skipped_directory` (2), `test_p5_14_control_gen_link_fails_closed_through_the_flag`, `test_p5_14_write_through_a_skipped_directory_is_unresolvable`, `test_p5_18_schemes_are_case_insensitive_and_data_is_uncomputable` (3), `test_p5_16_directory_junctions_count_as_links`; 11 new rule mutations | `tests/test_call_resolution_tier2_js.py`; `scripts/call_resolution_tier2_mutations.py` |

### PR 5: fold 6 (the president's re-check at 9d180a97, P5-20, P5-21)

`js` fact version 16; `python` stays 30 with unchanged digests. No expected
row changes.

| Item | Applied in |
| --- | --- |
| P5-20 no CommonJS shortcut for `filename_taints` | §9.9; `js_modules._ModuleFacts.module_bindings` |
| P5-21 skipped directories after case folding and Win32 trailing dot/space | §9.9; `modules._skipped` |
| URL whitespace stripped before the scheme | §9.9; `modules._uncomputable_specifier` |
| R12 (TS/JS): Windows 8.3 short names; bare specifiers through `node_modules` symlinks | §15 |
| Pins: `test_p5_20_commonjs_hints_do_not_bypass_the_writer_check` (2), `test_p5_13_commonjs_free_filename_taints_exactly` (updated: fails closed with a writer), `test_p5_21_skipped_directories_match_case_and_win32_forms` (5), `test_url_whitespace_is_stripped_before_the_scheme` (4); 5 new rule mutations | `tests/test_call_resolution_tier2_js.py`; `scripts/call_resolution_tier2_mutations.py` |

### PR 5: fold 7 (the president's re-check at ae5f53a5, P5-27, P5-32)

`js` stays at 16, because the analyzer output is unchanged and the digests
pass; `python` stays 30. No expected row changes.

| Item | Applied in |
| --- | --- |
| P5-27 `filename_taints` feed the O-2 edge graph | §9.9; `modules.build_module_run` |
| Taint-source audit: every file-naming source feeds `edges[path]` or `uncomputable` | §9.9; `test_every_file_naming_source_promotes` |
| P5-32 upper-casefold, `:` segments and 8.3 short names | §9.9; `modules._skipped`; R12 (TS/JS) |
| Pins: `test_p5_27_filename_base_targets_promote` (2), `test_every_file_naming_source_promotes` (14), `test_p5_32_short_names_and_streams_are_uncomputable` (6), `test_p5_32_ordinary_segments_stay_computable`; 4 new rule mutations | `tests/test_call_resolution_tier2_js.py`; `scripts/call_resolution_tier2_mutations.py` |

### PR 5: fold 8 (Codex on 6d0aadd0: discussion_r4659759218, r4659759224)

`js` fact version 17 (the text scan's output); `python` stays 30 with
unchanged digests. `js_textscan.py` joins the wheel payload (347 files). No
expected row changes.

| Item | Applied in |
| --- | --- |
| A lexer-level scan replaces the regex fallback: certain delimiting and decoding, or `unparsed-file` | §9.9; `js_textscan.py` |
| Loader spellings exempt only as complete literal calls (plus `typeof`, static imports, `import.meta` reads, `module.exports`) | §9.9 |
| Decoded relative literals taint | §9.9 |
| P5-37 8.3 match after the trailing strip | §9.9; `modules._skipped` |
| Pins: `test_fold8_text_scan_near_misses` (15, including both Codex repros), `test_fold8_clean_unparsed_files_leave_the_run_on` (8), `test_fold8_literal_require_taints_exactly`, `test_p5_37_short_name_after_trailing_dot_or_space`; 16 new rule mutations replacing the 3 regex ones (two more are recorded as equivalent) | `tests/test_call_resolution_tier2_js.py`; `scripts/call_resolution_tier2_mutations.py` |


### PR 5: fold 9 (executive ruling E5-7; the president's re-check at a27278b7)

`js` fact version 18 (unparsed files carry empty `module_bindings`;
P5-44); `python` stays 30 with unchanged digests. The wheel payload returns
to 346 files. No expected row changes.

| Item | Applied in |
| --- | --- |
| E5-7: the text-scan fallback removed; every unparsed JS/TS file is a run-wide `unparsed-file` cause, scoped by O-2 | §9.9; `modules.build_module_run`; `facts.compute_scope_facts` |
| P5-44: module-level `arguments` uses other than `typeof`/equality are `dynamic-loader` | §9.9; `js_modules._ModuleFacts._name` |
| P5-41: the parsed path's `typeof require(...)…` chain pinned | §9.9 |
| Pins: `test_e5_7_unparsed_production_files_are_run_wide` (7: the Codex repros and P5-40..P5-43/P5-45), `test_e5_7_unparsed_test_files_are_test_scoped` (7), `test_e5_7_a_reached_unparsed_test_file_is_promoted` (2), `test_e5_7_clean_parsed_files_are_unaffected`, `test_p5_44_module_level_arguments` (3), `test_p5_44_controls` (3), `test_p5_41_parsed_typeof_require_chain_is_a_loader`; the fold-1 and fold-8 text-scan tests and mutations removed; 2 new rule mutations | `tests/test_call_resolution_tier2_js.py`; `scripts/call_resolution_tier2_mutations.py` |

### PR 5: fold 10 (the president's re-check at 9bcd20c1, P5-47..P5-49)

`js` fact version 19; `python` stays 30 with unchanged digests. No expected
row changes.

| Item | Applied in |
| --- | --- |
| P5-47 lone CR, U+2028/U+2029 or an `html_comment` node make a JS/TS file unparsed | §9.9; `facts._misread_line_terminators` |
| P5-48 a module-scope declaration of `arguments` is a `dynamic-loader` cause | §9.9; `js_modules._ModuleFacts.module_system` |
| P5-49 static field initializers and static blocks are module level | §9.9; `js_modules.module_level` |
| Pins: `test_p5_47_misread_line_terminators_are_unparsed` (8), `test_p5_47_crlf_files_stay_parsed`, `test_p5_48_module_scope_arguments_declarations` (5), `test_p5_48_function_local_arguments_declaration_is_unaffected`, `test_p5_49_static_members_are_module_level` (3), `test_p5_49_static_field_this_makes_the_module_commonjs`, `test_p5_49_instance_members_stay_unaffected`; 7 new rule mutations | `tests/test_call_resolution_tier2_js.py`; `scripts/call_resolution_tier2_mutations.py` |

### PR 5: fold 11 (the president's re-check at cc3c2d3d, P5-50)

`js` fact version 20; `python` stays 30 with unchanged digests. No expected
row changes.

| Item | Applied in |
| --- | --- |
| P5-50 (a) a `<!--` on a code byte makes a JavaScript file unparsed | §9.9; `facts._hidden_html_comment` |
| P5-50 (b) a `-->` on a code byte with only whitespace and comments before it on its line makes a JavaScript file unparsed | §9.9; `facts._hidden_html_comment` |
| Pins: `test_p5_50_hidden_html_comments_are_unparsed` (8: the six repros and the two line-start controls), `test_p5_50_html_text_outside_code_stays_parsed` (8: the no-line-break control, strings, templates, regexes, `i-->0`, and the `.ts`/`.tsx` forms), `test_p5_50_substitution_in_a_template_is_code`; 4 new rule mutations | `tests/test_call_resolution_tier2_js.py`; `scripts/call_resolution_tier2_mutations.py` |

### PR 6: Tier 2 Python (treesitter-chunker#682, closes #682 and #697)

`python` fact version 31 at the first PR 6 head (32 at fold 1, 33 at fold 2,
34 at fold 3, 35 at fold 4, 36 at fold 5, 37 at fold 6, 38 at fold 7;
`js` stays 20 with unchanged digests). 18 expected
rows gain an `imports` field (`{5: 31, 6: 18}`): 9 positives (7 resolve, 2
narrow to their import group) and 9 near-misses.

| Item | Applied in |
| --- | --- |
| Import bindings, groups and member chains (9.4) | §9.10; `py_scope.analyze`, `py_modules.import_group`, `py_modules.member_chain`, `engine._python_proof` |
| Module paths: component-wise precedence, script directory, standard-library names, skipped directories, relative imports (9.5) | §9.10; `py_modules.resolve_module`, `_resolve_parts` |
| Name lookup: export table, conflicts, hops, cycles (9.6) | §9.10; `py_modules._attribute` |
| #697: closed allow-list of module-object uses, escapes, literal acquisitions, dotted strings, exposure closure, Tier 1 module-scope proofs in `imports` mode | §9.10; `py_modules._use_position`, `_scan_uses`, `_Builder.walk_use`, `build_py_module_run`, `tier1_reason` |
| Run-wide causes (executive rule 3), Tier 1 triggers made run-wide | §9.10; `py_modules._scan_causes`, `_classify_path`, `_sys_modules`, `_frame_locals_read` |
| Parse classification (executive rule 5) | §9.10; `py_modules.parse_hazard` |
| O-2 for Python (executive rule 4) | §9.10; `py_modules.is_test_path`, `_production` |
| Lanes: `tests/test_call_resolution_tier2_py.py` in `CI_SMOKE_TESTS` and `run_platform_core.py`; wheel payload 347 files | §13.2; `chunker/build/builder.py` |
| Pins: `tests/test_call_resolution_tier2_py.py`; `test_expected_imports_tables_hold_at_this_head`, `test_expected_imports_rows_per_pr_are_pinned`; rule mutations in `scripts/call_resolution_tier2_py_mutations.py` | `tests/test_call_resolution_tier2_py.py`; `tests/test_call_resolution_engine.py` |

### PR 6: fold 1 (owner decisions O-3, O-4; executive rulings on #705)

`python` fact version 32: the fixtures' digests are unchanged, but a file
that only compiles source loses its `evaluator` cause. `js` stays at 20. No
expected row changes.

| Item | Applied in |
| --- | --- |
| O-3: ship PR 6 as designed; Python Tier 2 gains nothing on the measured trees and loses `structural` resolutions where other files may write a module | §1, §9.10 (gain table), §15 |
| O-4: keep the experimental label on `structural` and `imports` | §1, §4.5, §13.1, §15 |
| Q1: run-wide causes shut off Tier 2 only (PR 5 precedent); named writes still void the written module's Tier 1 proofs; the unknown-target writer residual | §9.10; §15 R10 (residual, treesitter-chunker#699) |
| Q2: `compile` alone is no evaluator cause | §9.10; `py_modules._EVALUATORS` |
| Q3: the loader refinement is not applied (a possible future narrowing on #699) | §15 R12 (Python) |
| Pins: `test_routes_that_cannot_change_a_module_attribute_are_no_cause` (a `compile`-only syntax check), `test_run_wide_causes_fail_closed[exec-compile]`; the `compile-is-no-evaluator` mutation | `tests/test_call_resolution_tier2_py.py`; `scripts/call_resolution_tier2_py_mutations.py` |

### PR 6: fold 2 (the president's rulings E6-1..E6-8 on #705)

`python` fact version 33; `js` stays at 20. No expected row changes. The
fixture outputs are identical to fold 1.

| Item | Applied in |
| --- | --- |
| E6-1: a module's own bindings re-checked for Tier 2 proofs (A-1, B1); a package `__init__.py` name that is also a submodule conflicts, for Tier 2 and Tier 1 (A-4) | §9.10; `engine._python_proof`, `py_modules.own_binding_reason`, `tier1_reason` |
| E6-2: every module-namespace import binding followed (`module_imports`) | §9.10; `py_modules.module_facts`, `_Builder.attr_values`, `_Builder.exposed` |
| E6-3: `import a.b as m` as attribute access; own submodule imports (`own_submodules`); `module-getattr` | §9.8, §9.10; `py_modules.resolve_import`, `_attribute`, `_own_submodules` |
| E6-4: pytest `rootdir` insertion for test importers | §9.10; `py_modules.shadow_directories` |
| E6-5: patcher targets | §9.10; `py_modules._scan_patchers` |
| E6-6: write chains taint their first attribute | §9.10; `_Builder.walk_use` |
| E6-7: `__path__`/`__spec__` reads safe | §9.10; `py_modules._SAFE_DUNDERS` |
| E6-8: module facts only in `imports`; S-1; mutation gaps; wording; CLI help and docstrings; measurement roots; this table's fact versions; "PR 4 finding O-3" | §9.10; `facts.compute_scope_facts`, `py_scope.analyze`, `_attribute`; `chunker/cli/symbol_commands.py`, `cli/main.py`, `chunker/symbol_graph.py`, `chunker/boundary/adapter.py` |
| Pins: `test_fold2_blocking_cases_keep_their_off_mode_edge` (23 panel repros, each with its CPython 3.14 result), `test_fold2_written_module_loses_its_own_tier1_proof` (6), `test_fold2_controls_still_resolve` (4), `test_fold2_package_path_read_keeps_the_packages_own_proofs`, `test_fold2_computed_patcher_targets_are_test_scoped_causes` (3), `test_fold2_structural_facts_carry_no_tier2_tables`, `test_fold2_rules_each_have_a_failing_case` (19), `test_fold2_python2_exec_statement_is_an_evaluator`, `test_fold2_init_definition_shadowed_by_a_submodule`; 35 new rule mutations (82 in all) | `tests/test_call_resolution_tier2_py.py`; `scripts/call_resolution_tier2_py_mutations.py` |

### PR 6: fold 3 (the president's review P6-1..P6-4 on #705)

`python` fact version 34; `js` stays at 20. No expected row changes. The
fixture outputs are identical to fold 2.

| Item | Applied in |
| --- | --- |
| P6-1: own-submodule imports are `from . import b` or the package's full dotted name | §9.10; `py_modules._own_submodules` |
| P6-2: no own-submodule names in an `__init__.py` with a star import | §9.10; `py_modules._own_submodules`, `_own_submodule_import` |
| P6-3: patchers follow the Tier 1 W-3 aliases and `MonkeyPatch` aliases; computed `patch.multiple`/`patch.dict` targets are causes | §9.10; `py_modules._scan_patchers`, `_monkeypatch_aliases` |
| P6-4: pytest basedirs of every collected test module and conftest, for test importers and writers | §9.10; `py_modules.pytest_basedirs`, `shadow_directories` |
| N-1: a write of `__code__`, `__closure__`, `__defaults__` or `__kwdefaults__` is a `module-object` cause | §9.10; §15 R12 (Python); `py_modules._CODE_ATTRIBUTES`, `_scan_causes` |
| N-5: #706 cited for N2; O-3 rows say "may write" | §1, §9.10, §15 |
| Pins: `test_fold3_president_cases_keep_their_off_mode_edge` (9 president's trees, each with its CPython 3.14 or pytest result), `test_fold3_controls_still_resolve` (4: `h4b`, `requests.patch`, the absolute self-import, the relative import), `test_fold3_patcher_causes_stay_test_scoped`, `test_fold3_star_init_has_no_own_submodules`, `test_fold3_star_init_rejects_recorded_own_submodules`, `test_fold3_conftest_basedir_reaches_the_writer_side`, `test_fold3_function_code_writes_are_a_cause` (5); 10 new rule mutations (92 in all) | `tests/test_call_resolution_tier2_py.py`; `scripts/call_resolution_tier2_py_mutations.py` |

### PR 6: fold 4 (the president's re-check P6-5..P6-9; executive ruling E6-9)

`python` fact version 35; `js` stays at 20. No expected row changes. The
fixture outputs are identical to fold 3.

| Item | Applied in |
| --- | --- |
| E6-9: Tier 1's E-21 closed allow-list reused for patcher values; `MonkeyPatch` a patcher kind (P6-6), no substring rule | §9.10; `py_modules._Patchers`, `_scan_patchers` |
| P6-5: in a test file, a patcher value off the allow-list is an `unresolvable-writer` cause; production unchanged (Tier 1 E-21) | §9.10; `py_modules._scan_patcher_escapes`, `module_facts(test_file=...)`, `py_scope.analyze` |
| P6-7: `getfixturevalue` of a patcher fixture yields that kind; a computed name is a cause | §9.10; `py_modules._Patchers` |
| P6-8: off-mode residual, no change | §15 R12 (Python, PR 6) |
| Pins: `test_fold4_patcher_values_are_test_scoped_causes` (9: the six president's trees, `f3_mp_getfixture`, a `getfixturevalue("mocker")` row and a computed fixture name; each with what pytest printed), `test_fold4_allow_listed_patcher_uses_keep_their_exact_taints` (3), `test_fold4_production_patcher_values_are_no_cause`; 10 new rule mutations, one replaced (102 in all) | `tests/test_call_resolution_tier2_py.py`; `scripts/call_resolution_tier2_py_mutations.py` |

### PR 6: fold 5 (the president's re-check P6-10..P6-16; executive ruling E6-9a)

`python` fact version 36; `js` stays at 20. No expected row changes. The
fixture outputs are identical to fold 4.

| Item | Applied in |
| --- | --- |
| E6-9a / P6-13: the patcher-escape scan runs in every Python file; causes O-2-scoped by the file's own classification | §9.10; `py_modules.module_facts`, `_scan_patcher_escapes` |
| P6-10: `syspath_prepend` on a MonkeyPatch is `module-system` | §9.10; `py_modules._scan_patchers` |
| P6-11: MonkeyPatch aliases safe only as unreachable bindings | §9.10; `py_modules._Patchers._local_alias`, `safe_use` |
| P6-12, P6-15: `getfixturevalue` by alias or `getattr` is a computed fixture | §9.10; `py_modules._Patchers` |
| P6-14: annotation positions without a call in between | §9.10; `py_modules._ANNOTATION_PARTS`, `_Patchers.safe_use` |
| Pins: `test_fold5_president_cases_keep_their_off_mode_edge` (9 president's trees, each with what CPython 3.14 or pytest printed), `test_fold5_syspath_insert_control`, `test_fold5_production_patcher_causes_stay_production_scoped`, `test_fold5_local_aliases_and_plain_annotations_stay_safe`; fold 4's production control removed (E6-9a); 6 new rule mutations, one removed (107 in all) | `tests/test_call_resolution_tier2_py.py`; `scripts/call_resolution_tier2_py_mutations.py` |

### PR 6: fold 6 (the president's re-check P6-17..P6-20; executive ruling E6-9b)

`python` fact version 37; `js` stays at 20. No expected row changes. The
fixture outputs are identical to fold 5.

| Item | Applied in |
| --- | --- |
| E6-9b / P6-17: MonkeyPatch methods on any receiver (except `operator`), by name as a call argument and as a method reference | §9.10; `py_modules._scan_patch_methods`, `_patch_method_call`, `_operator_module`, `_argument_string` |
| P6-18: string spellings of `getfixturevalue` closed by E6-9b; the family named | §9.10; §15 R12 (Python, PR 6) |
| Redundant MonkeyPatch receiver tracking removed (folds 3–5) | §9.10; `py_modules._Patchers` (pytest-mock fixtures only), `_scan_patcher_escapes`, `_scan_patchers` |
| P6-19: Tier 1 E-21 gap, follow-up | §15 R12 (Python, PR 6) |
| Pins: `test_fold6_monkeypatch_methods_on_any_receiver` (19: the eight P6-17 and four P6-18 president's trees, five method-name spellings, a splat and a pytest-mock fixture handed on; each with what pytest printed), `test_fold6_controls_keep_their_treatment` (5, with `operator.setitem`), `test_fold6_syspath_prepend_on_any_receiver` (2); 7 new rule mutations, 9 removed with the code they targeted, 6 re-anchored (107 in all) | `tests/test_call_resolution_tier2_py.py`; `scripts/call_resolution_tier2_py_mutations.py` |

### PR 6: fold 7 (the president's re-check P6-21..P6-26)

`python` fact version 38; `js` stays at 20. No expected row changes. The
fixture outputs are identical to fold 6.

| Item | Applied in |
| --- | --- |
| P6-21: constant names in any `_constant_string` spelling, positional or keyword value | §9.10; `py_modules._argument_string`, `_NAME_STRING_NODES` |
| P6-22: constant names as subscript keys | §9.10; `py_modules._argument_string` |
| R12 sentence corrected: the computed-name residual | §15 R12 (Python, PR 6) |
| Pins: `test_fold7_method_names_by_constant_expression` (9: seven president's trees, a `syspath_prepend` concatenation and a `getfixturevalue` `+` row; each with what pytest printed), `test_fold7_computed_method_name_is_r12`, `test_fold7_other_constant_names_record_nothing`; 3 new rule mutations (110 in all) | `tests/test_call_resolution_tier2_py.py`; `scripts/call_resolution_tier2_py_mutations.py` |

### PR 6: fold 8 (Codex review r4661935648)

`python` fact version stays 38 (the analyzer's facts are unchanged); `js`
stays at 20. No expected row changes. The fixture outputs are identical to
fold 7.

| Item | Applied in |
| --- | --- |
| One proof resolver for import bindings: direct imports, import groups and every re-export hop | §9.10; `py_modules._resolve_binding`, `resolve_import`, `_attribute` |
| One writer-side resolver: module path plus the attribute walk | §9.10; `py_modules._Builder.module_values`, `binding_values`, `walk_use` |
| P6-31: R12 example list widened | §15 R12 (Python, PR 6) |
| Pins: `test_fold8_reexported_bindings_use_the_one_resolver` (7: the Codex repro, `facade.m.t()`, two hops, `from facade import m as n`, a re-exported `from a import b`, and two writer rows; each with what CPython printed), `test_fold8_clean_reexports_still_resolve` (2); 2 new rule mutations, 2 re-anchored (112 in all) | `tests/test_call_resolution_tier2_py.py`; `scripts/call_resolution_tier2_py_mutations.py` |

### Follow-up: treesitter-chunker#694 (comma writers before `.call`/`.apply`/`.bind`)

`js` fact version 21; `python` stays 38. The fixture facts are unchanged
apart from the version (every `js` digest moves only because the version is
hashed with the facts). No expected row changes. Only adds `none`.

| Item | Applied in |
| --- | --- |
| A comma or parenthesized writer before `.call`/`.apply`/`.bind` (`(0, Object.assign).call(null, this, …)`, `.apply(null, [this, …])`), at any depth, with optional chaining, is a property writer | §7.2 script goal; `js_scope._callee`, `_Analysis._writer_targets` |
| A bound writer called later (`Object.assign.bind(null)(this, …)`, `.bind(null).bind(null, this)(…)`), nested invokers (`Object.assign.call.call(…)`) and a computed invoker on any writer chain | §7.2; `_Analysis._writer_targets`, `_writer_chain` |
| `Reflect.apply(Object.assign, null, [this, …])` (also through a computed key on `Reflect`); a comma namespace (`(0, Object).assign`), a comma target (`Object.assign((0, this), …)`) and comments between arguments | §7.2; §15 R11; `_Analysis._writer_namespace`, `js_scope._arguments` |
| The #717 review: the comment-aware reading dropped `*` that the positional reading of js 20 gave (`Object.assign.call(/* c */ this, this ?? {}, …)`, the same through `.apply`/`.bind` and `Reflect.set`; 512 of the review's 11,340 generated forms, 384 of which node v24 confirmed replace the global). The positional reading now runs first and is never overridden, so every call main flagged is still flagged: 0 of 11,340 forms are flagged by main and not here | §7.2; `_Analysis._property_writer_call`, `_positional_writer_call` |
| Pins: `test_694_writer_invokers_fail_closed` (25 forms; node v24 confirms each writes the global through `this`, except `(0, Object.assign.call)(…)`, which throws and stays `*` as before), `test_694_writer_invokers_on_other_targets_are_not_wildcards` (9 controls), `test_694_writer_invoker_on_a_fresh_object_still_resolves`, `test_694_issue_forms_keep_name_mode_identical_to_off` (2), panel rows `I694-call` and `I694-apply`; `test_717_main_writer_wildcards_are_kept` (11 forms main flagged, each `none(reassigned)`), `test_717_commented_invoker_receiver_keeps_the_edge_unresolved`; 10 new rule mutations (`717-positional-floor` drops the floor) | `tests/test_call_resolution_tier1_js.py`; `scripts/call_resolution_tier2_mutations.py` |

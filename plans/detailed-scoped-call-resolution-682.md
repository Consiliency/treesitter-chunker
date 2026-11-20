---
automation:
  suite_command: "uv run --locked --with toml --all-extras python scripts/run_full_suite.py"
---

# Scope-aware call resolution, opt-in (treesitter-chunker#682)

Status: plan for board and president review. No product or test code is
written until this plan is approved. Releasing the feature is a separate owner
question; no PR in this plan cuts a release.

## 1. Decisions at a glance

| Topic | Decision |
| --- | --- |
| Opt-in surface | A new keyword-only option, `call_resolution`, orthogonal to `resolution_mode`. Values `"name"` (default, today's behavior), `"structural"` (Tier 1) and `"imports"` (Tier 1 + Tier 2). Not a `resolution_mode` value and not a `SemanticResolver`. |
| What can change | Only call edges that are `ambiguous` today (2+ candidates). Only `target`/`to`, `resolution`, `candidates`, `is_internal`, plus two additive provenance keys, on those edges. Derived counts follow. |
| Core rule | Remove-only. Each rule may only drop candidates from today's set. A rule that would leave zero candidates is skipped. The edge is `resolved` only when exactly one candidate remains. |
| Which calls | Bare-identifier callees (`t()`, `new Box()`) for Tier 1 and Tier 2. Namespace-import member calls (`ns.f()`, `m.f()`) for Tier 2 only. Every other member call (`self.m()`, `obj.m()`, `globalThis.f()`) is untouched, so dynamic dispatch stays ambiguous. |
| Where facts come from | A new per-file scope pass over the tree-sitter tree, run only when the option is on. The metadata extractors are not changed, because their output is part of node metadata and must stay byte-identical when the option is off. |
| Python redefinitions | Never resolved. Narrowed to the redefinition group, which stays `ambiguous` (owner decision, 2026-11-20; section 8). |
| JS redefinitions | Hoisted plain-JS function declarations in one function or script scope resolve to the last one. TS duplicate bodies stay `ambiguous`. TS overload sets resolve to their single implementation. |
| IDs | No ID input changes. `definition_id`, `node_id`, `#N` and `call_site_id` are byte-identical on and off; a test harness proves it for every fixture. |
| Schema and cache | Boundary IR stays `3.0`; the new provenance keys are additive. Off-mode cache keys are unchanged; on-mode keys add `call_resolution`. |
| Delivery | Five stacked PRs: surface, harness and kind filter; Tier 1 TS/JS; Tier 1 Python; Tier 2 TS/JS; Tier 2 Python. No heavy local runs on dev0; full validation in CI. |

## 2. Problem and motivating failure

`chunker/symbol_graph.py` resolves a call reference by name only.
`_build_resolution_indexes` indexes every symbol in the run by `qualified_name`
and by `name`. `_resolve_reference_candidates` returns an exact
`qualified_name` match if one exists, otherwise the union of name matches over
the reference's tokens, including member-chain parts.
`_resolve_call_reference_candidates` first applies a syntax guard: only plain
identifier and member chains are looked up. `_resolution_status` turns one
candidate into `resolved`, two or more into `ambiguous` and none into
`unresolved`. Nothing looks at scope, imports, module paths, symbol kind or
language.

5.x hid the collisions by keying symbols `module_stem:qualified_name`, so the
last definition won. On Greenfield's `r9-ts` tree, 5.3.0 kept only
`web/svc.tsx`'s `t`: six of the seven `t` calls in `web/svc.ts` resolved to the
wrong file (evidence `r9-ts-5.3.0.txt`). The probe tree shows the same thing for
`svc.ts`/`svc.tsx` and for `pkg.py`/`pkg/__init__.py`. **That misattribution is
the failure the exactly-one-target rule guards against:** a rule may only remove
candidates it can prove wrong, and an edge resolves only when one candidate is
left. No rule may pick a winner among candidates it cannot tell apart.

treesitter-chunker#496 (6.0.0) gave every definition its own ID, which exposed
the collisions as `ambiguous` edges. Greenfield (ViperJuice/greenfield#48, O-5)
then either drops those edges or over-approximates them.

## 3. Baseline evidence (current main)

Run on main `f213f1c2` (7.0.0 plus test-only changes), Python 3.14.10,
`uv run --locked --all-extras`. Greenfield's trees were copied out of
`/home/viperjuice/workspace/tmp/gf48-probes/` first. All 31 copied files (18
tree files and 13 upstream IRs) match
`evidence-manifest.sha256`, whose own sha256 is
`40575a9bd9612fd1d307dda1e8e94f0ca7af5dff19659ca45cbb7fad649a1e46`.

### 3.1 Call edges today, and against Greenfield's 6.0.0 IRs

The 6.0.0 column compares main's Boundary IR with
`r1/out/upstream-<tree>.json`, edge by edge, by `id`.

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
| rt-java | no edges | identical | none |
| rt-kotlin | no edges | identical | none |
| clo-go, clo-kotlin, clo-rust | 4 unresolved; none; 6 unresolved | (no 6.0.0 IR) | — |

The one 6.0.0 difference: in rt-pyrec, `uses_c2 → C().c` was `ambiguous` with
both `C` classes in 6.0.0. It is `unresolved` with no candidates on main. That
comes from the 7.0.0 complex-callee guard (commit `b8e992aa`), not from this
work. Greenfield should expect it when moving from 6.0.0 to 7.x.

### 3.2 The ambiguous edges this work targets

| Tree | Call (file:line, caller → reference) | Candidates today |
| --- | --- | --- |
| r9-ts | `svc.ts:4` A.m → `t` | svc.ts `t`, svc.tsx `t` |
| r9-ts | `svc.ts:5` A.m2 → `t` (×2) | same |
| r9-ts | `svc.ts:9` d → `t` (×2) | same |
| r9-ts | `svc.ts:12`, `:13` caller → `d` | svc.ts:8 `d` (overload signature), svc.ts:9 `d` (implementation) |
| r9-ts | `svc.ts:14` caller → `t` | svc.ts `t`, svc.tsx `t` |
| r9-ts | `svc.tsx:2` View → `t` | same |
| r9-py | `svc.py:16` C.b → `C` | class C @9, class C @14 |
| r9-py | `svc.py:31` caller → `d` | d @19, d @24 |
| rt-pycond | `svc.py:21` caller → `d` | d @13 (if branch), d @16 (else branch) |
| rt-pyrec | `svc.py:23` d → `d` | d @18, d @22 |
| rt-pyrec | `svc.py:27` uses_c2 → `C` | class C @5, class C @10 |
| rt-js | `k.js:9` g → `d` | d @3, d @6 |
| probe | `over.ts:6` g → `f` | f @1, f @2 (signatures), f @3 (implementation) |
| probe | `over.ts:6` g → `new Box` | interface Box @4, class Box @5 |
| probe | `svc.ts:2` caller → `t` (×2); `use.ts:2` user → `t` | svc.ts `t`, svc.tsx `t` |
| probe | `c.py:4` use → `helper` | a.py `helper`, b.py `helper` |
| probe | `pkg/__init__.py:5` call_k → `k` | pkg.py `k`, pkg/__init__.py `k` |
| probe | `redef.py:11` caller → `d` | d @1, d @4 |

### 3.3 What chunk metadata exposes today

Checked with `chunk_file(..., extract_metadata=True,
include_retrieval_metadata=True)` on probe files covering every form below.

| Fact | Exposed? | Notes |
| --- | --- | --- |
| Symbol kind | Yes, `metadata.kind` | TS: `function`, `method`, `class`, `interface`, `type`, `enum`, `module` (namespaces and `declare module`). Python: `function`, `method`, `class`. |
| Parent / qualified name | Yes, `parent_symbol`, `qualified_name` | The parent's name only, not its kind. Blocks never appear (`useAll.blockFn`). |
| TS overload signatures | Yes, as separate symbols | `node_type == "function_signature"` (or `method_signature` in classes), kind `function`/`method`, no `signature` key. Not recorded in the symbol record; `chunk.node_type` has it. |
| `declare` forms | Yes | `declare function` → `function_signature`, empty parent context. `declare global {}` members look top-level. |
| Arrow-function consts | Yes | The `arrow_function` chunk is a symbol with name `<anonymous>` and `qualified_name` set to the const name; the `variable_declarator` chunk is not a symbol. |
| Interface members | Yes | `method_signature`, kind `method`, parent the interface. |
| Imports (TS/JS) | Partly | `import_statement` chunks carry raw strings in `imports` and names in `dependencies`; not structured, aliases lost. |
| Imports (Python) | **No** | Module-level imports produce no chunk, so no import facts at all. |
| Exports | Partly | `exports` is a name set mixing locals and parameters (Python lists `self`, parameter names). Not usable as an export table. |
| Scopes, parameters, locals, conditionals | **No** | Not represented. |
| Python decorators | Partly | `decorated_definition` wraps the def; decorator names appear in `dependencies`. |

Conclusion: Tier 1 and Tier 2 need facts the metadata does not hold. Adding
them to the metadata extractors would change node metadata, and node records
are part of Boundary IR, so off-mode output would change. **The plan adds no
extractor changes.** A separate scope pass reads the tree directly (section 5).

## 4. Opt-in surface

### 4.1 Options weighed

| Option | Verdict | Why |
| --- | --- | --- |
| New `resolution_mode` value | Rejected | `strict`/`permissive` is an enforcement label (Boundary adds `provenance.enforcement_grade`), not a resolver choice; today it changes no candidate sets. A third value would make "strict plus scoped" impossible, and `resolution_mode` is a closed enum in `boundary_ir.schema.json` and `RESOLUTION_MODES`, so consumers that validate it would break. |
| First-party `SemanticResolver` | Rejected for this work | Semantic resolvers **add** separate edges whose IDs hash the target (`_semantic_edge_record`), under schema `3.1` with `source: "semantic"`. Consumers would see a second edge per call instead of today's edge narrowed, which breaks both "call-edge IDs unchanged" and "same shape as today's resolved edges". The resolver context also has only nodes and edges, not trees. It stays the right home for later language-server, receiver-typed resolution. |
| New orthogonal option | **Chosen** | Narrows today's call edges in place, so `call_site_id`, shape and joins stay as they are. Composes with both `resolution_mode` values and with semantic resolvers. |

### 4.2 API

- Type and constants in `chunker/types.py`, re-exported from
  `chunker.boundary.types`:
  `CallResolution = Literal["name", "structural", "imports"]` and
  `CALL_RESOLUTION_MODES = ("name", "structural", "imports")`. Values are
  cumulative: `imports` includes every Tier 1 rule.
- Keyword-only parameter `call_resolution: CallResolution = "name"` on:
  `extract_symbol_graph`, `extract_symbol_facts_for_file`,
  `assemble_symbol_graph`, `extract_boundary_ir` (cold and incremental paths),
  `_extract_file_cache_record` and `_cache_key_payload`. Existing positional
  parameters keep their positions. An unknown value raises `ValueError`, like
  `resolution_mode`.
- CLI: `--call-resolution {name,structural,imports}` (default `name`) on
  `symbols extract` (`chunker/cli/symbol_commands.py`) and on the `boundary`
  command (`cli/main.py`). No other command gains the flag; `find_symbols`,
  clustering and graph exporters keep calling with the default.
- `assemble_symbol_graph` with a value other than `name` requires every fact to
  carry `scope_facts` (section 5.2) and raises `ValueError` otherwise, so off-mode
  facts can never be silently assembled as on-mode.
- `imports` is introduced in PR 4, so no value ever does less than its name
  says. PRs 1–3 accept `name` and `structural`.

### 4.3 Output when the option is on

- **Symbol graph.** A call relationship whose candidate set changed gets new
  `to`, `resolution`, `candidates` and `is_internal`, and two provenance keys:
  `call_resolution` (the mode) and `call_rules` (rule IDs that removed
  candidates, in application order, for example
  `["t1.lexical", "t1.ts_overload"]`). Unchanged edges keep today's
  provenance exactly. `metadata.call_resolution` is added to the graph metadata.
- **Boundary IR.** `_edge_record` builds provenance from scratch today; it will
  copy `call_resolution` and `call_rules` from the relationship when present.
  `run.options.call_resolution` is added. `metrics.resolved_edges` and
  `metrics.ambiguous_edges` change because they count edges;
  `unresolved_edges` and `edges_total` cannot change. Canonical edge order sorts
  by `source, target, type, id`, so a narrowed edge can move within `edges`;
  consumers must key on `id`, which the spec already requires.
- **When off.** None of these keys appear; output is byte-identical to today.
- **Resolved shape.** A resolved edge is exactly today's resolved shape: symbol
  graph `to` is the symbol ID (`definition_id` or `node_id`, with `#N`);
  Boundary `target` is the Boundary node ID that `symbol_indexes` maps it to;
  `resolution == "resolved"`; `candidates == [target]`; `is_internal` true.

### 4.4 Schema and cache

- `boundary_ir.schema.json`: document optional `provenance.call_resolution`
  (enum `structural`, `imports`) and `provenance.call_rules` (array of strings)
  on edges, and `run.options.call_resolution`. Both objects already allow
  additional properties, so this is additive under the spec's compatibility
  policy and `schema_version` stays `"3.0"` (`"3.1"` when semantic resolvers
  are also on, as today).
- Cache: no `BOUNDARY_CACHE_VERSION` bump and no change to
  `BOUNDARY_CACHE_KEY_FIELDS`. Following the semantic-resolver pattern,
  `_cache_key_payload` adds `call_resolution` and `call_resolution_version`
  (an internal constant, bumped whenever a PR changes the per-file scope
  facts) **only when the mode is not `name`**, and `_build_boundary_cache_key`
  hashes them. Off-mode keys and records are unchanged and still reused.
  On-mode records live under different keys. An on-mode record with missing
  or malformed `scope_facts` is a safe miss and is re-extracted.
- Rules run at assembly, on every run, from cached per-file facts. As today,
  adding an unrelated file can change a call's resolution without changing its
  `call_site_id`.

## 5. Architecture

### 5.1 New module

`chunker/call_resolution/`:

- `engine.py`: eligibility, rule order, the remove-only guard, provenance.
  Pure functions over facts and `symbol_lookup`; no filesystem access, so cold
  and incremental runs agree.
- `js_scope.py`: one analyzer for `javascript`, `typescript` and `tsx` trees.
- `py_scope.py`: Python analyzer.
- `modules.py`: Tier 2 module-path resolution and export/re-export following.

### 5.2 Per-file scope facts

When the mode is not `name`, `extract_symbol_facts_for_file` re-parses the file
with `get_parser(language)`. It parses exactly the buffer core parses (the
replacement-decoded UTF-8 and, for Python, the `_lone_cr_parse_copy`
substitution, which keeps offsets), so byte spans line up with `call_spans`.
It stores a JSON-serializable `facts["scope_facts"]`:

- `version`, `language`, `supported` (false for other languages, or when the
  tree has errors: fail closed).
- `goal` for JS/TS: `module` if the file has a top-level `import` or `export`
  (including `export {}`), else `script`.
- `bindings`: one entry per call fact, keyed by callee byte span, giving the
  scope-lookup outcome (section 6.2).
- `script_globals`: for script-goal JS/TS files, names declared at top level.
- `exports` (Tier 2): the module's export table, local names, re-exports and
  star sources, with raw specifiers.
- `module_bindings` (Tier 2, Python): module-scope name → binding kind
  (definition group, import, other).

Declarations map to symbol IDs by `(node_type, byte_start, byte_end)` against
the file's symbol chunks: the `function_declaration` inside `export_statement`,
the `arrow_function` for an arrow const, the `function_definition` inside
`decorated_definition`. A declaration that maps to no symbol is treated as a
non-symbol binding, which never narrows. Fixture tests assert that every
function-like declaration in every fixture maps.

`facts["scope_facts"]` is not emitted in the symbol graph or Boundary IR; it is
stored only in incremental cache records under on-mode keys. The third parse
happens only when the option is on.

## 6. Rule engine

### 6.1 Eligibility

A call edge is processed only when all of these hold:

1. The mode is not `name`.
2. The caller's file language is `python`, `javascript`, `typescript` or `tsx`,
   and its scope facts are `supported`.
3. Today's candidate set `C0` has **two or more** entries. Resolved and
   unresolved edges are never touched, so the option cannot change any edge
   that is not ambiguous today.
4. The reference is a bare identifier (`[A-Za-z_][A-Za-z0-9_]*`), or, for
   Tier 2 only, a namespace member chain whose head binds to a namespace or
   module import (section 7).

### 6.2 Scope-lookup outcomes

The per-file pass gives each eligible call one outcome:

- `local(G)`: the innermost scope that binds the name binds it only through
  symbol definitions in this file; `G` is that set of symbol IDs.
- `import(b)`: the name binds to an import; `b` is the specifier and imported
  name.
- `none(reason)`: a parameter, local variable, `catch` or loop variable,
  reassignment, conditional mix, star import, `eval`/`with`, ambient-only
  declaration, unknown construct, or no binding in the file (globals and
  builtins).

### 6.3 Order and conflicts

```
C := C0                                            # |C0| >= 2
1. t1.kind      C' := callable(C); if C' nonempty and C' != C: C := C'
2. lookup       outcome := bindings[callee span]
   local(G)     G' := group_rule(G)                # 8.x; may be "none"
                X := C ∩ G'; if X nonempty and X != C: C := X   (t1.lexical + group rule id)
   import(b)    only in "imports" mode:
                T := resolve(b) (bounded hops); G' := group_rule(T) in the target module
                X := C ∩ G'; if X nonempty and X != C: C := X   (t2.import or t2.namespace)
   none         no change
3. |C| == 1 → resolved, else ambiguous with sorted C (|C| >= 2)
```

- Every step either removes candidates or is skipped. A step that would empty
  the set is skipped, so an ambiguous edge always keeps two or more candidates.
- Tier 1 and Tier 2 never compete: the innermost binding decides. A local
  definition shadows imports; an import binding means Tier 1 makes no lexical
  choice (in `structural` mode the edge only gets `t1.kind`).
- A name with both a local definition and an import in one scope is an error in
  TS (duplicate identifier) and a sequential rebinding in Python; both give
  `none` (TS) or the redefinition-group policy (Python).
- `t1.kind` runs first and alone can narrow and resolve, as the issue
  specifies. Its provenance (`call_rules == ["t1.kind"]`) lets a consumer tell
  a kind-only narrowing from a binding-proven one (open question Q3).

## 7. Tier 1 rules (`structural`)

### 7.1 `t1.kind`: callable kind and language family

Applies to every eligible edge. A candidate is removed when:

| Condition | Removed | Why sound |
| --- | --- | --- |
| Kind is `interface`, `type`, `enum`, `struct`, `trait` or `module` (namespace, `declare module`) | always | Types and namespaces are never the value a call invokes. Merged function or class declarations are separate candidates and stay. |
| Candidate language family differs from the caller's (`{javascript, typescript, tsx}` vs `{python}` vs any other) | always | A bare name cannot bind across runtimes. |
| JS family, plain call (`function`, `tagged_template` call kinds), candidate kind `class` | plain calls only | Calling a class without `new` throws. |
| JS family, `new` (`constructor` call kind), candidate kind `method` | `new` only | Method definitions are not constructors. |

Kept on purpose: methods for plain bare calls (`const { log } = console;
log()` really calls a method), classes for Python calls (`C()` instantiates),
functions for `new` (pre-class constructors).

### 7.2 `t1.lexical`, JS/TS scope chain

Node types from tree-sitter-javascript 0.25 and the pinned typescript/tsx
grammars.

- **Scopes**, innermost first: block (`statement_block`, `switch_body`,
  `for_statement`, `for_in_statement`, `catch_clause`, `class_static_block`);
  function (`function_declaration`, `generator_function_declaration`,
  `function_expression`, `generator_function`, `arrow_function`,
  `method_definition`); TS namespace body (`internal_module`, `module`); file
  (`program`).
- **`class_body` binds no bare names.** A method body's lookup skips its class
  and continues in the scope enclosing the class. Only a class *expression*'s
  own name is visible inside it.
- **Value declarations that create a symbol binding:** `function_declaration`,
  `generator_function_declaration`, TS `function_signature` (overloads and
  `ambient_declaration`), `class_declaration`, `abstract_class_declaration`,
  and a `lexical_declaration` with `const` whose `variable_declarator` value is
  an `arrow_function` or `function_expression`. TS `enum_declaration` and
  `internal_module` are value declarations but not callable.
- **Type-space declarations are ignored by the lookup:**
  `interface_declaration`, `type_alias_declaration`, `import type`.
- **Non-symbol bindings (outcome `none`):** parameters (`formal_parameters`,
  `required_parameter`, `optional_parameter`, `assignment_pattern`,
  `rest_pattern`, `object_pattern`, `array_pattern`,
  `shorthand_property_identifier_pattern`, `pair_pattern`, a lone arrow
  parameter), `catch_clause` parameter, `var` and `let` declarators, `const`
  with any other initializer, destructuring, the implicit `arguments`.
- **Hoisting:** function declarations and `var` bind across their whole
  function or program scope. A function declaration inside a block binds in
  that block. Because of Annex B sloppy-mode hoisting it also counts as a
  conditional binding in the enclosing function scope, which yields `none`
  for lookups that land there from outside the block.
- **Fail closed:** any assignment, update or compound assignment to the name in
  its binding scope; a direct `eval(...)` call or a `with` statement in a scope
  on the lookup chain; and an unrecognized declaration node.
- **Script goal:** in a script-goal file, top-level declarations are globals
  shared with other script files. A lookup that lands on a script-goal file's
  top level narrows only if no other script-goal file in the run declares the
  same name at top level (checked at assembly from `script_globals`).
- **TS namespaces:** namespace declarations with the same name merge, and
  exported members of every block are visible in each. A lookup that passes
  through a namespace body gives `none` when that namespace has more than one
  declaration in the run, or lives in a script-goal file.
- **Ambient:** a binding made only of ambient declarations (`declare`,
  `declare global`, `declare module`, `.d.ts`) gives `none`; the runtime
  implementation is elsewhere.

### 7.3 `t1.lexical`, Python scope chain (LEGB)

Node types from tree-sitter-python 0.25.

- **Scopes:** `module`, `function_definition`, `lambda`, `class_definition`,
  and comprehension scopes (`list_comprehension`, `set_comprehension`,
  `dictionary_comprehension`, `generator_expression`; the first iterable is
  evaluated in the enclosing scope).
- **Class scope is visible only to code directly in the class body.** Methods,
  nested functions, lambdas and comprehensions inside a class skip it.
- **Evaluated in the enclosing scope:** decorators, default values, and class
  bases and keywords.
- **A name assigned anywhere in a function body is local to the whole body.**
  Bindings: `function_definition`, `class_definition` (including inside
  `decorated_definition`), parameters (`identifier`, `typed_parameter`,
  `default_parameter`, `typed_default_parameter`, `list_splat_pattern`,
  `dictionary_splat_pattern`), `assignment`, `augmented_assignment`, annotated
  names without values, `for_statement` targets, `with_item` `as` targets,
  `except_clause` names, `import_statement`, `import_from_statement`,
  `aliased_import`, `named_expression` (binds in the nearest function scope,
  even from a comprehension), `match` capture patterns, `delete_statement`,
  PEP 695 type parameters, and `type` statements.
- `global_statement` sends the lookup to module scope; `nonlocal_statement` to
  the nearest enclosing function.
- Unbound at module scope means a builtin or `NameError`: outcome `none`.
- **Fail closed:** a `wildcard_import` anywhere in the module disables
  module-scope narrowing in that file. A call to bare `exec` or `globals`
  anywhere in the module does the same. A function that declares
  `global name` and binds it adds a non-definition binding at module scope.
- **Conditional:** a definition is conditional if any statement between it and
  its scope's body is `if_statement`, `elif_clause`, `else_clause`,
  `try_statement`, `except_clause`, `finally_clause`, `while_statement`,
  `for_statement`, `with_statement` or `match_statement`/`case_clause`.
  `decorated_definition` is transparent.

### 7.4 Group rules

Applied to the definitions `G` that a lookup (Tier 1) or an export lookup
(Tier 2) finds in one scope. First drop non-callable kinds (namespaces,
enums); then:

| Language | Group | Result | Rule ID |
| --- | --- | --- | --- |
| Any | One definition | That definition (Python: only if unconditional; a single conditional definition gives `none`) | `t1.lexical` |
| TS/TSX | k ≥ 1 bodyless `function_signature` plus exactly one `function_declaration` with a body, contiguous siblings in one scope (export wrappers allowed) | The implementation | `t1.ts_overload` |
| TS/TSX | Two or more bodies (duplicate implementation, a TS error), with or without signatures | The bodies only, `ambiguous` | `t1.lexical` |
| JS (`javascript` only) | Two or more `function_declaration`/`generator_function_declaration` that are direct children of the same function-body `statement_block` or of a script-goal `program`, no other binding of the name in that scope | The last one by byte offset | `t1.js_hoist` |
| JS | Same, but at the top level of a module-goal file (an early error in ESM) | The group, `ambiguous` | `t1.lexical` |
| Python | Two or more definitions in one scope, any mix of conditional and unconditional | The group, `ambiguous` | `t1.lexical` |
| Any | Definitions mixed with non-definition bindings | `none` | — |

## 8. Sequential redefinition policy (owner decision, 2026-11-20)

This decision replaces the issue's "Python redefinitions resolve when every
definition is unconditional and in the same scope". Greenfield needs to know
exactly which edges change, so the policy is stated here with its fixtures.

| Form | Result | Fixture proof |
| --- | --- | --- |
| Python `def` or `class` defined twice in one scope, unconditionally | `ambiguous`, narrowed to the group, both copies kept | r9-py `C` and `d`; rt-pyrec `d` and `C`; probe `redef.py` `d`; r9b-py and py-sameline `d` (no calls; controls) |
| Python conditional definitions (`if`/`else`, `try`) | `ambiguous`, group kept; a single conditional definition leaves the edge unchanged | rt-pycond `d`; authored `py-cond-e` (calls to py-sameline's `e` pattern, including the nested conditional `e`) |
| Python `@overload` stubs plus implementation | `ambiguous` (same policy) | authored `py-overload` |
| Plain JS: hoisted function declarations at one function-body or script top level | **resolved to the last declaration** | rt-js `g → d` resolves to `d` @6 |
| Plain JS: function declarations in blocks (`if`, `{}`), `var f = function…`, `let`/`const` arrows | unchanged | authored `js-block-fn`, `js-var-fn` |
| Plain JS: duplicates at the top level of an ES module | `ambiguous` (early error, no runtime meaning) | authored `js-esm-dup` |
| Plain JS: the same name in two script-goal files | unchanged (load order unknown) | authored `js-script-global` |
| TS duplicate function or method bodies | `ambiguous` (TS rejects them) | authored `ts-dup-impl`; rt-tsclass (no calls; control); authored `ts-dup-method` |
| TS overload set (k bodyless signatures, one implementation) | **resolved to the implementation** | r9-ts `caller → d`; probe `over.ts` `g → f` |

Why Python does not use "last definition wins" for calls inside function
bodies: a function can be called at module level between the two definitions.

```python
def d(): return 1
def caller(): return d()
caller()        # runs the first d
def d(): return 2
```

Static analysis without flow tracking cannot rule that out, so both copies stay
candidates. JavaScript differs: hoisting binds every function declaration of a
scope before any statement runs, so the last declaration is the only value any
call in that scope can see.

**Edges that change for Greenfield's round-1 trees:** the 9 call edges in
r9-ts and the 1 in rt-js. Nothing else changes.

## 9. Tier 2 rules (`imports`)

Tier 2 adds the `import(b)` branch. It intersects the import's proven target
with today's candidates, so it can only resolve when the true target is already
a candidate.

**Consequence of remove-only (open question Q1):** an aliased or default import
whose local name differs from the exported name (`import { t as tt }`,
`from a import helper as h`) never has the target among today's name-based
candidates, so it stays as it is today. Tier 2 still protects those calls from
a wrong same-name choice. Default imports with the same local name
(`import t from './svc'` where svc has `export default function t`) and
namespace imports do resolve.

### 9.1 TS/JS import bindings

| Form | Node types | Binding |
| --- | --- | --- |
| `import d from './m'` | `import_clause` → `identifier` | `d` → (m, `default`) |
| `import { a }`, `import { a as b }` | `named_imports` → `import_specifier` (`name`, `alias`) | `b` → (m, `a`) |
| `import * as ns from './m'` | `namespace_import` | `ns` → module m; eligible call `ns.a()` (two segments) |
| `import d, { a }`, `import d, * as ns` | combinations | as above |
| `import type …`, `import { type a }` | type-only | not a value binding → `none` |
| `import x = require('./m')`, `const x = require('./m')` | `import_require_clause`, `call_expression` | `none` (CommonJS deferred) |
| `import('./m')` | `call_expression` | `none` |

### 9.2 TS/JS module resolution

- Relative specifiers only (`./`, `../`, `.`, `..`), resolved against the
  importer's root-relative POSIX path. A path that leaves the extraction root,
  absolute paths, bare specifiers (`node_modules`, `@scope/pkg`, tsconfig
  `paths`/`baseUrl`, workspace packages), `#imports`, `node:` and URL
  specifiers, and query suffixes all give `none`.
- Candidate order, first match wins, as TypeScript resolves:
  1. Specifier ends in `.js` → `<p>.ts`, `<p>.tsx`, `<p>.d.ts`, then `<p>.js`.
     Ends in `.jsx` → `<p>.tsx`, `<p>.d.ts`, `<p>.jsx`.
  2. Ends in `.ts`, `.tsx` or `.d.ts` → that file only.
  3. Ends in `.mjs`, `.cjs`, `.mts` or `.cts` → `none` (not collected).
  4. Otherwise → `<p>.ts`, `<p>.tsx`, `<p>.d.ts`, `<p>.js`, `<p>.jsx`, then
     `<p>/index.` with the same five extensions.
- Existence is decided from the run's file set, without filesystem access at
  assembly. Walking the order: a file in the run binds. A candidate whose
  extension this run did not collect (a `language` filter) or that lies under a
  skipped directory (`node_modules`, `dist`, `build`, …) is unknown, and stops
  resolution with `none`. Otherwise the file does not exist; try the next one.
- A `.d.ts` target gives `none`; it is a declaration, not the runtime code.
- `<p>/package.json` (`main`, `types`, `exports`) is not read (risk R6).

### 9.3 TS/JS export lookup and re-exports

For name `x` (or `default`) in target module M:

1. M's explicit local exports: `export function|class x`,
   `export const x = <arrow|function>`, `export default function|class`,
   `export default <identifier>`, `export { y as x }`. Resolve the local name in
   M's module scope with the Tier 1 lookup and apply the group rules in M
   (overloads resolve; duplicate bodies stay a group). If the local name is
   itself an import in M, follow it as a re-export hop.
2. `export { a as x } from './n'` and `export { x } from './n'`: a hop to
   (n, a).
3. `export * as x from './n'`: x is a namespace; calling it gives `none`.
4. If x has no explicit export and is not `default`: follow every
   `export * from` source. Exactly one provider → follow it; none or several
   → `none` (ES excludes conflicting star exports).
5. `export =`, a module with only CommonJS exports, or a type-only export →
   `none`.

At most **3 re-export hops** after the first target module (internal constant,
open question Q7). A cycle gives `none`.

### 9.4 Python import bindings

| Form | Binding |
| --- | --- |
| `import a` | `a` → module `a` |
| `import a.b` | `a` → module `a`; the chain `a.b.f()` is eligible |
| `import a.b as m` | `m` → module `a.b`; `m.f()` is eligible |
| `from m import x`, `from m import x as y` | `y` → (m, x) |
| `from . import x`, `from .m import x`, `from ..m import x` | relative |
| `from m import *` | disables module-scope narrowing in the file |
| `from __future__ import …` | ignored |
| Function-local imports | bind in the function scope; unconditional only directly in the body |
| Imports under `try`/`if` (including `TYPE_CHECKING`) | conditional: narrow to the group, never resolve |

Eligible member chains are `head.….name` where the head binds to a module import
and every middle segment is a submodule explicitly imported in this file
(`import a.b` makes `a.b` usable).

### 9.5 Python module paths

- Module names are dotted paths relative to the extraction root (the
  `_module_name` convention), which is treated as the `sys.path` entry.
- Absolute name D: `D/__init__.py` first, then `D.py`. That is CPython's order
  within one directory (a regular package wins over a same-named module), which
  settles the probe's `pkg.py` versus `pkg/__init__.py`. A directory without
  `__init__.py` is a namespace package: usable only as a path to submodules.
- Relative imports start from the importer's package directory (for
  `__init__.py`, its own directory); each extra dot goes up one level, and
  leaving the root gives `none`.
- Not found in the run → external → `none`. No suffix matching: `from utils
  import helper` never binds to `tools/utils.py`. Src layouts are deferred
  (open question Q5).

### 9.6 Python name lookup in the target module

1. M's module-scope bindings of x: definitions follow the group rules (single
   unconditional resolves; otherwise group or `none`). An import binding is a
   re-export hop (this covers `__init__.py` re-exports). Any other binding
   (assignment, conditional mix) or a star import in M gives `none`.
2. If x is not bound in M and M is a package with submodule `M.x`, x is a
   module: calling it gives `none`; it can be the head of a member chain.
3. Otherwise `none`. At most 3 hops; cycles give `none`.

### 9.7 What stays ambiguous or unresolved

- **TS/JS:** tsconfig `paths`/`baseUrl`/`rootDirs`, `node_modules` and bare
  specifiers, package `exports`/`imports`, `.d.ts` targets, CommonJS `require`
  (literal or computed) and `module.exports`, TS `import = require`, dynamic
  `import()`, `export =`, nested namespace chains (`ns.sub.f`), conflicting star
  exports, more than 3 hops, type-only imports, `.mjs`/`.cjs`/`.mts`/`.cts`,
  and renamed bindings whose target is not a candidate.
- **Python:** star imports, conditional and `try`/`except` imports (narrow
  only), `importlib`/`__import__`, `sys.path` changes, roots other than the
  extraction root, external packages, module `__getattr__`, `.pyi` stubs and
  extension modules, more than 3 hops, and renamed bindings whose target is not
  a candidate.
- **Everywhere:** member calls on anything other than a namespace or module
  import (dynamic dispatch), `globalThis.f()`/`window.f()`, and computed
  callees (already unresolved by the 7.0.0 guard).

## 10. Fixtures

### 10.1 Layout and provenance

`tests/fixtures/call_resolution/`:

- `greenfield-r1/<tree>/`: all 16 round-1 trees, byte-for-byte copies: the 8
  in-scope trees (r9-ts, r9-py, r9b-py, py-sameline, rt-pycond, rt-pyrec,
  rt-js, rt-tsclass) and the 8 controls (rt-go, rt-rust, rt-cpp, rt-java,
  rt-kotlin, clo-go, clo-kotlin, clo-rust). Greenfield confirmed every
  round-1 tree is synthetic and safe to commit.
- `probe-r9/`: the probe tree from
  `ambiguity-scope-20261119/r9probe/`, original layout (`pkg/`, `py/`).
- `authored/<case>/`: the positive and near-miss cases in 10.4 and 10.5.
- `expected/<tree>.json`: per call (file, call byte span, reference), the
  expected outcome for `structural` and `imports`, with targets written as
  `file:line:qualified_name` so they are readable; the tests map them to IDs.
  These are hand-written oracle tables, not generated goldens.
- `provenance.json` and `PROVENANCE.md`: for every copied file, its source path,
  sha256 and source manifest. Greenfield files cite
  `evidence-manifest.sha256` (sha256 `40575a9b…a1e46`). Probe files cite the
  evidence directory and these hashes, computed for this plan because the
  evidence `SHA256SUMS` (sha256 `e1e0b01c…250e`) covers only the outputs and
  `r9probe_run.py`:

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

- `.gitattributes`: `tests/fixtures/call_resolution/** -text`, so Windows
  checkouts keep the bytes and spans that the hashes and expectations depend on.
- `tests/test_call_resolution_fixture_provenance.py` re-hashes every copied
  file against `provenance.json`.

Extraction roots: each Greenfield tree's own directory; `probe-r9/` for the
TS cases and `probe-r9/py/` for the Python cases (Python absolute imports need
the `sys.path` root). Extracting `probe-r9/` as one root is also a near-miss:
`from a import helper` cannot bind, because the module there is `py.a`.

### 10.2 Matrix: Greenfield round-1 and probe trees

"=" means unchanged from today.

| Tree | Call | Today | Tier 1 | Tier 2 | Rule |
| --- | --- | --- | --- | --- | --- |
| r9-ts | svc.ts:4 A.m → t | amb {svc.ts t, svc.tsx t} | **resolved svc.ts t** | = Tier 1 | t1.lexical (class body skipped) |
| r9-ts | svc.ts:5 A.m2 → t (×2) | amb, same | **resolved svc.ts t** | = | t1.lexical |
| r9-ts | svc.ts:9 d → t (×2) | amb, same | **resolved svc.ts t** | = | t1.lexical |
| r9-ts | svc.ts:12, :13 caller → d | amb {d @8 sig, d @9 impl} | **resolved d @9** | = | t1.lexical, t1.ts_overload |
| r9-ts | svc.ts:14 caller → t | amb {svc.ts t, svc.tsx t} | **resolved svc.ts t** | = | t1.lexical |
| r9-ts | svc.tsx:2 View → t | amb, same | **resolved svc.tsx t** | = | t1.lexical (arrow scope → module) |
| r9-py | svc.py:16 C.b → C | amb {C @9, C @14} | = | = | redefinition policy |
| r9-py | svc.py:31 caller → d | amb {d @19, d @24} | = | = | redefinition policy |
| r9-py | 9 resolved, 1 unresolved | — | = | = | not eligible |
| r9b-py | 2 resolved | — | = | = | not eligible |
| py-sameline | 5 resolved (all → t) | — | = | = | not eligible |
| rt-pycond | svc.py:21 caller → d | amb {d @13, d @16} | = | = | conditional (policy) |
| rt-pyrec | svc.py:23 d → d | amb {d @18, d @22} | = | = | redefinition policy |
| rt-pyrec | svc.py:27 uses_c2 → C | amb {C @5, C @10} | = | = | redefinition policy |
| rt-pyrec | `self.c` resolved; `C().c` unresolved | — | = | = | not eligible |
| rt-js | k.js:9 g → d | amb {d @3, d @6} | **resolved d @6** | = | t1.lexical, t1.js_hoist |
| rt-tsclass | 2 resolved | — | = | = | not eligible |
| Controls (8 trees) | all edges | as in 3.1 | **byte-identical** | **byte-identical** | other languages |
| probe | over.ts:6 g → f | amb {f @1, f @2, f @3} | **resolved f @3** | = | t1.lexical, t1.ts_overload |
| probe | over.ts:6 g → new Box | amb {interface Box, class Box} | **resolved class Box** | = | t1.kind (t1.lexical agrees, no further removal) |
| probe | svc.ts:2 caller → t (×2) | amb {svc.ts t, svc.tsx t} | **resolved svc.ts t** | = | t1.lexical |
| probe | use.ts:2 user → t | amb, same | = (import binding) | **resolved svc.ts t** | t2.import (`.ts` before `.tsx`) |
| probe (py root) | c.py:4 use → helper | amb {a, b} | = (import binding) | **resolved a.helper** | t2.import |
| probe (py root) | pkg/__init__.py:5 call_k → k | amb {pkg.py k, pkg/__init__ k} | **resolved pkg/__init__ k** | = | t1.lexical |
| probe (py root) | redef.py:11 caller → d | amb {d @1, d @4} | = | = | redefinition policy |
| probe (combined root) | c.py:4 use → helper | amb {a, b} | = | = | module path not under root |

### 10.3 Authored positive cases

| Case | Shape | Today | Tier 1 | Tier 2 | Rule |
| --- | --- | --- | --- | --- | --- |
| ts-class-body | module `t`, class method `A.t`, other.ts `t`; `A.m(){ return t(); }` | amb (3) | resolved module t | = | t1.lexical |
| ts-nested-scope | `function outer(){ function t(){} return t(); }`, module `t`; block `{ const t = () => 1; t(); }` | amb | resolved inner t | = | t1.lexical |
| ts-arrow-const | `const helper = () => 1` used in same file; other.ts `helper` | amb | resolved arrow | = | t1.lexical |
| ts-namespace-merge | `function NS(){}` + `namespace NS {}` + `NS()`; other.ts `NS` | amb | resolved function NS | = | t1.kind, t1.lexical |
| py-class-scope | module `helper`, method `K.helper`; `K.meth` calls `helper()` | amb | resolved module helper | = | t1.lexical (class scope skipped) |
| py-closure | module `helper`; `outer` defines `helper`; nested `inner` calls it | amb | resolved outer.helper | = | t1.lexical |
| py-class-call | `class C` and `C()` in a.py; `def C` in b.py | amb | resolved class C | = | t1.lexical |
| ts-default-import | svc.ts `export default function t`; other.ts `t`; `import t from './svc'` | amb | = | resolved svc t | t2.import |
| ts-namespace-import | `import * as svc from './svc'; svc.t()`; svc.tsx also has `t` | amb | = | resolved svc.ts t | t2.namespace |
| ts-ext-order | `from './svc.js'` with svc.ts and svc.tsx; `from './lib'` with `lib/index.ts` | amb | = | resolved svc.ts t; lib/index.ts u | t2.import |
| ts-barrel | `index.ts`: `export * from './a'`, `export { t } from './b'`; 2 hops | amb | = | resolved | t2.import |
| py-relative | `pkg/sub/x.py`: `from ..util import helper` | amb | = | resolved pkg/util.py helper | t2.import |
| py-import-as | `import pkg.util as u; u.helper()`; `import pkg.util; pkg.util.helper()` | amb | = | resolved | t2.namespace |
| py-init-reexport | `pkg/__init__.py`: `from .impl import helper`; `from pkg import helper` | amb | = | resolved pkg/impl.py helper | t2.import |
| py-local-import | `def f(): from a import helper; return helper()` | amb | = | resolved a.helper | t2.import |

### 10.4 Authored near-miss cases (must stay as shown)

| Case | Shape | Today | Tier 1 | Tier 2 |
| --- | --- | --- | --- | --- |
| py-cond-e (module caller) | py-sameline's `if os.name` / `else` defs of `e`; a module-level function calls `e(1)` | amb {e @13, e.e @15, e @18} | amb {e @13, e @18} (the function-local `e.e` cannot be seen; both module copies kept) | = Tier 1 |
| py-cond-e (inside `e`) | the same tree; `e` calls `e(…)` after its nested conditional `def e` (local, single, conditional) | amb (3) | = | = |
| py-try-import | `try: from fast import helper` / `except ImportError: from slow import helper`; third `helper` elsewhere | amb (3) | = | amb {fast, slow} |
| py-star-import | `from a import *; helper()`; a and b define helper | amb | = | = |
| py-two-imports | `from a import helper` then `from b import helper`; c also defines helper | amb (3) | = | amb {a, b} |
| py-param-shadow | `def use(helper): return helper()`; also a local `helper = make()` | amb | = | = |
| py-global-unbound | `helper()` with no import; a and b define helper | amb | = | = |
| py-global-rebind | a function with `global helper` assigns it | amb | = | = |
| py-dynamic-dispatch | classes A and B define `run`; `x.run()`, `self.run()` | amb | = | = |
| py-dynamic-import | `m = importlib.import_module("a"); m.helper()` | amb | = | = |
| py-overload | `@overload` stubs plus implementation of `f`; call `f()` | amb | = | = |
| py-module-positional | `def d` / `d()` at module level / `def d` | amb | = | = |
| py-reexport-depth | a 4-hop `__init__` re-export chain | amb | = | = |
| ts-dup-impl | two `function f(){…}` bodies in a TS module; other.ts `f`; call `f()` | amb (3) | amb {f, f} | = |
| ts-dup-method | rt-tsclass's `K` with `new K().m(1)` and `this.m()` | amb | = | = |
| ts-globalThis | `globalThis.t()`, `window.t()` | amb | = | = |
| ts-param-shadow | `function run(t: () => number) { return t(); }`; `const t = make(); t()` | amb | = | = |
| ts-two-imports | `import { t } from './a'; import { t } from './b'` | amb | = | = |
| ts-alias-import | `import { t as helper } from './svc'`; two other `helper`s | amb | = | = |
| ts-bare-specifier | `from '@app/svc'`, `from 'lodash'` | amb | = | = |
| ts-dynamic-import | `const m = await import('./svc'); m.t()` | amb | = | = |
| js-require | `const { t } = require('./svc')`; `require('./' + name)` | amb | = | = |
| ts-namespace-global | script files a.ts and b.ts each `namespace N { export function f(){} }`; `N.f()`; bare `f()` inside a third `namespace N` block | amb | = | = |
| ts-declare-ambient | `declare function amb(): void` plus script-goal js `function amb(){}`; call `amb()` | amb | = | = |
| ts-dts | `from './lib'` where only `lib.d.ts` and `lib.js` exist | amb | = | = |
| ts-reassign | `function t(){}; t = other; t()` | amb | = | = |
| ts-star-conflict | two `export *` sources both export `t` | amb | = | = |
| ts-language-filter | run with `language="typescript"`; `from './svc'` where only svc.tsx exists | amb | = | = |
| js-block-fn | `if (x) { function d(){} } else { function d(){} } d()` | amb | = | = |
| js-var-fn | `var d = function(){}; var d = function(){}; d()` | amb | = | = |
| js-esm-dup | ESM file with two `function d` and a call; other.js also defines `d` | amb (3) | amb {d, d} (this file's pair) | = |
| js-script-global | two script files each `function d(){}`; call in one | amb | = | = |
| js-eval-with | direct `eval(...)` in the caller; a `with` block | amb | = | = |

## 11. Identity stability proof

### 11.1 Harness

`tests/call_resolution_harness.py` (a helper module) and
`tests/test_call_resolution_identity.py`, over **every** fixture tree (Greenfield,
probe, authored, controls) and every mode in `CALL_RESOLUTION_MODES` other than
`name`. Off = default call; on = the mode.

Symbol graph, off versus on:

1. `symbol_lookup` equal as dicts (keys include `#N`), `symbols` equal,
   `call_facts` equal (call IDs included), and every non-call relationship equal,
   in the same order.
2. Call relationships: same length, same order, same `call_site_id` sequence.
   Per pair, every field equal except `to`, `resolution`, `candidates`,
   `is_internal` and `provenance`. Provenance may differ only by the
   `call_resolution` and `call_rules` keys, and only when the candidate set
   changed.
3. Narrowing invariants: on-candidates are a subset of off-candidates. If off
   is not `ambiguous`, on equals off exactly. If on is `ambiguous`, it has two
   or more candidates. If on is `resolved`, `candidates == [to]`, `to` is in
   the off-candidates and `is_internal` is true.
4. `metadata` equal except the added `call_resolution`.

Boundary IR, off versus on (canonical, `resolution_mode` both `strict` and
`permissive`):

5. `nodes`, `files`, `diagnostics`, `source` and `schema_version` byte-identical
   as canonical JSON.
6. Same edge `id` set. Non-call edges byte-identical by id. Call edges equal by
   id except `target`, `resolution`, `candidates`, `metadata.is_internal` and
   the two provenance keys. `call_site_id == id` on both sides.
7. `metrics` equal except `resolved_edges` and `ambiguous_edges`, whose sum is
   unchanged. `run.options` equal except the added `call_resolution`.
8. Resolved-shape check: every on-mode edge that changed to `resolved` has
   `target` equal to a Boundary node id, `candidates == [target]` and
   `metadata.is_internal` true.

Off-mode equals today:

9. `call_resolution="name"` is byte-identical to omitting the argument, for the
   symbol graph and canonical Boundary IR.
10. `tests/fixtures/call_resolution/off_mode_digests.json` holds, per fixture
    tree, the sha256 of the canonical symbol graph and of the canonical Boundary
    IR with volatile fields (`run.root`, `source.path`, `tool_version`,
    `created_at`) normalized. PR 1's **first commit** adds the fixtures, the
    capture script (`scripts/capture_call_resolution_off_digests.py`) and the
    digests, generated on unmodified product code; product changes come in
    later commits and the file is never touched again. Reviewers can re-run the
    script at that commit.
11. The existing Boundary goldens (`tests/test_boundary_ir_golden_snapshots.py`,
    `tests/test_boundary_ir_determinism.py`) pass with **no regeneration**; a
    PR in this plan that touches the goldens fails review.

Cache and determinism:

12. For on-modes, cold and incremental (warm) Boundary IR are byte-identical,
    and two cold runs are byte-identical.
13. Off then on with the same `cache_dir` gives on-output identical to a cold
    on-run, and the reverse; `_cache_key_payload` for `name` equals the payload
    built without the argument and has no `call_resolution` field.

### 11.2 Mutation proofs

Automated comparator self-tests: start from a real (off, on) pair, apply one
mutation to a copy of the on side, and require the harness to fail:

| # | Mutation | Must fail |
| --- | --- | --- |
| M1 | Change one `definition_id` | 1, 5 |
| M2 | Swap two `#N` suffixes | 1, 5 |
| M3 | Change one `call_site_id` (or hash the target into it) | 1, 2, 6 |
| M4 | Change a non-call edge's target or resolution | 1, 6 |
| M5 | Empty the candidates of an ambiguous edge | 3 |
| M6 | Add a candidate not in the off set | 3 |
| M7 | Re-target an edge that is resolved when off | 3 |
| M8 | Change an unresolved edge | 3 |
| M9 | Reorder call relationships | 2 |
| M10 | Drop an edge | 2, 6 |
| M11 | Add a provenance key other than the two allowed | 2, 6 |
| M12 | Resolved edge with `candidates` not equal to `[target]` | 3, 8 |
| M13 | Change one byte of off-mode output | 10 |

Each product PR also records one manual mutation in its description: a
deliberate one-line product edit that leaks an ID (for example, appending the
resolved target to the `_call_site_id` seed when the option is on), the failing
harness output, and the revert.

## 12. Consumer impact

**Default (off).** Nothing changes for Greenfield or Code-Index-MCP: output,
cache keys and cache records are byte-identical.

**When a consumer turns it on:**

- No identity changes. Joins on `call_site_id`, `definition_id`, node IDs and
  `#N` stay valid across modes.
- Edges that become `resolved` have exactly today's resolved shape (4.3), plus
  `provenance.call_resolution` and `provenance.call_rules`. A consumer that
  wants only binding-proven narrowing can ignore edges whose `call_rules` is
  just `["t1.kind"]`.
- Edges that stay `ambiguous` keep a `candidates` list, possibly shorter, never
  fewer than two, and always a subset of today's.
- Resolved, unresolved and non-call edges, nodes, files and diagnostics are
  unchanged. Derived counts (`metrics`, clustering weights, node degrees)
  change, so consumers must recompute them rather than compare across modes.
- Boundary edge positions can move because `target` is a sort key. Consumers
  must key on `id`.
- On-mode runs populate separate incremental cache records; the first on-mode
  run is cold.

**Greenfield.** Round-1: r9-ts's 9 edges and rt-js's 1 edge resolve; every
other edge is unchanged (section 8). For the 15 ambiguous edges Greenfield
found on 5.0.1 that really are different definitions: those reached through
dynamic dispatch stay ambiguous because member calls are never narrowed; those
reached through imports resolve only in `imports` mode, when the import binding
proves the target and the target is already a candidate. Greenfield also sees
the 7.0.0 `C().c` change from section 3.1 regardless of this option.

**Code-Index-MCP.** Call-hierarchy edges in TS/JS and Python repos become more
precise when it opts in; polyglot repos lose cross-language candidates on bare
calls (`t1.kind`). It must recompute any stored resolution counts.

## 13. Delivery

### 13.1 PRs

Every PR refs treesitter-chunker#682 without closing it until the last one, and
merges with a merge commit at the exact reviewed head after the board and
president approve and full CI passes. No release.

| PR | Scope | Fixture expectations it adds |
| --- | --- | --- |
| 1. Surface, harness, `t1.kind` | Types and constants; the parameter threaded through `symbol_graph.py`, `boundary/adapter.py` (cold, incremental, cache key, `run.options`, provenance copy in `_edge_record`); both CLI flags; the engine skeleton and `t1.kind`; schema documentation; `docs/interface-boundary-spec.md` "Scoped call resolution extension"; symbol-graph docs; CHANGELOG (Unreleased). All fixture trees, provenance, `.gitattributes`, off-mode digests (first commit), harness and mutation self-tests. | probe `new Box`; every tree "unchanged except kind" |
| 2. Tier 1 TS/JS | `js_scope.py`: scope chain, group rules (`t1.ts_overload`, `t1.js_hoist`), script-global check, namespace and ambient handling. Bump `call_resolution_version`. | r9-ts (9), rt-js (1), probe TS, ts-class-body, ts-nested-scope, ts-arrow-const, ts-namespace-merge, and the TS/JS Tier 1 near-misses |
| 3. Tier 1 Python | `py_scope.py`: LEGB, class scope, comprehensions, `global`/`nonlocal`, conditionals, redefinition policy. Bump the version. | probe `call_k`, py-class-scope, py-closure, py-class-call, all Greenfield Python trees unchanged, and the Python Tier 1 near-misses |
| 4. Tier 2 TS/JS | Adds the `imports` value; import and export facts; `modules.py` TS resolution and re-exports. Bump the version. | probe `use.ts`, ts-default-import, ts-namespace-import, ts-ext-order, ts-barrel, and the TS/JS import near-misses |
| 5. Tier 2 Python | Python imports, module paths and `__init__` re-exports. Bump the version. | probe `c.py`, combined-root near-miss, py-relative, py-import-as, py-init-reexport, py-local-import, and the Python import near-misses |

Order: PR 1 first. PRs 2 and 3 are independent and can be reviewed in
parallel (separate expectation files per language). PR 4 follows PR 2; PR 5
follows PRs 3 and 4.

### 13.2 Test lanes

New test files: `tests/test_call_resolution_surface.py`,
`tests/test_call_resolution_identity.py`,
`tests/test_call_resolution_fixture_provenance.py`,
`tests/test_call_resolution_tier1_js.py`,
`tests/test_call_resolution_tier1_py.py`,
`tests/test_call_resolution_tier2_js.py`,
`tests/test_call_resolution_tier2_py.py`.

- **PR CI:** add the new files to `CI_SMOKE_TESTS` in `scripts/run_ci_smoke.py`
  (Linux 3.14), and the identity and Tier 2 files to
  `scripts/run_platform_core.py` (Linux, macOS, Windows; Tier 2 path handling
  and the `-text` fixtures need Windows coverage). Keep the lane policy tests
  (`tests/test_ci_scope_policy.py` and the governed-scope checks) passing.
- **Before merge:** a manual full dispatch (full `tests/` and `spec_tests/` on
  all three OSes), because the issue requires full CI.
- **Local on dev0, narrow only:** check `free -h`, `/proc/loadavg` and `nproc`
  first, run pytest serially (or `-n 2` at most), and never run
  `run_platform_core.py` or `run_full_suite.py` locally:

  ```bash
  uv run --locked --all-extras pytest tests/test_call_resolution_*.py \
    tests/test_symbol_graph_resolution.py tests/test_symbol_graph_incremental_facts.py \
    tests/test_boundary_ir_resolution_modes.py tests/test_boundary_ir_incremental_cache.py -q
  uv run --locked --all-extras pytest tests/test_boundary_ir_golden_snapshots.py \
    tests/test_boundary_ir_determinism.py -q
  ```

  plus the Ruff, Black and mypy-gate commands from CONTRIBUTING.md (cheap).
- **Windows preflight:** CONTRIBUTING asks for it before pushing changes to
  paths and extraction. Run it for PRs 4 and 5 when the shared WIN host is
  free; otherwise rely on CI's Windows platform-core job and say so in the PR.

### 13.3 Release gates for a future 7.1.0

Not part of #682's delivery; recorded so a release decision has them. Gates
1–7 are automated acceptance tests from PR 1 onward (harness checks 1–13 in
section 11.1); gates 8 and 9 are release-time steps.

1. With the option off, output is byte-identical to today (off-mode digests
   unchanged; goldens unchanged, never regenerated).
2. `call_site_id` is unchanged on and off, for every fixture.
3. `definition_id`, `node_id` and the `#N` occurrence scheme are unchanged on
   and off.
4. Every edge left `ambiguous` keeps a `candidates` list: narrowed, never
   dropped or emptied, two or more entries, a subset of today's.
5. A narrowed edge has exactly today's resolved shape: `target` is the
   definition's ID, `resolution` is `resolved`, `candidates` holds exactly that
   ID.
6. Non-call edges, and calls that are resolved or unresolved when off, are
   identical on and off.
7. The off-scope controls (Go, Rust, Java, Kotlin, C++, and the `clo-*` trees)
   are byte-identical on and off.
8. Greenfield runs its 42 reference IRs with the option on and signs off on the
   changed-edge report.
9. Full three-OS CI passes at the release head.

## 14. Deferred, explicitly out of scope

- Go, Java, Kotlin, C#, Rust and C/C++ resolution.
- Receiver-typed member calls (`self.m()`, `this.m()`, `obj.m()`), including TS
  method overload groups reached through members; the `SemanticResolver`
  surface is the likely home.
- Class-qualified static calls (`Class.static()`) disambiguated across files.
- CommonJS `require`/`module.exports`, TS `import = require`.
- tsconfig `paths`/`baseUrl`, `package.json` `exports`/`main`/`types`,
  `.d.ts`-to-implementation pairing, nested namespace re-exports.
- Python source roots other than the extraction root (src layouts, configured
  `sys.path`).
- Python positional resolution of module-level calls between redefinitions, and
  Python `@overload` grouping.
- "Binding substitution" for renamed imports (Q1) and "demotion" of single
  candidates proven wrong (Q8).

## 15. Risks and open questions

| # | Question or risk | Recommendation |
| --- | --- | --- |
| Q1 | Remove-only means renamed imports (`{ t as tt }`, `import x as y`) never resolve: the target is not a name-based candidate. Allowing Tier 2 to substitute the proven target would change what `candidates` means. | Keep remove-only for #682 as the issue states. File a follow-up for an owner decision on substitution. |
| Q2 | Provenance keys on narrowed edges (`call_resolution`, `call_rules`) slightly extend "today's resolved shape". | Include them: additive, schema-legal, only on changed edges, and they let consumers audit or filter rules. The board can drop them without affecting anything else. |
| Q3 | `t1.kind` alone can resolve an edge by elimination; the survivor is a name match like today's single-candidate edges, not a proven binding. | Allow it, as the issue specifies. `call_rules == ["t1.kind"]` marks these edges. Alternative if the board prefers: require a binding before an edge resolves. |
| Q4 | Python redefinition: owner decided "never resolve". | Adopt (section 8). Positional module-level resolution and `@overload` grouping are deferred. |
| Q5 | Python module root: only root-relative names bind, so src layouts get no Tier 2 help. | Accept for #682; suffix matching would mis-bind external packages to vendored copies. Follow-up for configured roots. |
| Q6 | A relative import that lands on a `.d.ts` file. | `none`. Pairing declarations with `.js` implementations is deferred. |
| Q7 | Re-export depth. | 3 hops: enough for the common `index.ts` → feature barrel → implementation (2) with margin. Internal constant, not public. |
| Q8 | Today's single-candidate edges can be wrong (a parameter or import shadows the name). The option never touches them. | Out of scope: changing them would alter today's resolved edges, which consumers treat as stable. Separate issue. |
| R1 | Scope analyzer misses a binding construct and narrows wrongly. | Fail closed on unrecognized declarations, trees with errors, `eval`/`with`, star imports and `exec`/`globals`. Grammar pins are exact. Near-miss fixtures cover each construct. |
| R2 | JS script/module detection uses import/export presence only; `.js` ESM files without either look like scripts. | Misclassification only makes the analysis more conservative (the script-global check), except `t1.js_hoist` on a would-be early-error file, which cannot run anyway. Accept. |
| R3 | A third parse per file when on. | Opt-in only. Record timings in each PR description; no performance gate. Reusing the core parse tree is a later optimization. |
| R4 | Edge reordering in Boundary `edges` when targets change. | Documented; consumers key on `id` per the spec. |
| R5 | Off-mode digests depend on the locked grammar stack. | Same footing as the Boundary goldens: a lock change regenerates both through scripts, never by hand. |
| R6 | A relative import of a directory with `package.json` (`main`/`types`) resolves differently in TS. | Rare for relative imports; accept and document. |
| R7 | Python extension modules (`.so`) win over `.py` at runtime and are invisible to the run. | Rare in source trees; accept and document. |
| R8 | The `imports` value changes behavior between PR 4 and PR 5 (Python imports start resolving). | Unreleased between PRs; documented in PR 4. |

## 16. Acceptance criteria for this plan

- Rules per tier and language, with node types, metadata findings and
  extractor decisions (sections 3.3, 6–9).
- Opt-in surface chosen with rationale and exact API, provenance, schema and
  cache handling (section 4).
- Fixture matrix covering the probe cases, every in-scope Greenfield tree, the
  controls and the near-miss list (section 10).
- Identity proof with mutation proofs (section 11).
- Consumer impact (section 12), delivery with lanes and release gates
  (section 13), deferred work (section 14), and risks with recommendations
  (section 15).

## Appendix: how the baseline was produced

Narrow runs on dev0 after checking headroom (21 GiB available, load 1.4 on 24
cores). Greenfield trees copied to a scratch directory and verified with
`sha256sum -c` against the manifest lines for `r1/trees/` and
`r1/out/upstream-*`. Symbol graph per in-scope tree:

```python
import sys
from pathlib import Path
from chunker.symbol_graph import extract_symbol_graph

g = extract_symbol_graph(Path(sys.argv[1]))
syms = g["symbol_lookup"]
for e in g["relationships"]:
    if e["type"] == "calls":
        print(e["line"], e["from"], e["reference"], e["resolution"],
              [(syms[c]["file"], syms[c]["line"], syms[c]["kind"]) for c in e["candidates"]])
```

Boundary IR per round-1 tree with `extract_boundary_ir(tree)` (defaults),
compared edge by edge, by `id`, with `r1/out/upstream-<tree>.json` (6.0.0).
Metadata facts from `chunk_file(path, language, extract_metadata=True,
include_retrieval_metadata=True)` on probe files covering each construct in
section 3.3.

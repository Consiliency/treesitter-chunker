---
phase_loop_plan_version: 1
phase: REFS
roadmap: specs/phase-plans-v4.md
roadmap_sha256: 0a15424c6230b812b095dd9668ecf62bd0457aebdc927533ccde04e6e20cae14
automation:
  # Post-merge suite: the two language contract tests land in
  # treesitter-chunker#548 and treesitter-chunker#549; until both merge, drop
  # the missing file(s) from this command.
  suite_command: "uv run --locked --all-extras pytest tests/test_reference_fixture_oracle.py tests/test_python_reference_oracle_contract.py tests/test_javascript_reference_oracle_contract.py tests/unit/context tests/test_python_scope_visible_symbols_contract.py tests/test_javascript_scope_local_definition_contract.py tests/test_javascript_scope_import_contract.py tests/test_javascript_arrow_context_contract.py -q"
---

# REFS: Reference lookup accuracy

## Context

REFS is Phase 4 of `specs/phase-plans-v4.md`. It makes Python and JavaScript
definition, scope and reference lookup truthful against one shared
real-parser fixture suite (theme B). The plan starts from main `6d8d71cf`
(treesitter-chunker#538 merge). The roadmap hash above is the current
roadmap's hash.

All five issues were re-read on 2026-10-31 with `gh issue view N --comments`.
They are open and unchanged since the roadmap snapshot. Each reproduces at
`6d8d71cf` with the real pinned parsers (tree-sitter 0.26,
`tree-sitter-python==0.25.0`, `tree-sitter-javascript==0.25.0`):

| Issue | Observed on `6d8d71cf` |
|---|---|
| treesitter-chunker#274 | `find_symbol_definition("Renderer"/"render_report", root, root)` on `tests/fixtures/boundary_ir/repos/python/app/service.py` returns `None`. `PythonSymbolResolver._get_defined_name` returns `None` on every branch. |
| treesitter-chunker#294 | `for`, `with … as`, `except … as` and lambda-parameter targets are returned by `find_symbol_references`. The default value in `def f(value=DEFAULT)` is not, because every identifier under `default_parameter` counts as a definition. |
| treesitter-chunker#278 | `captured` from `[(captured := item) for item in values]` is not visible in `outer`. A lambda or generator in a parameter default has the function as its enclosing scope and sees the function's parameters and body locals. Assignment expressions bind nowhere: `named_expression` is not handled at all, so even a plain function-body walrus is missing. |
| treesitter-chunker#289 | `_find_definition("gen", root, root, source).content` is the full generator body (`const secret = 1; yield secret;`), for both `function* gen` and `export function* gen`. The ordinary function gives `function fn() { ... }`. |
| treesitter-chunker#293 | Default-import, named function-expression, bare arrow-parameter, default-parameter (`assignment_pattern`) and array-pattern binding identifiers are returned by `find_symbol_references`. The shorthand reference in `{ value }` is not returned at all, because its node is `shorthand_property_identifier`. |

The exact probe commands and outputs are recorded in each language PR (VB-1).

## Interface Freeze Gates

- [ ] IF-0-REFS-1 — The shared reference fixture suite, published by SL-fix:
  - layout: `tests/fixtures/references/{python,javascript}/<stem>.<py|js>`,
    each with a sibling `<stem>.oracle.json`;
  - schema: `tests/fixtures/references/oracle.schema.json`
    (`treesitter-chunker.reference-oracle.v1`, JSON Schema draft 2020-12);
  - loader: `tests/reference_oracle.py` (`load_reference_case`,
    `reference_case`, `oracle_paths`, `find_anchor`, `validate_oracle`,
    `ReferenceCase.scope/node/occurrence/entries`).

  An oracle names scopes by anchor (named node type plus tree-sitter start
  point, 0-based row and byte column; `root` is the parse root). Every
  expectation carries the `issue` it belongs to, so each issue keeps its own
  contract. The sections are:
  - `definitions` — lookup of a name from a scope is `found` (node type and
    anchor) or `absent`;
  - `occurrences` — a name occurrence is a `binding` (never a reference) or a
    `use` (always a reference), with the scope where it binds or is evaluated;
  - `visible` — names that are and are not visible from a scope;
  - `enclosing` — the scope where an expression is evaluated, plus a
    syntactically enclosing scope that must not be reported;
  - `dependency_context` — the definition found for a name, and text its
    dependency summary must and must not contain.

Fixtures, one per issue:

| Fixture | Issue | Positive | Negative |
|---|---|---|---|
| `python/module_definitions.py` | treesitter-chunker#274 | module class/function/decorated function/assignment found; nested `helper` shadows module `helper` | method, class attribute and function locals absent from the module; class attribute absent from a method; `cleaned` absent from sibling scopes |
| `python/binding_targets.py` | treesitter-chunker#294 | default values, loop/with/except bodies, lambda body and default value are uses | `for` (plain, tuple), `with … as` (name, tuple), `except … as`, lambda parameters, comprehension `for` targets and default-parameter names are bindings |
| `python/assignment_expression_scope.py` | treesitter-chunker#278 | comprehension walrus visible in the containing function (also through nested comprehensions); default walrus visible in the class body; lambda/generator in a default evaluated in the module | comprehension variables not visible outside; default walrus not visible in the method or module; function parameters and body locals not visible in a default lambda/generator |
| `javascript/generator_context.js` | treesitter-chunker#289 | generator and exported generator summaries keep the signature | summaries omit body locals and statements; the ordinary and exported ordinary functions are the comparison |
| `javascript/binding_identifiers.js` | treesitter-chunker#293 | shorthand `{ value, LIMIT }` references found; default value, body and later uses found | default import, named function-expression name, bare arrow parameter, default-parameter name and array-pattern elements are bindings |

`tests/test_reference_fixture_oracle.py` keeps the oracles truthful: the
schema validates, every fixture parses without error on the real parser,
every anchor resolves to exactly one node with the expected text, each
occurrence lies inside its scope, each found definition defines the name,
every issue has positive and negative expectations, and the suite covers
exactly the five REFS issues (EC-REFS-1).

Decisions this plan makes, which are open to challenge in review:

1. **Lane PR topology.** SL-fix lands first as a small PR. SL-py and SL-js
   are built on the SL-fix branch and target `main`, so that the hosted
   platform matrix (`test.yml` runs only for PRs into `main`) runs on them.
   Until SL-fix merges, their diffs include the SL-fix commit; reviewers of a
   language PR review only the commits after it. After SL-fix merges, each
   language branch is rebased onto `main` with no content change.
2. **#274 lookup scope.** "No cross-scope false positives" includes Python's
   class rule: a class body's names are not visible from functions, lambdas
   or comprehensions nested in it. Definition lookup therefore skips class
   scopes when ascending from an inner scope, as `get_visible_symbols`
   already does. The class's own name is still found in its parent scope.
3. **#278 needs walrus binding.** Assignment expressions bind nowhere on main,
   so the comprehension rule cannot be expressed without first making
   `named_expression` a binding. SL-py adds that binding with the scope rule;
   it is the mechanism of treesitter-chunker#278, not a separate repair.
4. **Defaults evaluate in the enclosing scope.** Default values of a
   `def` or `lambda` are evaluated in the scope that contains the definition.
   `get_enclosing_scope` skips the owning function for nodes inside a default
   value, and walrus targets in defaults bind in that enclosing scope.
5. **Out of scope, filed separately.** Gaps seen during reproduction that no
   REFS issue names are filed as their own issues and not repaired here:
   - treesitter-chunker#544: Python `def` splat parameters and walrus
     targets reported as references. Lambda splats moved into
     treesitter-chunker#294 in round-1 review.
   - treesitter-chunker#545: JavaScript `rest_pattern`, object-pattern
     `pair_pattern` values and `catch` parameters reported as references.
   - treesitter-chunker#552: JavaScript parent context empty inside
     generators.
   - treesitter-chunker#554: Python definition lookup ignores comprehension,
     loop, `with`/`except`, import, walrus, splat and unpacking bindings. The
     runner ruled these definitions out of REFS scope.
   - treesitter-chunker#555: Python tuple-unpacking assignment targets
     reported as references.
6. **CI selection (parent decision, 2026-10-31).** Hosted PR CI must run
   the new REFS tests. Following HOTFIX, each PR enrolls its own tests in the
   platform-core batch (`scripts/run_platform_core.py`, run by `test.yml` on
   Linux, macOS and Windows): SL-fix enrolls
   `tests/test_reference_fixture_oracle.py`, SL-py
   `tests/test_python_reference_oracle_contract.py` and SL-js
   `tests/test_javascript_reference_oracle_contract.py`. These are
   acknowledged out-of-lane registration edits, placed at separate anchors so
   the two language PRs do not conflict.

## Lane Index & Dependencies

SL-fix — Shared fixture suite (IF-0-REFS-1)
  Depends on: (none)
  Blocks: SL-py, SL-js
  Parallel-safe: yes (new files only)

SL-py — Python definition, binding and scope repairs
  Depends on: SL-fix
  Blocks: (none)
  Parallel-safe: yes with SL-js (disjoint files)

SL-js — JavaScript generator context and binding repairs
  Depends on: SL-fix
  Blocks: (none)
  Parallel-safe: yes with SL-py (disjoint files)

## Lanes

### SL-fix — Shared fixture suite

- **Scope**: Publish IF-0-REFS-1 and this plan. No product code changes.
- **Owned files**: `tests/fixtures/references/**`, `tests/reference_oracle.py`,
  `tests/test_reference_fixture_oracle.py`, `plans/phase-plan-v4-REFS.md`;
  one registration line in `scripts/run_platform_core.py` (decision 6)
- **Interfaces provided**: IF-0-REFS-1
- **Tasks**:
  - Write one fixture and oracle per issue, with positive and negative
    expectations taken from real parses of the pinned grammars.
  - Write the schema, loader and integrity test.
  - Run the integrity test and the CONTRIBUTING.md validation block.

### SL-py — Python (one PR; commits treesitter-chunker#274 → treesitter-chunker#294 → treesitter-chunker#278)

- **Owned files**: `chunker/context/languages/python.py`,
  `tests/test_python_reference_oracle_contract.py`; one registration line in
  `scripts/run_platform_core.py` (decision 6)
- **Interfaces consumed**: IF-0-REFS-1
- **Tasks and named mutations**:
  - treesitter-chunker#274: `PythonSymbolResolver._get_defined_name` returns
    the defined name of function, class, assignment and parameter nodes, and
    lookup skips class scopes when ascending. Mutation **M274**: restore
    `_get_defined_name` to return `None`; the `found` definitions fail. The
    class-scope skip is also guarded: without it, `class_label` is found from
    `Renderer.render`.
  - treesitter-chunker#294: `_is_definition_context` treats loop, `with`,
    `except` and lambda targets (through tuple and list patterns) as
    bindings, and only the `name` of a default parameter as a binding.
    Mutation **M294**: treat every identifier under `default_parameter` and
    `typed_default_parameter` as a definition again; the default-value `use`
    occurrences fail.
  - treesitter-chunker#278: walrus targets bind in the nearest enclosing
    non-comprehension scope, defaults and their walruses belong to the
    enclosing scope, and `get_enclosing_scope` skips a function for nodes in
    its defaults. Mutation **M278**: stop walrus collection at comprehension
    boundaries; the containing-function `visible` includes fail.
- Also runs the existing Python context tests unchanged. No base-class
  change is planned; if one becomes necessary, SL-py owns it and SL-js
  rebases (roadmap single-writer rule).

### SL-js — JavaScript (one PR; commits treesitter-chunker#289 → treesitter-chunker#293)

- **Owned files**: `chunker/context/languages/javascript.py`,
  `tests/test_javascript_reference_oracle_contract.py`; one registration line
  in `scripts/run_platform_core.py` (decision 6)
- **Interfaces consumed**: IF-0-REFS-1
- **Tasks and named mutations**:
  - treesitter-chunker#289: add `generator_function_declaration` (plain
    and exported) to the `_find_definition` summary dispatch and to
    `_extract_scope_declaration`. `generator_function` is not added: an
    assigned generator expression resolves to its `variable_declarator`, so
    the summary dispatch never sees it. Mutation **M289**: bypass the
    generator summary dispatch; the body-local `excludes` fail.
  - treesitter-chunker#293: classify default-import, named
    function-expression, bare arrow-parameter, default-parameter and
    array-pattern identifiers as bindings, and report
    `shorthand_property_identifier` in an object as a use. Mutation **M293**:
    drop the binding-identifier branch; the binding occurrences fail. The
    shorthand use is guarded by a second named mutation, **M293-shorthand**:
    stop treating `shorthand_property_identifier` as a reference node.

## Execution Notes

- Real parsers and fixtures only; no native-node mocks.
- No Boundary IR change is expected: the edited modules are not on the
  Boundary IR extraction path. The Boundary IR golden and determinism gates
  run in the smoke batch; if they ever change, regenerate them with
  `scripts/regenerate_boundary_goldens.py` and flag it in the PR.
- No parser pin changes.
- Respect the host resource caps: one heavy run at a time, at least 6 GiB
  available (`free -g`) before it starts, `pytest -n` no higher than 4, and
  scratch under `$TMPDIR`. `scripts/run_ci_smoke.py` hard-codes `-n auto`; run
  its selection with `-n 4` instead and say so in the PR.
- No Windows preflight: no path, native, temp-file, export or config change.
- Do not merge from a lane; the parent runs the two-reviewer panel (VB-4).

## Verification

```bash
# VB-1 / VB-2 (per language PR; commands and outputs recorded in the PR)
uv run --locked --all-extras pytest tests/test_reference_fixture_oracle.py -q
uv run --locked --all-extras pytest tests/test_python_reference_oracle_contract.py -q
uv run --locked --all-extras pytest tests/test_javascript_reference_oracle_contract.py -q
uv run --locked --all-extras pytest tests/unit/context tests/test_python_scope_visible_symbols_contract.py tests/test_javascript_scope_local_definition_contract.py tests/test_javascript_scope_import_contract.py tests/test_javascript_arrow_context_contract.py tests/test_smart_context.py -q

# CONTRIBUTING.md validation block (VB-3)
uv run --locked --all-extras ruff check chunker/ cli/ tests/ tools/governed_group.py tools/governed_scope.py tools/sync_governed_test_transport.py --exclude archive --exclude logs --exclude site
uv run --locked --all-extras black --check chunker/ cli/ tests/ scripts/ tools/governed_group.py tools/governed_scope.py tools/sync_governed_test_transport.py
uv run --locked --all-extras python scripts/mypy_gate.py
uv run --locked --all-extras mypy --follow-imports=silent --allow-untyped-defs --allow-incomplete-defs --allow-untyped-calls --check-untyped-defs --no-pretty --no-error-summary --show-error-codes tools/sync_governed_test_transport.py
# CI smoke selection with -n 4 (host cap) instead of run_ci_smoke.py's -n auto
uv run --locked --with toml --all-extras python -c "import subprocess, sys; from scripts.run_ci_smoke import CI_SMOKE_TESTS; sys.exit(subprocess.call([sys.executable, '-m', 'pytest', '-n', '4', '--timeout=60', '-q', *CI_SMOKE_TESTS]))"
```

## Acceptance Criteria

- [ ] EC-REFS-1 — IF-0-REFS-1 lands first, with positive and negative cases
  for all five issues (`tests/test_reference_fixture_oracle.py`).
- [ ] EC-REFS-2 — The Python PR covers treesitter-chunker#274,
  treesitter-chunker#294 and treesitter-chunker#278, each failing under its
  named mutation (M274, M294, M278).
- [ ] EC-REFS-3 — The JavaScript PR covers treesitter-chunker#289 and
  treesitter-chunker#293, each failing under its named mutation (M289, M293).
- [ ] EC-REFS-4 — Every PR meets VB-1 to VB-4. No Boundary IR golden or parser
  pin changes.

## Review record

- The parent runs the two-reviewer panel (VB-4) on each PR's exact head and
  records reviewers, heads and verdicts here or in the PR, at most three
  rounds per PR.

## Spec Closeout Plan

- schema: `spec_delta_closeout.v1`
- decision: `no_spec_delta`
- target surfaces: issue acceptance for treesitter-chunker#274,
  treesitter-chunker#278, treesitter-chunker#289, treesitter-chunker#293,
  treesitter-chunker#294
- evidence paths: `plans/phase-plan-v4-REFS.md`, PR verification logs
- redaction posture: `metadata_only`
- missing or malformed evidence: `blocker_class=contract_bug`

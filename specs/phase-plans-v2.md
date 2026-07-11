# Tree-sitter Chunker — Phase Plan v2 (v3.2.2 Review Remediation)

> How to use this document: run `/claude-plan-phase <ALIAS>` to produce the lane-level plan for each phase (→ `plans/phase-plan-v2-<alias>.md`), then `/claude-execute-phase <alias>` to build it.
>
> Revision note: this v2 incorporates a cross-vendor advisor-board review (Fable / GPT-5.6-SOL / Grok, all PARTIALLY AGREE) of the first draft. Changes: SUPPLY and APISAFE promoted to co-roots; a BOUNDARYFIX phase added for the orphaned Boundary-IR MAJORs; workflow-hardening moved into GATES; SCALE now depends on IDENTITY and APISAFE; the identity contract and parser-safety scope tightened; xfail/release gating hardened.

---

## Context

This roadmap turns the findings in `CODE_REVIEW_v3.2.2.md` (a six-subsystem review reconciled against a GPT-5.6 / Grok 4.5 / Claude advisor board) into an executable, parallelism-maximizing remediation plan for `treesitter-chunker`. The review's thesis: a genuinely well-engineered boundary-IR / canon determinism core is wrapped in an unsound concurrency model, a content-hash chunk identity that breaks incremental/graph/export, a demo-grade unauthenticated FastAPI surface, an unvalidated grammar-install chain, hollow quality gates, and ~45–55k LOC of dead phase-scaffolding shipped in the wheel.

The remediation strategy is ordered by leverage: close the externally-reachable safety holes (SUPPLY + APISAFE) immediately as roots, make the gates honest and shrink the surface (HYGIENE → GATES) so all later work is verifiable, correct the boundary-IR serializer determinism gaps (BOUNDARYFIX), freeze the two core contracts (chunk identity and parser acquisition) that unblock the correctness work, fix the core and repo-scale defects against those frozen contracts, consolidate the interface layer, then gate a clean release. The raw material for most fixes already exists in the repo — `definition_id`/`qualified_route` (the correct identity key), the unused `grammar_manager.py` URL validator, and the boundary-IR determinism gate — so lanes reuse rather than rewrite. This is a distinct initiative from `specs/phase-plans-v1.md` (which built the boundary-IR feature) and does not modify v1 phases.

---

## Architecture North Star

The target end-state preserves the boundary-IR/canon core's behavior (its golden bytes move only where a fix intentionally corrects them, gated by regenerated goldens) while replacing the unsound surrounding machinery.

```
  security roots (parallel, no HYGIENE dependency):
     SUPPLY ── validated + integrity-checked grammar install
     APISAFE ─ authenticated, canonical-root-confined API + VFS

  verification spine:
     HYGIENE ─► GATES ─► BOUNDARYFIX ─► IDENTITY ─► COREFIX ─┐
     (sever+   (honest   (float/cache/  (chunk_id  (incr.,   │
      delete)   CI, pin)  parity)        contract)  fallbacks)├─► RELEASE
                   └────► PARSER ─► SCALE ───────────────────┘   (green gate)
                          (lease)   (streaming, git, xref,
                                     mixed-lang, vfs, leiden)
     IFACE (single CLI/detect/exporter/version) ── after GATES + APISAFE
```

Deterministic-by-default remains the invariant: identical snapshot + identical tool version → byte-identical boundary IR. No fix may introduce a new source of run/machine variance.

---

## Assumptions (fail-loud if wrong)

1. After the HYGIENE audit severs the known static import edges (`chunker/__init__.py` → `integration`, the grammar CLI → `error_handling`, `chunker/contracts/__init__.py` → `cicd`), the named subpackages are unreachable from `chunker/`, `cli/`, `api/`. The audit is fail-loud: any remaining static or dynamic (importlib) reference blocks deletion and narrows that lane to quarantine. Reachability is proven by a full local `pytest` run, never by CI-smoke green.
2. The boundary-IR golden bytes are correct on the currently-pinned pack (0.9.x); any golden change during remediation (BOUNDARYFIX, IDENTITY) is an intentional correction, regenerated via the sanctioned script, and the boundary goldens are a cross-phase single-writer artifact serialized BOUNDARYFIX → IDENTITY.
3. The FastAPI server is not yet a depended-upon public deployment, so adding auth and changing the default bind is not a breaking change. (This defuses urgency but not necessity — SUPPLY/APISAFE are still roots so the holes close on wave 1.)
4. `git`, the `phase-loop` runtime, and the frontier CLIs used by the advisor board remain available.
5. Fixing chunk identity (P5) moves `chunk_id`/`node_id` values for collision cases; downstream consumers key on the new frozen contract, and any persisted caches are invalidated by a cache-version bump.

---

## Non-Goals

- No rewrite of the boundary-IR/canon serializer's core algorithm. BOUNDARYFIX is scoped to three specific corrections (float stringification per the canon rule, real grammar-version cache-key fields, a committed cross-tool parity golden) — these are targeted fixes, not a rewrite, and they are explicitly IN scope.
- No new features, languages, or exporters — remediation only.
- No migration of the CLI to a third framework; consolidation picks one of the two existing stacks.
- No introduction of an auth provider (OAuth/OIDC) — API safety means an auth hook + canonical path confinement + safe defaults, not an identity system.
- No performance tuning beyond removing the O(n²) / segfault-class defects the review names.
- Config-system consolidation (the four-config-system MAJOR) is deferred; the deferral rationale is recorded in RELEASE's findings matrix, not left silent.

---

## Cross-Cutting Principles

1. Determinism is sacred. Every phase touching serialized output must prove byte-stability (double-run identity) and must not add dict-ordering, float-repr, locale, or path variance. This principle makes the BOUNDARYFIX float-repr fix mandatory, not optional.
2. One parser per concurrent user. After IF-0-PARSER-1, NO code path — including the public `get_parser()` and every long-lived cache (`smart_context`, `export/relationships`) — may share a tree-sitter `Parser` across threads. Safety is by construction, not by auditing a hand-picked list.
3. Identity keys on the frozen IF-0-IDENTITY-1 contract, which assigns distinct, documented roles to `definition_id`, `node_id`, `chunk_id`, and `parent_chunk_id`. No map keys on an ambiguous "chunk_id and/or definition_id".
4. Fail loud, catch narrow-but-correct. Replace the recurring wrong exception tuples with the actual exception types; never widen to bare `except` to paper over a fix.
5. No fix ships behind a skipped test. GATES may xfail only modules on a tracked, capped inventory that maps each xfail to the phase/finding that will clear it; RELEASE fails if any CRITICAL- or MAJOR-linked xfail/skip remains.
6. Security defaults are closed. No wildcard CORS with credentials, no `0.0.0.0` default bind, no clone of an unvalidated URL, no load of an artifact without repo-owned provenance (immutable commit or checksum manifest).

---

## Phase Dependency DAG

```
  ROOTS (wave 1, parallel):   HYGIENE      SUPPLY      APISAFE
                                 │                        │
                                 ▼                        │
                              GATES                       │
                                 │                        │
                    ┌────────────┼───────────┐            │
                    ▼            ▼            ▼            │
               BOUNDARYFIX    PARSER       IFACE ◄────────┘  (IFACE: GATES + APISAFE)
                    │            │
                    ▼            ▼
                 IDENTITY      SCALE ◄──────── IDENTITY, APISAFE
                    │            │             (SCALE: PARSER + IDENTITY + APISAFE)
                    ▼            │
                 COREFIX        │
                    │           │
                    └────┬──────┴──────── RELEASE ◄── SCALE, COREFIX, IFACE, SUPPLY, BOUNDARYFIX
```

Cross-phase parallelism: wave 1 is HYGIENE ∥ SUPPLY ∥ APISAFE (disjoint files; only `chunker/__init__.py` needs the HYGIENE owner). After GATES: BOUNDARYFIX, PARSER, and IFACE fan out. BOUNDARYFIX → IDENTITY is serial (shared boundary goldens). PARSER → SCALE. COREFIX (after IDENTITY) and SCALE run concurrently. Critical path: `HYGIENE → GATES → BOUNDARYFIX → IDENTITY → {COREFIX | SCALE} → RELEASE` (6 phases deep).

---

## Top Interface-Freeze Gates

These gates are the narrowest contracts that unblock downstream phases. `/claude-plan-phase` concretizes each (exact signature/schema) when it plans the owning phase.

1. **IF-0-HYGIENE-1** — The surviving public surface: the set of `chunker/` subpackages and `__init__.py` exports remaining after the audit-and-delete, plus the reachability report proving each deletion safe.
2. **IF-0-GATES-1** — The CI verification contract: the test-tier definition (push/PR vs nightly), the `automation.suite_command`, the `resolve_pack_pin() -> (lower, upper)` helper deriving the pin from `pyproject.toml`, and the capped xfail inventory mapping each xfail to its clearing phase.
3. **IF-0-SUPPLY-1** — `validate_grammar_source(url, *, allow_hosts) -> str` (raises on disallowed scheme/host, `ext::`/`file::`, leading-`-`) plus `verify_artifact(path, provenance)` where provenance is a repo-owned immutable commit or checksum manifest; consumed by EVERY clone/fetch/build/load path (inventoried, not a fixed three).
4. **IF-0-APISAFE-1** — `resolve_within_root(candidate, root) -> Path` performing CANONICAL containment (resolves symlinks; rejects absolute escape, `..`, and symlink escape for both reads and output creation) plus the request-auth dependency signature; consumed by the API handlers and the VFS `LocalFileSystem`.
5. **IF-0-BOUNDARYFIX-1** — The corrected serializer contract: the canon float-stringification function (JS-parity, not Python `repr`), the real `grammar_version` cache-key fields (pack + runtime version), and the committed cross-tool parity golden; consumed by IDENTITY's golden regeneration.
6. **IF-0-IDENTITY-1** — The chunk identity contract: the distinct, documented roles and exact seed components of `definition_id`, `node_id`, `chunk_id`, `parent_chunk_id`, and the mapping of which namespace each incremental / graph / export / equality / cache map uses. Collision-free for duplicate-named definitions, anonymous siblings, edits, moves, and insertions. Consumed by COREFIX, SCALE, and exporters.
7. **IF-0-PARSER-1** — `acquire_parser(language) -> ParserLease` / `lease.release()` (or context-manager) checkout API with per-lease exclusivity, AND a safe-by-construction public `get_parser()` (thread-local or lease-based) so no raw shared parser escapes; consumed by repo, parallel, streaming, performance, and every cache holder.

---

## Phases

### Phase 1 — Surface Reduction & Dead-Code Removal (HYGIENE)

**Objective**
Audit static/dynamic reachability, sever the import edges that make dead subpackages falsely reachable, then delete them so every later fix targets real code and P2's tightened lint doesn't drown in dead-code noise.

**Exit criteria**
- [ ] Reachability audit recorded (import graph + importlib grep). The known false-reachability edges are severed first: `chunker/__init__.py` → `integration` (the swallow-all try/except block), the grammar CLI → `error_handling`, `chunker/contracts/__init__.py` → `cicd`. Any surviving reference blocks that subpackage's deletion (narrows to quarantine).
- [ ] Dead subpackages removed (or quarantined per audit): `extractors/`, `integration/`, `error_handling/` (core keeps `_internal/error_handling.py`), `testing/`, `deployment/`, `devenv/`, `distribution/`, `cicd/`, `monitoring/`.
- [ ] Duplicate `PluginConfig` collapsed to one definition; the six never-raised exception classes removed from `exceptions.py`.
- [ ] Root cruft removed and git-ignored: `test_api.py`, `test_symbol_extraction.py`, `test_csharp.cs`, `test_tsx.tsx`, `test_wasm.wat`, `tmp_test.Rmd`, `compatibility.db`, `troubleshooting.db`, `validation_report.json`, `setup.py.bak`, stale `CODE_REVIEW_REPORT.md`; `ide/**/node_modules/` and `*.db` untracked; `mcp_server.log` git-ignored.
- [ ] Full LOCAL `pytest` run passes (not CI-smoke) — proof no live path depended on removed code.

**Scope notes**
- Decompose into 6 lanes: (0) reachability audit + import-edge severing — MUST land before any deletion lane; (a) `extractors/` + `testing/`; (b) `integration/` + `error_handling/`; (c) `deployment/` + `devenv/` + `distribution/` + `cicd/` + `monitoring/`; (d) `PluginConfig` dedupe + `exceptions.py` prune; (e) root cruft + `.gitignore` + untracking.
- Parallelism: lane (0) is a gate for (a)–(c); (d) and (e) are independent.
- Single-writer file: `chunker/__init__.py` (lane 0 severs imports; deletion lanes remove exports) — lane (0) owns all `__init__.py` edits; other lanes hand it export deltas.

**Non-goals**
- No behavior change to surviving code; no config-system consolidation (deferred to RELEASE matrix).

**Key files**
- `chunker/__init__.py`
- `chunker/contracts/__init__.py`
- `chunker/exceptions.py`
- `chunker/languages/base.py`
- `chunker/languages/plugin_base.py`
- `.gitignore`

**Depends on**
- (none)

**Produces**
- IF-0-HYGIENE-1

**Spec closeout policy**
- schema: `spec_delta_closeout.v1`
- decision: `no_spec_delta`
- target surfaces: `(none)`
- evidence paths: `logs/hygiene-reachability-audit.txt`
- redaction posture: `metadata_only`

---

### Phase 2 — Quality-Gate Honesty (GATES)

**Objective**
Make the CI signal real: run the full/tiered suite, enforce lint correctness and mypy, derive the pack pin from a single source of truth, harden the CI workflows, and cap the xfail inventory.

**Exit criteria**
- [ ] CI executes the full test suite, or an explicit documented tiering (push/PR + nightly) naming every module; `tests/test_canon_vectors.py` and `spec_tests/` are wired in.
- [ ] `pyproject.toml` ruff `ignore` no longer suppresses `F401`, `F403`, `F811`, `F821`, `F841` (and `E722`); the tree is clean under the tightened config.
- [ ] mypy failures are blocking in CI (no `::warning` downgrade), consistent with `strict = true`.
- [ ] The conformance gate derives the pack pin from `pyproject.toml` via `resolve_pack_pin()`; `tests/boundary_ir_conformance.py` and `scripts/regenerate_boundary_goldens.py` use it; a test asserts the gate rejects `0.10`+ (the #84/#86 drift).
- [ ] All `.github/workflows/*` (moved here from SUPPLY): top-level `permissions: contents: read` (elevate per-job), `uses:` pinned to commit SHAs, `workflow_dispatch` inputs passed via `env:` not interpolated into `run:`.
- [ ] Any quarantined-failing module is on a CAPPED, tracked xfail inventory that maps each entry to the phase/finding that clears it; `automation.suite_command` documented and green.

**Scope notes**
- Decompose into 5 lanes: (a) CI workflow tiering + wire canon/spec_tests; (b) ruff F-rule un-ignore + cleanup (relies on HYGIENE deletions); (c) mypy blocking + triage; (d) pin-derivation helper + conformance/regenerate wiring + drift test + xfall-cap inventory; (e) workflow security hardening (perms, SHA pins, dispatch injection).
- Parallelism: publish `resolve_pack_pin()` signature day-1. Lanes (a) and (e) both edit `.github/workflows/*` — assign lane (a) to own the workflow files; lane (e) hands it the security delta (they are now in ONE phase, so no cross-phase collision with SUPPLY).
- Single-writer file: `pyproject.toml` (lanes b and d) — lane (d) owns it.

**Non-goals**
- No fixing of the bugs newly-run tests surface (those route to later phases); this phase makes them visible and caps their xfails.

**Key files**
- `.github/workflows/ci.yml`
- `.github/workflows/test.yml`
- `.github/workflows/*.yml`
- `scripts/run_ci_smoke.py`
- `scripts/run_platform_core.py`
- `pyproject.toml`
- `tests/boundary_ir_conformance.py`
- `scripts/regenerate_boundary_goldens.py`

**Depends on**
- HYGIENE

**Produces**
- IF-0-GATES-1

**Spec closeout policy**
- schema: `spec_delta_closeout.v1`
- decision: `canonical_spec_update`
- target surfaces: `tests/boundary_ir_conformance.py`, `.github/workflows/*.yml`
- evidence paths: `logs/gates-ci-run.txt`
- redaction posture: `metadata_only`

---

### Phase 3 — Supply-Chain & Grammar-Install Hardening (SUPPLY)

**Objective**
Close the grammar-install code-execution surface across EVERY live path: validate every clone URL, verify downloaded artifacts against repo-owned provenance before they are compiled and `CDLL`-loaded, and harden the build/plugin paths.

**Exit criteria**
- [ ] `validate_grammar_source()` (strict scheme allowlist, exact-host allowlist that rejects `github.com.evil.example`, rejects `ext::`/`file::`/leading-`-`) is the ONLY path to a `git clone` across the inventoried set: `grammar_management/core.py`, `grammar_management/cli.py`, `grammar/manager.py`, `grammar_manager.py`, and `_internal/user_grammar_tools.py` (the live argparse-CLI clone path via `UserGrammarTools`).
- [ ] `git checkout <version>` / `--branch <branch>` use a `--` separator; `version`/`branch` validated against a safe pattern.
- [ ] Grammar downloads resolve to an immutable commit (no bare `master` default); `verify_artifact()` checks a repo-owned checksum manifest before `cc` compile / `ctypes.CDLL` load — the trusted hash's provenance is frozen, not attacker-supplied.
- [ ] `build/builder.py` `tarfile.extractall` uses `filter="data"` and validates member paths.
- [ ] Plugin loading trust boundary documented; watched dirs treated as privileged (no default untrusted dir).

**Scope notes**
- Decompose into 3 lanes: (a) URL validator + route ALL inventoried clone paths + `--` separator; (b) download provenance/pinning + `verify_artifact` before compile/load; (c) tarfile filter + plugin trust doc/guard.
- Parallelism: publish IF-0-SUPPLY-1 signatures day-1. CI workflow hardening moved to GATES lane (e) — SUPPLY no longer touches `.github/`, removing the GATES∥SUPPLY collision.
- Note: lane (b) closes the real unconditional RCE (compile+load of unverified source); `ext::` hardening in lane (a) is defense-in-depth (git blocks it by default).

**Non-goals**
- No signing infrastructure (repo-owned checksum manifest suffices); no plugin sandbox/subprocess isolation.

**Key files**
- `chunker/grammar_management/core.py`
- `chunker/grammar_management/cli.py`
- `chunker/grammar/manager.py`
- `chunker/grammar_manager.py`
- `chunker/_internal/user_grammar_tools.py`
- `chunker/grammar/download.py`
- `chunker/build/builder.py`
- `chunker/plugin_manager.py`

**Depends on**
- (none)

**Produces**
- IF-0-SUPPLY-1

**Spec closeout policy**
- schema: `spec_delta_closeout.v1`
- decision: `no_spec_delta`
- target surfaces: `(none)`
- evidence paths: `logs/supply-negative-tests.txt`
- redaction posture: `metadata_only`

---

### Phase 4 — API & VFS Surface Safety (APISAFE)

**Objective**
Turn the demo-grade FastAPI server and the VFS `LocalFileSystem` into safe-by-default surfaces: authenticated, canonically root-confined, size-bounded, no injection, no drive-by; and resolve the `/graph/cut` stub product decision here so SCALE has a stable target.

**Exit criteria**
- [ ] `/chunk/file`, `/graph/xref`, `/export/postgres` require an auth dependency and confine every path argument via `resolve_within_root()` to a configured root; no arbitrary absolute path is read.
- [ ] `resolve_within_root()` performs canonical containment (resolves symlinks; rejects absolute escape, `..`, AND symlink escape) for both reads and output creation; `chunker/_internal/vfs.py` `LocalFileSystem` uses it (the C5 arbitrary-read + sandbox-escape closed, with symlink-escape tests).
- [ ] CORS no longer combines `allow_origins=["*"]` with `allow_credentials=True`; request body size capped; the entrypoint does not default-bind `0.0.0.0`.
- [ ] The generated `chunker_export.sql` escapes/parameterizes all interpolated fields (`id`, `file`, `symbol`, not just `attrs_json`); `/export/postgres` cannot connect to an unapproved DSN host.
- [ ] `/graph/cut` product decision FROZEN and executed here (implement against real nodes/edges, or remove from the advertised surface AND update `spec_tests/test_graph_cut.py` accordingly) — SCALE consumes the result.

**Scope notes**
- Decompose into 4 lanes: (a) auth dependency + path confinement on the three handlers; (b) CORS + size cap + bind default + entrypoint; (c) `resolve_within_root` canonical helper + VFS sandbox fix + symlink tests; (d) postgres SQL-file escaping + DSN allowlist + `/graph/cut` keep/remove decision.
- Parallelism: freeze IF-0-APISAFE-1 (resolver + auth signatures) day-1 so lanes (a) and (c) share it. This phase OWNS `chunker/graph/cut.py`; SCALE depends on APISAFE for its determinism follow-on.
- Single-writer file: `api/server.py` (lanes a, b, d) — lane (a) owns it.

**Non-goals**
- No auth provider/identity system; no rewrite of exporters (schema consolidation is IFACE).

**Key files**
- `api/server.py`
- `chunker/_internal/vfs.py`
- `chunker/export/postgres_spec_exporter.py`
- `chunker/graph/cut.py`

**Depends on**
- (none)

**Produces**
- IF-0-APISAFE-1

**Spec closeout policy**
- schema: `spec_delta_closeout.v1`
- decision: `no_spec_delta`
- target surfaces: `(none)`
- evidence paths: `logs/apisafe-symlink-auth-tests.txt`
- redaction posture: `metadata_only`

---

### Phase 5 — Boundary-IR Serializer Determinism (BOUNDARYFIX)

**Objective**
Close the three orphaned Boundary-IR MAJORs that the review names and Cross-Cutting Principle #1 forbids leaving open: cross-language float divergence, the constant grammar-version cache key, and the self-referential parity proof.

**Exit criteria**
- [ ] `chunker/boundary/serialization.py` `_floats_to_strings` uses a canon-defined, JS-Number-parity stringification (not Python `repr`); a test asserts `1e-05`-class values match the TypeScript canon port.
- [ ] `chunker/boundary/adapter.py` `_grammar_version()` returns a real fingerprint; pack + runtime versions are added to `BOUNDARY_CACHE_KEY_FIELDS` so an incremental recompute across a pack bump does not reuse stale nodes (no Frankenstein IR).
- [ ] A committed cross-tool parity golden replaces the self-referential `test_boundary_parity_view.py` assertion; the parity digest is compared against a stored fixture, not against a second in-process computation.
- [ ] Boundary goldens regenerated (sanctioned script) reflecting the corrected float formatting; determinism double-run identity holds. (Goldens are the shared artifact handed to IDENTITY.)

**Scope notes**
- Decompose into 3 lanes: (a) float stringification + JS-parity test; (b) `_grammar_version` fingerprint + cache-key fields; (c) committed cross-tool parity golden + regen.
- Parallelism: lanes touch disjoint files (`serialization.py` vs `adapter.py` vs the parity test/golden) but ALL regenerate goldens — lane (c) owns the final golden regen after (a)/(b) land.
- Serial with IDENTITY (both mutate boundary goldens): BOUNDARYFIX regenerates first, IDENTITY second.

**Non-goals**
- No broader serializer rewrite; no change to the canon Unicode pin.

**Key files**
- `chunker/boundary/serialization.py`
- `chunker/boundary/adapter.py`
- `chunker/boundary/types.py`
- `tests/test_boundary_parity_view.py`
- boundary goldens

**Depends on**
- GATES

**Produces**
- IF-0-BOUNDARYFIX-1

**Spec closeout policy**
- schema: `spec_delta_closeout.v1`
- decision: `canonical_spec_update`
- target surfaces: `chunker/boundary/serialization.py`, boundary goldens
- evidence paths: `logs/boundaryfix-parity-golden.txt`
- redaction posture: `metadata_only`

---

### Phase 6 — Chunk Identity Redesign (IDENTITY)

**Objective**
Freeze the id contract and make identity collision-free: assign distinct roles to `definition_id`/`node_id`/`chunk_id`/`parent_chunk_id`, pick the exact seed, and re-key every consuming map so no chunk is silently dropped.

**Exit criteria**
- [ ] IF-0-IDENTITY-1 frozen: documented role + exact seed components for each of `definition_id`, `node_id`, `chunk_id`, `parent_chunk_id`, and a table of which map (incremental, graph, export, equality, cache) uses which namespace. No map keys on an ambiguous union.
- [ ] The chosen `chunk_id` seed incorporates the qualified (named) route and/or position so two byte-identical siblings under same-typed ancestors get distinct ids; a property test asserts no collision across duplicate-named definitions, anonymous siblings, edits, moves, and insertions.
- [ ] `tmp_to_final` and every `{id: chunk}` / `parent_chunk_id` linkage keys per the frozen contract; no chunk dropped by de-duplication.
- [ ] `spec_tests/test_codechunk_ids_backcompat.py` is reconciled: either the `chunk_id == node_id` / `len == 40` invariants are preserved, or the spec_test is updated in lockstep with a documented back-compat decision.
- [ ] Persisted-cache version bumped; boundary goldens regenerated on top of BOUNDARYFIX's; determinism double-run identity holds.

**Scope notes**
- Decompose into 3 lanes: (a) contract freeze + id derivation in `types.py`/`core.py`; (b) audit + re-key all consuming maps (incremental, graph, export); (c) fixtures + property tests + spec_test reconciliation + golden regen.
- Parallelism: publish IF-0-IDENTITY-1 day-1 so lane (b), COREFIX, and SCALE start against the frozen contract. SCALE's graph re-key consumes this, so SCALE depends on IDENTITY.
- Single-writer: `chunker/core.py` (this phase, then COREFIX) and boundary goldens (BOUNDARYFIX, then this phase).

**Non-goals**
- No change to `definition_id` computation semantics (already correct); no incremental-diff logic fix (COREFIX consumes this contract).

**Key files**
- `chunker/types.py`
- `chunker/core.py`
- `chunker/graph/`
- `chunker/export/`
- `spec_tests/test_codechunk_ids_backcompat.py`

**Depends on**
- BOUNDARYFIX

**Produces**
- IF-0-IDENTITY-1

**Spec closeout policy**
- schema: `spec_delta_closeout.v1`
- decision: `canonical_spec_update`
- target surfaces: `chunker/types.py`, `spec_tests/test_codechunk_ids_backcompat.py`
- evidence paths: `logs/identity-collision-test.txt`
- redaction posture: `metadata_only`

---

### Phase 7 — Parser Concurrency Safety (PARSER)

**Objective**
Eliminate the shared-`Parser` segfault class by construction: a checkout API AND a safe public `get_parser()`, so no raw shared parser can escape to any caller or cache.

**Exit criteria**
- [ ] `acquire_parser(language)` returns an exclusively-leased parser removed from the shared cache/pool for the lease's lifetime; `release()` (or context-manager exit) returns it; no object is ever in cache and pool simultaneously.
- [ ] The public `get_parser()` is safe by construction (thread-local or lease/context-manager based) — it no longer hands out a raw cached parser. An inventory of every parser holder (`repo/processor.py`, `performance/optimization/*`, `memory_pool.py`, `smart_context`, `export/relationships/*`) is recorded and each migrated or confirmed safe.
- [ ] Factory cold-miss create + `LRUCache.put` are lock-guarded (no init race, no discarded freshly-built parser, no inflated count).
- [ ] The version-mismatch regex (`factory.py:173`) matches; the wrong `except (ImportError, Exception)` / `(AttributeError, KeyError, ..., Full)` tuples corrected.
- [ ] A concurrency stress test covers the public API, overlapping parses, parse exceptions, and guaranteed lease return, clean under repeated runs.

**Scope notes**
- Decompose into 3 lanes: (a) checkout API + safe public `get_parser()` + cache/pool ownership; (b) init-race locking + regex/exception fixes; (c) holder inventory + stress-test harness.
- Parallelism: publish IF-0-PARSER-1 day-1 so SCALE plans against it.
- Single-writer file: `chunker/_internal/factory.py` (lanes a and b) — lane (a) owns it.

**Non-goals**
- No switch to multiprocessing-only.

**Key files**
- `chunker/_internal/factory.py`
- `chunker/parser.py`

**Depends on**
- GATES

**Produces**
- IF-0-PARSER-1

**Spec closeout policy**
- schema: `spec_delta_closeout.v1`
- decision: `no_spec_delta`
- target surfaces: `(none)`
- evidence paths: `logs/parser-stress-test.txt`
- redaction posture: `metadata_only`

---

### Phase 8 — Concurrency & Repo-Scale Correctness (SCALE)

**Objective**
Fix the repo-scale and streaming defects on top of the safe parser API and the frozen identity/API contracts: correct or delete the broken streaming/mixed-language/VFS paths, make parallelism and git integration sound, and restore determinism to clustering/graph.

**Exit criteria**
- [ ] All parser holders acquire via IF-0-PARSER-1; no shared-parser path remains.
- [ ] `streaming.py` derives node types from the language-config registry (or the broken path is removed) — non-Python languages yield correct chunks or an explicit error, never silent empty.
- [ ] `multi_language.process_mixed_file` calls a real `chunk_file` signature (C3 fixed); `vfs_chunker` streaming works for Zip/HTTP backends with correct, non-duplicated, file-relative offsets, and uses APISAFE's confined `LocalFileSystem` (does not reopen the sandbox hole).
- [ ] `parallel.py` timeout actually cancels/stops a hung worker; `performance/optimization/incremental.py` uses the tree's real language (not hardcoded `python`).
- [ ] `leidenalg.find_partition` is seeded; `graph/cut.py` tie-order is deterministic on the version APISAFE froze; `graph/xref.py` uses a name→chunk index (no O(n²)) keyed on the frozen IF-0-IDENTITY-1 ids.
- [ ] Git integration: one `git.Repo` per operation with `.close()`, `check-ignore` not spawned per file, stale-commit `BadName` falls back to full scan, `watch_repository` has a stop condition and does not busy-loop non-git dirs.

**Scope notes**
- Decompose into 6 lanes by disjoint file: (a) parser-holder migration + `parallel.py` timeout; (b) `streaming.py` rewrite; (c) `multi_language.py` + `vfs_chunker.py` (consuming APISAFE's vfs); (d) clustering/graph determinism + xref index (consuming IDENTITY); (e) ALL `repo/processor.py` changes (git lifecycle + watch loop) — one lane owns this file; (f) `performance/optimization/incremental.py` language fix.
- Correction from draft: `repo/processor.py` is a single-writer owned entirely by lane (e); lane (a)'s parser migration there routes through lane (e).
- Depends on PARSER (lease API), IDENTITY (id-keyed maps), and APISAFE (confined vfs + frozen `/graph/cut`).

**Non-goals**
- No new streaming architecture beyond correctness; no distributed processing.

**Key files**
- `chunker/repo/processor.py`
- `chunker/streaming.py`
- `chunker/multi_language.py`
- `chunker/vfs_chunker.py`
- `chunker/parallel.py`
- `chunker/clustering/engine.py`
- `chunker/graph/xref.py`
- `chunker/graph/cut.py`
- `chunker/performance/optimization/`

**Depends on**
- PARSER
- IDENTITY
- APISAFE

**Produces**
- IF-0-SCALE-1

**Spec closeout policy**
- schema: `spec_delta_closeout.v1`
- decision: `no_spec_delta`
- target surfaces: `(none)`
- evidence paths: `logs/scale-streaming-determinism.txt`
- redaction posture: `metadata_only`

---

### Phase 9 — Core Chunk Correctness (COREFIX)

**Objective**
Fix the per-chunk correctness bugs against the frozen identity contract: incremental diff, fallback robustness, span/line consistency, offset correctness, and the smart-context O(n²).

**Exit criteria**
- [ ] Incremental content-diff reparses with the real `file_path` and classifies true body edits as MODIFIED via `definition_id` (IF-0-IDENTITY-1); a one-line-edit fixture produces a minimal diff, not all-ADDED/all-DELETED.
- [ ] Fallback paths catch the actual failure types (`LanguageNotFoundError` / `ParserError`, …) so the zero-config API falls back instead of crashing; file reads use `errors="replace"` where core does.
- [ ] The dead `end_line` conditional is fixed so span-extended chunks (Dart, R) report line ranges consistent with their bytes; Svelte control-flow chunks are emitted once.
- [ ] Token split sub-chunks carry correct `byte_start` / `byte_end` / `start_line`; fallback chunkers store true byte offsets (not char offsets) with no O(n²) newline scan.
- [ ] `smart_context` caches include the candidate set in the key (no stale cross-repo results), AND the O(n²) all-pairs feature extraction is replaced with an indexed/bounded approach.
- [ ] `_walk` has a recursion-depth guard that degrades to fallback instead of `RecursionError`.

**Scope notes**
- Decompose into 5 lanes by file: (a) `incremental.py` (consumes IDENTITY); (b) `auto.py` + `chunker.py` fallback/encoding; (c) `core.py` end_line + Svelte + `_walk` depth guard; (d) `token/chunker.py` split offsets; (e) fallback byte-offset correctness + `smart_context.py` cache key + O(n²) fix.
- Correction from draft: the public `chunk_text()` in-memory fix moved to IFACE (which owns `__init__.py`), removing the COREFIX∥IFACE collision on that file. COREFIX no longer edits `__init__.py`.
- Single-writer file: `chunker/core.py` (lane c) — owned here after IDENTITY.

**Non-goals**
- No identity redesign (IDENTITY); no streaming fixes (SCALE); no `__init__.py` edits (IFACE).

**Key files**
- `chunker/incremental.py`
- `chunker/auto.py`
- `chunker/chunker.py`
- `chunker/core.py`
- `chunker/token/chunker.py`
- `chunker/fallback/`
- `chunker/fallback_overlap/`
- `chunker/smart_context.py`

**Depends on**
- IDENTITY

**Produces**
- IF-0-COREFIX-1

**Spec closeout policy**
- schema: `spec_delta_closeout.v1`
- decision: `no_spec_delta`
- target surfaces: `(none)`
- evidence paths: `logs/corefix-incremental-span-tests.txt`
- redaction posture: `metadata_only`

---

### Phase 10 — Interface Consolidation (IFACE)

**Objective**
Collapse the forked interface layer onto single sources of truth: one CLI stack, one language-detection map, one exporter schema per format, consistent versioning, and the in-memory public `chunk_text`.

**Exit criteria**
- [ ] One CLI stack (typer `cli/` or argparse `chunker/cli/`) owns grammar management, resolution-mode defaults, and flag conventions; the other is removed or thinly delegates. No divergent `--resolution-mode` defaults or `-o` meanings.
- [ ] A single shared language-detection ext-map (used by CLI, API, exporters) — `.ts` and all languages resolve identically everywhere; unknown extensions warn rather than silently return `[]`.
- [ ] One parquet exporter schema per format (the `chunker/exporters/` vs `chunker/export/formats/` split resolved); the `gzip.Path` bug fixed so `compress=True` works and is tested.
- [ ] Public `chunker.chunk_text()` no longer round-trips through a temp file (moved here from COREFIX; owns the `__init__.py` edit).
- [ ] Version single-sourced: `_version.py` corrected or generated, `__init__` fallback matches, `/health` and OpenAPI report the real version.

**Scope notes**
- Decompose into 4 lanes: (a) CLI unification; (b) shared detection map; (c) exporter consolidation + gzip fix; (d) versioning + public `chunk_text` in-memory path.
- Single-writer file: `chunker/__init__.py` — owned by HYGIENE for deletions (wave 1), then by IFACE lane (d) here; never concurrent with COREFIX (which no longer touches it).

**Non-goals**
- No new CLI commands or export formats; no config-system unification.

**Key files**
- `cli/main.py`
- `chunker/cli/`
- `api/server.py`
- `chunker/export/formats/`
- `chunker/exporters/`
- `chunker/_version.py`
- `chunker/__init__.py`

**Depends on**
- GATES
- APISAFE

**Produces**
- IF-0-IFACE-1

**Spec closeout policy**
- schema: `spec_delta_closeout.v1`
- decision: `no_spec_delta`
- target surfaces: `(none)`
- evidence paths: `logs/iface-detection-parity.txt`
- redaction posture: `metadata_only`

---

### Phase 11 — Release Gate (RELEASE)

**Objective**
Prove the whole remediation landed and produce a release. Explicitly a RELEASE-PREPARATION gate: it verifies, builds, and tags a candidate; actual PyPI publication remains the separate GitHub release workflow (per README).

**Exit criteria**
- [ ] Full/tiered suite green under the P2 gates (ruff F-rules on, mypy blocking, canon vectors + spec_tests run); determinism double-run byte-identity holds across all supported languages.
- [ ] Conformance gate rejects a drifted pack (derived pin) in a test; goldens current on the correct pack.
- [ ] Security negative-tests pass: malicious clone URL/artifact rejected (all inventoried paths), API auth + canonical/symlink path confinement enforced, tarfile traversal blocked.
- [ ] A finding-to-phase-to-test traceability matrix exists; RELEASE FAILS if any CRITICAL- or MAJOR-linked xfail/skip remains, or any CRITICAL/MAJOR is unmapped. The deferred config-system MAJOR is recorded with rationale (not a silent gap).
- [ ] Version bumped, `CHANGELOG.md` updated, wheel builds and installs cleanly, candidate tagged.

**Scope notes**
- Decompose into 3 lanes: (a) full-suite + determinism run; (b) security negative-test sweep; (c) traceability matrix + version bump + changelog + wheel build/tag.
- Parallelism: lanes (a) and (b) concurrent; lane (c) folds results into the release candidate.

**Non-goals**
- No new remediation work; no PyPI publish (that is the existing release workflow).

**Key files**
- `pyproject.toml`
- `CHANGELOG.md`
- `chunker/_version.py`
- `CODE_REVIEW_v3.2.2.md`

**Depends on**
- SCALE
- COREFIX
- IFACE
- SUPPLY
- BOUNDARYFIX

**Produces**
- IF-0-RELEASE-1

**Spec closeout policy**
- schema: `spec_delta_closeout.v1`
- decision: `governed_pipeline_refresh`
- target surfaces: `CHANGELOG.md`, `pyproject.toml`
- evidence paths: `logs/release-green-ci.txt`
- redaction posture: `metadata_only`

---

## Execution Notes

- **Planning**: `/claude-plan-phase <ALIAS>` for each phase. Wave 1 roots — HYGIENE, SUPPLY, APISAFE — can be planned and executed concurrently (disjoint files; only `chunker/__init__.py` is HYGIENE-owned). Closing the external security holes no longer waits on dead-code deletion.
- **Cross-phase parallelism**: after GATES, BOUNDARYFIX / PARSER / IFACE fan out. BOUNDARYFIX → IDENTITY is serial (shared boundary goldens). COREFIX (after IDENTITY) and SCALE (after PARSER + IDENTITY + APISAFE) run concurrently.
- **Execution**: `/claude-execute-phase <alias>` after each plan is approved.
- **Critical path**: `HYGIENE → GATES → BOUNDARYFIX → IDENTITY → {COREFIX | SCALE} → RELEASE` — six phases deep.
- **Single-writer files across phases** (owners): `chunker/__init__.py` — HYGIENE (deletions) then IFACE (version + chunk_text); COREFIX does NOT touch it. `.github/workflows/*` — GATES only (SUPPLY hardening folded in). boundary goldens + `chunker/boundary/serialization.py` — BOUNDARYFIX then IDENTITY, never concurrent. `chunker/core.py` — IDENTITY then COREFIX. `chunker/graph/cut.py` + `chunker/_internal/vfs.py` — APISAFE owns; SCALE depends on APISAFE. `chunker/repo/processor.py` — SCALE lane (e) only. `chunker/_internal/factory.py` — PARSER only. `api/server.py` — APISAFE then IFACE. `pyproject.toml` — GATES (ruff/pin) then RELEASE (version).

---

## Acceptance Criteria

- [ ] Every CRITICAL and MAJOR finding in `CODE_REVIEW_v3.2.2.md` is resolved or explicitly deferred with rationale in the RELEASE traceability matrix — including the three Boundary-IR MAJORs (BOUNDARYFIX) and the deferred config-system MAJOR.
- [ ] Honest gates enforced: `ruff` with F-rules, blocking `mypy --strict`, full/tiered CI including canon vectors and `spec_tests/`; no CRITICAL/MAJOR-linked xfail survives to RELEASE.
- [ ] No shared tree-sitter `Parser` across threads via ANY path including public `get_parser()`; concurrency stress test clean.
- [ ] Chunk identity contract frozen and collision-free; no dropped chunks on the sibling fixture.
- [ ] API authenticated + canonically root-confined (symlink-escape tested); every inventoried grammar-install path validated + integrity-checked.
- [ ] Boundary-IR determinism holds (including JS-parity floats and a real cross-tool parity golden) and the conformance gate rejects a drifted pack.

---

## Verification

Concrete checks proving the roadmap delivered (run after RELEASE merges):

```bash
# 1. Honest gates: full/tiered suite runs, lint correctness on, mypy blocking
ruff check chunker cli api            # F401/F811/F821 enforced, exit 0
mypy chunker                          # strict, blocking, exit 0
phase-loop validate-roadmap specs/phase-plans-v2.md

# 2. Determinism: identical bytes across two runs; JS-parity floats; gate rejects drifted pack
python -m pytest tests/test_boundary_ir_determinism.py tests/test_canon_vectors.py tests/test_boundary_parity_view.py spec_tests/ -q
python -m pytest tests/boundary_ir_conformance.py -q

# 3. Concurrency safe: N-thread stress incl. public get_parser(), no crash/corruption
python -m pytest tests/ -k "concurren or parser_lease or thread or get_parser" -q

# 4. Identity: sibling fixture yields distinct ids, no dropped chunks, back-compat spec reconciled
python -m pytest tests/ spec_tests/ -k "chunk_id_collision or identity or codechunk_ids_backcompat" -q

# 5. Security negative-tests: all clone paths + canonical/symlink confinement + tarfile
python -m pytest tests/ -k "grammar_source_validation or path_traversal or symlink or api_auth or tarfile" -q

# 6. Interfaces: one detection map, compress round-trip works, versions agree
python -m pytest tests/ -k "detection_parity or gzip_compress or version" -q
curl -s localhost:8000/health         # reports the real v3.x version
```

Each numbered block maps to the phases that make it pass: (1) GATES, (2) BOUNDARYFIX/GATES/IDENTITY/SCALE, (3) PARSER/SCALE, (4) IDENTITY/COREFIX, (5) SUPPLY/APISAFE, (6) IFACE.

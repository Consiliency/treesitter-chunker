---
phase_loop_plan_version: 1
phase: GATES
roadmap: specs/phase-plans-v2.md
roadmap_sha256: c823c7f97987e4b68d451541507bf69c9271af17480c826f88725e41be0186dc
---

# GATES: Quality-Gate Honesty

## Context

The review's core systemic finding is that the CI signal is hollow: ruff's `select` block advertises
40 rule families but the `ignore` list guts pyflakes correctness (`F401`, `F403`, `F811`, `F821`,
`F841`, `E722` — 7 present in `pyproject.toml`); mypy is downgraded to `::warning::` in
`.github/workflows/test.yml:71-72` and `ci.yml` despite `strict = true`; CI runs only curated
subsets (`scripts/run_ci_smoke.py`, `scripts/run_platform_core.py`) of ~230 test modules; and the
determinism conformance gate's pack pin `PINNED_LANGUAGE_PACK = (("0.9","1.0"), …)`
(`tests/boundary_ir_conformance.py:58`) has DRIFTED from pyproject's load-bearing `<0.10` cap,
so it accepts exactly the 0.10–0.13 pack float that the #84/#86 incident proved dangerous.

GATES makes the signal real. It also formally owns "full-suite honesty": HYGIENE deferred the
pre-existing phase-9 docstring env artifact here (a determinism-sensitive test that fails on
unmodified base code in this worktree's env but passes in a fresh build). GATES resolves the suite
baseline — either by fixing the env sensitivity or by a capped, tracked xfail mapped to a clearing
owner — so downstream phases inherit a green baseline.

## Interface Freeze Gates
- [ ] IF-0-GATES-1 — `resolve_pack_pin() -> tuple[str, str]` (lower, upper) that parses the
  `tree-sitter-language-pack` version cap from `pyproject.toml` as the single source of truth; the
  conformance gate and regenerate script consume it, and a drift test asserts the gate rejects a
  `0.10`+ pack. Plus the capped xfail inventory (module → clearing phase/reason) and the documented
  push/PR-vs-nightly test-tier definition + `automation.suite_command`.

## Lane Index & Dependencies

SL-1 — Pack-pin single source of truth + drift test
  Depends on: (none)
  Blocks: SL-4
  Parallel-safe: yes

SL-2 — Ruff correctness-rule enforcement
  Depends on: (none)
  Blocks: SL-4
  Parallel-safe: yes

SL-3 — CI tiering + mypy blocking + workflow hardening + xfail cap
  Depends on: (none)
  Blocks: SL-4
  Parallel-safe: yes

SL-4 — Documentation & spec reconciliation (SL-docs)
  Depends on: SL-1, SL-2, SL-3
  Blocks: (none)
  Parallel-safe: no

## Lanes

### SL-1 — Pack-pin single source of truth + drift test
- **Scope**: Add `resolve_pack_pin()` that derives the language-pack version bound from `pyproject.toml`, route the conformance gate + regenerate script through it, and add a drift test that fails if a `0.10`+ pack is accepted.
- **Owned files**: `chunker/_internal/pack_pin.py`, `tests/boundary_ir_conformance.py`, `scripts/regenerate_boundary_goldens.py`, `tests/test_pack_pin_drift.py`
- **Interfaces provided**: IF-0-GATES-1 (`resolve_pack_pin`)
- **Interfaces consumed**: (none)
- **Tasks**:

| Task ID | Type | Depends on | Files in scope | Tests owned | Test command |
|---|---|---|---|---|---|
| SL-1.1 | test | — | `tests/test_pack_pin_drift.py` | `resolve_pack_pin()` returns the pyproject bound; conformance gate rejects a simulated `0.10.0`/`0.13.0` pack; accepts `0.9.0` | `uv run --with toml --all-extras python -m pytest tests/test_pack_pin_drift.py -q` |
| SL-1.2 | impl | SL-1.1 | `chunker/_internal/pack_pin.py` | — | — |
| SL-1.3 | impl | SL-1.2 | `tests/boundary_ir_conformance.py`, `scripts/regenerate_boundary_goldens.py` | — | — |
| SL-1.4 | verify | SL-1.3 | conformance gate | drift + conformance | `uv run --with toml --all-extras python -m pytest tests/test_pack_pin_drift.py tests/boundary_ir_conformance.py -q` |

### SL-2 — Ruff correctness-rule enforcement
- **Scope**: Remove the pyflakes/bugbear correctness rules from the ruff `ignore` list and make the tree clean under the tightened config (baseline-suppress only via a tracked, shrinking per-file allowlist if strictly needed).
- **Owned files**: `pyproject.toml`
- **Interfaces provided**: tightened ruff config (no `F401`/`F403`/`F811`/`F821`/`F841`/`E722` in ignore)
- **Interfaces consumed**: (none)
- **Tasks**:

| Task ID | Type | Depends on | Files in scope | Tests owned | Test command |
|---|---|---|---|---|---|
| SL-2.1 | test | — | `pyproject.toml` | (assertion is the ruff run itself) | `uv run --with toml --all-extras ruff check chunker cli api` |
| SL-2.2 | impl | SL-2.1 | `pyproject.toml` | — | — |
| SL-2.3 | verify | SL-2.2 | whole tree | ruff clean | `uv run --with toml --all-extras ruff check chunker cli api` |

### SL-3 — CI tiering + mypy blocking + workflow hardening + xfail cap
- **Scope**: Make CI run a documented full/tiered suite (push/PR + nightly) that names every module and wires `tests/test_canon_vectors.py` + `spec_tests/`; make mypy blocking (drop the `::warning::` downgrade); harden all workflows (top-level `permissions: contents: read`, SHA-pinned `uses:`, `workflow_dispatch` via `env:`); and establish the capped, tracked xfail inventory (including the phase-9 docstring baseline artifact) mapped to clearing owners.
- **Owned files**: `.github/workflows/ci.yml`, `.github/workflows/test.yml`, `.github/workflows/build.yml`, `.github/workflows/release.yml`, `.github/workflows/docs.yml`, `.github/workflows/packages.yml`, `.github/workflows/build-wheels.yml`, `.github/workflows/maintenance.yml`, `scripts/run_ci_smoke.py`, `scripts/run_platform_core.py`, `docs/development/xfail-inventory.md`
- **Interfaces provided**: IF-0-GATES-1 (test-tier definition + `automation.suite_command` + xfail inventory)
- **Interfaces consumed**: (none — the conformance pytest step SL-1 wired is exercised at CI runtime, not imported here)
- **Tasks**:

| Task ID | Type | Depends on | Files in scope | Tests owned | Test command |
|---|---|---|---|---|---|
| SL-3.1 | test | — | `docs/development/xfail-inventory.md` | inventory lists each xfail with a clearing owner; the phase-9 docstring baseline is recorded | `test -s docs/development/xfail-inventory.md` |
| SL-3.2 | impl | SL-3.1 | `.github/workflows/*.yml` | — | — |
| SL-3.3 | impl | SL-3.2 | `scripts/run_ci_smoke.py`, `scripts/run_platform_core.py` | — | — |
| SL-3.4 | verify | SL-3.3 | CI config | workflows parse + tier named | `python -c "import yaml,glob; [yaml.safe_load(open(f)) for f in glob.glob('.github/workflows/*.yml')]; print('workflows valid')"` |

### SL-4 — Documentation & spec reconciliation (SL-docs)
- **Scope**: Refresh the docs catalog, document the honest test-tier + gate policy, and append post-execution amendments to the GATES roadmap section if any freeze was empirically wrong.
- **Owned files**: `README.md`, `CONTRIBUTING.md`, `docs/development/RELEASE_CHECKLIST.md`, `.claude/docs-catalog.json`, `specs/phase-plans-v2.md`
- **Interfaces provided**: (none)
- **Interfaces consumed**: (none)
- **Parallel-safe**: no (terminal)
- **Depends on**: SL-1, SL-2, SL-3

**Tasks**:

| Task ID | Type | Depends on | Files in scope | Action |
|---|---|---|---|---|
| SL-4.1 | docs | — | `.claude/docs-catalog.json` | Rescan via `scaffold_docs_catalog.py --rescan` (record "helper unavailable" if absent). |
| SL-4.2 | docs | SL-4.1 | `CONTRIBUTING.md`, `README.md`, per catalog | Document the tiered-suite + ruff/mypy gate policy and how to run `automation.suite_command`; append `GATES` to `touched_by_phases`. |
| SL-4.3 | docs | SL-4.2 | `specs/phase-plans-v2.md` | Append `### Post-execution amendments` to the GATES section if any freeze was empirically wrong. |
| SL-4.4 | verify | SL-4.3 | — | Run repo doc linters if configured; else no-op. |

## Execution Notes
- **Single-writer files**: `pyproject.toml` is owned exclusively by **SL-2** (ruff ignore edits). SL-1 only READS `pyproject.toml` via `resolve_pack_pin()` — it must not write it. `.github/workflows/*` and the smoke scripts are owned exclusively by **SL-3** (mypy-blocking + tiering + hardening are all one lane to avoid workflow-file collisions). `specs/phase-plans-v2.md` is owned by SL-4 only.
- **Known destructive changes**: none — every lane is additive or an in-place edit (ruff ignore removal, mypy `::warning::` removal, pin-derivation). No file deletions.
- **Expected add/add conflicts**: none.
- **SL-0 re-exports**: n/a (no preamble lane).
- **Stale-base guidance** (verbatim): Lane teammates in isolated worktrees do not see sibling merges automatically. If a lane finds its base is stale, it MUST stop and report rather than committing — the orchestrator will re-spawn or rebase. Silent `git reset --hard` or `git checkout HEAD~N -- …` in a stale worktree produces commits that destroy peer-lane work on `--no-ff` merge.
- **Baseline-red handling**: the phase-9 docstring env artifact HYGIENE deferred is resolved here — SL-3 either fixes the env sensitivity or records it in the capped xfail inventory with a clearing owner; it must not be left as an untracked silent failure.

## Acceptance Criteria
- [ ] `resolve_pack_pin()` returns the `<0.10` bound parsed from `pyproject.toml`, and the conformance gate rejects a simulated `0.10.0`/`0.13.0` pack while accepting `0.9.0` — proven by `tests/test_pack_pin_drift.py`.
- [ ] `ruff check chunker cli api` passes with `F401`/`F403`/`F811`/`F821`/`F841`/`E722` no longer in the `ignore` list — proven by `uv run --with toml --all-extras ruff check chunker cli api` (exit 0) + `grep` showing those rules absent from ignore paired with the ruff run.
- [ ] mypy is blocking in CI (no `::warning::` downgrade in `ci.yml`/`test.yml`) — proven by `grep -L "::warning::mypy" .github/workflows/{ci,test}.yml` and the workflow YAML validating.
- [ ] CI runs a documented full/tiered suite naming every module incl. `tests/test_canon_vectors.py` + `spec_tests/`; all `.github/workflows/*.yml` parse and carry top-level `permissions:` — proven by the YAML-parse check in SL-3.4 + `grep permissions .github/workflows/*.yml`.
- [ ] The capped xfail inventory exists and records the phase-9 docstring baseline with a clearing owner — proven by `docs/development/xfail-inventory.md` being non-empty and naming it.

## Verification
```bash
uv run --with toml --all-extras python -m pytest tests/test_pack_pin_drift.py tests/boundary_ir_conformance.py -q
uv run --with toml --all-extras ruff check chunker cli api
grep -E '"F401"|"F821"|"E722"' pyproject.toml | grep -i ignore && echo "STILL IGNORED" || echo "F-rules enforced"
grep -q "::warning::mypy" .github/workflows/ci.yml .github/workflows/test.yml && echo "mypy still warning-only" || echo "mypy blocking"
python -c "import yaml,glob; [yaml.safe_load(open(f)) for f in glob.glob('.github/workflows/*.yml')]; print('workflows valid')"
test -s docs/development/xfail-inventory.md && echo "xfail inventory present"
```

## Spec Closeout Plan
- schema: `spec_delta_closeout.v1`
- decision: `canonical_spec_update`
- target surfaces: `tests/boundary_ir_conformance.py`, `.github/workflows/*.yml`, `pyproject.toml`
- evidence paths: `logs/gates-ci-run.txt`
- redaction posture: `metadata_only`
- downstream handling: `none`

## Execution Policy
- work-unit defaults: effort=medium, reason=CI+config surface with correctness implications
- SL-1: effort=high, reason=pin-derivation + drift semantics are subtly wrong-prone and load-bearing for determinism
- SL-2: effort=high, reason=un-ignoring F-rules may surface real undefined-name bugs that must be fixed not re-suppressed
- SL-4: effort=low, reason=docs sweep only

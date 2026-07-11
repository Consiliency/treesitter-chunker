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

GATES makes the signal real. Because un-ignoring the pyflakes correctness rules and making mypy
blocking surface violations that can live in ANY source file, and because resolving the deferred
phase-9 docstring baseline needs ownership of that test, the quality cleanup is an inherently
whole-tree, serial operation — it is one broad implementation lane (SL-1), not several parallel
narrow lanes that would contend for the same files. GATES also formally owns "full-suite honesty":
HYGIENE deferred the phase-9 docstring env artifact here (a determinism-sensitive test that fails on
unmodified base code in this worktree's env but passes in a fresh build), which SL-1 resolves either
by fixing the sensitivity or by a tracked `xfail` mapped to a clearing owner, so downstream phases
inherit a green baseline.

## Interface Freeze Gates
- [ ] IF-0-GATES-1 — `resolve_pack_pin() -> tuple[str, str]` (lower, upper) that parses the
  `tree-sitter-language-pack` version cap from `pyproject.toml` as the single source of truth; the
  conformance gate + regenerate script consume it, and a drift test asserts the gate rejects a
  `0.10`+ pack. Plus the capped, tracked xfail inventory (module → clearing phase/reason, including
  the phase-9 docstring baseline) and the documented push/PR-vs-nightly test-tier definition +
  `automation.suite_command`.

## Lane Index & Dependencies

SL-1 — Whole-tree quality-gate cleanup
  Depends on: (none)
  Blocks: SL-2
  Parallel-safe: no

SL-2 — Documentation & spec reconciliation (SL-docs)
  Depends on: SL-1
  Blocks: (none)
  Parallel-safe: no

## Lanes

### SL-1 — Whole-tree quality-gate cleanup
- **Scope**: Add `resolve_pack_pin()` + drift test and route the conformance gate/regenerate script through it; remove the pyflakes/bugbear correctness rules from ruff `ignore` and make the tree clean (fixing real violations rather than re-suppressing); make mypy blocking in CI; make CI run a documented full/tiered suite (push/PR + nightly) wiring `tests/test_canon_vectors.py` + `spec_tests/`; harden all workflows (top-level `permissions: contents: read`, SHA-pinned `uses:`, `workflow_dispatch` via `env:`); and resolve the phase-9 docstring baseline (fix or tracked `xfail`) with a capped xfail inventory.
- **Owned files**: `pyproject.toml`, `chunker/**`, `cli/**`, `api/**`, `tests/**`, `scripts/**`, `.github/workflows/**`, `docs/development/xfail-inventory.md`
- **Interfaces provided**: IF-0-GATES-1 (`resolve_pack_pin`, test-tier definition, `automation.suite_command`, xfail inventory)
- **Interfaces consumed**: (none)
- **Tasks**:

| Task ID | Type | Depends on | Files in scope | Tests owned | Test command |
|---|---|---|---|---|---|
| SL-1.1 | test | — | `tests/test_pack_pin_drift.py`, `docs/development/xfail-inventory.md` | `resolve_pack_pin()` returns the pyproject `<0.10` bound; conformance rejects a simulated `0.10.0`/`0.13.0` pack, accepts `0.9.0`; inventory names the phase-9 baseline + a clearing owner | `uv run --with toml --all-extras python -m pytest tests/test_pack_pin_drift.py -q` |
| SL-1.2 | impl | SL-1.1 | `chunker/_internal/pack_pin.py`, `tests/boundary_ir_conformance.py`, `scripts/regenerate_boundary_goldens.py` | — | — |
| SL-1.3 | impl | SL-1.2 | `pyproject.toml`, `chunker/**`, `cli/**`, `api/**` | — | — |
| SL-1.4 | impl | SL-1.3 | `.github/workflows/**`, `scripts/run_ci_smoke.py`, `scripts/run_platform_core.py`, `tests/integration/phase9/**` | — | — |
| SL-1.5 | verify | SL-1.4 | whole tree | pin drift + ruff + workflows | `uv run --with toml --all-extras python -m pytest tests/test_pack_pin_drift.py tests/boundary_ir_conformance.py -q && uv run --with toml --all-extras ruff check chunker cli api && python -c "import yaml,glob; [yaml.safe_load(open(f)) for f in glob.glob('.github/workflows/*.yml')]"` |

### SL-2 — Documentation & spec reconciliation (SL-docs)
- **Scope**: Refresh the docs catalog, document the honest tiered-suite + ruff/mypy gate policy, and append post-execution amendments to the GATES roadmap section if any freeze was empirically wrong.
- **Owned files**: `README.md`, `CONTRIBUTING.md`, `docs/development/RELEASE_CHECKLIST.md`, `.claude/docs-catalog.json`, `specs/phase-plans-v2.md`
- **Interfaces provided**: (none)
- **Interfaces consumed**: (none)
- **Parallel-safe**: no (terminal)
- **Depends on**: SL-1

**Tasks**:

| Task ID | Type | Depends on | Files in scope | Action |
|---|---|---|---|---|
| SL-2.1 | docs | — | `.claude/docs-catalog.json` | Rescan via `scaffold_docs_catalog.py --rescan` (record "helper unavailable" if absent). |
| SL-2.2 | docs | SL-2.1 | `CONTRIBUTING.md`, `README.md`, `docs/development/RELEASE_CHECKLIST.md` | Document the tiered-suite + ruff/mypy gate policy and how to run `automation.suite_command`; append `GATES` to `touched_by_phases`. |
| SL-2.3 | docs | SL-2.2 | `specs/phase-plans-v2.md` | Append `### Post-execution amendments` to the GATES section if any freeze was empirically wrong. |
| SL-2.4 | verify | SL-2.3 | — | Run repo doc linters if configured; else no-op. |

## Execution Notes
- **Single-writer files**: SL-1 owns the entire code/config/CI surface (`pyproject.toml`, `chunker/**`, `cli/**`, `api/**`, `tests/**`, `scripts/**`, `.github/workflows/**`, `docs/development/xfail-inventory.md`) as one serial lane, because ruff F-rule cleanup + mypy triage are cross-cutting and cannot be split into parallel lanes that all edit the same tree. SL-2 (docs) owns only `README.md`, `CONTRIBUTING.md`, `docs/development/RELEASE_CHECKLIST.md`, `.claude/docs-catalog.json`, `specs/phase-plans-v2.md` — disjoint from SL-1, and runs after it.
- **Why one broad lane**: this is a deliberate single-implementation-lane phase (not a smell) — the quality operation is whole-tree-serial; parallel narrow lanes would produce `overlapping_write_ownership`.
- **Known destructive changes**: none — every change is an in-place edit (ruff ignore removal, mypy `::warning::` removal, pin-derivation, `xfail` markers) or an additive file. No deletions.
- **Expected add/add conflicts**: none.
- **SL-0 re-exports**: n/a.
- **Stale-base guidance** (verbatim): Lane teammates in isolated worktrees do not see sibling merges automatically. If a lane finds its base is stale, it MUST stop and report rather than committing — the orchestrator will re-spawn or rebase. Silent `git reset --hard` or `git checkout HEAD~N -- …` in a stale worktree produces commits that destroy peer-lane work on `--no-ff` merge.
- **Baseline-red handling**: the phase-9 docstring env artifact HYGIENE deferred is resolved in SL-1.4 — fix the env sensitivity or add a tracked `@pytest.mark.xfail` recorded in `docs/development/xfail-inventory.md` with a clearing owner; never leave it as a silent untracked failure.

## Acceptance Criteria
- [ ] `resolve_pack_pin()` returns the `<0.10` bound parsed from `pyproject.toml`, and the conformance gate rejects a simulated `0.10.0`/`0.13.0` pack while accepting `0.9.0` — proven by `tests/test_pack_pin_drift.py`.
- [ ] `ruff check chunker cli api` passes with `F401`/`F403`/`F811`/`F821`/`F841`/`E722` no longer in the ruff `ignore` list — proven by `uv run --with toml --all-extras ruff check chunker cli api` (exit 0).
- [ ] mypy is blocking in CI (no `::warning::` downgrade in `ci.yml`/`test.yml`) — proven by `grep -q "::warning::mypy" .github/workflows/ci.yml .github/workflows/test.yml` returning no match and the YAML parsing.
- [ ] All `.github/workflows/*.yml` parse and carry a top-level `permissions:` block; CI names a full/tiered suite incl. `tests/test_canon_vectors.py` + `spec_tests/` — proven by the YAML-parse check + `grep permissions .github/workflows/*.yml`.
- [ ] The capped xfail inventory exists and records the phase-9 docstring baseline with a clearing owner — proven by `docs/development/xfail-inventory.md` being non-empty and naming it.

## Verification
```bash
uv run --with toml --all-extras python -m pytest tests/test_pack_pin_drift.py tests/boundary_ir_conformance.py -q
uv run --with toml --all-extras ruff check chunker cli api
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
- work-unit defaults: effort=high, reason=un-ignoring F-rules surfaces real undefined-name bugs that must be fixed not re-suppressed
- SL-2: effort=low, reason=docs sweep only

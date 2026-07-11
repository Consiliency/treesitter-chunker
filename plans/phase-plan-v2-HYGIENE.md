---
phase_loop_plan_version: 1
phase: HYGIENE
roadmap: specs/phase-plans-v2.md
roadmap_sha256: 4f31561d0d33504f8a3c2f88316b4c6e9d55af2cfe3e5a627ef0f3de75a010d1
---

# HYGIENE: Surface Reduction & Dead-Code Removal

## Context

HYGIENE removes dead phase-scaffolding before later remediation targets the surviving package.
The canonical `.phase-loop/` ledger records one failed execution against the earlier draft: the
deletion lanes did not own 21 legacy tests that directly import the deleted packages, and generated
`treesitter_chunker.egg-info/` output was outside the owned-file contract. This plan incorporates
that evidence so the full local suite can remain the acceptance gate instead of failing after the
deletions.

The preamble must sever all three known live import edges before deletion: `chunker/__init__.py` to
`integration`, `chunker/grammar_management/cli.py` to `error_handling`, and
`chunker/contracts/__init__.py` to `cicd`. Static imports, dynamic `importlib` calls, and the legacy
tests are inventoried in `logs/hygiene-reachability-audit.txt`. A surviving production reference
from `chunker/`, `cli/`, or `api/` blocks deletion of that package and narrows the affected lane to
quarantine; it does not permit widening ownership silently.

The 21 legacy test files are retired with the package that is their sole subject. GATES still owns
the downstream test-tier inventory and records that disposition, but it does not need to edit paths
already deleted by HYGIENE. Documentation is verified read-only in the terminal lane because the
removed phase scaffolding is not part of the supported public surface; any contrary documentation
finding blocks closeout and requires an explicit plan repair.

## Interface Freeze Gates

- [ ] IF-0-HYGIENE-1 — `logs/hygiene-reachability-audit.txt` records the static and dynamic
  reachability inventory, the retained/quarantined/deleted disposition for every candidate
  subpackage, and the final `chunker/__init__.py` exports; the terminal verifier proves the final
  public surface imports and the full local suite passes.

## Lane Index & Dependencies

SL-1 — Reachability audit and import-edge severing
  Depends on: (none)
  Blocks: SL-2, SL-3, SL-4, SL-7
  Parallel-safe: no

SL-2 — Remove extractors and testing scaffolding
  Depends on: SL-1
  Blocks: SL-7
  Parallel-safe: yes

SL-3 — Remove integration and error-handling scaffolding
  Depends on: SL-1
  Blocks: SL-7
  Parallel-safe: yes

SL-4 — Remove deployment, development, distribution, CI/CD, and monitoring scaffolding
  Depends on: SL-1
  Blocks: SL-7
  Parallel-safe: yes

SL-5 — Deduplicate PluginConfig and prune unused exceptions
  Depends on: (none)
  Blocks: SL-7
  Parallel-safe: yes

SL-6 — Remove root cruft and generated package metadata
  Depends on: (none)
  Blocks: SL-7
  Parallel-safe: yes

SL-7 — Phase verification, documentation sweep, and interface-freeze reducer
  Depends on: SL-1, SL-2, SL-3, SL-4, SL-5, SL-6
  Blocks: (none)
  Parallel-safe: no

## Lanes

### SL-1 — Reachability audit and import-edge severing

- **Scope**: Freeze the reachability inventory, add one contract test, and sever the three known production import edges before any deletion lane starts.
- **Owned files**: `chunker/__init__.py`, `chunker/contracts/__init__.py`, `chunker/grammar_management/cli.py`, `tests/test_hygiene_reachability.py`, `logs/hygiene-reachability-audit.txt`
- **Interfaces provided**: `HYGIENE_REACHABILITY_V1` inventory and severed-import baseline
- **Interfaces consumed**: package import graph (pre-existing)
- **Parallel-safe**: no
- **Tasks**:
  - test: Add `tests/test_hygiene_reachability.py` to assert the three false-reachability edges are absent, retained internal error handling still imports, and every audited candidate has a disposition.
  - impl: Record static and dynamic reachability in the audit, remove the optional integration export block, remove the grammar CLI error-handling integration, and remove CI/CD imports/exports from the contracts package initializer.
  - verify: `uv run --with toml --all-extras python -m pytest tests/test_hygiene_reachability.py -q` and `uv run --with toml --all-extras python -c "import chunker; import chunker.contracts"`.

### SL-2 — Remove extractors and testing scaffolding

- **Scope**: Delete `extractors/` and `testing/` after the preamble proves no production importer remains, and retire their seven legacy tests.
- **Owned files**: `chunker/extractors/**`, `chunker/testing/**`, `tests/test_extraction_framework.py`, `tests/unit/extractors/**`
- **Interfaces provided**: extractors/testing deletion or audit-recorded quarantine disposition
- **Interfaces consumed**: `HYGIENE_REACHABILITY_V1`
- **Parallel-safe**: yes
- **Tasks**:
  - test: Run the upstream reachability contract filtered to `extractors` and `testing`; fail closed on any production reference.
  - impl: Delete the two dead subpackages and the legacy tests whose sole subject is those packages, or record quarantine without touching undeclared files if the audit blocks deletion.
  - verify: `uv run --with toml --all-extras python -m pytest tests/test_hygiene_reachability.py -k "extractors or testing" -q`.

### SL-3 — Remove integration and error-handling scaffolding

- **Scope**: Delete `integration/` and the top-level `error_handling/` after SL-1 severs their live edges, retaining `_internal/error_handling.py`, and retire three legacy tests.
- **Owned files**: `chunker/integration/**`, `chunker/error_handling/**`, `tests/test_core_integration.py`, `tests/test_phase3_integration.py`, `tests/test_security.py`
- **Interfaces provided**: integration/error-handling deletion or audit-recorded quarantine disposition
- **Interfaces consumed**: `HYGIENE_REACHABILITY_V1`
- **Parallel-safe**: yes
- **Tasks**:
  - test: Run the upstream reachability contract filtered to `integration` and `error_handling`, including a positive import assertion for `chunker._internal.error_handling`.
  - impl: Delete the two dead subpackages and the three legacy tests whose sole subject is those packages, or record quarantine if a production reference survives.
  - verify: `uv run --with toml --all-extras python -m pytest tests/test_hygiene_reachability.py -k "integration or error_handling" -q`.

### SL-4 — Remove deployment, development, distribution, CI/CD, and monitoring scaffolding

- **Scope**: Delete the five audited scaffolding subpackages after the contracts edge is severed and retire their eleven legacy tests.
- **Owned files**: `chunker/deployment/**`, `chunker/devenv/**`, `chunker/distribution/**`, `chunker/cicd/**`, `chunker/monitoring/**`, `tests/test_cicd_pipeline.py`, `tests/test_workflow_validator.py`, `tests/test_devenv_integration.py`, `tests/unit/test_devenv.py`, `tests/test_distribution_impl.py`, `tests/unit/distribution/**`, `tests/test_observability_system.py`
- **Interfaces provided**: deployment/devenv/distribution/cicd/monitoring deletion or audit-recorded quarantine disposition
- **Interfaces consumed**: `HYGIENE_REACHABILITY_V1`
- **Parallel-safe**: yes
- **Tasks**:
  - test: Run the upstream reachability contract filtered to the five candidate packages and assert `chunker.contracts` still imports after CI/CD exports are removed.
  - impl: Delete the five dead subpackages and their eleven legacy tests, or record quarantine for any package with a surviving production reference.
  - verify: `uv run --with toml --all-extras python -m pytest tests/test_hygiene_reachability.py -k "deployment or devenv or distribution or cicd or monitoring" -q`.

### SL-5 — Deduplicate PluginConfig and prune unused exceptions

- **Scope**: Make `languages.base.PluginConfig` the single class identity and remove only the six exception classes proven never raised or caught by the audit.
- **Owned files**: `chunker/languages/base.py`, `chunker/languages/plugin_base.py`, `chunker/exceptions.py`, `tests/test_pluginconfig_single.py`, `tests/test_exceptions.py`, `tests/test_cross_module_errors.py`
- **Interfaces provided**: one `PluginConfig` identity shared by base and plugin APIs
- **Interfaces consumed**: language plugin API (pre-existing)
- **Parallel-safe**: yes
- **Tasks**:
  - test: Add `tests/test_pluginconfig_single.py` to assert both import paths expose the same class and the six audited exception symbols are absent.
  - impl: Import `PluginConfig` from `languages.base` in `plugin_base.py`; delete only the audit-confirmed unused exception definitions; and update the two surviving tests that reference them (`tests/test_exceptions.py` drops `LanguageLoadError`/`LibrarySymbolError` cases; `tests/test_cross_module_errors.py` drops the `CacheError` case) so the full suite stays green.
  - verify: `uv run --with toml --all-extras python -m pytest tests/test_pluginconfig_single.py tests/test_exceptions.py tests/test_cross_module_errors.py -q`.

### SL-6 — Remove root cruft and generated package metadata

- **Scope**: Delete or untrack the roadmap-named root cruft and generated metadata, then add durable ignore rules without touching unrelated untracked files.
- **Owned files**: `.gitignore`, `test_api.py`, `test_symbol_extraction.py`, `test_csharp.cs`, `test_tsx.tsx`, `test_wasm.wat`, `tmp_test.Rmd`, `compatibility.db`, `troubleshooting.db`, `validation_report.json`, `setup.py.bak`, `CODE_REVIEW_REPORT.md`, `mcp_server.log`, `ide/**/node_modules/**`, `treesitter_chunker.egg-info/**`, `tests/test_repo_hygiene.py`
- **Interfaces provided**: repository hygiene contract and ignore rules
- **Interfaces consumed**: roadmap root-cruft inventory (pre-existing)
- **Parallel-safe**: yes
- **Tasks**:
  - test: Add `tests/test_repo_hygiene.py` to assert the named paths, `ide/**/node_modules/**`, and `treesitter_chunker.egg-info/**` are not tracked and the generated patterns are ignored.
  - impl: Remove the named cruft and generated metadata from tracking, then update `.gitignore` for `*.db`, `mcp_server.log`, `ide/**/node_modules/`, and `treesitter_chunker.egg-info/`.
  - verify: `uv run --with toml --all-extras python -m pytest tests/test_repo_hygiene.py -q`.

### SL-7 — Phase verification, documentation sweep, and interface-freeze reducer

- **Scope**: Verify all producer outputs together, confirm documentation impact, and publish IF-0-HYGIENE-1 without writing synthesized repo files.
- **Owned files**: none
- **Interfaces provided**: IF-0-HYGIENE-1
- **Interfaces consumed**: `HYGIENE_REACHABILITY_V1`, all lane dispositions, repository hygiene contract, single-`PluginConfig` contract
- **Parallel-safe**: no
- **Tasks**:
  - test: Run all three HYGIENE contract tests together and confirm every deletion/quarantine disposition in the audit matches the final tree.
  - impl: Reduce the lane results into the final surviving public-surface decision; if supported-user documentation references a removed symbol or package, stop with a repairable docs-freshness blocker instead of editing undeclared files.
  - verify: Run the effective suite command, import smoke, lint/format checks, and the tracked-cruft assertion from `## Verification`; list IF-0-HYGIENE-1 in closeout only after all required checks pass.

## Execution Notes

- `chunker/__init__.py`, `chunker/contracts/__init__.py`, and `chunker/grammar_management/cli.py` are single-writer preamble files owned only by SL-1.
- The deletion lanes depend on SL-1 and consume its committed audit/test interface; they must stop on a stale pre-SL-1 worktree instead of attempting an undeclared rebase or reset.
- The 21 legacy tests are partitioned exactly once: seven in SL-2, three in SL-3, and eleven in SL-4. `tests/test_hygiene_reachability.py` is written only by SL-1 and consumed read-only downstream.
- `test_tsx.tsx` and `ide/**/node_modules/**` are deletion-only hygiene paths, not UI implementation surfaces, so no browser verification is applicable.
- **No doc change**: the removed phase scaffolding is not part of the supported public surface; SL-7 verifies that assumption and blocks for plan repair if it is false.
- SL-7 is read-only. It may block for documentation freshness, verification failure, or evidence drift, but it may not widen ownership or edit docs/specs during reduction.

## Verification

- `automation.suite_command`: `uv run --with toml --all-extras python -m pytest tests -q`

```bash
uv run --with toml --all-extras python -m pytest tests/test_hygiene_reachability.py tests/test_pluginconfig_single.py tests/test_repo_hygiene.py -q
uv run --with toml --all-extras python -c "import chunker; import chunker.contracts; import chunker._internal.error_handling"
uv run --with toml --all-extras python -m pytest tests -q
uv run --all-extras ruff check chunker/ cli/ tests/ --exclude archive --exclude logs --exclude site
uv run --all-extras black --check chunker/ cli/ tests/ scripts/
test -z "$(git ls-files 'treesitter_chunker.egg-info/**' 'ide/**/node_modules/**' test_api.py test_symbol_extraction.py test_csharp.cs test_tsx.tsx test_wasm.wat tmp_test.Rmd compatibility.db troubleshooting.db validation_report.json setup.py.bak CODE_REVIEW_REPORT.md mcp_server.log)"
```

## Acceptance Criteria

- [ ] `logs/hygiene-reachability-audit.txt` records static imports, dynamic imports, legacy-test disposition, and retained/quarantined/deleted status for every candidate package, as asserted by `tests/test_hygiene_reachability.py`.
- [ ] The three known false-reachability edges are absent, while `chunker`, `chunker.contracts`, and `chunker._internal.error_handling` import successfully.
- [ ] `uv run --with toml --all-extras python -m pytest tests/test_hygiene_reachability.py -q` proves every package cleared for deletion and its legacy tests are absent; any package not cleared is explicitly quarantined in the audit.
- [ ] `languages.base.PluginConfig is languages.plugin_base.PluginConfig`, and only the six audit-confirmed unused exception classes are removed.
- [ ] No roadmap-named cruft, generated egg-info, or IDE `node_modules` path remains tracked, and durable ignore rules cover regenerated artifacts.
- [ ] The targeted HYGIENE contracts, full local pytest suite, ruff check, and black check all pass.
- [ ] SL-7 lists IF-0-HYGIENE-1 in closeout only after `automation.suite_command` passes and `logs/hygiene-reachability-audit.txt` matches the final tree.

## Spec Closeout Plan

- schema: `spec_delta_closeout.v1`
- decision: `no_spec_delta`
- target surfaces: `(none)`
- evidence paths: `logs/hygiene-reachability-audit.txt`
- redaction posture: `metadata_only`
- downstream handling: `none`

## Execution Policy

- work-unit defaults: work-unit=`lane_execute`, unsupported=`inherit_default`, inherit-default=`true`
- SL-7: work-unit=`phase_verify`, unsupported=`inherit_default`, inherit-default=`true`, policy-source=`phase plan`

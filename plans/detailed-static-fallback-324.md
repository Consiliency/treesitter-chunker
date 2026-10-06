---
automation:
  suite_command: "uv run --locked --all-extras pytest tests/test_public_grammar_cli.py tests/test_release_hygiene_policy.py -q"
---

# Detailed plan: Static public fallback cleanup

## Task

Repair treesitter-chunker#324 and its separately filed coupled import boundary,
treesitter-chunker#369, in one independently reviewable PR. This implements only
the static portion of EC-CLEANUP-1 in roadmap v3. It produces no concurrent-safety
or IF-0-CLEANUP-1 claim. Published 5.2.0 remains usable.

## Research summary

ComprehensiveGrammarCLI._cleanup_cache_fallback deletes directories using only
their parent mtime. Its existing stale-directory fixture contains a fresh parsed
Python source but incorrectly expects deletion. The package initializer then
unconditionally imports core despite the CLI's existing optional-core handling,
so toggling an availability flag after import misses the real fallback boundary.
Core's descendant scan and config's walkers cannot establish the required
fallback contract: config follows regular-file links, and core is unavailable
in one of the target cases. Keep this change in the existing CLI method.

## Changes and owned paths

### chunker/grammar_management/cli.py (modify)

- _cleanup_cache_fallback: freeze one age cutoff. lstat the cache root and each
  managed namespace before traversal; reject linked/reparse or non-directory
  namespaces with existing errors. Inspect every entry/descendant without
  following links, using an explicit no-follow walk with Windows reparse checks.
- An entry is eligible only if its own and every descendant's mtime is strictly
  older than the cutoff. Preserve exact-cutoff/fresh descendants and mixed-age
  directories. Entirely expired regular files/directories remain removable.
- Conservatively preserve/report linked payload entries in this static slice;
  no target bytes are counted. The later complete protocol owns safe leaf-link
  removal. Do not promise constructor path redirection safety here: that raw
  configured-root boundary is explicitly part of treesitter-chunker#323.
- Scan errors preserve the entry. Add bytes/top-level-entry counts only after
  successful unlink/rmtree. Preserve namespace roots and existing result keys.
  Supported-platform rmtree follows only a completed static no-follow scan;
  simultaneous writer safety remains unresolved in treesitter-chunker#323.

### chunker/grammar_management/__init__.py (modify)

- Reuse the CLI's actual core availability result. Re-export the existing core
  classes only when core imported successfully. Keep normal exports identical;
  keep grammar_cli, ComprehensiveGrammarCLI, ProgressIndicator and the existing
  GrammarStatus handling available in degraded mode. Do not export CLI stubs as
  real core types or invent replacements.

### tests/test_public_grammar_cli.py (modify)

- Correct the existing mixed-age fixture expectation. Add an entirely expired
  nested directory counterpart, exact-cutoff, empty-root and truthful-counter
  cases. Parse real repository Python fixtures before and after preservation.
- Exercise cold public import in a real isolated subprocess denying only core
  import. Set HOME/USERPROFILE/XDG before imports and use a supplied cache root;
  invoke the exported public CLI, verify normal/degraded export contracts and
  parse surviving bytes with the real parser in the owning process.
- Separately force actual GrammarManager construction failure by seeding a
  regular file at its builds namespace (CLI's grammars/build is distinct).
  Confirm grammar_manager is None and real fallback still preserves fresh
  downloads. Do not replace the manager or cleanup method with mocks.
- Test linked namespaces, linked payloads and real Windows junctions against
  outside sentinels; skip privileges only as explicit unresolved evidence, never
  platform acceptance. Filesystem fault injection may deny unlink/rmtree but
  must call the real cleanup under test and assert zero false reclamation.

### docs/grammar_management.md and CHANGELOG.md (modify)

- Describe static mixed-age preservation, degraded public import, linked-entry
  diagnostics and counting units. State the remaining concurrent/publication
  boundary without claiming the future protocol or native admission.

This plan and its supported plans/manifest.json entry are control artifacts.
No other product/test path is owned. Amend ownership before any expansion.

## Dependencies and order

1. Reproduce both defects with real fixtures, then implement/tests together.
2. Kill fallback_parent_age_only at the CLI eligibility condition,
   follow_cache_link at its no-follow lstat/link rejection, and
   unconditional_core_import at the package initializer. Require each new test
   to fail under its named mutation, restore and rerun before proceeding.
3. Run local checks, publish a draft via the supported FABPUB adapter, then panel
   exact code using manual tool-enabled Opus 5.5 TUI, Gemini 3.8 Flash, Astra and
   Sol. Three substantive rounds; no unresolved blocker can be waived.
4. Require changed-head Linux/macOS/Windows checks, merge, comment/close accepted
   treesitter-chunker#324 and treesitter-chunker#369, and prune the clean worktree.
   No dependency on the concurrency or auxiliary implementation is claimed.

## Verification

- uv sync --locked --all-extras
- uv run --locked --all-extras pytest tests/test_public_grammar_cli.py -q
- uv run --locked --all-extras pytest tests/test_core_grammar_cache_cleanup.py tests/test_public_grammar_config.py tests/test_release_hygiene_policy.py -q
- uv run --locked --all-extras ruff check chunker/ cli/ tests/ --exclude archive --exclude logs --exclude site
- uv run --locked --all-extras black --check chunker/ cli/ tests/ scripts/
- uv run --locked --all-extras python scripts/mypy_gate.py
- uv run --locked --with toml --all-extras python scripts/run_ci_smoke.py
- uv run --locked --all-extras --with mkdocs --with mkdocs-material --with mkdocstrings-python mkdocs build --strict --site-dir "$(mktemp -d)"

Run CONTRIBUTING's standing Windows main preflight before pushing. Hosted
changed-head platform evidence remains separate. Store local command/mutation
metadata in a private operational artifact and point the PR to its exact head;
no old admitted ledger/checkpoint, consumer lock, pin or golden is changed.

## Acceptance criteria

- [ ] Static EC-CLEANUP-1 subset — proven by the public CLI suite: fresh and
  exact-cutoff descendants survive; wholly expired entries are removed with
  truthful counts; errors/links preserve outside bytes and managed roots.
- [ ] Public fallback is reachable when core truly cannot import; normal core
  exports are unchanged, unavailable core types are absent, and real constructor
  failure reaches the same static cleanup. Proven by cold subprocess/public CLI
  tests, with real parsing of the surviving fixture.
- [ ] The three named mutations fail at the intended behavior assertions and
  restored tests pass; required reviews and platforms accept the exact head.

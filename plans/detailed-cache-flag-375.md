---
automation:
  suite_command: "uv run --locked --all-extras pytest tests/test_core_grammar_cache_cleanup.py -q"
---

# Detailed plan: respect the removal cache option

## Task

Repair treesitter-chunker#375 as an independent CLEANUP behaviour slice.
`GrammarManager.remove_grammar(clean_cache=False)` must retain associated
downloads and build files while removing the installed library and metadata.
This does not establish writer/deleter coordination or IF-0-CLEANUP-1.

## Research summary

The manager forwards its cache flag positionally to the installer's existing
`clean_dependencies` argument. The installer always invokes `_cleanup_cache`.
The installer dependency operation currently logs its intent; this slice does
not implement dependency deletion. Existing cache tests already use explicit
roots and real Python fixtures. The provider-backed fixture in
tests/test_grammar_management.py supplies actual compiled Python bytes.

## Changes

### chunker/grammar_management/core.py (modify)

- Preserve the existing positional `clean_dependencies` argument; add a
  keyword-only `clean_cache=True` to `GrammarInstaller.remove_grammar`.
- Guard its existing `_cleanup_cache` call with that flag.
- Forward the manager flag by keyword so it cannot control dependency intent.

### tests/test_core_grammar_cache_cleanup.py (modify)

- Add parameterized real manager/installer/registry removal tests using explicit
  user/package/cache roots and genuine provider Python grammar bytes.
- Parse the checked-in service.py before removal and retained cache bytes after
  removal. Check installed-file and installation-metadata deletion for both
  cache choices, both download/build namespaces, and an unrelated-language
  sentinel. Use no manager, installer, registry or deletion mocks.
- Verify the legacy installer positional dependency flag still leaves the
  cache default enabled; verify its keyword-only cache flag retains both roots.

### docs/grammar_management.md and CHANGELOG.md (modify)

- Document the Python manager cache option and the preserved installer argument
  semantics, without promising dependency deletion or concurrent safety.

This plan and plans/manifest.json are control artifacts. No parser pin, Boundary
IR golden, consumer lock or protected train artifact is owned.

## Dependencies and order

1. Add the real fixtures and reproduce False deleting the cache.
2. Implement only the argument mapping and cache guard.
3. Kill `always_clean_removal_cache` by removing the guard; require the False
   cases to fail and restored tests to pass.
4. Verify, publish a draft through the supported adapter, obtain manual
   tool-enabled Opus 5.5 TUI, Gemini 3.8 Flash, Astra and Sol reviews (three
   substantive rounds maximum), reconcile, merge, comment/close
   treesitter-chunker#375 and prune the clean merged worktree.

## Verification

- uv sync --locked --all-extras
- uv run --locked --all-extras pytest tests/test_core_grammar_cache_cleanup.py tests/test_public_grammar_cli.py tests/test_public_grammar_config.py -q
- uv run --locked --all-extras ruff check chunker/ cli/ tests/ --exclude archive --exclude logs --exclude site
- uv run --locked --all-extras black --check chunker/ cli/ tests/ scripts/
- uv run --locked --all-extras python scripts/mypy_gate.py
- uv run --locked --with toml --all-extras python scripts/run_ci_smoke.py
- uv run --locked --with toml --all-extras python scripts/run_full_suite.py
- uv run --locked --all-extras --with mkdocs --with mkdocs-material --with mkdocstrings-python mkdocs build --strict --site-dir "$(mktemp -d)"

Standing Windows main preflight is supplemental; require changed-head hosted
Linux/macOS/Windows fixture checks. Bind reviews, mutations and command results
to actual source/test hashes. Operational records confer no transaction IF.

## Acceptance criteria

- [ ] The manager's False option preserves download/build fixture bytes and
  their real parse; True removes those entries and both options remove the
  installed library/metadata, leaving unrelated language bytes unchanged.
- [ ] Installer positional dependency compatibility remains intact while its
  keyword-only cache option has the stated behavior.
- [ ] The named mutation fails the False retention assertions; restored tests,
  required local gates, exact-head review and hosted platforms pass.

---
automation:
  suite_command: "uv run --locked --all-extras pytest tests/test_compatibility_database_reload.py tests/test_language_compatibility_records_contract.py -q"
---

# Detailed plan: Keep live compatibility upserts consistent with SQLite

## Task and research

Resolve treesitter-chunker#149 as an independently landable EC-COMPAT-1 subset.
chunker/languages/compatibility/database.py persists language and grammar records
with INSERT OR REPLACE, but the live CompatibilitySchema rejects duplicates.
The existing _read_schema reconstructs all persisted fields and SQLite id order;
the cold-open tests already specify that tied grammar selection preserves that
order. This is the language compatibility database, separate from the nullable
grammar-management history repair in treesitter-chunker#135.

## Changes

- Modify add_language_version and add_grammar_version in the existing database
  module. After executing the upsert, build a candidate schema with _read_schema
  on the same connection before committing. Publish that candidate only after
  commit succeeds. Read/decode or SQLite failures roll back without publishing
  speculative state. Use the existing reader instead of duplicating field or
  ordering reconstruction. Refresh includes rules, breaking changes and other
  languages. Database rows are authoritative; direct schema-only additions are
  not persisted database records. No public CompatibilitySchema duplicate-policy
  change, new schema, migration, helper or performance claim.
- Extend tests/test_compatibility_database_reload.py with actual private SQLite
  upsert cases. Parse the checked-in Python service fixture using the installed
  parser before observing compatibility. Replace language metadata and grammar
  path, features, constraints, breaking metadata and dates; live getters/schema
  and cold reopen must agree. Preserve other languages, compatibility rules and
  breaking changes. Replace an earlier tied grammar and require the live winner
  to follow persisted replacement/id order, matching reopen. Use real SQLite
  ABORT triggers for each upsert type to prove false return, unchanged live
  state and unchanged persisted state after failure. No production/parser/DB
  mocks. Schema-only duplicate semantics stay covered by existing tests.
- Named mutations: stale_language_upsert and stale_grammar_upsert restore the
  old schema.add_* publication for that method; each must fail the corresponding
  live/cold consistency contract. preserve_old_tie_order retains the replaced
  grammar in its former live position and must fail tied selection. Restore
  exact production bytes and pass the focused batch after every mutation.
- Update docs/grammar_management.md and CHANGELOG.md with successful database
  upserts becoming visible immediately and consistently after reopen. Own this
  plan and its typed plans/manifest.json row. No platform-runner edit is needed:
  the existing reload module is already selected by platform-core.

## Dependencies and order

Register the detailed plan before tests or source edits. Record baseline failing
tests, implement only the upsert repair, kill/restore all named mutations, and
run actual Windows focused and standing checks. Collect a complete manual
tool-enabled Opus/Gemini/Astra/Sol code round before changes, with at most three
substantive rounds. Serialize original full runners and integrate accepted main
before final checks/publication. File separately discovered defects rather than
fixing them silently. Publish through the supported adapter. External reviews
are supplementary code acceptance, not whole COMPAT/IF authority.

## Verification

- uv sync --locked --all-extras
- uv run --locked --all-extras pytest tests/test_compatibility_database_reload.py tests/test_language_compatibility_records_contract.py -q
- uv run --locked --all-extras ruff check chunker/ cli/ tests/ --exclude archive --exclude logs --exclude site
- uv run --locked --all-extras black --check chunker/ cli/ tests/ scripts/
- uv run --locked --all-extras python scripts/mypy_gate.py
- uv run --locked --with toml --all-extras python scripts/run_ci_smoke.py
- uv run --locked --with toml --all-extras python scripts/run_platform_core.py --platform linux
- uv run --locked --with toml --all-extras python scripts/run_full_suite.py

## Acceptance criteria

- [ ] EC-COMPAT-1 upsert subset: focused actual SQLite/parsed-fixture tests show
  successful language/grammar replacements, all fields and tied selection agree
  live and after reopen, with unrelated persisted records preserved.
- [ ] Real failed upserts leave live and persisted state unchanged; all three
  named mutations fail intended contracts and each exact restoration passes.
- [ ] Original six checks, locked refresh, full tests/spec_tests, matching-source
  Windows, exact hosted platforms and bounded review support this repair only;
  no coverage percentage, native admission or whole COMPAT/IF acceptance.

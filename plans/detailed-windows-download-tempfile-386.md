---
automation:
  suite_command: "uv run --locked --all-extras pytest tests/test_grammar_integrity.py -q"
---

# Detailed plan: Close the download staging handle before use

## Task

Resolve treesitter-chunker#386 without changing download trust, parser pins or
cache publication semantics. This independent repair is not CLEANUP acceptance.

## Research summary

GrammarDownloadManager.download_grammar creates a NamedTemporaryFile with
delete=False, then downloads, verifies, extracts and unlinks while its creation
handle remains open. Windows cannot reopen or remove that file. Existing tests
replace the download and extraction methods and do not exercise archive lifetime.

## Changes

- chunker/grammar/download.py: close the creation handle before the download
  try/finally. Retain checksum-before-extraction order and finally unlink after
  success, checksum rejection, transport error or extraction error.
- tests/test_grammar_integrity.py: add a real gzip tar fixture containing checked-in
  BAML grammar sources, with an in-memory HTTP response at the network boundary.
  Exercise the actual downloader, verifier and extractor. Observe the real staging
  handle is closed before transport opens, and the archive disappears on every
  tested outcome. Successful source bytes and metadata must match; failed downloads
  must not publish metadata. No production-method mocks establish these contracts.
- scripts/run_platform_core.py: select these portable download tests on Linux,
  macOS and Windows.
- CHANGELOG.md: record portable staging-file handling. This plan and its typed
  plans/manifest.json entry are owned control artifacts.

## Dependencies and order

Integrate current main before source edits. Add tests, repair the handle lifetime,
then run verification. Separately ticket discovered defects; do not fix checksum
policy or transaction debt here. Preserve all unrelated lifecycle records.

## Verification

- uv sync --locked --all-extras
- uv run --locked --all-extras pytest tests/test_grammar_integrity.py -q
- uv run --locked --all-extras ruff check chunker/ cli/ tests/ --exclude archive --exclude logs --exclude site
- uv run --locked --all-extras black --check chunker/ cli/ tests/ scripts/
- uv run --locked --all-extras python scripts/mypy_gate.py
- uv run --locked --with toml --all-extras python scripts/run_ci_smoke.py
- uv run --locked --all-extras pytest -q

Kill keep_download_creation_handle_open by restoring the old open-context
implementation; require the closed-handle contract to fail and restored focused
tests to pass. Run the standing Windows preflight and changed-source offline
download tests on Windows before publication. Require exact-head hosted platform
checks and a manual tool-enabled code review before merging. No percentage gate.

## Acceptance criteria

- [ ] Actual transport, checksum and extraction succeed with closed creation
  handle, correct source bytes, published metadata and no remaining archive.
- [ ] Checksum, transport and extraction failures remain observable, do not
  publish metadata, and remove the staging archive.
- [ ] The named mutation fails at the lifetime assertion; restored tests,
  original runner checks, changed-head platforms and code review pass.

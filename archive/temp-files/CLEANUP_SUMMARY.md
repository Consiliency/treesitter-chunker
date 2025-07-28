# Root Directory Cleanup Summary

Date: 2025-07-27

## Files Moved

### To examples/:
- demo_postgres_export.py
- example_parquet_usage.py
- example_repo_usage.py
- example_sliding_window_integration.py
- test_config_processor_demo.py
- test_integration_with_main_chunker.py
- test_overlapping_direct.py
- test_postgres_advanced.py
- test_token_integration_demo.py

### To scripts/:
- fix_language_conflicts.py
- fix_plugins.py
- setup_codex.sh

### To tests/:
- test_rust.rs
- test_ts.ts

### To packaging/homebrew/:
- treesitter-chunker.rb

### Archived here (temp-files/):
- dev.sh (empty file)
- test_ast.svg.svg (duplicate extension)
- click_batch.jsonl
- click_batch_results.jsonl
- click_clean.jsonl
- click_filtered.jsonl
- click_results.jsonl
- click_src.jsonl
- multi_lang_results.jsonl

## Test Repositories Preserved

The following directories contain test repositories used for language testing
as documented in docs/testing-methodology-complete.md and were left in place:

- TypeScript/ - Microsoft TypeScript compiler
- click/ - Python Click CLI framework
- flask/ - Python Flask web framework
- gin/ - Go Gin web framework
- googletest/ - Google C++ testing framework
- guava/ - Google Java libraries
- lodash/ - JavaScript utility library
- ruby/ - Ruby language source
- rust/ - Rust language source
- serde/ - Rust serialization framework

## No Breaking Changes

All moves were organizational only. The main project files remain unchanged:
- setup.py
- pyproject.toml
- MANIFEST.in
- LICENSE
- README.md
- CHANGELOG.md
- CLAUDE.md
- Dockerfile
- Dockerfile.alpine
- uv.lock
- requirements-build.txt
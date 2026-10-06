---
automation:
  suite_command: "uv run --locked --all-extras pytest tests/test_streaming.py::TestBufferOptimization -q"
---

# Detailed plan: Verify file hashes independently of timing

## Task and research summary

Resolve treesitter-chunker#342 as an independently landable EC-GATES-1 subset.
The existing streaming buffer test compares two individual hash durations with
a 1.1 ratio gate; unchanged coverage runs have both failed and passed. Actual
compute_file_hash used here lives in chunker/streaming.py; the separate internal
file-utils implementation is outside this repair. Its contract is SHA-256 of
every byte regardless of read size.
Existing parser fixtures and the installed parser provide real fixture evidence.

## Changes

- tests/test_streaming.py: replace only the hash timing test with parameterized
  SHA-256 correctness cases for default, one-byte, seven-byte, 8 KiB and 1 MiB
  reads, including empty input. Copy bytes from the checked-in Python service
  fixture, verify actual nonempty parsing of the fixture, and repeat its bytes
  sufficiently to cross the default read boundary. Compare each actual file hash
  to independent hashlib.sha256 of the entire input. Append a byte and require
  the new digest to match its independent oracle and differ from the old digest.
  Empty input must have the standard empty SHA-256 digest. No speed gate, parser
  mock, file mock or newly measured performance budget.
- Temporarily mutate the actual update loop in chunker/streaming.py
  as omit_final_partial_hash_chunk: skip updating the final short read. Cases
  with a partial final read must fail; one-byte reads correctly survive this
  particular mutation. Restore exact production bytes and pass focused
  tests. This module has no permanent change.
- scripts/run_platform_core.py: select the new hash contract cases on every
  hosted platform alongside the existing parsed streaming fixture case.
- CONTRIBUTING.md and CHANGELOG.md: record file-hash correctness checks against
  an independent SHA-256 oracle; wall-clock comparisons are not correctness
  acceptance. This plan and its typed plans/manifest.json row are owned paths.

## Documentation impact

Verification guidance only. No hashing algorithm, public parser/cache behavior,
new API, pin, native admission or consumer lock change.

## Dependencies and order

Register before tests/mutation. Preserve the prior coverage reproduction rather
than claiming the narrow passing Linux run reproduces that load-dependent flake.
Run the unchanged narrow case, new fixtures and mutation. Serialize original
full runners; require six checks, locked refresh, documented tests/spec_tests,
actual Windows focused/standing checks and exact hosted platforms. Manual
tool-enabled four-seat review has at most three substantive rounds, collect a
complete round before changes. External records are supplementary without IF
claims. Publish through the supported adapter.

## Verification

- uv sync --locked --all-extras
- uv run --locked --all-extras pytest tests/test_streaming.py::TestBufferOptimization -q
- uv run --locked --all-extras ruff check chunker/ cli/ tests/ --exclude archive --exclude logs --exclude site
- uv run --locked --all-extras black --check chunker/ cli/ tests/ scripts/
- uv run --locked --all-extras python scripts/mypy_gate.py
- uv run --locked --with toml --all-extras python scripts/run_ci_smoke.py
- uv run --locked --with toml --all-extras python scripts/run_platform_core.py --platform linux
- uv run --locked --with toml --all-extras python scripts/run_full_suite.py

## Acceptance criteria

- [ ] EC-GATES-1 hash subset: actual byte-complete SHA-256 matches its independent
  oracle for every declared read size, empty input and changed input; proven by
  the focused batch without whole GATES acceptance.
- [ ] omit_final_partial_hash_chunk fails real nonempty fixtures; exact restored
  production passes all focused cases. No wall-clock ratio correctness gate.
- [ ] Original verification, current-source Windows and exact hosted platforms,
  bounded reviews and accurate documentation support the independent repair.

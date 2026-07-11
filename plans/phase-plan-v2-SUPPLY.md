---
phase_loop_plan_version: 1
phase: SUPPLY
roadmap: specs/phase-plans-v2.md
roadmap_sha256: 232276eb0d69bb61e822ed7f1062defb89331085b45a2fb716d92f7566fb7ab9
---

# SUPPLY: Supply-Chain & Grammar-Install Hardening

## Context

The grammar-install chain reaches native code execution from untrusted input: every `git clone`
takes an unvalidated `repository_url`, and downloaded grammar source is compiled with `cc` and
loaded via `ctypes.CDLL` with no integrity check. Reconnaissance confirmed the clone/fetch/build/load
inventory:

- Clone sites with no URL validation: `grammar_management/core.py:694`, `grammar_management/cli.py`,
  `grammar/manager.py`, `grammar_manager.py`, and the live argparse-CLI path
  `_internal/user_grammar_tools.py` (via `UserGrammarTools`). `git checkout <version>` uses no `--`
  separator (option injection).
- The correct primitive already exists but unused: `grammar_manager.py:84-91` does `urlparse` +
  `"github.com" in netloc` — the latter substring check is itself weak (accepts `github.com.evil.example`)
  and must be tightened to an exact-host allowlist.
- `grammar/download.py:89-372`: fetch → `cc` → `CDLL` with default `version="master"`, no checksum.
- `build/builder.py:627`: `tarfile.extractall()` with no `filter=`.
- `plugin_manager.py:386-409`: `exec_module()` on any file in a watched dir.

This phase routes every clone through one validator, verifies artifact provenance before compile/load,
and hardens the tar/plugin paths. It is a co-root (no HYGIENE dependency; files disjoint from deletions).

## Interface Freeze Gates
- [ ] IF-0-SUPPLY-1 — `validate_grammar_source(url, *, allow_hosts) -> str` (raises on disallowed
  scheme/host, `ext::`/`file::`, leading-`-`; exact-host allowlist, not substring) AND
  `verify_artifact(path, provenance) -> None` (checks a repo-owned checksum manifest before compile/load).

## Lane Index & Dependencies

SL-1 — URL validator + route all clone paths
  Depends on: (none)
  Blocks: SL-docs
  Parallel-safe: yes

SL-2 — Download provenance + verify_artifact before compile/load
  Depends on: (none)
  Blocks: SL-docs
  Parallel-safe: yes

SL-3 — Tarfile filter + plugin trust
  Depends on: (none)
  Blocks: SL-docs
  Parallel-safe: yes

SL-4 — Documentation & spec reconciliation (SL-docs)
  Depends on: SL-1, SL-2, SL-3
  Blocks: (none)
  Parallel-safe: no

## Lanes

### SL-1 — URL validator + route all clone paths
- **Scope**: Add one `validate_grammar_source()` (exact-host allowlist, reject `ext::`/`file::`/leading-`-`) and route every inventoried `git clone`/`checkout` through it with a `--` separator.
- **Owned files**: `chunker/grammar/source_validation.py`, `chunker/grammar_management/core.py`, `chunker/grammar_management/cli.py`, `chunker/grammar/manager.py`, `chunker/grammar_manager.py`, `chunker/_internal/user_grammar_tools.py`, `tests/test_grammar_source_validation.py`
- **Interfaces provided**: IF-0-SUPPLY-1 (`validate_grammar_source`)
- **Interfaces consumed**: (none)
- **Tasks**:

| Task ID | Type | Depends on | Files in scope | Tests owned | Test command |
|---|---|---|---|---|---|
| SL-1.1 | test | — | `tests/test_grammar_source_validation.py` | rejects `ext::sh -c id`, `file::`, `-flag`, `github.com.evil.example`; accepts `https://github.com/tree-sitter/tree-sitter-python` | `python -m pytest tests/test_grammar_source_validation.py -q` |
| SL-1.2 | impl | SL-1.1 | `chunker/grammar/source_validation.py` | — | — |
| SL-1.3 | impl | SL-1.2 | `chunker/grammar_management/core.py`, `chunker/grammar_management/cli.py`, `chunker/grammar/manager.py`, `chunker/grammar_manager.py`, `chunker/_internal/user_grammar_tools.py` | — | — |
| SL-1.4 | verify | SL-1.3 | grammar clone paths | lane tests + grep no raw clone | `python -m pytest tests/test_grammar_source_validation.py -q` |

### SL-2 — Download provenance + verify_artifact before compile/load
- **Scope**: Resolve downloads to an immutable commit (no bare `master`) and check a repo-owned checksum manifest via `verify_artifact()` before `cc` compile / `CDLL` load.
- **Owned files**: `chunker/grammar/integrity.py`, `chunker/grammar/download.py`, `tests/test_grammar_integrity.py`
- **Interfaces provided**: IF-0-SUPPLY-1 (`verify_artifact`)
- **Interfaces consumed**: (none)
- **Tasks**:

| Task ID | Type | Depends on | Files in scope | Tests owned | Test command |
|---|---|---|---|---|---|
| SL-2.1 | test | — | `tests/test_grammar_integrity.py` | `verify_artifact` rejects checksum mismatch; download refuses bare `master` default | `python -m pytest tests/test_grammar_integrity.py -q` |
| SL-2.2 | impl | SL-2.1 | `chunker/grammar/integrity.py` | — | — |
| SL-2.3 | impl | SL-2.2 | `chunker/grammar/download.py` | — | — |
| SL-2.4 | verify | SL-2.3 | download path | lane tests | `python -m pytest tests/test_grammar_integrity.py -q` |

### SL-3 — Tarfile filter + plugin trust
- **Scope**: Use `filter="data"` + member validation in the conda-package extract, and document/guard the plugin-dir trust boundary.
- **Owned files**: `chunker/build/builder.py`, `chunker/plugin_manager.py`, `tests/test_tarfile_safe_extract.py`
- **Interfaces provided**: (none)
- **Interfaces consumed**: (none)
- **Tasks**:

| Task ID | Type | Depends on | Files in scope | Tests owned | Test command |
|---|---|---|---|---|---|
| SL-3.1 | test | — | `tests/test_tarfile_safe_extract.py` | crafted `../` member is blocked; plugin dir requires explicit trust | `python -m pytest tests/test_tarfile_safe_extract.py -q` |
| SL-3.2 | impl | SL-3.1 | `chunker/build/builder.py`, `chunker/plugin_manager.py` | — | — |
| SL-3.3 | verify | SL-3.2 | build/plugin paths | lane tests | `python -m pytest tests/test_tarfile_safe_extract.py -q` |

### SL-4 — Documentation & spec reconciliation (SL-docs)
- **Scope**: Refresh docs catalog, document the grammar-install trust model and plugin-dir privilege, and append post-execution amendments to the SUPPLY roadmap section if any freeze was wrong.
- **Owned files**: `README.md`, `SECURITY.md`, `docs/**`, `.claude/docs-catalog.json`, `specs/phase-plans-v2.md`
- **Interfaces provided**: (none)
- **Interfaces consumed**: (none)
- **Parallel-safe**: no (terminal)
- **Depends on**: SL-1, SL-2, SL-3

**Tasks**:

| Task ID | Type | Depends on | Files in scope | Action |
|---|---|---|---|---|
| SL-4.1 | docs | — | `.claude/docs-catalog.json` | Rescan via `scaffold_docs_catalog.py --rescan` (record "helper unavailable" if absent). |
| SL-4.2 | docs | SL-4.1 | `SECURITY.md`, per catalog | Document grammar-source validation + plugin trust boundary; append `SUPPLY` to `touched_by_phases`. |
| SL-4.3 | docs | SL-4.2 | `specs/phase-plans-v2.md` | Append `### Post-execution amendments` to the SUPPLY section if any freeze was empirically wrong. |
| SL-4.4 | verify | SL-4.3 | — | Run repo doc linters if configured; else no-op. |

## Execution Notes
- **Single-writer files**: none shared across lanes — SL-1 owns all clone sites + the new `source_validation.py`; SL-2 owns `download.py` + `integrity.py`; SL-3 owns `builder.py` + `plugin_manager.py`. Disjoint.
- **Known destructive changes**: none — every lane is additive (new modules, replaced call bodies, new tests). The unused sibling validator in `grammar_manager.py` is folded into `validate_grammar_source`, not deleted wholesale.
- **Expected add/add conflicts**: none.
- **SL-0 re-exports**: n/a (no preamble lane).
- **Stale-base guidance** (verbatim): Lane teammates in isolated worktrees do not see sibling merges automatically. If a lane finds its base is stale, it MUST stop and report rather than committing — the orchestrator will re-spawn or rebase. Silent `git reset --hard` or `git checkout HEAD~N -- …` in a stale worktree produces commits that destroy peer-lane work on `--no-ff` merge.

## Acceptance Criteria
- [ ] A malicious `repository_url` (`ext::sh -c id`, `file::/etc`, `-upload-pack=…`, `github.com.evil.example`) is rejected before any `git clone` — proven by `tests/test_grammar_source_validation.py`.
- [ ] A grammar artifact whose checksum does not match the repo-owned manifest is refused before `cc`/`CDLL` — proven by `tests/test_grammar_integrity.py`; no clone path defaults to bare `master`.
- [ ] A crafted conda tar with a `../` member cannot write outside the extract dir — proven by `tests/test_tarfile_safe_extract.py`.
- [ ] No `git clone`/`git checkout` call in the inventoried files bypasses `validate_grammar_source` — proven by SL-1.4 grep + lane tests.

## Verification
```bash
python -m pytest tests/test_grammar_source_validation.py tests/test_grammar_integrity.py tests/test_tarfile_safe_extract.py -q
grep -rn --include='*.py' -E "git.{0,4}clone" chunker | grep -v validate_grammar_source && echo "UNVALIDATED CLONE FOUND" || echo "all clones validated"
```

## Spec Closeout Plan
- schema: `spec_delta_closeout.v1`
- decision: `no_spec_delta`
- target surfaces: `(none)`
- evidence paths: `logs/supply-negative-tests.txt`
- redaction posture: `metadata_only`
- downstream handling: `none`

## Execution Policy
- work-unit defaults: effort=medium, reason=security-sensitive validation logic
- SL-1: effort=high, reason=URL/allowlist parsing is subtly wrong-prone and security-critical
- SL-4: effort=low, reason=docs sweep only

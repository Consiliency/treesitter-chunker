# Comprehensive Code Review — treesitter-chunker v3.2.2

**Date:** 2026-07-11 · **Commit:** `542896c0` (tag `v3.2.2`) · **Scope:** whole repository
(~144k LOC source in `chunker/`, ~82k LOC tests)

**Method.** Six parallel subsystem reviewers (core engine, boundary-IR/determinism,
repo-scale/concurrency, supply-chain security, interfaces, cross-cutting/hygiene), then a
four-vendor advisor board: **GPT-5.6** (red-team lens, via codex), **Grok 4.5** (adversarial
lens), **Gemini 3.1 Pro** (alternative-approach — *degraded, returned no usable output*), and a
native **Claude Fable 5** correctness leg. Load-bearing claims were spot-checked against the real
source; the one factual dispute between advisors (the `ext::` vector) was resolved by running git.

## Board verdicts

| Reviewer | Lens | Verdict | One-line |
|---|---|---|---|
| Claude Fable 5 (native) | correctness | **AGREE** | All 6 spot-checks confirmed; ruff = MAJOR not CRITICAL |
| Grok 4.5 | adversarial | **AGREE** | Every CRITICAL reproduced; only mild rhetorical overstatements |
| GPT-5.6 | red-team | **DISAGREE** | Not "clean core / weak edges" — blockers are *in the core too*; several false positives corrected |
| Gemini 3.1 Pro | alternative | DEGRADED | No output |

The DISAGREE is **harsher, not softer**: GPT-5.6 holds that "well-engineered core wrapped in weak
peripherals" is too generous because chunk-identity and concurrency defects sit in the core itself.
On the substance, all three functioning reviewers agree the codebase is not in a shippable state.

## The thesis (reconciled)

A genuinely well-engineered **boundary-IR / canon determinism subsystem** — fail-closed on the
Unicode DB pin, a thorough NFC/astral/float-rejection vector suite, documented BUG-N regression
tests, a real 12-language golden gate — is wrapped in:

1. an **unsound concurrency model** (one shared tree-sitter `Parser` dispensed unlocked to thread-pool workers),
2. a **content-hash chunk identity** that structurally breaks the incremental module and silently drops chunks,
3. a **demo-grade unauthenticated FastAPI** surface (arbitrary file read, SSRF, injection into a generated SQL artifact),
4. an **unvalidated grammar-install chain** whose real teeth are compile-and-load of unverified native code,
5. **hollow quality gates** (ruff correctness rules ignored, mypy warning-only, ~10% of tests run in CI, canon-fidelity proof not in CI, determinism pin-mirror already drifted), and
6. **~45–55k LOC of dead phase-scaffolding** shipped in the wheel.

---

## CRITICAL (fix before any release / exposure)

**C1 · Shared tree-sitter Parser across threads → UB / segfault.**
`chunker/_internal/factory.py:239-253` `get_parser()` returns the same LRU-cached `Parser` to
every caller with no checkout/lock; on a pool hit it *also* `cache.put`s that instance, so one
object lives in cache and pool at once and `return_parser` re-adds it while the cache still holds
it. `chunker/repo/processor.py:286` drives this from a `ThreadPoolExecutor`; N workers call
`parser.parse()` (which releases the GIL for the C parse) on one non-reentrant parser.
*Independently confirmed by three reviewers + a two-call identity probe.* The "parser pools" in
`performance/optimization/batch.py` and `memory_pool.py` pool N references to the same object, so
they provide no isolation. **Fix:** per-thread/thread-local parser acquisition, or a real
checkout with the parser removed from the cache while in use.

**C2 · `chunk_id` collisions silently drop chunks.**
`chunker/types.py:41-50` — `compute_node_id = sha1(f"{path}|{lang}|{route}|{text_hash16}")` where
`route` (`core.py:656`) is **node types only** (`[*parent_route, adjusted_node_type]`); definition
*names* live in a separate `qualified_route` that feeds `definition_id`, **not** `chunk_id`. Two
byte-identical trivial definitions under same-typed ancestors (e.g. `def __init__(self): pass` in
two classes) collide to one ID and get collapsed in `tmp_to_final` and every `{chunk_id: chunk}`
map (incremental, graph, export). **Bounded likelihood** (needs byte-identical siblings) but
real. **Fix:** key maps on the already-built `definition_id` / include `qualified_route` + position.

**C3 · Mixed-language processing has never worked.**
`chunker/multi_language.py:942-946` calls `chunk_file(file_path=..., content=..., language=...)`;
`core.chunk_file(path, language, ...)` accepts none of those kwargs (`# type: ignore[call-arg]`
even flags it) → `TypeError` on every HTML/MD/JSX/notebook mixed file, uncaught by the surrounding
narrow `except`.

**C4 · VFS large-file streaming is doubly broken.**
`chunker/vfs_chunker.py:97-121` — `self.vfs.Path()` exists only on Local/InMemory backends
(`AttributeError` on Zip/HTTP), and the buffer parses truncated 2 MB prefixes while retaining the
last 1 MB → duplicate chunks, mid-function splits, and file-relative offsets that are wrong after
the first flush. Files > 10 MB auto-route here.

**C5 · Unauthenticated FastAPI = arbitrary file read + SSRF.**
`api/server.py:247-262,376-395` — `/chunk/file` and `/graph/xref` accept arbitrary absolute paths
and return file contents as chunk `content`, with the entrypoint binding `0.0.0.0:8000`
(`:435`). `/export/postgres` (`:365-373`) takes attacker-controlled `repo_root` (arbitrary tree
read + output-file placement) and `config.dsn` (connect to an arbitrary Postgres host — SSRF/pivot).
*Advisor refinements:* the live DSN INSERT path uses **parameterized statements** (so the SQLi is
confined to the *generated* `chunker_export.sql` file, where `postgres_spec_exporter.py` f-string-
builds INSERTs escaping only `attrs_json`); and an `.ssh/id_rsa` example returns no chunks (non-code
emits nothing) — but any readable **source** file is fully exfiltrable. CORS `allow_origins=["*"]`
+ `allow_credentials=True` (`:37-43`) amplifies this to drive-by: Starlette reflects the Origin for
credentialed requests, so any page a developer visits can POST to `localhost:8000` and read local
source. **Fix:** auth + path allow-listing/root confinement, drop the wildcard-credentialed CORS,
size caps; treat this server as unshippable until then.

**C6 · Determinism pin-mirror has already drifted (gate is false-green).**
`tests/boundary_ir_conformance.py:58` pins the language pack to `("0.9","1.0")` — accepting
**0.10–0.13** — while `pyproject.toml:47` caps it at `<0.10` and calls that bound "load-bearing"
(the pack 0.13 cobol grammar C-level infinite-loops; a newer Python grammar drops docstrings and
byte-diverges the IR). The mirror is hand-maintained (`packaging.Version` is used correctly, so
this is a value drift, not a parse bug); `scripts/regenerate_boundary_goldens.py` inherits the same
too-wide assert, so goldens can be baked on a drifted pack. **This is the exact #84/#86 incident
the gate exists to catch, sailing through green.** **Fix:** parse the bound out of `pyproject.toml`
instead of hand-mirroring it.

**C7 · Quality gates are hollow.**
- `pyproject.toml` `select` advertises pyflakes `F` etc., then `ignore` removes `F401`, `F403`,
  `F811`, **`F821` (undefined name)**, `F841`, `E722`, `BLE001`, `B904` — an undefined-name typo
  ships. *(Verified: all six present in the ignore list.)*
- CI (`run_ci_smoke.py` 15 files + `run_platform_core.py` ~11) executes ~26 of ~230 test modules —
  **~90% of the suite never runs on push/PR**, including `tests/test_canon_vectors.py`, the canon
  serializer's *only* stated fidelity proof, and all of `spec_tests/`.
- mypy failures are downgraded to `::warning` while `pyproject.toml` declares `strict = true`.

> **Severity note (advisor consensus):** C7 is real but is a *quality-gate* critical, not a runtime
> one — the native Claude and Grok legs would rate the ruff item MAJOR. It stays in this section
> because it is what lets every other class of defect ship unseen.

---

## MAJOR

**Core engine.** Fallback almost never fires (`auto.py:227,379` catch `(OSError,FileNotFoundError,
IndexError)`/`(IndexError,KeyError)`, missing `LanguageNotFoundError`/`ParserError`);
`chunker.py:106` reads strict UTF-8 with no `errors="replace"`. Dead `end_line` conditional
(`core.py:668-679`) gives span-extended chunks (Dart sig+body, R) line ranges inconsistent with
their bytes. Svelte whole-file control-flow scan (`core.py:867-899`) runs once per top-level node →
control-flow chunks emitted 2–3× per file. Token split sub-chunks (`token/chunker.py:292-325`) all
inherit `byte_start=original.byte_start` → offsets on split parts are wrong. `smart_context.py:116`
caches by `(chunk_id, type)` while the result depends on the `chunks` argument → stale cross-repo
results (1 h TTL); O(n²) all-pairs feature extraction. Incremental content-diff (`incremental.py:236`)
reparses with `file_path=""` so no ID ever matches → every edit reports all-ADDED + all-DELETED, and
because content is in the ID the MODIFIED path is structurally dead (edits mis-classified as MOVED).

**Boundary IR.** `_grammar_version()` returns constant `f"tree-sitter-{language}"`
(`adapter.py:338`) — pack/runtime versions absent from the incremental cache key → a pack bump
without a chunker release reuses stale nodes → Frankenstein IR (cold path only is gated).
`_floats_to_strings` (`serialization.py:150`) uses Python `repr()`, whose exponent thresholds differ
from JS Number→string (`1e-05` vs `0.00001`) → a `confidence < 1e-4` diverges from the TS canon
port — the exact cross-language float divergence canon exists to prevent. The parity digest that
other tools consume has no committed cross-tool golden (`test_boundary_parity_view.py` is
self-referential).

**Concurrency / repo-scale.** `streaming.py:90-94` hardcodes Python-only node types → zero chunks
for Rust/Go/JS/Java; `parallel.py:70-81` timeout is dead code (`result(timeout=10)` only on
already-completed futures) → a hanging file blocks forever; `clustering/engine.py:236` calls
`leidenalg.find_partition` with **no seed** → nondeterministic clusters; `graph/xref.py:61-153` is
O(n²·refs) and rebuilt every watch-poll; `repo/processor.py:750` constructs a fresh `git.Repo` +
`check-ignore` subprocess + full index scan per file (O(n²) on large repos); `:546` crashes on stale
`last_commit` (gitpython `BadName` uncaught) instead of full-scan fallback; `watch_repository`'s
`while True` pegs a core re-chunking non-git dirs every second; `performance/optimization/
incremental.py:159` hardcodes `language="python"` for every incremental re-parse.

**Security.** No integrity gate between grammar download and execution (`grammar/download.py:89-372`:
fetch `master` → `cc` compile → `ctypes.CDLL` load → entrypoint invoked) — *this is the real
unconditional code-execution surface, not `ext::`.* Missing URL validation in
`grammar_management/core.py:694` still enables arbitrary-host clone/SSRF and (with
`protocol.ext.allow` loosened, or on hosts that set it) `ext::` RCE; `git checkout <version>` with no
`--` separator is option-injection-prone. The correct validator already exists unused one file over
(`grammar_manager.py:84-93`) — though its `"github.com" in netloc` substring check is itself weak
(accepts `github.com.evil.example`). `build/builder.py:627` `tarfile.extractall()` with no
`filter=` → path traversal from a crafted conda package. Plugin `exec_module()` on any file in a
watched dir (`plugin_manager.py:386`) is the expected plugin trust model but undocumented and
unguarded.

**Interfaces.** `export/formats/json.py:68` `gzip.Path(...)` — no such attribute → every
`compress=True` export raises `AttributeError` (never worked). Two divergent CLI stacks (typer
`cli/` vs argparse `chunker/cli/`) with different grammar management, resolution-mode defaults, and
flag conventions; duplicate parquet exporters with incompatible column schemas for the "same"
format; three hand-rolled language ext-maps that already disagree on `.ts`.

**Cross-cutting.** ~45–55k LOC of dead phase-scaffolding shipped in the wheel and maintained under
CI: `extractors/` (11.6k), `integration/` (13.3k, wired only via a swallow-all `try/except`),
`error_handling/` (12.9k — core uses a *different* `_internal/error_handling.py`), plus `testing/`,
`deployment/`, `devenv/`, `distribution/`, `cicd/`, `monitoring/`. Four separate config systems with
no precedence; two byte-identical `PluginConfig` dataclasses (`base.py` vs `plugin_base.py`) whose
type identity silently diverges; six exception classes never raised or caught.

---

## MINOR / hygiene

Public `chunker.chunk_text()` (`__init__.py:107`) writes every input to a `NamedTemporaryFile` and
round-trips through `chunk_file` → per-call disk I/O and failure on read-only tmpfs (the in-memory
`core.chunk_text` is *not* what `from chunker import chunk_text` gives you). `/graph/cut`
(`server.py:398`) is a shipped stub that always returns empty. Three-way version drift (pyproject
3.2.2, `_version.py` 2.0.0, `__init__` fallback 1.0.8) — *note: this checkout's egg-info reports
3.2.2, so the 1.0.8 fallback does not trigger here; the stale `_version.py` and wrong fallback
remain latent.* Fallback chunkers store character offsets in `byte_*` fields → wrong spans on
non-ASCII + O(n²) newline scans. `core._walk` has no recursion depth guard → `RecursionError` on
minified/deeply-nested input. **Committed cruft at repo root:** `test_api.py`,
`test_symbol_extraction.py`, `test_csharp.cs`, `test_tsx.tsx`, `test_wasm.wat`, `tmp_test.Rmd`,
`compatibility.db`, `troubleshooting.db`, `validation_report.json`, `setup.py.bak`, the **stale
`CODE_REVIEW_REPORT.md` (reviews v2.0.0)**, and 1141 tracked `ide/.../node_modules/` files. The
7.4 MB `mcp_server.log` is external contamination from an outside MCP indexer run with cwd here — not
this repo's code; add to `.gitignore` and delete.

---

## Advisor corrections applied (false positives caught)

- **`ext::` RCE "by default" is FALSE** (GPT-5.6, verified: `fatal: transport 'ext' not allowed` on
  git 2.34.1 default config). Reframed D1 around the download→compile→`CDLL` chain (D2) as the real
  unconditional RCE, with missing URL validation as the enabling defect.
- **Postgres SQLi** is confined to the *generated SQL file*, not the live DSN path (parameterized).
- **Plugin `exec_module`** is expected trust model, downgraded from standalone MAJOR to
  document-and-guard.
- **git `cat-file` process-leak** not demonstrated; the per-file Repo construction is still a severe
  scalability defect.
- **Version-drift** does not manifest in this checkout (egg-info present).
- Added by advisors: **`LocalFileSystem` sandbox escape** via absolute/`..` paths (`vfs.py:74`);
  init-time race in factory cold-miss (unlocked create + `LRUCache.put` discards the fresh Parser).

## Recommended order of work

1. **Stop the bleeding on exposure:** gate/remove the FastAPI server (C5) and add URL validation +
   download integrity to the grammar chain (security MAJOR / C-adjacent).
2. **Make gates honest:** parse the pack bound from `pyproject` (C6), add `test_canon_vectors.py` +
   `spec_tests/` to CI and run the full suite (or formally tier it), un-ignore the pyflakes F-rules,
   make mypy blocking (C7). Cheap and high-leverage — most are low-risk *because* the dead code has
   no consumers.
3. **Fix the core defects:** per-thread parser acquisition (C1), re-key maps/incremental on
   `definition_id` (C2), repair or delete mixed-language + VFS-streaming + streaming.py (C3/C4), seed
   Leiden, index-based xref, one `git.Repo` per op with `close()` + `BadName` fallback.
4. **Delete dead scaffolding** (~a third of the package) and root cruft.

# Code Review — treesitter-chunker v4.0.0 (post-remediation)

**Date:** 2026-09-02 · **Commit reviewed:** `2a728c5` (main, "Migrate workflows to Blacksmith") · **Scope:** whole repository
(97.4k LOC in `chunker/` + `cli/` + `api/`; 74.7k LOC of tests; CI, packaging, docs, repository hygiene)

**Method.** One lead reviewer read the core engine, concurrency/repo layer, Boundary IR, language plugins,
interfaces/CLI/export, tests/CI gates and repository hygiene directly, and verified load-bearing claims by running
code (probe scripts, `cProfile`, `ruff`, `pytest --collect-only`, the CI smoke batch, and the GitHub Actions API).
A security/supply-chain scout (Claude Sonnet) covered `api/`, `grammar*/`, `build/`, workflows and Dockerfiles; its
findings are marked *(scout)* and were spot-checked where noted. Every finding below carries a `file:line` and, where
possible, a reproduction. Items that could not be verified in this environment are marked **UNVERIFIED**.

This review deliberately does not re-litigate `CODE_REVIEW_v3.2.2.md`; Section 3 scores that remediation, and
everything after it is new.

---

## 1. Executive summary

The v3.2.2 remediation was real and substantial. Thread safety, the API surface, the Boundary IR determinism gate,
the grammar-download trust boundary and the identity scheme are all materially better than they were, and the code
carries unusually good in-line rationale. The codebase is nonetheless **not yet a release-quality library**, for
five reasons that are new, or newly visible, in 4.0.0:

1. **The nightly "full suite" has never executed.** Every one of the 51 scheduled CI runs since the schedule was
   added has failed in about five seconds at test collection, because `tests/integration/conftest.py` declares
   `pytest_plugins` in a non-root conftest. Push/PR CI stays green because it runs ~15% of the tests by explicit
   file list. Nobody noticed for a month, which means nobody reads the nightly signal (C1).
2. **The core walk is quadratic in file size.** `_walk` recounts newlines over the whole file prefix for every
   chunk (`chunker/core.py:745`). An 8.4 MB Python file never finishes; the VFS path routes it to that code path
   because it is under the 10 MB streaming threshold. Metadata extraction re-walks every subtree five times (C2).
3. **Identity is still not stable where it matters most.** `treesitter-chunker repo process` writes every file to a
   temp file before chunking, so every run produces different `node_id`s and reports `file_path` as
   `/tmp/tmpXXXX.python` (C3). Overloaded methods share a `definition_id`, so incremental diffs silently drop them
   (C4) — the same "silently drops chunks" class the 4.0.0 identity work was meant to close.
4. **The public `chunk_directory` only works for six languages** and returns `{}` for the rest (C5); at least twelve
   extension maps still disagree (three of them map `.ts` to JavaScript), despite the changelog's claim of one map.
5. **The repository itself is 97% junk by bytes**: two committed virtualenvs and 84 MB of Claude Code session logs,
   one of which contains a (truncated) PyPI token in a `.pypirc` block, plus the developer's personal Claude Code
   hooks that execute on every tool call for anyone who opens the repo in Claude Code (C6).

Beneath those: chunk explosion in Clojure/Elixir (one `defn` becomes nine chunks), a whole-file structural collapse
whenever any statement nests 900 levels deep, 16 of 26 language configs declaring node types that do not exist in the
pinned grammars, three parallel plugin hierarchies that the core walk bypasses with ~300 lines of inline
special-casing, ~35k lines with no production consumer, a ruff configuration that hides 742 findings, and a mandatory
dependency set (pyarrow, igraph, leidenalg, networkx, tiktoken, gitpython, and an unused pygments) that a chunking
library does not need.

The good news is that most of the critical items are small, mechanical fixes (Section 12 orders them). The structural
work (Sections 7–10) is the real "future of the codebase" and is where the remaining effort should go.

---

## 2. What is genuinely good — keep it

- **Boundary IR / canon subsystem.** The pack pin is single-sourced from `pyproject.toml` via
  `chunker/_internal/pack_pin.py` and asserted fail-closed; goldens cover 12 languages; a cross-tool parity golden is
  committed (`tests/fixtures/boundary_ir/parity-view.golden.json`); floats are rendered with ECMAScript
  `Number.toString` semantics (`chunker/boundary/serialization.py:147-182`); the cache key embeds pack and runtime
  versions (`adapter.py:338-345`); file discovery is sorted; cache writes are atomic; the vendored `_canon.py` carries
  its source digest and is proven against conformance vectors. This is the best-engineered part of the codebase.
- **Parser thread safety.** `ParserFactory.get_parser` is thread-local by construction with a generation counter for
  cache clears (`chunker/_internal/factory.py:263-300`); the lease API exists for callers that need exclusivity.
- **API hardening** *(scout, verified)*: bearer token with `secrets.compare_digest`, fail-closed when unset; canonical
  root confinement via `resolve_within_root`; CORS credentials off and `*` stripped; 1 MiB body cap; binds
  `127.0.0.1`.
- **Release pipeline** *(scout)*: every third-party action SHA-pinned; minimal `permissions`; OIDC trusted publishing.
- **The smoke batch is fast**: 401 tests in 3.8 s locally. That is a good foundation for a real PR gate.
- **Documentation of intent.** Comments explain *why* (e.g. the `<0.10` pack cap, the ARG_MAX batching). Keep that
  habit; several findings below exist only because the comment and the code disagree.

---

## 3. v3.2.2 remediation scorecard

| v3.2.2 finding | Status | Evidence |
|---|---|---|
| C1 shared Parser across threads | **FIXED** | thread-local `get_parser` (`_internal/factory.py:270-300`); `return_parser` is a no-op (`:346`) |
| C2 `chunk_id` collisions | **FIXED for chunk_id / REGRESSED into definition_id** | byte-identical siblings now get 4 distinct ids (probe); overloads share one `definition_id` → see C4 |
| C3 mixed-language TypeError | **FIXED, residuals** | `multi_language.py:954` uses `chunk_text`; region still parsed twice (`:947`); narrow `except` (`:988`) |
| C4 VFS streaming | **PARTIAL** | no more `vfs.Path`/duplicates, but return type flips list→iterator at 10 MB (`vfs_chunker.py:77`) and "streaming" reads the whole file (`:117`) |
| C5 unauthenticated API | **FIXED** *(scout)* | `api/server.py:66-83`; `tests/test_api_security.py` 4/4 pass; `/graph/cut` still unauthenticated (`:497`) |
| C6 pin-mirror drift | **FIXED** | `resolve_pack_pin()` parses pyproject; `tests/test_pack_pin_drift.py` |
| C7 hollow gates | **PARTIAL** | F-rules on, mypy baseline gate blocking; but BLE/S/B/RUF/UP/RET/I/Q still ignored (742 hidden findings) and the nightly never runs (this review's C1) |
| fallback never fires / strict UTF-8 | **FIXED** | `auto.py:227,379`; `core.py:1242-1246` |
| dead `end_line` conditional | **FIXED, but replaced by a quadratic scan** | `core.py:745` |
| Svelte control-flow duplicated | **FIXED** (dead block left behind, `core.py:942-985`) | |
| token-split `byte_start` | **FIXED** | `token/chunker.py:327-337` |
| `_walk` recursion guard | **FIXED, wrong granularity** | guard is whole-file (see M2) |
| streaming hardcoded Python types | **FIXED** (no depth guard, see M2) | `streaming.py:1-20` |
| `parallel.py` dead timeout | **FIXED** (hung workers orphaned, documented) | `parallel.py:65-140` |
| Leiden unseeded; xref O(n²) | **FIXED** | `clustering/engine.py:244-249`; `graph/xref.py:60-85` |
| git.Repo per file; BadName; watch loop | **FIXED** | `repo/processor.py:758-829, 832-911` |
| incremental MODIFIED dead | **FIXED** (overloads now dropped instead, C4) | `incremental.py:138` |
| smart_context cache keyed on `(chunk_id, type)` | **NOT FIXED** | `smart_context.py:851` |
| `_grammar_version` constant; float `repr`; parity golden | **FIXED** | `adapter.py:338`; `serialization.py:147`; parity golden committed |
| grammar integrity gate | **PARTIAL / inert** *(scout, verified)* | `grammar/download.py:56` `ARTIFACT_MANIFEST = {}`; only one of three download paths consults it |
| URL validation; `tarfile` filter; `--` separator | **FIXED / FIXED / alternate control** *(scout)* | `source_validation.py`; `build/builder.py:20-50`; `startswith("-")` rejects |
| `gzip.Path` | **FIXED** | `export/formats/json.py:68` |
| two divergent CLIs | **NOT FIXED** | `cli/` (typer) and `chunker/cli/` (argparse), the latter documented in `docs/grammar_management.md`, `docs/cli-reference.md` |
| duplicate parquet exporters | **NOT FIXED** | `export/formats/parquet.py` vs `exporters/parquet.py`, different schemas |
| three ext-maps disagree on `.ts` | **NOT FIXED** | now 12+ maps; `.ts→javascript` in `repo/processor.py:66`, `fallback_overlap/chunker.py:69`, `performance/optimization/batch.py:273`, `.chunkerrc` |
| two `PluginConfig` classes | **FIXED** | one class, `languages/base.py:56` |
| six exceptions never raised | **PARTIAL** | five remain (`LanguageError`, `LanguageLoadError`, `LibraryError`, `LibraryNotFoundError`, `ParsingError`); `LibraryNotFoundError` is even exported from `chunker/__init__.py` |
| 45–55k LOC dead scaffolding | **PARTIAL** | those packages are gone; ~35k lines remain with no production consumer (M13) |
| version drift | **FIXED** in code; **NOT FIXED** in conda/homebrew/SECURITY.md (M14) | |
| `LocalFileSystem` sandbox escape | **FIXED** (root default is still `/`, i.e. no sandbox unless a root is passed, `_internal/vfs.py:81`) | |

---

## 4. CRITICAL

### C1 · The nightly full suite has never run (gate is false-green by construction)

**Evidence.** `scripts/run_full_suite.py:11` runs `pytest -q tests spec_tests`. `tests/integration/conftest.py:4`
declares `pytest_plugins = ["tests.integration.fixtures"]`. Because that conftest is discovered lazily during
collection, pytest ≥ 7 aborts with *"Defining 'pytest_plugins' in a non-top-level conftest is no longer supported"*
and exits 2 before running a single test. Reproduced locally (`pytest --collect-only -q` → `1 error`), and confirmed
in the log of the latest scheduled run (job 99727716128: `Interrupted: 1 error during collection`, Pytest step
4.6 s). All 30 most recent scheduled runs listed by the Actions API (of 51 total) are failures; push runs are green
because `run_ci_smoke.py` passes explicit file arguments, which makes that conftest an "initial" conftest.

**Impact.** Roughly 85% of the suite (≈2,550 of ≈3,000 tests) has not been executed by CI since the schedule was
added. The v3.2.2 traceability matrix cites nightly-only tests as proof of fixes.

**Fix (one line).** Delete `tests/integration/conftest.py`; `tests/conftest.py:1` already registers the same
plugin. Then: (a) add `pytest --collect-only -q tests spec_tests` to the PR gate so collection errors fail fast;
(b) route scheduled-run failures to a notification (GitHub Actions `workflow_run` → issue/Slack, or a README badge
on the schedule workflow); (c) record the first honest nightly result and triage it (a full local run is reported in
Appendix D).

### C2 · `_walk` is quadratic in file size; large files never finish

**Evidence.** `chunker/core.py:745` builds each chunk with `end_line=source[:span_end].count(b"\n") + 1`, scanning
the whole prefix of the file for every chunk. Measured with `extract_metadata=False`:

| definitions | file size | time | per chunk |
|---|---|---|---|
| 1,000 | 0.04 MB | 0.14 s | 136 µs |
| 2,000 | 0.08 MB | 0.24 s | 122 µs |
| 4,000 | 0.17 MB | 0.69 s | 172 µs |
| 8,000 | 0.33 MB | 2.05 s | 256 µs |
| 260,000 | 8.4 MB | killed at 25 s, stack in `_walk` | — |

`cProfile` on 6,000 definitions: `bytes.count` is 0.80 s of 3.75 s and grows with file size; with
`extract_metadata=True` (the default) `chunker/metadata/extractor.py:186 _walk_tree` is called 750,000 times
(five full subtree walks per chunk) for 1.37 s more. `resolve_chunk_predicates` is re-resolved for every node
(132,001 calls). The VFS chunker routes files under 10 MB to exactly this path (`vfs_chunker.py:77`).

**Fix.** Use the parser's own line numbers: `end_line = node.end_point[0] + 1` when `span_end == node.end_byte`
(the common case), and for the Dart/R span extensions count only the delta,
`node.end_point[0] + 1 + source[node.end_byte:span_end].count(b"\n")`. Hoist `resolve_chunk_predicates` to
`chunk_text` and pass the predicates down. Make the metadata extractor single-pass (one subtree walk collecting
signature, docstring, dependencies, imports, exports, calls). Convert `_walk` to an explicit-stack iteration (also
fixes M2). Expected: linear scaling, 2–3× faster on ordinary files, and 8 MB files in seconds.

### C3 · Repository processing produces non-deterministic identities and temp-file paths

**Evidence.** `chunker/repo/chunker_adapter.py:14-27` implements `Chunker.chunk(content, language)` by writing the
content to `tempfile.NamedTemporaryFile(suffix=f".{language}")` and calling `chunk_file(temp_path, language)`.
`chunk_file` bakes `str(path)` into every `node_id`/`chunk_id`/`file_id` and sets `chunk.file_path` to it
(`core.py:1241`, then `chunk_text` at `:1190-1197`). `RepoProcessor.__init__` uses that adapter by default (`repo/processor.py:43`), and
`_process_single_file` only patches `metadata["file_path"]` (`:381-384`). Reproduced: two consecutive
`process_repository()` calls on the same directory yield different `node_id`s, and `chunk.file_path ==
'/tmp/tmpie2d2w9o.python'`.

**Impact.** `treesitter-chunker repo process` (and anything consuming `FileChunkResult.chunks`) cannot be used for
incremental indexing, diffing, or as a stable key, which is the stated purpose of the 4.0.0 identity work. This is
the same bug class that 4.0.0 fixed for the public `chunk_text`.

**Fix.** Replace the adapter body with `core.chunk_text(content, language, file_path=str(rel_path))` (the
processor already knows `rel_path`; pass it through `Chunker.chunk(content, language, identity_path)`). Add a
determinism test: two runs of `process_repository` on a fixture repo must produce identical ids and repo-relative
`file_path`s.

### C4 · Overloaded definitions collide on `definition_id`; incremental diffs silently drop them

**Evidence.** `compute_definition_id` hashes `(file_path, language, qualified_route)` (`types.py:67-90`) and
`_walk` builds each route segment as `f"{adjusted_node_type}:{def_name}"` (`core.py:734`) with no arity or ordinal.
`DefaultIncrementalProcessor._identity_key` returns `definition_id or chunk_id` (`incremental.py:138-139`) and
builds dict maps keyed on it. Reproduced: a Java class with `foo(int)`, `foo(String)`, `foo(int,int)` yields 4
chunks but 2 unique `definition_id`s; editing the second overload produces a diff whose summary is
`modified 1, unchanged 1` for 4 chunks — two chunks vanish from the diff. C++ overloads: 5 chunks, 3 ids. The
Boundary IR adapter is *not* affected because it disambiguates collisions (`boundary/identity.py:20-35`,
`_dedupe_node_identities`); `incremental.py`, `DefaultChunkCache` and any consumer keying on `definition_id` are.

**Fix.** Disambiguate same-named siblings deterministically in the route (`method_declaration:foo#2`, or append a
short hash of the signature/parameter list when the extractor has it), or make `_identity_key` fall back to
`node_id` on collision the way the adapter does. Note the first option changes `definition_id` values (another
breaking identity change); batch it with any other identity fixes and bump the major version once.

### C5 · Public `chunk_directory` works for six languages and silently returns nothing for the rest

**Evidence.** `chunker/__init__.py:46` exports `parallel.chunk_directory_parallel` as `chunk_directory`.
`ParallelChunker.chunk_directory_parallel` uses a hardcoded six-entry map (`parallel.py:155-162`) and
`ext_map.get(self.language, [])`, so any other language finds zero files. Reproduced:
`chunk_directory(dir, language="go") == {}`, same for `ruby`; `python` works. The README's headline example is this
function. The changelog's "one canonical extension map" claim is also not true elsewhere:

| location | `.ts` maps to | entries |
|---|---|---|
| `chunker/auto.py:36` (`ZeroConfigAPI.EXTENSION_MAP`, the intended canon) | typescript | 64 |
| `chunker/repo/processor.py:66` (used by `repo process`) | **javascript** | 16 |
| `chunker/fallback_overlap/chunker.py:69` | **javascript** | |
| `chunker/performance/optimization/batch.py:273` | **javascript** | |
| `.chunkerrc` (shipped, auto-loaded by walking up from the target file) | **javascript** | |
| `chunker/parallel.py:155` | typescript | 6 languages |
| `multi_language.py:49`, `vfs_chunker.py:187`, `rules/custom.py:133/223/289`, `debug/tools/visualization.py:116`, `export/postgres_spec_exporter.py:111`, `fallback/intelligent_fallback.py:84`, `grammar/discovery.py:242`, `contracts/auto_stub.py:20` | typescript | various |

**Fix.** One module (`chunker/languages/extensions.py`) exposing `EXTENSION_MAP` and `extensions_for(language)`;
derive it from the registered `LanguageConfig.file_extensions` plus the pack's known languages; delete every other
map; add a test that greps the tree for `".ts":` outside that module. `chunk_directory` should use
`extensions_for(language)` and raise on an unknown language instead of returning `{}`.

### C6 · The repository ships 299 MB of junk, a token fragment, developer-personal data, and auto-executing hooks

**Evidence.** Of 6,310 tracked files (309 MB), 97% of bytes are: `.pubenv/` (2,850 files, 160 MB — a full
virtualenv including pyarrow `.so`s), `logs/` (85 files, 84 MB of Claude Code session transcripts),
`.toxenv/` (1,846 files, 45 MB), `site/` (built mkdocs output) and `archive/`. All were added in one commit
(`425fe73`, 2026-04-23) and are listed in `.gitignore` (lines 4, 88, 89), which does not un-track them. The pack
file is 68 MB, so every clone pays. `logs/ebb2220f-…/chat.json` contains a `.pypirc` block with
`password = pypi-AgEIcHl…` — a 29-character fragment followed by `…`, so truncated rather than directly usable, but
it proves a live token was pasted into a session. The logs also contain 92,205 occurrences of the developer's home
path and 159 of an internal email address. `.claude/settings.json:61-116` registers hooks that run
`uv run --script .claude/hooks/*.py` on every tool call and POST event summaries to `http://localhost:4000/events`
(`.claude/hooks/send_event.py:62`); these run for any contributor who opens the repo in Claude Code.

**Fix.** Rotate the PyPI token regardless. `git rm -r --cached .pubenv .toxenv logs site` and commit. Then decide
on history: a `git filter-repo` purge shrinks clones from ~70 MB to a few MB but invalidates existing clones/forks —
coordinate once, do it once. Add `gitleaks` (or GitHub secret scanning push protection) to CI. Move personal hooks
to `.claude/settings.local.json` (gitignored) or a separate dotfiles repo; keep only project-level, opt-in tooling
in the repo.

---

## 5. MAJOR

### M1 · Chunk explosion in Clojure and Elixir

`resolve_chunk_predicates` treats **every** `list_lit` as a chunk for Clojure (`core.py:462`), and the Elixir
config lists raw `call` as a chunk type (`languages/elixir.py:32`). Reproduced: one `defn` with a `let` body →
9 chunks (`list_lit` ×8); one Elixir `def` → 6 chunks (`call` ×3, `anonymous_function`). Every nested form or
function call inside a definition becomes its own chunk, so embeddings/indexes built from these languages are
mostly noise. **Fix:** chunk a `list_lit` only when its head symbol is in the def-family (the check already exists
at `core.py:688-712` for renaming; move it into the predicate), and drop raw `call` from Elixir's chunk types
(keep the `def*` reinterpretation).

### M2 · One deeply nested statement collapses the whole file to line-window chunks

`_walk` raises `RecursionError` at depth 900 (`core.py:500`), and `chunk_text` catches it for the **entire file**
and re-chunks it with `SlidingWindowFallback` (`core.py:1162-1165`), emitting a `FallbackWarning` advisory.
Reproduced: five ordinary functions plus one 1,500-deep parenthesised expression → **one** `fallback_lines`
chunk. Minified JS, generated data literals and large nested config literals trigger this. `StreamingChunker`
has no guard at all (`streaming.py:108`): a `RecursionError` propagates to the caller. **Fix:** iterative walk
with an explicit stack (no recursion limit), or at minimum a per-subtree guard that stops descending into the
offending node and keeps every sibling chunk; log at WARNING with the file and node position.

### M3 · 16 of 26 language configs declare node types that do not exist in the pinned grammars

Checked every `LanguageConfig` in `language_config_registry` against `tree-sitter-language-pack 0.9.0`
(`Language.node_kind_for_id`):

| config | unknown / declared | examples |
|---|---|---|
| elixir | 19 / 24 | `function_definition`, `behaviour_definition`, `handle_call`, … |
| dart | 16 / 23 | `function_declaration`, `class_declaration`, `constructor_declaration`, … |
| clojure | 13 / 17 | `defmacro`, `defprotocol`, `defrecord`, … |
| r | 9 / 15 | `function_declaration`, `left_assignment`, `setClass`, … |
| kotlin | 6 / 14 | `data_class_declaration`, `interface_declaration`, `sealed_class_declaration`, `init_block` |
| swift | 5 / 15 | `struct_declaration`, `enum_declaration`, `extension_declaration`, `actor_declaration` |
| matlab | 5 / 17 | `function_declaration`, `nested_function`, `script`, … |
| scala | 5 / 19 | `case_class_definition`, `method_definition`, … |
| xml | 5 / 6 | `comment`, `cdata_section`, `self_closing_tag`, `attribute_value`, `text` |
| sql | 4 / 19 | `create_procedure`, `with_clause`, … |
| yaml | 2 / 13 | `folded_scalar`, `literal_scalar` |
| dockerfile, javascript, ocaml, php, tsx | 1 each | `instruction`, `enum_declaration`, `constructor`, `anonymous_function_creation_expression`, `jsx_fragment` |
| `c_sharp` | — | config name does not resolve to a pack grammar (`csharp`); works only via alias |

Some of these are names the core walk *synthesises* after selection (Dart/Elixir/Clojure/R/Scala), so they never
match a raw node and are dead as selectors — chunking for those languages works only because of the separate
hardcoded sets in `resolve_chunk_predicates`. Others are plain misses: PHP anonymous functions are never chunked
(grammar node is `anonymous_function`), XML chunks only `element`, YAML block scalars are never chunked, and Swift
`struct`/`enum`/`extension`/`actor` and Kotlin `interface`/`data class`/`sealed class` are all reported as
`class_declaration` (kind information is lost). **Fix:** a CI test that loads every config and asserts each declared
node type exists in the pinned grammar (with an explicit allowlist of adapter-synthesised names), and per-language
kind derivation from the keyword child for Swift/Kotlin.

### M4 · The core walk bypasses the plugin system

There are three parallel abstractions — `LanguageConfig` (`languages/base.py:70`, 26 registered),
`LanguagePlugin` (`languages/plugin_base.py:29`, 32 classes, 19 of which also implement
`ExtendedLanguagePluginContract`), and the legacy shim `LanguageChunker` (`base.py:211`, still subclassed by
`go.py`, `java.py`, `ruby.py`) — with per-language duplicates (`go.py`/`go_plugin.py`, `java.py`/`java_plugin.py`,
`ruby.py`/`ruby_plugin.py`, `cs.py`/`cs_plugin.py`, `rust.py`/`rust_config.py`). `core._walk` consults only
`language_config_registry` (`core.py:10, 411`) and then applies ~300 lines of inline `if language == …`
special-casing for Dart, Elixir, Haskell, Scala, C++, Julia, SQL, Clojure, R, Go, Vue, Svelte and MATLAB
(`core.py:524-985`), with comments such as "Normalize to expected name used in tests/config". The plugins'
`process_node` / `get_node_name` / `get_semantic_chunks` hooks are never called on the main path.
`chunker/languages/__init__.py:160-277` ends with 26 empty `try: pass / except ImportError: pass` blocks.
**Fix:** see Section 7.1.

### M5 · `VFSChunker.chunk_file` changes return type at 10 MB and its "streaming" is not streaming

`vfs_chunker.py:77-82` returns a `list` for small files and a generator for `streaming=True` or files over
10 MB; the generator path reads the entire file with `read_bytes()` (`:117`), so callers get an API surprise
(`len()` raises `TypeError`) with no memory benefit. `LocalFileSystem()` without a root defaults to `/`
(`_internal/vfs.py:81`), i.e. no confinement unless the caller opts in. **Fix:** one return type (always a list, or
always an iterator with an explicit `stream=` flag); require a root or default to `Path.cwd()`.

### M6 · `parallel.py` design problems

`ParallelChunker.chunk_files_parallel` submits the bound method `self._process_single_file`, pickling the whole
object (including `ASTCache`) per task (`parallel.py:78-81`); errors are `print()`ed to stdout rather than logged
or raised (`:107`, `:118`, `:122`, `:138`); the convenience functions `chunk_files_parallel`/`chunk_directory_parallel` do not expose
`timeout_seconds` (`:171-196`); a `ProcessPoolExecutor` is spun up even for a handful of files (each worker
re-imports the 654-module package); hung workers are orphaned by design (documented at `:118-130`). Since
`Parser.parse` releases the GIL, a `ThreadPoolExecutor` default with a module-level worker function and an
`initializer` would be simpler and faster for typical inputs.

### M7 · `repo/processor.py` residuals

- `_filter_tracked_files` compares `str(path.relative_to(root))` (OS separators) with git index keys and
  `untracked_files` (POSIX) (`:801-829`). On Windows every file is filtered out whenever a `.gitignore` exists.
  **UNVERIFIED** on Windows; no Windows CI job exercises this path. Use `.as_posix()`.
- `watch_repository` never populates `nodes_removed` (`:956-1013`) and swallows `on_update` exceptions
  (`:878-881`).
- `GitAwareRepoProcessor.get_processable_files` skips the tracked/untracked filter entirely when the repo has no
  `.gitignore` (`:766-777`).

### M8 · `process_mixed_file` residuals

Each region is parsed twice (`multi_language.py:947` discards the tree, `:954` parses again). The fallback
`except (FileNotFoundError, IndexError, KeyError)` (`:988`) does not cover `LanguageNotFoundError`/`ParserError`,
so one unsupported embedded language aborts the whole file; regions in unsupported languages are silently dropped
(`:942-943`); the fallback chunk stores character offsets in byte fields (`:994-995`).

### M9 · Quality gates still hide most real defects

- `pyproject.toml` `[tool.ruff.lint.ignore]` lists ~100 codes plus the entire `I`, `Q`, `RET`, `RUF`, `UP`
  families. Running ruff with only `F,B,BLE,E722,S,PLW,PLE,PERF` enabled (minus `S101/S603/S607/S404`) reports
  **742** findings: `BLE001` 453 blind excepts, `F401` 81 unused imports, `S110` 50 try/except/pass, `B008` 25,
  `S608` 10, `S202` 1 (`grammar/download.py:196`), `PLE0604` 1 (`languages/__init__.py:129`).
- The mypy gate (`scripts/mypy_gate.py`) is baseline-relative over **1,243** signatures (≈2,244 raw errors); its
  signature is `path + message` as a *set*, so a second occurrence of an already-baselined message in the same
  file passes; `api/` is not checked; `python_version = "3.12"` while `requires-python >= 3.11` and CI runs
  3.11 (`pyproject.toml:441, 6`).
- `.pre-commit-config.yaml` pins black 24.3.0 and ruff 0.3.4; CI runs black 25.12.0 and ruff 0.12.5, so local
  hooks and CI disagree.
- PR gate = 401 smoke tests + 148 platform-core tests (overlapping) of ≈3,004 collected (≈15%), and nightly = 0
  (C1). The 60-minute CI timeout and the "pytest-timeout cannot kill a C-level hang" note (`ci.yml:44-58`) mean
  a grammar hang would still eat the budget; the promised subprocess hard-kill guard for the load smoke is not
  implemented.
- `tests/conftest.py:29-56` is an autouse fixture that replaces `process_file_with_memory` in
  `tests/test_parallel_error_handling.py` with a stub returning 100 and swallowing all exceptions, neutralising
  the "simulated error" branch that test file was written to exercise. 49 test functions contain no assertion
  (18 in `tests/test_phase15_languages.py`); `tests/phase13_debug_tools_integration.py` is never collected.

### M10 · Supply chain *(scout, spot-checked)*

- `uv.lock` (428 KB) is not what CI or the release build installs: `ci.yml:57`, `test.yml:55`, `release.yml:112`
  use `uv pip install`, which ignores the lock; only the language pack is hand-pinned. Use `uv sync --locked`.
- `release.yml:114` installs `git+https://github.com/tree-sitter/py-tree-sitter.git` at branch HEAD inside the
  job that builds the published distributions (`contents: write`). Pin a commit SHA or drop it (the wheel already
  depends on `tree_sitter>=0.25,<0.26`).
- The grammar "integrity gate" advertised in `CHANGELOG.md` and `SECURITY.md` never fires:
  `grammar/download.py:56` `ARTIFACT_MANIFEST = {}` is only populated by a test monkeypatch, and
  `grammar_management/core.py` and `grammar/manager.py` never call `verify_artifact`. The real control is the host
  allowlist + HTTPS + pinned-ref requirement, which is reasonable; say so in the docs, or populate the manifest.
- `Dockerfile:19` `COPY . .` with no `.dockerignore` copies the 299 MB of junk into every image build.
- `chunker/build/platform.py:208-217` runs `sudo apt-get install` on the user's behalf.

### M11 · Dependency footprint and import cost

`import chunker` loads 654 modules in 0.45 s, including all 35 language modules (via `core.py:10 →
languages/__init__.py`), `numpy` (via `query_advanced.py:8`), `tiktoken` (via `chunker.py:11`), and `yaml`.
Of the 19 mandatory dependencies, `pyarrow`, `networkx`, `igraph`, `leidenalg`, `tiktoken`, `gitpython`, `tqdm`,
`pathspec`, `chardet`, `python-dateutil`, `tomli-w` serve optional features, and **`pygments` is never imported
anywhere**. For a library whose core needs only `tree_sitter` + the language pack, this roughly triples install
size and adds two compiled-extension dependencies (`igraph`, `leidenalg`) that fail to build on some platforms.
**Fix:** extras (`[export]`, `[graph]`, `[repo]`, `[tokens]`, `[api]`), lazy imports inside the optional modules,
and a module-level `__getattr__` in `chunker/__init__.py` so the public names stay importable without eager loading.

### M12 · Dead and unreachable code (~35k lines)

Reachable only from tests (no CLI/API/public-API consumer): `performance/` 5,087 lines, `interfaces/` 5,079
(`interfaces/debug.py` and `interfaces/stubs.py` have zero importers), `contracts/` 2,722 (13 `*_stub.py`
files), `validation/` 2,131, `rules/` 1,628, `tooling/` 327, `exporters/` 213, `fallback_overlap/` 563,
`template_generator.py` 247, `vfs_chunker.py` 318, and `grammar_management/` 9,296 lines reachable only through
the argparse CLI and with **zero** tests. Duplicated exporters: two Parquet (different schemas), two SQLite, two
GraphML, two DOT, two Neo4j, two JSON. Two CLIs. Five exception classes never raised. Postgres
`_escape_postgres_identifier` defined and never called (`export/postgres_exporter.py:34-42`). Every line here is
maintained, linted, type-checked (or baselined), shipped in the wheel, and counted in the "97k LOC" that makes the
project look larger and riskier than its useful core (~40k lines).

### M13 · `smart_context` cache correctness (carried over, not fixed)

`InMemoryContextCache` keys on `f"{chunk_id}_{context_type}"` (`smart_context.py:851`) while the computed context
depends on the `chunks` argument, so two repositories (or two revisions) sharing a chunk id read each other's
cached context for up to an hour. Key on a digest of the chunk set (or scope the cache per call/session).

### M14 · Documentation and metadata drift

`README.md:188,670` says 29 built-in plugins (32 exported, 26 configs); `CONTRIBUTING.md:23` requires Python 3.8
and `:46` installs `py-tree-sitter` from git HEAD; `SECURITY.md:9` supports "1.0.x until 2026-01-27";
`conda/meta.yaml:2` is version 0.1.0; the root `treesitter-chunker.rb:21` tests a non-existent `chunker` binary
(a second formula lives in `homebrew/`); `pyproject.toml [project.urls]` still points at `ViperJuice/…` while the
badges point at `Consiliency/…`; `SUPPORT.md` and the README link to a readthedocs site with no `.readthedocs.yaml`
in the repo (**UNVERIFIED** whether the site resolves); `docs/` documents `python -m chunker.cli …` (the second
CLI); `pyproject.toml [tool.setuptools.package-data]` references `chunker/data/grammars/build/*`, which does not
exist; `MANIFEST.in` includes `setup.py` and `build/my-languages.so`, which do not exist. The `tsc` console-script
alias (`pyproject.toml [project.scripts]`) shadows the TypeScript compiler for anyone with Node's `typescript`
installed.

---

## 6. MINOR / hygiene

- `core.py:942-985`: Svelte control-flow block guarded by `and not is_svelte_root` is unreachable (the same
  condition defines `is_svelte_root` at `:507`); delete.
- `core.py:520-700`: seven `except Exception: pass` blocks inside `_walk` hide grammar/plugin bugs; log at DEBUG.
- 40 `print()` calls in library code (`grammar_management/testing.py` 10, `build/*` 19, `template_generator.py` 5,
  `parallel.py` 4); use `logging`.
- `factory.get_parser(language, config)` creates an uncached parser on every call when `config` is given
  (`_internal/factory.py:291-294`); `_parser_count` is incremented outside the lock.
- `ASTCache.__init__` creates `~/.cache/treesitter-chunker` at construction and unpickles cached chunk lists
  (`_internal/cache.py:65-70, 199`); `DefaultChunkCache` writes `.chunker_cache/` into the current directory by
  default (`incremental.py:448`). Both should honour `XDG_CACHE_HOME` and be opt-in.
- `.chunkerrc` is auto-loaded by walking up from the target file (`cli/main.py:193-247`); the shipped example's
  `exclude_patterns = ["*test*", …]` is matched with `fnmatch` against the full path, so any path containing
  "test" (e.g. `/home/me/latest/…`) is excluded.
- `api/server.py:497` `/graph/cut` is the only filesystem-free endpoint without auth, and has no server-side clamp
  on `radius`/`budget` *(scout)*.
- SQL identifiers are f-string-interpolated in `export/formats/database.py:100,139-141,376` and
  `export/postgres_exporter.py:302-306` with public `set_table_names()` setters and no validation; not reachable
  from the API today *(scout)*. `_escape_postgres_string` doubles backslashes, which is wrong under the default
  `standard_conforming_strings = on` *(scout)*.
- Bandit flags `hashlib.sha1` in `types.py`; add `usedforsecurity=False` to silence the noise honestly *(scout)*.
- `tests/test_language_smoke.py::test_every_pack_language_loads` still has no subprocess hard-kill guard, so the
  latent C-level hang the pyproject comment describes will again eat the 60-minute CI budget when the pack pin
  moves.
- `cli/main.py:252` `base_path: Path = Path.cwd()` is evaluated once at import (B008).
- `examples/` (51 files, 9.5k lines) has a validator (`scripts/validate_examples.py`) that no workflow runs;
  `benchmarks/` is likewise unwired.
- `grammars/grammars.json` is a tracked file that `TreeSitterGrammarManager` treats as mutable state
  (`chunker/grammar/manager.py:56`); running the test suite flipped the `nasm` entry from `"ready"` to
  `"building"` and left the working tree dirty. Tests should point the manager at `tmp_path`, and the file should
  either be untracked state under the cache directory or a read-only manifest.
- `chunker/languages/__init__.py:129`: `*_plugin_exports` inside `__all__` (PLE0604) — harmless but confuses tools.
- Windows-specific tests are limited to 8 files; nothing in the Windows job touches `repo/`, `vfs`, `parallel` or
  export paths beyond `test_export_integration_advanced.py`.

---

## 7. Architecture recommendations

### 7.1 One language model, data first

Replace the three hierarchies and the inline special-casing with a single `LanguageSpec` dataclass per language:

```python
@dataclass(frozen=True)
class LanguageSpec:
    id: str                          # "python"
    grammar: str                     # pack name, "python"
    extensions: frozenset[str]
    chunk_types: frozenset[str]      # raw grammar node types only, validated in CI
    ignore_types: frozenset[str]
    name_of: Callable[[Node, bytes], str | None] | None = None      # hook
    adjust: Callable[[Node, bytes], NodeAdjustment | None] = None   # rename / extend span / synthesise
    extra_chunks: Callable[[Node, bytes], list[SyntheticChunk]] | None = None
```

- Most of the 50 modules become a 10-line table entry; the handful with real logic (Dart signature merge, R
  `setClass`, Elixir `def*` reinterpretation, Svelte control flow) implement the hooks.
- `_walk` becomes language-agnostic: predicate, hooks, done. The 300 lines of `if language == …` move into the
  specs, next to the tests that motivated them.
- A CI test asserts every `chunk_types`/`ignore_types` entry exists in the pinned grammar (M3), and that every
  extension appears in exactly one spec (C5).

### 7.2 One identity contract, versioned

Write down, in `docs/chunk-identity.md`, the exact inputs to `node_id`, `definition_id`, `symbol_id`, `file_id`,
including the overload rule (C4) and the "identity path is repo-relative and never a temp path" rule (C3), and
version the contract (`identity_version` in `CodeChunk.metadata` and in the Boundary IR `run` block). Add one
property-based test (Hypothesis is a dev-dep-sized addition) that generates sibling definitions and asserts id
uniqueness and stability under whitespace-only edits.

### 7.3 Shrink the package to its core

Two tiers: `chunker` (core, ~40k lines: `core`, `types`, `parser`, `_internal`, `languages`, `boundary`, `fallback`,
`token`, `streaming`, `repo`, one export module, one CLI) and everything else either deleted or moved to a clearly
optional namespace with its own extra and its own tests. Concretely: delete `interfaces/debug.py`,
`interfaces/stubs.py`, the 13 `contracts/*_stub.py`, the five unused exceptions, the 26 empty `try` blocks, the
duplicate exporters, and the argparse CLI (port `grammar`/`symbols`/`cluster` subcommands into the typer app if
they are wanted; `grammar_management/` at 9.3k untested lines is a strong deletion candidate).

### 7.4 One CLI, one exporter registry

Fold `chunker/cli/` into `cli/`. Introduce `chunker/export/registry.py` mapping format name → exporter class with a
common `Exporter.write(chunks, path)` protocol, used by `chunk`, `batch`, `repo process` and the API alike, so
`--output-format` is the same list everywhere and each format has exactly one schema.

### 7.5 Explicit error policy

Adopt a rule: library code never `print()`s, never swallows `Exception` without logging, and distinguishes
"expected degradation" (fallback chunking, missing optional dependency → `warnings.warn`/`logger.warning`) from
"bug" (propagate). Enable `BLE001`, `S110`, `B904`, `B008` in ruff and burn the 530 findings down file by file with
targeted `# noqa` where an exception truly must be broad.

---

## 8. Efficiency improvements (ranked by expected gain)

| # | change | where | expected effect |
|---|---|---|---|
| 1 | `end_line` from `node.end_point` (+ delta count for extended spans) | `core.py:745` | removes the quadratic term; 8 MB file from "never" to seconds |
| 2 | Single-pass metadata extraction (one subtree walk per chunk) | `metadata/extractor.py:186` and callers in `_walk` | −35–40% on default `chunk_file` (1.37 s of 5.2 s at 6k defs) |
| 3 | Hoist `resolve_chunk_predicates` to `chunk_text`; pass predicates down | `core.py:503` | −6%; also removes a registry lookup per node |
| 4 | Iterative `_walk` with explicit stack | `core.py:487` | removes recursion overhead (0.76 s tottime at 6k defs) and the depth-900 collapse (M2) |
| 5 | Stop chunking every `list_lit`/`call` (M1) | `core.py:462`, `languages/elixir.py:32` | 5–10× fewer chunks for Clojure/Elixir |
| 6 | Lazy public API (`__getattr__`) and optional-dependency extras | `chunker/__init__.py`, `chunker.py`, `query_advanced.py` | `import chunker` from 0.45 s/654 modules to ~0.1 s; CLI startup and worker spawn cost drop accordingly |
| 7 | Threads instead of processes by default in `ParallelChunker`; module-level worker; no per-task `self` pickling | `parallel.py` | faster for small/medium directories; no orphaned processes |
| 8 | Region parsed once in `process_mixed_file` | `multi_language.py:947` | −50% on mixed files |
| 9 | Cache `Path.home()`/`XDG` resolution and open one sqlite connection per `ASTCache` (currently one per call) | `_internal/cache.py:140-147` | cheaper cache hits; note the hit path still hashes the whole file (`compute_file_hash`) — compare `size+mtime` first and hash only on match |
| 10 | Avoid `list(parent.children)` + `.index(node)` for Dart sibling search | `core.py:556-566` | minor; use `node.next_named_sibling` |

---

## 9. Test and CI strategy

1. **Fix collection, then look at the honest nightly.** (C1.) Appendix D reports a full local run; use it as the
   triage list.
2. **Tier by marker, not by file list.** Apply `@pytest.mark.slow` / `integration` / `benchmark` consistently
   (they are declared in `pyproject.toml` but barely used), then PR gate = `-m "not slow and not integration"` with
   `--timeout=60`, nightly = everything. Retire `run_ci_smoke.py`'s hand-maintained list once markers exist.
3. **Guards worth adding to the PR gate** (each is seconds): `pytest --collect-only`; declared node types exist in
   the grammar (M3); exactly one extension map (C5); `process_repository` determinism (C3); `chunk_directory` finds
   files for every registered language (C5); overload ids unique (C4); a 2 MB generated file chunks in < 2 s (C2);
   `import chunker` does not import `numpy`/`tiktoken`/`pyarrow` (M11).
4. **Remove neutralisers.** Delete the autouse fixture in `tests/conftest.py:29-56` and fix or delete the tests it
   was protecting; delete assert-free tests or give them assertions; rename `tests/phase13_debug_tools_integration.py`
   or delete it.
5. **Make the tiers run somewhere visible.** Nightly failures should open/refresh a single tracking issue; a
   scheduled job that nobody reads is the same as no job.
6. **Windows/macOS coverage should follow the Windows-sensitive code**: `repo/processor.py` path handling (M7),
   `vfs`, `parallel`, export writers with `encoding=`.
7. **Ruff**: enable `BLE`, `S110`, `B904`, `B008`, `PERF203`, `F401` first (they find bugs, not style); leave the
   pure-style families for a formatting-only PR. Align pre-commit pins with `uv.lock`.
8. **mypy**: check `api/`; set `python_version = "3.11"`; make the baseline count-aware (multiset) so duplicate
   signatures cannot hide new errors; ratchet the baseline down by package.

---

## 10. Dependencies, packaging, distribution

- **Extras**: `core` (tree_sitter, language pack, unicodedata2, pyyaml?), `[cli]` (typer, rich), `[tokens]`
  (tiktoken), `[export]` (pyarrow), `[graph]` (networkx, igraph, leidenalg), `[repo]` (gitpython, pathspec, tqdm),
  `[api]`, `[fallback]` (chardet). Drop `pygments`, `python-dateutil` (only `processors/logs.py`), `tomli-w`
  (only config writing) or move them to the extra that uses them.
- **Lockfile**: `uv sync --locked` in every workflow; keep the explicit pack pin as a second assertion.
- **Wheel contents**: `api/` is not in `[tool.setuptools.packages.find] include` although the README documents
  `treesitter-chunker[api]` — either include it (as `chunker.api`) or document that the server is a repo-only
  example. Remove the phantom `package-data` and `MANIFEST.in` entries. Add a `.dockerignore`.
- **Console scripts**: drop or rename `tsc`.
- **Versions**: `conda/meta.yaml`, `homebrew/`, the root `.rb` file and `SECURITY.md` should read the version from
  one place or be deleted if not maintained.
- **Release job**: pin the git dependency or remove it; run `twine check` and `check-wheel-contents` (already in
  `requirements-build.txt`, unused).

---

## 11. Documentation and metadata

Fix the drift listed in M14, then make the docs *generated where possible*: the language table from the specs
(7.1), the CLI reference from `typer`'s `--help`, the coverage table from `docs/language-coverage.json` (already
done for that one). Pick one docs system (mkdocs is configured and current; `docs/sphinx/` looks abandoned) and add a
`.readthedocs.yaml` if the hosted site is meant to exist. Retire `CODE_REVIEW_v3.2.2.md` and this file into
`docs/development/reviews/` once their action items are tracked as issues.

---

## 12. Recommended order of work

**Week 1 — stop the bleeding (all small, mechanical):**
1. Delete `tests/integration/conftest.py`; add `--collect-only` guard; add nightly failure notification (C1).
2. Rotate the PyPI token; `git rm --cached` the junk; add secret scanning; move personal hooks out (C6). Decide on
   the history rewrite separately.
3. `end_line` from `node.end_point` + hoisted predicates (C2, items 1 and 3 of Section 8).
4. `repo/chunker_adapter.py` → `chunk_text` with the repo-relative path (C3).
5. `chunk_directory` extensions from the canonical map; delete the other maps (C5).
6. Pin/remove the git dependency in `release.yml`; `uv sync --locked` (M10).

**Month 1 — correctness that changes outputs (batch into one 5.0.0 or a clearly announced 4.1.0):**
7. Overload-safe `definition_id` (C4) + identity contract doc (7.2).
8. Clojure/Elixir chunk selection (M1); per-subtree recursion handling with an iterative walk (M2).
9. Node-type validation test and the resulting config fixes (M3).
10. VFS return type; `LocalFileSystem` root default (M5). `smart_context` cache key (M13).

**Quarter — structure:**
11. `LanguageSpec` migration (7.1); delete the two extra hierarchies.
12. Package shrink and extras (7.3, Section 10); lazy public API (M11).
13. One CLI, one exporter registry (7.4).
14. Ruff/mypy ratchet and test tiering (Section 9).

---

## Appendix A — Measurements

| metric | value |
|---|---|
| Source lines (`chunker/`, `cli/`, `api/`) | 97,363 (`languages/` 15,847; `grammar_management/` 9,296; `export/` 6,531; `performance/` 5,087; `interfaces/` 5,079) |
| Test lines / files / collected tests | 74,729 / 247 / ≈3,004 (2,926 + 78 in `tests/integration`) |
| Tests run per PR | 401 (smoke) + 148 (platform core, overlapping) ≈ 15% |
| Tests run nightly | 0 (collection error) — 51/51 scheduled runs failed |
| Local smoke batch | 401 passed in 3.8 s |
| Tracked files / bytes | 6,310 / 309 MB; `.pubenv` 160 MB, `logs/` 84 MB, `.toxenv` 45 MB, `site/` 6 MB, `archive/` 3 MB (97%); pack file 68 MB |
| `import chunker` | 0.45 s, 654 modules, 35 language modules, numpy + tiktoken + yaml loaded |
| ruff findings hidden by the ignore list (F,B,BLE,E722,S,PLW,PLE,PERF) | 742 (BLE001 453, F401 81, S110 50, PERF203 43, B008 25) |
| mypy baseline | 1,243 signatures (≈2,244 raw errors) |
| `chunk_file` scaling (no metadata) | 1k defs 0.14 s → 8k defs 2.05 s; 260k defs (8.4 MB) not finished at 25 s |
| Profile, 6k defs, default options | 5.2 s total; `bytes.count` 0.83 s; metadata `_walk_tree` 750k calls / 1.37 s; `_walk` 132k calls |
| Language configs with non-existent node types | 16 of 26 |
| Extension→language maps | 12+ (three map `.ts` → javascript) |
| Exception classes never raised | 5 |
| `print()` calls in library code | 40 |
| Empty `try: pass` blocks in `languages/__init__.py` | 26 |

## Appendix B — How the key findings were reproduced

```bash
# C1: collection error (0 tests run) and the nightly job log
.venv/bin/python -m pytest --collect-only -q            # -> "1 error during collection"
# GitHub Actions API: workflow ci.yml, event=schedule -> 51 runs, all conclusion=failure;
# job 99727716128 log: "Defining 'pytest_plugins' in a non-top-level conftest is no longer supported"

# C2: scaling and profile
python - <<'EOF'
from chunker import chunk_file; import time, tempfile, pathlib
d = pathlib.Path(tempfile.mkdtemp())
for n in (1000, 2000, 4000, 8000):
    p = d / f"{n}.py"; p.write_text("".join(f"def f{i}(a,b):\n    return a+b+{i}\n\n" for i in range(n)))
    t = time.perf_counter(); chunk_file(p, "python", extract_metadata=False); print(n, round(time.perf_counter()-t, 2))
EOF

# C3: repo processing identity
# RepoProcessor(...).process_repository(dir) twice -> node_ids differ; chunks[0].file_path == '/tmp/tmp....python'

# C4: overloads
# chunk_text("class A { void foo(int x){} void foo(String s){} void foo(int a,int b){} }", "java", "A.java")
# -> 4 chunks, 2 unique definition_ids; DefaultIncrementalProcessor._compute_chunks_diff drops 2 of 4

# C5: chunk_directory(dir, language="go") == {}

# M3: node-type validity — for each config: tree_sitter_language_pack.get_language(name).node_kind_for_id(i)

# M9: what the ruff ignore list hides
.venv/bin/ruff check chunker/ cli/ api/ --isolated --select F,B,BLE,E722,S,PLW,PLE,PERF --ignore S101,S603,S607,S404 --statistics
```

## Appendix C — Things not verified in this environment

- Windows behaviour of `repo/processor.py` path comparison (M7) and of the export writers.
- Whether `treesitter-chunker.readthedocs.io` resolves (network to that host was not permitted).
- Whether the truncated PyPI token fragment corresponds to a still-active token (rotate regardless).
- Bandit's 22 medium / 193 low findings were not triaged individually *(scout)*.
- Runtime of the full suite on CI hardware; local numbers are in Appendix D.

## Appendix D — The honest full-suite result (first run since the nightly broke)

Run locally on this checkout with the collection error bypassed (`pytest -n 4 --timeout=300 --ignore=tests/integration
tests spec_tests`, then `tests/integration` separately), tree-sitter 0.25.2, language pack 0.9.0, no locally built
grammars, running as root, no `graphviz`:

| tier | result | wall time |
|---|---|---|
| `tests` + `spec_tests` (minus integration) | **2,842 passed, 59 failed, 21 errors, 4 skipped** | 6 min 30 s (4 workers) |
| `tests/integration` | 77 passed, 1 failed | 13 s |

The failures fall into four classes:

| class | count | tests | note |
|---|---|---|---|
| Environment-dependent, should `skip` when the prerequisite is missing | ≈34 | `test_wasm_language.py` (13, grammar `wat` not in the pack), `test_nasm_language.py` (8, `nasm` not in the pack), `test_registry.py` / `test_parser.py` / `test_integration.py` (7, expect the locally built `build/my-languages.so`), 4 × "DID NOT RAISE PermissionError" (`chmod`-based tests are moot as root), 2 × missing `dot` binary | these will also fail on any CI runner without `scripts/build_lib.py` output or graphviz; mark with `pytest.importorskip`/`skipif` |
| Likely real regressions or stale expectations | ≈30 | `test_phase15_languages.py` (12: metadata call/definition extraction returns `[]`), `test_zig_language.py` (8: zero chunks — the M3 node-type class), `test_ruby_language.py` (6: zero chunks through the `LanguagePlugin` API), `test_java_language.py` (2: names empty), `test_parquet_export.py` (`pyarrow ArrowTypeError: string vs dictionary` — the exporter's schema is inconsistent under pyarrow 21), `test_phase15_base_extractor.py`, `test_phase2_extractors.py`, `tests/unit/grammar/test_manager.py` (`'clone' == 'pull'`), `test_config_advanced_scenarios.py`, `test_streaming_languages.py`, `test_plugin_initialization_failures.py` | triage each; several are the same root cause as M3/M4 |
| Order- or timing-dependent | ≈10 | `test_system_optimizer.py` (7: psutil metric names, `tracemalloc` state), `test_parallel.py` (1 timeout at 300 s, 1 assertion), `test_language_smoke.py::test_coverage_matches_committed_oracle` (passes in the smoke batch, fails in the full run → another test mutates the registry), `test_scale_parser_holders.py` (asserts distinct `id(parser)` across threads; `id()` reuse after a thread exits can produce a false positive — or the enhanced chunker really shares; investigate) | isolate registry state per test; do not key on `id()` |
| Tracked residual | 1 | `tests/integration/phase9/…::test_docstring_extraction_with_rules` is listed in `docs/development/xfail-inventory.md` but carries no `xfail` marker, so it fails rather than xfails | apply the marker or fix it |

Two conclusions. First, the nightly, once it runs, will be red until the environment-dependent tests are made
conditional and the ≈30 real failures are triaged — budget for that before re-enabling it as a gate. Second, the
full suite is only 6.5 minutes on four cores; there is no reason it cannot run on every PR once the
environment-dependent tests skip cleanly (Section 9).

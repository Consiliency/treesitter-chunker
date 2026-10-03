---
automation:
  suite_command: 'uv run --with toml --all-extras pytest -q tests/test_public_grammar_validator.py && uv run --all-extras ruff check chunker/ cli/ tests/ --exclude archive --exclude logs --exclude site && uv run --all-extras black --check chunker/ cli/ tests/ scripts/ && uv run --with toml --all-extras python scripts/run_ci_smoke.py'
---

# Detailed plan: observable coverage contracts for treesitter-chunker#69

## Task and baseline

Plan independently landable test and code-review slices for treesitter-chunker#69.
Implement only slice 1 in the first PR. Each later slice gets its own PR and
review. Keep 5.1.1 usable throughout. Coverage is diagnostic information; no
slice adds a percentage gate or accepts a change solely because a number rose.

Baseline on clean `main` at `64069ff83d1ae1e180173686b145143583d981bd`,
using `uv run --with toml --all-extras pytest -q tests spec_tests --cov=chunker
--cov-report=term-missing --cov-report=json:<out>/coverage.json`:
3,472 passed, 4 skipped; 25,324 of 40,011 statements executed (63.29%),
14,687 missed. The raw local report is
`/tmp/treesitter-chunker-69-baseline-20261001/coverage.json`; rerun the command
to regenerate it. The small platform-core CI subset is a different sample and
must not be used as the representative baseline.

Remeasurement on merged `main` at `b5de78da67d3764d8096fac2ea36f4ad06a32577`
used the same representative command with pytest temporary files and its
coverage database on the private workspace volume: 3,509 passed, 4 skipped; 28,363 of 39,993
statements executed (70.9199%), 11,630 missed. The report is
`/tmp/treesitter-69-current-main-b5de78da.json`. The five largest gaps are
`grammar_management/cli.py` (808 missed), `compatibility.py` (536),
`config.py` (480), `core.py` (436), and `testing.py` (421). Slice 22 stays in
`config.py` because size eviction is a separate supported cache contract with
an independently testable file-selection order.

Remeasurement on merged `main` at `7ae3b01b4c0bf7b425518730dde214ce775d8b27`
used the representative command with private workspace temporary and coverage
data: 3,509 passed, 4 skipped, and one known load-sensitive timing failure in
treesitter-chunker#130; 28,408 of 39,993 statements executed (71.0324%),
11,585 missed. The report is
`/tmp/treesitter-69-current-main-7ae3b01b.json`. Grammar CLI remains the
largest module gap (808/1,210 missed), so slice 23 covers a distinct public
cleanup command contract there.

Remeasurement on merged `main` at `475906da1572abfe6d84f63a7c58b6360fa016f4`
used the representative command with private workspace temporary and coverage
data: 3,509 passed, 4 skipped, and two known load-sensitive timing failures in
treesitter-chunker#130 and treesitter-chunker#131; 28,456 of 39,993 statements
executed (71.1525%), 11,537 missed. The report is
`/tmp/treesitter-69-current-main-475906da.json`. Grammar compatibility is
the second-largest module gap (536/820 missed), so slice 24 covers a separate
language-filtered performance trend contract there.

Remeasurement on merged `main` at `0a559079aaaab27f5518ad194d485d84fcbfb201`
used the same representative command with private workspace temporary and
coverage data: 3,511 passed, 4 skipped, and one known load-sensitive timing
failure in treesitter-chunker#130; 28,473 of 39,993 statements executed
(71.1950%), 11,520 missed. The report is
`/tmp/treesitter-69-current-main-0a559079.json`. Grammar compatibility
remains the second-largest module gap (516/820 missed), so slice 25 covers
the independent database statistics contract. Its cleanup defect is filed
separately as treesitter-chunker#205.

Remeasurement on merged `main` at `0a60ad675a7678cf6ba1e6ed72875d5d0dcf009f`
used the same representative command with private workspace temporary and
coverage data: 3,514 passed, 4 skipped; 28,502 of 39,993 statements executed
(71.2675%), 11,491 missed. The report is
`/tmp/treesitter-69-current-main-0a60ad67.json`. Grammar configuration
still has 437 of 773 statements uncovered, so slice 26 covers the independent
selective cache-clearing contract.

Remeasurement on merged `main` at `dcf127f72125c8eb947742a19b3e3bbf1c3a0f88`
used the same representative command with private workspace temporary and
coverage data: 3,516 passed, 4 skipped, and one known load-sensitive timing
failure in treesitter-chunker#130; 28,559 of 40,000 statements executed
(71.3975%), 11,441 missed. The report is
`/tmp/treesitter-69-current-main-dcf127f7.json`. Grammar configuration
still has 413 of 773 statements uncovered, so slice 27 covers cache size,
limit, and automatic-cleanup information as one observable contract.

Remeasurement on merged `main` at `a1071ca7` used the same representative
command with private workspace temporary and coverage data: 3,522 passed,
4 skipped, and one known load-sensitive timing failure in
treesitter-chunker#130 (10.41 seconds against a 10-second limit); 28,567 of
39,999 statements executed (71.4193%), 11,432 missed. The report is
`/home/viperjuice/workspace/tmp/treesitter-69-slice28/coverage.json`.
Grammar configuration still has 402 of 773 statements uncovered, so slice 28
covers directory usage reporting as an independent observable contract.

The table ranks **every zero-covered module first**, then the largest remaining
individual gaps. Risk is the possible consequence of an untested contract, not
an assertion that the module is in active production use. H means a parser,
packaging, repository, persistence, or CLI contract; M means an exported helper
whose consumer reachability still needs confirmation; L means an auxiliary
test/tool path. An external import search found no production call sites for
`chunker/grammar_management/`, `chunker/languages/version_detection/`, or
`chunker/languages/compatibility/` outside those packages. Exported names are
still user-visible, so each slice confirms its contract before testing it.

| Rank | Module (`chunker/` prefix omitted) | Missed / statements | Risk |
| ---: | --- | ---: | :---: |
| 1 | `grammar_management/cli.py` | 1,212 / 1,212 | H |
| 2 | `grammar_management/compatibility.py` | 818 / 818 | M |
| 3 | `grammar_management/config.py` | 770 / 770 | M |
| 4 | `grammar_management/core.py` | 705 / 705 | H |
| 5 | `grammar_management/testing.py` | 555 / 555 | L |
| 6 | `languages/compatibility/schema.py` | 407 / 407 | M |
| 7 | `languages/compatibility/database.py` | 368 / 368 | H |
| 8 | `languages/compatibility/grammar_analyzer.py` | 288 / 288 | M |
| 9 | `languages/version_detection/java_detector.py` | 248 / 248 | M |
| 10 | `languages/version_detection/cpp_detector.py` | 226 / 226 | M |
| 11 | `languages/version_detection/go_detector.py` | 226 / 226 | M |
| 12 | `languages/version_detection/javascript_detector.py` | 205 / 205 | M |
| 13 | `languages/version_detection/rust_detector.py` | 191 / 191 | M |
| 14 | `languages/version_detection/python_detector.py` | 173 / 173 | M |
| 15 | `repo/git_aware.py` | 140 / 140 | H |
| 16 | `interfaces/stubs.py` | 137 / 137 | L |
| 17 | `export/graphml_yed_exporter.py` | 94 / 94 | H |
| 18 | `build/cross_compile.py` | 68 / 68 | H |
| 19 | `grammar_management/__init__.py` | 14 / 14 | M |
| 20 | `languages/version_detection/__init__.py` | 8 / 8 | M |
| 21 | `languages/compatibility/__init__.py` | 5 / 5 | M |
| 22 | `build/builder.py` | 298 / 332 | H |
| 23 | `debug/interactive/node_explorer.py` | 222 / 290 | M |
| 24 | `debug/interactive/repl.py` | 171 / 221 | M |
| 25 | `cli/grammar_commands.py` | 170 / 270 | H |
| 26 | `export/formats/database.py` | 156 / 234 | H |

## Slice rules

Before each slice, confirm its exported or routed behavior is supported. Use a
checked-in source fixture and the pinned real Tree-sitter parser; do not mock
the implementation being measured. Pure metadata or storage contracts use a
fixture that is also parsed in the same test, then persist or classify that
fixture's observed language. Assert output, errors, side effects, and ordering
that a consumer can see. If an intended contract fails, file a separate issue
with a reproducer and stop that assertion; do not repair production code inside
the coverage PR. Later slices must remeasure current main before implementation.
The named mutation in each row is a deliberately wrong source edit. Its focused
test command must fail against that edit and pass after restoration; record the
result in the PR. Mutation experiments happen only in a disposable worktree,
with the original source restored before committing.

| Slice / separate PR | Target module(s) and observable contract | Real fixture and named mutation to kill |
| --- | --- | --- |
| **1 — public grammar validation** | `grammar_management/core.py` `GrammarValidator.test_parse_samples`: real Python fixtures parse successfully; an unavailable language reports setup failure; the validator's cache stays inside `tmp_path`. Add `tests/test_public_grammar_validator.py` and enroll it in the existing smoke/platform-core selections. | Parse `tests/fixtures/boundary_ir/repos/python/app/service.py` with the pinned parser. Mutation **invert sample-success condition** (`len(errors) == 0` to `!= 0`) must fail the valid-fixture test. |
| 2 — grammar registry selection | `grammar_management/core.py` `GrammarRegistry`: user/package/fallback discovery chooses the documented priority and returns metadata for a local grammar; no network fetch. | Parse a fixture with the selected pinned grammar. Mutation **reverse USER/PACKAGE priority** must fail. Add a separate registry contract test. |
| 3 — grammar CLI | `grammar_management/cli.py`: list/info/test expose the selected local grammar and a missing-language error through the public Click command, without downloads or global cache writes. | Feed the Python fixture to the command and inspect result. Mutation **report missing grammar as success** must fail. Add one CLI contract test file. |
| 4 — grammar configuration | `grammar_management/config.py`: save/reload of a temporary grammar directory and cache settings preserves values and does not touch the home directory. | Store the directory holding a Python fixture and parse that fixture with the pinned parser. Mutation **ignore saved nested cache setting on reload** must fail. Add one config contract test file. |
| 5 — grammar compatibility | `grammar_management/compatibility.py`: compatibility score/reason and grammar selection consistently prefer the compatible local grammar; history persists in a temporary database. | Parse Python and JavaScript fixtures with their real parsers. Mutation **prefer incompatible candidate** must fail. Add one compatibility contract test file. |
| 6 — grammar self-test utilities | `grammar_management/testing.py`: a bounded local validation workflow reports the real parser result and a missing grammar as failure, without installing from the network. | Parse the Python fixture. Mutation **aggregate a failed parse as success** must fail. Add one utility contract test file; keep this auxiliary path separate from the public CLI. |
| 7 — Python/JavaScript version hints | `languages/version_detection/python_detector.py` and `javascript_detector.py`: version hints from fixture source and local project metadata preserve source and precedence; exported info serializes the same result. | Parse checked-in Python and JavaScript fixtures first. Mutation **reverse explicit config/source precedence** must fail. Add one test file per language if either grows beyond a reviewable diff. |
| 8 — Rust/Go version hints | `languages/version_detection/rust_detector.py` and `go_detector.py`: Cargo/go.mod declarations and source directives yield stable primary versions. | Parse checked-in Rust and Go fixtures. Mutation **discard declared edition/go version** must fail. Add one test file per language as needed. |
| 9 — Java/C-family version hints | `languages/version_detection/java_detector.py` and `cpp_detector.py`: project/source version declarations and language feature hints produce consistent primary versions. | Parse checked-in Java and C++ fixtures. Mutation **ignore explicit standard/target declaration** must fail. Add one test file per language as needed. |
| 10 — compatibility records | `languages/compatibility/schema.py` and `database.py`: constraints select a compatible grammar, and SQLite round-trips versions/rules without mixing languages. | Parse a Python fixture, then persist its language/grammar pairing. Mutation **flip the version-constraint comparison** must fail. Add one schema/database contract test file. |
| 11 — compiled grammar analysis | `languages/compatibility/grammar_analyzer.py`: analyzer identifies the pinned local grammar's language/capabilities and rejects a missing file without fabricated metadata. | Parse the Python fixture with the same pinned grammar. Mutation **treat a missing grammar file as available** must fail. Add one analyzer contract test file. |
| 12 — git-aware repository selection | `repo/git_aware.py`: a temporary Git repo reports changed source files, respects ignore rules, and round-trips incremental state. | Parse a checked-in fixture copied into that repo. Mutation **include ignored source file** must fail. Add one repo contract test file. |
| 13 — GraphML export | `export/graphml_yed_exporter.py`: real chunks and relationships export with their source, target, and IDs intact. | Parse the Python fixture into chunks. Mutation **swap GraphML edge endpoints** must fail a parsed-XML assertion. Add one GraphML contract test file. |
| 14 — SQLite export | `export/formats/database.py` `SQLiteExporter`: exported real chunks and relationships round-trip with IDs intact in a temporary database. | Parse the Python fixture into chunks. Mutation **drop a SQLite relationship** must fail. Add one SQLite contract test file. |
| 15 — native build verification | `build/builder.py`: the supported native build path verifies a produced artifact and reports missing output as failure. | Parse a fixture with the selected pinned grammar before build verification. Mutation **accept missing build artifact** must fail. Add one build contract test file. |
| 16 — retired | The placeholder `build/cross_compile.py` API had no supported non-native target and could report an unrepaired manylinux wheel as successful. The owner chose retirement in treesitter-chunker#158; no coverage slice is planned for this removed module. | The Release workflow's universal wheel, checked after installation, is the supported cross-platform distribution. No mutation or coverage test applies to a removed API. |
| 17 — grammar commands | `cli/grammar_commands.py`: a local installed grammar is listed/validated and a missing grammar produces a nonzero command result without network fetch. | Parse the Python fixture with the selected grammar. Mutation **return success for failed grammar validation** must fail. Add one command contract test file. |
| 18 — interactive node navigation | `debug/interactive/node_explorer.py`: the routed debug explorer parses a local source fixture, navigates to a selected child, bookmarks it, returns to the root, and restores that bookmark without network access. | Parse the checked-in Python fixture through `explore_file` with scripted terminal input. Mutation **ignore requested child index and always choose child zero** must fail. Add one explorer contract test file. The separate breadcrumb defect is treesitter-chunker#188. |
| 19 — debug REPL local session | `debug/interactive/repl.py`: the routed REPL loads a local source fixture, detects its language, and saves the same source and command history to a requested temporary file. | Parse the loaded checked-in Python fixture with the REPL's real parser. Mutation **discard the loaded source before saving** must fail. Script only terminal input; do not mock the REPL or parser. |
| 20 — grammar CLI JSON export | `grammar_management/cli.py` `export`: a local grammar export retains the selected user path and priority when a package candidate also exists. The command writes to a requested temporary file without fetching anything. | Parse the checked-in Python fixture with the pinned parser, then inspect the JSON export through the public Click command. Mutation **drop selected grammar from export payload** must fail. Extend the existing grammar CLI contract test file. |
| 21 — grammar cache age cleanup | `grammar_management/config.py` `CacheManager.cleanup_old_files`: stale download and build files under a temporary grammar cache are removed with accurate counts and bytes, while recent files and the caller's home remain untouched. | Parse the checked-in Python fixture and cache copies with the pinned parser. Mutation **skip stale download eviction** must fail. Extend the existing grammar config contract test file. |
| 22 — grammar cache size cleanup | `grammar_management/config.py` `CacheManager.cleanup_by_size`: when a temporary grammar cache exceeds a requested size, its oldest file is evicted first with accurate counts and bytes, a newer parseable file remains, and a second call below the limit removes nothing. | Pad checked-in Python fixture copies with whitespace to 512 KiB and 768 KiB; put the oldest in builds, which is enumerated after downloads, and parse both with the pinned parser. Mutations **reverse oldest-first eviction order** (`mtime` descending) and **omit eviction sort** must fail. Extend the existing grammar config contract test file. |
| 23 — public grammar cache cleanup | `grammar_management/cli.py` `cleanup`: the public Click command honors `--days 20`, reports one removed 25-day-old download, preserves a 15-day-old build file, and leaves the caller's home untouched. | Parse checked-in Python fixture copies with the pinned parser before and after calling the command against a temporary cache. Mutations **omit age at manager call** (use the 30-day manager default) and **omit age at Click call** (use the seven-day CLI default) must fail. Extend the existing grammar CLI contract test file. |
| 24 — compatibility performance trends | `grammar_management/compatibility.py` `CompatibilityDatabase.get_performance_trends`: recent Python records from real parsed fixtures aggregate throughput and memory in chronological order, excluding an older Python record and a recent JavaScript record. | Parse checked-in Python and JavaScript fixtures with pinned parsers, then store their language labels and deterministic metrics in a temporary SQLite database. Insert the newer Python record first. Mutations **invert language filter**, **reverse trend chronology**, and **omit trend ordering** must fail. Extend the existing grammar compatibility contract test file. |
| 25 — compatibility database statistics | `grammar_management/compatibility.py` `CompatibilityDatabase.get_database_stats`: after reopening a temporary SQLite database, statistics count two persisted compatibility records and one test result from parsed Python and JavaScript fixtures, report a nonempty file, and retain the oldest/newest timestamps and two-day span. | Parse checked-in Python and JavaScript fixtures with pinned parsers before storing records. Mutations **count test results from the compatibility table** and **use oldest as newest timestamp** must fail. Extend the existing grammar compatibility contract test file. Keep the cleanup defect in treesitter-chunker#205 separate. |
| 26 — selective grammar cache clear | `grammar_management/config.py` `CacheManager.clear_cache`: clearing downloads removes a nested parseable fixture file with accurate counts and bytes, leaves a parseable build file intact, preserves the managed download directory, and a repeated clear removes nothing. | Parse the checked-in Python fixture with the pinned parser, then copy it into temporary nested downloads and builds. Mutations **clear builds during downloads selection** and **omit recursive cache walk** must fail. Extend the existing grammar config contract test file. |
| 27 — grammar cache information | `grammar_management/config.py` `CacheManager.get_cache_info` and `is_cleanup_needed`: parseable nested download/build fixtures produce exact separate and total byte/MB sizes, percentage against the configured limit, and a cleanup-needed signal that follows the threshold and auto-cleanup switch. | Parse checked-in Python fixture copies padded to 512 KiB and 768 KiB with the pinned parser. Mutations **omit download bytes from total** and **ignore auto-cleanup setting** must fail. Extend the existing grammar config contract test file. |
| 28 — grammar directory usage | `grammar_management/config.py` `DirectoryManager.get_disk_usage`: a user-selected directory structure reports the exact file counts and sizes for parseable grammar and nested cache fixtures, includes both in the base total, and reports absent directories without creating them. | Parse checked-in Python fixture copies padded with whitespace to 128 KiB and 256 KiB using the pinned parser. Mutation **replace recursive file scan with shallow glob** must fail the per-directory and base totals. Extend the existing grammar config contract test file. |

`interfaces/stubs.py` remains in the ranked inventory but is not promoted into
a coverage slice until its consumer contract is confirmed. The node explorer
and debug REPL are routed by `cli/debug/commands.py`, so slices 18 and 19 cover
their local interactive contracts. Zero or low coverage must not be hidden
with a coverage omit rule. No PR should change more than one observable
behavior cluster.
The table above preserves the initial inventory; slice 16 was retired after
the treesitter-chunker#158 support decision, not hidden from the measurement.

## Documentation and defects

The plan and each slice's PR description record contracts, mutation evidence,
and any issue filed for a defect. Update user docs only when a verified public
contract is clarified. Do not silently correct documentation or implementation
while adding coverage. Keep README Codecov reporting as currently configured.
Slice 1 exposed a separate syntax-error acceptance defect, filed as
treesitter-chunker#116. The slice 1 PR does not change that production behavior.

## Dependencies and order

1. Publish this plan as a draft PR for treesitter-chunker#69.
2. Implement and review slice 1 on that draft PR; no later slice changes enter it.
3. Land later slices individually, refreshing the baseline and checking the
   relevant real grammar is present before each PR.
4. After representative behavior coverage is credible, assess CI measurement
   separately. This plan adds no percentage threshold or gate tied to its own
   outputs.

## Verification and acceptance

For slice 1, run the frontmatter suite command plus the focused mutation
experiment. The focused test must pass on ordinary source, fail on the named
mutation, and pass again after restoration. Every later slice has the analogous
focused command `uv run --with toml --all-extras pytest -q <its test file>` and
the same mutation protocol, followed by local lint, format, smoke, and relevant
platform checks before review. A full-suite coverage rerun is informational
after each merge; it is not an acceptance threshold for the slice.

- [x] Slice 1 real Python fixture parsing and unavailable-language reporting pass.
- [x] The named slice 1 mutation is killed by the focused test and restored.
- [x] The first PR changes only the plan, metadata/handoff, slice 1 tests, and
      existing CI test selections.
- [x] Any product defect observed while testing is filed separately and linked.
- [ ] Each later slice is reviewed and lands in its own PR after current-main remeasurement.

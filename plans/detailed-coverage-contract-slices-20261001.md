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
| **1 — public grammar validation** | `grammar_management/core.py` `GrammarValidator.test_parse_samples`: a real Python fixture parses successfully; an unavailable language reports setup failure; the validator's cache stays inside `tmp_path`. Add `tests/test_public_grammar_validator.py` only. | Parse `tests/fixtures/boundary_ir/repos/python/app/service.py` with the pinned parser. Mutation **invert sample-success condition** (`len(errors) == 0` to `!= 0`) must fail the valid-fixture test. |
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
| 16 — cross-compile verification | `build/cross_compile.py`: in a dedicated Docker-capable lane, a supported target produces a repairable wheel; unavailable Docker produces a clear failure. This work never runs in the default smoke lane. | Install the resulting wheel outside the checkout and parse the Python fixture. Mutation **ignore wheel-repair failure** must fail. If cross compilation is unsupported, file a retirement/support issue and defer this PR. |
| 17 — grammar commands | `cli/grammar_commands.py`: a local installed grammar is listed/validated and a missing grammar produces a nonzero command result without network fetch. | Parse the Python fixture with the selected grammar. Mutation **return success for failed grammar validation** must fail. Add one command contract test file. |

`interfaces/stubs.py` and the debug REPL/explorer are listed in the ranked
inventory but are not promoted into a coverage slice until their consumer
contract is confirmed. Their zero or low coverage must not be hidden with a
coverage omit rule. No PR should change more than one observable behavior
cluster.

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

- [ ] Slice 1 real Python fixture parsing and unavailable-language reporting pass.
- [ ] The named slice 1 mutation is killed by the focused test and restored.
- [ ] The first PR changes only the plan, metadata/handoff, and slice 1 tests.
- [ ] Any product defect observed while testing is filed separately and linked.
- [ ] Each later slice is reviewed and lands in its own PR after current-main remeasurement.

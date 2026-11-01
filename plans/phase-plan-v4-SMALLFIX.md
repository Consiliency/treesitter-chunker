---
phase_loop_plan_version: 1
phase: SMALLFIX
roadmap: specs/phase-plans-v4.md
roadmap_sha256: a96ef9073df2cd1bd860b1a151d75abc0a7edde7f242d8a2d7613c3fb38726c9
automation:
  # Post-merge suite. Each SL-sel issue adds its own test file; until a lane
  # PR merges, drop its missing file from this command.
  suite_command: "uv run --locked --all-extras pytest tests/test_grammar_sample_evidence.py tests/test_grammar_candidate_attribution.py tests/test_grammar_global_constraints.py tests/test_grammar_candidate_compatibility.py tests/test_grammar_compatibility_contract.py tests/test_compatibility_schema_version_boundaries.py tests/test_go_version_hints_contract.py -q -n 4"
---

# SMALLFIX: Selection metadata, version semantics and Go hints

## Context

SMALLFIX is Phase 7 of `specs/phase-plans-v4.md` (roadmap hash above). It
repairs six independent Tier 4 defects that need no admission or transaction
design: three in local grammar selection (theme F), one in language-version
comparison, and two in Go build-constraint hints (theme G). The plan starts
from main `d15a7484` (the treesitter-chunker#564 merge).

All six issues were re-read on 2026-11-01 with `gh issue view N --comments`.
They are open and unchanged since the roadmap snapshot. Each reproduces at
`d15a7484` with real parsers and real artifacts. The selection rows use the
checked-in BAML grammar (`packages/baml-grammar/src/parser.c`) compiled with
`cc` into the USER and PACKAGE directories:

| Issue | Observed on `d15a7484` |
|---|---|
| treesitter-chunker#133 | `check_compatibility("baml", code_samples=[declarations.baml], grammar_path=<compiled libbaml.so>)` gives `DEGRADED`, score 0.7, `successful_samples == 1`, warning `No test samples available for baml`. Without caller samples it is also `DEGRADED` 0.7. |
| treesitter-chunker#134 | With a `baml` install record whose `install_path` is the USER artifact (version `0.2.0`, parse time 0.01), `_discover_candidates("baml")` gives both the USER and the PACKAGE candidate version `0.2.0` and that metadata. `_resolve_conflicts` keeps 1 of 2. |
| treesitter-chunker#344 | `select_multiple_grammars(["baml"], global_constraints={"max_total_parse_time": 0.0, "same_priority": True})` returns the PACKAGE selection, with no error and no sign that the constraints were ignored. |
| treesitter-chunker#170 | A JavaScript `GrammarVersion` with `min_language_version="ES2020"`, `max_language_version="ES2023"` supports `ES2015`, `ES2021` and `ES2030`. `CompatibilitySchema.find_compatible_grammar` returns it for `ES2015`. |
| treesitter-chunker#437 | The Go service fixture prefixed with `// +build go1.10,go1.9` gives `1.9`; `// +build go1.9,go1.10` gives `1.10`. |
| treesitter-chunker#438 | `//go:build go1.18 && !go1.21` gives `1.21`; `//go:build go1.18 \|\| go1.21` gives `1.21`; `// +build !go1.21` gives `1.21`. |

Every prefixed Go source parses without error under the real pinned Go
parser. The exact commands and outputs go into each PR (VB-1).

## Interface Freeze Gates

None. No lane changes a public signature that another phase consumes. The
public behavior changes are:

- treesitter-chunker#344: `SmartSelector.select_multiple_grammars` raises
  `ValueError` for a nonempty `global_constraints` instead of ignoring it.
- treesitter-chunker#438: `GoVersionDetector.detect_version` gains a
  `build_constraints_status` result key (see SL-go).

## Lane Index & Dependencies

SL-sel — Local grammar selection evidence and metadata (treesitter-chunker#133 → treesitter-chunker#134 → treesitter-chunker#344)
  Depends on: (none)
  Blocks: (none)
  Parallel-safe: yes (disjoint files from SL-ver and SL-go)

SL-ver — ES version ordering (treesitter-chunker#170)
  Depends on: (none)
  Blocks: (none)
  Parallel-safe: yes

SL-go — Go build-constraint minimums (treesitter-chunker#437 → treesitter-chunker#438)
  Depends on: (none)
  Blocks: (none)
  Parallel-safe: yes

Every lane edits `CHANGELOG.md` (one Fixed entry per PR). Every new test file
is enrolled in `scripts/run_ci_smoke.py` and `scripts/run_platform_core.py`.
Those shared lines are resolved by the PR that merges second, by merging
`origin/main` into its branch (no force-push once a PR is open).

## Lanes

### SL-sel — Local grammar selection evidence and metadata

- **Scope**: Three serial PRs in `chunker/grammar_management/compatibility.py`,
  one issue each, merged in the order treesitter-chunker#133 →
  treesitter-chunker#134 → treesitter-chunker#344. Each branch starts from
  `origin/main`. The functions are disjoint, so a later PR merges `origin/main`
  after an earlier one lands and does not need to stack on it.
- **Shared file**: ADMIT SL-core (treesitter-chunker#562, open) edits only the
  two `GrammarValidator(...)` constructor lines in
  `CompatibilityChecker.__init__` and `GrammarTester.__init__`. ADMIT
  treesitter-chunker#556/#558/#562 also edit `core.py`. SL-sel touches neither
  constructor, and does not touch `core.py` (`_validate_standard` stays
  unchanged; it is not needed). Each PR body names the functions it touches.
  Whichever merges second merges `origin/main` into its branch. After ADMIT
  lands, the local BAML artifact in these tests needs a `trusted_artifacts`
  pin, as ADMIT does for `tests/test_grammar_candidate_compatibility.py`.
- **Test files**: one new file per issue, so the three PRs and ADMIT never
  edit the same test file:
  `tests/test_grammar_sample_evidence.py` (treesitter-chunker#133),
  `tests/test_grammar_candidate_attribution.py` (treesitter-chunker#134),
  `tests/test_grammar_global_constraints.py` (treesitter-chunker#344). Each
  builds real BAML artifacts from `packages/baml-grammar/src` and is
  Linux-only, as the existing compiled-BAML tests are (discovery globs `*.so`).

#### treesitter-chunker#133 — Caller samples count as evidence

- **Function touched**: `CompatibilityChecker._perform_detailed_compatibility_check`.
- **Contract**: The validator's `No test samples available for <language>`
  warning is an evidence gap, not a performance finding. It is kept in
  `warnings` but never sets `DEGRADED` by itself.
  - With caller samples, their real parse outcomes classify the candidate by
    the existing success-rate thresholds. An all-successful sample set is
    `COMPATIBLE` with score 1.0 (absent other warnings or slow metrics).
  - With the gap present and no caller samples, nothing was parsed. The
    level is `UNKNOWN` ("compatibility not yet determined") with score 0.3,
    the same value `_calculate_compatibility_score` gives `UNKNOWN`,
    **whatever other warnings exist**; every warning is kept. Otherwise a
    warned candidate (`DEGRADED`) would outrank a clean one (`UNKNOWN`) in
    `SmartSelector`, which never passes samples.
  - Other validation warnings (e.g. `Parsing performance is slow`) give
    `DEGRADED` 0.7 only for evidence-backed results; errors still give
    `INCOMPATIBLE`.
  - This contract covers local-candidate checks (`grammar_path=`). The
    canonical check without `grammar_path=` validates at BASIC, never sees
    the gap, and is unchanged (treesitter-chunker#588).
- **Docs**: `docs/grammar_management.md` (detailed compatibility checks)
  records the gap, the `UNKNOWN` no-evidence result and the evidence-only
  degradation.
- **Tests**: the real BAML artifact checked through `check_compatibility`
  with `grammar_path=`:
  - one successful `declarations.baml` sample → `COMPATIBLE`, 1.0, warning
    kept, `successful_samples == 1`;
  - a failing sample → `INCOMPATIBLE` (control: sample evidence still counts
    against);
  - no samples → `UNKNOWN`, not `DEGRADED`;
  - the real validator's warning text equals the text the checker
    recognizes (guards against wording drift);
  - an extra quality warning alongside the gap still gives `DEGRADED` when
    a caller sample was parsed;
  - the gap plus `Grammar file is unusually large` with no samples →
    `UNKNOWN`, both warnings kept;
  - selection with real artifacts: a USER build padded past 50 MB (warned)
    and a clean PACKAGE build; `select_best_grammar` returns PACKAGE.
- **Named mutations**: `M133-gap-degrades` (treat the gap as a quality
  warning, the old code) fails the successful- and failing-sample cases;
  `M133-quality-before-gap` (let a quality warning degrade a candidate with
  no samples) fails the no-sample quality and selection cases.

#### treesitter-chunker#134 — Per-artifact version and metadata

- **Functions touched**: `SmartSelector._discover_candidates`,
  `SmartSelector._resolve_conflicts`, and a new private helper.
- **Contract**: The installer keeps one install record per language, and the
  record names the artifact it describes (`install_path`). A discovered
  artifact gets that record's version and metadata only if it is that file
  (same file, or the same resolved path when either is missing). Every other
  artifact is `version="unknown"` with empty metadata. Conflict grouping
  (`_resolve_conflicts`) groups candidates only when they share a known
  version; `unknown` candidates are never grouped with each other. No
  database rows are involved, so no migration is needed.
- **Tests**: real USER and PACKAGE BAML artifacts. An install record for the
  USER file gives USER its version/metadata and PACKAGE `unknown`/`{}`, and
  the reverse for a PACKAGE record. Both survive `_resolve_conflicts`.
  Control: two artifacts whose records show the same known version still
  group (`_resolve_conflicts` exercised with the discovered candidates
  re-versioned). A record naming a third path attaches to neither.
  `select_best_grammar` still returns a real artifact.
- **Path matching tests**: the record names the USER file through `..`, a
  symlinked directory, and a missing segment (resolved-path fallback only);
  a record path with an embedded NUL attaches to no candidate and hides
  none.
- **Named mutations**: `M134-shared-record` (assign the record to every
  artifact, the old code) fails the attribution and grouping cases;
  `M134-group-unknown` (group `unknown` versions) fails the no-record case;
  `M134-plain-equality` (`grammar_path == Path(install_path)`) fails the
  spelling cases; `M134-fallback-false` (no resolved-path fallback) fails
  the missing-segment case; `M134-valueerror-escapes` (catch only
  `OSError`) fails the corrupt-path case.

#### treesitter-chunker#344 — Global constraints are rejected explicitly

- **Functions touched**: `SmartSelector.select_multiple_grammars`; the
  no-op `SmartSelector._optimize_global_selection` is removed.
- **Contract (this lane's decision)**: No cross-language constraint has
  defined semantics, so none is supported. A nonempty `global_constraints`
  raises `ValueError` naming the keys before any selection runs, pointing
  callers to per-language `select_best_grammar(..., constraints=...)`.
  `None` and `{}` keep the current behavior. Defining real cross-language
  constraints is a product decision for a future issue, not this repair.
- **Tests**: with real USER/PACKAGE BAML artifacts, a nonempty mapping raises
  and runs no discovery (asserted by unchanged discovery cache); `None` and
  `{}` select the real artifact. Docstring documents the contract.
- **Named mutation** `M344-ignore`: restore the silent pass-through; the
  rejection cases fail.

### SL-ver — ES version ordering (treesitter-chunker#170)

- **Owned files**: `chunker/languages/compatibility/schema.py`
  (`GrammarVersion._compare_versions`, `GrammarVersion.supports_language_version`,
  and a new module-level ES key helper),
  `tests/test_compatibility_schema_version_boundaries.py`, `CHANGELOG.md`.
- **Contract**: The supported ECMAScript family is `ES3`, `ES5` and the
  year editions `ES2015` and later (case-insensitive). They compare in
  release order ES3 < ES5 < ES2015 < ES2016 < …, which matches the repository's
  existing breaking-change range key (`_version_sort_key`) for every
  supported value. Any other ES-shaped value (`ES6`, `ESNext`, `ES4`,
  `ES5.1`), and any pair mixing an ES edition with a dotted number, is
  uncomparable: `_compare_versions` raises `ValueError` instead of returning
  0, and `supports_language_version` fails closed (returns `False`, logs
  why). The same applies to any other version text that cannot be compared.
  Numeric versions compare exactly as before. `CompatibilityRule` version
  constraints use the same comparator, so ES ranges and operators
  (`ES2015-ES2019`, `>=ES2020`) apply to the editions they name; a value a
  rule cannot compare makes it not match. ES6–ES14 aliases stay rejected:
  `_version_sort_key` reads `ES6` as 6 for breaking-change ranges, so
  aliasing would need both orderings changed.
- **Tests**: real JavaScript fixture parse (`service.js`) as the language
  guard; a grammar bounded ES2020–ES2023 rejects ES2015 and ES2030 and
  accepts ES2020/ES2021/ES2023, through `supports_language_version`,
  `get_compatibility_level` and `CompatibilitySchema.find_compatible_grammar`
  (grammar selection, with an ES2015–ES2019 grammar as the selected
  alternative); ES3/ES5 below ES2015; uncomparable values (`ESNext`, `ES6`,
  `1.5` against ES bounds) rejected, never silently accepted; Python numeric
  bounds unchanged.
- **Named mutation** `M170-zero`: restore `return 0` on a comparison failure;
  the uncomparable, selection (`ESNext` selected) and numeric-control cases
  fail. The unchanged code also fails the in-order ES bounds case, because it
  had no ES ordering at all. `M170-es6-ordinal` (accept `ES6` as 6) fails
  the "rejected, not ordered low" case against an `ES3`–`ES2023` grammar;
  `M170-rule-numeric` (rules keep the numeric-only comparison) fails the
  ES-range rule case.

### SL-go — Go build-constraint minimums (treesitter-chunker#437 → treesitter-chunker#438)

- **Owned files**: `chunker/languages/version_detection/go_detector.py`,
  `tests/test_go_version_hints_contract.py`, `CHANGELOG.md`. No user doc
  covers version detection, so the treesitter-chunker#438 contract is in the
  `analyze_build_constraints` docstring and the CHANGELOG.
- **Order**: treesitter-chunker#437 first (narrow legacy repair), then
  treesitter-chunker#438 replaces the regex extraction with the bounded
  minimum computation below, keeping every earlier contract test green.
  Because both rewrite the same function, the treesitter-chunker#438 branch
  starts from the treesitter-chunker#437 head and merges after it.

#### treesitter-chunker#437 — Legacy comma conjunction

- **Function touched**: `GoVersionDetector.detect_from_build_constraints`.
- **Contract**: A legacy `// +build` line that is a single comma conjunction
  of positive tags (no whitespace OR, no `!`) contributes all of its
  `goX.Y` release tags, so the highest one wins in either order. This
  supplements the existing extraction the way treesitter-chunker#436 did for
  modern positive conjunctions. OR and negation are unchanged here
  (treesitter-chunker#438). Modern-before-legacy and go.mod precedence are
  unchanged.
- **Tests**: on the real Go fixture (parse-checked): `go1.10,go1.9` and
  `go1.9,go1.10` give `1.10`; three-tag permutations; a mixed
  `go1.10,go1.9,linux` conjunction; LF and CRLF; modern-before-legacy and
  go.mod precedence controls.
- **Tags**: atoms follow Go's tag rule (Unicode letters and decimal digits,
  `_` and `.`), so `go1.10,café,go1.9` keeps both release tags; both release
  orders are tested.
- **Named mutations**: `M437-last-tag`: drop the conjunction supplement
  (only the greedy last tag is kept); the reversed-order cases fail.
  `M437-ascii-atoms` (ASCII-only atoms) fails the Unicode cases whose
  highest tag is not last.

#### treesitter-chunker#438 — Boolean expressions (detailed plan)

**Goal.** Report a truthful minimum Go release for compound build
expressions, or an explicit unknown. This is a bounded minimum-release
computation, not a build-constraint evaluator: it never decides whether a
file builds for a given GOOS/GOARCH/tag set.

**Recognized lines.**

- Header only, mirroring `go/build` `parseFileHeader`: blank lines and
  comments before the first other text, skipping `/* */` comments. A
  `//go:build` line anywhere in the header controls; legacy lines count only
  up to the header's last blank line. Lines after `package` (string
  templates, function bodies) are never read.
- Modern: a header line whose trimmed text is `//go:build` alone or
  followed by whitespace (Go's `isGoBuildComment` rule); a bare
  `//go:build` is recognized and `unknown`. Grammar: `or := and ('||'
  and)*`, `and := unary ('&&' unary)*`, `unary := '!' atom | atom`,
  `atom := '(' or ')' | tag` (a direct `!!` is `unknown`, as Go rejects it;
  `!(!x)` is valid), tags following Go's rule (Unicode letters and decimal digits, `_`
  and `.`; release tags `goX.Y` use ASCII digits), `&&` binding tighter
  than `||`.
- Legacy: a line whose trimmed text is `//`, optional spaces, `+build`, then
  whitespace-separated fields (OR) of comma-separated atoms (AND), each atom
  a tag or `!tag`.
- If a modern line is present, legacy lines are ignored (Go 1.17+
  behavior, and the existing modern-first precedence). More than one
  `//go:build` line is `unknown` (Go rejects the file: "multiple //go:build
  comments"). Multiple legacy lines are AND-ed, as Go does.

**Semantics.** A release tag `goX.Y` is true exactly at releases ≥ X.Y.
Every other tag (`linux`, `cgo`, `ignore`, custom tags) is treated as an
independent free variable. The hint is the lowest release R at which the
expression is true for some assignment of the free tags. Releases below R
cannot satisfy the release-tag part of the constraint, so R is a truthful
necessary minimum. It is computed by checking the critical points: "below
every mentioned release", then each mentioned release in ascending order.
Release tags are substituted with constants, and the residual formula over
free tags is checked for satisfiability by constant folding with
branch-on-a-variable (small, bounded inputs).

**Results.**

| Expression | `build_constraints` | `build_constraints_status` |
|---|---|---|
| `go1.18 && !go1.21` | `1.18` | `minimum` |
| `go1.18 \|\| go1.21` | `1.18` | `minimum` |
| `go1.21 && go1.9` (either order) | `1.21` | `minimum` |
| `(go1.18 \|\| go1.20) && linux` | `1.18` | `minimum` |
| `!go1.21`, `go1.18 \|\| linux`, `linux` | `None` | `unconstrained` |
| `go1.21 && !go1.18` (unsatisfiable) | `None` | `unknown` |
| malformed (`go1.18 &&`, unbalanced parens, direct `!!`, bare `//go:build`, two `//go:build` lines, `!!x` in legacy, bad characters) | `None` | `unknown` |
| no constraint line | `None` | `absent` |
| too large (over 1,000 tokens, nesting over 100, over 32 distinct free tags, over 10,000 search steps, or a release number over 9 digits) | `None` | `unknown` |

`detect_from_build_constraints` keeps its `str | None` signature and returns
the minimum. The new `analyze_build_constraints(content)` returns
`{"minimum", "status", "reason"}`. `detect_version` adds `build_constraints_status`
(`absent`/`minimum`/`unconstrained`/`unknown`). An unknown never becomes a
version string, so `get_primary_version` precedence (go.mod > build
constraints > runtime > features) is unchanged: an unknown or unconstrained
constraint falls through to the next source. The removed legacy negation
branch (which reported `X.(Y+1)` for `!goX.Y`) was unreachable behind the
greedy positive regex and was wrong (a negated tag is an upper bound).

**Documented unsupported forms.** GOOS/GOARCH exclusivity (e.g. `linux &&
windows` is treated as satisfiable), `ignore`, and file-name constraints
(`_linux.go`, `_test.go`) are not interpreted. The `unknown` results for
malformed legacy lines are deliberately conservative: Go replaces each
malformed term with the never-set `ignore` tag and the rest of that line
still counts, whereas any malformed legacy term makes the whole hint
`unknown` here. A release number longer than 9 digits is `unknown` (it is
never a real release, and Go never builds `go1.<4500 digits>`), and a
leading UTF-8 byte-order mark is skipped, as `go/build` does.

**Tests** (all on the real Go fixture, parse-checked, LF and CRLF where the
line ending matters):

- the table above, modern and legacy, including the issue's two forms;
- treesitter-chunker#436 and treesitter-chunker#437 contracts unchanged;
- precedence: modern over legacy, go.mod over an unknown or unconstrained
  build constraint, and an unknown constraint falling through to the
  feature-based minimum;
- `get_primary_version` never returns `unknown`.

**Named mutations** (each fails at least one case and passes once restored):

1. `M438-or-as-and` — combine `||` with max: `go1.18 || go1.21` gives 1.21.
2. `M438-not-as-positive` — evaluate `!goX.Y` as `goX.Y`: `go1.18 &&
   !go1.21` gives 1.21.
3. `M438-unsat-as-max` — report the highest mentioned release when the
   expression is unsatisfiable: the unsatisfiable case gives a version.
4. `M438-free-tag-false` — treat free tags as false: `go1.18 || linux`
   gives 1.18.
5. `M438-legacy-last-tag` — legacy comma terms keep only the last tag
   (`M437-last-tag` on the new code).
6. `M438-ascii-tags` — ASCII-only tag characters: `go1.18 && café`
   becomes unknown instead of 1.18.
7. `M438-whole-file` — scan every line (the old behavior): body and
   template lines count.
8. `M438-and-duplicates` — AND repeated `//go:build` lines.
9. `M438-bare-absent` — require whitespace after `//go:build`.
10. `M438-double-negation` — allow a direct `!!`.
11. `M438-slash-star` — read `//go:build` inside `/* */`.
12. `M438-legacy-no-blank` — legacy lines not cut at the last blank line.
13. `M438-unbounded-int` — no digit bound: a 4,500-digit release component
    raises `ValueError` through every public method.
14. `M438-bom` — keep a leading UTF-8 BOM: BOM-prefixed headers become
    `absent`.

The header cases are compared against Go 1.26.8 `go/build`
`Context.MatchFile` in the PR, and committed with each case's Go result.

## Execution Notes

- One issue per PR, each branch off `origin/main`, except
  treesitter-chunker#438, which starts from the treesitter-chunker#437 head
  because both rewrite the same function; it merges `origin/main` and the
  later #437 head in (never a rebase or force-push). The parent runs the
  two-reviewer panel (VB-4); the execution agent does not merge or request
  reviews, and does not force-push after a PR is open.
- Merge order: SL-sel serial (#133 → #134 → #344); SL-go serial (#437 →
  #438); SL-ver independent. `compatibility.py` merges one PR at a time with
  ADMIT SL-core.
- Host caps: one heavy run at a time, at least 6 GiB available and a load
  average under about 28 before a heavy run, `pytest -n` at most 4, scratch
  under `$TMPDIR`. `scripts/run_ci_smoke.py` hard-codes `-n auto`
  (treesitter-chunker#567), so local smoke runs its `CI_SMOKE_TESTS`
  selection with `-n 4`; each PR records that substitution.
- Windows preflight: treesitter-chunker#134 changes path handling (an
  install record attaches to an artifact by same-file or resolved-path
  match), so its PR runs the standing Windows preflight via `ssh win` in a
  clean temporary clone at the exact head (`git rev-parse HEAD` checked, every
  `uv` with `--directory <clone>`, clone removed afterwards). It also runs a
  real-file probe of that matching on Windows, because the compiled-BAML
  attribution tests are Linux-only (local `.so` builds) and hosted
  macOS/Windows platform-core runs them as skips. The other PRs touch no
  paths, native code, temporary files, export formatting or configuration,
  so they do not need it. Host WIN Application Control (Code Integrity 3077)
  and the treesitter-chunker#547 `WinError 32` teardown flake are recorded
  if seen, not chased.
- Separately discovered defects are recorded in their own issues, not folded
  in.

## Verification

- `uv run --locked --all-extras pytest <lane test file> -q -n 4` per PR, on
  unchanged code (fails) and on the fix (passes).
- `uv run --locked --all-extras pytest tests/test_grammar_candidate_compatibility.py tests/test_grammar_compatibility_contract.py -q -n 4` (SL-sel regressions).
- The CONTRIBUTING.md local validation block (Ruff, Black, mypy gate,
  governed body-type check, and the CI smoke selection at `-n 4`).
- Hosted Linux/macOS/Windows CI green at each PR head.

## Acceptance Criteria

Each criterion is met when every named mutation listed for its issue in
the lane sections above fails its test file and passes once restored.

- [ ] EC-SMALLFIX-1 — treesitter-chunker#133 by
  `tests/test_grammar_sample_evidence.py` (`M133-gap-degrades`,
  `M133-quality-before-gap`); treesitter-chunker#134 by
  `tests/test_grammar_candidate_attribution.py` (`M134-shared-record`,
  `M134-group-unknown`, `M134-plain-equality`, `M134-fallback-false`,
  `M134-valueerror-escapes`); treesitter-chunker#344 by
  `tests/test_grammar_global_constraints.py` (`M344-ignore`). Each uses real
  local BAML artifacts.
- [ ] EC-SMALLFIX-2 — treesitter-chunker#170 by
  `tests/test_compatibility_schema_version_boundaries.py` (`M170-zero`,
  `M170-es6-ordinal`, `M170-rule-numeric`): direct comparison, compatibility
  rules and grammar selection.
- [ ] EC-SMALLFIX-3 — treesitter-chunker#437 by
  `tests/test_go_version_hints_contract.py` (`M437-last-tag`,
  `M437-ascii-atoms`), then treesitter-chunker#438 by the same file (the 14
  `M438-*` mutations listed in its detailed plan), with module precedence
  preserved and the header cases checked against Go `go/build`.
- [ ] EC-SMALLFIX-4 — VB-1 to VB-4 for each PR.

## Spec Closeout Plan

- schema: `spec_delta_closeout.v1`
- decision: `no_spec_delta`
- target surfaces: issue acceptance for treesitter-chunker#133,
  treesitter-chunker#134, treesitter-chunker#170, treesitter-chunker#344,
  treesitter-chunker#437, treesitter-chunker#438
- evidence paths: `plans/phase-plan-v4-SMALLFIX.md`, PR logs
- redaction posture: `metadata_only`
- missing or malformed evidence: `blocker_class=contract_bug`

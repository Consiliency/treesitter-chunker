# Backlog inventory — 2026-10-06

## Audit scope and evidence

Audited Consiliency/treesitter-chunker’s open issues and PRs, their bodies/comments, exact draft heads/checks, merged repair history, current source, tracked plans/roadmaps, active specs and historical residual inventories. Primary main was clean at `d11186b9b97ce63eeb665885a2f89e51634c425d`. Snapshot facts are audit evidence, not future acceptance pins.

No tests/builds were run during this planning audit. Historical verification is attributed to its actual PR/run. [Roadmap v3](../../specs/phase-plans-v3.md) schedules the remaining work; older plans are inputs, not an automatic execution queue.

## Cleanup completed before planning

| Item | Disposition | Evidence/comment |
| --- | --- | --- |
| treesitter-chunker#124 | Closed as repaired duplicate | [Closeout](https://github.com/Consiliency/treesitter-chunker/issues/124#issuecomment-6011531341); treesitter-chunker#222 fixed the same defect tracked as treesitter-chunker#220; current source uses one sentinel and fixture regressions cover missing/present/None/reload/removal. |
| treesitter-chunker#107 | Closed as completed | [Closeout](https://github.com/Consiliency/treesitter-chunker/issues/107#issuecomment-6011531994); treesitter-chunker#108 was insufficient, but treesitter-chunker#340 replaces the noisy timing contract with repeated fresh-source parsing. |
| treesitter-chunker#171 | Closed without merge as superseded | [Closeout](https://github.com/Consiliency/treesitter-chunker/pull/171#issuecomment-6011532579); replacement treesitter-chunker#180 explicitly carries its repair and additional regressions. Branch/worktree retained. |
| treesitter-chunker#69 | Kept open; goal corrected | [Reconciliation](https://github.com/Consiliency/treesitter-chunker/issues/69#issuecomment-6011555470); owner’s behavior/mutation policy supersedes the original blanket 90% enforcement wording. |
| treesitter-chunker#128 | Kept open; completed portions identified | [Reconciliation](https://github.com/Consiliency/treesitter-chunker/issues/128#issuecomment-6011568804); treesitter-chunker#218 fixed signature/options, treesitter-chunker#219 fixed bulk filenames, but wrong-library validation remains. |
| treesitter-chunker#361 | New record-reconciliation tracker | Exposes stale plan status and residuals missing from the issue queue; audit/triage only. |

Counts: initially 61 issues/five drafts; two issues and one superseded draft closed, one previously untracked records issue opened. The initial inventory contained 60 issues. Review added treesitter-chunker#362, treesitter-chunker#363, treesitter-chunker#365 and treesitter-chunker#368; newly reported treesitter-chunker#367 is also enrolled. **65 open issues, four held drafts and active drafts treesitter-chunker#364/treesitter-chunker#366 remain.** No item was closed merely for age or overlapping scope.

Execution update: treesitter-chunker#366 merged at a74e58f2 with accepted metadata/mutation evidence and green changed-head Linux/macOS/Windows checks. Commented and closed treesitter-chunker#365 and treesitter-chunker#368; the clean repair worktree is pruned. CLEANUP review reproduced and separately filed treesitter-chunker#369 and treesitter-chunker#370. Live backlog remains 65 open issues; the two accepted precursors are moved out of the open map below. The native implementation runs against its frozen reviewed input in a separate worktree; downstream plan amendments do not edit that active runner state.

## Remaining draft PRs

All listed heads had successful executable hosted CI checks (the optional code-review bot check was skipped). None has a completed current integration/review acceptance; old green checks do not clear the reproduced blockers.

| PR | Exact audited head | State against main | Required next disposition |
| --- | --- | --- | --- |
| [treesitter-chunker#159](https://github.com/Consiliency/treesitter-chunker/pull/159) | `a57873cbd8b65b75a143777547c3e8c4a2f3de57` | Draft; merge conflicts | Three-round cap exhausted. Design treesitter-chunker#165 for treesitter-chunker#151; replace/redesign probe only after provenance/acknowledgment contract review. |
| [treesitter-chunker#161](https://github.com/Consiliency/treesitter-chunker/pull/161) | `e77d57301f74524acb4177e28c54d891e45ed316` | Draft; merge conflicts | Address treesitter-chunker#164 and treesitter-chunker#162; refresh native-suffix repair for treesitter-chunker#160 from then-current main and review integration delta. |
| [treesitter-chunker#157](https://github.com/Consiliency/treesitter-chunker/pull/157) | `b4cef0addd247ced6ac9075623704e9cb365f1f8` | Draft; behind main | Dependent status repair for treesitter-chunker#156: suffix/validation/replacement chain must land first; refresh and review without reopening the known cross-platform regression. |
| [treesitter-chunker#180](https://github.com/Consiliency/treesitter-chunker/pull/180) | `a08868c76b0f088d9d3ba98a63dccc09ce39da1e` | Draft; behind main | Resolve treesitter-chunker#182, treesitter-chunker#183, treesitter-chunker#184 and treesitter-chunker#185; also prove earlier treesitter-chunker#174, treesitter-chunker#175 and treesitter-chunker#176 acceptances. |

These are implementation blockers, not a current subscription-cap blocker. Preserve existing held worktrees until an accepted successor lands; do not prune unmerged unique work.

## Complete issue-to-phase map

Each issue appears once. “Inline” means a short focused implementation/verification/review plan, not permission to skip fixtures or code review. Detailed planning is reserved for shared safety/identity/persistence designs.

| Priority | Phase | Open item / observable gap |
| --- | --- | --- |
| P0 | SAFELOAD | [treesitter-chunker#165](https://github.com/Consiliency/treesitter-chunker/issues/165) — Design provenance-safe compiled grammar validation with parse acknowledgment |
| P0 | SAFELOAD | [treesitter-chunker#151](https://github.com/Consiliency/treesitter-chunker/issues/151) — GrammarAnalyzer reports empty shared library as supported grammar |
| P0 | SAFELOAD | [treesitter-chunker#164](https://github.com/Consiliency/treesitter-chunker/issues/164) — Validate legacy grammar fallbacks without mapping source or accepting null language |
| P0 | CLEANUP | [treesitter-chunker#323](https://github.com/Consiliency/treesitter-chunker/issues/323) — Core grammar cleanup can remove a file created during directory deletion |
| P0 | CLEANUP | [treesitter-chunker#324](https://github.com/Consiliency/treesitter-chunker/issues/324) — Grammar CLI fallback deletes recent files inside old cache directories |
| P0 | CLEANUP | [treesitter-chunker#177](https://github.com/Consiliency/treesitter-chunker/issues/177) — Reconcile auxiliary grammar self-test and CLI validator scenarios |
| P1 | CLEANUP | [treesitter-chunker#369](https://github.com/Consiliency/treesitter-chunker/issues/369) — Public fallback cannot import when core is unavailable; coupled static fallback boundary |
| P0 | CLEANUP | [treesitter-chunker#370](https://github.com/Consiliency/treesitter-chunker/issues/370) — Validation-cache writers lose fresh records and follow outside symlinks |
| P0/P1 | GRAMMARS | [treesitter-chunker#162](https://github.com/Consiliency/treesitter-chunker/issues/162) — Updating a loaded grammar in place can crash the Python process |
| P0/P1 | GRAMMARS | [treesitter-chunker#160](https://github.com/Consiliency/treesitter-chunker/issues/160) — Legacy grammar tools ignore native macOS and Windows library extensions |
| P0/P1 | GRAMMARS | [treesitter-chunker#117](https://github.com/Consiliency/treesitter-chunker/issues/117) — GrammarRegistry ignores native library suffixes on Windows and macOS |
| P0/P1 | GRAMMARS | [treesitter-chunker#128](https://github.com/Consiliency/treesitter-chunker/issues/128) — Compiled grammar validate accepts libraries without verifying the requested language |
| P0/P1 | GRAMMARS | [treesitter-chunker#120](https://github.com/Consiliency/treesitter-chunker/issues/120) — Grammar Click list reports an invalid local grammar as healthy |
| P0/P1 | GRAMMARS | [treesitter-chunker#156](https://github.com/Consiliency/treesitter-chunker/issues/156) — Grammar info command returns success for a missing grammar |
| P0 | GRAMMARS | [treesitter-chunker#362](https://github.com/Consiliency/treesitter-chunker/issues/362) — Remaining native admission, verdict-reuse and dependency-inspection paths |
| P1 | GRAMMARS | [treesitter-chunker#363](https://github.com/Consiliency/treesitter-chunker/issues/363) — Failed update logs rollback without restoring the old installation |
| P1 | CACHE | [treesitter-chunker#358](https://github.com/Consiliency/treesitter-chunker/issues/358) — Parallel chunk cache reuses core results for streaming requests and ignores parser pins |
| P1 | CACHE | [treesitter-chunker#136](https://github.com/Consiliency/treesitter-chunker/issues/136) — Explicit grammar cache directory does not reach registry and compatibility helpers |
| P1 | WHEELS | [treesitter-chunker#155](https://github.com/Consiliency/treesitter-chunker/issues/155) — Legacy build verifier rejects the supported pure Python wheel |
| P1 | WHEELS | [treesitter-chunker#174](https://github.com/Consiliency/treesitter-chunker/issues/174) — Reject missing RECORD and nested wheel metadata in build verifier |
| P1 | WHEELS | [treesitter-chunker#175](https://github.com/Consiliency/treesitter-chunker/issues/175) — Verify native grammars in the runtime package directory |
| P1 | WHEELS | [treesitter-chunker#176](https://github.com/Consiliency/treesitter-chunker/issues/176) — Reject build artifacts missing modules required for chunker import |
| P1 | WHEELS | [treesitter-chunker#182](https://github.com/Consiliency/treesitter-chunker/issues/182) — Use authoritative payload manifest for installed wheel verification |
| P1 | WHEELS | [treesitter-chunker#183](https://github.com/Consiliency/treesitter-chunker/issues/183) — Reject wheel members that collide at installed paths |
| P1 | WHEELS | [treesitter-chunker#184](https://github.com/Consiliency/treesitter-chunker/issues/184) — Preserve console command case in wheel verification |
| P1 | WHEELS | [treesitter-chunker#185](https://github.com/Consiliency/treesitter-chunker/issues/185) — Reject versioned native libraries in universal wheels |
| P1 | RUNTIME | [treesitter-chunker#355](https://github.com/Consiliency/treesitter-chunker/issues/355) — ParserConfig silently ignores timeout and logger on the pinned runtime |
| P1 | RUNTIME | [treesitter-chunker#357](https://github.com/Consiliency/treesitter-chunker/issues/357) — Fresh first-use grammar download can fail its 60-second deadline on a working slow connection |
| P1 | RUNTIME | [treesitter-chunker#359](https://github.com/Consiliency/treesitter-chunker/issues/359) — Main chunk CLI exits zero and mixes diagnostics into quiet JSON after per-file errors |
| P1 | RUNTIME | [treesitter-chunker#360](https://github.com/Consiliency/treesitter-chunker/issues/360) — Replacing a registered plugin leaves the prior cached instance active |
| P1/P2 | GATES | [treesitter-chunker#131](https://github.com/Consiliency/treesitter-chunker/issues/131) — Streaming variance assertion flakes in representative coverage suite |
| P1/P2 | GATES | [treesitter-chunker#143](https://github.com/Consiliency/treesitter-chunker/issues/143) — Language-pack Python smoke can hit five-second parse deadline under coverage load |
| P1/P2 | GATES | [treesitter-chunker#194](https://github.com/Consiliency/treesitter-chunker/issues/194) — Cached parallel sizing test has load-sensitive one-second gate |
| P1/P2 | GATES | [treesitter-chunker#195](https://github.com/Consiliency/treesitter-chunker/issues/195) — Large-file chunking exceeds ten-second performance gate under coverage |
| P1/P2 | GATES | [treesitter-chunker#200](https://github.com/Consiliency/treesitter-chunker/issues/200) — macOS config contention test has flaky 0.35-second wait limit |
| P1/P2 | GATES | [treesitter-chunker#207](https://github.com/Consiliency/treesitter-chunker/issues/207) — Compiled grammar symbol analysis times out in Linux CI under load |
| P1/P2 | GATES | [treesitter-chunker#322](https://github.com/Consiliency/treesitter-chunker/issues/322) — SIGINT integration test has load-sensitive startup and shutdown timeout |
| P1/P2 | GATES | [treesitter-chunker#342](https://github.com/Consiliency/treesitter-chunker/issues/342) — File-hash chunk-size timing assertion flakes under coverage |
| P1 | COMPAT | [treesitter-chunker#133](https://github.com/Consiliency/treesitter-chunker/issues/133) — Successful caller samples still degrade local grammar compatibility score |
| P1 | COMPAT | [treesitter-chunker#134](https://github.com/Consiliency/treesitter-chunker/issues/134) — Grammar selector assigns one language install record to every local candidate |
| P1 | COMPAT | [treesitter-chunker#135](https://github.com/Consiliency/treesitter-chunker/issues/135) — Nullable language version duplicates compatibility records and mislabels fallback reads |
| P1 | COMPAT | [treesitter-chunker#149](https://github.com/Consiliency/treesitter-chunker/issues/149) — CompatibilityDatabase upserts leave live schema stale |
| P1 | COMPAT | [treesitter-chunker#170](https://github.com/Consiliency/treesitter-chunker/issues/170) — ES-style JavaScript versions silently bypass grammar min/max constraints |
| P1 | COMPAT | [treesitter-chunker#344](https://github.com/Consiliency/treesitter-chunker/issues/344) — SmartSelector silently ignores global grammar-selection constraints |
| P1 | COMPAT | [treesitter-chunker#345](https://github.com/Consiliency/treesitter-chunker/issues/345) — Breaking-change detection loses findings when old parse time is zero |
| P1 | COMPAT | [treesitter-chunker#138](https://github.com/Consiliency/treesitter-chunker/issues/138) — Python version detector ignores pyproject requires-python and selects broad classifier |
| P1 | COMPAT | [treesitter-chunker#141](https://github.com/Consiliency/treesitter-chunker/issues/141) — Rust version info export cannot retain selected Cargo rust-version |
| P1 | COMPAT | [treesitter-chunker#142](https://github.com/Consiliency/treesitter-chunker/issues/142) — Go build-constraint detector orders 1.9 after 1.10 lexicographically |
| P1 | COMPAT | [treesitter-chunker#146](https://github.com/Consiliency/treesitter-chunker/issues/146) — C++ standard inference orders C++98 above newer standards |
| P2 | SEMANTICS | [treesitter-chunker#274](https://github.com/Consiliency/treesitter-chunker/issues/274) — Python definition lookup misses module function and class declarations |
| P2 | SEMANTICS | [treesitter-chunker#278](https://github.com/Consiliency/treesitter-chunker/issues/278) — Honor Python assignment-expression scope in comprehensions and defaults |
| P2 | SEMANTICS | [treesitter-chunker#283](https://github.com/Consiliency/treesitter-chunker/issues/283) — JavaScript definition lookup leaks block-local declarations |
| P2 | SEMANTICS | [treesitter-chunker#289](https://github.com/Consiliency/treesitter-chunker/issues/289) — JavaScript generator context includes full body instead of declaration summary |
| P2 | SEMANTICS | [treesitter-chunker#293](https://github.com/Consiliency/treesitter-chunker/issues/293) — Classify remaining JavaScript binding identifiers before reporting references |
| P2 | SEMANTICS | [treesitter-chunker#294](https://github.com/Consiliency/treesitter-chunker/issues/294) — Distinguish Python binding targets from expression uses in reference lookup |
| P2 | SEMANTICS | [treesitter-chunker#265](https://github.com/Consiliency/treesitter-chunker/issues/265) — Svelte each-block metadata regex cannot match normal source |
| P2 | SIGNATURE | [treesitter-chunker#352](https://github.com/Consiliency/treesitter-chunker/issues/352) — Go method_declaration signatures are never extracted |
| P2 | SIGNATURE | [treesitter-chunker#353](https://github.com/Consiliency/treesitter-chunker/issues/353) — C++ in-class member function declarations get no signature |
| P2 | SIGNATURE | [treesitter-chunker#354](https://github.com/Consiliency/treesitter-chunker/issues/354) — Add signature metadata extractors for Java, C#, Kotlin, Swift, PHP and Ruby |
| P2 | SIGNATURE | [treesitter-chunker#367](https://github.com/Consiliency/treesitter-chunker/issues/367) — Rust method signatures omit receiver and return type |
| P1 | EXPORT | [treesitter-chunker#167](https://github.com/Consiliency/treesitter-chunker/issues/167) — Graph exporters collapse distinct chunks sharing a line span |
| P1 | EXPORT | [treesitter-chunker#168](https://github.com/Consiliency/treesitter-chunker/issues/168) — GraphML export emits XML-invalid control characters from metadata |
| P1 | EXPORT | [treesitter-chunker#169](https://github.com/Consiliency/treesitter-chunker/issues/169) — GraphML metadata named label produces duplicate key IDs |
| P3 | RECORDS | [treesitter-chunker#361](https://github.com/Consiliency/treesitter-chunker/issues/361) — Reconcile historical plan status and residual work with current main |
| P3 | COVERAGE | [treesitter-chunker#69](https://github.com/Consiliency/treesitter-chunker/issues/69) — Expand representative coverage with reviewed behavior and mutation contracts |

## Deduplication decisions

- treesitter-chunker#117 is the exported GrammarRegistry suffix bug; treesitter-chunker#160 concerns legacy managers/tools. Separate implementations and tests.
- treesitter-chunker#164 is source validation/mapping; treesitter-chunker#162 is destination replacement. treesitter-chunker#165 establishes provenance and explicit parse acknowledgment for analyzer/legacy consumers. GRAMMARS must integrate registry/central/CLI admission and both installer publication paths before any wider guarantee. Contract review alone closes no implementation issue. One shared design can unblock them, but their contracts are not duplicates.
- treesitter-chunker#323 is concurrent publication versus deletion; treesitter-chunker#324 is a static mixed-age bug in a different fallback. The core static case already fixed by treesitter-chunker#320 does not close either.
- Wheel reports specify different install-invalid/unsafe cases. Land the authoritative manifest foundation first, then one independently reviewable behavior PR per finding, each with its code, regression and mutation together.
- treesitter-chunker#170 concerns GrammarVersion’s ES comparison, which current source still mishandles. treesitter-chunker#332 fixed a different breaking-change interval comparator.
- Python/JavaScript reference classifiers, declaration lookup and scope visibility are distinct observable contracts. treesitter-chunker#354 adds six language extractors; it does not repair Go/C++ defects treesitter-chunker#352/treesitter-chunker#353.
- Eight remaining timing/deadline reports target different tests or product probe paths. Passing a rerun or fixing continuous processing does not close them.
- treesitter-chunker#265’s problematic each_block branch is not emitted by the pinned parser. Keep it explicitly conditional; no fake-node test can satisfy its real-runtime acceptance.

## Planning and specification crosswalk

| Surface | Current disposition and follow-up |
| --- | --- |
| `specs/phase-plans-v1.md` and all ten `plans/phase-plan-v1-*.md` | Historical Boundary IR initiative. Existing Boundary IR schema/conformance tests and merged v1 work are evidence; audit residual unchecked criteria individually under treesitter-chunker#361. Do not rerun the whole roadmap. |
| `specs/phase-plans-v2.md` and all nine `plans/phase-plan-v2-*.md` | Historical v3.2.2→v4 remediation, merged in treesitter-chunker#91. Current traceability matrix documents delivered critical/major contracts; remaining residuals are triage inputs, not automatic implementation authority. |
| `docs/interface-boundary-roadmap.md` | Original feature intent, overlaps v1. Preserve as historical/reference intent; validate semantic/throughput leftovers against current implementations. |
| `plans/P20-pypi-install.md` | Original fresh-install plan implemented by treesitter-chunker#52 and subsequent fixes. Its old control-plane/dependency assumptions do not guide current pin updates. New first-download failure is treesitter-chunker#357. |
| `plans/detailed-boundary-ir-determinism-gate-20260624-2200.md` | Delivered by treesitter-chunker#79 and later pin/C# work. Historical language/version assumptions; use current conformance tests and regeneration policy. |
| `plans/detailed-baml-structural-chunking-20260928-0706.md` | Companion/integration delivered in treesitter-chunker#103 and treesitter-chunker#105; treesitter-chunker#101 closed. Optional companion 0.1.0 and overlay remain deliberate until reviewed upstream parity. |
| `plans/detailed-python314-unicode-wheels-20260929.md` | Source delivered by treesitter-chunker#114; published consumer acceptance closed treesitter-chunker#102. Old manifest “failed” publication status needs evidence reconciliation, not another source fix. |
| `plans/detailed-coverage-contract-slices-20261001.md` | Active treesitter-chunker#69 quality plan. Slices through 69 have merged evidence; 15 and 17 held, 16 explicitly retired by treesitter-chunker#193 under treesitter-chunker#158. Latest pre-slice-69 full run: 74.5721%, 3,655 passed/4 skipped on f0106078. Fresh main measurement still needed before new slices. |
| `plans/manifest.json` | Lifecycle metadata is incomplete/stale as a backlog index. Reconcile via supported metadata path under treesitter-chunker#361; preserve recorded history and runner ledgers. |
| `plans/hygiene-reachability-audit.txt` | Historical reachability evidence for delivered hygiene. Reuse as provenance; it is not an open execution plan. |
| `specs/active/release-process-spec.md` | Current production release contract, including fresh hash-checked wheel acceptance. Keep authoritative. No release task needed merely to publish this roadmap. |
| `specs/active/agent-platform-integration-spec.md` | Interface/design reference. Audit listed deliverables against current APIs/tests before assigning pending work; do not infer every paragraph is unimplemented. |
| `specs/active/v4-preprod-finalization-spec.md` | Labeled active consistency backlog, but not fully evidence-reconciled. Decode/JSON/API migrations require current behavior and compatibility evidence under treesitter-chunker#361. |
| `docs/development/xfail-inventory.md` | No active xfails recorded. Contains completed fallback/PARSER history plus pending overload/streaming/CLI/Parquet/type/config work. Split current findings from historical text during records audit. |
| `docs/development/traceability-matrix.md` | Historical delivered contracts; still lists fallback residuals the xfail inventory says resolved. Correct misleading current summary under treesitter-chunker#361. |
| `archive/` reviews, roadmaps and implementation plans | Historical evidence, including v4 review superseded by later v5 repairs/releases. Preserve archival status; reconcile any claimed residual before creating a new bug. |
| `.ai-dev-kit/` planning templates and tracked `site/` copies | Tool/generated mirrors, not separate product backlogs. Do not count these as independent plans or edit generated site output during cleanup. |

Unqueued historical work now covered by treesitter-chunker#361 includes overload-target resolution, Dart/R/Elixir/Svelte streaming adjustment parity, CLI-stack/Parquet consolidation, configuration unification, mypy debt and remaining v4 decode/JSON/API recommendations. It must be confirmed and separately scoped before code work. The old fallback residuals already have resolved evidence and must not be reopened solely because the matrix is stale.

## Linked dependencies and publication

- [v5.2.0 release](https://github.com/Consiliency/treesitter-chunker/releases/tag/v5.2.0) is published. [dotfiles#52](https://github.com/Consiliency/dotfiles/pull/52) is merged and refreshes the consumer/tooling lock to chunker 5.2.0 and Harness 0.7.23; this audit makes no consumer changes.
- agent-harness#1117 is closed; agent-harness#1211 is merged. Installed phase-loop command reports 0.7.23. Later supported human-publication adapter delivery is documented on agent-harness#1117; the old blocked plan status is stale, not an active blocker.
- [agent-harness#730](https://github.com/Consiliency/agent-harness/issues/730) remains open for subscription-429 classification. Recent manual tool-enabled Opus review completed after reset; this external report is not a current reason to stop planning.
- [BoundaryML/baml#5012](https://github.com/BoundaryML/baml/issues/5012) is open. [xberg-io/tree-sitter-language-pack#200](https://github.com/xberg-io/tree-sitter-language-pack/issues/200) is closed as completed: maintainer says BAML ships in 1.21.0 at ABI 14 but backtick prompts still fail until the BoundaryML fix. Keep our current 1.20.0 pin and companion overlay; pack migration requires explicit fixture/golden parity and review.
- Existing supplier admission requirements remain in force. This inventory is not a new evidence manifest, reviewer allowance or permission to edit preserved train state.

## Recommended first action

Plan SAFELOAD’s native admission/parse-acknowledgment contract using the roadmap skill handoff. CLEANUP is an independent safety root. Correct parallel cache identity follows next; the wheel/runtime/gate roots can proceed independently with disjoint ownership. Every later item has an explicit phase above.

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
treesitter-chunker#130 (10.41 ms per operation against a 10 ms limit); 28,567 of
39,999 statements executed (71.4193%), 11,432 missed. The report is
`/home/viperjuice/workspace/tmp/treesitter-69-slice28/coverage.json`.
Grammar configuration still has 402 of 773 statements uncovered, so slice 28
covers directory usage reporting as an independent observable contract.

Remeasurement on merged `main` at `73b3d2ea` used the same representative
command with private workspace temporary and coverage data: 3,523 passed,
4 skipped, and one known load-sensitive timing failure in
treesitter-chunker#130 (21.51 ms per operation against a 10 ms limit);
28,588 of 39,999 statements executed (71.4718%), 11,411 missed. The report is
`/home/viperjuice/workspace/tmp/treesitter-69-slice29/coverage.json`.
Grammar configuration still has 385 of 773 statements uncovered, so slice 29
covers cleanup of empty child directories as an independent observable contract.

Remeasurement on merged `main` at `6e78d24b` used the same representative
command with private workspace temporary and coverage data: 3,526 passed,
4 skipped, and one known load-sensitive timing failure in
treesitter-chunker#130 (11.61 ms per operation against a 10 ms limit);
28,686 of 39,998 statements executed (71.7186%), 11,312 missed. The report is
`/home/viperjuice/workspace/tmp/treesitter-69-slice30/coverage.json`.
Grammar configuration still has 384 of 773 statements uncovered, so slice 30
covers backup and restore as an independent observable contract.

Remeasurement on merged `main` at `cb032864` used the same representative
command with private workspace temporary and coverage data: 3,529 passed,
4 skipped, and two failures. The streaming timing assertion is the known
load-sensitive treesitter-chunker#131; the grammar integration test reached
GitHub but its Git clone ended with a connection reset. 28,691 of 40,000
statements executed (71.7275%), 11,309 missed. The targeted grammar integration
rerun passed. The report is
`/home/viperjuice/workspace/tmp/treesitter-69-slice31/coverage.json`.
Grammar configuration still has 337 of 775 statements uncovered, so slice 31
covers backup retention as a separate observable contract.

Remeasurement on merged `main` at `26fe113f` used the same representative
command with private workspace temporary and coverage data: 3,535 passed,
4 skipped; 28,763 of 40,000 statements executed (71.9075%), 11,237 missed.
The report is
`/home/viperjuice/workspace/tmp/treesitter-69-slice32/coverage.json`.
Grammar configuration still has 311 of 775 statements uncovered, so slice 32
covers the public configuration export command as an independent contract.

Remeasurement on merged `main` at `8fb7cc1f` used the same representative
command with private workspace temporary and coverage data: 3,535 passed,
4 skipped, and one known load-sensitive failure in treesitter-chunker#130
(13.77 ms per operation against a 10 ms limit); 28,785 of 40,000 statements
executed (71.9625%), 11,215 missed. The report is
`/home/viperjuice/workspace/tmp/treesitter-69-slice33/coverage.json`.
Grammar configuration still has 288 of 775 statements uncovered, so slice 33
covers the public configuration import command as an independent contract.

Remeasurement on merged `main` at `e43525ee` used the same representative
command with private workspace temporary and coverage data: 3,535 passed,
4 skipped, and two known load-sensitive failures in treesitter-chunker#130
(10.54 ms per operation against a 10 ms limit) and treesitter-chunker#131
(0.109 variance against a 0.05 limit); 28,795 of 40,000 statements executed
(71.9875%), 11,205 missed. The report is
`/home/viperjuice/workspace/tmp/treesitter-69-slice34/coverage.json`.
Grammar configuration still has 281 of 775 statements uncovered, so slice 34
covers the public set/get commands as an independent contract.

Remeasurement on merged `main` at `8e53b70e` used the same representative
command with private workspace temporary and coverage data: 3,538 passed,
4 skipped; 28,805 of 40,000 statements executed (72.0125%), 11,195 missed.
The report is
`/home/viperjuice/workspace/tmp/treesitter-69-slice35/coverage.json`.
Grammar configuration still has 265 of 775 statements uncovered, so slice 35
covers the public cache information display as an independent contract.

Remeasurement on merged `main` at `33584ca3` used the same representative
command: 3,550 passed, 4 skipped; 28,989 of 40,024 statements executed
(72.4290%), 11,035 missed. The report is
`/home/viperjuice/workspace/tmp/treesitter-69-slice36/coverage.json`.
`interfaces/stubs.py` is the only wholly uncovered module (137/137) and still
needs a confirmed consumer contract. The largest remaining gaps are
`grammar_management/cli.py` (666/1,216), `compatibility.py` (488/820),
`testing.py` (421/563), `core.py` (405/731), and `build/builder.py`
(298/332). Slice 36 covers a separate public grammar-versions fallback
contract. Its tags URL defect was filed as treesitter-chunker#242 and fixed
separately by treesitter-chunker#243 before this slice.

Remeasurement on merged `main` at `e5eb830f` used the same representative
command in a clean worktree: 3,552 passed, 4 skipped; 29,040 of 40,024
statements executed (72.5565%), 10,984 missed. The report is
`/home/viperjuice/workspace/tmp/treesitter-69-slice37/coverage.json`, SHA-256
`66afc6fdc1feb1d031ebd703acb84aea2a696fd0d48b6b9470761b4013923957`.
`interfaces/stubs.py` remains the only wholly uncovered module (137/137).
The largest remaining gaps are `grammar_management/cli.py` (617/1,216),
`compatibility.py` (488/820), `testing.py` (421/563), `core.py` (405/731),
and `build/builder.py` (298/332). Slice 37 tested real parse-failure
classification; slice 38 covers a distinct compatibility database export and
import contract. Live in-memory selection remaining stale after import is a
separate defect filed as treesitter-chunker#246.

Remeasurement on clean `main` at `afed17fc` before slice 38 used the same
representative command: 3,553 passed, 4 skipped; 29,059 of 40,024 statements
executed (72.6039%), 10,965 missed. The private report is
`/home/viperjuice/workspace/tmp/treesitter-69-slice38/coverage.json`, SHA-256
`891104fb9c109d7a999e9e7937c8b71f32ade03892501e3b9e33f072ccf2b573`.

Remeasurement on clean `main` at `28774c09` before slice 39 had 3,554 passed,
4 skipped, and one existing load-sensitive failure in treesitter-chunker#123:
five SQLite lock errors caused the small-files test to count 995 of 1,000
chunks. Its isolated rerun passed. Diagnostic coverage was 29,115 of 40,030
statements executed (72.7330%), 10,915 missed. The private report is
`/home/viperjuice/workspace/tmp/treesitter-69-slice39/coverage.json`, SHA-256
`1d9eee8af5228d7d12e4d1fbc74b99d9ae40e5ecd1a839e5015f75f05e217478`.
`interfaces/stubs.py` remains the sole wholly uncovered module (137/137);
the largest remaining gap is `grammar_management/cli.py` (617/1,216).

Remeasurement on clean `main` at `2f80a1fd` before slice 40 used the same
representative command: 3,559 passed, 4 skipped; 29,153 of 40,048 statements
executed (72.7951%), 10,895 missed. The private report is
`/home/viperjuice/workspace/tmp/treesitter-69-slice40/coverage.json`, SHA-256
`e642370b74695d85405928902ca0a07358374de99b9ed96d421b3fb7c72e633c`.
`interfaces/stubs.py` remains the sole wholly uncovered module (137/137),
and `grammar_management/cli.py` has 604 of 1,216 statements uncovered.
The separate cache-lock defects in treesitter-chunker#123 and
treesitter-chunker#251 were fixed before this slice.

Remeasurement on clean `main` at `0ff9d9c7` before slice 41 used the same
representative command: 3,559 passed, 4 skipped, and one existing
load-sensitive failure in treesitter-chunker#131 (streaming variance). Diagnostic
coverage was 29,164 of 40,048 statements executed (72.8226%), 10,884 missed.
The private report is
`/home/viperjuice/workspace/tmp/treesitter-69-slice41/coverage.json`, SHA-256
`1567e75b0cf3288b8f393d41a78f2a390d8bfb4bedaaba4bc26801403c7f3314`.
`interfaces/stubs.py` remains the sole wholly uncovered module (137/137),
and `grammar_management/cli.py` has 600 of 1,216 statements uncovered.

Remeasurement on clean `main` at `b63d9259` before slice 42 used the same
representative command: 3,561 passed, 4 skipped; 29,164 of 40,048 statements
executed (72.8226%), 10,884 missed. The private report is
`/home/viperjuice/workspace/tmp/treesitter-69-slice42/coverage.json`, SHA-256
`59491e9c61595fc1c1dcc1eaf320b80c07c1215665e6bd04e8f989963d963878`.
`interfaces/stubs.py` remains the sole wholly uncovered module (137/137),
and `grammar_management/compatibility.py` has 468 of 820 statements uncovered.

Remeasurement on clean `main` at `d7536655` before slice 43 used the same
representative command: 3,562 passed, 4 skipped, and one existing
load-sensitive failure in treesitter-chunker#131 (streaming variance).
Diagnostic coverage was 29,189 of 40,054 statements executed (72.8741%),
10,865 missed. The private report is
`/home/viperjuice/workspace/tmp/treesitter-69-slice43/coverage.json`, SHA-256
`99c9e7b367c2649de83a37fd80811065bbf872a8929cff6f36120b3460a23f92`.
`interfaces/stubs.py` remains the sole wholly uncovered module (137/137),
and `grammar_management/compatibility.py` has 445 of 826 statements uncovered.

Remeasurement on clean `main` at `d58c0775` before slice 44 used the same
representative command: 3,565 passed, 4 skipped; 29,238 of 40,057 statements
executed (72.9910%), 10,819 missed. The private report is
`/home/viperjuice/workspace/tmp/treesitter-69-slice44/coverage.json`, SHA-256
`84fbf4b359a87143e051a29a3a4b58d574572abdfb8ab21fd4dfe6074acd4c3d`.
`interfaces/stubs.py` remains the sole wholly uncovered module (137/137).
The active Svelte plugin has 122 of 219 statements uncovered, including
semantic extraction paths that existing tests mostly exercise with simulated
nodes.

Remeasurement on clean `main` at `991f27b7` before slice 45 used the same
representative command: 3,566 passed, 4 skipped; 29,261 of 40,062 statements
executed (73.0393%), 10,801 missed. The private report is
`/home/viperjuice/workspace/tmp/treesitter-69-slice45/coverage.json`, SHA-256
`9a88df2ffdda9bcd721c1eb7a723fc7aa1189564cd99ccfa36abf6451e2d3b76`.
`interfaces/stubs.py` remains the sole wholly uncovered module (137/137),
while the active JavaScript context module has 146 of 272 statements uncovered.
The import-binding and local-definition defects are tracked separately as
treesitter-chunker#264 and treesitter-chunker#267.

Remeasurement on then-current clean `main` at `90bf75d1` before slice 46 used
the representative full-suite command: 3,570 passed, 4 skipped, and two
load-sensitive performance-threshold failures under concurrent review work.
Coverage was 29,416 of 40,182 statements executed (73.2069%), 10,766 missed.
The private report is
`/home/viperjuice/workspace/tmp/treesitter-69-slice46/coverage.json`, SHA-256
`8356302899e3c76fc918ac3c46a0228227bdde792ff3595ab06bdd5ffecaf477`.
The two failures were timing assertions in
`tests/test_performance_advanced.py`; neither affected the coverage inventory.
The subsequent treesitter-chunker#276 merge only changed scope-analyzer caches,
so the grammar-list slice still uses this measurement.

| Current rank | Module (`chunker/` prefix omitted) | Missed / statements | Risk |
| ---: | --- | ---: | :---: |
| 1 | `interfaces/stubs.py` | 137 / 137 (zero covered) | M |
| 2 | `grammar_management/cli.py` | 598 / 1,216 | H |
| 3 | `grammar_management/testing.py` | 421 / 563 | L |
| 4 | `grammar_management/core.py` | 405 / 731 | H |
| 5 | `grammar_management/compatibility.py` | 380 / 834 | M |
| 6 | `build/builder.py` | 298 / 332 | H |
| 7 | `languages/compatibility/database.py` | 185 / 386 | H |
| 8 | `languages/compatibility/schema.py` | 181 / 407 | H |

Remeasurement on clean `main` at `57610dbc` before slice 47 used the full
suite with coverage and a dedicated workspace temporary directory: 3,578
passed, 4 skipped, and one timing-sensitive failure in
`tests/test_streaming.py::TestBufferOptimization::test_streaming_performance_consistency`
(observed variance 1.393 versus its 0.05 threshold). Coverage was 29,472 of
40,187 statements executed (73.3371%), 10,715 missed. The private JSON report
is `/home/viperjuice/workspace/tmp/treesitter-69-slice47-coverage.json`,
SHA-256 `fc2975f7604c39f0b750086a6f6bc2c0083033364898662b5056d09f49a4511c`.
The first attempt used pytest's default temporary area and hit its disk quota;
that run was discarded and its generated coverage fragments were removed.

| Current rank | Module (`chunker/` prefix omitted) | Missed / statements | Risk |
| ---: | --- | ---: | :---: |
| 1 | `interfaces/stubs.py` | 137 / 137 (zero covered) | M |
| 2 | `grammar_management/cli.py` | 592 / 1,216 | H |
| 3 | `grammar_management/testing.py` | 421 / 563 | L |
| 4 | `grammar_management/core.py` | 405 / 731 | H |
| 5 | `grammar_management/compatibility.py` | 380 / 834 | M |
| 6 | `build/builder.py` | 298 / 332 | H |
| 7 | `languages/compatibility/database.py` | 185 / 386 | H |
| 8 | `languages/compatibility/schema.py` | 181 / 407 | H |

Remeasurement on clean `main` at `dcad0fee` before slice 48 used the same
representative full-suite command with private workspace temporary and coverage
data: 3,589 passed, 4 skipped; 29,514 of 40,201 statements executed
(73.4161%), 10,687 missed. The private JSON report is
`/home/viperjuice/workspace/tmp/treesitter-69-slice48/coverage.json`, SHA-256
`318bc0784b00c2ac087c975f3cb84ce61d7b1a9545e14853e8ba4b91ff30fda7`.

| Current rank | Module (`chunker/` prefix omitted) | Missed / statements | Risk |
| ---: | --- | ---: | :---: |
| 1 | `interfaces/stubs.py` | 137 / 137 (zero covered) | M |
| 2 | `grammar_management/cli.py` | 585 / 1,218 | H |
| 3 | `grammar_management/testing.py` | 421 / 563 | L |
| 4 | `grammar_management/core.py` | 398 / 736 | H |
| 5 | `grammar_management/compatibility.py` | 380 / 834 | M |
| 6 | `build/builder.py` | 298 / 332 | H |
| 7 | `languages/compatibility/database.py` | 185 / 386 | H |
| 8 | `languages/compatibility/schema.py` | 181 / 407 | H |

Remeasurement on clean `main` at `8b2280bd` before slice 49 used the full
suite with coverage and a private workspace temporary directory: 3,589 passed,
4 skipped, and one timing-sensitive integration failure in
`tests/test_performance_advanced.py::TestConcurrentPerformance::test_thread_safety_performance`
(10.53 ms per operation versus its 10 ms limit). The failed test passed when
rerun alone without coverage. Coverage was 29,530 of 40,202 statements executed
(73.4541%), 10,672 missed. The private JSON report is
`/home/viperjuice/workspace/tmp/treesitter-69-slice49/coverage.json`, SHA-256
`6dfdd24330c61f52b17eb94349d6b0809f1a76bed971b0d46389270b4354fef4`.

| Current rank | Module (`chunker/` prefix omitted) | Missed / statements | Risk |
| ---: | --- | ---: | :---: |
| 1 | `interfaces/stubs.py` | 137 / 137 (zero covered) | M |
| 2 | `grammar_management/cli.py` | 567 / 1,219 | H |
| 3 | `grammar_management/testing.py` | 421 / 563 | L |
| 4 | `grammar_management/core.py` | 398 / 736 | H |
| 5 | `grammar_management/compatibility.py` | 380 / 834 | M |
| 6 | `build/builder.py` | 298 / 332 | H |
| 7 | `languages/compatibility/database.py` | 185 / 386 | H |
| 8 | `languages/compatibility/schema.py` | 181 / 407 | H |

Remeasurement on clean `main` at `c88f95c4` before slice 50 used the full
suite with coverage and a private workspace temporary directory: 3,590 passed,
4 skipped, and one timing-sensitive failure in
`tests/test_streaming.py::TestBufferOptimization::test_streaming_performance_consistency`
(variance 0.4048 versus its 0.05 threshold). The failed test passed when rerun
alone without coverage. Coverage was 29,533 of 40,202 statements executed
(73.4615%), 10,669 missed. The private JSON report is
`/home/viperjuice/workspace/tmp/treesitter-69-slice50/coverage.json`, SHA-256
`b3e8859a0940c45f7722cfd5fe6338b08ce787239db76480fbd38459e1a2e4be`.

| Current rank | Module (`chunker/` prefix omitted) | Missed / statements | Risk |
| ---: | --- | ---: | :---: |
| 1 | `interfaces/stubs.py` | 137 / 137 (zero covered) | M |
| 2 | `grammar_management/cli.py` | 563 / 1,219 | H |
| 3 | `grammar_management/testing.py` | 421 / 563 | L |
| 4 | `grammar_management/core.py` | 398 / 736 | H |
| 5 | `grammar_management/compatibility.py` | 380 / 834 | M |
| 6 | `build/builder.py` | 298 / 332 | H |
| 7 | `languages/compatibility/database.py` | 185 / 386 | H |
| 8 | `languages/compatibility/schema.py` | 181 / 407 | H |

Remeasurement on clean `main` at `8950b91f` before slice 51 used the full
suite with coverage and a private workspace temporary directory: 3,594 passed,
4 skipped; 29,537 of 40,202 statements executed (73.4715%), 10,665 missed.
The private JSON report is
`/home/viperjuice/workspace/tmp/treesitter-69-slice51/coverage.json`, SHA-256
`e5a0d0de97f58108f2c73fe6e7f2949978083362e59552d586279e6d511d5da0`.

| Current rank | Module (`chunker/` prefix omitted) | Missed / statements | Risk |
| ---: | --- | ---: | :---: |
| 1 | `interfaces/stubs.py` | 137 / 137 (zero covered) | M |
| 2 | `grammar_management/cli.py` | 563 / 1,219 | H |
| 3 | `grammar_management/testing.py` | 421 / 563 | L |
| 4 | `grammar_management/core.py` | 398 / 736 | H |
| 5 | `grammar_management/compatibility.py` | 380 / 834 | M |
| 6 | `build/builder.py` | 294 / 332 | H |
| 7 | `languages/compatibility/database.py` | 185 / 386 | H |
| 8 | `languages/compatibility/schema.py` | 181 / 407 | H |

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
| 29 — empty grammar directory cleanup | `grammar_management/config.py` `DirectoryManager.cleanup_empty_directories`: one cleanup removes empty user and cache child directories, preserves the managed cache roots and a nonempty build directory holding a parseable fixture, and a second cleanup removes nothing. | Parse the checked-in Python fixture with the pinned parser, then retain a copy under the build directory. Mutation **remove the managed-cache exemption** must fail because the emptied downloads root disappears. Extend the existing grammar config contract test file. |
| 30 — grammar configuration backup/restore | `grammar_management/config.py` `UserConfig.backup` and `restore`: a named backup captures directory and cache settings, restoring it after an intervening change restores the saved values in memory and on disk and preserves a pre-restore copy of the later values. A missing backup raises without changing the config. | Parse the checked-in Python fixture and retain a copy under the configured grammar directory. Mutations **restore the pre-restore copy instead of the selected backup** and **omit in-memory reload after restore** must fail. Extend the existing grammar config contract test file. Keep the separate missing-key defect in treesitter-chunker#220 outside this PR. |
| 31 — grammar configuration backup retention | `grammar_management/config.py` `UserConfig.cleanup_old_backups`: with three named JSON backups at distinct ages, retaining two removes only the oldest, preserves their parseable contents and a non-JSON neighbor, leaves the active config and grammar fixture intact, and a repeated cleanup changes nothing. | Parse the checked-in Python fixture and retain a copy under the configured grammar directory. Set deterministic backup modification times and inspect the retained JSON. Mutation **reverse newest-first backup ordering** must fail. Extend the existing grammar config contract test file. Keep the partial-config default aliasing defect in treesitter-chunker#225 separate. |
| 32 — public grammar configuration export | `grammar_management/config.py` `config_cli export` and `UserConfig.export_config`: exporting to a nested requested path writes the live cache and directory settings, leaves the active configuration and a parseable grammar fixture intact, and can be loaded from the exported file. | Invoke the public Click command against an isolated home with a checked-in Python fixture under the managed grammar directory; parse the fixture before and after export. Mutation **export factory defaults instead of live settings** must fail. Extend the existing grammar config contract test file. |
| 33 — public grammar configuration import | `grammar_management/config.py` `config_cli import-config`: confirmed default import merges an external partial config while preserving omitted active cache and directory settings; `--replace` discards those omitted settings. Both report success and leave the parseable grammar fixture intact. Keep failure exit status in treesitter-chunker#233. | Invoke the public Click command with confirmation against an isolated home and a checked-in Python fixture under the managed grammar directory; parse it before and after import. Mutation **invert the public merge/replace switch** (`not replace` to `replace`) must fail. Extend the existing grammar config contract test file. |
| 34 — public grammar configuration set/get | `grammar_management/config.py` `config_cli set` and `get`: public commands persist and display a user-selected grammar path, numeric cache limit, Boolean cleanup switch, and logging level with their intended types; the managed Python grammar fixture remains parseable. Keep failure exit status in treesitter-chunker#233. | Invoke public Click commands against an isolated home, parse the checked-in Python fixture before and after placing it under the managed grammar directory, and inspect saved JSON types and displayed values. Mutation **skip JSON value decoding in set** must fail when a numeric limit is rejected as a string. Extend the existing grammar config contract test file. |
| 35 — public grammar cache information | `grammar_management/config.py` `config_cli cache-info`: the public report distinguishes download and build cache sizes, reports their total and configured limits, and changes cleanup-needed from Yes to No when auto-cleanup is disabled without changing the cached files. | Invoke the public Click command against an isolated home with checked-in Python fixture copies padded to 512 KiB and 768 KiB under the configured grammar cache; parse both before and after. Mutation **display build size as download size** must fail. Extend the existing grammar config contract test file. |
| 36 — grammar versions fallback | `grammar_management/cli.py` `versions`: an empty tags response reports no tagged versions and suggests the development branch; an API refusal reports the failure and common branch hints while preserving the public command's successful fallback and leaving home untouched. | Parse the checked-in Python fixture with the pinned parser; stub only the external HTTP response while invoking the public Click command. Mutation **drop HTTP failure fallback** (catch only `ValueError` instead of the HTTP error) must fail. Extend the existing grammar CLI contract test file. |
| 37 — grammar error pattern analysis | `grammar_management/compatibility.py` `GrammarTester.analyze_error_patterns`: one valid Python fixture and two malformed variants report one successful parse, two syntax failures, a two-thirds failure rate, and the ranked error category without writing to home. | Parse the checked-in Python fixture and malformed variants with the pinned parser; pass those same sources through the real validator and tester in isolated temporary directories. Mutation **count failed parses as successes** must fail. Extend the existing grammar compatibility contract test file. |
| 38 — compatibility database JSON transfer | `languages/compatibility/database.py` `export_database` and `import_database`: a JSON export contains Python and JavaScript language and grammar versions, a Python compatibility rule, and a breaking change; importing it replaces prior records and preserves those relationships after reopening. The live-schema defect is treesitter-chunker#246 and remains outside this slice. | Parse checked-in Python and JavaScript fixtures with pinned parsers before writing representative records to temporary SQLite databases. Mutation **omit compatibility rules from export** must fail. Extend the existing language compatibility records contract test file. |
| 39 — unknown grammar fetch | `grammar_management/cli.py` `fetch`: a misspelled, unsupported language fails without running Git, suggests the configured Python source, and does not install files or write to the isolated home. | Parse the checked-in Python fixture with the pinned parser, then invoke the public Click command against a temporary grammar cache while forbidding external subprocess calls. Mutation **suppress the similar-language suggestion** must fail. Extend the existing public grammar CLI contract test file. |
| 40 — grammar removal confirmation | `grammar_management/cli.py` `remove`: declining the public confirmation preserves a user-installed source directory and its parseable Python fixture; accepting it removes that user directory while preserving a package copy and leaving the isolated home untouched. | Copy the checked-in Python fixture to user and package grammar directories, parse both with the pinned parser, and invoke the public Click command with explicit no/yes answers. Mutation **bypass declined confirmation** must fail. Extend the existing public grammar CLI contract test file. |
| 41 — grammar info JSON API | `grammar_management/cli.py` `ComprehensiveGrammarCLI.info_grammar`: the exported Python API returns parseable JSON identifying the selected user library path, priority, existence, size, and validation fields when a package candidate also exists, without writing to the caller's home. The public Click `info` command currently exposes table output only. | Parse the checked-in Python fixture with the pinned parser before and after inspecting JSON from two temporary local library candidates. Mutation **omit selected path from JSON metadata** must fail. Extend the existing public grammar CLI contract test file. |
| 42 — comprehensive syntax result | `grammar_management/compatibility.py` `GrammarTester.run_comprehensive_test`: a requested syntax run reports success for a real parseable Python fixture and failure with a syntax error for that fixture plus malformed source, without writing to the caller's home. Unsupported test types are a separate defect in treesitter-chunker#255. | Parse the checked-in Python fixture and malformed variant with the pinned parser, then run the exported tester against an isolated discoverable grammar candidate. Mutation **report success after a failed syntax parse** must fail. Extend the existing grammar compatibility contract test file. |
| 43 — parse benchmark result accounting | `grammar_management/compatibility.py` `GrammarTester.benchmark_parsing_performance`: a benchmark over a valid checked-in Python fixture and its malformed variant reports one success and one syntax failure, counts only the success in its summary, and leaves the isolated home untouched. | Feed the real fixture variants to the exported tester without mocking its generator, parser, or validator; parse the generated inputs with the pinned parser before running the benchmark. Mutation **count failed parse as successful benchmark** must fail. Extend the existing grammar compatibility contract test file. |
| 44 — Svelte semantic extraction | `languages/svelte.py` `SveltePlugin.get_semantic_chunks`: a real parsed component distinguishes module TypeScript and instance JavaScript scripts, reports the reactive statement and SCSS style, and preserves the source line of the each-block marker. | Parse a checked-in Svelte component fixture with the pinned parser and inspect the plugin's observable semantic records. Mutation **force module scripts to instance context** must fail. Add a focused Svelte semantic contract test; keep product defects separate. |
| 45 — JavaScript arrow parent context | `context/languages/javascript.py` `JavaScriptContextExtractor.extract_parent_context`: a call inside a parsed arrow function reports its enclosing lexical declaration with the `const` binding name, arrow signature, and source line, without exposing the body. | Parse a checked-in JavaScript fixture with the pinned parser, find the real call node, and inspect the exported extractor's parent-context item. Mutation **omit the arrow's lexical binding name** must fail. Add a focused context contract test; keep treesitter-chunker#264 and treesitter-chunker#267 separate. |
| 46 — grammar list JSON filter | `grammar_management/cli.py` `ComprehensiveGrammarCLI.list_grammars`: the exported list API filters discovered local grammar names case-insensitively and emits only the matching entry as parseable JSON; a miss returns an error without changing isolated home state. | Parse the checked-in Python and JavaScript service fixtures with pinned parsers, install two local library candidates under a temporary cache, and call the exported API without mocking its discovery. Mutation **ignore the language filter** must fail because the JSON contains both entries. Extend the public grammar CLI contract test; file unrelated defects separately. |
| 47 — validator cache replacement | `grammar_management/core.py` `GrammarValidator.validate_grammar`: an empty local grammar reports invalid, and replacing that path with the pinned working Python grammar produces a valid standard result in the same validator and after cache reload. | Parse the checked-in Python service fixture with the real compiled grammar, replace an invalid temporary candidate with that grammar, and inspect exported validation results. Mutation **omit file metadata from the validation cache key** must fail because the old invalid result is reused. Extend the public validator contract test; keep production defects separate. |
| 48 — grammar cleanup fallback | `grammar_management/cli.py` `grammar cleanup`: when optional core grammar management is unavailable, a requested 20-day cutoff removes a 25-day-old local download, preserves a 15-day-old one, reports one removal, and leaves the isolated home untouched. The inaccurate report for a later untouched directory is a separate defect in treesitter-chunker#295. | Parse the checked-in Python service fixture before and after invoking the public Click command against a temporary cache with core component availability disabled. Mutation **reverse the fallback age comparison** must fail because the stale fixture remains. Extend the public grammar CLI contract test. |
| 49 — recursive grammar cleanup fallback | `grammar_management/cli.py` `grammar cleanup`: when optional core management is unavailable, a 25-day-old download directory containing source is removed recursively, a recent build fixture remains parseable, and the public command reports one removal and only the changed directory without writing to the isolated home. | Parse the checked-in Python service fixture from the stale directory, then invoke the public Click command with a 20-day cutoff and parse the preserved recent fixtures. Mutation **skip recursive directory removal** must fail because the stale directory remains. Extend the existing fallback CLI contract test as an independent parameter case. |
| 50 — safe tar extraction | `build/builder.py` `_safe_extract_tar`: a nested ordinary Python source file is extracted byte-for-byte and remains parseable, while POSIX absolute and Windows drive-qualified members are rejected before any archive member is written. | Create tar archives from the checked-in Python service fixture and parse it with the pinned parser before and after valid extraction. Mutation **accept Windows drive-qualified members** must fail because the unsafe archive is no longer rejected. Extend the existing tar extraction contract tests; file any production defect separately. |
| 51 — Conda package presence | `build/builder.py` `BuildSystem.verify_build`: a Conda-style tar archive with index, file manifest, and parseable Python source under the recipe's noarch `site-packages/` path reports valid with all required components; the same archive without a package payload reports invalid with `package` missing. Platform-mismatch validity and versioned platform-specific package paths are separate defects in treesitter-chunker#300 and treesitter-chunker#302. | Build temporary tar.bz2 archives from the checked-in Python service fixture and parse that payload with the pinned parser. Mutation **omit package presence from artifact validity** must fail because the metadata-only archive is accepted. Extend the tar/build contract tests; keep the product fixes separate. |

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
Slice 46 exposed the unrelated ignored `grammar list --all` flag, filed as
treesitter-chunker#284; the JSON-filter slice does not repair it.
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

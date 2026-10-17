---
automation:
  suite_command: "uv run --locked --with toml --all-extras python scripts/run_full_suite.py"
---

# Repair Python/JavaScript Unicode grammar regression (treesitter-chunker#492)

## Task

Restore valid U+017F/U+212A parsing in the default supplier grammar path without
normalizing source, weakening parse errors, bypassing grammar gates or changing
the existing runtime/pack pins. This repair is independent of unmerged
treesitter-chunker#495 and does not include its graph change. Keep the Codegraph
adoption hold until a verified release and its separate downstream acceptance.

## Research summary

Base is fresh origin/main `f3c15eaef59b149ad74d606a2c3bb87e1b447b59`.
The primary deliberately older main, admitted S27, held Go/CLEANUP work and all
unmerged trees/ledgers/checkpoints/broker state are protected.

On Linux Python3.12.14, both runtimes0.25.2/0.26.0 pass with pack0.9.0 and fail
the four reported cases with pack1.20.0. Latest published pack1.22.1 also fails.
Compiling the committed parser C at pack1.20's pinned Python
`26855eabccb19c6abf499fbc5b8dc7cc9ab8bc64` and JavaScript
`58404d8cf191d69f2674a8fd507bd5776f46cb11` passes all13 expanded cases.
Regenerating those same revisions with the pack CI's CLI0.26.11/ABI14 recreates
the failures and introduces explicit lexer exclusions for0x17f/0x212a. This
isolates the generation boundary. Subsequent one-rule reproduction and upstream
tree-sitter/tree-sitter#5755 and tree-sitter/tree-sitter#5756 identify unconditional removal of the two
characters from broad Unicode classes. The same grammar sources regenerated
with CLI0.27.1/ABI14 pass all13 cases. The original R1 packet remains immutable;
corrected source/compiler/library/probe bindings supplement its exploratory
results, rather than treating an inherited build receipt as regenerated proof.
Official `tree-sitter-python==0.25.0` and
`tree-sitter-javascript==0.25.0` wheels pass all13 with runtime0.26.0, including
ASCII/other-Unicode controls and complete root byte lengths.

The existing provider in `chunker/_internal/language_pack.py` is the default
fallback after custom compiled grammars. Use the official wheels for Python/JS
at that boundary, retaining custom compiled grammar priority and the pack for
all other languages. No system compiler/downloaded replacement library is
required in normal installations. A broken required wheel must not silently
fall back to the known-bad pack grammar.

Boundary incremental `_grammar_version` currently includes only pack/runtime
versions. Resolve actual Python/JS selection through existing registry metadata
before building their key. Record a load-bound `grammar_source` capability:
`official:tree-sitter-python@0.25.0` (or JavaScript) for required wheels, or
`custom:sha256:<digest>` for the actual combined/individual library bytes selected.
Capture the custom digest at successful load/selection, not from a path guessed
later; discovery compatibility probes must not overwrite selected provenance.
Preserve that identity while a native image remains loaded; replacing native
files in place is unsupported until fresh registry/process initialization.
Use `tree-sitter-<language>:source=<grammar_source>:pack=<version>:runtime=<version>`.
This distinguishes official/custom switches and fresh loads of changed custom
bytes, invalidates old Python/JS keys, and leaves other-language keys unchanged.
Retain existing public metadata fields and add only this capability for Python/JS;
it does not change IR top-level/schema vocabulary. Keep cache formatv1
and all public IR vocabulary/identity algorithms unchanged. The frozen contract
in `docs/interface-boundary-spec.md` says existing fields cannot change meaning
within a major; this repair adds no resolution/identity/schema vocabulary.

## Changes

- `pyproject.toml`, `uv.lock`: add exact official Python/JS grammar0.25.0
  requirements; regenerate the lock with the release workflow's uv0.12.11 and
  reject unrelated resolution drift. Retain runtime>=0.26,<0.27 and pack>=1.20,<1.21.
- `chunker/_internal/language_pack.py`: load those two official grammar capsules
  before the pack fallback. Preserve existing other-language behavior, COBOL
  exclusion and explicit custom-grammar precedence.
  Missing official modules, native-load failure, missing/invalid capsules and
  unsupported official ABI produce an actionable existing `ParserInitError`
  naming the required distribution/reinstallation. Validate the official capsule
  with the runtime Parser at the provider boundary. These failures never
  return a missing-language condition that silently triggers pack or network
  acquisition. Reuse existing error types; add no broad fallback.
- `chunker/_internal/registry.py`: correct provider docstrings/logging so the
  official fallback is not falsely described as loading a pack binary. Keep
  selection priority intact. Track actual successful Python/JS source identity
  separately from discovery/compatibility probes and expose it through existing
  metadata capabilities. A real official fallback must not swallow its typed
  required-dependency error. Record actual combined/individual custom selection
  with its library digest; do not label custom bytes as an official wheel.
- `chunker/_internal/factory.py`: close `_create_parser`'s direct pack-parser
  recovery for Python/JS. An ABI-incompatible selected custom grammar or official
  grammar fails closed with actionable `ParserInitError`; do not silently switch
  to pack. Valid custom grammars retain priority. Other-language recovery stays.
- `chunker/parser.py`: normalized Python/JS missing-language failures terminate
  with actionable initialization guidance rather than on-demand fetch/build.
  Other languages retain their existing acquisition path.
- `chunker/boundary/adapter.py`: include the official distribution/version in
  default Python/JS grammar cache identity and actual custom-library digest when
  custom selection wins, as specified above. Resolve metadata through the actual
  registry, including its cached selection. Do not alter other-language keys or
  IR output fields. No source rewriting or invented identity on load failure.
- `tests/test_language_pack.py`, `tests/test_parser.py`: real Python/JS matrices
  for both characters across comments, identifiers, Python strings, JS strings,
  regex and JSX; ASCII/other-Unicode controls and independent Python `ast.parse`.
  Assert no error/missing nodes, original UTF-8 token slices and root bounds.
  Prove Python/JS default parsing does not call the bad pack loader and a missing
  required official grammar does not silently use it.
  Default-provider fixtures must isolate compiled-library discovery/loading and
  module parser/factory state, retain real official capsules, and assert the
  selected official identity. They must work when hosted CI has built grammars.
- `tests/test_core_span_consistency.py`: real chunk_text/chunk_file fixtures with
  Unicode before/within functions, CRLF and multibyte prefixes. Assert expected
  declarations, complete original content slices and half-open UTF-8 byte spans.
- `tests/test_registry_fallback.py`: preserve existing explicit local grammar
  precedence and lazy discovery through the changed default provider path.
  Use an actual compatible custom grammar, assert its selected identity/digest
  and forbid official-provider calls; a mere non-None assertion is insufficient.
- `tests/test_factory.py`: add `test_492_incompatible_custom_never_uses_pack` and
  `test_492_required_grammar_failure_never_uses_pack_or_build` (parametrize module,
  native-load, capsule and ABI failures). Exercise public parser acquisition with
  both pack loader functions and automatic fetch/build forbidden. Existing
  parser errors and positive compatible-custom behavior are controls.
- `tests/test_boundary_ir_incremental_runtime.py`: actual pre-fix persisted
  Python/JS cache records miss/reparse; corrected cold/warm/fresh parity and
  actual subsequent payload reuse. Assert unchanged keys for a non-overridden
  language and changed identity when an official grammar version changes. Keep
  tool/schema/source/options fixed in seeded old-cache and M2 proofs. Also test
  persisted warm-cache transitions official-to-custom, custom-to-official and
  fresh-registry loads of different custom library bytes, proving actual selected
  parsers, re-extraction and stable reuse within each unchanged provider.
- `tests/boundary_ir_conformance.py`: extend the existing fail-closed grammar
  pin assertion with exact equality to0.25.0 for both official distributions;
  mirror their exact pyproject requirements, not a broader fabricated interval.
  Existing runtime/
  pack guards remain; no expectation or golden is changed to hide a failure.
- `CONTRIBUTING.md`, `docs/packaging.md`, `docs/interface-boundary-spec.md`,
  `CHANGELOG.md`: declare the complete provider tuple, acquisition/provenance,
  custom-grammar scope, unchanged byte/source contracts and Python/JS cache
  re-extraction. State standalone pack grammars remain affected. Reserve this
  change for the existing Unreleased6.0.0 train; no release/tag/version changes.
- `scripts/run_platform_core.py`: include all five Unicode/span/cache regression
  files in COMMON_TESTS plus the two new factory node IDs named above. The
  existing hosted Linux/macOS/Windows workflow invokes this command after local
  builds, so the isolated default-provider assertions run in every matrix job.
  No workflow change is needed unless verification reveals a different path;
  amend scope/review before such edits.
- `tests/fixtures/boundary_ir/golden/*.json`: locked-generator output only if
  intentional parser differences occur; inspect every diff, repeat generator
  for idempotence, and reject unrelated output drift. No manual golden edits.
- This plan and `plans/manifest.json`: supported own-slug registration/lifecycle
  only. Preserve all predecessor rows/events and any concurrently merged entry;
  never import or overwrite treesitter-chunker#495's unmerged manifest state.

Everything else is read-only. Amend owned paths and obtain applicable review
before an implementation outside this boundary. No upstream repository edits,
global installations, new language discovery or resolver changes are included.

## Documentation impact

The default Python/JS grammar provider and dependency tuple change deliberately.
Declare exact artifacts and supported platforms; package version alone does not
authenticate the pack's first-use grammar downloads. Custom grammar overrides
remain caller-controlled. Registry publication, release readiness and Codegraph
source/corpus/cache acceptance are separate, unfulfilled gates, not implied by
local parser passes. Keep treesitter-chunker#492 open until its release and
downstream requirements are actually satisfied.

## Dependencies & order

1. Private owned worktree `codex/unicode-parser-492` from the stated fresh base.
   Authorize executor evidence reads/writes only under
   `/home/viperjuice/workspace/evidence/treesitter-chunker/unicode-parser-492/20261017/`
   and its canonical symlink target. Read-only reuse of the existing review
   helper at `call-token-dedupe-487/20261013/finish-20261016/review-seat.py` is
   allowed; do not modify that earlier evidence. Resolver-owned handoffs and
   reflections are permitted. Other private/raw evidence is protected.
2. Complete tools-enabled independent PLAN seats: Sol x2, Gemini3.8Flash and
   Astra, then reconcile all four together and obtain separate Astra president.
   At most3 complete PLAN rounds and3 CODE rounds, heartbeat only, no silence
   or model deadlines. Exact-head isolated clones and immutable file-pointer
   evidence packets; no peer opinions in seats. Manual reviews establish no
   formal Harness/supplier/native/IF qualification.
3. Seed actual baseline caches before production edits and run new regressions
   on baseline to observe designated failures. Implement the reviewed repair.
   Named mutations: M1 route Python/JS back to pack; M2 remove the official
   grammar cache identity. Both must fail designated observable assertions;
   restore exact candidate bytes and keep passing controls separately.
4. Verify original full/local/docs, actual private native Windows snapshot and
   exact-head hosted matrix. Build wheel/sdist; install built wheel outside the
   source checkout using an exact portable dependency lock with hashes and
   wheel-only installation. Confirm installed imports/artifact hashes and
   selected native wheel tags/platforms, then rerun Unicode/span/default-provider
   probes on Python3.11/3.12/3.13/3.14. Retain source verification on3.13 alongside
   the developer3.12 run and existing hosted3.11 lanes; preserve all existing
   release3.11–3.13 and installed-wheel3.12/3.14 gates. Missing wheel availability
   is a compatibility blocker, not a source-build substitute. Do not claim
   downstream corpus acceptance.
5. Complete owned lifecycle before final-head checks/review; any resulting
   head change requires applicable original/native/hosted checks and reviews.
   Obtain complete CODE quartet, separate final Astra acceptance and portable
   independently verified raw-evidence archive. Publish via supported API,
   link the PR, then normal authorized exact-head merge and safe owned pruning.
   Preserve every failed attempt. Existing-PR metadata refresh may still be
   unavailable; do not replay/modify broker state or bypass that limitation.

## Verification

Use locked Python3.12, private disk scratch with a short TMPDIR and original
runner outputs/head/source/runtime bindings. Refresh dependencies after edits.

```sh
uv sync --locked --all-extras --python 3.12
uv run --locked --all-extras pytest tests/test_language_pack.py tests/test_parser.py tests/test_registry_fallback.py tests/test_core_span_consistency.py tests/test_boundary_ir_incremental_runtime.py -q
uv run --locked --all-extras pytest tests/test_factory.py -q
uv run --locked --all-extras pytest tests/test_registry.py tests/test_boundary_ir_determinism.py tests/test_boundary_ir_golden_snapshots.py -q
uv run --locked --all-extras python scripts/regenerate_boundary_goldens.py
# Save first generated diff outside source; regenerate and require identical diff.
uv run --locked --all-extras python scripts/regenerate_boundary_goldens.py
uv run --locked --all-extras ruff check chunker/ cli/ tests/ --exclude archive --exclude logs --exclude site
uv run --locked --all-extras black --check chunker/ cli/ tests/ scripts/
uv run --locked --all-extras python scripts/mypy_gate.py
uv run --locked --with toml --all-extras python scripts/run_ci_smoke.py
uv run --locked --with toml --all-extras python scripts/run_platform_core.py --platform linux
uv run --locked --with toml --all-extras python scripts/run_full_suite.py
uv run --locked --all-extras --with mkdocs --with mkdocs-material --with mkdocstrings-python mkdocs build --strict --site-dir <private-temp-directory>
uv run --locked --all-extras python -m build
```

Native Windows: exact candidate private snapshot, locked refresh, first targeted
pytest command above and `uv run --locked --with toml --all-extras python
scripts/run_windows_preflight.py`. Bind all tracked bytes and runtime/grammar
versions; preserve shared Windows checkout and global native journals. Available
fleet Linux/macOS checks and hosted matrix must cover the final head.

Portable install proof must retain the wheel/sdist and dependency registry
digests, hashes-checked install commands, independent installed import paths,
interpreter versions and actual Unicode/span outcomes. Tests from a source cwd
or PYTHONPATH pointing at checkout do not establish installed wheel behavior.

## Acceptance criteria

- [ ] AC1: first targeted command proves all reported and expanded real parser
  cases, source-byte spans and chunk declarations on candidate; baseline and
  M1 fail designated Unicode assertions with controls/exact restoration.
- [ ] AC2: incremental tests prove actual old cache miss/reparse, corrected
  fresh/cold/warm parity, actual warm reuse and actual custom/official transitions;
  M2 is detected with other key inputs held fixed. Existing grammar
  pin/determinism/golden gates and idempotence pass for all supported languages.
- [ ] AC3: original runner/full/docs, isolated native/hosted and installed
  Python3.11/3.12/3.13/3.14 wheel-only artifact proofs pass with complete
  source/artifact provenance, plus source3.13 and hosted regression collection.
  Complete independent reviews and separate Astra acceptance are recorded.
- [ ] AC4: supported publication/lifecycle/linkage and verified standalone
  archive precede normal merge; protected state/predecessors remain intact.
  Release/downstream adoption remain explicitly pending rather than declared
  complete, and treesitter-chunker#492 remains open for those acceptance items.

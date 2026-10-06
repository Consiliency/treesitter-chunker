---
automation:
  suite_command: "uv run --locked --all-extras pytest tests/test_factory.py tests/test_parser.py tests/test_parser_lease.py tests/test_integration.py -q"
---

# Detailed plan: Reject unsupported parser configuration

## Task

Resolve treesitter-chunker#355 as the unsupported-configuration portion of
EC-RUNTIME-1. Explicit rejection is the supported behavior; no new cancellation
mechanism or runtime/pin upgrade is included. Download recovery remains
treesitter-chunker#357; native admission and complete RUNTIME acceptance remain
separate.

Round-one reconciliation also owns treesitter-chunker#399, filed separately before
this amendment. The public on-demand retry can mask configuration errors when
the factory resolves a language first. Validate request shape and installed
runtime capability before factory language resolution, parser creation or idle
checkout; these rejected requests then cannot enter the acquisition retry.

## Research summary

ParserConfig validates input types. Both public get_parser and exclusive
ParserFactory.acquire_parser apply it through _apply_config, which silently
ignores timeout_ms on pinned Tree-sitter 0.26 and always ignores logger. The
existing ParserConfigError already carries the option name/value and guidance.
Configured instances are deliberately not reused in the lease pool. Several
older tests and guide examples request ignored positive timeouts merely to
exercise configured parser creation; they must use an actually supported
configuration instead. Historical timeout setter/property tests remain relevant
to the compatibility branch.

## Changes

- chunker/_internal/factory.py, ParserFactory._apply_config: keep actual legacy
  timeout setter/property application; when timeout_ms is explicitly set and
  neither API exists, raise ParserConfigError naming timeout_ms and explaining
  that it must be omitted on this runtime. Reject a non-None logger explicitly
  with ParserConfigError and guidance to configure Python application logging.
  Check the unsupported logger before applying ranges. Retain ParserConfig
  signatures/type validation, supported ranges and thread/lease ownership.
- In the same file, ParserConfig.validate checks the installed Parser type's
  actual legacy timeout capability and rejects unsupported timeout/logger
  requests after shape checks. ParserFactory._validate_request calls validation
  before checking language availability. Direct _apply_config compatibility
  guards remain for its legacy setter/property use.
- tests/test_parser_lease.py: add real checked-in fixture tests for public and
  lease rejection of timeout 0, timeout 1 and an actual logging.Logger for both
  available and unavailable requested languages; malformed negative timeouts
  retain their option-specific shape error. Assert
  error option/guidance and subsequent unconfigured parsing remains usable.
  Add actual full-fixture Range parsing through a configured lease; no production
  factory, parser or configuration mocks. Existing configured-lease lifetime test
  uses ParserConfig() rather than an ignored timeout.
- tests/test_factory.py and tests/test_parser.py: existing positive configured
  creation tests use ParserConfig(); retain invalid input tests and actual legacy
  timeout application tests. The no-timeout-API case now expects the explicit
  ParserConfigError rather than silent success.
- tests/test_integration.py: replace all-language silent-timeout acceptance with
  real supported-parser rejection checks. Avoid adding dependency on previously
  unrequested grammar downloads.
- docs/api-reference.md, docs/user-guide.md, docs/internal-api.md and
  docs/architecture.md: describe explicit unsupported-option errors and migrate
  examples to supported ParserConfig/ranges. Python application logging stays
  outside ParserConfig.logger. CHANGELOG.md records this observable compatibility
  change. This plan and its own typed plans/manifest.json row are owned.

The docs state that invalid option types, negative timeouts and unsupported
timeout/logger requests take precedence over factory language lookup; range
element validation remains Tree-sitter's application-time check. No fetch/build
mocks or native-loading guarantee is
introduced by the real unavailable-language request cases.

## Dependencies and order

Start from current main, register this plan before edits and reproduce actual
silent acceptance using fixture parsing. Keep the production change separate
from treesitter-chunker#397's test-gate repair and integrate its accepted main
history before final full/hosted verification. Serialize publication and final
full runners with other active repairs. Review at most three substantive rounds,
manually with tools enabled and compact pointers. No native probe, pin, golden,
consumer lock, admitted ledger/checkpoint or cache identity changes.

## Verification

- uv sync --locked --all-extras
- uv run --locked --all-extras pytest tests/test_factory.py tests/test_parser.py tests/test_parser_lease.py tests/test_integration.py -q
- uv run --locked --all-extras ruff check chunker/ cli/ tests/ --exclude archive --exclude logs --exclude site
- uv run --locked --all-extras black --check chunker/ cli/ tests/ scripts/
- uv run --locked --all-extras python scripts/mypy_gate.py
- uv run --locked --with toml --all-extras python scripts/run_ci_smoke.py
- uv run --locked --all-extras pytest -q

Named mutation silently_ignore_unsupported_options removes both rejection
branches while retaining legacy application/ranges. The real public/lease tests
must fail their expected exception checks; restore exact production bytes and
require every focused test to pass. Require the original sealed runner,
changed-source Windows tests and standing preflight, exact-head hosted platforms,
and manual code review. This supplies rejection evidence, not parse cancellation
or a performance budget.

The additional resolve_language_before_configuration mutation moves request
validation below language lookup. All eight unavailable-language cases must
fail with the wrong exception category and restore with the entire focused suite.

## Acceptance criteria

- [ ] Actual public and leased requests reject unsupported explicit timeout and
  logger values with option-specific ParserConfigError and actionable guidance,
  proven by the fixture rejection cases and named mutation.
- [ ] Supported ranges and unconfigured real parsing remain usable before and
  after rejection; configured leases still are not reused. Legacy setters apply
  when actually present; invalid input checks remain intact.
- [ ] Examples and compatibility guidance match rejection behavior; original
  runner, restored focused tests, changed platforms and bounded reviews accept
  this repair without claiming cancellation or complete RUNTIME acceptance.

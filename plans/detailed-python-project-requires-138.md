---
automation:
  suite_command: "uv run --locked --all-extras pytest tests/test_python_version_hints_contract.py -q"
---

# Detailed plan: Retain declared Python project requirements

## Task and research

Resolve treesitter-chunker#138, the PEP621 subset of EC-COMPAT-2. The current
detector recognizes the first broad Python classifier before inspecting the
declared project requires-python value. The checked-in pyproject.toml therefore
selects3.0.0 instead of its declared>=3.11. Existing tests exercise actual
Python fixture parsing, setup.py declarations and shebang precedence.

## Changes

- chunker/languages/version_detection/python_detector.py: at the start of
  detect_from_requirements, parse valid TOML using the supported Python3.11+
  standard-library tomllib. Prefer a nonempty string project.requires-python
  before broad classifiers and preserve the exact constraint expression. Catch
  TOML syntax errors locally so existing setup/source/requirements detection
  still runs. Ignore comment/tool-table decoys; do not change existing source
  priority, Poetry fallback, normalization or invalid-TOML fallback policy.
- tests/test_python_version_hints_contract.py: use checked-in project metadata
  and private valid TOML fixtures with broad classifiers, simple and compound
  operators, and comments/tool-table decoys. Parse the real checked-in Python
  service fixture with the installed parser, use tomllib to prove valid fixture
  structure, and assert public detection/primary results retain constraints.
  Keep the existing real source/setup/shebang control; no detector/parser mocks.
- CHANGELOG.md: explain declared PEP621 requirement preference without claiming
  dependency resolution or enforcement of the returned constraint.
- This plan and its typed plans/manifest.json entry are owned control paths.

## Dependencies and order

Independent detector slice, serialized original full runner. Register first,
reproduce on unchanged production, implement the declared-field preference,
then kill and restore ignore_project_requires_python. File independently
discovered defects instead of silently widening scope. Use supported draft
publication and four manual tool-enabled reviewers, maximum three substantive
rounds. No native admission, parser pins, consumer locks or whole COMPAT claim.

## Verification

- uv sync --locked --all-extras
- uv run --locked --all-extras pytest tests/test_python_version_hints_contract.py -q
- uv run --locked --all-extras ruff check chunker/ cli/ tests/ --exclude archive --exclude logs --exclude site
- uv run --locked --all-extras black --check chunker/ cli/ tests/ scripts/
- uv run --locked --all-extras python scripts/mypy_gate.py
- uv run --locked --with toml --all-extras python scripts/run_ci_smoke.py
- uv run --locked --with toml --all-extras python scripts/run_platform_core.py --platform linux
- uv run --locked --with toml --all-extras python scripts/run_full_suite.py

The named actual production mutation must fail declared-project assertions;
exact restoration must pass the complete focused module. Require actual Windows
focused/standing checks and exact-head hosted platforms. External review and
platform records supplement original verification without formal IF acceptance.

## Acceptance criteria

- [ ] EC-COMPAT-2 PEP621 subset: valid project requires-python overrides broad
  classifiers and retains simple/compound constraint operators via public APIs.
- [ ] Decoys do not become project requirements, existing setup/shebang behavior
  remains, and the named actual mutation fails then fully restores.
- [ ] Original six checks, locked refresh/full tests/spec_tests, Windows, exact
  hosted checks and bounded manual reviews accept the declared-field contract.

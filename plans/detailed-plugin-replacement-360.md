---
automation:
  suite_command: "uv run --locked --all-extras pytest tests/test_plugin_system.py tests/test_plugin_initialization_failures.py tests/test_parser_plugin_integration.py tests/test_pluginconfig_single.py -q"
---

# Detailed plan: Activate replacement plugins after first use

## Task

Resolve treesitter-chunker#360 as an independently landable RUNTIME repair.
This proves the replacement-hook portion of EC-RUNTIME-2, not whole-phase acceptance.

## Research summary

PluginRegistry.register validates the new class and updates _plugins, but leaves
the language's cached instance in _instances. get_plugin returns that instance
when no explicit config is supplied. Its existing RLock protects construction;
class publication and cache invalidation must share that lock to prevent an
in-progress constructor from restoring the superseded instance.

## Changes

- chunker/plugin_manager.py: after existing registration validation, publish the
  class and evict only its language's cached instance under _instance_lock.
  Preserve metadata/extension validation, error behavior, APIs and config semantics.
  Read the unlocked cache hit once, so eviction cannot occur between a separate
  membership test and indexing. An overlapping caller may use its already
  obtained old instance, but must not fail with KeyError.
- tests/test_plugin_system.py: parse the checked-in Python service fixture through
  an actual manager before and after replacement. A concrete Python subclass
  stamps returned chunk metadata in its real processing hook. Assert the old warm
  cache is replaced, repeated unconfigured calls reuse the new instance, explicit
  config invokes the new hook without replacing its default cached instance,
  unrelated language instances survive and failed registration preserves the
  previous class/instance. No production parser/plugin mocks or timing gate.
  Exercise the real warmed getter/registration interleaving with a per-thread
  Python line trace and events; restore the prior trace in finally. The trace
  pauses a cache-hit return without substituting registry data or methods.
- scripts/run_platform_core.py: select the replacement regression on all platforms.
- docs/plugin-development.md and CHANGELOG.md: remove the fresh-manager workaround
  and document invalidation after successful registration. Existing references to
  previously returned objects remain valid objects; no in-flight cancellation or
  global plugin-state migration is promised.
- This plan and its typed plans/manifest.json entry are owned control artifacts.

## Dependencies and order

Use current main in a private worktree. Register the plan before source edits,
reproduce the stale instance on a real fixture, repair and verify. Integrate
accepted neighboring records without rewriting any existing lifecycle. Separately
file unrelated defects; no native admission, parser pin or consumer lock change.

## Verification

- uv sync --locked --all-extras
- uv run --locked --all-extras pytest tests/test_plugin_system.py tests/test_plugin_initialization_failures.py tests/test_parser_plugin_integration.py tests/test_pluginconfig_single.py -q
- uv run --locked --all-extras ruff check chunker/ cli/ tests/ --exclude archive --exclude logs --exclude site
- uv run --locked --all-extras black --check chunker/ cli/ tests/ scripts/
- uv run --locked --all-extras python scripts/mypy_gate.py
- uv run --locked --with toml --all-extras python scripts/run_ci_smoke.py
- uv run --locked --all-extras pytest -q

Kill retain_old_cached_plugin by removing only the cache eviction. The real
replacement assertion must fail, then restore all focused modules. Kill
cache_hit_split_lookup by restoring separate membership/indexing; the real
interleaved getter must fail, then restore all focused modules. Run changed
fixture tests on Windows, exact-head hosted platforms and manual tool-enabled
review. Original runner records remain untouched; no supplemental IF is claimed.

## Acceptance criteria

- [ ] Real parsed chunks invoke the replacement hook after warming the original
  instance; subsequent default calls cache the replacement.
- [ ] Explicit config remains isolated, unrelated cached languages survive and
  failed registration leaves the previous working plugin usable.
- [ ] The named mutation fails and restores; original runner and platform checks
  plus code review accept the repair, with matching documentation.

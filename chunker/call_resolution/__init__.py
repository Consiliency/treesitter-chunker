"""Opt-in scope-aware call resolution (treesitter-chunker#682), experimental.

The ``call_resolution`` option narrows call edges that name-only resolution
leaves ``ambiguous``. It only removes candidates, and an edge becomes
``resolved`` only when its one remaining candidate is proven by a binding
(plan ``plans/detailed-scoped-call-resolution-682.md`` sections 6.3 and 7).

Modules:

- :mod:`.facts`: per-file scope facts, their schema and fact versions;
- :mod:`.engine`: eligibility, the binding-proof algorithm, the kind and
  family filters and provenance (pure functions, no filesystem access);
- :mod:`.js_scope` and :mod:`.py_scope`: the per-language analyzers;
- :mod:`.allowlist`: the binding allow-list.

At this head the JS/TS analyzer implements the Tier 1 core (plan section
13.1, PR 2): the scope chain, ``t1.lexical`` and ``t1.ts_overload``.
Script-goal top levels and namespace bodies give interim ``none`` reasons.
The Python analyzer is still a stub: every Python call has the outcome
``none(stub)``, so only the kind and family filters can narrow a Python edge.
"""

from __future__ import annotations

from .engine import (
    BINDING_RULE_IDS,
    KNOWN_RULE_IDS,
    NON_CALLABLE_KINDS,
    language_family,
)
from .facts import (
    ANALYZED_LANGUAGES,
    CALL_RESOLUTION_FACT_VERSIONS,
    KNOWN_NONE_REASONS,
    compute_scope_facts,
    fact_version,
    unsupported_scope_facts,
    valid_scope_facts,
)

__all__ = [
    "ANALYZED_LANGUAGES",
    "BINDING_RULE_IDS",
    "CALL_RESOLUTION_FACT_VERSIONS",
    "KNOWN_NONE_REASONS",
    "KNOWN_RULE_IDS",
    "NON_CALLABLE_KINDS",
    "compute_scope_facts",
    "fact_version",
    "language_family",
    "unsupported_scope_facts",
    "valid_scope_facts",
]
